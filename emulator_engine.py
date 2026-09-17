import time
import math
import threading
from typing import Dict, Any, Optional, Set, Tuple
import vgamepad as vg
from input_devices import DeviceManager

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

class EmulatorEngine:
    def __init__(self, device_manager: DeviceManager):
        self.device_manager = device_manager
        self.config: Dict[str, Any] = {}
        self.gamepads: Dict[int, vg.VX360Gamepad] = {}
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

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

    def start(self):
        with self.lock:
            if self.running:
                return

            max_ctrls = self.config.get("max_controllers", 12)
            print(f"[*] Iniciando motor de emulacion (hasta {max_ctrls} mandos)...")
            # Crear los mandos virtuales en ViGEmBus únicamente si tienen periférico físico asignado
            for i in range(1, max_ctrls + 1):
                cfg = self.config.get("controllers", {}).get(str(i), {})
                p_dev = cfg.get("physical_device_id", "none")
                if cfg.get("enabled", True) and p_dev and p_dev != "none":
                    try:
                        pad = vg.VX360Gamepad()
                        pad.reset()
                        pad.update()
                        self.gamepads[i] = pad
                    except Exception as e:
                        print(f"  [!] Error creando mando virtual #{i}: {e}")

            self.running = True
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            print(f"[+] Motor de emulacion iniciado con {len(self.gamepads)} mandos activos.")

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

        with self.lock:
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

    def _eval_mapping(self, mapping_str: str, joy_state: Dict[str, Any], dev_id: str = "") -> Tuple[bool, float]:
        if not mapping_str or mapping_str == "-- Ninguno --":
            return False, 0.0

        mapping_str = mapping_str.strip()

        # 1. Mapeo a Teclado
        if mapping_str.lower().startswith("tecla: ") or mapping_str.lower().startswith("key: "):
            k = mapping_str.split(":", 1)[1].strip().lower()
            kbd_keys = joy_state.get("keys", set())
            pressed = any(
                k == pk.split(":", 1)[1].strip().lower() if ":" in pk else k == pk.lower()
                for pk in kbd_keys
            )
            if not pressed and not dev_id.startswith("kbd_") and hasattr(self, "pressed_keys"):
                pressed = k in self.pressed_keys
            return pressed, (1.0 if pressed else 0.0)

        # 2. Mapeo a Boton de Joystick
        if mapping_str.startswith("Button "):
            try:
                b_idx = int(mapping_str.split()[1]) - 1
                pressed = joy_state["buttons"].get(b_idx, False)
                return pressed, (1.0 if pressed else 0.0)
            except Exception:
                pass

        # 3. Mapeo a POV / D-Pad
        if mapping_str.startswith("POV "):
            parts = mapping_str.split()
            try:
                h_idx = int(parts[1]) - 1
                dir_str = parts[2].lower()
                hx, hy = joy_state["hats"].get(h_idx, (0, 0))
                pressed = False
                if dir_str == "up":
                    pressed = hy > 0
                elif dir_str == "down":
                    pressed = hy < 0
                elif dir_str == "left":
                    pressed = hx < 0
                elif dir_str == "right":
                    pressed = hx > 0
                return pressed, (1.0 if pressed else 0.0)
            except Exception:
                pass

        # 4. Mapeo a Eje analogico
        if "Axis" in mapping_str:
            inverted = mapping_str.startswith("I")
            clean_str = mapping_str[1:] if inverted else mapping_str
            try:
                parts = clean_str.split()
                a_idx_str = parts[1]
                half_positive = a_idx_str.endswith("+")
                half_negative = a_idx_str.endswith("-")
                a_idx = int(a_idx_str.replace("+", "").replace("-", "")) - 1

                val = joy_state["axes"].get(a_idx, 0.0)
                if inverted:
                    val = -val

                if half_positive:
                    val = max(0.0, val)
                elif half_negative:
                    val = max(0.0, -val)

                pressed = val > 0.45
                return pressed, val
            except Exception:
                pass

        return False, 0.0

    def _loop(self):
        while self.running:
            self.device_manager.pump_events()

            with self.lock:
                controllers_cfg = self.config.get("controllers", {})
                active_gamepads = list(self.gamepads.items())

            for pad_id, pad in active_gamepads:
                cfg = controllers_cfg.get(str(pad_id), {})
                if not cfg.get("enabled", True):
                    continue

                dev_id = cfg.get("physical_device_id", "none")
                joy_state = self.device_manager.read_physical_state(dev_id)
                mappings = cfg.get("mappings", {})
                calib = cfg.get("calibration", {})

                # Calibraciones
                c_lt = calib.get("left_trigger", {})
                c_rt = calib.get("right_trigger", {})
                c_ls = calib.get("left_stick", {})
                c_rs = calib.get("right_stick", {})

                pressed_buttons = set()

                # 1. Botones Digitales
                for btn_name, vg_code in BUTTON_VG_MAP.items():
                    map_str = mappings.get(btn_name, "")
                    is_pressed, _ = self._eval_mapping(map_str, joy_state, dev_id)
                    if is_pressed:
                        pressed_buttons.add(btn_name)
                        pad.press_button(button=vg_code)
                    else:
                        pad.release_button(button=vg_code)

                # 2. Gatillo Izquierdo (LT)
                lt_map = mappings.get("LEFT_TRIGGER", "")
                is_lt_pressed, lt_raw = self._eval_mapping(lt_map, joy_state, dev_id)
                if is_lt_pressed and lt_raw == 1.0 and "Axis" not in lt_map:
                    lt_norm = 1.0
                else:
                    lt_norm = max(0.0, min(1.0, (lt_raw + 1.0) / 2.0 if ("Axis" in lt_map and not ("+" in lt_map or "-" in lt_map)) else lt_raw))

                lt_calib = apply_trigger_calibration(
                    lt_norm,
                    deadzone_pct=c_lt.get("deadzone", 0),
                    anti_deadzone_pct=c_lt.get("anti_deadzone", 0),
                    sensitivity_pct=c_lt.get("sensitivity", 0),
                    invert=c_lt.get("invert", False)
                )
                lt_byte = int(lt_calib * 255)
                pad.left_trigger(value=lt_byte)

                # Gatillo Derecho (RT)
                rt_map = mappings.get("RIGHT_TRIGGER", "")
                is_rt_pressed, rt_raw = self._eval_mapping(rt_map, joy_state, dev_id)
                if is_rt_pressed and rt_raw == 1.0 and "Axis" not in rt_map:
                    rt_norm = 1.0
                else:
                    rt_norm = max(0.0, min(1.0, (rt_raw + 1.0) / 2.0 if ("Axis" in rt_map and not ("+" in rt_map or "-" in rt_map)) else rt_raw))

                rt_calib = apply_trigger_calibration(
                    rt_norm,
                    deadzone_pct=c_rt.get("deadzone", 0),
                    anti_deadzone_pct=c_rt.get("anti_deadzone", 0),
                    sensitivity_pct=c_rt.get("sensitivity", 0),
                    invert=c_rt.get("invert", False)
                )
                rt_byte = int(rt_calib * 255)
                pad.right_trigger(value=rt_byte)

                # 3. Stick Izquierdo (LS) - Soporta tanto ejes analogicos como teclas/botones por direccion
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

                lx_raw = dig_lx if abs(dig_lx) > 0.0 else lx_axis
                ly_raw = dig_ly if abs(dig_ly) > 0.0 else ly_axis

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
                # Xbox Y: arriba es positivo; Pygame Y: arriba es negativo
                lx_int = int(lx_calib * 32767)
                ly_int = int(-ly_calib * 32767)
                pad.left_joystick(x_value=lx_int, y_value=ly_int)

                # 4. Stick Derecho (RS) - Soporta tanto ejes analogicos como teclas/botones por direccion
                _, rx_axis = self._eval_mapping(mappings.get("RIGHT_STICK_X", ""), joy_state, dev_id)
                _, ry_axis = self._eval_mapping(mappings.get("RIGHT_STICK_Y", ""), joy_state, dev_id)

                is_r_up, _ = self._eval_mapping(mappings.get("RIGHT_STICK_UP", ""), joy_state, dev_id)
                is_r_down, _ = self._eval_mapping(mappings.get("RIGHT_STICK_DOWN", ""), joy_state, dev_id)
                is_r_left, _ = self._eval_mapping(mappings.get("RIGHT_STICK_LEFT", ""), joy_state, dev_id)
                is_r_right, _ = self._eval_mapping(mappings.get("RIGHT_STICK_RIGHT", ""), joy_state, dev_id)

                if is_r_up: pressed_buttons.add("RIGHT_STICK_UP")
                if is_r_down: pressed_buttons.add("RIGHT_STICK_DOWN")
                if is_r_left: pressed_buttons.add("RIGHT_STICK_LEFT")
                if is_r_right: pressed_buttons.add("RIGHT_STICK_RIGHT")

                dig_rx = (1.0 if is_r_right else 0.0) - (1.0 if is_r_left else 0.0)
                dig_ry = (1.0 if is_r_down else 0.0) - (1.0 if is_r_up else 0.0)

                rx_raw = dig_rx if abs(dig_rx) > 0.0 else rx_axis
                ry_raw = dig_ry if abs(dig_ry) > 0.0 else ry_axis

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
                rx_int = int(rx_calib * 32767)
                ry_int = int(-ry_calib * 32767)
                pad.right_joystick(x_value=rx_int, y_value=ry_int)

                # Enviar reporte a ViGEmBus
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

            time.sleep(0.008)  # ~120 Hz de refresco

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

        lt_map = mappings.get("LEFT_TRIGGER", "")
        is_lt_pressed, lt_raw = self._eval_mapping(lt_map, joy_state, dev_id)
        if is_lt_pressed and lt_raw == 1.0 and "Axis" not in lt_map:
            lt_norm = 1.0
        else:
            lt_norm = max(0.0, min(1.0, (lt_raw + 1.0) / 2.0 if ("Axis" in lt_map and not ("+" in lt_map or "-" in lt_map)) else lt_raw))
        lt_calib = apply_trigger_calibration(lt_norm, c_lt.get("deadzone", 0), c_lt.get("anti_deadzone", 0), c_lt.get("sensitivity", 0), c_lt.get("invert", False))
        lt_byte = int(lt_calib * 255)

        rt_map = mappings.get("RIGHT_TRIGGER", "")
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

        lx_raw = dig_lx if abs(dig_lx) > 0.0 else lx_axis
        ly_raw = dig_ly if abs(dig_ly) > 0.0 else ly_axis

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

        rx_raw = dig_rx if abs(dig_rx) > 0.0 else rx_axis
        ry_raw = dig_ry if abs(dig_ry) > 0.0 else ry_axis

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

