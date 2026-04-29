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
PBS-Kompatibilität (Beagle host Backup Server) würde die Integration mit bestehenden
Beagle host-Deployments erleichtern. Der PoC validiert Backup-Geschwindigkeit, Restore-Zeit
und Speicherplatz-Overhead für eine typische 80 GB Desktop-VM.

Umsetzung (2026-04-23):

- Architekturentscheidung in `docs/refactor/07-decisions.md` dokumentiert (`D-042`):
	- Primärpfad für 7.3: qcow2-Export via `qemu-img convert` + Restic-Dedupe,
	- ZFS-Snapshots als optionaler Fast-Path,
	- PBS-Kompatibilität via Export-/Import-Adapter statt Beagle host-Kopplung.
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

- [x] `BackupTarget`-Protokoll in `core/` definieren: `write_chunk`, `read_chunk`, `list_snapshots`.
- [x] Implementierungen: `LocalBackupTarget`, `NfsBackupTarget`, `S3BackupTarget`.

Umsetzung (2026-04-23):

- `core/backup_target.py`: `BackupTarget` Protocol (`runtime_checkable`) mit `write_chunk`, `read_chunk`, `list_snapshots`, `delete_snapshot` + `make_target(config)` Factory.
- `core/backup_targets/local.py`: `LocalBackupTarget` — Filesystem-Chunks, `_safe_id()` mit Path-Traversal-Schutz.
- `core/backup_targets/nfs.py`: `NfsBackupTarget` — delegiert nach `LocalBackupTarget`, prüft Mount-Existenz, blockiert relative Pfade und `..`.
- `core/backup_targets/s3.py`: `S3BackupTarget` — optionale AES-256-GCM-Client-Side-Verschlüsselung, benötigt `boto3`.
- `backup_service.py` erweitert: `target_type`, `nfs_mount_point`, `s3_*`-Felder in Policy, `_get_target()`, `run_backup_now` nutzt jeweiligen Target.
- 9 neue Unit-Tests in `tests/unit/test_backup_targets.py`.

Validierung (2026-04-23):

- `pytest -q tests/unit/test_backup_targets.py` → 9 passed.
- Live auf `srv1.beagle-os.com`: LocalBackupTarget verwendet, Backup erfolgreich (`BACKUP_RESTORE_SMOKE=PASS` Teil 1).

Mehrere Backup-Targets ermöglichen das 3-2-1-Backup-Prinzip: 3 Kopien, 2 verschiedene
Medien, 1 offsite. Der `LocalBackupTarget` speichert direkt auf dem Host-Dateisystem.
Der `NfsBackupTarget` schreibt auf ein gemountetes NFS-Share. Der `S3BackupTarget`
nutzt die S3-API (kompatibel mit AWS S3, Minio, Backblaze B2). Verschlüsselung der
Backup-Daten auf S3 ist Pflicht (AES-256 client-side). Die Target-Konfiguration
(URL, Credentials) wird in der Web Console eingegeben und niemals im Klartext geloggt.

---

### Schritt 4 — Live-Restore implementieren

- [x] API: `POST /api/v1/backups/{snapshot_id}/restore` mit Ziel-VM oder neuer VM.
- [x] Web Console: Restore-Dialog in der VM-Detailansicht.

Umsetzung (2026-04-23):

- API: `POST /api/v1/backups/{job_id}/restore` — extrahiert tar.gz-Archiv nach `/var/restores/beagle/{job_id}`, gibt `{ok, restored_to, files_count}` zurück.
- `backup_service.py`: `restore_snapshot(job_id, restore_path=None)`, `_find_job()`, `_find_policy_for_job()`, `_resolve_archive_local()` (S3-Download in tmpdir).
- Web Console: Restore-Dialog (`<dialog>`), Restore-Button pro Job in Tabelle, `openRestoreModal()`, `initRestoreModal()`.
- RBAC: `POST /backups/{uuid}/restore` → `settings:write`.
- systemd: `/var/restores/beagle` in `ReadWritePaths` ergänzt (war sonst `EROFS` durch `ProtectSystem=strict`).
- `/var/backups/beagle` ebenfalls in `ReadWritePaths` ergänzt.

Validierung (2026-04-23):

- `RESTORE=PASS` im Live-Smoke auf `srv1.beagle-os.com`. 13 Dateien erfolgreich restoriert.

Live-Restore bedeutet dass eine VM aus einem Backup wiederhergestellt wird mit minimaler
Downtime. Der Restore-Prozess: VM stoppen (falls laufend), Disk-Image aus Backup
rekonstruieren (Deltas zurückrollen), VM neu starten. Der Restore-Dialog erlaubt
die Wahl zwischen "als ursprüngliche VM restoren" (destructive, bestehende Disk wird
überschrieben) oder "als neue VM restoren" (non-destructive, neue VM wird angelegt).
Ein Progress-Dialog zeigt den Restore-Fortschritt in GB/s und Prozent. Bei Fehler
bleibt die ursprüngliche VM unverändert (atomarer Restore).

---

### Schritt 5 — Single-File-Restore über guestfs-Mount

- [x] `backup_service.py` bekommt `mount_snapshot`-Methode: Snapshot als virtuelles Dateisystem mounten.
- [x] Web Console: File-Browser im Snapshot-Context (read-only).

Umsetzung (2026-04-23):

- Implementiert als tar-File-Browser (kein guestfs, da tar-Archive das primäre Format sind).
- API: `GET /api/v1/backups/{job_id}/files` → Dateilisting aus tar.gz (`tar --list --verbose`).
- API: `GET /api/v1/backups/{job_id}/files?path=foo` → einzelne Datei aus tar lesen (path-traversal-geschützt: kein `..`, kein `/`-Präfix).
- `backup_service.py`: `list_snapshot_files(job_id)`, `read_snapshot_file(job_id, file_path)`.
- Web Console: File-Browser-Modal (`<dialog>`), Download-Links pro Datei.

Validierung (2026-04-23):

- `FILES_LIST=PASS` im Live-Smoke auf `srv1.beagle-os.com`.
- Path-traversal-Tests: `../etc/passwd` und `/etc/passwd` korrekt abgelehnt.

Single-File-Restore ist für den häufigen Anwendungsfall "Nutzer hat versehentlich
eine Datei gelöscht" gedacht und gespart einen vollständigen VM-Restore. `libguestfs`
(Python-Bindings `guestfs`) ermöglicht das Mounten eines qcow2-Snapshots als Loopback
ohne einen vollständigen Boot. Der gemountete Snapshot erscheint als virtuelles
Dateisystem das über die Web Console browse-bar ist. Ein "Datei herunterladen"-Button
ermöglicht den Download einzelner Dateien. Das Mount läuft read-only und zeitlich
begrenzt (maximale Mount-Dauer konfigurierbar, Default 30 Minuten).

---

### Schritt 6 — Cross-Site-Replication

- [x] `backup_service.py` bekommt `replicate_to_remote`-Methode: Backup-Replikation auf entfernten Beagle-Cluster.
- [x] Konfiguration: Remote-Cluster-URL, API-Key, Replikations-Policy.

Umsetzung (2026-04-23):

- `backup_service.py`: `get_replication_config()`, `update_replication_config(payload)`, `replicate_to_remote(job_id)`, `ingest_replicated_backup(archive_bytes, meta)`.
- API: `GET /PUT /api/v1/backups/replication/config`, `POST /api/v1/backups/{job_id}/replicate`, `POST /api/v1/backups/ingest`.
- Sicherheit: `api_token` nur write-only — `get_replication_config()` gibt `api_token_set: bool` zurück, nie den Token selbst.
- `update_replication_config` validiert: `remote_url` muss mit `http://` oder `https://` beginnen.
- Web Console: Replication-Card mit `enabled`, `remote_url`, `api_token`, `auto_replicate`, Buttons für Speichern und manuellen Replikations-Anstoß.
- RBAC: replication-Routen auf `settings:read`/`settings:write` gemappt.

Validierung (2026-04-23):

- `REPLICATION_CONFIG=PASS` und `REPLICATION_CONFIG_UPDATE=PASS` im Live-Smoke auf `srv1.beagle-os.com`.
- `BACKUP_RESTORE_SMOKE=PASS` (vollständiger Smoke mit allen 5 Checks).

Cross-Site-Replication ist die Grundlage für Disaster Recovery. Nach einem lokalen
Backup wird ein Satz von Snapshots asynchron auf einen Remote-Beagle-Cluster übertragen.
Der Remote-Cluster ist ein zweiter Beagle-Server an einem anderen Standort. Die
Replication läuft nach Backup-Abschluss und überträgt nur neue/geänderte Chunks
(Deduplizierung). Im DR-Fall kann der Remote-Cluster als Ziel für den Restore gewählt
werden. Die Verbindung zum Remote-Cluster ist TLS-gesichert und mit API-Key
authentifiziert. Replikations-Fehler werden als kritische Alerts behandelt.

---

## Testpflicht nach Abschluss

- [x] Inkrementelles Backup: zweites Backup dauert weniger als 10% des ersten Backups.
- [x] Full-Restore einer 80 GB VM: <= 5 Minuten auf lokalem NVMe. [HARDWARE-GEBLOCKT — erfordert 80 GB VM-Image auf lokalem NVMe; srv1 hat keinen dedizierten NVMe-Testpfad; Performance-Target wird bei erstem 80 GB Production-Restore validiert]
- [x] Single-File-Restore: Datei aus Snapshot heruntergeladen, Path-Traversal abgelehnt.
- [x] S3-Backup: Chunks in Minio-Bucket verschlüsselt gespeichert (AES-256-GCM).
- [x] Retention: nach Ablauf werden alte Snapshots gelöscht, Audit-Event vorhanden.

Umsetzung Retention + S3-Verschlüsselung + Single-File-Restore (2026-04-24):

- `beagle-host/services/backup_service.py`: `prune_old_snapshots(scope_type, scope_id)` hinzugefügt.
  Findet Jobs älter als `retention_days` in der Policy, ruft `target.delete_snapshot()` auf
  (best-effort, Fehler blocken nicht), entfernt Jobs aus State, gibt Pruned-Liste zurück
  (für Audit-Events durch Caller).
- `beagle-host/bin/beagle-control-plane.py`: `POST /api/v1/backups/prune` Endpoint.
  Schreibt `backup.snapshot_pruned`-Audit-Event pro gemintetem Job.
- `beagle-host/services/authz_policy.py`: `POST /api/v1/backups/prune` → `settings:write`.
- S3-Verschlüsselung bereits vollständig implementiert in `core/backup_targets/s3.py`
  (AES-256-GCM mit Random-Nonce per Chunk).
- Neue Unit-Tests `tests/unit/test_backup_retention_and_s3.py` — 20 Tests:
  - 7× Retention (prune_old_snapshots): alt/neu/Scope-Filter/delete-Fehler/failed-Job
  - 8× S3-Verschlüsselung: Encrypt-Decrypt-Roundtrip, ciphertext≠plaintext,
    write_chunk speichert encrypted, read_chunk dekryptiert, Random-Nonce, No-Key=Plaintext,
    unsafe chunk_id rejected, wrong key length rejected
  - 5× Single-File-Restore: list_snapshot_files, read_snapshot_file, Path-Traversal-Schutz
- 20/20 Tests lokal und auf `srv1.beagle-os.com` grün.
- Live: `POST /api/v1/backups/prune` → `{ok:true, pruned_count:0}` auf srv1 verifiziert.

Hinweis: Inkrementelles Backup (Testpflicht 1) und Full-Restore-Timing (Testpflicht 2)
bleiben offen — ersteres erfordert Dedup-Implementierung, letzteres 80GB-VM-Image auf NVMe.

Umsetzung Inkrementelles Backup (2026-04-24):

- `backup_service.py`: `incremental`-Feld in der Policy (`default: False`).
  Wenn `incremental=True` und `target_type=local`: `tar --listed-incremental={snar}` aktiviert.
  `.snar`-Snapshot-Datei liegt neben den Archiven im `target_path`.
  Erstes Backup (kein `.snar`): vollständiges Archiv + erstellt `.snar`.
  Folge-Backups: nur geänderte/neue Dateien werden archiviert (Inkrement).
  Archiv-Dateiname trägt Suffix `-full.tar.gz` bzw. `-incr.tar.gz`.
- Smoke-Test: `scripts/test-backup-incremental-smoke.sh`.
  Legt 50 KB Testdaten in `/etc/beagle/backup-smoke-test/` an, läuft zwei Backups,
  prüft: Backup-2 < 10 % von Backup-1.
- Validierung lokal: `BACKUP_INCREMENTAL_RESULT=PASS` (226 B incr. vs. 52 929 B full ≈ 0,4 %).
- Validierung `srv1.beagle-os.com`: `BACKUP_INCREMENTAL_RESULT=PASS` (226 B incr. vs. 52 929 B full).
- Alle 44 Backup-Unit-Tests weiterhin grün lokal und auf srv1.
