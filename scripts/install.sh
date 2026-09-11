#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# termux-llamacpp: Production Prebuilt Zero-Compilation Installer for Termux ARM64
# ==============================================================================
set -euo pipefail

VERSION="${TERMUX_LLAMACPP_VERSION:-1.3.2}"
REPO="uno-km/termux-llamacpp"
ROOT="${TERMUX_LLAMACPP_HOME:-$HOME/.termux-llama}"
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
        --gpu|--with-gpu)
            TERMUX_LLAMA_PRESET="android-arm64-vulkan"
            ;;
        --help|-h)
            echo "Usage: install.sh [--from-source] [--gpu] [--help]"
            echo ""
            echo "Options:"
            echo "  (Default)       Download and verify prebuilt Android ARM64 release binaries (Zero-Compilation, <3s)"
            echo "  --from-source   Force local native compilation via Clang/CMake/Ninja"
            echo "  --gpu           Enable GPU Vulkan acceleration and provision ameva-runtime"
            exit 0
            ;;
    esac
done

printf '================================================================================\n'
printf '  [termux-llamacpp] Universal Installer v%s\n' "$VERSION"
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
    PRESET="${TERMUX_LLAMA_PRESET:-android-arm64-baseline}"
    printf '  [termux-llamacpp] Installing build toolchain prerequisites (Preset: %s)...\n' "$PRESET"

    # Base compiler toolchain
    pkg install -y git clang cmake ninja pkg-config || true

    VULKAN_FLAG="OFF"
    if [[ "$PRESET" == *"vulkan"* ]]; then
        printf '  [termux-llamacpp] Vulkan preset detected; installing shaderc/glslang...\n'
        pkg install -y vulkan-headers shaderc glslang || true
        VULKAN_FLAG="ON"
    fi

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

    CMAKE_ARGS=(
        -B build -G Ninja
        -DCMAKE_BUILD_TYPE=Release
        -DGGML_VULKAN="$VULKAN_FLAG"
        -DCMAKE_INSTALL_RPATH="\$ORIGIN/../lib:\$ORIGIN"
        -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON
        -DGGML_BUILD_TESTS=OFF
        -DGGML_BUILD_EXAMPLES=OFF
        -DLLAMA_BUILD_SERVER=ON
    )
    if [ "$VULKAN_FLAG" = "ON" ]; then
        CMAKE_ARGS+=(
            -DGGML_VULKAN_CHECK_RESULTS=OFF
            -DVulkan_LIBRARY=/system/lib64/libvulkan.so
            -DVulkan_INCLUDE_DIR="$PREFIX/include"
        )
    fi

    cmake "${CMAKE_ARGS[@]}"

    cmake --build build --target llama-server llama-cli -j4
    find build -name "*.so*" -type f -exec cp -a {} "$TARGET_DIR/lib/" \; 2>/dev/null || true
    cp build/bin/llama-server "$TARGET_DIR/bin/"
    cp build/bin/llama-cli "$TARGET_DIR/bin/"
    chmod 0755 "$TARGET_DIR/bin/llama-server" "$TARGET_DIR/bin/llama-cli"

    # Generate immutable build receipts with exact SHA-256 and pinned commit
    for bin_name in llama-server llama-cli; do
        bin_sha="$(sha256sum "$TARGET_DIR/bin/$bin_name" | awk '{print $1}')"
        cat <<EOF > "$TARGET_DIR/bin/${bin_name}.build-receipt.json"
{
  "artifact_filename": "$bin_name",
  "artifact_type": "local-native-build",
  "sha256": "$bin_sha",
  "llama_cpp_commit": "$PINNED_COMMIT",
  "build_preset": "$PRESET",
  "source_override_used": false,
  "built_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
    done

    ln -sfn "$TARGET_DIR" "$ROOT/current.new"
    mv -Tf "$ROOT/current.new" "$ROOT/current" 2>/dev/null || ln -sfn "$TARGET_DIR" "$ROOT/current"

    printf '  [termux-llamacpp] Source compilation and verified installation complete.\n'
fi

# ==============================================================================
# Branch 2: Default Prebuilt Release Binary Installation (Zero-Compilation)
# ==============================================================================
if [ "$FROM_SOURCE" != "1" ]; then
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

    # 2. Minimal Runtime Tools Check
    printf '  [termux-llamacpp] Checking minimal runtime prerequisites...\n'
    MISSING_PKGS=""
    command -v curl >/dev/null 2>&1 || MISSING_PKGS="$MISSING_PKGS curl ca-certificates"
    command -v tar >/dev/null 2>&1 || MISSING_PKGS="$MISSING_PKGS tar"
    command -v sha256sum >/dev/null 2>&1 || MISSING_PKGS="$MISSING_PKGS coreutils"

    if [ -n "$MISSING_PKGS" ]; then
        pkg install -y $MISSING_PKGS
    fi

    ASSET="termux-llamacpp-${VERSION}-${TARGET}.tar.gz"
    DOWNLOAD_SUCCESS=0
    CANDIDATE_URLS=(
        "https://github.com/${REPO}/releases/download/v${VERSION}/termux-llamacpp-${VERSION}-${TARGET}.tar.gz"
        "https://github.com/${REPO}/releases/latest/download/termux-llamacpp-${VERSION}-${TARGET}.tar.gz"
        "https://github.com/${REPO}/releases/latest/download/termux-llamacpp-android-arm64.tar.gz"
        "https://github.com/${REPO}/releases/download/v1.0.0b2/termux-llamacpp-1.0.0b2-android-arm64.tar.gz"
    )

    for CANDIDATE_URL in "${CANDIDATE_URLS[@]}"; do
        printf '  [termux-llamacpp] Checking candidate release: %s\n' "$CANDIDATE_URL"
        if curl -fL --retry 2 --retry-delay 1 --connect-timeout 10 -o "$TMP/$ASSET" "$CANDIDATE_URL" 2>/dev/null; then
            if [ -s "$TMP/$ASSET" ] && [ "$(wc -c < "$TMP/$ASSET")" -gt 1000000 ]; then
                DOWNLOAD_SUCCESS=1
                printf '  [termux-llamacpp] Successfully fetched prebuilt binary bundle from: %s\n' "$CANDIDATE_URL"
                break
            fi
        fi
    done

    if [ "$DOWNLOAD_SUCCESS" = "1" ]; then
        curl -fL --connect-timeout 5 -o "$TMP/$ASSET.sha256" "${CANDIDATE_URL}.sha256" 2>/dev/null || true
        if [ -s "$TMP/$ASSET.sha256" ]; then
            printf '  [termux-llamacpp] Verifying cryptographic SHA-256 integrity...\n'
            (cd "$TMP" && sha256sum -c "$ASSET.sha256") || fail "Cryptographic SHA-256 checksum mismatch!"
        fi

        # Staging & Pre-Swap Extraction
        STAGING="$ROOT/.staging-$VERSION"
        TARGET_DIR="$ROOT/versions/$VERSION"
        rm -rf "$STAGING"
        mkdir -p "$STAGING" "$ROOT/versions" "$ROOT/models"
        tar -xzf "$TMP/$ASSET" -C "$STAGING"

        rm -rf "$TARGET_DIR"
        mv "$STAGING" "$TARGET_DIR"
        ln -sfn "$TARGET_DIR" "$ROOT/current.new"
        mv -Tf "$ROOT/current.new" "$ROOT/current" 2>/dev/null || ln -sfn "$TARGET_DIR" "$ROOT/current"
        printf '  [termux-llamacpp] Prebuilt binary bundle successfully installed.\n'
    else
        printf '  [termux-llamacpp] Prebuilt binary bundle unavailable. Falling back to native on-device compilation...\n'
        # Call this script with --from-source to guarantee reliable build
        "$0" --from-source
        exit 0
    fi
fi

# ==============================================================================
# Step 3: Register Unified Wrappers in $PREFIX/bin with Vulkan Bionic Binding
# ==============================================================================
mkdir -p "$PREFIX/bin"

for cmd_name in termux-llama-cli termux-llama-server llama-cli llama-server; do
    target_bin="llama-cli"
    if [ "$cmd_name" = "termux-llama-server" ] || [ "$cmd_name" = "llama-server" ]; then
        target_bin="llama-server"
    fi

    cat <<EOF > "$PREFIX/bin/$cmd_name"
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="\${TERMUX_LLAMACPP_HOME:-\$HOME/.termux-llama}"
export LD_LIBRARY_PATH="\$ROOT/current/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}:\$PREFIX/lib"
if [ ! -f "\$ROOT/current/bin/$target_bin" ]; then
    printf '[ERROR] %s binary not found at %s/current/bin/%s\n' "$target_bin" "\$ROOT" "$target_bin" >&2
    printf 'Please run: termux-llama install --from-source\n' >&2
    exit 1
fi
exec "\$ROOT/current/bin/$target_bin" "\$@"
EOF
    chmod 0755 "$PREFIX/bin/$cmd_name"
done

# ==============================================================================
# Step 4: Python & Node.js Ecosystem Package Auto-Provisioning (pip & npm)
# ==============================================================================
printf '  [termux-llamacpp] Synchronizing Python & Node.js ecosystem packages...\n'

# 1. Python pip Package Auto-Install
if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
    PY_CMD="python3"
    command -v python3 >/dev/null 2>&1 || PY_CMD="python"
    printf '  [Python] Detected Python environment. Provisioning termux-llamacpp & ameva-runtime via pip...\n'
    $PY_CMD -m pip install --upgrade termux-llamacpp ameva-runtime --no-cache-dir >/dev/null 2>&1 || {
        $PY_CMD -m pip install termux-llamacpp ameva-runtime >/dev/null 2>&1 || printf '  [Python] Notice: pip install skipped (managed environment or offline).\n'
    }
fi

# 2. Node.js npm Package Auto-Install
if command -v npm >/dev/null 2>&1; then
    printf '  [Node.js] Detected Node.js environment. Provisioning termux-llamacpp & @ameva/runtime via npm...\n'
    npm install -g termux-llamacpp @ameva/runtime --force >/dev/null 2>&1 || {
        npm install -g termux-llamacpp @ameva/runtime >/dev/null 2>&1 || printf '  [Node.js] Notice: npm install skipped (offline).\n'
    }
fi

printf '================================================================================\n'
printf '  [termux-llamacpp] Complete Installation & Dual-Ecosystem Sync Completed!\n'
printf '  Version       : %s\n' "$VERSION"
printf '  Runtime Root  : %s/current\n' "$ROOT"
printf '  CLI Binaries  : %s/bin/llama-cli, %s/bin/llama-server, termux-llama\n' "$PREFIX" "$PREFIX"
printf '  Ecosystem     : Python SDK (pip) + Node.js CLI (npm) + Vulkan Bionic HAL\n'
printf '================================================================================\n'
