from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from pool_manager import PoolManagerService
from core.virtualization.desktop_pool import DesktopPoolSpec, DesktopPoolMode, DesktopPoolType


def _kiosk_spec() -> DesktopPoolSpec:
    return DesktopPoolSpec(
        pool_id="kiosk-1",
        template_id="tpl-kiosk",
        mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
        min_pool_size=1,
        max_pool_size=1,
        warm_pool_size=1,
        cpu_cores=2,
        memory_mib=4096,
        storage_pool="local",
        pool_type=DesktopPoolType.KIOSK,
        session_time_limit_minutes=30,
    )


def test_kiosk_release_resets_vm_to_template_and_marks_vm_free(tmp_path: Path) -> None:
    reset_calls: list[tuple[int, str]] = []
    stop_calls: list[int] = []
    svc = PoolManagerService(
        state_file=tmp_path / "pools.json",
        utcnow=lambda: "2026-04-27T16:00:00Z",
        stop_vm=lambda vmid: stop_calls.append(vmid),
        reset_vm_to_template=lambda vmid, tpl: reset_calls.append((vmid, tpl)),
    )
    svc.create_pool(_kiosk_spec())
    state = svc._load()
    state["vms"]["100"] = {
        "vmid": 100,
        "pool_id": "kiosk-1",
        "state": "in_use",
        "user_id": "alice",
        "assigned_at": "2026-04-27T15:30:00Z",
        "stream_health": None,
    }
    svc._save(state)

    lease = svc.release_desktop("kiosk-1", 100, "alice")

    assert lease.state == "free"
    assert stop_calls == [100]
    assert reset_calls == [(100, "tpl-kiosk")]
    assert svc._load()["vms"]["100"]["state"] == "free"


def test_kiosk_expire_reuses_release_path_and_resets_vm(tmp_path: Path) -> None:
    reset_calls: list[tuple[int, str]] = []
    svc = PoolManagerService(
        state_file=tmp_path / "pools.json",
        utcnow=lambda: "2026-04-27T16:00:00Z",
        reset_vm_to_template=lambda vmid, tpl: reset_calls.append((vmid, tpl)),
    )
    svc.create_pool(_kiosk_spec())
    state = svc._load()
    state["vms"]["100"] = {
        "vmid": 100,
        "pool_id": "kiosk-1",
        "state": "in_use",
        "user_id": "alice",
        "assigned_at": "2026-04-27T15:20:00Z",
        "stream_health": None,
    }
    svc._save(state)

    expired = svc.expire_overdue_sessions()

    assert expired == [{"pool_id": "kiosk-1", "vmid": 100, "user_id": "alice"}]
    assert reset_calls == [(100, "tpl-kiosk")]
    assert svc._load()["vms"]["100"]["state"] == "free"
