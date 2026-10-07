from __future__ import annotations
import os
import sys
import platform
import time
import socket
import struct
import subprocess
import threading
from typing import Dict, Any, Optional, Callable

# Rutas estándar de binarios
BIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
HIDMAESTRO_SUBDIR = os.path.join(BIN_DIR, "hidmaestro")

# Mapeo de botones abstractos estándar (HMButton bitmask en hidmaestro_host)
HM_BUTTONS = {
    'A': 1 << 0,
    'B': 1 << 1,
    'X': 1 << 2,
    'Y': 1 << 3,
    'LEFT_SHOULDER': 1 << 4,
    'RIGHT_SHOULDER': 1 << 5,
    'BACK': 1 << 6,
    'START': 1 << 7,
    'LEFT_THUMB': 1 << 8,
    'RIGHT_THUMB': 1 << 9,
    'GUIDE': 1 << 10,
    'TOUCHPAD': 1 << 11,
    'SHARE': 1 << 12,
}

# Mapeo de perfiles predeterminados en HIDMaestro
DEFAULT_PROFILES = {
    'xbox360': 'xbox-360-wired',
    'xboxone': 'xbox-one-s',
    'xbox_one': 'xbox-one-s',
    'xboxseries': 'xbox-series-xs',
    'xbox_series': 'xbox-series-xs',
    'xboxelite': 'xbox-elite-v2',
    'xbox_elite': 'xbox-elite-v2',
    'ds4': 'dualshock-4-v2-composite',
    'dualsense': 'dualsense',
    'ns2pro': 'switch-pro',
    'switchpro': 'switch-pro',
    'switch_pro': 'switch-pro',
    'joycon': 'joycon-charging-grip',
    'joycon_grip': 'joycon-charging-grip',
    'joycon_switch': 'joycon-charging-grip',
}

def get_candidate_bin_dirs() -> List[str]:
    dirs = []
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        bundle_dir = getattr(sys, '_MEIPASS', exe_dir)
        dirs.append(os.path.join(exe_dir, "bin"))
        dirs.append(exe_dir)
        if bundle_dir != exe_dir:
            dirs.append(os.path.join(bundle_dir, "bin"))
            dirs.append(bundle_dir)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dirs.append(os.path.join(base_dir, "bin"))
    dirs.append(base_dir)
    return dirs

def find_hidmaestro_executable() -> Optional[str]:
    mach = platform.machine().lower()
    is_arm = mach in ('aarch64', 'arm64')

    candidates = []
    for d in get_candidate_bin_dirs():
        if is_arm:
            candidates.extend([
                os.path.join(d, "hidmaestro_host-arm64.exe"),
                os.path.join(d, "hidmaestro_host_arm64.exe"),
                os.path.join(d, "arm64", "hidmaestro_host.exe"),
                os.path.join(d, "hidmaestro", "arm64", "hidmaestro_host.exe"),
                os.path.join(d, "hidmaestro_host.exe"),
            ])
        else:
            candidates.extend([
                os.path.join(d, "hidmaestro_host-amd64.exe"),
                os.path.join(d, "hidmaestro_host_amd64.exe"),
                os.path.join(d, "hidmaestro_host.exe"),
                os.path.join(d, "amd64", "hidmaestro_host.exe"),
                os.path.join(d, "hidmaestro", "amd64", "hidmaestro_host.exe"),
            ])

    for c in candidates:
        if os.path.isfile(c):
            return c
    return None

def find_hidmaestro_dll() -> Optional[str]:
    is_arm = platform.machine().lower() in ("arm64", "aarch64")
    if is_arm:
        dll_names = ["HIDMaestro.Core.arm64.dll", "HIDMaestro.Core.dll"]
    else:
        dll_names = ["HIDMaestro.Core.amd64.dll", "HIDMaestro.Core.x64.dll", "HIDMaestro.Core.dll"]

    exe = find_hidmaestro_executable()
    if exe:
        exe_dir = os.path.dirname(exe)
        for name in dll_names:
            sibling = os.path.join(exe_dir, name)
            if os.path.isfile(sibling):
                return sibling

    for d in get_candidate_bin_dirs():
        for name in dll_names:
            cand = os.path.join(d, name)
            if os.path.isfile(cand):
                return cand
            cand_sub = os.path.join(d, "hidmaestro", name)
            if os.path.isfile(cand_sub):
                return cand_sub
    return None

def is_hidmaestro_available() -> bool:
    """Verifica si los binarios requeridos de HIDMaestro están presentes en el sistema."""
    if sys.platform != "win32":
        return False
    return find_hidmaestro_executable() is not None and find_hidmaestro_dll() is not None

def is_hidmaestro_driver_installed() -> bool:
    """Verifica si el controlador HIDMaestro está registrado en el DriverStore de Windows."""
    if sys.platform != "win32":
        return False
    windir = os.environ.get("SystemRoot", r"C:\Windows")
    file_repo = os.path.join(windir, "System32", "DriverStore", "FileRepository")
    if os.path.isdir(file_repo):
        try:
            for entry in os.scandir(file_repo):
                if entry.name.lower().startswith("hidmaestro.inf_"):
                    return True
        except Exception:
            pass
    return False

def install_hidmaestro_driver() -> bool:
    """Invoca la instalación del controlador HIDMaestro con elevación UAC."""
    if sys.platform != "win32":
        return False
    exe = find_hidmaestro_executable()
    if not exe:
        return False
    try:
        import ctypes
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, "--install-driver", os.path.dirname(exe), 1)
        if rc > 32:
            for _ in range(40):
                time.sleep(0.5)
                if is_hidmaestro_driver_installed():
                    return True
        return False
    except Exception as e:
        print(f"[!] Error ejecutando instalación de driver HIDMaestro: {e}")
        return False

class HidMaestroClient:
    """Cliente para comunicarse con el servidor hidmaestro_host vía TCP."""

    def __init__(self, host: str = "127.0.0.1", port: int = 3255):
        self.host = host
        self.port = port
        self.server_proc: Optional[subprocess.Popen] = None
        self.sock: Optional[socket.socket] = None
        self.writer = None
        self.reader = None
        self.devices: Dict[int, Dict[str, Any]] = {}
        self.feedback_callbacks: Dict[int, Callable[[int, int, int], None]] = {}
        self.running = False
        self.listener_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

    def is_server_alive(self, require_elevated: bool = False) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect((self.host, self.port))
            s.sendall(b"PING\n")
            resp = s.recv(64).decode("utf-8", errors="ignore").strip()
            s.close()
            if not resp.startswith("PONG"):
                return False
            if require_elevated:
                return "ELEVATED" in resp and "NOT_ELEVATED" not in resp
            return True
        except Exception:
            return False

    def is_server_elevated(self) -> bool:
        return self.is_server_alive(require_elevated=True)

    def ensure_server_running(self) -> bool:
        # 1. Si ya está corriendo, listo
        if self.is_server_alive():
            return True

        exe_path = find_hidmaestro_executable()
        if not exe_path:
            print("[!] HIDMaestro: No se encontró hidmaestro_host.exe en bin/hidmaestro/ ni bin/.")
            return False

        import ctypes
        is_admin = False
        try:
            is_admin = (ctypes.windll.shell32.IsUserAnAdmin() != 0)
        except Exception:
            pass

        if is_admin:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE

            server_args = [exe_path, f"--port={self.port}", "--quiet"]
            try:
                self.server_proc = subprocess.Popen(
                    server_args,
                    cwd=os.path.dirname(exe_path),
                    env=os.environ,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    startupinfo=startupinfo
                )
            except Exception as e:
                print(f"[!] Error iniciando hidmaestro_host: {e}")
                return False
        else:
            # En Windows se requiere elevación administrativa para crear dispositivos virtuales HIDMaestro.
            # Intentamos ShellExecuteW con 'runas' para invocar el diálogo UAC estándar interactivo.
            params = f"--port={self.port} --quiet"
            rc = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                exe_path,
                params,
                os.path.dirname(exe_path),
                0  # SW_HIDE
            )
            if rc <= 32:
                # Si falló ShellExecuteW, intentamos arrancar con auto-elevación interna
                startupinfo = None
                if sys.platform == "win32":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = 0
                server_args = [exe_path, f"--port={self.port}", "--quiet", "--elevate"]
                try:
                    self.server_proc = subprocess.Popen(
                        server_args,
                        cwd=os.path.dirname(exe_path),
                        env=os.environ,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        startupinfo=startupinfo
                    )
                except Exception:
                    pass

        # Esperar hasta 15 segundos para dar tiempo al usuario de aceptar el diálogo UAC
        for _ in range(100):
            time.sleep(0.15)
            if self.is_server_alive(require_elevated=True):
                print(f"[+] Servidor HIDMaestro listo y elevado en {self.host}:{self.port}.")
                return True
            if self.server_proc and self.server_proc.poll() is not None:
                if self.is_server_alive(require_elevated=True):
                    print(f"[+] Servidor HIDMaestro listo y elevado en {self.host}:{self.port}.")
                    return True
        print("[!] No se pudo iniciar hidmaestro_host con privilegios de Administrador.")
        return False

    def start(self) -> bool:
        """Inicia el servidor y se conecta al socket de control y streaming."""
        if not self.ensure_server_running():
            return False

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.settimeout(10.0)
            self.sock.connect((self.host, self.port))
            self.running = True

            # Iniciar hilo lector de eventos (rumble/output)
            self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.listener_thread.start()
            return True
        except Exception as e:
            print(f"[!] Error conectando a HIDMaestro: {e}")
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
            return False

    def _listen_loop(self):
        buf = b""
        while self.running and self.sock:
            try:
                data = self.sock.recv(1024)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line_str = line.decode("utf-8", errors="ignore").strip()
                    if line_str.startswith("RUMBLE "):
                        parts = line_str.split()
                        if len(parts) >= 4:
                            try:
                                slot = int(parts[1])
                                left = int(parts[2])
                                right = int(parts[3])
                                cb = self.feedback_callbacks.get(slot)
                                if cb:
                                    cb(slot, left, right)
                            except Exception:
                                pass
            except Exception:
                break

    def _send_cmd(self, cmd_line: str, timeout: float = 4.0) -> str:
        with self.lock:
            if not self.sock:
                return "ERROR No conectado"
            try:
                # Usar socket temporal para transacciones de comando o enviar en el mismo
                # Para evitar carreras con el listener, abrimos una conexión de comando corta
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(timeout)
                s.connect((self.host, self.port))
                s.sendall(cmd_line.encode("utf-8") + b"\n")
                resp = s.recv(1024).decode("utf-8", errors="ignore").strip()
                s.close()
                return resp
            except Exception as e:
                return f"ERROR {e}"

    def is_driver_installed(self) -> bool:
        if is_hidmaestro_driver_installed():
            return True
        resp = self._send_cmd("IS_DRIVER_INSTALLED")
        return resp.strip().upper() == "YES"

    def install_driver(self) -> bool:
        resp = self._send_cmd("INSTALL_DRIVER", timeout=30.0)
        if resp.strip().upper().startswith("OK"):
            return True
        return install_hidmaestro_driver()

    def add_device(self, slot_idx: int, pad_type: str, feedback_cb: Optional[Callable[[int, int, int], None]] = None) -> bool:
        norm_type = pad_type.lower()
        profile_id = DEFAULT_PROFILES.get(norm_type, "xbox-360-wired")

        if feedback_cb:
            self.feedback_callbacks[slot_idx] = feedback_cb

        resp = self._send_cmd(f"ADD {slot_idx} {profile_id}", timeout=15.0)
        if resp.startswith("OK"):
            self.devices[slot_idx] = {"type": norm_type, "profile": profile_id}
            return True
        print(f"[!] HIDMaestro error creando mando #{slot_idx}: {resp}")
        return False

    def remove_device(self, slot_idx: int) -> bool:
        self.devices.pop(slot_idx, None)
        self.feedback_callbacks.pop(slot_idx, None)
        resp = self._send_cmd(f"REMOVE {slot_idx}")
        return resp.startswith("OK")

    def send_state(self, slot_idx: int, buttons: int, dpad: int, lt: int, rt: int, lx: int, ly: int, rx: int, ry: int):
        """Envía paquete binario rápido de 18 bytes (4 header + 14 payload) directamente por el socket."""
        if not self.running or not self.sock:
            return
        # Header: 'H' 'M' slot cmd(1)
        # Payload: <H (buttons), B (dpad), B (lt), B (rt), h (lx), h (ly), h (rx), h (ry), B (padding=0) -> 18 bytes
        packet = struct.pack('<ccBBHBBBhhhhB', b'H', b'M', slot_idx & 0xFF, 1,
                             buttons & 0xFFFF, dpad & 0xFF, lt & 0xFF, rt & 0xFF,
                             lx, ly, rx, ry, 0)
        try:
            self.sock.sendall(packet)
        except Exception:
            pass

    def send_xbox360_state(self, slot_idx: int, buttons: int, lt: int, rt: int, lx: int, ly: int, rx: int, ry: int):
        # Mapeo de botones estándar Xbox 360 a HM_BUTTONS
        hm_btns = 0
        if buttons & 0x1000: hm_btns |= HM_BUTTONS['A']
        if buttons & 0x2000: hm_btns |= HM_BUTTONS['B']
        if buttons & 0x4000: hm_btns |= HM_BUTTONS['X']
        if buttons & 0x8000: hm_btns |= HM_BUTTONS['Y']
        if buttons & 0x0100: hm_btns |= HM_BUTTONS['LEFT_SHOULDER']
        if buttons & 0x0200: hm_btns |= HM_BUTTONS['RIGHT_SHOULDER']
        if buttons & 0x0020: hm_btns |= HM_BUTTONS['BACK']
        if buttons & 0x0010: hm_btns |= HM_BUTTONS['START']
        if buttons & 0x0040: hm_btns |= HM_BUTTONS['LEFT_THUMB']
        if buttons & 0x0080: hm_btns |= HM_BUTTONS['RIGHT_THUMB']
        if buttons & 0x0400: hm_btns |= HM_BUTTONS['GUIDE']

        dpad = 0
        up = bool(buttons & 0x0001)
        down = bool(buttons & 0x0002)
        left = bool(buttons & 0x0004)
        right = bool(buttons & 0x0008)
        if up and right: dpad = 5
        elif up and left: dpad = 8
        elif down and right: dpad = 6
        elif down and left: dpad = 7
        elif up: dpad = 1
        elif down: dpad = 2
        elif left: dpad = 3
        elif right: dpad = 4

        self.send_state(slot_idx, hm_btns, dpad, lt, rt, lx, ly, rx, ry)

    def send_xboxone_state(self, slot_idx: int, buttons: int, lt: int, rt: int, lx: int, ly: int, rx: int, ry: int):
        # Para Xbox One, el mapeo de bits GIP estándar se traslada
        # En GIP: DPAD 0..3, START 4, BACK 5, L3 6, R3 7, LB 8, RB 9, GUIDE 10, A 11, B 12, X 13, Y 14, SHARE 15
        hm_btns = 0
        if buttons & (1 << 11): hm_btns |= HM_BUTTONS['A']
        if buttons & (1 << 12): hm_btns |= HM_BUTTONS['B']
        if buttons & (1 << 13): hm_btns |= HM_BUTTONS['X']
        if buttons & (1 << 14): hm_btns |= HM_BUTTONS['Y']
        if buttons & (1 << 8): hm_btns |= HM_BUTTONS['LEFT_SHOULDER']
        if buttons & (1 << 9): hm_btns |= HM_BUTTONS['RIGHT_SHOULDER']
        if buttons & (1 << 5): hm_btns |= HM_BUTTONS['BACK']
        if buttons & (1 << 4): hm_btns |= HM_BUTTONS['START']
        if buttons & (1 << 6): hm_btns |= HM_BUTTONS['LEFT_THUMB']
        if buttons & (1 << 7): hm_btns |= HM_BUTTONS['RIGHT_THUMB']
        if buttons & (1 << 10): hm_btns |= HM_BUTTONS['GUIDE']
        if buttons & (1 << 15): hm_btns |= HM_BUTTONS['SHARE']

        dpad = 0
        up = bool(buttons & (1 << 0))
        down = bool(buttons & (1 << 1))
        left = bool(buttons & (1 << 2))
        right = bool(buttons & (1 << 3))
        if up and right: dpad = 5
        elif up and left: dpad = 8
        elif down and right: dpad = 6
        elif down and left: dpad = 7
        elif up: dpad = 1
        elif down: dpad = 2
        elif left: dpad = 3
        elif right: dpad = 4

        self.send_state(slot_idx, hm_btns, dpad, lt, rt, lx, ly, rx, ry)

    def send_xboxseries_state(self, slot_idx: int, buttons: int, lt: int, rt: int, lx: int, ly: int, rx: int, ry: int):
        self.send_xboxone_state(slot_idx, buttons, lt, rt, lx, ly, rx, ry)

    def send_xboxelite_state(self, slot_idx: int, buttons: int, lt: int, rt: int, lx: int, ly: int, rx: int, ry: int):
        self.send_xboxone_state(slot_idx, buttons, lt, rt, lx, ly, rx, ry)

    def send_ds4_state(self, slot_idx: int, buttons: int, dpad_mask: int, lt: int, rt: int, lx: int, ly: int, rx: int, ry: int):
        hm_btns = 0
        if buttons & 0x0020: hm_btns |= HM_BUTTONS['A']            # Cross
        if buttons & 0x0040: hm_btns |= HM_BUTTONS['B']            # Circle
        if buttons & 0x0010: hm_btns |= HM_BUTTONS['X']            # Square
        if buttons & 0x0080: hm_btns |= HM_BUTTONS['Y']            # Triangle
        if buttons & 0x0100: hm_btns |= HM_BUTTONS['LEFT_SHOULDER'] # L1
        if buttons & 0x0200: hm_btns |= HM_BUTTONS['RIGHT_SHOULDER']# R1
        if buttons & 0x1000: hm_btns |= HM_BUTTONS['BACK']          # Share
        if buttons & 0x2000: hm_btns |= HM_BUTTONS['START']         # Options
        if buttons & 0x4000: hm_btns |= HM_BUTTONS['LEFT_THUMB']    # L3
        if buttons & 0x8000: hm_btns |= HM_BUTTONS['RIGHT_THUMB']   # R3
        if buttons & 0x0001: hm_btns |= HM_BUTTONS['GUIDE']         # PS
        if buttons & 0x0002: hm_btns |= HM_BUTTONS['TOUCHPAD']      # Touchpad

        dpad = 0
        up = bool(dpad_mask & 1)
        down = bool(dpad_mask & 2)
        left = bool(dpad_mask & 4)
        right = bool(dpad_mask & 8)
        if up and right: dpad = 5
        elif up and left: dpad = 8
        elif down and right: dpad = 6
        elif down and left: dpad = 7
        elif up: dpad = 1
        elif down: dpad = 2
        elif left: dpad = 3
        elif right: dpad = 4

        self.send_state(slot_idx, hm_btns, dpad, lt, rt, lx, ly, rx, ry)

    def send_dualsense_state(self, slot_idx: int, buttons: int, dpad_mask: int, lt: int, rt: int, lx: int, ly: int, rx: int, ry: int):
        hm_btns = 0
        if buttons & 0x00000020: hm_btns |= HM_BUTTONS['A']            # Cross
        if buttons & 0x00000040: hm_btns |= HM_BUTTONS['B']            # Circle
        if buttons & 0x00000010: hm_btns |= HM_BUTTONS['X']            # Square
        if buttons & 0x00000080: hm_btns |= HM_BUTTONS['Y']            # Triangle
        if buttons & 0x00000100: hm_btns |= HM_BUTTONS['LEFT_SHOULDER'] # L1
        if buttons & 0x00000200: hm_btns |= HM_BUTTONS['RIGHT_SHOULDER']# R1
        if buttons & 0x00001000: hm_btns |= HM_BUTTONS['BACK']          # Create
        if buttons & 0x00002000: hm_btns |= HM_BUTTONS['START']         # Options
        if buttons & 0x00004000: hm_btns |= HM_BUTTONS['LEFT_THUMB']    # L3
        if buttons & 0x00008000: hm_btns |= HM_BUTTONS['RIGHT_THUMB']   # R3
        if buttons & 0x00010000: hm_btns |= HM_BUTTONS['GUIDE']         # PS
        if buttons & 0x00020000: hm_btns |= HM_BUTTONS['TOUCHPAD']      # Touchpad

        dpad = 0
        up = bool(dpad_mask & 1)
        down = bool(dpad_mask & 2)
        left = bool(dpad_mask & 4)
        right = bool(dpad_mask & 8)
        if up and right: dpad = 5
        elif up and left: dpad = 8
        elif down and right: dpad = 6
        elif down and left: dpad = 7
        elif up: dpad = 1
        elif down: dpad = 2
        elif left: dpad = 3
        elif right: dpad = 4

        self.send_state(slot_idx, hm_btns, dpad, lt, rt, lx, ly, rx, ry)

    def stop(self):
        self.running = False
        try:
            self._send_cmd("QUIT", timeout=2.0)
        except Exception:
            pass

        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

        if self.server_proc:
            try:
                self.server_proc.terminate()
                self.server_proc.wait(timeout=2.0)
            except Exception:
                try:
                    self.server_proc.kill()
                except Exception:
                    pass
            self.server_proc = None

        self.devices.clear()
        self.feedback_callbacks.clear()
