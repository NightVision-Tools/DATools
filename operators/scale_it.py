import bpy

from .. import dictionary

class DAT_OP_ScaleIt(bpy.types.Operator):
    bl_idname = "dat.scale_it"
    bl_label = "Scale It"
    bl_description = "Scale the non-active selected objects using the active object dimensions"
    bl_options = {"REGISTER", "UNDO"}

    scale_axis: bpy.props.EnumProperty(
        name=dictionary.translate("scale_it_axis_label"),
        description=dictionary.translate("scale_it_axis_description"),
        items=[
            ("X", "X", "Scale to the X", 0, 0),
            ("Y", "Y", "Scale to the Y", 0, 1),
            ("Z", "Z", "Scale to the Z", 0, 2),
        ],
        default="X",
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and len(context.selected_objects) == 2 and context.object is not None

    def invoke(self, context, event):
        self.scale_axis = getattr(context.scene, "dat_scale", "X")
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "scale_axis")

    def execute(self, context):
        active = context.view_layer.objects.active
        selected = [obj for obj in context.selected_objects if obj != active]
        if not active or not selected:
            self.report({"WARNING"}, "Select two objects; the active object is used as reference")
            return {"CANCELLED"}
        target = selected[0]
        axis = getattr(self, "scale_axis", None)
        if not isinstance(axis, str) or axis not in ("X", "Y", "Z"):
            axis = getattr(context.scene, "dat_scale", "X")
        axis_index = {"X": 0, "Y": 1, "Z": 2}[axis]
        source_dim = active.dimensions[axis_index]
        target_dim = target.dimensions[axis_index]
        if target_dim == 0:
            self.report({"ERROR"}, "Cannot scale because target dimension is zero")
            return {"CANCELLED"}
        scale_factor = source_dim / target_dim

        original_selected = list(context.selected_objects)
        for obj in original_selected:
            obj.select_set(False)
        target.select_set(True)
        context.view_layer.objects.active = target

        bpy.ops.transform.resize(value=(scale_factor, scale_factor, scale_factor))

        for obj in original_selected:
            obj.select_set(True)
        context.view_layer.objects.active = active

        context.scene.dat_scalebuffer = scale_factor
        context.scene.dat_activeobjectbuffer = target
        context.scene.dat_scale = axis
        return {"FINISHED"}
    
def register_scene_properties():
    bpy.types.Scene.dat_activeobjectbuffer = bpy.props.PointerProperty(
        name="ActiveObjectBuffer",
        type=bpy.types.Object,
    )
    bpy.types.Scene.dat_scalebuffer = bpy.props.FloatProperty(
        name="ScaleBuffer",
        default=0.0,
        precision=6,
    )
    bpy.types.Scene.dat_scale = bpy.props.EnumProperty(
        name="Axis",
        description="Choose which axis should be used to scale the object",
        items=[
            ("X", "X", "Scale to the X", 0, 0),
            ("Y", "Y", "Scale to the Y", 0, 1),
            ("Z", "Z", "Scale to the Z", 0, 2),
        ],
    )

def unregister_scene_properties():
    for prop in (
        "dat_activeobjectbuffer",
        "dat_scalebuffer",
        "dat_scale",
    ):
        if hasattr(bpy.types.Scene, prop):
                delattr(bpy.types.Scene, prop)
