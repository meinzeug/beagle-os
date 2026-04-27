"""Integration test for VDI pool lifecycle."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
for subdir in ("services",):
    services_dir = ROOT / "beagle-host" / subdir
    if str(services_dir) not in sys.path:
        sys.path.insert(0, str(services_dir))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.virtualization.desktop_pool import DesktopPoolMode, DesktopPoolSpec, DesktopPoolType
from pool_manager import PoolManagerService


def _build_service(tmp_path: Path) -> PoolManagerService:
    return PoolManagerService(
        state_file=tmp_path / "desktop-pools.json",
        utcnow=lambda: "2026-04-27T12:00:00Z",
    )


def test_vdi_pool_lifecycle_allocate_update_release_recycle(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    service.create_pool(
        DesktopPoolSpec(
            pool_id="pool-vdi",
            template_id="tpl-vdi",
            mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
            min_pool_size=1,
            max_pool_size=3,
            warm_pool_size=1,
            cpu_cores=4,
            memory_mib=8192,
            storage_pool="local",
            pool_type=DesktopPoolType.DESKTOP,
        )
    )
    service.register_vm("pool-vdi", 701)
    service.register_vm("pool-vdi", 702)

    assert service.list_desktops("pool-vdi")[0]["state"] == "free"

    lease = service.allocate_desktop("pool-vdi", "alice")
    assert lease.vmid == 701
    assert lease.state == "in_use"
    assert service.list_active_sessions()[0]["vmid"] == 701

    updated = service.update_stream_health(
        pool_id="pool-vdi",
        vmid=701,
        stream_health={
            "rtt_ms": 14,
            "fps": 60,
            "dropped_frames": 1,
            "encoder_load": 82,
            "window_title": "Steam - Hades",
        },
    )
    assert updated.stream_health is not None
    assert updated.stream_health["window_title"] == "Steam - Hades"

    released = service.release_desktop("pool-vdi", 701, "alice")
    assert released.state == "recycling"
    assert service.list_active_sessions() == []

    recycled = service.recycle_desktop("pool-vdi", 701)
    assert recycled.state == "free"
    assert service.list_desktops("pool-vdi")[0]["state"] == "free"


def test_vdi_pool_scale_respects_maximum(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    service.create_pool(
        DesktopPoolSpec(
            pool_id="pool-scale",
            template_id="tpl-vdi",
            mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
            min_pool_size=1,
            max_pool_size=3,
            warm_pool_size=1,
            cpu_cores=4,
            memory_mib=8192,
            storage_pool="local",
            pool_type=DesktopPoolType.DESKTOP,
        )
    )
    info = service.scale_pool("pool-scale", 99)
    assert info.warm_pool_size == 3
