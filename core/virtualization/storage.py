from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class VolumeSpec:
    name: str
    size_gib: int
    format: str
    pool_name: str
    description: str = ""


@dataclass(frozen=True)
class SnapshotSpec:
    volume_id: str
    name: str
    description: str = ""


@dataclass(frozen=True)
class StoragePoolInfo:
    name: str
    driver: str
    path: str
    total_bytes: int
    used_bytes: int
    available_bytes: int
    active: bool = True
    shared: bool = False
    quota_bytes: int = 0


class StorageClass(Protocol):
    """Provider-neutral storage contract for VM volume lifecycle operations."""

    def create_volume(self, spec: VolumeSpec) -> dict[str, Any]: ...

    def delete_volume(self, volume_id: str) -> bool: ...

    def resize_volume(self, volume_id: str, size_gib: int) -> dict[str, Any]: ...

    def snapshot(self, spec: SnapshotSpec) -> dict[str, Any]: ...

    def clone(self, source_volume_id: str, target_spec: VolumeSpec, *, linked: bool = True) -> dict[str, Any]: ...

    def list_volumes(self, pool_name: str = "") -> list[dict[str, Any]]: ...
