import bpy

from .languages import english, french, german, italian

ADDON_MODULE = __package__ or "DATools"

LANGUAGE_MODULES = {
    "ENGLISH": english.strings,
    "ITALIAN": italian.strings,
    "GERMAN": german.strings,
    "FRENCH": french.strings,
}
LANGUAGE_LOCALES = {
    "ENGLISH": "en_US",
    "ITALIAN": "it_IT",
    "GERMAN": "de_DE",
    "FRENCH": "fr_FR",
}
DEFAULT_LANGUAGE = "ENGLISH"

KEY_TO_MSGID = {key: english.strings[key] for key in english.strings}


def get_language_items(self=None, context=None):
    return [
        (
            "ENGLISH",
            LANGUAGE_MODULES["ENGLISH"]["language_name"],
            LANGUAGE_MODULES["ENGLISH"]["language_description"],
            "WORLD",
            0,
        ),
        (
            "ITALIAN",
            LANGUAGE_MODULES["ITALIAN"]["language_name"],
            LANGUAGE_MODULES["ITALIAN"]["language_description"],
            "WORLD",
            1,
        ),
        (
            "GERMAN",
            LANGUAGE_MODULES["GERMAN"]["language_name"],
            LANGUAGE_MODULES["GERMAN"]["language_description"],
            "WORLD",
            2,
        ),
        (
            "FRENCH",
            LANGUAGE_MODULES["FRENCH"]["language_name"],
            LANGUAGE_MODULES["FRENCH"]["language_description"],
            "WORLD",
            3,
        ),
    ]


def get_addon(context=None):
    if context is None:
        context = bpy.context

    candidates = []
    for candidate in (ADDON_MODULE, "DATools"):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    package_suffix = "." + ADDON_MODULE if ADDON_MODULE else ""
    for candidate in candidates:
        addon = context.preferences.addons.get(candidate)
        if addon is not None:
            return addon

    for addon_key in context.preferences.addons.keys():
        addon = context.preferences.addons.get(addon_key)
        if addon is None:
            continue
        if addon_key == ADDON_MODULE or addon_key == "DATools":
            return addon
        if package_suffix and addon_key.endswith(package_suffix):
            return addon
        if addon_key.endswith(".DATools"):
            return addon

    return None


def get_addon_preferences(context=None):
    addon = get_addon(context)
    if addon is None:
        return None
    return addon.preferences


def set_addon_module(module_name):
    global ADDON_MODULE
    if module_name:
        ADDON_MODULE = module_name


def get_language(context=None):
    prefs = get_addon_preferences(context)
    if prefs is None:
        return DEFAULT_LANGUAGE
    if getattr(prefs, "language", None) in LANGUAGE_MODULES:
        return prefs.language
    return DEFAULT_LANGUAGE


def get_strings(context=None):
    return LANGUAGE_MODULES.get(get_language(context), LANGUAGE_MODULES[DEFAULT_LANGUAGE])


def get_language_display(language_code):
    return LANGUAGE_MODULES.get(language_code, LANGUAGE_MODULES[DEFAULT_LANGUAGE])["language_name"]


def get_translation_dict():
    translations = {}
    for lang_code, strings in ((LANGUAGE_LOCALES[key], LANGUAGE_MODULES[key]) for key in LANGUAGE_LOCALES):
        locale_dict = {}
        for msg_key, msgid in KEY_TO_MSGID.items():
            translation = strings.get(msg_key)
            if translation is not None and translation != msgid:
                locale_dict[("*", msgid)] = translation
        if locale_dict:
            translations[lang_code] = locale_dict
    return translations


def register_translations():
    bpy.app.translations.register(ADDON_MODULE, get_translation_dict())


def unregister_translations():
    bpy.app.translations.unregister(ADDON_MODULE)


def translate(key, context=None) -> str:
    msgid = KEY_TO_MSGID.get(key, key)
    return bpy.app.translations.pgettext(msgid)


def description(key, context=None) -> str:
    msgid = KEY_TO_MSGID.get(key, key)
    return bpy.app.translations.pgettext_tip(msgid)
