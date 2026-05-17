import bpy


class DAT_OP_ToFloor(bpy.types.Operator):
    bl_idname = "dat.to_floor"
    bl_label = "To Floor"
    bl_description = "Move selected meshes to the floor"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return any(obj.type == "MESH" for obj in context.selected_objects)
    
    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type != "MESH" or not obj.data.vertices:
                continue
            lowest_z = min((obj.matrix_world @ vert.co).z for vert in obj.data.vertices)
            obj.location.z -= lowest_z
        self.report({"INFO"}, "Snapped To Floor")
        return {"FINISHED"}
