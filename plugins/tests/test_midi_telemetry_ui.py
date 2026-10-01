"""
plugins/tests/test_midi_telemetry_ui.py
Verifies that MIDI activity telemetry renders and updates the UI canvas properly,
including custom labels, canvas fallback sizing, and broadcast dispatch.
"""

import sys
import os
import time
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any

# Add repository root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from plugins.plugin_ui_renderer import PluginUIRenderer
from plugins.plugin_manager import PluginManager


def test_ui_telemetry_rendering():
    root = tk.Tk()
    root.withdraw()  # Headless test

    # Define fields matching midi_controller/plugin.json
    fields = [
        {
            "id": "midi_telemetry",
            "label": "Actividad de Notas y Rueda (Pitch / Modulación):",
            "type": "progress_bar_multi",
            "labels": ["VELOCIDAD", "PITCH BEND", "MODULACIÓN"]
        }
    ]

    frame = ttk.Frame(root)
    frame.pack()

    rendered = PluginUIRenderer.render_fields(frame, fields, {})
    assert "midi_telemetry" in rendered, "midi_telemetry should be in rendered_refs"
    ref = rendered["midi_telemetry"]
    assert ref["labels"] == ["VELOCIDAD", "PITCH BEND", "MODULACIÓN"], f"Labels mismatch: {ref['labels']}"
    assert isinstance(ref["widget"], tk.Canvas), "Widget should be a tk.Canvas"

    # Test updating telemetry widget even before window mapping (winfo_width() <= 1)
    PluginUIRenderer.update_telemetry_widget(ref, [0.75, 0.5, 0.25])

    # Check canvas items drawn
    items = ref["widget"].find_all()
    assert len(items) > 0, "Canvas should have drawn background tracks, fills, and text labels"

    # Verify that text contains custom labels
    texts = [ref["widget"].itemcget(i, "text") for i in items if ref["widget"].type(i) == "text"]
    assert any("VELOCIDAD" in t for t in texts), f"VELOCIDAD not found in texts: {texts}"
    assert any("PITCH BEND" in t for t in texts), f"PITCH BEND not found in texts: {texts}"
    assert any("MODULACIÓN" in t for t in texts), f"MODULACIÓN not found in texts: {texts}"

    # Test dynamic value changes (animating)
    PluginUIRenderer.update_telemetry_widget(ref, [0.0, 1.0, 0.9])
    items2 = ref["widget"].find_all()
    texts2 = [ref["widget"].itemcget(i, "text") for i in items2 if ref["widget"].type(i) == "text"]
    assert any("0%" in t for t in texts2), "0% velocity expected"
    assert any("100%" in t for t in texts2), "100% pitch expected"

    root.destroy()
    print("[PASS] test_ui_telemetry_rendering passed successfully!")


def test_dispatch_plugin_telemetry_broadcast():
    """Verifies that _dispatch_plugin_telemetry delivers data to active tabs even when pad_id=0 (broadcast)."""
    root = tk.Tk()
    root.withdraw()

    class MockGUI:
        def __init__(self):
            self.root = root
            self._plugin_telemetry_refs = {}

        def _dispatch_plugin_telemetry(self, plugin_id: str, pad_id: int, data: Dict[str, Any]):
            target_refs_list = []
            if pad_id > 0 and (plugin_id, pad_id) in self._plugin_telemetry_refs:
                target_refs_list.append(self._plugin_telemetry_refs[(plugin_id, pad_id)])

            if not target_refs_list or pad_id == 0:
                for (p_id, p_pad), refs in list(self._plugin_telemetry_refs.items()):
                    if p_id == plugin_id and refs not in target_refs_list:
                        target_refs_list.append(refs)

            for refs in target_refs_list:
                for field_id, rdata in refs.items():
                    if isinstance(rdata, dict) and rdata.get("type") in ("progress_bar_multi", "progress_bar_pair"):
                        vals = data.get(field_id)
                        if vals is None:
                            vals = data.get("values")
                        if vals is not None:
                            if not isinstance(vals, (list, tuple)):
                                vals = [vals]
                            PluginUIRenderer.update_telemetry_widget(rdata, vals)

    mock = MockGUI()
    frame = ttk.Frame(root)
    fields = [
        {
            "id": "midi_telemetry",
            "type": "progress_bar_multi",
            "labels": ["VELOCIDAD", "PITCH BEND", "MODULACIÓN"]
        }
    ]
    refs_pad2 = PluginUIRenderer.render_fields(frame, fields, {})
    # Simulate user opened MIDI tab on Pad 2
    mock._plugin_telemetry_refs[("midi_controller", 2)] = refs_pad2

    # Plugin sends broadcast telemetry (pad_id=0)
    mock._dispatch_plugin_telemetry("midi_controller", 0, {"midi_telemetry": [0.8, 0.6, 0.4]})

    canvas = refs_pad2["midi_telemetry"]["widget"]
    items = canvas.find_all()
    texts = [canvas.itemcget(i, "text") for i in items if canvas.type(i) == "text"]
    assert any("VELOCIDAD 80%" in t for t in texts), f"Expected 80% velocity, got {texts}"
    assert any("PITCH BEND 60%" in t for t in texts), f"Expected 60% pitch, got {texts}"
    assert any("MODULACIÓN 40%" in t for t in texts), f"Expected 40% mod, got {texts}"

    root.destroy()
    print("[PASS] test_dispatch_plugin_telemetry_broadcast passed successfully!")


def test_live_midi_controller_telemetry():
    """Starts the real midi_controller plugin and verifies live telemetry frames arrive with moving values."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    mgr = PluginManager(base_dir=root_dir)
    mgr.scan_plugins()

    assert "midi_controller" in mgr.plugins, "midi_controller plugin must be present"

    received_frames = []

    def on_telemetry(plugin_id: str, pad_id: int, data: Dict[str, Any]):
        if plugin_id == "midi_controller" and "midi_telemetry" in data:
            received_frames.append(data["midi_telemetry"])

    mgr.add_on_telemetry(on_telemetry)

    success = mgr.start_plugin("midi_controller")
    assert success, "Failed to start midi_controller"

    # Wait for telemetry frames to arrive (simulated or hardware)
    deadline = time.time() + 4.0
    while time.time() < deadline and len(received_frames) < 10:
        time.sleep(0.05)

    mgr.stop_plugin("midi_controller")

    assert len(received_frames) >= 5, f"Expected at least 5 telemetry frames, got {len(received_frames)}"
    print(f"[INFO] Received {len(received_frames)} telemetry frames from midi_controller.")

    # Verify that telemetry values are valid normalized numbers (0.0 to 1.0) and move
    pitches = [frame[1] for frame in received_frames]
    assert all(0.0 <= p <= 1.0 for p in pitches), f"Pitches out of range: {pitches[:5]}"
    assert len(set(pitches)) > 1, f"Pitch bend should change dynamically over time! Got constant: {pitches[:5]}"

    print(f"[PASS] test_live_midi_controller_telemetry verified {len(received_frames)} live frames with moving values!")


if __name__ == "__main__":
    test_ui_telemetry_rendering()
    test_dispatch_plugin_telemetry_broadcast()
    test_live_midi_controller_telemetry()
    print("\nALL MIDI ACTIVITY TELEMETRY TESTS PASSED!")
