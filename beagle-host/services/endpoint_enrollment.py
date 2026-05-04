"""Endpoint enrollment and bootstrap response helpers.

This service owns enrollment-token issuance plus the endpoint enrollment
bootstrap/config response flow. Persistence stays delegated to the extracted
token-store services, while the control plane keeps thin wrappers and HTTP
status mapping.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable


class EndpointEnrollmentService:
    def __init__(
        self,
        *,
        build_profile: Callable[[Any], dict[str, Any]],
        ensure_vm_secret: Callable[[Any], dict[str, Any]],
        enrollment_token_ttl_seconds: int,
        find_vm: Callable[[int], Any | None],
        load_enrollment_token: Callable[[str], dict[str, Any] | None],
        manager_pinned_pubkey: str,
        mark_enrollment_token_used: Callable[[str, dict[str, Any], str], None],
        public_manager_url: str,
        public_server_name: str,
        resolve_vm_beagle_stream_server_pinned_pubkey: Callable[[Any], str],
        save_vm_secret: Callable[[str, int, dict[str, Any]], dict[str, Any]],
        service_name: str,
        store_endpoint_token: Callable[[str, dict[str, Any]], dict[str, Any]],
        store_enrollment_token: Callable[[str, dict[str, Any]], dict[str, Any]],
        token_is_valid: Callable[[dict[str, Any] | None, str], bool],
        token_urlsafe: Callable[[int], str],
        usb_tunnel_attach_host: str,
        usb_tunnel_known_host_line: Callable[[], str],
        usb_tunnel_user: str,
        utcnow: Callable[[], str],
        version: str,
        wireguard_bootstrap_defaults: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self._build_profile = build_profile
        self._ensure_vm_secret = ensure_vm_secret
        self._enrollment_token_ttl_seconds = int(enrollment_token_ttl_seconds)
        self._find_vm = find_vm
        self._load_enrollment_token = load_enrollment_token
        self._manager_pinned_pubkey = str(manager_pinned_pubkey or "")
        self._mark_enrollment_token_used = mark_enrollment_token_used
        self._public_manager_url = str(public_manager_url or "")
        self._public_server_name = str(public_server_name or "")
        self._resolve_vm_beagle_stream_server_pinned_pubkey = resolve_vm_beagle_stream_server_pinned_pubkey
        self._save_vm_secret = save_vm_secret
        self._service_name = str(service_name or "")
        self._store_endpoint_token = store_endpoint_token
        self._store_enrollment_token = store_enrollment_token
        self._token_is_valid = token_is_valid
        self._token_urlsafe = token_urlsafe
        self._usb_tunnel_attach_host = str(usb_tunnel_attach_host or "")
        self._usb_tunnel_known_host_line = usb_tunnel_known_host_line
        self._usb_tunnel_user = str(usb_tunnel_user or "")
        self._utcnow = utcnow
        self._version = str(version or "")
        self._wireguard_bootstrap_defaults = wireguard_bootstrap_defaults

    def issue_enrollment_token(self, vm: Any) -> tuple[str, dict[str, Any]]:
        record = self._ensure_vm_secret(vm)
        token = self._token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(0, self._enrollment_token_ttl_seconds))
        payload = {
            "vmid": vm.vmid,
            "node": vm.node,
            "profile_name": f"vm-{vm.vmid}",
            "expires_at": expires_at.isoformat(),
            "issued_at": self._utcnow(),
            "used_at": "",
        }
        self._store_enrollment_token(token, payload)
        response_payload = dict(payload)
        response_payload["thinclient_password"] = str(record.get("thinclient_password", ""))
        return token, response_payload

    def enroll_endpoint(self, payload: dict[str, Any]) -> dict[str, Any]:
        clean_payload = payload if isinstance(payload, dict) else {}
        enrollment_token = str(clean_payload.get("enrollment_token", "")).strip()
        endpoint_id = str(clean_payload.get("endpoint_id", "")).strip() or str(clean_payload.get("hostname", "")).strip()
        if not enrollment_token or not endpoint_id:
            raise ValueError("missing enrollment_token or endpoint_id")

        enrollment = self._load_enrollment_token(enrollment_token)
        if not self._token_is_valid(enrollment, endpoint_id):
            raise PermissionError("invalid or expired enrollment token")

        vm = self._find_vm(int((enrollment or {}).get("vmid", 0)))
        if vm is None or vm.node != str((enrollment or {}).get("node", "")).strip():
            raise LookupError("vm not found")

        secret = self._ensure_vm_secret(vm)
        beagle_stream_server_pinned_pubkey = str(self._resolve_vm_beagle_stream_server_pinned_pubkey(vm) or "").strip()
        if beagle_stream_server_pinned_pubkey and beagle_stream_server_pinned_pubkey != str(secret.get("beagle_stream_server_pinned_pubkey", "")):
            updated_secret = dict(secret)
            updated_secret["beagle_stream_server_pinned_pubkey"] = beagle_stream_server_pinned_pubkey
            secret = self._save_vm_secret(vm.node, vm.vmid, updated_secret)

        profile = dict(self._build_profile(vm) or {})
        profile.setdefault("stream_allocation_id", f"vm-{int(vm.vmid)}")
        endpoint_token = self._token_urlsafe(32)
        endpoint_payload = self._store_endpoint_token(
            endpoint_token,
            {
                "endpoint_id": endpoint_id,
                "hostname": str(clean_payload.get("hostname", "")).strip(),
                "vmid": vm.vmid,
                "node": vm.node,
            },
        )
        self._mark_enrollment_token_used(enrollment_token, enrollment or {}, endpoint_id)
        return {
            "ok": True,
            "service": self._service_name,
            "version": self._version,
            "generated_at": self._utcnow(),
            "endpoint": endpoint_payload,
            "config": self._build_endpoint_config(profile, secret, endpoint_token, endpoint_id=endpoint_id),
        }

    def _build_endpoint_config(
        self,
        profile: dict[str, Any],
        secret: dict[str, Any],
        endpoint_token: str,
        *,
        endpoint_id: str,
    ) -> dict[str, Any]:
        wg_defaults = (
            self._wireguard_bootstrap_defaults()
            if callable(self._wireguard_bootstrap_defaults)
            else {}
        )
        if not isinstance(wg_defaults, dict):
            wg_defaults = {}
        profile_egress_mode = str(profile.get("egress_mode", "full") or "full")
        profile_egress_type = str(profile.get("egress_type", "") or "")
        if wg_defaults and (not profile_egress_type or profile_egress_mode == "direct"):
            profile_egress_mode = str(wg_defaults.get("egress_mode", "") or profile_egress_mode)
            profile_egress_type = str(wg_defaults.get("egress_type", "") or profile_egress_type)
        profile_egress_interface = str(profile.get("egress_interface", "") or "")
        if not profile_egress_interface and wg_defaults:
            profile_egress_interface = str(wg_defaults.get("egress_interface", "") or "")
        return {
            "device_id": str(endpoint_id or ""),
            "beagle_manager_url": self._public_manager_url,
            "beagle_manager_token": endpoint_token,
            "beagle_manager_pinned_pubkey": self._manager_pinned_pubkey,
            "beagle_stream_mode": "broker",
            "beagle_stream_allocation_id": str(profile.get("stream_allocation_id", "") or ""),
            "update_enabled": bool(profile.get("update_enabled", True)),
            "update_channel": str(profile.get("update_channel", "stable") or "stable"),
            "update_behavior": str(profile.get("update_behavior", "prompt") or "prompt"),
            "update_feed_url": str(profile.get("update_feed_url", f"{self._public_manager_url}/api/v1/endpoints/update-feed") or ""),
            "update_version_pin": str(profile.get("update_version_pin", "") or ""),
            "beagle_stream_server_api_url": str(profile.get("beagle_stream_server_api_url", "") or ""),
            "beagle_stream_server_username": str(secret.get("beagle_stream_server_username", "")),
            "beagle_stream_server_password": str(secret.get("beagle_stream_server_password", "")),
            "beagle_stream_server_pinned_pubkey": str(secret.get("beagle_stream_server_pinned_pubkey", "")),
            "usb_enabled": True,
            "usb_tunnel_host": self._public_server_name,
            "usb_tunnel_user": self._usb_tunnel_user,
            "usb_tunnel_port": int(secret.get("usb_tunnel_port", 0) or 0),
            "usb_tunnel_attach_host": self._usb_tunnel_attach_host,
            "usb_tunnel_private_key": str(secret.get("usb_tunnel_private_key", "")),
            "usb_tunnel_known_host": self._usb_tunnel_known_host_line(),
            "beagle_stream_client_host": str(profile.get("stream_host", "") or ""),
            "beagle_stream_client_local_host": str(profile.get("beagle_stream_client_local_host", "") or ""),
            "beagle_stream_client_port": str(profile.get("beagle_stream_client_port", "") or ""),
            "beagle_stream_client_app": str(profile.get("beagle_stream_client_app", "Desktop") or "Desktop"),
            "egress_mode": profile_egress_mode,
            "egress_type": profile_egress_type,
            "egress_interface": profile_egress_interface or "wg-beagle",
            "egress_domains": list(profile.get("egress_domains", []) or []),
            "egress_resolvers": list(profile.get("egress_resolvers", []) or []),
            "egress_allowed_ips": list(profile.get("egress_allowed_ips", []) or []),
            "egress_wg_address": str(profile.get("egress_wg_address", "") or ""),
            "egress_wg_dns": str(profile.get("egress_wg_dns", "") or ""),
            "egress_wg_public_key": str(profile.get("egress_wg_public_key", "") or ""),
            "egress_wg_endpoint": str(profile.get("egress_wg_endpoint", "") or ""),
            "egress_wg_private_key": str(profile.get("egress_wg_private_key", "") or ""),
            "egress_wg_preshared_key": str(profile.get("egress_wg_preshared_key", "") or ""),
            "egress_wg_persistent_keepalive": str(profile.get("egress_wg_persistent_keepalive", "25") or "25"),
            "identity_hostname": str(profile.get("identity_hostname", "") or ""),
            "identity_timezone": str(profile.get("identity_timezone", "") or ""),
            "identity_locale": str(profile.get("identity_locale", "") or ""),
            "identity_keymap": str(profile.get("identity_keymap", "") or ""),
            "identity_chrome_profile": str(profile.get("identity_chrome_profile", "") or ""),
        }
