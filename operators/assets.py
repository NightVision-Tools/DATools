import os

import bpy
from bpy.props import BoolProperty

from .. import dictionary
from ..ui.help_buttons import DOC_PATHS, draw_doc_header

ASSET_BLEND_NAME = "DA_Abstract_Asset.blend"
ASSET_DIR_NAME = "asset"
THUMB_DIR_NAME = "thumbs"

_asset_previews = None
_asset_enum_items = []
_asset_item_map = {}
_last_asset_error = ""
_EMPTY_ASSET_ITEM = ("NONE", "No Assets", "No assets are available", "INFO", 0)


def _addon_root():
    return os.path.dirname(os.path.dirname(__file__))


def _asset_dir():
    return os.path.join(_addon_root(), ASSET_DIR_NAME)


def _asset_blend_path():
    return os.path.join(_asset_dir(), ASSET_BLEND_NAME)


def _thumb_dir():
    return os.path.join(_asset_dir(), THUMB_DIR_NAME)


def _blend_object_dir():
    return os.path.join(_asset_blend_path(), "Object")


def _load_preview_icon(path):
    if _asset_previews is None or not os.path.exists(path):
        return 0

    key = os.path.normpath(path)
    if key not in _asset_previews:
        _asset_previews.load(key, path, "IMAGE")
    return _asset_previews[key].icon_id


def _stable_enum_item(identifier, name, description, icon, number):
    key = f"{identifier}\0{name}\0{description}\0{icon}\0{number}"
    if key not in _asset_item_map:
        _asset_item_map[key] = (identifier, name, description, icon, number)
    return _asset_item_map[key]


def get_asset_names():
    global _last_asset_error
    path = _asset_blend_path()
    if not os.path.exists(path):
        _last_asset_error = ""
        return []

    try:
        with bpy.data.libraries.load(path) as (data_from, _data_to):
            _last_asset_error = ""
            return list(data_from.objects)
    except Exception as exc:
        _last_asset_error = str(exc)
        return []


def refresh_asset_items():
    _asset_enum_items.clear()
    _asset_item_map.clear()

    for index, name in enumerate(get_asset_names()):
        thumb_path = os.path.join(_thumb_dir(), f"{name}.png")
        try:
            icon = _load_preview_icon(thumb_path)
        except Exception:
            icon = 0
        _asset_enum_items.append(
            _stable_enum_item(name, name, dictionary.translate("asset_icons_description"), icon, index)
        )


def get_asset_items(self, context):
    if not _asset_enum_items:
        refresh_asset_items()
    return _asset_enum_items if _asset_enum_items else [_EMPTY_ASSET_ITEM]


def _selected_asset_name(context):
    name = getattr(context.scene, "dat_asset_icons", "")
    if name == "NONE":
        return None
    return name if name else None


def _asset_exists_in_library(name):
    return name in get_asset_names()


def _append_asset(name):
    before = {obj.name for obj in bpy.data.objects}
    bpy.ops.wm.append(directory=_blend_object_dir(), filename=name, link=False)
    return [obj for obj in bpy.data.objects if obj.name not in before]


def _select_objects(context, objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    if objects:
        context.view_layer.objects.active = objects[0]


def _unique_name(base_name):
    if bpy.data.objects.get(base_name) is None:
        return base_name

    index = 1
    while bpy.data.objects.get(f"{base_name}.{index:03d}") is not None:
        index += 1
    return f"{base_name}.{index:03d}"


def _selected_asset_or_report(operator, context):
    name = _selected_asset_name(context)
    if not name:
        operator.report({"WARNING"}, dictionary.translate("asset_no_selection", context))
        return None

    if not os.path.exists(_asset_blend_path()):
        operator.report({"ERROR"}, dictionary.translate("asset_missing_library", context))
        return None

    if not _asset_exists_in_library(name):
        operator.report({"ERROR"}, dictionary.translate("asset_not_found", context))
        return None

    return name


class DAT_OP_AssetToggleReference(bpy.types.Operator):
    bl_idname = "dat.asset_toggle_reference"
    bl_label = "Add / Hide Asset"
    bl_description = "Add or toggle the selected abstract asset as a reference"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        name = _selected_asset_or_report(self, context)
        if name is None:
            return {"CANCELLED"}

        obj = bpy.data.objects.get(name)
        if obj is not None:
            obj.hide_viewport = not obj.hide_viewport
            obj.hide_render = obj.hide_viewport
            message_key = "asset_hidden" if obj.hide_viewport else "asset_shown"
            self.report({"INFO"}, dictionary.translate(message_key, context).format(name))
            return {"FINISHED"}

        objects = _append_asset(name)
        if objects:
            _select_objects(context, objects)
        self.report({"INFO"}, dictionary.translate("asset_appended", context).format(name))
        return {"FINISHED"}


class DAT_OP_AssetReimportReference(bpy.types.Operator):
    bl_idname = "dat.asset_reimport_reference"
    bl_label = "Reimport Asset"
    bl_description = "Delete and reimport the selected abstract asset reference"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        name = _selected_asset_or_report(self, context)
        if name is None:
            return {"CANCELLED"}

        obj = bpy.data.objects.get(name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)

        objects = _append_asset(name)
        if objects:
            _select_objects(context, objects)
        self.report({"INFO"}, dictionary.translate("asset_reimported", context).format(name))
        return {"FINISHED"}


class DAT_OP_AssetAddCopy(bpy.types.Operator):
    bl_idname = "dat.asset_add_copy"
    bl_label = "Add Copy Asset"
    bl_description = "Add a renamed editable copy of the selected abstract asset"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        name = _selected_asset_or_report(self, context)
        if name is None:
            return {"CANCELLED"}

        objects = _append_asset(name)
        for obj in objects:
            obj.name = _unique_name(f"{name}_Copy")
            obj["dat_asset_copy"] = True
            if obj.data is not None:
                obj.data = obj.data.copy()

        if objects:
            _select_objects(context, objects)
        self.report({"INFO"}, dictionary.translate("asset_copy_added", context).format(name))
        return {"FINISHED"}


class DAT_OP_AssetRemoveReferences(bpy.types.Operator):
    bl_idname = "dat.asset_remove_references"
    bl_label = "Remove All Assets"
    bl_description = "Remove all abstract asset references, leaving renamed copies untouched"
    bl_options = {"REGISTER", "UNDO"}

    confirm: BoolProperty(default=True)

    def execute(self, context):
        asset_names = set(get_asset_names())
        removed = 0

        for obj in list(bpy.data.objects):
            if obj.name in asset_names:
                bpy.data.objects.remove(obj, do_unlink=True)
                removed += 1

        self.report({"INFO"}, dictionary.translate("asset_removed_all", context).format(removed))
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


def draw_asset_panel(layout, context):
    state = context.scene.dat_panel_state
    layout.scale_y = state.submenu_button_scale * state.ui_text_scale

    if not os.path.exists(_asset_blend_path()):
        layout.label(text=dictionary.translate("asset_missing_library", context), icon="ERROR")
        return

    refresh_asset_items()
    if not _asset_enum_items:
        if _last_asset_error:
            layout.label(text=dictionary.translate("asset_library_error", context), icon="ERROR")
            layout.label(text=_last_asset_error[:120], icon="INFO")
            return
        layout.label(text=dictionary.translate("asset_empty_library", context), icon="INFO")
        return

    box = layout.box()
    draw_doc_header(
        box,
        text=dictionary.translate("menu_asset", context),
        icon="ASSET_MANAGER",
        context=context,
        doc_path=DOC_PATHS["asset_panel"],
    )
    column = box.column(align=True)
    column.operator_context = "INVOKE_DEFAULT"
    column.template_icon_view(
        context.scene,
        "dat_asset_icons",
        show_labels=True,
        scale=5.0,
        scale_popup=state.asset_gallery_scale,
    )

    actions = column.grid_flow(columns=4, row_major=True, even_columns=False, even_rows=False, align=True)
    actions.operator("dat.asset_toggle_reference", text="", icon="UV_SYNC_SELECT")
    actions.operator("dat.asset_reimport_reference", text="", icon="FOLDER_REDIRECT")
    actions.operator("dat.asset_add_copy", text="", icon="IMPORT")
    remove_row = actions.row(align=True)
    remove_row.alert = True
    remove_row.operator("dat.asset_remove_references", text="", icon="TRASH")


def register_asset_previews():
    global _asset_previews
    import bpy.utils.previews

    unregister_asset_previews()
    _asset_previews = bpy.utils.previews.new()


def unregister_asset_previews():
    global _asset_previews
    import bpy.utils.previews

    if _asset_previews is not None:
        bpy.utils.previews.remove(_asset_previews)
        _asset_previews = None
    _asset_enum_items.clear()
    _asset_item_map.clear()
