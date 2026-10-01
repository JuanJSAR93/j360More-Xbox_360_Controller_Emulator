"""
plugins/tests/test_plugin_i18n.py
Comprehensive test suite for plugin multi-language and internationalization support.
"""

import sys
import os
import tkinter as tk
from tkinter import ttk

# Add repository root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from plugins.plugin_i18n import (
    localize_text,
    localize_list,
    localize_ui_definition,
    load_plugin_locales,
    normalize_lang_code
)
from plugins.plugin_manager import PluginManager
from plugins.plugin_ui_renderer import PluginUIRenderer


def test_i18n_core_functions():
    print("[1] Testing core plugin_i18n normalization and localization...")

    # Language code normalization
    assert normalize_lang_code("es") == "es"
    assert normalize_lang_code("es_ES") == "es"
    assert normalize_lang_code("en-US") == "en"
    assert normalize_lang_code("pt_br") == "pt_BR"
    assert normalize_lang_code("pt-BR") == "pt_BR"

    # Localize text from dictionary
    d = {
        "es": "Acelerador",
        "en": "Throttle",
        "fr": "Accélérateur",
        "pt_BR": "Acelerador (PT)"
    }
    assert localize_text(d, "es") == "Acelerador"
    assert localize_text(d, "en") == "Throttle"
    assert localize_text(d, "fr") == "Accélérateur"
    assert localize_text(d, "pt_BR") == "Acelerador (PT)"
    # Fallback to base or default
    assert localize_text(d, "de") == "Acelerador"  # default_lang='es'

    # Localize list of strings or dictionary of lists
    list_dict = {
        "es": ["GAS", "FRENO", "EMBRAGUE"],
        "en": ["THROTTLE", "BRAKE", "CLUTCH"]
    }
    assert localize_list(list_dict, "es") == ["GAS", "FRENO", "EMBRAGUE"]
    assert localize_list(list_dict, "en") == ["THROTTLE", "BRAKE", "CLUTCH"]

    print("    [OK] Core localization passed.")


def test_plugin_instance_i18n():
    print("[2] Testing PluginInstance loading and locale parsing...")
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    mgr = PluginManager(base_dir=root_dir)
    mgr.scan_plugins()

    assert "midi_controller" in mgr.plugins, "midi_controller should be discovered"
    assert "arduino_pedals" in mgr.plugins, "arduino_pedals should be discovered"

    midi = mgr.plugins["midi_controller"]
    pedals = mgr.plugins["arduino_pedals"]

    # Verify localized names
    assert midi.get_name("es") == "Controlador de Teclado/Pads MIDI"
    assert midi.get_name("en") == "MIDI Keyboard/Pad Controller"
    assert midi.get_name("fr") == "Contrôleur de Clavier/Pads MIDI"
    assert midi.get_name("de") == "MIDI-Tastatur/Pad-Controller"

    assert pedals.get_name("es") == "Pedales Arduino USB"
    assert pedals.get_name("en") == "Arduino USB Pedals"

    # Verify localized descriptions
    assert "Convierte cualquier teclado" in midi.get_description("es")
    assert "Converts any MIDI musical keyboard" in midi.get_description("en")

    # Verify localized pad UI
    pad_ui_es = midi.get_pad_ui("es")
    pad_ui_en = midi.get_pad_ui("en")

    assert pad_ui_es["custom_tabs"][0]["title"] == "🎹 Calibración MIDI"
    assert pad_ui_en["custom_tabs"][0]["title"] == "🎹 MIDI Calibration"

    # Verify section names
    sec_es = pad_ui_es["custom_tabs"][0]["sections"][0]["name"]
    sec_en = pad_ui_en["custom_tabs"][0]["sections"][0]["name"]
    assert sec_es == "Sensibilidad y Respuesta"
    assert sec_en == "Sensitivity & Response"

    # Verify field labels & progress bar labels
    fields_es = pad_ui_es["custom_tabs"][0]["sections"][1]["fields"][0]
    fields_en = pad_ui_en["custom_tabs"][0]["sections"][1]["fields"][0]
    assert fields_es["labels"] == ["VELOCIDAD", "PITCH BEND", "MODULACIÓN"]
    assert fields_en["labels"] == ["VELOCITY", "PITCH BEND", "MODULATION"]

    print("    [OK] PluginInstance localization passed.")


def test_plugin_ui_renderer_i18n():
    print("[3] Testing PluginUIRenderer rendering with target languages...")
    root = tk.Tk()
    root.withdraw()

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    mgr = PluginManager(base_dir=root_dir)
    mgr.scan_plugins()
    midi = mgr.plugins["midi_controller"]

    frame_es = ttk.Frame(root)
    pad_ui_es = midi.get_pad_ui("es")
    fields_es = pad_ui_es["custom_tabs"][0]["sections"][1]["fields"]
    refs_es = PluginUIRenderer.render_fields(frame_es, fields_es, {}, lang="es", locales=midi.locales)
    assert refs_es["midi_telemetry"]["labels"] == ["VELOCIDAD", "PITCH BEND", "MODULACIÓN"]

    frame_en = ttk.Frame(root)
    pad_ui_en = midi.get_pad_ui("en")
    fields_en = pad_ui_en["custom_tabs"][0]["sections"][1]["fields"]
    refs_en = PluginUIRenderer.render_fields(frame_en, fields_en, {}, lang="en", locales=midi.locales)
    assert refs_en["midi_telemetry"]["labels"] == ["VELOCITY", "PITCH BEND", "MODULATION"]

    # Render telemetry and test text
    PluginUIRenderer.update_telemetry_widget(refs_en["midi_telemetry"], [0.8, 0.5, 0.3])
    canvas = refs_en["midi_telemetry"]["widget"]
    items = canvas.find_all()
    texts = [canvas.itemcget(i, "text") for i in items if canvas.type(i) == "text"]
    assert any("VELOCITY 80%" in t for t in texts), f"Expected VELOCITY in texts: {texts}"
    assert any("MODULATION 30%" in t for t in texts), f"Expected MODULATION in texts: {texts}"

    root.destroy()
    print("    [OK] PluginUIRenderer rendering with i18n passed.")


def test_manager_get_plugins_info_i18n():
    print("[4] Testing PluginManager.get_plugins_info and get_available_devices i18n...")
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    mgr = PluginManager(base_dir=root_dir)
    mgr.scan_plugins()

    info_es = {p["id"]: p for p in mgr.get_plugins_info(lang="es")}
    info_en = {p["id"]: p for p in mgr.get_plugins_info(lang="en")}

    assert info_es["midi_controller"]["name"] == "Controlador de Teclado/Pads MIDI"
    assert info_en["midi_controller"]["name"] == "MIDI Keyboard/Pad Controller"

    assert info_es["arduino_pedals"]["name"] == "Pedales Arduino USB"
    assert info_en["arduino_pedals"]["name"] == "Arduino USB Pedals"

    print("    [OK] PluginManager info and device localization passed.")


if __name__ == "__main__":
    test_i18n_core_functions()
    test_plugin_instance_i18n()
    test_plugin_ui_renderer_i18n()
    test_manager_get_plugins_info_i18n()
    print("\nALL PLUGIN MULTI-LANGUAGE (i18n) TESTS PASSED SUCCESSFULLY!")
