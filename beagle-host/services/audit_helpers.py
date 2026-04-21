from __future__ import annotations

from typing import Any


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def build_vm_power_audit_event(response: dict[str, Any] | None, *, requester_identity: str) -> dict[str, Any] | None:
    if not isinstance(response, dict):
        return None
    payload = response.get("payload")
    if not isinstance(payload, dict):
        return None
    vm_power = payload.get("vm_power")
    if not isinstance(vm_power, dict):
        return None

    action_name = str(vm_power.get("action") or "").strip().lower()
    if action_name not in {"start", "stop", "reboot"}:
        return None

    status = _safe_int(response.get("status"), default=500)
    vmid = _safe_int(vm_power.get("vmid"), default=0)
    return {
        "event_type": f"vm.{action_name}",
        "outcome": "success" if status < 400 else "error",
        "details": {
            "username": str(requester_identity or "").strip(),
            "vmid": vmid,
            "node": str(vm_power.get("node") or ""),
            "resource_type": "vm",
            "resource_id": vmid,
        },
    }