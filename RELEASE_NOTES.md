# Release Notes - termux-llamacpp

## [v1.1.0] - 2026-08-31

### Production ARM64 Zero-Compilation Runtime & Dual-Engine Real-Device E2E Certified

#### Overview
Version 1.1.0 delivers official 100.0/100.0 (Grade A+) real-device remote verification on Android 13 Termux ARM64 hardware, robust dual-engine orchestration (Python 3.13 / Node.js v24), critical runtime CLI preset bug resolution, and non-interactive inference lifecycle management.

#### Key Highlights
- **Real-Device 100% E2E Verification**:
  - Full 4-phase automated regression passed on physical Samsung Galaxy hardware (Linux 5.15.189-android13-3-33470412 aarch64).
  - Validated across hardware profiling, PyPI wheel provisioning, npm global installation, Bionic native binaries, spatial image IO parsing (Exif/JPEG), live autoregressive LLM forward passes, and OpenAI REST serving.
- **Critical Runtime Bug Fix (`cmd_presets`)**:
  - Resolved `TypeError: 'BuildPreset' object is not subscriptable` in CLI preset inspection by implementing safe attribute extraction for dataclass and dictionary structures.
- **Inference Lifecycle & Single-Turn Non-Blocking Orchestration**:
  - Integrated `--single-turn --simple-io` execution flags for headless scripts, preventing interactive EOF hangs during automated subprocess execution.
  - Hardened process reaper teardown with zero residual or leaked daemon processes.
- **Dual-Engine Full Parity**:
  - Verified Python SDK (`termux_llamacpp`) and Node.js SDK / CLI bridge (`bin/cli.js`) execution parity for diagnostics, curated catalog discovery, and neural generation.

#### Real-Device Measured Benchmarks (Samsung Galaxy / Kryo ARM64)
- **Model**: Qwen 2.5 0.5B Instruct (`Q8_0`, 5425.8 MB total system RAM)
  - **Prompt Processing Speed**: **45.3 tokens / sec**
  - **Token Generation Speed**: **8.8 tokens / sec**
  - **OpenAI v1 REST Round-Trip Latency**: **5,145.84 ms**
  - **Cold Provisioning Time**: **5.06 seconds** (`pip install`), **5.12 seconds** (`npm install`)
  - **Process Termination Latency**: **1,441.73 ms** (Zero leaked processes)

```yaml
verification_matrix:
  environment:
    os: "Android 13 (Termux Bionic ARM64)"
    kernel: "Linux 5.15.189-android13-3-33470412"
    architecture: "aarch64"
    python_version: "3.13.13"
    node_version: "v24.18.0"
  scorecard:
    phase_1_provisioning: "25.0 / 25.0 pts"
    phase_2_dual_engine_cli: "25.0 / 25.0 pts"
    phase_3_image_neural_pipeline: "25.0 / 25.0 pts"
    phase_4_serving_lifecycle: "25.0 / 25.0 pts"
    total_score: "100.0 / 100.0 pts"
    grade: "A+"
  test_assets:
    image_input: "test.jpg (3.69 MB, Samsung SM-A356N Exif 4080x3060 px)"
    model_input: "qwen2.5-0.5b-instruct-q8_0.gguf"
  compliance:
    zero_mocking: true
    zero_compilation: true
    loopback_bound: true
```

---

## [v1.0.0b2] - 2026-08-27

### Production 1-Touch Zero-Compilation Runtime & Supply Chain Hardening

#### Key Features & Highlights
- **Zero-Compilation Instant Installer**:
  - Direct 1-touch installation via `curl -sSL https://raw.githubusercontent.com/uno-km/termux-llamacpp/master/scripts/install.sh | bash`
  - Eliminates heavy mobile toolchains (`clang`, `cmake`, `ninja`), installing verified ARM64 prebuilt native binaries in < 3 seconds.
- **Prebuilt Android Bionic Binaries**:
  - Bundles Bionic-linked `llama-cli`, `llama-server`, and required shared dynamic libraries (`libggml.so`, `libllama.so`).
  - Strict SHA-256 cryptographic verification and atomic directory swapping (`~/.termux-llama`).
- **OpenAI-Compatible REST & SSE Supervisor**:
  - Full reverse proxy supervisor running on port `8080` with `/health`, `/v1/models`, and `/v1/chat/completions` (JSON & SSE streaming).
  - Configured with memory-safe mobile defaults (`-np 1`, `--no-mmap`, `--ctx 2048`).
- **Python Module Entrypoint Support**:
  - Added `python -m termux_llamacpp` and Node.js `termux-llama` unified CLI.
- **Real-Device Measured Benchmarks (Samsung Galaxy S20+ 5G / Snapdragon 865)**:
  - Meta Llama 3.2 3B Instruct (Q4_K_M, 1.92 GiB):
    - Prompt evaluation: **16.19 tokens / sec**
    - Token generation: **10.23 tokens / sec**
    - Cold model load time: **~1.8 seconds**

#### Security & Supply Chain Hardening
- **Strict Pre-Execution Verification**: Fail-closed enforcement on missing or unverified native binaries (RuntimeBuildError).
- **Symlink & TOCTOU Attack Defense**: Symlinks strictly rejected for binary paths, model weights, and cryptographic manifests.
- **Loopback Isolation**: Native backend isolated strictly to loopback binding with CORS protection.

---

### Packages & Distribution
- **PyPI**: `pip install termux-llamacpp` (v1.1.0)
- **npm**: `npm install -g termux-llamacpp` (v1.1.0)
- **Documentation**: [https://uno-km.github.io/termux-llamacpp](https://uno-km.github.io/termux-llamacpp)
