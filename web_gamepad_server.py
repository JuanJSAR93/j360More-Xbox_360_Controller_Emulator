"""
web_gamepad_server.py
Servidor HTTP y WebSocket multicliente embebido (puro Python) para j360More.
Permite conectar hasta 12 smartphones (iOS / Android) por Wi-Fi como mandos virtuales AirPad.
Zero-Install: Los jugadores solo necesitan escanear el código QR en el navegador de su teléfono.
Incluye parser incremental RFC 6455 con buffer por cliente, protocolo binario v1,
cola FIFO para botones fiables, snapshots analógicos atómicos y selector multi-IP.
"""

import os
import sys
import time
import json
import base64
import hashlib
import struct
import socket
import select
import threading
from typing import Dict, List, Any, Optional, Callable

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_AIRPAD_CLIENTS = 12

BUTTON_BITS = {
    "A": 1 << 0,
    "B": 1 << 1,
    "X": 1 << 2,
    "Y": 1 << 3,
    "LB": 1 << 4,
    "RB": 1 << 5,
    "BACK": 1 << 6,
    "START": 1 << 7,
    "GUIDE": 1 << 8,
    "LS": 1 << 9,
    "RS": 1 << 10,
    "UP": 1 << 11,
    "DOWN": 1 << 12,
    "LEFT": 1 << 13,
    "RIGHT": 1 << 14,
}
BIT_TO_BUTTON = {bit: name for name, bit in BUTTON_BITS.items()}

# Protocolo Binario Versión 1 (Little-endian):
# uint8(ver=1) + uint8(type=1) + uint32(seq) + uint16(buttons) + uint8(lt) + uint8(rt) + int16(lx) + int16(ly) + int16(rx) + int16(ry) + uint32(client_time_ms)
STRUCT_BIN_V1_22 = struct.Struct("<BBIHBBhhhhI")  # 22 bytes con client_time_ms
STRUCT_BIN_V1_18 = struct.Struct("<BBIHBBhhhh")   # 18 bytes sin client_time_ms


def get_all_local_ips() -> List[Dict[str, str]]:
    """
    Obtiene todas las direcciones IPv4 locales disponibles de los adaptadores de red.
    Retorna lista de dicts: [{'ip': '192.168.1.14', 'label': '192.168.1.14 (Wi-Fi/LAN)'}, ...]
    """
    ips = []
    seen = set()

    # 1. Ruta primaria saliente
    primary_ip = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        primary_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    if primary_ip and not primary_ip.startswith("127."):
        seen.add(primary_ip)
        ips.append({"ip": primary_ip, "label": f"{primary_ip} (Recomendada / LAN activa)"})

    # 2. Todas las IPs asociadas al hostname
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip not in seen and not ip.startswith("127."):
                seen.add(ip)
                ips.append({"ip": ip, "label": f"{ip} (Adaptador de red)"})
    except Exception:
        pass

    if not ips:
        ips.append({"ip": "127.0.0.1", "label": "127.0.0.1 (Localhost)"})

    return ips


def get_local_ip(preferred_ip: Optional[str] = None) -> str:
    """Obtiene la direccion IP a exponer para el servidor AirPad."""
    if preferred_ip and preferred_ip.strip() not in ("", "0.0.0.0", "Auto", "Todas"):
        return preferred_ip.strip()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


class TelemetryCollector:
    """Recolecta métricas de latencia, jitter, frames y tasa de transferencia."""

    def __init__(self, max_samples: int = 1000):
        self.enabled = False
        self.max_samples = max_samples
        self.lock = threading.Lock()
        self.transit_times_ms: List[float] = []
        self.server_to_engine_us: List[float] = []
        self.engine_to_backend_us: List[float] = []
        self.total_pipeline_us: List[float] = []
        self.last_client_ms: Optional[float] = None
        self.jitter_ms: List[float] = []
        self.frames_received = 0
        self.frames_binary = 0
        self.frames_json = 0
        self.bytes_received = 0
        self.invalid_frames = 0
        self.start_time = time.time()

    def record_packet(self, is_binary: bool, byte_len: int, client_ms: int = 0, server_recv_ns: int = 0):
        if not self.enabled:
            return
        with self.lock:
            self.frames_received += 1
            if is_binary:
                self.frames_binary += 1
            else:
                self.frames_json += 1
            self.bytes_received += byte_len
            if client_ms > 0:
                if self.last_client_ms is not None:
                    diff = abs(client_ms - self.last_client_ms)
                    self.jitter_ms.append(diff)
                    if len(self.jitter_ms) > self.max_samples:
                        self.jitter_ms.pop(0)
                self.last_client_ms = client_ms

    def record_engine_stage(self, server_recv_ns: int, engine_ns: int, backend_ns: int):
        if not self.enabled or server_recv_ns <= 0:
            return
        with self.lock:
            s2e = (engine_ns - server_recv_ns) / 1000.0
            e2b = (backend_ns - engine_ns) / 1000.0
            total = (backend_ns - server_recv_ns) / 1000.0
            self.server_to_engine_us.append(s2e)
            self.engine_to_backend_us.append(e2b)
            self.total_pipeline_us.append(total)
            if len(self.total_pipeline_us) > self.max_samples:
                self.total_pipeline_us.pop(0)
                self.server_to_engine_us.pop(0)
                self.engine_to_backend_us.pop(0)

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            def percentile(vals, p):
                if not vals:
                    return 0.0
                s = sorted(vals)
                k = (len(s) - 1) * (p / 100.0)
                f = int(k)
                c = min(f + 1, len(s) - 1)
                return s[f] + (s[c] - s[f]) * (k - f)

            elapsed = max(0.1, time.time() - self.start_time)
            return {
                "enabled": self.enabled,
                "frames_total": self.frames_received,
                "frames_binary": self.frames_binary,
                "frames_json": self.frames_json,
                "fps": round(self.frames_received / elapsed, 1),
                "kbps": round((self.bytes_received / elapsed) / 1024.0, 2),
                "jitter_p50_ms": round(percentile(self.jitter_ms, 50), 2),
                "jitter_p95_ms": round(percentile(self.jitter_ms, 95), 2),
                "pipeline_p50_us": round(percentile(self.total_pipeline_us, 50), 1),
                "pipeline_p95_us": round(percentile(self.total_pipeline_us, 95), 1),
                "pipeline_p99_us": round(percentile(self.total_pipeline_us, 99), 1),
                "pipeline_max_us": round(max(self.total_pipeline_us) if self.total_pipeline_us else 0.0, 1),
            }


class AirPadClient:
    """Representa una sesion de smartphone conectada por WebSocket."""

    def __init__(self, slot_id: str, slot_num: int, sock: socket.socket, addr: tuple):
        self.slot_id = slot_id         # ej: 'phone_1'
        self.slot_num = slot_num       # ej: 1
        self.sock = sock
        self.addr = addr
        self.ip = addr[0]
        self.name = f"Teléfono {slot_num}"
        self.device_model = "Móvil Web"
        self.connected_at = time.time()
        self.last_activity = time.time()
        self.ping_ms = 0
        self.active = True
        self.binary_negotiated = False

        # Parser incremental TCP/WebSocket
        self.rx_buffer = bytearray()

        # Concurrencia de estado
        self.state_lock = threading.Lock()

        # Cola FIFO para transiciones fiables de botones (down/up)
        self.button_queue: List[Dict[str, Any]] = []
        self.current_buttons_mask = 0

        # Estado normalizado de botones activos
        self.buttons = {
            "A": False, "B": False, "X": False, "Y": False,
            "LB": False, "RB": False, "BACK": False, "START": False,
            "GUIDE": False, "LS": False, "RS": False,
            "UP": False, "DOWN": False, "LEFT": False, "RIGHT": False
        }

        # Snapshot atómico de ejes [-1.0, 1.0] y gatillos [0.0, 1.0]
        self.axes = {
            "lx": 0.0, "ly": 0.0,
            "rx": 0.0, "ry": 0.0,
            "lt": 0.0, "rt": 0.0
        }

        # Telemetría y marcas de tiempo
        self.latest_seq = 0
        self.t_client_ms = 0
        self.t_server_recv_ns = 0

    def enqueue_button(self, btn_name: str, state: int, seq: int = 0, client_ms: int = 0, recv_ns: int = 0):
        self.last_activity = time.time()
        self.t_client_ms = client_ms
        self.t_server_recv_ns = recv_ns
        self.latest_seq = seq

        key = btn_name.upper()
        name_map = {
            "DPADUP": "UP", "DPADDOWN": "DOWN", "DPADLEFT": "LEFT", "DPADRIGHT": "RIGHT",
            "SELECT": "BACK", "L1": "LB", "R1": "RB", "L3": "LS", "R3": "RS",
            "HOME": "GUIDE"
        }
        key = name_map.get(key, key)
        with self.state_lock:
            self.button_queue.append({
                "btn": key,
                "state": state,
                "seq": seq
            })
            if len(self.button_queue) > 64:
                self.button_queue.pop(0)

            if key in self.buttons:
                self.buttons[key] = (state == 1)

    def update_trigger(self, side: str, value: float, recv_ns: int = 0):
        self.last_activity = time.time()
        self.t_server_recv_ns = recv_ns
        s = side.lower()
        val = max(0.0, min(1.0, float(value)))
        with self.state_lock:
            if s in ("l", "lt", "l2"):
                self.axes["lt"] = val
            elif s in ("r", "rt", "r2"):
                self.axes["rt"] = val

    def update_joystick(self, stick: str, x: float, y: float, recv_ns: int = 0):
        self.last_activity = time.time()
        self.t_server_recv_ns = recv_ns
        s = stick.lower()
        vx = max(-1.0, min(1.0, float(x)))
        vy = max(-1.0, min(1.0, float(y)))
        with self.state_lock:
            if s in ("l", "left"):
                self.axes["lx"] = vx
                self.axes["ly"] = vy
            elif s in ("r", "right"):
                self.axes["rx"] = vx
                self.axes["ry"] = vy

    def update_binary_state(self, seq: int, buttons_mask: int, lt_u8: int, rt_u8: int,
                            lx_i16: int, ly_i16: int, rx_i16: int, ry_i16: int,
                            client_time_ms: int = 0, recv_ns: int = 0):
        self.last_activity = time.time()
        self.t_client_ms = client_time_ms
        self.t_server_recv_ns = recv_ns
        self.latest_seq = seq

        with self.state_lock:
            # 1. Detectar transiciones de botones respecto al estado anterior
            prev_mask = self.current_buttons_mask
            if buttons_mask != prev_mask:
                self.current_buttons_mask = buttons_mask
                for btn_name, bit in BUTTON_BITS.items():
                    was_pressed = bool(prev_mask & bit)
                    is_pressed = bool(buttons_mask & bit)
                    if was_pressed != is_pressed:
                        self.button_queue.append({
                            "btn": btn_name,
                            "state": 1 if is_pressed else 0,
                            "seq": seq
                        })
                        if len(self.button_queue) > 64:
                            self.button_queue.pop(0)
                        self.buttons[btn_name] = is_pressed

            # 2. Snapshot analógico atómico (reemplazable instantáneamente por el más reciente)
            self.axes["lt"] = lt_u8 / 255.0
            self.axes["rt"] = rt_u8 / 255.0
            self.axes["lx"] = max(-1.0, min(1.0, lx_i16 / 32767.0))
            self.axes["ly"] = max(-1.0, min(1.0, ly_i16 / 32767.0))
            self.axes["rx"] = max(-1.0, min(1.0, rx_i16 / 32767.0))
            self.axes["ry"] = max(-1.0, min(1.0, ry_i16 / 32767.0))

    def reset_inputs(self):
        """Libera todos los botones y centra ejes de forma segura."""
        with self.state_lock:
            self.button_queue.clear()
            self.current_buttons_mask = 0
            for k in self.buttons:
                self.buttons[k] = False
            for k in self.axes:
                self.axes[k] = 0.0

    def get_physical_state(self) -> Dict[str, Any]:
        """Convierte el estado de AirPad al diccionario compatible con EmulatorEngine."""
        with self.state_lock:
            # Drenar cola de botones
            while self.button_queue:
                ev = self.button_queue.pop(0)
                b_name = ev["btn"]
                if b_name in self.buttons:
                    self.buttons[b_name] = (ev["state"] == 1)

            b = dict(self.buttons)
            a = dict(self.axes)
            seq = self.latest_seq
            c_ms = self.t_client_ms
            r_ns = self.t_server_recv_ns

        return {
            "buttons": {
                0: b["A"],
                1: b["B"],
                2: b["X"],
                3: b["Y"],
                4: b["LB"],
                5: b["RB"],
                6: b["BACK"],
                7: b["START"],
                8: b["LS"],
                9: b["RS"],
                10: b["GUIDE"],
            },
            "axes": {
                0: a["lx"],
                1: a["ly"],
                2: (a["lt"] * 2.0 - 1.0),  # Escala DirectInput [-1.0, 1.0]
                3: a["rx"],
                4: a["ry"],
                5: (a["rt"] * 2.0 - 1.0)
            },
            "hats": {
                0: (
                    (1 if b["RIGHT"] else (-1 if b["LEFT"] else 0)),
                    (1 if b["UP"] else (-1 if b["DOWN"] else 0))
                )
            },
            "keys": set(),
            "raw_phone": {
                "buttons": dict(b),
                "axes": dict(a)
            },
            "telemetry": {
                "seq": seq,
                "t_client_ms": c_ms,
                "t_server_recv_ns": r_ns
            }
        }


class WebGamepadServer:
    """
    Servidor HTTP & WebSocket ultra ligero para j360More AirPad.
    Gestiona hasta 12 ranuras de smartphones simultaneos con protocolo binario.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080, static_dir: Optional[str] = None):
        self.host = host
        self.port = port
        self.preferred_ip: Optional[str] = None
        self.static_dir = static_dir
        if not self.static_dir:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.static_dir = os.path.join(base_dir, "assets", "web_pad")

        self.running = False
        self.server_sock: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.RLock()

        # Slots 1..12
        self.clients: Dict[str, AirPadClient] = {}

        # Opciones
        self.max_slots: int = 8
        self.haptics_enabled = True
        self.auto_assign_enabled = True

        # Telemetría
        self.telemetry = TelemetryCollector()

        # Callbacks y eventos reactivos
        self.on_client_connected_cb: Optional[Callable[[str, AirPadClient], None]] = None
        self.on_client_disconnected_cb: Optional[Callable[[str], None]] = None
        self.on_input_event: Optional[Callable[[], None]] = None

    def start(self) -> bool:
        """Inicia el servidor en un hilo secundario."""
        if self.running:
            return True

        try:
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind((self.host, self.port))
            self.server_sock.listen(16)
            self.server_sock.settimeout(0.5)

            self.running = True
            self.thread = threading.Thread(target=self._run_loop, daemon=True, name="AirPadServer")
            self.thread.start()
            print(f"[*] Servidor AirPad iniciado en http://{get_local_ip(self.preferred_ip)}:{self.port}")
            return True
        except Exception as e:
            print(f"[!] Error iniciando Servidor AirPad en puerto {self.port}: {e}")
            self.running = False
            if self.server_sock:
                try:
                    self.server_sock.close()
                except Exception:
                    pass
                self.server_sock = None
            return False

    def stop(self):
        """Detiene el servidor y desconecta a todos los clientes de forma limpia e instantánea."""
        self.running = False
        with self.lock:
            clients_to_close = list(self.clients.items())
            self.clients.clear()

        # Finalizar clientes fuera del lock para evitar cualquier contención o llamada recursiva
        for slot_id, client in clients_to_close:
            self._finish_client_disconnect(slot_id, client, notify_callbacks=False)

        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
            self.server_sock = None

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)
            self.thread = None

    def get_url(self) -> str:
        """Retorna la URL local para el QR y el portapapeles."""
        return f"http://{get_local_ip(self.preferred_ip)}:{self.port}"

    def get_connected_count(self) -> int:
        with self.lock:
            return len(self.clients)

    def get_clients_info(self, limit_count: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retorna informacion resumida de todos los clientes conectados hasta el limite de mandos."""
        with self.lock:
            res = []
            max_limit = limit_count if limit_count is not None else self.max_slots
            max_limit = min(MAX_AIRPAD_CLIENTS, max(1, int(max_limit)))
            for i in range(1, max_limit + 1):
                slot_id = f"phone_{i}"
                client = self.clients.get(slot_id)
                if client and client.active:
                    res.append({
                        "slot_id": slot_id,
                        "slot_num": i,
                        "ip": client.ip,
                        "name": client.name,
                        "model": client.device_model,
                        "ping": client.ping_ms,
                        "connected": True
                    })
                else:
                    res.append({
                        "slot_id": slot_id,
                        "slot_num": i,
                        "ip": "",
                        "name": f"Ranura {i}",
                        "model": "",
                        "ping": 0,
                        "connected": False
                    })
            return res

    def get_client(self, slot_id: str) -> Optional[AirPadClient]:
        with self.lock:
            return self.clients.get(slot_id)

    def get_physical_state(self, slot_id: str) -> Dict[str, Any]:
        """Obtiene el estado de entrada del cliente para el bucle de emulacion."""
        with self.lock:
            client = self.clients.get(slot_id)
            if client and client.active:
                return client.get_physical_state()

        return {
            "buttons": {i: False for i in range(12)},
            "axes": {i: 0.0 for i in range(6)},
            "hats": {0: (0, 0)},
            "keys": set(),
            "raw_phone": {"buttons": {}, "axes": {}},
            "telemetry": {"seq": 0, "t_client_ms": 0, "t_server_recv_ns": 0}
        }

    def send_rumble(self, slot_id: str, low: int, high: int):
        """Envia vibracion al smartphone si los hapticos estan habilitados."""
        if not self.haptics_enabled:
            return
        with self.lock:
            client = self.clients.get(slot_id)
            if client and client.active:
                msg = json.dumps({"type": "rumble", "low": low, "high": high})
                self._send_ws_frame(client.sock, msg)

    def notify_input(self):
        """Despierta inmediatamente al motor de emulacion."""
        if self.on_input_event:
            try:
                self.on_input_event()
            except Exception:
                pass

    def _find_free_slot(self) -> Optional[int]:
        """Encuentra el menor slot libre entre 1 y self.max_slots (maximo 12)."""
        limit = min(MAX_AIRPAD_CLIENTS, max(1, self.max_slots))
        for i in range(1, limit + 1):
            if f"phone_{i}" not in self.clients:
                return i
        return None

    def _run_loop(self):
        """Bucle principal de recepcion de conexiones y peticiones."""
        while self.running and self.server_sock:
            try:
                with self.lock:
                    sockets = [self.server_sock]
                    client_map = {}
                    for slot_id, client in list(self.clients.items()):
                        if client.active and client.sock:
                            sockets.append(client.sock)
                            client_map[client.sock] = slot_id

                rlist, _, xlist = select.select(sockets, [], sockets, 0.2)

                for s in rlist:
                    if s is self.server_sock:
                        try:
                            conn, addr = self.server_sock.accept()
                            conn.setblocking(True)
                            threading.Thread(target=self._handle_initial_connection, args=(conn, addr), daemon=True).start()
                        except Exception:
                            pass
                    else:
                        slot_id = client_map.get(s)
                        if slot_id:
                            self._handle_ws_data(slot_id, s)

                for s in xlist:
                    slot_id = client_map.get(s)
                    if slot_id:
                        self._disconnect_client(slot_id)

            except Exception:
                if not self.running:
                    break

    def _handle_initial_connection(self, conn: socket.socket, addr: tuple):
        """Procesa la peticion HTTP inicial (servir estaticos o upgrade a WebSocket)."""
        try:
            conn.settimeout(3.0)
            data = conn.recv(4096).decode("utf-8", errors="ignore")
            if not data:
                conn.close()
                return

            lines = data.split("\r\n")
            if not lines or len(lines[0].split()) < 2:
                conn.close()
                return

            method, path = lines[0].split()[:2]

            headers = {}
            for line in lines[1:]:
                if ": " in line:
                    k, v = line.split(": ", 1)
                    headers[k.lower()] = v.strip()

            # Comprobar si es solicitud de WebSocket
            if headers.get("upgrade", "").lower() == "websocket":
                key = headers.get("sec-websocket-key")
                if key:
                    self._upgrade_websocket(conn, addr, key, headers)
                else:
                    conn.close()
            elif method == "GET":
                self._serve_http_file(conn, path)
            else:
                conn.sendall(b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n")
                conn.close()

        except Exception:
            try:
                conn.close()
            except Exception:
                pass

    def _serve_http_file(self, conn: socket.socket, path: str):
        """Sirve archivos estaticos del cliente web (assets/web_pad/)."""
        try:
            clean_path = path.split("?")[0].lstrip("/")
            if not clean_path:
                clean_path = "index.html"

            full_path = os.path.normpath(os.path.join(self.static_dir, clean_path))

            # Evitar Path Traversal
            if not full_path.startswith(os.path.abspath(self.static_dir)):
                conn.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
                conn.close()
                return

            if not os.path.isfile(full_path):
                conn.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 9\r\n\r\nNot Found")
                conn.close()
                return

            # Determinar tipo MIME
            content_types = {
                ".html": "text/html; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".json": "application/json",
                ".png": "image/png",
                ".svg": "image/svg+xml",
                ".ico": "image/x-icon",
                ".webmanifest": "application/manifest+json"
            }
            ext = os.path.splitext(full_path)[1].lower()
            mime = content_types.get(ext, "application/octet-stream")

            with open(full_path, "rb") as f:
                body = f.read()

            response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: {mime}\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Access-Control-Allow-Origin: *\r\n"
                f"Cache-Control: no-cache\r\n"
                f"Connection: close\r\n\r\n"
            ).encode("utf-8") + body

            conn.sendall(response)
            conn.close()
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

    def _upgrade_websocket(self, conn: socket.socket, addr: tuple, key: str, headers: dict):
        """Completa el handshake RFC 6455 y asigna una ranura de cliente."""
        slot_num = None
        with self.lock:
            slot_num = self._find_free_slot()

        if slot_num is None:
            conn.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 17\r\n\r\nServer Full (12)")
            conn.close()
            return

        slot_id = f"phone_{slot_num}"

        # Calcular Sec-WebSocket-Accept
        accept_raw = hashlib.sha1((key + WS_GUID).encode("utf-8")).digest()
        accept_str = base64.b64encode(accept_raw).decode("utf-8")

        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_str}\r\n\r\n"
        ).encode("utf-8")

        conn.sendall(response)

        # Configurar TCP_NODELAY para mínima latencia
        try:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        conn.setblocking(False)

        client = AirPadClient(slot_id, slot_num, conn, addr)

        # Detectar modelo basico por User-Agent si esta disponible
        ua = headers.get("user-agent", "")
        if "iPhone" in ua:
            client.device_model = "iPhone"
        elif "iPad" in ua:
            client.device_model = "iPad"
        elif "Android" in ua:
            client.device_model = "Android"
        elif "Windows" in ua:
            client.device_model = "PC Browser"

        with self.lock:
            self.clients[slot_id] = client

        print(f"[+] AirPad conectado: {slot_id} desde {addr[0]} ({client.device_model})")

        # Enviar mensaje de bienvenida con el slot, hapticos y soporte binario anunciado
        welcome = {
            "type": "welcome",
            "slot": slot_num,
            "slot_id": slot_id,
            "haptics": self.haptics_enabled,
            "name": client.name,
            "binary": True,
            "protocol": "bin_v1"
        }
        self._send_ws_frame(conn, json.dumps(welcome))

        if self.on_client_connected_cb:
            try:
                self.on_client_connected_cb(slot_id, client)
            except Exception as e:
                print(f"[!] Error en callback on_client_connected: {e}")

    def _handle_ws_data(self, slot_id: str, sock: socket.socket):
        """Parser incremental RFC 6455 con buffer por cliente y drenado de todas las tramas."""
        client = self.clients.get(slot_id)
        if not client or not client.active:
            return

        # 1. Leer socket no bloqueante hasta BlockingIOError o EOF
        try:
            while True:
                chunk = sock.recv(8192)
                if not chunk:
                    self._disconnect_client(slot_id)
                    return
                client.rx_buffer.extend(chunk)
                if len(client.rx_buffer) > 262144:  # Protección contra desbordamiento
                    self._disconnect_client(slot_id)
                    return
        except (BlockingIOError, socket.timeout):
            pass
        except Exception:
            self._disconnect_client(slot_id)
            return

        # 2. Drenar tramas completas presentes en rx_buffer
        recv_ns = time.perf_counter_ns()
        buf = client.rx_buffer

        while True:
            if len(buf) < 2:
                break

            b0 = buf[0]
            b1 = buf[1]
            fin = bool(b0 & 0x80)
            opcode = b0 & 0x0F
            masked = bool(b1 & 0x80)
            raw_len = b1 & 0x7F

            header_len = 2
            if raw_len == 126:
                if len(buf) < 4:
                    break
                payload_len = struct.unpack_from("!H", buf, 2)[0]
                header_len += 2
            elif raw_len == 127:
                if len(buf) < 10:
                    break
                payload_len = struct.unpack_from("!Q", buf, 2)[0]
                header_len += 8
            else:
                payload_len = raw_len

            if masked:
                if len(buf) < header_len + 4:
                    break
                mask = buf[header_len:header_len+4]
                header_len += 4
            else:
                mask = None

            total_frame_len = header_len + payload_len
            if len(buf) < total_frame_len:
                break

            # Extraer payload y desenmascarar
            raw_payload = buf[header_len:total_frame_len]
            del buf[:total_frame_len]

            if mask:
                unmasked = bytearray(payload_len)
                for i in range(payload_len):
                    unmasked[i] = raw_payload[i] ^ mask[i % 4]
                payload = bytes(unmasked)
            else:
                payload = bytes(raw_payload)

            # Procesar según opcode RFC 6455
            if opcode == 0x8:  # Close
                self._disconnect_client(slot_id)
                return
            elif opcode == 0x9:  # Ping -> Responder Pong
                pong_header = bytearray([0x8A, len(payload)])
                sock.sendall(pong_header + payload)
            elif opcode == 0xA:  # Pong
                client.ping_ms = int(time.time() * 1000)
            elif opcode == 0x2:  # Binary frame
                self._process_binary_message(slot_id, client, payload, recv_ns)
            elif opcode == 0x1:  # Text frame (JSON)
                try:
                    payload_str = payload.decode("utf-8", errors="ignore")
                    self._process_json_message(slot_id, client, payload_str, recv_ns, len(payload))
                except Exception:
                    pass

    def _process_binary_message(self, slot_id: str, client: AirPadClient, payload: bytes, recv_ns: int):
        """Decodifica un estado completo de gamepad empaquetado en binario v1."""
        p_len = len(payload)
        if p_len < 18:
            return

        try:
            if p_len >= 22:
                ver, p_type, seq, buttons_mask, lt_u8, rt_u8, lx_i16, ly_i16, rx_i16, ry_i16, client_time_ms = STRUCT_BIN_V1_22.unpack_from(payload, 0)
            else:
                ver, p_type, seq, buttons_mask, lt_u8, rt_u8, lx_i16, ly_i16, rx_i16, ry_i16 = STRUCT_BIN_V1_18.unpack_from(payload, 0)
                client_time_ms = 0

            if ver != 1 or p_type != 1:
                return

            client.update_binary_state(
                seq=seq,
                buttons_mask=buttons_mask,
                lt_u8=lt_u8,
                rt_u8=rt_u8,
                lx_i16=lx_i16,
                ly_i16=ly_i16,
                rx_i16=rx_i16,
                ry_i16=ry_i16,
                client_time_ms=client_time_ms,
                recv_ns=recv_ns
            )

            self.telemetry.record_packet(is_binary=True, byte_len=p_len, client_ms=client_time_ms, server_recv_ns=recv_ns)
            self.notify_input()
        except Exception:
            pass

    def _process_json_message(self, slot_id: str, client: AirPadClient, raw_json: str, recv_ns: int, byte_len: int):
        """Parsea el mensaje JSON recibido del smartphone (compatibilidad retroactiva)."""
        try:
            msg = json.loads(raw_json)
            m_type = msg.get("type", "")

            if m_type == "btn":
                btn = msg.get("button") or msg.get("btn", "")
                state = int(msg.get("state", 0))
                seq = int(msg.get("seq", 0))
                t_c = int(msg.get("t", 0))
                client.enqueue_button(btn, state, seq, t_c, recv_ns)
                self.telemetry.record_packet(is_binary=False, byte_len=byte_len, client_ms=t_c, server_recv_ns=recv_ns)
                self.notify_input()

            elif m_type == "trigger":
                side = msg.get("side", "")
                val = float(msg.get("value", 0.0))
                client.update_trigger(side, val, recv_ns)
                self.telemetry.record_packet(is_binary=False, byte_len=byte_len, server_recv_ns=recv_ns)
                self.notify_input()

            elif m_type == "joystick":
                stick = msg.get("stick", "")
                x = float(msg.get("x", 0.0))
                y = float(msg.get("y", 0.0))
                client.update_joystick(stick, x, y, recv_ns)
                self.telemetry.record_packet(is_binary=False, byte_len=byte_len, server_recv_ns=recv_ns)
                self.notify_input()

            elif m_type == "info":
                name = msg.get("name")
                model = msg.get("model")
                proto = msg.get("protocol", "")
                if proto == "bin_v1":
                    client.binary_negotiated = True
                if name:
                    client.name = str(name)[:25]
                if model:
                    client.device_model = str(model)[:30]

            elif m_type == "ping":
                t = msg.get("t", 0)
                client.ping_ms = int((time.time() * 1000) - t) if t else 0
                pong = json.dumps({"type": "pong", "t": t})
                self._send_ws_frame(client.sock, pong)

        except Exception:
            pass

    def _send_ws_frame(self, sock: socket.socket, message: str):
        """Envia una trama de texto WebSocket no enmascarada (servidor -> cliente)."""
        try:
            data = message.encode("utf-8")
            length = len(data)
            header = bytearray([0x81])  # FIN + Text Opcode

            if length <= 125:
                header.append(length)
            elif length <= 65535:
                header.append(126)
                header.extend(struct.pack("!H", length))
            else:
                header.append(127)
                header.extend(struct.pack("!Q", length))

            sock.sendall(header + data)
        except Exception:
            pass

    def _finish_client_disconnect(self, slot_id: str, client: AirPadClient, notify_callbacks: bool = True):
        """Finaliza el cierre de socket y notificaciones de desconexión sin retener el lock del servidor."""
        client.active = False
        client.reset_inputs()
        self.notify_input()
        try:
            client.sock.close()
        except Exception:
            pass
        print(f"[-] AirPad desconectado: {slot_id} ({client.name})")

        if notify_callbacks and self.on_client_disconnected_cb:
            try:
                self.on_client_disconnected_cb(slot_id)
            except Exception as e:
                print(f"[!] Error en callback on_client_disconnected: {e}")

    def _disconnect_client(self, slot_id: str, notify_callbacks: bool = True):
        """Cierra la conexion de un cliente, resetea sus entradas y libera su ranura."""
        client = None
        with self.lock:
            client = self.clients.pop(slot_id, None)
        if client:
            self._finish_client_disconnect(slot_id, client, notify_callbacks=notify_callbacks)

    def kick_client(self, slot_id: str):
        """Desconecta intencionalmente a un cliente especifico."""
        self._disconnect_client(slot_id, notify_callbacks=True)


# Instancia singleton del servidor
_server_instance: Optional[WebGamepadServer] = None

def get_server_instance() -> WebGamepadServer:
    global _server_instance
    if _server_instance is None:
        _server_instance = WebGamepadServer()
    return _server_instance
