# SPDX-License-Identifier: GPL-3.0-or-later
"""Packages the add-on. python build.py -> dist/io_scene_madtracks-<version>.zip"""
import ast, pathlib, sys, zipfile

ROOT = pathlib.Path(__file__).resolve().parent
NAME = ROOT.name # io_scene_madtracks
DIST = ROOT / "dist"
INCLUDE = ["*.py", "LICENSE", "README.md", "blender_manifest.toml"]
EXCLUDE = {"build.py"}

def read_version():
	tree = ast.parse((ROOT / "__init__.py").read_text(encoding="utf-8"))
	for node in tree.body:
		if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "bl_info" for t in node.targets):
			return ".".join(map(str, ast.literal_eval(node.value)["version"]))
	sys.exit("bl_info not found in __init__.py")

def main():
	files = sorted({p for pat in INCLUDE for p in ROOT.glob(pat) if p.is_file() and p.name not in EXCLUDE})
	for f in files:
		if f.suffix == ".py":
			try:
				compile(f.read_text(encoding="utf-8"), str(f), "exec")
			except SyntaxError as e:
				sys.exit(f"Syntax error: {e.filename}:{e.lineno}: {e.msg}")
	DIST.mkdir(exist_ok=True)
	out = DIST / f"{NAME}-{read_version()}.zip"
	with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
		for f in files:
			zf.write(f, f"{NAME}/{f.name}")
	print(f"Wrote {out} ({len(files)} files)")

if __name__ == "__main__":
	main()