# Release Notes - termux-llamacpp

## [v1.0.0b2] - 2026-08-27

### Production 1-Touch Zero-Compilation Runtime & Supply Chain Hardening

#### 🚀 Key Features & Highlights
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

#### 🔒 Security & Supply Chain Hardening
- **Strict Pre-Execution Verification**: Fail-closed enforcement on missing or unverified native binaries (RuntimeBuildError).
- **Symlink & TOCTOU Attack Defense**: Symlinks strictly rejected for binary paths, model weights, and cryptographic manifests.
- **Loopback Isolation**: Native backend isolated strictly to loopback binding with CORS protection.

---

### Packages & Distribution
- **PyPI**: `pip install termux-llamacpp` (v1.0.0b2)
- **npm**: `npm install -g termux-llamacpp` (v1.0.1)
- **Documentation**: [https://uno-km.github.io/termux-llamacpp](https://uno-km.github.io/termux-llamacpp)
