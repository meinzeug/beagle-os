import { resolveApiTarget } from './api.js';
import { state } from './state.js';

const liveHooks = {
  loadDashboard() {
    return Promise.resolve();
  },
  loadAuditReport() {
    return Promise.resolve();
  },
  addToActivityLog() {},
  setBanner() {}
};

let source = null;
let reconnectTimer = null;
let reconnectDelayMs = 1500;

export function configureLive(nextHooks) {
  Object.assign(liveHooks, nextHooks || {});
}

function scheduleReconnect() {
  if (reconnectTimer || !state.token) {
    return;
  }
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    connectLiveUpdates();
  }, reconnectDelayMs);
  reconnectDelayMs = Math.min(15000, reconnectDelayMs * 2);
}

function onTickEvent() {
  if (!state.token || document.hidden) {
    return;
  }
  if (state.activePanel === 'audit') {
    liveHooks.loadAuditReport();
    return;
  }
  liveHooks.loadDashboard();
}

function closeSource() {
  if (source) {
    source.close();
    source = null;
  }
  state.liveFeedConnected = false;
}

export function connectLiveUpdates() {
  if (!state.token) {
    closeSource();
    return;
  }
  if (source) {
    return;
  }
  let url = '';
  try {
    const streamBase = resolveApiTarget('/events/stream');
    const parsed = new URL(streamBase, window.location.origin);
    parsed.searchParams.set('access_token', state.token);
    url = parsed.toString();
  } catch (error) {
    liveHooks.setBanner('Live-Updates konnten nicht initialisiert werden.', 'warn');
    return;
  }

  source = new EventSource(url);

  source.addEventListener('hello', () => {
    state.liveFeedConnected = true;
    reconnectDelayMs = 1500;
    liveHooks.setBanner('Live-Updates aktiv (SSE).', 'ok');
    liveHooks.addToActivityLog('live-connect', null, 'ok', 'SSE verbunden');
  });

  source.addEventListener('tick', onTickEvent);

  source.onerror = () => {
    state.liveFeedConnected = false;
    closeSource();
    scheduleReconnect();
  };
}

export function disconnectLiveUpdates() {
  if (reconnectTimer) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  closeSource();
}
