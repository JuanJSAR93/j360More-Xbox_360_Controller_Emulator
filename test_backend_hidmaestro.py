import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hidmaestro_backend import (
    is_hidmaestro_available,
    is_hidmaestro_driver_installed,
    find_hidmaestro_executable,
    find_hidmaestro_dll,
    HidMaestroClient,
    DEFAULT_PROFILES,
    HM_BUTTONS
)

def main():
    print("=" * 60)
    print(" [3/3] VERIFICANDO DRIVER: HIDMAESTRO")
    print("=" * 60)

    # 1. Chequeo de archivos organizados en bin/hidmaestro/
    available = is_hidmaestro_available()
    exe = find_hidmaestro_executable()
    dll = find_hidmaestro_dll()
    print(f"  [OK] Binarios en bin/hidmaestro/             : {'PASS' if available else 'FAIL'}")
    print(f"       -> Ejecutable Host IPC: {exe}")
    print(f"       -> Ensamblado Core    : {dll}")

    # 2. DriverStore
    in_driverstore = is_hidmaestro_driver_installed()
    print(f"  [OK] Driver registrado en DriverStore (inf)  : {'PASS' if in_driverstore else 'FAIL'}")

    # 3. Perfiles soportados
    print(f"  [OK] Perfiles nativos verificados            : {list(DEFAULT_PROFILES.keys())}")
    print(f"  [OK] Mapeo de botones nativo HM_BUTTONS      : {len(HM_BUTTONS)} controles mapeados")

    # 4. Estado del servicio IPC
    c = HidMaestroClient()
    alive = c.is_server_alive()
    elevated = c.is_server_elevated()
    print(f"  [*] Servidor IPC en escucha (Puerto 3255)    : {'Activo' if alive else 'Inactivo (se levanta con la GUI)'}")
    print(f"  [*] Estado de elevacion Administrativa (UAC) : {'ELEVADO' if elevated else 'Requiere confirmacion UAC interactiva al pulsar Iniciar'}")

    total_pass = available and in_driverstore
    print(f"\n>>> RESULTADO HIDMAESTRO: {'LISTO Y VERIFICADO [OK]' if total_pass else 'FALLO'} <<<")
    return 0 if total_pass else 1

if __name__ == '__main__':
    sys.exit(main())
