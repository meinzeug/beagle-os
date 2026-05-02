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


def test_novnc_action_launch_and_error_guards_are_wired() -> None:
    actions = _read(ACTIONS_JS)

    assert "const access = payload && payload.novnc_access ? payload.novnc_access : {};" in actions
    assert "if (!access.available) {" in actions
    assert "noVNC ist fuer diese VM nicht verfuegbar." in actions
    assert "if (!url) {" in actions
    assert "Keine noVNC URL erhalten." in actions
    assert "if (!isSafeExternalUrl(url)) {" in actions
    assert "Unsichere noVNC URL blockiert." in actions
    assert "window.open(url, '_blank', 'noopener');" in actions
    assert "actionHooks.setBanner('noVNC Zugriff fehlgeschlagen: ' + error.message, 'warn');" in actions


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


def test_vm_delete_action_is_unconditionally_visible_in_detail_actions() -> None:
    main = _read(MAIN_JS)

    install_block = main.index("if (status === 'installing') {")
    delete_button = main.index("html += actionButton('vm-delete', 'VM loeschen', 'danger');")
    return_line = main.index("return html;", delete_button)

    assert install_block < delete_button < return_line


def test_vm_delete_action_logs_success_and_failure_paths() -> None:
    actions = _read(ACTIONS_JS)

    assert "actionHooks.addToActivityLog('vm-delete', vmid, 'ok', 'VM geloescht');" in actions
    assert "actionHooks.setBanner('VM ' + vmid + ' geloescht.', 'ok');" in actions
    assert "actionHooks.addToActivityLog('vm-delete', vmid, 'warn', error.message);" in actions
    assert "actionHooks.setBanner('VM konnte nicht geloescht werden: ' + error.message, 'warn');" in actions


def test_vm_detail_surfaces_stream_runtime_variant_and_fallback_state() -> None:
    main = _read(MAIN_JS)

    assert "function streamRuntimeVariantLabel(profile)" in main
    assert "function streamRuntimeVariantBanner(profile)" in main
    assert "BeagleStream Server" in main
    assert "Sunshine Fallback" in main
    assert "fieldBlock('Stream-Runtime', streamRuntimeVariantLabel(profile))" in main
    assert "fieldBlock('Stream-Paket', profile.stream_runtime && profile.stream_runtime.package_url ? profile.stream_runtime.package_url : 'n/a')" in main
    assert "Diese VM laeuft noch im Sunshine-Fallback." in main
