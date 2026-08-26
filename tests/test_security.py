"""Unit tests for fail-closed security, Ed25519 verification, atomic rollback, model provenance, and build receipts."""

import base64
import json
import tempfile
import unittest
from pathlib import Path

from termux_llamacpp.security import (
    canonicalize_json,
    compute_sha256,
    verify_binary_integrity,
    verify_ed25519_signature,
    atomic_replace_verified,
    build_model_manifest_payload,
    save_signed_model_manifest,
    TrustStore,
    verify_manifest_and_binary,
    verify_binary_pre_execution,
    verify_model_pre_execution,
    normalize_loopback_origin,
    SecurityVerificationError,
    BinaryTrustLevel,
)
from termux_llamacpp.config import LLAMA_CPP_PINNED_COMMIT


class TestSecurityAndManifest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

        # Setup trust directory with valid key
        self.trust_dir = self.work_dir / "trust"
        self.trust_dir.mkdir()
        self.pub_key_hex = "3b1a77d8c6b3e945c7429188e7a82c69d82136015b69c4a45ec466cfcb15469e"
        (self.trust_dir / "release-2026-01.pub").write_text(
            f"# Key-ID: release-key-1\ned25519:{self.pub_key_hex}\n", encoding="utf-8"
        )
        (self.trust_dir / "revoked-keys.json").write_text(
            json.dumps({"revoked_key_ids": ["revoked-key-id"]}), encoding="utf-8"
        )
        self.trust_store = TrustStore(trust_dir=self.trust_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_canonicalize_json(self):
        """Verify deterministic JSON canonicalization."""
        data = {"z_key": 1, "a_key": "test", "nested": {"b": True, "a": False}}
        canon = canonicalize_json(data)
        expected = b'{"a_key":"test","nested":{"a":false,"b":true},"z_key":1}'
        self.assertEqual(canon, expected)

    def test_ed25519_fail_closed_validation(self):
        """Verify that invalid keys, lengths, or corrupted signatures return False (NO FAIL-OPEN)."""
        valid_length_key = "00" * 32
        valid_length_sig = base64.b64encode(b"0" * 64).decode("utf-8")

        self.assertFalse(verify_ed25519_signature("00" * 16, b"test", valid_length_sig))
        self.assertFalse(verify_ed25519_signature(valid_length_key, b"test", base64.b64encode(b"0"*32).decode("utf-8")))
        self.assertFalse(verify_ed25519_signature(valid_length_key, b"test", "!!!not-base64!!!"))
        self.assertFalse(verify_ed25519_signature(valid_length_key, b"test", valid_length_sig))

    def test_trust_store_fail_closed_on_corrupted_files(self):
        """Test TrustStore fail-closed behavior on corrupted revocation or invalid schema."""
        bad_dir = self.work_dir / "bad_trust"
        bad_dir.mkdir()
        (bad_dir / "release.pub").write_text("# Key-ID: k1\ned25519:" + "00"*32 + "\n")

        (bad_dir / "revoked-keys.json").write_text(json.dumps({"revoked_key_ids": "not-a-list"}))
        with self.assertRaises(SecurityVerificationError):
            TrustStore(trust_dir=bad_dir)

        bad_dir_2 = self.work_dir / "bad_trust_2"
        bad_dir_2.mkdir()
        (bad_dir_2 / "release.pub").write_text("# Key-ID: k1\n# No ed25519 key here\n")
        with self.assertRaises(SecurityVerificationError):
            TrustStore(trust_dir=bad_dir_2)

    def test_atomic_replace_rollback_preserves_destination_on_failure(self):
        """Test that failure during post-install verification restores original destination."""
        dest_file = self.work_dir / "original.bin"
        dest_file.write_bytes(b"ORIGINAL_VERIFIED_CONTENT")
        original_sha = compute_sha256(dest_file)

        corrupted_stage = self.work_dir / "bad.stage"
        corrupted_stage.write_bytes(b"CORRUPTED_BYTES")

        with self.assertRaises(SecurityVerificationError):
            atomic_replace_verified(
                staged_file=corrupted_stage,
                destination=dest_file,
                expected_sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            )

        self.assertTrue(dest_file.is_file())
        self.assertEqual(dest_file.read_bytes(), b"ORIGINAL_VERIFIED_CONTENT")
        self.assertEqual(compute_sha256(dest_file), original_sha)

    def test_pre_execution_requires_manifest_or_build_receipt(self):
        """Binary without .manifest.json or .build-receipt.json must fail."""
        bin_path = self.work_dir / "llama-server"
        bin_path.write_bytes(b"RAW_BINARY_WITHOUT_PROVENANCE")

        with self.assertRaises(SecurityVerificationError) as ctx:
            verify_binary_pre_execution(bin_path, self.trust_store)
        self.assertIn("untrusted binary", str(ctx.exception).lower())

    def test_local_build_receipt_accepts_matching_binary(self):
        """Test that verified local build receipt validates binary integrity and returns LOCAL_BUILD_RECEIPT."""
        bin_path = self.work_dir / "llama-server"
        bin_path.write_bytes(b"LOCAL_COMPILED_BINARY_BYTES")

        receipt_path = bin_path.with_suffix(".build-receipt.json")
        receipt_path.write_text(json.dumps({
            "artifact_filename": "llama-server",
            "artifact_type": "local-native-build",
            "build_preset": "android-arm64-baseline",
            "sha256": compute_sha256(bin_path),
            "llama_cpp_commit": LLAMA_CPP_PINNED_COMMIT,
            "built_at": "2026-08-27T00:00:00Z",
        }))

        res = verify_binary_pre_execution(bin_path, self.trust_store)
        self.assertEqual(res.trust_level, BinaryTrustLevel.LOCAL_BUILD_RECEIPT)
        self.assertEqual(res.sha256, compute_sha256(bin_path))

    def test_development_receipt_denied_by_default(self):
        """P0-1: development-local-build receipt must be denied by default execution policy."""
        bin_path = self.work_dir / "llama-server"
        bin_path.write_bytes(b"DEV_BINARY_BYTES")

        receipt_path = bin_path.with_suffix(".build-receipt.json")
        receipt_path.write_text(json.dumps({
            "artifact_filename": "llama-server",
            "artifact_type": "development-local-build",
            "build_preset": "android-arm64-baseline",
            "sha256": compute_sha256(bin_path),
            "llama_cpp_commit": "1111222233334444555566667777888899990000",
            "source_override_used": True,
            "upstream_url": "https://github.com/custom/llama.cpp.git",
            "release_eligible": False,
            "built_at": "2026-08-27T00:00:00Z",
        }))

        with self.assertRaises(SecurityVerificationError) as ctx:
            verify_binary_pre_execution(bin_path, self.trust_store, allow_development_build=False)
        self.assertIn("development build receipt", str(ctx.exception).lower())

    def test_development_receipt_allowed_with_explicit_policy(self):
        """P0-1: development-local-build receipt is accepted when allow_development_build=True."""
        bin_path = self.work_dir / "llama-server"
        bin_path.write_bytes(b"DEV_BINARY_BYTES")

        dev_commit = "1111222233334444555566667777888899990000"
        receipt_path = bin_path.with_suffix(".build-receipt.json")
        receipt_path.write_text(json.dumps({
            "artifact_filename": "llama-server",
            "artifact_type": "development-local-build",
            "build_preset": "android-arm64-baseline",
            "sha256": compute_sha256(bin_path),
            "llama_cpp_commit": dev_commit,
            "source_override_used": True,
            "upstream_url": "https://github.com/custom/llama.cpp.git",
            "release_eligible": False,
            "built_at": "2026-08-27T00:00:00Z",
        }))

        res = verify_binary_pre_execution(bin_path, self.trust_store, allow_development_build=True)
        self.assertEqual(res.trust_level, BinaryTrustLevel.DEVELOPMENT_BUILD)
        self.assertEqual(res.llama_cpp_commit, dev_commit)
        self.assertTrue(res.source_override_used)

    def test_unknown_receipt_artifact_type_rejected(self):
        """Build receipt with unknown artifact_type must be rejected."""
        bin_path = self.work_dir / "llama-server"
        bin_path.write_bytes(b"BYTES")

        receipt_path = bin_path.with_suffix(".build-receipt.json")
        receipt_path.write_text(json.dumps({
            "artifact_filename": "llama-server",
            "artifact_type": "untrusted-random-type",
            "build_preset": "android-arm64-baseline",
            "sha256": compute_sha256(bin_path),
            "llama_cpp_commit": LLAMA_CPP_PINNED_COMMIT,
            "built_at": "2026-08-27T00:00:00Z",
        }))

        with self.assertRaises(SecurityVerificationError) as ctx:
            verify_binary_pre_execution(bin_path, self.trust_store)
        self.assertIn("unsupported build receipt artifact_type", str(ctx.exception).lower())

    def test_local_build_binary_tampering_rejected(self):
        """Tampering with binary after receipt generation must be rejected."""
        bin_path = self.work_dir / "llama-server"
        bin_path.write_bytes(b"INITIAL_BYTES")

        receipt_path = bin_path.with_suffix(".build-receipt.json")
        receipt_path.write_text(json.dumps({
            "artifact_filename": "llama-server",
            "artifact_type": "local-native-build",
            "build_preset": "android-arm64-baseline",
            "sha256": compute_sha256(bin_path),
            "llama_cpp_commit": LLAMA_CPP_PINNED_COMMIT,
            "built_at": "2026-08-27T00:00:00Z",
        }))

        # Tampering
        bin_path.write_bytes(b"TAMPERED_MALICIOUS_BYTES")
        with self.assertRaises(SecurityVerificationError) as ctx:
            verify_binary_pre_execution(bin_path, self.trust_store)
        self.assertIn("post-build modification detected", str(ctx.exception).lower())

    def test_local_build_receipt_commit_mismatch_rejected(self):
        """Receipt referencing unexpected commit SHA must be rejected."""
        bin_path = self.work_dir / "llama-server"
        bin_path.write_bytes(b"BYTES")

        receipt_path = bin_path.with_suffix(".build-receipt.json")
        receipt_path.write_text(json.dumps({
            "artifact_filename": "llama-server",
            "artifact_type": "local-native-build",
            "build_preset": "android-arm64-baseline",
            "sha256": compute_sha256(bin_path),
            "llama_cpp_commit": "1111111111111111111111111111111111111111",
            "built_at": "2026-08-27T00:00:00Z",
        }))

        with self.assertRaises(SecurityVerificationError) as ctx:
            verify_binary_pre_execution(bin_path, self.trust_store)
        self.assertIn("commit mismatch", str(ctx.exception).lower())

    def test_invalid_signed_manifest_never_downgrades_to_receipt(self):
        """ANTI-DOWNGRADE: Corrupted signed manifest must fail even if a valid receipt is also present."""
        bin_path = self.work_dir / "llama-server"
        bin_path.write_bytes(b"BYTES")

        # 1. Invalid signed manifest
        manifest_path = bin_path.with_suffix(".manifest.json")
        manifest_path.write_text(json.dumps({
            "key_id": "release-key-1",
            "signature": base64.b64encode(b"invalid_sig"*5).decode("utf-8"),
            "sha256": compute_sha256(bin_path),
            "llama_cpp_commit": LLAMA_CPP_PINNED_COMMIT,
            "artifact_filename": "llama-server",
        }))

        # 2. Also present valid receipt
        receipt_path = bin_path.with_suffix(".build-receipt.json")
        receipt_path.write_text(json.dumps({
            "artifact_filename": "llama-server",
            "artifact_type": "local-native-build",
            "build_preset": "android-arm64-baseline",
            "sha256": compute_sha256(bin_path),
            "llama_cpp_commit": LLAMA_CPP_PINNED_COMMIT,
            "built_at": "2026-08-27T00:00:00Z",
        }))

        with self.assertRaises(SecurityVerificationError) as ctx:
            verify_binary_pre_execution(bin_path, self.trust_store)
        self.assertIn("signature is invalid", str(ctx.exception).lower())

    def test_verify_manifest_and_binary_commit_mismatch_rejected(self):
        """P1-1: verify_manifest_and_binary must reject commit mismatch against LLAMA_CPP_PINNED_COMMIT."""
        stage_bin = self.work_dir / "stage.bin"
        stage_bin.write_bytes(b"BIN_BYTES")
        target_bin = self.work_dir / "llama-server"

        manifest = {
            "key_id": "release-key-1",
            "signature": base64.b64encode(b"0"*64).decode("utf-8"),
            "sha256": compute_sha256(stage_bin),
            "llama_cpp_commit": "ffffffffffffffffffffffffffffffffffffffff",  # Mismatched commit
            "artifact_filename": "llama-server",
        }

        with self.assertRaises(SecurityVerificationError) as ctx:
            verify_manifest_and_binary(manifest, stage_bin, target_bin, self.trust_store)
        self.assertIn("commit mismatch", str(ctx.exception).lower())

    def test_binary_manifest_non_string_sha_rejected_cleanly(self):
        """Non-string fields in binary manifest must raise SecurityVerificationError without TypeError."""
        bin_path = self.work_dir / "llama-server"
        bin_path.write_bytes(b"BYTES")

        manifest_path = bin_path.with_suffix(".manifest.json")
        manifest_path.write_text(json.dumps({
            "key_id": "release-key-1",
            "signature": base64.b64encode(b"0"*64).decode("utf-8"),
            "sha256": 12345,  # Non-string integer
            "llama_cpp_commit": LLAMA_CPP_PINNED_COMMIT,
            "artifact_filename": "llama-server",
        }))

        with self.assertRaises(SecurityVerificationError) as ctx:
            verify_binary_pre_execution(bin_path, self.trust_store)
        self.assertIn("must be a non-empty string", str(ctx.exception))

    def test_save_signed_model_manifest_with_invalid_sig_rejected(self):
        """P0-2: Verify save_signed_model_manifest validates signature against trust store before saving."""
        model_path = self.work_dir / "m.gguf"
        payload = build_model_manifest_payload(
            model_path=model_path,
            model_id="m",
            repo_id="repo",
            revision="rev",
            sha256="ffff"*16,
            quant_type="Q4_K_M",
            license_id="Apache-2.0",
            size_bytes=100,
        )

        with self.assertRaises(SecurityVerificationError):
            save_signed_model_manifest(
                model_path=model_path,
                payload=payload,
                key_id="release-key-1",
                signature=base64.b64encode(b"fake_signature"*4).decode("utf-8"),
                trust_store=self.trust_store,
            )

    def test_digest_chain_is_valid_json(self):
        """Verify that artifacts/digest-chain.json is valid JSON with proper schema."""
        chain_path = Path("artifacts/digest-chain.json")
        self.assertTrue(chain_path.is_file())
        data = json.loads(chain_path.read_text(encoding="utf-8"))
        self.assertIn("llama_cpp_upstream_commit_pinned", data)
        self.assertEqual(data["llama_cpp_upstream_commit_pinned"], LLAMA_CPP_PINNED_COMMIT)

    def test_cors_loopback_origin_and_prefix_bypass_rejection(self):
        """P0-D: Ensure strict loopback origin validation and reject prefix bypasses."""
        self.assertEqual(normalize_loopback_origin("http://localhost"), "http://localhost")
        self.assertEqual(normalize_loopback_origin("http://localhost:8080"), "http://localhost:8080")
        self.assertEqual(normalize_loopback_origin("http://127.0.0.1:3000"), "http://127.0.0.1:3000")
        self.assertEqual(normalize_loopback_origin("http://[::1]:8080"), "http://[::1]:8080")

        self.assertIsNone(normalize_loopback_origin("http://localhost.evil.example"))
        self.assertIsNone(normalize_loopback_origin("http://localhost.attacker.com"))
        self.assertIsNone(normalize_loopback_origin("http://127.0.0.1.evil.example"))
        self.assertIsNone(normalize_loopback_origin("http://127.0.0.1.attacker.com"))
        self.assertIsNone(normalize_loopback_origin("https://evil-site.com"))
        self.assertIsNone(normalize_loopback_origin(""))


if __name__ == "__main__":
    unittest.main()
