from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API_JS = ROOT / "website" / "ui" / "api.js"
SETTINGS_JS = ROOT / "website" / "ui" / "settings.js"


def test_api_request_retries_transient_get_failures_once() -> None:
    js = API_JS.read_text(encoding="utf-8")

    assert "export function isTransientNetworkError(error)" in js
    assert "const networkRetryCount = Number(rawOptions.__networkRetryCount || 0);" in js
    assert "if ((method === 'GET' || method === 'HEAD') && networkRetryCount < 1 && isTransientNetworkError(error)) {" in js
    assert "__networkRetryCount: networkRetryCount + 1" in js
    assert "return wait(1200).then(() => request(path, retriedOptions));" in js


def test_settings_letsencrypt_success_waits_before_tls_status_refresh() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "window.setTimeout(() => {" in js
    assert "loadSettingsSecurity().catch((error) => {" in js
    assert "TLS-Status-Refresh nach Zertifikatswechsel fehlgeschlagen" in js
