"""
plugins/arduino_pedals/main.py
Main driver script for Arduino USB Pedals plugin.
Supports physical COM port reading (pyserial) and built-in simulation mode.
"""

import sys
import os
import time

# Ensure plugins can import the SDK
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from plugins.plugin_sdk import PluginDevice
from plugins.arduino_pedals.sim_arduino import ArduinoSimulator

# Create the virtual device
device = PluginDevice(id="pedals", name="Pedales Arduino USB", num_buttons=4, num_axes=3)

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
use_simulator = False
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


# -------------------------------------------------------------
# Hardware Reader Loop
# -------------------------------------------------------------

def run_loop():
    global use_simulator, serial_conn
    # Check if forced simulation via CLI or if pyserial is absent
    if "--simulate" in sys.argv:
        use_simulator = True
        device.log("Modo de simulación de hardware activado (--simulate).")
    else:
        try:
            import serial
            import serial.tools.list_ports
            # Try connecting if real port
            if active_com_port != "AUTO":
                serial_conn = serial.Serial(active_com_port, active_baudrate, timeout=0.01)
                device.log(f"Conectado a puerto físico {active_com_port} a {active_baudrate} baudios.")
            else:
                # AUTO: Look for an Arduino device
                ports = [p.device for p in serial.tools.list_ports.comports() if "arduino" in p.description.lower() or "ch340" in p.description.lower()]
                if ports:
                    serial_conn = serial.Serial(ports[0], active_baudrate, timeout=0.01)
                    device.log(f"Arduino auto-detectado en {ports[0]}.")
                else:
                    use_simulator = True
                    device.log("No se detectó Arduino físico en puertos COM. Usando simulador de hardware.")
        except Exception as e:
            use_simulator = True
            device.log(f"No se pudo abrir puerto COM ({e}). Activando simulador de hardware.")

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
            except Exception:
                time.sleep(0.005)
                continue
        else:
            time.sleep(0.01)
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

        # Send live telemetry to GUI (progress bars)
        device.send_telemetry({"pedals_telemetry": [gas_norm, brake_norm, clutch_norm]}, pad_id=1)

        # Maintain ~120 Hz loop (8.3 ms per tick)
        elapsed = time.perf_counter() - t0
        rem = 0.0083 - elapsed
        if rem > 0:
            time.sleep(rem)


if __name__ == "__main__":
    device.start(run_loop)
