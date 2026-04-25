# Plan 03 — Secret-Management: Rotation, Vault, Audit

**Dringlichkeit**: HIGH
**Welle**: A (Sofort)
**Audit-Bezug**: S-003

## Problem

Secrets werden aktuell beim Start aus Environment-Variablen geladen (`BEAGLE_MANAGER_API_TOKEN`, `BEAGLE_AUTH_BOOTSTRAP_PASSWORD`, `BEAGLE_SCIM_BEARER_TOKEN`, `BEAGLE_PAIRING_TOKEN_SECRET`, `BEAGLE_AUDIT_EXPORT_WEBHOOK_SECRET` u.a. in `beagle-host/bin/beagle-control-plane.py:149-172`).

Probleme:

- Keine dokumentierte Rotations-Strategie
- Bootstrap-Passwort kann aus API-Token abgeleitet werden
- Kein Secret-Versioning (alte Tokens bleiben unbegrenzt gueltig, wenn sie geleakt sind)
- Kein Audit-Eintrag, wenn Secrets neu erstellt oder verwendet werden

## Ziel

1. Klar dokumentierter Secret-Lifecycle (Erzeugung, Rotation, Revocation).
2. Optionales File-basiertes Secret-Backend mit Versioning.
3. Audit-Log fuer alle Secret-Operationen.
4. Default-Secrets werden bei erstem Start automatisch generiert (nie hartcodiert).

## Schritte

- [ ] **Schritt 1** — Secret-Inventur
  - [ ] `docs/security/secret-inventory.md` erstellen mit Tabelle:
    - Name | Zweck | TTL | Rotation-Trigger | Verwendet von
  - [ ] Mind. erfassen: alle BEAGLE_*-Env-Vars in `beagle-control-plane.py`
  - [ ] Pro Secret: kann es zur Laufzeit rotiert werden ohne Service-Restart?

- [x] **Schritt 2** — `SecretStoreService`
  - [ ] `beagle-host/services/secret_store_service.py` neu
  - [ ] API:
    - `get_secret(name) -> SecretValue`  (mit `version`, `created_at`, `expires_at`)
    - `rotate_secret(name) -> SecretValue` (erzeugt neue Version, markiert alte als `superseded`)
    - `revoke_secret(name, version)` (sofort ungueltig)
    - `list_secrets() -> list[SecretMeta]` (ohne Werte!)
  - [ ] Backend (Phase 1): JSON unter `/var/lib/beagle/secrets/` (mode 0o600), via `JsonStateStore` aus Plan 01
  - [ ] Backend (Phase 2 — optional): HashiCorp Vault, AWS Secrets Manager (via Adapter)
  - [ ] Tests: `tests/unit/test_secret_store.py`
    - [ ] get/set Round-Trip
    - [ ] Rotation: alte Version bleibt 24h valid (Grace-Period)
    - [ ] Revocation: sofort ungueltig
    - [ ] Permissions auf Secret-File 0o600

- [ ] **Schritt 3** — Auto-Bootstrap
  - [ ] Beim ersten Start von `beagle-control-plane`: wenn `secrets/manager-api-token.json` fehlt → `secrets.token_hex(32)` generieren, in SecretStore ablegen, Operator-Hinweis ins Journal loggen (NICHT in Datei)
  - [ ] Env-Vars werden weiterhin als Override unterstuetzt (Backwards-kompat), aber Standard ist SecretStore
  - [ ] Tests: `tests/unit/test_secret_bootstrap.py`

- [ ] **Schritt 4** — Audit-Integration
  - [ ] Jeder `get_secret(name)`-Aufruf erzeugt Audit-Event `secret_accessed` (nur Name + Version, NICHT Wert)
  - [ ] `rotate_secret` / `revoke_secret` erzeugen `secret_rotated` / `secret_revoked` Events
  - [ ] Audit-Log via existierendem `AuditLogService`
  - [ ] Tests: pruefen, dass keine Klartext-Werte in Audit-Logs landen

- [ ] **Schritt 5** — Rotation-CLI
  - [ ] `scripts/beaglectl.py secret rotate <name>` Subcommand
  - [ ] `scripts/beaglectl.py secret list` (zeigt nur Metadaten)
  - [ ] `scripts/beaglectl.py secret revoke <name> <version>`

- [ ] **Schritt 6** — Web-UI
  - [ ] `website/ui/secrets_admin.js` neu — Liste aller Secrets, Rotate-Button, Last-Rotated-Anzeige
  - [ ] RBAC: nur Rolle `security_admin` darf Secrets verwalten
  - [ ] Werte werden NIE im UI angezeigt — nur "rotiert am ...", "naechste Rotation faellig am ..."

- [ ] **Schritt 7** — Dokumentation
  - [ ] `docs/security/secret-lifecycle.md`: empfohlene TTLs, Rotation-Procedure, Notfall-Revocation
  - [ ] Update `docs/refactor/11-security-findings.md`: S-003 als geloest markieren

## Abnahmekriterien

- [ ] `SecretStoreService` mit JSON-Backend produktiv.
- [ ] Mind. 5 Secrets via SecretStore verwaltet (nicht mehr nur Env).
- [ ] Audit-Event fuer jeden Secret-Access.
- [ ] CLI funktioniert auf `srv1.beagle-os.com`.
- [ ] Doku in `docs/security/secret-lifecycle.md` vorhanden.

## Risiko

- Bei Migration von Env zu SecretStore: bestehende Deployments duerfen nicht brechen → Env-Override bleibt waehrend Uebergangszeit.
- Audit-Log darf selbst kein Secret-Material enthalten (Tests mussen pruefen).
