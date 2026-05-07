from __future__ import annotations

import base64
import shlex
from pathlib import Path
from typing import Any, Callable

from thin_client_preset import build_common_preset, build_runtime_extension_fields


class InstallerScriptService:
    def __init__(
        self,
        *,
        build_profile: Callable[[Any], dict[str, Any]],
        ensure_vm_secret: Callable[[Any], dict[str, Any]],
        fetch_beagle_stream_server_identity: Callable[[Any, str], dict[str, Any]],
        get_vm_config: Callable[[str, int], dict[str, Any]],
        hosted_installer_iso_file: Path,
        hosted_installer_template_file: Path,
        hosted_live_usb_template_file: Path,
        issue_enrollment_token: Callable[[Any], tuple[str, dict[str, Any]]],
        issue_installer_log_context: Callable[..., dict[str, str]],
        manager_pinned_pubkey: str,
        parse_description_meta: Callable[[str], dict[str, str]],
        patch_installer_defaults: Callable[..., str],
        patch_windows_installer_defaults: Callable[..., str],
        public_bootstrap_latest_download_url: Callable[[], str],
        public_installer_iso_url: Callable[[], str],
        public_manager_url: str,
        public_payload_latest_download_url: Callable[[], str],
        public_server_name: str,
        raw_shell_installer_template_file: Path,
        raw_windows_installer_template_file: Path,
        safe_hostname: Callable[[str, int], str],
        beagle_stream_server_guest_user: Callable[[Any, dict[str, Any]], str],
    ) -> None:
        self._build_profile = build_profile
        self._ensure_vm_secret = ensure_vm_secret
        self._fetch_beagle_stream_server_identity = fetch_beagle_stream_server_identity
        self._get_vm_config = get_vm_config
        self._hosted_installer_iso_file = hosted_installer_iso_file
        self._hosted_installer_template_file = hosted_installer_template_file
        self._hosted_live_usb_template_file = hosted_live_usb_template_file
        self._issue_enrollment_token = issue_enrollment_token
        self._issue_installer_log_context = issue_installer_log_context
        self._manager_pinned_pubkey = str(manager_pinned_pubkey or "")
        self._parse_description_meta = parse_description_meta
        self._patch_installer_defaults = patch_installer_defaults
        self._patch_windows_installer_defaults = patch_windows_installer_defaults
        self._public_bootstrap_latest_download_url = public_bootstrap_latest_download_url
        self._public_installer_iso_url = public_installer_iso_url
        self._public_manager_url = str(public_manager_url or "")
        self._public_payload_latest_download_url = public_payload_latest_download_url
        self._public_server_name = str(public_server_name or "")
        self._raw_shell_installer_template_file = Path(raw_shell_installer_template_file)
        self._raw_windows_installer_template_file = raw_windows_installer_template_file
        self._safe_hostname = safe_hostname
        self._beagle_stream_server_guest_user = beagle_stream_server_guest_user

    def _read_shell_template(self, preferred_template_file: Path) -> str:
        for candidate in (Path(preferred_template_file), self._raw_shell_installer_template_file):
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")
        raise FileNotFoundError(f"missing installer template: {preferred_template_file}")

    @staticmethod
    def _encode_installer_preset(preset: dict[str, Any]) -> str:
        lines = ["# Auto-generated Beagle OS VM preset"]
        for key in sorted(preset):
            lines.append(f"{key}={shlex.quote(str(preset.get(key, '')))}")
        payload = "\n".join(lines) + "\n"
        return base64.b64encode(payload.encode("utf-8")).decode("ascii")

    @staticmethod
    def _first_non_empty(*values: Any) -> str:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""

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
        # Legacy meta-keys kept for thin-client backwards compat; rename local vars to beagle_*
        beagle_scheme = meta.get("beagle-scheme", "https")
        beagle_host = meta.get("beagle-host", self._public_server_name)
        beagle_port = meta.get("beagle-port", "8006")
        beagle_realm = meta.get("beagle-realm", "pam")
        beagle_verify_tls = meta.get("beagle-verify-tls", "1")
        expected_profile_name = str(profile.get("expected_profile_name") or f"vm-{vm.vmid}")
        stream_allocation_id = str(profile.get("stream_allocation_id", f"vm-{vm.vmid}") or f"vm-{vm.vmid}")
        beagle_stream_client_host = str(profile.get("stream_host", "") or "")
        beagle_stream_client_local_host = str(profile.get("beagle_stream_client_local_host", "") or "")
        beagle_stream_client_port = str(profile.get("beagle_stream_client_port", "") or "")
        beagle_stream_server_api_url = str(profile.get("beagle_stream_server_api_url", "") or "")
        vm_secret = self._ensure_vm_secret(vm)
        beagle_stream_server_username = self._first_non_empty(
            meta.get("beagle-stream-server-user"),
            vm_secret.get("beagle_stream_server_username", ""),
        )
        beagle_stream_server_password = self._first_non_empty(
            meta.get("beagle-stream-server-password"),
            vm_secret.get("beagle_stream_server_password", ""),
        )
        beagle_stream_server_pinned_pubkey = str(vm_secret.get("beagle_stream_server_pinned_pubkey", "") or "")
        guest_user = self._beagle_stream_server_guest_user(vm, config)
        beagle_stream_server = (
            self._fetch_beagle_stream_server_identity(vm, guest_user)
            if vm.status == "running" and guest_user
            else {}
        )
        beagle_stream_server_cert_pem = str(beagle_stream_server.get("server_cert_pem", "") or "")
        beagle_stream_server_cert_b64 = (
            base64.b64encode(beagle_stream_server_cert_pem.encode("utf-8")).decode("ascii")
            if beagle_stream_server_cert_pem
            else ""
        )

        if beagle_stream_client_host and not all((beagle_stream_server_username, beagle_stream_server_password)):
            raise ValueError(
                f"vm {vm.vmid} is missing Beagle Stream Server API credentials for Beagle Stream Client preset generation"
            )

        return build_common_preset(
            profile_name=expected_profile_name,
            vm_name=vm_name,
            hostname_value=self._safe_hostname(vm_name, vm.vmid),
            autostart=meta.get("thinclient-autostart", "1"),
            default_mode="BEAGLE_STREAM_CLIENT",
            network_mode=meta.get("thinclient-network-mode", "dhcp"),
            network_interface=meta.get("thinclient-network-interface", "eth0"),
            beagle_scheme=beagle_scheme,
            beagle_host=beagle_host,
            beagle_port=beagle_port,
            beagle_node=vm.node,
            beagle_vmid=str(vm.vmid),
            beagle_realm=beagle_realm,
            beagle_verify_tls=beagle_verify_tls,
            beagle_manager_url=self._public_manager_url,
            beagle_stream_client_host="",
            beagle_stream_client_local_host=beagle_stream_client_local_host,
            beagle_stream_client_app=str(profile.get("beagle_stream_client_app", "Desktop") or "Desktop"),
            beagle_stream_client_bin=meta.get("beagle-stream-client-bin", "beagle-stream"),
            beagle_stream_client_resolution=str(profile.get("beagle_stream_client_resolution", "1920x1080") or "1920x1080"),
            beagle_stream_client_fps=str(profile.get("beagle_stream_client_fps", "60") or "60"),
            beagle_stream_client_bitrate=str(profile.get("beagle_stream_client_bitrate", "32000") or "32000"),
            beagle_stream_client_video_codec=str(profile.get("beagle_stream_client_video_codec", "H.264") or "H.264"),
            beagle_stream_client_video_decoder=str(profile.get("beagle_stream_client_video_decoder", "software") or "software"),
            beagle_stream_client_audio_config=str(profile.get("beagle_stream_client_audio_config", "stereo") or "stereo"),
            beagle_stream_client_absolute_mouse=meta.get("beagle-stream-client-absolute-mouse", "1"),
            beagle_stream_client_quit_after=meta.get("beagle-stream-client-quit-after", "0"),
            beagle_stream_server_api_url=beagle_stream_server_api_url,
            beagle_stream_server_username=beagle_stream_server_username,
            beagle_stream_server_password=beagle_stream_server_password,
            extra_fields=build_runtime_extension_fields(
                network_static_address=meta.get("thinclient-network-static-address", ""),
                network_static_prefix=meta.get("thinclient-network-static-prefix", "24"),
                network_gateway=meta.get("thinclient-network-gateway", ""),
                network_dns_servers=meta.get("thinclient-network-dns-servers", "1.1.1.1 8.8.8.8"),
                beagle_manager_pinned_pubkey=self._manager_pinned_pubkey,
                beagle_enrollment_url=f"{self._public_manager_url}/api/v1/endpoints/enroll",
                beagle_enrollment_token=enrollment_token,
                beagle_stream_mode="broker",
                beagle_stream_allocation_id=stream_allocation_id,
                thinclient_password=thinclient_password,
                beagle_update_enabled="1" if bool(profile.get("update_enabled", True)) else "0",
                beagle_update_channel=str(profile.get("update_channel", "stable") or "stable"),
                beagle_update_behavior=str(profile.get("update_behavior", "prompt") or "prompt"),
                beagle_update_feed_url=str(
                    profile.get("update_feed_url", f"{self._public_manager_url}/api/v1/endpoints/update-feed") or ""
                ),
                beagle_update_version_pin=str(profile.get("update_version_pin", "") or ""),
                beagle_egress_mode=str(profile.get("egress_mode", "full") or "full"),
                beagle_egress_type=str(profile.get("egress_type", "wireguard") or "wireguard"),
                beagle_egress_interface=str(profile.get("egress_interface", "wg-beagle") or "wg-beagle"),
                beagle_egress_domains=" ".join(profile.get("egress_domains", []) or []),
                beagle_egress_resolvers=" ".join(profile.get("egress_resolvers", []) or []),
                beagle_egress_allowed_ips=" ".join(profile.get("egress_allowed_ips", []) or []),
                beagle_egress_wg_address=str(profile.get("egress_wg_address", "") or ""),
                beagle_egress_wg_dns=str(profile.get("egress_wg_dns", "") or ""),
                beagle_egress_wg_public_key=str(profile.get("egress_wg_public_key", "") or ""),
                beagle_egress_wg_endpoint=str(profile.get("egress_wg_endpoint", "") or ""),
                beagle_egress_wg_private_key=str(profile.get("egress_wg_private_key", "") or ""),
                beagle_egress_wg_preshared_key=str(profile.get("egress_wg_preshared_key", "") or ""),
                beagle_egress_wg_persistent_keepalive=str(
                    profile.get("egress_wg_persistent_keepalive", "25") or "25"
                ),
                identity_hostname=str(profile.get("identity_hostname", "") or ""),
                identity_timezone=str(profile.get("identity_timezone", "") or ""),
                identity_locale=str(profile.get("identity_locale", "") or ""),
                identity_keymap=str(profile.get("identity_keymap", "") or ""),
                identity_chrome_profile=str(profile.get("identity_chrome_profile", "") or ""),
                beagle_stream_client_port=beagle_stream_client_port,
                beagle_stream_server_pinned_pubkey=beagle_stream_server_pinned_pubkey,
                beagle_stream_server_name=str(beagle_stream_server.get("beagle_stream_server_name", "") or ""),
                beagle_stream_server_stream_port=str(beagle_stream_server.get("stream_port", "") or beagle_stream_client_port or ""),
                beagle_stream_server_uniqueid=str(beagle_stream_server.get("uniqueid", "") or ""),
                beagle_stream_server_cert_b64=beagle_stream_server_cert_b64,
                beagle_stream_client_host=beagle_stream_client_host,
                beagle_stream_server_api_url=beagle_stream_server_api_url,
            ),
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

    def _installer_log_context(self, vm: Any, *, script_kind: str, script_name: str) -> dict[str, str]:
        context = self._issue_installer_log_context(
            vmid=int(vm.vmid),
            node=str(vm.node),
            script_kind=script_kind,
            script_name=script_name,
        )
        return {
            "url": f"{self._public_manager_url.rstrip('/')}/api/v1/public/installer-logs",
            "token": str(context.get("token") or ""),
            "session_id": str(context.get("session_id") or ""),
        }

    def render_installer_script(self, vm: Any) -> tuple[bytes, str]:
        _, preset_name, preset_b64 = self._build_preset_for_vm(vm)
        filename = f"pve-thin-client-usb-installer-vm-{vm.vmid}.sh"
        log_context = self._installer_log_context(vm, script_kind="linux-installer-usb", script_name=filename)
        rendered = self._patch_installer_defaults(
            self._read_shell_template(self._hosted_installer_template_file),
            preset_name,
            preset_b64,
            self._public_installer_iso_url(),
            self._public_bootstrap_latest_download_url(),
            self._public_payload_latest_download_url(),
            "installer",
            log_context["url"],
            log_context["token"],
            log_context["session_id"],
        )
        return rendered.encode("utf-8"), filename

    def render_live_usb_script(self, vm: Any) -> tuple[bytes, str]:
        _, preset_name, preset_b64 = self._build_preset_for_vm(vm)
        filename = f"pve-thin-client-live-usb-vm-{vm.vmid}.sh"
        log_context = self._installer_log_context(vm, script_kind="linux-live-usb", script_name=filename)
        rendered = self._patch_installer_defaults(
            self._read_shell_template(self._hosted_live_usb_template_file),
            preset_name,
            preset_b64,
            self._public_installer_iso_url(),
            self._public_bootstrap_latest_download_url(),
            self._public_payload_latest_download_url(),
            "live",
            log_context["url"],
            log_context["token"],
            log_context["session_id"],
        )
        return rendered.encode("utf-8"), filename

    def render_windows_installer_script(self, vm: Any) -> tuple[bytes, str]:
        if not self._raw_windows_installer_template_file.is_file():
            raise FileNotFoundError(
                f"missing windows installer template: {self._raw_windows_installer_template_file}"
            )
        _, preset_name, preset_b64 = self._build_preset_for_vm(vm)
        filename = f"pve-thin-client-usb-installer-vm-{vm.vmid}.ps1"
        log_context = self._installer_log_context(vm, script_kind="windows-installer-usb", script_name=filename)
        rendered = self._patch_windows_installer_defaults(
            self._raw_windows_installer_template_file.read_text(encoding="utf-8"),
            preset_name,
            preset_b64,
            self._public_installer_iso_url(),
            "installer",
            log_context["url"],
            log_context["token"],
            log_context["session_id"],
        )
        return rendered.encode("utf-8"), filename

    def render_windows_live_usb_script(self, vm: Any) -> tuple[bytes, str]:
        if not self._raw_windows_installer_template_file.is_file():
            raise FileNotFoundError(
                f"missing windows installer template: {self._raw_windows_installer_template_file}"
            )
        _, preset_name, preset_b64 = self._build_preset_for_vm(vm)
        filename = f"pve-thin-client-live-usb-vm-{vm.vmid}.ps1"
        log_context = self._installer_log_context(vm, script_kind="windows-live-usb", script_name=filename)
        rendered = self._patch_windows_installer_defaults(
            self._raw_windows_installer_template_file.read_text(encoding="utf-8"),
            preset_name,
            preset_b64,
            self._public_installer_iso_url(),
            "live",
            log_context["url"],
            log_context["token"],
            log_context["session_id"],
        )
        return rendered.encode("utf-8"), filename
