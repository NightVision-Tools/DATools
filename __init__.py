"""Init DATools"""

bl_info = {
    "name": "DATools",
    "author": "Tinazzi Patrick",
    "version": (1, 10, 1),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > DAT",
    "description": "A set of tools for the DungeonAlchemist™ import pipeline",
    "category": "3D View",
}

import bpy

ADDON_MODULE = __package__

from . import dictionary

dictionary.set_addon_module(ADDON_MODULE)

from .dictionary import (
    get_language_items,
    get_language_display,
    register_translations,
    translate,
    unregister_translations,
)
from .ui.main_panel import (
    DAT_PT_3DV_MainPanel,
    DAT_MainPanelState,
    DAT_OT_MainPanelExpand,
    DAT_OT_MainPanelPin,
    DAT_OT_MainPanelPreviewHello,
    DAT_OT_MainPanelSelect,
    register_custom_icons,
    register_scene_properties,
    unregister_custom_icons,
)
from .ui.help_buttons import DAT_OT_OpenDocs, DOC_PATHS, draw_doc_header
from .ui.select_language import DAT_OP_SelectLanguage
from .operators.floor_it import DAT_OP_FloorIt
from .operators.rez_it import DAT_OP_RezIt
from .operators.scale_it import DAT_OP_ScaleIt
from .operators.mirror_it import DAT_OP_Mirrorit
from .operators.shrink_it import DAT_OP_ShrinkIt
from .operators.map_it import DAT_OP_MapIt
from .operators.custom_scripts import (
    DAT_CustomScriptItem,
    DAT_OT_CustomScriptAdd,
    DAT_OT_CustomScriptDisplayToggle,
    DAT_OT_CustomScriptEdit,
    DAT_OT_CustomScriptIcon,
    DAT_OT_CustomScriptMove,
    DAT_OT_CustomScriptRename,
    DAT_OT_CustomScriptRemove,
    DAT_OT_CustomScriptToggle,
    draw_custom_scripts_settings,
    register_enabled_custom_scripts,
    unregister_custom_scripts,
)
from .operators.gltf_da import (
    DAT_MT_ExportControlWarningPie,
    DAT_OP_FbxExport,
    DAT_OP_FbxImport,
    DAT_OP_ExportControlCancel,
    DAT_OP_ExportControlContinue,
    DAT_OP_ExportControlWarning,
    DAT_OP_GltfExport,
    DAT_OP_GltfImport,
    DAT_OP_GltfProfileDelete,
    DAT_OP_GltfToggleCollision,
    DAT_OP_OpenWarningConsole,
    DAT_OP_StlExport,
    DAT_OP_StlImport,
    DAT_OP_TagMaterialWarnings,
    DAT_OP_UsdzImport,
    DEFAULT_COLLISION_PREFIX,
    PROFILE_DEFAULT_NAME,
    dat_fbx_export_menu,
    dat_fbx_import_menu,
    dat_gltf_export_menu,
    dat_gltf_import_menu,
    dat_stl_export_menu,
    dat_stl_import_menu,
    dat_usdz_import_menu,
    draw_gltf_settings,
    get_gltf_profile_items,
    update_gltf_active_profile,
)


class DAToolsPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_MODULE
    bl_label = "DATools Preferences"

    language: bpy.props.StringProperty(
        name="Language",
        default="ENGLISH",
    )
    custom_scripts: bpy.props.CollectionProperty(type=DAT_CustomScriptItem)
    gltf_collision_prefix: bpy.props.StringProperty(
        name="Collision Prefix",
        description="Objects whose names start with this prefix are treated as Dungeon Alchemist collision objects",
        default=DEFAULT_COLLISION_PREFIX,
    )
    gltf_active_profile_name: bpy.props.StringProperty(
        name="Active GLTF Profile Name",
        default=PROFILE_DEFAULT_NAME,
    )
    gltf_active_profile: bpy.props.EnumProperty(
        name="Active GLTF Profile",
        description="Choose the DATools GLTF export profile",
        items=get_gltf_profile_items,
        update=update_gltf_active_profile,
    )
    gltf_profiles_json: bpy.props.StringProperty(
        name="GLTF Profiles JSON",
        description="Internal DATools storage for GLTF export profiles",
        default="",
    )

    def draw(self, context):
        layout = self.layout
        language_box = layout.box()
        draw_doc_header(
            language_box,
            text=translate("addon_language_header", context),
            icon="WORLD",
            context=context,
            doc_path=DOC_PATHS["preferences"],
        )
        language_box.label(
            text=str(translate("selected_language_text", context)).format(
                get_language_display(self.language)
            )
        )

        row = language_box.row()
        row.operator("dat.select_language", text=translate("language_option_english", context)).language = "ENGLISH"
        row.operator("dat.select_language", text=translate("language_option_italian", context)).language = "ITALIAN"

        row = language_box.row()
        row.operator("dat.select_language", text=translate("language_option_german", context)).language = "GERMAN"
        row.operator("dat.select_language", text=translate("language_option_french", context)).language = "FRENCH"

        draw_custom_scripts_settings(layout, context)
        draw_gltf_settings(layout, context)
        _draw_icon_viewer_preferences(layout, context)


def _get_icon_viewer_addon(context):
    for addon_key in context.preferences.addons.keys():
        if addon_key.endswith(".icon_viewer") or addon_key == "icon_viewer":
            addon = context.preferences.addons.get(addon_key)
            if addon is not None:
                return addon

    return None


def _draw_prop_if_exists(layout, data, prop_name):
    if hasattr(data, prop_name):
        layout.prop(data, prop_name)


def _draw_icon_viewer_preferences(layout, context):
    box = layout.box()
    box.label(text="Icon Viewer Preferences", icon="FILE_IMAGE")

    addon = _get_icon_viewer_addon(context)
    if addon is None:
        box.label(text="Icon Viewer add-on not enabled", icon="INFO")
        return

    prefs = addon.preferences

    try:
        box.operator("iv.icons_show", icon="VIEWZOOM")
    except Exception:
        pass

    row = box.row()

    col = row.column(align=True)
    col.label(text="Icons:")
    _draw_prop_if_exists(col, prefs, "show_matcap_icons")
    _draw_prop_if_exists(col, prefs, "show_brush_icons")
    _draw_prop_if_exists(col, prefs, "show_colorset_icons")
    _draw_prop_if_exists(col, prefs, "show_event_icons")
    col.separator()
    _draw_prop_if_exists(col, prefs, "show_history")

    col = row.column(align=True)
    col.label(text="Popup:")
    _draw_prop_if_exists(col, prefs, "auto_focus_filter")
    _draw_prop_if_exists(col, prefs, "copy_on_select")
    if getattr(prefs, "copy_on_select", False):
        _draw_prop_if_exists(col, prefs, "close_on_select")

    col = row.column(align=True)
    col.label(text="Panel:")
    _draw_prop_if_exists(col, prefs, "show_panel")
    if getattr(prefs, "show_panel", False):
        _draw_prop_if_exists(col, prefs, "show_panel_icons")

    col.separator()
    col.label(text="Header:")
    _draw_prop_if_exists(col, prefs, "show_header")


# register classes
classes = (
    DAT_CustomScriptItem,
    DAToolsPreferences,
    DAT_OP_SelectLanguage,
    DAT_OT_CustomScriptAdd,
    DAT_OT_CustomScriptRemove,
    DAT_OT_CustomScriptEdit,
    DAT_OT_CustomScriptRename,
    DAT_OT_CustomScriptIcon,
    DAT_OT_CustomScriptMove,
    DAT_OT_CustomScriptDisplayToggle,
    DAT_OT_CustomScriptToggle,
    DAT_OT_OpenDocs,
    DAT_OP_FloorIt,
    DAT_OP_RezIt,
    DAT_OP_ScaleIt,
    DAT_OP_Mirrorit,
    DAT_OP_ShrinkIt,
    DAT_OP_MapIt,
    DAT_OP_GltfImport,
    DAT_OP_FbxImport,
    DAT_OP_StlImport,
    DAT_OP_UsdzImport,
    DAT_OP_GltfExport,
    DAT_OP_FbxExport,
    DAT_OP_StlExport,
    DAT_OP_ExportControlWarning,
    DAT_MT_ExportControlWarningPie,
    DAT_OP_ExportControlContinue,
    DAT_OP_ExportControlCancel,
    DAT_OP_OpenWarningConsole,
    DAT_OP_TagMaterialWarnings,
    DAT_OP_GltfToggleCollision,
    DAT_OP_GltfProfileDelete,
    DAT_MainPanelState,
    DAT_OT_MainPanelSelect,
    DAT_OT_MainPanelExpand,
    DAT_OT_MainPanelPin,
    DAT_OT_MainPanelPreviewHello,
    DAT_PT_3DV_MainPanel,
)


def register():
    register_custom_icons()

    for cls in classes:
        bpy.utils.register_class(cls)

    register_translations()
    register_scene_properties()
    register_enabled_custom_scripts()
    bpy.types.TOPBAR_MT_file_export.append(dat_gltf_export_menu)
    bpy.types.TOPBAR_MT_file_export.append(dat_fbx_export_menu)
    bpy.types.TOPBAR_MT_file_export.append(dat_stl_export_menu)
    bpy.types.TOPBAR_MT_file_import.append(dat_gltf_import_menu)
    bpy.types.TOPBAR_MT_file_import.append(dat_fbx_import_menu)
    bpy.types.TOPBAR_MT_file_import.append(dat_stl_import_menu)
    bpy.types.TOPBAR_MT_file_import.append(dat_usdz_import_menu)


def unregister():
    try:
        bpy.types.TOPBAR_MT_file_export.remove(dat_gltf_export_menu)
        bpy.types.TOPBAR_MT_file_export.remove(dat_fbx_export_menu)
        bpy.types.TOPBAR_MT_file_export.remove(dat_stl_export_menu)
        bpy.types.TOPBAR_MT_file_import.remove(dat_gltf_import_menu)
        bpy.types.TOPBAR_MT_file_import.remove(dat_fbx_import_menu)
        bpy.types.TOPBAR_MT_file_import.remove(dat_stl_import_menu)
        bpy.types.TOPBAR_MT_file_import.remove(dat_usdz_import_menu)
    except Exception:
        pass

    unregister_custom_scripts()
    unregister_translations()

    for prop in (
        "dat_panel_state",
        "ui_menu",
        "dat_textureresolution",
        "dat_scale",
        "dat_mirror",
        "dat_shrinkpercentage",
        "dat_shrink_mode",
        "dat_shrink_apply_modifiers",
        "dat_shrink_select_result",
        "dat_location_x",
        "dat_location_y",
        "dat_location_z",
        "dat_rotation_x",
        "dat_rotation_y",
        "dat_rotation_z",
        "dat_scale_x",
        "dat_scale_y",
        "dat_scale_z",
        "dat_scalebuffer",
        "dat_activeobjectbuffer",
    ):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    unregister_custom_icons()

