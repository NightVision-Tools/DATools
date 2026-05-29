import bpy
import json
import os
from collections import namedtuple
from bpy.props import BoolProperty, FloatProperty, PointerProperty, StringProperty

from .. import dictionary
from ..operators.custom_scripts import active_custom_scripts, draw_custom_script, script_icon

DAT_LOGO_ICON = "DAT_Logo"
_preview_collections = {}

# for info -> (identifier, label_key, description_key, icon)
PANEL_ITEMS = (
    ("BLENDER", "menu_blender", "Blender tools", DAT_LOGO_ICON),
    ("TOOLS", "menu_tools", "General operators", "TOOL_SETTINGS"),
    ("TEXTURE", "menu_texture", "Texture tools", "TEXTURE"),
    ("LIGHT", "menu_light", "Lighting tools", "OUTLINER_OB_LIGHT"),
    ("SCRIPT", "menu_script", "Custom scripts", "FILE_SCRIPT"),
    ("IO", "menu_io", "Import and export", "NETWORK_DRIVE"),
    ("SETTINGS", "menu_settings", "DATools settings", "SETTINGS"),
)
PANEL_IDS = [item[0] for item in PANEL_ITEMS]
DEFAULT_PANEL_ID = "TOOLS"
PanelState = namedtuple("PanelState", "identifier label icon selected expanded pinned index")


def register_custom_icons():
    import bpy.utils.previews

    unregister_custom_icons()

    previews = bpy.utils.previews.new()
    icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons", "DAT_Logo.png")
    if os.path.exists(icon_path):
        previews.load(DAT_LOGO_ICON, icon_path, "IMAGE")
    _preview_collections["datools"] = previews


def unregister_custom_icons():
    import bpy.utils.previews

    for previews in _preview_collections.values():
        bpy.utils.previews.remove(previews)
    _preview_collections.clear()


def _get_icon_value(icon):
    previews = _preview_collections.get("datools")
    if previews is None or icon not in previews:
        return 0
    return previews[icon].icon_id


def _operator_with_panel_icon(layout, operator_id, panel, **kwargs):
    icon_value = _get_icon_value(panel.icon)
    if icon_value:
        kwargs["icon_value"] = icon_value
    else:
        kwargs["icon"] = "BLENDER" if panel.icon == DAT_LOGO_ICON else panel.icon
    return layout.operator(operator_id, **kwargs)


def _label_with_panel_icon(layout, text, icon):
    icon_value = _get_icon_value(icon)
    if icon_value:
        layout.label(text=text, icon_value=icon_value)
    else:
        layout.label(text=text, icon="BLENDER" if icon == DAT_LOGO_ICON else icon)


def _draw_section_header(layout, text="", icon="NONE"):
    row = layout.row(align=True)
    row.label(text=text, icon=icon)
    return row


def _draw_axis_tabs(layout, data, prop_name):
    row = layout.row(align=True)
    row.prop(data, prop_name, expand=True)
    return row


def _draw_action_button(layout, operator_id, text, icon="NONE", *, highlight=True, operator_context=None):
    row = layout.row(align=True)
    row.scale_y = 1.12
    if operator_context is not None:
        row.operator_context = operator_context
    return row.operator(operator_id, text=text, icon=icon, depress=highlight)


def _draw_axis_action_section(
    layout,
    data,
    prop_name,
    header_text,
    header_icon,
    operator_id,
    operator_text,
    operator_icon,
):
    box = layout.box()
    _draw_section_header(box, text=header_text, icon=header_icon)
    controls = box.column(align=True)
    _draw_axis_tabs(controls, data, prop_name)
    _draw_action_button(controls, operator_id, operator_text, icon=operator_icon)
    return box


def _draw_vector_props(layout, label, data, prop_names, icon="NONE"):
    box = layout.box()
    header = box.row(align=True)
    header.label(text=label, icon=icon)

    props = box.row(align=True)
    for axis, prop_name in zip(("X", "Y", "Z"), prop_names):
        props.prop(data, prop_name, text=axis)
    return box


def _json_to_dict(value):
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _dict_to_json(value):
    clean = {key: bool(value.get(key, False)) for key in PANEL_IDS if value.get(key, False)}
    return json.dumps(clean, sort_keys=True)


def _expanded_to_json(value):
    clean = {key: bool(value[key]) for key in PANEL_IDS if key in value}
    return json.dumps(clean, sort_keys=True)


def _json_to_list(value, fallback=None):
    fallback = fallback or []
    if not value:
        return list(fallback)
    try:
        data = json.loads(value)
        if isinstance(data, list):
            return [item for item in data if item in PANEL_IDS]
    except Exception:
        pass
    return list(fallback)


def _list_to_json(value):
    clean = []
    for item in value:
        if item in PANEL_IDS and item not in clean:
            clean.append(item)
    if not clean:
        clean = [DEFAULT_PANEL_ID]
    return json.dumps(clean)


def _get_active(state):
    return set(_json_to_list(state.active_panels, [DEFAULT_PANEL_ID]))


def _set_active(state, active):
    ordered = [identifier for identifier in PANEL_IDS if identifier in active]
    state.active_panels = _list_to_json(ordered)


def _update_map_it_from_ui(self, context):
    try:
        from ..operators.map_it import apply_scene_mapping_to_selected

        apply_scene_mapping_to_selected(context)
    except Exception:
        pass


def _get_selected_map_it_material_count(context):
    try:
        from ..operators.map_it import selected_map_it_materials

        return len(selected_map_it_materials(context))
    except Exception:
        return 0


def _draw_tab_content_split(layout, state):
    if state.vertical_tabs and state.show_tab_labels:
        root = layout.split(factor=state.menu_area_width, align=True)
        return root.column(align=False), root.column(align=True)

    if state.vertical_tabs:
        root = layout.row(align=True)
        tab_column = root.column(align=False)
        tab_column.ui_units_x = max(1.6, 2.1 * state.menu_button_scale * state.menu_icon_scale)
        return tab_column, root.column(align=True)

    root = layout.column(align=False)
    return root.row(align=False), root.column(align=True)


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
            "Texture",
            dictionary.translate("menu_texture", context),
            dictionary.translate("menu_texture", context),
            "TEXTURE",
            4,
        ),
        (
            "Light",
            dictionary.translate("menu_light", context),
            dictionary.translate("menu_light", context),
            "OUTLINER_OB_LIGHT",
            5,
        ),
        (
            "Script",
            dictionary.translate("menu_script", context),
            dictionary.translate("menu_script", context),
            "FILE_SCRIPT",
            6,
        ),
        (
            "I/O",
            dictionary.translate("menu_io", context),
            dictionary.translate("menu_io", context),
            "NETWORK_DRIVE",
            8,
        ),
        (
            "Settings",
            dictionary.translate("menu_settings", context),
            dictionary.translate("menu_settings", context),
            "SETTINGS",
            12,
        ),
    ]
    return enum_items


class DAT_MainPanelState(bpy.types.PropertyGroup):
    active_panels: StringProperty(
        name="Active Panels",
        description="Panels currently visible in DATools",
        default='["TOOLS"]',
    )
    expanded_panels: StringProperty(
        name="Expanded Panels",
        description="Collapsed/open state for each panel. Missing values are treated as open.",
        default="{}",
    )
    pinned_panels: StringProperty(
        name="Pinned Panels",
        description="Pinned panels stay visible when another panel is selected.",
        default="{}",
    )
    vertical_tabs: BoolProperty(
        name="Vertical Tabs",
        description="Place selector icons vertically, like a side toolbar",
        default=True,
    )
    shift_multiselect: BoolProperty(
        name="Shift Multiselect",
        description="Use Shift-click to add or remove visible panels",
        default=True,
    )
    show_tab_labels: BoolProperty(
        name="Show Tab Labels",
        description="Show text near the tab icons",
        default=False,
    )
    menu_button_scale: FloatProperty(
        name="Menu Button Size",
        description="Scale the main panel selector buttons",
        default=1.0,
        min=0.7,
        max=2.0,
        soft_min=0.8,
        soft_max=1.6,
    )
    menu_icon_scale: FloatProperty(
        name="Menu Icon Size",
        description="Scale the main menu selector icons",
        default=1.0,
        min=0.7,
        max=2.0,
        soft_min=0.8,
        soft_max=1.6,
    )
    menu_area_width: FloatProperty(
        name="Menu Area Width (Show Tab Labels)",
        description="Portion of the panel width used by the menu selector when tabs are vertical",
        default=0.2,
        min=0.1,
        max=0.6,
        soft_min=0.15,
        soft_max=0.45,
        subtype="FACTOR",
    )
    submenu_button_scale: FloatProperty(
        name="Submenu Button Size",
        description="Scale the expandable submenu header buttons",
        default=1.0,
        min=0.7,
        max=2.0,
        soft_min=0.8,
        soft_max=1.6,
    )
    ui_text_scale: FloatProperty(
        name="Text / Row Size",
        description="Scale text-bearing rows. Blender panels do not expose independent font size.",
        default=1.0,
        min=0.8,
        max=1.6,
        soft_min=0.9,
        soft_max=1.3,
    )
    show_script_names: BoolProperty(
        name="Show Script Names",
        description="Show custom script titles inside the Script panel",
        default=True,
    )
    show_script_icons: BoolProperty(
        name="Show Script Icons",
        description="Show custom script icons inside the Script panel",
        default=True,
    )
    align_script_buttons: BoolProperty(
        name="Align Script Buttons",
        description="Draw custom script controls in aligned rows",
        default=False,
    )


class DAT_OT_MainPanelSelect(bpy.types.Operator):
    bl_idname = "dat.main_panel_select"
    bl_label = "Select DATools Panel"
    bl_description = "Select, multi-select or pin a DATools panel"

    panel_id: StringProperty(default="")

    def execute(self, context):
        state = context.scene.dat_panel_state
        pinned = _json_to_dict(state.pinned_panels)
        active = {identifier for identifier in PANEL_IDS if pinned.get(identifier, False)}
        active.add(self.panel_id)
        _set_active(state, active)
        return {"FINISHED"}

    def invoke(self, context, event):
        state = context.scene.dat_panel_state
        active = _get_active(state)
        pinned = _json_to_dict(state.pinned_panels)
        is_pinned = bool(pinned.get(self.panel_id, False))

        if event.ctrl:
            pinned[self.panel_id] = not is_pinned
            if not is_pinned:
                active.add(self.panel_id)
            state.pinned_panels = _dict_to_json(pinned)
        else:
            use_multi = event.shift if state.shift_multiselect else not event.shift

            if use_multi:
                if self.panel_id in active:
                    if len(active) > 1 and not is_pinned:
                        active.remove(self.panel_id)
                else:
                    active.add(self.panel_id)
            else:
                active = {identifier for identifier in PANEL_IDS if pinned.get(identifier, False)}
                active.add(self.panel_id)

        _set_active(state, active)
        return {"FINISHED"}


class DAT_OT_MainPanelExpand(bpy.types.Operator):
    bl_idname = "dat.main_panel_expand"
    bl_label = "Expand DATools Panel"
    bl_description = "Expand or collapse a DATools panel"

    panel_id: StringProperty(default="")
    expanded: BoolProperty(default=True)

    def execute(self, context):
        state = context.scene.dat_panel_state
        expanded = _json_to_dict(state.expanded_panels)

        if self.panel_id:
            expanded[self.panel_id] = self.expanded
        else:
            for identifier in _get_active(state):
                expanded[identifier] = self.expanded

        state.expanded_panels = _expanded_to_json(expanded)
        return {"FINISHED"}


class DAT_OT_MainPanelPin(bpy.types.Operator):
    bl_idname = "dat.main_panel_pin"
    bl_label = "Pin DATools Panel"
    bl_description = "Pin or unpin a DATools panel"

    panel_id: StringProperty(default="")
    pinned: BoolProperty(default=False)

    def execute(self, context):
        state = context.scene.dat_panel_state
        pinned = _json_to_dict(state.pinned_panels)
        active = _get_active(state)

        pinned[self.panel_id] = self.pinned
        if self.pinned:
            active.add(self.panel_id)

        state.pinned_panels = _dict_to_json(pinned)
        _set_active(state, active)
        return {"FINISHED"}


class DAT_OT_MainPanelPreviewHello(bpy.types.Operator):
    bl_idname = "dat.main_panel_preview_hello"
    bl_label = "Dummy"
    bl_description = "Preview dummy action"

    def execute(self, context):
        self.report({"INFO"}, "Hello There!")
        return {"FINISHED"}


def _draw_tools_panel(layout, context):
    layout.operator_context = 'EXEC_DEFAULT'
    state = context.scene.dat_panel_state
    layout.scale_y = state.submenu_button_scale * state.ui_text_scale
    scene = context.scene
    # --- Scale It ---
    _draw_axis_action_section(
        layout,
        scene,
        "dat_scale",
        "Scale Axis",
        "MOD_SCATTER_ON_SURFACE",
        "dat.scale_it",
        dictionary.translate("scale_it_label", context),
        "MOD_SCATTER_ON_SURFACE",
    )

    # --- Mirror It ---
    _draw_axis_action_section(
        layout,
        scene,
        "dat_mirror",
        "Mirror Axis",
        "MOD_MIRROR",
        "dat.mirror_it",
        dictionary.translate("mirror_it_label", context),
        "MOD_MIRROR",
    )

    # --- Shrink It ---
    box = layout.box()
    _draw_section_header(box, icon="MOD_DECIM")
    controls = box.column(align=True)
    controls.prop(scene, "dat_shrinkpercentage")
    _draw_action_button(
        controls,
        "dat.shrink_it",
        dictionary.translate("shrink_it_label", context),
        icon="MOD_DECIM",
    )

    # --- Floor It ---
    box = layout.box()
    _draw_section_header(box, icon="CON_FLOOR")
    _draw_action_button(
        box,
        "dat.floor_it",
        dictionary.translate("floor_it_label", context),
        icon="CON_FLOOR",
    )
    

def _draw_settings_panel(layout, context):
    state = context.scene.dat_panel_state
    layout.prop(state, "vertical_tabs")
    layout.prop(state, "shift_multiselect")
    layout.prop(state, "show_tab_labels")
    layout.prop(state, "menu_area_width")
    layout.prop(state, "menu_button_scale")
    layout.prop(state, "menu_icon_scale")
    layout.prop(state, "submenu_button_scale")
    layout.prop(state, "ui_text_scale")
    script_box = layout.box()
    script_box.label(text=dictionary.translate("custom_scripts_running_header", context), icon="FILE_SCRIPT")
    script_box.prop(state, "show_script_names")
    script_box.prop(state, "show_script_icons")
    script_box.prop(state, "align_script_buttons", toggle=True)
    _draw_settings_preview(layout, context)


def _draw_settings_preview(layout, context):
    state = context.scene.dat_panel_state
    box = layout.box()
    box.label(text="Preview", icon="HIDE_OFF")

    menu_col, content_col = _draw_tab_content_split(box, state)

    preview_tabs = (
        ("TOOL_SETTINGS", True),
        ("NETWORK_DRIVE", False),
        ("SETTINGS", False),
    )
    for index, (icon, selected) in enumerate(preview_tabs):
        row = menu_col.row(align=True)
        row.scale_x = state.menu_button_scale * state.menu_icon_scale
        row.scale_y = state.menu_button_scale * state.menu_icon_scale * state.ui_text_scale
        row.alert = selected
        row.label(text="DAT" if state.show_tab_labels else "", icon=icon)
        if index < len(preview_tabs) - 1:
            menu_col.separator()

    header = content_col.row(align=True)
    header.scale_y = state.submenu_button_scale * state.ui_text_scale
    header.label(text="Tools", icon="TRIA_DOWN")
    header.separator()
    header.label(text="", icon="UNPINNED")

    sample = content_col.box()
    sample.scale_y = state.submenu_button_scale * state.ui_text_scale
    sample.label(text="Mapping Settings", icon="FORCE_TEXTURE")
    sample.label(text="Location X  0.000")
    sample.label(text="Scale X  1.000")
    _draw_action_button(sample, "dat.main_panel_preview_hello", text="Dummy", icon="PLAY")

def _draw_texture_panel(layout, context):
    state = context.scene.dat_panel_state
    layout.scale_y = state.submenu_button_scale * state.ui_text_scale
    scene = context.scene

    # --- Rez It ---
    box = layout.box()
    _draw_section_header(box, icon="NODE_TEXTURE")
    controls = box.column(align=True)
    controls.prop(scene, "dat_textureresolution")
    rez_op = _draw_action_button(
        controls,
        "dat.rez_it",
        dictionary.translate("rez_it_label", context),
        icon="NODE_TEXTURE",
        operator_context="EXEC_DEFAULT",
    )
    rez_op.texture_resolution = int(scene.dat_textureresolution)

    # --- Map It ---
    box = layout.box()
    box.label(icon="FORCE_TEXTURE", text="Mapping Settings")
    mapped_count = _get_selected_map_it_material_count(context)
    if mapped_count:
        box.label(text=dictionary.translate("map_it_live_label", context).format(mapped_count), icon="LINKED")
    _draw_vector_props(
        box,
        "Location",
        scene,
        ("dat_location_x", "dat_location_y", "dat_location_z"),
        icon="EMPTY_ARROWS",
    )
    _draw_vector_props(
        box,
        "Rotation",
        scene,
        ("dat_rotation_x", "dat_rotation_y", "dat_rotation_z"),
        icon="DRIVER_ROTATIONAL_DIFFERENCE",
    )
    _draw_vector_props(
        box,
        "Scale",
        scene,
        ("dat_scale_x", "dat_scale_y", "dat_scale_z"),
        icon="FULLSCREEN_ENTER",
    )
    map_op = _draw_action_button(
        box,
        "dat.map_it",
        dictionary.translate("map_it_label", context),
        icon="FORCE_TEXTURE",
        operator_context="EXEC_DEFAULT",
    )
    map_op.location_x = float(scene.dat_location_x)
    map_op.location_y = float(scene.dat_location_y)
    map_op.location_z = float(scene.dat_location_z)
    map_op.rotation_x = float(scene.dat_rotation_x)
    map_op.rotation_y = float(scene.dat_rotation_y)
    map_op.rotation_z = float(scene.dat_rotation_z)
    map_op.scale_x = float(scene.dat_scale_x)
    map_op.scale_y = float(scene.dat_scale_y)
    map_op.scale_z = float(scene.dat_scale_z)


def _draw_light_panel(layout, context):
    state = context.scene.dat_panel_state
    layout.scale_y = state.submenu_button_scale * state.ui_text_scale

    box = layout.box()
    box.label(text=dictionary.translate("light_add_label", context), icon="OUTLINER_OB_LIGHT")

    row = box.row(align=True)
    op = row.operator(
        "object.light_add",
        text=dictionary.translate("light_point_label", context),
        icon="LIGHT_POINT",
        depress=True,
    )
    op.type = "POINT"
    op = row.operator(
        "object.light_add",
        text=dictionary.translate("light_sun_label", context),
        icon="LIGHT_SUN",
        depress=True,
    )
    op.type = "SUN"

    row = box.row(align=True)
    op = row.operator(
        "object.light_add",
        text=dictionary.translate("light_spot_label", context),
        icon="LIGHT_SPOT",
        depress=True,
    )
    op.type = "SPOT"
    op = row.operator(
        "object.light_add",
        text=dictionary.translate("light_area_label", context),
        icon="LIGHT_AREA",
        depress=True,
    )
    op.type = "AREA"

    active = context.object
    box = layout.box()
    if active is None or active.type != "LIGHT":
        box.label(text=dictionary.translate("light_no_active_label", context), icon="INFO")
        return

    light = active.data
    box.label(text=dictionary.translate("light_selected_label", context), icon="OUTLINER_OB_LIGHT")
    box.prop(light, "type")
    box.prop(light, "color")
    box.prop(light, "energy")

    if hasattr(light, "shadow_soft_size"):
        box.prop(light, "shadow_soft_size")
    if hasattr(light, "angle"):
        box.prop(light, "angle")
    if hasattr(light, "size"):
        box.prop(light, "size")
    if hasattr(light, "spot_size"):
        box.prop(light, "spot_size")
    if hasattr(light, "spot_blend"):
        box.prop(light, "spot_blend")


def _draw_script_panel(layout, context):
    state = context.scene.dat_panel_state
    layout.scale_y = state.submenu_button_scale * state.ui_text_scale

    box = layout.box()
    box.label(text=dictionary.translate("custom_scripts_running_header", context), icon="FILE_SCRIPT")

    scripts = active_custom_scripts(context)
    if not scripts:
        box.label(text=dictionary.translate("custom_scripts_empty_active", context), icon="INFO")
        return

    script_column = box.column(align=state.align_script_buttons)
    for item in scripts:
        script_box = script_column.column(align=state.align_script_buttons) if state.align_script_buttons else script_column.box()
        show_title = state.show_script_names and getattr(item, "show_title", True)
        show_icon = state.show_script_icons and getattr(item, "show_icon", True)
        if show_title:
            script_box.label(text=item.name, icon=script_icon(item) if show_icon else "NONE")
        elif show_icon:
            script_box.label(text="", icon=script_icon(item))
        draw_custom_script(script_box, context, item)


def _draw_panel_content(layout, context, identifier):
    col = layout.column(align=True)

    if identifier == "TOOLS":
        _draw_tools_panel(col, context)
    elif identifier == "SETTINGS":
        _draw_settings_panel(col, context)
    elif identifier == "BLENDER":
        _label_with_panel_icon(col, dictionary.translate("menu_blender", context), DAT_LOGO_ICON)
    elif identifier == "IO":
        col.label(text=dictionary.translate("menu_io", context), icon="NETWORK_DRIVE")
    elif identifier == "TEXTURE":
        _draw_texture_panel(col, context)
    elif identifier == "LIGHT":
        _draw_light_panel(col, context)
    elif identifier == "SCRIPT":
        _draw_script_panel(col, context)


class DAT_3DV_MainPanel(bpy.types.Panel):
    bl_label = "DATools"
    bl_idname = "DAT_3DV_MainPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DAT"
    bl_order = 0

    def draw_header_preset(self, context):
        state = context.scene.dat_panel_state
        active = _get_active(state)
        expanded = _json_to_dict(state.expanded_panels)
        visible = [identifier for identifier in PANEL_IDS if identifier in active]
        any_open = any(expanded.get(identifier, True) for identifier in visible)

        op = self.layout.operator(
            "dat.main_panel_expand",
            text="",
            icon="DISCLOSURE_TRI_DOWN" if any_open else "DISCLOSURE_TRI_RIGHT",
        )
        op.panel_id = ""
        op.expanded = not any_open

    def draw(self, context):
        layout = self.layout
        state = context.scene.dat_panel_state
        active = _get_active(state)
        expanded = _json_to_dict(state.expanded_panels)
        pinned = _json_to_dict(state.pinned_panels)

        panels = [
            PanelState(
                identifier,
                dictionary.translate(label_key, context),
                icon,
                identifier in active,
                expanded.get(identifier, True),
                bool(pinned.get(identifier, False)),
                index,
            )
            for index, (identifier, label_key, _description, icon) in enumerate(PANEL_ITEMS)
        ]

        tab_column, content_column = _draw_tab_content_split(layout, state)
        tab_column.operator_context = 'INVOKE_DEFAULT'
        content_column.operator_context = 'EXEC_DEFAULT'

        for index, panel in enumerate(panels):
            row = tab_column.row(align=True)
            row.operator_context = 'INVOKE_DEFAULT'
            row.scale_x = state.menu_button_scale * state.menu_icon_scale
            row.scale_y = state.menu_button_scale * state.menu_icon_scale * state.ui_text_scale
            row.alert = panel.pinned
            op = _operator_with_panel_icon(
                row,
                "dat.main_panel_select",
                panel,
                text=panel.label if state.show_tab_labels else "",
                depress=panel.selected,
                emboss=panel.selected,
            )
            op.panel_id = panel.identifier
            if index < len(panels) - 1:
                tab_column.separator()

        for panel in panels:
            if not panel.selected:
                continue

            box = content_column.box()
            header = box.row(align=True)
            header.scale_y = state.submenu_button_scale * state.ui_text_scale

            op = header.operator(
                "dat.main_panel_expand",
                text=panel.label,
                icon="TRIA_DOWN" if panel.expanded else "TRIA_RIGHT",
                emboss=False,
            )
            op.panel_id = panel.identifier
            op.expanded = not panel.expanded

            header.separator()
            pin = header.operator(
                "dat.main_panel_pin",
                text="",
                icon="PINNED" if panel.pinned else "UNPINNED",
                emboss=False,
            )
            pin.panel_id = panel.identifier
            pin.pinned = not panel.pinned

            if panel.expanded:
                _draw_panel_content(box, context, panel.identifier)



def register_scene_properties():
    bpy.types.Scene.dat_panel_state = PointerProperty(type=DAT_MainPanelState)
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
    bpy.types.Scene.dat_location_x = bpy.props.FloatProperty(
        name=dictionary.translate("map_it_location_x_label"),
        description=dictionary.translate("map_it_location_description"),
        default=0.0,
        update=_update_map_it_from_ui,
    )
    bpy.types.Scene.dat_location_y = bpy.props.FloatProperty(
        name=dictionary.translate("map_it_location_y_label"),
        description=dictionary.translate("map_it_location_description"),
        default=0.0,
        update=_update_map_it_from_ui,
    )
    bpy.types.Scene.dat_location_z = bpy.props.FloatProperty(
        name=dictionary.translate("map_it_location_z_label"),
        description=dictionary.translate("map_it_location_description"),
        default=0.0,
        update=_update_map_it_from_ui,
    )
    bpy.types.Scene.dat_rotation_x = bpy.props.FloatProperty(
        name=dictionary.translate("map_it_rotation_x_label"),
        description=dictionary.translate("map_it_rotation_description"),
        default=0.0,
        subtype="ANGLE",
        update=_update_map_it_from_ui,
    )
    bpy.types.Scene.dat_rotation_y = bpy.props.FloatProperty(
        name=dictionary.translate("map_it_rotation_y_label"),
        description=dictionary.translate("map_it_rotation_description"),
        default=0.0,
        subtype="ANGLE",
        update=_update_map_it_from_ui,
    )
    bpy.types.Scene.dat_rotation_z = bpy.props.FloatProperty(
        name=dictionary.translate("map_it_rotation_z_label"),
        description=dictionary.translate("map_it_rotation_description"),
        default=0.0,
        subtype="ANGLE",
        update=_update_map_it_from_ui,
    )
    bpy.types.Scene.dat_scale_x = bpy.props.FloatProperty(
        name=dictionary.translate("map_it_scale_x_label"),
        description=dictionary.translate("map_it_scale_description"),
        default=1.0,
        update=_update_map_it_from_ui,
    )
    bpy.types.Scene.dat_scale_y = bpy.props.FloatProperty(
        name=dictionary.translate("map_it_scale_y_label"),
        description=dictionary.translate("map_it_scale_description"),
        default=1.0,
        update=_update_map_it_from_ui,
    )
    bpy.types.Scene.dat_scale_z = bpy.props.FloatProperty(
        name=dictionary.translate("map_it_scale_z_label"),
        description=dictionary.translate("map_it_scale_description"),
        default=1.0,
        update=_update_map_it_from_ui,
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
