# SPDX-License-Identifier: GPL-3.0-or-later
import bpy, bmesh, mathutils
import time, os, io

from . import ldo, utils, compat

def image_base_name(image):
	name = bpy.path.basename(image.filepath) or image.name
	return os.path.splitext(utils.remove_dot_suffix(name))[0]

class MaterialExport:
	def write(file, instance):
		utils.write_string(file, instance.name)
		utils.write_u32(file, instance.flags)
		
		if (instance.flags & ldo.Material.FLAG_COLORED1):
			utils.write_color(file, instance.color1)
			
		if (instance.flags & ldo.Material.FLAG_COLORED2):
			utils.write_color(file, instance.color2)
			
		if (instance.flags & ldo.Material.FLAG_REFLECTIVE):
			utils.write_float(file, instance.reflectivity)
			
		if (instance.flags & ldo.Material.FLAG_TEXTURED):   
			utils.write_string(file, instance.texture)
			
		if (instance.flags & ldo.Material.FLAG_EMISSIVE):
			utils.write_float(file, instance.emissive_strength)
			
		if (instance.flags & ldo.Material.FLAG_REFLECTMAP):
			utils.write_float(file, instance.specularity)
			utils.write_string(file, instance.specmap)

class VertexGroupExport:
	def write(file, instance, format_specifiers):
		data_pointer = 0
		for format_specifier in format_specifiers:
			format = ldo.Mesh.FormatList[format_specifier]
			if format[2] == "Color": # Write int, not float
				for i in range(4):
					utils.write_u8(file, instance.vertex_data[data_pointer + i])
				data_pointer += 4
			else: # Always floats
				for i in range(format[1]):
					utils.write_float(file, instance.vertex_data[data_pointer + i])
				data_pointer += format[1]

class IndexGroupExport:
	def write(file, instance, old_version):
		utils.write_u32(file, (instance.material_index, len(instance.indices)))
		
		write_func = utils.write_u16 if not old_version else utils.write_u32
		for indices in instance.indices:
			write_func(file, (indices[0], indices[1], indices[2]))

class MeshExport:
	def write(file, instance, old_version):
		num_faces = ldo.Mesh.calculate_num_faces(instance.index_groups)
		vertex_groups_size = ldo.Mesh.calculate_vertex_group_size(instance.vertex_format)
		utils.write_u32(file, (len(instance.vertex_groups), num_faces, vertex_groups_size, instance.flags))
		utils.write_vector4(file, instance.bounds)
		utils.write_u32(file, instance.mesh_ID)
		utils.write_u8(file, len(instance.vertex_format))
		
		for vertex_format_specifier in instance.vertex_format:
			utils.write_u8(file, vertex_format_specifier)
		
		for vertex_group in instance.vertex_groups:
			VertexGroupExport.write(file, vertex_group, instance.vertex_format)
		
		utils.write_u32(file, len(instance.index_groups))
		for index_group in instance.index_groups:
			IndexGroupExport.write(file, index_group, old_version)

class NodeExport:   
	def write(file, instance):
		if len(instance.node_name) > ldo.Node.MASK_NAMELENGTH:
			raise Exception("Name is too long to fit in flags of hierarchy node")
		
		# Set name length in flags
		name_len = 0 if instance.node_name == "No Name" else len(instance.node_name)
		instance.flags |= name_len & ldo.Node.MASK_NAMELENGTH
		
		utils.write_u8(file, (instance.flags, len(instance.children)))
		
		translate_type = instance.flags & ldo.Node.MASK_TRANSLATETYPE
		if translate_type != 0:
			matrix = instance.translation
			if translate_type == 0x0040:
				utils.write_vector3(file, matrix.to_translation())
			elif translate_type == 0x0080:
				utils.write_matrix_4x4(file, matrix)
		
		utils.write_u32(file, (instance.child_ID, instance.parent_ID))
		if instance.node_name != "No Name":
			utils.write_string(file, instance.node_name, extra=False)
		for child in instance.children:
			NodeExport.write(file, child)

class AtomicExport:
	def write(file, instance, old_version):
		if not old_version: 
			utils.write_u16(file, (len(instance.meshes), len(instance.materials)))
			utils.write_u8(file, (instance.end_of_file, instance.is_animated))
		else:
			utils.write_u32(file, (len(instance.meshes), len(instance.materials)))
		
		utils.write_vector4(file, instance.bounds)
		
		if old_version:
			utils.write_u8(file, 0)
		
		for material in instance.materials:
			MaterialExport.write(file, material)
		
		for mesh in instance.meshes:
			MeshExport.write(file, mesh, old_version)
			
		NodeExport.write(file, instance.hierarchy)
	
class ObjectExport:
	def write(instance, path, old_version):
		file = io.BytesIO() # Build in memory, so a failed export never leaves an incomplete .ldo
		object_version   = 1
		atomic_version   = 3 if not old_version else 2
		mesh_version	 = 2 if not old_version else 1
		material_version = 3 if not old_version else 2
		utils.write_u8(file, (object_version, atomic_version, mesh_version, material_version))
		
		if not old_version:
			utils.write_u16(file, len(instance.atomics))
		else:
			utils.write_u32(file, len(instance.atomics))
		
		for atomic in instance.atomics:
			AtomicExport.write(file, atomic, old_version)

		with open(path, 'wb') as out:
			out.write(file.getvalue())
		
def calculate_bounds(objects):
	if not isinstance(objects, bpy.types.bpy_prop_collection):
		objects = [objects]
	points = []
	for obj in objects:
		if obj.data is not None:
			points.extend([obj.matrix_world @ vertex.co for vertex in obj.data.vertices])
	if not points:
		return mathutils.Vector((0.0, 0.0, 0.0, 0.0))

	def get_center(list):
		return (max(list) + min(list)) / 2 if list else 0.0
	
	x, y, z = [[point[i] for point in points] for i in range(3)]
	bounding_sphere_center = mathutils.Vector([get_center(axis) for axis in [x, y, z]]) if (x and y and z) else None
	bounding_sphere_radius = max(((point - bounding_sphere_center) for point in points)) if bounding_sphere_center else None
	sphere = bounding_sphere_center.to_4d()
	sphere.w = bounding_sphere_radius.length * 2.5
	return sphere

class LDOExport:
	def __init__(self, ldo):
		self.ldo = ldo
		
	def write(self, path, old_version):
		ObjectExport.write(self.ldo, path, old_version)
	
	@staticmethod
	def from_scene(root_collection):
		scene = bpy.context.scene
		
		if len(root_collection.objects) != 0:
			raise Exception("Root collection must strictly contain only child collections to be exported as atomics")
		
		object_name = utils.remove_dot_suffix(root_collection.name)
		atomics = []
		for atomic_collection in root_collection.children:
			ldo.debug_print("LDO: Reading Atomic " + atomic_collection.name)
			
			if len(atomic_collection.children) != 0:
				raise Exception("Atomic collection must strictly contain only child objects to be exported as meshes")
			if len(atomic_collection.objects) <= 0:
				raise Exception("Atomic collection must contain at least one mesh")
			
			# Gather all materials
			atomic_materials = []
			material_dict = {}
			for object in atomic_collection.objects:
				ldo.debug_print("LDO: Reading materials of object '" + object.name + "'")
				
				if object.data is not None and len(object.material_slots) <= 0:
					raise Exception("Mesh must have at least one material assigned to it")
				
				for slot in object.material_slots:
					mtl = slot.material
					if mtl is None:
						continue
					mtl_name = utils.remove_dot_suffix(mtl.name)
					if mtl_name in material_dict:
						continue
					# Material not saved already, add it

					material_name = mtl_name
					material_flags = 0
					
					material_color1 = None
					material_texture = None
					bsdf = mtl.node_tree.nodes["Principled BSDF"]
					color_input = bsdf.inputs["Base Color"]
					if len(color_input.links) <= 0:
						ldo.debug_print("LDO: Material {} has nodes not enabled".format(material_name))
						material_flags |= ldo.Material.FLAG_COLORED1
						col1 = color_input.default_value
						material_color1 = mathutils.Color((col1[0], col1[1], col1[2]))
					else:
						color_input = color_input.links[0].from_node
						if color_input.bl_idname == "ShaderNodeMixRGB": # Color and texture
							material_flags |= ldo.Material.FLAG_COLORED1
							material_flags |= ldo.Material.FLAG_TEXTURED
							pure_color_input = color_input.inputs["Color2"].links[0].from_node
							texture_input    = color_input.inputs["Color1"].links[0].from_node
							col1 = pure_color_input.outputs["Color"].default_value
							material_color1  = mathutils.Color((col1[0], col1[1], col1[2]))
							material_texture = image_base_name(texture_input.image)
							# Alpha linked from a texture => blended and flag. "Alpha Clip" node => alpha test and no flag
							alpha_input = bsdf.inputs["Alpha"]
							if alpha_input.is_linked and alpha_input.links[0].from_node.bl_idname == "ShaderNodeTexImage":
								material_flags |= ldo.Material.FLAG_TRANSPARENT
						elif color_input.bl_idname == "ShaderNodeRGB": # Just color
							material_flags |= ldo.Material.FLAG_COLORED1
							col1 = color_input.outputs["Color"].default_value
							material_color1 = mathutils.Color((col1[0], col1[1], col1[2]))
						elif color_input.bl_idname == "ShaderNodeTexImage":
							material_flags  |= ldo.Material.FLAG_COLORED1
							material_flags  |= ldo.Material.FLAG_TEXTURED
							material_color1  = mathutils.Color((1.0, 1.0, 1.0))
							material_texture = image_base_name(color_input.image)
					
					material_emissive_strength = None
					emissive_color = compat.bsdf_input(bsdf, "Emission")
					if emissive_color is not None:
						e_r, e_g, e_b, e_a = emissive_color.default_value
						if e_r > 0.01 or e_g > 0.01 or e_b > 0.01:
							material_flags |= ldo.Material.FLAG_EMISSIVE
							material_emissive_strength = e_r # TODO: Is this correct?
					
					material_specmap = None
					material_specularity = None
					spec_input = bsdf.inputs["Roughness"]
					if spec_input.links is not None and len(spec_input.links) > 0:
						spec_input = spec_input.links[0]
						if spec_input is not None:
							spec_input = spec_input.from_node
							if spec_input.bl_idname == "ShaderNodeTexImage":
								material_flags |= ldo.Material.FLAG_REFLECTMAP
								material_specmap = image_base_name(spec_input.image)
								material_specularity = compat.bsdf_input(bsdf, "Specular").default_value
					
					material_reflectivity = None
					if material_flags & ldo.Material.FLAG_REFLECTMAP:
						material_flags |= ldo.Material.FLAG_REFLECTIVE
						material_reflectivity = 10.0
					
					material = ldo.Material(material_name, material_flags,
											material_color1, None,
											material_reflectivity, material_texture,
											material_emissive_strength, material_specularity,
											material_specmap)
					
					material_dict[material_name] = material
					atomic_materials.append(material)
			
			# Gather all meshes of atomic
			atomic_meshes = []
			mesh_id_dict = {}
			for object in atomic_collection.objects:
				ldo.debug_print("LDO: Reading mesh of object '" + object.name + "'")
				meOriginal = object.data
				
				if meOriginal is None: # Skip dummies
					continue
				
				# Separate UV Islands
				me = bpy.data.meshes.new_from_object(object)
				object.data = me
				uv_split_copy_name = object.data.name + "_uv_split"
				me.name = uv_split_copy_name
				
				object.select_set(True)
				bpy.context.view_layer.objects.active = object
				bpy.ops.object.select_all(action="DESELECT")
				bpy.ops.object.mode_set(mode='EDIT')
				
				bm = bmesh.from_edit_mesh(me)
				old_seams = [e for e in bm.edges if e.seam]
				# unmark
				for e in old_seams:
					e.seam = False
				# mark seams from uv islands
				bpy.ops.uv.seams_from_islands()
				seams = [e for e in bm.edges if e.seam]
				# split on seams
				bmesh.ops.split_edges(bm, edges=seams)
				# re instate old seams.. could clear new seams.
				for e in old_seams:
					e.seam = True
				bmesh.update_edit_mesh(me)
				
				bpy.ops.object.mode_set(mode='OBJECT')
				
				# Copy original normals back
				compat.set_auto_smooth(me, True)
				object_normal_transfer_source = bpy.data.objects.new(object.name + "_normal_transfer", meOriginal)
				object_normal_transfer_source.matrix_local = object.matrix_local
				data_xfer_modifier = object.modifiers.new(name="", type="DATA_TRANSFER")
				data_xfer_modifier.object = object_normal_transfer_source
				data_xfer_modifier.use_loop_data = True
				data_xfer_modifier.data_types_loops = {"CUSTOM_NORMAL"}
				data_xfer_modifier.loop_mapping = "TOPOLOGY"
				bpy.ops.object.modifier_apply(modifier=data_xfer_modifier.name)
				bpy.ops.object.select_all(action="DESELECT")
				object_normal_transfer_source.data = None
				bpy.data.objects.remove(object_normal_transfer_source)
				compat.calc_split_normals(me)
				
				# In order to export the vertices correctly, it is required to undo any transformation to them
				# The transformations get applied later on by the hierarchy
				object_matrix_backup = object.matrix_world.copy()
				if object.data is not None:
					object.matrix_world = mathutils.Matrix()
				
				bm = bmesh.new()
				bm.from_mesh(me, face_normals=False)
				bm.verts.ensure_lookup_table()
				# Convert axis back
				bmesh.ops.transform(bm, matrix=ldo.inverse_axis_conversion_matrix, space=object.matrix_world, verts=bm.verts)
				
				mesh_vertex_format = []
				ldo.Mesh.add_vertex_format(mesh_vertex_format, "Vertex")
				ldo.Mesh.add_vertex_format(mesh_vertex_format, "Normal")
				
				num_vertex_color_layers = len(bm.loops.layers.color)
				if num_vertex_color_layers:
					if num_vertex_color_layers >= 2:
						raise Exception("Only one color layer is supported by .ldo format")
					ldo.Mesh.add_vertex_format(mesh_vertex_format, "Color")
				
				num_uv_layers = len(bm.loops.layers.uv)
				if num_uv_layers > 4:
					raise Exception("A maximum of 4 uv layers is supported by .ldo format")
				for layer_num in range(num_uv_layers):
					ldo.Mesh.add_vertex_format(mesh_vertex_format, "Textcoord{}uv".format(layer_num))
				
				vertex_groups = []
				for iv, vertex in enumerate(bm.verts):
					grp = ldo.VertexGroup([])
					grp.set_value("Vertex", mesh_vertex_format, vertex.co)
					
					link_loop = vertex.link_loops[0]
					original_normal = me.loops[link_loop.index].normal
					grp.set_value("Normal", mesh_vertex_format, ldo.inverse_axis_conversion_matrix @ original_normal)
						
					if num_vertex_color_layers: # vertex color
						color_layer = bm.loops.layers.color.active
						color = link_loop[color_layer]
						grp.set_value("Color", mesh_vertex_format, color)
						
					for layer_num in range(num_uv_layers): # uv
						uv_layer = bm.loops.layers.uv[layer_num]
						uv = link_loop[uv_layer].uv
						grp.set_value("Textcoord{}uv".format(layer_num), mesh_vertex_format, (uv.x, 1.0 - uv.y))
					
					vertex_groups.append(grp)
				
				index_groups = []
				for idm, mat in enumerate(atomic_materials):
					has_material = False
					for slot in object.material_slots:
						if slot is None:
							continue
						if utils.remove_dot_suffix(slot.material.name) == mat.name:
							has_material = True
					
					if has_material:
						index_groups.append(ldo.IndexGroup(idm, []))
				
				for poly in me.polygons:
					if len(poly.vertices) > 3:
						raise Exception("ldo format only supports tris")
					
					indices = [poly.vertices[0], poly.vertices[1], poly.vertices[2]]
					index_groups[poly.material_index].indices.append(indices)
					
				object.matrix_world = object_matrix_backup
				ldo_mesh = ldo.Mesh(4, calculate_bounds(object), -1, mesh_vertex_format, vertex_groups, index_groups)
				mesh_id_dict[object.name] = ldo_mesh
				atomic_meshes.append(ldo_mesh)
				bm.free()
				object.data = meOriginal
				bpy.data.meshes.remove(me)
			
			### Setup hierarchy ###
			hierarchy_root = ldo.Node(0, None, 0, 0, "No Name", [])
			hierarchy_dict = { 0: hierarchy_root }
			
			child_nodes = []
			current_mesh_index = 1
			
			for ob in atomic_collection.objects:
				def export_node(parent, object):
					nonlocal current_mesh_index
					ldo.debug_print("LDO: Setting up hierarchy for object '" + object.name + "'")
					me = object.data
					
					child_node_flags = 0
					
					child_loc = mathutils.Matrix(object.matrix_local)
					child_translation, child_rotation, child_scale = child_loc.decompose()
					child_node_translation = None
					if (   child_translation.length >= 0.001 
						or child_rotation != mathutils.Quaternion((1,0,0,0))
						or child_scale != mathutils.Vector((1,1,1))):
						ldo.debug_print("LDO: Saving matrix of object " + object.name)
						child_node_flags |= 0x0080
						if me is None:
							child_node_translation = ldo.inverse_axis_conversion_matrix @ child_loc @ ldo.inverse_axis_conversion_matrix
						else:
							child_node_translation = ldo.inverse_axis_conversion_matrix @ child_loc

					child_node_child_ID = current_mesh_index
					child_node_parent_ID = 0 # parent is root by default
					if object.parent is not None:
						child_node_parent_ID = parent.child_ID # parent is another object
					
					child_node_node_name = utils.remove_dot_suffix(object.name)
					child_node_children = []
					
					child_node = ldo.Node(child_node_flags, child_node_translation,
										  child_node_child_ID, child_node_parent_ID,
										  child_node_node_name, child_node_children)
					
					
					parent.children.append(child_node)
					if object.name in mesh_id_dict: # Dummies are not meshes
						mesh_id_dict[object.name].mesh_ID = current_mesh_index
						
					hierarchy_dict[current_mesh_index] = child_node
					current_mesh_index += 1
					
					for child in object.children:
						export_node(child_node, child)
				
				if ob.parent is None:
					export_node(hierarchy_root, ob)
			
			atomics.append(ldo.Atomic(0, 0, calculate_bounds(atomic_collection.objects), atomic_materials, atomic_meshes, hierarchy_root))
	
		return LDOExport(ldo.Object(object_name, 1, 3, 2, 3, atomics))

def export_ldo_file(path, root_collection, old_version=False):
	time_start = time.perf_counter()
	ldo_export = LDOExport.from_scene(root_collection)
	ldo.debug_print("LDO: Converting from scene done after {0:.4f}s".format(time.perf_counter() - time_start))
	ldo_export.write(path, old_version)
	ldo.debug_print("LDO: Writing to file done after {0:.4f}s".format(time.perf_counter() - time_start))
