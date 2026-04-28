import {
  MAX_USERNAME_LEN,
  MIN_PASSWORD_LEN,
  SESSION_IDLE_TIMEOUT_MS,
  USERNAME_PATTERN,
  browserCommon,
  config,
  resetVirtualizationInspector,
  state
} from './state.js';
import { qs } from './dom.js';
import { fetchWithTimeout, resolveApiTarget } from './api.js';

let tokenStore = null;
let refreshTokenStore = null;
let refreshInFlight = null;
let loginInFlight = null;
let authLockCountdownTimer = null;
let sessionLastActivityAt = Date.now();

const uiHooks = {
  setAuthMode() {},
  setBanner() {},
  updateSessionChrome() {},
  renderInventory() {},
  renderVirtualizationOverview() {},
  renderVirtualizationPanel() {},
  renderVirtualizationInspector() {},
  renderProvisioningWorkspace() {},
  renderEndpointsOverview() {},
  renderClusterPanel() {},
  clearSecretVault() {},
  addToActivityLog() {},
  connectLiveUpdates() {},
  disconnectLiveUpdates() {}
};

function readStoredToken() {
  return tokenStore ? tokenStore.read() : '';
}

function writeStoredToken(token) {
  if (tokenStore) {
    tokenStore.write(token);
  }
}

function clearStoredToken() {
  if (tokenStore) {
    tokenStore.clear();
  }
}

function readStoredRefreshToken() {
  return refreshTokenStore ? refreshTokenStore.read() : '';
}

function writeStoredRefreshToken(token) {
  if (refreshTokenStore) {
    refreshTokenStore.write(token);
  }
}

function clearStoredRefreshToken() {
  if (refreshTokenStore) {
    refreshTokenStore.clear();
  }
}

export function configureAuthUi(nextHooks) {
  Object.assign(uiHooks, nextHooks || {});
}

export function setSessionTokens(accessToken, refreshToken) {
  state.token = String(accessToken || '').trim();
  state.refreshToken = String(refreshToken || '').trim();
  if (state.token) {
    writeStoredToken(state.token);
  } else {
    clearStoredToken();
  }
  if (state.refreshToken) {
    writeStoredRefreshToken(state.refreshToken);
  } else {
    clearStoredRefreshToken();
  }
  if (state.token) {
    uiHooks.connectLiveUpdates();
  } else {
    uiHooks.disconnectLiveUpdates();
  }
}

export function clearPersistedTokens() {
  state.token = '';
  state.refreshToken = '';
  clearStoredToken();
  clearStoredRefreshToken();
}

export function initTokenStores(common = browserCommon) {
  if (!common || typeof common.createSessionTokenStore !== 'function') {
    throw new Error('BeagleBrowserCommon must be loaded before auth initialization');
  }
  tokenStore = common.createSessionTokenStore('beagle.webUi.apiToken');
  refreshTokenStore = common.createSessionTokenStore('beagle.webUi.refreshToken');
  state.token = readStoredToken();
  state.refreshToken = readStoredRefreshToken();
  return {
    tokenStore,
    refreshTokenStore
  };
}

export function buildAuthHeaders() {
  const headers = {};
  if (!state.token) {
    return headers;
  }
  headers.Authorization = 'Bearer ' + state.token;
  if (config.sendLegacyApiTokenHeader === true) {
    headers['X-Beagle-Api-Token'] = state.token;
  }
  return headers;
}

export function markSessionActivity() {
  sessionLastActivityAt = Date.now();
}

export function sanitizeIdentifier(value, label, pattern, minLen, maxLen) {
  const normalized = String(value || '').trim();
  if (!normalized) {
    throw new Error(label + ' ist erforderlich.');
  }
  if (normalized.length < minLen || normalized.length > maxLen) {
    throw new Error(label + ' muss zwischen ' + String(minLen) + ' und ' + String(maxLen) + ' Zeichen liegen.');
  }
  if (!pattern.test(normalized)) {
    throw new Error(label + ' enthaelt unzulaessige Zeichen.');
  }
  return normalized;
}

export function sanitizePassword(value, label) {
  const password = String(value || '');
  if (!password) {
    throw new Error(label + ' ist erforderlich.');
  }
  if (password.length < MIN_PASSWORD_LEN) {
    throw new Error(label + ' muss mindestens ' + String(MIN_PASSWORD_LEN) + ' Zeichen lang sein.');
  }
  return password;
}

export function clearSessionState(reason, tone) {
  state.token = '';
  state.refreshToken = '';
  state.user = null;
  clearStoredToken();
  clearStoredRefreshToken();
  if (qs('auth-password')) {
    qs('auth-password').value = '';
  }
  if (qs('api-token')) {
    qs('api-token').value = '';
  }
  state.inventory = [];
  state.endpointReports = [];
  state.virtualizationOverview = null;
  state.virtualizationNodeFilter = '';
  resetVirtualizationInspector();
  state.provisioningCatalog = null;
  state.selectedVmid = null;
  state.selectedVmids = [];
  uiHooks.clearSecretVault();
  uiHooks.renderInventory();
  uiHooks.renderVirtualizationOverview();
  uiHooks.renderVirtualizationPanel();
  uiHooks.renderVirtualizationInspector();
  uiHooks.renderProvisioningWorkspace();
  uiHooks.renderEndpointsOverview();
  uiHooks.renderClusterPanel();
  uiHooks.disconnectLiveUpdates();
  uiHooks.setAuthMode(false);
  uiHooks.setBanner(reason || 'Session gesperrt.', tone || 'warn');
}

export function logoutSession() {
  if (!state.token && !state.refreshToken) {
    return Promise.resolve();
  }
  const headers = Object.assign({ 'Content-Type': 'application/json' }, buildAuthHeaders());
  return fetchWithTimeout(resolveApiTarget('/auth/logout'), {
    method: 'POST',
    credentials: 'same-origin',
    headers,
    body: JSON.stringify({ refresh_token: state.refreshToken || '' })
  }).then(() => null).catch(() => null);
}

export function refreshAccessToken() {
  if (!state.refreshToken) {
    return Promise.reject(new Error('missing refresh token'));
  }
  if (refreshInFlight) {
    return refreshInFlight;
  }
  refreshInFlight = fetchWithTimeout(resolveApiTarget('/auth/refresh'), {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: state.refreshToken })
  }).then((response) => {
    return response.text().then((body) => {
      let payload = {};
      try {
        payload = JSON.parse(body || '{}');
      } catch (error) {
        void error;
      }
      if (!response.ok) {
        throw new Error(payload.error || ('HTTP ' + response.status));
      }
      state.token = String(payload.access_token || '').trim();
      if (!state.token) {
        throw new Error('no access token in refresh response');
      }
      if (payload.refresh_token) {
        state.refreshToken = String(payload.refresh_token).trim();
        writeStoredRefreshToken(state.refreshToken);
      }
      writeStoredToken(state.token);
      state.user = payload.user || state.user;
      uiHooks.connectLiveUpdates();
      uiHooks.updateSessionChrome();
      return state.token;
    });
  }).finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

export function canRefreshAfterAuthError(path) {
  const normalized = String(path || '').trim();
  if (!normalized) {
    return false;
  }
  if (normalized.indexOf('/auth/refresh') === 0) {
    return false;
  }
  if (normalized.indexOf('/auth/login') === 0) {
    return false;
  }
  if (normalized.indexOf('/auth/logout') === 0) {
    return false;
  }
  if (normalized.indexOf('/auth/onboarding/') === 0) {
    return false;
  }
  return true;
}

export function shouldHardLockOnUnauthorized(path) {
  return String(path || '').trim().indexOf('/auth/me') === 0;
}

export function lockSession(reason) {
  clearSessionState(reason || 'Session gesperrt.', 'warn');
}

export function checkSessionTimeout() {
  if (!state.token) {
    return;
  }
  if ((Date.now() - sessionLastActivityAt) > SESSION_IDLE_TIMEOUT_MS) {
    lockSession('Session aus Sicherheitsgruenden wegen Inaktivitaet gesperrt.');
  }
}

export function isAuthLocked() {
  return state.authLockUntil > Date.now();
}

export function updateConnectButton() {
  const btn = qs('connect-button');
  if (!btn) {
    return;
  }
  if (isAuthLocked()) {
    const remaining = Math.max(0, Math.ceil((state.authLockUntil - Date.now()) / 1000));
    btn.disabled = true;
    btn.textContent = 'Gesperrt (' + String(remaining) + 's)';
  } else {
    btn.disabled = false;
    btn.textContent = 'Verbinden';
  }
}

export function startAuthLockCountdown() {
  if (authLockCountdownTimer) {
    return;
  }
  authLockCountdownTimer = window.setInterval(() => {
    updateConnectButton();
    if (!isAuthLocked()) {
      window.clearInterval(authLockCountdownTimer);
      authLockCountdownTimer = null;
      uiHooks.setBanner('Verbindungssperre aufgehoben.', 'info');
    }
  }, 1000);
}

export function recordAuthSuccess() {
  state.authFailCount = 0;
  state.authLockUntil = 0;
  updateConnectButton();
}

export function recordAuthFailure() {
  state.authFailCount += 1;
  if (state.authFailCount >= 5) {
    state.authLockUntil = Date.now() + 60000;
    uiHooks.addToActivityLog('connect', null, 'warn', 'Auth locked: zu viele Fehlversuche');
    startAuthLockCountdown();
  }
  updateConnectButton();
}

export function saveToken() {
  const input = qs('api-token');
  state.token = input ? String(input.value || '').trim() : '';
  state.refreshToken = '';
  state.user = null;
  if (state.token) {
    writeStoredToken(state.token);
    clearStoredRefreshToken();
  } else {
    clearStoredToken();
    clearStoredRefreshToken();
  }
}

export function loginWithCredentials(username, password) {
  const safeUsername = sanitizeIdentifier(username, 'Benutzername', USERNAME_PATTERN, 1, MAX_USERNAME_LEN);
  const safePassword = sanitizePassword(password, 'Passwort');
  if (loginInFlight) {
    return loginInFlight;
  }
  loginInFlight = fetchWithTimeout(resolveApiTarget('/auth/login'), {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: safeUsername,
      password: safePassword
    })
  }).then((response) => {
    return response.text().then((body) => {
      let payload = {};
      try {
        payload = JSON.parse(body || '{}');
      } catch (error) {
        void error;
      }
      if (!response.ok) {
        if (response.status === 429) {
          const retryAfter = Number(payload.retry_after_seconds || response.headers.get('Retry-After') || 0);
          const suffix = Number.isFinite(retryAfter) && retryAfter > 0
            ? ' Bitte in ' + String(Math.ceil(retryAfter)) + 's erneut versuchen.'
            : '';
          throw new Error((payload.error || 'Login temporaer gesperrt.') + suffix);
        }
        throw new Error(payload.error || ('HTTP ' + response.status));
      }
      state.token = String(payload.access_token || '').trim();
      state.refreshToken = String(payload.refresh_token || '').trim();
      state.user = payload.user || null;
      if (!state.token) {
        throw new Error('No access token returned');
      }
      if (!state.refreshToken) {
        throw new Error('No refresh token returned');
      }
      writeStoredToken(state.token);
      writeStoredRefreshToken(state.refreshToken);
      try {
        localStorage.setItem('beagle.auth.username', safeUsername);
      } catch (error) {
        void error;
      }
      if (qs('auth-password')) {
        qs('auth-password').value = '';
      }
    }).catch((error) => {
      if (error && (error.name === 'AbortError' || /aborted/i.test(String(error.message || '')))) {
        throw new Error('Request timeout');
      }
      throw error;
    });
  }).finally(() => {
    loginInFlight = null;
  });
  return loginInFlight;
}

function renderIdentityProviderMethods() {
  const listNode = qs('auth-provider-methods');
  if (!listNode) {
    return;
  }
  const providers = Array.isArray(state.identityProviders) ? state.identityProviders : [];
  if (!providers.length) {
    listNode.innerHTML = '<div class="auth-method-item is-muted">Nur lokaler Login verfuegbar.</div>';
    return;
  }

  const cards = providers.map((provider) => {
    const type = String(provider.type || provider.id || '').trim().toLowerCase();
    const label = String(provider.label || type || 'Provider').trim();
    const description = String(provider.description || '').trim();
    const enabled = provider.enabled !== false;
    const loginUrl = String(provider.login_url || '').trim();
    const metadataUrl = String(provider.metadata_url || '').trim();
    const actionLabel = type === 'local' ? 'Lokal' : (enabled && loginUrl ? 'Weiterleiten' : 'Nicht verfuegbar');
    const extraAction = type === 'saml' && metadataUrl
      ? '<a class="button ghost auth-method-action" href="' + metadataUrl.replace(/"/g, '&quot;') + '" download="beagle-sp-metadata.xml">SP-Metadata</a>'
      : '';
    return [
      '<div class="auth-method-item">',
      '<div class="auth-method-copy">',
      '<strong>' + label + '</strong>',
      '<span>' + (description || 'Login-Methode konfiguriert.') + '</span>',
      '</div>',
      '<div class="auth-method-actions">',
      '<button type="button" class="button ghost auth-method-action" data-provider-id="' + String(provider.id || type || '') + '"',
      enabled ? '' : ' disabled',
      loginUrl ? ' data-provider-login-url="' + loginUrl.replace(/"/g, '&quot;') + '"' : '',
      '>' + actionLabel + '</button>',
      extraAction,
      '</div>',
      '</div>'
    ].join('');
  }).join('');
  listNode.innerHTML = cards;

  listNode.querySelectorAll('.auth-method-action[data-provider-login-url]').forEach((node) => {
    node.addEventListener('click', () => {
      const url = String(node.getAttribute('data-provider-login-url') || '').trim();
      if (url) {
        window.location.href = url;
      }
    });
  });
}

export function loadIdentityProviders() {
  return fetchWithTimeout(resolveApiTarget('/auth/providers'), {
    method: 'GET',
    credentials: 'same-origin'
  }).then((response) => {
    if (!response.ok) {
      throw new Error('HTTP ' + response.status);
    }
    return response.json();
  }).then((payload) => {
    const providers = payload && Array.isArray(payload.providers)
      ? payload.providers
      : [{ id: 'local', type: 'local', label: 'Lokaler Account', description: 'Benutzername + Passwort', enabled: true, login_url: '' }];
    state.identityProviders = providers;
    renderIdentityProviderMethods();
    return providers;
  }).catch((error) => {
    state.identityProviders = [{ id: 'local', type: 'local', label: 'Lokaler Account', description: 'Benutzername + Passwort', enabled: true, login_url: '' }];
    renderIdentityProviderMethods();
    throw error;
  });
}
