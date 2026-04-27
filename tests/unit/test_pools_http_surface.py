from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from core.virtualization.desktop_pool import DesktopPoolMode, DesktopPoolType
from gaming_metrics_service import GamingMetricsService
from pools_http_surface import PoolsHttpSurfaceService


@dataclass
class _PoolInfo:
    pool_id: str
    pool_type: DesktopPoolType
    session_extension_options_minutes: tuple[int, ...] = (15, 30, 60)


class _PoolManagerStub:
    def __init__(self) -> None:
        self.created_spec = None
        self.allocated: list[tuple[str, str]] = []
        self.released: list[tuple[str, int, str]] = []
        self.extended: list[tuple[str, int, int]] = []
        self.stream_health_updates: list[tuple[str, int, dict | None]] = []
        self.desktops = {
            "kiosk-1": [{"vmid": 101, "node": "srv2"}],
            "gaming-1": [{"vmid": 303, "node": "srv2"}],
            "desktop-1": [{"vmid": 202, "node": "srv1"}],
        }

    def pool_info_to_dict(self, pool_info):
        return {
            "pool_id": pool_info.pool_id,
            "pool_type": pool_info.pool_type.value,
            "session_extension_options_minutes": list(pool_info.session_extension_options_minutes),
        }

    def list_pools(self, tenant_id=None):
        return [
            _PoolInfo(pool_id="kiosk-1", pool_type=DesktopPoolType.KIOSK),
            _PoolInfo(pool_id="kiosk-2", pool_type=DesktopPoolType.KIOSK),
            _PoolInfo(pool_id="gaming-1", pool_type=DesktopPoolType.GAMING),
            _PoolInfo(pool_id="desktop-1", pool_type=DesktopPoolType.DESKTOP),
        ]

    def template_info_to_dict(self, template):
        return template

    def create_pool(self, spec):
        self.created_spec = spec
        return _PoolInfo(
            pool_id=spec.pool_id,
            pool_type=spec.pool_type,
            session_extension_options_minutes=tuple(spec.session_extension_options_minutes),
        )

    def list_active_sessions(self):
        return [
            {
                "session_id": "kiosk-1:101",
                "pool_id": "kiosk-1",
                "vmid": 101,
                "user_id": "alice",
                "mode": DesktopPoolMode.FLOATING_NON_PERSISTENT.value,
                "state": "in_use",
                "assigned_at": "2026-04-27T03:00:00Z",
                "stream_health": {
                    "fps": 60,
                    "rtt_ms": 12,
                    "gpu_util_pct": 84,
                    "gpu_temp_c": 67,
                    "window_title": "Steam - Hades",
                },
            },
            {
                "session_id": "kiosk-2:102",
                "pool_id": "kiosk-2",
                "vmid": 102,
                "user_id": "mallory",
                "mode": DesktopPoolMode.FLOATING_NON_PERSISTENT.value,
                "state": "in_use",
                "assigned_at": "2026-04-27T03:01:00Z",
            },
            {
                "session_id": "gaming-1:303",
                "pool_id": "gaming-1",
                "vmid": 303,
                "user_id": "carol",
                "mode": DesktopPoolMode.FLOATING_NON_PERSISTENT.value,
                "state": "in_use",
                "assigned_at": "2026-04-27T03:10:00Z",
                "stream_health": {
                    "fps": 118,
                    "rtt_ms": 7,
                    "dropped_frames": 1,
                    "encoder_load": 62,
                    "gpu_util_pct": 91,
                    "gpu_temp_c": 72,
                    "updated_at": "2026-04-27T03:20:00Z",
                },
            },
            {
                "session_id": "desktop-1:202",
                "pool_id": "desktop-1",
                "vmid": 202,
                "user_id": "bob",
                "mode": DesktopPoolMode.FLOATING_NON_PERSISTENT.value,
                "state": "in_use",
                "assigned_at": "2026-04-27T03:05:00Z",
            },
        ]

    def get_pool(self, pool_id: str):
        if pool_id == "kiosk-1":
            return _PoolInfo(pool_id=pool_id, pool_type=DesktopPoolType.KIOSK, session_extension_options_minutes=(15, 30))
        if pool_id == "kiosk-2":
            return _PoolInfo(pool_id=pool_id, pool_type=DesktopPoolType.KIOSK, session_extension_options_minutes=(60,))
        if pool_id == "gaming-1":
            return _PoolInfo(pool_id=pool_id, pool_type=DesktopPoolType.GAMING)
        if pool_id == "desktop-1":
            return _PoolInfo(pool_id=pool_id, pool_type=DesktopPoolType.DESKTOP)
        return None

    def list_desktops(self, pool_id: str):
        return list(self.desktops.get(pool_id, []))

    def time_remaining_seconds(self, pool_id: str, vmid: int) -> float:
        assert pool_id == "kiosk-1"
        assert vmid == 101
        return 600.0

    def release_desktop(self, pool_id: str, vmid: int, user_id: str):
        self.released.append((pool_id, vmid, user_id))
        return type(
            "Lease",
            (),
            {
                "pool_id": pool_id,
                "vmid": vmid,
                "user_id": user_id,
                "mode": DesktopPoolMode.FLOATING_NON_PERSISTENT,
                "state": "recycling",
                "assigned_at": "",
                "stream_health": None,
            },
        )()

    def allocate_desktop(self, pool_id: str, user_id: str):
        self.allocated.append((pool_id, user_id))
        vmid = 303 if pool_id == "gaming-1" else 202
        return type(
            "Lease",
            (),
            {
                "pool_id": pool_id,
                "vmid": vmid,
                "user_id": user_id,
                "mode": DesktopPoolMode.FLOATING_NON_PERSISTENT,
                "state": "in_use",
                "assigned_at": "2026-04-27T03:10:00Z",
                "stream_health": None,
            },
        )()

    def extend_kiosk_session(self, pool_id: str, vmid: int, *, minutes: int):
        self.extended.append((pool_id, vmid, minutes))
        return type(
            "Lease",
            (),
            {
                "pool_id": pool_id,
                "vmid": vmid,
                "user_id": "alice",
                "mode": DesktopPoolMode.FLOATING_NON_PERSISTENT,
                "state": "in_use",
                "assigned_at": "2026-04-27T03:00:00Z",
                "stream_health": {
                    "fps": 60,
                    "rtt_ms": 12,
                    "gpu_util_pct": 84,
                    "gpu_temp_c": 67,
                    "window_title": "Steam - Hades",
                },
            },
        )()

    def lease_to_dict(self, lease):
        return {
            "pool_id": lease.pool_id,
            "vmid": lease.vmid,
            "user_id": lease.user_id,
            "mode": lease.mode.value,
            "state": lease.state,
            "assigned_at": lease.assigned_at,
            "stream_health": lease.stream_health,
        }

    def update_stream_health(self, *, pool_id: str, vmid: int, stream_health: dict | None):
        self.stream_health_updates.append((pool_id, vmid, stream_health))
        return type(
            "Lease",
            (),
            {
                "pool_id": pool_id,
                "vmid": vmid,
                "user_id": "carol",
                "mode": DesktopPoolMode.FLOATING_NON_PERSISTENT,
                "state": "in_use",
                "assigned_at": "2026-04-27T03:10:00Z",
                "stream_health": stream_health,
            },
        )()


def _make_service(*, audit_event=None) -> tuple[PoolsHttpSurfaceService, _PoolManagerStub]:
    pool_mgr = _PoolManagerStub()
    session_events: list[tuple[str, dict[str, object]]] = []
    metrics = GamingMetricsService(
        state_dir=Path(tempfile.mkdtemp(prefix="beagle-gaming-metrics-")),
        utcnow=lambda: "2026-04-27T03:30:00Z",
    )
    service = PoolsHttpSurfaceService(
        pool_manager_service=pool_mgr,
        gaming_metrics_service=metrics,
        entitlement_service=type("Ent", (), {"is_entitled": lambda self, pool_id, user_id: True})(),
        desktop_template_builder_service=type("Tpl", (), {"template_info_to_dict": lambda self, item: item})(),
        recording_service=type("Rec", (), {})(),
        session_manager_service=type(
            "SessionManagerStub",
            (),
            {
                "events": session_events,
                "register_session": staticmethod(lambda **kwargs: session_events.append(("register", kwargs))),
                "end_session": staticmethod(lambda session_id: session_events.append(("end", {"session_id": session_id}))),
                "list_handover_events": staticmethod(
                    lambda: [
                        {
                            "session_id": "gaming-1:303",
                            "pool_id": "gaming-1",
                            "user_id": "carol",
                            "source_node": "srv1",
                            "target_node": "srv2",
                            "status": "completed",
                            "duration_seconds": 3.4,
                            "started_at": "2026-04-27T03:10:00Z",
                            "completed_at": "2026-04-27T03:10:03Z",
                        }
                    ]
                ),
                "list_handover_alerts": staticmethod(
                    lambda: [
                        {
                            "session_id": "gaming-1:303",
                            "user_id": "carol",
                            "metric": "handover_duration_seconds",
                            "current_value": 12.7,
                            "threshold": 10.0,
                            "severity": "warning",
                            "fired_at": "2026-04-27T03:10:13Z",
                        }
                    ]
                ),
                "get_session": staticmethod(lambda session_id: {"pool_id": "gaming-1"} if session_id == "gaming-1:303" else None),
            },
        )(),
        audit_event=audit_event or (lambda *args, **kwargs: None),
        requester_identity=lambda: "operator",
        requester_tenant_id=lambda: "",
        can_bypass_pool_visibility=lambda: True,
        can_view_pool=lambda pool_id: pool_id in {"kiosk-1", "gaming-1"},
        pool_recording_policy=lambda pool_id: "disabled",
        pool_recording_watermark=lambda pool_id: {"enabled": False, "custom_text": ""},
        remote_addr=lambda: "127.0.0.1",
        utcnow=lambda: "2026-04-27T03:30:00Z",
        version="test",
    )
    setattr(pool_mgr, "session_events", session_events)
    return service, pool_mgr


def test_create_pool_accepts_gaming_and_kiosk_specific_fields() -> None:
    service, pool_mgr = _make_service()

    response = service.route_post(
        "/api/v1/pools",
        json_payload={
            "pool_id": "gaming-pool",
            "template_id": "tpl-1",
            "mode": "floating_non_persistent",
            "storage_pool": "local",
            "min_pool_size": 1,
            "max_pool_size": 2,
            "warm_pool_size": 1,
            "cpu_cores": 8,
            "memory_mib": 16384,
            "pool_type": "gaming",
            "gpu_class": "passthrough-nvidia-gtx-1080",
            "session_time_limit_minutes": 45,
            "session_cost_per_minute": 0.75,
        },
    )

    assert response is not None
    assert response["status"] == HTTPStatus.CREATED
    assert pool_mgr.created_spec is not None
    assert pool_mgr.created_spec.pool_type == DesktopPoolType.GAMING
    assert pool_mgr.created_spec.gpu_class == "passthrough-nvidia-gtx-1080"
    assert pool_mgr.created_spec.session_time_limit_minutes == 45
    assert pool_mgr.created_spec.session_cost_per_minute == 0.75
    assert pool_mgr.created_spec.session_extension_options_minutes == ()


def test_kiosk_sessions_route_filters_to_kiosk_pools_and_adds_remaining_time() -> None:
    service, _ = _make_service()

    response = service.route_get("/api/v1/pools/kiosk/sessions")

    assert response is not None
    assert response["status"] == HTTPStatus.OK
    payload = response["payload"]
    assert payload["ok"] is True
    assert len(payload["sessions"]) == 1
    session = payload["sessions"][0]
    assert session["pool_id"] == "kiosk-1"
    assert session["vm_id"] == 101
    assert session["time_remaining_seconds"] == 600.0
    assert session["session_extension_options_minutes"] == [15, 30]
    assert session["stream_health"]["fps"] == 60
    assert session["stream_health"]["rtt_ms"] == 12
    assert session["stream_health"]["gpu_util_pct"] == 84
    assert session["stream_health"]["gpu_temp_c"] == 67
    assert session["stream_health"]["window_title"] == "Steam - Hades"


def test_kiosk_sessions_route_hides_unentitled_kiosk_pools() -> None:
    service, _ = _make_service()

    response = service.route_get("/api/v1/pools/kiosk/sessions")

    assert response is not None
    sessions = response["payload"]["sessions"]
    assert [item["pool_id"] for item in sessions] == ["kiosk-1"]


def test_kiosk_end_route_releases_matching_session() -> None:
    service, pool_mgr = _make_service()

    response = service.route_post("/api/v1/pools/kiosk/sessions/101/end", json_payload={})

    assert response is not None
    assert response["status"] == HTTPStatus.OK
    assert pool_mgr.released == [("kiosk-1", 101, "alice")]


def test_kiosk_extend_route_extends_matching_session() -> None:
    service, pool_mgr = _make_service()

    response = service.route_post("/api/v1/pools/kiosk/sessions/101/extend", json_payload={"minutes": 15})

    assert response is not None
    assert response["status"] == HTTPStatus.OK
    assert pool_mgr.extended == [("kiosk-1", 101, 15)]
    assert response["payload"]["time_remaining_seconds"] == 600.0


def test_kiosk_extend_route_tolerates_audit_failure() -> None:
    service, pool_mgr = _make_service(audit_event=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit down")))

    response = service.route_post("/api/v1/pools/kiosk/sessions/101/extend", json_payload={"minutes": 15})

    assert response is not None
    assert response["status"] == HTTPStatus.OK
    assert pool_mgr.extended == [("kiosk-1", 101, 15)]


def test_create_pool_accepts_kiosk_extension_levels() -> None:
    service, pool_mgr = _make_service()

    response = service.route_post(
        "/api/v1/pools",
        json_payload={
            "pool_id": "kiosk-pool",
            "template_id": "tpl-1",
            "mode": "floating_non_persistent",
            "storage_pool": "local",
            "min_pool_size": 1,
            "max_pool_size": 2,
            "warm_pool_size": 1,
            "cpu_cores": 4,
            "memory_mib": 8192,
            "pool_type": "kiosk",
            "session_time_limit_minutes": 45,
            "session_extension_options_minutes": [30, 60],
        },
    )

    assert response is not None
    assert response["status"] == HTTPStatus.CREATED
    assert pool_mgr.created_spec is not None
    assert pool_mgr.created_spec.session_extension_options_minutes == (30, 60)


def test_gaming_metrics_route_returns_active_dashboard_payload() -> None:
    service, _ = _make_service()

    response = service.route_get("/api/v1/gaming/metrics")

    assert response is not None
    assert response["status"] == HTTPStatus.OK
    payload = response["payload"]
    assert payload["ok"] is True
    assert payload["overview"]["active_sessions"] == 1
    assert payload["active_sessions"][0]["pool_id"] == "gaming-1"
    assert payload["active_sessions"][0]["latest_sample"]["fps"] == 118.0


def test_stream_health_update_mirrors_into_gaming_metrics_for_gaming_pool() -> None:
    service, pool_mgr = _make_service()

    response = service.route_post(
        "/api/v1/sessions/stream-health",
        json_payload={
            "pool_id": "gaming-1",
            "vmid": 303,
            "stream_health": {
                "fps": 120,
                "rtt_ms": 8,
                "dropped_frames": 0,
                "encoder_load": 55,
                "gpu_util_pct": 88,
                "gpu_temp_c": 71,
                "updated_at": "2026-04-27T03:25:00Z",
            },
        },
    )

    assert response is not None
    assert response["status"] == HTTPStatus.OK
    assert pool_mgr.stream_health_updates == [
        (
            "gaming-1",
            303,
            {
                "fps": 120,
                "rtt_ms": 8,
                "dropped_frames": 0,
                "encoder_load": 55,
                "gpu_util_pct": 88,
                "gpu_temp_c": 71,
                "updated_at": "2026-04-27T03:25:00Z",
            },
        )
    ]


def test_allocate_route_registers_session_with_current_node() -> None:
    service, pool_mgr = _make_service()

    response = service.route_post("/api/v1/pools/gaming-1/allocate", json_payload={"user_id": "carol"})

    assert response is not None
    assert response["status"] == HTTPStatus.OK
    assert pool_mgr.allocated == [("gaming-1", "carol")]
    assert pool_mgr.session_events == [
        (
            "register",
            {
                "session_id": "gaming-1:303",
                "pool_id": "gaming-1",
                "vm_id": 303,
                "user_id": "carol",
                "node_id": "srv2",
            },
        )
    ]


def test_release_route_ends_registered_session() -> None:
    service, pool_mgr = _make_service()

    response = service.route_post("/api/v1/pools/desktop-1/release", json_payload={"vmid": 202, "user_id": "bob"})

    assert response is not None
    assert response["status"] == HTTPStatus.OK
    assert pool_mgr.released == [("desktop-1", 202, "bob")]
    assert pool_mgr.session_events == [("end", {"session_id": "desktop-1:202"})]


def test_handover_history_route_returns_visible_events_and_alerts() -> None:
    service, _ = _make_service()

    response = service.route_get("/api/v1/sessions/handover")

    assert response is not None
    assert response["status"] == HTTPStatus.OK
    assert response["payload"]["events"][0]["session_id"] == "gaming-1:303"
    assert response["payload"]["alerts"][0]["metric"] == "handover_duration_seconds"
