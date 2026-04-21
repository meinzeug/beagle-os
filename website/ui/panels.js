import {
  config,
  panelMeta,
  state
} from './state.js';
import { qs, text } from './dom.js';
import { fetchWithTimeout, resolveApiTarget } from './api.js';
import { clearPersistedTokens, setSessionTokens } from './auth.js';

const panelHooks = {
  loadSettingsForPanel() {}
};

export function configurePanels(nextHooks) {
  Object.assign(panelHooks, nextHooks || {});
}

export function applyTitle() {
  const title = String(config.title || 'Beagle OS Web UI');
  document.title = title;
  const heading = document.querySelector('.app-header h1');
  if (heading) {
    heading.textContent = title;
  }
}

export function consumeTokenFromLocation() {
  if (config.allowHashToken !== true) {
    return;
  }
  const hash = String(window.location.hash || '').replace(/^#/, '');
  if (!hash) {
    return;
  }
  const tokenMatch = hash.match(/(?:^|&)beagle_token=([^&]+)/);
  if (!tokenMatch) {
    return;
  }
  const params = new URLSearchParams(hash);
  const token = String(params.get('beagle_token') || '').trim();
  if (!token) {
    return;
  }
  setSessionTokens(token, '');
  if (qs('api-token')) {
    qs('api-token').value = token;
  }
  if (window.history && window.history.replaceState) {
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
  } else {
    window.location.hash = '';
  }
}

export function parseAppHash() {
  const raw = String(window.location.hash || '').replace(/^#/, '');
  if (!raw || raw.indexOf('beagle_token=') !== -1) {
    return {};
  }
  const params = new URLSearchParams(raw);
  return {
    panel: String(params.get('panel') || '').trim(),
    vmid: String(params.get('vmid') || '').trim(),
    detail: String(params.get('detail') || '').trim()
  };
}

export function syncHash() {
  const params = new URLSearchParams();
  if (state.activePanel && state.activePanel !== 'overview') {
    params.set('panel', state.activePanel);
  }
  if (state.activePanel === 'inventory' && state.selectedVmid) {
    params.set('vmid', String(state.selectedVmid));
  }
  if (state.activePanel === 'inventory' && state.activeDetailPanel && state.activeDetailPanel !== 'summary') {
    params.set('detail', state.activeDetailPanel);
  }
  const next = params.toString();
  const current = String(window.location.hash || '').replace(/^#/, '');
  if (current !== next) {
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, '', window.location.pathname + window.location.search + (next ? '#' + next : ''));
    } else {
      window.location.hash = next;
    }
  }
}

export function updateSessionChrome() {
  const chip = qs('session-chip');
  const sidebarBtn = qs('open-connect-modal');
  if (chip) {
    if (!state.token) {
      chip.textContent = 'Nicht verbunden';
    } else if (state.user && state.user.username) {
      chip.textContent = 'Angemeldet: ' + String(state.user.username);
    } else {
      chip.textContent = 'Verbunden';
    }
  }
  if (sidebarBtn) {
    if (state.token) {
      sidebarBtn.textContent = 'Abmelden';
      sidebarBtn.classList.remove('primary');
      sidebarBtn.classList.add('ghost');
    } else {
      sidebarBtn.textContent = 'Anmelden';
      sidebarBtn.classList.remove('ghost');
      sidebarBtn.classList.add('primary');
    }
  }
}

export function setAuthMode(connected) {
  document.body.classList.toggle('auth-only', !connected);
  if (connected) {
    document.body.classList.remove('auth-modal-open');
    const authModal = qs('auth-modal');
    if (authModal) {
      authModal.hidden = true;
      authModal.setAttribute('aria-hidden', 'true');
    }
    const onboardingModal = qs('onboarding-modal');
    if (onboardingModal) {
      onboardingModal.hidden = true;
      onboardingModal.setAttribute('aria-hidden', 'true');
    }
  } else {
    document.body.classList.add('auth-modal-open');
  }
  updateSessionChrome();
}

export function setBanner(message, tone) {
  const node = qs('auth-status');
  if (!node) {
    return;
  }
  node.className = 'banner ' + String(tone || 'info');
  node.textContent = message;
}

export function requestConfirm(opts) {
  const options = opts || {};
  return new Promise((resolve) => {
    const modal = qs('confirm-modal');
    const titleEl = qs('confirm-title');
    const msgEl = qs('confirm-message');
    const acceptBtn = qs('confirm-accept');
    const cancelBtn = qs('confirm-cancel');
    if (!modal || !titleEl || !msgEl || !acceptBtn || !cancelBtn) {
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

    function onAccept() {
      close(true);
    }

    function onCancel() {
      close(false);
    }

    function onKey(event) {
      if (event.key === 'Escape') {
        close(false);
      }
      if (event.key === 'Enter') {
        close(true);
      }
    }

    function onBackdrop(event) {
      if (event.target === modal) {
        close(false);
      }
    }

    acceptBtn.addEventListener('click', onAccept);
    cancelBtn.addEventListener('click', onCancel);
    document.addEventListener('keydown', onKey);
    modal.addEventListener('click', onBackdrop);
    window.setTimeout(() => {
      acceptBtn.focus();
    }, 30);
  });
}

export function setActivePanel(panelName) {
  const next = panelMeta[panelName] ? panelName : 'overview';
  state.activePanel = next;
  try {
    localStorage.setItem('beagle.ui.activePanel', next);
  } catch (error) {
    void error;
  }
  document.querySelectorAll('[data-panel]').forEach((node) => {
    node.classList.toggle('nav-item-active', node.getAttribute('data-panel') === next);
  });
  document.querySelectorAll('[data-panel-section]').forEach((node) => {
    const sectionPanel = node.getAttribute('data-panel-section');
    node.classList.toggle('panel-section-active', sectionPanel === next);
  });
  const meta = panelMeta[next] || panelMeta.overview;
  text('panel-eyebrow', meta.eyebrow);
  text('panel-title', meta.title);
  text('panel-description', meta.description);
  if (next.indexOf('settings_') === 0) {
    panelHooks.loadSettingsForPanel(next);
  }
  syncHash();
}

export function setActiveDetailPanel(panelName) {
  const next = panelName || 'summary';
  state.activeDetailPanel = next;
  try {
    localStorage.setItem('beagle.ui.activeDetailPanel', next);
  } catch (error) {
    void error;
  }
  document.querySelectorAll('[data-detail-panel]').forEach((node) => {
    node.classList.toggle('detail-tab-active', node.getAttribute('data-detail-panel') === next);
  });
  document.querySelectorAll('.detail-panel').forEach((node) => {
    node.classList.toggle('detail-panel-active', node.getAttribute('data-detail-panel') === next);
  });
  syncHash();
}

export function openAuthModal() {
  if (state.onboarding && state.onboarding.pending) {
    openOnboardingModal();
    return;
  }
  const authModal = qs('auth-modal');
  if (authModal) {
    authModal.hidden = false;
    authModal.setAttribute('aria-hidden', 'false');
  }
  document.body.classList.add('auth-modal-open');
  const field = qs('auth-username') || qs('api-token');
  let rememberedUsername = '';
  try {
    rememberedUsername = String(localStorage.getItem('beagle.auth.username') || '').trim();
  } catch (error) {
    void error;
  }
  if (rememberedUsername && qs('auth-username') && !String(qs('auth-username').value || '').trim()) {
    qs('auth-username').value = rememberedUsername;
  }
  if (field) {
    window.setTimeout(() => {
      field.focus();
      if (typeof field.select === 'function') {
        field.select();
      }
    }, 30);
  }
}

export function closeAuthModal() {
  if (!document.body.classList.contains('auth-only')) {
    document.body.classList.remove('auth-modal-open');
  }
  const authModal = qs('auth-modal');
  if (authModal) {
    authModal.hidden = true;
    authModal.setAttribute('aria-hidden', 'true');
  }
}

export function openOnboardingModal() {
  const modal = qs('onboarding-modal');
  if (!modal) {
    return;
  }
  const authModal = qs('auth-modal');
  if (authModal) {
    authModal.hidden = true;
    authModal.setAttribute('aria-hidden', 'true');
  }
  modal.hidden = false;
  modal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('auth-modal-open');
  const username = qs('onboarding-username');
  if (username && !String(username.value || '').trim()) {
    username.value = 'admin';
  }
  if (username) {
    window.setTimeout(() => {
      username.focus();
      username.select();
    }, 30);
  }
}

export function closeOnboardingModal() {
  const modal = qs('onboarding-modal');
  if (!modal) {
    return;
  }
  modal.hidden = true;
  modal.setAttribute('aria-hidden', 'true');
  const authModal = qs('auth-modal');
  if (authModal) {
    authModal.hidden = false;
    authModal.setAttribute('aria-hidden', 'false');
  }
}

export function fetchOnboardingStatus() {
  return fetchWithTimeout(resolveApiTarget('/auth/onboarding/status'), {
    method: 'GET',
    credentials: 'same-origin'
  }).then((response) => {
    if (!response.ok) {
      throw new Error('HTTP ' + response.status);
    }
    return response.json();
  }).then((payload) => {
    const onboarding = payload && payload.onboarding ? payload.onboarding : {};
    state.onboarding = {
      pending: Boolean(onboarding.pending),
      completed: Boolean(onboarding.completed)
    };
    if (state.onboarding.pending) {
      clearPersistedTokens();
      state.user = null;
      setAuthMode(false);
      setBanner('Ersteinrichtung erforderlich: bitte Administrator anlegen.', 'warn');
      openOnboardingModal();
    } else {
      closeOnboardingModal();
    }
    return state.onboarding;
  });
}

export function completeOnboarding() {
  const username = String(qs('onboarding-username') ? qs('onboarding-username').value : '').trim();
  const password = String(qs('onboarding-password') ? qs('onboarding-password').value : '');
  const passwordConfirm = String(qs('onboarding-password-confirm') ? qs('onboarding-password-confirm').value : '');
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
      username,
      password,
      password_confirm: passwordConfirm
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
  }).catch((error) => {
    setBanner('Onboarding fehlgeschlagen: ' + error.message, 'warn');
  });
}

export function accountShell() {
  const toggle = qs('avatar-toggle');
  return toggle ? toggle.closest('.account-shell') : null;
}

export function closeAccountMenu() {
  const shell = accountShell();
  if (shell) {
    shell.classList.remove('menu-open');
  }
}