"""Core LlamaRuntime engine and native execution orchestrator."""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union, List, Dict, Any

from termux_llamacpp.config import (
    RuntimeConfig,
    ServerConfig,
    GenerationMetrics,
    DEFAULT_BIN_DIR,
    DEFAULT_MODELS_DIR,
    BUILD_PRESETS,
    LLAMA_CPP_PINNED_COMMIT,
)
from termux_llamacpp.downloader import ModelManager
from termux_llamacpp.crawler import HuggingFaceCrawler
from termux_llamacpp.hardware import detect_hardware, HardwareProfile
from termux_llamacpp.exceptions import (
    RuntimeBuildError,
    ModelNotFoundError,
    TermuxLlamaError,
)


def ensure_system_dependencies() -> None:
    """Ensure optional Termux system packages (like python-cryptography) are present without triggering Rust builds."""
    try:
        import cryptography
        return
    except ImportError:
        pass

    if shutil.which("pkg"):
        print("[termux-llamacpp] Auto-installing precompiled 'python-cryptography' via Termux pkg...")
        try:
            subprocess.run(["pkg", "install", "-y", "python-cryptography"], check=True)
            print("[termux-llamacpp] 'python-cryptography' installed successfully.")
        except Exception as e:
            print(f"[termux-llamacpp] Notice: Failed to auto-install python-cryptography via pkg: {e}")


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
            except Exception:
                pass

    def get_binary_path(self, binary_name: str) -> Optional[Path]:
        """Find the absolute path of a llama.cpp binary across standard Termux locations."""
        import re
        ext = ".exe" if sys.platform == "win32" else ""
        candidates = [
            self.bin_dir / f"{binary_name}{ext}",
            self.bin_dir / binary_name,
            self.bin_dir.parent / "current" / "bin" / binary_name,
            Path.home() / ".termux-llama" / "current" / "bin" / binary_name,
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
            except Exception:
                pass
            return p

        return None

    def serve(
        self,
        model: Union[str, Path],
        host: str = "127.0.0.1",
        port: int = 8080,
        ctx_size: int = 2048,
        threads: Optional[int] = None,
        n_gpu_layers: int = 0,
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
        return server_mgr.serve(
            model_path=resolved_model_path,
            host=host,
            port=port,
            ctx_size=ctx_size,
            threads=threads or self.hw.recommended_threads,
            n_gpu_layers=n_gpu_layers,
            daemon=daemon,
        )

    def generate(
        self,
        model: Union[str, Path],
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        threads: Optional[int] = None,
    ) -> str:
        """
        Execute one-shot CLI text generation with the resolved model.

        Raises:
            ModelNotFoundError: If the model file is not found.
        """
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

        cmd = [
            str(cli_bin),
            "-m", str(resolved_model_path),
            "-p", prompt,
            "-n", str(max_tokens),
            "--temp", str(temperature),
            "-t", str(threads or self.hw.recommended_threads),
            "--no-display-prompt",
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return res.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise TermuxLlamaError(f"llama-cli inference failed: {e.stderr}") from e
