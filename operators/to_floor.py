import bpy

from .. import dictionary


class DAT_OP_ToFloor(bpy.types.Operator):
    bl_idname = "dat.to_floor"
    bl_label = dictionary.translate("to_floor_label")
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return any(obj.type == "MESH" for obj in context.selected_objects)
    
    @classmethod
    def description(cls, context, properties):
        return dictionary.description("to_floor_description", context)

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type != "MESH" or not obj.data.vertices:
                continue
            lowest_z = min((obj.matrix_world @ vert.co).z for vert in obj.data.vertices)
            obj.location.z -= lowest_z
        self.report({"INFO"}, dictionary.translate("snapped_to_floor", context))
        return {"FINISHED"}
