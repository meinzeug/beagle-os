#!/usr/bin/env python3
"""Resolve runtime config dirs and preset restore paths for Beagle thin-client."""

from __future__ import annotations

import argparse
import base64
import gzip
import re
import subprocess
from pathlib import Path

from generate_config_from_preset import generate_config_dir_from_preset


def find_live_state_dir(*, live_state_dir: str, live_state_dir_default: str) -> str:
    candidates = [
        str(live_state_dir or ""),
        str(live_state_dir_default or ""),
        "/lib/live/mount/medium/pve-thin-client/state",
    ]
    for candidate in candidates:
        candidate = candidate.strip()
        if candidate and (Path(candidate) / "thinclient.conf").is_file():
            return candidate

    try:
        output = subprocess.check_output(["findmnt", "-rn", "-o", "TARGET"], text=True)
    except Exception:  # noqa: BLE001
        return ""

    for raw_line in output.splitlines():
        target = str(raw_line or "").strip()
        if not target:
            continue
        candidate = Path(target) / "pve-thin-client" / "state"
        if (candidate / "thinclient.conf").is_file():
            return str(candidate)
    return ""


def find_preset_file(*, preset_file: str, live_preset_file_default: str) -> str:
    candidates = [
        str(preset_file or ""),
        str(live_preset_file_default or ""),
        "/run/live/medium/pve-thin-client/live/preset.env",
        "/lib/live/mount/medium/pve-thin-client/preset.env",
        "/lib/live/mount/medium/pve-thin-client/live/preset.env",
    ]
    for candidate in candidates:
        candidate = candidate.strip()
        if candidate and Path(candidate).is_file():
            return candidate
    return ""


def restore_preset_from_cmdline(*, target_file: Path, cmdline_file: Path) -> bool:
    if not target_file:
        return False
    cmdline = cmdline_file.read_text(encoding="utf-8").strip() if cmdline_file.is_file() else ""
    codec = ""
    chunks: dict[int, str] = {}

    for token in cmdline.split():
        if token.startswith("pve_thin_client.preset_codec="):
            codec = token.split("=", 1)[1]
            continue
        match = re.match(r"pve_thin_client\.preset_b64_(\d+)=([A-Za-z0-9_-]+)$", token)
        if match:
            chunks[int(match.group(1))] = match.group(2)
            continue
        if token.startswith("pve_thin_client.preset_b64="):
            chunks[0] = token.split("=", 1)[1]

    if not chunks:
        return False

    payload = "".join(chunks[index] for index in sorted(chunks))
    payload += "=" * (-len(payload) % 4)
    data = base64.urlsafe_b64decode(payload.encode("ascii"))

    if codec in {"", "base64url"}:
        decoded = data
    elif codec in {"gzip+base64url", "gz+base64url", "gzip"}:
        decoded = gzip.decompress(data)
    else:
        raise SystemExit(f"unsupported preset codec: {codec}")

    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_bytes(decoded)
    target_file.chmod(0o644)
    return True


def find_config_dir(
    *,
    config_dir: str,
    default_config_dir: str,
    live_state_dir: str,
    live_state_dir_default: str,
    preset_file: str,
    live_preset_file_default: str,
    preset_state_dir: str,
    runtime_user: str,
    installer_script: Path,
    cmdline_file: Path,
) -> str:
    candidate = Path(str(config_dir or default_config_dir or "")).expanduser()
    if candidate.is_dir() and (candidate / "thinclient.conf").is_file():
        return str(candidate)

    live_dir = find_live_state_dir(
        live_state_dir=live_state_dir,
        live_state_dir_default=live_state_dir_default,
    )
    if live_dir:
        return live_dir

    preset_candidate = find_preset_file(
        preset_file=preset_file,
        live_preset_file_default=live_preset_file_default,
    )
    if preset_candidate:
        state_dir = Path(str(preset_state_dir or "")).expanduser()
        generate_config_dir_from_preset(
            preset_file=Path(preset_candidate),
            state_dir=state_dir,
            installer_script=installer_script,
            runtime_user=runtime_user,
        )
        if (state_dir / "thinclient.conf").is_file():
            return str(state_dir)

    cmdline_preset = Path(str(preset_state_dir or "")).expanduser() / "cmdline-preset.env"
    if restore_preset_from_cmdline(target_file=cmdline_preset, cmdline_file=cmdline_file):
        state_dir = Path(str(preset_state_dir or "")).expanduser()
        generate_config_dir_from_preset(
            preset_file=cmdline_preset,
            state_dir=state_dir,
            installer_script=installer_script,
            runtime_user=runtime_user,
        )
        if (state_dir / "thinclient.conf").is_file():
            return str(state_dir)

    return ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve Beagle thin-client runtime config discovery")
    subparsers = parser.add_subparsers(dest="command", required=True)

    live_state = subparsers.add_parser("find-live-state-dir")
    live_state.add_argument("--live-state-dir", default="")
    live_state.add_argument("--live-state-dir-default", default="/run/live/medium/pve-thin-client/state")

    config_dir = subparsers.add_parser("find-config-dir")
    config_dir.add_argument("--config-dir", default="")
    config_dir.add_argument("--default-config-dir", default="/etc/pve-thin-client")
    config_dir.add_argument("--live-state-dir", default="")
    config_dir.add_argument("--live-state-dir-default", default="/run/live/medium/pve-thin-client/state")
    config_dir.add_argument("--preset-file", default="")
    config_dir.add_argument("--live-preset-file-default", default="/run/live/medium/pve-thin-client/preset.env")
    config_dir.add_argument("--preset-state-dir", required=True)
    config_dir.add_argument("--runtime-user", default="thinclient")
    config_dir.add_argument("--installer-script", required=True)
    config_dir.add_argument("--cmdline-file", default="/proc/cmdline")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "find-live-state-dir":
        result = find_live_state_dir(
            live_state_dir=args.live_state_dir,
            live_state_dir_default=args.live_state_dir_default,
        )
        if result:
            print(result)
            return 0
        return 1
    if args.command == "find-config-dir":
        result = find_config_dir(
            config_dir=args.config_dir,
            default_config_dir=args.default_config_dir,
            live_state_dir=args.live_state_dir,
            live_state_dir_default=args.live_state_dir_default,
            preset_file=args.preset_file,
            live_preset_file_default=args.live_preset_file_default,
            preset_state_dir=args.preset_state_dir,
            runtime_user=args.runtime_user,
            installer_script=Path(args.installer_script),
            cmdline_file=Path(args.cmdline_file),
        )
        if result:
            print(result)
            return 0
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
