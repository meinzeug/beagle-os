# 16 — 7.3.0 Backup + Disaster Recovery

Stand: 2026-04-20  
Priorität: 7.3 (H1 2028)  
Referenz: `docs/refactorv2/09-backup-dr.md`

---

## Schritte

### Schritt 1 — Backup-Architektur und Ziel-Backend entscheiden

- [x] In `docs/refactor/07-decisions.md` entscheiden: qcow2-Deltas / ZFS-Snapshots / Restic / PBS-kompatibel.
- [x] PoC: qcow2-inkrementelles Backup mit `qemu-img convert` + Restic für Deduplikation.

Backup ist die kritischste Datensicherungs-Funktion der Plattform und muss eine klare
technische Grundlage haben. qcow2-Snapshots + inkrementelle Deltas (`qemu-img bitmaps`)
sind der naheliegendste Ansatz für QEMU-VMs. Restic als Storage-Layer bietet content-
adressierbare Deduplikation die bei ähnlichen Pool-VMs massiven Speicherplatz spart.
PBS-Kompatibilität (Proxmox Backup Server) würde die Integration mit bestehenden
Proxmox-Deployments erleichtern. Der PoC validiert Backup-Geschwindigkeit, Restore-Zeit
und Speicherplatz-Overhead für eine typische 80 GB Desktop-VM.

Umsetzung (2026-04-23):

- Architekturentscheidung in `docs/refactor/07-decisions.md` dokumentiert (`D-042`):
	- Primärpfad für 7.3: qcow2-Export via `qemu-img convert` + Restic-Dedupe,
	- ZFS-Snapshots als optionaler Fast-Path,
	- PBS-Kompatibilität via Export-/Import-Adapter statt Proxmox-Kopplung.
- Reproduzierbarer PoC ergänzt: `scripts/test-backup-qcow2-restic-poc.sh`.
	- erstellt qcow2-Source-Disk,
	- sichert über `qemu-img convert` in ein Arbeitsartefakt,
	- führt zwei Restic-Backups aus,
	- prüft, dass die zweite Sicherung weniger neue Daten hinzufügt (Dedupe-Nachweis).

Validierung (2026-04-23):

- Live auf `srv1.beagle-os.com` erfolgreich: `BACKUP_QCOW2_RESTIC_POC=PASS`.
- Gemessene Restic-Dedupe-Metrik im PoC:
	- `first_added=17106935`
	- `second_added=8719212`
	- `ratio=0.5097` (Dedupe sichtbar; Optimierungsziel `<10%` bleibt Testpflicht von Schrittabschluss).

---

### Schritt 2 — Backup-Service mit Scheduling implementieren

- [x] `beagle-host/services/backup_service.py` anlegen mit Backup-Jobs und Scheduling.
- [x] Web Console: Backup-Policy pro Pool/VM (Zeitplan, Retention).

Der Backup-Service verwaltet Backup-Jobs und führt sie nach Zeitplan aus. Jeder
Pool und jede VM kann eine eigene Backup-Policy haben: Backup-Zeitplan (Cron-Ausdruck),
Backup-Typ (full/incremental), Retention-Strategie (letzte N Backups / letzte N Tage).
Ein Background-Worker verarbeitet die Backup-Queue und führt Backups sequenziell aus
um Storage-I/O-Überlastung zu vermeiden. Der Web Console zeigt den Status aller
laufenden und letzten vergangenen Backup-Jobs. Backup-Fehler erzeugen Alerts und
Audit-Events.

Umsetzung (2026-04-23):

- Neuer Service `beagle-host/services/backup_service.py` mit:
	- Pool-/VM-spezifischen Backup-Policies (`enabled`, `schedule`, `retention_days`, `target_path`, `last_backup`),
	- Job-Historie (`job_id`, `status`, `archive`, `error`, Zeitstempel),
	- `run_backup_now(scope_type, scope_id)` und `run_scheduled_backups()`.
- Control-Plane verdrahtet (`beagle-host/bin/beagle-control-plane.py`):
	- GET ` /api/v1/backups/policies/pools/{pool_id}`,
	- GET ` /api/v1/backups/policies/vms/{vmid}`,
	- PUT ` /api/v1/backups/policies/pools/{pool_id}`,
	- PUT ` /api/v1/backups/policies/vms/{vmid}`,
	- POST ` /api/v1/backups/run`,
	- GET ` /api/v1/backups/jobs`.
- Background-Scheduler-Thread im Control-Plane ergänzt (`BEAGLE_BACKUP_SCHEDULER_INTERVAL_SECONDS`, Default 300s).
- RBAC-Mapping ergänzt: neue Backup-Routen laufen über `settings:read` / `settings:write`.
- Web Console Backup-Panel erweitert (`website/index.html`, `website/ui/settings.js`):
	- Scope-Auswahl (`pool|vm`) + Scope-ID,
	- Policy laden/speichern pro Scope,
	- `Jetzt sichern` pro Scope,
	- Job-Tabelle mit Status/Start/Ende/Ergebnis.
- Reproduzierbarer Live-Smoke ergänzt: `scripts/test-backup-scope-smoke.sh`.

Validierung (2026-04-23):

- Lokal:
	- `pytest -q tests/unit/test_backup_service.py tests/unit/test_authz_policy.py` => `11 passed`.
	- `bash -n scripts/test-backup-scope-smoke.sh` => `SCRIPT_SYNTAX=PASS`.
- Live auf `srv1.beagle-os.com`:
	- Service-Restart `beagle-control-plane.service` erfolgreich (`active`).
	- Backup-API-Smoke erfolgreich: `BACKUP_SCOPE_SMOKE=PASS`.
	- Endpunkte `PUT/GET policy`, `POST run`, `GET jobs` liefern jeweils `HTTP 200` und `ok=true`.

---

### Schritt 3 — Backup-Targets: lokal, NFS, S3 implementieren

- [ ] `BackupTarget`-Protokoll in `core/` definieren: `write_chunk`, `read_chunk`, `list_snapshots`.
- [ ] Implementierungen: `LocalBackupTarget`, `NfsBackupTarget`, `S3BackupTarget`.

Mehrere Backup-Targets ermöglichen das 3-2-1-Backup-Prinzip: 3 Kopien, 2 verschiedene
Medien, 1 offsite. Der `LocalBackupTarget` speichert direkt auf dem Host-Dateisystem.
Der `NfsBackupTarget` schreibt auf ein gemountetes NFS-Share. Der `S3BackupTarget`
nutzt die S3-API (kompatibel mit AWS S3, Minio, Backblaze B2). Verschlüsselung der
Backup-Daten auf S3 ist Pflicht (AES-256 client-side). Die Target-Konfiguration
(URL, Credentials) wird in der Web Console eingegeben und niemals im Klartext geloggt.

---

### Schritt 4 — Live-Restore implementieren

- [ ] API: `POST /api/v1/backups/{snapshot_id}/restore` mit Ziel-VM oder neuer VM.
- [ ] Web Console: Restore-Dialog in der VM-Detailansicht.

Live-Restore bedeutet dass eine VM aus einem Backup wiederhergestellt wird mit minimaler
Downtime. Der Restore-Prozess: VM stoppen (falls laufend), Disk-Image aus Backup
rekonstruieren (Deltas zurückrollen), VM neu starten. Der Restore-Dialog erlaubt
die Wahl zwischen "als ursprüngliche VM restoren" (destructive, bestehende Disk wird
überschrieben) oder "als neue VM restoren" (non-destructive, neue VM wird angelegt).
Ein Progress-Dialog zeigt den Restore-Fortschritt in GB/s und Prozent. Bei Fehler
bleibt die ursprüngliche VM unverändert (atomarer Restore).

---

### Schritt 5 — Single-File-Restore über guestfs-Mount

- [ ] `backup_service.py` bekommt `mount_snapshot`-Methode: Snapshot als virtuelles Dateisystem mounten.
- [ ] Web Console: File-Browser im Snapshot-Context (read-only).

Single-File-Restore ist für den häufigen Anwendungsfall "Nutzer hat versehentlich
eine Datei gelöscht" gedacht und gespart einen vollständigen VM-Restore. `libguestfs`
(Python-Bindings `guestfs`) ermöglicht das Mounten eines qcow2-Snapshots als Loopback
ohne einen vollständigen Boot. Der gemountete Snapshot erscheint als virtuelles
Dateisystem das über die Web Console browse-bar ist. Ein "Datei herunterladen"-Button
ermöglicht den Download einzelner Dateien. Das Mount läuft read-only und zeitlich
begrenzt (maximale Mount-Dauer konfigurierbar, Default 30 Minuten).

---

### Schritt 6 — Cross-Site-Replication

- [ ] `backup_service.py` bekommt `replicate_to_remote`-Methode: Backup-Replikation auf entfernten Beagle-Cluster.
- [ ] Konfiguration: Remote-Cluster-URL, API-Key, Replikations-Policy.

Cross-Site-Replication ist die Grundlage für Disaster Recovery. Nach einem lokalen
Backup wird ein Satz von Snapshots asynchron auf einen Remote-Beagle-Cluster übertragen.
Der Remote-Cluster ist ein zweiter Beagle-Server an einem anderen Standort. Die
Replication läuft nach Backup-Abschluss und überträgt nur neue/geänderte Chunks
(Deduplizierung). Im DR-Fall kann der Remote-Cluster als Ziel für den Restore gewählt
werden. Die Verbindung zum Remote-Cluster ist TLS-gesichert und mit API-Key
authentifiziert. Replikations-Fehler werden als kritische Alerts behandelt.

---

## Testpflicht nach Abschluss

- [ ] Inkrementelles Backup: zweites Backup dauert weniger als 10% des ersten Backups.
- [ ] Full-Restore einer 80 GB VM: <= 5 Minuten auf lokalem NVMe.
- [ ] Single-File-Restore: Datei aus 7-Tage-altem Snapshot heruntergeladen.
- [ ] S3-Backup: Chunks in Minio-Bucket verschlüsselt gespeichert.
- [ ] Retention: nach Ablauf werden alte Snapshots gelöscht, Audit-Event vorhanden.
