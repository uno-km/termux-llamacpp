"""
termux_llamacpp.adapter
========================
AMEVA Component Protocol v1 — Orchestrator Adapter (v0.8.1 호환)

오케스트레이터 v0.8.1이 ameva.components Entry Point로 탐색합니다.
"""
from __future__ import annotations

from typing import Any, AsyncIterator

from ameva_component.adapter_base import BaseOrchestratorAdapter
from ameva_component.exceptions import OperationNotSupported
from termux_llamacpp.control.component import LlamaCppControl


class LlamaCppOrchestratorAdapter(BaseOrchestratorAdapter):
    """LlamaCpp Orchestrator Adapter.

    LlamaCppControl을 통해 단일 진실 원천을 보장합니다.
    infer()는 현재 HTTP streaming이 서버 계층에서 처리되므로 OPERATION_NOT_SUPPORTED 반환.
    직접 streaming이 필요한 경우 서브클래스에서 오버라이드하십시오.
    """

    COMPONENT_ID = "termux-llamacpp"

    def __init__(self, control: LlamaCppControl | None = None) -> None:
        self._control = control or LlamaCppControl()

    async def infer(self, request: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """LlamaCpp inference는 내장 HTTP 서버(llama-server)를 통해 수행됩니다.
        Orchestrator 직접 streaming은 미지원 — OperationNotSupported를 발생시킵니다.

        P0-2: yield 방식은 상위 소비자가 Frame을 정상으로 처리할 위험이 있어 raise로 변경.
        """
        raise OperationNotSupported(operation="infer", component_id=self.COMPONENT_ID)
        yield  # type: ignore[misc]


def create_adapter() -> LlamaCppOrchestratorAdapter:
    """Entry Point Factory. 오케스트레이터가 ameva.components 그룹에서 호출합니다."""
    return LlamaCppOrchestratorAdapter()
