# Release Notes - termux-llamacpp v1.3.12

**Release Tag**: `v1.3.12`  
**Distribution Channels**: PyPI (`termux-llamacpp`), NPM (`termux-llamacpp`), GitHub Releases  
**Target Platform**: Android Termux (ARM64 / aarch64 Bionic)  
**License**: Apache-2.0  

---

## Highlights & Key Architectural Changes

### 1. Dynamic Linker Bionic Isolation (`engine.py`)
- **Purge Regressive `$PREFIX/lib` Injection**: Completely removed `$PREFIX/lib` from `LD_LIBRARY_PATH` during ameva-runtime fallback execution, preventing Android 15/16 Bionic dynamic linker namespace pollution and `libunwindstack.so` (`Xzs_Construct`) symbol collision crashes.
- **Embedded `DT_RUNPATH` Priority**: Relies exclusively on the binary's internal `$ORIGIN` and `$PREFIX/lib` ELF dynamic attributes, ensuring strictly isolated runtime execution.

### 2. ChatML Auto-Templating & Token Attractor Mitigation
- **Repetition Loop Resolution**: Fixed token degeneration loops in Qwen and Llama-3 series by standardizing `<|im_start|>` prompt encapsulation and automatic `-r "<|im_end|>"` reverse stop token injection.
- **Stop Token Sanitization**: Guarantees deterministic end-of-sequence termination across single-turn and multi-turn generation.

### 3. Cross-SoC Mobile Inference Stability
- **Qualcomm Adreno Defense**: Retained verified `-fa 0` defense on legacy Adreno 600 series while maintaining high-performance Flash Attention on Adreno 830 (Snapdragon 8 Elite) and ARM Mali GPUs.
- **CPU Isolation Mode**: Guarantees zero Vulkan ICD loading when `--device cpu` is selected.

---

## Detailed Changelog

### Fixed & Hardened
- `termux_llamacpp/engine.py`: Purged regressive `$PREFIX/lib` injection from fallback runtime environment; enhanced ChatML prompt formatting.
- `termux_llamacpp/__init__.py`: Version bumped to `1.3.12`.
- `pyproject.toml` & `package.json`: Version synchronized to `1.3.12`.
- `doc.config.yaml`: Documentation schema and version bumped to `v1.3.12`.
