import os
import sys
import time
import json
import signal
import argparse
from typing import Dict, List, Optional, Any
try:
    import vgamepad as vg
    HAS_VGAMEPAD = True
except Exception:
    vg = None
    HAS_VGAMEPAD = False
from pynput import keyboard

BUTTON_MAP = {
    "DPAD_UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
    "DPAD_DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
    "DPAD_LEFT": vg.XUSB_GAMEPAD_DPAD_LEFT if hasattr(vg, "XUSB_GAMEPAD_DPAD_LEFT") else vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
    "DPAD_RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
    "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
    "BACK": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
    "LEFT_THUMB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
    "RIGHT_THUMB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
    "LEFT_SHOULDER": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
    "RIGHT_SHOULDER": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
    "GUIDE": vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
    "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
    "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
    "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
    "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
}

SPECIAL_KEYS_MAP = {
    keyboard.Key.up: "up",
    keyboard.Key.down: "down",
    keyboard.Key.left: "left",
    keyboard.Key.right: "right",
    keyboard.Key.space: "space",
    keyboard.Key.enter: "enter",
    keyboard.Key.tab: "tab",
    keyboard.Key.shift: "shift",
    keyboard.Key.ctrl_l: "ctrl",
    keyboard.Key.ctrl_r: "ctrl",
    keyboard.Key.alt_l: "alt",
    keyboard.Key.alt_r: "alt",
    keyboard.Key.backspace: "backspace",
    keyboard.Key.esc: "esc"
}

class Xbox8Emulator:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.gamepads: Dict[int, vg.VX360Gamepad] = {}
        self.key_to_actions: Dict[str, List[tuple]] = {}
        self.running = False
        self.keyboard_listener: Optional[keyboard.Listener] = None

        self.load_config()
        self.initialize_gamepads()
        self.build_key_mappings()

    def load_config(self):
        print(f"[*] Cargando archivo de configuracion: {self.config_path}")
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"No se encontro el archivo de configuracion en: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8-sig") as f:
            self.config = json.load(f)
        print(f"[+] Configuracion cargada exitosamente. Version: {self.config.get('version', 'N/A')}")

    def initialize_gamepads(self):
        controllers_cfg = self.config.get("controllers", {})
        print("\n[*] Conectando mandos virtuales Xbox 360 al bus ViGEmBus...")

        max_ctrls = self.config.get("max_controllers", 12)
        for idx in range(1, max_ctrls + 1):
            str_idx = str(idx)
            cfg = controllers_cfg.get(str_idx, {"enabled": True, "name": f"Jugador {idx}"})
            if cfg.get("enabled", True):
                try:
                    gamepad = vg.VX360Gamepad()
                    # Enviar estado neutro inicial
                    gamepad.reset()
                    gamepad.update()
                    self.gamepads[idx] = gamepad
                    print(f"  [+] Control #{idx} ({cfg.get('name', f'Player {idx}')}): CONECTADO")
                except Exception as e:
                    print(f"  [-] Error creando Control #{idx}: {e}")
            else:
                print(f"  [-] Control #{idx} ({cfg.get('name', f'Player {idx}')}): DESHABILITADO en JSON")

        print(f"[+] Total de controles virtuales activos: {len(self.gamepads)}/{max_ctrls}\n")

    def build_key_mappings(self):
        self.key_to_actions.clear()
        controllers_cfg = self.config.get("controllers", {})

        for str_idx, cfg in controllers_cfg.items():
            try:
                pad_id = int(str_idx)
            except ValueError:
                continue

            if pad_id not in self.gamepads:
                continue

            k_map = cfg.get("keyboard_mapping", {})
            for key_str, btn_name in k_map.items():
                clean_key = str(key_str).lower().strip()
                clean_btn = str(btn_name).upper().strip()
                if clean_btn in BUTTON_MAP:
                    if clean_key not in self.key_to_actions:
                        self.key_to_actions[clean_key] = []
                    self.key_to_actions[clean_key].append((pad_id, clean_btn))
                else:
                    print(f"  [!] Advertencia: Boton '{btn_name}' no reconocido para Control #{pad_id}")

    def _normalize_key(self, key) -> Optional[str]:
        if isinstance(key, keyboard.KeyCode):
            if key.char:
                return key.char.lower()
            elif hasattr(key, 'vk') and key.vk is not None:
                # Soporte para teclas del Numpad (VK_NUMPAD0 a VK_NUMPAD9)
                if 96 <= key.vk <= 105:
                    return f"num_{key.vk - 96}"
            return None
        elif key in SPECIAL_KEYS_MAP:
            return SPECIAL_KEYS_MAP[key]
        return None

    def press_button(self, pad_id: int, button_name: str):
        if pad_id in self.gamepads and button_name in BUTTON_MAP:
            pad = self.gamepads[pad_id]
            pad.press_button(button=BUTTON_MAP[button_name])
            pad.update()

    def release_button(self, pad_id: int, button_name: str):
        if pad_id in self.gamepads and button_name in BUTTON_MAP:
            pad = self.gamepads[pad_id]
            pad.release_button(button=BUTTON_MAP[button_name])
            pad.update()

    def pulse_button(self, pad_id: int, button_name: str, duration: float = 0.15):
        if pad_id in self.gamepads and button_name in BUTTON_MAP:
            self.press_button(pad_id, button_name)
            time.sleep(duration)
            self.release_button(pad_id, button_name)

    def on_key_press(self, key):
        k_str = self._normalize_key(key)
        if not k_str:
            return
        if k_str == "esc":
            print("\n[*] Tecla ESC detectada. Deteniendo escucha...")
            self.stop()
            return

        actions = self.key_to_actions.get(k_str)
        if actions:
            for pad_id, btn_name in actions:
                self.press_button(pad_id, btn_name)
                print(f"[EVENTO] Tecla '{k_str}' -> Control #{pad_id} presiona [{btn_name}]")

    def on_key_release(self, key):
        k_str = self._normalize_key(key)
        if not k_str:
            return
        actions = self.key_to_actions.get(k_str)
        if actions:
            for pad_id, btn_name in actions:
                self.release_button(pad_id, btn_name)

    def run_self_test(self):
        print("=" * 60)
        print(" INICIANDO PRUEBA DE DIAGNOSTICO AUTOMATICA (8 MANDOS)")
        print(" TIP: Puedes abrir 'joy.cpl' en Windows para ver la respuesta")
        print("=" * 60)

        controllers_cfg = self.config.get("controllers", {})
        for pad_id, pad in sorted(self.gamepads.items()):
            cfg = controllers_cfg.get(str(pad_id), {})
            name = cfg.get("name", f"Jugador {pad_id}")
            test_sequence = cfg.get("test_sequence", ["A", "B", "X", "Y"])

            print(f"\n--- Probando Control #{pad_id} ({name}) ---")
            for btn in test_sequence:
                if btn in BUTTON_MAP:
                    print(f"  -> Pulsando boton [{btn}]...")
                    self.pulse_button(pad_id, btn, duration=0.15)
                    time.sleep(0.08)

        print("\n[+] Prueba de diagnostico finalizada con exito en los 8 mandos.")

    def start_listener(self):
        print("=" * 60)
        print(" ESCUCHANDO EVENTOS DE TECLADO SEGUN config_mapping.json")
        print(" Presiona las teclas asignadas para controlar los 8 mandos.")
        print(" Presiona ESC o Ctrl+C para salir.")
        print("=" * 60)

        self.running = True
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_key_press,
            on_release=self.on_key_release
        )
        self.keyboard_listener.start()

        try:
            while self.running and self.keyboard_listener.is_alive():
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n[*] Interrupcion por usuario (Ctrl+C).")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        if self.keyboard_listener and self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()

        print("\n[*] Desconectando y liberando mandos virtuales...")
        for pad_id, pad in list(self.gamepads.items()):
            try:
                pad.reset()
                pad.update()
            except Exception:
                pass
        self.gamepads.clear()
        print("[+] Todos los mandos virtuales han sido liberados limpiamente.")

def main():
    parser = argparse.ArgumentParser(description="j360More - Emulador Multi-Gamepad (1 a 12 Mandos) con ViGEmBus")
    parser.add_argument("--gui", action="store_true", help="Lanzar la interfaz gráfica j360More (Por defecto)")
    parser.add_argument("--config", default="config_mapping.json", help="Ruta al archivo JSON de mapeo")
    parser.add_argument("--test", action="store_true", help="Ejecutar prueba automática de botones en los 8 mandos por consola")
    parser.add_argument("--hold", type=int, default=0, help="Mantener activos los mandos durante N segundos antes de salir (modo test)")
    parser.add_argument("--listen", action="store_true", help="Escuchar teclas de teclado por consola para activar botones de mandos")

    args = parser.parse_args()

    # Si se pasa --gui o no se pasa ningún argumento de consola, lanzar la interfaz gráfica
    if args.gui or (not args.test and not args.listen):
        try:
            import gui_app
            gui_app.run_gui()
            return
        except Exception as e:
            print(f"[!] Error iniciando la interfaz gráfica: {e}")
            print("[*] Cambiando a modo consola...")

    # Modo Consola
    config_file = args.config
    if not os.path.isabs(config_file):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_file = os.path.join(script_dir, config_file)

    try:
        emulator = Xbox8Emulator(config_file)
    except Exception as e:
        print(f"[!] Error inicializando el emulador: {e}")
        sys.exit(1)

    # Manejar señales para desconexión limpia
    def sig_handler(signum, frame):
        emulator.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, sig_handler)

    try:
        if args.test:
            emulator.run_self_test()
            if args.hold > 0:
                print(f"\n[*] Manteniendo mandos conectados por {args.hold} segundos...")
                time.sleep(args.hold)
            emulator.stop()
        else:
            emulator.start_listener()
    except KeyboardInterrupt:
        emulator.stop()

if __name__ == "__main__":
    main()
