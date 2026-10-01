"""
plugins/plugin_ipc.py
High-performance, ultra-low latency (< 0.1 ms) IPC transport for j360More plugins.
Supports line-delimited JSON streaming over optimized localhost TCP sockets (with TCP_NODELAY)
and Unix Domain Sockets on Linux/POSIX platforms.
"""

import json
import logging
import os
import queue
import socket
import sys
import threading
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("j360More.IPC")

DEFAULT_HOST = "127.0.0.1"


class IPCConnectionClosed(Exception):
    """Raised when an IPC connection is cleanly or abruptly closed."""
    pass


class IPCServer:
    """
    Host-side IPC endpoint hosted by j360More.
    Binds an ephemeral loopback socket, awaits child process connection,
    and handles bidirectional streaming.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = 0, unix_path: Optional[str] = None):
        self.host = host
        self.port = port
        self.unix_path = unix_path
        self._server_sock: Optional[socket.socket] = None
        self._client_sock: Optional[socket.socket] = None
        self._running = False
        self._read_thread: Optional[threading.Thread] = None
        self._accept_thread: Optional[threading.Thread] = None
        self._on_message_callbacks = []
        self._on_connect_callbacks = []
        self._on_disconnect_callbacks = []
        self._send_lock = threading.Lock()
        self._is_connected = False

    def start(self) -> int:
        """Starts listening. Returns the allocated port or 0 if unix socket."""
        if self.unix_path and hasattr(socket, "AF_UNIX"):
            if os.path.exists(self.unix_path):
                os.unlink(self.unix_path)
            self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server_sock.bind(self.unix_path)
            self._server_sock.listen(1)
            self.port = 0
        else:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind((self.host, self.port))
            self._server_sock.listen(1)
            self.port = self._server_sock.getsockname()[1]

        self._running = True
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True, name="IPCServer-Accept")
        self._accept_thread.start()
        return self.port

    def add_on_message(self, callback: Callable[[Dict[str, Any]], None]):
        self._on_message_callbacks.append(callback)

    def add_on_connect(self, callback: Callable[[], None]):
        self._on_connect_callbacks.append(callback)

    def add_on_disconnect(self, callback: Callable[[], None]):
        self._on_disconnect_callbacks.append(callback)

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self._client_sock is not None

    def _accept_loop(self):
        try:
            while self._running:
                client_sock, _ = self._server_sock.accept()
                if not self.unix_path:
                    try:
                        client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    except Exception:
                        pass

                self._client_sock = client_sock
                self._is_connected = True

                for cb in self._on_connect_callbacks:
                    try:
                        cb()
                    except Exception as e:
                        logger.error(f"Error in on_connect callback: {e}")

                self._read_loop(client_sock)
        except Exception:
            pass
        finally:
            self._is_connected = False

    def _read_loop(self, client_sock: socket.socket):
        buffer = ""
        try:
            while self._running:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        for cb in self._on_message_callbacks:
                            try:
                                cb(msg)
                            except Exception as e:
                                logger.error(f"Error in on_message callback: {e}")
                    except json.JSONDecodeError as jde:
                        logger.warning(f"Malformed JSON in IPC: {jde} -> {line[:80]}")
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass
        finally:
            self._is_connected = False
            for cb in self._on_disconnect_callbacks:
                try:
                    cb()
                except Exception as e:
                    logger.error(f"Error in on_disconnect callback: {e}")

    def send(self, message: Dict[str, Any]) -> bool:
        """Sends a JSON message delimited by newline. Returns True if sent."""
        if not self.is_connected or not self._client_sock:
            return False
        try:
            payload = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
            with self._send_lock:
                self._client_sock.sendall(payload)
            return True
        except Exception as e:
            logger.debug(f"IPCServer send error: {e}")
            self._is_connected = False
            return False

    def close(self):
        self._running = False
        self._is_connected = False
        if self._client_sock:
            try:
                self._client_sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self._client_sock.close()
            except Exception:
                pass
            self._client_sock = None

        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

        if self.unix_path and os.path.exists(self.unix_path):
            try:
                os.unlink(self.unix_path)
            except Exception:
                pass


class IPCClient:
    """
    Client-side IPC endpoint used inside plugin worker scripts.
    Connects to j360More server and manages bidirectional messaging.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = 0, unix_path: Optional[str] = None):
        self.host = host
        self.port = port
        self.unix_path = unix_path
        self._sock: Optional[socket.socket] = None
        self._running = False
        self._read_thread: Optional[threading.Thread] = None
        self._on_message_callbacks = []
        self._on_disconnect_callbacks = []
        self._send_lock = threading.Lock()
        self._is_connected = False

    def connect(self, timeout: float = 5.0) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if self.unix_path and hasattr(socket, "AF_UNIX"):
                    self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    self._sock.connect(self.unix_path)
                else:
                    self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    try:
                        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    except Exception:
                        pass
                    self._sock.connect((self.host, self.port))

                self._is_connected = True
                self._running = True
                self._read_thread = threading.Thread(target=self._read_loop, daemon=True, name="IPCClient-Read")
                self._read_thread.start()
                return True
            except (ConnectionRefusedError, FileNotFoundError, OSError):
                time.sleep(0.05)

        return False

    def add_on_message(self, callback: Callable[[Dict[str, Any]], None]):
        self._on_message_callbacks.append(callback)

    def add_on_disconnect(self, callback: Callable[[], None]):
        self._on_disconnect_callbacks.append(callback)

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self._sock is not None

    def _read_loop(self):
        buffer = ""
        try:
            while self._running and self._sock:
                chunk = self._sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        for cb in self._on_message_callbacks:
                            try:
                                cb(msg)
                            except Exception as e:
                                logger.error(f"Error in client on_message: {e}")
                    except json.JSONDecodeError as jde:
                        logger.warning(f"Malformed JSON in client IPC: {jde}")
        except Exception:
            pass
        finally:
            self._is_connected = False
            for cb in self._on_disconnect_callbacks:
                try:
                    cb()
                except Exception:
                    pass

    def send(self, message: Dict[str, Any]) -> bool:
        if not self.is_connected or not self._sock:
            return False
        try:
            payload = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
            with self._send_lock:
                self._sock.sendall(payload)
            return True
        except Exception:
            self._is_connected = False
            return False

    def close(self):
        self._running = False
        self._is_connected = False
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
