import bpy

from .. import dictionary


class DAT_OP_FloorIt(bpy.types.Operator):
    bl_idname = "dat.floor_it"
    bl_label = dictionary.translate("floor_it_label")
    bl_description = "Move selected mesh objects to the floor (Z=0) based on their lowest vertex"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return any(obj.type == "MESH" for obj in context.selected_objects)
    
    @classmethod
    def description(cls, context, properties):
        return dictionary.description("floor_it_description", context)

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type != "MESH" or not obj.data.vertices:
                continue
            lowest_z = min((obj.matrix_world @ vert.co).z for vert in obj.data.vertices)
            obj.location.z -= lowest_z
        self.report({"INFO"}, dictionary.translate("snapped_floor_it", context))
        return {"FINISHED"}
