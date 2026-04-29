# Runbook — Update

**Status**: Skelett · **Letzte Validierung**: —

Ziel: Eine produktive Beagle-OS-Installation auf eine neue Version heben, ohne
Datenverlust und mit definierter Rollback-Strategie.

## 1. Vor dem Update

- [ ] Release-Notes der Zielversion gelesen (Breaking Changes, Migrations)
- [ ] Vollstaendiges Backup nach [`backup-restore.md`](backup-restore.md) erstellt + verifiziert
- [ ] Wartungsfenster angekuendigt
- [ ] Aktuelle Version notiert: `cat /opt/beagle/VERSION`
- [ ] Snapshot-/Restore-Punkt auf Storage-Ebene gesetzt (ZFS/LVM/btrfs)

## 2. Pakete + Artefakte beziehen

- [ ] `SHA256SUMS` + `SHA256SUMS.sig` (GPG) der neuen Version verifiziert
- [ ] Cosign-Verifikation der Container-/Artefakt-Signaturen erfolgreich

## 3. Update durchfuehren

1. Control-Plane in Drain-Modus (`beaglectl cluster drain --node <self>`).
2. Aktive Streams sauber beenden oder uebergeben (Live Session Handover, falls 2-Node).
3. Update-Skript ausfuehren (TBD, in [`../checklists/05-release-operations.md`](../checklists/05-release-operations.md) verlinken sobald vorhanden).
4. `systemctl daemon-reload && systemctl restart beagle-control-plane.service`.
5. Schema-Migration laufen lassen (sofern vorhanden).
6. Drain aufheben (`beaglectl cluster undrain --node <self>`).

## 4. Smoke-Tests nach Update

- [ ] `cat /opt/beagle/VERSION` zeigt Zielversion
- [ ] `https://<host>/healthz` = `200`
- [ ] Login + Dashboard ohne Console-Fehler
- [ ] Mind. 1 VM lifecycle (start/stop) erfolgreich
- [ ] Alle bestehenden RBAC-Rollen funktionieren weiter
- [ ] Audit-Log enthaelt Update-Events

## 5. Rollback bei Fehlschlag

Wenn einer der Smoke-Tests fehlschlaegt: [`rollback.md`](rollback.md) folgen.

## 6. Befund-Felder

- Datum / Operator / Host:
- Vorversion -> Zielversion:
- Dauer (Drain bis Wiederaufnahme):
- Beobachtete Probleme:
