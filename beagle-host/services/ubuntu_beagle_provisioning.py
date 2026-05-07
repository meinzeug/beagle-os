"""Ubuntu-Beagle provisioning and lifecycle orchestration helpers.

This service owns provisioning catalog assembly, installer ISO/seed creation,
VM lifecycle orchestration for ubuntu-beagle desktops, and the update/finalize
flows around those VMs. The control plane keeps thin wrappers so HTTP handler
signatures and payload shapes stay stable while the large provisioning block
leaves the entrypoint.
"""

from __future__ import annotations

import base64
import os
import secrets
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


class UbuntuBeagleProvisioningService:
    def __init__(
        self,
        *,
        allocate_public_stream_base_port: Callable[[str, int], int | None],
        build_profile: Callable[[Any], dict[str, Any]],
        configure_beagle_stream_server_guest_script: Path,
        current_public_stream_host: Callable[[], str],
        default_usb_tunnel_port: Callable[[int], int],
        ensure_vm_secret: Callable[[Any], dict[str, Any]],
        expand_software_packages: Callable[[list[str], list[str]], list[str]],
        find_vm: Callable[..., Any | None],
        get_storage_quota: Callable[[str], dict[str, Any]],
        get_vm_config: Callable[[str, int], dict[str, Any]],
        invalidate_vm_cache: Callable[[int | None, str], None],
        latest_ubuntu_beagle_state_for_vmid: Callable[..., dict[str, Any] | None],
        list_bridge_inventory: Callable[[str], list[str]],
        list_nodes_inventory: Callable[[], list[dict[str, Any]]],
        list_ubuntu_beagle_states: Callable[..., list[dict[str, Any]]],
        local_iso_dir: Path,
        make_vm_summary: Callable[..., Any],
        manager_pinned_pubkey: str,
        normalize_keymap: Callable[[str], str],
        normalize_locale: Callable[[str], str],
        normalize_package_names: Callable[..., list[str]],
        normalize_package_presets: Callable[[Any], list[str]],
        provider: Any,
        public_manager_url: str,
        public_ubuntu_beagle_complete_url: Callable[[str], str],
        random_pin: Callable[[], str],
        random_secret: Callable[[int], str],
        reconcile_public_streams_script: Path,
        resolve_ubuntu_beagle_desktop: Callable[[str], dict[str, Any]],
        run_checked: Callable[..., str],
        safe_hostname: Callable[[str, int], str],
        safe_slug: Callable[..., str],
        save_ubuntu_beagle_state: Callable[[str, dict[str, Any]], dict[str, Any]],
        save_vm_secret: Callable[[str, int, dict[str, Any]], dict[str, Any]],
        ensure_ubuntu_beagle_vm_restart_state: Callable[[dict[str, Any], int], dict[str, Any]],
        stream_ports: Callable[[int], dict[str, int]],
        summarize_ubuntu_beagle_state: Callable[..., dict[str, Any]],
        template_dir: Path,
        time_now_epoch: Callable[[], float],
        ubuntu_beagle_autoinstall_url_ttl_seconds: int,
        ubuntu_beagle_cyberpunk_wallpaper_source: Path,
        ubuntu_beagle_default_bridge: str,
        ubuntu_beagle_default_cores: int,
        ubuntu_beagle_default_desktop: str,
        ubuntu_beagle_default_disk_gb: int,
        ubuntu_beagle_default_guest_user: str,
        ubuntu_beagle_default_keymap: str,
        ubuntu_beagle_default_locale: str,
        ubuntu_beagle_default_package_presets: list[str],
        ubuntu_beagle_default_memory_mib: int,
        ubuntu_beagle_desktops: dict[str, dict[str, Any]],
        ubuntu_beagle_disk_storage: str,
        ubuntu_beagle_iso_storage: str,
        ubuntu_beagle_iso_url: str,
        ubuntu_beagle_profile_id: str,
        ubuntu_beagle_profile_label: str,
        ubuntu_beagle_profile_legacy_ids: dict[str, str],
        ubuntu_beagle_profile_release: str,
        ubuntu_beagle_profile_streaming: str,
        ubuntu_beagle_software_presets: dict[str, dict[str, Any]],
        ubuntu_beagle_stream_server_url: str,
        ubuntu_beagle_beagle_stream_server_url: str,
        ubuntu_beagle_tokens_dir: Callable[[], Path],
        utcnow: Callable[[], str],
        validate_linux_username: Callable[[str, str], str],
        validate_password: Callable[..., str],
    ) -> None:
        self._allocate_public_stream_base_port = allocate_public_stream_base_port
        self._build_profile = build_profile
        self._configure_beagle_stream_server_guest_script = Path(configure_beagle_stream_server_guest_script)
        self._current_public_stream_host = current_public_stream_host
        self._default_usb_tunnel_port = default_usb_tunnel_port
        self._ensure_vm_secret = ensure_vm_secret
        self._expand_software_packages = expand_software_packages
        self._find_vm = find_vm
        self._get_storage_quota = get_storage_quota
        self._get_vm_config = get_vm_config
        self._invalidate_vm_cache = invalidate_vm_cache
        self._latest_ubuntu_beagle_state_for_vmid = latest_ubuntu_beagle_state_for_vmid
        self._list_bridge_inventory = list_bridge_inventory
        self._list_nodes_inventory = list_nodes_inventory
        self._list_ubuntu_beagle_states = list_ubuntu_beagle_states
        self._local_iso_dir = Path(local_iso_dir)
        self._make_vm_summary = make_vm_summary
        self._manager_pinned_pubkey = str(manager_pinned_pubkey or "")
        self._normalize_keymap = normalize_keymap
        self._normalize_locale = normalize_locale
        self._normalize_package_names = normalize_package_names
        self._normalize_package_presets = normalize_package_presets
        self._provider = provider
        self._public_manager_url = str(public_manager_url or "")
        self._public_ubuntu_beagle_complete_url = public_ubuntu_beagle_complete_url
        self._random_pin = random_pin
        self._random_secret = random_secret
        self._reconcile_public_streams_script = Path(reconcile_public_streams_script)
        self._resolve_ubuntu_beagle_desktop = resolve_ubuntu_beagle_desktop
        self._run_checked = run_checked
        self._safe_hostname = safe_hostname
        self._safe_slug = safe_slug
        self._save_ubuntu_beagle_state = save_ubuntu_beagle_state
        self._save_vm_secret = save_vm_secret
        self._ensure_ubuntu_beagle_vm_restart_state = ensure_ubuntu_beagle_vm_restart_state
        self._stream_ports = stream_ports
        self._summarize_ubuntu_beagle_state = summarize_ubuntu_beagle_state
        self._template_dir = Path(template_dir)
        self._time_now_epoch = time_now_epoch
        self._ubuntu_beagle_autoinstall_url_ttl_seconds = int(ubuntu_beagle_autoinstall_url_ttl_seconds)
        self._ubuntu_beagle_cyberpunk_wallpaper_source = Path(ubuntu_beagle_cyberpunk_wallpaper_source)
        self._ubuntu_beagle_default_bridge = str(ubuntu_beagle_default_bridge or "")
        self._ubuntu_beagle_default_cores = int(ubuntu_beagle_default_cores)
        self._ubuntu_beagle_default_desktop = str(ubuntu_beagle_default_desktop or "")
        self._ubuntu_beagle_default_disk_gb = int(ubuntu_beagle_default_disk_gb)
        self._ubuntu_beagle_default_guest_user = str(ubuntu_beagle_default_guest_user or "")
        self._ubuntu_beagle_default_keymap = str(ubuntu_beagle_default_keymap or "")
        self._ubuntu_beagle_default_locale = str(ubuntu_beagle_default_locale or "")
        self._ubuntu_beagle_default_memory_mib = int(ubuntu_beagle_default_memory_mib)
        self._ubuntu_beagle_desktops = dict(ubuntu_beagle_desktops or {})
        self._ubuntu_beagle_disk_storage = str(ubuntu_beagle_disk_storage or "")
        self._ubuntu_beagle_iso_storage = str(ubuntu_beagle_iso_storage or "")
        self._ubuntu_beagle_iso_url = str(ubuntu_beagle_iso_url or "")
        self._ubuntu_beagle_profile_id = str(ubuntu_beagle_profile_id or "")
        self._ubuntu_beagle_profile_label = str(ubuntu_beagle_profile_label or "")
        self._ubuntu_beagle_profile_legacy_ids = dict(ubuntu_beagle_profile_legacy_ids or {})
        self._ubuntu_beagle_profile_release = str(ubuntu_beagle_profile_release or "")
        self._ubuntu_beagle_profile_streaming = str(ubuntu_beagle_profile_streaming or "")
        self._ubuntu_beagle_software_presets = dict(ubuntu_beagle_software_presets or {})
        supported_presets = set(self._ubuntu_beagle_software_presets.keys())
        self._ubuntu_beagle_default_package_presets = [
            item
            for item in [str(value or "").strip().lower() for value in (ubuntu_beagle_default_package_presets or [])]
            if item and item in supported_presets
        ]
        self._ubuntu_beagle_stream_server_url = str(ubuntu_beagle_stream_server_url or "")
        self._ubuntu_beagle_beagle_stream_server_url = str(ubuntu_beagle_beagle_stream_server_url or "")
        self._ubuntu_beagle_tokens_dir = ubuntu_beagle_tokens_dir
        self._utcnow = utcnow
        self._validate_linux_username = validate_linux_username
        self._validate_password = validate_password

    def provisioning_desktop_profiles(self) -> list[dict[str, Any]]:
        profiles: list[dict[str, Any]] = []
        for desktop in self._ubuntu_beagle_desktops.values():
            if not bool(desktop.get("visible_in_ui")):
                continue
            profiles.append(
                {
                    "id": str(desktop.get("id", "")).strip(),
                    "label": str(desktop.get("label", "")).strip(),
                    "session": str(desktop.get("session", "")).strip(),
                    "packages": list(desktop.get("packages", []) or []),
                    "features": list(desktop.get("features", []) or []),
                    "theme_variant": str(desktop.get("theme_variant", "")).strip(),
                }
            )
        return profiles

    def provisioning_software_presets(self) -> list[dict[str, Any]]:
        presets: list[dict[str, Any]] = []
        for preset in self._ubuntu_beagle_software_presets.values():
            presets.append(
                {
                    "id": str(preset.get("id", "")).strip(),
                    "label": str(preset.get("label", "")).strip(),
                    "packages": list(preset.get("packages", []) or []),
                    "description": str(preset.get("description", "")).strip(),
                }
            )
        return presets

    def provisioning_os_profiles(self) -> list[dict[str, Any]]:
        return [
            {
                "id": self._ubuntu_beagle_profile_id,
                "label": self._ubuntu_beagle_profile_label,
                "family": "ubuntu",
                "release": self._ubuntu_beagle_profile_release,
                "desktop": self._resolve_ubuntu_beagle_desktop(self._ubuntu_beagle_default_desktop)["label"],
                "streaming": self._ubuntu_beagle_profile_streaming,
                "template_set": "ubuntu-beagle",
                "iso_url": self._ubuntu_beagle_iso_url,
                "features": [
                    "Ubuntu Autoinstall",
                    "Selectable desktop",
                    "LightDM Autologin",
                    "Beagle Stream Server Streaming",
                    "QEMU Guest Agent",
                    "Chrome preinstalled",
                ],
            }
        ]

    @staticmethod
    def _node_value_to_mib(value: Any) -> int:
        """Convert provider node memory value to MiB.

        Beagle-style providers report bytes, while some local providers may
        already report MiB-like values.
        """
        raw = int(value or 0)
        if raw <= 0:
            return 0
        # Treat large values as bytes (>= 64 MiB in bytes).
        if raw >= 64 * 1024 * 1024:
            return int(raw / (1024 * 1024))
        return raw

    def _node_memory_budget_mib(self, node: str) -> int | None:
        target = str(node or "").strip()
        if not target:
            return None
        for item in self._list_nodes_inventory():
            if str(item.get("name", "")).strip() != target:
                continue
            maxmem_mib = self._node_value_to_mib(item.get("maxmem", 0))
            used_mib = self._node_value_to_mib(item.get("mem", 0))
            if maxmem_mib <= 0:
                return None
            free_mib = max(maxmem_mib - used_mib, 0)
            # Keep 1 GiB host reserve so VM startup does not OOM the node.
            return max(free_mib - 1024, 0)
        return None

    def _recommended_default_memory_mib(self, node: str) -> int:
        configured = max(int(self._ubuntu_beagle_default_memory_mib), 2048)
        budget = self._node_memory_budget_mib(node)
        if budget is None or budget <= 0:
            return configured
        # Keep UX simple: never suggest below the enforced minimum.
        return max(2048, min(configured, budget))

    def build_provisioning_catalog(self) -> dict[str, Any]:
        nodes = self._list_nodes_inventory()
        storages = self._provider.list_storage_inventory()
        default_node = next((item["name"] for item in nodes if item.get("status") == "online"), "")
        if not default_node and nodes:
            default_node = str(nodes[0].get("name", "")).strip()
        default_memory_mib = self._recommended_default_memory_mib(default_node)
        default_memory_budget_mib = self._node_memory_budget_mib(default_node)
        images_storages = [
            {
                "id": str(item.get("storage", "")).strip(),
                "content": [part.strip() for part in str(item.get("content", "")).split(",") if part.strip()],
                "path": str(item.get("path", "")).strip(),
                "type": str(item.get("type", "")).strip(),
            }
            for item in storages
            if self.storage_supports_content(str(item.get("storage", "")).strip(), "images")
        ]
        iso_storages = [
            {
                "id": str(item.get("storage", "")).strip(),
                "content": [part.strip() for part in str(item.get("content", "")).split(",") if part.strip()],
                "path": str(item.get("path", "")).strip(),
                "type": str(item.get("type", "")).strip(),
            }
            for item in storages
            if self.storage_supports_content(str(item.get("storage", "")).strip(), "iso")
        ]
        bridges_by_node = {
            item["name"]: self._list_bridge_inventory(item["name"]) for item in nodes if str(item.get("name", "")).strip()
        }
        bridges = sorted({bridge for values in bridges_by_node.values() for bridge in values if bridge})
        configured_bridge = str(self._ubuntu_beagle_default_bridge or "").strip()
        if configured_bridge and configured_bridge in bridges:
            default_bridge = configured_bridge
        else:
            default_bridge = bridges[0] if bridges else configured_bridge
        next_vmid_value = int(self._provider.next_vmid())
        return {
            "defaults": {
                "node": default_node,
                "bridge": default_bridge,
                "memory": default_memory_mib,
                "memory_recommended_max": default_memory_budget_mib,
                "cores": self._ubuntu_beagle_default_cores,
                "disk_gb": self._ubuntu_beagle_default_disk_gb,
                "guest_user": self._ubuntu_beagle_default_guest_user,
                "identity_locale": self._ubuntu_beagle_default_locale,
                "identity_keymap": self._ubuntu_beagle_default_keymap,
                "desktop": self._resolve_ubuntu_beagle_desktop(self._ubuntu_beagle_default_desktop)["id"],
                "package_presets": list(self._ubuntu_beagle_default_package_presets),
                "disk_storage": self.resolve_storage(
                    self._ubuntu_beagle_disk_storage,
                    "images",
                    self._ubuntu_beagle_iso_storage,
                ),
                "iso_storage": self.resolve_storage(
                    self._ubuntu_beagle_iso_storage,
                    "iso",
                    self._ubuntu_beagle_disk_storage,
                ),
                "next_vmid": next_vmid_value,
            },
            "nodes": nodes,
            "bridges": bridges,
            "bridges_by_node": bridges_by_node,
            "storages": {
                "images": images_storages,
                "iso": iso_storages,
            },
            "os_profiles": self.provisioning_os_profiles(),
            "desktop_profiles": self.provisioning_desktop_profiles(),
            "software_presets": self.provisioning_software_presets(),
            "recent_requests": self._list_ubuntu_beagle_states(),
        }

    def create_provisioned_vm(self, payload: dict[str, Any]) -> dict[str, Any]:
        os_profile = str(payload.get("os_profile", "") or payload.get("os", "") or self._ubuntu_beagle_profile_id).strip()
        os_profile = os_profile or self._ubuntu_beagle_profile_id
        desktop = str(payload.get("desktop", "") or payload.get("desktop_id", "") or "").strip()
        if os_profile in self._ubuntu_beagle_profile_legacy_ids and not desktop:
            desktop = self._ubuntu_beagle_profile_legacy_ids[os_profile]
        if os_profile not in {self._ubuntu_beagle_profile_id, *self._ubuntu_beagle_profile_legacy_ids.keys()}:
            raise ValueError(f"unsupported os_profile: {os_profile}")
        normalized = dict(payload)
        normalized["os_profile"] = self._ubuntu_beagle_profile_id
        normalized["desktop"] = self._resolve_ubuntu_beagle_desktop(desktop or self._ubuntu_beagle_default_desktop)["id"]
        normalized["identity_locale"] = self._normalize_locale(payload.get("identity_locale", ""))
        normalized["identity_keymap"] = self._normalize_keymap(payload.get("identity_keymap", ""))
        normalized["package_presets"] = self._normalize_package_presets(
            payload.get("package_presets", self._ubuntu_beagle_default_package_presets)
        )
        normalized["extra_packages"] = self._normalize_package_names(payload.get("extra_packages", []), field_name="extra_packages")
        return self.create_ubuntu_beagle_vm(normalized)

    @staticmethod
    def _normalize_ha_policy(value: Any) -> str:
        policy = str(value or "").strip().lower().replace("-", "_")
        if not policy:
            return ""
        if policy not in {"disabled", "restart", "fail_over"}:
            raise ValueError("ha_policy must be one of: disabled, restart, fail_over")
        return policy

    def storage_supports_content(self, storage_id: str, content_type: str) -> bool:
        target = str(storage_id or "").strip()
        if not target:
            return False
        for entry in self._provider.list_storage_inventory():
            if str(entry.get("storage", "")).strip() != target:
                continue
            content = str(entry.get("content", "")).strip()
            supported = {item.strip() for item in content.split(",") if item.strip()}
            return content_type in supported
        return False

    def resolve_storage(self, preferred: str, content_type: str, fallback: str) -> str:
        for candidate in (preferred, fallback):
            if self.storage_supports_content(candidate, content_type):
                return str(candidate).strip()
        for entry in self._provider.list_storage_inventory():
            content = str(entry.get("content", "")).strip()
            supported = {item.strip() for item in content.split(",") if item.strip()}
            if content_type in supported:
                candidate = str(entry.get("storage", "")).strip()
                if candidate:
                    return candidate
        raise RuntimeError(f"no Beagle storage with content type '{content_type}' is available")

    def _storage_inventory_entry(self, storage_id: str) -> dict[str, Any] | None:
        target = str(storage_id or "").strip()
        if not target:
            return None
        for entry in self._provider.list_storage_inventory():
            if str(entry.get("storage", "")).strip() == target:
                return entry
        return None

    def enforce_storage_quota(self, storage_id: str, requested_bytes: int) -> None:
        pool = str(storage_id or "").strip()
        if not pool:
            return
        requested = max(int(requested_bytes or 0), 0)
        quota_payload = self._get_storage_quota(pool)
        quota_bytes = max(int((quota_payload or {}).get("quota_bytes", 0) or 0), 0)
        if quota_bytes <= 0:
            return
        storage_entry = self._storage_inventory_entry(pool)
        if not isinstance(storage_entry, dict):
            raise ValueError(f"quota_exceeded: storage pool '{pool}' not found for quota check")
        used_bytes = max(int(storage_entry.get("used", 0) or 0), 0)
        if used_bytes + requested > quota_bytes:
            raise ValueError(
                "quota_exceeded: "
                f"pool '{pool}' limit={quota_bytes} used={used_bytes} requested={requested}"
            )

    def local_iso_storage_dir(self) -> Path:
        self._local_iso_dir.mkdir(parents=True, exist_ok=True)
        return self._local_iso_dir

    def ensure_iso_in_storage_pool(self, storage_id: str, iso_path: Path) -> Path:
        """Ensure an ISO exists in the selected storage path when a provider exposes one.

        Some providers (for example libvirt-backed test providers) resolve
        ``<storage>:iso/<filename>`` against their own pool path, not against
        ``local_iso_storage_dir``. To keep provisioning reproducible, copy the
        generated ISO into the selected pool path when needed.
        """
        source = Path(iso_path)
        if not source.is_file():
            raise FileNotFoundError(f"missing iso file: {source}")
        target_storage = str(storage_id or "").strip()
        if not target_storage:
            return source
        for entry in self._provider.list_storage_inventory():
            if str(entry.get("storage", "")).strip() != target_storage:
                continue
            pool_path = str(entry.get("path", "")).strip()
            if not pool_path:
                return source
            pool_dir = Path(pool_path)
            try:
                pool_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                return source
            target = pool_dir / source.name
            if target.resolve() == source.resolve():
                return source
            needs_copy = True
            if target.exists():
                try:
                    needs_copy = target.stat().st_size != source.stat().st_size
                except OSError:
                    needs_copy = True
            if needs_copy:
                try:
                    shutil.copy2(source, target)
                    target.chmod(0o644)
                except OSError:
                    return source
            return target
        return source

    def ubuntu_beagle_iso_filename(self, iso_url: str) -> str:
        candidate = Path(urlparse(iso_url).path).name or "ubuntu-live-server-amd64.iso"
        return self._safe_slug(candidate, "ubuntu-live-server-amd64.iso")

    def ubuntu_beagle_extract_dir(self, iso_filename: str) -> Path:
        # Keep extracted boot assets in the provider ISO storage path so libvirt
        # security profiles can access them without host-wide security downgrades.
        base_dir = self.local_iso_storage_dir() / "beagle-extracted"
        base_dir.mkdir(parents=True, exist_ok=True)
        base_dir.chmod(0o755)
        path = base_dir / self._safe_slug(iso_filename, "ubuntu")
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o755)
        return path

    def ensure_ubuntu_beagle_iso_cached(self, iso_url: str) -> dict[str, str]:
        iso_filename = self.ubuntu_beagle_iso_filename(iso_url)
        iso_path = self.local_iso_storage_dir() / iso_filename
        partial_path = iso_path.with_suffix(iso_path.suffix + ".part")
        if not iso_path.exists() or iso_path.stat().st_size == 0:
            self._run_checked(
                [
                    "curl",
                    "-fL",
                    "--retry",
                    "5",
                    "--continue-at",
                    "-",
                    "-o",
                    str(partial_path),
                    iso_url,
                ],
                timeout=None,
            )
            partial_path.replace(iso_path)

        extract_dir = self.ubuntu_beagle_extract_dir(iso_filename)
        kernel_path = extract_dir / "vmlinuz"
        initrd_path = extract_dir / "initrd"
        if not kernel_path.exists():
            self._run_checked(
                [
                    "xorriso",
                    "-osirrox",
                    "on",
                    "-indev",
                    str(iso_path),
                    "-extract",
                    "/casper/vmlinuz",
                    str(kernel_path),
                ],
                timeout=None,
            )
            kernel_path.chmod(0o644)
        if not initrd_path.exists():
            try:
                self._run_checked(
                    [
                        "xorriso",
                        "-osirrox",
                        "on",
                        "-indev",
                        str(iso_path),
                        "-extract",
                        "/casper/initrd",
                        str(initrd_path),
                    ],
                    timeout=None,
                )
            except subprocess.CalledProcessError:
                self._run_checked(
                    [
                        "xorriso",
                        "-osirrox",
                        "on",
                        "-indev",
                        str(iso_path),
                        "-extract",
                        "/casper/initrd.gz",
                        str(initrd_path),
                    ],
                    timeout=None,
                )
            initrd_path.chmod(0o644)

        # Ensure existing files are readable by the libvirt worker account.
        kernel_path.chmod(0o644)
        initrd_path.chmod(0o644)

        return {
            "iso_filename": iso_filename,
            "iso_path": str(iso_path),
            "kernel_path": str(kernel_path),
            "initrd_path": str(initrd_path),
        }

    @staticmethod
    def render_template_file(path: Path, values: dict[str, str]) -> str:
        content = path.read_text(encoding="utf-8")
        for key, value in values.items():
            content = content.replace(key, value)
        return content

    def locale_language(self, locale: str) -> str:
        value = str(locale or "").strip() or self._ubuntu_beagle_default_locale
        base = value.split(".", 1)[0].strip()
        if not base:
            return ""
        if "_" in base:
            return f"{base}:{base.split('_', 1)[0]}"
        return base

    @staticmethod
    def indent_block(text: str, prefix: str) -> str:
        lines = str(text).splitlines()
        if not lines:
            return prefix.rstrip()
        return "\n".join(f"{prefix}{line}" if line else prefix.rstrip() for line in lines)

    def build_desktop_wallpaper_write_file_block(self, wallpaper_asset: dict[str, str]) -> str:
        wallpaper_filename = str(wallpaper_asset.get("filename", "")).strip()
        wallpaper_source = str(wallpaper_asset.get("source", "")).strip()
        if not wallpaper_filename or not wallpaper_source:
            return ""
        wallpaper_b64 = base64.b64encode(Path(wallpaper_source).read_bytes()).decode("ascii")
        lines = [
            "      - path: /var/lib/beagle/seed/" + wallpaper_filename,
            "        owner: root:root",
            "        permissions: '0644'",
            "        encoding: b64",
            "        content: |",
            self.indent_block(wallpaper_b64, "          "),
        ]
        return "\n" + "\n".join(lines)

    def resolve_desktop_wallpaper_asset(self, desktop_id: str) -> dict[str, str]:
        desktop = self._resolve_ubuntu_beagle_desktop(desktop_id or self._ubuntu_beagle_default_desktop)
        wallpaper_required = bool(desktop.get("wallpaper_required"))
        configured_source = str(
            desktop.get("wallpaper_source")
            or (self._ubuntu_beagle_cyberpunk_wallpaper_source if str(desktop.get("theme_variant", "")) == "cyberpunk" else "")
        ).strip()
        if not configured_source:
            if wallpaper_required:
                raise FileNotFoundError(
                    f"desktop profile '{desktop['id']}' requires a wallpaper source but none is configured"
                )
            return {}
        source = Path(os.path.expanduser(configured_source))
        if not source.is_file():
            raise FileNotFoundError(
                f"desktop profile '{desktop['id']}' requires wallpaper file '{source}', but it was not found"
            )
        return {
            "filename": self._safe_slug(source.name, "beagle-wallpaper.png"),
            "source": str(source),
        }

    def openssl_password_hash(self, password: str) -> str:
        salt = self._random_secret(16).lower()
        return self._run_checked(["openssl", "passwd", "-6", "-salt", salt, password]).strip()

    def build_ubuntu_beagle_description(
        self,
        hostname: str,
        guest_user: str,
        public_stream: dict[str, Any] | None = None,
        *,
        os_profile: str = "",
        identity_locale: str = "",
        identity_keymap: str = "",
        desktop_id: str = "",
        package_presets: list[str] | None = None,
        extra_packages: list[str] | None = None,
    ) -> str:
        desktop = self._resolve_ubuntu_beagle_desktop(desktop_id or self._ubuntu_beagle_default_desktop)
        package_presets = package_presets or []
        extra_packages = extra_packages or []
        lines = [
            "beagle-role: desktop",
            f"beagle-os-profile: {os_profile or self._ubuntu_beagle_profile_id}",
            "beagle-os-family: ubuntu",
            f"beagle-os-release: {self._ubuntu_beagle_profile_release}",
            f"beagle-desktop: {desktop['label']}",
            f"beagle-desktop-id: {desktop['id']}",
            f"beagle-desktop-session: {desktop['session']}",
            f"beagle-desktop-theme: {desktop.get('theme_variant', desktop['id'])}",
            f"beagle-streaming: {self._ubuntu_beagle_profile_streaming}",
            f"beagle-stream-server-guest-user: {guest_user}",
            "beagle-stream-server-app: Desktop",
            "beagle-stream-client-app: Desktop",
            "beagle-stream-client-resolution: 1920x1080",
            "beagle-stream-client-fps: 60",
            "beagle-stream-client-bitrate: 32000",
            "beagle-stream-client-video-codec: H.264",
            "beagle-stream-client-video-decoder: software",
            "beagle-stream-client-audio-config: stereo",
            "thinclient-default-mode: BEAGLE_STREAM_CLIENT",
            "beagle-template-set: ubuntu-beagle",
            f"beagle-template-hostname: {hostname}",
            f"beagle-identity-hostname: {hostname}",
            f"beagle-identity-locale: {identity_locale or self._ubuntu_beagle_default_locale}",
            f"beagle-identity-keymap: {identity_keymap or self._ubuntu_beagle_default_keymap}",
        ]
        if package_presets:
            lines.append(f"beagle-package-presets: {','.join(package_presets)}")
        if extra_packages:
            lines.append(f"beagle-extra-packages: {','.join(extra_packages)}")
        if public_stream:
            public_host = str(public_stream.get("host", "")).strip()
            beagle_stream_client_port = int(public_stream.get("beagle_stream_client_port", 0) or 0)
            beagle_stream_server_api_url = str(public_stream.get("beagle_stream_server_api_url", "")).strip()
            if public_host:
                lines.append(f"beagle-public-stream-host: {public_host}")
            if beagle_stream_client_port > 0:
                lines.append(f"beagle-public-beagle-stream-client-port: {beagle_stream_client_port}")
            if beagle_stream_server_api_url:
                lines.append(f"beagle-public-beagle-stream-server-api-url: {beagle_stream_server_api_url}")
        return "\n".join(lines) + "\n"

    def build_ubuntu_beagle_seed_iso(
        self,
        *,
        vmid: int,
        hostname: str,
        guest_user: str,
        guest_password_hash: str,
        identity_locale: str,
        identity_keymap: str,
        desktop_id: str,
        desktop_session: str,
        desktop_packages: list[str],
        software_packages: list[str],
        package_presets: list[str],
        network_mac: str,
        beagle_stream_server_user: str,
        beagle_stream_server_password: str,
        beagle_stream_server_token: str,
        beagle_stream_server_port: int | None,
        callback_url: str,
    ) -> Path:
        if not self._template_dir.exists():
            raise FileNotFoundError(f"missing ubuntu-beagle templates: {self._template_dir}")
        desktop = self._resolve_ubuntu_beagle_desktop(desktop_id or self._ubuntu_beagle_default_desktop)
        wallpaper_asset = self.resolve_desktop_wallpaper_asset(desktop["id"])
        wallpaper_filename = str(wallpaper_asset.get("filename", "")).strip()
        wallpaper_write_file = self.build_desktop_wallpaper_write_file_block(wallpaper_asset)
        desktop_theme_variant = str(desktop.get("theme_variant", desktop["id"])).strip()

        firstboot_script = self.render_template_file(
            self._template_dir / "firstboot-provision.sh.tpl",
            {
                "__GUEST_USER__": guest_user,
                "__VMID__": str(int(vmid)),
                "__BEAGLE_MANAGER_URL__": self._public_manager_url,
                "__BEAGLE_STREAM_SERVER_USER__": beagle_stream_server_user,
                "__BEAGLE_STREAM_SERVER_PASSWORD__": beagle_stream_server_password,
                "__BEAGLE_STREAM_SERVER_TOKEN__": beagle_stream_server_token,
                "__BEAGLE_STREAM_SERVER_PORT__": str(int(beagle_stream_server_port)) if beagle_stream_server_port else "",
                "__BEAGLE_STREAM_SERVER_URL__": self._ubuntu_beagle_stream_server_url,
                "__BEAGLE_STREAM_SERVER_URL__": self._ubuntu_beagle_beagle_stream_server_url,
                "__BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED__": "wan",
                "__IDENTITY_LOCALE__": identity_locale,
                "__IDENTITY_LANGUAGE__": self.locale_language(identity_locale),
                "__IDENTITY_KEYMAP__": identity_keymap,
                "__DESKTOP_ID__": desktop_id,
                "__DESKTOP_THEME_VARIANT__": desktop_theme_variant,
                "__DESKTOP_SESSION__": desktop_session,
                "__DESKTOP_PACKAGES__": " ".join(desktop_packages),
                "__DESKTOP_WALLPAPER_FILENAME__": wallpaper_filename,
                "__SOFTWARE_PACKAGES__": " ".join(software_packages),
                "__PACKAGE_PRESETS__": ",".join(package_presets),
                "__NETWORK_MAC__": network_mac,
                "__CALLBACK_URL__": callback_url,
                "__CALLBACK_PINNED_PUBKEY__": self._manager_pinned_pubkey,
            },
        ).rstrip()
        firstboot_service = "\n".join(
            [
                "[Unit]",
                "Description=Beagle Ubuntu Desktop First Boot Provisioning",
                "After=network-online.target systemd-resolved.service",
                "Wants=network-online.target systemd-resolved.service",
                "StartLimitIntervalSec=0",
                "ConditionPathExists=!/var/lib/beagle/ubuntu-firstboot.done",
                "",
                "[Service]",
                "Type=oneshot",
                "ExecStart=/usr/local/sbin/beagle-ubuntu-firstboot.sh",
                "Restart=on-failure",
                "RestartSec=15",
                "RemainAfterExit=yes",
                "",
                "[Install]",
                "WantedBy=multi-user.target",
                "",
            ]
        )
        firstboot_script_b64 = base64.b64encode((firstboot_script + "\n").encode("utf-8")).decode("ascii")
        firstboot_service_b64 = base64.b64encode(firstboot_service.encode("utf-8")).decode("ascii")
        user_data = self.render_template_file(
            self._template_dir / "user-data.tpl",
            {
                "__HOSTNAME__": hostname,
                "__GUEST_USER__": guest_user,
                "__GUEST_PASSWORD_HASH__": guest_password_hash,
                "__IDENTITY_LOCALE__": identity_locale,
                "__IDENTITY_KEYMAP__": identity_keymap,
                "__CALLBACK_URL__": callback_url,
                "__PREPARE_FIRSTBOOT_URL__": callback_url.rsplit("/complete", 1)[0] + "/prepare-firstboot",
                "__PREPARE_FIRSTBOOT_CURL_ARGS__": f'-k --pinnedpubkey "{self._manager_pinned_pubkey}"' if self._manager_pinned_pubkey else "-k",
                "__NETWORK_MAC__": network_mac,
                "__FIRSTBOOT_SCRIPT__": self.indent_block(firstboot_script, "          "),
                "__FIRSTBOOT_SCRIPT_B64__": firstboot_script_b64,
                "__FIRSTBOOT_SERVICE_B64__": firstboot_service_b64,
                "__DESKTOP_WALLPAPER_WRITE_FILE__": wallpaper_write_file,
            },
        )
        meta_data = self.render_template_file(
            self._template_dir / "meta-data.tpl",
            {
                "__INSTANCE_ID__": f"beagle-ubuntu-{vmid}",
                "__HOSTNAME__": hostname,
            },
        )

        work_dir = self._ubuntu_beagle_tokens_dir() / "seed" / str(vmid)
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "user-data").write_text(user_data, encoding="utf-8")
        (work_dir / "meta-data").write_text(meta_data, encoding="utf-8")
        if wallpaper_filename:
            shutil.copy2(Path(wallpaper_asset["source"]), work_dir / wallpaper_filename)
        seed_name = f"beagle-ubuntu-autoinstall-vm{vmid}.iso"
        seed_path = self.local_iso_storage_dir() / seed_name
        seed_path.unlink(missing_ok=True)
        iso_command = [
            "xorriso",
            "-as",
            "mkisofs",
            "-volid",
            "CIDATA",
            "-joliet",
            "-rock",
            "-output",
            str(seed_path),
            str(work_dir / "user-data"),
            str(work_dir / "meta-data"),
        ]
        if wallpaper_filename:
            iso_command.append(str(work_dir / wallpaper_filename))
        self._run_checked(iso_command, timeout=None)
        return seed_path

    def finalize_ubuntu_beagle_install(self, state: dict[str, Any], *, restart: bool = True) -> dict[str, Any]:
        vmid = int(state["vmid"])
        vm = self._find_vm(vmid)
        config = self._get_vm_config(vm.node, vm.vmid) if vm is not None else {}
        stale_options = [option for option in ("args", "ide2", "ide3") if option in config]
        for option in stale_options:
            try:
                self._provider.delete_vm_options(vmid, [option], timeout=None)
            except subprocess.CalledProcessError:
                pass
        boot_disk = ""
        for candidate in ("scsi0", "virtio0", "sata0", "ide0"):
            if candidate in config:
                boot_disk = candidate
                break
        if not boot_disk:
            boot_disk = "scsi0"
        desired_boot = f"order={boot_disk}"
        if str(config.get("boot", "") or "").strip() != desired_boot:
            self._provider.set_vm_boot_order(vmid, desired_boot, timeout=None)
        if restart:
            try:
                self._provider.stop_vm(vmid, skiplock=True, timeout=None)
            except Exception:
                pass
            self._provider.start_vm(vmid, timeout=None)
            # Ensure VM is not paused due to QEMU -S flag or other provisioning side effects
            try:
                self._provider.resume_vm(vmid, timeout=None)
            except Exception:
                pass
        if self._reconcile_public_streams_script.is_file():
            try:
                self._run_checked([str(self._reconcile_public_streams_script)], timeout=None)
            except subprocess.CalledProcessError:
                pass
        return {"vmid": vmid, "cleanup": "ok", "restart": "stop-start" if restart else "guest-reboot"}

    @staticmethod
    def ubuntu_beagle_network_mac(vmid: int) -> str:
        value = int(vmid) & 0xFFFFFF
        return "52:54:00:%02x:%02x:%02x" % (
            (value >> 16) & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF,
        )

    def prepare_ubuntu_beagle_firstboot(self, state: dict[str, Any]) -> dict[str, Any]:
        cleanup = self.finalize_ubuntu_beagle_install(state, restart=True)
        state["updated_at"] = self._utcnow()
        state["status"] = "installing"
        state["phase"] = "firstboot"
        state["message"] = (
            "Ubuntu-Basisinstallation ist abgeschlossen. Der Host hat den Gast neu gestartet; "
            "First-Boot-Provisioning laeuft."
        )
        state["cleanup"] = cleanup
        return cleanup

    def create_ubuntu_beagle_vm(self, payload: dict[str, Any]) -> dict[str, Any]:
        os_profile = str(payload.get("os_profile", "") or self._ubuntu_beagle_profile_id).strip() or self._ubuntu_beagle_profile_id
        if os_profile not in {self._ubuntu_beagle_profile_id, *self._ubuntu_beagle_profile_legacy_ids.keys()}:
            raise ValueError(f"unsupported os_profile: {os_profile}")
        desktop = self._resolve_ubuntu_beagle_desktop(
            str(payload.get("desktop", "") or payload.get("desktop_id", "") or self._ubuntu_beagle_default_desktop)
        )
        package_presets = self._normalize_package_presets(
            payload.get("package_presets", self._ubuntu_beagle_default_package_presets)
        )
        extra_packages = self._normalize_package_names(payload.get("extra_packages", []), field_name="extra_packages")
        software_packages = self._expand_software_packages(package_presets, extra_packages)
        node = str(payload.get("node", "")).strip()
        if not node:
            raise ValueError("missing node")
        known_nodes = {str(item.get("name", "")).strip() for item in self._list_nodes_inventory()}
        if node not in known_nodes:
            raise ValueError(f"unknown node: {node}")
        vmid_value = payload.get("vmid")
        vmid = int(vmid_value) if str(vmid_value or "").strip() else int(self._provider.next_vmid())
        if self._find_vm(vmid, refresh=True) is not None:
            raise ValueError(f"vmid already exists: {vmid}")
        name = str(payload.get("name", "")).strip() or f"ubuntu-beagle-{vmid}"
        if not name:
            raise ValueError("missing name")
        memory = int(payload.get("memory", self._ubuntu_beagle_default_memory_mib))
        if memory < 2048:
            raise ValueError("memory must be at least 2048 MiB")
        cores = int(payload.get("cores", self._ubuntu_beagle_default_cores))
        if cores < 2:
            raise ValueError("cores must be at least 2")
        memory_budget_mib = self._node_memory_budget_mib(node)
        if memory_budget_mib is not None and memory_budget_mib < 2048:
            raise ValueError(
                f"insufficient host memory on node {node}: available budget {memory_budget_mib} MiB,"
                " minimum required is 2048 MiB"
            )
        if memory_budget_mib is not None and memory > memory_budget_mib:
            raise ValueError(
                f"insufficient host memory on node {node}: requested {memory} MiB,"
                f" available budget is {memory_budget_mib} MiB"
            )
        disk_gb = int(payload.get("disk_gb", self._ubuntu_beagle_default_disk_gb))
        if disk_gb < 32:
            raise ValueError("disk_gb must be at least 32")
        bridge = str(payload.get("bridge", self._ubuntu_beagle_default_bridge)).strip() or self._ubuntu_beagle_default_bridge
        if not bridge:
            raise ValueError("missing bridge")
        iso_storage = self.resolve_storage(
            str(payload.get("iso_storage", self._ubuntu_beagle_iso_storage)).strip() or self._ubuntu_beagle_iso_storage,
            "iso",
            self._ubuntu_beagle_iso_storage,
        )
        disk_storage = self.resolve_storage(
            str(payload.get("disk_storage", self._ubuntu_beagle_disk_storage)).strip() or self._ubuntu_beagle_disk_storage,
            "images",
            self._ubuntu_beagle_disk_storage,
        )
        self.enforce_storage_quota(disk_storage, disk_gb * 1024 * 1024 * 1024)
        guest_user = self._validate_linux_username(
            str(payload.get("guest_user", self._ubuntu_beagle_default_guest_user)).strip() or self._ubuntu_beagle_default_guest_user,
            "guest_user",
        )
        start_after_create = str(payload.get("start", "1")).strip().lower() not in {"0", "false", "no", "off"}
        hostname = self._safe_hostname(str(payload.get("hostname", "")).strip() or name, vmid)
        iso_assets = self.ensure_ubuntu_beagle_iso_cached(self._ubuntu_beagle_iso_url)
        beagle_stream_server_user_input = str(payload.get("beagle_stream_server_user", "")).strip()
        beagle_stream_server_user = (
            self._validate_linux_username(beagle_stream_server_user_input, "beagle_stream_server_user")
            if beagle_stream_server_user_input
            else f"beagle-stream-server-vm{vmid}"
        )
        beagle_stream_server_password_input = str(payload.get("beagle_stream_server_password", ""))
        beagle_stream_server_password = self._validate_password(beagle_stream_server_password_input, "beagle_stream_server_password", allow_empty=True) or self._random_secret(26)
        beagle_stream_server_token = secrets.token_urlsafe(32)
        guest_password_input = str(payload.get("guest_password", ""))
        guest_password = self._validate_password(guest_password_input, "guest_password", allow_empty=True) or self._random_secret(20)
        identity_locale = self._normalize_locale(payload.get("identity_locale", ""))
        identity_keymap = self._normalize_keymap(payload.get("identity_keymap", ""))
        guest_password_hash = self.openssl_password_hash(guest_password)
        completion_token = secrets.token_urlsafe(24)
        callback_url = self._public_ubuntu_beagle_complete_url(completion_token)
        public_stream: dict[str, Any] | None = None
        public_base_port = self._allocate_public_stream_base_port(node, vmid)
        beagle_stream_server_port: int | None = None
        network_mac = self.ubuntu_beagle_network_mac(vmid)
        ha_policy = self._normalize_ha_policy(payload.get("ha_policy", ""))
        resolved_public_stream_host = self._current_public_stream_host()
        if resolved_public_stream_host and public_base_port is not None:
            ports = self._stream_ports(public_base_port)
            beagle_stream_server_port = ports["beagle_stream_client_port"]
            public_stream = {
                "host": resolved_public_stream_host,
                "beagle_stream_client_port": ports["beagle_stream_client_port"],
                "beagle_stream_server_api_url": f"https://{resolved_public_stream_host}:{ports['beagle_stream_server_api_port']}",
            }
        seed_path = self.build_ubuntu_beagle_seed_iso(
            vmid=vmid,
            hostname=hostname,
            guest_user=guest_user,
            guest_password_hash=guest_password_hash,
            identity_locale=identity_locale,
            identity_keymap=identity_keymap,
            desktop_id=str(desktop["id"]),
            desktop_session=str(desktop["session"]),
            desktop_packages=list(desktop.get("packages", []) or []),
            software_packages=software_packages,
            package_presets=package_presets,
            network_mac=network_mac,
            beagle_stream_server_user=beagle_stream_server_user,
            beagle_stream_server_password=beagle_stream_server_password,
            beagle_stream_server_token=beagle_stream_server_token,
            beagle_stream_server_port=beagle_stream_server_port,
            callback_url=callback_url,
        )
        # Keep storage references reproducible across providers by ensuring
        # both Ubuntu ISO and generated seed ISO are present in iso_storage.
        self.ensure_iso_in_storage_pool(iso_storage, Path(iso_assets["iso_path"]))
        self.ensure_iso_in_storage_pool(iso_storage, seed_path)
        description = self.build_ubuntu_beagle_description(
            hostname,
            guest_user,
            public_stream,
            os_profile=os_profile,
            identity_locale=identity_locale,
            identity_keymap=identity_keymap,
            desktop_id=str(desktop["id"]),
            package_presets=package_presets,
            extra_packages=extra_packages,
        )
        args = " ".join(
            [
                f"-kernel {shlex.quote(iso_assets['kernel_path'])}",
                f"-initrd {shlex.quote(iso_assets['initrd_path'])}",
                "-append",
                shlex.quote("autoinstall console=tty0 console=ttyS0,115200n8 ---"),
            ]
        )
        tags = "beagle;desktop;ubuntu"
        state = self._save_ubuntu_beagle_state(
            completion_token,
            {
                "token": completion_token,
                "node": node,
                "vmid": vmid,
                "name": name,
                "hostname": hostname,
                "os_profile": os_profile,
                "guest_user": guest_user,
                "guest_password": guest_password,
                "beagle_stream_server_user": beagle_stream_server_user,
                "beagle_stream_server_password": beagle_stream_server_password,
                "beagle_stream_server_token": beagle_stream_server_token,
                "desktop": str(desktop["id"]),
                "desktop_label": str(desktop["label"]),
                "package_presets": package_presets,
                "extra_packages": extra_packages,
                "software_packages": software_packages,
                "identity_locale": identity_locale,
                "identity_keymap": identity_keymap,
                "bridge": bridge,
                "network_mac": network_mac,
                "disk_storage": disk_storage,
                "iso_storage": iso_storage,
                "seed_iso": str(seed_path),
                "iso_filename": iso_assets["iso_filename"],
                "callback_url": callback_url,
                "public_stream": public_stream,
                "status": "creating",
                "phase": "beagle-create",
                "message": "Beagle-VM und Autoinstall-Medien werden vorbereitet.",
                "created_at": self._utcnow(),
                "updated_at": self._utcnow(),
                "expires_at": self._time_now_epoch() + self._ubuntu_beagle_autoinstall_url_ttl_seconds,
            },
        )

        try:
            self._provider.create_vm(
                vmid,
                [
                    ("name", name),
                    ("memory", str(memory)),
                    ("cores", str(cores)),
                    ("cpu", "host"),
                    ("machine", "q35"),
                    ("bios", "ovmf"),
                    ("ostype", "l26"),
                    ("agent", "enabled=1"),
                    ("net0", f"virtio,bridge={bridge},macaddr={network_mac}"),
                    ("tags", tags),
                ],
                timeout=None,
            )
            self._provider.set_vm_description(vmid, description, timeout=None)
            self._provider.set_vm_options(
                vmid,
                [
                    ("scsihw", "virtio-scsi-single"),
                    ("scsi0", f"{disk_storage}:{disk_gb}"),
                    ("efidisk0", f"{disk_storage}:0,efitype=4m,pre-enrolled-keys=1"),
                    ("serial0", "socket"),
                    ("vga", "std"),
                    ("ide2", f"{iso_storage}:iso/{iso_assets['iso_filename']},media=cdrom"),
                    ("ide3", f"{iso_storage}:iso/{seed_path.name},media=cdrom"),
                    ("args", args),
                ],
                timeout=None,
            )
            if ha_policy:
                self._provider.set_vm_options(
                    vmid,
                    [("ha_policy", ha_policy)],
                    timeout=None,
                )
            self._provider.set_vm_boot_order(vmid, "order=scsi0;ide2;ide3", timeout=None)
            if start_after_create:
                self._provider.start_vm(vmid, timeout=None)
            self._invalidate_vm_cache(vmid, node)
        except Exception as exc:
            self._invalidate_vm_cache(vmid, node)
            state["status"] = "failed"
            state["phase"] = "beagle-create"
            state["message"] = "Die VM konnte nicht vollstaendig angelegt werden."
            state["error"] = str(exc)
            state["failed_at"] = self._utcnow()
            state["updated_at"] = self._utcnow()
            self._save_ubuntu_beagle_state(completion_token, state)
            raise

        self._save_vm_secret(
            node,
            vmid,
            {
                "guest_password": guest_password,
                "password": guest_password,
                "beagle_stream_server_username": beagle_stream_server_user,
                "beagle_stream_server_password": beagle_stream_server_password,
                "beagle_stream_server_token": beagle_stream_server_token,
                "beagle_stream_server_token_generation": 1,
                "thinclient_password": self._random_secret(22),
                "beagle_stream_server_pinned_pubkey": "",
                "usb_tunnel_port": self._default_usb_tunnel_port(vmid),
                "node": node,
                "vmid": vmid,
                "updated_at": self._utcnow(),
            },
        )
        created_vm = self._make_vm_summary(
            vmid=vmid,
            node=node,
            name=name,
            status="running" if start_after_create else "stopped",
            tags=tags,
        )
        secret = self._ensure_vm_secret(created_vm)
        state["status"] = "installing" if start_after_create else "created"
        state["phase"] = "autoinstall" if start_after_create else "awaiting-start"
        state["message"] = (
            f"Ubuntu-Autoinstall laeuft. {desktop['label']}, LightDM und BeagleStream Server werden im Guest eingerichtet."
            if start_after_create
            else f"VM angelegt. Starten Sie die VM, um Ubuntu, {desktop['label']}, LightDM und BeagleStream Server zu provisionieren."
        )
        state["started"] = start_after_create
        state["updated_at"] = self._utcnow()
        self._save_ubuntu_beagle_state(completion_token, state)
        return {
            "vmid": vmid,
            "node": node,
            "name": name,
            "hostname": hostname,
            "os_profile": os_profile,
            "desktop": str(desktop["id"]),
            "desktop_label": str(desktop["label"]),
            "package_presets": package_presets,
            "extra_packages": extra_packages,
            "bridge": bridge,
            "disk_storage": disk_storage,
            "iso_storage": iso_storage,
            "iso_filename": iso_assets["iso_filename"],
            "seed_iso": seed_path.name,
            "guest_user": guest_user,
            "guest_password": guest_password,
            "identity_locale": identity_locale,
            "identity_keymap": identity_keymap,
            "beagle_stream_server_user": str(secret.get("beagle_stream_server_username", "") or beagle_stream_server_user),
            "beagle_stream_server_password": str(secret.get("beagle_stream_server_password", "") or beagle_stream_server_password),
            "beagle_stream_server_token": str(secret.get("beagle_stream_server_token", "") or ""),
            "completion_token": completion_token,
            "completion_url": callback_url,
            "started": start_after_create,
            "state": state,
            "provisioning": self._summarize_ubuntu_beagle_state(state, include_credentials=True),
            "public_stream": public_stream,
            "ha_policy": ha_policy,
        }

    def update_ubuntu_beagle_vm(self, vmid: int, payload: dict[str, Any]) -> dict[str, Any]:
        vm = self._find_vm(vmid, refresh=True)
        if vm is None:
            raise ValueError("vm not found")
        current_profile = self._build_profile(vm)
        if str(current_profile.get("beagle_role", "")).strip().lower() != "desktop":
            raise ValueError("vm is not a managed Beagle desktop target")

        desktop = self._resolve_ubuntu_beagle_desktop(
            str(
                payload.get("desktop", "")
                or payload.get("desktop_id", "")
                or current_profile.get("desktop_id", "")
                or self._ubuntu_beagle_default_desktop
            )
        )
        package_presets = self._normalize_package_presets(payload.get("package_presets", current_profile.get("package_presets", [])))
        extra_packages = self._normalize_package_names(
            payload.get("extra_packages", current_profile.get("extra_packages", [])),
            field_name="extra_packages",
        )
        software_packages = self._expand_software_packages(package_presets, extra_packages)
        identity_locale = self._normalize_locale(payload.get("identity_locale", current_profile.get("identity_locale", "")))
        identity_keymap = self._normalize_keymap(payload.get("identity_keymap", current_profile.get("identity_keymap", "")))
        guest_user = self._validate_linux_username(
            str(current_profile.get("guest_user", "") or self._ubuntu_beagle_default_guest_user),
            "guest_user",
        )
        hostname = self._safe_hostname(
            str(current_profile.get("identity_hostname", "") or current_profile.get("name", "") or f"beagle-{vmid}"),
            vmid,
        )
        public_stream = current_profile.get("public_stream") if isinstance(current_profile.get("public_stream"), dict) else None
        description = self.build_ubuntu_beagle_description(
            hostname,
            guest_user,
            public_stream,
            os_profile=self._ubuntu_beagle_profile_id,
            identity_locale=identity_locale,
            identity_keymap=identity_keymap,
            desktop_id=str(desktop["id"]),
            package_presets=package_presets,
            extra_packages=extra_packages,
        )
        self._provider.set_vm_description(vmid, description, timeout=None)
        ha_policy = ""
        if "ha_policy" in payload:
            ha_policy = self._normalize_ha_policy(payload.get("ha_policy"))
            self._provider.set_vm_options(vmid, [("ha_policy", ha_policy)], timeout=None)

        applied = False
        if vm.status == "running":
            secret = self._ensure_vm_secret(vm)
            provisioning_state = self._latest_ubuntu_beagle_state_for_vmid(vmid, include_credentials=True) or {}
            credentials = provisioning_state.get("credentials") if isinstance(provisioning_state.get("credentials"), dict) else {}
            guest_password = str(credentials.get("guest_password", "") or "").strip()
            beagle_stream_server_user = str(secret.get("beagle_stream_server_username", "") or "").strip()
            beagle_stream_server_password = str(secret.get("beagle_stream_server_password", "") or "").strip()
            if not beagle_stream_server_user or not beagle_stream_server_password:
                raise RuntimeError("beagle-stream-server credentials are missing for guest reconfiguration")
            configure_command = [
                str(self._configure_beagle_stream_server_guest_script),
                "--beagle-host",
                "localhost",
                "--vmid",
                str(vmid),
                "--guest-user",
                guest_user,
                "--guest-password",
                guest_password,
                "--identity-locale",
                identity_locale,
                "--identity-keymap",
                identity_keymap,
                "--desktop-id",
                str(desktop["id"]),
                "--desktop-label",
                str(desktop["label"]),
                "--desktop-session",
                str(desktop["session"]),
                "--beagle-stream-server-user",
                beagle_stream_server_user,
                "--beagle-stream-server-password",
                beagle_stream_server_password,
            ]
            beagle_stream_server_token = str(secret.get("beagle_stream_server_token", "") or "").strip()
            if beagle_stream_server_token:
                configure_command.extend(["--beagle-stream-server-token", beagle_stream_server_token])
            beagle_stream_client_port = str(current_profile.get("beagle_stream_client_port", "") or "").strip()
            if beagle_stream_client_port.isdigit():
                configure_command.extend(["--beagle-stream-server-port", beagle_stream_client_port])
            public_stream_host = str(current_profile.get("stream_host", "") or "").strip()
            if public_stream_host:
                configure_command.extend(["--public-stream-host", public_stream_host])
            for package_name in desktop.get("packages", []) or []:
                configure_command.extend(["--desktop-package", str(package_name)])
            for package_name in software_packages:
                configure_command.extend(["--software-package", package_name])
            for preset_id in package_presets:
                configure_command.extend(["--package-preset", preset_id])
            for package_name in extra_packages:
                configure_command.extend(["--extra-package", package_name])
            self._run_checked(configure_command, timeout=None)
            applied = True

        self._invalidate_vm_cache(vmid, vm.node)
        updated_vm = self._find_vm(vmid, refresh=True) or vm
        updated_profile = self._build_profile(updated_vm)
        return {
            "vmid": vmid,
            "node": updated_vm.node,
            "name": updated_vm.name,
            "applied": applied,
            "desktop": str(desktop["id"]),
            "desktop_label": str(desktop["label"]),
            "package_presets": package_presets,
            "extra_packages": extra_packages,
            "software_packages": software_packages,
            "identity_locale": identity_locale,
            "identity_keymap": identity_keymap,
            "requires_running_guest": not applied,
            "profile": updated_profile,
            "message": (
                "Desktop profile and packages were applied inside the running guest."
                if applied
                else "VM metadata was updated. Start the guest and re-run the edit action to apply packages inside Ubuntu."
            ),
            "ha_policy": ha_policy,
        }
