import os
import sys
import time
import ctypes
from ctypes import wintypes as w

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from viiper_backend import ViiperClient, XBOX_ONE_BUTTONS

class XInputGamepad(ctypes.Structure):
    _fields_ = [
        ("buttons", w.WORD),
        ("left_trigger", w.BYTE),
        ("right_trigger", w.BYTE),
        ("left_x", ctypes.c_short),
        ("left_y", ctypes.c_short),
        ("right_x", ctypes.c_short),
        ("right_y", ctypes.c_short),
    ]

class XInputState(ctypes.Structure):
    _fields_ = [("packet", w.DWORD), ("gamepad", XInputGamepad)]

class XInputVibration(ctypes.Structure):
    _fields_ = [
        ("wLeftMotorSpeed", w.WORD),
        ("wRightMotorSpeed", w.WORD),
    ]

def get_xinput():
    try:
        return ctypes.WinDLL("XInput1_4.dll")
    except Exception:
        return ctypes.WinDLL("xinput9_1_0.dll")

xinput = get_xinput()
get_state = xinput.XInputGetState
get_state.argtypes = [w.DWORD, ctypes.POINTER(XInputState)]
get_state.restype = w.DWORD

set_state = xinput.XInputSetState
set_state.argtypes = [w.DWORD, ctypes.POINTER(XInputVibration)]
set_state.restype = w.DWORD

def read_xinput_slot(slot_idx: int):
    st = XInputState()
    res = get_state(slot_idx, ctypes.byref(st))
    if res == 0:
        return {
            'packet': st.packet,
            'buttons': st.gamepad.buttons,
            'lt': st.gamepad.left_trigger,
            'rt': st.gamepad.right_trigger,
            'lx': st.gamepad.left_x,
            'ly': st.gamepad.left_y,
            'rx': st.gamepad.right_x,
            'ry': st.gamepad.right_y,
        }
    return None

def find_new_xinput_slot(existing_slots):
    for _ in range(40):
        for slot in range(4):
            if slot not in existing_slots:
                st = read_xinput_slot(slot)
                if st is not None:
                    return slot
        time.sleep(0.15)
    return None

def test_profile(client, dev_type: str, existing_slots):
    print(f"\n>>> INICIANDO PRUEBA DE CONTROLADOR: {dev_type.upper()} <<<")
    received_rumbles = []
    def on_rumble(slot, left_motor, right_motor):
        print(f"    >>> [FEEDBACK RUMBLE RECIBIDO] Slot {slot}: Motor Izq={left_motor}, Motor Der={right_motor}")
        received_rumbles.append((left_motor, right_motor))

    print(f"[*] Creando mando virtual {dev_type} GIP en slot 0 con retroalimentacion de vibracion...")
    if not client.add_device(0, dev_type, feedback_cb=on_rumble):
        print("[!] Error creando mando en VIIPER.")
        return False

    slot = find_new_xinput_slot(existing_slots)
    if slot is None:
        print("[!] No se detecto ranura XInput para el mando virtual.")
        return False
    print(f"[+] Mando detectado por Windows en Ranura XInput #{slot}")
    time.sleep(0.5)

    buttons_to_test = [
        ("A", XBOX_ONE_BUTTONS['A'], 0x1000),
        ("B", XBOX_ONE_BUTTONS['B'], 0x2000),
        ("X", XBOX_ONE_BUTTONS['X'], 0x4000),
        ("Y", XBOX_ONE_BUTTONS['Y'], 0x8000),
        ("LB", XBOX_ONE_BUTTONS['LEFT_SHOULDER'], 0x0100),
        ("RB", XBOX_ONE_BUTTONS['RIGHT_SHOULDER'], 0x0200),
        ("BACK", XBOX_ONE_BUTTONS['BACK'], 0x0020),
        ("START", XBOX_ONE_BUTTONS['START'], 0x0010),
        ("DPAD_UP", XBOX_ONE_BUTTONS['DPAD_UP'], 0x0001),
        ("DPAD_DOWN", XBOX_ONE_BUTTONS['DPAD_DOWN'], 0x0002),
        ("DPAD_LEFT", XBOX_ONE_BUTTONS['DPAD_LEFT'], 0x0004),
        ("DPAD_RIGHT", XBOX_ONE_BUTTONS['DPAD_RIGHT'], 0x0008),
    ]

    all_buttons_ok = True
    for b_name, b_mask, expected_xinput in buttons_to_test:
        if dev_type == 'xboxone':
            client.send_xboxone_state(0, b_mask, 0, 0, 0, 0, 0, 0)
        else:
            client.send_xboxseries_state(0, b_mask, 0, 0, 0, 0, 0, 0)
        time.sleep(0.06)
        st = read_xinput_slot(slot)
        has_btn = bool(st['buttons'] & expected_xinput) if st else False
        if has_btn:
            print(f"  [OK] Boton {b_name:<10}: Reconocido (XInput: 0x{st['buttons']:04X})")
        else:
            print(f"  [FAIL] Boton {b_name:<8}: No reconocido")
            all_buttons_ok = False

    # Neutral
    if dev_type == 'xboxone':
        client.send_xboxone_state(0, 0, 0, 0, 0, 0, 0, 0)
    else:
        client.send_xboxseries_state(0, 0, 0, 0, 0, 0, 0, 0)

    # Triggers
    if dev_type == 'xboxone':
        client.send_xboxone_state(0, 0, 255, 128, 0, 0, 0, 0)
    else:
        client.send_xboxseries_state(0, 0, 255, 128, 0, 0, 0, 0)
    time.sleep(0.08)
    st_trig = read_xinput_slot(slot)
    trig_ok = st_trig and st_trig['lt'] >= 250 and 100 <= st_trig['rt'] <= 150
    print(f"  [OK] Gatillos: LT={st_trig['lt'] if st_trig else 0}, RT={st_trig['rt'] if st_trig else 0}")

    # Sticks
    if dev_type == 'xboxone':
        client.send_xboxone_state(0, 0, 0, 0, -32768, 32767, 32767, -32768)
    else:
        client.send_xboxseries_state(0, 0, 0, 0, -32768, 32767, 32767, -32768)
    time.sleep(0.08)
    st_stick = read_xinput_slot(slot)
    stick_ok = st_stick and st_stick['lx'] < -30000 and st_stick['ly'] > 30000 and st_stick['rx'] > 30000 and st_stick['ry'] < -30000
    print(f"  [OK] Joysticks: LX={st_stick['lx'] if st_stick else 0}, LY={st_stick['ly'] if st_stick else 0}, RX={st_stick['rx'] if st_stick else 0}, RY={st_stick['ry'] if st_stick else 0}")

    # Reset
    if dev_type == 'xboxone':
        client.send_xboxone_state(0, 0, 0, 0, 0, 0, 0, 0)
    else:
        client.send_xboxseries_state(0, 0, 0, 0, 0, 0, 0, 0)
    time.sleep(0.05)

    # Rumble
    vib = XInputVibration(32768, 49152)
    set_state(slot, ctypes.byref(vib))
    time.sleep(0.5)
    set_state(slot, ctypes.byref(XInputVibration(0, 0)))
    time.sleep(0.2)
    rumble_ok = len(received_rumbles) > 0
    print(f"  [OK] Vibracion recibida: {rumble_ok} ({received_rumbles[-1] if received_rumbles else 'none'})")

    client.remove_device(0)
    time.sleep(1.0)
    return all_buttons_ok and trig_ok and stick_ok and rumble_ok

def test_full_gamepad():
    print("=" * 60)
    print("[*] PRUEBA COMPLETA: XBOX ONE Y XBOX SERIES (GIP)")
    print("=" * 60)

    existing = [s for s in range(4) if read_xinput_slot(s) is not None]
    client = ViiperClient()
    if not client.start_bus():
        return False

    try:
        ok_one = test_profile(client, 'xboxone', existing)
        time.sleep(1.0)
        ok_series = test_profile(client, 'xboxseries', existing)
        print("\n" + "=" * 60)
        print(f"RESULTADO FINAL:")
        print(f"  Xbox One GIP   : {'SUPERADO [OK]' if ok_one else 'FALLO'}")
        print(f"  Xbox Series GIP: {'SUPERADO [OK]' if ok_series else 'FALLO'}")
        print("=" * 60)
        return ok_one and ok_series
    finally:
        client.stop()

if __name__ == '__main__':
    ok = test_full_gamepad()
    sys.exit(0 if ok else 1)
