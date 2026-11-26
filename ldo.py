# SPDX-License-Identifier: GPL-3.0-or-later
import mathutils

from dataclasses import dataclass
from typing import List

from bpy_extras.io_utils import axis_conversion

axis_conversion_matrix = axis_conversion(from_forward="Z", from_up="Y", to_forward="-Y", to_up="Z").to_4x4()
inverse_axis_conversion_matrix = axis_conversion_matrix.inverted()

DEBUG = False # Set to True for verbose console output while developing

def debug_print(*args):
    if DEBUG:
        print(args)

@dataclass
class Material:
	FLAG_COLORED1   	= 0b0000_0001
	FLAG_COLORED2   	= 0b0000_0010
	FLAG_REFLECTIVE 	= 0b0000_0100
	FLAG_TEXTURED   	= 0b0000_1000
	FLAG_5  			= 0b0001_0000
	FLAG_TRANSPARENT	= 0b0010_0000
	FLAG_EMISSIVE   	= 0b0100_0000
	FLAG_REFLECTMAP 	= 0b1000_0000
	
	name				: str
	flags   			: int
	color1  			: mathutils.Color # FLAG_COLOR1
	color2  			: mathutils.Color # FLAG_COLOR2
	reflectivity		: float 		  # FLAG_REFLECTIVE
	texture 			: str   		  # FLAG_TEXTURED
	emissive_strength   : float 		  # FLAG_EMISSIVE
	specularity 		: float 		  # FLAG_REFLECTMAP
	specmap 			: str   		  # FLAG_REFLECTMAP
	
@dataclass
class VertexGroup:
	vertex_data 	: List[float]
	
	@staticmethod
	def __calculate_offset(name, format_specifier_list):
		offset_dict = {}
		offset = 0
		for i, format in enumerate(Mesh.FormatList):
			if i not in format_specifier_list:
				continue
			
			offset_dict[format[2]] = (offset, format[1])
			offset += format[1]
		if name not in offset_dict:
			raise Exception("Offset for requested data invalid")
		return offset_dict[name]
	
	# Set certain value according to the format
	def get_value(self, name, format_specifier_list):
		offset, count = VertexGroup.__calculate_offset(name, format_specifier_list)
		if name != "Color":
			return mathutils.Vector( (self.vertex_data[offset+i] for i in range(count)) )
		else: # Color
			return mathutils.Color([self.vertex_data[offset+i]/255.0 for i in range(3)])
	
	# Get certain value according to the format
	def set_value(self, name, format_specifier_list, value):
		offset, count = VertexGroup.__calculate_offset(name, format_specifier_list)
		
		missing = offset + count - len(self.vertex_data)
		self.vertex_data.extend([0.0] * max(missing, 0))

		if name != "Color":
			for i in range(count):
				self.vertex_data[offset+i] = value[i]
		else: # Color
			for i in range(3):
				self.vertex_data[offset+i] = int(value[i]*255)
			self.vertex_data[offset+3] = 255
	
@dataclass
class IndexGroup:
	material_index  : int
	indices 		: List[List[int]]
	
@dataclass
class Mesh:
	flags   			: int
	bounds  			: mathutils.Vector
	mesh_ID 			: int
	vertex_format   	: List[int]
	vertex_groups   	: List[VertexGroup]
	index_groups		: List[IndexGroup]
	
	FormatList = [
	#    Size  Count Name
		(4,    3,   "Vertex"),
		(4,    3,   "Normal"),
		(1,    4,   "Color"),
		(4,    1,   "Textcoord0u"),
		(4,    1,   "Textcoord1u"),
		(4,    1,   "Textcoord2u"),
		(4,    1,   "Textcoord3u"),
		(4,    2,   "Textcoord0uv"),
		(4,    2,   "Textcoord1uv"),
		(4,    2,   "Textcoord2uv"),
		(4,    2,   "Textcoord3uv"),
		(4,    3,   "Textcoord0uvw"), # uvw used for shadow offsets
		(4,    3,   "Textcoord1uvw"),
		(4,    3,   "Textcoord2uvw"),
		(4,    3,   "Textcoord3uvw"),
		(4,    3,   "Tangent"),
		(4,    3,   "Binormal")
	]
	
	@staticmethod
	def calculate_num_faces(indexGroups):
		num_faces = 0
		for indexGroup in indexGroups:
			num_faces += len(indexGroup.indices)
		return num_faces
	
	# Calculate the size of the vertex groups using the format specified
	@staticmethod
	def calculate_vertex_group_size(format_specifier_list):
		vertex_group_size = 0
		for format_specifier in format_specifier_list:
			if format_specifier >= len(Mesh.FormatList):
				raise Exception("Unknown format specifier")
			
			format = Mesh.FormatList[format_specifier]
			vertex_group_size += format[0] * format[1]
		return vertex_group_size
	
	@staticmethod
	def get_format(name):
		for format in Mesh.FormatList:
			if format[2] == name:
				return format
		raise Exception("Unknown format name")
	
	def has_vertex_data(self, name):
		format_index = Mesh.FormatList.index(Mesh.get_format(name))
		return True if format_index in self.vertex_format else False
	
	@staticmethod
	def add_vertex_format(vertex_format, name):
		vertex_format.append(Mesh.FormatList.index(Mesh.get_format(name)))
		
	
@dataclass
class Node:
	MASK_NAMELENGTH 	= 0b0011_1111
	MASK_TRANSLATETYPE  = 0b1100_0000
	
	flags   	: int
	translation : mathutils.Matrix
	child_ID	: int
	parent_ID   : int
	node_name   : str
	
	children	: List
	
@dataclass
class Atomic:
	end_of_file 	: int
	is_animated     : int
	bounds  		: mathutils.Vector
	materials   	: List[Material]
	meshes  		: List[Mesh]
	hierarchy   	: Node
	
@dataclass
class Object:
	object_name 	: str
	
	object_version  : int
	atomic_version  : int
	mesh_version	: int
	material_version: int
	
	atomics 		: List[Atomic]
	
	def is_old_version(self): # For original Mad Tracks release
		return (self.atomic_version == 2 and self.mesh_version == 1 and self.material_version == 2)
	