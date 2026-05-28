import bpy


from .. import dictionary

class DAT_OP_ShrinkIt(bpy.types.Operator):
    bl_idname = "dat.shrink_it"
    bl_label = dictionary.translate("shrink_it_label")
    bl_description = dictionary.translate("shrink_it_description")
    bl_options = {"REGISTER", "UNDO"}
    
    shrink_percentage: bpy.props.IntProperty(
        name=dictionary.translate("shrink_it_percentage_label"),
        description=dictionary.translate("shrink_it_percentage_description"),
        default=50,
        min=1,
        max=100,
    )
    shrink_mode: bpy.props.EnumProperty(
        name=dictionary.translate("shrink_it_mode_label"),
        description=dictionary.translate("shrink_it_mode_description"),
        items=[
            ("KEEP", dictionary.translate("shrink_it_mode_keep_label"), "Keep duplicates and leave originals"),
            ("REPLACE", dictionary.translate("shrink_it_mode_replace_label"), "Replace originals with decimated duplicates"),
        ],
        default="KEEP",
    )
    shrink_apply_modifiers: bpy.props.BoolProperty(
        name=dictionary.translate("shrink_it_apply_modifiers_label"),
        description=dictionary.translate("shrink_it_apply_modifiers_description"),
        default=False,
    )
    shrink_select_result: bpy.props.BoolProperty(
        name=dictionary.translate("shrink_it_select_result_label"),
        description=dictionary.translate("shrink_it_select_result_description"),
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and any(obj.type == "MESH" for obj in context.selected_objects)
        )

    @classmethod
    def description(cls, context, properties):
        return dictionary.description("shrink_it_description", context)

    def invoke(self, context, event):
        self.shrink_percentage = int(getattr(context.scene, "dat_shrinkpercentage", 50))
        self.shrink_mode = getattr(context.scene, "dat_shrink_mode", "KEEP")
        self.shrink_apply_modifiers = bool(getattr(context.scene, "dat_shrink_apply_modifiers", False))
        self.shrink_select_result = bool(getattr(context.scene, "dat_shrink_select_result", True))
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "shrink_percentage")
        layout.prop(self, "shrink_mode")
        layout.prop(self, "shrink_apply_modifiers")
        layout.prop(self, "shrink_select_result")

    def execute(self, context):
        try:
            percentage = int(self.shrink_percentage)
        except Exception:
            percentage = int(getattr(context.scene, "dat_shrinkpercentage", 50))
        if percentage < 1 or percentage > 100:
            self.report({"WARNING"}, dictionary.translate("shrink_it_invalid_percentage", context))
            return {"CANCELLED"}

        # resolve operator properties falling back to scene properties when called without invoke()
        mode = getattr(self, "shrink_mode", None)
        if not isinstance(mode, str) or mode not in ("KEEP", "REPLACE"):
            mode = getattr(context.scene, "dat_shrink_mode", "KEEP")
        apply_mods = getattr(self, "shrink_apply_modifiers", None)
        if not isinstance(apply_mods, bool):
            apply_mods = bool(getattr(context.scene, "dat_shrink_apply_modifiers", False))
        select_result = getattr(self, "shrink_select_result", None)
        if not isinstance(select_result, bool):
            select_result = bool(getattr(context.scene, "dat_shrink_select_result", True))

        selected_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not selected_meshes:
            self.report({"WARNING"}, dictionary.translate("shrink_it_no_mesh", context))
            return {"CANCELLED"}

        original_selection = list(context.selected_objects)
        original_names = [obj.name for obj in original_selection]
        original_active_name = getattr(context.view_layer.objects.active, "name", None)
        duplicated_objects = []
        original_to_dup = {}

        for source in selected_meshes:
            dup = source.copy()
            dup.data = source.data.copy()
            dup["dat_shrink"] = True
            # link to same collections or scene collection
            linked = False
            for collection in source.users_collection:
                collection.objects.link(dup)
                linked = True
            if not linked:
                context.scene.collection.objects.link(dup)
            dup.name = f"{source.name}_Shrink"
            duplicated_objects.append(dup)
            original_to_dup[source.name] = dup

        for obj in original_selection:
            obj.select_set(False)
        for dup in duplicated_objects:
            dup.select_set(True)

        context.view_layer.objects.active = duplicated_objects[-1] if duplicated_objects else None
        ratio = percentage / 100.0

        for dup in duplicated_objects:
            context.view_layer.objects.active = dup
            # optionally apply existing modifiers first
            if apply_mods:
                for m in list(dup.modifiers):
                    try:
                        bpy.ops.object.modifier_apply(modifier=m.name)
                    except Exception:
                        pass
            modifier = dup.modifiers.new(name="DAT_Shrink", type="DECIMATE")
            modifier.decimate_type = "COLLAPSE"
            modifier.ratio = ratio
            try:
                bpy.ops.object.modifier_apply(modifier=modifier.name)
            except Exception:
                pass

        # Handle replace mode: delete originals and rename duplicates to original names
        if mode == "REPLACE":
            for orig_name, dup in original_to_dup.items():
                src = bpy.data.objects.get(orig_name)
                # remove original object if present
                if src is not None:
                    try:
                        bpy.data.objects.remove(src, do_unlink=True)
                    except Exception:
                        pass
                    # rename dup to original name
                try:
                    dup.name = orig_name
                except Exception:
                    pass

        # Restore original selection: select originals if still present, otherwise select corresponding duplicates
        for obj in list(context.scene.objects):
            obj.select_set(False)

        for name in original_names:
            if name in bpy.data.objects:
                bpy.data.objects[name].select_set(True)
            else:
                dup = original_to_dup.get(name)
                if dup and dup.name in bpy.data.objects and select_result:
                    bpy.data.objects[dup.name].select_set(True)

        # Restore active object
        active_name = original_active_name
        if active_name and active_name in bpy.data.objects:
            context.view_layer.objects.active = bpy.data.objects[active_name]
        else:
            # try to set to last duplicated if selection wants result
            if select_result and duplicated_objects:
                context.view_layer.objects.active = duplicated_objects[-1]
            else:
                context.view_layer.objects.active = None

        # persist scene properties
        context.scene.dat_shrinkpercentage = int(percentage)
        context.scene.dat_shrink_mode = mode
        context.scene.dat_shrink_apply_modifiers = bool(apply_mods)
        context.scene.dat_shrink_select_result = bool(select_result)

        self.report({"INFO"}, dictionary.translate("shrink_it_completed", context))
        return {"FINISHED"}
