"""Tests for Device Registry (GoEnterprise Plan 02, Schritt 1+4+5)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from device_registry import DeviceRegistryService


HW = {
    "cpu_model": "Intel Core i5-8500T",
    "cpu_cores": 6,
    "ram_gb": 16,
    "gpu_model": "",
    "network_interfaces": ["eth0"],
    "disk_gb": 256,
}


def make_svc(tmp_path: Path) -> DeviceRegistryService:
    return DeviceRegistryService(
        state_file=tmp_path / "registry.json",
        utcnow=lambda: "2026-04-25T10:00:00Z",
    )


def test_register_device(tmp_path):
    svc = make_svc(tmp_path)
    dev = svc.register_device("dev-001", "kiosk-01", HW, os_version="1.6.0")
    assert dev.device_id == "dev-001"
    assert dev.hostname == "kiosk-01"
    assert dev.hardware.cpu_cores == 6
    assert dev.status == "offline"


def test_get_device(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_device("dev-001", "kiosk-01", HW)
    dev = svc.get_device("dev-001")
    assert dev is not None
    assert dev.hostname == "kiosk-01"


def test_get_nonexistent_returns_none(tmp_path):
    svc = make_svc(tmp_path)
    assert svc.get_device("ghost") is None


def test_heartbeat_sets_online(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_device("dev-001", "kiosk-01", HW)
    dev = svc.update_heartbeat("dev-001")
    assert dev.status == "online"


def test_list_by_group(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_device("dev-001", "k1", HW)
    svc.register_device("dev-002", "k2", HW)
    svc.set_group("dev-001", "reception")
    svc.set_group("dev-002", "lobby")
    reception = svc.list_devices(group="reception")
    assert len(reception) == 1
    assert reception[0].device_id == "dev-001"


def test_remote_wipe(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_device("dev-001", "k1", HW)
    svc.update_heartbeat("dev-001")
    dev = svc.wipe_device("dev-001")
    assert dev.status == "wipe_pending"
    dev2 = svc.confirm_wiped("dev-001")
    assert dev2.status == "wiped"
    assert dev2.wg_public_key == ""


def test_lock_unlock(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_device("dev-001", "k1", HW)
    svc.lock_device("dev-001")
    assert svc.get_device("dev-001").status == "locked"
    svc.unlock_device("dev-001")
    assert svc.get_device("dev-001").status == "offline"


def test_bulk_group_assign(tmp_path):
    svc = make_svc(tmp_path)
    for i in range(5):
        svc.register_device(f"dev-{i:03}", f"k{i}", HW)
    updated = svc.assign_group("lab-room-1", ["dev-000", "dev-001", "dev-002"])
    assert len(updated) == 3
    assert all(svc.get_device(did).group == "lab-room-1" for did in updated)


def test_list_groups(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_device("dev-001", "k1", HW)
    svc.register_device("dev-002", "k2", HW)
    svc.set_group("dev-001", "alpha")
    svc.set_group("dev-002", "beta")
    groups = svc.list_groups()
    assert "alpha" in groups
    assert "beta" in groups


def test_persistence(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_device("dev-001", "kiosk-01", HW)
    svc2 = make_svc(tmp_path)
    dev = svc2.get_device("dev-001")
    assert dev is not None
    assert dev.hostname == "kiosk-01"


def test_register_or_update_device_preserves_record(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_device("dev-001", "kiosk-01", HW, os_version="1.0")
    dev = svc.register_or_update_device(
        "dev-001",
        "kiosk-01-new",
        {**HW, "cpu_cores": 8},
        os_version="1.1",
        vpn_active=True,
        vpn_interface="wg-beagle",
        wg_assigned_ip="10.88.0.10/32",
    )
    assert dev.hostname == "kiosk-01-new"
    assert dev.hardware.cpu_cores == 8
    assert dev.os_version == "1.1"
    assert dev.vpn_active is True
    assert dev.vpn_interface == "wg-beagle"
    assert dev.wg_assigned_ip == "10.88.0.10/32"


def test_heartbeat_keeps_locked_and_wipe_pending_status(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_device("dev-001", "k1", HW)
    svc.lock_device("dev-001")
    locked = svc.update_heartbeat("dev-001")
    assert locked.status == "locked"
    svc.wipe_device("dev-001")
    wiped = svc.update_heartbeat("dev-001")
    assert wiped.status == "wipe_pending"


def test_confirm_wiped_clears_vpn_state(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_device(
        "dev-001",
        "k1",
        HW,
        vpn_active=True,
        vpn_interface="wg-beagle",
        wg_public_key="pub",
        wg_assigned_ip="10.88.0.10/32",
    )
    svc.wipe_device("dev-001")
    wiped = svc.confirm_wiped("dev-001")
    assert wiped.status == "wiped"
    assert wiped.vpn_active is False
    assert wiped.vpn_interface == ""
    assert wiped.wg_public_key == ""
    assert wiped.wg_assigned_ip == ""
