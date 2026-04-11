#!/usr/bin/env python3
"""Provider-neutral script helper for host-side virtualization reads.

This module gives shell scripts and inline Python a single import/CLI seam for
provider-backed VM inventory, config, and guest-interface reads. Proxmox is the
first implementation behind the seam; new script logic should call this helper
instead of embedding raw `pvesh` / `qm guest cmd` calls directly.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any


def provider_kind() -> str:
    kind = str(os.environ.get("BEAGLE_HOST_PROVIDER", "proxmox") or "").strip().lower()
    if kind == "pve":
        return "proxmox"
    return kind or "proxmox"


def run_json(command: list[str]) -> Any:
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError:
        return None


def _require_supported_provider() -> str:
    kind = provider_kind()
    if kind != "proxmox":
        raise SystemExit(f"unsupported host provider for script helper: {kind}")
    return kind


def list_vms() -> list[dict[str, Any]]:
    _require_supported_provider()
    payload = run_json(["pvesh", "get", "/cluster/resources", "--type", "vm", "--output-format", "json"])
    return payload if isinstance(payload, list) else []


def vm_config(node: str, vmid: int) -> dict[str, Any]:
    _require_supported_provider()
    payload = run_json(
        ["pvesh", "get", f"/nodes/{str(node or '').strip()}/qemu/{int(vmid)}/config", "--output-format", "json"]
    )
    return payload if isinstance(payload, dict) else {}


def guest_interfaces(vmid: int) -> list[dict[str, Any]]:
    _require_supported_provider()
    payload = run_json(["qm", "guest", "cmd", str(int(vmid)), "network-get-interfaces"])
    return payload if isinstance(payload, list) else []


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit("usage: beagle_provider.py <list-vms|vm-config|guest-interfaces> [args]")
    command = argv[1]
    if command == "list-vms":
        print(json.dumps(list_vms(), indent=2))
        return 0
    if command == "vm-config":
        if len(argv) != 4:
            raise SystemExit("usage: beagle_provider.py vm-config <node> <vmid>")
        print(json.dumps(vm_config(argv[2], int(argv[3])), indent=2))
        return 0
    if command == "guest-interfaces":
        if len(argv) != 3:
            raise SystemExit("usage: beagle_provider.py guest-interfaces <vmid>")
        print(json.dumps(guest_interfaces(int(argv[2])), indent=2))
        return 0
    raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
