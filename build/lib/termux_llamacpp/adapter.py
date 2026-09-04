"""
termux_llamacpp.adapter
========================
AMEVA Component Protocol v1 — Orchestrator Adapter (v0.8.1 호환)

오케스트레이터 v0.8.1이 ameva.components Entry Point로 탐색합니다.
"""
from __future__ import annotations

from typing import Any, AsyncIterator

from ameva_component.adapter_base import BaseOrchestratorAdapter
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
        Orchestrator 직접 streaming은 OPERATION_NOT_SUPPORTED — 서버 URL을 사용하십시오.
        """
        yield self._not_supported("infer")


def create_adapter() -> LlamaCppOrchestratorAdapter:
    """Entry Point Factory. 오케스트레이터가 ameva.components 그룹에서 호출합니다."""
    return LlamaCppOrchestratorAdapter()
