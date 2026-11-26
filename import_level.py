# SPDX-License-Identifier: GPL-3.0-or-later
import bpy, bmesh, mathutils
import time, os, math, itertools

from . import ldo, import_ldo, utils, compat

class INIParser:
	def __enum_sections__(self):
		current_section = "DEFAULT"
		current_dict = {}
		
		def push_dict():
			if current_section not in self.data:
				self.data[current_section] = []
			values = self.data[current_section]
			values.append(current_dict)
		
		for line in self.file:
			if line.startswith("["):
				# Push data
				if current_section != "DEFAULT":
					push_dict()
				
				# Move on
				current_section = line[1:line.rfind("]")]
				current_dict = {}
			elif line.isspace():
				continue
			else:
				line = "".join(line.split())
				line = line.replace(" ", "")
				split = line.split("=")
				if len(split) < 2:
					continue
				key = split[0]
				value = split[1] # split[2] might be after comma
				current_dict[key] = value
		push_dict()
	
	def __init__(self, path):
		with open(path, 'r', errors='ignore') as f:
			self.file = f
			self.data = {
				#"DEFAULT" : [{"name1" : "test1"}, {"name2" : "test2"}]
			}
			self.__enum_sections__()
		
	def has_section(self, section):
		if section in self.data:
			return True
		return False
	
	def has_key(self, section, key):
		if not self.has_section(section):
			return False
		sections = self.data[section]
		has_all = True
		for s in sections:
			has_all &= key in s
		return has_all
		
	def get(self, section, key):
		if self.has_section(section):
			sections = self.data[section]
			for s in sections:
				if key in s:
					v = s[key]
					return v if hasattr(v, "__len__") else v[0]
		
worlds = {
	0  : "FrBistrot",
	1  : "WorldTest",
	3  : "UkMiniGolf",
	4  : "GerBal",
	5  : "UkStairs",
	6  : "UsRoofs",
	7  : "GerRamparts", # Castle
	8  : "US_ToyStore",
	9  : "FR_Musee",
	10 : "Antartique"
}

def import_level(path, texture_path, version=2):
	level_name = os.path.splitext(os.path.basename(path))[0]
	levels_path = os.path.dirname(path)
	if os.path.splitext(path)[1] != ".ini":
		raise Exception("Invalid level file given")
	
	scene = bpy.context.scene
	level_collection = bpy.data.collections.new(level_name)
	instance_collection = bpy.data.collections.new(level_name + "_instances")
	library_collection = bpy.data.collections.new(level_name + "_library")
	library_collection.hide_render = True
	library_collection.hide_select = True
	library_collection.hide_viewport = True
	level_collection.children.link(instance_collection)
	level_collection.children.link(library_collection)
	scene.collection.children.link(level_collection)
	
	def vector3_from_ini(value, key):
		return tuple(float(v) for v in value[key].split(","))
	
	def vector3_from_ini2(ini, section, key):
		s = ini.get(section, key)
		return tuple(float(v) for v in s.strip().split(","))
	
	# Level file
	settings = INIParser(os.path.splitext(path)[0] + ".dam")
	world_value = settings.get("base", "World")
	world_name = worlds.get(int(world_value)) if world_value is not None else None
	if world_name is not None:
		ldo.debug_print("World: " + world_name)
		world = INIParser(levels_path + "/../universes/" + world_name + ".ini")
		world_mesh_name = world.get("base", "Mesh")
		if world_mesh_name is not None:
			filepath = levels_path + "/../../Gfx/models/Geometry/" + world_mesh_name.split("/")[1]
			world_collection = import_ldo.import_ldo_file(filepath.replace("\"", ""), texture_path)
			if world_collection is not None:
				library_collection.children.link(world_collection)
				scene.collection.children.unlink(world_collection)
				instance = bpy.data.objects.new(world_collection.name + "_instance", None)
				instance.instance_collection = world_collection
				instance.instance_type = "COLLECTION"
				instance.show_axis = True
				instance_collection.objects.link(instance)
	
		if world.has_section("Skybox"):
			skybox_position = vector3_from_ini2(world, "Skybox", "Position")
			skybox_size 	= float(world.get("Skybox", "Scale")) * 2
			skybox_textures = {}
			sides = ["Back", "Front", "Right", "Left", "Up", "Down"]
			for side in sides:
				skybox_textures[side] = world.get("Skybox", side)
			
			me = bpy.data.meshes.new(name="Skybox_Mesh")
			skybox = bpy.data.objects.new(name="Skybox", object_data=me)
			bm = bmesh.new()
			bmesh.ops.create_cube(bm, size=skybox_size)
			bm.to_mesh(me)
			bm.free()
			skybox.location = skybox_position
			level_collection.objects.link(skybox)
			compat.set_auto_smooth(me, False)
			skybox.name = "Skybox"
			skybox.hide_select = True
			
			side_to_polyindex = {
				"Right" : 0,
				"Front" : 1,
				"Left"  : 2,
				"Back"  : 3,
				"Down"  : 4,
				"Up"	: 5
			}
			uv_layer_block = me.uv_layers.active or me.uv_layers.new(name="UVMap")
			uv_layer = uv_layer_block.data
			for i, side in enumerate(sides):
				material = bpy.data.materials.new("Skybox_" + side)
				material.use_nodes = True
				bsdf = material.node_tree.nodes["Principled BSDF"]
				texture_node = material.node_tree.nodes.new("ShaderNodeTexImage")
				texture_node.image = import_ldo.load_texture(texture_path, skybox_textures[side].replace("\"", ""))
				material.node_tree.links.new(bsdf.inputs["Base Color"], texture_node.outputs["Color"])
				skybox.data.materials.append(material)
				poly = skybox.data.polygons[side_to_polyindex[side]]
				poly.material_index = i
				poly.use_smooth = True
				correct_uvs_side = ((0.0, 0.0),(0.0, 1.0),(1.0, 1.0),(1.0, 0.0))
				correct_uvs_down = ((1.0, 0.0),(0.0, 0.0),(0.0, 1.0),(1.0, 1.0))
				correct_uvs_up   = ((0.0, 1.0),(1.0, 1.0),(1.0, 0.0),(0.0, 0.0))
				correct_uvs = (correct_uvs_up if side == "Up" else correct_uvs_down if side == "Down" else correct_uvs_side)
				for i, loop in enumerate(range(poly.loop_start, poly.loop_start + poly.loop_total)):
					uv_layer[loop].uv = correct_uvs[i]
	
	# Objects file
	with open(path, "r") as level_file:
		level_lines = level_file.readlines()
	current_section = {}

	previous_out = None
	for line in itertools.chain(level_lines, ["[]\n"]):  # sentinel flushes the last section
		
		if line.isspace():
			continue
		elif line.startswith("["):
			
			if "Filename" in current_section:
				filename = current_section["Filename"].replace("\"", "")
				split_ext = os.path.splitext(filename)
				editor_name = os.path.basename(split_ext[0])
				from_ini = False
				invert   = False
				unknown  = False
				if split_ext[1] != ".ldo":
					object_ini = INIParser(levels_path + "/../Descriptors/" + filename)
					
					new_filename = None
					if not object_ini.has_key("object", "Filename"):
						unknown = True
						new_filename = editor_name
					else:
						new_filename = object_ini.get("object", "Filename").replace("\"", "")
						
					if new_filename is None or os.path.splitext(new_filename)[1] != ".ldo":
						unknown = True
						new_filename = editor_name
						
					filename = new_filename
					editor_name = editor_name + ".ini"
					from_ini   = True
					if object_ini.has_key("object", "Invert"):
						invert_str = object_ini.get("object", "Invert")
						invert     = True if invert_str == "1" else False
				
				def get_dummy_out(to_search):
					dummy_out = None
					objects = to_search.all_objects if isinstance(to_search, bpy.types.Collection) else to_search.children
					for instance_child in objects:
						if utils.remove_dot_suffix(instance_child.name) == "DUMMY_OUT":
							dummy_out = instance_child
					return dummy_out
				
				def set_position_from_ini(previous_out, object):
					bpy.context.view_layer.update()
					if len(current_section) > 4:
						print("Extra info:")
						print(current_section)
					if "Position" in current_section:
						pos  = mathutils.Vector(vector3_from_ini(current_section, "Position"))
						up   = mathutils.Vector(vector3_from_ini(current_section, "DirectionUp"))
						at   = mathutils.Vector(vector3_from_ini(current_section, "DirectionAT"))
						side = up.cross(at)
						matrix = ldo.axis_conversion_matrix @ mathutils.Matrix((
							(side[0], up[0], at[0], pos[0]),
							(side[1], up[1], at[1], pos[1]),
							(side[2], up[2], at[2], pos[2]),
							(    0.0,  0.0,    0.0,    1.0)
						)) @ ldo.inverse_axis_conversion_matrix
						object.matrix_local = matrix
						if from_ini:
							dummy_out = get_dummy_out(object)
							if dummy_out is not None:
								return dummy_out.matrix_world
					elif from_ini: # Use dummy_out
						dummy_out = get_dummy_out(object)
						if dummy_out is not None and previous_out is not None:
							object.matrix_world = previous_out
							return get_dummy_out(object).matrix_world
				
				
				if editor_name not in bpy.data.collections: # Add to library
					object_collection = None
					
					def add_unknown():
						nonlocal object_collection
						object_collection = bpy.data.collections.new(editor_name)
						library_collection.children.link(object_collection)
						print("Unknown: " + editor_name)
						
					if unknown: # Not importable, empty instance
						add_unknown()
					else:
						filepath = levels_path + "/../../Gfx/models/Geometry/" + filename.split("/")[1]
						try:
							object_collection = import_ldo.import_ldo_file(filepath, texture_path)
						except:
							ldo.debug_print("Mad Tracks level: Could not import " + filepath)
							object_collection = None
						if object_collection is None:
							add_unknown()
							current_section = {}
							continue
							
						bpy.context.view_layer.update()
						if from_ini:
							ini_collection = bpy.data.collections.new(editor_name)
							ini_collection.children.link(object_collection)
							library_collection.children.link(ini_collection)
							if invert:
								for object in ini_collection.all_objects:
									if object.parent is not None:
										continue
									dummy = get_dummy_out(ini_collection)
									if dummy is None:
										print("Mad Tracks level: '" + editor_name + "' is marked Invert but has no DUMMY_OUT, skipping invert")
										break
									print(object.name)
									dummy_matrix = dummy.matrix_local.copy()
									object.select_set(True)
									object.rotation_euler[2] += math.radians(180) - dummy_matrix.to_euler()[2]
									translation = dummy_matrix.to_translation()
									object.location[0] -= translation[0]
									object.location[1] += translation[1]
									object.location[2] -= translation[2]
									bpy.ops.object.transform_apply()
									object.select_set(False)
									dummy.location = translation
									dummy.location[0] *= -1.0
									dummy.location[2] *= -1.0
									dummy.rotation_euler = dummy_matrix.to_euler()
									dummy.rotation_euler[2] = -dummy.rotation_euler[2]
									bpy.context.view_layer.update()
									
						else:
							library_collection.children.link(object_collection)
						scene.collection.children.unlink(object_collection)
				
				# Instance from library
				instance = bpy.data.objects.new(editor_name + "_instance", None)
				instance.instance_collection = bpy.data.collections[editor_name]
				instance.instance_type = "COLLECTION"
				instance.show_axis = True
				dummy = get_dummy_out(instance.instance_collection)
				if dummy is not None:
					dummy_out = bpy.data.objects.new("DUMMY_OUT", None)
					dummy_out.empty_display_size = 1
					dummy_out.empty_display_type = "ARROWS"
					dummy_out.parent = instance
					matrix = dummy.matrix_world @ ldo.inverse_axis_conversion_matrix
					dummy_out.matrix_local = matrix
					instance_collection.objects.link(dummy_out)
				out = set_position_from_ini(previous_out, instance)
				if out is not None:
					previous_out = out
				instance_collection.objects.link(instance)
			
			current_section = {}
			section_name = line[1:line.rfind("]")]
		else:
			line = "".join(line.split())
			line = line.replace(" ", "")
			split = line.split("=")
			if len(split) < 2:
				continue
			key, value = split
			current_section[key] = value

				
	# Graph file
	graph = INIParser(os.path.splitext(path)[0] + ".gra")
	
	nodes = {}
	edges = []
	for (section, values) in graph.data.items():
		for (i, value) in enumerate(values):
			if section == "Node":
				id = int(value["ID"])
				pos = vector3_from_ini(value, "Position")
				nodes[id] = [ldo.axis_conversion_matrix @ mathutils.Vector(pos)]
			elif section == "Edge":
				node_in = int(value["In"])
				node_out = int(value["Out"])
				edges.append((node_in, node_out))
	
	if len(edges) > 0:
		me = bpy.data.meshes.new(level_name + "_Path")
		path_obj = bpy.data.objects.new(level_name + "_Path", me)
		bm = bmesh.new()
		bm.from_mesh(me)
		
		for edge in edges:
			verts = [None, None]
			for i in range(2):
				node = nodes[edge[i]]
				vert = bm.verts.new(node[0]) if len(node) < 2 else node[1] # Reuse existing bmvert
				node.append(vert)
				verts[i] = vert
			bm.edges.new(verts)
		
		level_collection.objects.link(path_obj)
		bm.to_mesh(me)
		bm.free()
		#path = bpy.data.curves.new(level_name + "_Path", "CURVE")
		#path.dimensions = "3D"
		#for edge in edges:
		#   spline = path.splines.new(type="POLY")
		#   spline.points.add(1)
		#   spline.points[0].co = (node_in.x, node_in.y, node_in.z, 1.0)
		#   spline.points[1].co = (node_out.x, node_out.y, node_out.z, 1.0)
		#path_obj = bpy.data.objects.new(level_name + "_Path", path)
		#level_collection.objects.link(path_obj)
	return level_collection

def import_level_file(path, texture_path):
	time_start = time.perf_counter()
	if not texture_path:
		texture_path = os.path.dirname(path) + "/../../Graph/maps/High/"
	if not os.path.isdir(texture_path):
		raise Exception("No texture path was given and default not applicable")
	level_collection = import_level(path, texture_path)
	ldo.debug_print("Mad Tracks Level: Importing and adding to scene done after {0:.4f}s".format(time.perf_counter() - time_start))
	return level_collection
