import os
import sys
import time
import ctypes
from ctypes import wintypes as w

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

try:
    xinput = ctypes.WinDLL("XInput1_4.dll")
except Exception:
    xinput = ctypes.WinDLL("xinput9_1_0.dll")

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
    for _ in range(30):
        for slot in range(4):
            if slot not in existing_slots:
                st = read_xinput_slot(slot)
                if st is not None:
                    return slot
        time.sleep(0.15)
    return None

def test_vigem_xbox360():
    print("=" * 60)
    print("[*] PRUEBA VIGEMBUS: XBOX 360")
    print("=" * 60)

    try:
        import vgamepad as vg
    except Exception as e:
        print(f"[!] ViGEmBus / vgamepad no disponible: {e}")
        return False

    existing = [s for s in range(4) if read_xinput_slot(s) is not None]
    print(f"[*] Ranuras previas: {existing}")

    pad = vg.VX360Gamepad()
    pad.reset()
    pad.update()

    received_rumbles = []
    def rumble_cb(client, target, large_motor, small_motor, led_number, user_data):
        print(f"    >>> [VIGEM RUMBLE RECIBIDO] L={large_motor}, R={small_motor}")
        received_rumbles.append((large_motor, small_motor))

    pad.register_notification(callback_function=rumble_cb)

    slot = find_new_xinput_slot(existing)
    if slot is None:
        print("[!] No se detecto ranura XInput para ViGEm Xbox 360.")
        return False
    print(f"[+] Ranura XInput detectada: #{slot}")
    time.sleep(0.5)

    # 1. Botones
    buttons = [
        ("A", vg.XUSB_BUTTON.XUSB_GAMEPAD_A, 0x1000),
        ("B", vg.XUSB_BUTTON.XUSB_GAMEPAD_B, 0x2000),
        ("X", vg.XUSB_BUTTON.XUSB_GAMEPAD_X, 0x4000),
        ("Y", vg.XUSB_BUTTON.XUSB_GAMEPAD_Y, 0x8000),
        ("LB", vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER, 0x0100),
        ("RB", vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, 0x0200),
        ("BACK", vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK, 0x0020),
        ("START", vg.XUSB_BUTTON.XUSB_GAMEPAD_START, 0x0010),
        ("DPAD_UP", vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, 0x0001),
        ("DPAD_DOWN", vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN, 0x0002),
        ("DPAD_LEFT", vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT, 0x0004),
        ("DPAD_RIGHT", vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT, 0x0008),
    ]

    all_btn = True
    for name, btn_const, exp_mask in buttons:
        pad.reset()
        pad.press_button(button=btn_const)
        pad.update()
        time.sleep(0.06)
        st = read_xinput_slot(slot)
        ok = bool(st['buttons'] & exp_mask) if st else False
        if ok:
            print(f"  [OK] Boton {name:<10}: Reconocido (0x{st['buttons']:04X})")
        else:
            print(f"  [FAIL] Boton {name:<8}: No reconocido")
            all_btn = False

    pad.reset()
    pad.update()

    # 2. Gatillos
    pad.left_trigger(value=255)
    pad.right_trigger(value=128)
    pad.update()
    time.sleep(0.08)
    st_t = read_xinput_slot(slot)
    trig_ok = st_t and st_t['lt'] >= 250 and 120 <= st_t['rt'] <= 135
    print(f"  [OK] Gatillos: LT={st_t['lt'] if st_t else 0}, RT={st_t['rt'] if st_t else 0}")

    # 3. Joysticks
    pad.left_joystick(x_value=-32768, y_value=32767)
    pad.right_joystick(x_value=32767, y_value=-32768)
    pad.update()
    time.sleep(0.08)
    st_j = read_xinput_slot(slot)
    joy_ok = st_j and st_j['lx'] < -30000 and st_j['ly'] > 30000 and st_j['rx'] > 30000 and st_j['ry'] < -30000
    print(f"  [OK] Joysticks: LX={st_j['lx'] if st_j else 0}, LY={st_j['ly'] if st_j else 0}, RX={st_j['rx'] if st_j else 0}, RY={st_j['ry'] if st_j else 0}")

    pad.reset()
    pad.update()

    # 4. Vibracion
    vib = XInputVibration(32768, 49152)
    set_state(slot, ctypes.byref(vib))
    time.sleep(0.5)
    set_state(slot, ctypes.byref(XInputVibration(0, 0)))
    time.sleep(0.2)
    rumble_ok = len(received_rumbles) > 0
    print(f"  [OK] Vibracion ViGEm recibida: {rumble_ok} ({received_rumbles[-1] if received_rumbles else 'none'})")

    del pad
    time.sleep(1.0)
    res = all_btn and trig_ok and joy_ok and rumble_ok
    print(f"\n>>> RESULTADO VIGEMBUS XBOX 360: {'SUPERADO [OK]' if res else 'FALLIDO'} <<<\n")
    return res

if __name__ == '__main__':
    ok = test_vigem_xbox360()
    sys.exit(0 if ok else 1)
