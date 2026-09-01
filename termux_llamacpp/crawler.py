"""Hugging Face GGUF Discovery Engine with Optional termux-playwright Scraper."""

import json
import os
import sys
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import requests

from termux_llamacpp.exceptions import DependencyMissingError, TermuxLlamaError


@dataclass
class DiscoveredGGUFModel:
    """Discovered Hugging Face GGUF model record."""
    repo_id: str
    name: str
    downloads: int
    likes: int
    pipeline_tag: str
    recommended_file: str
    download_url: str
    description: str = ""
    quant_types: List[str] = None


class HuggingFaceCrawler:
    """Hugging Face GGUF model discovery and web scraping manager."""

    def __init__(self, hf_token: Optional[str] = None):
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")
        self.headers = {"User-Agent": "termux-llamacpp/1.0.0 (ARM64 Android)"}
        if self.hf_token:
            self.headers["Authorization"] = f"Bearer {self.hf_token}"

    def check_playwright_installed(self) -> bool:
        """Check whether termux-playwright (or standard playwright) is installed."""
        try:
            import termux_playwright  # type: ignore
            return True
        except ImportError:
            try:
                import playwright  # type: ignore
                return True
            except ImportError:
                return False

    def discover(
        self,
        query: str = "gguf",
        limit: int = 10,
        deep_crawl: bool = False,
    ) -> List[DiscoveredGGUFModel]:
        """
        Discover GGUF models on Hugging Face.

        Args:
            query: Search keyword (e.g. 'qwen2.5 gguf', 'llama 3.2 gguf').
            limit: Maximum number of models to return.
            deep_crawl: If True, uses termux-playwright to render model pages and extract full file trees.

        Raises:
            DependencyMissingError: If deep_crawl is True but termux-playwright is not installed.
        """
        if deep_crawl:
            if not self.check_playwright_installed():
                self._print_playwright_warning()
                raise DependencyMissingError(
                    package_name="termux-playwright",
                    reason="Hugging Face 동적 페이지 렌더링 및 심층 GGUF 파일 테이블 크롤링"
                )
            return self._deep_crawl_with_playwright(query, limit)

        return self._rest_api_search(query, limit)

    def _print_playwright_warning(self):
        """Print prominent CLI warning banner when termux-playwright is absent."""
        print("\n" + "=" * 80)
        print(" [termux-llamacpp] DEPENDENCY WARNING: termux-playwright is not installed!")
        print("=" * 80)
        print(" Hugging Face 동적 페이지 렌더링 및 심층 GGUF 파일 크롤링을 위해 termux-playwright가 필요합니다.\n")
        print(" 다음 명령어를 실행하여 설치하십시오:")
        print("   [Python]  pip install termux-playwright")
        print("   [Node.js] npm install termux-playwright\n")
        print(" 일반 REST API 검색 모드를 사용하려면 deep_crawl=False 옵션으로 재시도하십시오.")
        print("=" * 80 + "\n")

    def _resolve_repo_gguf_files(self, repo_id: str) -> tuple:
        """Query Hugging Face model metadata API to discover actual .gguf files and quantization types."""
        url = f"https://huggingface.co/api/models/{repo_id}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
        except requests.RequestException as e:
            raise TermuxLlamaError(f"Network error querying metadata for Hugging Face repo '{repo_id}': {e}") from e

        if resp.status_code == 429:
            raise TermuxLlamaError(
                f"Hugging Face API rate limit reached (HTTP 429) while querying '{repo_id}'. "
                f"Please provide an HF_TOKEN or try again later."
            )
        if resp.status_code == 404:
            raise TermuxLlamaError(f"Hugging Face repository '{repo_id}' not found (HTTP 404).")
        if resp.status_code != 200:
            raise TermuxLlamaError(f"Hugging Face API returned HTTP {resp.status_code} for '{repo_id}': {resp.text}")

        data = resp.json()
        siblings = data.get("siblings", [])
        gguf_files = [
            s.get("rfilename") for s in siblings
            if isinstance(s, dict) and s.get("rfilename", "").lower().endswith(".gguf")
        ]
        if not gguf_files:
            raise TermuxLlamaError(f"No .gguf files found in repository '{repo_id}'.")

        # Detect quantization types from actual file names
        quant_types = []
        for gf in gguf_files:
            for q in ["Q4_K_M", "Q5_K_M", "Q8_0", "Q4_0", "Q4_K_S", "Q5_0", "Q6_K", "Q2_K", "Q3_K_M", "IQ4_XS", "IQ4_NL", "BF16", "F16"]:
                if q.lower() in gf.lower() and q not in quant_types:
                    quant_types.append(q)

        # Select optimal recommended file (priority: Q4_K_M > Q5_K_M > Q4_0 > Q8_0 > first available)
        preferred = None
        for q in ["Q4_K_M", "Q5_K_M", "Q4_0", "Q8_0", "IQ4_XS"]:
            for gf in gguf_files:
                if q.lower() in gf.lower():
                    preferred = gf
                    break
            if preferred:
                break

        rec_file = preferred or gguf_files[0]
        return rec_file, quant_types or ["Q4_K_M"]

    def _rest_api_search(self, query: str, limit: int) -> List[DiscoveredGGUFModel]:
        """Search Hugging Face Hub using the official REST API and resolve real file trees."""
        url = "https://huggingface.co/api/models"
        params = {
            "search": query,
            "filter": "gguf",
            "sort": "downloads",
            "direction": "-1",
            "limit": limit,
            "full": "false",
        }

        try:
            resp = requests.get(url, params=params, headers=self.headers, timeout=15)
            resp.raise_for_status()
            raw_models = resp.json()
        except Exception as e:
            raise TermuxLlamaError(f"Hugging Face API request failed: {e}") from e

        results: List[DiscoveredGGUFModel] = []
        for item in raw_models:
            repo_id = item.get("id", "")
            if not repo_id:
                continue
            downloads = item.get("downloads", 0)
            likes = item.get("likes", 0)
            pipeline_tag = item.get("pipeline_tag", "text-generation") or "text-generation"
            repo_name = repo_id.split("/")[-1]

            # Resolve actual GGUF file tree with fail-safe repository skip
            try:
                rec_file, quant_types = self._resolve_repo_gguf_files(repo_id)
            except Exception as resolve_err:
                print(f"[termux-llamacpp] Info: Skipping repository '{repo_id}' ({resolve_err})")
                continue

            download_url = f"https://huggingface.co/{repo_id}/resolve/main/{rec_file}"

            results.append(
                DiscoveredGGUFModel(
                    repo_id=repo_id,
                    name=repo_name,
                    downloads=downloads,
                    likes=likes,
                    pipeline_tag=pipeline_tag,
                    recommended_file=rec_file,
                    download_url=download_url,
                    description=f"Hugging Face GGUF repository ({downloads:,} downloads)",
                    quant_types=quant_types,
                )
            )

        return results

    def _deep_crawl_with_playwright(self, query: str, limit: int) -> List[DiscoveredGGUFModel]:
        """Execute headless browser scraping via termux-playwright and resolve real file trees."""
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except ImportError:
            from termux_playwright.sync_api import sync_playwright  # type: ignore

        print(f"[termux-llamacpp] Launching termux-playwright headless browser for deep crawl: '{query}'...")
        results: List[DiscoveredGGUFModel] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            search_url = f"https://huggingface.co/models?search={requests.utils.quote(query)}&pipeline_tag=text-generation"
            page.goto(search_url, timeout=30000)
            page.wait_for_selector("article", timeout=15000)

            articles = page.query_selector_all("article")
            for article in articles[:limit]:
                try:
                    title_elem = article.query_selector("h4, header a")
                    repo_id = title_elem.inner_text().strip() if title_elem else "unknown"
                    if "gguf" not in repo_id.lower() and "gguf" not in query.lower():
                        continue

                    repo_name = repo_id.split("/")[-1] if "/" in repo_id else repo_id
                    rec_file, quant_types = self._resolve_repo_gguf_files(repo_id)
                    download_url = f"https://huggingface.co/{repo_id}/resolve/main/{rec_file}"

                    results.append(
                        DiscoveredGGUFModel(
                            repo_id=repo_id,
                            name=repo_name,
                            downloads=0,
                            likes=0,
                            pipeline_tag="text-generation",
                            recommended_file=rec_file,
                            download_url=download_url,
                            description="Deep crawled via termux-playwright",
                            quant_types=quant_types,
                        )
                    )
                except Exception:
                    continue

            browser.close()

        return results


def discover_hf_models(query: str = "gguf", limit: int = 10, deep_crawl: bool = False) -> List[DiscoveredGGUFModel]:
    """Functional convenience entrypoint for model discovery."""
    crawler = HuggingFaceCrawler()
    return crawler.discover(query=query, limit=limit, deep_crawl=deep_crawl)
