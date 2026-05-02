#!/usr/bin/env python3
"""Shared preset summary helpers for thin-client USB installer surfaces."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from typing import Any

STREAMING_MODES = ("BEAGLE_STREAM_CLIENT", "SPICE", "NOVNC", "DCV")


def _string(value: Any) -> str:
    return str(value or "")


def mode_available(name: str, preset: dict[str, Any]) -> bool:
    mode = str(name or "").strip().upper()
    if mode == "BEAGLE_STREAM_CLIENT":
        return bool(_string(preset.get("beagle_stream_client_host")))
    if mode == "SPICE":
        return bool(_string(preset.get("spice_url"))) or (
            bool(_string(preset.get("beagle_host")))
            and bool(_string(preset.get("beagle_node")))
            and bool(_string(preset.get("beagle_vmid")))
            and bool(_string(preset.get("spice_username")) or _string(preset.get("beagle_username")))
            and bool(_string(preset.get("spice_password")) or _string(preset.get("beagle_password")))
        )
    if mode == "NOVNC":
        return bool(_string(preset.get("novnc_url")))
    if mode == "DCV":
        return bool(_string(preset.get("dcv_url")))
    return False


def available_modes(preset: dict[str, Any]) -> list[str]:
    return [name for name in STREAMING_MODES if mode_available(name, preset)]


def build_preset_summary(
    *,
    preset_active: bool,
    vm_name: str,
    profile_name: str,
    beagle_host: str,
    beagle_node: str,
    beagle_vmid: str,
    spice_url: str,
    beagle_username: str,
    beagle_password: str,
    spice_username: str,
    spice_password: str,
    novnc_url: str,
    dcv_url: str,
    beagle_stream_client_host: str,
    default_mode: str,
    beagle_stream_client_app: str,
) -> dict[str, Any]:
    raw = {
        "preset_active": bool(preset_active),
        "vm_name": _string(vm_name),
        "profile_name": _string(profile_name),
        "beagle_host": _string(beagle_host),
        "beagle_node": _string(beagle_node),
        "beagle_vmid": _string(beagle_vmid),
        "spice_url": _string(spice_url),
        "beagle_username": _string(beagle_username),
        "beagle_password": _string(beagle_password),
        "spice_username": _string(spice_username),
        "spice_password": _string(spice_password),
        "novnc_url": _string(novnc_url),
        "dcv_url": _string(dcv_url),
        "beagle_stream_client_host": _string(beagle_stream_client_host),
        "default_mode": _string(default_mode),
        "beagle_stream_client_app": _string(beagle_stream_client_app),
    }
    return {
        "preset_active": raw["preset_active"],
        "vm_name": raw["vm_name"],
        "profile_name": raw["profile_name"],
        "beagle_host": raw["beagle_host"],
        "beagle_node": raw["beagle_node"],
        "beagle_vmid": raw["beagle_vmid"],
        "beagle_stream_client_host": raw["beagle_stream_client_host"],
        "beagle_stream_client_app": raw["beagle_stream_client_app"],
        "default_mode": raw["default_mode"],
        "available_modes": available_modes(raw),
    }


def list_target_disks(*, live_disk: str) -> list[dict[str, str]]:
    disks: list[dict[str, str]] = []
    try:
        output = subprocess.check_output(
            ["lsblk", "-dn", "-P", "-o", "NAME,SIZE,MODEL,TYPE,RM,TRAN"],
            text=True,
        )
        for line in output.splitlines():
            entry: dict[str, str] = {}
            for token in shlex.split(line):
                key, value = token.split("=", 1)
                entry[key] = value
            if entry.get("TYPE") != "disk":
                continue
            device = f"/dev/{entry['NAME']}"
            if device == str(live_disk or ""):
                continue
            if any(device.startswith(prefix) for prefix in ("/dev/loop", "/dev/sr", "/dev/ram", "/dev/zram")):
                continue
            disks.append(
                {
                    "device": device,
                    "size": entry.get("SIZE", "unknown"),
                    "model": entry.get("MODEL", "disk"),
                    "removable": entry.get("RM", "0"),
                    "transport": entry.get("TRAN", ""),
                }
            )
    except Exception as exc:  # noqa: BLE001
        return [{"device": "", "size": "", "model": f"lsblk failed: {exc}", "removable": "0", "transport": ""}]
    return disks


def build_debug_payload(
    *,
    preset_active: bool,
    live_medium_default: str,
    live_medium: str,
    live_asset_dir: str,
    preset_file: str,
    log_file: str,
    log_dir: str,
    preset_source: str,
    cached_preset_file: str,
    cached_preset_source: str,
    live_disk: str,
    log_session_id: str,
) -> dict[str, Any]:
    return {
        "preset_active": bool(preset_active),
        "live_medium_default": _string(live_medium_default),
        "live_medium": _string(live_medium),
        "live_asset_dir": _string(live_asset_dir),
        "preset_file": _string(preset_file),
        "preset_exists": bool(preset_file and os.path.isfile(str(preset_file))),
        "log_file": _string(log_file),
        "log_exists": bool(log_file and os.path.isfile(str(log_file))),
        "log_dir": _string(log_dir),
        "log_dir_exists": bool(log_dir and os.path.isdir(str(log_dir))),
        "preset_source": _string(preset_source),
        "cached_preset_file": _string(cached_preset_file),
        "cached_preset_exists": bool(cached_preset_file and os.path.isfile(str(cached_preset_file))),
        "cached_preset_source": _string(cached_preset_source),
        "live_disk": _string(live_disk),
        "log_session_id": _string(log_session_id),
    }


def build_ui_state_payload(
    *,
    preset_summary: dict[str, Any],
    debug_payload: dict[str, Any],
    live_disk: str,
) -> dict[str, Any]:
    return {
        "ok": True,
        "preset": preset_summary,
        "debug": debug_payload,
        "disks": list_target_disks(live_disk=live_disk),
        "log_dir": _string(debug_payload.get("log_dir")),
    }


def _bool_arg(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _add_preset_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--preset-active", default="0")
    parser.add_argument("--vm-name", default="")
    parser.add_argument("--profile-name", default="")
    parser.add_argument("--beagle-host", default="")
    parser.add_argument("--beagle-node", default="")
    parser.add_argument("--beagle-vmid", default="")
    parser.add_argument("--spice-url", default="")
    parser.add_argument("--beagle-username", default="")
    parser.add_argument("--beagle-password", default="")
    parser.add_argument("--spice-username", default="")
    parser.add_argument("--spice-password", default="")
    parser.add_argument("--novnc-url", default="")
    parser.add_argument("--dcv-url", default="")
    parser.add_argument("--beagle-stream-client-host", default="")
    parser.add_argument("--default-mode", default="")
    parser.add_argument("--beagle-stream-client-app", default="Desktop")


def _summary_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return build_preset_summary(
        preset_active=_bool_arg(args.preset_active),
        vm_name=args.vm_name,
        profile_name=args.profile_name,
        beagle_host=args.beagle_host,
        beagle_node=args.beagle_node,
        beagle_vmid=args.beagle_vmid,
        spice_url=args.spice_url,
        beagle_username=args.beagle_username,
        beagle_password=args.beagle_password,
        spice_username=args.spice_username,
        spice_password=args.spice_password,
        novnc_url=args.novnc_url,
        dcv_url=args.dcv_url,
        beagle_stream_client_host=args.beagle_stream_client_host,
        default_mode=args.default_mode,
        beagle_stream_client_app=args.beagle_stream_client_app,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Shared USB preset summary helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser("preset-summary-json")
    _add_preset_args(summary_parser)

    ui_state_parser = subparsers.add_parser("ui-state-json")
    _add_preset_args(ui_state_parser)
    ui_state_parser.add_argument("--live-medium-default", default="")
    ui_state_parser.add_argument("--live-medium", default="")
    ui_state_parser.add_argument("--live-asset-dir", default="")
    ui_state_parser.add_argument("--preset-file", default="")
    ui_state_parser.add_argument("--log-file", default="")
    ui_state_parser.add_argument("--log-dir", default="")
    ui_state_parser.add_argument("--preset-source", default="")
    ui_state_parser.add_argument("--cached-preset-file", default="")
    ui_state_parser.add_argument("--cached-preset-source", default="")
    ui_state_parser.add_argument("--live-disk", default="")
    ui_state_parser.add_argument("--log-session-id", default="")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "preset-summary-json":
        print(json.dumps(_summary_from_args(args), indent=2))
        return 0
    if args.command == "ui-state-json":
        summary = _summary_from_args(args)
        debug_payload = build_debug_payload(
            preset_active=_bool_arg(args.preset_active),
            live_medium_default=args.live_medium_default,
            live_medium=args.live_medium,
            live_asset_dir=args.live_asset_dir,
            preset_file=args.preset_file,
            log_file=args.log_file,
            log_dir=args.log_dir,
            preset_source=args.preset_source,
            cached_preset_file=args.cached_preset_file,
            cached_preset_source=args.cached_preset_source,
            live_disk=args.live_disk,
            log_session_id=args.log_session_id,
        )
        print(json.dumps(build_ui_state_payload(preset_summary=summary, debug_payload=debug_payload, live_disk=args.live_disk), indent=2))
        return 0
    parser.error(f"unsupported command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
