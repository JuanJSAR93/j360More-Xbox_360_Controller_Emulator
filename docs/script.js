// j360More Official Website Script with Bilingual Support (ES / EN)
// Developed by JuanJSAR

const translations = {
  es: {
    nav_features: "Cualidades",
    nav_dual: "Emulación Dual",
    nav_screenshots: "Capturas",
    nav_drivers: "Controladores",
    nav_requirements: "Requisitos",
    nav_quickstart: "Guía Rápida",
    nav_faq: "Preguntas",
    nav_download: "Descargar",
    hero_badge_players: "🎮 Hasta 12 Mandos Simultáneos",
    hero_badge_hz: "⚡ Ultra Baja Latencia 120Hz",
    hero_badge_multiplatform: "🐧 Windows & Linux (Próximamente)",
    hero_badge_rawkb: "⌨️ Multi-Teclado Raw Input",
    hero_badge_author: "👨‍💻 Creado por JuanJSAR",
    hero_subtitle: "Convierte cualquier control genérico USB, mando de PlayStation, Nintendo Switch, palanca arcade o múltiples teclados independientes en mandos oficiales de Xbox 360, DualShock 4, DualSense o Switch 2 Pro con precisión milimétrica y compatibilidad total.",
    hero_btn_releases: "Descargar j360More",
    hero_btn_drivers: "Ver Drivers Necesarios",
    hero_controller_tag: "Mapeo Interactivo en Tiempo Real",
    stat_controllers: "Mandos Virtuales Simultáneos",
    stat_refreshrate: "Tasa de Refresco y Despacho",
    stat_latency: "Latencia de Procesamiento",
    stat_compatibility: "Compatible con Juegos XInput",
    feat_tag: "Características Principales",
    feat_title: "Diseñado para la Mejor Experiencia Multijugador",
    feat_subtitle: "Diseñado para jugadores de PC, emuladores y salones arcade que necesitan conectar múltiples mandos sin conflictos de detección.",
    f1_title: "1 a 12 Jugadores Locales",
    f1_desc: "Rompe el límite clásico de 4 mandos. j360More permite crear de 1 hasta 12 slots independientes de Xbox 360, ideal para títulos multijugador masivos como Party Animals, Gang Beasts, emuladores y arcades.",
    f2_title: "Motor de 120Hz de Ultra Baja Latencia",
    f2_desc: "Hilo de ejecución dedicado que muestrea los eventos de palancas, botones y gatillos a 120 ciclos por segundo con respuesta inmediata sin input lag perceptible.",
    f3_title: "Calibración Analógica Milimétrica",
    f3_desc: "Ajuste fino de zonas muertas (deadzone), anti-deadzone para sticks con deriva o desgaste, curvas de sensibilidad dinámica y reversión de ejes X/Y para sticks y gatillos.",
    f4_title: "Filtro Selectivo con HidHide",
    f4_desc: "Oculta periféricos DirectInput físicos a nivel de driver para que los juegos solo detecten el mando emulado, eliminando para siempre el 'doble control' en FIFA, Rocket League y emuladores.",
    f5_title: "Detección Plug & Play en Caliente",
    f5_desc: "Reconexión automática de gamepads en caliente mediante SDL2. Si desconectas o reconectas un mando en mitad de la partida, j360More lo recupera al instante sin reiniciar.",
    f6_title: "Guardado Persistente en JSON",
    f6_desc: "Todas tus asignaciones de botones, dispositivos y calibraciones se guardan de forma limpia en config_mapping.json para transferir o respaldar en cualquier equipo.",
    f7_title: "Soporte Multi-Teclado Independiente",
    f7_desc: "Conecta 2 o más teclados físicos (USB, Bluetooth o laptop) y asígnalos a mandos virtuales de Xbox separados. Desarrollado sobre Windows Raw Input para garantizar cero interferencias cruzadas (Zero Cross-Talk).",
    f8_title: "Lanzador 'Juegos' (+4 Mandos)",
    f8_desc: "Pestaña dedicada para lanzar juegos multijugador con inyección automática de variables de entorno (FNA_GAMEPAD_NUM_GAMEPADS, etc.) escaladas en tiempo real para soportar hasta 12 mandos.",
    dual_tag: "Soporte Multi-Consola",
    dual_title: "Emulación de Xbox 360, PS4, PS5 y Switch 2 Pro",
    dual_subtitle: "j360More te permite elegir qué tipo de mando crear en tu sistema mediante los drivers VIIPER y ViGEmBus: Xbox 360, DualShock 4, DualSense (PS5), Nintendo Switch 2 Pro o modo Mixto simultáneo.",
    dual_xbox_badge: "XInput Nativo",
    dual_xbox_count: "1 a 12 Mandos",
    dual_xbox_title: "Mando Xbox 360 (XInput)",
    dual_xbox_desc: "El estándar principal en PC. Compatibilidad asegurada con títulos de Steam, Xbox Game Pass, Epic Games Store y emuladores modernos.",
    dual_ds4_badge: "DirectInput / Sony HID",
    dual_ds4_count: "1 a 12 Mandos",
    dual_ds4_title: "Mando PlayStation 4 (DualShock 4)",
    dual_ds4_desc: "Emulación de mandos PlayStation 4, ideal para juegos con soporte nativo de botones de PlayStation y emuladores como RPCS3, PCSX2 y DuckStation.",
    dual_dualsense_badge: "PlayStation 5 HID",
    dual_dualsense_count: "1 a 12 Mandos",
    dual_dualsense_title: "Mando PlayStation 5 (DualSense)",
    dual_dualsense_desc: "Emulación de mandos DualSense de PlayStation 5 mediante el driver VIIPER, con mapeo completo de botones y compatibilidad de última generación.",
    dual_switch_badge: "Nintendo HID",
    dual_switch_count: "1 a 12 Mandos",
    dual_switch_title: "Mando Nintendo Switch 2 Pro",
    dual_switch_desc: "Soporte para el nuevo mando Switch 2 Pro (ns2pro) con disposición de botones de Nintendo, calibración precisa de 12 bits y centrado neutro.",
    dual_mixed_badge: "Soporte Mixto Multi-Consola",
    dual_mixed_title: "¿Partidas combinadas? Usa el Modo Mixto",
    dual_mixed_desc: "Configura de 2 a 12 mandos y j360More dividirá la carga equitativamente entre diferentes plataformas para que tus amigos jueguen en simultáneo sin conflictos.",
    dual_chip_2: "🎮 2 Mandos Combinados",
    dual_chip_4: "🎮 4 Mandos Combinados",
    dual_chip_8: "🎮 8 Mandos Combinados",
    dual_chip_12: "🎮 12 Mandos Combinados",
    drivers_tag: "Drivers Indispensables",
    drivers_title: "Controladores del Sistema Necesarios",
    drivers_subtitle: "Para lograr una emulación nativa de ultra baja latencia sin bloatware, j360More se apoya en los controladores de referencia USB/IP y kernel.",
    driver_viiper_tag: "Por Defecto / Multiplataforma",
    driver_viiper_desc: "Potente servidor de emulación USB sobre red local (USB/IP) que permite crear mandos virtuales de última generación directamente en Windows y Linux (próximamente). El ejecutable ya viene incluido en j360More.",
    driver_viiper_why_title: "¿Para qué se utiliza en j360More?",
    driver_viiper_why_desc: "Es el nuevo motor de emulación predeterminado y multiplataforma. Permite generar mandos de Xbox 360, DualShock 4, DualSense (PS5) y Nintendo Switch 2 Pro. En Windows requiere el controlador complementario usbip-win2.",
    driver_viiper_b1: "Emulación de 4 familias de mandos: Xbox 360, PS4, PS5 y Switch 2 Pro.",
    driver_viiper_b2: "Arquitectura estándar USB/IP: soporte para Windows y Linux (próximamente).",
    driver_viiper_b3: "Binario autónomo incluido en 'bin/viiper.exe' sin instalaciones engorrosas.",
    driver_viiper_btn: "Descargar Driver usbip-win2 (GitHub)",
    driver_vigem_tag: "Alternativo (Windows)",
    driver_vigem_desc: "El Virtual Gamepad Emulation Bus es un driver de nivel de sistema (kernel-mode) clásico para Windows que genera mandos virtuales de Xbox 360 y DualShock 4.",
    driver_vigem_why_title: "¿Para qué se utiliza en j360More?",
    driver_vigem_why_desc: "Es el motor alternativo tradicional para usuarios de Windows con ViGEmBus previamente instalado. Permite crear mandos virtuales de Xbox 360 y DualShock 4 con máxima compatibilidad en Windows 10 y 11.",
    driver_vigem_b1: "Emulación nativa de 1 a 12 slots XInput en Windows.",
    driver_vigem_b2: "Compatibilidad total con gatillos analógicos y vibración.",
    driver_vigem_b3: "100% retrocompatible con configuraciones previas de j360More.",
    driver_vigem_btn: "Descargar ViGEmBus (GitHub Releases)",
    driver_hidhide_tag: "Recomendado (Opcional)",
    driver_hidhide_desc: "Un controlador de filtro de dispositivos HID que permite ocultar de forma selectiva periféricos de juego reales a todas las aplicaciones del sistema, excepto a los procesos que estén expresamente autorizados (como j360More).",
    driver_hidhide_why_title: "¿Para qué se utiliza en j360More?",
    driver_hidhide_why_desc: "Resuelve el clásico y molesto problema del 'doble mando' (double-input). Cuando conectas un control genérico o de PS4/PS5, muchos juegos detectan al mismo tiempo el mando físico y el mando virtual emulado, duplicando las pulsaciones. HidHide oculta el mando físico a los juegos dejando visible solo el mando Xbox 360 emulado.",
    driver_hidhide_b1: "Previene duplicación de botones y saltos dobles en menús.",
    driver_hidhide_b2: "Selección individual de qué periféricos ocultar desde la UI de j360More.",
    driver_hidhide_b3: "Totalmente opcional: j360More funciona sin él si tus juegos no sufren de doble entrada.",
    driver_hidhide_btn: "Descargar HidHide (GitHub Releases)",
    req_table_title: "Requisitos del Sistema",
    req_col_component: "Componente",
    req_col_minimum: "Requisito Mínimo",
    req_col_recommended: "Recomendado",
    req_row_os: "Sistema Operativo",
    req_row_os_val1: "Windows 10 / 11 (64-bit)",
    req_row_os_val: "Windows 11 / Linux (Próximamente)",
    req_row_drivers: "Driver de Emulación",
    req_row_drivers_val1: "VIIPER (con usbip-win2) o ViGEmBus",
    req_row_drivers_val2: "VIIPER (Multiplataforma: X360, DS4, PS5, Switch 2)",
    req_row_hidhide: "Driver HidHide",
    req_row_hidhide_val1: "Opcional (No requerido para arrancar)",
    req_row_hidhide_val2: "HidHide v1.2+ (Para evitar doble control)",
    req_row_inputs: "Periféricos de Entrada",
    req_row_inputs_val1: "Cualquier Gamepad USB / Bluetooth o Multi-Teclado Raw Input",
    req_row_inputs_val2: "Múltiples teclados independientes, DirectInput o mandos estándar",
    req_row_runtime: "Formato del Programa",
    req_row_runtime_val1: "Ejecutable standalone sin dependencias",
    req_row_runtime_val2: "Modo portátil directo con bin/viiper.exe",
    quick_tag: "Paso a Paso",
    quick_title: "Comienza a Jugar en Menos de 2 Minutos",
    quick_subtitle: "Sigue estos sencillos pasos para tener tus mandos listos.",
    q1_title: "Instala usbip-win2 o ViGEmBus",
    q1_desc: "Instala el driver usbip-win2 para el motor VIIPER (o ViGEmBus para el motor clásico). Solo debes hacerlo una vez.",
    q2_title: "Ejecuta j360More",
    q2_desc: "Abre el ejecutable j360More.exe. El programa detectará tus drivers y mandos conectados automáticamente.",
    q3_title: "Asigna tus Mandos",
    q3_desc: "En las pestañas 'Mando 1' al 'Mando 12', selecciona qué dispositivo físico controlará cada ranura virtual de Xbox 360.",
    q4_title: "¡Inicia y Juega!",
    q4_desc: "Pulsa 'Iniciar Emulación'. Windows creará inmediatamente los mandos virtuales y tus juegos responderán a la perfección.",
    code_title: "¿Deseas compilar el código tú mismo?",
    code_subtitle: "Puedes clonar el repositorio y ejecutar el compilador oficial de un solo clic:",
    copy_btn: "Copiar",
    faq_tag: "Dudas Habituales",
    faq_title: "Preguntas Frecuentes",
    faq_q1: "¿Por qué es obligatorio instalar usbip-win2 o ViGEmBus?",
    faq_a1: "Windows no permite crear dispositivos de control virtual sin un controlador firmado del sistema. Si utilizas el motor predeterminado VIIPER, requieres el driver complementario usbip-win2 para comunicar los mandos por USB/IP (soportando Xbox 360, PS4, PS5 y Switch 2 Pro). Si optas por el motor clásico alternativo, necesitas ViGEmBus. Sin al menos uno de ellos instalado, el sistema no puede crear los mandos virtuales reconocibles por tus juegos.",
    faq_q2: "¿Qué pasa si no tengo instalado HidHide?",
    faq_a2: "j360More funcionará perfectamente. HidHide solo es necesario si notas que tu juego recibe órdenes dobles al presionar un botón (porque detecta al mismo tiempo tu mando genérico y el mando emulado). Si tu juego solo lee XInput, ni siquiera notarás la diferencia.",
    faq_q3: "¿Puedo usar múltiples teclados para jugar con amigos como mandos independientes?",
    faq_a3: "¡Sí! Gracias a la integración nativa con Windows Raw Input, j360More detecta individualmente cada teclado físico conectado (USB, Bluetooth o integrado de laptop). Puedes conectar 2, 3 o más teclados y asignarlos a mandos separados (Mando 1, Mando 2, etc.) sin interferencia cruzada (Zero Cross-Talk): presionar teclas en el Teclado 1 jamás afectará los controles del Teclado 2.",
    faq_q4: "¿Cómo soluciono sticks con deriva (drift)?",
    faq_a4: "j360More incluye calibración analógica avanzada. En la pestaña de calibración puedes aumentar la 'Zona Muerta (Deadzone)' en un porcentaje para que los movimientos no deseados del stick sean completamente ignorados.",
    cta_title: "¡Lleva el Multijugador en PC al Siguiente Nivel!",
    cta_desc: "Descarga la última versión de j360More y disfruta de partidas locales con amigos sin complicaciones.",
    cta_btn: "Descargar Última Versión en GitHub",
    nav_screenshots: "Capturas",
    screenshots_tag: "Galería de la Aplicación",
    screenshots_title: "Interfaz Real de j360More en Acción",
    screenshots_subtitle: "Explora la interfaz moderna, limpia y potente diseñada para un control milimétrico y configuración sin esfuerzo.",
    s1_badge: "Xbox 360",
    s1_title: "Mapeo para Xbox 360",
    s1_desc: "Configuración y emulación de mandos Xbox 360 para hasta 12 jugadores independientes.",
    s1b_badge: "DualShock 4",
    s1b_title: "Mapeo para DualShock 4",
    s1b_desc: "Configuración y emulación de mandos DualShock 4, disponible en modo individual o en modo Mixto.",
    s2_badge: "Calibración",
    s2_title: "Ajuste Analógico de Sticks",
    s2_desc: "Ajuste de zona muerta para corregir deriva (drift), curvas de sensibilidad e inversión de ejes.",
    s3_badge: "Configuración",
    s3_title: "Opciones de Emulación y Drivers",
    s3_desc: "Selección del motor (VIIPER / ViGEmBus), tipo de mando (Xbox 360, DualShock 4, DualSense, Switch 2 Pro o Mixto), cantidad de mandos e idioma.",
    screenshot_zoom: "Haz clic para ampliar en alta resolución",
    footer_desc: "Emulador de mandos virtuales para Windows y Linux (próximamente). Diseñado y desarrollado por JuanJSAR para ofrecer la máxima velocidad, estabilidad y flexibilidad en entornos multijugador de 1 a 12 participantes.",
    footer_drivers_title: "Controladores",
    footer_links_title: "Enlaces y Proyecto",
    footer_releases: "Descargas / Releases"
  },
  en: {
    nav_features: "Features",
    nav_dual: "Dual Emulation",
    nav_screenshots: "Screenshots",
    nav_drivers: "Drivers",
    nav_requirements: "Requirements",
    nav_quickstart: "Quickstart",
    nav_faq: "FAQ",
    nav_download: "Download",
    hero_badge_players: "🎮 Up to 12 Controllers",
    hero_badge_hz: "⚡ Ultra Low Latency 120Hz",
    hero_badge_multiplatform: "🐧 Windows & Linux (Coming Soon)",
    hero_badge_rawkb: "⌨️ Multi-Keyboard Raw Input",
    hero_badge_author: "👨‍💻 Created by JuanJSAR",
    hero_subtitle: "Turn any generic USB controller, PlayStation gamepad, Nintendo Switch, arcade stick, or multiple independent keyboards into official Xbox 360, DualShock 4, DualSense, or Switch 2 Pro controllers with pinpoint accuracy and full compatibility.",
    hero_btn_releases: "Download j360More",
    hero_btn_drivers: "View Required Drivers",
    hero_controller_tag: "Real-Time Interactive Mapping",
    stat_controllers: "Simultaneous Virtual Controllers",
    stat_refreshrate: "Refresh & Dispatch Rate",
    stat_latency: "Processing Latency",
    stat_compatibility: "Compatible with XInput Games",
    feat_tag: "Core Features",
    feat_title: "Engineered for the Ultimate Multiplayer Experience",
    feat_subtitle: "Built for PC gamers, emulators, and arcade setups requiring multiple gamepads without device conflicts.",
    f1_title: "1 to 12 Local Players",
    f1_desc: "Break past the traditional 4-controller limit. j360More enables creating 1 to 12 independent Xbox 360 slots, perfect for party titles like Gang Beasts, Party Animals, emulators, and arcade cabinets.",
    f2_title: "120Hz Ultra Low Latency Engine",
    f2_desc: "Dedicated high-priority thread polling analog sticks, buttons, and triggers at 120 cycles per second for instantaneous response with zero noticeable input lag.",
    f3_title: "Millimeter Analog Calibration",
    f3_desc: "Fine-tune deadzones, anti-deadzones for worn or drifting sticks, dynamic sensitivity curves, and independent X/Y axis inversion for sticks and triggers.",
    f4_title: "Selective Driver Masking with HidHide",
    f4_desc: "Cloaks physical DirectInput devices at the driver level so games only see the virtual Xbox controller, permanently eliminating double-input issues in FIFA, Rocket League, and emulators.",
    f5_title: "Hot-Plug & Play Auto Detection",
    f5_desc: "Automatic real-time controller reconnection powered by SDL2. If a controller disconnects or reconnects mid-game, j360More recovers it seamlessly without restarting.",
    f6_title: "Persistent JSON Profiles",
    f6_desc: "All your button assignments, device pairings, and calibrations are neatly saved in config_mapping.json for effortless backup and migration across PCs.",
    f7_title: "Independent Multi-Keyboard Support",
    f7_desc: "Connect 2 or more physical keyboards (USB, wireless, or laptop) and map them to separate virtual Xbox controllers. Powered by Windows Raw Input with zero player cross-talk: typing on Keyboard 1 will never trigger actions on Keyboard 2.",
    f8_title: "Dedicated 'Games' Launcher (+4 Gamepads)",
    f8_desc: "Integrated launcher for local multiplayer titles with automatic environment variable scaling (FNA_GAMEPAD_NUM_GAMEPADS, etc.) dynamically matched to your active controller setup up to 12 gamepads.",
    dual_tag: "Multi-Console Support",
    dual_title: "Xbox 360, PS4, PS5 & Switch 2 Pro Emulation",
    dual_subtitle: "j360More allows you to choose what type of controller to spawn on your system using VIIPER and ViGEmBus: Xbox 360, DualShock 4, DualSense (PS5), Nintendo Switch 2 Pro, or simultaneous Mixed mode.",
    dual_xbox_badge: "Native XInput",
    dual_xbox_count: "1 to 12 Controllers",
    dual_xbox_title: "Xbox 360 Controller (XInput)",
    dual_xbox_desc: "The primary standard on PC. Seamless compatibility with titles on Steam, Xbox Game Pass, Epic Games Store, and modern emulators.",
    dual_ds4_badge: "DirectInput / Sony HID",
    dual_ds4_count: "1 to 12 Controllers",
    dual_ds4_title: "PlayStation 4 Controller (DualShock 4)",
    dual_ds4_desc: "PlayStation 4 controller emulation, ideal for games with native PlayStation layout support and emulators like RPCS3, PCSX2, and DuckStation.",
    dual_dualsense_badge: "PlayStation 5 HID",
    dual_dualsense_count: "1 to 12 Controllers",
    dual_dualsense_title: "PlayStation 5 Controller (DualSense)",
    dual_dualsense_desc: "PlayStation 5 DualSense emulation powered by the VIIPER driver, with full button mapping and next-gen PC compatibility.",
    dual_switch_badge: "Nintendo HID",
    dual_switch_count: "1 to 12 Controllers",
    dual_switch_title: "Nintendo Switch 2 Pro Controller",
    dual_switch_desc: "Support for the new Switch 2 Pro (ns2pro) gamepad with authentic Nintendo layout, 12-bit precision calibration, and neutral center.",
    dual_mixed_badge: "Multi-Console Mixed Support",
    dual_mixed_title: "Mixed Gaming? Use Mixed Mode",
    dual_mixed_desc: "Configure from 2 to 12 controllers and j360More will split the virtual slots evenly across platforms so your friends can play together with zero conflicts.",
    dual_chip_2: "🎮 2 Combined Gamepads",
    dual_chip_4: "🎮 4 Combined Gamepads",
    dual_chip_8: "🎮 8 Combined Gamepads",
    dual_chip_12: "🎮 12 Combined Gamepads",
    drivers_tag: "Essential Drivers",
    drivers_title: "Required System Controllers",
    drivers_subtitle: "To deliver ultra-low-latency native emulation without bloatware, j360More relies on industry-standard USB/IP and kernel drivers.",
    driver_viiper_tag: "Default / Multiplatform",
    driver_viiper_desc: "High-performance USB over IP (USB/IP) emulation server to spawn next-generation virtual gamepads on Windows and Linux (coming soon). The standalone binary is bundled inside j360More.",
    driver_viiper_why_title: "Why is it used in j360More?",
    driver_viiper_why_desc: "It is the new default, cross-platform emulation engine. Spawns Xbox 360, DualShock 4, DualSense (PS5), and Nintendo Switch 2 Pro controllers. On Windows, it pairs with the companion usbip-win2 driver.",
    driver_viiper_b1: "Emulates 4 gamepad families: Xbox 360, PS4, PS5, and Switch 2 Pro.",
    driver_viiper_b2: "Standard USB/IP architecture: ready for Windows and Linux (coming soon).",
    driver_viiper_b3: "Self-contained binary bundled in 'bin/viiper.exe' with zero hassle.",
    driver_viiper_btn: "Download usbip-win2 Driver (GitHub)",
    driver_vigem_tag: "Alternative (Windows)",
    driver_vigem_desc: "The Virtual Gamepad Emulation Bus is a classic kernel-mode driver for Windows that spawns virtual Xbox 360 and DualShock 4 controllers.",
    driver_vigem_why_title: "Why is it used in j360More?",
    driver_vigem_why_desc: "The traditional alternative engine for Windows users with ViGEmBus pre-installed. Spawns virtual Xbox 360 and DualShock 4 controllers with proven stability on Windows 10 and 11.",
    driver_vigem_b1: "Native emulation of 1 to 12 XInput slots in Windows.",
    driver_vigem_b2: "Full support for analog triggers and vibration rumble.",
    driver_vigem_b3: "100% backward-compatible with existing j360More configurations.",
    driver_vigem_btn: "Download ViGEmBus (GitHub Releases)",
    driver_hidhide_tag: "Recommended (Optional)",
    driver_hidhide_desc: "A HID device filter driver that selectively hides physical game controllers from all applications on the system, except for authorized processes (such as j360More).",
    driver_hidhide_why_title: "Why is it used in j360More?",
    driver_hidhide_why_desc: "It permanently solves the frustrating 'double controller' (double-input) bug. When connecting generic or PS4/PS5 controllers, games often detect both the physical gamepad and the virtual Xbox controller, registering inputs twice. HidHide masks the physical device so only the virtual Xbox controller is visible to games.",
    driver_hidhide_b1: "Prevents double button presses and menu jumping.",
    driver_hidhide_b2: "Per-device hide toggle directly inside j360More UI.",
    driver_hidhide_b3: "Completely optional: j360More works fine without it if your games don't suffer from double inputs.",
    driver_hidhide_btn: "Download HidHide (GitHub Releases)",
    req_table_title: "System Requirements",
    req_col_component: "Component",
    req_col_minimum: "Minimum Requirement",
    req_col_recommended: "Recommended",
    req_row_os: "Operating System",
    req_row_os_val1: "Windows 10 / 11 (64-bit)",
    req_row_os_val: "Windows 11 / Linux (Coming Soon)",
    req_row_drivers: "Emulation Driver",
    req_row_drivers_val1: "VIIPER (with usbip-win2) or ViGEmBus",
    req_row_drivers_val2: "VIIPER (Multiplatform: X360, DS4, PS5, Switch 2)",
    req_row_hidhide: "HidHide Driver",
    req_row_hidhide_val1: "Optional (Not required to launch)",
    req_row_hidhide_val2: "HidHide v1.2+ (To prevent double input)",
    req_row_inputs: "Input Devices",
    req_row_inputs_val1: "Any USB / Bluetooth Gamepad or Multi-Keyboard Raw Input",
    req_row_inputs_val2: "Multiple independent keyboards, DirectInput or standard gamepads",
    req_row_runtime: "Application Format",
    req_row_runtime_val1: "Standalone portable executable (no dependencies)",
    req_row_runtime_val2: "Portable standalone with bin/viiper.exe",
    quick_tag: "Step by Step",
    quick_title: "Start Playing in Under 2 Minutes",
    quick_subtitle: "Follow these simple steps to get your controllers ready.",
    q1_title: "Install usbip-win2 or ViGEmBus",
    q1_desc: "Install the usbip-win2 driver for the VIIPER engine (or ViGEmBus for the legacy engine). Run the installer once on your PC.",
    q2_title: "Launch j360More",
    q2_desc: "Open j360More.exe. The application automatically detects your installed drivers and connected gamepads.",
    q3_title: "Assign Controllers",
    q3_desc: "Under tabs 'Mando 1' through 'Mando 12', pick which physical device maps to each virtual Xbox 360 slot.",
    q4_title: "Start & Play!",
    q4_desc: "Click 'Iniciar Emulación'. Windows will immediately spawn the virtual gamepads and your games are ready to roll.",
    code_title: "Want to compile the source yourself?",
    code_subtitle: "You can clone the repository and run our official 1-click build script:",
    copy_btn: "Copy",
    faq_tag: "Frequently Asked Questions",
    faq_title: "FAQ",
    faq_q1: "Why is it mandatory to install usbip-win2 or ViGEmBus?",
    faq_a1: "Windows does not permit creating virtual input devices without a signed system driver. If you use the default VIIPER engine, you need the companion usbip-win2 driver to communicate gamepads over USB/IP (supporting Xbox 360, PS4, PS5, and Switch 2 Pro). If you choose the classic alternative engine, you need ViGEmBus. Without at least one of these drivers installed, the system cannot spawn virtual controllers recognized by your games.",
    faq_q2: "What happens if I don't install HidHide?",
    faq_a2: "j360More will work completely fine. HidHide is only needed if your game registers double actions when pressing buttons (because it reads both your physical controller and the emulated one). If your game only reads XInput, you won't experience double input.",
    faq_q3: "Can I use multiple keyboards simultaneously to play with friends as separate controllers?",
    faq_a3: "Yes! Thanks to low-level Windows Raw Input API integration, j360More individually tracks each connected physical keyboard (USB, Bluetooth, or internal laptop keyboard). You can connect 2, 3, or more keyboards and assign each to separate virtual slots (Controller 1, Controller 2, etc.) with zero cross-talk: pressing keys on Keyboard 1 will never affect Keyboard 2.",
    faq_q4: "How do I fix joystick drift?",
    faq_a4: "j360More features analog calibration. Open the calibration window and increase the 'Deadzone' percentage so unintended micro-movements are completely ignored.",
    cta_title: "Elevate Your PC Local Multiplayer Gaming!",
    cta_desc: "Download the latest release of j360More and enjoy seamless local gaming with friends.",
    cta_btn: "Download Latest Release on GitHub",
    nav_screenshots: "Screenshots",
    screenshots_tag: "Application Showcase",
    screenshots_title: "Real j360More Interface in Action",
    screenshots_subtitle: "Explore the modern, sleek, and intuitive interface engineered for pinpoint calibration and effortless configuration.",
    s1_badge: "Xbox 360",
    s1_title: "Xbox 360 Mapping",
    s1_desc: "Configuration and emulation of Xbox 360 controllers for up to 12 independent players.",
    s1b_badge: "DualShock 4",
    s1b_title: "DualShock 4 Mapping",
    s1b_desc: "Configuration and emulation of DualShock 4 controllers, available in standalone or Mixed mode.",
    s2_badge: "Calibration",
    s2_title: "Analog Sticks Calibration",
    s2_desc: "Dead zone adjustments to eliminate drift, custom sensitivity curves, and axis inversion.",
    s3_badge: "Settings",
    s3_title: "Emulation Options & Drivers",
    s3_desc: "Selection of driver engine (VIIPER / ViGEmBus), controller type (Xbox 360, DualShock 4, DualSense, Switch 2 Pro, or Mixed), controller count, and language.",
    screenshot_zoom: "Click to view full resolution",
    footer_desc: "Virtual controller emulator for Windows & Linux (coming soon). Designed and developed by JuanJSAR to provide unmatched speed, stability, and versatility for 1 to 12 local players.",
    footer_drivers_title: "Drivers",
    footer_links_title: "Links & Project",
    footer_releases: "Downloads / Releases"
  }
};

let currentLang = localStorage.getItem('j360_lang') || 'es';

function setLanguage(lang) {
  if (!translations[lang]) lang = 'es';
  currentLang = lang;
  localStorage.setItem('j360_lang', lang);
  document.documentElement.lang = lang;

  // Update button active state
  const btnEs = document.getElementById('lang-btn-es');
  const btnEn = document.getElementById('lang-btn-en');
  if (btnEs && btnEn) {
    btnEs.classList.toggle('active', lang === 'es');
    btnEn.classList.toggle('active', lang === 'en');
  }

  // Update text of elements with data-i18n
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (translations[lang][key]) {
      el.textContent = translations[lang][key];
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Language
  setLanguage(currentLang);

  const btnEs = document.getElementById('lang-btn-es');
  const btnEn = document.getElementById('lang-btn-en');

  if (btnEs) btnEs.addEventListener('click', () => setLanguage('es'));
  if (btnEn) btnEn.addEventListener('click', () => setLanguage('en'));

  // Mobile Menu Toggle
  const menuToggle = document.querySelector('.menu-toggle');
  const navLinks = document.querySelector('.nav-links');

  if (menuToggle && navLinks) {
    const closeMenu = () => {
      navLinks.classList.remove('show');
      menuToggle.textContent = '☰';
      menuToggle.setAttribute('aria-expanded', 'false');
    };

    menuToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const isShowing = navLinks.classList.toggle('show');
      menuToggle.textContent = isShowing ? '✕' : '☰';
      menuToggle.setAttribute('aria-expanded', isShowing ? 'true' : 'false');
    });

    navLinks.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        closeMenu();
      });
    });

    document.addEventListener('click', (e) => {
      if (navLinks.classList.contains('show') && !navLinks.contains(e.target) && e.target !== menuToggle) {
        closeMenu();
      }
    });
  }

  // FAQ Accordion Toggle
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const question = item.querySelector('.faq-question');
    if (question) {
      question.addEventListener('click', () => {
        const isActive = item.classList.contains('active');
        faqItems.forEach(i => i.classList.remove('active'));
        if (!isActive) {
          item.classList.add('active');
        }
      });
    }
  });

  // Copy Code Buttons
  const copyButtons = document.querySelectorAll('.copy-btn');
  copyButtons.forEach(button => {
    button.addEventListener('click', () => {
      const codeText = button.getAttribute('data-code') || button.previousElementSibling.textContent;
      navigator.clipboard.writeText(codeText).then(() => {
        const originalText = button.textContent;
        button.textContent = currentLang === 'en' ? 'Copied!' : '¡Copiado!';
        button.style.color = '#10cf65';
        setTimeout(() => {
          button.textContent = originalText;
          button.style.color = '';
        }, 2000);
      });
    });
  });

  // Header Shadow on Scroll
  const header = document.querySelector('.header');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 30) {
      header.style.boxShadow = '0 10px 30px rgba(0,0,0,0.5)';
      header.style.background = 'rgba(13, 17, 23, 0.95)';
    } else {
      header.style.boxShadow = 'none';
      header.style.background = 'rgba(13, 17, 23, 0.85)';
    }
  });

  // Screenshot Lightbox Modal
  const modal = document.getElementById('lightbox-modal');
  const modalImg = document.getElementById('lightbox-img');
  const modalCaption = document.getElementById('lightbox-caption');
  const modalClose = document.getElementById('lightbox-close');

  if (modal && modalImg) {
    document.querySelectorAll('.screenshot-zoomable').forEach(img => {
      img.addEventListener('click', () => {
        modalImg.src = img.src;
        if (modalCaption) {
          modalCaption.textContent = img.alt || '';
        }
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
      });
    });

    const closeModal = () => {
      modal.classList.remove('active');
      document.body.style.overflow = '';
    };

    if (modalClose) modalClose.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal || e.target === modalClose) {
        closeModal();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modal.classList.contains('active')) {
        closeModal();
      }
    });
  }
});
