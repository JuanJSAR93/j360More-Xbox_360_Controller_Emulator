"""
plugins/tests/test_full_gui_integration.py
Full End-to-End integration test for the Plugin System with GUI components,
simulated hardware, and dynamic tab injection.
"""

import os
import sys
import time
import tkinter as tk

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure app root is on path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from plugins.plugin_manager import get_plugin_manager
from gui_app import J360MoreApp


def test_plugin_gui_integration():
    print("[1] Creating root Tkinter instance (hidden)...")
    root = tk.Tk()
    root.withdraw()

    print("[2] Initializing J360MoreApp...")
    app = J360MoreApp(root)
    assert app.plugin_manager is not None, "app.plugin_manager was not initialized"

    print("[3] Verifying scanned plugins...")
    plugins = app.plugin_manager.plugins
    print(f"    Discovered plugins: {list(plugins.keys())}")
    assert "arduino_pedals" in plugins, "arduino_pedals not discovered"
    assert "midi_controller" in plugins, "midi_controller not discovered"

    print("[4] Starting arduino_pedals in simulated mode...")
    ok, msg = app.plugin_manager.start_plugin("arduino_pedals", simulate=True)
    assert ok, f"Failed to start arduino_pedals: {msg}"

    print("[5] Waiting for IPC handshake and dynamic device detection...")
    start_t = time.time()
    discovered_devs = []
    while time.time() - start_t < 4.0:
        root.update()
        time.sleep(0.05)
        devs = app.device_manager.refresh_devices()
        plugin_devs = [d for d in devs if d.get("id", "").startswith("plugin:arduino_pedals")]
        if plugin_devs:
            discovered_devs = plugin_devs
            break

    assert len(discovered_devs) > 0, "arduino_pedals device was not registered dynamically"
    pedal_dev = discovered_devs[0]
    print(f"    Found plugin device: {pedal_dev['id']} -> {pedal_dev['name']}")

    print("[6] Assigning plugin device to Controller 1...")
    # Refresh available_devices in app
    app._refresh_all_devices(async_scan=False)
    root.update()

    # Find index of pedal_dev in app.available_devices
    match_idx = -1
    for idx, d in enumerate(app.available_devices):
        if d["id"] == pedal_dev["id"]:
            match_idx = idx
            break
    assert match_idx >= 0, "Plugin device not in app.available_devices"

    widgets_1 = app.tab_widgets[1]
    widgets_1["dev_combo"].current(match_idx)
    app._on_device_selected(1)
    root.update()

    # Verify that 'sticks' tab was removed and custom tab '🏎 Calibración Pedales' was added
    sub_nb = widgets_1["sub_nb"]
    tab_texts = [sub_nb.tab(i, "text").strip() for i in range(len(sub_nb.tabs()))]
    print(f"    Controller 1 tabs with Pedals: {tab_texts}")
    assert "Sticks" not in tab_texts, "'Sticks' tab should be hidden for pedals!"
    assert any("Pedales" in t or "Pedals" in t for t in tab_texts), "Custom pedals tab should be present!"
    assert len(widgets_1["custom_plugin_tabs"]) == 1, "custom_plugin_tabs list should have 1 entry"

    # Verify that 'btn_plugin_cfg' is mapped/visible
    btn_cfg = widgets_1.get("btn_plugin_cfg")
    assert btn_cfg is not None and btn_cfg.winfo_ismapped(), "Ajustes de Plugin button should be visible"

    print("[7] Simulating live telemetry dispatch to Controller 1 UI...")
    # Dispatch simulated telemetry
    app._dispatch_plugin_telemetry("arduino_pedals", 1, {"values": [0.85, 0.40, 0.10]})
    root.update()
    print("    Telemetry rendered on canvas successfully.")

    print("[8] Switching Controller 1 back to 'none' device...")
    widgets_1["dev_combo"].current(0)
    app._on_device_selected(1)
    root.update()

    # Verify that default tabs were restored and custom tabs removed
    tab_texts_after = [sub_nb.tab(i, "text").strip() for i in range(len(sub_nb.tabs()))]
    print(f"    Controller 1 tabs after reset: {tab_texts_after}")
    assert "Sticks" in tab_texts_after, "'Sticks' tab should be restored!"
    assert not any("Pedales" in t for t in tab_texts_after), "Custom pedals tab should be removed!"
    assert len(widgets_1["custom_plugin_tabs"]) == 0, "custom_plugin_tabs should be empty"
    assert not btn_cfg.winfo_ismapped(), "Ajustes de Plugin button should be hidden"

    print("[9] Testing Settings Dialog plugins tab opening...")
    # Open settings dialog with initial_tab=2 (Plugins)
    # We will close it after a tick
    app._open_settings_dialog(initial_tab=2)
    root.update()
    if app._active_dialog:
        app._active_dialog.destroy()
    root.update()

    print("[10] Cleaning up processes and closing app...")
    app._on_close()
    print("[✓] ALL INTEGRATION TESTS PASSED CLEANLY!")


if __name__ == "__main__":
    test_plugin_gui_integration()
