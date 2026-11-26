# SPDX-License-Identifier: GPL-3.0-or-later
def bsdf_input(bsdf, name):
	renamed = {"Specular": "Specular IOR Level", "Emission": "Emission Color"}  # Blender 4.0
	return bsdf.inputs[name] if name in bsdf.inputs else bsdf.inputs[renamed[name]]

def set_auto_smooth(mesh, value=True):
	if hasattr(mesh, "use_auto_smooth"):      # removed in 4.1
		mesh.use_auto_smooth = value

def calc_split_normals(mesh):
	if hasattr(mesh, "calc_normals_split"):   # removed in 4.1 (always available now)
		mesh.calc_normals_split()