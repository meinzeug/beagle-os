from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from core.virtualization.streaming_profile import StreamingProfile


class DesktopPoolMode(str, Enum):
    FLOATING_NON_PERSISTENT = "floating_non_persistent"
    FLOATING_PERSISTENT = "floating_persistent"
    DEDICATED = "dedicated"


class DesktopPoolType(str, Enum):
    """GoEnterprise Plan 03/10: Pool-Typ für unterschiedliche Workloads."""
    DESKTOP = "desktop"             # Standard VDI Desktop
    GAMING = "gaming"               # GPU-Pflicht, hohe Bitrate, gaming-grade FPS
    KIOSK = "kiosk"                 # Session-Time-Limit, stateless (VM-Reset nach Session)
    GPU_PASSTHROUGH = "gpu_passthrough"  # Exklusive GPU-Zuweisung via PCI-Passthrough
    GPU_TIMESLICE = "gpu_timeslice"      # Geteilte GPU via CUDA Time-Slicing (N VMs, 1 GPU)
    GPU_VGPU = "gpu_vgpu"               # NVIDIA vGPU (mdev) — Hardware-vGPU pro VM


class SessionRecordingPolicy(str, Enum):
    DISABLED = "disabled"
    ON_DEMAND = "on_demand"
    ALWAYS = "always"


@dataclass(frozen=True)
class DesktopPoolSpec:
    pool_id: str
    template_id: str
    mode: DesktopPoolMode
    min_pool_size: int
    max_pool_size: int
    warm_pool_size: int
    cpu_cores: int
    memory_mib: int
    storage_pool: str
    gpu_class: str = ""
    session_recording: SessionRecordingPolicy = SessionRecordingPolicy.DISABLED
    recording_retention_days: int = 30
    recording_watermark_enabled: bool = False
    recording_watermark_custom_text: str = ""
    enabled: bool = True
    labels: tuple[str, ...] = field(default_factory=tuple)
    streaming_profile: StreamingProfile | None = None
    tenant_id: str = ""
    # GoEnterprise Plan 03: Gaming/Kiosk pools
    pool_type: DesktopPoolType = DesktopPoolType.DESKTOP
    session_time_limit_minutes: int = 0     # 0 = unlimited (kiosk: set >0)
    session_cost_per_minute: float = 0.0    # for kiosk billing
    session_extension_options_minutes: tuple[int, ...] = (15, 30, 60)


@dataclass(frozen=True)
class DesktopLease:
    pool_id: str
    vmid: int
    user_id: str
    mode: DesktopPoolMode
    state: str
    assigned_at: str = ""
    stream_health: dict | None = None


@dataclass(frozen=True)
class DesktopPoolInfo:
    pool_id: str
    template_id: str
    mode: DesktopPoolMode
    min_pool_size: int
    max_pool_size: int
    warm_pool_size: int
    gpu_class: str
    session_recording: SessionRecordingPolicy
    recording_retention_days: int
    free_desktops: int
    in_use_desktops: int
    recycling_desktops: int
    error_desktops: int
    enabled: bool = True
    streaming_profile: StreamingProfile | None = None
    recording_watermark_enabled: bool = False
    recording_watermark_custom_text: str = ""
    tenant_id: str = ""
    pool_type: DesktopPoolType = DesktopPoolType.DESKTOP
    session_time_limit_minutes: int = 0
    session_cost_per_minute: float = 0.0
    session_extension_options_minutes: tuple[int, ...] = (15, 30, 60)


class DesktopPool(Protocol):
    """Provider-neutral desktop pool contract for VDI allocation lifecycle."""

    def create_pool(self, spec: DesktopPoolSpec) -> DesktopPoolInfo: ...

    def get_pool(self, pool_id: str) -> DesktopPoolInfo | None: ...

    def list_pools(self) -> list[DesktopPoolInfo]: ...

    def delete_pool(self, pool_id: str) -> bool: ...

    def scale_pool(self, pool_id: str, target_size: int) -> DesktopPoolInfo: ...

    def allocate_desktop(self, pool_id: str, user_id: str) -> DesktopLease: ...

    def release_desktop(self, pool_id: str, vmid: int, user_id: str) -> DesktopLease: ...

    def recycle_desktop(self, pool_id: str, vmid: int) -> DesktopLease: ...
