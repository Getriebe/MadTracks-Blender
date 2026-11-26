# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import time

from . import ldo, utils

def export_level(path, root_collection):
    instance_collection = utils.find_child_collection(root_collection, "_instances")
    if instance_collection is None:
        raise Exception("Active collection '" + root_collection.name + "' has no _instances child collection. Select the level collection before exporting")

    with open(path, "w") as level:
        def write_to_ini(string):
            level.write(string + "\n")

        for object in instance_collection.objects:
            if object.instance_collection is None or object.instance_type != "COLLECTION":
                continue
            object_name = utils.remove_dot_suffix(object.name)
            if object_name.endswith("_instance"):
                object_name = object_name.replace("_instance", "")
            is_ini = ".ini" in object_name
            ldo.debug_print(object_name)
            ini_name = object_name if is_ini else "geometry/" + object_name + ".ldo"
            write_to_ini("[" + ini_name + "]")

            def write_pair(key, value):
                write_to_ini(key + " = " + value)
            def write_vector3(key, vector3):
                value = ",".join([format(flt, ".06f") for flt in vector3])
                write_pair(key, value)

            matrix = ldo.inverse_axis_conversion_matrix @ object.matrix_local @ ldo.axis_conversion_matrix
            write_vector3("Position", 	 (matrix[i][3] for i in range(3)))
            write_vector3("DirectionAT", (matrix[i][2] for i in range(3)))
            write_vector3("DirectionUp", (matrix[i][1] for i in range(3)))
            write_pair("Filename", "\""+ ini_name + "\"")

            write_to_ini("")

def export_level_file(path, root_collection):
    time_start = time.perf_counter()
    export_level(path, root_collection)
    ldo.debug_print("Mad Tracks Level: Converting from scene and writing to file done after {0:.4f}s".format(time.perf_counter() - time_start))
