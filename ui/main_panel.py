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
        layout.operator_context = 'EXEC_DEFAULT'
        scene = context.scene
        row = layout.row()
        row.prop(scene, "ui_menu", text=dictionary.translate("ui_menu_label", context))

        menu = set(scene.ui_menu)
        if not menu:
            layout.label(text=dictionary.translate("menu_need_select", context), icon="ERROR")
            return

        layout.label(text=dictionary.translate("selected_text", context).format(", ".join(sorted(menu))))

        if "Tools" in menu:
            layout.operator("dat.floor_it", text=dictionary.translate("floor_it_label", context))            
            layout.prop(scene, "dat_scale", expand=True)
            layout.operator("dat.scale_it", text=dictionary.translate("scale_it_label", context))
            layout.prop(scene, "dat_shrinkpercentage")
            layout.operator("dat.shrink_it", text=dictionary.translate("shrink_it_label", context))
            layout.prop(scene, "dat_mirror", expand=True)
            layout.operator("dat.mirror_it", text=dictionary.translate("mirror_it_label", context))
            layout.prop(scene, "dat_textureresolution")
            layout.operator("dat.rez_it", text=dictionary.translate("rez_it_label", context))



def register_scene_properties():
    bpy.types.Scene.ui_menu = bpy.props.EnumProperty(
        name="UI Menu",
        items=ui_menu_options,
        options={"ENUM_FLAG"},
    )
    bpy.types.Scene.dat_textureresolution = bpy.props.IntProperty(
        name=dictionary.translate("dat_textureresolution_label"),
        description=dictionary.translate("dat_textureresolution_description"),
        default=1024,
        min=1,
    )
    bpy.types.Scene.dat_scale = bpy.props.EnumProperty(
        name=dictionary.translate("scale_it_axis_label"),
        description=dictionary.translate("scale_it_axis_description"),
        items=[
            ("X", "X", "Scale to the X", 0, 0),
            ("Y", "Y", "Scale to the Y", 0, 1),
            ("Z", "Z", "Scale to the Z", 0, 2),
        ],
        default="X",
    )
    bpy.types.Scene.dat_mirror = bpy.props.EnumProperty(
        name=dictionary.translate("mirror_it_axis_label"),
        description=dictionary.translate("mirror_it_axis_description"),
        items=[
            ("X", "X", "Mirror over the X axis", 0, 0),
            ("Y", "Y", "Mirror over the Y axis", 0, 1),
            ("Z", "Z", "Mirror over the Z axis", 0, 2),
        ],
        default="X",
    )
    bpy.types.Scene.dat_shrinkpercentage = bpy.props.IntProperty(
        name=dictionary.translate("shrink_it_percentage_label"),
        description=dictionary.translate("shrink_it_percentage_description"),
        default=50,
        min=1,
        max=100,
    )
    bpy.types.Scene.dat_shrink_mode = bpy.props.EnumProperty(
        name=dictionary.translate("shrink_it_mode_label"),
        description=dictionary.translate("shrink_it_mode_description"),
        items=[
            ("KEEP", dictionary.translate("shrink_it_mode_keep_label"), "Keep duplicates and leave originals"),
            ("REPLACE", dictionary.translate("shrink_it_mode_replace_label"), "Replace originals with decimated duplicates"),
        ],
        default="KEEP",
    )
    bpy.types.Scene.dat_shrink_apply_modifiers = bpy.props.BoolProperty(
        name=dictionary.translate("shrink_it_apply_modifiers_label"),
        description=dictionary.translate("shrink_it_apply_modifiers_description"),
        default=False,
    )
    bpy.types.Scene.dat_shrink_select_result = bpy.props.BoolProperty(
        name=dictionary.translate("shrink_it_select_result_label"),
        description=dictionary.translate("shrink_it_select_result_description"),
        default=True,
    )
    bpy.types.Scene.dat_scalebuffer = bpy.props.FloatProperty(
        name=dictionary.translate("dat_scalebuffer_label"),
        default=0.0,
        precision=6,
    )
    bpy.types.Scene.dat_activeobjectbuffer = bpy.props.PointerProperty(
        name=dictionary.translate("dat_activeobjectbuffer_label"),
        type=bpy.types.Object,
    )