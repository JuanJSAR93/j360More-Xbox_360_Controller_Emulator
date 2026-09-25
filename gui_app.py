from __future__ import annotations
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
from typing import Optional, List, Dict, Any, Tuple, Union
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

try:
    import resvg_py
except ImportError:
    resvg_py = None

try:
    import qrcode
except ImportError:
    qrcode = None

import web_gamepad_server

from driver_manager import DriverManager
from input_devices import DeviceManager
from emulator_engine import EmulatorEngine, apply_axis_calibration, apply_trigger_calibration, get_pad_emulated_type
from i18n import (
    get_text, get_target_name, SUPPORTED_LANGUAGES,
    ALL_NONE_LABELS, get_none_label, get_input_options, is_none_mapping,
    canonicalize_mapping, localize_mapping
)

APP_VERSION = "1.5.0"

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

CONTROLLER_360_SVG_PATH = os.path.join(ASSETS_DIR, "controller_360.svg") if os.path.exists(os.path.join(ASSETS_DIR, "controller_360.svg")) else os.path.join(ASSETS_DIR, "controller.svg")
CONTROLLER_ONE_SVG_PATH = os.path.join(ASSETS_DIR, "controller_one.svg")
CONTROLLER_DS4_SVG_PATH = os.path.join(ASSETS_DIR, "controller_DS4.svg")
CONTROLLER_DS5_SVG_PATH = os.path.join(ASSETS_DIR, "controller_DS5.svg")
CONTROLLER_NS2P_SVG_PATH = os.path.join(ASSETS_DIR, "controller_ns2p.svg")
CONTROLLER_SVG_PATH = CONTROLLER_360_SVG_PATH

CONTROLLER_360_CACHE_PNG = os.path.join(ASSETS_DIR, "controller_360_render.png")
CONTROLLER_360_HIRES_PNG = os.path.join(ASSETS_DIR, "controller_360_hires.png")
CONTROLLER_ONE_CACHE_PNG = os.path.join(ASSETS_DIR, "controller_one_render.png")
CONTROLLER_ONE_HIRES_PNG = os.path.join(ASSETS_DIR, "controller_one_hires.png")
CONTROLLER_DS4_CACHE_PNG = os.path.join(ASSETS_DIR, "controller_ds4_render.png")
CONTROLLER_DS4_HIRES_PNG = os.path.join(ASSETS_DIR, "controller_ds4_hires.png")
CONTROLLER_DS5_CACHE_PNG = os.path.join(ASSETS_DIR, "controller_ds5_render.png")
CONTROLLER_DS5_HIRES_PNG = os.path.join(ASSETS_DIR, "controller_ds5_hires.png")
CONTROLLER_NS2P_CACHE_PNG = os.path.join(ASSETS_DIR, "controller_ns2p_render.png")
CONTROLLER_NS2P_HIRES_PNG = os.path.join(ASSETS_DIR, "controller_ns2p_hires.png")

CONTROLLER_PNG_FALLBACK = os.path.join(ASSETS_DIR, "controller_360_render.png")
ICON_SVG_PATH = os.path.join(ASSETS_DIR, "icon.svg")
ICON_PNG_PATH = os.path.join(ASSETS_DIR, "icon.png")
ICON_ICO_PATH = os.path.join(ASSETS_DIR, "icon.ico")

# Coordenadas relativas en el canvas para Xbox 360 (350x275)
XBOX_HITBOXES = {
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

XBOX_CANVAS_POINTS = {
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

# Coordenadas relativas en el canvas para Xbox One (350x275)
XBOXONE_HITBOXES = {
    "A": (269.4, 145.2, 14.0),
    "B": (291.4, 123.6, 14.0),
    "X": (245.4, 123.7, 14.0),
    "Y": (269.6, 102.5, 14.0),
    "GUIDE": (175.0, 93.8, 16.0),
    "BACK": (149.4, 119.7, 13.0),
    "START": (200.9, 120.1, 13.0),
    "LEFT_SHOULDER": (75.3, 72.7, 15.0),
    "RIGHT_SHOULDER": (275.8, 74.5, 15.0),
    "LEFT_TRIGGER": (74.8, 50.5, 15.0),
    "RIGHT_TRIGGER": (276.1, 50.3, 15.0),
}

XBOXONE_CANVAS_POINTS = {
    "LEFT_TRIGGER": (74.8, 50.5, 13),
    "LEFT_SHOULDER": (75.3, 72.7, 13),
    "RIGHT_TRIGGER": (276.1, 50.3, 13),
    "RIGHT_SHOULDER": (275.8, 74.5, 13),
    "LEFT_STICK_UP": (81.5, 107.4, 7),
    "LEFT_STICK_DOWN": (81.5, 141.4, 7),
    "LEFT_STICK_LEFT": (64.5, 124.4, 7),
    "LEFT_STICK_RIGHT": (98.5, 124.4, 7),
    "LEFT_THUMB": (81.5, 124.4, 8),
    "RIGHT_STICK_UP": (218.0, 151.0, 7),
    "RIGHT_STICK_DOWN": (218.0, 184.9, 7),
    "RIGHT_STICK_LEFT": (201.1, 167.9, 7),
    "RIGHT_STICK_RIGHT": (235.0, 167.9, 7),
    "RIGHT_THUMB": (218.0, 167.9, 8),
    "DPAD_UP": (129.8, 150.1, 9),
    "DPAD_DOWN": (129.8, 180.9, 9),
    "DPAD_LEFT": (114.4, 165.5, 9),
    "DPAD_RIGHT": (145.2, 165.5, 9),
    "BACK": (149.4, 119.7, 9),
    "GUIDE": (175.0, 93.8, 14),
    "START": (200.9, 120.1, 9),
    "A": (269.4, 145.2, 11),
    "B": (291.4, 123.6, 11),
    "X": (245.4, 123.7, 11),
    "Y": (269.6, 102.5, 11),
}

# Coordenadas relativas en el canvas para DualShock 4 (350x275)
DS4_HITBOXES = {
    "A": (280.5, 147.0, 14.0),
    "B": (301.5, 126.5, 14.0),
    "X": (259.0, 126.5, 14.0),
    "Y": (280.5, 106.0, 14.0),
    "GUIDE": (174.5, 167.5, 14.0),
    "BACK": (107.0, 95.0, 12.0),
    "START": (243.0, 95.0, 12.0),
    "LEFT_SHOULDER": (70.0, 72.0, 12.0),
    "RIGHT_SHOULDER": (280.0, 72.0, 12.0),
    "LEFT_TRIGGER": (71.5, 52.0, 12.0),
    "RIGHT_TRIGGER": (279.0, 52.0, 12.0),
}

DS4_CANVAS_POINTS = {
    "LEFT_TRIGGER": (71.5, 52.0, 11),
    "LEFT_SHOULDER": (70.0, 72.0, 11),
    "RIGHT_TRIGGER": (279.0, 52.0, 11),
    "RIGHT_SHOULDER": (280.0, 72.0, 11),
    "LEFT_STICK_UP": (123.5, 151.5, 7),
    "LEFT_STICK_DOWN": (123.5, 183.5, 7),
    "LEFT_STICK_LEFT": (107.5, 167.5, 7),
    "LEFT_STICK_RIGHT": (139.5, 167.5, 7),
    "LEFT_THUMB": (123.5, 167.5, 8),
    "RIGHT_STICK_UP": (225.5, 151.5, 7),
    "RIGHT_STICK_DOWN": (225.5, 183.5, 7),
    "RIGHT_STICK_LEFT": (209.5, 167.5, 7),
    "RIGHT_STICK_RIGHT": (241.5, 167.5, 7),
    "RIGHT_THUMB": (225.5, 167.5, 8),
    "DPAD_UP": (70.0, 111.0, 9),
    "DPAD_DOWN": (70.0, 141.5, 9),
    "DPAD_LEFT": (54.5, 126.5, 9),
    "DPAD_RIGHT": (85.5, 126.5, 9),
    "BACK": (107.0, 95.0, 9),
    "GUIDE": (174.5, 167.5, 12),
    "START": (243.0, 95.0, 9),
    "A": (280.5, 147.0, 11),
    "B": (301.5, 126.5, 11),
    "X": (259.0, 126.5, 11),
    "Y": (280.5, 106.0, 11),
}

# Coordenadas relativas en el canvas para PlayStation 5 DualSense (350x275)
DS5_HITBOXES = {
    "A": (278.6, 139.9, 14.0),
    "B": (298.7, 121.2, 14.0),
    "X": (257.5, 121.2, 14.0),
    "Y": (278.6, 100.7, 14.0),
    "GUIDE": (173.9, 151.7, 14.0),
    "BACK": (101.1, 93.1, 12.0),
    "START": (246.7, 93.1, 12.0),
    "LEFT_SHOULDER": (70.0, 67.1, 12.0),
    "RIGHT_SHOULDER": (279.7, 68.0, 12.0),
    "LEFT_TRIGGER": (71.5, 43.7, 12.0),
    "RIGHT_TRIGGER": (278.7, 43.7, 12.0),
}

DS5_CANVAS_POINTS = {
    "LEFT_TRIGGER": (71.5, 43.7, 11),
    "LEFT_SHOULDER": (70.0, 67.1, 11),
    "RIGHT_TRIGGER": (278.7, 43.7, 11),
    "RIGHT_SHOULDER": (279.7, 68.0, 11),
    "LEFT_STICK_UP": (122.0, 138.2, 7),
    "LEFT_STICK_DOWN": (122.0, 170.2, 7),
    "LEFT_STICK_LEFT": (106.0, 154.2, 7),
    "LEFT_STICK_RIGHT": (138.0, 154.2, 7),
    "LEFT_THUMB": (122.0, 154.2, 8),
    "RIGHT_STICK_UP": (225.5, 138.2, 7),
    "RIGHT_STICK_DOWN": (225.5, 170.2, 7),
    "RIGHT_STICK_LEFT": (208.0, 154.2, 7),
    "RIGHT_STICK_RIGHT": (241.5, 154.2, 7),
    "RIGHT_THUMB": (225.5, 154.2, 8),
    "DPAD_UP": (68.5, 105.7, 9),
    "DPAD_DOWN": (68.5, 136.2, 9),
    "DPAD_LEFT": (53.0, 121.2, 9),
    "DPAD_RIGHT": (84.0, 121.2, 9),
    "BACK": (101.1, 93.1, 9),
    "GUIDE": (173.9, 151.7, 12),
    "START": (246.7, 93.1, 9),
    "A": (278.6, 139.9, 11),
    "B": (298.7, 121.2, 11),
    "X": (257.5, 121.2, 11),
    "Y": (278.6, 100.7, 11),
}

# Coordenadas relativas en el canvas para Nintendo Switch 2 Pro (350x275)
NS2PRO_HITBOXES = {
    "A": (288.6, 131.9, 14.0),
    "B": (268.2, 151.4, 14.0),
    "X": (268.1, 112.5, 14.0),
    "Y": (247.6, 132.0, 14.0),
    "GUIDE": (208.0, 131.5, 12.0),
    "BACK": (132.1, 108.5, 12.0),   # Botón Menos (-)
    "START": (219.3, 108.5, 12.0),  # Botón Más (+)
    "LEFT_SHOULDER": (74.0, 78.0, 13.0),
    "RIGHT_SHOULDER": (276.0, 78.0, 13.0),
    "LEFT_TRIGGER": (74.0, 52.0, 13.0),
    "RIGHT_TRIGGER": (276.0, 52.0, 13.0),
}

NS2PRO_CANVAS_POINTS = {
    "LEFT_TRIGGER": (74.0, 52.0, 12),
    "LEFT_SHOULDER": (74.0, 78.0, 12),
    "RIGHT_TRIGGER": (276.0, 52.0, 12),
    "RIGHT_SHOULDER": (276.0, 78.0, 12),
    "LEFT_STICK_UP": (79.4, 114.8, 7),
    "LEFT_STICK_DOWN": (79.4, 148.8, 7),
    "LEFT_STICK_LEFT": (62.4, 131.8, 7),
    "LEFT_STICK_RIGHT": (96.4, 131.8, 7),
    "LEFT_THUMB": (79.4, 131.8, 8),
    "RIGHT_STICK_UP": (224.4, 155.0, 7),
    "RIGHT_STICK_DOWN": (224.4, 189.0, 7),
    "RIGHT_STICK_LEFT": (207.4, 172.0, 7),
    "RIGHT_STICK_RIGHT": (241.4, 172.0, 7),
    "RIGHT_THUMB": (224.4, 172.0, 8),
    "DPAD_UP": (126.3, 156.1, 9),
    "DPAD_DOWN": (126.3, 185.9, 9),
    "DPAD_LEFT": (111.8, 171.0, 9),
    "DPAD_RIGHT": (140.8, 171.0, 9),
    "BACK": (132.1, 108.5, 9),
    "GUIDE": (208.0, 131.5, 10),
    "START": (219.3, 108.5, 9),
    "A": (288.6, 131.9, 11),
    "B": (268.2, 151.4, 11),
    "X": (268.1, 112.5, 11),
    "Y": (247.6, 132.0, 11),
}

HITBOXES = XBOX_HITBOXES
CANVAS_POINTS = XBOX_CANVAS_POINTS

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

DEFAULT_PHONE_MAPPINGS = {
    "LEFT_TRIGGER": "Axis 3",
    "LEFT_SHOULDER": "Button 5",
    "BACK": "Button 7",
    "START": "Button 8",
    "GUIDE": "Button 11",
    "LEFT_STICK_X": "Axis 1",
    "LEFT_STICK_Y": "Axis 2",
    "LEFT_STICK_UP": "-- Ninguno --",
    "LEFT_STICK_DOWN": "-- Ninguno --",
    "LEFT_STICK_LEFT": "-- Ninguno --",
    "LEFT_STICK_RIGHT": "-- Ninguno --",
    "LEFT_THUMB": "Button 9",
    "RIGHT_TRIGGER": "Axis 6",
    "RIGHT_SHOULDER": "Button 6",
    "Y": "Button 4",
    "X": "Button 3",
    "B": "Button 2",
    "A": "Button 1",
    "RIGHT_STICK_X": "Axis 4",
    "RIGHT_STICK_Y": "Axis 5",
    "RIGHT_STICK_UP": "-- Ninguno --",
    "RIGHT_STICK_DOWN": "-- Ninguno --",
    "RIGHT_STICK_LEFT": "-- Ninguno --",
    "RIGHT_STICK_RIGHT": "-- Ninguno --",
    "RIGHT_THUMB": "Button 10",
    "DPAD_UP": "POV 1 Up",
    "DPAD_DOWN": "POV 1 Down",
    "DPAD_LEFT": "POV 1 Left",
    "DPAD_RIGHT": "POV 1 Right"
}

class ArrowButton(tk.Canvas):
    """Botón estilizado para deslizamiento horizontal de pestañas con flechas proporcionadas y vectoriales."""
    def __init__(self, parent, direction="left", command_start=None, command_stop=None, **kwargs):
        super().__init__(
            parent,
            width=20,
            height=22,
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            bg="#f1f5f9",
            cursor="hand2",
            **kwargs
        )
        self.direction = direction
        self.command_start = command_start
        self.command_stop = command_stop

        if direction == "left":
            self.poly = self.create_polygon(13, 5, 6, 11, 13, 17, fill="#334155")
        else:
            self.poly = self.create_polygon(7, 5, 14, 11, 7, 17, fill="#334155")

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, e):
        self.configure(bg="#e0f2fe", highlightbackground="#38bdf8")
        self.itemconfig(self.poly, fill="#0284c7")

    def _on_leave(self, e):
        self.configure(bg="#f1f5f9", highlightbackground="#cbd5e1")
        self.itemconfig(self.poly, fill="#334155")

    def _on_press(self, e):
        self.configure(bg="#bae6fd", highlightbackground="#0284c7")
        if self.command_start:
            self.command_start(e)

    def _on_release(self, e):
        self.configure(bg="#e0f2fe", highlightbackground="#38bdf8")
        if self.command_stop:
            self.command_stop(e)


class ScrollableNotebook(ttk.Frame):
    """Contenedor de pestañas horizontales deslizables con soporte para rueda del ratón y flechas ◀ ▶.
    Basado en la arquitectura de muhammeteminturgut/ttkScrollableNotebook con soporte nativo de Windows.
    """
    def __init__(self, parent, wheelscroll: bool = True, **kwargs):
        super().__init__(parent)
        self.xLocation = 0
        self.timer = None
        self.menuSpace = 48
        self.contentsManaged = []
        self._external_tab_changed_cbs = []

        # Estilo para asegurar que el notebook de contenido no dibuje encabezados de pestaña duplicados
        s = ttk.Style()
        try:
            s.layout("NoTabs.TNotebook.Tab", [])
        except Exception:
            pass

        # 1. Marco visor superior que aloja únicamente la tira de pestañas y las flechas
        self.tab_viewport = ttk.Frame(self, height=28)
        self.tab_viewport.pack(fill="x", side="top")
        self.tab_viewport.pack_propagate(False)

        self.notebookTab = ttk.Notebook(self.tab_viewport, **kwargs)
        self.notebookTab.place(x=0, y=0)
        self.notebookTab.bind("<<NotebookTabChanged>>", self._tabChanger)

        self.slideFrame = ttk.Frame(self.tab_viewport)

        self.leftArrow = ArrowButton(self.slideFrame, direction="left", command_start=self._leftSlideStart, command_stop=self._slideStop)
        self.leftArrow.pack(side="left", padx=(0, 2))

        self.rightArrow = ArrowButton(self.slideFrame, direction="right", command_start=self._rightSlideStart, command_stop=self._slideStop)
        self.rightArrow.pack(side="left")

        if wheelscroll:
            for w in (self.notebookTab, self.tab_viewport, self.slideFrame, self.leftArrow, self.rightArrow):
                w.bind("<MouseWheel>", self._wheelscroll)

        # 2. Notebook de contenido que ocupa el resto del espacio
        self.notebookContent = ttk.Notebook(self, style="NoTabs.TNotebook", **kwargs)
        self.notebookContent.pack(fill="both", expand=True, side="top")

        self.bind("<Configure>", self._on_configure)

    def _update_arrows_visibility(self):
        cont_w = self.tab_viewport.winfo_width()
        tab_w = self.notebookTab.winfo_reqwidth()
        if cont_w <= 1:
            return
        tab_h = self.notebookTab.winfo_reqheight()
        if tab_h > 1 and tab_h != self.tab_viewport.winfo_height():
            self.tab_viewport.configure(height=max(28, tab_h))

        if tab_w <= cont_w:
            self.xLocation = 0
            self.notebookTab.place(x=0, y=0)
            self.slideFrame.place_forget()
        else:
            self.slideFrame.place(relx=1.0, x=-2, y=2, anchor="ne")
            self.slideFrame.lift()
            max_scroll = tab_w - (cont_w - self.menuSpace)
            if -self.xLocation > max_scroll:
                self.xLocation = -max_scroll
                self.notebookTab.place(x=self.xLocation, y=0)

    def _on_configure(self, event=None):
        self._update_arrows_visibility()

    def _wheelscroll(self, event):
        if hasattr(event, "delta") and event.delta:
            if event.delta > 0:
                self._leftSlide(event)
            else:
                self._rightSlide(event)

    def _tabChanger(self, event=None):
        if getattr(self, "_in_tab_change", False):
            return
        self._in_tab_change = True
        try:
            cur = self.notebookTab.select()
            if cur:
                idx = self.notebookTab.index(cur)
                if idx < len(self.notebookContent.tabs()):
                    cur_cont = self.notebookContent.select()
                    if not cur_cont or self.notebookContent.index(cur_cont) != idx:
                        self.notebookContent.select(idx)
                self._ensure_visible(idx)
            for cb in self._external_tab_changed_cbs:
                try:
                    cb(event)
                except Exception:
                    pass
        finally:
            self._in_tab_change = False

    def _ensure_visible(self, idx: int):
        total_tabs = len(self.notebookTab.tabs())
        if total_tabs == 0:
            return
        total_w = self.notebookTab.winfo_reqwidth()
        cont_w = self.tab_viewport.winfo_width()
        if total_w <= cont_w - self.menuSpace or cont_w <= 0:
            self.xLocation = 0
            self.notebookTab.place(x=0, y=0)
            return

        max_scroll = total_w - (cont_w - self.menuSpace)
        if idx == 0:
            self.xLocation = 0
        elif idx >= total_tabs - 1:
            self.xLocation = -max_scroll
        else:
            avg_w = total_w / total_tabs
            est_left = idx * avg_w
            est_right = (idx + 1) * avg_w
            if est_left + self.xLocation < 0:
                self.xLocation = -est_left
            elif est_right + self.xLocation > (cont_w - self.menuSpace):
                self.xLocation = (cont_w - self.menuSpace) - est_right
            self.xLocation = max(-max_scroll, min(0, int(self.xLocation)))

        self.notebookTab.place(x=self.xLocation, y=0)

    def _rightSlideStart(self, event=None):
        if self._rightSlide(event):
            self.timer = self.after(50, self._rightSlideStart)

    def _rightSlide(self, event=None):
        tab_w = self.notebookTab.winfo_reqwidth()
        cont_w = self.tab_viewport.winfo_width()
        if tab_w > cont_w - self.menuSpace:
            max_scroll = tab_w - (cont_w - self.menuSpace)
            if -self.xLocation < max_scroll:
                self.xLocation -= 40
                if -self.xLocation > max_scroll:
                    self.xLocation = -max_scroll
                self.notebookTab.place(x=self.xLocation, y=0)
                return True
        return False

    def _leftSlideStart(self, event=None):
        if self._leftSlide(event):
            self.timer = self.after(50, self._leftSlideStart)

    def _leftSlide(self, event=None):
        if self.xLocation < 0:
            self.xLocation += 40
            if self.xLocation > 0:
                self.xLocation = 0
            self.notebookTab.place(x=self.xLocation, y=0)
            return True
        return False

    def _slideStop(self, event=None):
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None

    def add(self, frame, **kwargs):
        self.notebookContent.add(frame, text="")
        dummy = ttk.Frame(self.notebookTab)
        self.notebookTab.add(dummy, **kwargs)
        self.contentsManaged.append(frame)
        self._update_arrows_visibility()

    def select(self, tab_id=None):
        if tab_id is None:
            return self.notebookTab.select()
        if getattr(self, "_in_tab_change", False):
            return
        self._in_tab_change = True
        try:
            target_idx = None
            if tab_id in self.contentsManaged:
                target_idx = self.contentsManaged.index(tab_id)
            else:
                try:
                    target_idx = self.notebookTab.index(tab_id)
                except Exception:
                    pass

            if target_idx is not None:
                cur_tab = self.notebookTab.select()
                cur_tab_idx = self.notebookTab.index(cur_tab) if cur_tab else None
                if cur_tab_idx != target_idx:
                    self.notebookTab.select(target_idx)

                cur_content = self.notebookContent.select()
                cur_cont_idx = self.notebookContent.index(cur_content) if cur_content else None
                if target_idx < len(self.notebookContent.tabs()) and cur_cont_idx != target_idx:
                    self.notebookContent.select(target_idx)

                self._ensure_visible(target_idx)

                for cb in self._external_tab_changed_cbs:
                    try:
                        cb(None)
                    except Exception:
                        pass
        finally:
            self._in_tab_change = False

    def index(self, tab_id):
        if tab_id in self.contentsManaged:
            return self.contentsManaged.index(tab_id)
        return self.notebookTab.index(tab_id)

    def tabs(self):
        return self.notebookTab.tabs()

    def forget(self, tab_id, destroy: bool = False):
        try:
            idx = self.index(tab_id)
            content_frame = None
            if idx < len(self.contentsManaged):
                content_frame = self.contentsManaged.pop(idx)
            if idx < len(self.notebookContent.tabs()):
                self.notebookContent.forget(idx)
            self.notebookTab.forget(tab_id)
            if destroy and content_frame is not None:
                try:
                    content_frame.destroy()
                except Exception:
                    pass
        except Exception:
            pass
        self._update_arrows_visibility()

    def clear(self):
        """Limpia y destruye todos los widgets contenidos liberando recursos GDI de Windows."""
        for f in list(self.contentsManaged):
            try:
                f.destroy()
            except Exception:
                pass
        self.contentsManaged.clear()
        for t in list(self.notebookTab.tabs()):
            try:
                self.notebookTab.forget(t)
            except Exception:
                pass
        for t in list(self.notebookContent.tabs()):
            try:
                self.notebookContent.forget(t)
            except Exception:
                pass
        self.xLocation = 0
        self.notebookTab.place(x=0, y=0)
        self._update_arrows_visibility()

    def tab(self, tab_id, option=None, **kwargs):
        idx = self.index(tab_id)
        if kwargs:
            return self.notebookTab.tab(idx, option=option, **kwargs)
        return self.notebookTab.tab(idx, option=option)

    def bind(self, sequence, func=None, add=None):
        if sequence == "<<NotebookTabChanged>>":
            if func is not None:
                if add:
                    self._external_tab_changed_cbs.append(func)
                else:
                    self._external_tab_changed_cbs = [func]
            return
        return self.notebookTab.bind(sequence, func, add=add)

    def unbind(self, sequence, funcid=None):
        if sequence == "<<NotebookTabChanged>>":
            self._external_tab_changed_cbs.clear()
            return
        return self.notebookTab.unbind(sequence, funcid=funcid)


class SplashScreen:
    """Ventana de carga inicial (Splash Screen) con icono SVG y en primer plano (topmost)."""
    def __init__(self, root: tk.Tk, title: str = "j360More", desc: str = "Cargando controladores y periféricos..."):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.title(title)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg="#2d2d30")

        # Dimensiones y centrado en el monitor principal
        w, h = 420, 240
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.window.geometry(f"{w}x{h}+{x}+{y}")

        # Contenedor con borde fino oscuro
        outer = tk.Frame(self.window, bg="#3e3e42", padx=1, pady=1)
        outer.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(outer, bg="#1e1e1e", padx=20, pady=16)
        inner.pack(fill=tk.BOTH, expand=True)

        # 1. Icono oficial de la app desde icon.svg o icon.png
        self.icon_photo = None
        if os.path.exists(ICON_SVG_PATH) and resvg_py is not None:
            try:
                png_bytes = resvg_py.svg_to_bytes(svg_path=ICON_SVG_PATH, width=64, height=64)
                pil_img = Image.open(io.BytesIO(png_bytes))
                self.icon_photo = ImageTk.PhotoImage(pil_img)
            except Exception:
                pass
        if not self.icon_photo and os.path.exists(ICON_PNG_PATH):
            try:
                pil_img = Image.open(ICON_PNG_PATH).resize((64, 64), Image.Resampling.LANCZOS)
                self.icon_photo = ImageTk.PhotoImage(pil_img)
            except Exception:
                pass

        if self.icon_photo:
            lbl_icon = tk.Label(inner, image=self.icon_photo, bg="#1e1e1e")
            lbl_icon.pack(pady=(0, 4))
        else:
            lbl_icon = tk.Label(inner, text="🎮", font=("Segoe UI Emoji", 28), fg="#39ff14", bg="#1e1e1e")
            lbl_icon.pack(pady=(0, 4))

        # 2. Título de la app
        lbl_title = tk.Label(inner, text="j360More", font=("Segoe UI", 16, "bold"), fg="#ffffff", bg="#1e1e1e")
        lbl_title.pack(pady=(0, 2))

        # 3. Estado dinámico de carga
        self.lbl_status = tk.Label(inner, text=desc, font=("Segoe UI", 9), fg="#b0b0b0", bg="#1e1e1e")
        self.lbl_status.pack(pady=(0, 10))

        # 4. Barra de progreso animada indeterminada
        self.progress = ttk.Progressbar(inner, mode="indeterminate", length=340)
        self.progress.pack(pady=(0, 8))
        self.progress.start(10)

        # 5. Versión en la parte inferior
        lbl_ver = tk.Label(inner, text=f"v{APP_VERSION}", font=("Segoe UI", 8), fg="#666666", bg="#1e1e1e")
        lbl_ver.pack()

        self.window.update()

    def set_status(self, text: str):
        try:
            self.lbl_status.config(text=text)
            self.window.update_idletasks()
        except Exception:
            pass

    def finish(self):
        if "_PYI_SPLASH_IPC" in os.environ:
            try:
                import pyi_splash
                if pyi_splash.is_alive():
                    pyi_splash.close()
            except Exception:
                pass

        try:
            self.progress.stop()
            self.window.destroy()
        except Exception:
            pass


class J360MoreApp:
    def __init__(self, root: tk.Tk, splash: Optional[Any] = None):
        self.root = root
        self.splash = splash
        self.config = self.load_config()
        self.root.title(self.t("app_title"))
        self._setup_app_icon()

        # Tamaño balanceado donde todo es visible cómodamente sin cortes
        self.root.geometry("950x600")
        self.root.resizable(False, False)

        self.driver_manager = DriverManager(self.config)
        self.device_manager = DeviceManager(self.driver_manager)
        self.device_manager.set_driver_backend(self.config.get("driver_backend", "vigem" if sys.platform == "win32" else "viiper"))
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
        self.device_manager.add_on_devices_changed_callback(lambda devs: self.root.after(0, self._on_devices_hotplugged, devs))

        # Servidor AirPad para smartphones
        self.airpad_server = web_gamepad_server.get_server_instance()
        self.airpad_server.preferred_ip = self.config.get("airpad_bind_ip", None)
        self.airpad_server.port = self.config.get("airpad_server_port", 8080)
        self.airpad_server.haptics_enabled = self.config.get("airpad_haptics_enabled", True)
        self.airpad_server.max_slots = self.config.get("max_controllers", 8)
        self.airpad_server.on_input_event = self.engine.trigger_input_event
        if self.config.get("airpad_server_enabled", True):
            self.airpad_server.start()

        # Asegurar que el cloaking residual de HidHide esté desactivado al iniciar y que Python/la app estén en la whitelist
        if self.driver_manager.is_hidhide_installed():
            try:
                self.driver_manager.set_cloak_active(False)
                self.driver_manager.ensure_process_whitelisted()
            except Exception:
                pass

        # Comprobar estado de drivers (ViGEmBus y aviso leve de HidHide)
        self.root.after(200, self._check_system_drivers)

        # Verificacion asincrona de nueva version (una unica vez al iniciar)
        self._update_checked = False
        self._available_update_version = None
        self.root.after(1500, self._check_update_once)

        self.root.bind("<KeyPress>", self._on_key_press)
        self.root.bind("<KeyRelease>", self._on_key_release)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Manejo de modales para evitar bloqueo al minimizar con Win+D
        self._active_dialog = None
        self._modal_needs_regrab = False

        self.root.after(30, self._update_loop)

        # Cerrar el Splash Screen y desplegar la ventana principal lista
        if getattr(self, "splash", None):
            try:
                self.splash.finish()
            except Exception:
                pass
            self.splash = None

        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _setup_modal_dialog(self, dlg: tk.Toplevel):
        """Configura un diálogo modal protegido contra bloqueos de minimizado con Win+D en Windows."""
        dlg.transient(self.root)
        try:
            dlg.grab_set()
        except Exception:
            pass
        self._active_dialog = dlg
        self._modal_needs_regrab = False

        orig_destroy = dlg.destroy
        def on_close():
            if getattr(self, "_active_dialog", None) == dlg:
                self._active_dialog = None
                self._modal_needs_regrab = False
            try:
                dlg.grab_release()
            except Exception:
                pass
            try:
                orig_destroy()
            except Exception:
                pass
            try:
                self.root.focus_force()
            except Exception:
                pass

        dlg.destroy = on_close

    def t(self, key: str, **kwargs) -> str:
        lang = self.config.get("language", "es")
        return get_text(lang, key, **kwargs)

    def _get_current_pad_id(self) -> int:
        try:
            if hasattr(self, "notebook") and self.notebook.tabs():
                cur_tab = self.notebook.select()
                for pid, frame in self.tab_frames.items():
                    if str(frame) == cur_tab:
                        return pid
        except Exception:
            pass
        return 1

    def get_pad_emulated_type(self, pad_id: Optional[int] = None) -> str:
        if pad_id is None:
            pad_id = self._get_current_pad_id()
        return get_pad_emulated_type(self.config, pad_id)

    def target_name(self, target: str, pad_id: Optional[int] = None) -> str:
        lang = self.config.get("language", "es")
        emulated_type = self.get_pad_emulated_type(pad_id)
        return get_target_name(lang, target, emulated_type)

    def _get_hitboxes(self, pad_id: Optional[int] = None) -> dict:
        t = self.get_pad_emulated_type(pad_id)
        if t in ("xboxone", "xbox_one"):
            return XBOXONE_HITBOXES
        elif t == "dualsense":
            return DS5_HITBOXES
        elif t == "ds4":
            return DS4_HITBOXES
        elif t == "ns2pro":
            return NS2PRO_HITBOXES
        return XBOX_HITBOXES

    def _get_canvas_points(self, pad_id: Optional[int] = None) -> dict:
        t = self.get_pad_emulated_type(pad_id)
        if t in ("xboxone", "xbox_one"):
            return XBOXONE_CANVAS_POINTS
        elif t == "dualsense":
            return DS5_CANVAS_POINTS
        elif t == "ds4":
            return DS4_CANVAS_POINTS
        elif t == "ns2pro":
            return NS2PRO_CANVAS_POINTS
        return XBOX_CANVAS_POINTS

    def _get_pad_img_tk(self, pad_id: Optional[int] = None):
        t = self.get_pad_emulated_type(pad_id)
        if t in ("xboxone", "xbox_one"):
            if getattr(self, "ctrl_one_tk", None) is None:
                self._load_one_asset()
            return self.ctrl_one_tk
        elif t == "dualsense":
            if getattr(self, "ctrl_ds5_tk", None) is None:
                self._load_ds5_asset()
            return self.ctrl_ds5_tk
        elif t == "ds4":
            if getattr(self, "ctrl_ds4_tk", None) is None:
                self._load_ds4_asset()
            return self.ctrl_ds4_tk
        elif t == "ns2pro":
            if getattr(self, "ctrl_ns2p_tk", None) is None:
                self._load_ns2p_asset()
            return self.ctrl_ns2p_tk
        if getattr(self, "ctrl_360_tk", None) is None:
            self._load_360_asset()
        return self.ctrl_360_tk

    def _get_pad_hires_img(self, pad_id: Optional[int] = None):
        t = self.get_pad_emulated_type(pad_id)
        if t in ("xboxone", "xbox_one"):
            if getattr(self, "ctrl_one_hires", None) is None:
                self._load_one_asset()
            return getattr(self, "ctrl_one_hires", None) or getattr(self, "ctrl_one_base", None) or self.ctrl_360_hires
        elif t == "dualsense":
            if getattr(self, "ctrl_ds5_hires", None) is None:
                self._load_ds5_asset()
            return getattr(self, "ctrl_ds5_hires", None) or getattr(self, "ctrl_ds5_base", None) or self.ctrl_ds4_hires
        elif t == "ds4":
            if getattr(self, "ctrl_ds4_hires", None) is None:
                self._load_ds4_asset()
            return self.ctrl_ds4_hires or self.ctrl_ds4_base
        elif t == "ns2pro":
            if getattr(self, "ctrl_ns2p_hires", None) is None:
                self._load_ns2p_asset()
            return getattr(self, "ctrl_ns2p_hires", None) or getattr(self, "ctrl_ns2p_base", None) or self.ctrl_360_hires
        if getattr(self, "ctrl_360_hires", None) is None:
            self._load_360_asset()
        return self.ctrl_360_hires or self.ctrl_360_base

    @property
    def current_lang(self) -> str:
        return self.config.get("language", "es")

    def get_none_label(self) -> str:
        return get_none_label(self.current_lang)

    def get_input_options(self) -> list:
        return get_input_options(self.current_lang)

    def localize_mapping(self, val: str) -> str:
        return localize_mapping(val, self.current_lang)

    def canonicalize_mapping(self, val: str) -> str:
        return canonicalize_mapping(val)

    def get_device_display_name(self, d: dict, kbd_idx: int = 1) -> str:
        dev_id = d.get("id", "")
        if dev_id == "none":
            return self.t("none_disconnected")
        if dev_id == "keyboard":
            return self.t("keyboard_device_global")
        if dev_id == "mouse":
            return self.t("mouse_device_name")
        if dev_id.startswith("kbd_"):
            c_type = d.get("conn_type", "USB")
            conn_str = self.t("conn_usb") if c_type == "USB" else (self.t("conn_bt") if c_type in ("BT", "BTH") else (self.t("conn_int") if c_type == "INT" else c_type))
            pname = d.get("product_name", self.t("keyboard_device_name"))
            return self.t("kbd_device_item", num=kbd_idx, name=pname, conn=conn_str)
        return d.get("name", self.t("dev_device_fallback"))

    def _toggle_language(self):
        codes = list(SUPPORTED_LANGUAGES.keys())
        cur = self.config.get("language", "es")
        idx = codes.index(cur) if cur in codes else 0
        self.config["language"] = codes[(idx + 1) % len(codes)]
        self.save_config(silent=True)
        self._update_ui_texts()

    def _update_header_title(self, count: int = None):
        if count is None:
            count = self.config.get("max_controllers", 8)
        if hasattr(self, "title_lbl"):
            full_title = self.t("header_title", count=count)
            if "JuanJSAR" in full_title:
                prefix = full_title.split("JuanJSAR")[0]
                self.title_lbl.config(text=prefix)
                if hasattr(self, "lbl_author"):
                    self.lbl_author.config(text="JuanJSAR")
            else:
                self.title_lbl.config(text=full_title)
                if hasattr(self, "lbl_author"):
                    self.lbl_author.config(text="")

    def _update_ui_texts(self):
        max_ctrls = self.config.get("max_controllers", 8)
        self.root.title(self.t("app_title"))
        self._update_header_title(max_ctrls)
        if hasattr(self, "btn_devices"):
            self.btn_devices.config(text=self.t("btn_devices"))
        if hasattr(self, "btn_settings"):
            self.btn_settings.config(text=self.t("btn_settings"))
        if hasattr(self, "btn_airpad"):
            self.btn_airpad.config(text=self.t("btn_airpad_main"))
        if hasattr(self, "btn_joy_cpl"):
            self.btn_joy_cpl.config(text=self.t("btn_joy_cpl"))
        if hasattr(self, "btn_hidhide"):
            self.btn_hidhide.config(text=self.t("btn_hidhide_client"))
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

        self._update_airpad_status_ui(force=True)
        self._rebuild_tabs(max_ctrls)

    def _update_airpad_status_ui(self, force: bool = False):
        """Actualiza el indicador visual de AirPad en la cabecera."""
        if not hasattr(self, "airpad_status_text_lbl") or not hasattr(self, "airpad_status_dot"):
            return
        is_running = bool(hasattr(self, "airpad_server") and getattr(self.airpad_server, "running", False))
        if force or getattr(self, "_last_airpad_running_state", None) != is_running:
            self._last_airpad_running_state = is_running
            color = "#00cc44" if is_running else "#888888"
            text_key = "airpad_status_active" if is_running else "airpad_status_stopped"
            try:
                self.airpad_status_dot.itemconfig(self.airpad_status_circle, fill=color)
                self.airpad_status_text_lbl.config(text=self.t(text_key))
            except Exception:
                pass

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
        icon_set = False
        if os.path.exists(ICON_ICO_PATH) and sys.platform == "win32":
            try:
                self.root.iconbitmap(ICON_ICO_PATH)
                icon_set = True
            except Exception:
                pass

        if not icon_set and os.path.exists(ICON_PNG_PATH):
            try:
                self.app_icon_tk = ImageTk.PhotoImage(file=ICON_PNG_PATH)
                self.root.iconphoto(True, self.app_icon_tk)
            except Exception:
                pass

    def _load_single_controller_asset(self, svg_path: str, hires_png: str, render_png: str):
        pil_hires = None
        pil_base = None

        # 1. Si ya existen los archivos PNG en assets, usarlos directamente SIN regenerar
        if os.path.exists(hires_png):
            try:
                pil_hires = Image.open(hires_png)
            except Exception:
                pass

        if os.path.exists(render_png):
            try:
                pil_base = Image.open(render_png)
            except Exception:
                pass

        # 2. Solo si no existen las imágenes PNG, intentar renderizar desde SVG
        if pil_hires is None and pil_base is None and os.path.exists(svg_path) and resvg_py is not None:
            try:
                png_bytes_hi = resvg_py.svg_to_bytes(svg_path=svg_path, width=1400)
                pil_hires = Image.open(io.BytesIO(png_bytes_hi))
                try:
                    pil_hires.save(hires_png)
                except Exception:
                    pass
            except Exception as e:
                print(f"[!] Error renderizando SVG HD ({svg_path}): {e}")

        # 3. Asegurar que pil_base tenga tamaño (350, 275) si se derivó de hires
        if pil_base is None and pil_hires is not None:
            try:
                pil_base = pil_hires.resize((350, 275), Image.Resampling.LANCZOS)
                try:
                    pil_base.save(render_png)
                except Exception:
                    pass
            except Exception:
                pass
        elif pil_hires is None and pil_base is not None:
            pil_hires = pil_base

        tk_img = ImageTk.PhotoImage(pil_base) if pil_base else None
        return pil_hires, pil_base, tk_img

    def _load_360_asset(self):
        if getattr(self, "ctrl_360_tk", None) is None:
            (self.ctrl_360_hires, self.ctrl_360_base, self.ctrl_360_tk) = self._load_single_controller_asset(
                CONTROLLER_360_SVG_PATH, CONTROLLER_360_HIRES_PNG, CONTROLLER_360_CACHE_PNG
            )
            if self.ctrl_360_base is None and os.path.exists(CONTROLLER_PNG_FALLBACK):
                try:
                    p = Image.open(CONTROLLER_PNG_FALLBACK).resize((350, 275), Image.Resampling.LANCZOS)
                    self.ctrl_360_base = p
                    self.ctrl_360_hires = p
                    self.ctrl_360_tk = ImageTk.PhotoImage(p)
                except Exception:
                    pass

    def _load_one_asset(self):
        if getattr(self, "ctrl_one_tk", None) is None:
            (self.ctrl_one_hires, self.ctrl_one_base, self.ctrl_one_tk) = self._load_single_controller_asset(
                CONTROLLER_ONE_SVG_PATH, CONTROLLER_ONE_HIRES_PNG, CONTROLLER_ONE_CACHE_PNG
            )

    def _load_ds4_asset(self):
        if getattr(self, "ctrl_ds4_tk", None) is None:
            (self.ctrl_ds4_hires, self.ctrl_ds4_base, self.ctrl_ds4_tk) = self._load_single_controller_asset(
                CONTROLLER_DS4_SVG_PATH, CONTROLLER_DS4_HIRES_PNG, CONTROLLER_DS4_CACHE_PNG
            )

    def _load_ds5_asset(self):
        if getattr(self, "ctrl_ds5_tk", None) is None:
            (self.ctrl_ds5_hires, self.ctrl_ds5_base, self.ctrl_ds5_tk) = self._load_single_controller_asset(
                CONTROLLER_DS5_SVG_PATH, CONTROLLER_DS5_HIRES_PNG, CONTROLLER_DS5_CACHE_PNG
            )

    def _load_ns2p_asset(self):
        if getattr(self, "ctrl_ns2p_tk", None) is None:
            (self.ctrl_ns2p_hires, self.ctrl_ns2p_base, self.ctrl_ns2p_tk) = self._load_single_controller_asset(
                CONTROLLER_NS2P_SVG_PATH, CONTROLLER_NS2P_HIRES_PNG, CONTROLLER_NS2P_CACHE_PNG
            )

    def _load_assets(self):
        self.controller_img_tk = None
        self.controller_pil_base = None
        self.controller_pil_hires = None
        self.ctrl_360_hires = self.ctrl_360_base = self.ctrl_360_tk = None
        self.ctrl_one_hires = self.ctrl_one_base = self.ctrl_one_tk = None
        self.ctrl_ds4_hires = self.ctrl_ds4_base = self.ctrl_ds4_tk = None
        self.ctrl_ds5_hires = self.ctrl_ds5_base = self.ctrl_ds5_tk = None
        self.ctrl_ns2p_hires = self.ctrl_ns2p_base = self.ctrl_ns2p_tk = None

        emulated_type = self.config.get("emulated_type", "xbox360").lower()
        if emulated_type in ("xboxone", "xbox_one"):
            self._load_one_asset()
        elif emulated_type == "dualsense":
            self._load_ds5_asset()
        elif emulated_type == "ds4":
            self._load_ds4_asset()
        elif emulated_type == "ns2pro":
            self._load_ns2p_asset()
        else:
            self._load_360_asset()

        self._update_active_assets()

    def _update_active_assets(self):
        emulated_type = self.config.get("emulated_type", "xbox360").lower()
        if emulated_type in ("xboxone", "xbox_one"):
            if getattr(self, "ctrl_one_tk", None) is None:
                self._load_one_asset()
            if getattr(self, "ctrl_one_base", None) is not None:
                self.controller_pil_hires = self.ctrl_one_hires
                self.controller_pil_base = self.ctrl_one_base
                self.controller_img_tk = self.ctrl_one_tk
            else:
                self.controller_pil_hires = self.ctrl_360_hires
                self.controller_pil_base = self.ctrl_360_base
                self.controller_img_tk = self.ctrl_360_tk
        elif emulated_type == "dualsense" and getattr(self, "ctrl_ds5_base", None) is not None:
            self.controller_pil_hires = self.ctrl_ds5_hires
            self.controller_pil_base = self.ctrl_ds5_base
            self.controller_img_tk = self.ctrl_ds5_tk
        elif emulated_type == "ds4" and getattr(self, "ctrl_ds4_base", None) is not None:
            self.controller_pil_hires = self.ctrl_ds4_hires
            self.controller_pil_base = self.ctrl_ds4_base
            self.controller_img_tk = self.ctrl_ds4_tk
        elif emulated_type == "ns2pro" and getattr(self, "ctrl_ns2p_base", None) is not None:
            self.controller_pil_hires = self.ctrl_ns2p_hires
            self.controller_pil_base = self.ctrl_ns2p_base
            self.controller_img_tk = self.ctrl_ns2p_tk
        else:
            self.controller_pil_hires = self.ctrl_360_hires
            self.controller_pil_base = self.ctrl_360_base
            self.controller_img_tk = self.ctrl_360_tk

    def load_config(self) -> dict:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                    # Regla de backend de drivers:
                    if sys.platform != "win32":
                        data["driver_backend"] = "viiper"
                    elif "driver_backend" not in data or data["driver_backend"] != "viiper":
                        data["driver_backend"] = "vigem"

                    # Si está en ViGEmBus, solo se permiten xbox360, ds4 o mixed
                    if data.get("driver_backend") == "vigem" and data.get("emulated_type") in ("xboxone", "xbox_one", "dualsense", "ns2pro"):
                        data["emulated_type"] = "xbox360"

                    if "language" not in data:
                        data["language"] = "es"
                    if "author" not in data:
                        data["author"] = "JuanJSAR"
                    if "max_controllers" not in data:
                        data["max_controllers"] = 8
                    if "controllers" not in data or not isinstance(data["controllers"], dict):
                        data["controllers"] = {}
                    for i in range(1, 13):
                        str_i = str(i)
                        if str_i in data["controllers"]:
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

        # Sin archivo previo (instalación limpia): por defecto VIIPER
        cfg = {
            "version": "2.0",
            "author": "JuanJSAR",
            "language": "es",
            "max_controllers": 8,
            "driver_backend": "viiper",
            "emulated_type": "xbox360",
            "games": [],
            "controllers": {}
        }
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
                messagebox.showerror(self.t("msg_error"), self.t("config_error", e=e))

    def _build_ui(self):
        # 1. Cabecera superior compacta
        header_frame = ttk.Frame(self.root, padding="8 3 8 3")
        header_frame.pack(fill=tk.X)

        max_ctrls = self.config.get("max_controllers", 8)
        title_box = ttk.Frame(header_frame)
        title_box.pack(side=tk.LEFT)

        full_title = self.t("header_title", count=max_ctrls)
        prefix = full_title.split("JuanJSAR")[0] if "JuanJSAR" in full_title else full_title

        self.title_lbl = ttk.Label(title_box, text=prefix, font=("Segoe UI", 10, "bold"))
        self.title_lbl.pack(side=tk.LEFT)

        self.lbl_author = ttk.Label(
            title_box,
            text="JuanJSAR" if "JuanJSAR" in full_title else "",
            font=("Segoe UI", 10, "bold"),
            foreground="#0284c7",
            cursor="hand2"
        )
        self.lbl_author.pack(side=tk.LEFT)
        self.lbl_author.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/JuanJSAR93"))
        self.lbl_author.bind("<Enter>", lambda e: self.lbl_author.config(foreground="#0369a1", font=("Segoe UI", 10, "bold underline")))
        self.lbl_author.bind("<Leave>", lambda e: self.lbl_author.config(foreground="#0284c7", font=("Segoe UI", 10, "bold")))

        self.btn_devices = ttk.Button(header_frame, text=self.t("btn_devices"), command=self._open_devices_dialog)
        self.btn_devices.pack(side=tk.LEFT, padx=(12, 4))

        self.btn_settings = ttk.Button(header_frame, text=self.t("btn_settings"), command=self._open_settings_dialog)
        self.btn_settings.pack(side=tk.LEFT, padx=4)

        self.btn_airpad = ttk.Button(header_frame, text=self.t("btn_airpad_main"), command=lambda: self._open_settings_dialog(initial_tab=1))
        self.btn_airpad.pack(side=tk.LEFT, padx=4)

        status_container = ttk.Frame(header_frame)
        status_container.pack(side=tk.RIGHT)

        # 1. Indicador de Emulación
        self.status_dot = tk.Canvas(status_container, width=12, height=12, highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 2))
        self.status_circle = self.status_dot.create_oval(1, 1, 11, 11, fill="#888888", outline="")

        self.status_text_lbl = ttk.Label(status_container, text=self.t("status_stopped"), font=("Segoe UI", 8))
        self.status_text_lbl.pack(side=tk.LEFT, padx=(0, 8))

        # Separador vertical
        sep_status = ttk.Separator(status_container, orient=tk.VERTICAL)
        sep_status.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)

        # 2. Indicador de AirPad
        self.airpad_status_dot = tk.Canvas(status_container, width=12, height=12, highlightthickness=0)
        self.airpad_status_dot.pack(side=tk.LEFT, padx=(6, 2))
        self.airpad_status_circle = self.airpad_status_dot.create_oval(1, 1, 11, 11, fill="#888888", outline="")

        self.airpad_status_text_lbl = ttk.Label(status_container, text=self.t("airpad_status_stopped"), font=("Segoe UI", 8))
        self.airpad_status_text_lbl.pack(side=tk.LEFT)

        # 2. Barra inferior compacta (se empaqueta primero al fondo para garantizar visibilidad)
        bottom_frame = ttk.Frame(self.root, padding="8 4 8 4")
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_toggle_emu = ttk.Button(bottom_frame, text=self.t("btn_start_emu"), command=self._toggle_emulation)
        self.btn_toggle_emu.pack(side=tk.LEFT, padx=4)

        self.btn_joy_cpl = ttk.Button(bottom_frame, text=self.t("btn_joy_cpl"), command=self._open_joy_cpl)
        self.btn_joy_cpl.pack(side=tk.LEFT, padx=4)

        self.btn_hidhide = ttk.Button(bottom_frame, text=self.t("btn_hidhide_client"), command=self._open_hidhide_client)
        self.btn_hidhide.pack(side=tk.LEFT, padx=4)

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

        # 3. Pestañas de controles deslizantes (ScrollableNotebook) y pestaña de Juegos
        self.notebook = ScrollableNotebook(self.root, wheelscroll=True)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=2)

        self.tab_frames = {}
        self.tab_widgets = {}

        self._rebuild_tabs(max_ctrls)

        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._on_tab_changed())
        self._update_airpad_status_ui(force=True)

    def _rebuild_tabs(self, count: int):
        self._update_active_assets()
        # Guardar pestaña seleccionada actualmente si es posible
        cur_idx = 0
        try:
            cur_idx = self.notebook.index(self.notebook.select())
        except Exception:
            pass

        # Limpiar y destruir pestañas anteriores para liberar recursos GDI y evitar fugas
        self.notebook.clear()

        self.tab_frames.clear()
        self.tab_widgets.clear()

        for i in range(1, count + 1):
            tab = ttk.Frame(self.notebook, padding=4)
            tab_text = self.t("tab_control", i=i)
            self.notebook.add(tab, text=f" {tab_text} ")
            self.tab_frames[i] = tab

        # Pestaña fija de Juegos al extremo derecho
        self.tab_games = ttk.Frame(self.notebook, padding=6)
        games_text = self.t("tab_games")
        self.notebook.add(self.tab_games, text=f" {games_text} ")
        self._build_games_tab(self.tab_games)

        target_idx = 0
        if count > 0:
            target_idx = min(cur_idx, count)  # permitir seleccionar pestaña de juegos si estaba activa
            if target_idx < count:
                self._ensure_tab_built(target_idx + 1)
        self.notebook.select(target_idx)

        self._update_header_title(count)
        self._refresh_all_devices(async_scan=False)

    def _ensure_tab_built(self, pad_id: int):
        if pad_id in self.tab_frames and pad_id not in self.tab_widgets:
            parent = self.tab_frames[pad_id]
            self._build_tab_content(pad_id, parent)

            # Si ya se escanearon periféricos físicos previamente, asociar al dev_combo
            if getattr(self, "available_devices", None):
                cb = self.tab_widgets[pad_id].get("dev_combo")
                if cb and cb.winfo_exists():
                    dev_names = []
                    kbd_count = 0
                    for d in self.available_devices:
                        if d.get("id", "").startswith("kbd_"):
                            kbd_count += 1
                            dev_names.append(self.get_device_display_name(d, kbd_count))
                        else:
                            dev_names.append(self.get_device_display_name(d))
                    cb["values"] = dev_names
                    saved_dev_id = self.config.get("controllers", {}).get(str(pad_id), {}).get("physical_device_id", "none")
                    match_idx = 0
                    for idx, dev in enumerate(self.available_devices):
                        if dev["id"] == saved_dev_id:
                            match_idx = idx
                            break
                    try:
                        cb.current(match_idx)
                    except Exception:
                        pass
                    has_dev = (saved_dev_id != "none" and any(d["id"] == saved_dev_id for d in self.available_devices if d["id"] != "none"))
                    self._update_tab_state(pad_id, has_dev)

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

        options = tuple(self.get_input_options())
        def make_row(parent_col, label_text, target_name, label_anchor="w", lbl_width=14):
            row = ttk.Frame(parent_col)
            row.pack(fill=tk.X, pady=1)
            lbl = ttk.Label(row, text=label_text, width=lbl_width, anchor=label_anchor, font=("Segoe UI", 8))
            lbl.pack(side=tk.LEFT)
            cb = ttk.Combobox(row, values=options, width=15, font=("Segoe UI", 8))
            cb.pack(side=tk.LEFT, padx=2)
            cb.bind("<<ComboboxSelected>>", lambda e, p=pad_id, t=target_name, c=cb: self._on_combo_changed(p, t, c))
            btn = ttk.Button(row, text="...", width=3, command=lambda: self._start_record(pad_id, target_name))
            btn.pack(side=tk.LEFT)
            widgets["combos"][target_name] = cb
            widgets["buttons"][target_name] = btn

        pad_type = self.get_pad_emulated_type(pad_id)
        is_ps = pad_type in ("ds4", "dualsense")
        is_switch = (pad_type == "ns2pro")

        # Columna Izquierda
        if is_ps:
            sec_left_title = self.t("sec_left_controls_ds4")
            row_lt_lbl = self.t("row_left_trigger_ds4")
            row_lb_lbl = self.t("row_left_shoulder_ds4")
            row_back_lbl = self.t("row_back_ds4")
            row_start_lbl = self.t("row_start_ds4")
            row_guide_lbl = self.t("row_guide_ds4")
            sec_ls_title = self.t("sec_left_stick_ds4")
            row_ls_btn_lbl = self.t("row_stick_button_l_ds4")
        elif is_switch:
            sec_left_title = self.t("sec_left_controls_ns2pro")
            row_lt_lbl = self.t("row_left_trigger_ns2pro")
            row_lb_lbl = self.t("row_left_shoulder_ns2pro")
            row_back_lbl = self.t("row_back_ns2pro")
            row_start_lbl = self.t("row_start_ns2pro")
            row_guide_lbl = self.t("row_guide_ns2pro")
            sec_ls_title = self.t("sec_left_stick_ns2pro")
            row_ls_btn_lbl = self.t("row_stick_button_l_ns2pro")
        else:
            sec_left_title = self.t("sec_left_controls")
            row_lt_lbl = self.t("row_left_trigger")
            row_lb_lbl = self.t("row_left_shoulder")
            row_back_lbl = self.t("row_back")
            row_start_lbl = self.t("row_start")
            row_guide_lbl = self.t("row_guide")
            sec_ls_title = self.t("sec_left_stick")
            row_ls_btn_lbl = self.t("row_stick_button")

        make_row(left_col, row_lt_lbl, "LEFT_TRIGGER")
        make_row(left_col, row_lb_lbl, "LEFT_SHOULDER")
        make_row(left_col, row_back_lbl, "BACK")
        make_row(left_col, row_start_lbl, "START")
        make_row(left_col, row_guide_lbl, "GUIDE")
        ttk.Separator(left_col, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=2)

        ttk.Label(left_col, text=sec_ls_title, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 1))
        make_row(left_col, self.t("row_stick_axis_x"), "LEFT_STICK_X")
        make_row(left_col, self.t("row_stick_axis_y"), "LEFT_STICK_Y")
        make_row(left_col, row_ls_btn_lbl, "LEFT_THUMB")
        make_row(left_col, self.t("row_stick_up"), "LEFT_STICK_UP")
        make_row(left_col, self.t("row_stick_down"), "LEFT_STICK_DOWN")
        make_row(left_col, self.t("row_stick_left"), "LEFT_STICK_LEFT")
        make_row(left_col, self.t("row_stick_right"), "LEFT_STICK_RIGHT")

        # Columna Central: Imagen SVG y Clic Interactivo
        c_w, c_h = 350, 275
        canvas = tk.Canvas(center_col, width=c_w, height=c_h, bg="#ffffff", highlightthickness=1, highlightbackground="#d0d0d0")
        canvas.pack(pady=2)
        widgets["canvas"] = canvas

        pad_img = self._get_pad_img_tk(pad_id)
        if pad_img:
            canvas.create_image(c_w // 2, c_h // 2, image=pad_img)

        # Vincular clics del ratón para mapear directamente al pulsar en el SVG
        canvas.bind("<Button-1>", lambda e, p=pad_id: self._on_canvas_click(e, p))
        canvas.bind("<Motion>", lambda e, p=pad_id: self._on_canvas_motion(e, p))

        # Indicadores reactivos en el canvas (LEDs de pulsación)
        widgets["leds"] = {}
        for btn_k, (cx, cy, r) in self._get_canvas_points(pad_id).items():
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
        if is_ps:
            sec_right_title = self.t("sec_right_controls_ds4")
            row_rt_lbl = self.t("row_right_trigger_ds4")
            row_rb_lbl = self.t("row_right_shoulder_ds4")
            row_y_lbl = self.t("row_btn_y_ds4")
            row_x_lbl = self.t("row_btn_x_ds4")
            row_b_lbl = self.t("row_btn_b_ds4")
            row_a_lbl = self.t("row_btn_a_ds4")
            sec_rs_title = self.t("sec_right_stick_ds4")
            row_rs_btn_lbl = self.t("row_stick_button_r_ds4")
        elif is_switch:
            sec_right_title = self.t("sec_right_controls_ns2pro")
            row_rt_lbl = self.t("row_right_trigger_ns2pro")
            row_rb_lbl = self.t("row_right_shoulder_ns2pro")
            row_y_lbl = self.t("row_btn_y_ns2pro")
            row_x_lbl = self.t("row_btn_x_ns2pro")
            row_b_lbl = self.t("row_btn_b_ns2pro")
            row_a_lbl = self.t("row_btn_a_ns2pro")
            sec_rs_title = self.t("sec_right_stick_ns2pro")
            row_rs_btn_lbl = self.t("row_stick_button_r_ns2pro")
        else:
            sec_right_title = self.t("sec_right_controls")
            row_rt_lbl = self.t("row_right_trigger")
            row_rb_lbl = self.t("row_right_shoulder")
            row_y_lbl = self.t("row_btn_y")
            row_x_lbl = self.t("row_btn_x")
            row_b_lbl = self.t("row_btn_b")
            row_a_lbl = self.t("row_btn_a")
            sec_rs_title = self.t("sec_right_stick")
            row_rs_btn_lbl = self.t("row_stick_button")

        make_row(right_col, row_rt_lbl, "RIGHT_TRIGGER")
        make_row(right_col, row_rb_lbl, "RIGHT_SHOULDER")
        make_row(right_col, row_y_lbl, "Y")
        make_row(right_col, row_x_lbl, "X")
        make_row(right_col, row_b_lbl, "B")
        make_row(right_col, row_a_lbl, "A")
        ttk.Separator(right_col, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=2)

        ttk.Label(right_col, text=sec_rs_title, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 1))
        make_row(right_col, self.t("row_stick_axis_x"), "RIGHT_STICK_X")
        make_row(right_col, self.t("row_stick_axis_y"), "RIGHT_STICK_Y")
        make_row(right_col, row_rs_btn_lbl, "RIGHT_THUMB")
        make_row(right_col, self.t("row_stick_up"), "RIGHT_STICK_UP")
        make_row(right_col, self.t("row_stick_down"), "RIGHT_STICK_DOWN")
        make_row(right_col, self.t("row_stick_left"), "RIGHT_STICK_LEFT")
        make_row(right_col, self.t("row_stick_right"), "RIGHT_STICK_RIGHT")

        cfg = self.config.get("controllers", {}).get(str(pad_id), {})
        saved_maps = cfg.get("mappings", {})
        for target, cb in widgets["combos"].items():
            val = saved_maps.get(target, DEFAULT_MAPPINGS.get(target, "-- Ninguno --"))
            cb.set(self.localize_mapping(val))

    def _find_target_at_pos(self, click_x: float, click_y: float, pad_id: Optional[int] = None) -> str:
        """Determina qué botón o parte interactiva fue clickeada (excluyendo el Fondo)."""
        pad_type = self.get_pad_emulated_type(pad_id)

        # Centros geométricos de D-Pad y Sticks según el controlador emulado activo
        if pad_type in ("xboxone", "xbox_one"):
            dpad_cx, dpad_cy = 129.8, 165.5
            ls_cx, ls_cy = 81.5, 124.4
            rs_cx, rs_cy = 218.0, 167.9
        elif pad_type == "dualsense":
            dpad_cx, dpad_cy = 68.5, 121.2
            ls_cx, ls_cy = 122.0, 154.2
            rs_cx, rs_cy = 225.5, 154.2
        elif pad_type == "ds4":
            dpad_cx, dpad_cy = 70.0, 126.5
            ls_cx, ls_cy = 123.5, 167.5
            rs_cx, rs_cy = 225.5, 167.5
        elif pad_type == "ns2pro":
            dpad_cx, dpad_cy = 126.3, 171.0
            ls_cx, ls_cy = 79.4, 131.8
            rs_cx, rs_cy = 224.4, 172.0
        else:  # xbox360
            dpad_cx, dpad_cy = 122.5, 189.6
            ls_cx, ls_cy = 63.9, 140.2
            rs_cx, rs_cy = 224.4, 189.6

        # 1. Comprobar cruceta D-Pad
        dx = click_x - dpad_cx
        dy = click_y - dpad_cy
        dist_dpad = math.sqrt(dx * dx + dy * dy)
        if dist_dpad <= 28.0:
            if abs(dy) > abs(dx):
                return "DPAD_UP" if dy < 0 else "DPAD_DOWN"
            else:
                return "DPAD_LEFT" if dx < 0 else "DPAD_RIGHT"

        # 2. Comprobar Stick Izquierdo
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

        # 3. Comprobar Stick Derecho
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

        # 4. Comprobar los demás botones individuales del mando activo
        hitbox_map = self._get_hitboxes(pad_id)
        for btn_name, (bx, by, br) in hitbox_map.items():
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

        target = self._find_target_at_pos(event.x, event.y, pad_id)
        if target:
            canvas.config(cursor="hand2")
            lbl_text = self.target_name(target, pad_id)
            self.hint_lbl.config(text=self.t("hint_click_map", name=lbl_text))
        else:
            canvas.config(cursor="")
            self.hint_lbl.config(text=self.t("hint_canvas_click"))

    def _on_canvas_click(self, event, pad_id: int):
        widgets = self.tab_widgets.get(pad_id, {})
        if not widgets.get("is_device_assigned", True):
            return

        target = self._find_target_at_pos(event.x, event.y, pad_id)
        if target:
            lbl_text = self.target_name(target, pad_id)
            self.hint_lbl.config(text=self.t("hint_mapping_wait", name=lbl_text))
            self._start_record(pad_id, target)

    def _build_calib_row(self, parent, label_text: str, from_: float, to: float, init_val: float, var_holder: dict, var_key: str, widgets: dict = None, entry_from: float = None, entry_to: float = None):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=1)

        ttk.Label(row, text=label_text, width=16, font=("Segoe UI", 8)).pack(side=tk.LEFT)

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

        pad_type = self.get_pad_emulated_type(pad_id)
        if pad_type in ("ds4", "dualsense"):
            t_lt = self.t("title_left_trigger_ds4")
            t_rt = self.t("title_right_trigger_ds4")
        elif pad_type == "ns2pro":
            t_lt = self.t("title_left_trigger_ns2pro")
            t_rt = self.t("title_right_trigger_ns2pro")
        else:
            t_lt = self.t("title_left_trigger")
            t_rt = self.t("title_right_trigger")
        make_trigger_panel(parent, "left_trigger", t_lt)
        make_trigger_panel(parent, "right_trigger", t_rt)

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

        pad_type = self.get_pad_emulated_type(pad_id)
        if pad_type in ("ds4", "dualsense"):
            t_ls = self.t("title_left_stick_ds4")
            t_rs = self.t("title_right_stick_ds4")
        elif pad_type == "ns2pro":
            t_ls = self.t("title_left_stick_ns2pro")
            t_rs = self.t("title_right_stick_ns2pro")
        else:
            t_ls = self.t("title_left_stick")
            t_rs = self.t("title_right_stick")
        make_stick_box(parent, "left_stick", t_ls)
        make_stick_box(parent, "right_stick", t_rs)

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

    def _apply_refreshed_devices(self, new_devices: List[Dict[str, Any]]):
        self.available_devices = new_devices
        dev_names = []
        kbd_count = 0
        for d in self.available_devices:
            if d.get("id", "").startswith("kbd_"):
                kbd_count += 1
                dev_names.append(self.get_device_display_name(d, kbd_count))
            else:
                dev_names.append(self.get_device_display_name(d))

        for pad_id, widgets in list(self.tab_widgets.items()):
            cb = widgets.get("dev_combo")
            if not cb or not cb.winfo_exists():
                continue
            cb["values"] = dev_names

            cfg = self.config.get("controllers", {}).get(str(pad_id), {})
            saved_dev_id = cfg.get("physical_device_id", "none")

            match_idx = 0
            for idx, dev in enumerate(self.available_devices):
                if dev["id"] == saved_dev_id:
                    match_idx = idx
                    break
            try:
                cb.current(match_idx)
            except Exception:
                pass

            has_dev = (saved_dev_id != "none" and any(d["id"] == saved_dev_id for d in self.available_devices if d["id"] != "none"))
            self._update_tab_state(pad_id, has_dev)

    def _refresh_all_devices(self, async_scan: bool = False):
        if async_scan:
            def _worker():
                devs = self.device_manager.refresh_devices()
                try:
                    self.root.after(0, self._apply_refreshed_devices, devs)
                except Exception:
                    pass
            threading.Thread(target=_worker, daemon=True, name="refresh-devices-worker").start()
        else:
            devs = self.device_manager.refresh_devices()
            self._apply_refreshed_devices(devs)

    def _on_devices_hotplugged(self, new_devices: List[Dict[str, Any]]):
        """Manejador ejecutado en el hilo de la UI cuando el DeviceManager auto-reconecta mandos."""
        try:
            old_dev_ids = {d["id"] for d in getattr(self, "available_devices", []) if d["id"] != "none"}
            current_dev_ids = {d["id"] for d in new_devices if d["id"] != "none"}
            newly_added_ids = current_dev_ids - old_dev_ids

            self._apply_refreshed_devices(new_devices)

            auto_usb = self.config.get("auto_assign_usb", True)
            auto_phone = self.config.get("airpad_auto_assign", True)

            # Auto-asignación de dispositivos nuevos a ranuras libres
            if newly_added_ids and (auto_usb or auto_phone):
                assigned_now = {
                    cfg.get("physical_device_id")
                    for cfg in self.config.get("controllers", {}).values()
                    if cfg.get("physical_device_id") and cfg.get("physical_device_id") != "none"
                }

                for new_id in newly_added_ids:
                    if new_id in assigned_now:
                        continue
                    is_usb = new_id.startswith("joy_")
                    is_phone = new_id.startswith("phone_")
                    if (is_usb and auto_usb) or (is_phone and auto_phone):
                        for pad_id in sorted(self.tab_widgets.keys()):
                            widgets = self.tab_widgets[pad_id]
                            cfg = self.config.get("controllers", {}).get(str(pad_id), {})
                            cur_p_id = cfg.get("physical_device_id", "none")
                            if cur_p_id == "none":
                                cfg["physical_device_id"] = new_id
                                assigned_now.add(new_id)

                                if is_phone:
                                    cur_maps = cfg.get("mappings", {})
                                    all_none = all(is_none_mapping(v) for v in cur_maps.values())
                                    if all_none or not cur_maps:
                                        cfg["mappings"] = dict(DEFAULT_PHONE_MAPPINGS)
                                        for target, t_cb in widgets.get("combos", {}).items():
                                            t_cb.set(self.localize_mapping(DEFAULT_PHONE_MAPPINGS.get(target, "-- Ninguno --")))

                                for idx, dev in enumerate(self.available_devices):
                                    if dev["id"] == new_id:
                                        widgets["dev_combo"].current(idx)
                                        break
                                self._update_tab_state(pad_id, True)
                                break

                self._sync_ui_to_config()
                self.engine.set_config(self.config)
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

            if dev_id.startswith("phone_"):
                cur_maps = self.config["controllers"][str(pad_id)].get("mappings", {})
                all_none = all(is_none_mapping(v) for v in cur_maps.values())
                if all_none or not cur_maps:
                    self.config["controllers"][str(pad_id)]["mappings"] = dict(DEFAULT_PHONE_MAPPINGS)
                    for target, cb in widgets.get("combos", {}).items():
                        cb.set(self.localize_mapping(DEFAULT_PHONE_MAPPINGS.get(target, "-- Ninguno --")))

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
                raw_val = cb.get().strip()
                mappings[target] = self.canonicalize_mapping(raw_val)
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
        can_new = self.canonicalize_mapping(new_mapping)
        if not can_new or is_none_mapping(can_new):
            return None

        current_cfg = self.config.get("controllers", {}).get(str(current_pad_id), {})
        current_maps = current_cfg.get("mappings", {})

        # 1. Comprobar si ya esta asignada en OTRA posicion de este mismo mando
        for other_btn, mapped_val in current_maps.items():
            can_other = self.canonicalize_mapping(mapped_val)
            if other_btn != target_name and can_other and can_other.lower() == can_new.lower():
                return ("same", current_pad_id, current_cfg.get("name", self.t("tab_control", i=current_pad_id)), other_btn)

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
                        can_other = self.canonicalize_mapping(mapped_val)
                        if can_other and can_other.lower() == can_new.lower():
                            other_name = other_cfg.get("name", self.t("tab_control", i=other_id))
                            return ("other", other_id, other_name, other_btn)
        return None

    def _apply_mapping_with_conflict_check(self, pad_id: int, target_name: str, new_val: str, combo: ttk.Combobox = None) -> bool:
        new_val = new_val.strip()
        can_new = self.canonicalize_mapping(new_val)
        display_val = self.localize_mapping(can_new)
        prev_val = self.config.get("controllers", {}).get(str(pad_id), {}).get("mappings", {}).get(target_name, "-- Ninguno --")

        if not is_none_mapping(can_new):
            conflict = self._check_mapping_conflict(pad_id, target_name, can_new)
            if conflict:
                conflict_type, other_id, other_name, other_btn = conflict
                other_btn_str = self.target_name(other_btn)
                target_name_str = self.target_name(target_name)

                if conflict_type == "same":
                    ans = messagebox.askyesnocancel(
                        self.t("conflict_same_title"),
                        self.t("conflict_same_msg", val=display_val, other=other_btn_str, target=target_name_str),
                        icon="warning"
                    )
                    if ans is None:
                        if combo:
                            combo.set(self.localize_mapping(prev_val))
                        return False
                    elif ans is True:
                        self.config["controllers"][str(pad_id)]["mappings"][other_btn] = "-- Ninguno --"
                        if pad_id in self.tab_widgets:
                            other_cb = self.tab_widgets[pad_id]["combos"].get(other_btn)
                            if other_cb:
                                other_cb.set(self.get_none_label())

                elif conflict_type == "other":
                    ans = messagebox.askyesnocancel(
                        self.t("conflict_other_title"),
                        self.t("conflict_other_msg", val=display_val, other=other_btn_str, name=other_name, id=other_id),
                        icon="warning"
                    )
                    if ans is None:
                        if combo:
                            combo.set(self.localize_mapping(prev_val))
                        return False
                    elif ans is True:
                        str_other = str(other_id)
                        if str_other in self.config.get("controllers", {}):
                            self.config["controllers"][str_other]["mappings"][other_btn] = "-- Ninguno --"
                        if other_id in self.tab_widgets:
                            other_cb = self.tab_widgets[other_id]["combos"].get(other_btn)
                            if other_cb:
                                other_cb.set(self.get_none_label())

        cb = combo or self.tab_widgets.get(pad_id, {}).get("combos", {}).get(target_name)
        if cb:
            cb.set(display_val)

        self._sync_ui_to_config()
        return True

    def _on_combo_changed(self, pad_id: int, target_name: str, combo: ttk.Combobox):
        val = combo.get().strip()
        self._apply_mapping_with_conflict_check(pad_id, target_name, val, combo=combo)

    def _prev_tab(self):
        if not hasattr(self, "notebook"):
            return
        tabs = self.notebook.tabs()
        if not tabs:
            return
        try:
            cur = self.notebook.index(self.notebook.select())
            if cur > 0:
                self.notebook.select(cur - 1)
        except Exception:
            pass

    def _next_tab(self):
        if not hasattr(self, "notebook"):
            return
        tabs = self.notebook.tabs()
        if not tabs:
            return
        try:
            cur = self.notebook.index(self.notebook.select())
            if cur < len(tabs) - 1:
                self.notebook.select(cur + 1)
        except Exception:
            pass

    def _on_notebook_mousewheel(self, event):
        if not hasattr(self, "notebook"):
            return
        tabs = self.notebook.tabs()
        if not tabs:
            return
        try:
            cur = self.notebook.index(self.notebook.select())
            if event.delta > 0 and cur > 0:
                self.notebook.select(cur - 1)
            elif event.delta < 0 and cur < len(tabs) - 1:
                self.notebook.select(cur + 1)
        except Exception:
            pass

    def _on_tab_changed(self):
        if self.recording_target:
            self._cancel_recording()
        try:
            sel = self.notebook.select()
            if sel:
                idx = self.notebook.index(sel)
                pad_id = idx + 1
                if pad_id in self.tab_frames:
                    self._ensure_tab_built(pad_id)
        except Exception:
            pass

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

    def _is_device_path_hidden(self, path: Optional[str]) -> bool:
        """Comprueba de forma insensible a mayúsculas si una ruta PnP está marcada para ocultar."""
        if not path:
            return False
        norm = path.strip().upper()
        return any(isinstance(p, str) and p.strip().upper() == norm for p in self.config.get("hidden_devices", []))

    def _mark_device_hidden(self, path: str):
        """Marca una ruta PnP para ser ocultada al emular de forma normalizada."""
        if not path:
            return
        norm = path.strip().upper()
        current = [p.strip().upper() for p in self.config.get("hidden_devices", []) if isinstance(p, str) and p.strip().upper() != norm]
        current.append(norm)
        self.config["hidden_devices"] = current
        self.save_config(silent=True)

    def _unmark_device_hidden(self, path: str):
        """Desmarca una ruta PnP de la lista de ocultos."""
        if not path:
            return
        norm = path.strip().upper()
        current = [p.strip().upper() for p in self.config.get("hidden_devices", []) if isinstance(p, str) and p.strip().upper() != norm]
        self.config["hidden_devices"] = current
        self.save_config(silent=True)

    def _hide_emulation_devices(self):
        """Oculta únicamente los dispositivos explícitamente marcados con HidHide cuando inicia la emulación."""
        if not self.driver_manager.is_hidhide_installed():
            return

        hidden_devs = [p.strip().upper() for p in self.config.get("hidden_devices", []) if isinstance(p, str) and p.strip()]
        if not hidden_devs:
            return

        # Registrar j360More en la lista blanca de HidHide para que la app siempre pueda leerlos
        self.driver_manager.ensure_process_whitelisted()

        for inst_path in hidden_devs:
            self.driver_manager.hide_device(inst_path)

        self.driver_manager.set_cloak_active(True)

    def _unhide_emulation_devices(self):
        """Restaura la visibilidad de los dispositivos para todo el sistema cuando se detiene la emulación."""
        if not self.driver_manager.is_hidhide_installed():
            return

        hidden_devs = [p.strip().upper() for p in self.config.get("hidden_devices", []) if isinstance(p, str) and p.strip()]
        for inst_path in hidden_devs:
            self.driver_manager.unhide_device(inst_path)

        # Desactivar siempre el cloaking global de HidHide al detener la emulación
        self.driver_manager.set_cloak_active(False)

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
            val = DEFAULT_MAPPINGS.get(target, "-- Ninguno --")
            cb.set(self.localize_mapping(val))

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
        messagebox.showinfo(self.t("preset_title"), self.t("preset_restored", i=cur_pad_id))

    def _check_system_drivers(self):
        """Verifica la disponibilidad de drivers según el backend configurado."""
        driver_backend = self.config.get("driver_backend", "vigem")
        if driver_backend == "vigem":
            if not self.driver_manager.is_vigem_installed():
                messagebox.showerror(
                    self.t("vigem_missing_title"),
                    self.t("vigem_missing_msg")
                )
        else:
            from viiper_backend import is_usbip_installed, get_viiper_binary_path
            if not get_viiper_binary_path():
                messagebox.showwarning(
                    self.t("viiper_missing_title"),
                    self.t("viiper_binary_missing_msg")
                )
            elif sys.platform == "win32" and not is_usbip_installed():
                messagebox.showwarning(
                    self.t("usbip_missing_title"),
                    self.t("usbip_missing_msg")
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
                        release_url = f"https://github.com/JuanJSAR93/j360More-Xbox_360_Controller_Emulator/releases/tag/{tag_name}"
                        self.root.after(0, lambda t=clean_tag, u=release_url: self._on_update_detected(t, u))
        except Exception:
            # En caso de falta de conexion o timeout, se omite silenciosamente sin interrumpir
            pass

    def _on_update_detected(self, latest_ver: str, release_url: str = None):
        """Actualiza el indicador de version en la barra inferior haciendolo interactivo."""
        if not hasattr(self, "lbl_version"):
            return
        target_url = release_url or f"https://github.com/JuanJSAR93/j360More-Xbox_360_Controller_Emulator/releases/tag/{latest_ver}"
        self._update_release_url = target_url

        alert_text = self.t("new_version_available", ver=latest_ver)
        self.lbl_version.config(
            text=f"v{APP_VERSION}  {alert_text}",
            foreground="#b45309",
            cursor="hand2"
        )
        self.lbl_version.bind("<Button-1>", lambda e: webbrowser.open(self._update_release_url))

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
        self._setup_modal_dialog(dlg)

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

    def _open_settings_dialog(self, initial_tab: int = 0):
        """Ventana modal de configuración con pestañas General (Emulación/HidHide/Auto-asignación) y Mandos Móviles AirPad."""
        dlg = tk.Toplevel(self.root)
        dlg.title(self.t("set_dlg_title"))
        dlg.geometry("750x710")
        dlg.resizable(False, False)
        self._setup_modal_dialog(dlg)

        x = max(0, self.root.winfo_x() + (self.root.winfo_width() // 2) - 375)
        y = max(0, self.root.winfo_y() + (self.root.winfo_height() // 2) - 355)
        dlg.geometry(f"750x710+{x}+{y}")

        main_box = ttk.Frame(dlg, padding=8)
        main_box.pack(fill=tk.BOTH, expand=True)

        notebook_settings = ttk.Notebook(main_box)
        notebook_settings.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 8))

        # ==================== PESTAÑA 1: GENERAL & EMULACIÓN ====================
        tab_general = ttk.Frame(notebook_settings, padding=10)
        notebook_settings.add(tab_general, text=self.t("set_tab_general"))

        # SECCION 1: Idioma / Language
        box_lang = ttk.LabelFrame(tab_general, text="🌐 " + self.t("set_language_label"), padding=8)
        box_lang.pack(fill=tk.X, pady=(0, 6))

        cur_lang_code = self.config.get("language", "es")
        if cur_lang_code not in SUPPORTED_LANGUAGES:
            cur_lang_code = "es"
        cur_lang_str = SUPPORTED_LANGUAGES[cur_lang_code]
        lang_var = tk.StringVar(value=cur_lang_str)

        lang_combo = ttk.Combobox(box_lang, textvariable=lang_var, values=list(SUPPORTED_LANGUAGES.values()), state="readonly", width=25)
        lang_combo.pack(anchor="w", padx=4, pady=2)

        # SECCION 2: Backend de Driver Virtual (VIIPER vs ViGEmBus)
        box_driver = ttk.LabelFrame(tab_general, text="⚡ " + self.t("set_driver_title"), padding=8)
        box_driver.pack(fill=tk.X, pady=(0, 6))

        cur_driver = self.config.get("driver_backend", "vigem")
        if sys.platform != "win32":
            cur_driver = "viiper"
        driver_var = tk.StringVar(value=cur_driver)

        driver_row = ttk.Frame(box_driver)
        driver_row.pack(fill=tk.X, padx=4, pady=2)

        def on_driver_changed():
            d = driver_var.get()
            if d == "vigem":
                rb_xbone.configure(state="disabled")
                rb_ps5.configure(state="disabled")
                rb_ns2.configure(state="disabled")
                if type_var.get() in ("xboxone", "xbox_one", "dualsense", "ns2pro"):
                    type_var.set("xbox360")
                    on_type_changed()
            else:
                rb_xbone.configure(state="normal")
                rb_ps5.configure(state="normal")
                rb_ns2.configure(state="normal")

        rb_viiper = ttk.Radiobutton(driver_row, text=self.t("set_driver_viiper"), variable=driver_var, value="viiper", command=on_driver_changed)
        rb_viiper.pack(anchor="w", pady=1)

        vigem_state = "normal" if sys.platform == "win32" else "disabled"
        rb_vigem = ttk.Radiobutton(driver_row, text=self.t("set_driver_vigem"), variable=driver_var, value="vigem", state=vigem_state, command=on_driver_changed)
        rb_vigem.pack(anchor="w", pady=1)

        ttk.Label(box_driver, text=self.t("set_driver_desc"), font=("Segoe UI", 8), foreground="#555555", wraplength=660).pack(anchor="w", padx=4, pady=(2, 0))

        # SECCION 3: Tipo de mando virtual emulado
        box_type = ttk.LabelFrame(tab_general, text="🎮 " + self.t("set_emulated_type_title"), padding=8)
        box_type.pack(fill=tk.X, pady=(0, 6))

        cur_type = self.config.get("emulated_type", "xbox360").lower()
        if driver_var.get() == "vigem" and cur_type in ("xboxone", "xbox_one", "dualsense", "ns2pro"):
            cur_type = "xbox360"
        type_var = tk.StringVar(value=cur_type)

        def get_ctrl_label(cnt):
            t = type_var.get().lower()
            base = self.t("set_ctrl_count_1") if cnt == 1 else self.t("set_ctrl_count", count=cnt)
            if t in ("mixed", "mixto"):
                half = cnt // 2
                return f"{base}  ({half} Xbox + {half} DS4)"
            return base

        is_updating = [False]

        def on_type_changed():
            t = type_var.get().lower()
            cur = val_var.get()
            if t in ("mixed", "mixto"):
                if cur % 2 != 0:
                    new_cur = min(12, cur + 1)
                    if new_cur < 2:
                        new_cur = 2
                    val_var.set(new_cur)
                    is_updating[0] = True
                    try:
                        slider.set(new_cur)
                    finally:
                        is_updating[0] = False
                slider.configure(from_=2)
            else:
                slider.configure(from_=1)
            val_display.config(text=get_ctrl_label(val_var.get()))

        type_row = ttk.Frame(box_type)
        type_row.pack(fill=tk.X, padx=4, pady=2)
        ttk.Radiobutton(type_row, text=self.t("set_emulated_type_x360"), variable=type_var, value="xbox360", command=on_type_changed).pack(side=tk.LEFT, padx=(0, 10))
        rb_xbone = ttk.Radiobutton(type_row, text=self.t("set_emulated_type_xboxone"), variable=type_var, value="xboxone", command=on_type_changed)
        rb_xbone.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(type_row, text=self.t("set_emulated_type_ds4"), variable=type_var, value="ds4", command=on_type_changed).pack(side=tk.LEFT, padx=(0, 10))
        rb_ps5 = ttk.Radiobutton(type_row, text=self.t("set_emulated_type_dualsense"), variable=type_var, value="dualsense", command=on_type_changed)
        rb_ps5.pack(side=tk.LEFT, padx=(0, 10))
        rb_ns2 = ttk.Radiobutton(type_row, text=self.t("set_emulated_type_ns2pro"), variable=type_var, value="ns2pro", command=on_type_changed)
        rb_ns2.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(type_row, text=self.t("set_emulated_type_mixed"), variable=type_var, value="mixed", command=on_type_changed).pack(side=tk.LEFT)

        if driver_var.get() == "vigem":
            rb_xbone.configure(state="disabled")
            rb_ps5.configure(state="disabled")
            rb_ns2.configure(state="disabled")

        ttk.Label(box_type, text=self.t("set_emulated_type_desc"), font=("Segoe UI", 8), foreground="#555555", wraplength=660).pack(anchor="w", padx=4, pady=(2, 0))

        # SECCION 4: Mandos virtuales a emular (Slider 1 a 12)
        box_mandos = ttk.LabelFrame(tab_general, text=self.t("set_mandos_title"), padding=8)
        box_mandos.pack(fill=tk.X, pady=(0, 6))

        current_val = self.config.get("max_controllers", 8)
        if cur_type in ("mixed", "mixto") and current_val % 2 != 0:
            current_val = max(2, min(12, current_val + 1))
        val_var = tk.IntVar(value=current_val)

        val_display = ttk.Label(box_mandos, text=get_ctrl_label(current_val), font=("Segoe UI", 10, "bold"), foreground="#0066cc")
        val_display.pack(anchor="center", pady=(0, 2))

        def on_slider(v):
            if is_updating[0]:
                return
            is_updating[0] = True
            try:
                f_val = float(v)
                if type_var.get().lower() in ("mixed", "mixto"):
                    ival = max(2, min(12, int(round(f_val / 2.0) * 2)))
                else:
                    ival = max(1, min(12, int(round(f_val))))
                val_var.set(ival)
                val_display.config(text=get_ctrl_label(ival))
            finally:
                is_updating[0] = False

        init_from = 2 if cur_type in ("mixed", "mixto") else 1
        slider = ttk.Scale(box_mandos, from_=init_from, to=12, orient=tk.HORIZONTAL, value=current_val, command=on_slider)
        slider.pack(fill=tk.X, pady=2)
        slider.bind("<ButtonRelease-1>", lambda e: slider.set(val_var.get()))

        ticks_frame = ttk.Frame(box_mandos)
        ticks_frame.pack(fill=tk.X)
        ttk.Label(ticks_frame, text=self.t("set_1_controller"), font=("Segoe UI", 8)).pack(side=tk.LEFT)
        ttk.Label(ticks_frame, text=self.t("set_6_controllers"), font=("Segoe UI", 8)).pack(side=tk.LEFT, expand=True)
        ttk.Label(ticks_frame, text=self.t("set_12_controllers"), font=("Segoe UI", 8)).pack(side=tk.RIGHT)

        # SECCION 5: Integración con HidHide (Opcional)
        box_hidhide = ttk.LabelFrame(tab_general, text=self.t("set_hidhide_title"), padding=8)
        box_hidhide.pack(fill=tk.X, pady=(0, 6))

        is_installed = self.driver_manager.is_hidhide_installed()
        status_text = self.t("set_status_installed") if is_installed else self.t("set_status_missing")
        status_color = "#16a34a" if is_installed else "#d97706"

        status_lbl = ttk.Label(box_hidhide, text=self.t("set_status_lbl", status=status_text), font=("Segoe UI", 8, "bold"), foreground=status_color)
        status_lbl.pack(anchor="w", pady=(0, 2))

        path_row = ttk.Frame(box_hidhide)
        path_row.pack(fill=tk.X, pady=(2, 2))

        current_path = self.driver_manager.get_hidhide_cli_path() or ""
        path_var = tk.StringVar(value=current_path)
        entry_path = ttk.Entry(path_row, textvariable=path_var, font=("Segoe UI", 8))
        entry_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        def on_browse_hidhide():
            chosen = filedialog.askopenfilename(
                title=self.t("set_browse_title"),
                filetypes=[(self.t("filetype_hidhide_cli"), "HidHideCLI.exe"), (self.t("ft_executables"), "*.exe"), (self.t("ft_all_files"), "*.*")]
            )
            if chosen:
                path_var.set(chosen)

        btn_browse = ttk.Button(path_row, text=self.t("set_btn_browse"), command=on_browse_hidhide)
        btn_browse.pack(side=tk.RIGHT)

        cloak_active_var = tk.BooleanVar(value=self.driver_manager.is_cloak_active() if is_installed else True)
        chk_cloak = ttk.Checkbutton(box_hidhide, text=self.t("set_chk_cloak"), variable=cloak_active_var)
        chk_cloak.pack(anchor="w", pady=1)

        warn_suppressed = self.config.get("suppress_hidhide_warning", False)
        show_warn_var = tk.BooleanVar(value=not warn_suppressed)
        chk_warn = ttk.Checkbutton(box_hidhide, text=self.t("set_chk_warn"), variable=show_warn_var)
        chk_warn.pack(anchor="w", pady=1)

        # SECCION 6: Auto-asignación para mandos USB
        auto_assign_usb_var = tk.BooleanVar(value=self.config.get("auto_assign_usb", True))
        chk_auto_usb = ttk.Checkbutton(tab_general, text=self.t("set_auto_assign_usb"), variable=auto_assign_usb_var)
        chk_auto_usb.pack(anchor="w", padx=4, pady=(4, 2))


        # ==================== PESTAÑA 2: MANDOS MÓVILES (AIRPAD) ====================
        tab_airpad = ttk.Frame(notebook_settings, padding=10)
        notebook_settings.add(tab_airpad, text=self.t("set_tab_airpad"))
        if initial_tab == 1:
            notebook_settings.select(tab_airpad)

        srv = web_gamepad_server.get_server_instance()

        # Fila superior de control del servidor
        top_ctrls = ttk.Frame(tab_airpad)
        top_ctrls.pack(fill=tk.X, pady=(0, 10))

        airpad_srv_enabled_var = tk.BooleanVar(value=srv.running)
        port_var = tk.StringVar(value=str(getattr(srv, "port", self.config.get("airpad_server_port", 8080))))

        def update_srv_status_label():
            if srv.running:
                lbl_srv_status.config(
                    text=self.t("airpad_server_active", url=srv.get_url()),
                    foreground="#16a34a"
                )
                btn_toggle_srv.config(text=self.t("airpad_btn_turn_off"))
            else:
                lbl_srv_status.config(
                    text=self.t("airpad_server_stopped"),
                    foreground="#dc2626"
                )
                btn_toggle_srv.config(text=self.t("airpad_btn_turn_on"))

        def toggle_server_state():
            if srv.running:
                srv.stop()
                airpad_srv_enabled_var.set(False)
                self.config["airpad_server_enabled"] = False
            else:
                try:
                    srv.port = int(port_var.get().strip())
                except Exception:
                    srv.port = 8080
                srv.start()
                airpad_srv_enabled_var.set(True)
                self.config["airpad_server_enabled"] = True
            self.save_config(silent=True)
            update_srv_status_label()
            update_qr_code()
            self._update_airpad_status_ui(force=True)

        def restart_airpad():
            try:
                p = int(port_var.get().strip())
                srv.port = p
            except Exception:
                p = 8080
                port_var.set("8080")
                srv.port = 8080
            srv.stop()
            if airpad_srv_enabled_var.get():
                srv.start()
            self.config["airpad_server_port"] = srv.port
            self.save_config(silent=True)
            update_srv_status_label()
            update_qr_code()
            self._update_airpad_status_ui(force=True)

        btn_toggle_srv = ttk.Button(top_ctrls, text=self.t("airpad_btn_turn_on"), command=toggle_server_state)
        btn_toggle_srv.pack(side=tk.LEFT, padx=(0, 10))

        lbl_srv_status = ttk.Label(top_ctrls, text="", font=("Segoe UI", 9, "bold"))
        lbl_srv_status.pack(side=tk.LEFT, padx=(0, 10))

        port_box = ttk.Frame(top_ctrls)
        port_box.pack(side=tk.RIGHT)
        ttk.Label(port_box, text=self.t("airpad_port_label"), font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(0, 4))
        entry_port = ttk.Entry(port_box, textvariable=port_var, width=6, font=("Segoe UI", 8))
        entry_port.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(port_box, text=self.t("airpad_btn_restart"), command=restart_airpad).pack(side=tk.LEFT)

        # Selector de Interfaz de Red / IP
        ip_row = ttk.Frame(tab_airpad)
        ip_row.pack(fill=tk.X, pady=(0, 6))

        all_ip_data = web_gamepad_server.get_all_local_ips()
        ip_choices = [item["ip"] if isinstance(item, dict) else str(item) for item in all_ip_data]
        if not ip_choices:
            ip_choices = ["127.0.0.1"]
        default_ip = srv.preferred_ip or self.config.get("airpad_bind_ip") or ip_choices[0]
        if default_ip not in ip_choices:
            ip_choices.insert(0, default_ip)

        ip_var = tk.StringVar(value=default_ip)

        ttk.Label(ip_row, text=self.t("airpad_ip_label"), font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 6))
        combo_ip = ttk.Combobox(ip_row, textvariable=ip_var, values=ip_choices, state="readonly", width=18, font=("Segoe UI", 9))
        combo_ip.pack(side=tk.LEFT, padx=(0, 8))

        def on_ip_selected(event=None):
            chosen_ip = ip_var.get()
            srv.preferred_ip = chosen_ip
            self.config["airpad_bind_ip"] = chosen_ip
            self.save_config(silent=True)
            update_srv_status_label()
            update_qr_code()

        combo_ip.bind("<<ComboboxSelected>>", on_ip_selected)

        lbl_ip_hint = ttk.Label(ip_row, text=self.t("airpad_ip_hint"), font=("Segoe UI", 8), foreground="#666666")
        lbl_ip_hint.pack(side=tk.LEFT)

        # Panel Superior: QR y URL (Escanea este código QR con la cámara de tu smartphone...)
        qr_box = ttk.LabelFrame(tab_airpad, text="📷 " + self.t("airpad_scan_qr_desc"), padding=8)
        qr_box.pack(fill=tk.X, pady=(0, 6))

        # Marco con tamaño fijo para que la caja no cambie de tamaño entre QR y mensaje de apagado
        qr_frame = tk.Frame(qr_box, width=170, height=170, bg="white", relief="solid", borderwidth=1)
        qr_frame.pack(side=tk.LEFT, padx=(4, 14), pady=2)
        qr_frame.pack_propagate(False)

        lbl_qr = tk.Label(qr_frame, bg="white")
        lbl_qr.pack(fill=tk.BOTH, expand=True)

        qr_info_box = ttk.Frame(qr_box)
        qr_info_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        lbl_hint = ttk.Label(qr_info_box, text=self.t("airpad_scan_hint"), wraplength=470, font=("Segoe UI", 9))
        lbl_hint.pack(anchor="w", pady=(4, 6))

        entry_url = ttk.Entry(qr_info_box, font=("Segoe UI", 9, "bold"), justify="center")
        entry_url.pack(fill=tk.X, pady=(0, 6))

        btn_url_row = ttk.Frame(qr_info_box)
        btn_url_row.pack(fill=tk.X, pady=(0, 6))

        def copy_url_to_clipboard():
            url = srv.get_url()
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            btn_copy.config(text=self.t("airpad_url_copied"))
            dlg.after(2000, lambda: btn_copy.config(text=self.t("airpad_btn_copy_url")))

        btn_copy = ttk.Button(btn_url_row, text=self.t("airpad_btn_copy_url"), command=copy_url_to_clipboard)
        btn_copy.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))

        btn_open = ttk.Button(btn_url_row, text=self.t("airpad_btn_open_browser"), command=lambda: webbrowser.open(srv.get_url()))
        btn_open.pack(side=tk.RIGHT, expand=True, fill=tk.X)

        lbl_subhint = ttk.Label(qr_info_box, text="⚡ Conexión instantánea sin apps • Compatible con iOS Safari y Android Chrome", font=("Segoe UI", 8), foreground="#555555")
        lbl_subhint.pack(anchor="w", pady=(2, 0))

        def update_qr_code():
            if not srv.running:
                lbl_qr.config(image="", text=self.t("airpad_srv_off_box"), font=("Segoe UI", 9, "bold"), fg="#dc2626", justify="center")
                lbl_qr.image = None
                entry_url.config(state="normal")
                entry_url.delete(0, tk.END)
                entry_url.insert(0, self.t("airpad_disabled_url"))
                entry_url.config(state="readonly")
                btn_copy.config(state="disabled")
                btn_open.config(state="disabled")
            else:
                url = srv.get_url()
                entry_url.config(state="normal")
                entry_url.delete(0, tk.END)
                entry_url.insert(0, url)
                entry_url.config(state="readonly")
                btn_copy.config(state="normal")
                btn_open.config(state="normal")

                qr_done = False
                if qrcode:
                    try:
                        qr = qrcode.QRCode(box_size=4, border=2)
                        qr.add_data(url)
                        qr.make(fit=True)
                        qr_img = qr.make_image(fill_color="black", back_color="white")
                        qr_img = qr_img.resize((165, 165), Image.Resampling.NEAREST)
                        qr_photo = ImageTk.PhotoImage(qr_img)
                        lbl_qr.config(image=qr_photo, text="")
                        lbl_qr.image = qr_photo
                        qr_done = True
                    except Exception as ex:
                        logger.warning(f"Error renderizando código QR: {ex}")
                if not qr_done:
                    lbl_qr.config(image="", text=url, font=("Segoe UI", 8), fg="black", justify="center")
                    lbl_qr.image = None

        update_srv_status_label()
        update_qr_code()

        # Panel Inferior: Tabla scrollable de ranuras (igual al número de mandos virtuales a emular)
        devices_box = ttk.LabelFrame(tab_airpad, text="📱 " + self.t("airpad_devices_title"), padding=8)
        devices_box.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        tree_frame = ttk.Frame(devices_box)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        cols = ("slot", "device", "assigned")
        tree_devices = ttk.Treeview(tree_frame, columns=cols, show="headings", height=5, yscrollcommand=scroll_y.set, selectmode="browse")
        scroll_y.config(command=tree_devices.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree_devices.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tree_devices.heading("slot", text="#")
        tree_devices.heading("device", text="Dispositivo / IP")
        tree_devices.heading("assigned", text="Asignado")
        tree_devices.column("slot", width=36, anchor="center", stretch=False)
        tree_devices.column("device", width=420, anchor="w")
        tree_devices.column("assigned", width=120, anchor="center")

        right_bot_row = ttk.Frame(devices_box)
        right_bot_row.pack(fill=tk.X)

        def kick_selected_phone():
            sel = tree_devices.selection()
            if sel:
                slot_id = sel[0]
                srv.kick_client(slot_id)
                refresh_airpad_tree()

        btn_kick = ttk.Button(right_bot_row, text="❌ " + self.t("airpad_btn_kick"), command=kick_selected_phone)
        btn_kick.pack(side=tk.RIGHT, padx=2)

        # Opciones inferiores de la pestaña AirPad
        bot_options = ttk.Frame(tab_airpad)
        bot_options.pack(fill=tk.X, pady=(2, 0))

        airpad_auto_assign_var = tk.BooleanVar(value=self.config.get("airpad_auto_assign", True))
        chk_auto_phone = ttk.Checkbutton(bot_options, text=self.t("airpad_chk_auto_assign"), variable=airpad_auto_assign_var)
        chk_auto_phone.pack(anchor="w", pady=2)

        airpad_haptics_var = tk.BooleanVar(value=self.config.get("airpad_haptics_enabled", True))
        chk_haptics = ttk.Checkbutton(bot_options, text=self.t("airpad_chk_haptics"), variable=airpad_haptics_var)
        chk_haptics.pack(anchor="w", pady=2)

        # Actualización en vivo de la lista de teléfonos mientras el diálogo esté abierto
        timer_active = [True]

        def refresh_airpad_tree():
            if not timer_active[0]:
                return
            try:
                selected_item = tree_devices.selection()
                sel_slot = selected_item[0] if selected_item else None

                tree_devices.delete(*tree_devices.get_children())

                assigned_map = {}
                for p_id, p_cfg in self.config.get("controllers", {}).items():
                    p_dev = p_cfg.get("physical_device_id", "")
                    if p_dev.startswith("phone_"):
                        assigned_map[p_dev] = f"Mando {p_id}"

                cur_limit = val_var.get()
                devices_box.config(text=f"📱 {self.t('airpad_devices_title')} ({cur_limit})")

                for c in srv.get_clients_info(limit_count=cur_limit):
                    s_id = c["slot_id"]
                    s_num = c["slot_num"]
                    if c["connected"]:
                        dev_text = f"🟢 {c['name']} [{c['model']}]"
                        if c["ip"]:
                            dev_text += f" ({c['ip']})"
                        assigned_text = assigned_map.get(s_id, self.t("airpad_not_assigned"))
                    else:
                        dev_text = self.t("airpad_slot_status_free")
                        assigned_text = "--"

                    tree_devices.insert("", tk.END, iid=s_id, values=(f"{s_num}", dev_text, assigned_text))

                if sel_slot and tree_devices.exists(sel_slot):
                    tree_devices.selection_set(sel_slot)
            except Exception:
                pass

            if timer_active[0]:
                dlg.after(1000, refresh_airpad_tree)

        refresh_airpad_tree()

        def on_dlg_close():
            timer_active[0] = False
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", on_dlg_close)

        def apply_settings():
            # 1. Aplicar idioma
            inv_lang = {v: k for k, v in SUPPORTED_LANGUAGES.items()}
            new_lang = inv_lang.get(lang_var.get(), "es")
            self.config["language"] = new_lang
            self.config["author"] = "JuanJSAR"

            # 2. Aplicar driver backend
            old_driver = self.config.get("driver_backend", "vigem")
            new_driver = driver_var.get()
            driver_changed = (new_driver != old_driver)
            self.config["driver_backend"] = new_driver
            self.device_manager.set_driver_backend(new_driver)

            # 3. Aplicar tipo de mando emulado
            old_type = self.config.get("emulated_type", "xbox360").lower()
            new_type = type_var.get().lower()
            if new_driver == "vigem" and new_type in ("xboxone", "xbox_one", "dualsense", "ns2pro"):
                new_type = "xbox360"
            type_changed = (new_type != old_type)
            self.config["emulated_type"] = new_type

            # 4. Aplicar mandos
            old_count = self.config.get("max_controllers", 8)
            new_count = val_var.get()
            if new_type in ("mixed", "mixto") and new_count % 2 != 0:
                new_count = max(2, min(12, new_count + 1))
            count_changed = (new_count != old_count)
            self.config["max_controllers"] = new_count

            # 5. Aplicar configuración de HidHide
            cli_path = path_var.get().strip()
            self.config["hidhide_cli_path"] = cli_path
            self.config["suppress_hidhide_warning"] = not show_warn_var.get()
            self.driver_manager.update_config(self.config)

            if self.driver_manager.is_hidhide_installed():
                self.driver_manager.set_cloak_active(cloak_active_var.get())
                self.driver_manager.ensure_process_whitelisted()

            # 6. Guardar opciones de auto-asignación y AirPad
            self.config["auto_assign_usb"] = auto_assign_usb_var.get()
            self.config["airpad_server_enabled"] = airpad_srv_enabled_var.get()
            chosen_ip = ip_var.get()
            self.config["airpad_bind_ip"] = chosen_ip
            srv.preferred_ip = chosen_ip
            try:
                p_val = int(port_var.get().strip())
            except Exception:
                p_val = 8080
            self.config["airpad_server_port"] = p_val
            self.config["airpad_auto_assign"] = airpad_auto_assign_var.get()
            self.config["airpad_haptics_enabled"] = airpad_haptics_var.get()

            srv.haptics_enabled = airpad_haptics_var.get()
            srv.port = p_val
            srv.max_slots = new_count
            if airpad_srv_enabled_var.get():
                if not srv.running:
                    srv.start()
            else:
                if srv.running:
                    srv.stop()

            if driver_changed or type_changed or count_changed:
                self._update_active_assets()
                if self.engine.is_running():
                    self.engine.stop()
                    self.engine.set_config(self.config)
                    self.engine.start()

            self._sync_ui_to_config()
            self._rebuild_tabs(new_count)
            self.save_config(silent=True)
            self._update_ui_texts()

            timer_active[0] = False
            dlg.destroy()
            messagebox.showinfo(self.t("set_dlg_title"), self.t("set_saved"))

        btn_box = ttk.Frame(main_box)
        btn_box.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 0))

        ttk.Button(btn_box, text="✔ " + self.t("set_btn_save"), command=apply_settings).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_box, text=self.t("set_btn_cancel"), command=on_dlg_close).pack(side=tk.RIGHT, padx=4)

    def _open_devices_dialog(self):
        """Ventana modal estilo x360ce para listar y administrar DirectInput Devices."""
        has_hidhide = self.driver_manager.is_hidhide_installed()

        dlg = tk.Toplevel(self.root)
        dlg.title(self.t("dev_dlg_title"))
        dlg.geometry("860x440")
        dlg.resizable(True, True)
        self._setup_modal_dialog(dlg)

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
                is_marked = self._is_device_path_hidden(inst_path)
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
                    assigned_map[p_dev].append(f"{self.t('virtual_controller_prefix')} {pad_id}")

            for dev in self.available_devices:
                if dev["id"] == "none":
                    continue

                xinput_str = ", ".join(assigned_map.get(dev["id"], []))
                c_type = dev.get("conn_type", "SYS")
                conn_lbl = self.t("conn_usb") if c_type == "USB" else (self.t("conn_bt") if c_type in ("BT", "BTH") else (self.t("conn_int") if c_type == "INT" else self.t("conn_sys")))
                conn_icon = f"🔌 {conn_lbl}" if c_type == "USB" else (f"📶 {conn_lbl}" if c_type in ("BT", "BTH") else (f"💻 {conn_lbl}" if c_type == "INT" else f"⌨️ {conn_lbl}"))
                status_str = self.t("dev_status_connected")

                inst_path = dev.get("instance_path")
                is_marked = self._is_device_path_hidden(inst_path)

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

                dev_pname = self.t("keyboard_device_global") if dev["id"] == "keyboard" else (self.t("mouse_device_name") if dev["id"] == "mouse" else dev.get("product_name", dev.get("name", self.t("dev_device_fallback"))))

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
                        dev_pname
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
            is_marked = self._is_device_path_hidden(inst_path)

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
                messagebox.showinfo(self.t("hidhide_title"), self.t("dev_select_device"))
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
                messagebox.showwarning(self.t("hidhide_title"), self.t("dev_no_pnp_path"))
                return

            self._mark_device_hidden(inst_path)

            if self.engine.is_running():
                self.driver_manager.hide_device(inst_path)
                messagebox.showinfo(
                    self.t("hidhide_title"),
                    self.t("dev_hide_active_msg", name=dev.get('product_name'))
                )
            else:
                messagebox.showinfo(
                    self.t("hidhide_title"),
                    self.t("dev_hide_marked_msg", name=dev.get('product_name'))
                )
            populate_tree()

        def unhide_selected_device():
            if not has_hidhide:
                return

            selected = tree.selection()
            if not selected:
                messagebox.showinfo(self.t("hidhide_title"), self.t("dev_select_device"))
                return
            item = tree.item(selected[0])
            tags = item.get("tags", [])
            dev_id = tags[0] if tags else ""
            dev = next((d for d in self.available_devices if d["id"] == dev_id), None)
            if not dev:
                return

            inst_path = dev.get("instance_path")
            if not inst_path:
                messagebox.showwarning(self.t("hidhide_title"), self.t("dev_no_pnp_path"))
                return

            self._unmark_device_hidden(inst_path)
            self.driver_manager.unhide_device(inst_path)

            # Si ya no quedan dispositivos marcados o no se está emulando, desactivar cloaking
            if not self.config.get("hidden_devices", []) or not self.engine.is_running():
                self.driver_manager.set_cloak_active(False)

            messagebox.showinfo(
                self.t("hidhide_title"),
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
                messagebox.showwarning(self.t("dev_dlg_title"), self.t("dev_select_control_tab"))

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
        self._setup_modal_dialog(dlg)

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
                        val = src_maps.get(target, "-- Ninguno --")
                        cb.set(self.localize_mapping(val))
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
        is_keyboard = dev_id.startswith("kbd_") or dev_id == "keyboard"
        if is_keyboard:
            steps_queue = [
                # Cruceta / D-Pad
                "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT",
                # Botones Principales
                "A", "B", "X", "Y",
                # Botones Centrales / Menú
                "START", "BACK", "GUIDE",
                # Bumpers y Gatillos
                "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_TRIGGER", "RIGHT_TRIGGER",
                # Stick Izquierdo (Discreto para teclado)
                "LEFT_THUMB", "LEFT_STICK_UP", "LEFT_STICK_DOWN", "LEFT_STICK_LEFT", "LEFT_STICK_RIGHT",
                # Stick Derecho (Discreto para teclado)
                "RIGHT_THUMB", "RIGHT_STICK_UP", "RIGHT_STICK_DOWN", "RIGHT_STICK_LEFT", "RIGHT_STICK_RIGHT"
            ]
        else:
            steps_queue = list(BASE_SEQUENCE)
        current_step_idx = 0

        dlg = tk.Toplevel(self.root)
        dlg.title(self.t("wizard_title", id=pad_id))
        dlg.geometry("670x505")
        dlg.resizable(False, False)

        dlg.update_idletasks()
        pw = self.root.winfo_width()
        ph = self.root.winfo_height()
        px = self.root.winfo_rootx()
        py = self.root.winfo_rooty()
        dw, dh = 670, 505
        pos_x = max(0, px + (pw - dw) // 2)
        pos_y = max(0, py + (ph - dh) // 2)
        dlg.geometry(f"{dw}x{dh}+{pos_x}+{pos_y}")

        self._setup_modal_dialog(dlg)
        dlg.lift()
        dlg.focus_force()

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

        pad_type = self.get_pad_emulated_type(pad_id)
        is_ps = pad_type in ("ds4", "dualsense")
        if pad_type == "dualsense":
            pad_badge = "DualSense (PS5)"
        elif pad_type == "ds4":
            pad_badge = "DualShock 4"
        elif pad_type == "ns2pro":
            pad_badge = "Switch 2 Pro"
        elif pad_type in ("xboxone", "xbox_one"):
            pad_badge = "Xbox One"
        else:
            pad_badge = "Xbox 360"
        left_box = ttk.LabelFrame(center_frame, text=f" {self.t('subtab_general')} - {pad_badge} ", padding=2)
        left_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        cv_main = tk.Canvas(left_box, width=350, height=275, bg="#ffffff", highlightthickness=1, highlightbackground="#d0d0d0")
        cv_main.pack(anchor="center", pady=2)

        pad_img = self._get_pad_img_tk(pad_id)
        if pad_img:
            cv_main.create_image(175, 137, image=pad_img)

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

            lbl_target_name.config(text=f"👉 {self.target_name(tgt, pad_id)}")
            lbl_target_hint.config(text=get_hint_text(tgt))
            lbl_status.config(text=self.t("wizard_waiting"), foreground="#666666")

            canvas_key = map_target_to_canvas_key(tgt)
            pt = self._get_canvas_points(pad_id).get(canvas_key, (175.0, 137.5, 10))
            cx, cy = pt[0], pt[1]

            cv_main.coords(main_halo, cx - 14, cy - 14, cx + 14, cy + 14)
            cv_main.coords(main_core, cx - 6, cy - 6, cx + 6, cy + 6)
            cv_main.itemconfig(main_halo, outline="#ff2200", state="normal")
            cv_main.itemconfig(main_core, fill="#ffaa00", state="normal")

            cv_zoom.delete("all")
            source_img = self._get_pad_hires_img(pad_id)
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

            if not is_keyboard:
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
            can_val = self.canonicalize_mapping(detected_val)
            staged_mappings[tgt] = can_val

            loc_val = self.localize_mapping(can_val)
            lbl_status.config(text=self.t("wizard_detected", input=loc_val), foreground="#009922")
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
            self.device_manager.cancel_capture()

            nonlocal current_step_idx
            if current_step_idx > 0:
                # Si el paso actual tenía mapeo recién capturado o saltado, se limpia
                cur_tgt = worker_state["current_target"]
                staged_mappings.pop(cur_tgt, None)
                skipped_targets.discard(cur_tgt)

                current_step_idx -= 1
                prev_tgt = steps_queue[current_step_idx]

                # Si retrocedemos a un paso de stick analógico tras haber insertado discretos
                if not is_keyboard:
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
            self.device_manager.cancel_capture()
            tgt = worker_state["current_target"]
            skipped_targets.add(tgt)
            advance()

        def on_finish():
            cancel_advance_timer()
            worker_state["active"] = False
            worker_state["listening"] = False
            self.device_manager.cancel_capture()

            if is_keyboard:
                for axis_key in ("LEFT_STICK_X", "LEFT_STICK_Y", "RIGHT_STICK_X", "RIGHT_STICK_Y"):
                    if axis_key not in staged_mappings:
                        staged_mappings[axis_key] = "-- Ninguno --"

            widgets = self.tab_widgets.get(pad_id)
            if widgets and "combos" in widgets:
                combos = widgets["combos"]
                for t, v in staged_mappings.items():
                    if t in combos:
                        combos[t].set(self.localize_mapping(v))

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
        dlg.bind("<Escape>", lambda e: on_cancel())

        if is_keyboard and not getattr(self.device_manager, "keyboard_manager", None):
            def on_key_event(event):
                if not worker_state["active"] or not worker_state["listening"]:
                    return
                if event.keysym.lower() in ("escape", "esc") or event.keycode == 27:
                    on_cancel()
                    return
                k_name = event.keysym.lower()
                on_detected(f"Tecla: {k_name}")

            dlg.bind("<KeyPress>", on_key_event)

        def capture_thread_func():
            time.sleep(0.1)
            while worker_state["active"]:
                if worker_state["listening"]:
                    cur_tgt = worker_state.get("current_target", "")
                    timeout_val = 0.08 if dev_id.startswith("joy_") else 0.15
                    det = self.device_manager.capture_input(dev_id, timeout=timeout_val, target_name=cur_tgt)
                    if det and worker_state["active"] and worker_state["listening"]:
                        if is_keyboard and det in ("Key: Escape", "Tecla: escape", "Tecla: esc"):
                            try:
                                dlg.after(0, on_cancel)
                            except Exception:
                                pass
                            break
                        try:
                            dlg.after(0, lambda d=det: on_detected(d))
                        except Exception:
                            pass
                        time.sleep(0.25)
                time.sleep(0.01)

        threading.Thread(target=capture_thread_func, daemon=True).start()

        update_ui_for_target(steps_queue[0])
        dlg.after(50, lambda: dlg.focus_force())


    def _open_joy_cpl(self):
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.Popen(["joy.cpl"], shell=True, creationflags=flags)
        except Exception as e:
            messagebox.showerror(self.t("msg_error"), self.t("joy_cpl_error", e=e))

    def _open_hidhide_client(self):
        try:
            client_path = self.driver_manager.get_hidhide_client_path()
            if client_path and os.path.isfile(client_path):
                try:
                    os.startfile(client_path)
                except Exception:
                    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    subprocess.Popen([client_path], shell=True, creationflags=flags)
            else:
                messagebox.showwarning(
                    self.t("hidhide_client_not_found_title"),
                    self.t("hidhide_client_not_found_msg")
                )
        except Exception as e:
            messagebox.showerror(self.t("msg_error"), self.t("hidhide_client_error", e=e))

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
            self._update_airpad_status_ui()
            # Sincronización de modales ante eventos globales como Win+D
            if getattr(self, "_active_dialog", None):
                dlg = self._active_dialog
                if dlg.winfo_exists():
                    r_state = self.root.wm_state()
                    if r_state == "iconic":
                        try:
                            if dlg.grab_status() is not None:
                                dlg.grab_release()
                                self._modal_needs_regrab = True
                        except Exception:
                            pass
                    elif r_state == "normal" and getattr(self, "_modal_needs_regrab", False):
                        try:
                            self._modal_needs_regrab = False
                            dlg.deiconify()
                            dlg.lift()
                            dlg.focus_force()
                            dlg.grab_set()
                        except Exception:
                            pass
                else:
                    self._active_dialog = None
                    self._modal_needs_regrab = False

            selected = self.notebook.select()
            if not selected:
                self.root.after(30, self._update_loop)
                return
            try:
                cur_pad_id = self.notebook.index(selected) + 1
            except Exception:
                self.root.after(30, self._update_loop)
                return

            widgets = self.tab_widgets.get(cur_pad_id)

            if widgets:
                # Si la emulacion no esta activa, computamos el estado en tiempo real
                # para que los controles respondan y se iluminen inmediatamente al probar
                if self.engine.is_running():
                    state = self.engine.get_active_state(cur_pad_id)
                else:
                    state = self.engine.compute_controller_state(cur_pad_id)

                canvas = widgets.get("canvas")
                if not canvas or not canvas.winfo_exists():
                    self.root.after(30, self._update_loop)
                    return
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
                    active_pts = self._get_canvas_points(cur_pad_id)
                    if rec_canvas_key and rec_canvas_key in active_pts:
                        widgets["_rec_shown"] = True
                        cx, cy, r = active_pts[rec_canvas_key]
                        t = time.time()
                        pulse = (math.sin(t * 10) + 1.0) / 2.0  # 0..1 oscila a ~1.6 Hz
                        halo_r = r + 3 + int(pulse * 5)
                        halo_col = "#ff3300" if pulse > 0.45 else "#ff9900"
                        canvas.coords(rec_ind["halo"], cx - halo_r, cy - halo_r, cx + halo_r, cy + halo_r)
                        canvas.itemconfig(rec_ind["halo"], state="normal", outline=halo_col, width=3)

                        canvas.coords(rec_ind["core"], cx - r, cy - r, cx + r, cy + r)
                        canvas.itemconfig(rec_ind["core"], state="normal", fill="#ffaa00", outline="#ffffff", width=2)
                    elif widgets.get("_rec_shown", True):
                        widgets["_rec_shown"] = False
                        canvas.itemconfig(rec_ind["halo"], state="hidden")
                        canvas.itemconfig(rec_ind["core"], state="hidden")

                # 2. Indicadores reactivos de botones OPRIMIDOS (verde neon brillante con halo)
                if canvas and leds:
                    pressed_btns = state.get("buttons", set())
                    last_led_states = widgets.setdefault("_led_states", {})
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

                        if last_led_states.get(btn_name) != is_active:
                            last_led_states[btn_name] = is_active
                            new_state = "normal" if is_active else "hidden"
                            canvas.itemconfig(tag, state=new_state)
                            canvas.itemconfig(glow, state=new_state)
                            if is_active:
                                canvas.tag_raise(glow)
                                canvas.tag_raise(tag)

                # 3. Triggers
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

                        trig_sig = (dz, adz, sens, inv, round(raw_val, 3), out_byte)
                        if tw.get("_last_sig") != trig_sig:
                            tw["_last_sig"] = trig_sig
                            self._draw_trigger_graph(tw["canvas"], dz, adz, sens, inv, raw_val, out_byte)
                            tw["lbl_di_xi"].config(text=f"DI: {int(raw_val * 32767):5d}    XI: {out_byte:3d}")

                # 4. Sticks
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

                        stick_canvas_sig = (dz, adz, round(cal_x, 3), round(disp_y, 3))
                        if sw.get("_last_canvas_sig") != stick_canvas_sig:
                            sw["_last_canvas_sig"] = stick_canvas_sig
                            self._draw_stick_canvas(sw["canvas"], dz, adz, cal_x, disp_y)
                            sw["lbl_xy"].config(text=f"X: {cal_x:+0.2f}  Y: {disp_y:+0.2f}")

                        raw_mag = min(1.0, math.sqrt(raw_x**2 + raw_y**2))
                        out_mag = min(1.0, math.sqrt(cal_x**2 + cal_y**2))
                        curve_sig = (dz, adz, sens, round(raw_mag, 3), round(out_mag, 3))
                        if sw.get("_last_curve_sig") != curve_sig:
                            sw["_last_curve_sig"] = curve_sig
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
            title = g.get("title", self.t("default_game_title", idx=idx + 1))
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
            env_summary = ", ".join(active_vars) if active_vars else self.t("env_none")
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
        self._setup_modal_dialog(dlg)

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
                    (self.t("ft_exec_and_scripts"), "*.exe;*.cmd;*.bat"),
                    (self.t("ft_executables"), "*.exe"),
                    (self.t("ft_scripts"), "*.cmd;*.bat"),
                    (self.t("ft_all_files"), "*.*")
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
            ("FNA_GAMEPAD_NUM_GAMEPADS", True, default_max, self.t("env_desc_fna", count=default_max)),
            ("SDL_JOYSTICK_DIRECTINPUT", True, "1", self.t("env_directinput_desc")),
            ("SDL_JOYSTICK_RAWINPUT", True, "1", self.t("env_rawinput_desc")),
            ("SDL_JOYSTICK_RAWINPUT_CORRELATE_XINPUT", True, "0", self.t("env_correlate_xinput_desc")),
            ("SDL_XINPUT_ENABLED", True, "0", self.t("env_xinput_enabled_desc")),
            ("SDL_JOYSTICK_GAMEINPUT", True, "1", self.t("env_gameinput_desc")),
            ("SDL_JOYSTICK_THREAD", True, "1", self.t("env_thread_desc"))
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
                lbl_auto = ttk.Label(row, text=self.t("env_fna_in_settings", count=default_max), font=("Segoe UI", 7, "italic"), foreground="#008800")
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
            t_str = title_var.get().strip() or self.t("default_untitled_game")
            p_str = path_var.get().strip()
            if not p_str:
                messagebox.showwarning(self.t("tab_games"), self.t("msg_specify_executable_path"))
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
                messagebox.showwarning(self.t("tab_games"), self.t("msg_specify_executable_path"))
                return

            default_bat_name = f"Launch_{os.path.splitext(os.path.basename(p_str))[0]}_MultiPad.bat"
            desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            chosen_bat = filedialog.asksaveasfilename(
                title=self.t("btn_create_bat"),
                initialdir=desktop_dir if os.path.exists(desktop_dir) else os.path.dirname(p_str),
                initialfile=default_bat_name,
                defaultextension=".bat",
                filetypes=[(self.t("ft_batch_file"), "*.bat"), (self.t("ft_all_files"), "*.*")]
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
                messagebox.showerror(self.t("msg_error"), self.t("msg_bat_save_error", e=e))

        btn_save = ttk.Button(btn_bar, text=self.t("btn_save"), command=save_and_close)
        btn_save.pack(side=tk.LEFT, padx=(0, 6))

        btn_bat = ttk.Button(btn_bar, text=self.t("btn_create_bat"), command=create_bat_shortcut)
        btn_bat.pack(side=tk.LEFT, padx=6)

        btn_cancel = ttk.Button(btn_bar, text=self.t("set_btn_cancel"), command=dlg.destroy)
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
            messagebox.showerror(self.t("msg_error"), self.t("game_not_found", path=exe_path))
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
            messagebox.showerror(self.t("msg_error"), self.t("game_launch_error", e=e))

    def _on_close(self):
        try:
            if hasattr(self, "airpad_server") and self.airpad_server:
                self.airpad_server.stop()
        except Exception as e:
            print(f"[!] Error deteniendo AirPad server al cerrar: {e}")

        try:
            if hasattr(self, "engine") and self.engine and self.engine.is_running():
                self.engine.stop()
            self._unhide_emulation_devices()
        except Exception as e:
            print(f"[!] Error deteniendo motor de emulación al cerrar: {e}")

        try:
            if hasattr(self, "device_manager") and hasattr(self.device_manager, "stop"):
                self.device_manager.stop()
        except Exception as e:
            print(f"[!] Error deteniendo gestor de dispositivos al cerrar: {e}")

        try:
            self.root.destroy()
        except Exception:
            pass

def run_gui():
    root = tk.Tk()
    root.withdraw()

    # Cargar idioma de configuración para el texto del splash
    lang = "es"
    try:
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_mapping.json")
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                lang = json.load(f).get("language", "es")
    except Exception:
        pass

    splash_title = get_text(lang, "splash_loading_title")
    splash_desc = get_text(lang, "splash_loading_desc")
    splash = SplashScreen(root, title=splash_title, desc=splash_desc)

    app = J360MoreApp(root, splash=splash)
    root.mainloop()

if __name__ == "__main__":
    run_gui()
