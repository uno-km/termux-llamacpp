# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-09-01

### Added
- **Unified AMEVA Vulkan HAL v1.1.0 Integration**: Added deep integration with meva-vulkan-runtime>=1.1.0 providing certified 12-stage hardware diagnostic checks.
- **Strict 3-Tier Execution Mode**:
  - --device vulkan: Strict GPU compute with Fail-Fast protection (no silent CPU fallback).
  - --device auto: Intelligent hardware discovery with transparent ARM64 NEON fallback.
  - --device cpu: Zero-overhead direct CPU NEON forward pass bypassing Vulkan loader.
- **Dynamic Octa-Core Thread Tuning**: Automatic detection of ARM big.LITTLE architectures (e.g. Exynos 1380, Snapdragon) injecting -t 4 for optimal big-core throughput.
- **Dual Package Distribution**: Synchronized distribution across Python PyPI (	ermux-llamacpp) and Node.js npm (	ermux-llamacpp).
- **Real-Device Galaxy A35 Validation**: End-to-end multi-modal inference and OpenAI-compatible REST server verification on Samsung Galaxy A35 (Android 14, Bionic ICD /system/lib64/libvulkan.so).

### Fixed
- **Supply-Chain Receipt Gatekeeper**: Added verified build receipt support (llama-server.build-receipt.json) for local and custom native binaries.
- **Process Supervisor Resilience**: Guaranteed zero-zombie process termination with tracked PID ledger.

---

## [1.1.0] - 2026-08-30

### Added
- Supply-chain security verification with Ed25519 signatures and SHA-256 binary manifests.
- Multi-channel HuggingFace GGUF crawler and downloader.
- Background OpenAI server daemon mode (	ermux-llama serve -d).

---

## [1.0.0] - 2026-08-15

### Added
- Initial release with prebuilt ARM64 llama.cpp binaries for Android Termux.
