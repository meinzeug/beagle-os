#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[1] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from migration_service import MigrationService  # type: ignore


@dataclass
class Vm:
    vmid: int
    node: str
    status: str


def main() -> int:
    vm = Vm(vmid=321, node="node-a", status="running")
    calls: dict[str, object] = {"virsh": None, "persist": None}

    service = MigrationService(
        build_migration_uri=lambda source_node, target_node, vmid: f"qemu+ssh://{target_node}/system?source={source_node}&vmid={vmid}",
        find_vm=lambda vmid: vm if int(vmid) == vm.vmid else None,
        invalidate_vm_cache=lambda vmid, node: None,
        libvirt_domain_exists=lambda vmid: True,
        libvirt_domain_name=lambda vmid: f"beagle-{int(vmid)}",
        libvirt_enabled=lambda: True,
        list_nodes=lambda: [{"name": "node-a", "status": "online"}, {"name": "node-b", "status": "online"}],
        persist_vm_node=lambda vmid, source_node, target_node: calls.__setitem__("persist", (vmid, source_node, target_node)),
        run_virsh_command=lambda command: calls.__setitem__("virsh", list(command)) or "migration complete",
        service_name="beagle-control-plane",
        utcnow=lambda: "2026-04-23T10:00:00Z",
        version="test",
    )

    payload = service.migrate_vm(321, target_node="node-b", requester_identity="smoke")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if calls["persist"] != (321, "node-a", "node-b"):
        return 1
    if not isinstance(calls["virsh"], list) or "--live" not in calls["virsh"]:
        return 1
    print("VM_MIGRATION_SMOKE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())