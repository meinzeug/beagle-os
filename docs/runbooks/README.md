# Beagle OS — Runbooks

Operative Anleitungen fuer wiederkehrende und kritische Vorgaenge im
Produktivbetrieb. Pflicht-Lektuere fuer Operatoren vor Pilotbetrieb (R4).

| Runbook | Zweck | Status |
|---|---|---|
| [installation.md](installation.md) | Bare-Metal- und Hetzner-Installation eines neuen Hosts | Skelett |
| [update.md](update.md) | Update einer laufenden Beagle-OS-Installation | Skelett |
| [rollback.md](rollback.md) | Zurueckrollen auf eine frueher installierte Version | Skelett |
| [backup-restore.md](backup-restore.md) | VM-Backup, Restore, Single-File-Restore | Skelett |
| [incident-response.md](incident-response.md) | Reaktion auf Stoerungen und Sicherheitsvorfaelle | Skelett |
| [pilot.md](pilot.md) | Anleitung fuer Pilotkunden (Onboarding bis Tagesbetrieb) | Skelett |

Status-Legende: **Skelett** = Struktur vorhanden, Befehle/Output fehlen ·
**Entwurf** = erste Version mit echten Befehlen, ungetestet · **Validiert** =
mindestens 1x auf echter Hardware ausgefuehrt + Befund eingetragen.

Wenn ein Runbook validiert wird, wird der Befund zusaetzlich in
[`../checklists/05-release-operations.md`](../checklists/05-release-operations.md)
auf `[x]` gesetzt.
