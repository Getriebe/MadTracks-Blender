# SPDX-License-Identifier: GPL-3.0-or-later
import struct, io, mathutils

def __read(file, type, count=1, endian="<"):
    format = "{}{}{}".format(endian, count, type)
    data = struct.unpack(format, file.read(struct.calcsize(format)))
    return data if count > 1 else data[0]

def read_u8(file, num=1, endian="<"):
    return __read(file, "B", num, endian)
    
def read_u16(file, num=1, endian="<"):
    return __read(file, "H", num, endian)
    
def read_u32(file, num=1, endian="<"):
    return __read(file, "I", num, endian)
    
def read_u64(file, num=1, endian="<"):
    return __read(file, "Q", num, endian)
    
def read_i8(file, num=1, endian="<"):
    return __read(file, "b", num, endian)
    
def read_i16(file, num=1, endian="<"):
    return __read(file, "h", num, endian)
    
def read_i32(file, num=1, endian="<"):
    return __read(file, "i", num, endian)
    
def read_i64(file, num=1, endian="<"):
    return __read(file, "q", num, endian)
    
def read_float(file, num=1, endian="<"):
    return __read(file, "f", num, endian)
	
def read_float16(file, num=1, endian="<"):
	return __read(file, "e", num, endian)

def read_double(file, num=1, endian="<"):
    return __read(file, "d", num, endian)

def read_string(file, len = -1):
    if (len == -1):
        read_len = file.read(1)[0]
        string  = struct.unpack("<" + str(read_len) + "s", file.read(read_len))[0]
        file.read(1) # Skip null-terminator
        return string.decode("ascii")
    else:
        return struct.unpack("<" + str(len) + "s", file.read(len))[0].decode("ascii")
    
def read_color(file):
    r, g, b, a = read_u8(file, 4)
    return mathutils.Color((r/255.0, g/255.0, b/255.0))

def read_vector3(file):
    return mathutils.Vector(read_float(file, 3))

def read_vector4(file):
    return mathutils.Vector(read_float(file, 4))

def read_matrix_4x4(file):
    _1 = read_float(file, 3)
    _2 = read_float(file, 3)
    _3 = read_float(file, 3)
    _4 = read_float(file, 3)
    matrix = mathutils.Matrix((
        ( _4[0],  _3[0],  _2[0],  _1[0]),
        ( _4[1],  _3[1],  _2[1],  _1[1]),
        ( _4[2],  _3[2],  _2[2],  _1[2]),
        (   0.0,	0.0,	0.0,	1.0)
    ))
    #ldo.debug_print(_1)
    #ldo.debug_print(_2)
    #ldo.debug_print(_3)
    #ldo.debug_print(_4)
    return matrix

def __write(file, vals, type, endian="<"):
    data = vals if hasattr(vals, "__len__") else (vals,)
    file.write( struct.pack("{}{}{}".format(endian, len(data), type), *data) )
    
def write_u8(file, vals, endian="<"):
    __write(file, vals, "B", endian)
    
def write_u16(file, vals, endian="<"):
    __write(file, vals, "H", endian)
    
def write_u32(file, vals, endian="<"):
    __write(file, vals, "I", endian)
    
def write_u64(file, vals, endian="<"):
    __write(file, vals, "Q", endian)
    
def write_i8(file, vals, endian="<"):
    __write(file, vals, "b", endian)
    
def write_i16(file, vals, endian="<"):
    __write(file, vals, "h", endian)
    
def write_i32(file, vals, endian="<"):
    __write(file, vals, "i", endian)
    
def write_i64(file, vals, endian="<"):
    __write(file, vals, "q", endian)
    
def write_float(file, vals, endian="<"):
    __write(file, vals, "f", endian)
    
def write_double(file, vals, endian="<"):
    __write(file, vals, "d", endian)
    
def write_string(file, string, extra=True):
    if extra:
        write_u8(file, len(string))
    file.write(bytes(string, "ascii"))
    if extra:
        write_u8(file, 0)

def write_color(file, color):
    write_u8(file, (int(color.r*255), int(color.g*255), int(color.b*255), 255))

def write_vector3(file, vector3):
    write_float(file, (vector3.x, vector3.y, vector3.z))

def write_vector4(file, vector4):
    write_float(file, (vector4.x, vector4.y, vector4.z, vector4.w))
    
def write_matrix_4x4(file, matrix):
    _4 = mathutils.Vector(( matrix[0][0],  matrix[1][0],  matrix[2][0]))
    _3 = mathutils.Vector((-matrix[0][1], -matrix[1][1], -matrix[2][1]))
    _2 = mathutils.Vector(( matrix[0][2],  matrix[1][2],  matrix[2][2]))
    _1 = mathutils.Vector(( matrix[0][3],  matrix[1][3],  matrix[2][3]))
    write_vector3(file, _1)
    write_vector3(file, _3)
    write_vector3(file, _2)
    write_vector3(file, _4)

def remove_dot_suffix(string):
    if "." in string:
        suffix_pos = string.rfind(".")
        if string[suffix_pos+1:].isnumeric():
            return string[:suffix_pos]
        else:
            return string
    else:
        return string

def find_child_collection(parent, suffix):
    """Find e.g. 'Level_instances' under 'Level', ignoring Blender's '.001' suffixes on either name."""
    wanted = remove_dot_suffix(parent.name) + suffix
    for child in parent.children:
        if remove_dot_suffix(child.name) == wanted:
            return child
    return None
