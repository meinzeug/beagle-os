"""Tests for Gaming Pool Type + Gaming Metrics (GoEnterprise Plan 03)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from core.virtualization.desktop_pool import DesktopPoolType, DesktopPoolSpec, DesktopPoolMode
from gaming_metrics_service import GamingMetricsService


# ------------------------------------------------------------------
# Pool Type tests
# ------------------------------------------------------------------

def test_pool_type_default_is_desktop():
    spec = DesktopPoolSpec(
        pool_id="p1",
        template_id="t1",
        mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
        min_pool_size=1,
        max_pool_size=5,
        warm_pool_size=1,
        cpu_cores=2,
        memory_mib=4096,
        storage_pool="default",
    )
    assert spec.pool_type == DesktopPoolType.DESKTOP


def test_gaming_pool_type():
    spec = DesktopPoolSpec(
        pool_id="gaming-1",
        template_id="t1",
        mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
        min_pool_size=1,
        max_pool_size=10,
        warm_pool_size=2,
        cpu_cores=8,
        memory_mib=16384,
        storage_pool="default",
        gpu_class="rtx4090",
        pool_type=DesktopPoolType.GAMING,
    )
    assert spec.pool_type == DesktopPoolType.GAMING
    assert spec.gpu_class == "rtx4090"


def test_kiosk_pool_with_time_limit():
    spec = DesktopPoolSpec(
        pool_id="kiosk-1",
        template_id="t1",
        mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
        min_pool_size=1,
        max_pool_size=20,
        warm_pool_size=5,
        cpu_cores=4,
        memory_mib=8192,
        storage_pool="default",
        pool_type=DesktopPoolType.KIOSK,
        session_time_limit_minutes=60,
        session_cost_per_minute=0.05,
    )
    assert spec.pool_type == DesktopPoolType.KIOSK
    assert spec.session_time_limit_minutes == 60
    assert spec.session_cost_per_minute == 0.05


# ------------------------------------------------------------------
# Gaming Metrics tests
# ------------------------------------------------------------------

def make_metrics_svc(tmp_path: Path) -> GamingMetricsService:
    return GamingMetricsService(
        state_dir=tmp_path,
        utcnow=lambda: "2026-04-25T14:30:00Z",
    )


def test_start_session(tmp_path):
    svc = make_metrics_svc(tmp_path)
    m = svc.start_session("sess-1", vmid=100, pool_id="gaming-pool", user_id="alice")
    assert m.session_id == "sess-1"
    assert m.vmid == 100


def test_record_samples_and_averages(tmp_path):
    svc = make_metrics_svc(tmp_path)
    svc.start_session("sess-1", vmid=100, pool_id="p1", user_id="alice")
    for fps in [120.0, 118.0, 122.0]:
        svc.record_sample("sess-1", fps=fps, rtt_ms=2.5, gpu_util_pct=85.0, gpu_temp_c=70.0, encoder_util_pct=60.0)
    svc2 = svc._sessions["sess-1"]
    assert abs(svc2.avg_fps() - 120.0) < 1.0


def test_end_session_writes_file(tmp_path):
    svc = make_metrics_svc(tmp_path)
    svc.start_session("sess-1", vmid=100, pool_id="p1", user_id="alice")
    svc.record_sample("sess-1", fps=60.0, rtt_ms=3.0, gpu_util_pct=70.0, gpu_temp_c=65.0, encoder_util_pct=50.0)
    summary = svc.end_session("sess-1")
    assert summary["avg_fps"] == 60.0
    assert (tmp_path / "sess-1.json").exists()


def test_alert_low_fps(tmp_path):
    svc = make_metrics_svc(tmp_path)
    svc.start_session("sess-1", vmid=100, pool_id="p1", user_id="alice")
    for _ in range(3):
        svc.record_sample("sess-1", fps=20.0, rtt_ms=3.0, gpu_util_pct=50.0, gpu_temp_c=60.0, encoder_util_pct=40.0)
    alerts = svc.check_alerts("sess-1", fps_threshold=30.0)
    assert any("low_fps" in a for a in alerts)


def test_alert_high_rtt(tmp_path):
    svc = make_metrics_svc(tmp_path)
    svc.start_session("sess-1", vmid=100, pool_id="p1", user_id="alice")
    for _ in range(3):
        svc.record_sample("sess-1", fps=60.0, rtt_ms=80.0, gpu_util_pct=50.0, gpu_temp_c=60.0, encoder_util_pct=40.0)
    alerts = svc.check_alerts("sess-1", rtt_threshold_ms=50.0)
    assert any("high_rtt" in a for a in alerts)


def test_get_active_sessions(tmp_path):
    svc = make_metrics_svc(tmp_path)
    svc.start_session("sess-1", vmid=100, pool_id="p1", user_id="alice")
    svc.start_session("sess-2", vmid=101, pool_id="p1", user_id="bob")
    active = svc.get_active_sessions()
    assert len(active) == 2
