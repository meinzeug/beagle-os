# Runbook — Incident Response

**Status**: Skelett · **Letzte Validierung**: —

Ziel: Strukturierte Reaktion auf Stoerungen und Sicherheitsvorfaelle in einer
Beagle-OS-Installation.

## 1. Klassifikation

| Severity | Definition | Reaktionszeit | Beispiele |
|---|---|---|---|
| SEV-1 | Komplettausfall oder Sicherheitsvorfall mit Datenabfluss | < 30 min | Control-Plane down, kompromittierter Admin-Account |
| SEV-2 | Teilausfall oder unbestaetigter Sicherheitsverdacht | < 2 h | Streaming fuer einzelne Pools weg, ungewoehnlicher Login |
| SEV-3 | Funktional eingeschraenkt, nicht zeitkritisch | < 1 Tag | Einzelne UI-Funktion defekt |
| SEV-4 | Kosmetisch | naechster Sprint | UI-Glitch ohne Funktionsverlust |

## 2. Sofortmassnahmen (alle Severities)

1. Vorfall im Incident-Log eintragen (Datum, Severity, beschreibender Titel).
2. Bei Sicherheitsvorfall: betroffene Sessions invalidieren (`beaglectl session revoke --all` bei SEV-1).
3. Audit-Log sichern: `beaglectl audit export --since <timestamp> --target <secure-location>`.

## 3. SEV-1 Sicherheitsvorfall — Vorgehen

1. **Containment**: betroffene Hosts vom Netz nehmen (oder API-Zugriff sperren via nftables).
2. **Forensik**: vollstaendigen Audit-Log-Export + State-Snapshot sichern, **bevor** etwas geaendert wird.
3. **Eradication**: kompromittierte Credentials rotieren (`beaglectl secret rotate --all`).
4. **Recovery**: nach [`backup-restore.md`](backup-restore.md) auf sauberen Stand zuruecksetzen.
5. **Post-Mortem**: dokumentieren in `docs/refactor/11-security-findings.md` mit Status `INCIDENT`.

## 4. SEV-1 Komplettausfall — Vorgehen

1. Health-Endpoints pruefen: `https://<host>/healthz`, `systemctl status beagle-control-plane`.
2. Logs: `journalctl -u beagle-control-plane -n 200`.
3. Storage-Fuellstand: `df -h /var/lib/beagle/`.
4. Bei nicht-trivialer Ursache: nach [`rollback.md`](rollback.md) auf letzte gute Version zuruecksetzen.

## 5. Eskalation

| Stufe | Empfaenger | Mittel |
|---|---|---|
| 1 | On-Call Operator | Pager / Webhook |
| 2 | Tech-Lead | Telefon |
| 3 | Security-Officer (bei SEV-1 Sicherheit) | Telefon |

Eskalations-Kontakte werden **nicht** in dieser Datei dokumentiert (keine PII im
Repo). Operator-Hinweise liegen lokal beim Betreiber.

## 6. Post-Mortem Template

- Was ist passiert (Faktenlage)?
- Wann war es bemerkt? Wann eskaliert? Wann gemildert?
- Welche Daten/Systeme waren betroffen?
- Root cause (Five Whys)?
- Was hat funktioniert?
- Was hat **nicht** funktioniert?
- Konkrete Folgemassnahmen mit Eigentuemer und Termin
