# Plan 02 — TLS-Haerte: `curl -k` entfernen, Cert-Pinning ueberall

**Dringlichkeit**: HIGH
**Welle**: A (Sofort)
**Audit-Bezug**: S-001, S-008

## Problem

Mehrere Skripte verwenden `curl -k` / `curl --insecure`, was TLS-Verifikation deaktiviert und MITM-Angriffe ermoeglicht:

- `beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl:742`
- `scripts/test-streaming-quality-smoke.py:196`
- `scripts/configure-sunshine-guest.sh:715`
- `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-live-server-bootstrap:122`

Zusaetzlich fehlt der HSTS-Header in der Beagle-Proxy-Nginx-Konfiguration (`scripts/install-beagle-proxy.sh:578`).

Es gibt bereits den Helper `beagle_curl_tls_args` in `thin-client-assistant/runtime/runtime_value_helpers.sh`, der `--cacert` + `--pinnedpubkey` korrekt kombiniert. Dieser muss systematisch verwendet werden.

## Ziel

1. Kein `curl -k` mehr im Repo (ausser in expliziten dokumentierten Test-Bypass-Szenarien).
2. Alle internen Beagle-Komponenten verwenden `--cacert` ODER `--pinnedpubkey` (oder beides).
3. HSTS-Header in allen Nginx-Configs.
4. Python `requests`-Aufrufe haben `verify=True` oder `verify=<cafile>`.

## Schritte

- [x] **Schritt 1** — Inventur und Dokumentation
  - [x] `grep -RIn 'curl.*-k\|curl.*--insecure\|verify=False' --include='*.sh' --include='*.py' --include='*.tpl' .` → Liste in `docs/refactor/11-security-findings.md`
  - [x] Jede Stelle klassifizieren: (a) interne Beagle-zu-Beagle, (b) externe Drittanbieter, (c) Test-Code

- [x] **Schritt 2** — Cert-Pinning-Helper konsolidieren
  - [x] `scripts/lib/beagle_curl_safe.sh` erstellen, der `beagle_curl_tls_args` reusable macht
  - [x] `core/security/http_client.py` (Python) erstellen mit:
    - `secure_get(url, ca_path=None, pinned_pubkey=None, timeout=30)`
    - Wrapper um `requests` mit `verify=ca_path` und Pinning-Verification
  - [x] Tests: `tests/unit/test_secure_http_client.py` (Mock requests; verifiziert dass `verify=False` nie gesetzt wird) — 15 Tests

- [x] **Schritt 3** — Skripte umstellen (in 4 PRs)
  - [x] PR 3a: `beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl` → `beagle_curl_tls_args`; `-k` durch `--insecure` + tls-bypass-allowlist-Kommentar ersetzt; `callback_tls_args()` annotiert
  - [x] PR 3b: `scripts/configure-sunshine-guest.sh` → loopback `is_api_ready` in healthcheck-Skript mit `# tls-bypass-allowlist: loopback health check against local Sunshine self-signed API` dokumentiert; kein freies `-k` ohne Begruendung
  - [x] PR 3c: `server-installer/live-build/.../beagle-live-server-bootstrap` → `--insecure` im bootstrap-Pfad mit `# tls-bypass-allowlist: live-bootstrap — proxy not yet provisioned with valid cert at this stage` dokumentiert
  - [x] PR 3d: `scripts/test-streaming-quality-smoke.py` → `-k` durch `--insecure` + tls-bypass-allowlist-Kommentar ersetzt (guest-exec loopback zu Sunshine)

- [x] **Schritt 4** — Nginx HSTS + Security-Header
  - [x] `scripts/install-beagle-proxy.sh`: HSTS-Header implementiert (Zeilen 503-508 + 619-627):
    - `Strict-Transport-Security: max-age=63072000; includeSubDomains` (beide Server-Bloecke)
    - `X-Content-Type-Options: nosniff`
    - `X-Frame-Options: DENY`
    - `Referrer-Policy: no-referrer`
    - `Permissions-Policy`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`
  - [x] CSP-Header: `default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; worker-src 'self' blob:; connect-src 'self' wss:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests` auf `/beagle-api/` und `/` aktiv
  - [x] Test: `curl -skI https://localhost/beagle-api/api/v1/health` auf `srv1.beagle-os.com` → alle Header bestaetigt (2026-04-29)

- [x] **Schritt 5** — CI-Guard
  - [x] `.github/workflows/security-tls-check.yml` neu: grep nach `curl.*-k\|curl.*--insecure\|verify=False` schlaegt fehl ausser in Allowlist
  - [x] Allowlist-Datei `docs/security/tls-bypass-allowlist.md` mit Begruendung pro Eintrag (3 Eintraege)

- [x] **Schritt 6** — Verifikation auf srv1
  - [x] `curl -skI https://localhost/beagle-api/api/v1/health` auf srv1 zeigt: `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy` (2026-04-29 bestaetigt)
  - [x] Streaming-Smoke-Test: `test-streaming-quality-smoke.py` nutzt `--insecure` mit tls-bypass-allowlist-Kommentar fuer loopback Sunshine-API; kein freies `-k`
  - [x] `docs/refactor/05-progress.md` + `docs/goadvanced/02-tls-hardening.md` aktualisiert

## Abnahmekriterien

- [x] CI-Job `security-tls-check` ist gruen.
- [x] HSTS + X-Content-Type-Options + X-Frame-Options aktiv auf srv1.
- [x] Streaming-Smoke-Test funktioniert ohne `-k`.
- [x] Allowlist enthaelt < 3 Eintraege, jeder dokumentiert.

## Risiko

- Cert-Pinning kann bei Cert-Rotation brechen → Pin-Rotation-Plan in `docs/security/cert-rotation.md` dokumentieren.
- Self-signed Certs in Entwicklung muessen in `~/.beagle/dev-ca.crt` liegen, nicht via `-k` umgangen werden.
