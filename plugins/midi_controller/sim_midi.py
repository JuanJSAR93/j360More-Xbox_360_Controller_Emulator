"""
plugins/midi_controller/sim_midi.py
Virtual MIDI device simulator.
Generates synthetic MIDI events (Note On/Off, Pitch Bend sweeps, CC Modulation)
for automated testing without requiring a physical MIDI keyboard.
"""

import math
import time
from typing import Dict, List, Optional


class MIDISimulator:
    """Emulates a MIDI synthesizer/keyboard producing events."""

    def __init__(self):
        self._start_time = time.time()
        self._active_notes = set()

    def poll_events(self) -> List[Dict[str, any]]:
        """
        Polls for synthetic MIDI messages:
        Returns list of dicts:
            {'type': 'note_on'|'note_off', 'note': 60, 'velocity': 100}
            {'type': 'pitchwheel', 'pitch': -8192..8191}
            {'type': 'control_change', 'control': 1, 'value': 0..127}
        """
        events = []
        t = time.time() - self._start_time

        # Note sequence based on second interval (C4=60, D4=62, E4=64, F4=65)
        step = int(t * 2) % 8
        note_map = {
            0: 60,  # C4 -> 'A'
            1: 62,  # D4 -> 'B'
            2: 64,  # E4 -> 'X'
            3: 65,  # F4 -> 'Y'
            4: 67,  # G4 -> 'LB'
            5: 69,  # A4 -> 'RB'
        }

        current_note = note_map.get(step % 6, 60)

        # Trigger short pulses
        sub_t = (t * 2) % 1.0
        if sub_t < 0.6:
            if current_note not in self._active_notes:
                self._active_notes.add(current_note)
                events.append({"type": "note_on", "note": current_note, "velocity": 95, "channel": 0})
        else:
            if current_note in self._active_notes:
                self._active_notes.remove(current_note)
                events.append({"type": "note_off", "note": current_note, "velocity": 0, "channel": 0})

        # Pitch bend sweep: sine wave from -8192 to 8191
        pitch_val = int(math.sin(t * 1.8) * 8191)
        events.append({"type": "pitchwheel", "pitch": pitch_val, "channel": 0})

        # Modulation wheel: CC 1 (0 to 127)
        mod_val = int(((math.cos(t * 1.2) + 1.0) / 2.0) * 127)
        events.append({"type": "control_change", "control": 1, "value": mod_val, "channel": 0})

        return events


if __name__ == "__main__":
    sim = MIDISimulator()
    print("[*] Running standalone MIDI Simulator test (Ctrl+C to stop)...")
    try:
        while True:
            evs = sim.poll_events()
            for e in evs:
                if e["type"] in ("note_on", "note_off"):
                    print(f"MIDI Event: {e}")
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("[*] Simulator stopped.")
