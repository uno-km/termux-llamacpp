"""termux-llamacpp: Universal GGUF Runtime, Model Manager & OpenAI Server for Android Termux & ARM64."""

from termux_llamacpp.config import (
    RuntimeConfig,
    ServerConfig,
    ModelInfo,
    BuildPreset,
    GenerationMetrics,
    CURATED_MODELS,
    AVAILABLE_MODELS,
    BUILD_PRESETS,
    LLAMA_CPP_PINNED_COMMIT,
    PROTOCOL_VERSION,
)
from termux_llamacpp.engine import LlamaRuntime
from termux_llamacpp.downloader import ModelManager, download_model, list_models, resolve_model_path
from termux_llamacpp.crawler import HuggingFaceCrawler, discover_hf_models
from termux_llamacpp.hardware import detect_hardware, print_hardware_summary, HardwareProfile, resolve_device, is_termux, is_android, bind_hardware
from termux_llamacpp.server import ServerManager, ServerInstance, ProcessIdentityLock
from termux_llamacpp.security import (
    compute_sha256,
    verify_file_sha256,
    verify_binary_integrity,
    atomic_replace_verified,
    build_model_manifest_payload,
    save_signed_model_manifest,
    verify_binary_pre_execution,
    verify_model_pre_execution,
    TrustStore,
)
from termux_llamacpp.exceptions import (
    AmevaTermuxError,
    TermuxLlamaError,
    ModelNotFoundError,
    DependencyMissingError,
    RuntimeBuildError,
    ServerStartupError,
    SecurityVerificationError,
)


__version__ = "1.3.7"
__author__ = "uno-km"

__all__ = [
    "LlamaRuntime",
    "ModelManager",
    "ServerManager",
    "ServerInstance",
    "ProcessIdentityLock",
    "HuggingFaceCrawler",
    "discover_hf_models",
    "download_model",
    "detect_hardware",
    "is_termux",
    "is_android",
    "bind_hardware",
    "print_hardware_summary",
    "compute_sha256",
    "verify_file_sha256",
    "verify_binary_integrity",
    "atomic_replace_verified",
    "build_model_manifest_payload",
    "save_signed_model_manifest",
    "verify_binary_pre_execution",
    "verify_model_pre_execution",
    "TrustStore",
    "RuntimeConfig",
    "ServerConfig",
    "ModelInfo",
    "BuildPreset",
    "GenerationMetrics",
    "CURATED_MODELS",
    "AVAILABLE_MODELS",
    "BUILD_PRESETS",
    "LLAMA_CPP_PINNED_COMMIT",
    "PROTOCOL_VERSION",
    "HardwareProfile",
    "resolve_device",
    "list_models",
    "resolve_model_path",
    "AmevaTermuxError",
    "TermuxLlamaError",
    "ModelNotFoundError",
    "DependencyMissingError",
    "RuntimeBuildError",
    "ServerStartupError",
    "SecurityVerificationError",
]



# Standard Unified Engine & Factory
LlamaEngine = LlamaRuntime

def load(model: str = "default", device: str = "auto", **kwargs) -> LlamaEngine:
    """Standard Unified Engine Factory for termux-llamacpp."""
    config = RuntimeConfig(preset=kwargs.get("preset", "balanced"))
    return LlamaEngine(config=config)
