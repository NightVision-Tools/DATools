import bpy


def ui_menu_options(self, context):
    enum_items = [
        ("Blender", "Blender", "Blender", "BLENDER", 1),
        ("Tools", "Tools", "Tools", "TOOL_SETTINGS", 2),
        ("I/O", "I/O", "I/O", "NETWORK_DRIVE", 4),
        ("Settings", "Settings", "Settings", "SETTINGS", 8),
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
        row.prop(scene, "ui_menu", text="")

        menu = set(scene.ui_menu)
        if not menu:
            layout.label(text="SELECT A MENU!", icon="ERROR")
            return
        
        layout.label(text=f"Selected: {', '.join(sorted(menu))}")
        
        if "Tools" in menu:
            layout.operator("dat.to_floor", text="To Floor")


def register_scene_properties():
    bpy.types.Scene.ui_menu = bpy.props.EnumProperty(
        name="UI Menu",
        items=ui_menu_options,
        options={"ENUM_FLAG"},
    )