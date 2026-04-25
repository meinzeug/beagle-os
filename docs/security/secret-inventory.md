# Secret Inventory — Beagle OS Control Plane

**Stand**: 2026-04-25
**Bezug**: GoAdvanced Plan 03 — S-003

Alle Secrets die von `beagle-control-plane.py` aus Umgebungsvariablen gelesen werden.
Neue Instanzen sollen über `SecretStoreService` verwaltet werden (auto-generiert bei erstem Start).

---

## Tabelle: Alle Control-Plane-Secrets

| Name                               | Env-Var                              | Zweck                                                        | TTL empfohlen | Rotation-Trigger              | Verwendet von                        | Online-Rotation |
|------------------------------------|--------------------------------------|--------------------------------------------------------------|---------------|-------------------------------|--------------------------------------|-----------------|
| `manager-api-token`                | `BEAGLE_MANAGER_API_TOKEN`           | Bearer-Token für direkte API-Aufrufe (Provisioning, CLI)     | 90 Tage       | Kompromittierung, Deployment  | API-Auth-Middleware                  | Ja (grace 24h)  |
| `auth-bootstrap-password`          | `BEAGLE_AUTH_BOOTSTRAP_PASSWORD`     | Initiales Admin-Passwort (einmaliger Bootstrap)              | Einmalig      | Nach erstem Login ändern      | `AuthSessionService`                 | Nein            |
| `scim-bearer-token`                | `BEAGLE_SCIM_BEARER_TOKEN`           | SCIM-Provisioning-Token (IdP → Beagle)                       | 180 Tage      | IdP-Rotation, Kompromittierung| SCIM-Endpunkte `/api/v1/scim/`       | Ja (grace 24h)  |
| `pairing-token-secret`             | `BEAGLE_PAIRING_TOKEN_SECRET`        | HMAC-Schlüssel für Pairing-Token-Signierung                  | 180 Tage      | Deployment, Kompromittierung  | Thin-Client-Pairing                  | Nein (Restart)  |
| `audit-webhook-secret`             | `BEAGLE_AUDIT_EXPORT_WEBHOOK_SECRET` | HMAC-Secret für Webhook-Signierung (Audit-Export)            | 365 Tage      | Webhook-Empfänger-Rotation    | `AuditExportService`                 | Ja (grace 1h)   |
| `audit-s3-access-key`              | `BEAGLE_AUDIT_EXPORT_S3_ACCESS_KEY`  | S3 Access Key für Audit-Export                               | 90 Tage       | IAM-Rotation                  | `AuditExportService`                 | Ja              |
| `audit-s3-secret-key`              | `BEAGLE_AUDIT_EXPORT_S3_SECRET_KEY`  | S3 Secret Key für Audit-Export                               | 90 Tage       | IAM-Rotation                  | `AuditExportService`                 | Ja              |
| `recording-s3-access-key`          | `BEAGLE_RECORDING_S3_ACCESS_KEY`     | S3 Access Key für Session-Recordings                         | 90 Tage       | IAM-Rotation                  | Recording-Speicher                   | Ja              |
| `recording-s3-secret-key`          | `BEAGLE_RECORDING_S3_SECRET_KEY`     | S3 Secret Key für Session-Recordings                         | 90 Tage       | IAM-Rotation                  | Recording-Speicher                   | Ja              |

---

## Migrationsstatus

| Secret                    | Status            | Notiz                                                                 |
|---------------------------|-------------------|-----------------------------------------------------------------------|
| `manager-api-token`       | ✅ SecretStore    | Auto-generiert bei erstem Start, Env-Override weiterhin unterstützt  |
| `auth-bootstrap-password` | ⚠️ Env-only       | Einmaliger Bootstrap — kein SecretStore-Bedarf                       |
| `scim-bearer-token`       | 🔲 Geplant        | Rotation-CLI implementiert, SecretStore-Wiring TODO                  |
| `pairing-token-secret`    | 🔲 Geplant        | Restart erforderlich nach Rotation                                    |
| `audit-webhook-secret`    | 🔲 Geplant        | Rotation ohne Restart möglich                                         |
| `audit-s3-access-key`     | 🔲 Extern         | IAM-seitig rotiert, kein internes Auto-Rotate                        |
| `audit-s3-secret-key`     | 🔲 Extern         | IAM-seitig rotiert, kein internes Auto-Rotate                        |
| `recording-s3-access-key` | 🔲 Extern         | IAM-seitig rotiert, kein internes Auto-Rotate                        |
| `recording-s3-secret-key` | 🔲 Extern         | IAM-seitig rotiert, kein internes Auto-Rotate                        |

---

## Fragen pro Secret: Online-Rotation möglich?

- **manager-api-token**: Ja — grace period 24h, API-Clients bekommen neuen Token via CLI/Webhook
- **auth-bootstrap-password**: Nein — wird nur beim ersten Start verwendet; Admin ändert danach manuell
- **scim-bearer-token**: Ja — IdP-seitig und Beagle-seitig koordiniert rotieren; grace period nötig
- **pairing-token-secret**: Nein — ist HMAC-Signing-Key; alle aktiven Pairing-Tokens werden ungültig; Restart nötig
- **audit-webhook-secret**: Ja — neues Secret an Webhook-Empfänger kommunizieren, dann rotieren (grace 1h)
