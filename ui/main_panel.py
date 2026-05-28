import bpy
import json
from collections import namedtuple
from bpy.props import BoolProperty, PointerProperty, StringProperty

from .. import dictionary


PANEL_ITEMS = (
    ("BLENDER", "menu_blender", "Blender tools", "BLENDER"),
    ("TOOLS", "menu_tools", "DATools operators", "TOOL_SETTINGS"),
    ("IO", "menu_io", "Import and export", "NETWORK_DRIVE"),
    ("SETTINGS", "menu_settings", "DATools settings", "SETTINGS"),
)
PANEL_IDS = [item[0] for item in PANEL_ITEMS]
DEFAULT_PANEL_ID = "TOOLS"
PanelState = namedtuple("PanelState", "identifier label icon selected expanded pinned index")


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


def _draw_tools_panel(layout, context):
    layout.operator_context = 'EXEC_DEFAULT'
    scene = context.scene
    layout.operator("dat.floor_it", text=dictionary.translate("floor_it_label", context))
    layout.prop(scene, "dat_scale", expand=True)
    layout.operator("dat.scale_it", text=dictionary.translate("scale_it_label", context))
    layout.prop(scene, "dat_shrinkpercentage")
    layout.operator("dat.shrink_it", text=dictionary.translate("shrink_it_label", context))
    layout.prop(scene, "dat_mirror", expand=True)
    layout.operator("dat.mirror_it", text=dictionary.translate("mirror_it_label", context))
    layout.prop(scene, "dat_textureresolution")
    layout.operator("dat.rez_it", text=dictionary.translate("rez_it_label", context))


def _draw_settings_panel(layout, context):
    state = context.scene.dat_panel_state
    layout.prop(state, "vertical_tabs")
    layout.prop(state, "shift_multiselect")
    layout.prop(state, "show_tab_labels")


def _draw_panel_content(layout, context, identifier):
    col = layout.column(align=True)

    if identifier == "TOOLS":
        _draw_tools_panel(col, context)
    elif identifier == "SETTINGS":
        _draw_settings_panel(col, context)
    elif identifier == "BLENDER":
        col.label(text=dictionary.translate("menu_blender", context), icon="BLENDER")
    elif identifier == "IO":
        col.label(text=dictionary.translate("menu_io", context), icon="NETWORK_DRIVE")


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

        root = layout.row(align=False) if state.vertical_tabs else layout.column(align=False)
        tab_column = root.column(align=True) if state.vertical_tabs else root.row(align=True)
        content_column = root.column(align=True)
        tab_column.operator_context = 'INVOKE_DEFAULT'
        content_column.operator_context = 'EXEC_DEFAULT'

        for panel in panels:
            row = tab_column.row(align=True)
            row.operator_context = 'INVOKE_DEFAULT'
            row.alert = panel.pinned
            op = row.operator(
                "dat.main_panel_select",
                text=panel.label if state.show_tab_labels else "",
                icon=panel.icon,
                depress=panel.selected,
            )
            op.panel_id = panel.identifier

        for panel in panels:
            if not panel.selected:
                continue

            box = content_column.box()
            header = box.row(align=True)

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
    bpy.types.Scene.dat_scalebuffer = bpy.props.FloatProperty(
        name=dictionary.translate("dat_scalebuffer_label"),
        default=0.0,
        precision=6,
    )
    bpy.types.Scene.dat_activeobjectbuffer = bpy.props.PointerProperty(
        name=dictionary.translate("dat_activeobjectbuffer_label"),
        type=bpy.types.Object,
    )
