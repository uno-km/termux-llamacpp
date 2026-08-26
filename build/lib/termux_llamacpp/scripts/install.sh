#!/usr/bin/env bash
# ==============================================================================
# termux-llamacpp: Pinned 40-Char Git Commit Native Build & Installation Pipeline
# ==============================================================================
set -euo pipefail

PRESET="${TERMUX_LLAMA_PRESET:-android-arm64-baseline}"
DEFAULT_COMMIT_SHA="08f32c9b68a8b13a890a827038e21946059d57a2"
DEFAULT_UPSTREAM="https://github.com/ggerganov/llama.cpp.git"

if [ "${TERMUX_LLAMA_UNSAFE_SOURCE_OVERRIDE:-0}" = "1" ]; then
    echo "[SECURITY WARNING] Unsafe source override enabled."
    EXPECTED_COMMIT_SHA="${LLAMA_CPP_COMMIT_SHA:-$DEFAULT_COMMIT_SHA}"
    UPSTREAM_URL="${LLAMA_CPP_UPSTREAM_URL:-$DEFAULT_UPSTREAM}"
else
    readonly EXPECTED_COMMIT_SHA="$DEFAULT_COMMIT_SHA"
    readonly UPSTREAM_URL="$DEFAULT_UPSTREAM"
fi

BIN_DIR="${TERMUX_LLAMA_BIN_DIR:-$HOME/.termux-llama/bin}"
BUILD_DIR="/tmp/termux_llamacpp_build"

echo "================================================================================"
echo "  [termux-llamacpp] Pinned-Commit Native Compilation"
echo "================================================================================"
echo "  Target Preset : $PRESET"
echo "  Expected SHA  : $EXPECTED_COMMIT_SHA"
echo "  Binary Dir    : $BIN_DIR"
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
    echo "  [Termux] Ensuring build dependencies (clang, cmake, ninja, git, python)..."
    if ! pkg update -y; then
        echo "[ERROR] Termux package index update failed." >&2
        exit 1
    fi
    if ! pkg install -y clang cmake ninja git python; then
        echo "[ERROR] Failed to install build toolchain packages." >&2
        exit 1
    fi
fi

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo "  [termux-llamacpp] Cloning llama.cpp repository..."
git clone "$UPSTREAM_URL" llama.cpp
cd llama.cpp

echo "  [termux-llamacpp] Checking out detached commit: $EXPECTED_COMMIT_SHA..."
git checkout --detach "$EXPECTED_COMMIT_SHA"

ACTUAL_COMMIT_SHA=$(git rev-parse HEAD)
if [ "$ACTUAL_COMMIT_SHA" != "$EXPECTED_COMMIT_SHA" ]; then
    echo "[ERROR] Git commit verification failed!" >&2
    echo "Expected: $EXPECTED_COMMIT_SHA" >&2
    echo "Actual  : $ACTUAL_COMMIT_SHA" >&2
    exit 1
fi
echo "  [termux-llamacpp] Commit integrity verified: $ACTUAL_COMMIT_SHA"

echo "  [termux-llamacpp] Configuring CMake..."
cmake -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS="$OPT_FLAGS" \
    -DCMAKE_CXX_FLAGS="$OPT_FLAGS" \
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
    else
        echo "[ERROR] Missing compiled build artifact: $name" >&2
        exit 1
    fi

    local tmp_bin="$BIN_DIR/$name.tmp.$$"
    local tmp_receipt="$BIN_DIR/$name.build-receipt.json.tmp.$$"
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
  "artifact_type": "local-native-build",
  "build_preset": "$PRESET",
  "sha256": "$bin_sha256",
  "llama_cpp_commit": "$EXPECTED_COMMIT_SHA",
  "built_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
    chmod 0644 "$tmp_receipt"

    mv -f "$tmp_bin" "$final_bin"
    mv -f "$tmp_receipt" "$final_receipt"
    echo "  [termux-llamacpp] Atomically installed $name and build receipt: $final_receipt"
}

echo "  [termux-llamacpp] Installing compiled binaries to $BIN_DIR..."
install_binary "llama-server"
install_binary "llama-cli"

test -x "$BIN_DIR/llama-server"
test -x "$BIN_DIR/llama-cli"

echo "================================================================================"
echo "  [termux-llamacpp] Pinned Native Build & Atomic Provenance Installation Completed!"
echo "================================================================================"
