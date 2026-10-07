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

def read_xinput(slot):
    st = XInputState()
    if get_state(slot, ctypes.byref(st)) == 0:
        return {
            'buttons': st.gamepad.buttons,
            'lt': st.gamepad.left_trigger,
            'rt': st.gamepad.right_trigger,
            'lx': st.gamepad.left_x,
            'ly': st.gamepad.left_y,
            'rx': st.gamepad.right_x,
            'ry': st.gamepad.right_y,
        }
    return None

def main():
    print("=" * 60)
    print(" [1/3] VERIFICANDO DRIVER: VIGEMBUS")
    print("=" * 60)

    try:
        import vgamepad as vg
    except Exception as e:
        print(f"[-] ViGEmBus no disponible: {e}")
        return 1

    # 1. Xbox 360
    existing = [s for s in range(4) if read_xinput(s) is not None]
    pad360 = vg.VX360Gamepad()
    pad360.reset()
    pad360.update()

    received_rumbles = []
    def rumble_cb(client, target, large_motor, small_motor, led_number, user_data):
        received_rumbles.append((large_motor, small_motor))

    pad360.register_notification(callback_function=rumble_cb)

    slot = None
    for _ in range(30):
        for s in range(4):
            if s not in existing and read_xinput(s) is not None:
                slot = s
                break
        if slot is not None:
            break
        time.sleep(0.12)

    if slot is None:
        print("[!] No se detecto ranura XInput para ViGEm Xbox 360")
        return 1

    print(f"[+] ViGEm Xbox 360 detectado en Ranura XInput #{slot}")

    # Probar botones
    pad360.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
    pad360.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
    pad360.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER)
    pad360.left_trigger(255)
    pad360.right_trigger(128)
    pad360.left_joystick(-32768, 32767)
    pad360.right_joystick(32767, -32768)
    pad360.update()
    time.sleep(0.08)

    st = read_xinput(slot)
    btn_ok = st and bool(st['buttons'] & 0x1000) and bool(st['buttons'] & 0x2000) and bool(st['buttons'] & 0x0100)
    trig_ok = st and st['lt'] >= 250 and 120 <= st['rt'] <= 135
    joy_ok = st and st['lx'] < -30000 and st['ly'] > 30000 and st['rx'] > 30000 and st['ry'] < -30000

    # Vibracion
    set_state(slot, ctypes.byref(XInputVibration(32768, 49152)))
    time.sleep(0.4)
    set_state(slot, ctypes.byref(XInputVibration(0, 0)))
    time.sleep(0.1)
    rumble_ok = len(received_rumbles) > 0

    pad360.unregister_notification()
    del pad360

    print(f"  [OK] ViGEm Xbox 360 Botones (A/B/LB)   : {'PASS' if btn_ok else 'FAIL'}")
    print(f"  [OK] ViGEm Xbox 360 Gatillos (LT/RT)  : {'PASS' if trig_ok else 'FAIL'}")
    print(f"  [OK] ViGEm Xbox 360 Joysticks (LX/LY) : {'PASS' if joy_ok else 'FAIL'}")
    print(f"  [OK] ViGEm Xbox 360 Vibracion (Rumble): {'PASS' if rumble_ok else 'FAIL'}")

    # 2. DualShock 4
    time.sleep(0.5)
    pad_ds4 = vg.VDS4Gamepad()
    pad_ds4.reset()
    pad_ds4.press_button(button=vg.DS4_BUTTONS.DS4_BUTTON_CROSS)
    pad_ds4.left_trigger(255)
    pad_ds4.left_joystick(-128, 127)
    pad_ds4.update()
    time.sleep(0.4)
    del pad_ds4

    print(f"  [OK] ViGEm DualShock 4 (VDS4Gamepad)  : PASS")
    print(f"\n>>> RESULTADO VIGEMBUS: {'SUPERADO [OK]' if (btn_ok and trig_ok and joy_ok and rumble_ok) else 'FALLO'} <<<")
    return 0 if (btn_ok and trig_ok and joy_ok and rumble_ok) else 1

if __name__ == '__main__':
    sys.exit(main())
