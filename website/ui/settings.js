import { state } from './state.js';
import { escapeHtml, qs, text } from './dom.js';
import { request } from './api.js';

const settingsHooks = {
  setBanner() {}
};

let webhookRows = [];

export function configureSettings(nextHooks) {
  Object.assign(settingsHooks, nextHooks || {});
}

export function isAdminRole() {
  const role = (state.user && state.user.role) ? String(state.user.role).toLowerCase() : '';
  return role === 'admin' || role === 'superadmin';
}

export function updateSettingsVisibility() {
  const show = isAdminRole();
  const label = qs('settings-section-label');
  if (label) {
    label.style.display = show ? 'block' : 'none';
  }
  document.querySelectorAll('.sidebar-admin-item').forEach((btn) => {
    btn.style.display = show ? 'flex' : 'none';
  });
}

export function loadSettingsGeneral() {
  return request('/settings/general').then((data) => {
    if (qs('sg-server-name')) { qs('sg-server-name').value = data.server_name || ''; }
    if (qs('sg-hostname')) { qs('sg-hostname').value = data.hostname || ''; }
    if (qs('sg-timezone')) { qs('sg-timezone').value = data.timezone || ''; }
    if (qs('sg-public-url')) { qs('sg-public-url').value = data.public_url || ''; }
  }).catch((error) => {
    settingsHooks.setBanner('Allgemein laden fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function saveSettingsGeneral() {
  const payload = {
    server_name: String(qs('sg-server-name') ? qs('sg-server-name').value : '').trim(),
    hostname: String(qs('sg-hostname') ? qs('sg-hostname').value : '').trim(),
    timezone: String(qs('sg-timezone') ? qs('sg-timezone').value : '').trim(),
    public_url: String(qs('sg-public-url') ? qs('sg-public-url').value : '').trim()
  };
  return request('/settings/general', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then((data) => {
    if (data.ok) {
      settingsHooks.setBanner('Allgemeine Einstellungen gespeichert.', 'info');
      loadSettingsGeneral();
    } else {
      settingsHooks.setBanner('Fehler: ' + (data.errors || []).join(', '), 'warn');
    }
  }).catch((error) => {
    settingsHooks.setBanner('Speichern fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function loadSettingsSecurity() {
  return request('/settings/security').then((data) => {
    const tls = data.tls || {};
    text('tls-domain', tls.domain || '(nicht konfiguriert)');
    text('tls-provider', tls.provider || 'self-signed');
    text('tls-cert-exists', tls.certificate_exists ? 'Ja' : 'Nein');
    text('tls-nginx-active', tls.nginx_tls_enabled ? 'Ja' : 'Nein');
    if (qs('tls-req-domain') && tls.domain) { qs('tls-req-domain').value = tls.domain; }
    if (qs('tls-req-email') && tls.email) { qs('tls-req-email').value = tls.email; }
    const passwordPolicy = data.password_policy || {};
    if (qs('sec-pw-min-length')) { qs('sec-pw-min-length').value = passwordPolicy.min_length || 8; }
    const session = data.session || {};
    if (qs('sec-session-idle')) { qs('sec-session-idle').value = session.idle_timeout_minutes || 30; }
    if (qs('sec-session-max')) { qs('sec-session-max').value = session.max_sessions_per_user || 5; }
  }).catch((error) => {
    settingsHooks.setBanner('Sicherheit laden fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function saveSettingsSecurity() {
  const payload = {
    password_policy: {
      min_length: Number(qs('sec-pw-min-length') ? qs('sec-pw-min-length').value : 8)
    },
    session: {
      idle_timeout_minutes: Number(qs('sec-session-idle') ? qs('sec-session-idle').value : 30),
      max_sessions_per_user: Number(qs('sec-session-max') ? qs('sec-session-max').value : 5)
    }
  };
  return request('/settings/security', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then((data) => {
    if (data.ok) {
      settingsHooks.setBanner('Sicherheitseinstellungen gespeichert.', 'info');
    } else {
      settingsHooks.setBanner('Fehler: ' + (data.errors || []).join(', '), 'warn');
    }
  }).catch((error) => {
    settingsHooks.setBanner('Speichern fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function requestLetsEncrypt() {
  const domain = String(qs('tls-req-domain') ? qs('tls-req-domain').value : '').trim();
  const email = String(qs('tls-req-email') ? qs('tls-req-email').value : '').trim();
  if (!domain || !email) {
    settingsHooks.setBanner('Domain und E-Mail sind erforderlich.', 'warn');
    return;
  }
  settingsHooks.setBanner('Let\'s Encrypt Zertifikat wird angefordert...', 'info');
  request('/settings/security/tls/letsencrypt', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ domain, email }),
    __timeoutMs: 180000
  }).then((data) => {
    if (data.ok) {
      settingsHooks.setBanner('Zertifikat erfolgreich erstellt fuer ' + escapeHtml(domain), 'info');
      loadSettingsSecurity();
    } else {
      settingsHooks.setBanner('Let\'s Encrypt fehlgeschlagen: ' + escapeHtml(data.error || 'Unbekannter Fehler'), 'warn');
    }
  }).catch((error) => {
    settingsHooks.setBanner('Let\'s Encrypt Fehler: ' + error.message, 'warn');
  });
}

export function loadSettingsFirewall() {
  return request('/settings/firewall').then((data) => {
    text('fw-status', data.active ? 'Aktiv' : 'Inaktiv');
    const tbody = qs('fw-rules-body');
    if (!tbody) {
      return;
    }
    const rules = data.rules || [];
    if (!rules.length) {
      tbody.innerHTML = '<tr><td colspan="3" class="empty-cell">Keine Regeln vorhanden.</td></tr>';
      return;
    }
    tbody.innerHTML = rules.map((rule) => {
      return '<tr><td>' + escapeHtml(rule.number) + '</td><td>' + escapeHtml(rule.rule) + '</td><td><button class="button danger small fw-delete-rule" data-rule-num="' + escapeHtml(rule.number) + '">Loeschen</button></td></tr>';
    }).join('');
  }).catch((error) => {
    settingsHooks.setBanner('Firewall laden fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function firewallAction(action, extra) {
  const payload = Object.assign({ action }, extra || {});
  return request('/settings/firewall', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then((data) => {
    if (data.ok) {
      settingsHooks.setBanner('Firewall-Aktion erfolgreich.', 'info');
      loadSettingsFirewall();
    } else {
      settingsHooks.setBanner('Firewall-Fehler: ' + (data.errors || []).join(', '), 'warn');
    }
  }).catch((error) => {
    settingsHooks.setBanner('Firewall-Fehler: ' + error.message, 'warn');
  });
}

export function loadSettingsNetwork() {
  return request('/settings/network').then((data) => {
    const tbody = qs('net-interfaces-body');
    if (tbody) {
      const interfaces = data.interfaces || [];
      if (!interfaces.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-cell">Keine Schnittstellen.</td></tr>';
      } else {
        tbody.innerHTML = interfaces.map((iface) => {
          const addrs = (iface.addresses || []).map((addr) => {
            return escapeHtml(addr.address + '/' + addr.prefix);
          }).join(', ');
          return '<tr><td>' + escapeHtml(iface.name) + '</td><td>' + escapeHtml(iface.state) + '</td><td><code>' + escapeHtml(iface.mac) + '</code></td><td>' + (addrs || '—') + '</td></tr>';
        }).join('');
      }
    }
    text('net-dns-current', (data.dns_servers || []).join(', ') || '—');
    text('net-gateway', data.default_gateway || '—');
    if (qs('net-dns-input')) {
      qs('net-dns-input').value = (data.dns_servers || []).join(', ');
    }
  }).catch((error) => {
    settingsHooks.setBanner('Netzwerk laden fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function saveNetworkDns() {
  const raw = String(qs('net-dns-input') ? qs('net-dns-input').value : '').trim();
  const servers = raw.split(/[,\s]+/).filter((server) => server.length > 0);
  return request('/settings/network/dns', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dns_servers: servers })
  }).then((data) => {
    if (data.ok) {
      settingsHooks.setBanner('DNS-Einstellungen gespeichert.', 'info');
      loadSettingsNetwork();
    } else {
      settingsHooks.setBanner('DNS-Fehler: ' + escapeHtml(data.error || 'Unbekannt'), 'warn');
    }
  }).catch((error) => {
    settingsHooks.setBanner('DNS speichern fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function loadSettingsServices() {
  return request('/settings/services').then((data) => {
    const tbody = qs('svc-body');
    if (!tbody) {
      return;
    }
    const services = data.services || [];
    if (!services.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="empty-cell">Keine Dienste.</td></tr>';
      return;
    }
    tbody.innerHTML = services.map((service) => {
      const statusClass = service.status === 'active' ? 'badge-ok' : 'badge-warn';
      return '<tr><td>' + escapeHtml(service.name) + '</td><td><span class="badge ' + statusClass + '">' + escapeHtml(service.status) + '</span></td><td>' + escapeHtml(service.enabled) + '</td><td><button class="button ghost small svc-restart-btn" data-svc="' + escapeHtml(service.name) + '">Neustarten</button></td></tr>';
    }).join('');
  }).catch((error) => {
    settingsHooks.setBanner('Dienste laden fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function restartService(name) {
  return request('/settings/services/' + encodeURIComponent(name) + '/restart', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  }).then((data) => {
    if (data.ok) {
      settingsHooks.setBanner('Dienst "' + escapeHtml(name) + '" neugestartet. Status: ' + escapeHtml(data.status), 'info');
      loadSettingsServices();
    } else {
      settingsHooks.setBanner('Neustart fehlgeschlagen: ' + escapeHtml(data.error || 'Unbekannt'), 'warn');
    }
  }).catch((error) => {
    settingsHooks.setBanner('Neustart-Fehler: ' + error.message, 'warn');
  });
}

export function loadSettingsUpdates() {
  settingsHooks.setBanner('Suche nach Updates...', 'info');
  return request('/settings/updates', { __timeoutMs: 60000 }).then((data) => {
    text('upd-count', String(data.upgradable_count || 0));
    const tbody = qs('upd-packages-body');
    if (!tbody) {
      return;
    }
    const packages = data.upgradable || [];
    if (!packages.length) {
      tbody.innerHTML = '<tr><td colspan="2" class="empty-cell">System ist aktuell.</td></tr>';
      settingsHooks.setBanner('System ist aktuell.', 'info');
      return;
    }
    tbody.innerHTML = packages.map((pkg) => {
      return '<tr><td>' + escapeHtml(pkg.package) + '</td><td><code>' + escapeHtml(pkg.line) + '</code></td></tr>';
    }).join('');
    settingsHooks.setBanner(packages.length + ' Update(s) verfuegbar.', 'info');
  }).catch((error) => {
    settingsHooks.setBanner('Update-Check fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function applyUpdates() {
  if (!window.confirm('Alle verfuegbaren Updates jetzt installieren?')) {
    return;
  }
  settingsHooks.setBanner('Updates werden installiert...', 'info');
  request('/settings/updates/apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
    __timeoutMs: 600000
  }).then((data) => {
    if (data.ok) {
      settingsHooks.setBanner('Updates erfolgreich installiert.', 'info');
      loadSettingsUpdates();
    } else {
      settingsHooks.setBanner('Update fehlgeschlagen: ' + escapeHtml(data.error || 'Unbekannt'), 'warn');
    }
  }).catch((error) => {
    settingsHooks.setBanner('Update-Fehler: ' + error.message, 'warn');
  });
}

function backupScope() {
  const scopeType = String(qs('bak-scope-type') ? qs('bak-scope-type').value : 'pool').trim().toLowerCase();
  const scopeId = String(qs('bak-scope-id') ? qs('bak-scope-id').value : '').trim();
  if ((scopeType !== 'pool' && scopeType !== 'vm') || !scopeId) {
    return null;
  }
  return { scopeType, scopeId };
}

function backupPolicyPath(scope) {
  if (scope.scopeType === 'pool') {
    return '/backups/policies/pools/' + encodeURIComponent(scope.scopeId);
  }
  return '/backups/policies/vms/' + encodeURIComponent(scope.scopeId);
}

function renderBackupJobs(jobs) {
  const tbody = qs('bak-jobs-body');
  if (!tbody) {
    return;
  }
  if (!Array.isArray(jobs) || !jobs.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-cell">Keine Backup-Jobs vorhanden.</td></tr>';
    return;
  }
  tbody.innerHTML = jobs.map((job) => {
    return '<tr>' +
      '<td><code>' + escapeHtml(String(job.job_id || '')) + '</code></td>' +
      '<td>' + escapeHtml(String(job.status || '')) + '</td>' +
      '<td>' + escapeHtml(String(job.created_at || '')) + '</td>' +
      '<td>' + escapeHtml(String(job.finished_at || '')) + '</td>' +
      '<td>' + escapeHtml(String(job.archive || job.error || '')) + '</td>' +
    '</tr>';
  }).join('');
}

function loadBackupJobs(scope) {
  const path = '/backups/jobs?scope_type=' + encodeURIComponent(scope.scopeType) + '&scope_id=' + encodeURIComponent(scope.scopeId);
  return request(path).then((data) => {
    renderBackupJobs(data.jobs || []);
  }).catch((error) => {
    settingsHooks.setBanner('Backup-Jobs laden fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function loadSettingsBackup() {
  const scope = backupScope();
  if (!scope) {
    settingsHooks.setBanner('Backup-Scope ungueltig: Typ und ID setzen.', 'warn');
    renderBackupJobs([]);
    return Promise.resolve();
  }
  return request(backupPolicyPath(scope)).then((data) => {
    if (qs('bak-enabled')) { qs('bak-enabled').checked = Boolean(data.enabled); }
    if (qs('bak-schedule')) { qs('bak-schedule').value = data.schedule || 'daily'; }
    if (qs('bak-retention')) { qs('bak-retention').value = data.retention_days || 7; }
    if (qs('bak-target')) { qs('bak-target').value = data.target_path || '/var/backups/beagle'; }
    text('bak-last-run', data.last_backup || '(noch nie)');
    return loadBackupJobs(scope);
  }).catch((error) => {
    settingsHooks.setBanner('Backup laden fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function saveSettingsBackup() {
  const scope = backupScope();
  if (!scope) {
    settingsHooks.setBanner('Backup-Scope ungueltig: Typ und ID setzen.', 'warn');
    return Promise.resolve();
  }
  const payload = {
    enabled: Boolean(qs('bak-enabled') && qs('bak-enabled').checked),
    schedule: String(qs('bak-schedule') ? qs('bak-schedule').value : 'daily'),
    retention_days: Number(qs('bak-retention') ? qs('bak-retention').value : 7),
    target_path: String(qs('bak-target') ? qs('bak-target').value : '').trim()
  };
  return request(backupPolicyPath(scope), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then((data) => {
    if (data.ok) {
      settingsHooks.setBanner('Backup-Einstellungen gespeichert.', 'info');
      loadSettingsBackup();
    } else {
      settingsHooks.setBanner('Backup speichern fehlgeschlagen.', 'warn');
    }
  }).catch((error) => {
    settingsHooks.setBanner('Backup speichern fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function runBackupNow() {
  const scope = backupScope();
  if (!scope) {
    settingsHooks.setBanner('Backup-Scope ungueltig: Typ und ID setzen.', 'warn');
    return;
  }
  settingsHooks.setBanner('Backup wird erstellt...', 'info');
  request('/backups/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scope_type: scope.scopeType, scope_id: scope.scopeId })
  }).then((data) => {
    if (data.ok) {
      const job = data.job || {};
      settingsHooks.setBanner('Backup erstellt: ' + escapeHtml(String(job.archive || '')), 'info');
      loadSettingsBackup();
    } else {
      const job = data.job || {};
      settingsHooks.setBanner('Backup fehlgeschlagen: ' + escapeHtml(String(job.error || data.error || 'Unbekannt')), 'warn');
      loadSettingsBackup();
    }
  }).catch((error) => {
    settingsHooks.setBanner('Backup-Fehler: ' + error.message, 'warn');
  });
}

function parseWebhookEvents(raw) {
  const values = String(raw || '').split(/[\s,]+/).map((value) => value.trim().toLowerCase()).filter((value) => value.length > 0);
  return Array.from(new Set(values));
}

function resetWebhookForm() {
  if (qs('wh-url')) { qs('wh-url').value = ''; }
  if (qs('wh-events')) { qs('wh-events').value = ''; }
  if (qs('wh-secret')) { qs('wh-secret').value = ''; }
  if (qs('wh-enabled')) { qs('wh-enabled').checked = true; }
}

function renderWebhookRows() {
  const tbody = qs('wh-body');
  if (!tbody) {
    return;
  }
  if (!webhookRows.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-cell">Keine Webhooks konfiguriert.</td></tr>';
    return;
  }
  tbody.innerHTML = webhookRows.map((hook, idx) => {
    const statusText = hook.enabled ? 'aktiv' : 'inaktiv';
    const secretText = hook.has_secret || hook.secret ? 'gesetzt' : 'fehlt';
    const lastDelivery = hook.last_delivery_at || '—';
    const title = hook.last_error ? (' title="' + escapeHtml(hook.last_error) + '"') : '';
    return '<tr>' +
      '<td><code>' + escapeHtml(hook.id || ('draft-' + String(idx + 1))) + '</code></td>' +
      '<td>' + escapeHtml(hook.url || '') + '</td>' +
      '<td>' + escapeHtml((hook.events || []).join(', ')) + '</td>' +
      '<td><span class="badge ' + (hook.enabled ? 'badge-ok' : 'badge-warn') + '">' + escapeHtml(statusText) + '</span></td>' +
      '<td>' + escapeHtml(secretText) + '</td>' +
      '<td><span' + title + '>' + escapeHtml(lastDelivery) + '</span></td>' +
      '<td>' +
        '<button class="button ghost small wh-test" data-wh-idx="' + escapeHtml(String(idx)) + '">Test</button> ' +
        '<button class="button danger small wh-delete" data-wh-idx="' + escapeHtml(String(idx)) + '">Loeschen</button>' +
      '</td>' +
    '</tr>';
  }).join('');
}

export function loadSettingsWebhooks() {
  return request('/settings/webhooks').then((data) => {
    webhookRows = Array.isArray(data.webhooks) ? data.webhooks.map((item) => ({
      id: String(item.id || '').trim(),
      url: String(item.url || '').trim(),
      events: Array.isArray(item.events) ? item.events.map((value) => String(value || '').trim().toLowerCase()).filter((value) => value.length > 0) : [],
      enabled: Boolean(item.enabled),
      has_secret: Boolean(item.has_secret),
      secret: '',
      last_delivery_at: String(item.last_delivery_at || ''),
      last_status: Number(item.last_status || 0),
      last_error: String(item.last_error || '')
    })) : [];
    renderWebhookRows();
  }).catch((error) => {
    settingsHooks.setBanner('Webhooks laden fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function addWebhookFromForm() {
  const url = String(qs('wh-url') ? qs('wh-url').value : '').trim();
  const events = parseWebhookEvents(qs('wh-events') ? qs('wh-events').value : '');
  const secret = String(qs('wh-secret') ? qs('wh-secret').value : '').trim();
  const enabled = Boolean(qs('wh-enabled') && qs('wh-enabled').checked);

  if (!url || !(url.startsWith('https://') || url.startsWith('http://'))) {
    settingsHooks.setBanner('Webhook-URL muss mit http:// oder https:// beginnen.', 'warn');
    return;
  }
  if (!events.length) {
    settingsHooks.setBanner('Mindestens ein Event ist erforderlich.', 'warn');
    return;
  }
  if (!secret || secret.length < 12) {
    settingsHooks.setBanner('Webhook-Secret muss mindestens 12 Zeichen lang sein.', 'warn');
    return;
  }

  webhookRows.push({
    id: '',
    url,
    events,
    enabled,
    has_secret: true,
    secret,
    last_delivery_at: '',
    last_status: 0,
    last_error: ''
  });
  renderWebhookRows();
  resetWebhookForm();
  settingsHooks.setBanner('Webhook zur lokalen Liste hinzugefuegt. Zum Anwenden bitte speichern.', 'info');
}

export function saveSettingsWebhooks() {
  const webhooksPayload = webhookRows.map((hook) => {
    const entry = {
      id: hook.id || undefined,
      url: hook.url,
      events: Array.isArray(hook.events) ? hook.events : [],
      enabled: Boolean(hook.enabled)
    };
    const secret = String(hook.secret || '').trim();
    if (secret) {
      entry.secret = secret;
    }
    return entry;
  });
  return request('/settings/webhooks', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ webhooks: webhooksPayload })
  }).then((data) => {
    if (data.ok) {
      settingsHooks.setBanner('Webhooks gespeichert.', 'info');
      loadSettingsWebhooks();
    } else if (Array.isArray(data.errors) && data.errors.length) {
      settingsHooks.setBanner('Webhook-Fehler: ' + data.errors.join(', '), 'warn');
    } else {
      settingsHooks.setBanner('Webhook-Speichern fehlgeschlagen.', 'warn');
    }
  }).catch((error) => {
    settingsHooks.setBanner('Webhook-Speichern fehlgeschlagen: ' + error.message, 'warn');
  });
}

function testWebhook(index) {
  const item = webhookRows[index];
  if (!item || !item.id) {
    settingsHooks.setBanner('Webhook muss erst gespeichert werden, bevor ein Test moeglich ist.', 'warn');
    return;
  }
  request('/settings/webhooks/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: item.id })
  }).then((data) => {
    if (data.ok) {
      settingsHooks.setBanner('Webhook-Test gesendet: ' + String(data.delivered || 0) + '/' + String(data.attempted || 0) + ' erfolgreich.', 'info');
      loadSettingsWebhooks();
    } else {
      settingsHooks.setBanner('Webhook-Test fehlgeschlagen: ' + escapeHtml(data.error || 'Unbekannt'), 'warn');
    }
  }).catch((error) => {
    settingsHooks.setBanner('Webhook-Test fehlgeschlagen: ' + error.message, 'warn');
  });
}

function deleteWebhook(index) {
  if (index < 0 || index >= webhookRows.length) {
    return;
  }
  webhookRows.splice(index, 1);
  renderWebhookRows();
  settingsHooks.setBanner('Webhook aus lokaler Liste entfernt. Zum Anwenden bitte speichern.', 'info');
}

export function loadSettingsForPanel(panel) {
  if (!isAdminRole()) {
    return;
  }
  switch (panel) {
    case 'settings_general':
      loadSettingsGeneral();
      break;
    case 'settings_security':
      loadSettingsSecurity();
      break;
    case 'settings_firewall':
      loadSettingsFirewall();
      break;
    case 'settings_network':
      loadSettingsNetwork();
      break;
    case 'settings_services':
      loadSettingsServices();
      break;
    case 'settings_updates':
      loadSettingsUpdates();
      break;
    case 'settings_backup':
      loadSettingsBackup();
      break;
    case 'settings_webhooks':
      loadSettingsWebhooks();
      break;
    default:
      break;
  }
}

export function bindSettingsEvents() {
  if (qs('settings-general-save')) {
    qs('settings-general-save').addEventListener('click', saveSettingsGeneral);
  }
  if (qs('settings-general-refresh')) {
    qs('settings-general-refresh').addEventListener('click', loadSettingsGeneral);
  }
  if (qs('settings-security-save')) {
    qs('settings-security-save').addEventListener('click', saveSettingsSecurity);
  }
  if (qs('settings-security-refresh')) {
    qs('settings-security-refresh').addEventListener('click', loadSettingsSecurity);
  }
  if (qs('tls-request-cert')) {
    qs('tls-request-cert').addEventListener('click', requestLetsEncrypt);
  }
  if (qs('settings-firewall-refresh')) {
    qs('settings-firewall-refresh').addEventListener('click', loadSettingsFirewall);
  }
  if (qs('fw-enable')) {
    qs('fw-enable').addEventListener('click', () => {
      firewallAction('enable');
    });
  }
  if (qs('fw-disable')) {
    qs('fw-disable').addEventListener('click', () => {
      firewallAction('disable');
    });
  }
  if (qs('fw-add-rule')) {
    qs('fw-add-rule').addEventListener('click', () => {
      const rule = String(qs('fw-new-rule') ? qs('fw-new-rule').value : '').trim();
      if (!rule) {
        settingsHooks.setBanner('Bitte eine Regel eingeben.', 'warn');
        return;
      }
      firewallAction('add_rule', { rule });
    });
  }
  if (qs('fw-rules-body')) {
    qs('fw-rules-body').addEventListener('click', (event) => {
      const btn = event.target.closest('.fw-delete-rule');
      if (!btn) {
        return;
      }
      const num = btn.getAttribute('data-rule-num');
      if (num && window.confirm('Regel #' + num + ' wirklich loeschen?')) {
        firewallAction('delete_rule', { rule_number: num });
      }
    });
  }
  if (qs('settings-network-refresh')) {
    qs('settings-network-refresh').addEventListener('click', loadSettingsNetwork);
  }
  if (qs('net-dns-save')) {
    qs('net-dns-save').addEventListener('click', saveNetworkDns);
  }
  if (qs('settings-services-refresh')) {
    qs('settings-services-refresh').addEventListener('click', loadSettingsServices);
  }
  if (qs('svc-body')) {
    qs('svc-body').addEventListener('click', (event) => {
      const btn = event.target.closest('.svc-restart-btn');
      if (!btn) {
        return;
      }
      const name = btn.getAttribute('data-svc');
      if (name && window.confirm('Dienst "' + name + '" wirklich neustarten?')) {
        restartService(name);
      }
    });
  }
  if (qs('settings-updates-refresh')) {
    qs('settings-updates-refresh').addEventListener('click', loadSettingsUpdates);
  }
  if (qs('upd-apply')) {
    qs('upd-apply').addEventListener('click', applyUpdates);
  }
  if (qs('settings-backup-refresh')) {
    qs('settings-backup-refresh').addEventListener('click', loadSettingsBackup);
  }
  if (qs('bak-scope-type')) {
    qs('bak-scope-type').addEventListener('change', loadSettingsBackup);
  }
  if (qs('bak-scope-id')) {
    qs('bak-scope-id').addEventListener('change', loadSettingsBackup);
  }
  if (qs('settings-backup-save')) {
    qs('settings-backup-save').addEventListener('click', saveSettingsBackup);
  }
  if (qs('settings-backup-run')) {
    qs('settings-backup-run').addEventListener('click', runBackupNow);
  }
  if (qs('settings-webhooks-refresh')) {
    qs('settings-webhooks-refresh').addEventListener('click', loadSettingsWebhooks);
  }
  if (qs('wh-add')) {
    qs('wh-add').addEventListener('click', addWebhookFromForm);
  }
  if (qs('wh-clear')) {
    qs('wh-clear').addEventListener('click', resetWebhookForm);
  }
  if (qs('wh-save')) {
    qs('wh-save').addEventListener('click', saveSettingsWebhooks);
  }
  if (qs('wh-body')) {
    qs('wh-body').addEventListener('click', (event) => {
      const testBtn = event.target.closest('.wh-test');
      if (testBtn) {
        const idx = Number(testBtn.getAttribute('data-wh-idx'));
        if (!Number.isNaN(idx)) {
          testWebhook(idx);
        }
        return;
      }
      const deleteBtn = event.target.closest('.wh-delete');
      if (deleteBtn) {
        const idx = Number(deleteBtn.getAttribute('data-wh-idx'));
        if (!Number.isNaN(idx) && window.confirm('Webhook wirklich loeschen?')) {
          deleteWebhook(idx);
        }
      }
    });
  }
}