import os
import sys
import time
import math
import threading
from typing import Dict, Any, Optional, Set, Tuple

try:
    import vgamepad as vg
    HAS_VGAMEPAD = True
except Exception:
    vg = None
    HAS_VGAMEPAD = False

import viiper_backend
from viiper_backend import (
    ViiperClient,
    XBOX_BUTTONS,
    XBOX_ONE_BUTTONS,
    DS4_BUTTONS,
    DUALSENSE_BUTTONS,
    NS2PRO_BUTTONS
)

from input_devices import DeviceManager
from i18n import canonicalize_mapping, is_none_mapping
import web_gamepad_server

if HAS_VGAMEPAD and vg is not None:
    BUTTON_VG_MAP = {
        "DPAD_UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
        "DPAD_DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
        "DPAD_LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
        "DPAD_RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
        "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
        "BACK": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
        "LEFT_THUMB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
        "RIGHT_THUMB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
        "LEFT_SHOULDER": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
        "RIGHT_SHOULDER": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
        "GUIDE": vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
        "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
        "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
        "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
        "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
    }

    DS4_BUTTON_VG_MAP = {
        "A": vg.DS4_BUTTONS.DS4_BUTTON_CROSS,
        "B": vg.DS4_BUTTONS.DS4_BUTTON_CIRCLE,
        "X": vg.DS4_BUTTONS.DS4_BUTTON_SQUARE,
        "Y": vg.DS4_BUTTONS.DS4_BUTTON_TRIANGLE,
        "LEFT_SHOULDER": vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT,
        "RIGHT_SHOULDER": vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT,
        "START": vg.DS4_BUTTONS.DS4_BUTTON_OPTIONS,
        "BACK": vg.DS4_BUTTONS.DS4_BUTTON_SHARE,
        "LEFT_THUMB": vg.DS4_BUTTONS.DS4_BUTTON_THUMB_LEFT,
        "RIGHT_THUMB": vg.DS4_BUTTONS.DS4_BUTTON_THUMB_RIGHT,
    }

    def get_ds4_dpad_direction(up: bool, down: bool, left: bool, right: bool):
        if up and right:
            return vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHEAST
        if up and left:
            return vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHWEST
        if down and right:
            return vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHEAST
        if down and left:
            return vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHWEST
        if up:
            return vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTH
        if down:
            return vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTH
        if left:
            return vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_WEST
        if right:
            return vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_EAST
        return vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NONE
else:
    BUTTON_VG_MAP = {
        "DPAD_UP": 1, "DPAD_DOWN": 2, "DPAD_LEFT": 4, "DPAD_RIGHT": 8,
        "START": 16, "BACK": 32, "LEFT_THUMB": 64, "RIGHT_THUMB": 128,
        "LEFT_SHOULDER": 256, "RIGHT_SHOULDER": 512, "GUIDE": 1024,
        "A": 4096, "B": 8192, "X": 16384, "Y": 32768,
    }
    DS4_BUTTON_VG_MAP = {
        "A": 1, "B": 2, "X": 4, "Y": 8,
        "LEFT_SHOULDER": 16, "RIGHT_SHOULDER": 32,
        "START": 64, "BACK": 128, "LEFT_THUMB": 256, "RIGHT_THUMB": 512
    }
    def get_ds4_dpad_direction(up: bool, down: bool, left: bool, right: bool):
        return 0

def apply_axis_calibration(val: float, deadzone_pct: float, anti_deadzone_pct: float, sensitivity_pct: float, invert: bool = False) -> float:
    """Aplica zona muerta, anti-deadzone, sensibilidad exponencial e inversion a un eje [-1.0, 1.0]."""
    if invert:
        val = -val

    d = max(0.0, min(0.99, deadzone_pct / 100.0))
    a = max(0.0, min(0.99, anti_deadzone_pct / 100.0))
    s = max(-10.0, min(10.0, sensitivity_pct / 100.0))

    abs_v = abs(val)
    if abs_v <= d:
        return 0.0

    # 1. Normalizar tras remover zona muerta
    norm_v = (abs_v - d) / (1.0 - d)

    # 2. Sensibilidad exponencial (curva x360ce)
    gamma = 2.0 ** (-s)
    sens_v = norm_v ** gamma

    # 3. Anti-zona muerta
    if a > 0.0:
        anti_v = a + (1.0 - a) * sens_v
    else:
        anti_v = sens_v

    sign = 1.0 if val >= 0 else -1.0
    return max(-1.0, min(1.0, sign * anti_v))

def apply_trigger_calibration(val: float, deadzone_pct: float, anti_deadzone_pct: float, sensitivity_pct: float, invert: bool = False) -> float:
    """Aplica zona muerta, anti-deadzone, sensibilidad exponencial e inversion a un gatillo [0.0, 1.0]."""
    if invert:
        val = 1.0 - val

    d = max(0.0, min(0.99, deadzone_pct / 100.0))
    a = max(0.0, min(0.99, anti_deadzone_pct / 100.0))
    s = max(-10.0, min(10.0, sensitivity_pct / 100.0))

    if val <= d:
        return 0.0

    norm_v = (val - d) / (1.0 - d)
    gamma = 2.0 ** (-s)
    sens_v = norm_v ** gamma

    if a > 0.0:
        res = a + (1.0 - a) * sens_v
    else:
        res = sens_v

    return max(0.0, min(1.0, res))

def get_pad_emulated_type(config: dict, pad_id: int) -> str:
    """Determina si un pad_id debe ser emulado como 'xbox360', 'xboxone', 'ds4', 'dualsense' o 'ns2pro'."""
    mode = config.get("emulated_type", "xbox360").lower()
    if mode in ("xboxone", "xbox_one", "ds4", "dualsense", "ns2pro"):
        return mode
    elif mode in ("mixed", "mixto"):
        max_ctrls = config.get("max_controllers", 8)
        half = max_ctrls // 2
        return "xbox360" if pad_id <= half else "ds4"
    return "xbox360"

def compile_mapping(mapping_str: str) -> Tuple:
    """Precompila un string de mapeo en una tupla rápida para evitar split/lower en el bucle principal."""
    if not mapping_str or is_none_mapping(mapping_str):
        return ("none",)
    clean = canonicalize_mapping(mapping_str.strip())
    low = clean.lower()
    if low.startswith("tecla: ") or low.startswith("key: "):
        k = clean.split(":", 1)[1].strip().lower()
        return ("key", k)
    if clean.startswith("Button "):
        try:
            b_idx = int(clean.split()[1]) - 1
            return ("button", b_idx)
        except Exception:
            return ("none",)
    if clean.startswith("POV "):
        parts = clean.split()
        try:
            h_idx = int(parts[1]) - 1
            dir_str = parts[2].lower()
            return ("pov", h_idx, dir_str)
        except Exception:
            return ("none",)
    if "Axis" in clean:
        inverted = clean.startswith("I")
        clean_no_i = clean[1:] if inverted else clean
        try:
            parts = clean_no_i.split()
            a_idx_str = parts[1]
            half_pos = a_idx_str.endswith("+")
            half_neg = a_idx_str.endswith("-")
            a_idx = int(a_idx_str.replace("+", "").replace("-", "")) - 1
            is_bipolar = not (half_pos or half_neg)
            return ("axis", a_idx, inverted, half_pos, half_neg, is_bipolar)
        except Exception:
            return ("none",)
    return ("none",)

def eval_compiled(compiled: Tuple, joy_state: Dict[str, Any], dev_id: str = "", pressed_keys: Optional[Set[str]] = None) -> Tuple[bool, float]:
    """Evalúa un mapeo precompilado con latencia mínima."""
    kind = compiled[0]
    if kind == "none":
        return False, 0.0
    if kind == "button":
        pressed = joy_state["buttons"].get(compiled[1], False)
        return pressed, (1.0 if pressed else 0.0)
    if kind == "pov":
        _, h_idx, dir_str = compiled
        hx, hy = joy_state["hats"].get(h_idx, (0, 0))
        if dir_str == "up": pressed = hy > 0
        elif dir_str == "down": pressed = hy < 0
        elif dir_str == "left": pressed = hx < 0
        elif dir_str == "right": pressed = hx > 0
        else: pressed = False
        return pressed, (1.0 if pressed else 0.0)
    if kind == "axis":
        _, a_idx, inverted, half_pos, half_neg, _ = compiled
        val = joy_state["axes"].get(a_idx, 0.0)
        if inverted: val = -val
        if half_pos: val = max(0.0, val)
        elif half_neg: val = max(0.0, -val)
        return val > 0.45, val
    if kind == "key":
        k = compiled[1]
        kbd_keys = joy_state.get("keys", set())
        pressed = any(
            k == (pk.split(":", 1)[1].strip().lower() if ":" in pk else pk.lower())
            for pk in kbd_keys
        )
        if not pressed and not dev_id.startswith("kbd_") and pressed_keys:
            pressed = k in pressed_keys
        return pressed, (1.0 if pressed else 0.0)
    return False, 0.0

class EmulatorEngine:
    def __init__(self, device_manager: DeviceManager):
        self.device_manager = device_manager
        self.config: Dict[str, Any] = {}
        self.gamepads: Dict[int, Any] = {}
        self.viiper_client: Optional[ViiperClient] = None
        self.driver_backend: str = "vigem"
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.input_event = threading.Event()
        self.compiled_mappings: Dict[int, Dict[str, Tuple]] = {}

        # Almacena el estado activo en tiempo real para reflejarlo en la GUI
        self.active_states: Dict[int, Dict[str, Any]] = {
            i: {
                "buttons": set(),
                "lt_raw": 0.0, "lt": 0,
                "rt_raw": 0.0, "rt": 0,
                "lx_raw": 0.0, "lx": 0.0,
                "ly_raw": 0.0, "ly": 0.0,
                "rx_raw": 0.0, "rx": 0.0,
                "ry_raw": 0.0, "ry": 0.0
            }
            for i in range(1, 13)
        }

        # Estado de teclas presionadas para mapeo de teclado
        self.pressed_keys: Set[str] = set()

    def set_config(self, config: Dict[str, Any]):
        with self.lock:
            self.config = config
            self._recompile_mappings()
        self.trigger_input_event()

    def _recompile_mappings(self):
        new_compiled = {}
        for p_id_str, p_cfg in self.config.get("controllers", {}).items():
            try:
                p_id = int(p_id_str)
            except Exception:
                continue
            m_dict = {}
            for target_btn, map_str in p_cfg.get("mappings", {}).items():
                m_dict[target_btn] = compile_mapping(map_str)
            new_compiled[p_id] = m_dict
        self.compiled_mappings = new_compiled

    def trigger_input_event(self):
        """Despierta el bucle de emulacion reactivamente ante nueva entrada."""
        self.input_event.set()

    def start(self):
        with self.lock:
            if self.running:
                return

            max_ctrls = self.config.get("max_controllers", 12)
            emulated_type = self.config.get("emulated_type", "xbox360").lower()
            if emulated_type in ("mixed", "mixto"):
                half = max_ctrls // 2
                ctrl_type_name = f"Mixto ({half}x Xbox 360 + {half}x DS4)"
            elif emulated_type in ("xboxone", "xbox_one"):
                ctrl_type_name = "Xbox One"
            elif emulated_type == "ds4":
                ctrl_type_name = "DualShock 4"
            elif emulated_type == "dualsense":
                ctrl_type_name = "DualSense (PS5)"
            elif emulated_type == "ns2pro":
                ctrl_type_name = "Switch 2 Pro"
            else:
                ctrl_type_name = "Xbox 360"

            backend = self.config.get("driver_backend", "vigem" if sys.platform == "win32" else "viiper").lower()
            if sys.platform != "win32":
                backend = "viiper"
            self.driver_backend = backend

            print(f"[*] Iniciando motor de emulacion {ctrl_type_name} usando backend [{self.driver_backend.upper()}] (hasta {max_ctrls} mandos)...")

            if self.driver_backend == "viiper":
                self.viiper_client = ViiperClient()
                if not self.viiper_client.start_bus():
                    print("[!] Error: No se pudo iniciar el bus de VIIPER.")
                    return
                for i in range(1, max_ctrls + 1):
                    cfg = self.config.get("controllers", {}).get(str(i), {})
                    p_dev = cfg.get("physical_device_id", "none")
                    if cfg.get("enabled", True) and p_dev and p_dev != "none":
                        pad_type = get_pad_emulated_type(self.config, i)
                        if not self.viiper_client.add_device(i, pad_type):
                            pad_label = pad_type.upper()
                            print(f"  [!] Error creando mando virtual #{i} ({pad_label}) en VIIPER.")
                active_count = len(self.viiper_client.devices)
            else:
                if not HAS_VGAMEPAD or vg is None:
                    print("[!] Error: ViGEmBus/vgamepad no está disponible en este sistema.")
                    return
                for i in range(1, max_ctrls + 1):
                    cfg = self.config.get("controllers", {}).get(str(i), {})
                    p_dev = cfg.get("physical_device_id", "none")
                    if cfg.get("enabled", True) and p_dev and p_dev != "none":
                        pad_type = get_pad_emulated_type(self.config, i)
                        try:
                            if pad_type == "ds4":
                                pad = vg.VDS4Gamepad()
                            else:
                                pad = vg.VX360Gamepad()
                            pad.reset()
                            pad.update()
                            self.gamepads[i] = pad

                            # Reenvío de vibración háptica a smartphone AirPad
                            if p_dev.startswith("phone_"):
                                try:
                                    def _make_rumble_cb(target_phone):
                                        def _rcb(client, target, large_motor, small_motor, led_number):
                                            srv = web_gamepad_server.get_server_instance()
                                            srv.send_rumble(target_phone, large_motor * 256, small_motor * 256)
                                        return _rcb
                                    pad.register_notification(callback_function=_make_rumble_cb(p_dev))
                                except Exception:
                                    pass
                        except Exception as e:
                            pad_label = "DualShock 4" if pad_type == "ds4" else "Xbox 360"
                            print(f"  [!] Error creando mando virtual #{i} ({pad_label}): {e}")
                active_count = len(self.gamepads)

            self.running = True
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            print(f"[+] Motor de emulacion iniciado con {active_count} mandos activos ({ctrl_type_name}) [{self.driver_backend.upper()}].")

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            self.input_event.set()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

        with self.lock:
            if self.driver_backend == "viiper" and self.viiper_client:
                try:
                    self.viiper_client.stop()
                except Exception as e:
                    print(f"[!] Error deteniendo VIIPER: {e}")
                self.viiper_client = None
            else:
                for i, pad in list(self.gamepads.items()):
                    try:
                        pad.reset()
                        pad.update()
                    except Exception:
                        pass
                self.gamepads.clear()

            for i in range(1, 13):
                self.active_states[i] = {
                    "buttons": set(),
                    "lt_raw": 0.0, "lt": 0,
                    "rt_raw": 0.0, "rt": 0,
                    "lx_raw": 0.0, "lx": 0.0,
                    "ly_raw": 0.0, "ly": 0.0,
                    "rx_raw": 0.0, "rx": 0.0,
                    "ry_raw": 0.0, "ry": 0.0
                }
            print("[+] Emulacion detenida y mandos liberados.")

    def is_running(self) -> bool:
        return self.running

    def get_active_state(self, pad_id: int) -> Dict[str, Any]:
        with self.lock:
            return dict(self.active_states.get(pad_id, {"buttons": set()}))

    def on_key_event(self, key_name: str, is_pressed: bool):
        with self.lock:
            if is_pressed:
                self.pressed_keys.add(key_name.lower())
            else:
                self.pressed_keys.discard(key_name.lower())
        self.trigger_input_event()

    def _eval_mapping(self, mapping_str: str, joy_state: Dict[str, Any], dev_id: str = "") -> Tuple[bool, float]:
        compiled = compile_mapping(mapping_str)
        return eval_compiled(compiled, joy_state, dev_id, getattr(self, "pressed_keys", None))

    def _loop(self):
        while self.running:
            self.device_manager.pump_events()

            with self.lock:
                controllers_cfg = self.config.get("controllers", {})
                is_viiper = (self.driver_backend == "viiper" and self.viiper_client is not None)
                if is_viiper:
                    active_pad_ids = list(self.viiper_client.devices.keys())
                else:
                    active_pad_ids = list(self.gamepads.keys())

            for pad_id in active_pad_ids:
                cfg = controllers_cfg.get(str(pad_id), {})
                if not cfg.get("enabled", True):
                    continue

                dev_id = cfg.get("physical_device_id", "none")
                joy_state = self.device_manager.read_physical_state(dev_id, pump=False)
                calib = cfg.get("calibration", {})

                # Calibraciones
                c_lt = calib.get("left_trigger", {})
                c_rt = calib.get("right_trigger", {})
                c_ls = calib.get("left_stick", {})
                c_rs = calib.get("right_stick", {})

                pressed_buttons = set()
                pad_type = get_pad_emulated_type(self.config, pad_id)
                is_ds4 = (pad_type in ("ds4", "dualsense"))
                is_ns2pro = (pad_type == "ns2pro")
                pad = self.gamepads.get(pad_id) if not is_viiper else None
                p_comp = self.compiled_mappings.get(pad_id, {})

                # 1. Botones Digitales
                for btn_name in ("A", "B", "X", "Y", "START", "BACK", "LEFT_THUMB", "RIGHT_THUMB", "LEFT_SHOULDER", "RIGHT_SHOULDER", "GUIDE"):
                    comp = p_comp.get(btn_name, ("none",))
                    is_pressed, _ = eval_compiled(comp, joy_state, dev_id, self.pressed_keys)
                    if is_pressed:
                        pressed_buttons.add(btn_name)

                is_d_up, _ = eval_compiled(p_comp.get("DPAD_UP", ("none",)), joy_state, dev_id, self.pressed_keys)
                is_d_down, _ = eval_compiled(p_comp.get("DPAD_DOWN", ("none",)), joy_state, dev_id, self.pressed_keys)
                is_d_left, _ = eval_compiled(p_comp.get("DPAD_LEFT", ("none",)), joy_state, dev_id, self.pressed_keys)
                is_d_right, _ = eval_compiled(p_comp.get("DPAD_RIGHT", ("none",)), joy_state, dev_id, self.pressed_keys)
                if is_d_up: pressed_buttons.add("DPAD_UP")
                if is_d_down: pressed_buttons.add("DPAD_DOWN")
                if is_d_left: pressed_buttons.add("DPAD_LEFT")
                if is_d_right: pressed_buttons.add("DPAD_RIGHT")

                # 2. Gatillo Izquierdo (LT)
                lt_comp = p_comp.get("LEFT_TRIGGER", ("none",))
                is_lt_pressed, lt_raw = eval_compiled(lt_comp, joy_state, dev_id, self.pressed_keys)
                if is_lt_pressed and lt_raw == 1.0 and lt_comp[0] != "axis":
                    lt_norm = 1.0
                else:
                    is_bipolar = (lt_comp[0] == "axis" and len(lt_comp) > 5 and lt_comp[5])
                    lt_norm = max(0.0, min(1.0, (lt_raw + 1.0) / 2.0 if is_bipolar else lt_raw))

                lt_calib = apply_trigger_calibration(
                    lt_norm,
                    deadzone_pct=c_lt.get("deadzone", 0),
                    anti_deadzone_pct=c_lt.get("anti_deadzone", 0),
                    sensitivity_pct=c_lt.get("sensitivity", 0),
                    invert=c_lt.get("invert", False)
                )
                lt_byte = int(lt_calib * 255)

                # Gatillo Derecho (RT)
                rt_comp = p_comp.get("RIGHT_TRIGGER", ("none",))
                is_rt_pressed, rt_raw = eval_compiled(rt_comp, joy_state, dev_id, self.pressed_keys)
                if is_rt_pressed and rt_raw == 1.0 and rt_comp[0] != "axis":
                    rt_norm = 1.0
                else:
                    is_bipolar = (rt_comp[0] == "axis" and len(rt_comp) > 5 and rt_comp[5])
                    rt_norm = max(0.0, min(1.0, (rt_raw + 1.0) / 2.0 if is_bipolar else rt_raw))

                rt_calib = apply_trigger_calibration(
                    rt_norm,
                    deadzone_pct=c_rt.get("deadzone", 0),
                    anti_deadzone_pct=c_rt.get("anti_deadzone", 0),
                    sensitivity_pct=c_rt.get("sensitivity", 0),
                    invert=c_rt.get("invert", False)
                )
                rt_byte = int(rt_calib * 255)

                # 3. Stick Izquierdo (LS)
                _, lx_axis = eval_compiled(p_comp.get("LEFT_STICK_X", ("none",)), joy_state, dev_id, self.pressed_keys)
                _, ly_axis = eval_compiled(p_comp.get("LEFT_STICK_Y", ("none",)), joy_state, dev_id, self.pressed_keys)

                is_l_up, _ = eval_compiled(p_comp.get("LEFT_STICK_UP", ("none",)), joy_state, dev_id, self.pressed_keys)
                is_l_down, _ = eval_compiled(p_comp.get("LEFT_STICK_DOWN", ("none",)), joy_state, dev_id, self.pressed_keys)
                is_l_left, _ = eval_compiled(p_comp.get("LEFT_STICK_LEFT", ("none",)), joy_state, dev_id, self.pressed_keys)
                is_l_right, _ = eval_compiled(p_comp.get("LEFT_STICK_RIGHT", ("none",)), joy_state, dev_id, self.pressed_keys)

                if is_l_up: pressed_buttons.add("LEFT_STICK_UP")
                if is_l_down: pressed_buttons.add("LEFT_STICK_DOWN")
                if is_l_left: pressed_buttons.add("LEFT_STICK_LEFT")
                if is_l_right: pressed_buttons.add("LEFT_STICK_RIGHT")

                dig_lx = (1.0 if is_l_right else 0.0) - (1.0 if is_l_left else 0.0)
                dig_ly = (1.0 if is_l_down else 0.0) - (1.0 if is_l_up else 0.0)

                # Si el eje analógico tiene entrada activa (lx_axis / ly_axis != 0.0),
                # la entrada analógica prevalece para conservar la respuesta gradual continua de 0% a 100%.
                # Solo si el eje analógico está inactivo (0.0) se adopta la entrada digital secundaria (teclado/dpad).
                lx_raw = lx_axis if abs(lx_axis) > 0.0 else dig_lx
                ly_raw = ly_axis if abs(ly_axis) > 0.0 else dig_ly

                lx_calib = apply_axis_calibration(
                    lx_raw,
                    deadzone_pct=c_ls.get("deadzone", 8),
                    anti_deadzone_pct=c_ls.get("anti_deadzone", 0),
                    sensitivity_pct=c_ls.get("sensitivity", 0),
                    invert=c_ls.get("invert_x", False)
                )
                ly_calib = apply_axis_calibration(
                    ly_raw,
                    deadzone_pct=c_ls.get("deadzone", 8),
                    anti_deadzone_pct=c_ls.get("anti_deadzone", 0),
                    sensitivity_pct=c_ls.get("sensitivity", 0),
                    invert=c_ls.get("invert_y", False)
                )

                # 4. Stick Derecho (RS)
                _, rx_axis = eval_compiled(p_comp.get("RIGHT_STICK_X", ("none",)), joy_state, dev_id, self.pressed_keys)
                _, ry_axis = eval_compiled(p_comp.get("RIGHT_STICK_Y", ("none",)), joy_state, dev_id, self.pressed_keys)

                is_r_up, _ = eval_compiled(p_comp.get("RIGHT_STICK_UP", ("none",)), joy_state, dev_id, self.pressed_keys)
                is_r_down, _ = eval_compiled(p_comp.get("RIGHT_STICK_DOWN", ("none",)), joy_state, dev_id, self.pressed_keys)
                is_r_left, _ = eval_compiled(p_comp.get("RIGHT_STICK_LEFT", ("none",)), joy_state, dev_id, self.pressed_keys)
                is_r_right, _ = eval_compiled(p_comp.get("RIGHT_STICK_RIGHT", ("none",)), joy_state, dev_id, self.pressed_keys)

                if is_r_up: pressed_buttons.add("RIGHT_STICK_UP")
                if is_r_down: pressed_buttons.add("RIGHT_STICK_DOWN")
                if is_r_left: pressed_buttons.add("RIGHT_STICK_LEFT")
                if is_r_right: pressed_buttons.add("RIGHT_STICK_RIGHT")

                dig_rx = (1.0 if is_r_right else 0.0) - (1.0 if is_r_left else 0.0)
                dig_ry = (1.0 if is_r_down else 0.0) - (1.0 if is_r_up else 0.0)

                rx_raw = rx_axis if abs(rx_axis) > 0.0 else dig_rx
                ry_raw = ry_axis if abs(ry_axis) > 0.0 else dig_ry

                rx_calib = apply_axis_calibration(
                    rx_raw,
                    deadzone_pct=c_rs.get("deadzone", 8),
                    anti_deadzone_pct=c_rs.get("anti_deadzone", 0),
                    sensitivity_pct=c_rs.get("sensitivity", 0),
                    invert=c_rs.get("invert_x", False)
                )
                ry_calib = apply_axis_calibration(
                    ry_raw,
                    deadzone_pct=c_rs.get("deadzone", 8),
                    anti_deadzone_pct=c_rs.get("anti_deadzone", 0),
                    sensitivity_pct=c_rs.get("sensitivity", 0),
                    invert=c_rs.get("invert_y", False)
                )

                # 5. Envio al backend correspondiente
                if is_viiper:
                    if pad_type == "xbox360":
                        btn_mask = 0
                        for b in pressed_buttons:
                            btn_mask |= XBOX_BUTTONS.get(b, 0)
                        lx_int = int(lx_calib * 32767)
                        ly_int = int(-ly_calib * 32767)
                        rx_int = int(rx_calib * 32767)
                        ry_int = int(-ry_calib * 32767)
                        self.viiper_client.send_xbox360_state(pad_id, btn_mask, lt_byte, rt_byte, lx_int, ly_int, rx_int, ry_int)
                    elif pad_type in ("xboxone", "xbox_one"):
                        btn_mask = 0
                        for b in pressed_buttons:
                            btn_mask |= XBOX_ONE_BUTTONS.get(b, 0)
                        lx_int = int(lx_calib * 32767)
                        ly_int = int(-ly_calib * 32767)
                        rx_int = int(rx_calib * 32767)
                        ry_int = int(-ry_calib * 32767)
                        self.viiper_client.send_xboxone_state(pad_id, btn_mask, lt_byte, rt_byte, lx_int, ly_int, rx_int, ry_int)
                    elif pad_type == "ds4":
                        btn_mask = 0
                        for b in pressed_buttons:
                            btn_mask |= DS4_BUTTONS.get(b, 0)
                        dpad_mask = (1 if is_d_up else 0) | (2 if is_d_down else 0) | (4 if is_d_left else 0) | (8 if is_d_right else 0)
                        lx_b = max(-128, min(127, int(lx_calib * 127)))
                        ly_b = max(-128, min(127, int(ly_calib * 127)))
                        rx_b = max(-128, min(127, int(rx_calib * 127)))
                        ry_b = max(-128, min(127, int(ry_calib * 127)))
                        self.viiper_client.send_ds4_state(pad_id, btn_mask, dpad_mask, lt_byte, rt_byte, lx_b, ly_b, rx_b, ry_b)
                    elif pad_type == "dualsense":
                        btn_mask = 0
                        for b in pressed_buttons:
                            btn_mask |= DUALSENSE_BUTTONS.get(b, 0)
                        dpad_mask = (1 if is_d_up else 0) | (2 if is_d_down else 0) | (4 if is_d_left else 0) | (8 if is_d_right else 0)
                        lx_b = max(-128, min(127, int(lx_calib * 127)))
                        ly_b = max(-128, min(127, int(ly_calib * 127)))
                        rx_b = max(-128, min(127, int(rx_calib * 127)))
                        ry_b = max(-128, min(127, int(ry_calib * 127)))
                        self.viiper_client.send_dualsense_state(pad_id, btn_mask, dpad_mask, lt_byte, rt_byte, lx_b, ly_b, rx_b, ry_b)
                    elif pad_type == "ns2pro":
                        btn_mask = 0
                        for b in pressed_buttons:
                            btn_mask |= NS2PRO_BUTTONS.get(b, 0)
                        if lt_byte > 40:
                            btn_mask |= NS2PRO_BUTTONS.get("ZL", 0)
                        if rt_byte > 40:
                            btn_mask |= NS2PRO_BUTTONS.get("ZR", 0)
                        lx_u = max(0, min(4095, int(2048 + lx_calib * 2047)))
                        ly_u = max(0, min(4095, int(2048 + ly_calib * 2047)))
                        rx_u = max(0, min(4095, int(2048 + rx_calib * 2047)))
                        ry_u = max(0, min(4095, int(2048 + ry_calib * 2047)))
                        self.viiper_client.send_ns2pro_state(pad_id, btn_mask, lx_u, ly_u, rx_u, ry_u)
                elif pad is not None:
                    # Modo ViGEmBus
                    if is_ds4:
                        for btn_name, vg_code in DS4_BUTTON_VG_MAP.items():
                            if btn_name in pressed_buttons:
                                pad.press_button(button=vg_code)
                            else:
                                pad.release_button(button=vg_code)
                        if "GUIDE" in pressed_buttons:
                            pad.press_special_button(special_button=vg.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_PS)
                        else:
                            pad.release_special_button(special_button=vg.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_PS)
                        pad.directional_pad(direction=get_ds4_dpad_direction(is_d_up, is_d_down, is_d_left, is_d_right))
                        pad.left_trigger(value=lt_byte)
                        if lt_byte > 10:
                            pad.press_button(button=vg.DS4_BUTTONS.DS4_BUTTON_TRIGGER_LEFT)
                        else:
                            pad.release_button(button=vg.DS4_BUTTONS.DS4_BUTTON_TRIGGER_LEFT)
                        pad.right_trigger(value=rt_byte)
                        if rt_byte > 10:
                            pad.press_button(button=vg.DS4_BUTTONS.DS4_BUTTON_TRIGGER_RIGHT)
                        else:
                            pad.release_button(button=vg.DS4_BUTTONS.DS4_BUTTON_TRIGGER_RIGHT)
                        lx_byte = max(0, min(255, 128 + int(lx_calib * 127)))
                        ly_byte = max(0, min(255, 128 + int(ly_calib * 127)))
                        pad.left_joystick(x_value=lx_byte, y_value=ly_byte)
                        rx_byte = max(0, min(255, 128 + int(rx_calib * 127)))
                        ry_byte = max(0, min(255, 128 + int(ry_calib * 127)))
                        pad.right_joystick(x_value=rx_byte, y_value=ry_byte)
                    else:
                        for btn_name, vg_code in BUTTON_VG_MAP.items():
                            if btn_name in pressed_buttons:
                                pad.press_button(button=vg_code)
                            else:
                                pad.release_button(button=vg_code)
                        pad.left_trigger(value=lt_byte)
                        pad.right_trigger(value=rt_byte)
                        lx_int = int(lx_calib * 32767)
                        ly_int = int(-ly_calib * 32767)
                        pad.left_joystick(x_value=lx_int, y_value=ly_int)
                        rx_int = int(rx_calib * 32767)
                        ry_int = int(-ry_calib * 32767)
                        pad.right_joystick(x_value=rx_int, y_value=ry_int)
                    pad.update()

                # Actualizar estado de visualizacion para la GUI
                with self.lock:
                    self.active_states[pad_id] = {
                        "buttons": pressed_buttons,
                        "lt_raw": lt_norm, "lt": lt_byte,
                        "rt_raw": rt_norm, "rt": rt_byte,
                        "lx_raw": lx_raw, "lx": lx_calib,
                        "ly_raw": ly_raw, "ly": ly_calib,
                        "rx_raw": rx_raw, "rx": rx_calib,
                        "ry_raw": ry_raw, "ry": ry_calib
                    }

            # Despertar reactivo con límite de espera de 8 ms (~120 Hz)
            # para sincronizar con VIIPER write-batch sin demora
            self.input_event.wait(timeout=0.008)
            self.input_event.clear()

    def compute_controller_state(self, pad_id: int) -> dict:
        """Lee el estado del periferico fisico en tiempo real aunque la emulacion no este activa."""
        self.device_manager.pump_events()
        with self.lock:
            cfg = self.config.get("controllers", {}).get(str(pad_id), {})
            dev_id = cfg.get("physical_device_id", "none")
            mappings = cfg.get("mappings", {})
            calib = cfg.get("calibration", {})

        if dev_id == "none":
            return {
                "buttons": set(),
                "lt_raw": 0.0, "lt": 0, "rt_raw": 0.0, "rt": 0,
                "lx_raw": 0.0, "lx": 0.0, "ly_raw": 0.0, "ly": 0.0,
                "rx_raw": 0.0, "rx": 0.0, "ry_raw": 0.0, "ry": 0.0
            }

        joy_state = self.device_manager.read_physical_state(dev_id)
        pressed_buttons = set()

        for btn_name in BUTTON_VG_MAP.keys():
            map_str = mappings.get(btn_name, "")
            is_pressed, _ = self._eval_mapping(map_str, joy_state, dev_id)
            if is_pressed:
                pressed_buttons.add(btn_name)

        c_lt = calib.get("left_trigger", {})
        c_rt = calib.get("right_trigger", {})
        c_ls = calib.get("left_stick", {})
        c_rs = calib.get("right_stick", {})

        lt_map = canonicalize_mapping(mappings.get("LEFT_TRIGGER", ""))
        is_lt_pressed, lt_raw = self._eval_mapping(lt_map, joy_state, dev_id)
        if is_lt_pressed and lt_raw == 1.0 and "Axis" not in lt_map:
            lt_norm = 1.0
        else:
            lt_norm = max(0.0, min(1.0, (lt_raw + 1.0) / 2.0 if ("Axis" in lt_map and not ("+" in lt_map or "-" in lt_map)) else lt_raw))
        lt_calib = apply_trigger_calibration(lt_norm, c_lt.get("deadzone", 0), c_lt.get("anti_deadzone", 0), c_lt.get("sensitivity", 0), c_lt.get("invert", False))
        lt_byte = int(lt_calib * 255)

        rt_map = canonicalize_mapping(mappings.get("RIGHT_TRIGGER", ""))
        is_rt_pressed, rt_raw = self._eval_mapping(rt_map, joy_state, dev_id)
        if is_rt_pressed and rt_raw == 1.0 and "Axis" not in rt_map:
            rt_norm = 1.0
        else:
            rt_norm = max(0.0, min(1.0, (rt_raw + 1.0) / 2.0 if ("Axis" in rt_map and not ("+" in rt_map or "-" in rt_map)) else rt_raw))
        rt_calib = apply_trigger_calibration(rt_norm, c_rt.get("deadzone", 0), c_rt.get("anti_deadzone", 0), c_rt.get("sensitivity", 0), c_rt.get("invert", False))
        rt_byte = int(rt_calib * 255)

        _, lx_axis = self._eval_mapping(mappings.get("LEFT_STICK_X", ""), joy_state, dev_id)
        _, ly_axis = self._eval_mapping(mappings.get("LEFT_STICK_Y", ""), joy_state, dev_id)

        is_l_up, _ = self._eval_mapping(mappings.get("LEFT_STICK_UP", ""), joy_state, dev_id)
        is_l_down, _ = self._eval_mapping(mappings.get("LEFT_STICK_DOWN", ""), joy_state, dev_id)
        is_l_left, _ = self._eval_mapping(mappings.get("LEFT_STICK_LEFT", ""), joy_state, dev_id)
        is_l_right, _ = self._eval_mapping(mappings.get("LEFT_STICK_RIGHT", ""), joy_state, dev_id)

        if is_l_up: pressed_buttons.add("LEFT_STICK_UP")
        if is_l_down: pressed_buttons.add("LEFT_STICK_DOWN")
        if is_l_left: pressed_buttons.add("LEFT_STICK_LEFT")
        if is_l_right: pressed_buttons.add("LEFT_STICK_RIGHT")

        dig_lx = (1.0 if is_l_right else 0.0) - (1.0 if is_l_left else 0.0)
        dig_ly = (1.0 if is_l_down else 0.0) - (1.0 if is_l_up else 0.0)

        lx_raw = lx_axis if abs(lx_axis) > 0.0 else dig_lx
        ly_raw = ly_axis if abs(ly_axis) > 0.0 else dig_ly

        lx_calib = apply_axis_calibration(lx_raw, c_ls.get("deadzone", 8), c_ls.get("anti_deadzone", 0), c_ls.get("sensitivity", 0), c_ls.get("invert_x", False))
        ly_calib = apply_axis_calibration(ly_raw, c_ls.get("deadzone", 8), c_ls.get("anti_deadzone", 0), c_ls.get("sensitivity", 0), c_ls.get("invert_y", False))

        _, rx_axis = self._eval_mapping(mappings.get("RIGHT_STICK_X", ""), joy_state)
        _, ry_axis = self._eval_mapping(mappings.get("RIGHT_STICK_Y", ""), joy_state)

        is_r_up, _ = self._eval_mapping(mappings.get("RIGHT_STICK_UP", ""), joy_state)
        is_r_down, _ = self._eval_mapping(mappings.get("RIGHT_STICK_DOWN", ""), joy_state)
        is_r_left, _ = self._eval_mapping(mappings.get("RIGHT_STICK_LEFT", ""), joy_state)
        is_r_right, _ = self._eval_mapping(mappings.get("RIGHT_STICK_RIGHT", ""), joy_state)

        if is_r_up: pressed_buttons.add("RIGHT_STICK_UP")
        if is_r_down: pressed_buttons.add("RIGHT_STICK_DOWN")
        if is_r_left: pressed_buttons.add("RIGHT_STICK_LEFT")
        if is_r_right: pressed_buttons.add("RIGHT_STICK_RIGHT")

        dig_rx = (1.0 if is_r_right else 0.0) - (1.0 if is_r_left else 0.0)
        dig_ry = (1.0 if is_r_down else 0.0) - (1.0 if is_r_up else 0.0)

        rx_raw = rx_axis if abs(rx_axis) > 0.0 else dig_rx
        ry_raw = ry_axis if abs(ry_axis) > 0.0 else dig_ry

        rx_calib = apply_axis_calibration(rx_raw, c_rs.get("deadzone", 8), c_rs.get("anti_deadzone", 0), c_rs.get("sensitivity", 0), c_rs.get("invert_x", False))
        ry_calib = apply_axis_calibration(ry_raw, c_rs.get("deadzone", 8), c_rs.get("anti_deadzone", 0), c_rs.get("sensitivity", 0), c_rs.get("invert_y", False))

        return {
            "buttons": pressed_buttons,
            "lt_raw": lt_norm, "lt": lt_byte,
            "rt_raw": rt_norm, "rt": rt_byte,
            "lx_raw": lx_raw, "lx": lx_calib,
            "ly_raw": ly_raw, "ly": ly_calib,
            "rx_raw": rx_raw, "rx": rx_calib,
            "ry_raw": ry_raw, "ry": ry_calib
        }

