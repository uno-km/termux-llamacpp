# Release Notes - termux-llamacpp v1.3.8

**Release Tag**: `v1.3.8`  
**Distribution Channels**: PyPI (`termux-llamacpp`), NPM (`termux-llamacpp`), GitHub Releases  
**Target Platform**: Android Termux (ARM64 / aarch64 Bionic)  
**License**: Apache-2.0  

---

## Highlights & Key Architectural Changes

### 1. Official Multimodal VLM Engine Integration
- **Direct VLM Execution Pipeline**: Introduced `LlamaRuntime.generate_vlm()` and top-level `generate_vlm()` with structured `VLMResponse` dataclass.
- **Strict Device Pass-through Governance**:
  - `cpu`: Forces pure ARM64 CPU NEON execution with `-ngl 0` and zero GPU probing.
  - `gpu` / `vulkan`: Strict validation against `ameva-runtime` HAL; halts immediately under Zero-Silent-Fallback policy if prerequisites are absent.
  - `auto`: Dynamically selects Vulkan when `ameva-runtime` is present, or CPU NEON otherwise.
- **Interference-Free Prompting**: Stripped conflicting `--chat-template` arguments to preserve GGUF model-native multimodal markers.

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
