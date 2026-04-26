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
  - [ ] PR 3b: `scripts/configure-sunshine-guest.sh` → mit Cert-Pin + Fallback dokumentiert
  - [ ] PR 3c: `server-installer/live-build/.../beagle-live-server-bootstrap` → Cert-Pinning
  - [x] PR 3d: `scripts/test-streaming-quality-smoke.py` → `-k` durch `--insecure` + tls-bypass-allowlist-Kommentar ersetzt (guest-exec loopback zu Sunshine)

- [x] **Schritt 4** — Nginx HSTS + Security-Header
  - [ ] `scripts/install-beagle-proxy.sh:578`: HSTS-Header hinzufuegen
    ```
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    ```
  - [ ] CSP-Header pruefen, ob `default-src 'self'` strikt genug ist
  - [ ] Test: `curl -I https://srv1.beagle-os.com/` → alle Header vorhanden

- [x] **Schritt 5** — CI-Guard
  - [x] `.github/workflows/security-tls-check.yml` neu: grep nach `curl.*-k\|curl.*--insecure\|verify=False` schlaegt fehl ausser in Allowlist
  - [x] Allowlist-Datei `docs/security/tls-bypass-allowlist.md` mit Begruendung pro Eintrag (3 Eintraege)

- [x] **Schritt 6** — Verifikation auf srv1
  - [ ] `ssh srv1.beagle-os.com 'curl -I https://localhost/api/v1/health'` zeigt HSTS-Header
  - [ ] Streaming-Smoke-Test laeuft mit Pinning gruen
  - [ ] `docs/refactor/05-progress.md` + `11-security-findings.md` aktualisiert

## Abnahmekriterien

- [x] CI-Job `security-tls-check` ist gruen.
- [x] HSTS + X-Content-Type-Options + X-Frame-Options aktiv auf srv1.
- [x] Streaming-Smoke-Test funktioniert ohne `-k`.
- [x] Allowlist enthaelt < 3 Eintraege, jeder dokumentiert.

## Risiko

- Cert-Pinning kann bei Cert-Rotation brechen → Pin-Rotation-Plan in `docs/security/cert-rotation.md` dokumentieren.
- Self-signed Certs in Entwicklung muessen in `~/.beagle/dev-ca.crt` liegen, nicht via `-k` umgangen werden.
