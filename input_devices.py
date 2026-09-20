import os
import sys
import time
import ctypes
from typing import Dict, List, Optional, Tuple, Any, Set, Callable

# Permitir ejecucion de pygame sin crear ventana grafica propia
os.environ['SDL_VIDEODRIVER'] = 'dummy'
import threading
import pygame
from driver_manager import DriverManager
from raw_keyboard import RawKeyboardManager

# Inicializar subsistema de joystick de pygame
pygame.init()
pygame.joystick.init()

KNOWN_VENDORS = {
    "045E": "Microsoft Corporation",
    "054C": "Sony Interactive Entertainment",
    "057E": "Nintendo Co., Ltd.",
    "046D": "Logitech",
    "1532": "Razer Inc.",
    "2DC8": "8BitDo",
    "0E6F": "PDP (Performance Designed Products)",
    "11C0": "Generic USB / DragonRise",
    "0810": "Twin USB Gamepad / Personal Comm.",
    "0079": "DragonRise Inc."
}

def _get_present_pnp_device_instance_paths() -> List[str]:
    """Obtiene la lista de rutas de instancia de dispositivos PnP actualmente presentes en Windows."""
    if sys.platform != "win32":
        return []
    try:
        cfgmgr32 = ctypes.windll.cfgmgr32
        buf_len = ctypes.c_ulong()
        if cfgmgr32.CM_Get_Device_ID_List_SizeW(ctypes.byref(buf_len), None, 0) != 0:
            return []
        buf = ctypes.create_unicode_buffer(buf_len.value)
        if cfgmgr32.CM_Get_Device_ID_ListW(None, buf, buf_len.value, 0) != 0:
            return []

        all_paths = []
        cur = ""
        for c in buf:
            if c == "\x00":
                if cur:
                    all_paths.append(cur)
                    cur = ""
            else:
                cur += c

        # Filtrar únicamente los presentes
        present = []
        dev_inst = ctypes.c_ulong()
        for p in all_paths:
            # 0 = CM_LOCATE_DEVNODE_NORMAL (sólo dispositivos físicamente presentes)
            if cfgmgr32.CM_Locate_DevNodeW(ctypes.byref(dev_inst), p, 0) == 0:
                present.append(p)
        return present
    except Exception:
        return []

class DeviceManager:
    def __init__(self, driver_manager: Optional[DriverManager] = None):
        self.driver_manager = driver_manager or DriverManager()
        self.keyboard_manager = RawKeyboardManager.get_instance()
        self.joysticks: Dict[str, pygame.joystick.Joystick] = {}
        self._physical_map: Dict[str, str] = {}
        self._on_devices_changed_callbacks: List[Callable[[List[Dict[str, Any]]], None]] = []
        self._auto_reconnect_job = None
        self._pending_hotplug_check = False
        self._last_hotplug_event_time = 0.0

        try:
            if not pygame.get_init():
                pygame.init()
            if not pygame.joystick.get_init():
                pygame.joystick.init()
        except Exception as e:
            print(f"[!] Error inicializando subsistema de joystick de Pygame: {e}")

        # Iniciar captura de teclado Raw Input en segundo plano
        if self.keyboard_manager:
            try:
                self.keyboard_manager.start()
            except Exception as e:
                print(f"[!] No se pudo iniciar el gestor de teclados Raw Input: {e}")

    def add_on_devices_changed_callback(self, callback):
        """Registra una función callback a invocar cuando se detecta reconexión/cambio de mandos."""
        if callback not in self._on_devices_changed_callbacks:
            self._on_devices_changed_callbacks.append(callback)

    def set_excluded_virtual_indices(self, indices):
        """Compatibilidad con versiones anteriores."""
        pass

    def cancel_capture(self):
        """Cancela inmediatamente cualquier proceso de captura en curso."""
        self._cancel_capture = True
        if hasattr(self, "keyboard_manager") and self.keyboard_manager:
            self.keyboard_manager.cancel_capture()

    def stop(self):
        """Detiene el gestor de teclados y libera recursos."""
        if hasattr(self, "keyboard_manager") and self.keyboard_manager:
            self.keyboard_manager.stop()

    def _is_virtual_gamepad(self, joy: pygame.joystick.Joystick) -> bool:
        """Determina si un joystick es un mando virtual creado por ViGEmBus o VIIPER."""
        try:
            name = joy.get_name().strip()
            guid = joy.get_guid()
            vid = "0000"
            pid = "0000"
            if len(guid) >= 20:
                vid = (guid[10:12] + guid[8:10]).upper()
                pid = (guid[18:20] + guid[16:18]).upper()

            name_l = name.lower()
            if any(x in name_l for x in ("usbip", "viiper", "vigem", "nefarius", "vgamepad")):
                return True

            # Xbox 360 virtual (ViGEmBus o VIIPER)
            if vid == "045E" and pid == "028E" and ("xbox 360" in name_l or "xinput" in name_l or "controller" in name_l):
                return True

            # DualShock 4 virtual (ViGEmBus o VIIPER)
            if vid == "054C" and pid in ("05C4", "09CC"):
                if any(x in name_l for x in ("ps4", "playstation", "wireless controller", "dualshock", "compatible con hid", "sony")):
                    return True

            # DualSense virtual (VIIPER)
            if vid == "054C" and pid in ("0CE6", "0DF2"):
                if any(x in name_l for x in ("dualsense", "wireless controller", "playstation", "sony")):
                    return True

            # Switch 2 Pro virtual (VIIPER)
            if (vid == "057E" and pid == "2069") or ("switch 2" in name_l) or ("ns2pro" in name_l):
                return True
        except Exception:
            pass
        return False

    def refresh_devices(self) -> List[Dict[str, Any]]:
        """Re-escanea los joysticks fisicos conectados por USB o Bluetooth, excluyendo virtuales."""
        try:
            pygame.event.pump()
        except Exception:
            pass

        self.joysticks.clear()
        self._physical_map.clear()

        device_list = [
            {
                "id": "none",
                "name": "-- Ninguno / Desconectado --",
                "type": "none",
                "vendor_name": "",
                "product_name": "Ninguno",
                "instance_id": "00000000",
                "conn_type": "N/A"
            },
            {
                "id": "keyboard",
                "name": "⌨ Teclado (Cualquiera / Global)",
                "type": "keyboard",
                "vendor_name": "(Sistema)",
                "product_name": "Cualquier Teclado",
                "instance_id": "GLOBAL",
                "conn_type": "SYS"
            }
        ]

        # Enumerar teclados físicos individuales vía Windows Raw Input
        if hasattr(self, "keyboard_manager") and self.keyboard_manager:
            raw_keyboards = self.keyboard_manager.refresh_devices()
            for idx, k in enumerate(raw_keyboards):
                conn_lbl = "USB" if k["conn_type"] == "USB" else ("Bluetooth" if k["conn_type"] in ("BT", "BTH") else ("Interno" if k["conn_type"] == "INT" else k["conn_type"]))
                device_list.append({
                    "id": k["id"],
                    "name": f"⌨ Teclado {idx + 1}: {k['product_name']} ({conn_lbl})",
                    "type": "keyboard",
                    "vendor_name": k.get("vendor_name", "(Genérico)"),
                    "product_name": k.get("product_name", "Teclado"),
                    "instance_id": k.get("instance_id", "KBD"),
                    "conn_type": k.get("conn_type", "USB"),
                    "instance_path": k.get("pnp_path") or k.get("path", "")
                })

        device_list.append({
            "id": "mouse",
            "name": "Mouse (Puntero / Botones)",
            "type": "mouse",
            "vendor_name": "(Dispositivos de sistema estándar)",
            "product_name": "Mouse del Sistema",
            "instance_id": "6F1D2B60",
            "conn_type": "SYS"
        })

        count = pygame.joystick.get_count()
        phys_idx = 0

        # Obtener rutas de instancia presentes e información de HidHide
        present_pnp_paths = _get_present_pnp_device_instance_paths()
        hidden_paths = self.driver_manager.get_hidden_device_paths()

        # Recopilar rutas candidatas PnP por (VID, PID)
        import hashlib
        import re
        candidates_by_vid_pid: Dict[Tuple[str, str], List[str]] = {}

        def _is_virtual_path(pth: str) -> bool:
            u = pth.upper()
            if any(x in u for x in (
                "VID_045E&PID_028E",
                "VID_054C&PID_05C4",
                "VID_054C&PID_09CC",
                "VID_054C&PID_0CE6",
                "VID_054C&PID_0DF2",
                "VID_057E&PID_2069",
            )):
                return True
            if any(x in u for x in ("USBIP", "VIGEM", "VIIPER")):
                return True
            return False

        # 1. Prioridad: rutas directas de mandos reportadas por HidHide (dev-gaming)
        gaming_devices = self.driver_manager.get_gaming_devices_info()
        for g in gaming_devices:
            p = g.get("instance_path", "").strip()
            if p:
                if _is_virtual_path(p):
                    continue
                up = p.upper()
                m_vid = re.search(r'VID[_\&]([0-9A-F]{4})', up)
                m_pid = re.search(r'PID[_\&]([0-9A-F]{4})', up)
                if m_vid and m_pid:
                    key = (m_vid.group(1), m_pid.group(1))
                    candidates_by_vid_pid.setdefault(key, []).append(p)

        # 2. Complementar con rutas PnP presentes de clase HID
        for p in present_pnp_paths:
            if _is_virtual_path(p):
                continue
            up = p.upper()
            if up.startswith("HID\\"):
                m_vid = re.search(r'VID[_\&]([0-9A-F]{4})', up)
                m_pid = re.search(r'PID[_\&]([0-9A-F]{4})', up)
                if m_vid and m_pid:
                    key = (m_vid.group(1), m_pid.group(1))
                    pool = candidates_by_vid_pid.setdefault(key, [])
                    if p not in pool:
                        pool.append(p)

        # 3. Fallback USB si no hay rutas HID para ese dispositivo
        for p in present_pnp_paths:
            if _is_virtual_path(p):
                continue
            up = p.upper()
            if up.startswith("USB\\"):
                m_vid = re.search(r'VID[_\&]([0-9A-F]{4})', up)
                m_pid = re.search(r'PID[_\&]([0-9A-F]{4})', up)
                if m_vid and m_pid:
                    key = (m_vid.group(1), m_pid.group(1))
                    pool = candidates_by_vid_pid.setdefault(key, [])
                    if not any(x.upper().startswith("HID\\") for x in pool):
                        if p not in pool:
                            pool.append(p)

        # Ordenar determinísticamente cada lista de candidatos
        for key in candidates_by_vid_pid:
            candidates_by_vid_pid[key] = sorted(candidates_by_vid_pid[key])

        used_instance_paths: Set[str] = set()

        for i in range(count):
            try:
                joy = pygame.joystick.Joystick(i)
                joy.init()

                # Si es un mando virtual de ViGEmBus, lo ignoramos totalmente
                if self._is_virtual_gamepad(joy):
                    joy.quit()
                    continue

                self.joysticks[i] = joy
                dev_id = f"joy_{phys_idx}"
                self._physical_map[dev_id] = i

                name = joy.get_name().strip()
                guid = joy.get_guid()
                num_buttons = joy.get_numbuttons()
                num_axes = joy.get_numaxes()
                num_hats = joy.get_numhats()

                # Extraer VID y PID a partir del GUID de SDL (Windows little-endian)
                vid = "0000"
                pid = "0000"
                if len(guid) >= 20:
                    vid = (guid[10:12] + guid[8:10]).upper()
                    pid = (guid[18:20] + guid[16:18]).upper()

                vendor_name = KNOWN_VENDORS.get(vid, "(Dispositivos de sistema estándar)")

                # Determinar tipo de conexion estimada (Bluetooth vs USB)
                conn_type = "USB"
                if "bluetooth" in name.lower() or "wireless" in name.lower() or "bth" in guid.lower():
                    conn_type = "BT"

                # Correlacionar con una ruta PnP única no utilizada previamente para HidHide
                instance_path = ""
                pool = candidates_by_vid_pid.get((vid, pid), [])
                for cand in pool:
                    if cand not in used_instance_paths:
                        instance_path = cand
                        used_instance_paths.add(cand)
                        break

                # Instance ID determinista, consistente y único por dispositivo (8 hex chars)
                id_seed = f"{guid}_{instance_path}" if instance_path else f"{guid}_{dev_id}_{phys_idx}"
                instance_id = hashlib.sha256(id_seed.encode("utf-8")).hexdigest()[:8].upper()

                is_hidden = False
                if instance_path:
                    is_hidden = instance_path.upper() in hidden_paths

                dev_info = {
                    "id": dev_id,
                    "sdl_index": i,
                    "guid": guid,
                    "vid": vid,
                    "pid": pid,
                    "vendor_name": vendor_name,
                    "product_name": name,
                    "conn_type": conn_type,
                    "instance_id": instance_id,
                    "instance_path": instance_path,
                    "is_hidden": is_hidden,
                    "name": f"Joystick {phys_idx}: {name} ({num_buttons}B / {num_axes}A / {num_hats}H)",
                    "type": "joystick",
                    "num_buttons": num_buttons,
                    "num_axes": num_axes,
                    "num_hats": num_hats
                }
                device_list.append(dev_info)
                phys_idx += 1
            except Exception as e:
                print(f"[!] Error inicializando joystick {i}: {e}")

        self._device_cache = list(device_list)
        return device_list

    def get_cached_devices(self) -> List[Dict[str, Any]]:
        """Retorna la lista de dispositivos en caché sin reiniciar los joysticks."""
        return list(self._device_cache)

    def _mark_device_disconnected(self, dev_id: str, sdl_idx: Optional[int] = None):
        """Cierra y desconecta ÚNICAMENTE el joystick indicado sin afectar a los demás."""
        if sdl_idx is None:
            sdl_idx = self._physical_map.get(dev_id)
        if sdl_idx is not None and sdl_idx in self.joysticks:
            try:
                joy = self.joysticks[sdl_idx]
                joy.quit()
            except Exception:
                pass
            self.joysticks.pop(sdl_idx, None)

        self._pending_hotplug_check = True
        self._last_hotplug_event_time = time.time()

    def get_joystick(self, dev_id_or_idx) -> Optional[pygame.joystick.Joystick]:
        """Obtiene el joystick por dev_id ('joy_0') o por índice SDL numérico."""
        if isinstance(dev_id_or_idx, str):
            if dev_id_or_idx in self._physical_map:
                sdl_idx = self._physical_map[dev_id_or_idx]
                return self.joysticks.get(sdl_idx)
            try:
                sdl_idx = int(dev_id_or_idx.split("_")[1])
            except Exception:
                return None
        else:
            sdl_idx = dev_id_or_idx

        if sdl_idx not in self.joysticks:
            if 0 <= sdl_idx < pygame.joystick.get_count():
                try:
                    joy = pygame.joystick.Joystick(sdl_idx)
                    joy.init()
                    self.joysticks[sdl_idx] = joy
                except Exception:
                    return None
        return self.joysticks.get(sdl_idx)

    def pump_events(self):
        """Actualiza el estado de eventos de pygame y procesa hotplug selectivo."""
        try:
            # Procesar eventos individuales de agregación / remoción generados por SDL
            hotplug_events = pygame.event.get([pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED])
            if hotplug_events:
                now = time.time()
                for ev in hotplug_events:
                    if ev.type == pygame.JOYDEVICEREMOVED:
                        inst_id = getattr(ev, 'instance_id', None)
                        # Localizar el joystick específico desconectado por su instance_id
                        for s_idx, j in list(self.joysticks.items()):
                            try:
                                if j.get_instance_id() == inst_id:
                                    try:
                                        j.quit()
                                    except Exception:
                                        pass
                                    self.joysticks.pop(s_idx, None)
                                    break
                            except Exception:
                                pass
                    elif ev.type == pygame.JOYDEVICEADDED:
                        pass
                self._pending_hotplug_check = True
                self._last_hotplug_event_time = now

            # Debounce: si hubo eventos de hotplug y ya pasaron ~300ms de calma USB, refrescar
            if self._pending_hotplug_check and (time.time() - self._last_hotplug_event_time >= 0.3):
                self._pending_hotplug_check = False
                self._perform_selective_reconnect()
        except Exception:
            pass

    def _perform_selective_reconnect(self):
        """Re-escanea dispositivos preservando los mandos sanos y reconectando los perdidos."""
        try:
            new_list = self.refresh_devices()
            # Notificar a los observadores (ej. GUI) de forma segura
            for cb in list(self._on_devices_changed_callbacks):
                try:
                    cb(new_list)
                except Exception:
                    pass
        except Exception as e:
            print(f"[!] Error en auto-reconexión selectiva: {e}")

    def read_physical_state(self, dev_id: str, pump: bool = True) -> Dict[str, Any]:
        """Lee el estado crudo actual de botones, ejes y cruceta de un dispositivo."""
        if pump:
            self.pump_events()
        state = {
            "buttons": {},
            "axes": {},
            "hats": {},
            "keys": set()
        }

        if dev_id.startswith("joy_"):
            joy = self.get_joystick(dev_id)
            if joy and joy.get_init():
                try:
                    for b in range(joy.get_numbuttons()):
                        state["buttons"][b] = bool(joy.get_button(b))
                    for a in range(joy.get_numaxes()):
                        state["axes"][a] = float(joy.get_axis(a))
                    for h in range(joy.get_numhats()):
                        state["hats"][h] = joy.get_hat(h)  # (x, y)
                except Exception:
                    # Falla de lectura (handle roto por micro-desconexión en este mando específico)
                    self._mark_device_disconnected(dev_id)
            else:
                # El mando no está inicializado o está ausente
                if not self._pending_hotplug_check:
                    self._pending_hotplug_check = True
                    self._last_hotplug_event_time = time.time()
        elif dev_id.startswith("kbd_"):
            if hasattr(self, "keyboard_manager") and self.keyboard_manager:
                state["keys"] = self.keyboard_manager.get_pressed_keys(dev_id)
        elif dev_id == "keyboard":
            if hasattr(self, "keyboard_manager") and self.keyboard_manager:
                all_k = set()
                for k in self.keyboard_manager.get_available_keyboards():
                    all_k.update(self.keyboard_manager.get_pressed_keys(k["id"]))
                state["keys"] = all_k

        return state

    def capture_input(self, dev_id: str, timeout: float = 4.0, target_name: str = "") -> Optional[str]:
        """
        Escucha el proximo movimiento de boton, eje o cruceta en el dispositivo fisico indicado.
        Retorna la etiqueta del mapeo detectado (ej: 'Button 1', 'Axis 1', 'POV 1 Up', etc.).
        """
        if dev_id == "none":
            return None

        self._cancel_capture = False
        start_time = time.time()

        # Captura de teclas para teclado físico específico o global
        if dev_id.startswith("kbd_") or dev_id == "keyboard":
            if not hasattr(self, "keyboard_manager") or not self.keyboard_manager:
                return None
            target_kbd = dev_id if dev_id.startswith("kbd_") else None
            captured_res = [None]
            done_ev = threading.Event()

            def _on_key_captured(k_name):
                captured_res[0] = k_name
                done_ev.set()

            self.keyboard_manager.start_capture(target_kbd, _on_key_captured)
            while time.time() - start_time < timeout:
                if self._cancel_capture:
                    self.keyboard_manager.cancel_capture()
                    return None
                if done_ev.wait(timeout=0.03):
                    break
            self.keyboard_manager.cancel_capture()
            return captured_res[0]

        self.pump_events()

        # Guardar linea base de botones, hats y ejes para detectar movimiento relativo
        baseline_axes = {}
        baseline_buttons = set()
        baseline_hats = {}

        if dev_id.startswith("joy_"):
            try:
                joy = self.get_joystick(dev_id)
                if joy and joy.get_init():
                    for a in range(joy.get_numaxes()):
                        baseline_axes[a] = joy.get_axis(a)
                    for b in range(joy.get_numbuttons()):
                        if joy.get_button(b):
                            baseline_buttons.add(b)
                    for h in range(joy.get_numhats()):
                        baseline_hats[h] = joy.get_hat(h)
            except Exception:
                pass

        # Si el control objetivo es un eje analógico o gatillo, umbral de sensibilidad más reactivo
        is_stick_target = any(k in target_name for k in ("STICK", "TRIGGER"))
        axis_thresh = 0.35 if is_stick_target else 0.50

        while time.time() - start_time < timeout:
            if self._cancel_capture:
                return None
            self.pump_events()

            if dev_id.startswith("joy_"):
                try:
                    joy = self.get_joystick(dev_id)
                    if not joy or not joy.get_init():
                        time.sleep(0.01)
                        continue

                    # 1. Chequear botones fisicos (prioridad instantanea al presionar)
                    for b in range(joy.get_numbuttons()):
                        if joy.get_button(b) and b not in baseline_buttons:
                            return f"Button {b + 1}"

                    # 2. Chequear Hats (POV / D-Pad)
                    for h in range(joy.get_numhats()):
                        hx, hy = joy.get_hat(h)
                        if (hx, hy) != (0, 0) and (hx, hy) != baseline_hats.get(h, (0, 0)):
                            if hy > 0:
                                return f"POV {h + 1} Up"
                            elif hy < 0:
                                return f"POV {h + 1} Down"
                            elif hx < 0:
                                return f"POV {h + 1} Left"
                            elif hx > 0:
                                return f"POV {h + 1} Right"

                    # 3. Chequear Ejes (por desplazamiento relativo respecto a la posición de reposo)
                    for a in range(joy.get_numaxes()):
                        curr = joy.get_axis(a)
                        prev = baseline_axes.get(a, 0.0)
                        diff = curr - prev
                        if abs(diff) > axis_thresh:
                            # 3.1 Si el objetivo es un Gatillo (TRIGGER) y reposa en un extremo
                            if "TRIGGER" in target_name:
                                if prev < -0.6 and curr > -0.2:
                                    return f"Axis {a + 1}"
                                elif prev > 0.6 and curr < 0.2:
                                    return f"IAxis {a + 1}"
                                elif diff > 0:
                                    return f"Axis {a + 1}"
                                else:
                                    return f"IAxis {a + 1}"
                            
                            # 3.2 Si el objetivo es un eje completo analógico de stick (STICK_X / STICK_Y)
                            if target_name.endswith("_X") or target_name.endswith("_Y"):
                                return f"Axis {a + 1}"

                            # 3.3 Si estamos asignando una dirección discreta específica del stick
                            if target_name.endswith("_UP"):
                                # En SDL/DirectInput: empujar hacia arriba genera un diff negativo (< 0)
                                return f"IAxis {a + 1}" if diff < 0 else f"Axis {a + 1}"
                            elif target_name.endswith("_DOWN"):
                                # Empujar hacia abajo genera un diff positivo (> 0)
                                return f"Axis {a + 1}" if diff > 0 else f"IAxis {a + 1}"
                            elif target_name.endswith("_LEFT"):
                                # Empujar a la izquierda genera un diff negativo (< 0)
                                return f"IAxis {a + 1}" if diff < 0 else f"Axis {a + 1}"
                            elif target_name.endswith("_RIGHT"):
                                # Empujar a la derecha genera un diff positivo (> 0)
                                return f"Axis {a + 1}" if diff > 0 else f"IAxis {a + 1}"

                            # 3.4 Fallback general (para triggers u otros controles)
                            if diff > 0:
                                return f"Axis {a + 1}"
                            else:
                                return f"IAxis {a + 1}"

                except Exception:
                    pass

            time.sleep(0.01)

        return None
