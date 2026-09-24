"""Detect physical and virtual gamepads on Windows and Linux.

The script is read-only. It uses OS PnP / sysfs metadata, not only VID/PID:
VID/PID can be deliberately copied by a virtual device such as VIIPER or ViGEmBus.

Supports driver-conditioned filtering:
- When active_driver is "viiper", only VIIPER virtual controllers are filtered.
- When active_driver is "vigem", only ViGEmBus virtual controllers are filtered.
- When active_driver is "all", both are filtered.

Usage:
    python detect_virtual_gamepads.py
    python detect_virtual_gamepads.py --driver viiper
    python detect_virtual_gamepads.py --driver vigem
    python detect_virtual_gamepads.py --all --json
    python detect_virtual_gamepads.py --virtual-only
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple


PS_SCRIPT = r'''
$ErrorActionPreference = 'SilentlyContinue'

function Get-PropertyData($Properties, [string]$KeyName) {
  $property = @($Properties | Where-Object KeyName -eq $KeyName | Select-Object -First 1)
  if ($null -eq $property) { return $null }
  if ($property.Data -is [array]) {
    return @($property.Data | ForEach-Object { [string]$_ })
  }
  return [string]$property.Data
}

Get-CimInstance Win32_PnPEntity | ForEach-Object {
  $instanceId = [string]$_.PNPDeviceID
  if ([string]::IsNullOrWhiteSpace($instanceId)) { return }

  $hardwareIds = @($_.HardwareID | ForEach-Object { [string]$_ })
  $compatibleIds = @($_.CompatibleID | ForEach-Object { [string]$_ })
  $hardwareText = (($hardwareIds + $compatibleIds) -join ' ')
  $class = [string]$_.PNPClass
  $name = [string]$_.Name
  $service = [string]$_.Service
  $preCandidate = $hardwareText -match
    'VID_045E&PID_(028E|02EA|0B12)|VID_054C&PID_(05C4|09CC|0CE6|0DF2)|VID_057E&PID_2069' -or
    $hardwareText -match 'HID_DEVICE_SYSTEM_GAME' -or
    $class -in @('XnaComposite', 'XboxComposite') -or
    $name -match 'Gamepad|Xbox|DualShock|DualSense|Switch|VIIPER|Mando|Game controller|Controlador de juego' -or
    $service -match 'xusb22|vigem|usbip|vhci|dc1-controller'
  if (-not $preCandidate) { return }
  $deviceProperties = @(Get-PnpDeviceProperty -InstanceId $instanceId -KeyName @(
    'DEVPKEY_Device_Parent',
    'DEVPKEY_Device_BusReportedDeviceDesc',
    'DEVPKEY_Device_EnumeratorName',
    'DEVPKEY_Device_DriverInfPath',
    'DEVPKEY_Device_LocationPaths'
  ))
  $parentId = [string](Get-PropertyData $deviceProperties 'DEVPKEY_Device_Parent')
  $busReported = Get-PropertyData $deviceProperties 'DEVPKEY_Device_BusReportedDeviceDesc'
  $parentProperties = @(Get-PnpDeviceProperty -InstanceId $parentId -KeyName @(
    'DEVPKEY_Device_BusReportedDeviceDesc',
    'DEVPKEY_Device_Parent'
  ))
  $parentBusReported = Get-PropertyData $parentProperties 'DEVPKEY_Device_BusReportedDeviceDesc'
  $grandParent = Get-PropertyData $parentProperties 'DEVPKEY_Device_Parent'
  $enumerator = Get-PropertyData $deviceProperties 'DEVPKEY_Device_EnumeratorName'
  $driverInf = Get-PropertyData $deviceProperties 'DEVPKEY_Device_DriverInfPath'
  $locationPaths = Get-PropertyData $deviceProperties 'DEVPKEY_Device_LocationPaths'
  $identityText = (($name, $busReported, $parentBusReported, $hardwareText, $service, $enumerator) -join ' ')

  # Include known controller identities even when Windows exposes them through
  # a localized or vendor-specific PnP class. The classifier decides later if
  # the controller is physical, ViGEmBus, USB/IP, or VIIPER.
  $knownControllerId = $hardwareText -match
    'VID_045E&PID_(028E|02EA|0B12)|VID_054C&PID_(05C4|09CC|0CE6|0DF2)|VID_057E&PID_2069'
  $isCandidate = $knownControllerId -or
    (($class -in @('HIDClass', 'XnaComposite', 'XboxComposite') -and
      $name -match 'Gamepad|Xbox|DualShock|DualSense|Switch|Controller|Mando|Controlador')) -or
    $service -match 'xusb22|vigem|usbip|vhci|dc1-controller' -or
    $identityText -match 'VIIPER|Virtual Gamepad|Virtual Xbox|Virtual DS4|Virtual DualShock|Virtual DualSense' -or
    ($class -eq 'HIDClass' -and $hardwareText -match 'HID_DEVICE_SYSTEM_GAME')

  if ($isCandidate) {
    [PSCustomObject][ordered]@{
      instance_id = $instanceId
      class = $class
      friendly_name = $name
      status = [string]$_.Status
      problem = [string]$_.ConfigManagerErrorCode
      service = $service
      manufacturer = [string]$_.Manufacturer
      hardware_ids = $hardwareIds
      compatible_ids = $compatibleIds
      class_guid = [string]$_.ClassGuid
      Parent = $parentId
      BusReportedDeviceDesc = $busReported
      ParentBusReportedDeviceDesc = $parentBusReported
      GrandParent = $grandParent
      EnumeratorName = $enumerator
      DriverInfPath = $driverInf
      LocationPaths = $locationPaths
    }
  }
} | ConvertTo-Json -Depth 8 -Compress
'''


def native_windows_devices() -> list[dict[str, Any]]:
    """Enumeración nativa de dispositivos PnP en Windows usando cfgmgr32 (C ctypes).
    Se ejecuta en ~0.05s de forma 100% nativa en Python, sin lanzar powershell.exe ni WMI.
    """
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    try:
        cfgmgr32 = ctypes.windll.cfgmgr32
    except Exception:
        return []

    def get_reg_prop(dn: int, prop_idx: int) -> str:
        buf_size = wintypes.ULONG(2048)
        buf = ctypes.create_unicode_buffer(2048)
        reg_type = wintypes.ULONG()
        ret = cfgmgr32.CM_Get_DevNode_Registry_PropertyW(
            dn, prop_idx, ctypes.byref(reg_type), ctypes.byref(buf), ctypes.byref(buf_size), 0
        )
        if ret == 0:
            val = buf[:buf_size.value // 2].rstrip('\x00')
            return val.replace('\x00', ' ')
        return ''

    size = wintypes.ULONG()
    if cfgmgr32.CM_Get_Device_ID_List_SizeW(ctypes.byref(size), None, 0) != 0:
        return []
    buf = ctypes.create_unicode_buffer(size.value)
    if cfgmgr32.CM_Get_Device_ID_ListW(None, buf, size.value, 0) != 0:
        return []
    ids = [i for i in buf[:].split('\x00') if i]

    results: list[dict[str, Any]] = []
    for dev_id in ids:
        dn = wintypes.DWORD()
        if cfgmgr32.CM_Locate_DevNodeW(ctypes.byref(dn), dev_id, 0) != 0:
            continue

        cls = get_reg_prop(dn, 8)       # CM_DRP_CLASS
        service = get_reg_prop(dn, 5)   # CM_DRP_SERVICE
        name = get_reg_prop(dn, 13) or get_reg_prop(dn, 1) # FriendlyName or DeviceDesc
        hwid = get_reg_prop(dn, 2)      # CM_DRP_HARDWAREID
        comp = get_reg_prop(dn, 3)      # CM_DRP_COMPATIBLEIDS
        bus_reported = get_reg_prop(dn, 22) # CM_DRP_BUSREPORTEDDEVICEDESC
        enum_name = get_reg_prop(dn, 26)    # CM_DRP_ENUMERATOR_NAME

        text_scan = f"{dev_id} {cls} {service} {name} {hwid} {comp} {bus_reported} {enum_name}".upper()
        
        # Omitir chipsets de placa base comunes a menos que sean transporte USB/IP o buses virtuales
        if any(ign in text_scan for ign in ('VEN_8086', 'VEN_1022', 'INTEL(R)', 'AMD ', 'HOST CONTROLLER', 'GPIO', 'SPI (FLASH)')) and not any(v in text_scan for v in ('USBIP', 'VHCI', 'VIGEM')):
            continue

        is_candidate = any(k in text_scan for k in (
            '045E', '054C', '057E', '028E', '02EA', '0B12', '0B13',
            '05C4', '09CC', '0CE6', '0DF2', '2069',
            'HID_DEVICE_SYSTEM_GAME', 'GAMEPAD', 'JOYSTICK', 'XBOX',
            'DUALSHOCK', 'DUALSENSE', 'SWITCH', 'VIGEM', 'VIIPER',
            'USBIP', 'VHCI', 'XUSB22', 'DC1-CONTROLLER', 'MANDO'
        ))
        if not is_candidate and cls not in ('XnaComposite', 'XboxComposite'):
            continue

        p_dn = wintypes.DWORD()
        curr_dn = dn
        parent_id = ''
        grandparent_id = ''
        parent_bus_reported = ''
        ancestor_tokens: list[str] = []

        depth = 0
        while cfgmgr32.CM_Get_Parent(ctypes.byref(p_dn), curr_dn, 0) == 0:
            p_buf = ctypes.create_unicode_buffer(512)
            if cfgmgr32.CM_Get_Device_IDW(p_dn, p_buf, 512, 0) != 0:
                break
            anc_id = p_buf.value
            if not anc_id or anc_id.startswith("HTREE") or anc_id == "ROOT":
                break
            anc_svc = get_reg_prop(p_dn, 5)
            anc_desc = get_reg_prop(p_dn, 1) or get_reg_prop(p_dn, 13)
            anc_bus = get_reg_prop(p_dn, 22)

            for item in (anc_id, anc_svc, anc_desc, anc_bus):
                if item and item not in ancestor_tokens:
                    ancestor_tokens.append(item)

            if depth == 0:
                parent_id = anc_id
                parent_bus_reported = anc_bus
            elif depth == 1:
                grandparent_id = anc_id

            curr_dn = wintypes.DWORD(p_dn.value)
            depth += 1
            if depth >= 5:
                break

        results.append({
            'instance_id': dev_id,
            'class': cls,
            'friendly_name': name,
            'name': name,
            'service': service,
            'enumerator': enum_name,
            'BusReportedDeviceDesc': bus_reported,
            'Parent': parent_id,
            'ParentBusReportedDeviceDesc': parent_bus_reported,
            'GrandParent': grandparent_id,
            'Ancestors': " ".join(ancestor_tokens),
            'hardware_ids': hwid.split(),
            'compatible_ids': comp.split(),
            'HardwareIds': hwid.split(),
            'CompatibleIds': comp.split(),
        })
    return results


def powershell_devices() -> list[dict[str, Any]]:
    cmd = [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-Command", PS_SCRIPT,
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
    except FileNotFoundError as exc:
        raise RuntimeError("No se encontró powershell.exe; este script requiere Windows.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("La consulta PnP superó el límite de 5 segundos.") from exc
    if p.returncode != 0 and not p.stdout.strip():
        return pnputil_devices()
    try:
        data = json.loads(p.stdout) if p.stdout.strip() else []
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"La salida de PowerShell no fue JSON válido: {exc}") from exc
    if data is None:
        return []
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise RuntimeError("La salida de PowerShell no contiene una lista PnP válida.")
    return data


def pnputil_devices() -> list[dict[str, Any]]:
    """Inventario reducido de fallback con pnputil para sesiones restringidas de Windows."""
    cmd = ["pnputil.exe", "/enum-devices", "/connected", "/class", "HIDClass", "/deviceids"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="mbcs", errors="replace", timeout=5)
    except (FileNotFoundError, LookupError) as exc:
        raise RuntimeError("No se pudo usar pnputil para enumerar dispositivos HID.") from exc
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "pnputil no pudo enumerar dispositivos HID.")

    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    field_patterns = {
        "instance_id": re.compile(r"(?:Instance ID|Id\. de instancia)\s*:\s*(.+)$", re.I),
        "friendly_name": re.compile(r"(?:Device description|Descripci.n del dispositivo)\s*:\s*(.+)$", re.I),
        "class": re.compile(r"(?:Class Name|Nombre de clase)\s*:\s*(.+)$", re.I),
        "manufacturer": re.compile(r"(?:Manufacturer Name|Nombre del fabricante)\s*:\s*(.+)$", re.I),
        "driver": re.compile(r"(?:Driver Name|Nombre del controlador)\s*:\s*(.+)$", re.I),
    }
    for raw in p.stdout.splitlines():
        line = raw.strip()
        match = field_patterns["instance_id"].match(line)
        if match:
            if current and current.get("instance_id"):
                rows.append(current)
            current = {"instance_id": match.group(1).strip(), "hardware_ids": []}
            continue
        if current is None:
            continue
        for key, pattern in field_patterns.items():
            match = pattern.match(line)
            if match and key != "instance_id":
                current[key] = match.group(1).strip()
                break
        else:
            if line.startswith("HID\\") or line.startswith("USB\\") or line.startswith("ROOT\\"):
                current["hardware_ids"].append(line)
    if current and current.get("instance_id"):
        rows.append(current)
    return rows


def linux_devices() -> list[dict[str, Any]]:
    """Enumera dispositivos de entrada en Linux vía sysfs."""
    devices: list[dict[str, Any]] = []
    base_path = Path("/sys/class/input")
    if not base_path.exists():
        return devices

    for dev_entry in base_path.iterdir():
        if not (dev_entry.name.startswith("event") or dev_entry.name.startswith("js")):
            continue
        device_dir = dev_entry / "device"
        if not device_dir.exists():
            continue
        try:
            real_path = str(device_dir.resolve())
            name_file = device_dir / "name"
            name = name_file.read_text(encoding="utf-8").strip() if name_file.exists() else dev_entry.name
            name_l = name.lower()
            is_usbip = "vhci_hcd" in real_path or "usbip" in real_path
            is_viiper = "viiper" in name_l or is_usbip
            is_virtual = "/devices/virtual/" in real_path or is_usbip or is_viiper
            origin = "VIIPER" if is_viiper else ("unknown" if is_virtual else "physical")

            devices.append({
                "instance_id": real_path,
                "name": name,
                "friendly_name": name,
                "path": real_path,
                "BusReportedDeviceDesc": "VIIPER" if is_viiper else "",
                "Service": "usbip" if is_usbip else "",
                "class": "input",
                "origin": origin,
                "is_virtual": is_virtual,
            })
        except Exception:
            continue
    return devices


def get_system_devices() -> list[dict[str, Any]]:
    """Obtiene los dispositivos de hardware de forma multiplataforma sin depender de PowerShell."""
    if sys.platform == "win32":
        try:
            devs = native_windows_devices()
            if devs:
                return devs
        except Exception:
            pass
        try:
            return powershell_devices()
        except Exception:
            return pnputil_devices()
    elif sys.platform.startswith("linux"):
        return linux_devices()
    return []


# Caché global en memoria con TTL para evitar relanzar PowerShell en cada frame de la GUI
_DEVICE_CACHE: dict[str, Any] = {
    "timestamp": 0.0,
    "devices": [],
}


def get_cached_devices(max_age: float = 5.0) -> list[dict[str, Any]]:
    """Retorna la lista de dispositivos del sistema usando caché con TTL."""
    now = time.time()
    if _DEVICE_CACHE["devices"] and (now - _DEVICE_CACHE["timestamp"]) < max_age:
        return _DEVICE_CACHE["devices"]
    try:
        devs = get_system_devices()
        _DEVICE_CACHE["devices"] = devs
        _DEVICE_CACHE["timestamp"] = now
        return devs
    except Exception:
        return _DEVICE_CACHE.get("devices", [])


def clear_device_cache():
    """Invalida la caché de dispositivos PnP."""
    _DEVICE_CACHE["timestamp"] = 0.0
    _DEVICE_CACHE["devices"] = []


def text(device: dict[str, Any]) -> str:
    parts: list[str] = []
    for value in device.values():
        if isinstance(value, list):
            parts.extend(str(x) for x in value)
        elif value is not None:
            parts.append(str(value))
    return " ".join(parts).lower()


def value(device: dict[str, Any], *names: str) -> Any:
    for name in names:
        if device.get(name) not in (None, "", []):
            return device.get(name)
    return None


def normalized(value_to_normalize: Any) -> str:
    if isinstance(value_to_normalize, list):
        value_to_normalize = " ".join(str(item) for item in value_to_normalize)
    return " ".join(str(value_to_normalize or "").lower().split())


def pnp_signal_text(device: dict[str, Any]) -> str:
    fields = (
        value(device, "friendly_name", "name"),
        value(device, "BusReportedDeviceDesc", "bus_reported_desc", "bus_reported"),
        value(device, "ParentBusReportedDeviceDesc", "parent_bus_reported"),
        value(device, "Parent", "parent"),
        value(device, "GrandParent", "grandparent"),
        value(device, "Ancestors", "ancestors"),
        value(device, "EnumeratorName", "enumerator_name", "enumerator"),
        value(device, "Service", "service"),
        value(device, "Driver", "driver"),
        value(device, "DriverInfPath", "driver_inf_path", "driver_inf"),
        value(device, "HardwareIds", "hardware_ids"),
        value(device, "CompatibleIds", "compatible_ids"),
    )
    return normalized(" ".join(normalized(field) for field in fields))


def controller_model(device: dict[str, Any]) -> str:
    signals = pnp_signal_text(device)
    if "xbox series" in signals or "pid_0b12" in signals:
        return "Xbox Series X|S"
    if "xbox one" in signals or "pid_02ea" in signals:
        return "Xbox One"
    if "xbox 360" in signals or "pid_028e" in signals:
        return "Xbox 360"
    if "dualsense" in signals or "pid_0ce6" in signals or "pid_0df2" in signals:
        return "DualSense"
    if "dualshock" in signals or "ps4" in signals or "pid_05c4" in signals or "pid_09cc" in signals:
        return "DualShock 4"
    if "switch 2" in signals or "ns2pro" in signals or "pid_2069" in signals:
        return "Switch 2 Pro"
    return "unknown"


def classify_origin(d: dict[str, Any]) -> tuple[str, str, int, str]:
    """Clasifica un dispositivo identificando su origen intrínseco (VIIPER, ViGEmBus o desconocido)."""
    signals = pnp_signal_text(d)
    bus_description = normalized(value(d, "BusReportedDeviceDesc", "bus_reported_desc", "bus_reported"))
    parent_description = normalized(value(d, "ParentBusReportedDeviceDesc", "parent_bus_reported"))
    service = normalized(value(d, "Service", "service"))
    parent = normalized(value(d, "Parent", "parent"))
    instance = normalized(value(d, "instance_id"))

    # VIIPER signature
    if "viiper" in bus_description or "viiper" in parent_description:
        return "virtual", "VIIPER BusReportedDeviceDesc", 100, "VIIPER"

    if (
        "A1B2C3D4E5F60706" in instance.upper()
        or "0000FFFB" in instance.upper()
        or "VIIPER" in signals.upper()
    ):
        return "virtual", "VIIPER device identity/serial", 100, "VIIPER"

    # ViGEmBus signature
    vigem_evidence = (
        "vigembus" in signals
        or "vigem bus" in signals
        or "root\\vigem" in signals
        or "root\\system\\0003" in signals
        or "nefarius\\vigembus" in signals
        or service == "vigembus"
    )
    if vigem_evidence:
        return "virtual", "ViGEmBus PnP chain", 100, "ViGEmBus"

    if any(token in signals for token in ("usbip", "vhci", "usb/ip")):
        return "virtual", "USB/IP or VIIPER transport", 98, "VIIPER"

    if any(token in (instance + " " + parent + " " + signals)
           for token in ("root\\", "software", "virtual", "swd\\", "swdevice")):
        return "likely_virtual", "software/root PnP enumerator", 70, "unknown"

    if any(token in signals for token in (
        "hid", "gamepad", "controller", "xbox", "dualshock", "dualsense", "switch"
    )):
        return "unknown", "HID/gamepad without a definitive virtual-bus signature", 35, "unknown"
    return "other", "not classified as a gamepad", 0, "unknown"


def classify_driver(d: dict[str, Any], active_driver: str = "all") -> tuple[str, str, int, str]:
    """Clasifica un dispositivo de forma condicionada por el driver activo.
    
    - Si active_driver == 'viiper': Solo clasifica como virtual los creados por VIIPER.
    - Si active_driver in ('vigem', 'vigembus'): Solo clasifica como virtual los de ViGEmBus.
    - Si active_driver in ('all', 'both'): Clasifica cualquier virtual.
    """
    kind, reason, confidence, origin = classify_origin(d)
    norm_driver = active_driver.lower()

    if norm_driver in ("viiper", "usbip"):
        if origin == "VIIPER":
            return kind, reason, confidence, origin
        # Si fue creado por ViGEmBus pero el driver activo es VIIPER, no se filtra
        return "other", f"Ignorado bajo filtro exclusivo VIIPER (origen: {origin})", 0, origin

    elif norm_driver in ("vigem", "vigembus"):
        if origin == "ViGEmBus":
            return kind, reason, confidence, origin
        # Si fue creado por VIIPER pero el driver activo es ViGEmBus, no se filtra
        return "other", f"Ignorado bajo filtro exclusivo ViGEmBus (origen: {origin})", 0, origin

    # Modo 'all': reporta cualquier dispositivo virtual detectado
    return kind, reason, confidence, origin


def classify(d: dict[str, Any]) -> tuple[str, str, int]:
    """Compatibilidad hacia atrás: clasifica sin condicionar por driver."""
    kind, reason, confidence, _ = classify_origin(d)
    return kind, reason, confidence


def get_virtual_instance_ids(active_driver: str = "all", max_age: float = 5.0) -> set[str]:
    """Retorna un conjunto con las rutas/IDs de instancia de mandos virtuales para el driver indicado,
    incluyendo de forma exhaustiva todos los nodos descendientes (hijos y nietos en el árbol PnP)."""
    devs = get_cached_devices(max_age)
    virtual_ids: set[str] = set()
    for d in devs:
        kind, _, _, _ = classify_driver(d, active_driver=active_driver)
        if kind in ("virtual", "likely_virtual"):
            for key in ("instance_id", "Parent", "parent", "path"):
                val = d.get(key)
                if val:
                    s_val = str(val).strip().upper()
                    if s_val and not s_val.startswith("HTREE") and s_val != "ROOT":
                        virtual_ids.add(s_val)

    # Propagación recursiva hacia abajo: cualquier nodo cuyo padre o abuelo esté en virtual_ids es virtual
    added = True
    while added:
        added = False
        for d in devs:
            iid = (d.get("instance_id") or "").strip().upper()
            if iid and iid not in virtual_ids:
                p = (d.get("Parent") or "").strip().upper()
                gp = (d.get("GrandParent") or "").strip().upper()
                if (p and p in virtual_ids) or (gp and gp in virtual_ids):
                    virtual_ids.add(iid)
                    added = True

    return virtual_ids


def get_virtual_vid_pids(active_driver: str = "all", max_age: float = 5.0) -> set[tuple[str, str]]:
    """Retorna los pares (VID, PID) de dispositivos identificados como virtuales para el driver activo."""
    import re
    v_ids = get_virtual_instance_ids(active_driver=active_driver, max_age=max_age)
    vid_pids: set[tuple[str, str]] = set()
    for vid_str in v_ids:
        m_vid = re.search(r'VID[_\&]([0-9A-F]{4})', vid_str)
        m_pid = re.search(r'PID[_\&]([0-9A-F]{4})', vid_str)
        if m_vid and m_pid:
            vid_pids.add((m_vid.group(1).upper(), m_pid.group(1).upper()))
    return vid_pids


def is_virtual_device(
    instance_id: str = "",
    name: str = "",
    active_driver: str = "all",
    max_age: float = 5.0
) -> bool:
    """Comprueba si un dispositivo específico es virtual bajo el driver seleccionado."""
    norm_id = instance_id.strip().upper()
    norm_name = name.strip().lower()
    norm_driver = active_driver.lower()

    if norm_id:
        v_ids = get_virtual_instance_ids(active_driver=active_driver, max_age=max_age)
        if norm_id in v_ids:
            return True
        for vid in v_ids:
            if vid and (vid in norm_id or norm_id in vid):
                return True

    # Comprobaciones rápidas por nombre condicionadas al driver
    if norm_driver in ("viiper", "usbip", "all"):
        if any(x in norm_name for x in ("viiper", "usbip", "vhci")):
            return True
    if norm_driver in ("vigem", "vigembus", "all"):
        if any(x in norm_name for x in ("vigem", "nefarius", "virtual gamepad emulation bus")):
            return True

    return False


def is_gamepad(d: dict[str, Any]) -> bool:
    name = normalized(value(d, "friendly_name", "name"))
    instance = normalized(value(d, "instance_id"))
    device_class = normalized(value(d, "class"))
    all_text = pnp_signal_text(d)
    bus_infrastructure = (
        "virtual gamepad emulation bus" in name
        or "emulated host controller" in name
        or "root hub" in name
        or ("host controller" in name and "controller" not in name.removesuffix(" host controller"))
        or name.endswith(" emulation bus")
    )
    if bus_infrastructure:
        return False
    explicit = (
        "gamepad", "xbox", "dualshock", "dualsense", "joystick",
        "switch", "mando", "controlador de juego", "game controller",
        "hid_device_system_game", "viiper",
    )
    if any(x in name for x in explicit):
        return True
    if "hid_device_system_game" in all_text or device_class == "xnacomposite":
        return True
    return "controller" in name and (
        device_class == "hidclass"
        or instance.startswith(("HID\\", "USB\\", "BTHLE\\", "ROOT\\", "/sys/"))
        or str(d.get("class", "")).lower() == "xnacomposite"
    )


def compact(d: dict[str, Any], active_driver: str = "all") -> dict[str, Any]:
    kind, reason, confidence, origin = classify_driver(d, active_driver=active_driver)
    bus_reported = value(d, "BusReportedDeviceDesc", "bus_reported_desc", "bus_reported")
    parent_bus_reported = value(d, "ParentBusReportedDeviceDesc", "parent_bus_reported")
    friendly_name = value(d, "friendly_name", "name")
    display_name = bus_reported or parent_bus_reported or friendly_name or value(d, "instance_id")
    model = controller_model(d)
    return {
        "classification": kind,
        "confidence": confidence,
        "reason": reason,
        "origin": origin,
        "model": model,
        "name": display_name,
        "friendly_name": friendly_name,
        "bus_reported": bus_reported,
        "instance_id": value(d, "instance_id"),
        "class": value(d, "class"),
        "status": value(d, "status"),
        "problem": value(d, "problem"),
        "parent": value(d, "Parent", "parent"),
        "parent_bus_reported": parent_bus_reported,
        "grandparent": value(d, "GrandParent", "grandparent"),
        "enumerator": value(d, "EnumeratorName", "enumerator_name", "enumerator"),
        "service": value(d, "Service", "service"),
        "driver": value(d, "Driver", "driver"),
        "driver_inf": value(d, "DriverInfPath", "driver_inf_path", "driver_inf"),
        "manufacturer": value(d, "Manufacturer", "manufacturer"),
        "hardware_ids": value(d, "HardwareIds", "hardware_ids"),
        "compatible_ids": value(d, "CompatibleIds", "compatible_ids"),
        "location_paths": value(d, "LocationPaths", "location_paths"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Clasifica mandos físicos y virtuales mediante metadatos PnP de Windows o sysfs de Linux.")
    ap.add_argument("--driver", choices=["all", "viiper", "vigem"], default="all", help="driver activo a considerar para la detección condicionada (default: all)")
    ap.add_argument("--all", action="store_true", help="mostrar todos los dispositivos PnP")
    ap.add_argument("--virtual-only", action="store_true", help="mostrar solo virtuales o probablemente virtuales")
    ap.add_argument("--json", action="store_true", help="emitir JSON")
    args = ap.parse_args()

    try:
        devices = get_system_devices()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    rows = [compact(d, active_driver=args.driver) for d in devices if args.all or is_gamepad(d)]
    if args.virtual_only:
        rows = [r for r in rows if r["classification"] in ("virtual", "likely_virtual")]
    rows.sort(key=lambda r: (-int(r["confidence"]), str(r["name"])))

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    if not rows:
        print("No se encontraron dispositivos con los filtros indicados.")
        return 0
    for r in rows:
        print(f"[{r['classification']:<14} {r['confidence']:>3}%] {r['origin']} / {r['model']} / {r['name']}")
        print(f"  instance: {r['instance_id']}")
        print(f"  BusReportedDeviceDesc: {r['bus_reported']} | parent desc: {r['parent_bus_reported']}")
        print(f"  bus/parent: {r['enumerator']} | {r['parent']}")
        print(f"  service/driver: {r['service']} | {r['driver']} | {r['driver_inf']}")
        print(f"  motivo: {r['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
