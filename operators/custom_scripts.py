import hashlib
import importlib.util
import os
import re
import shutil

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy.types import Operator, PropertyGroup
from bpy_extras.io_utils import ImportHelper

from .. import __package__ as ADDON_PACKAGE
from .. import dictionary
from ..ui.help_buttons import DOC_PATHS, draw_help_button, show_help_buttons


_loaded_modules = {}
_valid_icon_ids = None


def _scripts_dir():
    user_dir = bpy.utils.extension_path_user(ADDON_PACKAGE, create=True)
    path = os.path.join(user_dir, "custom_scripts")
    os.makedirs(path, exist_ok=True)
    return path


def _safe_name(value):
    name = os.path.splitext(os.path.basename(value))[0]
    name = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")
    return name or "custom_script"


def _get_valid_icon_ids():
    global _valid_icon_ids
    if _valid_icon_ids is not None:
        return _valid_icon_ids

    try:
        enum_items = bpy.types.UILayout.bl_rna.functions["operator"].parameters["icon"].enum_items
        _valid_icon_ids = {item.identifier for item in enum_items}
    except Exception:
        _valid_icon_ids = set()
    return _valid_icon_ids


def _clean_icon(value):
    icon = (value or "FILE_SCRIPT").strip().upper()
    valid_icons = _get_valid_icon_ids()
    if valid_icons and icon not in valid_icons:
        return "FILE_SCRIPT"
    return icon


def _is_valid_icon(value):
    icon = (value or "").strip().upper()
    valid_icons = _get_valid_icon_ids()
    return bool(icon) and (not valid_icons or icon in valid_icons)


def script_icon(item):
    return _clean_icon(getattr(item, "icon", "FILE_SCRIPT"))


def _unique_script_path(source_path):
    scripts_dir = _scripts_dir()
    base_name = _safe_name(source_path)
    candidate = os.path.join(scripts_dir, base_name + ".py")
    index = 1
    while os.path.exists(candidate):
        candidate = os.path.join(scripts_dir, "{}_{}.py".format(base_name, index))
        index += 1
    return candidate


def _copy_script(source_path, destination_path=None):
    if not source_path or not os.path.isfile(source_path):
        raise FileNotFoundError(source_path)
    if os.path.splitext(source_path)[1].lower() != ".py":
        raise ValueError("Only Python scripts can be imported")

    destination_path = destination_path or _unique_script_path(source_path)
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    shutil.copy2(source_path, destination_path)
    return destination_path


def _module_name(path):
    normalized = os.path.normcase(os.path.abspath(path))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    module_base = _safe_name(path)
    return "{}.custom_scripts_runtime.{}_{}".format(ADDON_PACKAGE, module_base, digest)


def _get_addon_preferences(context=None):
    return dictionary.get_addon_preferences(context)


def _is_already_unregistered_error(exc):
    message = str(exc)
    return "missing bl_rna attribute" in message or "not registered" in message


def _safe_unregister_class(cls):
    try:
        bpy.utils.unregister_class(cls)
    except RuntimeError as exc:
        if not _is_already_unregistered_error(exc):
            raise
    except Exception as exc:
        print("DATools custom script class unload failed: {} ({})".format(getattr(cls, "__name__", cls), exc))


def _fallback_unregister_classes(module):
    classes = getattr(module, "_datools_registered_classes", None)
    if not classes:
        classes = getattr(module, "classes", ())

    for cls in reversed(tuple(classes)):
        _safe_unregister_class(cls)


def _unregister_module(module):
    unregister = getattr(module, "unregister", None)
    if callable(unregister):
        try:
            unregister()
        except RuntimeError as exc:
            if not _is_already_unregistered_error(exc):
                print("DATools custom script unload failed: {} ({})".format(module.__name__, exc))
            _fallback_unregister_classes(module)
        except Exception as exc:
            print("DATools custom script unload failed: {} ({})".format(module.__name__, exc))
            _fallback_unregister_classes(module)
        return

    _fallback_unregister_classes(module)


def _register_module(module):
    register = getattr(module, "register", None)
    if callable(register):
        register()
        module._datools_registered_classes = tuple(getattr(module, "classes", ()))
        return

    registered = []
    for cls in getattr(module, "classes", ()):
        bpy.utils.register_class(cls)
        registered.append(cls)
    module._datools_registered_classes = tuple(registered)


def load_custom_script(item):
    path = bpy.path.abspath(item.internal_path)
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(path)

    key = os.path.normcase(os.path.abspath(path))
    if key in _loaded_modules:
        return _loaded_modules[key]

    module_name = _module_name(path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load script: {}".format(path))

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        _register_module(module)
    except Exception:
        raise

    _loaded_modules[key] = module
    return module


def unload_custom_script(item):
    path = bpy.path.abspath(item.internal_path)
    if not path:
        return

    key = os.path.normcase(os.path.abspath(path))
    module = _loaded_modules.pop(key, None)
    if module is None:
        return

    _unregister_module(module)


def register_enabled_custom_scripts(context=None):
    prefs = _get_addon_preferences(context)
    if prefs is None:
        return

    for item in prefs.custom_scripts:
        if item.active:
            try:
                load_custom_script(item)
            except Exception as exc:
                print("DATools custom script load failed: {} ({})".format(item.name, exc))


def unregister_custom_scripts(context=None):
    prefs = _get_addon_preferences(context)
    if prefs is None:
        return

    for item in prefs.custom_scripts:
        try:
            unload_custom_script(item)
        except Exception as exc:
            print("DATools custom script unload failed: {} ({})".format(item.name, exc))


def active_custom_scripts(context=None):
    prefs = _get_addon_preferences(context)
    if prefs is None:
        return []
    return [item for item in prefs.custom_scripts if item.active]


def draw_custom_script(layout, context, item):
    try:
        module = load_custom_script(item)
    except Exception as exc:
        layout.label(text="{}: {}".format(dictionary.translate("custom_script_load_error", context), exc), icon="ERROR")
        return

    draw = getattr(module, "draw", None)
    if callable(draw):
        try:
            draw(layout, context)
        except Exception as exc:
            layout.label(text="{}: {}".format(dictionary.translate("custom_script_draw_error", context), exc), icon="ERROR")
    else:
        layout.label(text=dictionary.translate("custom_script_no_draw", context), icon="INFO")


def draw_custom_scripts_settings(layout, context):
    prefs = _get_addon_preferences(context)

    box = layout.box()
    if show_help_buttons(context):
        split = box.split(factor=0.72, align=True)
        header = split.row(align=True)
        header.label(text=dictionary.translate("custom_scripts_header", context), icon="FILE_SCRIPT")

        actions = split.row(align=True)
        actions.alignment = "RIGHT"
        actions.operator_context = "INVOKE_DEFAULT"
        actions.operator("dat.custom_script_add", text="", icon="ADD")
        draw_help_button(actions, DOC_PATHS["custom_scripts"])
    else:
        header = box.row(align=True)
        header.label(text=dictionary.translate("custom_scripts_header", context), icon="FILE_SCRIPT")
        header.operator_context = "INVOKE_DEFAULT"
        header.operator("dat.custom_script_add", text="", icon="ADD")

    if prefs is None:
        box.label(text="DATools preferences not found", icon="ERROR")
        return

    if len(prefs.custom_scripts) == 0:
        box.label(text=dictionary.translate("custom_scripts_empty_settings", context), icon="INFO")

    for index, item in enumerate(prefs.custom_scripts):
        row = box.row(align=True)
        file_col = row.column(align=True)
        file_col.label(text=item.name or os.path.basename(item.internal_path), icon=script_icon(item))
        if item.internal_path:
            file_col.label(text=bpy.path.abspath(item.internal_path), icon="BLANK1")

        actions = row.row(align=True)
        actions.operator_context = "INVOKE_DEFAULT"
        up_row = actions.row(align=True)
        up_row.enabled = index > 0
        move_up = up_row.operator("dat.custom_script_move", text="", icon="TRIA_UP")
        move_up.index = index
        move_up.direction = -1
        down_row = actions.row(align=True)
        down_row.enabled = index < len(prefs.custom_scripts) - 1
        move_down = down_row.operator("dat.custom_script_move", text="", icon="TRIA_DOWN")
        move_down.index = index
        move_down.direction = 1
        toggle = actions.operator(
            "dat.custom_script_toggle",
            text="",
            icon="CHECKBOX_HLT" if item.active else "CHECKBOX_DEHLT",
            depress=item.active,
        )
        toggle.index = index
        icon = actions.operator("dat.custom_script_icon", text="", icon=script_icon(item))
        icon.index = index
        show_icon = actions.operator(
            "dat.custom_script_display_toggle",
            text="",
            icon="RESTRICT_RENDER_ON",
            depress=getattr(item, "show_icon", True),
        )
        show_icon.index = index
        show_icon.property_name = "show_icon"
        show_title = actions.operator(
            "dat.custom_script_display_toggle",
            text="",
            icon="OUTLINER_OB_FONT",
            depress=getattr(item, "show_title", True),
        )
        show_title.index = index
        show_title.property_name = "show_title"
        rename = actions.operator("dat.custom_script_rename", text="", icon="GREASEPENCIL")
        rename.index = index
        edit = actions.operator("dat.custom_script_edit", text="", icon="FOLDER_REDIRECT")
        edit.index = index
        remove = actions.operator("dat.custom_script_remove", text="", icon="REMOVE")
        remove.index = index


class DAT_CustomScriptItem(PropertyGroup):
    name: StringProperty(name="Name", default="")
    source_path: StringProperty(name="Source", subtype="FILE_PATH", default="")
    internal_path: StringProperty(name="Imported File", subtype="FILE_PATH", default="")
    icon: StringProperty(name="Icon", default="FILE_SCRIPT")
    show_icon: BoolProperty(name="Show Icon", default=True)
    show_title: BoolProperty(name="Show Title", default=True)
    active: BoolProperty(name="Active", default=True)


class DAT_OT_CustomScriptAdd(Operator, ImportHelper):
    bl_idname = "dat.custom_script_add"
    bl_label = "Add Custom Script"
    bl_description = "Import a Python script into DATools custom scripts"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".py"
    filter_glob: StringProperty(default="*.py", options={"HIDDEN"})

    def execute(self, context):
        prefs = _get_addon_preferences(context)
        if prefs is None:
            self.report({"ERROR"}, "DATools preferences not found")
            return {"CANCELLED"}

        try:
            destination = _copy_script(self.filepath)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        item = prefs.custom_scripts.add()
        item.name = _safe_name(destination)
        item.source_path = self.filepath
        item.internal_path = destination
        item.icon = "FILE_SCRIPT"
        item.show_icon = True
        item.show_title = True
        item.active = True

        try:
            load_custom_script(item)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            item.active = False
            prefs.custom_scripts.remove(len(prefs.custom_scripts) - 1)
            try:
                os.remove(destination)
            except OSError:
                pass
            return {"CANCELLED"}

        self.report({"INFO"}, "Custom script added: {}".format(item.name))
        return {"FINISHED"}


class DAT_OT_CustomScriptRemove(Operator):
    bl_idname = "dat.custom_script_remove"
    bl_label = "Remove Custom Script"
    bl_description = "Remove a DATools custom script"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        prefs = _get_addon_preferences(context)
        if prefs is None or self.index < 0 or self.index >= len(prefs.custom_scripts):
            return {"CANCELLED"}

        item = prefs.custom_scripts[self.index]
        internal_path = bpy.path.abspath(item.internal_path)
        unload_custom_script(item)

        scripts_dir = os.path.normcase(os.path.abspath(_scripts_dir()))
        candidate = os.path.normcase(os.path.abspath(internal_path))
        if candidate.startswith(scripts_dir + os.sep) and os.path.isfile(internal_path):
            try:
                os.remove(internal_path)
            except OSError as exc:
                self.report({"WARNING"}, str(exc))

        prefs.custom_scripts.remove(self.index)
        return {"FINISHED"}


class DAT_OT_CustomScriptEdit(Operator, ImportHelper):
    bl_idname = "dat.custom_script_edit"
    bl_label = "Change Custom Script Source"
    bl_description = "Replace the imported file for a DATools custom script"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".py"
    filter_glob: StringProperty(default="*.py", options={"HIDDEN"})
    index: IntProperty(default=-1)

    def execute(self, context):
        prefs = _get_addon_preferences(context)
        if prefs is None or self.index < 0 or self.index >= len(prefs.custom_scripts):
            return {"CANCELLED"}

        item = prefs.custom_scripts[self.index]
        was_active = bool(item.active)
        old_path = bpy.path.abspath(item.internal_path)
        old_name = item.name
        old_source_path = item.source_path
        old_internal_path = item.internal_path
        unload_custom_script(item)

        try:
            destination = _copy_script(self.filepath)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        item.name = _safe_name(destination)
        item.source_path = self.filepath
        item.internal_path = destination

        if was_active:
            try:
                load_custom_script(item)
                item.active = True
            except Exception as exc:
                item.name = old_name
                item.source_path = old_source_path
                item.internal_path = old_internal_path
                item.active = was_active
                try:
                    os.remove(destination)
                except OSError:
                    pass
                try:
                    if was_active:
                        load_custom_script(item)
                except Exception:
                    item.active = False
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}

        scripts_dir = os.path.normcase(os.path.abspath(_scripts_dir()))
        old_candidate = os.path.normcase(os.path.abspath(old_path))
        if old_candidate.startswith(scripts_dir + os.sep) and old_path != destination and os.path.isfile(old_path):
            try:
                os.remove(old_path)
            except OSError as exc:
                self.report({"WARNING"}, str(exc))

        return {"FINISHED"}


class DAT_OT_CustomScriptRename(Operator):
    bl_idname = "dat.custom_script_rename"
    bl_label = "Rename Custom Script"
    bl_description = "Change the title shown for this custom script in the Script panel"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1)
    name: StringProperty(name="Title", default="")

    def invoke(self, context, event):
        prefs = _get_addon_preferences(context)
        if prefs is None or self.index < 0 or self.index >= len(prefs.custom_scripts):
            return {"CANCELLED"}

        self.name = prefs.custom_scripts[self.index].name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        prefs = _get_addon_preferences(context)
        if prefs is None or self.index < 0 or self.index >= len(prefs.custom_scripts):
            return {"CANCELLED"}

        item = prefs.custom_scripts[self.index]
        title = self.name.strip()
        item.name = title or _safe_name(item.internal_path)
        return {"FINISHED"}


class DAT_OT_CustomScriptIcon(Operator):
    bl_idname = "dat.custom_script_icon"
    bl_label = "Change Custom Script Icon"
    bl_description = "Change the icon shown for this custom script"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1)
    icon: StringProperty(name="Icon", default="FILE_SCRIPT")

    def invoke(self, context, event):
        prefs = _get_addon_preferences(context)
        if prefs is None or self.index < 0 or self.index >= len(prefs.custom_scripts):
            return {"CANCELLED"}

        self.icon = script_icon(prefs.custom_scripts[self.index])
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "icon", text="Icon")

    def execute(self, context):
        prefs = _get_addon_preferences(context)
        if prefs is None or self.index < 0 or self.index >= len(prefs.custom_scripts):
            return {"CANCELLED"}

        icon = self.icon
        if not _is_valid_icon(icon):
            self.report({"ERROR"}, "Invalid Blender icon: {}".format(self.icon))
            return {"CANCELLED"}

        prefs.custom_scripts[self.index].icon = icon
        return {"FINISHED"}


class DAT_OT_CustomScriptMove(Operator):
    bl_idname = "dat.custom_script_move"
    bl_label = "Move Custom Script"
    bl_description = "Move this custom script up or down"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1)
    direction: IntProperty(default=0)

    def execute(self, context):
        prefs = _get_addon_preferences(context)
        if prefs is None or self.index < 0 or self.index >= len(prefs.custom_scripts):
            return {"CANCELLED"}

        new_index = self.index + (-1 if self.direction < 0 else 1)
        if new_index < 0 or new_index >= len(prefs.custom_scripts):
            return {"CANCELLED"}

        prefs.custom_scripts.move(self.index, new_index)
        return {"FINISHED"}


class DAT_OT_CustomScriptDisplayToggle(Operator):
    bl_idname = "dat.custom_script_display_toggle"
    bl_label = "Toggle Custom Script Display"
    bl_description = "Show or hide this custom script detail in the Script panel"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1)
    property_name: StringProperty(default="")

    def execute(self, context):
        prefs = _get_addon_preferences(context)
        if prefs is None or self.index < 0 or self.index >= len(prefs.custom_scripts):
            return {"CANCELLED"}
        if self.property_name not in {"show_icon", "show_title"}:
            return {"CANCELLED"}

        item = prefs.custom_scripts[self.index]
        setattr(item, self.property_name, not bool(getattr(item, self.property_name, True)))
        return {"FINISHED"}


class DAT_OT_CustomScriptToggle(Operator):
    bl_idname = "dat.custom_script_toggle"
    bl_label = "Toggle Custom Script"
    bl_description = "Show or hide this custom script in the DATools Script panel"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1)

    def execute(self, context):
        prefs = _get_addon_preferences(context)
        if prefs is None or self.index < 0 or self.index >= len(prefs.custom_scripts):
            return {"CANCELLED"}

        item = prefs.custom_scripts[self.index]
        item.active = not item.active
        if item.active:
            try:
                load_custom_script(item)
            except Exception as exc:
                item.active = False
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
        else:
            unload_custom_script(item)

        return {"FINISHED"}
