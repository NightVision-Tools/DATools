import bpy
from bpy.props import StringProperty
from bpy.types import Operator


DOCS_BASE_URL = "https://1nightvision1.github.io/DATools_Doc/"
ISSUES_URL = "https://github.com/NightVision-Tools/DATools/issues"
DOC_PATHS = {
    "about": "About/",
    "asset_panel": "Interface/#asset-panel",
    "asset_settings": "Operators/Asset_Tools/#settings",
    "asset_tools": "Operators/Asset_Tools/#asset-gallery",
    "custom_scripts": "Custom_Scripts/#user-workflow",
    "custom_scripts_manager": "Preferences/#custom-scripts",
    "floor_it": "Operators/Floor_It/#floor-it",
    "gltf_animations": "Operators/IO_Tools/#animations",
    "gltf_collision_helpers": "Operators/IO_Tools/#collision-helpers",
    "gltf_export": "Operators/IO_Tools/#export",
    "gltf_export_options": "Operators/IO_Tools/#export-options",
    "gltf_export_profiles": "Operators/IO_Tools/#export-profiles",
    "gltf_geometry": "Operators/IO_Tools/#geometry",
    "gltf_import": "Operators/IO_Tools/#import",
    "gltf_io_preferences": "Preferences/#gltf-io",
    "gltf_object_types": "Operators/IO_Tools/#object-types",
    "help_panel": "Interface/#help-panel",
    "installation": "Installation/",
    "interface": "Interface/#panel-sections",
    "io_panel": "Interface/#io-panel",
    "io_tools": "Operators/IO_Tools/#io-tools",
    "language_preferences": "Preferences/#language",
    "light_add": "Operators/Light_Tools/#add-lights",
    "light_edit": "Operators/Light_Tools/#edit-the-active-light",
    "light_tools": "Operators/Light_Tools/#light-tools",
    "map_it": "Operators/Map_It/#map-it",
    "map_it_values": "Operators/Map_It/#mapping-values",
    "mirror_it": "Operators/Mirror_It/#mirror-it",
    "operators": "Operators/",
    "preferences": "Interface/#settings",
    "preferences_icon_viewer": "Preferences/#icon-viewer-preferences",
    "rez_it": "Operators/Rez_It/#rez-it",
    "script_panel": "Interface/#script-panel",
    "scale_it": "Operators/Scale_It/#scale-it",
    "shrink_it": "Operators/Shrink_It/#shrink-it",
}


def _open_url(operator, url):
    if not bpy.app.online_access:
        operator.report({"WARNING"}, "Online access is disabled in Blender preferences")
        return {"CANCELLED"}

    bpy.ops.wm.url_open(url=url)
    return {"FINISHED"}


class DAT_OT_OpenDocs(Operator):
    bl_idname = "dat.open_docs"
    bl_label = "Open DATools Documentation"
    bl_description = "Open the DATools documentation"

    path: StringProperty(default="")

    def execute(self, context):
        return _open_url(self, DOCS_BASE_URL + self.path)


class DAT_OT_OpenIssues(Operator):
    bl_idname = "dat.open_issues"
    bl_label = "Open DATools Issues"
    bl_description = "Open the DATools GitHub issues page"

    def execute(self, context):
        return _open_url(self, ISSUES_URL)


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
