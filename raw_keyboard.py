"""
raw_keyboard.py - Dispatcher multiplataforma para teclados individuales.
En Windows utiliza raw_keyboard_win32 (Windows Raw Input API).
En Linux / macOS expone una interfaz compatible (fallback seguro).
"""

import sys
from typing import Callable, Dict, List, Optional, Set, Tuple

if sys.platform == "win32":
    from raw_keyboard_win32 import RawKeyboardManager, vk_to_friendly_name
else:
    class RawKeyboardManager:
        _instance = None

        @classmethod
        def get_instance(cls) -> "RawKeyboardManager":
            if cls._instance is None:
                cls._instance = RawKeyboardManager()
            return cls._instance

        def __init__(self):
            self.running = False

        def start(self):
            pass

        def stop(self):
            pass

        def refresh_devices(self) -> List[Dict]:
            return []

        def get_available_keyboards(self) -> List[Dict]:
            return []

        def get_pressed_keys(self, dev_id: str) -> Set[str]:
            return set()

        def start_capture(self, dev_id: str, callback: Callable[[str], None]):
            pass

        def cancel_capture(self):
            pass

    def vk_to_friendly_name(vkey: int, flags: int = 0) -> str:
        return f"Key: {vkey}"
