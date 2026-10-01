"""
plugins/arduino_pedals/sim_arduino.py
Hardware simulator for Arduino Pedals.
Generates realistic analog potentiometer curves (sine/ramp) for Gas, Brake, and Clutch
and logs received vibration/rumble packets for automated testing.
"""

import math
import time
from typing import Tuple


class ArduinoSimulator:
    """Simulates an Arduino Nano/ESP32 sending periodic ADC telemetry (0-1023)."""

    def __init__(self):
        self._start_time = time.time()
        self.last_rumble_small = 0.0
        self.last_rumble_large = 0.0

    def read_frame(self) -> Tuple[int, int, int, bool]:
        """
        Returns (gas_adc, brake_adc, clutch_adc, handbrake_pressed).
        Simulates driver action: pressing gas, hitting brake, and clutch shifts.
        """
        t = time.time() - self._start_time

        # Gas pedal: smooth oscillation 100 to 950 ADC
        gas_norm = (math.sin(t * 1.5) + 1.0) / 2.0
        gas_adc = int(50 + gas_norm * 900)

        # Brake pedal: periodic braking spikes
        brake_norm = max(0.0, math.sin(t * 0.8 + 1.0)) ** 2
        brake_adc = int(30 + brake_norm * 920)

        # Clutch pedal: occasional clutch press
        clutch_norm = 1.0 if (int(t) % 6 == 0) else 0.0
        clutch_adc = int(40 + clutch_norm * 850)

        # Handbrake digital button
        handbrake = (int(t) % 10 == 0)

        return gas_adc, brake_adc, clutch_adc, handbrake

    def on_rumble_received(self, small: float, large: float):
        self.last_rumble_small = small
        self.last_rumble_large = large
        if large > 0.01 or small > 0.01:
            print(f"[SIMULATED ARDUINO] Haptic feedback received -> Large Motor: {large:.2f}, Small Motor: {small:.2f}")


if __name__ == "__main__":
    sim = ArduinoSimulator()
    print("[*] Running standalone Arduino Simulator test (Ctrl+C to stop)...")
    try:
        while True:
            g, b, c, h = sim.read_frame()
            print(f"Gas={g:4d} | Brake={b:4d} | Clutch={c:4d} | Handbrake={h}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("[*] Simulator stopped.")
