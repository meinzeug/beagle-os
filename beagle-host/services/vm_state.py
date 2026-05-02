from __future__ import annotations

from typing import Any, Callable


class VmStateService:
    def __init__(
        self,
        *,
        build_profile: Callable[[Any], dict[str, Any]],
        latest_ubuntu_beagle_state_for_vmid: Callable[..., dict[str, Any] | None],
        load_action_queue: Callable[[str, int], list[dict[str, Any]]],
        load_action_result: Callable[[str, int], dict[str, Any] | None],
        load_endpoint_report: Callable[[str, int], dict[str, Any] | None],
        load_installer_prep_state: Callable[[str, int], dict[str, Any] | None],
        stale_endpoint_seconds: int,
        summarize_action_result: Callable[[dict[str, Any] | None], dict[str, Any]],
        summarize_endpoint_report: Callable[[dict[str, Any]], dict[str, Any]],
        summarize_installer_prep_state: Callable[[Any, dict[str, Any] | None], dict[str, Any]],
        timestamp_age_seconds: Callable[[str], int | None],
    ) -> None:
        self._build_profile = build_profile
        self._latest_ubuntu_beagle_state_for_vmid = latest_ubuntu_beagle_state_for_vmid
        self._load_action_queue = load_action_queue
        self._load_action_result = load_action_result
        self._load_endpoint_report = load_endpoint_report
        self._load_installer_prep_state = load_installer_prep_state
        self._stale_endpoint_seconds = int(stale_endpoint_seconds)
        self._summarize_action_result = summarize_action_result
        self._summarize_endpoint_report = summarize_endpoint_report
        self._summarize_installer_prep_state = summarize_installer_prep_state
        self._timestamp_age_seconds = timestamp_age_seconds

    def evaluate_endpoint_compliance(self, profile: dict[str, Any], report: dict[str, Any] | None) -> dict[str, Any]:
        managed = bool(profile.get("stream_host") or profile.get("assigned_target") or profile.get("expected_profile_name"))
        desired = {
            "stream_host": profile.get("stream_host", ""),
            "beagle_stream_client_port": profile.get("beagle_stream_client_port", ""),
            "beagle_stream_client_app": profile.get("beagle_stream_client_app", ""),
            "network_mode": profile.get("network_mode", ""),
            "egress_mode": profile.get("egress_mode", ""),
            "identity_timezone": profile.get("identity_timezone", ""),
            "identity_locale": profile.get("identity_locale", ""),
            "profile_name": profile.get("expected_profile_name", ""),
            "assigned_target": profile.get("assigned_target"),
        }
        if not isinstance(report, dict):
            return {
                "managed": managed,
                "endpoint_seen": False,
                "status": "pending" if managed else "unmanaged",
                "compliant": False,
                "drift_count": 0,
                "alert_count": 0,
                "drift": [],
                "alerts": [],
                "desired": desired,
            }

        summary = self._summarize_endpoint_report(report)
        drift: list[dict[str, Any]] = []
        alerts: list[dict[str, Any]] = []
        reported_at = str(summary.get("reported_at", ""))
        report_age_seconds = self._timestamp_age_seconds(reported_at)

        def compare(field: str, expected: str, actual: str, label: str) -> None:
            if not expected:
                return
            if str(expected).strip() == str(actual).strip():
                return
            drift.append({"field": field, "label": label, "expected": expected, "actual": actual})

        compare("stream_host", str(profile.get("stream_host", "")), str(summary.get("stream_host", "")), "Stream Host")
        compare("beagle_stream_client_port", str(profile.get("beagle_stream_client_port", "")), str(summary.get("beagle_stream_client_port", "")), "Beagle Stream Client Port")
        compare("beagle_stream_client_app", str(profile.get("beagle_stream_client_app", "")), str(summary.get("beagle_stream_client_app", "")), "Beagle Stream Client App")
        compare("network_mode", str(profile.get("network_mode", "")), str(summary.get("network_mode", "")), "Network Mode")
        compare("egress_mode", str(profile.get("egress_mode", "")), str(summary.get("egress_mode", "")), "Egress Mode")
        compare("identity_timezone", str(profile.get("identity_timezone", "")), str(summary.get("identity_timezone", "")), "Timezone")
        compare("identity_locale", str(profile.get("identity_locale", "")), str(summary.get("identity_locale", "")), "Locale")
        compare("profile_name", str(profile.get("expected_profile_name", "")), str(summary.get("profile_name", "")), "Profile Name")

        def alert(field: str, label: str, actual: str, expected: str = "1") -> None:
            if str(actual).strip() == str(expected).strip():
                return
            alerts.append({"field": field, "label": label, "expected": expected, "actual": actual})

        alert("beagle_stream_client_target_reachable", "Target Reachable", str(summary.get("beagle_stream_client_target_reachable", "")))
        alert("beagle_stream_server_api_reachable", "Beagle Stream Server API Reachable", str(summary.get("beagle_stream_server_api_reachable", "")))
        alert("runtime_binary_available", "Beagle Stream Client Runtime", str(summary.get("runtime_binary_available", "")))
        vm_fingerprint = profile.get("vm_fingerprint", {}) if isinstance(profile.get("vm_fingerprint"), dict) else {}
        if str(vm_fingerprint.get("risk_level", "")).lower() == "high":
            alerts.append({
                "field": "vm_fingerprint",
                "label": "VM Fingerprint",
                "expected": "low/medium risk",
                "actual": "high risk",
            })

        autologin_state = str(summary.get("autologin_state", "")).strip()
        if autologin_state and autologin_state != "active":
            alerts.append({"field": "autologin_state", "label": "Autologin", "expected": "active", "actual": autologin_state})

        status = "healthy"
        if drift:
            status = "drifted"
        elif report_age_seconds is not None and report_age_seconds > self._stale_endpoint_seconds:
            status = "stale"
            alerts.append({
                "field": "reported_at",
                "label": "Last Check-In",
                "expected": f"<={self._stale_endpoint_seconds}s",
                "actual": f"{report_age_seconds}s",
            })
        elif alerts:
            status = "degraded"

        return {
            "managed": managed,
            "endpoint_seen": True,
            "status": status,
            "compliant": not drift,
            "stale": bool(report_age_seconds is not None and report_age_seconds > self._stale_endpoint_seconds),
            "report_age_seconds": report_age_seconds,
            "drift_count": len(drift),
            "alert_count": len(alerts),
            "drift": drift,
            "alerts": alerts,
            "desired": desired,
        }

    def build_vm_state(self, vm: Any) -> dict[str, Any]:
        profile = self._build_profile(vm)
        report = self._load_endpoint_report(vm.node, vm.vmid)
        endpoint = self._summarize_endpoint_report(report or {})
        compliance = self.evaluate_endpoint_compliance(profile, report)
        last_action = self._summarize_action_result(self._load_action_result(vm.node, vm.vmid))
        pending_actions = self._load_action_queue(vm.node, vm.vmid)
        installer_prep = self._summarize_installer_prep_state(vm, self._load_installer_prep_state(vm.node, vm.vmid))
        provisioning = self._latest_ubuntu_beagle_state_for_vmid(vm.vmid)
        return {
            "profile": profile,
            "endpoint": endpoint,
            "compliance": compliance,
            "last_action": last_action,
            "pending_action_count": len(pending_actions),
            "installer_prep": installer_prep,
            "provisioning": provisioning,
        }
