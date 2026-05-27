from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACTIONS_JS = ROOT / "website" / "ui" / "actions.js"
INVENTORY_JS = ROOT / "website" / "ui" / "inventory.js"
MAIN_JS = ROOT / "website" / "main.js"
VM_CONFIG_EDITOR_JS = ROOT / "website" / "ui" / "vm_config_editor.js"
PROVISIONING_JS = ROOT / "website" / "ui" / "provisioning.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_novnc_actions_are_available_in_inventory_and_detail() -> None:
    actions = _read(ACTIONS_JS)
    inventory = _read(INVENTORY_JS)
    main = _read(MAIN_JS)

    assert "if (action === 'novnc-ui')" in actions
    assert "if (action === 'spice-ui')" in actions
    assert "request('/vms/' + vmid + '/novnc-access'" in actions
    assert "blobRequest('/vms/' + vmid + '/spice.vv'" in actions
    assert "window.open(url, '_blank', 'noopener')" in actions
    assert "noVNC Zugriff fehlgeschlagen" in actions
    assert 'data-vm-console="novnc"' in inventory
    assert 'data-vm-console="spice"' in inventory
    assert 'summary class="btn btn-ghost">Konsole</summary>' in main
    assert "actionButton('novnc-ui', 'noVNC', 'ghost')" in main
    assert "actionButton('spice-ui', 'SPICE (.vv)', 'ghost')" in main


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
    assert "actionHooks.setBanner('SPICE Download fehlgeschlagen: ' + error.message, 'warn');" in actions


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
    assert "Beagle Stream Server Fallback" in main
    assert "fieldBlock('Stream-Runtime', streamRuntimeVariantLabel(profile))" in main
    assert "fieldBlock('Stream-Paket', profile.stream_runtime && profile.stream_runtime.package_url ? profile.stream_runtime.package_url : 'n/a')" in main
    assert "Diese VM laeuft noch im Beagle Stream Server-Fallback." in main


def test_vm_detail_update_policy_switches_are_wired() -> None:
    actions = _read(ACTIONS_JS)
    main = _read(MAIN_JS)

    assert 'data-update-policy-toggle data-action="set-update-enabled"' in main
    assert 'data-update-policy-toggle data-action="set-update-automation"' in main
    assert "set-update-channel-stable" in main
    assert "set-update-channel-rolling" in main
    assert "request('/vms/' + vmid + '/update-policy'" in actions
    assert "payload.behavior = enabled ? 'auto' : 'prompt';" in actions
    assert "payload.enabled = Boolean(sourceButton && sourceButton.checked);" in actions


def test_vm_config_editor_surfaces_guided_control_ui() -> None:
    editor = _read(VM_CONFIG_EDITOR_JS)

    assert "vm-setting-row" in editor
    assert "vm-setting-hint" in editor
    assert "renderSelectOptions(field, value)" in editor
    assert "renderParamSelect(" in editor
    assert "beagle.vmConfigEditor.mode" in editor
    assert "data-vm-mode=\"simple\"" in editor
    assert "data-vm-mode=\"pro\"" in editor
    assert "data-vm-config-item" in editor
    assert "vm-config-group-summary" in editor
    assert "FIELD_PRESETS" in editor
    assert "data-vm-preset-key" in editor
    assert "applyPreset(form, presetButton)" in editor
    assert "mode === 'append'" in editor
    assert "data-vm-config-range" in editor
    assert "vm-setting-number" in editor
    assert "vm-setting-toggle" in editor
    assert "syncControlSurface(form, event.target)" in editor
    assert "data-vm-config-filter" in editor
    assert "data-vm-show-changed" in editor
    assert "data-vm-change-count" in editor
    assert "refreshEnterpriseConsole(form)" in editor
    assert "FIELD_VALIDATIONS" in editor
    assert "VM Konfiguration" in editor
    assert "vm-config-help-modal" not in editor
    assert "vm-config-guide-panel" not in editor


def test_provisioning_supports_one_click_quick_intents() -> None:
    provisioning = _read(PROVISIONING_JS)

    assert "One-Click Provisioning" in provisioning
    assert "Thinclient VM mieten" in provisioning
    assert "Dedicated Server mieten" in provisioning
    assert "runProvisionQuickIntent(intentKey, idPrefix, autoCreate)" in provisioning
    assert "data-provision-quick-intent" in provisioning
    assert "data-provision-quick-create=\"1\"" in provisioning
    assert "ensureQuickIntentDeck(idPrefix)" in provisioning
    assert "randomPassword(20)" in provisioning
