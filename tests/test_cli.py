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


if __name__ == "__main__":
    unittest.main()
