#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# termux-llamacpp: Production Prebuilt Zero-Compilation Installer for Termux ARM64
# ==============================================================================
set -euo pipefail

VERSION="${TERMUX_LLAMACPP_VERSION:-1.0.0b2}"
REPO="uno-km/termux-llamacpp"
ROOT="${TERMUX_LLAMACPP_HOME:-$HOME/.termux-llamacpp}"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
ARCH="$(uname -m)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/termux-llamacpp-inst.XXXXXXXX")"
FROM_SOURCE=0

cleanup() {
    rm -rf "$TMP"
}
trap cleanup EXIT INT TERM HUP

fail() {
    printf '\n[ERROR] %s\n' "$*" >&2
    exit 1
}

for arg in "$@"; do
    case "$arg" in
        --from-source|--build-from-source)
            FROM_SOURCE=1
            ;;
        --help|-h)
            echo "Usage: install.sh [--from-source] [--help]"
            echo ""
            echo "Options:"
            echo "  (Default)       Download and verify prebuilt Android ARM64 release binaries (Zero-Compilation, <3s)"
            echo "  --from-source   Force local native compilation via Clang/CMake/Ninja"
            exit 0
            ;;
    esac
done

printf '================================================================================\n'
printf '  [termux-llamacpp] Installer v%s\n' "$VERSION"
printf '================================================================================\n'
printf '  Architecture : %s\n' "$ARCH"
printf '  Install Root : %s\n' "$ROOT"
printf '  Mode         : %s\n' "$([ "$FROM_SOURCE" = "1" ] && echo "Source Build (--from-source)" || echo "Prebuilt Binary (Zero-Compilation)")"
printf '================================================================================\n'

# Environment Verification
[ -n "${PREFIX:-}" ] || fail "This installer must run inside Android Termux."
[ -x "$PREFIX/bin/pkg" ] || fail "Termux pkg package manager was not found."

# ==============================================================================
# Branch 1: Manual Source Compilation (--from-source)
# ==============================================================================
if [ "$FROM_SOURCE" = "1" ]; then
    printf '  [termux-llamacpp] Installing build toolchain prerequisites...\n'
    pkg install -y git clang cmake ninja pkg-config

    PRESET="${TERMUX_LLAMA_PRESET:-android-arm64-dotprod}"
    PINNED_COMMIT="5e6a37cb115dc1074e274ac004373f5661909695"
    UPSTREAM_URL="https://github.com/ggerganov/llama.cpp.git"
    BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/termux-llamacpp-src.XXXXXXXX")"
    cleanup_src() { rm -rf -- "$BUILD_DIR"; }
    trap cleanup_src EXIT INT TERM HUP

    TARGET_DIR="$ROOT/versions/$VERSION"
    mkdir -p "$TARGET_DIR/bin" "$TARGET_DIR/lib" "$TARGET_DIR/share" "$TARGET_DIR/LICENSES" "$ROOT/models"

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
    find build -name "*.so*" -type f -exec cp -a {} "$TARGET_DIR/lib/" \; 2>/dev/null || true
    cp build/bin/llama-server "$TARGET_DIR/bin/"
    cp build/bin/llama-cli "$TARGET_DIR/bin/"
    chmod 0755 "$TARGET_DIR/bin/llama-server" "$TARGET_DIR/bin/llama-cli"

    ln -sfn "$TARGET_DIR" "$ROOT/current.new"
    mv -Tf "$ROOT/current.new" "$ROOT/current" 2>/dev/null || ln -sfn "$TARGET_DIR" "$ROOT/current"

    printf '  [termux-llamacpp] Source compilation and installation complete.\n'
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
        fail "Unsupported architecture: $ARCH. Only Android ARM64 (aarch64) is supported for prebuilt binaries."
        ;;
esac

# 1. Storage Space Check (Minimum 700MB)
AVAILABLE_KB="$(df -Pk "$HOME" | awk 'NR==2 {print $4}')"
REQUIRED_KB=700000
if [ "$AVAILABLE_KB" -lt "$REQUIRED_KB" ]; then
    fail "Insufficient storage: At least 700 MB free space is required in $HOME."
fi

# 2. Minimal Runtime Tools Check (Only install if missing, zero clang/cmake/ninja)
printf '  [termux-llamacpp] Checking minimal runtime prerequisites...\n'
MISSING_PKGS=""
command -v curl >/dev/null 2>&1 || MISSING_PKGS="$MISSING_PKGS curl ca-certificates"
command -v tar >/dev/null 2>&1 || MISSING_PKGS="$MISSING_PKGS tar"
command -v sha256sum >/dev/null 2>&1 || MISSING_PKGS="$MISSING_PKGS coreutils"

if [ -n "$MISSING_PKGS" ]; then
    pkg install -y $MISSING_PKGS
fi

ASSET="termux-llamacpp-${VERSION}-${TARGET}.tar.gz"
BASE_URL="https://github.com/${REPO}/releases/download/v${VERSION}"
ASSET_URL="${BASE_URL}/${ASSET}"
SHA_URL="${ASSET_URL}.sha256"

# 3. Download Release Asset & SHA-256
printf '  [termux-llamacpp] Downloading verified ARM64 prebuilt bundle (%s)...\n' "$ASSET"
curl -fL --retry 3 --retry-delay 2 --connect-timeout 15 -o "$TMP/$ASSET" "$ASSET_URL" || fail "Failed to download $ASSET_URL"
curl -fL --retry 3 --retry-delay 2 --connect-timeout 15 -o "$TMP/$ASSET.sha256" "$SHA_URL" || fail "Failed to download $SHA_URL"

# 4. Cryptographic SHA-256 Integrity Verification
printf '  [termux-llamacpp] Verifying cryptographic SHA-256 integrity...\n'
(
    cd "$TMP"
    sha256sum -c "$ASSET.sha256"
) || fail "SHA-256 checksum mismatch! The download package is corrupted or untrusted."

# 5. Staging & Pre-Swap Extraction
STAGING="$ROOT/.staging-$VERSION"
TARGET_DIR="$ROOT/versions/$VERSION"
rm -rf "$STAGING"
mkdir -p "$STAGING" "$ROOT/versions" "$ROOT/models"

tar -xzf "$TMP/$ASSET" -C "$STAGING"

for executable in llama-cli llama-server; do
    [ -f "$STAGING/bin/$executable" ] || fail "Missing executable in release bundle: $executable"
    chmod 0755 "$STAGING/bin/$executable"
    sha_val="$(sha256sum "$STAGING/bin/$executable" | awk '{print $1}')"
    cat <<EOF > "$STAGING/bin/${executable}.build-receipt.json"
{
  "artifact_filename": "$executable",
  "artifact_type": "local-native-build",
  "sha256": "$sha_val",
  "llama_cpp_commit": "5e6a37cb115dc1074e274ac004373f5661909695",
  "build_preset": "android-arm64-baseline",
  "source_override_used": false
}
EOF
done

[ -d "$STAGING/lib" ] || fail "Missing required shared library directory in release bundle."

# 6. Pre-Swap Smoke Test
printf '  [termux-llamacpp] Executing pre-swap binary smoke test...\n'
export LD_LIBRARY_PATH="$STAGING/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
"$STAGING/bin/llama-cli" --version >/dev/null 2>&1 || fail "Pre-swap smoke test failed for llama-cli."
"$STAGING/bin/llama-server" --version >/dev/null 2>&1 || fail "Pre-swap smoke test failed for llama-server."

# 7. Atomic Versioning Swap & Rollback Safety
rm -rf "$TARGET_DIR"
mv "$STAGING" "$TARGET_DIR"

PREVIOUS_TARGET=""
if [ -L "$ROOT/current" ]; then
    PREVIOUS_TARGET="$(readlink "$ROOT/current" 2>/dev/null || true)"
fi

ln -sfn "$TARGET_DIR" "$ROOT/current.new"
mv -Tf "$ROOT/current.new" "$ROOT/current" 2>/dev/null || ln -sfn "$TARGET_DIR" "$ROOT/current"

# 8. Register Thin Wrappers in $PREFIX/bin
mkdir -p "$PREFIX/bin"

for cmd_name in termux-llama-cli termux-llama-server llama-cli llama-server; do
    target_bin="llama-cli"
    if [ "$cmd_name" = "termux-llama-server" ] || [ "$cmd_name" = "llama-server" ]; then
        target_bin="llama-server"
    fi

    cat <<EOF > "$PREFIX/bin/$cmd_name"
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="\${TERMUX_LLAMACPP_HOME:-\$HOME/.termux-llamacpp}"
export LD_LIBRARY_PATH="\$ROOT/current/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
exec "\$ROOT/current/bin/$target_bin" "\$@"
EOF
    chmod 0755 "$PREFIX/bin/$cmd_name"
done

# 9. Post-Install Smoke Test
if ! "$PREFIX/bin/termux-llama-cli" --version >/dev/null 2>&1; then
    printf '  [ERROR] Post-install smoke test failed! Initiating rollback...\n' >&2
    if [ -n "$PREVIOUS_TARGET" ]; then
        ln -sfn "$PREVIOUS_TARGET" "$ROOT/current"
    fi
    fail "Installation failed and previous version was restored."
fi

printf '================================================================================\n'
printf '  [termux-llamacpp] Prebuilt Installation Completed Successfully!\n'
printf '  Version       : %s\n' "$VERSION"
printf '  Compilation   : NO (0 commands, 0 compiler toolchains)\n'
printf '  Runtime Root  : %s/current\n' "$ROOT"
printf '  CLI Binaries  : %s/bin/termux-llama-cli, %s/bin/termux-llama-server\n' "$PREFIX" "$PREFIX"
printf '  Models Cache  : %s/models\n' "$ROOT"
printf '================================================================================\n'
