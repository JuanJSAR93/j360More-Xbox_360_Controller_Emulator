import os
import sys
import time
import ctypes
from ctypes import wintypes as w

# Add current dir to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from viiper_backend import ViiperClient, XBOX_ONE_BUTTONS, XBOX_SERIES_BUTTONS

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

def get_xinput_states():
    try:
        xinput = ctypes.WinDLL("XInput1_4.dll")
    except Exception:
        xinput = ctypes.WinDLL("xinput9_1_0.dll")
    get_state = xinput.XInputGetState
    get_state.argtypes = [w.DWORD, ctypes.POINTER(XInputState)]
    get_state.restype = w.DWORD
    states = {}
    for i in range(4):
        st = XInputState()
        res = get_state(i, ctypes.byref(st))
        if res == 0:
            states[i] = {
                'packet': st.packet,
                'buttons': st.gamepad.buttons,
                'lt': st.gamepad.left_trigger,
                'rt': st.gamepad.right_trigger,
                'lx': st.gamepad.left_x,
                'ly': st.gamepad.left_y,
                'rx': st.gamepad.right_x,
                'ry': st.gamepad.right_y,
            }
    return states

def test_device_profile(client, dev_type, button_name, button_mask, trigger_side):
    print(f"\n==========================================")
    print(f"[*] INICIANDO PRUEBA PARA: {dev_type.upper()} (GIP)")
    print(f"==========================================")
    init_states = get_xinput_states()
    print(f"    Ranuras XInput activas antes del test: {list(init_states.keys())}")

    if not client.add_device(0, dev_type):
        print(f"[!] Error creando mando {dev_type} GIP.")
        return False

    print(f"[+] Mando {dev_type} GIP creado con exito. Esperando enumeracion PnP en Windows...")
    time.sleep(2.0)

    # Buscar ranura XInput nueva
    new_slot = None
    for _ in range(30):
        current_states = get_xinput_states()
        for slot_idx in current_states:
            if slot_idx not in init_states:
                new_slot = slot_idx
                break
        if new_slot is not None:
            break
        time.sleep(0.2)

    if new_slot is None:
        print("[!] No se detecto nueva ranura XInput tras la conexion.")
        print(f"    Ranuras actuales: {get_xinput_states()}")
        client.remove_device(0)
        return False

    print(f"[+] Nueva ranura XInput detectada: Ranura #{new_slot}")
    print(f"    Estado inicial: {get_xinput_states()[new_slot]}")

    # Enviar pulsación
    lt_val = 255 if trigger_side == 'lt' else 0
    rt_val = 255 if trigger_side == 'rt' else 0
    print(f"[*] Enviando pulsacion de BOTON {button_name} + Gatillo {trigger_side.upper()} (255)...")
    if dev_type == 'xboxone':
        client.send_xboxone_state(0, button_mask, lt_val, rt_val, 0, 0, 0, 0)
    else:
        client.send_xboxseries_state(0, button_mask, lt_val, rt_val, 0, 0, 0, 0)
    time.sleep(0.5)

    st_pressed = get_xinput_states().get(new_slot, {})
    print(f"    Estado XInput leido: {st_pressed}")

    # XINPUT masks: A=0x1000, B=0x2000
    expected_xinput_btn = 0x1000 if button_name == 'A' else 0x2000
    btn_pressed = bool(st_pressed.get('buttons', 0) & expected_xinput_btn)
    trig_pressed = st_pressed.get(trigger_side, 0) > 200

    print(f"    -> Boton {button_name} reconocido por XInput: {btn_pressed}")
    print(f"    -> Gatillo {trigger_side.upper()} reconocido por XInput: {trig_pressed}")

    # Enviar neutral
    print("[*] Enviando estado neutral...")
    if dev_type == 'xboxone':
        client.send_xboxone_state(0, 0, 0, 0, 0, 0, 0, 0)
    else:
        client.send_xboxseries_state(0, 0, 0, 0, 0, 0, 0, 0)
    time.sleep(0.3)

    print("[*] Desconectando y liberando mando...")
    client.remove_device(0)
    time.sleep(1.5)

    success = btn_pressed and trig_pressed
    if success:
        print(f"[+] PRUEBA DE {dev_type.upper()} SUPERADA CON EXITO.")
    else:
        print(f"[!] PRUEBA DE {dev_type.upper()} FALLIDA.")
    return success

def main():
    client = ViiperClient()
    print("[*] Iniciando bus VIIPER...")
    if not client.start_bus():
        print("[!] No se pudo iniciar el bus VIIPER.")
        return 1

    ok_one = False
    ok_series = False
    try:
        ok_one = test_device_profile(client, 'xboxone', 'A', XBOX_ONE_BUTTONS['A'], 'lt')
        time.sleep(1.0)
        ok_series = test_device_profile(client, 'xboxseries', 'B', XBOX_SERIES_BUTTONS['B'], 'rt')
    finally:
        client.stop()
        print("[+] Servidor VIIPER detenido y recursos liberados.")

    if ok_one and ok_series:
        print("\n>>> TEST GIP XINPUT (XBOX ONE & XBOX SERIES): EXITO TOTAL (PASS) <<<")
        return 0
    else:
        print(f"\n>>> TEST GIP XINPUT: FALLO (XboxOne={ok_one}, XboxSeries={ok_series}) <<<")
        return 1

if __name__ == '__main__':
    sys.exit(main())
