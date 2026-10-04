"""Unit tests for CLI argument parsing and commands."""

import io
import sys
import unittest
from unittest.mock import patch

from termux_llamacpp.cli import main


class TestCLIExecution(unittest.TestCase):
    def test_cli_help(self):
        with patch("sys.argv", ["termux-llama", "--help"]), patch("sys.stdout", new_callable=io.StringIO) as out:
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertEqual(ctx.exception.code, 0)
            output = out.getvalue()
            self.assertIn("termux-llama", output)
            self.assertIn("serve", output)
            self.assertIn("download", output)
            self.assertIn("find", output)

    def test_cli_models(self):
        with patch("sys.argv", ["termux-llama", "models"]), patch("sys.stdout", new_callable=io.StringIO) as out:
            main()
            output = out.getvalue()
            self.assertIn("qwen2.5-1.5b-instruct", output)
            self.assertIn("llama-3.2-1b-instruct", output)

    def test_cli_doctor(self):
        with patch("sys.argv", ["termux-llama", "doctor"]), patch("sys.stdout", new_callable=io.StringIO) as out:
            main()
            output = out.getvalue()
            self.assertIn("Architecture", output)

    def test_cli_run_without_model_fails_fast(self):
        with patch("sys.argv", ["termux-llama", "run"]), patch("sys.stderr", new_callable=io.StringIO) as err:
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("MODEL NOT SPECIFIED", err.getvalue())

    def test_cli_run_help_shows_rpc_flags(self):
        with patch("sys.argv", ["termux-llama", "run", "--help"]), patch("sys.stdout", new_callable=io.StringIO) as out:
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertEqual(ctx.exception.code, 0)
            output = out.getvalue()
            self.assertIn("--rpc", output)
            self.assertIn("--tensor-split", output)

    def test_cli_run_rpc_dispatch(self):
        with patch("sys.argv", [
            "termux-llama", "run", "qwen2.5-1.5b-instruct", "test prompt",
            "--rpc", "192.168.0.220:50052", "-ts", "50,50", "-ngl", "16"
        ]), patch("termux_llamacpp.cli.LlamaRuntime") as mock_runtime_cls:
            mock_runtime = mock_runtime_cls.return_value
            mock_runtime.generate.return_value = "mock response"
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                main()
                self.assertIn("mock response", out.getvalue())
                mock_runtime.generate.assert_called_once()
                kwargs = mock_runtime.generate.call_args.kwargs
                self.assertEqual(kwargs.get("rpc"), "192.168.0.220:50052")
                self.assertEqual(kwargs.get("tensor_split"), "50,50")
                self.assertEqual(kwargs.get("n_gpu_layers"), 16)


if __name__ == "__main__":
    unittest.main()
