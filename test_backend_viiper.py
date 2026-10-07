import os
import sys
import time
import ctypes
from ctypes import wintypes as w

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from viiper_backend import (
    ViiperClient,
    XBOX_BUTTONS,
    XBOX_ONE_BUTTONS,
    DS4_BUTTONS,
    DUALSENSE_BUTTONS,
    NS2PRO_BUTTONS
)

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

def find_new_slot(existing):
    for _ in range(35):
        for s in range(4):
            if s not in existing and read_xinput(s) is not None:
                return s
        time.sleep(0.12)
    return None

def main():
    print("=" * 60)
    print(" [2/3] VERIFICANDO DRIVER: VIIPER")
    print("=" * 60)

    client = ViiperClient()
    if not client.start_bus():
        print("[!] No se pudo iniciar el bus de VIIPER.")
        return 1

    try:
        # A) Xbox One GIP
        print("\n--- [A] VIIPER XBOX ONE (GIP) ---")
        existing = [s for s in range(4) if read_xinput(s) is not None]
        received_rumbles = []
        def on_r(s, l, r): received_rumbles.append((l, r))

        if not client.add_device(0, 'xboxone', feedback_cb=on_r):
            print("[!] Error creando mando Xbox One GIP en VIIPER")
            return 1

        slot = find_new_slot(existing)
        if slot is None:
            print("[!] Ranura XInput no detectada para Xbox One GIP")
            return 1

        print(f"[+] Mando Xbox One detectado en Ranura XInput #{slot}")

        # Probar botones A, B, LB, Triggers y Joysticks
        client.send_xboxone_state(0, XBOX_ONE_BUTTONS['A'] | XBOX_ONE_BUTTONS['B'] | XBOX_ONE_BUTTONS['LEFT_SHOULDER'], 255, 128, -32768, 32767, 32767, -32768)
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

        client.remove_device(0)
        time.sleep(0.8)

        print(f"  [OK] Xbox One GIP Botones (A/B/LB)   : {'PASS' if btn_ok else 'FAIL'}")
        print(f"  [OK] Xbox One GIP Gatillos (LT/RT)  : {'PASS' if trig_ok else 'FAIL'}")
        print(f"  [OK] Xbox One GIP Joysticks (LX/LY) : {'PASS' if joy_ok else 'FAIL'}")
        print(f"  [OK] Xbox One GIP Vibracion (Rumble): {'PASS' if rumble_ok else 'FAIL'}")

        # B) Xbox Series GIP
        print("\n--- [B] VIIPER XBOX SERIES (GIP) ---")
        existing = [s for s in range(4) if read_xinput(s) is not None]
        received_rumbles.clear()
        if not client.add_device(0, 'xboxseries', feedback_cb=on_r):
            print("[!] Error creando mando Xbox Series GIP en VIIPER")
            return 1

        slot = find_new_slot(existing)
        if slot is None:
            print("[!] Ranura XInput no detectada para Xbox Series GIP")
            return 1

        print(f"[+] Mando Xbox Series detectado en Ranura XInput #{slot}")

        client.send_xboxseries_state(0, XBOX_ONE_BUTTONS['X'] | XBOX_ONE_BUTTONS['Y'] | XBOX_ONE_BUTTONS['RIGHT_SHOULDER'], 128, 255, 32767, -32768, -32768, 32767)
        time.sleep(0.08)
        st_s = read_xinput(slot)
        btn_s_ok = st_s and bool(st_s['buttons'] & 0x4000) and bool(st_s['buttons'] & 0x8000) and bool(st_s['buttons'] & 0x0200)
        trig_s_ok = st_s and 120 <= st_s['lt'] <= 135 and st_s['rt'] >= 250
        joy_s_ok = st_s and st_s['lx'] > 30000 and st_s['ly'] < -30000 and st_s['rx'] < -30000 and st_s['ry'] > 30000

        # Vibracion
        set_state(slot, ctypes.byref(XInputVibration(32768, 49152)))
        time.sleep(0.4)
        set_state(slot, ctypes.byref(XInputVibration(0, 0)))
        time.sleep(0.1)
        rumble_s_ok = len(received_rumbles) > 0

        client.remove_device(0)
        time.sleep(0.8)

        print(f"  [OK] Xbox Series GIP Botones (X/Y/RB): {'PASS' if btn_s_ok else 'FAIL'}")
        print(f"  [OK] Xbox Series GIP Gatillos (LT/RT): {'PASS' if trig_s_ok else 'FAIL'}")
        print(f"  [OK] Xbox Series GIP Joysticks (LX/LY): {'PASS' if joy_s_ok else 'FAIL'}")
        print(f"  [OK] Xbox Series GIP Vibracion (Rumble): {'PASS' if rumble_s_ok else 'FAIL'}")

        # C) Xbox 360 Simple Transport
        print("\n--- [C] VIIPER XBOX 360 ---")
        ok_360 = client.add_device(0, 'xbox360')
        if ok_360:
            client.send_xbox360_state(0, XBOX_BUTTONS['A'], 255, 0, 0, 0, 0, 0)
            time.sleep(0.2)
            client.remove_device(0)
            time.sleep(0.5)
        print(f"  [OK] VIIPER Xbox 360 (Simple Transport): {'PASS' if ok_360 else 'FAIL'}")

        # D) DualShock 4
        print("\n--- [D] VIIPER DUALSHOCK 4 ---")
        ok_ds4 = client.add_device(0, 'ds4')
        if ok_ds4:
            client.send_ds4_state(0, DS4_BUTTONS['A'], 0, 255, 0, 0, 0, 0, 0)
            time.sleep(0.2)
            client.remove_device(0)
            time.sleep(0.5)
        print(f"  [OK] VIIPER DualShock 4                : {'PASS' if ok_ds4 else 'FAIL'}")

        # E) DualSense PS5
        print("\n--- [E] VIIPER DUALSENSE (PS5) ---")
        ok_ds5 = client.add_device(0, 'dualsense')
        if ok_ds5:
            client.send_dualsense_state(0, DUALSENSE_BUTTONS['A'], 0, 255, 0, 0, 0, 0, 0)
            time.sleep(0.2)
            client.remove_device(0)
            time.sleep(0.5)
        print(f"  [OK] VIIPER DualSense PS5              : {'PASS' if ok_ds5 else 'FAIL'}")

        # F) Switch 2 Pro
        print("\n--- [F] VIIPER SWITCH 2 PRO ---")
        ok_ns2 = client.add_device(0, 'ns2pro')
        if ok_ns2:
            client.send_ns2pro_state(0, NS2PRO_BUTTONS['A'], 2048, 2048, 2048, 2048)
            time.sleep(0.2)
            client.remove_device(0)
            time.sleep(0.5)
        print(f"  [OK] VIIPER Switch 2 Pro               : {'PASS' if ok_ns2 else 'FAIL'}")

        total_pass = btn_ok and trig_ok and joy_ok and rumble_ok and btn_s_ok and trig_s_ok and joy_s_ok and rumble_s_ok and ok_360 and ok_ds4 and ok_ds5 and ok_ns2
        print(f"\n>>> RESULTADO VIIPER: {'SUPERADO [OK]' if total_pass else 'FALLO'} <<<")
        return 0 if total_pass else 1

    finally:
        client.stop()

if __name__ == '__main__':
    sys.exit(main())
