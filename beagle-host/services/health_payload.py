from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class HealthPayloadService:
    def __init__(
        self,
        *,
        build_profile: Callable[[Any], dict[str, Any]],
        data_dir: Path,
        downloads_status_file: Path,
        host_provider_kind: str,
        list_endpoint_reports: Callable[[], list[Any]],
        list_policies: Callable[[], list[Any]],
        list_providers: Callable[[], list[str]],
        list_vms: Callable[[], list[Any]],
        load_action_queue: Callable[[str, int], list[dict[str, Any]]],
        load_endpoint_report: Callable[[str, int], dict[str, Any] | None],
        load_json_file: Callable[[Path, Any], Any],
        service_name: str,
        stale_endpoint_seconds: int,
        summarize_endpoint_report: Callable[[dict[str, Any]], dict[str, Any]],
        utcnow: Callable[[], str],
        version: str,
        vm_installers_file: Path,
    ) -> None:
        self._build_profile = build_profile
        self._data_dir = data_dir
        self._downloads_status_file = downloads_status_file
        self._host_provider_kind = str(host_provider_kind or "")
        self._list_endpoint_reports = list_endpoint_reports
        self._list_policies = list_policies
        self._list_providers = list_providers
        self._list_vms = list_vms
        self._load_action_queue = load_action_queue
        self._load_endpoint_report = load_endpoint_report
        self._load_json_file = load_json_file
        self._service_name = str(service_name or "beagle-control-plane")
        self._stale_endpoint_seconds = int(stale_endpoint_seconds)
        self._summarize_endpoint_report = summarize_endpoint_report
        self._utcnow = utcnow
        self._version = str(version or "")
        self._vm_installers_file = vm_installers_file

    def build_payload(self) -> dict[str, Any]:
        warnings: list[str] = []
        try:
            downloads_status = self._load_json_file(self._downloads_status_file, {})
        except Exception as exc:
            downloads_status = {}
            warnings.append(f"downloads_status_unavailable:{exc}")
        try:
            vm_installers = self._load_json_file(self._vm_installers_file, [])
        except Exception as exc:
            vm_installers = []
            warnings.append(f"vm_installers_unavailable:{exc}")
        try:
            endpoint_reports = self._list_endpoint_reports()
        except Exception as exc:
            endpoint_reports = []
            warnings.append(f"endpoint_reports_unavailable:{exc}")
        try:
            policies = self._list_policies()
        except Exception as exc:
            policies = []
            warnings.append(f"policies_unavailable:{exc}")
        try:
            vms = self._list_vms()
        except Exception as exc:
            vms = []
            warnings.append(f"vm_inventory_unavailable:{exc}")
        status_counts = {
            "healthy": 0,
            "degraded": 0,
            "drifted": 0,
            "stale": 0,
            "pending": 0,
            "unmanaged": 0,
        }
        pending_action_count = 0
        for vm in vms:
            try:
                profile = self._build_profile(vm)
            except Exception as exc:
                profile = {}
                warnings.append(f"vm_profile_unavailable:{getattr(vm, 'vmid', 'unknown')}:{exc}")
            try:
                endpoint = self._summarize_endpoint_report(self._load_endpoint_report(vm.node, vm.vmid) or {})
            except Exception as exc:
                endpoint = {}
                warnings.append(f"endpoint_summary_unavailable:{getattr(vm, 'vmid', 'unknown')}:{exc}")
            role = str(profile.get("beagle_role", "")).strip().lower()
            report_age = endpoint.get("report_age_seconds")
            if role in {"endpoint", "thinclient", "client"}:
                if not endpoint.get("reported_at"):
                    status = "pending"
                elif report_age is not None and int(report_age) > self._stale_endpoint_seconds:
                    status = "stale"
                elif endpoint.get("moonlight_target_reachable") not in {"1", 1, True}:
                    status = "degraded"
                else:
                    status = "healthy"
            elif profile.get("installer_target_eligible"):
                status = "healthy" if vm.status == "running" else "degraded"
            else:
                status = "unmanaged"
            status_counts[status] = status_counts.get(status, 0) + 1
            try:
                pending_action_count += len(self._load_action_queue(vm.node, vm.vmid))
            except Exception as exc:
                warnings.append(f"action_queue_unavailable:{getattr(vm, 'vmid', 'unknown')}:{exc}")
                continue
        available_providers: list[str] = []
        try:
            available_providers = self._list_providers()
        except Exception as exc:
            warnings.append(f"providers_unavailable:{exc}")
        return {
            "service": self._service_name,
            "ok": True,
            "version": self._version,
            "provider": self._host_provider_kind,
            "available_providers": available_providers,
            "generated_at": self._utcnow(),
            "downloads_status_present": self._downloads_status_file.exists(),
            "downloads_status": downloads_status,
            "vm_installer_inventory_present": self._vm_installers_file.exists(),
            "vm_installer_count": len(vm_installers) if isinstance(vm_installers, list) else 0,
            "vm_count": len(vms),
            "endpoint_count": len(endpoint_reports),
            "policy_count": len(policies),
            "pending_action_count": pending_action_count,
            "endpoint_status_counts": status_counts,
            "data_dir": str(self._data_dir),
            "warnings": warnings,
        }
