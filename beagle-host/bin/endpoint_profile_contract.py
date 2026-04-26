from __future__ import annotations

from typing import Any, Mapping

ENDPOINT_PROFILE_CONTRACT_VERSION = "v1"


def normalize_endpoint_profile_contract(
    profile: Mapping[str, Any] | None,
    *,
    vmid: int,
    installer_iso_url: str = "",
) -> dict[str, Any]:
    payload = dict(profile or {})
    payload["contract_version"] = ENDPOINT_PROFILE_CONTRACT_VERSION
    payload["vmid"] = int(payload.get("vmid") or vmid)
    payload["installer_url"] = str(payload.get("installer_url") or f"/beagle-api/api/v1/vms/{int(vmid)}/installer.sh")
    payload["live_usb_url"] = str(payload.get("live_usb_url") or f"/beagle-api/api/v1/vms/{int(vmid)}/live-usb.sh")
    payload["installer_windows_url"] = str(payload.get("installer_windows_url") or f"/beagle-api/api/v1/vms/{int(vmid)}/installer.ps1")
    payload["live_usb_windows_url"] = str(payload.get("live_usb_windows_url") or f"/beagle-api/api/v1/vms/{int(vmid)}/live-usb.ps1")
    payload["installer_iso_url"] = str(payload.get("installer_iso_url") or installer_iso_url or "")
    payload["stream_host"] = str(payload.get("stream_host") or "")
    payload["moonlight_port"] = str(payload.get("moonlight_port") or "")
    payload["sunshine_api_url"] = str(payload.get("sunshine_api_url") or "")
    payload["expected_profile_name"] = str(payload.get("expected_profile_name") or "")
    payload["installer_target_eligible"] = bool(payload.get("installer_target_eligible"))
    payload["installer_target_message"] = str(payload.get("installer_target_message") or "")
    payload["assignment_source"] = str(payload.get("assignment_source") or "")
    payload["beagle_manager_pinned_pubkey"] = str(payload.get("beagle_manager_pinned_pubkey") or "")
    payload["beagle_role"] = str(payload.get("beagle_role") or "")
    payload["guest_user"] = str(payload.get("guest_user") or "")
    payload["desktop_id"] = str(payload.get("desktop_id") or "")
    payload["desktop_label"] = str(payload.get("desktop_label") or "")
    payload["desktop_session"] = str(payload.get("desktop_session") or "")
    payload["package_presets"] = list(payload.get("package_presets") or [])
    payload["extra_packages"] = list(payload.get("extra_packages") or [])
    payload["software_packages"] = list(payload.get("software_packages") or [])
    payload["assigned_target"] = payload.get("assigned_target") if isinstance(payload.get("assigned_target"), dict) else None
    payload["applied_policy"] = payload.get("applied_policy") if isinstance(payload.get("applied_policy"), dict) else None
    return payload


def installer_profile_surface(
    profile: Mapping[str, Any] | None,
    *,
    vmid: int,
    installer_iso_url: str = "",
) -> dict[str, Any]:
    payload = normalize_endpoint_profile_contract(profile, vmid=vmid, installer_iso_url=installer_iso_url)
    return {
        "contract_version": payload["contract_version"],
        "installer_url": payload["installer_url"],
        "live_usb_url": payload["live_usb_url"],
        "installer_windows_url": payload["installer_windows_url"],
        "live_usb_windows_url": payload["live_usb_windows_url"],
        "installer_iso_url": payload["installer_iso_url"],
        "stream_host": payload["stream_host"],
        "moonlight_port": payload["moonlight_port"],
        "sunshine_api_url": payload["sunshine_api_url"],
        "installer_target_eligible": payload["installer_target_eligible"],
        "installer_target_message": payload["installer_target_message"],
    }
