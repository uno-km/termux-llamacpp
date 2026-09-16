"""Unit tests for hardware topology and ARM64 feature detection."""

import os
import unittest
from termux_llamacpp.hardware import (
    detect_hardware,
    is_termux,
    is_android,
    is_termux_environment,
    is_android_environment,
    print_hardware_summary,
)


class TestHardwareDetection(unittest.TestCase):
    def test_detect_hardware_profile(self):
        hw = detect_hardware()
        self.assertIsNotNone(hw.arch)
        self.assertIsInstance(hw.is_arm64, bool)
        self.assertIsInstance(hw.is_termux, bool)
        self.assertIsInstance(hw.is_android, bool)
        # Test unified standard functions and backward compatibility alias equivalence
        self.assertIsInstance(is_termux(), bool)
        self.assertIsInstance(is_android(), bool)
        self.assertEqual(is_termux(), is_termux_environment())
        self.assertEqual(is_android(), is_android_environment())
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
            err_text = str(ctx.exception)
            self.assertIn("AMEVA-LLAMA-E001", err_text)
            self.assertIn("pip install ameva-runtime", err_text)

    def test_resolve_device_backend_vulkan_transparent_error_propagation(self):
        from unittest.mock import patch, MagicMock
        from termux_llamacpp.hardware import resolve_device_backend
        from termux_llamacpp.exceptions import TermuxLlamaError

        mock_avr = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.bind.side_effect = RuntimeError("Vulkan shader pipeline compilation failed: out of memory")
        mock_avr.adapters.llamacpp.LlamaCppAdapter = mock_adapter

        with patch("termux_llamacpp.hardware._resolve_ameva_runtime", return_value=mock_avr), \
             patch.dict("sys.modules", {"ameva_runtime.adapters.llamacpp": mock_avr.adapters.llamacpp}):
            with self.assertRaises(TermuxLlamaError) as ctx:
                resolve_device_backend("vulkan")
            self.assertIn("AMEVA-LLAMA-E002", str(ctx.exception))
            self.assertIn("Vulkan shader pipeline compilation failed", str(ctx.exception))
            self.assertIsInstance(ctx.exception.__cause__, RuntimeError)

    def test_resolve_device_backend_enforces_requested_ngl(self):
        from termux_llamacpp.hardware import resolve_device_backend
        backend, ngl = resolve_device_backend("cpu", requested_ngl=50)
        self.assertEqual(backend, "cpu")
        self.assertEqual(ngl, 0)  # CPU NEON strictly forces ngl=0

        backend, ngl = resolve_device_backend("auto", requested_ngl=77)
        self.assertEqual(ngl, 77)

    def test_unified_model_search_dirs(self):
        from termux_llamacpp.hardware import get_unified_model_search_dirs
        dirs = get_unified_model_search_dirs()
        self.assertIsInstance(dirs, list)
        self.assertGreater(len(dirs), 0)


if __name__ == "__main__":
    unittest.main()
