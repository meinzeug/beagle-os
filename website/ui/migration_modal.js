/**
 * migrate_modal.js — VM Migration Modal mit topografischer Node-Ansicht
 *
 * Exports:
 *   openMigrateModal(opts) → Promise<void>
 *     opts: { vmid, vmName, currentNode, nodes, onMigrate(targetNode, live, copyStorage) }
 *
 *   initMigrateModal() — event-wiring, einmalig bei App-Start aufrufen
 */

/* ── IDs ─────────────────────────────────────────────────────────────── */
const MODAL_ID       = 'migrate-modal';
const TOPOLOGY_ID    = 'migrate-topology';
const NODE_LIST_ID   = 'migrate-node-list';
const VM_CHIP_ID     = 'migrate-vm-chip';
const STATUS_ID      = 'migrate-status';
const STATUS_TEXT_ID = 'migrate-status-text';
const MIGRATE_BTN_ID = 'migrate-confirm-btn';
const CANCEL_BTN_ID  = 'migrate-cancel-btn';
const LIVE_CHK_ID    = 'migrate-opt-live';
const COPY_CHK_ID    = 'migrate-opt-copy';
const SUBTITLE_ID    = 'migrate-modal-subtitle';

/* ── State ───────────────────────────────────────────────────────────── */
let _resolve  = null;
let _opts     = null;
let _selected = null;

/* ── Helpers ─────────────────────────────────────────────────────────── */
function qs(id) { return document.getElementById(id); }

function nodeIcon(nodeName, isSource) {
  if (isSource) return '🖥️';
  return '🖧';
}

function formatMem(bytes) {
  if (!bytes) return '';
  const gb = bytes / (1024 ** 3);
  return gb >= 1 ? gb.toFixed(1) + ' GB' : Math.round(bytes / (1024 ** 2)) + ' MB';
}

function formatLoad(cpu) {
  if (cpu == null) return '';
  return 'CPU ' + (cpu * 100).toFixed(1) + '%';
}

/* ── Build topology HTML ─────────────────────────────────────────────── */
function buildTopologyHTML(vmid, vmName, currentNode, nodes) {
  const sourceNode = nodes.find((n) => n.name === currentNode) || { name: currentNode, status: 'online' };
  const targets    = nodes.filter((n) => n.name !== currentNode);

  function nodeCard(node, isSource) {
    const offline = node.status !== 'online';
    const classes  = [
      'migrate-node',
      isSource ? 'migrate-node-source' : '',
      offline  ? 'migrate-node-offline' : '',
    ].filter(Boolean).join(' ');
    const meta = [
      node.vm_count != null ? node.vm_count + ' VMs' : '',
      formatMem(node.maxmem),
      formatLoad(node.cpu),
    ].filter(Boolean).join(' · ');
    return `
      <div class="${classes}" data-migrate-node="${node.name}" role="${isSource ? 'presentation' : 'button'}" tabindex="${isSource || offline ? -1 : 0}" aria-pressed="false" aria-label="${isSource ? 'Quellknoten ' : 'Zielknoten '}${node.name}">
        ${isSource ? `<div class="migrate-node-badge">Quelle</div>` : ''}
        <div class="migrate-node-check" aria-hidden="true">✓</div>
        <div class="migrate-node-icon">${nodeIcon(node.name, isSource)}</div>
        <div class="migrate-node-name">${node.name}</div>
        ${meta ? `<div class="migrate-node-meta">${meta}</div>` : ''}
        <div class="migrate-node-status-dot${offline ? ' offline' : ''}"></div>
        ${isSource ? `<div class="migrate-vm-chip" id="${VM_CHIP_ID}">VM ${vmid}</div>` : ''}
      </div>`;
  }

  let html = `<div class="migrate-node-list" id="${NODE_LIST_ID}">`;
  html += nodeCard(sourceNode, true);

  if (targets.length === 0) {
    html += `
      <div class="migrate-arrow-wrap">
        <div class="migrate-arrow">
          <div class="migrate-arrow-line"></div>
          <div class="migrate-arrow-head"></div>
        </div>
        <div class="migrate-arrow-label">Migrieren</div>
      </div>
      <div class="migrate-node migrate-node-offline migrate-node-empty">
        <div class="migrate-node-icon">🖧</div>
        <div class="migrate-node-name">Kein Ziel</div>
        <div class="migrate-node-meta">Keine online Nodes verfügbar</div>
      </div>`;
  } else {
    html += `
      <div class="migrate-arrow-wrap">
        <div class="migrate-arrow">
          <div class="migrate-arrow-line"></div>
          <div class="migrate-arrow-head"></div>
        </div>
        <div class="migrate-arrow-label">Migrieren nach</div>
      </div>
      <div class="migrate-target-list">`;
    targets.forEach((node) => { html += nodeCard(node, false); });
    html += `</div>`;
  }

  html += `</div>`;
  return html;
}

/* ── Open modal ──────────────────────────────────────────────────────── */
export function openMigrateModal(opts) {
  _opts     = opts || {};
  _selected = null;

  const modal    = qs(MODAL_ID);
  const topology = qs(TOPOLOGY_ID);
  if (!modal || !topology) {
    // fallback — should not happen if HTML is loaded
    return Promise.reject(new Error('migrate-modal not found in DOM'));
  }

  // inject subtitle
  const subtitle = qs(SUBTITLE_ID);
  if (subtitle) {
    subtitle.textContent = 'VM ' + String(_opts.vmid || '') + (_opts.vmName ? ' · ' + _opts.vmName : '') + ' · aktuell auf ' + String(_opts.currentNode || '');
  }

  // build topology
  topology.className = 'migrate-topology';
  topology.innerHTML = buildTopologyHTML(
    _opts.vmid,
    _opts.vmName,
    _opts.currentNode,
    Array.isArray(_opts.nodes) ? _opts.nodes : []
  );

  // reset options
  const liveChk = qs(LIVE_CHK_ID);
  const copyChk = qs(COPY_CHK_ID);
  if (liveChk) liveChk.checked = true;
  if (copyChk) copyChk.checked = true;

  // reset status
  _setStatus(null);

  // disable confirm button until a target is chosen
  const confirmBtn = qs(MIGRATE_BTN_ID);
  if (confirmBtn) confirmBtn.disabled = true;

  // wire node clicks
  topology.querySelectorAll('[data-migrate-node]').forEach((card) => {
    const name = card.getAttribute('data-migrate-node');
    if (name === _opts.currentNode) return;  // source — not clickable
    if (card.classList.contains('migrate-node-offline')) return;

    card.addEventListener('click', () => _selectTarget(name));
    card.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); _selectTarget(name); }
    });
  });

  // auto-select if only one target
  const targetNodes = (Array.isArray(_opts.nodes) ? _opts.nodes : [])
    .filter((n) => n.name !== _opts.currentNode && n.status === 'online');
  if (targetNodes.length === 1) {
    _selectTarget(targetNodes[0].name);
  }

  // show modal
  modal.hidden = false;
  modal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');

  // focus cancel by default
  window.setTimeout(() => { const c = qs(CANCEL_BTN_ID); if (c) c.focus(); }, 40);

  return new Promise((resolve) => { _resolve = resolve; });
}

/* ── Select target ───────────────────────────────────────────────────── */
function _selectTarget(name) {
  _selected = name;
  const topology = qs(TOPOLOGY_ID);
  if (topology) topology.classList.toggle('has-target', true);

  document.querySelectorAll('[data-migrate-node]').forEach((card) => {
    const isThis = card.getAttribute('data-migrate-node') === name;
    card.classList.toggle('migrate-node-selected', isThis);
    card.setAttribute('aria-pressed', isThis ? 'true' : 'false');
  });

  const confirmBtn = qs(MIGRATE_BTN_ID);
  if (confirmBtn) {
    confirmBtn.disabled = false;
    confirmBtn.textContent = 'Nach ' + name + ' migrieren';
  }
}

/* ── Set status ──────────────────────────────────────────────────────── */
function _setStatus(state, text) {
  const row = qs(STATUS_ID);
  const txt = qs(STATUS_TEXT_ID);
  if (!row) return;
  const spinner = row.querySelector('.migrate-status-spinner');
  if (!state) {
    row.classList.remove('visible', 'is-error', 'is-ok');
    if (spinner) spinner.classList.add('is-hidden');
    return;
  }
  row.classList.add('visible');
  row.classList.toggle('is-error', state === 'error');
  row.classList.toggle('is-ok', state === 'ok');
  if (spinner) spinner.classList.toggle('is-hidden', state !== 'running');
  if (txt) txt.textContent = text || '';
}

/* ── Close modal ─────────────────────────────────────────────────────── */
function _close() {
  const modal = qs(MODAL_ID);
  if (modal) {
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
  }
  document.body.classList.remove('modal-open');
  _selected = null;
  _opts     = null;
  if (_resolve) { _resolve(); _resolve = null; }
}

/* ── Confirm migration ───────────────────────────────────────────────── */
async function _confirm() {
  if (!_selected || !_opts) return;

  const liveChk = qs(LIVE_CHK_ID);
  const copyChk = qs(COPY_CHK_ID);
  const live        = liveChk ? liveChk.checked : true;
  const copyStorage = copyChk ? copyChk.checked : true;

  const topology   = qs(TOPOLOGY_ID);
  const confirmBtn = qs(MIGRATE_BTN_ID);
  const cancelBtn  = qs(CANCEL_BTN_ID);

  if (topology) topology.classList.add('is-migrating');
  if (confirmBtn) confirmBtn.disabled = true;
  if (cancelBtn)  cancelBtn.disabled  = true;

  _setStatus('running', 'Live-Migration läuft … VM wird nach ' + _selected + ' verschoben.');

  try {
    if (typeof _opts.onMigrate === 'function') {
      await _opts.onMigrate(_selected, live, copyStorage);
    }
    _setStatus('ok', 'VM erfolgreich nach ' + _selected + ' migriert.');
    window.setTimeout(_close, 1200);
  } catch (err) {
    if (topology) topology.classList.remove('is-migrating');
    if (cancelBtn) cancelBtn.disabled = false;
    _setStatus('error', 'Migration fehlgeschlagen: ' + String((err && err.message) || err));
    if (confirmBtn) {
      confirmBtn.disabled = false;
      confirmBtn.textContent = 'Erneut versuchen';
    }
  }
}

/* ── Init (once on app start) ────────────────────────────────────────── */
export function initMigrateModal() {
  const confirmBtn = qs(MIGRATE_BTN_ID);
  const cancelBtn  = qs(CANCEL_BTN_ID);
  const closeBtn   = qs('close-migrate-modal');
  const modal      = qs(MODAL_ID);

  if (confirmBtn) confirmBtn.addEventListener('click', _confirm);
  if (cancelBtn)  cancelBtn.addEventListener('click', _close);
  if (closeBtn)   closeBtn.addEventListener('click', _close);

  if (modal) {
    modal.addEventListener('click', (e) => { if (e.target === modal) _close(); });
  }

  document.addEventListener('keydown', (e) => {
    const modal = qs(MODAL_ID);
    if (modal && !modal.hidden && e.key === 'Escape') _close();
  });
}
