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
    """Verify that target resolves safely to an accessible regular file."""
    try:
        resolved = path.resolve()
        if not resolved.is_file():
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
        if shutil.which("pkg"):
            try:
                import subprocess
                subprocess.run(["pkg", "install", "-y", "python-cryptography"], check=True)
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
                from cryptography.exceptions import InvalidSignature
            except Exception:
                raise SecurityVerificationError(
                    "Ed25519 cryptographic verification requires 'python-cryptography'. "
                    "Please install via: pkg install -y python-cryptography"
                ) from exc
        else:
            raise SecurityVerificationError(
                "Ed25519 cryptographic verification requires 'cryptography>=42.0.0'. "
                "Please install via: pip install cryptography or pkg install -y python-cryptography"
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

    binary_path = binary_path.resolve()
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

    # 3. Fail-Closed if neither verified signed manifest nor build receipt can be established
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
