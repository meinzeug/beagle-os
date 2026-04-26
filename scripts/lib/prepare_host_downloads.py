#!/usr/bin/env python3
"""Helpers for scripts/prepare-host-downloads.sh.

This module owns the non-shell artifact patching and VM installer metadata
generation used by the host download-preparation script. Keeping that logic
here removes the large inline Python blocks from the shell entrypoint and lets
the metadata builder reuse the extracted host-side contract helpers.
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_SERVICES_DIR = REPO_ROOT / "beagle-host" / "services"
HOST_BIN_DIR = REPO_ROOT / "beagle-host" / "bin"

for helper_dir in (HOST_SERVICES_DIR, HOST_BIN_DIR):
    helper_path = str(helper_dir)
    if helper_path not in sys.path:
        sys.path.insert(0, helper_path)

from endpoint_profile_contract import normalize_endpoint_profile_contract
from installer_template_patch import InstallerTemplatePatchService
from metadata_support import MetadataSupportService


def _load_provider_module(provider_module_path: Path) -> Any:
    resolved = Path(provider_module_path).resolve()
    spec = importlib.util.spec_from_file_location("beagle_script_provider_runtime", resolved)
    if spec is None or spec.loader is None:
        raise SystemExit(f"unable to load provider helper: {resolved}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _encode_preset(preset: dict[str, Any]) -> str:
    lines = ["# Auto-generated VM preset for the thin-client USB installer"]
    for key in sorted(preset):
        value = str(preset.get(key, ""))
        lines.append(f"{key}={shlex.quote(value)}")
    payload = "\n".join(lines) + "\n"
    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


def _legacy_safe_hostname(name: str, vmid: int) -> str:
    cleaned = re.sub(r"[^a-z0-9-]+", "-", str(name or "").strip().lower()).strip("-")
    if not cleaned:
        cleaned = f"pve-tc-{int(vmid)}"
    return cleaned[:63].strip("-") or f"pve-tc-{int(vmid)}"


def patch_host_shell_template(
    *,
    path: Path,
    writer_variant: str,
    installer_iso_url: str,
    installer_bootstrap_url: str,
    installer_payload_url: str,
) -> None:
    template_patch = InstallerTemplatePatchService()
    rendered = template_patch.patch_installer_defaults(
        path.read_text(encoding="utf-8"),
        "",
        "",
        str(installer_iso_url or ""),
        str(installer_bootstrap_url or ""),
        str(installer_payload_url or ""),
        str(writer_variant or ""),
    )
    path.write_text(rendered, encoding="utf-8")


def patch_host_windows_template(*, path: Path, installer_iso_url: str, writer_variant: str) -> None:
    template_patch = InstallerTemplatePatchService()
    rendered = template_patch.patch_windows_installer_defaults(
        path.read_text(encoding="utf-8"),
        "",
        "",
        str(installer_iso_url or ""),
        str(writer_variant or ""),
    )
    path.write_text(rendered, encoding="utf-8")


def _merge_stream_meta(
    *,
    vm: dict[str, Any],
    meta: dict[str, str],
    load_vm_config: Callable[[str, int], dict[str, Any]],
    parse_description_meta: Callable[[str], dict[str, str]],
) -> dict[str, str]:
    stream_keys = [
        "moonlight-host",
        "moonlight-app",
        "moonlight-resolution",
        "moonlight-fps",
        "moonlight-bitrate",
        "moonlight-video-codec",
        "moonlight-video-decoder",
        "moonlight-audio-config",
        "moonlight-absolute-mouse",
        "moonlight-quit-after",
        "sunshine-host",
        "sunshine-ip",
        "sunshine-api-url",
        "sunshine-user",
        "sunshine-password",
        "sunshine-pin",
        "sunshine-app",
        "thinclient-default-mode",
    ]
    if any(meta.get(key) for key in ("moonlight-host", "sunshine-host", "sunshine-ip")):
        return dict(meta)

    target_vmid = (meta.get("beagle-target-vmid") or meta.get("thinclient-target-vmid") or "").strip()
    if not target_vmid.isdigit():
        return dict(meta)

    target_node = (meta.get("beagle-target-node") or vm.get("node") or "").strip()
    target_config = load_vm_config(target_node, int(target_vmid))
    if not target_config:
        return dict(meta)

    target_meta = parse_description_meta(target_config.get("description", ""))
    merged = dict(meta)
    for key in stream_keys:
        if not merged.get(key) and target_meta.get(key):
            merged[key] = target_meta[key]
    return merged


def _build_vm_catalog_entry(
    *,
    vm: dict[str, Any],
    config: dict[str, Any],
    load_vm_config: Callable[[str, int], dict[str, Any]],
    metadata_support: MetadataSupportService,
    server_name: str,
    installer_iso_url: str,
    default_proxmox_username: str,
    default_proxmox_password: str,
    default_proxmox_token: str,
    beagle_manager_url: str,
) -> dict[str, Any]:
    meta = metadata_support.parse_description_meta(config.get("description", ""))
    stream_meta = _merge_stream_meta(
        vm=vm,
        meta=meta,
        load_vm_config=load_vm_config,
        parse_description_meta=metadata_support.parse_description_meta,
    )
    vmid = int(vm["vmid"])
    vm_name = str(config.get("name") or vm.get("name") or f"vm-{vmid}")
    proxmox_scheme = meta.get("proxmox-scheme", "https")
    proxmox_host = meta.get("proxmox-host", server_name)
    proxmox_port = meta.get("proxmox-port", "8006")
    proxmox_realm = meta.get("proxmox-realm", "pam")
    proxmox_verify_tls = meta.get("proxmox-verify-tls", "1")
    moonlight_host = (
        stream_meta.get("moonlight-host")
        or stream_meta.get("sunshine-host")
        or stream_meta.get("sunshine-ip")
        or ""
    )
    sunshine_api_url = stream_meta.get("sunshine-api-url") or (
        f"https://{moonlight_host}:47990" if moonlight_host else ""
    )
    moonlight_resolution = (stream_meta.get("moonlight-resolution") or "").strip()
    if not moonlight_resolution or moonlight_resolution in {"1080", "native", "auto"}:
        moonlight_resolution = "auto"

    preset = {
        "PVE_THIN_CLIENT_PRESET_PROFILE_NAME": f"vm-{vmid}",
        "PVE_THIN_CLIENT_PRESET_VM_NAME": vm_name,
        "PVE_THIN_CLIENT_PRESET_HOSTNAME_VALUE": _legacy_safe_hostname(vm_name, vmid),
        "PVE_THIN_CLIENT_PRESET_AUTOSTART": meta.get("thinclient-autostart", "1"),
        "PVE_THIN_CLIENT_PRESET_DEFAULT_MODE": "MOONLIGHT" if moonlight_host else "",
        "PVE_THIN_CLIENT_PRESET_NETWORK_MODE": meta.get("thinclient-network-mode", "dhcp"),
        "PVE_THIN_CLIENT_PRESET_NETWORK_INTERFACE": meta.get("thinclient-network-interface", "eth0"),
        "PVE_THIN_CLIENT_PRESET_PROXMOX_SCHEME": proxmox_scheme,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_HOST": proxmox_host,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_PORT": proxmox_port,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_NODE": str(vm.get("node") or ""),
        "PVE_THIN_CLIENT_PRESET_PROXMOX_VMID": str(vmid),
        "PVE_THIN_CLIENT_PRESET_PROXMOX_REALM": proxmox_realm,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_VERIFY_TLS": proxmox_verify_tls,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_USERNAME": "",
        "PVE_THIN_CLIENT_PRESET_PROXMOX_PASSWORD": "",
        "PVE_THIN_CLIENT_PRESET_PROXMOX_TOKEN": "",
        "PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_URL": str(beagle_manager_url or ""),
        "PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_TOKEN": "",
        "PVE_THIN_CLIENT_PRESET_SPICE_METHOD": "",
        "PVE_THIN_CLIENT_PRESET_SPICE_URL": "",
        "PVE_THIN_CLIENT_PRESET_SPICE_USERNAME": "",
        "PVE_THIN_CLIENT_PRESET_SPICE_PASSWORD": "",
        "PVE_THIN_CLIENT_PRESET_SPICE_TOKEN": "",
        "PVE_THIN_CLIENT_PRESET_NOVNC_URL": "",
        "PVE_THIN_CLIENT_PRESET_NOVNC_USERNAME": "",
        "PVE_THIN_CLIENT_PRESET_NOVNC_PASSWORD": "",
        "PVE_THIN_CLIENT_PRESET_NOVNC_TOKEN": "",
        "PVE_THIN_CLIENT_PRESET_DCV_URL": "",
        "PVE_THIN_CLIENT_PRESET_DCV_USERNAME": "",
        "PVE_THIN_CLIENT_PRESET_DCV_PASSWORD": "",
        "PVE_THIN_CLIENT_PRESET_DCV_TOKEN": "",
        "PVE_THIN_CLIENT_PRESET_DCV_SESSION": "",
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_HOST": moonlight_host,
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_APP": stream_meta.get(
            "moonlight-app",
            stream_meta.get("sunshine-app", "Desktop"),
        ),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_BIN": stream_meta.get("moonlight-bin", "moonlight"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_RESOLUTION": moonlight_resolution,
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_FPS": stream_meta.get("moonlight-fps", "60"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_BITRATE": stream_meta.get("moonlight-bitrate", "20000"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_VIDEO_CODEC": stream_meta.get("moonlight-video-codec", "H.264"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_VIDEO_DECODER": stream_meta.get("moonlight-video-decoder", "auto"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_AUDIO_CONFIG": stream_meta.get("moonlight-audio-config", "stereo"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_ABSOLUTE_MOUSE": stream_meta.get("moonlight-absolute-mouse", "1"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_QUIT_AFTER": stream_meta.get("moonlight-quit-after", "0"),
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_API_URL": sunshine_api_url,
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_USERNAME": "",
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_PASSWORD": "",
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_PIN": "",
    }
    available_modes = ["MOONLIGHT"] if preset["PVE_THIN_CLIENT_PRESET_MOONLIGHT_HOST"] else []
    preset["PVE_THIN_CLIENT_PRESET_DEFAULT_MODE"] = "MOONLIGHT" if available_modes else ""
    preset_name = preset.get("PVE_THIN_CLIENT_PRESET_PROFILE_NAME") or f"vm-{vmid}"
    _ = _encode_preset(preset)

    profile_contract = normalize_endpoint_profile_contract(
        {
            "installer_url": f"/beagle-api/api/v1/vms/{vmid}/installer.sh",
            "live_usb_url": f"/beagle-api/api/v1/vms/{vmid}/live-usb.sh",
            "installer_windows_url": f"/beagle-api/api/v1/vms/{vmid}/installer.ps1",
            "live_usb_windows_url": f"/beagle-api/api/v1/vms/{vmid}/live-usb.ps1",
            "installer_iso_url": installer_iso_url,
            "stream_host": preset.get("PVE_THIN_CLIENT_PRESET_MOONLIGHT_HOST", ""),
            "sunshine_api_url": preset.get("PVE_THIN_CLIENT_PRESET_SUNSHINE_API_URL", ""),
            "expected_profile_name": preset_name,
        },
        vmid=vmid,
        installer_iso_url=installer_iso_url,
    )

    return {
        "vmid": vmid,
        "node": str(vm.get("node") or ""),
        "name": preset["PVE_THIN_CLIENT_PRESET_VM_NAME"],
        "preset_name": preset_name,
        "default_mode": preset.get("PVE_THIN_CLIENT_PRESET_DEFAULT_MODE", ""),
        "installer_filename": "",
        "installer_url": profile_contract["installer_url"],
        "live_usb_filename": "",
        "live_usb_url": profile_contract["live_usb_url"],
        "installer_windows_filename": "",
        "installer_windows_url": profile_contract["installer_windows_url"],
        "live_usb_windows_filename": "",
        "live_usb_windows_url": profile_contract["live_usb_windows_url"],
        "installer_iso_url": profile_contract["installer_iso_url"],
        "available_modes": available_modes,
    }


def generate_vm_installers_metadata(
    *,
    provider_module_path: Path,
    metadata_path: Path,
    server_name: str,
    installer_iso_url: str,
    default_proxmox_username: str,
    default_proxmox_password: str,
    default_proxmox_token: str,
    beagle_manager_url: str,
) -> None:
    provider_module = _load_provider_module(provider_module_path)
    metadata_support = MetadataSupportService()
    resources = provider_module.list_vms()
    config_cache: dict[tuple[str, int], dict[str, Any]] = {}

    if not isinstance(resources, list) or not resources:
        metadata_path.write_text("[]\n", encoding="utf-8")
        return

    def load_vm_config(node: str, vmid: int) -> dict[str, Any]:
        key = (str(node or ""), int(vmid))
        if key not in config_cache:
            payload = provider_module.vm_config(key[0], key[1]) or {}
            config_cache[key] = payload if isinstance(payload, dict) else {}
        return config_cache[key]

    vm_installers: list[dict[str, Any]] = []
    for vm in resources:
        if not isinstance(vm, dict):
            continue
        if vm.get("type") != "qemu" or vm.get("vmid") is None or not vm.get("node"):
            continue
        config = load_vm_config(str(vm["node"]), int(vm["vmid"]))
        vm_installers.append(
            _build_vm_catalog_entry(
                vm=vm,
                config=config,
                load_vm_config=load_vm_config,
                metadata_support=metadata_support,
                server_name=server_name,
                installer_iso_url=installer_iso_url,
                default_proxmox_username=default_proxmox_username,
                default_proxmox_password=default_proxmox_password,
                default_proxmox_token=default_proxmox_token,
                beagle_manager_url=beagle_manager_url,
            )
        )

    metadata_path.write_text(
        json.dumps(sorted(vm_installers, key=lambda item: item["vmid"]), indent=2) + "\n",
        encoding="utf-8",
    )


def write_download_status(
    *,
    status_path: Path,
    version: str,
    server_name: str,
    listen_port: int,
    downloads_path: str,
    installer_url: str,
    live_usb_url: str,
    installer_windows_url: str,
    live_usb_windows_url: str,
    bootstrap_url: str,
    payload_url: str,
    installer_iso_url: str,
    server_installer_iso_url: str,
    server_installimage_url: str,
    status_url: str,
    sha256sums_url: str,
    installer_path: Path,
    live_usb_path: Path,
    installer_windows_path: Path,
    live_usb_windows_path: Path,
    bootstrap_path: Path,
    payload_path: Path,
    installer_iso_path: Path,
    server_installer_iso_path: Path,
    server_installimage_path: Path,
    installer_sha256: str,
    bootstrap_sha256: str,
    payload_sha256: str,
    installer_iso_sha256: str,
    server_installer_iso_sha256: str,
    server_installimage_sha256: str,
    vm_installer_url_template: str,
    vm_windows_installer_url_template: str,
    vm_windows_live_usb_url_template: str,
    vm_live_usb_url_template: str,
    vm_installers_path: Path,
) -> None:
    vm_installers = json.loads(vm_installers_path.read_text(encoding="utf-8")) if vm_installers_path.exists() else []
    payload = {
        "version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "server_name": server_name,
        "listen_port": int(listen_port),
        "downloads_path": downloads_path,
        "installer_url": installer_url,
        "live_usb_url": live_usb_url,
        "installer_windows_url": installer_windows_url,
        "live_usb_windows_url": live_usb_windows_url,
        "installer_iso_url": installer_iso_url,
        "bootstrap_url": bootstrap_url,
        "payload_url": payload_url,
        "status_url": status_url,
        "sha256sums_url": sha256sums_url,
        "installer_size": installer_path.stat().st_size,
        "live_usb_size": live_usb_path.stat().st_size,
        "installer_windows_size": installer_windows_path.stat().st_size,
        "live_usb_windows_size": live_usb_windows_path.stat().st_size,
        "bootstrap_size": bootstrap_path.stat().st_size,
        "payload_size": payload_path.stat().st_size,
        "installer_iso_size": installer_iso_path.stat().st_size,
        "server_installer_iso_size": server_installer_iso_path.stat().st_size,
        "server_installimage_size": server_installimage_path.stat().st_size,
        "installer_sha256": installer_sha256,
        "bootstrap_sha256": bootstrap_sha256,
        "payload_sha256": payload_sha256,
        "installer_iso_sha256": installer_iso_sha256,
        "server_installer_iso_sha256": server_installer_iso_sha256,
        "server_installimage_sha256": server_installimage_sha256,
        "installer_filename": installer_path.name,
        "live_usb_filename": live_usb_path.name,
        "installer_windows_filename": installer_windows_path.name,
        "live_usb_windows_filename": live_usb_windows_path.name,
        "installer_iso_filename": installer_iso_path.name,
        "server_installer_iso_filename": server_installer_iso_path.name,
        "server_installimage_filename": server_installimage_path.name,
        "bootstrap_filename": bootstrap_path.name,
        "payload_filename": payload_path.name,
        "server_installer_iso_url": server_installer_iso_url,
        "server_installimage_url": server_installimage_url,
        "vm_installer_url_template": vm_installer_url_template,
        "vm_windows_installer_url_template": vm_windows_installer_url_template,
        "vm_windows_live_usb_url_template": vm_windows_live_usb_url_template,
        "vm_live_usb_url_template": vm_live_usb_url_template,
        "vm_installer_count": len(vm_installers),
        "vm_installers": vm_installers,
    }
    status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Helper seams for prepare-host-downloads.sh")
    subparsers = parser.add_subparsers(dest="command", required=True)

    patch_shell_parser = subparsers.add_parser("patch-host-shell-template")
    patch_shell_parser.add_argument("--path", required=True)
    patch_shell_parser.add_argument("--writer-variant", required=True)
    patch_shell_parser.add_argument("--installer-iso-url", required=True)
    patch_shell_parser.add_argument("--installer-bootstrap-url", required=True)
    patch_shell_parser.add_argument("--installer-payload-url", required=True)

    patch_windows_parser = subparsers.add_parser("patch-host-windows-template")
    patch_windows_parser.add_argument("--path", required=True)
    patch_windows_parser.add_argument("--installer-iso-url", required=True)
    patch_windows_parser.add_argument("--writer-variant", required=True)

    metadata_parser = subparsers.add_parser("generate-vm-installers-metadata")
    metadata_parser.add_argument("--provider-module-path", required=True)
    metadata_parser.add_argument("--metadata-path", required=True)
    metadata_parser.add_argument("--server-name", required=True)
    metadata_parser.add_argument("--installer-iso-url", required=True)
    metadata_parser.add_argument("--default-proxmox-username", default="")
    metadata_parser.add_argument("--default-proxmox-password", default="")
    metadata_parser.add_argument("--default-proxmox-token", default="")
    metadata_parser.add_argument("--beagle-manager-url", default="")

    status_parser = subparsers.add_parser("write-download-status")
    status_parser.add_argument("--status-path", required=True)
    status_parser.add_argument("--version", required=True)
    status_parser.add_argument("--server-name", required=True)
    status_parser.add_argument("--listen-port", required=True, type=int)
    status_parser.add_argument("--downloads-path", required=True)
    status_parser.add_argument("--installer-url", required=True)
    status_parser.add_argument("--live-usb-url", required=True)
    status_parser.add_argument("--installer-windows-url", required=True)
    status_parser.add_argument("--live-usb-windows-url", required=True)
    status_parser.add_argument("--bootstrap-url", required=True)
    status_parser.add_argument("--payload-url", required=True)
    status_parser.add_argument("--installer-iso-url", required=True)
    status_parser.add_argument("--server-installer-iso-url", required=True)
    status_parser.add_argument("--server-installimage-url", required=True)
    status_parser.add_argument("--status-url", required=True)
    status_parser.add_argument("--sha256sums-url", required=True)
    status_parser.add_argument("--installer-path", required=True)
    status_parser.add_argument("--live-usb-path", required=True)
    status_parser.add_argument("--installer-windows-path", required=True)
    status_parser.add_argument("--live-usb-windows-path", required=True)
    status_parser.add_argument("--bootstrap-path", required=True)
    status_parser.add_argument("--payload-path", required=True)
    status_parser.add_argument("--installer-iso-path", required=True)
    status_parser.add_argument("--server-installer-iso-path", required=True)
    status_parser.add_argument("--server-installimage-path", required=True)
    status_parser.add_argument("--installer-sha256", required=True)
    status_parser.add_argument("--bootstrap-sha256", required=True)
    status_parser.add_argument("--payload-sha256", required=True)
    status_parser.add_argument("--installer-iso-sha256", required=True)
    status_parser.add_argument("--server-installer-iso-sha256", required=True)
    status_parser.add_argument("--server-installimage-sha256", required=True)
    status_parser.add_argument("--vm-installer-url-template", required=True)
    status_parser.add_argument("--vm-windows-installer-url-template", required=True)
    status_parser.add_argument("--vm-windows-live-usb-url-template", required=True)
    status_parser.add_argument("--vm-live-usb-url-template", required=True)
    status_parser.add_argument("--vm-installers-path", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "patch-host-shell-template":
        patch_host_shell_template(
            path=Path(args.path),
            writer_variant=args.writer_variant,
            installer_iso_url=args.installer_iso_url,
            installer_bootstrap_url=args.installer_bootstrap_url,
            installer_payload_url=args.installer_payload_url,
        )
        return 0

    if args.command == "patch-host-windows-template":
        patch_host_windows_template(
            path=Path(args.path),
            installer_iso_url=args.installer_iso_url,
            writer_variant=args.writer_variant,
        )
        return 0

    if args.command == "generate-vm-installers-metadata":
        generate_vm_installers_metadata(
            provider_module_path=Path(args.provider_module_path),
            metadata_path=Path(args.metadata_path),
            server_name=args.server_name,
            installer_iso_url=args.installer_iso_url,
            default_proxmox_username=args.default_proxmox_username,
            default_proxmox_password=args.default_proxmox_password,
            default_proxmox_token=args.default_proxmox_token,
            beagle_manager_url=args.beagle_manager_url,
        )
        return 0

    if args.command == "write-download-status":
        write_download_status(
            status_path=Path(args.status_path),
            version=args.version,
            server_name=args.server_name,
            listen_port=args.listen_port,
            downloads_path=args.downloads_path,
            installer_url=args.installer_url,
            live_usb_url=args.live_usb_url,
            installer_windows_url=args.installer_windows_url,
            live_usb_windows_url=args.live_usb_windows_url,
            bootstrap_url=args.bootstrap_url,
            payload_url=args.payload_url,
            installer_iso_url=args.installer_iso_url,
            server_installer_iso_url=args.server_installer_iso_url,
            server_installimage_url=args.server_installimage_url,
            status_url=args.status_url,
            sha256sums_url=args.sha256sums_url,
            installer_path=Path(args.installer_path),
            live_usb_path=Path(args.live_usb_path),
            installer_windows_path=Path(args.installer_windows_path),
            live_usb_windows_path=Path(args.live_usb_windows_path),
            bootstrap_path=Path(args.bootstrap_path),
            payload_path=Path(args.payload_path),
            installer_iso_path=Path(args.installer_iso_path),
            server_installer_iso_path=Path(args.server_installer_iso_path),
            server_installimage_path=Path(args.server_installimage_path),
            installer_sha256=args.installer_sha256,
            bootstrap_sha256=args.bootstrap_sha256,
            payload_sha256=args.payload_sha256,
            installer_iso_sha256=args.installer_iso_sha256,
            server_installer_iso_sha256=args.server_installer_iso_sha256,
            server_installimage_sha256=args.server_installimage_sha256,
            vm_installer_url_template=args.vm_installer_url_template,
            vm_windows_installer_url_template=args.vm_windows_installer_url_template,
            vm_windows_live_usb_url_template=args.vm_windows_live_usb_url_template,
            vm_live_usb_url_template=args.vm_live_usb_url_template,
            vm_installers_path=Path(args.vm_installers_path),
        )
        return 0

    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
