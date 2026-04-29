"""
Unit tests for website/ui/i18n.js and website/ui/error-handler.js.

JS modules are executed via Node.js. Dynamic imports are used so that
globalThis stubs are set up before module evaluation.
"""

import json
import subprocess
import textwrap
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

# ---------------------------------------------------------------------------
# Node.js test driver (stubs run BEFORE any import)
# ---------------------------------------------------------------------------

_STUBS = textwrap.dedent("""
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dir = dirname(fileURLToPath(import.meta.url));
const repoRoot = __dir;  // stdin module: import.meta.url resolves to cwd

globalThis.navigator = { language: 'de' };
globalThis.localStorage = (() => {
  const store = {};
  return {
    getItem: k => store[k] ?? null,
    setItem: (k, v) => { store[k] = v; },
    removeItem: k => { delete store[k]; },
  };
})();
globalThis.window = globalThis;
globalThis.location = { hostname: 'localhost', href: 'http://localhost/', search: '' };
globalThis.dispatchEvent = () => {};
globalThis.addEventListener = () => {};
globalThis.CustomEvent = class CustomEvent {
  constructor(type, opts) { this.type = type; this.detail = opts?.detail; }
};
globalThis.XMLHttpRequest = class XMLHttpRequest {
  open(method, url) { this._url = url; }
  send() {
    const match = (this._url || '').match(/\\/locales\\/([^/]+\\.json)/);
    if (match) {
      try {
        const p = join(repoRoot, 'website', 'locales', match[1]);
        this.status = 200;
        this.responseText = readFileSync(p, 'utf8');
        return;
      } catch (_) {}
    }
    this.status = 404;
    this.responseText = '{}';
  }
};
globalThis.document = {
  querySelector: () => null,
  getElementById: () => null,
  createElement: (tag) => ({
    tagName: tag,
    className: '',
    textContent: '',
    innerHTML: '',
    style: {},
    classList: { add: () => {}, remove: () => {}, contains: () => false },
    appendChild: () => {},
    setAttribute: () => {},
    getAttribute: () => null,
    addEventListener: () => {},
    removeEventListener: () => {},
    remove: () => {},
    parentNode: null,
    querySelector: () => null,
    querySelectorAll: () => [],
  }),
  body: { appendChild: () => {}, classList: { add: () => {}, contains: () => false } },
};
""")


def _run_js(body: str) -> str:
    """Run body inside an async IIFE after stubs, using dynamic imports."""
    script = _STUBS + textwrap.dedent(f"""
(async () => {{
{textwrap.indent(textwrap.dedent(body), '  ')}
}})().catch(err => {{ console.error(err); process.exit(1); }});
""")
    result = subprocess.run(
        ["node", "--input-type=module"],
        input=script,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Node failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# i18n module tests
# ---------------------------------------------------------------------------

class TestI18n:
    def test_simple_key_de(self):
        out = _run_js("""
const { t } = await import('./website/ui/i18n.js');
console.log(t('action.login'));
""")
        assert out == "Anmelden", f"Got: {out}"

    def test_simple_key_en(self):
        out = _run_js("""
const { t, setLanguage } = await import('./website/ui/i18n.js');
setLanguage('en');
console.log(t('action.login'));
""")
        assert out == "Log in", f"Got: {out}"

    def test_interpolation_de(self):
        out = _run_js("""
const { t, setLanguage } = await import('./website/ui/i18n.js');
setLanguage('de');
console.log(t('auth.user_logged_in', { username: 'admin' }));
""")
        assert "admin" in out and "Angemeldet" in out, f"Got: {out}"

    def test_interpolation_en(self):
        out = _run_js("""
const { t, setLanguage } = await import('./website/ui/i18n.js');
setLanguage('en');
console.log(t('error.server', { status: 503 }));
""")
        assert "503" in out, f"Got: {out}"

    def test_missing_key_returns_key(self):
        out = _run_js("""
const { t } = await import('./website/ui/i18n.js');
console.log(t('does.not.exist'));
""")
        assert out == "does.not.exist", f"Got: {out}"

    def test_missing_param_placeholder_preserved(self):
        out = _run_js("""
const { t, setLanguage } = await import('./website/ui/i18n.js');
setLanguage('de');
console.log(t('auth.locked'));
""")
        assert "{seconds}" in out, f"Got: {out}"

    def test_get_language_default_de(self):
        out = _run_js("""
const { getLanguage } = await import('./website/ui/i18n.js');
console.log(getLanguage());
""")
        assert out == "de", f"Got: {out}"

    def test_set_language(self):
        out = _run_js("""
const { setLanguage, getLanguage } = await import('./website/ui/i18n.js');
setLanguage('en');
console.log(getLanguage());
""")
        assert out == "en", f"Got: {out}"

    def test_unsupported_language_is_ignored(self):
        out = _run_js("""
const { setLanguage, getLanguage } = await import('./website/ui/i18n.js');
setLanguage('fr');
console.log(getLanguage());
""")
        assert out == "de", f"Got: {out}"

    def test_get_supported_languages(self):
        out = _run_js("""
const { getSupportedLanguages } = await import('./website/ui/i18n.js');
console.log(JSON.stringify(getSupportedLanguages().sort()));
""")
        langs = json.loads(out)
        assert "de" in langs and "en" in langs, f"Got: {langs}"

    def test_action_cancel_de(self):
        out = _run_js("""
const { t } = await import('./website/ui/i18n.js');
console.log(t('action.cancel'));
""")
        assert out == "Abbrechen", f"Got: {out}"


# ---------------------------------------------------------------------------
# error-handler module tests (pure logic; toast DOM is stubbed away)
# ---------------------------------------------------------------------------

class TestErrorHandler:
    def test_all_exports_are_functions(self):
        out = _run_js("""
const mod = await import('./website/ui/error-handler.js');
const fns = ['showError','showWarning','showSuccess','showInfo','handleFetchError','withErrorHandling'];
const types = fns.map(f => typeof mod[f]);
console.log(JSON.stringify(types));
""")
        types = json.loads(out)
        assert all(t == "function" for t in types), f"Got: {types}"

    def test_with_error_handling_rethrows(self):
        out = _run_js("""
const { withErrorHandling } = await import('./website/ui/error-handler.js');
try {
  await withErrorHandling(Promise.reject(new Error('boom')), 'test');
} catch (err) {
  console.log('caught:' + err.message);
}
""")
        assert "caught:boom" in out, f"Got: {out}"

    def test_with_error_handling_resolves(self):
        out = _run_js("""
const { withErrorHandling } = await import('./website/ui/error-handler.js');
const val = await withErrorHandling(Promise.resolve('ok'), 'test');
console.log(val);
""")
        assert out == "ok", f"Got: {out}"

    def test_unauthorized_message_via_i18n(self):
        out = _run_js("""
const { t, setLanguage } = await import('./website/ui/i18n.js');
setLanguage('de');
console.log(t('error.unauthorized'));
""")
        assert out and ("anmelden" in out.lower() or "autorisiert" in out.lower()), f"Got: {out}"

    def test_network_error_message_via_i18n(self):
        out = _run_js("""
const { t, setLanguage } = await import('./website/ui/i18n.js');
setLanguage('de');
console.log(t('error.network'));
""")
        assert "Netzwerk" in out or "Verbindung" in out, f"Got: {out}"


# ---------------------------------------------------------------------------
# Locale file structure tests (pure Python, no JS needed)
# ---------------------------------------------------------------------------

class TestLocaleFiles:
    def _load(self, lang: str) -> dict:
        p = REPO_ROOT / "website" / "locales" / f"{lang}.json"
        return json.loads(p.read_text(encoding="utf-8"))

    REQUIRED_KEYS = [
        "action.login", "action.logout", "action.save", "action.cancel",
        "status.error", "status.loading", "status.done",
        "error.generic", "error.network", "error.unauthorized",
        "error.forbidden", "error.not_found", "error.server",
    ]

    def test_de_has_required_keys(self):
        de = self._load("de")
        missing = [k for k in self.REQUIRED_KEYS if k not in de]
        assert not missing, f"Missing in de.json: {missing}"

    def test_en_has_required_keys(self):
        en = self._load("en")
        missing = [k for k in self.REQUIRED_KEYS if k not in en]
        assert not missing, f"Missing in en.json: {missing}"

    def test_de_and_en_same_key_set(self):
        de = set(self._load("de"))
        en = set(self._load("en"))
        only_de = de - en
        only_en = en - de
        assert not only_de, f"Keys only in de.json: {only_de}"
        assert not only_en, f"Keys only in en.json: {only_en}"

    def test_no_empty_values(self):
        for lang in ("de", "en"):
            catalog = self._load(lang)
            empty = [k for k, v in catalog.items() if not str(v).strip()]
            assert not empty, f"Empty values in {lang}.json: {empty}"

    def test_valid_json(self):
        for lang in ("de", "en"):
            p = REPO_ROOT / "website" / "locales" / f"{lang}.json"
            data = json.loads(p.read_text(encoding="utf-8"))
            assert isinstance(data, dict), f"{lang}.json is not an object"
