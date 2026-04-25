"""Tests for Session Time Limit in Pool Manager (GoEnterprise Plan 03, Schritt 3)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from pool_manager import PoolManagerService
from core.virtualization.desktop_pool import (
    DesktopPoolSpec, DesktopPoolMode, DesktopPoolType, SessionRecordingPolicy
)


def make_svc(tmp_path: Path, utcnow=None) -> PoolManagerService:
    return PoolManagerService(
        state_file=tmp_path / "pools.json",
        utcnow=utcnow or (lambda: "2026-04-25T12:00:00Z"),
    )


def make_kiosk_spec(pool_id="kiosk-1", time_limit=30) -> DesktopPoolSpec:
    return DesktopPoolSpec(
        pool_id=pool_id,
        template_id="tpl-kiosk",
        mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
        min_pool_size=1,
        max_pool_size=5,
        warm_pool_size=2,
        cpu_cores=4,
        memory_mib=8192,
        storage_pool="local",
        pool_type=DesktopPoolType.KIOSK,
        session_time_limit_minutes=time_limit,
    )


def make_gaming_spec(pool_id="gaming-1") -> DesktopPoolSpec:
    return DesktopPoolSpec(
        pool_id=pool_id,
        template_id="tpl-gaming",
        mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
        min_pool_size=1,
        max_pool_size=4,
        warm_pool_size=2,
        cpu_cores=8,
        memory_mib=16384,
        storage_pool="local",
        pool_type=DesktopPoolType.GAMING,
        gpu_class="passthrough-nvidia-rtx3090",
    )


def test_create_kiosk_pool_stores_type(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_pool(make_kiosk_spec())
    info = svc.get_pool("kiosk-1")
    assert info is not None
    assert info.pool_type == DesktopPoolType.KIOSK
    assert info.session_time_limit_minutes == 30


def test_create_gaming_pool_stores_type(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_pool(make_gaming_spec())
    info = svc.get_pool("gaming-1")
    assert info is not None
    assert info.pool_type == DesktopPoolType.GAMING


def test_time_remaining_unlimited_pool(tmp_path):
    svc = make_svc(tmp_path)
    spec = DesktopPoolSpec(
        pool_id="desktop-1",
        template_id="tpl",
        mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
        min_pool_size=1, max_pool_size=5, warm_pool_size=2,
        cpu_cores=2, memory_mib=4096, storage_pool="local",
        pool_type=DesktopPoolType.DESKTOP,
        session_time_limit_minutes=0,
    )
    svc.create_pool(spec)
    # Add a free VM
    state = svc._load()
    state["vms"]["100"] = {
        "vmid": 100, "pool_id": "desktop-1", "state": "in_use",
        "user_id": "alice", "assigned_at": "2026-04-25T12:00:00Z", "stream_health": None,
    }
    svc._save(state)
    remaining = svc.time_remaining_seconds("desktop-1", 100)
    assert remaining == pytest.approx(-1.0)


def test_time_remaining_limited_session(tmp_path):
    # Session started 10 minutes ago, limit is 30 minutes
    call_count = [0]
    def utcnow():
        call_count[0] += 1
        if call_count[0] <= 2:  # pool creation + vm assignment
            return "2026-04-25T12:00:00Z"
        return "2026-04-25T12:10:00Z"  # 10 minutes later

    svc = make_svc(tmp_path, utcnow=utcnow)
    svc.create_pool(make_kiosk_spec(time_limit=30))
    # Manually add in_use VM with known assigned_at
    state = svc._load()
    state["vms"]["100"] = {
        "vmid": 100, "pool_id": "kiosk-1", "state": "in_use",
        "user_id": "user1", "assigned_at": "2026-04-25T12:00:00Z", "stream_health": None,
    }
    svc._save(state)

    # Create new svc instance with "10 minutes later" time
    svc2 = make_svc(tmp_path, utcnow=lambda: "2026-04-25T12:10:00Z")
    remaining = svc2.time_remaining_seconds("kiosk-1", 100)
    # 30min * 60 - 10min * 60 = 1200s remaining
    assert abs(remaining - 1200.0) < 5.0


def test_expire_overdue_sessions(tmp_path):
    # Session started 31 minutes ago, limit 30 minutes → should expire
    svc = make_svc(tmp_path, utcnow=lambda: "2026-04-25T12:31:00Z")
    svc.create_pool(make_kiosk_spec(time_limit=30))

    state = svc._load()
    state["vms"]["100"] = {
        "vmid": 100, "pool_id": "kiosk-1", "state": "in_use",
        "user_id": "user1", "assigned_at": "2026-04-25T12:00:00Z", "stream_health": None,
    }
    svc._save(state)

    expired = svc.expire_overdue_sessions()
    assert len(expired) == 1
    assert expired[0]["vmid"] == 100

    # VM should now be marked expired
    state2 = svc._load()
    assert state2["vms"]["100"]["state"] == "expired"


def test_expire_does_not_touch_unlimited_sessions(tmp_path):
    svc = make_svc(tmp_path, utcnow=lambda: "2026-04-25T23:00:00Z")
    # Desktop pool with no time limit
    spec = DesktopPoolSpec(
        pool_id="desktop-2",
        template_id="tpl",
        mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
        min_pool_size=1, max_pool_size=5, warm_pool_size=2,
        cpu_cores=2, memory_mib=4096, storage_pool="local",
        session_time_limit_minutes=0,
    )
    svc.create_pool(spec)
    state = svc._load()
    state["vms"]["200"] = {
        "vmid": 200, "pool_id": "desktop-2", "state": "in_use",
        "user_id": "alice", "assigned_at": "2026-04-25T08:00:00Z", "stream_health": None,
    }
    svc._save(state)

    expired = svc.expire_overdue_sessions()
    assert expired == []


def test_kiosk_reset_triggered_on_expire(tmp_path):
    reset_calls = []
    svc = PoolManagerService(
        state_file=tmp_path / "pools.json",
        utcnow=lambda: "2026-04-25T12:31:00Z",
        reset_vm_to_template=lambda vmid, tpl: reset_calls.append(vmid),
    )
    svc.create_pool(make_kiosk_spec(time_limit=30))
    state = svc._load()
    state["vms"]["100"] = {
        "vmid": 100, "pool_id": "kiosk-1", "state": "in_use",
        "user_id": "user1", "assigned_at": "2026-04-25T12:00:00Z", "stream_health": None,
    }
    svc._save(state)
    svc.expire_overdue_sessions()
    assert 100 in reset_calls
