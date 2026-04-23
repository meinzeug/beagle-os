import { qs, escapeHtml } from './dom.js';
import { postJson } from './api.js';
import { state } from './state.js';

const clusterHooks = {
  openInventoryWithNodeFilter() {},
  setBanner() {},
  loadDashboard() {}
};

let clusterEventsBound = false;

export function configureCluster(nextHooks) {
  Object.assign(clusterHooks, nextHooks || {});
}

export function bindClusterEvents() {
  if (clusterEventsBound) {
    return;
  }
  document.addEventListener('click', (event) => {
    const maintenanceTrigger = event.target.closest('[data-cluster-maintenance-node]');
    if (maintenanceTrigger) {
      const nodeName = String(maintenanceTrigger.getAttribute('data-cluster-maintenance-node') || '').trim();
      if (!nodeName) {
        return;
      }
      if (!window.confirm('Knoten ' + nodeName + ' in Maintenance versetzen und Drain starten?')) {
        return;
      }
      maintenanceTrigger.disabled = true;
      postJson('/ha/maintenance/drain', { node_name: nodeName }).then((payload) => {
        const handled = Number(payload && payload.handled_vm_count ? payload.handled_vm_count : 0);
        clusterHooks.setBanner('Maintenance-Drain fuer ' + nodeName + ' gestartet (' + handled + ' VMs behandelt).', 'success');
        return clusterHooks.loadDashboard();
      }).catch((error) => {
        clusterHooks.setBanner('Maintenance-Drain fehlgeschlagen: ' + error.message, 'error');
      }).finally(() => {
        maintenanceTrigger.disabled = false;
      });
      return;
    }

    const trigger = event.target.closest('[data-cluster-node]');
    if (!trigger) {
      return;
    }
    const nodeName = String(trigger.getAttribute('data-cluster-node') || '').trim();
    if (!nodeName) {
      return;
    }
    clusterHooks.openInventoryWithNodeFilter(nodeName);
  });
  clusterEventsBound = true;
}

function statusChipClass(status) {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'online') {
    return 'chip good';
  }
  if (normalized === 'offline' || normalized === 'unreachable') {
    return 'chip bad';
  }
  return 'chip muted';
}

function clampPercent(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) {
    return 0;
  }
  if (numeric < 0) {
    return 0;
  }
  if (numeric > 100) {
    return 100;
  }
  return Math.round(numeric);
}

function clusterHaChipClass(status) {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'online' || normalized === 'active') {
    return 'chip good';
  }
  if (normalized === 'maintenance') {
    return 'chip muted';
  }
  if (normalized === 'fencing' || normalized === 'fenced' || normalized === 'offline' || normalized === 'unreachable') {
    return 'chip bad';
  }
  return 'chip muted';
}

function renderHaStatusPanel() {
  const haStatus = state.haStatus || {};
  const summary = haStatus.summary || {};
  const quorum = haStatus.quorum || {};
  const fencing = haStatus.fencing || {};
  const nodes = Array.isArray(haStatus.nodes) ? haStatus.nodes : [];
  const alerts = Array.isArray(haStatus.alerts) ? haStatus.alerts : [];

  const healthEl = qs('cluster-ha-health');
  const healthMetaEl = qs('cluster-ha-health-meta');
  const protectedEl = qs('cluster-ha-protected-vms');
  const quorumEl = qs('cluster-ha-quorum');
  const quorumMetaEl = qs('cluster-ha-quorum-meta');
  const fencingEl = qs('cluster-ha-fencing');
  const alertEl = qs('cluster-ha-alert');
  const bodyEl = qs('cluster-ha-nodes-body');

  const stateValue = String(haStatus.ha_state || 'unknown').toLowerCase();
  const stateText = stateValue ? stateValue.toUpperCase() : 'UNKNOWN';
  const quorumOnline = Number(quorum.online_nodes || 0);
  const quorumMin = Number(quorum.minimum_nodes || 0);
  const protectedVms = Number(summary.ha_protected_vms || 0);
  const fencingActive = Number((Array.isArray(fencing.nodes) ? fencing.nodes : []).filter((item) => Boolean(item && item.active)).length);

  if (healthEl) {
    healthEl.textContent = stateText;
    healthEl.classList.remove('cluster-ha-health-ok', 'cluster-ha-health-degraded', 'cluster-ha-health-failed');
    if (stateValue === 'ok') {
      healthEl.classList.add('cluster-ha-health-ok');
    } else if (stateValue === 'degraded') {
      healthEl.classList.add('cluster-ha-health-degraded');
    } else if (stateValue === 'failed') {
      healthEl.classList.add('cluster-ha-health-failed');
    }
  }
  if (healthMetaEl) {
    healthMetaEl.textContent = String(haStatus.generated_at || 'Keine Zeitbasis verfuegbar');
  }
  if (protectedEl) {
    protectedEl.textContent = String(protectedVms);
  }
  if (quorumEl) {
    quorumEl.textContent = String(quorumOnline) + '/' + String(quorumMin || 0);
  }
  if (quorumMetaEl) {
    quorumMetaEl.textContent = quorum.ok ? 'Quorum erfuellt' : 'Quorum unterschritten';
  }
  if (fencingEl) {
    fencingEl.textContent = String(fencingActive);
    fencingEl.classList.toggle('cluster-ha-fencing', fencingActive > 0);
  }

  if (alertEl) {
    if (alerts.length) {
      alertEl.textContent = alerts.join(' ');
      alertEl.classList.remove('hidden');
    } else {
      alertEl.textContent = 'Kein HA-Alert aktiv.';
      alertEl.classList.add('hidden');
    }
  }

  if (!bodyEl) {
    return;
  }
  if (!nodes.length) {
    bodyEl.innerHTML = '<tr><td colspan="5" class="empty-cell">Noch keine HA-Daten.</td></tr>';
    return;
  }

  bodyEl.innerHTML = nodes.map((node) => {
    const name = String(node && node.name ? node.name : '').trim() || '-';
    const status = String(node && node.status ? node.status : 'unknown').trim() || 'unknown';
    const lastHeartbeat = String(node && node.last_heartbeat_utc ? node.last_heartbeat_utc : '').trim() || '-';
    const protectedVmCount = Number(node && node.ha_protected_vms ? node.ha_protected_vms : 0);
    const fencingMethod = String(node && node.last_fencing_method ? node.last_fencing_method : '').trim();
    const fencingState = node && node.fencing_active ? 'aktiv' : (fencingMethod ? 'zuletzt: ' + fencingMethod : '-');
    return (
      '<tr>' +
      '<td>' + escapeHtml(name) + '</td>' +
      '<td><span class="' + clusterHaChipClass(status) + '">' + escapeHtml(status) + '</span></td>' +
      '<td><span class="cluster-ha-heartbeat">' + escapeHtml(lastHeartbeat) + '</span></td>' +
      '<td>' + String(protectedVmCount) + '</td>' +
      '<td>' + escapeHtml(fencingState) + '</td>' +
      '</tr>'
    );
  }).join('');
}

export function renderClusterPanel() {
  const body = qs('cluster-nodes-body');
  if (!body) {
    return;
  }

  const overview = state.virtualizationOverview || {};
  const nodes = Array.isArray(overview.nodes) ? overview.nodes : [];
  const vms = Array.isArray(state.inventory) ? state.inventory : [];

  const vmCountByNode = Object.create(null);
  vms.forEach((vm) => {
    const nodeName = String(vm && vm.node ? vm.node : '').trim();
    if (!nodeName) {
      return;
    }
    vmCountByNode[nodeName] = (vmCountByNode[nodeName] || 0) + 1;
  });

  const onlineCount = nodes.filter((node) => String(node.status || '').toLowerCase() === 'online').length;
  const unreachableCount = nodes.filter((node) => {
    const status = String(node.status || '').toLowerCase();
    return status === 'offline' || status === 'unreachable';
  }).length;

  const totalNodesEl = qs('cluster-total-nodes');
  const onlineNodesEl = qs('cluster-online-nodes');
  const unreachableNodesEl = qs('cluster-unreachable-nodes');
  const totalVmsEl = qs('cluster-total-vms');

  if (totalNodesEl) {
    totalNodesEl.textContent = String(nodes.length);
  }
  if (onlineNodesEl) {
    onlineNodesEl.textContent = String(onlineCount);
  }
  if (unreachableNodesEl) {
    unreachableNodesEl.textContent = String(unreachableCount);
  }
  if (totalVmsEl) {
    totalVmsEl.textContent = String(vms.length);
  }

  if (!nodes.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty-cell">Keine Cluster-Node-Daten verfuegbar.</td></tr>';
    renderHaStatusPanel();
    return;
  }

  body.innerHTML = nodes.map((node) => {
    const nodeName = String(node.name || node.id || '').trim();
    const status = String(node.status || 'unknown').trim() || 'unknown';
    const cpuPercent = clampPercent(Number(node.cpu || 0) * 100);
    const ramPercent = clampPercent(
      Number(node.maxmem || 0) > 0 ? (Number(node.mem || 0) / Number(node.maxmem || 1)) * 100 : 0
    );
    const vmCount = Number(vmCountByNode[nodeName] || 0);
    return (
      '<tr>' +
      '<td>' + escapeHtml(nodeName || '-') + '</td>' +
      '<td><span class="' + statusChipClass(status) + '">' + escapeHtml(status) + '</span></td>' +
      '<td>' + String(cpuPercent) + '%</td>' +
      '<td>' + String(ramPercent) + '%</td>' +
      '<td>' + String(vmCount) + '</td>' +
      '<td>' +
      '<button type="button" class="button ghost small" data-cluster-node="' + escapeHtml(nodeName) + '">VMs anzeigen</button> ' +
      '<button type="button" class="button ghost small" data-cluster-maintenance-node="' + escapeHtml(nodeName) + '">In Maintenance versetzen</button>' +
      '</td>' +
      '</tr>'
    );
  }).join('');

  renderHaStatusPanel();
}
