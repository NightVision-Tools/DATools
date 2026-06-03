import base64
import json
import mimetypes
import os
import unicodedata

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import Menu, Operator
from mathutils import Vector

from .. import dictionary
from ..ui.help_buttons import DOC_PATHS, draw_doc_header


COLLISION_OBJECT_KEY = "is_collision"
DEFAULT_COLLISION_PREFIX = "COL_"
PROFILE_DEFAULT_NAME = "Default"
EXPORT_CONTROL_STATE = {
    "pending_kwargs": None,
    "pending_operator_id": "",
    "warning_title": "",
    "warning_message": "",
    "warning_details": "",
    "warning_nodes": [],
    "warning_node_details": [],
}
EXPORT_CONTROL_WARNING_PIE_ID = "DAT_MT_export_control_warning_pie"
SUPPORTED_EXPORT_MATERIAL_NODE_TYPES = {
    "BSDF_PRINCIPLED",
    "TEX_IMAGE",
    "OUTPUT_MATERIAL",
    "NORMAL_MAP",
    "TEX_COORD",
    "REROUTE",
    "MAPPING",
    "DISPLACEMENT",
    "FRAME",
}
PROFILE_FIELDS = (
    "export_format_ui",
    "export_scope",
    "apply_modifiers",
    "export_materials",
    "check_materials_before_export",
    "triangulate_all",
    "convert_curves_to_mesh",
    "convert_text_to_mesh",
    "convert_surfaces_to_mesh",
    "convert_meta_to_mesh",
    "include_empties",
    "include_cameras",
    "lights_mode",
    "exclude_unsupported_lights",
    "export_animations_mode",
    "use_prefix_for_collisions",
    "use_property_for_collisions",
    "write_collision_manifest",
    "unicode_policy",
)


def _t(key, context=None):
    return dictionary.translate(key, context)


def _addon_preferences(context=None):
    prefs = dictionary.get_addon_preferences(context)
    if prefs is None:
        raise RuntimeError("DATools preferences are not available")
    return prefs


def _ensure_extension(filepath, export_format_ui):
    fmt = export_format_ui.upper()
    if fmt == "GLB" and not filepath.lower().endswith(".glb"):
        return filepath + ".glb"
    if fmt in {"GLTF_SEPARATE", "GLTF_EMBEDDED"} and not filepath.lower().endswith(".gltf"):
        return filepath + ".gltf"
    return filepath


def _ensure_file_extension(filepath, extension):
    if not filepath.lower().endswith(extension.lower()):
        return filepath + extension
    return filepath


def _world_bbox(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_v = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    max_v = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    return min_v, max_v


def _is_collision_object(obj, prefix="", use_prefix=True, use_property=True):
    by_prefix = bool(use_prefix and prefix and obj.name.startswith(prefix))
    by_property = bool(use_property and obj.get(COLLISION_OBJECT_KEY))
    return by_prefix or by_property


def _format_name_list(names, max_items=6):
    shown = names[:max_items]
    suffix = "" if len(names) <= max_items else ", +{}".format(len(names) - max_items)
    return ", ".join(shown) + suffix


def _node_display_name(node):
    label = getattr(node, "label", "")
    if label:
        return label
    name = getattr(node, "name", "")
    if name:
        return name
    bl_label = getattr(node, "bl_label", "")
    if bl_label:
        return bl_label
    return getattr(node, "type", "Node")


def _node_parent_names(node):
    names = []
    parent = getattr(node, "parent", None)
    seen = set()
    while parent is not None:
        try:
            parent_id = parent.as_pointer()
        except Exception:
            parent_id = id(parent)
        if parent_id in seen:
            break
        seen.add(parent_id)
        names.insert(0, _node_display_name(parent))
        parent = getattr(parent, "parent", None)
    return names


def _warning_node_detail(material, node, path):
    return {
        "material": material.name,
        "path": " -> ".join(path),
        "node_type": getattr(node, "type", "UNKNOWN"),
        "node_name": _node_display_name(node),
    }


def _collect_invalid_material_nodes(material):
    invalid = []
    if material is None or not material.use_nodes or material.node_tree is None:
        return invalid

    def walk_node_tree(node_tree, path_prefix, visited_trees):
        for node in node_tree.nodes:
            node_path = path_prefix + _node_parent_names(node) + [_node_display_name(node)]

            if node.type not in SUPPORTED_EXPORT_MATERIAL_NODE_TYPES:
                invalid.append((node, _warning_node_detail(material, node, node_path)))

            group_tree = getattr(node, "node_tree", None)
            if group_tree is None:
                continue

            try:
                group_tree_id = group_tree.as_pointer()
            except Exception:
                group_tree_id = id(group_tree)
            if group_tree_id in visited_trees:
                continue

            walk_node_tree(group_tree, node_path, visited_trees | {group_tree_id})

    try:
        root_tree_id = material.node_tree.as_pointer()
    except Exception:
        root_tree_id = id(material.node_tree)
    walk_node_tree(material.node_tree, [material.name], {root_tree_id})
    return invalid


def _print_export_control_warning_nodes():
    details = EXPORT_CONTROL_STATE.get("warning_node_details", [])
    if not details:
        print("[DATools] Material check: no unsupported material nodes found.")
        return

    print("[DATools] Material check: unsupported material nodes")
    for detail in details:
        print(
            "[DATools] - {path} ({node_type})".format(
                path=detail.get("path", ""),
                node_type=detail.get("node_type", "UNKNOWN"),
            )
        )


def _focus_visible_system_console():
    if os.name != "nt":
        return False

    try:
        import ctypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = kernel32.GetConsoleWindow()
        if not hwnd or not user32.IsWindowVisible(hwnd):
            return False

        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def _check_material_export_problems(objects, prefix="", use_prefix=True, use_property=True):
    invalid_objects = []
    invalid_nodes = set()
    warning_nodes = []
    warning_node_details = []
    seen_warning_nodes = set()

    for obj in objects:
        if _is_collision_object(obj, prefix, use_prefix, use_property):
            continue
        if not hasattr(obj, "material_slots"):
            continue

        has_error = False
        for slot in obj.material_slots:
            material = slot.material
            if material is None or not material.use_nodes or material.node_tree is None:
                continue

            for node, detail in _collect_invalid_material_nodes(material):
                has_error = True
                invalid_nodes.add(node.type.lower())

                try:
                    node_key = (material.as_pointer(), node.as_pointer(), detail["path"])
                except Exception:
                    node_key = (material.name, detail["path"], detail["node_type"])
                if node_key in seen_warning_nodes:
                    continue
                seen_warning_nodes.add(node_key)
                warning_nodes.append(node)
                warning_node_details.append(detail)

        if has_error:
            invalid_objects.append(obj.name)

    return sorted(invalid_objects), sorted(invalid_nodes), warning_nodes, warning_node_details


def _store_export_control_warning(
    operator,
    context,
    invalid_objects,
    invalid_nodes,
    warning_nodes,
    warning_node_details,
    pending_fields=None,
):
    fields = pending_fields or getattr(operator, "export_control_fields", PROFILE_FIELDS)
    EXPORT_CONTROL_STATE["pending_kwargs"] = {
        key: getattr(operator, key)
        for key in fields
        if hasattr(operator, key)
    }
    for key in ("filepath", "filter_glob", "profile_save_as", "profile_new_name"):
        if hasattr(operator, key):
            EXPORT_CONTROL_STATE["pending_kwargs"][key] = getattr(operator, key)
    if hasattr(operator, "skip_export_control"):
        EXPORT_CONTROL_STATE["pending_kwargs"]["skip_export_control"] = True
    EXPORT_CONTROL_STATE["pending_operator_id"] = operator.bl_idname
    EXPORT_CONTROL_STATE["warning_title"] = _t("export_control_warning_title", context)
    EXPORT_CONTROL_STATE["warning_message"] = _t("export_control_warning_objects", context).format(
        _format_name_list(invalid_objects)
    )
    EXPORT_CONTROL_STATE["warning_details"] = _t("export_control_warning_nodes", context).format(
        _format_name_list(invalid_nodes)
    )
    EXPORT_CONTROL_STATE["warning_nodes"] = warning_nodes
    EXPORT_CONTROL_STATE["warning_node_details"] = warning_node_details


def _clear_export_control_state():
    EXPORT_CONTROL_STATE["pending_kwargs"] = None
    EXPORT_CONTROL_STATE["pending_operator_id"] = ""
    EXPORT_CONTROL_STATE["warning_title"] = ""
    EXPORT_CONTROL_STATE["warning_message"] = ""
    EXPORT_CONTROL_STATE["warning_details"] = ""
    EXPORT_CONTROL_STATE["warning_nodes"] = []
    EXPORT_CONTROL_STATE["warning_node_details"] = []


def _continue_pending_export(context, reporter=None):
    pending_kwargs = EXPORT_CONTROL_STATE.get("pending_kwargs")
    operator_id = EXPORT_CONTROL_STATE.get("pending_operator_id")
    if not pending_kwargs or not operator_id:
        if reporter is not None:
            reporter({"ERROR"}, _t("export_control_missing_pending", context))
        return {"CANCELLED"}

    try:
        module_name, operator_name = operator_id.split(".", 1)
        operator = getattr(getattr(bpy.ops, module_name), operator_name)
    except Exception:
        if reporter is not None:
            reporter({"ERROR"}, _t("export_control_missing_pending", context))
        return {"CANCELLED"}

    call_context = "EXEC_DEFAULT" if pending_kwargs.get("filepath") else "INVOKE_DEFAULT"
    result = operator(call_context, **pending_kwargs)
    _clear_export_control_state()
    return result


def _warn_for_export_materials_if_needed(operator, context, objects, use_prefix=True, use_property=True):
    if not getattr(operator, "check_materials_before_export", False):
        return False
    if getattr(operator, "skip_export_control", False):
        return False
    if hasattr(operator, "export_materials") and getattr(operator, "export_materials") != "EXPORT":
        return False

    prefs = _addon_preferences(context)
    invalid_objects, invalid_nodes, warning_nodes, warning_node_details = _check_material_export_problems(
        objects,
        prefs.gltf_collision_prefix,
        use_prefix,
        use_property,
    )
    if not invalid_objects:
        return False

    _store_export_control_warning(operator, context, invalid_objects, invalid_nodes, warning_nodes, warning_node_details)
    bpy.ops.dat.export_control_warning("INVOKE_DEFAULT")
    return True


def _scene_has_animations(context):
    try:
        if any(action and getattr(action, "fcurves", None) and len(action.fcurves) > 0 for action in bpy.data.actions):
            return True
    except Exception:
        pass

    for obj in context.scene.objects:
        animation_data = getattr(obj, "animation_data", None)
        if animation_data and (animation_data.action or (animation_data.nla_tracks and len(animation_data.nla_tracks) > 0)):
            return True
    return False


def _supported_operator_properties(operator):
    try:
        return {prop.identifier for prop in operator.get_rna_type().properties}
    except Exception:
        return set()


def _call_operator_with_supported_properties(operator, **kwargs):
    supported = _supported_operator_properties(operator)
    if supported:
        kwargs = {key: value for key, value in kwargs.items() if key in supported}
    return operator(**kwargs)


def _resolve_bpy_operator(operator_path):
    current = bpy.ops
    for part in operator_path.split("."):
        try:
            current = getattr(current, part)
        except Exception:
            return None
    return current


def _call_first_available_operator(operator_paths, **kwargs):
    last_error = None
    for operator_path in operator_paths:
        operator = _resolve_bpy_operator(operator_path)
        if operator is None:
            continue
        try:
            return _call_operator_with_supported_properties(operator, **kwargs)
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("No compatible Blender operator found")


def _strip_accents_to_ascii(text):
    if not isinstance(text, str):
        return text
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_json_strings(obj, policy):
    if isinstance(obj, dict):
        return {key: _normalize_json_strings(value, policy) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_normalize_json_strings(value, policy) for value in obj]
    if isinstance(obj, str):
        return _strip_accents_to_ascii(obj) if policy == "ASCII" else obj
    return obj


def _apply_unicode_policy_to_json_file(path, policy):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    data = _normalize_json_strings(data, policy)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)


def _embed_external_resources(gltf_path, delete_bin_after=True):
    folder = os.path.dirname(gltf_path)
    with open(gltf_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    inlined_bins = []
    for buffer in data.get("buffers", []):
        uri = buffer.get("uri")
        if uri and not uri.startswith("data:"):
            bin_path = os.path.join(folder, uri)
            if os.path.exists(bin_path):
                with open(bin_path, "rb") as bin_handle:
                    encoded = base64.b64encode(bin_handle.read()).decode("ascii")
                buffer["uri"] = f"data:application/octet-stream;base64,{encoded}"
                inlined_bins.append(bin_path)

    for image in data.get("images", []):
        uri = image.get("uri")
        if uri and not uri.startswith("data:"):
            image_path = os.path.join(folder, uri)
            if os.path.exists(image_path):
                mime, _ = mimetypes.guess_type(image_path)
                if not mime:
                    mime = "image/png"
                with open(image_path, "rb") as image_handle:
                    encoded = base64.b64encode(image_handle.read()).decode("ascii")
                image["uri"] = f"data:{mime};base64,{encoded}"

    with open(gltf_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)

    if delete_bin_after:
        for path in inlined_bins:
            try:
                os.remove(path)
            except Exception:
                pass
    return inlined_bins


def default_gltf_profile_dict():
    return {
        "export_format_ui": "GLB",
        "export_scope": "SELECTION",
        "apply_modifiers": True,
        "export_materials": "EXPORT",
        "check_materials_before_export": True,
        "triangulate_all": True,
        "convert_curves_to_mesh": True,
        "convert_text_to_mesh": True,
        "convert_surfaces_to_mesh": True,
        "convert_meta_to_mesh": True,
        "include_empties": False,
        "include_cameras": False,
        "lights_mode": "ALL",
        "exclude_unsupported_lights": True,
        "export_animations_mode": "AUTO",
        "use_prefix_for_collisions": True,
        "use_property_for_collisions": True,
        "write_collision_manifest": False,
        "unicode_policy": "RAW",
    }


def get_gltf_profiles_dict(prefs):
    try:
        data = json.loads(prefs.gltf_profiles_json) if prefs.gltf_profiles_json else {}
    except Exception:
        data = {}
    if PROFILE_DEFAULT_NAME not in data:
        data[PROFILE_DEFAULT_NAME] = default_gltf_profile_dict()
    return data


def set_gltf_profiles_dict(prefs, data):
    try:
        prefs.gltf_profiles_json = json.dumps(data, indent=2)
    except Exception:
        prefs.gltf_profiles_json = json.dumps({}, indent=2)


def get_gltf_profile_items(self, context):
    data = get_gltf_profiles_dict(self)
    names = sorted(data.keys())
    return [(name, name, "", index) for index, name in enumerate(names)]


def update_gltf_active_profile(self, context):
    self.gltf_active_profile_name = self.gltf_active_profile


def _apply_profile_to_operator(operator, prefs):
    profiles = get_gltf_profiles_dict(prefs)
    profile = profiles.get(prefs.gltf_active_profile_name, profiles[PROFILE_DEFAULT_NAME])
    for key, value in profile.items():
        if hasattr(operator, key):
            try:
                setattr(operator, key, value)
            except Exception:
                pass


def _snapshot_operator_to_profile(operator):
    out = {}
    for key in PROFILE_FIELDS:
        if hasattr(operator, key):
            out[key] = getattr(operator, key)
    return out


class DAT_OP_GltfImport(Operator):
    bl_idname = "dat.import_gltf"
    bl_label = "Import GLTF/GLB"
    bl_description = "Import a GLTF or GLB file for the Dungeon Alchemist pipeline"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(name="File", subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.glb;*.gltf", options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if not self.filepath:
            self.report({"ERROR"}, _t("gltf_no_file_selected", context))
            return {"CANCELLED"}

        try:
            _call_operator_with_supported_properties(bpy.ops.import_scene.gltf, filepath=self.filepath)
        except Exception as exc:
            self.report({"ERROR"}, f"{_t('gltf_import_failed', context)}: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


class DAT_OP_FbxImport(Operator):
    bl_idname = "dat.import_fbx"
    bl_label = "Import FBX"
    bl_description = "Import an FBX file for the Dungeon Alchemist pipeline"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(name="File", subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.fbx", options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if not self.filepath:
            self.report({"ERROR"}, _t("gltf_no_file_selected", context))
            return {"CANCELLED"}

        try:
            _call_operator_with_supported_properties(bpy.ops.import_scene.fbx, filepath=self.filepath)
        except Exception as exc:
            self.report({"ERROR"}, f"{_t('gltf_import_failed', context)}: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


class DAT_OP_StlImport(Operator):
    bl_idname = "dat.import_stl"
    bl_label = "Import STL"
    bl_description = "Import an STL file for the Dungeon Alchemist pipeline"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(name="File", subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.stl", options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if not self.filepath:
            self.report({"ERROR"}, _t("gltf_no_file_selected", context))
            return {"CANCELLED"}

        try:
            _call_first_available_operator(
                ("wm.stl_import", "import_mesh.stl"),
                filepath=self.filepath,
            )
        except Exception as exc:
            self.report({"ERROR"}, f"{_t('gltf_import_failed', context)}: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


class DAT_OP_UsdzImport(Operator):
    bl_idname = "dat.import_usdz"
    bl_label = "Import USDZ"
    bl_description = "Import a USDZ file for the Dungeon Alchemist pipeline"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(name="File", subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.usdz", options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if not self.filepath:
            self.report({"ERROR"}, _t("gltf_no_file_selected", context))
            return {"CANCELLED"}

        try:
            _call_first_available_operator(
                ("wm.usd_import", "import_scene.usd"),
                filepath=self.filepath,
            )
        except Exception as exc:
            self.report({"ERROR"}, f"{_t('gltf_import_failed', context)}: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


class DAT_OP_FbxExport(Operator):
    bl_idname = "dat.export_fbx"
    bl_label = "Export FBX"
    bl_description = "Export selected objects to FBX with DATools export control"
    bl_options = {"REGISTER"}
    export_control_fields = ("check_materials_before_export",)

    filepath: StringProperty(name="File", subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.fbx", options={"HIDDEN"})
    check_materials_before_export: BoolProperty(name="Check Materials Before Export", default=True)
    skip_export_control: BoolProperty(default=False, options={"HIDDEN"})

    def invoke(self, context, event):
        if _warn_for_export_materials_if_needed(self, context, context.selected_objects):
            return {"CANCELLED"}
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        self.layout.prop(self, "check_materials_before_export")

    def execute(self, context):
        if not self.filepath:
            self.report({"ERROR"}, _t("gltf_no_file_selected", context))
            return {"CANCELLED"}
        if _warn_for_export_materials_if_needed(self, context, context.selected_objects):
            return {"CANCELLED"}

        export_path = _ensure_file_extension(self.filepath, ".fbx")
        try:
            result = _call_operator_with_supported_properties(
                bpy.ops.export_scene.fbx,
                filepath=export_path,
                check_existing=True,
                use_selection=True,
                use_visible=False,
                use_active_collection=False,
                global_scale=1.0,
                apply_unit_scale=True,
                apply_scale_options="FBX_SCALE_NONE",
                use_space_transform=True,
                bake_space_transform=False,
                object_types={"LIGHT", "MESH", "ARMATURE", "OTHER"},
                use_mesh_modifiers=True,
                mesh_smooth_type="FACE",
                colors_type="SRGB",
                use_triangles=True,
                path_mode="COPY",
                embed_textures=True,
                batch_mode="OFF",
                axis_forward="-Z",
                axis_up="Y",
            )
            if result != {"FINISHED"}:
                raise RuntimeError("Exporter did not finish successfully")
        except Exception as exc:
            self.report({"ERROR"}, f"{_t('gltf_export_failed', context)}: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, _t("gltf_export_completed", context).format(export_path))
        return {"FINISHED"}


class DAT_OP_StlExport(Operator):
    bl_idname = "dat.export_stl"
    bl_label = "Export STL"
    bl_description = "Export selected objects to STL with DATools export control"
    bl_options = {"REGISTER"}
    export_control_fields = ("check_materials_before_export",)

    filepath: StringProperty(name="File", subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.stl", options={"HIDDEN"})
    check_materials_before_export: BoolProperty(name="Check Materials Before Export", default=True)
    skip_export_control: BoolProperty(default=False, options={"HIDDEN"})

    def invoke(self, context, event):
        if _warn_for_export_materials_if_needed(self, context, context.selected_objects):
            return {"CANCELLED"}
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        self.layout.prop(self, "check_materials_before_export")

    def execute(self, context):
        if not self.filepath:
            self.report({"ERROR"}, _t("gltf_no_file_selected", context))
            return {"CANCELLED"}
        if _warn_for_export_materials_if_needed(self, context, context.selected_objects):
            return {"CANCELLED"}

        export_path = _ensure_file_extension(self.filepath, ".stl")
        try:
            result = _call_first_available_operator(
                ("wm.stl_export", "export_mesh.stl"),
                filepath=export_path,
                use_selection=True,
                global_scale=1.0,
                use_scene_unit=False,
                ascii=False,
                use_mesh_modifiers=True,
                batch_mode="OFF",
                axis_forward="Y",
                axis_up="Z",
            )
            if result != {"FINISHED"}:
                raise RuntimeError("Exporter did not finish successfully")
        except Exception as exc:
            self.report({"ERROR"}, f"{_t('gltf_export_failed', context)}: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, _t("gltf_export_completed", context).format(export_path))
        return {"FINISHED"}


class DAT_OP_GltfToggleCollision(Operator):
    bl_idname = "dat.toggle_collision"
    bl_label = "Toggle Collision"
    bl_description = "Toggle the Dungeon Alchemist collision custom property on selected objects"
    bl_options = {"REGISTER", "UNDO"}

    set_state: EnumProperty(
        name="Set",
        description="Force a specific collision state or toggle it",
        items=[
            ("TOGGLE", "Toggle", "Toggle current state"),
            ("ON", "On", "Set as collision"),
            ("OFF", "Off", "Unset collision"),
        ],
        default="TOGGLE",
    )

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if self.set_state == "ON":
                obj[COLLISION_OBJECT_KEY] = True
            elif self.set_state == "OFF":
                if COLLISION_OBJECT_KEY in obj.keys():
                    del obj[COLLISION_OBJECT_KEY]
            else:
                if obj.get(COLLISION_OBJECT_KEY):
                    del obj[COLLISION_OBJECT_KEY]
                else:
                    obj[COLLISION_OBJECT_KEY] = True
            count += 1

        self.report({"INFO"}, _t("gltf_collision_updated", context).format(count))
        return {"FINISHED"}


class DAT_OP_GltfExport(Operator):
    bl_idname = "dat.export_gltf"
    bl_label = "Export GLTF/GLB"
    bl_description = "Export GLTF or GLB with Dungeon Alchemist collision helpers and DATools profiles"
    bl_options = {"REGISTER"}

    filepath: StringProperty(name="File", subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.glb;*.gltf", options={"HIDDEN"})

    export_format_ui: EnumProperty(
        name="Format",
        items=[
            ("GLB", "GLB (Binary)", "Single-file binary .glb"),
            ("GLTF_SEPARATE", "GLTF + BIN + textures", "JSON with external bin and textures"),
            ("GLTF_EMBEDDED", "GLTF (Embedded)", "JSON with embedded buffer and images"),
        ],
        default="GLB",
    )
    export_scope: EnumProperty(
        name="Scope",
        description="What to include in the export",
        items=[
            ("ALL", "Entire Scene", "Export every object"),
            ("VISIBLE", "Visible Only", "Only objects visible in the current View Layer"),
            ("SELECTION", "Only Selected", "Only currently selected objects"),
        ],
        default="SELECTION",
    )
    apply_modifiers: BoolProperty(name="Apply Modifiers", default=True)
    export_materials: EnumProperty(
        name="Materials",
        items=[
            ("EXPORT", "Export", "Export materials"),
            ("PLACEHOLDER", "Placeholder", "Export empty material slots"),
            ("NONE", "None", "Do not export materials"),
        ],
        default="EXPORT",
    )
    check_materials_before_export: BoolProperty(name="Check Materials Before Export", default=True)
    unicode_policy: EnumProperty(
        name="Unicode",
        description="How to write non-ASCII characters into JSON files",
        items=[
            ("RAW", "Keep UTF-8", "Write characters as-is"),
            ("ASCII", "Strip accents", "Convert accented characters to ASCII"),
        ],
        default="RAW",
    )
    triangulate_all: BoolProperty(name="Triangulate All", default=True)
    convert_curves_to_mesh: BoolProperty(name="Curves to Mesh (temp)", default=True)
    convert_text_to_mesh: BoolProperty(name="Text to Mesh (temp)", default=True)
    convert_surfaces_to_mesh: BoolProperty(name="Surfaces to Mesh (temp)", default=True)
    convert_meta_to_mesh: BoolProperty(name="Metaball to Mesh (temp)", default=True)
    include_empties: BoolProperty(name="Include Empties", default=False)
    include_cameras: BoolProperty(name="Include Cameras", default=False)
    lights_mode: EnumProperty(
        name="Lights",
        items=[
            ("NONE", "Exclude", "Do not export lights"),
            ("SUN_ONLY", "Sun Only", "Export only Sun lights"),
            ("ALL", "All Supported", "Export all supported light types"),
        ],
        default="ALL",
    )
    exclude_unsupported_lights: BoolProperty(name="Exclude Unsupported Area Lights", default=True)
    export_animations_mode: EnumProperty(
        name="Animations",
        items=[
            ("AUTO", "Auto (if present)", "Export animations only if any exist"),
            ("ON", "Export", "Always export animations"),
            ("OFF", "Exclude", "Do not export animations"),
        ],
        default="AUTO",
    )
    use_prefix_for_collisions: BoolProperty(name="Use Prefix for Collisions", default=True)
    use_property_for_collisions: BoolProperty(name="Use Property for Collisions", default=True)
    write_collision_manifest: BoolProperty(name="Write Collision Manifest (.json)", default=False)
    profile_save_as: BoolProperty(name="Save as New Profile", default=False)
    profile_new_name: StringProperty(name="Profile Name", default="")
    skip_export_control: BoolProperty(default=False, options={"HIDDEN"})

    def material_check_objects(self, context):
        if self.export_scope == "SELECTION":
            base_objects = context.selected_objects[:]
        elif self.export_scope == "VISIBLE":
            base_objects = [obj for obj in context.view_layer.objects if obj.visible_get()]
        else:
            base_objects = list(context.view_layer.objects)

        objects = []
        for obj in base_objects:
            obj_type = obj.type
            if obj_type == "CAMERA" and not self.include_cameras:
                continue
            if obj_type == "EMPTY" and not self.include_empties:
                continue
            if obj_type == "LIGHT":
                if self.lights_mode == "NONE":
                    continue
                light_type = getattr(obj.data, "type", None)
                if self.lights_mode == "SUN_ONLY" and light_type != "SUN":
                    continue
                if self.exclude_unsupported_lights and light_type == "AREA":
                    continue
            objects.append(obj)
        return objects

    def invoke(self, context, event):
        prefs = _addon_preferences(context)
        _apply_profile_to_operator(self, prefs)
        if _warn_for_export_materials_if_needed(
            self,
            context,
            self.material_check_objects(context),
            self.use_prefix_for_collisions,
            self.use_property_for_collisions,
        ):
            return {"CANCELLED"}
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        layout = self.layout
        prefs = _addon_preferences(context)

        box = layout.box()
        draw_doc_header(
            box,
            text=_t("gltf_export_options_header", context),
            context=context,
            doc_path=DOC_PATHS["gltf_export_options"],
        )
        box.prop(self, "export_format_ui")
        box.prop(self, "export_scope")
        box.prop(self, "apply_modifiers")
        box.prop(self, "export_materials")
        box.prop(self, "check_materials_before_export")
        box.prop(self, "unicode_policy")

        geo = layout.box()
        draw_doc_header(
            geo,
            text=_t("gltf_geometry_header", context),
            context=context,
            doc_path=DOC_PATHS["gltf_geometry"],
        )
        geo.prop(self, "triangulate_all")
        geo.prop(self, "convert_curves_to_mesh")
        geo.prop(self, "convert_text_to_mesh")
        geo.prop(self, "convert_surfaces_to_mesh")
        geo.prop(self, "convert_meta_to_mesh")

        obj_box = layout.box()
        draw_doc_header(
            obj_box,
            text=_t("gltf_object_types_header", context),
            context=context,
            doc_path=DOC_PATHS["gltf_object_types"],
        )
        obj_box.prop(self, "include_empties")
        obj_box.prop(self, "include_cameras")
        obj_box.prop(self, "lights_mode")
        obj_box.prop(self, "exclude_unsupported_lights")

        anim = layout.box()
        draw_doc_header(
            anim,
            text=_t("gltf_animations_header", context),
            context=context,
            doc_path=DOC_PATHS["gltf_animations"],
        )
        anim.prop(self, "export_animations_mode")

        collisions = layout.box()
        draw_doc_header(
            collisions,
            text=_t("gltf_collision_options_header", context),
            context=context,
            doc_path=DOC_PATHS["gltf_collision_helpers"],
        )
        collisions.prop(self, "use_prefix_for_collisions")
        collisions.label(text=_t("gltf_prefix_status_label", context).format(prefs.gltf_collision_prefix))
        collisions.prop(self, "use_property_for_collisions")
        collisions.prop(self, "write_collision_manifest")
        collisions.label(text=_t("gltf_collision_key_label", context).format(COLLISION_OBJECT_KEY))

        profiles = layout.box()
        draw_doc_header(
            profiles,
            text=_t("gltf_export_profile_header", context),
            context=context,
            doc_path=DOC_PATHS["gltf_export_profiles"],
        )
        profiles.prop(prefs, "gltf_active_profile", text=_t("gltf_active_profile_label", context))
        row = profiles.row(align=True)
        row.prop(self, "profile_save_as")
        row.prop(self, "profile_new_name")
        profiles.label(text=_t("gltf_profile_dialog_hint", context))

    def execute(self, context):
        if not self.filepath:
            self.report({"ERROR"}, _t("gltf_no_file_selected", context))
            return {"CANCELLED"}

        prefs = _addon_preferences(context)
        export_path = _ensure_extension(self.filepath, self.export_format_ui)
        prev_selection = context.selected_objects[:]
        prev_active = context.view_layer.objects.active

        if self.export_scope == "SELECTION":
            base_objects = prev_selection[:]
        elif self.export_scope == "VISIBLE":
            base_objects = [obj for obj in context.view_layer.objects if obj.visible_get()]
        else:
            base_objects = list(context.view_layer.objects)

        if _warn_for_export_materials_if_needed(
            self,
            context,
            self.material_check_objects(context),
            self.use_prefix_for_collisions,
            self.use_property_for_collisions,
        ):
            return {"CANCELLED"}

        depsgraph = context.evaluated_depsgraph_get()
        export_objects = []
        temp_objects = []
        triangulate_modifiers = []

        def create_temp_mesh_from_object(obj):
            try:
                mesh = bpy.data.meshes.new_from_object(
                    obj.evaluated_get(depsgraph),
                    preserve_all_data_layers=True,
                    depsgraph=depsgraph,
                )
            except Exception:
                try:
                    mesh = obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
                except Exception:
                    return None
            if not mesh:
                return None

            new_obj = bpy.data.objects.new(obj.name + "__DAT_GLTF_TEMP", mesh)
            new_obj.matrix_world = obj.matrix_world.copy()
            if obj.get(COLLISION_OBJECT_KEY):
                new_obj[COLLISION_OBJECT_KEY] = True
            for collection in obj.users_collection:
                try:
                    collection.objects.link(new_obj)
                except Exception:
                    pass
            if not new_obj.users_collection:
                try:
                    context.scene.collection.objects.link(new_obj)
                except Exception:
                    pass
            return new_obj

        for obj in base_objects:
            obj_type = obj.type
            if obj_type == "CAMERA" and not self.include_cameras:
                continue
            if obj_type == "EMPTY" and not self.include_empties:
                continue
            if obj_type == "LIGHT":
                if self.lights_mode == "NONE":
                    continue
                light_type = getattr(obj.data, "type", None)
                if self.lights_mode == "SUN_ONLY" and light_type != "SUN":
                    continue
                if self.exclude_unsupported_lights and light_type == "AREA":
                    continue
                export_objects.append(obj)
                continue
            if obj_type == "MESH":
                export_objects.append(obj)
                continue

            will_convert = (
                (obj_type == "CURVE" and self.convert_curves_to_mesh)
                or (obj_type == "FONT" and self.convert_text_to_mesh)
                or (obj_type == "SURFACE" and self.convert_surfaces_to_mesh)
                or (obj_type == "META" and self.convert_meta_to_mesh)
            )
            if will_convert:
                new_obj = create_temp_mesh_from_object(obj)
                if new_obj:
                    temp_objects.append(new_obj)
                    export_objects.append(new_obj)
                continue
            export_objects.append(obj)

        if self.triangulate_all:
            for obj in export_objects:
                if obj.type == "MESH":
                    try:
                        modifier = obj.modifiers.new("DAT_GLTF_TRI", "TRIANGULATE")
                        triangulate_modifiers.append((obj, modifier.name))
                    except Exception:
                        pass

        bpy.ops.object.select_all(action="DESELECT")
        for obj in export_objects:
            try:
                obj.select_set(True)
            except Exception:
                pass
        if export_objects:
            try:
                context.view_layer.objects.active = export_objects[0]
            except Exception:
                pass

        if self.export_animations_mode == "AUTO":
            export_animation_flag = _scene_has_animations(context)
        elif self.export_animations_mode == "ON":
            export_animation_flag = True
        else:
            export_animation_flag = False

        try:
            enum_items = bpy.ops.export_scene.gltf.get_rna_type().properties["export_format"].enum_items.keys()
            supported_formats = {str(key) for key in enum_items}
        except Exception:
            supported_formats = {"GLB", "GLTF_SEPARATE"}

        need_embed_post = False
        if self.export_format_ui == "GLTF_EMBEDDED":
            if "GLTF_EMBEDDED" in supported_formats:
                effective_format = "GLTF_EMBEDDED"
            else:
                effective_format = "GLTF_SEPARATE"
                need_embed_post = True
        else:
            effective_format = self.export_format_ui

        try:
            op_kwargs = {
                "filepath": export_path,
                "export_format": effective_format,
                "use_selection": True,
                "export_apply": self.apply_modifiers,
                "export_materials": self.export_materials,
                "export_extras": True,
                "export_animations": export_animation_flag,
                "export_cameras": self.include_cameras,
                "export_lights": self.lights_mode != "NONE",
            }
            result = _call_operator_with_supported_properties(bpy.ops.export_scene.gltf, **op_kwargs)
            if result != {"FINISHED"}:
                raise RuntimeError("Exporter did not finish successfully")
        except Exception as exc:
            self.report({"ERROR"}, f"{_t('gltf_export_failed', context)}: {exc}")
            return {"CANCELLED"}
        finally:
            for obj, name in triangulate_modifiers:
                try:
                    modifier = obj.modifiers.get(name)
                except Exception:
                    modifier = None
                try:
                    if modifier:
                        obj.modifiers.remove(modifier)
                except Exception:
                    pass

            for temp_obj in temp_objects:
                try:
                    mesh = temp_obj.data
                    bpy.data.objects.remove(temp_obj, do_unlink=True)
                    if mesh and mesh.users == 0:
                        bpy.data.meshes.remove(mesh)
                except Exception:
                    pass

            try:
                bpy.ops.object.select_all(action="DESELECT")
                for obj in prev_selection:
                    try:
                        obj.select_set(True)
                    except Exception:
                        pass
                if prev_active is not None:
                    context.view_layer.objects.active = prev_active
            except Exception:
                pass

        if need_embed_post and export_path.lower().endswith(".gltf"):
            try:
                _embed_external_resources(export_path, delete_bin_after=True)
            except Exception as exc:
                self.report({"WARNING"}, f"{_t('gltf_embed_failed', context)}: {exc}")

        if export_path.lower().endswith(".gltf"):
            try:
                _apply_unicode_policy_to_json_file(export_path, self.unicode_policy)
            except Exception as exc:
                self.report({"WARNING"}, f"{_t('gltf_unicode_failed', context)}: {exc}")

        collisions = []
        manifest_prefix = prefs.gltf_collision_prefix if self.use_prefix_for_collisions else ""
        if self.use_prefix_for_collisions or self.use_property_for_collisions:
            for obj in bpy.data.objects:
                if obj.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
                    continue
                if _is_collision_object(
                    obj,
                    manifest_prefix,
                    self.use_prefix_for_collisions,
                    self.use_property_for_collisions,
                ):
                    collisions.append(obj)

        if self.write_collision_manifest and collisions:
            base, _ = os.path.splitext(export_path)
            manifest_path = base + "_collisions.json"
            payload = []
            for obj in collisions:
                bbox_min, bbox_max = _world_bbox(obj)
                payload.append(
                    {
                        "name": obj.name,
                        "extrasFlag": _is_collision_object(
                            obj,
                            manifest_prefix,
                            self.use_prefix_for_collisions,
                            self.use_property_for_collisions,
                        ),
                        "bboxMin": [bbox_min.x, bbox_min.y, bbox_min.z],
                        "bboxMax": [bbox_max.x, bbox_max.y, bbox_max.z],
                    }
                )
            manifest_data = {
                "collisionPropertyKey": COLLISION_OBJECT_KEY,
                "prefixUsed": manifest_prefix,
                "objects": payload,
            }
            manifest_data = _normalize_json_strings(manifest_data, self.unicode_policy)
            with open(manifest_path, "w", encoding="utf-8") as handle:
                json.dump(manifest_data, handle, indent=2, ensure_ascii=False)

        profiles = get_gltf_profiles_dict(prefs)
        if self.profile_save_as and self.profile_new_name.strip():
            profile_name = self.profile_new_name.strip()
            profiles[profile_name] = _snapshot_operator_to_profile(self)
            set_gltf_profiles_dict(prefs, profiles)
            prefs.gltf_active_profile_name = profile_name
            try:
                prefs.gltf_active_profile = profile_name
            except Exception:
                pass
        else:
            profile_name = prefs.gltf_active_profile_name
            if profile_name not in profiles:
                profile_name = PROFILE_DEFAULT_NAME
                prefs.gltf_active_profile_name = PROFILE_DEFAULT_NAME
            profiles[profile_name] = _snapshot_operator_to_profile(self)
            set_gltf_profiles_dict(prefs, profiles)

        self.report({"INFO"}, _t("gltf_export_completed", context).format(export_path))
        return {"FINISHED"}


class DAT_OP_ExportControlWarning(Operator):
    bl_idname = "dat.export_control_warning"
    bl_label = "Export Warning"
    bl_description = "Warn before exporting materials that may not be supported by Dungeon Alchemist"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        return bpy.ops.wm.call_menu_pie(name=EXPORT_CONTROL_WARNING_PIE_ID)

    def execute(self, context):
        return bpy.ops.wm.call_menu_pie(name=EXPORT_CONTROL_WARNING_PIE_ID)


class DAT_MT_ExportControlWarningPie(Menu):
    bl_idname = EXPORT_CONTROL_WARNING_PIE_ID
    bl_label = "Continue?"

    def draw(self, context):
        layout = self.layout.menu_pie()
        layout.operator("dat.export_control_cancel", text=_t("export_control_cancel_button", context), icon="CANCEL")
        layout.operator("dat.export_control_continue", text=_t("export_control_continue_button", context), icon="CHECKMARK")
        layout.operator("dat.tag_material_warnings", text=_t("export_control_tag_warnings", context), icon="ERROR")

        box = layout.box()
        box.label(text=EXPORT_CONTROL_STATE["warning_title"], icon="ERROR")
        box.label(text=EXPORT_CONTROL_STATE["warning_message"], icon="NODE")
        if EXPORT_CONTROL_STATE["warning_details"]:
            box.label(text=EXPORT_CONTROL_STATE["warning_details"], icon="INFO")
        box.label(text=_t("export_control_continue_hint", context), icon="INFO")

        layout.operator("dat.open_warning_console", text=_t("export_control_open_console", context), icon="CONSOLE")


class DAT_OP_OpenWarningConsole(Operator):
    bl_idname = "dat.open_warning_console"
    bl_label = "Open Console"
    bl_description = "Open or focus the console and print DATools material warnings"
    bl_options = {"REGISTER"}

    def execute(self, context):
        _print_export_control_warning_nodes()

        if _focus_visible_system_console():
            return {"FINISHED"}

        try:
            result = bpy.ops.wm.console_toggle()
        except Exception as exc:
            self.report({"WARNING"}, f"Console unavailable: {exc}")
            return {"CANCELLED"}

        _focus_visible_system_console()
        return result


class DAT_OP_ExportControlContinue(Operator):
    bl_idname = "dat.export_control_continue"
    bl_label = "Continue Export"
    bl_description = "Continue the pending DATools export"
    bl_options = {"REGISTER"}

    def execute(self, context):
        return _continue_pending_export(context, self.report)


class DAT_OP_ExportControlCancel(Operator):
    bl_idname = "dat.export_control_cancel"
    bl_label = "Cancel Export"
    bl_description = "Cancel the pending DATools export"
    bl_options = {"REGISTER"}

    def execute(self, context):
        _clear_export_control_state()
        return {"FINISHED"}


class DAT_OP_TagMaterialWarnings(Operator):
    bl_idname = "dat.tag_material_warnings"
    bl_label = "Tag Warnings"
    bl_description = "Color unsupported material nodes red"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        tagged = 0
        seen = set()
        for node in EXPORT_CONTROL_STATE.get("warning_nodes", []):
            if node is None:
                continue
            try:
                node_id = node.as_pointer()
                if node_id in seen:
                    continue
                seen.add(node_id)
                node.use_custom_color = True
                node.color = (1.0, 0.05, 0.03)
                node.select = True
                if getattr(node, "id_data", None) is not None:
                    node.id_data.nodes.active = node
                tagged += 1
            except ReferenceError:
                continue
            except Exception:
                continue

        if tagged:
            self.report({"INFO"}, _t("export_control_tagged", context).format(tagged))
            return {"FINISHED"}

        self.report({"WARNING"}, _t("export_control_no_nodes_to_tag", context))
        return {"CANCELLED"}


class DAT_OP_GltfProfileDelete(Operator):
    bl_idname = "dat.gltf_profile_delete"
    bl_label = "Delete GLTF Export Profile"
    bl_description = "Delete the active DATools GLTF export profile"
    bl_options = {"REGISTER", "UNDO"}

    profile_name: StringProperty(name="Profile")

    def execute(self, context):
        prefs = _addon_preferences(context)
        profiles = get_gltf_profiles_dict(prefs)
        name = self.profile_name or prefs.gltf_active_profile_name
        if name == PROFILE_DEFAULT_NAME:
            self.report({"WARNING"}, _t("gltf_default_profile_locked", context))
            return {"CANCELLED"}
        if name in profiles:
            del profiles[name]
            set_gltf_profiles_dict(prefs, profiles)
            prefs.gltf_active_profile_name = PROFILE_DEFAULT_NAME
            try:
                prefs.gltf_active_profile = PROFILE_DEFAULT_NAME
            except Exception:
                pass
            self.report({"INFO"}, _t("gltf_profile_deleted", context).format(name))
            return {"FINISHED"}

        self.report({"WARNING"}, _t("gltf_profile_not_found", context).format(name))
        return {"CANCELLED"}


def draw_gltf_io_panel(layout, context):
    prefs = _addon_preferences(context)
    state = context.scene.dat_panel_state
    layout.scale_y = state.submenu_button_scale * state.ui_text_scale

    collision_box = layout.box()
    draw_doc_header(
        collision_box,
        text=_t("gltf_collision_helpers_header", context),
        icon="MOD_PHYSICS",
        context=context,
        doc_path=DOC_PATHS["gltf_collision_helpers"],
    )
    row = collision_box.row(align=True)
    row.operator("dat.toggle_collision", text=_t("gltf_toggle_collision_label", context), icon="FILE_REFRESH").set_state = "TOGGLE"
    row.operator("dat.toggle_collision", text=_t("gltf_collision_on_label", context), icon="CHECKMARK").set_state = "ON"
    row.operator("dat.toggle_collision", text=_t("gltf_collision_off_label", context), icon="X").set_state = "OFF"
    collision_box.prop(prefs, "gltf_collision_prefix", text=_t("gltf_collision_prefix_label", context))
    collision_box.label(text=_t("gltf_collision_key_label", context).format(COLLISION_OBJECT_KEY), icon="INFO")

    actions_box = layout.box()
    draw_doc_header(
        actions_box,
        text=_t("gltf_quick_actions_header", context),
        icon="NETWORK_DRIVE",
        context=context,
        doc_path=DOC_PATHS["io_panel"],
    )
    draw_doc_header(
        actions_box,
        text=_t("dat_imports_header", context),
        icon="IMPORT",
        context=context,
        doc_path=DOC_PATHS["gltf_import"],
    )
    actions_box.operator("dat.import_gltf", text=_t("gltf_import_label", context), icon="IMPORT")
    actions_box.operator("dat.import_fbx", text=_t("fbx_import_label", context), icon="IMPORT")
    actions_box.operator("dat.import_stl", text=_t("stl_import_label", context), icon="IMPORT")
    actions_box.operator("dat.import_usdz", text=_t("usdz_import_label", context), icon="IMPORT")
    draw_doc_header(
        actions_box,
        text=_t("dat_exports_header", context),
        icon="EXPORT",
        context=context,
        doc_path=DOC_PATHS["gltf_export"],
    )
    actions_box.operator("dat.export_gltf", text=_t("gltf_export_label", context), icon="EXPORT")
    actions_box.operator("dat.export_fbx", text=_t("fbx_export_label", context), icon="EXPORT")
    actions_box.operator("dat.export_stl", text=_t("stl_export_label", context), icon="EXPORT")

    profile_box = layout.box()
    draw_doc_header(
        profile_box,
        text=_t("gltf_export_profile_header", context),
        icon="PRESET",
        context=context,
        doc_path=DOC_PATHS["gltf_export_profiles"],
    )
    profile_box.prop(prefs, "gltf_active_profile", text=_t("gltf_active_profile_label", context))
    row = profile_box.row(align=True)
    op = row.operator("dat.gltf_profile_delete", text=_t("gltf_delete_active_profile_label", context), icon="TRASH")
    op.profile_name = prefs.gltf_active_profile_name
    row.enabled = prefs.gltf_active_profile_name != PROFILE_DEFAULT_NAME
    profile_box.label(text=_t("gltf_profile_panel_hint", context))


def draw_gltf_settings(layout, context):
    prefs = _addon_preferences(context)
    box = layout.box()
    draw_doc_header(
        box,
        text=_t("gltf_io_header", context),
        icon="NETWORK_DRIVE",
        context=context,
        doc_path=DOC_PATHS["gltf_io_preferences"],
    )
    box.prop(prefs, "gltf_collision_prefix", text=_t("gltf_collision_prefix_label", context))
    box.prop(prefs, "gltf_active_profile", text=_t("gltf_active_profile_label", context))
    row = box.row(align=True)
    op = row.operator("dat.gltf_profile_delete", text=_t("gltf_delete_active_profile_label", context), icon="TRASH")
    op.profile_name = prefs.gltf_active_profile_name
    row.enabled = prefs.gltf_active_profile_name != PROFILE_DEFAULT_NAME
    box.label(text=_t("gltf_default_profile_locked", context))


def dat_gltf_export_menu(self, context):
    self.layout.operator("dat.export_gltf", text=_t("gltf_export_menu_label", context))


def dat_gltf_import_menu(self, context):
    self.layout.operator("dat.import_gltf", text=_t("gltf_import_menu_label", context))


def dat_fbx_export_menu(self, context):
    self.layout.operator("dat.export_fbx", text=_t("fbx_export_menu_label", context))


def dat_fbx_import_menu(self, context):
    self.layout.operator("dat.import_fbx", text=_t("fbx_import_menu_label", context))


def dat_stl_export_menu(self, context):
    self.layout.operator("dat.export_stl", text=_t("stl_export_menu_label", context))


def dat_stl_import_menu(self, context):
    self.layout.operator("dat.import_stl", text=_t("stl_import_menu_label", context))


def dat_usdz_import_menu(self, context):
    self.layout.operator("dat.import_usdz", text=_t("usdz_import_menu_label", context))
