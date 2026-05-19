import bpy


class DAT_OP_Mirrorit(bpy.types.Operator):
    bl_idname = "dat.mirror_it"
    bl_label = "Mirror It!"
    bl_description = "Mirror selected objects based on the chosen axis"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        return any(obj.type == "MESH" for obj in context.selected_objects)

    def execute(self, context):
        mesh_objects = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not mesh_objects:
            self.report({"WARNING"}, "No mesh selected")
            return {"CANCELLED"}

        old_pivot = context.tool_settings.transform_pivot_point
        old_selection = list(context.selected_objects)
        old_active = context.view_layer.objects.active

        for obj in old_selection:
            obj.select_set(False)
        for obj in mesh_objects:
            obj.select_set(True)

        context.view_layer.objects.active = mesh_objects[0]
        context.tool_settings.transform_pivot_point = "INDIVIDUAL_ORIGINS"

        axis = context.scene.dat_mirror
        bpy.ops.transform.mirror(
            constraint_axis=(axis == "X", axis == "Y", axis == "Z")
        )

        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        for mesh_obj in mesh_objects:
            context.view_layer.objects.active = mesh_obj
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.normals_make_consistent()
            bpy.ops.object.mode_set(mode="OBJECT")

        context.tool_settings.transform_pivot_point = old_pivot

        for obj in old_selection:
            obj.select_set(True)
        context.view_layer.objects.active = old_active

        self.report({"INFO"}, "MIRROR IT! Completed")
        return {"FINISHED"}
    
