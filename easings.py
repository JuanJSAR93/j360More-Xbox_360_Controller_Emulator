"""
Módulo de Curvas de Respuesta y Easing para Joysticks.
Implementa las curvas estándares de https://easings.net/ (Robert Penner / CSS)
y un interpolador cúbico monótono (PCHIP) para curvas personalizadas con nodos interactivos.
"""
from __future__ import annotations
import math
from typing import List, Tuple, Dict, Callable, Any

# =============================================================================
# CURVAS BÁSICAS
# =============================================================================

def linear(x: float) -> float:
    return max(0.0, min(1.0, x))

def exponential(x: float, sensitivity_pct: float = 0.0) -> float:
    x = max(0.0, min(1.0, x))
    s = max(-10.0, min(10.0, sensitivity_pct / 100.0))
    gamma = 2.0 ** (-s)
    return x ** gamma

def real_exponential(x: float) -> float:
    """
    Curva exponencial matemática real normalizada en [0.0, 1.0].
    f(x) = (e^(2x) - 1) / (e^2 - 1)
    Garantiza f(0)=0, f(1)=1 y crecimiento exponencial continuo y suave.
    """
    x = max(0.0, min(1.0, x))
    k = 2.0
    val = (math.exp(k * x) - 1.0) / (math.exp(k) - 1.0)
    return max(0.0, min(1.0, val))

# =============================================================================
# CURVAS EASINGS.NET (https://easings.net/)
# =============================================================================

# --- SINE ---
def ease_in_sine(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1.0 - math.cos((x * math.pi) / 2.0)

def ease_out_sine(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return math.sin((x * math.pi) / 2.0)

def ease_in_out_sine(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return -(math.cos(math.pi * x) - 1.0) / 2.0

# --- QUAD ---
def ease_in_quad(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x

def ease_out_quad(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1.0 - (1.0 - x) * (1.0 - x)

def ease_in_out_quad(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 2.0 * x * x if x < 0.5 else 1.0 - ((-2.0 * x + 2.0) ** 2) / 2.0

# --- CUBIC ---
def ease_in_cubic(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * x

def ease_out_cubic(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1.0 - (1.0 - x) ** 3

def ease_in_out_cubic(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 4.0 * x * x * x if x < 0.5 else 1.0 - ((-2.0 * x + 2.0) ** 3) / 2.0

# --- QUART ---
def ease_in_quart(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x ** 4

def ease_out_quart(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1.0 - (1.0 - x) ** 4

def ease_in_out_quart(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 8.0 * (x ** 4) if x < 0.5 else 1.0 - ((-2.0 * x + 2.0) ** 4) / 2.0

# --- QUINT ---
def ease_in_quint(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x ** 5

def ease_out_quint(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1.0 - (1.0 - x) ** 5

def ease_in_out_quint(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 16.0 * (x ** 5) if x < 0.5 else 1.0 - ((-2.0 * x + 2.0) ** 5) / 2.0

# --- EXPO ---
def ease_in_expo(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 0.0 if x <= 0.0 else (2.0 ** (10.0 * x - 10.0))

def ease_out_expo(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1.0 if x >= 1.0 else 1.0 - (2.0 ** (-10.0 * x))

def ease_in_out_expo(x: float) -> float:
    x = max(0.0, min(1.0, x))
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    return (2.0 ** (20.0 * x - 10.0)) / 2.0 if x < 0.5 else (2.0 - (2.0 ** (-20.0 * x + 10.0))) / 2.0

# --- CIRC ---
def ease_in_circ(x: float) -> float:
    x = max(0.0, min(1.0, x))
    clamped = max(0.0, min(1.0, 1.0 - x * x))
    return 1.0 - math.sqrt(clamped)

def ease_out_circ(x: float) -> float:
    x = max(0.0, min(1.0, x))
    clamped = max(0.0, min(1.0, 1.0 - (x - 1.0) ** 2))
    return math.sqrt(clamped)

def ease_in_out_circ(x: float) -> float:
    x = max(0.0, min(1.0, x))
    if x < 0.5:
        clamped = max(0.0, min(1.0, 1.0 - (2.0 * x) ** 2))
        return (1.0 - math.sqrt(clamped)) / 2.0
    else:
        clamped = max(0.0, min(1.0, 1.0 - (-2.0 * x + 2.0) ** 2))
        return (math.sqrt(clamped) + 1.0) / 2.0


# =============================================================================
# INTERPOLADOR CÚBICO MONÓTONO (PCHIP) PARA NODOS PERSONALIZADOS
# =============================================================================

DEFAULT_CUSTOM_NODES = [
    [0.0, 0.0],
    [0.125, 0.125],
    [0.25, 0.25],
    [0.375, 0.375],
    [0.5, 0.5],
    [0.625, 0.625],
    [0.75, 0.75],
    [0.875, 0.875],
    [1.0, 1.0]
]

def pchip_interpolate(x_val: float, xs: List[float], ys: List[float]) -> float:
    """
    Interpolación cúbica monótona de Fritsch-Carlson (PCHIP).
    Garantiza que no haya sobreoscilaciones (Runge) y que la función conserve
    la monotonía de los datos sin saltos abruptos.
    """
    n = len(xs)
    if n == 0:
        return x_val
    if n == 1:
        return ys[0]

    # Confinar x_val a los extremos
    if x_val <= xs[0]:
        return ys[0]
    if x_val >= xs[-1]:
        return ys[-1]

    # Calcular pendientes secantes (deltas)
    h = [xs[i+1] - xs[i] for i in range(n - 1)]
    delta = [(ys[i+1] - ys[i]) / h[i] if h[i] != 0 else 0.0 for i in range(n - 1)]

    # Calcular derivadas en los nodos d_k
    d = [0.0] * n
    # Extremos
    d[0] = delta[0]
    d[-1] = delta[-1]

    # Nodos interiores: media armónica modificada
    for i in range(1, n - 1):
        if delta[i-1] * delta[i] <= 0.0:
            d[i] = 0.0
        else:
            w1 = 2.0 * h[i] + h[i-1]
            w2 = h[i] + 2.0 * h[i-1]
            d[i] = (w1 + w2) / (w1 / delta[i-1] + w2 / delta[i])

    # Localizar intervalo [xs[k], xs[k+1]]
    k = 0
    for i in range(n - 1):
        if xs[i] <= x_val <= xs[i+1]:
            k = i
            break

    hk = h[k]
    if hk == 0:
        return ys[k]

    t = (x_val - xs[k]) / hk
    t2 = t * t
    t3 = t2 * t

    # Polinomios base de Hermite
    h00 = 2.0 * t3 - 3.0 * t2 + 1.0
    h10 = t3 - 2.0 * t2 + t
    h01 = -2.0 * t3 + 3.0 * t2
    h11 = t3 - t2

    res = h00 * ys[k] + h10 * hk * d[k] + h01 * ys[k+1] + h11 * hk * d[k+1]
    return max(0.0, min(1.0, res))

def evaluate_custom_nodes(x_val: float, custom_nodes: Any) -> float:
    """Evalúa un conjunto de nodos interactivos.
    Soporta lista de pares [[x0, y0], [x1, y1], ...] o lista de flotantes [y0, y1, ...].
    """
    if not custom_nodes:
        custom_nodes = DEFAULT_CUSTOM_NODES

    first = custom_nodes[0]
    if isinstance(first, (list, tuple)) and len(first) >= 2:
        # Formato [[x, y], ...]
        raw_pts = []
        for p in custom_nodes:
            try:
                raw_pts.append([max(0.0, min(1.0, float(p[0]))), max(0.0, min(1.0, float(p[1])))])
            except Exception:
                pass
        if not raw_pts:
            return x_val

        pts = sorted(raw_pts, key=lambda p: p[0])

        # Asegurar extremos 0.0 y 1.0
        if pts[0][0] > 0.0:
            pts.insert(0, [0.0, pts[0][1]])
        if pts[-1][0] < 1.0:
            pts.append([1.0, pts[-1][1]])

        xs = [pts[0][0]]
        ys = [pts[0][1]]
        for p in pts[1:]:
            curr_x = p[0]
            if curr_x <= xs[-1]:
                curr_x = xs[-1] + 0.0001
            xs.append(curr_x)
            ys.append(p[1])
    else:
        # Formato legado [y0, y1, ...]
        n = len(custom_nodes)
        if n < 2:
            return x_val
        xs = [i / (n - 1) for i in range(n)]
        ys = [max(0.0, min(1.0, float(y))) for y in custom_nodes]

    return pchip_interpolate(x_val, xs, ys)


# =============================================================================
# CATÁLOGO Y EVALUADOR CENTRAL
# =============================================================================

EASING_MAP: Dict[str, Callable[[float], float]] = {
    # Básicas
    "linear": linear,
    "exponential": None,        # Manejado con sensitivity_pct (Exponencial por defecto)
    "default": None,            # Alias de exponential
    "real_exponential": real_exponential,  # Curva exponencial matemática pura
    "custom": None,             # Manejado con custom_nodes

    # Sine
    "easeInSine": ease_in_sine,
    "easeOutSine": ease_out_sine,
    "easeInOutSine": ease_in_out_sine,

    # Quad
    "easeInQuad": ease_in_quad,
    "easeOutQuad": ease_out_quad,
    "easeInOutQuad": ease_in_out_quad,

    # Cubic
    "easeInCubic": ease_in_cubic,
    "easeOutCubic": ease_out_cubic,
    "easeInOutCubic": ease_in_out_cubic,

    # Quart
    "easeInQuart": ease_in_quart,
    "easeOutQuart": ease_out_quart,
    "easeInOutQuart": ease_in_out_quart,

    # Quint
    "easeInQuint": ease_in_quint,
    "easeOutQuint": ease_out_quint,
    "easeInOutQuint": ease_in_out_quint,

    # Expo
    "easeInExpo": ease_in_expo,
    "easeOutExpo": ease_out_expo,
    "easeInOutExpo": ease_in_out_expo,

    # Circ
    "easeInCirc": ease_in_circ,
    "easeOutCirc": ease_out_circ,
    "easeInOutCirc": ease_in_out_circ,
}

# Lista ordenada para el Combobox de la GUI
CURVE_CHOICES: List[Tuple[str, str, str]] = [
    # (id, nombre_es, nombre_en)
    ("exponential", "Exponencial (Por Defecto)", "Exponential (Default)"),
    ("real_exponential", "Exponencial", "Exponential"),
    ("linear", "Lineal (1:1)", "Linear (1:1)"),

    # Ease In
    ("easeInSine", "Ease In Sine (Suave)", "Ease In Sine (Gentle)"),
    ("easeInQuad", "Ease In Quad", "Ease In Quad"),
    ("easeInCubic", "Ease In Cubic (Microapuntado)", "Ease In Cubic (Micro-aim)"),
    ("easeInQuart", "Ease In Quart", "Ease In Quart"),
    ("easeInQuint", "Ease In Quint", "Ease In Quint"),
    ("easeInExpo", "Ease In Expo (Extremo)", "Ease In Expo (Extreme)"),
    ("easeInCirc", "Ease In Circ", "Ease In Circ"),

    # Ease Out
    ("easeOutSine", "Ease Out Sine (Reactiva)", "Ease Out Sine (Reactive)"),
    ("easeOutQuad", "Ease Out Quad", "Ease Out Quad"),
    ("easeOutCubic", "Ease Out Cubic (Acción Rápida)", "Ease Out Cubic (Fast Action)"),
    ("easeOutQuart", "Ease Out Quart", "Ease Out Quart"),
    ("easeOutQuint", "Ease Out Quint", "Ease Out Quint"),
    ("easeOutExpo", "Ease Out Expo (Instantánea)", "Ease Out Expo (Instant)"),
    ("easeOutCirc", "Ease Out Circ", "Ease Out Circ"),

    # Ease In-Out (Curvas S)
    ("easeInOutSine", "Ease In-Out Sine (Curva S Suave)", "Ease In-Out Sine (Soft S-Curve)"),
    ("easeInOutQuad", "Ease In-Out Quad (Curva S)", "Ease In-Out Quad (S-Curve)"),
    ("easeInOutCubic", "Ease In-Out Cubic (Curva S Clásica)", "Ease In-Out Cubic (Classic S-Curve)"),
    ("easeInOutQuart", "Ease In-Out Quart", "Ease In-Out Quart"),
    ("easeInOutQuint", "Ease In-Out Quint", "Ease In-Out Quint"),
    ("easeInOutExpo", "Ease In-Out Expo (Doble Rango)", "Ease In-Out Expo (Dual Range)"),
    ("easeInOutCirc", "Ease In-Out Circ", "Ease In-Out Circ"),

    # Personalizada
    ("custom", "Personalizada (Nodos)", "Custom (Nodes)"),
]

def evaluate_curve(curve_name: str, x: float, sensitivity_pct: float = 0.0, custom_nodes: List[float] = None) -> float:
    """
    Evalúa una curva normalizada x en [0.0, 1.0] -> y en [0.0, 1.0].
    Solo 'exponential' y 'default' (Exponencial por defecto) modulan con el slider de sensibilidad;
    todas las demás curvas se evalúan según su fórmula matemática pura.
    """
    x = max(0.0, min(1.0, x))
    c_type = curve_name or "exponential"

    if c_type in ("exponential", "default"):
        return exponential(x, sensitivity_pct)

    if c_type == "custom":
        return evaluate_custom_nodes(x, custom_nodes)

    fn = EASING_MAP.get(c_type)
    if fn:
        return fn(x)

    return x

def sample_curve_to_nodes(curve_name: str, sensitivity_pct: float = 0.0, num_nodes: int = 9, custom_nodes: Any = None) -> List[List[float]]:
    """
    Convierte una curva seleccionada a una lista de nodos editables [[x, y], ...].
    Si ya es 'custom' y cuenta con nodos, los devuelve en formato [[x, y], ...].
    Si es cualquier otro tipo de curva (easings, exponential, linear), muestrea 'num_nodes' puntos
    distribuidos a lo largo de esa curva exacta para poder editar sobre ella.
    """
    c_type = curve_name or "exponential"
    if c_type == "custom" and custom_nodes:
        first = custom_nodes[0]
        if isinstance(first, (list, tuple)) and len(first) >= 2:
            return [[round(float(p[0]), 3), round(float(p[1]), 3)] for p in custom_nodes]
        else:
            n = len(custom_nodes)
            return [[round(i / (n - 1), 3), round(float(custom_nodes[i]), 3)] for i in range(n)]

    count = max(3, num_nodes)
    sampled = []
    for i in range(count):
        t = i / (count - 1)
        y = evaluate_curve(c_type, t, sensitivity_pct)
        sampled.append([round(t, 3), round(max(0.0, min(1.0, y)), 3)])
    return sampled
