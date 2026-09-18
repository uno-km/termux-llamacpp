# Release Notes - termux-llamacpp v1.3.5

**Release Tag**: `v1.3.5`  
**Distribution Channels**: PyPI (`termux-llamacpp`), NPM (`termux-llamacpp`), GitHub Releases  
**Target Platform**: Android Termux (ARM64 / aarch64 Bionic)  
**License**: Apache-2.0  

---

## Highlights & Key Architectural Changes

### 1. 100% Zero-Hardcoding Dynamic Provisioning Architecture
- **Dynamic API Introspection**: Completely purged static fallback versions from installer shell scripts, introducing dynamic GitHub Releases API querying.
- **Harmonized Dual Install Scripts**: Resolved version drift between `scripts/install.sh` and `termux_llamacpp/scripts/install.sh`, enforcing identical 3-Tier resolution.
- **Invariant Latest Canonical Endpoint**: Prioritizes `https://github.com/uno-km/termux-llamacpp/releases/latest/download/termux-llamacpp-${TARGET}.tar.gz` over version-pinned downloads.

### 2. Pure CPU Optimization & Multi-Architecture Support
- **ARM64 Vector Presets**: Provides pre-tuned native builds for universal baseline (`android-arm64-baseline`) and vector-accelerated (`android-arm64-dotprod`) mobile cores.
- **Fail-Safe Source Fallback**: Preserves automatic on-device compilation fallback if precompiled binaries are unavailable.

### 3. Unified Pip & NPM Packaging Parity
- **Full SemVer Synchronization**: Synchronized `pyproject.toml`, `package.json`, and `termux_llamacpp/__init__.py` to `1.3.5`.
- **Node.js Dual Engine CLI**: Full compatibility with `npx termux-llamacpp`.

---

## Detailed Changelog

### Changed
- `scripts/install.sh`: Dynamic version resolution via GitHub Releases API and latest-first URL priority.
- `termux_llamacpp/scripts/install.sh`: Synchronized 1:1 with root install script.
- `CHANGELOG.md`: Added release documentation for `v1.3.5`.
- Package manifests bumped to `1.3.5`.
