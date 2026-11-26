# SPDX-License-Identifier: GPL-3.0-or-later
import bpy, bmesh
import time, os, re, io

from . import ldl, utils

class ObjectLightmapImport:
	@staticmethod
	def read(file):
		mesh_count = utils.read_u32(file)
		name = utils.read_string(file)
		
		mesh_lightmaps = []
		for im in range(mesh_count):
			uv_count = utils.read_u32(file)
			data = []
			for i in range(uv_count):
				data.append((utils.read_float16(file), utils.read_float16(file)))
			mesh_lightmaps.append(ldl.MeshLightmap(data))
			
			
		return ldl.ObjectLightmap(name, mesh_lightmaps)
	
class LightmapImport:
	@staticmethod
	def read(path):
		with open(path, "rb") as f:
			file = io.BytesIO(f.read())
		unk1 = utils.read_u32(file)
		object_count = utils.read_u32(file)
		
		lightmaps = []
		for i in range(object_count):
			lightmaps.append(ObjectLightmapImport.read(file))
		
		return ldl.Lightmap(unk1, lightmaps)
	
def load_texture(texture_path, name):
	fullpath = texture_path + name
	texture = None
	try:
		texture = bpy.data.images.load(fullpath + ".png", check_existing=True)
	except: # Texture png not found, fall back to dds
		texture = bpy.data.images.load(fullpath + ".dds", check_existing=True)
	return texture
	
class LDLImport:
	def __init__(self, ldl):
		self.ldl = ldl
	
	@staticmethod
	def from_file(path):
		ldl = LightmapImport.read(path)
		return LDLImport(ldl)
	
	def print(self):
		ldl = self.ldl
		print(ldl.unk1)
		for lightmap in ldl.lightmaps:
			print(lightmap.name)
	
	# New material to mix lightmap texture with base texture
	@staticmethod
	def make_lightmap_material_from_existing(old_material, lightmap_image): 
		lightmap_material = old_material.copy()
		lightmap_material.name = old_material.name + "_lightmap"
		lightmap_material.use_nodes = True
		lightmap_material_nodes = lightmap_material.node_tree.nodes
		lightmap_material_links = lightmap_material.node_tree.links
		
		bsdf = lightmap_material_nodes["Principled BSDF"]
		
		# Get original input node to base color
		base_color_input = bsdf.inputs["Base Color"]
		original_output = None
		if base_color_input.is_linked:
			original_output = base_color_input.links[0].from_socket
			lightmap_material_links.remove(base_color_input.links[0])
		
		# Nodes to mix original input with lightmap
		texture_node = lightmap_material_nodes.new("ShaderNodeTexImage")
		texture_node.image = lightmap_image
		uv_node = lightmap_material_nodes.new("ShaderNodeUVMap")
		uv_node.uv_map = "lightmap"
		lightmap_material_links.new(texture_node.inputs["Vector"], uv_node.outputs["UV"])
		
		mix_node = lightmap_material_nodes.new("ShaderNodeMixRGB")
		mix_node.blend_type = "MULTIPLY"
		mix_node.inputs["Fac"].default_value = 1.0
		lightmap_material_nodes.update()

		if original_output:
			lightmap_material_links.new(mix_node.inputs["Color1"], original_output)
		else:
			print(f"LDL: Original material '{old_material.name}' to apply lightmap to has no base color input")
			mix_node.inputs["Color1"].default_value = base_color_input.default_value

		lightmap_material_links.new(mix_node.inputs["Color2"], texture_node.outputs["Color"])
		lightmap_material_links.new(base_color_input, mix_node.outputs["Color"])
		return lightmap_material
	
	def apply_to_scene(self, lightmap_image, collection):
		scene = bpy.context.scene
		bpy.ops.object.select_all(action="DESELECT")
		
		instances_collection = utils.find_child_collection(collection, "_instances")
		if instances_collection is None:
			raise Exception("LDL: Level collection '" + collection.name + "' has no _instances child collection")
		candidates = [
			obj for obj in instances_collection.objects 
			if obj.instance_collection is not None 
			and len(obj.instance_collection.all_objects) >= 1
		]
		
		match_dict = {}
		for object_lightmap in self.ldl.lightmaps:
			name = object_lightmap.name[object_lightmap.name.find("/")+1:object_lightmap.name.rfind(".ldo")]
				
			instance = None
			for object in candidates:
				instance_collection = object.instance_collection
				names_to_match = None
				if object.name in match_dict:
					names_to_match = match_dict[object.name]
				else:
					names_to_match = [
						object.name,
						instance_collection.name
					]
					names_to_match.extend(child_collection.name for child_collection in instance_collection.children)
					match_dict[object.name] = names_to_match
				
				found = False
				for match_name in names_to_match:
					found |= name in match_name
					if found:
						break
				if not found:
					continue
				
				instance = object
				break
			if instance is None:
				continue
			candidates.remove(instance)
			
			instance.select_set(True)
			bpy.ops.object.duplicates_make_real(use_base_parent=True, use_hierarchy=True)
			instance.select_set(False)

			def mesh_sort_key(obj):
				m = re.search(r"Mesh (\d+)", obj.name)
				return int(m.group(1)) if m else 0	
			mesh_candidates = list(instance.children)
			for child in mesh_candidates:
				if len(child.children) > 0:
					extension = [c for c in child.children if c.data is not None]
					mesh_candidates.extend(sorted(extension, key=mesh_sort_key))
			mesh_candidates = [c for c in mesh_candidates if c.data is not None]
			
			print("LDL: Applying lightmap " + name + " to object " + instance_collection.name)
			for mesh_lightmap in object_lightmap.mesh_lightmaps:
				lightmap_data = mesh_lightmap.data
				if len(lightmap_data) == 0:
					continue
				
				found_child = None
				for child in mesh_candidates:
					if child.data is not None and len(lightmap_data) == len(child.data.vertices):
						found_child = child # Mesh has no lightmap yet
				if found_child is None:
					continue
				mesh_candidates.remove(found_child)
				
				print("LDL: Applying lightmap " + name + " to mesh " + found_child.name)
				me = found_child.data.copy()
				found_child.data = me
				
				for i in range(len(me.materials)):
					lightmap_material = LDLImport.make_lightmap_material_from_existing(me.materials[i], lightmap_image)
					me.materials[i] = lightmap_material
				
				bm = bmesh.new()
				bm.from_mesh(me)
				uv_map = bm.loops.layers.uv.new("lightmap")
				
				bm.verts.ensure_lookup_table()
				for iv, vert in enumerate(bm.verts):
					for loop in vert.link_loops:
						uv = lightmap_data[iv]
						loop[uv_map].uv = (uv[0], 1.0 - uv[1])
						
				bm.to_mesh(me)
				bm.free()
				#me.uv_layers["lightmap"].active = True
				#me.uv_layers["lightmap"].active_render = True
					

def import_ldl_file(path, collection):
	time_start = time.perf_counter()
	
	if not path:
		raise Exception("No path specified for ldl import")
	if not collection:
		raise Exception("No collection specified for ldl import")
	lightmap_path = os.path.dirname(path) + "/"
	lightmap_name = os.path.splitext(os.path.basename(path))[0] + "_lgt0000"
	if not os.path.isfile(lightmap_path + lightmap_name + ".dds"):
		raise Exception("No corresponding lightmap image found")
	lightmap_image = load_texture(lightmap_path, lightmap_name)
	
	ldl_import = LDLImport.from_file(path)
	print("LDL: Importing done after {0:.4f}s".format(time.perf_counter() - time_start))
	#ldl_import.print()
	ldl_import.apply_to_scene(lightmap_image, collection)
	print("LDL: Adding to scene done after {0:.4f}s".format(time.perf_counter() - time_start))