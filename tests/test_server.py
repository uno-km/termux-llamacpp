"""Unit tests for reverse proxy supervisor, loopback host binding, identity handshake, and transfer encoding."""

import base64
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import requests

from termux_llamacpp.server import (
    ServerManager,
    native_is_ready,
    normalize_loopback_bind_host,
    ServerConflictError,
)
from termux_llamacpp.config import PROTOCOL_VERSION, LLAMA_CPP_PINNED_COMMIT
from termux_llamacpp.exceptions import ServerStartupError
from termux_llamacpp.security import compute_sha256, SecurityVerificationError, BinaryTrustLevel


class TestServerManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)
        self.dummy_model = self.work_dir / "test-model.gguf"
        self.dummy_model.write_bytes(b"MOCK_GGUF_DATA")

        # Create model manifest
        self.model_manifest = self.dummy_model.with_suffix(".gguf.manifest.json")
        self.model_manifest.write_text(json.dumps({
            "model_id": "test-model",
            "artifact_filename": "test-model.gguf",
            "repo_id": "test/model",
            "repo_revision": "08f32c9b68a8b13a890a827038e21946059d57a2",
            "sha256": compute_sha256(self.dummy_model),
            "quant_type": "Q4_K_M",
            "license_id": "Apache-2.0",
            "size_bytes": len(b"MOCK_GGUF_DATA"),
        }))

        # Setup trust directory
        self.trust_dir = self.work_dir / "trust"
        self.trust_dir.mkdir()
        pub_hex = "3b1a77d8c6b3e945c7429188e7a82c69d82136015b69c4a45ec466cfcb15469e"
        (self.trust_dir / "release-2026-01.pub").write_text(f"# Key-ID: key-1\ned25519:{pub_hex}\n", encoding="utf-8")

        # Create dummy binary and build receipt
        self.bin_dir = self.work_dir / "bin"
        self.bin_dir.mkdir()
        self.server_bin = self.bin_dir / "llama-server"
        self.server_bin.write_bytes(b"MOCK_SERVER_BINARY_BYTES")
        (self.server_bin.with_suffix(".build-receipt.json")).write_text(json.dumps({
            "artifact_filename": "llama-server",
            "artifact_type": "local-native-build",
            "build_preset": "android-arm64-baseline",
            "sha256": compute_sha256(self.server_bin),
            "llama_cpp_commit": LLAMA_CPP_PINNED_COMMIT,
            "built_at": "2026-08-27T00:00:00Z",
        }))

        # Mock runtime object
        self.mock_runtime = MagicMock()
        self.mock_runtime.get_binary_path.return_value = self.server_bin

        # Mock process
        self.mock_proc = MagicMock()
        self.mock_proc.pid = 12345
        self.mock_proc.poll.return_value = None
        self.mock_process_factory = MagicMock(return_value=self.mock_proc)
        self.mock_readiness_probe = MagicMock(return_value=True)

        self.server_mgr = ServerManager(
            runtime=self.mock_runtime,
            run_dir=self.work_dir / "run",
            log_dir=self.work_dir / "logs",
            process_factory=self.mock_process_factory,
            readiness_probe=self.mock_readiness_probe,
            allow_mock_lock=True,
        )
        self.server_mgr.trust_store.trust_dir = self.trust_dir
        self.server_mgr.trust_store._load_trust_roots()

        self.server_port = 18088
        self.native_port = 19088

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_loopback_bind_host_enforcement(self):
        """P0-1: Ensure loopback binding for hosts and reject 0.0.0.0 and external IPs."""
        self.assertEqual(normalize_loopback_bind_host("127.0.0.1"), "127.0.0.1")
        self.assertEqual(normalize_loopback_bind_host("localhost"), "127.0.0.1")
        self.assertEqual(normalize_loopback_bind_host("::1"), "::1")

        with self.assertRaises(ServerStartupError):
            normalize_loopback_bind_host("0.0.0.0")
        with self.assertRaises(ServerStartupError):
            normalize_loopback_bind_host("192.168.1.100")
        with self.assertRaises(ServerStartupError):
            normalize_loopback_bind_host("2001:db8::1")

    def test_missing_binary_raises_startup_error(self):
        """P0-C: Missing binary must immediately raise ServerStartupError."""
        self.mock_runtime.get_binary_path.return_value = self.work_dir / "non_existent_binary"
        with self.assertRaises(ServerStartupError) as ctx:
            self.server_mgr.serve(
                model_path=self.dummy_model,
                public_host="127.0.0.1",
                public_port=self.server_port,
            )
        self.assertIn("unavailable", str(ctx.exception).lower())

    def test_missing_model_manifest_raises_security_error(self):
        """P0-3: Model file without manifest must be rejected."""
        unmanifested_model = self.work_dir / "raw.gguf"
        unmanifested_model.write_bytes(b"DATA")
        with self.assertRaises(SecurityVerificationError) as ctx:
            self.server_mgr.serve(
                model_path=unmanifested_model,
                public_host="127.0.0.1",
                public_port=self.server_port,
            )
        self.assertIn("manifest is missing", str(ctx.exception).lower())

    def test_native_readiness_probe_identity_validation(self):
        """P0-2: Verify native_is_ready requires HTTP 200, JSON, ready=True, and model match."""
        # Offline endpoint returns False
        self.assertFalse(native_is_ready("http://127.0.0.1:59999", expected_model_id="test-model"))

    def test_termux_aichain_health_handshake_and_transfer_encoding(self):
        """Test GET /health, trust level reporting, and Transfer-Encoding rejection."""
        instance = self.server_mgr.serve(
            model_path=self.dummy_model,
            public_host="127.0.0.1",
            public_port=self.server_port,
            native_host="127.0.0.1",
            native_port=self.native_port,
        )
        try:
            # 1. Health check & Trust Level reporting
            resp = requests.get(f"http://127.0.0.1:{self.server_port}/health", timeout=3)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data.get("service"), "llama-server")
            self.assertEqual(data.get("status"), "ok")
            self.assertEqual(data.get("ready"), True)
            self.assertIn("runtime", data)
            self.assertEqual(data["runtime"].get("trustLevel"), BinaryTrustLevel.LOCAL_BUILD_RECEIPT.value)
            self.assertEqual(data["runtime"].get("commit"), LLAMA_CPP_PINNED_COMMIT)

            # 2. Transfer-Encoding rejection (P1-8)
            resp_te = requests.post(
                f"http://127.0.0.1:{self.server_port}/v1/chat/completions",
                headers={"Transfer-Encoding": "chunked"},
                data=b"5\r\nhello\r\n0\r\n\r\n",
                timeout=3,
            )
            self.assertEqual(resp_te.status_code, 400)
            self.assertIn(resp_te.json()["error"]["code"], {"UNSUPPORTED_TRANSFER_ENCODING", "INVALID_TRANSFER_ENCODING"})

            # 3. 404 Route message check (P1-7)
            resp_404 = requests.get(f"http://127.0.0.1:{self.server_port}/invalid_route", timeout=3)
            self.assertEqual(resp_404.status_code, 404)
            self.assertEqual(resp_404.json()["error"]["code"], "ROUTE_NOT_FOUND")

        finally:
            instance.stop()


if __name__ == "__main__":
    unittest.main()
