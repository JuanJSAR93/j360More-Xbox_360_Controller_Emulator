"""
plugins/plugin_i18n.py
Multi-language / Internationalization engine for j360More plugins.
Provides transparent localization for plugin manifests, configuration dialogs,
custom pad tabs, dynamic controls, labels, and descriptions.
"""

import copy
import json
import os
from typing import Any, Dict, List, Optional, Union


SUPPORTED_LANG_CODES = ("es", "en", "fr", "pt_BR", "de", "it", "ru")


def normalize_lang_code(lang: str) -> str:
    """Normalizes language code (e.g. 'es_ES' -> 'es', 'pt-br' -> 'pt_BR')."""
    if not lang:
        return "es"
    clean = lang.replace("-", "_").strip()
    if clean.lower() in ("pt_br", "pt-br"):
        return "pt_BR"
    if "_" in clean:
        base = clean.split("_")[0].lower()
        if base in ("es", "en", "fr", "de", "it", "ru", "pt"):
            return "pt_BR" if base == "pt" else base
    return clean.lower()


def localize_text(
    val: Any,
    lang: str = "es",
    default_lang: str = "es",
    locales: Optional[Dict[str, Dict[str, str]]] = None
) -> str:
    """
    Localizes a value that can be:
    - A localized dictionary: {"es": "Texto", "en": "Text", "fr": "Texte", ...}
    - A string key matching a locale entry in locales/{lang}.json
    - A plain string or number
    """
    if val is None:
        return ""

    norm_lang = normalize_lang_code(lang)
    norm_def = normalize_lang_code(default_lang)

    # 1. If val is a dictionary of language translations
    if isinstance(val, dict):
        # Check exact language (e.g. 'pt_BR' or 'es')
        if norm_lang in val:
            return str(val[norm_lang])
        # Check lower/upper variants
        for k, v in val.items():
            if normalize_lang_code(k) == norm_lang:
                return str(v)
        # Check language prefix (e.g. 'pt' for 'pt_BR')
        lang_prefix = norm_lang.split("_")[0]
        if lang_prefix in val:
            return str(val[lang_prefix])
        for k, v in val.items():
            if normalize_lang_code(k).split("_")[0] == lang_prefix:
                return str(v)
        # Fallback to default_lang
        if norm_def in val:
            return str(val[norm_def])
        for k, v in val.items():
            if normalize_lang_code(k) == norm_def:
                return str(v)
        # Fallback to 'en' or 'es'
        if "en" in val:
            return str(val["en"])
        if "es" in val:
            return str(val["es"])
        # Return first available value
        for v in val.values():
            return str(v)
        return ""

    val_str = str(val)

    # 2. If locales dictionary is provided, check if val_str is a translation key
    if locales:
        key = val_str[1:] if val_str.startswith(("$", "@")) else val_str
        lang_dict = locales.get(norm_lang) or locales.get(norm_lang.split("_")[0]) or {}
        if key in lang_dict:
            return str(lang_dict[key])
        def_dict = locales.get(norm_def) or locales.get("es") or locales.get("en") or {}
        if key in def_dict:
            return str(def_dict[key])

    return val_str


def localize_list(
    items: Any,
    lang: str = "es",
    default_lang: str = "es",
    locales: Optional[Dict[str, Dict[str, str]]] = None
) -> List[Any]:
    """Localizes a list of items or a localized dictionary of lists."""
    if isinstance(items, dict):
        # e.g. {"es": ["GAS", "FRENO"], "en": ["GAS", "BRAKE"]}
        loc_val = localize_text(items, lang=lang, default_lang=default_lang, locales=locales)
        if isinstance(loc_val, list):
            return loc_val
        # If localize_text returned string from dict, check if the chosen value was a list
        norm_lang = normalize_lang_code(lang)
        if norm_lang in items and isinstance(items[norm_lang], list):
            return items[norm_lang]
        if "es" in items and isinstance(items["es"], list):
            return items["es"]
        if "en" in items and isinstance(items["en"], list):
            return items["en"]
        for v in items.values():
            if isinstance(v, list):
                return v
        return [loc_val]

    if isinstance(items, (list, tuple)):
        result = []
        for it in items:
            if isinstance(it, dict) and any(k in SUPPORTED_LANG_CODES for k in it.keys()):
                result.append(localize_text(it, lang=lang, default_lang=default_lang, locales=locales))
            else:
                result.append(it)
        return result

    return [items] if items is not None else []


def localize_ui_definition(
    ui_def: Dict[str, Any],
    lang: str = "es",
    default_lang: str = "es",
    locales: Optional[Dict[str, Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Returns a deep copy of a UI specification (global_ui or pad_ui_customization)
    with all titles, section names, field labels, option text, and progress bar labels
    localized to the target language.
    """
    if not ui_def:
        return {}

    cloned = copy.deepcopy(ui_def)

    # 1. Localize root titles
    if "title" in cloned:
        cloned["title"] = localize_text(cloned["title"], lang, default_lang, locales)

    # 2. Localize fields in global_ui
    if "fields" in cloned and isinstance(cloned["fields"], list):
        for f in cloned["fields"]:
            _localize_field(f, lang, default_lang, locales)

    # 3. Localize custom tabs in pad_ui_customization
    if "custom_tabs" in cloned and isinstance(cloned["custom_tabs"], list):
        for tab in cloned["custom_tabs"]:
            if "title" in tab:
                tab["title"] = localize_text(tab["title"], lang, default_lang, locales)
            if "label" in tab:
                tab["label"] = localize_text(tab["label"], lang, default_lang, locales)

            if "sections" in tab and isinstance(tab["sections"], list):
                for sec in tab["sections"]:
                    if "name" in sec:
                        sec["name"] = localize_text(sec["name"], lang, default_lang, locales)
                    if "fields" in sec and isinstance(sec["fields"], list):
                        for f in sec["fields"]:
                            _localize_field(f, lang, default_lang, locales)

            if "fields" in tab and isinstance(tab["fields"], list):
                for f in tab["fields"]:
                    _localize_field(f, lang, default_lang, locales)

    return cloned


def _localize_field(field: Dict[str, Any], lang: str, default_lang: str, locales: Optional[Dict[str, Dict[str, str]]]):
    """Helper to translate labels, options, and progress bar labels on a field."""
    if "label" in field:
        field["label"] = localize_text(field["label"], lang, default_lang, locales)

    if "labels" in field:
        field["labels"] = localize_list(field["labels"], lang, default_lang, locales)

    if "options" in field and isinstance(field["options"], list):
        new_opts = []
        for opt in field["options"]:
            if isinstance(opt, dict):
                # e.g. {"value": "AUTO", "label": {"es": "Automático", "en": "Automatic"}}
                lbl = opt.get("label", opt.get("value", ""))
                new_opts.append(localize_text(lbl, lang, default_lang, locales))
            else:
                new_opts.append(localize_text(opt, lang, default_lang, locales))
        field["options"] = new_opts


def load_plugin_locales(plugin_dir: str) -> Dict[str, Dict[str, str]]:
    """
    Scans <plugin_dir>/locales/*.json and loads all language dictionaries.
    Example files:
        <plugin_dir>/locales/es.json
        <plugin_dir>/locales/en.json
        <plugin_dir>/locales/fr.json
        <plugin_dir>/locales/pt_BR.json
    """
    locales: Dict[str, Dict[str, str]] = {}
    locales_dir = os.path.join(plugin_dir, "locales")
    if not os.path.isdir(locales_dir):
        return locales

    for fname in os.listdir(locales_dir):
        if fname.endswith(".json"):
            lang_code = normalize_lang_code(fname[:-5])
            full_path = os.path.join(locales_dir, fname)
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        locales[lang_code] = {str(k): str(v) for k, v in data.items()}
            except Exception:
                pass

    return locales
