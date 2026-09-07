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

All notable changes to 	ermux-llamacpp will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.3.0] - 2026-09-07

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