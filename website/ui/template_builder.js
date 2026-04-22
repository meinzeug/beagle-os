import { request, runSingleFlight } from './api.js';
import { parseCommaList } from './inventory.js';
import { qs } from './dom.js';

const templateBuilderHooks = {
  setBanner() {},
  addToActivityLog() {},
  loadDashboard() {
    return Promise.resolve();
  },
  loadDetail() {
    return Promise.resolve();
  }
};

const templateBuilderProgressState = {
  running: false,
  vmid: null,
  phaseTimer: null
};

const TEMPLATE_PROGRESS_STEPS = [
  { title: 'Input validieren', detail: 'Template-Parameter werden geprueft.' },
  { title: 'Sysprep/Seal', detail: 'Guest wird bereinigt (cloud-init/sysprep).' },
  { title: 'Backing-Image exportieren', detail: 'qcow2 wird als Template-Artefakt gespeichert.' },
  { title: 'Metadaten persistieren', detail: 'Template wird im Katalog registriert.' }
];

function clearPhaseTimer() {
  if (templateBuilderProgressState.phaseTimer) {
    window.clearTimeout(templateBuilderProgressState.phaseTimer);
    templateBuilderProgressState.phaseTimer = null;
  }
}

function hasVisibleModal() {
  const modals = document.querySelectorAll('.modal');
  for (let index = 0; index < modals.length; index += 1) {
    if (!modals[index].hasAttribute('hidden')) {
      return true;
    }
  }
  return false;
}

function closeTemplateBuilderModalInternal() {
  const modal = qs('template-builder-modal');
  if (!modal) {
    return;
  }
  modal.setAttribute('hidden', 'hidden');
  if (!hasVisibleModal()) {
    document.body.classList.remove('modal-open');
  }
}

function setTemplateProgressMessage(message, tone) {
  const node = qs('template-builder-progress-message');
  if (!node) {
    return;
  }
  node.className = 'banner ' + String(tone || 'info') + ' provision-progress-banner';
  node.textContent = String(message || '');
}

function setTemplateProgressStep(stepIndex, status, detail) {
  const list = qs('template-builder-progress-steps');
  if (!list) {
    return;
  }
  const item = list.querySelector('[data-template-step="' + String(stepIndex) + '"]');
  if (!item) {
    return;
  }
  item.classList.remove('is-active', 'is-done', 'is-error');
  if (status === 'active') {
    item.classList.add('is-active');
  } else if (status === 'done') {
    item.classList.add('is-done');
  } else if (status === 'error') {
    item.classList.add('is-error');
  }
  const stateNode = item.querySelector('.step-state');
  if (stateNode) {
    stateNode.textContent = String(detail || status || 'pending');
  }
}

function markTemplateProgressRunning() {
  clearPhaseTimer();
  setTemplateProgressStep(1, 'active', 'running');
  setTemplateProgressMessage('Sysprep/Seal wird ausgefuehrt ...', 'info');
  templateBuilderProgressState.phaseTimer = window.setTimeout(() => {
    setTemplateProgressStep(1, 'done', 'done');
    setTemplateProgressStep(2, 'active', 'running');
    setTemplateProgressMessage('Backing-Image Export laeuft ...', 'info');
  }, 1100);
}

function openTemplateProgressModal(templateName) {
  const modal = qs('template-builder-progress-modal');
  const list = qs('template-builder-progress-steps');
  const title = qs('template-builder-progress-title');
  const subtitle = qs('template-builder-progress-subtitle');
  const closeButton = qs('template-builder-progress-close');
  if (!modal || !list) {
    return;
  }
  templateBuilderProgressState.running = true;
  clearPhaseTimer();
  if (title) {
    title.textContent = 'Template wird erstellt: ' + String(templateName || 'Neues Template');
  }
  if (subtitle) {
    subtitle.textContent = 'Sysprep/Seal und Export laufen auf dem Host.';
  }
  list.innerHTML = TEMPLATE_PROGRESS_STEPS.map((step, index) => {
    return '<li class="provision-progress-step" data-template-step="' + String(index) + '">' +
      '<span class="step-dot"></span><div><strong>' + String(step.title) + '</strong><p>' + String(step.detail) + '</p></div><span class="step-state">pending</span></li>';
  }).join('');
  setTemplateProgressStep(0, 'active', 'running');
  setTemplateProgressMessage('Template-Builder wird gestartet ...', 'info');
  if (closeButton) {
    closeButton.disabled = true;
    closeButton.textContent = 'Laeuft ...';
  }
  modal.removeAttribute('hidden');
  document.body.classList.add('modal-open');
  window.setTimeout(() => {
    setTemplateProgressStep(0, 'done', 'done');
    markTemplateProgressRunning();
  }, 200);
}

function finishTemplateProgress(success, message) {
  const closeButton = qs('template-builder-progress-close');
  clearPhaseTimer();
  templateBuilderProgressState.running = false;
  if (success) {
    setTemplateProgressStep(1, 'done', 'done');
    setTemplateProgressStep(2, 'done', 'done');
    setTemplateProgressStep(3, 'done', 'done');
    setTemplateProgressMessage(message || 'Template erfolgreich erstellt.', 'ok');
  } else {
    setTemplateProgressStep(3, 'error', 'failed');
    setTemplateProgressMessage(message || 'Template-Erstellung fehlgeschlagen.', 'warn');
  }
  if (closeButton) {
    closeButton.disabled = false;
    closeButton.textContent = 'Schliessen';
  }
}

function closeTemplateProgressModalInternal(force) {
  const modal = qs('template-builder-progress-modal');
  if (!modal) {
    return;
  }
  if (templateBuilderProgressState.running && !force) {
    return;
  }
  clearPhaseTimer();
  modal.setAttribute('hidden', 'hidden');
  if (!hasVisibleModal()) {
    document.body.classList.remove('modal-open');
  }
}

function defaultTemplateName(vmid) {
  const now = new Date();
  const stamp = String(now.getFullYear()) +
    String(now.getMonth() + 1).padStart(2, '0') +
    String(now.getDate()).padStart(2, '0') + '-' +
    String(now.getHours()).padStart(2, '0') +
    String(now.getMinutes()).padStart(2, '0');
  return 'golden-vm' + String(vmid) + '-' + stamp;
}

function collectTemplatePayload() {
  const vmid = Number(qs('template-source-vmid') ? qs('template-source-vmid').value : 0) || 0;
  const payload = {
    template_id: String(qs('template-id') ? qs('template-id').value : '').trim(),
    source_vmid: vmid,
    template_name: String(qs('template-name') ? qs('template-name').value : '').trim(),
    os_family: String(qs('template-os-family') ? qs('template-os-family').value : 'linux').trim() || 'linux',
    storage_pool: String(qs('template-storage-pool') ? qs('template-storage-pool').value : 'local').trim() || 'local',
    snapshot_name: String(qs('template-snapshot-name') ? qs('template-snapshot-name').value : 'sealed').trim() || 'sealed',
    cpu_cores: Number(qs('template-cpu-cores') ? qs('template-cpu-cores').value : 2) || 2,
    memory_mib: Number(qs('template-memory-mib') ? qs('template-memory-mib').value : 4096) || 4096,
    software_packages: parseCommaList(qs('template-software-packages') ? qs('template-software-packages').value : ''),
    notes: String(qs('template-notes') ? qs('template-notes').value : '').trim()
  };
  return payload;
}

export function configureTemplateBuilder(nextHooks) {
  Object.assign(templateBuilderHooks, nextHooks || {});
}

export function openTemplateBuilderModal(vmid) {
  const numericVmid = Number(vmid || 0) || 0;
  const modal = qs('template-builder-modal');
  if (!modal || !numericVmid) {
    return;
  }
  if (qs('template-source-vmid')) {
    qs('template-source-vmid').value = String(numericVmid);
  }
  if (qs('template-id')) {
    qs('template-id').value = '';
  }
  if (qs('template-name')) {
    qs('template-name').value = defaultTemplateName(numericVmid);
  }
  if (qs('template-os-family')) {
    qs('template-os-family').value = 'linux';
  }
  if (qs('template-storage-pool')) {
    qs('template-storage-pool').value = 'local';
  }
  if (qs('template-snapshot-name')) {
    qs('template-snapshot-name').value = 'sealed';
  }
  if (qs('template-cpu-cores')) {
    qs('template-cpu-cores').value = '2';
  }
  if (qs('template-memory-mib')) {
    qs('template-memory-mib').value = '4096';
  }
  if (qs('template-software-packages')) {
    qs('template-software-packages').value = '';
  }
  if (qs('template-notes')) {
    qs('template-notes').value = '';
  }
  modal.removeAttribute('hidden');
  document.body.classList.add('modal-open');
}

export function closeTemplateBuilderModal() {
  closeTemplateBuilderModalInternal();
}

export function closeTemplateBuilderProgressModal() {
  closeTemplateProgressModalInternal(false);
}

export function createTemplateFromModal() {
  const payload = collectTemplatePayload();
  if (!payload.source_vmid) {
    templateBuilderHooks.setBanner('Source VMID fehlt.', 'warn');
    return;
  }
  if (!payload.template_name) {
    templateBuilderHooks.setBanner('Template-Name ist erforderlich.', 'warn');
    return;
  }

  closeTemplateBuilderModalInternal();
  openTemplateProgressModal(payload.template_name);

  runSingleFlight('template-builder:' + String(payload.source_vmid), () => {
    return request('/pool-templates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then((result) => {
      const templateId = String(result && result.template_id || payload.template_id || payload.template_name || 'template');
      finishTemplateProgress(true, 'Template ' + templateId + ' erfolgreich erstellt.');
      templateBuilderHooks.addToActivityLog('template-create', payload.source_vmid, 'ok', templateId);
      templateBuilderHooks.setBanner('Template ' + templateId + ' erstellt.', 'ok');
      return Promise.all([
        templateBuilderHooks.loadDashboard({ force: true }),
        templateBuilderHooks.loadDetail(payload.source_vmid)
      ]);
    }).catch((error) => {
      finishTemplateProgress(false, 'Template-Erstellung fehlgeschlagen: ' + error.message);
      templateBuilderHooks.addToActivityLog('template-create', payload.source_vmid, 'warn', error.message);
      templateBuilderHooks.setBanner('Template-Erstellung fehlgeschlagen: ' + error.message, 'warn');
    });
  });
}
