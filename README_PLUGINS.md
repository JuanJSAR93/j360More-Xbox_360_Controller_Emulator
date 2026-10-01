# j360More Extensible Plugin System — Comprehensive Development & Real Hardware Guide

Welcome to the official developer and hardware creator documentation for the **j360More** plugin system.

This guide covers everything from core architecture to building custom plugins from scratch, designing declarative user interfaces without writing GUI code, and connecting **real physical hardware** (Arduino/ESP32 and USB-MIDI keyboards/pads) without relying on emulation.

---

## Table of Contents

1. [System Architecture and Philosophy](#1-system-architecture-and-philosophy)
   - [Process Isolation and IPC](#11-process-isolation-and-ipc)
   - [Automated Virtual Environment (.venv)](#12-automated-virtual-environment-venv)
2. [Plugin Anatomy and Creation Step-by-Step](#2-plugin-anatomy-and-creation-step-by-step)
   - [Directory Structure](#21-directory-structure)
   - [The Manifest (`plugin.json`)](#22-the-manifest-pluginjson)
   - [Execution Lifecycle](#23-execution-lifecycle)
3. [Declarative Custom User Interfaces (UI)](#3-declarative-custom-user-interfaces-ui)
   - [Global Settings Dialog (`global_ui`)](#31-global-settings-dialog-global_ui)
   - [Dynamic Dropdowns (`dynamic_dropdown`) with Live Scan](#32-dynamic-dropdowns-with-live-scan)
   - [Per-Pad Custom Tabs (`pad_ui_customization`)](#33-per-pad-custom-tabs-pad_ui_customization)
   - [Real-Time Telemetry Monitors (`progress_bar_multi`)](#34-real-time-telemetry-monitors-progress_bar_multi)
4. [Multi-Language Support (i18n)](#4-multi-language-support-i18n)
   - [Inline Approach in `plugin.json`](#41-inline-approach-in-pluginjson)
   - [Modular Approach with `locales/` Files](#42-modular-approach-with-locales-files)
5. [Real Physical Hardware 1: Arduino / ESP32 (Pedals, Wheels, Handbrake)](#5-real-physical-hardware-1-arduino--esp32-pedals-wheels-handbrake)
   - [Circuit and Pin Wiring](#51-circuit-and-pin-wiring)
   - [Full Arduino C++ Firmware (`pedals_firmware.ino`)](#52-full-arduino-c-firmware-pedals_firmwareino)
   - [Python Plugin Script (`main.py`)](#53-python-plugin-script-mainpy)
6. [Real Physical Hardware 2: Synthesizers, Pianos, and MIDI Pads](#6-real-physical-hardware-2-synthesizers-pianos-and-midi-pads)
   - [Filtering Ports on Windows (Input vs Output)](#61-filtering-ports-on-windows-input-vs-output)
   - [Real-Time Polling with `pygame.midi`](#62-real-time-polling-with-pygamemidi)
   - [Mapping Pitch Bend, Modulation Wheel, and Keys to Xbox Controls](#63-mapping-pitch-bend-modulation-wheel-and-keys-to-xbox-controls)
7. [Complete Python SDK Reference (`PluginDevice`)](#7-complete-python-sdk-reference-plugindevice)
   - [Semantic vs Indexed Controls](#71-semantic-vs-indexed-controls)
   - [Haptic Feedback / Force Feedback (Rumble)](#72-haptic-feedback--force-feedback-rumble)
   - [Atomic Synchronization and Telemetry](#73-atomic-synchronization-and-telemetry)
8. [Troubleshooting and Diagnostics](#8-troubleshooting-and-diagnostics)

---

## 1. System Architecture and Philosophy

The **j360More** plugin engine was engineered around a core principle: **maximum stability with zero impact on gameplay latency**.

### 1.1. Process Isolation and IPC

Traditionally, loading third-party scripts into the main execution thread of an emulator or GUI framework risks freezing player inputs whenever a blocking I/O call occurs (such as waiting for serial COM buffer data or socket timeouts).

In j360More:
1. Every active plugin runs in its own child process (`subprocess.Popen`) using the dedicated virtual environment Python interpreter.
2. Inter-Process Communication (IPC) is handled via lightweight local TCP sockets (`127.0.0.1`) transferring compact JSON packets.
3. The virtual controller dispatch loop runs at **120 Hz**, reading shared state within microseconds to guarantee that any external physical hardware delay will never degrade other controllers' performance.

```
┌────────────────────────────────────────────────────────┐
│               j360More Core (120 Hz)                   │
│   - ViGEmBus / VIIPER Dispatcher                       │
│   - Tkinter GUI with Telemetry Monitor (~33 FPS)       │
│   - Local TCP IPC Server (127.0.0.1:AssignedPort)      │
└──────────────────────────┬─────────────────────────────┘
                           │ JSON TCP Socket
        ┌──────────────────┴──────────────────┐
        ▼                                     ▼
┌───────────────────────────┐     ┌───────────────────────────┐
│ Plugin 1 (Child Process)  │     │ Plugin 2 (Child Process)  │
│ - Arduino Pedals          │     │ - USB-MIDI Controller     │
│ - pyserial @ 115200 baud  │     │ - pygame.midi @ 120 Hz    │
└───────────────────────────┘     └───────────────────────────┘
```

### 1.2. Automated Virtual Environment (`.venv`)

To ensure end users never need to install Python globally or manage terminal commands:
- When opening the `🔌 Plugins` tab, j360More checks for `plugins/.venv`.
- If missing or lacking packages, the interface cleanly displays a notice with a single-click button: **"Install Plugin Dependencies"**.
- Dependencies are isolated from the OS.
- For MIDI controllers, `pygame-ce` is used instead of packages requiring external C++ compilers, ensuring trouble-free installation across Windows 10 and 11.

---

## 2. Plugin Anatomy and Creation Step-by-Step

### 2.1. Directory Structure

Each plugin resides in its own folder inside `plugins/`:

```
plugins/
└── my_device/
    ├── plugin.json         # Metadata, declarative UI schema, and options
    ├── main.py             # Main executable Python script
    ├── requirements.txt    # PyPI requirements (e.g. pyserial, pygame-ce)
    └── locales/            # (Optional) External translations
        ├── en.json
        └── es.json
```

### 2.2. The Manifest (`plugin.json`)

The `plugin.json` file declares your plugin, provided devices, and user-configurable parameters:

```json
{
  "id": "my_device",
  "name": "My Custom Device",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "Custom hardware controller for j360More",
  "entry_point": "main.py",
  "devices": [
    {
      "id": "custom_pad",
      "name": "Custom Pad",
      "type": "gamepad",
      "num_buttons": 16,
      "num_axes": 6
    }
  ]
}
```

j360More registers it under the global device identifier:
`plugin:my_device:custom_pad`

### 2.3. Execution Lifecycle

1. **Discovery**: On launch, `PluginManager` discovers `plugins/*/plugin.json`.
2. **Startup**: When emulation starts or the plugin is toggled ON, `main.py --port <TCP_PORT> --id <PLUGIN_ID>` is launched.
3. **IPC Handshake**: The script connects via `PluginDevice` and identifies itself.
4. **Mapping Loop**: The script polls hardware and calls `device.flush()`.
5. **Clean Shutdown**: When emulation stops, `device.is_running()` becomes `False`; the script safely releases serial ports or MIDI streams before exiting.

---

## 3. Declarative Custom User Interfaces (UI)

With j360More, **you don't need to write any GUI code (Tkinter, PyQt, etc.)** to provide a polished configuration experience. Everything is declared inside `plugin.json`.

### 3.1. Global Settings Dialog (`global_ui`)

Clicking the `⚙ Configure` button next to any plugin opens a dynamic dialog generated from `"global_ui"`:

Supported field types:
- **`slider`**: Numeric value with `min`, `max`, `step`, and `default`.
- **`checkbox`**: Boolean toggle (`true`/`false`).
- **`dropdown`**: Static select menu.
- **`dynamic_dropdown`**: Select menu with a `🔄` refresh button invoking live plugin discovery.

Example:

```json
"global_ui": {
  "title": { "es": "Ajustes de Mi Dispositivo", "en": "My Device Settings" },
  "fields": [
    {
      "id": "serial_baud",
      "label": { "es": "Velocidad de Baudios", "en": "Baud Rate" },
      "type": "dropdown",
      "options": ["9600", "57600", "115200"],
      "default": "115200"
    },
    {
      "id": "invert_axes",
      "label": { "es": "Invertir Ejes Analógicos", "en": "Invert Analog Axes" },
      "type": "checkbox",
      "default": false
    }
  ]
}
```

### 3.2. Dynamic Dropdowns with Live Scan

To allow users to select COM ports or MIDI interfaces dynamically:

```json
{
  "id": "port",
  "label": { "es": "Puerto Serie COM", "en": "Serial COM Port" },
  "type": "dynamic_dropdown",
  "discovery_action": "scan_ports",
  "default": "Auto"
}
```

In `main.py`, register the action callback:

```python
def handle_scan_ports(params):
    import serial.tools.list_ports
    ports = ["Auto"] + [p.device for p in serial.tools.list_ports.comports()]
    return {"options": ports}

device.on_action("scan_ports", handle_scan_ports)
```

### 3.3. Per-Pad Custom Tabs (`pad_ui_customization`)

If your plugin provides specialized hardware (such as racing pedals without analog sticks or a steering wheel with rotation angles), you can inject custom tabs directly into the selected gamepad's view:

```json
"pad_ui_customization": {
  "disable_default_tabs": ["sticks"],
  "custom_tabs": [
    {
      "id": "pedals_calibration",
      "title": { "es": "🏎️ Pedales", "en": "🏎️ Pedals" },
      "sections": [
        {
          "title": { "es": "Calibración de Recorrido", "en": "Travel Calibration" },
          "fields": [
            {
              "id": "deadzone_gas",
              "label": { "es": "Zona Muerta Acelerador (%)", "en": "Gas Deadzone (%)" },
              "type": "slider",
              "min": 0,
              "max": 30,
              "step": 1,
              "default": 3
            }
          ]
        }
      ]
    }
  ]
}
```

### 3.4. Real-Time Telemetry Monitors (`progress_bar_multi`)

To display live, animated activity bars in the GUI:

```json
{
  "id": "pedals_monitor",
  "type": "progress_bar_multi",
  "label": { "es": "Monitor de Recorrido Físico", "en": "Physical Travel Monitor" },
  "bars": 3,
  "labels": ["GAS", "BRAKE", "CLUTCH"],
  "center_zero": false
}
```

- `center_zero: false`: Grows from 0% to 100% (ideal for pedals and triggers).
- `center_zero: true`: Centers at 50% and expands left/right (ideal for thumbsticks and pitch wheels).

Throttle telemetry to approximately **33 FPS** (~30 milliseconds) to maintain a fluid GUI without burdening Tkinter:

```python
now = time.perf_counter()
if now - last_telemetry >= 0.03:
    device.send_telemetry({
        "pedals_monitor": [gas_val, brake_val, clutch_val]
    }, pad_id=0)
    last_telemetry = now
```

---

## 4. Multi-Language Support (i18n)

The plugin architecture integrates natively with the 7 supported languages in j360More (English, Spanish, French, Portuguese, German, Italian, Russian).

### 4.1. Inline Approach in `plugin.json`

```json
"label": {
  "en": "Response Sensitivity",
  "es": "Sensibilidad de Respuesta",
  "fr": "Sensibilité de Réponse"
}
```

### 4.2. Modular Approach with `locales/` Files

For larger projects, create JSON files in `locales/`:

`plugins/my_device/locales/en.json`:
```json
{
  "tab_title": "🏎️ Calibration",
  "sec_calibration": "Travel Adjustment",
  "lbl_deadzone": "Deadzone (%)"
}
```

`plugins/my_device/locales/es.json`:
```json
{
  "tab_title": "🏎️ Calibración",
  "sec_calibration": "Ajuste de Recorrido",
  "lbl_deadzone": "Zona Muerta (%)"
}
```

Reference the translation keys directly in `plugin.json`:
```json
"title": "tab_title",
"label": "lbl_deadzone"
```

---

## 5. Real Physical Hardware 1: Arduino / ESP32 (Pedals, Wheels, Handbrake)

Here is how to build and flash a physical USB controller using linear potentiometers and an Arduino micro-board.

### 5.1. Circuit and Pin Wiring

Connect three **10 kΩ linear potentiometers**:

```
Arduino Nano / Uno / ESP32:
              ┌───────────────────────────┐
              │ 5V / 3.3V ───► Terminal 1 │
              │ GND       ───► Terminal 3 │
              │                           │
  Gas Pedal   │ A0        ───► Terminal 2 (Center Pin / Wiper)
  Brake Pedal │ A1        ───► Terminal 2 (Center Pin / Wiper)
  Clutch      │ A2        ───► Terminal 2 (Center Pin / Wiper)
              │                           │
  Button 1    │ D2        ───► Pushbutton to GND (INPUT_PULLUP)
  Button 2    │ D3        ───► Pushbutton to GND (INPUT_PULLUP)
              └───────────────────────────┘
```

### 5.2. Full Arduino C++ Firmware (`pedals_firmware.ino`)

Flash this sketch via **Arduino IDE** (compatible with Arduino Nano, Uno, Leonardo, Pro Micro, ESP32):

```cpp
/*
 * j360More - Physical Pedals & Wheel USB Firmware
 * Serial Baud Rate: 115200 (Latency < 2ms)
 */

const int PIN_GAS   = A0;
const int PIN_BRAKE = A1;
const int PIN_CLUTCH= A2;
const int PIN_BTN1  = 2;
const int PIN_BTN2  = 3;

// Exponential low-pass filter to remove electrical jitter
float smoothGas    = 0.0;
float smoothBrake  = 0.0;
float smoothClutch = 0.0;
const float ALPHA  = 0.25; // Smoothing factor (0.1 = smooth, 0.9 = instant)

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000);

  pinMode(PIN_BTN1, INPUT_PULLUP);
  pinMode(PIN_BTN2, INPUT_PULLUP);

  smoothGas    = analogRead(PIN_GAS);
  smoothBrake  = analogRead(PIN_BRAKE);
  smoothClutch = analogRead(PIN_CLUTCH);
}

void loop() {
  // 1. 10-bit analog readings (0 - 1023)
  int rawGas    = analogRead(PIN_GAS);
  int rawBrake  = analogRead(PIN_BRAKE);
  int rawClutch = analogRead(PIN_CLUTCH);

  // 2. Apply low-pass filtering
  smoothGas    = (ALPHA * rawGas)    + ((1.0 - ALPHA) * smoothGas);
  smoothBrake  = (ALPHA * rawBrake)  + ((1.0 - ALPHA) * smoothBrake);
  smoothClutch = (ALPHA * rawClutch) + ((1.0 - ALPHA) * smoothClutch);

  // 3. Digital buttons (inverted logic with PULLUP)
  int btn1 = (digitalRead(PIN_BTN1) == LOW) ? 1 : 0;
  int btn2 = (digitalRead(PIN_BTN2) == LOW) ? 1 : 0;

  // 4. Send compact packet over serial
  // Format: GAS:val,BRK:val,CLT:val,BTN1:val,BTN2:val\n
  Serial.print("GAS:");
  Serial.print((int)smoothGas);
  Serial.print(",BRK:");
  Serial.print((int)smoothBrake);
  Serial.print(",CLT:");
  Serial.print((int)smoothClutch);
  Serial.print(",BTN1:");
  Serial.print(btn1);
  Serial.print(",BTN2:");
  Serial.println(btn2);

  // Loop dispatch at ~100 Hz (10 ms)
  delay(10);
}
```

### 5.3. Python Plugin Script (`main.py`)

Create `plugins/arduino_pedals/main.py`:

```python
import sys
import time
import serial
import serial.tools.list_ports
from plugins.plugin_sdk import PluginDevice

# Initialize device with 2 analog axes (Triggers LT/RT) and 2 buttons
device = PluginDevice(
    id="arduino_pedals",
    name="Arduino Pedals Controller",
    num_buttons=2,
    num_axes=2
)

active_port = "Auto"
baud_rate = 115200
ser = None

def get_best_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = p.description.lower()
        if "arduino" in desc or "ch340" in desc or "cp210" in desc:
            return p.device
    return ports[0].device if ports else None

def map_axis(val, min_in=50, max_in=950):
    """Maps 0-1023 to 0.0 - 1.0 with deadzone clamp"""
    clamped = max(min_in, min(max_in, val))
    return (clamped - min_in) / float(max_in - min_in)

last_telemetry = 0.0

try:
    while device.is_running():
        # Automatic hot-plug reconnection if USB disconnects
        if ser is None or not ser.is_open:
            port_to_open = get_best_port() if active_port == "Auto" else active_port
            if port_to_open:
                try:
                    ser = serial.Serial(port_to_open, baud_rate, timeout=0.02)
                    time.sleep(0.5)
                except Exception:
                    ser = None
                    time.sleep(1.0)
                    continue
            else:
                time.sleep(1.0)
                continue

        try:
            line = ser.readline().decode("ascii", errors="ignore").strip()
            if line:
                data = dict(item.split(":") for item in line.split(",") if ":" in item)
                
                gas_raw = int(data.get("GAS", 0))
                brake_raw = int(data.get("BRK", 0))
                clutch_raw = int(data.get("CLT", 0))
                btn1 = int(data.get("BTN1", 0)) == 1
                btn2 = int(data.get("BTN2", 0)) == 1

                gas_norm = map_axis(gas_raw)
                brake_norm = map_axis(brake_raw)

                # Direct semantic mapping to Xbox controller triggers
                device.set_trigger("RT", gas_norm)    # Accelerator
                device.set_trigger("LT", brake_norm)  # Brake
                device.set_button("A", btn1)
                device.set_button("B", btn2)
                device.flush()

                # Telemetry at ~33 FPS for GUI monitors
                now = time.perf_counter()
                if now - last_telemetry >= 0.03:
                    device.send_telemetry({
                        "pedals_monitor": [gas_norm, brake_norm, map_axis(clutch_raw)]
                    }, pad_id=0)
                    last_telemetry = now

        except serial.SerialException:
            ser = None # Trigger reconnect

        time.sleep(0.005) # 200 Hz loop
finally:
    if ser and ser.is_open:
        ser.close()
```

---

## 6. Real Physical Hardware 2: Synthesizers, Pianos, and MIDI Pads

Any standard USB musical keyboard, MIDI pad controller (such as Novation Launchpad or Akai MPK), or DIN-5 adapter works directly.

### 6.1. Filtering Ports on Windows (Input vs Output)

Windows enumerates MIDI ports that are **output-only** (like `Microsoft GS Wavetable Synth`). Opening an output port for input causes an immediate descriptor error.

Always filter for `is_input == 1`:

```python
import pygame.midi

pygame.midi.init()
input_devices = []
for dev_id in range(pygame.midi.get_count()):
    interf, name, is_input, is_output, opened = pygame.midi.get_device_info(dev_id)
    if is_input == 1:
        dev_name = name.decode("utf-8", errors="ignore")
        input_devices.append((dev_id, dev_name))
```

### 6.2. Real-Time Polling with `pygame.midi`

`pygame.midi` delivers ultra-low latency direct access to Windows multimedia streams:

```python
midi_in = pygame.midi.Input(target_device_id)

while device.is_running():
    if midi_in.poll():
        events = midi_in.read(16)
        for event in events:
            status = event[0][0]
            data1  = event[0][1] # Note or CC number
            data2  = event[0][2] # Velocity or CC value
            ...
```

### 6.3. Mapping Pitch Bend, Modulation Wheel, and Keys to Xbox Controls

| MIDI Message | Status Byte | Data | Recommended Xbox 360 Mapping |
| :--- | :--- | :--- | :--- |
| **Note On** | `0x90` | Key pressed (`velocity > 0`) | Buttons `A`, `B`, `X`, `Y`, `LB`, `RB` or D-Pad |
| **Note Off** | `0x80` (or `0x90` vel 0) | Key released | Release corresponding button |
| **Pitch Bend** | `0xE0` | 14-bit pitch wheel (0-16383, 8192 center) | Left thumbstick horizontal (`LX`: -1.0 to +1.0) |
| **Modulation Wheel** | `0xB0` (CC #1) | Modulation wheel (0 to 127) | Right trigger (`RT`: 0.0 to 1.0) |

Mapping code:

```python
# Pitch Bend Wheel (14-bit) to Left Thumbstick LX (-1.0 to +1.0)
if status == 0xE0:
    pitch_14bit = (data2 << 7) | data1
    normalized_stick = (pitch_14bit - 8192) / 8192.0
    device.set_stick("LX", max(-1.0, min(1.0, normalized_stick)))
    device.flush()

# Modulation Wheel (CC 1) to Right Trigger RT (0.0 to 1.0)
elif status == 0xB0 and data1 == 1:
    normalized_trigger = data2 / 127.0
    device.set_trigger("RT", normalized_trigger)
    device.flush()

# Key to Button (e.g. Note 60 = Middle C -> Button A)
elif (status & 0xF0) == 0x90:
    is_pressed = (data2 > 0)
    if data1 == 60:
        device.set_button("A", is_pressed)
    elif data1 == 62:
        device.set_button("B", is_pressed)
    device.flush()
```

---

## 7. Complete Python SDK Reference (`PluginDevice`)

Located in `plugins/plugin_sdk.py`, `PluginDevice` abstracts all TCP socket serialization.

### 7.1. Semantic vs Indexed Controls

#### Semantic Controls (Recommended):
- `device.set_button(name: str, pressed: bool)`: `"A"`, `"B"`, `"X"`, `"Y"`, `"LB"`, `"RB"`, `"BACK"`, `"START"`, `"GUIDE"`, `"L3"`, `"R3"`, `"DPAD_UP"`, `"DPAD_DOWN"`, `"DPAD_LEFT"`, `"DPAD_RIGHT"`.
- `device.set_trigger(name: str, value: float)`: `"LT"`, `"RT"`. Range: `0.0` to `1.0`.
- `device.set_stick(name: str, value: float)`: `"LX"`, `"LY"`, `"RX"`, `"RY"`. Range: `-1.0` to `1.0`.

#### Indexed Physical Controls:
- `device.set_button_index(index: int, pressed: bool)`: Assigns physical button `0..N`.
- `device.set_axis(index: int, value: float)`: Assigns analog axis `0..M` (`-1.0` to `1.0`).

### 7.2. Haptic Feedback / Force Feedback (Rumble)

The emulator forwards game force feedback commands to plugins in real time:

```python
def on_rumble_received(small_motor: float, large_motor: float):
    # small_motor (high frequency): 0.0 to 1.0
    # large_motor (low frequency): 0.0 to 1.0
    if ser and ser.is_open:
        cmd = f"RUMBLE:{int(large_motor * 255)},{int(small_motor * 255)}\n"
        ser.write(cmd.encode("ascii"))

device.on_rumble(on_rumble_received)
```

### 7.3. Atomic Synchronization and Telemetry

- **`device.flush()`**: Flushes buffered button and axis modifications in a single atomic TCP payload. Call at the end of every poll cycle.
- **`device.send_telemetry(payload: dict, pad_id: int = 0)`**: Streams real-time values to GUI canvas monitors.
- **`device.on_field_change(callback)`**: Receives real-time updates when the user adjusts configuration sliders without restarting the plugin.

---

## 8. Troubleshooting and Diagnostics

### Built-in Plugin Console
Inside the `🔌 Plugins` tab, j360More provides a **Live Debug Console**. Any `print(...)` statement or exception traceback from `main.py` appears here instantly.

### Common Issues:
1. **Error: `PermissionError: [Errno 13] could not open port 'COMx'`**:
   - *Cause*: Another program has the port open (frequently the **Arduino IDE Serial Monitor** or 3D printer slicers).
   - *Fix*: Close the Arduino Serial Monitor window.
2. **Telemetry Monitor is inactive**:
   - Verify that the dictionary key sent to `device.send_telemetry({"my_monitor": [...]})` matches the `id` declared in `plugin.json`.
3. **MIDI device missing from dropdown**:
   - Click the `🔄` button next to the dropdown to rescan ports.
4. **Development without hardware**:
   - Add `"simulate": true` to `global_ui`. In `main.py`, check this flag and generate test sinusoidal curves via `math.sin(time.time())` to preview mapping before connecting wires.

---

You now have all the tools to build custom hardware controllers or integrate external instruments with **j360More**!
