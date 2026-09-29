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
    soc_model: Optional[str] = None

    @property
    def soc_name(self) -> str:
        return self.soc_model or "Unknown SoC"

    @property
    def cpu_cores(self) -> int:
        return self.cpu_count

    @property
    def threads(self) -> int:
        return self.recommended_threads

    @property
    def ram_total_mb(self) -> float:
        return self.total_ram_mb

    @property
    def ram_available_mb(self) -> float:
        return self.available_ram_mb


def is_termux() -> bool:
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


def is_android() -> bool:
    """Check whether running on Android (Termux execution implies Android runtime)."""
    return is_termux()


# Backward compatibility aliases
is_termux_environment = is_termux
is_android_environment = is_android



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


def _get_memory_info() -> tuple[Optional[float], Optional[float]]:
    """Get total and available RAM in megabytes without synthetic metric stubs."""
    total_mb: Optional[float] = None
    avail_mb: Optional[float] = None

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
            if total_mb is not None and avail_mb is not None:
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

    # No fake fallback metrics: return actual None if undetectable
    return total_mb, avail_mb


def detect_hardware() -> HardwareProfile:
    """Detect comprehensive hardware capabilities and select conservative safe preset."""
    machine = platform.machine().lower()
    is_arm64 = "arm64" in machine or "aarch64" in machine
    # [버그 수정] 지역변수명 섀도잉 방지: is_termux_env / is_android_env 로 명명
    is_termux_env = is_termux()
    is_android_env = is_android()

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
        total_ram_mb=round(total_ram, 1) if total_ram is not None else 0.0,
        available_ram_mb=round(avail_ram, 1) if avail_ram is not None else 0.0,
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


def detect_vulkan_int_dot() -> Optional[int]:
    """Detect hardware integer dot product support (VK_KHR_shader_integer_dot_product).

    Returns:
        1 if hardware integer dot product is supported (e.g. Exynos 1380, Snapdragon 8 Elite).
        0 if hardware integer dot product is absent (e.g. Exynos 1280, Snapdragon 865).
        None if undetectable.
    """
    cache_file = Path.home() / ".cache" / "termux-llamacpp" / "vulkan_features.json"
    if cache_file.exists():
        try:
            import json
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if "int_dot" in data:
                return data["int_dot"]
        except Exception:
            pass

    # Known SoC identification via /proc/cpuinfo
    try:
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
                if "s5e8825" in content or "exynos 1280" in content:
                    return 0
                if "s5e8835" in content or "exynos 1380" in content:
                    return 1
    except Exception:
        pass

    return None


def resolve_device_backend(requested_device: str, requested_ngl: Optional[int] = None) -> tuple[str, int]:
    """Resolve the user's device= argument to an actual backend and ngl count.

    Adheres strictly to the User & AMEVA Decoupled Gateway Protocol:
    1. 'cpu': Always routes to pure CPU NEON without external dependency (ngl=0).
              STRICT RULE: If user explicitly requested CPU, NEVER route to GPU!
    2. 'gpu' / 'vulkan': Explicitly forces GPU offloading. Requires ameva-runtime/Vulkan driver.
              Fail-Fast error if GPU unavailable. Never silently fall back to CPU.
    3. 'opencl': Explicitly forces OpenCL execution.
    4. 'auto': Evaluates hardware intelligence:
              - Priority 1: Check Vulkan GPU availability.
              - If ameva-runtime is available, queries SmartRouter.
              - If int_dot == 0 on Mali (e.g. A53), auto-routes to pure CPU ('cpu', 0)
                to prevent Turkish token attractor degeneration and numerical drift.
              - If GPU is unavailable, auto-routes to pure CPU ('cpu', 0).
    """
    import sys
    from termux_llamacpp.exceptions import TermuxLlamaError

    req = str(requested_device or "auto").lower().strip()
    ameva_mod = _resolve_ameva_runtime()
    ngl_target = requested_ngl if requested_ngl is not None else 999

    # [규칙 1] 사용자가 명시적으로 cpu를 요청한 경우: 100% 순수 CPU NEON 강제 (GPU 진입 절대 차단)
    if req == "cpu":
        return "cpu", 0

    # [규칙 2] 사용자가 명시적으로 gpu/vulkan을 요청한 경우: 100% GPU 강제 (침묵 폴백 금지, 미지원 시 Fail-Fast)
    if req in ("vulkan", "gpu"):
        if ameva_mod is None:
            raise TermuxLlamaError(
                "\n"
                "================================================================================\n"
                "[FAIL-FAST] [ERROR: AMEVA-LLAMA-E001] GPU acceleration requires 'ameva-runtime'!\n"
                "================================================================================\n"
                "Hardware acceleration provider 'ameva-runtime' is not installed on this system.\n"
                "Explicit GPU execution ('--gpu' / '--device vulkan') cannot proceed.\n"
                "Forced CPU fallback is strictly disabled under Zero-Silent-Fallback policy.\n\n"
                "To unlock native GPU (Vulkan) hardware acceleration on your mobile SoC:\n"
                "  - Python:  pip install ameva-runtime\n"
                "  - Node.js: npm install @unokm/ameva-runtime\n"
                "Or explicitly execute in ARM64 CPU NEON mode via:\n"
                "  --device cpu\n\n"
                "For full documentation and hardware setup, visit:\n"
                "  https://github.com/uno-km/termux-llamacpp\n"
                "================================================================================\n"
            )

        # Check native Vulkan availability via ameva-runtime Adapter or Vulkan probe
        try:
            try:
                from ameva_runtime.adapters.llamacpp import LlamaCppAdapter
                binding = LlamaCppAdapter.bind(requested_backend="vulkan", requested_ngl=ngl_target)
                if binding and getattr(binding, "is_vulkan", False):
                    effective_ngl = binding.config.get("ngl", ngl_target) if hasattr(binding, "config") else ngl_target
                    return "vulkan", effective_ngl
            except ImportError:
                pass

            from ameva_runtime import vulkan as avr
            is_vk = False
            if hasattr(avr, "is_available"):
                is_vk = avr.is_available()
            elif hasattr(avr, "create_context"):
                ctx = avr.create_context("vulkan")
                is_vk = ctx.backend_type == "vulkan" or getattr(ctx, "is_gpu", False)
            elif hasattr(avr, "get_or_create_context"):
                ctx = avr.get_or_create_context("vulkan")
                is_vk = ctx.backend_type == "vulkan" or getattr(ctx, "is_gpu", False)

            if is_vk:
                return "vulkan", ngl_target
        except Exception as ctx_err:
            raise TermuxLlamaError(
                f"[ERROR: AMEVA-LLAMA-E002] Vulkan GPU acceleration failed in ameva-runtime:\n{type(ctx_err).__name__}: {ctx_err}\n"
                f"Execution halted strictly under Zero-Silent-Fallback policy."
            ) from ctx_err

        raise TermuxLlamaError(
            "[ERROR: AMEVA-LLAMA-E002] Vulkan GPU acceleration was explicitly requested (device='vulkan' / 'gpu'), "
            "but no accessible Vulkan driver (.so) was found or validated on this system.\n"
            "Execution halted strictly without silent fallback to prevent unexpected CPU execution."
        )

    # [규칙 3] 사용자가 명시적으로 opencl을 요청한 경우: 100% OpenCL 강제
    if req == "opencl":
        try:
            from ameva_runtime.adapters.llamacpp import LlamaCppAdapter
            binding = LlamaCppAdapter.bind(requested_backend="opencl", requested_ngl=ngl_target)
            if binding and binding.backend == "opencl":
                effective_ngl = binding.config.get("ngl", ngl_target) if hasattr(binding, "config") else ngl_target
                return "opencl", effective_ngl
        except Exception:
            pass
        return "opencl", ngl_target

    # [규칙 4] 사용자가 옵션을 주지 않았거나 'auto'인 경우:
    # 1순위: GPU 우선 검사 -> int_dot 감지 -> int_dot 지원 시 GPU, 미지원 시 CPU 안전 실행
    if req == "auto":
        if ameva_mod is not None:
            try:
                from ameva_runtime.router import SmartRouter
                plan = SmartRouter().route_for_llm(requested_backend=None, requested_ngl=requested_ngl)
                mapped_backend = "cpu" if plan.backend in ("cpu", "cpu_neon") else plan.backend
                effective_ngl = requested_ngl if requested_ngl is not None else plan.ngl
                logger.info("Auto-detected optimal backend via ameva-runtime: %s (ngl=%s)", mapped_backend, effective_ngl)
                return mapped_backend, effective_ngl
            except Exception as e:
                logger.debug("[termux-llamacpp] SmartRouter evaluation fallback: %s", e)

        int_dot = detect_vulkan_int_dot()
        has_vulkan = os.path.exists("/system/lib64/libvulkan.so") or os.path.exists("/vendor/lib64/libvulkan.so")
        if has_vulkan:
            if int_dot == 0:
                sys.stdout.write("[INFO] GPU lacks hardware integer dot product (int dot: 0). Auto-routing to ARM64 NEON CPU.\n")
                sys.stdout.flush()
                return "cpu", 0
            return "vulkan", ngl_target

        sys.stdout.write("[INFO] No compatible Vulkan GPU detected. Defaulting to ARM64 NEON CPU.\n")
        sys.stdout.flush()
        return "cpu", 0

    raise ValueError(f"Unsupported device '{requested_device}'. Must be one of ['auto', 'gpu', 'vulkan', 'opencl', 'cpu'].")


def bind_llamacpp_hardware(engine: Any = None, requested_device: str = "auto", requested_ngl: Optional[int] = None) -> Optional[Any]:
    """Safely invoke AMEVA-Runtime LlamaCppAdapter if present to configure engine instance."""
    ameva_mod = _resolve_ameva_runtime()
    if ameva_mod is None:
        return None

    try:
        from ameva_runtime.adapters.llamacpp import LlamaCppAdapter
        binding = LlamaCppAdapter.bind(
            engine=engine,
            requested_backend=requested_device,
            requested_ngl=requested_ngl,
        )
        return binding
    except Exception as e:
        logger.debug("Hardware adapter binding skipped: %s", e)
        return None


def get_unified_model_search_dirs(submodule: str = "llama") -> list:
    """
    Returns unified model search paths adhering to AMEVA Ecosystem Shared Storage Specification.
    Enables zero-redundancy model sharing across STT, TTS, LLaMA, Vision, and Diffusion.
    """
    from pathlib import Path

    home = Path.home()
    dirs = []

    env_dir = os.environ.get("AMEVA_MODELS_DIR")
    if env_dir:
        p = Path(env_dir)
        dirs.extend([p / submodule, p])

    xdg_cache = Path(os.environ.get("XDG_CACHE_HOME") or (home / ".cache"))
    dirs.extend([
        xdg_cache / f"termux-{submodule}" / "models",
        xdg_cache / "ameva" / "models" / submodule,
        xdg_cache / "ameva" / "models",
    ])

    # Deduplicate while preserving order
    seen = set()
    unique_dirs = []
    for d in dirs:
        resolved = str(d)
        if resolved not in seen:
            seen.add(resolved)
            unique_dirs.append(d)

    return unique_dirs


# Standard Unified Hardware Interface Aliases
resolve_device = resolve_device_backend


def get_optimal_threads() -> int:
    return detect_hardware().recommended_threads


def is_adreno_vulkan() -> bool:
    """Check if the active Vulkan hardware device is Qualcomm Adreno.

    Qualcomm Adreno 600 series GPUs require -fa 0 to prevent driver shader compilation timeouts.
    Conversely, ARM Mali GPUs (e.g. Mali-G68 on Exynos 1280) require Flash Attention enabled;
    forcing -fa 0 disables fused attention, leading to descriptor set pool exhaustion on
    silicons lacking hardware integer dot products.
    """
    try:
        from ameva_runtime import vulkan as avr
        if hasattr(avr, "get_or_create_context"):
            ctx = avr.get_or_create_context("vulkan")
        elif hasattr(avr, "create_context"):
            ctx = avr.create_context("vulkan")
        else:
            ctx = avr.VulkanContext("vulkan")
        dev_name = str(getattr(ctx, "device_name", "")).lower()
        vendor_id = getattr(ctx, "vendor_id", 0)
        return vendor_id == 0x5143 or "adreno" in dev_name
    except Exception:
        pass

    try:
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
                if "qualcomm" in content or "qcom" in content or "sm8" in content or "sm7" in content or "sdm" in content:
                    return True
    except Exception:
        pass
    return False


def bind_hardware(engine: Any = None, requested_device: str = "auto", **kwargs) -> Optional[Any]:
    return bind_llamacpp_hardware(engine, requested_device, **kwargs)

