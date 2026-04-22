from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class FleetInventoryService:
    def __init__(
        self,
        *,
        build_profile: Callable[[Any], dict[str, Any]],
        latest_ubuntu_beagle_state_for_vmid: Callable[..., dict[str, Any] | None],
        list_support_bundle_metadata: Callable[..., list[dict[str, Any]]],
        list_vms: Callable[[], list[Any]],
        load_action_queue: Callable[[str, int], list[dict[str, Any]]],
        load_action_result: Callable[[str, int], dict[str, Any] | None],
        load_endpoint_report: Callable[[str, int], dict[str, Any] | None],
        load_json_file: Callable[[Path, Any], Any],
        public_installer_iso_url: Callable[[], str],
        service_name: str,
        summarize_action_result: Callable[[dict[str, Any] | None], dict[str, Any]],
        summarize_endpoint_report: Callable[[dict[str, Any]], dict[str, Any]],
        utcnow: Callable[[], str],
        version: str,
        vm_installers_file: Path,
    ) -> None:
        self._build_profile = build_profile
        self._latest_ubuntu_beagle_state_for_vmid = latest_ubuntu_beagle_state_for_vmid
        self._list_support_bundle_metadata = list_support_bundle_metadata
        self._list_vms = list_vms
        self._load_action_queue = load_action_queue
        self._load_action_result = load_action_result
        self._load_endpoint_report = load_endpoint_report
        self._load_json_file = load_json_file
        self._public_installer_iso_url = public_installer_iso_url
        self._service_name = str(service_name or "beagle-control-plane")
        self._summarize_action_result = summarize_action_result
        self._summarize_endpoint_report = summarize_endpoint_report
        self._utcnow = utcnow
        self._version = str(version or "")
        self._vm_installers_file = vm_installers_file

    @staticmethod
    def _effective_vm_status(base_status: str, provisioning: dict[str, Any] | None) -> str:
        status = str(base_status or "unknown").strip().lower() or "unknown"
        if not isinstance(provisioning, dict):
            return status
        prov_status = str(provisioning.get("status", "")).strip().lower()
        prov_phase = str(provisioning.get("phase", "")).strip().lower()
        if prov_status in {"creating", "installing"}:
            return "installing"
        if prov_phase in {"autoinstall", "firstboot"} and prov_status not in {"failed", "completed"}:
            return "installing"
        return status

    def build_inventory(self) -> dict[str, Any]:
        inventory: list[dict[str, Any]] = []
        warnings: list[str] = []
        try:
            installers = self._load_json_file(self._vm_installers_file, [])
        except Exception as exc:
            installers = []
            warnings.append(f"vm_installers_unavailable:{exc}")
        installers_by_vmid = {
            int(item.get("vmid")): item
            for item in installers
            if isinstance(item, dict) and item.get("vmid") is not None
        }
        try:
            vms = self._list_vms()
        except Exception as exc:
            vms = []
            warnings.append(f"vm_inventory_unavailable:{exc}")
        for vm in vms:
            try:
                profile = self._build_profile(vm)
            except Exception as exc:
                profile = {}
                warnings.append(f"vm_profile_unavailable:{getattr(vm, 'vmid', 'unknown')}:{exc}")
            installer = installers_by_vmid.get(getattr(vm, "vmid", 0), {})
            try:
                endpoint = self._summarize_endpoint_report(self._load_endpoint_report(vm.node, vm.vmid) or {})
            except Exception as exc:
                endpoint = {}
                warnings.append(f"endpoint_summary_unavailable:{getattr(vm, 'vmid', 'unknown')}:{exc}")
            try:
                last_action = self._summarize_action_result(self._load_action_result(vm.node, vm.vmid))
            except Exception as exc:
                last_action = {}
                warnings.append(f"action_result_unavailable:{getattr(vm, 'vmid', 'unknown')}:{exc}")
            try:
                pending_action_count = len(self._load_action_queue(vm.node, vm.vmid))
            except Exception as exc:
                pending_action_count = 0
                warnings.append(f"action_queue_unavailable:{getattr(vm, 'vmid', 'unknown')}:{exc}")
            try:
                provisioning = self._latest_ubuntu_beagle_state_for_vmid(vm.vmid)
            except Exception as exc:
                provisioning = None
                warnings.append(f"provisioning_state_unavailable:{getattr(vm, 'vmid', 'unknown')}:{exc}")
            effective_status = self._effective_vm_status(getattr(vm, "status", "unknown"), provisioning)
            vmid = int(getattr(vm, "vmid", 0) or 0)
            node = str(getattr(vm, "node", "") or "")
            name = str(getattr(vm, "name", "") or f"vm-{vmid}")
            support_bundle_count = 0
            try:
                support_bundle_count = len(self._list_support_bundle_metadata(node=node, vmid=vmid))
            except Exception as exc:
                warnings.append(f"support_bundle_unavailable:{vmid}:{exc}")
            inventory.append(
                {
                    "vmid": vmid,
                    "node": node,
                    "name": name,
                    "status": effective_status,
                    "stream_host": profile.get("stream_host", ""),
                    "moonlight_port": profile.get("moonlight_port", ""),
                    "sunshine_api_url": profile.get("sunshine_api_url", ""),
                    "moonlight_app": profile.get("moonlight_app", ""),
                    "network_mode": profile.get("network_mode", ""),
                    "egress_mode": profile.get("egress_mode", "direct"),
                    "beagle_role": profile.get("beagle_role", ""),
                    "guest_user": profile.get("guest_user", ""),
                    "identity_timezone": profile.get("identity_timezone", ""),
                    "identity_locale": profile.get("identity_locale", ""),
                    "identity_keymap": profile.get("identity_keymap", ""),
                    "desktop_id": profile.get("desktop_id", ""),
                    "desktop_label": profile.get("desktop_label", ""),
                    "desktop_session": profile.get("desktop_session", ""),
                    "package_presets": profile.get("package_presets", []),
                    "extra_packages": profile.get("extra_packages", []),
                    "software_packages": profile.get("software_packages", []),
                    "vm_fingerprint": profile.get("vm_fingerprint"),
                    "profile_contract_version": profile.get("contract_version", ""),
                    "expected_profile_name": profile.get("expected_profile_name", ""),
                    "default_mode": "MOONLIGHT" if profile.get("stream_host") else "",
                    "installer_url": profile.get("installer_url", ""),
                    "live_usb_url": profile.get("live_usb_url", f"/beagle-api/api/v1/vms/{vmid}/live-usb.sh"),
                    "installer_windows_url": profile.get(
                        "installer_windows_url", f"/beagle-api/api/v1/vms/{vmid}/installer.ps1"
                    ),
                    "installer_iso_url": profile.get("installer_iso_url", self._public_installer_iso_url()),
                    "installer_target_eligible": profile.get("installer_target_eligible", False),
                    "installer_target_message": profile.get("installer_target_message", ""),
                    "available_modes": installer.get("available_modes")
                    or (["MOONLIGHT"] if profile["stream_host"] else []),
                    "assigned_target": profile.get("assigned_target"),
                    "assignment_source": profile.get("assignment_source", ""),
                    "applied_policy": profile.get("applied_policy"),
                    "endpoint": endpoint,
                    "compliance": {},
                    "last_action": last_action,
                    "pending_action_count": pending_action_count,
                    "support_bundle_count": support_bundle_count,
                    "provisioning": provisioning,
                }
            )
        return {
            "service": self._service_name,
            "version": self._version,
            "generated_at": self._utcnow(),
            "vms": inventory,
            "warnings": warnings,
        }
