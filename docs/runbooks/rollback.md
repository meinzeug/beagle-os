# Runbook — Rollback

**Status**: Skelett · **Letzte Validierung**: —

Ziel: Eine fehlgeschlagene Installation oder ein fehlgeschlagenes Update sicher
auf den letzten bekannten guten Zustand zuruecksetzen.

## 1. Entscheidung: Wann rollback?

- Smoke-Test nach Update ([`update.md`](update.md) §4) schlaegt fehl
- Kritische Audit-/Auth-/RBAC-Funktion gebrochen
- Datenintegritaet verdaechtig (DB-Errors, Inkonsistenzen)

Nicht rollback (sondern fix-forward): kosmetische UI-Fehler, einzelne nicht-kritische API-Endpoints.

## 2. Voraussetzungen

- [ ] Snapshot/Restore-Punkt aus §1 von [`update.md`](update.md) verfuegbar
- [ ] Backup nach [`backup-restore.md`](backup-restore.md) verfuegbar
- [ ] Vorheriges Release-Artefakt + SHA256SUMS verfuegbar

## 3. Rollback-Strategien (in Reihenfolge der Praeferenz)

### A) Storage-Snapshot

1. Control-Plane stoppen.
2. ZFS/LVM-Snapshot zurueckrollen (TBD, hostspezifisch dokumentieren).
3. Control-Plane starten, Smoke-Tests fahren.

### B) Paket-Downgrade

1. Update-Pakete deinstallieren.
2. Vorgaenger-Version per `apt`/`dnf` installieren.
3. Schema-Downgrade-Migration laufen lassen (sofern vorhanden — sonst aus Backup).

### C) Vollstaendige Wiederherstellung aus Backup

1. Frisch installieren nach [`installation.md`](installation.md) mit Vorversion.
2. Backup nach [`backup-restore.md`](backup-restore.md) zurueckspielen.

## 4. Smoke-Tests nach Rollback

- [ ] `cat /opt/beagle/VERSION` zeigt Vorversion
- [ ] Login + Dashboard ohne Console-Fehler
- [ ] Alle VMs sind im erwarteten Zustand

## 5. Befund-Felder

- Datum / Operator / Host:
- Strategie (A/B/C):
- Ursache des Updates-Fehlschlags:
- Datenverlust (ja/nein, Umfang):
- Folgemassnahmen / Bug-Tickets:
