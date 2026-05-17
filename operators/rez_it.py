import bpy
from math import ceil


class DAT_OP_RezIt(bpy.types.Operator):
    bl_idname = "dat.rez_it"
    bl_label = "Texture Resize"
    bl_description = "Resize textures of selected objects to the desired resolution"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        return any(obj.type == "MESH" for obj in context.selected_objects)
    def execute(self, context):
        resolution = int(context.scene.dat_textureresolution)
        selected_objects = [obj for obj in context.selected_objects if obj.type == "MESH"]
        processed_materials = set()
        processed_textures = set()
        original_to_duplicate = {}
        original_to_resized = {}
        def get_existing_resize_material(original_material_name, resolution):
            prefix = f"Resize_{resolution}_"
            for material in bpy.data.materials:
                if material.name.startswith(prefix) and material.name[len(prefix):] == original_material_name:
                    return material
            return None
        def get_existing_resize_texture(original_texture_name, resolution):
            prefix = f"Resize_{resolution}_"
            for texture in bpy.data.images:
                if texture.name.startswith(prefix) and texture.name[len(prefix):] == original_texture_name:
                    return texture
            return None
        for obj in selected_objects:
            for slot in obj.material_slots:
                original_material = slot.material
                if original_material is None:
                    continue
                original_material_name = original_material.name
                new_material = get_existing_resize_material(original_material_name, resolution)
                if original_material_name not in processed_materials:
                    if not new_material:
                        new_material = original_material.copy()
                        new_material.name = f"Resize_{resolution}_{original_material_name}"
                    original_material.use_fake_user = True
                    processed_materials.add(original_material_name)
                else:
                    new_material = bpy.data.materials.get(f"Resize_{resolution}_{original_material_name}", original_material)
                slot.material = new_material
                original_to_duplicate[original_material.name] = new_material.name
        for obj in selected_objects:
            for slot in obj.material_slots:
                material = slot.material
                if material is None or not material.use_nodes or not material.node_tree:
                    continue
                for node in material.node_tree.nodes:
                    if node.type != "TEX_IMAGE":
                        continue
                    original_texture = node.image
                    if original_texture is None:
                        continue
                    original_texture_name = original_texture.name
                    if original_texture_name in processed_textures:
                        existing = get_existing_resize_texture(original_texture_name, resolution)
                        if existing:
                            node.image = existing
                        continue
                    existing_texture = get_existing_resize_texture(original_texture_name, resolution)
                    if existing_texture:
                        node.image = existing_texture
                        processed_textures.add(original_texture_name)
                        continue
                    if original_texture.packed_file:
                        try:
                            original_texture.unpack()
                        except Exception:
                            pass
                    new_texture = original_texture.copy()
                    new_texture.name = f"Resize_{resolution}_{original_texture_name}"
                    width, height = original_texture.size
                    if width <= 0 or height <= 0:
                        continue
                    new_width = new_height = resolution
                    if width > height:
                        new_height = ceil(height * (float(resolution) / width))
                    elif width < height:
                        new_width = ceil(width * (float(resolution) / height))
                    new_texture.scale(int(new_width), int(new_height))
                    node.image = new_texture
                    processed_textures.add(original_texture_name)
                    original_to_resized[original_texture.filepath] = new_texture.name
        print("Original Material to Duplicated Material:")
        print(original_to_duplicate)
        print("Original Texture to Resized Texture:")
        print(original_to_resized)
        self.report({"INFO"}, "Texture resize completed")
        return {"FINISHED"}