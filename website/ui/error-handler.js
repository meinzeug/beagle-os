/**
 * Beagle Web Console — standardised error-handler
 *
 * Provides consistent error / warning / success display via the
 * existing job-toast infrastructure (jobs_panel.js).
 *
 * Usage:
 *   import { showError, showWarning, showSuccess, handleFetchError } from './error-handler.js';
 *
 *   showError('Verbindungsfehler');
 *   showError(new Error('Timeout'), { context: 'VM starten', recoverable: true });
 *   showSuccess('VM gestartet');
 *   showWarning('GPU nicht verfügbar');
 *
 *   // automatic HTTP error translation:
 *   fetch('/api/...').then(r => r.json()).catch(err => handleFetchError(err, 'VM starten'));
 */

import { showJobToast } from './jobs_panel.js';
import { t } from './i18n.js';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const DEV_MODE =
  typeof window !== 'undefined' &&
  (window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1' ||
    (window.BEAGLE_DEV_MODE === true));

const DURATION_ERROR_MS = 10_000;
const DURATION_WARN_MS = 7_000;
const DURATION_SUCCESS_MS = 4_000;
const DURATION_INFO_MS = 5_000;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Resolve a raw error argument to a human-readable string.
 * @param {unknown} err
 * @param {boolean} includeStack - only in dev mode
 * @returns {string}
 */
function _errorToString(err, includeStack = false) {
  if (!err) return t('error.generic');
  if (typeof err === 'string') return err;
  if (err instanceof Error) {
    if (includeStack && DEV_MODE && err.stack) {
      return err.message + '\n' + err.stack;
    }
    return err.message || t('error.generic');
  }
  return String(err);
}

/**
 * Show a toast with a custom duration. Wraps showJobToast with a second
 * auto-dismiss because the underlying TOAST_DURATION_MS is fixed.
 * @param {string} message
 * @param {'info'|'success'|'warn'|'error'} tone
 */
function _show(message, tone) {
  // showJobToast handles the DOM work; duration is controlled there.
  // We pass the message only — duration differences are cosmetic and
  // the base 5 s is acceptable for all tones for now.
  showJobToast(message, tone);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Display an error notification.
 *
 * @param {unknown} err            - string, Error object, or anything stringifiable
 * @param {{ context?: string, recoverable?: boolean }} [options]
 *   context    – short label prepended to the message (e.g. 'VM starten')
 *   recoverable – (informational) whether the error is transient
 */
export function showError(err, options = {}) {
  const raw = _errorToString(err, /* includeStack */ true);
  const msg = options.context ? options.context + ': ' + raw : raw;
  _show(msg, 'error');
  if (DEV_MODE) {
    console.error('[Beagle]', msg, err);
  }
}

/**
 * Display a warning notification.
 * @param {string} message
 */
export function showWarning(message) {
  _show(String(message || t('status.warning')), 'warn');
}

/**
 * Display a success notification.
 * @param {string} message
 */
export function showSuccess(message) {
  _show(String(message || t('status.success')), 'success');
}

/**
 * Display an informational notification.
 * @param {string} message
 */
export function showInfo(message) {
  _show(String(message || ''), 'info');
}

/**
 * Translate a fetch/HTTP response error into a user-friendly message
 * and display it.
 *
 * @param {unknown} err       - caught exception OR Response object
 * @param {string} [context]  - action context label, e.g. 'VM starten'
 */
export function handleFetchError(err, context) {
  let msg;

  // Handle Response-like objects (e.g. when callers throw on !response.ok)
  if (err && typeof err === 'object' && 'status' in err) {
    const status = err.status;
    if (status === 401) {
      msg = t('error.unauthorized');
    } else if (status === 403) {
      msg = t('error.forbidden');
    } else if (status === 404) {
      msg = t('error.not_found');
    } else if (status >= 500) {
      msg = t('error.server', { status });
    } else {
      msg = t('error.generic');
    }
  } else if (err instanceof TypeError && String(err.message).includes('fetch')) {
    msg = t('error.network');
  } else if (err instanceof Error && err.name === 'AbortError') {
    msg = t('error.timeout');
  } else {
    msg = _errorToString(err);
  }

  showError(msg, { context });
}

/**
 * Wraps a Promise so that any rejection is automatically displayed
 * as an error toast. Returns the original promise (for chaining).
 *
 * @template T
 * @param {Promise<T>} promise
 * @param {string} [context]
 * @returns {Promise<T>}
 */
export function withErrorHandling(promise, context) {
  return promise.catch(err => {
    handleFetchError(err, context);
    throw err; // re-throw so caller can also react
  });
}
