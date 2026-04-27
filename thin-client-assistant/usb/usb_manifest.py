#!/usr/bin/env python3
"""Shared manifest helpers for thin-client USB installer surfaces."""

from __future__ import annotations

import argparse
import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest payload must be an object")
    return payload


def read_project_version(path: Path) -> str:
    payload = _read_json(path)
    value = str(payload.get("project_version", "")).strip()
    if not value:
        raise ValueError("manifest does not contain project_version")
    return value


def read_payload_source(path: Path) -> str:
    payload = _read_json(path)
    value = str(payload.get("payload_source", "")).strip()
    if not value:
        raise ValueError("manifest does not contain payload_source")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("manifest payload_source must be http(s)")
    return value


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _resolve_first_ipv4(hostname: str) -> str:
    if not hostname:
        return ""
    try:
        infos = socket.getaddrinfo(hostname, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
    except OSError:
        return ""
    for info in infos:
        candidate = info[4][0]
        if candidate:
            return candidate
    return ""


def command_read_project_version(args: argparse.Namespace) -> int:
    print(read_project_version(Path(args.path)))
    return 0


def command_read_payload_source(args: argparse.Namespace) -> int:
    print(read_payload_source(Path(args.path)))
    return 0


def command_write_install_manifest(args: argparse.Namespace) -> int:
    _write_json(
        Path(args.path),
        {
            "project": "beagle-os",
            "project_version": args.project_version,
            "installed_at": args.installed_at,
            "source_kind": args.source_kind,
            "payload_source_url": args.payload_source_url,
            "vmlinuz_sha256": args.vmlinuz_sha256,
            "initrd_sha256": args.initrd_sha256,
            "filesystem_squashfs_sha256": args.filesystem_squashfs_sha256,
            "bootstrap_manifest_version": args.bootstrap_manifest_version,
            "installed_slot": args.installed_slot,
        },
    )
    return 0


def command_write_usb_manifest(args: argparse.Namespace) -> int:
    parsed = urlparse(args.payload_source) if args.payload_source else None
    beagle_host = parsed.hostname if parsed and parsed.hostname else ""
    _write_json(
        Path(args.path),
        {
            "project_version": args.project_version,
            "usb_writer_variant": args.usb_writer_variant,
            "usb_label": args.usb_label,
            "target_device": args.target_device,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "payload_source": args.payload_source,
            "start_installer_menu_sha256": args.start_installer_menu_sha256,
            "filesystem_squashfs_sha256": args.filesystem_squashfs_sha256,
            "preset_name": args.preset_name,
            "beagle_api_scheme": "https",
            "beagle_api_host": beagle_host,
            "beagle_api_host_ip": _resolve_first_ipv4(beagle_host),
            "beagle_api_port": "8006",
            "beagle_api_verify_tls": "1",
        },
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    read_parser = subparsers.add_parser("read-project-version")
    read_parser.add_argument("--path", required=True)
    read_parser.set_defaults(func=command_read_project_version)

    payload_parser = subparsers.add_parser("read-payload-source")
    payload_parser.add_argument("--path", required=True)
    payload_parser.set_defaults(func=command_read_payload_source)

    install_parser = subparsers.add_parser("write-install-manifest")
    install_parser.add_argument("--path", required=True)
    install_parser.add_argument("--project-version", default="")
    install_parser.add_argument("--installed-at", default="")
    install_parser.add_argument("--source-kind", default="")
    install_parser.add_argument("--payload-source-url", default="")
    install_parser.add_argument("--vmlinuz-sha256", default="")
    install_parser.add_argument("--initrd-sha256", default="")
    install_parser.add_argument("--filesystem-squashfs-sha256", default="")
    install_parser.add_argument("--bootstrap-manifest-version", default="")
    install_parser.add_argument("--installed-slot", default="")
    install_parser.set_defaults(func=command_write_install_manifest)

    usb_parser = subparsers.add_parser("write-usb-manifest")
    usb_parser.add_argument("--path", required=True)
    usb_parser.add_argument("--project-version", default="")
    usb_parser.add_argument("--usb-label", default="")
    usb_parser.add_argument("--target-device", default="")
    usb_parser.add_argument("--payload-source", default="")
    usb_parser.add_argument("--start-installer-menu-sha256", default="")
    usb_parser.add_argument("--filesystem-squashfs-sha256", default="")
    usb_parser.add_argument("--preset-name", default="")
    usb_parser.add_argument("--usb-writer-variant", default="")
    usb_parser.set_defaults(func=command_write_usb_manifest)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
