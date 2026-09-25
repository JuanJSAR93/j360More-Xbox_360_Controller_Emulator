# j360More - Emulador Multimando (Xbox 360, Xbox One, PS4, PS5 y Switch 2 Pro)

[📖 Read in English](README.md) | [Descargas Oficiales (Releases)](https://github.com/JuanJSAR93/j360More-Xbox_360_Controller_Emulator/releases) | [Documentación Web](https://juanjsar93.github.io/j360More-Xbox_360_Controller_Emulator/)

> **Desarrollado por JuanJSAR**  
> Repositorio Oficial: [GitHub - JuanJSAR93/j360More](https://github.com/JuanJSAR93/j360More-Xbox_360_Controller_Emulator)  
> Descargas y Versiones: [Releases Oficiales](https://github.com/JuanJSAR93/j360More-Xbox_360_Controller_Emulator/releases)  
> Documentación Web (GitHub Pages): Carpeta `/docs`

**j360More** es una solución avanzada de emulación multi-mando desarrollada por **JuanJSAR**. Con soporte tanto para el nuevo driver multiplataforma **VIIPER** (USB/IP) como para **ViGEmBus**, ofrece una moderna interfaz bilingüe (**Español e Inglés**), diseño intuitivo inspirado en x360ce, emulación de hasta **12 mandos virtuales** simultáneos (**Xbox 360**, **Xbox One**, **PlayStation 4 DualShock 4**, **PlayStation 5 DualSense** y **Nintendo Switch 2 Pro**) e integración opcional con **Nefarius HidHide** para erradicar el problema de "doble entrada" en juegos de PC y emuladores.

Diseñado con arquitectura multiplataforma: funcionamiento nativo en **Windows (10/11)** y con **soporte completo para Linux (Beta)** gracias a VIIPER y al protocolo estándar USB/IP.

Permite asociar periféricos físicos reales (mandos USB o Bluetooth DirectInput/XInput, joysticks genéricos, volantes, teclado y ratón) a cada mando virtual, calibrar curvas analógicas en tiempo real y probar la respuesta reactiva directamente sobre un diagrama vectorial interactivo.

---

## 📸 Capturas de Pantalla

| Mapeo Xbox 360 | Mapeo DualShock 4 |
|:---:|:---:|
| [![Mapeo Xbox 360](assets/screenshot_main.png)](assets/screenshot_main.png) | [![Mapeo DualShock 4](assets/screenshot_main2.png)](assets/screenshot_main2.png) |
| **Calibración de Sticks Analógicos** | **Configuración y Selección de Drivers** |
| [![Calibración de Sticks](assets/screenshot_sticks.png)](assets/screenshot_sticks.png) | [![Configuración](assets/screenshot_settings.png)](assets/screenshot_settings.png) |

---

## 🎮 Características Principales

### 1. Soporte Extendido de 1 a 12 Mandos Simultáneos
- Configura libremente la cantidad de mandos virtuales activos (de 1 a 12) desde la ventana de **`⚙ Configuración...`**.
- Pestañas individuales e independientes para cada jugador (`Control 1` a `Control 12`).

### 2. Arquitectura de Doble Controlador (VIIPER y ViGEmBus)
- **Driver VIIPER (Recomendado / Por defecto en nuevas instalaciones)**:
  - Arquitectura moderna basada en el protocolo USB/IP.
  - Basado en una versión personalizada y optimizada de [JuanJSAR93/VIIPER](https://github.com/JuanJSAR93/VIIPER) (fork de [Alia5/VIIPER](https://github.com/Alia5/VIIPER)), incorporando soporte nativo para **Xbox One (protocolo GIP)** y una correcta localización/enumeración de dispositivos emulados.
  - Binario autónomo `bin/viiper.exe` incluido directamente en la aplicación (se inicia y gestiona en segundo plano automáticamente).
  - Desbloquea la emulación de **Xbox 360**, **Xbox One (GIP)**, **PlayStation 4 (DualShock 4)**, **PlayStation 5 (DualSense)** y **Nintendo Switch 2 Pro (`ns2pro`)**.
  - Abre el camino a la compatibilidad nativa con **Linux (Beta)** mediante los módulos de kernel `usbip`.
- **Driver ViGEmBus**:
  - Controlador clásico a nivel de kernel para Windows que soporta mandos de **Xbox 360**, **DualShock 4** y modo **Mixto**.
  - 100% retrocompatible: las configuraciones previas existentes conservan ViGEmBus de forma automática.

### 3. Soporte de Emulación Multi-Consola
- **Xbox 360 (XInput)**: El estándar universal para juegos en Steam, Xbox Game Pass, Epic Games Store y emuladores.
- **Xbox One (GIP / XInput)**: Emulación oficial mediante el protocolo **GIP (General Input Protocol)** de Microsoft a través de VIIPER (`authorized-xboxone`). El sistema Windows PnP lo reconoce e instala como un mando nativo de Xbox One, con soporte completo XInput, ideal para juegos modernos de Windows Store, Xbox Game Pass y títulos que requieren el estándar moderno de Xbox One.
- **PlayStation 4 (DualShock 4)**: DirectInput / Sony HID nativo, con iconos oficiales de PlayStation en juegos compatibles.
- **PlayStation 5 (DualSense)**: Emulación del layout oficial de PS5 con respuesta analógica completa.
- **Nintendo Switch 2 Pro (`ns2pro`)**: Disposición auténtica de Nintendo (B/A, Y/X, L/ZL, R/ZR, -, +, Home) con rango escalado $0 \dots 4095$ y punto central calibrado en $2048$.
- **Modo Mixto**: Divide automáticamente los mandos creados entre Xbox 360/Xbox One y PlayStation/Nintendo para partidas combinadas.

### 4. Visión Multiplataforma: Windows y Linux (Beta)
- **Windows**: Compatible de fábrica mediante el driver `usbip-win2` o `ViGEmBus`.
- **Linux (Beta)**: Integración directa mediante los módulos de kernel de Linux (`usbip` / `vhci-hcd`), binario ELF nativo y VIIPER para Linux.

### 5. Activación Inteligente y Aislamiento de Mandos Virtuales
- **Sin mandos fantasma**: Solo se instancian en el sistema los mandos virtuales que tengan asignado y habilitado un periférico físico real.
- **Identificación Precisa de Dispositivos Virtuales vs. Físicos**: Gracias a nuestra versión personalizada de VIIPER y al rastreo del árbol PnP de Windows (`cfgmgr32.dll`), el gestor de periféricos inspecciona la raíz del bus de hardware y las descripciones en tiempo de ejecución para diferenciar con total fiabilidad los mandos emulados de los periféricos físicos reales. Esto corrige por completo el fallo de versiones anteriores donde mandos físicos oficiales de Xbox 360, DualShock 4, DualSense y Switch 2 Pro eran omitidos al confundirse erróneamente con dispositivos virtuales.

### 6. Soporte Bilingüe Integrado (Español e Inglés)
- Toda la interfaz, cuadros de diálogo, avisos del sistema, tablas de periféricos e información de hardware están traducidos al 100%.
- Selección de idioma accesible en cualquier momento desde **`⚙ Configuración...`** -> **`Idioma de la Interfaz`**.

### 7. Integración Opcional con Nefarius HidHide (Anti Doble Entrada)
- **Completamente Opcional**: Si HidHide no está instalado en tu equipo, j360More funciona con total normalidad.
- **Ocultamiento Dinámico**: Al pulsar **`▶ Iniciar Emulación`**, j360More oculta de inmediato los periféricos seleccionados para todo Windows mediante HidHide, permitiendo que **solo j360More** pueda leerlos (gracias a la lista blanca automática). Al pulsar **`⏹ Detener Emulación`** (o cerrar la app), los periféricos vuelven a ser visibles para todo el sistema automáticamente.

### 8. Diagramas Vectoriales Interactivos y LEDs Reactivos
- Diagramas vectoriales de alta fidelidad para **Xbox 360**, **DualShock 4**, **DualSense** y **Switch 2 Pro**.
- **Mapeo por Clic**: Haz clic directo sobre cualquier botón o palanca del dibujo del mando para iniciar su asignación instantánea.
- **LEDs Reactivos Glow**: Cada botón, gatillo, cruceta o movimiento de stick se ilumina en tiempo real al pulsarlo en tu mando físico.

### 9. Calibración Especializada de Gatillos y Sticks
- **Sub-pestaña `Triggers` (Gatillos LT / RT / ZL / ZR / L2 / R2)**: Curva cuadrática de respuesta en tiempo real, Dead Zone, Anti-Dead Zone, Sensibilidad e Inversión.
- **Sub-pestaña `Sticks` (Sticks Izquierdo y Derecho)**: Visualizador cartesiano 2D interactivo con retícula, posición actual, círculos de Dead Zone y Anti-Dead Zone, curva de sensibilidad radial e inversión X/Y.

### 10. Soporte Multi-Teclado Independiente (Zero Cross-Talk)
- Conecta múltiples teclados físicos USB, Bluetooth o integrados de laptop y asígnalos a mandos virtuales de jugadores separados sin interferencia entre teclas, gracias a Windows Raw Input.

---

## 📋 Requisitos del Sistema

### Sistema Operativo:
- **Windows 10 / 11 (64-bit)** (Soportado actualmente)
- **Linux (x86_64)** (*Beta mediante binario ELF y USB/IP*)

### Controladores de Emulación Requeridos:
Elige uno de los dos controladores soportados:
1. **Controlador VIIPER (Por defecto / Multiplataforma)**:
   - El ejecutable `bin/viiper.exe` ya viene preempaquetado con j360More.
   - Requiere la instalación del driver **usbip-win2** en Windows (`C:\Program Files\USBip`).
   - Descarga oficial: [usbip-win2 Releases (GitHub)](https://github.com/vadimgrn/usbip-win2/releases)
2. **Controlador ViGEmBus (Solo Windows)**:
   - Requiere el controlador **ViGEmBus** instalado en Windows.
   - Descarga oficial: [ViGEmBus Releases (GitHub)](https://github.com/nefarius/ViGEmBus/releases)

> **❓ ¿Por qué es obligatorio instalar usbip-win2 o ViGEmBus?**  
> Windows no permite que las aplicaciones creen dispositivos de entrada virtuales sin un controlador firmado a nivel de sistema.  
> - **Si usas VIIPER (predeterminado)**: necesitas el driver **usbip-win2** para comunicar y exponer los mandos por USB/IP (soportando Xbox 360, Xbox One GIP, DualShock 4, DualSense y Switch 2 Pro).  
> - **Si usas ViGEmBus (alternativo tradicional)**: necesitas el driver **ViGEmBus** (soportando Xbox 360 y DualShock 4).  
> Sin al menos uno de ellos instalado, Windows no podrá instanciar los mandos virtuales para tus juegos.

### Opcional:
- **Nefarius HidHide**: Evita la doble entrada en juegos cuando se utilizan periféricos físicos DirectInput.
  - Descarga oficial: [HidHide Releases (GitHub)](https://github.com/nefarius/HidHide/releases)

---

## 🛠 Instalación y Uso desde Código Fuente

### 1. Clonar el repositorio
```powershell
git clone https://github.com/JuanJSAR93/j360More-Xbox_360_Controller_Emulator.git
cd j360More-Xbox_360_Controller_Emulator
```

### 2. Crear y Activar entorno virtual
```powershell
python -m venv venv
.\venv\Scripts\activate
```

### 3. Instalar dependencias
```powershell
pip install -r requirements.txt
```

### 4. Ejecutar la aplicación
```powershell
python gui_app.py
```

---

## 📦 Compilación a Ejecutables Standalone

### Windows:
Para compilar el ejecutable portable standalone (`dist\j360More.exe`) con icono oficial, metadatos de versión y el demonio VIIPER integrado:
```cmd
build_windows.bat
```

### Linux (Docker):
Para compilar el binario nativo ELF y paquete de distribución para Linux (`dist/j360More` y `dist/j360More-v1.5.0-linux-x86_64.tar.gz`):
```cmd
build_linux.bat
```
*(En entornos host de Linux, puedes ejecutar directamente `./build_linux.sh`)*

---

## 📂 Estructura del Proyecto

```text
xbox_multi_emulator/
├── assets/                     # Recursos visuales e iconos (SVG, ICO, PNG)
│   ├── icon.svg                # Icono vectorial oficial del proyecto
│   ├── icon.ico                # Icono multirresolución compilado de Windows
│   ├── controller_360.svg      # Diagrama vectorial detallado de Xbox 360
│   ├── controller_DS4.svg      # Diagrama vectorial de PlayStation 4
│   ├── controller_DS5.svg      # Diagrama vectorial de PlayStation 5
│   └── web_pad/                # Interfaz táctil HTML5/JS AirPad para smartphones
├── bin/                        # Binarios auxiliares del backend
│   ├── viiper-amd64.exe        # Servidor de emulación USB/IP VIIPER (Windows x64 / AMD64)
│   ├── viiper_arm64.exe        # Servidor de emulación USB/IP VIIPER (Windows ARM64)
│   ├── viiper-amd64            # Servidor de emulación USB/IP VIIPER (Linux x86_64 / AMD64)
│   └── viiper-arm64            # Servidor de emulación USB/IP VIIPER (Linux ARM64 / AArch64)
├── docs/                       # Página web oficial para GitHub Pages (Bilingüe)
│   ├── assets/                 # Recursos gráficos web
│   ├── index.html              # Landing page principal
│   ├── script.js               # Lógica interactiva y selector de idioma
│   └── styles.css              # Estilos Cyber Gaming
├── dist/                       # Salida de compilación y empaquetado
│   ├── j360More.exe            # Ejecutable portable standalone para Windows
│   ├── j360More-*-windows-amd64.zip # Paquete de distribución Windows AMD64 (j360More.exe + viiper-amd64.exe)
│   ├── j360More-*-windows-arm64.zip # Paquete de distribución Windows ARM64 (j360More.exe + viiper_arm64.exe)
│   ├── j360More-*-linux-amd64.tar.gz # Paquete de distribución Linux AMD64 (j360More + viiper-amd64)
│   └── j360More-*-linux-arm64.tar.gz  # Paquete de distribución Linux ARM64 (j360More + viiper-arm64)
├── config_mapping.json         # Configuración base en JSON
├── driver_manager.py           # Administrador de detección de ViGEmBus, VIIPER e HidHide
├── emulator.py                 # Punto de entrada y modos consola/test
├── emulator_engine.py          # Motor de emulación híbrido a 120Hz (ViGEmBus y VIIPER)
├── gui_app.py                  # Interfaz gráfica principal Tkinter/TTK y SplashScreen
├── i18n.py                     # Módulo de internacionalización (Multilenguaje)
├── input_devices.py            # Detección SDL2 en caliente, correlación PnP y exclusión de virtuales
├── raw_keyboard.py             # Gestor de multi-teclado Raw Input (Zero Cross-Talk)
├── viiper_backend.py           # Cliente IPC/TCP nativo para VIIPER (Xbox 360, Xbox One GIP, DS4, PS5, Switch 2)
├── web_gamepad_server.py       # Servidor HTTP y WebSocket de AirPad para mandos móviles
├── version_info.txt            # Metadatos del ejecutable y derechos de autor
└── requirements.txt            # Dependencias de Python
```

---

## 📄 Licencia y Créditos
- **Creador y Desarrollador Principal**: **JuanJSAR** ([@JuanJSAR93](https://github.com/JuanJSAR93))
- **VIIPER**: Desarrollado por Alia5 ([VIIPER Original en GitHub](https://github.com/Alia5/VIIPER)), posibilitando la emulación multiplataforma de mandos USB virtuales mediante USB/IP. **j360More** incluye y mantiene una compilación mejorada y modificada por JuanJSAR ([JuanJSAR93/VIIPER: Virtual Input over IP Emulator](https://github.com/JuanJSAR93/VIIPER)) con soporte nativo para Xbox One GIP y una correcta localización/enumeración de dispositivos emulados.
- **usbip-win2**: Desarrollado por vadimgrn ([usbip-win2 en GitHub](https://github.com/vadimgrn/usbip-win2)).
- **ViGEmBus e HidHide**: Creados por Benjamin Höglinger-Stelzer (Nefarius Software Solutions).
- **pygame-ce (SDL2)**: Detección en caliente y lectura de eventos de periféricos.
- Diseñado para entusiastas de juegos locales multijugador en PC de todo el mundo.
