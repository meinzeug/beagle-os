from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACTIONS_JS = ROOT / "website" / "ui" / "actions.js"
INVENTORY_JS = ROOT / "website" / "ui" / "inventory.js"
MAIN_JS = ROOT / "website" / "main.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_novnc_actions_are_available_in_inventory_and_detail() -> None:
    actions = _read(ACTIONS_JS)
    inventory = _read(INVENTORY_JS)
    main = _read(MAIN_JS)

    assert "if (action === 'novnc-ui')" in actions
    assert "request('/vms/' + vmid + '/novnc-access'" in actions
    assert "window.open(url, '_blank', 'noopener')" in actions
    assert "noVNC Zugriff fehlgeschlagen" in actions
    assert 'data-vm-console="novnc"' in inventory
    assert "actionButton('novnc-ui', 'noVNC', 'ghost')" in main


def test_vm_delete_action_clears_selection_and_refreshes_dashboard() -> None:
    actions = _read(ACTIONS_JS)
    main = _read(MAIN_JS)

    assert "if (action === 'vm-delete')" in actions
    assert "request('/provisioning/vms/' + vmid, { method: 'DELETE' })" in actions
    assert "state.selectedVmids = state.selectedVmids.filter" in actions
    assert "delete state.detailCache[vmid]" in actions
    assert "state.selectedVmid = null" in actions
    assert "actionHooks.loadDashboard({ force: true })" in actions
    assert "actionButton('vm-delete', 'VM loeschen', 'danger')" in main
