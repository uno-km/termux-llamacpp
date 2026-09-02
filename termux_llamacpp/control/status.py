"""
termux_llamacpp.control.status
AMEVA Component Protocol v1 — 상태 파일 Writer + 10초 Heartbeat

Heartbeat 갱신 트리거:
  - Worker 시작
  - 모델 활성화/비활성화
  - Job 시작 (active_jobs++)
  - Job 종료 (active_jobs--)
  - 엔진 오류
  - 정상 종료
  - 10초 주기 Heartbeat
"""
from __future__ import annotations

import threading
import time
from typing import Any

from ameva_component import log_stderr


class LlamaCppStatusWriter:
    """LlamaCppControl 상태를 10초마다 상태 파일에 원자적으로 기록합니다."""

    def __init__(self, control: Any) -> None:
        self._control = control
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def write(self, **overrides) -> None:
        """현재 control 상태를 상태 파일에 즉시 기록합니다."""
        self._control._write_state(**overrides)

    def start_heartbeat(self, interval: float = 10.0) -> None:
        """백그라운드 쓰레드로 interval초마다 상태 파일을 갱신합니다."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()

        def _loop() -> None:
            while not self._stop_event.wait(timeout=interval):
                try:
                    self._control._write_state()
                except Exception as exc:
                    log_stderr(f"[llamacpp] heartbeat write failed: {exc}")

        self._thread = threading.Thread(target=_loop, daemon=True, name="llama-heartbeat")
        self._thread.start()
        log_stderr(f"[llamacpp] Heartbeat started (interval={interval}s)")

    def stop_heartbeat(self) -> None:
        """Heartbeat 쓰레드를 중지합니다."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        log_stderr("[llamacpp] Heartbeat stopped")
