/**
 * jobs_panel.js — Async Job Queue UI Panel (GoAdvanced Plan 07 Schritt 6)
 *
 * Features:
 *   - List active/recent jobs with auto-refresh (polling fallback + SSE).
 *   - SSE-subscribe to a specific job_id for live progress updates.
 *   - Toast notifications on job completion (success / error).
 *   - Auto-subscribe when a POST returns {ok: true, job_id: "..."}.
 *
 * Usage:
 *   import { initJobsPanel, subscribeJob, showJobToast } from './jobs_panel.js';
 *   initJobsPanel();                        // call once after DOM ready
 *   subscribeJob(jobId);                    // subscribe SSE for a specific job
 *   showJobToast('Backup started', 'info'); // manual toast
 *
 * Exports:
 *   initJobsPanel()     — mount & start auto-refresh
 *   subscribeJob(id)    — subscribe SSE for a single job, returns unsubscribe fn
 *   showJobToast(msg, tone) — show a temporary notification
 *   onAsyncResponse(resp)   — helper: call after any fetch returning {job_id}
 */

import { request, apiBase, postJson } from './api.js';
import { qs, escapeHtml, chip } from './dom.js';
import { state } from './state.js';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const POLL_INTERVAL_MS = 5_000;
const TOAST_DURATION_MS = 5_000;
const MAX_JOBS_DISPLAYED = 30;
const SSE_RECONNECT_DELAY_MS = 3_000;
const SSE_MAX_RECONNECTS = 10;

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

let _pollTimer = null;
const _sseByJobId = new Map(); // jobId → EventSource

// ---------------------------------------------------------------------------
// Toast system
// ---------------------------------------------------------------------------

/**
 * Show a temporary toast notification.
 * @param {string} message
 * @param {'info'|'success'|'warn'|'error'} tone
 */
export function showJobToast(message, tone = 'info') {
  const container = _ensureToastContainer();
  const toast = document.createElement('div');
  toast.className = 'job-toast job-toast--' + tone;
  toast.setAttribute('role', 'status');
  toast.setAttribute('aria-live', 'polite');
  toast.textContent = String(message || '');

  // Close button
  const close = document.createElement('button');
  close.className = 'job-toast__close';
  close.setAttribute('aria-label', 'Schließen');
  close.textContent = '×';
  close.addEventListener('click', () => toast.remove());
  toast.appendChild(close);

  container.appendChild(toast);

  // Auto-dismiss
  setTimeout(() => {
    if (toast.parentNode) {
      toast.classList.add('job-toast--fade');
      setTimeout(() => toast.remove(), 400);
    }
  }, TOAST_DURATION_MS);
}

function _ensureToastContainer() {
  let container = document.getElementById('job-toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'job-toast-container';
    container.setAttribute('aria-label', 'Job-Benachrichtigungen');
    document.body.appendChild(container);
  }
  return container;
}

// ---------------------------------------------------------------------------
// SSE subscription
// ---------------------------------------------------------------------------

/**
 * Subscribe to live updates for a single job via SSE.
 * @param {string} jobId
 * @returns {() => void} unsubscribe function
 */
export function subscribeJob(jobId) {
  if (!jobId || _sseByJobId.has(jobId)) {
    return () => {};
  }

  let reconnects = 0;
  let closed = false;

  function connect() {
    if (closed) {
      return;
    }
    const streamUrl = new URL(apiBase() + '/jobs/' + encodeURIComponent(jobId) + '/stream', window.location.origin);
    if (state.token) {
      streamUrl.searchParams.set('access_token', state.token);
    }
    const url = streamUrl.toString();
    const es = new EventSource(url, { withCredentials: true });

    const handleMessage = (evt) => {
      let data = {};
      try {
        data = JSON.parse(evt.data);
      } catch (_) {
        return;
      }
      const status = String(data.status || '').toLowerCase();
      if (status === 'completed' || status === 'failed' || status === 'cancelled') {
        _handleJobDone(data);
        es.close();
        _sseByJobId.delete(jobId);
        closed = true;
        return;
      }
      _handleJobUpdate(data);
      reconnects = 0;
    };

    es.addEventListener('message', handleMessage);
    es.addEventListener('job_update', handleMessage);
    es.addEventListener('job_done', handleMessage);

    es.onerror = () => {
      es.close();
      _sseByJobId.delete(jobId);
      if (!closed && reconnects < SSE_MAX_RECONNECTS) {
        reconnects++;
        setTimeout(connect, SSE_RECONNECT_DELAY_MS);
      }
    };

    _sseByJobId.set(jobId, es);
  }

  connect();

  return () => {
    closed = true;
    const es = _sseByJobId.get(jobId);
    if (es) {
      es.close();
      _sseByJobId.delete(jobId);
    }
  };
}

function _handleJobUpdate(data) {
  renderJobsPanel(); // refresh panel with new state
  // Could also update a specific row's status cell without full re-render
}

function _handleJobDone(data) {
  const status = String(data.status || '').toLowerCase();
  const name = String(data.name || data.job_id || 'Job');
  if (status === 'completed') {
    showJobToast('✓ ' + name + ' abgeschlossen', 'success');
  } else if (status === 'failed') {
    const err = String(data.error || '');
    showJobToast('✗ ' + name + ' fehlgeschlagen' + (err ? ': ' + err : ''), 'error');
  } else if (status === 'cancelled') {
    showJobToast(name + ' abgebrochen', 'warn');
  }
  renderJobsPanel();
}

// ---------------------------------------------------------------------------
// Panel rendering
// ---------------------------------------------------------------------------

export async function renderJobsPanel() {
  const panel = qs('jobs-panel');
  if (!panel) {
    return;
  }

  let jobs = [];
  try {
    const result = await request('/jobs', {});
    jobs = Array.isArray(result.jobs) ? result.jobs : [];
  } catch (err) {
    const body = qs('jobs-panel-body');
    if (body) {
      body.innerHTML = '<tr><td colspan="5" class="empty-cell error-cell">' +
        escapeHtml('Fehler beim Laden der Jobs: ' + String(err && err.message || err)) +
        '</td></tr>';
    }
    return;
  }

  const body = qs('jobs-panel-body');
  if (!body) {
    return;
  }

  if (!jobs.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-cell">Keine aktiven Jobs.</td></tr>';
    return;
  }

  const rows = jobs.slice(0, MAX_JOBS_DISPLAYED).map((job) => {
    const status = String(job.status || 'unknown').toLowerCase();
    const tone = status === 'completed' ? 'ok'
      : status === 'failed' ? 'error'
      : status === 'cancelled' ? 'muted'
      : status === 'running' ? 'info'
      : 'warn';

    const cancelBtn = (status === 'pending' || status === 'running')
      ? '<button class="btn-sm" data-cancel-job="' + escapeHtml(job.job_id) + '" title="Job abbrechen">⊘</button>'
      : '';

    return '<tr>' +
      '<td class="vm-sub">' + escapeHtml(String(job.job_id || '').slice(0, 8) + '…') + '</td>' +
      '<td>' + escapeHtml(String(job.name || '')) + '</td>' +
      '<td>' + chip(status, tone) + '</td>' +
      '<td class="vm-sub">' + escapeHtml(String(job.owner || '–')) + '</td>' +
      '<td>' + cancelBtn + '</td>' +
      '</tr>';
  }).join('');

  body.innerHTML = rows;

  // Wire cancel buttons
  body.querySelectorAll('[data-cancel-job]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const jobId = btn.getAttribute('data-cancel-job');
      btn.disabled = true;
      try {
        await request('/jobs/' + encodeURIComponent(jobId), { method: 'DELETE' });
        showJobToast('Job abgebrochen', 'warn');
        renderJobsPanel();
      } catch (err) {
        showJobToast('Abbruch fehlgeschlagen: ' + String(err && err.message || err), 'error');
        btn.disabled = false;
      }
    });
  });
}

// ---------------------------------------------------------------------------
// Auto-subscribe helper for POST responses
// ---------------------------------------------------------------------------

/**
 * Call after a POST response to auto-subscribe SSE if the response includes a job_id.
 *
 * Example:
 *   const result = await postJson('/vms/100/snapshot', { name: 'snap1' });
 *   onAsyncResponse(result);  // if result.job_id → subscribeJob automatically
 *
 * @param {object} responsePayload
 * @param {string} [label]  Optional human-readable label for the toast
 */
export function onAsyncResponse(responsePayload, label) {
  if (!responsePayload || !responsePayload.ok) {
    return;
  }
  const jobId = String(responsePayload.job_id || '');
  if (!jobId) {
    return;
  }
  const name = label || String(responsePayload.name || responsePayload.scope_type || 'Operation');
  showJobToast('⏳ ' + name + ' gestartet (Job ' + jobId.slice(0, 8) + '…)', 'info');
  subscribeJob(jobId);
}

// ---------------------------------------------------------------------------
// Panel init + polling
// ---------------------------------------------------------------------------

/**
 * Initialize the jobs panel: mount DOM, start polling, wire refresh button.
 * Safe to call multiple times (idempotent).
 */
export function initJobsPanel() {
  if (_pollTimer !== null) {
    return; // already initialized
  }

  renderJobsPanel();

  // Polling fallback (in case SSE is unavailable)
  _pollTimer = setInterval(() => {
    if (qs('jobs-panel')) {
      renderJobsPanel();
    }
  }, POLL_INTERVAL_MS);

  // Wire manual refresh button if present
  const refreshBtn = document.getElementById('jobs-panel-refresh');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => renderJobsPanel());
  }
}

export function teardownJobsPanel() {
  if (_pollTimer !== null) {
    clearInterval(_pollTimer);
    _pollTimer = null;
  }
  _sseByJobId.forEach((es) => es.close());
  _sseByJobId.clear();
}
