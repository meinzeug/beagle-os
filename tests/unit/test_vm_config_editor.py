from __future__ import annotations

import sys
from pathlib import Path

SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from vm_config_editor import VmConfigEditorService


class _Vm:
    vmid = 100
    node = "node-a"


def test_update_vm_config_validates_and_updates_provider_state() -> None:
    current = {"vmid": 100, "node": "node-a", "name": "old", "memory": 2048, "net0": "virtio,bridge=br0"}
    calls: list[tuple[int, dict]] = []
    invalidations: list[tuple[int | None, str]] = []

    service = VmConfigEditorService(
        get_vm_config=lambda node, vmid: dict(current),
        set_vm_options=lambda vmid, options: calls.append((vmid, dict(options))) or "ok",
        invalidate_vm_cache=lambda vmid, node: invalidations.append((vmid, node)),
    )

    result = service.update_vm_config(_Vm(), {"updates": {"name": "new", "memory": "4096", "onboot": "true"}})

    assert result["ok"] is True
    assert result["changed"] == ["memory", "name", "onboot"]
    assert result["config"]["memory"] == 4096
    assert result["config"]["onboot"] is True
    assert calls[0][0] == 100
    assert calls[0][1]["name"] == "new"
    assert calls[0][1]["memory"] == 4096
    assert invalidations == [(100, "node-a")]


def test_update_vm_config_rejects_unsupported_options() -> None:
    service = VmConfigEditorService(
        get_vm_config=lambda node, vmid: {},
        set_vm_options=lambda vmid, options: "ok",
        invalidate_vm_cache=lambda vmid, node: None,
    )

    result = service.update_vm_config(_Vm(), {"updates": {"not_allowed": "x"}})

    assert result["ok"] is False
    assert int(result["status"]) == 400
    assert "unsupported option" in result["error"]


def test_update_vm_config_accepts_hardware_patterns() -> None:
    calls: list[tuple[int, dict]] = []
    service = VmConfigEditorService(
        get_vm_config=lambda node, vmid: {"vmid": 100, "node": "node-a"},
        set_vm_options=lambda vmid, options: calls.append((vmid, dict(options))) or "ok",
        invalidate_vm_cache=lambda vmid, node: None,
    )

    result = service.update_vm_config(_Vm(), {"updates": {"virtio0": "local:vm-100-disk-0", "net0": "virtio,bridge=br0"}})

    assert result["ok"] is True
    assert calls[0][1]["virtio0"] == "local:vm-100-disk-0"
    assert calls[0][1]["net0"] == "virtio,bridge=br0"
