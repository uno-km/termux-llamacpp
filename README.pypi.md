# Termux-LlamaCpp (Python)

[![PyPI](https://img.shields.io/pypi/v/termux-llamacpp.svg?style=flat-square&color=0369a1)](https://pypi.org/project/termux-llamacpp/)
[![Python](https://img.shields.io/pypi/pyversions/termux-llamacpp.svg?style=flat-square)](https://pypi.org/project/termux-llamacpp/)
[![License](https://img.shields.io/badge/License-Apache_2.0-004499.svg?style=flat-square)](https://github.com/uno-km/termux-llamacpp)

> **디바이스 리소스를 활용한 Android Termux ARM64 전용 GGUF LLM 런타임, 모델 매니저 및 OpenAI 호환 REST/SSE 서버**  
> *Production-Grade GGUF LLM Runtime Utilizing Device Resources, Model Manager & OpenAI Server for Android ARM64*

## Installation

```bash
pip install termux-llamacpp
```

## Quickstart

```python
from termux_llamacpp import LlamaRuntime, RuntimeConfig

# 1. Initialize Runtime with Vulkan GPU Acceleration
config = RuntimeConfig(
    model_path="models/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
    device="auto",
    threads=4,
    context_size=2048
)
runtime = LlamaRuntime(config)

# 2. Synchronous or Streaming Text Generation
output = runtime.generate("한국의 사계절 중 가을의 매력에 대해 설명해줘.", max_tokens=256)
print(output.text)
print(f"Speed: {output.metrics.eval_tokens_per_sec:.2f} t/s (Prompt: {output.metrics.prompt_tokens_per_sec:.2f} t/s)")
```

## Description
Ships verified Android ARM64 native binaries with bundled shared libraries and device resource optimization, enabling instant zero-compilation local inference and a robust OpenAI-compatible REST/SSE server.

## Documentation
- [Official Documentation & API Reference](https://uno-km.vercel.app/lib/llamacpp/)
- [GitHub Repository](https://github.com/uno-km/termux-llamacpp)

## License
Apache-2.0 License. Copyright (c) 2026 Eunho Kim (@uno-km).
