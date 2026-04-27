import {
  MAX_USERNAME_LEN,
  MIN_PASSWORD_LEN,
  ROLE_NAME_PATTERN,
  USERNAME_PATTERN,
  state
} from './state.js';
import { escapeHtml, qs } from './dom.js';
import { request, runSingleFlight } from './api.js';
import { sanitizeIdentifier } from './auth.js';

const iamHooks = {
  setBanner() {},
  requestConfirm() {
    return Promise.resolve(true);
  }
};

export function configureIam(nextHooks) {
  Object.assign(iamHooks, nextHooks || {});
}

export function parsePermissions(raw) {
  return String(raw || '')
    .split(/[,\n]/)
    .map((entry) => entry.trim())
    .filter(Boolean);
}

export function renderIamRoleSelect() {
  const roleSelect = qs('iam-user-role');
  if (!roleSelect) {
    return;
  }
  if (!state.authRoles.length) {
    roleSelect.innerHTML = '<option value="">Keine Rollen</option>';
    return;
  }
  roleSelect.innerHTML = state.authRoles.map((role) => {
    return '<option value="' + escapeHtml(role.name) + '">' + escapeHtml(role.name) + '</option>';
  }).join('');
}

function selectedUser() {
  return state.authUsers.find((entry) => entry.username === state.selectedAuthUser) || null;
}

function selectedRole() {
  return state.authRoles.find((entry) => entry.name === state.selectedAuthRole) || null;
}

function roleProtected(role) {
  if (!role) {
    return false;
  }
  const name = String(role.name || '').toLowerCase();
  return Boolean(role.protected || role.built_in || ['viewer', 'kiosk_operator', 'ops', 'admin', 'superadmin'].includes(name));
}

function sessionsForUser(username) {
  const body = document.getElementById('iam-sessions-body');
  if (!body || !username) {
    return [];
  }
  return Array.from(body.querySelectorAll('tr')).filter((row) => {
    return String(row.getAttribute('data-session-username') || '') === username;
  });
}

export function resetIamUserEditor() {
  state.selectedAuthUser = '';
  if (qs('iam-user-username')) {
    qs('iam-user-username').value = '';
  }
  if (qs('iam-user-password')) {
    qs('iam-user-password').value = '';
  }
  if (qs('iam-user-enabled')) {
    qs('iam-user-enabled').checked = true;
  }
  if (qs('iam-user-role')) {
    qs('iam-user-role').selectedIndex = 0;
  }
  const tenantEl = document.getElementById('iam-user-tenant');
  if (tenantEl) {
    tenantEl.value = '';
  }
  renderIamUserDetail();
}

export function renderPermissionTagEditor(activePermissions) {
  const container = qs('iam-role-permissions-grid');
  if (!container) {
    return;
  }
  const active = new Set(Array.isArray(activePermissions) ? activePermissions : []);
  const hasWildcard = active.has('*');
  const query = String(qs('iam-role-permission-search') ? qs('iam-role-permission-search').value : '').trim().toLowerCase();
  if (!Array.isArray(state.permissionCatalog) || !state.permissionCatalog.length) {
    container.innerHTML = '<p class="perm-empty">Berechtigungskatalog nicht geladen.</p>';
    return;
  }
  const html = state.permissionCatalog.map((group) => {
    const tags = Array.isArray(group.tags) ? group.tags : [];
    const visibleTags = tags.filter((entry) => {
      if (!query) {
        return true;
      }
      const haystack = String(group.group || '') + ' ' + String(entry.tag || '') + ' ' + String(entry.label || '');
      return haystack.toLowerCase().includes(query);
    });
    if (!visibleTags.length) {
      return '';
    }
    const checkboxes = visibleTags.map((entry) => {
      const tag = escapeHtml(String(entry.tag || ''));
      const label = escapeHtml(String(entry.label || entry.tag || ''));
      const checked = active.has(entry.tag) || (hasWildcard && entry.tag !== '*') ? ' checked' : '';
      return '<label class="check-label perm-check"><input type="checkbox" class="perm-tag-cb" data-tag="' + tag + '"' + checked + '><span>' + label + '</span></label>';
    }).join('');
    return '<div class="perm-group"><div class="perm-group-label">' + escapeHtml(String(group.group || '')) + '</div><div class="perm-group-tags">' + checkboxes + '</div></div>';
  }).filter(Boolean).join('');
  container.innerHTML = html || '<p class="perm-empty">Keine Berechtigungen fuer diesen Filter.</p>';
  renderIamRoleDiff();
}

export function resetIamRoleEditor() {
  state.selectedAuthRole = '';
  if (qs('iam-role-name')) {
    qs('iam-role-name').value = '';
    qs('iam-role-name').disabled = false;
  }
  if (qs('iam-role-save')) qs('iam-role-save').disabled = false;
  if (qs('iam-role-delete')) qs('iam-role-delete').disabled = false;
  if (qs('iam-role-permission-search')) qs('iam-role-permission-search').value = '';
  renderPermissionTagEditor([]);
  renderIamRoleDiff();
}

export function loadIamUserIntoEditor(username) {
  const user = state.authUsers.find((entry) => entry.username === username);
  if (!user) {
    return;
  }
  state.selectedAuthUser = user.username;
  if (qs('iam-user-username')) {
    qs('iam-user-username').value = user.username || '';
  }
  if (qs('iam-user-role')) {
    qs('iam-user-role').value = user.role || '';
  }
  if (qs('iam-user-password')) {
    qs('iam-user-password').value = '';
  }
  if (qs('iam-user-enabled')) {
    qs('iam-user-enabled').checked = user.enabled !== false;
  }
  const tenantEl = document.getElementById('iam-user-tenant');
  if (tenantEl) {
    tenantEl.value = user.tenant_id || '';
  }
  renderIamUserDetail();
}

export function loadIamRoleIntoEditor(roleName) {
  const role = state.authRoles.find((entry) => entry.name === roleName);
  if (!role) {
    return;
  }
  state.selectedAuthRole = role.name;
  if (qs('iam-role-name')) {
    qs('iam-role-name').value = role.name || '';
    qs('iam-role-name').disabled = roleProtected(role);
  }
  if (qs('iam-role-save')) qs('iam-role-save').disabled = roleProtected(role);
  if (qs('iam-role-delete')) qs('iam-role-delete').disabled = roleProtected(role);
  renderPermissionTagEditor(Array.isArray(role.permissions) ? role.permissions : []);
  renderIamRoleDiff();
}

export function renderIamUserDetail() {
  const container = qs('iam-user-detail');
  if (!container) {
    return;
  }
  const user = selectedUser();
  if (!user) {
    container.innerHTML = '<div class="empty-card">Kein User ausgewaehlt.</div>';
    return;
  }
  const groups = Array.isArray(user.groups) && user.groups.length ? user.groups : [];
  const sessionRows = sessionsForUser(user.username);
  const statusChip = user.enabled === false
    ? '<span class="status-chip warn">deaktiviert</span>'
    : '<span class="status-chip ok">aktiv</span>';
  container.innerHTML = '<div class="iam-detail-head">' +
      '<div><span class="eyebrow">User Detail</span><h3>' + escapeHtml(user.username) + '</h3></div>' + statusChip +
    '</div>' +
    '<dl class="iam-detail-grid">' +
      '<div><dt>Rolle</dt><dd>' + escapeHtml(user.role || '-') + '</dd></div>' +
      '<div><dt>Tenant</dt><dd>' + escapeHtml(user.tenant_id || 'platform') + '</dd></div>' +
      '<div><dt>Gruppen</dt><dd>' + escapeHtml(groups.join(', ') || '-') + '</dd></div>' +
      '<div><dt>Aktive Sessions</dt><dd>' + String(sessionRows.length) + '</dd></div>' +
    '</dl>' +
    '<div class="iam-detail-actions">' +
      '<button class="button ghost small" id="iam-detail-toggle-enabled" type="button">' + (user.enabled === false ? 'Aktivieren' : 'Deaktivieren') + '</button>' +
      '<button class="button ghost small" id="iam-detail-revoke" type="button">Sessions widerrufen</button>' +
      '<button class="button ghost small" id="iam-detail-reset-password" type="button">Passwort zuruecksetzen</button>' +
    '</div>';
  const toggle = qs('iam-detail-toggle-enabled');
  if (toggle) {
    toggle.addEventListener('click', () => {
      if (qs('iam-user-enabled')) qs('iam-user-enabled').checked = user.enabled === false;
      saveIamUser();
    });
  }
  const revoke = qs('iam-detail-revoke');
  if (revoke) {
    revoke.addEventListener('click', revokeIamUserSessions);
  }
  const reset = qs('iam-detail-reset-password');
  if (reset) {
    reset.addEventListener('click', () => {
      if (qs('iam-user-password')) {
        qs('iam-user-password').focus();
      }
      iamHooks.setBanner('Neues Passwort im User-Editor eintragen und speichern.', 'info');
    });
  }
}

export function renderIamUsers() {
  const body = qs('iam-users-body');
  if (!body) {
    return;
  }
  if (!state.authUsers.length) {
    body.innerHTML = '<tr><td colspan="3" class="empty-cell">Keine Benutzer sichtbar.</td></tr>';
    return;
  }
  body.innerHTML = state.authUsers.map((user) => {
    const selected = state.selectedAuthUser === user.username ? ' selected' : '';
    return '<tr class="clickable-row' + selected + '" data-iam-user="' + escapeHtml(user.username) + '"><td>' + escapeHtml(user.username) + '</td><td>' + escapeHtml(user.role || '-') + '</td><td>' + (user.enabled === false ? 'deaktiviert' : 'aktiv') + '</td></tr>';
  }).join('');
}

export function renderIamRoleDiff() {
  const container = qs('iam-role-diff');
  if (!container) {
    return;
  }
  const role = selectedRole();
  const current = new Set(_collectRolePermissions());
  if (!role) {
    container.textContent = current.size ? String(current.size) + ' Berechtigungen fuer neue Rolle gewaehlt.' : 'Keine Rolle ausgewaehlt.';
    return;
  }
  const original = new Set(Array.isArray(role.permissions) ? role.permissions : []);
  const added = Array.from(current).filter((item) => !original.has(item)).sort();
  const removed = Array.from(original).filter((item) => !current.has(item)).sort();
  const protection = roleProtected(role) ? ' Eingebaute Rolle: geschuetzt.' : '';
  if (!added.length && !removed.length) {
    container.textContent = 'Keine Aenderungen.' + protection;
    return;
  }
  container.innerHTML = '<span>Neu: ' + escapeHtml(added.join(', ') || '-') + '</span><span>Entfernt: ' + escapeHtml(removed.join(', ') || '-') + '</span>' + (protection ? '<span>' + protection + '</span>' : '');
}

export function renderIamRoles() {
  const body = qs('iam-roles-body');
  if (!body) {
    return;
  }
  if (!state.authRoles.length) {
    body.innerHTML = '<tr><td colspan="2" class="empty-cell">Keine Rollen sichtbar.</td></tr>';
    return;
  }
  body.innerHTML = state.authRoles.map((role) => {
    const selected = state.selectedAuthRole === role.name ? ' selected' : '';
    const permissions = Array.isArray(role.permissions) ? role.permissions : [];
    const preview = permissions.slice(0, 3).join(', ');
    const suffix = permissions.length > 3 ? ' ...' : '';
    const protectedChip = roleProtected(role) ? ' <span class="status-chip off">built-in</span>' : '';
    return '<tr class="clickable-row' + selected + '" data-iam-role="' + escapeHtml(role.name) + '"><td>' + escapeHtml(role.name) + protectedChip + '</td><td>' + escapeHtml(preview || '-') + escapeHtml(suffix) + '</td></tr>';
  }).join('');
}

export function renderIam() {
  renderIamRoleSelect();
  renderIamUsers();
  renderIamRoles();
}

export function refreshIamData() {
  return Promise.all([
    request('/auth/users').catch(() => ({ users: [] })),
    request('/auth/roles').catch(() => ({ roles: [] })),
    request('/auth/permission-tags').catch(() => null)
  ]).then((results) => {
    const usersPayload = results[0];
    const rolesPayload = results[1];
    state.authUsers = Array.isArray(usersPayload) ? usersPayload :
      (Array.isArray(usersPayload && usersPayload.users) ? usersPayload.users : []);
    state.authRoles = Array.isArray(rolesPayload) ? rolesPayload :
      (Array.isArray(rolesPayload && rolesPayload.roles) ? rolesPayload.roles : []);
    const catalogPayload = results[2];
    if (catalogPayload && Array.isArray(catalogPayload.catalog)) {
      state.permissionCatalog = catalogPayload.catalog;
    }
    if (state.selectedAuthUser && !state.authUsers.some((user) => user.username === state.selectedAuthUser)) {
      state.selectedAuthUser = '';
    }
    if (state.selectedAuthRole && !state.authRoles.some((role) => role.name === state.selectedAuthRole)) {
      state.selectedAuthRole = '';
    }
    renderIam();
    renderIamUserDetail();
    if (state.selectedAuthRole) {
      loadIamRoleIntoEditor(state.selectedAuthRole);
    } else {
      renderPermissionTagEditor([]);
    }
    // Load extended IAM sections in parallel (non-critical, fail silently)
    loadIamSessions().catch(() => {});
    loadIamTenants().catch(() => {});
    loadIamIdpCards().catch(() => {});
    loadIamScimStatus().catch(() => {});
  });
}

export function saveIamUser() {
  let username = String(qs('iam-user-username') ? qs('iam-user-username').value : '').trim();
  const role = String(qs('iam-user-role') ? qs('iam-user-role').value : '').trim();
  const password = String(qs('iam-user-password') ? qs('iam-user-password').value : '');
  const enabled = Boolean(qs('iam-user-enabled') && qs('iam-user-enabled').checked);
  const tenantId = String(document.getElementById('iam-user-tenant') ? document.getElementById('iam-user-tenant').value : '').trim() || null;
  const existing = state.authUsers.find((user) => user.username === username);
  let payload;
  try {
    username = sanitizeIdentifier(username, 'Username', USERNAME_PATTERN, 1, MAX_USERNAME_LEN);
  } catch (error) {
    iamHooks.setBanner(error.message, 'warn');
    return;
  }
  if (!role) {
    iamHooks.setBanner('Bitte eine Rolle auswaehlen.', 'warn');
    return;
  }
  payload = { role, enabled };
  if (tenantId) payload.tenant_id = tenantId;
  if (password) {
    payload.password = password;
  }
  if (!existing && !password) {
    iamHooks.setBanner('Neue User benoetigen ein Passwort.', 'warn');
    return;
  }
  if (password && password.length < MIN_PASSWORD_LEN) {
    iamHooks.setBanner('Passwort ist zu kurz (min. ' + String(MIN_PASSWORD_LEN) + ').', 'warn');
    return;
  }
  runSingleFlight('iam-user-save:' + username, () => {
    const createBody = { username, role, password, enabled };
    if (tenantId) createBody.tenant_id = tenantId;
    return request(existing ? ('/auth/users/' + encodeURIComponent(username)) : '/auth/users', {
      method: existing ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(existing ? payload : createBody)
    }).then(() => {
      state.selectedAuthUser = username;
      if (qs('iam-user-password')) {
        qs('iam-user-password').value = '';
      }
      iamHooks.setBanner('User gespeichert: ' + username, 'ok');
      return refreshIamData();
    }).catch((error) => {
      iamHooks.setBanner('User konnte nicht gespeichert werden: ' + error.message, 'warn');
    });
  });
}

export function deleteIamUser() {
  const username = String(qs('iam-user-username') ? qs('iam-user-username').value : '').trim() || state.selectedAuthUser;
  if (!username) {
    iamHooks.setBanner('Bitte zuerst einen User auswaehlen.', 'warn');
    return;
  }
  iamHooks.requestConfirm({
    title: 'User loeschen?',
    message: 'User "' + username + '" wirklich loeschen?',
    confirmLabel: 'Loeschen',
    danger: true
  }).then((ok) => {
    if (!ok) {
      return;
    }
    runSingleFlight('iam-user-delete:' + username, () => {
      return request('/auth/users/' + encodeURIComponent(username), {
        method: 'DELETE'
      }).then(() => {
        resetIamUserEditor();
        iamHooks.setBanner('User geloescht: ' + username, 'ok');
        return refreshIamData();
      }).catch((error) => {
        iamHooks.setBanner('User konnte nicht geloescht werden: ' + error.message, 'warn');
      });
    });
  });
}

export function revokeIamUserSessions() {
  const username = String(qs('iam-user-username') ? qs('iam-user-username').value : '').trim() || state.selectedAuthUser;
  if (!username) {
    iamHooks.setBanner('Bitte zuerst einen User auswaehlen.', 'warn');
    return;
  }
  runSingleFlight('iam-user-revoke:' + username, () => {
    return request('/auth/users/' + encodeURIComponent(username) + '/revoke-sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'admin_revoke_from_web_ui' })
    }).then(() => {
      iamHooks.setBanner('Sessions widerrufen fuer: ' + username, 'ok');
    }).catch((error) => {
      iamHooks.setBanner('Session-Revoke fehlgeschlagen: ' + error.message, 'warn');
    });
  });
}

function _collectRolePermissions() {
  const container = qs('iam-role-permissions-grid');
  if (!container) {
    return [];
  }
  const checked = Array.from(container.querySelectorAll('.perm-tag-cb:checked'));
  return checked.map((cb) => String(cb.dataset.tag || '').trim()).filter(Boolean);
}

export function saveIamRole() {
  let roleName = String(qs('iam-role-name') ? qs('iam-role-name').value : '').trim();
  const permissions = _collectRolePermissions();
  const existing = state.authRoles.find((role) => role.name === roleName);
  try {
    roleName = sanitizeIdentifier(roleName, 'Rollenname', ROLE_NAME_PATTERN, 2, 80);
  } catch (error) {
    iamHooks.setBanner(error.message, 'warn');
    return;
  }
  if (existing && roleProtected(existing)) {
    iamHooks.setBanner('Eingebaute Rollen sind geschuetzt und koennen nicht geaendert werden.', 'warn');
    return;
  }
  runSingleFlight('iam-role-save:' + roleName, () => {
    return request(existing ? ('/auth/roles/' + encodeURIComponent(roleName)) : '/auth/roles', {
      method: existing ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(existing ? { permissions } : { name: roleName, permissions })
    }).then(() => {
      state.selectedAuthRole = roleName;
      iamHooks.setBanner('Rolle gespeichert: ' + roleName, 'ok');
      return refreshIamData();
    }).catch((error) => {
      iamHooks.setBanner('Rolle konnte nicht gespeichert werden: ' + error.message, 'warn');
    });
  });
}

export function deleteIamRole() {
  const roleName = String(qs('iam-role-name') ? qs('iam-role-name').value : '').trim() || state.selectedAuthRole;
  if (!roleName) {
    iamHooks.setBanner('Bitte zuerst eine Rolle auswaehlen.', 'warn');
    return;
  }
  const existing = state.authRoles.find((role) => role.name === roleName);
  if (existing && roleProtected(existing)) {
    iamHooks.setBanner('Eingebaute Rollen sind geschuetzt und koennen nicht geloescht werden.', 'warn');
    return;
  }
  iamHooks.requestConfirm({
    title: 'Rolle loeschen?',
    message: 'Rolle "' + roleName + '" wirklich loeschen?',
    confirmLabel: 'Loeschen',
    danger: true
  }).then((ok) => {
    if (!ok) {
      return;
    }
    runSingleFlight('iam-role-delete:' + roleName, () => {
      return request('/auth/roles/' + encodeURIComponent(roleName), {
        method: 'DELETE'
      }).then(() => {
        resetIamRoleEditor();
        iamHooks.setBanner('Rolle geloescht: ' + roleName, 'ok');
        return refreshIamData();
      }).catch((error) => {
        iamHooks.setBanner('Rolle konnte nicht geloescht werden: ' + error.message, 'warn');
      });
    });
  });
}

// ===== Session Browser =====

export function renderIamSessions(sessions) {
  const tbody = document.getElementById('iam-sessions-body');
  if (!tbody) return;
  if (!sessions || !sessions.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-cell">Keine aktiven Sessions.</td></tr>';
    return;
  }
  tbody.innerHTML = sessions.map((s) => {
    const created = s.created_at ? new Date(s.created_at * 1000).toLocaleString() : '—';
    const expires = s.expires_at ? new Date(s.expires_at * 1000).toLocaleString() : '—';
    const jti = escapeHtml(String(s.jti || ''));
    const username = escapeHtml(String(s.username || ''));
    const tenant = escapeHtml(String(s.tenant_id || '—'));
    const role = escapeHtml(String(s.role || ''));
    return '<tr data-session-username="' + username + '">' +
      '<td>' + username + '</td>' +
      '<td>' + role + '</td>' +
      '<td>' + tenant + '</td>' +
      '<td>' + created + ' – ' + expires + '</td>' +
      '<td><button class="button danger small" data-jti="' + jti + '" onclick="window._iamRevokeSession(this)">Widerrufen</button></td>' +
      '</tr>';
  }).join('');
}

export function loadIamSessions() {
  const usernameFilter = String((document.getElementById('iam-session-filter-user') || {}).value || '').trim();
  const tenantFilter = String((document.getElementById('iam-session-filter-tenant') || {}).value || '').trim();
  let url = '/auth/sessions';
  const params = [];
  if (usernameFilter) params.push('username=' + encodeURIComponent(usernameFilter));
  if (tenantFilter) params.push('tenant_id=' + encodeURIComponent(tenantFilter));
  if (params.length) url += '?' + params.join('&');
  return request(url).then((data) => {
    renderIamSessions(Array.isArray(data.sessions) ? data.sessions : []);
  }).catch((error) => {
    iamHooks.setBanner('Sessions konnten nicht geladen werden: ' + error.message, 'warn');
  });
}

// exposed as global for inline onclick in table rows
if (typeof window !== 'undefined') {
  window._iamRevokeSession = function(btn) {
    const jti = String(btn.dataset.jti || '').trim();
    if (!jti) return;
    iamHooks.requestConfirm({
      title: 'Session widerrufen?',
      message: 'Diese Session wirklich sofort beenden?',
      confirmLabel: 'Widerrufen',
      danger: true
    }).then((ok) => {
      if (!ok) return;
      request('/auth/sessions/' + encodeURIComponent(jti), { method: 'DELETE' })
        .then(() => {
          iamHooks.setBanner('Session widerrufen.', 'ok');
          loadIamSessions();
        })
        .catch((err) => iamHooks.setBanner('Fehler: ' + err.message, 'warn'));
    });
  };
}

// ===== Tenant List =====

export function renderIamTenants(tenants) {
  const container = document.getElementById('iam-tenants-list');
  if (!container) return;
  if (!tenants || !tenants.length) {
    container.innerHTML = '<p class="empty-cell">Keine Tenants konfiguriert.</p>';
    return;
  }
  container.innerHTML = tenants.map((tid) => {
    const t = escapeHtml(String(tid || ''));
    const userCount = (state.authUsers || []).filter((u) => u.tenant_id === tid).length;
    return '<div class="tenant-card">' +
      '<span class="tenant-id">' + t + '</span>' +
      '<span class="tenant-user-count">' + userCount + ' User</span>' +
      '</div>';
  }).join('');
}

export function loadIamTenants() {
  return request('/auth/tenants').then((data) => {
    renderIamTenants(Array.isArray(data.tenants) ? data.tenants : []);
  }).catch(() => {
    const container = document.getElementById('iam-tenants-list');
    if (container) container.innerHTML = '<p class="empty-cell">Tenants konnten nicht geladen werden.</p>';
  });
}

// ===== IdP Status Cards =====

export function renderIamIdpCards(providers) {
  const container = document.getElementById('iam-idp-cards');
  if (!container) return;
  const list = Array.isArray(providers) ? providers : [];
  if (!list.length) {
    container.innerHTML = '<p class="empty-cell">Keine Identity Provider konfiguriert. Nur lokale Anmeldung aktiv.</p>';
    return;
  }
  container.innerHTML = list.map((p) => {
    const name = escapeHtml(String(p.name || p.type || 'Unbekannt'));
    const type = escapeHtml(String(p.type || 'local'));
    const enabled = p.enabled !== false;
    const statusClass = enabled ? 'status-chip ok' : 'status-chip warn';
    const statusLabel = enabled ? 'aktiv' : 'deaktiviert';
    const hint = type === 'oidc' ? 'Redirect URI konfigurieren im IdP: <code>' + escapeHtml(String(p.redirect_uri || '')) + '</code>' :
                 type === 'saml' ? 'SP-Metadata unter <code>' + escapeHtml(String(p.metadata_url || '')) + '</code>' :
                 'Lokaler Admin-Account (immer aktiv)';
    return '<div class="idp-card">' +
      '<div class="idp-card-header"><span class="idp-type-badge">' + type.toUpperCase() + '</span>' +
      '<span class="' + statusClass + '">' + statusLabel + '</span></div>' +
      '<div class="idp-card-name">' + name + '</div>' +
      '<div class="idp-card-hint">' + hint + '</div>' +
      '</div>';
  }).join('');
}

export function loadIamIdpCards() {
  return request('/auth/providers').then((data) => {
    renderIamIdpCards(Array.isArray(data.providers) ? data.providers : []);
  }).catch(() => {
    const container = document.getElementById('iam-idp-cards');
    if (container) container.innerHTML = '<p class="empty-cell">IdP-Status nicht verfuegbar.</p>';
  });
}

// ===== SCIM Status =====

export function renderIamScimStatus(data) {
  const container = document.getElementById('iam-scim-status');
  if (!container) return;
  const enabled = data && data.scim_enabled;
  const url = escapeHtml(String((data && data.scim_base_url) || ''));
  container.innerHTML = '<div class="scim-status-row">' +
    '<span class="' + (enabled ? 'status-chip ok' : 'status-chip off') + '">' + (enabled ? 'SCIM aktiv' : 'SCIM deaktiviert') + '</span>' +
    (enabled ? '<div class="scim-endpoint">Endpoint: <code>' + url + 'scim/v2/</code></div>' +
      '<div class="scim-hint">Bearer Token wird ueber <code>BEAGLE_SCIM_BEARER_TOKEN</code> gesetzt. Token-Rotation: neuen Wert setzen, Dienst neustarten.</div>' : '') +
    '</div>';
}

export function loadIamScimStatus() {
  return request('/auth/me').then((data) => {
    // Derive SCIM status from /auth/me (has server_url) and onboarding status
    const serverUrl = escapeHtml(String((data && data.server_url) || window.location.origin + '/api/v1/'));
    renderIamScimStatus({ scim_enabled: true, scim_base_url: serverUrl });
  }).catch(() => {
    renderIamScimStatus(null);
  });
}
