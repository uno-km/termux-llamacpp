"""Configuration data classes, hardware presets, SSOT pinned commits, and dynamic registry loader."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List


# SSOT Native Engine Pinned Source Definition
LLAMA_CPP_UPSTREAM = "https://github.com/ggerganov/llama.cpp.git"
LLAMA_CPP_RELEASE_LABEL = "release-5e6a37c"
LLAMA_CPP_PINNED_COMMIT = "5e6a37cb115dc1074e274ac004373f5661909695"
PROTOCOL_VERSION = "1.0"

# Default Network Ports for Supervisor & Native Engines
DEFAULT_PUBLIC_PORT = 8080
DEFAULT_NATIVE_PORT = 18080

# Base filesystem directories
DEFAULT_BASE_DIR = Path(os.environ.get("TERMUX_LLAMA_HOME", Path.home() / ".termux-llama"))
DEFAULT_MODELS_DIR = Path(os.environ.get("TERMUX_LLAMA_MODELS_DIR", DEFAULT_BASE_DIR / "models"))
DEFAULT_BIN_DIR = Path(os.environ.get("TERMUX_LLAMA_BIN_DIR", DEFAULT_BASE_DIR / "bin"))
DEFAULT_RUN_DIR = Path(os.environ.get("TERMUX_LLAMA_RUN_DIR", DEFAULT_BASE_DIR / "run"))
DEFAULT_LOG_DIR = Path(os.environ.get("TERMUX_LLAMA_LOG_DIR", DEFAULT_BASE_DIR / "logs"))
TRUST_DIR = Path(__file__).parent / "trust"


@dataclass
class BuildPreset:
    """Strict compiler and optimization settings for a hardware build preset."""
    name: str
    march: str
    cflags: str
    cxxflags: str
    openmp: bool
    vulkan: bool
    description: str
    requires: List[str] = field(default_factory=list)


# Strict Hardware Build Presets
BUILD_PRESETS: Dict[str, BuildPreset] = {
    "android-arm64-baseline": BuildPreset(
        name="android-arm64-baseline",
        march="armv8-a",
        cflags="-O3 -march=armv8-a",
        cxxflags="-O3 -march=armv8-a",
        openmp=False,
        vulkan=False,
        description="Safe universal baseline for all ARM64 Android devices (guaranteed SIGILL-free).",
        requires=[],
    ),
    "android-arm64-dotprod": BuildPreset(
        name="android-arm64-dotprod",
        march="armv8.2-a+fp16+dotprod",
        cflags="-O3 -march=armv8.2-a+fp16+dotprod",
        cxxflags="-O3 -march=armv8.2-a+fp16+dotprod",
        openmp=False,
        vulkan=False,
        description="SIMD-accelerated preset with DotProd and FP16 (requires runtime verification).",
        requires=["dotprod", "fp16"],
    ),
    "android-arm64-native": BuildPreset(
        name="android-arm64-native",
        march="native",
        cflags="-O3 -mcpu=native",
        cxxflags="-O3 -mcpu=native",
        openmp=False,
        vulkan=False,
        description="Direct native optimization compiled locally on the target device.",
        requires=[],
    ),
    "host-native": BuildPreset(
        name="host-native",
        march="native",
        cflags="-O3 -march=native",
        cxxflags="-O3 -march=native",
        openmp=False,
        vulkan=False,
        description="Generic host compilation for development and unit testing.",
        requires=[],
    ),
}


@dataclass
class ModelInfo:
    """Metadata for a registered GGUF model."""
    model_id: str
    repo_id: str
    artifact_filename: str
    repo_revision: str = "main"
    sha256: Optional[str] = None
    size_mb: float = 0.0
    quant_type: str = "Q4_K_M"
    architecture: str = "llama"
    license_id: str = "Apache-2.0"
    license_url: str = ""
    requires_acceptance: bool = False
    description: str = ""
    min_ram_mb: int = 2048

    @property
    def filename(self) -> str:
        return self.artifact_filename

    @property
    def name(self) -> str:
        return self.model_id



def _load_registry_models() -> Dict[str, ModelInfo]:
    """Load model definitions from registry/models.json."""
    registry_path = Path(__file__).parent / "registry" / "models.json"
    if not registry_path.is_file():
        registry_path = Path(__file__).parent.parent / "registry" / "models.json"

    models_map: Dict[str, ModelInfo] = {}
    if registry_path.is_file():
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for name, item in data.get("models", {}).items():
                    models_map[name] = ModelInfo(
                        model_id=item.get("model_id", name),
                        repo_id=item.get("repo_id", ""),
                        artifact_filename=item.get("artifact_filename", f"{name}.gguf"),
                        repo_revision=item.get("repo_revision", "main"),
                        sha256=item.get("artifact_sha256"),
                        size_mb=item.get("size_mb", 0.0),
                        quant_type=item.get("quant_type", "Q4_K_M"),
                        architecture=item.get("architecture", "llama"),
                        license_id=item.get("license_id", "Apache-2.0"),
                        license_url=item.get("license_url", ""),
                        requires_acceptance=item.get("requires_acceptance", False),
                        description=item.get("description", ""),
                        min_ram_mb=item.get("min_ram_mb", 2048),
                    )
        except Exception:
            pass

    return models_map


CURATED_MODELS: Dict[str, ModelInfo] = _load_registry_models()
AVAILABLE_MODELS = list(CURATED_MODELS.keys())


@dataclass
class RuntimeConfig:
    """Runtime configuration for llama.cpp native toolchain."""
    preset: str = "android-arm64-baseline"
    bin_dir: Path = DEFAULT_BIN_DIR
    models_dir: Path = DEFAULT_MODELS_DIR
    run_dir: Path = DEFAULT_RUN_DIR
    log_dir: Path = DEFAULT_LOG_DIR
    pinned_commit: str = LLAMA_CPP_PINNED_COMMIT
    release_label: str = LLAMA_CPP_RELEASE_LABEL
    upstream_url: str = LLAMA_CPP_UPSTREAM


@dataclass
class ServerConfig:
    """Configuration for reverse proxy supervisor and llama-server backend."""
    public_host: str = "127.0.0.1"
    public_port: int = DEFAULT_PUBLIC_PORT
    native_host: str = "127.0.0.1"
    native_port: int = DEFAULT_NATIVE_PORT
    model_path: str = ""
    ctx_size: int = 2048
    n_predict: int = 512
    threads: int = 4
    n_gpu_layers: int = 0
    batch_size: int = 512
    ubatch_size: int = 512
    timeout_seconds: int = 30
    log_file: Optional[str] = None


@dataclass
class GenerationMetrics:
    """Inference execution metrics."""
    tokens_generated: int = 0
    prompt_tokens: int = 0
    total_time_ms: float = 0.0
    tokens_per_second: float = 0.0
    ram_usage_mb: float = 0.0
