"""Init DATools"""

bl_info = {
    "name": "DATools",
    "author": "Tinazzi Patrick",
    "version": (1, 0, 0),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > DAT",
    "description": "A set of tools for the DungeonAlchemist™ import pipeline",
    "category": "3D View",
}

import os
import sys
import types

import bpy

if __package__ is None:
    addon_name = os.path.basename(os.path.dirname(__file__))
    addon_path = os.path.dirname(__file__)
    parent_dir = os.path.dirname(addon_path)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    if addon_name not in sys.modules:
        package_module = types.ModuleType(addon_name)
        package_module.__path__ = [addon_path]
        sys.modules[addon_name] = package_module
    __package__ = addon_name

from .dictionary import (
    get_language_items,
    get_language_display,
    register_translations,
    translate,
    unregister_translations,
)
from .ui.main_panel import DAT_3DV_MainPanel, register_scene_properties
from .ui.select_language import DAT_OP_SelectLanguage
from .operators.floor_it import DAT_OP_FloorIt
from .operators.rez_it import DAT_OP_RezIt
from .operators.scale_it import DAT_OP_ScaleIt
from .operators.mirror_it import DAT_OP_Mirrorit
from .operators.shrink_it import DAT_OP_ShrinkIt


class DAToolsPreferences(bpy.types.AddonPreferences):
    bl_idname = "DATools"
    bl_label = "DATools Preferences"

    language = bpy.props.StringProperty(
        name="Language",
        default="ENGLISH",
    )  # type: ignore[assignment]

    def draw(self, context):
        layout = self.layout
        layout.label(text=translate("addon_language_header", context))
        layout.label(
            text=str(translate("selected_language_text", context)).format(
                get_language_display(self.language)
            )
        )

        row = layout.row()
        row.operator("dat.select_language", text=translate("language_option_english", context)).language = "ENGLISH"
        row.operator("dat.select_language", text=translate("language_option_italian", context)).language = "ITALIAN"

        row = layout.row()
        row.operator("dat.select_language", text=translate("language_option_german", context)).language = "GERMAN"
        row.operator("dat.select_language", text=translate("language_option_french", context)).language = "FRENCH"


# register classes
classes = (
    DAToolsPreferences,
    DAT_OP_SelectLanguage,
    DAT_OP_FloorIt,
    DAT_OP_RezIt,
    DAT_OP_ScaleIt,
    DAT_OP_Mirrorit,
    DAT_OP_ShrinkIt,
    DAT_3DV_MainPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    register_translations()
    register_scene_properties()


def unregister():
    unregister_translations()

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    for prop in (
        "ui_menu",
        "dat_textureresolution",
        "dat_scale",
        "dat_mirror",
        "dat_shrinkpercentage",
        "dat_shrink_mode",
        "dat_shrink_apply_modifiers",
        "dat_shrink_select_result",
        "dat_scalebuffer",
        "dat_activeobjectbuffer",
    ):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)

