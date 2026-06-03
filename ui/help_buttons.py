import bpy
from bpy.props import StringProperty
from bpy.types import Operator


DOCS_BASE_URL = "https://1nightvision1.github.io/DATools_Doc/"
DOC_PATHS = {
    "about": "About/",
    "custom_scripts": "Custom_Scripts/",
    "floor_it": "Operators/Floor_It/",
    "installation": "Installation/",
    "interface": "Interface/",
    "io_tools": "Operators/IO_Tools/",
    "light_tools": "Operators/Light_Tools/",
    "map_it": "Operators/Map_It/",
    "mirror_it": "Operators/Mirror_It/",
    "operators": "Operators/",
    "preferences": "Preferences/",
    "rez_it": "Operators/Rez_It/",
    "scale_it": "Operators/Scale_It/",
    "shrink_it": "Operators/Shrink_It/",
}


class DAT_OT_OpenDocs(Operator):
    bl_idname = "dat.open_docs"
    bl_label = "Open DATools Documentation"
    bl_description = "Open the DATools documentation"

    path: StringProperty(default="")

    def execute(self, context):
        if not bpy.app.online_access:
            self.report({"WARNING"}, "Online access is disabled in Blender preferences")
            return {"CANCELLED"}

        bpy.ops.wm.url_open(url=DOCS_BASE_URL + self.path)
        return {"FINISHED"}


def show_help_buttons(context):
    scene = getattr(context, "scene", None)
    state = getattr(scene, "dat_panel_state", None)
    return state is not None and getattr(state, "show_help_buttons", True)


def draw_help_button(layout, doc_path):
    op = layout.operator("dat.open_docs", text="", icon="QUESTION", emboss=False)
    op.path = doc_path
    return op


def draw_doc_header(layout, text="", icon="NONE", *, context=None, doc_path=None, factor=0.85):
    if context is not None and doc_path and show_help_buttons(context):
        split = layout.split(factor=factor, align=True)
        title = split.row(align=True)
        title.label(text=text, icon=icon)

        help_row = split.row(align=True)
        help_row.alignment = "RIGHT"
        draw_help_button(help_row, doc_path)
        return title

    row = layout.row(align=True)
    row.label(text=text, icon=icon)
    return row
