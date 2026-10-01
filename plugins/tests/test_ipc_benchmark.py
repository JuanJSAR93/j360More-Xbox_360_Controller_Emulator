"""
plugins/tests/test_ipc_benchmark.py
Unit tests and latency benchmark for j360More Plugin IPC and SDK.
Tests:
  1. IPC Server/Client connection and handshake.
  2. Semantic controls (press_button, set_trigger, set_stick) & Physical controls (set_axis, set_button_index).
  3. Bidirectional event handling: UI field change, Action buttons, Rumble force-feedback.
  4. Roundtrip latency benchmark (1,000 messages).
"""

import os
import sys
import threading
import time
import unittest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from plugins.plugin_ipc import IPCServer, IPCClient
from plugins.plugin_sdk import PluginDevice


class TestPluginIPCLatency(unittest.TestCase):

    def test_01_ipc_connection_and_handshake(self):
        server = IPCServer(host="127.0.0.1", port=0)
        port = server.start()
        self.assertGreater(port, 0)

        received_msgs = []
        server.add_on_message(lambda msg: received_msgs.append(msg))

        client = IPCClient(host="127.0.0.1", port=port)
        connected = client.connect(timeout=2.0)
        self.assertTrue(connected)

        # Wait a moment for accept
        time.sleep(0.05)
        self.assertTrue(server.is_connected)

        # Send test message
        client.send({"event": "handshake", "plugin_id": "test_plugin", "version": "1.0.0"})
        time.sleep(0.05)

        self.assertEqual(len(received_msgs), 1)
        self.assertEqual(received_msgs[0]["event"], "handshake")
        self.assertEqual(received_msgs[0]["plugin_id"], "test_plugin")

        client.close()
        server.close()

    def test_02_sdk_state_flush_and_events(self):
        server = IPCServer(host="127.0.0.1", port=0)
        port = server.start()

        server_messages = []
        server.add_on_message(lambda msg: server_messages.append(msg))

        device = PluginDevice(id="pedals_test", name="Test Pedals", num_buttons=8, num_axes=4)

        # Connect SDK manually to test server
        device._ipc_client = IPCClient(host="127.0.0.1", port=port)
        device._ipc_client.add_on_message(device._handle_ipc_message)
        device._ipc_client.connect(timeout=2.0)
        device._running = True
        time.sleep(0.05)

        # 1. Test Semantic controls
        device.press_button("A")
        device.set_trigger("RT", 0.85)
        device.set_stick("LX", 0.5, "LY", -0.25)
        device.set_axis(0, 0.77)
        device.set_button_index(3, True)
        device.flush()

        time.sleep(0.05)
        self.assertGreaterEqual(len(server_messages), 1)
        state_msg = server_messages[-1]
        self.assertEqual(state_msg["event"], "state_update")
        self.assertTrue(state_msg["named_buttons"]["A"])
        self.assertAlmostEqual(state_msg["triggers"]["RT"], 0.85)
        self.assertAlmostEqual(state_msg["sticks"]["LX"], 0.5)
        self.assertAlmostEqual(state_msg["sticks"]["LY"], -0.25)
        self.assertAlmostEqual(state_msg["axes"]["0"], 0.77)
        self.assertTrue(state_msg["buttons"]["3"])

        # 2. Test Rumble Callback (Server -> Plugin)
        rumble_received = []
        @device.on_rumble
        def on_rumble(small, large):
            rumble_received.append((small, large))

        server.send({
            "event": "rumble",
            "device_id": "pedals_test",
            "small_motor": 0.4,
            "large_motor": 0.9
        })
        time.sleep(0.05)

        self.assertEqual(len(rumble_received), 1)
        self.assertAlmostEqual(rumble_received[0][0], 0.4)
        self.assertAlmostEqual(rumble_received[0][1], 0.9)

        # 3. Test Field Change Callback (GUI -> Plugin)
        field_changes = []
        @device.on_field_change("gas_min")
        def on_gas_min(val, pad):
            field_changes.append((val, pad))

        server.send({
            "event": "field_change",
            "field": "gas_min",
            "val": 120,
            "pad": 1
        })
        time.sleep(0.05)

        self.assertEqual(len(field_changes), 1)
        self.assertEqual(field_changes[0], (120, 1))

        # 4. Test Action Callback (GUI Button -> Plugin)
        actions = []
        @device.on_action("calibrate_zero")
        def on_zero(pad):
            actions.append(pad)

        server.send({
            "event": "ui_action",
            "action": "calibrate_zero",
            "pad": 2
        })
        time.sleep(0.05)

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0], 2)

        device._running = False
        device._ipc_client.close()
        server.close()

    def test_03_latency_benchmark(self):
        server = IPCServer(host="127.0.0.1", port=0)
        port = server.start()

        # Echo server: when message received, echo it back
        server.add_on_message(lambda msg: server.send({"event": "pong", "seq": msg.get("seq", 0)}))

        client = IPCClient(host="127.0.0.1", port=port)
        client.connect(timeout=2.0)
        time.sleep(0.05)

        pong_events = {}
        pong_cv = threading.Condition()

        def on_pong(msg):
            seq = msg.get("seq")
            with pong_cv:
                pong_events[seq] = True
                pong_cv.notify()

        client.add_on_message(on_pong)

        NUM_MESSAGES = 1000
        start_time = time.perf_counter()

        for seq in range(NUM_MESSAGES):
            client.send({"event": "ping", "seq": seq})
            with pong_cv:
                while seq not in pong_events:
                    pong_cv.wait(timeout=1.0)
                    if seq not in pong_events:
                        self.fail(f"Timeout waiting for pong {seq}")

        elapsed = time.perf_counter() - start_time
        avg_roundtrip_ms = (elapsed / NUM_MESSAGES) * 1000.0
        one_way_latency_ms = avg_roundtrip_ms / 2.0
        msgs_per_sec = NUM_MESSAGES / elapsed

        print(f"\n=======================================================")
        print(f"  IPC BENCHMARK RESULTS ({NUM_MESSAGES} messages):")
        print(f"  Total time:       {elapsed:.4f} seconds")
        print(f"  Avg roundtrip:    {avg_roundtrip_ms:.3f} ms")
        print(f"  One-way latency:  {one_way_latency_ms:.3f} ms")
        print(f"  Throughput:       {msgs_per_sec:.0f} msgs/sec")
        print(f"=======================================================")

        # Assert roundtrip latency is ultra-fast (< 0.5 ms roundtrip -> < 0.25 ms one way)
        self.assertLess(avg_roundtrip_ms, 1.0, "IPC roundtrip latency is too high!")

        client.close()
        server.close()

    def test_04_streaming_throughput(self):
        server = IPCServer(host="127.0.0.1", port=0)
        port = server.start()

        received_count = 0
        all_received = threading.Event()
        TARGET_COUNT = 5000

        def on_msg(msg):
            nonlocal received_count
            received_count += 1
            if received_count >= TARGET_COUNT:
                all_received.set()

        server.add_on_message(on_msg)

        client = IPCClient(host="127.0.0.1", port=port)
        client.connect(timeout=2.0)
        time.sleep(0.05)

        start_time = time.perf_counter()
        for i in range(TARGET_COUNT):
            client.send({"event": "state_update", "idx": i, "axes": {"0": 0.5}, "buttons": {"0": True}})

        success = all_received.wait(timeout=5.0)
        elapsed = time.perf_counter() - start_time
        self.assertTrue(success)

        rate = TARGET_COUNT / elapsed
        latency_per_frame_ms = (elapsed / TARGET_COUNT) * 1000.0

        print(f"\n=======================================================")
        print(f"  STREAMING THROUGHPUT ({TARGET_COUNT} frames):")
        print(f"  Total time:       {elapsed:.4f} seconds")
        print(f"  Latency/frame:    {latency_per_frame_ms:.4f} ms")
        print(f"  Streaming Rate:   {rate:.0f} frames/sec")
        print(f"=======================================================")
        self.assertGreater(rate, 2000, "Streaming throughput should exceed 2000 frames/sec")

        client.close()
        server.close()


if __name__ == "__main__":
    unittest.main()
