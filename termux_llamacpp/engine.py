"""Core LlamaRuntime engine and native execution orchestrator."""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union, List, Dict, Any

logger = logging.getLogger("termux_llamacpp.engine")

from termux_llamacpp.config import (
    RuntimeConfig,
    DEFAULT_BIN_DIR,
    DEFAULT_MODELS_DIR,
    LLAMA_CPP_PINNED_COMMIT,
)
from termux_llamacpp.downloader import ModelManager
from termux_llamacpp.crawler import HuggingFaceCrawler
from termux_llamacpp.hardware import detect_hardware, HardwareProfile
from termux_llamacpp.exceptions import (
    RuntimeBuildError,
    TermuxLlamaError,
)


def ensure_system_dependencies() -> None:
    """Ensure ecosystem dependencies (python-cryptography, ameva-runtime) are provisioned."""
    # 1. Check cryptography
    try:
        import cryptography
    except ImportError:
        if shutil.which("pkg"):
            print("[termux-llamacpp] Auto-installing precompiled 'python-cryptography' via Termux pkg...")
            try:
                subprocess.run(["pkg", "install", "-y", "python-cryptography"], check=True)
            except Exception as e:
                print(f"[termux-llamacpp] Notice: Failed to auto-install python-cryptography via pkg: {e}")

    # 2. Check ameva-runtime
    try:
        from ameva_runtime import vulkan as avr
    except ImportError:
        if shutil.which("pip"):
            print("[termux-llamacpp] Auto-provisioning 'ameva-runtime' via pip...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "ameva-runtime>=2.0.0"], check=False)
            except Exception as e:
                print(f"[termux-llamacpp] Notice: Failed to auto-install ameva-runtime: {e}")


class LlamaRuntime:
    """Universal GGUF Runtime manager for Android Termux & ARM64."""

    def __init__(self, config: Optional[RuntimeConfig] = None):
        self.config = config or RuntimeConfig()
        self.bin_dir = Path(self.config.bin_dir)
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        self.models = ModelManager(self.config.models_dir)
        self.crawler = HuggingFaceCrawler()
        self.hw: HardwareProfile = detect_hardware()

    @classmethod
    def install(
        cls,
        preset: str = "android-arm64-baseline",
        force_rebuild: bool = False,
        bin_dir: Optional[Union[str, Path]] = None,
        models_dir: Optional[Union[str, Path]] = None,
    ) -> "LlamaRuntime":
        """
        Verify native toolchain and compile/install pinned-commit ARM64 llama.cpp binaries.

        Args:
            preset: Hardware build preset ('android-arm64-baseline', 'android-arm64-dotprod', 'android-arm64-native').
            force_rebuild: Recompile binaries even if cached binaries exist.
            bin_dir: Target binary destination directory.
            models_dir: Target models directory.

        Returns:
            LlamaRuntime: Initialized runtime ready for model execution.
        """
        ensure_system_dependencies()
        config = RuntimeConfig(
            preset=preset,
            bin_dir=Path(bin_dir) if bin_dir else DEFAULT_BIN_DIR,
            models_dir=Path(models_dir) if models_dir else DEFAULT_MODELS_DIR,
        )
        runtime = cls(config)
        runtime._ensure_binaries(force_rebuild=force_rebuild)
        return runtime

    def _ensure_binaries(self, force_rebuild: bool = False):
        """Check for llama-server and llama-cli binaries with pinned commit verification."""
        server_bin = self.get_binary_path("llama-server")
        cli_bin = self.get_binary_path("llama-cli")

        if server_bin and cli_bin and not force_rebuild:
            return

        print("================================================================================")
        print(f"  [termux-llamacpp] Compiling Native llama.cpp (Commit: {self.config.pinned_commit})")
        print(f"  Preset: {self.config.preset}")
        print("================================================================================")

        # Check package-bundled script path, then local repo script path
        script_path = Path(__file__).parent / "scripts" / "install.sh"
        if not script_path.is_file():
            script_path = Path(__file__).parent.parent / "scripts" / "install.sh"

        if script_path.is_file() and (self.hw.is_termux or self.hw.is_android or self.hw.is_arm64):
            env = os.environ.copy()
            env["TERMUX_LLAMA_PRESET"] = self.config.preset
            env["LLAMA_CPP_COMMIT"] = self.config.pinned_commit
            env["TERMUX_LLAMA_HOME"] = str(self.bin_dir.parent if self.bin_dir.name == "bin" else self.bin_dir)
            cmd = ["bash", str(script_path)]
            if force_rebuild:
                cmd.append("--from-source")
            try:
                subprocess.run(cmd, env=env, check=True)
            except Exception as e:
                raise RuntimeBuildError(
                    f"Runtime installation failed for preset '{self.config.preset}': {e}\n"
                    f"Please check installation logs or run with --from-source."
                ) from e

        # Ensure executable permissions
        for b in self.bin_dir.glob("llama-*"):
            try:
                b.chmod(0o755)
            except OSError as _chmod_err:
                import logging
                logging.getLogger(__name__).warning(
                    "llamacpp: chmod 0o755 failed for %s: %s (non-fatal, file may still be executable)",
                    b, _chmod_err,
                )

    def get_binary_path(self, binary_name: str) -> Optional[Path]:
        """Find the absolute path of a llama.cpp binary across standard Termux locations."""
        import re
        ext = ".exe" if sys.platform == "win32" else ""
        candidates = [
            Path.home() / ".termux-llama" / "current" / "bin" / binary_name,
            self.bin_dir / f"{binary_name}{ext}",
            self.bin_dir / binary_name,
            self.bin_dir.parent / "current" / "bin" / binary_name,
            Path.home() / ".termux-llama" / "bin" / binary_name,
            Path.home() / ".termux-llamacpp" / "current" / "bin" / binary_name,
            Path.home() / ".termux-llamacpp" / "bin" / binary_name,
        ]

        for cand in candidates:
            if cand.is_file():
                return cand.resolve()

        # Search in versions directory
        for base in [Path.home() / ".termux-llama", Path.home() / ".termux-llamacpp"]:
            versions_dir = base / "versions"
            if versions_dir.is_dir():
                for v in versions_dir.iterdir():
                    cand = v / "bin" / binary_name
                    if cand.is_file():
                        return cand.resolve()

        sys_path = shutil.which(binary_name)
        if sys_path:
            p = Path(sys_path).resolve()
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                for line in content.splitlines():
                    if "exec " in line and binary_name in line:
                        match = re.search(r'exec\s+"?([^"\s]+)"?', line)
                        if match:
                            target_str = match.group(1).replace("$ROOT", str(Path.home() / ".termux-llamacpp"))
                            real_p = Path(os.path.expanduser(os.path.expandvars(target_str)))
                            if real_p.is_file():
                                return real_p.resolve()
            except (OSError, ValueError) as _parse_err:
                import logging
                logging.getLogger(__name__).debug(
                    "llamacpp: wrapper script parse fallback for '%s': %s (using shutil.which result)",
                    binary_name, _parse_err,
                )
            return p

        return None

    def _prepare_env(self, device: str = "auto") -> Dict[str, str]:
        """
        Configure subprocess environment safely using the official ameva-runtime HAL.

        Args:
            device: 'auto' (Vulkan priority with CPU fallback), 'vulkan' (strict GPU fail-fast), 'cpu' (pure NEON).

        Returns:
            Dict[str, str]: Prepared environment dictionary with verified LD_LIBRARY_PATH.
        """
        env = os.environ.copy()
        dev_mode = str(device or "auto").strip().lower()

        if dev_mode == "cpu" or sys.platform == "win32":
            return env

        try:
            from ameva_runtime import vulkan as avr

            # 1. Acquire Vulkan HAL context
            if hasattr(avr, "create_context"):
                ctx = avr.create_context(dev_mode)
            elif hasattr(avr, "get_or_create_context"):
                ctx = avr.get_or_create_context(dev_mode)
            else:
                ctx = avr.VulkanContext(dev_mode)

            # 2. Verify GPU status
            if ctx.backend_type == "vulkan" or getattr(ctx, "is_gpu", False):
                # Dynamically resolve driver path from context or Android system
                loader_path = getattr(ctx, "loader_path", "")
                vk_dir = str(Path(loader_path).parent) if loader_path and os.path.exists(loader_path) else "/system/lib64"
                if os.path.exists(vk_dir):
                    existing_lp = env.get("LD_LIBRARY_PATH", "")
                    if vk_dir not in existing_lp:
                        env["LD_LIBRARY_PATH"] = f"{vk_dir}:{existing_lp}".rstrip(":")
            elif dev_mode in ("vulkan", "gpu"):
                raise TermuxLlamaError(
                    f"Explicit Vulkan backend requested ('--device {device}'), but ameva-runtime "
                    f"initialized with non-GPU backend ('{ctx.backend_type}': {ctx.device_name})."
                )
        except ImportError:
            if dev_mode in ("vulkan", "gpu"):
                raise TermuxLlamaError(
                    f"Explicit Vulkan acceleration requested ('--device {device}'), but 'ameva-runtime' "
                    f"is not installed. Please run 'pip install ameva-runtime' or 'npm install @ameva/runtime'."
                )
            # Auto-mode graceful fallback to system Vulkan driver if present
            if os.path.exists("/system/lib64/libvulkan.so"):
                existing_lp = env.get("LD_LIBRARY_PATH", "")
                if "/system/lib64" not in existing_lp:
                    env["LD_LIBRARY_PATH"] = f"/system/lib64:{existing_lp}".rstrip(":")
        except Exception as e:
            if dev_mode in ("vulkan", "gpu"):
                if isinstance(e, TermuxLlamaError):
                    raise
                raise TermuxLlamaError(f"AMEVA Vulkan Runtime initialization failed: {e}") from e

        return env

    def serve(
        self,
        model: Optional[Union[str, Path]] = None,
        host: str = "127.0.0.1",
        port: int = 8080,
        ctx_size: int = 2048,
        threads: Optional[int] = None,
        n_gpu_layers: int = 0,
        device: str = "auto",
        daemon: bool = False,
    ):
        """
        Start an OpenAI and termux-aichain compliant server instance using the resolved model.

        Raises:
            ModelNotFoundError: If the model file is not found.
        """
        from termux_llamacpp.server import ServerManager

        resolved_model_path = self.models.get(model)
        server_mgr = ServerManager(runtime=self)
        dev_mode = "vulkan" if str(device).lower() == "gpu" else device
        return server_mgr.serve(
            model_path=resolved_model_path,
            host=host,
            port=port,
            ctx_size=ctx_size,
            threads=threads or self.hw.recommended_threads,
            n_gpu_layers=n_gpu_layers if dev_mode != "cpu" else 0,
            device=dev_mode,
            daemon=daemon,
        )

    def generate(
        self,
        model: Optional[Union[str, Path]] = None,
        prompt: str = "",
        mmproj: Optional[Union[str, Path]] = None,
        image: Optional[Union[str, Path]] = None,
        max_tokens: int = 256,
        temperature: float = 0.7,
        threads: Optional[int] = None,
        device: str = "auto",
        n_gpu_layers: Optional[int] = None,
    ) -> str:
        """
        Execute one-shot CLI text or multimodal generation with strict device routing (auto, vulkan, cpu, gpu).

        Args:
            model: Model name, alias, path, or None for auto-resolved default model.
            prompt: Text prompt input.
            mmproj: Multimodal vision projector file path (e.g. mmproj-*.gguf).
            image: Path to input image file for visual reasoning.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            threads: Worker threads count.
            device: 'auto' (Vulkan priority with CPU fallback), 'vulkan' / 'gpu' (strict GPU fail-fast), 'cpu' (pure NEON).
            n_gpu_layers: Specific number of layers to offload to GPU.

        Raises:
            TermuxLlamaError: On inference failure or when strict Vulkan mode fails without fallback.
        """
        # If model is passed as prompt (single positional string) or model is omitted
        if model is not None and prompt == "" and isinstance(model, str) and not (model.endswith(".gguf") or model in CURATED_MODELS):
            # Model argument was used as prompt
            prompt = model
            model = None

        resolved_model_path = self.models.get(model)

        cli_bin = self.get_binary_path("llama-cli")
        if not cli_bin:
            raise RuntimeBuildError(
                f"Binary 'llama-cli' not found in '{self.bin_dir}' or PATH.\n"
                f"Please install or compile the runtime first by running:\n"
                f"  termux-llama install\n"
                f"Or in Python:\n"
                f"  from termux_llamacpp import LlamaRuntime; LlamaRuntime.install()"
            )

        t_count = str(threads or self.hw.recommended_threads)
        ngl_target = 99 if n_gpu_layers is None else n_gpu_layers

        def _run_cmd(target_device: str, gpu_layers: int) -> subprocess.CompletedProcess:
            env = self._prepare_env(device=target_device)
            cmd = [
                str(cli_bin),
                "-m", str(resolved_model_path),
                "-p", prompt,
                "-n", str(max_tokens),
                "--temp", str(temperature),
                "-t", t_count,
                "--single-turn",
                "--simple-io",
                "--no-display-prompt",
            ]
            if mmproj:
                cmd.extend(["--mmproj", str(mmproj)])
            if image:
                cmd.extend(["--image", str(image)])

            if gpu_layers > 0 and target_device != "cpu":
                cmd.extend(["-ngl", str(gpu_layers)])
            else:
                cmd.extend(["-ngl", "0"])

            return subprocess.run(cmd, capture_output=True, text=True, env=env)

        dev_mode = str(device or "auto").lower()

        # 1. Strict GPU/Vulkan Mode (Fail-Fast: no fallback, return clear error on failure)
        if dev_mode in ("vulkan", "gpu"):
            res = _run_cmd("vulkan", ngl_target)
            err_lower = (res.stderr or "").lower()
            if "no usable gpu found" in err_lower or "no devices found" in err_lower or res.returncode != 0:
                raise TermuxLlamaError(
                    f"[ERROR] Vulkan GPU device initialization failed or unavailable on this device.\n"
                    f"Fallback suppressed in strict '--device {dev_mode}' mode.\n"
                    f"Please run in CPU mode using '--device cpu' or auto mode with '--device auto'.\n"
                    f"Details: {res.stderr.strip()}"
                )
            return res.stdout.strip()

        # 2. Auto Mode (Check Vulkan capability first to prevent double-load overhead)
        elif dev_mode == "auto":
            use_vulkan = False
            try:
                from ameva_runtime import vulkan as avr
                if hasattr(avr, "create_context"):
                    use_vulkan = avr.create_context("auto").backend_type == "vulkan"
                elif hasattr(avr, "get_or_create_context"):
                    use_vulkan = avr.get_or_create_context("auto").backend_type == "vulkan"
                else:
                    use_vulkan = avr.VulkanContext("auto").backend_type == "vulkan"
                logger.debug("Auto device probe: use_vulkan=%s", use_vulkan)
            except Exception as e:
                logger.debug("Vulkan runtime probe unavailable (%s); using CPU mode.", e)

            if use_vulkan:
                res = _run_cmd("vulkan", ngl_target)
                err_lower = (res.stderr or "").lower()
                if "no usable gpu found" in err_lower or "no devices found" in err_lower or res.returncode != 0:
                    logger.warning("[termux-llamacpp] Vulkan GPU execution failed; falling back to CPU NEON engine.")
                    sys.stderr.write("[WARN] Vulkan GPU execution failed. Falling back to ARM64 CPU NEON engine...\n")
                    sys.stderr.flush()
                    cpu_res = _run_cmd("cpu", 0)
                    if cpu_res.returncode != 0:
                        raise TermuxLlamaError(f"CPU NEON inference fallback failed: {cpu_res.stderr}")
                    return cpu_res.stdout.strip()
                return res.stdout.strip()
            else:
                cpu_res = _run_cmd("cpu", 0)
                if cpu_res.returncode != 0:
                    raise TermuxLlamaError(f"CPU NEON inference failed: {cpu_res.stderr}")
                return cpu_res.stdout.strip()

        # 3. CPU Mode (Direct ARM64 NEON execution)
        elif dev_mode == "cpu":
            res = _run_cmd("cpu", 0)
            if res.returncode != 0:
                raise TermuxLlamaError(f"CPU NEON inference failed: {res.stderr}")
            return res.stdout.strip()

        else:
            raise ValueError(f"Unsupported device '{device}'. Must be one of ['auto', 'gpu', 'vulkan', 'cpu'].")
