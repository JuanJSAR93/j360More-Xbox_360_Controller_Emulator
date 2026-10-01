"""
plugins/plugin_sdk.py
High-level, developer-friendly SDK for j360More plugins.
Allows makers and community developers to easily send buttons, triggers, sticks,
receive rumble feedback, stream telemetry, and customize UI tabs without low-level IPC knowledge.
"""

import argparse
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Union

from plugins.plugin_ipc import IPCClient


class PluginDevice:
    """
    Virtual peripheral representation.
    Provides semantic methods (press_button, set_trigger, set_stick)
    and physical indexed methods (set_axis, set_button_index).
    """

    VALID_BUTTONS = {
        "A", "B", "X", "Y", "LB", "RB", "BACK", "START", "GUIDE",
        "L3", "R3", "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT"
    }

    def __init__(self, id: str, name: str, num_buttons: int = 16, num_axes: int = 6):
        self.id = id
        self.name = name
        self.num_buttons = num_buttons
        self.num_axes = num_axes

        # Internal state buffers
        self._buttons: Dict[int, bool] = {i: False for i in range(num_buttons)}
        self._named_buttons: Dict[str, bool] = {btn: False for btn in self.VALID_BUTTONS}
        self._axes: Dict[int, float] = {i: 0.0 for i in range(num_axes)}
        self._triggers: Dict[str, float] = {"LT": 0.0, "RT": 0.0}
        self._sticks: Dict[str, float] = {"LX": 0.0, "LY": 0.0, "RX": 0.0, "RY": 0.0}
        self._device_connected: bool = True

        self._state_lock = threading.Lock()
        self._ipc_client: Optional[IPCClient] = None
        self._running = False
        self._is_simulated = False

        # Event callbacks
        self._rumble_callback: Optional[Callable[[float, float], None]] = None
        self._discovery_callback: Optional[Callable[[], List[Dict[str, Any]]]] = None
        self._field_change_callbacks: Dict[str, List[Callable[[Any, int], None]]] = {}
        self._general_config_callbacks: List[Callable[[str, Any, int], None]] = []
        self._action_callbacks: Dict[str, List[Callable[[int], None]]] = {}

    # ---------------------------------------------------------
    # High-level Semantic Controls
    # ---------------------------------------------------------

    def press_button(self, name: str):
        """Presses a named gamepad button (e.g. 'A', 'B', 'LB')."""
        self.set_button(name, True)

    def release_button(self, name: str):
        """Releases a named gamepad button."""
        self.set_button(name, False)

    def set_button(self, name: str, is_pressed: bool):
        """Sets the state of a named gamepad button."""
        name_upper = str(name).upper()
        with self._state_lock:
            self._named_buttons[name_upper] = bool(is_pressed)

    def set_trigger(self, name: str, value: float):
        """Sets an analog trigger ('LT' or 'RT') value clamped between 0.0 and 1.0."""
        name_upper = str(name).upper()
        if name_upper not in ("LT", "RT"):
            return
        clamped = max(0.0, min(1.0, float(value)))
        with self._state_lock:
            self._triggers[name_upper] = clamped

    def set_stick(self, *args, **kwargs):
        """
        Sets stick axis values (-1.0 to 1.0).
        Extremely flexible signature supporting:
            set_stick('left', 0.5, -0.2)
            set_stick('left', x=0.5, y=-0.2)
            set_stick('LX', 0.5)
            set_stick('LX', 0.5, 'LY', -0.25)
            set_stick(LX=0.5, LY=-0.25)
        """
        with self._state_lock:
            # 1. Process keyword arguments
            for k, v in kwargs.items():
                k_norm = k.upper().replace("_", "")
                if k_norm in ("LX", "LEFTX"):
                    self._sticks["LX"] = max(-1.0, min(1.0, float(v)))
                elif k_norm in ("LY", "LEFTY"):
                    self._sticks["LY"] = max(-1.0, min(1.0, float(v)))
                elif k_norm in ("RX", "RIGHTX"):
                    self._sticks["RX"] = max(-1.0, min(1.0, float(v)))
                elif k_norm in ("RY", "RIGHTY"):
                    self._sticks["RY"] = max(-1.0, min(1.0, float(v)))

            # 2. Process positional arguments
            if not args:
                return

            # Pattern A: set_stick('left', 0.5, -0.2)
            first = str(args[0]).upper()
            if first in ("LEFT", "L"):
                if len(args) > 1 and args[1] is not None:
                    self._sticks["LX"] = max(-1.0, min(1.0, float(args[1])))
                if len(args) > 2 and args[2] is not None:
                    self._sticks["LY"] = max(-1.0, min(1.0, float(args[2])))
                return
            elif first in ("RIGHT", "R"):
                if len(args) > 1 and args[1] is not None:
                    self._sticks["RX"] = max(-1.0, min(1.0, float(args[1])))
                if len(args) > 2 and args[2] is not None:
                    self._sticks["RY"] = max(-1.0, min(1.0, float(args[2])))
                return

            # Pattern B: alternating pairs, e.g. set_stick('LX', 0.5, 'LY', -0.25)
            # or single pair set_stick('LX', 0.5)
            i = 0
            while i < len(args):
                name = str(args[i]).upper()
                if i + 1 < len(args) and not isinstance(args[i + 1], str):
                    val = float(args[i + 1])
                    if name in ("LX", "LY", "RX", "RY"):
                        self._sticks[name] = max(-1.0, min(1.0, val))
                    i += 2
                else:
                    i += 1

    # ---------------------------------------------------------
    # Physical / Indexed Controls
    # ---------------------------------------------------------

    def set_axis(self, axis_index: int, value: float):
        """Sets an indexed analog axis (-1.0 to 1.0) for manual user mapping."""
        idx = int(axis_index)
        clamped = max(-1.0, min(1.0, float(value)))
        with self._state_lock:
            self._axes[idx] = clamped

    def set_button_index(self, button_index: int, is_pressed: bool):
        """Sets an indexed button state (True/False) for manual user mapping."""
        idx = int(button_index)
        with self._state_lock:
            self._buttons[idx] = bool(is_pressed)

    # ---------------------------------------------------------
    # State Transmission, Connection Status & Telemetry
    # ---------------------------------------------------------

    def reset_inputs(self, flush: bool = False):
        """
        Resets all internal input states (buttons, triggers, sticks, axes) to neutral.
        Call this when physical hardware disconnects to prevent stuck inputs.
        """
        with self._state_lock:
            self._buttons = {i: False for i in range(self.num_buttons)}
            self._named_buttons = {btn: False for btn in self.VALID_BUTTONS}
            self._axes = {i: 0.0 for i in range(self.num_axes)}
            self._triggers = {"LT": 0.0, "RT": 0.0}
            self._sticks = {"LX": 0.0, "LY": 0.0, "RX": 0.0, "RY": 0.0}
        if flush:
            self.flush()

    def set_connected(self, is_connected: bool, device_id: Optional[str] = None):
        """
        Explicitly notifies j360More whether the physical peripheral is connected or disconnected.
        When set to False, automatically resets inputs to neutral to prevent stuck buttons or axes.
        """
        target_id = device_id or self.id
        self._device_connected = bool(is_connected)
        if not self._device_connected:
            self.reset_inputs(flush=False)

        if self._ipc_client and self._ipc_client.is_connected:
            self.flush()
            self._ipc_client.send({
                "event": "device_status",
                "device_id": target_id,
                "connected": self._device_connected
            })
        status_str = "CONECTADO" if self._device_connected else "DESCONECTADO"
        self.log(f"Estado de conexión de '{target_id}': {status_str}", "INFO")

    def is_device_connected(self) -> bool:
        """Returns True if the physical hardware is currently marked as connected."""
        return self._device_connected

    def report_devices(self, devices: List[Dict[str, Any]]):
        """
        Proactively notifies j360More about the list of currently connected physical devices.
        Allows instant hot-plug registration when devices are plugged or unplugged dynamically.
        """
        if self._ipc_client and self._ipc_client.is_connected:
            self._ipc_client.send({
                "event": "discovered_devices",
                "device_id": self.id,
                "devices": devices or []
            })

    def flush(self):
        """Sends the atomic controller state snapshot over IPC to j360More."""
        if not self._ipc_client or not self._ipc_client.is_connected:
            return

        with self._state_lock:
            payload = {
                "event": "state_update",
                "device_id": self.id,
                "connected": self._device_connected,
                "buttons": dict(self._buttons),
                "named_buttons": dict(self._named_buttons),
                "axes": dict(self._axes),
                "triggers": dict(self._triggers),
                "sticks": dict(self._sticks),
            }

        self._ipc_client.send(payload)

    def send_telemetry(self, data: Dict[str, Any], pad_id: int = 1):
        """Sends real-time telemetry (progress bars, graphs, VU-meters) to the GUI."""
        if not self._ipc_client or not self._ipc_client.is_connected:
            return
        payload = {
            "event": "telemetry",
            "device_id": self.id,
            "pad_id": pad_id,
            "data": data,
        }
        self._ipc_client.send(payload)

    def update_field_options(self, field_id: str, options: List[Any]):
        """Dynamically updates the options of a combobox/dropdown in the GUI."""
        if not self._ipc_client or not self._ipc_client.is_connected:
            return
        payload = {
            "event": "update_options",
            "device_id": self.id,
            "field_id": field_id,
            "options": options,
        }
        self._ipc_client.send(payload)

    def set_field_value(self, field_id: str, value: Any, pad_id: int = 1):
        """Pushes an updated value to a GUI field (e.g. after zero auto-calibration)."""
        if not self._ipc_client or not self._ipc_client.is_connected:
            return
        payload = {
            "event": "set_field_value",
            "device_id": self.id,
            "pad_id": pad_id,
            "field_id": field_id,
            "value": value,
        }
        self._ipc_client.send(payload)

    def log(self, message: str, level: str = "INFO"):
        """Sends a log line to be displayed in the j360More Plugins GUI console."""
        print(f"[{level}] {message}")
        if self._ipc_client and self._ipc_client.is_connected:
            self._ipc_client.send({
                "event": "log",
                "device_id": self.id,
                "level": level.upper(),
                "message": str(message)
            })

    # ---------------------------------------------------------
    # Event Decorators
    # ---------------------------------------------------------

    def on_rumble(self, func: Callable[[float, float], None]):
        """Decorator for receiving rumble / haptic force feedback (small_motor, large_motor: 0.0 - 1.0)."""
        self._rumble_callback = func
        return func

    def on_discover_devices(self, func: Callable[[], List[Dict[str, Any]]]):
        """Decorator for scanning and registering physical hardware devices (COM, MIDI)."""
        self._discovery_callback = func
        return func

    def on_field_change(self, field_id: str):
        """Decorator for listening to a specific UI widget change (slider, checkbox, etc.)."""
        def decorator(func: Callable[[Any, int], None]):
            self._field_change_callbacks.setdefault(field_id, []).append(func)
            return func
        return decorator

    def on_config_change(self, func: Callable[[str, Any, int], None]):
        """Decorator for listening to any configuration change event (field_id, new_value, pad_id)."""
        self._general_config_callbacks.append(func)
        return func

    def on_action(self, action_name: str):
        """Decorator for listening to UI action button clicks (e.g. 'calibrate_zero')."""
        def decorator(func: Callable[[int], None]):
            self._action_callbacks.setdefault(action_name, []).append(func)
            return func
        return decorator

    # ---------------------------------------------------------
    # Lifecycle & IPC Message Dispatch
    # ---------------------------------------------------------

    def _handle_ipc_message(self, msg: Dict[str, Any]):
        event = msg.get("event")
        if event == "rumble":
            if self._rumble_callback:
                small = float(msg.get("small_motor", 0.0))
                large = float(msg.get("large_motor", 0.0))
                try:
                    self._rumble_callback(small, large)
                except Exception as e:
                    self.log(f"Error in on_rumble: {e}", "ERROR")

        elif event == "field_change":
            field_id = msg.get("field")
            val = msg.get("val")
            pad = int(msg.get("pad", 1))

            for cb in self._field_change_callbacks.get(field_id, []):
                try:
                    cb(val, pad)
                except Exception as e:
                    self.log(f"Error in on_field_change({field_id}): {e}", "ERROR")

            for cb in self._general_config_callbacks:
                try:
                    cb(field_id, val, pad)
                except Exception as e:
                    self.log(f"Error in on_config_change: {e}", "ERROR")

        elif event == "ui_action":
            action = msg.get("action")
            pad = int(msg.get("pad", 1))
            for cb in self._action_callbacks.get(action, []):
                try:
                    cb(pad)
                except Exception as e:
                    self.log(f"Error in on_action({action}): {e}", "ERROR")

        elif event == "request_discovery":
            if self._discovery_callback:
                try:
                    devices = self._discovery_callback()
                    self._ipc_client.send({
                        "event": "discovered_devices",
                        "device_id": self.id,
                        "devices": devices or []
                    })
                except Exception as e:
                    self.log(f"Error in on_discover_devices: {e}", "ERROR")

    def is_running(self) -> bool:
        return self._running

    def start(self, loop_fn: Optional[Callable[[], None]] = None):
        """
        Parses CLI parameters, connects to j360More IPC, performs handshake,
        and starts loop_fn or keeps main thread responsive.
        """
        parser = argparse.ArgumentParser(description=f"j360More Plugin: {self.name}")
        parser.add_argument("--ipc-port", type=int, default=0, help="IPC TCP port on localhost")
        parser.add_argument("--ipc-host", type=str, default="127.0.0.1", help="IPC host")
        parser.add_argument("--unix-path", type=str, default=None, help="IPC Unix Domain Socket path")
        parser.add_argument("--simulate", action="store_true", help="Run in hardware simulation mode")
        args, _ = parser.parse_known_args()

        self._is_simulated = args.simulate

        if args.ipc_port > 0 or args.unix_path:
            self._ipc_client = IPCClient(host=args.ipc_host, port=args.ipc_port, unix_path=args.unix_path)
            self._ipc_client.add_on_message(self._handle_ipc_message)
            connected = self._ipc_client.connect(timeout=3.0)
            if connected:
                # Send Handshake
                self._ipc_client.send({
                    "event": "handshake",
                    "device_id": self.id,
                    "name": self.name,
                    "num_buttons": self.num_buttons,
                    "num_axes": self.num_axes,
                    "simulated": self._is_simulated
                })
            else:
                print(f"[WARN] Plugin {self.id}: Could not connect to IPC server. Running standalone.")

        self._running = True

        try:
            if loop_fn:
                loop_fn()
            else:
                while self._running:
                    time.sleep(1.0)
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False
            if self._ipc_client:
                self._ipc_client.close()
