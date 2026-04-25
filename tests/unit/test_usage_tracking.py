"""Tests for Usage Tracking Service (GoEnterprise Plan 05, Schritt 2)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from usage_tracking_service import UsageTrackingService, UsageRecord


def make_svc(tmp_path: Path) -> UsageTrackingService:
    return UsageTrackingService(db_file=tmp_path / "usage.json")


def test_record_session_returns_usage_record(tmp_path):
    svc = make_svc(tmp_path)
    rec = svc.record_session(
        session_id="s-001",
        user_id="alice",
        department="marketing",
        pool_id="pool-desktop",
        vm_id=100,
        start_time="2026-04-01T08:00:00Z",
        end_time="2026-04-01T10:00:00Z",
        cpu_cores=2,
        ram_gb=8.0,
    )
    assert isinstance(rec, UsageRecord)
    assert rec.session_id == "s-001"
    assert rec.duration_seconds == 7200.0
    assert rec.cpu_hours == pytest.approx(4.0)   # 2 cores × 2h
    assert rec.month == "2026-04"


def test_record_session_persists_to_disk(tmp_path):
    svc = make_svc(tmp_path)
    svc.record_session(
        session_id="s-002",
        user_id="bob",
        department="engineering",
        pool_id="pool-dev",
        vm_id=101,
        start_time="2026-04-02T09:00:00Z",
        end_time="2026-04-02T09:30:00Z",
    )
    svc2 = make_svc(tmp_path)
    records = svc2.get_usage()
    assert any(r["session_id"] == "s-002" for r in records)


def test_get_usage_filter_by_month(tmp_path):
    svc = make_svc(tmp_path)
    svc.record_session(
        session_id="s-apr",
        user_id="alice",
        department="marketing",
        pool_id="p1",
        vm_id=100,
        start_time="2026-04-01T08:00:00Z",
        end_time="2026-04-01T09:00:00Z",
    )
    svc.record_session(
        session_id="s-may",
        user_id="alice",
        department="marketing",
        pool_id="p1",
        vm_id=100,
        start_time="2026-05-01T08:00:00Z",
        end_time="2026-05-01T09:00:00Z",
    )
    april = svc.get_usage(month="2026-04")
    assert len(april) == 1
    assert april[0]["session_id"] == "s-apr"


def test_get_usage_filter_by_department(tmp_path):
    svc = make_svc(tmp_path)
    for dept in ("marketing", "engineering", "marketing"):
        svc.record_session(
            session_id=f"s-{dept}-{dept}",
            user_id="user",
            department=dept,
            pool_id="p1",
            vm_id=100,
            start_time="2026-04-01T08:00:00Z",
            end_time="2026-04-01T09:00:00Z",
        )
    mkt = svc.get_usage(department="marketing")
    assert len(mkt) == 2
    assert all(r["department"] == "marketing" for r in mkt)


def test_get_usage_filter_by_user(tmp_path):
    svc = make_svc(tmp_path)
    for user in ("alice", "bob", "alice"):
        svc.record_session(
            session_id=f"s-{user}-{user}",
            user_id=user,
            department="eng",
            pool_id="p1",
            vm_id=100,
            start_time="2026-04-01T08:00:00Z",
            end_time="2026-04-01T09:00:00Z",
        )
    alice = svc.get_usage(user_id="alice")
    assert len(alice) == 2
    assert all(r["user_id"] == "alice" for r in alice)


def test_gpu_session_records_gpu_hours(tmp_path):
    svc = make_svc(tmp_path)
    rec = svc.record_session(
        session_id="s-gpu",
        user_id="gamer",
        department="gaming",
        pool_id="pool-gaming",
        vm_id=200,
        start_time="2026-04-01T10:00:00Z",
        end_time="2026-04-01T12:00:00Z",
        gpu_slots=1,
    )
    assert rec.gpu_hours == pytest.approx(2.0)


def test_five_sessions_for_alice_correct_sum(tmp_path):
    svc = make_svc(tmp_path)
    for i in range(5):
        svc.record_session(
            session_id=f"alice-s{i}",
            user_id="alice",
            department="marketing",
            pool_id="pool-desktop",
            vm_id=100,
            start_time=f"2026-04-0{i+1}T08:00:00Z",
            end_time=f"2026-04-0{i+1}T10:00:00Z",
            cpu_cores=2,
            ram_gb=4.0,
        )
    records = svc.get_usage(user_id="alice", month="2026-04")
    assert len(records) == 5
    total_cpu_hours = sum(r["cpu_hours"] for r in records)
    assert total_cpu_hours == pytest.approx(20.0)  # 5 × 2 cores × 2h
