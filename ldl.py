# SPDX-License-Identifier: GPL-3.0-or-later
import mathutils

from typing import List, Tuple
from dataclasses import dataclass

@dataclass
class MeshLightmap:
    data        : List[Tuple[float]] # 32 bit floats in old version, 16 bit in new version

@dataclass
class ObjectLightmap:
    name            : str
    mesh_lightmaps  : List[MeshLightmap]
    

@dataclass
class Lightmap:
    unk1        : int
    lightmaps   : List[ObjectLightmap]
    
    