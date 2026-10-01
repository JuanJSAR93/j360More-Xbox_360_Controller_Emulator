# Sistema de Plugins Extensibles de j360More — Guía Exhaustiva de Desarrollo y Conexión de Hardware Real

Bienvenido a la documentación oficial para desarrolladores y creadores de hardware del sistema de plugins de **j360More**.

Esta guía cubre desde la arquitectura del sistema hasta la creación de plugins avanzados desde cero, el diseño de interfaces gráficas personalizadas declarativas sin escribir código de interfaz, y la conexión de **hardware físico real** (Arduino/ESP32 y teclados/pads MIDI) sin depender de emulación.

---

## Tabla de Contenidos

1. [Arquitectura y Filosofía del Sistema](#1-arquitectura-y-filosofía-del-sistema)
   - [Aislamiento por Procesos Secundarios e IPC](#11-aislamiento-por-procesos-secundarios-e-ipc)
   - [Entorno Virtual Automático (.venv)](#12-entorno-virtual-automático-venv)
2. [Anatomía y Creación de un Plugin desde Cero](#2-anatomía-y-creación-de-un-plugin-desde-cero)
   - [Estructura de Archivos](#21-estructura-de-archivos)
   - [El Manifiesto (`plugin.json`)](#22-el-manifiesto-pluginjson)
   - [Ciclo de Vida de Ejecución](#23-ciclo-de-vida-de-ejecución)
3. [Creación de Interfaces Declarativas Personalizadas (UI)](#3-creación-de-interfaces-declarativas-personalizadas-ui)
   - [Diálogo Global de Configuración (`global_ui`)](#31-diálogo-global-de-configuración-global_ui)
   - [Menús Desplegables Dinámicos (`dynamic_dropdown`) con Escaneo en Vivo](#32-menús-desplegables-dinámicos-con-escaneo-en-vivo)
   - [Pestañas Personalizadas por Mando (`pad_ui_customization`)](#33-pestañas-personalizadas-por-mando-pad_ui_customization)
   - [Monitores de Telemetría Dinámicos (`progress_bar_multi`)](#34-monitores-de-telemetría-dinámicos-progress_bar_multi)
4. [Soporte Multi-Idioma (i18n)](#4-soporte-multi-idioma-i18n)
   - [Enfoque Inline en `plugin.json`](#41-enfoque-inline-en-pluginjson)
   - [Enfoque Modular con Archivos en `locales/`](#42-enfoque-modular-con-archivos-en-locales)
5. [Hardware Físico Real 1: Arduino / ESP32 (Pedales, Volantes y Freno de Mano)](#5-hardware-físico-real-1-arduino--esp32-pedales-volantes-y-freno-de-mano)
   - [Circuito y Conexión de Pines](#51-circuito-y-conexión-de-pines)
   - [Firmware Arduino C++ Completo (`pedals_firmware.ino`)](#52-firmware-arduino-c-completo-pedals_firmwareino)
   - [Script del Plugin en Python (`main.py`)](#53-script-del-plugin-en-python-mainpy)
6. [Hardware Físico Real 2: Sintetizadores, Pianos y Pads MIDI](#6-hardware-físico-real-2-sintetizadores-pianos-y-pads-midi)
   - [Filtrado de Puertos en Windows (Entrada vs Salida)](#61-filtrado-de-puertos-en-windows-entrada-vs-salida)
   - [Lectura en Tiempo Real con `pygame.midi`](#62-lectura-en-tiempo-real-con-pygamemidi)
   - [Mapeo de Pitch Bend, Modulación y Teclas a Controles de Xbox](#63-mapeo-de-pitch-bend-modulación-y-teclas-a-controles-de-xbox)
7. [Referencia Completa del SDK de Python (`PluginDevice`)](#7-referencia-completa-del-sdk-de-python-plugindevice)
   - [Controles Semánticos vs Indexados](#71-controles-semánticos-vs-indexados)
   - [Vibración Háptica / Force Feedback (Rumble)](#72-vibración-háptica--force-feedback-rumble)
   - [Sincronización Atómica y Telemetría](#73-sincronización-atómica-y-telemetría)
8. [Diagnóstico y Resolución de Problemas](#8-diagnóstico-y-resolución-de-problemas)

---

## 1. Arquitectura y Filosofía del Sistema

El motor de plugins de **j360More** fue diseñado bajo una premisa fundamental: **máxima estabilidad y cero impacto en la latencia de juego**.

### 1.1. Aislamiento por Procesos Secundarios e IPC

Tradicionalmente, cargar scripts de terceros en el mismo hilo de ejecución de un emulador o interfaz de usuario conlleva el riesgo de que una lectura bloqueante (por ejemplo, esperar datos en un puerto serie COM o un timeout de socket) congele los controles de todos los jugadores o provoque micro-tirones (*stuttering*).

En j360More:
1. Cada plugin activo se ejecuta en su propio proceso hijo (`subprocess.Popen`) utilizando el intérprete de Python del entorno virtual.
2. La comunicación entre el proceso central de j360More y los plugins se realiza a través de un canal IPC ultraligero mediante sockets TCP en la interfaz local (`127.0.0.1`) con tramas atómicas JSON.
3. El bucle de despacho de mandos virtuales a **120 Hz** lee el estado de memoria compartido en microsegundos, asegurando que un retardo físico en el hardware jamás degrade el rendimiento de los demás mandos.

```
┌────────────────────────────────────────────────────────┐
│               j360More Core (120 Hz)                   │
│   - Dispatcher ViGEmBus / VIIPER                       │
│   - GUI Tkinter con Monitor de Telemetría (~33 FPS)    │
│   - Servidor TCP IPC Local (127.0.0.1:PuertoAsignado)  │
└──────────────────────────┬─────────────────────────────┘
                           │ Socket TCP JSON
        ┌──────────────────┴──────────────────┐
        ▼                                     ▼
┌───────────────────────────┐     ┌───────────────────────────┐
│ Plugin 1 (Proceso Hijo)   │     │ Plugin 2 (Proceso Hijo)   │
│ - Arduino Pedals          │     │ - USB-MIDI Controller     │
│ - pyserial @ 115200 baud  │     │ - pygame.midi @ 120 Hz    │
└───────────────────────────┘     └───────────────────────────┘
```

### 1.2. Entorno Virtual Automático (`.venv`)

Para que el usuario final no necesite instalar Python globalmente ni configurar variables de entorno complejas:
- Al abrir la pestaña `🔌 Plugins`, el emulador verifica la presencia de la carpeta `plugins/.venv`.
- Si no existe o le faltan dependencias, la interfaz muestra un aviso descriptivo y un botón de un clic: **"Instalar Dependencias de Plugins"**.
- Las dependencias se instalan de forma aislada sin afectar ninguna otra aplicación del sistema operativo.
- Para periféricos MIDI se utiliza `pygame-ce` en lugar de librerías con dependencias C++ nativas no compiladas, garantizando una instalación transparente en cualquier versión de Windows 10 u 11.

---

## 2. Anatomía y Creación de un Plugin desde Cero

### 2.1. Estructura de Archivos

Cada plugin reside en una carpeta independiente dentro del directorio `plugins/`:

```
plugins/
└── mi_dispositivo/
    ├── plugin.json         # Metadatos, esquema de UI declarativa y opciones
    ├── main.py             # Script ejecutable principal del plugin
    ├── requirements.txt    # Librerías Python requeridas de PyPI
    └── locales/            # (Opcional) Archivos de traducción externa
        ├── en.json
        └── es.json
```

### 2.2. El Manifiesto (`plugin.json`)

El archivo `plugin.json` describe el plugin, sus dispositivos provistos y las opciones configurables por el usuario. Un manifiesto básico se ve así:

```json
{
  "id": "mi_dispositivo",
  "name": "Mi Dispositivo Personalizado",
  "version": "1.0.0",
  "author": "Tu Nombre",
  "description": "Controlador físico personalizado para j360More",
  "entry_point": "main.py",
  "devices": [
    {
      "id": "mando_custom",
      "name": "Mando Personalizado",
      "type": "gamepad",
      "num_buttons": 16,
      "num_axes": 6
    }
  ]
}
```

Una vez creado, j360More lo registrará como fuente de entrada con el identificador:
`plugin:mi_dispositivo:mando_custom`

### 2.3. Ciclo de Vida de Ejecución

1. **Descubrimiento**: Al iniciar la aplicación, `PluginManager` escanea `plugins/*/plugin.json`.
2. **Arranque**: Cuando el usuario pulsa "Iniciar Emulación" (o activa el plugin manualmente), se ejecuta `main.py --port <TCP_PORT> --id <PLUGIN_ID>`.
3. **Handshake IPC**: El script se conecta al puerto TCP mediante `PluginDevice` y se identifica.
4. **Bucle de Mapeo**: El script lee el hardware a alta velocidad y llama a `device.flush()`.
5. **Cierre Limpio**: Cuando la emulación se detiene, `device.is_running()` pasa a `False`; el script debe liberar puertos serie o conexiones MIDI antes de terminar.

---

## 3. Creación de Interfaces Declarativas Personalizadas (UI)

Una de las grandes ventajas de j360More es que **no necesitas escribir código de GUI (Tkinter, PyQt, etc.)** para darle al usuario una experiencia de configuración completa. Todo se declara en el archivo `plugin.json`.

### 3.1. Diálogo Global de Configuración (`global_ui`)

Cuando el usuario hace clic en el botón `⚙ Configurar` en la lista de plugins, se abre un diálogo modal generado automáticamente a partir de la clave `"global_ui"`.

Admite los siguientes tipos de control:
- **`slider`**: Rango numérico con `min`, `max`, `step` y `default`.
- **`checkbox`**: Valor booleano (`true`/`false`).
- **`dropdown`**: Menú desplegable con lista fija de opciones.
- **`dynamic_dropdown`**: Menú desplegable con botón de refresco `🔄` que consulta al plugin en vivo.

Ejemplo en `plugin.json`:

```json
"global_ui": {
  "title": { "es": "Ajustes de Mi Dispositivo", "en": "My Device Settings" },
  "fields": [
    {
      "id": "serial_baud",
      "label": { "es": "Velocidad de Baudios", "en": "Baud Rate" },
      "type": "dropdown",
      "options": ["9600", "57600", "115200"],
      "default": "115200"
    },
    {
      "id": "invert_axes",
      "label": { "es": "Invertir Ejes Analógicos", "en": "Invert Analog Axes" },
      "type": "checkbox",
      "default": false
    }
  ]
}
```

### 3.2. Menús Desplegables Dinámicos con Escaneo en Vivo

Para permitir al usuario seleccionar puertos COM o interfaces MIDI sin tener que reiniciar la app:

```json
{
  "id": "port",
  "label": { "es": "Puerto Serie COM", "en": "Serial COM Port" },
  "type": "dynamic_dropdown",
  "discovery_action": "scan_ports",
  "default": "Auto"
}
```

En tu script `main.py`, registra la acción para responder dinámicamente:

```python
def handle_scan_ports(params):
    import serial.tools.list_ports
    ports = ["Auto"] + [p.device for p in serial.tools.list_ports.comports()]
    return {"options": ports}

device.on_action("scan_ports", handle_scan_ports)
```

### 3.3. Pestañas Personalizadas por Mando (`pad_ui_customization`)

Si tu plugin provee una experiencia especializada (por ejemplo, una pedalera que no tiene sticks analógicos o un volante con calibración de giro), puedes inyectar pestañas dentro del panel del mando seleccionado:

```json
"pad_ui_customization": {
  "disable_default_tabs": ["sticks"],
  "custom_tabs": [
    {
      "id": "pedals_calibration",
      "title": { "es": "🏎️ Pedales", "en": "🏎️ Pedals" },
      "sections": [
        {
          "title": { "es": "Calibración de Recorrido", "en": "Travel Calibration" },
          "fields": [
            {
              "id": "deadzone_gas",
              "label": { "es": "Zona Muerta Acelerador (%)", "en": "Gas Deadzone (%)" },
              "type": "slider",
              "min": 0,
              "max": 30,
              "step": 1,
              "default": 3
            }
          ]
        }
      ]
    }
  ]
}
```

### 3.4. Monitores de Telemetría Dinámicos (`progress_bar_multi`)

Para mostrar barras de progreso en tiempo real con feedback visual instantáneo:

```json
{
  "id": "pedals_monitor",
  "type": "progress_bar_multi",
  "label": { "es": "Monitor de Recorrido Físico", "en": "Physical Travel Monitor" },
  "bars": 3,
  "labels": ["GAS", "FRENO", "EMBRAGUE"],
  "center_zero": false
}
```

- `center_zero: false`: La barra crece de 0% a 100% (ideal para pedales y gatillos).
- `center_zero: true`: El punto neutro está centrado al 50% y la barra se expande hacia la izquierda o derecha (ideal para palancas de stick y ruedas de pitch bend).

En tu script Python, envía la telemetría regulando la tasa de envío a aproximadamente **33 FPS** (~30 milisegundos) para mantener la interfaz a 60 FPS sin sobrecargar el hilo de Tkinter:

```python
# Enviar telemetría cada 30 ms
now = time.perf_counter()
if now - last_telemetry >= 0.03:
    device.send_telemetry({
        "pedals_monitor": [gas_val, brake_val, clutch_val]
    }, pad_id=0)
    last_telemetry = now
```

---

## 4. Soporte Multi-Idioma (i18n)

El sistema de plugins incluye traducción automática integrada con el selector de idioma global de j360More (Español, Inglés, Francés, Portugués, Alemán, Italiano, Ruso).

### 4.1. Enfoque Inline en `plugin.json`

Puedes escribir las traducciones directamente como un diccionario clave-valor:

```json
"label": {
  "es": "Sensibilidad de Respuesta",
  "en": "Response Sensitivity",
  "fr": "Sensibilité de Réponse",
  "de": "Antwort-Empfindlichkeit"
}
```

Si el idioma seleccionado por el usuario no está disponible, el sistema recurrirá automáticamente al español (`es`) o al inglés (`en`).

### 4.2. Enfoque Modular con Archivos en `locales/`

Para plugins extensos, crea archivos JSON en `locales/`:

`plugins/mi_dispositivo/locales/es.json`:
```json
{
  "tab_title": "🏎️ Calibración",
  "sec_calibration": "Ajuste de Recorrido",
  "lbl_deadzone": "Zona Muerta (%)"
}
```

`plugins/mi_dispositivo/locales/en.json`:
```json
{
  "tab_title": "🏎️ Calibration",
  "sec_calibration": "Travel Adjustment",
  "lbl_deadzone": "Deadzone (%)"
}
```

En `plugin.json` solo necesitas referenciar las claves:
```json
"title": "tab_title",
"label": "lbl_deadzone"
```

---

## 5. Hardware Físico Real 1: Arduino / ESP32 (Pedales, Volantes y Freno de Mano)

A continuación se detalla cómo crear un periférico físico real conectando potenciómetros a un microcontrolador y programando el firmware en Arduino IDE.

### 5.1. Circuito y Conexión de Pines

Conecta tres potenciómetros rotativos o deslizantes de **10 kΩ** (lineales recomendados):

```
Arduino Nano / Uno / ESP32:
              ┌───────────────────────────┐
              │ 5V / 3.3V ───► Terminal 1 │
              │ GND       ───► Terminal 3 │
              │                           │
  Acelerador  │ A0        ───► Terminal 2 (Pin central / Señal)
  Freno       │ A1        ───► Terminal 2 (Pin central / Señal)
  Embrague    │ A2        ───► Terminal 2 (Pin central / Señal)
              │                           │
  Botón 1     │ D2        ───► Pulsador hacia GND (INPUT_PULLUP)
  Botón 2     │ D3        ───► Pulsador hacia GND (INPUT_PULLUP)
              └───────────────────────────┘
```

### 5.2. Firmware Arduino C++ Completo (`pedals_firmware.ino`)

Copia y pega este código en **Arduino IDE** y súbelo a tu placa (funciona en Arduino Nano, Uno, Leonardo, Pro Micro y ESP32):

```cpp
/*
 * j360More - Firmware para Pedales y Volantes Físicos USB
 * Velocidad Serial: 115200 baudios (Latencia < 2ms)
 */

const int PIN_GAS   = A0;
const int PIN_BRAKE = A1;
const int PIN_CLUTCH= A2;
const int PIN_BTN1  = 2;
const int PIN_BTN2  = 3;

// Filtro digital pasa-bajos exponencial para eliminar ruido eléctrico (jitter)
float smoothGas    = 0.0;
float smoothBrake  = 0.0;
float smoothClutch = 0.0;
const float ALPHA  = 0.25; // Factor de suavizado (0.1 = suave, 0.9 = reactivo)

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000); // Espera activa segura

  pinMode(PIN_BTN1, INPUT_PULLUP);
  pinMode(PIN_BTN2, INPUT_PULLUP);

  // Inicializar lecturas base
  smoothGas    = analogRead(PIN_GAS);
  smoothBrake  = analogRead(PIN_BRAKE);
  smoothClutch = analogRead(PIN_CLUTCH);
}

void loop() {
  // 1. Lectura analógica de 10 bits (0 - 1023)
  int rawGas    = analogRead(PIN_GAS);
  int rawBrake  = analogRead(PIN_BRAKE);
  int rawClutch = analogRead(PIN_CLUTCH);

  // 2. Aplicar filtro pasa-bajos
  smoothGas    = (ALPHA * rawGas)    + ((1.0 - ALPHA) * smoothGas);
  smoothBrake  = (ALPHA * rawBrake)  + ((1.0 - ALPHA) * smoothBrake);
  smoothClutch = (ALPHA * rawClutch) + ((1.0 - ALPHA) * smoothClutch);

  // 3. Lectura de pulsadores digitales (lógica invertida por PULLUP)
  int btn1 = (digitalRead(PIN_BTN1) == LOW) ? 1 : 0;
  int btn2 = (digitalRead(PIN_BTN2) == LOW) ? 1 : 0;

  // 4. Enviar trama compacta optimizada por puerto serie
  // Formato: GAS:val,BRK:val,CLT:val,BTN1:val,BTN2:val\n
  Serial.print("GAS:");
  Serial.print((int)smoothGas);
  Serial.print(",BRK:");
  Serial.print((int)smoothBrake);
  Serial.print(",CLT:");
  Serial.print((int)smoothClutch);
  Serial.print(",BTN1:");
  Serial.print(btn1);
  Serial.print(",BTN2:");
  Serial.println(btn2);

  // Intervalo de despacho a ~100 Hz (10 ms)
  delay(10);
}
```

### 5.3. Script del Plugin en Python (`main.py`)

Crea `plugins/arduino_pedals/main.py`:

```python
import sys
import time
import serial
import serial.tools.list_ports
from plugins.plugin_sdk import PluginDevice

# Inicializar dispositivo con 2 ejes analógicos (Gatillos LT/RT) y 2 botones
device = PluginDevice(
    id="arduino_pedals",
    name="Arduino Pedals Controller",
    num_buttons=2,
    num_axes=2
)

active_port = "Auto"
baud_rate = 115200
ser = None

def get_best_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = p.description.lower()
        if "arduino" in desc or "ch340" in desc or "cp210" in desc:
            return p.device
    return ports[0].device if ports else None

def map_axis(val, min_in=50, max_in=950):
    """Mapea valores de 0-1023 a 0.0 - 1.0 con zona muerta"""
    clamped = max(min_in, min(max_in, val))
    return (clamped - min_in) / float(max_in - min_in)

last_telemetry = 0.0

try:
    while device.is_running():
        # Reconexión automática si el cable USB se desconecta
        if ser is None or not ser.is_open:
            port_to_open = get_best_port() if active_port == "Auto" else active_port
            if port_to_open:
                try:
                    ser = serial.Serial(port_to_open, baud_rate, timeout=0.02)
                    time.sleep(0.5) # Estabilización serial
                except Exception:
                    ser = None
                    time.sleep(1.0)
                    continue
            else:
                time.sleep(1.0)
                continue

        try:
            line = ser.readline().decode("ascii", errors="ignore").strip()
            if line:
                data = dict(item.split(":") for item in line.split(",") if ":" in item)
                
                gas_raw = int(data.get("GAS", 0))
                brake_raw = int(data.get("BRK", 0))
                clutch_raw = int(data.get("CLT", 0))
                btn1 = int(data.get("BTN1", 0)) == 1
                btn2 = int(data.get("BTN2", 0)) == 1

                gas_norm = map_axis(gas_raw)
                brake_norm = map_axis(brake_raw)

                # Mapeo semántico directo a gatillos del mando Xbox
                device.set_trigger("RT", gas_norm)    # Acelerador
                device.set_trigger("LT", brake_norm)  # Freno
                device.set_button("A", btn1)
                device.set_button("B", btn2)
                device.flush()

                # Telemetría a ~33 FPS para los monitores de la GUI
                now = time.perf_counter()
                if now - last_telemetry >= 0.03:
                    device.send_telemetry({
                        "pedals_monitor": [gas_norm, brake_norm, map_axis(clutch_raw)]
                    }, pad_id=0)
                    last_telemetry = now

        except serial.SerialException:
            ser = None # Forzar reconexión

        time.sleep(0.005) # 200 Hz loop
finally:
    if ser and ser.is_open:
        ser.close()
```

---

## 6. Hardware Físico Real 2: Sintetizadores, Pianos y Pads MIDI

Cualquier teclado musical USB, interfaz MIDI DIN-5 o controlador de pads tipo Launchpad puede utilizarse como mando para jugar.

### 6.1. Filtrado de Puertos en Windows (Entrada vs Salida)

En Windows, el subsistema MIDI enumera puertos que **no son dispositivos de entrada** (como `Microsoft GS Wavetable Synth` o puertos virtuales solo-salida). Si intentas abrir un puerto de solo-salida en modo lectura, el programa fallará con error de descriptor.

El código debe filtrar siempre `is_input == 1`:

```python
import pygame.midi

pygame.midi.init()
input_devices = []
for dev_id in range(pygame.midi.get_count()):
    interf, name, is_input, is_output, opened = pygame.midi.get_device_info(dev_id)
    if is_input == 1:
        dev_name = name.decode("utf-8", errors="ignore")
        input_devices.append((dev_id, dev_name))
```

### 6.2. Lectura en Tiempo Real con `pygame.midi`

`pygame.midi` proporciona acceso directo de latencia ultrabaja a través de la API multimedia de Windows sin requerir drivers privativos:

```python
midi_in = pygame.midi.Input(target_device_id)

while device.is_running():
    if midi_in.poll():
        # Leer hasta 16 eventos MIDI disponibles de forma no bloqueante
        events = midi_in.read(16)
        for event in events:
            status = event[0][0]
            data1  = event[0][1] # Nota o número de CC
            data2  = event[0][2] # Velocidad o valor de CC
            ...
```

### 6.3. Mapeo de Pitch Bend, Modulación y Teclas a Controles de Xbox

Los mensajes MIDI estándar se traducen directamente a controles de mando:

| Mensaje MIDI | Byte de Estado | Interpretación | Mapeo Recomendado en Xbox 360 |
| :--- | :--- | :--- | :--- |
| **Note On** | `0x90` | Tecla/Pad presionado (`velocity > 0`) | Botones `A`, `B`, `X`, `Y`, `LB`, `RB` o D-Pad |
| **Note Off** | `0x80` (o `0x90` con vel 0) | Tecla/Pad liberado | Liberar botón correspondiente |
| **Pitch Bend** | `0xE0` | Rueda de tono (14 bits: 0 a 16383, centro 8192) | Stick izquierdo horizontal (`LX`: -1.0 a +1.0) |
| **Modulation Wheel** | `0xB0` (CC #1) | Rueda de modulación (0 a 127) | Gatillo derecho (`RT`: 0.0 a 1.0) |

Código de mapeo:

```python
# Mapeo de Rueda de Pitch Bend (14-bit) al Stick Izquierdo LX (-1.0 a +1.0)
if status == 0xE0:
    # data1 = 7 bits menos significativos (LSB), data2 = 7 bits más significativos (MSB)
    pitch_14bit = (data2 << 7) | data1
    # 8192 es la posición neutra centrada
    normalized_stick = (pitch_14bit - 8192) / 8192.0
    device.set_stick("LX", max(-1.0, min(1.0, normalized_stick)))
    device.flush()

# Mapeo de Rueda de Modulación (CC 1) al Gatillo Derecho RT (0.0 a 1.0)
elif status == 0xB0 and data1 == 1:
    normalized_trigger = data2 / 127.0
    device.set_trigger("RT", normalized_trigger)
    device.flush()

# Mapeo de Tecla a Botón (ejemplo: Nota 60 = Do central -> Botón A)
elif (status & 0xF0) == 0x90:
    is_pressed = (data2 > 0)
    if data1 == 60:
        device.set_button("A", is_pressed)
    elif data1 == 62:
        device.set_button("B", is_pressed)
    device.flush()
```

---

## 7. Referencia Completa del SDK de Python (`PluginDevice`)

El SDK provisto en `plugins/plugin_sdk.py` encapsula toda la complejidad de comunicación IPC.

### 7.1. Controles Semánticos vs Indexados

Puedes alimentar controles utilizando nombres semánticos de Xbox o mediante índices directos:

#### Controles Semánticos (Recomendado):
- `device.set_button(name: str, pressed: bool)`: Nombres admitidos: `"A"`, `"B"`, `"X"`, `"Y"`, `"LB"`, `"RB"`, `"BACK"`, `"START"`, `"GUIDE"`, `"L3"`, `"R3"`, `"DPAD_UP"`, `"DPAD_DOWN"`, `"DPAD_LEFT"`, `"DPAD_RIGHT"`.
- `device.set_trigger(name: str, value: float)`: `"LT"`, `"RT"`. Rango: `0.0` a `1.0`.
- `device.set_stick(name: str, value: float)`: `"LX"`, `"LY"`, `"RX"`, `"RY"`. Rango: `-1.0` a `1.0`.

#### Controles Físicos Indexados:
- `device.set_button_index(index: int, pressed: bool)`: Asigna el botón físico `0..N`.
- `device.set_axis(index: int, value: float)`: Asigna el eje analógico `0..M` (`-1.0` a `1.0`).

### 7.2. Vibración Háptica / Force Feedback (Rumble)

El emulador reenvía las órdenes de vibración de los juegos (XInput Rumble) a los plugins en tiempo real:

```python
def on_rumble_received(small_motor: float, large_motor: float):
    # small_motor (alta frecuencia): 0.0 a 1.0
    # large_motor (baja frecuencia): 0.0 a 1.0
    if ser and ser.is_open:
        cmd = f"RUMBLE:{int(large_motor * 255)},{int(small_motor * 255)}\n"
        ser.write(cmd.encode("ascii"))

device.on_rumble(on_rumble_received)
```

### 7.3. Sincronización Atómica y Telemetría

- **`device.flush()`**: Envía todas las modificaciones de botones y ejes acumuladas en un único paquete atómico TCP. Debe llamarse al final de cada iteración de lectura para evitar lecturas intermedias incompletas.
- **`device.send_telemetry(payload: dict, pad_id: int = 0)`**: Envía variables en tiempo real a los monitores de la GUI.
- **`device.on_field_change(callback)`**: Permite escuchar cambios en tiempo real cuando el usuario mueve un slider o cambia un checkbox en la interfaz de configuración sin necesidad de reiniciar el plugin.

---

## 8. Diagnóstico y Resolución de Problemas

### La Consola de Plugins Integrada
En la pestaña `🔌 Plugins`, j360More incluye una **Consola de Depuración en Tiempo Real**. Todos los `print(...)` de tu script `main.py` o errores de excepciones se reflejan de inmediato en esa ventana, facilitando la depuración interactiva.

### Problemas Frecuentes y Soluciones:
1. **Error: `PermissionError: [Errno 13] could not open port 'COMx'`**:
   - *Causa*: Otro programa tiene el puerto abierto (típicamente el **Monitor Serie de Arduino IDE** o Cura/PrusaSlicer).
   - *Solución*: Cierra el Monitor Serie de Arduino IDE para permitir que j360More abra el puerto.
2. **El Monitor de Telemetría no se mueve**:
   - Verifica que el identificador enviado en `device.send_telemetry({"mi_monitor": [...]})` coincida exactamente con el `id` declarado en `plugin.json`.
   - Asegúrate de llamar a `send_telemetry` con valores numéricos flotantes entre `0.0` y `1.0`.
3. **El dispositivo MIDI no aparece en la lista**:
   - Presiona el botón de refresco `🔄` al lado del menú desplegable.
   - En Windows, desconectar y reconectar el cable USB actualiza los identificadores de dispositivo.
4. **Desarrollo sin hardware físico conectado**:
   - Puedes activar un modo simulador agregando una opción `"simulate": true` en `global_ui`. En `main.py`, si la opción está activa, genera señales senoidales o aleatorias con `math.sin(time.time())` para verificar el correcto funcionamiento del plugin antes de conectar el circuito real.

---

¡Felicidades! Ahora cuentas con todos los conocimientos técnicos necesarios para construir cualquier periférico de control físico o integrar instrumentos y dispositivos a medida con **j360More**.
