import {
  config,
  FETCH_TIMEOUT_MS,
  state
} from './state.js';

const mutationInFlight = Object.create(null);
let rateLimitBackoffUntil = 0;

const authHooks = {
  buildAuthHeaders() {
    return {};
  },
  refreshAccessToken() {
    return Promise.reject(new Error('auth refresh not configured'));
  },
  canRefreshAfterAuthError() {
    return false;
  },
  shouldHardLockOnUnauthorized() {
    return false;
  },
  lockSession() {
    return null;
  }
};

export function configureApiAuth(nextHooks) {
  Object.assign(authHooks, nextHooks || {});
}

export function apiBase() {
  return String(config.apiBase || '/beagle-api/api/v1').replace(/\/$/, '');
}

export function normalizedOrigin(urlValue) {
  try {
    return new URL(String(urlValue || ''), window.location.origin).origin;
  } catch (error) {
    void error;
    return '';
  }
}

export function trustedApiOrigins() {
  const trusted = Object.create(null);
  trusted[window.location.origin] = true;
  if (Array.isArray(config.trustedApiOrigins)) {
    config.trustedApiOrigins.forEach((value) => {
      const origin = normalizedOrigin(value);
      if (origin) {
        trusted[origin] = true;
      }
    });
  } else if (typeof config.trustedApiOrigins === 'string') {
    config.trustedApiOrigins.split(/[\s,]+/).forEach((value) => {
      const origin = normalizedOrigin(value);
      if (origin) {
        trusted[origin] = true;
      }
    });
  }
  return trusted;
}

export function resolveApiTarget(path) {
  const raw = String(path || '');
  if (!raw) {
    throw new Error('empty api path');
  }
  if (raw.indexOf('http') === 0 && config.allowAbsoluteApiTargets !== true) {
    throw new Error('absolute api targets are disabled');
  }
  const target = raw.indexOf('http') === 0 ? raw : apiBase() + raw;
  let parsed;
  try {
    parsed = new URL(target, window.location.origin);
  } catch (error) {
    throw new Error('invalid api target');
  }
  const trusted = trustedApiOrigins();
  if (!trusted[parsed.origin]) {
    throw new Error('blocked untrusted api origin: ' + parsed.origin);
  }
  return parsed.toString();
}

export function runSingleFlight(key, task) {
  const lockKey = String(key || '').trim();
  if (!lockKey) {
    return Promise.resolve().then(task);
  }
  if (mutationInFlight[lockKey]) {
    return mutationInFlight[lockKey];
  }
  const current = Promise.resolve().then(task).finally(() => {
    if (mutationInFlight[lockKey] === current) {
      delete mutationInFlight[lockKey];
    }
  });
  mutationInFlight[lockKey] = current;
  return current;
}

export function downloadsBase() {
  return String(config.downloadsBase || '/beagle-downloads').replace(/\/$/, '');
}

export function webUiUrl() {
  return String(config.webUiUrl || window.location.origin);
}

export function isSafeExternalUrl(url) {
  try {
    const parsed = new URL(String(url || ''), window.location.origin);
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

export function fetchWithTimeout(url, options, timeoutMs) {
  const timeout = Number(timeoutMs || FETCH_TIMEOUT_MS);
  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  let timer = null;
  const finalOptions = Object.assign({}, options || {});
  if (controller) {
    finalOptions.signal = controller.signal;
    timer = window.setTimeout(() => {
      controller.abort();
    }, Math.max(1, timeout));
  }
  return fetch(url, finalOptions).finally(() => {
    if (timer) {
      window.clearTimeout(timer);
    }
  });
}

function parseRetryAfterSeconds(value) {
  const raw = String(value || '').trim();
  if (!raw) {
    return 0;
  }
  const numeric = Number(raw);
  if (Number.isFinite(numeric) && numeric > 0) {
    return numeric;
  }
  const unixTs = Date.parse(raw);
  if (Number.isFinite(unixTs)) {
    const deltaMs = unixTs - Date.now();
    return deltaMs > 0 ? Math.ceil(deltaMs / 1000) : 0;
  }
  return 0;
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, Math.max(1, Number(ms) || 1));
  });
}

export function request(path, options) {
  const target = resolveApiTarget(path);
  const rawOptions = Object.assign({}, options || {});
  const noRefreshRetry = Boolean(rawOptions.__noRefreshRetry);
  const noRateLimitRetry = Boolean(rawOptions.__noRateLimitRetry);
  const suppressAuthLock = Boolean(rawOptions.__suppressAuthLock);
  const timeoutMs = Number(rawOptions.__timeoutMs || 0);
  delete rawOptions.__noRefreshRetry;
  delete rawOptions.__noRateLimitRetry;
  delete rawOptions.__suppressAuthLock;
  delete rawOptions.__timeoutMs;
  const finalOptions = Object.assign({ method: 'GET', credentials: 'same-origin' }, rawOptions);
  finalOptions.headers = Object.assign({}, finalOptions.headers || {}, authHooks.buildAuthHeaders());
  const method = String(finalOptions.method || 'GET').toUpperCase();
  if ((method === 'GET' || method === 'HEAD') && !finalOptions.cache) {
    finalOptions.cache = 'no-store';
  }
  const startRequest = () => fetchWithTimeout(target, finalOptions, timeoutMs > 0 ? timeoutMs : undefined);
  const startWithBackoff = () => {
    const delayMs = rateLimitBackoffUntil - Date.now();
    if (delayMs > 0) {
      return wait(delayMs).then(startRequest);
    }
    return startRequest();
  };
  return startWithBackoff()
    .then((response) => {
      if (!response.ok) {
        return response.text().then((body) => {
          let detail = body;
          try {
            const parsed = JSON.parse(body);
            detail = parsed.error || parsed.message || body;
          } catch (error) {
            void error;
          }
          if (response.status === 429) {
            const retryAfterRaw = response.headers.get('Retry-After') || '';
            const retryAfterSeconds = parseRetryAfterSeconds(retryAfterRaw);
            const cooldownMs = Math.max(2000, retryAfterSeconds > 0 ? retryAfterSeconds * 1000 : 5000);
            rateLimitBackoffUntil = Math.max(rateLimitBackoffUntil, Date.now() + cooldownMs);
            if (!noRateLimitRetry && (method === 'GET' || method === 'HEAD')) {
              const retriedOptions = Object.assign({}, rawOptions, {
                __noRefreshRetry: noRefreshRetry,
                __noRateLimitRetry: true,
                __suppressAuthLock: suppressAuthLock,
                __timeoutMs: timeoutMs > 0 ? timeoutMs : undefined
              });
              return wait(cooldownMs).then(() => request(path, retriedOptions));
            }
          }
          if ((response.status === 401 || response.status === 403) && state.token) {
            if (!noRefreshRetry && state.refreshToken && authHooks.canRefreshAfterAuthError(path)) {
              return authHooks.refreshAccessToken().then(() => {
                const retriedOptions = Object.assign({}, rawOptions, {
                  __noRefreshRetry: true,
                  __noRateLimitRetry: noRateLimitRetry,
                  __suppressAuthLock: suppressAuthLock,
                  __timeoutMs: timeoutMs > 0 ? timeoutMs : undefined
                });
                return request(path, retriedOptions);
              }).catch(() => {
                if (!suppressAuthLock && authHooks.shouldHardLockOnUnauthorized(path)) {
                  authHooks.lockSession('Sitzung abgelaufen oder ungueltig. Bitte neu anmelden.');
                }
                throw new Error('HTTP ' + response.status + ': ' + detail);
              });
            }
            if (!suppressAuthLock && authHooks.shouldHardLockOnUnauthorized(path)) {
              authHooks.lockSession('Sitzung abgelaufen oder ungueltig. Bitte neu anmelden.');
            }
          }
          throw new Error('HTTP ' + response.status + ': ' + detail);
        });
      }
      return response.json();
    })
    .catch((error) => {
      if (error && (error.name === 'AbortError' || /aborted/i.test(String(error.message || '')))) {
        throw new Error('Request timeout');
      }
      throw error;
    });
}

export function blobRequest(path, filename) {
  const target = resolveApiTarget(path);
  const headers = authHooks.buildAuthHeaders();
  return fetchWithTimeout(target, {
    method: 'GET',
    credentials: 'same-origin',
    headers
  }).then((response) => {
    if (!response.ok) {
      if ((response.status === 401 || response.status === 403) && state.token && state.refreshToken && authHooks.canRefreshAfterAuthError(path)) {
        return authHooks.refreshAccessToken().then(() => {
          return blobRequest(path, filename);
        }).catch(() => {
          if (authHooks.shouldHardLockOnUnauthorized(path)) {
            authHooks.lockSession('Sitzung abgelaufen oder ungueltig. Bitte neu anmelden.');
          }
          throw new Error('HTTP ' + response.status + ' downloading');
        });
      }
      throw new Error('HTTP ' + response.status + ' downloading');
    }
    return response.blob().then((blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      window.setTimeout(() => {
        URL.revokeObjectURL(url);
        link.remove();
      }, 1000);
    });
  }).catch((error) => {
    if (error && (error.name === 'AbortError' || /aborted/i.test(String(error.message || '')))) {
      throw new Error('Download timeout');
    }
    throw error;
  });
}

export function postJson(path, payload, options) {
  return request(path, Object.assign({
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {})
  }, options || {}));
}

export function patchJson(path, payload, options) {
  return request(path, Object.assign({
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {})
  }, options || {}));
}

export function deleteJson(path, options) {
  return request(path, Object.assign({
    method: 'DELETE',
    headers: { 'Accept': 'application/json' }
  }, options || {}));
}