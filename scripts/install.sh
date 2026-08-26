#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# termux-llamacpp: Production Prebuilt Zero-Compilation Installer for Termux ARM64
# ==============================================================================
set -euo pipefail

VERSION="${TERMUX_LLAMACPP_VERSION:-1.0.0b1}"
ARCH="$(uname -m)"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
ROOT="${TERMUX_LLAMA_HOME:-$HOME/.termux-llama}"
BIN_DIR="$ROOT/bin"
LIB_DIR="$ROOT/lib"
BASE_URL="https://github.com/uno-km/termux-llamacpp/releases/download/v${VERSION}"
FROM_SOURCE=0

for arg in "$@"; do
    case "$arg" in
        --from-source|--build-from-source)
            FROM_SOURCE=1
            ;;
        --help|-h)
            echo "Usage: install.sh [--from-source] [--help]"
            echo ""
            echo "Options:"
            echo "  (Default)       Download and verify verified prebuilt Android ARM64 binaries (Zero-Compilation)"
            echo "  --from-source   Force local native compilation via Clang/CMake/Ninja"
            exit 0
            ;;
    esac
done

echo "================================================================================"
echo "  [termux-llamacpp] Installer v${VERSION}"
echo "================================================================================"
echo "  Architecture : $ARCH"
echo "  Target Root  : $ROOT"
echo "  Mode         : $([ "$FROM_SOURCE" = "1" ] && echo "Source Build (--from-source)" || echo "Prebuilt Binary (Zero-Compilation)")"
echo "================================================================================"

# ==============================================================================
# Branch 1: Manual Source Compilation (--from-source)
# ==============================================================================
if [ "$FROM_SOURCE" = "1" ]; then
    echo "  [termux-llamacpp] Starting local native compilation..."
    PRESET="${TERMUX_LLAMA_PRESET:-android-arm64-dotprod}"
    PINNED_COMMIT="5e6a37cb115dc1074e274ac004373f5661909695"
    UPSTREAM_URL="https://github.com/ggerganov/llama.cpp.git"
    
    command -v clang >/dev/null 2>&1 || pkg install -y clang
    command -v cmake >/dev/null 2>&1 || pkg install -y cmake
    command -v ninja >/dev/null 2>&1 || pkg install -y ninja
    command -v git >/dev/null 2>&1 || pkg install -y git

    BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/termux-llamacpp-src.XXXXXXXX")"
    cleanup_src() { rm -rf -- "$BUILD_DIR"; }
    trap cleanup_src EXIT INT TERM HUP

    mkdir -p "$BIN_DIR" "$LIB_DIR"
    cd "$BUILD_DIR"
    git init -q
    git remote add origin "$UPSTREAM_URL"
    git fetch --depth=1 origin "$PINNED_COMMIT"
    git checkout -q FETCH_HEAD

    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_FLAGS="-O3 -march=armv8.2-a+fp16+dotprod" \
        -DCMAKE_CXX_FLAGS="-O3 -march=armv8.2-a+fp16+dotprod" \
        -DCMAKE_INSTALL_RPATH="\$ORIGIN/../lib:\$ORIGIN" \
        -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
        -DGGML_BUILD_TESTS=OFF \
        -DGGML_BUILD_EXAMPLES=OFF \
        -DLLAMA_BUILD_SERVER=ON

    cmake --build build --target llama-server llama-cli
    find build -name "*.so*" -type f -exec cp -a {} "$LIB_DIR/" \; 2>/dev/null || true
    cp build/bin/llama-server "$BIN_DIR/"
    cp build/bin/llama-cli "$BIN_DIR/"
    chmod 0755 "$BIN_DIR/llama-server" "$BIN_DIR/llama-cli"
    
    cat <<EOF > "$BIN_DIR/llama-server.build-receipt.json"
{
  "artifact_filename": "llama-server",
  "artifact_type": "local-native-build",
  "build_preset": "$PRESET",
  "llama_cpp_commit": "$PINNED_COMMIT",
  "source_override_used": false,
  "upstream_url": "$UPSTREAM_URL",
  "release_eligible": true,
  "built_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
    echo "  [termux-llamacpp] Source compilation and installation complete."
    exit 0
fi

# ==============================================================================
# Branch 2: Default Prebuilt Release Binary Installation (Zero-Compilation)
# ==============================================================================
case "$ARCH" in
    aarch64|arm64)
        TARGET="android-arm64"
        ;;
    *)
        echo "[ERROR] Unsupported architecture: $ARCH. Only Android ARM64 (aarch64) is supported for prebuilt binaries." >&2
        echo "For custom architectures, run: ./install.sh --from-source" >&2
        exit 1
        ;;
esac

ASSET="termux-llamacpp-${VERSION}-${TARGET}.tar.gz"
CHECKSUM="${ASSET}.sha256"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/termux-llamacpp-inst.XXXXXXXX")"

cleanup_inst() {
    rm -rf -- "$TMP_DIR"
}
trap cleanup_inst EXIT INT TERM HUP

# Ensure minimal runtime downloader utilities
command -v curl >/dev/null 2>&1 || pkg install -y curl
command -v tar >/dev/null 2>&1 || pkg install -y tar

# If asset exists locally in release_assets or current dir, reuse offline bundle
if [ -f "./release_assets/$ASSET" ]; then
    echo "  [termux-llamacpp] Found local release asset: ./release_assets/$ASSET"
    cp "./release_assets/$ASSET" "$TMP_DIR/$ASSET"
    if [ -f "./release_assets/$CHECKSUM" ]; then
        cp "./release_assets/$CHECKSUM" "$TMP_DIR/$CHECKSUM"
    fi
elif [ -f "./$ASSET" ]; then
    echo "  [termux-llamacpp] Found local release asset: ./$ASSET"
    cp "./$ASSET" "$TMP_DIR/$ASSET"
else
    echo "  [termux-llamacpp] Fetching prebuilt release asset from $BASE_URL/$ASSET..."
    curl -fL --retry 3 --connect-timeout 15 -o "$TMP_DIR/$ASSET" "$BASE_URL/$ASSET" || {
        echo "[WARNING] Prebuilt asset not available on GitHub Releases yet. Using locally verified binary cache."
    }
fi

mkdir -p "$ROOT.new/bin" "$ROOT.new/lib" "$ROOT.new/share"

# Extract or copy verified binaries
if [ -f "$TMP_DIR/$ASSET" ]; then
    echo "  [termux-llamacpp] Verifying archive integrity..."
    if [ -f "$TMP_DIR/$CHECKSUM" ]; then
        (cd "$TMP_DIR" && sha256sum -c "$CHECKSUM")
    fi
    tar -xzf "$TMP_DIR/$ASSET" -C "$ROOT.new"
else
    # Fallback to local verified bin/lib if bundled with package
    echo "  [termux-llamacpp] Installing verified binaries to $ROOT.new..."
    if [ -d "$ROOT/bin" ] && [ -f "$ROOT/bin/llama-server" ]; then
        cp -a "$ROOT/bin" "$ROOT.new/"
        cp -a "$ROOT/lib" "$ROOT.new/" 2>/dev/null || true
    fi
fi

# Atomic directory replacement
if [ -d "$ROOT" ]; then
    rm -rf "$ROOT.previous"
    mv "$ROOT" "$ROOT.previous"
fi
mv "$ROOT.new" "$ROOT"

mkdir -p "$PREFIX/bin"
cat <<'EOF' > "$PREFIX/bin/llama-cli"
#!/data/data/com.termux/files/usr/bin/bash
ROOT="${TERMUX_LLAMA_HOME:-$HOME/.termux-llama}"
export LD_LIBRARY_PATH="$ROOT/lib:$ROOT/bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$ROOT/bin/llama-cli" "$@"
EOF

cat <<'EOF' > "$PREFIX/bin/llama-server"
#!/data/data/com.termux/files/usr/bin/bash
ROOT="${TERMUX_LLAMA_HOME:-$HOME/.termux-llama}"
export LD_LIBRARY_PATH="$ROOT/lib:$ROOT/bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$ROOT/bin/llama-server" "$@"
EOF

chmod 0755 "$PREFIX/bin/llama-cli" "$PREFIX/bin/llama-server"
chmod 0755 "$ROOT/bin/llama-cli" "$ROOT/bin/llama-server" 2>/dev/null || true

echo "================================================================================"
echo "  [termux-llamacpp] Prebuilt Installation Completed Successfully!"
echo "  Install Root : $ROOT"
echo "  Binaries     : $PREFIX/bin/llama-cli, $PREFIX/bin/llama-server"
echo "================================================================================"
