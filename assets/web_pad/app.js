/**
 * app.js - Cliente Web Gamepad j360More AirPad
 * Soporta Screen Wake Lock, Multi-touch, Hápticos y Puente Gamepad API.
 */

(function () {
  'use strict';

  // --- 1. Elementos UI ---
  const connDot = document.getElementById('conn-dot');
  const connText = document.getElementById('conn-text');
  const playerBadge = document.getElementById('player-badge');
  const pingText = document.getElementById('ping-text');
  const btnTheme = document.getElementById('btn-theme');
  const btnFullscreen = document.getElementById('btn-fullscreen');

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

  // Activar en carga y re-activar al volver a la pestaña
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      requestWakeLock();
    }
  });

  // Re-intentar también en el primer toque de pantalla
  window.addEventListener('pointerdown', () => {
    if (!wakeLock) requestWakeLock();
  }, { once: true });

  // --- 3. Conexión WebSocket ---
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
    } catch (e) {
      setTimeout(connectWebSocket, 2000);
      return;
    }

    ws.onopen = () => {
      isConnected = true;
      connDot.className = 'dot connected';
      connText.textContent = 'Conectado';
      requestWakeLock();

      // Enviar información de dispositivo
      sendMsg({
        type: 'info',
        name: navigator.userAgent.includes('iPhone') ? 'iPhone' :
              navigator.userAgent.includes('Android') ? 'Android' : 'Móvil Web'
      });
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'welcome') {
          currentSlot = msg.slot;
          playerBadge.textContent = `P${msg.slot}`;
          if (msg.haptics !== undefined) hapticsEnabled = msg.haptics;
        } else if (msg.type === 'rumble') {
          handleRumble(msg.low, msg.high);
        } else if (msg.type === 'pong') {
          const rtt = Math.round(performance.now() - msg.t);
          pingText.textContent = `${rtt} ms`;
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

  // Heartbeat / Ping cada 2 segundos
  setInterval(() => {
    if (isConnected) {
      sendMsg({ type: 'ping', t: performance.now() });
    }
  }, 2000);

  // --- 4. Hápticos y Vibración ---
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

  // --- 5. Manejo de Botones Digitales y Gatillos ---
  function setupButton(el, btnName) {
    if (!el) return;

    el.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      e.stopPropagation();
      el.setPointerCapture(e.pointerId);
      el.classList.add('active');
      vibrateShort();

      if (btnName === 'LT' || btnName === 'RT') {
        sendMsg({ type: 'trigger', side: btnName === 'LT' ? 'L' : 'R', value: 1.0 });
        const meter = document.getElementById(btnName === 'LT' ? 'lt-meter' : 'rt-meter');
        if (meter) meter.style.width = '100%';
      } else {
        sendMsg({ type: 'btn', button: btnName, state: 1 });
      }
    });

    const onRelease = (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (el.hasPointerCapture(e.pointerId)) {
        try { el.releasePointerCapture(e.pointerId); } catch (err) {}
      }
      el.classList.remove('active');

      if (btnName === 'LT' || btnName === 'RT') {
        sendMsg({ type: 'trigger', side: btnName === 'LT' ? 'L' : 'R', value: 0.0 });
        const meter = document.getElementById(btnName === 'LT' ? 'lt-meter' : 'rt-meter');
        if (meter) meter.style.width = '0%';
      } else {
        sendMsg({ type: 'btn', button: btnName, state: 0 });
      }
    };

    el.addEventListener('pointerup', onRelease);
    el.addEventListener('pointercancel', onRelease);
    el.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  // Registrar todos los botones con data-btn
  document.querySelectorAll('[data-btn]').forEach((el) => {
    setupButton(el, el.getAttribute('data-btn'));
  });

  // --- 6. Joysticks Virtuales Analógicos ---
  function setupJoystick(baseId, knobId, stickName, clickBtnName) {
    const base = document.getElementById(baseId);
    const knob = document.getElementById(knobId);
    if (!base || !knob) return;

    let activePointerId = null;
    let lastTap = 0;
    const RADIUS = 45;

    function handleMove(clientX, clientY) {
      const rect = base.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;

      let dx = clientX - cx;
      let dy = clientY - cy;
      const dist = Math.hypot(dx, dy);

      if (dist > RADIUS) {
        dx = (dx / dist) * RADIUS;
        dy = (dy / dist) * RADIUS;
      }

      knob.style.transform = `translate(${dx}px, ${dy}px)`;

      // Normalizar [-1.0, 1.0] (formato estándar DirectInput: Y negativo hacia arriba, positivo hacia abajo)
      const normX = dx / RADIUS;
      const normY = dy / RADIUS;

      sendMsg({ type: 'joystick', stick: stickName, x: normX, y: normY });
    }

    base.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      e.stopPropagation();

      const now = Date.now();
      if (now - lastTap < 300) {
        // Doble toque rápido -> Stick Click (L3 / R3)
        vibrateShort();
        knob.classList.add('clicked');
        sendMsg({ type: 'btn', button: clickBtnName, state: 1 });
        setTimeout(() => {
          knob.classList.remove('clicked');
          sendMsg({ type: 'btn', button: clickBtnName, state: 0 });
        }, 150);
        lastTap = 0;
      } else {
        lastTap = now;
      }

      activePointerId = e.pointerId;
      base.setPointerCapture(e.pointerId);
      handleMove(e.clientX, e.clientY);
    });

    base.addEventListener('pointermove', (e) => {
      if (e.pointerId === activePointerId) {
        handleMove(e.clientX, e.clientY);
      }
    });

    const onStickEnd = (e) => {
      if (e.pointerId === activePointerId) {
        activePointerId = null;
        if (base.hasPointerCapture(e.pointerId)) {
          try { base.releasePointerCapture(e.pointerId); } catch (err) {}
        }
        knob.style.transform = 'translate(0px, 0px)';
        sendMsg({ type: 'joystick', stick: stickName, x: 0.0, y: 0.0 });
      }
    };

    base.addEventListener('pointerup', onStickEnd);
    base.addEventListener('pointercancel', onStickEnd);
  }

  setupJoystick('stick-left-base', 'stick-left-knob', 'L', 'LS');
  setupJoystick('stick-right-base', 'stick-right-knob', 'R', 'RS');

  // --- 7. Cambiar Tema Visual (Xbox / PlayStation) ---
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

  // --- 8. Pantalla Completa ---
  btnFullscreen.addEventListener('click', () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  });

  // --- 9. Puente Gamepad API (Mandos físicos conectados al teléfono) ---
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
        // Botones
        for (const m of physicalMap) {
          if (m.idx < pad.buttons.length) {
            const pressed = pad.buttons[m.idx].pressed;
            if (lastPhysButtons[m.name] !== pressed) {
              lastPhysButtons[m.name] = pressed;
              sendMsg({ type: 'btn', button: m.name, state: pressed ? 1 : 0 });
            }
          }
        }
        // Gatillos analógicos
        if (pad.buttons.length > 7) {
          sendMsg({ type: 'trigger', side: 'L', value: pad.buttons[6].value });
          sendMsg({ type: 'trigger', side: 'R', value: pad.buttons[7].value });
        }
        // Ejes joysticks
        if (pad.axes.length >= 4) {
          sendMsg({ type: 'joystick', stick: 'L', x: pad.axes[0], y: pad.axes[1] });
          sendMsg({ type: 'joystick', stick: 'R', x: pad.axes[2], y: pad.axes[3] });
        }
      }
    }
    requestAnimationFrame(pollPhysicalGamepad);
  }

  requestAnimationFrame(pollPhysicalGamepad);

  // Iniciar conexión al cargar
  connectWebSocket();

})();
