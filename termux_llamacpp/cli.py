"""Command line interface for termux-llamacpp."""

import argparse
import sys
import time
from pathlib import Path

from termux_llamacpp.engine import LlamaRuntime
from termux_llamacpp.downloader import ModelManager
from termux_llamacpp.crawler import HuggingFaceCrawler
from termux_llamacpp.hardware import detect_hardware, print_hardware_summary
from termux_llamacpp.config import CURATED_MODELS, BUILD_PRESETS, LLAMA_CPP_PINNED_COMMIT
from termux_llamacpp.exceptions import (
    ModelNotFoundError,
    DependencyMissingError,
    TermuxLlamaError,
)


def cmd_install(args):
    """Execute native runtime toolchain compilation."""
    print(f"[termux-llama] Installing runtime with preset '{args.preset}' (Pinned Commit: {LLAMA_CPP_PINNED_COMMIT})...")
    try:
        runtime = LlamaRuntime.install(preset=args.preset, force_rebuild=args.force)
        print(f"[termux-llama] Runtime installation completed.")
    except Exception as e:
        print(f"[Error] {e}", file=sys.stderr)
        sys.exit(1)


def cmd_download(args):
    """Download GGUF model with SHA256 and manifest sidecar."""
    manager = ModelManager()
    try:
        path = manager.download(
            repo_id_or_alias=args.model,
            filename=args.filename,
            revision=args.revision,
            sha256=args.sha256,
            force=args.force,
        )
        print(f"[termux-llama] Successfully downloaded to: {path}")
    except TermuxLlamaError as e:
        print(f"\n[Error] {e}", file=sys.stderr)
        sys.exit(1)


def cmd_serve(args):
    """Start OpenAI and termux-aichain compliant server."""
    runtime = LlamaRuntime()
    try:
        server = runtime.serve(
            model=args.model,
            host=args.host,
            port=args.port,
            ctx_size=args.ctx,
            threads=args.threads,
        )
        print(f"\n[termux-llama] Server running at {server.endpoint} (Ctrl+C to stop)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[termux-llama] Stopping server...")
    except TermuxLlamaError as e:
        print(f"\n[Error] {e}", file=sys.stderr)
        sys.exit(1)


def cmd_find(args):
    """Search for GGUF models on Hugging Face."""
    crawler = HuggingFaceCrawler()
    print(f"[termux-llama] Searching Hugging Face for '{args.query}' (deep_crawl={args.deep})...")
    try:
        results = crawler.search_models(
            query=args.query,
            limit=args.limit,
            deep_crawl=args.deep,
        )
        if not results:
            print("[termux-llama] No models found.")
            return

        print(f"\nFound {len(results)} GGUF models:\n")
        for r in results:
            likes = f"❤️ {r.likes}" if r.likes else ""
            downloads = f"⬇️ {r.downloads}" if r.downloads else ""
            stats = f"({likes} {downloads})".strip()
            print(f" • {r.repo_id} {stats}")
            if r.direct_download_url:
                print(f"   URL: {r.direct_download_url}")
            if r.description:
                print(f"   Desc: {r.description[:80]}...")
            print()
    except DependencyMissingError as e:
        print(f"\n[Warning] {e}")
        print("Falling back to standard REST API search...")
        results = crawler.search_models(query=args.query, limit=args.limit, deep_crawl=False)
        for r in results:
            print(f" • {r.repo_id}")
    except Exception as e:
        print(f"[Error] Search failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    """List local downloaded GGUF models in cache."""
    manager = ModelManager()
    models = manager.list_local_models()
    if not models:
        print("[termux-llama] No cached models found in ~/.termux-llama/models/")
        return

    print(f"\nCached GGUF Models ({len(models)}):\n")
    for m in models:
        size_mb = m["size_bytes"] / (1024 * 1024)
        verified = " [VERIFIED]" if m.get("manifest_verified") else ""
        print(f" • {m['filename']}{verified}")
        print(f"   Size: {size_mb:.1f} MB | Model ID: {m.get('model_id', 'unknown')}")
        print(f"   Path: {m['path']}")
        print()


def cmd_curated(args):
    """Display curated high-performance model aliases."""
    print("\nCurated Recommended Models for Termux & ARM64:\n")
    print(f"{'Alias':<26} {'Size':<10} {'RAM':<10} {'Repo / File'}")
    print("-" * 75)
    for alias, info in CURATED_MODELS.items():
        print(f"{alias:<26} {info['size']:<10} {info['recommended_ram']:<10} {info['repo_id']}")
    print("\nTo download, run: termux-llama download <alias>\n")


def cmd_presets(args):
    """List available hardware build presets."""
    print("\nHardware Build Presets for llama.cpp:\n")
    print(f"{'Preset':<25} {'Opt Flags':<35} {'Description'}")
    print("-" * 80)
    for name, p in BUILD_PRESETS.items():
        print(f"{name:<25} {p['cflags']:<35} {p['description']}")
    print()


def cmd_doctor(args):
    """Diagnose hardware and installation environment."""
    print_hardware_summary()


def main():
    parser = argparse.ArgumentParser(
        prog="termux-llama",
        description="Universal GGUF Runtime, Model Manager & OpenAI Server for Android Termux & ARM64",
    )
    parser.add_argument("--version", action="version", version="termux-llamacpp 1.0.0b1")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # install
    p_install = subparsers.add_parser("install", help="Build/install pinned-commit llama.cpp runtime")
    p_install.add_argument("--preset", default="android-arm64-baseline", choices=list(BUILD_PRESETS.keys()), help="Target hardware preset")
    p_install.add_argument("--force", action="store_true", help="Force rebuild binaries")

    # download
    p_download = subparsers.add_parser("download", help="Download GGUF model with resume & SHA-256")
    p_download.add_argument("model", help="Model repo_id or curated alias (e.g. qwen2.5-1.5b-instruct)")
    p_download.add_argument("filename", nargs="?", default=None, help="GGUF filename (if not using alias)")
    p_download.add_argument("--revision", default="main", help="Hugging Face repo revision")
    p_download.add_argument("--sha256", default=None, help="Expected SHA-256 hash")
    p_download.add_argument("--force", action="store_true", help="Force re-download")

    # serve
    p_serve = subparsers.add_parser("serve", help="Start OpenAI/termux-aichain server")
    p_serve.add_argument("model", help="Model filename, alias, or direct path")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    p_serve.add_argument("--ctx", type=int, default=2048, help="Context length in tokens")
    p_serve.add_argument("--threads", type=int, default=None, help="CPU threads")

    # find
    p_find = subparsers.add_parser("find", help="Discover GGUF models on Hugging Face")
    p_find.add_argument("query", nargs="?", default="gguf", help="Search keyword")
    p_find.add_argument("--limit", type=int, default=10, help="Max results")
    p_find.add_argument("--deep", action="store_true", help="Use termux-playwright (P2 optional)")

    # list
    subparsers.add_parser("list", help="List downloaded GGUF models in cache")

    # models
    subparsers.add_parser("models", help="List curated model presets")

    # presets
    subparsers.add_parser("presets", help="List hardware build presets")

    # doctor / hardware
    subparsers.add_parser("doctor", help="Inspect hardware topology & binary status")
    subparsers.add_parser("hardware", help="Inspect hardware topology & binary status")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "install": cmd_install,
        "download": cmd_download,
        "serve": cmd_serve,
        "find": cmd_find,
        "list": cmd_list,
        "models": cmd_curated,
        "presets": cmd_presets,
        "doctor": cmd_doctor,
        "hardware": cmd_doctor,
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)


if __name__ == "__main__":
    main()
