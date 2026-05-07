# 03 — Sicherheit, Auth, Audit, Compliance

**Scope**: Auth/Session, RBAC, Secrets, Audit, TLS, IAM/Tenancy, Compliance-Export.
**Quelle**: konsolidiert aus `docs/archive/goadvanced/02-04`, `docs/archive/gofuture/13-15,20`, `docs/archive/gorelease/01,05`, `docs/refactor/11-security-findings.md`.

---

## Auth + Session + RBAC

- [x] Refactor Welle 1: Login, Refresh, Logout, RBAC-Middleware fuer mutierende Endpoints (services: `auth_session.py`, `authz_policy.py`)
- [x] LDAP-Auth + SCIM-Provisioning (`ldap_auth.py`)
- [x] Auth-Bootstrap auto-generiert (Plan 03 Schritt 3)
- [x] Brute-Force-Schutz inkl. Rate-Limit-Test in pytest
- [x] Session-Cookies: `Secure`, `HttpOnly`, `SameSite`, kurze TTL durchgaengig validieren (R3) — `Max-Age` fix in `request_handler_mixin._refresh_cookie_header`, 9 unit-tests `SESSION_COOKIE_FLAGS`=PASS (2026-04-30)
- [x] Login-Smoke per echtem Browser auf Zielhost ohne Console-Fehler (R3) — `WEBUI_RBAC_BROWSER_SMOKE=PASS` auf srv1 (2026-04-30, Viewer-Login erfolgreich, 0 console/page errors)

## RBAC + Tenancy

- [x] IAM v2 + Mandanten + SCIM/OIDC/SAML (`docs/archive/gofuture/13-iam-tenancy.md`)
- [x] Tenant-Sichtbarkeit fuer VMs/Pools/Sessions/Audit
- [x] RBAC-Regression fuer alle Built-in-Rollen: admin, operator, kiosk_operator, read-only, tenant-scoped (R3) — 42 tests in `test_authz_policy.py::BuiltInRoleRegressionTests` PASS (2026-04-30)
- [x] Browser-Smoke mit Nicht-Admin-Rolle zeigt keine Admin-Aktionen (R3) — `WEBUI_RBAC_BROWSER_SMOKE=PASS` auf srv1 (2026-04-30, visible_admin_panels=0, settings label hidden)

## Secret-Management

- [x] `SecretStoreService` mit JSON-Backend (mode 0o600, Audit-Events)
- [x] CLI: `beaglectl secret list/rotate/revoke`
- [x] WebUI: `secrets_admin.js` (RBAC: `security_admin`)
- [x] Audit-Filter prueft, dass Klartext-Werte nie in Logs landen
- [ ] Phase 2 — Vault-/AWS-Adapter (Backlog, optional)

## TLS + Hardening

- [x] HSTS, CSP, COOP, CORP, X-Frame-Options, X-Content-Type-Options, Permissions-Policy live auf srv1 (verifiziert 2026-04-29)
- [x] mTLS fuer interne Cluster-Kommunikation (`harden-cluster-api-iptables.sh`)
- [x] CI-Guard `security-tls-check.yml` aktiv
- [x] BeagleStream Public-DNAT geschlossen (2026-05-07): Public-Ports `49995/50000/50001/50021` closed, UDP `50009-50015` per prerouting guard vor DNAT gedroppt, Legacy-Tabelle `inet beagle_stream` entfernt.
- [ ] TLS-Cert-Erneuerung auf frischem Host getestet (R3)

## Audit + Compliance

- [x] `AuditLogService` + PII-Filter + Export
- [x] Audit-Report-Builder + Export-Ziele (`audit_report*.py`)
- [x] Audit-Export mit Redaction fuer Secrets in CSV/JSON validieren (R3) — `AUDIT_EXPORT_REDACTION_SMOKE=PASS` auf `srv1` (2026-04-30, events_checked=262)
- [x] Datenschutz-Doku fuer Pilotkunden (DSGVO/Auftragsverarbeitung) (R4) — `docs/runbooks/dsgvo-avv-pilot.md` deckt Datenarten, TOMs, Betroffenenrechte, Meldepflicht und VVT-Vorlage ab (2026-05-02 Docs-Triage)

## Console + noVNC Tokens

- [x] Console-Tokens TTL + Scope + Audit-Trail
- [x] Browser-Smoke: noVNC-Token verfaellt nach TTL und ist scope-gebunden (R3) — `NOVNC_TOKEN_TTL_SMOKE=PASS` auf `srv1` (2026-04-30, ttl=30s, used+expired pruning validiert)

## Subprocess Sandboxing

- [x] `core/exec/` Wrapper mit allowlist + timeout (`docs/archive/goadvanced/04-subprocess-sandboxing.md`)
- [x] CI-Guard `security-subprocess-check.yml` aktiv
- [x] Smoke: VM-Start ueber API + Netzwerk-Operationen ueber CLI ohne sandbox-bypass (R3) — `SUBPROCESS_SANDBOX_SMOKE=PASS` auf `srv1` (2026-04-30)

## Security-Findings Backlog

- [x] Alle offenen Findings in `docs/refactor/11-security-findings.md` auf `PATCHED` oder akzeptiertes Restrisiko (R3) — alle 40 Findings PATCHED oder accepted (S-001..S-040)
- [ ] Externer Security-Review / Penetrationstest ohne kritische Findings (R4)
