import { browserCommon, panelMeta, state } from './ui/state.js';
import { configureApiAuth } from './ui/api.js';
import {
  buildAuthHeaders,
  canRefreshAfterAuthError,
  checkSessionTimeout,
  configureAuthUi,
  initTokenStores,
  loadIdentityProviders,
  lockSession,
  refreshAccessToken
} from './ui/auth.js';
import {
  bindSessionsEvents,
  configureSessions,
  renderSessionsPanel
} from './ui/sessions.js';
import {
  applyTitle,
  configurePanels,
  consumeTokenFromLocation,
  fetchOnboardingStatus,
  parseAppHash,
  requestConfirm,
  setActiveDetailPanel,
  setActivePanel,
  setAuthMode,
  setBanner,
  syncHash,
  updateSessionChrome
} from './ui/panels.js';
import {
  addToActivityLog,
  configureActivity,
  renderActivityLog,
  startDashboardPoll,
  updateAutoRefreshButton
} from './ui/activity.js';
import {
  configureInventory,
  filteredInventory,
  openInventoryWithNodeFilter,
  profileOf,
  renderEndpointsOverview,
  renderInventory,
  runVmPowerAction
} from './ui/inventory.js';
import {
  configureActions
} from './ui/actions.js';
import {
  configureTemplateBuilder,
  openTemplateBuilderModal
} from './ui/template_builder.js';
import {
  initMigrateModal,
  openMigrateModal
} from './ui/migration_modal.js';
import {
  configurePolicies,
  renderPolicies
} from './ui/policies.js';
import {
  configureProvisioning,
  renderProvisioningWorkspace
} from './ui/provisioning.js';
import {
  configureIam,
  renderIam
} from './ui/iam.js';
import {
  configureFleetHealth,
  renderFleetHealth
} from './ui/fleet_health.js';
import {
  configureSchedulerInsights,
  renderSchedulerInsights
} from './ui/scheduler_insights.js';
import {
  configureCostDashboard,
  renderCostDashboard
} from './ui/cost_dashboard.js';
import {
  configureEnergyDashboard,
  renderEnergyDashboard
} from './ui/energy_dashboard.js';
import {
  configureAudit,
  exportAuditCsv,
  loadAuditExportTargets,
  loadAuditFailureQueue,
  loadAuditReport,
  onAuditRangeChanged,
  replayAuditFailures,
  renderAudit,
  resetAuditFilters,
  runAuditReportBuilder,
  testAuditExportTarget
} from './ui/audit.js';
import {
  configureVirtualization,
  renderVirtualizationInspector,
  renderVirtualizationOverview,
  renderVirtualizationPanel
} from './ui/virtualization.js';
import {
  bindClusterEvents,
  configureCluster,
  renderClusterPanel
} from './ui/cluster.js';
import {
  bindEvents,
  configureEvents
} from './ui/events.js';
import {
  bindSettingsEvents,
  configureSettings,
  loadSettingsForPanel,
  updateSettingsVisibility
} from './ui/settings.js';
import {
  configureDashboard,
  loadDashboard
} from './ui/dashboard.js';
import {
  loadDarkModePreference,
  updateDarkModeButton
} from './ui/theme.js';
import {
  configureLive,
  connectLiveUpdates,
  disconnectLiveUpdates
} from './ui/live.js';
import { request } from './ui/api.js';
import {
  actionButton,
  escapeHtml,
  fieldBlock,
  formatDate,
  maskedFieldBlock
} from './ui/dom.js';

function buildUsbDownloadMenuHtml() {
  return (
    '<details class="detail-action-menu">' +
    '<summary class="btn btn-ghost">USB Sticks</summary>' +
    '<div class="detail-action-menu-panel">' +
    actionButton('download-linux', 'Installer Linux', 'ghost') +
    actionButton('download-windows', 'Installer Windows', 'ghost') +
    actionButton('download-live-usb', 'Live USB', 'ghost') +
    actionButton('download-live-usb-windows', 'Live USB Windows', 'ghost') +
    '</div>' +
    '</details>'
  );
}

function buildDetailActionsHtml(status) {
  let html = actionButton('refresh-detail', 'Refresh', 'ghost');
  if (status === 'stopped' || status === 'shutoff') {
    html += actionButton('vm-start', 'Starten', 'primary');
  }
  if (status === 'running') {
    html += actionButton('vm-migrate', 'VM verschieben', 'ghost');
    html += actionButton('vm-stop', 'Stoppen', 'ghost');
    html += actionButton('vm-reboot', 'Neustart', 'ghost');
    html += actionButton('novnc-ui', 'noVNC', 'ghost');
    html += actionButton('sunshine-ui', 'Sunshine', 'ghost');
    html += buildUsbDownloadMenuHtml();
  }
  if (status === 'stopped' || status === 'shutoff') {
    html += actionButton('open-template-builder', 'Als Template', 'ghost');
    html += buildUsbDownloadMenuHtml();
  }
  if (status === 'installing') {
    html += actionButton('vm-stop', 'Stoppen', 'ghost');
  }
  html += actionButton('vm-delete', 'VM loeschen', 'danger');
  return html;
}

function streamRuntimeVariantLabel(profile) {
  const runtime = profile && profile.stream_runtime ? profile.stream_runtime : {};
  const variant = String(runtime.variant || '').trim().toLowerCase();
  if (variant === 'beagle-stream-server') {
    return 'BeagleStream Server';
  }
  if (variant === 'sunshine-fallback') {
    return 'Sunshine Fallback';
  }
  return 'Unbekannt';
}

function streamRuntimeVariantBanner(profile) {
  const runtime = profile && profile.stream_runtime ? profile.stream_runtime : {};
  const variant = String(runtime.variant || '').trim().toLowerCase();
  if (variant === 'beagle-stream-server') {
    return '<div class="banner ok">Diese VM nutzt bereits den echten BeagleStream-Server-Fork.</div>';
  }
  if (variant === 'sunshine-fallback') {
    return '<div class="banner warn">Diese VM laeuft noch im Sunshine-Fallback. Der echte BeagleStream-Server-Fork ist hier noch nicht aktiv.</div>';
  }
  return '<div class="banner subtle">Der Stream-Runtime-Status dieser VM wurde noch nicht erkannt.</div>';
}

function buildSummaryPanelHtml(vmid, profile) {
  if (!profile) {
    return '<div class="banner warn">VM ' + vmid + ': Kein Profil verfuegbar.</div>';
  }
  const role = String(profile.beagle_role || 'n/a').toUpperCase();
  return (
    streamRuntimeVariantBanner(profile) +
    '<div class="detail-section">' +
    '<h3>Endpoint Profil</h3>' +
    '<div class="detail-grid">' +
    fieldBlock('VMID', String(profile.vmid || vmid)) +
    fieldBlock('Name', profile.name || 'n/a') +
    fieldBlock('Status', profile.status || 'n/a') +
    fieldBlock('Node', profile.node || 'n/a') +
    fieldBlock('Rolle', role) +
    fieldBlock('Stream-Host', profile.stream_host || 'n/a') +
    fieldBlock('Moonlight-Port', profile.moonlight_port ? String(profile.moonlight_port) : 'n/a') +
    fieldBlock('Stream-Runtime', streamRuntimeVariantLabel(profile)) +
    fieldBlock('Stream-Paket', profile.stream_runtime && profile.stream_runtime.package_url ? profile.stream_runtime.package_url : 'n/a') +
    fieldBlock('Installer geeignet', profile.installer_target_eligible ? 'Ja' : 'Nein') +
    fieldBlock('Letzte Aenderung', formatDate(profile.updated_at || profile.provisioned_at || '')) +
    '</div>' +
    '</div>'
  );
}

function buildCredentialsPanelHtml(credentials) {
  if (!credentials) {
    return '<div class="banner warn">Credentials nicht verfuegbar.</div>';
  }
  return (
    '<div class="detail-section">' +
    '<h3>Sensitive Daten</h3>' +
    '<div class="detail-grid">' +
    maskedFieldBlock('Thin-Client Passwort', credentials.thinclient_password) +
    maskedFieldBlock('Guest Passwort', credentials.guest_password) +
    maskedFieldBlock('Sunshine Benutzername', credentials.sunshine_username) +
    maskedFieldBlock('Sunshine Passwort', credentials.sunshine_password) +
    maskedFieldBlock('Sunshine PIN', credentials.sunshine_pin) +
    fieldBlock('USB-Tunnel Host', credentials.usb_tunnel_host || 'n/a') +
    fieldBlock('USB-Tunnel Benutzer', credentials.usb_tunnel_user || 'n/a') +
    fieldBlock('USB-Tunnel Port', credentials.usb_tunnel_port ? String(credentials.usb_tunnel_port) : 'n/a') +
    '</div>' +
    '</div>'
  );
}

function buildUpdatesPanelHtml(update) {
  if (!update) {
    return '<div class="banner info">Keine Update-Informationen verfuegbar.</div>';
  }
  const policy = update.policy || {};
  const endpoint = update.endpoint || {};
  const compatibility = update.compatibility || {};
  const reinstallReasons = Array.isArray(compatibility.reinstall_reasons) ? compatibility.reinstall_reasons : [];
  const migrationReasons = Array.isArray(compatibility.migration_reasons) ? compatibility.migration_reasons : [];
  const rebuildRequired = Boolean(compatibility.rebuild_recommended || compatibility.reinstall_required || compatibility.migration_required);
  const healthFailure = Boolean(endpoint.health_failure || endpoint.rollback_recommended);
  const compatibilityBanner = rebuildRequired
    ? '<div class="banner warn"><strong>Thinclient/Live-USB neu bauen empfohlen.</strong><br>' +
      (compatibility.reinstall_required
        ? 'Diese Endpoint-Version kann nicht sicher per Self-Update migriert werden.'
        : 'Diese Endpoint-Version braucht zuerst eine Migrationsstufe.') +
      (reinstallReasons.length || migrationReasons.length
        ? '<ul>' + reinstallReasons.concat(migrationReasons).map((item) => '<li>' + escapeHtml(String(item)) + '</li>').join('') + '</ul>'
        : '') +
      '</div>'
    : '<div class="banner ok">Self-Update ist fuer diesen Endpoint-Pfad freigegeben.</div>';
  const healthBanner = healthFailure
    ? '<div class="banner warn"><strong>Runtime-Health fehlgeschlagen.</strong><br>Rollback oder Repair ist empfohlen. Letzter Fehler: ' +
      escapeHtml(endpoint.last_error || 'n/a') + '</div>'
    : '';
  return (
    compatibilityBanner +
    healthBanner +
    '<div class="detail-section">' +
    '<h3>Update Policy</h3>' +
    '<div class="detail-grid">' +
    fieldBlock('Update aktiviert', policy.enabled !== false ? 'Ja' : 'Nein') +
    fieldBlock('Kanal', policy.channel || 'stable') +
    fieldBlock('Verhalten', policy.behavior || 'prompt') +
    fieldBlock('Version Pin', policy.version_pin || 'n/a') +
    fieldBlock('Update-Pfad', compatibility.update_path || 'self_update') +
    fieldBlock('Min. Self-Update', compatibility.minimum_self_update_version || 'n/a') +
    fieldBlock('Installiert', endpoint.current_version || 'n/a') +
    fieldBlock('Publiziert', update.published_latest_version || 'n/a') +
    fieldBlock('Status', endpoint.state || 'n/a') +
    fieldBlock('Pending Reboot', endpoint.pending_reboot ? 'Ja' : 'Nein') +
    '</div>' +
    '</div>' +
    '<div class="button-row section-spaced-tight">' +
    actionButton('update-check', 'Update pruefen', 'ghost') +
    actionButton('update-apply', 'Update anwenden', 'primary') +
    '</div>'
  );
}

function buildUsbPanelHtml(usb) {
  if (!usb) {
    return '<div class="banner info">Keine USB-Informationen verfuegbar.</div>';
  }
  const attached = Array.isArray(usb.attached) ? usb.attached : [];
  return (
    '<div class="detail-section"><h3>USB Devices</h3><div class="button-row">' + actionButton('usb-refresh', 'USB aktualisieren', 'ghost') + '</div></div>' +
    '<div class="table-wrap compact section-spaced-tight"><table class="vm-table compact-table"><thead><tr><th>Bus-ID</th><th>Name</th><th>Aktion</th></tr></thead><tbody>' +
    (attached.length ? attached.map((d) =>
      '<tr><td>' + escapeHtml(String(d.busid || '')) + '</td><td>' + escapeHtml(String(d.name || '')) + '</td>' +
      '<td><button type="button" class="btn btn-ghost" data-action="usb-detach"' +
      ' data-usb-busid="' + escapeHtml(String(d.busid || '')) + '"' +
      ' data-usb-port="' + escapeHtml(String(d.port || '')) + '">Detach</button></td></tr>'
    ).join('') : '<tr><td colspan="3" class="empty-cell">Keine USB-Geraete verbunden.</td></tr>') +
    '</tbody></table></div>'
  );
}

function buildTasksPanelHtml(pendingActions) {
  if (!pendingActions || !pendingActions.length) {
    return '<div class="banner info">Keine offenen Tasks.</div>';
  }
  return (
    '<div class="detail-section"><h3>Queue</h3>' +
    '<div class="table-wrap compact"><table class="vm-table compact-table"><thead><tr><th>Aktion</th><th>Status</th><th>Zeit</th></tr></thead><tbody>' +
    pendingActions.map((a) =>
      '<tr><td>' + escapeHtml(String(a.action || '')) + '</td><td>' + escapeHtml(String(a.status || '')) +
      '</td><td>' + escapeHtml(formatDate(a.scheduled_at || a.created_at || '')) + '</td></tr>'
    ).join('') +
    '</tbody></table></div></div>'
  );
}

function buildBundlesPanelHtml(bundles) {
  if (!bundles || !bundles.length) {
    return '<div class="banner info">Keine Support-Bundles vorhanden.</div>';
  }
  return (
    '<div class="detail-section"><h3>Support Bundles</h3>' +
    '<div class="table-wrap compact"><table class="vm-table compact-table"><thead><tr><th>Name</th><th>Groesse</th><th>Zeit</th></tr></thead><tbody>' +
    bundles.map((b) =>
      '<tr><td>' + escapeHtml(String(b.name || '')) + '</td><td>' + escapeHtml(String(b.size || '')) +
      '</td><td>' + escapeHtml(formatDate(b.created_at || '')) + '</td></tr>'
    ).join('') +
    '</tbody></table></div></div>'
  );
}

function showDetailPage(show) {
  const listSection = document.getElementById('inventory-section');
  const detailPage = document.getElementById('vm-detail-page');
  if (listSection) {
    listSection.hidden = show;
    listSection.classList.toggle('panel-section-active', !show && state.activePanel === 'inventory');
  }
  if (detailPage) {
    detailPage.hidden = !show;
    detailPage.classList.toggle('panel-section-active', show && state.activePanel === 'inventory');
  }
}

function closeDetail() {
  state.selectedVmid = null;
  showDetailPage(false);
  renderInventory();
  syncHash();
}

function loadDetail(vmid) {
  const numericVmid = Number(vmid);
  if (!numericVmid) return Promise.resolve();

  state.selectedVmid = numericVmid;
  showDetailPage(true);

  const titleEl = document.getElementById('detail-title');
  const breadcrumbEl = document.getElementById('vdp-breadcrumb-name');
  const actionsEl = document.getElementById('detail-actions');
  const statusChipEl = document.getElementById('detail-status-chip');
  const stackEl = document.getElementById('detail-stack');
  const vmMetaEl = document.getElementById('detail-vm-meta');

  const vmEntry = state.inventory.find((v) => Number(profileOf(v).vmid) === numericVmid);
  const profile = vmEntry ? profileOf(vmEntry) : null;
  const displayName = profile
    ? (String(profile.name || '').trim() || 'VM ' + numericVmid)
    : 'VM ' + numericVmid;

  if (titleEl) titleEl.textContent = displayName;
  if (breadcrumbEl) breadcrumbEl.textContent = displayName;

  const status = String((profile && profile.status) || '').toLowerCase();

  if (statusChipEl) {
    statusChipEl.textContent = status ? status.toUpperCase() : 'UNBEKANNT';
    statusChipEl.className = 'chip ' + (status === 'running' ? 'ok' : status === 'installing' ? 'info' : status ? 'warn' : 'muted');
  }

  if (vmMetaEl) {
    vmMetaEl.innerHTML =
      (profile && profile.node ? '<span>#' + escapeHtml(String(numericVmid)) + ' &middot; ' + escapeHtml(profile.node) + '</span>' : '') +
      (profile && profile.beagle_role ? '<span>' + escapeHtml(String(profile.beagle_role).toUpperCase()) + '</span>' : '');
  }

  // Populate hero stat tiles
  const tileStatus = document.getElementById('vdp-tile-status');
  const tileNode   = document.getElementById('vdp-tile-node');
  const tileRole   = document.getElementById('vdp-tile-role');
  const tileStream = document.getElementById('vdp-tile-stream');
  const statStatus = document.getElementById('vdp-stat-status');

  if (tileStatus) tileStatus.textContent = status ? status.charAt(0).toUpperCase() + status.slice(1) : '—';
  if (tileNode)   tileNode.textContent   = (profile && profile.node)         ? String(profile.node)         : '—';
  if (tileRole)   tileRole.textContent   = (profile && profile.beagle_role)  ? String(profile.beagle_role).toUpperCase() : '—';
  if (tileStream) tileStream.textContent = (profile && profile.stream_host)  ? String(profile.stream_host) + (profile.moonlight_port ? ':' + profile.moonlight_port : '') : '—';
  if (statStatus) {
    statStatus.classList.remove('vdp-running', 'vdp-installing');
    if (status === 'running')    statStatus.classList.add('vdp-running');
    if (status === 'installing') statStatus.classList.add('vdp-installing');
  }

  if (actionsEl) {
    actionsEl.innerHTML = buildDetailActionsHtml(status);
  }

  if (stackEl) {
    stackEl.innerHTML =
      '<div class="detail-panel" data-detail-panel="summary">' + buildSummaryPanelHtml(numericVmid, profile) + '</div>' +
      '<div class="detail-panel" data-detail-panel="updates"><div class="banner info">Wird geladen...</div></div>' +
      '<div class="detail-panel" data-detail-panel="tasks"><div class="banner info">Wird geladen...</div></div>' +
      '<div class="detail-panel" data-detail-panel="usb"><div class="banner info">Wird geladen...</div></div>' +
      '<div class="detail-panel" data-detail-panel="credentials"><div class="banner info">Wird geladen...</div></div>' +
      '<div class="detail-panel" data-detail-panel="config"><div class="banner info">Konfiguration wird geladen...</div></div>' +
      '<div class="detail-panel" data-detail-panel="bundles"><div class="banner info">Wird geladen...</div></div>';
    setActiveDetailPanel(state.activeDetailPanel || 'summary');
  }

  syncHash();

  return Promise.all([
    request('/vms/' + numericVmid + '/credentials').then((data) => {
      if (state.selectedVmid !== numericVmid || !stackEl) return;
      const panel = stackEl.querySelector('[data-detail-panel="credentials"]');
      if (panel) panel.innerHTML = buildCredentialsPanelHtml(data && data.credentials);
    }).catch((err) => {
      if (state.selectedVmid !== numericVmid || !stackEl) return;
      const panel = stackEl.querySelector('[data-detail-panel="credentials"]');
      if (panel) panel.innerHTML = '<div class="banner warn">Credentials: ' + escapeHtml(err.message) + '</div>';
    }),
    request('/vms/' + numericVmid + '/update').then((data) => {
      if (state.selectedVmid !== numericVmid || !stackEl) return;
      const panel = stackEl.querySelector('[data-detail-panel="updates"]');
      if (panel) panel.innerHTML = buildUpdatesPanelHtml(data && data.update);
    }).catch(() => {
      if (state.selectedVmid !== numericVmid || !stackEl) return;
      const panel = stackEl.querySelector('[data-detail-panel="updates"]');
      if (panel) panel.innerHTML = '<div class="banner info">Update-Informationen nicht verfuegbar.</div>';
    }),
    request('/vms/' + numericVmid + '/usb').then((data) => {
      if (state.selectedVmid !== numericVmid || !stackEl) return;
      const panel = stackEl.querySelector('[data-detail-panel="usb"]');
      if (panel) panel.innerHTML = buildUsbPanelHtml(data && data.usb);
    }).catch(() => {
      if (state.selectedVmid !== numericVmid || !stackEl) return;
      const panel = stackEl.querySelector('[data-detail-panel="usb"]');
      if (panel) panel.innerHTML = '<div class="banner info">USB-Informationen nicht verfuegbar.</div>';
    }),
    request('/vms/' + numericVmid + '/actions').then((data) => {
      if (state.selectedVmid !== numericVmid || !stackEl) return;
      const panel = stackEl.querySelector('[data-detail-panel="tasks"]');
      if (panel) panel.innerHTML = buildTasksPanelHtml(data && data.pending_actions);
    }).catch(() => {
      if (state.selectedVmid !== numericVmid || !stackEl) return;
      const panel = stackEl.querySelector('[data-detail-panel="tasks"]');
      if (panel) panel.innerHTML = '<div class="banner info">Tasks nicht verfuegbar.</div>';
    }),
    request('/vms/' + numericVmid + '/support-bundles').then((data) => {
      if (state.selectedVmid !== numericVmid || !stackEl) return;
      const panel = stackEl.querySelector('[data-detail-panel="bundles"]');
      if (panel) panel.innerHTML = buildBundlesPanelHtml(data && data.support_bundles);
    }).catch(() => {
      if (state.selectedVmid !== numericVmid || !stackEl) return;
      const panel = stackEl.querySelector('[data-detail-panel="bundles"]');
      if (panel) panel.innerHTML = '<div class="banner info">Bundles nicht verfuegbar.</div>';
    }),
  ]).then(() => undefined);
}

function bootstrapHashState() {
  const hashState = parseAppHash();
  let storedPanel = '';
  let storedDetail = '';
  try {
    storedPanel = String(localStorage.getItem('beagle.ui.activePanel') || '').trim();
    storedDetail = String(localStorage.getItem('beagle.ui.activeDetailPanel') || '').trim();
  } catch (error) {
    void error;
  }
  if (hashState.panel) {
    state.activePanel = hashState.panel;
  } else if (storedPanel && panelMeta[storedPanel]) {
    state.activePanel = storedPanel;
  }
  if (hashState.detail) {
    state.activeDetailPanel = hashState.detail;
  } else if (storedDetail) {
    state.activeDetailPanel = storedDetail;
  }
  if (hashState.vmid && /^\d+$/.test(hashState.vmid)) {
    state.selectedVmid = Number(hashState.vmid);
  }
}

export function bootstrapApp() {
  if (!browserCommon) {
    throw new Error('BeagleBrowserCommon must be loaded before website/main.js');
  }

  initTokenStores(browserCommon);
  initMigrateModal();
  configureApiAuth({
    buildAuthHeaders,
    refreshAccessToken,
    canRefreshAfterAuthError,
    shouldHardLockOnUnauthorized(path) {
      return String(path || '').trim().indexOf('/auth/me') === 0;
    },
    lockSession
  });
  configureSettings({
    setBanner
  });
  configureInventory({
    setActivePanel,
    setBanner,
    addToActivityLog,
    loadDashboard,
    requestConfirm,
    loadDetail
  });
  configureActions({
    addToActivityLog,
    loadDashboard,
    requestConfirm,
    runVmPowerAction,
    setBanner,
    loadDetail,
    openTemplateBuilderModal,
    openMigrateModal: (opts) => openMigrateModal(opts),
  });
  configureTemplateBuilder({
    addToActivityLog,
    loadDashboard,
    setBanner,
    loadDetail
  });
  configurePolicies({
    addToActivityLog,
    loadDashboard,
    requestConfirm,
    setBanner
  });
  configureProvisioning({
    addToActivityLog,
    loadDashboard,
    setBanner
  });
  configureIam({
    requestConfirm,
    setBanner
  });
  configureFleetHealth({
    setBanner,
    requestConfirm,
    loadDashboard
  });
  configureAudit({
    setBanner
  });
  configureVirtualization({
    setBanner,
    loadDashboard
  });
  configureCluster({
    openInventoryWithNodeFilter,
    setBanner,
    loadDashboard
  });
  configureSessions({
    setBanner
  });
  configureEvents({
    setBanner,
    loadDetail,
    closeDetail,
    loadAuditReport,
    resetAuditFilters,
    exportAuditCsv,
    onAuditRangeChanged,
    loadAuditExportTargets,
    loadAuditFailureQueue,
    replayAuditFailures,
    runAuditReportBuilder,
    testAuditExportTarget
  });
  configurePanels({
    loadSettingsForPanel,
    loadIdentityProviders,
    loadAuditPanel: loadAuditReport,
    loadAuditExportTargets,
    loadAuditFailureQueue
  });
  configureAuthUi({
    setAuthMode,
    setBanner,
    updateSessionChrome,
    addToActivityLog,
    renderInventory,
    renderVirtualizationOverview,
    renderVirtualizationPanel,
    renderVirtualizationInspector,
    renderProvisioningWorkspace,
    renderClusterPanel,
    connectLiveUpdates,
    disconnectLiveUpdates
  });
  configureActivity({
    loadDashboard,
    loadAuditReport,
    setBanner
  });
  configureLive({
    loadDashboard,
    loadAuditReport,
    addToActivityLog,
    setBanner
  });
  configureDashboard({
    recordAuthSuccess() {},
    recordAuthFailure() {},
    filteredInventory,
    profileOf,
    setAuthMode,
    updateSettingsVisibility,
    renderInventory,
    renderEndpointsOverview,
    renderVirtualizationOverview,
    renderVirtualizationPanel,
    renderClusterPanel,
    renderSessionsPanel,
    renderFleetHealth,
    renderSchedulerInsights,
    renderCostDashboard,
    renderEnergyDashboard,
    renderProvisioningWorkspace,
    renderPolicies,
    renderIam,
    setBanner,
    loadDetail
  });
  configureSchedulerInsights({ setBanner });
  configureCostDashboard({ setBanner });
  configureEnergyDashboard({ setBanner });

  applyTitle();
  loadDarkModePreference();
  updateDarkModeButton();
  updateAutoRefreshButton();
  consumeTokenFromLocation();
  loadIdentityProviders().catch((error) => {
    console.warn('Identity provider registry unavailable, using local auth fallback:', error);
  });
  bindEvents();
  bindClusterEvents();
  bindSessionsEvents();
  bindSettingsEvents();
  renderActivityLog();
  renderInventory();
  renderEndpointsOverview();
  renderVirtualizationOverview();
  renderVirtualizationPanel();
  renderClusterPanel();
  renderSessionsPanel();
  renderVirtualizationInspector();
  renderProvisioningWorkspace();
  renderPolicies();
  renderIam();
  renderAudit();
  bootstrapHashState();
  setActivePanel(state.activePanel);
  setActiveDetailPanel(state.activeDetailPanel);
  setAuthMode(Boolean(state.token));
  updateSessionChrome();
  updateSettingsVisibility();

  fetchOnboardingStatus().catch((error) => {
    // Keep current session state intact on transient onboarding status errors.
    // Otherwise temporary 5xx responses can incorrectly force users into onboarding.
    if (!state.onboarding || typeof state.onboarding !== 'object') {
      state.onboarding = { pending: false, completed: false };
    }
    setBanner('Onboarding-Status temporaer nicht verfuegbar. Bitte erneut versuchen.', 'warn');
    console.warn('Onboarding status fallback enabled:', error);
  }).then(() => {
    return loadDashboard().then(() => {
      connectLiveUpdates();
    });
  });

  window.setInterval(checkSessionTimeout, 60000);
  window.addEventListener('hashchange', () => {
    const hashState = parseAppHash();
    if (hashState.panel && hashState.panel !== state.activePanel) {
      setActivePanel(hashState.panel);
    }
    if (hashState.detail && hashState.detail !== state.activeDetailPanel) {
      setActiveDetailPanel(hashState.detail);
    }
    // Handle vmid in hash (e.g. back/forward navigation)
    if (hashState.vmid && /^\d+$/.test(hashState.vmid)) {
      const vmid = Number(hashState.vmid);
      if (vmid !== state.selectedVmid) {
        loadDetail(vmid);
      }
    } else if (!hashState.vmid && state.selectedVmid && hashState.panel === 'inventory') {
      // Hash lost vmid — go back to list
      closeDetail();
    }
  });
  startDashboardPoll();

  window.addEventListener('beforeunload', () => {
    disconnectLiveUpdates();
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bootstrapApp, { once: true });
} else {
  bootstrapApp();
}
