# j360More - Multi-Gamepad Emulator (1 to 12 Xbox 360 Controllers)

[📖 Leer en Español](README_es.md) | [Official Releases](https://github.com/JuanJSAR93/j360More-Xbox_360_Controller_Emulator/releases) | [Web Documentation](https://juanjsar93.github.io/j360More-Xbox_360_Controller_Emulator/)

> **Developed by JuanJSAR**  
> Official Repository: [GitHub - JuanJSAR93/j360More](https://github.com/JuanJSAR93/j360More-Xbox_360_Controller_Emulator)  
> Downloads & Releases: [Official Releases](https://github.com/JuanJSAR93/j360More-Xbox_360_Controller_Emulator/releases)  
> Web Documentation (GitHub Pages): `/docs` folder

**j360More** is an advanced multi-controller virtual gamepad solution developed by **JuanJSAR**. Supporting both **VIIPER** (multiplatform USB/IP) and **ViGEmBus** backends, it features a modern bilingual interface (**English and Spanish**), an intuitive layout inspired by x360ce, support for up to **12 simultaneous virtual controllers** (**Xbox 360**, **DualShock 4**, **DualSense (PS5)**, and **Nintendo Switch 2 Pro**), and optional integration with **Nefarius HidHide** to eliminate the double-input issue in PC games and emulators.

Map real physical hardware (DirectInput/XInput gamepads via USB or Bluetooth, generic arcade sticks, steering wheels, keyboard and mouse) to each virtual controller, calibrate analog response curves in real time, and monitor reactive input feedback directly on an interactive vector diagram.

---

## 📸 Application Screenshots

| Xbox 360 Mapping | DualShock 4 Mapping |
|:---:|:---:|
| [![Xbox 360 Mapping](assets/screenshot_main.png)](assets/screenshot_main.png) | [![DualShock 4 Mapping](assets/screenshot_main2.png)](assets/screenshot_main2.png) |
| **Analog Sticks Calibration** | **Settings & HidHide Integration** |
| [![Analog Sticks](assets/screenshot_sticks.png)](assets/screenshot_sticks.png) | [![Settings](assets/screenshot_settings.png)](assets/screenshot_settings.png) |

---

## 🎮 Key Features

### 1. Extended Support for 1 to 12 Simultaneous Controllers
- Adjust the number of active virtual gamepads (from 1 to 12) from the **`⚙ Settings...`** modal.
- Dedicated, independent tabs for each player (`Controller 1` to `Controller 12`).

### 2. Built-in Bilingual Interface (English & Spanish)
- Complete, 100% localization for every menu, dialog, system prompt, device table, and hardware inspection view.
- Easily toggle languages at any time via **`⚙ Settings...`** -> **`Interface Language`**.

### 3. Smart Activation & Mapping Protection
- If a controller tab is set to `-- None / Disconnected --`:
  - The **`[ ] Enabled`** checkbox is automatically disabled and set to `False`.
  - All mapping inputs (comboboxes, quick-record `...` buttons, calibration curves, canvas) are **dimmed and disabled**.
  - **No phantom controllers**: ViGEmBus only instantiates virtual gamepads on Windows that have a physical device assigned and enabled.
  - If you attempt to start emulation without any assigned peripherals, the app notifies you and avoids creating redundant devices.
- Selecting any physical device (Gamepad, Keyboard, or Mouse) immediately reactivates all controls and the enable checkbox.

### 4. Optional Nefarius HidHide Integration (Anti Double-Input)
- **Completely Optional**: If HidHide is not installed on your system, j360More works normally for virtual controller emulation.
- **Gentle Notification**: If HidHide is absent, a non-intrusive prompt appears with a **`[ ] Do not show this warning again`** checkbox.
- **Custom Path**: In `⚙ Settings...`, check driver status, toggle global cloaking, or browse directly to `HidHideCLI.exe` using **`📂 Browse...`**.
- **Management in `🎮 DirectInput Devices...`**:
  - Device list with dedicated **`HidHide`** status column (`🚫 Cloaked` vs `👁 Visible`).
  - **`🔒 Cloak on Emulation`** and **`🔓 Keep Visible`** toolbar buttons (safely disabled if HidHide is not installed).
  - **Dynamic Cloaking**: Clicking **`▶ Start Emulation`** immediately cloaks selected physical devices for all Windows applications, allowing **only j360More** to read them (via automatic process whitelisting). Stopping emulation (or closing the app) instantly restores visibility system-wide.

### 5. Interactive Vector Diagrams (Xbox 360 & DualShock 4)
- High-fidelity vector rendering for both **Xbox 360** (`controller_360.svg`) and **DualShock 4** (`controller_DS4.svg`) controllers.
- Full support for **Xbox 360**, **DualShock 4**, and **Mixed** (half Xbox 360, half DS4 in even multiples: 2, 4, 6, 8, 10, 12) emulation modes.
- **Click-to-Map**: Click directly on any button or stick on the controller illustration to trigger instant button mapping.
- **Reactive Glow LEDs**: Every button press, trigger pull, D-pad direction, or stick motion illuminates in real time.
- **Assignment Halo**: A pulsing visual indicator highlights the exact component waiting for physical input.

### 6. Specialized Analog Calibration for Triggers & Sticks
- **`Triggers` Tab (LT / RT)**:
  - Real-time quadratic input response curve (DirectInput vs XInput).
  - Configurable **Dead Zone**, **Anti-Dead Zone**, **Sensitivity**, and **Invert**.
- **`Sticks` Tab (Left & Right Sticks)**:
  - 2D Cartesian display with grid, live green position indicator, Dead Zone circle, and Anti-Dead Zone circle.
  - Radial sensitivity response curve visualization.
  - Controls for **Dead Zone**, **Anti-Dead Zone**, **Sensitivity**, **Invert X Axis**, and **Invert Y Axis**.
- **Dual Numeric & Slider Input**: All parameters support both slider adjustment and direct numeric input (including percentage values `%`).

### 7. Productivity & Utilities
- **`...` Quick-Record Button**: Click and press the button/axis on your physical controller to assign it instantly without searching lists.
- **`📋 Copy Mapping to...` Button**: Duplicate button configuration and calibration to another controller tab (or all controllers) without overwriting assigned physical devices.
- **`🎮 Open joy.cpl` Button**: Direct shortcut to the native Windows Game Controllers control panel.
- **Hardware Inspector**: View vendor name, product name, VID, PID, SDL GUID, Instance ID, and connection type (USB/BT).

---

## 📋 System Requirements

### Mandatory:
- **Windows 10 or Windows 11 (64-bit)**.
- **ViGEmBus Driver**: Required to spawn virtual Xbox 360 gamepads in Windows.
  - Official Download: [ViGEmBus Releases (GitHub)](https://github.com/nefarius/ViGEmBus/releases)

### Optional:
- **Nefarius HidHide**: Recommended when playing games that detect generic DirectInput devices alongside virtual Xbox 360 pads, preventing double-input conflicts.
  - Official Download: [HidHide Releases (GitHub)](https://github.com/nefarius/HidHide/releases)

---

## 🛠 Installation & Running from Source

### 1. Clone the repository
```powershell
git clone https://github.com/JuanJSAR93/j360More-Xbox_360_Controller_Emulator.git
cd j360More-Xbox_360_Controller_Emulator
```

### 2. Create and Activate a Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\activate
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Run the Application
```powershell
python gui_app.py
```

---

## 📦 Building Standalone Executable (.exe)

To build the standalone portable executable (`dist\j360More.exe`) with the official icon and no console flashing:

```powershell
pyinstaller --noconfirm --onefile --windowed --noupx --name "j360More" --icon "assets\icon.ico" --add-data "assets;assets" --collect-all "vgamepad" --collect-all "resvg_py" gui_app.py
```

The output executable will be generated at `dist\j360More.exe`, ready to run alongside `config_mapping.json`.

---

## 📂 Project Structure

```text
xbox_multi_emulator/
├── assets/                     # Visual assets and icons (SVG, ICO, PNG)
│   ├── icon.svg                # Official project vector icon
│   ├── icon.ico                # Multi-resolution compiled Windows icon
│   ├── controller.svg          # Xbox 360 vector diagram
│   └── controller_render.png   # High-resolution render
├── docs/                       # Official GitHub Pages website (Bilingual)
│   ├── assets/                 # Web visual assets
│   ├── index.html              # Main landing page
│   ├── script.js               # Interactive logic & language toggle
│   └── styles.css              # Cyber Gaming UI styles
├── dist/                       # Output distribution
│   ├── j360More.exe            # Standalone portable executable
│   └── config_mapping.json     # Persistent controller mapping configuration
├── config_mapping.json         # Base configuration in JSON
├── driver_manager.py           # ViGEmBus and HidHide driver manager
├── emulator.py                 # Entry point & console/test modes
├── emulator_engine.py          # 120Hz emulation loop using vgamepad
├── gui_app.py                  # Main Tkinter/TTK graphical user interface
├── i18n.py                     # Internationalization module (Spanish / English)
├── input_devices.py            # SDL2 hotplug detection and PnP correlation
└── requirements.txt            # Python dependencies
```

---

## 📄 License & Credits
- **Creator & Lead Developer**: **JuanJSAR** ([@JuanJSAR93](https://github.com/JuanJSAR93))
- Virtual gamepad emulation powered by **ViGEmBus** and **HidHide** created by Benjamin Höglinger-Stelzer (Nefarius Software Solutions).
- Hotplug detection and input handling provided by **pygame-ce** (SDL2).
- Built for local multiplayer PC gaming enthusiasts worldwide.
