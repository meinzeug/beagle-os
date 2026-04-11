from __future__ import annotations

import base64
import shlex
from pathlib import Path
from typing import Any, Callable

from thin_client_preset import build_common_preset


class InstallerScriptService:
    def __init__(
        self,
        *,
        build_profile: Callable[[Any], dict[str, Any]],
        ensure_vm_secret: Callable[[Any], dict[str, Any]],
        fetch_sunshine_server_identity: Callable[[Any, str], dict[str, Any]],
        get_vm_config: Callable[[str, int], dict[str, Any]],
        hosted_installer_iso_file: Path,
        hosted_installer_template_file: Path,
        hosted_live_usb_template_file: Path,
        issue_enrollment_token: Callable[[Any], tuple[str, dict[str, Any]]],
        manager_pinned_pubkey: str,
        parse_description_meta: Callable[[str], dict[str, str]],
        patch_installer_defaults: Callable[..., str],
        patch_windows_installer_defaults: Callable[..., str],
        public_bootstrap_latest_download_url: Callable[[], str],
        public_installer_iso_url: Callable[[], str],
        public_manager_url: str,
        public_payload_latest_download_url: Callable[[], str],
        public_server_name: str,
        raw_windows_installer_template_file: Path,
        safe_hostname: Callable[[str, int], str],
        sunshine_guest_user: Callable[[Any, dict[str, Any]], str],
    ) -> None:
        self._build_profile = build_profile
        self._ensure_vm_secret = ensure_vm_secret
        self._fetch_sunshine_server_identity = fetch_sunshine_server_identity
        self._get_vm_config = get_vm_config
        self._hosted_installer_iso_file = hosted_installer_iso_file
        self._hosted_installer_template_file = hosted_installer_template_file
        self._hosted_live_usb_template_file = hosted_live_usb_template_file
        self._issue_enrollment_token = issue_enrollment_token
        self._manager_pinned_pubkey = str(manager_pinned_pubkey or "")
        self._parse_description_meta = parse_description_meta
        self._patch_installer_defaults = patch_installer_defaults
        self._patch_windows_installer_defaults = patch_windows_installer_defaults
        self._public_bootstrap_latest_download_url = public_bootstrap_latest_download_url
        self._public_installer_iso_url = public_installer_iso_url
        self._public_manager_url = str(public_manager_url or "")
        self._public_payload_latest_download_url = public_payload_latest_download_url
        self._public_server_name = str(public_server_name or "")
        self._raw_windows_installer_template_file = raw_windows_installer_template_file
        self._safe_hostname = safe_hostname
        self._sunshine_guest_user = sunshine_guest_user

    @staticmethod
    def _encode_installer_preset(preset: dict[str, Any]) -> str:
        lines = ["# Auto-generated Beagle OS VM preset"]
        for key in sorted(preset):
            lines.append(f"{key}={shlex.quote(str(preset.get(key, '')))}")
        payload = "\n".join(lines) + "\n"
        return base64.b64encode(payload.encode("utf-8")).decode("ascii")

    def build_preset(
        self,
        vm: Any,
        profile: dict[str, Any],
        config: dict[str, Any],
        *,
        enrollment_token: str,
        thinclient_password: str,
    ) -> dict[str, str]:
        meta = self._parse_description_meta(config.get("description", ""))
        vm_name = str(config.get("name") or vm.name or f"vm-{vm.vmid}")
        proxmox_scheme = meta.get("proxmox-scheme", "https")
        proxmox_host = meta.get("proxmox-host", self._public_server_name)
        proxmox_port = meta.get("proxmox-port", "8006")
        proxmox_realm = meta.get("proxmox-realm", "pam")
        proxmox_verify_tls = meta.get("proxmox-verify-tls", "1")
        expected_profile_name = str(profile.get("expected_profile_name") or f"vm-{vm.vmid}")
        moonlight_host = str(profile.get("stream_host", "") or "")
        moonlight_local_host = str(profile.get("moonlight_local_host", "") or "")
        moonlight_port = str(profile.get("moonlight_port", "") or "")
        sunshine_api_url = str(profile.get("sunshine_api_url", "") or "")
        vm_secret = self._ensure_vm_secret(vm)
        sunshine_username = str(vm_secret.get("sunshine_username", "") or "")
        sunshine_password = str(vm_secret.get("sunshine_password", "") or "")
        sunshine_pin = str(vm_secret.get("sunshine_pin", "") or "")
        sunshine_pinned_pubkey = str(vm_secret.get("sunshine_pinned_pubkey", "") or "")
        guest_user = self._sunshine_guest_user(vm, config)
        sunshine_server = (
            self._fetch_sunshine_server_identity(vm, guest_user)
            if vm.status == "running" and guest_user
            else {}
        )
        sunshine_server_cert_pem = str(sunshine_server.get("server_cert_pem", "") or "")
        sunshine_server_cert_b64 = (
            base64.b64encode(sunshine_server_cert_pem.encode("utf-8")).decode("ascii")
            if sunshine_server_cert_pem
            else ""
        )

        return build_common_preset(
            profile_name=expected_profile_name,
            vm_name=vm_name,
            hostname_value=self._safe_hostname(vm_name, vm.vmid),
            autostart=meta.get("thinclient-autostart", "1"),
            default_mode="MOONLIGHT" if moonlight_host else "",
            network_mode=meta.get("thinclient-network-mode", "dhcp"),
            network_interface=meta.get("thinclient-network-interface", "eth0"),
            proxmox_scheme=proxmox_scheme,
            proxmox_host=proxmox_host,
            proxmox_port=proxmox_port,
            proxmox_node=vm.node,
            proxmox_vmid=str(vm.vmid),
            proxmox_realm=proxmox_realm,
            proxmox_verify_tls=proxmox_verify_tls,
            beagle_manager_url=self._public_manager_url,
            moonlight_host=moonlight_host,
            moonlight_local_host=moonlight_local_host,
            moonlight_app=str(profile.get("moonlight_app", "Desktop") or "Desktop"),
            moonlight_bin=meta.get("moonlight-bin", "moonlight"),
            moonlight_resolution=str(profile.get("moonlight_resolution", "auto") or "auto"),
            moonlight_fps=str(profile.get("moonlight_fps", "60") or "60"),
            moonlight_bitrate=str(profile.get("moonlight_bitrate", "20000") or "20000"),
            moonlight_video_codec=str(profile.get("moonlight_video_codec", "H.264") or "H.264"),
            moonlight_video_decoder=str(profile.get("moonlight_video_decoder", "auto") or "auto"),
            moonlight_audio_config=str(profile.get("moonlight_audio_config", "stereo") or "stereo"),
            moonlight_absolute_mouse=meta.get("moonlight-absolute-mouse", "1"),
            moonlight_quit_after=meta.get("moonlight-quit-after", "0"),
            sunshine_api_url=sunshine_api_url,
            sunshine_username=sunshine_username,
            sunshine_password=sunshine_password,
            sunshine_pin=sunshine_pin,
            extra_fields={
                "PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_ADDRESS": meta.get("thinclient-network-static-address", ""),
                "PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_PREFIX": meta.get("thinclient-network-static-prefix", "24"),
                "PVE_THIN_CLIENT_PRESET_NETWORK_GATEWAY": meta.get("thinclient-network-gateway", ""),
                "PVE_THIN_CLIENT_PRESET_NETWORK_DNS_SERVERS": meta.get("thinclient-network-dns-servers", "1.1.1.1 8.8.8.8"),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_PINNED_PUBKEY": self._manager_pinned_pubkey,
                "PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_URL": f"{self._public_manager_url}/api/v1/endpoints/enroll",
                "PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_TOKEN": enrollment_token,
                "PVE_THIN_CLIENT_PRESET_THINCLIENT_PASSWORD": thinclient_password,
                "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_ENABLED": "1" if bool(profile.get("update_enabled", True)) else "0",
                "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_CHANNEL": str(profile.get("update_channel", "stable") or "stable"),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_BEHAVIOR": str(profile.get("update_behavior", "prompt") or "prompt"),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_FEED_URL": str(
                    profile.get("update_feed_url", f"{self._public_manager_url}/api/v1/endpoints/update-feed") or ""
                ),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_VERSION_PIN": str(profile.get("update_version_pin", "") or ""),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_MODE": str(profile.get("egress_mode", "direct") or "direct"),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_TYPE": str(profile.get("egress_type", "") or ""),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_INTERFACE": str(
                    profile.get("egress_interface", "beagle-egress") or "beagle-egress"
                ),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_DOMAINS": " ".join(profile.get("egress_domains", []) or []),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_RESOLVERS": " ".join(profile.get("egress_resolvers", []) or []),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_ALLOWED_IPS": " ".join(profile.get("egress_allowed_ips", []) or []),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ADDRESS": str(profile.get("egress_wg_address", "") or ""),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_DNS": str(profile.get("egress_wg_dns", "") or ""),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PUBLIC_KEY": str(profile.get("egress_wg_public_key", "") or ""),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ENDPOINT": str(profile.get("egress_wg_endpoint", "") or ""),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRIVATE_KEY": str(
                    profile.get("egress_wg_private_key", "") or ""
                ),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRESHARED_KEY": str(
                    profile.get("egress_wg_preshared_key", "") or ""
                ),
                "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE": str(
                    profile.get("egress_wg_persistent_keepalive", "25") or "25"
                ),
                "PVE_THIN_CLIENT_PRESET_IDENTITY_HOSTNAME": str(profile.get("identity_hostname", "") or ""),
                "PVE_THIN_CLIENT_PRESET_IDENTITY_TIMEZONE": str(profile.get("identity_timezone", "") or ""),
                "PVE_THIN_CLIENT_PRESET_IDENTITY_LOCALE": str(profile.get("identity_locale", "") or ""),
                "PVE_THIN_CLIENT_PRESET_IDENTITY_KEYMAP": str(profile.get("identity_keymap", "") or ""),
                "PVE_THIN_CLIENT_PRESET_IDENTITY_CHROME_PROFILE": str(
                    profile.get("identity_chrome_profile", "") or ""
                ),
                "PVE_THIN_CLIENT_PRESET_MOONLIGHT_PORT": moonlight_port,
                "PVE_THIN_CLIENT_PRESET_SUNSHINE_PINNED_PUBKEY": sunshine_pinned_pubkey,
                "PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_NAME": str(sunshine_server.get("sunshine_name", "") or ""),
                "PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_STREAM_PORT": str(
                    sunshine_server.get("stream_port", "") or moonlight_port or ""
                ),
                "PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_UNIQUEID": str(sunshine_server.get("uniqueid", "") or ""),
                "PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_CERT_B64": sunshine_server_cert_b64,
            },
        )

    def _build_preset_for_vm(self, vm: Any) -> tuple[dict[str, str], str, str]:
        config = self._get_vm_config(vm.node, vm.vmid)
        profile = self._build_profile(vm)
        enrollment_token, enrollment_record = self._issue_enrollment_token(vm)
        preset = self.build_preset(
            vm,
            profile,
            config,
            enrollment_token=enrollment_token,
            thinclient_password=str(enrollment_record.get("thinclient_password", "")),
        )
        preset_name = preset.get("PVE_THIN_CLIENT_PRESET_PROFILE_NAME") or f"vm-{vm.vmid}"
        preset_b64 = self._encode_installer_preset(preset)
        return preset, preset_name, preset_b64

    def render_installer_script(self, vm: Any) -> tuple[bytes, str]:
        if not self._hosted_installer_template_file.is_file():
            raise FileNotFoundError(f"missing installer template: {self._hosted_installer_template_file}")
        if not self._hosted_installer_iso_file.is_file():
            raise FileNotFoundError(f"missing installer ISO: {self._hosted_installer_iso_file}")
        _, preset_name, preset_b64 = self._build_preset_for_vm(vm)
        rendered = self._patch_installer_defaults(
            self._hosted_installer_template_file.read_text(encoding="utf-8"),
            preset_name,
            preset_b64,
            self._public_installer_iso_url(),
            self._public_bootstrap_latest_download_url(),
            self._public_payload_latest_download_url(),
            "installer",
        )
        filename = f"pve-thin-client-usb-installer-vm-{vm.vmid}.sh"
        return rendered.encode("utf-8"), filename

    def render_live_usb_script(self, vm: Any) -> tuple[bytes, str]:
        if not self._hosted_live_usb_template_file.is_file():
            raise FileNotFoundError(f"missing live USB template: {self._hosted_live_usb_template_file}")
        if not self._hosted_installer_iso_file.is_file():
            raise FileNotFoundError(f"missing installer ISO: {self._hosted_installer_iso_file}")
        _, preset_name, preset_b64 = self._build_preset_for_vm(vm)
        rendered = self._patch_installer_defaults(
            self._hosted_live_usb_template_file.read_text(encoding="utf-8"),
            preset_name,
            preset_b64,
            self._public_installer_iso_url(),
            self._public_bootstrap_latest_download_url(),
            self._public_payload_latest_download_url(),
            "live",
        )
        filename = f"pve-thin-client-live-usb-vm-{vm.vmid}.sh"
        return rendered.encode("utf-8"), filename

    def render_windows_installer_script(self, vm: Any) -> tuple[bytes, str]:
        if not self._raw_windows_installer_template_file.is_file():
            raise FileNotFoundError(
                f"missing windows installer template: {self._raw_windows_installer_template_file}"
            )
        if not self._hosted_installer_iso_file.is_file():
            raise FileNotFoundError(f"missing installer ISO: {self._hosted_installer_iso_file}")
        _, preset_name, preset_b64 = self._build_preset_for_vm(vm)
        rendered = self._patch_windows_installer_defaults(
            self._raw_windows_installer_template_file.read_text(encoding="utf-8"),
            preset_name,
            preset_b64,
            self._public_installer_iso_url(),
        )
        filename = f"pve-thin-client-usb-installer-vm-{vm.vmid}.ps1"
        return rendered.encode("utf-8"), filename
