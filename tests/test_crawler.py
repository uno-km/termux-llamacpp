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

    def test_rest_api_discovery_mock(self):
        """Verify standard REST API discovery formatting."""
        mock_response = [
            {
                "id": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
                "downloads": 12500,
                "likes": 420,
                "pipeline_tag": "text-generation"
            }
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = mock_response

            results = self.crawler.discover(query="Qwen", deep_crawl=False)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].repo_id, "Qwen/Qwen2.5-1.5B-Instruct-GGUF")
            self.assertEqual(results[0].downloads, 12500)
            self.assertIn("qwen2.5-1.5b-instruct-gguf", results[0].recommended_file.lower())


if __name__ == "__main__":
    unittest.main()
