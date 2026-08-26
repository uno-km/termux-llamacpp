"""Custom exceptions for termux-llamacpp."""

import sys


class TermuxLlamaError(Exception):
    """Base exception for all termux-llamacpp errors."""
    pass


class SecurityVerificationError(TermuxLlamaError):
    """Raised when cryptographic verification, provenance validation, or manifest integrity fails."""
    pass


class ModelNotFoundError(TermuxLlamaError):
    """Raised when a requested GGUF model file or alias does not exist locally."""

    def __init__(self, model_identifier: str, search_path: str = ""):
        self.model_identifier = model_identifier
        self.search_path = search_path
        msg = (
            f"\n"
            f"================================================================================\n"
            f"[termux-llamacpp] MODEL NOT FOUND: '{model_identifier}'\n"
            f"================================================================================\n"
            f"지정된 GGUF 모델을 로컬 디렉터리에서 찾을 수 없습니다.\n"
            f"검색 경로: {search_path or '기본 모델 저장소 (~/.termux-llama/models/)'}\n\n"
            f"해결 방법:\n"
            f"  1. 사전 큐레이션 모델 다운로드:\n"
            f"     termux-llama download qwen2.5-1.5b-instruct\n\n"
            f"  2. Hugging Face에서 직접 다운로드:\n"
            f"     termux-llama download <repo_id> <filename>\n\n"
            f"  3. 로컬 모델 목록 확인:\n"
            f"     termux-llama list\n"
            f"================================================================================"
        )
        super().__init__(msg)


class DependencyMissingError(TermuxLlamaError):
    """Raised when an optional dependency (such as termux-playwright) is required but missing."""

    def __init__(self, package_name: str = "termux-playwright", reason: str = ""):
        self.package_name = package_name
        self.reason = reason or "Hugging Face 동적 페이지 렌더링 및 심층 GGUF 파일 크롤링"
        msg = (
            f"\n"
            f"================================================================================\n"
            f"[termux-llamacpp] DEPENDENCY MISSING: '{package_name}' is not installed!\n"
            f"================================================================================\n"
            f"{self.reason}을(를) 수행하려면 '{package_name}' 패키지가 필요합니다.\n\n"
            f"다음 명령어를 실행하여 설치를 진행하십시오:\n"
            f"  - Python 환경:  pip install {package_name}\n"
            f"  - Node.js 환경: npm install {package_name}\n\n"
            f"참고: 기본 REST API 기반 검색 모드를 사용하려면 deep_crawl=False 로 호출하십시오.\n"
            f"================================================================================"
        )
        super().__init__(msg)


class RuntimeBuildError(TermuxLlamaError):
    """Raised when native llama.cpp compilation or binary installation fails."""
    pass


class ServerStartupError(TermuxLlamaError):
    """Raised when llama-server process fails to start or healthcheck fails."""
    pass
