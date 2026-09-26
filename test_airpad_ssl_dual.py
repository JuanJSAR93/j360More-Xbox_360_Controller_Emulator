"""
test_airpad_ssl_dual.py
Pruebas exhaustivas para el servidor dual HTTP / HTTPS de AirPad con SSL autofirmado.
"""

import os
import socket
import ssl
import time
import base64
import urllib.request

import web_gamepad_server


def test_ensure_ssl_certificates():
    cert_path, key_path = web_gamepad_server.ensure_ssl_certificates(preferred_ip="192.168.1.100")
    assert cert_path is not None, "Certificado SSL no encontrado ni generado"
    assert key_path is not None, "Clave privada SSL no encontrada ni generada"
    assert os.path.isfile(cert_path), f"El archivo de certificado no existe: {cert_path}"
    assert os.path.isfile(key_path), f"El archivo de clave no existe: {key_path}"

    # Validar que python ssl puede cargar el certificado
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
    assert ctx is not None


def test_airpad_server_http_mode():
    server = web_gamepad_server.WebGamepadServer(host="127.0.0.1", port=0)
    server.ssl_enabled = False
    assert server.start() is True
    try:
        url = server.get_url()
        assert url.startswith("http://")

        req = urllib.request.Request(f"http://127.0.0.1:{server.port}/")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            assert resp.status == 200
            content = resp.read()
            assert len(content) > 100
    finally:
        server.stop()


def test_airpad_server_https_mode():
    server = web_gamepad_server.WebGamepadServer(host="127.0.0.1", port=0)
    server.ssl_enabled = True
    assert server.start() is True
    try:
        url = server.get_url()
        assert url.startswith("https://")

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(f"https://127.0.0.1:{server.port}/")
        with urllib.request.urlopen(req, context=ctx, timeout=3.0) as resp:
            assert resp.status == 200
            content = resp.read()
            assert len(content) > 100
    finally:
        server.stop()


def test_airpad_server_wss_handshake():
    server = web_gamepad_server.WebGamepadServer(host="127.0.0.1", port=0)
    server.ssl_enabled = True
    assert server.start() is True
    try:
        raw_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_s.connect(("127.0.0.1", server.port))
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        s = ctx.wrap_socket(raw_s, server_hostname="127.0.0.1")

        ws_key = base64.b64encode(b"1234567890123456").decode("ascii")
        req = (
            "GET / HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{server.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        s.sendall(req.encode("ascii"))
        resp = s.recv(4096)
        assert b"101 Switching Protocols" in resp

        time.sleep(0.05)
        frame = s.recv(4096)
        assert len(frame) > 2
        s.close()
    finally:
        server.stop()


def test_airpad_server_http_to_https_redirect():
    server = web_gamepad_server.WebGamepadServer(host="127.0.0.1", port=0)
    server.ssl_enabled = True
    assert server.start() is True
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", server.port))
        s.sendall(f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n\r\n".encode("ascii"))
        resp = s.recv(4096)
        assert b"301 Moved Permanently" in resp
        assert b"Location: https://" in resp
        s.close()
    finally:
        server.stop()


if __name__ == "__main__":
    test_ensure_ssl_certificates()
    test_airpad_server_http_mode()
    test_airpad_server_https_mode()
    test_airpad_server_wss_handshake()
    test_airpad_server_http_to_https_redirect()
    print("ALL TESTS PASSED SUCCESSFULLY!")
