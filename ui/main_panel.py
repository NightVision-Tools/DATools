import bpy

from .. import dictionary


def ui_menu_options(self, context):
    enum_items = [
        (
            "Blender",
            dictionary.translate("menu_blender", context),
            dictionary.translate("menu_blender", context),
            "BLENDER",
            1,
        ),
        (
            "Tools",
            dictionary.translate("menu_tools", context),
            dictionary.translate("menu_tools", context),
            "TOOL_SETTINGS",
            2,
        ),
        (
            "I/O",
            dictionary.translate("menu_io", context),
            dictionary.translate("menu_io", context),
            "NETWORK_DRIVE",
            4,
        ),
        (
            "Settings",
            dictionary.translate("menu_settings", context),
            dictionary.translate("menu_settings", context),
            "SETTINGS",
            8,
        ),
    ]
    return enum_items


class DAT_3DV_MainPanel(bpy.types.Panel):
    bl_label = "DATools"
    bl_idname = "DAT_3DV_MainPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DAT"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        row = layout.row()
        row.prop(scene, "ui_menu", text=dictionary.translate("ui_menu_label", context))

        menu = set(scene.ui_menu)
        if not menu:
            layout.label(text=dictionary.translate("menu_need_select", context), icon="ERROR")
            return

        layout.label(text=dictionary.translate("selected_text", context).format(", ".join(sorted(menu))))

        if "Tools" in menu:
            layout.operator("dat.to_floor", text=dictionary.translate("to_floor_label", context))


def register_scene_properties():
    bpy.types.Scene.ui_menu = bpy.props.EnumProperty(
        name="UI Menu",
        items=ui_menu_options,
        options={"ENUM_FLAG"},
    )