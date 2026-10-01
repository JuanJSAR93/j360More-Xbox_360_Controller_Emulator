"""
plugins/plugin_manager.py
Orchestrator and lifecycle supervisor for j360More plugins.
Handles drop-in discovery, isolated subprocess spawning, IPC routing,
and dynamic device registration for the emulator engine.
"""

import json
import logging
import os
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from plugins.plugin_ipc import IPCServer
from plugins.venv_manager import VenvManager
from plugins.plugin_i18n import (
    localize_text,
    localize_list,
    localize_ui_definition,
    load_plugin_locales,
    normalize_lang_code
)

logger = logging.getLogger("j360More.PluginManager")


class PluginInstance:
    """Represents a discovered plugin, its metadata, configuration, and runtime process."""

    def __init__(self, plugin_dir: str, manifest: Dict[str, Any]):
        self.plugin_dir = plugin_dir
        self.manifest = manifest
        self.id = manifest.get("id", os.path.basename(plugin_dir))
        self.version = manifest.get("version", "1.0.0")
        self.author = manifest.get("author", "Comunidad")
        self.entrypoint = manifest.get("entrypoint", "main.py")
        self.requirements = manifest.get("requirements", [])
        self.global_ui = manifest.get("global_ui", {})
        self.pad_ui = manifest.get("pad_ui_customization", {})

        # Multi-language / Internationalization
        self.locales = load_plugin_locales(self.plugin_dir)
        extra_i18n = manifest.get("i18n") or manifest.get("locales")
        if isinstance(extra_i18n, dict):
            for lk, lv in extra_i18n.items():
                nlk = normalize_lang_code(lk)
                if nlk not in self.locales:
                    self.locales[nlk] = {}
                if isinstance(lv, dict):
                    self.locales[nlk].update({str(k): str(v) for k, v in lv.items()})

        # Runtime state
        self.status = "stopped"  # stopped, running, error, missing_dependencies
        self.process: Optional[subprocess.Popen] = None
        self.ipc_server: Optional[IPCServer] = None
        self.ipc_port: int = 0
        self.log_lines: List[str] = []
        self.max_log_lines: int = 500
        self.discovered_devices: List[Dict[str, Any]] = []
        self.is_simulated: bool = False

        # Latest controller state per device_id
        # Key: device_id -> { "buttons": dict, "named_buttons": dict, "axes": dict, "triggers": dict, "sticks": dict }
        self.device_states: Dict[str, Dict[str, Any]] = {}

        # Config per pad
        self.config_data: Dict[str, Any] = self._load_saved_config()

    @property
    def name(self) -> str:
        return self.get_name("es")

    @property
    def description(self) -> str:
        return self.get_description("es")

    def get_name(self, lang: str = "es") -> str:
        return localize_text(self.manifest.get("name", self.id), lang=lang, default_lang="es", locales=self.locales)

    def get_description(self, lang: str = "es") -> str:
        return localize_text(self.manifest.get("description", ""), lang=lang, default_lang="es", locales=self.locales)

    def get_global_ui(self, lang: str = "es") -> Dict[str, Any]:
        return localize_ui_definition(self.global_ui, lang=lang, default_lang="es", locales=self.locales)

    def get_pad_ui(self, lang: str = "es") -> Dict[str, Any]:
        return localize_ui_definition(self.pad_ui, lang=lang, default_lang="es", locales=self.locales)

    def get_text(self, key: str, lang: str = "es", default: Optional[str] = None) -> str:
        res = localize_text(key, lang=lang, default_lang="es", locales=self.locales)
        return res if res else (default if default is not None else key)

    def _load_saved_config(self) -> Dict[str, Any]:
        cfg_file = os.path.join(self.plugin_dir, "config.json")
        if os.path.isfile(cfg_file):
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"global": {}, "pads": {}}

    def save_config(self):
        cfg_file = os.path.join(self.plugin_dir, "config.json")
        try:
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config for plugin {self.id}: {e}")

    def append_log(self, line: str):
        self.log_lines.append(line)
        if len(self.log_lines) > self.max_log_lines:
            self.log_lines.pop(0)


class PluginManager:
    """
    Central hub managing all plugins, communication with DeviceManager/EmulatorEngine,
    and event routing to the GUI.
    """

    def __init__(self, base_dir: Optional[str] = None):
        if not base_dir:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.base_dir = base_dir
        self.plugins_dir = os.path.join(self.base_dir, "plugins")
        self.venv_manager = VenvManager(base_dir=self.base_dir)

        self.plugins: Dict[str, PluginInstance] = {}
        self._lock = threading.Lock()
        self.current_lang: str = "es"

        # Callbacks for GUI telemetry & device changes
        self._on_device_list_changed: List[Callable[[], None]] = []
        self._on_telemetry_callbacks: List[Callable[[str, int, Dict[str, Any]], None]] = []
        self._on_log_callbacks: List[Callable[[str, str], None]] = []
        self._on_options_updated: List[Callable[[str, str, List[Any]], None]] = []

    def is_plugins_folder_present(self) -> bool:
        """Returns True if the plugins directory exists on disk."""
        return os.path.isdir(self.plugins_dir)

    def has_runtime(self) -> bool:
        """Returns True if a Python runtime or virtual environment is available."""
        return bool(self.venv_manager.get_venv_python())

    def is_enabled(self) -> bool:
        """Returns True if plugins folder exists and runtime is ready."""
        return self.is_plugins_folder_present()

    def initialize_plugin_system(self, progress_callback: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
        """
        Creates the plugins/ directory, initializes the Python runtime and virtual environment,
        and scans discovered plugins.
        """
        try:
            if not os.path.isdir(self.plugins_dir):
                os.makedirs(self.plugins_dir, exist_ok=True)
                if progress_callback:
                    progress_callback("Carpeta 'plugins/' creada exitosamente.")

            ok, py_exe_or_err = self.venv_manager.ensure_runtime(progress_callback=progress_callback)
            if not ok:
                return False, f"Fallo al inicializar el entorno de Python: {py_exe_or_err}"

            self.scan_plugins()
            self.start_all_auto()
            self._notify_device_list_changed()
            return True, "Soporte de plugins y entorno virtual inicializados con éxito."
        except Exception as e:
            return False, f"Error durante la inicialización: {e}"

    def scan_plugins(self) -> List[PluginInstance]:
        """Scans the plugins/ directory for drop-in plugins."""
        with self._lock:
            discovered = []
            if not self.is_plugins_folder_present():
                self.plugins.clear()
                return discovered

            for entry in os.scandir(self.plugins_dir):
                if entry.is_dir() and not entry.name.startswith(".") and entry.name not in ("tests", "__pycache__"):
                    plugin_dir = entry.path
                    manifest_file = os.path.join(plugin_dir, "plugin.json")
                    entrypoint_file = os.path.join(plugin_dir, "main.py")

                    manifest = {}
                    if os.path.isfile(manifest_file):
                        try:
                            with open(manifest_file, "r", encoding="utf-8") as f:
                                manifest = json.load(f)
                        except Exception as e:
                            logger.error(f"Failed to parse manifest {manifest_file}: {e}")
                            continue
                    elif os.path.isfile(entrypoint_file):
                        # Minimal fallback manifest
                        manifest = {
                            "id": entry.name,
                            "name": entry.name.replace("_", " ").title(),
                            "entrypoint": "main.py"
                        }
                    else:
                        continue

                    plugin_id = manifest.get("id", entry.name)
                    if plugin_id in self.plugins:
                        instance = self.plugins[plugin_id]
                        instance.manifest = manifest
                    else:
                        instance = PluginInstance(plugin_dir, manifest)
                        self.plugins[plugin_id] = instance

                    # Check dependencies
                    req_file = os.path.join(plugin_dir, "requirements.txt")
                    if os.path.isfile(req_file) and not instance.requirements:
                        try:
                            with open(req_file, "r", encoding="utf-8") as rf:
                                instance.requirements = [l.strip() for l in rf if l.strip() and not l.startswith("#")]
                        except Exception:
                            pass

                    discovered.append(instance)

            return discovered

    def start_plugin(self, plugin_id: str, simulate: bool = False) -> Tuple[bool, str]:
        """Launches the plugin's worker script inside an isolated process with IPC."""
        instance = self.plugins.get(plugin_id)
        if not instance:
            return False, f"Plugin '{plugin_id}' no encontrado."

        if instance.status == "running":
            return True, "El plugin ya está en ejecución."

        # Verify runtime
        venv_py = self.venv_manager.get_venv_python()
        if not venv_py:
            ok, venv_py = self.venv_manager.ensure_runtime()
            if not ok:
                instance.status = "error"
                return False, f"Fallo al inicializar Python: {venv_py}"

        # Setup IPC Server
        server = IPCServer(host="127.0.0.1", port=0)
        port = server.start()
        instance.ipc_server = server
        instance.ipc_port = port
        instance.is_simulated = simulate

        def handle_msg(msg: Dict[str, Any]):
            self._handle_plugin_message(instance, msg)

        server.add_on_message(handle_msg)
        server.add_on_disconnect(lambda: self._on_plugin_disconnect(instance))

        # Launch process
        entrypoint_path = os.path.join(instance.plugin_dir, instance.entrypoint)
        if not os.path.isfile(entrypoint_path):
            server.close()
            instance.status = "error"
            return False, f"No se encontró el script de entrada: {instance.entrypoint}"

        cmd = [
            venv_py,
            entrypoint_path,
            "--ipc-port", str(port),
            "--ipc-host", "127.0.0.1",
        ]
        if simulate:
            cmd.append("--simulate")

        # Set PYTHONPATH so plugins can import plugins.plugin_sdk easily
        env = os.environ.copy()
        env["PYTHONPATH"] = self.base_dir + os.pathsep + env.get("PYTHONPATH", "")

        try:
            instance.process = subprocess.Popen(
                cmd,
                cwd=instance.plugin_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env
            )
            instance.status = "running"

            # Thread to capture stdout/stderr
            threading.Thread(target=self._log_reader, args=(instance, instance.process.stdout, "STDOUT"), daemon=True).start()
            threading.Thread(target=self._log_reader, args=(instance, instance.process.stderr, "STDERR"), daemon=True).start()

            # Wait briefly for process or immediate crash
            time.sleep(0.15)
            if instance.process.poll() is not None:
                instance.status = "error"
                server.close()
                return False, f"El script finalizó inesperadamente con código {instance.process.returncode}."

            # Trigger discovery
            server.send({"event": "request_discovery"})

            # Send initial saved configuration
            server.send({
                "event": "initial_config",
                "config": instance.config_data
            })

            return True, "Plugin iniciado correctamente."
        except Exception as e:
            instance.status = "error"
            server.close()
            return False, str(e)

    def stop_plugin(self, plugin_id: str):
        """Stops a running plugin process and closes its IPC channel."""
        instance = self.plugins.get(plugin_id)
        if not instance:
            return

        instance.status = "stopped"
        if instance.ipc_server:
            instance.ipc_server.close()
            instance.ipc_server = None

        if instance.process:
            try:
                instance.process.terminate()
                instance.process.wait(timeout=1.0)
            except Exception:
                try:
                    instance.process.kill()
                except Exception:
                    pass
            instance.process = None

        instance.device_states.clear()
        self._notify_device_list_changed()

    def _log_reader(self, instance: PluginInstance, pipe, prefix: str):
        try:
            for line in pipe:
                clean = line.rstrip()
                if clean:
                    log_entry = f"[{prefix}] {clean}"
                    instance.append_log(log_entry)
                    for cb in self._on_log_callbacks:
                        try:
                            cb(instance.id, log_entry)
                        except Exception:
                            pass
        except Exception:
            pass

    def _on_plugin_disconnect(self, instance: PluginInstance):
        if instance.status == "running":
            instance.status = "stopped"
            self._notify_device_list_changed()

    def _handle_plugin_message(self, instance: PluginInstance, msg: Dict[str, Any]):
        event = msg.get("event")
        if event == "state_update":
            dev_id = msg.get("device_id", instance.id)
            instance.device_states[dev_id] = {
                "buttons": {int(k): v for k, v in msg.get("buttons", {}).items()},
                "named_buttons": msg.get("named_buttons", {}),
                "axes": {int(k): v for k, v in msg.get("axes", {}).items()},
                "triggers": msg.get("triggers", {}),
                "sticks": msg.get("sticks", {}),
            }

        elif event == "handshake":
            # Handshake received from plugin
            instance.append_log(f"[IPC] Conectado exitosamente: {msg.get('name')}")
            # Register initial device if not yet discovered
            dev_id = msg.get("device_id", instance.id)
            instance.discovered_devices = [{
                "id": dev_id,
                "name": msg.get("name", instance.name),
                "num_buttons": msg.get("num_buttons", 16),
                "num_axes": msg.get("num_axes", 6)
            }]
            self._notify_device_list_changed()

        elif event == "discovered_devices":
            devs = msg.get("devices", [])
            instance.discovered_devices = devs
            self._notify_device_list_changed()

        elif event == "telemetry":
            pad = int(msg.get("pad_id", 1))
            data = msg.get("data", {})
            for cb in self._on_telemetry_callbacks:
                try:
                    cb(instance.id, pad, data)
                except Exception:
                    pass

        elif event == "update_options":
            field_id = msg.get("field_id", "")
            opts = msg.get("options", [])
            for cb in self._on_options_updated:
                try:
                    cb(instance.id, field_id, opts)
                except Exception:
                    pass

        elif event == "log":
            lvl = msg.get("level", "INFO")
            text = msg.get("message", "")
            log_line = f"[{lvl}] {text}"
            instance.append_log(log_line)
            for cb in self._on_log_callbacks:
                try:
                    cb(instance.id, log_line)
                except Exception:
                    pass

    # ---------------------------------------------------------
    # Integration with DeviceManager & EmulatorEngine
    # ---------------------------------------------------------

    def get_available_devices(self, lang: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns all devices registered by running plugins.
        Prefixed with 'plugin:<plugin_id>:<device_id>'.
        """
        if not self.is_plugins_folder_present():
            return []

        use_lang = lang or self.current_lang or "es"
        result = []
        with self._lock:
            for p_id, inst in self.plugins.items():
                if inst.status == "running":
                    for dev in inst.discovered_devices:
                        d_id = dev.get("id", p_id)
                        full_id = f"plugin:{p_id}:{d_id}"
                        dev_raw_name = dev.get("name")
                        if dev_raw_name:
                            dev_name = localize_text(dev_raw_name, lang=use_lang, default_lang="es", locales=inst.locales)
                        else:
                            dev_name = inst.get_name(use_lang)
                        display_name = f"🔌 [Plugin] {dev_name}"
                        result.append({
                            "id": full_id,
                            "name": display_name,
                            "plugin_id": p_id,
                            "device_id": d_id,
                            "num_buttons": dev.get("num_buttons", 16),
                            "num_axes": dev.get("num_axes", 6),
                        })
        return result

    def read_physical_state(self, full_device_id: str) -> Optional[Dict[str, Any]]:
        """
        Reads the latest buttons, axes, triggers, and sticks from a plugin device.
        Called by DeviceManager / EmulatorEngine at 120Hz.
        """
        if not self.is_plugins_folder_present() or not full_device_id.startswith("plugin:"):
            return None

        parts = full_device_id.split(":", 2)
        if len(parts) < 3:
            return None

        plugin_id = parts[1]
        device_id = parts[2]

        inst = self.plugins.get(plugin_id)
        if not inst or inst.status != "running":
            return None

        state = inst.device_states.get(device_id)
        if not state:
            return None

        return state

    def send_rumble(self, full_device_id: str, pad_id: int, small_motor: float, large_motor: float):
        """Dispatches haptic rumble feedback to the corresponding plugin."""
        if not full_device_id or not full_device_id.startswith("plugin:"):
            return

        parts = full_device_id.split(":", 2)
        if len(parts) < 3:
            return

        plugin_id = parts[1]
        device_id = parts[2]

        inst = self.plugins.get(plugin_id)
        if inst and inst.ipc_server and inst.status == "running":
            inst.ipc_server.send({
                "event": "rumble",
                "device_id": device_id,
                "pad_id": pad_id,
                "small_motor": float(small_motor),
                "large_motor": float(large_motor)
            })

    def send_field_change(self, plugin_id: str, field_id: str, value: Any, pad_id: int = 1):
        """Sends a UI field change event to the plugin and updates saved config."""
        inst = self.plugins.get(plugin_id)
        if not inst:
            return

        # Save in config
        if pad_id > 0:
            pad_key = f"pad_{pad_id}"
            inst.config_data.setdefault("pads", {}).setdefault(pad_key, {})[field_id] = value
        else:
            inst.config_data.setdefault("global", {})[field_id] = value
        inst.save_config()

        if inst.ipc_server and inst.status == "running":
            inst.ipc_server.send({
                "event": "field_change",
                "field": field_id,
                "val": value,
                "pad": pad_id
            })

    def send_action(self, plugin_id: str, action: str, pad_id: int = 1):
        """Sends a UI button action click to the plugin."""
        inst = self.plugins.get(plugin_id)
        if inst and inst.ipc_server and inst.status == "running":
            inst.ipc_server.send({
                "event": "ui_action",
                "action": action,
                "pad": pad_id
            })

    # ---------------------------------------------------------
    # Listeners
    # ---------------------------------------------------------

    def add_on_device_list_changed(self, callback: Callable[[], None]):
        self._on_device_list_changed.append(callback)

    def add_on_telemetry(self, callback: Callable[[str, int, Dict[str, Any]], None]):
        self._on_telemetry_callbacks.append(callback)

    def add_on_log(self, callback: Callable[[str, str], None]):
        self._on_log_callbacks.append(callback)

    def add_on_options_updated(self, callback: Callable[[str, str, List[Any]], None]):
        self._on_options_updated.append(callback)

    def _notify_device_list_changed(self):
        for cb in self._on_device_list_changed:
            try:
                cb()
            except Exception:
                pass

    def shutdown(self):
        """Stops all running plugins cleanly."""
        for p_id in list(self.plugins.keys()):
            self.stop_plugin(p_id)

    def stop_all(self):
        """Alias for shutdown."""
        self.shutdown()

    def start_all_auto(self):
        """Starts all plugins that have autostart enabled or are active by default."""
        for p_id, inst in list(self.plugins.items()):
            autostart = inst.manifest.get("autostart", True)
            if autostart and inst.status != "running":
                self.start_plugin(p_id)

    def get_plugins_info(self, lang: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns structured metadata of all discovered plugins for UI rendering."""
        use_lang = lang or self.current_lang or "es"
        res = []
        for p_id, p in self.plugins.items():
            res.append({
                "id": p.id,
                "name": p.get_name(use_lang),
                "version": p.version,
                "author": p.author,
                "description": p.get_description(use_lang),
                "status": p.status,
                "is_simulated": p.is_simulated,
                "requirements": p.requirements,
                "devices_count": len(p.discovered_devices),
                "has_global_ui": bool(p.global_ui),
                "has_pad_ui": bool(p.pad_ui),
                "plugin_dir": p.plugin_dir
            })
        return res

    def install_plugin_requirements(self, plugin_id: str, callback: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
        """Installs dependencies declared in requirements.txt for the given plugin."""
        inst = self.plugins.get(plugin_id)
        if not inst:
            return False, f"Plugin '{plugin_id}' no encontrado."
        req_file = os.path.join(inst.plugin_dir, "requirements.txt")
        if not os.path.isfile(req_file):
            return True, "No se requiere instalar dependencias adicionales."
        return self.venv_manager.install_requirements(req_file, progress_callback=callback)


_global_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager(base_dir: Optional[str] = None) -> PluginManager:
    """Singleton getter for the global PluginManager."""
    global _global_plugin_manager
    if _global_plugin_manager is None:
        _global_plugin_manager = PluginManager(base_dir=base_dir)
    return _global_plugin_manager
