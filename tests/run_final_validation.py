import sys
import os

# Make addon importable
script_dir = os.path.dirname(os.path.abspath(__file__))
addon_dir = os.path.dirname(script_dir)
parent_dir = os.path.dirname(addon_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import bpy

import DATools
DATools.register()

# Clean scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Create a mesh and a non-mesh
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
mesh = bpy.context.object
mesh.name = 'TestCube'

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(2, 0, 0))
empty = bpy.context.object
empty.name = 'TestEmpty'

# Select both
mesh.select_set(True)
empty.select_set(True)
bpy.context.view_layer.objects.active = mesh

print('Selected objects before:', [(o.name, o.type) for o in bpy.context.selected_objects])

# Test shrink with percentage 1
bpy.context.scene.dat_shrinkpercentage = 1
print('\nRunning shrink_it with percentage=1')
res = bpy.ops.dat.shrink_it()
print('Result:', res)
print('Objects after 1% shrink:', [o.name for o in bpy.context.scene.objects])

# Count shrink duplicates
shrinks = [o for o in bpy.context.scene.objects if o.name.endswith('_Shrink')]
print('Shrink duplicates count (1%):', len(shrinks))

# Test shrink with percentage 100 (Keep mode)
bpy.context.scene.dat_shrinkpercentage = 100
# Reselect original objects (they should still be present)
for o in bpy.context.scene.objects:
    o.select_set(False)
mesh.select_set(True)
empty.select_set(True)
bpy.context.view_layer.objects.active = mesh

print('\nRunning shrink_it with percentage=100 (KEEP mode)')
res = bpy.ops.dat.shrink_it()
print('Result:', res)
print('Objects after 100% shrink (KEEP):', [o.name for o in bpy.context.scene.objects])

shrinks = [o for o in bpy.context.scene.objects if o.name.endswith('_Shrink')]
print('Shrink duplicates count (total):', len(shrinks))

# Verify that non-mesh wasn't duplicated
non_mesh_dups = [o for o in shrinks if o.name.startswith('TestEmpty')]
print('Non-mesh duplicated?', len(non_mesh_dups) > 0)

# Verify selection restored: original selection should be TestCube and TestEmpty
print('Selected objects after (KEEP):', [(o.name, o.type) for o in bpy.context.selected_objects])

# Now test REPLACE mode
for o in bpy.context.scene.objects:
    o.select_set(False)
mesh.select_set(True)
empty.select_set(True)
bpy.context.view_layer.objects.active = mesh

bpy.context.scene.dat_shrinkpercentage = 50
bpy.context.scene.dat_shrink_mode = 'REPLACE'
print('\nRunning shrink_it in REPLACE mode (50%)')
res = bpy.ops.dat.shrink_it()
print('Result:', res)
print('Objects after REPLACE:', [o.name for o in bpy.context.scene.objects])

shrinks = [o for o in bpy.context.scene.objects if o.name.endswith('_Shrink') or o.get('dat_shrink')]
print('Shrink duplicates count after REPLACE:', len(shrinks))

print('Selected objects after (REPLACE):', [(o.name, o.type) for o in bpy.context.selected_objects])

DATools.unregister()
print('\nFinal validation completed')
