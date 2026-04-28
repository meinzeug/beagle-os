from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from device_registry import DeviceRegistryService
from mdm_policy_service import MDMPolicy, MDMPolicyService


HW = {
    "cpu_model": "Intel Core i5-8500T",
    "cpu_cores": 6,
    "ram_gb": 16,
    "gpu_model": "Intel UHD 630",
    "network_interfaces": ["eth0"],
    "disk_gb": 256,
}


def make_registry(tmp_path: Path) -> DeviceRegistryService:
    return DeviceRegistryService(
        state_file=tmp_path / "registry.json",
        utcnow=lambda: "2026-04-28T09:00:00Z",
    )


def make_policy_service(tmp_path: Path) -> MDMPolicyService:
    return MDMPolicyService(state_file=tmp_path / "mdm.json")


def test_location_and_group_filters_can_be_combined(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    registry.register_device("dev-001", "tc-001", HW)
    registry.register_device("dev-002", "tc-002", HW)
    registry.set_location("dev-001", "Berlin")
    registry.set_group("dev-001", "reception")
    registry.set_location("dev-002", "Munich")
    registry.set_group("dev-002", "reception")

    berlin = registry.list_devices(location="Berlin", group="reception")

    assert [device.device_id for device in berlin] == ["dev-001"]


def test_assign_group_only_updates_existing_devices(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    registry.register_device("dev-001", "tc-001", HW)
    registry.register_device("dev-002", "tc-002", HW)

    updated = registry.assign_group("berlin-lobby", ["dev-001", "missing", "dev-002"])

    assert updated == ["dev-001", "dev-002"]
    assert registry.get_device("dev-001").group == "berlin-lobby"
    assert registry.get_device("dev-002").group == "berlin-lobby"


def test_group_assignment_resolves_effective_policy_for_devices(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    mdm = make_policy_service(tmp_path)
    registry.register_device("dev-001", "tc-001", HW)
    registry.register_device("dev-002", "tc-002", HW)
    registry.assign_group("berlin", ["dev-001", "dev-002"])
    mdm.create_policy(MDMPolicy(policy_id="corp", name="Corporate", allowed_pools=["pool-a"]))
    mdm.assign_to_group("berlin", "corp")

    first, first_source, first_id = mdm.resolve_policy_with_source("dev-001", group=registry.get_device("dev-001").group)
    second, second_source, second_id = mdm.resolve_policy_with_source("dev-002", group=registry.get_device("dev-002").group)

    assert first.policy_id == "corp"
    assert second.policy_id == "corp"
    assert (first_source, first_id) == ("group", "berlin")
    assert (second_source, second_id) == ("group", "berlin")
