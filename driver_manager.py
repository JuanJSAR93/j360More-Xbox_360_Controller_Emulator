import os
import sys
import json
import subprocess
from typing import Optional, Set, List, Dict, Any

DEFAULT_HIDHIDE_CLI_PATH = r"C:\Program Files\Nefarius Software Solutions\HidHide\x64\HidHideCLI.exe"

class DriverManager:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._cached_cli_path: Optional[str] = None
        self._hidhide_available: Optional[bool] = None
        self._vigem_available: Optional[bool] = None

    def update_config(self, config: Dict[str, Any]):
        self.config = config
        self._cached_cli_path = None
        self._hidhide_available = None

    # ==========================================
    # DETECCION DE VIGEMBUS
    # ==========================================
    def is_vigem_installed(self) -> bool:
        """Verifica si el controlador ViGEmBus está instalado en el sistema."""
        if sys.platform != "win32":
            self._vigem_available = False
            return False
        if self._vigem_available is not None:
            return self._vigem_available

        try:
            import vgamepad as vg
            self._vigem_available = True
            return True
        except Exception:
            pass

        vigem_sys = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "drivers", "ViGEmBus.sys")
        if os.path.exists(vigem_sys):
            self._vigem_available = True
            return True

        self._vigem_available = False
        return False

    # ==========================================
    # DETECCION Y RUTA DE HIDHIDE
    # ==========================================
    def get_hidhide_cli_path(self) -> Optional[str]:
        """Obtiene la ruta hacia HidHideCLI.exe buscando en la configuración o rutas habituales."""
        if self._cached_cli_path and os.path.isfile(self._cached_cli_path):
            return self._cached_cli_path

        # 1. Ruta guardada en la configuración
        custom_path = self.config.get("hidhide_cli_path", "").strip()
        if custom_path and os.path.isfile(custom_path):
            self._cached_cli_path = custom_path
            return custom_path

        # 2. Ruta estándar de instalación (x64)
        if os.path.isfile(DEFAULT_HIDHIDE_CLI_PATH):
            self._cached_cli_path = DEFAULT_HIDHIDE_CLI_PATH
            return DEFAULT_HIDHIDE_CLI_PATH

        # 3. Buscar en Program Files alternativo o PATH
        prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        for sub in [
            os.path.join(prog_files, "Nefarius Software Solutions", "HidHide", "x64", "HidHideCLI.exe"),
            os.path.join(prog_files, "Nefarius Software Solutions", "HidHide", "HidHideCLI.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Nefarius Software Solutions", "HidHide", "x64", "HidHideCLI.exe")
        ]:
            if os.path.isfile(sub):
                self._cached_cli_path = sub
                return sub

        # 4. Buscar en PATH del sistema
        import shutil
        which_cli = shutil.which("HidHideCLI.exe") or shutil.which("HidHideCLI")
        if which_cli and os.path.isfile(which_cli):
            self._cached_cli_path = which_cli
            return which_cli

        return None

    def get_hidhide_client_path(self) -> Optional[str]:
        """Obtiene la ruta hacia HidHideClient.exe (interfaz gráfica oficial de configuración de HidHide)."""
        if getattr(self, "_cached_client_path", None) and os.path.isfile(self._cached_client_path):
            return self._cached_client_path

        # 1. Comprobar directorio junto al CLI si está detectado
        cli_path = self.get_hidhide_cli_path()
        if cli_path:
            dir_cli = os.path.dirname(cli_path)
            candidate_same = os.path.join(dir_cli, "HidHideClient.exe")
            if os.path.isfile(candidate_same):
                self._cached_client_path = candidate_same
                return candidate_same
            candidate_parent = os.path.join(os.path.dirname(dir_cli), "HidHideClient.exe")
            if os.path.isfile(candidate_parent):
                self._cached_client_path = candidate_parent
                return candidate_parent

        # 2. Rutas estándar en Program Files
        prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        candidates = [
            os.path.join(prog_files, "Nefarius Software Solutions", "HidHide", "x64", "HidHideClient.exe"),
            os.path.join(prog_files, "Nefarius Software Solutions", "HidHide", "HidHideClient.exe"),
            os.path.join(prog_files_x86, "Nefarius Software Solutions", "HidHide", "x64", "HidHideClient.exe"),
            os.path.join(prog_files_x86, "Nefarius Software Solutions", "HidHide", "HidHideClient.exe"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                self._cached_client_path = c
                return c

        # 3. Buscar en PATH
        import shutil
        which_client = shutil.which("HidHideClient.exe") or shutil.which("HidHideClient")
        if which_client and os.path.isfile(which_client):
            self._cached_client_path = which_client
            return which_client

        return None

    def is_hidhide_installed(self) -> bool:
        """Comprueba si HidHide está instalado en el sistema de forma instantánea y sin abrir consolas."""
        if sys.platform != "win32":
            self._hidhide_available = False
            return False
        if self._hidhide_available is not None:
            return self._hidhide_available

        cli = self.get_hidhide_cli_path()
        if cli and os.path.isfile(cli):
            self._hidhide_available = True
            return True

        # Comprobar si el driver está presente en System32/drivers
        hidhide_sys = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "drivers", "HidHide.sys")
        if os.path.exists(hidhide_sys):
            self._hidhide_available = True
            return True

        self._hidhide_available = False
        return False

    def _run_cli(self, args: List[str], timeout: float = 4.0) -> subprocess.CompletedProcess:
        """Ejecuta un comando con HidHideCLI de forma segura, rápida y sin abrir ventanas de consola."""
        cli = self.get_hidhide_cli_path()
        if not cli:
            return subprocess.CompletedProcess(args=[], returncode=-1, stdout="", stderr="HidHideCLI no encontrado")

        # Bandera para evitar abrir ventanas de consola emergentes en Windows
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW

        try:
            return subprocess.run(
                [cli] + args,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                creationflags=flags,
                timeout=timeout
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(args=[cli] + args, returncode=-1, stdout="", stderr="TimeoutExpired")
        except Exception as e:
            return subprocess.CompletedProcess(args=[cli] + args, returncode=-1, stdout="", stderr=str(e))

    # ==========================================
    # GESTION DE WHITELIST (LISTA BLANCA)
    # ==========================================
    def ensure_process_whitelisted(self, exe_path: Optional[str] = None) -> bool:
        """Asegura que el ejecutable actual (Python, pythonw o j360More) esté registrado en la lista blanca de HidHide."""
        if not self.is_hidhide_installed():
            return False

        try:
            # Consultar lista blanca actual
            p = self._run_cli(["--app-list"], timeout=4.0)
            app_list_lower = p.stdout.lower()

            candidates = set()
            if exe_path:
                candidates.add(os.path.abspath(exe_path))

            if sys.executable:
                candidates.add(os.path.abspath(sys.executable))
                try:
                    candidates.add(os.path.realpath(sys.executable))
                except Exception:
                    pass
                exe_dir = os.path.dirname(sys.executable)
                for alt_name in ("python.exe", "pythonw.exe", "j360More.exe"):
                    alt_path = os.path.join(exe_dir, alt_name)
                    if os.path.isfile(alt_path):
                        candidates.add(alt_path)

            base_dir = os.path.dirname(os.path.abspath(__file__))
            for cand_rel in (
                os.path.join(base_dir, "dist", "j360More.exe"),
                os.path.join(base_dir, "dist", "j360More", "j360More.exe")
            ):
                if os.path.isfile(cand_rel):
                    candidates.add(cand_rel)

            all_ok = True
            for target in candidates:
                if target.lower() not in app_list_lower:
                    res = self._run_cli(["--app-reg", target], timeout=4.0)
                    if res.returncode != 0:
                        all_ok = False
            return all_ok
        except Exception as e:
            print(f"[!] Error asegurando whitelist en HidHide: {e}")
            return False

    # ==========================================
    # GESTION DE CLOAKING Y DISPOSITIVOS OCULTOS
    # ==========================================
    def is_cloak_active(self) -> bool:
        """Retorna True si el cloaking global de HidHide está activo."""
        if not self.is_hidhide_installed():
            return False
        try:
            p = self._run_cli(["--cloak-state"])
            return "--cloak-on" in p.stdout.lower()
        except Exception:
            return False

    def set_cloak_active(self, enable: bool) -> bool:
        """Activa o desactiva el cloaking global de HidHide."""
        if not self.is_hidhide_installed():
            return False
        try:
            cmd = "--cloak-on" if enable else "--cloak-off"
            p = self._run_cli([cmd])
            return p.returncode == 0
        except Exception as e:
            print(f"[!] Error configurando cloaking en HidHide: {e}")
            return False

    def get_hidden_device_paths(self, max_age: float = 10.0) -> Set[str]:
        """Obtiene el conjunto de rutas de instancia actualmente ocultas en HidHide con caché de respuesta."""
        if not self.is_hidhide_installed():
            return set()

        import time
        now = time.time()
        if getattr(self, "_hidden_paths_cache", None) is not None and (now - getattr(self, "_hidden_paths_cache_time", 0.0)) < max_age:
            return self._hidden_paths_cache

        try:
            p = self._run_cli(["--dev-list"], timeout=3.0)
            paths = set()
            for line in p.stdout.splitlines():
                line = line.strip()
                if line.startswith('--dev-hide "') and line.endswith('"'):
                    path = line[len('--dev-hide "'):-1]
                    paths.add(path.upper())
            self._hidden_paths_cache = paths
            self._hidden_paths_cache_time = now
            return paths
        except Exception:
            return getattr(self, "_hidden_paths_cache", set())

    def get_gaming_devices_info(self, max_age: float = 30.0) -> List[Dict[str, Any]]:
        """Obtiene la lista de mandos para juegos detectados por HidHide en formato JSON con caché de respuesta."""
        if not self.is_hidhide_installed():
            return []

        import time
        now = time.time()
        if getattr(self, "_gaming_cache", None) is not None and (now - getattr(self, "_gaming_cache_time", 0.0)) < max_age:
            return self._gaming_cache

        try:
            p = self._run_cli(["--dev-gaming"], timeout=4.0)
            if not p.stdout or not p.stdout.strip():
                return []
            data = json.loads(p.stdout)
            devices = []
            for container in data:
                for d in container.get("devices", []):
                    devices.append({
                        "description": d.get("description", ""),
                        "instance_path": d.get("deviceInstancePath", ""),
                        "base_container": d.get("baseContainerDeviceInstancePath", ""),
                        "present": d.get("present", False),
                        "usage": d.get("usage", "")
                    })
            self._gaming_cache = devices
            self._gaming_cache_time = now
            return devices
        except Exception as e:
            return getattr(self, "_gaming_cache", [])

    def hide_device(self, instance_path: str) -> bool:
        """Oculta un dispositivo físico específico y activa el cloaking global si está apagado."""
        if not self.is_hidhide_installed() or not instance_path:
            return False

        try:
            # 1. Asegurar que j360More esté en la lista blanca antes de ocultar
            self.ensure_process_whitelisted()

            # 2. Agregar a la lista negra
            p = self._run_cli(["--dev-hide", instance_path])
            if p.returncode != 0:
                return False

            # 3. Asegurar que el cloaking esté activo
            self.set_cloak_active(True)
            self._hidden_paths_cache = None
            self._gaming_cache = None
            return True
        except Exception as e:
            print(f"[!] Error ocultando dispositivo en HidHide: {e}")
            return False

    def unhide_device(self, instance_path: str) -> bool:
        """Desoculta un dispositivo físico específico en HidHide."""
        if not self.is_hidhide_installed() or not instance_path:
            return False

        try:
            p = self._run_cli(["--dev-unhide", instance_path])
            self._hidden_paths_cache = None
            self._gaming_cache = None
            return p.returncode == 0
        except Exception as e:
            print(f"[!] Error desocultando dispositivo en HidHide: {e}")
            return False
