from __future__ import annotations

import re
from dataclasses import asdict
from http import HTTPStatus
from typing import Any, Callable

from mdm_policy_service import MDMPolicy


class MDMPolicyHttpSurfaceService:
    _POLICY_DETAIL = re.compile(r"^/api/v1/fleet/policies/(?P<policy_id>[A-Za-z0-9._:-]+)$")

    def __init__(
        self,
        *,
        mdm_policy_service: Any,
        requester_identity: Callable[[], str] | None = None,
        audit_event: Callable[..., None] | None = None,
        service_name: str = "beagle-control-plane",
        utcnow: Callable[[], str],
        version: str = "",
    ) -> None:
        self._service = mdm_policy_service
        self._requester_identity = requester_identity or (lambda: "")
        self._audit_event = audit_event
        self._service_name = str(service_name or "beagle-control-plane")
        self._utcnow = utcnow
        self._version = str(version or "")

    @staticmethod
    def _json(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    def _envelope(self, **payload: Any) -> dict[str, Any]:
        return {
            "service": self._service_name,
            "version": self._version,
            "generated_at": self._utcnow(),
            **payload,
        }

    def _policy_to_dict(self, policy: Any) -> dict[str, Any]:
        return asdict(policy) if isinstance(policy, MDMPolicy) else {
            "policy_id": str(getattr(policy, "policy_id", "") or ""),
            "name": str(getattr(policy, "name", "") or ""),
            "allowed_networks": list(getattr(policy, "allowed_networks", []) or []),
            "allowed_pools": list(getattr(policy, "allowed_pools", []) or []),
            "max_resolution": str(getattr(policy, "max_resolution", "") or ""),
            "allowed_codecs": list(getattr(policy, "allowed_codecs", []) or []),
            "auto_update": bool(getattr(policy, "auto_update", True)),
            "update_window_start_hour": int(getattr(policy, "update_window_start_hour", 2) or 2),
            "update_window_end_hour": int(getattr(policy, "update_window_end_hour", 4) or 4),
            "screen_lock_timeout_seconds": int(getattr(policy, "screen_lock_timeout_seconds", 0) or 0),
        }

    def _safe_audit(self, event_type: str, outcome: str, **details: Any) -> None:
        if self._audit_event is None:
            return
        try:
            payload = dict(details)
            payload.setdefault("username", self._requester_identity())
            self._audit_event(event_type, outcome, **payload)
        except Exception:
            return

    @staticmethod
    def _csv_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    def _policy_from_payload(self, payload: dict[str, Any], policy_id: str | None = None) -> MDMPolicy:
        pid = str(policy_id or payload.get("policy_id") or "").strip()
        if not pid:
            raise ValueError("policy_id required")
        name = str(payload.get("name") or pid).strip()
        if not name:
            raise ValueError("name required")
        return MDMPolicy(
            policy_id=pid,
            name=name,
            allowed_networks=self._csv_list(payload.get("allowed_networks")),
            allowed_pools=self._csv_list(payload.get("allowed_pools")),
            max_resolution=str(payload.get("max_resolution") or "").strip(),
            allowed_codecs=self._csv_list(payload.get("allowed_codecs")),
            auto_update=bool(payload.get("auto_update", True)),
            update_window_start_hour=int(payload.get("update_window_start_hour", 2) or 2),
            update_window_end_hour=int(payload.get("update_window_end_hour", 4) or 4),
            screen_lock_timeout_seconds=int(payload.get("screen_lock_timeout_seconds", 0) or 0),
        )

    def handles_get(self, path: str) -> bool:
        return path in {"/api/v1/fleet/policies", "/api/v1/fleet/policies/assignments"} or self._POLICY_DETAIL.match(path) is not None

    def route_get(self, path: str, *, query: dict[str, list[str]] | None = None) -> dict[str, Any] | None:
        if path == "/api/v1/fleet/policies":
            policies = [self._policy_to_dict(item) for item in self._service.list_policies()]
            return self._json(HTTPStatus.OK, {"ok": True, **self._envelope(policies=policies)})
        if path == "/api/v1/fleet/policies/assignments":
            return self._json(HTTPStatus.OK, {"ok": True, **self._envelope(**self._service.list_assignments())})
        match = self._POLICY_DETAIL.match(path)
        if match is None:
            return None
        policy = self._service.get_policy(match.group("policy_id"))
        if policy is None:
            return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "policy not found"})
        return self._json(HTTPStatus.OK, {"ok": True, **self._envelope(policy=self._policy_to_dict(policy))})

    def handles_post(self, path: str) -> bool:
        return path in {"/api/v1/fleet/policies", "/api/v1/fleet/policies/assignments", "/api/v1/fleet/policies/assignments/bulk"}

    def route_post(self, path: str, *, json_payload: dict[str, Any] | None = None, requester: str = "") -> dict[str, Any] | None:
        payload = json_payload or {}
        if path == "/api/v1/fleet/policies":
            try:
                policy = self._policy_from_payload(payload)
                created = self._service.create_policy(policy)
            except (ValueError, KeyError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._safe_audit("fleet.policy.create", "success", username=requester or self._requester_identity(), policy_id=created.policy_id)
            return self._json(HTTPStatus.CREATED, {"ok": True, **self._envelope(policy=self._policy_to_dict(created))})
        if path == "/api/v1/fleet/policies/assignments":
            target_type = str(payload.get("target_type") or "").strip().lower()
            target_id = str(payload.get("target_id") or "").strip()
            policy_id = str(payload.get("policy_id") or "").strip()
            if target_type not in {"device", "group"} or not target_id:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "target_type device|group and target_id required"})
            try:
                if not policy_id:
                    changed = self._service.clear_device_assignment(target_id) if target_type == "device" else self._service.clear_group_assignment(target_id)
                    outcome = "cleared" if changed else "unchanged"
                elif target_type == "device":
                    self._service.assign_to_device(target_id, policy_id)
                    outcome = "assigned"
                else:
                    self._service.assign_to_group(target_id, policy_id)
                    outcome = "assigned"
            except KeyError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._safe_audit("fleet.policy.assign", "success", username=requester or self._requester_identity(), target_type=target_type, target_id=target_id, policy_id=policy_id, assignment_status=outcome)
            return self._json(HTTPStatus.OK, {"ok": True, **self._envelope(target_type=target_type, target_id=target_id, policy_id=policy_id, assignment_status=outcome, **self._service.list_assignments())})
        if path == "/api/v1/fleet/policies/assignments/bulk":
            target_type = str(payload.get("target_type") or "device").strip().lower()
            policy_id = str(payload.get("policy_id") or "").strip()
            target_ids = payload.get("target_ids")
            if target_type != "device":
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "bulk target_type must be device"})
            if not isinstance(target_ids, list):
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "target_ids list required"})
            normalized_ids = [str(item or "").strip() for item in target_ids if str(item or "").strip()]
            if not normalized_ids:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "at least one target_id required"})
            try:
                if policy_id:
                    affected = self._service.assign_to_devices(normalized_ids, policy_id)
                    assignment_status = "assigned"
                else:
                    affected = self._service.clear_device_assignments(normalized_ids)
                    assignment_status = "cleared"
            except KeyError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._safe_audit(
                "fleet.policy.bulk_assign",
                "success",
                username=requester or self._requester_identity(),
                target_type=target_type,
                policy_id=policy_id,
                affected_count=len(affected),
                assignment_status=assignment_status,
            )
            return self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        target_type=target_type,
                        policy_id=policy_id,
                        affected_ids=affected,
                        assignment_status=assignment_status,
                        **self._service.list_assignments(),
                    ),
                },
            )
        return None

    def handles_put(self, path: str) -> bool:
        return self._POLICY_DETAIL.match(path) is not None

    def route_put(self, path: str, *, json_payload: dict[str, Any] | None = None, requester: str = "") -> dict[str, Any] | None:
        match = self._POLICY_DETAIL.match(path)
        if match is None:
            return None
        try:
            policy = self._policy_from_payload(json_payload or {}, match.group("policy_id"))
            updated = self._service.update_policy(policy)
        except (ValueError, KeyError) as exc:
            return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        self._safe_audit("fleet.policy.update", "success", username=requester or self._requester_identity(), policy_id=updated.policy_id)
        return self._json(HTTPStatus.OK, {"ok": True, **self._envelope(policy=self._policy_to_dict(updated))})

    def handles_delete(self, path: str) -> bool:
        return self._POLICY_DETAIL.match(path) is not None

    def route_delete(self, path: str, *, requester: str = "") -> dict[str, Any] | None:
        match = self._POLICY_DETAIL.match(path)
        if match is None:
            return None
        policy_id = match.group("policy_id")
        deleted = self._service.delete_policy(policy_id)
        if not deleted:
            return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "policy not found"})
        self._safe_audit("fleet.policy.delete", "success", username=requester or self._requester_identity(), policy_id=policy_id)
        return self._json(HTTPStatus.OK, {"ok": True, **self._envelope(policy_id=policy_id, deleted=True)})
