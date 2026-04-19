(function () {
  'use strict';

  var browserCommon = window.BeagleBrowserCommon;
  var config = window.BEAGLE_WEB_UI_CONFIG || {};
  var tokenStore = null;
  var refreshTokenStore = null;

  if (!browserCommon) {
    throw new Error('BeagleBrowserCommon must be loaded before website/app.js');
  }
  tokenStore = browserCommon.createSessionTokenStore('beagle.webUi.apiToken');
  refreshTokenStore = browserCommon.createSessionTokenStore('beagle.webUi.refreshToken');

  function readStoredToken() {
    return tokenStore.read();
  }

  function writeStoredToken(token) {
    tokenStore.write(token);
  }

  function clearStoredToken() {
    tokenStore.clear();
  }

  function readStoredRefreshToken() {
    return refreshTokenStore.read();
  }

  function writeStoredRefreshToken(token) {
    refreshTokenStore.write(token);
  }

  function clearStoredRefreshToken() {
    refreshTokenStore.clear();
  }

  var state = {
    token: readStoredToken(),
    refreshToken: readStoredRefreshToken(),
    user: null,
    onboarding: {
      pending: false,
      completed: false
    },
    inventory: [],
    endpointReports: [],
    policies: [],
    authUsers: [],
    authRoles: [],
    selectedAuthUser: '',
    selectedAuthRole: '',
    virtualizationOverview: null,
    virtualizationNodeFilter: '',
    virtualizationInspector: {
      vmid: null,
      loading: false,
      config: null,
      interfaces: [],
      error: ''
    },
    provisioningCatalog: null,
    selectedVmid: null,
    selectedVmids: [],
    selectedPolicyName: '',
    activeDetailPanel: 'summary',
    activePanel: 'overview',
    detailCache: Object.create(null),
    autoRefresh: true,
    authFailCount: 0,
    authLockUntil: 0
  };

  var SESSION_IDLE_TIMEOUT_MS = 20 * 60 * 1000;
  var sessionLastActivityAt = Date.now();
  var ACTIVITY_LOG_MAX = 50;
  var FETCH_TIMEOUT_MS = 20000;
  var activityLog = [];
  var dashboardPollInterval = null;
  var authLockCountdownTimer = null;
  var refreshInFlight = null;
  var dashboardLoadInFlight = null;
  var mutationInFlight = Object.create(null);
  var secretVault = Object.create(null);
  var provisionProgressState = {
    running: false,
    vmid: null,
    stepIndex: -1
  };

  var USAGE_WARN_THRESHOLD = 90;
  var USAGE_INFO_THRESHOLD = 70;
  var MIN_PASSWORD_LEN = 6;
  var MIN_GUEST_PASSWORD_LEN = 8;
  var MAX_USERNAME_LEN = 64;
  var USERNAME_PATTERN = /^[A-Za-z0-9._-]+$/;
  var ROLE_NAME_PATTERN = /^[A-Za-z0-9._:-]+$/;
  var POLICY_NAME_PATTERN = /^[A-Za-z0-9._:-]+$/;
  var DISK_KEY_PATTERN = /^(virtio|ide|sata|scsi|efidisk|tpmstate)\d*$/;
  var NET_KEY_PATTERN = /^net\d+$/;
  var VM_MAIN_KEYS = ['vmid', 'name', 'node', 'status', 'tags', 'cores', 'memory', 'machine', 'bios', 'ostype', 'boot', 'agent', 'balloon', 'onboot', 'cpu'];
  var BULK_ACTION_BUTTON_IDS = [
    'bulk-healthcheck',
    'bulk-support-bundle',
    'bulk-restart-session',
    'bulk-restart-runtime',
    'bulk-update-scan',
    'bulk-update-download',
    'bulk-vm-start',
    'bulk-vm-stop',
    'bulk-vm-reboot'
  ];

  var panelMeta = {
    overview: {
      eyebrow: 'Beagle Console',
      title: 'Dashboard',
      description: 'Live Status, Aktivitaet und Infrastruktur-Telemetrie auf einen Blick.'
    },
    inventory: {
      eyebrow: 'Beagle Endpoints',
      title: 'Endpoint Inventar',
      description: 'Aktive Beagle-VMs verwalten: Filter, Bulk Actions und Detailansicht.'
    },
    virtualization: {
      eyebrow: 'Infrastruktur',
      title: 'Nodes, Storage und Netzwerk',
      description: 'Provider-neutrale Sicht auf Compute, Persistenz und Netz-Bridges.'
    },
    provisioning: {
      eyebrow: 'Provisioning',
      title: 'Neue VM erstellen',
      description: 'Provider-neutrale Provisioning-Contracts mit Verlauf der letzten Requests.'
    },
    policies: {
      eyebrow: 'Konfiguration',
      title: 'Assignment Policies',
      description: 'Zuweisungen, Profile und Prioritaeten fuer die Beagle-Flotte verwalten.'
    },
    iam: {
      eyebrow: 'Identity & Access',
      title: 'Benutzer & Rollen',
      description: 'Konsolen-Anmeldung, RBAC und Sessions zentral steuern.'
    }
  };

  function qs(id) {
    return document.getElementById(id);
  }

  function text(id, value) {
    var node = qs(id);
    if (node) {
      node.textContent = value;
    }
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function apiBase() {
    return String(config.apiBase || '/beagle-api/api/v1').replace(/\/$/, '');
  }

  function normalizedOrigin(urlValue) {
    try {
      return new URL(String(urlValue || ''), window.location.origin).origin;
    } catch (error) {
      void error;
      return '';
    }
  }

  function trustedApiOrigins() {
    var trusted = Object.create(null);
    trusted[window.location.origin] = true;
    if (Array.isArray(config.trustedApiOrigins)) {
      config.trustedApiOrigins.forEach(function (value) {
        var origin = normalizedOrigin(value);
        if (origin) {
          trusted[origin] = true;
        }
      });
    } else if (typeof config.trustedApiOrigins === 'string') {
      config.trustedApiOrigins.split(/[\s,]+/).forEach(function (value) {
        var origin = normalizedOrigin(value);
        if (origin) {
          trusted[origin] = true;
        }
      });
    }
    return trusted;
  }

  function resolveApiTarget(path) {
    var raw = String(path || '');
    if (!raw) {
      throw new Error('empty api path');
    }
    if (raw.indexOf('http') === 0 && config.allowAbsoluteApiTargets !== true) {
      throw new Error('absolute api targets are disabled');
    }
    var target = raw.indexOf('http') === 0 ? raw : apiBase() + raw;
    var parsed;
    try {
      parsed = new URL(target, window.location.origin);
    } catch (error) {
      throw new Error('invalid api target');
    }
    var trusted = trustedApiOrigins();
    if (!trusted[parsed.origin]) {
      throw new Error('blocked untrusted api origin: ' + parsed.origin);
    }
    return parsed.toString();
  }

  function runSingleFlight(key, task) {
    var lockKey = String(key || '').trim();
    if (!lockKey) {
      return Promise.resolve().then(task);
    }
    if (mutationInFlight[lockKey]) {
      return mutationInFlight[lockKey];
    }
    var current = Promise.resolve().then(task).finally(function () {
      if (mutationInFlight[lockKey] === current) {
        delete mutationInFlight[lockKey];
      }
    });
    mutationInFlight[lockKey] = current;
    return current;
  }

  function downloadsBase() {
    return String(config.downloadsBase || '/beagle-downloads').replace(/\/$/, '');
  }

  function webUiUrl() {
    return String(config.webUiUrl || window.location.origin);
  }

  function applyTitle() {
    var title = String(config.title || 'Beagle OS Web UI');
    document.title = title;
    var heading = document.querySelector('.app-header h1');
    if (heading) {
      heading.textContent = title;
    }
  }

  function consumeTokenFromLocation() {
    if (config.allowHashToken !== true) {
      return;
    }
    var hash = String(window.location.hash || '').replace(/^#/, '');
    if (!hash) {
      return;
    }
    var tokenMatch = hash.match(/(?:^|&)beagle_token=([^&]+)/);
    if (!tokenMatch) {
      return;
    }
    var params = new URLSearchParams(hash);
    var token = String(params.get('beagle_token') || '').trim();
    if (!token) {
      return;
    }
    state.token = token;
    state.refreshToken = '';
    writeStoredToken(token);
    clearStoredRefreshToken();
    if (qs('api-token')) {
      qs('api-token').value = token;
    }
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    } else {
      window.location.hash = '';
    }
  }

  function parseAppHash() {
    var raw = String(window.location.hash || '').replace(/^#/, '');
    if (!raw) {
      return {};
    }
    if (raw.indexOf('beagle_token=') !== -1) {
      return {};
    }
    var params = new URLSearchParams(raw);
    return {
      panel: String(params.get('panel') || '').trim(),
      vmid: String(params.get('vmid') || '').trim(),
      detail: String(params.get('detail') || '').trim()
    };
  }

  function syncHash() {
    var params = new URLSearchParams();
    if (state.activePanel && state.activePanel !== 'overview') {
      params.set('panel', state.activePanel);
    }
    if (state.activePanel === 'inventory' && state.selectedVmid) {
      params.set('vmid', String(state.selectedVmid));
    }
    if (state.activePanel === 'inventory' && state.activeDetailPanel && state.activeDetailPanel !== 'summary') {
      params.set('detail', state.activeDetailPanel);
    }
    var next = params.toString();
    var current = String(window.location.hash || '').replace(/^#/, '');
    if (current !== next) {
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, '', window.location.pathname + window.location.search + (next ? '#' + next : ''));
      } else {
        window.location.hash = next;
      }
    }
  }

  function setAuthMode(connected) {
    document.body.classList.toggle('auth-only', !connected);
    if (connected) {
      document.body.classList.remove('auth-modal-open');
      var authModal = qs('auth-modal');
      if (authModal) {
        authModal.hidden = true;
        authModal.setAttribute('aria-hidden', 'true');
      }
      var onboardingModal = qs('onboarding-modal');
      if (onboardingModal) {
        onboardingModal.hidden = true;
        onboardingModal.setAttribute('aria-hidden', 'true');
      }
    } else {
      document.body.classList.add('auth-modal-open');
    }
    updateSessionChrome();
  }

  function setBanner(message, tone) {
    var node = qs('auth-status');
    if (!node) {
      return;
    }
    node.className = 'banner ' + (tone || 'info');
    node.textContent = message;
  }

  /* ── Confirm modal (replaces window.confirm) ─────────── */
  function requestConfirm(opts) {
    var options = opts || {};
    return new Promise(function (resolve) {
      var modal = qs('confirm-modal');
      var titleEl = qs('confirm-title');
      var msgEl = qs('confirm-message');
      var acceptBtn = qs('confirm-accept');
      var cancelBtn = qs('confirm-cancel');
      if (!modal || !titleEl || !msgEl || !acceptBtn || !cancelBtn) {
        // Fallback to native confirm if modal markup is missing.
        resolve(window.confirm(String(options.message || 'Aktion ausfuehren?')));
        return;
      }
      titleEl.textContent = String(options.title || 'Bitte bestaetigen');
      msgEl.textContent = String(options.message || 'Aktion ausfuehren?');
      acceptBtn.textContent = String(options.confirmLabel || 'Bestaetigen');
      cancelBtn.textContent = String(options.cancelLabel || 'Abbrechen');
      acceptBtn.classList.remove('danger', 'primary');
      acceptBtn.classList.add(options.danger ? 'danger' : 'primary');
      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('modal-open');

      function close(result) {
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('modal-open');
        acceptBtn.removeEventListener('click', onAccept);
        cancelBtn.removeEventListener('click', onCancel);
        document.removeEventListener('keydown', onKey);
        modal.removeEventListener('click', onBackdrop);
        resolve(Boolean(result));
      }
      function onAccept() { close(true); }
      function onCancel() { close(false); }
      function onKey(event) {
        if (event.key === 'Escape') { close(false); }
        if (event.key === 'Enter') { close(true); }
      }
      function onBackdrop(event) { if (event.target === modal) { close(false); } }
      acceptBtn.addEventListener('click', onAccept);
      cancelBtn.addEventListener('click', onCancel);
      document.addEventListener('keydown', onKey);
      modal.addEventListener('click', onBackdrop);
      window.setTimeout(function () { acceptBtn.focus(); }, 30);
    });
  }

  function fetchWithTimeout(url, options, timeoutMs) {
    var timeout = Number(timeoutMs || FETCH_TIMEOUT_MS);
    var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timer = null;
    var finalOptions = Object.assign({}, options || {});
    if (controller) {
      finalOptions.signal = controller.signal;
      timer = window.setTimeout(function () {
        controller.abort();
      }, Math.max(1, timeout));
    }
    return fetch(url, finalOptions).finally(function () {
      if (timer) {
        window.clearTimeout(timer);
      }
    });
  }

  function updateSessionChrome() {
    var chip = qs('session-chip');
    if (chip) {
      if (!state.token) {
        chip.textContent = 'Nicht verbunden';
      } else if (state.user && state.user.username) {
        chip.textContent = 'Angemeldet: ' + String(state.user.username);
      } else {
        chip.textContent = 'Verbunden';
      }
    }
  }

  function setActivePanel(panelName) {
    var next = panelMeta[panelName] ? panelName : 'overview';
    state.activePanel = next;
    try {
      localStorage.setItem('beagle.ui.activePanel', next);
    } catch (error) {
      void error;
    }
    document.querySelectorAll('[data-panel]').forEach(function (node) {
      node.classList.toggle('nav-item-active', node.getAttribute('data-panel') === next);
    });
    document.querySelectorAll('[data-panel-section]').forEach(function (node) {
      var sectionPanel = node.getAttribute('data-panel-section');
      node.classList.toggle('panel-section-active', sectionPanel === next);
    });
    var meta = panelMeta[next] || panelMeta.overview;
    text('panel-eyebrow', meta.eyebrow);
    text('panel-title', meta.title);
    text('panel-description', meta.description);
    syncHash();
  }

  function setActiveDetailPanel(panelName) {
    var next = panelName || 'summary';
    state.activeDetailPanel = next;
    try {
      localStorage.setItem('beagle.ui.activeDetailPanel', next);
    } catch (error) {
      void error;
    }
    document.querySelectorAll('[data-detail-panel]').forEach(function(node) {
      node.classList.toggle('detail-tab-active', node.getAttribute('data-detail-panel') === next);
    });
    document.querySelectorAll('.detail-panel').forEach(function(node) {
      node.classList.toggle('detail-panel-active', node.getAttribute('data-detail-panel') === next);
    });
    syncHash();
  }

  function openAuthModal() {
    if (state.onboarding && state.onboarding.pending) {
      openOnboardingModal();
      return;
    }
    var authModal = qs('auth-modal');
    if (authModal) {
      authModal.hidden = false;
      authModal.setAttribute('aria-hidden', 'false');
    }
    document.body.classList.add('auth-modal-open');
    var field = qs('auth-username') || qs('api-token');
    var rememberedUsername = '';
    try {
      rememberedUsername = String(localStorage.getItem('beagle.auth.username') || '').trim();
    } catch (error) {
      void error;
    }
    if (rememberedUsername && qs('auth-username') && !String(qs('auth-username').value || '').trim()) {
      qs('auth-username').value = rememberedUsername;
    }
    if (field) {
      window.setTimeout(function () {
        field.focus();
        field.select();
      }, 30);
    }
  }

  function closeAuthModal() {
    if (!document.body.classList.contains('auth-only')) {
      document.body.classList.remove('auth-modal-open');
    }
    var authModal = qs('auth-modal');
    if (authModal) {
      authModal.hidden = true;
      authModal.setAttribute('aria-hidden', 'true');
    }
  }

  function openOnboardingModal() {
    var modal = qs('onboarding-modal');
    if (!modal) {
      return;
    }
    var authModal = qs('auth-modal');
    if (authModal) {
      authModal.hidden = true;
      authModal.setAttribute('aria-hidden', 'true');
    }
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('auth-modal-open');
    var username = qs('onboarding-username');
    if (username && !String(username.value || '').trim()) {
      username.value = 'admin';
    }
    if (username) {
      window.setTimeout(function () {
        username.focus();
        username.select();
      }, 30);
    }
  }

  function closeOnboardingModal() {
    var modal = qs('onboarding-modal');
    if (!modal) {
      return;
    }
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
    var authModal = qs('auth-modal');
    if (authModal) {
      authModal.hidden = false;
      authModal.setAttribute('aria-hidden', 'false');
    }
  }

  function fetchOnboardingStatus() {
    return fetchWithTimeout(resolveApiTarget('/auth/onboarding/status'), {
      method: 'GET',
      credentials: 'same-origin'
    }).then(function (response) {
      if (!response.ok) {
        throw new Error('HTTP ' + response.status);
      }
      return response.json();
    }).then(function (payload) {
      var onboarding = payload && payload.onboarding ? payload.onboarding : {};
      state.onboarding = {
        pending: Boolean(onboarding.pending),
        completed: Boolean(onboarding.completed)
      };
      if (state.onboarding.pending) {
        state.token = '';
        state.refreshToken = '';
        state.user = null;
        clearStoredToken();
        clearStoredRefreshToken();
        setAuthMode(false);
        setBanner('Ersteinrichtung erforderlich: bitte Administrator anlegen.', 'warn');
        openOnboardingModal();
      } else {
        closeOnboardingModal();
      }
      return state.onboarding;
    });
  }

  function completeOnboarding() {
    var username = String(qs('onboarding-username') ? qs('onboarding-username').value : '').trim();
    var password = String(qs('onboarding-password') ? qs('onboarding-password').value : '');
    var passwordConfirm = String(qs('onboarding-password-confirm') ? qs('onboarding-password-confirm').value : '');
    if (!username || !password) {
      setBanner('Onboarding: Benutzername und Passwort sind erforderlich.', 'warn');
      return Promise.resolve();
    }
    if (password !== passwordConfirm) {
      setBanner('Onboarding: Passwort-Bestaetigung stimmt nicht ueberein.', 'warn');
      return Promise.resolve();
    }
    return fetchWithTimeout(resolveApiTarget('/auth/onboarding/complete'), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: username,
        password: password,
        password_confirm: passwordConfirm
      })
    }).then(function (response) {
      return response.text().then(function (body) {
        var payload = {};
        try {
          payload = JSON.parse(body || '{}');
        } catch (error) {
          void error;
        }
        if (!response.ok) {
          throw new Error(payload.error || ('HTTP ' + response.status));
        }
        state.onboarding = {
          pending: false,
          completed: true
        };
        closeOnboardingModal();
        if (qs('onboarding-password')) {
          qs('onboarding-password').value = '';
        }
        if (qs('onboarding-password-confirm')) {
          qs('onboarding-password-confirm').value = '';
        }
        if (qs('auth-username')) {
          qs('auth-username').value = username;
        }
        setBanner('Ersteinrichtung abgeschlossen. Bitte jetzt anmelden.', 'ok');
      });
    }).catch(function (error) {
      setBanner('Onboarding fehlgeschlagen: ' + error.message, 'warn');
    });
  }

  function accountShell() {
    var toggle = qs('avatar-toggle');
    return toggle ? toggle.closest('.account-shell') : null;
  }

  function closeAccountMenu() {
    var shell = accountShell();
    if (shell) {
      shell.classList.remove('menu-open');
    }
  }

  function isSafeExternalUrl(url) {
    try {
      var parsed = new URL(String(url || ''), window.location.origin);
      if (parsed.protocol === 'https:') {
        return true;
      }
      if (config.allowInsecureExternalUrls === true && parsed.protocol === 'http:' && parsed.origin === window.location.origin) {
        return true;
      }
      return false;
    } catch (error) {
      void error;
      return false;
    }
  }

  function sanitizeIdentifier(value, label, pattern, minLen, maxLen) {
    var normalized = String(value || '').trim();
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

  function sanitizePassword(value, label) {
    var password = String(value || '');
    if (!password) {
      throw new Error(label + ' ist erforderlich.');
    }
    if (password.length < MIN_PASSWORD_LEN) {
      throw new Error(label + ' muss mindestens ' + String(MIN_PASSWORD_LEN) + ' Zeichen lang sein.');
    }
    return password;
  }

  function buildAuthHeaders() {
    var headers = {};
    if (!state.token) {
      return headers;
    }
    headers.Authorization = 'Bearer ' + state.token;
    if (config.sendLegacyApiTokenHeader === true) {
      headers['X-Beagle-Api-Token'] = state.token;
    }
    return headers;
  }

  function markSessionActivity() {
    sessionLastActivityAt = Date.now();
  }

  function clearSessionState(reason, tone) {
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
    state.virtualizationInspector = {
      vmid: null,
      loading: false,
      config: null,
      interfaces: [],
      error: ''
    };
    state.provisioningCatalog = null;
    state.selectedVmid = null;
    state.selectedVmids = [];
    clearSecretVault();
    renderInventory();
    renderVirtualizationOverview();
    renderVirtualizationPanel();
    renderVirtualizationInspector();
    renderProvisioningWorkspace();
    renderEndpointsOverview();
    setAuthMode(false);
    setBanner(reason || 'Session gesperrt.', tone || 'warn');
  }

  function logoutSession() {
    if (!state.token && !state.refreshToken) {
      return Promise.resolve();
    }
    var headers = Object.assign({ 'Content-Type': 'application/json' }, buildAuthHeaders());
    return fetchWithTimeout(resolveApiTarget('/auth/logout'), {
      method: 'POST',
      credentials: 'same-origin',
      headers: headers,
      body: JSON.stringify({ refresh_token: state.refreshToken || '' })
    }).then(function () {
      return null;
    }).catch(function () {
      return null;
    });
  }

  function refreshAccessToken() {
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
    }).then(function (response) {
      return response.text().then(function (body) {
        var payload = {};
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
        updateSessionChrome();
        return state.token;
      });
    }).finally(function () {
      refreshInFlight = null;
    });
    return refreshInFlight;
  }

  function canRefreshAfterAuthError(path) {
    var normalized = String(path || '').trim();
    if (!normalized) {
      return false;
    }
    // Never recurse into refresh/login/logout/onboarding auth flows.
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

  function shouldHardLockOnUnauthorized(path) {
    var normalized = String(path || '').trim();
    return normalized.indexOf('/auth/me') === 0;
  }

  function lockSession(reason) {
    clearSessionState(reason || 'Session gesperrt.', 'warn');
  }

  function checkSessionTimeout() {
    if (!state.token) {
      return;
    }
    if ((Date.now() - sessionLastActivityAt) > SESSION_IDLE_TIMEOUT_MS) {
      lockSession('Session aus Sicherheitsgruenden wegen Inaktivitaet gesperrt.');
    }
  }

  /* ── Dark mode ─────────────────────────────────────────── */
  function loadDarkModePreference() {
    try {
      if (localStorage.getItem('beagle.darkMode') === '1') {
        document.body.classList.add('dark-mode');
      }
    } catch (err) { void err; }
  }

  function toggleDarkMode() {
    var isDark = document.body.classList.toggle('dark-mode');
    try { localStorage.setItem('beagle.darkMode', isDark ? '1' : '0'); } catch (err) { void err; }
    updateDarkModeButton();
  }

  function updateDarkModeButton() {
    var btn = qs('toggle-dark-mode');
    if (!btn) { return; }
    var isDark = document.body.classList.contains('dark-mode');
    btn.setAttribute('aria-label', isDark ? 'Hellmodus aktivieren' : 'Dunkelmodus aktivieren');
    var useEl = btn.querySelector('use');
    if (useEl) {
      useEl.setAttribute('href', isDark ? '#i-sun' : '#i-moon');
      try { useEl.setAttributeNS('http://www.w3.org/1999/xlink', 'href', isDark ? '#i-sun' : '#i-moon'); } catch (err) { void err; }
    } else if (!btn.querySelector('svg')) {
      btn.textContent = isDark ? 'Hell' : 'Dunkel';
    }
  }

  /* ── Auto-refresh ──────────────────────────────────────── */
  function startDashboardPoll() {
    if (dashboardPollInterval) { return; }
    dashboardPollInterval = window.setInterval(function () {
      if (!state.autoRefresh || !state.token || document.hidden) {
        return;
      }
      loadDashboard();
    }, 30000);
  }

  function stopDashboardPoll() {
    if (dashboardPollInterval) {
      window.clearInterval(dashboardPollInterval);
      dashboardPollInterval = null;
    }
  }

  function toggleAutoRefresh() {
    state.autoRefresh = !state.autoRefresh;
    if (state.autoRefresh) {
      startDashboardPoll();
      setBanner('Auto-Aktualisierung wieder aktiv.', 'info');
    } else {
      stopDashboardPoll();
      setBanner('Auto-Aktualisierung pausiert.', 'warn');
    }
    updateAutoRefreshButton();
  }

  function updateAutoRefreshButton() {
    var btn = qs('toggle-auto-refresh');
    if (!btn) { return; }
    if (state.autoRefresh) {
      btn.textContent = 'Auto-Refresh an';
      btn.className = 'button ghost';
    } else {
      btn.textContent = 'Auto-Refresh aus';
      btn.className = 'button paused';
    }
  }

  /* ── Activity log ──────────────────────────────────────── */
  function addToActivityLog(action, vmid, result, message) {
    activityLog.unshift({
      ts: Date.now(),
      action: String(action || 'action'),
      vmid: vmid || null,
      result: String(result || 'ok'),
      message: String(message || '')
    });
    if (activityLog.length > ACTIVITY_LOG_MAX) {
      activityLog.length = ACTIVITY_LOG_MAX;
    }
    renderActivityLog();
  }

  function renderActivityLog() {
    var body = qs('activity-log-body');
    if (!body) { return; }
    if (!activityLog.length) {
      body.innerHTML = '<tr><td colspan="4" class="empty-cell">Noch keine Aktionen protokolliert.</td></tr>';
      return;
    }
    body.innerHTML = activityLog.slice(0, 20).map(function (entry) {
      var tone = entry.result === 'ok' ? 'ok' : entry.result === 'warn' ? 'warn' : 'muted';
      return '<tr>' +
        '<td class="vm-sub">' + escapeHtml(formatDate(new Date(entry.ts))) + '</td>' +
        '<td>' + escapeHtml(entry.action) + '</td>' +
        '<td>' + (entry.vmid ? escapeHtml(String(entry.vmid)) : '–') + '</td>' +
        '<td>' + chip(entry.result, tone) + '</td>' +
        '</tr>';
    }).join('');
  }

  /* ── Fleet health alert ────────────────────────────────── */
  function updateFleetHealthAlert() {
    var alertNode = qs('fleet-health-alert');
    if (!alertNode) { return; }
    var rows = Array.isArray(state.endpointReports) ? state.endpointReports : [];
    var unhealthy = rows.filter(function (ep) {
      var s = String(ep.status || ep.health_status || '').toLowerCase();
      return s === 'stale' || s === 'offline' || s === 'error' || s === 'unknown';
    });
    if (unhealthy.length) {
      alertNode.classList.remove('hidden');
      var names = unhealthy.slice(0, 5).map(function (ep) {
        return ep.hostname || ep.endpoint_id || 'endpoint';
      });
      alertNode.textContent = '\u26a0 ' + String(unhealthy.length) + ' Endpoint(s) mit Problemen: ' +
        names.join(', ') + (unhealthy.length > 5 ? ' \u2026' : '');
    } else {
      alertNode.classList.add('hidden');
    }
  }

  /* ── Auth lockout ──────────────────────────────────────── */
  function isAuthLocked() {
    return state.authLockUntil > Date.now();
  }

  function recordAuthSuccess() {
    state.authFailCount = 0;
    state.authLockUntil = 0;
    updateConnectButton();
  }

  function recordAuthFailure() {
    state.authFailCount++;
    if (state.authFailCount >= 5) {
      state.authLockUntil = Date.now() + 60000;
      addToActivityLog('connect', null, 'warn', 'Auth locked: zu viele Fehlversuche');
      startAuthLockCountdown();
    }
    updateConnectButton();
  }

  function updateConnectButton() {
    var btn = qs('connect-button');
    if (!btn) { return; }
    if (isAuthLocked()) {
      var remaining = Math.max(0, Math.ceil((state.authLockUntil - Date.now()) / 1000));
      btn.disabled = true;
      btn.textContent = 'Gesperrt (' + String(remaining) + 's)';
    } else {
      btn.disabled = false;
      btn.textContent = 'Verbinden';
    }
  }

  function startAuthLockCountdown() {
    if (authLockCountdownTimer) { return; }
    authLockCountdownTimer = window.setInterval(function () {
      updateConnectButton();
      if (!isAuthLocked()) {
        window.clearInterval(authLockCountdownTimer);
        authLockCountdownTimer = null;
        setBanner('Verbindungssperre aufgehoben.', 'info');
      }
    }, 1000);
  }

  /* ── Masked credential field ───────────────────────────── */
  function maskedFieldBlock(label, value) {
    var safeId = 'cred-' + Math.random().toString(36).slice(2, 10);
    var hasValue = Boolean(value);
    secretVault[safeId] = String(value || '');
    return '<div class="kv"><div class="kv-label">' + escapeHtml(label) + '</div>' +
      '<div class="kv-value kv-value-masked">' +
      '<span class="kv-secret" id="' + safeId + '" data-visible="0">' +
      (hasValue ? '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022' : 'n/a') +
      '</span>' +
      (hasValue ? '<button type="button" class="btn-reveal" data-reveal-id="' + safeId + '">Anzeigen</button>' : '') +
      '</div></div>';
  }

  function clearSecretVault() {
    secretVault = Object.create(null);
  }

  function downloadTextFile(filename, content, contentType) {
    var blob = new Blob([String(content || '')], { type: contentType || 'text/plain;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    window.setTimeout(function () {
      URL.revokeObjectURL(url);
      link.remove();
    }, 1000);
  }

  function exportInventoryJson() {
    var payload = filteredInventory().map(function (vm) {
      return profileOf(vm);
    });
    downloadTextFile('beagle-inventory.json', JSON.stringify(payload, null, 2), 'application/json;charset=utf-8');
    setBanner('Inventar als JSON exportiert.', 'ok');
  }

  function exportInventoryCsv() {
    var rows = filteredInventory().map(function (vm) {
      var profile = profileOf(vm);
      return [
        profile.vmid,
        profile.name,
        profile.node,
        profile.status,
        profile.beagle_role,
        profile.stream_host,
        profile.moonlight_port,
        profile.identity_hostname
      ].map(function (cell) {
        var textValue = String(cell == null ? '' : cell);
        return '"' + textValue.replace(/"/g, '""') + '"';
      }).join(',');
    });
    rows.unshift('"vmid","name","node","status","role","stream_host","moonlight_port","hostname"');
    downloadTextFile('beagle-inventory.csv', rows.join('\n') + '\n', 'text/csv;charset=utf-8');
    setBanner('Inventar als CSV exportiert.', 'ok');
  }

  function exportEndpointsJson() {
    downloadTextFile('beagle-endpoints.json', JSON.stringify(state.endpointReports || [], null, 2), 'application/json;charset=utf-8');
    setBanner('Endpoints als JSON exportiert.', 'ok');
  }

  function request(path, options) {
    var target = resolveApiTarget(path);
    var rawOptions = Object.assign({}, options || {});
    var noRefreshRetry = Boolean(rawOptions.__noRefreshRetry);
    var suppressAuthLock = Boolean(rawOptions.__suppressAuthLock);
    delete rawOptions.__noRefreshRetry;
    delete rawOptions.__suppressAuthLock;
    var finalOptions = Object.assign({ method: 'GET', credentials: 'same-origin' }, rawOptions);
    finalOptions.headers = Object.assign({}, finalOptions.headers || {}, buildAuthHeaders());
    return fetchWithTimeout(target, finalOptions).then(function (response) {
      if (!response.ok) {
        return response.text().then(function (body) {
          var detail = body;
          try {
            var parsed = JSON.parse(body);
            detail = parsed.error || parsed.message || body;
          } catch (error) {
            void error;
          }
          if ((response.status === 401 || response.status === 403) && state.token) {
            if (!noRefreshRetry && state.refreshToken && canRefreshAfterAuthError(path)) {
              return refreshAccessToken().then(function () {
                var retriedOptions = Object.assign({}, rawOptions, {
                  __noRefreshRetry: true,
                  __suppressAuthLock: suppressAuthLock
                });
                return request(path, retriedOptions);
              }).catch(function () {
                if (!suppressAuthLock && shouldHardLockOnUnauthorized(path)) {
                  lockSession('Sitzung abgelaufen oder ungueltig. Bitte neu anmelden.');
                }
                throw new Error('HTTP ' + response.status + ': ' + detail);
              });
            }
            if (!suppressAuthLock && shouldHardLockOnUnauthorized(path)) {
              lockSession('Sitzung abgelaufen oder ungueltig. Bitte neu anmelden.');
            }
          }
          throw new Error('HTTP ' + response.status + ': ' + detail);
        });
      }
      return response.json();
    }).catch(function (error) {
      if (error && (error.name === 'AbortError' || /aborted/i.test(String(error.message || '')))) {
        throw new Error('Request timeout');
      }
      throw error;
    });
  }

  function blobRequest(path, filename) {
    var target = resolveApiTarget(path);
    var headers = buildAuthHeaders();
    return fetchWithTimeout(target, {
      method: 'GET',
      credentials: 'same-origin',
      headers: headers
    }).then(function (response) {
      if (!response.ok) {
        if ((response.status === 401 || response.status === 403) && state.token && state.refreshToken && canRefreshAfterAuthError(path)) {
          return refreshAccessToken().then(function () {
            return blobRequest(path, filename);
          }).catch(function () {
            if (shouldHardLockOnUnauthorized(path)) {
              lockSession('Sitzung abgelaufen oder ungueltig. Bitte neu anmelden.');
            }
            throw new Error('HTTP ' + response.status + ' downloading');
          });
        }
        throw new Error('HTTP ' + response.status + ' downloading');
      }
      return response.blob().then(function (blob) {
        var url = URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        window.setTimeout(function () {
          URL.revokeObjectURL(url);
          link.remove();
        }, 1000);
      });
    }).catch(function (error) {
      if (error && (error.name === 'AbortError' || /aborted/i.test(String(error.message || '')))) {
        throw new Error('Download timeout');
      }
      throw error;
    });
  }

  function formatDate(value) {
    if (!value) {
      return 'n/a';
    }
    var date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }
    return date.toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' });
  }

  function formatGiB(value) {
    var numeric = Number(value || 0);
    if (!Number.isFinite(numeric) || numeric <= 0) {
      return 'n/a';
    }
    return (numeric / (1024 * 1024 * 1024)).toFixed(1) + ' GiB';
  }

  function profileOf(vm) {
    return vm && vm.profile ? vm.profile : vm || {};
  }

  function roleOf(vm) {
    var profile = profileOf(vm);
    return String(profile.beagle_role || profile.role || '').trim().toLowerCase();
  }

  function isBeagleVm(vm) {
    var profile = profileOf(vm);
    return Boolean(
      profile.beagle_role ||
      profile.stream_host ||
      profile.installer_target_eligible ||
      (vm && vm.endpoint && vm.endpoint.reported_at)
    );
  }

  function isEligible(vm) {
    var profile = profileOf(vm);
    return Boolean(profile.installer_target_eligible);
  }

  function matchesRoleFilter(vm, value) {
    var role = roleOf(vm);
    if (value === 'all') {
      return true;
    }
    if (value === 'endpoint') {
      return role === 'endpoint' || role === 'thinclient' || role === 'client';
    }
    if (value === 'desktop') {
      return role === 'desktop';
    }
    return role !== 'desktop' && role !== 'endpoint' && role !== 'thinclient' && role !== 'client';
  }

  function filteredInventory() {
    var query = String(qs('search-input') ? qs('search-input').value : '').trim().toLowerCase();
    var roleFilter = String(qs('role-filter') ? qs('role-filter').value : 'all');
    var eligibleOnly = Boolean(qs('eligible-only') && qs('eligible-only').checked);
    return state.inventory.filter(function (vm) {
      var profile = profileOf(vm);
      if (!isBeagleVm(vm)) {
        return false;
      }
      if (!matchesRoleFilter(vm, roleFilter)) {
        return false;
      }
      if (eligibleOnly && !isEligible(vm)) {
        return false;
      }
      if (!query) {
        return true;
      }
      var haystack = [
        profile.name,
        profile.identity_hostname,
        profile.stream_host,
        profile.node,
        profile.vmid,
        profile.beagle_role,
        profile.assignment_source,
        profile.moonlight_app
      ].join(' ').toLowerCase();
      return haystack.indexOf(query) !== -1;
    }).sort(function (left, right) {
      var leftProfile = profileOf(left);
      var rightProfile = profileOf(right);
      var leftRunning = leftProfile.status === 'running' ? 0 : 1;
      var rightRunning = rightProfile.status === 'running' ? 0 : 1;
      if (leftRunning !== rightRunning) {
        return leftRunning - rightRunning;
      }
      return String(leftProfile.name || leftProfile.vmid).localeCompare(String(rightProfile.name || rightProfile.vmid), 'de');
    });
  }

  function chip(label, tone) {
    return '<span class="chip ' + tone + '">' + escapeHtml(label) + '</span>';
  }

  function actionLabel(action) {
    var map = {
      'healthcheck': 'Health Check',
      'support-bundle': 'Support Bundle',
      'restart-session': 'Restart Session',
      'restart-runtime': 'Restart Runtime',
      'os-update-scan': 'Update Scan',
      'os-update-download': 'Update Download',
      'os-update-apply': 'Update Apply',
      'os-update-rollback': 'Update Rollback'
    };
    return map[action] || action;
  }

  function powerActionLabel(action) {
    var map = {
      'start': 'Start',
      'stop': 'Stop',
      'reboot': 'Reboot'
    };
    return map[action] || action;
  }

  function updateStateLabel(updateState) {
    var normalized = String(updateState || '').trim().toLowerCase();
    return normalized || 'unbekannt';
  }

  function parseCommaList(value) {
    return String(value || '')
      .split(',')
      .map(function (item) { return item.trim(); })
      .filter(function (item) { return item.length > 0; });
  }

  function resetInventoryFilters() {
    if (qs('search-input')) {
      qs('search-input').value = '';
    }
    if (qs('role-filter')) {
      qs('role-filter').value = 'all';
    }
    if (qs('eligible-only')) {
      qs('eligible-only').checked = false;
    }
    renderInventory();
  }

  function openInventoryWithNodeFilter(nodeName) {
    if (!nodeName) {
      return;
    }
    setActivePanel('inventory');
    if (qs('search-input')) {
      qs('search-input').value = String(nodeName);
    }
    renderInventory();
    setBanner('Inventar nach Node ' + nodeName + ' gefiltert.', 'info');
  }

  function updateBulkUiState() {
    var selectedCount = selectedVmidsFromInventory().length;
    var enabled = Boolean(state.token) && selectedCount > 0;
    BULK_ACTION_BUTTON_IDS.forEach(function (id) {
      var button = qs(id);
      if (button) {
        button.disabled = !enabled;
      }
    });
    if (qs('bulk-selection')) {
      qs('bulk-selection').textContent = String(selectedCount) + ' ausgewaehlt';
    }
  }

  function runVmPowerAction(vmid, actionName) {
    var numericVmid = Number(vmid);
    if (!numericVmid || !actionName) {
      return Promise.resolve();
    }
    var confirmStop = actionName === 'stop'
      ? requestConfirm({
          title: 'VM ' + numericVmid + ' stoppen?',
          message: 'Die VM wird hart heruntergefahren.',
          confirmLabel: 'Stoppen',
          danger: true
        })
      : Promise.resolve(true);
    return confirmStop.then(function (ok) {
      if (!ok) { return Promise.resolve(); }
    return runSingleFlight('vm-power:' + numericVmid + ':' + actionName, function () {
      setBanner('VM ' + numericVmid + ': ' + powerActionLabel(actionName) + ' wird ausgefuehrt ...', 'info');
      return request('/virtualization/vms/' + numericVmid + '/power', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: actionName })
      }).then(function () {
        addToActivityLog('vm-' + actionName, numericVmid, 'ok', 'VM power action');
        setBanner('VM ' + numericVmid + ': ' + powerActionLabel(actionName) + ' erfolgreich.', 'ok');
        return loadDashboard().then(function () {
          if (state.selectedVmid === numericVmid) {
            return loadDetail(numericVmid);
          }
          return null;
        });
      }).catch(function (error) {
        addToActivityLog('vm-' + actionName, numericVmid, 'warn', error.message);
        setBanner('VM ' + numericVmid + ': ' + powerActionLabel(actionName) + ' fehlgeschlagen: ' + error.message, 'warn');
      });
    });
    });
  }

  function bulkVmPowerAction(actionName) {
    var vmids = selectedVmidsFromInventory();
    if (!vmids.length) {
      setBanner('Keine VM fuer die Bulk-Power-Aktion ausgewaehlt.', 'warn');
      return;
    }
    runSingleFlight('bulk-vm-power:' + actionName, function () {
      setBanner('Bulk VM ' + powerActionLabel(actionName) + ' fuer ' + vmids.length + ' VM(s) wird ausgefuehrt ...', 'info');
      return Promise.all(vmids.map(function (vmid) {
        return request('/virtualization/vms/' + Number(vmid) + '/power', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: actionName })
        }).then(function () {
          return { ok: true, vmid: vmid };
        }).catch(function (error) {
          return { ok: false, vmid: vmid, error: error.message };
        });
      })).then(function (results) {
        var okCount = results.filter(function (item) { return item.ok; }).length;
        var failItems = results.filter(function (item) { return !item.ok; });
        if (failItems.length) {
          setBanner('Bulk VM ' + powerActionLabel(actionName) + ': ' + okCount + ' ok, ' + failItems.length + ' fehlgeschlagen.', 'warn');
        } else {
          setBanner('Bulk VM ' + powerActionLabel(actionName) + ' erfolgreich fuer ' + okCount + ' VM(s).', 'ok');
        }
        return loadDashboard();
      });
    });
  }

  function formatBytes(bytes) {
    if (!bytes) {
      return '0 B';
    }
    var units = ['B', 'KB', 'MB', 'GB', 'TB'];
    var i = 0;
    var value = Number(bytes);
    while (value >= 1024 && i < units.length - 1) {
      value = value / 1024;
      i++;
    }
    return value.toFixed(1) + '\u00a0' + units[i];
  }

  function usageBar(used, total, label) {
    var pct = total > 0 ? Math.min(100, Math.round((Number(used) / Number(total)) * 100)) : 0;
    var tone = pct >= USAGE_WARN_THRESHOLD ? 'warn' : pct >= USAGE_INFO_THRESHOLD ? 'info' : '';
    return '<span class="usage-bar-outer ' + tone + '">' +
      '<progress class="usage-bar-track usage-progress" max="100" value="' + pct + '"></progress>' +
      '<span class="usage-label">' + escapeHtml(label || (pct + '%')) + '</span>' +
      '</span>';
  }

  function renderVirtualizationPanel() {
    var overview = state.virtualizationOverview;
    var nodesGrid = qs('nodes-grid');
    var storageBody = qs('storage-body');
    if (!nodesGrid || !storageBody) {
      return;
    }
    if (!overview || !state.token) {
      nodesGrid.innerHTML = '<div class="empty-card">Keine Daten. Verbinde dich zuerst mit dem API-Token.</div>';
      storageBody.innerHTML = '<tr><td colspan="6" class="empty-cell">Keine Daten verfuegbar.</td></tr>';
      return;
    }
    var nodes = Array.isArray(overview.nodes) ? overview.nodes : [];
    var storage = Array.isArray(overview.storage) ? overview.storage : [];
    if (!nodes.length) {
      nodesGrid.innerHTML = '<div class="empty-card">Keine Nodes gefunden.</div>';
    } else {
      nodesGrid.innerHTML = nodes.map(function (node) {
        var statusTone = node.status === 'online' ? 'ok' : 'warn';
        var cpuUsed = node.maxcpu > 0 ? Math.round((node.cpu || 0) * 100) : 0;
        return '<article class="node-card">' +
          '<div class="node-head">' +
            '<strong class="node-name">' + escapeHtml(node.name || node.id || 'node') + '</strong>' +
            '<span class="chip ' + statusTone + '">' + escapeHtml(node.status || 'unknown') + '</span>' +
          '</div>' +
          '<div class="node-meta"><span class="usage-key">CPU</span>' + usageBar(cpuUsed, 100, cpuUsed + '%') + '</div>' +
          '<div class="node-meta"><span class="usage-key">RAM</span>' + usageBar(node.mem, node.maxmem, formatBytes(node.mem) + ' / ' + formatBytes(node.maxmem)) + '</div>' +
          '<div class="node-footer">' +
            '<span>' + String(node.maxcpu || 0) + '\u00a0vCPU</span>' +
            '<span>' + escapeHtml(node.provider || (overview && overview.provider) || '') + '</span>' +
          '</div>' +
        '</article>';
      }).join('');
    }
    if (!storage.length) {
      storageBody.innerHTML = '<tr><td colspan="6" class="empty-cell">Kein Storage gefunden.</td></tr>';
    } else {
      storageBody.innerHTML = storage.map(function (item) {
        return '<tr>' +
          '<td><strong>' + escapeHtml(item.name || item.id || '') + '</strong></td>' +
          '<td>' + escapeHtml(item.node || '') + '</td>' +
          '<td>' + chip(item.type || 'n/a', 'muted') + '</td>' +
          '<td class="storage-content">' + escapeHtml(item.content || '') + '</td>' +
          '<td class="storage-usage">' + usageBar(item.used, item.total, formatBytes(item.used) + ' / ' + formatBytes(item.total)) + '</td>' +
          '<td>' + formatBytes(item.avail) + '</td>' +
        '</tr>';
      }).join('');
    }
  }

  function renderVmConfigPanel(config, interfaces) {
    var diskKeys = Object.keys(config).filter(function (k) { return DISK_KEY_PATTERN.test(k); }).sort();
    var netKeys = Object.keys(config).filter(function (k) { return NET_KEY_PATTERN.test(k); }).sort();
    var html = '<section class="detail-section"><h3>VM Konfiguration</h3>';
    VM_MAIN_KEYS.forEach(function (k) {
      if (config[k] != null && config[k] !== '') {
        html += fieldBlock(k, String(config[k]));
      }
    });
    html += '</section>';
    if (diskKeys.length) {
      html += '<section class="detail-section"><h3>Disks</h3>';
      diskKeys.forEach(function (k) {
        html += fieldBlock(k, String(config[k] || ''), 'mono');
      });
      html += '</section>';
    }
    if (netKeys.length) {
      html += '<section class="detail-section"><h3>Netzwerk (Config)</h3>';
      netKeys.forEach(function (k) {
        html += fieldBlock(k, String(config[k] || ''), 'mono');
      });
      html += '</section>';
    }
    if (Array.isArray(interfaces) && interfaces.length) {
      html += '<section class="detail-section"><h3>Netzwerk Interfaces (Guest Agent)</h3>';
      interfaces.forEach(function (iface) {
        var addrs = (iface['ip-addresses'] || []).map(function (a) {
          return String(a['ip-address'] || '') + (a['prefix'] ? '/' + a['prefix'] : '');
        }).join(', ');
        html += fieldBlock(String(iface.name || ''), addrs || 'n/a');
      });
      html += '</section>';
    }
    return html;
  }

  function loadVmConfig(vmid) {
    var stack = qs('detail-stack');
    if (!stack) {
      return;
    }
    var configPanel = stack.querySelector('[data-detail-panel="config"]');
    if (!configPanel) {
      return;
    }
    if (configPanel.getAttribute('data-loaded') === String(vmid)) {
      return;
    }
    configPanel.innerHTML = '<div class="banner banner-info">Lade VM-Konfiguration...</div>';
    Promise.all([
      request('/virtualization/vms/' + vmid + '/config'),
      request('/virtualization/vms/' + vmid + '/interfaces').catch(function () { return null; })
    ]).then(function (results) {
      var config = (results[0] && results[0].config) || {};
      var interfaces = (results[1] && results[1].interfaces) || [];
      configPanel.setAttribute('data-loaded', String(vmid));
      configPanel.innerHTML = renderVmConfigPanel(config, interfaces);
    }).catch(function (error) {
      configPanel.innerHTML = '<div class="banner warn">Fehler: ' + escapeHtml(error.message) + '</div>';
    });
  }

  function renderInventory() {
    var rows = filteredInventory();
    var body = qs('inventory-body');
    if (!body) {
      return;
    }
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="7" class="empty-cell">Keine passenden Beagle-VMs gefunden.</td></tr>';
      updateBulkUiState();
      return;
    }
    body.innerHTML = rows.map(function (vm) {
      var profile = profileOf(vm);
      var statusTone = profile.status === 'running' ? 'ok' : 'warn';
      var installerTone = profile.installer_target_eligible ? 'ok' : 'muted';
      var canStart = profile.status !== 'running';
      var canStop = profile.status === 'running';
      return '' +
        '<tr class="vm-row' + (state.selectedVmid === profile.vmid ? ' selected' : '') + '" data-vmid="' + escapeHtml(profile.vmid) + '">' +
        '  <td><input class="row-select" type="checkbox" data-select-vmid="' + escapeHtml(profile.vmid) + '"' + (state.selectedVmids.indexOf(profile.vmid) !== -1 ? ' checked' : '') + '></td>' +
        '  <td><span class="vm-name">' + escapeHtml(profile.name || ('VM ' + profile.vmid)) + '</span><div class="vm-sub">#' + escapeHtml(profile.vmid) + ' · ' + escapeHtml(profile.node || '') + '</div></td>' +
        '  <td>' + chip(roleOf(vm) || 'unassigned', roleOf(vm) === 'desktop' ? 'info' : 'muted') + '</td>' +
        '  <td>' + chip(profile.status || 'unknown', statusTone) + '</td>' +
        '  <td><div>' + escapeHtml(profile.stream_host || 'n/a') + '</div><div class="vm-sub">' + escapeHtml(profile.moonlight_port || '') + '</div></td>' +
        '  <td>' + chip(profile.installer_target_status || (profile.installer_target_eligible ? 'ready' : 'not eligible'), installerTone) + '</td>' +
        '  <td class="power-cell"><div class="power-inline">' +
        '    <button type="button" class="btn btn-ghost btn-small" data-vm-power="start" data-vmid="' + escapeHtml(profile.vmid) + '"' + (canStart ? '' : ' disabled') + '>Start</button>' +
        '    <button type="button" class="btn btn-ghost btn-small" data-vm-power="stop" data-vmid="' + escapeHtml(profile.vmid) + '"' + (canStop ? '' : ' disabled') + '>Stop</button>' +
        '    <button type="button" class="btn btn-primary btn-small" data-vm-power="reboot" data-vmid="' + escapeHtml(profile.vmid) + '">Reboot</button>' +
        '    <button type="button" class="btn btn-ghost btn-small" data-vm-console="novnc" data-vmid="' + escapeHtml(profile.vmid) + '">noVNC</button>' +
        '  </div></td>' +
        '</tr>';
    }).join('');
    if (qs('inventory-select-all')) {
      qs('inventory-select-all').checked = rows.length > 0 && rows.every(function (vm) {
        return state.selectedVmids.indexOf(profileOf(vm).vmid) !== -1;
      });
    }
    updateBulkUiState();
  }

  function renderVirtualizationOverview() {
    var overview = state.virtualizationOverview || {};
    var hosts = Array.isArray(overview.hosts) ? overview.hosts : [];
    var nodes = Array.isArray(overview.nodes) ? overview.nodes : [];
    var storage = Array.isArray(overview.storage) ? overview.storage : [];
    var bridges = Array.isArray(overview.bridges) ? overview.bridges : [];
    var nodeFilter = String(state.virtualizationNodeFilter || '').trim();
    var filteredStorage = nodeFilter ? storage.filter(function (item) {
      return String(item.node || '').trim() === nodeFilter;
    }) : storage;
    var filteredBridges = nodeFilter ? bridges.filter(function (item) {
      return String(item.node || '').trim() === nodeFilter;
    }) : bridges;
    var hostBody = qs('virtualization-hosts-body');
    var nodeBody = qs('virtualization-nodes-body');
    var storageBody = qs('virtualization-storage-body');
    var bridgeBody = qs('virtualization-bridges-body');
    text('virtualization-node-filter', nodeFilter || 'Alle Nodes');
    if (qs('clear-virt-node-filter')) {
      qs('clear-virt-node-filter').disabled = !nodeFilter;
    }

    if (hostBody) {
      hostBody.innerHTML = hosts.length ? hosts.map(function (item) {
        return '' +
          '<tr>' +
          '  <td>' + escapeHtml(item.label || item.name || item.id || 'host') + '</td>' +
          '  <td>' + chip(item.status || 'unknown', (item.status || '').toLowerCase() === 'online' ? 'ok' : 'muted') + '</td>' +
          '  <td>' + escapeHtml(item.provider || overview.provider || 'n/a') + '</td>' +
          '</tr>';
      }).join('') : '<tr><td colspan="3" class="empty-cell">Keine Host-Daten vorhanden.</td></tr>';
    }

    if (nodeBody) {
      nodeBody.innerHTML = nodes.length ? nodes.map(function (item) {
        var cpuPercent = Math.max(0, Number(item.cpu || 0) * 100);
        var memPercent = Number(item.maxmem || 0) > 0 ? (Number(item.mem || 0) / Number(item.maxmem || 0)) * 100 : 0;
        return '' +
          '<tr data-node="' + escapeHtml(item.label || item.name || item.id || '') + '"' + ((nodeFilter && (item.label || item.name || item.id || '') === nodeFilter) ? ' class="node-filter-selected"' : '') + '>' +
          '  <td>' + escapeHtml(item.label || item.name || item.id || 'node') + '</td>' +
          '  <td>' + chip(item.status || 'unknown', (item.status || '').toLowerCase() === 'online' ? 'ok' : 'muted') + '</td>' +
          '  <td>' + escapeHtml(cpuPercent.toFixed(0) + '%') + '</td>' +
          '  <td>' + escapeHtml(memPercent.toFixed(0) + '%') + '</td>' +
          '</tr>';
      }).join('') : '<tr><td colspan="4" class="empty-cell">Keine Node-Daten vorhanden.</td></tr>';
    }

    if (storageBody) {
      storageBody.innerHTML = filteredStorage.length ? filteredStorage.map(function (item) {
        var usedPercent = Number(item.total || 0) > 0 ? (Number(item.used || 0) / Number(item.total || 0)) * 100 : 0;
        return '' +
          '<tr>' +
          '  <td>' + escapeHtml(item.name || item.id || 'storage') + '</td>' +
          '  <td>' + escapeHtml(item.node || '-') + '</td>' +
          '  <td>' + escapeHtml(item.type || '-') + '</td>' +
          '  <td>' + escapeHtml(formatGiB(item.used) + ' / ' + formatGiB(item.total) + ' (' + usedPercent.toFixed(0) + '%)') + '</td>' +
          '</tr>';
      }).join('') : '<tr><td colspan="4" class="empty-cell">Keine Storage-Daten vorhanden.</td></tr>';
    }

    if (bridgeBody) {
      bridgeBody.innerHTML = filteredBridges.length ? filteredBridges.map(function (item) {
        return '' +
          '<tr data-node="' + escapeHtml(item.node || '') + '"' + ((nodeFilter && String(item.node || '') === nodeFilter) ? ' class="node-filter-selected"' : '') + '>' +
          '  <td>' + escapeHtml(item.name || item.id || 'bridge') + '</td>' +
          '  <td>' + escapeHtml(item.node || '-') + '</td>' +
          '  <td>' + escapeHtml(item.cidr || item.address || '-') + '</td>' +
          '  <td>' + escapeHtml(item.bridge_ports || '-') + '</td>' +
          '  <td>' + chip(item.active ? 'active' : 'inactive', item.active ? 'ok' : 'muted') + '</td>' +
          '</tr>';
      }).join('') : '<tr><td colspan="5" class="empty-cell">Keine Bridge-Daten vorhanden.</td></tr>';
    }
  }

  function setVirtualizationNodeFilter(nodeName) {
    var next = String(nodeName || '').trim();
    state.virtualizationNodeFilter = next;
    renderVirtualizationOverview();
    setBanner(next ? ('Node-Filter aktiv: ' + next) : 'Node-Filter entfernt.', 'info');
  }

  function renderVirtualizationInspector() {
    var summary = qs('virt-inspector-summary');
    var configBody = qs('virt-inspector-config-body');
    var ifaceBody = qs('virt-inspector-iface-body');
    if (!summary || !configBody || !ifaceBody) {
      return;
    }
    if (!state.token) {
      summary.innerHTML = '<div class="kv"><div class="kv-label">Status</div><div class="kv-value">Bitte anmelden, um VM-Details zu laden.</div></div>';
      configBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Nicht angemeldet.</td></tr>';
      ifaceBody.innerHTML = '<tr><td colspan="3" class="empty-cell">Nicht angemeldet.</td></tr>';
      return;
    }

    var inspector = state.virtualizationInspector || {};
    if (inspector.loading) {
      summary.innerHTML = '<div class="kv"><div class="kv-label">Status</div><div class="kv-value">Lade VM-Inspector ...</div></div>';
      configBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Lade Konfiguration ...</td></tr>';
      ifaceBody.innerHTML = '<tr><td colspan="3" class="empty-cell">Lade Interfaces ...</td></tr>';
      return;
    }
    if (inspector.error) {
      summary.innerHTML = '<div class="kv"><div class="kv-label">Fehler</div><div class="kv-value">' + escapeHtml(inspector.error) + '</div></div>';
      configBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Keine Config verfuegbar.</td></tr>';
      ifaceBody.innerHTML = '<tr><td colspan="3" class="empty-cell">Keine Interface-Daten verfuegbar.</td></tr>';
      return;
    }
    if (!inspector.vmid || !inspector.config) {
      summary.innerHTML = '<div class="kv"><div class="kv-label">Status</div><div class="kv-value">Noch keine VM geladen.</div></div>';
      configBody.innerHTML = '<tr><td colspan="2" class="empty-cell">Noch keine Config geladen.</td></tr>';
      ifaceBody.innerHTML = '<tr><td colspan="3" class="empty-cell">Noch keine Interfaces geladen.</td></tr>';
      return;
    }

    var config = inspector.config || {};
    var interfaces = Array.isArray(inspector.interfaces) ? inspector.interfaces : [];
    var diskKeys = Object.keys(config).filter(function (k) { return DISK_KEY_PATTERN.test(k); }).sort();
    var netKeys = Object.keys(config).filter(function (k) { return NET_KEY_PATTERN.test(k); }).sort();
    var configKeys = VM_MAIN_KEYS.concat(diskKeys).concat(netKeys).filter(function (key, index, arr) {
      return arr.indexOf(key) === index && config[key] != null && config[key] !== '';
    });

    summary.innerHTML = [
      fieldBlock('VMID', String(inspector.vmid)),
      fieldBlock('Name', String(config.name || 'n/a')),
      fieldBlock('Node', String(config.node || 'n/a')),
      fieldBlock('Status', String(config.status || 'unknown'))
    ].join('');

    configBody.innerHTML = configKeys.length ? configKeys.map(function (key) {
      return '<tr><td>' + escapeHtml(key) + '</td><td class="storage-content">' + escapeHtml(String(config[key])) + '</td></tr>';
    }).join('') : '<tr><td colspan="2" class="empty-cell">Keine Config-Werte verfuegbar.</td></tr>';

    ifaceBody.innerHTML = interfaces.length ? interfaces.map(function (iface) {
      var ipList = Array.isArray(iface['ip-addresses']) ? iface['ip-addresses'] : [];
      var addresses = ipList.map(function (entry) {
        var ip = String(entry['ip-address'] || '').trim();
        var prefix = String(entry.prefix || '').trim();
        return ip ? ip + (prefix ? '/' + prefix : '') : '';
      }).filter(Boolean).join(', ');
      return '<tr>' +
        '<td>' + escapeHtml(String(iface.name || iface.ifname || '-')) + '</td>' +
        '<td>' + escapeHtml(String(iface['hardware-address'] || iface.mac || '-')) + '</td>' +
        '<td>' + escapeHtml(addresses || '-') + '</td>' +
      '</tr>';
    }).join('') : '<tr><td colspan="3" class="empty-cell">Keine Guest-Interface-Daten verfuegbar.</td></tr>';
  }

  function loadVirtualizationInspector(vmid) {
    var numericVmid = Number(vmid || 0);
    if (!Number.isFinite(numericVmid) || numericVmid <= 0) {
      setBanner('VM Inspector: gueltige VMID erforderlich.', 'warn');
      return;
    }
    state.virtualizationInspector = {
      vmid: numericVmid,
      loading: true,
      config: null,
      interfaces: [],
      error: ''
    };
    renderVirtualizationInspector();
    Promise.all([
      request('/virtualization/vms/' + numericVmid + '/config'),
      request('/virtualization/vms/' + numericVmid + '/interfaces').catch(function () { return { interfaces: [] }; })
    ]).then(function (results) {
      state.virtualizationInspector = {
        vmid: numericVmid,
        loading: false,
        config: (results[0] && results[0].config) || {},
        interfaces: (results[1] && results[1].interfaces) || [],
        error: ''
      };
      renderVirtualizationInspector();
      setBanner('VM Inspector geladen fuer VM ' + numericVmid + '.', 'ok');
    }).catch(function (error) {
      state.virtualizationInspector = {
        vmid: numericVmid,
        loading: false,
        config: null,
        interfaces: [],
        error: error.message
      };
      renderVirtualizationInspector();
      setBanner('VM Inspector Fehler: ' + error.message, 'warn');
    });
  }

  function renderEndpointsOverview() {
    var body = qs('endpoints-body');
    if (!body) {
      return;
    }
    var rows = Array.isArray(state.endpointReports) ? state.endpointReports : [];
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="5" class="empty-cell">Keine Endpoint-Daten verfuegbar.</td></tr>';
      return;
    }
    body.innerHTML = rows.map(function (item) {
      var status = String(item.status || item.health_status || 'unknown');
      var tone = status === 'healthy' ? 'ok' : status === 'stale' ? 'warn' : 'muted';
      var vmid = item.vmid || (item.assigned_target && item.assigned_target.vmid) || '-';
      return '' +
        '<tr>' +
        '  <td><strong>' + escapeHtml(item.hostname || item.endpoint_id || 'endpoint') + '</strong></td>' +
        '  <td>' + chip(status, tone) + '</td>' +
        '  <td>' + escapeHtml(vmid) + '</td>' +
        '  <td>' + escapeHtml(item.stream_host || '-') + '</td>' +
        '  <td>' + escapeHtml(formatDate(item.reported_at || item.updated_at || '')) + '</td>' +
        '</tr>';
    }).join('');
  }

  function loadProvisioningCatalog(idPrefix) {
    var catalog = state.provisioningCatalog || {};
    var defaults = catalog.defaults || {};
    var nodes = Array.isArray(catalog.nodes) ? catalog.nodes : [];
    var desktopProfiles = Array.isArray(catalog.desktop_profiles) ? catalog.desktop_profiles : [];
    var bridges = Array.isArray(catalog.bridges) ? catalog.bridges : [];
    var storages = catalog.storages || {};
    var imagesStorages = Array.isArray(storages.images) ? storages.images : [];
    var isoStorages = Array.isArray(storages.iso) ? storages.iso : [];

    function fillSelect(selectId, items, valueFn, labelFn, selectedValue) {
      var select = qs(selectId);
      if (!select) {
        return;
      }
      if (!items.length) {
        select.innerHTML = '<option value="">n/a</option>';
        return;
      }
      select.innerHTML = items.map(function (item) {
        var value = String(valueFn(item));
        var label = String(labelFn(item));
        return '<option value="' + escapeHtml(value) + '"' + (value === String(selectedValue || '') ? ' selected' : '') + '>' + escapeHtml(label) + '</option>';
      }).join('');
    }

    fillSelect(idPrefix + 'node', nodes, function (item) {
      return item.name || '';
    }, function (item) {
      return (item.name || 'node') + ' (' + (item.status || 'unknown') + ')';
    }, defaults.node || '');

    fillSelect(idPrefix + 'desktop', desktopProfiles, function (item) {
      return item.id || '';
    }, function (item) {
      return item.label || item.id || 'desktop';
    }, defaults.desktop || '');

    fillSelect(idPrefix + 'bridge', bridges, function (item) {
      return item;
    }, function (item) {
      return item;
    }, defaults.bridge || '');

    fillSelect(idPrefix + 'disk-storage', imagesStorages, function (item) {
      return item.id || '';
    }, function (item) {
      return (item.id || 'storage') + ' [' + (item.type || 'n/a') + ']';
    }, defaults.disk_storage || '');

    fillSelect(idPrefix + 'iso-storage', isoStorages, function (item) {
      return item.id || '';
    }, function (item) {
      return (item.id || 'storage') + ' [' + (item.type || 'n/a') + ']';
    }, defaults.iso_storage || '');

    if (qs(idPrefix + 'vmid')) {
      qs(idPrefix + 'vmid').value = String(defaults.next_vmid || '');
    }
    if (qs(idPrefix + 'name')) {
      qs(idPrefix + 'name').value = defaults.next_vmid ? 'ubuntu-beagle-' + String(defaults.next_vmid) : '';
    }
    if (qs(idPrefix + 'memory')) {
      qs(idPrefix + 'memory').value = String(defaults.memory || '4096');
    }
    if (qs(idPrefix + 'cores')) {
      qs(idPrefix + 'cores').value = String(defaults.cores || '4');
    }
    if (qs(idPrefix + 'disk')) {
      qs(idPrefix + 'disk').value = String(defaults.disk_gb || '64');
    }
    if (qs(idPrefix + 'guest-user')) {
      qs(idPrefix + 'guest-user').value = String(defaults.guest_user || 'beagle');
    }
    if (qs(idPrefix + 'guest-password')) {
      qs(idPrefix + 'guest-password').value = '';
    }
    if (qs(idPrefix + 'extra-packages')) {
      qs(idPrefix + 'extra-packages').value = '';
    }
  }

  function renderProvisioningWorkspace() {
    var catalog = state.provisioningCatalog || {};
    var recentRequests = Array.isArray(catalog.recent_requests) ? catalog.recent_requests : [];

    loadProvisioningCatalog('prov-');

    if (qs('provision-recent-body')) {
      if (!recentRequests.length) {
        qs('provision-recent-body').innerHTML = '<tr><td colspan="5" class="empty-cell">Noch keine Provisioning-Requests vorhanden.</td></tr>';
      } else {
        qs('provision-recent-body').innerHTML = recentRequests.slice(0, 20).map(function (item) {
          return '' +
            '<tr data-vmid="' + escapeHtml(item.vmid || '') + '">' +
            '  <td>' + escapeHtml(formatDate(item.updated_at || item.created_at || '')) + '</td>' +
            '  <td><strong>' + escapeHtml(item.name || ('VM ' + item.vmid)) + '</strong><div class="vm-sub">#' + escapeHtml(item.vmid || '') + '</div></td>' +
            '  <td>' + escapeHtml(item.node || '-') + '</td>' +
            '  <td>' + chip(item.provision_status || item.status || 'unknown', String(item.provision_status || item.status || '').indexOf('ready') !== -1 ? 'ok' : 'muted') + '</td>' +
            '  <td>' + escapeHtml(item.desktop_id || item.desktop || '-') + '</td>' +
            '</tr>';
        }).join('');
      }
    }
  }

  function provisioningStepDescriptors() {
    return [
      {
        title: 'Konfiguration validieren',
        detail: 'Eingaben und Ziel-Provider werden geprueft.'
      },
      {
        title: 'Provisioning Request senden',
        detail: 'Host API erstellt den Provisioning-Auftrag.'
      },
      {
        title: 'VM wird auf dem Host angelegt',
        detail: 'Compute, Storage und Netzwerk werden vorbereitet.'
      },
      {
        title: 'Inventar wird aktualisiert',
        detail: 'Dashboard und Laufzeitdaten werden synchronisiert.'
      },
      {
        title: 'Detailansicht wird geladen',
        detail: 'Die neue VM wird direkt in der Console vorbereitet.'
      }
    ];
  }

  function openProvisionProgressModal(vmName) {
    var modal = qs('provision-progress-modal');
    var stepsNode = qs('provision-progress-steps');
    var titleNode = qs('provision-progress-title');
    var subtitleNode = qs('provision-progress-subtitle');
    var messageNode = qs('provision-progress-message');
    var openVmButton = qs('provision-progress-open-vm');
    var closeButton = qs('provision-progress-close');
    var descriptors = provisioningStepDescriptors();

    if (!modal || !stepsNode) {
      return;
    }
    provisionProgressState.running = true;
    provisionProgressState.vmid = null;
    provisionProgressState.stepIndex = -1;

    if (titleNode) {
      titleNode.textContent = 'VM wird erstellt: ' + String(vmName || 'Neue Beagle VM');
    }
    if (subtitleNode) {
      subtitleNode.textContent = 'Der Workflow laeuft im Vordergrund mit Live-Schritten.';
    }
    if (messageNode) {
      messageNode.className = 'banner info provision-progress-banner';
      messageNode.textContent = 'Provisioning gestartet ...';
    }
    if (openVmButton) {
      openVmButton.hidden = true;
      openVmButton.disabled = true;
    }
    if (closeButton) {
      closeButton.disabled = true;
      closeButton.textContent = 'Laeuft ...';
    }

    stepsNode.innerHTML = descriptors.map(function (item, index) {
      return '' +
        '<li class="provision-progress-step" data-provision-step="' + String(index) + '">' +
        '  <span class="step-dot"></span>' +
        '  <div><strong>' + escapeHtml(item.title) + '</strong><p>' + escapeHtml(item.detail) + '</p></div>' +
        '  <span class="step-state">pending</span>' +
        '</li>';
    }).join('');

    modal.removeAttribute('hidden');
    document.body.classList.add('modal-open');
  }

  function setProvisionProgressMessage(message, tone) {
    var messageNode = qs('provision-progress-message');
    if (!messageNode) {
      return;
    }
    messageNode.className = 'banner ' + String(tone || 'info') + ' provision-progress-banner';
    messageNode.textContent = String(message || '');
  }

  function setProvisionProgressStep(stepIndex, status, message) {
    var stepsNode = qs('provision-progress-steps');
    var row;
    var stateNode;
    if (!stepsNode) {
      return;
    }
    row = stepsNode.querySelector('[data-provision-step="' + String(stepIndex) + '"]');
    if (!row) {
      return;
    }
    row.classList.remove('is-active', 'is-done', 'is-error');
    if (status === 'active') {
      row.classList.add('is-active');
      provisionProgressState.stepIndex = stepIndex;
    } else if (status === 'done') {
      row.classList.add('is-done');
    } else if (status === 'error') {
      row.classList.add('is-error');
      provisionProgressState.stepIndex = stepIndex;
    }
    stateNode = row.querySelector('.step-state');
    if (stateNode) {
      stateNode.textContent = String(message || status || 'pending');
    }
  }

  function finishProvisionProgress(success, vmid, message) {
    var closeButton = qs('provision-progress-close');
    var openVmButton = qs('provision-progress-open-vm');
    provisionProgressState.running = false;
    provisionProgressState.vmid = Number(vmid || 0) || null;

    if (success) {
      setProvisionProgressMessage(message || 'Provisioning erfolgreich gestartet.', 'ok');
    } else {
      setProvisionProgressMessage(message || 'Provisioning fehlgeschlagen.', 'warn');
    }

    if (closeButton) {
      closeButton.disabled = false;
      closeButton.textContent = success ? 'Schliessen' : 'Zurueck';
    }
    if (openVmButton) {
      if (success && provisionProgressState.vmid) {
        openVmButton.hidden = false;
        openVmButton.disabled = false;
      } else {
        openVmButton.hidden = true;
        openVmButton.disabled = true;
      }
    }
  }

  function closeProvisionProgressModal(force) {
    var modal = qs('provision-progress-modal');
    var anyModalVisible = false;
    var modals;
    var index;
    if (provisionProgressState.running && !force) {
      return;
    }
    if (!modal) {
      return;
    }
    modal.setAttribute('hidden', 'hidden');
    modals = document.querySelectorAll('.modal');
    for (index = 0; index < modals.length; index += 1) {
      if (!modals[index].hasAttribute('hidden')) {
        anyModalVisible = true;
        break;
      }
    }
    if (!anyModalVisible) {
      document.body.classList.remove('modal-open');
    }
  }

  function setProvisionCreateButtonsDisabled(disabled) {
    if (qs('provision-create')) {
      qs('provision-create').disabled = Boolean(disabled);
    }
    if (qs('provision-modal-create')) {
      qs('provision-modal-create').disabled = Boolean(disabled);
    }
  }

  function createProvisionedVmWithPrefix(idPrefix) {
    var payload = {
      node: String(qs(idPrefix + 'node') ? qs(idPrefix + 'node').value : '').trim(),
      vmid: Number(qs(idPrefix + 'vmid') ? qs(idPrefix + 'vmid').value : 0) || undefined,
      name: String(qs(idPrefix + 'name') ? qs(idPrefix + 'name').value : '').trim(),
      desktop: String(qs(idPrefix + 'desktop') ? qs(idPrefix + 'desktop').value : '').trim(),
      memory: Number(qs(idPrefix + 'memory') ? qs(idPrefix + 'memory').value : 0) || undefined,
      cores: Number(qs(idPrefix + 'cores') ? qs(idPrefix + 'cores').value : 0) || undefined,
      disk_gb: Number(qs(idPrefix + 'disk') ? qs(idPrefix + 'disk').value : 0) || undefined,
      bridge: String(qs(idPrefix + 'bridge') ? qs(idPrefix + 'bridge').value : '').trim(),
      disk_storage: String(qs(idPrefix + 'disk-storage') ? qs(idPrefix + 'disk-storage').value : '').trim(),
      iso_storage: String(qs(idPrefix + 'iso-storage') ? qs(idPrefix + 'iso-storage').value : '').trim(),
      guest_user: String(qs(idPrefix + 'guest-user') ? qs(idPrefix + 'guest-user').value : '').trim(),
      guest_password: String(qs(idPrefix + 'guest-password') ? qs(idPrefix + 'guest-password').value : ''),
      extra_packages: parseCommaList(qs(idPrefix + 'extra-packages') ? qs(idPrefix + 'extra-packages').value : ''),
      start: true
    };

    if (!payload.node) {
      setBanner('Provisioning: Node fehlt.', 'warn');
      return;
    }
    if (!payload.guest_password) {
      setBanner('Provisioning: Guest-Passwort ist erforderlich.', 'warn');
      return;
    }
    if (payload.guest_password.length < MIN_GUEST_PASSWORD_LEN) {
      setBanner('Provisioning: Guest-Passwort ist zu kurz (min. ' + String(MIN_GUEST_PASSWORD_LEN) + ').', 'warn');
      return;
    }

    if (idPrefix === 'prov-modal-') {
      closeProvisionModal();
    }
    openProvisionProgressModal(payload.name || ('vm-' + String(payload.vmid || 'auto')));
    setProvisionProgressStep(0, 'active', 'laeuft');
    setProvisionProgressMessage('Konfiguration wird geprueft ...', 'info');

    setProvisionCreateButtonsDisabled(true);
    return runSingleFlight('provision-create', function () {
      setProvisionProgressStep(0, 'done', 'ok');
      setProvisionProgressStep(1, 'active', 'laeuft');
      setProvisionProgressMessage('Provisioning-Request wird an den Host gesendet ...', 'info');
      setBanner('Provisioning: VM wird erstellt ...', 'info');
      return postJson('/provisioning/vms', payload).then(function (response) {
        var vm = response && response.provisioned_vm ? response.provisioned_vm : {};
        var vmid = Number(vm.vmid || payload.vmid || 0);
        setProvisionProgressStep(1, 'done', 'ok');
        setProvisionProgressStep(2, 'active', 'laeuft');
        setProvisionProgressMessage('Host meldet VM-Initialisierung fuer #' + String(vmid || '?') + ' ...', 'info');
        addToActivityLog('provision-create', vmid || null, 'ok', 'VM erstellt: ' + (payload.name || ''));
        setBanner('Provisioning gestartet fuer VM ' + (vmid || '?') + '.', 'ok');
        setProvisionProgressStep(2, 'done', 'ok');
        setProvisionProgressStep(3, 'active', 'laeuft');
        setProvisionProgressMessage('Dashboard und Inventar werden aktualisiert ...', 'info');
        return loadDashboard().then(function () {
          setProvisionProgressStep(3, 'done', 'ok');
          setProvisionProgressStep(4, 'active', 'laeuft');
          if (vmid) {
            return loadDetail(vmid).then(function () {
              setProvisionProgressStep(4, 'done', 'ok');
              finishProvisionProgress(true, vmid, 'Provisioning fuer VM #' + String(vmid) + ' erfolgreich gestartet.');
              return null;
            });
          }
          setProvisionProgressStep(4, 'done', 'uebersprungen');
          finishProvisionProgress(true, null, 'Provisioning gestartet. Es wurde keine VMID zurueckgegeben.');
          return null;
        });
      }).catch(function (error) {
        if (provisionProgressState.stepIndex >= 0) {
          setProvisionProgressStep(provisionProgressState.stepIndex, 'error', 'fehler');
        }
        finishProvisionProgress(false, null, 'Provisioning fehlgeschlagen: ' + error.message);
        addToActivityLog('provision-create', null, 'warn', error.message);
        setBanner('Provisioning fehlgeschlagen: ' + error.message, 'warn');
      });
    }).finally(function () {
      setProvisionCreateButtonsDisabled(false);
    });
  }

  function createProvisionedVm() {
    return createProvisionedVmWithPrefix('prov-');
  }

  function createProvisionedVmFromModal() {
    return createProvisionedVmWithPrefix('prov-modal-');
  }

  function openProvisionModal() {
    var modal = qs('provision-modal');
    if (modal) {
      modal.removeAttribute('hidden');
      document.body.classList.add('modal-open');
      loadProvisioningCatalog('prov-modal-');
      if (qs('prov-modal-name')) {
        qs('prov-modal-name').focus();
      }
    }
  }

  function closeProvisionModal() {
    var modal = qs('provision-modal');
    if (modal) {
      modal.setAttribute('hidden', 'hidden');
      document.body.classList.remove('modal-open');
    }
  }

  function resetProvisioningFormWithPrefix(idPrefix) {
    loadProvisioningCatalog(idPrefix);
  }

  function statCardFromHealth(payload, overview) {
    var counts = (payload && payload.endpoint_status_counts) || {};
    var provider = String((overview && overview.provider) || payload && payload.provider || '').trim();
    var nodeCount = Number(overview && overview.node_count || 0);
    var storageCount = Number(overview && overview.storage_count || 0);
    var bridgeCount = Number(overview && overview.bridge_count || 0);
    var managerMeta = 'v' + String(payload.version || 'unknown');
    if (provider) {
      managerMeta += ' · ' + provider;
    }
    if (nodeCount > 0 || storageCount > 0) {
      managerMeta += ' · ' + String(nodeCount) + ' nodes · ' + String(storageCount) + ' storage · ' + String(bridgeCount) + ' bridges';
    }
    text('stat-manager', 'Online');
    text('stat-manager-meta', managerMeta);
    text('stat-vms', String(payload.vm_count || state.inventory.length || 0));
    text('stat-vms-meta', 'Active Beagle VMs: ' + String(filteredInventory().length));
    text('stat-endpoints', String(payload.endpoint_count || 0));
    text('stat-endpoints-meta', 'healthy ' + String(counts.healthy || 0) + ' · stale ' + String(counts.stale || 0) + ' · offline ' + String(counts.offline || 0));
    text('stat-policies', String(payload.policy_count || 0));
    text('stat-policies-meta', 'queued actions ' + String(payload.pending_action_count || 0));
    text('stat-nodes', String(nodeCount));
    var nodes = Array.isArray(overview && overview.nodes) ? overview.nodes : [];
    var onlineNodes = nodes.filter(function (n) { return n.status === 'online'; }).length;
    text('stat-nodes-meta', nodeCount > 0 ? 'online ' + String(onlineNodes) + ' / ' + String(nodeCount) : 'Keine Daten');
    text('stat-storage', String(storageCount));
    var storageItems = Array.isArray(overview && overview.storage) ? overview.storage : [];
    var activeStorage = storageItems.filter(function (s) { return s.active; }).length;
    text('stat-storage-meta', storageCount > 0 ? 'active ' + String(activeStorage) + ' / ' + String(storageCount) : 'Keine Daten');
  }

  function fieldBlock(label, value, tone) {
    return '<div class="kv ' + (tone || '') + '"><div class="kv-label">' + escapeHtml(label) + '</div><div class="kv-value">' + escapeHtml(value || 'n/a') + '</div></div>';
  }

  function actionButton(action, label, tone) {
    return '<button type="button" class="btn btn-' + (tone || 'ghost') + '" data-action="' + escapeHtml(action) + '">' + escapeHtml(label) + '</button>';
  }

  function renderPolicies() {
    var node = qs('policies-list');
    if (!node) {
      return;
    }
    if (!state.policies.length) {
      node.innerHTML = '<div class="empty-card">No policies found.</div>';
      return;
    }
    node.innerHTML = state.policies.map(function (policy) {
      var selector = policy.selector || {};
      var profile = policy.profile || {};
      return '' +
        '<article class="policy-card' + (state.selectedPolicyName === policy.name ? ' active' : '') + '" data-policy-name="' + escapeHtml(policy.name || '') + '">' +
        '  <div class="policy-head"><strong>' + escapeHtml(policy.name || 'policy') + '</strong>' + chip('prio ' + String(policy.priority || 0), 'muted') + '</div>' +
        '  <div class="policy-grid">' +
        fieldBlock('Selector', JSON.stringify(selector), 'mono') +
        fieldBlock('Profile', JSON.stringify(profile), 'mono') +
        '  </div>' +
        '</article>';
    }).join('');
  }

  function resetPolicyEditor() {
    state.selectedPolicyName = '';
    if (qs('policy-name')) {
      qs('policy-name').value = '';
    }
    if (qs('policy-priority')) {
      qs('policy-priority').value = '100';
    }
    if (qs('policy-enabled')) {
      qs('policy-enabled').checked = true;
    }
    if (qs('policy-selector')) {
      qs('policy-selector').value = '{\n  "vmid": 100\n}';
    }
    if (qs('policy-profile')) {
      qs('policy-profile').value = '{\n  "assigned_target": {\n    "vmid": 100\n  },\n  "beagle_role": "endpoint"\n}';
    }
    renderPolicies();
  }

  function loadPolicyIntoEditor(name) {
    var policy = state.policies.find(function (item) {
      return item.name === name;
    });
    if (!policy) {
      return;
    }
    state.selectedPolicyName = policy.name || '';
    if (qs('policy-name')) {
      qs('policy-name').value = policy.name || '';
    }
    if (qs('policy-priority')) {
      qs('policy-priority').value = String(policy.priority == null ? 100 : policy.priority);
    }
    if (qs('policy-enabled')) {
      qs('policy-enabled').checked = policy.enabled !== false;
    }
    if (qs('policy-selector')) {
      qs('policy-selector').value = JSON.stringify(policy.selector || {}, null, 2);
    }
    if (qs('policy-profile')) {
      qs('policy-profile').value = JSON.stringify(policy.profile || {}, null, 2);
    }
    renderPolicies();
  }

  function renderDetail(detail) {
    var profile = detail.profile || {};
    var credentials = detail.credentials || {};
    var installerPrep = detail.installerPrep || {};
    var actions = detail.actions || {};
    var update = detail.update || {};
    var bundles = detail.supportBundles || [];
    var endpoint = detail.state && detail.state.endpoint ? detail.state.endpoint : {};
    var usb = detail.state && detail.state.usb ? detail.state.usb : {};
    var lastAction = detail.state && detail.state.last_action ? detail.state.last_action : {};
    var node = qs('detail-stack');
    var actionsNode = qs('detail-actions');
    var usbDevices = Array.isArray(usb.devices) ? usb.devices : [];
    var attachedDevices = Array.isArray(usb.attached) ? usb.attached : [];
    var pendingActions = Array.isArray(actions.pending_actions) ? actions.pending_actions : [];
    var updateEndpoint = update.endpoint || {};
    var updatePolicy = update.policy || {};
    var usbDevicesHtml = usbDevices.length ? usbDevices.map(function (device) {
      var busid = String(device.busid || '');
      return '<div class="bundle-row">' +
        '<strong>' + escapeHtml(busid) + '</strong><span>' + escapeHtml(device.description || '') + '</span>' +
        '<div class="btn-row">' +
        '<button class="btn btn-ghost" type="button" data-action="usb-attach" data-usb-busid="' + escapeHtml(busid) + '">Attach</button>' +
        (device.bound ? '<span class="chip ok">exported</span>' : '<span class="chip muted">local</span>') +
        '</div>' +
      '</div>';
    }).join('') : '<div class="empty-card">No exportable USB devices reported.</div>';
    var attachedDevicesHtml = attachedDevices.length ? attachedDevices.map(function (item) {
      var port = String(item.port || '');
      var busid = String(item.busid || '');
      return '<div class="bundle-row">' +
        '<strong>Port ' + escapeHtml(port) + '</strong><span>' + escapeHtml(busid || item.device || '') + '</span>' +
        '<div class="btn-row">' +
        '<button class="btn btn-ghost" type="button" data-action="usb-detach" data-usb-port="' + escapeHtml(port) + '" data-usb-busid="' + escapeHtml(busid) + '">Detach</button>' +
        '</div>' +
      '</div>';
    }).join('') : '<div class="empty-card">No USB devices attached to VM.</div>';
    secretVault = Object.create(null);
    text('detail-title', (profile.name || ('VM ' + profile.vmid)) + ' (#' + profile.vmid + ')');
    if (actionsNode) {
      actionsNode.innerHTML = actionButton('refresh-detail', 'Reload', 'ghost') + actionButton('novnc-ui', 'noVNC Console', 'ghost') + actionButton('sunshine-ui', 'Sunshine Web UI', 'ghost') + actionButton('usb-refresh', 'USB Refresh', 'ghost');
    }
    if (!node) {
      return;
    }
    node.innerHTML = '' +
      '<div class="banner ' + (installerPrep.status === 'ready' ? 'ok' : installerPrep.status === 'failed' || installerPrep.status === 'error' ? 'warn' : 'info') + '">Installer Readiness: ' + escapeHtml(installerPrep.target_status || installerPrep.status || 'unknown') + ' · ' + escapeHtml(installerPrep.message || 'No detail message') + '</div>' +
      '<div class="detail-panel detail-panel-active" data-detail-panel="summary">' +
      '<div class="detail-grid">' +
      '  <section class="detail-section"><h3>Profil</h3>' +
           fieldBlock('Role', profile.beagle_role) +
           fieldBlock('Status', profile.status) +
           fieldBlock('Hostname', profile.identity_hostname) +
           fieldBlock('Assignment', profile.assignment_source || 'n/a') +
           fieldBlock('Policy', profile.applied_policy && profile.applied_policy.name ? profile.applied_policy.name : 'none') +
      '  </section>' +
      '  <section class="detail-section"><h3>Streaming</h3>' +
           fieldBlock('Stream Host', profile.stream_host) +
           fieldBlock('Moonlight Port', profile.moonlight_port) +
           fieldBlock('App', profile.moonlight_app) +
           fieldBlock('Sunshine API', profile.sunshine_api_url, 'mono') +
           fieldBlock('Installer Linux', profile.installer_url, 'mono') +
         fieldBlock('Live USB Script', profile.live_usb_url, 'mono') +
           fieldBlock('Installer Windows', profile.installer_windows_url, 'mono') +
      '  </section>' +
      '  <section class="detail-section"><h3>Endpoint</h3>' +
           fieldBlock('Reported', endpoint.reported_at ? formatDate(endpoint.reported_at) : 'n/a') +
           fieldBlock('Endpoint Host', endpoint.hostname || endpoint.endpoint_id || 'n/a') +
           fieldBlock('Last Action', lastAction.action || 'n/a') +
           fieldBlock('Last Result', lastAction.message || (lastAction.ok == null ? 'n/a' : String(lastAction.ok))) +
           fieldBlock('Pending Actions', String((actions.pending_actions || []).length)) +
           fieldBlock('Support Bundles', String(bundles.length)) +
      '  </section>' +
      '</div>' +
      '<section class="detail-card action-card"><h3>Actions</h3><div class="btn-row">' +
         actionButton('vm-start', 'Start VM', 'ghost') +
         actionButton('vm-stop', 'Stop VM', 'ghost') +
         actionButton('vm-reboot', 'Reboot VM', 'primary') +
        actionButton('novnc-ui', 'noVNC Console', 'ghost') +
        actionButton('vm-delete', 'Delete VM', 'ghost') +
           actionButton('installer-prep', 'Prepare Installer', 'primary') +
           actionButton('download-linux', 'Linux Installer', 'ghost') +
           actionButton('download-live-usb', 'Live USB Script', 'ghost') +
           actionButton('download-windows', 'Windows Installer', 'ghost') +
           actionButton('usb-refresh', 'USB Refresh', 'ghost') +
           actionButton('healthcheck', 'Healthcheck', 'ghost') +
           actionButton('support-bundle', 'Support Bundle', 'ghost') +
           actionButton('restart-session', 'Restart Session', 'ghost') +
           actionButton('restart-runtime', 'Restart Runtime', 'ghost') +
      '</div></section>' +
      '</div>' +
         '<div class="detail-panel" data-detail-panel="updates">' +
         '  <section class="detail-section"><h3>Update Status</h3>' +
           fieldBlock('State', updateStateLabel(updateEndpoint.state || '')) +
           fieldBlock('Current Version', updateEndpoint.current_version || 'n/a') +
           fieldBlock('Latest Version', updateEndpoint.latest_version || update.published_latest_version || 'n/a') +
           fieldBlock('Staged Version', updateEndpoint.staged_version || 'n/a') +
           fieldBlock('Current Slot', updateEndpoint.current_slot || 'n/a') +
           fieldBlock('Next Slot', updateEndpoint.next_slot || 'n/a') +
           fieldBlock('Pending Reboot', String(Boolean(updateEndpoint.pending_reboot))) +
         '  </section>' +
         '  <section class="detail-section"><h3>Update Policy</h3>' +
           fieldBlock('Channel', updatePolicy.channel || 'stable') +
           fieldBlock('Behavior', updatePolicy.behavior || 'prompt') +
           fieldBlock('Enabled', String(updatePolicy.enabled !== false)) +
           fieldBlock('Version Pin', updatePolicy.version_pin || 'none') +
         '  </section>' +
         '  <section class="detail-card action-card"><h3>Update Operations</h3><div class="btn-row">' +
           actionButton('update-scan', 'Scan', 'ghost') +
           actionButton('update-download', 'Download', 'ghost') +
           actionButton('update-apply', 'Apply', 'primary') +
           actionButton('update-rollback', 'Rollback', 'ghost') +
         '  </div></section>' +
         '</div>' +
         '<div class="detail-panel" data-detail-panel="tasks">' +
         '  <section class="detail-section"><h3>Pending Action Queue</h3><div class="bundle-list">' +
           (pendingActions.length ? pendingActions.map(function (item) {
          return '<div class="bundle-row">' +
            '<strong>' + escapeHtml(item.action || 'action') + '</strong>' +
            '<span>' + escapeHtml(formatDate(item.created_at || item.updated_at || '')) + '</span>' +
            '</div>';
           }).join('') : '<div class="empty-card">Keine pending actions.</div>') +
         '</div></section>' +
         '  <section class="detail-section"><h3>Last Action</h3>' +
           fieldBlock('Action', lastAction.action || 'n/a') +
           fieldBlock('Result', lastAction.message || (lastAction.ok == null ? 'n/a' : String(lastAction.ok))) +
           fieldBlock('Timestamp', formatDate(lastAction.created_at || lastAction.finished_at || '')) +
         '  </section>' +
         '</div>' +
      '<div class="detail-panel" data-detail-panel="usb">' +
      '  <section class="detail-section"><h3>USB</h3>' +
           fieldBlock('Tunnel', usb.tunnel_state || 'n/a') +
           fieldBlock('Tunnel Host', usb.tunnel_host || 'n/a') +
           fieldBlock('Tunnel Port', String(usb.tunnel_port || '')) +
           fieldBlock('Exportable Devices', String(usb.device_count || 0)) +
           fieldBlock('Guest Attachments', String(usb.attached_count || 0)) +
      '  </section>' +
      '<section class="detail-section"><h3>USB Devices from Endpoint</h3><div class="bundle-list">' + usbDevicesHtml + '</div></section>' +
      '<section class="detail-section"><h3>USB Devices in VM</h3><div class="bundle-list">' + attachedDevicesHtml + '</div></section>' +
      '</div>' +
      '<div class="detail-panel" data-detail-panel="credentials">' +
      '  <section class="detail-section"><h3>Credentials</h3>' +
           fieldBlock('Thin Client User', credentials.thinclient_username) +
           maskedFieldBlock('Thin Client Password', credentials.thinclient_password) +
           fieldBlock('Sunshine User', credentials.sunshine_username) +
           maskedFieldBlock('Sunshine Password', credentials.sunshine_password) +
           maskedFieldBlock('Sunshine PIN', credentials.sunshine_pin) +
      '  </section>' +
      '</div>' +
      '<div class="detail-panel" data-detail-panel="bundles">' +
      '<section class="detail-section"><h3>Support Bundles</h3><div class="bundle-list">' +
        (bundles.length ? bundles.map(function (bundle) {
          return '<div class="bundle-row"><strong>' + escapeHtml(bundle.stored_filename || bundle.bundle_id || 'bundle') + '</strong><span>' + escapeHtml(formatDate(bundle.generated_at || bundle.stored_at)) + '</span></div>';
        }).join('') : '<div class="empty-card">No bundles available.</div>') +
      '</div></section>' +
      '</div>' +
      '<div class="detail-panel" data-detail-panel="config">' +
      '<div class="banner banner-info">Klicke auf "Config" um die VM-Konfiguration zu laden.</div>' +
      '</div>';
    setActiveDetailPanel(state.activeDetailPanel);
  }

  function loadDetail(vmid) {
    var numericVmid = Number(vmid);
    state.selectedVmid = numericVmid;
    clearSecretVault();
    setActivePanel('inventory');
    renderInventory();
    setBanner('Lade Details fuer VM ' + numericVmid + ' ...', 'info');
    return Promise.all([
      request('/vms/' + numericVmid),
      request('/vms/' + numericVmid + '/state'),
      request('/vms/' + numericVmid + '/credentials'),
      request('/vms/' + numericVmid + '/actions', { __suppressAuthLock: true }).catch(function () { return {}; }),
      request('/vms/' + numericVmid + '/update'),
      request('/vms/' + numericVmid + '/installer-prep'),
      request('/vms/' + numericVmid + '/support-bundles', { __suppressAuthLock: true }).catch(function () { return { support_bundles: [] }; }),
      request('/vms/' + numericVmid + '/usb', { __suppressAuthLock: true }).catch(function () { return { usb: {} }; })
    ]).then(function (results) {
      var detail = {
        profile: results[0].profile || {},
        state: results[1] || {},
        credentials: results[2].credentials || {},
        actions: results[3] || {},
        update: results[4].update || {},
        installerPrep: results[5].installer_prep || {},
        supportBundles: results[6].support_bundles || []
      };
      if (!detail.state.usb && results[7] && results[7].usb) {
        detail.state.usb = results[7].usb;
      }
      state.detailCache[numericVmid] = detail;
      renderDetail(detail);
      setBanner('Details for VM' + numericVmid + ' loaded.', 'ok');
      return detail;
    }).catch(function (error) {
      setBanner('Failed to load VM details:' + error.message, 'warn');
    });
  }

  function saveToken() {
    var input = qs('api-token');
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

  function loginWithCredentials(username, password) {
    var safeUsername = sanitizeIdentifier(username, 'Benutzername', USERNAME_PATTERN, 1, MAX_USERNAME_LEN);
    var safePassword = sanitizePassword(password, 'Passwort');
    return fetchWithTimeout(resolveApiTarget('/auth/login'), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: safeUsername,
        password: safePassword
      })
    }).then(function (response) {
      return response.text().then(function (body) {
        var payload = {};
        try {
          payload = JSON.parse(body || '{}');
        } catch (error) {
          void error;
        }
        if (!response.ok) {
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
      }).catch(function (error) {
        if (error && (error.name === 'AbortError' || /aborted/i.test(String(error.message || '')))) {
          throw new Error('Request timeout');
        }
        throw error;
      });
    });
  }

  function selectedVmidsFromInventory() {
    return state.selectedVmids.slice().sort(function (left, right) {
      return Number(left) - Number(right);
    });
  }

  function bulkAction(action) {
    var vmids = selectedVmidsFromInventory();
    if (!vmids.length) {
      setBanner('Keine VM fuer die Bulk-Aktion ausgewaehlt.', 'warn');
      return;
    }
    runSingleFlight('bulk-action:' + action, function () {
      setBanner('Bulk-Aktion ' + actionLabel(action) + ' fuer ' + vmids.length + ' VM(s) wird eingereiht ...', 'info');
      return postJson('/actions/bulk', {
        vmids: vmids,
        action: action
      }).then(function (payload) {
        var queued = payload && payload.queued_count != null ? payload.queued_count : vmids.length;
        setBanner('Bulk-Aktion ' + actionLabel(action) + ' eingereiht: ' + queued + ' VM(s).', 'ok');
        return loadDashboard();
      }).catch(function (error) {
        setBanner('Bulk-Aktion fehlgeschlagen: ' + error.message, 'warn');
      });
    });
  }

  function parseJsonField(id, label) {
    var raw = String(qs(id) ? qs(id).value : '').trim();
    if (!raw) {
      return {};
    }
    try {
      return JSON.parse(raw);
    } catch (error) {
      throw new Error(label + ' is not valid JSON');
    }
  }

  function savePolicy() {
    var name = String(qs('policy-name') ? qs('policy-name').value : '').trim();
    var payload;
    try {
      name = sanitizeIdentifier(name, 'Policy-Name', POLICY_NAME_PATTERN, 2, 80);
    } catch (error) {
      setBanner(error.message, 'warn');
      return;
    }
    try {
      payload = {
        name: name,
        priority: Number(qs('policy-priority') ? qs('policy-priority').value : '100') || 0,
        enabled: Boolean(qs('policy-enabled') && qs('policy-enabled').checked),
        selector: parseJsonField('policy-selector', 'Selector'),
        profile: parseJsonField('policy-profile', 'Profile')
      };
    } catch (error) {
      setBanner(error.message, 'warn');
      return;
    }

    var updateExisting = Boolean(state.selectedPolicyName && state.selectedPolicyName === name);
    var path = updateExisting ? '/policies/' + encodeURIComponent(name) : '/policies';
    var method = updateExisting ? 'PUT' : 'POST';
    runSingleFlight('policy-save:' + name, function () {
      setBanner('Policy ' + name + ' saving...', 'info');
      return request(path, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).then(function () {
        state.selectedPolicyName = name;
        return loadDashboard();
      }).then(function () {
        loadPolicyIntoEditor(name);
        setBanner('Policy ' + name + ' saved.', 'ok');
      }).catch(function (error) {
        setBanner('Failed to save policy:' + error.message, 'warn');
      });
    });
  }

  function deleteSelectedPolicy() {
    var name = String(qs('policy-name') ? qs('policy-name').value : '').trim() || state.selectedPolicyName;
    if (!name) {
      setBanner('No policy selected.', 'warn');
      return;
    }
    if (!window.confirm('Policy "' + name + '" wirklich loeschen?')) {
      return;
    }
    runSingleFlight('policy-delete:' + name, function () {
      setBanner('Policy ' + name + ' deleting...', 'info');
      return request('/policies/' + encodeURIComponent(name), {
        method: 'DELETE'
      }).then(function () {
        addToActivityLog('policy-delete', null, 'ok', name);
        resetPolicyEditor();
        return loadDashboard();
      }).then(function () {
        setBanner('Policy ' + name + ' deleted.', 'ok');
      }).catch(function (error) {
        addToActivityLog('policy-delete', null, 'warn', error.message);
        setBanner('Failed to delete policy:' + error.message, 'warn');
      });
    });
  }

  function parsePermissions(raw) {
    return String(raw || '')
      .split(/[,\n]/)
      .map(function (entry) { return entry.trim(); })
      .filter(Boolean);
  }

  function renderIamRoleSelect() {
    var roleSelect = qs('iam-user-role');
    if (!roleSelect) {
      return;
    }
    if (!state.authRoles.length) {
      roleSelect.innerHTML = '<option value="">Keine Rollen</option>';
      return;
    }
    roleSelect.innerHTML = state.authRoles.map(function (role) {
      return '<option value="' + escapeHtml(role.name) + '">' + escapeHtml(role.name) + '</option>';
    }).join('');
  }

  function resetIamUserEditor() {
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

  function resetIamRoleEditor() {
    state.selectedAuthRole = '';
    if (qs('iam-role-name')) {
      qs('iam-role-name').value = '';
    }
    if (qs('iam-role-permissions')) {
      qs('iam-role-permissions').value = '';
    }
  }

  function loadIamUserIntoEditor(username) {
    var user = state.authUsers.find(function (entry) {
      return entry.username === username;
    });
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

  function loadIamRoleIntoEditor(roleName) {
    var role = state.authRoles.find(function (entry) {
      return entry.name === roleName;
    });
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

  function renderIamUsers() {
    var body = qs('iam-users-body');
    if (!body) {
      return;
    }
    if (!state.authUsers.length) {
      body.innerHTML = '<tr><td colspan="3" class="empty-cell">Keine Benutzer sichtbar.</td></tr>';
      return;
    }
    body.innerHTML = state.authUsers.map(function (user) {
      var selected = state.selectedAuthUser === user.username ? ' selected' : '';
      return '<tr class="clickable-row' + selected + '" data-iam-user="' + escapeHtml(user.username) + '">' +
        '<td>' + escapeHtml(user.username) + '</td>' +
        '<td>' + escapeHtml(user.role || '-') + '</td>' +
        '<td>' + (user.enabled === false ? 'deaktiviert' : 'aktiv') + '</td>' +
        '</tr>';
    }).join('');
  }

  function renderIamRoles() {
    var body = qs('iam-roles-body');
    if (!body) {
      return;
    }
    if (!state.authRoles.length) {
      body.innerHTML = '<tr><td colspan="2" class="empty-cell">Keine Rollen sichtbar.</td></tr>';
      return;
    }
    body.innerHTML = state.authRoles.map(function (role) {
      var selected = state.selectedAuthRole === role.name ? ' selected' : '';
      var permissions = Array.isArray(role.permissions) ? role.permissions : [];
      var preview = permissions.slice(0, 3).join(', ');
      var suffix = permissions.length > 3 ? ' ...' : '';
      return '<tr class="clickable-row' + selected + '" data-iam-role="' + escapeHtml(role.name) + '">' +
        '<td>' + escapeHtml(role.name) + '</td>' +
        '<td>' + escapeHtml(preview || '-') + escapeHtml(suffix) + '</td>' +
        '</tr>';
    }).join('');
  }

  function renderIam() {
    renderIamRoleSelect();
    renderIamUsers();
    renderIamRoles();
  }

  function refreshIamData() {
    return Promise.all([
      request('/auth/users').catch(function () { return []; }),
      request('/auth/roles').catch(function () { return []; })
    ]).then(function (results) {
      state.authUsers = Array.isArray(results[0]) ? results[0] : [];
      state.authRoles = Array.isArray(results[1]) ? results[1] : [];
      if (state.selectedAuthUser && !state.authUsers.some(function (user) { return user.username === state.selectedAuthUser; })) {
        state.selectedAuthUser = '';
      }
      if (state.selectedAuthRole && !state.authRoles.some(function (role) { return role.name === state.selectedAuthRole; })) {
        state.selectedAuthRole = '';
      }
      renderIam();
    });
  }

  function saveIamUser() {
    var username = String(qs('iam-user-username') ? qs('iam-user-username').value : '').trim();
    var role = String(qs('iam-user-role') ? qs('iam-user-role').value : '').trim();
    var password = String(qs('iam-user-password') ? qs('iam-user-password').value : '');
    var enabled = Boolean(qs('iam-user-enabled') && qs('iam-user-enabled').checked);
    var existing = state.authUsers.find(function (user) { return user.username === username; });
    var payload;

    try {
      username = sanitizeIdentifier(username, 'Username', USERNAME_PATTERN, 1, MAX_USERNAME_LEN);
    } catch (error) {
      setBanner(error.message, 'warn');
      return;
    }
    if (!role) {
      setBanner('Bitte eine Rolle auswaehlen.', 'warn');
      return;
    }

    payload = { role: role, enabled: enabled };
    if (password) {
      payload.password = password;
    }

    if (!existing && !password) {
      setBanner('Neue User benoetigen ein Passwort.', 'warn');
      return;
    }
    if (password && password.length < MIN_PASSWORD_LEN) {
      setBanner('Passwort ist zu kurz (min. ' + String(MIN_PASSWORD_LEN) + ').', 'warn');
      return;
    }

    runSingleFlight('iam-user-save:' + username, function () {
      return request(existing ? ('/auth/users/' + encodeURIComponent(username)) : '/auth/users', {
        method: existing ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(existing ? payload : {
          username: username,
          role: role,
          password: password,
          enabled: enabled
        })
      }).then(function () {
        state.selectedAuthUser = username;
        if (qs('iam-user-password')) {
          qs('iam-user-password').value = '';
        }
        setBanner('User gespeichert: ' + username, 'ok');
        return refreshIamData();
      }).catch(function (error) {
        setBanner('User konnte nicht gespeichert werden: ' + error.message, 'warn');
      });
    });
  }

  function deleteIamUser() {
    var username = String(qs('iam-user-username') ? qs('iam-user-username').value : '').trim() || state.selectedAuthUser;
    if (!username) {
      setBanner('Bitte zuerst einen User auswaehlen.', 'warn');
      return;
    }
    if (!window.confirm('User "' + username + '" wirklich loeschen?')) {
      return;
    }
    runSingleFlight('iam-user-delete:' + username, function () {
      return request('/auth/users/' + encodeURIComponent(username), {
        method: 'DELETE'
      }).then(function () {
        resetIamUserEditor();
        setBanner('User geloescht: ' + username, 'ok');
        return refreshIamData();
      }).catch(function (error) {
        setBanner('User konnte nicht geloescht werden: ' + error.message, 'warn');
      });
    });
  }

  function revokeIamUserSessions() {
    var username = String(qs('iam-user-username') ? qs('iam-user-username').value : '').trim() || state.selectedAuthUser;
    if (!username) {
      setBanner('Bitte zuerst einen User auswaehlen.', 'warn');
      return;
    }
    runSingleFlight('iam-user-revoke:' + username, function () {
      return request('/auth/users/' + encodeURIComponent(username) + '/revoke-sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'admin_revoke_from_web_ui' })
      }).then(function () {
        setBanner('Sessions widerrufen fuer: ' + username, 'ok');
      }).catch(function (error) {
        setBanner('Session-Revoke fehlgeschlagen: ' + error.message, 'warn');
      });
    });
  }

  function saveIamRole() {
    var roleName = String(qs('iam-role-name') ? qs('iam-role-name').value : '').trim();
    var permissions = parsePermissions(qs('iam-role-permissions') ? qs('iam-role-permissions').value : '');
    var existing = state.authRoles.find(function (role) { return role.name === roleName; });
    try {
      roleName = sanitizeIdentifier(roleName, 'Rollenname', ROLE_NAME_PATTERN, 2, 80);
    } catch (error) {
      setBanner(error.message, 'warn');
      return;
    }
    runSingleFlight('iam-role-save:' + roleName, function () {
      return request(existing ? ('/auth/roles/' + encodeURIComponent(roleName)) : '/auth/roles', {
        method: existing ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(existing ? { permissions: permissions } : { name: roleName, permissions: permissions })
      }).then(function () {
        state.selectedAuthRole = roleName;
        setBanner('Rolle gespeichert: ' + roleName, 'ok');
        return refreshIamData();
      }).catch(function (error) {
        setBanner('Rolle konnte nicht gespeichert werden: ' + error.message, 'warn');
      });
    });
  }

  function deleteIamRole() {
    var roleName = String(qs('iam-role-name') ? qs('iam-role-name').value : '').trim() || state.selectedAuthRole;
    if (!roleName) {
      setBanner('Bitte zuerst eine Rolle auswaehlen.', 'warn');
      return;
    }
    if (!window.confirm('Rolle "' + roleName + '" wirklich loeschen?')) {
      return;
    }
    runSingleFlight('iam-role-delete:' + roleName, function () {
      return request('/auth/roles/' + encodeURIComponent(roleName), {
        method: 'DELETE'
      }).then(function () {
        resetIamRoleEditor();
        setBanner('Rolle geloescht: ' + roleName, 'ok');
        return refreshIamData();
      }).catch(function (error) {
        setBanner('Rolle konnte nicht geloescht werden: ' + error.message, 'warn');
      });
    });
  }

  function loadDashboard(options) {
    var opts = options || {};
    if (dashboardLoadInFlight && !opts.force) {
      return dashboardLoadInFlight;
    }
    if (state.onboarding && state.onboarding.pending) {
      setAuthMode(false);
      openOnboardingModal();
      return Promise.resolve();
    }
    if (!state.token) {
      setAuthMode(false);
      setBanner('Nicht angemeldet.', 'warn');
      return Promise.resolve();
    }
    setBanner('Lade Beagle Manager...', 'info');
    dashboardLoadInFlight = Promise.all([
      request('/auth/me'),
      request('/health'),
      request('/vms'),
      request('/endpoints'),
      request('/policies'),
      request('/virtualization/overview'),
      request('/provisioning/catalog', { __suppressAuthLock: true }).catch(function () { return { catalog: null }; }),
      request('/auth/users', { __suppressAuthLock: true }).catch(function () { return []; }),
      request('/auth/roles', { __suppressAuthLock: true }).catch(function () { return []; })
    ]).then(function (results) {
      var me = results[0] || {};
      var health = results[1] || {};
      state.user = me.user || null;
      state.inventory = (results[2] && results[2].vms) || [];
      state.endpointReports = (results[3] && results[3].endpoints) || [];
      state.policies = (results[4] && results[4].policies) || [];
      state.virtualizationOverview = results[5] || null;
      state.provisioningCatalog = results[6] && results[6].catalog ? results[6].catalog : null;
      state.authUsers = Array.isArray(results[7]) ? results[7] : [];
      state.authRoles = Array.isArray(results[8]) ? results[8] : [];
      recordAuthSuccess();
      setAuthMode(true);
      statCardFromHealth(health, state.virtualizationOverview);
      renderInventory();
      renderEndpointsOverview();
      renderVirtualizationOverview();
      renderPolicies();
      renderIam();
      renderVirtualizationPanel();
      renderProvisioningWorkspace();
      updateFleetHealthAlert();
      setBanner('Verbunden. Inventar, Policies und Virtualisierung sind aktuell.', 'ok');
      if (state.selectedVmid) {
        return loadDetail(state.selectedVmid);
      }
      if (filteredInventory().length) {
        return loadDetail(profileOf(filteredInventory()[0]).vmid);
      }
      return null;
    }).catch(function (error) {
      recordAuthFailure();
      text('stat-manager', 'Error');
      text('stat-manager-meta', error.message);
      setBanner('Teilweise Ladefehler: ' + error.message + ' (Session bleibt aktiv).', 'warn');
    }).finally(function () {
      dashboardLoadInFlight = null;
    });
    return dashboardLoadInFlight;
  }

  function postJson(path, payload) {
    return request(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {})
    });
  }

  function executeAction(action, sourceButton) {
    var vmid = state.selectedVmid;
    if (!vmid) {
      return;
    }
    if (action === 'refresh-detail') {
      loadDetail(vmid);
      return;
    }
    if (action === 'download-linux') {
      blobRequest('/vms/' + vmid + '/installer.sh', 'pve-thin-client-usb-installer-vm-' + vmid + '.sh').catch(function (error) {
        setBanner('Linux-Installer Download failed:' + error.message, 'warn');
      });
      return;
    }
    if (action === 'download-windows') {
      blobRequest('/vms/' + vmid + '/installer.ps1', 'pve-thin-client-usb-installer-vm-' + vmid + '.ps1').catch(function (error) {
        setBanner('Windows-Installer Download failed:' + error.message, 'warn');
      });
      return;
    }
    if (action === 'download-live-usb') {
      blobRequest('/vms/' + vmid + '/live-usb.sh', 'pve-thin-client-live-usb-vm-' + vmid + '.sh').catch(function (error) {
        setBanner('Live-USB Download failed:' + error.message, 'warn');
      });
      return;
    }
    if (action === 'usb-refresh') {
      runSingleFlight('vm-action:' + vmid + ':usb-refresh', function () {
        setBanner('Refreshing USB inventory for VM ' + vmid + '...', 'info');
        return postJson('/vms/' + vmid + '/usb/refresh', {}).then(function () {
          return loadDetail(vmid);
        }).catch(function (error) {
          setBanner('USB-Refresh failed:' + error.message, 'warn');
        });
      });
      return;
    }
    if (action === 'usb-attach') {
      runSingleFlight('vm-action:' + vmid + ':usb-attach', function () {
        setBanner('Attaching USB device to VM ' + vmid + '...', 'info');
        return postJson('/vms/' + vmid + '/usb/attach', {
          busid: sourceButton && sourceButton.getAttribute('data-usb-busid') || ''
        }).then(function () {
          return loadDetail(vmid);
        }).catch(function (error) {
          setBanner('USB-Attach failed:' + error.message, 'warn');
        });
      });
      return;
    }
    if (action === 'usb-detach') {
      runSingleFlight('vm-action:' + vmid + ':usb-detach', function () {
        setBanner('Detaching USB device from VM ' + vmid + '...', 'info');
        return postJson('/vms/' + vmid + '/usb/detach', {
          busid: sourceButton && sourceButton.getAttribute('data-usb-busid') || '',
          port: sourceButton && sourceButton.getAttribute('data-usb-port') || ''
        }).then(function () {
          return loadDetail(vmid);
        }).catch(function (error) {
          setBanner('USB-Detach failed:' + error.message, 'warn');
        });
      });
      return;
    }
    if (action === 'installer-prep') {
      runSingleFlight('vm-action:' + vmid + ':installer-prep', function () {
        setBanner('Preparing installer for VM ' + vmid + '...', 'info');
        return postJson('/vms/' + vmid + '/installer-prep', {}).then(function () {
          addToActivityLog('installer-prep', vmid, 'ok', 'Installer vorbereitet');
          return loadDetail(vmid);
        }).catch(function (error) {
          addToActivityLog('installer-prep', vmid, 'warn', error.message);
          setBanner('Installer preparation failed: ' + error.message, 'warn');
        });
      });
      return;
    }
    if (action === 'sunshine-ui') {
      postJson('/vms/' + vmid + '/sunshine-access', {}).then(function (payload) {
        var url = payload && payload.sunshine_access ? payload.sunshine_access.url : '';
        if (!url) {
          throw new Error('No Sunshine URL received');
        }
        if (!isSafeExternalUrl(url)) {
          throw new Error('Unsafe Sunshine URL blocked');
        }
        window.open(url, '_blank', 'noopener');
      }).catch(function (error) {
        setBanner('Sunshine access failed: ' + error.message, 'warn');
      });
      return;
    }
    if (action === 'novnc-ui') {
      request('/vms/' + vmid + '/novnc-access', { __suppressAuthLock: true }).then(function (payload) {
        var access = payload && payload.novnc_access ? payload.novnc_access : {};
        var url = String(access.url || '').trim();
        if (!access.available) {
          throw new Error(String(access.reason || 'noVNC ist fuer diese VM nicht verfuegbar.'));
        }
        if (!url) {
          throw new Error('Keine noVNC URL erhalten.');
        }
        if (!isSafeExternalUrl(url)) {
          throw new Error('Unsichere noVNC URL blockiert.');
        }
        window.open(url, '_blank', 'noopener');
      }).catch(function (error) {
        setBanner('noVNC Zugriff fehlgeschlagen: ' + error.message, 'warn');
      });
      return;
    }
    if (action.indexOf('update-') === 0) {
      var operation = action.replace('update-', '');
      runSingleFlight('vm-action:' + vmid + ':update:' + operation, function () {
        setBanner('Update-Aktion ' + actionLabel('os-update-' + operation) + ' fuer VM ' + vmid + ' wird gestartet ...', 'info');
        return postJson('/vms/' + vmid + '/update/' + operation, {}).then(function () {
          setBanner('Update-Aktion ' + actionLabel('os-update-' + operation) + ' gestartet.', 'ok');
          return loadDetail(vmid);
        }).catch(function (error) {
          setBanner('Update-Aktion fehlgeschlagen: ' + error.message, 'warn');
        });
      });
      return;
    }
    if (action === 'vm-start' || action === 'vm-stop' || action === 'vm-reboot') {
      var powerAction = action === 'vm-start' ? 'start' : action === 'vm-stop' ? 'stop' : 'reboot';
      runVmPowerAction(vmid, powerAction);
      return;
    }
    if (action === 'vm-delete') {
      requestConfirm({
        title: 'VM ' + vmid + ' loeschen?',
        message: 'Diese Aktion kann nicht rueckgaengig gemacht werden. Die VM wird endgueltig entfernt.',
        confirmLabel: 'Endgueltig loeschen',
        danger: true
      }).then(function (ok) {
        if (!ok) { return; }
        runSingleFlight('vm-action:' + vmid + ':delete', function () {
        setBanner('Loesche VM ' + vmid + ' ...', 'info');
        return request('/provisioning/vms/' + vmid, {
          method: 'DELETE'
        }).then(function () {
          addToActivityLog('vm-delete', vmid, 'ok', 'VM geloescht');
          state.selectedVmids = state.selectedVmids.filter(function (item) {
            return Number(item) !== Number(vmid);
          });
          delete state.detailCache[vmid];
          state.selectedVmid = null;
          return loadDashboard({ force: true });
        }).then(function () {
          setBanner('VM ' + vmid + ' geloescht.', 'ok');
        }).catch(function (error) {
          addToActivityLog('vm-delete', vmid, 'warn', error.message);
          setBanner('VM konnte nicht geloescht werden: ' + error.message, 'warn');
        });
        });
      });
      return;
    }
    runSingleFlight('vm-action:' + vmid + ':generic:' + action, function () {
      setBanner('Queuing action ' + action + ' for VM ' + vmid + '...', 'info');
      return postJson('/vms/' + vmid + '/actions', { action: action }).then(function () {
        addToActivityLog(action, vmid, 'ok', 'Action queued');
        setBanner('Action ' + action + ' queued for VM ' + vmid + '.', 'ok');
        return loadDetail(vmid);
      }).catch(function (error) {
        addToActivityLog(action, vmid, 'warn', error.message);
        setBanner('Action failed: ' + error.message, 'warn');
      });
    });
  }

  function openProvisioningWorkspace() {
    openProvisionModal();
  }

  function bindEvents() {
    if (qs('toggle-dark-mode')) {
      qs('toggle-dark-mode').addEventListener('click', toggleDarkMode);
    }
    if (qs('toggle-auto-refresh')) {
      qs('toggle-auto-refresh').addEventListener('click', toggleAutoRefresh);
    }
    if (qs('clear-activity-log')) {
      qs('clear-activity-log').addEventListener('click', function () {
        activityLog.length = 0;
        renderActivityLog();
        setBanner('Aktivitaetslog geleert.', 'info');
      });
    }
    var tokenField = qs('api-token');
    if (tokenField) {
      tokenField.value = state.token;
      tokenField.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          saveToken();
          loadDashboard();
        }
      });
    }
    var usernameField = qs('auth-username');
    var passwordField = qs('auth-password');
    var onboardingPasswordField = qs('onboarding-password');
    var onboardingPasswordConfirmField = qs('onboarding-password-confirm');
    if (passwordField) {
      passwordField.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          var username = String(usernameField ? usernameField.value : '').trim();
          var password = String(passwordField.value || '');
          if (!username || !password) {
            setBanner('Benutzername und Passwort erforderlich.', 'warn');
            return;
          }
          loginWithCredentials(username, password)
            .then(function () { return loadDashboard(); })
            .catch(function (error) { setBanner('Login fehlgeschlagen: ' + error.message, 'warn'); });
        }
      });
    }
    qs('web-ui-url').value = webUiUrl();
    qs('api-base').value = apiBase();
    qs('connect-button').addEventListener('click', function () {
      markSessionActivity();
      if (state.onboarding && state.onboarding.pending) {
        openOnboardingModal();
        return;
      }
      var username = String(usernameField ? usernameField.value : '').trim();
      var password = String(passwordField ? passwordField.value : '');
      if (username || password) {
        if (!username || !password) {
          setBanner('Benutzername und Passwort erforderlich.', 'warn');
          return;
        }
        loginWithCredentials(username, password)
          .then(function () { return loadDashboard(); })
          .catch(function (error) { setBanner('Login fehlgeschlagen: ' + error.message, 'warn'); });
        return;
      }
      saveToken();
      loadDashboard();
    });
    if (qs('open-connect-modal')) {
      qs('open-connect-modal').addEventListener('click', openAuthModal);
    }
    if (qs('open-connect-menu')) {
      qs('open-connect-menu').addEventListener('click', function () {
        closeAccountMenu();
        openAuthModal();
      });
    }
    if (qs('close-auth-modal')) {
      qs('close-auth-modal').addEventListener('click', closeAuthModal);
    }
    if (qs('onboarding-complete')) {
      qs('onboarding-complete').addEventListener('click', function () {
        Promise.resolve().then(function () {
          try {
            var onboardingUser = sanitizeIdentifier(
              String(qs('onboarding-username') ? qs('onboarding-username').value : ''),
              'Onboarding-Benutzername',
              USERNAME_PATTERN,
              1,
              MAX_USERNAME_LEN
            );
            var onboardingPw = sanitizePassword(String(qs('onboarding-password') ? qs('onboarding-password').value : ''), 'Onboarding-Passwort');
            if (qs('onboarding-username')) {
              qs('onboarding-username').value = onboardingUser;
            }
            if (qs('onboarding-password')) {
              qs('onboarding-password').value = onboardingPw;
            }
          } catch (error) {
            setBanner(error.message, 'warn');
            throw error;
          }
        }).then(function () {
          return completeOnboarding();
        }).then(function () {
          if (state.onboarding && !state.onboarding.pending) {
            openAuthModal();
          }
        }).catch(function () {
          return null;
        });
      });
    }
    if (onboardingPasswordField) {
      onboardingPasswordField.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          if (qs('onboarding-complete')) {
            qs('onboarding-complete').click();
          }
        }
      });
    }
    if (onboardingPasswordConfirmField) {
      onboardingPasswordConfirmField.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          if (qs('onboarding-complete')) {
            qs('onboarding-complete').click();
          }
        }
      });
    }
    if (qs('avatar-toggle')) {
      qs('avatar-toggle').addEventListener('click', function () {
        var shell = accountShell();
        if (shell) {
          shell.classList.toggle('menu-open');
        }
      });
    }
    document.addEventListener('click', function (event) {
      var shell = accountShell();
      if (shell && !shell.contains(event.target)) {
        shell.classList.remove('menu-open');
      }
    });
    if (qs('sidebar-nav')) {
      qs('sidebar-nav').addEventListener('click', function (event) {
        var trigger = event.target.closest('[data-panel]');
        var panelName;
        if (!trigger) {
          return;
        }
        panelName = String(trigger.getAttribute('data-panel') || '').trim();
        markSessionActivity();
        if (panelName === 'provisioning') {
          openProvisioningWorkspace();
          return;
        }
        setActivePanel(panelName);
      });
    }
    document.addEventListener('keydown', function (event) {
      if (event.key !== '/' || event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }
      var target = event.target;
      var tag = target && target.tagName ? String(target.tagName).toLowerCase() : '';
      if (tag === 'input' || tag === 'textarea' || (target && target.isContentEditable)) {
        return;
      }
      if (qs('search-input')) {
        event.preventDefault();
        qs('search-input').focus();
      }
    });
    qs('clear-token').addEventListener('click', function () {
      logoutSession().finally(function () {
        clearSessionState('Anmeldedaten geloescht.', 'info');
      });
      if (usernameField) {
        usernameField.value = '';
      }
      if (passwordField) {
        passwordField.value = '';
      }
      if (tokenField) {
        tokenField.value = '';
      }
      closeAccountMenu();
    });
    if (qs('clear-token-menu')) {
      qs('clear-token-menu').addEventListener('click', function () {
        if (qs('clear-token')) {
          qs('clear-token').click();
        }
      });
    }
    qs('refresh-all').addEventListener('click', function () {
      markSessionActivity();
      loadDashboard();
    });
    if (qs('open-provision-create')) {
      qs('open-provision-create').addEventListener('click', function () {
        markSessionActivity();
        openProvisioningWorkspace();
      });
    }
    if (qs('refresh-virt')) {
      qs('refresh-virt').addEventListener('click', function () {
        markSessionActivity();
        loadDashboard();
      });
    }
    if (qs('refresh-endpoints')) {
      qs('refresh-endpoints').addEventListener('click', function () {
        markSessionActivity();
        loadDashboard();
      });
    }
    if (qs('export-inventory-json')) {
      qs('export-inventory-json').addEventListener('click', exportInventoryJson);
    }
    if (qs('export-inventory-csv')) {
      qs('export-inventory-csv').addEventListener('click', exportInventoryCsv);
    }
    if (qs('export-endpoints-json')) {
      qs('export-endpoints-json').addEventListener('click', exportEndpointsJson);
    }
    qs('search-input').addEventListener('input', renderInventory);
    qs('role-filter').addEventListener('change', renderInventory);
    qs('eligible-only').addEventListener('change', renderInventory);
    if (qs('clear-filters')) {
      qs('clear-filters').addEventListener('click', function () {
        resetInventoryFilters();
        setBanner('Filter zurueckgesetzt.', 'info');
      });
    }
    qs('inventory-select-all').addEventListener('change', function (event) {
      var vmids = filteredInventory().map(function (vm) {
        return profileOf(vm).vmid;
      });
      if (event.target.checked) {
        state.selectedVmids = Array.from(new Set(state.selectedVmids.concat(vmids)));
      } else {
        state.selectedVmids = state.selectedVmids.filter(function (vmid) {
          return vmids.indexOf(vmid) === -1;
        });
      }
      renderInventory();
    });
    qs('bulk-healthcheck').addEventListener('click', function () {
      bulkAction('healthcheck');
    });
    qs('bulk-support-bundle').addEventListener('click', function () {
      bulkAction('support-bundle');
    });
    qs('bulk-restart-session').addEventListener('click', function () {
      bulkAction('restart-session');
    });
    qs('bulk-restart-runtime').addEventListener('click', function () {
      bulkAction('restart-runtime');
    });
    if (qs('bulk-update-scan')) {
      qs('bulk-update-scan').addEventListener('click', function () {
        bulkAction('os-update-scan');
      });
    }
    if (qs('bulk-update-download')) {
      qs('bulk-update-download').addEventListener('click', function () {
        bulkAction('os-update-download');
      });
    }
    if (qs('bulk-vm-start')) {
      qs('bulk-vm-start').addEventListener('click', function () {
        bulkVmPowerAction('start');
      });
    }
    if (qs('bulk-vm-stop')) {
      qs('bulk-vm-stop').addEventListener('click', function () {
        bulkVmPowerAction('stop');
      });
    }
    if (qs('bulk-vm-reboot')) {
      qs('bulk-vm-reboot').addEventListener('click', function () {
        bulkVmPowerAction('reboot');
      });
    }
    qs('inventory-body').addEventListener('click', function (event) {
      var powerButton = event.target.closest('button[data-vm-power]');
      if (powerButton) {
        var actionName = powerButton.getAttribute('data-vm-power');
        var actionVmid = Number(powerButton.getAttribute('data-vmid') || '0');
        runVmPowerAction(actionVmid, actionName);
        return;
      }
      var consoleButton = event.target.closest('button[data-vm-console]');
      if (consoleButton) {
        var consoleName = String(consoleButton.getAttribute('data-vm-console') || '').trim().toLowerCase();
        var consoleVmid = Number(consoleButton.getAttribute('data-vmid') || '0');
        if (consoleName === 'novnc' && consoleVmid > 0) {
          var previousVmid = state.selectedVmid;
          state.selectedVmid = consoleVmid;
          executeAction('novnc-ui', consoleButton);
          state.selectedVmid = previousVmid;
        }
        return;
      }
      var select = event.target.closest('input[data-select-vmid]');
      if (select) {
        var selectedVmid = Number(select.getAttribute('data-select-vmid'));
        if (select.checked) {
          if (state.selectedVmids.indexOf(selectedVmid) === -1) {
            state.selectedVmids.push(selectedVmid);
          }
        } else {
          state.selectedVmids = state.selectedVmids.filter(function (vmid) {
            return vmid !== selectedVmid;
          });
        }
        renderInventory();
        return;
      }
      var row = event.target.closest('tr[data-vmid]');
      if (!row) {
        return;
      }
      loadDetail(row.getAttribute('data-vmid'));
    });
    if (qs('detail-tabbar')) {
      qs('detail-tabbar').addEventListener('click', function(event) {
        var trigger = event.target.closest('[data-detail-panel]');
        if (!trigger) {
          return;
        }
        var panelName = trigger.getAttribute('data-detail-panel');
        setActiveDetailPanel(panelName);
        if (panelName === 'config' && state.selectedVmid) {
          loadVmConfig(state.selectedVmid);
        }
      });
    }
    if (qs('virtualization-overview-section')) {
      qs('virtualization-overview-section').addEventListener('click', function (event) {
        var row = event.target.closest('tr[data-node]');
        if (!row) {
          return;
        }
        var nodeName = row.getAttribute('data-node');
        if (nodeName) {
          openInventoryWithNodeFilter(nodeName);
        }
      });
    }
    qs('detail-stack').addEventListener('click', function (event) {
      var revealBtn = event.target.closest('button[data-reveal-id]');
      if (revealBtn) {
        var targetId = revealBtn.getAttribute('data-reveal-id');
        var secretSpan = document.getElementById(targetId);
        if (secretSpan) {
          var visible = secretSpan.getAttribute('data-visible') === '1';
          if (visible) {
            secretSpan.textContent = '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022';
            secretSpan.setAttribute('data-visible', '0');
            revealBtn.textContent = 'Anzeigen';
          } else {
            secretSpan.textContent = String(secretVault[targetId] || '');
            secretSpan.setAttribute('data-visible', '1');
            revealBtn.textContent = 'Verbergen';
          }
        }
        return;
      }
      var button = event.target.closest('button[data-action]');
      if (!button) {
        return;
      }
      executeAction(button.getAttribute('data-action'), button);
    });
    qs('detail-actions').addEventListener('click', function (event) {
      var button = event.target.closest('button[data-action]');
      if (!button) {
        return;
      }
      executeAction(button.getAttribute('data-action'), button);
    });
    qs('policies-list').addEventListener('click', function (event) {
      var card = event.target.closest('[data-policy-name]');
      if (!card) {
        return;
      }
      loadPolicyIntoEditor(card.getAttribute('data-policy-name'));
    });
    qs('policy-save').addEventListener('click', savePolicy);
    qs('policy-new').addEventListener('click', function () {
      resetPolicyEditor();
      setBanner('Policy editor reset.', 'info');
    });
    qs('policy-delete').addEventListener('click', deleteSelectedPolicy);
    if (qs('iam-refresh')) {
      qs('iam-refresh').addEventListener('click', function () {
        refreshIamData();
      });
    }
    if (qs('iam-user-save')) {
      qs('iam-user-save').addEventListener('click', saveIamUser);
    }
    if (qs('iam-user-new')) {
      qs('iam-user-new').addEventListener('click', function () {
        resetIamUserEditor();
        setBanner('User-Editor zurueckgesetzt.', 'info');
      });
    }
    if (qs('iam-user-delete')) {
      qs('iam-user-delete').addEventListener('click', deleteIamUser);
    }
    if (qs('iam-user-revoke')) {
      qs('iam-user-revoke').addEventListener('click', revokeIamUserSessions);
    }
    if (qs('iam-role-save')) {
      qs('iam-role-save').addEventListener('click', saveIamRole);
    }
    if (qs('iam-role-new')) {
      qs('iam-role-new').addEventListener('click', function () {
        resetIamRoleEditor();
        setBanner('Rollen-Editor zurueckgesetzt.', 'info');
      });
    }
    if (qs('iam-role-delete')) {
      qs('iam-role-delete').addEventListener('click', deleteIamRole);
    }
    if (qs('iam-users-body')) {
      qs('iam-users-body').addEventListener('click', function (event) {
        var row = event.target.closest('tr[data-iam-user]');
        if (!row) {
          return;
        }
        loadIamUserIntoEditor(row.getAttribute('data-iam-user'));
        renderIamUsers();
      });
    }
    if (qs('iam-roles-body')) {
      qs('iam-roles-body').addEventListener('click', function (event) {
        var row = event.target.closest('tr[data-iam-role]');
        if (!row) {
          return;
        }
        loadIamRoleIntoEditor(row.getAttribute('data-iam-role'));
        renderIamRoles();
      });
    }
    if (qs('provision-create')) {
      qs('provision-create').addEventListener('click', createProvisionedVm);
    }
    if (qs('provision-reset')) {
      qs('provision-reset').addEventListener('click', function () {
        renderProvisioningWorkspace();
        setBanner('Provisioning-Defaults geladen.', 'info');
      });
    }
    if (qs('provision-modal-create')) {
      qs('provision-modal-create').addEventListener('click', function () {
        createProvisionedVmWithPrefix('prov-modal-');
      });
    }
    if (qs('close-provision-modal')) {
      qs('close-provision-modal').addEventListener('click', closeProvisionModal);
    }
    if (qs('provision-modal-cancel')) {
      qs('provision-modal-cancel').addEventListener('click', closeProvisionModal);
    }
    if (qs('provision-modal-reset')) {
      qs('provision-modal-reset').addEventListener('click', function () {
        loadProvisioningCatalog('prov-modal-');
        setBanner('Modal-Defaults geladen.', 'info');
      });
    }
    if (qs('provision-progress-close')) {
      qs('provision-progress-close').addEventListener('click', function () {
        closeProvisionProgressModal(false);
      });
    }
    if (qs('provision-progress-open-vm')) {
      qs('provision-progress-open-vm').addEventListener('click', function () {
        var vmid = Number(provisionProgressState.vmid || 0);
        closeProvisionProgressModal(true);
        if (vmid > 0) {
          loadDetail(vmid);
        }
      });
    }
    if (qs('refresh-catalog')) {
      qs('refresh-catalog').addEventListener('click', function () {
        markSessionActivity();
        loadDashboard();
      });
    }
    if (qs('provision-recent-body')) {
      qs('provision-recent-body').addEventListener('click', function (event) {
        var row = event.target.closest('tr[data-vmid]');
        if (!row) {
          return;
        }
        var vmid = Number(row.getAttribute('data-vmid') || '0');
        if (vmid > 0) {
          loadDetail(vmid);
        }
      });
    }
    if (qs('virtualization-nodes-body')) {
      qs('virtualization-nodes-body').addEventListener('click', function (event) {
        var row = event.target.closest('tr[data-node]');
        if (!row) {
          return;
        }
        setVirtualizationNodeFilter(row.getAttribute('data-node'));
      });
    }
    if (qs('virtualization-bridges-body')) {
      qs('virtualization-bridges-body').addEventListener('click', function (event) {
        var row = event.target.closest('tr[data-node]');
        if (!row) {
          return;
        }
        setVirtualizationNodeFilter(row.getAttribute('data-node'));
      });
    }
    if (qs('clear-virt-node-filter')) {
      qs('clear-virt-node-filter').addEventListener('click', function () {
        setVirtualizationNodeFilter('');
      });
    }
    if (qs('virt-inspector-load')) {
      qs('virt-inspector-load').addEventListener('click', function () {
        loadVirtualizationInspector(String(qs('virt-inspector-vmid') ? qs('virt-inspector-vmid').value : ''));
      });
    }
    if (qs('virt-inspector-vmid')) {
      qs('virt-inspector-vmid').addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          loadVirtualizationInspector(String(event.target.value || ''));
        }
      });
    }
    if (qs('virt-inspector-use-selected')) {
      qs('virt-inspector-use-selected').addEventListener('click', function () {
        if (!state.selectedVmid) {
          setBanner('Keine VM aus Inventar ausgewaehlt.', 'warn');
          return;
        }
        if (qs('virt-inspector-vmid')) {
          qs('virt-inspector-vmid').value = String(state.selectedVmid);
        }
        loadVirtualizationInspector(state.selectedVmid);
      });
    }

    ['click', 'keydown', 'mousemove', 'touchstart'].forEach(function (eventName) {
      document.addEventListener(eventName, markSessionActivity, { passive: true });
    });
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) {
        return;
      }
      checkSessionTimeout();
    });
  }

  applyTitle();
  loadDarkModePreference();
  updateDarkModeButton();
  updateAutoRefreshButton();
  consumeTokenFromLocation();
  bindEvents();
  resetPolicyEditor();
  resetIamUserEditor();
  resetIamRoleEditor();
  renderVirtualizationOverview();
  renderEndpointsOverview();
  renderActivityLog();
  renderIam();
  renderProvisioningWorkspace();
  renderVirtualizationInspector();
  (function bootstrapHashState() {
    var hashState = parseAppHash();
    var storedPanel = '';
    var storedDetail = '';
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
    if (hashState.vmid && /^\\d+$/.test(hashState.vmid)) {
      state.selectedVmid = Number(hashState.vmid);
    }
  })();
  setActivePanel(state.activePanel);
  setAuthMode(Boolean(state.token));
  updateSessionChrome();
  updateBulkUiState();
  fetchOnboardingStatus()
    .catch(function (error) {
      state.onboarding = { pending: true, completed: false };
      state.token = '';
      state.refreshToken = '';
      state.user = null;
      clearStoredToken();
      clearStoredRefreshToken();
      setAuthMode(false);
      setBanner('Onboarding-Status konnte nicht geladen werden. Bitte Ersteinrichtung fortsetzen.', 'warn');
      openOnboardingModal();
      console.warn('Onboarding status fallback enabled:', error);
    })
    .then(function () {
      loadDashboard();
    });
  window.setInterval(checkSessionTimeout, 60000);
  window.addEventListener('hashchange', function() {
    var hashState = parseAppHash();
    if (hashState.panel && hashState.panel !== state.activePanel) {
      setActivePanel(hashState.panel);
    }
    if (hashState.detail && hashState.detail !== state.activeDetailPanel) {
      setActiveDetailPanel(hashState.detail);
    }
    if (hashState.vmid && /^\\d+$/.test(hashState.vmid) && Number(hashState.vmid) !== state.selectedVmid) {
      loadDetail(hashState.vmid);
    }
  });
  startDashboardPoll();
})();
