## [1.3.8] - 2026-09-18

### Added
- **Official Multimodal VLM Engine Integration**: Added `LlamaRuntime.generate_vlm()` and module-level `generate_vlm()` with `VLMResponse` dataclass.
- **Strict Device Pass-through Governance**: 1:1 hardware pass-through routing (`cpu` forced pure NEON, `gpu`/`vulkan` strict Fail-Fast without `ameva-runtime`, `auto` fallback).
- **Zero Interference Execution**: Stripped conflicting `--chat-template` arguments to preserve GGUF model-native multimodal markers.

## [1.3.7] - 2026-09-18

### Fixed
- Fixed interactive REPL hang by enforcing single-turn non-interactive completion.

## [1.3.6] - 2026-09-18

### Added
- Added `-c, --ctx, --ctx-size` argument to `termux-llama run` CLI for explicit context window tuning.
- Added `ctx_size: Optional[int] = 2048` parameter to `LlamaRuntime.generate()` with support for native model context pass-through (`ctx_size=0`).
- Exposed `LlamaRuntime.prepare_env(device)` publicly for official execution environment export to sibling packages.

### Changed & Fixed
- Removed deprecated `--single-turn` flag from internal CLI execution in `engine.py`.
- Synchronized package manifests across PyPI and npm to `1.3.6`.

## [1.3.5] - 2026-09-18

### Changed & Hardened
- **Zero-Hardcoding Dynamic Latest-First Provisioning Architecture**:
  - Replaced hardcoded fallback versions with dynamic GitHub API releases query in `scripts/install.sh` and `termux_llamacpp/scripts/install.sh`.
  - Harmonized dual install scripts with 100% parity, eliminating previous `1.3.3` vs `1.3.4` drift.
  - Prioritized invariant `releases/latest/download/termux-llamacpp-${TARGET}.tar.gz` download endpoint.
  - Synchronized versions across `package.json`, `pyproject.toml`, and `termux_llamacpp/__init__.py` to `1.3.5`.

## [1.3.3] - 2026-09-18

### Changed & Enhanced
- **Installation Environment Lightweighting**:
  - Completely purged heavy Vulkan/GPU build dependencies, `--gpu / --with-gpu` flags, and intrusive external runtime auto-provisioning (`pip install ameva-runtime`, `npm install @ameva/runtime`) from the base package installer.
  - Enforced strict 2-tier architectural decoupling: `termux-llamacpp` now acts as an ultra-compact, independent pure CPU baseline engine (<13MB), delegating GPU hardware acceleration strictly to the upper `@ameva/runtime` orchestration layer.
- **Pure CPU Mode Optimization**:
  - Streamlined build presets exclusively to verified pure CPU targets: `android-arm64-baseline` (universal ARMv8-A SIGILL-free baseline), `android-arm64-dotprod` (ARMv8.2-A FP16 + DotProd SIMD vector acceleration), and `android-arm64-native` (on-device Clang autotuning).
  - Eliminated redundant `android-arm64-vulkan` and `host-native` presets.
- **Canonical Release Asset Standardization**:
  - Unified binary distribution under single canonical asset `termux-llamacpp-android-arm64.tar.gz`, eliminating version-pinned filename fragmentation and duplicate uploads.
- **Multi-Directory Model Discovery**:
  - Upgraded `termux-llama list` to automatically discover and deduplicate GGUF models across both XDG standard paths (`~/.cache/termux-llamacpp/models/`) and ecosystem legacy paths (`~/.termux-llama/models/`).

---

## [1.3.2] - 2026-09-07

### Added
- **Dynamic Candidate Resolution & Automatic Source Build Fallback**: Replaced hardcoded legacy version string in `scripts/install.sh` with dynamic candidates (`v{VERSION}`, `releases/latest/download`, `v1.0.0b2` fallback). Added automated fallback to native C++ compilation (`--from-source`) if prebuilt binary download fails, eliminating 404 aborts.
- **Fail-Safe Executable Wrappers**: Unified wrappers in `$PREFIX/bin/` now verify physical existence of target binaries before invocation, preventing misleading `No such file or directory` shell errors.
- **Synchronized Installer SSOT**: Reconciled split-brain drift between repository root `scripts/install.sh` and packaged `termux_llamacpp/scripts/install.sh`.

---

## [1.3.1] - 2026-09-07

### Added
- Complete 12-tier enterprise English documentation overhaul for PyPI and GitHub/NPM.
- Detailed empirical mobile hardware benchmarks (Snapdragon 8 Elite / Adreno 830, Snapdragon 865, Exynos 1380 / Mali-G68 MP5).
- Full GPU interconnect architecture documentation with SPIR-V compute shader details.
- Comprehensive CPU vs. GPU thermal dissipation, latency, and power efficiency analysis.
- 3-stage 24/7 unattended background execution guide (Termux wake-lock, battery optimization, ADB phantom process killer).
- Expanded technical SEO metadata keywords (50 keywords connecting to AMEVA ecosystem).
- Archived comprehensive engineering breakthroughs and legacy reports to ameva-foundation.

---

# Changelog

All notable changes to `termux-llamacpp` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.7] - 2026-09-18

### Fixed
- Added `--single-turn` to `LlamaRuntime.generate()` command line invocation to ensure clean process termination.

## [1.3.6] - 2026-09-18

### Added
- Integrated unified `LlamaCppAdapter` directly from `ameva_runtime.adapters` SSOT.
- Enforced strict E002 Fail-Fast when GPU acceleration is requested but Vulkan/CL environment is missing.
- Sanitized legacy `--single-turn` CLI flag in favor of canonical options.

---

## [1.2.4] - 2026-09-05

### Changed
- Untracked build artifacts, sanitized environment diagnostics, and updated ecosystem bindings.
- Fully synchronized install scripts to ameva-runtime (pip) and @ameva/runtime (npm).

---

## [1.2.3] - 2026-09-05

### Changed
- Migrated hardware acceleration dependency to unified `ameva-runtime>=2.0.0` and `@ameva/runtime>=2.0.0`.
- Enforced Fail-Fast error propagation on explicit Vulkan acceleration requests (`--device vulkan`).

---

## [1.2.1] - 2026-09-02

### Added
- **Reverse Proxy Supervisor**: Production reverse proxy with OpenAI /v1/chat/completions compatibility.
- **Trust Store**: Ed25519 cryptographic binary verification for ARM64 server builds.
- **Standard 3-View READMEs**: Complete PyPI and NPM documentation parity.

### Fixed
- **CLI Exception Transparency**: Differentiated HTTP health probe timeout and connection errors in warmup loop.
- **Lock File Cleanup**: Added structured warning logs on server shutdown lock file removal failures.
- **PIDLockManager Refactor**: Removed dead legacy alias and unified under ProcessIdentityLock.
- **Model Verification**: Added strict expected_model_id validation in 
ative_is_ready().

### Cleaned
- Purged tracked uild/ directory and orphan .pyc cache files.