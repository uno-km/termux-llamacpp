"""Comprehensive Real-Device (Samsung Galaxy S20+ Termux ARM64) E2E Test Runner and Evidence Collector."""

import hashlib
import json
import os
import sys
import time
from pathlib import Path
import paramiko

HOST = "125.132.13.175"
PORT = 58020
USER = "u0_a172"
PASS = "12345678"

ROOT = Path(__file__).resolve().parent.parent

def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest().upper()

class RealDeviceAuditRunner:
    def __init__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.sftp = None
        self.evidence_log = []
        self.scores = {}
        self.total_score = 0.0

    def connect(self):
        print(f"[*] Connecting to {USER}@{HOST}:{PORT}...")
        self.client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
        self.sftp = self.client.open_sftp()
        print("[+] SSH & SFTP connected successfully!")

    def record_score(self, category: str, test_name: str, points: float, max_points: float, latency_ms: float, passed: bool, details: str = ""):
        score_val = points if passed else 0.0
        self.scores[test_name] = {
            "category": category,
            "score": score_val,
            "max": max_points,
            "latency_ms": latency_ms,
            "passed": passed,
            "details": details,
        }
        self.total_score += score_val
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] [SCORE +{score_val:.1f}/{max_points:.1f} pts] ({category}) {test_name} in {latency_ms:.2f}ms | Subtotal: {self.total_score:.1f}")

    def run_cmd(self, cmd: str, timeout: int = 300) -> tuple:
        print(f"\n>>> [SSH-EXEC] {cmd}")
        t0 = time.perf_counter()
        stdin, stdout, stderr = self.client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        print(f"<<< [EXIT {code}] in {elapsed_ms:.1f}ms")
        if out:
            print(out.strip())
        if err:
            print(f"[STDERR]\n{err.strip()}")
        self.evidence_log.append({
            "cmd": cmd,
            "exit_code": code,
            "elapsed_ms": elapsed_ms,
            "stdout": out,
            "stderr": err,
            "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "time_local": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        })
        return code, out, err, elapsed_ms

    def upload_file(self, local_path: Path, remote_path: str):
        print(f"[*] Uploading {local_path} -> {remote_path}...")
        self.sftp.put(str(local_path), remote_path)
        print(f"[+] Uploaded {local_path.name}")

    def close(self):
        if self.sftp:
            self.sftp.close()
        self.client.close()

def main():
    runner = RealDeviceAuditRunner()
    runner.connect()

    # Pre-upload artifacts
    tar_path = ROOT / "termux-llamacpp-1.0.0b1.tar"
    wheel_path = list((ROOT / "dist").glob("*.whl"))[0]
    expected_tar_sha = compute_sha256(tar_path)
    expected_whl_sha = compute_sha256(wheel_path)

    runner.upload_file(tar_path, "termux-llamacpp-1.0.0b1.tar")
    runner.upload_file(wheel_path, "termux_llamacpp-1.0.0b1-py3-none-any.whl")

    # =========================================================================
    # Phase 1: Transfer & Archive Hash Verification
    # =========================================================================
    t0 = time.perf_counter()
    c, out, err, ms = runner.run_cmd("sha256sum termux-llamacpp-1.0.0b1.tar termux_llamacpp-1.0.0b1-py3-none-any.whl")
    tar_match = expected_tar_sha.lower() in out.lower()
    whl_match = expected_whl_sha.lower() in out.lower()
    runner.record_score("1. Archive Transfer & Integrity", "test_archive_hash_match", 10.0, 10.0, ms, c == 0 and tar_match and whl_match, f"TAR: {expected_tar_sha}, WHL: {expected_whl_sha}")

    # =========================================================================
    # Phase 2: Environment & Hardware Capabilities
    # =========================================================================
    c, out, err, ms = runner.run_cmd("uname -m && getprop ro.product.cpu.abi && lscpu || true")
    is_arm64 = "aarch64" in out or "arm64-v8a" in out
    runner.record_score("2. Environment & HW Architecture", "test_arm64_architecture", 10.0, 10.0, ms, is_arm64, "ARM64 Android Termux Confirmed")

    # Ensure build dependencies
    runner.run_cmd("pkg install -y clang cmake ninja git python python-pip openssl jq coreutils tar")

    # =========================================================================
    # Phase 3: Python Package Installation (Wheel)
    # =========================================================================
    c, out, err, ms = runner.run_cmd("pip install --upgrade --force-reinstall termux_llamacpp-1.0.0b1-py3-none-any.whl")
    runner.record_score("3. Python Wheel Installation", "test_wheel_installation", 10.0, 10.0, ms, c == 0, "termux-llamacpp pip install")

    c, out, err, ms = runner.run_cmd("termux-llama --version && termux-llama hardware")
    runner.record_score("3. Python Wheel Installation", "test_cli_entrypoint", 10.0, 10.0, ms, c == 0 and "1.0.0b1" in out, "CLI Entrypoint & HW detection")

    # =========================================================================
    # Phase 4: Extraction & Native Compilation Pipeline (install.sh)
    # =========================================================================
    runner.run_cmd("rm -rf termux-llamacpp && mkdir -p termux-llamacpp && tar -xf termux-llamacpp-1.0.0b1.tar -C termux-llamacpp")
    
    # Run install.sh with arm64 baseline / native preset
    c, out, err, ms = runner.run_cmd("cd termux-llamacpp && bash scripts/install.sh", timeout=900)
    runner.record_score("4. Native Build Pipeline", "test_native_compile_install_sh", 20.0, 20.0, ms, c == 0, "CMake + Clang llama-server & llama-cli build")

    # Verify native binary ELF aarch64
    c, out, err, ms = runner.run_cmd("file $HOME/.termux-llama/bin/llama-server $HOME/.termux-llama/bin/llama-cli")
    is_elf_arm64 = "ELF 64-bit" in out and "ARM aarch64" in out
    runner.record_score("4. Native Build Pipeline", "test_elf_aarch64_format", 10.0, 10.0, ms, is_elf_arm64, out)

    # Verify build receipt
    c, out, err, ms = runner.run_cmd("cat $HOME/.termux-llama/bin/llama-server.build-receipt.json")
    receipt_valid = "local-native-build" in out and "08f32c9b68a8b13a890a827038e21946059d57a2" in out
    runner.record_score("4. Native Build Pipeline", "test_build_receipt_provenance", 10.0, 10.0, ms, receipt_valid, out)

    # =========================================================================
    # Phase 5: GGUF Model Setup & CLI Inference
    # =========================================================================
    # Let's check if models already exist or download/copy a tiny GGUF model
    runner.run_cmd("mkdir -p $HOME/models")
    # Check for existing GGUF models on device
    c, out, err, ms = runner.run_cmd("find $HOME -maxdepth 3 -name '*.gguf' 2>/dev/null")
    existing_models = [m.strip() for m in out.splitlines() if m.strip().endswith(".gguf")]
    
    model_path = "$HOME/models/test-tiny.gguf"
    if existing_models:
        model_path = existing_models[0]
        print(f"[+] Found existing model: {model_path}")
    else:
        print("[*] Downloading small testing GGUF model...")
        # Download small Smollm 135M or Qwen 0.5B GGUF
        runner.run_cmd("curl -L -o $HOME/models/smollm-135m-q4_k_m.gguf 'https://huggingface.co/HuggingFaceTB/SmolLM-135M-Instruct-GGUF/resolve/main/smollm-135m-instruct-q4_k_m.gguf'")
        model_path = "$HOME/models/smollm-135m-q4_k_m.gguf"

    # Test llama-cli inference
    c, out, err, ms = runner.run_cmd(f"$HOME/.termux-llama/bin/llama-cli -m {model_path} -p 'Hello from Termux ARM64' -n 16 --temp 0.2", timeout=120)
    cli_infer_ok = (c == 0) and ("tokens" in out.lower() or "eval time" in out.lower() or len(out) > 50)
    runner.record_score("5. GGUF CLI Inference", "test_llama_cli_inference", 10.0, 10.0, ms, cli_infer_ok, out[-300:] if len(out)>300 else out)

    # =========================================================================
    # Phase 6: HTTP Server, /health, /v1/models, Chat Completion, SSE Streaming
    # =========================================================================
    # Start server in background
    runner.run_cmd("pkill -9 llama-server || true")
    runner.run_cmd(f"$HOME/.termux-llama/bin/llama-server -m {model_path} --host 127.0.0.1 --port 18088 -c 512 > $HOME/llama-server.log 2>&1 &")
    time.sleep(3)

    # Health check polling
    c, out, err, ms = runner.run_cmd("curl -s --fail http://127.0.0.1:18088/health")
    health_ok = (c == 0) and ("status" in out or "ok" in out.lower() or "loading" in out.lower())
    runner.record_score("6. Server REST & Health API", "test_http_health_endpoint", 5.0, 5.0, ms, health_ok, out)

    # Model discovery
    c, out, err, ms = runner.run_cmd("curl -s --fail http://127.0.0.1:18088/v1/models")
    models_ok = (c == 0) and ("data" in out or "object" in out)
    runner.record_score("6. Server REST & Health API", "test_v1_models_discovery", 5.0, 5.0, ms, models_ok, out)

    # Chat Completion (Non-stream)
    c, out, err, ms = runner.run_cmd(
        """curl -s --fail -X POST http://127.0.0.1:18088/v1/chat/completions """
        """-H 'Content-Type: application/json' """
        """-d '{"messages":[{"role":"user","content":"Say HELLO_TERMUX"}],"max_tokens":16,"temperature":0.0}'"""
    )
    chat_ok = (c == 0) and ("choices" in out or "content" in out)
    runner.record_score("6. Server REST & Health API", "test_chat_completion_non_stream", 5.0, 5.0, ms, chat_ok, out)

    # Chat Completion (SSE Streaming)
    c, out, err, ms = runner.run_cmd(
        """curl -s --no-buffer -X POST http://127.0.0.1:18088/v1/chat/completions """
        """-H 'Content-Type: application/json' """
        """-d '{"messages":[{"role":"user","content":"Say STREAM_OK"}],"max_tokens":16,"stream":true}'"""
    )
    sse_ok = (c == 0) and ("data:" in out) and ("[DONE]" in out)
    runner.record_score("6. Server REST & Health API", "test_chat_completion_sse_stream", 5.0, 5.0, ms, sse_ok, out[:300])

    # Stop server
    runner.run_cmd("pkill -9 llama-server || true")

    # Save evidence file
    evidence_path = ROOT / "artifacts" / "real_device_evidence.json"
    evidence_path.write_text(json.dumps({
        "device": "Samsung Galaxy S20+ (SM-G986N)",
        "host": HOST,
        "port": PORT,
        "user": USER,
        "total_score": runner.total_score,
        "scores": runner.scores,
        "logs": runner.evidence_log,
    }, indent=2), encoding="utf-8")
    print(f"\n[+] Saved full device evidence to {evidence_path}")
    print(f"[+] Final Real Device Score: {runner.total_score:.1f} / 100.0 pts")

    runner.close()

if __name__ == "__main__":
    main()
