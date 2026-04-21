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
}

export function resetIamRoleEditor() {
  state.selectedAuthRole = '';
  if (qs('iam-role-name')) {
    qs('iam-role-name').value = '';
  }
  if (qs('iam-role-permissions')) {
    qs('iam-role-permissions').value = '';
  }
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
}

export function loadIamRoleIntoEditor(roleName) {
  const role = state.authRoles.find((entry) => entry.name === roleName);
  if (!role) {
    return;
  }
  state.selectedAuthRole = role.name;
  if (qs('iam-role-name')) {
    qs('iam-role-name').value = role.name || '';
  }
  if (qs('iam-role-permissions')) {
    qs('iam-role-permissions').value = (role.permissions || []).join('\n');
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
    return '<tr class="clickable-row' + selected + '" data-iam-role="' + escapeHtml(role.name) + '"><td>' + escapeHtml(role.name) + '</td><td>' + escapeHtml(preview || '-') + escapeHtml(suffix) + '</td></tr>';
  }).join('');
}

export function renderIam() {
  renderIamRoleSelect();
  renderIamUsers();
  renderIamRoles();
}

export function refreshIamData() {
  return Promise.all([
    request('/auth/users').catch(() => []),
    request('/auth/roles').catch(() => [])
  ]).then((results) => {
    state.authUsers = Array.isArray(results[0]) ? results[0] : [];
    state.authRoles = Array.isArray(results[1]) ? results[1] : [];
    if (state.selectedAuthUser && !state.authUsers.some((user) => user.username === state.selectedAuthUser)) {
      state.selectedAuthUser = '';
    }
    if (state.selectedAuthRole && !state.authRoles.some((role) => role.name === state.selectedAuthRole)) {
      state.selectedAuthRole = '';
    }
    renderIam();
  });
}

export function saveIamUser() {
  let username = String(qs('iam-user-username') ? qs('iam-user-username').value : '').trim();
  const role = String(qs('iam-user-role') ? qs('iam-user-role').value : '').trim();
  const password = String(qs('iam-user-password') ? qs('iam-user-password').value : '');
  const enabled = Boolean(qs('iam-user-enabled') && qs('iam-user-enabled').checked);
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
    return request(existing ? ('/auth/users/' + encodeURIComponent(username)) : '/auth/users', {
      method: existing ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(existing ? payload : {
        username,
        role,
        password,
        enabled
      })
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

export function saveIamRole() {
  let roleName = String(qs('iam-role-name') ? qs('iam-role-name').value : '').trim();
  const permissions = parsePermissions(qs('iam-role-permissions') ? qs('iam-role-permissions').value : '');
  const existing = state.authRoles.find((role) => role.name === roleName);
  try {
    roleName = sanitizeIdentifier(roleName, 'Rollenname', ROLE_NAME_PATTERN, 2, 80);
  } catch (error) {
    iamHooks.setBanner(error.message, 'warn');
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