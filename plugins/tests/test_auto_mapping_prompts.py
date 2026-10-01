"""
plugins/tests/test_auto_mapping_prompts.py
Unit & integration tests for auto-mapping logic, confirmation prompts on device switch,
preservation during hotplug reconnect, and manual auto-map button.
"""

import os
import sys
import tkinter as tk
from unittest.mock import patch, MagicMock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from gui_app import J360MoreApp, DEFAULT_PHONE_MAPPINGS


def test_auto_mapping():
    print("[1] Initializing Tkinter and J360MoreApp...")
    root = tk.Tk()
    root.withdraw()
    app = J360MoreApp(root)

    # Set up test mock devices in available_devices
    test_devices = [
        {"id": "none", "name": "-- Ninguno / Desconectado --"},
        {"id": "phone_test1", "name": "AirPad Móvil (Pixel 7)", "display_name": "AirPad Móvil (Pixel 7)"},
        {"id": "plugin:arduino_pedals:0", "name": "Pedales Arduino USB", "display_name": "Pedales Arduino USB"},
        {"id": "joy_0", "name": "Xbox 360 Controller USB", "display_name": "Xbox 360 Controller USB"},
    ]
    app.available_devices = test_devices

    pad_id = 1
    widgets = app.tab_widgets[pad_id]

    print("[2] Testing clean slot + AirPad (No prompt, direct auto-map)...")
    # Reset all combos in slot 1 to None
    for cb in widgets["combos"].values():
        cb.set("-- Ninguno --")
    app._sync_ui_to_config()
    assert not app._pad_has_active_mappings(pad_id), "Clean pad was reported as having active mappings"

    # Select AirPad
    widgets["dev_combo"].current(1)  # phone_test1
    with patch("tkinter.messagebox.askyesno") as mock_prompt:
        app._on_device_selected(pad_id)
        mock_prompt.assert_not_called()

    # Verify AirPad mappings applied
    assert widgets["combos"]["A"].get() == app.localize_mapping(DEFAULT_PHONE_MAPPINGS["A"]), f"A was {widgets['combos']['A'].get()}"
    assert widgets["combos"]["RIGHT_TRIGGER"].get() == app.localize_mapping(DEFAULT_PHONE_MAPPINGS["RIGHT_TRIGGER"]), f"RT was {widgets['combos']['RIGHT_TRIGGER'].get()}"
    print("    Clean slot + AirPad auto-mapped successfully without prompt.")

    print("[3] Testing active slot + AirPad (Prompt shown, user chooses NO)...")
    # Modify a mapping manually
    widgets["combos"]["A"].set(app.localize_mapping("Button 8"))
    app._sync_ui_to_config()
    assert app._pad_has_active_mappings(pad_id)

    # Re-select AirPad, user responds NO (False)
    with patch("tkinter.messagebox.askyesno", return_value=False) as mock_prompt:
        app._on_device_selected(pad_id)
        mock_prompt.assert_called_once()

    # Verify custom mapping was preserved
    assert widgets["combos"]["A"].get() == app.localize_mapping("Button 8"), "Custom mapping was overwritten despite user answering NO"
    print("    Active slot preserved when user answered NO.")

    print("[4] Testing active slot + AirPad (Prompt shown, user chooses YES)...")
    # Re-select AirPad, user responds YES (True)
    with patch("tkinter.messagebox.askyesno", return_value=True) as mock_prompt:
        app._on_device_selected(pad_id)
        mock_prompt.assert_called_once()

    # Verify template was restored
    assert widgets["combos"]["A"].get() == app.localize_mapping("Button 1"), "Template was not applied when user answered YES"
    print("    Active slot replaced with AirPad template when user answered YES.")

    print("[5] Testing Plugin auto-mapping (Arduino Pedals)...")
    # Start plugin or mock plugin default mappings
    app.plugin_manager.plugins["arduino_pedals"].manifest["auto_map_controller"] = True
    app.plugin_manager.plugins["arduino_pedals"].manifest["default_mappings"] = {
        "RIGHT_TRIGGER": "Axis 1",
        "LEFT_TRIGGER": "Axis 2",
        "LEFT_SHOULDER": "Axis 3"
    }

    # Case 5A: Clean slot + Arduino Pedals (No prompt)
    for cb in widgets["combos"].values():
        cb.set(app.localize_mapping("-- Ninguno --"))
    app._sync_ui_to_config()

    widgets["dev_combo"].current(2)  # plugin:arduino_pedals:0
    with patch("tkinter.messagebox.askyesno") as mock_prompt:
        app._on_device_selected(pad_id)
        mock_prompt.assert_not_called()

    assert widgets["combos"]["RIGHT_TRIGGER"].get() == app.localize_mapping("Axis 1")
    assert widgets["combos"]["LEFT_TRIGGER"].get() == app.localize_mapping("Axis 2")
    assert widgets["combos"]["LEFT_SHOULDER"].get() == app.localize_mapping("Axis 3")
    assert app.canonicalize_mapping(widgets["combos"]["A"].get()) == "-- Ninguno --"
    print("    Clean slot + Arduino Pedals auto-mapped pedals and cleared unused inputs.")

    # Case 5B: Active slot + Arduino Pedals with user choosing YES
    widgets["combos"]["A"].set(app.localize_mapping("Button 4"))
    app._sync_ui_to_config()
    with patch("tkinter.messagebox.askyesno", return_value=True) as mock_prompt:
        app._on_device_selected(pad_id)
        mock_prompt.assert_called_once()
    assert widgets["combos"]["RIGHT_TRIGGER"].get() == app.localize_mapping("Axis 1")
    assert app.canonicalize_mapping(widgets["combos"]["A"].get()) == "-- Ninguno --"
    print("    Active slot + Arduino Pedals replaced when user answered YES.")

    # Case 5C: When plugin auto_map_controller is False, selecting does not auto-map
    app.plugin_manager.plugins["arduino_pedals"].manifest["auto_map_controller"] = False
    widgets["combos"]["A"].set(app.localize_mapping("Button 5"))
    app._sync_ui_to_config()
    with patch("tkinter.messagebox.askyesno") as mock_prompt:
        app._on_device_selected(pad_id)
        mock_prompt.assert_not_called()
    assert widgets["combos"]["A"].get() == app.localize_mapping("Button 5")
    print("    Plugin with auto_map_controller=False did not prompt and did not auto-map.")

    print("[6] Testing standard USB Gamepad (joy_0)...")
    widgets["combos"]["A"].set(app.localize_mapping("Button 10"))
    app._sync_ui_to_config()
    widgets["dev_combo"].current(3)  # joy_0
    with patch("tkinter.messagebox.askyesno") as mock_prompt:
        app._on_device_selected(pad_id)
        mock_prompt.assert_not_called()
    assert widgets["combos"]["A"].get() == app.localize_mapping("Button 10")
    print("    Standard USB Gamepad selection never prompts and never overwrites mappings.")

    print("[7] Testing manual auto-map button (_manual_auto_map)...")
    # For Arduino Pedals with default_mappings available
    widgets["dev_combo"].current(2)  # plugin:arduino_pedals:0
    widgets["combos"]["RIGHT_TRIGGER"].set(app.localize_mapping("-- Ninguno --"))
    with patch("tkinter.messagebox.showinfo") as mock_info:
        app._manual_auto_map(pad_id)
        mock_info.assert_called_once()
    assert widgets["combos"]["RIGHT_TRIGGER"].get() == app.localize_mapping("Axis 1")
    print("    Manual auto-map button successfully re-applied template and showed info dialog.")

    # For joy_0 (no template)
    widgets["dev_combo"].current(3)  # joy_0
    with patch("tkinter.messagebox.showinfo") as mock_info:
        app._manual_auto_map(pad_id)
        mock_info.assert_called_once()
        # Verify automap_no_template was shown
        call_msg = mock_info.call_args[0][1]
        assert "no hay" in call_msg.lower() or "no specific" in call_msg.lower()
    print("    Manual auto-map button showed 'no template' notice for generic joystick.")

    print("[8] Testing hotplug reconnect preservation...")
    # Slot 1 is assigned to joy_0 with A=Botón 10
    app.config["controllers"]["1"]["physical_device_id"] = "joy_0"
    app.config["controllers"]["1"]["mappings"]["A"] = "Button 10"
    # Simulate hotplug where joy_0 reconnects
    app._on_devices_hotplugged(test_devices)
    assert app.config["controllers"]["1"]["mappings"]["A"] == "Button 10"
    print("    Hotplug reconnect preserved existing mappings.")

    print("\nALL AUTO-MAPPING TESTS PASSED SUCCESSFULLY!")
    root.destroy()


if __name__ == "__main__":
    test_auto_mapping()
