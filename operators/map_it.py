import bpy

from .. import dictionary


MAPPING_NODE_NAME = "DAT_MapIt_Mapping"
TEXCOORD_NODE_NAME = "DAT_MapIt_TextureCoordinate"


def get_map_it_mapping_node(material):
    if material is None or not material.use_nodes or material.node_tree is None:
        return None

    for node in material.node_tree.nodes:
        if node.type == "MAPPING" and (node.name == MAPPING_NODE_NAME or node.label == "DAT Map It"):
            return node
    return None


def selected_map_it_materials(context):
    materials = []
    seen = set()

    for obj in getattr(context, "selected_objects", []):
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            material = slot.material
            if material is None or material.name in seen:
                continue
            if get_map_it_mapping_node(material) is not None:
                materials.append(material)
                seen.add(material.name)

    return materials


def apply_scene_mapping_to_selected(context):
    scene = context.scene
    values = {
        "Location": (
            float(getattr(scene, "dat_location_x", 0.0)),
            float(getattr(scene, "dat_location_y", 0.0)),
            float(getattr(scene, "dat_location_z", 0.0)),
        ),
        "Rotation": (
            float(getattr(scene, "dat_rotation_x", 0.0)),
            float(getattr(scene, "dat_rotation_y", 0.0)),
            float(getattr(scene, "dat_rotation_z", 0.0)),
        ),
        "Scale": (
            float(getattr(scene, "dat_scale_x", 1.0)),
            float(getattr(scene, "dat_scale_y", 1.0)),
            float(getattr(scene, "dat_scale_z", 1.0)),
        ),
    }

    updated = 0
    for material in selected_map_it_materials(context):
        mapping = get_map_it_mapping_node(material)
        if mapping is None:
            continue
        set_mapping_values(mapping, values)
        updated += 1
    return updated


def set_mapping_values(mapping, values):
    for input_name, vector in values.items():
        socket = mapping.inputs.get(input_name)
        if socket is not None:
            socket.default_value[0] = float(vector[0])
            socket.default_value[1] = float(vector[1])
            socket.default_value[2] = float(vector[2])


class DAT_OP_MapIt(bpy.types.Operator):
    bl_idname = "dat.map_it"
    bl_label = dictionary.translate("map_it_label")
    bl_description = dictionary.translate("map_it_description")
    bl_options = {"REGISTER", "UNDO"}

    location_x: bpy.props.FloatProperty(name="Location X", default=0.0)
    location_y: bpy.props.FloatProperty(name="Location Y", default=0.0)
    location_z: bpy.props.FloatProperty(name="Location Z", default=0.0)
    rotation_x: bpy.props.FloatProperty(name="Rotation X", default=0.0, subtype="ANGLE")
    rotation_y: bpy.props.FloatProperty(name="Rotation Y", default=0.0, subtype="ANGLE")
    rotation_z: bpy.props.FloatProperty(name="Rotation Z", default=0.0, subtype="ANGLE")
    scale_x: bpy.props.FloatProperty(name="Scale X", default=1.0)
    scale_y: bpy.props.FloatProperty(name="Scale Y", default=1.0)
    scale_z: bpy.props.FloatProperty(name="Scale Z", default=1.0)

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and any(obj.type == "MESH" for obj in context.selected_objects)
        )

    @classmethod
    def description(cls, context, properties):
        return dictionary.description("map_it_description", context)

    def invoke(self, context, event):
        scene = context.scene
        self.location_x = float(getattr(scene, "dat_location_x", 0.0))
        self.location_y = float(getattr(scene, "dat_location_y", 0.0))
        self.location_z = float(getattr(scene, "dat_location_z", 0.0))
        self.rotation_x = float(getattr(scene, "dat_rotation_x", 0.0))
        self.rotation_y = float(getattr(scene, "dat_rotation_y", 0.0))
        self.rotation_z = float(getattr(scene, "dat_rotation_z", 0.0))
        self.scale_x = float(getattr(scene, "dat_scale_x", 1.0))
        self.scale_y = float(getattr(scene, "dat_scale_y", 1.0))
        self.scale_z = float(getattr(scene, "dat_scale_z", 1.0))
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "location_x")
        layout.prop(self, "location_y")
        layout.prop(self, "location_z")
        layout.prop(self, "rotation_x")
        layout.prop(self, "rotation_y")
        layout.prop(self, "rotation_z")
        layout.prop(self, "scale_x")
        layout.prop(self, "scale_y")
        layout.prop(self, "scale_z")

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not selected_meshes:
            self.report({"WARNING"}, dictionary.translate("map_it_no_mesh", context))
            return {"CANCELLED"}

        mapped_materials = set()
        mapped_textures = 0

        for obj in selected_meshes:
            for slot in obj.material_slots:
                material = slot.material
                if material is None:
                    continue
                mapped_textures += self._map_material(material, mapped_materials)

        if mapped_textures == 0:
            self.report({"WARNING"}, dictionary.translate("map_it_no_textures", context))
            return {"CANCELLED"}

        scene = context.scene
        scene.dat_location_x = float(self.location_x)
        scene.dat_location_y = float(self.location_y)
        scene.dat_location_z = float(self.location_z)
        scene.dat_rotation_x = float(self.rotation_x)
        scene.dat_rotation_y = float(self.rotation_y)
        scene.dat_rotation_z = float(self.rotation_z)
        scene.dat_scale_x = float(self.scale_x)
        scene.dat_scale_y = float(self.scale_y)
        scene.dat_scale_z = float(self.scale_z)

        self.report({"INFO"}, dictionary.translate("map_it_completed", context))
        return {"FINISHED"}

    def _map_material(self, material, mapped_materials):
        if material.name in mapped_materials:
            return 0

        material.use_nodes = True
        node_tree = material.node_tree
        if node_tree is None:
            return 0

        nodes = node_tree.nodes
        links = node_tree.links
        image_nodes = [node for node in nodes if node.type == "TEX_IMAGE"]
        if not image_nodes:
            return 0

        mapping = self._get_or_create_node(
            nodes,
            node_type="MAPPING",
            bl_idname="ShaderNodeMapping",
            name=MAPPING_NODE_NAME,
            label="DAT Map It",
            location=(-450, 150),
        )
        texcoord = self._get_or_create_node(
            nodes,
            node_type="TEX_COORD",
            bl_idname="ShaderNodeTexCoord",
            name=TEXCOORD_NODE_NAME,
            label="DAT Texture Coordinates",
            location=(-650, 150),
        )

        self._set_mapping_values(mapping)
        self._link_texture_coordinates(links, texcoord, mapping)

        mapped_count = 0
        mapping_output = mapping.outputs.get("Vector")
        if mapping_output is None:
            return 0

        for image_node in image_nodes:
            vector_input = image_node.inputs.get("Vector")
            if vector_input is None:
                continue
            for link in list(vector_input.links):
                links.remove(link)
            links.new(mapping_output, vector_input)
            mapped_count += 1

        if mapped_count:
            mapped_materials.add(material.name)
        return mapped_count

    def _get_or_create_node(self, nodes, node_type, bl_idname, name, label, location):
        for node in nodes:
            if node.type == node_type and (node.name == name or node.label == label):
                return node

        node = nodes.new(type=bl_idname)
        node.name = name
        node.label = label
        node.location = location
        return node

    def _set_mapping_values(self, mapping):
        values = {
            "Location": (self.location_x, self.location_y, self.location_z),
            "Rotation": (self.rotation_x, self.rotation_y, self.rotation_z),
            "Scale": (self.scale_x, self.scale_y, self.scale_z),
        }
        set_mapping_values(mapping, values)

    def _link_texture_coordinates(self, links, texcoord, mapping):
        vector_input = mapping.inputs.get("Vector")
        if vector_input is None:
            return
        for link in list(vector_input.links):
            links.remove(link)

        vector_output = texcoord.outputs.get("UV") or texcoord.outputs.get("Generated")
        if vector_output is not None:
            links.new(vector_output, vector_input)
