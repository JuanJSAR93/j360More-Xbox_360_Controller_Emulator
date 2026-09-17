import os
import sys
import json
import time
import math
import io
import threading
import subprocess
import webbrowser
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

try:
    import resvg_py
except ImportError:
    resvg_py = None

from driver_manager import DriverManager
from input_devices import DeviceManager
from emulator_engine import EmulatorEngine, apply_axis_calibration, apply_trigger_calibration
from i18n import get_text, get_target_name, SUPPORTED_LANGUAGES

APP_VERSION = "1.2.0"

def parse_version(v_str: str) -> tuple:
    if not v_str:
        return (0,)
    clean = v_str.strip().lstrip("vV")
    parts = []
    for p in clean.split("."):
        num = ""
        for ch in p:
            if ch.isdigit():
                num += ch
            else:
                break
        if num:
            parts.append(int(num))
        else:
            break
    return tuple(parts) if parts else (0,)

if getattr(sys, "frozen", False):
    EXE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", EXE_DIR)
    CONFIG_FILE = os.path.join(EXE_DIR, "config_mapping.json")
    ASSETS_DIR = os.path.join(BUNDLE_DIR, "assets") if os.path.exists(os.path.join(BUNDLE_DIR, "assets")) else os.path.join(EXE_DIR, "assets")
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    CONFIG_FILE = os.path.join(SCRIPT_DIR, "config_mapping.json")
    ASSETS_DIR = os.path.join(SCRIPT_DIR, "assets")

CONTROLLER_SVG_PATH = os.path.join(ASSETS_DIR, "controller.svg")
CONTROLLER_CACHE_PNG = os.path.join(ASSETS_DIR, "controller_render.png")
CONTROLLER_HIRES_PNG = os.path.join(ASSETS_DIR, "controller_hires.png")
CONTROLLER_PNG_FALLBACK = os.path.join(ASSETS_DIR, "controller.png")
ICON_SVG_PATH = os.path.join(ASSETS_DIR, "icon.svg")
ICON_PNG_PATH = os.path.join(ASSETS_DIR, "icon.png")
ICON_ICO_PATH = os.path.join(ASSETS_DIR, "icon.ico")

INPUT_OPTIONS = [
    "-- Ninguno --",
    "Button 1", "Button 2", "Button 3", "Button 4",
    "Button 5", "Button 6", "Button 7", "Button 8",
    "Button 9", "Button 10", "Button 11", "Button 12",
    "Button 13", "Button 14", "Button 15", "Button 16",
    "Axis 1", "IAxis 1", "Axis 2", "IAxis 2",
    "Axis 3", "IAxis 3", "Axis 4", "IAxis 4",
    "Axis 5", "IAxis 5", "Axis 6", "IAxis 6",
    "POV 1 Up", "POV 1 Down", "POV 1 Left", "POV 1 Right",
    "Tecla: w", "Tecla: s", "Tecla: a", "Tecla: d",
    "Tecla: j", "Tecla: k", "Tecla: u", "Tecla: i",
    "Tecla: q", "Tecla: e", "Tecla: space", "Tecla: enter",
    "Tecla: up", "Tecla: down", "Tecla: left", "Tecla: right"
]

# Coordenadas relativas en el canvas para la imagen renderizada a 350x275
HITBOXES = {
    "A": (287.6, 154.9, 16.0),
    "B": (311.5, 129.4, 16.0),
    "X": (259.1, 129.4, 16.0),
    "Y": (287.6, 105.5, 16.0),
    "GUIDE": (176.5, 134.1, 22.0),
    "BACK": (136.4, 136.8, 14.0),
    "START": (214.9, 136.8, 14.0),
    "LEFT_SHOULDER": (60.0, 56.0, 16.0),
    "RIGHT_SHOULDER": (290.0, 56.0, 16.0),
    "LEFT_TRIGGER": (87.0, 42.0, 16.0),
    "RIGHT_TRIGGER": (263.0, 42.0, 16.0),
}

CANVAS_POINTS = {
    "LEFT_TRIGGER": (87.0, 42.0, 14),
    "LEFT_SHOULDER": (60.0, 56.0, 14),
    "RIGHT_TRIGGER": (263.0, 42.0, 14),
    "RIGHT_SHOULDER": (290.0, 56.0, 14),
    "LEFT_STICK_UP": (63.9, 124.0, 7),
    "LEFT_STICK_DOWN": (63.9, 156.4, 7),
    "LEFT_STICK_LEFT": (47.9, 140.2, 7),
    "LEFT_STICK_RIGHT": (79.9, 140.2, 7),
    "LEFT_THUMB": (63.9, 140.2, 8),
    "RIGHT_STICK_UP": (224.4, 173.4, 7),
    "RIGHT_STICK_DOWN": (224.4, 205.8, 7),
    "RIGHT_STICK_LEFT": (208.4, 189.6, 7),
    "RIGHT_STICK_RIGHT": (240.4, 189.6, 7),
    "RIGHT_THUMB": (224.4, 189.6, 8),
    "DPAD_UP": (122.5, 175.0, 9),
    "DPAD_DOWN": (122.5, 205.0, 9),
    "DPAD_LEFT": (108.0, 189.6, 9),
    "DPAD_RIGHT": (137.0, 189.6, 9),
    "BACK": (136.4, 136.8, 9),
    "GUIDE": (176.5, 134.1, 15),
    "START": (214.9, 136.8, 9),
    "A": (287.6, 154.9, 11),
    "B": (311.5, 129.4, 11),
    "X": (259.1, 129.4, 11),
    "Y": (287.6, 105.5, 11),
}

def map_target_to_canvas_key(target: str) -> str:
    """Convierte el nombre del destino del mapeo a la clave del componente visual en el canvas."""
    if target == "LEFT_STICK_X":
        return "LEFT_STICK_RIGHT"
    if target == "LEFT_STICK_Y":
        return "LEFT_STICK_UP"
    if target == "RIGHT_STICK_X":
        return "RIGHT_STICK_RIGHT"
    if target == "RIGHT_STICK_Y":
        return "RIGHT_STICK_UP"
    return target

TARGET_NAMES_ES = {
    "A": "Botón A",
    "B": "Botón B",
    "X": "Botón X",
    "Y": "Botón Y",
    "GUIDE": "Botón Guía (Xbox)",
    "BACK": "Botón Back / Selec",
    "START": "Botón Start",
    "LEFT_THUMB": "Stick Izq. Botón (L3)",
    "RIGHT_THUMB": "Stick Der. Botón (R3)",
    "LEFT_STICK_X": "Stick Izq. Eje X",
    "LEFT_STICK_Y": "Stick Izq. Eje Y",
    "LEFT_STICK_UP": "Stick Izq. Arriba",
    "LEFT_STICK_DOWN": "Stick Izq. Abajo",
    "LEFT_STICK_LEFT": "Stick Izq. Izquierda",
    "LEFT_STICK_RIGHT": "Stick Izq. Derecha",
    "RIGHT_STICK_X": "Stick Der. Eje X",
    "RIGHT_STICK_Y": "Stick Der. Eje Y",
    "RIGHT_STICK_UP": "Stick Der. Arriba",
    "RIGHT_STICK_DOWN": "Stick Der. Abajo",
    "RIGHT_STICK_LEFT": "Stick Der. Izquierda",
    "RIGHT_STICK_RIGHT": "Stick Der. Derecha",
    "DPAD_UP": "D-Pad Arriba",
    "DPAD_DOWN": "D-Pad Abajo",
    "DPAD_LEFT": "D-Pad Izquierda",
    "DPAD_RIGHT": "D-Pad Derecha",
    "LEFT_SHOULDER": "Bumper Izq. (LB)",
    "RIGHT_SHOULDER": "Bumper Der. (RB)",
    "LEFT_TRIGGER": "Gatillo Izq. (LT)",
    "RIGHT_TRIGGER": "Gatillo Der. (RT)",
}

DEFAULT_MAPPINGS = {
    "LEFT_TRIGGER": "-- Ninguno --",
    "LEFT_SHOULDER": "-- Ninguno --",
    "BACK": "-- Ninguno --",
    "START": "-- Ninguno --",
    "GUIDE": "-- Ninguno --",
    "LEFT_STICK_X": "-- Ninguno --",
    "LEFT_STICK_Y": "-- Ninguno --",
    "LEFT_STICK_UP": "-- Ninguno --",
    "LEFT_STICK_DOWN": "-- Ninguno --",
    "LEFT_STICK_LEFT": "-- Ninguno --",
    "LEFT_STICK_RIGHT": "-- Ninguno --",
    "LEFT_THUMB": "-- Ninguno --",
    "RIGHT_TRIGGER": "-- Ninguno --",
    "RIGHT_SHOULDER": "-- Ninguno --",
    "Y": "-- Ninguno --",
    "X": "-- Ninguno --",
    "B": "-- Ninguno --",
    "A": "-- Ninguno --",
    "RIGHT_STICK_X": "-- Ninguno --",
    "RIGHT_STICK_Y": "-- Ninguno --",
    "RIGHT_STICK_UP": "-- Ninguno --",
    "RIGHT_STICK_DOWN": "-- Ninguno --",
    "RIGHT_STICK_LEFT": "-- Ninguno --",
    "RIGHT_STICK_RIGHT": "-- Ninguno --",
    "RIGHT_THUMB": "-- Ninguno --",
    "DPAD_UP": "-- Ninguno --",
    "DPAD_DOWN": "-- Ninguno --",
    "DPAD_LEFT": "-- Ninguno --",
    "DPAD_RIGHT": "-- Ninguno --"
}

DEFAULT_CALIBRATION = {
    "left_trigger": {"deadzone": 0, "anti_deadzone": 0, "sensitivity": 0, "invert": False},
    "right_trigger": {"deadzone": 0, "anti_deadzone": 0, "sensitivity": 0, "invert": False},
    "left_stick": {"deadzone": 8, "anti_deadzone": 0, "sensitivity": 0, "invert_x": False, "invert_y": False},
    "right_stick": {"deadzone": 8, "anti_deadzone": 0, "sensitivity": 0, "invert_x": False, "invert_y": False}
}

class J360MoreApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.config = self.load_config()
        self.root.title(self.t("app_title"))
        self._setup_app_icon()

        # Tamaño balanceado donde todo es visible cómodamente sin cortes
        self.root.geometry("980x615")
        self.root.resizable(False, False)

        self.driver_manager = DriverManager(self.config)
        self.device_manager = DeviceManager(self.driver_manager)
        self.engine = EmulatorEngine(self.device_manager)
        self.engine.set_config(self.config)

        self.recording_target = None
        self.available_devices = []
        self.tab_frames = {}
        self.tab_widgets = {}

        self.style = ttk.Style()
        try:
            self.style.theme_use("vista")
        except Exception:
            pass

        self._load_assets()
        self._build_ui()
        self._refresh_all_devices()
        self.device_manager.add_on_devices_changed_callback(lambda devs: self.root.after(0, self._on_devices_hotplugged, devs))

        # Comprobar estado de drivers (ViGEmBus y aviso leve de HidHide)
        self.root.after(200, self._check_system_drivers)

        # Verificacion asincrona de nueva version (una unica vez al iniciar)
        self._update_checked = False
        self._available_update_version = None
        self.root.after(1500, self._check_update_once)

        self.root.bind("<KeyPress>", self._on_key_press)
        self.root.bind("<KeyRelease>", self._on_key_release)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.root.after(30, self._update_loop)

    def t(self, key: str, **kwargs) -> str:
        lang = self.config.get("language", "es")
        return get_text(lang, key, **kwargs)

    def target_name(self, target: str) -> str:
        lang = self.config.get("language", "es")
        return get_target_name(lang, target)

    def _toggle_language(self):
        codes = list(SUPPORTED_LANGUAGES.keys())
        cur = self.config.get("language", "es")
        idx = codes.index(cur) if cur in codes else 0
        self.config["language"] = codes[(idx + 1) % len(codes)]
        self.save_config(silent=True)
        self._update_ui_texts()

    def _update_ui_texts(self):
        max_ctrls = self.config.get("max_controllers", 8)
        self.root.title(self.t("app_title"))
        if hasattr(self, "title_lbl"):
            self.title_lbl.config(text=self.t("header_title", count=max_ctrls))
        if hasattr(self, "btn_devices"):
            self.btn_devices.config(text=self.t("btn_devices"))
        if hasattr(self, "btn_settings"):
            self.btn_settings.config(text=self.t("btn_settings"))
        if hasattr(self, "btn_joy_cpl"):
            self.btn_joy_cpl.config(text=self.t("btn_joy_cpl"))
        if hasattr(self, "btn_save"):
            self.btn_save.config(text=self.t("btn_save"))
        if hasattr(self, "btn_reset"):
            self.btn_reset.config(text=self.t("btn_reset"))

        if hasattr(self, "engine") and self.engine.is_running:
            if hasattr(self, "status_text_lbl"):
                self.status_text_lbl.config(text=self.t("status_active"))
            if hasattr(self, "btn_toggle_emu"):
                self.btn_toggle_emu.config(text=self.t("btn_stop_emu"))
        else:
            if hasattr(self, "status_text_lbl"):
                self.status_text_lbl.config(text=self.t("status_stopped"))
            if hasattr(self, "btn_toggle_emu"):
                self.btn_toggle_emu.config(text=self.t("btn_start_emu"))

        if hasattr(self, "lbl_version"):
            if getattr(self, "_available_update_version", None):
                alert_text = self.t("new_version_available", ver=self._available_update_version)
                self.lbl_version.config(text=f"v{APP_VERSION}  {alert_text}")
            else:
                self.lbl_version.config(text=f"v{APP_VERSION}")

        self._rebuild_tabs(max_ctrls)

    def _setup_app_icon(self):
        """Configura el icono de la ventana principal y secundarias a partir de icon.svg o icon.ico/png"""
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("j360More.multiemulator.app")
            except Exception:
                pass

        # 1. Asegurar generación si solo está presente icon.svg
        if (not os.path.exists(ICON_PNG_PATH) or not os.path.exists(ICON_ICO_PATH)) and os.path.exists(ICON_SVG_PATH) and resvg_py is not None:
            try:
                png_bytes = resvg_py.svg_to_bytes(svg_path=ICON_SVG_PATH, width=256)
                pil_img = Image.open(io.BytesIO(png_bytes))
                pil_img.save(ICON_PNG_PATH, format="PNG")
                pil_img.save(ICON_ICO_PATH, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
            except Exception as e:
                print(f"[!] Error generando icono desde icon.svg: {e}")

        # 2. Configurar icono en la ventana de Tkinter
        if os.path.exists(ICON_ICO_PATH):
            try:
                self.root.iconbitmap(ICON_ICO_PATH)
            except Exception:
                pass

        if os.path.exists(ICON_PNG_PATH):
            try:
                self.app_icon_tk = ImageTk.PhotoImage(file=ICON_PNG_PATH)
                self.root.iconphoto(True, self.app_icon_tk)
            except Exception:
                pass

    def _load_assets(self):
        self.controller_img_tk = None
        self.controller_pil_base = None
        self.controller_pil_hires = None

        # 1. Cargar o renderizar SVG de alta resolución (1400px) para zoom ultra nítido
        if os.path.exists(CONTROLLER_SVG_PATH) and resvg_py is not None:
            try:
                png_bytes_hi = resvg_py.svg_to_bytes(svg_path=CONTROLLER_SVG_PATH, width=1400)
                self.controller_pil_hires = Image.open(io.BytesIO(png_bytes_hi))
                try:
                    self.controller_pil_hires.save(CONTROLLER_HIRES_PNG)
                except Exception:
                    pass
            except Exception as e:
                print(f"[!] Error renderizando SVG HD: {e}")

        # 2. Cargar cache HD desde disco si está disponible
        if self.controller_pil_hires is None and os.path.exists(CONTROLLER_HIRES_PNG):
            try:
                self.controller_pil_hires = Image.open(CONTROLLER_HIRES_PNG)
            except Exception:
                pass

        # 3. Si disponemos de la imagen HD, generar la imagen base de 350x275 con LANCZOS
        if self.controller_pil_hires is not None:
            try:
                self.controller_pil_base = self.controller_pil_hires.resize((350, 275), Image.Resampling.LANCZOS)
                self.controller_img_tk = ImageTk.PhotoImage(self.controller_pil_base)
                try:
                    self.controller_pil_base.save(CONTROLLER_CACHE_PNG)
                except Exception:
                    pass
                return
            except Exception:
                pass

        # 4. Fallback a cache renderizada previa de 350x275
        if os.path.exists(CONTROLLER_CACHE_PNG):
            try:
                pil_img = Image.open(CONTROLLER_CACHE_PNG)
                self.controller_pil_base = pil_img.copy()
                self.controller_pil_hires = self.controller_pil_base
                self.controller_img_tk = ImageTk.PhotoImage(pil_img)
                return
            except Exception:
                pass

        # 5. Fallback a PNG anterior si existe
        if os.path.exists(CONTROLLER_PNG_FALLBACK):
            try:
                pil_img = Image.open(CONTROLLER_PNG_FALLBACK).resize((350, 275), Image.Resampling.LANCZOS)
                self.controller_pil_base = pil_img.copy()
                self.controller_pil_hires = self.controller_pil_base
                self.controller_img_tk = ImageTk.PhotoImage(pil_img)
                return
            except Exception:
                pass

    def load_config(self) -> dict:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                    if "language" not in data:
                        data["language"] = "es"
                    if "author" not in data:
                        data["author"] = "JuanJSAR"
                    if "max_controllers" not in data:
                        data["max_controllers"] = 8
                    for i in range(1, 13):
                        str_i = str(i)
                        if str_i in data.get("controllers", {}):
                            if "calibration" not in data["controllers"][str_i]:
                                data["controllers"][str_i]["calibration"] = json.loads(json.dumps(DEFAULT_CALIBRATION))
                        else:
                            data["controllers"][str_i] = {
                                "name": f"Jugador {i}",
                                "enabled": False,
                                "physical_device_id": "none",
                                "mappings": dict(DEFAULT_MAPPINGS),
                                "calibration": json.loads(json.dumps(DEFAULT_CALIBRATION))
                            }
                    if "games" not in data or not isinstance(data["games"], list):
                        data["games"] = []
                    return data
            except Exception as e:
                print(f"[!] Error leyendo {CONFIG_FILE}: {e}")

        cfg = {"version": "2.0", "author": "JuanJSAR", "language": "es", "max_controllers": 8, "games": [], "controllers": {}}
        for i in range(1, 13):
            cfg["controllers"][str(i)] = {
                "name": f"Jugador {i}",
                "enabled": False,
                "physical_device_id": "none",
                "mappings": dict(DEFAULT_MAPPINGS),
                "calibration": json.loads(json.dumps(DEFAULT_CALIBRATION))
            }
        return cfg

    def save_config(self, silent: bool = False):
        self._sync_ui_to_config()
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            self.engine.set_config(self.config)
            if not silent:
                messagebox.showinfo(self.t("btn_settings"), self.t("config_saved"))
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", self.t("config_error", e=e))

    def _build_ui(self):
        # 1. Cabecera superior compacta
        header_frame = ttk.Frame(self.root, padding="8 3 8 3")
        header_frame.pack(fill=tk.X)

        max_ctrls = self.config.get("max_controllers", 8)
        self.title_lbl = ttk.Label(header_frame, text=self.t("header_title", count=max_ctrls), font=("Segoe UI", 10, "bold"))
        self.title_lbl.pack(side=tk.LEFT)

        self.btn_devices = ttk.Button(header_frame, text=self.t("btn_devices"), command=self._open_devices_dialog)
        self.btn_devices.pack(side=tk.LEFT, padx=(12, 4))

        self.btn_settings = ttk.Button(header_frame, text=self.t("btn_settings"), command=self._open_settings_dialog)
        self.btn_settings.pack(side=tk.LEFT, padx=4)

        status_container = ttk.Frame(header_frame)
        status_container.pack(side=tk.RIGHT)

        self.status_dot = tk.Canvas(status_container, width=12, height=12, highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, padx=3)
        self.status_circle = self.status_dot.create_oval(1, 1, 11, 11, fill="#888888", outline="")

        self.status_text_lbl = ttk.Label(status_container, text=self.t("status_stopped"), font=("Segoe UI", 8))
        self.status_text_lbl.pack(side=tk.LEFT)

        # 2. Barra inferior compacta (se empaqueta primero al fondo para garantizar visibilidad)
        bottom_frame = ttk.Frame(self.root, padding="8 4 8 4")
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_toggle_emu = ttk.Button(bottom_frame, text=self.t("btn_start_emu"), command=self._toggle_emulation)
        self.btn_toggle_emu.pack(side=tk.LEFT, padx=4)

        self.btn_joy_cpl = ttk.Button(bottom_frame, text=self.t("btn_joy_cpl"), command=self._open_joy_cpl)
        self.btn_joy_cpl.pack(side=tk.LEFT, padx=4)

        self.btn_save = ttk.Button(bottom_frame, text=self.t("btn_save"), command=self.save_config)
        self.btn_save.pack(side=tk.RIGHT, padx=4)

        self.btn_reset = ttk.Button(bottom_frame, text=self.t("btn_reset"), command=self._reset_current_preset)
        self.btn_reset.pack(side=tk.RIGHT, padx=4)

        self.lbl_version = ttk.Label(
            bottom_frame,
            text=f"v{APP_VERSION}",
            font=("Segoe UI", 9, "bold"),
            foreground="#666666",
            anchor="center"
        )
        self.lbl_version.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 3. Pestañas de controles (1 a 12 según max_controllers) que rellenan el espacio central
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=2)

        self.tab_frames = {}
        self.tab_widgets = {}

        self._rebuild_tabs(max_ctrls)

        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._on_tab_changed())

    def _rebuild_tabs(self, count: int):
        # Guardar pestaña seleccionada actualmente si es posible
        cur_idx = 0
        try:
            cur_idx = self.notebook.index(self.notebook.select())
        except Exception:
            pass

        # Limpiar pestañas actuales del notebook
        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)

        self.tab_frames.clear()
        self.tab_widgets.clear()

        for i in range(1, count + 1):
            tab = ttk.Frame(self.notebook, padding=4)
            tab_text = self.t("tab_control", i=i)
            self.notebook.add(tab, text=f" {tab_text} ")
            self.tab_frames[i] = tab
            self._build_tab_content(i, tab)

        # Pestaña fija de Juegos al extremo derecho
        self.tab_games = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(self.tab_games, text=f" {self.t('tab_games')} ")
        self._build_games_tab(self.tab_games)

        if count > 0:
            target_idx = min(cur_idx, count)  # permitir seleccionar pestaña de juegos si estaba activa
            self.notebook.select(target_idx)

        if hasattr(self, "title_lbl"):
            self.title_lbl.config(text=self.t("header_title", count=count))

        self._refresh_all_devices()

    def _build_tab_content(self, pad_id: int, parent: ttk.Frame):
        widgets = {"combos": {}, "buttons": {}, "calib": {}, "mapping_controls": []}

        # Barra de asignación de periférico físico
        top_bar = ttk.Frame(parent, padding=2)
        top_bar.pack(fill=tk.X, pady=(0, 2))

        enabled_var = tk.BooleanVar(value=self.config.get("controllers", {}).get(str(pad_id), {}).get("enabled", True))
        chk_enable = ttk.Checkbutton(top_bar, text=self.t("lbl_enabled"), variable=enabled_var, command=self._sync_ui_to_config)
        chk_enable.pack(side=tk.LEFT, padx=(2, 10))
        widgets["enabled_var"] = enabled_var
        widgets["chk_enable"] = chk_enable

        ttk.Label(top_bar, text=f"{self.t('lbl_device')}:").pack(side=tk.LEFT, padx=2)
        dev_combo = ttk.Combobox(top_bar, state="readonly", width=38)
        dev_combo.pack(side=tk.LEFT, padx=3)
        dev_combo.bind("<<ComboboxSelected>>", lambda e, p=pad_id: self._on_device_selected(p))
        widgets["dev_combo"] = dev_combo

        btn_refresh = ttk.Button(top_bar, text=self.t("btn_refresh"), command=self._refresh_all_devices)
        btn_refresh.pack(side=tk.LEFT, padx=4)

        btn_copy = ttk.Button(top_bar, text=self.t("btn_copy_to"), command=lambda p=pad_id: self._open_copy_dialog(p))
        btn_copy.pack(side=tk.LEFT, padx=4)
        widgets["mapping_controls"].append(btn_copy)

        btn_wizard = ttk.Button(top_bar, text=self.t("btn_wizard"), command=lambda p=pad_id: self._open_wizard_dialog(p))
        btn_wizard.pack(side=tk.LEFT, padx=4)
        widgets["mapping_controls"].append(btn_wizard)
        widgets["btn_wizard"] = btn_wizard

        # Sub-notebook: General, Triggers, Sticks
        sub_nb = ttk.Notebook(parent)
        sub_nb.pack(fill=tk.BOTH, expand=True, pady=2)
        widgets["sub_nb"] = sub_nb

        # Sub-pestaña 1: General
        sub_gen = ttk.Frame(sub_nb, padding=2)
        sub_nb.add(sub_gen, text=f" {self.t('subtab_general')} ")
        self._build_subtab_general(pad_id, sub_gen, widgets)

        # Sub-pestaña 2: Triggers
        sub_trig = ttk.Frame(sub_nb, padding=4)
        sub_nb.add(sub_trig, text=f" {self.t('subtab_triggers')} ")
        self._build_subtab_triggers(pad_id, sub_trig, widgets)

        # Sub-pestaña 3: Sticks (Stick Izquierdo y Stick Derecho combinados)
        sub_sticks = ttk.Frame(sub_nb, padding=4)
        sub_nb.add(sub_sticks, text=f" {self.t('subtab_sticks')} ")
        self._build_subtab_sticks(pad_id, sub_sticks, widgets)

        self.tab_widgets[pad_id] = widgets

    def _build_subtab_general(self, pad_id: int, parent: ttk.Frame, widgets: dict):
        main_grid = ttk.Frame(parent)
        main_grid.pack(fill=tk.BOTH, expand=True)

        left_col = ttk.Frame(main_grid, padding=2)
        left_col.pack(side=tk.LEFT, fill=tk.Y, padx=4)

        center_col = ttk.Frame(main_grid, padding=2)
        center_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        right_col = ttk.Frame(main_grid, padding=2)
        right_col.pack(side=tk.RIGHT, fill=tk.Y, padx=4)

        def make_row(parent_col, label_text, target_name, label_anchor="w", lbl_width=12):
            row = ttk.Frame(parent_col)
            row.pack(fill=tk.X, pady=1)
            lbl = ttk.Label(row, text=label_text, width=lbl_width, anchor=label_anchor, font=("Segoe UI", 8))
            lbl.pack(side=tk.LEFT)
            cb = ttk.Combobox(row, values=INPUT_OPTIONS, width=11, font=("Segoe UI", 8))
            cb.pack(side=tk.LEFT, padx=2)
            cb.bind("<<ComboboxSelected>>", lambda e, p=pad_id, t=target_name, c=cb: self._on_combo_changed(p, t, c))
            btn = ttk.Button(row, text="...", width=3, command=lambda: self._start_record(pad_id, target_name))
            btn.pack(side=tk.LEFT)
            widgets["combos"][target_name] = cb
            widgets["buttons"][target_name] = btn

        # Columna Izquierda
        ttk.Label(left_col, text=self.t("sec_left_controls"), font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 1))
        make_row(left_col, self.t("row_left_trigger"), "LEFT_TRIGGER")
        make_row(left_col, self.t("row_left_shoulder"), "LEFT_SHOULDER")
        make_row(left_col, self.t("row_back"), "BACK")
        make_row(left_col, self.t("row_start"), "START")
        make_row(left_col, self.t("row_guide"), "GUIDE")
        ttk.Separator(left_col, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=2)
        ttk.Label(left_col, text=self.t("sec_left_stick"), font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 1))
        make_row(left_col, self.t("row_stick_axis_x"), "LEFT_STICK_X")
        make_row(left_col, self.t("row_stick_axis_y"), "LEFT_STICK_Y")
        make_row(left_col, self.t("row_stick_button"), "LEFT_THUMB")
        make_row(left_col, self.t("row_stick_up"), "LEFT_STICK_UP")
        make_row(left_col, self.t("row_stick_down"), "LEFT_STICK_DOWN")
        make_row(left_col, self.t("row_stick_left"), "LEFT_STICK_LEFT")
        make_row(left_col, self.t("row_stick_right"), "LEFT_STICK_RIGHT")

        # Columna Central: Imagen SVG y Clic Interactivo
        c_w, c_h = 350, 275
        canvas = tk.Canvas(center_col, width=c_w, height=c_h, bg="#ffffff", highlightthickness=1, highlightbackground="#d0d0d0")
        canvas.pack(pady=2)
        widgets["canvas"] = canvas

        if self.controller_img_tk:
            canvas.create_image(c_w // 2, c_h // 2, image=self.controller_img_tk)

        # Vincular clics del ratón para mapear directamente al pulsar en el SVG
        canvas.bind("<Button-1>", lambda e, p=pad_id: self._on_canvas_click(e, p))
        canvas.bind("<Motion>", lambda e, p=pad_id: self._on_canvas_motion(e, p))

        # Indicadores reactivos en el canvas (LEDs de pulsación)
        widgets["leds"] = {}
        for btn_k, (cx, cy, r) in CANVAS_POINTS.items():
            glow = canvas.create_oval(cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2, outline="#00ff66", width=2, state="hidden")
            tag = canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#00ff66", outline="#ffffff", width=2, state="hidden")
            widgets["leds"][btn_k] = (tag, glow)

        # Elementos dinamicos para destacar el boton en modo ASIGNACION (grabando)
        rec_halo = canvas.create_oval(0, 0, 0, 0, outline="#ff3300", width=3, state="hidden")
        rec_core = canvas.create_oval(0, 0, 0, 0, fill="#ffaa00", outline="#ffffff", width=2, state="hidden")
        widgets["rec_indicators"] = {"halo": rec_halo, "core": rec_core}

        # Mensaje de ayuda / tooltip
        self.hint_lbl = ttk.Label(center_col, text=self.t("hint_canvas_click"), font=("Segoe UI", 8, "italic"))
        self.hint_lbl.pack(pady=1)

        # D-Pad inferior centrado con textos centrados
        dpad_outer = ttk.Frame(center_col)
        dpad_outer.pack(pady=2)

        ttk.Label(dpad_outer, text=self.t("sec_dpad"), font=("Segoe UI", 8, "bold"), anchor="center").pack(fill=tk.X, pady=(0, 1))

        dpad_frame = ttk.Frame(dpad_outer)
        dpad_frame.pack()
        make_row(dpad_frame, self.t("row_dpad_up"), "DPAD_UP", label_anchor="center", lbl_width=14)
        make_row(dpad_frame, self.t("row_dpad_down"), "DPAD_DOWN", label_anchor="center", lbl_width=14)
        make_row(dpad_frame, self.t("row_dpad_left"), "DPAD_LEFT", label_anchor="center", lbl_width=14)
        make_row(dpad_frame, self.t("row_dpad_right"), "DPAD_RIGHT", label_anchor="center", lbl_width=14)

        # Columna Derecha
        ttk.Label(right_col, text=self.t("sec_right_controls"), font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 1))
        make_row(right_col, self.t("row_right_trigger"), "RIGHT_TRIGGER")
        make_row(right_col, self.t("row_right_shoulder"), "RIGHT_SHOULDER")
        make_row(right_col, self.t("row_btn_y"), "Y")
        make_row(right_col, self.t("row_btn_x"), "X")
        make_row(right_col, self.t("row_btn_b"), "B")
        make_row(right_col, self.t("row_btn_a"), "A")
        ttk.Separator(right_col, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=2)
        ttk.Label(right_col, text=self.t("sec_right_stick"), font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 1))
        make_row(right_col, self.t("row_stick_axis_x"), "RIGHT_STICK_X")
        make_row(right_col, self.t("row_stick_axis_y"), "RIGHT_STICK_Y")
        make_row(right_col, self.t("row_stick_button"), "RIGHT_THUMB")
        make_row(right_col, self.t("row_stick_up"), "RIGHT_STICK_UP")
        make_row(right_col, self.t("row_stick_down"), "RIGHT_STICK_DOWN")
        make_row(right_col, self.t("row_stick_left"), "RIGHT_STICK_LEFT")
        make_row(right_col, self.t("row_stick_right"), "RIGHT_STICK_RIGHT")

        cfg = self.config.get("controllers", {}).get(str(pad_id), {})
        saved_maps = cfg.get("mappings", {})
        for target, cb in widgets["combos"].items():
            val = saved_maps.get(target, DEFAULT_MAPPINGS.get(target, "-- Ninguno --"))
            cb.set(val)

    def _find_target_at_pos(self, click_x: float, click_y: float) -> str:
        """Determina qué botón o parte interactiva fue clickeada (excluyendo el Fondo)."""
        # 1. Comprobar cruceta D-Pad
        dpad_cx, dpad_cy = 122.5, 189.6
        dx = click_x - dpad_cx
        dy = click_y - dpad_cy
        dist_dpad = math.sqrt(dx * dx + dy * dy)
        if dist_dpad <= 28.0:
            if abs(dy) > abs(dx):
                return "DPAD_UP" if dy < 0 else "DPAD_DOWN"
            else:
                return "DPAD_LEFT" if dx < 0 else "DPAD_RIGHT"

        # 2. Comprobar Stick Izquierdo (direccional o centro)
        ls_cx, ls_cy = 63.9, 140.2
        dx_ls = click_x - ls_cx
        dy_ls = click_y - ls_cy
        dist_ls = math.sqrt(dx_ls * dx_ls + dy_ls * dy_ls)
        if dist_ls <= 26.0:
            if dist_ls < 7.5:
                return "LEFT_THUMB"
            else:
                if abs(dy_ls) > abs(dx_ls):
                    return "LEFT_STICK_UP" if dy_ls < 0 else "LEFT_STICK_DOWN"
                else:
                    return "LEFT_STICK_LEFT" if dx_ls < 0 else "LEFT_STICK_RIGHT"

        # 3. Comprobar Stick Derecho (direccional o centro)
        rs_cx, rs_cy = 224.4, 189.6
        dx_rs = click_x - rs_cx
        dy_rs = click_y - rs_cy
        dist_rs = math.sqrt(dx_rs * dx_rs + dy_rs * dy_rs)
        if dist_rs <= 26.0:
            if dist_rs < 7.5:
                return "RIGHT_THUMB"
            else:
                if abs(dy_rs) > abs(dx_rs):
                    return "RIGHT_STICK_UP" if dy_rs < 0 else "RIGHT_STICK_DOWN"
                else:
                    return "RIGHT_STICK_LEFT" if dx_rs < 0 else "RIGHT_STICK_RIGHT"

        # 4. Comprobar los demás botones individuales
        for btn_name, (bx, by, br) in HITBOXES.items():
            d = math.sqrt((click_x - bx) ** 2 + (click_y - by) ** 2)
            if d <= br:
                return btn_name

        return None

    def _on_canvas_motion(self, event, pad_id: int):
        widgets = self.tab_widgets.get(pad_id, {})
        canvas = widgets.get("canvas")
        if not canvas:
            return

        if not widgets.get("is_device_assigned", True):
            canvas.config(cursor="")
            if hasattr(self, "hint_lbl"):
                self.hint_lbl.config(text=self.t("hint_no_device"))
            return

        target = self._find_target_at_pos(event.x, event.y)
        if target:
            canvas.config(cursor="hand2")
            lbl_text = self.target_name(target)
            self.hint_lbl.config(text=self.t("hint_click_map", name=lbl_text))
        else:
            canvas.config(cursor="")
            self.hint_lbl.config(text=self.t("hint_canvas_click"))

    def _on_canvas_click(self, event, pad_id: int):
        widgets = self.tab_widgets.get(pad_id, {})
        if not widgets.get("is_device_assigned", True):
            return

        target = self._find_target_at_pos(event.x, event.y)
        if target:
            lbl_text = self.target_name(target)
            self.hint_lbl.config(text=self.t("hint_mapping_wait", name=lbl_text))
            self._start_record(pad_id, target)

    def _build_calib_row(self, parent, label_text: str, from_: float, to: float, init_val: float, var_holder: dict, var_key: str, widgets: dict = None, entry_from: float = None, entry_to: float = None):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=1)

        ttk.Label(row, text=label_text, width=14, font=("Segoe UI", 8)).pack(side=tk.LEFT)

        float_var = tk.DoubleVar(value=float(init_val))
        var_holder[var_key] = float_var

        # Slider con pasos en unidades enteras
        scale = ttk.Scale(row, from_=from_, to=to, orient=tk.HORIZONTAL)
        scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # Entry para permitir tipeo directo de float con % al lado
        entry_var = tk.StringVar(value=f"{init_val:g}")
        entry = ttk.Entry(row, textvariable=entry_var, width=7, font=("Segoe UI", 8))
        entry.pack(side=tk.LEFT)
        ttk.Label(row, text="%", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(1, 2))

        var_holder[f"{var_key}_scale"] = scale
        var_holder[f"{var_key}_entry"] = entry_var
        var_holder[f"{var_key}_entry_widget"] = entry

        if widgets is not None and "mapping_controls" in widgets:
            widgets["mapping_controls"].append(scale)
            widgets["mapping_controls"].append(entry)

        is_updating = [False]

        def on_scale_move(v):
            if is_updating[0]:
                return
            is_updating[0] = True
            try:
                # El slider opera en unidades enteras dentro de [from_, to]
                int_val = round(float(v))
                float_var.set(float(int_val))
                entry_var.set(str(int_val))
                self._sync_ui_to_config()
            finally:
                is_updating[0] = False

        scale.configure(command=on_scale_move)
        is_updating[0] = True
        scale.set(round(max(from_, min(to, init_val))))
        is_updating[0] = False

        e_from = from_ if entry_from is None else entry_from
        e_to = to if entry_to is None else entry_to

        def on_entry_commit(event=None):
            if is_updating[0]:
                return
            is_updating[0] = True
            try:
                txt = entry_var.get().strip().replace("%", "")
                val = float(txt)
                val = max(e_from, min(e_to, val))
                float_var.set(val)
                slider_val = max(from_, min(to, val))
                scale.set(round(slider_val))
                entry_var.set(f"{val:g}")
                self._sync_ui_to_config()
            except ValueError:
                entry_var.set(f"{float_var.get():g}")
            finally:
                is_updating[0] = False

        entry.bind("<Return>", on_entry_commit)
        entry.bind("<FocusOut>", on_entry_commit)

        return float_var

    def _build_subtab_triggers(self, pad_id: int, parent: ttk.Frame, widgets: dict):
        cfg = self.config.get("controllers", {}).get(str(pad_id), {})
        calib_cfg = cfg.get("calibration", json.loads(json.dumps(DEFAULT_CALIBRATION)))

        def make_trigger_panel(parent_frame, trig_key, title):
            box = ttk.LabelFrame(parent_frame, text=title, padding=6)
            box.pack(fill=tk.BOTH, expand=True, pady=3)

            data = calib_cfg.get(trig_key, {"deadzone": 0, "anti_deadzone": 0, "sensitivity": 0, "invert": False})

            # Contenedor visual: Curva de Respuesta cuadrada
            curve_box = ttk.LabelFrame(box, text=self.t("curve_response"), padding=2)
            curve_box.pack(side=tk.LEFT, padx=6)

            s_w, s_h = 125, 125
            cv = tk.Canvas(curve_box, width=s_w, height=s_h, bg="#ffffff", highlightthickness=1, highlightbackground="#cccccc")
            cv.pack()

            lbl_di_xi = ttk.Label(curve_box, text="DI: 0    XI: 0", font=("Consolas", 8, "bold"))
            lbl_di_xi.pack(pady=1)

            right_box = ttk.Frame(box)
            right_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

            calib_vars = {}
            adz_var = self._build_calib_row(right_box, self.t("lbl_anti_deadzone"), 0, 100, float(data.get("anti_deadzone", 0)), calib_vars, "adz_var", widgets)
            dz_var = self._build_calib_row(right_box, self.t("lbl_deadzone"), 0, 100, float(data.get("deadzone", 0)), calib_vars, "dz_var", widgets)
            sens_var = self._build_calib_row(right_box, self.t("lbl_sensitivity"), -100, 100, float(data.get("sensitivity", 0)), calib_vars, "sens_var", widgets, entry_from=-1000, entry_to=1000)

            inv_var = tk.BooleanVar(value=data.get("invert", False))
            chk_inv = ttk.Checkbutton(right_box, text=self.t("chk_invert_axis"), variable=inv_var, command=self._sync_ui_to_config)
            chk_inv.pack(anchor="w", pady=1)
            widgets["mapping_controls"].append(chk_inv)

            widgets["calib"][trig_key] = {
                "canvas": cv,
                "lbl_di_xi": lbl_di_xi,
                "adz_var": adz_var,
                "dz_var": dz_var,
                "sens_var": sens_var,
                "inv_var": inv_var
            }

        make_trigger_panel(parent, "left_trigger", self.t("title_left_trigger"))
        make_trigger_panel(parent, "right_trigger", self.t("title_right_trigger"))

    def _build_subtab_sticks(self, pad_id: int, parent: ttk.Frame, widgets: dict):
        cfg = self.config.get("controllers", {}).get(str(pad_id), {})
        calib_cfg = cfg.get("calibration", json.loads(json.dumps(DEFAULT_CALIBRATION)))

        def make_stick_box(parent_frame, stick_key: str, stick_title: str):
            data = calib_cfg.get(stick_key, {"deadzone": 8, "anti_deadzone": 0, "sensitivity": 0, "invert_x": False, "invert_y": False})

            box = ttk.LabelFrame(parent_frame, text=stick_title, padding=6)
            box.pack(fill=tk.BOTH, expand=True, pady=3)

            # Contenedor izquierdo: Visualizadores 2D y Curva
            visuals_row = ttk.Frame(box)
            visuals_row.pack(side=tk.LEFT, padx=6)

            # 1. Posición 2D
            pos_box = ttk.LabelFrame(visuals_row, text=self.t("pos_2d"), padding=2)
            pos_box.pack(side=tk.LEFT, padx=3)

            s_w, s_h = 125, 125
            cv_pos = tk.Canvas(pos_box, width=s_w, height=s_h, bg="#ffffff", highlightthickness=1, highlightbackground="#cccccc")
            cv_pos.pack()

            lbl_xy = ttk.Label(pos_box, text="X: +0.00  Y: +0.00", font=("Consolas", 8, "bold"))
            lbl_xy.pack(pady=1)

            # 2. Curva de Sensibilidad
            curve_box = ttk.LabelFrame(visuals_row, text=self.t("curve_response"), padding=2)
            curve_box.pack(side=tk.LEFT, padx=3)

            cv_curve = tk.Canvas(curve_box, width=s_w, height=s_h, bg="#ffffff", highlightthickness=1, highlightbackground="#cccccc")
            cv_curve.pack()

            lbl_di_xi = ttk.Label(curve_box, text="DI: 0    XI: 0", font=("Consolas", 8, "bold"))
            lbl_di_xi.pack(pady=1)

            # Contenedor derecho: Sliders y controles
            right_box = ttk.Frame(box, padding=2)
            right_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8)

            calib_vars = {}
            adz_var = self._build_calib_row(right_box, self.t("lbl_anti_deadzone"), 0, 100, float(data.get("anti_deadzone", 0)), calib_vars, "adz_var", widgets)
            dz_var = self._build_calib_row(right_box, self.t("lbl_deadzone"), 0, 100, float(data.get("deadzone", 8)), calib_vars, "dz_var", widgets)
            sens_var = self._build_calib_row(right_box, self.t("lbl_sensitivity"), -100, 100, float(data.get("sensitivity", 0)), calib_vars, "sens_var", widgets, entry_from=-1000, entry_to=1000)

            check_row = ttk.Frame(right_box)
            check_row.pack(fill=tk.X, pady=2)

            inv_x_var = tk.BooleanVar(value=data.get("invert_x", False))
            chk_inv_x = ttk.Checkbutton(check_row, text=self.t("chk_invert_x"), variable=inv_x_var, command=self._sync_ui_to_config)
            chk_inv_x.pack(side=tk.LEFT, padx=(0, 10))
            widgets["mapping_controls"].append(chk_inv_x)

            inv_y_var = tk.BooleanVar(value=data.get("invert_y", False))
            chk_inv_y = ttk.Checkbutton(check_row, text=self.t("chk_invert_y"), variable=inv_y_var, command=self._sync_ui_to_config)
            chk_inv_y.pack(side=tk.LEFT)
            widgets["mapping_controls"].append(chk_inv_y)

            widgets["calib"][stick_key] = {
                "canvas": cv_pos,
                "curve_canvas": cv_curve,
                "lbl_xy": lbl_xy,
                "lbl_di_xi": lbl_di_xi,
                "dz_var": dz_var,
                "adz_var": adz_var,
                "sens_var": sens_var,
                "inv_x_var": inv_x_var,
                "inv_y_var": inv_y_var
            }

        make_stick_box(parent, "left_stick", self.t("title_left_stick"))
        make_stick_box(parent, "right_stick", self.t("title_right_stick"))

    def _update_tab_state(self, pad_id: int, has_dev: bool):
        """Si el control no tiene un periférico asignado, no se puede activar y todas las funciones de mapeo se desactivan (opacas)."""
        widgets = self.tab_widgets.get(pad_id)
        if not widgets:
            return

        widgets["is_device_assigned"] = has_dev
        chk_enable = widgets.get("chk_enable")
        enabled_var = widgets.get("enabled_var")

        if not has_dev:
            # 1. El control NO se puede activar si no tiene periférico asignado
            if chk_enable:
                try:
                    chk_enable.state(['disabled'])
                except Exception:
                    chk_enable.config(state=tk.DISABLED)
            if enabled_var:
                enabled_var.set(False)

            # 2. Todas las funciones de mapeo se desactivan y vuelven opacas
            for cb in widgets.get("combos", {}).values():
                cb.config(state="disabled")

            for btn in widgets.get("buttons", {}).values():
                btn.config(state=tk.DISABLED)

            for ctrl in widgets.get("mapping_controls", []):
                try:
                    ctrl.state(['disabled'])
                except Exception:
                    try:
                        ctrl.config(state=tk.DISABLED)
                    except Exception:
                        pass
        else:
            # 1. El control SÍ se puede activar si tiene periférico asignado
            if chk_enable:
                try:
                    chk_enable.state(['!disabled'])
                except Exception:
                    chk_enable.config(state=tk.NORMAL)
            if enabled_var:
                cfg_enabled = self.config.get("controllers", {}).get(str(pad_id), {}).get("enabled", True)
                enabled_var.set(cfg_enabled)

            # 2. Todas las funciones de mapeo se reactivan
            for cb in widgets.get("combos", {}).values():
                cb.config(state="readonly")

            for btn in widgets.get("buttons", {}).values():
                btn.config(state=tk.NORMAL)

            for ctrl in widgets.get("mapping_controls", []):
                try:
                    ctrl.state(['!disabled'])
                except Exception:
                    try:
                        ctrl.config(state=tk.NORMAL)
                    except Exception:
                        pass

    def _refresh_all_devices(self):
        self.available_devices = self.device_manager.refresh_devices()
        dev_names = []
        for d in self.available_devices:
            if d["id"] == "none":
                dev_names.append(self.t("none_disconnected"))
            elif d["id"] == "keyboard":
                dev_names.append(self.t("keyboard_device_name"))
            else:
                dev_names.append(d["name"])

        for pad_id, widgets in self.tab_widgets.items():
            cb = widgets["dev_combo"]
            cb["values"] = dev_names

            cfg = self.config.get("controllers", {}).get(str(pad_id), {})
            saved_dev_id = cfg.get("physical_device_id", "none")

            match_idx = 0
            for idx, dev in enumerate(self.available_devices):
                if dev["id"] == saved_dev_id:
                    match_idx = idx
                    break
            cb.current(match_idx)

            has_dev = (saved_dev_id != "none" and any(d["id"] == saved_dev_id for d in self.available_devices if d["id"] != "none"))
            self._update_tab_state(pad_id, has_dev)

    def _on_devices_hotplugged(self, new_devices: List[Dict[str, Any]]):
        """Manejador ejecutado en el hilo de la UI cuando el DeviceManager auto-reconecta mandos."""
        try:
            self.available_devices = new_devices
            dev_names = []
            for d in self.available_devices:
                if d["id"] == "none":
                    dev_names.append(self.t("none_disconnected"))
                elif d["id"] == "keyboard":
                    dev_names.append(self.t("keyboard_device_name"))
                else:
                    dev_names.append(d["name"])

            for pad_id, widgets in self.tab_widgets.items():
                cb = widgets["dev_combo"]
                cb["values"] = dev_names

                cfg = self.config.get("controllers", {}).get(str(pad_id), {})
                saved_dev_id = cfg.get("physical_device_id", "none")

                match_idx = 0
                for idx, dev in enumerate(self.available_devices):
                    if dev["id"] == saved_dev_id:
                        match_idx = idx
                        break
                cb.current(match_idx)

                has_dev = (saved_dev_id != "none" and any(d["id"] == saved_dev_id for d in self.available_devices if d["id"] != "none"))
                self._update_tab_state(pad_id, has_dev)
        except Exception:
            pass

    def _on_device_selected(self, pad_id: int):
        widgets = self.tab_widgets[pad_id]
        sel_idx = widgets["dev_combo"].current()
        if 0 <= sel_idx < len(self.available_devices):
            dev = self.available_devices[sel_idx]
            dev_id = dev["id"]
            if str(pad_id) not in self.config["controllers"]:
                self.config["controllers"][str(pad_id)] = {}
            self.config["controllers"][str(pad_id)]["physical_device_id"] = dev_id

            has_dev = (dev_id != "none")
            self._update_tab_state(pad_id, has_dev)
            self._sync_ui_to_config()
            self.engine.set_config(self.config)

    def _sync_ui_to_config(self):
        for pad_id, widgets in self.tab_widgets.items():
            str_id = str(pad_id)
            if str_id not in self.config["controllers"]:
                self.config["controllers"][str_id] = {}

            self.config["controllers"][str_id]["enabled"] = widgets["enabled_var"].get()

            sel_idx = widgets["dev_combo"].current()
            if 0 <= sel_idx < len(self.available_devices):
                self.config["controllers"][str_id]["physical_device_id"] = self.available_devices[sel_idx]["id"]

            mappings = {}
            for target, cb in widgets["combos"].items():
                mappings[target] = cb.get().strip()
            self.config["controllers"][str_id]["mappings"] = mappings

            calib = {}
            c_widgets = widgets.get("calib", {})
            for key in ["left_trigger", "right_trigger"]:
                if key in c_widgets:
                    calib[key] = {
                        "deadzone": c_widgets[key]["dz_var"].get(),
                        "anti_deadzone": c_widgets[key]["adz_var"].get(),
                        "sensitivity": c_widgets[key]["sens_var"].get(),
                        "invert": c_widgets[key]["inv_var"].get()
                    }
            for key in ["left_stick", "right_stick"]:
                if key in c_widgets:
                    calib[key] = {
                        "deadzone": c_widgets[key]["dz_var"].get(),
                        "anti_deadzone": c_widgets[key]["adz_var"].get(),
                        "sensitivity": c_widgets[key]["sens_var"].get(),
                        "invert_x": c_widgets[key]["inv_x_var"].get(),
                        "invert_y": c_widgets[key]["inv_y_var"].get()
                    }
            self.config["controllers"][str_id]["calibration"] = calib

        self.engine.set_config(self.config)

    def _check_mapping_conflict(self, current_pad_id: int, target_name: str, new_mapping: str):
        if not new_mapping or new_mapping == "-- Ninguno --":
            return None

        current_cfg = self.config.get("controllers", {}).get(str(current_pad_id), {})
        current_maps = current_cfg.get("mappings", {})

        # 1. Comprobar si ya esta asignada en OTRA posicion de este mismo mando
        for other_btn, mapped_val in current_maps.items():
            if other_btn != target_name and mapped_val and mapped_val.strip().lower() == new_mapping.strip().lower():
                return ("same", current_pad_id, current_cfg.get("name", f"Control {current_pad_id}"), other_btn)

        # 2. Comprobar si esta asignada en otro mando virtual con el mismo periferico fisico
        current_dev = current_cfg.get("physical_device_id", "none")
        if current_dev != "none":
            controllers_cfg = self.config.get("controllers", {})
            for other_id_str, other_cfg in controllers_cfg.items():
                try:
                    other_id = int(other_id_str)
                except ValueError:
                    continue

                if other_id == current_pad_id:
                    continue

                other_dev = other_cfg.get("physical_device_id", "none")
                if other_dev == current_dev:
                    other_maps = other_cfg.get("mappings", {})
                    for other_btn, mapped_val in other_maps.items():
                        if mapped_val and mapped_val.strip().lower() == new_mapping.strip().lower():
                            other_name = other_cfg.get("name", f"Control {other_id}")
                            return ("other", other_id, other_name, other_btn)
        return None

    def _apply_mapping_with_conflict_check(self, pad_id: int, target_name: str, new_val: str, combo: ttk.Combobox = None) -> bool:
        new_val = new_val.strip()
        prev_val = self.config.get("controllers", {}).get(str(pad_id), {}).get("mappings", {}).get(target_name, "-- Ninguno --")

        if new_val != "-- Ninguno --":
            conflict = self._check_mapping_conflict(pad_id, target_name, new_val)
            if conflict:
                conflict_type, other_id, other_name, other_btn = conflict
                other_btn_str = self.target_name(other_btn)
                target_name_str = self.target_name(target_name)

                if conflict_type == "same":
                    ans = messagebox.askyesnocancel(
                        self.t("conflict_same_title"),
                        self.t("conflict_same_msg", val=new_val, other=other_btn_str, target=target_name_str),
                        icon="warning"
                    )
                    if ans is None:
                        if combo:
                            combo.set(prev_val)
                        return False
                    elif ans is True:
                        self.config["controllers"][str(pad_id)]["mappings"][other_btn] = "-- Ninguno --"
                        if pad_id in self.tab_widgets:
                            other_cb = self.tab_widgets[pad_id]["combos"].get(other_btn)
                            if other_cb:
                                other_cb.set("-- Ninguno --")

                elif conflict_type == "other":
                    ans = messagebox.askyesnocancel(
                        self.t("conflict_other_title"),
                        self.t("conflict_other_msg", val=new_val, other=other_btn_str, name=other_name, id=other_id),
                        icon="warning"
                    )
                    if ans is None:
                        if combo:
                            combo.set(prev_val)
                        return False
                    elif ans is True:
                        str_other = str(other_id)
                        if str_other in self.config.get("controllers", {}):
                            self.config["controllers"][str_other]["mappings"][other_btn] = "-- Ninguno --"
                        if other_id in self.tab_widgets:
                            other_cb = self.tab_widgets[other_id]["combos"].get(other_btn)
                            if other_cb:
                                other_cb.set("-- Ninguno --")

        cb = combo or self.tab_widgets.get(pad_id, {}).get("combos", {}).get(target_name)
        if cb:
            cb.set(new_val)

        self._sync_ui_to_config()
        return True

    def _on_combo_changed(self, pad_id: int, target_name: str, combo: ttk.Combobox):
        val = combo.get().strip()
        self._apply_mapping_with_conflict_check(pad_id, target_name, val, combo=combo)

    def _on_tab_changed(self):
        if self.recording_target:
            self._cancel_recording()

    def _cancel_recording(self):
        if not self.recording_target:
            return
        pad_id, target_name, btn = self.recording_target
        self.device_manager.cancel_capture()
        if btn:
            btn.config(text="...")
        self.recording_target = None
        if hasattr(self, "hint_lbl"):
            self.hint_lbl.config(text=self.t("hint_cancelled"))

    def _start_record(self, pad_id: int, target_name: str):
        if self.recording_target is not None:
            self._cancel_recording()

        widgets = self.tab_widgets[pad_id]
        btn = widgets["buttons"].get(target_name)
        if btn:
            btn.config(text="[...]")

        self.recording_target = (pad_id, target_name, btn)
        lbl_text = self.target_name(target_name)
        if hasattr(self, "hint_lbl"):
            self.hint_lbl.config(text=self.t("hint_mapping_wait", name=lbl_text))

        cfg = self.config.get("controllers", {}).get(str(pad_id), {})
        dev_id = cfg.get("physical_device_id", "none")

        threading.Thread(target=self._record_worker, args=(pad_id, target_name, dev_id, btn), daemon=True).start()

    def _record_worker(self, pad_id: int, target_name: str, dev_id: str, btn: ttk.Button):
        detected = self.device_manager.capture_input(dev_id, timeout=4.5, target_name=target_name)

        def finish():
            if self.recording_target and self.recording_target[0] == pad_id and self.recording_target[1] == target_name:
                if detected:
                    self._apply_mapping_with_conflict_check(pad_id, target_name, detected)
                self.recording_target = None
                if hasattr(self, "hint_lbl"):
                    self.hint_lbl.config(text=self.t("hint_canvas_click"))
            if btn:
                btn.config(text="...")

        self.root.after(0, finish)

    def _on_key_press(self, event):
        # 1. Si se presiona Escape, cancelar inmediatamente la asignacion en curso
        if event.keysym.lower() in ("escape", "esc") or event.keycode == 27:
            if self.recording_target:
                self._cancel_recording()
                return

        if self.recording_target:
            pad_id, target_name, btn = self.recording_target
            cfg = self.config.get("controllers", {}).get(str(pad_id), {})
            dev_id = cfg.get("physical_device_id", "none")
            if dev_id == "keyboard":
                k_name = event.keysym.lower()
                if btn:
                    btn.config(text="...")
                self.recording_target = None
                self._apply_mapping_with_conflict_check(pad_id, target_name, f"Tecla: {k_name}")
                if hasattr(self, "hint_lbl"):
                    self.hint_lbl.config(text=self.t("hint_canvas_click"))
                return

        self.engine.on_key_event(event.keysym, is_pressed=True)

    def _on_key_release(self, event):
        self.engine.on_key_event(event.keysym, is_pressed=False)

    def _hide_emulation_devices(self):
        """Oculta los dispositivos seleccionados con HidHide cuando inicia la emulación."""
        if not self.driver_manager.is_hidhide_installed():
            return

        hidden_devs = self.config.get("hidden_devices", [])
        if not hidden_devs:
            return

        # Registrar j360More en la lista blanca de HidHide para que la app siempre pueda leerlos
        self.driver_manager.ensure_process_whitelisted()

        for inst_path in hidden_devs:
            if inst_path:
                self.driver_manager.hide_device(inst_path)

        self.driver_manager.set_cloak_active(True)

    def _unhide_emulation_devices(self):
        """Restaura la visibilidad de los dispositivos para todo el sistema cuando se detiene la emulación."""
        if not self.driver_manager.is_hidhide_installed():
            return

        hidden_devs = self.config.get("hidden_devices", [])
        if not hidden_devs:
            return

        for inst_path in hidden_devs:
            if inst_path:
                self.driver_manager.unhide_device(inst_path)

    def _toggle_emulation(self):
        self._sync_ui_to_config()

        if self.engine.is_running():
            self.engine.stop()
            self._unhide_emulation_devices()
            self.btn_toggle_emu.config(text=self.t("btn_start_emu"))
            self.status_dot.itemconfig(self.status_circle, fill="#888888")
            self.status_text_lbl.config(text=self.t("status_stopped"))
        else:
            # Comprobar si al menos un control tiene periférico asignado y está habilitado
            max_ctrls = self.config.get("max_controllers", 12)
            has_active_pad = False
            for i in range(1, max_ctrls + 1):
                c_cfg = self.config.get("controllers", {}).get(str(i), {})
                p_dev = c_cfg.get("physical_device_id", "none")
                if c_cfg.get("enabled", True) and p_dev and p_dev != "none":
                    has_active_pad = True
                    break

            if not has_active_pad:
                messagebox.showwarning(
                    self.t("emu_unavailable_title"),
                    self.t("emu_unavailable_msg")
                )
                return

            self._hide_emulation_devices()
            self.engine.start()
            self.btn_toggle_emu.config(text=self.t("btn_stop_emu"))
            self.status_dot.itemconfig(self.status_circle, fill="#00cc44")
            self.status_text_lbl.config(text=self.t("status_active"))

    def _reset_current_preset(self):
        cur_pad_id = self.notebook.index(self.notebook.select()) + 1
        widgets = self.tab_widgets.get(cur_pad_id)
        if not widgets:
            return

        for target, cb in widgets["combos"].items():
            cb.set(DEFAULT_MAPPINGS.get(target, "-- Ninguno --"))

        c_w = widgets.get("calib", {})
        for k in ["left_trigger", "right_trigger"]:
            if k in c_w:
                for vkey, def_v in [("dz_var", 0), ("adz_var", 0), ("sens_var", 0)]:
                    c_w[k][vkey].set(def_v)
                    if f"{vkey}_scale" in c_w[k]: c_w[k][f"{vkey}_scale"].set(round(def_v))
                    if f"{vkey}_entry" in c_w[k]: c_w[k][f"{vkey}_entry"].set(str(def_v))
                c_w[k]["inv_var"].set(False)
        for k in ["left_stick", "right_stick"]:
            if k in c_w:
                for vkey, def_v in [("dz_var", 8), ("adz_var", 0), ("sens_var", 0)]:
                    c_w[k][vkey].set(def_v)
                    if f"{vkey}_scale" in c_w[k]: c_w[k][f"{vkey}_scale"].set(round(def_v))
                    if f"{vkey}_entry" in c_w[k]: c_w[k][f"{vkey}_entry"].set(str(def_v))
                c_w[k]["inv_x_var"].set(False)
                c_w[k]["inv_y_var"].set(False)

        self._sync_ui_to_config()
        messagebox.showinfo("Preset", self.t("preset_restored", i=cur_pad_id))

    def _check_system_drivers(self):
        """Verifica la disponibilidad de ViGEmBus e HidHide al arrancar la aplicación."""
        # 1. ViGEmBus es obligatorio
        if not self.driver_manager.is_vigem_installed():
            messagebox.showerror(
                self.t("vigem_missing_title"),
                self.t("vigem_missing_msg")
            )

        # 2. HidHide es opcional con aviso leve y checkbox 'No volver a preguntar'
        suppress_hidhide = self.config.get("suppress_hidhide_warning", False)
        if not suppress_hidhide and not self.driver_manager.is_hidhide_installed():
            self._show_hidhide_warning_dialog()

    def _check_update_once(self):
        """Dispara la comprobacion de nueva version en GitHub una unica vez al iniciar."""
        if getattr(self, "_update_checked", False):
            return
        self._update_checked = True
        threading.Thread(target=self._fetch_latest_release_worker, daemon=True).start()

    def _fetch_latest_release_worker(self):
        """Consulta en segundo plano la API de GitHub Releases sin bloquear la interfaz."""
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/JuanJSAR93/j360More-Xbox_360_Controller_Emulator/releases/latest",
                headers={"User-Agent": "j360More-App"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    tag_name = data.get("tag_name", "").strip()
                    if tag_name and parse_version(tag_name) > parse_version(APP_VERSION):
                        clean_tag = tag_name.lstrip("vV")
                        self._available_update_version = clean_tag
                        self.root.after(0, lambda t=clean_tag: self._on_update_detected(t))
        except Exception:
            # En caso de falta de conexion o timeout, se omite silenciosamente sin interrumpir
            pass

    def _on_update_detected(self, latest_ver: str):
        """Actualiza el indicador de version en la barra inferior haciendolo interactivo."""
        if not hasattr(self, "lbl_version"):
            return
        alert_text = self.t("new_version_available", ver=latest_ver)
        self.lbl_version.config(
            text=f"v{APP_VERSION}  {alert_text}",
            foreground="#b45309",
            cursor="hand2"
        )
        releases_url = "https://github.com/JuanJSAR93/j360More-Xbox_360_Controller_Emulator/releases"
        self.lbl_version.bind("<Button-1>", lambda e: webbrowser.open(releases_url))

        def on_enter(e):
            self.lbl_version.config(foreground="#d97706", font=("Segoe UI", 9, "bold underline"))

        def on_leave(e):
            self.lbl_version.config(foreground="#b45309", font=("Segoe UI", 9, "bold"))

        self.lbl_version.bind("<Enter>", on_enter)
        self.lbl_version.bind("<Leave>", on_leave)

    def _show_hidhide_warning_dialog(self):
        """Ventana modal informativa leve sobre la ausencia de HidHide con opción de no volver a mostrar."""
        dlg = tk.Toplevel(self.root)
        dlg.title(self.t("hidhide_warn_title"))
        dlg.geometry("450x240")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        x = max(0, self.root.winfo_x() + (self.root.winfo_width() // 2) - 225)
        y = max(0, self.root.winfo_y() + (self.root.winfo_height() // 2) - 120)
        dlg.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dlg, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text=self.t("hidhide_warn_header"),
            font=("Segoe UI", 10, "bold"),
            foreground="#d97706"
        ).pack(anchor="w", pady=(0, 6))

        ttk.Label(frame, text=self.t("hidhide_warn_body"), wraplength=410, font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 10))

        dont_ask_var = tk.BooleanVar(value=False)
        chk_dont_ask = ttk.Checkbutton(frame, text=self.t("hidhide_warn_dont_ask"), variable=dont_ask_var)
        chk_dont_ask.pack(anchor="w", pady=(0, 10))

        def on_accept():
            if dont_ask_var.get():
                self.config["suppress_hidhide_warning"] = True
                self.save_config(silent=True)
            dlg.destroy()

        btn_box = ttk.Frame(frame)
        btn_box.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(btn_box, text=self.t("hidhide_warn_btn"), command=on_accept).pack(side=tk.RIGHT, padx=4)

    def _open_settings_dialog(self):
        """Ventana modal de configuración con Idioma, Slider (1 a 12 mandos) y ruta de HidHide."""
        dlg = tk.Toplevel(self.root)
        dlg.title(self.t("set_dlg_title"))
        dlg.geometry("520x430")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        x = max(0, self.root.winfo_x() + (self.root.winfo_width() // 2) - 260)
        y = max(0, self.root.winfo_y() + (self.root.winfo_height() // 2) - 215)
        dlg.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dlg, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        # SECCION 1: Idioma / Language
        box_lang = ttk.LabelFrame(frame, text="🌐 " + self.t("set_language_label"), padding=8)
        box_lang.pack(fill=tk.X, pady=(0, 8))

        cur_lang_code = self.config.get("language", "es")
        if cur_lang_code not in SUPPORTED_LANGUAGES:
            cur_lang_code = "es"
        cur_lang_str = SUPPORTED_LANGUAGES[cur_lang_code]
        lang_var = tk.StringVar(value=cur_lang_str)

        lang_combo = ttk.Combobox(box_lang, textvariable=lang_var, values=list(SUPPORTED_LANGUAGES.values()), state="readonly", width=25)
        lang_combo.pack(anchor="w", padx=4, pady=2)

        # SECCION 2: Mandos virtuales a emular
        box_mandos = ttk.LabelFrame(frame, text=self.t("set_mandos_title"), padding=10)
        box_mandos.pack(fill=tk.X, pady=(0, 8))

        current_val = self.config.get("max_controllers", 8)
        val_var = tk.IntVar(value=current_val)

        def get_ctrl_label(cnt):
            return self.t("set_ctrl_count_1") if cnt == 1 else self.t("set_ctrl_count", count=cnt)

        val_display = ttk.Label(box_mandos, text=get_ctrl_label(current_val), font=("Segoe UI", 10, "bold"), foreground="#0066cc")
        val_display.pack(anchor="center", pady=(0, 2))

        def on_slider(v):
            ival = int(float(v))
            val_var.set(ival)
            val_display.config(text=get_ctrl_label(ival))

        slider = ttk.Scale(box_mandos, from_=1, to=12, orient=tk.HORIZONTAL, value=current_val, command=on_slider)
        slider.pack(fill=tk.X, pady=2)

        ticks_frame = ttk.Frame(box_mandos)
        ticks_frame.pack(fill=tk.X)
        ttk.Label(ticks_frame, text=self.t("set_1_controller"), font=("Segoe UI", 8)).pack(side=tk.LEFT)
        ttk.Label(ticks_frame, text=self.t("set_6_controllers"), font=("Segoe UI", 8)).pack(side=tk.LEFT, expand=True)
        ttk.Label(ticks_frame, text=self.t("set_12_controllers"), font=("Segoe UI", 8)).pack(side=tk.RIGHT)

        # SECCION 3: Integración con HidHide (Opcional)
        box_hidhide = ttk.LabelFrame(frame, text=self.t("set_hidhide_title"), padding=10)
        box_hidhide.pack(fill=tk.X, pady=(0, 8))

        is_installed = self.driver_manager.is_hidhide_installed()
        status_text = self.t("set_status_installed") if is_installed else self.t("set_status_missing")
        status_color = "#16a34a" if is_installed else "#d97706"

        status_lbl = ttk.Label(box_hidhide, text=self.t("set_status_lbl", status=status_text), font=("Segoe UI", 8, "bold"), foreground=status_color)
        status_lbl.pack(anchor="w", pady=(0, 4))

        ttk.Label(box_hidhide, text=self.t("set_hidhide_path"), font=("Segoe UI", 8)).pack(anchor="w")

        path_row = ttk.Frame(box_hidhide)
        path_row.pack(fill=tk.X, pady=(2, 4))

        current_path = self.driver_manager.get_hidhide_cli_path() or ""
        path_var = tk.StringVar(value=current_path)
        entry_path = ttk.Entry(path_row, textvariable=path_var, font=("Segoe UI", 8))
        entry_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        def on_browse_hidhide():
            chosen = filedialog.askopenfilename(
                title=self.t("set_browse_title"),
                filetypes=[("HidHideCLI executable", "HidHideCLI.exe"), ("*.exe", "*.exe"), ("*.*", "*.*")]
            )
            if chosen:
                path_var.set(chosen)

        btn_browse = ttk.Button(path_row, text=self.t("set_btn_browse"), command=on_browse_hidhide)
        btn_browse.pack(side=tk.RIGHT)

        # Opciones adicionales de HidHide
        cloak_active_var = tk.BooleanVar(value=self.driver_manager.is_cloak_active() if is_installed else True)
        chk_cloak = ttk.Checkbutton(box_hidhide, text=self.t("set_chk_cloak"), variable=cloak_active_var)
        chk_cloak.pack(anchor="w", pady=2)

        warn_suppressed = self.config.get("suppress_hidhide_warning", False)
        show_warn_var = tk.BooleanVar(value=not warn_suppressed)
        chk_warn = ttk.Checkbutton(box_hidhide, text=self.t("set_chk_warn"), variable=show_warn_var)
        chk_warn.pack(anchor="w", pady=2)

        def apply_settings():
            # 1. Aplicar idioma
            inv_lang = {v: k for k, v in SUPPORTED_LANGUAGES.items()}
            new_lang = inv_lang.get(lang_var.get(), "es")
            self.config["language"] = new_lang
            self.config["author"] = "JuanJSAR"

            # 2. Aplicar mandos
            new_count = val_var.get()
            self.config["max_controllers"] = new_count

            # 3. Aplicar configuración de HidHide
            cli_path = path_var.get().strip()
            self.config["hidhide_cli_path"] = cli_path
            self.config["suppress_hidhide_warning"] = not show_warn_var.get()
            self.driver_manager.update_config(self.config)

            if self.driver_manager.is_hidhide_installed():
                self.driver_manager.set_cloak_active(cloak_active_var.get())
                self.driver_manager.ensure_process_whitelisted()

            self._sync_ui_to_config()
            self._rebuild_tabs(new_count)
            self.save_config(silent=True)
            self._update_ui_texts()
            dlg.destroy()
            messagebox.showinfo(self.t("set_dlg_title"), self.t("set_saved"))

        btn_box = ttk.Frame(frame)
        btn_box.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))

        ttk.Button(btn_box, text="✔ " + self.t("set_btn_save"), command=apply_settings).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_box, text=self.t("set_btn_cancel"), command=dlg.destroy).pack(side=tk.RIGHT, padx=4)

    def _open_devices_dialog(self):
        """Ventana modal estilo x360ce para listar y administrar DirectInput Devices."""
        has_hidhide = self.driver_manager.is_hidhide_installed()

        dlg = tk.Toplevel(self.root)
        dlg.title(self.t("dev_dlg_title"))
        dlg.geometry("860x440")
        dlg.resizable(True, True)
        dlg.transient(self.root)
        dlg.grab_set()

        x = max(0, self.root.winfo_x() + (self.root.winfo_width() // 2) - 430)
        y = max(0, self.root.winfo_y() + (self.root.winfo_height() // 2) - 220)
        dlg.geometry(f"+{x}+{y}")

        main_f = ttk.Frame(dlg, padding=8)
        main_f.pack(fill=tk.BOTH, expand=True)

        # Encabezado superior
        top_header = ttk.Frame(main_f)
        top_header.pack(fill=tk.X, pady=(0, 6))

        header_lbl = ttk.Label(
            top_header,
            text=self.t("dev_dlg_header"),
            font=("Segoe UI", 10, "bold")
        )
        header_lbl.pack(side=tk.LEFT, padx=2)

        # Barra de herramientas superior (Refresh, Hardware, Ocultar, Mostrar)
        btn_refresh = ttk.Button(top_header, text=self.t("dev_btn_refresh"), command=lambda: populate_tree())
        btn_refresh.pack(side=tk.RIGHT, padx=2)

        btn_hw = ttk.Button(top_header, text=self.t("dev_btn_hw"), command=lambda: inspect_selected_device())
        btn_hw.pack(side=tk.RIGHT, padx=2)

        btn_unhide = ttk.Button(top_header, text=self.t("dev_btn_unhide"), command=lambda: unhide_selected_device(), state=tk.DISABLED)
        btn_unhide.pack(side=tk.RIGHT, padx=2)

        btn_hide = ttk.Button(top_header, text=self.t("dev_btn_hide"), command=lambda: hide_selected_device(), state=tk.DISABLED)
        btn_hide.pack(side=tk.RIGHT, padx=2)

        # Tabla Treeview con columna HidHide agregada
        cols = ("xinput", "type", "state", "instance_id", "hidhide", "vendor", "product")
        tree = ttk.Treeview(main_f, columns=cols, show="headings", selectmode="browse")

        tree.heading("xinput", text="XInput")
        tree.heading("type", text=self.t("dev_col_type"))
        tree.heading("state", text=self.t("dev_col_status"))
        tree.heading("instance_id", text="Instance ID")
        tree.heading("hidhide", text=self.t("dev_col_hide"))
        tree.heading("vendor", text=self.t("dev_col_vendor"))
        tree.heading("product", text=self.t("dev_col_product"))

        tree.column("xinput", width=90, anchor="center")
        tree.column("type", width=65, anchor="center")
        tree.column("state", width=75, anchor="center")
        tree.column("instance_id", width=95, anchor="center")
        tree.column("hidhide", width=125, anchor="center")
        tree.column("vendor", width=190, anchor="w")
        tree.column("product", width=190, anchor="w")

        tree_scroll = ttk.Scrollbar(main_f, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def update_button_states():
            if not has_hidhide:
                btn_hide.config(state=tk.DISABLED)
                btn_unhide.config(state=tk.DISABLED)
                return

            selected = tree.selection()
            if not selected:
                btn_hide.config(state=tk.DISABLED)
                btn_unhide.config(state=tk.DISABLED)
                return

            item = tree.item(selected[0])
            tags = item.get("tags", [])
            dev_id = tags[0] if tags else ""
            dev = next((d for d in self.available_devices if d["id"] == dev_id), None)

            # Los teclados y ratones no se pueden ocultar con HidHide
            if not dev or dev.get("type") != "joystick" or dev["id"].startswith("kbd_") or dev["id"] in ("keyboard", "mouse"):
                btn_hide.config(state=tk.DISABLED)
                btn_unhide.config(state=tk.DISABLED)
                return

            if dev.get("instance_path"):
                inst_path = dev.get("instance_path")
                is_marked = inst_path in self.config.get("hidden_devices", [])
                if is_marked or dev.get("is_hidden"):
                    btn_hide.config(state=tk.DISABLED)
                    btn_unhide.config(state=tk.NORMAL)
                else:
                    btn_hide.config(state=tk.NORMAL)
                    btn_unhide.config(state=tk.DISABLED)
            else:
                btn_hide.config(state=tk.DISABLED)
                btn_unhide.config(state=tk.DISABLED)

        def populate_tree():
            for item in tree.get_children():
                tree.delete(item)

            self.available_devices = self.device_manager.refresh_devices()

            # Mapear qué periférico está asignado a qué Virtual pad
            assigned_map = {}
            for pad_id in range(1, self.config.get("max_controllers", 12) + 1):
                p_cfg = self.config.get("controllers", {}).get(str(pad_id), {})
                p_dev = p_cfg.get("physical_device_id", "none")
                if p_dev and p_dev != "none":
                    if p_dev not in assigned_map:
                        assigned_map[p_dev] = []
                    assigned_map[p_dev].append(f"Virtual {pad_id}")

            for dev in self.available_devices:
                if dev["id"] == "none":
                    continue

                xinput_str = ", ".join(assigned_map.get(dev["id"], []))
                conn_icon = "🔌 USB" if dev["conn_type"] == "USB" else ("📶 BT" if dev["conn_type"] in ("BT", "BTH") else ("💻 INT" if dev["conn_type"] == "INT" else "⌨️ SYS"))
                status_str = self.t("dev_status_connected")

                inst_path = dev.get("instance_path")
                is_marked = inst_path and (inst_path in self.config.get("hidden_devices", []))

                if not has_hidhide:
                    hidhide_str = self.t("dev_not_available")
                elif dev.get("type") != "joystick" or dev["id"].startswith("kbd_") or dev["id"] in ("keyboard", "mouse") or not inst_path:
                    hidhide_str = "N/A"
                elif is_marked:
                    if self.engine.is_running():
                        hidhide_str = self.t("dev_hidden_emulating")
                    else:
                        hidhide_str = self.t("dev_cloak_on_emu")
                elif dev.get("is_hidden"):
                    hidhide_str = self.t("dev_hidden_system")
                else:
                    hidhide_str = self.t("dev_visible")

                tree.insert(
                    "",
                    tk.END,
                    values=(
                        xinput_str,
                        conn_icon,
                        status_str,
                        dev.get("instance_id", "N/A"),
                        hidhide_str,
                        dev.get("vendor_name", self.t("dev_std_vendor")),
                        dev.get("product_name", dev.get("name", self.t("dev_device_fallback")))
                    ),
                    tags=(dev["id"],)
                )

            update_button_states()

        def inspect_selected_device():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo(self.t("dev_btn_hw"), self.t("dev_hw_no_selection"))
                return
            item = tree.item(selected[0])
            tags = item.get("tags", [])
            dev_id = tags[0] if tags else ""
            dev = next((d for d in self.available_devices if d["id"] == dev_id), None)
            if not dev:
                return

            inst_path = dev.get("instance_path")
            is_marked = inst_path and (inst_path in self.config.get("hidden_devices", []))

            if not has_hidhide:
                hidhide_state = self.t("dev_not_available")
            elif dev.get("type") != "joystick" or dev["id"].startswith("kbd_") or dev["id"] in ("keyboard", "mouse"):
                hidhide_state = "N/A"
            elif is_marked and self.engine.is_running():
                hidhide_state = self.t("dev_hidden_emulating")
            elif is_marked:
                hidhide_state = self.t("dev_cloak_on_emu")
            elif dev.get("is_hidden"):
                hidhide_state = self.t("dev_hidden_system")
            else:
                hidhide_state = self.t("dev_visible")

            info_text = (
                f"{self.t('dev_hw_product_name')} {dev.get('product_name', 'N/A')}\n"
                f"{self.t('dev_hw_vendor')} {dev.get('vendor_name', 'N/A')}\n"
                f"{self.t('dev_hw_inst_id')} {dev.get('instance_id', 'N/A')}\n"
                f"{self.t('dev_hw_hidhide_state')} {hidhide_state}\n"
                f"{self.t('dev_hw_pnp_path')} {inst_path or 'N/A'}\n"
                f"{self.t('dev_hw_conn_type')} {dev.get('conn_type', 'N/A')}\n"
                f"VID: 0x{dev.get('vid', '0000')} | PID: 0x{dev.get('pid', '0000')}\n"
                f"{self.t('dev_hw_buttons')} {dev.get('num_buttons', 'N/A')}\n"
                f"{self.t('dev_hw_axes')} {dev.get('num_axes', 'N/A')}\n"
                f"{self.t('dev_hw_hats')} {dev.get('num_hats', 'N/A')}\n"
                f"{self.t('dev_hw_guid')} {dev.get('guid', 'N/A')}"
            )
            pname = dev.get('product_name', dev.get('name', ''))
            messagebox.showinfo(self.t("dev_hw_title", name=pname), info_text)

        def hide_selected_device():
            if not has_hidhide:
                return

            selected = tree.selection()
            if not selected:
                messagebox.showinfo("HidHide", self.t("dev_select_device"))
                return
            item = tree.item(selected[0])
            tags = item.get("tags", [])
            dev_id = tags[0] if tags else ""
            dev = next((d for d in self.available_devices if d["id"] == dev_id), None)
            if not dev:
                return

            # No permitir ocultar teclados ni ratones
            if dev.get("type") != "joystick" or dev["id"].startswith("kbd_") or dev["id"] in ("keyboard", "mouse"):
                return

            inst_path = dev.get("instance_path")
            if not inst_path:
                messagebox.showwarning("HidHide", self.t("dev_no_pnp_path"))
                return

            hidden_list = self.config.setdefault("hidden_devices", [])
            if inst_path not in hidden_list:
                hidden_list.append(inst_path)
                self.save_config(silent=True)

            if self.engine.is_running():
                self.driver_manager.hide_device(inst_path)
                messagebox.showinfo(
                    "HidHide",
                    self.t("dev_hide_active_msg", name=dev.get('product_name'))
                )
            else:
                messagebox.showinfo(
                    "HidHide",
                    self.t("dev_hide_marked_msg", name=dev.get('product_name'))
                )
            populate_tree()

        def unhide_selected_device():
            if not has_hidhide:
                return

            selected = tree.selection()
            if not selected:
                messagebox.showinfo("HidHide", self.t("dev_select_device"))
                return
            item = tree.item(selected[0])
            tags = item.get("tags", [])
            dev_id = tags[0] if tags else ""
            dev = next((d for d in self.available_devices if d["id"] == dev_id), None)
            if not dev:
                return

            inst_path = dev.get("instance_path")
            if not inst_path:
                messagebox.showwarning("HidHide", self.t("dev_no_pnp_path"))
                return

            hidden_list = self.config.setdefault("hidden_devices", [])
            if inst_path in hidden_list:
                hidden_list.remove(inst_path)
                self.save_config(silent=True)

            self.driver_manager.unhide_device(inst_path)
            messagebox.showinfo(
                "HidHide",
                self.t("dev_unhide_msg", name=dev.get('product_name'))
            )
            populate_tree()

        tree.bind("<<TreeviewSelect>>", lambda e: update_button_states())

        populate_tree()

        # Boton inferior para asignar al mando actual
        bottom_box = ttk.Frame(main_f)
        bottom_box.pack(fill=tk.X, pady=(6, 0))

        def assign_to_current_tab():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo(self.t("dev_btn_assign"), self.t("dev_select_device"))
                return
            item = tree.item(selected[0])
            tags = item.get("tags", [])
            if not tags:
                return
            dev_id = tags[0]

            cur_pad_id = self.notebook.index(self.notebook.select()) + 1
            if cur_pad_id in self.tab_widgets:
                cb = self.tab_widgets[cur_pad_id]["dev_combo"]
                for idx, d in enumerate(self.available_devices):
                    if d["id"] == dev_id:
                        cb.current(idx)
                        self._on_device_selected(cur_pad_id)
                        break
                populate_tree()
                messagebox.showinfo(self.t("dev_dlg_title"), self.t("dev_assign_success", id=cur_pad_id))
            else:
                messagebox.showwarning(self.t("dev_dlg_title"), "Selecciona una pestaña de control (Control 1 a 12) antes de asignar.")

        ttk.Button(bottom_box, text=self.t("dev_btn_assign"), command=assign_to_current_tab).pack(side=tk.LEFT, padx=4)

        hidhide_status_text = self.t("dev_hidhide_active_bar") if has_hidhide else self.t("dev_hidhide_missing_bar")
        hidhide_status_color = "#008800" if has_hidhide else "#888888"
        lbl_hid_status = ttk.Label(bottom_box, text=hidhide_status_text, font=("Segoe UI", 8, "italic"), foreground=hidhide_status_color)
        lbl_hid_status.pack(side=tk.LEFT, padx=8)

        ttk.Button(bottom_box, text=self.t("dev_btn_close"), command=dlg.destroy).pack(side=tk.RIGHT, padx=4)

    def _open_copy_dialog(self, source_pad_id: int):
        self._sync_ui_to_config()
        src_cfg = self.config.get("controllers", {}).get(str(source_pad_id), {})
        src_maps = json.loads(json.dumps(src_cfg.get("mappings", {})))
        src_calib = json.loads(json.dumps(src_cfg.get("calibration", {})))

        max_ctrls = self.config.get("max_controllers", 12)

        dlg = tk.Toplevel(self.root)
        dlg.title(self.t("copy_dlg_title"))
        dlg.geometry("400x240")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        x = max(0, self.root.winfo_x() + (self.root.winfo_width() // 2) - 200)
        y = max(0, self.root.winfo_y() + (self.root.winfo_height() // 2) - 120)
        dlg.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=self.t("copy_from_pad", id=source_pad_id), font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 6))

        ttk.Label(frame, text=self.t("dest_controller")).pack(anchor="w")
        all_others_label = self.t("dest_all_others", max=max_ctrls)
        dest_options = [all_others_label] + [self.t("dest_pad_item", id=i) for i in range(1, max_ctrls + 1) if i != source_pad_id]
        dest_var = tk.StringVar(value=dest_options[0])
        cb_dest = ttk.Combobox(frame, values=dest_options, textvariable=dest_var, state="readonly", font=("Segoe UI", 9))
        cb_dest.pack(fill=tk.X, pady=4)

        inc_calib_var = tk.BooleanVar(value=True)
        chk_calib = ttk.Checkbutton(frame, text=self.t("inc_calib"), variable=inc_calib_var)
        chk_calib.pack(anchor="w", pady=6)

        note_lbl = ttk.Label(frame, text=self.t("copy_note"), font=("Segoe UI", 8, "italic"), foreground="#555555")
        note_lbl.pack(anchor="w", pady=(0, 10))

        btn_box = ttk.Frame(frame)
        btn_box.pack(fill=tk.X, side=tk.BOTTOM)

        def do_copy():
            choice = dest_var.get()
            target_ids = []
            if choice == all_others_label:
                target_ids = [i for i in range(1, max_ctrls + 1) if i != source_pad_id]
            else:
                try:
                    t_id = int(choice.split()[-1])
                    target_ids = [t_id]
                except Exception:
                    pass

            for tid in target_ids:
                str_tid = str(tid)
                if str_tid not in self.config.get("controllers", {}):
                    self.config["controllers"][str_tid] = {}
                self.config["controllers"][str_tid]["mappings"] = json.loads(json.dumps(src_maps))
                if inc_calib_var.get():
                    self.config["controllers"][str_tid]["calibration"] = json.loads(json.dumps(src_calib))

                if tid in self.tab_widgets:
                    t_w = self.tab_widgets[tid]
                    for target, cb in t_w.get("combos", {}).items():
                        cb.set(src_maps.get(target, "-- Ninguno --"))
                    if inc_calib_var.get():
                        c_w = t_w.get("calib", {})
                        for k in ["left_trigger", "right_trigger"]:
                            if k in c_w and k in src_calib:
                                for vkey, dkey, def_v in [("dz_var", "deadzone", 0), ("adz_var", "anti_deadzone", 0), ("sens_var", "sensitivity", 0)]:
                                    val = src_calib[k].get(dkey, def_v)
                                    c_w[k][vkey].set(val)
                                    if f"{vkey}_scale" in c_w[k]: c_w[k][f"{vkey}_scale"].set(round(val))
                                    if f"{vkey}_entry" in c_w[k]: c_w[k][f"{vkey}_entry"].set(f"{val:g}")
                                c_w[k]["inv_var"].set(src_calib[k].get("invert", False))
                        for k in ["left_stick", "right_stick"]:
                            if k in c_w and k in src_calib:
                                for vkey, dkey, def_v in [("dz_var", "deadzone", 8), ("adz_var", "anti_deadzone", 0), ("sens_var", "sensitivity", 0)]:
                                    val = src_calib[k].get(dkey, def_v)
                                    c_w[k][vkey].set(val)
                                    if f"{vkey}_scale" in c_w[k]: c_w[k][f"{vkey}_scale"].set(round(val))
                                    if f"{vkey}_entry" in c_w[k]: c_w[k][f"{vkey}_entry"].set(f"{val:g}")
                                c_w[k]["inv_x_var"].set(src_calib[k].get("invert_x", False))
                                c_w[k]["inv_y_var"].set(src_calib[k].get("invert_y", False))

            self.engine.set_config(self.config)
            dlg.destroy()
            dest_msg = all_others_label if choice == all_others_label else choice
            messagebox.showinfo(self.t("copy_success_title"), self.t("copy_success_msg", dest=dest_msg))

        btn_ok = ttk.Button(btn_box, text=self.t("btn_copy_submit"), command=do_copy)
        btn_ok.pack(side=tk.RIGHT, padx=4)

        btn_cancel = ttk.Button(btn_box, text=self.t("set_btn_cancel"), command=dlg.destroy)
        btn_cancel.pack(side=tk.RIGHT, padx=4)

    def _open_wizard_dialog(self, pad_id: int):
        cfg = self.config.get("controllers", {}).get(str(pad_id), {})
        dev_id = cfg.get("physical_device_id", "none")
        if dev_id == "none":
            messagebox.showwarning(self.t("wizard_title", id=pad_id), self.t("wizard_no_device"))
            return

        BASE_SEQUENCE = [
            # Cruceta / D-Pad
            "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT",
            # Botones Principales
            "A", "B", "X", "Y",
            # Botones Centrales / Menú
            "START", "BACK", "GUIDE",
            # Bumpers y Gatillos
            "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_TRIGGER", "RIGHT_TRIGGER",
            # Stick Izquierdo
            "LEFT_THUMB", "LEFT_STICK_X", "LEFT_STICK_Y",
            # Stick Derecho
            "RIGHT_THUMB", "RIGHT_STICK_X", "RIGHT_STICK_Y"
        ]

        LEFT_STICK_DISCRETE = ["LEFT_STICK_UP", "LEFT_STICK_DOWN", "LEFT_STICK_LEFT", "LEFT_STICK_RIGHT"]
        RIGHT_STICK_DISCRETE = ["RIGHT_STICK_UP", "RIGHT_STICK_DOWN", "RIGHT_STICK_LEFT", "RIGHT_STICK_RIGHT"]

        staged_mappings = {}
        skipped_targets = set()
        steps_queue = list(BASE_SEQUENCE)
        current_step_idx = 0

        dlg = tk.Toplevel(self.root)
        dlg.title(self.t("wizard_title", id=pad_id))
        dlg.geometry("670x505")
        dlg.resizable(False, False)
        dlg.transient(self.root)

        dlg.update_idletasks()
        pw = self.root.winfo_width()
        ph = self.root.winfo_height()
        px = self.root.winfo_rootx()
        py = self.root.winfo_rooty()
        dw, dh = 670, 505
        pos_x = max(0, px + (pw - dw) // 2)
        pos_y = max(0, py + (ph - dh) // 2)
        dlg.geometry(f"{dw}x{dh}+{pos_x}+{pos_y}")

        dlg.lift()
        dlg.focus_force()
        dlg.grab_set()

        header_frame = ttk.Frame(dlg, padding="10 6 10 2")
        header_frame.pack(fill=tk.X)

        top_info = ttk.Frame(header_frame)
        top_info.pack(fill=tk.X)

        lbl_step = ttk.Label(top_info, text="", font=("Segoe UI", 9, "bold"), foreground="#0066cc")
        lbl_step.pack(side=tk.LEFT)

        prog_bar = ttk.Progressbar(header_frame, orient="horizontal", mode="determinate")
        prog_bar.pack(fill=tk.X, pady=(2, 4))

        lbl_target_name = ttk.Label(header_frame, text="", font=("Segoe UI", 13, "bold"), foreground="#111111")
        lbl_target_name.pack(anchor="center")

        lbl_target_hint = ttk.Label(header_frame, text="", font=("Segoe UI", 9, "italic"), foreground="#555555")
        lbl_target_hint.pack(anchor="center", pady=(1, 2))

        center_frame = ttk.Frame(dlg, padding="10 2 10 2")
        center_frame.pack(fill=tk.X)

        left_box = ttk.LabelFrame(center_frame, text=f" {self.t('subtab_general')} - {self.t('wizard_official_pad')} ", padding=2)
        left_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        cv_main = tk.Canvas(left_box, width=350, height=275, bg="#ffffff", highlightthickness=1, highlightbackground="#d0d0d0")
        cv_main.pack(anchor="center", pady=2)

        if self.controller_img_tk:
            cv_main.create_image(175, 137, image=self.controller_img_tk)

        main_halo = cv_main.create_oval(0, 0, 0, 0, outline="#ff2200", width=3, state="hidden")
        main_core = cv_main.create_oval(0, 0, 0, 0, fill="#ffaa00", outline="#ffffff", width=1.5, state="hidden")

        right_box = ttk.LabelFrame(center_frame, text=f" {self.t('wizard_zoom_title')} ", padding=2)
        right_box.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        cv_zoom = tk.Canvas(right_box, width=240, height=240, bg="#f8f9fa", highlightthickness=1, highlightbackground="#d0d0d0")
        cv_zoom.pack(anchor="center", pady=2)

        zoom_img_holder = [None]

        status_frame = ttk.Frame(dlg, padding="10 2 10 2")
        status_frame.pack(fill=tk.X)

        lbl_status = ttk.Label(status_frame, text=self.t("wizard_waiting"), font=("Segoe UI", 11, "bold"), foreground="#666666", anchor="center")
        lbl_status.pack(fill=tk.X)

        btn_bar = ttk.Frame(dlg, padding="10 4 10 8")
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM)

        worker_state = {
            "active": True,
            "listening": True,
            "current_target": None,
            "pad_id": pad_id,
            "dev_id": dev_id
        }

        def get_hint_text(tgt: str) -> str:
            if "TRIGGER" in tgt:
                return self.t("wizard_hint_trigger")
            elif "SHOULDER" in tgt:
                return self.t("wizard_hint_bumper")
            elif tgt in ("A", "B", "X", "Y"):
                return self.t("wizard_hint_btn", btn=tgt)
            elif tgt == "START":
                return self.t("wizard_hint_start")
            elif tgt == "BACK":
                return self.t("wizard_hint_back")
            elif tgt == "GUIDE":
                return self.t("wizard_hint_guide")
            elif tgt in ("LEFT_THUMB", "RIGHT_THUMB"):
                return self.t("wizard_hint_thumb")
            elif "STICK_X" in tgt:
                return self.t("wizard_hint_stick_x")
            elif "STICK_Y" in tgt:
                return self.t("wizard_hint_stick_y")
            elif "STICK" in tgt and any(d in tgt for d in ("UP", "DOWN", "LEFT", "RIGHT")):
                return self.t("wizard_hint_stick_dir")
            elif "DPAD" in tgt:
                return self.t("wizard_hint_dpad")
            return self.t("wizard_hint_default")

        def update_ui_for_target(tgt: str):
            nonlocal current_step_idx
            worker_state["current_target"] = tgt
            worker_state["listening"] = True

            total = len(steps_queue)
            cur = current_step_idx + 1
            pct = int((cur / total) * 100)
            lbl_step.config(text=f"{self.t('wizard_step', cur=cur, total=total)} ({pct}%)")
            prog_bar["value"] = pct

            lbl_target_name.config(text=f"👉 {self.target_name(tgt)}")
            lbl_target_hint.config(text=get_hint_text(tgt))
            lbl_status.config(text=self.t("wizard_waiting"), foreground="#666666")

            canvas_key = map_target_to_canvas_key(tgt)
            pt = CANVAS_POINTS.get(canvas_key, (175.0, 137.5, 10))
            cx, cy = pt[0], pt[1]

            cv_main.coords(main_halo, cx - 14, cy - 14, cx + 14, cy + 14)
            cv_main.coords(main_core, cx - 6, cy - 6, cx + 6, cy + 6)
            cv_main.itemconfig(main_halo, outline="#ff2200", state="normal")
            cv_main.itemconfig(main_core, fill="#ffaa00", state="normal")

            cv_zoom.delete("all")
            source_img = self.controller_pil_hires or self.controller_pil_base
            if source_img:
                try:
                    scale_x = source_img.width / 350.0
                    scale_y = source_img.height / 275.0
                    hi_cx = cx * scale_x
                    hi_cy = cy * scale_y
                    crop_r_x = 42.0 * scale_x
                    crop_r_y = 42.0 * scale_y

                    x0 = max(0, int(hi_cx - crop_r_x))
                    y0 = max(0, int(hi_cy - crop_r_y))
                    x1 = min(source_img.width, int(hi_cx + crop_r_x))
                    y1 = min(source_img.height, int(hi_cy + crop_r_y))

                    cropped = source_img.crop((x0, y0, x1, y1))
                    zoomed = cropped.resize((240, 240), Image.Resampling.LANCZOS)
                    zoom_img_holder[0] = ImageTk.PhotoImage(zoomed)
                    cv_zoom.create_image(120, 120, image=zoom_img_holder[0])
                except Exception as ex:
                    print(f"[!] Error generando zoom: {ex}")

            cv_zoom.create_oval(120 - 30, 120 - 30, 120 + 30, 120 + 30, outline="#ff2200", width=3)
            cv_zoom.create_oval(120 - 4, 120 - 4, 120 + 4, 120 + 4, fill="#ff2200", outline="#ffffff", width=1)
            cv_zoom.create_line(120 - 45, 120, 120 - 32, 120, fill="#ff2200", width=2)
            cv_zoom.create_line(120 + 32, 120, 120 + 45, 120, fill="#ff2200", width=2)
            cv_zoom.create_line(120, 120 - 45, 120, 120 - 32, fill="#ff2200", width=2)
            cv_zoom.create_line(120, 120 + 32, 120, 120 + 45, fill="#ff2200", width=2)

        advance_timer = [None]

        def cancel_advance_timer():
            if advance_timer[0] is not None:
                try:
                    dlg.after_cancel(advance_timer[0])
                except Exception:
                    pass
                advance_timer[0] = None

        def update_button_states():
            if current_step_idx > 0:
                btn_back.config(state=tk.NORMAL)
            else:
                btn_back.config(state=tk.DISABLED)

        def advance():
            cancel_advance_timer()
            nonlocal current_step_idx
            cur_tgt = worker_state["current_target"]

            if cur_tgt == "LEFT_STICK_Y":
                if "LEFT_STICK_X" not in staged_mappings or "LEFT_STICK_Y" not in staged_mappings:
                    if not any(t in steps_queue for t in LEFT_STICK_DISCRETE):
                        for off, t in enumerate(LEFT_STICK_DISCRETE):
                            steps_queue.insert(current_step_idx + 1 + off, t)
            elif cur_tgt == "RIGHT_STICK_Y":
                if "RIGHT_STICK_X" not in staged_mappings or "RIGHT_STICK_Y" not in staged_mappings:
                    if not any(t in steps_queue for t in RIGHT_STICK_DISCRETE):
                        for off, t in enumerate(RIGHT_STICK_DISCRETE):
                            steps_queue.insert(current_step_idx + 1 + off, t)

            current_step_idx += 1
            if current_step_idx < len(steps_queue):
                update_ui_for_target(steps_queue[current_step_idx])
                update_button_states()
            else:
                on_finish()

        def on_detected(detected_val: str):
            if not worker_state["active"] or not worker_state["listening"]:
                return
            worker_state["listening"] = False

            tgt = worker_state["current_target"]
            staged_mappings[tgt] = detected_val

            lbl_status.config(text=self.t("wizard_detected", input=detected_val), foreground="#009922")
            cv_main.itemconfig(main_halo, outline="#00cc44")
            cv_main.itemconfig(main_core, fill="#00ff66")
            cv_zoom.create_oval(120 - 35, 120 - 35, 120 + 35, 120 + 35, outline="#00cc44", width=5)

            cancel_advance_timer()
            advance_timer[0] = dlg.after(350, advance)

        def on_back():
            if not worker_state["active"]:
                return
            cancel_advance_timer()
            worker_state["listening"] = False

            nonlocal current_step_idx
            if current_step_idx > 0:
                # Si el paso actual tenía mapeo recién capturado o saltado, se limpia
                cur_tgt = worker_state["current_target"]
                staged_mappings.pop(cur_tgt, None)
                skipped_targets.discard(cur_tgt)

                current_step_idx -= 1
                prev_tgt = steps_queue[current_step_idx]

                # Si retrocedemos a un paso de stick analógico tras haber insertado discretos
                if prev_tgt == "LEFT_STICK_Y":
                    # Si estaban los discretos insertados a continuación, retirarlos para reevaluar
                    for t in LEFT_STICK_DISCRETE:
                        if t in steps_queue:
                            steps_queue.remove(t)
                            staged_mappings.pop(t, None)
                            skipped_targets.discard(t)
                elif prev_tgt == "RIGHT_STICK_Y":
                    for t in RIGHT_STICK_DISCRETE:
                        if t in steps_queue:
                            steps_queue.remove(t)
                            staged_mappings.pop(t, None)
                            skipped_targets.discard(t)

                # También permitimos sobreescribir el paso anterior
                staged_mappings.pop(prev_tgt, None)
                skipped_targets.discard(prev_tgt)

                update_ui_for_target(prev_tgt)
                update_button_states()

        def on_skip():
            if not worker_state["active"]:
                return
            cancel_advance_timer()
            worker_state["listening"] = False
            tgt = worker_state["current_target"]
            skipped_targets.add(tgt)
            advance()

        def on_finish():
            cancel_advance_timer()
            worker_state["active"] = False
            worker_state["listening"] = False
            self.device_manager.cancel_capture()

            widgets = self.tab_widgets.get(pad_id)
            if widgets and "combos" in widgets:
                combos = widgets["combos"]
                for t, v in staged_mappings.items():
                    if t in combos:
                        combos[t].set(v)

            self._sync_ui_to_config()
            self.save_config(silent=True)

            try:
                dlg.destroy()
            except Exception:
                pass

            messagebox.showinfo(self.t("wizard_completed_title"), self.t("wizard_completed_msg", id=pad_id))

        def on_cancel():
            cancel_advance_timer()
            worker_state["active"] = False
            worker_state["listening"] = False
            self.device_manager.cancel_capture()
            try:
                dlg.destroy()
            except Exception:
                pass

        btn_cancel = ttk.Button(btn_bar, text=self.t("wizard_btn_cancel"), command=on_cancel)
        btn_cancel.pack(side=tk.LEFT, padx=4)

        btn_back = ttk.Button(btn_bar, text=self.t("wizard_btn_back"), command=on_back, state=tk.DISABLED)
        btn_back.pack(side=tk.LEFT, padx=(12, 4))

        btn_skip = ttk.Button(btn_bar, text=self.t("wizard_btn_skip"), command=on_skip)
        btn_skip.pack(side=tk.LEFT, padx=4)

        btn_finish = ttk.Button(btn_bar, text=self.t("wizard_btn_finish"), command=on_finish)
        btn_finish.pack(side=tk.RIGHT, padx=4)

        dlg.protocol("WM_DELETE_WINDOW", on_cancel)

        if dev_id == "keyboard":
            def on_key_event(event):
                if not worker_state["active"] or not worker_state["listening"]:
                    return
                if event.keysym.lower() in ("escape", "esc") or event.keycode == 27:
                    on_cancel()
                    return
                k_name = event.keysym.lower()
                on_detected(f"Tecla: {k_name}")

            dlg.bind("<KeyPress>", on_key_event)
        else:
            dlg.bind("<Escape>", lambda e: on_cancel())

        def capture_thread_func():
            time.sleep(0.1)
            while worker_state["active"]:
                if worker_state["listening"] and dev_id.startswith("joy_"):
                    cur_tgt = worker_state.get("current_target", "")
                    det = self.device_manager.capture_input(dev_id, timeout=0.08, target_name=cur_tgt)
                    if det and worker_state["active"] and worker_state["listening"]:
                        dlg.after(0, lambda d=det: on_detected(d))
                        time.sleep(0.2)
                time.sleep(0.01)

        threading.Thread(target=capture_thread_func, daemon=True).start()

        update_ui_for_target(steps_queue[0])
        dlg.after(50, lambda: dlg.focus_force())


    def _open_joy_cpl(self):
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.Popen(["joy.cpl"], shell=True, creationflags=flags)
        except Exception as e:
            messagebox.showerror("Error", self.t("joy_cpl_error", e=e))

    def _draw_trigger_graph(self, cv: tk.Canvas, dz: int, adz: int, sens: int, inv: bool, raw_val: float, out_byte: int):
        cv.delete("all")
        w = cv.winfo_width()
        h = cv.winfo_height()
        if w < 10 or h < 10:
            w, h = int(cv.cget("width")), int(cv.cget("height"))

        pad = 10
        gw = max(10, w - 2 * pad)
        gh = max(10, h - 2 * pad)

        cv.create_rectangle(pad, pad, pad + gw, pad + gh, fill="#fdfdfd", outline="#dddddd")
        cv.create_line(pad, pad + gh, pad + gw, pad + gh, fill="#aaaaaa")
        cv.create_line(pad, pad, pad, pad + gh, fill="#aaaaaa")

        points = []
        steps = 25
        for i in range(steps + 1):
            t = i / steps
            out_v = apply_trigger_calibration(t, dz, adz, sens, inv)
            px = pad + t * gw
            py = (pad + gh) - (out_v * gh)
            points.extend([px, py])

        if len(points) >= 4:
            cv.create_line(points, fill="#e62e2e", width=2)

        dot_x = pad + max(0.0, min(1.0, raw_val)) * gw
        dot_y = (pad + gh) - ((out_byte / 255.0) * gh)
        cv.create_line(dot_x, pad, dot_x, pad + gh, fill="#39ff14", dash=(2, 2))
        cv.create_oval(dot_x - 3, dot_y - 3, dot_x + 3, dot_y + 3, fill="#00aa00", outline="#ffffff", width=1)

    def _draw_stick_canvas(self, cv: tk.Canvas, dz: int, adz: int, x_val: float, y_val: float):
        cv.delete("all")
        w = cv.winfo_width()
        h = cv.winfo_height()
        if w < 10 or h < 10:
            w, h = int(cv.cget("width")), int(cv.cget("height"))

        cx, cy = w // 2, h // 2
        r_max = (min(w, h) // 2) - 8

        cv.create_rectangle(4, 4, w - 4, h - 4, fill="#fafafa", outline="#e0e0e0")
        cv.create_line(cx, 4, cx, h - 4, fill="#dddddd")
        cv.create_line(4, cy, w - 4, cy, fill="#dddddd")
        cv.create_oval(cx - r_max, cy - r_max, cx + r_max, cy + r_max, outline="#cccccc", width=1)

        dz_r = r_max * (dz / 100.0)
        if dz_r > 1:
            cv.create_oval(cx - dz_r, cy - dz_r, cx + dz_r, cy + dz_r, fill="#ffeeee", outline="#ff9999", dash=(2, 2))

        adz_r = r_max * (adz / 100.0)
        if adz_r > 1:
            cv.create_oval(cx - adz_r, cy - adz_r, cx + adz_r, cy + adz_r, outline="#99bbff", dash=(2, 2))

        dot_x = cx + max(-1.0, min(1.0, x_val)) * r_max
        dot_y = cy - max(-1.0, min(1.0, y_val)) * r_max
        cv.create_oval(dot_x - 3, dot_y - 3, dot_x + 3, dot_y + 3, fill="#00bb00", outline="#ffffff", width=1)

    def _draw_stick_curve(self, cv: tk.Canvas, dz: int, adz: int, sens: int, raw_mag: float, out_mag: float):
        cv.delete("all")
        w = cv.winfo_width()
        h = cv.winfo_height()
        if w < 10 or h < 10:
            w, h = int(cv.cget("width")), int(cv.cget("height"))

        pad = 10
        gw = max(10, w - 2 * pad)
        gh = max(10, h - 2 * pad)

        cv.create_rectangle(pad, pad, pad + gw, pad + gh, fill="#fdfdfd", outline="#dddddd")
        cv.create_line(pad, pad + gh, pad + gw, pad + gh, fill="#aaaaaa")
        cv.create_line(pad, pad, pad, pad + gh, fill="#aaaaaa")

        points = []
        steps = 25
        for i in range(steps + 1):
            t = i / steps
            out_v = apply_axis_calibration(t, dz, adz, sens, invert=False)
            px = pad + t * gw
            py = (pad + gh) - (out_v * gh)
            points.extend([px, py])

        if len(points) >= 4:
            cv.create_line(points, fill="#e62e2e", width=2)

        dot_x = pad + max(0.0, min(1.0, raw_mag)) * gw
        dot_y = (pad + gh) - (max(0.0, min(1.0, out_mag)) * gh)
        cv.create_line(dot_x, pad, dot_x, pad + gh, fill="#39ff14", dash=(2, 2))
        cv.create_oval(dot_x - 3, dot_y - 3, dot_x + 3, dot_y + 3, fill="#00aa00", outline="#ffffff", width=1)

    def _update_loop(self):
        try:
            cur_pad_id = self.notebook.index(self.notebook.select()) + 1
            widgets = self.tab_widgets.get(cur_pad_id)

            if widgets:
                # Si la emulacion no esta activa, computamos el estado en tiempo real
                # para que los controles respondan y se iluminen inmediatamente al probar
                if self.engine.is_running():
                    state = self.engine.get_active_state(cur_pad_id)
                else:
                    state = self.engine.compute_controller_state(cur_pad_id)

                canvas = widgets.get("canvas")
                leds = widgets.get("leds", {})
                rec_ind = widgets.get("rec_indicators", {})

                # 1. Comprobar si hay una tecla/boton en proceso de asignacion
                rec_canvas_key = None
                if self.recording_target:
                    rec_pad, rec_name, _ = self.recording_target
                    if rec_pad == cur_pad_id:
                        rec_canvas_key = map_target_to_canvas_key(rec_name)

                # Animacion llamativa del boton en modo ASIGNACION (halo pulsante ambar/rojo)
                if canvas and rec_ind:
                    if rec_canvas_key and rec_canvas_key in CANVAS_POINTS:
                        cx, cy, r = CANVAS_POINTS[rec_canvas_key]
                        t = time.time()
                        pulse = (math.sin(t * 10) + 1.0) / 2.0  # 0..1 oscila a ~1.6 Hz
                        halo_r = r + 3 + int(pulse * 5)
                        halo_col = "#ff3300" if pulse > 0.45 else "#ff9900"
                        canvas.coords(rec_ind["halo"], cx - halo_r, cy - halo_r, cx + halo_r, cy + halo_r)
                        canvas.itemconfig(rec_ind["halo"], state="normal", outline=halo_col, width=3)

                        canvas.coords(rec_ind["core"], cx - r, cy - r, cx + r, cy + r)
                        canvas.itemconfig(rec_ind["core"], state="normal", fill="#ffaa00", outline="#ffffff", width=2)
                    else:
                        canvas.itemconfig(rec_ind["halo"], state="hidden")
                        canvas.itemconfig(rec_ind["core"], state="hidden")

                # 2. Indicadores reactivos de botones OPRIMIDOS (verde neon brillante con halo)
                if canvas and leds:
                    pressed_btns = state.get("buttons", set())
                    for btn_name, (tag, glow) in leds.items():
                        is_active = False
                        if btn_name in pressed_btns:
                            is_active = True
                        elif btn_name == "LEFT_TRIGGER" and (state.get("lt", 0) > 25 or "LEFT_TRIGGER" in pressed_btns):
                            is_active = True
                        elif btn_name == "RIGHT_TRIGGER" and (state.get("rt", 0) > 25 or "RIGHT_TRIGGER" in pressed_btns):
                            is_active = True
                        elif btn_name == "LEFT_STICK_UP" and (state.get("ly", 0.0) < -0.2 or "LEFT_STICK_UP" in pressed_btns):
                            is_active = True
                        elif btn_name == "LEFT_STICK_DOWN" and (state.get("ly", 0.0) > 0.2 or "LEFT_STICK_DOWN" in pressed_btns):
                            is_active = True
                        elif btn_name == "LEFT_STICK_LEFT" and (state.get("lx", 0.0) < -0.2 or "LEFT_STICK_LEFT" in pressed_btns):
                            is_active = True
                        elif btn_name == "LEFT_STICK_RIGHT" and (state.get("lx", 0.0) > 0.2 or "LEFT_STICK_RIGHT" in pressed_btns):
                            is_active = True
                        elif btn_name == "LEFT_THUMB" and ("LEFT_THUMB" in pressed_btns):
                            is_active = True
                        elif btn_name == "RIGHT_STICK_UP" and (state.get("ry", 0.0) < -0.2 or "RIGHT_STICK_UP" in pressed_btns):
                            is_active = True
                        elif btn_name == "RIGHT_STICK_DOWN" and (state.get("ry", 0.0) > 0.2 or "RIGHT_STICK_DOWN" in pressed_btns):
                            is_active = True
                        elif btn_name == "RIGHT_STICK_LEFT" and (state.get("rx", 0.0) < -0.2 or "RIGHT_STICK_LEFT" in pressed_btns):
                            is_active = True
                        elif btn_name == "RIGHT_STICK_RIGHT" and (state.get("rx", 0.0) > 0.2 or "RIGHT_STICK_RIGHT" in pressed_btns):
                            is_active = True
                        elif btn_name == "RIGHT_THUMB" and ("RIGHT_THUMB" in pressed_btns):
                            is_active = True

                        new_state = "normal" if is_active else "hidden"
                        canvas.itemconfig(tag, state=new_state)
                        canvas.itemconfig(glow, state=new_state)
                        if is_active:
                            canvas.tag_raise(glow)
                            canvas.tag_raise(tag)

                # 2. Triggers
                c_w = widgets.get("calib", {})
                for trig_key, raw_k, out_k in [("left_trigger", "lt_raw", "lt"), ("right_trigger", "rt_raw", "rt")]:
                    if trig_key in c_w:
                        tw = c_w[trig_key]
                        dz = tw["dz_var"].get()
                        adz = tw["adz_var"].get()
                        sens = tw["sens_var"].get()
                        inv = tw["inv_var"].get()

                        raw_val = state.get(raw_k, 0.0)
                        out_byte = state.get(out_k, 0)

                        self._draw_trigger_graph(tw["canvas"], dz, adz, sens, inv, raw_val, out_byte)
                        tw["lbl_di_xi"].config(text=f"DI: {int(raw_val * 32767):5d}    XI: {out_byte:3d}")

                # 3. Sticks
                for stick_key, rx_k, ry_k, cx_k, cy_k in [
                    ("left_stick", "lx_raw", "ly_raw", "lx", "ly"),
                    ("right_stick", "rx_raw", "ry_raw", "rx", "ry")
                ]:
                    if stick_key in c_w:
                        sw = c_w[stick_key]
                        dz = sw["dz_var"].get()
                        adz = sw["adz_var"].get()
                        sens = sw["sens_var"].get()

                        raw_x = state.get(rx_k, 0.0)
                        raw_y = state.get(ry_k, 0.0)
                        cal_x = state.get(cx_k, 0.0)
                        cal_y = state.get(cy_k, 0.0)

                        # En representacion visual cartesiana (tipo Xbox/x360ce):
                        # Arriba es +Y y Abajo es -Y. En Pygame Y hacia arriba es negativo, por lo que invertimos para la visualizacion 2D
                        disp_y = -cal_y

                        self._draw_stick_canvas(sw["canvas"], dz, adz, cal_x, disp_y)
                        sw["lbl_xy"].config(text=f"X: {cal_x:+0.2f}  Y: {disp_y:+0.2f}")

                        raw_mag = min(1.0, math.sqrt(raw_x**2 + raw_y**2))
                        out_mag = min(1.0, math.sqrt(cal_x**2 + cal_y**2))
                        self._draw_stick_curve(sw["curve_canvas"], dz, adz, sens, raw_mag, out_mag)
                        sw["lbl_di_xi"].config(text=f"DI: {int(raw_mag * 32767):5d}    XI: {int(out_mag * 32767):5d}")

        except Exception:
            pass

        self.root.after(30, self._update_loop)

    # =========================================================================
    # PESTAÑA DE JUEGOS: SOPORTE MULTI-GAMEPAD (+4 MANDOS CON VARIABLES ENV)
    # =========================================================================
    def _build_games_tab(self, parent: ttk.Frame):
        """Construye la interfaz de la pestaña de Juegos para gestionar y lanzar con variables ENV."""
        # Barra superior de acciones
        actions_bar = ttk.Frame(parent, padding=4)
        actions_bar.pack(fill=tk.X, pady=(0, 4))

        btn_add = ttk.Button(actions_bar, text=self.t("btn_add_game"), command=lambda: self._open_game_editor_dialog(None))
        btn_add.pack(side=tk.LEFT, padx=4)

        btn_edit = ttk.Button(actions_bar, text=self.t("btn_edit_game"), command=self._edit_selected_game)
        btn_edit.pack(side=tk.LEFT, padx=4)

        btn_del = ttk.Button(actions_bar, text=self.t("btn_delete_game"), command=self._delete_selected_game)
        btn_del.pack(side=tk.LEFT, padx=4)

        btn_launch = ttk.Button(actions_bar, text=self.t("btn_launch_game"), command=self._launch_selected_game)
        btn_launch.pack(side=tk.RIGHT, padx=4)

        # Contenedor para Treeview y Scrollbar
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=2)

        cols = ("title", "path", "env")
        self.games_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.games_tree.heading("title", text=self.t("col_game_title"))
        self.games_tree.heading("path", text=self.t("col_game_path"))
        self.games_tree.heading("env", text=self.t("col_game_env"))

        self.games_tree.column("title", width=220, minwidth=140)
        self.games_tree.column("path", width=420, minwidth=200)
        self.games_tree.column("env", width=300, minwidth=160)

        sb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.games_tree.yview)
        self.games_tree.configure(yscrollcommand=sb.set)

        self.games_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.games_tree.bind("<Double-1>", lambda e: self._launch_selected_game())

        # Pie con nota explicativa
        footer = ttk.Frame(parent, padding=4)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(footer, text=self.t("games_empty_hint"), font=("Segoe UI", 8, "italic"), foreground="#555555").pack(side=tk.LEFT)

        self._populate_games_tree()

    def _populate_games_tree(self):
        """Rellena el Treeview con la lista de juegos registrados."""
        if not hasattr(self, "games_tree"):
            return
        for item in self.games_tree.get_children():
            self.games_tree.delete(item)

        games_list = self.config.get("games", [])
        for idx, g in enumerate(games_list):
            title = g.get("title", f"Juego {idx + 1}")
            path = g.get("path", "")
            active_vars = []
            for v_name, v_cfg in g.get("env_vars", {}).items():
                if isinstance(v_cfg, dict) and v_cfg.get("enabled", False):
                    if v_name == "FNA_GAMEPAD_NUM_GAMEPADS":
                        val = str(self.config.get("max_controllers", 8))
                        active_vars.append(f"FNA({val})")
                    else:
                        val = v_cfg.get("value", "1")
                        clean_n = v_name.replace("SDL_JOYSTICK_", "").replace("SDL_", "")
                        active_vars.append(f"{clean_n}={val}")
            env_summary = ", ".join(active_vars) if active_vars else "Ninguna"
            self.games_tree.insert("", tk.END, iid=str(idx), values=(title, path, env_summary))

    def _edit_selected_game(self):
        sel = self.games_tree.selection()
        if not sel:
            messagebox.showinfo(self.t("tab_games"), self.t("select_game_first"))
            return
        idx = int(sel[0])
        games_list = self.config.get("games", [])
        if 0 <= idx < len(games_list):
            self._open_game_editor_dialog(idx)

    def _delete_selected_game(self):
        sel = self.games_tree.selection()
        if not sel:
            messagebox.showinfo(self.t("tab_games"), self.t("select_game_first"))
            return
        idx = int(sel[0])
        games_list = self.config.get("games", [])
        if 0 <= idx < len(games_list):
            g = games_list[idx]
            if messagebox.askyesno(self.t("btn_delete_game"), self.t("confirm_delete_game", title=g.get("title", ""))):
                games_list.pop(idx)
                self.config["games"] = games_list
                self.save_config(silent=True)
                self._populate_games_tree()

    def _open_game_editor_dialog(self, game_index: Optional[int] = None):
        """Abre la ventana modal para agregar o editar un juego."""
        is_edit = (game_index is not None)
        games_list = self.config.setdefault("games", [])
        game_data = games_list[game_index] if (is_edit and 0 <= game_index < len(games_list)) else {}

        dlg = tk.Toplevel(self.root)
        dlg.title(self.t("dialog_edit_game") if is_edit else self.t("dialog_add_game"))
        dlg.geometry("640x520")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        # Centrar sobre la ventana principal
        x = max(0, self.root.winfo_x() + (self.root.winfo_width() // 2) - 320)
        y = max(0, self.root.winfo_y() + (self.root.winfo_height() // 2) - 260)
        dlg.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dlg, padding=14)
        frame.pack(fill=tk.BOTH, expand=True)

        # 1. Título del juego
        ttk.Label(frame, text=self.t("lbl_game_title"), font=("Segoe UI", 9, "bold")).pack(anchor="w")
        title_var = tk.StringVar(value=game_data.get("title", ""))
        entry_title = ttk.Entry(frame, textvariable=title_var, font=("Segoe UI", 9))
        entry_title.pack(fill=tk.X, pady=(2, 8))

        # 2. Ruta del ejecutable
        ttk.Label(frame, text=self.t("lbl_game_path"), font=("Segoe UI", 9, "bold")).pack(anchor="w")
        path_row = ttk.Frame(frame)
        path_row.pack(fill=tk.X, pady=(2, 8))

        path_var = tk.StringVar(value=game_data.get("path", ""))
        entry_path = ttk.Entry(path_row, textvariable=path_var, font=("Segoe UI", 9))
        entry_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        def on_browse():
            chosen = filedialog.askopenfilename(
                title=self.t("btn_browse_game"),
                filetypes=[
                    ("Ejecutables y Scripts", "*.exe;*.cmd;*.bat"),
                    ("Archivos Ejecutables (*.exe)", "*.exe"),
                    ("Scripts de Comandos (*.cmd, *.bat)", "*.cmd;*.bat"),
                    ("Todos los Archivos (*.*)", "*.*")
                ]
            )
            if chosen:
                path_var.set(chosen)
                if not title_var.get().strip():
                    # Autocompletar título con el nombre base sin extensión
                    base_name = os.path.splitext(os.path.basename(chosen))[0]
                    title_var.set(base_name.replace("_", " ").replace("-", " ").title())

        btn_browse = ttk.Button(path_row, text=self.t("btn_browse_game"), command=on_browse)
        btn_browse.pack(side=tk.RIGHT)

        # 3. Argumentos adicionales
        ttk.Label(frame, text=self.t("lbl_game_args"), font=("Segoe UI", 8)).pack(anchor="w")
        args_var = tk.StringVar(value=game_data.get("args", ""))
        entry_args = ttk.Entry(frame, textvariable=args_var, font=("Segoe UI", 8))
        entry_args.pack(fill=tk.X, pady=(2, 10))

        # 4. Grupo de Variables de Entorno
        box_env = ttk.LabelFrame(frame, text=self.t("grp_env_vars"), padding=8)
        box_env.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        ttk.Label(box_env, text=self.t("env_hint"), font=("Segoe UI", 8, "italic"), foreground="#555555").pack(anchor="w", pady=(0, 6))

        saved_envs = game_data.get("env_vars", {})
        env_checkboxes = {}

        # Definición de variables estándar
        default_max = str(self.config.get("max_controllers", 8))
        env_specs = [
            ("FNA_GAMEPAD_NUM_GAMEPADS", True, default_max, f"Ajustado según mandos virtuales a emular ({default_max} mandos)"),
            ("SDL_JOYSTICK_DIRECTINPUT", True, "1", "Habilita la enumeración mediante la API DirectInput de Windows"),
            ("SDL_JOYSTICK_RAWINPUT", True, "1", "Habilita la lectura de hardware mediante RawInput de Windows"),
            ("SDL_JOYSTICK_RAWINPUT_CORRELATE_XINPUT", True, "0", "Evita que SDL correlacione y bloquee mandos mediante el límite XInput"),
            ("SDL_XINPUT_ENABLED", True, "0", "Desactiva el límite estricto de 4 mandos impuesto por Microsoft XInput"),
            ("SDL_JOYSTICK_GAMEINPUT", True, "1", "Habilita el backend moderno de GameInput si está soportado"),
            ("SDL_JOYSTICK_THREAD", True, "1", "Ejecuta el escaneo y procesamiento de joysticks en un hilo separado")
        ]

        # Contenedor con scroll para checkboxes si fuese necesario
        chk_container = ttk.Frame(box_env)
        chk_container.pack(fill=tk.BOTH, expand=True)

        for v_name, def_en, def_val, desc in env_specs:
            v_saved = saved_envs.get(v_name, {})
            is_enabled = v_saved.get("enabled", def_en) if isinstance(v_saved, dict) else def_en

            row = ttk.Frame(chk_container)
            row.pack(fill=tk.X, pady=1)

            c_var = tk.BooleanVar(value=is_enabled)
            val_holder = tk.StringVar(value=default_max if v_name == "FNA_GAMEPAD_NUM_GAMEPADS" else def_val)

            chk = ttk.Checkbutton(row, text=v_name, variable=c_var)
            chk.pack(side=tk.LEFT, padx=(0, 6))

            if v_name == "FNA_GAMEPAD_NUM_GAMEPADS":
                lbl_val = ttk.Label(row, text=f'= "{default_max}"', font=("Segoe UI", 8, "bold"), foreground="#0066cc")
                lbl_val.pack(side=tk.LEFT, padx=2)
                lbl_auto = ttk.Label(row, text=f"({default_max} en Ajustes)", font=("Segoe UI", 7, "italic"), foreground="#008800")
                lbl_auto.pack(side=tk.LEFT, padx=2)
            else:
                lbl_val = ttk.Label(row, text=f'= "{def_val}"', font=("Segoe UI", 8, "bold"), foreground="#0066cc")
                lbl_val.pack(side=tk.LEFT, padx=2)

            lbl_desc = ttk.Label(row, text=f"({desc})", font=("Segoe UI", 7), foreground="#777777")
            lbl_desc.pack(side=tk.LEFT, padx=6)

            env_checkboxes[v_name] = (c_var, val_holder)

        # 5. Botonera inferior
        btn_bar = ttk.Frame(frame)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM)

        def save_and_close():
            t_str = title_var.get().strip() or "Juego Sin Título"
            p_str = path_var.get().strip()
            if not p_str:
                messagebox.showwarning(self.t("tab_games"), "Por favor indica la ruta del ejecutable.")
                return

            built_env = {}
            for v_name, (c_var, val_var) in env_checkboxes.items():
                val_to_save = str(self.config.get("max_controllers", 8)) if v_name == "FNA_GAMEPAD_NUM_GAMEPADS" else str(val_var.get())
                built_env[v_name] = {
                    "enabled": bool(c_var.get()),
                    "value": val_to_save
                }

            entry_dict = {
                "title": t_str,
                "path": p_str,
                "args": args_var.get().strip(),
                "working_dir": os.path.dirname(p_str) if p_str else "",
                "env_vars": built_env
            }

            if is_edit:
                games_list[game_index] = entry_dict
            else:
                games_list.append(entry_dict)

            self.config["games"] = games_list
            self.save_config(silent=True)
            self._populate_games_tree()
            dlg.destroy()

        def create_bat_shortcut():
            p_str = path_var.get().strip()
            if not p_str:
                messagebox.showwarning(self.t("tab_games"), "Indica primero la ruta del ejecutable.")
                return

            default_bat_name = f"Launch_{os.path.splitext(os.path.basename(p_str))[0]}_MultiPad.bat"
            desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            chosen_bat = filedialog.asksaveasfilename(
                title=self.t("btn_create_bat"),
                initialdir=desktop_dir if os.path.exists(desktop_dir) else os.path.dirname(p_str),
                initialfile=default_bat_name,
                defaultextension=".bat",
                filetypes=[("Archivo por lotes (*.bat)", "*.bat"), ("Todos los archivos", "*.*")]
            )
            if not chosen_bat:
                return

            bat_lines = [
                "@echo off",
                f"rem Lanzador generado por j360More con soporte +4 mandos",
                f"cd /d \"{os.path.dirname(p_str)}\""
            ]
            for v_name, (c_var, val_var) in env_checkboxes.items():
                if c_var.get():
                    val_to_write = str(self.config.get("max_controllers", 8)) if v_name == "FNA_GAMEPAD_NUM_GAMEPADS" else str(val_var.get())
                    bat_lines.append(f"set {v_name}={val_to_write}")

            args_str = f" {args_var.get().strip()}" if args_var.get().strip() else ""
            bat_lines.append(f"start \"\" \"{p_str}\"{args_str}")

            try:
                with open(chosen_bat, "w", encoding="utf-8") as f:
                    f.write("\r\n".join(bat_lines) + "\r\n")
                messagebox.showinfo(self.t("tab_games"), self.t("bat_created_success", path=chosen_bat))
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar el archivo .bat: {e}")

        btn_save = ttk.Button(btn_bar, text="💾 Guardar", command=save_and_close)
        btn_save.pack(side=tk.LEFT, padx=(0, 6))

        btn_bat = ttk.Button(btn_bar, text=self.t("btn_create_bat"), command=create_bat_shortcut)
        btn_bat.pack(side=tk.LEFT, padx=6)

        btn_cancel = ttk.Button(btn_bar, text="Cancelar", command=dlg.destroy)
        btn_cancel.pack(side=tk.RIGHT)

    def _launch_selected_game(self):
        """Inicia el juego seleccionado inyectando las variables de entorno configuradas."""
        sel = self.games_tree.selection()
        if not sel:
            messagebox.showinfo(self.t("tab_games"), self.t("select_game_first"))
            return
        idx = int(sel[0])
        games_list = self.config.get("games", [])
        if not (0 <= idx < len(games_list)):
            return

        game = games_list[idx]
        exe_path = game.get("path", "").strip()

        if not os.path.exists(exe_path):
            messagebox.showerror("Error", self.t("game_not_found", path=exe_path))
            return

        # Construir entorno enriquecido
        env = os.environ.copy()
        for v_name, v_cfg in game.get("env_vars", {}).items():
            if isinstance(v_cfg, dict) and v_cfg.get("enabled", False):
                if v_name == "FNA_GAMEPAD_NUM_GAMEPADS":
                    env[v_name] = str(self.config.get("max_controllers", 8))
                else:
                    env[v_name] = str(v_cfg.get("value", "1"))

        working_dir = game.get("working_dir") or os.path.dirname(exe_path)
        if not os.path.exists(working_dir):
            working_dir = os.path.dirname(exe_path)

        cmd = [exe_path]
        if game.get("args"):
            import shlex
            try:
                cmd.extend(shlex.split(game["args"]))
            except Exception:
                cmd.extend(game["args"].split())

        try:
            subprocess.Popen(cmd, env=env, cwd=working_dir)
            # Iniciar emulación automáticamente si estaba detenida
            if not self.engine.is_running():
                self._toggle_emulation()
        except Exception as e:
            messagebox.showerror("Error", self.t("game_launch_error", e=e))

    def _on_close(self):
        if self.engine.is_running():
            self.engine.stop()
            self._unhide_emulation_devices()
        if hasattr(self.device_manager, "stop"):
            self.device_manager.stop()
        self.root.destroy()

def run_gui():
    root = tk.Tk()
    app = J360MoreApp(root)
    root.mainloop()

if __name__ == "__main__":
    run_gui()
