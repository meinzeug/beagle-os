from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from gaming_metrics_service import GamingMetricsService


def make_service(tmp_path: Path) -> GamingMetricsService:
    return GamingMetricsService(
        state_dir=tmp_path,
        utcnow=lambda: "2026-04-27T10:00:00Z",
    )


def test_observe_session_deduplicates_same_sample_timestamp(tmp_path: Path) -> None:
    svc = make_service(tmp_path)
    session = {
        "session_id": "gaming-1:101",
        "pool_id": "gaming-1",
        "vmid": 101,
        "user_id": "alice",
        "assigned_at": "2026-04-27T09:55:00Z",
        "stream_health": {
            "fps": 120,
            "rtt_ms": 6,
            "dropped_frames": 0,
            "encoder_load": 58,
            "gpu_util_pct": 89,
            "gpu_temp_c": 70,
            "updated_at": "2026-04-27T10:00:00Z",
        },
    }

    svc.observe_session(session)
    svc.observe_session(session)
    payload = svc.build_dashboard()

    assert payload["overview"]["active_sessions"] == 1
    assert payload["active_sessions"][0]["sample_count"] == 1
    assert payload["active_sessions"][0]["latest_sample"]["fps"] == 120.0


def test_finalize_missing_sessions_persists_report(tmp_path: Path) -> None:
    svc = make_service(tmp_path)
    svc.observe_session(
        {
            "session_id": "gaming-1:101",
            "pool_id": "gaming-1",
            "vmid": 101,
            "user_id": "alice",
            "assigned_at": "2026-04-27T09:55:00Z",
            "stream_health": {
                "fps": 90,
                "rtt_ms": 12,
                "gpu_temp_c": 68,
                "updated_at": "2026-04-27T10:00:00Z",
            },
        }
    )

    ended = svc.finalize_missing_sessions([])

    assert len(ended) == 1
    report = json.loads((tmp_path / "gaming-1:101.json").read_text())
    assert report["session_id"] == "gaming-1:101"
    assert report["avg_fps"] == 90.0
    assert report["user_id"] == "alice"


def test_build_dashboard_filters_visible_pools_and_builds_trend(tmp_path: Path) -> None:
    svc = make_service(tmp_path)
    for idx, pool_id in enumerate(["gaming-a", "gaming-b"], start=1):
        svc.start_session(
            f"{pool_id}:10{idx}",
            vmid=100 + idx,
            pool_id=pool_id,
            user_id="u",
            started_at=f"2026-04-27T09:5{idx}:00Z",
        )
        svc.record_sample(
            f"{pool_id}:10{idx}",
            fps=60.0 + idx,
            rtt_ms=5.0 + idx,
            gpu_temp_c=65.0 + idx,
            gpu_util_pct=80.0,
            encoder_util_pct=50.0,
        )
        svc.end_session(f"{pool_id}:10{idx}")

    payload = svc.build_dashboard(visible_pool_ids={"gaming-a"}, recent_limit=10)

    assert payload["overview"]["recent_sessions"] == 1
    assert payload["recent_reports"][0]["pool_id"] == "gaming-a"
    assert len(payload["trend"]) == 1


def test_build_dashboard_uses_active_sessions_when_no_reports_exist(tmp_path: Path) -> None:
    svc = make_service(tmp_path)
    svc.observe_session(
        {
            "session_id": "gaming-live:9303",
            "pool_id": "gaming-live",
            "vmid": 9303,
            "user_id": "guest-gaming",
            "assigned_at": "2026-04-27T09:55:00Z",
            "stream_health": {
                "fps": 121,
                "rtt_ms": 7,
                "gpu_temp_c": 73,
                "gpu_util_pct": 92,
                "updated_at": "2026-04-27T10:00:00Z",
            },
        }
    )

    payload = svc.build_dashboard(visible_pool_ids={"gaming-live"}, recent_limit=10)

    assert payload["overview"]["active_sessions"] == 1
    assert payload["overview"]["avg_fps_recent"] == 121.0
    assert payload["overview"]["avg_rtt_ms_recent"] == 7.0
    assert payload["overview"]["max_gpu_temp_c_recent"] == 73.0
    assert len(payload["trend"]) == 1
    assert payload["trend"][0]["avg_fps"] == 121.0
