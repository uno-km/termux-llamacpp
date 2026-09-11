"""Unit tests for GGUF model manager, cache resolution, and manifest creation."""

import json
import tempfile
import unittest
from pathlib import Path

from termux_llamacpp.downloader import ModelManager
from termux_llamacpp.security import compute_sha256
from termux_llamacpp.exceptions import ModelNotFoundError
from termux_llamacpp.config import CURATED_MODELS


class TestModelManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.models_dir = Path(self.temp_dir.name)
        self.manager = ModelManager(models_dir=self.models_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_model_raises_interrupt(self):
        """Test that querying a non-existent model raises ModelNotFoundError with instructions."""
        with self.assertRaises(ModelNotFoundError) as ctx:
            self.manager.resolve_model_path("non_existent_model_12345")

        err_msg = str(ctx.exception)
        self.assertIn("MODEL NOT FOUND", err_msg)
        self.assertIn("termux-llama download", err_msg)

    def test_existing_file_resolution(self):
        """Test resolving an existing GGUF model file."""
        fake_model = self.models_dir / "custom-model.gguf"
        fake_model.write_bytes(b"GGUF_TEST_HEADER_DATA")

        resolved = self.manager.resolve_model_path("custom-model.gguf")
        self.assertEqual(resolved, fake_model.resolve())

        resolved_no_ext = self.manager.resolve_model_path("custom-model")
        self.assertEqual(resolved_no_ext, fake_model.resolve())

        resolved_full = self.manager.resolve_model_path(str(fake_model))
        self.assertEqual(resolved_full, fake_model.resolve())

    def test_curated_alias_resolution_when_present(self):
        """Test resolving a curated model preset when the file exists in cache."""
        target_filename = CURATED_MODELS["qwen2.5-1.5b-instruct"].filename
        fake_qwen = self.models_dir / target_filename
        fake_qwen.write_bytes(b"GGUF_QWEN_MOCK")

        resolved = self.manager.resolve_model_path("qwen2.5-1.5b-instruct")
        self.assertEqual(resolved, fake_qwen.resolve())

    def test_sha256_calculation(self):
        """Test SHA-256 computation."""
        test_file = self.models_dir / "test.bin"
        test_file.write_bytes(b"Hello Uno-km Termux Llama")
        calculated = compute_sha256(test_file)
        self.assertEqual(len(calculated), 64)

    def test_license_acceptance_required(self):
        """Test that downloading models requiring acceptance without accept_license=True raises TermuxLlamaError."""
        from termux_llamacpp.exceptions import TermuxLlamaError
        with self.assertRaises(TermuxLlamaError) as ctx:
            self.manager.download("llama-3.2-1b-instruct", accept_license=False)
        self.assertIn("requires accepting its community license", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

