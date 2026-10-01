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
   - [Control de Inicio Automático (Activar / Desactivar al Iniciar)](#24-control-de-inicio-automático-activar--desactivar-al-iniciar)
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
7. [Referencia Completa del SDK de Python (`PluginDevice`)](#7-referencia-completa-y-detallada-del-sdk-de-python-plugindevice)
   - [Inicialización y Estado de Conexión](#71-inicialización-y-ciclo-de-vida)
   - [Controles Semánticos vs Indexados](#72-controles-semánticos-de-xbox-recomendado)
   - [Sincronización Atómica y Telemetría](#74-sincronización-y-transmisión-de-estados)
   - [Decoradores de Eventos Bidireccionales](#75-decoradores-de-eventos-bidireccionales)
8. [Gestión de Conexión, Desconexión y Reconexión en Caliente (Hot-Plug)](#8-gestión-de-conexión-desconexión-y-reconexión-en-caliente-hot-plug)
   - [Los Dos Niveles de Enlace: IPC vs Hardware Físico](#81-los-dos-niveles-de-enlace-ipc-vs-hardware-físico)
   - [Prevención de Entradas Pegadas (Stuck Inputs) con `set_connected(False)`](#82-prevención-de-entradas-pegadas-stuck-inputs-y-reset_inputs)
   - [Patrón de Reconexión Automática sin Bloqueos](#83-patrón-de-reconexión-automática-sin-bloqueos)
   - [Notificación Dinámica de Periféricos con `report_devices()`](#84-notificación-dinámica-de-periféricos-con-report_devices)
9. [Diagnóstico y Resolución de Problemas](#9-diagnóstico-y-resolución-de-problemas)

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

### 2.4. Control de Inicio Automático (Activar / Desactivar al Iniciar)

En j360More puedes controlar con precisión qué plugins arrancan automáticamente cuando se abre la aplicación y cuáles permanecen en reposo hasta que decidas iniciarlos manualmente:

#### A. Desde la Interfaz Gráfica (GUI)
1. Ve a la pestaña **`🔌 Plugins`** en la ventana de Ajustes de j360More.
2. En la tabla de plugins verás la columna **`Inicio`**, que indica si el plugin tiene el arranque automático activado (`✔ Activado`) o desactivado (`✖ Desactivado`).
3. Selecciona cualquier plugin de la lista y presiona el botón **`✔ Activar al Inicio`** / **`✖ Desactivar al Inicio`**.
4. La preferencia se guarda de inmediato en el archivo `config.json` del plugin (`"enabled": false`), asegurando que al cerrar y reabrir j360More, el plugin no se inicie solo.

#### B. Desde el Manifiesto (`plugin.json`)
Puedes definir el comportamiento por defecto de fábrica en `plugin.json` mediante la clave `"autostart"`:

```json
{
  "id": "mi_dispositivo",
  "name": "Mi Dispositivo Personalizado",
  "autostart": false,
  "entry_point": "main.py"
}
```
- Si `"autostart": false`: El plugin nunca arrancará solo al abrir la aplicación a menos que el usuario lo active manualmente en la interfaz o lo inicie con `▶ Iniciar`.
- Si `"autostart": true` (o se omite): Arrancará automáticamente con la aplicación (a menos que el usuario lo desactive en la GUI).

#### C. Control Programático en Python
Desde el gestor central (`PluginManager`):
```python
# Desactivar plugin para que no inicie con la app
pm.set_plugin_enabled("arduino_pedals", False)

# Comprobar si está activado
if pm.is_plugin_enabled("arduino_pedals"):
    print("El plugin arrancará al iniciar la app")
```

---

## 3. Creación de Interfaces Declarativas Personalizadas (UI)

Una de las mayores virtudes arquitectónicas de j360More es que **no necesitas escribir código de interfaz gráfica (Tkinter, PyQt, etc.)** para ofrecer una experiencia de usuario nativa y profesional. Todo el árbol de controles se declara en el archivo `plugin.json` mediante esquemas JSON estandarizados.

El motor de interfaz (`plugins/plugin_ui_renderer.py`) interpreta este manifiesto y construye dinámicamente los controles en la GUI, sincronizando cambios bidireccionalmente con tu proceso de Python.

---

### 3.1. Catálogo Completo de Controles Admitidos

A continuación se detalla cada control disponible, las propiedades que admite, cómo se renderiza en la GUI y cómo se captura su valor en el script de Python:

#### 1. Deslizador Numérico (`slider`)
- **Descripción**: Barra deslizante analógica continua o discreta (`ttk.Scale`), que incluye una etiqueta a la derecha con el valor numérico entero en tiempo real.
- **Propiedades JSON**:
  - `id` *(string, obligatorio)*: Clave identificadora única.
  - `label` *(string o dict i18n)*: Texto visible para el usuario.
  - `min` *(numérico, por defecto 0)*: Valor mínimo del rango.
  - `max` *(numérico, por defecto 100)*: Valor máximo del rango.
  - `default` *(numérico, obligatorio)*: Valor inicial.
  - `step` *(numérico, opcional)*: Incremento del ajuste.
- **Ejemplo JSON**:
  ```json
  {
    "id": "gas_deadzone",
    "label": { "es": "Zona Muerta Acelerador (%)", "en": "Gas Deadzone (%)" },
    "type": "slider",
    "min": 0,
    "max": 40,
    "default": 5
  }
  ```
- **Captura en Python**:
  ```python
  @device.on_field_change("gas_deadzone")
  def on_gas_deadzone_changed(new_val, pad_id):
      print(f"Zona muerta actualizada para el mando {pad_id}: {new_val}%")
  ```

---

#### 2. Interruptor Booleano (`checkbox`)
- **Descripción**: Casilla de verificación estándar (`ttk.Checkbutton`) para alternar modos o activar opciones.
- **Propiedades JSON**:
  - `id` *(string, obligatorio)*: Identificador del campo.
  - `label` *(string o dict i18n)*: Texto explicativo de la opción.
  - `default` *(boolean, por defecto `false`)*: Estado inicial (`true` o `false`).
- **Ejemplo JSON**:
  ```json
  {
    "id": "invert_brake",
    "label": { "es": "Invertir Polaridad del Freno", "en": "Invert Brake Polarity" },
    "type": "checkbox",
    "default": false
  }
  ```
- **Captura en Python**:
  ```python
  @device.on_field_change("invert_brake")
  def on_invert_brake_changed(is_inverted: bool, pad_id: int):
      print(f"Polaridad de freno invertida: {is_inverted}")
  ```

---

#### 3. Menú Desplegable Estático (`dropdown`)
- **Descripción**: Selector de opciones de solo lectura (`ttk.Combobox`) con una lista fija de valores o pares valor/etiqueta.
- **Propiedades JSON**:
  - `id` *(string, obligatorio)*: Identificador.
  - `label` *(string o dict i18n)*: Título del menú.
  - `options` *(lista de strings o dicts)*: Valores seleccionables.
  - `default` *(string)*: Opción seleccionada por defecto.
- **Ejemplo JSON**:
  ```json
  {
    "id": "baud_rate",
    "label": { "es": "Velocidad Serial (Baudios)", "en": "Serial Baud Rate" },
    "type": "dropdown",
    "options": ["9600", "57600", "115200"],
    "default": "115200"
  }
  ```
- **Captura en Python**:
  ```python
  @device.on_field_change("baud_rate")
  def on_baud_changed(new_baud_str: str, pad_id: int):
      baud_int = int(new_baud_str)
  ```

---

#### 4. Menú Desplegable Dinámico con Escaneo en Vivo (`dynamic_dropdown`)
- **Descripción**: Menú desplegable que incorpora un botón interactivo `🔄` a su derecha. Al hacer clic, consulta a tu plugin para redescubrir dispositivos físicos conectados en caliente (puertos COM serie, periféricos MIDI USB, etc.) y actualiza la lista sin reiniciar la aplicación.
- **Propiedades JSON**:
  - `id` *(string, obligatorio)*: Identificador.
  - `label` *(string o dict i18n)*: Título del menú.
  - `options` *(lista inicial)*: Opciones de arranque (ej: `["AUTO"]`).
  - `discovery_action` *(string, obligatorio)*: Nombre de la acción que se dispara en Python al pulsar `🔄`.
  - `default` *(string)*: Opción predeterminada.
- **Ejemplo JSON**:
  ```json
  {
    "id": "midi_port",
    "label": { "es": "Puerto MIDI Físico", "en": "Physical MIDI Port" },
    "type": "dynamic_dropdown",
    "discovery_action": "scan_midi_ports",
    "options": ["AUTO"],
    "default": "AUTO"
  }
  ```
- **Captura y Respuesta en Python**:
  ```python
  @device.on_action("scan_midi_ports")
  def handle_scan_ports(pad_id: int):
      import pygame.midi
      if not pygame.midi.get_init():
          pygame.midi.init()
      
      found_ports = ["AUTO"]
      for i in range(pygame.midi.get_count()):
          info = pygame.midi.get_device_info(i)
          if info and info[2]:  # Solo puertos de entrada física
              found_ports.append(f"{i}: {info[1].decode('utf-8')}")
      
      # Actualizar opciones del combobox en la GUI en vivo
      device.update_field_options("midi_port", found_ports)
      device.log(f"Puertos detectados: {found_ports}")
  ```

---

#### 5. Botón de Acción (`button`)
- **Descripción**: Botón estándar (`ttk.Button`) que invoca una función del plugin al hacer clic (ej. calibrar centro en cero, reiniciar hardware, enviar reset).
- **Propiedades JSON**:
  - `id` *(string, obligatorio)*: Identificador.
  - `label` *(string o dict i18n)*: Texto visible en el botón.
  - `action` *(string, opcional, por defecto el `id`)*: Nombre de la acción a disparar.
- **Ejemplo JSON**:
  ```json
  {
    "id": "btn_calibrate_zero",
    "label": { "es": "Calibrar Centro en Cero", "en": "Calibrate Center Zero" },
    "type": "button",
    "action": "calibrate_zero"
  }
  ```
- **Manejo en Python**:
  ```python
  @device.on_action("calibrate_zero")
  def handle_calibrate_zero(pad_id: int):
      # Calibrar volante o joystick
      device.log(f"Centro calibrado exitosamente para mando {pad_id}")
  ```

---

#### 6. Monitores de Telemetría Dinámicos (`progress_bar_multi` y `progress_bar_pair`)
- **Descripción**: Monitor visual interactivo renderizado sobre un lienzo `tk.Canvas` con temática oscura. Dibuja barras con código de colores independientes (`#107C41` verde, `#0078D7` azul, `#FFB900` ámbar, etc.), texto con porcentaje dinámico en vivo (`0%` a `100%`) y nombres de canal personalizados.
- **Propiedades JSON**:
  - `id` *(string, obligatorio)*: Identificador del monitor (se utiliza como clave en `device.send_telemetry`).
  - `label` *(string o dict i18n)*: Título del recuadro del monitor.
  - `bars` *(número entero)*: Cantidad de barras a dibujar (ej. 2 o 3).
  - `labels` *(lista de strings)*: Nombres individuales de cada barra (ej. `["GAS", "FRENO", "EMBRAGUE"]`).
  - `center_zero` *(boolean)*: `false` para crecer de 0% a 100%; `true` para centrado neutro en 50% con expansión bidireccional.
- **Ejemplo JSON**:
  ```json
  {
    "id": "pedals_monitor",
    "type": "progress_bar_multi",
    "label": { "es": "Recorrido Físico de Pedales", "en": "Pedals Physical Travel" },
    "bars": 3,
    "labels": ["GAS", "FRENO", "CLUTCH"],
    "center_zero": false
  }
  ```
- **Alimentación en Tiempo Real desde Python**:
  ```python
  # Enviar valores flotantes normalizados de 0.0 a 1.0 cada ~33 ms (30 FPS)
  now = time.perf_counter()
  if now - last_telemetry >= 0.03:
      device.send_telemetry({
          "pedals_monitor": [gas_val, brake_val, clutch_val]
      }, pad_id=1)
      last_telemetry = now
  ```

---

### 3.2. Contenedores de Diseño: `global_ui` vs `pad_ui_customization`

El sistema provee dos ubicaciones estratégicas para renderizar tu interfaz:

#### A. Diálogo de Configuración Global (`global_ui`)
Se define en la raíz de `plugin.json` y se abre cuando el usuario presiona el botón **`⚙ Configurar`** en la lista de plugins. Es ideal para parámetros del puerto COM, selección de periféricos físicos, velocidades de baudios y opciones que afectan a todo el plugin.

#### B. Pestañas Personalizadas por Mando (`pad_ui_customization`)
Permite insertar pestañas especializadas dentro del panel de cada mando emulado (Mando 1, Mando 2, etc.):
- **`disable_default_tabs`**: Array de strings con los identificadores exactos de las sub-pestañas nativas que deseas ocultar porque no aplican a tu hardware físico.
  
  **Valores válidos permitidos (nombres exactos):**
  | Identificador String | Sub-pestaña Nativa Ocultada | Cuándo utilizarlo / Casos de uso |
  | :--- | :--- | :--- |
  | **`"sticks"`** | **Sticks / Palancas Analógicas** (Calibración de sticks izquierdo LX/LY y derecho RX/RY, zonas muertas y curvas) | Dispositivos sin joysticks analógicos como **pedaleras de carreras**, volantes puros, guitarras o botoneras arcade. |
  | **`"triggers"`** | **Gatillos / Triggers** (Calibración analógica de recorrido, umbrales y zonas muertas de gatillos traseros LT y RT) | Controles sin gatillos analógicos, como joysticks de aviación clásicos, palancas de lucha retro o teclados simples. |
  | **`"rumble"`** | **Vibración / Force Feedback** (Ajuste de intensidad y prueba de motores hápticos de alta y baja frecuencia) | Periféricos que no disponen de motores físicos de vibración excéntrica o actuadores hápticos. |
  | **`"general"`** | **General / Mapeo de Botones** (Asignación de botones A, B, X, Y, LB, RB, D-Pad, Start, Back, Guide) | Periféricos dedicados que reemplazan todo el mapeo estándar por su propia interfaz de calibración personalizada. |

  *Ejemplos de combinación:*
  ```json
  // Para una pedalera de carreras (solo usa pedales analógicos mapeados a LT/RT):
  "disable_default_tabs": ["sticks", "rumble"]

  // Para una botonera arcade / Fight stick 100% digital:
  "disable_default_tabs": ["triggers", "sticks"]

  // Para un teclado musical o sintetizador MIDI:
  "disable_default_tabs": ["sticks", "rumble"]
  ```

- **`custom_tabs`**: Array de pestañas personalizadas con:
  - `id`: Identificador único de la pestaña.
  - `title`: Título visible en la interfaz (soporta emojis y diccionarios i18n).
  - `sections`: Array de recuadros de agrupación lógica (`ttk.LabelFrame`) con `title` y `fields`.

---

### 3.3. Ejemplo Completo Verificado de `plugin.json` con Todos los Controles

```json
{
  "id": "pedales_pro",
  "name": "Pedales de Carreras Pro USB",
  "version": "1.0.0",
  "author": "Tu Nombre",
  "entry_point": "main.py",
  "devices": [
    {
      "id": "pedals",
      "name": "Pedalera Analógica",
      "type": "gamepad",
      "num_buttons": 4,
      "num_axes": 3
    }
  ],
  "global_ui": {
    "title": { "es": "Ajustes de Conexión Serial", "en": "Serial Connection Settings" },
    "fields": [
      {
        "id": "port",
        "label": { "es": "Puerto COM Arduino", "en": "Arduino COM Port" },
        "type": "dynamic_dropdown",
        "discovery_action": "scan_ports",
        "options": ["AUTO"],
        "default": "AUTO"
      },
      {
        "id": "baud",
        "label": { "es": "Velocidad de Baudios", "en": "Baud Rate" },
        "type": "dropdown",
        "options": ["9600", "57600", "115200"],
        "default": "115200"
      },
      {
        "id": "simulate",
        "label": { "es": "Modo Simulación (Sin Hardware)", "en": "Simulation Mode (No Hardware)" },
        "type": "checkbox",
        "default": false
      }
    ]
  },
  "pad_ui_customization": {
    "disable_default_tabs": ["sticks"],
    "custom_tabs": [
      {
        "id": "pedals_cal",
        "title": { "es": "🏎️ Pedales", "en": "🏎️ Pedals" },
        "sections": [
          {
            "title": { "es": "Ajuste de Recorrido", "en": "Travel Calibration" },
            "fields": [
              {
                "id": "deadzone_gas",
                "label": { "es": "Zona Muerta Gas (%)", "en": "Gas Deadzone (%)" },
                "type": "slider",
                "min": 0,
                "max": 30,
                "default": 3
              },
              {
                "id": "invert_pedals",
                "label": { "es": "Invertir Dirección de Ejes", "en": "Invert Axis Direction" },
                "type": "checkbox",
                "default": false
              },
              {
                "id": "btn_reset_cal",
                "label": { "es": "Restablecer a Fábrica", "en": "Reset to Defaults" },
                "type": "button",
                "action": "reset_calibration"
              }
            ]
          },
          {
            "title": { "es": "Monitor en Vivo", "en": "Live Monitor" },
            "fields": [
              {
                "id": "pedals_telemetry",
                "type": "progress_bar_multi",
                "label": { "es": "Presión Física de Pedales", "en": "Pedals Physical Pressure" },
                "bars": 3,
                "labels": ["GAS", "FRENO", "EMBRAGUE"],
                "center_zero": false
              }
            ]
          }
        ]
      }
    ]
  }
}
```

---

## 4. Soporte Multi-Idioma (i18n)

El sistema de plugins cuenta con un motor de internacionalización nativo (`plugins/plugin_i18n.py`) completamente integrado con el selector de idioma global de j360More. Permite que tus diálogos de configuración, nombres de dispositivos, pestañas personalizadas, opciones de menús y monitores de telemetría se adapten al idioma del usuario sin requerir código complejo ni reiniciar el emulador.

---

### 4.1. Arquitectura y Códigos de Idioma Admitidos

El motor de traducción normaliza y soporta oficialmente los siguientes códigos de idioma:

| Código | Idioma | Nota de Normalización |
| :--- | :--- | :--- |
| **`"es"`** | **Español** | Idioma predeterminado del emulador. Utilizado como fallback base si falta una traducción. |
| **`"en"`** | **English** | Idioma internacional secundario de fallback. |
| **`"fr"`** | **Français** | Francés estándar. |
| **`"pt_BR"`** | **Português (Brasil)** | Se normaliza automáticamente si escribes `"pt"`, `"pt-br"`, `"pt_br"` o `"pt-BR"`. |
| **`"de"`** | **Deutsch** | Alemán estándar. |
| **`"it"`** | **Italiano** | Italiano estándar. |
| **`"ru"`** | **Русский** | Ruso (soporta caracteres cirílicos UTF-8 sin restricciones). |

#### Cascada de Respaldo Automática (Fallback Inteligente):
Si el usuario tiene j360More configurado en Alemán (`de`), pero tu plugin solo incluye Español e Inglés:
1. El motor busca la clave en el idioma seleccionado (`de`).
2. Si no existe, busca el idioma predeterminado del plugin (`default_lang`, por defecto `es`).
3. Si tampoco existe, recurre a `en` (Inglés).
4. Si ninguna coincide, muestra la primera traducción disponible o el nombre de la clave.
> **Garantía técnica**: La interfaz **nunca fallará ni lanzará excepciones** por falta de una traducción; siempre mostrará un texto legible.

---

### 4.2. Método 1: Enfoque Inline (Dentro de `plugin.json`)

**¿Cuándo usarlo?** Ideal para plugins pequeños o medianos, o prototipos rápidos donde prefieres tener todo concentrado en un único archivo `plugin.json` sin carpetas adicionales.

#### Propiedades que admiten diccionarios multilingüe:
1. **Metadatos generales**: `"name"` y `"description"` del plugin.
2. **Dispositivos**: `"devices[].name"`.
3. **Diálogo Global**: `"global_ui.title"`.
4. **Etiquetas de Controles**: `"label"` en sliders, checkboxes, dropdowns y botones.
5. **Etiquetas de Monitores de Telemetría**: `"labels"` en `progress_bar_multi` (como diccionario de listas).
6. **Opciones de Menús Desplegables**: En `dropdown`, cada opción puede ser un objeto con `"value"` técnico y `"label"` traducible.
7. **Pestañas y Secciones Personalizadas**: `"custom_tabs[].title"` y `"sections[].name"`.

#### Ejemplo Completo de Configuración Inline:
```json
{
  "id": "pedales_usb",
  "name": {
    "es": "Pedales de Carreras USB",
    "en": "USB Racing Pedals",
    "fr": "Pédales de Course USB"
  },
  "description": {
    "es": "Controlador físico de acelerador y freno para simulación",
    "en": "Physical throttle and brake controller for racing simulation"
  },
  "global_ui": {
    "title": {
      "es": "Ajustes de Conexión Serial",
      "en": "Serial Connection Settings",
      "fr": "Paramètres de Connexion Série"
    },
    "fields": [
      {
        "id": "baud_rate",
        "label": {
          "es": "Velocidad de Baudios",
          "en": "Baud Rate",
          "fr": "Vitesse en Bauds"
        },
        "type": "dropdown",
        "options": ["9600", "57600", "115200"],
        "default": "115200"
      },
      {
        "id": "mode_select",
        "label": {
          "es": "Modo de Operación",
          "en": "Operating Mode"
        },
        "type": "dropdown",
        "options": [
          { "value": "normal", "label": { "es": "Lineal Estándar", "en": "Standard Linear" } },
          { "value": "sport", "label": { "es": "Deportivo Agresivo", "en": "Aggressive Sport" } }
        ],
        "default": "normal"
      }
    ]
  },
  "pad_ui_customization": {
    "disable_default_tabs": ["sticks", "rumble"],
    "custom_tabs": [
      {
        "id": "pedals_tab",
        "title": {
          "es": "🏎️ Calibración",
          "en": "🏎️ Calibration",
          "de": "🏎️ Kalibrierung"
        },
        "sections": [
          {
            "name": {
              "es": "Ajuste Físico",
              "en": "Physical Adjustment"
            },
            "fields": [
              {
                "id": "gas_deadzone",
                "label": {
                  "es": "Zona Muerta Acelerador (%)",
                  "en": "Throttle Deadzone (%)",
                  "pt_BR": "Zona Morta Acelerador (%)"
                },
                "type": "slider",
                "min": 0,
                "max": 30,
                "default": 5
              }
            ]
          },
          {
            "name": {
              "es": "Telemetría en Vivo",
              "en": "Live Telemetry"
            },
            "fields": [
              {
                "id": "pedals_monitor",
                "type": "progress_bar_multi",
                "label": {
                  "es": "Presión de Pedales",
                  "en": "Pedal Pressure"
                },
                "bars": 2,
                "labels": {
                  "es": ["ACELERADOR", "FRENO"],
                  "en": ["THROTTLE", "BRAKE"],
                  "fr": ["ACCÉLÉRATEUR", "FREIN"]
                },
                "center_zero": false
              }
            ]
          }
        ]
      }
    ]
  }
}
```

---

### 4.3. Método 2: Enfoque Modular con Archivos en `locales/`

**¿Cuándo usarlo?** Es la mejor práctica para plugins grandes, proyectos colaborativos o cuando traductores externos trabajan en los textos sin riesgo de alterar la estructura JSON del manifiesto técnico.

#### 1. Estructura de Archivos:
Crea un subdirectorio `locales/` dentro de la carpeta de tu plugin con un archivo `.json` por cada idioma:
```
plugins/
└── mi_dispositivo/
    ├── plugin.json
    ├── main.py
    └── locales/
        ├── es.json      # Español (Base)
        ├── en.json      # English
        ├── fr.json      # Français
        ├── pt_BR.json   # Português
        └── de.json      # Deutsch
```

#### 2. Definición de Archivos de Idioma:
Cada archivo es un diccionario JSON plano donde cada clave representa un identificador de texto:

*`plugins/mi_dispositivo/locales/es.json`:*
```json
{
  "plugin_name": "Volante de Carreras Pro",
  "plugin_desc": "Controlador de volante y pedales con Force Feedback",
  "cfg_title": "Ajustes de Conexión Serial",
  "lbl_port": "Puerto COM del Volante",
  "lbl_baud": "Velocidad de Baudios",
  "tab_title": "🏎️ Calibración",
  "sec_angles": "Ángulo de Giro y Zona Muerta",
  "lbl_max_angle": "Ángulo Máximo (Grados)",
  "lbl_deadzone": "Zona Muerta (%)",
  "btn_zero": "Calibrar Centro en Cero",
  "sec_telemetry": "Monitor en Vivo",
  "bar_wheel": "VOLANTE",
  "bar_gas": "GAS",
  "bar_brake": "FRENO"
}
```

*`plugins/mi_dispositivo/locales/en.json`:*
```json
{
  "plugin_name": "Pro Racing Wheel",
  "plugin_desc": "Force Feedback steering wheel and pedals controller",
  "cfg_title": "Serial Connection Settings",
  "lbl_port": "Wheel COM Port",
  "lbl_baud": "Baud Rate",
  "tab_title": "🏎️ Calibration",
  "sec_angles": "Steering Angle & Deadzone",
  "lbl_max_angle": "Max Rotation Angle (Degrees)",
  "lbl_deadzone": "Deadzone (%)",
  "btn_zero": "Calibrate Center Zero",
  "sec_telemetry": "Live Monitor",
  "bar_wheel": "STEERING",
  "bar_gas": "THROTTLE",
  "bar_brake": "BRAKE"
}
```

#### 3. Cómo Referenciar las Claves en `plugin.json`:
En `plugin.json`, en cualquier lugar donde antes colocabas texto visible, escribe el nombre de la clave. Puedes usar opcionalmente el prefijo `@` o `$` para máxima claridad:

```json
{
  "id": "volante_pro",
  "name": "@plugin_name",
  "description": "@plugin_desc",
  "entry_point": "main.py",
  "devices": [
    {
      "id": "wheel",
      "name": "@plugin_name",
      "type": "gamepad",
      "num_buttons": 16,
      "num_axes": 4
    }
  ],
  "global_ui": {
    "title": "@cfg_title",
    "fields": [
      {
        "id": "com_port",
        "label": "@lbl_port",
        "type": "dynamic_dropdown",
        "discovery_action": "scan_ports",
        "default": "AUTO"
      },
      {
        "id": "baud",
        "label": "@lbl_baud",
        "type": "dropdown",
        "options": ["9600", "57600", "115200"],
        "default": "115200"
      }
    ]
  },
  "pad_ui_customization": {
    "disable_default_tabs": ["sticks"],
    "custom_tabs": [
      {
        "id": "wheel_cal",
        "title": "@tab_title",
        "sections": [
          {
            "name": "@sec_angles",
            "fields": [
              {
                "id": "max_degrees",
                "label": "@lbl_max_angle",
                "type": "slider",
                "min": 180,
                "max": 900,
                "default": 900
              },
              {
                "id": "deadzone",
                "label": "@lbl_deadzone",
                "type": "slider",
                "min": 0,
                "max": 20,
                "default": 2
              },
              {
                "id": "btn_zero_cal",
                "label": "@btn_zero",
                "type": "button",
                "action": "calibrate_zero"
              }
            ]
          },
          {
            "name": "@sec_telemetry",
            "fields": [
              {
                "id": "wheel_monitor",
                "type": "progress_bar_multi",
                "label": "@sec_telemetry",
                "bars": 3,
                "labels": ["@bar_wheel", "@bar_gas", "@bar_brake"],
                "center_zero": false
              }
            ]
          }
        ]
      }
    ]
  }
}
```

---

### 4.4. Cómo se Utiliza e Interactúa con el Código Python (`main.py`)

Una de las decisiones arquitectónicas más importantes de j360More es el **Aislamiento Técnico del Idioma**:

1. **Los Callbacks reciben siempre Identificadores Técnicos Neutros**:
   Cuando el usuario cambia un valor en la GUI, el evento que llega a tu script de Python utiliza **únicamente el `id` técnico** declarado en `plugin.json`, **jamás la etiqueta traducida**:
   ```python
   # Python siempre escucha 'gas_deadzone', sin importar si la GUI muestra
   # 'Zona Muerta Acelerador (%)', 'Throttle Deadzone (%)' o 'Zona Morta (%)'
   @device.on_field_change("gas_deadzone")
   def handle_deadzone(new_val, pad_id):
       deadzone_ratio = float(new_val) / 100.0
   ```

2. **Los Menús Desplegables transmiten el `value` técnico**:
   Si declaras opciones con traducción:
   ```json
   { "value": "AUTO", "label": { "es": "Automático", "en": "Automatic" } }
   ```
   Tu función en Python recibirá siempre `"AUTO"`. No necesitas hacer comparaciones de cadenas por cada idioma en tus condicionales.

3. **Mensajes de Depuración y Registro de Eventos**:
   Al enviar logs a la consola de j360More con `device.log(...)`, puedes emitir mensajes descriptivos sin afectar el funcionamiento del mapeo:
   ```python
   device.log("Puerto serial COM3 conectado exitosamente", "INFO")
   ```

---

### 4.5. Prueba y Conmutación en Caliente en j360More

Puedes verificar el funcionamiento multi-idioma de tu plugin en tiempo real:

1. Inicia **j360More**.
2. En la barra superior de navegación, pulsa el botón **`EN`** o **`ES`** (o ve a la pestaña *Configuración* y cambia el idioma a Francés, Alemán, Portugués o Ruso).
3. Selecciona la pestaña del mando emulado o pulsa el botón **`⚙ Configurar`** de tu plugin.
4. **Resultado**: El emulador invoca `PluginManager` y re-renderiza dinámicamente toda la interfaz en el idioma seleccionado al instante, **sin detener la emulación ni reiniciar tu proceso de Python**.

---

## 5. Hardware Físico Real 1: Arduino / ESP32 (Pedales, Volantes y Freno de Mano)

![Demostración en Vivo: Pedales Arduino en j360More](assets/videoArduino.gif)

*Animación en tiempo real: Respuesta de acelerador, freno y embrague con telemetría visual (~33 FPS) y mapeo XInput a 120 Hz en j360More.*

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

![Demostración en Vivo: Controlador MIDI en j360More](assets/videoMidi.gif)

*Animación en tiempo real: Pulsación de notas para botones, barrido de Pitch Bend al stick izquierdo y rueda de modulación a gatillo RT con VU-meter reactivo.*

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

### 6.4. Script Completo del Plugin MIDI en Python (`main.py`)

A continuación se muestra el código fuente completo, probado y listo para producción del plugin MIDI (`plugins/midi_controller/main.py`), incluyendo conexión con `pygame.midi`, decodificación de eventos, mapeo semántico, escaneo dinámico y telemetría en tiempo real:

```python
"""
plugins/midi_controller/main.py
Controlador de Teclado y Pads MIDI Físicos para j360More.
Convierte eventos Note On/Off a botones de Xbox y ruedas de tono/modulación a sticks.
"""

import sys
import os
import time

# Permitir importaciones del SDK
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from plugins.plugin_sdk import PluginDevice

# 1. Instanciación del dispositivo con 8 botones semánticos y 4 ejes
device = PluginDevice(
    id="midi_controller",
    name="Controlador MIDI USB",
    num_buttons=8,
    num_axes=4
)

# Mapeo de notas MIDI estándar a botones de Xbox 360
NOTE_MAP = {
    60: "A",       # C4 (Do central)
    62: "B",       # D4 (Re)
    64: "X",       # E4 (Mi)
    65: "Y",       # F4 (Fa)
    67: "LB",      # G4 (Sol)
    69: "RB",      # A4 (La)
    71: "START",   # B4 (Si)
    72: "GUIDE",   # C5 (Do agudo)
}

active_midi_port = "AUTO"
velocity_threshold = 15

# -------------------------------------------------------------
# Callbacks del Manifiesto UI
# -------------------------------------------------------------

@device.on_action("scan_midi_ports")
def handle_scan_midi_ports(pad_id: int):
    """Escanea puertos de entrada física y actualiza el dynamic_dropdown."""
    found = ["AUTO"]
    try:
        import pygame.midi
        if not pygame.midi.get_init():
            pygame.midi.init()
        for i in range(pygame.midi.get_count()):
            info = pygame.midi.get_device_info(i)
            # info = (interface, name, is_input, is_output, opened)
            if info and info[2] == 1:  # Filtrar estrictamente solo puertos de entrada
                dev_name = info[1].decode("utf-8", errors="ignore")
                found.append(f"{i}: {dev_name}")
    except Exception as e:
        device.log(f"Error escaneando MIDI: {e}", "ERROR")

    # Actualizar combobox en la interfaz
    device.update_field_options("midi_port", found)
    device.log(f"Puertos MIDI escaneados con éxito: {found}")

@device.on_field_change("midi_port")
def handle_port_change(new_port, pad_id):
    global active_midi_port
    active_midi_port = str(new_port)
    device.log(f"Puerto MIDI seleccionado: {active_midi_port}")

@device.on_field_change("velocity_threshold")
def handle_velocity_change(new_val, pad_id):
    global velocity_threshold
    velocity_threshold = int(new_val)
    device.log(f"Umbral de velocidad actualizado a: {velocity_threshold}")

# -------------------------------------------------------------
# Bucle de Control y Lectura a 120 Hz
# -------------------------------------------------------------

def run_loop():
    import pygame.midi
    if not pygame.midi.get_init():
        pygame.midi.init()

    pg_midi_in = None
    target_id = None

    # Determinar ID del dispositivo seleccionado
    if active_midi_port != "AUTO" and ":" in active_midi_port:
        try:
            target_id = int(active_midi_port.split(":")[0])
        except ValueError:
            target_id = None

    # Autodetección del primer puerto de entrada válido si está en AUTO
    if target_id is None:
        for i in range(pygame.midi.get_count()):
            info = pygame.midi.get_device_info(i)
            if info and info[2] == 1:
                target_id = i
                break

    if target_id is not None:
        try:
            pg_midi_in = pygame.midi.Input(target_id)
            device.log(f"Conectado exitosamente a dispositivo MIDI físico #{target_id}")
        except Exception as e:
            device.log(f"No se pudo abrir dispositivo MIDI #{target_id}: {e}", "ERROR")
    else:
        device.log("Aviso: No se detectó teclado MIDI físico conectado. Esperando conexión...", "WARN")

    last_velocity_norm = 0.0
    last_pitch_norm = 0.5  # Centro neutro (50%)
    last_mod_norm = 0.0
    last_telemetry_time = 0.0

    try:
        while device.is_running():
            t0 = time.perf_counter()

            if pg_midi_in and pg_midi_in.poll():
                # Leer paquetes de eventos sin bloquear
                midi_packets = pg_midi_in.read(16)
                for packet in midi_packets:
                    data, timestamp = packet
                    status, d1, d2, _ = data
                    cmd = status & 0xF0

                    # 1. Note On / Note Off
                    if cmd == 0x90 and d2 > 0:  # Pulsación con velocidad
                        if d2 >= velocity_threshold:
                            btn = NOTE_MAP.get(d1)
                            if btn:
                                device.set_button(btn, True)
                            # También activar botón indexado por compatibilidad
                            device.set_button_index(d1 % 8, True)
                            last_velocity_norm = d2 / 127.0
                    elif cmd == 0x80 or (cmd == 0x90 and d2 == 0):  # Liberación
                        btn = NOTE_MAP.get(d1)
                        if btn:
                            device.set_button(btn, False)
                        device.set_button_index(d1 % 8, False)

                    # 2. Pitch Bend Wheel (14 bits: -8192 a +8191)
                    elif cmd == 0xE0:
                        pitch_14bit = (d2 << 7) | d1
                        norm_stick = max(-1.0, min(1.0, (pitch_14bit - 8192) / 8192.0))
                        device.set_stick("LX", norm_stick)
                        last_pitch_norm = (norm_stick + 1.0) / 2.0

                    # 3. Modulation Wheel (CC #1, 0 a 127)
                    elif cmd == 0xB0 and d1 == 1:
                        norm_trigger = max(0.0, min(1.0, d2 / 127.0))
                        device.set_trigger("RT", norm_trigger)
                        last_mod_norm = norm_trigger

                # Sincronización atómica de estados
                device.flush()

            # Desvanecimiento progresivo del indicador de velocidad cuando se sueltan notas
            if last_velocity_norm > 0:
                last_velocity_norm = max(0.0, last_velocity_norm - 0.04)

            # Envío de telemetría dinámica a ~33 FPS para el Canvas de la GUI
            now = time.perf_counter()
            if now - last_telemetry_time >= 0.03:
                last_telemetry_time = now
                device.send_telemetry({
                    "midi_telemetry": [last_velocity_norm, last_pitch_norm, last_mod_norm]
                }, pad_id=0)

            # Mantener ciclo a 120 Hz (~8.3 ms)
            elapsed = time.perf_counter() - t0
            sleep_time = 0.0083 - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        if pg_midi_in:
            try:
                pg_midi_in.close()
            except Exception:
                pass
        pygame.midi.quit()
        device.log("Dispositivo MIDI cerrado limpiamente.")

if __name__ == "__main__":
    device.start(run_loop)
```

---

## 7. Referencia Completa y Detallada del SDK de Python (`PluginDevice`)

La clase `PluginDevice` (ubicada en `plugins/plugin_sdk.py`) encapsula todo el protocolo IPC de bajo nivel, la gestión de memoria protegida por hilos (`threading.Lock`), y la comunicación por sockets TCP JSON locales con el motor de j360More.

A continuación se detalla la firma, parámetros, tipo de datos, valor de retorno y ejemplo de uso de **cada método y decorador disponible**:

---

### 7.1. Inicialización y Ciclo de Vida

#### `__init__(id: str, name: str, num_buttons: int = 16, num_axes: int = 6)`
- **Descripción**: Constructor del dispositivo. Inicializa los búferes internos de botones semánticos, ejes y disparadores.
- **Parámetros**:
  - `id` *(str)*: Identificador único del dispositivo (debe coincidir con `devices[].id` de `plugin.json`).
  - `name` *(str)*: Nombre descriptivo visible para el usuario en la GUI.
  - `num_buttons` *(int, por defecto 16)*: Cantidad de botones físicos indexados (`0..N-1`).
  - `num_axes` *(int, por defecto 6)*: Cantidad de ejes analógicos indexados (`0..N-1`).
- **Ejemplo**:
  ```python
  from plugins.plugin_sdk import PluginDevice

  device = PluginDevice(id="mi_mando", name="Volante Pro", num_buttons=12, num_axes=4)
  ```

#### `is_running() -> bool`
- **Descripción**: Indica si el proceso de emulación y el socket IPC permanecen activos. Debe utilizarse como condición principal del bucle `while`.
- **Retorno**: `True` mientras el emulador esté ejecutándose; `False` cuando el usuario pulsa "Detener" o cierra la aplicación.
- **Ejemplo**:
  ```python
  while device.is_running():
      leer_hardware()
  ```

#### `set_connected(is_connected: bool, device_id: Optional[str] = None)`
- **Descripción**: Informa explícitamente a j360More sobre el estado de conexión del hardware físico (cable USB, puerto COM o MIDI). Al invocarlo con `False`:
  1. Invoca automáticamente `reset_inputs()` para restablecer todos los botones a `False` y gatillos/palancas a `0.0`, impidiendo **entradas pegadas** (*stuck inputs*).
  2. Notifica al emulador mediante el evento IPC `device_status`.
  3. En la interfaz gráfica de j360More, el periférico se etiqueta en tiempo real como `[Offline]` y se neutralizan lecturas de motor.
  Al invocarlo con `True` (tras reconexión física), el periférico vuelve a su estado normal activo.
- **Parámetros**:
  - `is_connected` *(bool)*: `True` para conectado, `False` para desconectado o en búsqueda.
  - `device_id` *(str, opcional)*: Identificador específico del subdispositivo (por defecto toma `device.id`).
- **Ejemplo**:
  ```python
  try:
      ser = serial.Serial("COM3", 115200)
      device.set_connected(True)
  except Exception:
      device.set_connected(False)
  ```

#### `is_device_connected() -> bool`
- **Descripción**: Consulta el estado de conexión física actual establecido para el dispositivo.
- **Retorno**: `True` si está marcado como conectado; `False` si está fuera de línea.

#### `reset_inputs(flush: bool = False)`
- **Descripción**: Restablece de forma inmediata todos los búferes internos a su posición neutra de reposo (todos los botones semánticos e indexados en `False`, gatillos en `0.0`, palancas en `0.0` y ejes analógicos en `0.0`).
- **Parámetros**:
  - `flush` *(bool, por defecto False)*: Si es `True`, transmite el estado neutro inmediatamente por el socket IPC.
- **Ejemplo**:
  ```python
  device.reset_inputs(flush=True)
  ```

#### `report_devices(devices: List[Dict[str, Any]])`
- **Descripción**: Notifica proactivamente al emulador una lista dinámica actualizada de dispositivos físicos descubiertos o conectados en caliente, sin necesidad de esperar a que j360More solicite `request_discovery`.
- **Parámetros**:
  - `devices` *(list)*: Lista de diccionarios con llaves `id`, `name`, `num_buttons`, `num_axes`.
- **Ejemplo**:
  ```python
  device.report_devices([
      {"id": "volante_usb", "name": "Volante ForceFeedback", "num_buttons": 12, "num_axes": 4}
  ])
  ```

#### `start(loop_fn: Optional[Callable[[], None]] = None)`
- **Descripción**: Punto de entrada de ejecución del plugin. Parsea automáticamente los argumentos pasados por j360More (`--ipc-port`, `--ipc-host`, `--simulate`), realiza el handshake con el servidor local e inicia el bucle `loop_fn` en el hilo principal.
- **Parámetros**:
  - `loop_fn` *(callable, opcional)*: Función principal del bucle de captura.
- **Ejemplo**:
  ```python
  if __name__ == "__main__":
      device.start(run_loop)
  ```

---

### 7.2. Controles Semánticos de Xbox (Recomendado)

#### `set_button(name: str, is_pressed: bool)`
- **Descripción**: Establece el estado de un botón oficial de Xbox 360 por su nombre semántico.
- **Parámetros**:
  - `name` *(str)*: Nombre del botón. Valores válidos exactos:
    `"A"`, `"B"`, `"X"`, `"Y"`, `"LB"`, `"RB"`, `"BACK"`, `"START"`, `"GUIDE"`, `"L3"`, `"R3"`, `"DPAD_UP"`, `"DPAD_DOWN"`, `"DPAD_LEFT"`, `"DPAD_RIGHT"`.
  - `is_pressed` *(bool)*: `True` para presionar, `False` para liberar.
- **Ejemplo**:
  ```python
  device.set_button("A", True)       # Presionar botón A
  device.set_button("DPAD_UP", False) # Liberar cruceta arriba
  ```

#### `press_button(name: str)` y `release_button(name: str)`
- **Descripción**: Métodos de conveniencia para activar o desactivar botones semánticos.
- **Ejemplo**:
  ```python
  device.press_button("RB")   # Equivale a set_button("RB", True)
  device.release_button("RB") # Equivale a set_button("RB", False)
  ```

#### `set_trigger(name: str, value: float)`
- **Descripción**: Establece el valor analógico de los gatillos traseros `LT` (izquierdo) o `RT` (derecho). El valor se clampa automáticamente entre 0.0 y 1.0.
- **Parámetros**:
  - `name` *(str)*: `"LT"` o `"RT"` (no sensible a mayúsculas).
  - `value` *(float)*: Presión normalizada de `0.0` (reposo) a `1.0` (presión completa).
- **Ejemplo**:
  ```python
  device.set_trigger("RT", 0.85) # Acelerador al 85%
  device.set_trigger("LT", 0.0)  # Freno liberado
  ```

#### `set_stick(*args, **kwargs)`
- **Descripción**: Asigna las coordenadas bidimensionales de las palancas analógicas izquierda y derecha con un rango de `-1.0` a `+1.0`. Soporta firmas múltiples ultra-flexibles:
  - Por nombre de eje individual: `set_stick('LX', 0.5)`
  - Por palabras clave: `set_stick(LX=0.5, LY=-0.2, RX=0.0, RY=0.0)`
  - Por pares posicionales: `set_stick('left', x_val, y_val)` o `set_stick('right', x_val, y_val)`
- **Ejemplo**:
  ```python
  # Mover stick izquierdo a la derecha y arriba:
  device.set_stick(LX=0.75, LY=0.50)

  # Centrar stick derecho en reposo:
  device.set_stick('right', 0.0, 0.0)
  ```

---

### 7.3. Controles Físicos Indexados

Los controles indexados (`set_axis` y `set_button_index`) son ideales cuando estás creando periféricos de libre disposición (por ejemplo, palancas de vuelo HOTAS con 32 botones, volantes DIY con botoneras personalizadas o placas arcade USB), donde el usuario desea asignar cada botón o eje de forma personalizada en la pestaña de configuración del emulador sin nombres fijos predefinidos.

#### `set_axis(axis_index: int, value: float)`
- **Descripción**: Asigna el valor analógico de un eje físico genérico numerado (`0..num_axes-1`).
- **Parámetros**:
  - `axis_index` *(int)*: Índice del eje (`0` a `num_axes-1`).
  - `value` *(float)*: Valor normalizado entre `-1.0` (extremo negativo) y `+1.0` (extremo positivo).
- **Ejemplo**:
  ```python
  device.set_axis(0, -0.45) # Eje físico 0 a -45%
  ```

#### `set_button_index(button_index: int, is_pressed: bool)`
- **Descripción**: Asigna el estado booleano de un botón físico indexado (`0..num_buttons-1`).
- **Parámetros**:
  - `button_index` *(int)*: Índice del botón (`0` a `num_buttons-1`).
  - `is_pressed` *(bool)*: `True` si está pulsado, `False` si está en reposo.
- **Ejemplo**:
  ```python
  device.set_button_index(3, True) # Botón físico 3 presionado
  ```

#### Ejemplo Práctico Completo: Joystick de Vuelo con 12 Botones y 4 Ejes Indexados

```python
import time
from plugins.plugin_sdk import PluginDevice

# Declarar un dispositivo genérico con 12 botones físicos y 4 ejes analógicos
device = PluginDevice(id="flight_stick", name="Flight Stick HOTAS", num_buttons=12, num_axes=4)

def run_loop():
    device.log("Iniciando lectura de joystick indexado a 120 Hz.", "INFO")
    
    while device.is_running():
        # Supongamos que leemos 4 canales analógicos crudos (ej. ADC 0 a 1023)
        raw_pot_x = 512    # Alerones (centro)
        raw_pot_y = 768    # Elevador (inclinado)
        raw_rudder = 512   # Timón (centro)
        raw_throttle = 100 # Acelerador (casi al mínimo)

        # 1. Normalizar los 4 ejes al rango [-1.0, 1.0]
        axis_x = ((raw_pot_x / 1023.0) * 2.0) - 1.0
        axis_y = ((raw_pot_y / 1023.0) * 2.0) - 1.0
        axis_rudder = ((raw_rudder / 1023.0) * 2.0) - 1.0
        axis_throttle = ((raw_throttle / 1023.0) * 2.0) - 1.0

        device.set_axis(0, axis_x)
        device.set_axis(1, axis_y)
        device.set_axis(2, axis_rudder)
        device.set_axis(3, axis_throttle)

        # 2. Leer estado de los 12 interruptores físicos
        # En este ejemplo, supongamos que el gatillo de disparo (índice 0) y el botón de armas (índice 3) están activos
        for btn_idx in range(12):
            is_active = (btn_idx in (0, 3))
            device.set_button_index(btn_idx, is_active)

        # 3. Transmisión atómica de todos los índices al emulador
        device.flush()

        time.sleep(0.0083) # ~120 Hz

if __name__ == "__main__":
    device.start(run_loop)
```

---

### 7.4. Sincronización y Transmisión de Estados

#### `flush()`
- **Descripción**: Empaqueta de forma atómica y segura (`threading.Lock`) todos los estados acumulados de botones, gatillos y palancas, y los transmite al motor de j360More mediante el socket TCP. **Debe llamarse al final de cada iteración de lectura**.

#### `send_telemetry(data: Dict[str, Any], pad_id: int = 1)`
- **Descripción**: Transmite datos numéricos en vivo a los monitores Canvas (`progress_bar_multi`) de la GUI. Se recomienda regular su envío a ~33 FPS (`0.03` s).

#### `update_field_options(field_id: str, options: List[Any])`
- **Descripción**: Actualiza dinámicamente las opciones de un menú desplegable (`dropdown` o `dynamic_dropdown`) en la GUI sin recargar la aplicación.

#### `set_field_value(field_id: str, value: Any, pad_id: int = 1)`
- **Descripción**: Fuerza un nuevo valor visual en un widget de la GUI (útil por ejemplo tras ejecutar una auto-calibración en cero).

#### `log(message: str, level: str = "INFO")`
- **Descripción**: Imprime un mensaje en la consola de terminal y lo retransmite simultáneamente a la **Consola de Depuración de Plugins** integrada en la GUI de j360More (`"INFO"`, `"WARN"`, `"ERROR"`, `"DEBUG"`).

#### Ejemplo Práctico Completo: Bucle de 120 Hz con Telemetría Regulada y Comunicación GUI

```python
import time
from plugins.plugin_sdk import PluginDevice

device = PluginDevice(id="pedales_pro", name="Pedales de Competición")

def run_loop():
    last_telemetry_time = 0.0
    telemetry_interval = 0.033  # ~30-33 FPS para no saturar la GUI

    device.log("Driver iniciado correctamente. Bucle de transmisión activo.", "INFO")

    while device.is_running():
        t_start = time.perf_counter()

        # Simular lectura analógica de acelerador y freno (0.0 a 1.0)
        gas_norm = 0.85
        brake_norm = 0.10

        # 1. Enviar entradas de control al emulador a 120 Hz
        device.set_trigger("RT", gas_norm)
        device.set_trigger("LT", brake_norm)
        device.flush()  # Envío atómico inmediato por socket IPC

        # 2. Enviar telemetría visual regulada a ~33 FPS para los monitores de la GUI
        now = time.perf_counter()
        if now - last_telemetry_time >= telemetry_interval:
            last_telemetry_time = now
            # 'monitor_barras' debe coincidir con el 'id' en plugin.json (progress_bar_multi)
            device.send_telemetry({
                "monitor_barras": [gas_norm, brake_norm, 0.0]
            }, pad_id=1)

        # 3. Mantener cadencia estricta de 120 Hz (8.33 ms por iteración)
        elapsed = time.perf_counter() - t_start
        sleep_rem = 0.00833 - elapsed
        if sleep_rem > 0:
            time.sleep(sleep_rem)

if __name__ == "__main__":
    device.start(run_loop)
```

---

### 7.5. Decoradores de Eventos Bidireccionales

Los decoradores permiten responder a eventos que provienen de la interfaz de usuario de j360More o de los juegos (como el Force Feedback):

- **`@device.on_rumble`**: Recibe vibración háptica XInput desde el juego (`small_motor`, `large_motor` de 0.0 a 1.0).
- **`@device.on_field_change(field_id)`**: Recibe el nuevo valor cuando el usuario interactúa con un slider o checkbox en la GUI.
- **`@device.on_action(action_name)`**: Se ejecuta cuando el usuario pulsa un botón de acción en la interfaz (como calibrar o escanear).
- **`@device.on_discover_devices`**: Se invoca cuando j360More consulta qué periféricos físicos están presentes.

#### Ejemplo Práctico Completo: Integración de los 4 Decoradores en un Solo Driver

```python
from plugins.plugin_sdk import PluginDevice

device = PluginDevice(id="volante_ffb", name="Volante Force Feedback")

# Variables de calibración en memoria
config_runtime = {
    "sensibilidad": 100,
    "invertir_eje": False,
    "centro_calibrado": 0.0
}

# 1. Decorador de Vibración Háptica / Force Feedback desde el juego
@device.on_rumble
def handle_rumble(small_motor: float, large_motor: float):
    # 'small_motor': motor ligero de alta frecuencia (0.0 a 1.0)
    # 'large_motor': motor pesado de baja frecuencia (0.0 a 1.0)
    pwm_pesado = int(large_motor * 255)
    pwm_ligero = int(small_motor * 255)
    device.log(f"Rumble recibido -> Pesado: {pwm_pesado}/255, Ligero: {pwm_ligero}/255", "DEBUG")
    # Aquí enviarías los comandos PWM por USB o Serial a tu motor de Force Feedback

# 2. Decorador de Cambios en la Interfaz (Sliders / Checkboxes)
@device.on_field_change("sensibilidad")
def on_sens_changed(nuevo_valor, pad_id: int):
    config_runtime["sensibilidad"] = int(nuevo_valor)
    device.log(f"Sensibilidad actualizada a {nuevo_valor}% para Mando {pad_id}", "INFO")

@device.on_field_change("invertir_eje")
def on_invert_changed(nuevo_valor, pad_id: int):
    config_runtime["invertir_eje"] = bool(nuevo_valor)
    device.log(f"Inversión de eje: {config_runtime['invertir_eje']}", "INFO")

# 3. Decorador de Acciones de Botón (Calibración o Escaneo)
@device.on_action("calibrar_centro")
def on_calibrar_centro(pad_id: int):
    # Supongamos que tomamos la lectura actual como cero
    config_runtime["centro_calibrado"] = 0.0
    # Forzar la actualización visual en la GUI
    device.set_field_value("offset_centro", 0, pad_id=pad_id)
    device.log(f"Centro calibrado a cero para Mando {pad_id}.", "INFO")

@device.on_action("escanear_puertos")
def on_escanear_puertos(pad_id: int):
    puertos_encontrados = ["COM3 (Arduino)", "COM5 (ESP32)"]
    # Actualizar dinámicamente las opciones del dropdown en la GUI
    device.update_field_options("puerto_com", puertos_encontrados)
    device.log(f"Puertos escaneados y enviados a la GUI: {puertos_encontrados}", "INFO")

# 4. Decorador de Detección Dinámica de Dispositivos
@device.on_discover_devices
def on_discover():
    # Reporta los dispositivos físicos disponibles al emulador
    return [
        {"id": "volante", "name": "Volante FFB Principal", "num_buttons": 12, "num_axes": 4},
        {"id": "pedales", "name": "Pedales Analógicos USB", "num_buttons": 4, "num_axes": 3}
    ]

if __name__ == "__main__":
    device.start()
```

---

## 8. Gestión de Conexión, Desconexión y Reconexión en Caliente (Hot-Plug)

Uno de los mayores retos en la emulación de mandos y controladores personalizados es el manejo de cables desconectados accidentalmente durante una partida, tirones de cables USB o reconexiones en puertos diferentes.

### 8.1. Los Dos Niveles de Enlace: IPC vs Hardware Físico

En **j360More** existen dos niveles de conexión completamente diferenciados:

```
┌─────────────────────────────────────────────────────────────┐
│                 Nivel 1: Enlace IPC Local                   │
│         [Script Python main.py] ◄──TCP Socket──► [j360More] │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                Nivel 2: Enlace Físico Real                  │
│       [Sensor / Arduino / MIDI] ◄──USB/COM──► [main.py]     │
└─────────────────────────────────────────────────────────────┘
```

1. **Nivel 1 (IPC Socket)**: El canal TCP entre el proceso del plugin y j360More.
   - Si el proceso del plugin se detiene o falla, el servidor IPC en j360More detecta inmediatamente la desconexión del socket, marca el estado en `stopped`, purga los mandos virtuales y dispara el refresco de ranuras en la GUI.
2. **Nivel 2 (Hardware Físico)**: El enlace por cable (USB COM o MIDI) entre el microcontrolador y el script `main.py`.
   - Si el usuario desconecta el cable USB del Arduino o el teclado MIDI, **el proceso Python sigue vivo**, pero ya no recibe bytes físicos del sensor.
   - **El Peligro de las Entradas Pegadas (*Stuck Inputs*)**: Si el usuario estaba pisando el acelerador al 100% en el instante en que se desconectó el cable, el último estado reportado a j360More permanecería en `RT: 1.0` indefinidamente. El coche en el juego continuaría acelerando solo y sin control.

#### Ejemplo Práctico: Desacoplamiento de los Dos Niveles en el Código

```python
# Demostración del desacoplamiento entre el Nivel 1 (IPC) y el Nivel 2 (Hardware)
while device.is_running(): # Nivel 1: El canal IPC con j360More permanece activo y receptivo
    if hardware_serial is not None:
        try:
            # Nivel 2: Intento de lectura física sobre el cable USB
            linea = hardware_serial.readline().decode().strip()
            valor_gas = float(linea) / 1023.0
            device.set_trigger("RT", valor_gas)
            device.flush()
        except Exception as error_fisico:
            # ¡El cable físico USB se desconectó (Nivel 2)!
            device.log(f"Falla en enlace físico Nivel 2: {error_fisico}", "WARNING")
            try:
                hardware_serial.close()
            except Exception:
                pass
            hardware_serial = None
            
            # Notificamos a j360More por el canal IPC (Nivel 1) que el hardware físico está fuera de línea:
            device.set_connected(False)
    else:
        # El proceso sigue vivo respondiendo a eventos de GUI mientras espera la reconexión física
        time.sleep(1.0)
```

---

### 8.2. Prevención de Entradas Pegadas (*Stuck Inputs*) y `reset_inputs()`

Para garantizar seguridad total en juegos de carreras, simuladores de vuelo o juegos de lucha, el SDK provee dos mecanismos automáticos:

1. **`device.reset_inputs(flush=True)`**: Limpia todos los botones a `False`, gatillos a `0.0`, sticks a `0.0` y ejes a `0.0` de forma atómica en memoria.
2. **`device.set_connected(False)`**:
   - Pone automáticamente en cero todos los controles invocando `reset_inputs()`.
   - Transmite de inmediato un paquete `state_update` neutro a j360More.
   - Envía un evento IPC `device_status` con `connected: False`.
   - El motor de j360More neutraliza las lecturas del mando y la interfaz muestra el distintivo `🔌 [Plugin] Mi Dispositivo [Offline]`.

#### Ejemplo Comparativo: Código Vulnerable vs Código Seguro con Prevención

```python
# -------------------------------------------------------------
# ❌ EJEMPLO INCORRECTO: VULNERABLE A ENTRADAS TRABADAS (STUCK INPUTS)
# -------------------------------------------------------------
try:
    raw_data = ser.readline()
    pedal_gas = int(raw_data) / 1023.0 # Supongamos 1.0 (a fondo)
    device.set_trigger("RT", pedal_gas)
    device.flush()
except Exception:
    # ERROR GRAVE: Si el cable se suelta aquí, RT se queda congelado en 1.0 para siempre
    pass


# -------------------------------------------------------------
# ✅ EJEMPLO CORRECTO: PROTECCIÓN TOTAL CON RESET Y SET_CONNECTED
# -------------------------------------------------------------
try:
    raw_data = ser.readline()
    pedal_gas = int(raw_data) / 1023.0
    device.set_trigger("RT", pedal_gas)
    device.flush()
except Exception as e:
    device.log(f"Cable desconectado o error de lectura: {e}", "WARNING")
    # 1. Neutraliza de inmediato los controles a 0.0 / False en memoria
    # 2. Envía un paquete neutro por IPC al emulador
    # 3. Notifica a la GUI que el mando está [Offline]
    device.set_connected(False)
    
    # 4. También puedes invocar explícitamente reset_inputs si deseas forzar el limpiado de inmediato:
    device.reset_inputs(flush=True)
```

---

### 8.3. Patrón de Reconexión Automática sin Bloqueos

El script del plugin **nunca debe colapsar ni llamar a `sys.exit()`** si un cable se desconecta. En su lugar, debe capturar la excepción de lectura, marcar `device.set_connected(False)` e iniciar un temporizador de reintento no bloqueante:

```python
import time
import serial
from plugins.plugin_sdk import PluginDevice

device = PluginDevice(id="mi_hardware", name="Mi Hardware USB")
serial_conn = None

def try_connect() -> bool:
    global serial_conn
    try:
        serial_conn = serial.Serial("COM3", 115200, timeout=0.01)
        device.set_connected(True) # Avisa a j360More que el hardware está listo
        device.log("Hardware USB conectado en COM3.", "INFO")
        return True
    except Exception:
        serial_conn = None
        return False

def run_loop():
    global serial_conn
    last_reconnect_time = 0.0

    # Intento inicial al arrancar
    if not try_connect():
        device.set_connected(False)
        device.log("Hardware desconectado al inicio. Esperando conexión física...", "INFO")

    while device.is_running():
        # 1. Si el puerto está abierto, leer tramas
        if serial_conn:
            try:
                line = serial_conn.readline().decode("utf-8").strip()
                if line:
                    procesar_datos(line)
                    device.flush()
            except Exception as e:
                # ¡Cable desconectado físicamente!
                device.log(f"Desconexión detectada: {e}", "WARNING")
                try:
                    serial_conn.close()
                except Exception:
                    pass
                serial_conn = None
                
                # ¡Poner entradas en neutro y avisar a j360More!
                device.set_connected(False)
                last_reconnect_time = time.time()
                continue
        else:
            # 2. Si está desconectado, reintentar reconexión cada 1.5 segundos
            now = time.time()
            if now - last_reconnect_time >= 1.5:
                last_reconnect_time = now
                if try_connect():
                    continue
            time.sleep(0.02)
```

---

### 8.4. Notificación Dinámica de Periféricos con `report_devices()`

Si tu plugin gestiona múltiples dispositivos conectados simultáneamente (por ejemplo, múltiples puertos COM para pedales + palanca de cambios independiente, o varios teclados MIDI enchufados en puertos USB diferentes), puedes notificar dinámicamente la lista de hardware activo en tiempo real:

```python
# Escaneo de dispositivos físicos conectados actualmente
dispositivos_activos = [
    {"id": "volante", "name": "Volante Principal", "num_buttons": 12, "num_axes": 4},
    {"id": "shifter", "name": "Palanca H Secuencial", "num_buttons": 8, "num_axes": 0}
]

# Registrar de forma proactiva ante j360More sin esperar un sondeo
device.report_devices(dispositivos_activos)
```

Al llamar a `report_devices()`, j360More actualiza automáticamente los selectores de periféricos en todas las pestañas de mandos en la GUI.

---

## 9. Diagnóstico y Resolución de Problemas

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
