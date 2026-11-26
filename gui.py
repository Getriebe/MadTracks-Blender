# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import os

from bpy.props import(
	BoolProperty,
	StringProperty,
	CollectionProperty,
)

from bpy_extras.io_utils import(
	ImportHelper,
	ExportHelper,
)

from . import import_ldo, export_ldo, import_level, export_level, import_ldl

def selected_files(operator):
	"""Paths picked in the file browser; falls back to the typed filename if nothing was multi-selected."""
	folder = os.path.dirname(operator.filepath)
	names = [f.name for f in operator.files if f.name] or [os.path.basename(operator.filepath)]
	return [os.path.join(folder, name) for name in names]

class OperatorImportLDO(bpy.types.Operator, ImportHelper):
	bl_idname   	= "import_scene.ldo"
	bl_description  = "Import Mad Tracks .ldo objects"
	bl_label		= "Mad Tracks object (.ldo)"
	bl_options  	= {'REGISTER', 'UNDO'}

	filename_ext	= ".ldo"
	filter_glob 	: StringProperty(default	 = "*.ldo",
									 options	 = {'HIDDEN'})
	
	files   		: CollectionProperty(type=bpy.types.OperatorFileListElement)
	
	filepath		: StringProperty(name   	 = "File Path",
									 description = "The file to import",
									 maxlen 	 = 512,
									 default	 = "",
									 options	 = {'HIDDEN'})
	
	image_directory : StringProperty(name   	 = "Texture Path",
									 description = "The folder to search for textures",
									 maxlen 	 = 512,
									 default	 = "",
									 subtype	 = 'DIR_PATH',
									 options	 = {'HIDDEN'})
									 
	def draw(self, context):
		layout = self.layout
		layout.prop(self, "image_directory")
	
	def execute(self, context):
		try:
			for file in selected_files(self):
				import_ldo.import_ldo_file(file, self.image_directory)
		except Exception as e:
			self.report({'ERROR'}, f"Mad Tracks: {e}")
			return {'CANCELLED'}
		return {'FINISHED'}

def menu_func_import_ldo(self, context):
	self.layout.operator(OperatorImportLDO.bl_idname, text="Mad Tracks object (.ldo)")
	
class OperatorExportLDO(bpy.types.Operator, ExportHelper):
	bl_idname   	= "export_scene.ldo"
	bl_description  = "Export Mad Tracks .ldo objects"
	bl_label		= "Mad Tracks object (.ldo)"
	bl_options  	= {'REGISTER', 'UNDO'}

	filename_ext	= ".ldo"
	filter_glob 	: StringProperty(default	 = "*.ldo",
									 options	 = {'HIDDEN'})
	
	filepath		: StringProperty(name   	 = "File Path",
									 description = "The file to export",
									 maxlen 	 = 512,
									 default	 = "",
									 options	 = {'HIDDEN'})
	
	old_version 	: BoolProperty  (name   	 = "Old version",
									 description = "Use version preceding Steam release",
									 default	 = False)
	
	def draw(self, context):
		layout = self.layout
		layout.prop(self, "old_version")
	
	def execute(self, context):
		try:
			export_ldo.export_ldo_file(self.filepath, context.collection, self.old_version)
		except Exception as e:
			self.report({'ERROR'}, f"Mad Tracks: {e}")
			return {'CANCELLED'}
		return {'FINISHED'}

def menu_func_export_ldo(self, context):
	self.layout.operator(OperatorExportLDO.bl_idname, text="Mad Tracks object (.ldo)")

class OperatorImportLevel(bpy.types.Operator, ImportHelper):
	bl_idname   	= "import_scene.mad_tracks_level"
	bl_description  = "Import Mad Tracks .ini levels"
	bl_label		= "Mad Tracks level (.ini)"
	bl_options  	= {'REGISTER', 'UNDO'}

	filename_ext	= ".ini"
	filter_glob 	: StringProperty(default	 = "*.ini",
									 options	 = {'HIDDEN'})
	
	files   		: CollectionProperty(type=bpy.types.OperatorFileListElement)
	
	filepath		: StringProperty(name   	 = "File Path",
									 description = "The file to import",
									 maxlen 	 = 512,
									 default	 = "",
									 options	 = {'HIDDEN'})
	
	image_directory : StringProperty(name   	 = "Texture Path",
									 description = "The folder to search for textures",
									 maxlen 	 = 512,
									 default	 = "",
									 subtype	 = 'DIR_PATH',
									 options	 = {'HIDDEN'})
	
	import_lightmap : BoolProperty(name 	   = "Import lightmap",
								   description = "Whether to import and apply lightmap",
								   default     = False,
								   options     = {'HIDDEN'})
	
	def draw(self, context):
		layout = self.layout
		layout.prop(self, "image_directory")
		layout.prop(self, "import_lightmap")
	
	def execute(self, context):
		try:
			for file in selected_files(self):
				level_collection = import_level.import_level_file(file, self.image_directory)
				if self.import_lightmap:
					level_name = os.path.splitext(os.path.basename(file))[0]
					lightmap_path = os.path.join(os.path.dirname(file), "..", "..", "Gfx", "Lightmaps", level_name + ".ldl")
					import_ldl.import_ldl_file(lightmap_path, level_collection)
		except Exception as e:
			self.report({'ERROR'}, f"Mad Tracks: {e}")
			return {'CANCELLED'}
		return {'FINISHED'}

def menu_func_import_level(self, context):
	self.layout.operator(OperatorImportLevel.bl_idname, text="Mad Tracks level (.ini)")
	
class OperatorExportLevel(bpy.types.Operator, ExportHelper):
	bl_idname   	= "export_scene.mad_tracks_level"
	bl_description  = "Export Mad Tracks .ini levels"
	bl_label		= "Mad Tracks level (.ini)"
	bl_options  	= {'REGISTER', 'UNDO'}

	filename_ext	= ".ini"
	filter_glob 	: StringProperty(default	 = "*.ini",
									 options	 = {'HIDDEN'})
	
	filepath		: StringProperty(name   	 = "File Path",
									 description = "The file to export",
									 maxlen 	 = 512,
									 default	 = "",
									 options	 = {'HIDDEN'})
	
	def draw(self, context):
		layout = self.layout
	
	def execute(self, context):
		try:
			export_level.export_level_file(self.filepath, context.collection)
		except Exception as e:
			self.report({'ERROR'}, f"Mad Tracks: {e}")
			return {'CANCELLED'}
		return {'FINISHED'}

def menu_func_export_level(self, context):
	self.layout.operator(OperatorExportLevel.bl_idname, text="Mad Tracks level (.ini)")

