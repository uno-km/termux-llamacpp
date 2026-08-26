# termux-llamacpp: 공급망 검증형 범용 GGUF 런타임 관리자 결과보고서 및 전체 소스코드 추출본 (Master Report & Full Source Extraction)

---

## 1. 프로젝트 개요 및 공식 판정 상태 (Release Assessment)

> **공식 정의**:  
> **`termux-llamacpp`는 Android Termux 환경에서 고정된 llama.cpp 런타임과 검증된 GGUF 모델을 안전하게 설치, 검증, 실행하고 OpenAI 호환 로컬 API로 제공하는 공급망 검증형 런타임 관리자입니다.**

### 현재 공식 판정 상태 (Ground Truth)
- **배포 버전**: `1.0.0b1` (`Development Status :: 4 - Beta`)
- **보안 검증 상태**: **주요 P0/P1 보안 결함 조치 완료 및 공급망 신뢰 계층 분류 적용, 유닛 테스트 34건 전수 통과**
- **공개 배포 상태**: **내부 패키징 및 보안 통합 검증용 1.0.0b1 Beta 유효 / Android Termux ARM64 실기기(Galaxy S20 등) 원격 빌드, 모델 로드, readiness, completion 및 실시간 추론 스트리밍 부하 테스트 후 정식 Production 승인**

> **[공식 릴리스 계약 및 보안 경계 명시]**:  
> `termux-llamacpp 1.0.0b1`은 official release binary에 대해 trusted Ed25519 key로 서명된 manifest, pinned llama.cpp commit 및 실측 SHA-256을 검증하며, signed manifest가 존재할 경우 검증 실패를 local build receipt로 우회하지 않습니다. Production local build는 pinned commit과 binary SHA-256을 기록한 receipt를 사용합니다. Development source override build는 별도의 `development-local-build` 등급으로 분류하며, 명시적 execution policy(`allow_development_build=True`)가 없으면 실행을 거부합니다.  
> Binary와 receipt는 각각 atomic rename으로 설치됩니다. 두 파일 전체에 대한 다중 파일 원자성은 제공하지 않으며, 설치 중단으로 파일 조합이 불일치하면 실행 전 hash 및 commit 검증에서 fail-closed 처리됩니다. Binary, model 및 sidecar manifest/receipt의 symbolic link는 거부하지만, 동일 사용자 권한이 경로를 검증과 실행 사이에 교체하는 모든 TOCTOU 공격에 대한 완전한 외부 보호는 제공하지 않습니다.  
> 현재 버전은 host-side unit 및 packaging regression 34건을 통과한 내부 Beta입니다. 공개 Production 승인은 Android Termux ARM64 실기기 native build, verified GGUF load, readiness, completion, SSE streaming, concurrent startup, installation interruption recovery 및 release artifact signing 검증 후 결정합니다.

---

## 2. 결함 조치 및 보안 강화 상세 내역 (Remediation & Hardening Matrix)

| 결함 ID | 식별된 결함 및 문제점 | 수정 및 적용된 Fail-Closed 구현 내용 |
| :--- | :--- | :--- |
| **P0-1** | Development receipt 생성과 검증 계약의 충돌 문제 | **신뢰 계층 정책 분리**: `RECEIPT_TYPE_TO_TRUST_LEVEL` 매핑을 도입하고 `verify_binary_pre_execution()`에 `allow_development_build` 파라미터를 추가. 기본 실행에서는 `development-local-build`를 엄격히 거부하고, 명시적 개발 모드 승인 시에만 `DEVELOPMENT_BUILD` 등급으로 실행 허용. |
| **P0-2** | 심링크 및 사이드카 경로 TOCTOU 취약 표면 | `require_regular_non_symlink_file()` 헬퍼를 도입하여 바이너리, 모델 본문뿐만 아니라 `*.manifest.json`, `*.build-receipt.json`, `*.pub`, `revoked-keys.json` 등 모든 신뢰 루트 및 사이드카의 심링크를 전면 차단. |
| **P0-3** | 설치 스크립트 소스 오버라이드 격리 및 메타데이터 기록 | `install.sh`에서 `TERMUX_LLAMA_ALLOW_DEVELOPMENT_MODE=1`이 명시되지 않은 오버라이드를 거부하고, 오버라이드 빌드 영수증에 `source_override_used: true`, `upstream_url`, `release_eligible: false`를 명시 기록. |
| **P1-1** | Commit Pin 검증 일관성 | `verify_manifest_and_binary()` 및 `verify_binary_pre_execution()` 모두에서 `LLAMA_CPP_PINNED_COMMIT`과의 `hmac.compare_digest` 대조를 필수 강제. |
| **P1-2** | 고유 임시 파일명 생성 | `install.sh`에서 PID 기반 대신 `mktemp "$BIN_DIR/.${name}.bin.XXXXXXXX"` 및 `mktemp "$BIN_DIR/.${name}.receipt.XXXXXXXX"`을 사용하여 충돌 및 예측 가능성 차단. |
| **P1-3** | Git 소스 트리 구조적 일관성 검증 | `mktemp` 격리 디렉터리에서 빌드 후 `git diff --exit-code`, `git status --porcelain`, `git fsck --full --strict` 검증을 필수 수행. |
| **P1-4** | SSOT 메타데이터 단일화 | `pyproject.toml`을 유일한 메타데이터 및 패키지 데이터 정의 소스로 통합하고 `setup.py`를 최소 래퍼로 축소. |
| **P1-5** | 다이제스트 체인 분리 | 업스트림 llama.cpp 커밋(`llama_cpp_upstream_commit_pinned`)과 termux-llamacpp 레포지토리 커밋(`termux_llamacpp_source_commit`), 트리 SHA(`termux_llamacpp_source_tree`)를 명확히 분리하여 `artifacts/digest-chain.json`으로 저장. |

---

## 3. 배포 아티팩트 및 무결성 체크섬 (`dist/`)

```
dist/
├── termux_llamacpp-1.0.0b1-py3-none-any.whl (SHA-256: 5B4C386CC3069449446ACFD0B48C6A1B0A188676E560935DDDF03D54F859D57E)
└── termux_llamacpp-1.0.0b1.tar.gz           (SHA-256: 212DAB78BC7F3DD21283340B398B97ABD21941C842FE28A3EDC820ED1469EF7E)
```

### Wheel 패키지 내부 구성 검증 (`zipfile -l`)
```text
termux_llamacpp/__init__.py
termux_llamacpp/cli.py
termux_llamacpp/config.py
termux_llamacpp/crawler.py
termux_llamacpp/downloader.py
termux_llamacpp/engine.py
termux_llamacpp/exceptions.py
termux_llamacpp/hardware.py
termux_llamacpp/security.py
termux_llamacpp/server.py
termux_llamacpp/registry/models.json
termux_llamacpp/scripts/install.sh
termux_llamacpp/trust/release-2026-01.pub
termux_llamacpp/trust/revoked-keys.json
termux_llamacpp-1.0.0b1.dist-info/licenses/LICENSE
termux_llamacpp-1.0.0b1.dist-info/METADATA
termux_llamacpp-1.0.0b1.dist-info/WHEEL
termux_llamacpp-1.0.0b1.dist-info/entry_points.txt
termux_llamacpp-1.0.0b1.dist-info/top_level.txt
termux_llamacpp-1.0.0b1.dist-info/RECORD
```

---

## 4. 유닛 테스트 실행 증적 (Automated Test Evidence - 34 Tests)

```text
PS C:\Users\GAME\Desktop\uno-km\dev\termux-llamacpp> py -3 -m unittest discover -s tests -p 'test_*.py'
.................................127.0.0.1 - - [27/Aug/2026 00:53:06] "GET /health HTTP/1.1" 200 -
127.0.0.1 - - [27/Aug/2026 00:53:06] "POST /v1/chat/completions HTTP/1.1" 400 -
127.0.0.1 - - [27/Aug/2026 00:53:06] "GET /invalid_route HTTP/1.1" 404 -
.
----------------------------------------------------------------------
Ran 34 tests in 2.094s

OK
```

---

## 5. 프로젝트 전체 소스코드 추출본 (Full Source Code)

### 5.1 `pyproject.toml`
```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "termux-llamacpp"
version = "1.0.0b1"
description = "Supply-Chain Verified GGUF Runtime, Model Manager & OpenAI Supervisor for Android Termux & ARM64"
readme = "README.md"
authors = [{ name = "uno-km", email = "dev@ameva.org" }]
license = { text = "Apache-2.0" }
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Operating System :: POSIX :: Linux",
    "Operating System :: Android",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "Topic :: Security",
]
keywords = ["termux", "llama.cpp", "gguf", "android", "llm", "arm64", "openai-server", "supply-chain-security"]
requires-python = ">=3.8"
dependencies = [
    "requests>=2.31.0",
    "tqdm>=4.66.0",
    "cryptography>=42.0.0",
]

[project.optional-dependencies]
crawler = [
    "termux-playwright>=1.70.0",
]
test = [
    "pytest>=7.0.0",
]

[project.scripts]
termux-llama = "termux_llamacpp.cli:main"
termux-llamacpp = "termux_llamacpp.cli:main"

[project.urls]
Homepage = "https://uno-km.github.io/termux-llamacpp"
Repository = "https://github.com/uno-km/termux-llamacpp"
Documentation = "https://uno-km.github.io/termux-llamacpp"

[tool.setuptools.packages.find]
include = ["termux_llamacpp", "termux_llamacpp.*"]

[tool.setuptools.package-data]
termux_llamacpp = [
    "scripts/*.sh",
    "registry/*.json",
    "trust/*.pub",
    "trust/*.json",
]
```

---

### 5.2 `setup.py`
```python
"""Minimal setup.py wrapper for backward-compatibility with editable installs."""

from setuptools import setup

setup()
```

---

### 5.3 `scripts/install.sh`
```bash
#!/usr/bin/env bash
# ==============================================================================
# termux-llamacpp: Pinned 40-Char Git Commit Native Build & Installation Pipeline
# ==============================================================================
set -e
set -u

PRESET="${TERMUX_LLAMA_PRESET:-android-arm64-baseline}"
DEFAULT_COMMIT_SHA="5e6a37cb115dc1074e274ac004373f5661909695"
DEFAULT_UPSTREAM="https://github.com/ggerganov/llama.cpp.git"

# Production release script enforces pinned commit immutability
if [ "${TERMUX_LLAMA_UNSAFE_SOURCE_OVERRIDE:-0}" = "1" ]; then
    if [ "${TERMUX_LLAMA_ALLOW_DEVELOPMENT_MODE:-0}" != "1" ]; then
        echo "[SECURITY ERROR] Source override requires explicit TERMUX_LLAMA_ALLOW_DEVELOPMENT_MODE=1." >&2
        exit 2
    fi
    echo "[SECURITY WARNING] Development source override active."
    EXPECTED_COMMIT_SHA="${LLAMA_CPP_COMMIT_SHA:-$DEFAULT_COMMIT_SHA}"
    UPSTREAM_URL="${LLAMA_CPP_UPSTREAM_URL:-$DEFAULT_UPSTREAM}"
    RECEIPT_TRUST_LEVEL="development-local-build"
    SOURCE_OVERRIDE_USED=true
    RELEASE_ELIGIBLE=false
else
    readonly EXPECTED_COMMIT_SHA="$DEFAULT_COMMIT_SHA"
    readonly UPSTREAM_URL="$DEFAULT_UPSTREAM"
    RECEIPT_TRUST_LEVEL="local-native-build"
    SOURCE_OVERRIDE_USED=false
    RELEASE_ELIGIBLE=true
fi

BIN_DIR="${TERMUX_LLAMA_BIN_DIR:-$HOME/.termux-llama/bin}"

# Secure, non-predictable temporary build workspace
BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/termux-llamacpp.XXXXXXXX")"

cleanup() {
    rm -rf -- "$BUILD_DIR"
}
trap cleanup EXIT INT TERM HUP

echo "================================================================================"
echo "  [termux-llamacpp] Pinned-Commit Native Compilation"
echo "================================================================================"
echo "  Target Preset : $PRESET"
echo "  Expected SHA  : $EXPECTED_COMMIT_SHA"
echo "  Binary Dir    : $BIN_DIR"
echo "  Workspace     : $BUILD_DIR"
echo "================================================================================"

mkdir -p "$BIN_DIR"

case "$PRESET" in
    "android-arm64-baseline")
        OPT_FLAGS="-O3 -march=armv8-a"
        ;;
    "android-arm64-dotprod")
        OPT_FLAGS="-O3 -march=armv8.2-a+fp16+dotprod"
        ;;
    "android-arm64-native")
        OPT_FLAGS="-O3 -mcpu=native"
        ;;
    "host-native")
        OPT_FLAGS="-O3 -march=native"
        ;;
    *)
        echo "[ERROR] Unknown build preset: '$PRESET'" >&2
        echo "Supported presets: android-arm64-baseline, android-arm64-dotprod, android-arm64-native, host-native" >&2
        exit 2
        ;;
esac

echo "  Compiler Flags: $OPT_FLAGS"

if [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux/files/usr" ]; then
    echo "  [Termux] Checking build toolchain dependencies..."
    if ! command -v clang >/dev/null 2>&1 || ! command -v cmake >/dev/null 2>&1 || ! command -v ninja >/dev/null 2>&1; then
        echo "  [Termux] Installing build toolchain packages (clang, cmake, ninja, git, python)..."
        pkg install -y clang cmake ninja git python || true
    fi
fi

cd "$BUILD_DIR"

echo "  [termux-llamacpp] Fetching pinned commit $EXPECTED_COMMIT_SHA from $UPSTREAM_URL..."
mkdir -p llama.cpp
cd llama.cpp
git init -q
git remote add origin "$UPSTREAM_URL"
git fetch --depth=1 origin "$EXPECTED_COMMIT_SHA"
git checkout -q FETCH_HEAD

ACTUAL_COMMIT_SHA=$(git rev-parse HEAD)
if [ "$ACTUAL_COMMIT_SHA" != "$EXPECTED_COMMIT_SHA" ]; then
    echo "[ERROR] Git commit verification failed!" >&2
    echo "Expected: $EXPECTED_COMMIT_SHA" >&2
    echo "Actual  : $ACTUAL_COMMIT_SHA" >&2
    exit 1
fi

echo "  [termux-llamacpp] Verifying source tree cleanliness and structural integrity..."
git diff --exit-code
test -z "$(git status --porcelain --untracked-files=all)"
git fsck --full --strict
echo "  [termux-llamacpp] Source tree verified clean and structurally consistent."

echo "  [termux-llamacpp] Configuring CMake..."
cmake -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS="$OPT_FLAGS" \
    -DCMAKE_CXX_FLAGS="$OPT_FLAGS" \
    -DCMAKE_INSTALL_RPATH="\$ORIGIN" \
    -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
    -DGGML_BUILD_TESTS=OFF \
    -DGGML_BUILD_EXAMPLES=OFF \
    -DLLAMA_BUILD_SERVER=ON

echo "  [termux-llamacpp] Building llama-server and llama-cli..."
cmake --build build --config Release -j"$(nproc 2>/dev/null || echo 4)" --target llama-server llama-cli

install_binary() {
    local name="$1"
    local src_path=""
    if [ -f "build/bin/$name" ]; then
        src_path="build/bin/$name"
    elif [ -f "build/$name" ]; then
        src_path="build/$name"
    elif [ -f "build/bin/Release/$name" ]; then
        src_path="build/bin/Release/$name"
    else
        src_path="$(find build -name "$name" -type f -perm -111 2>/dev/null | head -n 1)"
    fi

    if [ -z "$src_path" ] || [ ! -f "$src_path" ]; then
        echo "[ERROR] Missing compiled build artifact: $name" >&2
        exit 1
    fi

    local tmp_bin
    local tmp_receipt
    tmp_bin="$(mktemp "$BIN_DIR/.${name}.bin.XXXXXXXX")"
    tmp_receipt="$(mktemp "$BIN_DIR/.${name}.receipt.XXXXXXXX")"

    local final_bin="$BIN_DIR/$name"
    local final_receipt="$BIN_DIR/$name.build-receipt.json"

    cp "$src_path" "$tmp_bin"
    chmod 0755 "$tmp_bin"

    local bin_sha256=""
    if command -v sha256sum >/dev/null 2>&1; then
        bin_sha256=$(sha256sum "$tmp_bin" | awk '{print $1}')
    elif command -v shasum >/dev/null 2>&1; then
        bin_sha256=$(shasum -a 256 "$tmp_bin" | awk '{print $1}')
    else
        bin_sha256=$(python3 -c "import hashlib; print(hashlib.sha256(open('$tmp_bin', 'rb').read()).hexdigest())")
    fi

    cat <<EOF > "$tmp_receipt"
{
  "artifact_filename": "$name",
  "artifact_type": "$RECEIPT_TRUST_LEVEL",
  "build_preset": "$PRESET",
  "sha256": "$bin_sha256",
  "llama_cpp_commit": "$EXPECTED_COMMIT_SHA",
  "source_override_used": $SOURCE_OVERRIDE_USED,
  "upstream_url": "$UPSTREAM_URL",
  "release_eligible": $RELEASE_ELIGIBLE,
  "built_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
    chmod 0644 "$tmp_receipt"

    mv -f "$tmp_bin" "$final_bin"
    mv -f "$tmp_receipt" "$final_receipt"
    echo "  [termux-llamacpp] Installed $name and build receipt: $final_receipt"
}

echo "  [termux-llamacpp] Installing compiled binaries and shared libraries to $BIN_DIR..."
# Copy all built shared libraries so dynaminc linker resolves dependencies
find build -name "*.so*" -type f -exec cp -a {} "$BIN_DIR/" \; 2>/dev/null || true
install_binary "llama-server"
install_binary "llama-cli"

test -x "$BIN_DIR/llama-server"
test -x "$BIN_DIR/llama-cli"

echo "================================================================================"
echo "  [termux-llamacpp] Pinned Native Build & Provenance Installation Completed!"
echo "================================================================================"
```

---

### 5.4 `termux_llamacpp/security.py`
```python
"""Supply chain security, cryptographic trust roots, Ed25519 verification, and provenance."""

import base64
import binascii
import hashlib
import hmac
import ipaddress
import json
import os
import re
import shutil
import stat
import sys
import urllib.parse
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Set, Union

from termux_llamacpp.config import TRUST_DIR, LLAMA_CPP_PINNED_COMMIT
from termux_llamacpp.exceptions import TermuxLlamaError, SecurityVerificationError

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")

ALLOWED_BUILD_PRESETS = {
    "android-arm64-baseline",
    "android-arm64-dotprod",
    "android-arm64-native",
    "host-native",
}


class BinaryTrustLevel(str, Enum):
    """Explicit provenance classification for verified native runtime binaries."""
    SIGNED_RELEASE = "signed-release"
    LOCAL_BUILD_RECEIPT = "local-build-receipt"
    DEVELOPMENT_BUILD = "development-local-build"


RECEIPT_TYPE_TO_TRUST_LEVEL = {
    "local-native-build": BinaryTrustLevel.LOCAL_BUILD_RECEIPT,
    "development-local-build": BinaryTrustLevel.DEVELOPMENT_BUILD,
}


@dataclass(frozen=True)
class BinaryVerificationResult:
    """Immutable record of binary pre-execution verification output."""
    trust_level: BinaryTrustLevel
    sha256: str
    llama_cpp_commit: str
    artifact_filename: str
    signing_key_id: Optional[str] = None
    build_preset: Optional[str] = None
    source_override_used: bool = False
    upstream_url: Optional[str] = None


def require_regular_non_symlink_file(path: Path, context: str) -> None:
    """Strictly reject symbolic links and verify that target is an accessible regular file."""
    try:
        if path.is_symlink():
            raise SecurityVerificationError(f"{context} must not be a symbolic link: '{path}'")
        if not path.is_file():
            raise SecurityVerificationError(f"{context} does not exist or is not a regular file: '{path}'")
    except OSError as exc:
        raise SecurityVerificationError(f"Unable to safely inspect {context} at '{path}': {exc}") from exc


def require_non_empty_string(data: Dict[str, Any], field: str, context: str) -> str:
    """Centralized schema validator ensuring field exists and is a non-empty string."""
    if field not in data:
        raise SecurityVerificationError(f"{context} missing required field: '{field}'")
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
        raise SecurityVerificationError(f"{context} field '{field}' must be a non-empty string.")
    return value.strip()


def canonicalize_json(data: Dict[str, Any]) -> bytes:
    """Deterministic UTF-8 JSON serialization with sorted keys and compact separators."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_sha256(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 hash of a regular local file."""
    require_regular_non_symlink_file(file_path, "File for SHA-256 calculation")
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def fsync_directory(directory: Path) -> None:
    """Synchronize directory metadata to disk on POSIX systems."""
    if hasattr(os, "O_DIRECTORY") and hasattr(os, "fsync"):
        try:
            dir_fd = os.open(str(directory), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError as exc:
            if exc.errno not in (22, 38):  # EINVAL, ENOSYS
                raise SecurityVerificationError(f"Directory fsync failed for {directory}: {exc}") from exc


class TrustStore:
    """Manages trusted Ed25519 public keys and revocation lists with Fail-Closed parsing."""

    def __init__(self, trust_dir: Path = TRUST_DIR):
        self.trust_dir = Path(trust_dir)
        self.public_keys: Dict[str, str] = {}
        self.revoked_keys: Set[str] = set()
        self._load_trust_roots()

    def _load_trust_roots(self):
        if not self.trust_dir.is_dir():
            raise SecurityVerificationError(f"Trust directory not found: {self.trust_dir}")

        revoked_file = self.trust_dir / "revoked-keys.json"
        if revoked_file.exists():
            require_regular_non_symlink_file(revoked_file, "Revocation file")
            try:
                data = json.loads(revoked_file.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or "revoked_key_ids" not in data:
                    raise SecurityVerificationError("Invalid revocation file schema: missing 'revoked_key_ids'.")
                revoked = data.get("revoked_key_ids")
                if not isinstance(revoked, list):
                    raise SecurityVerificationError("'revoked_key_ids' must be a JSON array.")
                if not all(isinstance(k, str) and k.strip() for k in revoked):
                    raise SecurityVerificationError("Every revoked key ID must be a non-empty string.")
                self.revoked_keys = set(revoked)
            except Exception as e:
                if isinstance(e, SecurityVerificationError):
                    raise e
                raise SecurityVerificationError(f"Failed to parse revoked keys file '{revoked_file}': {e}") from e

        pub_files = list(self.trust_dir.glob("*.pub"))
        if not pub_files:
            raise SecurityVerificationError(f"No trusted Ed25519 public keys found in '{self.trust_dir}'.")

        for pub_path in pub_files:
            require_regular_non_symlink_file(pub_path, "Trust root public key file")
            try:
                current_key_id = None
                key_found = False
                for line in pub_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("# "):
                        if line.startswith("# Key-ID:"):
                            current_key_id = line.split(":", 1)[1].strip()
                        continue
                    if line.startswith("ed25519:"):
                        if not current_key_id:
                            raise SecurityVerificationError(f"Found ed25519 key without preceding Key-ID in {pub_path}")
                        if key_found:
                            raise SecurityVerificationError(f"Multiple keys in single trust file '{pub_path}' are forbidden.")
                        key_val = line.split(":", 1)[1].strip()
                        if len(bytes.fromhex(key_val)) != 32:
                            raise SecurityVerificationError(f"Ed25519 public key in {pub_path} must be 32 bytes (64 hex chars).")
                        if current_key_id in self.public_keys:
                            raise SecurityVerificationError(f"Duplicate Key-ID '{current_key_id}' detected in trust store.")
                        self.public_keys[current_key_id] = key_val
                        key_found = True
                    else:
                        raise SecurityVerificationError(f"Unexpected non-comment line in '{pub_path}': {line}")
                if not key_found:
                    raise SecurityVerificationError(f"No valid Ed25519 public key found in '{pub_path}'.")
            except SecurityVerificationError:
                raise
            except Exception as e:
                raise SecurityVerificationError(f"Failed to parse public key file '{pub_path}': {e}") from e

    def is_key_trusted(self, key_id: str) -> bool:
        if not key_id or key_id in self.revoked_keys:
            return False
        return key_id in self.public_keys

    def get_public_key(self, key_id: str) -> Optional[str]:
        if not self.is_key_trusted(key_id):
            return None
        return self.public_keys.get(key_id)


def verify_ed25519_signature(
    public_key_hex: str,
    message_bytes: bytes,
    signature_base64: str,
) -> bool:
    """Cryptographic Fail-Closed Ed25519 Signature Verification."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
    except ImportError as exc:
        raise SecurityVerificationError(
            "Ed25519 cryptographic verification requires 'cryptography>=42.0.0'. "
            "Please install via: pip install cryptography"
        ) from exc

    try:
        if not public_key_hex or not signature_base64:
            return False

        public_key_bytes = bytes.fromhex(public_key_hex)
        if len(public_key_bytes) != 32:
            return False

        signature_bytes = base64.b64decode(signature_base64, validate=True)
        if len(signature_bytes) != 64:
            return False

        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature_bytes, message_bytes)
        return True
    except (InvalidSignature, ValueError, binascii.Error, TypeError):
        return False
    except Exception as exc:
        raise SecurityVerificationError(f"Unexpected cryptographic error: {exc}") from exc


def atomic_replace_verified(
    staged_file: Path,
    destination: Path,
    expected_sha256: str,
    executable: bool = False,
) -> Path:
    """Atomic verified single file replacement with crash-resilient rollback backup."""
    if not _SHA256_RE.fullmatch(expected_sha256):
        raise SecurityVerificationError(f"Invalid expected SHA-256 hash format: {expected_sha256}")

    if destination.is_symlink():
        raise SecurityVerificationError(f"Symlink destination '{destination}' is forbidden.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination_dir = destination.parent

    if staged_file.parent.resolve() != destination_dir.resolve():
        local_stage = destination_dir / f"{destination.name}.stage.{os.getpid()}.tmp"
        with open(staged_file, "rb") as src, open(local_stage, "wb") as dst:
            shutil.copyfileobj(src, dst)
            dst.flush()
            os.fsync(dst.fileno())
        staged_file.unlink(missing_ok=True)
    else:
        local_stage = staged_file
        with open(local_stage, "rb+") as f:
            f.flush()
            os.fsync(f.fileno())

    actual_sha256 = compute_sha256(local_stage)
    if not hmac.compare_digest(actual_sha256.lower(), expected_sha256.lower()):
        local_stage.unlink(missing_ok=True)
        raise SecurityVerificationError(
            f"Staged file checksum mismatch!\nExpected: {expected_sha256}\nActual: {actual_sha256}"
        )

    if executable:
        try:
            local_stage.chmod(0o755)
        except Exception:
            pass

    backup_file = destination_dir / f"{destination.name}.bak.{os.getpid()}.tmp"
    has_existing = destination.exists()
    if has_existing:
        os.replace(str(destination), str(backup_file))
        fsync_directory(destination_dir)

    try:
        os.replace(str(local_stage), str(destination))
        fsync_directory(destination_dir)

        installed_sha256 = compute_sha256(destination)
        if not hmac.compare_digest(installed_sha256.lower(), expected_sha256.lower()):
            raise SecurityVerificationError("Post-installation file verification failed.")

        if has_existing and backup_file.exists():
            backup_file.unlink(missing_ok=True)
            fsync_directory(destination_dir)

    except Exception as exc:
        if destination.exists():
            destination.unlink(missing_ok=True)
        if has_existing and backup_file.exists():
            os.replace(str(backup_file), str(destination))
            fsync_directory(destination_dir)
        raise SecurityVerificationError(f"Atomic replacement failed; restored previous state: {exc}") from exc

    return destination.resolve()


def verify_manifest_and_binary(
    manifest_data: Dict[str, Any],
    temp_binary_path: Path,
    target_destination: Path,
    trust_store: Optional[TrustStore] = None,
    expected_commit: str = LLAMA_CPP_PINNED_COMMIT,
) -> Path:
    """
    P1-1: Strict 8-Step Cryptographic Verification Pipeline for Native Binaries.
    Validates manifest structure, commit pin equality, Ed25519 signature, and staged SHA-256 hash.
    """
    if trust_store is None:
        trust_store = TrustStore()

    if not isinstance(manifest_data, dict):
        raise SecurityVerificationError("Binary manifest must be a JSON object.")

    key_id = require_non_empty_string(manifest_data, "key_id", "Binary manifest")
    signature = require_non_empty_string(manifest_data, "signature", "Binary manifest")
    expected_sha256 = require_non_empty_string(manifest_data, "sha256", "Binary manifest")
    commit = require_non_empty_string(manifest_data, "llama_cpp_commit", "Binary manifest")
    artifact_filename = require_non_empty_string(manifest_data, "artifact_filename", "Binary manifest")

    if artifact_filename != target_destination.name:
        raise SecurityVerificationError(
            f"Binary manifest artifact filename mismatch. Expected '{target_destination.name}', got '{artifact_filename}'"
        )

    if not _SHA256_RE.fullmatch(expected_sha256):
        raise SecurityVerificationError(f"Invalid sha256 in binary manifest: {expected_sha256}")
    if not _COMMIT_RE.fullmatch(commit):
        raise SecurityVerificationError(f"Invalid commit SHA in binary manifest: {commit}")

    if not hmac.compare_digest(commit.lower(), expected_commit.lower()):
        raise SecurityVerificationError(
            f"Binary manifest commit mismatch. Expected '{expected_commit}', got '{commit}'."
        )

    if not trust_store.is_key_trusted(key_id):
        raise SecurityVerificationError(f"Signing key '{key_id}' is not in local trust store or has been revoked.")

    pub_key = trust_store.get_public_key(key_id)
    payload_to_verify = {k: v for k, v in manifest_data.items() if k != "signature"}
    canonical_bytes = canonicalize_json(payload_to_verify)

    if not verify_ed25519_signature(pub_key, canonical_bytes, signature):
        raise SecurityVerificationError(f"Ed25519 manifest signature verification failed for key '{key_id}'.")

    require_regular_non_symlink_file(temp_binary_path, "Temporary staged binary")

    return atomic_replace_verified(
        staged_file=temp_binary_path,
        destination=target_destination,
        expected_sha256=expected_sha256,
        executable=True,
    )


def verify_binary_pre_execution(
    binary_path: Path,
    trust_store: Optional[TrustStore] = None,
    expected_commit: str = LLAMA_CPP_PINNED_COMMIT,
    allow_local_build_receipt: bool = True,
    allow_development_build: bool = False,
) -> BinaryVerificationResult:
    """
    P0-1: Pre-Execution Native Binary Verification with Explicit Provenance Classification.
    Returns:
      BinaryVerificationResult containing trust_level ('signed-release', 'local-build-receipt', or 'development-local-build').
    ANTI-DOWNGRADE GUARANTEE:
      If a signed manifest exists (*.manifest.json), it MUST pass Ed25519 signature verification.
      An invalid signed manifest NEVER falls back to local build receipt.
    """
    require_regular_non_symlink_file(binary_path, "Native runtime binary")

    manifest_path = binary_path.with_suffix(binary_path.suffix + ".manifest.json")
    receipt_path = binary_path.with_suffix(binary_path.suffix + ".build-receipt.json")

    # 1. Official Signed Release Pathway (Highest Trust Level)
    if manifest_path.exists():
        require_regular_non_symlink_file(manifest_path, "Binary release manifest")
        if trust_store is None:
            trust_store = TrustStore()

        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise SecurityVerificationError(f"Corrupted binary manifest '{manifest_path}': {e}") from e

        if not isinstance(manifest_data, dict):
            raise SecurityVerificationError(f"Binary manifest '{manifest_path}' must be a JSON object.")

        key_id = require_non_empty_string(manifest_data, "key_id", "Binary manifest")
        signature = require_non_empty_string(manifest_data, "signature", "Binary manifest")
        expected_sha256 = require_non_empty_string(manifest_data, "sha256", "Binary manifest")
        commit = require_non_empty_string(manifest_data, "llama_cpp_commit", "Binary manifest")
        artifact_filename = require_non_empty_string(manifest_data, "artifact_filename", "Binary manifest")

        if artifact_filename != binary_path.name:
            raise SecurityVerificationError(
                f"Binary manifest artifact mismatch. Expected '{binary_path.name}', got '{artifact_filename}'"
            )

        if not _SHA256_RE.fullmatch(expected_sha256):
            raise SecurityVerificationError(f"Invalid SHA-256 hash in binary manifest: {expected_sha256}")
        if not _COMMIT_RE.fullmatch(commit):
            raise SecurityVerificationError(f"Invalid commit SHA in binary manifest: {commit}")

        if not hmac.compare_digest(commit.lower(), expected_commit.lower()):
            raise SecurityVerificationError(
                f"Binary commit mismatch!\nExpected: {expected_commit}\nManifest: {commit}"
            )

        if not trust_store.is_key_trusted(key_id):
            raise SecurityVerificationError(f"Untrusted or revoked key '{key_id}' in binary manifest.")

        pub_key = trust_store.get_public_key(key_id)
        payload = {k: v for k, v in manifest_data.items() if k != "signature"}
        if not verify_ed25519_signature(pub_key, canonicalize_json(payload), signature):
            raise SecurityVerificationError(f"Binary manifest Ed25519 signature is invalid for key '{key_id}'.")

        actual_sha = compute_sha256(binary_path)
        if not hmac.compare_digest(actual_sha.lower(), expected_sha256.lower()):
            raise SecurityVerificationError(
                f"Pre-execution binary tampering detected!\nExpected: {expected_sha256}\nActual: {actual_sha}"
            )

        return BinaryVerificationResult(
            trust_level=BinaryTrustLevel.SIGNED_RELEASE,
            sha256=actual_sha,
            llama_cpp_commit=commit,
            artifact_filename=artifact_filename,
            signing_key_id=key_id,
        )

    # 2. Local Native Build Receipt Pathway (Consistent Local Build Trust Level)
    if receipt_path.exists() and allow_local_build_receipt:
        require_regular_non_symlink_file(receipt_path, "Local build receipt")
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise SecurityVerificationError(f"Corrupted local build receipt '{receipt_path}': {e}") from e

        if not isinstance(receipt, dict):
            raise SecurityVerificationError(f"Build receipt '{receipt_path}' must be a JSON object.")

        artifact_filename = require_non_empty_string(receipt, "artifact_filename", "Build receipt")
        artifact_type = require_non_empty_string(receipt, "artifact_type", "Build receipt")
        expected_sha = require_non_empty_string(receipt, "sha256", "Build receipt")
        commit = require_non_empty_string(receipt, "llama_cpp_commit", "Build receipt")
        preset = require_non_empty_string(receipt, "build_preset", "Build receipt")

        trust_level = RECEIPT_TYPE_TO_TRUST_LEVEL.get(artifact_type)
        if trust_level is None:
            raise SecurityVerificationError(
                f"Unsupported build receipt artifact_type: '{artifact_type}'. "
                f"Allowed types: {list(RECEIPT_TYPE_TO_TRUST_LEVEL.keys())}"
            )

        if trust_level == BinaryTrustLevel.DEVELOPMENT_BUILD:
            if not allow_development_build:
                raise SecurityVerificationError(
                    "Development build receipt ('development-local-build') is denied by current execution policy. "
                    "Set allow_development_build=True or use a standard production build."
                )
            if not _COMMIT_RE.fullmatch(commit):
                raise SecurityVerificationError(f"Invalid development commit SHA in receipt: '{commit}'")
        else:
            if not hmac.compare_digest(commit.lower(), expected_commit.lower()):
                raise SecurityVerificationError(
                    f"Local build binary commit mismatch!\nExpected: {expected_commit}\nReceipt: {commit}"
                )

        if preset not in ALLOWED_BUILD_PRESETS:
            raise SecurityVerificationError(f"Unknown or untrusted build_preset in receipt: '{preset}'")

        if artifact_filename != binary_path.name:
            raise SecurityVerificationError(
                f"Build receipt artifact mismatch. Expected '{binary_path.name}', got '{artifact_filename}'"
            )

        if not _SHA256_RE.fullmatch(expected_sha):
            raise SecurityVerificationError(f"Invalid SHA-256 hash in build receipt: {expected_sha}")

        actual_sha = compute_sha256(binary_path)
        if not hmac.compare_digest(actual_sha.lower(), expected_sha.lower()):
            raise SecurityVerificationError(
                f"Local binary post-build modification detected!\nExpected: {expected_sha}\nActual: {actual_sha}"
            )

        return BinaryVerificationResult(
            trust_level=trust_level,
            sha256=actual_sha,
            llama_cpp_commit=commit,
            artifact_filename=artifact_filename,
            build_preset=preset,
            source_override_used=receipt.get("source_override_used", False),
            upstream_url=receipt.get("upstream_url"),
        )

    # 3. Fail-Closed if neither verified signed manifest nor build receipt is present
    raise SecurityVerificationError(
        f"Untrusted binary: Neither signed release manifest ('{manifest_path.name}') nor "
        f"verified local build receipt ('{receipt_path.name}') was found for '{binary_path}'."
    )


def verify_model_pre_execution(
    model_path: Path,
    trust_store: Optional[TrustStore] = None,
) -> Dict[str, Any]:
    """
    P0-3: Strict Pre-Execution Signed GGUF Model Manifest & Hash Verification.
    """
    require_regular_non_symlink_file(model_path, "GGUF Model file")

    manifest_path = model_path.with_suffix(model_path.suffix + ".manifest.json")
    if not manifest_path.exists():
        raise SecurityVerificationError(f"Required signed model manifest is missing: {manifest_path}")

    require_regular_non_symlink_file(manifest_path, "Model manifest sidecar")

    if trust_store is None:
        trust_store = TrustStore()

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SecurityVerificationError(f"Corrupted model manifest: {manifest_path}") from exc

    if not isinstance(manifest, dict):
        raise SecurityVerificationError(f"Model manifest '{manifest_path}' must be a JSON object.")

    key_id = require_non_empty_string(manifest, "key_id", "Model manifest")
    signature = require_non_empty_string(manifest, "signature", "Model manifest")
    model_id = require_non_empty_string(manifest, "model_id", "Model manifest")
    artifact_filename = require_non_empty_string(manifest, "artifact_filename", "Model manifest")
    repo_id = require_non_empty_string(manifest, "repo_id", "Model manifest")
    repo_revision = require_non_empty_string(manifest, "repo_revision", "Model manifest")
    expected_sha256 = require_non_empty_string(manifest, "sha256", "Model manifest")

    if "size_bytes" not in manifest:
        raise SecurityVerificationError("Model manifest missing required field: 'size_bytes'")
    size_bytes = manifest["size_bytes"]
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes <= 0:
        raise SecurityVerificationError("Model manifest 'size_bytes' must be a positive integer.")

    if artifact_filename != model_path.name:
        raise SecurityVerificationError(
            f"Model manifest artifact filename mismatch. Expected '{model_path.name}', got '{artifact_filename}'"
        )

    if not _SHA256_RE.fullmatch(expected_sha256):
        raise SecurityVerificationError(f"Invalid SHA-256 hash in model manifest: {expected_sha256}")

    public_key = trust_store.get_public_key(key_id)
    if not public_key:
        raise SecurityVerificationError(f"Model signing key '{key_id}' is untrusted or revoked.")

    payload = {k: v for k, v in manifest.items() if k != "signature"}
    if not verify_ed25519_signature(public_key, canonicalize_json(payload), signature):
        raise SecurityVerificationError(f"Model manifest Ed25519 signature is invalid for key '{key_id}'.")

    actual_sha256 = compute_sha256(model_path)
    if not hmac.compare_digest(actual_sha256.lower(), expected_sha256.lower()):
        raise SecurityVerificationError(
            f"Model file checksum mismatch!\nExpected: {expected_sha256}\nActual: {actual_sha256}"
        )

    actual_size = model_path.stat().st_size
    if actual_size != size_bytes:
        raise SecurityVerificationError(
            f"Model file size mismatch! Expected {size_bytes} bytes, actual {actual_size} bytes."
        )

    return manifest


def normalize_loopback_origin(origin: str) -> Optional[str]:
    """Strict URL and IP-level loopback origin validation (P0-D)."""
    if not origin:
        return None
    try:
        parsed = urllib.parse.urlsplit(origin)
        if parsed.scheme not in {"http", "https"}:
            return None
        if parsed.username or parsed.password:
            return None
        if parsed.path not in {"", "/"}:
            return None
        if parsed.query or parsed.fragment:
            return None
        if parsed.hostname is None:
            return None

        host = parsed.hostname.rstrip(".").lower()
        if host == "localhost":
            return origin

        try:
            ip = ipaddress.ip_address(host)
            if ip.is_loopback:
                return origin
        except ValueError:
            return None

        return None
    except Exception:
        return None


def verify_binary_integrity(binary_path: Path, expected_sha256: str) -> bool:
    """Validate binary SHA-256 integrity."""
    if not binary_path.is_file():
        return False
    return hmac.compare_digest(compute_sha256(binary_path).lower(), expected_sha256.lower())


def atomic_write_and_verify(
    temp_file: Path,
    target_destination: Path,
    expected_sha256: Optional[str] = None,
    executable: bool = False,
) -> Path:
    """Wrapper around atomic_replace_verified."""
    sha = expected_sha256 or compute_sha256(temp_file)
    return atomic_replace_verified(
        staged_file=temp_file,
        destination=target_destination,
        expected_sha256=sha,
        executable=executable,
    )


def atomic_save_json(target_path: Path, data: Dict[str, Any]):
    """Atomically write JSON document with fsync and rename."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = target_path.with_suffix(f"{target_path.suffix}.tmp.{os.getpid()}")
    with open(temp_file, "wb") as f:
        f.write(canonicalize_json(data))
        f.flush()
        os.fsync(f.fileno())
    os.replace(str(temp_file), str(target_path))
    fsync_directory(target_path.parent)


def build_model_manifest_payload(
    model_path: Path,
    model_id: str,
    repo_id: str,
    revision: str,
    sha256: str,
    quant_type: str,
    license_id: str,
    size_bytes: int,
) -> Dict[str, Any]:
    """Deterministic payload constructor for model manifests."""
    return {
        "model_id": model_id,
        "artifact_filename": model_path.name,
        "repo_id": repo_id,
        "repo_revision": revision,
        "sha256": sha256,
        "quant_type": quant_type,
        "license_id": license_id,
        "size_bytes": size_bytes,
    }


def save_signed_model_manifest(
    model_path: Path,
    payload: Dict[str, Any],
    key_id: str,
    signature: str,
    trust_store: Optional[TrustStore] = None,
) -> Path:
    """
    P0-2: Save a cryptographically verified signed model manifest sidecar.
    Validates the Ed25519 signature before writing to disk.
    """
    if not signature or not isinstance(signature, str) or not signature.strip():
        raise SecurityVerificationError("A signed model manifest requires a non-empty Ed25519 signature.")
    if not key_id or not isinstance(key_id, str) or not key_id.strip():
        raise SecurityVerificationError("A signed model manifest requires a non-empty key_id.")

    if trust_store is None:
        trust_store = TrustStore()

    pub_key = trust_store.get_public_key(key_id)
    if not pub_key:
        raise SecurityVerificationError(f"Signing key '{key_id}' is untrusted or revoked.")

    manifest_content = {
        **payload,
        "key_id": key_id,
    }
    canonical_bytes = canonicalize_json(manifest_content)

    if not verify_ed25519_signature(pub_key, canonical_bytes, signature):
        raise SecurityVerificationError("Signature does not match manifest payload.")

    manifest_path = model_path.with_suffix(model_path.suffix + ".manifest.json")
    final_metadata = {
        **manifest_content,
        "signature": signature,
    }
    atomic_save_json(manifest_path, final_metadata)
    return manifest_path
```

---

## 6. 빌드 및 공급망 아티팩트 검증 메타데이터 (Digest Chain)

```json
{
  "schema_version": 1,
  "termux_llamacpp_source_repository": "https://github.com/uno-km/termux-llamacpp",
  "termux_llamacpp_source_commit": "f9ae9e34ac629e10ab266445e3f0751bda79f30b",
  "termux_llamacpp_source_tree": "b1851005566d4f23eb01f97d26a803653cf06afd",
  "working_tree_state": "clean",
  "llama_cpp_upstream_repository": "https://github.com/ggerganov/llama.cpp.git",
  "llama_cpp_upstream_commit_pinned": "08f32c9b68a8b13a890a827038e21946059d57a2",
  "package_version": "1.0.0b1",
  "status": "Development Status :: 4 - Beta",
  "pyproject_toml_sha256": "164FB8F0720110F2B08F000F93343012FD7D8DDCE8E86F43AC8A09F6A5F904E1",
  "wheel_sha256": "5B4C386CC3069449446ACFD0B48C6A1B0A188676E560935DDDF03D54F859D57E",
  "sdist_sha256": "212DAB78BC7F3DD21283340B398B97ABD21941C842FE28A3EDC820ED1469EF7E",
  "tests": {
    "total": 34,
    "passed": 34,
    "failed": 0,
    "errors": 0
  },
  "execution_target_validation": "Internal Packaging Beta Verified / Native Android Termux ARM64 hardware testing pending"
}
```
