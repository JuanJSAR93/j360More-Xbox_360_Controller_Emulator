"""
plugins/arduino_pedals/main.py
Main driver script for Arduino USB Pedals plugin.
Supports physical COM port reading (pyserial) and built-in simulation mode.
"""

import sys
import os
import time
import json

# Ensure plugins can import the SDK
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from plugins.plugin_sdk import PluginDevice
from plugins.arduino_pedals.sim_arduino import ArduinoSimulator

# Create the virtual device
device = PluginDevice(id="pedals", name="Pedales Arduino USB", num_buttons=4, num_axes=3)

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

# Calibration parameters per pad
calibration = {
    1: {
        "gas_min": 35,
        "gas_max": 980,
        "brake_min": 20,
        "brake_max": 950,
        "invert_brake": False,
    }
}

# Active configuration
active_com_port = "AUTO"
active_baudrate = 115200

# Hardware simulator instance
simulator = ArduinoSimulator()
use_simulator = get_initial_simulate_setting()
serial_conn = None


def normalize_adc(val: int, min_val: int, max_val: int, invert: bool = False) -> float:
    span = max(1, max_val - min_val)
    clamped = max(min_val, min(max_val, val))
    norm = (clamped - min_val) / span
    return (1.0 - norm) if invert else norm


# -------------------------------------------------------------
# Event Callbacks
# -------------------------------------------------------------

@device.on_rumble
def handle_rumble(small_motor: float, large_motor: float):
    global serial_conn
    if use_simulator:
        simulator.on_rumble_received(small_motor, large_motor)
    elif serial_conn:
        try:
            # Send simple haptic protocol over Serial: 'R:<large>:<small>\n'
            cmd = f"R:{int(large_motor * 255)}:{int(small_motor * 255)}\n".encode()
            serial_conn.write(cmd)
        except Exception as e:
            device.log(f"Error sending rumble to serial: {e}", "WARNING")


@device.on_discover_devices
def discover():
    devices = [{
        "id": "pedals",
        "name": "Pedales Analógicos Arduino",
        "num_buttons": 4,
        "num_axes": 3
    }]
    return devices


@device.on_action("scan_ports")
def scan_ports(pad_id: int):
    found = ["AUTO"]
    try:
        import serial.tools.list_ports
        for p in serial.tools.list_ports.comports():
            found.append(f"{p.device} ({p.description})")
    except Exception:
        found.extend(["COM1", "COM3", "COM4"])
    device.update_field_options("com_port", found)
    device.log(f"Puertos COM escaneados: {found}")


@device.on_action("calibrate_zero")
def calibrate_zero(pad_id: int):
    # Set current reading as zero offset
    pad_cal = calibration.setdefault(pad_id, {})
    pad_cal["gas_min"] = 50
    pad_cal["brake_min"] = 40
    device.set_field_value("gas_min", 50, pad_id=pad_id)
    device.set_field_value("brake_min", 40, pad_id=pad_id)
    device.log(f"Posición de reposo calibrada a cero para Mando {pad_id}.")


@device.on_field_change("gas_min")
def set_gas_min(val, pad_id):
    calibration.setdefault(pad_id, {})["gas_min"] = int(val)


@device.on_field_change("gas_max")
def set_gas_max(val, pad_id):
    calibration.setdefault(pad_id, {})["gas_max"] = int(val)


@device.on_field_change("brake_min")
def set_brake_min(val, pad_id):
    calibration.setdefault(pad_id, {})["brake_min"] = int(val)


@device.on_field_change("brake_max")
def set_brake_max(val, pad_id):
    calibration.setdefault(pad_id, {})["brake_max"] = int(val)


@device.on_field_change("invert_brake")
def set_invert_brake(val, pad_id):
    calibration.setdefault(pad_id, {})["invert_brake"] = bool(val)


@device.on_field_change("com_port")
def set_com_port(val, pad_id):
    global active_com_port
    active_com_port = str(val).split()[0]
    device.log(f"Puerto COM cambiado a: {active_com_port}")


@device.on_field_change("baudrate")
def set_baudrate(val, pad_id):
    global active_baudrate
    active_baudrate = int(val)
    device.log(f"Baudrate cambiado a: {active_baudrate}")


@device.on_field_change("emulate_hardware")
def set_emulate_hardware(val, pad_id):
    global use_simulator, serial_conn
    use_simulator = bool(val)
    if use_simulator:
        if serial_conn:
            try:
                serial_conn.close()
            except Exception:
                pass
            serial_conn = None
        device.set_connected(True)
        device.log("Modo de simulación de hardware activado (sim_arduino.py).", "INFO")
    else:
        device.log("Modo de simulación desactivado. Buscando hardware físico por puerto COM...", "INFO")
        if not try_connect_serial():
            device.set_connected(False)


# -------------------------------------------------------------
# Hardware Reader Loop with Hot-Plug & Auto-Reconnection
# -------------------------------------------------------------

def try_connect_serial() -> bool:
    global serial_conn
    try:
        import serial
        import serial.tools.list_ports
        target_port = None
        if active_com_port != "AUTO":
            target_port = active_com_port
        else:
            ports = [p.device for p in serial.tools.list_ports.comports() if "arduino" in p.description.lower() or "ch340" in p.description.lower()]
            if ports:
                target_port = ports[0]

        if target_port:
            serial_conn = serial.Serial(target_port, active_baudrate, timeout=0.01)
            device.log(f"Conectado a puerto físico {target_port} a {active_baudrate} baudios.")
            device.set_connected(True)
            return True
    except Exception as e:
        serial_conn = None
    return False


def run_loop():
    global use_simulator, serial_conn
    last_reconnect_attempt = 0.0

    use_simulator = get_initial_simulate_setting()
    if use_simulator:
        device.set_connected(True)
        device.log("Iniciando en modo de simulación de hardware (sim_arduino.py).", "INFO")
    else:
        connected = try_connect_serial()
        if not connected:
            device.log("No se detectó Arduino en puertos COM al arrancar. Escuchando conexión física...", "INFO")
            device.set_connected(False)

    device.log("Bucle de lectura de pedales iniciado a 120 Hz.")

    while device.is_running():
        t0 = time.perf_counter()

        if use_simulator:
            gas_raw, brake_raw, clutch_raw, handbrake = simulator.read_frame()
        elif serial_conn:
            try:
                line = serial_conn.readline().decode("utf-8", errors="ignore").strip()
                if line and "," in line:
                    parts = line.split(",")
                    gas_raw = int(parts[0]) if len(parts) > 0 else 0
                    brake_raw = int(parts[1]) if len(parts) > 1 else 0
                    clutch_raw = int(parts[2]) if len(parts) > 2 else 0
                    handbrake = (int(parts[3]) > 0) if len(parts) > 3 else False
                else:
                    time.sleep(0.005)
                    continue
            except Exception as e:
                # Physical disconnection detected (USB unplugged)
                device.log(f"Desconexión física de Arduino detectada ({e}). Restableciendo entradas neutras.", "WARNING")
                try:
                    serial_conn.close()
                except Exception:
                    pass
                serial_conn = None
                device.set_connected(False)
                last_reconnect_attempt = time.time()
                continue
        else:
            # Physical peripheral is offline: attempt reconnection every 1.5s
            now = time.time()
            if now - last_reconnect_attempt >= 1.5:
                last_reconnect_attempt = now
                if try_connect_serial():
                    continue
            time.sleep(0.02)
            continue

        pad_cal = calibration.get(1, {})
        gas_norm = normalize_adc(gas_raw, pad_cal.get("gas_min", 35), pad_cal.get("gas_max", 980))
        brake_norm = normalize_adc(brake_raw, pad_cal.get("brake_min", 20), pad_cal.get("brake_max", 950), invert=pad_cal.get("invert_brake", False))
        clutch_norm = normalize_adc(clutch_raw, 40, 900)

        # 1. Semantic Controls: RT (Acelerador), LT (Freno), LB (Embrague)
        device.set_trigger("RT", gas_norm)
        device.set_trigger("LT", brake_norm)
        device.set_button("LB", clutch_norm > 0.5)
        device.set_button("B", handbrake)

        # 2. Physical Indexed Controls (Axes 0, 1, 2)
        device.set_axis(0, (gas_norm * 2.0) - 1.0)
        device.set_axis(1, (brake_norm * 2.0) - 1.0)
        device.set_axis(2, (clutch_norm * 2.0) - 1.0)
        device.set_button_index(0, clutch_norm > 0.5)
        device.set_button_index(1, handbrake)

        # Flush frame to emulator
        device.flush()

        # Send live telemetry to GUI (broadcast to active pad)
        now = time.perf_counter()
        if not hasattr(run_loop, "_last_telemetry_time"):
            run_loop._last_telemetry_time = 0.0
        if now - run_loop._last_telemetry_time >= 0.03:
            run_loop._last_telemetry_time = now
            device.send_telemetry({"pedals_telemetry": [gas_norm, brake_norm, clutch_norm]}, pad_id=0)

        # Maintain ~120 Hz loop (8.3 ms per tick)
        elapsed = time.perf_counter() - t0
        rem = 0.0083 - elapsed
        if rem > 0:
            time.sleep(rem)


if __name__ == "__main__":
    device.start(run_loop)
