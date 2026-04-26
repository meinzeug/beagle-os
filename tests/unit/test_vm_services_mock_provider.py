"""Unit tests for beagle-host services using a mock HostProvider.

Covers Plan 05 Step 5a: provider-neutral service tests with mock provider.
Tests verify service behaviour without real libvirt/KVM dependencies.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

# Add the providers and services directories to the path
_PROVIDERS_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "providers"
_SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
for _p in (_PROVIDERS_DIR, _SERVICES_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from host_provider_contract import HostProvider
from virtualization_inventory import VirtualizationInventoryService


class MockHostProvider:
    """Minimal HostProvider implementation for testing service behaviour."""

    def __init__(self, vms: list[dict[str, Any]] | None = None) -> None:
        self._vms: list[dict[str, Any]] = vms or []
        self._nodes: list[dict[str, Any]] = [{"node": "beagle-0", "status": "online", "type": "node"}]
        self._bridges: list[dict[str, Any]] = [{"iface": "vmbr0"}]

    # --- HostProvider contract methods ---

    def next_vmid(self) -> int:
        existing = {int(v.get("vmid", 0)) for v in self._vms}
        vmid = 100
        while vmid in existing:
            vmid += 1
        return vmid

    def list_storage_inventory(self) -> list[dict[str, Any]]:
        return [{"storage": "local", "type": "dir", "content": "images,iso"}]

    def list_nodes(self) -> list[dict[str, Any]]:
        return list(self._nodes)

    def list_bridges(self, node: str = "") -> list[dict[str, Any]]:
        return list(self._bridges)

    def get_guest_network_interfaces(
        self,
        vmid: int,
        *,
        cache_key: str = "",
        cache_ttl_seconds: float = 0,
        timeout_seconds: float = 5,
    ) -> list[dict[str, Any]]:
        return []

    def list_vms(
        self,
        *,
        refresh: bool = False,
        cache_key: str = "",
        cache_ttl_seconds: float = 0,
        vm_summary_factory: Any = None,
    ) -> list[Any]:
        if vm_summary_factory is not None:
            return [vm_summary_factory(v) for v in self._vms]
        return list(self._vms)

    def get_vm_config(
        self,
        node: str,
        vmid: int,
        *,
        cache_key: str = "",
        cache_ttl_seconds: float = 0,
    ) -> dict[str, Any]:
        for vm in self._vms:
            if int(vm.get("vmid", -1)) == int(vmid):
                return dict(vm)
        return {}

    def create_vm(self, vmid: int, config: dict[str, Any]) -> dict[str, Any]:
        record = {"vmid": vmid, **config}
        self._vms.append(record)
        return record

    def set_vm_options(self, node: str, vmid: int, options: dict[str, Any]) -> dict[str, Any]:
        for vm in self._vms:
            if int(vm.get("vmid", -1)) == int(vmid):
                vm.update(options)
                return dict(vm)
        return {}

    def delete_vm_options(self, node: str, vmid: int, keys: list[str]) -> dict[str, Any]:
        for vm in self._vms:
            if int(vm.get("vmid", -1)) == int(vmid):
                for k in keys:
                    vm.pop(k, None)
                return dict(vm)
        return {}

    def delete_vm(self, node: str, vmid: int) -> str:
        self._vms = [v for v in self._vms if int(v.get("vmid", -1)) != int(vmid)]
        return f"deleted {vmid}"

    def set_vm_description(self, node: str, vmid: int, description: str) -> dict[str, Any]:
        return {}

    def set_vm_boot_order(self, node: str, vmid: int, boot_order: str) -> dict[str, Any]:
        return {}

    def start_vm(self, vmid: int) -> str:
        return f"started {vmid}"

    def reboot_vm(self, vmid: int) -> str:
        return f"rebooted {vmid}"

    def stop_vm(self, vmid: int) -> str:
        return f"stopped {vmid}"

    def resume_vm(self, vmid: int) -> str:
        return f"resumed {vmid}"

    def guest_exec_bash(self, vmid: int, command: str, *, timeout_seconds: float = 30) -> dict[str, Any]:
        return {"exitcode": 0, "stdout": "", "stderr": ""}

    def guest_exec_status(self, vmid: int, pid: int) -> dict[str, Any]:
        return {"status": "done", "exitcode": 0}

    def guest_exec_script_text(self, vmid: int, script: str, *, timeout_seconds: float = 60) -> dict[str, Any]:
        return {"exitcode": 0, "stdout": "", "stderr": ""}

    def schedule_vm_restart_after_stop(self, vmid: int, *, delay_seconds: float = 5) -> dict[str, Any]:
        return {"scheduled": True, "vmid": vmid}

    def snapshot_vm(self, vmid: int, name: str, *, description: str = "") -> str:
        return f"created snapshot {name} for vm {vmid}"

    def reset_vm_to_snapshot(self, vmid: int, snapshot_name: str, *, timeout: Any = None) -> str:
        return f"reset vm {vmid} to snapshot {snapshot_name}"

    def clone_vm(self, vmid: int, newid: int, *, name: str = "", node: str = "") -> str:
        return f"cloned {vmid} to {newid}"

    def get_console_proxy(self, vmid: int) -> dict[str, Any]:
        return {"provider": "beagle", "available": False, "scheme": "vnc", "vmid": vmid}

    def get_guest_ipv4(
        self,
        vmid: int,
        *,
        cache_key: str = "",
        cache_ttl_seconds: float = 0,
        enable_lookup: bool = False,
        timeout_seconds: float = 5,
    ) -> str:
        return ""


class _VmSummary:
    """Minimal VM summary object as returned by vm_summary_factory."""

    def __init__(self, record: dict[str, Any]) -> None:
        self.vmid = int(record.get("vmid", 0))
        self.name = str(record.get("name", ""))
        self.status = str(record.get("status", "stopped"))

    def __repr__(self) -> str:
        return f"<VmSummary vmid={self.vmid} name={self.name!r}>"


def _make_inventory_service(vms: list[dict[str, Any]] | None = None) -> VirtualizationInventoryService:
    provider = MockHostProvider(vms=vms)
    return VirtualizationInventoryService(
        provider=provider,
        vm_summary_factory=_VmSummary,
        list_vms_cache_seconds=0,
        vm_config_cache_seconds=0,
        guest_ipv4_cache_seconds=0,
        enable_guest_ip_lookup=False,
        guest_agent_timeout_seconds=5,
        default_bridge="vmbr0",
    )


class TestVirtualizationInventoryServiceWithMock(unittest.TestCase):
    """VirtualizationInventoryService tests using MockHostProvider."""

    def test_list_vms_returns_summaries(self) -> None:
        vms = [
            {"vmid": 101, "name": "desktop-1", "status": "running"},
            {"vmid": 102, "name": "desktop-2", "status": "stopped"},
        ]
        svc = _make_inventory_service(vms)
        result = svc.list_vms()
        self.assertEqual(len(result), 2)
        vmids = sorted(s.vmid for s in result)
        self.assertEqual(vmids, [101, 102])

    def test_list_vms_empty(self) -> None:
        svc = _make_inventory_service([])
        result = svc.list_vms()
        self.assertEqual(result, [])

    def test_find_vm_returns_matching_summary(self) -> None:
        vms = [{"vmid": 101, "name": "desktop-1", "status": "running"}]
        svc = _make_inventory_service(vms)
        found = svc.find_vm(101)
        self.assertIsNotNone(found)
        self.assertEqual(found.vmid, 101)

    def test_find_vm_missing_returns_none(self) -> None:
        svc = _make_inventory_service([])
        self.assertIsNone(svc.find_vm(999))

    def test_list_nodes_inventory(self) -> None:
        svc = _make_inventory_service()
        nodes = svc.list_nodes_inventory()
        self.assertIsInstance(nodes, list)
        self.assertGreater(len(nodes), 0)
        self.assertEqual(nodes[0]["node"], "beagle-0")

    def test_get_vm_config_returns_dict(self) -> None:
        vms = [{"vmid": 101, "name": "desktop-1", "status": "running", "memory": 4096}]
        svc = _make_inventory_service(vms)
        cfg = svc.get_vm_config("beagle-0", 101)
        self.assertIsInstance(cfg, dict)
        self.assertEqual(cfg.get("vmid"), 101)
        self.assertEqual(cfg.get("memory"), 4096)

    def test_get_vm_config_missing_returns_empty(self) -> None:
        svc = _make_inventory_service([])
        cfg = svc.get_vm_config("beagle-0", 999)
        self.assertEqual(cfg, {})

    def test_first_guest_ipv4_returns_string(self) -> None:
        svc = _make_inventory_service([{"vmid": 101, "name": "x", "status": "running"}])
        ip = svc.first_guest_ipv4(101)
        self.assertIsInstance(ip, str)

    def test_list_bridge_inventory_includes_default(self) -> None:
        svc = _make_inventory_service()
        bridges = svc.list_bridge_inventory()
        self.assertIn("vmbr0", bridges)

    def test_config_bridge_names_extracts_bridges(self) -> None:
        svc = _make_inventory_service()
        config = {"net0": "virtio,bridge=vmbr0,firewall=1", "net1": "virtio,bridge=vmbr1"}
        bridges = svc.config_bridge_names(config)
        self.assertIn("vmbr0", bridges)
        self.assertIn("vmbr1", bridges)

    def test_config_bridge_names_empty_config(self) -> None:
        svc = _make_inventory_service()
        self.assertEqual(svc.config_bridge_names({}), set())


class TestMockHostProviderContractCompliance(unittest.TestCase):
    """Verify MockHostProvider satisfies the HostProvider contract at runtime."""

    def setUp(self) -> None:
        self.provider = MockHostProvider(vms=[
            {"vmid": 101, "name": "vm-101", "status": "running"},
        ])

    def test_next_vmid_is_int(self) -> None:
        self.assertIsInstance(self.provider.next_vmid(), int)

    def test_list_nodes_is_list(self) -> None:
        self.assertIsInstance(self.provider.list_nodes(), list)

    def test_list_bridges_is_list(self) -> None:
        self.assertIsInstance(self.provider.list_bridges(), list)

    def test_start_vm_returns_string(self) -> None:
        self.assertIsInstance(self.provider.start_vm(101), str)

    def test_stop_vm_returns_string(self) -> None:
        self.assertIsInstance(self.provider.stop_vm(101), str)

    def test_reboot_vm_returns_string(self) -> None:
        self.assertIsInstance(self.provider.reboot_vm(101), str)

    def test_snapshot_vm_returns_string(self) -> None:
        result = self.provider.snapshot_vm(101, "snap1", description="test")
        self.assertIsInstance(result, str)

    def test_clone_vm_returns_string(self) -> None:
        result = self.provider.clone_vm(101, 201, name="clone-201")
        self.assertIsInstance(result, str)

    def test_get_console_proxy_returns_dict_with_provider_key(self) -> None:
        payload = self.provider.get_console_proxy(101)
        self.assertIn("provider", payload)
        self.assertEqual(payload["provider"], "beagle")

    def test_delete_vm_removes_from_list(self) -> None:
        self.provider.create_vm(200, {"name": "vm-200", "status": "stopped"})
        self.provider.delete_vm("beagle-0", 200)
        ids = [int(v["vmid"]) for v in self.provider.list_vms()]
        self.assertNotIn(200, ids)

    def test_create_vm_adds_to_list(self) -> None:
        self.provider.create_vm(300, {"name": "vm-300", "status": "stopped"})
        ids = [int(v["vmid"]) for v in self.provider.list_vms()]
        self.assertIn(300, ids)

    def test_mock_provider_satisfies_host_provider_protocol(self) -> None:
        """Ensure MockHostProvider has all methods required by HostProvider."""
        import inspect
        contract_methods = {
            name for name, _ in inspect.getmembers(HostProvider, predicate=inspect.isfunction)
            if not name.startswith("_")
        }
        mock_methods = {
            name for name, _ in inspect.getmembers(MockHostProvider, predicate=inspect.isfunction)
            if not name.startswith("_")
        }
        missing = contract_methods - mock_methods
        self.assertEqual(missing, set(), f"MockHostProvider is missing contract methods: {missing}")


if __name__ == "__main__":
    unittest.main()
