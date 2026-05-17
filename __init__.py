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

import bpy

from .dictionary import (
    get_language_items,
    get_language_display,
    register_translations,
    translate,
    unregister_translations,
)
from .ui.main_panel import DAT_3DV_MainPanel, register_scene_properties
from .operators.select_language import DAT_OP_SelectLanguage
from .operators.to_floor import DAT_OP_ToFloor


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
    DAT_OP_ToFloor,
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

    if hasattr(bpy.types.Scene, "ui_menu"):
        delattr(bpy.types.Scene, "ui_menu")

