# Changelog

All notable changes to 	ermux-llamacpp will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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