import { state } from './state.js';
import { request } from './api.js';
import { text } from './dom.js';

let dashboardLoadInFlight = null;

function currentUserPermissions(me) {
  const user = me && typeof me === 'object' ? me.user : null;
  const raw = user && Array.isArray(user.permissions) ? user.permissions : [];
  return new Set(raw.map((value) => String(value || '').trim()).filter(Boolean));
}

function canReadWithPermissions(permissions, permission) {
  const needed = String(permission || '').trim();
  if (!needed) {
    return true;
  }
  if (permissions.has('*')) {
    return true;
  }
  return permissions.has(needed);
}

const dashboardHooks = {
  filteredInventory() {
    return [];
  },
  profileOf(vm) {
    return vm || {};
  },
  recordAuthSuccess() {},
  recordAuthFailure() {},
  setAuthMode() {},
  updateSettingsVisibility() {},
  renderInventory() {},
  renderEndpointsOverview() {},
  renderVirtualizationOverview() {},
  renderPolicies() {},
  renderIam() {},
  renderVirtualizationPanel() {},
  renderClusterPanel() {},
  renderSessionsPanel() {},
  renderFleetHealth() {},
  renderProvisioningWorkspace() {},
  updateFleetHealthAlert() {},
  setBanner() {},
  loadDetail() {
    return Promise.resolve();
  }
};

export function configureDashboard(nextHooks) {
  Object.assign(dashboardHooks, nextHooks || {});
}

export function statCardFromHealth(payload, overview) {
  const counts = (payload && payload.endpoint_status_counts) || {};
  const provider = String((overview && overview.provider) || (payload && payload.provider) || '').trim();
  const nodeCount = Number((overview && overview.node_count) || 0);
  const storageCount = Number((overview && overview.storage_count) || 0);
  const bridgeCount = Number((overview && overview.bridge_count) || 0);
  let managerMeta = 'v' + String((payload && payload.version) || 'unknown');
  if (provider) {
    managerMeta += ' · ' + provider;
  }
  if (nodeCount > 0 || storageCount > 0) {
    managerMeta += ' · ' + String(nodeCount) + ' nodes · ' + String(storageCount) + ' storage · ' + String(bridgeCount) + ' bridges';
  }
  text('stat-manager', 'Online');
  text('stat-manager-meta', managerMeta);
  text('stat-vms', String((payload && payload.vm_count) || state.inventory.length || 0));
  text('stat-vms-meta', 'Active Beagle VMs: ' + String(dashboardHooks.filteredInventory().length));
  text('stat-endpoints', String((payload && payload.endpoint_count) || 0));
  text('stat-endpoints-meta', 'healthy ' + String(counts.healthy || 0) + ' · stale ' + String(counts.stale || 0) + ' · offline ' + String(counts.offline || 0));
  text('stat-policies', String((payload && payload.policy_count) || 0));
  text('stat-policies-meta', 'queued actions ' + String((payload && payload.pending_action_count) || 0));
  text('stat-nodes', String(nodeCount));
  const nodes = Array.isArray(overview && overview.nodes) ? overview.nodes : [];
  const onlineNodes = nodes.filter((node) => node.status === 'online').length;
  text('stat-nodes-meta', nodeCount > 0 ? 'online ' + String(onlineNodes) + ' / ' + String(nodeCount) : 'Keine Daten');
  text('stat-storage', String(storageCount));
  const storageItems = Array.isArray(overview && overview.storage) ? overview.storage : [];
  const activeStorage = storageItems.filter((storage) => storage.active).length;
  text('stat-storage-meta', storageCount > 0 ? 'active ' + String(activeStorage) + ' / ' + String(storageCount) : 'Keine Daten');
}

export function loadDashboard(options) {
  const opts = options || {};
  if (dashboardLoadInFlight && !opts.force) {
    return dashboardLoadInFlight;
  }
  if (state.onboarding && state.onboarding.pending) {
    dashboardHooks.setAuthMode(false);
    return Promise.resolve();
  }
  if (!state.token) {
    dashboardHooks.setAuthMode(false);
    dashboardHooks.setBanner('Nicht angemeldet.', 'warn');
    return Promise.resolve();
  }
  dashboardHooks.setBanner('Lade Beagle Manager...', 'info');
  dashboardLoadInFlight = request('/auth/me').then((me) => {
    const permissions = currentUserPermissions(me);
    const shouldLoadIam = state.activePanel === 'iam';
    const endpointRequests = [
      request('/health'),
      request('/vms'),
      request('/endpoints'),
      request('/policies'),
      request('/virtualization/overview'),
      canReadWithPermissions(permissions, 'cluster:read')
        ? request('/ha/status', { __suppressAuthLock: true })
        : Promise.resolve(null),
      canReadWithPermissions(permissions, 'cluster:read')
        ? request('/cluster/status', { __suppressAuthLock: true })
        : Promise.resolve(null),
      canReadWithPermissions(permissions, 'cluster:read')
        ? request('/nodes/install-checks', { __suppressAuthLock: true })
        : Promise.resolve({ reports: [], recent_reports: [], latest_ready_report: null }),
      request('/provisioning/catalog', { __suppressAuthLock: true }),
      shouldLoadIam && canReadWithPermissions(permissions, 'auth:read')
        ? request('/auth/users', { __suppressAuthLock: true })
        : Promise.resolve(state.authUsers),
      shouldLoadIam && canReadWithPermissions(permissions, 'auth:read')
        ? request('/auth/roles', { __suppressAuthLock: true })
        : Promise.resolve(state.authRoles),
      canReadWithPermissions(permissions, 'pool:read')
        ? request('/pools', { __suppressAuthLock: true })
        : Promise.resolve({ pools: [] }),
      canReadWithPermissions(permissions, 'pool:read')
        ? request('/pool-templates', { __suppressAuthLock: true })
        : Promise.resolve({ templates: [] }),
      canReadWithPermissions(permissions, 'pool:read')
        ? request('/sessions', { __suppressAuthLock: true })
        : Promise.resolve({ sessions: [] })
    ];
    return Promise.allSettled(endpointRequests).then((results) => {
      const health = results[0].status === 'fulfilled' ? (results[0].value || {}) : {};
      const vms = results[1].status === 'fulfilled' ? (results[1].value || {}) : {};
      const endpoints = results[2].status === 'fulfilled' ? (results[2].value || {}) : {};
      const policies = results[3].status === 'fulfilled' ? (results[3].value || {}) : {};
      const virtualizationOverview = results[4].status === 'fulfilled' ? (results[4].value || null) : null;
      const haStatus = results[5].status === 'fulfilled' ? (results[5].value || null) : null;
      const clusterStatus = results[6].status === 'fulfilled' ? (results[6].value || null) : null;
      const installChecks = results[7].status === 'fulfilled' ? (results[7].value || { reports: [], recent_reports: [], latest_ready_report: null }) : { reports: [], recent_reports: [], latest_ready_report: null };
      const provisioningCatalog = results[8].status === 'fulfilled' ? (results[8].value || { catalog: null }) : { catalog: null };
      const authUsers = results[9].status === 'fulfilled' && Array.isArray(results[9].value) ? results[9].value : [];
      const authRoles = results[10].status === 'fulfilled' && Array.isArray(results[10].value) ? results[10].value : [];
      const pools = results[11].status === 'fulfilled' ? (results[11].value || { pools: [] }) : { pools: [] };
      const templates = results[12].status === 'fulfilled' ? (results[12].value || { templates: [] }) : { templates: [] };
      const sessions = results[13].status === 'fulfilled' ? (results[13].value || { sessions: [] }) : { sessions: [] };
      const failedRequests = results.filter((result) => result.status !== 'fulfilled').length;

      state.user = me.user || null;
      state.inventory = vms.vms || [];
      state.endpointReports = endpoints.endpoints || [];
      state.policies = policies.policies || [];
      state.virtualizationOverview = virtualizationOverview;
      state.clusterStatus = clusterStatus;
      state.haStatus = haStatus;
      state.installChecks = installChecks;
      state.provisioningCatalog = provisioningCatalog.catalog || null;
      state.authUsers = authUsers;
      state.authRoles = authRoles;
      state.desktopPools = Array.isArray(pools.pools) ? pools.pools : [];
      state.poolTemplates = Array.isArray(templates.templates) ? templates.templates : [];
      state.sessions = Array.isArray(sessions.sessions) ? sessions.sessions : [];
      dashboardHooks.recordAuthSuccess();
      dashboardHooks.setAuthMode(true);
      dashboardHooks.updateSettingsVisibility();
      statCardFromHealth(health, state.virtualizationOverview);
      dashboardHooks.renderInventory();
      dashboardHooks.renderEndpointsOverview();
      dashboardHooks.renderVirtualizationOverview();
      dashboardHooks.renderPolicies();
      dashboardHooks.renderIam();
      dashboardHooks.renderVirtualizationPanel();
      dashboardHooks.renderClusterPanel();
      dashboardHooks.renderSessionsPanel();
      dashboardHooks.renderFleetHealth();
      dashboardHooks.renderProvisioningWorkspace();
      dashboardHooks.updateFleetHealthAlert();
      if (failedRequests > 0) {
        dashboardHooks.setBanner('Verbunden. ' + String(failedRequests) + ' API-Aufrufe momentan nicht verfuegbar.', 'warn');
      } else {
        dashboardHooks.setBanner('Verbunden. Inventar, Policies und Virtualisierung sind aktuell.', 'ok');
      }

      if (state.selectedVmid) {
        // Only restore detail if the VM still exists in the loaded inventory
        const exists = state.inventory.some((v) => Number(dashboardHooks.profileOf(v).vmid) === state.selectedVmid);
        if (exists) {
          return dashboardHooks.loadDetail(state.selectedVmid);
        }
        // VM no longer exists — clear it and show the list
        state.selectedVmid = null;
        dashboardHooks.renderInventory();
      }
      return null;
    });
  }).catch((error) => {
    dashboardHooks.recordAuthFailure();
    text('stat-manager', 'Error');
    text('stat-manager-meta', error.message);
    dashboardHooks.setBanner('Teilweise Ladefehler: ' + error.message + ' (Session bleibt aktiv).', 'warn');
  }).finally(() => {
    dashboardLoadInFlight = null;
  });
  return dashboardLoadInFlight;
}
