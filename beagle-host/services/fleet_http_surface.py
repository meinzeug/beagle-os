"""Fleet / Thin-client Device Registry HTTP surface.

GoEnterprise Plan 02:
- device registry CRUD/read surface
- heartbeat / lock / wipe state transitions
"""
from __future__ import annotations

import re
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable

from core.persistence.json_state_store import JsonStateStore


class FleetHttpSurfaceService:
    _FLEET_REMEDIATION_DRIFT = "/api/v1/fleet/remediation/drift"
    _FLEET_REMEDIATION_CONFIG = "/api/v1/fleet/remediation/config"
    _FLEET_REMEDIATION_HISTORY = "/api/v1/fleet/remediation/history"
    _FLEET_REMEDIATION_RUN = "/api/v1/fleet/remediation/run"
    _DEVICE_DETAIL = re.compile(r"^/api/v1/fleet/devices/(?P<device_id>[A-Za-z0-9._:-]+)$")
    _DEVICE_EFFECTIVE_POLICY = re.compile(r"^/api/v1/fleet/devices/(?P<device_id>[A-Za-z0-9._:-]+)/effective-policy$")
    _DEVICE_REMEDIATION = re.compile(r"^/api/v1/fleet/devices/(?P<device_id>[A-Za-z0-9._:-]+)/remediation/execute$")
    _DEVICE_ACTION = re.compile(r"^/api/v1/fleet/devices/(?P<device_id>[A-Za-z0-9._:-]+)/(?P<action>heartbeat|lock|unlock|wipe|confirm-wiped)$")
    _DEVICE_BULK_ACTIONS = "/api/v1/fleet/devices/actions/bulk"

    def __init__(
        self,
        *,
        device_registry_service: Any,
        mdm_policy_service: Any | None = None,
        audit_event: Callable[..., None] | None = None,
        requester_identity: Callable[[], str] | None = None,
        remediation_state_file: Path | None = None,
        service_name: str = "beagle-control-plane",
        utcnow: Callable[[], str],
        version: str = "",
    ) -> None:
        self._registry = device_registry_service
        self._mdm_policy = mdm_policy_service
        self._audit_event = audit_event
        self._requester_identity = requester_identity or (lambda: "")
        self._service_name = str(service_name or "beagle-control-plane")
        self._utcnow = utcnow
        self._version = str(version or "")
        self._remediation_store = JsonStateStore(
            remediation_state_file or Path("/var/lib/beagle/beagle-manager/fleet-remediation.json"),
            default_factory=lambda: {
                "enabled": False,
                "safe_actions": ["clear-device-policy-assignment"],
                "excluded_device_ids": [],
                "history": [],
                "last_run": {},
            },
        )
        self._remediation_state = self._remediation_store.load()

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

    def _safe_audit_event(self, event_type: str, outcome: str, **details: Any) -> None:
        if self._audit_event is None:
            return
        try:
            payload = dict(details)
            payload.setdefault("username", self._requester_identity())
            self._audit_event(
                event_type,
                outcome,
                **payload,
            )
        except Exception:
            return

    def _build_remediation_hints(self, *, device: Any, policy_validation: dict[str, Any], conflicts: list[str], diagnostics: dict[str, Any]) -> list[str]:
        hints: list[str] = []
        if conflicts:
            hints.append("Pruefe die Device-Zuweisung und entferne sie, wenn wieder die Gruppenpolicy gelten soll.")
        if str(getattr(device, "group", "") or "").strip() == "":
            hints.append("Ordne das Geraet einer Gruppe zu, damit Gruppenpolicies und Bulk-Operationen greifen.")
        if str(diagnostics.get("effective_source_type") or "") == "default":
            hints.append("Weise eine explizite Device- oder Gruppenpolicy zu, statt auf der Default-Policy zu bleiben.")
        warnings = list(policy_validation.get("warnings") or [])
        if any("allows all pools" in str(item) for item in warnings):
            hints.append("Begrenze allowed_pools, wenn das Geraet nicht auf alle Pools zugreifen soll.")
        if any("allows all networks" in str(item) for item in warnings):
            hints.append("Begrenze allowed_networks auf vertrauenswuerdige Netze oder WireGuard.")
        if any("allows all codecs" in str(item) for item in warnings):
            hints.append("Reduziere allowed_codecs auf die wirklich freigegebenen Stream-Codecs.")
        if str(getattr(device, "status", "") or "") == "locked":
            hints.append("Entsperre das Geraet erst nach Abschluss der Operator-Pruefung wieder.")
        if str(getattr(device, "status", "") or "") == "wipe_pending":
            hints.append("Halte das Geraet online, bis der naechste Sync den Wipe bestaetigt.")
        return hints

    def _build_remediation_actions(self, *, device: Any, policy_validation: dict[str, Any], conflicts: list[str], diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        if conflicts:
            actions.append({"action": "clear-device-policy-assignment", "label": "Device-Policy-Zuweisung loeschen", "target_type": "device", "target_id": str(getattr(device, "device_id", "") or ""), "recommended": True})
        if str(getattr(device, "group", "") or "").strip() == "":
            actions.append({"action": "assign-group", "label": "Geraet einer Gruppe zuordnen", "target_type": "device", "target_id": str(getattr(device, "device_id", "") or ""), "recommended": True})
        if str(diagnostics.get("effective_source_type") or "") == "default":
            actions.append({"action": "assign-explicit-policy", "label": "Explizite Policy zuweisen", "target_type": "device", "target_id": str(getattr(device, "device_id", "") or ""), "recommended": True})
        warnings = list(policy_validation.get("warnings") or [])
        if any("allows all pools" in str(item) for item in warnings):
            actions.append({"action": "restrict-allowed-pools", "label": "Allowed Pools eingrenzen", "recommended": False})
        if any("allows all networks" in str(item) for item in warnings):
            actions.append({"action": "restrict-allowed-networks", "label": "Allowed Networks eingrenzen", "recommended": False})
        if any("allows all codecs" in str(item) for item in warnings):
            actions.append({"action": "restrict-allowed-codecs", "label": "Allowed Codecs eingrenzen", "recommended": False})
        if str(getattr(device, "status", "") or "") == "locked":
            actions.append({"action": "unlock-device", "label": "Geraet entsperren", "target_type": "device", "target_id": str(getattr(device, "device_id", "") or ""), "recommended": False})
        if str(getattr(device, "status", "") or "") == "wipe_pending":
            actions.append({"action": "await-wipe-confirmation", "label": "Wipe-Bestaetigung abwarten", "recommended": True})
        return actions

    def _device_policy_bundle(self, device: Any) -> dict[str, Any]:
        if self._mdm_policy is None:
            return {
                "source_type": "default",
                "source_id": "__default__",
                "conflicts": [],
                "diagnostics": {},
                "remediation_hints": [],
                "remediation_actions": [],
                "policy": None,
            }
        device_id = str(getattr(device, "device_id", "") or "")
        group = str(getattr(device, "group", "") or "")
        policy, source_type, source_id = self._mdm_policy.resolve_policy_with_source(device_id, group=group)
        diagnostics = self._mdm_policy.build_effective_policy_diagnostics(device_id, group=group)
        policy_validation = self._mdm_policy.validate_policy(policy)
        conflicts = self._mdm_policy.describe_effective_policy_conflicts(device_id, group=group)
        remediation_hints = self._build_remediation_hints(
            device=device,
            policy_validation=policy_validation,
            conflicts=conflicts,
            diagnostics=diagnostics,
        )
        remediation_actions = self._build_remediation_actions(
            device=device,
            policy_validation=policy_validation,
            conflicts=conflicts,
            diagnostics=diagnostics,
        )
        return {
            "source_type": source_type,
            "source_id": source_id,
            "conflicts": conflicts,
            "diagnostics": diagnostics,
            "remediation_hints": remediation_hints,
            "remediation_actions": remediation_actions,
            "policy": {
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
                "validation": policy_validation,
            },
        }

    @staticmethod
    def _safe_auto_remediation_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        allowed = {"clear-device-policy-assignment"}
        return [item for item in actions if str(item.get("action") or "") in allowed]

    def _remediation_config(self) -> dict[str, Any]:
        return {
            "enabled": bool(self._remediation_state.get("enabled", False)),
            "safe_actions": [str(item or "").strip() for item in self._remediation_state.get("safe_actions", []) if str(item or "").strip()],
            "excluded_device_ids": [str(item or "").strip() for item in self._remediation_state.get("excluded_device_ids", []) if str(item or "").strip()],
            "last_run": dict(self._remediation_state.get("last_run", {}) or {}),
        }

    def _remediation_history(self) -> list[dict[str, Any]]:
        return list(self._remediation_state.get("history", []) or [])

    def _save_remediation_state(self) -> None:
        self._remediation_store.save(self._remediation_state)

    def _update_remediation_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "enabled" in payload:
            self._remediation_state["enabled"] = bool(payload.get("enabled"))
        if "safe_actions" in payload:
            raw = payload.get("safe_actions")
            if not isinstance(raw, list):
                raise ValueError("safe_actions must be a list")
            self._remediation_state["safe_actions"] = [str(item or "").strip() for item in raw if str(item or "").strip()]
        if "excluded_device_ids" in payload:
            raw = payload.get("excluded_device_ids")
            if not isinstance(raw, list):
                raise ValueError("excluded_device_ids must be a list")
            self._remediation_state["excluded_device_ids"] = [str(item or "").strip() for item in raw if str(item or "").strip()]
        self._save_remediation_state()
        return self._remediation_config()

    def _configured_safe_auto_remediation_actions(self, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        configured = set(self._remediation_config().get("safe_actions") or [])
        if not configured:
            return []
        return [item for item in self._safe_auto_remediation_actions(actions) if str(item.get("action") or "") in configured]

    def _record_remediation_run(self, *, dry_run: bool, applied: list[dict[str, Any]], skipped: list[dict[str, Any]], failed: list[dict[str, Any]]) -> None:
        run_summary = {
            "ran_at": self._utcnow(),
            "dry_run": bool(dry_run),
            "applied_count": len(applied),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
        }
        history = list(self._remediation_state.get("history", []) or [])
        history.insert(0, {**run_summary, "applied": applied[:20], "failed": failed[:20]})
        self._remediation_state["history"] = history[:25]
        self._remediation_state["last_run"] = run_summary
        self._save_remediation_state()

    @staticmethod
    def _hardware_to_dict(hardware: Any) -> dict[str, Any]:
        return {
            "cpu_model": str(getattr(hardware, "cpu_model", "") or ""),
            "cpu_cores": int(getattr(hardware, "cpu_cores", 0) or 0),
            "ram_gb": int(getattr(hardware, "ram_gb", 0) or 0),
            "gpu_model": str(getattr(hardware, "gpu_model", "") or ""),
            "network_interfaces": list(getattr(hardware, "network_interfaces", []) or []),
            "disk_gb": int(getattr(hardware, "disk_gb", 0) or 0),
        }

    @classmethod
    def _device_to_dict(cls, device: Any) -> dict[str, Any]:
        return {
            "device_id": str(getattr(device, "device_id", "") or ""),
            "hostname": str(getattr(device, "hostname", "") or ""),
            "hardware": cls._hardware_to_dict(getattr(device, "hardware", None)),
            "os_version": str(getattr(device, "os_version", "") or ""),
            "enrolled_at": str(getattr(device, "enrolled_at", "") or ""),
            "last_seen": str(getattr(device, "last_seen", "") or ""),
            "location": str(getattr(device, "location", "") or ""),
            "group": str(getattr(device, "group", "") or ""),
            "status": str(getattr(device, "status", "offline") or "offline"),
            "vpn_active": bool(getattr(device, "vpn_active", False)),
            "vpn_interface": str(getattr(device, "vpn_interface", "") or ""),
            "wg_public_key": str(getattr(device, "wg_public_key", "") or ""),
            "wg_assigned_ip": str(getattr(device, "wg_assigned_ip", "") or ""),
            "notes": str(getattr(device, "notes", "") or ""),
            "wipe_requested_at": str(getattr(device, "wipe_requested_at", "") or ""),
            "wipe_confirmed_at": str(getattr(device, "wipe_confirmed_at", "") or ""),
            "last_wipe_report": dict(getattr(device, "last_wipe_report", {}) or {}),
        }

    def handles_get(self, path: str) -> bool:
        if path == self._FLEET_REMEDIATION_DRIFT:
            return True
        if path == self._FLEET_REMEDIATION_CONFIG:
            return True
        if path == self._FLEET_REMEDIATION_HISTORY:
            return True
        if path == "/api/v1/fleet/devices":
            return True
        if path == "/api/v1/fleet/devices/groups":
            return True
        if self._DEVICE_EFFECTIVE_POLICY.match(path):
            return True
        return self._DEVICE_DETAIL.match(path) is not None

    def route_get(self, path: str, *, query: dict[str, list[str]] | None = None) -> dict[str, Any] | None:
        params = query or {}
        if path == self._FLEET_REMEDIATION_CONFIG:
            return self._json(HTTPStatus.OK, {"ok": True, **self._envelope(config=self._remediation_config())})
        if path == self._FLEET_REMEDIATION_HISTORY:
            return self._json(HTTPStatus.OK, {"ok": True, **self._envelope(history=self._remediation_history())})
        if path == self._FLEET_REMEDIATION_DRIFT:
            devices = self._registry.list_devices()
            excluded = set(self._remediation_config().get("excluded_device_ids") or [])
            entries: list[dict[str, Any]] = []
            for device in devices:
                bundle = self._device_policy_bundle(device)
                actions = list(bundle.get("remediation_actions") or [])
                safe_actions = self._configured_safe_auto_remediation_actions(actions)
                excluded_device = str(getattr(device, "device_id", "") or "") in excluded
                drifted = bool(bundle.get("conflicts")) or bool(bundle.get("remediation_hints")) or bool(safe_actions)
                entries.append(
                    {
                        "device": self._device_to_dict(device),
                        "drifted": drifted,
                        "excluded": excluded_device,
                        "conflicts": list(bundle.get("conflicts") or []),
                        "safe_actions": safe_actions,
                        "remediation_actions": actions,
                        "source_type": str(bundle.get("source_type") or "default"),
                    }
                )
            drifted_entries = [item for item in entries if item["drifted"]]
            return self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        devices=entries,
                        drifted_count=len(drifted_entries),
                        safe_candidate_count=sum(len(item["safe_actions"]) for item in drifted_entries),
                    ),
                },
            )
        if path == "/api/v1/fleet/devices":
            location = str((params.get("location") or [""])[0] or "").strip() or None
            group = str((params.get("group") or [""])[0] or "").strip() or None
            status = str((params.get("status") or [""])[0] or "").strip() or None
            devices = self._registry.list_devices(location=location, group=group, status=status)
            payload = [self._device_to_dict(item) for item in devices]
            return self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        devices=payload,
                        groups=self._registry.list_groups(),
                        count=len(payload),
                    ),
                },
            )
        if path == "/api/v1/fleet/devices/groups":
            return self._json(
                HTTPStatus.OK,
                {"ok": True, **self._envelope(groups=self._registry.list_groups())},
            )

        match = self._DEVICE_EFFECTIVE_POLICY.match(path)
        if match is not None:
            device = self._registry.get_device(match.group("device_id"))
            if device is None:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "device not found"})
            bundle = self._device_policy_bundle(device)
            return self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        device_id=str(getattr(device, "device_id", "") or ""),
                        group=str(getattr(device, "group", "") or ""),
                        source_type=bundle["source_type"],
                        source_id=bundle["source_id"],
                        conflicts=bundle["conflicts"],
                        diagnostics=bundle["diagnostics"],
                        remediation_hints=bundle["remediation_hints"],
                        remediation_actions=bundle["remediation_actions"],
                        policy=bundle["policy"],
                    ),
                },
            )

        match = self._DEVICE_DETAIL.match(path)
        if match is None:
            return None
        device = self._registry.get_device(match.group("device_id"))
        if device is None:
            return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "device not found"})
        return self._json(
            HTTPStatus.OK,
            {"ok": True, **self._envelope(device=self._device_to_dict(device))},
        )

    def handles_post(self, path: str) -> bool:
        if path == "/api/v1/fleet/devices/register":
            return True
        if path == self._FLEET_REMEDIATION_RUN:
            return True
        if path == self._DEVICE_BULK_ACTIONS:
            return True
        if self._DEVICE_REMEDIATION.match(path):
            return True
        return self._DEVICE_ACTION.match(path) is not None

    @staticmethod
    def _normalized_csv_values(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item or "").strip() for item in value if str(item or "").strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return []

    def _execute_remediation_action(self, *, device: Any, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        action = str(payload.get("action") or "").strip()
        if not action:
            raise ValueError("action required")
        device_id = str(getattr(device, "device_id", "") or "")

        if action == "clear-device-policy-assignment":
            if self._mdm_policy is None:
                raise ValueError("mdm policy service unavailable")
            changed = bool(self._mdm_policy.clear_device_assignment(device_id))
            return {"changed": changed}, action
        if action == "assign-explicit-policy":
            if self._mdm_policy is None:
                raise ValueError("mdm policy service unavailable")
            policy_id = str(payload.get("policy_id") or "").strip()
            if not policy_id:
                raise ValueError("policy_id required")
            self._mdm_policy.assign_to_device(device_id, policy_id)
            return {"policy_id": policy_id, "changed": True}, action
        if action == "assign-group":
            group = str(payload.get("group") or payload.get("value") or "").strip()
            if not group:
                raise ValueError("group required")
            updated = self._registry.set_group(device_id, group)
            return {"group": str(updated.group), "changed": True}, action
        if action == "unlock-device":
            updated = self._registry.unlock_device(device_id)
            return {"status": str(updated.status), "changed": True}, action
        if action == "await-wipe-confirmation":
            return {"changed": False, "status": str(getattr(device, "status", "") or "")}, action
        if action in {"restrict-allowed-pools", "restrict-allowed-networks", "restrict-allowed-codecs"}:
            if self._mdm_policy is None:
                raise ValueError("mdm policy service unavailable")
            policy_id = str(payload.get("policy_id") or "").strip()
            if not policy_id:
                raise ValueError("policy_id required")
            policy = self._mdm_policy.get_policy(policy_id)
            if policy is None:
                raise KeyError(f"Policy {policy_id!r} not found")
            if action == "restrict-allowed-pools":
                policy.allowed_pools = self._normalized_csv_values(payload.get("allowed_pools"))
            elif action == "restrict-allowed-networks":
                policy.allowed_networks = self._normalized_csv_values(payload.get("allowed_networks"))
            else:
                policy.allowed_codecs = self._normalized_csv_values(payload.get("allowed_codecs"))
            self._mdm_policy.update_policy(policy)
            return {"policy_id": policy_id, "changed": True}, action
        raise ValueError(f"unsupported remediation action: {action}")

    def route_post(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
        requester: str = "",
    ) -> dict[str, Any] | None:
        payload = json_payload or {}
        requester_name = str(requester or "").strip()
        if path == self._FLEET_REMEDIATION_RUN:
            device_ids_raw = payload.get("device_ids")
            dry_run = bool(payload.get("dry_run", False))
            excluded = set(self._remediation_config().get("excluded_device_ids") or [])
            if isinstance(device_ids_raw, list):
                normalized_ids = [str(item or "").strip() for item in device_ids_raw if str(item or "").strip()]
                devices = [self._registry.get_device(device_id) for device_id in normalized_ids]
                devices = [item for item in devices if item is not None]
            else:
                devices = self._registry.list_devices()
            applied: list[dict[str, Any]] = []
            skipped: list[dict[str, Any]] = []
            failed: list[dict[str, Any]] = []
            for device in devices:
                device_id = str(getattr(device, "device_id", "") or "")
                if device_id in excluded:
                    skipped.append({"device_id": device_id, "reason": "excluded"})
                    continue
                safe_actions = self._configured_safe_auto_remediation_actions(list(self._device_policy_bundle(device).get("remediation_actions") or []))
                if not safe_actions:
                    skipped.append({"device_id": device_id, "reason": "no safe actions"})
                    continue
                for action in safe_actions:
                    action_name = str(action.get("action") or "")
                    if dry_run:
                        applied.append({"device_id": device_id, "action": action_name, "dry_run": True})
                        continue
                    try:
                        result, _ = self._execute_remediation_action(device=device, payload={"action": action_name})
                        applied.append({"device_id": device_id, "action": action_name, "result": result})
                    except Exception as exc:
                        failed.append({"device_id": device_id, "action": action_name, "error": str(exc)})
            self._record_remediation_run(dry_run=dry_run, applied=applied, skipped=skipped, failed=failed)
            self._safe_audit_event(
                "fleet.remediation.run",
                "success" if not failed else "partial",
                username=requester_name or self._requester_identity(),
                applied_count=len(applied),
                skipped_count=len(skipped),
                failed_count=len(failed),
                dry_run=dry_run,
            )
            return self._json(
                HTTPStatus.OK,
                {"ok": True, **self._envelope(applied=applied, skipped=skipped, failed=failed, dry_run=dry_run, last_run=self._remediation_state.get("last_run", {}))},
            )
        remediation_match = self._DEVICE_REMEDIATION.match(path)
        if remediation_match is not None:
            device = self._registry.get_device(remediation_match.group("device_id"))
            if device is None:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "device not found"})
            try:
                result, action = self._execute_remediation_action(device=device, payload=payload)
            except KeyError as exc:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": str(exc)})
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            updated_device = self._registry.get_device(remediation_match.group("device_id")) or device
            self._safe_audit_event(
                "fleet.device.remediation",
                "success",
                device_id=str(getattr(updated_device, "device_id", "") or ""),
                action=action,
                requester=requester_name,
            )
            return self._json(
                HTTPStatus.OK,
                {"ok": True, **self._envelope(action=action, result=result, device=self._device_to_dict(updated_device))},
            )
        if path == "/api/v1/fleet/devices/register":
            device_id = str(payload.get("device_id") or "").strip()
            hostname = str(payload.get("hostname") or "").strip()
            hardware = payload.get("hardware")
            if not device_id or not hostname or not isinstance(hardware, dict):
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "device_id, hostname, hardware required"})
            device = self._registry.register_device(
                device_id,
                hostname,
                hardware,
                os_version=str(payload.get("os_version") or "").strip(),
                vpn_active=bool(payload.get("vpn_active", False)),
                vpn_interface=str(payload.get("vpn_interface") or "").strip(),
                wg_public_key=str(payload.get("wg_public_key") or "").strip(),
                wg_assigned_ip=str(payload.get("wg_assigned_ip") or "").strip(),
            )
            self._safe_audit_event(
                "fleet.device.register",
                "success",
                username=requester_name or self._requester_identity(),
                device_id=device_id,
                hostname=hostname,
            )
            return self._json(
                HTTPStatus.CREATED,
                {"ok": True, **self._envelope(device=self._device_to_dict(device))},
            )
        if path == self._DEVICE_BULK_ACTIONS:
            action = str(payload.get("action") or "").strip().lower()
            target_ids = payload.get("target_ids")
            value = str(payload.get("value") or "").strip()
            if action not in {"lock", "unlock", "wipe", "set-group", "set-location"}:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "unsupported bulk action"})
            if not isinstance(target_ids, list):
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "target_ids list required"})
            normalized_ids = [str(item or "").strip() for item in target_ids if str(item or "").strip()]
            if not normalized_ids:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "at least one target_id required"})
            if action in {"set-group", "set-location"} and not value:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "value required for set-group or set-location"})
            affected: list[dict[str, Any]] = []
            failed: list[dict[str, Any]] = []
            for device_id in normalized_ids:
                try:
                    if action == "lock":
                        device = self._registry.lock_device(device_id)
                    elif action == "unlock":
                        device = self._registry.unlock_device(device_id)
                    elif action == "wipe":
                        device = self._registry.wipe_device(device_id)
                    elif action == "set-group":
                        device = self._registry.set_group(device_id, value)
                    else:
                        device = self._registry.set_location(device_id, value)
                    affected.append(self._device_to_dict(device))
                except KeyError:
                    failed.append({"device_id": device_id, "error": "device not found"})
            self._safe_audit_event(
                "fleet.device.bulk_action",
                "success" if not failed else "partial",
                username=requester_name or self._requester_identity(),
                action=action,
                target_count=len(normalized_ids),
                affected_count=len(affected),
                failed_count=len(failed),
                value=value or None,
            )
            return self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        action=action,
                        affected=affected,
                        failed=failed,
                        value=value,
                    ),
                },
            )

        match = self._DEVICE_ACTION.match(path)
        if match is None:
            return None
        device_id = match.group("device_id")
        action = match.group("action")
        try:
            if action == "heartbeat":
                device = self._registry.update_heartbeat(device_id, metrics=payload.get("metrics"))
            elif action == "lock":
                device = self._registry.lock_device(device_id)
            elif action == "unlock":
                device = self._registry.unlock_device(device_id)
            elif action == "wipe":
                device = self._registry.wipe_device(device_id)
            elif action == "confirm-wiped":
                device = self._registry.confirm_wiped(device_id)
            else:
                return None
        except KeyError:
            return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "device not found"})
        self._safe_audit_event(
            f"fleet.device.{action}",
            "success",
            username=requester_name or self._requester_identity(),
            device_id=device_id,
            status=str(getattr(device, "status", "") or ""),
        )
        return self._json(
            HTTPStatus.OK,
            {"ok": True, "action": action, **self._envelope(device=self._device_to_dict(device))},
        )

    def handles_put(self, path: str) -> bool:
        if path == self._FLEET_REMEDIATION_CONFIG:
            return True
        return self._DEVICE_DETAIL.match(path) is not None

    def route_put(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
        requester: str = "",
    ) -> dict[str, Any] | None:
        payload = json_payload or {}
        requester_name = str(requester or "").strip()
        if path == self._FLEET_REMEDIATION_CONFIG:
            try:
                config = self._update_remediation_config(payload)
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._safe_audit_event(
                "fleet.remediation.config",
                "success",
                username=requester_name or self._requester_identity(),
                enabled=config.get("enabled"),
            )
            return self._json(HTTPStatus.OK, {"ok": True, **self._envelope(config=config)})
        match = self._DEVICE_DETAIL.match(path)
        if match is None:
            return None
        device_id = match.group("device_id")
        try:
            device = self._registry.get_device(device_id)
            if device is None:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "device not found"})
            if "location" in payload:
                device = self._registry.set_location(device_id, str(payload.get("location") or "").strip())
            if "group" in payload:
                device = self._registry.set_group(device_id, str(payload.get("group") or "").strip())
            if "notes" in payload:
                raw = self._registry._require(device_id)
                raw["notes"] = str(payload.get("notes") or "").strip()
                self._registry._save()
                device = self._registry.get_device(device_id)
            if device is None:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "device not found"})
        except KeyError:
            return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "device not found"})
        self._safe_audit_event(
            "fleet.device.update",
            "success",
            username=requester_name or self._requester_identity(),
            device_id=device_id,
            location=str(payload.get("location") or "").strip() if "location" in payload else None,
            group=str(payload.get("group") or "").strip() if "group" in payload else None,
            notes_updated="notes" in payload,
        )
        return self._json(
            HTTPStatus.OK,
            {"ok": True, **self._envelope(device=self._device_to_dict(device))},
        )
