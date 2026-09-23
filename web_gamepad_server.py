"""
web_gamepad_server.py
Servidor HTTP y WebSocket multicliente embebido (puro Python) para j360More.
Permite conectar hasta 12 smartphones (iOS / Android) por Wi-Fi como mandos virtuales AirPad.
Zero-Install: Los jugadores solo necesitan escanear el código QR en el navegador de su teléfono.
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

def get_local_ip() -> str:
    """Obtiene la direccion IP de la interfaz local activa (Wi-Fi / Ethernet)."""
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

        # Estado normalizado de botones
        self.buttons = {
            "A": False, "B": False, "X": False, "Y": False,
            "LB": False, "RB": False, "BACK": False, "START": False,
            "GUIDE": False, "LS": False, "RS": False,
            "UP": False, "DOWN": False, "LEFT": False, "RIGHT": False
        }

        # Estado normalizado de ejes [-1.0, 1.0] y gatillos [0.0, 1.0]
        self.axes = {
            "lx": 0.0, "ly": 0.0,
            "rx": 0.0, "ry": 0.0,
            "lt": 0.0, "rt": 0.0
        }

    def update_button(self, btn_name: str, state: int):
        self.last_activity = time.time()
        key = btn_name.upper()
        # Normalizaciones de nombres
        name_map = {
            "DPADUP": "UP", "DPADDOWN": "DOWN", "DPADLEFT": "LEFT", "DPADRIGHT": "RIGHT",
            "SELECT": "BACK", "L1": "LB", "R1": "RB", "L3": "LS", "R3": "RS",
            "HOME": "GUIDE"
        }
        key = name_map.get(key, key)
        if key in self.buttons:
            self.buttons[key] = (state == 1)

    def update_trigger(self, side: str, value: float):
        self.last_activity = time.time()
        s = side.lower()
        val = max(0.0, min(1.0, float(value)))
        if s in ("l", "lt", "l2"):
            self.axes["lt"] = val
        elif s in ("r", "rt", "r2"):
            self.axes["rt"] = val

    def update_joystick(self, stick: str, x: float, y: float):
        self.last_activity = time.time()
        s = stick.lower()
        vx = max(-1.0, min(1.0, float(x)))
        vy = max(-1.0, min(1.0, float(y)))
        if s in ("l", "left"):
            self.axes["lx"] = vx
            self.axes["ly"] = vy
        elif s in ("r", "right"):
            self.axes["rx"] = vx
            self.axes["ry"] = vy

    def get_physical_state(self) -> Dict[str, Any]:
        """Convierte el estado de AirPad al diccionario compatible con EmulatorEngine."""
        b = self.buttons
        a = self.axes

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
            }
        }


class WebGamepadServer:
    """
    Servidor HTTP & WebSocket ultra ligero para j360More AirPad.
    Gestiona hasta 12 ranuras de smartphones simultaneos.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080, static_dir: Optional[str] = None):
        self.host = host
        self.port = port
        self.static_dir = static_dir
        if not self.static_dir:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.static_dir = os.path.join(base_dir, "assets", "web_pad")

        self.running = False
        self.server_sock: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        # Slots 1..12
        self.clients: Dict[str, AirPadClient] = {}

        # Opciones
        self.max_slots: int = 8
        self.haptics_enabled = True
        self.auto_assign_enabled = True

        # Callbacks
        self.on_client_connected_cb: Optional[Callable[[str, AirPadClient], None]] = None
        self.on_client_disconnected_cb: Optional[Callable[[str], None]] = None

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
            print(f"[*] Servidor AirPad iniciado en http://{get_local_ip()}:{self.port}")
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
        """Detiene el servidor y desconecta a todos los clientes."""
        self.running = False
        with self.lock:
            for slot_id, client in list(self.clients.items()):
                self._disconnect_client(slot_id)

        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
            self.server_sock = None

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
            self.thread = None

    def get_url(self) -> str:
        """Retorna la URL local para el QR y el portapapeles."""
        return f"http://{get_local_ip()}:{self.port}"

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
            "raw_phone": {"buttons": {}, "axes": {}}
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
                # Recoger sockets a monitorear
                with self.lock:
                    sockets = [self.server_sock]
                    client_map = {}
                    for slot_id, client in self.clients.items():
                        if client.active:
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
                # Fallback para SPA o 404
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
            # Servidor lleno (max 12)
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

        # Enviar mensaje de bienvenida con el slot y configuración
        welcome = {
            "type": "welcome",
            "slot": slot_num,
            "slot_id": slot_id,
            "haptics": self.haptics_enabled,
            "name": client.name
        }
        self._send_ws_frame(conn, json.dumps(welcome))

        if self.on_client_connected_cb:
            try:
                self.on_client_connected_cb(slot_id, client)
            except Exception as e:
                print(f"[!] Error en callback on_client_connected: {e}")

    def _handle_ws_data(self, slot_id: str, sock: socket.socket):
        """Lee y decodifica tramas WebSocket entrantes."""
        try:
            head = sock.recv(2)
            if not head or len(head) < 2:
                self._disconnect_client(slot_id)
                return

            b1, b2 = head[0], head[1]
            opcode = b1 & 0x0F
            masked = (b2 & 0x80) != 0
            payload_len = b2 & 0x7F

            # 0x8 = Close frame
            if opcode == 0x8:
                self._disconnect_client(slot_id)
                return

            if payload_len == 126:
                ext = sock.recv(2)
                payload_len = struct.unpack("!H", ext)[0]
            elif payload_len == 127:
                ext = sock.recv(8)
                payload_len = struct.unpack("!Q", ext)[0]

            mask_key = sock.recv(4) if masked else None

            # Leer carga util
            raw_payload = b""
            while len(raw_payload) < payload_len:
                chunk = sock.recv(min(4096, payload_len - len(raw_payload)))
                if not chunk:
                    break
                raw_payload += chunk

            if mask_key:
                unmasked = bytearray(len(raw_payload))
                for i in range(len(raw_payload)):
                    unmasked[i] = raw_payload[i] ^ mask_key[i % 4]
                payload_str = unmasked.decode("utf-8", errors="ignore")
            else:
                payload_str = raw_payload.decode("utf-8", errors="ignore")

            # Procesar JSON
            if opcode == 0x1:  # Text frame
                self._process_message(slot_id, payload_str)
            elif opcode == 0x9:  # Ping
                # Responder pong
                pong_frame = bytearray([0x8A, 0x00])
                sock.sendall(pong_frame)

        except (BlockingIOError, socket.timeout):
            pass
        except Exception:
            self._disconnect_client(slot_id)

    def _process_message(self, slot_id: str, raw_json: str):
        """Parsea el mensaje JSON recibido del smartphone."""
        try:
            msg = json.loads(raw_json)
            client = self.clients.get(slot_id)
            if not client:
                return

            m_type = msg.get("type", "")

            if m_type == "btn":
                btn = msg.get("button") or msg.get("btn", "")
                state = int(msg.get("state", 0))
                client.update_button(btn, state)

            elif m_type == "trigger":
                side = msg.get("side", "")
                val = float(msg.get("value", 0.0))
                client.update_trigger(side, val)

            elif m_type == "joystick":
                stick = msg.get("stick", "")
                x = float(msg.get("x", 0.0))
                y = float(msg.get("y", 0.0))
                client.update_joystick(stick, x, y)

            elif m_type == "info":
                name = msg.get("name")
                model = msg.get("model")
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

    def _disconnect_client(self, slot_id: str):
        """Cierra la conexion de un cliente y libera su ranura."""
        client = self.clients.pop(slot_id, None)
        if client:
            client.active = False
            try:
                client.sock.close()
            except Exception:
                pass
            print(f"[-] AirPad desconectado: {slot_id} ({client.name})")

            if self.on_client_disconnected_cb:
                try:
                    self.on_client_disconnected_cb(slot_id)
                except Exception as e:
                    print(f"[!] Error en callback on_client_disconnected: {e}")

    def kick_client(self, slot_id: str):
        """Desconecta intencionalmente a un cliente especifico."""
        with self.lock:
            self._disconnect_client(slot_id)


# Instancia singleton del servidor
_server_instance: Optional[WebGamepadServer] = None

def get_server_instance() -> WebGamepadServer:
    global _server_instance
    if _server_instance is None:
        _server_instance = WebGamepadServer()
    return _server_instance
