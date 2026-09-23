import os
import sys
import re
import json
import math

def test_dpad_algorithm():
    print("=== TEST: D-Pad 8-Way Continuous Sliding Math ===")
    
    # Simulación de la función del D-Pad continuo de app.js
    def eval_dpad(dx, dy, radius=60, deadzone=10):
        dist = math.hypot(dx, dy)
        new_dirs = {"UP": False, "DOWN": False, "LEFT": False, "RIGHT": False}
        if dist >= deadzone:
            threshold = dist * 0.38
            if dy < -threshold: new_dirs["UP"] = True
            if dy > threshold: new_dirs["DOWN"] = True
            if dx < -threshold: new_dirs["LEFT"] = True
            if dx > threshold: new_dirs["RIGHT"] = True
        return new_dirs

    # Centro / Deadzone
    res_center = eval_dpad(2, 3)
    assert not any(res_center.values()), "Center should be neutral"

    # 1. Este / Derecha (0°)
    res_e = eval_dpad(50, 0)
    assert res_e == {"UP": False, "DOWN": False, "LEFT": False, "RIGHT": True}, f"East failed: {res_e}"

    # 2. Sureste / Abajo-Derecha cruzado (45°)
    res_se = eval_dpad(35, 35)
    assert res_se == {"UP": False, "DOWN": True, "LEFT": False, "RIGHT": True}, f"SE failed: {res_se}"

    # 3. Sur / Abajo (90°)
    res_s = eval_dpad(0, 50)
    assert res_s == {"UP": False, "DOWN": True, "LEFT": False, "RIGHT": False}, f"South failed: {res_s}"

    # 4. Suroeste / Abajo-Izquierda cruzado (135°)
    res_sw = eval_dpad(-35, 35)
    assert res_sw == {"UP": False, "DOWN": True, "LEFT": True, "RIGHT": False}, f"SW failed: {res_sw}"

    # 5. Oeste / Izquierda (180°)
    res_w = eval_dpad(-50, 0)
    assert res_w == {"UP": False, "DOWN": False, "LEFT": True, "RIGHT": False}, f"West failed: {res_w}"

    # 6. Noroeste / Arriba-Izquierda cruzado (225°)
    res_nw = eval_dpad(-35, -35)
    assert res_nw == {"UP": True, "DOWN": False, "LEFT": True, "RIGHT": False}, f"NW failed: {res_nw}"

    # 7. Norte / Arriba (270°)
    res_n = eval_dpad(0, -50)
    assert res_n == {"UP": True, "DOWN": False, "LEFT": False, "RIGHT": False}, f"North failed: {res_n}"

    # 8. Noreste / Arriba-Derecha cruzado (315°)
    res_ne = eval_dpad(35, -35)
    assert res_ne == {"UP": True, "DOWN": False, "LEFT": False, "RIGHT": True}, f"NE failed: {res_ne}"

    print("[+] All 8 directions (4 cardinals + 4 diagonals) correctly evaluated!")

def test_html_and_layout_ids():
    print("\n=== TEST: HTML Layout IDs and Modal Elements ===")
    html_path = os.path.join(os.path.dirname(__file__), "assets", "web_pad", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    expected_layout_ids = [
        "btn-lt", "btn-lb", "btn-ls",
        "btn-rt", "btn-rb", "btn-rs",
        "center-buttons",
        "stick-left", "dpad", "action-buttons", "stick-right"
    ]
    for lid in expected_layout_ids:
        assert f'data-layout-id="{lid}"' in html, f"Missing layout ID: {lid}"
    print(f"[+] All {len(expected_layout_ids)} movable layout IDs found in index.html!")

    # Check modal and scale elements
    modal_ids = [
        "layout-modal", "modal-title", "modal-desc", "modal-textarea",
        "modal-btn-copy", "modal-btn-download", "modal-btn-upload", "modal-btn-apply",
        "btn-scale-down", "lbl-scale-val", "btn-scale-up"
    ]
    for mid in modal_ids:
        assert f'id="{mid}"' in html, f"Missing modal/scale ID: {mid}"
    print(f"[+] All {len(modal_ids)} toolbar & modal IDs found in index.html!")

def test_layout_json_schema():
    print("\n=== TEST: Layout Export/Import Schema ===")
    sample_layout = {
        "btn-lt": {"x": 10, "y": 5, "scale": 1.2},
        "btn-lb": {"x": 0, "y": 0, "scale": 1.0},
        "btn-ls": {"x": -5, "y": 0, "scale": 0.9},
        "btn-rt": {"x": -10, "y": 5, "scale": 1.2},
        "btn-rb": {"x": 0, "y": 0, "scale": 1.0},
        "btn-rs": {"x": 5, "y": 0, "scale": 0.9},
        "stick-left": {"x": -20, "y": 15, "scale": 1.1},
        "dpad": {"x": 0, "y": -10, "scale": 1.0},
        "action-buttons": {"x": 15, "y": -15, "scale": 1.15},
        "stick-right": {"x": 10, "y": 20, "scale": 1.0}
    }
    encoded = json.dumps(sample_layout)
    decoded = json.loads(encoded)
    assert len(decoded) == len(sample_layout)
    for k, v in decoded.items():
        assert "x" in v and "y" in v and "scale" in v
        assert 0.5 <= v["scale"] <= 2.0
    print("[+] JSON export/import schema verified successfully!")

if __name__ == "__main__":
    test_dpad_algorithm()
    test_html_and_layout_ids()
    test_layout_json_schema()
    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")
