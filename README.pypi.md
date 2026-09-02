# termux-llamacpp

> **Universal GGUF Large Language Model Inference Engine & Supervisor for Android Termux**  
> *Non-Root Native ARM64 Execution · Ed25519 Trust Store · Reverse Proxy Supervisor · Dynamic Model Registry · OpenAI API Compatible*

---

## 🚀 Key Features

- **OpenAI-Compatible Local API**: Run /v1/chat/completions and /v1/models directly on your smartphone.
- **Ed25519 Trust Store**: Cryptographically signed binary and model checksum verification.
- **Mobile Hardware Probing**: Automatic SoC detection (Snapdragon Adreno Vulkan vs ARM NEON CPU).
- **Process Identity Lock**: Single-instance supervisor preventing duplicate server instances.

---

## ⚡ 5-Minute Quickstart

### Python Installation

`ash
# In Android Termux:
pkg update && pkg install -y clang cmake python openblas
pip install termux-llamacpp
`

### Starting the Server

`ash
# Start local inference server on port 8080:
termux-llamacpp serve --model qwen2.5-0.5b --port 8080
`

### Python SDK Usage

`python
import requests

response = requests.post("http://127.0.0.1:8080/v1/chat/completions", json={
    "model": "qwen2.5-0.5b",
    "messages": [{"role": "user", "content": "Hello on-device AI!"}]
})
print(response.json()["choices"][0]["message"]["content"])
`

---

## 📚 Official Documentation

- **Official Web Documentation**: [https://uno-km.vercel.app/lib/llamacpp/](https://uno-km.vercel.app/lib/llamacpp/)
- **GitHub Repository**: [https://github.com/uno-km/termux-llamacpp](https://github.com/uno-km/termux-llamacpp)
- **License**: Apache-2.0