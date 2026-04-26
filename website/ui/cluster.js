import { qs, escapeHtml, text } from './dom.js';
import { postJson, patchJson, deleteJson } from './api.js';
import { state } from './state.js';

const clusterHooks = {
  openInventoryWithNodeFilter() {},
  setBanner() {},
  loadDashboard() {}
};

let clusterEventsBound = false;

export function configureCluster(nextHooks) {
  Object.assign(clusterHooks, nextHooks || {});
}

export function bindClusterEvents() {
  if (clusterEventsBound) {
    return;
  }
  document.addEventListener('click', (event) => {
    const openModalTrigger = event.target.closest('[data-open-cluster-modal]');
    if (openModalTrigger) {
      openClusterModal(String(openModalTrigger.getAttribute('data-open-cluster-modal') || '').trim());
      return;
    }
    if (event.target.closest('[data-close-cluster-modal]')) {
      closeClusterModals();
      return;
    }
    const modalBackdrop = event.target.closest('.modal');
    if (modalBackdrop && modalBackdrop.id && modalBackdrop.id.startsWith('cluster-') && event.target === modalBackdrop) {
      closeClusterModals();
      return;
    }
    if (event.target.closest('#cluster-init-btn')) {
      createClusterFromWizard();
      return;
    }
    if (event.target.closest('#cluster-join-token-create')) {
      createClusterJoinToken();
      return;
    }
    if (event.target.closest('#cluster-setup-code-create')) {
      createClusterSetupCode();
      return;
    }
    if (event.target.closest('#cluster-add-server-preflight-btn')) {
      runAddServerPreflight();
      return;
    }
    if (event.target.closest('#cluster-leave-local-btn')) {
      leaveLocalCluster();
      return;
    }
    if (event.target.closest('#cluster-existing-btn')) {
      joinExistingClusterFromWizard();
      return;
    }

    const memberEditTrigger = event.target.closest('[data-cluster-member-edit]');
    if (memberEditTrigger) {
      const nodeName = String(memberEditTrigger.getAttribute('data-cluster-member-edit') || '').trim();
      if (nodeName) {
        openMemberEditForm(nodeName);
      }
      return;
    }

    const memberRemoveTrigger = event.target.closest('[data-cluster-member-remove]');
    if (memberRemoveTrigger) {
      const nodeName = String(memberRemoveTrigger.getAttribute('data-cluster-member-remove') || '').trim();
      if (nodeName) {
        removeClusterMember(nodeName, memberRemoveTrigger);
      }
      return;
    }

    const memberSaveTrigger = event.target.closest('#cluster-member-edit-save-btn');
    if (memberSaveTrigger) {
      saveClusterMemberEdit();
      return;
    }

    const maintenanceTrigger = event.target.closest('[data-cluster-maintenance-node]');
    if (maintenanceTrigger) {
      const nodeName = String(maintenanceTrigger.getAttribute('data-cluster-maintenance-node') || '').trim();
      if (!nodeName) {
        return;
      }
      if (!window.confirm('Knoten ' + nodeName + ' in Maintenance versetzen und Drain starten?')) {
        return;
      }
      maintenanceTrigger.disabled = true;
      postJson('/ha/maintenance/drain', { node_name: nodeName }).then((payload) => {
        const handled = Number(payload && payload.handled_vm_count ? payload.handled_vm_count : 0);
        clusterHooks.setBanner('Maintenance-Drain fuer ' + nodeName + ' gestartet (' + handled + ' VMs behandelt).', 'success');
        return clusterHooks.loadDashboard();
      }).catch((error) => {
        clusterHooks.setBanner('Maintenance-Drain fehlgeschlagen: ' + error.message, 'error');
      }).finally(() => {
        maintenanceTrigger.disabled = false;
      });
      return;
    }

    const trigger = event.target.closest('[data-cluster-node]');
    if (!trigger) {
      return;
    }
    const nodeName = String(trigger.getAttribute('data-cluster-node') || '').trim();
    if (!nodeName) {
      return;
    }
    clusterHooks.openInventoryWithNodeFilter(nodeName);
  });
  clusterEventsBound = true;
}

function openClusterModal(id) {
  const modal = qs(id);
  if (!modal) {
    return;
  }
  closeClusterModals();
  modal.hidden = false;
  modal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');
  window.setTimeout(() => {
    const firstInput = modal.querySelector('input, textarea, select, button');
    if (firstInput && typeof firstInput.focus === 'function') {
      firstInput.focus();
    }
  }, 0);
}

function closeClusterModals() {
  document.querySelectorAll('.modal[id^="cluster-"]').forEach((modal) => {
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
  });
  const openModal = Array.from(document.querySelectorAll('.modal')).some((modal) => !modal.hidden);
  if (!openModal) {
    document.body.classList.remove('modal-open');
  }
}

function fieldValue(id) {
  return String(qs(id) ? qs(id).value : '').trim();
}

function setFieldIfEmpty(id, value) {
  const el = qs(id);
  if (el && !String(el.value || '').trim() && value) {
    el.value = value;
  }
}

function currentHostFromUrl(urlValue) {
  try {
    return new URL(String(urlValue || ''), window.location.origin).hostname;
  } catch (error) {
    void error;
    return '';
  }
}

function normalizeComparable(value) {
  return String(value || '').trim().toLowerCase();
}

function isLocalClusterLeader(status, cluster, localMember) {
  if (!status || !cluster || !localMember) {
    return false;
  }
  const localName = normalizeComparable(localMember.name);
  const leaderName = normalizeComparable(cluster.leader_node);
  return Boolean(status.initialized && localName && leaderName && localName === leaderName);
}

function setElementHidden(id, hidden) {
  const el = qs(id);
  if (!el) {
    return;
  }
  el.hidden = Boolean(hidden);
}

function setActionDisabled(id, disabled) {
  const el = qs(id);
  if (!el) {
    return;
  }
  el.disabled = Boolean(disabled);
  el.setAttribute('aria-disabled', disabled ? 'true' : 'false');
}

function hostnameToNodeName(hostname) {
  const host = String(hostname || '').trim().replace(/^https?:\/\//i, '').split('/')[0].split(':')[0];
  const firstLabel = host.split('.')[0] || host;
  return firstLabel.replace(/[^A-Za-z0-9._-]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') || host;
}

function normalizeServerHostname(value) {
  return String(value || '').trim().replace(/^https?:\/\//i, '').split('/')[0].replace(/\/+$/g, '');
}

function fillAddServerExpertFieldsFromHostname(hostname) {
  const host = normalizeServerHostname(hostname);
  if (!host) {
    return null;
  }
  const hostWithoutPort = host.split(':')[0];
  const nodeName = fieldValue('cluster-add-server-node') || hostnameToNodeName(hostWithoutPort);
  const apiUrl = fieldValue('cluster-add-server-api-url') || ('https://' + host + '/beagle-api/api/v1');
  const rpcUrl = fieldValue('cluster-add-server-rpc') || ('https://' + hostWithoutPort + ':9089/rpc');
  if (qs('cluster-add-server-node')) {
    qs('cluster-add-server-node').value = nodeName;
  }
  if (qs('cluster-add-server-api-url')) {
    qs('cluster-add-server-api-url').value = apiUrl;
  }
  if (qs('cluster-add-server-host')) {
    qs('cluster-add-server-host').value = hostWithoutPort;
  }
  if (qs('cluster-add-server-rpc')) {
    qs('cluster-add-server-rpc').value = rpcUrl;
  }
  return {
    node_name: nodeName,
    api_url: apiUrl,
    advertise_host: hostWithoutPort,
    rpc_url: rpcUrl
  };
}

function renderClusterSetupPanel() {
  const status = state.clusterStatus || {};
  const cluster = status.cluster || {};
  const localMember = status.local_member || {};
  const initialized = Boolean(status.initialized);
  const defaultApiUrl = String((localMember && localMember.api_url) || '').trim();
  const defaultNode = String((localMember && localMember.name) || '').trim();
  const defaultHost = currentHostFromUrl(defaultApiUrl);
  const localLeader = isLocalClusterLeader(status, cluster, localMember);
  const localMemberOnly = initialized && !localLeader;
  const leaderNode = String(cluster.leader_node || '').trim();

  text('cluster-status-initialized', initialized ? 'Ja' : 'Nein');
  text('cluster-status-id', String(cluster.cluster_id || '—'));
  text('cluster-status-leader', leaderNode || '—');
  text('cluster-status-local', defaultNode || '—');
  text('cluster-leader-title', localLeader ? 'Dieser Server ist der Cluster-Leader' : (initialized ? 'Dieser Server ist Cluster-Mitglied' : 'Noch kein Cluster eingerichtet'));
  text(
    'cluster-leader-copy',
    localLeader
      ? 'Du arbeitest direkt auf dem fuehrenden Server. Neue Server werden von hier vorbereitet und erhalten einen Beitritts-Code.'
      : (initialized
        ? 'Leader: ' + (leaderNode || 'unbekannt') + '. Aktionen, die den Leader betreffen, muessen dort ausgefuehrt werden.'
        : 'Starte zuerst auf diesem Server einen Cluster oder fuege ihn einem bestehenden Cluster hinzu.')
  );
  text('cluster-leader-badge', localLeader ? 'LEADER' : (initialized ? 'MEMBER' : 'SETUP'));
  const leaderCard = qs('cluster-leader-card');
  if (leaderCard) {
    leaderCard.classList.toggle('cluster-leader-card-active', localLeader);
    leaderCard.classList.toggle('cluster-leader-card-member', initialized && !localLeader);
  }
  setElementHidden('cluster-actions-section', localMemberOnly);
  setElementHidden('cluster-technical-actions', !localMemberOnly);
  setElementHidden('cluster-action-init', initialized);
  setElementHidden('cluster-action-add-server', !localLeader);
  setElementHidden('cluster-action-token', !localLeader);
  setElementHidden('cluster-action-join-existing', initialized);
  setActionDisabled('cluster-action-init', initialized);
  setActionDisabled('cluster-action-add-server', !localLeader);
  setActionDisabled('cluster-action-token', !localLeader);
  setActionDisabled('cluster-action-join-existing', initialized);

  setFieldIfEmpty('cluster-init-node', defaultNode);
  setFieldIfEmpty('cluster-init-api-url', defaultApiUrl);
  setFieldIfEmpty('cluster-init-advertise-host', defaultHost);
  setFieldIfEmpty('cluster-existing-node', defaultNode);
  setFieldIfEmpty('cluster-existing-api-url', defaultApiUrl);
  setFieldIfEmpty('cluster-existing-advertise', defaultHost);
}

function createClusterFromWizard() {
  const payload = {
    node_name: fieldValue('cluster-init-node'),
    api_url: fieldValue('cluster-init-api-url'),
    advertise_host: fieldValue('cluster-init-advertise-host')
  };
  if (!payload.node_name || !payload.api_url || !payload.advertise_host) {
    clusterHooks.setBanner('Cluster erstellen: Node Name, API URL und Advertise Host sind erforderlich.', 'warn');
    return;
  }
  clusterHooks.setBanner('Cluster wird initialisiert ...', 'info');
  postJson('/cluster/init', payload).then(() => {
    clusterHooks.setBanner('Cluster wurde erstellt.', 'success');
    closeClusterModals();
    return clusterHooks.loadDashboard({ force: true });
  }).catch((error) => {
    clusterHooks.setBanner('Cluster-Erstellung fehlgeschlagen: ' + error.message, 'error');
  });
}

function createClusterJoinToken() {
  const ttl = Number(fieldValue('cluster-join-ttl') || 900);
  const payload = {
    ttl_seconds: Number.isFinite(ttl) ? Math.max(60, Math.min(86400, Math.round(ttl))) : 900
  };
  clusterHooks.setBanner('Join-Token wird erzeugt ...', 'info');
  postJson('/cluster/join-token', payload).then((data) => {
    const token = String(data && data.join_token ? data.join_token : '');
    if (qs('cluster-join-token-output')) {
      qs('cluster-join-token-output').value = token;
    }
    if (qs('cluster-existing-token') && !String(qs('cluster-existing-token').value || '').trim()) {
      qs('cluster-existing-token').value = token;
    }
    text('cluster-join-token-meta', 'Cluster ' + String(data.cluster_id || '—') + ' · Leader ' + String(data.leader_api_url || '—'));
    clusterHooks.setBanner('Join-Token erzeugt. Token auf dem neuen Server im Beitritts-Wizard einfuegen.', 'success');
  }).catch((error) => {
    clusterHooks.setBanner('Join-Token konnte nicht erzeugt werden: ' + error.message, 'error');
  });
}

function preflightStatusClass(status) {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'pass') {
    return 'chip good';
  }
  if (normalized === 'fail') {
    return 'chip bad';
  }
  if (normalized === 'warn') {
    return 'chip warn';
  }
  return 'chip muted';
}

function renderAddServerPreflight(preflight) {
  const out = qs('cluster-add-server-preflight-output');
  const tokenOut = qs('cluster-add-server-token-output');
  if (!out) {
    return;
  }
  const checks = Array.isArray(preflight && preflight.checks) ? preflight.checks : [];
  if (!checks.length) {
    out.innerHTML = '<div class="empty-cell">Noch kein Preflight ausgefuehrt.</div>';
    if (tokenOut) {
      tokenOut.value = '';
    }
    return;
  }
  out.innerHTML = checks.map((item) => {
    const status = String(item && item.status ? item.status : 'unknown');
    const name = String(item && item.name ? item.name : 'check');
    const message = String(item && item.message ? item.message : '');
    const required = item && item.required === false ? 'optional' : 'pflicht';
    return (
      '<div class="info-item">' +
      '<span class="' + preflightStatusClass(status) + '">' + escapeHtml(status) + '</span>' +
      '<span class="info-label">' + escapeHtml(name) + ' · ' + escapeHtml(required) + '</span>' +
      '<span class="info-value">' + escapeHtml(message) + '</span>' +
      '</div>'
    );
  }).join('');
  if (tokenOut) {
    tokenOut.value = '';
  }
}

function runAddServerPreflight() {
  const ttl = Number(fieldValue('cluster-add-server-token-ttl') || 900);
  const simpleHost = fieldValue('cluster-add-server-hostname');
  const setupCode = fieldValue('cluster-add-server-setup-code');
  const derived = fillAddServerExpertFieldsFromHostname(simpleHost) || {};
  const payload = {
    setup_code: setupCode,
    node_name: derived.node_name || fieldValue('cluster-add-server-node'),
    api_url: derived.api_url || fieldValue('cluster-add-server-api-url'),
    advertise_host: derived.advertise_host || fieldValue('cluster-add-server-host'),
    rpc_url: derived.rpc_url || fieldValue('cluster-add-server-rpc'),
    ssh_port: Number(fieldValue('cluster-add-server-ssh-port') || 22),
    token_ttl_seconds: Number.isFinite(ttl) ? Math.max(60, Math.min(86400, Math.round(ttl))) : 900
  };
  if (!payload.node_name || !payload.api_url || !payload.advertise_host) {
    clusterHooks.setBanner('Server hinzufügen: Bitte den Servernamen eingeben, z.B. srv2.beagle-os.com.', 'warn');
    return;
  }
  if (!payload.setup_code) {
    clusterHooks.setBanner('Server hinzufügen: Bitte den Setup-Code vom Zielserver eingeben.', 'warn');
    return;
  }
  const button = qs('cluster-add-server-preflight-btn');
  if (button) {
    button.disabled = true;
  }
  clusterHooks.setBanner('Verbinde ' + payload.advertise_host + ' sicher per Setup-Code ...', 'info');
  postJson('/cluster/auto-join', payload, { __timeoutMs: 30000 }).then((data) => {
    const autoJoin = data && data.auto_join ? data.auto_join : {};
    const preflight = autoJoin.preflight || {};
    renderAddServerPreflight(preflight);
    const target = autoJoin.target || {};
    const tokenOut = qs('cluster-add-server-token-output');
    if (tokenOut) {
      tokenOut.value = autoJoin.ok
        ? 'Server verbunden. Cluster: ' + String(target.cluster_id || '—') + '\nMember: ' + String(target.member && target.member.name ? target.member.name : payload.node_name) + '\nMember gesamt: ' + String(target.member_count || '—')
        : 'Auto-Join nicht abgeschlossen. Siehe Pruefung oben.';
    }
    if (autoJoin.ok) {
      clusterHooks.setBanner('Server wurde per Setup-Code verbunden.', 'success');
      return clusterHooks.loadDashboard({ force: true });
    }
    if (preflight && preflight.ok === false) {
      clusterHooks.setBanner('Der Server ist noch nicht bereit. Pruefung im Assistenten zeigt, was fehlt.', 'error');
    } else {
      clusterHooks.setBanner('Auto-Join wurde nicht abgeschlossen.', 'error');
    }
  }).catch((error) => {
    clusterHooks.setBanner('Auto-Join fehlgeschlagen: ' + error.message, 'error');
  }).finally(() => {
    if (button) {
      button.disabled = false;
    }
  });
}

function createClusterSetupCode() {
  const clusterStatus = state.clusterStatus || {};
  if (clusterStatus.initialized) {
    clusterHooks.setBanner('Dieser Server ist bereits Teil eines Clusters. Setup-Codes gibt es nur auf noch nicht verbundenen Zielservern.', 'warn');
    return;
  }
  const ttl = Number(fieldValue('cluster-setup-code-ttl') || 600);
  const payload = {
    ttl_seconds: Number.isFinite(ttl) ? Math.max(60, Math.min(1800, Math.round(ttl))) : 600
  };
  const button = qs('cluster-setup-code-create');
  if (button) {
    button.disabled = true;
  }
  clusterHooks.setBanner('Setup-Code wird auf diesem Server erzeugt ...', 'info');
  postJson('/cluster/setup-code', payload).then((data) => {
    const code = String(data && data.setup_code ? data.setup_code : '');
    if (qs('cluster-setup-code-output')) {
      qs('cluster-setup-code-output').value = code;
    }
    const expiresAt = Number(data && data.expires_at ? data.expires_at : 0);
    const expiryText = expiresAt > 0 ? new Date(expiresAt * 1000).toLocaleString() : 'unbekannt';
    text('cluster-setup-code-meta', 'Gueltig bis ' + expiryText + ' · einmalig nutzbar');
    clusterHooks.setBanner('Setup-Code erzeugt. Gib ihn im Leader-Wizard zusammen mit diesem Servernamen ein.', 'success');
  }).catch((error) => {
    const message = String(error && error.message ? error.message : '');
    if (message.indexOf('already part of a cluster') >= 0) {
      clusterHooks.setBanner('Dieser Server ist bereits Cluster-Mitglied. Ein Setup-Code ist nur fuer neue Zielserver moeglich.', 'warn');
      return;
    }
    clusterHooks.setBanner('Setup-Code konnte nicht erzeugt werden: ' + message, 'error');
  }).finally(() => {
    if (button) {
      button.disabled = false;
    }
  });
}

function leaveLocalCluster() {
  const clusterStatus = state.clusterStatus || {};
  const cluster = clusterStatus.cluster || {};
  const localMember = clusterStatus.local_member || {};
  if (!clusterStatus.initialized) {
    clusterHooks.setBanner('Dieser Server ist derzeit kein Cluster-Mitglied.', 'warn');
    return;
  }
  if (isLocalClusterLeader(clusterStatus, cluster, localMember)) {
    clusterHooks.setBanner('Der Cluster-Leader kann nicht lokal geloest werden.', 'warn');
    return;
  }
  const localName = String(localMember.name || '').trim() || 'dieser Server';
  const leaderNode = String(cluster.leader_node || '').trim() || 'der Leader';
  if (!window.confirm('Server ' + localName + ' jetzt sauber aus dem Cluster loesen? Der Leader ' + leaderNode + ' entfernt den Member zuerst aus dem Clusterzustand, danach wird die lokale Konfiguration bereinigt.')) {
    return;
  }
  const button = qs('cluster-leave-local-btn');
  if (button) {
    button.disabled = true;
  }
  clusterHooks.setBanner('Server wird lokal aus dem Cluster geloest ...', 'info');
  postJson('/cluster/leave-local', {}, { __timeoutMs: 15000 }).then(() => {
    clusterHooks.setBanner('Server wurde lokal aus dem Cluster geloest.', 'success');
    return clusterHooks.loadDashboard({ force: true });
  }).catch((error) => {
    clusterHooks.setBanner('Cluster-Loesung fehlgeschlagen: ' + error.message, 'error');
  }).finally(() => {
    if (button) {
      button.disabled = false;
    }
  });
}

function joinExistingClusterFromWizard() {
  const payload = {
    join_token: fieldValue('cluster-existing-token'),
    leader_api_url: fieldValue('cluster-existing-leader'),
    node_name: fieldValue('cluster-existing-node'),
    api_url: fieldValue('cluster-existing-api-url'),
    advertise_host: fieldValue('cluster-existing-advertise'),
    rpc_url: fieldValue('cluster-existing-rpc')
  };
  if (!payload.join_token || !payload.node_name || !payload.api_url || !payload.advertise_host) {
    clusterHooks.setBanner('Cluster-Beitritt: Join-Token, Node Name, API URL und Advertise Host sind erforderlich.', 'warn');
    return;
  }
  clusterHooks.setBanner('Server tritt dem Cluster bei ...', 'info');
  postJson('/cluster/join-existing', payload, { __timeoutMs: 30000 }).then(() => {
    clusterHooks.setBanner('Server wurde dem Cluster hinzugefuegt.', 'success');
    closeClusterModals();
    return clusterHooks.loadDashboard({ force: true });
  }).catch((error) => {
    clusterHooks.setBanner('Cluster-Beitritt fehlgeschlagen: ' + error.message, 'error');
  });
}

function openMemberEditForm(nodeName) {
  const modal = qs('cluster-member-edit-modal');
  if (!modal) {
    return;
  }
  const status = state.clusterStatus || {};
  const members = Array.isArray(status.members) ? status.members : [];
  const member = members.find((m) => String(m && m.name || '').trim() === nodeName) || {};
  if (qs('cluster-member-edit-name')) {
    qs('cluster-member-edit-name').value = nodeName;
  }
  if (qs('cluster-member-edit-display')) {
    qs('cluster-member-edit-display').value = String(member.display_name || '');
  }
  if (qs('cluster-member-edit-api-url')) {
    qs('cluster-member-edit-api-url').value = String(member.api_url || '');
  }
  if (qs('cluster-member-edit-rpc-url')) {
    qs('cluster-member-edit-rpc-url').value = String(member.rpc_url || '');
  }
  if (qs('cluster-member-edit-enabled')) {
    qs('cluster-member-edit-enabled').checked = member.enabled !== false;
  }
  openClusterModal('#cluster-member-edit-modal');
}

function saveClusterMemberEdit() {
  const nodeName = fieldValue('cluster-member-edit-name');
  if (!nodeName) {
    clusterHooks.setBanner('Kein Member ausgewaehlt.', 'warn');
    return;
  }
  const payload = {
    display_name: fieldValue('cluster-member-edit-display'),
    api_url: fieldValue('cluster-member-edit-api-url'),
    rpc_url: fieldValue('cluster-member-edit-rpc-url'),
  };
  const enabledEl = qs('cluster-member-edit-enabled');
  if (enabledEl) {
    payload.enabled = enabledEl.checked;
  }
  const btn = qs('cluster-member-edit-save-btn');
  if (btn) {
    btn.disabled = true;
  }
  clusterHooks.setBanner('Member wird aktualisiert ...', 'info');
  patchJson('/cluster/members/' + encodeURIComponent(nodeName), payload).then(() => {
    clusterHooks.setBanner('Member \'' + nodeName + '\' wurde aktualisiert.', 'success');
    closeClusterModals();
    return clusterHooks.loadDashboard();
  }).catch((error) => {
    clusterHooks.setBanner('Member-Update fehlgeschlagen: ' + error.message, 'error');
  }).finally(() => {
    if (btn) {
      btn.disabled = false;
    }
  });
}

function removeClusterMember(nodeName, triggerEl) {
  if (!window.confirm('Member \'' + nodeName + '\' jetzt aus dem Cluster entfernen?')) {
    return;
  }
  if (triggerEl) {
    triggerEl.disabled = true;
  }
  clusterHooks.setBanner('Member wird entfernt ...', 'info');
  deleteJson('/cluster/members/' + encodeURIComponent(nodeName)).then(() => {
    clusterHooks.setBanner('Member \'' + nodeName + '\' wurde entfernt.', 'success');
    return clusterHooks.loadDashboard();
  }).catch((error) => {
    clusterHooks.setBanner('Member-Entfernung fehlgeschlagen: ' + error.message, 'error');
  }).finally(() => {
    if (triggerEl) {
      triggerEl.disabled = false;
    }
  });
}

function statusChipClass(status) {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'online') {
    return 'chip good';
  }
  if (normalized === 'offline' || normalized === 'unreachable') {
    return 'chip bad';
  }
  return 'chip muted';
}

function clampPercent(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) {
    return 0;
  }
  if (numeric < 0) {
    return 0;
  }
  if (numeric > 100) {
    return 100;
  }
  return Math.round(numeric);
}

function clusterHaChipClass(status) {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'online' || normalized === 'active') {
    return 'chip good';
  }
  if (normalized === 'maintenance') {
    return 'chip muted';
  }
  if (normalized === 'fencing' || normalized === 'fenced' || normalized === 'offline' || normalized === 'unreachable') {
    return 'chip bad';
  }
  return 'chip muted';
}

function renderHaStatusPanel() {
  const haStatus = state.haStatus || {};
  const summary = haStatus.summary || {};
  const quorum = haStatus.quorum || {};
  const fencing = haStatus.fencing || {};
  const nodes = Array.isArray(haStatus.nodes) ? haStatus.nodes : [];
  const alerts = Array.isArray(haStatus.alerts) ? haStatus.alerts : [];

  const healthEl = qs('cluster-ha-health');
  const healthMetaEl = qs('cluster-ha-health-meta');
  const protectedEl = qs('cluster-ha-protected-vms');
  const quorumEl = qs('cluster-ha-quorum');
  const quorumMetaEl = qs('cluster-ha-quorum-meta');
  const fencingEl = qs('cluster-ha-fencing');
  const alertEl = qs('cluster-ha-alert');
  const bodyEl = qs('cluster-ha-nodes-body');

  const stateValue = String(haStatus.ha_state || 'unknown').toLowerCase();
  const stateText = stateValue ? stateValue.toUpperCase() : 'UNKNOWN';
  const quorumOnline = Number(quorum.online_nodes || 0);
  const quorumMin = Number(quorum.minimum_nodes || 0);
  const protectedVms = Number(summary.ha_protected_vms || 0);
  const fencingActive = Number((Array.isArray(fencing.nodes) ? fencing.nodes : []).filter((item) => Boolean(item && item.active)).length);

  if (healthEl) {
    healthEl.textContent = stateText;
    healthEl.classList.remove('cluster-ha-health-ok', 'cluster-ha-health-degraded', 'cluster-ha-health-failed');
    if (stateValue === 'ok') {
      healthEl.classList.add('cluster-ha-health-ok');
    } else if (stateValue === 'degraded') {
      healthEl.classList.add('cluster-ha-health-degraded');
    } else if (stateValue === 'failed') {
      healthEl.classList.add('cluster-ha-health-failed');
    }
  }
  if (healthMetaEl) {
    healthMetaEl.textContent = String(haStatus.generated_at || 'Keine Zeitbasis verfuegbar');
  }
  if (protectedEl) {
    protectedEl.textContent = String(protectedVms);
  }
  if (quorumEl) {
    quorumEl.textContent = String(quorumOnline) + '/' + String(quorumMin || 0);
  }
  if (quorumMetaEl) {
    quorumMetaEl.textContent = quorum.ok ? 'Quorum erfuellt' : 'Quorum unterschritten';
  }
  if (fencingEl) {
    fencingEl.textContent = String(fencingActive);
    fencingEl.classList.toggle('cluster-ha-fencing', fencingActive > 0);
  }

  if (alertEl) {
    if (alerts.length) {
      alertEl.textContent = alerts.join(' ');
      alertEl.classList.remove('hidden');
    } else {
      alertEl.textContent = 'Kein HA-Alert aktiv.';
      alertEl.classList.add('hidden');
    }
  }

  if (!bodyEl) {
    return;
  }
  if (!nodes.length) {
    bodyEl.innerHTML = '<tr><td colspan="5" class="empty-cell">Noch keine HA-Daten.</td></tr>';
    return;
  }

  bodyEl.innerHTML = nodes.map((node) => {
    const name = String(node && node.name ? node.name : '').trim() || '-';
    const status = String(node && node.status ? node.status : 'unknown').trim() || 'unknown';
    const lastHeartbeat = String(node && node.last_heartbeat_utc ? node.last_heartbeat_utc : '').trim() || '-';
    const protectedVmCount = Number(node && node.ha_protected_vms ? node.ha_protected_vms : 0);
    const fencingMethod = String(node && node.last_fencing_method ? node.last_fencing_method : '').trim();
    const fencingState = node && node.fencing_active ? 'aktiv' : (fencingMethod ? 'zuletzt: ' + fencingMethod : '-');
    return (
      '<tr>' +
      '<td>' + escapeHtml(name) + '</td>' +
      '<td><span class="' + clusterHaChipClass(status) + '">' + escapeHtml(status) + '</span></td>' +
      '<td><span class="cluster-ha-heartbeat">' + escapeHtml(lastHeartbeat) + '</span></td>' +
      '<td>' + String(protectedVmCount) + '</td>' +
      '<td>' + escapeHtml(fencingState) + '</td>' +
      '</tr>'
    );
  }).join('');
}

export function renderClusterPanel() {
  renderClusterSetupPanel();
  const body = qs('cluster-nodes-body');
  if (!body) {
    return;
  }

  const overview = state.virtualizationOverview || {};
  const nodes = Array.isArray(overview.nodes) ? overview.nodes : [];
  const vms = Array.isArray(state.inventory) ? state.inventory : [];

  const vmCountByNode = Object.create(null);
  vms.forEach((vm) => {
    const nodeName = String(vm && vm.node ? vm.node : '').trim();
    if (!nodeName) {
      return;
    }
    vmCountByNode[nodeName] = (vmCountByNode[nodeName] || 0) + 1;
  });

  const onlineCount = nodes.filter((node) => String(node.status || '').toLowerCase() === 'online').length;
  const unreachableCount = nodes.filter((node) => {
    const status = String(node.status || '').toLowerCase();
    return status === 'offline' || status === 'unreachable';
  }).length;

  const totalNodesEl = qs('cluster-total-nodes');
  const onlineNodesEl = qs('cluster-online-nodes');
  const unreachableNodesEl = qs('cluster-unreachable-nodes');
  const totalVmsEl = qs('cluster-total-vms');

  if (totalNodesEl) {
    totalNodesEl.textContent = String(nodes.length);
  }
  if (onlineNodesEl) {
    onlineNodesEl.textContent = String(onlineCount);
  }
  if (unreachableNodesEl) {
    unreachableNodesEl.textContent = String(unreachableCount);
  }
  if (totalVmsEl) {
    totalVmsEl.textContent = String(vms.length);
  }

  if (!nodes.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty-cell">Keine Cluster-Node-Daten verfuegbar.</td></tr>';
    renderHaStatusPanel();
    return;
  }

  body.innerHTML = nodes.map((node) => {
    const nodeName = String(node.name || node.id || '').trim();
    const nodeLabel = String(node.label || nodeName || '-').trim() || '-';
    const actionNodeName = String(node.provider_node_name || nodeName).trim() || nodeName;
    const status = String(node.status || 'unknown').trim() || 'unknown';
    const cpuPercent = clampPercent(Number(node.cpu || 0) * 100);
    const ramPercent = clampPercent(
      Number(node.maxmem || 0) > 0 ? (Number(node.mem || 0) / Number(node.maxmem || 1)) * 100 : 0
    );
    const vmCount = Number(node.vm_count || vmCountByNode[actionNodeName] || vmCountByNode[nodeName] || 0);
    return (
      '<tr>' +
      '<td>' + escapeHtml(nodeLabel) + '</td>' +
      '<td><span class="' + statusChipClass(status) + '">' + escapeHtml(status) + '</span></td>' +
      '<td>' + String(cpuPercent) + '%</td>' +
      '<td>' + String(ramPercent) + '%</td>' +
      '<td>' + String(vmCount) + '</td>' +
      '<td>' +
      '<button type="button" class="button ghost small" data-cluster-node="' + escapeHtml(actionNodeName) + '">VMs anzeigen</button> ' +
      '<button type="button" class="button ghost small" data-cluster-maintenance-node="' + escapeHtml(actionNodeName) + '">In Maintenance versetzen</button> ' +
      '<button type="button" class="button ghost small" data-cluster-member-edit="' + escapeHtml(actionNodeName) + '">Bearbeiten</button> ' +
      '<button type="button" class="button ghost small danger" data-cluster-member-remove="' + escapeHtml(actionNodeName) + '">Entfernen</button>' +
      '</td>' +
      '</tr>'
    );
  }).join('');

  renderHaStatusPanel();
}
