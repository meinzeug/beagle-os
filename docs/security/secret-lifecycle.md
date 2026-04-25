# Secret Lifecycle — Beagle OS

**Stand**: 2026-04-25
**Bezug**: GoAdvanced Plan 03, S-003

---

## Übersicht

Alle Beagle-Secrets werden durch `SecretStoreService` verwaltet:
- JSON-Backend unter `/var/lib/beagle/secrets/<name>.json` (mode 0o600)
- Versionierung: alte Version bleibt 24h gültig nach Rotation (Grace Period)
- Audit-Events für jeden Zugriff, jede Rotation, jede Revocation
- Kein Secret-Wert in Logs oder API-Antworten

---

## Empfohlene TTLs

| Secret-Typ                  | Empfohlene TTL | Grace Period |
|-----------------------------|----------------|--------------|
| API-Token (machine-to-machine) | 90 Tage     | 24h          |
| SCIM-Bearer-Token           | 180 Tage       | 24h          |
| Webhook-Signing-Secret      | 365 Tage       | 1h           |
| HMAC-Key (Pairing-Token)    | 180 Tage       | Restart req. |
| S3-Keys (extern verwaltet)  | 90 Tage        | extern       |

---

## Standard-Rotation-Procedure

```bash
# 1. Neuen Token generieren (auto-generiert wenn kein --value angegeben)
beaglectl secret rotate manager-api-token

# 2. Alten Token bleibt 24h gültig (Grace Period) — Clients können migrieren
# 3. Nach 24h ist alter Token ungültig

# Rotation mit eigenem Wert:
beaglectl secret rotate manager-api-token --value "my-new-token"

# Liste aller Secrets (keine Werte):
beaglectl secret list

# Version explizit revoken (sofortig, keine Grace Period):
beaglectl secret revoke manager-api-token 1
```

---

## Notfall-Revocation

Bei Kompromittierung eines Secrets:

```bash
# 1. Sofortige Revocation (kein Grace Period!)
beaglectl secret revoke <name> <version>

# 2. Neues Secret setzen
beaglectl secret rotate <name>

# 3. Audit-Log prüfen
journalctl -u beagle-control-plane | grep "secret_accessed\|secret_rotated\|secret_revoked"
```

**Wichtig**: Revocation ist sofort wirksam — KEIN Grace Period.
Erst rotieren wenn neue Clients konfiguriert sind, dann revoken.

---

## Auto-Bootstrap (erster Start)

Beim ersten Start von `beagle-control-plane` ohne gesetztes `BEAGLE_MANAGER_API_TOKEN`:

1. `SecretStoreService` prüft ob `secrets/manager-api-token.json` existiert
2. Falls nicht: generiert `secrets.token_hex(32)` (64-Hex-Zeichen)
3. Speichert in SecretStore (mode 0o600)
4. Loggt ins Journal: `[BEAGLE BOOTSTRAP] Generated manager-api-token — retrieve with: beaglectl secret get manager-api-token`
5. **Kein Klartext-Wert in Logs**

---

## Secret-Zugriff durch die Control Plane

Die Control Plane lädt Secrets in dieser Priorität:

1. **Env-Var** (Override, für Deployments mit externem Secret-Manager)
2. **SecretStoreService** (Standard, auto-generiert bei erstem Start)
3. **Fehler** wenn weder Env noch SecretStore das Secret enthält (nur für nicht-optionale Secrets)

---

## Audit-Events

Alle Secret-Operationen werden in `/var/lib/beagle/beagle-manager/audit.log` geschrieben:

```json
{"action":"secret_accessed","result":"ok","details":{"name":"manager-api-token","version":1}}
{"action":"secret_rotated","result":"ok","details":{"name":"manager-api-token","new_version":2}}
{"action":"secret_revoked","result":"ok","details":{"name":"manager-api-token","version":1}}
```

**Werte werden NIEMALS in Audit-Logs geschrieben.**

---

## Sicherheitsanforderungen

- Alle Secret-Dateien: mode 0o600 (nur root/beagle)
- Verzeichnis `/var/lib/beagle/secrets/`: mode 0o700
- Keine Secret-Werte in API-Responses, Logs, Audit-Events
- Rotation-CLI erfordert root oder beagle-admin Rolle
- Secret-Dateien werden NICHT in Backups/Snapshots eingeschlossen (exclude in backup_service.py)
