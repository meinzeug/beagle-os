from __future__ import annotations

import re
from typing import Any, Callable


class VmProfileService:
    def __init__(
        self,
        *,
        allocate_public_stream_base_port: Callable[[str, int], int | None],
        current_public_stream_host: Callable[[], str],
        expand_software_packages: Callable[[list[str], list[str]], list[str]],
        find_vm: Callable[[int], Any | None],
        first_guest_ipv4: Callable[[int], str],
        get_vm_config: Callable[[str, int], dict[str, Any]],
        list_policies: Callable[[], list[dict[str, Any]]],
        listify: Callable[[Any], list[str]],
        load_vm_secret: Callable[[str, int], dict[str, Any] | None],
        manager_pinned_pubkey: str,
        normalize_endpoint_profile_contract: Callable[..., dict[str, Any]],
        parse_description_meta: Callable[[str], dict[str, str]],
        public_installer_iso_url: Callable[[], str],
        public_manager_url: str,
        resolve_public_stream_host: Callable[[str], str],
        resolve_ubuntu_beagle_desktop: Callable[[str], dict[str, Any]],
        safe_hostname: Callable[[str, int], str],
        stream_ports: Callable[[int], dict[str, int]],
        truthy: Callable[..., bool],
        ubuntu_beagle_default_desktop: str,
        ubuntu_beagle_default_guest_user: str,
        ubuntu_beagle_default_keymap: str,
        ubuntu_beagle_default_locale: str,
        ubuntu_beagle_software_presets: dict[str, dict[str, Any]],
    ) -> None:
        self._allocate_public_stream_base_port = allocate_public_stream_base_port
        self._current_public_stream_host = current_public_stream_host
        self._expand_software_packages = expand_software_packages
        self._find_vm = find_vm
        self._first_guest_ipv4 = first_guest_ipv4
        self._get_vm_config = get_vm_config
        self._list_policies = list_policies
        self._listify = listify
        self._load_vm_secret = load_vm_secret
        self._manager_pinned_pubkey = str(manager_pinned_pubkey or "")
        self._normalize_endpoint_profile_contract = normalize_endpoint_profile_contract
        self._parse_description_meta = parse_description_meta
        self._public_installer_iso_url = public_installer_iso_url
        self._public_manager_url = str(public_manager_url or "")
        self._resolve_public_stream_host = resolve_public_stream_host
        self._resolve_ubuntu_beagle_desktop = resolve_ubuntu_beagle_desktop
        self._safe_hostname = safe_hostname
        self._stream_ports = stream_ports
        self._truthy = truthy
        self._ubuntu_beagle_default_desktop = str(ubuntu_beagle_default_desktop or "")
        self._ubuntu_beagle_default_guest_user = str(ubuntu_beagle_default_guest_user or "")
        self._ubuntu_beagle_default_keymap = str(ubuntu_beagle_default_keymap or "")
        self._ubuntu_beagle_default_locale = str(ubuntu_beagle_default_locale or "")
        self._ubuntu_beagle_software_presets = dict(ubuntu_beagle_software_presets or {})

    def should_use_public_stream(self, meta: dict[str, str], guest_ip: str) -> bool:
        if not self._current_public_stream_host():
            return False
        if str(meta.get("beagle-public-stream", "1")).strip().lower() in {"0", "false", "no", "off"}:
            return False
        if meta.get("beagle-public-beagle-stream-client-port"):
            return True
        if meta.get("beagle-stream-server-user") or meta.get("beagle-stream-server-password") or meta.get("beagle-stream-server-api-url"):
            return True
        if meta.get("beagle-stream-client-host") or meta.get("beagle-stream-server-host") or meta.get("beagle-stream-server-ip"):
            return True
        if guest_ip and str(meta.get("beagle-role", "")).strip().lower() == "desktop":
            return True
        return False

    def build_public_stream_details(self, vm: Any, meta: dict[str, str], guest_ip: str) -> dict[str, Any] | None:
        if not self.should_use_public_stream(meta, guest_ip):
            return None
        explicit_port = str(meta.get("beagle-public-beagle-stream-client-port", "")).strip()
        if explicit_port.isdigit():
            base_port = int(explicit_port)
        else:
            allocated = self._allocate_public_stream_base_port(vm.node, vm.vmid)
            if allocated is None:
                return None
            base_port = int(allocated)
        meta_public_host = str(meta.get("beagle-public-stream-host", "")).strip()
        public_host = self._resolve_public_stream_host(meta_public_host or self._current_public_stream_host())
        ports = self._stream_ports(base_port)
        return {
            "enabled": True,
            "host": public_host,
            "guest_ip": guest_ip,
            "beagle_stream_client_port": ports["beagle_stream_client_port"],
            "beagle_stream_server_api_url": f"https://{public_host}:{ports['beagle_stream_server_api_port']}",
            "ports": ports,
        }

    def resolve_assigned_target(self, target_vmid: int, target_node: str, *, allow_assignment: bool) -> dict[str, Any] | None:
        del allow_assignment
        target_vm = self._find_vm(target_vmid)
        if target_vm is None:
            return None
        if target_node and target_node != target_vm.node:
            return None
        target_profile = self.build_profile(target_vm, allow_assignment=False)
        return {
            "vmid": target_vm.vmid,
            "node": target_vm.node,
            "name": target_vm.name,
            "stream_host": target_profile["stream_host"],
            "beagle_stream_client_local_host": str(target_profile.get("beagle_stream_client_local_host", "") or ""),
            "beagle_stream_client_port": target_profile.get("beagle_stream_client_port", ""),
            "beagle_stream_server_api_url": target_profile["beagle_stream_server_api_url"],
            "beagle_stream_client_app": target_profile["beagle_stream_client_app"],
        }

    def resolve_policy_for_vm(self, vm: Any, meta: dict[str, str]) -> dict[str, Any] | None:
        tags = {item.strip() for item in str(vm.tags or "").split(";") if item.strip()}
        role = meta.get("beagle-role", "desktop" if meta.get("beagle-stream-client-host") or meta.get("beagle-stream-server-ip") or meta.get("beagle-stream-server-host") else "")
        for policy in self._list_policies():
            if not policy.get("enabled", True):
                continue
            selector = policy.get("selector", {}) if isinstance(policy.get("selector"), dict) else {}
            selector_vmid = selector.get("vmid")
            if selector_vmid is not None and int(selector_vmid) != vm.vmid:
                continue
            if selector.get("node") and str(selector.get("node")).strip() != vm.node:
                continue
            if selector.get("role") and str(selector.get("role")).strip() != role:
                continue
            tags_any = {item for item in selector.get("tags_any", []) if item}
            if tags_any and not tags.intersection(tags_any):
                continue
            tags_all = {item for item in selector.get("tags_all", []) if item}
            if tags_all and not tags_all.issubset(tags):
                continue
            return policy
        return None

    def assess_vm_fingerprint(self, config: dict[str, Any], meta: dict[str, str], guest_ip: str) -> dict[str, Any]:
        vga = str(config.get("vga", "") or "").strip()
        machine = str(config.get("machine", "") or "").strip()
        cpu = str(config.get("cpu", "") or "").strip()
        tags = str(config.get("tags", "") or "")
        risk_flags: list[str] = []
        recommendations: list[str] = []
        if "virtio" in vga.lower():
            risk_flags.append("virtio-gpu")
            recommendations.append("Use GPU passthrough or a less generic virtual display path.")
        if "q35" in machine.lower():
            risk_flags.append("q35-machine")
        if not cpu or cpu.lower() in {"kvm64", "x86-64-v2-aes"}:
            risk_flags.append("generic-cpu")
            recommendations.append("Set CPU type to host for more realistic guest characteristics.")
        if guest_ip:
            risk_flags.append("guest-networked")
        if meta.get("beagle-public-stream-host") or meta.get("beagle-public-beagle-stream-client-port"):
            risk_flags.append("public-stream")
        risk_level = "low"
        if len(risk_flags) >= 4:
            risk_level = "high"
        elif len(risk_flags) >= 2:
            risk_level = "medium"
        return {
            "risk_level": risk_level,
            "flags": risk_flags,
            "recommendations": recommendations,
            "vga": vga,
            "machine": machine,
            "cpu": cpu,
            "tags": tags,
        }

    def build_profile(self, vm: Any, *, allow_assignment: bool = True) -> dict[str, Any]:
        config = self._get_vm_config(vm.node, vm.vmid)
        meta = self._parse_description_meta(config.get("description", ""))
        matched_policy = self.resolve_policy_for_vm(vm, meta) if allow_assignment else None
        policy_profile = matched_policy.get("profile", {}) if isinstance(matched_policy, dict) and isinstance(matched_policy.get("profile"), dict) else {}
        desktop_hint = str(
            policy_profile.get("desktop")
            or meta.get("beagle-desktop-id")
            or meta.get("beagle-desktop")
            or self._ubuntu_beagle_default_desktop
        ).strip()
        try:
            desktop = self._resolve_ubuntu_beagle_desktop(desktop_hint)
        except ValueError:
            desktop = self._resolve_ubuntu_beagle_desktop(self._ubuntu_beagle_default_desktop)
        supported_presets = set(self._ubuntu_beagle_software_presets.keys())
        package_presets = [item for item in self._listify(meta.get("beagle-package-presets", "")) if item in supported_presets]
        extra_packages = [
            item for item in self._listify(meta.get("beagle-extra-packages", ""))
            if re.fullmatch(r"[a-z0-9][a-z0-9+.-]*", str(item or "").strip().lower())
        ]
        software_packages = self._expand_software_packages(package_presets, extra_packages)
        guest_ip = self._first_guest_ipv4(vm.vmid) if vm.status == "running" else ""
        guest_ip = guest_ip or str(meta.get("beagle-stream-server-ip", "")).strip()
        beagle_stream_client_local_host = (
            policy_profile.get("beagle_stream_client_local_host")
            or meta.get("beagle-stream-client-local-host")
            or meta.get("beagle-stream-server-ip")
            or guest_ip
        )
        stream_host = policy_profile.get("stream_host") or meta.get("beagle-stream-client-host") or meta.get("beagle-stream-server-ip") or meta.get("beagle-stream-server-host") or beagle_stream_client_local_host
        beagle_stream_client_port = str(policy_profile.get("beagle_stream_client_port") or meta.get("beagle-stream-client-port") or meta.get("beagle-public-beagle-stream-client-port") or "").strip()
        beagle_stream_server_api_url = policy_profile.get("beagle_stream_server_api_url") or meta.get("beagle-stream-server-api-url") or (f"https://{stream_host}:47990" if stream_host else "")
        public_stream = self.build_public_stream_details(vm, meta, guest_ip)
        if public_stream is not None:
            stream_host = public_stream["host"]
            beagle_stream_client_local_host = str(public_stream.get("guest_ip", "") or beagle_stream_client_local_host).strip()
            beagle_stream_client_port = str(public_stream["beagle_stream_client_port"])
            beagle_stream_server_api_url = public_stream["beagle_stream_server_api_url"]
        installer_url = f"/beagle-api/api/v1/vms/{vm.vmid}/installer.sh"
        live_usb_url = f"/beagle-api/api/v1/vms/{vm.vmid}/live-usb.sh"
        installer_windows_url = f"/beagle-api/api/v1/vms/{vm.vmid}/installer.ps1"
        live_usb_windows_url = f"/beagle-api/api/v1/vms/{vm.vmid}/live-usb.ps1"
        installer_iso_url = self._public_installer_iso_url()
        vm_secret = self._load_vm_secret(vm.node, vm.vmid)
        has_beagle_stream_server_password = bool((vm_secret or {}).get("beagle_stream_server_password"))
        expected_profile_name = policy_profile.get("expected_profile_name") or meta.get("beagle-profile-name", "")
        beagle_stream_client_app = policy_profile.get("beagle_stream_client_app") or meta.get("beagle-stream-client-app", meta.get("beagle-stream-server-app", "Desktop"))
        update_enabled = self._truthy(policy_profile.get("update_enabled", meta.get("beagle-update-enabled", "1")), default=True)
        update_channel = str(policy_profile.get("update_channel") or meta.get("beagle-update-channel", "stable")).strip() or "stable"
        update_behavior = str(policy_profile.get("update_behavior") or meta.get("beagle-update-behavior", "prompt")).strip() or "prompt"
        update_feed_url = str(policy_profile.get("update_feed_url") or meta.get("beagle-update-feed-url", f"{self._public_manager_url}/api/v1/endpoints/update-feed")).strip()
        update_version_pin = str(policy_profile.get("update_version_pin") or meta.get("beagle-update-version-pin", "")).strip()
        egress_domains = self._listify(policy_profile.get("egress_domains") or meta.get("beagle-egress-domains", ""))
        egress_resolvers = self._listify(policy_profile.get("egress_resolvers") or meta.get("beagle-egress-resolvers", ""))
        egress_allowed_ips = self._listify(policy_profile.get("egress_allowed_ips") or meta.get("beagle-egress-allowed-ips", ""))
        profile = {
            "vmid": vm.vmid,
            "node": vm.node,
            "name": config.get("name") or vm.name,
            "status": vm.status,
            "tags": vm.tags,
            "guest_ip": guest_ip,
            "stream_host": stream_host,
            "beagle_stream_client_local_host": str(beagle_stream_client_local_host or "").strip(),
            "beagle_stream_client_port": beagle_stream_client_port,
            "beagle_stream_server_api_url": beagle_stream_server_api_url,
            "guest_user": meta.get("beagle-stream-server-guest-user", self._ubuntu_beagle_default_guest_user),
            "beagle_stream_server_username": "",
            "beagle_stream_server_password_configured": has_beagle_stream_server_password,
            "beagle_stream_client_app": beagle_stream_client_app,
            "update_enabled": update_enabled,
            "update_channel": update_channel,
            "update_behavior": update_behavior,
            "update_feed_url": update_feed_url,
            "update_version_pin": update_version_pin,
            "beagle_stream_client_resolution": policy_profile.get("beagle_stream_client_resolution") or meta.get("beagle-stream-client-resolution", "1280x720"),
            "beagle_stream_client_fps": policy_profile.get("beagle_stream_client_fps") or meta.get("beagle-stream-client-fps", "30"),
            "beagle_stream_client_bitrate": policy_profile.get("beagle_stream_client_bitrate") or meta.get("beagle-stream-client-bitrate", "6000"),
            "beagle_stream_client_video_codec": policy_profile.get("beagle_stream_client_video_codec") or meta.get("beagle-stream-client-video-codec", "H.264"),
            "beagle_stream_client_video_decoder": policy_profile.get("beagle_stream_client_video_decoder") or meta.get("beagle-stream-client-video-decoder", "auto"),
            "beagle_stream_client_audio_config": policy_profile.get("beagle_stream_client_audio_config") or meta.get("beagle-stream-client-audio-config", "stereo"),
            "egress_mode": policy_profile.get("egress_mode") or meta.get("beagle-egress-mode", "full"),
            "egress_type": policy_profile.get("egress_type") or meta.get("beagle-egress-type", "wireguard"),
            "egress_interface": policy_profile.get("egress_interface") or meta.get("beagle-egress-interface", "wg-beagle"),
            "egress_domains": egress_domains,
            "egress_resolvers": egress_resolvers,
            "egress_allowed_ips": egress_allowed_ips,
            "egress_wg_address": policy_profile.get("egress_wg_address") or meta.get("beagle-egress-wg-address", ""),
            "egress_wg_dns": policy_profile.get("egress_wg_dns") or meta.get("beagle-egress-wg-dns", ""),
            "egress_wg_public_key": policy_profile.get("egress_wg_public_key") or meta.get("beagle-egress-wg-public-key", ""),
            "egress_wg_endpoint": policy_profile.get("egress_wg_endpoint") or meta.get("beagle-egress-wg-endpoint", ""),
            "egress_wg_private_key": policy_profile.get("egress_wg_private_key") or meta.get("beagle-egress-wg-private-key", ""),
            "egress_wg_preshared_key": policy_profile.get("egress_wg_preshared_key") or meta.get("beagle-egress-wg-preshared-key", ""),
            "egress_wg_persistent_keepalive": policy_profile.get("egress_wg_persistent_keepalive") or meta.get("beagle-egress-wg-persistent-keepalive", "25"),
            "identity_hostname": policy_profile.get("identity_hostname") or meta.get("beagle-identity-hostname", self._safe_hostname(config.get("name") or vm.name, vm.vmid)),
            "identity_timezone": policy_profile.get("identity_timezone") or meta.get("beagle-identity-timezone", "UTC"),
            "identity_locale": policy_profile.get("identity_locale") or meta.get("beagle-identity-locale", self._ubuntu_beagle_default_locale),
            "identity_keymap": policy_profile.get("identity_keymap") or meta.get("beagle-identity-keymap", self._ubuntu_beagle_default_keymap),
            "identity_chrome_profile": policy_profile.get("identity_chrome_profile") or meta.get("beagle-identity-chrome-profile", expected_profile_name or f"vm-{vm.vmid}"),
            "desktop_id": str(desktop.get("id", "")),
            "desktop_label": str(desktop.get("label", "")),
            "desktop_session": str(meta.get("beagle-desktop-session", desktop.get("session", ""))),
            "desktop_packages": list(desktop.get("packages", []) or []),
            "package_presets": package_presets,
            "extra_packages": extra_packages,
            "software_packages": software_packages,
            "network_mode": policy_profile.get("network_mode") or meta.get("thinclient-network-mode", "dhcp"),
            "default_mode": "BEAGLE_STREAM_CLIENT" if stream_host else "",
            "beagle_hostname": self._safe_hostname(config.get("name") or vm.name, vm.vmid),
            "beagle_manager_pinned_pubkey": self._manager_pinned_pubkey,
            "beagle_role": policy_profile.get("beagle_role") or meta.get("beagle-role", "desktop" if stream_host else ""),
            "expected_profile_name": expected_profile_name,
            "installer_url": installer_url,
            "live_usb_url": live_usb_url,
            "installer_windows_url": installer_windows_url,
            "live_usb_windows_url": live_usb_windows_url,
            "installer_iso_url": installer_iso_url,
            "public_stream": public_stream,
            "metadata_keys": sorted(meta.keys()),
            "applied_policy": {
                "name": matched_policy.get("name", ""),
                "priority": matched_policy.get("priority", 0),
            } if matched_policy else None,
            "config_digest": {
                "memory": config.get("memory"),
                "cores": config.get("cores"),
                "sockets": config.get("sockets"),
                "machine": config.get("machine"),
                "ostype": config.get("ostype"),
                "agent": config.get("agent"),
                "vga": config.get("vga"),
            },
            "vm_fingerprint": self.assess_vm_fingerprint(config, meta, guest_ip),
        }
        if allow_assignment:
            target_vmid = None
            target_node = ""
            assignment_source = ""
            policy_target = policy_profile.get("assigned_target") if isinstance(policy_profile.get("assigned_target"), dict) else None
            if policy_target and policy_target.get("vmid") is not None:
                target_vmid = int(policy_target["vmid"])
                target_node = str(policy_target.get("node", "")).strip()
                assignment_source = "manager-policy"
            else:
                assigned_vmid = meta.get("beagle-target-vmid", "").strip()
                if assigned_vmid.isdigit():
                    target_vmid = int(assigned_vmid)
                    target_node = meta.get("beagle-target-node", "").strip()
                    assignment_source = "vm-metadata"
            if target_vmid is not None:
                assigned_target = self.resolve_assigned_target(target_vmid, target_node, allow_assignment=False)
                if assigned_target is not None:
                    profile["assigned_target"] = assigned_target
                    profile["assignment_source"] = assignment_source
                    profile["beagle_role"] = "endpoint"
                    if (assignment_source == "manager-policy" or not meta.get("beagle-stream-client-host")) and assigned_target["stream_host"]:
                        profile["stream_host"] = assigned_target["stream_host"]
                    if (assignment_source == "manager-policy" or not meta.get("beagle-stream-client-local-host")) and assigned_target.get("beagle_stream_client_local_host"):
                        profile["beagle_stream_client_local_host"] = assigned_target["beagle_stream_client_local_host"]
                    if (assignment_source == "manager-policy" or not meta.get("beagle-stream-client-port")) and assigned_target.get("beagle_stream_client_port"):
                        profile["beagle_stream_client_port"] = assigned_target["beagle_stream_client_port"]
                    if (assignment_source == "manager-policy" or not meta.get("beagle-stream-server-api-url")) and assigned_target["beagle_stream_server_api_url"]:
                        profile["beagle_stream_server_api_url"] = assigned_target["beagle_stream_server_api_url"]
                    if (assignment_source == "manager-policy" or not meta.get("beagle-stream-client-app")) and assigned_target["beagle_stream_client_app"]:
                        profile["beagle_stream_client_app"] = assigned_target["beagle_stream_client_app"]
                    if not expected_profile_name:
                        profile["expected_profile_name"] = f"vm-{target_vmid}"
                    profile["default_mode"] = "BEAGLE_STREAM_CLIENT" if profile["stream_host"] else ""
                    if assigned_target.get("beagle_stream_client_port"):
                        profile["public_stream"] = {
                            "enabled": True,
                            "host": profile["stream_host"],
                            "beagle_stream_client_port": profile["beagle_stream_client_port"],
                            "beagle_stream_server_api_url": profile["beagle_stream_server_api_url"],
                        }
        role_text = str(profile.get("beagle_role", "")).strip().lower()
        installer_target_eligible = bool(profile.get("stream_host")) and role_text not in {"endpoint", "thinclient", "client"}
        if installer_target_eligible:
            installer_target_message = "Diese VM kann als Beagle Stream Server-Ziel vorbereitet und als Beagle-Profil installiert werden."
        elif role_text in {"endpoint", "thinclient", "client"}:
            installer_target_message = "Diese VM ist als Beagle-Endpunkt klassifiziert und wird nicht als Streaming-Ziel angeboten."
        else:
            installer_target_message = "Diese VM hat aktuell kein verwertbares Beagle Stream Server-/Beagle Stream Client-Streaming-Ziel."
        profile["installer_target_eligible"] = installer_target_eligible
        profile["installer_target_message"] = installer_target_message
        return self._normalize_endpoint_profile_contract(profile, vmid=vm.vmid, installer_iso_url=installer_iso_url)
