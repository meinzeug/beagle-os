#!/usr/bin/env python3
"""Provider-neutral script helper for host-side virtualization access.

This module gives shell scripts and inline Python a single import/CLI seam for
provider-backed VM inventory/config reads plus the first guest-exec and VM-write
helpers. Proxmox is the first implementation behind the seam; new script logic
should call this helper instead of embedding raw `pvesh` / `qm` calls directly.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from base64 import b64decode
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


def run_checked(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout or ""


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


def vm_node(vmid: int) -> str:
    record = find_vm_record(vmid)
    if not isinstance(record, dict):
        return ""
    return str(record.get("node") or "").strip()


def vm_description_text(node: str, vmid: int) -> str:
    return str(vm_config(node, vmid).get("description", "") or "")


def vm_description_text_for_vmid(vmid: int) -> str:
    node = vm_node(vmid)
    if not node:
        return ""
    return vm_description_text(node, int(vmid))


def vm_description_meta(node: str, vmid: int) -> dict[str, str]:
    return parse_description_meta(vm_description_text(node, vmid))


def vm_description_meta_for_vmid(vmid: int) -> dict[str, str]:
    node = vm_node(vmid)
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


def guest_exec_bash(vmid: int, command: str, *, timeout_seconds: int | None = None) -> dict[str, Any]:
    _require_supported_provider()
    guest_command = ["qm", "guest", "exec", str(int(vmid))]
    if timeout_seconds is not None:
        guest_command.extend(["--timeout", str(int(timeout_seconds))])
    guest_command.extend(["--", "bash", "-lc", str(command)])
    payload = run_json(guest_command)
    return payload if isinstance(payload, dict) else {}


def guest_exec_status(vmid: int, pid: int) -> dict[str, Any]:
    _require_supported_provider()
    payload = run_json(["qm", "guest", "exec-status", str(int(vmid)), str(int(pid))])
    return payload if isinstance(payload, dict) else {}


def guest_exec_bash_sync(vmid: int, command: str, *, timeout_seconds: int | None = None) -> dict[str, Any]:
    payload = guest_exec_bash(int(vmid), command, timeout_seconds=timeout_seconds)
    pid = payload.get("pid")
    if pid in {None, ""}:
        return payload if isinstance(payload, dict) else {}
    while True:
        status = guest_exec_status(int(vmid), int(pid))
        if not isinstance(status, dict):
            return {}
        if status.get("exited"):
            return status
        time.sleep(2)


def set_vm_options(vmid: int, option_pairs: list[tuple[str, str]]) -> str:
    _require_supported_provider()
    command = ["qm", "set", str(int(vmid))]
    for key, value in option_pairs:
        flag = str(key)
        if not flag.startswith("--"):
            flag = f"--{flag}"
        command.extend([flag, str(value)])
    return run_checked(command)


def set_vm_description(vmid: int, description: str) -> str:
    _require_supported_provider()
    return run_checked(["qm", "set", str(int(vmid)), "--description", str(description)])


def reboot_vm(vmid: int) -> str:
    _require_supported_provider()
    return run_checked(["qm", "reboot", str(int(vmid))])


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit(
            "usage: beagle_provider.py <list-vms|vm-config|guest-interfaces|guest-ipv4|vm-node|vm-description|vm-description-meta|guest-exec-bash-b64|guest-exec-bash-sync-b64|guest-exec-status|set-vm-options|set-vm-description-b64|reboot-vm> [args]"
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
    if command == "vm-node":
        if len(argv) != 3:
            raise SystemExit("usage: beagle_provider.py vm-node <vmid>")
        print(vm_node(int(argv[2])))
        return 0
    if command == "vm-description":
        if len(argv) == 4:
            print(vm_description_text(argv[2], int(argv[3])))
            return 0
        if len(argv) == 3:
            print(vm_description_text_for_vmid(int(argv[2])))
            return 0
        raise SystemExit("usage: beagle_provider.py vm-description <vmid> | <node> <vmid>")
    if command == "vm-description-meta":
        if len(argv) == 4:
            print(json.dumps(vm_description_meta(argv[2], int(argv[3])), indent=2))
            return 0
        if len(argv) == 3:
            print(json.dumps(vm_description_meta_for_vmid(int(argv[2])), indent=2))
            return 0
        raise SystemExit("usage: beagle_provider.py vm-description-meta <vmid> | <node> <vmid>")
    if command == "guest-exec-bash-b64":
        if len(argv) not in {4, 5}:
            raise SystemExit("usage: beagle_provider.py guest-exec-bash-b64 <vmid> <command_b64> [timeout_seconds]")
        timeout_seconds = int(argv[4]) if len(argv) == 5 and str(argv[4]).strip() else None
        script = b64decode(argv[3].encode("ascii")).decode("utf-8")
        print(json.dumps(guest_exec_bash(int(argv[2]), script, timeout_seconds=timeout_seconds), indent=2))
        return 0
    if command == "guest-exec-bash-sync-b64":
        if len(argv) not in {4, 5}:
            raise SystemExit("usage: beagle_provider.py guest-exec-bash-sync-b64 <vmid> <command_b64> [timeout_seconds]")
        timeout_seconds = int(argv[4]) if len(argv) == 5 and str(argv[4]).strip() else None
        script = b64decode(argv[3].encode("ascii")).decode("utf-8")
        print(json.dumps(guest_exec_bash_sync(int(argv[2]), script, timeout_seconds=timeout_seconds), indent=2))
        return 0
    if command == "guest-exec-status":
        if len(argv) != 4:
            raise SystemExit("usage: beagle_provider.py guest-exec-status <vmid> <pid>")
        print(json.dumps(guest_exec_status(int(argv[2]), int(argv[3])), indent=2))
        return 0
    if command == "set-vm-options":
        if len(argv) < 5 or (len(argv) - 3) % 2 != 0:
            raise SystemExit("usage: beagle_provider.py set-vm-options <vmid> <option> <value> [<option> <value> ...]")
        pairs: list[tuple[str, str]] = []
        for index in range(3, len(argv), 2):
            pairs.append((argv[index], argv[index + 1]))
        output = set_vm_options(int(argv[2]), pairs)
        if output:
            print(output, end="" if output.endswith("\n") else "\n")
        return 0
    if command == "set-vm-description-b64":
        if len(argv) != 4:
            raise SystemExit("usage: beagle_provider.py set-vm-description-b64 <vmid> <description_b64>")
        output = set_vm_description(int(argv[2]), b64decode(argv[3].encode("ascii")).decode("utf-8"))
        if output:
            print(output, end="" if output.endswith("\n") else "\n")
        return 0
    if command == "reboot-vm":
        if len(argv) != 3:
            raise SystemExit("usage: beagle_provider.py reboot-vm <vmid>")
        output = reboot_vm(int(argv[2]))
        if output:
            print(output, end="" if output.endswith("\n") else "\n")
        return 0
    raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
