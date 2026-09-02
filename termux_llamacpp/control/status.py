"""
termux_llamacpp.control.status
AMEVA Component Protocol v1 — 상태 파일 Writer + 10초 Heartbeat

갱신 트리거:
  ① Worker 시작      → start()
  ② 모델 활성화      → write()
  ③ Job 시작         → notify_job_start()
  ④ Job 종료         → notify_job_end()
  ⑤ 엔진 오류        → notify_error()
  ⑥ 정상 종료        → stop()
  ⑦ Heartbeat 주기   → 10초마다 updated_at 갱신
"""
from __future__ import annotations
from typing import Any
from ameva_component.heartbeat import HeartbeatWriter


class LlamaCppStatusWriter(HeartbeatWriter):
    """LlamaCppControl 상태를 10초마다 상태 파일에 원자적으로 기록합니다."""

    def __init__(self, control: Any) -> None:
        super().__init__(control, name="llamacpp")
