// j360More Official Website Script with Bilingual Support (ES / EN)
// Developed by JuanJSAR

const translations = {
  es: {
    nav_features: "Cualidades",
    nav_drivers: "Controladores",
    nav_requirements: "Requisitos",
    nav_quickstart: "Guía Rápida",
    nav_faq: "Preguntas",
    nav_download: "Descargar",
    hero_badge_players: "🎮 Hasta 12 Mandos Simultáneos",
    hero_badge_hz: "⚡ Ultra Baja Latencia 120Hz",
    hero_badge_rawkb: "⌨️ Multi-Teclado Raw Input",
    hero_badge_author: "👨‍💻 Creado por JuanJSAR",
    hero_subtitle: "Convierte cualquier control genérico USB, mando de PlayStation, palanca arcade o múltiples teclados independientes en mandos oficiales de Xbox 360 (XInput) con precisión milimétrica y compatibilidad total en PC. Desarrollado por JuanJSAR.",
    hero_btn_releases: "Descargar j360More",
    hero_btn_drivers: "Ver Drivers Necesarios",
    hero_controller_tag: "Mapeo Interactivo en Tiempo Real",
    stat_controllers: "Mandos Virtuales Simultáneos",
    stat_refreshrate: "Tasa de Refresco y Despacho",
    stat_latency: "Latencia de Procesamiento",
    stat_compatibility: "Compatible con Juegos XInput",
    feat_tag: "Características Principales",
    feat_title: "Diseñado para la Mejor Experiencia Multijugador",
    feat_subtitle: "Desarrollado por JuanJSAR para jugadores de PC, emuladores y salones arcade que necesitan conectar múltiples mandos sin conflictos de detección.",
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
    drivers_tag: "Drivers Indispensables",
    drivers_title: "Controladores del Sistema Necesarios",
    drivers_subtitle: "Para lograr una emulación 100% nativa a nivel de kernel en Windows sin requerir programas pesados, j360More se apoya en los controladores de referencia de la comunidad.",
    driver_vigem_tag: "Obligatorio",
    driver_vigem_desc: "El Virtual Gamepad Emulation Bus es un driver de nivel de sistema (kernel-mode) que permite a Windows generar y conectar mandos virtuales de Xbox 360 y DualShock 4 idénticos a los mandos físicos oficiales.",
    driver_vigem_why_title: "¿Para qué se utiliza en j360More?",
    driver_vigem_why_desc: "Es el motor central de emulación. Sin ViGEmBus, la aplicación no puede crear los mandos virtuales en Windows. Se encarga de que cualquier juego de Steam, Xbox Game Pass o emulador reconozca los controles como mandos oficiales de Xbox 360 (XInput).",
    driver_vigem_b1: "Emulación nativa de 1 a 12 slots XInput en Windows.",
    driver_vigem_b2: "Compatibilidad total con gatillos analógicos y vibración.",
    driver_vigem_b3: "Firmado digitalmente para máxima estabilidad en Windows 10 y 11.",
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
    req_row_os_val: "Windows 11 (64-bit) actualizado",
    req_row_vigem: "Driver ViGEmBus",
    req_row_vigem_val: "Última versión oficial estable",
    req_row_hidhide: "Driver HidHide",
    req_row_hidhide_val1: "Opcional (No requerido para arrancar)",
    req_row_hidhide_val2: "HidHide v1.2+ (Para evitar doble control)",
    req_row_inputs: "Periféricos de Entrada",
    req_row_inputs_val1: "Cualquier Gamepad USB / Bluetooth o Multi-Teclado Raw Input",
    req_row_inputs_val2: "Múltiples teclados independientes, DirectInput o mandos estándar",
    req_row_runtime: "Formato del Programa",
    req_row_runtime_val1: "Ejecutable standalone sin dependencias",
    req_row_runtime_val2: "Modo portátil directo (41 MB)",
    quick_tag: "Paso a Paso",
    quick_title: "Comienza a Jugar en Menos de 2 Minutos",
    quick_subtitle: "Sigue estos sencillos pasos para tener tus mandos listos.",
    q1_title: "Instala ViGEmBus",
    q1_desc: "Descarga e instala el instalador oficial de ViGEmBus. Solo necesitas hacerlo una sola vez en tu equipo.",
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
    faq_q1: "¿Por qué es obligatorio instalar ViGEmBus?",
    faq_a1: "Windows no permite crear dispositivos de control virtual sin un driver de kernel firmado. ViGEmBus es el estándar de oro de código abierto que actúa como puente para crear mandos virtuales Xbox 360 totalmente indistinguibles de un mando oficial con cable.",
    faq_q2: "¿Qué pasa si no tengo instalado HidHide?",
    faq_a2: "j360More funcionará perfectamente. HidHide solo es necesario si notas que tu juego recibe órdenes dobles al presionar un botón (porque detecta al mismo tiempo tu mando genérico y el mando emulado). Si tu juego solo lee XInput, ni siquiera notarás la diferencia.",
    faq_q3: "¿Puedo usar múltiples teclados para jugar con amigos como mandos independientes?",
    faq_a3: "¡Sí! Gracias a la integración nativa con Windows Raw Input, j360More detecta individualmente cada teclado físico conectado (USB, Bluetooth o integrado de laptop). Puedes conectar 2, 3 o más teclados y asignarlos a mandos separados (Mando 1, Mando 2, etc.) sin interferencia cruzada (Zero Cross-Talk): presionar teclas en el Teclado 1 jamás afectará los controles del Teclado 2.",
    faq_q4: "¿Cómo soluciono sticks con deriva (drift)?",
    faq_a4: "j360More incluye calibración analógica avanzada. En la pestaña de calibración puedes aumentar la 'Zona Muerta (Deadzone)' en un porcentaje para que los movimientos no deseados del stick sean completamente ignorados.",
    cta_title: "¡Lleva el Multijugador en PC al Siguiente Nivel!",
    cta_desc: "Descarga la última versión de j360More desarrollada por JuanJSAR y disfruta de partidas locales con amigos sin complicaciones.",
    cta_btn: "Descargar Última Versión en GitHub",
    nav_screenshots: "Capturas",
    screenshots_tag: "Galería de la Aplicación",
    screenshots_title: "Interfaz Real de j360More en Acción",
    screenshots_subtitle: "Explora la interfaz moderna, limpia y potente diseñada para un control milimétrico y configuración sin esfuerzo.",
    s1_badge: "Mapeo Principal",
    s1_title: "Mapeo Visual Interactivo y Soporte Multi-Mando",
    s1_desc: "Diagrama interactivo del mando Xbox 360 con LEDs reactivos en tiempo real, pestañas dedicadas para hasta 12 jugadores y protección inteligente contra mandos fantasma.",
    s2_badge: "Calibración Fina",
    s2_title: "Plano Cartesiano y Curvas de Respuesta de Sticks",
    s2_desc: "Visualizador 2D en tiempo real con control exacto de Zona Muerta (Dead Zone), Anti-Dead Zone para anular la deriva (drift), sensibilidad cuadrática e inversión de ejes.",
    s3_badge: "Ajustes del Sistema",
    s3_title: "Configuración General e Integración con HidHide",
    s3_desc: "Selector bilingüe instantáneo (Español / Inglés), ajuste del número de mandos a emular (1 a 12) y activación del Cloaking global para erradicar el doble mando en juegos.",
    screenshot_zoom: "Haz clic para ampliar en alta resolución",
    footer_desc: "Emulador de mandos virtuales Xbox 360 para Windows. Diseñado y desarrollado por JuanJSAR para ofrecer la máxima velocidad, estabilidad y flexibilidad en entornos multijugador de 1 a 12 participantes.",
    footer_drivers_title: "Controladores",
    footer_links_title: "Enlaces y Proyecto",
    footer_releases: "Descargas / Releases"
  },
  en: {
    nav_features: "Features",
    nav_drivers: "Drivers",
    nav_requirements: "Requirements",
    nav_quickstart: "Quickstart",
    nav_faq: "FAQ",
    nav_download: "Download",
    hero_badge_players: "🎮 Up to 12 Controllers",
    hero_badge_hz: "⚡ Ultra Low Latency 120Hz",
    hero_badge_rawkb: "⌨️ Multi-Keyboard Raw Input",
    hero_badge_author: "👨‍💻 Created by JuanJSAR",
    hero_subtitle: "Turn any generic USB controller, PlayStation gamepad, arcade stick, or multiple independent keyboards into official Xbox 360 controllers (XInput) with pinpoint accuracy and full PC compatibility. Developed by JuanJSAR.",
    hero_btn_releases: "Download j360More",
    hero_btn_drivers: "View Required Drivers",
    hero_controller_tag: "Real-Time Interactive Mapping",
    stat_controllers: "Simultaneous Virtual Controllers",
    stat_refreshrate: "Refresh & Dispatch Rate",
    stat_latency: "Processing Latency",
    stat_compatibility: "Compatible with XInput Games",
    feat_tag: "Core Features",
    feat_title: "Engineered for the Ultimate Multiplayer Experience",
    feat_subtitle: "Developed by JuanJSAR for PC gamers, emulators, and arcade setups requiring multiple gamepads without device conflicts.",
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
    drivers_tag: "Essential Drivers",
    drivers_title: "Required System Controllers",
    drivers_subtitle: "To deliver 100% native kernel-level emulation in Windows without bloatware, j360More leverages the gold-standard drivers of the emulation community.",
    driver_vigem_tag: "Mandatory",
    driver_vigem_desc: "The Virtual Gamepad Emulation Bus is a kernel-mode driver that empowers Windows to generate and connect virtual Xbox 360 and DualShock 4 controllers identical to physical hardware.",
    driver_vigem_why_title: "Why is it required in j360More?",
    driver_vigem_why_desc: "It is the core emulation engine. Without ViGEmBus, the application cannot spawn virtual gamepads in Windows. It ensures that any game on Steam, Xbox Game Pass, or emulators natively recognizes your gamepads as official Xbox 360 controllers (XInput).",
    driver_vigem_b1: "Native emulation of 1 to 12 XInput slots in Windows.",
    driver_vigem_b2: "Full support for analog triggers and vibration rumble.",
    driver_vigem_b3: "Digitally signed for rock-solid stability on Windows 10 and 11.",
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
    req_row_os_val: "Windows 11 (64-bit) up to date",
    req_row_vigem: "ViGEmBus Driver",
    req_row_vigem_val: "Latest official stable release",
    req_row_hidhide: "HidHide Driver",
    req_row_hidhide_val1: "Optional (Not required to launch)",
    req_row_hidhide_val2: "HidHide v1.2+ (To prevent double input)",
    req_row_inputs: "Input Devices",
    req_row_inputs_val1: "Any USB / Bluetooth Gamepad or Multi-Keyboard Raw Input",
    req_row_inputs_val2: "Multiple independent keyboards, DirectInput or standard gamepads",
    req_row_runtime: "Application Format",
    req_row_runtime_val1: "Standalone portable executable (no extras)",
    req_row_runtime_val2: "Single portable EXE (41 MB)",
    quick_tag: "Step by Step",
    quick_title: "Start Playing in Under 2 Minutes",
    quick_subtitle: "Follow these simple steps to get your controllers ready.",
    q1_title: "Install ViGEmBus",
    q1_desc: "Download and install the official ViGEmBus package. You only need to run this installer once on your PC.",
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
    faq_q1: "Why is ViGEmBus mandatory?",
    faq_a1: "Windows does not permit creating virtual input devices without a signed kernel driver. ViGEmBus is the open-source industry standard that acts as a bridge to spawn virtual Xbox 360 controllers identical to official hardware.",
    faq_q2: "What happens if I don't install HidHide?",
    faq_a2: "j360More will work completely fine. HidHide is only needed if your game registers double actions when pressing buttons (because it reads both your physical controller and the emulated one). If your game only reads XInput, you won't experience double input.",
    faq_q3: "Can I use multiple keyboards simultaneously to play with friends as separate controllers?",
    faq_a3: "Yes! Thanks to low-level Windows Raw Input API integration, j360More individually tracks each connected physical keyboard (USB, Bluetooth, or internal laptop keyboard). You can connect 2, 3, or more keyboards and assign each to separate virtual slots (Controller 1, Controller 2, etc.) with zero cross-talk: pressing keys on Keyboard 1 will never affect Keyboard 2.",
    faq_q4: "How do I fix joystick drift?",
    faq_a4: "j360More features analog calibration. Open the calibration window and increase the 'Deadzone' percentage so unintended micro-movements are completely ignored.",
    cta_title: "Elevate Your PC Local Multiplayer Gaming!",
    cta_desc: "Download the latest release of j360More created by JuanJSAR and enjoy seamless local gaming with friends.",
    cta_btn: "Download Latest Release on GitHub",
    nav_screenshots: "Screenshots",
    screenshots_tag: "Application Showcase",
    screenshots_title: "Real j360More Interface in Action",
    screenshots_subtitle: "Explore the modern, sleek, and intuitive interface engineered for pinpoint calibration and effortless configuration.",
    s1_badge: "Main Mapping",
    s1_title: "Interactive Visual Mapping & Multi-Controller Support",
    s1_desc: "Interactive Xbox 360 controller diagram with real-time reactive glow LEDs, dedicated tabs for up to 12 players, and smart protection against phantom devices.",
    s2_badge: "Fine Calibration",
    s2_title: "2D Cartesian Plane & Analog Sticks Response Curves",
    s2_desc: "Real-time 2D Cartesian visualizer with precise Dead Zone control, Anti-Dead Zone to eliminate joystick drift, quadratic sensitivity curves, and axis inversion.",
    s3_badge: "System Settings",
    s3_title: "General Settings & Nefarius HidHide Integration",
    s3_desc: "Instant bilingual switcher (English / Spanish), virtual controller count slider (1 to 12), and global Cloaking activation to eliminate double-input conflicts in games.",
    screenshot_zoom: "Click to view full resolution",
    footer_desc: "Virtual Xbox 360 controller emulator for Windows. Designed and developed by JuanJSAR to provide unmatched speed, stability, and versatility for 1 to 12 local players.",
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
