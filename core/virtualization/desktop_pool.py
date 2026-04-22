from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from core.virtualization.streaming_profile import StreamingProfile


class DesktopPoolMode(str, Enum):
    FLOATING_NON_PERSISTENT = "floating_non_persistent"
    FLOATING_PERSISTENT = "floating_persistent"
    DEDICATED = "dedicated"


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
    enabled: bool = True
    labels: tuple[str, ...] = field(default_factory=tuple)
    streaming_profile: StreamingProfile | None = None


@dataclass(frozen=True)
class DesktopLease:
    pool_id: str
    vmid: int
    user_id: str
    mode: DesktopPoolMode
    state: str
    assigned_at: str = ""


@dataclass(frozen=True)
class DesktopPoolInfo:
    pool_id: str
    template_id: str
    mode: DesktopPoolMode
    min_pool_size: int
    max_pool_size: int
    warm_pool_size: int
    free_desktops: int
    in_use_desktops: int
    recycling_desktops: int
    error_desktops: int
    enabled: bool = True
    streaming_profile: StreamingProfile | None = None


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
