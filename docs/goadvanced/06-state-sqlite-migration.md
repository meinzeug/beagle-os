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

- [ ] **Schritt 1** — DB-Layer
  - [ ] `core/persistence/sqlite_db.py`:
    - `BeagleDb(path)` mit Connection-Pool, WAL-Mode, `PRAGMA foreign_keys=ON`
    - `migrate(schema_dir)` — applies SQL files in order
    - Tests: `tests/unit/test_sqlite_db.py`

- [ ] **Schritt 2** — Schema
  - [ ] `core/persistence/migrations/001_init.sql`:
    - Tabellen: `vms`, `pools`, `sessions`, `devices`, `gpus`, `audit_events`, `secrets_meta`
    - Indizes: `vms.node_id`, `sessions.user_id`, `devices.fingerprint`
  - [ ] Foreign Keys + ON DELETE CASCADE wo sinnvoll
  - [ ] Wiederholbar: `IF NOT EXISTS`

- [ ] **Schritt 3** — Repository-Pattern
  - [ ] `core/repository/vm_repository.py`:
    - `get(vmid)`, `list(node_id=None, status=None)`, `save(vm)`, `delete(vmid)`
  - [ ] Analog: `pool_repository.py`, `session_repository.py`, `device_repository.py`, `gpu_repository.py`
  - [ ] Tests pro Repository (in-memory SQLite)

- [ ] **Schritt 4** — One-Shot-Importer
  - [ ] `scripts/migrate-json-to-sqlite.py`:
    - Liest alle bekannten JSON-State-Files
    - Schreibt in SQLite
    - Verschiebt JSON-Files nach `.bak/<timestamp>/`
    - Idempotent: bei Wiederholung erkennt bestehende Datensaetze (UPSERT)
  - [ ] Dry-Run-Modus: `--dry-run` zeigt nur, was migriert wuerde
  - [ ] Tests: `tests/unit/test_json_to_sqlite_migration.py`

- [ ] **Schritt 5** — Service-Migration (schrittweise)
  - [ ] Phase 5a: `device_registry.py` — DeviceRepository injizieren statt JSON
  - [ ] Phase 5b: `pool_manager.py`
  - [ ] Phase 5c: `session_manager.py`
  - [ ] Phase 5d: `gpu_streaming_service.py`
  - [ ] Phase 5e: `vm_state_service.py` (groesste Datenmenge)
  - [ ] Pro Phase: bestehende Tests muessen mit gemockten Repositories weiterhin laufen

- [ ] **Schritt 6** — Backup-Strategie
  - [ ] `beagle-host/services/db_backup_service.py`:
    - `snapshot(target_path)` via `sqlite3 .backup`
    - Optional: Litestream-Integration fuer Continuous-Replication
  - [ ] Systemd-Timer: `beagle-db-backup.timer` (taeglich + bei VM-State-Aenderung)
  - [ ] Tests: Backup → Restore → Daten identisch

- [ ] **Schritt 7** — Performance-Validation
  - [ ] Benchmark-Skript: `scripts/bench-fleet-state.py`
  - [ ] Generiert 1000 VMs, misst Lookup-Latenz JSON vs. SQLite
  - [ ] Ziel: SQLite < 5ms P99 fuer Single-VM-Lookup, JSON > 50ms
  - [ ] Auf `srv1.beagle-os.com` ausfuehren
  - [ ] Resultate in `docs/refactor/05-progress.md`

## Abnahmekriterien

- [ ] SQLite-DB unter `/var/lib/beagle/state.db` existiert.
- [ ] Mind. 5 Repositories produktiv.
- [ ] Migration aller bekannten JSON-States ohne Datenverlust auf srv1.
- [ ] Benchmark zeigt mind. 10x Schneller fuer Lookups bei 1000 VMs.
- [ ] DB-Backup-Timer aktiv.

## Risiko

- Datenmigration ist heikel — Backups vor jedem Run; Dry-Run zuerst.
- WAL-Mode benoetigt korrekte Permissions (`/var/lib/beagle/state.db-wal` und `-shm`).
- Service-Migration kann bestehende Tests brechen — pro Phase isolierter PR.
