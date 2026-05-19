import sys
import os

# Make addon importable
script_dir = os.path.dirname(os.path.abspath(__file__))
addon_dir = os.path.dirname(script_dir)
parent_dir = os.path.dirname(addon_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import bpy

# Import and register addon
import DATools
DATools.register()

# Clean scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Create test meshes
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
cube = bpy.context.object
bpy.ops.mesh.primitive_uv_sphere_add(location=(2, 0, 0))
sphere = bpy.context.object

# Ensure both selected and active set
cube.select_set(True)
sphere.select_set(True)
bpy.context.view_layer.objects.active = cube

print('Objects in scene before operators:', [o.name for o in bpy.context.scene.objects])

# Run Scale It (uses default axis)
try:
    res = bpy.ops.dat.scale_it()
    print('scale_it result:', res)
except Exception as e:
    print('scale_it error:', e)

# Run Mirror It (uses default axis)
try:
    res = bpy.ops.dat.mirror_it()
    print('mirror_it result:', res)
except Exception as e:
    print('mirror_it error:', e)

# Run Shrink It (uses default percentage)
try:
    res = bpy.ops.dat.shrink_it()
    print('shrink_it result:', res)
except Exception as e:
    print('shrink_it error:', e)

# Run Rez It (should run but do nothing meaningful without materials)
try:
    res = bpy.ops.dat.rez_it()
    print('rez_it result:', res)
except Exception as e:
    print('rez_it error:', e)

print('Objects in scene after operators:', [o.name for o in bpy.context.scene.objects])

# Unregister addon
DATools.unregister()

print('Smoke test completed')
