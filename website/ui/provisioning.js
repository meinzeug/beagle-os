import {
  MIN_GUEST_PASSWORD_LEN,
  state
} from './state.js';
import { escapeHtml, formatDate, qs } from './dom.js';
import { postJson, runSingleFlight } from './api.js';
import { addToActivityLog as defaultAddToActivityLog } from './activity.js';
import { parseCommaList } from './inventory.js';

const provisioningHooks = {
  setBanner() {},
  loadDashboard() {
    return Promise.resolve();
  },
  loadDetail() {
    return Promise.resolve();
  },
  addToActivityLog: defaultAddToActivityLog
};

const provisionProgressState = {
  running: false,
  vmid: null,
  stepIndex: -1
};

export function configureProvisioning(nextHooks) {
  Object.assign(provisioningHooks, nextHooks || {});
}

export function loadProvisioningCatalog(idPrefix) {
  const catalog = state.provisioningCatalog || {};
  const defaults = catalog.defaults || {};
  const nodes = Array.isArray(catalog.nodes) ? catalog.nodes : [];
  const desktopProfiles = Array.isArray(catalog.desktop_profiles) ? catalog.desktop_profiles : [];
  const bridges = Array.isArray(catalog.bridges) ? catalog.bridges : [];
  const storages = catalog.storages || {};
  const imagesStorages = Array.isArray(storages.images) ? storages.images : [];
  const isoStorages = Array.isArray(storages.iso) ? storages.iso : [];

  function fillSelect(selectId, items, valueFn, labelFn, selectedValue) {
    const select = qs(selectId);
    if (!select) {
      return;
    }
    if (!items.length) {
      select.innerHTML = '<option value="">n/a</option>';
      return;
    }
    select.innerHTML = items.map((item) => {
      const value = String(valueFn(item));
      const label = String(labelFn(item));
      return '<option value="' + escapeHtml(value) + '"' + (value === String(selectedValue || '') ? ' selected' : '') + '>' + escapeHtml(label) + '</option>';
    }).join('');
  }

  fillSelect(idPrefix + 'node', nodes, (item) => item.name || '', (item) => (item.name || 'node') + ' (' + (item.status || 'unknown') + ')', defaults.node || '');
  fillSelect(idPrefix + 'desktop', desktopProfiles, (item) => item.id || '', (item) => item.label || item.id || 'desktop', defaults.desktop || '');
  fillSelect(idPrefix + 'bridge', bridges, (item) => item, (item) => item, defaults.bridge || '');
  fillSelect(idPrefix + 'disk-storage', imagesStorages, (item) => item.id || '', (item) => (item.id || 'storage') + ' [' + (item.type || 'n/a') + ']', defaults.disk_storage || '');
  fillSelect(idPrefix + 'iso-storage', isoStorages, (item) => item.id || '', (item) => (item.id || 'storage') + ' [' + (item.type || 'n/a') + ']', defaults.iso_storage || '');

  if (qs(idPrefix + 'vmid')) {
    qs(idPrefix + 'vmid').value = String(defaults.next_vmid || '');
  }
  if (qs(idPrefix + 'name')) {
    qs(idPrefix + 'name').value = defaults.next_vmid ? 'ubuntu-beagle-' + String(defaults.next_vmid) : '';
  }
  if (qs(idPrefix + 'memory')) {
    qs(idPrefix + 'memory').value = String(defaults.memory || '4096');
  }
  if (qs(idPrefix + 'cores')) {
    qs(idPrefix + 'cores').value = String(defaults.cores || '4');
  }
  if (qs(idPrefix + 'disk')) {
    qs(idPrefix + 'disk').value = String(defaults.disk_gb || '64');
  }
  if (qs(idPrefix + 'guest-user')) {
    qs(idPrefix + 'guest-user').value = String(defaults.guest_user || 'beagle');
  }
  if (qs(idPrefix + 'guest-password')) {
    qs(idPrefix + 'guest-password').value = '';
  }
  if (qs(idPrefix + 'extra-packages')) {
    qs(idPrefix + 'extra-packages').value = '';
  }
}

export function renderProvisioningWorkspace() {
  const catalog = state.provisioningCatalog || {};
  const recentRequests = Array.isArray(catalog.recent_requests) ? catalog.recent_requests : [];
  loadProvisioningCatalog('prov-');
  if (qs('provision-recent-body')) {
    if (!recentRequests.length) {
      qs('provision-recent-body').innerHTML = '<tr><td colspan="5" class="empty-cell">Noch keine Provisioning-Requests vorhanden.</td></tr>';
    } else {
      qs('provision-recent-body').innerHTML = recentRequests.slice(0, 20).map((item) => {
        return '<tr data-vmid="' + escapeHtml(item.vmid || '') + '">' +
          '<td>' + escapeHtml(formatDate(item.updated_at || item.created_at || '')) + '</td>' +
          '<td><strong>' + escapeHtml(item.name || ('VM ' + item.vmid)) + '</strong><div class="vm-sub">#' + escapeHtml(item.vmid || '') + '</div></td>' +
          '<td>' + escapeHtml(item.node || '-') + '</td>' +
          '<td>' + escapeHtml(item.desktop_id || item.desktop || '-') + '</td>' +
          '<td>' + escapeHtml(item.provision_status || item.status || 'unknown') + '</td>' +
          '</tr>';
      }).join('');
    }
  }
}

function provisioningStepDescriptors() {
  return [
    { title: 'Konfiguration validieren', detail: 'Eingaben und Ziel-Provider werden geprueft.' },
    { title: 'Provisioning Request senden', detail: 'Host API erstellt den Provisioning-Auftrag.' },
    { title: 'VM wird auf dem Host angelegt', detail: 'Compute, Storage und Netzwerk werden vorbereitet.' },
    { title: 'Inventar wird aktualisiert', detail: 'Dashboard und Laufzeitdaten werden synchronisiert.' },
    { title: 'Detailansicht wird geladen', detail: 'Die neue VM wird direkt in der Console vorbereitet.' }
  ];
}

export function openProvisionProgressModal(vmName) {
  const modal = qs('provision-progress-modal');
  const stepsNode = qs('provision-progress-steps');
  const titleNode = qs('provision-progress-title');
  const subtitleNode = qs('provision-progress-subtitle');
  const messageNode = qs('provision-progress-message');
  const openVmButton = qs('provision-progress-open-vm');
  const closeButton = qs('provision-progress-close');
  const descriptors = provisioningStepDescriptors();
  if (!modal || !stepsNode) {
    return;
  }
  provisionProgressState.running = true;
  provisionProgressState.vmid = null;
  provisionProgressState.stepIndex = -1;
  if (titleNode) {
    titleNode.textContent = 'VM wird erstellt: ' + String(vmName || 'Neue Beagle VM');
  }
  if (subtitleNode) {
    subtitleNode.textContent = 'Der Workflow laeuft im Vordergrund mit Live-Schritten.';
  }
  if (messageNode) {
    messageNode.className = 'banner info provision-progress-banner';
    messageNode.textContent = 'Provisioning gestartet ...';
  }
  if (openVmButton) {
    openVmButton.hidden = true;
    openVmButton.disabled = true;
  }
  if (closeButton) {
    closeButton.disabled = true;
    closeButton.textContent = 'Laeuft ...';
  }
  stepsNode.innerHTML = descriptors.map((item, index) => {
    return '<li class="provision-progress-step" data-provision-step="' + String(index) + '"><span class="step-dot"></span><div><strong>' + escapeHtml(item.title) + '</strong><p>' + escapeHtml(item.detail) + '</p></div><span class="step-state">pending</span></li>';
  }).join('');
  modal.removeAttribute('hidden');
  document.body.classList.add('modal-open');
}

export function setProvisionProgressMessage(message, tone) {
  const messageNode = qs('provision-progress-message');
  if (!messageNode) {
    return;
  }
  messageNode.className = 'banner ' + String(tone || 'info') + ' provision-progress-banner';
  messageNode.textContent = String(message || '');
}

export function setProvisionProgressStep(stepIndex, status, message) {
  const stepsNode = qs('provision-progress-steps');
  if (!stepsNode) {
    return;
  }
  const row = stepsNode.querySelector('[data-provision-step="' + String(stepIndex) + '"]');
  if (!row) {
    return;
  }
  row.classList.remove('is-active', 'is-done', 'is-error');
  if (status === 'active') {
    row.classList.add('is-active');
    provisionProgressState.stepIndex = stepIndex;
  } else if (status === 'done') {
    row.classList.add('is-done');
  } else if (status === 'error') {
    row.classList.add('is-error');
    provisionProgressState.stepIndex = stepIndex;
  }
  const stateNode = row.querySelector('.step-state');
  if (stateNode) {
    stateNode.textContent = String(message || status || 'pending');
  }
}

export function finishProvisionProgress(success, vmid, message) {
  const closeButton = qs('provision-progress-close');
  const openVmButton = qs('provision-progress-open-vm');
  provisionProgressState.running = false;
  provisionProgressState.vmid = Number(vmid || 0) || null;
  if (success) {
    setProvisionProgressMessage(message || 'Provisioning erfolgreich gestartet.', 'ok');
  } else {
    setProvisionProgressMessage(message || 'Provisioning fehlgeschlagen.', 'warn');
  }
  if (closeButton) {
    closeButton.disabled = false;
    closeButton.textContent = success ? 'Schliessen' : 'Zurueck';
  }
  if (openVmButton) {
    if (success && provisionProgressState.vmid) {
      openVmButton.hidden = false;
      openVmButton.disabled = false;
    } else {
      openVmButton.hidden = true;
      openVmButton.disabled = true;
    }
  }
}

export function closeProvisionProgressModal(force) {
  const modal = qs('provision-progress-modal');
  let anyModalVisible = false;
  if (provisionProgressState.running && !force) {
    return;
  }
  if (!modal) {
    return;
  }
  modal.setAttribute('hidden', 'hidden');
  const modals = document.querySelectorAll('.modal');
  for (let index = 0; index < modals.length; index += 1) {
    if (!modals[index].hasAttribute('hidden')) {
      anyModalVisible = true;
      break;
    }
  }
  if (!anyModalVisible) {
    document.body.classList.remove('modal-open');
  }
}

export function setProvisionCreateButtonsDisabled(disabled) {
  if (qs('provision-create')) {
    qs('provision-create').disabled = Boolean(disabled);
  }
  if (qs('provision-modal-create')) {
    qs('provision-modal-create').disabled = Boolean(disabled);
  }
}

export function createProvisionedVmWithPrefix(idPrefix) {
  const payload = {
    node: String(qs(idPrefix + 'node') ? qs(idPrefix + 'node').value : '').trim(),
    vmid: Number(qs(idPrefix + 'vmid') ? qs(idPrefix + 'vmid').value : 0) || undefined,
    name: String(qs(idPrefix + 'name') ? qs(idPrefix + 'name').value : '').trim(),
    desktop: String(qs(idPrefix + 'desktop') ? qs(idPrefix + 'desktop').value : '').trim(),
    memory: Number(qs(idPrefix + 'memory') ? qs(idPrefix + 'memory').value : 0) || undefined,
    cores: Number(qs(idPrefix + 'cores') ? qs(idPrefix + 'cores').value : 0) || undefined,
    disk_gb: Number(qs(idPrefix + 'disk') ? qs(idPrefix + 'disk').value : 0) || undefined,
    bridge: String(qs(idPrefix + 'bridge') ? qs(idPrefix + 'bridge').value : '').trim(),
    disk_storage: String(qs(idPrefix + 'disk-storage') ? qs(idPrefix + 'disk-storage').value : '').trim(),
    iso_storage: String(qs(idPrefix + 'iso-storage') ? qs(idPrefix + 'iso-storage').value : '').trim(),
    guest_user: String(qs(idPrefix + 'guest-user') ? qs(idPrefix + 'guest-user').value : '').trim(),
    guest_password: String(qs(idPrefix + 'guest-password') ? qs(idPrefix + 'guest-password').value : ''),
    extra_packages: parseCommaList(qs(idPrefix + 'extra-packages') ? qs(idPrefix + 'extra-packages').value : ''),
    start: true
  };
  if (!payload.node) {
    provisioningHooks.setBanner('Provisioning: Node fehlt.', 'warn');
    return;
  }
  if (!payload.guest_password) {
    provisioningHooks.setBanner('Provisioning: Guest-Passwort ist erforderlich.', 'warn');
    return;
  }
  if (payload.guest_password.length < MIN_GUEST_PASSWORD_LEN) {
    provisioningHooks.setBanner('Provisioning: Guest-Passwort ist zu kurz (min. ' + String(MIN_GUEST_PASSWORD_LEN) + ').', 'warn');
    return;
  }
  if (idPrefix === 'prov-modal-') {
    closeProvisionModal();
  }
  openProvisionProgressModal(payload.name || ('vm-' + String(payload.vmid || 'auto')));
  setProvisionProgressStep(0, 'active', 'laeuft');
  setProvisionProgressMessage('Konfiguration wird geprueft ...', 'info');
  setProvisionCreateButtonsDisabled(true);
  return runSingleFlight('provision-create', () => {
    setProvisionProgressStep(0, 'done', 'ok');
    setProvisionProgressStep(1, 'active', 'laeuft');
    setProvisionProgressMessage('Provisioning-Request wird an den Host gesendet ...', 'info');
    provisioningHooks.setBanner('Provisioning: VM wird erstellt ...', 'info');
    return postJson('/provisioning/vms', payload, { __timeoutMs: 180000 }).then((response) => {
      const vm = response && response.provisioned_vm ? response.provisioned_vm : {};
      const vmid = Number(vm.vmid || payload.vmid || 0);
      setProvisionProgressStep(1, 'done', 'ok');
      setProvisionProgressStep(2, 'active', 'laeuft');
      setProvisionProgressMessage('Host meldet VM-Initialisierung fuer #' + String(vmid || '?') + ' ...', 'info');
      provisioningHooks.addToActivityLog('provision-create', vmid || null, 'ok', 'VM erstellt: ' + (payload.name || ''));
      provisioningHooks.setBanner('Provisioning gestartet fuer VM ' + (vmid || '?') + '.', 'ok');
      setProvisionProgressStep(2, 'done', 'ok');
      setProvisionProgressStep(3, 'active', 'laeuft');
      setProvisionProgressMessage('Dashboard und Inventar werden aktualisiert ...', 'info');
      return provisioningHooks.loadDashboard().then(() => {
        setProvisionProgressStep(3, 'done', 'ok');
        setProvisionProgressStep(4, 'active', 'laeuft');
        if (vmid) {
          return provisioningHooks.loadDetail(vmid).then(() => {
            setProvisionProgressStep(4, 'done', 'ok');
            finishProvisionProgress(true, vmid, 'Provisioning fuer VM #' + String(vmid) + ' erfolgreich gestartet.');
            return null;
          });
        }
        setProvisionProgressStep(4, 'done', 'uebersprungen');
        finishProvisionProgress(true, null, 'Provisioning gestartet. Es wurde keine VMID zurueckgegeben.');
        return null;
      });
    }).catch((error) => {
      if (provisionProgressState.stepIndex >= 0) {
        setProvisionProgressStep(provisionProgressState.stepIndex, 'error', 'fehler');
      }
      finishProvisionProgress(false, null, 'Provisioning fehlgeschlagen: ' + error.message);
      provisioningHooks.addToActivityLog('provision-create', null, 'warn', error.message);
      provisioningHooks.setBanner('Provisioning fehlgeschlagen: ' + error.message, 'warn');
    });
  }).finally(() => {
    setProvisionCreateButtonsDisabled(false);
  });
}

export function createProvisionedVm() {
  return createProvisionedVmWithPrefix('prov-');
}

export function createProvisionedVmFromModal() {
  return createProvisionedVmWithPrefix('prov-modal-');
}

export function openProvisionModal() {
  const modal = qs('provision-modal');
  if (modal) {
    modal.removeAttribute('hidden');
    document.body.classList.add('modal-open');
    loadProvisioningCatalog('prov-modal-');
    if (qs('prov-modal-name')) {
      qs('prov-modal-name').focus();
    }
  }
}

export function closeProvisionModal() {
  const modal = qs('provision-modal');
  if (modal) {
    modal.setAttribute('hidden', 'hidden');
    document.body.classList.remove('modal-open');
  }
}

export function openProvisioningWorkspace() {
  openProvisionModal();
}