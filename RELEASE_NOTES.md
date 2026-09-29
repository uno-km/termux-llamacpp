# Release Notes - termux-llamacpp v1.3.13

**Release Tag**: `v1.3.13`  
**Distribution Channels**: PyPI (`termux-llamacpp`), NPM (`termux-llamacpp`), GitHub Releases  
**Target Platform**: Android Termux (ARM64 / aarch64 Bionic)  
**License**: Apache-2.0  

---

## Highlights & Key Architectural Changes

### 1. Unified 5-Backend Standard (`["auto", "gpu", "vulkan", "opencl", "cpu"]`)
- **Strict Single Source of Truth**: All CLI subcommands (`run`, `serve`, `benchmark`) and runtime factory parameters now enforce a unified 5-backend whitelist.
- **Fail-Fast Defense**: Passing `cpu_neon` triggers immediate invalid choice rejection (`choose from 'auto', 'gpu', 'vulkan', 'opencl', 'cpu'`). All NEON SIMD capabilities are orchestrated seamlessly under the standard `cpu` target.

### 2. Qualcomm Adreno 600 Series OpenCL Acceleration Engine
- **Direct OpenCL Dispatch**: Added first-class `opencl` backend execution using optimized Qualcomm OpenCL 2.0 kernels (`llama-cli-opencl`).
- **Defect Resolution**: Overcomes Adreno 650 (Snapdragon 865) SPIR-V shader underflow and missing integer dot product hardware by routing compute to native OpenCL.
- **Runtime Model Resolution**: Fixed variable binding in `engine.py` (`resolved_model_path`) and enabled OpenCL binary dispatch for multimodal `generate_vlm`.

### 3. Empirical Silicon Verification
- **Galaxy S20 (Snapdragon 865)**: Verified clean token outputs without character degradation or segmentation faults under OpenCL offloading.
- **Pure CPU NEON Performance**: Validated 47.2 t/s Prompt, 27.0 t/s Generation under `-b cpu`.

---

## Detailed Changelog

### Added & Fixed
- `termux_llamacpp/cli.py`: Standardized backend choices to 5-item set; added `--opencl` flag.
- `termux_llamacpp/hardware.py`: Added OpenCL backend resolution; strictly rejected `cpu_neon`.
- `termux_llamacpp/engine.py`: Added OpenCL binary lookup, environment scoping, and resolved model path resolution bug.
- `pyproject.toml` & `package.json`: Version bumped to `1.3.13`.
- `doc.config.yaml`: Documentation schema and version bumped to `v1.3.13`.
