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
import { blobRequest, postJson, request } from './api.js';
import { t } from './i18n.js';

const virtualizationHooks = {
  openInventoryWithNodeFilter() {},
  setBanner() {},
  loadDashboard() {}
};

function serviceTone(status) {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'pass' || normalized === 'online' || normalized === 'active') {
    return 'ok';
  }
  if (normalized === 'warn' || normalized === 'warning' || normalized === 'maintenance') {
    return 'warn';
  }
  if (normalized === 'fail' || normalized === 'offline' || normalized === 'unreachable') {
    return 'bad';
  }
  return 'muted';
}

function storageHealth(used, total) {
  const totalBytes = Number(total || 0);
  const usedBytes = Number(used || 0);
  const usedPct = totalBytes > 0 ? (usedBytes / totalBytes) * 100 : 0;
  if (usedPct >= 90) {
    return { tone: 'bad', label: 'kritisch', usedPct };
  }
  if (usedPct >= 75) {
    return { tone: 'warn', label: 'hoch', usedPct };
  }
  return { tone: 'ok', label: 'ok', usedPct };
}

function gpuReadiness(item) {
  const status = String((item && item.status) || '').trim();
  const driver = String((item && item.driver) || '').trim();
  const groupSize = Number((item && item.iommu_group_size) || 0);
  if (status === 'not-isolatable') {
    return {
      tone: 'bad',
      label: 'nicht isolierbar',
      reason: 'IOMMU-Gruppe enthaelt weitere Geraete (' + String(groupSize || 0) + ').',
      nextStep: 'Passthrough erst nach sauberer Isolierung per BIOS/ACS/anderer Hardwaretopologie freigeben.',
    };
  }
  if (status === 'assigned') {
    return {
      tone: 'ok',
      label: 'bereit / vfio-pci',
      reason: driver ? ('GPU ist bereits an ' + driver + ' gebunden.') : 'GPU ist bereits fuer Passthrough vorbereitet.',
      nextStep: 'Kann einer ausgeschalteten VM zugewiesen oder von ihr geloest werden.',
    };
  }
  if (status === 'available-for-passthrough') {
    return {
      tone: 'warn',
      label: 'vorbereitbar',
      reason: driver && driver !== 'vfio-pci' ? ('Aktuell noch an Host-Treiber ' + driver + ' gebunden.') : 'GPU ist isolierbar und fuer Passthrough geeignet.',
      nextStep: driver && driver !== 'vfio-pci'
        ? 'Vor Zuweisung den Host-Treiber loesen bzw. auf vfio-pci umstellen; je nach Host ist ein Reboot noetig.'
        : 'Kann einer passenden VM zugewiesen werden.',
    };
  }
  if (status === 'no-iommu-group') {
    return {
      tone: 'bad',
      label: 'kein IOMMU-Schutz',
      reason: 'Fuer diese GPU wurde keine IOMMU-Gruppe erkannt.',
      nextStep: 'IOMMU im BIOS/Kernel aktivieren, bevor Passthrough oder vGPU verwendet wird.',
    };
  }
  return {
    tone: 'warn',
    label: status || 'unbekannt',
    reason: 'GPU-Status konnte nicht eindeutig klassifiziert werden.',
    nextStep: 'Knoten-Details und Host-Logs pruefen, bevor Aenderungen an der VM-Zuordnung vorgenommen werden.',
  };
}

function vmInspectorStatePatch() {
  const current = state.virtualizationInspector || {};
  return {
    lastVmid: current.lastVmid || null,
    recentVmids: Array.isArray(current.recentVmids) ? current.recentVmids.slice(0, 6) : [],
  };
}

function rememberInspectorVmid(vmid) {
  const numericVmid = Number(vmid || 0);
  if (!Number.isFinite(numericVmid) || numericVmid <= 0) {
    return vmInspectorStatePatch();
  }
  const current = vmInspectorStatePatch();
  const recent = [numericVmid].concat(current.recentVmids.filter((item) => Number(item || 0) !== numericVmid)).slice(0, 6);
  return {
    lastVmid: numericVmid,
    recentVmids: recent,
  };
}

function renderInspectorRecentVmids() {
  const recentEl = qs('virt-inspector-recent');
  if (!recentEl) {
    return;
  }
  const inspector = state.virtualizationInspector || {};
  const recent = Array.isArray(inspector.recentVmids) ? inspector.recentVmids : [];
  if (!recent.length) {
    recentEl.innerHTML = '<span class="chip muted">' + escapeHtml(t('vm.recent_empty')) + '</span>';
    return;
  }
  recentEl.innerHTML = recent.map((vmid) => {
    const active = Number(inspector.vmid || 0) === Number(vmid || 0);
    return '<button type="button" class="button ' + (active ? 'primary' : 'ghost') + ' small" data-virt-inspector-recent="' + escapeHtml(String(vmid)) + '">VM ' + escapeHtml(String(vmid)) + '</button>';
  }).join('');
}

function currentSuggestedVmid() {
  const selected = Number(state.selectedVmid || 0);
  if (Number.isFinite(selected) && selected > 0) {
    return selected;
  }
  const inspectorVmid = Number((state.virtualizationInspector || {}).vmid || 0);
  if (Number.isFinite(inspectorVmid) && inspectorVmid > 0) {
    return inspectorVmid;
  }
  return 0;
}

function findGpuByPci(pciAddress) {
  const pci = String(pciAddress || '').trim();
  const overview = state.virtualizationOverview || {};
  const gpus = Array.isArray(overview.gpus) ? overview.gpus : [];
  return gpus.find((item) => String(item.pci_address || '').trim() === pci) || null;
}

function vmOptionHtml(selectedVmid) {
  const vmRows = Array.isArray(state.vms) ? state.vms : [];
  const options = vmRows.map((vm) => {
    const vmid = Number(vm.vmid || vm.id || 0);
    if (!Number.isFinite(vmid) || vmid <= 0) {
      return '';
    }
    const label = 'VM ' + vmid + (vm.name ? ' · ' + String(vm.name) : '') + (vm.status ? ' · ' + String(vm.status) : '');
    return '<option value="' + escapeHtml(String(vmid)) + '"' + (Number(selectedVmid || 0) === vmid ? ' selected' : '') + '>' + escapeHtml(label) + '</option>';
  }).filter(Boolean).join('');
  return '<option value="">VM auswaehlen oder ID eingeben</option>' + options;
}

function requestGpuMutation(path, payload) {
  return postJson(path, payload);
}

function openGpuActionModal(pciAddress, mode) {
  const pci = String(pciAddress || '').trim();
  const action = String(mode || '').trim() === 'release' ? 'release' : 'assign';
  if (!pci) {
    virtualizationHooks.setBanner('PCI-Adresse fehlt.', 'warn');
    return;
  }
  const gpu = findGpuByPci(pci);
  const readiness = gpuReadiness(gpu || { status: '', driver: '' });
  const suggestedVmid = currentSuggestedVmid();
  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.id = 'gpu-action-modal';
  modal.innerHTML = `
    <div class="modal-dialog provision-dialog" role="dialog" aria-modal="true" aria-labelledby="gpu-action-title">
      <div class="modal-dialog-head">
        <div>
          <span class="eyebrow">GPU Aktion</span>
          <h2 id="gpu-action-title">${escapeHtml(action === 'assign' ? 'GPU einer VM zuweisen' : 'GPU von VM loesen')}</h2>
          <p>${escapeHtml(pci)} · ${escapeHtml(action === 'assign' ? 'Diese Aenderung wirkt direkt auf die Ziel-VM.' : 'Die GPU wird aus der Ziel-VM-Konfiguration entfernt.')}</p>
        </div>
        <button class="icon-button" type="button" aria-label="Schliessen" id="gpu-action-close">×</button>
      </div>
      <div class="settings-form">
        <div class="gpu-wizard-steps" aria-label="GPU Wizard Schritte">
          <span class="active">1 GPU</span>
          <span class="active">2 VM</span>
          <span class="active">3 Bestaetigung</span>
          <span>4 Ergebnis</span>
        </div>
        <div class="field field-wide gpu-wizard-summary">
          <span>Ausgewaehlte GPU</span>
          <div class="settings-info-grid compact-grid">
            <div class="info-item"><span class="info-label">PCI</span><span class="info-value mono">${escapeHtml(pci)}</span></div>
            <div class="info-item"><span class="info-label">Modell</span><span class="info-value">${escapeHtml(String((gpu && gpu.model) || 'Unbekannt'))}</span></div>
            <div class="info-item"><span class="info-label">Treiber</span><span class="info-value">${chip((gpu && gpu.driver) || 'kein Treiber', (gpu && gpu.driver) === 'vfio-pci' ? 'ok' : 'warn')}</span></div>
            <div class="info-item"><span class="info-label">Readiness</span><span class="info-value">${chip(readiness.label, readiness.tone)}</span></div>
          </div>
          <p class="muted-text">${escapeHtml(readiness.reason + ' ' + readiness.nextStep)}</p>
        </div>
        <div class="field field-wide cluster-security-note">
          <span>Wichtiger Hinweis</span>
          <p>${escapeHtml(action === 'assign'
            ? 'Passthrough- oder vfio-aehnliche Geraete sollten nur ausgeschalteten oder sauber vorbereiteten VMs zugewiesen werden.'
            : 'Das Loesen einer GPU kann Treiber- oder Boot-Folgen in der VM haben und sollte geplant erfolgen.')}</p>
        </div>
        <label class="field field-wide">
          <span>Ziel-VM</span>
          <select id="gpu-action-vm-select">${vmOptionHtml(suggestedVmid)}</select>
          <input id="gpu-action-vmid" type="number" min="1" step="1" value="${escapeHtml(suggestedVmid > 0 ? String(suggestedVmid) : '')}" placeholder="z.B. 100">
        </label>
        <label class="field field-wide checkbox-field">
          <input id="gpu-action-ack" type="checkbox">
          <span>${escapeHtml(action === 'assign' ? 'Ich bestaetige, dass die Ziel-VM ausgeschaltet oder fuer Hostdev-Aenderungen vorbereitet ist.' : 'Ich bestaetige, dass die GPU aus der VM-Konfiguration entfernt werden soll.')}</span>
        </label>
        <div class="field field-wide">
          <span>Payload</span>
          <pre class="payload-preview" id="gpu-action-payload">${escapeHtml(JSON.stringify({ pci_address: pci, action, vmid: suggestedVmid || null }, null, 2))}</pre>
        </div>
        <div class="banner hidden" id="gpu-action-result"></div>
      </div>
      <div class="button-row provision-modal-buttons">
        <button class="button ghost" type="button" id="gpu-action-cancel">Abbrechen</button>
        <button class="button ${action === 'assign' ? 'primary' : 'danger'}" type="button" id="gpu-action-confirm">${escapeHtml(action === 'assign' ? 'GPU zuweisen' : 'GPU loesen')}</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  document.body.classList.add('modal-open');
  modal.hidden = false;
  modal.setAttribute('aria-hidden', 'false');

  const close = () => {
    modal.remove();
    if (document.querySelectorAll('.modal[aria-hidden="false"]').length === 0) {
      document.body.classList.remove('modal-open');
    }
  };
  const closeBtn = document.getElementById('gpu-action-close');
  const cancelBtn = document.getElementById('gpu-action-cancel');
  const confirmBtn = document.getElementById('gpu-action-confirm');
  const vmidInput = document.getElementById('gpu-action-vmid');
  const vmSelect = document.getElementById('gpu-action-vm-select');
  const ackInput = document.getElementById('gpu-action-ack');
  const payloadEl = document.getElementById('gpu-action-payload');
  const resultEl = document.getElementById('gpu-action-result');
  const syncPayload = () => {
    const vmid = parseInt(String(vmidInput ? vmidInput.value : '').trim(), 10);
    if (payloadEl) {
      payloadEl.textContent = JSON.stringify({ pci_address: pci, action, vmid: Number.isFinite(vmid) && vmid > 0 ? vmid : null }, null, 2);
    }
  };
  if (closeBtn) {
    closeBtn.addEventListener('click', close);
  }
  if (cancelBtn) {
    cancelBtn.addEventListener('click', close);
  }
  modal.addEventListener('click', (event) => {
    if (event.target === modal) {
      close();
    }
  });
  if (confirmBtn) {
    confirmBtn.addEventListener('click', () => {
      const vmid = parseInt(String(vmidInput ? vmidInput.value : '').trim(), 10);
      if (!Number.isFinite(vmid) || vmid <= 0) {
        virtualizationHooks.setBanner('Ungueltige VM-ID.', 'warn');
        return;
      }
      if (!ackInput || !ackInput.checked) {
        virtualizationHooks.setBanner('Bestaetigung fehlt.', 'warn');
        return;
      }
      const path = action === 'assign'
        ? '/virtualization/gpus/' + encodeURIComponent(pci) + '/assign'
        : '/virtualization/gpus/' + encodeURIComponent(pci) + '/release';
      confirmBtn.disabled = true;
      requestGpuMutation(path, { vmid }).then((res) => {
        if (res.ok) {
          virtualizationHooks.setBanner(
            action === 'assign'
              ? ('GPU ' + pci + ' wurde VM ' + vmid + ' zugewiesen.')
              : ('GPU ' + pci + ' wurde von VM ' + vmid + ' geloest.'),
            'ok'
          );
          if (resultEl) {
            resultEl.className = 'banner banner-ok';
            resultEl.textContent = action === 'assign'
              ? ('Ergebnis: GPU ' + pci + ' ist fuer VM ' + vmid + ' eingetragen.')
              : ('Ergebnis: GPU ' + pci + ' wurde aus VM ' + vmid + ' geloest.');
          }
          virtualizationHooks.loadDashboard();
          return;
        }
        virtualizationHooks.setBanner('Fehler: ' + (res.error || JSON.stringify(res)), 'warn');
      }).catch((err) => {
        virtualizationHooks.setBanner('Fehler: ' + (err.message || String(err)), 'warn');
      }).finally(() => {
        confirmBtn.disabled = false;
      });
    });
  }
  if (vmSelect) {
    vmSelect.addEventListener('change', () => {
      if (vmidInput && vmSelect.value) {
        vmidInput.value = vmSelect.value;
      }
      syncPayload();
    });
  }
  if (vmidInput) {
    vmidInput.addEventListener('input', syncPayload);
  }
  if (vmidInput) {
    window.setTimeout(() => vmidInput.focus(), 30);
  }
}

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
    nodesGrid.innerHTML = '<div class="empty-card">' + escapeHtml(t('vm.connect_first')) + '</div>';
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
        '<button type="button" class="button ghost small" data-virt-node-detail="' + escapeHtml(nodeName) + '">Details</button> ' +
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
        '<td><button type="button" class="button ghost small" data-storage-detail="' + escapeHtml(item.name || item.id || '') + '">Dateien</button> <button type="button" class="button ghost small" data-storage-quota-set="1" data-storage-pool="' + escapeHtml(item.name || item.id || '') + '" data-storage-quota-bytes="' + String(quotaBytes) + '">Quota</button></td>' +
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

function formatStorageImageTimestamp(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return '-';
  }
  try {
    return new Date(numeric * 1000).toLocaleString('de-DE');
  } catch (error) {
    void error;
    return '-';
  }
}

function storageImageTone(kind) {
  const normalized = String(kind || '').trim().toLowerCase();
  if (normalized === 'iso') {
    return 'ok';
  }
  if (normalized === 'images') {
    return 'muted';
  }
  return 'warn';
}

export function openStoragePoolDetail(poolName) {
  const pool = String(poolName || '').trim();
  if (!pool) {
    virtualizationHooks.setBanner('Storage-Pool fehlt.', 'warn');
    return;
  }
  virtualizationHooks.setBanner('Lade Storage-Inhalt fuer ' + pool + ' ...', 'info');
  request('/storage/pools/' + encodeURIComponent(pool) + '/files').then((payload) => {
    const files = Array.isArray(payload && payload.files) ? payload.files : [];
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'virt-storage-detail-modal';
    modal.innerHTML = `
      <div class="modal-dialog provision-dialog" role="dialog" aria-modal="true" aria-labelledby="virt-storage-detail-title">
        <div class="modal-dialog-head">
          <div>
            <span class="eyebrow">Storage Detail</span>
            <h2 id="virt-storage-detail-title">${escapeHtml(pool)}</h2>
            <p>${escapeHtml(String(files.length))} Datei(en) im aktuell lesbaren Pool-Inhalt.</p>
          </div>
          <button class="icon-button" type="button" aria-label="Schliessen" id="virt-storage-detail-close">×</button>
        </div>
        <div class="settings-form">
          <div class="field field-wide">
            <span>Dateien</span>
            <div class="settings-info-grid compact-grid">
              ${files.length ? files.map((item) => (
                '<div class="info-item">' +
                '<span class="info-label">' + escapeHtml(String(item.filename || '-')) + '</span>' +
                '<span class="info-value">' +
                chip(String(item.content_kind || 'datei'), storageImageTone(item.content_kind)) + ' ' +
                escapeHtml(formatBytes(item.size_bytes || 0)) + ' · ' +
                escapeHtml(formatStorageImageTimestamp(item.modified_at)) +
                ' <button type="button" class="button ghost small" data-storage-file-download="' + escapeHtml(String(item.filename || '')) + '" data-storage-file-pool="' + escapeHtml(pool) + '">Download</button>' +
                '</span>' +
                '</div>'
              )).join('') : '<div class="empty-cell">Keine ISO-/Disk-Images im Pool gefunden.</div>'}
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    document.body.classList.add('modal-open');
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');

    const close = () => {
      modal.remove();
      if (document.querySelectorAll('.modal[aria-hidden="false"]').length === 0) {
        document.body.classList.remove('modal-open');
      }
    };
    const closeBtn = document.getElementById('virt-storage-detail-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', close);
    }
    modal.addEventListener('click', (event) => {
      if (event.target === modal) {
        close();
      }
    });
    modal.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-storage-file-download]');
      if (!button) {
        return;
      }
      const filename = String(button.getAttribute('data-storage-file-download') || '').trim();
      if (!filename) {
        return;
      }
      button.disabled = true;
      blobRequest(
        '/storage/pools/' + encodeURIComponent(pool) + '/files?filename=' + encodeURIComponent(filename),
        filename
      ).catch((error) => {
        virtualizationHooks.setBanner('Storage-Download fehlgeschlagen: ' + error.message, 'warn');
      }).finally(() => {
        button.disabled = false;
      });
    });
  }).catch((error) => {
    virtualizationHooks.setBanner('Storage-Inhalt konnte nicht geladen werden: ' + error.message, 'warn');
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
  const storageCards = qs('virtualization-storage-cards');
  const bridgeCards = qs('virtualization-bridge-cards');
  const gpuCards = qs('virtualization-gpu-cards');
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

  if (storageCards) {
    storageCards.innerHTML = filteredStorage.length ? filteredStorage.map((item) => {
      const quotaBytes = Number(item.quota_bytes || 0);
      const quotaText = quotaBytes > 0 ? formatGiB(quotaBytes) : 'unbegrenzt';
      const health = storageHealth(item.used, item.total);
      const nodeName = String(item.node || '').trim();
      const usageText = formatBytes(item.used || 0) + ' / ' + formatBytes(item.total || 0) + ' (' + health.usedPct.toFixed(0) + '%)';
      const healthButton = nodeName
        ? '<button type="button" class="button ghost small" data-storage-health-node="' + escapeHtml(nodeName) + '">Health pruefen</button>'
        : '<button type="button" class="button ghost small" disabled>Health pruefen</button>';
      return '<article class="storage-card ' + health.tone + '">' +
        '<div class="storage-card-head">' +
        '<div>' +
        '<strong class="node-name">' + escapeHtml(item.name || item.id || 'storage') + '</strong>' +
        '<div class="storage-card-meta">' +
        chip(item.type || 'n/a', 'muted') +
        chip(nodeName || 'ohne Node', 'muted') +
        chip(health.label, health.tone) +
        '</div>' +
        '</div>' +
        '<div>' + chip(item.active ? 'aktiv' : 'inaktiv', item.active ? 'ok' : 'warn') + '</div>' +
        '</div>' +
        '<div class="storage-card-usage">' +
        '<span class="usage-key">Auslastung</span>' +
        usageBar(item.used, item.total, usageText).replace('usage-bar-outer', 'usage-bar-outer ' + health.tone) +
        '</div>' +
        '<div class="settings-info-grid compact-grid">' +
        '<div class="info-item"><span class="info-label">Content</span><span class="info-value">' + escapeHtml(item.content || '-') + '</span></div>' +
        '<div class="info-item"><span class="info-label">Verfuegbar</span><span class="info-value">' + escapeHtml(formatBytes(item.avail || 0)) + '</span></div>' +
        '<div class="info-item"><span class="info-label">Quota</span><span class="info-value">' + escapeHtml(quotaText) + '</span></div>' +
        '<div class="info-item"><span class="info-label">Shared</span><span class="info-value">' + escapeHtml(item.shared ? 'ja' : 'nein') + '</span></div>' +
        '</div>' +
        '<div class="storage-card-actions">' +
        '<button type="button" class="button ghost small" data-storage-detail="' + escapeHtml(item.name || item.id || '') + '">Dateien</button>' +
        '<button type="button" class="button ghost small" data-storage-quota-set="1" data-storage-pool="' + escapeHtml(item.name || item.id || '') + '" data-storage-quota-bytes="' + String(quotaBytes) + '">Quota setzen</button>' +
        healthButton +
        '</div>' +
        '</article>';
    }).join('') : '<div class="empty-card">Keine Storage-Daten vorhanden.</div>';
  }

  if (gpuCards) {
    gpuCards.innerHTML = filteredGpus.length ? filteredGpus.map((item) => {
      const readiness = gpuReadiness(item);
      const iommu = item.iommu_group ? ('Group ' + String(item.iommu_group) + ' (' + String(item.iommu_group_size || 0) + ')') : '-';
      const pci = escapeHtml(item.pci_address || '');
      const nodeName = String(item.node || '').trim();
      let actionBtn = '';
      if (item.status === 'available-for-passthrough' || item.status === 'assigned') {
        actionBtn = item.status === 'assigned'
          ? '<button type="button" class="button ghost small" data-gpu-release="1" data-gpu-pci="' + pci + '">Von VM loesen</button>'
          : '<button type="button" class="button ghost small" data-gpu-assign="1" data-gpu-pci="' + pci + '">VM zuweisen</button>';
      } else {
        actionBtn = '<button type="button" class="button ghost small" disabled>Nicht sicher zuweisbar</button>';
      }
      return '<article class="gpu-card ' + readiness.tone + '" data-node="' + escapeHtml(nodeName) + '">' +
        '<div class="gpu-card-head">' +
        '<div>' +
        '<strong class="node-name">' + escapeHtml(item.model || item.vendor || 'GPU') + '</strong>' +
        '<div class="gpu-card-meta">' +
        chip(nodeName || 'ohne Node', 'muted') +
        chip(item.vendor || 'vendor', 'muted') +
        chip(readiness.label, readiness.tone) +
        '</div>' +
        '</div>' +
        '<div>' + chip(item.driver || 'kein Treiber', item.driver === 'vfio-pci' ? 'ok' : 'warn') + '</div>' +
        '</div>' +
        '<div class="settings-info-grid compact-grid">' +
        '<div class="info-item"><span class="info-label">PCI</span><span class="info-value mono">' + escapeHtml(item.pci_address || '-') + '</span></div>' +
        '<div class="info-item"><span class="info-label">IOMMU</span><span class="info-value">' + escapeHtml(iommu) + '</span></div>' +
        '<div class="info-item"><span class="info-label">Status</span><span class="info-value">' + escapeHtml(String(item.status || 'unknown')) + '</span></div>' +
        '<div class="info-item"><span class="info-label">Passthrough</span><span class="info-value">' + escapeHtml(item.passthrough_ready ? 'bereit' : 'blockiert') + '</span></div>' +
        '</div>' +
        '<div class="gpu-readiness-note">' +
        '<strong>Warum gerade dieser Status?</strong>' +
        '<div>' + escapeHtml(readiness.reason) + '</div>' +
        '<div class="muted-text">' + escapeHtml(readiness.nextStep) + '</div>' +
        '</div>' +
        '<div class="gpu-card-actions">' +
        actionBtn +
        '<button type="button" class="button ghost small" data-virt-node-detail="' + escapeHtml(nodeName) + '">Host pruefen</button>' +
        '</div>' +
        '</article>';
    }).join('') : '<div class="empty-card">Keine GPU-Daten vorhanden.</div>';
  }

  if (bridgeCards) {
    bridgeCards.innerHTML = filteredBridges.length ? filteredBridges.map((item) => {
      const nodeName = String(item.node || '').trim();
      const warningCount = (!item.active ? 1 : 0) + (!item.bridge_ports ? 1 : 0) + (!(item.cidr || item.address) ? 1 : 0);
      const tone = !item.active ? 'bad' : (warningCount > 0 ? 'warn' : 'ok');
      return '<article class="bridge-card ' + tone + '"' +
        ((nodeFilter && nodeName === nodeFilter) ? ' data-node="' + escapeHtml(nodeName) + '"' : ' data-node="' + escapeHtml(nodeName) + '"') +
        '>' +
        '<div class="bridge-card-head">' +
        '<div>' +
        '<strong class="node-name">' + escapeHtml(item.name || item.id || 'bridge') + '</strong>' +
        '<div class="bridge-card-meta">' +
        chip(nodeName || 'ohne Node', 'muted') +
        chip(item.active ? 'aktiv' : 'inaktiv', item.active ? 'ok' : 'warn') +
        chip(warningCount ? (warningCount + ' Warnungen') : 'bereit', tone) +
        '</div>' +
        '</div>' +
        '<div>' + chip(item.type || 'bridge', 'muted') + '</div>' +
        '</div>' +
        '<div class="settings-info-grid compact-grid">' +
        '<div class="info-item"><span class="info-label">Adresse</span><span class="info-value">' + escapeHtml(item.cidr || item.address || '-') + '</span></div>' +
        '<div class="info-item"><span class="info-label">Ports</span><span class="info-value">' + escapeHtml(item.bridge_ports || '-') + '</span></div>' +
        '<div class="info-item"><span class="info-label">Autostart</span><span class="info-value">' + escapeHtml(item.autostart ? 'ja' : 'nein') + '</span></div>' +
        '</div>' +
        '<div class="bridge-card-actions">' +
        '<button type="button" class="button ghost small" data-virt-bridge-detail="' + escapeHtml(item.name || item.id || '') + '">Details</button>' +
        '<button type="button" class="button ghost small" data-virt-bridge-ipam="' + escapeHtml(item.name || item.id || '') + '" data-virt-bridge-cidr="' + escapeHtml(item.cidr || '') + '">IPAM-Zone</button>' +
        '<button type="button" class="button ghost small" data-virt-node-filter="' + escapeHtml(nodeName) + '">Node filtern</button>' +
        '</div>' +
        '</article>';
    }).join('') : '<div class="empty-card">Keine Bridge-Daten vorhanden.</div>';
  }
}

export function setVirtualizationNodeFilter(nodeName) {
  const next = String(nodeName || '').trim();
  state.virtualizationNodeFilter = next;
  renderVirtualizationOverview();
  virtualizationHooks.setBanner(next ? ('Node-Filter aktiv: ' + next) : 'Node-Filter entfernt.', 'info');
}

export function openVirtualizationNodeDetail(nodeName) {
  const node = String(nodeName || '').trim();
  if (!node) {
    virtualizationHooks.setBanner('Node-Name fehlt.', 'warn');
    return;
  }
  virtualizationHooks.setBanner('Lade Node-Details fuer ' + node + ' ...', 'info');
  request('/virtualization/nodes/' + encodeURIComponent(node) + '/detail').then((payload) => {
    const detail = payload || {};
    const nodeData = detail.node || {};
    const warnings = Array.isArray(detail.warnings) ? detail.warnings : [];
    const services = detail.services || {};
    const serviceMessages = detail.service_messages || {};
    const storage = Array.isArray(detail.storage) ? detail.storage : [];
    const bridges = Array.isArray(detail.bridges) ? detail.bridges : [];
    const gpus = Array.isArray(detail.gpus) ? detail.gpus : [];

    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'virt-node-detail-modal';
    modal.innerHTML = `
      <div class="modal-dialog provision-dialog" role="dialog" aria-modal="true" aria-labelledby="virt-node-detail-title">
        <div class="modal-dialog-head">
          <div>
            <span class="eyebrow">Node Detail</span>
            <h2 id="virt-node-detail-title">${escapeHtml(String(nodeData.label || nodeData.name || node))}</h2>
            <p>${escapeHtml(String(nodeData.local ? 'Lokaler Host' : 'Cluster-Knoten'))}${nodeData.api_url ? ' · ' + escapeHtml(String(nodeData.api_url)) : ''}</p>
          </div>
          <button class="icon-button" type="button" aria-label="Schliessen" id="virt-node-detail-close">×</button>
        </div>
        <div class="settings-form">
          ${warnings.length ? `
            <div class="field field-wide">
              <span>Warnungen</span>
              <div class="settings-info-grid compact-grid">
                ${warnings.map((warning) => '<div class="info-item"><span class="info-label">Hinweis</span><span class="info-value">' + escapeHtml(String(warning || '')) + '</span></div>').join('')}
              </div>
            </div>
          ` : ''}
          <div class="field field-wide">
            <span>Services & Reachability</span>
            <div class="settings-info-grid compact-grid">
              ${Object.keys(services).map((key) => (
                '<div class="info-item">' +
                '<span class="info-label">' + escapeHtml(key) + '</span>' +
                '<span class="info-value">' + chip(String(services[key] || 'unknown'), serviceTone(services[key])) + (serviceMessages[key] ? ' ' + escapeHtml(String(serviceMessages[key])) : '') + '</span>' +
                '</div>'
              )).join('')}
            </div>
          </div>
          <div class="field field-wide">
            <span>Storage</span>
            <div class="settings-info-grid compact-grid">
              ${storage.length ? storage.map((item) => (
                '<div class="info-item">' +
                '<span class="info-label">' + escapeHtml(String(item.name || item.id || 'storage')) + '</span>' +
                '<span class="info-value">' + escapeHtml(String(item.type || '-')) + ' · ' + escapeHtml(formatBytes(item.used || 0) + ' / ' + formatBytes(item.total || 0)) + '</span>' +
                '</div>'
              )).join('') : '<div class="empty-cell">Keine Storage-Pools fuer diesen Node.</div>'}
            </div>
          </div>
          <div class="field field-wide">
            <span>Bridges</span>
            <div class="settings-info-grid compact-grid">
              ${bridges.length ? bridges.map((item) => (
                '<div class="info-item">' +
                '<span class="info-label">' + escapeHtml(String(item.name || item.id || 'bridge')) + '</span>' +
                '<span class="info-value">' + escapeHtml(String(item.cidr || item.address || '-')) + ' · ' + escapeHtml(String(item.bridge_ports || '-')) + '</span>' +
                '</div>'
              )).join('') : '<div class="empty-cell">Keine Bridges fuer diesen Node.</div>'}
            </div>
          </div>
          <div class="field field-wide">
            <span>GPUs</span>
            <div class="settings-info-grid compact-grid">
              ${gpus.length ? gpus.map((item) => (
                '<div class="info-item">' +
                '<span class="info-label">' + escapeHtml(String(item.pci_address || item.model || 'gpu')) + '</span>' +
                '<span class="info-value">' + escapeHtml(String(item.status || 'unknown')) + (item.driver ? ' · ' + escapeHtml(String(item.driver)) : '') + '</span>' +
                '</div>'
              )).join('') : '<div class="empty-cell">Keine GPUs fuer diesen Node erkannt.</div>'}
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    document.body.classList.add('modal-open');
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');

    const close = () => {
      modal.remove();
      if (document.querySelectorAll('.modal[aria-hidden="false"]').length === 0) {
        document.body.classList.remove('modal-open');
      }
    };
    const closeBtn = document.getElementById('virt-node-detail-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', close);
    }
    modal.addEventListener('click', (event) => {
      if (event.target === modal) {
        close();
      }
    });
  }).catch((error) => {
    virtualizationHooks.setBanner('Node-Details konnten nicht geladen werden: ' + error.message, 'warn');
  });
}

export function createIpamZoneForBridge(bridgeName, bridgeCidr) {
  const bridge = String(bridgeName || '').trim();
  if (!bridge) {
    virtualizationHooks.setBanner('Bridge-Name fehlt.', 'warn');
    return;
  }
  const subnet = window.prompt('IPAM-Zone fuer Bridge "' + bridge + '" anlegen.\nSubnetz/CIDR:', String(bridgeCidr || '').trim());
  if (subnet == null) {
    return;
  }
  const dhcpStart = window.prompt('DHCP-Start fuer "' + bridge + '":', '');
  if (dhcpStart == null) {
    return;
  }
  const dhcpEnd = window.prompt('DHCP-Ende fuer "' + bridge + '":', '');
  if (dhcpEnd == null) {
    return;
  }
  virtualizationHooks.setBanner('Lege IPAM-Zone fuer ' + bridge + ' an ...', 'info');
  postJson('/network/ipam/zones', {
    zone_id: bridge,
    bridge_name: bridge,
    subnet: String(subnet || '').trim(),
    dhcp_start: String(dhcpStart || '').trim(),
    dhcp_end: String(dhcpEnd || '').trim(),
  }).then(() => {
    virtualizationHooks.setBanner('IPAM-Zone fuer ' + bridge + ' angelegt.', 'ok');
    virtualizationHooks.loadDashboard();
  }).catch((error) => {
    virtualizationHooks.setBanner('IPAM-Zone konnte nicht angelegt werden: ' + error.message, 'warn');
  });
}

export function openVirtualizationBridgeDetail(bridgeName) {
  const bridge = String(bridgeName || '').trim();
  if (!bridge) {
    virtualizationHooks.setBanner('Bridge-Name fehlt.', 'warn');
    return;
  }
  virtualizationHooks.setBanner('Lade Bridge-Details fuer ' + bridge + ' ...', 'info');
  request('/virtualization/bridges/' + encodeURIComponent(bridge) + '/detail').then((payload) => {
    const detail = payload || {};
    const bridgeData = detail.bridge || {};
    const warnings = Array.isArray(detail.warnings) ? detail.warnings : [];
    const vms = Array.isArray(detail.vms) ? detail.vms : [];
    const zones = Array.isArray(detail.ipam_zones) ? detail.ipam_zones : [];
    const profiles = Array.isArray(detail.firewall_profiles) ? detail.firewall_profiles : [];
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'virt-bridge-detail-modal';
    modal.innerHTML = `
      <div class="modal-dialog provision-dialog" role="dialog" aria-modal="true" aria-labelledby="virt-bridge-detail-title">
        <div class="modal-dialog-head">
          <div>
            <span class="eyebrow">Bridge Detail</span>
            <h2 id="virt-bridge-detail-title">${escapeHtml(String(bridgeData.name || bridge))}</h2>
            <p>${escapeHtml(String(bridgeData.node || '-'))} · ${escapeHtml(String(bridgeData.cidr || bridgeData.address || 'ohne Adresse'))}</p>
          </div>
          <button class="icon-button" type="button" aria-label="Schliessen" id="virt-bridge-detail-close">×</button>
        </div>
        <div class="settings-form">
          ${warnings.length ? `
            <div class="field field-wide">
              <span>Warnungen</span>
              <div class="settings-info-grid compact-grid">
                ${warnings.map((warning) => '<div class="info-item"><span class="info-label">Hinweis</span><span class="info-value">' + escapeHtml(String(warning || '')) + '</span></div>').join('')}
              </div>
            </div>
          ` : ''}
          <div class="field field-wide">
            <span>VM-Nutzung</span>
            <div class="settings-info-grid compact-grid">
              ${vms.length ? vms.map((item) => (
                '<div class="info-item">' +
                '<span class="info-label">VM ' + escapeHtml(String(item.vmid || '')) + '</span>' +
                '<span class="info-value">' + escapeHtml(String(item.name || 'vm')) + ' · ' + escapeHtml(String(item.status || 'unknown')) + (item.firewall_profile_name ? ' · FW ' + escapeHtml(String(item.firewall_profile_name || '')) : '') + '</span>' +
                '</div>'
              )).join('') : '<div class="empty-cell">Keine lokalen VMs auf dieser Bridge.</div>'}
            </div>
          </div>
          <div class="field field-wide">
            <span>IPAM-Zonen & Leases</span>
            <div class="settings-info-grid compact-grid">
              ${zones.length ? zones.map((zone) => (
                '<div class="info-item">' +
                '<span class="info-label">' + escapeHtml(String(zone.zone_id || 'zone')) + '</span>' +
                '<span class="info-value">' + escapeHtml(String(zone.subnet || '-')) + ' · ' + escapeHtml(String(zone.lease_count || 0) + ' Leases') + '</span>' +
                '</div>'
              )).join('') : '<div class="empty-cell">Noch keine IPAM-Zone fuer diese Bridge.</div>'}
            </div>
          </div>
          <div class="field field-wide">
            <span>Verfuegbare Firewall-Profile</span>
            <div class="settings-info-grid compact-grid">
              ${profiles.length ? profiles.map((item) => (
                '<div class="info-item">' +
                '<span class="info-label">' + escapeHtml(String(item.name || item.profile_id || 'Profil')) + '</span>' +
                '<span class="info-value">' + escapeHtml(String(item.rule_count || 0) + ' Regeln') + '</span>' +
                '</div>'
              )).join('') : '<div class="empty-cell">Keine Firewall-Profile vorhanden.</div>'}
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    document.body.classList.add('modal-open');
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    const close = () => {
      modal.remove();
      if (document.querySelectorAll('.modal[aria-hidden="false"]').length === 0) {
        document.body.classList.remove('modal-open');
      }
    };
    const closeBtn = document.getElementById('virt-bridge-detail-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', close);
    }
    modal.addEventListener('click', (event) => {
      if (event.target === modal) {
        close();
      }
    });
  }).catch((error) => {
    virtualizationHooks.setBanner('Bridge-Details konnten nicht geladen werden: ' + error.message, 'warn');
  });
}

export function assignGpuToVm(pciAddress) {
  openGpuActionModal(pciAddress, 'assign');
}

export function releaseGpuFromVm(pciAddress) {
  openGpuActionModal(pciAddress, 'release');
}

export function renderVirtualizationInspector() {
  const summary = qs('virt-inspector-summary');
  const configBody = qs('virt-inspector-config-body');
  const disksBody = qs('virt-inspector-disks-body');
  const netcfgBody = qs('virt-inspector-netcfg-body');
  const ifaceBody = qs('virt-inspector-iface-body');
  renderInspectorRecentVmids();
  if (!summary || !configBody || !disksBody || !netcfgBody || !ifaceBody) {
    return;
  }
  if (!state.token) {
    summary.innerHTML = '<div class="kv"><div class="kv-label">Status</div><div class="kv-value">Bitte anmelden, um VM-Details zu laden.</div></div>';
    configBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Nicht angemeldet.</td></tr>';
    disksBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Nicht angemeldet.</td></tr>';
    netcfgBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Nicht angemeldet.</td></tr>';
    ifaceBody.innerHTML = '<tr><td colspan="3" class="empty-cell">Nicht angemeldet.</td></tr>';
    return;
  }
  const inspector = state.virtualizationInspector || {};
  if (inspector.loading) {
    summary.innerHTML = '<div class="kv"><div class="kv-label">Status</div><div class="kv-value">Lade VM-Inspector ...</div></div>';
    configBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Lade Konfiguration ...</td></tr>';
    disksBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Lade Disk-Daten ...</td></tr>';
    netcfgBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Lade Netzwerk-Config ...</td></tr>';
    ifaceBody.innerHTML = '<tr><td colspan="3" class="empty-cell">Lade Interfaces ...</td></tr>';
    return;
  }
  if (inspector.error) {
    summary.innerHTML = '<div class="kv"><div class="kv-label">Fehler</div><div class="kv-value">' + escapeHtml(inspector.error) + '</div></div>';
    configBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Keine Config verfuegbar.</td></tr>';
    disksBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Keine Disk-Daten verfuegbar.</td></tr>';
    netcfgBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Keine Netzwerk-Config verfuegbar.</td></tr>';
    ifaceBody.innerHTML = '<tr><td colspan="3" class="empty-cell">Keine Interface-Daten verfuegbar.</td></tr>';
    return;
  }
  if (!inspector.vmid || !inspector.config) {
    summary.innerHTML = '<div class="kv"><div class="kv-label">Status</div><div class="kv-value">Noch keine VM geladen.</div></div>';
    configBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Noch keine Config geladen.</td></tr>';
    disksBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Noch keine Disk-Daten geladen.</td></tr>';
    netcfgBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Noch keine Netzwerk-Config geladen.</td></tr>';
    ifaceBody.innerHTML = '<tr><td colspan="3" class="empty-cell">Noch keine Interfaces geladen.</td></tr>';
    return;
  }
  const config = inspector.config || {};
  const interfaces = Array.isArray(inspector.interfaces) ? inspector.interfaces : [];
  const diskKeys = Object.keys(config).filter((key) => DISK_KEY_PATTERN.test(key)).sort();
  const netKeys = Object.keys(config).filter((key) => NET_KEY_PATTERN.test(key)).sort();
  const generalKeys = VM_MAIN_KEYS.filter((key) => config[key] != null && config[key] !== '');
  summary.innerHTML = [
    fieldBlock('VMID', String(inspector.vmid)),
    fieldBlock('Name', String(config.name || 'n/a')),
    fieldBlock('Node', String(config.node || 'n/a')),
    fieldBlock('Status', String(config.status || 'unknown')),
    fieldBlock('Disks', String(diskKeys.length)),
    fieldBlock('NICs', String(netKeys.length))
  ].join('');
  configBody.innerHTML = generalKeys.length ? generalKeys.map((key) => {
    return '<tr><td>' + escapeHtml(key) + '</td><td class="storage-content">' + escapeHtml(String(config[key])) + '</td></tr>';
  }).join('') : '<tr><td colspan="2" class="empty-cell">Keine Config-Werte verfuegbar.</td></tr>';
  disksBody.innerHTML = diskKeys.length ? diskKeys.map((key) => {
    return '<tr><td>' + escapeHtml(key) + '</td><td class="storage-content">' + escapeHtml(String(config[key] || '')) + '</td></tr>';
  }).join('') : '<tr><td colspan="2" class="empty-cell">Keine Disk-Config vorhanden.</td></tr>';
  netcfgBody.innerHTML = netKeys.length ? netKeys.map((key) => {
    return '<tr><td>' + escapeHtml(key) + '</td><td class="storage-content">' + escapeHtml(String(config[key] || '')) + '</td></tr>';
  }).join('') : '<tr><td colspan="2" class="empty-cell">Keine Netzwerk-Config vorhanden.</td></tr>';
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
  const remembered = rememberInspectorVmid(numericVmid);
  state.virtualizationInspector = {
    ...remembered,
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
    const rememberedSuccess = rememberInspectorVmid(numericVmid);
    state.virtualizationInspector = {
      ...rememberedSuccess,
      vmid: numericVmid,
      loading: false,
      config: (results[0] && results[0].config) || {},
      interfaces: (results[1] && results[1].interfaces) || [],
      error: ''
    };
    renderVirtualizationInspector();
    virtualizationHooks.setBanner('VM Inspector geladen fuer VM ' + numericVmid + '.', 'ok');
  }).catch((error) => {
    const rememberedError = rememberInspectorVmid(numericVmid);
    state.virtualizationInspector = {
      ...rememberedError,
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
    ? '/virtualization/mdev/types?gpu_pci=' + encodeURIComponent(gpuPci)
    : '/virtualization/mdev/types';
  request(url).then((res) => {
    const types = Array.isArray(res.mdev_types) ? res.mdev_types : [];
    if (!types.length) {
      typesBody.innerHTML = '<div class="empty-card">Keine vGPU-Typen gefunden. Pruefe NVIDIA-vGPU-Treiber, Lizenz und mdev_supported_types auf dem Host.</div>';
    } else {
      typesBody.innerHTML = types.map((t) => {
        const pci = escapeHtml(t.gpu_pci || '');
        const tid = escapeHtml(t.type_id || '');
        const available = Number(t.available_instances ?? 0);
        const max = Number(t.max_instances ?? 0);
        const tone = available > 0 ? 'ok' : 'warn';
        return '<article class="gpu-subcard ' + tone + '">' +
          '<div class="gpu-card-head"><div><strong>' + escapeHtml(t.name || tid || 'mdev Typ') + '</strong><div class="gpu-card-meta">' + chip(pci || 'ohne PCI', 'muted') + chip(tid || 'ohne Typ', 'muted') + chip(String(available) + '/' + String(max || '-') + ' frei', tone) + '</div></div></div>' +
          '<div class="settings-info-grid compact-grid">' +
          '<div class="info-item"><span class="info-label">GPU PCI</span><span class="info-value mono">' + pci + '</span></div>' +
          '<div class="info-item"><span class="info-label">Typ-ID</span><span class="info-value mono">' + tid + '</span></div>' +
          '<div class="info-item"><span class="info-label">Kapazitaet</span><span class="info-value">' + escapeHtml(String(available) + ' verfuegbar von ' + String(max || '-')) + '</span></div>' +
          '</div>' +
          '<div class="gpu-card-actions"><button type="button" class="button ghost small" data-mdev-create="1" data-mdev-pci="' + pci + '" data-mdev-type="' + tid + '"' + (available <= 0 ? ' disabled' : '') + '>Instanz erzeugen</button></div>' +
          '</article>';
      }).join('');
    }
  }).catch((err) => {
    typesBody.innerHTML = '<div class="empty-card error">Fehler: ' + escapeHtml(err.message) + '</div>';
  });
  request('/virtualization/mdev/instances').then((res) => {
    const instances = Array.isArray(res.mdev_instances) ? res.mdev_instances : [];
    if (!instances.length) {
      instancesBody.innerHTML = '<div class="empty-card">Keine aktiven mdev-Instanzen.</div>';
    } else {
      instancesBody.innerHTML = instances.map((inst) => {
        const uid = escapeHtml(inst.uuid || '');
        return '<article class="gpu-subcard">' +
          '<div class="gpu-card-head"><div><strong class="mono">' + uid + '</strong><div class="gpu-card-meta">' + chip(inst.type_id || '-', 'muted') + chip(inst.gpu_pci || '-', 'muted') + '</div></div></div>' +
          '<div class="gpu-card-actions">' +
          '<button type="button" class="button ghost small mdev-assign-button" data-mdev-assign="1" data-mdev-uuid="' + uid + '">Zuweisen</button>' +
          '<button type="button" class="button ghost small danger" data-mdev-delete="1" data-mdev-uuid="' + uid + '">Löschen</button>' +
          '</div></article>';
      }).join('');
    }
  }).catch((err) => {
    instancesBody.innerHTML = '<div class="empty-card error">Fehler: ' + escapeHtml(err.message) + '</div>';
  });
}

export function createMdevInstance(gpuPci, typeId) {
  const pci = String(gpuPci || '').trim();
  const tid = String(typeId || '').trim();
  if (!pci || !tid) {
    virtualizationHooks.setBanner('GPU-PCI und Typ-ID sind erforderlich.', 'warn');
    return;
  }
  postJson('/virtualization/mdev/create', { gpu_pci: pci, type_id: tid }).then((res) => {
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
  postJson('/virtualization/mdev/' + encodeURIComponent(uid) + '/assign', { vmid }).then((res) => {
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
  postJson('/virtualization/mdev/' + encodeURIComponent(uid) + '/delete', {}).then((res) => {
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
  request('/virtualization/sriov').then((res) => {
    const devices = Array.isArray(res.sriov_devices) ? res.sriov_devices : [];
    if (!devices.length) {
      body.innerHTML = '<div class="empty-card">Keine SR-IOV-faehigen GPUs gefunden. Intel Arc/Xe-LP, Kernel-Support und sriov_totalvfs pruefen.</div>';
    } else {
      body.innerHTML = devices.map((dev) => {
        const pci = escapeHtml(dev.pci || '');
        return '<article class="gpu-subcard">' +
          '<div class="gpu-card-head"><div><strong class="mono">' + pci + '</strong><div class="gpu-card-meta">' + chip(dev.driver || '-', 'muted') + chip(String(dev.current_vfs ?? '-') + '/' + String(dev.total_vfs ?? '-') + ' VFs', Number(dev.current_vfs || 0) > 0 ? 'ok' : 'warn') + '</div></div></div>' +
          '<div class="gpu-readiness-note"><strong>Hardware-Constraints</strong><div>SR-IOV funktioniert nur mit passender Intel-GPU, Kernel-/Treiber-Support und aktivierbarem sriov_numvfs.</div></div>' +
          '<div class="gpu-card-actions"><button type="button" class="button ghost small" data-sriov-set="1" data-sriov-pci="' + pci + '" data-sriov-total="' + escapeHtml(String(dev.total_vfs ?? '0')) + '">VF-Anzahl setzen</button><button type="button" class="button ghost small" data-sriov-vfs="1" data-sriov-pci="' + pci + '">VFs anzeigen</button></div>' +
          '<div class="sriov-vf-list" id="sriov-vfs-' + pci.replace(/[^a-zA-Z0-9_-]/g, '-') + '"></div>' +
          '</article>';
      }).join('');
    }
  }).catch((err) => {
    body.innerHTML = '<div class="empty-card error">Fehler: ' + escapeHtml(err.message) + '</div>';
  });
}

export function loadSriovVfs(pciAddress) {
  const pci = String(pciAddress || '').trim();
  if (!pci) {
    virtualizationHooks.setBanner('PCI-Adresse fehlt.', 'warn');
    return;
  }
  const listId = 'sriov-vfs-' + pci.replace(/[^a-zA-Z0-9_-]/g, '-');
  const target = qs(listId);
  if (target) {
    target.innerHTML = '<div class="muted-text">Lade VFs ...</div>';
  }
  request('/virtualization/sriov/' + encodeURIComponent(pci) + '/vfs').then((res) => {
    const vfs = Array.isArray(res.vfs) ? res.vfs : [];
    const html = vfs.length
      ? vfs.map((vf) => '<span class="chip muted mono">' + escapeHtml(String(vf.pci || vf.address || vf.id || vf)) + '</span>').join(' ')
      : '<span class="chip muted">Keine aktiven VFs.</span>';
    if (target) {
      target.innerHTML = html;
    } else {
      virtualizationHooks.setBanner('VFs: ' + vfs.length, 'info');
    }
  }).catch((err) => {
    if (target) {
      target.innerHTML = '<div class="muted-text">Fehler: ' + escapeHtml(err.message) + '</div>';
    }
    virtualizationHooks.setBanner('SR-IOV VFs konnten nicht geladen werden: ' + err.message, 'warn');
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
  postJson('/virtualization/sriov/' + encodeURIComponent(pci) + '/set-vfs', { count }).then((res) => {
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
