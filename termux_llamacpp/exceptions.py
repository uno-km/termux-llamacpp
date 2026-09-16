"""
AMEVA Unified Exception Hierarchy for Termux AI Engines.
Component: [LLAMA]
"""
from typing import Optional, Any, List


class AmevaTermuxError(Exception):
    """Root exception for all Termux On-Device AI Engines."""
    COMPONENT_TAG = "[LLAMA]"
    DEFAULT_CODE = "E000_UNKNOWN"

    def __init__(self, message: str = "", code: Optional[Any] = None, details: Optional[Any] = None):
        self.code = code or self.DEFAULT_CODE
        self.details = details
        self.raw_message = message
        super().__init__(message)


TermuxLlamaError = AmevaTermuxError


class PlatformNotSupportedError(AmevaTermuxError):
    DEFAULT_CODE = "E002_PLATFORM_NOT_SUPPORTED"


class HardwareCompatibilityError(AmevaTermuxError):
    DEFAULT_CODE = "E003_HARDWARE_INCOMPATIBLE"


class RuntimeNotFoundError(AmevaTermuxError):
    DEFAULT_CODE = "E004_RUNTIME_NOT_FOUND"


class ProvisioningError(AmevaTermuxError):
    DEFAULT_CODE = "E005_PROVISIONING_FAILED"


class InferenceTimeoutError(AmevaTermuxError):
    DEFAULT_CODE = "E006_INFERENCE_TIMEOUT"


class InferenceExecutionError(AmevaTermuxError):
    DEFAULT_CODE = "E007_INFERENCE_FAILED"


class ModelCorruptedError(AmevaTermuxError):
    DEFAULT_CODE = "E008_MODEL_CORRUPTED"


class ModelDownloadError(ProvisioningError):
    DEFAULT_CODE = "E009_MODEL_DOWNLOAD_FAILED"


class SecurityVerificationError(TermuxLlamaError):
    DEFAULT_CODE = "E301_SECURITY_VERIFICATION_FAILED"


class RuntimeBuildError(TermuxLlamaError):
    DEFAULT_CODE = "E303_RUNTIME_BUILD_FAILED"


class ServerStartupError(TermuxLlamaError):
    DEFAULT_CODE = "E304_SERVER_STARTUP_FAILED"


class ModelNotFoundError(TermuxLlamaError):
    def __init__(self, model_identifier: str = "", search_path: str = "", message: str = ""):
        self.model_identifier = model_identifier
        self.search_path = search_path
        if not message:
            message = (
                f"\n"
                f"================================================================================\n"
                f"[termux-llamacpp] MODEL NOT FOUND: '{model_identifier}'\n"
                f"================================================================================\n"
                f"지정된 GGUF 모델을 로컬 디렉터리에서 찾을 수 없습니다.\n"
                f"검색 경로: {search_path or '기본 모델 저장소 (~/.cache/termux-llamacpp/models/)'}\n\n"
                f"해결 방법:\n"
                f"  1. 사전 큐레이션 모델 다운로드:\n"
                f"     termux-llama download qwen2.5-1.5b-instruct\n\n"
                f"  2. Hugging Face에서 직접 다운로드:\n"
                f"     termux-llama download <repo_id> <filename>\n\n"
                f"  3. 로컬 모델 목록 확인:\n"
                f"     termux-llama list\n"
                f"================================================================================"
            )
        super().__init__(message)


class DependencyMissingError(TermuxLlamaError):
    def __init__(self, package_name: str = "termux-playwright", reason: str = "", message: str = ""):
        self.package_name = package_name
        self.reason = reason or "Hugging Face 동적 페이지 렌더링 및 심층 GGUF 파일 크롤링"
        if not message:
            message = (
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
        super().__init__(message)


class ModelNotSpecifiedError(TermuxLlamaError):
    def __init__(self, search_path: str = "", message: str = ""):
        self.search_path = search_path
        if not message:
            message = (
                f"\n"
                f"================================================================================\n"
                f"[termux-llamacpp] MODEL NOT SPECIFIED (Zero-Silent-Fallback)\n"
                f"================================================================================\n"
                f"실행할 GGUF 모델 식별자가 지정되지 않았습니다.\n"
                f"임의의 캐시 파일 무단 할당(Silent Fallback)은 엄격히 금지되어 있습니다.\n\n"
                f"해결 방법:\n"
                f"  1. 큐레이션 모델 다운로드 후 지정:\n"
                f"     termux-llama download qwen2.5-0.5b-instruct\n"
                f"     termux-llama run qwen2.5-0.5b-instruct \"Hello\"\n\n"
                f"  2. Hugging Face 레포지토리 직접 다운로드:\n"
                f"     termux-llama download Qwen/Qwen2.5-0.5B-Instruct-GGUF qwen2.5-0.5b-instruct-q4_k_m.gguf\n\n"
                f"  3. 로컬 캐시된 모델 확인:\n"
                f"     termux-llama list\n"
                f"================================================================================"
            )
        super().__init__(message)


class InvalidModelIdentifierError(TermuxLlamaError):
    def __init__(self, model_identifier: str = "", available_models: list = None, message: str = ""):
        self.model_identifier = model_identifier
        avail = available_models or []
        avail_str = "\n".join(f"    - {m}" for m in avail) if avail else "    (termux-llama models 명령으로 확인 가능)"
        if not message:
            message = (
                f"\n"
                f"================================================================================\n"
                f"[termux-llamacpp] INVALID MODEL IDENTIFIER: '{model_identifier}'\n"
                f"================================================================================\n"
                f"'{model_identifier}' 은(는) 등록된 모델 별칭이나 유효한 로컬 .gguf 파일이 아닙니다.\n"
                f"미등록 모델 입력을 임의로 프롬프트로 변조하거나 조용히 넘기는 행위는 금지되어 있습니다.\n\n"
                f"추천 큐레이션 모델 목록:\n{avail_str}\n\n"
                f"다운로드 예시:\n"
                f"  termux-llama download {avail[0] if avail else 'qwen2.5-0.5b-instruct'}\n"
                f"================================================================================"
            )
        super().__init__(message)
