"""Command line interface for termux-llamacpp."""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
import requests

logger = logging.getLogger("termux_llamacpp.cli")

from termux_llamacpp import __version__
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
    if getattr(args, "daemon", False):
        import shutil
        py_bin = sys.executable or "python3"
        cmd = [
            py_bin,
            "-m", "termux_llamacpp",
            "serve",
            str(args.model),
            "--host", str(args.host),
            "--port", str(args.port),
            "--ctx", str(args.ctx),
        ]
        if args.threads is not None:
            cmd.extend(["--threads", str(args.threads)])

        log_dir = Path.home() / ".termux-llama" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "daemon.log"
        log_handle = open(log_file, "a", encoding="utf-8")

        popen_kwargs = {
            "stdout": log_handle,
            "stderr": subprocess.STDOUT,
        }
        if sys.platform != "win32":
            popen_kwargs["start_new_session"] = True

        proc = subprocess.Popen(cmd, **popen_kwargs)

        print("================================================================================")
        print(f"  [termux-llamacpp] Launching Background Server Daemon (PID: {proc.pid})")
        print("================================================================================")
        print(f"  Endpoint : http://{args.host}:{args.port}")
        print(f"  Log File : {log_file}")
        print("================================================================================")

        endpoint = f"http://{args.host}:{args.port}"
        print(f"[termux-llama] Loading model & initializing server at {endpoint}...")
        dots = [".", "..", "...", "....", "....."]
        ready = False
        start_time = time.time()
        try:
            for i in range(120):  # up to 60s
                time.sleep(0.5)
                elapsed = int(time.time() - start_time)
                dot = dots[i % len(dots)]
                sys.stdout.write(f"\r[*] Warmup in progress (Elapsed: {elapsed}s) {dot:<6}")
                sys.stdout.flush()
                try:
                    r = requests.get(f"{endpoint}/health", timeout=1)
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("ready") is True or data.get("status") in {"ok", "ready", "healthy"}:
                            ready = True
                            break
                    else:
                        logger.debug("Health probe returned status code %d", r.status_code)
                except requests.exceptions.Timeout:
                    logger.debug("Health probe timed out (attempt %d/120)", i + 1)
                except requests.exceptions.ConnectionError:
                    logger.debug("Health probe connection refused (server booting, attempt %d/120)", i + 1)
                except Exception as exc:
                    logger.debug("Health probe error during warmup: %s", exc)
        except KeyboardInterrupt:
            print("\n\n[termux-llama] Initialization cancelled by user. Terminating server...")
            try:
                proc.terminate()
            except Exception:
                pass
            cmd_stop(args)
            return

        print()  # newline
        if ready:
            print(f"[termux-llama] Server is ACTIVE and READY on {endpoint} (PID: {proc.pid})")
        else:
            print(f"[termux-llama] Background server launched (PID: {proc.pid}). Check logs at {log_file}")
        print("[termux-llama] Use 'termux-llama stop' to stop server.\n")
        return

    runtime = LlamaRuntime()
    try:
        server = runtime.serve(
            model=args.model,
            host=args.host,
            port=args.port,
            ctx_size=args.ctx,
            threads=args.threads,
            device=getattr(args, "device", "auto"),
        )
        print(f"\n[termux-llama] Server running at {server.endpoint} (Ctrl+C to stop)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[termux-llama] Stopping server...")
    except TermuxLlamaError as e:
        print(f"\n[Error] {e}", file=sys.stderr)
        sys.exit(1)


def cmd_run(args):
    """Run direct one-shot text generation with strict device routing."""
    runtime = LlamaRuntime()
    # Resolve prompt from flag or positional argument
    prompt_val = getattr(args, "prompt_flag", None) or getattr(args, "prompt", None) or getattr(args, "prompt_pos", "")
    model_val = args.model

    # If only one positional argument was provided and prompt is empty, check if model is prompt
    if model_val and not prompt_val:
        # Check if model_val looks like prompt
        if not (model_val.endswith(".gguf") or model_val in CURATED_MODELS):
            prompt_val = model_val
            model_val = None

    if not prompt_val:
        print("[Error] Input prompt is required. Use 'termux-llama run [model] <prompt>' or 'termux-llama run -p \"<prompt>\"'", file=sys.stderr)
        sys.exit(1)

    try:
        output = runtime.generate(
            model=model_val,
            prompt=prompt_val,
            max_tokens=args.max_tokens,
            temperature=args.temp,
            threads=args.threads,
            device=args.device,
        )
        print(output)
    except TermuxLlamaError as e:
        print(f"\n[Error] {e}", file=sys.stderr)
        sys.exit(1)



def cmd_stop(args):
    """Stop running termux-llama server instances via tracked PID files without collateral pkill."""
    import signal
    from termux_llamacpp.config import DEFAULT_RUN_DIR
    from termux_llamacpp.server import ProcessIdentityLock

    print("[termux-llama] Stopping running server instance via tracked PID ledger...")
    stopped_count = 0

    # 1. Read ProcessIdentityLock metadata
    lock_mgr = ProcessIdentityLock(run_dir=DEFAULT_RUN_DIR)
    metadata = lock_mgr.read_metadata()
    target_pids = set()

    if metadata:
        if "native_pid" in metadata and int(metadata["native_pid"]) > 0:
            target_pids.add(int(metadata["native_pid"]))
        if "lock_owner_pid" in metadata and int(metadata["lock_owner_pid"]) > 0:
            target_pids.add(int(metadata["lock_owner_pid"]))
        if "supervisor_pid" in metadata and int(metadata["supervisor_pid"]) > 0:
            target_pids.add(int(metadata["supervisor_pid"]))

    # 2. Check explicit server.pid file
    pid_file = DEFAULT_RUN_DIR / "server.pid"
    if pid_file.is_file():
        try:
            pid_content = pid_file.read_text(encoding="utf-8").strip()
            if pid_content.isdigit():
                target_pids.add(int(pid_content))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to read PID file '%s': %s", pid_file, e)

    # 3. Gracefully terminate target PIDs only
    for pid in target_pids:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"[termux-llama] Sent SIGTERM to tracked server process (PID: {pid}).")
            stopped_count += 1
        except (ProcessLookupError, PermissionError) as e:
            print(f"[termux-llama] PID {pid} is not running or already terminated: {e}")

    # 4. Clean up state
    if lock_mgr.lock_file.exists():
        try:
            lock_mgr.lock_file.unlink(missing_ok=True)
            logger.debug("Cleaned up lock file: %s", lock_mgr.lock_file)
        except OSError as e:
            logger.warning("[termux-llamacpp] Failed to remove lock file (%s): %s", lock_mgr.lock_file, e)
    if pid_file.exists():
        try:
            pid_file.unlink(missing_ok=True)
            logger.debug("Cleaned up PID file: %s", pid_file)
        except OSError as e:
            logger.warning("[termux-llamacpp] Failed to remove PID file (%s): %s", pid_file, e)

    if stopped_count > 0:
        print(f"[termux-llama] Stopped {stopped_count} tracked server process(es).")
    else:
        print("[termux-llama] No active tracked server instances found.")


def cmd_find(args):
    """Search for GGUF models on Hugging Face."""
    crawler = HuggingFaceCrawler()
    print(f"[termux-llama] Searching Hugging Face for '{args.query}' (deep_crawl={args.deep})...")
    try:
        results = crawler.discover(
            query=args.query,
            limit=args.limit,
            deep_crawl=args.deep,
        )
        if not results:
            print("[termux-llama] No models found.")
            return

        print(f"\nFound {len(results)} GGUF models:\n")
        for r in results:
            stats_parts = []
            if r.likes:
                stats_parts.append(f"Likes: {r.likes}")
            if r.downloads:
                stats_parts.append(f"Downloads: {r.downloads:,}")
            stats_str = f" ({', '.join(stats_parts)})" if stats_parts else ""
            print(f" * {r.repo_id}{stats_str}")
            if getattr(r, "download_url", None):
                print(f"   URL: {r.download_url}")
            if r.description:
                print(f"   Desc: {r.description[:80]}...")
            print()
    except DependencyMissingError as e:
        print(f"\n[Warning] {e}")
        print("Falling back to standard REST API search...")
        results = crawler.discover(query=args.query, limit=args.limit, deep_crawl=False)
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
        size_mb = m.get("size_mb", (m.get("size_bytes", 0) / (1024 * 1024)))
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
        size_str = f"{info.size_mb:.1f} MB" if hasattr(info, "size_mb") and info.size_mb > 0 else "-"
        ram_str = f"{info.min_ram_mb} MB" if hasattr(info, "min_ram_mb") and info.min_ram_mb > 0 else "-"
        repo = getattr(info, "repo_id", "")
        print(f"{alias:<26} {size_str:<10} {ram_str:<10} {repo}")
    print("\nTo download, run: termux-llama download <alias>\n")


def cmd_presets(args):
    """List available hardware build presets."""
    print("\nHardware Build Presets for llama.cpp:\n")
    print(f"{'Preset':<25} {'Opt Flags':<35} {'Description'}")
    print("-" * 80)
    for name, p in BUILD_PRESETS.items():
        cflags = getattr(p, "cflags", p.get("cflags") if isinstance(p, dict) else "")
        desc = getattr(p, "description", p.get("description") if isinstance(p, dict) else "")
        print(f"{name:<25} {cflags:<35} {desc}")
    print()


def cmd_doctor(args):
    """Diagnose hardware and installation environment."""
    print_hardware_summary()


def main():
    parser = argparse.ArgumentParser(
        prog="termux-llama",
        description="Universal GGUF Runtime, Model Manager & OpenAI Server for Android Termux & ARM64",
    )
    parser.add_argument("--version", action="version", version=f"termux-llamacpp {__version__}")
    parser.add_argument("-d", "--daemon", action="store_true", help="Run in background daemon mode")
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
    p_serve.add_argument("model", nargs="?", default=None, help="Model filename, alias, or direct path (default: first cached model)")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    p_serve.add_argument("--ctx", type=int, default=2048, help="Context length in tokens")
    p_serve.add_argument("--threads", type=int, default=None, help="CPU threads")
    p_serve.add_argument("--device", default="auto", choices=["auto", "vulkan", "cpu", "gpu"], help="Compute device: auto (Vulkan priority with CPU fallback), vulkan/gpu (strict GPU fail-fast), cpu")
    p_serve.add_argument("-d", "--daemon", action="store_true", help="Run server in the background as a daemon")

    # run (direct one-shot inference)
    p_run = subparsers.add_parser("run", help="Run direct text generation with strict device routing")
    p_run.add_argument("model", nargs="?", default=None, help="Model filename, alias, or direct path (default: first cached model)")
    p_run.add_argument("prompt", nargs="?", default=None, help="Input text prompt (positional)")
    p_run.add_argument("-p", "--prompt", dest="prompt_flag", default=None, help="Input text prompt (flag)")
    p_run.add_argument("--device", default="auto", choices=["auto", "vulkan", "cpu", "gpu"], help="Compute device: auto (Vulkan priority with CPU fallback), vulkan/gpu (strict GPU fail-fast), cpu")
    p_run.add_argument("-n", "--max-tokens", type=int, default=256, help="Max tokens to generate")
    p_run.add_argument("-t", "--threads", type=int, default=None, help="CPU threads")
    p_run.add_argument("--temp", type=float, default=0.7, help="Sampling temperature")


    # stop
    subparsers.add_parser("stop", help="Stop all running termux-llama server instances")

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

    # ── AMEVA Component Protocol v1 ─────────────────────────────────────────
    try:
        from ameva_component.cli_support import build_protocol_subcommands
        build_protocol_subcommands(subparsers)
        _protocol_available = True
    except ImportError:
        _protocol_available = False
    # ────────────────────────────────────────────────────────────────────────

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "install": cmd_install,
        "download": cmd_download,
        "serve": cmd_serve,
        "run": cmd_run,
        "stop": cmd_stop,
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
    elif args.command in ("component", "model", "instance") and _protocol_available:
        # AMEVA Component Protocol v1 명령 처리
        from ameva_component.cli_support import dispatch_protocol
        from termux_llamacpp.control import LlamaCppControl
        control = LlamaCppControl()
        dispatch_protocol(args, control)
    elif args.command in ("component", "model", "instance"):
        print("[ERROR] ameva-component-sdk not installed. Run: pip install ameva-component-sdk", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

