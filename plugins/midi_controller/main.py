"""
plugins/midi_controller/main.py
Main driver script for MIDI Controller plugin.
Converts MIDI Note On/Off messages to gamepad buttons and wheels to sticks.
Supports real physical MIDI hardware and built-in simulation mode.
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from plugins.plugin_sdk import PluginDevice
from plugins.midi_controller.sim_midi import MIDISimulator

device = PluginDevice(id="midi", name="Controlador de Teclado/Pads MIDI", num_buttons=8, num_axes=4)

def get_initial_simulate_setting() -> bool:
    if "--simulate" in sys.argv:
        return True
    cfg_file = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.isfile(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if "emulate_hardware" in cfg.get("global", {}):
                    return bool(cfg["global"]["emulate_hardware"])
        except Exception:
            pass
    return True

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
use_simulator = get_initial_simulate_setting()
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
    # 1. Intentar con pygame.midi (precompilado, universal)
    try:
        import pygame.midi
        if not pygame.midi.get_init():
            pygame.midi.init()
        for i in range(pygame.midi.get_count()):
            info = pygame.midi.get_device_info(i)
            if info and info[2]:  # is_input
                dname = info[1].decode("utf-8", errors="ignore")
                found.append(f"{i}: {dname}")
    except Exception:
        pass

    # 2. Intentar con mido
    if len(found) == 1:
        try:
            import mido
            inputs = mido.get_input_names()
            found.extend(inputs)
        except Exception:
            pass

    if len(found) == 1:
        found.extend(["Simulador Virtual MIDI", "nanoKEY2", "Launchpad Mini", "MPK mini"])

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

pg_midi_in = None


def try_connect_midi() -> bool:
    global pg_midi_in, midi_in_port
    # 1. Intentar con pygame.midi
    try:
        import pygame.midi
        if not pygame.midi.get_init():
            pygame.midi.init()
        chosen_dev_id = None
        if active_midi_port != "AUTO" and ":" in active_midi_port:
            try:
                chosen_dev_id = int(active_midi_port.split(":")[0])
            except ValueError:
                chosen_dev_id = None

        if chosen_dev_id is None:
            for i in range(pygame.midi.get_count()):
                info = pygame.midi.get_device_info(i)
                if info and info[2]:  # is_input
                    chosen_dev_id = i
                    break

        if chosen_dev_id is not None:
            pg_midi_in = pygame.midi.Input(chosen_dev_id)
            device.log(f"Conectado a puerto MIDI físico vía pygame.midi: ID #{chosen_dev_id}")
            device.set_connected(True)
            return True
    except Exception as ex:
        pg_midi_in = None

    # 2. Intentar con mido
    try:
        import mido
        inputs = mido.get_input_names()
        if inputs:
            target_port = inputs[0] if active_midi_port == "AUTO" else active_midi_port
            midi_in_port = mido.open_input(target_port)
            device.log(f"Conectado a puerto MIDI físico vía mido: {target_port}")
            device.set_connected(True)
            return True
    except Exception:
        midi_in_port = None

    return False


@device.on_field_change("emulate_hardware")
def set_emulate_hardware(val, pad_id):
    global use_simulator, midi_in_port, pg_midi_in
    use_simulator = bool(val)
    if use_simulator:
        if pg_midi_in:
            try:
                pg_midi_in.close()
            except Exception:
                pass
            pg_midi_in = None
        if midi_in_port:
            try:
                midi_in_port.close()
            except Exception:
                pass
            midi_in_port = None
        device.set_connected(True)
        device.log("Modo de simulación MIDI activado (sim_midi.py).", "INFO")
    else:
        device.log("Modo de simulación desactivado. Buscando dispositivo MIDI físico...", "INFO")
        if not try_connect_midi():
            device.set_connected(False)


# -------------------------------------------------------------
# MIDI Loop with Hot-Plug & Auto-Reconnection
# -------------------------------------------------------------

def run_loop():
    global use_simulator, midi_in_port, pg_midi_in
    last_reconnect_time = 0.0

    use_simulator = get_initial_simulate_setting()
    if use_simulator:
        device.set_connected(True)
        device.log("Iniciando en modo de simulación MIDI (sim_midi.py).", "INFO")
    else:
        connected = try_connect_midi()
        if not connected:
            device.log("No se detectó dispositivo MIDI físico al arrancar. Escuchando conexión física...", "INFO")
            device.set_connected(False)

    device.log("Bucle de recepción MIDI iniciado.")

    last_velocity_norm = 0.0
    last_pitch_norm = 0.5  # Neutral center
    last_mod_norm = 0.0
    active_notes = set()
    last_telemetry_time = 0.0

    while device.is_running():
        t0 = time.perf_counter()

        events = []
        if use_simulator:
            events = simulator.poll_events()
        elif pg_midi_in:
            try:
                while pg_midi_in.poll():
                    midi_data = pg_midi_in.read(16)
                    for me in midi_data:
                        raw_bytes, timestamp = me
                        st, d1, d2, _ = raw_bytes
                        cmd = st & 0xF0
                        if cmd == 0x90 and d2 > 0:
                            events.append({"type": "note_on", "note": d1, "velocity": d2})
                        elif cmd == 0x80 or (cmd == 0x90 and d2 == 0):
                            events.append({"type": "note_off", "note": d1, "velocity": 0})
                        elif cmd == 0xE0:
                            val14 = (d2 << 7) | d1
                            events.append({"type": "pitchwheel", "pitch": val14 - 8192})
                        elif cmd == 0xB0 and d1 == 1:
                            events.append({"type": "control_change", "control": 1, "value": d2})
            except Exception as e:
                device.log(f"Desconexión física o error en pygame.midi: {e}", "WARNING")
                try:
                    pg_midi_in.close()
                except Exception:
                    pass
                pg_midi_in = None
                device.set_connected(False)
                last_reconnect_time = time.time()
                continue
        elif midi_in_port:
            try:
                for msg in midi_in_port.iter_pending():
                    events.append(msg.dict())
            except Exception as e:
                device.log(f"Desconexión física o error en mido: {e}", "WARNING")
                try:
                    midi_in_port.close()
                except Exception:
                    pass
                midi_in_port = None
                device.set_connected(False)
                last_reconnect_time = time.time()
                continue
        else:
            # Physical peripheral disconnected: retry connection every 1.5s
            now = time.time()
            if now - last_reconnect_time >= 1.5:
                last_reconnect_time = now
                if try_connect_midi():
                    continue
            time.sleep(0.02)
            continue

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
                    active_notes.add(note)
                else:
                    btn_name = NOTE_MAP.get(note)
                    if btn_name:
                        device.set_button(btn_name, False)
                    device.set_button_index(note % 8, False)
                    active_notes.discard(note)

            elif ev_type == "note_off":
                note = ev.get("note", 60)
                btn_name = NOTE_MAP.get(note)
                if btn_name:
                    device.set_button(btn_name, False)
                device.set_button_index(note % 8, False)
                active_notes.discard(note)

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

        if not active_notes and last_velocity_norm > 0:
            last_velocity_norm = max(0.0, last_velocity_norm - 0.05)

        # Flush controller state
        device.flush()

        # Telemetry: broadcast to any assigned pad (pad_id=0) throttled to ~33 FPS
        now = time.perf_counter()
        if now - last_telemetry_time >= 0.03:
            last_telemetry_time = now
            device.send_telemetry({"midi_telemetry": [last_velocity_norm, last_pitch_norm, last_mod_norm]}, pad_id=0)

        elapsed = time.perf_counter() - t0
        rem = 0.01 - elapsed
        if rem > 0:
            time.sleep(rem)

    if pg_midi_in:
        try:
            pg_midi_in.close()
        except Exception:
            pass
    if midi_in_port:
        try:
            midi_in_port.close()
        except Exception:
            pass


if __name__ == "__main__":
    device.start(run_loop)
