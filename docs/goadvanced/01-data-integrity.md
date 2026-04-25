# Plan 01 — Datenintegritaet: Atomic Writes + Locking + State-Base-Class

**Dringlichkeit**: HIGH
**Welle**: A (Sofort)
**Audit-Bezug**: S-004, B-002, B-003

## Problem

Aktuell schreiben mehrere Services JSON-State-Dateien direkt mit `path.write_text(json.dumps(...))`. Bei gleichzeitigen Schreibvorgaengen oder Crashs waehrend des Schreibens kann der State korrupt sein.

Betroffene Dateien (Audit-Befund):

- `providers/beagle/network/vxlan.py:39-43`
- `providers/beagle/network/vlan.py:27-32`
- `beagle-host/bin/beagle_novnc_token.py:60-68`
- ~40 weitere Services unter `beagle-host/services/`

Zusaetzlich existiert keine gemeinsame Basisklasse fuer State-Persistenz — jeder Service implementiert Load/Save erneut.

## Ziel

1. Eine zentrale Helper-Klasse `JsonStateStore` mit:
   - Atomic Write (tempfile + `os.rename` + `os.fsync`)
   - File-Locking (`fcntl.flock`) zur Vermeidung von Race-Conditions
   - Automatische Permission-Enforcement (0o600 fuer Secrets, 0o644 fuer Config)
   - Konsistentes Error-Handling
2. Schrittweise Migration aller Services auf `JsonStateStore`.
3. Unit-Tests, die Crash-Szenarien (Schreiben unterbrechen) simulieren.

## Schritte

- [ ] **Schritt 1** — Basis-Klasse erstellen
  - [ ] `core/persistence/json_state_store.py` neu anlegen
  - [ ] API:
    - `JsonStateStore(path, default_factory, mode=0o600)`
    - `.load() -> dict` (mit Lock)
    - `.save(data: dict) -> None` (atomic + Lock)
    - `.update(mutator: Callable[[dict], None]) -> None` (Read-Modify-Write unter Lock)
    - `.exists() -> bool`
  - [ ] Atomic-Pattern: `NamedTemporaryFile(dir=parent, delete=False)` → `fsync()` → `os.replace()`
  - [ ] Lock-Pattern: `fcntl.flock(fd, fcntl.LOCK_EX)` mit Context-Manager
  - [ ] Permissions: `os.chmod(path, mode)` nach jedem Save
  - [ ] Tests: `tests/unit/test_json_state_store.py`
    - [ ] save+load Round-Trip
    - [ ] Atomic-Write: Crash-Simulation (Tempfile bleibt, Original unveraendert)
    - [ ] Concurrent-Write: 10 parallele `update()`-Aufrufe, finaler State enthaelt alle 10 Aenderungen
    - [ ] Permissions: nach Save ist Datei-Mode korrekt
    - [ ] Default-Factory: nicht-existente Datei → default
    - [ ] Korrupte JSON-Datei → `JSONDecodeError` sauber propagiert

- [ ] **Schritt 2** — Migration Hochrisiko-Services
  - [ ] `providers/beagle/network/vxlan.py` umstellen
  - [ ] `providers/beagle/network/vlan.py` umstellen
  - [ ] `beagle-host/bin/beagle_novnc_token.py` umstellen
  - [ ] `beagle-host/services/vm_secret_store.py` umstellen
  - [ ] `beagle-host/services/audit_log_service.py` umstellen (kritisch fuer Compliance)

- [ ] **Schritt 3** — Migration restliche Services (in 4 Wellen je ~10 Services)
  - [ ] Welle 3a: `pool_manager.py`, `gpu_streaming_service.py`, `cost_model_service.py`, `usage_tracking_service.py`, `energy_service.py`
  - [ ] Welle 3b: `device_registry.py`, `attestation_service.py`, `mdm_policy_service.py`, `cluster_service.py`, `alert_service.py`
  - [ ] Welle 3c: `session_manager.py`, `fleet_telemetry_service.py`, `metrics_collector.py`, `workload_pattern_analyzer.py`, `smart_scheduler.py`
  - [ ] Welle 3d: alle restlichen Services unter `beagle-host/services/`

- [ ] **Schritt 4** — Verifikation
  - [ ] Stress-Test-Skript: `scripts/test-json-state-stress.sh` (1000 parallele Writes auf testfile.json, kein Korruptions-Fehler)
  - [ ] Auf `srv1.beagle-os.com` ausfuehren
  - [ ] Repo-Grep: keine `path.write_text(json.dumps(` mehr ausserhalb von Tests
  - [ ] `docs/refactor/05-progress.md` aktualisiert

## Abnahmekriterien

- [ ] `JsonStateStore` ist in `core/persistence/json_state_store.py` verfuegbar.
- [ ] Mind. 20 Services auf `JsonStateStore` migriert.
- [ ] Stress-Test mit 1000 parallelen Writes ohne Datenkorruption.
- [ ] Alle bestehenden Service-Tests weiterhin gruen.
- [ ] Crash-Simulations-Test in `tests/unit/test_json_state_store.py` gruen.

## Risiko

- Migration kann bestehendes Verhalten leicht aendern (z.B. Default-Werte fuer neue Felder). Pro Service einen separaten Commit.
- Lock-Files koennen bei abgestuerzten Prozessen stale sein → `flock` mit Timeout, nicht permanenter Lock.
