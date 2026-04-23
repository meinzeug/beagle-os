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
}
