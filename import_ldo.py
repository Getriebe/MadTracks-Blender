# SPDX-License-Identifier: GPL-3.0-or-later
import bpy, bmesh, mathutils
import time, os, io

from . import ldo, utils, compat

class MaterialImport:
	@staticmethod
	def read(file):
		name = utils.read_string(file)
		flags = utils.read_u32(file)
		
		color1  			= utils.read_color(file)  if (flags & ldo.Material.FLAG_COLORED1) 	else None
		color2  			= utils.read_color(file)  if (flags & ldo.Material.FLAG_COLORED2) 	else None
		reflectivity		= utils.read_float(file)  if (flags & ldo.Material.FLAG_REFLECTIVE) else None
		texture 			= utils.read_string(file) if (flags & ldo.Material.FLAG_TEXTURED) 	else None
		emissive_strength   = utils.read_float(file)  if (flags & ldo.Material.FLAG_EMISSIVE) 	else None
		
		specularity = utils.read_float(file)  if (flags & ldo.Material.FLAG_REFLECTMAP) else None
		specmap 	= utils.read_string(file) if (flags & ldo.Material.FLAG_REFLECTMAP) else None
		
		return ldo.Material(
			name,
			flags,
			color1,
			color2,
			reflectivity,
			texture,
			emissive_strength,
			specularity,
			specmap
		)
	
class VertexGroupImport:
	@staticmethod
	def read(file, format_specifier_list):
		vertex_data = []
		for format_specifier in format_specifier_list:
			format = ldo.Mesh.FormatList[format_specifier]
			if format[2] == "Color":
				vertex_data.extend(utils.read_u8(file, 4))
			else:
				vertex_data.extend(utils.read_float(file, format[1]))
		
		return ldo.VertexGroup(
			vertex_data
		)

class IndexGroupImport:
	@staticmethod
	def read(file, old_version):
		material_index, index_count = utils.read_u32(file, 2)
		indices = []
		read_func = utils.read_u16 if not old_version else utils.read_u32
		for i in range(index_count):
			indices.append(list(read_func(file, 3)))
		
		return ldo.IndexGroup(
			material_index,
			indices
		)
	
class MeshImport:
	@staticmethod
	def read(file, old_version): 
		vertex_groups_count, face_count, vertex_groups_size, flags = utils.read_u32(file, 4)
		
		bounds = utils.read_vector4(file)
		mesh_ID = utils.read_u32(file)
		vertex_format_count = utils.read_u8(file)
		
		vertex_format = []
		for vertex_format_index in range(vertex_format_count):
			vertex_format.append(utils.read_u8(file))
			
		if vertex_groups_size != ldo.Mesh.calculate_vertex_group_size(vertex_format):
			raise Exception("Size of vertex groups specified does not match actual size")    
		
		vertex_groups = []
		for vertex_group_index in range(vertex_groups_count):
			vertex_groups.append(VertexGroupImport.read(file, vertex_format))
		
		index_groups_count = utils.read_u32(file)
		index_groups = []
		for index_group_index in range(index_groups_count):
			index_groups.append(IndexGroupImport.read(file, old_version))
			
		if face_count != ldo.Mesh.calculate_num_faces(index_groups):
			raise Exception("Number of faces specified in mesh does not match number of faces read")
			
		return ldo.Mesh(
			flags,
			bounds,
			mesh_ID,
			vertex_format,
			vertex_groups,
			index_groups
		)

class NodeImport:
	@staticmethod
	def read(file):
		flags, child_count = utils.read_u8(file, 2)
		
		translate_type = flags & ldo.Node.MASK_TRANSLATETYPE
		translation = None
		if (translate_type == 0x0040):
			translation = mathutils.Matrix.Translation(utils.read_vector3(file))
		elif (translate_type == 0x0080):
			translation = utils.read_matrix_4x4(file)
		else:
			translation = mathutils.Matrix.Translation((0, 0, 0))
		
		child_ID, parent_ID = utils.read_u32(file, 2)
		name_len = flags & ldo.Node.MASK_NAMELENGTH
		node_name = "No Name"
		if (name_len > 0):
			node_name = utils.read_string(file, name_len)
		children = []
		for child_index in range(child_count):
			children.append(NodeImport.read(file))
		
		return ldo.Node(
			flags,
			translation,
			child_ID,
			parent_ID,
			node_name,
			children
		)
	
class AtomicImport:
	@staticmethod
	def read(file, old_version):
		mesh_count     = None
		material_count = None
		end_of_file = 0
		is_animated = False 
		if not old_version:
			mesh_count     = utils.read_u16(file)
			material_count = utils.read_u16(file)
			end_of_file = utils.read_u8(file)
			if (end_of_file != 0):
				raise Exception("LDO: Detected EOF byte")
			is_animated = utils.read_u8(file)
		else:
			mesh_count     = utils.read_u32(file)
			material_count = utils.read_u32(file)
			# TODO: check is_animated
			
		bounds = utils.read_vector4(file)
		
		if old_version:
			utils.read_u8(file)
		
		materials = []
		for material_index in range(material_count):
			materials.append(MaterialImport.read(file))
			
		meshes = []
		for mesh_index in range(mesh_count):
			meshes.append(MeshImport.read(file, old_version))
		
		hierarchy = NodeImport.read(file)
		
		return ldo.Atomic(
			end_of_file,
			is_animated,
			bounds,
			materials,
			meshes,
			hierarchy
		)
	
class ObjectImport:
	@staticmethod
	def read(path):
		with open(path, "rb") as f:
			file = io.BytesIO(f.read())
		object_name = os.path.splitext(os.path.basename(path))[0]
		
		object_version, atomic_version, mesh_version, material_version = utils.read_u8(file, 4)
		old_version = (atomic_version == 2 and mesh_version == 1 and material_version == 2)
		
		atomic_count = None
		if not old_version:
			atomic_count = utils.read_u16(file)
		else:
			atomic_count = utils.read_u32(file)
		
		atomics = []
		for atomic_index in range(atomic_count):
			atomics.append(AtomicImport.read(file, old_version))

		return ldo.Object(
			object_name,
			object_version,
			atomic_version,
			mesh_version,
			material_version,
			atomics
		)

def load_texture(texture_path, name):
	fullpath = os.path.join(texture_path, name)
	texture = None
	try:
		texture = bpy.data.images.load(fullpath + ".png", check_existing=True)
	except: # Texture png not found, fall back to dds
		texture = bpy.data.images.load(fullpath + ".dds", check_existing=True)
	return texture

class LDOImport:
	def __init__(self, ldo):
		self.ldo = ldo
	
	@staticmethod
	def from_file(path, version):
		ldo = ObjectImport.read(path)
		return LDOImport(ldo)
	
	def add_to_scene(self, texture_path):
		scene = bpy.context.scene
		
		atomic_collection = bpy.data.collections.new(self.ldo.object_name)
		scene.collection.children.link(atomic_collection)
		
		for ida, atomic in enumerate(self.ldo.atomics):
			atomic_name = "Atomic " + str(ida)
			
			collection = bpy.data.collections.new(atomic_name)
			atomic_collection.children.link(collection)
			
			# Setup materials
			materials = []
			for material in atomic.materials:
				flags = material.flags
				name  = material.name
				
				# Reuse materials
				#if name in bpy.data.materials:
				#   materials.append(bpy.data.materials[name])
				
				mtl = bpy.data.materials.new(name)
				mtl.use_nodes = True
				mtl.use_backface_culling = True
				bsdf = mtl.node_tree.nodes["Principled BSDF"]
				
				color = mathutils.Color((1, 1, 1))
				if flags & ldo.Material.FLAG_COLORED2:
					color = material.color2
				elif flags & ldo.Material.FLAG_COLORED1:
					color = material.color1
				color_node = mtl.node_tree.nodes.new("ShaderNodeRGB")
				color_node.outputs["Color"].default_value = [color.r, color.g, color.b, 1.0]
				
				compat.bsdf_input(bsdf, "Roughness").default_value = 0.0
				compat.bsdf_input(bsdf, "Specular").default_value = 0.0
					
				if flags & ldo.Material.FLAG_TEXTURED: 
					texture_node = mtl.node_tree.nodes.new("ShaderNodeTexImage")
					texture_node.image = load_texture(texture_path, material.texture)
					
					mix_node = mtl.node_tree.nodes.new("ShaderNodeMixRGB")
					mix_node.blend_type = 'MULTIPLY'
					mtl.node_tree.links.new(bsdf.inputs["Base Color"], mix_node.outputs["Color"])
					if flags & ldo.Material.FLAG_TRANSPARENT: # Alpha blend
						mtl.node_tree.links.new(bsdf.inputs["Alpha"], texture_node.outputs["Alpha"])
					else: # Alpha tested (decals)
						clip_node = mtl.node_tree.nodes.new("ShaderNodeMath")
						clip_node.name = clip_node.label = "Alpha Clip"
						clip_node.operation = 'GREATER_THAN'
						clip_node.inputs[1].default_value = 0.5
						mtl.node_tree.links.new(clip_node.inputs[0], texture_node.outputs["Alpha"])
						mtl.node_tree.links.new(bsdf.inputs["Alpha"], clip_node.outputs["Value"])
					compat.set_transparent(mtl)
					
					mtl.node_tree.links.new(mix_node.inputs["Color1"], texture_node.outputs["Color"])
					mtl.node_tree.links.new(mix_node.inputs["Color2"], color_node.outputs["Color"])
				else:
					mtl.node_tree.links.new(bsdf.inputs["Base Color"], color_node.outputs["Color"])
				
				if flags & ldo.Material.FLAG_EMISSIVE:
					s = material.emissive_strength
					compat.bsdf_input(bsdf, "Emission").default_value = (s, s, s, 1.0)
					if "Emission Strength" in bsdf.inputs: # defaults to 0.0 in Blender 4.0+
						bsdf.inputs["Emission Strength"].default_value = 1.0

				if flags & ldo.Material.FLAG_REFLECTMAP:
					compat.bsdf_input(bsdf, "Specular").default_value = material.specularity
					
					specmap_node = mtl.node_tree.nodes.new("ShaderNodeTexImage")
					specmap_node.image = load_texture(texture_path, material.specmap)
					mtl.node_tree.links.new(bsdf.inputs["Roughness"], specmap_node.outputs["Color"])
				
				materials.append(mtl)
				
			
			hierarchy_dict = { } # Map mesh_IDs to parent_ID, translation and name
			object_refs = { } # Map mesh_IDs to objects
			
			def enum_nodes(_node):
				hierarchy_dict[_node.child_ID] = [_node.parent_ID, _node.translation, _node.node_name]
				for node in _node.children:
					enum_nodes(node)
			enum_nodes(atomic.hierarchy)
			
			for idm, mesh in enumerate(atomic.meshes):
				object_name = "Mesh " + str(idm)
				
				me = bpy.data.meshes.new(object_name)
				object = bpy.data.objects.new(object_name, me)
				
				bm = bmesh.new()
				bm.from_mesh(me)

				object_refs[mesh.mesh_ID] = object
				
				# Vertices & Normals
				if not mesh.has_vertex_data("Vertex"):
					raise Exception("Cannot import mesh without vertices")
					
				has_normals = mesh.has_vertex_data("Normal")
				for vertex_group in mesh.vertex_groups:
					pos = vertex_group.get_value("Vertex", mesh.vertex_format)
					vert = bm.verts.new(pos)
					if has_normals:
						vert.normal = vertex_group.get_value("Normal", mesh.vertex_format)
				bm.verts.ensure_lookup_table()
				compat.set_auto_smooth(me, True)
				
				# Indices / Faces & UV Maps
				has_uv_maps = []
				for i in range(4):
					b = mesh.has_vertex_data("Textcoord{}uv".format(i))
					if b: has_uv_maps.append(i)
				
				uv_maps = []
				for _ in has_uv_maps:
					uv_maps.append(bm.loops.layers.uv.new())
					
				for ig, index_group in enumerate(mesh.index_groups):
					object.data.materials.append(materials[index_group.material_index])
					for index_list in index_group.indices:
						indices = ( bm.verts[index_list[0]], 
									bm.verts[index_list[1]], 
									bm.verts[index_list[2]] )
						face = bm.faces.new(indices)
						face.smooth = True
						face.material_index = ig
						
						for uv_map_num in range(len(has_uv_maps)):
							for uv_loop in range(3):
								uv = mesh.vertex_groups[index_list[uv_loop]].get_value("Textcoord{}uv".format(has_uv_maps[uv_map_num]), mesh.vertex_format)
								uv.y = 1.0 - uv.y
								face.loops[uv_loop][uv_maps[uv_map_num]].uv = uv
				
				# Convert axis
				bmesh.ops.transform(bm, matrix=ldo.axis_conversion_matrix, space=object.matrix_world, verts=bm.verts)
				
				bm.verts.ensure_lookup_table()  
				bm.to_mesh(me)
				bm.free()
				
				# Set custom normals
				#me.use_auto_smooth = True
				#normals = []
				#for vertex_group in mesh.vertex_groups:
				#   normal = (vertex_group.vertex_data[3], vertex_group.vertex_data[5], vertex_group.vertex_data[4])
				#   normals.append(normal)
				#me.normals_split_custom_set_from_vertices(normals)
			
			# Parent objects and set names
			for child_ID, info in hierarchy_dict.items():
				parent_ID   = info[0]
				matrix  	= info[1]
				name		= info[2]
				
				if child_ID in object_refs: # Mesh associated with ID, set parent
					object   = object_refs[child_ID]
					if parent_ID != 0:
						parent = object_refs[parent_ID]
						parent.users_collection[0].objects.link(object)
						object.parent = parent
						object.matrix_local = ldo.axis_conversion_matrix @ matrix @ ldo.inverse_axis_conversion_matrix
					else: # Parent is the root
						collection.objects.link(object)
						object.matrix_local = matrix
					if name != "No Name":
						object.name = name
					
					ldo.debug_print("LDO: Parented mesh: child: {} parent: {} with name: {}".format(child_ID, parent_ID, name))
				
				else: # Create dummy as no mesh with ID exists
					if child_ID == 0 and parent_ID == 0: # Skip Root
						continue
					dummy = bpy.data.objects.new(name, None)
					dummy.empty_display_type = 'ARROWS'
					dummy.empty_display_size = 0.25
					dummy.show_name 		 = True
					
					if parent_ID != 0:
						parent = object_refs[parent_ID]
						parent.users_collection[0].objects.link(dummy)
						dummy.parent = parent
						# Use bpy.ops to ensure relative parenting
						#bpy.context.scene.objects.active = parent
						#bpy.ops.select_all(action="DESELECT")
						#dummy.select = True
						#bpy.ops.object.parent_set(keep_transform=True)
						#bpy.ops.select_all(action="DESELECT")
						dummy.matrix_local = ldo.axis_conversion_matrix @ matrix
					else:
						collection.objects.link(dummy)
						dummy.matrix_local = matrix
					
					# Add the dummy to the id <-> object database, in case the dummy has children
					if not child_ID in object_refs:
						object_refs[child_ID] = dummy
					
					ldo.debug_print("LDO: Created dummy: child: {} parent: {} with name: {}".format(child_ID, parent_ID, name))
		
		return atomic_collection
				
def import_ldo_file(path, texture_path, version=2):
	time_start = time.perf_counter()
	if not texture_path:
		texture_path = os.path.dirname(path) + "/../../../Graph/maps/High/"
	if not os.path.isdir(texture_path):
		raise Exception("No texture path was given and default not applicable")
		
	ldo_import = LDOImport.from_file(path, version)
	ldo.debug_print("LDO: Importing done after {0:.4f}s".format(time.perf_counter() - time_start))
	object_collection = ldo_import.add_to_scene(texture_path)
	ldo.debug_print("LDO: Adding to scene done after {0:.4f}s".format(time.perf_counter() - time_start))
	return object_collection