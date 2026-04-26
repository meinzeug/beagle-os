from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from migration_service import MigrationService


@dataclass
class _Vm:
    vmid: int
    node: str
    status: str


def _service(*, vm: _Vm | None = None, nodes: list[dict] | None = None, exists: bool = True):
    vm_obj = vm or _Vm(vmid=101, node="node-a", status="running")
    node_list = nodes or [
        {"name": "node-a", "status": "online"},
        {"name": "node-b", "status": "online"},
    ]
    calls: dict[str, object] = {"virsh": None, "persist": None, "invalidations": []}

    service = MigrationService(
        build_migration_uri=lambda source_node, target_node, vmid: f"qemu+ssh://{target_node}/system?source={source_node}&vmid={vmid}",
        find_vm=lambda vmid: vm_obj if int(vmid) == vm_obj.vmid else None,
        invalidate_vm_cache=lambda vmid, node: calls["invalidations"].append((vmid, node)),
        libvirt_domain_exists=lambda vmid: bool(exists),
        libvirt_domain_name=lambda vmid: f"beagle-{int(vmid)}",
        libvirt_enabled=lambda: True,
        list_nodes=lambda: node_list,
        persist_vm_node=lambda vmid, source_node, target_node: calls.__setitem__("persist", (vmid, source_node, target_node)),
        run_virsh_command=lambda command: calls.__setitem__("virsh", list(command)) or "migration complete",
        service_name="beagle-control-plane",
        utcnow=lambda: "2026-04-23T10:00:00Z",
        version="test",
    )
    return service, calls


def _service_with_virsh_calls(run_virsh_command, *, vm: _Vm | None = None, nodes: list[dict] | None = None, exists: bool = True):
    vm_obj = vm or _Vm(vmid=101, node="node-a", status="running")
    node_list = nodes or [
        {"name": "node-a", "status": "online"},
        {"name": "node-b", "status": "online"},
    ]

    service = MigrationService(
        build_migration_uri=lambda source_node, target_node, vmid: f"qemu+ssh://{target_node}/system?source={source_node}&vmid={vmid}",
        find_vm=lambda vmid: vm_obj if int(vmid) == vm_obj.vmid else None,
        invalidate_vm_cache=lambda vmid, node: None,
        libvirt_domain_exists=lambda vmid: bool(exists),
        libvirt_domain_name=lambda vmid: f"beagle-{int(vmid)}",
        libvirt_enabled=lambda: True,
        list_nodes=lambda: node_list,
        persist_vm_node=lambda vmid, source_node, target_node: None,
        run_virsh_command=run_virsh_command,
        service_name="beagle-control-plane",
        utcnow=lambda: "2026-04-23T10:00:00Z",
        version="test",
    )
    return service


def test_list_target_nodes_filters_online_non_source_nodes() -> None:
    service, _calls = _service(nodes=[
        {"name": "node-a", "status": "online"},
        {"name": "node-b", "status": "online"},
        {"name": "node-c", "status": "offline"},
    ])

    assert service.list_target_nodes(101) == [{"name": "node-b", "status": "online"}]


def test_migrate_vm_runs_live_virsh_and_persists_target_node() -> None:
    service, calls = _service()

    payload = service.migrate_vm(101, target_node="node-b", requester_identity="admin")

    assert calls["virsh"] == [
        "migrate",
        "--persistent",
        "--undefinesource",
        "--verbose",
        "--live",
        "beagle-101",
        "qemu+ssh://node-b/system?source=node-a&vmid=101",
    ]
    assert calls["persist"] == (101, "node-a", "node-b")
    assert payload["migration"]["target_node"] == "node-b"
    assert payload["migration"]["requested_by"] == "admin"


def test_migrate_vm_requires_running_vm_for_live_migration() -> None:
    service, _calls = _service(vm=_Vm(vmid=101, node="node-a", status="stopped"))

    try:
        service.migrate_vm(101, target_node="node-b")
    except RuntimeError as exc:
        assert "requires a running VM" in str(exc)
    else:
        raise AssertionError("expected live migration validation to fail")


def test_migrate_vm_rejects_same_target_node() -> None:
    service, _calls = _service()

    try:
        service.migrate_vm(101, target_node="node-a")
    except RuntimeError as exc:
        assert "must differ" in str(exc)
    else:
        raise AssertionError("expected same-node validation to fail")


def test_migrate_vm_copy_storage_prefers_incremental_mode() -> None:
    calls: list[list[str]] = []

    def _run(command: list[str]) -> str:
        calls.append(list(command))
        return "ok"

    service = _service_with_virsh_calls(_run)
    payload = service.migrate_vm(101, target_node="node-b", live=True, copy_storage=True)

    assert calls and "--copy-storage-inc" in calls[0]
    assert "--copy-storage-all" not in calls[0]
    assert payload["migration"]["copy_storage_mode"] == "incremental"


def test_migrate_vm_copy_storage_falls_back_to_all_when_inc_unsupported() -> None:
    calls: list[list[str]] = []

    def _run(command: list[str]) -> str:
        calls.append(list(command))
        if "--copy-storage-inc" in command:
            raise RuntimeError("virsh: error: unknown option --copy-storage-inc")
        return "ok"

    service = _service_with_virsh_calls(_run)
    payload = service.migrate_vm(101, target_node="node-b", live=True, copy_storage=True)

    assert len(calls) == 2
    assert "--copy-storage-inc" in calls[0]
    assert "--copy-storage-all" in calls[1]
    assert payload["migration"]["copy_storage_mode"] == "all"