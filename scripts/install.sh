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

echo "  [termux-llamacpp] Installing compiled binaries to $BIN_DIR..."
install_binary "llama-server"
install_binary "llama-cli"

test -x "$BIN_DIR/llama-server"
test -x "$BIN_DIR/llama-cli"

echo "================================================================================"
echo "  [termux-llamacpp] Pinned Native Build & Provenance Installation Completed!"
echo "================================================================================"
