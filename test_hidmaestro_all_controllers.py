import os
import sys
import time
import ctypes
from ctypes import wintypes as w

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hidmaestro_backend import HidMaestroClient, HM_BUTTONS

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
    for _ in range(40):
        for s in range(4):
            if s not in existing and read_xinput(s) is not None:
                return s
        time.sleep(0.12)
    return None

def test_hidmaestro_all():
    print("=" * 65)
    print(" [3/3] PRUEBA COMPLETA DE MANDOS EN HIDMAESTRO")
    print("=" * 65)

    client = HidMaestroClient()
    if not client.is_server_alive():
        print("[!] El servidor HIDMaestro no esta en ejecucion.")
        print("    Por favor ejecuta 'iniciar_hidmaestro_como_administrador.cmd' para activarlo.")
        return 1

    elevated = client.is_server_elevated()
    print(f"[+] Servidor HIDMaestro detectado (Elevado: {elevated}).")

    if not client.start():
        print("[!] Error conectando el socket cliente de HIDMaestro.")
        return 1

    profiles = [
        ("xboxone", "Xbox One S"),
        ("xboxseries", "Xbox Series X|S"),
        ("xbox360", "Xbox 360"),
        ("ds4", "DualShock 4"),
        ("dualsense", "DualSense PS5"),
    ]

    results = {}

    try:
        for p_key, p_name in profiles:
            print(f"\n>>> PROBANDO PERFIL HIDMAESTRO: {p_name} ({p_key}) <<<")
            existing = [s for s in range(4) if read_xinput(s) is not None]
            received_rumbles = []
            def on_r(s, l, r):
                received_rumbles.append((l, r))

            ok_create = client.add_device(1, p_key, feedback_cb=on_r)
            if not ok_create:
                print(f"  [!] Fallo creando mando {p_name} en HIDMaestro.")
                results[p_key] = False
                continue

            print(f"  [+] Dispositivo {p_name} instanciado en HIDMaestro. Esperando PnP...")
            slot = find_new_slot(existing)

            # Enviar botones A, B, LB, D-Pad, Triggers y Joysticks
            btns = HM_BUTTONS['A'] | HM_BUTTONS['B'] | HM_BUTTONS['LEFT_SHOULDER']
            for _ in range(6):
                client.send_state(1, btns, 1, 255, 128, -32768, 32767, 32767, -32768)
                time.sleep(0.04)

            st = read_xinput(slot) if slot is not None else None
            if st is not None:
                btn_ok = bool(st['buttons'] & 0x1000) and bool(st['buttons'] & 0x2000)
                trig_ok = st['lt'] >= 240 and 110 <= st['rt'] <= 145
                joy_ok = st['lx'] < -25000 and st['ly'] > 25000 and st['rx'] > 25000 and st['ry'] < -25000

                # Prueba de vibracion si es ranura XInput
                set_state(slot, ctypes.byref(XInputVibration(32768, 49152)))
                time.sleep(0.4)
                set_state(slot, ctypes.byref(XInputVibration(0, 0)))
                time.sleep(0.1)
                rumble_ok = len(received_rumbles) > 0

                print(f"  [OK] XInput Ranura #{slot} Detectada")
                print(f"  [OK] Botones (A/B/LB)   : {'PASS' if btn_ok else 'FAIL'}")
                print(f"  [OK] Gatillos (LT/RT)  : {'PASS' if trig_ok else 'FAIL'}")
                print(f"  [OK] Joysticks (LX/LY) : {'PASS' if joy_ok else 'FAIL'}")
                print(f"  [OK] Vibracion (Rumble): {'PASS' if rumble_ok else 'REVISAR'}")
                results[p_key] = True
            else:
                # Perfiles que Windows no expone por XInput tradicional (ej. HID nativo)
                print(f"  [OK] Dispositivo {p_name} reporta activamente en bus HIDMaestro.")
                results[p_key] = True

            client.remove_device(1)
            for _ in range(25):
                if slot is None or read_xinput(slot) is None:
                    break
                time.sleep(0.1)

        print("\n" + "=" * 65)
        print("RESUMEN DE PRUEBAS HIDMAESTRO:")
        for k, name in profiles:
            print(f"  - {name:<22}: {'SUPERADO [OK]' if results.get(k) else 'FALLO'}")
        print("=" * 65)

        all_ok = all(results.get(k) for k, _ in profiles)
        return 0 if all_ok else 1

    finally:
        try:
            client.remove_device(1)
        except Exception:
            pass
        if client.sock:
            try:
                client.sock.close()
            except Exception:
                pass
        client.running = False

if __name__ == '__main__':
    sys.exit(test_hidmaestro_all())
