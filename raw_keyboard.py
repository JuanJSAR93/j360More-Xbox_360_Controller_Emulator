"""
raw_keyboard.py - Gestor de múltiples teclados independientes para Windows
utilizando la API nativa Windows Raw Input (user32.dll).

Permite detectar teclados USB, Bluetooth e integrados por separado,
identificarlos de forma persistente y leer pulsaciones de forma aislada
sin interferencias entre jugadores.
"""

import ctypes
from ctypes import wintypes
import hashlib
import logging
import os
import threading
import time
from typing import Callable, Dict, List, Optional, Set, Tuple
import winreg

logger = logging.getLogger("j360More.RawKeyboard")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

LRESULT = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT

WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

# Estructuras Win32
class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HICON),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]

class RAWINPUTDEVICELIST(ctypes.Structure):
    _fields_ = [
        ("hDevice", wintypes.HANDLE),
        ("dwType", wintypes.DWORD),
    ]

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]

class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", wintypes.USHORT),
        ("Flags", wintypes.USHORT),
        ("Reserved", wintypes.USHORT),
        ("VKey", wintypes.USHORT),
        ("Message", wintypes.UINT),
        ("ExtraInformation", wintypes.ULONG),
    ]

class RAWINPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("keyboard", RAWKEYBOARD)]
    _anonymous_ = ("_u",)
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("_u", _U),
    ]

# Configuración de llamadas Win32
user32.GetRawInputData.argtypes = [
    wintypes.HANDLE,
    wintypes.UINT,
    wintypes.LPVOID,
    ctypes.POINTER(wintypes.UINT),
    wintypes.UINT
]
user32.GetRawInputData.restype = wintypes.UINT

user32.GetRawInputDeviceInfoW.argtypes = [
    wintypes.HANDLE,
    wintypes.UINT,
    wintypes.LPVOID,
    ctypes.POINTER(wintypes.UINT)
]
user32.GetRawInputDeviceInfoW.restype = wintypes.UINT

user32.GetRawInputDeviceList.argtypes = [
    ctypes.POINTER(RAWINPUTDEVICELIST),
    ctypes.POINTER(wintypes.UINT),
    wintypes.UINT
]
user32.GetRawInputDeviceList.restype = wintypes.UINT

user32.RegisterRawInputDevices.argtypes = [
    ctypes.POINTER(RAWINPUTDEVICE),
    wintypes.UINT,
    wintypes.UINT
]
user32.RegisterRawInputDevices.restype = wintypes.BOOL

# Constantes Win32
RIM_TYPEKEYBOARD = 1
RIDI_DEVICENAME = 0x20000007
RID_INPUT = 0x10000003

WM_INPUT = 0x00FF
WM_INPUT_DEVICE_CHANGE = 0x00FE
WM_DESTROY = 0x0002
WM_USER = 0x0400
WM_QUIT_CUSTOM = WM_USER + 101

RIDEV_INPUTSINK = 0x00000100
RIDEV_DEVNOTIFY = 0x00002000
HWND_MESSAGE = wintypes.HWND(-3)

RI_KEY_BREAK = 0x01
RI_KEY_E0 = 0x02
RI_KEY_E1 = 0x04

# Diccionario de Virtual-Key Codes a Nombres Amigables
VK_MAP = {
    0x08: "Backspace",
    0x09: "Tab",
    0x0D: "Enter",
    0x10: "Shift",
    0x11: "Ctrl",
    0x12: "Alt",
    0x13: "Pause",
    0x14: "CapsLock",
    0x1B: "Esc",
    0x20: "Space",
    0x21: "PageUp",
    0x22: "PageDown",
    0x23: "End",
    0x24: "Home",
    0x25: "Left",
    0x26: "Up",
    0x27: "Right",
    0x28: "Down",
    0x2D: "Insert",
    0x2E: "Delete",
    0x5B: "Win",
    0x5C: "RightWin",
    0x5D: "Apps",
    # Teclado numérico
    0x60: "Num 0",
    0x61: "Num 1",
    0x62: "Num 2",
    0x63: "Num 3",
    0x64: "Num 4",
    0x65: "Num 5",
    0x66: "Num 6",
    0x67: "Num 7",
    0x68: "Num 8",
    0x69: "Num 9",
    0x6A: "Num *",
    0x6B: "Num +",
    0x6C: "Num Sep",
    0x6D: "Num -",
    0x6E: "Num .",
    0x6F: "Num /",
    # Teclas F
    0x70: "F1", 0x71: "F2", 0x72: "F3", 0x73: "F4",
    0x74: "F5", 0x75: "F6", 0x76: "F7", 0x77: "F8",
    0x78: "F9", 0x79: "F10", 0x7A: "F11", 0x7B: "F12",
    # Modificadores específicos
    0xA0: "LShift", 0xA1: "RShift",
    0xA2: "LCtrl",  0xA3: "RCtrl",
    0xA4: "LAlt",   0xA5: "RAlt",
    # Símbolos y puntuación estándar
    0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/",
    0xC0: "`", 0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'",
}

for i in range(0x30, 0x3A):
    VK_MAP[i] = chr(i)
for i in range(0x41, 0x5B):
    VK_MAP[i] = chr(i)

def vk_to_friendly_name(vkey: int, flags: int) -> str:
    is_e0 = bool(flags & RI_KEY_E0)
    if vkey == 0x11:
        name = "RCtrl" if is_e0 else "LCtrl"
    elif vkey == 0x12:
        name = "RAlt" if is_e0 else "LAlt"
    elif vkey == 0x10:
        name = "RShift" if is_e0 else "LShift"
    elif vkey == 0x0D and is_e0:
        name = "Num Enter"
    else:
        name = VK_MAP.get(vkey, f"VK_{vkey:02X}")
    return f"Key: {name}"

def get_device_friendly_name(device_path: str) -> Tuple[str, str, str]:
    p = device_path.upper()
    conn_type = "USB"
    friendly_name = "Teclado USB"
    vendor = "Genérico"

    if "ACPI" in p or "PNP03" in p:
        conn_type = "INT"
        friendly_name = "Teclado Interno de Laptop"
        vendor = "Sistema"
    elif "BTH" in p or "BLUETOOTH" in p:
        conn_type = "BTH"
        friendly_name = "Teclado Bluetooth"
        vendor = "Bluetooth"

    parts = device_path.split("#")
    if len(parts) >= 3:
        dev_id_str = parts[1]
        inst_id_str = parts[2]
        for base in [r"SYSTEM\CurrentControlSet\Enum\HID", r"SYSTEM\CurrentControlSet\Enum\USB"]:
            try:
                reg_path = f"{base}\\{dev_id_str}\\{inst_id_str}"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as k:
                    for val_name in ["FriendlyName", "DeviceDesc"]:
                        try:
                            val = winreg.QueryValueEx(k, val_name)[0]
                            if ";" in val:
                                val = val.split(";")[-1]
                            if val:
                                friendly_name = val.strip()
                                break
                        except Exception:
                            pass
                    try:
                        mfg = winreg.QueryValueEx(k, "Mfg")[0]
                        if ";" in mfg:
                            mfg = mfg.split(";")[-1]
                        if mfg and not mfg.startswith("@"):
                            vendor = mfg.strip()
                    except Exception:
                        pass
            except Exception:
                pass

    return friendly_name, vendor, conn_type

class RawKeyboardManager:
    _instance: Optional["RawKeyboardManager"] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "RawKeyboardManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = RawKeyboardManager()
            return cls._instance

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._hwnd: Optional[int] = None
        self._wndproc = None
        self._class_name = f"j360More_RawKbd_{os.getpid()}"
        self._running = False
        self._ready_event = threading.Event()

        self._devices_lock = threading.Lock()
        self._handle_to_id: Dict[int, str] = {}
        self._id_to_device: Dict[str, Dict] = {}
        self._key_states: Dict[str, Set[str]] = {}

        self._capture_target_dev: Optional[str] = None
        self._capture_callback: Optional[Callable[[str], None]] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._ready_event.clear()
        self._thread = threading.Thread(target=self._run_message_loop, daemon=True, name="RawKeyboardThread")
        self._thread.start()
        self._ready_event.wait(timeout=2.0)
        self.refresh_devices()

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_QUIT_CUSTOM, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        self._hwnd = None

    def refresh_devices(self) -> List[Dict]:
        num = wintypes.UINT()
        res = user32.GetRawInputDeviceList(None, ctypes.byref(num), ctypes.sizeof(RAWINPUTDEVICELIST))
        if num.value == 0:
            return []

        dev_list = (RAWINPUTDEVICELIST * num.value)()
        user32.GetRawInputDeviceList(dev_list, ctypes.byref(num), ctypes.sizeof(RAWINPUTDEVICELIST))

        found_devices = []
        seen_paths = set()

        with self._devices_lock:
            for d in dev_list:
                if d.dwType == RIM_TYPEKEYBOARD:
                    size = wintypes.UINT()
                    user32.GetRawInputDeviceInfoW(d.hDevice, RIDI_DEVICENAME, None, ctypes.byref(size))
                    if size.value > 0:
                        buf = ctypes.create_unicode_buffer(size.value)
                        user32.GetRawInputDeviceInfoW(d.hDevice, RIDI_DEVICENAME, buf, ctypes.byref(size))
                        dev_path = buf.value
                        if not dev_path or dev_path in seen_paths:
                            continue
                        if "MICROSOFT KEYBOARD RID" in dev_path.upper():
                            continue

                        seen_paths.add(dev_path)
                        stable_hash = hashlib.md5(dev_path.upper().encode("utf-8")).hexdigest()[:8]
                        dev_id = f"kbd_{stable_hash}"

                        friendly_name, vendor, conn_type = get_device_friendly_name(dev_path)

                        dev_info = {
                            "id": dev_id,
                            "hDevice": d.hDevice,
                            "path": dev_path,
                            "name": friendly_name,
                            "vendor_name": vendor,
                            "product_name": friendly_name,
                            "instance_id": stable_hash,
                            "conn_type": conn_type,
                            "type": "keyboard"
                        }

                        self._handle_to_id[d.hDevice] = dev_id
                        self._id_to_device[dev_id] = dev_info
                        if dev_id not in self._key_states:
                            self._key_states[dev_id] = set()

                        found_devices.append(dev_info)

        return found_devices

    def get_available_keyboards(self) -> List[Dict]:
        with self._devices_lock:
            return list(self._id_to_device.values())

    def get_pressed_keys(self, dev_id: str) -> Set[str]:
        with self._devices_lock:
            return set(self._key_states.get(dev_id, set()))

    def start_capture(self, dev_id: str, callback: Callable[[str], None]):
        with self._devices_lock:
            self._capture_target_dev = dev_id
            self._capture_callback = callback

    def cancel_capture(self):
        with self._devices_lock:
            self._capture_target_dev = None
            self._capture_callback = None

    def _resolve_handle_to_id(self, h_device: int) -> Optional[str]:
        if h_device in self._handle_to_id:
            return self._handle_to_id[h_device]

        size = wintypes.UINT()
        user32.GetRawInputDeviceInfoW(wintypes.HANDLE(h_device), RIDI_DEVICENAME, None, ctypes.byref(size))
        if size.value > 0:
            buf = ctypes.create_unicode_buffer(size.value)
            user32.GetRawInputDeviceInfoW(wintypes.HANDLE(h_device), RIDI_DEVICENAME, buf, ctypes.byref(size))
            dev_path = buf.value
            if dev_path and "MICROSOFT KEYBOARD RID" not in dev_path.upper():
                stable_hash = hashlib.md5(dev_path.upper().encode("utf-8")).hexdigest()[:8]
                dev_id = f"kbd_{stable_hash}"
                friendly_name, vendor, conn_type = get_device_friendly_name(dev_path)
                dev_info = {
                    "id": dev_id,
                    "hDevice": h_device,
                    "path": dev_path,
                    "name": friendly_name,
                    "vendor_name": vendor,
                    "product_name": friendly_name,
                    "instance_id": stable_hash,
                    "conn_type": conn_type,
                    "type": "keyboard"
                }
                self._handle_to_id[h_device] = dev_id
                self._id_to_device[dev_id] = dev_info
                if dev_id not in self._key_states:
                    self._key_states[dev_id] = set()
                return dev_id
        return None

    def _on_raw_key_event(self, h_device: int, vkey: int, flags: int):
        if vkey == 0 or vkey == 0xFF:
            return

        dev_id = self._resolve_handle_to_id(h_device)
        if not dev_id:
            return

        is_release = bool(flags & RI_KEY_BREAK)
        key_name = vk_to_friendly_name(vkey, flags)

        with self._devices_lock:
            if is_release:
                if dev_id in self._key_states and key_name in self._key_states[dev_id]:
                    self._key_states[dev_id].remove(key_name)
            else:
                if dev_id not in self._key_states:
                    self._key_states[dev_id] = set()
                self._key_states[dev_id].add(key_name)

                if self._capture_callback and (self._capture_target_dev == dev_id or self._capture_target_dev is None):
                    cb = self._capture_callback
                    self._capture_target_dev = None
                    self._capture_callback = None
                    try:
                        cb(key_name)
                    except Exception as e:
                        logger.error(f"Error en callback de captura: {e}")

    def _wnd_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if msg == WM_INPUT:
            raw = RAWINPUT()
            size = wintypes.UINT(ctypes.sizeof(RAWINPUT))
            ret = user32.GetRawInputData(
                wintypes.HANDLE(lparam),
                RID_INPUT,
                ctypes.byref(raw),
                ctypes.byref(size),
                ctypes.sizeof(RAWINPUTHEADER)
            )
            if ret != 0xFFFFFFFF and raw.header.dwType == RIM_TYPEKEYBOARD:
                kb = raw.data.keyboard
                self._on_raw_key_event(raw.header.hDevice, kb.VKey, kb.Flags)
            return 0

        elif msg == WM_INPUT_DEVICE_CHANGE:
            self.refresh_devices()
            return 0

        elif msg == WM_QUIT_CUSTOM or msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run_message_loop(self):
        self._wndproc = WNDPROC(self._wnd_proc)
        hinst = kernel32.GetModuleHandleW(None)

        cls = WNDCLASSEXW()
        cls.cbSize = ctypes.sizeof(WNDCLASSEXW)
        cls.lpfnWndProc = self._wndproc
        cls.hInstance = hinst
        cls.lpszClassName = self._class_name

        atom = user32.RegisterClassExW(ctypes.byref(cls))
        if not atom:
            self._ready_event.set()
            return

        self._hwnd = user32.CreateWindowExW(
            0, self._class_name, "j360More_RawKbd_Window",
            0, 0, 0, 0, 0,
            HWND_MESSAGE, None, hinst, None
        )

        if not self._hwnd:
            user32.UnregisterClassW(self._class_name, hinst)
            self._ready_event.set()
            return

        rid = RAWINPUTDEVICE()
        rid.usUsagePage = 1
        rid.usUsage = 6
        rid.dwFlags = RIDEV_INPUTSINK | RIDEV_DEVNOTIFY
        rid.hwndTarget = self._hwnd

        res = user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE))
        if not res:
            user32.DestroyWindow(self._hwnd)
            user32.UnregisterClassW(self._class_name, hinst)
            self._ready_event.set()
            return

        self._ready_event.set()

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._hwnd:
            user32.DestroyWindow(self._hwnd)
        user32.UnregisterClassW(self._class_name, hinst)
