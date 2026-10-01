"""
plugins/midi_controller/main.py
Main driver script for MIDI Controller plugin.
Converts MIDI Note On/Off messages to gamepad buttons and wheels to sticks.
Supports real physical MIDI hardware and built-in simulation mode.
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from plugins.plugin_sdk import PluginDevice
from plugins.midi_controller.sim_midi import MIDISimulator

device = PluginDevice(id="midi", name="Controlador de Teclado/Pads MIDI", num_buttons=8, num_axes=4)

# MIDI Note to Xbox Button Mapping
NOTE_MAP = {
    60: "A",       # C4
    62: "B",       # D4
    64: "X",       # E4
    65: "Y",       # F4
    67: "LB",      # G4
    69: "RB",      # A4
    71: "START",   # B4
    72: "GUIDE",   # C5
}

# Calibration parameters
calibration = {
    1: {
        "velocity_threshold": 15,
        "pitch_bend_sens": 100,
    }
}

active_midi_port = "AUTO"
active_midi_channel = "TODOS"

simulator = MIDISimulator()
use_simulator = False
midi_in_port = None


# -------------------------------------------------------------
# Event Callbacks
# -------------------------------------------------------------

@device.on_discover_devices
def discover():
    return [{
        "id": "midi",
        "name": "Teclado / Pads MIDI",
        "num_buttons": 8,
        "num_axes": 4
    }]


@device.on_action("scan_midi_ports")
def scan_midi_ports(pad_id: int):
    found = ["AUTO"]
    try:
        import mido
        inputs = mido.get_input_names()
        found.extend(inputs)
    except Exception:
        found.extend(["nanoKEY2", "Launchpad Mini", "MPK mini"])
    device.update_field_options("midi_port", found)
    device.log(f"Puertos MIDI escaneados: {found}")


@device.on_field_change("velocity_threshold")
def set_velocity_threshold(val, pad_id):
    calibration.setdefault(pad_id, {})["velocity_threshold"] = int(val)


@device.on_field_change("pitch_bend_sens")
def set_pitch_bend_sens(val, pad_id):
    calibration.setdefault(pad_id, {})["pitch_bend_sens"] = int(val)


@device.on_field_change("midi_port")
def set_midi_port(val, pad_id):
    global active_midi_port
    active_midi_port = str(val)
    device.log(f"Puerto MIDI cambiado a: {active_midi_port}")


@device.on_field_change("midi_channel")
def set_midi_channel(val, pad_id):
    global active_midi_channel
    active_midi_channel = str(val)
    device.log(f"Canal MIDI cambiado a: {active_midi_channel}")


# -------------------------------------------------------------
# MIDI Loop
# -------------------------------------------------------------

def run_loop():
    global use_simulator, midi_in_port

    if "--simulate" in sys.argv:
        use_simulator = True
        device.log("Modo de simulación MIDI activado (--simulate).")
    else:
        try:
            import mido
            inputs = mido.get_input_names()
            if inputs:
                target_port = inputs[0] if active_midi_port == "AUTO" else active_midi_port
                midi_in_port = mido.open_input(target_port)
                device.log(f"Conectado a puerto MIDI físico: {target_port}")
            else:
                use_simulator = True
                device.log("No se encontraron dispositivos MIDI físicos. Activando simulador virtual.")
        except Exception as e:
            use_simulator = True
            device.log(f"mido no disponible o sin hardware ({e}). Activando simulador MIDI.")

    device.log("Bucle de recepción MIDI iniciado.")

    last_velocity_norm = 0.0
    last_pitch_norm = 0.0
    last_mod_norm = 0.0

    while device.is_running():
        t0 = time.perf_counter()

        events = []
        if use_simulator:
            events = simulator.poll_events()
        elif midi_in_port:
            for msg in midi_in_port.iter_pending():
                events.append(msg.dict())

        pad_cal = calibration.get(1, {})
        vel_thresh = pad_cal.get("velocity_threshold", 15)
        pitch_sens = pad_cal.get("pitch_bend_sens", 100) / 100.0

        for ev in events:
            ev_type = ev.get("type")

            # 1. Note On / Off
            if ev_type == "note_on":
                note = ev.get("note", 60)
                vel = ev.get("velocity", 0)
                if vel >= vel_thresh:
                    btn_name = NOTE_MAP.get(note)
                    if btn_name:
                        device.set_button(btn_name, True)
                    # Also map to indexed buttons
                    device.set_button_index(note % 8, True)
                    last_velocity_norm = vel / 127.0
                else:
                    btn_name = NOTE_MAP.get(note)
                    if btn_name:
                        device.set_button(btn_name, False)
                    device.set_button_index(note % 8, False)

            elif ev_type == "note_off":
                note = ev.get("note", 60)
                btn_name = NOTE_MAP.get(note)
                if btn_name:
                    device.set_button(btn_name, False)
                device.set_button_index(note % 8, False)

            # 2. Pitch Bend -> Left Stick X
            elif ev_type == "pitchwheel":
                raw_pitch = ev.get("pitch", 0)  # -8192 to 8191
                norm_pitch = max(-1.0, min(1.0, (raw_pitch / 8191.0) * pitch_sens))
                device.set_stick("LX", norm_pitch)
                device.set_axis(0, norm_pitch)
                last_pitch_norm = (norm_pitch + 1.0) / 2.0

            # 3. Modulation Wheel (CC 1) -> Left Stick Y
            elif ev_type == "control_change" and ev.get("control") == 1:
                cc_val = ev.get("value", 0)  # 0 to 127
                norm_mod = (cc_val / 63.5) - 1.0  # -1.0 to 1.0
                device.set_stick("LY", norm_mod)
                device.set_axis(1, norm_mod)
                last_mod_norm = cc_val / 127.0

        # Flush controller state
        device.flush()

        # Telemetry
        device.send_telemetry({"midi_telemetry": [last_velocity_norm, last_pitch_norm, last_mod_norm]}, pad_id=1)

        elapsed = time.perf_counter() - t0
        rem = 0.01 - elapsed
        if rem > 0:
            time.sleep(rem)

    if midi_in_port:
        try:
            midi_in_port.close()
        except Exception:
            pass


if __name__ == "__main__":
    device.start(run_loop)
