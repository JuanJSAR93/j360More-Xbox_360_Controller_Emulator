import os
import sys
import time
import ctypes
from ctypes import wintypes as w

# Add current dir to sys.path
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

def main():
    print("[*] Diagnosticando estados XInput iniciales...")
    init_states = get_xinput_states()
    print(f"    Ranuras XInput activas antes del test: {list(init_states.keys())}")

    client = ViiperClient()
    print("[*] Iniciando bus VIIPER...")
    if not client.start_bus():
        print("[!] No se pudo iniciar el bus VIIPER.")
        return 1

    print("[*] Anadiendo mando virtual Xbox One (GIP)...")
    if not client.add_device(0, 'xboxone'):
        print("[!] Error creando mando Xbox One GIP.")
        client.stop()
        return 1

    print("[+] Mando Xbox One GIP creado con exito. Esperando enumeracion PnP en Windows...")
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
        client.stop()
        return 1

    print(f"[+] Nueva ranura XInput detectada: Ranura #{new_slot}")
    print(f"    Estado inicial: {get_xinput_states()[new_slot]}")

    # Enviar pulsacion de Boton A
    print("[*] Enviando pulsacion de BOTON A + Gatillo Izquierdo (255)...")
    client.send_xboxone_state(0, XBOX_ONE_BUTTONS['A'], 255, 0, 0, 0, 0, 0)
    time.sleep(0.5)

    st_after_a = get_xinput_states().get(new_slot, {})
    print(f"    Estado XInput leido: {st_after_a}")
    btn_a_pressed = bool(st_after_a.get('buttons', 0) & 0x1000) # XINPUT_GAMEPAD_A = 0x1000
    lt_pressed = st_after_a.get('lt', 0) > 200

    print(f"    -> Boton A reconocido por XInput: {btn_a_pressed}")
    print(f"    -> Gatillo Izquierdo reconocido por XInput: {lt_pressed}")

    # Enviar estado neutral
    print("[*] Enviando estado neutral...")
    client.send_xboxone_state(0, 0, 0, 0, 0, 0, 0, 0)
    time.sleep(0.3)
    st_neutral = get_xinput_states().get(new_slot, {})
    print(f"    Estado XInput tras soltar: {st_neutral}")

    print("[*] Desconectando y liberando mando...")
    client.remove_device(0)
    time.sleep(1.0)
    client.stop()
    print("[+] Servidor VIIPER detenido y dispositivos liberados.")

    if btn_a_pressed and lt_pressed:
        print("\n>>> TEST GIP XINPUT: EXITO TOTAL (PASS) <<<")
        return 0
    else:
        print("\n>>> TEST GIP XINPUT: FALLO DE RECEPCION <<<")
        return 1

if __name__ == '__main__':
    sys.exit(main())
