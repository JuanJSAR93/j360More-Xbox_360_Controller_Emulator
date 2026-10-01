"""
plugins/tests/test_missing_plugins_and_midi.py
Tests:
1. Behavior when the plugins directory is missing (deactivates plugin functions, shows setup UI).
2. Clean installation of midi_controller dependencies without compilation errors.
"""

import os
import sys
import time
import tkinter as tk

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from plugins.plugin_manager import PluginManager, get_plugin_manager
from gui_app import J360MoreApp


def test_missing_plugins_behavior():
    print("[1] Testing PluginManager when plugins folder does not exist...")
    fake_base = os.path.join(BASE_DIR, "non_existent_folder_for_test")
    pm_fake = PluginManager(base_dir=fake_base)

    assert not pm_fake.is_plugins_folder_present(), "Should report False when folder does not exist"
    assert not pm_fake.is_enabled(), "Should be disabled when folder is missing"
    assert pm_fake.scan_plugins() == [], "scan_plugins should return empty list"
    assert pm_fake.get_available_devices() == [], "get_available_devices should return empty list"
    assert pm_fake.read_physical_state("plugin:fake:dev") is None, "read_physical_state should return None"
    print("    [✓] Non-existent plugins folder correctly deactivates plugin functions.")


def test_missing_plugins_gui_view():
    print("[2] Testing Settings Dialog when plugins folder is reported missing...")
    root = tk.Tk()
    root.withdraw()
    app = J360MoreApp(root)

    # Temporarily point plugin_manager to non-existent folder
    orig_plugins_dir = app.plugin_manager.plugins_dir
    app.plugin_manager.plugins_dir = os.path.join(BASE_DIR, "missing_plugins_dir_xyz")

    # Open Settings Dialog on tab 2 (Plugins tab)
    app._open_settings_dialog(initial_tab=2)
    root.update()

    # The dialog should have opened and rendered the setup warning frame
    assert app._active_dialog is not None, "Settings dialog should be active"
    print("    [✓] Settings dialog opened and rendered setup/warning view.")

    # Restore plugins_dir
    app.plugin_manager.plugins_dir = orig_plugins_dir
    app._active_dialog.destroy()
    root.update()
    app._on_close()


def test_midi_controller_no_compiler_error():
    print("[3] Testing midi_controller requirements installation...")
    pm = get_plugin_manager()
    pm.scan_plugins()
    assert "midi_controller" in pm.plugins, "midi_controller should be discovered"

    ok, msg = pm.install_plugin_requirements("midi_controller", callback=lambda m: None)
    assert ok, f"midi_controller dependencies should install cleanly: {msg}"
    print("    [✓] midi_controller dependencies installed without C++ compiler requirement.")

    print("[4] Testing midi_controller execution in simulated mode...")
    pm.add_on_log(lambda pid, msg: print(f"    [{pid}] {msg}"))
    ok, msg = pm.start_plugin("midi_controller", simulate=True)
    assert ok, f"midi_controller should start: {msg}"
    
    deadline = time.time() + 3.0
    state = None
    while time.time() < deadline:
        state = pm.read_physical_state("plugin:midi_controller:midi")
        if state is not None:
            break
        time.sleep(0.1)

    assert state is not None, "Should read physical state from midi_controller"
    assert "buttons" in state and "sticks" in state, "State must contain buttons and sticks"
    print(f"    State sample: axes={state.get('axes')}")

    pm.stop_plugin("midi_controller")
    print("    [✓] midi_controller executed and stopped cleanly.")


if __name__ == "__main__":
    test_missing_plugins_behavior()
    test_missing_plugins_gui_view()
    test_midi_controller_no_compiler_error()
    print("\n[✓] ALL TESTS PASSED!")
