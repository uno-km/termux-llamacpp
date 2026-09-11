"""Unit tests for Hugging Face crawler and termux-playwright dependency checking."""

import unittest
from unittest.mock import patch

from termux_llamacpp.crawler import HuggingFaceCrawler
from termux_llamacpp.exceptions import DependencyMissingError


class TestHuggingFaceCrawler(unittest.TestCase):
    def setUp(self):
        self.crawler = HuggingFaceCrawler()

    def test_playwright_missing_raises_dependency_error(self):
        """Verify that requesting deep_crawl when playwright is absent raises DependencyMissingError."""
        with patch.object(self.crawler, "check_playwright_installed", return_value=False):
            with self.assertRaises(DependencyMissingError) as ctx:
                self.crawler.discover(query="qwen2.5 gguf", deep_crawl=True)

            err = str(ctx.exception)
            self.assertIn("DEPENDENCY MISSING", err)
            self.assertIn("pip install termux-playwright", err)
            self.assertIn("npm install termux-playwright", err)

    def test_resolve_repo_gguf_files_from_siblings(self):
        """Verify that _resolve_repo_gguf_files parses siblings and picks optimal quantization."""
        mock_model_info = {
            "siblings": [
                {"rfilename": "README.md"},
                {"rfilename": "config.json"},
                {"rfilename": "Llama-3.2-3B-Instruct-Q8_0.gguf"},
                {"rfilename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf"},
                {"rfilename": "Llama-3.2-3B-Instruct-Q5_K_M.gguf"},
            ]
        }
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = mock_model_info

            rec_file, quants = self.crawler._resolve_repo_gguf_files("bartowski/Llama-3.2-3B-Instruct-GGUF")
            self.assertEqual(rec_file, "Llama-3.2-3B-Instruct-Q4_K_M.gguf")
            self.assertIn("Q4_K_M", quants)
            self.assertIn("Q5_K_M", quants)
            self.assertIn("Q8_0", quants)

    def test_resolve_repo_gguf_files_raises_on_no_gguf(self):
        """Verify that repositories without .gguf files raise TermuxLlamaError instead of guessing."""
        mock_model_info = {
            "siblings": [
                {"rfilename": "README.md"},
                {"rfilename": "pytorch_model.bin"},
            ]
        }
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = mock_model_info

            with self.assertRaises(Exception) as ctx:
                self.crawler._resolve_repo_gguf_files("some-user/non-gguf-repo")
            self.assertIn("no .gguf files found", str(ctx.exception).lower())

    def test_resolve_repo_gguf_files_raises_on_429_rate_limit(self):
        """Verify that HTTP 429 rate limits raise explicit TermuxLlamaError with rate limit guidance."""
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 429
            mock_get.return_value.text = "Rate limit exceeded"

            with self.assertRaises(Exception) as ctx:
                self.crawler._resolve_repo_gguf_files("some-user/rate-limited-repo")
            self.assertIn("rate limit", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
