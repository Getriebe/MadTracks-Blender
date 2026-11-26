# SPDX-License-Identifier: GPL-3.0-or-later
if "bpy" in locals():  # To re-import in Blender, dependencies first submodules
	import importlib
	for _mod in (utils, ldo, ldl, import_ldo, export_ldo, import_level, export_level, import_ldl, gui):
		importlib.reload(_mod)
else:
	from . import utils, ldo, ldl, import_ldo, export_ldo, import_level, export_level, import_ldl, gui

import bpy
from bpy.utils import register_class, unregister_class


bl_info = {
	"name": "Mad Tracks Import/Export",
	"author": "Getriebe",
	"version": (1, 0, 0),
	"blender": (3, 4, 0), # oldest version tested
	"location": "File > Import-Export",
	"category": "Import-Export",
	"description": "Import and export Mad Tracks files"
}

classes = [
    gui.OperatorImportLDO,
    gui.OperatorExportLDO,
    gui.OperatorImportLevel,
    gui.OperatorExportLevel
]

def get_import_export_list():
	return (bpy.types.TOPBAR_MT_file_import, bpy.types.TOPBAR_MT_file_export)

def register():
	for cls in classes:
		register_class(cls)
	
	import_list, export_list = get_import_export_list()
	import_list.append(gui.menu_func_import_ldo)
	import_list.append(gui.menu_func_import_level)
	export_list.append(gui.menu_func_export_ldo)
	export_list.append(gui.menu_func_export_level)

def unregister():
	import_list, export_list = get_import_export_list()
	import_list.remove(gui.menu_func_import_ldo)
	import_list.remove(gui.menu_func_import_level)
	export_list.remove(gui.menu_func_export_ldo)
	export_list.remove(gui.menu_func_export_level)

	for cls in reversed(classes):
		unregister_class(cls)

if __name__ == "__main__":
	register()
