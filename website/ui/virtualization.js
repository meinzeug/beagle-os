import {
  DISK_KEY_PATTERN,
  NET_KEY_PATTERN,
  VM_MAIN_KEYS,
  state
} from './state.js';
import {
  chip,
  escapeHtml,
  fieldBlock,
  formatBytes,
  formatGiB,
  qs,
  text,
  usageBar
} from './dom.js';
import { request } from './api.js';

const virtualizationHooks = {
  openInventoryWithNodeFilter() {},
  setBanner() {},
  loadDashboard() {}
};

export function configureVirtualization(nextHooks) {
  Object.assign(virtualizationHooks, nextHooks || {});
}

export function renderVirtualizationPanel() {
  const overview = state.virtualizationOverview;
  const nodesGrid = qs('nodes-grid');
  const storageBody = qs('storage-body');
  const riskBannerEl = qs('virt-risk-banner');
  if (!nodesGrid || !storageBody) {
    return;
  }
  if (!overview || !state.token) {
    nodesGrid.innerHTML = '<div class="empty-card">Keine Daten. Verbinde dich zuerst mit dem API-Token.</div>';
    storageBody.innerHTML = '<tr><td colspan="8" class="empty-cell">Keine Daten verfuegbar.</td></tr>';
    return;
  }
  const nodes = Array.isArray(overview.nodes) ? overview.nodes : [];
  const storage = Array.isArray(overview.storage) ? overview.storage : [];

  // Build risk/health banner messages
  const risks = [];
  nodes.forEach((node) => {
    const name = String(node.name || node.id || 'node');
    const health = node.health || {};
    if (health.kvm === false) {
      risks.push(name + ': KVM nicht verfuegbar (/dev/kvm fehlt)');
    }
    if (health.libvirt === false) {
      risks.push(name + ': libvirtd nicht erreichbar');
    }
    if (String(node.status || '').toLowerCase() !== 'online') {
      risks.push(name + ': Node offline / nicht erreichbar');
    }
  });
  storage.forEach((item) => {
    const usedPct = Number(item.total || 0) > 0 ? (Number(item.used || 0) / Number(item.total || 0)) * 100 : 0;
    if (usedPct >= 90) {
      risks.push('Storage ' + String(item.name || item.id || '') + ': ' + usedPct.toFixed(0) + '% belegt (kritisch)');
    }
  });
  if (riskBannerEl) {
    if (risks.length) {
      riskBannerEl.textContent = risks.join(' · ');
      riskBannerEl.classList.remove('hidden');
      riskBannerEl.classList.add('banner-warn');
    } else {
      riskBannerEl.textContent = '';
      riskBannerEl.classList.add('hidden');
      riskBannerEl.classList.remove('banner-warn');
    }
  }

  if (!nodes.length) {
    nodesGrid.innerHTML = '<div class="empty-card">Keine Nodes gefunden.</div>';
  } else {
    nodesGrid.innerHTML = nodes.map((node) => {
      const statusTone = node.status === 'online' ? 'ok' : 'warn';
      const cpuUsed = node.maxcpu > 0 ? Math.round((node.cpu || 0) * 100) : 0;
      const health = node.health || {};
      const kvmOk = health.kvm !== false;
      const libvirtOk = health.libvirt !== false;
      const healthBadges =
        '<span class="chip ' + (kvmOk ? 'ok' : 'bad') + '" title="KVM">KVM</span> ' +
        '<span class="chip ' + (libvirtOk ? 'ok' : 'bad') + '" title="libvirt">libvirt</span>';
      const nodeName = String(node.name || node.id || 'node');
      return '<article class="node-card">' +
        '<div class="node-head">' +
        '<strong class="node-name">' + escapeHtml(nodeName) + '</strong>' +
        '<span class="chip ' + statusTone + '">' + escapeHtml(node.status || 'unknown') + '</span>' +
        '</div>' +
        '<div class="node-meta"><span class="usage-key">CPU</span>' + usageBar(cpuUsed, 100, cpuUsed + '%') + '</div>' +
        '<div class="node-meta"><span class="usage-key">RAM</span>' + usageBar(node.mem, node.maxmem, formatBytes(node.mem) + ' / ' + formatBytes(node.maxmem)) + '</div>' +
        '<div class="node-health">' + healthBadges + '</div>' +
        '<div class="node-footer">' +
        '<span>' + String(node.maxcpu || 0) + '\u00a0vCPU</span>' +
        '<span>' + escapeHtml(node.provider || (overview && overview.provider) || '') + '</span>' +
        '</div>' +
        '<div class="node-actions">' +
        '<button type="button" class="button ghost small" data-virt-node-filter="' + escapeHtml(nodeName) + '">VMs filtern</button> ' +
        '<button type="button" class="button ghost small" data-virt-local-preflight="' + escapeHtml(nodeName) + '">Preflight</button>' +
        '</div>' +
        '</article>';
    }).join('');
  }
  if (!storage.length) {
    storageBody.innerHTML = '<tr><td colspan="8" class="empty-cell">Kein Storage gefunden.</td></tr>';
  } else {
    storageBody.innerHTML = storage.map((item) => {
      const quotaBytes = Number(item.quota_bytes || 0);
      const quotaText = quotaBytes > 0 ? formatBytes(quotaBytes) : 'Unbegrenzt';
      const usedPct = Number(item.total || 0) > 0 ? (Number(item.used || 0) / Number(item.total || 0)) * 100 : 0;
      const healthTone = usedPct >= 90 ? 'bad' : (usedPct >= 75 ? 'warn' : 'ok');
      const healthLabel = usedPct >= 90 ? 'kritisch' : (usedPct >= 75 ? 'hoch' : 'ok');
      return '<tr>' +
        '<td><strong>' + escapeHtml(item.name || item.id || '') + '</strong></td>' +
        '<td>' + escapeHtml(item.node || '') + '</td>' +
        '<td>' + chip(item.type || 'n/a', 'muted') + '</td>' +
        '<td class="storage-content">' + escapeHtml(item.content || '') + '</td>' +
        '<td class="storage-usage">' + usageBar(item.used, item.total, formatBytes(item.used) + ' / ' + formatBytes(item.total)) + '</td>' +
        '<td>' + formatBytes(item.avail) + '</td>' +
        '<td>' + escapeHtml(quotaText) + '</td>' +
        '<td>' + chip(healthLabel, healthTone) + '</td>' +
        '<td><button type="button" class="button ghost small" data-storage-quota-set="1" data-storage-pool="' + escapeHtml(item.name || item.id || '') + '" data-storage-quota-bytes="' + String(quotaBytes) + '">Quota</button></td>' +
        '</tr>';
    }).join('');
  }
}

export function setStoragePoolQuota(poolName, currentQuotaBytes) {
  const pool = String(poolName || '').trim();
  if (!pool) {
    virtualizationHooks.setBanner('Storage-Pool fehlt.', 'warn');
    return;
  }
  const currentGiB = Number(currentQuotaBytes || 0) > 0 ? (Number(currentQuotaBytes || 0) / (1024 ** 3)).toFixed(1) : '0';
  const input = window.prompt('Quota fuer Pool "' + pool + '" in GiB setzen (0 = unbegrenzt):', currentGiB);
  if (input == null) {
    return;
  }
  const normalized = String(input || '').trim().replace(',', '.');
  const quotaGiB = Number(normalized || '0');
  if (!Number.isFinite(quotaGiB) || quotaGiB < 0) {
    virtualizationHooks.setBanner('Ungueltiger Quota-Wert.', 'warn');
    return;
  }
  const quotaBytes = Math.round(quotaGiB * (1024 ** 3));
  request('/storage/pools/' + encodeURIComponent(pool) + '/quota', {
    method: 'PUT',
    body: { quota_bytes: quotaBytes }
  }).then(() => {
    virtualizationHooks.setBanner('Quota fuer Pool ' + pool + ' aktualisiert.', 'ok');
    virtualizationHooks.loadDashboard();
  }).catch((error) => {
    virtualizationHooks.setBanner('Quota-Update fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function renderVmConfigPanel(config, interfaces) {
  const diskKeys = Object.keys(config).filter((key) => DISK_KEY_PATTERN.test(key)).sort();
  const netKeys = Object.keys(config).filter((key) => NET_KEY_PATTERN.test(key)).sort();
  let html = '<section class="detail-section"><h3>VM Konfiguration</h3>';
  VM_MAIN_KEYS.forEach((key) => {
    if (config[key] != null && config[key] !== '') {
      html += fieldBlock(key, String(config[key]));
    }
  });
  html += '</section>';
  if (diskKeys.length) {
    html += '<section class="detail-section"><h3>Disks</h3>';
    diskKeys.forEach((key) => {
      html += fieldBlock(key, String(config[key] || ''), 'mono');
    });
    html += '</section>';
  }
  if (netKeys.length) {
    html += '<section class="detail-section"><h3>Netzwerk (Config)</h3>';
    netKeys.forEach((key) => {
      html += fieldBlock(key, String(config[key] || ''), 'mono');
    });
    html += '</section>';
  }
  if (Array.isArray(interfaces) && interfaces.length) {
    html += '<section class="detail-section"><h3>Netzwerk Interfaces (Guest Agent)</h3>';
    interfaces.forEach((iface) => {
      const addrs = (iface['ip-addresses'] || []).map((addr) => {
        return String(addr['ip-address'] || '') + (addr.prefix ? '/' + addr.prefix : '');
      }).join(', ');
      html += fieldBlock(String(iface.name || ''), addrs || 'n/a');
    });
    html += '</section>';
  }
  return html;
}

export function loadVmConfig(vmid) {
  const stack = qs('detail-stack');
  if (!stack) {
    return;
  }
  const configPanel = stack.querySelector('[data-detail-panel="config"]');
  if (!configPanel) {
    return;
  }
  if (configPanel.getAttribute('data-loaded') === String(vmid)) {
    return;
  }
  configPanel.innerHTML = '<div class="banner banner-info">Lade VM-Konfiguration...</div>';
  Promise.all([
    request('/virtualization/vms/' + vmid + '/config'),
    request('/virtualization/vms/' + vmid + '/interfaces').catch(() => null)
  ]).then((results) => {
    const config = (results[0] && results[0].config) || {};
    const interfaces = (results[1] && results[1].interfaces) || [];
    configPanel.setAttribute('data-loaded', String(vmid));
    configPanel.innerHTML = renderVmConfigPanel(config, interfaces);
  }).catch((error) => {
    configPanel.innerHTML = '<div class="banner warn">Fehler: ' + escapeHtml(error.message) + '</div>';
  });
}

export function renderVirtualizationOverview() {
  const overview = state.virtualizationOverview || {};
  const hosts = Array.isArray(overview.hosts) ? overview.hosts : [];
  const nodes = Array.isArray(overview.nodes) ? overview.nodes : [];
  const storage = Array.isArray(overview.storage) ? overview.storage : [];
  const bridges = Array.isArray(overview.bridges) ? overview.bridges : [];
  const gpus = Array.isArray(overview.gpus) ? overview.gpus : [];
  const nodeFilter = String(state.virtualizationNodeFilter || '').trim();
  const filteredStorage = nodeFilter ? storage.filter((item) => String(item.node || '').trim() === nodeFilter) : storage;
  const filteredBridges = nodeFilter ? bridges.filter((item) => String(item.node || '').trim() === nodeFilter) : bridges;
  const filteredGpus = nodeFilter ? gpus.filter((item) => String(item.node || '').trim() === nodeFilter) : gpus;
  const hostBody = qs('virtualization-hosts-body');
  const nodeBody = qs('virtualization-nodes-body');
  const storageBody = qs('virtualization-storage-body');
  const bridgeBody = qs('virtualization-bridges-body');
  const gpuBody = qs('virtualization-gpus-body');
  text('virtualization-node-filter', nodeFilter || 'Alle Nodes');
  if (qs('clear-virt-node-filter')) {
    qs('clear-virt-node-filter').disabled = !nodeFilter;
  }

  if (hostBody) {
    hostBody.innerHTML = hosts.length ? hosts.map((item) => {
      return '<tr><td>' + escapeHtml(item.label || item.name || item.id || 'host') + '</td><td>' + chip(item.status || 'unknown', String(item.status || '').toLowerCase() === 'online' ? 'ok' : 'muted') + '</td><td>' + escapeHtml(item.provider || overview.provider || 'n/a') + '</td></tr>';
    }).join('') : '<tr><td colspan="3" class="empty-cell">Keine Host-Daten vorhanden.</td></tr>';
  }

  if (nodeBody) {
    nodeBody.innerHTML = nodes.length ? nodes.map((item) => {
      const cpuPercent = Math.max(0, Number(item.cpu || 0) * 100);
      const memPercent = Number(item.maxmem || 0) > 0 ? (Number(item.mem || 0) / Number(item.maxmem || 0)) * 100 : 0;
      return '<tr data-node="' + escapeHtml(item.label || item.name || item.id || '') + '"' + ((nodeFilter && (item.label || item.name || item.id || '') === nodeFilter) ? ' class="node-filter-selected"' : '') + '><td>' + escapeHtml(item.label || item.name || item.id || 'node') + '</td><td>' + chip(item.status || 'unknown', String(item.status || '').toLowerCase() === 'online' ? 'ok' : 'muted') + '</td><td>' + escapeHtml(cpuPercent.toFixed(0) + '%') + '</td><td>' + escapeHtml(memPercent.toFixed(0) + '%') + '</td></tr>';
    }).join('') : '<tr><td colspan="4" class="empty-cell">Keine Node-Daten vorhanden.</td></tr>';
  }

  if (storageBody) {
    storageBody.innerHTML = filteredStorage.length ? filteredStorage.map((item) => {
      const usedPercent = Number(item.total || 0) > 0 ? (Number(item.used || 0) / Number(item.total || 0)) * 100 : 0;
      const quotaBytes = Number(item.quota_bytes || 0);
      const quotaText = quotaBytes > 0 ? formatGiB(quotaBytes) : 'unbegrenzt';
      return '<tr><td>' + escapeHtml(item.name || item.id || 'storage') + '</td><td>' + escapeHtml(item.node || '-') + '</td><td>' + escapeHtml(item.type || '-') + '</td><td>' + escapeHtml(formatGiB(item.used) + ' / ' + formatGiB(item.total) + ' (' + usedPercent.toFixed(0) + '%)') + '</td><td>' + escapeHtml(quotaText) + '</td></tr>';
    }).join('') : '<tr><td colspan="5" class="empty-cell">Keine Storage-Daten vorhanden.</td></tr>';
  }

  if (gpuBody) {
    gpuBody.innerHTML = filteredGpus.length ? filteredGpus.map((item) => {
      const iommu = item.iommu_group ? ('Group ' + String(item.iommu_group) + ' (' + String(item.iommu_group_size || 0) + ')') : '-';
      const tone = item.passthrough_ready ? 'ok' : 'warn';
      const pci = escapeHtml(item.pci_address || '');
      let actionBtn = '';
      if (item.status === 'available-for-passthrough') {
        actionBtn = '<button type="button" class="button ghost small" data-gpu-assign="1" data-gpu-pci="' + pci + '">Zuweisen</button>';
      } else if (item.status === 'assigned') {
        actionBtn = '<button type="button" class="button ghost small" data-gpu-release="1" data-gpu-pci="' + pci + '">Freigeben</button>';
      }
      return '<tr data-node="' + escapeHtml(item.node || '') + '"' + ((nodeFilter && String(item.node || '') === nodeFilter) ? ' class="node-filter-selected"' : '') + '><td>' + escapeHtml(item.node || '-') + '</td><td class="mono">' + escapeHtml(item.pci_address || '-') + '</td><td>' + escapeHtml(item.model || item.vendor || '-') + '</td><td>' + escapeHtml(item.driver || '-') + '</td><td>' + escapeHtml(iommu) + '</td><td>' + chip(item.status || 'unknown', tone) + '</td><td>' + actionBtn + '</td></tr>';
    }).join('') : '<tr><td colspan="7" class="empty-cell">Keine GPU-Daten vorhanden.</td></tr>';
  }

  if (bridgeBody) {
    bridgeBody.innerHTML = filteredBridges.length ? filteredBridges.map((item) => {
      return '<tr data-node="' + escapeHtml(item.node || '') + '"' + ((nodeFilter && String(item.node || '') === nodeFilter) ? ' class="node-filter-selected"' : '') + '><td>' + escapeHtml(item.name || item.id || 'bridge') + '</td><td>' + escapeHtml(item.node || '-') + '</td><td>' + escapeHtml(item.cidr || item.address || '-') + '</td><td>' + escapeHtml(item.bridge_ports || '-') + '</td><td>' + chip(item.active ? 'active' : 'inactive', item.active ? 'ok' : 'muted') + '</td></tr>';
    }).join('') : '<tr><td colspan="5" class="empty-cell">Keine Bridge-Daten vorhanden.</td></tr>';
  }
}

export function setVirtualizationNodeFilter(nodeName) {
  const next = String(nodeName || '').trim();
  state.virtualizationNodeFilter = next;
  renderVirtualizationOverview();
  virtualizationHooks.setBanner(next ? ('Node-Filter aktiv: ' + next) : 'Node-Filter entfernt.', 'info');
}

export function assignGpuToVm(pciAddress) {
  const pci = String(pciAddress || '').trim();
  if (!pci) {
    virtualizationHooks.setBanner('PCI-Adresse fehlt.', 'warn');
    return;
  }
  const input = window.prompt('GPU ' + pci + ' einer VM zuweisen.\nVM-ID eingeben:', '');
  if (input == null) {
    return;
  }
  const vmid = parseInt(String(input || '').trim(), 10);
  if (!Number.isFinite(vmid) || vmid <= 0) {
    virtualizationHooks.setBanner('Ungültige VM-ID.', 'warn');
    return;
  }
  request(
    '/api/v1/virtualization/gpus/' + encodeURIComponent(pci) + '/assign',
    { method: 'POST', body: JSON.stringify({ vmid }) }
  ).then((res) => {
    if (res.ok) {
      virtualizationHooks.setBanner('GPU ' + pci + ' wurde VM ' + vmid + ' zugewiesen.', 'ok');
      virtualizationHooks.loadDashboard();
    } else {
      virtualizationHooks.setBanner('Fehler: ' + (res.error || JSON.stringify(res)), 'warn');
    }
  }).catch((err) => {
    virtualizationHooks.setBanner('Fehler: ' + (err.message || String(err)), 'warn');
  });
}

export function releaseGpuFromVm(pciAddress) {
  const pci = String(pciAddress || '').trim();
  if (!pci) {
    virtualizationHooks.setBanner('PCI-Adresse fehlt.', 'warn');
    return;
  }
  const input = window.prompt('GPU ' + pci + ' freigeben.\nVM-ID eingeben:', '');
  if (input == null) {
    return;
  }
  const vmid = parseInt(String(input || '').trim(), 10);
  if (!Number.isFinite(vmid) || vmid <= 0) {
    virtualizationHooks.setBanner('Ungültige VM-ID.', 'warn');
    return;
  }
  request(
    '/api/v1/virtualization/gpus/' + encodeURIComponent(pci) + '/release',
    { method: 'POST', body: JSON.stringify({ vmid }) }
  ).then((res) => {
    if (res.ok) {
      virtualizationHooks.setBanner('GPU ' + pci + ' von VM ' + vmid + ' freigegeben.', 'ok');
      virtualizationHooks.loadDashboard();
    } else {
      virtualizationHooks.setBanner('Fehler: ' + (res.error || JSON.stringify(res)), 'warn');
    }
  }).catch((err) => {
    virtualizationHooks.setBanner('Fehler: ' + (err.message || String(err)), 'warn');
  });
}

export function renderVirtualizationInspector() {
  const summary = qs('virt-inspector-summary');
  const configBody = qs('virt-inspector-config-body');
  const ifaceBody = qs('virt-inspector-iface-body');
  if (!summary || !configBody || !ifaceBody) {
    return;
  }
  if (!state.token) {
    summary.innerHTML = '<div class="kv"><div class="kv-label">Status</div><div class="kv-value">Bitte anmelden, um VM-Details zu laden.</div></div>';
    configBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Nicht angemeldet.</td></tr>';
    ifaceBody.innerHTML = '<tr><td colspan="3" class="empty-cell">Nicht angemeldet.</td></tr>';
    return;
  }
  const inspector = state.virtualizationInspector || {};
  if (inspector.loading) {
    summary.innerHTML = '<div class="kv"><div class="kv-label">Status</div><div class="kv-value">Lade VM-Inspector ...</div></div>';
    configBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Lade Konfiguration ...</td></tr>';
    ifaceBody.innerHTML = '<tr><td colspan="3" class="empty-cell">Lade Interfaces ...</td></tr>';
    return;
  }
  if (inspector.error) {
    summary.innerHTML = '<div class="kv"><div class="kv-label">Fehler</div><div class="kv-value">' + escapeHtml(inspector.error) + '</div></div>';
    configBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Keine Config verfuegbar.</td></tr>';
    ifaceBody.innerHTML = '<tr><td colspan="3" class="empty-cell">Keine Interface-Daten verfuegbar.</td></tr>';
    return;
  }
  if (!inspector.vmid || !inspector.config) {
    summary.innerHTML = '<div class="kv"><div class="kv-label">Status</div><div class="kv-value">Noch keine VM geladen.</div></div>';
    configBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Noch keine Config geladen.</td></tr>';
    ifaceBody.innerHTML = '<tr><td colspan="3" class="empty-cell">Noch keine Interfaces geladen.</td></tr>';
    return;
  }
  const config = inspector.config || {};
  const interfaces = Array.isArray(inspector.interfaces) ? inspector.interfaces : [];
  const diskKeys = Object.keys(config).filter((key) => DISK_KEY_PATTERN.test(key)).sort();
  const netKeys = Object.keys(config).filter((key) => NET_KEY_PATTERN.test(key)).sort();
  const configKeys = VM_MAIN_KEYS.concat(diskKeys).concat(netKeys).filter((key, index, arr) => {
    return arr.indexOf(key) === index && config[key] != null && config[key] !== '';
  });
  summary.innerHTML = [
    fieldBlock('VMID', String(inspector.vmid)),
    fieldBlock('Name', String(config.name || 'n/a')),
    fieldBlock('Node', String(config.node || 'n/a')),
    fieldBlock('Status', String(config.status || 'unknown'))
  ].join('');
  configBody.innerHTML = configKeys.length ? configKeys.map((key) => {
    return '<tr><td>' + escapeHtml(key) + '</td><td class="storage-content">' + escapeHtml(String(config[key])) + '</td></tr>';
  }).join('') : '<tr><td colspan="2" class="empty-cell">Keine Config-Werte verfuegbar.</td></tr>';
  ifaceBody.innerHTML = interfaces.length ? interfaces.map((iface) => {
    const ipList = Array.isArray(iface['ip-addresses']) ? iface['ip-addresses'] : [];
    const addresses = ipList.map((entry) => {
      const ip = String(entry['ip-address'] || '').trim();
      const prefix = String(entry.prefix || '').trim();
      return ip ? ip + (prefix ? '/' + prefix : '') : '';
    }).filter(Boolean).join(', ');
    return '<tr><td>' + escapeHtml(String(iface.name || iface.ifname || '-')) + '</td><td>' + escapeHtml(String(iface['hardware-address'] || iface.mac || '-')) + '</td><td>' + escapeHtml(addresses || '-') + '</td></tr>';
  }).join('') : '<tr><td colspan="3" class="empty-cell">Keine Guest-Interface-Daten verfuegbar.</td></tr>';
}

export function loadVirtualizationInspector(vmid) {
  const numericVmid = Number(vmid || 0);
  if (!Number.isFinite(numericVmid) || numericVmid <= 0) {
    virtualizationHooks.setBanner('VM Inspector: gueltige VMID erforderlich.', 'warn');
    return;
  }
  state.virtualizationInspector = {
    vmid: numericVmid,
    loading: true,
    config: null,
    interfaces: [],
    error: ''
  };
  renderVirtualizationInspector();
  Promise.all([
    request('/virtualization/vms/' + numericVmid + '/config'),
    request('/virtualization/vms/' + numericVmid + '/interfaces').catch(() => { return { interfaces: [] }; })
  ]).then((results) => {
    state.virtualizationInspector = {
      vmid: numericVmid,
      loading: false,
      config: (results[0] && results[0].config) || {},
      interfaces: (results[1] && results[1].interfaces) || [],
      error: ''
    };
    renderVirtualizationInspector();
    virtualizationHooks.setBanner('VM Inspector geladen fuer VM ' + numericVmid + '.', 'ok');
  }).catch((error) => {
    state.virtualizationInspector = {
      vmid: numericVmid,
      loading: false,
      config: null,
      interfaces: [],
      error: error.message
    };
    renderVirtualizationInspector();
    virtualizationHooks.setBanner('VM Inspector Fehler: ' + error.message, 'warn');
  });
}

export function loadMdevTypes(gpuPci) {
  const typesBody = qs('vgpu-types-body');
  const instancesBody = qs('vgpu-instances-body');
  if (!typesBody || !instancesBody) {
    return;
  }
  const url = gpuPci
    ? '/api/v1/virtualization/mdev/types?gpu_pci=' + encodeURIComponent(gpuPci)
    : '/api/v1/virtualization/mdev/types';
  request(url).then((res) => {
    const types = Array.isArray(res.mdev_types) ? res.mdev_types : [];
    if (!types.length) {
      typesBody.innerHTML = '<tr><td colspan="6" class="empty-cell">Keine vGPU-Typen gefunden (kein NVIDIA-mdev-fähiges Gerät?).</td></tr>';
    } else {
      typesBody.innerHTML = types.map((t) => {
        const pci = escapeHtml(t.gpu_pci || '');
        const tid = escapeHtml(t.type_id || '');
        return '<tr>' +
          '<td class="mono">' + pci + '</td>' +
          '<td class="mono">' + tid + '</td>' +
          '<td>' + escapeHtml(t.name || '-') + '</td>' +
          '<td>' + escapeHtml(String(t.available_instances ?? '-')) + '</td>' +
          '<td>' + escapeHtml(String(t.max_instances ?? '-')) + '</td>' +
          '<td><button type="button" class="button ghost small" data-mdev-create="1" data-mdev-pci="' + pci + '" data-mdev-type="' + tid + '">Erstellen</button></td>' +
          '</tr>';
      }).join('');
    }
  }).catch((err) => {
    typesBody.innerHTML = '<tr><td colspan="6" class="empty-cell">Fehler: ' + escapeHtml(err.message) + '</td></tr>';
  });
  request('/api/v1/virtualization/mdev/instances').then((res) => {
    const instances = Array.isArray(res.mdev_instances) ? res.mdev_instances : [];
    if (!instances.length) {
      instancesBody.innerHTML = '<tr><td colspan="4" class="empty-cell">Keine aktiven mdev-Instanzen.</td></tr>';
    } else {
      instancesBody.innerHTML = instances.map((inst) => {
        const uid = escapeHtml(inst.uuid || '');
        return '<tr>' +
          '<td class="mono">' + uid + '</td>' +
          '<td class="mono">' + escapeHtml(inst.type_id || '-') + '</td>' +
          '<td class="mono">' + escapeHtml(inst.gpu_pci || '-') + '</td>' +
          '<td>' +
          '<button type="button" class="button ghost small" data-mdev-assign="1" data-mdev-uuid="' + uid + '" style="margin-right:4px">Zuweisen</button>' +
          '<button type="button" class="button ghost small danger" data-mdev-delete="1" data-mdev-uuid="' + uid + '">Löschen</button>' +
          '</td></tr>';
      }).join('');
    }
  }).catch((err) => {
    instancesBody.innerHTML = '<tr><td colspan="4" class="empty-cell">Fehler: ' + escapeHtml(err.message) + '</td></tr>';
  });
}

export function createMdevInstance(gpuPci, typeId) {
  const pci = String(gpuPci || '').trim();
  const tid = String(typeId || '').trim();
  if (!pci || !tid) {
    virtualizationHooks.setBanner('GPU-PCI und Typ-ID sind erforderlich.', 'warn');
    return;
  }
  request('/api/v1/virtualization/mdev/create', {
    method: 'POST',
    body: { gpu_pci: pci, type_id: tid }
  }).then((res) => {
    if (res.ok) {
      virtualizationHooks.setBanner('mdev-Instanz erstellt: ' + (res.uuid || ''), 'ok');
      loadMdevTypes();
    } else {
      virtualizationHooks.setBanner('Fehler: ' + (res.error || JSON.stringify(res)), 'warn');
    }
  }).catch((err) => {
    virtualizationHooks.setBanner('Fehler: ' + err.message, 'warn');
  });
}

export function assignMdevToVm(mdevUuid) {
  const uid = String(mdevUuid || '').trim();
  if (!uid) {
    virtualizationHooks.setBanner('UUID fehlt.', 'warn');
    return;
  }
  const input = window.prompt('mdev-Instanz ' + uid + ' einer VM zuweisen.\nVM-ID eingeben:', '');
  if (input == null) {
    return;
  }
  const vmid = parseInt(String(input || '').trim(), 10);
  if (!Number.isFinite(vmid) || vmid <= 0) {
    virtualizationHooks.setBanner('Ungültige VM-ID.', 'warn');
    return;
  }
  request('/api/v1/virtualization/mdev/' + encodeURIComponent(uid) + '/assign', {
    method: 'POST',
    body: { vmid }
  }).then((res) => {
    if (res.ok) {
      virtualizationHooks.setBanner('mdev ' + uid + ' VM ' + vmid + ' zugewiesen.', 'ok');
      loadMdevTypes();
    } else {
      virtualizationHooks.setBanner('Fehler: ' + (res.error || JSON.stringify(res)), 'warn');
    }
  }).catch((err) => {
    virtualizationHooks.setBanner('Fehler: ' + err.message, 'warn');
  });
}

export function deleteMdevInstance(mdevUuid) {
  const uid = String(mdevUuid || '').trim();
  if (!uid) {
    virtualizationHooks.setBanner('UUID fehlt.', 'warn');
    return;
  }
  if (!window.confirm('mdev-Instanz ' + uid + ' wirklich löschen?')) {
    return;
  }
  request('/api/v1/virtualization/mdev/' + encodeURIComponent(uid) + '/delete', {
    method: 'POST',
    body: {}
  }).then((res) => {
    if (res.ok) {
      virtualizationHooks.setBanner('mdev-Instanz ' + uid + ' gelöscht.', 'ok');
      loadMdevTypes();
    } else {
      virtualizationHooks.setBanner('Fehler: ' + (res.error || JSON.stringify(res)), 'warn');
    }
  }).catch((err) => {
    virtualizationHooks.setBanner('Fehler: ' + err.message, 'warn');
  });
}

export function loadSriovDevices() {
  const body = qs('sriov-devices-body');
  if (!body) {
    return;
  }
  request('/api/v1/virtualization/sriov').then((res) => {
    const devices = Array.isArray(res.sriov_devices) ? res.sriov_devices : [];
    if (!devices.length) {
      body.innerHTML = '<tr><td colspan="5" class="empty-cell">Keine SR-IOV-fähigen GPUs gefunden.</td></tr>';
    } else {
      body.innerHTML = devices.map((dev) => {
        const pci = escapeHtml(dev.pci || '');
        return '<tr>' +
          '<td class="mono">' + pci + '</td>' +
          '<td>' + escapeHtml(dev.driver || '-') + '</td>' +
          '<td>' + escapeHtml(String(dev.total_vfs ?? '-')) + '</td>' +
          '<td>' + escapeHtml(String(dev.current_vfs ?? '-')) + '</td>' +
          '<td><button type="button" class="button ghost small" data-sriov-set="1" data-sriov-pci="' + pci + '" data-sriov-total="' + escapeHtml(String(dev.total_vfs ?? '0')) + '">VFs setzen</button></td>' +
          '</tr>';
      }).join('');
    }
  }).catch((err) => {
    body.innerHTML = '<tr><td colspan="5" class="empty-cell">Fehler: ' + escapeHtml(err.message) + '</td></tr>';
  });
}

export function setSriovVfCount(pciAddress, totalVfs) {
  const pci = String(pciAddress || '').trim();
  if (!pci) {
    virtualizationHooks.setBanner('PCI-Adresse fehlt.', 'warn');
    return;
  }
  const max = Number(totalVfs || 0);
  const input = window.prompt('SR-IOV VF-Anzahl für ' + pci + ' setzen (0–' + max + '):', '0');
  if (input == null) {
    return;
  }
  const count = parseInt(String(input || '').trim(), 10);
  if (!Number.isFinite(count) || count < 0 || count > max) {
    virtualizationHooks.setBanner('Ungültige VF-Anzahl (0–' + max + ').', 'warn');
    return;
  }
  request('/api/v1/virtualization/sriov/' + encodeURIComponent(pci) + '/set-vfs', {
    method: 'POST',
    body: { count }
  }).then((res) => {
    if (res.ok) {
      virtualizationHooks.setBanner('SR-IOV VFs für ' + pci + ' auf ' + count + ' gesetzt.', 'ok');
      loadSriovDevices();
    } else {
      virtualizationHooks.setBanner('Fehler: ' + (res.error || JSON.stringify(res)), 'warn');
    }
  }).catch((err) => {
    virtualizationHooks.setBanner('Fehler: ' + err.message, 'warn');
  });
}