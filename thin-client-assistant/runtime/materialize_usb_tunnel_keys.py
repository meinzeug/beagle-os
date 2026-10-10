#!/usr/bin/env python3
"""Restore VM-specific SSH files from protected installer credentials.

Never replace keys installed by enrollment. Base64 is transport encoding, not
protection: the containing credentials file must retain its restricted mode.
"""

from __future__ import annotations

import base64
import os
import shlex
import sys
from pathlib import Path


def materialize_keys(credentials: Path, target: Path) -> None:
    values: dict[str, str] = {}
    for line in credentials.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        if key in {
            "PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PRIVATE_KEY_B64",
            "PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_KNOWN_HOST_B64",
        }:
            parts = shlex.split(value)
            values[key] = parts[0] if len(parts) == 1 else ""
    files = []
    for suffix, name, mode in (
        ("PRIVATE_KEY_B64", "usb-tunnel.key", 0o600),
        ("KNOWN_HOST_B64", "usb-tunnel-known_hosts", 0o644),
    ):
        encoded = values.get("PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_" + suffix, "")
        if not encoded:
            continue
        if len(encoded) > 131072:
            raise ValueError("Oversized SSH provisioning data")
        content = base64.b64decode(encoded, validate=True)
        if not content or b"\x00" in content:
            raise ValueError("Invalid SSH provisioning data")
        files.append((name, content, mode))
    if files:
        target.mkdir(parents=True, exist_ok=True, mode=0o755)
    for name, content, mode in files:
        try:
            fd = os.open(target / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        except FileExistsError:
            continue
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)


if __name__ == "__main__":
    try:
        materialize_keys(Path(sys.argv[1]) / "credentials.env", Path(sys.argv[2]))
    except (OSError, ValueError):
        print(
            "Unable to restore USB tunnel SSH files; check protected preset credentials and permissions.",
            file=sys.stderr,
        )
        raise SystemExit(1)
