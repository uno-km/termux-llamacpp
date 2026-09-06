"""Hardware detection, multi-source CPU feature verification, and safe preset mapping."""

import ctypes
import logging
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, Any, Optional

logger = logging.getLogger("termux_llamacpp.hardware")

# [B방안] Platform SSOT: ameva-runtime.platform 에서 공유 구현을 가져옵니다.
# ameva-runtime 미설치 환경(개발 호스트 등)에서는 인라인 fallback 을 사용합니다.
try:
    from ameva_runtime.vulkan.platform import (
        is_termux as _ameva_is_termux,
        is_android as _ameva_is_android,
    )
    _AMEVA_PLATFORM_AVAILABLE = True
except ImportError:
    _AMEVA_PLATFORM_AVAILABLE = False


@dataclass
class HardwareProfile:
    """System hardware capabilities for LLM inference."""
    arch: str
    is_arm64: bool
    is_termux: bool
    is_android: bool
    cpu_count: int
    recommended_threads: int
    has_neon: bool
    has_fp16: bool
    has_dotprod: bool
    total_ram_mb: float
    available_ram_mb: float
    recommended_preset: str


def is_termux_environment() -> bool:
    """Check whether execution is running inside Android Termux.

    [B방안] ameva-runtime.platform.is_termux() 를 SSOT 로 사용합니다.
    미설치 환경에서는 인라인 구현으로 폴백합니다.
    """
    if _AMEVA_PLATFORM_AVAILABLE:
        return _ameva_is_termux()
    # inline fallback
    prefix = os.environ.get("PREFIX", "")
    return (
        "com.termux" in prefix
        or os.path.exists("/data/data/com.termux/files/usr")
        or "TERMUX_VERSION" in os.environ
    )


def is_android_environment() -> bool:
    """Check whether running on Android (via getprop, uname, or filesystem).

    [B방안] ameva-runtime.platform.is_android() 를 SSOT 로 사용합니다.
    """
    if _AMEVA_PLATFORM_AVAILABLE:
        return _ameva_is_android()
    # inline fallback
    if is_termux_environment():
        return True
    if os.path.exists("/system/build.prop"):
        return True
    try:
        res = subprocess.run(
            ["getprop", "ro.build.version.release"],
            capture_output=True, text=True, timeout=1
        )
        if res.returncode == 0 and res.stdout.strip():
            return True
    except Exception as e:
        logger.debug("[termux-llamacpp] getprop 실행 실패 (비 Android 환경에서 정상): %s", e)
    return False


def _read_hwcap_features() -> Dict[str, bool]:
    """Read Linux / Android ARM64 HWCAP and HWCAP2 via getauxval if available."""
    features = {"neon": False, "fp16": False, "dotprod": False}
    AT_HWCAP = 16
    AT_HWCAP2 = 26

    # HWCAP bitmasks for ARM64 Linux/Android
    HWCAP_ASIMD = 1 << 1
    HWCAP_FPHP = 1 << 9
    HWCAP_ASIMDDP = 1 << 20

    libc = None
    for lib_target in [None, "libc.so", "libc.so.6"]:
        try:
            libc = ctypes.CDLL(lib_target)
            if hasattr(libc, "getauxval"):
                break
        except Exception:
            libc = None

    if libc and hasattr(libc, "getauxval"):
        try:
            libc.getauxval.restype = ctypes.c_ulong
            hwcap = libc.getauxval(AT_HWCAP)
            hwcap2 = libc.getauxval(AT_HWCAP2)

            if hwcap & HWCAP_ASIMD:
                features["neon"] = True
            if hwcap & HWCAP_FPHP:
                features["fp16"] = True
            if hwcap & HWCAP_ASIMDDP:
                features["dotprod"] = True
            return features
        except Exception as e:
            logger.debug("[termux-llamacpp] getauxval HWCAP reading failed: %s", e)

    return features


def _read_cpuinfo_features() -> Dict[str, bool]:
    """Read CPU features from /proc/cpuinfo supporting standard Linux/Android ARM64 tokens."""
    features = {"neon": False, "fp16": False, "dotprod": False}
    if not os.path.exists("/proc/cpuinfo"):
        return features

    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().lower()
            features["neon"] = "neon" in content or "asimd" in content
            features["fp16"] = "fp16" in content or "fphp" in content or "asimdhp" in content
            features["dotprod"] = "dotprod" in content or "asimddp" in content
    except Exception as e:
        logger.debug("[termux-llamacpp] /proc/cpuinfo reading failed: %s", e)

    return features


def _read_cpu_features() -> Dict[str, bool]:
    """Merge multi-source CPU capability checks (getauxval, /proc/cpuinfo, arch)."""
    machine = platform.machine().lower()
    is_arm = "arm64" in machine or "aarch64" in machine

    hwcap = _read_hwcap_features()
    cpuinfo = _read_cpuinfo_features()

    features = {
        "neon": hwcap["neon"] or cpuinfo["neon"] or is_arm,
        "fp16": hwcap["fp16"] or cpuinfo["fp16"],
        "dotprod": hwcap["dotprod"] or cpuinfo["dotprod"],
    }
    return features


def _get_memory_info() -> tuple:
    """Get total and available RAM in megabytes."""
    total_mb = 4096.0
    avail_mb = 2048.0

    # 1. Linux / Android /proc/meminfo
    if os.path.exists("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        if parts[0] == "MemTotal:":
                            total_mb = float(parts[1]) / 1024.0
                        elif parts[0] in ("MemAvailable:", "MemFree:"):
                            avail_mb = float(parts[1]) / 1024.0
            return total_mb, avail_mb
        except Exception as e:
            logger.debug("[termux-llamacpp] /proc/meminfo read failed: %s", e)

    # 2. Windows GlobalMemoryStatusEx via ctypes
    if sys.platform == "win32":
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return stat.ullTotalPhys / (1024.0 * 1024.0), stat.ullAvailPhys / (1024.0 * 1024.0)
        except Exception as e:
            logger.debug("[termux-llamacpp] Windows memory detection failed: %s", e)

    # 3. macOS / POSIX sysconf
    if hasattr(os, "sysconf"):
        try:
            phys_pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            if phys_pages > 0 and page_size > 0:
                tot = (phys_pages * page_size) / (1024.0 * 1024.0)
                return tot, tot * 0.5
        except (ValueError, OSError) as e:
            logger.debug("[termux-llamacpp] POSIX sysconf memory detection failed: %s", e)

    return total_mb, avail_mb


def detect_hardware() -> HardwareProfile:
    """Detect comprehensive hardware capabilities and select conservative safe preset."""
    machine = platform.machine().lower()
    is_arm64 = "arm64" in machine or "aarch64" in machine
    # [버그 수정] 지역변수명 섀도잉 방지: is_termux_env / is_android_env 로 명명
    is_termux_env = is_termux_environment()
    is_android_env = is_android_environment()

    cpu_features = _read_cpu_features()
    total_ram, avail_ram = _get_memory_info()
    cpu_count = os.cpu_count() or 4

    if is_arm64:
        recommended_threads = 4 if cpu_count >= 8 else max(1, cpu_count - 1)
        # Conservative choice: only recommend dotprod if verified across sources
        if cpu_features["dotprod"] and cpu_features["fp16"]:
            recommended_preset = "android-arm64-dotprod"
        else:
            recommended_preset = "android-arm64-baseline"
    else:
        recommended_threads = max(1, cpu_count // 2 if cpu_count > 4 else cpu_count)
        recommended_preset = "host-native"

    return HardwareProfile(
        arch=machine,
        is_arm64=is_arm64,
        is_termux=is_termux_env,
        is_android=is_android_env,
        cpu_count=cpu_count,
        recommended_threads=recommended_threads,
        has_neon=cpu_features["neon"],
        has_fp16=cpu_features["fp16"],
        has_dotprod=cpu_features["dotprod"],
        total_ram_mb=round(total_ram, 1),
        available_ram_mb=round(avail_ram, 1),
        recommended_preset=recommended_preset,
    )


def print_hardware_summary(hw: Optional[HardwareProfile] = None):
    """Print clean, formatted hardware assessment report."""
    if hw is None:
        hw = detect_hardware()

    print("================================================================================")
    print("  termux-llamacpp Hardware & System Profile")
    print("================================================================================")
    print(f"  Architecture        : {hw.arch} (ARM64: {hw.is_arm64})")
    print(f"  Android / Termux    : Android={hw.is_android}, Termux={hw.is_termux}")
    print(f"  CPU Topology        : {hw.cpu_count} Cores (Recommended Threads: {hw.recommended_threads})")
    print(f"  SIMD Acceleration   : NEON={hw.has_neon}, FP16={hw.has_fp16}, DotProd={hw.has_dotprod}")
    print(f"  Memory Footprint    : Available {hw.available_ram_mb:.1f} MB / Total {hw.total_ram_mb:.1f} MB")
    print(f"  Recommended Preset  : {hw.recommended_preset}")
    print("================================================================================")


def _resolve_ameva_runtime() -> Optional[Any]:
    """Check for ameva_runtime availability without top-level static dependency.
    
    Returns the ameva_runtime module if installed, otherwise None.
    """
    try:
        import ameva_runtime
        return ameva_runtime
    except ImportError:
        return None


def resolve_device_backend(requested_device: str, requested_ngl: Optional[int] = None) -> tuple[str, int]:
    """Resolve the user's device= argument to an actual backend and ngl count.

    Adheres strictly to the AMEVA Decoupled Gateway Protocol:
    1. 'cpu': Always routes to pure CPU NEON without external dependency.
    2. 'auto': If ameva-runtime is absent, safely defaults to CPU NEON with explicit INFO log.
               If ameva-runtime is present, queries SmartRouter for optimal device routing.
    3. 'vulkan' / 'gpu': Requires ameva-runtime. Emits Fail-Fast error [AMEVA-LLAMA-E001] if absent.
    """
    import sys
    from termux_llamacpp.exceptions import TermuxLlamaError

    req = str(requested_device or "auto").lower().strip()
    ameva_mod = _resolve_ameva_runtime()
    ngl_target = 99 if requested_ngl is None else requested_ngl

    if req == "cpu":
        return "cpu", 0

    if req == "auto":
        if ameva_mod is None:
            sys.stdout.write("[INFO] ameva-runtime is not installed. Defaulting to ARM64 NEON CPU backend.\n")
            sys.stdout.flush()
            return "cpu", 0

        # ameva_runtime is available: evaluate via SmartRouter / Doctor
        try:
            from ameva_runtime.router import SmartRouter
            plan = SmartRouter().route_for_llm(requested_backend=None)
            logger.info("Auto-detected optimal backend via ameva-runtime: %s", plan.backend)
            return plan.backend, plan.ngl
        except Exception as e:
            # 침묵 폴백 금지: 명확한 에러 코드 분출
            raise RuntimeError(f"[ERROR: AMEVA-LLAMA-E002] Hardware evaluation failed: {e}") from e

    if req in ("vulkan", "gpu"):
        if ameva_mod is None:
            raise TermuxLlamaError(
                "[ERROR: AMEVA-LLAMA-E001] GPU acceleration requires 'ameva-runtime'.\n"
                "Cause: Hardware abstraction provider 'ameva-runtime' is not installed.\n"
                "Action Required: Install the hardware acceleration package via:\n"
                "  - Python: pip install ameva-runtime\n"
                "  - Node.js: npm install @unokm/ameva-runtime\n"
                "Documentation: https://github.com/uno-km/termux-llamacpp"
            )

        # Check native Vulkan availability via ameva-runtime Doctor probe
        try:
            from ameva_runtime import vulkan as avr
            is_vk = False
            if hasattr(avr, "is_available"):
                is_vk = avr.is_available()
            elif hasattr(avr, "create_context"):
                is_vk = avr.create_context("vulkan").backend_type == "vulkan"

            if is_vk:
                return "vulkan", ngl_target
        except Exception as e:
            logger.debug("Vulkan probe error: %s", e)

        raise TermuxLlamaError(
            "[ERROR: AMEVA-LLAMA-E002] Vulkan GPU acceleration was explicitly requested (device='vulkan' / 'gpu'), "
            "but no accessible Vulkan driver (.so) was found or validated on this system.\n"
            "Execution halted strictly without silent fallback to prevent unexpected CPU execution."
        )

    raise ValueError(f"Unsupported device '{requested_device}'. Must be one of ['auto', 'gpu', 'vulkan', 'cpu'].")
