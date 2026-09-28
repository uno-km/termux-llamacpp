# Release Notes - termux-llamacpp v1.3.11

**Release Tag**: `v1.3.11`  
**Distribution Channels**: PyPI (`termux-llamacpp`), NPM (`termux-llamacpp`), GitHub Releases  
**Target Platform**: Android Termux (ARM64 / aarch64 Bionic)  
**License**: Apache-2.0  

---

## Highlights & Key Architectural Changes

### 1. Dynamic 5-Stage Network Resume & Exponential Backoff (`downloader.py`)
- **Resilient Model Downloading**: Implemented dynamic retry mechanism (`max_retries=5`, exponential backoff) with HTTP Range 206 / 416 self-healing for interrupted GGUF downloads.
- **Compression Encoding Safety**: Added transfer-encoding inspection (`identity` vs `gzip/deflate`) to reject corrupted partial resumes and ensure cryptographic bit-level integrity.

### 2. Qualcomm Adreno Flash Attention Defense & CPU Isolation (`engine.py`)
- **Adreno Compiler Assertion Defense**: Automatically injects `-fa 0` (Flash Attention disabled) during mobile GPU inference to prevent closed-source driver compiler assertion crashes.
- **Buggy Vulkan Driver Isolation**: Sets `GGML_VK_VISIBLE_DEVICES = ""` under pure CPU mode (`device="cpu"`), preventing buggy vendor Vulkan driver crashes during CPU execution.

### 3. Model-Aware Chat Template Auto-Resolution
- **Zero-Friction Prompting**: Automatically formats chat templates for Qwen (`<|im_start|>`) and Llama-3 (`<|start_header_id|>`) models with deterministic stop token cleanup.

### 4. Official ameva-runtime Adapter Integration
- **Deep Bionic HAL Binding**: Integrated `LlamaCppAdapter.get_execution_environment()` for seamless Bionic HAL shim and dynamic library orchestration.

---

## Detailed Changelog

### Fixed & Hardened
- `termux_llamacpp/downloader.py`: Added 5-stage exponential backoff retry and robust HTTP Range 206/416 handling.
- `termux_llamacpp/engine.py`: Injected `-fa 0` guard, `GGML_VK_VISIBLE_DEVICES` isolation, and automatic Qwen/Llama3 chat template formatting.
- `termux_llamacpp/cli.py`: Integrated ameva-runtime adapter environment.
- Manifests synchronized across `pyproject.toml`, `package.json`, `termux_llamacpp/__init__.py`, and `doc.config.yaml` to `1.3.10`.
