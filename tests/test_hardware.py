"""Unit tests for hardware topology and ARM64 feature detection."""

import os
import unittest
from termux_llamacpp.hardware import detect_hardware, is_termux_environment, is_android_environment, print_hardware_summary


class TestHardwareDetection(unittest.TestCase):
    def test_detect_hardware_profile(self):
        hw = detect_hardware()
        self.assertIsNotNone(hw.arch)
        self.assertIsInstance(hw.is_arm64, bool)
        self.assertIsInstance(hw.is_termux, bool)
        self.assertIsInstance(hw.is_android, bool)
        self.assertGreater(hw.cpu_count, 0)
        self.assertGreater(hw.recommended_threads, 0)
        self.assertGreater(hw.total_ram_mb, 0)
        self.assertGreater(hw.available_ram_mb, 0)

    def test_summary_printer(self):
        # Ensure printer runs without throwing exceptions
        print_hardware_summary()

    def test_resolve_device_backend_cpu(self):
        from termux_llamacpp.hardware import resolve_device_backend
        backend, ngl = resolve_device_backend("cpu")
        self.assertEqual(backend, "cpu")
        self.assertEqual(ngl, 0)

    def test_resolve_device_backend_auto(self):
        from termux_llamacpp.hardware import resolve_device_backend
        backend, ngl = resolve_device_backend("auto")
        self.assertIn(backend, ("cpu", "vulkan", "cpu_neon"))
        self.assertIsInstance(ngl, int)

    def test_resolve_device_backend_vulkan_fail_fast_without_runtime(self):
        from unittest.mock import patch
        from termux_llamacpp.hardware import resolve_device_backend
        from termux_llamacpp.exceptions import TermuxLlamaError

        with patch("termux_llamacpp.hardware._resolve_ameva_runtime", return_value=None):
            with self.assertRaises(TermuxLlamaError) as ctx:
                resolve_device_backend("vulkan")
            self.assertIn("AMEVA-LLAMA-E001", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
