# Runbook — Backup + Restore

**Status**: Skelett · **Letzte Validierung**: —

Ziel: Vollstaendiges Backup einer Beagle-OS-Installation inkl. Control-Plane-State,
Audit-Log, Secret-Store und VM-Disks. Restore auf einem zweiten Host.

## 1. Was wird gesichert

| Datenklasse | Pfad | Frequenz |
|---|---|---|
| Control-Plane-State (JSON) | `/var/lib/beagle/state/` | stuendlich (oder bei jeder Aenderung) |
| Audit-Log | `/var/lib/beagle/audit/` | stuendlich |
| Secret-Store | `/var/lib/beagle/secrets/` (mode 0o600) | bei jeder Aenderung |
| Konfiguration | `/etc/beagle/` | bei jeder Aenderung |
| TLS-Zertifikate + Schluessel | `/etc/beagle/tls/` (mode 0o600) | bei jeder Aenderung |
| VM-Disks | abhaengig vom Storage-Backend (LVM/ZFS/Pfad) | nach Schedule |
| VM-Definitions (libvirt XML) | `/etc/libvirt/qemu/` | bei jeder Aenderung |

## 2. Backup-Verfahren

### A) Control-Plane-Daten

```
beaglectl backup create --target <s3|nfs|local> --include state,audit,secrets,config,tls
```

Output enthaelt mindestens Job-ID, Archivpfad/-Referenz, Zeitstempel und
`archive_sha256`. Restore-Pfade muessen vor dem Einspielen gegen diesen Hash
verifiziert werden.

### B) VM-Backup

```
beaglectl vm backup --vmid <id> --target <s3|nfs|local> [--incremental]
```

## 3. Restore-Verfahren (auf zweitem Host)

1. Host nach [`installation.md`](installation.md) frisch installieren.
2. Backup-Manifest auf den Host kopieren.
3. Hash-Verifikation: `sha256sum <archive>` muss `archive_sha256` aus dem Backup-Job/Manifest entsprechen.
4. Restore: `beaglectl backup restore --manifest <path> --include state,audit,secrets,config,tls`.
5. VM-Disks zurueckspielen: `beaglectl vm restore --vmid <id> --manifest <path>`.
6. Control-Plane neu starten.

## 4. Single-File-Restore aus VM-Backup

```
beaglectl vm backup mount --vmid <id> --backup <id> --mountpoint /mnt/restore
# Datei kopieren
beaglectl vm backup umount --mountpoint /mnt/restore
```

## 5. Smoke-Tests nach Restore

- [ ] `cat /opt/beagle/VERSION` zeigt Quell-Version
- [ ] Login mit dem urspruenglichen Admin-Account funktioniert
- [ ] Audit-Log enthaelt vollstaendige Historie der Quellinstallation
- [ ] Restorede VM startet und ist erreichbar
- [ ] Hash-Vergleich zwischen Quell- und Ziel-Disk OK (`sha256sum` auf Datei-Ebene oder via `beaglectl vm verify`)
- [ ] Restore lehnt manipulierte Archive mit absoluten Pfaden, `..`-Pfaden oder unsicheren Symlinks ab.

## 6. Cross-Site Disaster Recovery

Wenn ein zweiter Standort vorhanden ist:

- [ ] Backup-Ziele liegen ausserhalb des Quellstandorts (Off-Site S3 / zweites Rechenzentrum)
- [ ] Mind. 1 vollstaendiger Restore-Test pro Quartal (in `checklists/05-release-operations.md` eintragen)

## 7. Befund-Felder

- Datum / Operator / Quell-Host / Ziel-Host:
- Daten-Volumen:
- Backup-Dauer / Restore-Dauer:
- Hash-Match (ja/nein):
