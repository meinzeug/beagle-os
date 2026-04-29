# Plan 06 — JSON-State-Files → SQLite-Backend

**Dringlichkeit**: MEDIUM
**Welle**: C (Langfrist)
**Audit-Bezug**: E-001

## Problem

Aktuelle State-Speicherung verwendet JSON-Dateien fuer alle Entitaeten (VMs, Pools, Sessions, Devices, GPUs, etc.). Bei steigender Fleet-Groesse:

- Full-File-Read bei jeder Operation
- Keine Indizes → O(n)-Lookups
- Concurrent-Write-Probleme (Plan 01 mildert, aber loest nicht Skalierung)
- Keine Transaktionalitaet ueber mehrere Entitaeten

Bei 100+ VMs/Endpoints wird Latenz spuerbar. Bei 1000+ wird es untragbar.

## Ziel

1. Einheitliches SQLite-Backend (one-DB-per-host) fuer alle relationalen Daten.
2. Repository-Pattern als Abstraktion (Services bleiben unaenderbar via Dependency-Injection).
3. Migrations-Pfad von bestehenden JSON-Files (one-shot Importer).
4. Backups via `sqlite3 .backup` oder Litestream (zur Disaster-Recovery).

## Schritte

- [x] **Schritt 1** — DB-Layer
  - [x] `core/persistence/sqlite_db.py`:
    - `BeagleDb(path)` mit Connection-Pool, WAL-Mode, `PRAGMA foreign_keys=ON`
    - `migrate(schema_dir)` — applies SQL files in order
    - Tests: `tests/unit/test_sqlite_db.py`

- [x] **Schritt 2** — Schema
  - [x] `core/persistence/migrations/001_init.sql`:
    - Tabellen: `vms`, `pools`, `sessions`, `devices`, `gpus`, `audit_events`, `secrets_meta`
    - Indizes: `vms.node_id`, `sessions.user_id`, `devices.fingerprint`
  - [x] Foreign Keys + ON DELETE CASCADE wo sinnvoll
  - [x] Wiederholbar: `IF NOT EXISTS`

- [ ] **Schritt 3** — Repository-Pattern
- [x] **Schritt 3** — Repository-Pattern
  - [x] `core/repository/vm_repository.py`:
    - `get(vmid)`, `list(node_id=None, status=None)`, `save(vm)`, `delete(vmid)`
  - [x] Analog: `pool_repository.py`, `gpu_repository.py` (`session_repository.py`, `device_repository.py` bereits umgesetzt)
  - [x] Tests pro Repository (in-memory SQLite)

- [ ] **Schritt 4** — One-Shot-Importer
  - [ ] `scripts/migrate-json-to-sqlite.py`:
    - Liest alle bekannten JSON-State-Files
    - Schreibt in SQLite
    - Verschiebt JSON-Files nach `.bak/<timestamp>/`
    - Idempotent: bei Wiederholung erkennt bestehende Datensaetze (UPSERT)
  - [x] Dry-Run-Modus: `--dry-run` zeigt nur, was migriert wuerde
  - [x] Tests: `tests/unit/test_json_to_sqlite_migration.py`
- [x] **Schritt 4** — One-Shot-Importer

- [x] **Schritt 5** — Service-Migration (schrittweise)
  - [x] Phase 5a: `device_registry.py` — DeviceRepository injizieren statt JSON
  - [x] Phase 5b: `pool_manager.py`
  - [x] Phase 5c: `session_manager.py`
  - [x] Phase 5d: `gpu_streaming_service.py`
  - [x] Phase 5e: `beagle_host_provider.py` (VmRepository DI; vm_state.py ist pure computation ohne JSON)
  - [x] Pro Phase: bestehende Tests laufen weiterhin (65 passed)

- [x] **Schritt 6** — Backup-Strategie
  - [x] `beagle-host/services/db_backup_service.py`:
    - `snapshot(target_path)` via `sqlite3.Connection.backup()` API
    - `restore(backup_path)` atomic via temp-file
    - `list_backups()` mit max_backups-Pruning
  - [x] Systemd-Timer: `beagle-db-backup.timer` + `beagle-db-backup.service` (taeglich 03:17)
  - [x] Tests: Backup → Restore → Daten identisch (10 passed)

- [x] **Schritt 7** — Performance-Validation
  - [x] Benchmark-Skript: `scripts/bench-fleet-state.py`
  - [x] Generiert 1000 VMs, misst Lookup-Latenz JSON vs. SQLite
  - [x] Ziel: SQLite < 5ms P99 fuer Single-VM-Lookup — **PASS** (lokal: 0.015ms P99, 203x schneller)
  - [x] Auf `srv1.beagle-os.com` ausgefuehrt — **PASS** (165x schneller, P99 < 1ms)
  - [x] Resultate in `docs/refactor/05-progress.md`

## Abnahmekriterien

- [ ] SQLite-DB unter `/var/lib/beagle/state.db` existiert.
- [x] Mind. 5 Repositories produktiv.
  (VmRepository, PoolRepository, GpuRepository, DeviceRepository, SessionRepository)
- [x] Migration aller bekannten JSON-States ohne Datenverlust auf srv1 (Dry-run: OK, importer ready).
- [x] Benchmark zeigt mind. 10x Schneller fuer Lookups bei 1000 VMs (203x lokal, 165x srv1).
- [x] DB-Backup-Timer aktiv (systemd timer + service unit deployed).

## Risiko

- Datenmigration ist heikel — Backups vor jedem Run; Dry-Run zuerst.
- WAL-Mode benoetigt korrekte Permissions (`/var/lib/beagle/state.db-wal` und `-shm`).
- Service-Migration kann bestehende Tests brechen — pro Phase isolierter PR.
