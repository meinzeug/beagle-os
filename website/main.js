import { browserCommon, panelMeta, state } from './ui/state.js';
import { configureApiAuth } from './ui/api.js';
import {
  buildAuthHeaders,
  canRefreshAfterAuthError,
  checkSessionTimeout,
  configureAuthUi,
  initTokenStores,
  lockSession,
  refreshAccessToken
} from './ui/auth.js';
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
  profileOf,
  renderEndpointsOverview,
  renderInventory,
  runVmPowerAction
} from './ui/inventory.js';
import {
  configureActions
} from './ui/actions.js';
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
  configureVirtualization,
  renderVirtualizationInspector,
  renderVirtualizationOverview,
  renderVirtualizationPanel
} from './ui/virtualization.js';
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
    setBanner
  });
  configureActions({
    addToActivityLog,
    loadDashboard,
    requestConfirm,
    runVmPowerAction,
    setBanner
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
  configureVirtualization({
    setBanner
  });
  configureEvents({
    setBanner
  });
  configurePanels({
    loadSettingsForPanel
  });
  configureAuthUi({
    setAuthMode,
    setBanner,
    updateSessionChrome,
    addToActivityLog,
    renderInventory,
    renderVirtualizationOverview,
    renderVirtualizationPanel,
    renderVirtualizationInspector
    ,renderProvisioningWorkspace
  });
  configureActivity({
    loadDashboard,
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
    renderProvisioningWorkspace,
    renderPolicies,
    renderIam,
    setBanner
  });

  applyTitle();
  loadDarkModePreference();
  updateDarkModeButton();
  updateAutoRefreshButton();
  consumeTokenFromLocation();
  bindEvents();
  bindSettingsEvents();
  renderActivityLog();
  renderInventory();
  renderEndpointsOverview();
  renderVirtualizationOverview();
  renderVirtualizationPanel();
  renderVirtualizationInspector();
  renderProvisioningWorkspace();
  renderPolicies();
  renderIam();
  bootstrapHashState();
  setActivePanel(state.activePanel);
  setActiveDetailPanel(state.activeDetailPanel);
  setAuthMode(Boolean(state.token));
  updateSessionChrome();
  updateSettingsVisibility();

  fetchOnboardingStatus().catch((error) => {
    state.onboarding = { pending: true, completed: false };
    state.token = '';
    state.refreshToken = '';
    state.user = null;
    setAuthMode(false);
    setBanner('Onboarding-Status konnte nicht geladen werden. Bitte Ersteinrichtung fortsetzen.', 'warn');
    console.warn('Onboarding status fallback enabled:', error);
  }).then(() => {
    return loadDashboard();
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
  });
  startDashboardPoll();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bootstrapApp, { once: true });
} else {
  bootstrapApp();
}