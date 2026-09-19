# j360More - Emulador Multimando (1 a 12 Mandos Xbox 360)

[📖 Read in English](README.md) | [Descargas Oficiales (Releases)](https://github.com/JuanJSAR93/j360More-Xbox_360_Controller_Emulator/releases) | [Documentación Web](https://juanjsar93.github.io/j360More-Xbox_360_Controller_Emulator/)

> **Desarrollado por JuanJSAR**  
> Repositorio Oficial: [GitHub - JuanJSAR93/j360More](https://github.com/JuanJSAR93/j360More-Xbox_360_Controller_Emulator)  
> Descargas y Versiones: [Releases Oficiales](https://github.com/JuanJSAR93/j360More-Xbox_360_Controller_Emulator/releases)  
> Documentación Web (GitHub Pages): Carpeta `/docs`

**j360More** es una solución avanzada de emulación multi-mando para Windows desarrollada por **JuanJSAR** sobre el controlador kernel **ViGEmBus**, con soporte bilingüe (**Español e Inglés**), interfaz gráfica moderna inspirada en x360ce, soporte para hasta **12 mandos virtuales de Xbox 360** simultáneos e integración opcional con **Nefarius HidHide** para erradicar el molesto problema de "doble entrada" (doble mando) en juegos de PC y emuladores.

Permite asociar periféricos físicos reales (mandos USB o Bluetooth DirectInput/XInput, joysticks genéricos, volantes, teclado y ratón) a cada mando virtual, calibrar curvas analógicas en tiempo real y probar la respuesta reactiva directamente sobre un diagrama vectorial interactivo.

---

## 📸 Capturas de Pantalla

| Mapeo Xbox 360 | Mapeo DualShock 4 |
|:---:|:---:|
| [![Mapeo Xbox 360](assets/screenshot_main.png)](assets/screenshot_main.png) | [![Mapeo DualShock 4](assets/screenshot_main2.png)](assets/screenshot_main2.png) |
| **Calibración de Sticks Analógicos** | **Configuración e Integración HidHide** |
| [![Calibración de Sticks](assets/screenshot_sticks.png)](assets/screenshot_sticks.png) | [![Configuración](assets/screenshot_settings.png)](assets/screenshot_settings.png) |

---

## 🎮 Características Principales

### 1. Soporte Extendido de 1 a 12 Mandos Simultáneos
- Configura libremente la cantidad de mandos virtuales activos (de 1 a 12) desde la ventana de **`⚙ Configuración...`**.
- Pestañas individuales e independientes para cada jugador (`Control 1` a `Control 12`).

### 2. Soporte Bilingüe Integrado (Español e Inglés)
- Toda la interfaz, cuadros de diálogo, avisos del sistema, tablas de periféricos e información de hardware están traducidos al 100%.
- Selección de idioma accesible en cualquier momento desde **`⚙ Configuración...`** -> **`Idioma de la Interfaz`**.

### 3. Activación Inteligente y Bloqueo de Mapeo sin Dispositivo
- Si un control tiene asignado `-- Ninguno / Desconectado --`:
  - La casilla **`[ ] Habilitado`** se bloquea de forma opaca (`disabled`) con valor `False`.
  - Todas las opciones de mapeo (comboboxes, botones `...`, curvas de calibración, canvas) quedan **desactivadas y opacas**.
  - **ViGEmBus no crea mandos fantasma**: solo se instancian en el sistema los mandos que tienen un periférico físico asignado y habilitado.
  - Si intentas iniciar la emulación sin ningún periférico asignado a ningún control, la app muestra un aviso preventivo y no inicia mandos innecesarios.
- Al seleccionar un dispositivo (Joystick, Teclado o Ratón), todas las opciones y la casilla de habilitación se reactivan automáticamente.

### 4. Integración Opcional con Nefarius HidHide (Anti Doble Entrada)
- **Completamente Opcional**: Si HidHide no está instalado en tu equipo, j360More funciona con total normalidad para emular controles.
- **Aviso Informativo Suave**: Si no se detecta HidHide, la app muestra un aviso leve con la casilla **`[ ] No volver a mostrar este aviso`** para no interrumpirte.
- **Ruta Personalizada**: En `⚙ Configuración...` puedes ver el estado del driver, activar/desactivar el *Cloaking* global y especificar manualmente la ruta a `HidHideCLI.exe` con el botón **`📂 Examinar...`**.
- **Gestión en `🎮 Dispositivos DirectInput...`**:
  - Tabla con columna **`HidHide`** (`🚫 Oculto` vs `👁 Visible`).
  - Botones **`🔒 Ocultar al Emular`** y **`🔓 Mantener Visible`** (se muestran deshabilitados si HidHide no está presente).
  - **Ocultamiento Dinámico**: Al pulsar **`▶ Iniciar Emulación`**, j360More oculta de inmediato los periféricos seleccionados para todo Windows mediante HidHide, permitiendo que **solo j360More** pueda leerlos (gracias a la lista blanca automática). Al pulsar **`⏹ Detener Emulación`** (o cerrar la app), los periféricos vuelven a ser visibles para todo el sistema automáticamente.

### 5. Diagramas Vectoriales Interactivos (Xbox 360 y DualShock 4)
- Diagramas renderizados en alta fidelidad tanto para mandos **Xbox 360** (`controller_360.svg`) como **DualShock 4** (`controller_DS4.svg`).
- Compatibilidad total con modos de emulación **Xbox 360**, **DualShock 4** y **Mixto** (mitad Xbox 360 y mitad DS4 en múltiplos pares: 2, 4, 6, 8, 10, 12).
- **Mapeo por Clic**: Haz clic directo sobre cualquier botón o palanca del dibujo del mando para iniciar su asignación instantánea.
- **LEDs Reactivos Glow**: Cada botón, gatillo, cruceta o movimiento de stick se ilumina en tiempo real al pulsarlo en tu mando físico.
- **Halo de Asignación**: Indicador visual pulsante sobre el componente que está esperando que presiones un botón o tecla.

### 6. Calibración Especializada de Gatillos y Sticks
- **Sub-pestaña `Triggers` (Gatillos LT / RT)**:
  - Gráfica cuadrática de respuesta en tiempo real (DI vs XI).
  - Ajustes de **Dead Zone (Zona Muerta)**, **Anti-Dead Zone**, **Sensibilidad** e **Inversión**.
- **Sub-pestaña `Sticks` (Sticks Izquierdo y Derecho)**:
  - Visualizador cartesiano 2D con retícula, punto verde de posición actual, y círculos de Dead Zone y Anti-Dead Zone.
  - Gráfica de curva de sensibilidad de respuesta angular y magnitud.
  - Controles de **Dead Zone**, **Anti-Dead Zone**, **Sensibilidad**, **Invertir Eje X** e **Invertir Eje Y**.
- **Entrada Numérica Dual**: Cada parámetro cuenta con un slider de pasos enteros y un campo numérico para ingresar valores exactos o decimales con `%`.

### 7. Productividad y Utilidades
- **Botón `...` (Captura Rápida / Record)**: Presiónalo y oprime el botón o eje de tu mando para mapearlo al instante sin buscarlo en listas.
- **Botón `📋 Copiar Mapeo a...`**: Duplica la configuración de botones y calibración hacia otro mando (o a todos los demás) sin sobreescribir el periférico asignado a cada uno.
- **Botón `🎮 Abrir joy.cpl`**: Acceso directo al panel de dispositivos de juego nativo de Windows.
- **Inspección de Hardware**: Consulta VID, PID, GUID SDL, Instance ID y tipo de conexión (USB/BT).

---

## 📋 Requisitos del Sistema

### Obligatorios:
- **Windows 10 o Windows 11 (64-bit)**.
- **Controlador ViGEmBus**: Necesario para crear los mandos virtuales de Xbox 360 en el sistema.
  - Descarga oficial: [ViGEmBus Releases (GitHub)](https://github.com/nefarius/ViGEmBus/releases)

### Opcionales:
- **Nefarius HidHide**: Recomendado si vas a jugar títulos que detectan periféricos DirectInput genéricos simultáneamente con mandos de Xbox 360, evitando la doble pulsación.
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

## 📦 Compilación a Ejecutable (.exe)

Para generar el ejecutable standalone portátil (`dist\j360More.exe`) con icono oficial y sin consolas emergentes:

```powershell
pyinstaller --noconfirm --onefile --windowed --noupx --name "j360More" --icon "assets\icon.ico" --add-data "assets;assets" --collect-all "vgamepad" --collect-all "resvg_py" gui_app.py
```

El binario compilado se ubicará en `dist\j360More.exe` listo para ejecutarse de forma independiente junto a `config_mapping.json`.

---

## 📂 Estructura del Proyecto

```text
xbox_multi_emulator/
├── assets/                     # Recursos visuales e iconos (SVG, ICO, PNG)
│   ├── icon.svg                # Icono vectorial oficial del proyecto
│   ├── icon.ico                # Icono multirresolución compilado de Windows
│   ├── controller.svg          # Diagrama vectorial del mando Xbox 360
│   └── controller_render.png   # Render de alta resolución
├── docs/                       # Página web oficial para GitHub Pages (Bilingüe)
│   ├── assets/                 # Recursos gráficos web
│   ├── index.html              # Landing page principal
│   ├── script.js               # Lógica interactiva y selector de idioma
│   └── styles.css              # Estilos Cyber Gaming
├── dist/                       # Binario compilado y configuración
│   ├── j360More.exe            # Ejecutable portable standalone
│   └── config_mapping.json     # Mapeo persistente de controles
├── config_mapping.json         # Configuración base en JSON
├── driver_manager.py           # Administrador de controladores ViGEmBus e HidHide
├── emulator.py                 # Punto de entrada y modos consola/test
├── emulator_engine.py          # Motor de emulación a 120Hz con vgamepad
├── gui_app.py                  # Interfaz gráfica principal Tkinter/TTK
├── i18n.py                     # Módulo de internacionalización (Español / Inglés)
├── input_devices.py            # Detección SDL2 en caliente y correlación PnP
└── requirements.txt            # Dependencias de Python
```

---

## 📄 Licencia y Créditos
- **Creador y Desarrollador Principal**: **JuanJSAR** ([@JuanJSAR93](https://github.com/JuanJSAR93))
- Emulación del bus de control virtual impulsada por **ViGEmBus** y **HidHide** creados por Benjamin Höglinger-Stelzer (Nefarius Software Solutions).
- Soporte para detección en caliente y periféricos provisto por **pygame-ce** (SDL2).
- Diseñado para entusiastas de juegos locales multijugador en PC de todo el mundo.
