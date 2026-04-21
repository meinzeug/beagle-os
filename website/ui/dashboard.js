import { state } from './state.js';
import { request } from './api.js';
import { text } from './dom.js';

let dashboardLoadInFlight = null;

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
  dashboardLoadInFlight = Promise.all([
    request('/auth/me'),
    request('/health'),
    request('/vms'),
    request('/endpoints'),
    request('/policies'),
    request('/virtualization/overview'),
    request('/provisioning/catalog', { __suppressAuthLock: true }).catch(() => { return { catalog: null }; }),
    request('/auth/users', { __suppressAuthLock: true }).catch(() => []),
    request('/auth/roles', { __suppressAuthLock: true }).catch(() => [])
  ]).then((results) => {
    const me = results[0] || {};
    const health = results[1] || {};
    state.user = me.user || null;
    state.inventory = (results[2] && results[2].vms) || [];
    state.endpointReports = (results[3] && results[3].endpoints) || [];
    state.policies = (results[4] && results[4].policies) || [];
    state.virtualizationOverview = results[5] || null;
    state.provisioningCatalog = results[6] && results[6].catalog ? results[6].catalog : null;
    state.authUsers = Array.isArray(results[7]) ? results[7] : [];
    state.authRoles = Array.isArray(results[8]) ? results[8] : [];
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
    dashboardHooks.renderProvisioningWorkspace();
    dashboardHooks.updateFleetHealthAlert();
    dashboardHooks.setBanner('Verbunden. Inventar, Policies und Virtualisierung sind aktuell.', 'ok');
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