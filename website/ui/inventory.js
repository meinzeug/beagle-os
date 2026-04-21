import {
  BULK_ACTION_BUTTON_IDS,
  state
} from './state.js';
import {
  actionButton,
  chip,
  clearSecretVault,
  downloadTextFile,
  escapeHtml,
  fieldBlock,
  formatDate,
  maskedFieldBlock,
  qs
} from './dom.js';
import { postJson, request, runSingleFlight } from './api.js';

const inventoryHooks = {
  setActivePanel() {},
  setBanner() {},
  requestConfirm() {
    return Promise.resolve(true);
  },
  loadDashboard() {
    return Promise.resolve();
  },
  addToActivityLog() {},
  loadDetail() {
    return Promise.resolve();
  }
};

export function configureInventory(nextHooks) {
  Object.assign(inventoryHooks, nextHooks || {});
}

export function profileOf(vm) {
  return vm && vm.profile ? vm.profile : vm || {};
}

export function roleOf(vm) {
  const profile = profileOf(vm);
  return String(profile.beagle_role || profile.role || '').trim().toLowerCase();
}

export function isBeagleVm(vm) {
  const profile = profileOf(vm);
  return Boolean(
    profile.beagle_role ||
    profile.stream_host ||
    profile.installer_target_eligible ||
    (vm && vm.endpoint && vm.endpoint.reported_at)
  );
}

export function isEligible(vm) {
  const profile = profileOf(vm);
  return Boolean(profile.installer_target_eligible);
}

export function matchesRoleFilter(vm, value) {
  const role = roleOf(vm);
  if (value === 'all') {
    return true;
  }
  if (value === 'endpoint') {
    return role === 'endpoint' || role === 'thinclient' || role === 'client';
  }
  if (value === 'desktop') {
    return role === 'desktop';
  }
  return role !== 'desktop' && role !== 'endpoint' && role !== 'thinclient' && role !== 'client';
}

export function filteredInventory() {
  const query = String(qs('search-input') ? qs('search-input').value : '').trim().toLowerCase();
  const roleFilter = String(qs('role-filter') ? qs('role-filter').value : 'all');
  const eligibleOnly = Boolean(qs('eligible-only') && qs('eligible-only').checked);
  return state.inventory.filter((vm) => {
    const profile = profileOf(vm);
    if (!isBeagleVm(vm)) {
      return false;
    }
    if (!matchesRoleFilter(vm, roleFilter)) {
      return false;
    }
    if (eligibleOnly && !isEligible(vm)) {
      return false;
    }
    if (!query) {
      return true;
    }
    const haystack = [
      profile.name,
      profile.identity_hostname,
      profile.stream_host,
      profile.node,
      profile.vmid,
      profile.beagle_role,
      profile.assignment_source,
      profile.moonlight_app
    ].join(' ').toLowerCase();
    return haystack.indexOf(query) !== -1;
  }).sort((left, right) => {
    const leftProfile = profileOf(left);
    const rightProfile = profileOf(right);
    const leftRunning = leftProfile.status === 'running' ? 0 : 1;
    const rightRunning = rightProfile.status === 'running' ? 0 : 1;
    if (leftRunning !== rightRunning) {
      return leftRunning - rightRunning;
    }
    return String(leftProfile.name || leftProfile.vmid).localeCompare(String(rightProfile.name || rightProfile.vmid), 'de');
  });
}

export function actionLabel(action) {
  const map = {
    healthcheck: 'Health Check',
    'support-bundle': 'Support Bundle',
    'restart-session': 'Restart Session',
    'restart-runtime': 'Restart Runtime',
    'os-update-scan': 'Update Scan',
    'os-update-download': 'Update Download',
    'os-update-apply': 'Update Apply',
    'os-update-rollback': 'Update Rollback'
  };
  return map[action] || action;
}

export function powerActionLabel(action) {
  const map = {
    start: 'Start',
    stop: 'Stop',
    reboot: 'Reboot'
  };
  return map[action] || action;
}

export function updateStateLabel(updateState) {
  const normalized = String(updateState || '').trim().toLowerCase();
  return normalized || 'unbekannt';
}

export function parseCommaList(value) {
  return String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

export function selectedVmidsFromInventory() {
  return state.selectedVmids.slice().sort((left, right) => Number(left) - Number(right));
}

export function updateBulkUiState() {
  const selectedCount = selectedVmidsFromInventory().length;
  const enabled = Boolean(state.token) && selectedCount > 0;
  BULK_ACTION_BUTTON_IDS.forEach((id) => {
    const button = qs(id);
    if (button) {
      button.disabled = !enabled;
    }
  });
  if (qs('bulk-selection')) {
    qs('bulk-selection').textContent = String(selectedCount) + ' ausgewaehlt';
  }
}

export function resetInventoryFilters() {
  if (qs('search-input')) {
    qs('search-input').value = '';
  }
  if (qs('role-filter')) {
    qs('role-filter').value = 'all';
  }
  if (qs('eligible-only')) {
    qs('eligible-only').checked = false;
  }
  renderInventory();
}

export function openInventoryWithNodeFilter(nodeName) {
  if (!nodeName) {
    return;
  }
  inventoryHooks.setActivePanel('inventory');
  if (qs('search-input')) {
    qs('search-input').value = String(nodeName);
  }
  renderInventory();
  inventoryHooks.setBanner('Inventar nach Node ' + nodeName + ' gefiltert.', 'info');
}

export function exportInventoryJson() {
  const payload = filteredInventory().map((vm) => profileOf(vm));
  downloadTextFile('beagle-inventory.json', JSON.stringify(payload, null, 2), 'application/json;charset=utf-8');
  inventoryHooks.setBanner('Inventar als JSON exportiert.', 'ok');
}

export function exportInventoryCsv() {
  const rows = filteredInventory().map((vm) => {
    const profile = profileOf(vm);
    return [
      profile.vmid,
      profile.name,
      profile.node,
      profile.status,
      profile.beagle_role,
      profile.stream_host,
      profile.moonlight_port,
      profile.identity_hostname
    ].map((cell) => {
      const textValue = String(cell == null ? '' : cell);
      return '"' + textValue.replace(/"/g, '""') + '"';
    }).join(',');
  });
  rows.unshift('"vmid","name","node","status","role","stream_host","moonlight_port","hostname"');
  downloadTextFile('beagle-inventory.csv', rows.join('\n') + '\n', 'text/csv;charset=utf-8');
  inventoryHooks.setBanner('Inventar als CSV exportiert.', 'ok');
}

export function exportEndpointsJson() {
  downloadTextFile('beagle-endpoints.json', JSON.stringify(state.endpointReports || [], null, 2), 'application/json;charset=utf-8');
  inventoryHooks.setBanner('Endpoints als JSON exportiert.', 'ok');
}

export function runVmPowerAction(vmid, actionName) {
  const numericVmid = Number(vmid);
  if (!numericVmid || !actionName) {
    return Promise.resolve();
  }
  const confirmStop = actionName === 'stop'
    ? inventoryHooks.requestConfirm({
        title: 'VM ' + numericVmid + ' stoppen?',
        message: 'Die VM wird hart heruntergefahren.',
        confirmLabel: 'Stoppen',
        danger: true
      })
    : Promise.resolve(true);
  return confirmStop.then((ok) => {
    if (!ok) {
      return Promise.resolve();
    }
    return runSingleFlight('vm-power:' + numericVmid + ':' + actionName, () => {
      inventoryHooks.setBanner('VM ' + numericVmid + ': ' + powerActionLabel(actionName) + ' wird ausgefuehrt ...', 'info');
      return request('/virtualization/vms/' + numericVmid + '/power', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: actionName })
      }).then(() => {
        inventoryHooks.addToActivityLog('vm-' + actionName, numericVmid, 'ok', 'VM power action');
        inventoryHooks.setBanner('VM ' + numericVmid + ': ' + powerActionLabel(actionName) + ' erfolgreich.', 'ok');
        return inventoryHooks.loadDashboard().then(() => {
          if (state.selectedVmid === numericVmid) {
            return inventoryHooks.loadDetail(numericVmid);
          }
          return null;
        });
      }).catch((error) => {
        inventoryHooks.addToActivityLog('vm-' + actionName, numericVmid, 'warn', error.message);
        inventoryHooks.setBanner('VM ' + numericVmid + ': ' + powerActionLabel(actionName) + ' fehlgeschlagen: ' + error.message, 'warn');
      });
    });
  });
}

export function bulkVmPowerAction(actionName) {
  const vmids = selectedVmidsFromInventory();
  if (!vmids.length) {
    inventoryHooks.setBanner('Keine VM fuer die Bulk-Power-Aktion ausgewaehlt.', 'warn');
    return;
  }
  runSingleFlight('bulk-vm-power:' + actionName, () => {
    inventoryHooks.setBanner('Bulk VM ' + powerActionLabel(actionName) + ' fuer ' + vmids.length + ' VM(s) wird ausgefuehrt ...', 'info');
    return Promise.all(vmids.map((vmid) => {
      return request('/virtualization/vms/' + Number(vmid) + '/power', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: actionName })
      }).then(() => {
        return { ok: true, vmid };
      }).catch((error) => {
        return { ok: false, vmid, error: error.message };
      });
    })).then((results) => {
      const okCount = results.filter((item) => item.ok).length;
      const failItems = results.filter((item) => !item.ok);
      if (failItems.length) {
        inventoryHooks.setBanner('Bulk VM ' + powerActionLabel(actionName) + ': ' + okCount + ' ok, ' + failItems.length + ' fehlgeschlagen.', 'warn');
      } else {
        inventoryHooks.setBanner('Bulk VM ' + powerActionLabel(actionName) + ' erfolgreich fuer ' + okCount + ' VM(s).', 'ok');
      }
      return inventoryHooks.loadDashboard();
    });
  });
}

export function bulkAction(action) {
  const vmids = selectedVmidsFromInventory();
  if (!vmids.length) {
    inventoryHooks.setBanner('Keine VM fuer die Bulk-Aktion ausgewaehlt.', 'warn');
    return;
  }
  runSingleFlight('bulk-action:' + action, () => {
    inventoryHooks.setBanner('Bulk-Aktion ' + actionLabel(action) + ' fuer ' + vmids.length + ' VM(s) wird eingereiht ...', 'info');
    return postJson('/actions/bulk', {
      vmids,
      action
    }).then((payload) => {
      const queued = payload && payload.queued_count != null ? payload.queued_count : vmids.length;
      inventoryHooks.setBanner('Bulk-Aktion ' + actionLabel(action) + ' eingereiht: ' + queued + ' VM(s).', 'ok');
      return inventoryHooks.loadDashboard();
    }).catch((error) => {
      inventoryHooks.setBanner('Bulk-Aktion fehlgeschlagen: ' + error.message, 'warn');
    });
  });
}

export function renderInventory() {
  const rows = filteredInventory();
  const body = qs('inventory-body');
  if (!body) {
    return;
  }
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="7" class="empty-cell">Keine passenden Beagle-VMs gefunden.</td></tr>';
    updateBulkUiState();
    return;
  }
  body.innerHTML = rows.map((vm) => {
    const profile = profileOf(vm);
    const normalizedStatus = String(profile.status || '').trim().toLowerCase();
    const statusTone = normalizedStatus === 'running' ? 'ok' : (normalizedStatus === 'installing' ? 'info' : 'warn');
    const installerTone = profile.installer_target_eligible ? 'ok' : 'muted';
    const canStart = normalizedStatus !== 'running' && normalizedStatus !== 'installing';
    const canStop = normalizedStatus === 'running' || normalizedStatus === 'installing';
    return '' +
      '<tr class="vm-row' + (state.selectedVmid === profile.vmid ? ' selected' : '') + '" data-vmid="' + escapeHtml(profile.vmid) + '">' +
      '  <td><input class="row-select" type="checkbox" data-select-vmid="' + escapeHtml(profile.vmid) + '"' + (state.selectedVmids.indexOf(profile.vmid) !== -1 ? ' checked' : '') + '></td>' +
      '  <td><span class="vm-name">' + escapeHtml(profile.name || ('VM ' + profile.vmid)) + '</span><div class="vm-sub">#' + escapeHtml(profile.vmid) + ' · ' + escapeHtml(profile.node || '') + '</div></td>' +
      '  <td>' + chip(roleOf(vm) || 'unassigned', roleOf(vm) === 'desktop' ? 'info' : 'muted') + '</td>' +
      '  <td>' + chip(profile.status || 'unknown', statusTone) + '</td>' +
      '  <td><div>' + escapeHtml(profile.stream_host || 'n/a') + '</div><div class="vm-sub">' + escapeHtml(profile.moonlight_port || '') + '</div></td>' +
      '  <td>' + chip(profile.installer_target_status || (profile.installer_target_eligible ? 'ready' : 'not eligible'), installerTone) + '</td>' +
      '  <td class="power-cell"><div class="power-inline">' +
      '    <button type="button" class="btn btn-ghost btn-small" data-vm-power="start" data-vmid="' + escapeHtml(profile.vmid) + '"' + (canStart ? '' : ' disabled') + '>Start</button>' +
      '    <button type="button" class="btn btn-ghost btn-small" data-vm-power="stop" data-vmid="' + escapeHtml(profile.vmid) + '"' + (canStop ? '' : ' disabled') + '>Stop</button>' +
      '    <button type="button" class="btn btn-primary btn-small" data-vm-power="reboot" data-vmid="' + escapeHtml(profile.vmid) + '">Reboot</button>' +
      '    <button type="button" class="btn btn-ghost btn-small" data-vm-console="novnc" data-vmid="' + escapeHtml(profile.vmid) + '">noVNC</button>' +
      '  </div></td>' +
      '</tr>';
  }).join('');
  if (qs('inventory-select-all')) {
    qs('inventory-select-all').checked = rows.length > 0 && rows.every((vm) => {
      return state.selectedVmids.indexOf(profileOf(vm).vmid) !== -1;
    });
  }
  updateBulkUiState();
}

export function renderEndpointsOverview() {
  const body = qs('endpoints-body');
  if (!body) {
    return;
  }
  const rows = Array.isArray(state.endpointReports) ? state.endpointReports : [];
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-cell">Keine Endpoint-Daten verfuegbar.</td></tr>';
    return;
  }
  body.innerHTML = rows.map((item) => {
    const status = String(item.status || item.health_status || 'unknown');
    const tone = status === 'healthy' ? 'ok' : status === 'stale' ? 'warn' : 'muted';
    const vmid = item.vmid || (item.assigned_target && item.assigned_target.vmid) || '-';
    return '' +
      '<tr>' +
      '  <td><strong>' + escapeHtml(item.hostname || item.endpoint_id || 'endpoint') + '</strong></td>' +
      '  <td>' + chip(status, tone) + '</td>' +
      '  <td>' + escapeHtml(vmid) + '</td>' +
      '  <td>' + escapeHtml(item.stream_host || '-') + '</td>' +
      '  <td>' + escapeHtml(formatDate(item.reported_at || item.updated_at || '')) + '</td>' +
      '</tr>';
  }).join('');
}