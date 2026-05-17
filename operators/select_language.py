import bpy

from .. import dictionary


class DAT_OP_SelectLanguage(bpy.types.Operator):
    bl_idname = "dat.select_language"
    bl_label = "Select DATools Language"
    bl_description = "Change the active DATools language"
    bl_options = {"REGISTER"}

    language = bpy.props.EnumProperty(
        name="Language",
        items=dictionary.get_language_items,
        default="ENGLISH",
    )

    def execute(self, context):
        addon = context.preferences.addons.get(dictionary.ADDON_MODULE)
        if addon is None:
            self.report({"ERROR"}, "Addon preferences not found")
            return {"CANCELLED"}

        prefs = addon.preferences
        prefs.language = self.language
        language_locale = dictionary.LANGUAGE_LOCALES.get(self.language)
        if language_locale:
            context.preferences.view.language = language_locale

        self.report(
            {"INFO"},
            dictionary.translate("selected_language_text", context).format(
                dictionary.get_language_display(self.language)
            ),
        )
        return {"FINISHED"}
