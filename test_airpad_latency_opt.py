import os
import sys
import time
import socket
import struct
import hashlib
import base64
import json
import threading

import web_gamepad_server
import emulator_engine
from input_devices import DeviceManager

def test_all():
    print("=== TEST 1: IP Detection ===")
    all_ip_data = web_gamepad_server.get_all_local_ips()
    print(f"Detected local IPs: {all_ip_data}")
    assert len(all_ip_data) > 0, "Should detect at least 1 local IP"
    ips = [item["ip"] for item in all_ip_data]
    primary_ip = web_gamepad_server.get_local_ip()
    print(f"Primary local IP: {primary_ip}")
    assert primary_ip in ips

    print("\n=== TEST 2: Precompiled Mappings & Engine Wakeup ===")
    dev_mgr = DeviceManager()
    engine = emulator_engine.EmulatorEngine(dev_mgr)

    test_cfg = {
        "max_controllers": 4,
        "emulated_type": "xbox360",
        "controllers": {
            "1": {
                "enabled": True,
                "physical_device_id": "phone_1",
                "mappings": {
                    "A": "Button 1",
                    "B": "Button 2",
                    "LEFT_THUMB": "Button 9",
                    "RIGHT_THUMB": "Button 10",
                    "LEFT_TRIGGER": "Axis 3+",
                    "LEFT_STICK_X": "Axis 1",
                    "LEFT_STICK_Y": "Axis 2"
                }
            }
        }
    }
    engine.set_config(test_cfg)
    assert 1 in engine.compiled_mappings
    assert engine.compiled_mappings[1]["A"] == ("button", 0)
    assert engine.compiled_mappings[1]["LEFT_THUMB"] == ("button", 8)
    assert engine.compiled_mappings[1]["RIGHT_THUMB"] == ("button", 9)
    assert engine.compiled_mappings[1]["LEFT_TRIGGER"][0] == "axis"
    print("Precompiled mappings verified successfully!")

    # Test reactive event wake up
    t0 = time.perf_counter()
    engine.trigger_input_event()
    engine.input_event.wait(timeout=0.008)
    t_elapsed = (time.perf_counter() - t0) * 1000
    print(f"Reactive wake up time: {t_elapsed:.3f} ms (target: < 1.0 ms)")
    assert t_elapsed < 5.0, "Reactive wakeup should be near instant"

    print("\n=== TEST 3: Web Server + Binary WebSocket Protocol ===")
    srv = web_gamepad_server.get_server_instance()
    srv.port = 18888
    srv.max_slots = 4

    input_event_called = threading.Event()
    srv.on_input_event = lambda: input_event_called.set()

    srv.start()
    time.sleep(0.2)
    assert srv.running

    # Realizar handshake WebSocket raw
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 18888))

    sec_key = base64.b64encode(os.urandom(16)).decode('ascii')
    req = (
        f"GET /ws HTTP/1.1\r\n"
        f"Host: 127.0.0.1:18888\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {sec_key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    )
    s.sendall(req.encode('ascii'))

    raw_buffer = bytearray()
    while b"\r\n\r\n" not in raw_buffer:
        chunk = s.recv(4096)
        if not chunk:
            break
        raw_buffer.extend(chunk)

    idx = raw_buffer.find(b"\r\n\r\n")
    http_resp = bytes(raw_buffer[:idx+4])
    assert b"101 Switching Protocols" in http_resp, f"Handshake failed: {http_resp}"
    print("[+] WebSocket handshake completed successfully!")

    frame = bytearray(raw_buffer[idx+4:])
    while len(frame) < 2:
        frame.extend(s.recv(4096))

    payload_len = frame[1] & 0x7F
    offset = 2
    if payload_len == 126:
        while len(frame) < 4:
            frame.extend(s.recv(4096))
        payload_len = struct.unpack("!H", frame[2:4])[0]
        offset = 4
    elif payload_len == 127:
        while len(frame) < 10:
            frame.extend(s.recv(4096))
        payload_len = struct.unpack("!Q", frame[2:10])[0]
        offset = 10

    while len(frame) < offset + payload_len:
        frame.extend(s.recv(4096))

    welcome_bytes = bytes(frame[offset:offset+payload_len])
    welcome_json = json.loads(welcome_bytes.decode('utf-8'))
    print(f"[+] Welcome frame payload: {welcome_json}")
    assert welcome_json.get("type") == "welcome"
    assert welcome_json.get("binary") == True
    assert welcome_json.get("protocol") == "bin_v1"

    # Enviar paquete binario v1 (<BBIHBBhhhhI = 22 bytes)
    # Mask bit set = 0x80
    # buttons = (1 << 9) [LS] | (1 << 10) [RS] | (1 << 0) [A]
    # lt = 255, rt = 128
    # lx = -16384, ly = 16384, rx = 32767, ry = -32767
    btn_mask = (1 << 0) | (1 << 9) | (1 << 10)
    bin_payload = web_gamepad_server.STRUCT_BIN_V1_22.pack(
        1, 1, 100, btn_mask, 255, 128, -16384, 16384, 32767, -32767, 12345
    )
    assert len(bin_payload) == 22

    # Construir frame RFC 6455 de cliente (enmascarado, opcode 0x02 BINARY)
    mask_key = b"\x12\x34\x56\x78"
    masked_data = bytearray(22)
    for i in range(22):
        masked_data[i] = bin_payload[i] ^ mask_key[i % 4]

    ws_frame = bytearray([0x82, 0x80 | 22]) + mask_key + masked_data
    s.sendall(ws_frame)

    # Esperar a que se procese y despierte engine
    assert input_event_called.wait(timeout=1.0), "on_input_event should have been called"
    print("[+] input_event triggered by binary packet!")

    time.sleep(0.05)
    phys_state = dev_mgr.read_physical_state("phone_1")
    print(f"[+] Decoded phone_1 state: buttons={phys_state['buttons']}, axes={phys_state['axes']}")

    # Verificar botones decodificados
    # Button 1 (A) -> idx 0
    # Button 9 (LS) -> idx 8
    # Button 10 (RS) -> idx 9
    assert phys_state["buttons"].get(0) == True, "Button A should be pressed"
    assert phys_state["buttons"].get(8) == True, "Button LS should be pressed"
    assert phys_state["buttons"].get(9) == True, "Button RS should be pressed"

    # Verificar gatillo LT (255 -> DirectInput 1.0) y RT (128 -> DirectInput ~0.00)
    assert abs(phys_state["axes"].get(2, 0.0) - 1.0) < 0.02, f"LT should be ~1.0, got {phys_state['axes'].get(2)}"
    assert abs(phys_state["axes"].get(5, 0.0) - 0.004) < 0.02, f"RT should be ~0.004 (DirectInput scale), got {phys_state['axes'].get(5)}"

    # Verificar joystick LX (-16384/32767 -> -0.50), LY (16384/32767 -> 0.50)
    assert abs(phys_state["axes"].get(0, 0.0) - (-0.50)) < 0.02, f"LX should be ~ -0.50, got {phys_state['axes'].get(0)}"
    assert abs(phys_state["axes"].get(1, 0.0) - 0.50) < 0.02, f"LY should be ~ 0.50, got {phys_state['axes'].get(1)}"

    # Verificar telemetría del servidor
    srv.telemetry.enabled = True
    assert srv.telemetry is not None
    stats = srv.telemetry.get_stats()
    print(f"[+] Server Telemetry stats: {stats}")

    s.close()
    time.sleep(0.1)
    srv.stop()
    print("\n>>> ALL AIRPAD LATENCY & PROTOCOL TESTS PASSED WITH 100% SUCCESS! <<<")

if __name__ == "__main__":
    test_all()
