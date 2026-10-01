"""
plugins/venv_manager.py
Multiplatform Python runtime detector, Zero-Install portable downloader,
virtual environment manager (.venv), and asynchronous pip installer.
"""

import os
import platform
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile
from typing import Callable, List, Optional, Tuple

PYTHON_EMBED_URL_AMD64 = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"


def get_default_base_dir() -> str:
    """
    Returns the persistent base directory of the application:
    - If running as a frozen PyInstaller binary, returns the directory of the executable (EXE_DIR),
      NOT the temporary extraction directory (sys._MEIPASS).
    - If running from source, returns the project root.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class VenvManager:
    """
    Manages the isolated Python virtual environment for plugins.
    Ensures zero-install operation on Windows and native venv support on Linux.
    """

    def __init__(self, base_dir: Optional[str] = None):
        if not base_dir:
            base_dir = get_default_base_dir()
        self.base_dir = base_dir
        self.plugins_dir = os.path.join(self.base_dir, "plugins")
        self.venv_dir = os.path.join(self.plugins_dir, ".venv")
        self.portable_dir = os.path.join(self.base_dir, "bin", "python_portable")

    def get_venv_python(self) -> Optional[str]:
        """Returns the path to the python executable inside plugins/.venv, if it exists."""
        if platform.system() == "Windows":
            py_path = os.path.join(self.venv_dir, "Scripts", "python.exe")
        else:
            py_path = os.path.join(self.venv_dir, "bin", "python")

        if os.path.isfile(py_path):
            return py_path

        # Check portable runtime fallback
        portable_py = os.path.join(self.portable_dir, "python.exe")
        if os.path.isfile(portable_py):
            return portable_py

        return None

    def find_system_python(self) -> Optional[str]:
        """Discovers standard Python on the host machine (PATH or sys.executable)."""
        # If running within a normal Python interpreter, sys.executable is our best candidate
        if getattr(sys, "frozen", False) is False:
            if sys.executable and os.path.isfile(sys.executable):
                try:
                    res = subprocess.run([sys.executable, "--version"], capture_output=True, text=True, timeout=3)
                    if res.returncode == 0:
                        return sys.executable
                except Exception:
                    pass

        # Try which python3 / python
        candidates = ["python3", "python", "py"]
        for cand in candidates:
            found = shutil.which(cand)
            if found:
                try:
                    res = subprocess.run([found, "--version"], capture_output=True, text=True, timeout=3)
                    if res.returncode == 0 and "Python 3." in res.stdout:
                        return found
                except Exception:
                    pass

        # Check standard Linux locations
        if platform.system() == "Linux":
            for p in ["/usr/bin/python3", "/usr/local/bin/python3"]:
                if os.path.isfile(p):
                    return p

        # Check Windows registry or default paths
        if platform.system() == "Windows":
            user_profile = os.environ.get("USERPROFILE", "")
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            for p in [
                os.path.join(local_appdata, "Programs", "Python", "Python311", "python.exe"),
                os.path.join(local_appdata, "Programs", "Python", "Python312", "python.exe"),
                os.path.join(local_appdata, "Programs", "Python", "Python310", "python.exe"),
                r"C:\Python311\python.exe",
                r"C:\Python312\python.exe",
            ]:
                if os.path.isfile(p):
                    return p

        return None

    def ensure_runtime(self, progress_callback: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
        """
        Ensures a working Python environment exists.
        Creates plugins/.venv if missing. Downloads portable runtime on Windows if no Python is found.
        """
        existing = self.get_venv_python()
        if existing:
            return True, existing

        def log(msg: str):
            if progress_callback:
                progress_callback(msg)
            print(f"[VenvManager] {msg}")

        system_py = self.find_system_python()

        # Windows Zero-Install fallback
        if not system_py and platform.system() == "Windows":
            log("No se detectó Python en el sistema. Descargando Python portátil oficial (~15 MB)...")
            success, err = self._download_portable_python(progress_callback=log)
            if not success:
                return False, f"Error al descargar Python portátil: {err}"
            system_py = os.path.join(self.portable_dir, "python.exe")

        if not system_py:
            return False, "No se encontró ningún intérprete de Python 3 en el sistema."

        # Create venv
        log(f"Creando entorno virtual en {self.venv_dir}...")
        try:
            os.makedirs(self.plugins_dir, exist_ok=True)
            res = subprocess.run([system_py, "-m", "venv", self.venv_dir], capture_output=True, text=True, timeout=60)
            if res.returncode != 0:
                # If venv module failed, fallback to portable runtime or direct python
                log(f"Aviso al crear venv: {res.stderr.strip()}. Intentando fallback...")
                return False, f"Fallo al inicializar venv: {res.stderr.strip()}"

            venv_py = self.get_venv_python()
            if venv_py:
                log("Entorno virtual inicializado con éxito.")
                return True, venv_py
            return False, "El archivo ejecutable del venv no se encontró tras la creación."
        except Exception as e:
            return False, str(e)

    def _download_portable_python(self, progress_callback: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
        """Downloads Python Embeddable for Windows and enables site-packages & pip."""
        try:
            os.makedirs(self.portable_dir, exist_ok=True)
            zip_dest = os.path.join(self.portable_dir, "python_embed.zip")

            if progress_callback:
                progress_callback("Descargando paquete oficial de python.org...")

            urllib.request.urlretrieve(PYTHON_EMBED_URL_AMD64, zip_dest)

            if progress_callback:
                progress_callback("Descomprimiendo runtime portátil...")

            with zipfile.ZipFile(zip_dest, "r") as z:
                z.extractall(self.portable_dir)

            if os.path.exists(zip_dest):
                os.remove(zip_dest)

            # Enable site-packages in ._pth file
            for fname in os.listdir(self.portable_dir):
                if fname.endswith("._pth"):
                    pth_file = os.path.join(self.portable_dir, fname)
                    with open(pth_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    with open(pth_file, "w", encoding="utf-8") as f:
                        for line in lines:
                            if "#import site" in line or "import site" in line:
                                f.write("import site\n")
                            else:
                                f.write(line)

            # Bootstrap get-pip.py
            if progress_callback:
                progress_callback("Instalando pip para el runtime portátil...")

            get_pip_dest = os.path.join(self.portable_dir, "get-pip.py")
            urllib.request.urlretrieve(GET_PIP_URL, get_pip_dest)

            py_exe = os.path.join(self.portable_dir, "python.exe")
            res = subprocess.run([py_exe, get_pip_dest, "--no-warn-script-location"], capture_output=True, text=True, timeout=120)

            if os.path.exists(get_pip_dest):
                os.remove(get_pip_dest)

            if res.returncode == 0:
                return True, py_exe
            return False, f"Fallo al instalar pip en runtime portátil: {res.stderr}"

        except Exception as e:
            return False, str(e)

    def install_requirements(
        self,
        requirements_file: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """
        Installs pip dependencies asynchronously or synchronously.
        Streams log lines to progress_callback.
        """
        ok, py_exe_or_err = self.ensure_runtime(progress_callback=progress_callback)
        if not ok:
            return False, py_exe_or_err

        py_exe = py_exe_or_err

        if not os.path.isfile(requirements_file):
            return False, f"No se encontró el archivo {requirements_file}"

        def log(msg: str):
            if progress_callback:
                progress_callback(msg)
            print(f"[pip] {msg}")

        log(f"Instalando dependencias desde {os.path.basename(requirements_file)}...")

        cmd = [py_exe, "-m", "pip", "install", "-r", requirements_file]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            for line in proc.stdout:
                clean = line.strip()
                if clean:
                    log(clean)

            proc.wait()
            if proc.returncode == 0:
                log("¡Todas las librerías se instalaron exitosamente!")
                return True, "Instalación completada con éxito."
            else:
                return False, f"pip terminó con código de error {proc.returncode}"
        except Exception as e:
            return False, str(e)

    def check_requirements_satisfied(self, requirements: List[str]) -> bool:
        """
        Quick check to determine if declared requirements are installed in the venv.
        """
        py_exe = self.get_venv_python()
        if not py_exe:
            return False

        # Format package names: e.g. "pyserial>=3.5" -> "serial" or "pyserial"
        check_script = "import sys\nfor pkg in sys.argv[1:]:\n" \
                       "    name = pkg.split('>=')[0].split('==')[0].split('<')[0].strip()\n" \
                       "    try:\n" \
                       "        __import__(name)\n" \
                       "    except ImportError:\n" \
                       "        sys.exit(1)\n" \
                       "sys.exit(0)\n"

        cmd = [py_exe, "-c", check_script] + requirements
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False
