import os
import sys
import time
import socket
import struct
import json
import subprocess
import hashlib
import hmac
import threading
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

# Xbox One Semantic Buttons (conforme a device/xboxone/semantic_input_wire.go)
XBOX_ONE_BUTTONS = {
    'START': 1 << 0,          # Menu
    'BACK': 1 << 1,           # View
    'A': 1 << 2,
    'B': 1 << 3,
    'X': 1 << 4,
    'Y': 1 << 5,
    'DPAD_UP': 1 << 6,
    'DPAD_DOWN': 1 << 7,
    'DPAD_LEFT': 1 << 8,
    'DPAD_RIGHT': 1 << 9,
    'LEFT_SHOULDER': 1 << 10,
    'RIGHT_SHOULDER': 1 << 11,
    'LEFT_THUMB': 1 << 12,
    'RIGHT_THUMB': 1 << 13,
    'GUIDE': 1 << 14,
    'SHARE': 1 << 15,
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
    import platform
    import shutil
    mach = platform.machine().lower()
    if sys.platform == 'win32':
        if mach in ('aarch64', 'arm64'):
            bin_names = ['viiper.exe', 'viiper_arm64.exe', 'viiper-arm64.exe']
        else:
            bin_names = ['viiper.exe', 'viiper-amd64.exe', 'viiper_amd64.exe']
    elif mach in ('aarch64', 'arm64'):
        bin_names = ['viiper', 'viiper-arm64', 'viiper_arm64', 'viiper-aarch64']
    elif mach in ('x86_64', 'amd64'):
        bin_names = ['viiper', 'viiper-amd64', 'viiper_amd64', 'viiper-x86_64']
    else:
        bin_names = ['viiper']

    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = []

    for bn in bin_names:
        candidates.extend([
            os.path.join(base_dir, 'bin', bn),
            os.path.join(base_dir, 'dist', 'bin', bn),
            os.path.join(base_dir, 'assets', 'bin', bn),
        ])
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            bundle_dir = getattr(sys, '_MEIPASS', exe_dir)
            candidates.extend([
                os.path.join(exe_dir, 'bin', bn),
                os.path.join(exe_dir, bn),
                os.path.join(bundle_dir, 'bin', bn),
                os.path.join(bundle_dir, bn),
            ])

    if sys.platform == 'win32':
        local_app = os.environ.get('LOCALAPPDATA', '')
        if local_app:
            candidates.append(os.path.join(local_app, 'VIIPER', 'viiper.exe'))
    else:
        for bn in bin_names:
            candidates.extend([f'/usr/local/bin/{bn}', f'/usr/bin/{bn}'])

    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK if sys.platform != 'win32' else os.R_OK):
            return c

    for bn in bin_names:
        found = shutil.which(bn)
        if found:
            return found
    return None


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


def get_viiper_key() -> Optional[bytes]:
    """Obtiene la clave de autenticación derivada de VIIPER para conexiones autorizadas."""
    key_file_env = os.environ.get('VIIPER_KEY_FILE', '')
    candidates = [key_file_env] if key_file_env else []
    app_data = os.environ.get('APPDATA', '')
    if app_data:
        candidates.append(os.path.join(app_data, 'VIIPER', 'viiper.key.txt'))
    local_app = os.environ.get('LOCALAPPDATA', '')
    if local_app:
        candidates.append(os.path.join(local_app, 'VIIPER', 'viiper.key.txt'))
    home = os.path.expanduser('~')
    candidates.append(os.path.join(home, '.config', 'viiper', 'viiper.key.txt'))

    for c in candidates:
        if c and os.path.isfile(c):
            try:
                with open(c, 'r', encoding='utf-8') as f:
                    pwd = f.read().strip()
                if pwd:
                    return hashlib.pbkdf2_hmac('sha256', pwd.encode('utf-8'), b'VIIPER-Key-v1', 100000, 32)
            except Exception:
                pass
    return None


class ViiperSecureConn:
    """Conexión TCP cifrada con ChaCha20-Poly1305 para API autorizada de VIIPER."""

    def __init__(self, sock: socket.socket, session_key: bytes):
        self.sock = sock
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        self.aead = ChaCha20Poly1305(session_key)
        self.send_ctr = 0

    def write(self, data: bytes):
        nonce = struct.pack('>IQ', 0, self.send_ctr)
        self.send_ctr += 1
        sealed = self.aead.encrypt(nonce, data, None)
        rec_len = 12 + len(data) + 16
        self.sock.sendall(struct.pack('>I', rec_len) + nonce + sealed)

    def read_record(self) -> bytes:
        hdr = b''
        while len(hdr) < 4:
            c = self.sock.recv(4 - len(hdr))
            if not c:
                return b''
            hdr += c
        rec_len = struct.unpack('>I', hdr)[0]
        enc = b''
        while len(enc) < rec_len:
            chunk = self.sock.recv(rec_len - len(enc))
            if not chunk:
                break
            enc += chunk
        if len(enc) < 12:
            return b''
        return self.aead.decrypt(enc[:12], enc[12:], None)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def connect_secure_viiper(host: str, port: int, key: bytes, timeout: float = 10.0) -> ViiperSecureConn:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    s.settimeout(timeout)
    s.connect((host, port))
    client_nonce = os.urandom(32)
    mac = hmac.new(key, b'VIIPER-Auth-v2' + client_nonce, hashlib.sha256).digest()
    s.sendall(b'eVI2\x00' + client_nonce + mac)
    prefix = s.recv(3)
    if prefix != b'OK\x00':
        s.close()
        raise RuntimeError('Handshake de autenticación con VIIPER falló')
    server_nonce = s.recv(32)
    h = hashlib.sha256()
    h.update(key)
    h.update(server_nonce)
    h.update(client_nonce)
    h.update(b'VIIPER-Session-v2')
    return ViiperSecureConn(s, h.digest())


class ViiperClient:
    def __init__(self, host: str = '127.0.0.1', port: int = 3242):
        self.host = host
        self.port = port
        self.server_proc: Optional[subprocess.Popen] = None
        self.bus_id: Optional[int] = None
        self.devices: Dict[int, Dict[str, Any]] = {}
        self.running = False

    def ensure_server_running(self) -> bool:
        # Si el servidor ya responde con estado running, reutilizarlo
        if self.is_server_alive():
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
            startupinfo.wShowWindow = 0  # SW_HIDE

        server_args = [
            exe_path,
            'server',
            '--log.level=warn',
            '--usb.write-batch-flush-interval=8ms',
            '--usb.retained-import-authority-id=1',
            f'--usb.addr=0.0.0.0:{self.port - 1}',
            f'--api.addr={self.host}:{self.port}',
            '--api.auto-attach-local-client=true',
            '--api.auto-attach-windows-native=false',
        ]

        self.server_proc = subprocess.Popen(
            server_args,
            env=os.environ,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo
        )

        for _ in range(40):
            time.sleep(0.1)
            if self.is_server_alive():
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

    def get_server_status(self) -> Optional[Dict[str, Any]]:
        """Consulta el estado en vivo de VIIPER mediante el endpoint 'server/status'."""
        try:
            res = self._send_cmd('server/status')
            if isinstance(res, dict) and res.get('server') == 'VIIPER':
                return res
        except Exception:
            pass
        return None

    def is_server_alive(self) -> bool:
        """Verifica si el servidor VIIPER está activo y respondiendo correctamente."""
        status = self.get_server_status()
        return bool(status and status.get('state') == 'running')

    def restart_server(self) -> bool:
        """Reinicia los listeners del servidor VIIPER in-process mediante 'server/restart'."""
        try:
            res = self._send_cmd('server/restart')
            if isinstance(res, dict) and res.get('accepted') and res.get('action') == 'restart':
                # Limpiar referencias de dispositivos y streams
                for s_info in self.devices.values():
                    conn = s_info.get('secure_conn') or s_info.get('socket')
                    if conn:
                        try:
                            conn.close()
                        except Exception:
                            pass
                self.devices.clear()
                self.bus_id = None
                time.sleep(0.3)
                return self.is_server_alive()
        except Exception:
            pass
        return False

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

        vtype = dev_type.lower()
        if vtype == 'ds4':
            vtype = 'dualshock4'
        elif vtype in ('dualsense', 'ps5'):
            vtype = 'dualsensegamepadv5'

        # Soporte para Xbox One vía flujo retenido autenticado
        if vtype in ('xboxone', 'xbox_one', 'xboxseries'):
            return self._add_xboxone_device(slot, vtype)

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
            'dpad': 0,
        }
        return True

    def _add_xboxone_device(self, slot: int, profile: str) -> bool:
        key = get_viiper_key()
        if not key:
            print('[!] VIIPER Xbox One: No se encontro el archivo de clave de autenticacion en %APPDATA%\\VIIPER\\viiper.key.txt')
            return False

        try:
            device_id = 0x0000fffb00000000 | (int(time.time_ns()) & 0xffffffff)
            import_dev_id = int(time.time_ns())
            serial = f'{device_id:016x}A1B2C3D4E5F60706'
            pid = 0x0B12 if profile == 'xboxseries' else 0x02EA
            prod = "VIIPER Xbox Series X|S Controller" if profile == 'xboxseries' else "VIIPER Xbox One Controller"

            create_req = {
                'version': 1,
                'identityAuthorizationGranted': True,
                'baseGamepadMetadata': True,
                'identity': {
                    'vendorId': 0x045E, 'productId': pid, 'deviceReleaseBcd': 0x0100,
                    'deviceId': device_id, 'firmwareMajor': 1, 'firmwareBuild': 1, 'hardwareMajor': 1
                },
                'usb': {'maxPower2mA': 250, 'outIntervalMs': 4, 'inIntervalMs': 4},
                'strings': {'manufacturer': '©Microsoft Corporation', 'product': prod, 'serial': serial},
                'feedback': {'source': 1, 'personaGeneration': 1, 'deviceGeneration': 1, 'transportGeneration': 1, 'ownershipEpoch': 1, 'timeToLiveMicroseconds': 250000},
                'importDeviceId': import_dev_id, 'localTimeoutMilliseconds': 100
            }

            # 1. Crear persona autorizada
            c_auth = connect_secure_viiper(self.host, self.port, key, timeout=10.0)
            c_auth.write(f'bus/{self.bus_id}/add-authorized-xboxone {json.dumps(create_req)}\0'.encode('utf-8'))
            created_raw = c_auth.read_record()
            c_auth.close()
            created = json.loads(created_raw.decode('utf-8').strip('\0\r\n'))
            dev_id = created.get('devId')
            removal_token = created.get('removalToken')
            if not dev_id or not removal_token:
                print(f'[!] Error creando persona autorizada Xbox One: {created}')
                return False

            act_req = {'version': 1, 'removalToken': removal_token}

            # 2. Conectar stream de broker persistente (debe preceder a la activación)
            c_stream = connect_secure_viiper(self.host, self.port, key, timeout=10.0)
            c_stream.write(f'bus/{self.bus_id}/{dev_id}/stream-authorized-xboxone {json.dumps(act_req)}\0'.encode('utf-8'))

            # ConsumerReady frame: magic X1BR, ver 1, type 0x01
            ready_frame = b'X1BR\x01\x01' + struct.pack('<HQ', 0, 0)
            c_stream.write(ready_frame)
            ready_ack = c_stream.read_record()
            if not ready_ack.startswith(b'X1BR\x01\x81'):
                c_stream.close()
                print(f'[!] Error en ConsumerReadyAck de Xbox One: {ready_ack[:6]}')
                return False

            # 3. Activar el attach del dispositivo retenido (operación de driver PnP de Windows)
            c_act = connect_secure_viiper(self.host, self.port, key, timeout=25.0)
            c_act.write(f'bus/{self.bus_id}/{dev_id}/activate-authorized-xboxone {json.dumps(act_req)}\0'.encode('utf-8'))
            act_res_raw = c_act.read_record()
            c_act.close()
            activated = json.loads(act_res_raw.decode('utf-8').strip('\0\r\n'))

            # 4. Enviar estado neutral inicial (correlación 2)
            neutral_wire = bytearray(24)
            struct.pack_into('<HH', neutral_wire, 0, 1, 24)
            neutral_frame = b'X1BR\x01\x02' + struct.pack('<HQ', 24, 2) + bytes(neutral_wire)
            c_stream.write(neutral_frame)
            try:
                c_stream.sock.settimeout(2.0)
                _ = c_stream.read_record()
            except Exception:
                pass
            c_stream.sock.settimeout(None)

            stop_evt = threading.Event()
            def feedback_worker():
                while not stop_evt.is_set():
                    try:
                        c_stream.sock.settimeout(0.5)
                        record = c_stream.read_record()
                        if not record or len(record) < 16:
                            continue
                        if record[:4] == b'X1BR':
                            ftype = record[5]
                            length, corr = struct.unpack('<HQ', record[6:16])
                            if ftype == 0x83: # xboxOneCanonicalFeedback
                                ack_frame = b'X1BR\x01\x03' + struct.pack('<HQ', 1, corr) + b'\x01'
                                c_stream.write(ack_frame)
                    except (socket.timeout, TimeoutError):
                        continue
                    except Exception:
                        break

            t = threading.Thread(target=feedback_worker, daemon=True, name=f"viiper-gip-feedback-{slot}")
            t.start()

            self.devices[slot] = {
                'devId': dev_id,
                'type': 'xboxone',
                'secure_conn': c_stream,
                'removal_token': removal_token,
                'correlation': 3,
                'last_pkt': None,
                'last_send_time': 0.0,
                'stop_event': stop_evt,
                'thread': t,
            }
            return True
        except Exception as e:
            print(f'[!] Excepción configurando mando virtual Xbox One: {e}')
            return False

    def _send_stream_pkt(self, slot: int, pkt: bytes):
        dev = self.devices.get(slot)
        if not dev:
            return
        now = time.time()
        if dev.get('last_pkt') == pkt and (now - dev.get('last_send_time', 0.0)) < 1.0:
            return
        dev['last_pkt'] = pkt
        dev['last_send_time'] = now

        sock = dev.get('socket')
        if sock:
            try:
                sock.sendall(pkt)
            except Exception:
                pass

    def send_xbox360_state(self, slot: int, buttons: int, lt: int, rt: int, lx: int, ly: int, rx: int, ry: int):
        # VIIPER Xbox 360: 20 bytes (<IBBhhhh6s)
        pkt = struct.pack('<IBBhhhh6s', buttons, lt, rt, lx, ly, rx, ry, b'\x00' * 6)
        self._send_stream_pkt(slot, pkt)

    def send_xboxone_state(self, slot: int, buttons: int, lt: int, rt: int, lx: int, ly: int, rx: int, ry: int):
        """Envía estado semántico a un mando virtual Xbox One conectado en el slot."""
        dev = self.devices.get(slot)
        if not dev or not dev.get('secure_conn'):
            return

        # Escalamiento: gatillos 0..1023 (10 bits), sticks -32768..32767
        lt_val = max(0, min(1023, int(lt * 4)))
        rt_val = max(0, min(1023, int(rt * 4)))
        lx_val = max(-32768, min(32767, int(lx)))
        ly_val = max(-32768, min(32767, int(ly)))
        rx_val = max(-32768, min(32767, int(rx)))
        ry_val = max(-32768, min(32767, int(ry)))

        # Estructura semántica InputStateV1 (24 bytes)
        wire = bytearray(24)
        struct.pack_into('<HH', wire, 0, 1, 24)
        struct.pack_into('<I', wire, 4, buttons)
        struct.pack_into('<HH', wire, 8, lt_val, rt_val)
        struct.pack_into('<hhhh', wire, 12, lx_val, ly_val, rx_val, ry_val)

        now = time.time()
        if dev.get('last_pkt') == bytes(wire) and (now - dev.get('last_send_time', 0.0)) < 1.0:
            return
        dev['last_pkt'] = bytes(wire)
        dev['last_send_time'] = now

        corr = dev.get('correlation', 3)
        dev['correlation'] = (corr + 1) if corr < 0xFFFFFFFFFFFFFFF0 else 3

        # Trama del broker X1BR: tipo 0x02 (SemanticInput)
        frame = b'X1BR\x01\x02' + struct.pack('<HQ', 24, corr) + bytes(wire)
        try:
            dev['secure_conn'].write(frame)
        except Exception:
            pass

    def send_ds4_state(self, slot: int, buttons: int, dpad: int, l2: int, r2: int, lx: int, ly: int, rx: int, ry: int):
        # VIIPER DS4: 31 bytes (<bbbbHBBB22s)
        imu_touch = bytearray(22)
        struct.pack_into('<h', imu_touch, 16, -5023)
        pkt = struct.pack('<bbbbHBBB22s', lx, ly, rx, ry, buttons, dpad, l2, r2, bytes(imu_touch))
        self._send_stream_pkt(slot, pkt)

    def send_dualsense_state(self, slot: int, buttons: int, dpad: int, l2: int, r2: int, lx: int, ly: int, rx: int, ry: int):
        # VIIPER DualSense: 33 bytes (<bbbbIBBB22s)
        imu_touch = bytearray(22)
        struct.pack_into('<h', imu_touch, 16, -5023)
        pkt = struct.pack('<bbbbIBBB22s', lx, ly, rx, ry, buttons, dpad, l2, r2, bytes(imu_touch))
        self._send_stream_pkt(slot, pkt)

    def send_ns2pro_state(self, slot: int, buttons: int, lx: int, ly: int, rx: int, ry: int):
        # VIIPER Switch 2 Pro: 24 bytes (<IHHHHhhhhhh)
        pkt = struct.pack('<IHHHHhhhhhh', buttons, lx, ly, rx, ry, 0, 0, -4096, 0, 0, 0)
        self._send_stream_pkt(slot, pkt)

    def remove_device(self, slot: int) -> bool:
        dev = self.devices.pop(slot, None)
        if not dev:
            return False
        stop_evt = dev.get('stop_event')
        if stop_evt:
            stop_evt.set()
        dev_id = dev.get('devId')
        rem_tok = dev.get('removal_token')
        key = get_viiper_key()
        if self.bus_id and dev_id and rem_tok and key:
            try:
                c_rem = connect_secure_viiper(self.host, self.port, key, timeout=3.0)
                c_rem.write(f'bus/{self.bus_id}/{dev_id}/remove-authorized-xboxone {json.dumps({"version": 1, "removalToken": rem_tok})}\0'.encode('utf-8'))
                c_rem.close()
            except Exception:
                pass
        elif self.bus_id and dev_id:
            try:
                self._send_cmd(f'bus/{self.bus_id}/remove {dev_id}')
            except Exception:
                pass
        conn = dev.get('secure_conn')
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        sock = dev.get('socket')
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        return True

    def stop(self):
        self.running = False
        key = get_viiper_key()
        # Cerrar y retirar todos los dispositivos
        for slot in list(self.devices.keys()):
            self.remove_device(slot)

        # Eliminar bus si está activo
        if self.bus_id is not None:
            try:
                self._send_cmd(f'bus/remove {self.bus_id}')
            except Exception:
                pass
            self.bus_id = None

        # Apagado limpio del servidor VIIPER con server/shutdown
        if self.server_proc and self.server_proc.poll() is None:
            try:
                self._send_cmd('server/shutdown')
                self.server_proc.wait(timeout=3.5)
            except Exception:
                try:
                    self.server_proc.terminate()
                    self.server_proc.wait(timeout=1.5)
                except Exception:
                    try:
                        self.server_proc.kill()
                    except Exception:
                        pass
            self.server_proc = None
