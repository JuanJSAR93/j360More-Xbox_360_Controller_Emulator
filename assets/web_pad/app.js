/**
 * app.js - Cliente Web Gamepad j360More AirPad
 * Soporta:
 * - Protocolo Binario v1 de ultra-baja latencia (22 bytes Little-Endian).
 * - D-Pad continuo deslizable con soporte de diagonales cruzadas (8 sectores).
 * - Reposicionamiento y escalado individual de todos los controles (LT, LB, LS, RT, RB, RS, Sticks, D-Pad, ABXY).
 * - Exportación e Importación de disposiciones en JSON (portapapeles y archivo descargable).
 * - Screen Wake Lock, Multi-touch, Hápticos y Puente Gamepad API.
 */

(function () {
  'use strict';

  // --- 1. Elementos UI ---
  const connDot = document.getElementById('conn-dot');
  const connText = document.getElementById('conn-text');
  const playerBadge = document.getElementById('player-badge');
  const pingText = document.getElementById('ping-text');
  const btnLayout = document.getElementById('btn-layout');
  const btnTheme = document.getElementById('btn-theme');
  const btnFullscreen = document.getElementById('btn-fullscreen');

  // Toolbar de edición
  const layoutToolbar = document.getElementById('layout-toolbar');
  const layoutToolbarTitle = document.getElementById('layout-toolbar-title');
  const btnScaleDown = document.getElementById('btn-scale-down');
  const lblScaleVal = document.getElementById('lbl-scale-val');
  const btnScaleUp = document.getElementById('btn-scale-up');
  const btnLayoutExport = document.getElementById('btn-layout-export');
  const btnLayoutImport = document.getElementById('btn-layout-import');
  const btnLayoutSave = document.getElementById('btn-layout-save');
  const btnLayoutReset = document.getElementById('btn-layout-reset');
  const btnLayoutCancel = document.getElementById('btn-layout-cancel');

  // Modal de Exportar / Importar
  const layoutModal = document.getElementById('layout-modal');
  const modalTitle = document.getElementById('modal-title');
  const modalDesc = document.getElementById('modal-desc');
  const modalTextarea = document.getElementById('modal-textarea');
  const modalFileInput = document.getElementById('modal-file-input');
  const modalBtnCopy = document.getElementById('modal-btn-copy');
  const modalBtnDownload = document.getElementById('modal-btn-download');
  const modalBtnUpload = document.getElementById('modal-btn-upload');
  const modalBtnApply = document.getElementById('modal-btn-apply');
  const btnModalClose = document.getElementById('btn-modal-close');

  // --- 2. Screen Wake Lock (Evita que la pantalla se apague) ---
  let wakeLock = null;

  async function requestWakeLock() {
    try {
      if ('wakeLock' in navigator) {
        wakeLock = await navigator.wakeLock.request('screen');
        console.log('[*] Screen Wake Lock activado');
        wakeLock.addEventListener('release', () => {
          wakeLock = null;
        });
      }
    } catch (err) {
      console.log('[!] Wake Lock no soportado o bloqueado:', err);
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      requestWakeLock();
    }
  });

  window.addEventListener('pointerdown', () => {
    if (!wakeLock) requestWakeLock();
  }, { once: true });

  // --- 3. Protocolo Binario v1 y Estado Local ---
  const BUTTON_BITS = {
    'A': 1 << 0,
    'B': 1 << 1,
    'X': 1 << 2,
    'Y': 1 << 3,
    'LB': 1 << 4,
    'RB': 1 << 5,
    'BACK': 1 << 6,
    'START': 1 << 7,
    'GUIDE': 1 << 8,
    'LS': 1 << 9,
    'RS': 1 << 10,
    'UP': 1 << 11,
    'DOWN': 1 << 12,
    'LEFT': 1 << 13,
    'RIGHT': 1 << 14
  };

  let useBinaryProtocol = false;
  let packetSeq = 0;

  // Buffer binario reutilizable de 22 bytes (<BBIHBBhhhhI)
  const binBuffer = new ArrayBuffer(22);
  const binView = new DataView(binBuffer);
  binView.setUint8(0, 1); // Version = 1
  binView.setUint8(1, 1); // Type = 1 (INPUT)

  // Estado unificado del mando
  let buttonsMask = 0;
  let triggerLT = 0;   // 0..255
  let triggerRT = 0;   // 0..255
  let stickLX = 0;     // -32768..32767
  let stickLY = 0;     // -32768..32767
  let stickRX = 0;     // -32768..32767
  let stickRY = 0;     // -32768..32767
  let analogDirty = false;

  // --- 4. Conexión WebSocket ---
  let ws = null;
  let isConnected = false;
  let currentSlot = null;
  let hapticsEnabled = true;

  function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws`;

    connText.textContent = 'Conectando...';
    connDot.className = 'dot disconnected';

    try {
      ws = new WebSocket(wsUrl);
      ws.binaryType = 'arraybuffer';
    } catch (e) {
      setTimeout(connectWebSocket, 2000);
      return;
    }

    ws.onopen = () => {
      isConnected = true;
      connDot.className = 'dot connected';
      connText.textContent = 'Conectado';
      requestWakeLock();

      sendMsg({
        type: 'info',
        name: navigator.userAgent.includes('iPhone') ? 'iPhone' :
              navigator.userAgent.includes('Android') ? 'Android' : 'Móvil Web'
      });
    };

    ws.onmessage = (event) => {
      try {
        if (typeof event.data === 'string') {
          const msg = JSON.parse(event.data);
          if (msg.type === 'welcome') {
            currentSlot = msg.slot;
            playerBadge.textContent = `P${msg.slot}`;
            if (msg.haptics !== undefined) hapticsEnabled = msg.haptics;
            if (msg.binary) useBinaryProtocol = true;
          } else if (msg.type === 'rumble') {
            handleRumble(msg.low, msg.high);
          } else if (msg.type === 'pong') {
            const rtt = Math.round(performance.now() - msg.t);
            pingText.textContent = `${rtt} ms`;
          }
        }
      } catch (e) {}
    };

    ws.onclose = () => {
      isConnected = false;
      connDot.className = 'dot disconnected';
      connText.textContent = 'Desconectado';
      playerBadge.textContent = '--';
      setTimeout(connectWebSocket, 1500);
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  function sendMsg(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(obj));
    }
  }

  // Envío binario v1 empaquetado (<BBIHBBhhhhI)
  function sendBinaryPacket() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    if (!useBinaryProtocol) {
      // Fallback JSON si el servidor no negoció binario
      sendMsg({
        type: 'state',
        buttons: buttonsMask,
        lt: triggerLT / 255.0,
        rt: triggerRT / 255.0,
        lx: stickLX / 32767.0,
        ly: stickLY / 32767.0,
        rx: stickRX / 32767.0,
        ry: stickRY / 32767.0,
        t: Math.round(performance.now())
      });
      return;
    }

    packetSeq = (packetSeq + 1) >>> 0;
    const nowMs = Math.round(performance.now()) >>> 0;

    binView.setUint32(2, packetSeq, true);
    binView.setUint16(6, buttonsMask, true);
    binView.setUint8(8, triggerLT);
    binView.setUint8(9, triggerRT);
    binView.setInt16(10, stickLX, true);
    binView.setInt16(12, stickLY, true);
    binView.setInt16(14, stickRX, true);
    binView.setInt16(16, stickRY, true);
    binView.setUint32(18, nowMs, true);

    ws.send(binBuffer);
  }

  // Política Híbrida:
  // - Los cambios en botones digitales o transiciones de gatillo se envían INMEDIATAMENTE
  function onButtonStateChange(btnName, isPressed) {
    const bit = BUTTON_BITS[btnName];
    if (bit === undefined) return;

    const prevMask = buttonsMask;
    if (isPressed) {
      buttonsMask |= bit;
    } else {
      buttonsMask &= ~bit;
    }

    if (buttonsMask !== prevMask) {
      sendBinaryPacket();
    }
  }

  // - Los cambios analógicos continuos se envían en bucle animado con control de backpressure
  function flushAnalogLoop() {
    if (analogDirty && ws && ws.readyState === WebSocket.OPEN) {
      if (ws.bufferedAmount < 4096) {
        sendBinaryPacket();
        analogDirty = false;
      }
    }
    requestAnimationFrame(flushAnalogLoop);
  }
  requestAnimationFrame(flushAnalogLoop);

  // Ping periódico cada 2 segundos
  setInterval(() => {
    if (isConnected) {
      sendMsg({ type: 'ping', t: performance.now() });
    }
  }, 2000);

  // --- 5. Hápticos y Vibración ---
  function vibrateShort() {
    if (hapticsEnabled && 'vibrate' in navigator) {
      try { navigator.vibrate(20); } catch (e) {}
    }
  }

  function handleRumble(low, high) {
    if (!hapticsEnabled || !('vibrate' in navigator)) return;
    const intensity = Math.max(low, high) / 65535.0;
    if (intensity > 0.1) {
      const ms = Math.min(150, Math.round(intensity * 120));
      try { navigator.vibrate(ms); } catch (e) {}
    }
  }

  // --- 6. Manejo de Botones Digitales y Gatillos Individuales ---
  let isEditingLayout = false;

  function setupButton(el, btnName) {
    if (!el) return;

    el.addEventListener('pointerdown', (e) => {
      if (isEditingLayout) return; // En modo edición no emite botones
      e.preventDefault();
      e.stopPropagation();
      el.setPointerCapture(e.pointerId);
      el.classList.add('active');
      vibrateShort();

      if (btnName === 'LT' || btnName === 'RT') {
        if (btnName === 'LT') {
          triggerLT = 255;
          const meter = document.getElementById('lt-meter');
          if (meter) meter.style.width = '100%';
        } else {
          triggerRT = 255;
          const meter = document.getElementById('rt-meter');
          if (meter) meter.style.width = '100%';
        }
        sendBinaryPacket();
      } else {
        onButtonStateChange(btnName, true);
      }
    });

    const onRelease = (e) => {
      if (isEditingLayout) return;
      e.preventDefault();
      e.stopPropagation();
      if (el.hasPointerCapture(e.pointerId)) {
        try { el.releasePointerCapture(e.pointerId); } catch (err) {}
      }
      el.classList.remove('active');

      if (btnName === 'LT' || btnName === 'RT') {
        if (btnName === 'LT') {
          triggerLT = 0;
          const meter = document.getElementById('lt-meter');
          if (meter) meter.style.width = '0%';
        } else {
          triggerRT = 0;
          const meter = document.getElementById('rt-meter');
          if (meter) meter.style.width = '0%';
        }
        sendBinaryPacket();
      } else {
        onButtonStateChange(btnName, false);
      }
    };

    el.addEventListener('pointerup', onRelease);
    el.addEventListener('pointercancel', onRelease);
    el.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  // Registrar botones con data-btn (excepto los de la cruceta que usan el D-Pad continuo)
  document.querySelectorAll('[data-btn]').forEach((el) => {
    if (el.classList.contains('dpad-btn')) return;
    setupButton(el, el.getAttribute('data-btn'));
  });

  // --- 7. D-Pad Continuo Deslizable (8 Sectores, Diagonales Cruzadas sin Bloqueo) ---
  function setupContinuousDpad() {
    const dpad = document.getElementById('dpad');
    if (!dpad) return;

    const btnUp = dpad.querySelector('.dpad-up');
    const btnDown = dpad.querySelector('.dpad-down');
    const btnLeft = dpad.querySelector('.dpad-left');
    const btnRight = dpad.querySelector('.dpad-right');

    let activePointerId = null;
    let cachedRect = null;
    let activeDirs = { UP: false, DOWN: false, LEFT: false, RIGHT: false };

    function updateRect() {
      cachedRect = dpad.getBoundingClientRect();
    }

    window.addEventListener('resize', updateRect);
    window.addEventListener('orientationchange', updateRect);

    function handleDpadMove(clientX, clientY) {
      if (!cachedRect) updateRect();
      const cx = cachedRect.left + cachedRect.width / 2;
      const cy = cachedRect.top + cachedRect.height / 2;

      const dx = clientX - cx;
      const dy = clientY - cy;
      const dist = Math.hypot(dx, dy);

      // Zona muerta central (~16% del tamaño del D-Pad)
      const deadzone = cachedRect.width * 0.16;
      const newDirs = { UP: false, DOWN: false, LEFT: false, RIGHT: false };

      if (dist >= deadzone) {
        // Umbral angular de 45° por sector: proyección mínima sin(22.5°) ≈ 0.38 de la distancia
        const threshold = dist * 0.38;

        if (dy < -threshold) newDirs.UP = true;
        if (dy > threshold) newDirs.DOWN = true;
        if (dx < -threshold) newDirs.LEFT = true;
        if (dx > threshold) newDirs.RIGHT = true;
      }

      let changedAny = false;
      for (const dir of ['UP', 'DOWN', 'LEFT', 'RIGHT']) {
        if (activeDirs[dir] !== newDirs[dir]) {
          changedAny = true;
          activeDirs[dir] = newDirs[dir];
          onButtonStateChange(dir, newDirs[dir]);
          const el = dir === 'UP' ? btnUp : dir === 'DOWN' ? btnDown : dir === 'LEFT' ? btnLeft : btnRight;
          if (el) el.classList.toggle('active', newDirs[dir]);
        }
      }

      if (changedAny && (newDirs.UP || newDirs.DOWN || newDirs.LEFT || newDirs.RIGHT)) {
        vibrateShort();
      }
    }

    dpad.addEventListener('pointerdown', (e) => {
      if (isEditingLayout) return;
      e.preventDefault();
      e.stopPropagation();
      activePointerId = e.pointerId;
      dpad.setPointerCapture(e.pointerId);
      updateRect();
      handleDpadMove(e.clientX, e.clientY);
    });

    dpad.addEventListener('pointermove', (e) => {
      if (isEditingLayout) return;
      if (e.pointerId === activePointerId) {
        handleDpadMove(e.clientX, e.clientY);
      }
    });

    const onEnd = (e) => {
      if (isEditingLayout) return;
      if (e.pointerId === activePointerId) {
        activePointerId = null;
        if (dpad.hasPointerCapture(e.pointerId)) {
          try { dpad.releasePointerCapture(e.pointerId); } catch (err) {}
        }
        for (const dir of ['UP', 'DOWN', 'LEFT', 'RIGHT']) {
          if (activeDirs[dir]) {
            activeDirs[dir] = false;
            onButtonStateChange(dir, false);
            const el = dir === 'UP' ? btnUp : dir === 'DOWN' ? btnDown : dir === 'LEFT' ? btnLeft : btnRight;
            if (el) el.classList.remove('active');
          }
        }
      }
    };

    dpad.addEventListener('pointerup', onEnd);
    dpad.addEventListener('pointercancel', onEnd);
  }

  setupContinuousDpad();

  // --- 8. Joysticks Virtuales Analógicos (con Bounding Rect en Caché) ---
  function setupJoystick(baseId, knobId, stickName, clickBtnName) {
    const base = document.getElementById(baseId);
    const knob = document.getElementById(knobId);
    if (!base || !knob) return;

    let activePointerId = null;
    let lastTap = 0;
    const RADIUS = 45;

    let cachedCenterX = 0;
    let cachedCenterY = 0;

    function updateCachedCenter() {
      const rect = base.getBoundingClientRect();
      cachedCenterX = rect.left + rect.width / 2;
      cachedCenterY = rect.top + rect.height / 2;
    }

    window.addEventListener('resize', updateCachedCenter);
    window.addEventListener('orientationchange', updateCachedCenter);

    function handleMove(clientX, clientY) {
      let dx = clientX - cachedCenterX;
      let dy = clientY - cachedCenterY;
      const dist = Math.hypot(dx, dy);

      if (dist > RADIUS) {
        dx = (dx / dist) * RADIUS;
        dy = (dy / dist) * RADIUS;
      }

      knob.style.transform = `translate(${dx}px, ${dy}px)`;

      // Normalizar a int16 [-32767, 32767]
      const normX = dx / RADIUS;
      const normY = dy / RADIUS;
      const intX = Math.round(Math.max(-1.0, Math.min(1.0, normX)) * 32767);
      const intY = Math.round(Math.max(-1.0, Math.min(1.0, normY)) * 32767);

      if (stickName === 'L') {
        stickLX = intX;
        stickLY = intY;
      } else {
        stickRX = intX;
        stickRY = intY;
      }
      analogDirty = true;
    }

    base.addEventListener('pointerdown', (e) => {
      if (isEditingLayout) return;
      e.preventDefault();
      e.stopPropagation();

      const now = Date.now();
      if (now - lastTap < 300) {
        vibrateShort();
        knob.classList.add('clicked');
        onButtonStateChange(clickBtnName, true);
        setTimeout(() => {
          knob.classList.remove('clicked');
          onButtonStateChange(clickBtnName, false);
        }, 150);
        lastTap = 0;
      } else {
        lastTap = now;
      }

      updateCachedCenter();
      activePointerId = e.pointerId;
      base.setPointerCapture(e.pointerId);
      handleMove(e.clientX, e.clientY);
    });

    base.addEventListener('pointermove', (e) => {
      if (isEditingLayout) return;
      if (e.pointerId === activePointerId) {
        handleMove(e.clientX, e.clientY);
      }
    });

    const onStickEnd = (e) => {
      if (isEditingLayout) return;
      if (e.pointerId === activePointerId) {
        activePointerId = null;
        if (base.hasPointerCapture(e.pointerId)) {
          try { base.releasePointerCapture(e.pointerId); } catch (err) {}
        }
        knob.style.transform = 'translate(0px, 0px)';
        if (stickName === 'L') {
          stickLX = 0;
          stickLY = 0;
        } else {
          stickRX = 0;
          stickRY = 0;
        }
        sendBinaryPacket();
      }
    };

    base.addEventListener('pointerup', onStickEnd);
    base.addEventListener('pointercancel', onStickEnd);
  }

  setupJoystick('stick-left-base', 'stick-left-knob', 'L', 'LS');
  setupJoystick('stick-right-base', 'stick-right-knob', 'R', 'RS');

  // --- 9. Personalizador Local de Disposición (LocalStorage + Export/Import + Escalado) ---
  const STORAGE_KEY = 'airpad_custom_layout_v1';
  let layoutPositions = {};
  let tempSessionPositions = {};
  let selectedLayoutId = null;

  const FRIENDLY_NAMES = {
    'btn-lt': 'Gatillo LT',
    'btn-lb': 'Bumper LB',
    'btn-ls': 'Botón Stick LS (L3)',
    'btn-rt': 'Gatillo RT',
    'btn-rb': 'Bumper RB',
    'btn-rs': 'Botón Stick RS (R3)',
    'center-buttons': 'Botones Centrales (Select/Guide/Start)',
    'stick-left': 'Joystick Izquierdo (LS)',
    'dpad': 'Cruceta (D-Pad)',
    'btn-y': 'Botón Y (Amarillo)',
    'btn-x': 'Botón X (Azul)',
    'btn-b': 'Botón B (Rojo)',
    'btn-a': 'Botón A (Verde)',
    'action-buttons': 'Botones de Acción (ABXY)',
    'abxy': 'Botones de Acción (ABXY)',
    'stick-right': 'Joystick Derecho (RS)'
  };

  function loadSavedLayout() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        layoutPositions = JSON.parse(raw);
        // Migración hacia atrás: si existía el grupo unificado action-buttons, expandirlo a cada botón
        if (layoutPositions['action-buttons'] && !layoutPositions['btn-a']) {
          const legacy = layoutPositions['action-buttons'];
          ['btn-a', 'btn-b', 'btn-x', 'btn-y'].forEach((k) => {
            layoutPositions[k] = JSON.parse(JSON.stringify(legacy));
          });
          delete layoutPositions['action-buttons'];
        }
        applyPositions(layoutPositions);
      }
    } catch (e) {
      console.warn('[!] Error leyendo layout de localStorage:', e);
    }
  }

  function applyPositions(posMap) {
    document.querySelectorAll('.layout-item[data-layout-id]').forEach((el) => {
      const id = el.getAttribute('data-layout-id');
      let item = posMap[id];
      if (!item && (id === 'btn-a' || id === 'btn-b' || id === 'btn-x' || id === 'btn-y')) {
        item = posMap['action-buttons'] || posMap['abxy'];
      }
      if (item && typeof item.x === 'number' && typeof item.y === 'number') {
        const scale = (typeof item.scale === 'number' && item.scale > 0) ? item.scale : 1.0;
        el.style.transform = `translate(${item.x}px, ${item.y}px) scale(${scale})`;
      } else {
        el.style.transform = 'translate(0px, 0px) scale(1)';
      }
    });
  }

  function setSelectedItem(layoutId) {
    selectedLayoutId = layoutId;
    document.querySelectorAll('.layout-item[data-layout-id]').forEach((el) => {
      el.classList.toggle('selected', el.getAttribute('data-layout-id') === layoutId);
    });

    if (layoutId) {
      const item = tempSessionPositions[layoutId] || { x: 0, y: 0, scale: 1.0 };
      const curScale = (typeof item.scale === 'number') ? item.scale : 1.0;
      lblScaleVal.textContent = `${Math.round(curScale * 100)}%`;
      layoutToolbarTitle.textContent = `${FRIENDLY_NAMES[layoutId] || layoutId}`;
    } else {
      lblScaleVal.textContent = '100%';
      layoutToolbarTitle.textContent = 'Toca un control para moverlo o escalarlo';
    }
  }

  function adjustScale(delta) {
    if (!selectedLayoutId) return;
    if (!tempSessionPositions[selectedLayoutId]) {
      tempSessionPositions[selectedLayoutId] = { x: 0, y: 0, scale: 1.0 };
    }
    const item = tempSessionPositions[selectedLayoutId];
    let curScale = (typeof item.scale === 'number') ? item.scale : 1.0;
    curScale = Math.max(0.5, Math.min(2.0, Math.round((curScale + delta) * 10) / 10));
    item.scale = curScale;

    lblScaleVal.textContent = `${Math.round(curScale * 100)}%`;

    const el = document.querySelector(`.layout-item[data-layout-id="${selectedLayoutId}"]`);
    if (el) {
      el.style.transform = `translate(${item.x}px, ${item.y}px) scale(${curScale})`;
    }
  }

  btnScaleDown.addEventListener('click', () => adjustScale(-0.1));
  btnScaleUp.addEventListener('click', () => adjustScale(0.1));

  function toggleEditLayout(forceState) {
    isEditingLayout = (forceState !== undefined) ? forceState : !isEditingLayout;
    document.body.classList.toggle('layout-editing', isEditingLayout);
    btnLayout.classList.toggle('active', isEditingLayout);

    if (isEditingLayout) {
      layoutToolbar.classList.remove('hidden');
      tempSessionPositions = JSON.parse(JSON.stringify(layoutPositions));
      if (tempSessionPositions['action-buttons'] && !tempSessionPositions['btn-a']) {
        const legacy = tempSessionPositions['action-buttons'];
        ['btn-a', 'btn-b', 'btn-x', 'btn-y'].forEach((k) => {
          tempSessionPositions[k] = JSON.parse(JSON.stringify(legacy));
        });
        delete tempSessionPositions['action-buttons'];
      }
      setSelectedItem('btn-a');
    } else {
      layoutToolbar.classList.add('hidden');
      setSelectedItem(null);
    }
  }

  btnLayout.addEventListener('click', () => toggleEditLayout());

  btnLayoutSave.addEventListener('click', () => {
    layoutPositions = JSON.parse(JSON.stringify(tempSessionPositions));
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(layoutPositions));
    } catch (e) {}
    toggleEditLayout(false);
  });

  btnLayoutReset.addEventListener('click', () => {
    layoutPositions = {};
    tempSessionPositions = {};
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
    applyPositions({});
    toggleEditLayout(false);
  });

  btnLayoutCancel.addEventListener('click', () => {
    applyPositions(layoutPositions);
    toggleEditLayout(false);
  });

  // Modal de Exportar / Importar
  btnLayoutExport.addEventListener('click', () => {
    modalTitle.textContent = 'Exportar Disposición';
    modalDesc.textContent = 'Copia este código o guárdalo como archivo para usar tu disposición personalizada en otros teléfonos:';
    modalTextarea.value = JSON.stringify(tempSessionPositions, null, 2);
    modalTextarea.readOnly = true;

    modalBtnCopy.classList.remove('hidden');
    modalBtnDownload.classList.remove('hidden');
    modalBtnUpload.classList.add('hidden');
    modalBtnApply.classList.add('hidden');

    layoutModal.classList.remove('hidden');
  });

  btnLayoutImport.addEventListener('click', () => {
    modalTitle.textContent = 'Importar Disposición';
    modalDesc.textContent = 'Pega un código de disposición JSON o carga un archivo guardado previamente:';
    modalTextarea.value = '';
    modalTextarea.readOnly = false;
    modalTextarea.placeholder = '{\n  "stick-left": { "x": 0, "y": 0, "scale": 1.0 },\n  "btn-a": { "x": 10, "y": 15, "scale": 1.1 },\n  "btn-b": { "x": 30, "y": 0, "scale": 1.0 },\n  ...\n}';

    modalBtnCopy.classList.add('hidden');
    modalBtnDownload.classList.add('hidden');
    modalBtnUpload.classList.remove('hidden');
    modalBtnApply.classList.remove('hidden');

    layoutModal.classList.remove('hidden');
  });

  btnModalClose.addEventListener('click', () => {
    layoutModal.classList.add('hidden');
  });

  modalBtnCopy.addEventListener('click', () => {
    if (modalTextarea.value) {
      navigator.clipboard.writeText(modalTextarea.value).then(() => {
        const prev = modalBtnCopy.textContent;
        modalBtnCopy.textContent = '¡Copiado!';
        setTimeout(() => { modalBtnCopy.textContent = prev; }, 1500);
      }).catch(() => {
        modalTextarea.select();
        document.execCommand('copy');
      });
    }
  });

  modalBtnDownload.addEventListener('click', () => {
    if (!modalTextarea.value) return;
    const blob = new Blob([modalTextarea.value], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `airpad_layout_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });

  modalBtnUpload.addEventListener('click', () => {
    modalFileInput.value = '';
    modalFileInput.click();
  });

  modalFileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      modalTextarea.value = ev.target.result;
    };
    reader.readAsText(file);
  });

  modalBtnApply.addEventListener('click', () => {
    try {
      const parsed = JSON.parse(modalTextarea.value);
      if (typeof parsed !== 'object' || parsed === null) throw new Error('Formato inválido');
      tempSessionPositions = parsed;
      applyPositions(tempSessionPositions);
      layoutModal.classList.add('hidden');
      if (selectedLayoutId) setSelectedItem(selectedLayoutId);
    } catch (err) {
      alert('Error: El texto proporcionado no es un JSON de disposición válido.');
    }
  });

  // Arrastre táctil y gesto de escala (Pinch-to-zoom) de elementos en modo edición
  document.querySelectorAll('.layout-item[data-layout-id]').forEach((el) => {
    const layoutId = el.getAttribute('data-layout-id');
    let isDragging = false;
    let startX = 0;
    let startY = 0;
    let initialX = 0;
    let initialY = 0;
    let initialScale = 1.0;
    let initialPinchDist = null;

    el.addEventListener('pointerdown', (e) => {
      if (!isEditingLayout) return;
      e.preventDefault();
      e.stopPropagation();

      setSelectedItem(layoutId);

      isDragging = true;
      startX = e.clientX;
      startY = e.clientY;

      if (!tempSessionPositions[layoutId]) {
        tempSessionPositions[layoutId] = { x: 0, y: 0, scale: 1.0 };
      }
      const cur = tempSessionPositions[layoutId];
      initialX = cur.x || 0;
      initialY = cur.y || 0;
      initialScale = (typeof cur.scale === 'number') ? cur.scale : 1.0;

      el.setPointerCapture(e.pointerId);
    });

    el.addEventListener('pointermove', (e) => {
      if (!isEditingLayout || !isDragging) return;
      e.preventDefault();
      e.stopPropagation();

      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      const nx = Math.round(initialX + dx);
      const ny = Math.round(initialY + dy);

      tempSessionPositions[layoutId].x = nx;
      tempSessionPositions[layoutId].y = ny;
      const scale = tempSessionPositions[layoutId].scale || 1.0;
      el.style.transform = `translate(${nx}px, ${ny}px) scale(${scale})`;
    });

    const onDragEnd = (e) => {
      if (!isEditingLayout || !isDragging) return;
      isDragging = false;
      if (el.hasPointerCapture(e.pointerId)) {
        try { el.releasePointerCapture(e.pointerId); } catch (err) {}
      }
    };

    el.addEventListener('pointerup', onDragEnd);
    el.addEventListener('pointercancel', onDragEnd);

    // Detección de gesto táctil de pellizco (Pinch-to-zoom) con 2 dedos en dispositivos móviles
    el.addEventListener('touchstart', (e) => {
      if (!isEditingLayout) return;
      if (e.touches.length === 2) {
        initialPinchDist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        const cur = tempSessionPositions[layoutId] || { x: 0, y: 0, scale: 1.0 };
        initialScale = cur.scale || 1.0;
      }
    }, { passive: true });

    el.addEventListener('touchmove', (e) => {
      if (!isEditingLayout) return;
      if (e.touches.length === 2 && initialPinchDist) {
        const curDist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        const ratio = curDist / initialPinchDist;
        let newScale = Math.max(0.5, Math.min(2.0, Math.round(initialScale * ratio * 10) / 10));

        if (!tempSessionPositions[layoutId]) {
          tempSessionPositions[layoutId] = { x: 0, y: 0, scale: 1.0 };
        }
        tempSessionPositions[layoutId].scale = newScale;
        const cur = tempSessionPositions[layoutId];
        el.style.transform = `translate(${cur.x || 0}px, ${cur.y || 0}px) scale(${newScale})`;
        lblScaleVal.textContent = `${Math.round(newScale * 100)}%`;
      }
    }, { passive: true });

    el.addEventListener('touchend', (e) => {
      if (e.touches.length < 2) {
        initialPinchDist = null;
      }
    }, { passive: true });
  });

  loadSavedLayout();

  // --- 10. Cambiar Tema Visual (Xbox / PlayStation) ---
  let isPlayStationTheme = false;
  btnTheme.addEventListener('click', () => {
    isPlayStationTheme = !isPlayStationTheme;
    document.body.classList.toggle('theme-ps', isPlayStationTheme);

    const btnY = document.querySelector('.btn-y .btn-text');
    const btnX = document.querySelector('.btn-x .btn-text');
    const btnB = document.querySelector('.btn-b .btn-text');
    const btnA = document.querySelector('.btn-a .btn-text');

    if (isPlayStationTheme) {
      if (btnY) btnY.textContent = '▲';
      if (btnX) btnX.textContent = '■';
      if (btnB) btnB.textContent = '●';
      if (btnA) btnA.textContent = '✖';
      document.getElementById('btn-back').textContent = 'SHARE';
      document.getElementById('btn-start').textContent = 'OPTIONS';
    } else {
      if (btnY) btnY.textContent = 'Y';
      if (btnX) btnX.textContent = 'X';
      if (btnB) btnB.textContent = 'B';
      if (btnA) btnA.textContent = 'A';
      document.getElementById('btn-back').textContent = 'SELECT';
      document.getElementById('btn-start').textContent = 'START';
    }
  });

  // --- 11. Pantalla Completa ---
  btnFullscreen.addEventListener('click', () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  });

  // --- 12. Puente Gamepad API (Mandos físicos conectados al teléfono) ---
  const physicalMap = [
    { idx: 0, name: 'A' }, { idx: 1, name: 'B' },
    { idx: 2, name: 'X' }, { idx: 3, name: 'Y' },
    { idx: 4, name: 'LB' }, { idx: 5, name: 'RB' },
    { idx: 8, name: 'BACK' }, { idx: 9, name: 'START' },
    { idx: 10, name: 'LS' }, { idx: 11, name: 'RS' },
    { idx: 12, name: 'UP' }, { idx: 13, name: 'DOWN' },
    { idx: 14, name: 'LEFT' }, { idx: 15, name: 'RIGHT' },
    { idx: 16, name: 'GUIDE' }
  ];

  let lastPhysButtons = {};

  function pollPhysicalGamepad() {
    if ('getGamepads' in navigator) {
      const pads = navigator.getGamepads();
      let pad = null;
      for (const p of pads) {
        if (p && p.connected) { pad = p; break; }
      }

      if (pad) {
        // Botones digitales
        for (const m of physicalMap) {
          if (m.idx < pad.buttons.length) {
            const pressed = pad.buttons[m.idx].pressed;
            if (lastPhysButtons[m.name] !== pressed) {
              lastPhysButtons[m.name] = pressed;
              onButtonStateChange(m.name, pressed);
            }
          }
        }
        // Gatillos analógicos
        if (pad.buttons.length > 7) {
          triggerLT = Math.round(pad.buttons[6].value * 255);
          triggerRT = Math.round(pad.buttons[7].value * 255);
          analogDirty = true;
        }
        // Ejes joysticks
        if (pad.axes.length >= 4) {
          stickLX = Math.round(Math.max(-1.0, Math.min(1.0, pad.axes[0])) * 32767);
          stickLY = Math.round(Math.max(-1.0, Math.min(1.0, pad.axes[1])) * 32767);
          stickRX = Math.round(Math.max(-1.0, Math.min(1.0, pad.axes[2])) * 32767);
          stickRY = Math.round(Math.max(-1.0, Math.min(1.0, pad.axes[3])) * 32767);
          analogDirty = true;
        }
      }
    }
    requestAnimationFrame(pollPhysicalGamepad);
  }

  requestAnimationFrame(pollPhysicalGamepad);

  // Iniciar conexión al cargar
  connectWebSocket();

})();
