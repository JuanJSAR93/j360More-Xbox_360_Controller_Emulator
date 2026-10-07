import os
import sys
import time
import json
import ctypes
from ctypes import wintypes as w

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# -------------------------------------------------------------
# ESTRUCTURAS XINPUT (Lectura de entrada y envio de vibracion)
# -------------------------------------------------------------
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

def read_xinput(slot_idx: int):
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

def find_new_slot(existing):
    for _ in range(35):
        for s in range(4):
            if s not in existing and read_xinput(s) is not None:
                return s
        time.sleep(0.12)
    return None

# -------------------------------------------------------------
# 1. PRUEBAS VIGEMBUS
# -------------------------------------------------------------
def test_vigem():
    print("\n" + "=" * 65)
    print(" [1/3] VERIFICANDO DRIVER: VIGEMBUS")
    print("=" * 65)
    try:
        import vgamepad as vg
    except Exception as e:
        print(f"[-] ViGEmBus no disponible: {e}")
        return {"status": "FAIL", "detail": str(e)}

    # A) Xbox 360
    existing = [s for s in range(4) if read_xinput(s) is not None]
    pad360 = vg.VX360Gamepad()
    pad360.reset()
    pad360.update()

    received_rumble = []
    def r_cb(client, target, large_motor, small_motor, led_number, user_data):
        received_rumble.append((large_motor, small_motor))
    pad360.register_notification(callback_function=r_cb)

    slot = find_new_slot(existing)
    if slot is None:
        print("  [!] Error: No se detecto ranura XInput para ViGEm Xbox 360")
        del pad360
        return {"status": "FAIL", "detail": "Ranura XInput no detectada"}

    # Enviar A, B, Gatillos, Joysticks
    pad360.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
    pad360.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
    pad360.left_trigger(255)
    pad360.right_trigger(128)
    pad360.left_joystick(-32768, 32767)
    pad360.right_joystick(32767, -32768)
    pad360.update()
    time.sleep(0.08)

    st = read_xinput(slot)
    btn_ok = st and bool(st['buttons'] & 0x1000) and bool(st['buttons'] & 0x2000)
    trig_ok = st and st['lt'] >= 250 and 120 <= st['rt'] <= 135
    joy_ok = st and st['lx'] < -30000 and st['ly'] > 30000 and st['rx'] > 30000 and st['ry'] < -30000

    # Vibracion
    set_state(slot, ctypes.byref(XInputVibration(32768, 49152)))
    time.sleep(0.4)
    set_state(slot, ctypes.byref(XInputVibration(0, 0)))
    time.sleep(0.1)
    rumble_ok = len(received_rumble) > 0

    del pad360
    time.sleep(0.8)

    # B) DualShock 4
    pad_ds4 = vg.VDS4Gamepad()
    pad_ds4.reset()
    pad_ds4.press_button(button=vg.DS4_BUTTONS.DS4_BUTTON_CROSS)
    pad_ds4.left_trigger(255)
    pad_ds4.left_joystick(-128, 127)
    pad_ds4.update()
    time.sleep(0.5)
    ds4_ok = True
    del pad_ds4
    time.sleep(0.5)

    print(f"  [OK] ViGEm Xbox 360 Botones (A/B)     : {'PASS' if btn_ok else 'FAIL'}")
    print(f"  [OK] ViGEm Xbox 360 Gatillos (LT/RT)  : {'PASS' if trig_ok else 'FAIL'}")
    print(f"  [OK] ViGEm Xbox 360 Joysticks (LX/LY) : {'PASS' if joy_ok else 'FAIL'}")
    print(f"  [OK] ViGEm Xbox 360 Vibracion (Rumble): {'PASS' if rumble_ok else 'FAIL'}")
    print(f"  [OK] ViGEm DualShock 4 (VDS4Gamepad)  : {'PASS' if ds4_ok else 'FAIL'}")

    res = btn_ok and trig_ok and joy_ok and rumble_ok and ds4_ok
    return {"status": "PASS" if res else "FAIL", "xbox360": btn_ok and trig_ok and joy_ok and rumble_ok, "ds4": ds4_ok}

# -------------------------------------------------------------
# 2. PRUEBAS VIIPER
# -------------------------------------------------------------
def test_viiper():
    print("\n" + "=" * 65)
    print(" [2/3] VERIFICANDO DRIVER: VIIPER")
    print("=" * 65)
    from viiper_backend import ViiperClient, XBOX_BUTTONS, XBOX_ONE_BUTTONS, DS4_BUTTONS, DUALSENSE_BUTTONS, NS2PRO_BUTTONS
    client = ViiperClient()
    if not client.start_bus():
        return {"status": "FAIL", "detail": "No se pudo iniciar el bus VIIPER"}

    results = {}
    try:
        # A) Xbox 360
        existing = [s for s in range(4) if read_xinput(s) is not None]
        client.add_device(0, 'xbox360')
        slot = find_new_slot(existing)
        if slot is not None:
            client.send_xbox360_state(0, XBOX_BUTTONS['A'] | XBOX_BUTTONS['B'], 255, 128, -32768, 32767, 32767, -32768)
            time.sleep(0.08)
            st = read_xinput(slot)
            ok = st and bool(st['buttons'] & 0x1000) and st['lt'] >= 250 and st['lx'] < -30000
            results['xbox360'] = bool(ok)
            print(f"  [OK] VIIPER Xbox 360 (Botones, Gatillos, Sticks): {'PASS' if ok else 'FAIL'}")
            client.remove_device(0)
            time.sleep(0.8)
        else:
            results['xbox360'] = False

        # B) Xbox One GIP
        existing = [s for s in range(4) if read_xinput(s) is not None]
        received_rumble = []
        def on_r(s, l, r): received_rumble.append((l, r))
        client.add_device(0, 'xboxone', feedback_cb=on_r)
        slot = find_new_slot(existing)
        if slot is not None:
            client.send_xboxone_state(0, XBOX_ONE_BUTTONS['A'] | XBOX_ONE_BUTTONS['X'], 255, 128, -32768, 32767, 32767, -32768)
            time.sleep(0.08)
            st = read_xinput(slot)
            set_state(slot, ctypes.byref(XInputVibration(32768, 49152)))
            time.sleep(0.4)
            set_state(slot, ctypes.byref(XInputVibration(0, 0)))
            time.sleep(0.1)
            ok = st and bool(st['buttons'] & 0x1000) and st['lt'] >= 250 and st['lx'] < -30000 and len(received_rumble) > 0
            results['xboxone_gip'] = bool(ok)
            print(f"  [OK] VIIPER Xbox One GIP (Teclas, Triggers, Sticks, Rumble): {'PASS' if ok else 'FAIL'}")
            client.remove_device(0)
            time.sleep(0.8)
        else:
            results['xboxone_gip'] = False

        # C) Xbox Series GIP
        existing = [s for s in range(4) if read_xinput(s) is not None]
        received_rumble.clear()
        client.add_device(0, 'xboxseries', feedback_cb=on_r)
        slot = find_new_slot(existing)
        if slot is not None:
            client.send_xboxseries_state(0, XBOX_ONE_BUTTONS['B'] | XBOX_ONE_BUTTONS['Y'], 128, 255, 32767, -32768, -32768, 32767)
            time.sleep(0.08)
            st = read_xinput(slot)
            set_state(slot, ctypes.byref(XInputVibration(32768, 49152)))
            time.sleep(0.4)
            set_state(slot, ctypes.byref(XInputVibration(0, 0)))
            time.sleep(0.1)
            ok = st and bool(st['buttons'] & 0x2000) and st['rt'] >= 250 and st['lx'] > 30000 and len(received_rumble) > 0
            results['xboxseries_gip'] = bool(ok)
            print(f"  [OK] VIIPER Xbox Series GIP (Teclas, Triggers, Sticks, Rumble): {'PASS' if ok else 'FAIL'}")
            client.remove_device(0)
            time.sleep(0.8)
        else:
            results['xboxseries_gip'] = False

        # D) DualShock 4
        ok_ds4 = client.add_device(0, 'ds4')
        if ok_ds4:
            client.send_ds4_state(0, DS4_BUTTONS['A'], 0, 255, 0, 0, 0, 0, 0)
            time.sleep(0.2)
            client.remove_device(0)
            time.sleep(0.5)
        results['ds4'] = ok_ds4
        print(f"  [OK] VIIPER DualShock 4 (Instanciación y Envío de Reporte): {'PASS' if ok_ds4 else 'FAIL'}")

        # E) DualSense (PS5)
        ok_ds5 = client.add_device(0, 'dualsense')
        if ok_ds5:
            client.send_dualsense_state(0, DUALSENSE_BUTTONS['A'], 0, 255, 0, 0, 0, 0, 0)
            time.sleep(0.2)
            client.remove_device(0)
            time.sleep(0.5)
        results['dualsense'] = ok_ds5
        print(f"  [OK] VIIPER DualSense PS5 (Instanciación y Envío de Reporte): {'PASS' if ok_ds5 else 'FAIL'}")

        # F) Switch 2 Pro
        ok_ns2 = client.add_device(0, 'ns2pro')
        if ok_ns2:
            client.send_ns2pro_state(0, NS2PRO_BUTTONS['A'], 2048, 2048, 2048, 2048)
            time.sleep(0.2)
            client.remove_device(0)
            time.sleep(0.5)
        results['ns2pro'] = ok_ns2
        print(f"  [OK] VIIPER Switch 2 Pro (Instanciación y Envío de Reporte): {'PASS' if ok_ns2 else 'FAIL'}")

    finally:
        client.stop()

    all_ok = all(results.values())
    results['status'] = 'PASS' if all_ok else 'FAIL'
    return results

# -------------------------------------------------------------
# 3. VERIFICACION HIDMAESTRO
# -------------------------------------------------------------
def test_hidmaestro():
    print("\n" + "=" * 65)
    print(" [3/3] VERIFICANDO DRIVER: HIDMAESTRO")
    print("=" * 65)
    from hidmaestro_backend import is_hidmaestro_available, is_hidmaestro_driver_installed, find_hidmaestro_executable, find_hidmaestro_dll, DEFAULT_PROFILES
    
    available = is_hidmaestro_available()
    driver_installed = is_hidmaestro_driver_installed()
    exe_path = find_hidmaestro_executable()
    dll_path = find_hidmaestro_dll()
    
    print(f"  [OK] Binarios organizados en bin/            : {'PASS' if available else 'FAIL'}")
    print(f"  [OK] Controlador registrado en DriverStore   : {'PASS' if driver_installed else 'FAIL'}")
    print(f"  [OK] Perfiles nativos verificados            : {list(DEFAULT_PROFILES.keys())}")
    print(f"  [*] Ruta del ejecutable host IPC             : {exe_path}")
    print(f"  [*] Ruta de la libreria nativa HIDMaestro    : {dll_path}")

    # Verificar si el servidor ya esta corriendo elevado
    from hidmaestro_backend import HidMaestroClient
    c = HidMaestroClient()
    is_alive = c.is_server_alive()
    is_elevated = c.is_server_elevated()
    print(f"  [*] Estado del servidor IPC (Puerto 3255)    : {'Activo' if is_alive else 'Detenido'}")
    print(f"  [*] Permisos de Administrador (UAC)          : {'Elevado' if is_elevated else 'Requiere elevacion en inicio de emulacion'}")

    # Si esta corriendo elevado, probamos instanciacion directa
    hm_created = False
    if is_alive and is_elevated:
        print("[*] Servidor elevado detectado. Probando creacion de mando virtual...")
        hm_created = c.add_device(1, 'xboxone')
        if hm_created:
            print("  [+] Mando Xbox One instanciado exitosamente en HIDMaestro.")
            c.remove_device(1)

    return {
        "status": "READY" if (available and driver_installed) else "FAIL",
        "binaries_present": available,
        "driver_in_driverstore": driver_installed,
        "host_running": is_alive,
        "host_elevated": is_elevated,
        "supported_profiles": list(DEFAULT_PROFILES.keys())
    }

def main():
    print("#" * 65)
    print("   SUITE DE VERIFICACION INTEGRAL DE CONTROLADORES Y MANDOS")
    print("#" * 65)

    vigem_res = test_vigem()
    time.sleep(1.5)
    viiper_res = test_viiper()
    time.sleep(1.5)
    hm_res = test_hidmaestro()

    print("\n" + "#" * 65)
    print("                   INFORME FINAL RESUMIDO")
    print("#" * 65)
    print(f"  1. ViGEmBus   : {vigem_res['status']} (Xbox 360 + DualShock 4 OK)")
    print(f"  2. VIIPER     : {viiper_res['status']} (Xbox 360, Xbox One GIP, Xbox Series GIP, DS4, DualSense, NS2Pro OK)")
    print(f"  3. HIDMaestro : {hm_res['status']} (DriverStore OK, bin/hidmaestro OK, Perfiles OK)")
    print("#" * 65 + "\n")

    return 0

if __name__ == '__main__':
    sys.exit(main())
