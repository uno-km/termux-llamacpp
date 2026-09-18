# Release Notes - termux-llamacpp v1.3.6

**Release Tag**: `v1.3.6`  
**Distribution Channels**: PyPI (`termux-llamacpp`), NPM (`termux-llamacpp`), GitHub Releases  
**Target Platform**: Android Termux (ARM64 / aarch64 Bionic)  
**License**: Apache-2.0  

---

## Highlights & Key Architectural Changes

### 1. Robust Context Window Control & Universal 2048 Baseline
- **Flexible Context Scaling**: Added `ctx_size: Optional[int] = 2048` to `LlamaRuntime.generate()`, providing safe 2048 mobile defaults while allowing explicit override (`-c 4096`, `-c 8192`) or native model context pass-through (`ctx_size=0`).
- **CLI Context Control**: Added `-c, --ctx` flag to `termux-llama run` subcommand, allowing users to tune context window size on single-turn inference without daemon configuration.

### 2. Sibling Package Interoperability & Canonical Environment Export
- **Public Environment Provider**: Exposed `LlamaRuntime.prepare_env(device)` publicly, enabling sibling frameworks (`termux-vision`, `ameva-runtime`) to inherit validated Android Bionic library search paths and Vulkan ICD configurations seamlessly.
- **Legacy Flag Modernization**: Purged deprecated `--single-turn` CLI flag from `generate()` invocation pipeline to ensure 100% forward compatibility with modern upstream llama.cpp releases.

---

## Detailed Changelog

### Added
- `-c, --ctx, --ctx-size` argument to `termux-llama run` CLI subcommand.
- `ctx_size: Optional[int] = 2048` parameter to `LlamaRuntime.generate()`.
- Public `prepare_env(device)` method on `LlamaRuntime`.

### Changed
- Removed obsolete `--single-turn` flag from internal CLI execution in `engine.py`.
- Package manifests synchronized across PyPI and npm to `1.3.6`.
- `CHANGELOG.md` updated for `v1.3.6`.
