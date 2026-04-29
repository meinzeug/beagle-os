/**
 * Beagle Web Console — i18n module
 *
 * Lightweight internationalisation for the Vanilla-JS frontend.
 * No external dependencies. Works in browsers that support ES modules.
 *
 * Usage:
 *   import { t, setLanguage, getLanguage } from './i18n.js';
 *   t('action.login')                    // → "Anmelden" (when lang=de)
 *   t('auth.user_logged_in', { username: 'admin' }) // → "Angemeldet: admin"
 *   setLanguage('en');                   // switch at runtime
 */

const STORAGE_KEY = 'beagle.lang';
const DEFAULT_LANG = 'de';
const SUPPORTED = new Set(['de', 'en']);

/** Loaded locale dictionaries { 'de': {…}, 'en': {…} } */
const _catalogs = {};

/** Active language code (e.g. 'de', 'en') */
let _lang = DEFAULT_LANG;

// ---------------------------------------------------------------------------
// Bootstrap: detect language from storage / navigator
// ---------------------------------------------------------------------------

function _detectLang() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && SUPPORTED.has(stored)) {
      return stored;
    }
  } catch (_) { void _; }

  // navigator.language → 'de-DE' → 'de'
  const nav = (navigator.language || '').split('-')[0].toLowerCase();
  if (SUPPORTED.has(nav)) {
    return nav;
  }
  return DEFAULT_LANG;
}

// ---------------------------------------------------------------------------
// Catalog loading (synchronous JSON fetch via XHR for module-compat)
// ---------------------------------------------------------------------------

/**
 * Load a locale catalog synchronously.
 * Falls back to empty object on failure so the app keeps working.
 * @param {string} lang
 * @returns {Record<string, string>}
 */
function _loadCatalog(lang) {
  if (_catalogs[lang]) {
    return _catalogs[lang];
  }
  try {
    const base = document.querySelector('meta[name="beagle-base"]')?.content || '';
    const xhr = new XMLHttpRequest();
    xhr.open('GET', base + '/locales/' + lang + '.json', false /* synchronous */);
    xhr.send(null);
    if (xhr.status === 200) {
      _catalogs[lang] = JSON.parse(xhr.responseText);
    } else {
      _catalogs[lang] = {};
    }
  } catch (_) {
    _catalogs[lang] = {};
  }
  return _catalogs[lang];
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Translate a key with optional named interpolation.
 *
 * @param {string} key  - e.g. 'action.login', 'auth.locked'
 * @param {Record<string, string|number>} [params] - e.g. { seconds: 5 }
 * @returns {string}
 */
export function t(key, params) {
  const catalog = _loadCatalog(_lang);
  const fallback = _lang !== 'en' ? _loadCatalog('en') : null;

  let str = catalog[key] ?? (fallback ? (fallback[key] ?? key) : key);

  if (params && typeof params === 'object') {
    str = str.replace(/\{(\w+)\}/g, (_, k) => {
      const val = params[k];
      return val !== undefined ? String(val) : '{' + k + '}';
    });
  }
  return str;
}

/**
 * Get the current active language code.
 * @returns {string}
 */
export function getLanguage() {
  return _lang;
}

/**
 * Switch the active language at runtime.
 * Dispatches a 'beagle:langchange' CustomEvent on window so UI can re-render.
 * @param {string} lang - 'de' | 'en'
 */
export function setLanguage(lang) {
  if (!SUPPORTED.has(lang)) {
    return;
  }
  _lang = lang;
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch (_) { void _; }
  window.dispatchEvent(new CustomEvent('beagle:langchange', { detail: { lang } }));
}

/**
 * Return array of all supported language codes.
 * @returns {string[]}
 */
export function getSupportedLanguages() {
  return Array.from(SUPPORTED);
}

// ---------------------------------------------------------------------------
// Initialise on module load
// ---------------------------------------------------------------------------

_lang = _detectLang();
_loadCatalog(_lang);
