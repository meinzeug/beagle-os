/**
 * secrets_admin.js — Secret management UI module
 * GoAdvanced Plan 03, Schritt 6
 *
 * Shows list of secrets (metadata only, no values).
 * Allows rotate and revoke operations.
 * RBAC: only security_admin role can use rotate/revoke buttons.
 */

import { request } from './api.js';
import { buildAuthHeaders } from './auth.js';
import { escapeHtml, qs } from './dom.js';
import { state } from './state.js';

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

async function fetchSecrets() {
  return request('GET', '/api/v1/secrets', {
    headers: buildAuthHeaders(),
  });
}

async function rotateSecret(name) {
  return request('POST', `/api/v1/secrets/${encodeURIComponent(name)}/rotate`, {
    headers: buildAuthHeaders(),
    body: {},
  });
}

async function revokeSecret(name, version) {
  return request('POST', `/api/v1/secrets/${encodeURIComponent(name)}/revoke`, {
    headers: buildAuthHeaders(),
    body: { version: Number(version) },
  });
}

// ---------------------------------------------------------------------------
// RBAC helper
// ---------------------------------------------------------------------------

function hasSecurityAdminRole() {
  const roles = state.currentUser?.roles ?? [];
  return roles.includes('security_admin') || roles.includes('superadmin');
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function statusBadge(status) {
  const cls = status === 'active' ? 'badge-success'
    : status === 'superseded' ? 'badge-warning'
    : 'badge-danger';
  return `<span class="badge ${cls}">${escapeHtml(status)}</span>`;
}

function renderSecretsTable(secrets) {
  const canManage = hasSecurityAdminRole();
  if (!secrets || secrets.length === 0) {
    return '<p class="text-muted">No secrets found.</p>';
  }
  const rows = secrets.map(s => {
    const rotateBtn = canManage
      ? `<button class="btn btn-sm btn-warning btn-rotate-secret"
           data-name="${escapeHtml(s.name)}"
           title="Generate new version (old version stays valid 24h)">Rotate</button>`
      : '';
    const revokeBtn = canManage
      ? `<button class="btn btn-sm btn-danger btn-revoke-secret"
           data-name="${escapeHtml(s.name)}"
           data-version="${Number(s.version) || 0}"
           title="Immediately revoke this version (no grace period)">Revoke v${Number(s.version) || 0}</button>`
      : '';
    return `
      <tr>
        <td><code>${escapeHtml(s.name)}</code></td>
        <td>${Number(s.version) || 0}</td>
        <td>${statusBadge(s.status || 'unknown')}</td>
        <td>${escapeHtml(s.created_at || '')}</td>
        <td>${escapeHtml(s.rotated_at || '—')}</td>
        <td>${Number(s.versions_count) || 1}</td>
        <td class="text-nowrap">${rotateBtn} ${revokeBtn}</td>
      </tr>`;
  }).join('');

  return `
    <table class="table table-sm table-hover secrets-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Version</th>
          <th>Status</th>
          <th>Created</th>
          <th>Last Rotated</th>
          <th>Versions</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="text-muted small mt-2">
      Secret values are never displayed. Rotate creates a new version;
      old version stays valid for 24 h (grace period).
      Revoke is immediate and cannot be undone.
    </p>`;
}

// ---------------------------------------------------------------------------
// Panel mount / refresh
// ---------------------------------------------------------------------------

export async function mountSecretsAdmin(container) {
  if (!container) return;

  container.innerHTML = `
    <div class="panel-header d-flex justify-content-between align-items-center mb-3">
      <h5 class="mb-0">Secret Management</h5>
      <button class="btn btn-sm btn-outline-secondary" id="btn-refresh-secrets">Refresh</button>
    </div>
    <div id="secrets-content"><span class="text-muted">Loading…</span></div>`;

  const content = container.querySelector('#secrets-content');

  async function refresh() {
    content.innerHTML = '<span class="text-muted">Loading…</span>';
    try {
      const data = await fetchSecrets();
      const list = Array.isArray(data) ? data
        : Array.isArray(data?.secrets) ? data.secrets
        : [];
      content.innerHTML = renderSecretsTable(list);
      wireButtons(content);
    } catch (err) {
      content.innerHTML = `<div class="alert alert-danger">Failed to load secrets: ${escapeHtml(String(err?.message || err))}</div>`;
    }
  }

  function wireButtons(root) {
    root.querySelectorAll('.btn-rotate-secret').forEach(btn => {
      btn.addEventListener('click', async () => {
        const name = btn.dataset.name;
        if (!confirm(`Rotate secret "${name}"?\n\nA new version will be generated. The old version remains valid for 24 hours.`)) return;
        btn.disabled = true;
        try {
          await rotateSecret(name);
          await refresh();
        } catch (err) {
          import('./error-handler.js').then(({ showError }) => showError(err, { context: 'Rotation failed' }));
          btn.disabled = false;
        }
      });
    });

    root.querySelectorAll('.btn-revoke-secret').forEach(btn => {
      btn.addEventListener('click', async () => {
        const name = btn.dataset.name;
        const version = btn.dataset.version;
        if (!confirm(`REVOKE secret "${name}" version ${version}?\n\nThis is IMMEDIATE and cannot be undone. All clients using this version will fail instantly.`)) return;
        btn.disabled = true;
        try {
          await revokeSecret(name, version);
          await refresh();
        } catch (err) {
          import('./error-handler.js').then(({ showError }) => showError(err, { context: 'Revocation failed' }));
          btn.disabled = false;
        }
      });
    });
  }

  container.querySelector('#btn-refresh-secrets').addEventListener('click', refresh);
  await refresh();
}
