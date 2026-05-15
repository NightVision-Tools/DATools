"""Init DATools"""

bl_info = {
    "name": "DATools",
    "author": "DATools",
    "version": (1, 0, 0),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > DAT",
    "description": "A set of tools for the DungeonAlchemist™ import pipeline",
    "category": "3D View",
}

import bpy

from .ui.main_panel import DAT_3DV_MainPanel, register_scene_properties

# register classes
classes = (
    DAT_3DV_MainPanel,
)


def register():
    register_scene_properties()

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    if hasattr(bpy.types.Scene, "ui_menu"):
        delattr(bpy.types.Scene, "ui_menu")

