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


def parse_description_meta(description: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    text = str(description or "").replace("\\r\\n", "\n").replace("\\n", "\n")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key and key not in meta:
            meta[key] = value
    return meta


def find_vm_record(vmid: int) -> dict[str, Any] | None:
    target_vmid = int(vmid)
    for item in list_vms():
        if item.get("type") != "qemu" or item.get("vmid") is None:
            continue
        try:
            candidate_vmid = int(item.get("vmid"))
        except (TypeError, ValueError):
            continue
        if candidate_vmid == target_vmid:
            return item
    return None


def vm_description_meta(node: str, vmid: int) -> dict[str, str]:
    return parse_description_meta(vm_config(node, vmid).get("description", ""))


def vm_description_meta_for_vmid(vmid: int) -> dict[str, str]:
    record = find_vm_record(vmid)
    if not isinstance(record, dict):
        return {}
    node = str(record.get("node") or "").strip()
    if not node:
        return {}
    return vm_description_meta(node, int(vmid))


def first_guest_ipv4(vmid: int) -> str:
    for iface in guest_interfaces(vmid):
        for address in iface.get("ip-addresses", []):
            ip = str(address.get("ip-address", ""))
            if address.get("ip-address-type") != "ipv4":
                continue
            if not ip or ip.startswith("127.") or ip.startswith("169.254."):
                continue
            return ip
    return ""


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit(
            "usage: beagle_provider.py <list-vms|vm-config|guest-interfaces|guest-ipv4|vm-description-meta> [args]"
        )
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
    if command == "guest-ipv4":
        if len(argv) != 3:
            raise SystemExit("usage: beagle_provider.py guest-ipv4 <vmid>")
        print(first_guest_ipv4(int(argv[2])))
        return 0
    if command == "vm-description-meta":
        if len(argv) == 4:
            print(json.dumps(vm_description_meta(argv[2], int(argv[3])), indent=2))
            return 0
        if len(argv) == 3:
            print(json.dumps(vm_description_meta_for_vmid(int(argv[2])), indent=2))
            return 0
        raise SystemExit("usage: beagle_provider.py vm-description-meta <vmid> | <node> <vmid>")
    raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
