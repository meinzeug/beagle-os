#!/usr/bin/env python3
"""Resolve runtime mode overrides from cmdline and current runtime env."""

from __future__ import annotations

import argparse
from pathlib import Path


def cmdline_var(*, key: str, cmdline_text: str) -> str:
    wanted = str(key or "").strip()
    if not wanted:
        return ""
    for token in str(cmdline_text or "").split():
        if token.startswith(f"{wanted}="):
            return token.split("=", 1)[1]
    return ""


def resolve_runtime_mode_overrides(
    *,
    current_mode: str,
    current_boot_profile: str,
    current_client_mode: str,
    requested_mode: str,
) -> dict[str, str]:
    requested = str(requested_mode or "").strip().lower()
    client_mode = requested or str(current_client_mode or "").strip()
    mode = str(current_mode or "MOONLIGHT").strip() or "MOONLIGHT"
    boot_profile = str(current_boot_profile or "").strip()

    if requested in {"desktop", "moonlight"}:
        mode = "MOONLIGHT"
        boot_profile = "desktop"
    elif requested in {"gaming", "kiosk"}:
        mode = "KIOSK"
        boot_profile = "gaming"
    elif requested in {"gfn", "geforcenow", "geforce-now"}:
        mode = "GFN"
        boot_profile = "gaming"

    if mode in {"GFN", "KIOSK"}:
        boot_profile = boot_profile or "gaming"
    else:
        boot_profile = boot_profile or "desktop"

    return {
        "PVE_THIN_CLIENT_CLIENT_MODE": client_mode,
        "PVE_THIN_CLIENT_MODE": mode,
        "PVE_THIN_CLIENT_BOOT_PROFILE": boot_profile,
    }


def shell_exports(*, cmdline_file: Path, current_mode: str, current_boot_profile: str, current_client_mode: str) -> str:
    cmdline_text = cmdline_file.read_text(encoding="utf-8").strip() if cmdline_file.is_file() else ""
    payload = resolve_runtime_mode_overrides(
        current_mode=current_mode,
        current_boot_profile=current_boot_profile,
        current_client_mode=current_client_mode,
        requested_mode=cmdline_var(key="pve_thin_client.client_mode", cmdline_text=cmdline_text),
    )
    lines = [f"{key}\t{value}" for key, value in payload.items()]
    return "\n".join(lines) + ("\n" if lines else "")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve Beagle thin-client runtime mode overrides")
    parser.add_argument("--cmdline-file", default="/proc/cmdline")
    parser.add_argument("--current-mode", default="")
    parser.add_argument("--current-boot-profile", default="")
    parser.add_argument("--current-client-mode", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        shell_exports(
            cmdline_file=Path(args.cmdline_file),
            current_mode=args.current_mode,
            current_boot_profile=args.current_boot_profile,
            current_client_mode=args.current_client_mode,
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
