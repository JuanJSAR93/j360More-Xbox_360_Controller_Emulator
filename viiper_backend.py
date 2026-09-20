import os
import sys
import time
import socket
import struct
import json
import subprocess
from typing import Dict, Any, Optional, List, Tuple

# Xbox 360 Buttons
XBOX_BUTTONS = {
    'DPAD_UP': 0x0001,
    'DPAD_DOWN': 0x0002,
    'DPAD_LEFT': 0x0004,
    'DPAD_RIGHT': 0x0008,
    'START': 0x0010,
    'BACK': 0x0020,
    'LEFT_THUMB': 0x0040,
    'RIGHT_THUMB': 0x0080,
    'LEFT_SHOULDER': 0x0100,
    'RIGHT_SHOULDER': 0x0200,
    'GUIDE': 0x0400,
    'A': 0x1000,
    'B': 0x2000,
    'X': 0x4000,
    'Y': 0x8000,
}

# DS4 Buttons
DS4_BUTTONS = {
    'X': 0x0010,       # Square
    'A': 0x0020,       # Cross
    'B': 0x0040,       # Circle
    'Y': 0x0080,       # Triangle
    'LEFT_SHOULDER': 0x0100,  # L1
    'RIGHT_SHOULDER': 0x0200, # R1
    'L2_BTN': 0x0400,
    'R2_BTN': 0x0800,
    'BACK': 0x1000,    # Share
    'START': 0x2000,   # Options
    'LEFT_THUMB': 0x4000,
    'RIGHT_THUMB': 0x8000,
    'GUIDE': 0x0001,   # PS
    'TOUCHPAD': 0x0002,
}

# DualSense Buttons
DUALSENSE_BUTTONS = {
    'X': 0x00000010,       # Square
    'A': 0x00000020,       # Cross
    'B': 0x00000040,       # Circle
    'Y': 0x00000080,       # Triangle
    'LEFT_SHOULDER': 0x00000100,
    'RIGHT_SHOULDER': 0x00000200,
    'L2_BTN': 0x00000400,
    'R2_BTN': 0x00000800,
    'BACK': 0x00001000,    # Create
    'START': 0x00002000,   # Options
    'LEFT_THUMB': 0x00004000,
    'RIGHT_THUMB': 0x00008000,
    'GUIDE': 0x00010000,   # PS
    'TOUCHPAD': 0x00020000,
    'MUTE': 0x00040000,
}

# Switch 2 Pro Buttons (aligned with VIIPER device/ns2pro/const.go)
NS2PRO_BUTTONS = {
    'B': 0x00000001,
    'A': 0x00000002,
    'Y': 0x00000004,
    'X': 0x00000008,
    'RIGHT_SHOULDER': 0x00000010,  # ButtonR
    'ZR': 0x00000020,              # ButtonZR
    'RIGHT_TRIGGER': 0x00000020,
    'START': 0x00000040,           # ButtonPlus (+)
    'RIGHT_THUMB': 0x00000080,     # ButtonRightStick
    'DPAD_DOWN': 0x00000100,       # ButtonDown
    'DPAD_RIGHT': 0x00000200,      # ButtonRight
    'DPAD_LEFT': 0x00000400,       # ButtonLeft
    'DPAD_UP': 0x00000800,         # ButtonUp
    'LEFT_SHOULDER': 0x00001000,   # ButtonL
    'ZL': 0x00002000,              # ButtonZL
    'LEFT_TRIGGER': 0x00002000,
    'BACK': 0x00004000,            # ButtonMinus (-)
    'LEFT_THUMB': 0x00008000,      # ButtonLeftStick
    'GUIDE': 0x00010000,           # ButtonHome
    'CAPTURE': 0x00020000,         # ButtonCapture
}

def find_viiper_executable() -> Optional[str]:
    bin_name = 'viiper.exe' if sys.platform == 'win32' else 'viiper'
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, 'bin', bin_name),
        os.path.join(base_dir, 'assets', 'bin', bin_name),
    ]
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        bundle_dir = getattr(sys, '_MEIPASS', exe_dir)
        candidates.extend([
            os.path.join(exe_dir, 'bin', bin_name),
            os.path.join(exe_dir, bin_name),
            os.path.join(bundle_dir, 'bin', bin_name),
            os.path.join(bundle_dir, bin_name),
        ])
    if sys.platform == 'win32':
        local_app = os.environ.get('LOCALAPPDATA', '')
        if local_app:
            candidates.append(os.path.join(local_app, 'VIIPER', 'viiper.exe'))
    else:
        candidates.extend(['/usr/local/bin/viiper', '/usr/bin/viiper'])
    
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK if sys.platform != 'win32' else os.R_OK):
            return c
    
    import shutil
    return shutil.which(bin_name)

get_viiper_binary_path = find_viiper_executable

def is_usbip_installed() -> bool:
    if sys.platform != 'win32':
        import shutil
        return shutil.which('usbip') is not None
    ensure_usbip_in_path()
    import shutil
    return shutil.which('usbip.exe') is not None

def ensure_usbip_in_path():
    if sys.platform == 'win32':
        known_dirs = [
            r'C:\Program Files\USBip',
            r'C:\Program Files (x86)\USBip',
        ]
        cur_path = os.environ.get('PATH', '')
        for kd in known_dirs:
            if os.path.isdir(kd) and kd.lower() not in cur_path.lower():
                os.environ['PATH'] = kd + os.pathsep + cur_path
                cur_path = os.environ['PATH']

class ViiperClient:
    def __init__(self, host: str = '127.0.0.1', port: int = 3242):
        self.host = host
        self.port = port
        self.server_proc: Optional[subprocess.Popen] = None
        self.bus_id: Optional[int] = None
        self.devices: Dict[int, Dict[str, Any]] = {} # slot -> {devId, type, stream_socket}
        self.running = False

    def ensure_server_running(self) -> bool:
        # Check if port 3242 is responding
        if self._is_port_open():
            return True

        exe_path = find_viiper_executable()
        if not exe_path:
            print('[!] VIIPER: No se encontro el ejecutable viiper en el sistema.')
            return False

        ensure_usbip_in_path()
        print(f'[*] Iniciando servidor VIIPER: {exe_path}')
        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0 # SW_HIDE

        self.server_proc = subprocess.Popen(
            [exe_path, 'server', '--log.level=warn'],
            env=os.environ,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo
        )

        for _ in range(30):
            time.sleep(0.1)
            if self._is_port_open():
                print('[+] Servidor VIIPER listo y escuchando.')
                return True
        return False

    def _is_port_open(self) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect((self.host, self.port))
            s.close()
            return True
        except Exception:
            return False

    def _send_cmd(self, cmd_path: str, payload: Optional[dict] = None) -> dict:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(4.0)
        s.connect((self.host, self.port))
        line = cmd_path
        if payload is not None:
            line += ' ' + json.dumps(payload)
        s.sendall(line.encode('utf-8') + b'\0')
        raw = b''
        while True:
            chunk = s.recv(2048)
            if not chunk:
                break
            raw += chunk
            if b'\n' in raw or b'\0' in raw:
                break
        s.close()
        text = raw.decode('utf-8', errors='ignore').strip('\0\r\n')
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            return {'raw': text}

    def start_bus(self) -> bool:
        if not self.ensure_server_running():
            return False
        res = self._send_cmd('bus/create')
        if 'busId' in res:
            self.bus_id = res['busId']
            self.running = True
            return True
        print(f'[!] Error creando bus en VIIPER: {res}')
        return False

    def add_device(self, slot: int, dev_type: str) -> bool:
        if not self.bus_id:
            if not self.start_bus():
                return False

        # Map to VIIPER dev type
        vtype = dev_type.lower()
        if vtype == 'ds4':
            vtype = 'dualshock4'

        res = self._send_cmd(f'bus/{self.bus_id}/add', {'type': vtype})
        if 'devId' not in res:
            print(f'[!] Error anadiendo {dev_type} al bus {self.bus_id}: {res}')
            return False

        dev_id = str(res['devId'])
        # Connect persistent streaming socket
        stream_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        stream_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        stream_sock.connect((self.host, self.port))
        stream_sock.sendall(f'bus/{self.bus_id}/{dev_id}\0'.encode('utf-8'))

        self.devices[slot] = {
            'devId': dev_id,
            'type': vtype,
            'socket': stream_sock,
            'buttons': 0,
            'lt': 0,
            'rt': 0,
            'lx': 0,
            'ly': 0,
            'rx': 0,
            'ry': 0,
            'dpad': 0, # for sony
        }
        return True

    def send_xbox360_state(self, slot: int, buttons: int, lt: int, rt: int, lx: int, ly: int, rx: int, ry: int):
        dev = self.devices.get(slot)
        if not dev or dev.get('socket') is None:
            return
        # VIIPER Xbox 360: 20 bytes (<IBBhhhh6s)
        # Buttons uint32, LT uint8, RT uint8, LX, LY, RX, RY int16, Reserved 6s
        pkt = struct.pack('<IBBhhhh6s', buttons, lt, rt, lx, ly, rx, ry, b'\x00' * 6)
        try:
            dev['socket'].sendall(pkt)
        except Exception:
            pass

    def send_ds4_state(self, slot: int, buttons: int, dpad: int, l2: int, r2: int, lx: int, ly: int, rx: int, ry: int):
        dev = self.devices.get(slot)
        if not dev or dev.get('socket') is None:
            return
        # VIIPER DS4: 31 bytes (<bbbbHBBB22s)
        # LX, LY, RX, RY int8 (-128..127)
        # Buttons uint16, DPad uint8 (0x01 U, 0x02 D, 0x04 L, 0x08 R), L2 uint8, R2 uint8 (0..255)
        # Default IMU AccelZ = -5023
        imu_touch = bytearray(22)
        struct.pack_into('<h', imu_touch, 16, -5023)
        pkt = struct.pack('<bbbbHBBB22s', lx, ly, rx, ry, buttons, dpad, l2, r2, bytes(imu_touch))
        try:
            dev['socket'].sendall(pkt)
        except Exception:
            pass

    def send_dualsense_state(self, slot: int, buttons: int, dpad: int, l2: int, r2: int, lx: int, ly: int, rx: int, ry: int):
        dev = self.devices.get(slot)
        if not dev or dev.get('socket') is None:
            return
        # VIIPER DualSense: 33 bytes (<bbbbIBBB22s)
        # LX, LY, RX, RY int8 (-128..127)
        # Buttons uint32, DPad uint8, L2 uint8, R2 uint8 (0..255)
        # Default IMU AccelZ = -5023
        imu_touch = bytearray(22)
        struct.pack_into('<h', imu_touch, 16, -5023)
        pkt = struct.pack('<bbbbIBBB22s', lx, ly, rx, ry, buttons, dpad, l2, r2, bytes(imu_touch))
        try:
            dev['socket'].sendall(pkt)
        except Exception:
            pass

    def send_ns2pro_state(self, slot: int, buttons: int, lx: int, ly: int, rx: int, ry: int):
        dev = self.devices.get(slot)
        if not dev or dev.get('socket') is None:
            return
        # VIIPER Switch 2 Pro: 24 bytes (<IHHHHhhhhhh)
        # Buttons uint32, LX, LY, RX, RY uint16 (0..4095, center 2048)
        # AccelX, AccelY, AccelZ (int16), GyroX, GyroY, GyroZ (int16)
        pkt = struct.pack('<IHHHHhhhhhh', buttons, lx, ly, rx, ry, 0, 0, -4096, 0, 0, 0)
        try:
            dev['socket'].sendall(pkt)
        except Exception:
            pass

    def stop(self):
        self.running = False
        # Close all streams
        for s_info in self.devices.values():
            sock = s_info.get('socket')
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
        self.devices.clear()

        # Remove bus
        if self.bus_id is not None:
            try:
                self._send_cmd(f'bus/remove {self.bus_id}')
            except Exception:
                pass
            self.bus_id = None

        # Terminate server if we started it
        if self.server_proc:
            try:
                self.server_proc.terminate()
                self.server_proc.wait(timeout=1.5)
            except Exception:
                try:
                    self.server_proc.kill()
                except Exception:
                    pass
            self.server_proc = None
