"""Unit tests for session geo-routing and handover history."""
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from session_manager import SessionManagerService


def _make_svc(tmp_path: Path, **kwargs) -> SessionManagerService:
    ticks = kwargs.pop("ticks", iter([0.0, 0.1, 0.2, 0.3, 12.5, 12.7, 12.9]))
    return SessionManagerService(
        state_file=tmp_path / "sessions.json",
        checkpoint_dir=tmp_path / "checkpoints",
        utcnow=lambda: "2026-04-27T12:00:00Z",
        monotonic=lambda: next(ticks),
        slow_handover_threshold_seconds=10.0,
        **kwargs,
    )


def test_register_session_resolves_geo_routing_from_user_profile(tmp_path: Path) -> None:
    svc = _make_svc(
        tmp_path,
        user_geo_resolver=lambda user_id: {
            "enabled": True,
            "sites": {"berlin": {"target_node": "srv1", "cidrs": ["10.10.0.0/16"]}},
        }
        if user_id == "alice"
        else None,
    )

    session = svc.register_session(
        session_id="sess-geo-1",
        pool_id="pool-a",
        vm_id=101,
        user_id="alice",
        node_id="srv2",
    )

    assert session["session_geo_routing"]["sites"]["berlin"]["target_node"] == "srv1"


def test_evaluate_geo_handover_matches_target_site(tmp_path: Path) -> None:
    svc = _make_svc(tmp_path)
    svc.register_session(
        session_id="sess-geo-2",
        pool_id="pool-a",
        vm_id=101,
        user_id="alice",
        node_id="srv1",
    )
    svc.set_session_geo_routing("sess-geo-2", {
        "enabled": True,
        "sites": {
            "berlin": {"target_node": "srv1", "cidrs": ["10.10.0.0/16"]},
            "munich": {"target_node": "srv2", "cidrs": ["10.20.0.0/16"]},
        },
    })

    decision = svc.evaluate_geo_handover("sess-geo-2", client_ip="10.20.3.4")

    assert decision["matched_site"] == "munich"
    assert decision["target_node"] == "srv2"
    assert decision["should_handover"] is True


def test_apply_geo_handover_transfers_session(tmp_path: Path) -> None:
    svc = _make_svc(tmp_path)
    svc.register_session(
        session_id="sess-geo-3",
        pool_id="pool-a",
        vm_id=101,
        user_id="alice",
        node_id="srv1",
    )
    svc.set_session_geo_routing("sess-geo-3", {
        "enabled": True,
        "sites": {"munich": {"target_node": "srv2", "cidrs": ["10.20.0.0/16"]}},
    })

    result = svc.apply_geo_handover("sess-geo-3", client_ip="10.20.8.9")

    assert result["ok"] is True
    assert svc.get_current_node("sess-geo-3") == "srv2"


def test_slow_handover_creates_alert_entry(tmp_path: Path) -> None:
    svc = _make_svc(tmp_path, ticks=iter([0.0, 11.5]))
    svc.register_session(
        session_id="sess-slow",
        pool_id="pool-a",
        vm_id=101,
        user_id="alice",
        node_id="srv1",
    )

    transfer = svc.transfer_session("sess-slow", "srv2")

    assert transfer.status == "completed"
    alerts = svc.list_handover_alerts(session_id="sess-slow")
    assert len(alerts) == 1
    assert alerts[0]["metric"] == "handover_duration_seconds"


def test_handover_history_contains_started_and_completed_events(tmp_path: Path) -> None:
    svc = _make_svc(tmp_path)
    svc.register_session(
        session_id="sess-hist",
        pool_id="pool-a",
        vm_id=101,
        user_id="alice",
        node_id="srv1",
    )

    svc.transfer_session("sess-hist", "srv2")

    events = svc.list_handover_events(session_id="sess-hist")
    statuses = {item["status"] for item in events}
    assert "started" in statuses
    assert "completed" in statuses
