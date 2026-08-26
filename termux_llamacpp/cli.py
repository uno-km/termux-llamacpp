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
    except ModelNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[termux-llama] Shutting down...")
        if 'server' in locals():
            server.stop()
    except Exception as e:
        print(f"[Error] {e}", file=sys.stderr)
        sys.exit(1)


def cmd_find(args):
    """Search Hugging Face for GGUF models via REST API."""
    crawler = HuggingFaceCrawler()
    print(f"[termux-llama] Searching Hugging Face for '{args.query}'...\n")
    try:
        models = crawler.discover(query=args.query, limit=args.limit, deep_crawl=args.deep)
        print(f"{'Repository ID':<45} | {'Downloads':<10} | {'Recommended File'}")
        print("-" * 80)
        for m in models:
            print(f"{m.repo_id:<45} | {m.downloads:<10,} | {m.recommended_file}")
        print("\n다운로드 예시: termux-llama download <repo_id> <filename>")
    except DependencyMissingError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[Error] {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    """List locally cached GGUF models."""
    manager = ModelManager()
    models = manager.list_local_models()
    print("================================================================================")
    print(f"  Local GGUF Models in Cache ({manager.models_dir})")
    print("================================================================================")
    if not models:
        print("  (No GGUF models found in local cache)")
        print("  다운로드 가이드: termux-llama download qwen2.5-1.5b-instruct")
    else:
        print(f"  {'Filename':<45} | {'Size':<10} | Full Path")
        print("  " + "-" * 76)
        for m in models:
            size_str = f"{m['size_mb']} MB"
            print(f"  {m['filename']:<45} | {size_str:<10} | {m['path']}")
    print("================================================================================")


def cmd_curated(args):
    """List pre-configured curated model presets."""
    print("================================================================================")
    print("  termux-llamacpp Curated Model Presets (from registry/models.json)")
    print("================================================================================")
    print(f"  {'Alias':<25} | {'Size':<8} | {'Quant':<6} | Description")
    print("  " + "-" * 76)
    for alias, info in CURATED_MODELS.items():
        print(f"  {alias:<25} | {info.size_mb:>6.0f}MB | {info.quant_type:<6} | {info.description}")
    print("\n  실행 가이드:")
    print("    termux-llama download qwen2.5-1.5b-instruct")
    print("    termux-llama serve qwen2.5-1.5b-instruct")
    print("================================================================================")


def cmd_presets(args):
    """List supported hardware build presets."""
    print("================================================================================")
    print("  Supported llama.cpp Build Presets")
    print("================================================================================")
    print(f"  {'Preset':<26} | {'Flags':<30} | Description")
    print("  " + "-" * 76)
    for name, p in BUILD_PRESETS.items():
        print(f"  {name:<26} | {p.cflags:<30} | {p.description}")
    print("================================================================================")


def cmd_doctor(args):
    """System hardware and runtime diagnostics."""
    print_hardware_summary()
    runtime = LlamaRuntime()
    print("  Pinned Commit       : " + LLAMA_CPP_PINNED_COMMIT)
    print("  llama.cpp Binaries  :")
    for b in ["llama-server", "llama-cli", "llama-quantize"]:
        path = runtime.get_binary_path(b)
        status = f"Found ({path})" if path else "Not Found (Run: termux-llama install)"
        print(f"    - {b:<16}: {status}")
    print("================================================================================\n")


def main():
    parser = argparse.ArgumentParser(
        prog="termux-llama",
        description="Universal GGUF Runtime, Model Manager & OpenAI Server for Android Termux & ARM64",
    )
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

    # doctor
    subparsers.add_parser("doctor", help="Inspect hardware topology & binary status")

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
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)


if __name__ == "__main__":
    main()
