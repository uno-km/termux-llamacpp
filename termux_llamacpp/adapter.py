"""
termux_llamacpp.adapter
AMEVA Component Protocol v1 — Orchestrator Adapter

Orchestrator가 호출하는 단일 인터페이스.
SSH CLI와 REST 결과가 동일한 상태를 반환하도록 보장합니다.
"""
from __future__ import annotations

from termux_llamacpp.control.component import LlamaCppControl


class LlamaCppOrchestratorAdapter:
    """
    Orchestrator (termux-ai-orchestrator v0.7.0+)가 호출하는 어댑터.
    내부적으로 LlamaCppControl을 사용하여 단일 진실 원천을 보장합니다.
    """

    def __init__(self, control: LlamaCppControl | None = None) -> None:
        self._control = control or LlamaCppControl()

    def info(self) -> dict:
        """컴포넌트 신원 정보. orchestrator discovery용."""
        return self._control.component_info()

    def health(self) -> dict:
        """doctor_lite 결과. orchestrator heartbeat / health check용."""
        return self._control.doctor_lite()

    def models(self) -> dict:
        """설치된 모델 목록."""
        return self._control.list_models()

    def instances(self) -> dict:
        """Instance 목록."""
        return self._control.list_instances()

    async def activate(self, req: dict) -> dict:
        """모델 활성화 (safe-switch)."""
        return await self._control.activate_model(req)

    async def deactivate(self, req: dict) -> dict:
        """모델 비활성화."""
        return await self._control.deactivate_model(req)

    async def start_instance(self, req: dict) -> dict:
        """인스턴스 시작."""
        return await self._control.start_instance(req)

    async def stop_instance(self, instance_id: str) -> dict:
        """인스턴스 중지."""
        return await self._control.stop_instance(instance_id)
