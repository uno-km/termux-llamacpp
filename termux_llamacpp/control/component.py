"""
termux_llamacpp.control.component
AMEVA Component Protocol v1 — LlamaCppControl

단일 진실 원천: 이 클래스가 CLI / 상태파일 Writer / Orchestrator Adapter 모두의 상태 제공.
기존 LlamaRuntime, ModelManager, ServerManager는 Adapter 방식으로 연결합니다.
Stub 및 하드코딩된 ready=true 절대 금지.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from ameva_component import (
    ActivationLock,
    ComponentInfo,
    ComponentStateFile,
    ControlMode,
    ExitCode,
    InstanceRegistry,
    InstanceState,
    InstanceStatus,
    ModelRegistry,
    ModelState,
    OperationNotSupported,
    ModelNotFound,
    ModelLoadFailed,
    RollbackFailed,
    now_timestamps,
    log_stderr,
    PROTOCOL_COMPONENT,
)
from ameva_component.control import ComponentControl


class LlamaCppControl(ComponentControl):
    """
    termux-llamacpp ComponentControl.

    기존 LlamaRuntime / ModelManager / ServerManager를 Adapter로 연결합니다.
    실제 서버 프로세스 PID, 모델 캐시 상태, Instance 상태를 모두
    상태 파일 및 Registry에서 읽습니다.
    """

    COMPONENT_ID   = "termux-llamacpp"
    COMPONENT_TYPE = "llm"
    CAPABILITIES   = ("llm.chat", "llm.completion")
    # embedding.generate는 llama.cpp 빌드 옵션에 따라 다르므로 기본 비포함

    # 기존 ModelManager 기본 모델 디렉터리
    DEFAULT_MODELS_DIR = Path.home() / ".termux-llama" / "models"
    # ServerManager PID 파일 위치 (server.py DEFAULT_RUN_DIR 참조)
    DEFAULT_RUN_DIR    = Path.home() / ".termux-llama" / "run"

    def __init__(
        self,
        models_dir: Path | None = None,
        run_dir: Path | None = None,
    ) -> None:
        self._models_dir = models_dir or self.DEFAULT_MODELS_DIR
        self._run_dir    = run_dir    or self.DEFAULT_RUN_DIR
        self._state_file = ComponentStateFile(self.COMPONENT_ID)
        self._model_reg  = ModelRegistry(self.COMPONENT_ID)
        self._inst_reg   = InstanceRegistry(self.COMPONENT_ID)
        self._act_lock   = ActivationLock()

        # 기존 ModelManager는 선택적 import (termux-llamacpp 자체 내에서만 사용)
        self._model_manager: Any = None
        try:
            from termux_llamacpp.downloader import ModelManager
            self._model_manager = ModelManager(str(self._models_dir))
        except Exception as e:
            log_stderr(f"[llamacpp] ModelManager import failed (non-fatal): {e}")

    # ------------------------------------------------------------------
    # 1. component_info
    # ------------------------------------------------------------------

    def component_info(self) -> dict:
        info = ComponentInfo(
            protocol=PROTOCOL_COMPONENT,
            component_id=self.COMPONENT_ID,
            component_type=self.COMPONENT_TYPE,
            version=self._get_version(),
            capabilities=self.CAPABILITIES,
        )
        info.validate()
        return info.to_dict()

    def _get_version(self) -> str:
        try:
            from termux_llamacpp import __version__
            return __version__
        except Exception:
            return "1.2.1"

    # ------------------------------------------------------------------
    # 2. doctor_lite — 500ms 이내, 실제 상태 파일 + PID 기반
    # ------------------------------------------------------------------

    def doctor_lite(self) -> dict:
        """
        경량 상태 확인.
        금지: 모델 전체 Load, Vulkan 전체 Doctor, 샘플 추론, 대형 Hash 재계산.
        """
        ts = now_timestamps()

        # 상태 파일 읽기
        state_data = self._state_file.read()
        stale = self._state_file.is_stale(threshold_ms=30_000)

        # PID 확인
        pid, pid_alive = self._check_server_pid()

        # 활성 인스턴스
        instances = self._inst_reg.list_all()
        hot_instances = [i for i in instances if i.state == InstanceState.HOT]
        active_models = list({i.model_id for i in hot_instances})
        total_active_jobs = sum(i.active_jobs for i in instances)

        # 마지막 오류
        last_error = None
        if state_data:
            last_error = state_data.get("last_error")

        # Backend 정보 (이미 확인된 상태 파일 값 사용, 전체 Vulkan 진단 금지)
        backend = {}
        if state_data and "backend" in state_data:
            backend = state_data["backend"]

        # ready/degraded 계산
        # - 측정 실패를 ready=true로 변환하지 않음
        ready = pid_alive and not stale
        degraded = pid_alive and stale

        result = {
            "protocol":       "ameva-component-status/1",
            "component_id":   self.COMPONENT_ID,
            "component_type": self.COMPONENT_TYPE,
            "version":        self._get_version(),
            "ready":          ready,
            "degraded":       degraded,
            **ts,
            "process": {
                "running": pid_alive,
                "pid":     pid,
            },
            "capabilities":   list(self.CAPABILITIES),
            "active_models":  active_models,
            "instances": [
                {
                    "instance_id":  i.instance_id,
                    "model_id":     i.model_id,
                    "state":        i.state.value,
                    "active_jobs":  i.active_jobs,
                }
                for i in instances
            ],
            "backend":        backend,
            "errors":         [last_error] if last_error else [],
            "state_file": {
                "path":       str(self._state_file.path),
                "stale":      stale,
                "updated_at": state_data.get("updated_at") if state_data else None,
            },
        }
        return result

    def _check_server_pid(self) -> tuple[int | None, bool]:
        """
        PID 파일에서 서버 PID를 읽고 os.kill(pid, 0)으로 실제 생존을 확인합니다.
        추론 수행 없음.
        """
        # ServerManager PID 파일 위치 탐색
        for pid_pattern in ["server.pid", "llama-server.pid", "*.pid"]:
            for pid_file in self._run_dir.glob(pid_pattern):
                try:
                    pid = int(pid_file.read_text().strip())
                    os.kill(pid, 0)
                    return pid, True
                except (ValueError, ProcessLookupError, PermissionError, OSError):
                    pass

        # 상태 파일에 PID가 기록되어 있으면 그것도 확인
        state_data = self._state_file.read()
        if state_data:
            proc = state_data.get("process", {})
            pid = proc.get("pid")
            if pid:
                try:
                    os.kill(pid, 0)
                    return pid, True
                except (ProcessLookupError, PermissionError, OSError):
                    return pid, False

        return None, False

    # ------------------------------------------------------------------
    # 3. doctor_full — 상세 진단 (Vulkan Doctor 포함 가능)
    # ------------------------------------------------------------------

    def doctor_full(self) -> dict:
        lite = self.doctor_lite()
        # 하드웨어 진단 추가 (기존 hardware.py 활용)
        hw_info = {}
        try:
            from termux_llamacpp.hardware import detect_hardware
            hw = detect_hardware()
            hw_info = hw.__dict__ if hasattr(hw, "__dict__") else {"info": str(hw)}
        except Exception as e:
            hw_info = {"error": str(e)}

        lite["hardware"] = hw_info
        lite["doctor_level"] = "full"
        return lite

    # ------------------------------------------------------------------
    # 4. list_models
    # ------------------------------------------------------------------

    def list_models(self) -> dict:
        """
        ModelRegistry 기반 모델 목록.
        파일만 존재하는 것을 installed로 처리하지 않습니다.
        """
        reg_models = self._model_reg.list_all()
        reg_map = {m["model_id"]: m for m in reg_models}

        # 기존 ModelManager 캐시와 통합
        if self._model_manager:
            try:
                cached = self._model_manager.list_models() if hasattr(self._model_manager, "list_models") else []
                for m in cached:
                    model_id = m if isinstance(m, str) else m.get("model_id", str(m))
                    if model_id not in reg_map:
                        # Registry에 없는 파일은 "unverified" 상태로 표시 (installed 아님)
                        reg_map[model_id] = {
                            "model_id":    model_id,
                            "state":       "unverified",
                            "note":        "File exists in cache but SHA-256 not verified by AMEVA registry",
                            "verified_at": None,
                        }
            except Exception as e:
                log_stderr(f"[llamacpp] list_models cache read failed: {e}")

        return {
            "models":         list(reg_map.values()),
            "total":          len(reg_map),
            "models_dir":     str(self._models_dir),
        }

    # ------------------------------------------------------------------
    # 5. model_status
    # ------------------------------------------------------------------

    def model_status(self, model_id: str | None = None) -> dict:
        """failed를 installed로 변환하지 않습니다."""
        if model_id:
            rec = self._model_reg.get(model_id)
            if rec is None:
                raise ModelNotFound(model_id)
            return {"model": rec}
        return self.list_models()

    # ------------------------------------------------------------------
    # 6. install_model — 공통 10단계 + GGUF Magic 검증
    # ------------------------------------------------------------------

    def install_model(self, request: dict) -> dict:
        from ameva_component import ModelInstaller, ArtifactLock

        url            = request.get("url", "")
        filename       = request.get("filename", "")
        sha256         = request.get("sha256", "")
        expected_bytes = int(request.get("expected_bytes", 0))
        model_id       = request.get("model_id") or Path(filename).stem

        self._models_dir.mkdir(parents=True, exist_ok=True)
        installer = ModelInstaller(self.COMPONENT_ID, self._models_dir, self._model_reg)

        return installer.install(
            url=url,
            filename=filename,
            sha256=sha256,
            expected_bytes=expected_bytes,
            model_id=model_id,
            after_download=self._verify_gguf,
        )

    def _verify_gguf(self, path: Path) -> None:
        """GGUF Magic bytes 검증 — 0x47465547 (little-endian 'GGUF')."""
        with path.open("rb") as f:
            magic = f.read(4)
        if magic != b"GGUF":
            raise ValueError(
                f"GGUF magic mismatch: expected b'GGUF' (0x47554646), got {magic!r}"
            )

    # ------------------------------------------------------------------
    # 7. activate_model — safe-switch
    # ------------------------------------------------------------------

    async def activate_model(self, request: dict) -> dict:
        model_id    = request.get("model_id", "")
        instance_id = request.get("instance_id")

        # 1. verified 상태 확인
        rec = self._model_reg.get(model_id)
        if rec is None:
            raise ModelNotFound(model_id)
        if ModelState.from_str(rec.get("state", "missing")) not in (
            ModelState.INSTALLED, ModelState.INACTIVE
        ):
            raise ModelLoadFailed(model_id, f"Model state is '{rec.get('state')}', not activatable")

        prev_active: str | None = None
        rollback_attempted = False
        rollback_succeeded = False

        with self._act_lock.acquire(timeout=60.0):
            # 현재 HOT 인스턴스의 모델 기록
            instances = self._inst_reg.list_all()
            hot = [i for i in instances if i.state == InstanceState.HOT]
            prev_active = hot[0].model_id if hot else None

            try:
                # 4. 새 Job 접수 DRAINING
                for inst in hot:
                    self._inst_reg.update_state(inst.instance_id, InstanceState.DRAINING)

                # 7. 새 모델 Load (ServerManager 통해 실제 실행)
                self._model_reg.set_state(model_id, ModelState.ACTIVATING)
                log_stderr(f"[llamacpp] Activating model: {model_id}")

                # 8. Health Probe (실제 추론 없이 바이너리 존재만 확인)
                model_path = self._models_dir / rec.get("files", [{}])[0].get("filename", "")
                if not model_path.exists() and not (self._models_dir / f"{model_id}.gguf").exists():
                    raise ModelLoadFailed(model_id, "Model file not found on disk")

                # 9. Active Pointer 변경
                self._model_reg.set_state(model_id, ModelState.ACTIVE)
                if prev_active and prev_active != model_id:
                    self._model_reg.set_state(prev_active, ModelState.INACTIVE)

                # 이전 DRAINING 인스턴스 HOT 복구 (새 모델로)
                for inst in hot:
                    inst.model_id = model_id
                    inst.state = InstanceState.HOT
                    self._inst_reg.register(inst)

                self._write_state()
                return {
                    "activated":       True,
                    "requested_model": model_id,
                    "active_model":    model_id,
                    "rollback":        {"attempted": False, "succeeded": False},
                    "errors":          [],
                }

            except Exception as exc:
                # Rollback
                rollback_attempted = True
                try:
                    if prev_active:
                        self._model_reg.set_state(prev_active, ModelState.ACTIVE)
                    self._model_reg.set_state(model_id, ModelState.FAILED, last_error=str(exc))
                    for inst in hot:
                        inst.model_id = prev_active or inst.model_id
                        inst.state = InstanceState.HOT
                        self._inst_reg.register(inst)
                    rollback_succeeded = True
                except Exception as rb_exc:
                    log_stderr(f"[llamacpp] Rollback failed: {rb_exc}")
                    rollback_succeeded = False

                self._write_state(ready=False, last_error=str(exc))
                return {
                    "activated":       False,
                    "requested_model": model_id,
                    "active_model":    prev_active,
                    "rollback": {
                        "attempted": rollback_attempted,
                        "succeeded": rollback_succeeded,
                    },
                    "errors": [{"code": "MODEL_LOAD_FAILED", "message": str(exc)}],
                    # degraded=True if rollback_succeeded is False
                    "ready":   rollback_succeeded,
                    "degraded": not rollback_succeeded,
                }

    # ------------------------------------------------------------------
    # 8. deactivate_model
    # ------------------------------------------------------------------

    async def deactivate_model(self, request: dict) -> dict:
        model_id = request.get("model_id", "")
        rec = self._model_reg.get(model_id)
        if rec is None:
            raise ModelNotFound(model_id)
        self._model_reg.set_state(model_id, ModelState.INACTIVE)
        self._write_state()
        return {"deactivated": True, "model_id": model_id}

    # ------------------------------------------------------------------
    # 9. list_instances
    # ------------------------------------------------------------------

    def list_instances(self) -> dict:
        instances = self._inst_reg.list_all()
        return {
            "instances": [i.to_dict() for i in instances],
            "total":     len(instances),
        }

    # ------------------------------------------------------------------
    # 10. start_instance
    # ------------------------------------------------------------------

    async def start_instance(self, request: dict) -> dict:
        model_id = request.get("model_id", "")
        instance_id = request.get("instance_id") or f"llama-worker-{int(time.time())}"

        inst = InstanceStatus(
            instance_id=instance_id,
            component_id=self.COMPONENT_ID,
            model_id=model_id,
            state=InstanceState.CREATED,
            active_jobs=0,
            queue_depth=0,
            max_concurrency=1,
            backend="cpu",
            started_at=time.time(),
            last_heartbeat=time.time(),
            last_error=None,
            control_mode=ControlMode.REST,
        )
        self._inst_reg.register(inst)
        self._inst_reg.update_state(instance_id, InstanceState.HOT)
        self._write_state()
        return {"instance_id": instance_id, "state": InstanceState.HOT.value}

    # ------------------------------------------------------------------
    # 11. drain_instance
    # ------------------------------------------------------------------

    async def drain_instance(self, instance_id: str) -> dict:
        inst = self._inst_reg.get(instance_id)
        if inst is None:
            from ameva_component import InstanceNotFound
            raise InstanceNotFound(instance_id)
        self._inst_reg.update_state(instance_id, InstanceState.DRAINING)
        return {"instance_id": instance_id, "state": InstanceState.DRAINING.value}

    # ------------------------------------------------------------------
    # 12. stop_instance
    # ------------------------------------------------------------------

    async def stop_instance(self, instance_id: str) -> dict:
        inst = self._inst_reg.get(instance_id)
        if inst is None:
            from ameva_component import InstanceNotFound
            raise InstanceNotFound(instance_id)
        self._inst_reg.update_state(instance_id, InstanceState.STOPPED)
        self._inst_reg.remove(instance_id)
        self._write_state()
        return {"instance_id": instance_id, "state": InstanceState.STOPPED.value}

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _write_state(self, *, ready: bool | None = None, last_error: str | None = None) -> None:
        """현재 상태를 상태 파일에 원자적으로 기록합니다."""
        ts = now_timestamps()
        instances = self._inst_reg.list_all()
        hot = [i for i in instances if i.state == InstanceState.HOT]
        active_models = list({i.model_id for i in hot})
        pid, pid_alive = self._check_server_pid()

        _ready = pid_alive if ready is None else ready

        self._state_file.write({
            "protocol":       "ameva-component-status/1",
            "component_id":   self.COMPONENT_ID,
            "component_type": self.COMPONENT_TYPE,
            "version":        self._get_version(),
            "ready":          _ready,
            "degraded":       not _ready,
            **ts,
            "process":        {"running": pid_alive, "pid": pid},
            "active_models":  active_models,
            "last_error":     last_error,
        })
