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


if __name__ == "__main__":
    unittest.main()
