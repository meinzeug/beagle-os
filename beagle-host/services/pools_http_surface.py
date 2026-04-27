"""Pools + Sessions HTTP Surface — Plan 05 Schritt 3b.

Handles:
  /api/v1/pools
  /api/v1/pools/{pool_id}
  /api/v1/pools/{pool_id}/vms
  /api/v1/pools/{pool_id}/entitlements
  /api/v1/pools/{pool_id}/allocate
  /api/v1/pools/{pool_id}/release
  /api/v1/pools/{pool_id}/recycle
  /api/v1/pools/{pool_id}/scale
  /api/v1/pool-templates
  /api/v1/pool-templates/{template_id}
  /api/v1/sessions
  /api/v1/sessions/stream-health

Extracted from beagle-control-plane.py (Plan 05 Schritt 3b).
"""
from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable


class PoolsHttpSurfaceService:
    _GAMING_METRICS = re.compile(r"^/api/v1/gaming/metrics$")
    _POOL = re.compile(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)$")
    _KIOSK_SESSIONS = re.compile(r"^/api/v1/pools/kiosk/sessions$")
    _KIOSK_SESSION_END = re.compile(r"^/api/v1/pools/kiosk/sessions/(?P<vmid>\d+)/end$")
    _KIOSK_SESSION_EXTEND = re.compile(r"^/api/v1/pools/kiosk/sessions/(?P<vmid>\d+)/extend$")
    _POOL_VMS = re.compile(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)/vms$")
    _POOL_ENTITLEMENTS = re.compile(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)/entitlements$")
    _POOL_ALLOCATE = re.compile(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)/allocate$")
    _POOL_RELEASE = re.compile(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)/release$")
    _POOL_RECYCLE = re.compile(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)/recycle$")
    _POOL_SCALE = re.compile(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)/scale$")
    _POOL_TEMPLATE = re.compile(r"^/api/v1/pool-templates/(?P<tid>[A-Za-z0-9._-]+)$")

    def __init__(
        self,
        *,
        pool_manager_service: Any,
        gaming_metrics_service: Any,
        entitlement_service: Any,
        desktop_template_builder_service: Any,
        recording_service: Any,
        session_manager_service: Any,
        audit_event: Callable[..., None],
        requester_identity: Callable[[], str],
        requester_tenant_id: Callable[[], str],
        can_bypass_pool_visibility: Callable[[], bool],
        can_view_pool: Callable[[str], bool],
        pool_recording_policy: Callable[[str], str],
        pool_recording_watermark: Callable[[str], dict[str, Any]],
        remote_addr: Callable[[], str],
        service_name: str = "beagle-control-plane",
        utcnow: Callable[[], str],
        version: str = "",
    ) -> None:
        self._pool_mgr = pool_manager_service
        self._gaming_metrics = gaming_metrics_service
        self._entitlement = entitlement_service
        self._template_builder = desktop_template_builder_service
        self._recording = recording_service
        self._session_manager = session_manager_service
        self._audit_event = audit_event
        self._requester_identity = requester_identity
        self._requester_tenant_id = requester_tenant_id
        self._can_bypass_pool_visibility = can_bypass_pool_visibility
        self._can_view_pool = can_view_pool
        self._pool_recording_policy = pool_recording_policy
        self._pool_recording_watermark = pool_recording_watermark
        self._remote_addr = remote_addr
        self._service_name = str(service_name or "beagle-control-plane")
        self._utcnow = utcnow
        self._version = str(version or "")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _json(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    def _pool_dict(self, pool_info: Any) -> dict[str, Any]:
        return self._pool_mgr.pool_info_to_dict(pool_info)

    def _tmpl_dict(self, tmpl_info: Any) -> dict[str, Any]:
        return self._template_builder.template_info_to_dict(tmpl_info)

    @staticmethod
    def _pool_type_value(pool_info: Any) -> str:
        raw = getattr(pool_info, "pool_type", "")
        return str(raw.value if hasattr(raw, "value") else raw or "").strip().lower()

    def _safe_audit_event(self, *args: Any, **kwargs: Any) -> None:
        try:
            self._audit_event(*args, **kwargs)
        except Exception:
            return

    def _node_for_pool_vm(self, pool_id: str, vmid: int) -> str:
        try:
            desktops = self._pool_mgr.list_desktops(pool_id)
        except Exception:
            return ""
        for desktop in desktops:
            if int(desktop.get("vmid") or 0) == int(vmid):
                return str(desktop.get("node") or "").strip()
        return ""

    # ------------------------------------------------------------------
    # GET routing
    # ------------------------------------------------------------------

    def handles_get(self, path: str) -> bool:
        if path in {"/api/v1/pools", "/api/v1/pool-templates", "/api/v1/sessions", "/api/v1/sessions/handover"}:
            return True
        if self._GAMING_METRICS.match(path):
            return True
        if self._KIOSK_SESSIONS.match(path):
            return True
        if self._POOL.match(path):
            return True
        if self._POOL_VMS.match(path):
            return True
        if self._POOL_ENTITLEMENTS.match(path):
            return True
        if self._POOL_TEMPLATE.match(path):
            return True
        return False

    def route_get(self, path: str) -> dict[str, Any] | None:
        if self._GAMING_METRICS.match(path):
            all_gaming_session_ids: list[str] = []
            visible_pool_ids: set[str] = set()
            for pool in self._pool_mgr.list_pools():
                pool_id = str(getattr(pool, "pool_id", "") or "").strip()
                if not pool_id:
                    continue
                if self._pool_type_value(pool) != "gaming":
                    continue
                if self._can_view_pool(pool_id):
                    visible_pool_ids.add(pool_id)
            for session in self._pool_mgr.list_active_sessions():
                pool_id = str(session.get("pool_id") or "").strip()
                if not pool_id:
                    continue
                pool_info = self._pool_mgr.get_pool(pool_id)
                if pool_info is None or self._pool_type_value(pool_info) != "gaming":
                    continue
                all_gaming_session_ids.append(str(session.get("session_id") or ""))
                if not self._can_view_pool(pool_id):
                    continue
                visible_pool_ids.add(pool_id)
                self._gaming_metrics.observe_session(session)
            self._gaming_metrics.finalize_missing_sessions(all_gaming_session_ids)
            payload = self._gaming_metrics.build_dashboard(
                visible_pool_ids=visible_pool_ids,
                recent_limit=24,
            )
            return self._json(HTTPStatus.OK, {"ok": True, **payload})

        if self._KIOSK_SESSIONS.match(path):
            sessions = []
            for session in self._pool_mgr.list_active_sessions():
                pool_id = str(session.get("pool_id") or "").strip()
                if not pool_id:
                    continue
                pool_info = self._pool_mgr.get_pool(pool_id)
                if pool_info is None or self._pool_type_value(pool_info) != "kiosk":
                    continue
                if not self._can_view_pool(pool_id):
                    continue
                vmid = int(session.get("vmid") or 0)
                item = dict(session)
                item["vm_id"] = vmid
                item["session_extension_options_minutes"] = list(
                    getattr(pool_info, "session_extension_options_minutes", ()) or ()
                )
                try:
                    item["time_remaining_seconds"] = self._pool_mgr.time_remaining_seconds(pool_id, vmid)
                except Exception:
                    item["time_remaining_seconds"] = -1.0
                sessions.append(item)
            return self._json(HTTPStatus.OK, {"ok": True, "sessions": sessions})

        if path == "/api/v1/sessions":
            sessions = []
            for session in self._pool_mgr.list_active_sessions():
                pool_id = str(session.get("pool_id") or "")
                if pool_id and not self._can_view_pool(pool_id):
                    continue
                sessions.append(session)
            return self._json(HTTPStatus.OK, {"ok": True, "sessions": sessions})

        if path == "/api/v1/sessions/handover":
            events = []
            for item in self._session_manager.list_handover_events():
                pool_id = str(item.get("pool_id") or "").strip()
                if pool_id and not self._can_view_pool(pool_id):
                    continue
                events.append(item)
            alerts = []
            for item in self._session_manager.list_handover_alerts():
                session = self._session_manager.get_session(str(item.get("session_id") or ""))
                pool_id = str((session or {}).get("pool_id") or "").strip()
                if pool_id and not self._can_view_pool(pool_id):
                    continue
                alerts.append(item)
            return self._json(HTTPStatus.OK, {"ok": True, "events": events, "alerts": alerts})

        if path == "/api/v1/pools":
            requester_tid = self._requester_tenant_id() if not self._can_bypass_pool_visibility() else None
            pools = [
                pool
                for pool in self._pool_mgr.list_pools(tenant_id=requester_tid)
                if self._can_view_pool(pool.pool_id)
            ]
            return self._json(HTTPStatus.OK, {
                "ok": True,
                "pools": [self._pool_dict(p) for p in pools],
            })

        m = self._POOL.match(path)
        if m:
            pool_id = m.group("pool_id")
            if not self._can_view_pool(pool_id):
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "pool not found"})
            pool_info = self._pool_mgr.get_pool(pool_id)
            if pool_info is None:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "pool not found"})
            return self._json(HTTPStatus.OK, {"ok": True, **self._pool_dict(pool_info)})

        m = self._POOL_VMS.match(path)
        if m:
            pool_id = m.group("pool_id")
            if not self._can_view_pool(pool_id):
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "pool not found"})
            try:
                desktops = self._pool_mgr.list_desktops(pool_id)
            except ValueError as exc:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": str(exc)})
            return self._json(HTTPStatus.OK, {"ok": True, "vms": desktops})

        m = self._POOL_ENTITLEMENTS.match(path)
        if m:
            pool_id = m.group("pool_id")
            if not self._can_view_pool(pool_id):
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "pool not found"})
            try:
                result = self._entitlement.get_entitlements(pool_id)
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json(HTTPStatus.OK, {"ok": True, **result})

        if path == "/api/v1/pool-templates":
            templates = self._template_builder.list_templates()
            return self._json(HTTPStatus.OK, {
                "ok": True,
                "templates": [self._tmpl_dict(t) for t in templates],
            })

        m = self._POOL_TEMPLATE.match(path)
        if m:
            tid = m.group("tid")
            tmpl = self._template_builder.get_template(tid)
            if tmpl is None:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "template not found"})
            return self._json(HTTPStatus.OK, {"ok": True, **self._tmpl_dict(tmpl)})

        return None

    # ------------------------------------------------------------------
    # POST routing
    # ------------------------------------------------------------------

    def handles_post(self, path: str) -> bool:
        if path in {
            "/api/v1/pools",
            "/api/v1/pool-templates",
            "/api/v1/sessions/stream-health",
        }:
            return True
        if self._KIOSK_SESSION_END.match(path):
            return True
        if self._KIOSK_SESSION_EXTEND.match(path):
            return True
        if self._POOL_ENTITLEMENTS.match(path):
            return True
        if self._POOL_VMS.match(path):
            return True
        if self._POOL_ALLOCATE.match(path):
            return True
        if self._POOL_RELEASE.match(path):
            return True
        if self._POOL_RECYCLE.match(path):
            return True
        if self._POOL_SCALE.match(path):
            return True
        return False

    def route_post(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        p = json_payload or {}
        requester = self._requester_identity()

        if path == "/api/v1/sessions/stream-health":
            try:
                pool_id = str(p.get("pool_id") or "").strip()
                vmid = int(p.get("vmid") or 0)
                if not pool_id:
                    raise ValueError("pool_id is required")
                if vmid <= 0:
                    raise ValueError("vmid must be > 0")
                stream_health_raw = p.get("stream_health")
                if stream_health_raw is not None and not isinstance(stream_health_raw, dict):
                    raise ValueError("stream_health must be an object")
                lease = self._pool_mgr.update_stream_health(
                    pool_id=pool_id,
                    vmid=vmid,
                    stream_health=stream_health_raw,
                )
            except (ValueError, TypeError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            try:
                pool_info = self._pool_mgr.get_pool(pool_id)
                if pool_info is not None and self._pool_type_value(pool_info) == "gaming":
                    for session in self._pool_mgr.list_active_sessions():
                        if str(session.get("pool_id") or "") == pool_id and int(session.get("vmid") or 0) == vmid:
                            self._gaming_metrics.observe_session(session)
                            break
            except Exception:
                pass
            self._audit_event(
                "session.stream_health.update",
                "success",
                pool_id=pool_id,
                vmid=vmid,
                username=requester,
            )
            return self._json(HTTPStatus.OK, {"ok": True, **self._pool_mgr.lease_to_dict(lease)})

        if path == "/api/v1/pools":
            from core.virtualization.desktop_pool import DesktopPoolMode, DesktopPoolSpec, DesktopPoolType, SessionRecordingPolicy
            from core.virtualization.streaming_profile import streaming_profile_from_payload
            try:
                mode = DesktopPoolMode(str(p.get("mode", "floating_non_persistent")))
                pool_type = DesktopPoolType(str(p.get("pool_type", "desktop") or "desktop").strip().lower())
                streaming_profile = None
                if "streaming_profile" in p and p.get("streaming_profile") is not None:
                    if not isinstance(p.get("streaming_profile"), dict):
                        raise ValueError("streaming_profile must be an object")
                    streaming_profile = streaming_profile_from_payload(p.get("streaming_profile"))
                spec = DesktopPoolSpec(
                    pool_id=str(p.get("pool_id", "") or "").strip(),
                    template_id=str(p.get("template_id", "") or ""),
                    mode=mode,
                    min_pool_size=int(p.get("min_pool_size", 0)),
                    max_pool_size=int(p.get("max_pool_size", 10)),
                    warm_pool_size=int(p.get("warm_pool_size", 2)),
                    cpu_cores=int(p.get("cpu_cores", 2)),
                    memory_mib=int(p.get("memory_mib", 2048)),
                    storage_pool=str(p.get("storage_pool", "local") or "local"),
                    gpu_class=str(p.get("gpu_class", "") or "").strip(),
                    session_recording=SessionRecordingPolicy(
                        str(p.get("session_recording", "disabled") or "disabled").strip().lower()
                    ),
                    recording_retention_days=int(p.get("recording_retention_days", 30)),
                    recording_watermark_enabled=bool(p.get("recording_watermark_enabled", False)),
                    recording_watermark_custom_text=str(p.get("recording_watermark_custom_text", "") or "").strip(),
                    enabled=bool(p.get("enabled", True)),
                    labels=tuple(str(lbl) for lbl in p.get("labels", [])),
                    streaming_profile=streaming_profile,
                    tenant_id=str(p.get("tenant_id", "") or self._requester_tenant_id()).strip(),
                    pool_type=pool_type,
                    session_time_limit_minutes=int(p.get("session_time_limit_minutes", 0) or 0),
                    session_cost_per_minute=float(p.get("session_cost_per_minute", 0.0) or 0.0),
                    session_extension_options_minutes=tuple(p.get("session_extension_options_minutes") or ()),
                )
                pool_info = self._pool_mgr.create_pool(spec)
            except (ValueError, TypeError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event("pool.create", "success", pool_id=pool_info.pool_id, username=requester)
            return self._json(HTTPStatus.CREATED, {"ok": True, **self._pool_dict(pool_info)})

        m = self._KIOSK_SESSION_END.match(path)
        if m:
            vmid = int(m.group("vmid") or 0)
            target_session = None
            for session in self._pool_mgr.list_active_sessions():
                if int(session.get("vmid") or 0) != vmid:
                    continue
                pool_id = str(session.get("pool_id") or "").strip()
                pool_info = self._pool_mgr.get_pool(pool_id)
                if pool_info is None or self._pool_type_value(pool_info) != "kiosk":
                    continue
                if not self._can_view_pool(pool_id):
                    return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "kiosk session not found"})
                target_session = session
                break
            if target_session is None:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "kiosk session not found"})
            pool_id = str(target_session.get("pool_id") or "").strip()
            user_id = str(target_session.get("user_id") or "").strip() or requester
            try:
                lease = self._pool_mgr.release_desktop(pool_id, vmid, user_id)
            except (ValueError, RuntimeError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            try:
                self._session_manager.end_session(f"{pool_id}:{vmid}")
            except Exception:
                pass
            self._safe_audit_event(
                "kiosk.session.end",
                "success",
                pool_id=pool_id,
                vmid=vmid,
                user_id=user_id,
                username=requester,
            )
            return self._json(HTTPStatus.OK, {"ok": True, **self._pool_mgr.lease_to_dict(lease)})

        m = self._KIOSK_SESSION_EXTEND.match(path)
        if m:
            vmid = int(m.group("vmid") or 0)
            extend_minutes = int(p.get("minutes") or 0)
            target_session = None
            for session in self._pool_mgr.list_active_sessions():
                if int(session.get("vmid") or 0) != vmid:
                    continue
                pool_id = str(session.get("pool_id") or "").strip()
                pool_info = self._pool_mgr.get_pool(pool_id)
                if pool_info is None or self._pool_type_value(pool_info) != "kiosk":
                    continue
                if not self._can_view_pool(pool_id):
                    return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "kiosk session not found"})
                target_session = session
                break
            if target_session is None:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "kiosk session not found"})
            pool_id = str(target_session.get("pool_id") or "").strip()
            try:
                lease = self._pool_mgr.extend_kiosk_session(pool_id, vmid, minutes=extend_minutes)
                remaining = self._pool_mgr.time_remaining_seconds(pool_id, vmid)
            except (ValueError, RuntimeError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._safe_audit_event(
                "kiosk.session.extend",
                "success",
                pool_id=pool_id,
                vmid=vmid,
                minutes=extend_minutes,
                username=requester,
            )
            payload = {"ok": True, **self._pool_mgr.lease_to_dict(lease), "time_remaining_seconds": remaining}
            return self._json(HTTPStatus.OK, payload)

        m = self._POOL_ENTITLEMENTS.match(path)
        if m:
            pool_id = m.group("pool_id")
            action = str(p.get("action", "set")).strip().lower()
            try:
                if action == "add":
                    result = self._entitlement.add_entitlement(
                        pool_id,
                        user_id=str(p.get("user_id", "") or ""),
                        group_id=str(p.get("group_id", "") or ""),
                    )
                elif action == "remove":
                    result = self._entitlement.remove_entitlement(
                        pool_id,
                        user_id=str(p.get("user_id", "") or ""),
                        group_id=str(p.get("group_id", "") or ""),
                    )
                else:
                    result = self._entitlement.set_entitlements(
                        pool_id,
                        users=p.get("users"),
                        groups=p.get("groups"),
                    )
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event(
                "pool.entitlement.update",
                "success",
                pool_id=pool_id,
                action=action,
                username=requester,
            )
            return self._json(HTTPStatus.OK, {"ok": True, **result})

        m = self._POOL_VMS.match(path)
        if m:
            pool_id = m.group("pool_id")
            try:
                vmid = int(p.get("vmid") or 0)
                if not vmid:
                    raise ValueError("vmid is required")
                result = self._pool_mgr.register_vm(
                    pool_id,
                    vmid,
                    scheduler_policy=p.get("scheduler_policy"),
                )
            except (ValueError, TypeError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event("pool.vm.register", "success", pool_id=pool_id, vmid=vmid, username=requester)
            return self._json(HTTPStatus.CREATED, {"ok": True, **result})

        m = self._POOL_ALLOCATE.match(path)
        if m:
            pool_id = m.group("pool_id")
            user_id = str(p.get("user_id", "") or "").strip() or requester
            try:
                from core.virtualization.desktop_pool import SessionRecordingPolicy
                if not self._entitlement.is_entitled(pool_id, user_id=user_id):
                    return self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "not entitled to this pool"})
                lease = self._pool_mgr.allocate_desktop(pool_id, user_id)
            except (ValueError, RuntimeError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})

            policy = self._pool_recording_policy(pool_id)
            if policy == "always":
                try:
                    watermark = self._pool_recording_watermark(pool_id)
                    self._recording.start_recording(
                        session_id=f"{pool_id}:{lease.vmid}",
                        input_url=str(p.get("recording_input_url") or "").strip(),
                        codec=str(p.get("recording_codec") or "h264").strip(),
                        test_source=bool(p.get("recording_test_source", False)),
                        watermark_enabled=bool(watermark.get("enabled", False)),
                        watermark_username=str(lease.user_id or user_id or requester).strip(),
                        watermark_custom_text=str(watermark.get("custom_text") or "").strip(),
                        watermark_show_timestamp=True,
                    )
                    self._audit_event(
                        "session.recording.start",
                        "success",
                        session_id=f"{pool_id}:{lease.vmid}",
                        requested_by=requester,
                        auto_policy="always",
                        remote_addr=self._remote_addr(),
                    )
                except Exception as exc:
                    self._audit_event(
                        "session.recording.start",
                        "error",
                        session_id=f"{pool_id}:{lease.vmid}",
                        requested_by=requester,
                        auto_policy="always",
                        error=str(exc),
                        remote_addr=self._remote_addr(),
                    )

            try:
                self._session_manager.register_session(
                    session_id=f"{pool_id}:{lease.vmid}",
                    pool_id=pool_id,
                    vm_id=int(lease.vmid),
                    user_id=str(lease.user_id or user_id or requester).strip(),
                    node_id=self._node_for_pool_vm(pool_id, int(lease.vmid)),
                )
            except Exception:
                pass

            self._audit_event(
                "pool.desktop.allocate",
                "success",
                pool_id=pool_id,
                user_id=user_id,
                vmid=lease.vmid,
                username=requester,
            )
            return self._json(HTTPStatus.OK, {"ok": True, **self._pool_mgr.lease_to_dict(lease)})

        m = self._POOL_RELEASE.match(path)
        if m:
            pool_id = m.group("pool_id")
            try:
                vmid = int(p.get("vmid") or 0)
                user_id = str(p.get("user_id", "") or "").strip() or requester
                lease = self._pool_mgr.release_desktop(pool_id, vmid, user_id)
            except (ValueError, RuntimeError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            try:
                self._session_manager.end_session(f"{pool_id}:{vmid}")
            except Exception:
                pass

            policy = self._pool_recording_policy(pool_id)
            if policy == "always":
                session_id = f"{pool_id}:{vmid}"
                stop_result = self._recording.stop_recording(session_id=session_id)
                if bool(stop_result.get("ok")):
                    self._audit_event(
                        "session.recording.stop",
                        "success",
                        session_id=session_id,
                        requested_by=requester,
                        auto_policy="always",
                        remote_addr=self._remote_addr(),
                    )

            self._audit_event(
                "pool.desktop.release",
                "success",
                pool_id=pool_id,
                vmid=vmid,
                username=requester,
            )
            return self._json(HTTPStatus.OK, {"ok": True, **self._pool_mgr.lease_to_dict(lease)})

        m = self._POOL_RECYCLE.match(path)
        if m:
            pool_id = m.group("pool_id")
            try:
                vmid = int(p.get("vmid") or 0)
                lease = self._pool_mgr.recycle_desktop(pool_id, vmid)
            except (ValueError, RuntimeError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event(
                "pool.desktop.recycle",
                "success",
                pool_id=pool_id,
                vmid=vmid,
                username=requester,
            )
            return self._json(HTTPStatus.OK, {"ok": True, **self._pool_mgr.lease_to_dict(lease)})

        m = self._POOL_SCALE.match(path)
        if m:
            pool_id = m.group("pool_id")
            try:
                target_size = int(p.get("target_size") or 0)
                pool_info = self._pool_mgr.scale_pool(pool_id, target_size)
            except (ValueError, TypeError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event(
                "pool.scale",
                "success",
                pool_id=pool_id,
                target_size=target_size,
                username=requester,
            )
            return self._json(HTTPStatus.OK, {"ok": True, **self._pool_dict(pool_info)})

        if path == "/api/v1/pool-templates":
            from core.virtualization.desktop_template import DesktopTemplateBuildSpec
            try:
                spec = DesktopTemplateBuildSpec(
                    template_id=str(p.get("template_id", "") or "").strip(),
                    source_vmid=int(p.get("source_vmid") or 0),
                    template_name=str(p.get("template_name", "") or "").strip(),
                    os_family=str(p.get("os_family", "linux") or "linux"),
                    storage_pool=str(p.get("storage_pool", "local") or "local"),
                    snapshot_name=str(p.get("snapshot_name", "sealed") or "sealed"),
                    backing_image=str(p.get("backing_image", "") or ""),
                    cpu_cores=int(p.get("cpu_cores", 2)),
                    memory_mib=int(p.get("memory_mib", 2048)),
                    software_packages=tuple(str(pkg) for pkg in p.get("software_packages", [])),
                    notes=str(p.get("notes", "") or ""),
                )
                tmpl_info = self._template_builder.build_template(spec)
            except (ValueError, RuntimeError, TypeError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event(
                "pool_template.create",
                "success",
                template_id=tmpl_info.template_id,
                username=requester,
            )
            return self._json(HTTPStatus.CREATED, {"ok": True, **self._tmpl_dict(tmpl_info)})

        return None

    # ------------------------------------------------------------------
    # PUT routing
    # ------------------------------------------------------------------

    def handles_put(self, path: str) -> bool:
        return bool(self._POOL.match(path))

    def route_put(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        p = json_payload or {}
        requester = self._requester_identity()

        m = self._POOL.match(path)
        if m:
            pool_id = str(m.group("pool_id") or "").strip()
            try:
                payload = self._pool_mgr.update_pool(pool_id, p)
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event("pool.update", "success", pool_id=pool_id, username=requester)
            return self._json(HTTPStatus.OK, {"ok": True, **self._pool_dict(payload)})

        return None

    # ------------------------------------------------------------------
    # DELETE routing
    # ------------------------------------------------------------------

    def handles_delete(self, path: str) -> bool:
        if self._POOL.match(path):
            return True
        if self._POOL_TEMPLATE.match(path):
            return True
        return False

    def route_delete(self, path: str) -> dict[str, Any] | None:
        requester = self._requester_identity()

        m = self._POOL.match(path)
        if m:
            pool_id = m.group("pool_id")
            deleted = self._pool_mgr.delete_pool(pool_id)
            if not deleted:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "pool not found"})
            self._audit_event("pool.delete", "success", pool_id=pool_id, username=requester)
            return self._json(HTTPStatus.OK, {"ok": True, "pool_id": pool_id, "deleted": True})

        m = self._POOL_TEMPLATE.match(path)
        if m:
            template_id = m.group("tid")
            deleted = self._template_builder.delete_template(template_id)
            if not deleted:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "template not found"})
            self._audit_event("pool_template.delete", "success", template_id=template_id, username=requester)
            return self._json(HTTPStatus.OK, {"ok": True, "template_id": template_id, "deleted": True})

        return None
