"""Production-Grade Process Supervisor, Reverse Proxy Adapter (:8080 <-> :18080), OS fcntl File Lock, and Bounded Logger."""

import ipaddress
import json
import os
import signal
import subprocess
import sys
import time
import uuid
import hmac
import urllib.request
import urllib.error
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional, Union, Dict, Any, List, Callable
import threading

import requests

from termux_llamacpp.config import (
    ServerConfig,
    PROTOCOL_VERSION,
    DEFAULT_PUBLIC_PORT,
    DEFAULT_NATIVE_PORT,
    DEFAULT_RUN_DIR,
    DEFAULT_LOG_DIR,
    LLAMA_CPP_PINNED_COMMIT,
)
from termux_llamacpp.exceptions import ServerStartupError, TermuxLlamaError
from termux_llamacpp.security import (
    compute_sha256,
    verify_binary_pre_execution,
    verify_model_pre_execution,
    normalize_loopback_origin,
    TrustStore,
    SecurityVerificationError,
    BinaryTrustLevel,
    BinaryVerificationResult,
)


class ServerConflictError(TermuxLlamaError):
    """Raised when a conflicting server instance is already occupying the target port or lock."""
    pass


# Hop-by-hop HTTP headers to strip during reverse proxy forwarding
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

# Explicit Allowed HTTP API Route Endpoints
ALLOWED_ROUTES = {
    "/health",
    "/v1/health",
    "/v1/models",
    "/models",
    "/v1/chat/completions",
    "/chat/completions",
    "/v1/completions",
    "/completions",
}

MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024  # 10 MB limit


def normalize_loopback_bind_host(host: str, param_name: str = "host") -> str:
    """
    P0-1: Strictly enforce loopback binding for native and public hosts.
    Rejects 0.0.0.0, external IPs, and invalid hostnames.
    """
    normalized = host.strip().lower()
    if normalized == "localhost":
        return "127.0.0.1"
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError as exc:
        raise ServerStartupError(f"Invalid {param_name} bind host address: '{host}'") from exc

    if not address.is_loopback:
        raise ServerStartupError(
            f"{param_name} ('{host}') must bind to a local loopback address (e.g. 127.0.0.1, ::1, localhost)."
        )
    return normalized


def get_process_start_ticks(pid: int) -> str:
    """
    P1-2: Safely parse Linux /proc/<pid>/stat starttime ticks.
    Finds the last ')' to safely bypass process names containing spaces/brackets.
    """
    stat_file = Path(f"/proc/{pid}/stat")
    if not stat_file.is_file():
        return "0"
    try:
        raw = stat_file.read_text(encoding="utf-8")
        closing = raw.rfind(")")
        if closing < 0:
            raise ServerConflictError(f"Malformed /proc/{pid}/stat content.")
        fields_after_comm = raw[closing + 2:].split()
        if len(fields_after_comm) <= 19:
            raise ServerConflictError(f"Incomplete /proc/{pid}/stat fields.")
        return fields_after_comm[19]
    except Exception as exc:
        if isinstance(exc, ServerConflictError):
            raise exc
        raise ServerConflictError(f"Unable to verify process identity for PID {pid}: {exc}") from exc


class BoundedRingLogger:
    """Non-sensitive 256KB bounded ring buffer logger with 0600 file permissions."""

    def __init__(self, log_dir: Path = DEFAULT_LOG_DIR, max_bytes: int = 256 * 1024):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "llama-server.log"
        self.max_bytes = max_bytes
        self.recent_lines: List[str] = []

    def log(self, line: str):
        if "Bearer" in line or "Authorization" in line:
            line = "[REDACTED_AUTH_HEADER]"

        self.recent_lines.append(line)
        if len(self.recent_lines) > 50:
            self.recent_lines.pop(0)

        try:
            if self.log_file.is_file() and self.log_file.stat().st_size > self.max_bytes:
                bak_file = self.log_file.with_suffix(".log.1")
                if bak_file.exists():
                    bak_file.unlink()
                os.replace(str(self.log_file), str(bak_file))

            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ')}] {line}\n")

            try:
                self.log_file.chmod(0o600)
            except Exception:
                pass
        except Exception:
            pass

    def get_last_error_tail(self, max_count: int = 20) -> str:
        return "\n".join(self.recent_lines[-max_count:])


class ProcessIdentityLock:
    """Race-free OS file lock using fcntl.flock and separated supervisor & native PID validation."""

    def __init__(self, run_dir: Path = DEFAULT_RUN_DIR, lock_name: str = "llama-server.lock", allow_mock_lock: bool = False):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file = self.run_dir / lock_name
        self._handle = None
        self.owns_lock = False
        self.allow_mock_lock = allow_mock_lock

    def try_acquire(self) -> bool:
        """Attempt to acquire exclusive, non-blocking OS file lock."""
        self._handle = open(self.lock_file, "a+", encoding="utf-8")
        try:
            import fcntl
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.owns_lock = True
            return True
        except (BlockingIOError, PermissionError, OSError):
            self._handle.close()
            self._handle = None
            self.owns_lock = False
            return False
        except ImportError as exc:
            if self.allow_mock_lock:
                self.owns_lock = True
                return True
            self._handle.close()
            self._handle = None
            raise ServerStartupError("ProcessIdentityLock production mode requires POSIX fcntl.") from exc

    def write_metadata(self, metadata: Dict[str, Any]):
        if not self.owns_lock or not self._handle:
            raise RuntimeError("Cannot write metadata without exclusive lock ownership.")
        self._handle.seek(0)
        self._handle.truncate()
        json.dump(metadata, self._handle, indent=2)
        self._handle.flush()
        os.fsync(self._handle.fileno())

    def read_metadata(self) -> Optional[Dict[str, Any]]:
        if not self.lock_file.is_file():
            return None
        try:
            return json.loads(self.lock_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def release(self):
        if self._handle:
            try:
                import fcntl
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                self._handle.close()
            except Exception:
                pass
            self._handle = None
        self.owns_lock = False
        if self.lock_file.is_file():
            try:
                self.lock_file.unlink(missing_ok=True)
            except Exception:
                pass


class RuntimeState:
    """Encapsulated per-server instance runtime state."""

    def __init__(
        self,
        model_id: str,
        artifact_filename: str,
        model_sha256: str,
        native_endpoint: str,
        binary_verification: Optional[BinaryVerificationResult] = None,
        logger: Optional[BoundedRingLogger] = None,
    ):
        self.model_id = model_id
        self.artifact_filename = artifact_filename
        self.model_sha256 = model_sha256
        self.native_endpoint = native_endpoint
        self.binary_verification = binary_verification
        self.is_ready = False
        self.logger = logger


class ReverseProxyHTTPHandler(BaseHTTPRequestHandler):
    """Supervisor Reverse Proxy forwarding to native loopback :18080 with fail-closed error handling."""

    def _set_cors_headers(self):
        origin = self.headers.get("Origin", "")
        allowed = normalize_loopback_origin(origin)
        if allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    @property
    def state(self) -> RuntimeState:
        return getattr(self.server, "runtime_state")

    def do_GET(self):
        parsed_path = urllib.parse.urlsplit(self.path).path
        if parsed_path not in ALLOWED_ROUTES:
            self._send_proxy_error(404, "ROUTE_NOT_FOUND", "Requested route is not allowed.", parsed_path)
            return

        if parsed_path in ("/health", "/v1/health"):
            status_str = "ok" if self.state.is_ready else "loading"
            trust_info = {}
            if self.state.binary_verification:
                trust_info = {
                    "trustLevel": str(self.state.binary_verification.trust_level.value),
                    "commit": self.state.binary_verification.llama_cpp_commit,
                    "sha256": self.state.binary_verification.sha256,
                }
                if self.state.binary_verification.signing_key_id:
                    trust_info["signingKeyId"] = self.state.binary_verification.signing_key_id

            payload = {
                "service": "llama-server",
                "protocolVersion": PROTOCOL_VERSION,
                "status": status_str,
                "ready": self.state.is_ready,
                "runtime": trust_info,
                "model": {
                    "id": self.state.model_id,
                    "artifact_filename": self.state.artifact_filename,
                    "sha256": self.state.model_sha256,
                },
            }
            code = 200 if self.state.is_ready else 503
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed_path in ("/v1/models", "/models"):
            payload = {
                "object": "list",
                "data": [
                    {
                        "id": self.state.model_id,
                        "artifact_filename": self.state.artifact_filename,
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "uno-km",
                        "sha256": self.state.model_sha256,
                    }
                ],
            }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        self._forward_request("GET")

    def do_POST(self):
        parsed_path = urllib.parse.urlsplit(self.path).path
        if parsed_path not in ALLOWED_ROUTES:
            self._send_proxy_error(404, "ROUTE_NOT_FOUND", "Requested route is not allowed.", parsed_path)
            return

        self._forward_request("POST")

    def _forward_request(self, method: str):
        transfer_encoding = self.headers.get("Transfer-Encoding", "").lower()
        has_content_length = "Content-Length" in self.headers

        if transfer_encoding:
            if has_content_length:
                self._send_proxy_error(400, "INVALID_TRANSFER_ENCODING", "Both Content-Length and Transfer-Encoding are present.")
                return
            self._send_proxy_error(400, "UNSUPPORTED_TRANSFER_ENCODING", "Transfer-Encoding is not supported.")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self._send_proxy_error(400, "INVALID_CONTENT_LENGTH", "Invalid Content-Length header.")
            return

        if content_length < 0:
            self._send_proxy_error(400, "NEGATIVE_CONTENT_LENGTH", "Negative Content-Length header.")
            return

        if content_length > MAX_REQUEST_BODY_BYTES:
            self._send_proxy_error(413, "REQUEST_ENTITY_TOO_LARGE", f"Body exceeds {MAX_REQUEST_BODY_BYTES} bytes.")
            return

        body = self.rfile.read(content_length) if content_length > 0 else None
        upstream_url = f"{self.state.native_endpoint}{self.path}"

        if not self.state.is_ready:
            self._send_proxy_error(503, "LLAMA_SERVER_UNAVAILABLE", "Native llama-server is not ready.")
            return

        try:
            req = urllib.request.Request(upstream_url, data=body, method=method)
            for k, v in self.headers.items():
                if k.lower() not in HOP_BY_HOP_HEADERS and k.lower() != "host":
                    req.add_header(k, v)

            with urllib.request.urlopen(req, timeout=10) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in HOP_BY_HOP_HEADERS:
                        self.send_header(k, v)
                self._set_cors_headers()
                self.end_headers()

                while True:
                    chunk = resp.read(1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except urllib.error.HTTPError as exc:
            self.send_response(exc.code)
            for k, v in exc.headers.items():
                if k.lower() not in HOP_BY_HOP_HEADERS:
                    self.send_header(k, v)
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(exc.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            self.state.is_ready = False
            self._send_proxy_error(503, "LLAMA_SERVER_UNAVAILABLE", "Native llama-server is unavailable.", str(exc))

    def _send_proxy_error(self, status: int, code: str, message: str = "Native llama-server is unavailable.", detail: str = ""):
        payload = {
            "error": {
                "code": code,
                "message": message,
                "detail": detail,
            }
        }
        if self.state.logger:
            self.state.logger.log(f"Proxy Error [{code}] Status {status}: {message} ({detail})")
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(body)


def native_is_ready(native_endpoint: str, expected_model_id: str = "") -> bool:
    """
    P0-2 & P0-4 & P0-5: Robust Native llama-server Readiness Probe with Identity Handshake.
    """
    try:
        resp = requests.get(
            f"{native_endpoint}/health",
            timeout=1,
            allow_redirects=False,
        )
        if resp.status_code != 200:
            return False

        content_type = resp.headers.get("Content-Type", "").lower()
        if "application/json" not in content_type:
            return False

        payload = resp.json()
        if not isinstance(payload, dict):
            return False

        status = str(payload.get("status", "")).lower()
        if status not in {"ok", "ready", "healthy"}:
            return False

        if payload.get("ready") is False:
            return False

        if expected_model_id:
            actual_model_id = None
            if "model" in payload:
                m = payload["model"]
                actual_model_id = m.get("id") if isinstance(m, dict) else m

            if actual_model_id and hmac.compare_digest(str(actual_model_id), str(expected_model_id)):
                return True

            try:
                models_resp = requests.get(f"{native_endpoint}/v1/models", timeout=1, allow_redirects=False)
                if models_resp.status_code == 200:
                    models_data = models_resp.json().get("data", [])
                    loaded_ids = [str(item.get("id")) for item in models_data if isinstance(item, dict) and item.get("id")]
                    if any(hmac.compare_digest(lid, str(expected_model_id)) for lid in loaded_ids):
                        return True
            except Exception:
                pass

            return False

        return True
    except Exception:
        return False


class ServerInstance:
    def __init__(
        self,
        public_host: str,
        public_port: int,
        native_host: str,
        native_port: int,
        model_path: Path,
        model_id: str,
        model_sha256: str,
        is_owned: bool = True,
        process: Optional[subprocess.Popen] = None,
        proxy_httpd: Optional[ThreadingHTTPServer] = None,
        proxy_thread: Optional[threading.Thread] = None,
        lock_manager: Optional[ProcessIdentityLock] = None,
        logger: Optional[BoundedRingLogger] = None,
        log_handle: Optional[Any] = None,
        binary_verification: Optional[BinaryVerificationResult] = None,
    ):
        self.public_host = public_host
        self.public_port = public_port
        self.native_host = native_host
        self.native_port = native_port
        self.model_path = Path(model_path)
        self.model_id = model_id
        self.model_sha256 = model_sha256
        self.is_owned = is_owned
        self.process = process
        self.proxy_httpd = proxy_httpd
        self.proxy_thread = proxy_thread
        self.lock_manager = lock_manager
        self.logger = logger
        self.log_handle = log_handle
        self.binary_verification = binary_verification
        self.endpoint = f"http://{public_host}:{public_port}"
        self.native_endpoint = f"http://{native_host}:{native_port}"

    @property
    def pid(self) -> int:
        if self.process:
            return self.process.pid
        return os.getpid()

    def is_healthy(self) -> bool:
        try:
            resp = requests.get(f"{self.endpoint}/health", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("ready") is True and data.get("service") == "llama-server"
            return False
        except Exception:
            return False

    def wait_until_ready(self, timeout_seconds: int = 30) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self.is_healthy():
                return True
            time.sleep(0.5)
        return False

    def stop(self):
        if not self.is_owned:
            print(f"[termux-llamacpp] Detaching from attached server on {self.endpoint} (Process preserved).")
            return

        print(f"[termux-llamacpp] Terminating owned server on {self.endpoint}...")
        if self.proxy_httpd and hasattr(self.proxy_httpd, "runtime_state"):
            self.proxy_httpd.runtime_state.is_ready = False

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

        if self.log_handle:
            try:
                self.log_handle.close()
            except Exception:
                pass
            self.log_handle = None

        if self.proxy_httpd:
            try:
                self.proxy_httpd.shutdown()
                self.proxy_httpd.server_close()
            except Exception:
                pass
            self.proxy_httpd = None

        if self.proxy_thread and self.proxy_thread.is_alive():
            try:
                self.proxy_thread.join(timeout=2)
            except Exception:
                pass
            self.proxy_thread = None

        if self.lock_manager:
            self.lock_manager.release()

        print("[termux-llamacpp] Server supervisor stopped successfully.")


class ServerManager:
    def __init__(
        self,
        runtime=None,
        run_dir: Path = DEFAULT_RUN_DIR,
        log_dir: Path = DEFAULT_LOG_DIR,
        process_factory: Callable = subprocess.Popen,
        readiness_probe: Callable[[str, str], bool] = native_is_ready,
        allow_mock_lock: bool = False,
    ):
        self.runtime = runtime
        self.lock_mgr = ProcessIdentityLock(run_dir=run_dir, allow_mock_lock=allow_mock_lock)
        self.logger = BoundedRingLogger(log_dir=log_dir)
        self.trust_store = TrustStore()
        self.process_factory = process_factory
        self.readiness_probe = readiness_probe

    def serve(
        self,
        model_path: Path,
        public_host: str = "127.0.0.1",
        public_port: int = DEFAULT_PUBLIC_PORT,
        native_host: str = "127.0.0.1",
        native_port: int = DEFAULT_NATIVE_PORT,
        ctx_size: int = 2048,
        threads: int = 4,
        n_gpu_layers: int = 0,
        daemon: bool = False,
        **kwargs,
    ) -> ServerInstance:
        if "host" in kwargs:
            public_host = kwargs.pop("host")
        if "port" in kwargs:
            public_port = kwargs.pop("port")

        public_host = normalize_loopback_bind_host(public_host, "public_host")
        native_host = normalize_loopback_bind_host(native_host, "native_host")

        model_path = Path(model_path)
        if not model_path.is_file():
            raise ServerStartupError(f"Specified model file '{model_path}' does not exist.")

        manifest_path = model_path.with_suffix(model_path.suffix + ".manifest.json")
        if not manifest_path.is_file():
            raise SecurityVerificationError(f"Required model manifest is missing: {manifest_path}")

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SecurityVerificationError(f"Corrupted model manifest '{manifest_path}': {exc}") from exc

        # If signed, perform full cryptographic Ed25519 verification
        if "signature" in manifest and manifest.get("signature"):
            model_manifest = verify_model_pre_execution(model_path, self.trust_store)
            model_id = model_manifest["model_id"]
            model_sha256 = model_manifest["sha256"]
        else:
            # Unsigned manifest: validate filename, size, and SHA-256 integrity
            if manifest.get("artifact_filename") != model_path.name:
                raise SecurityVerificationError(
                    f"Model manifest artifact filename mismatch. Expected '{model_path.name}', got '{manifest.get('artifact_filename')}'"
                )
            actual_size = model_path.stat().st_size
            if manifest.get("size_bytes") and actual_size != manifest["size_bytes"]:
                raise SecurityVerificationError("Model file size mismatch against manifest.")
            expected_sha = manifest.get("sha256", "")
            actual_sha = compute_sha256(model_path)
            if expected_sha and not hmac.compare_digest(actual_sha.lower(), expected_sha.lower()):
                raise SecurityVerificationError("Model file checksum mismatch against manifest.")
            model_id = manifest.get("model_id", model_path.stem)
            model_sha256 = actual_sha

        server_bin = self.runtime.get_binary_path("llama-server") if self.runtime else None

        if not server_bin or not server_bin.is_file():
            raise ServerStartupError(
                f"Verified llama-server binary is unavailable. "
                f"Please run 'termux-llama install' to build the pinned native runtime."
            )

        # Pre-Execution Binary Validation with Trust Level Result
        binary_verification = verify_binary_pre_execution(
            server_bin,
            self.trust_store,
            LLAMA_CPP_PINNED_COMMIT,
            allow_local_build_receipt=True,
        )
        binary_sha256 = binary_verification.sha256

        public_endpoint = f"http://{public_host}:{public_port}"
        native_endpoint = f"http://{native_host}:{native_port}"

        if not self.lock_mgr.try_acquire():
            existing_meta = self.lock_mgr.read_metadata()
            if existing_meta:
                required_lock_fields = {
                    "schema_version",
                    "lock_owner_pid",
                    "lock_owner_start_ticks",
                    "native_pid",
                    "native_start_ticks",
                    "public_endpoint",
                    "native_endpoint",
                    "model_id",
                    "model_sha256",
                    "binary_sha256",
                    "llama_cpp_commit",
                }
                if required_lock_fields - set(existing_meta.keys()):
                    raise ServerConflictError("Lock metadata is incomplete or uses an unsupported schema.")

                lock_owner_pid = existing_meta.get("lock_owner_pid")
                lock_owner_ticks = existing_meta.get("lock_owner_start_ticks")
                native_pid = existing_meta.get("native_pid")
                native_ticks = existing_meta.get("native_start_ticks")

                cur_lock_ticks = get_process_start_ticks(lock_owner_pid) if lock_owner_pid else ""
                cur_native_ticks = get_process_start_ticks(native_pid) if native_pid else ""

                is_exact_match = (
                    existing_meta.get("public_endpoint") == public_endpoint
                    and existing_meta.get("native_endpoint") == native_endpoint
                    and existing_meta.get("model_id") == model_id
                    and existing_meta.get("model_sha256") == model_sha256
                    and existing_meta.get("binary_sha256") == binary_sha256
                    and existing_meta.get("llama_cpp_commit") == LLAMA_CPP_PINNED_COMMIT
                    and lock_owner_ticks == cur_lock_ticks
                    and native_ticks == cur_native_ticks
                )

                if is_exact_match:
                    try:
                        resp = requests.get(f"{public_endpoint}/health", timeout=2)
                        if resp.status_code == 200:
                            health_data = resp.json()
                            if (
                                health_data.get("ready") is True
                                and health_data.get("service") == "llama-server"
                                and health_data.get("protocolVersion") == PROTOCOL_VERSION
                                and health_data.get("model", {}).get("id") == model_id
                                and health_data.get("model", {}).get("sha256") == model_sha256
                            ):
                                print(f"[termux-llamacpp] Attaching to healthy VERIFIED instance on {public_endpoint}...")
                                return ServerInstance(
                                    public_host=public_host,
                                    public_port=public_port,
                                    native_host=native_host,
                                    native_port=native_port,
                                    model_path=model_path,
                                    model_id=model_id,
                                    model_sha256=model_sha256,
                                    is_owned=False,
                                    binary_verification=binary_verification,
                                )
                    except Exception:
                        pass

            raise ServerConflictError(
                f"Port or lockfile on {public_endpoint} is occupied by a conflicting instance. "
                f"Stop existing server or choose another port."
            )

        lock_meta = {
            "schema_version": "1.0",
            "lock_owner_pid": os.getpid(),
            "lock_owner_start_ticks": get_process_start_ticks(os.getpid()),
            "native_pid": 0,
            "native_start_ticks": "0",
            "public_endpoint": public_endpoint,
            "native_endpoint": native_endpoint,
            "model_id": model_id,
            "model_sha256": model_sha256,
            "binary_sha256": binary_sha256,
            "llama_cpp_commit": LLAMA_CPP_PINNED_COMMIT,
            "trust_level": binary_verification.trust_level.value,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self.lock_mgr.write_metadata(lock_meta)

        print("================================================================================")
        print("  [termux-llamacpp] Launching Reverse Proxy Server Supervisor")
        print("================================================================================")
        print(f"  Model ID        : {model_id}")
        print(f"  Artifact File   : {model_path.name}")
        print(f"  Public Endpoint : {public_endpoint}")
        print(f"  Native Endpoint : {native_endpoint} (Loopback)")
        print(f"  Binary Trust    : {binary_verification.trust_level.value}")
        print(f"  Protocol Version: {PROTOCOL_VERSION} (termux-aichain compliant)")
        print("================================================================================")

        runtime_state = RuntimeState(
            model_id=model_id,
            artifact_filename=model_path.name,
            model_sha256=model_sha256,
            native_endpoint=native_endpoint,
            binary_verification=binary_verification,
            logger=self.logger,
        )

        proxy_httpd = None
        proxy_thread = None
        process = None
        log_handle = None

        try:
            proxy_httpd = ThreadingHTTPServer((public_host, public_port), ReverseProxyHTTPHandler)
            proxy_httpd.daemon_threads = True
            proxy_httpd.runtime_state = runtime_state

            proxy_thread = threading.Thread(target=proxy_httpd.serve_forever, daemon=True)
            proxy_thread.start()

            cmd = [
                str(server_bin),
                "-m", str(model_path),
                "--host", native_host,
                "--port", str(native_port),
                "-c", str(ctx_size),
                "-np", "1",
                "-t", str(threads),
                "-ngl", str(n_gpu_layers),
                "--no-mmap",
            ]

            log_handle = open(self.logger.log_file, "a", encoding="utf-8")
            process = self.process_factory(
                cmd,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )

            lock_meta["native_pid"] = process.pid
            lock_meta["native_start_ticks"] = get_process_start_ticks(process.pid)
            self.lock_mgr.write_metadata(lock_meta)

            native_ready = False
            deadline = time.time() + 25
            while time.time() < deadline:
                if self.readiness_probe(native_endpoint, model_id):
                    native_ready = True
                    break
                if process.poll() is not None:
                    break
                time.sleep(0.5)

            if not native_ready:
                exit_code = process.poll()
                if exit_code is not None:
                    self.logger.log(f"Native llama-server exited prematurely with code {exit_code}")
                err_tail = self.logger.get_last_error_tail(20)
                raise ServerStartupError(
                    f"Native llama-server failed to bind and become ready on {native_endpoint}.\n"
                    f"Last log lines:\n{err_tail}"
                )

            if process.poll() is not None:
                raise ServerStartupError("Native llama-server exited immediately after readiness probe.")

            runtime_state.is_ready = True

            instance = ServerInstance(
                public_host=public_host,
                public_port=public_port,
                native_host=native_host,
                native_port=native_port,
                model_path=model_path,
                model_id=model_id,
                model_sha256=model_sha256,
                is_owned=True,
                process=process,
                proxy_httpd=proxy_httpd,
                proxy_thread=proxy_thread,
                lock_manager=self.lock_mgr,
                logger=self.logger,
                log_handle=log_handle,
                binary_verification=binary_verification,
            )

            time.sleep(0.1)
            print(f"[termux-llamacpp] Reverse Proxy active and ready at {public_endpoint}")
            return instance

        except Exception as exc:
            if process:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
            if log_handle:
                try:
                    log_handle.close()
                except Exception:
                    pass
            if proxy_httpd:
                try:
                    proxy_httpd.shutdown()
                    proxy_httpd.server_close()
                except Exception:
                    pass
            if proxy_thread and proxy_thread.is_alive():
                try:
                    proxy_thread.join(timeout=1)
                except Exception:
                    pass
            self.lock_mgr.release()
            if isinstance(exc, TermuxLlamaError):
                raise exc
            raise ServerStartupError(f"Failed to start reverse proxy server: {exc}") from exc


PIDLockManager = ProcessIdentityLock
