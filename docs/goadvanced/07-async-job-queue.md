# Plan 07 — Async-Job-Queue fuer VM-Operationen

**Dringlichkeit**: MEDIUM
**Welle**: C (Langfrist)
**Audit-Bezug**: E-002

## Problem

Lange Operationen wie VM-Snapshots, Live-Migration, Backups blockieren den HTTP-Request-Handler. Der Client-Request laeuft potentiell in Timeout, obwohl der Server noch arbeitet. Ergebnis:

- Schlechte UX (kein Progress, harte Timeouts)
- Hohe Last auf API-Threads bei vielen parallelen Operationen
- Retry-Loops verschlimmern Lage

## Ziel

1. Async-Job-Queue: lange Operationen laufen im Hintergrund.
2. POST-Endpoints geben sofort `202 Accepted` + `job_id` zurueck.
3. `GET /api/v1/jobs/{job_id}` liefert Status, Progress, Resultat.
4. WebSocket / SSE-Endpoint fuer Live-Progress.

## Schritte

- [x] **Schritt 1** — `JobQueueService` (7390f8d)
  - [x] `beagle-host/services/job_queue_service.py`
  - [x] API:
    - `enqueue(name, payload, *, idempotency_key=None) -> Job`
    - `get(job_id) -> Job | None`
    - `update_progress(job_id, percent, message)`
    - `complete(job_id, result)` / `fail(job_id, error)`
    - `list(status=None, since=None) -> list[Job]`
    - `cancel(job_id) -> bool`
  - [x] Job-Storage: in-memory (SQLite/JsonStateStore layer-on-top stub ready)
  - [x] Tests: `tests/unit/test_job_queue_service.py` (33 tests)

- [x] **Schritt 2** — Worker (7390f8d)
  - [x] `beagle-host/services/job_worker.py`:
    - Pollt Queue, ruft registrierte Handler auf
    - Pro Job: separater Thread
    - Maximal N parallele Worker (konfigurierbar via BEAGLE_JOB_WORKER_COUNT, Default 4)
    - Heartbeat-Update alle 5s (verhindert Stuck-Jobs)
  - [x] Handler-Registry:
    - `register("vm.snapshot", snapshot_handler)`
    - `register("vm.migrate", migrate_handler)`
    - `register("backup.create", backup_handler)`
  - [x] Tests: `tests/unit/test_job_worker.py` (11 tests, inkl. cancel + parallel)

- [x] **Schritt 3** — Integration in HTTP-Surfaces
  - [x] `vm_mutation_surface.py`: `POST /api/v1/vms/{vmid}/snapshot` → enqueue + 202 (enqueue_job optional, 503 if not wired)
  - [x] `backups_http_surface.py`: `POST /api/v1/backups/run` → enqueue + 202 (sync fallback wenn kein enqueue_job)
  - [x] `cluster_http_surface.py`: `POST /api/v1/cluster/migrate` → enqueue + 202 (503 wenn kein enqueue_job)

- [x] **Schritt 4** — Status-Endpoints (7390f8d)
  - [x] `jobs_http_surface.py`:
    - `GET /api/v1/jobs/{job_id}` → JSON
    - `GET /api/v1/jobs?status=running` → Liste
    - `DELETE /api/v1/jobs/{job_id}` → Cancel
    - `GET /api/v1/jobs/{job_id}/stream` → SSE mit Progress-Events
  - [x] `control_plane_handler.py`: routing in do_GET + do_DELETE
  - [x] `request_handler_mixin.py`: `_stream_sse_job()` helper
  - [x] Tests: `tests/unit/test_jobs_http_surface.py` (22 tests)
  - [ ] Auth: User darf nur eigene Jobs sehen (RBAC) — offen (naechste Iteration)

- [x] **Schritt 5** — Idempotency
  - [x] Client kann `Idempotency-Key`-Header senden (Control-Plane-Handler extrahiert Header, leitet als `client_idempotency_key` weiter)
  - [x] Bei Wiederholung mit gleichem Key → gleicher Job, kein neuer Enqueue (Server-computed Key als Fallback wenn kein Client-Key)
  - [x] TTL fuer Idempotency-Keys: 24h (bereits in `job_queue_service.py` implementiert, `DEFAULT_IDEMPOTENCY_TTL=86400`)
  - [x] Tests: `tests/unit/test_job_idempotency.py` (10 Tests: TTL-Expiry, Dedup, Client-Key-Override, Server-Fallback)

- [ ] **Schritt 6** — Web-UI
  - [ ] `website/ui/jobs_panel.js`:
    - Liste laufender Jobs mit Progress-Bars
    - Filter (status, type)
    - Cancel-Button
  - [ ] Bei VM-Operation im UI: nach POST → automatisch SSE-Subscribe
  - [ ] Toast bei Job-Completion

- [ ] **Schritt 7** — Validation auf srv1
  - [ ] `srv1.beagle-os.com`: Backup einer 5GB-VM via Job-Queue
  - [ ] Browser-UI zeigt Progress live
  - [ ] Job-History bleibt nach Restart erhalten

## Abnahmekriterien

- [ ] `JobQueueService` produktiv mit mind. 3 registrierten Handlern.
- [ ] Mind. 3 lange Operationen laufen async (Snapshot, Migrate, Backup).
- [ ] `GET /api/v1/jobs/{id}` + SSE funktioniert.
- [ ] Idempotency-Key respektiert.
- [ ] UI zeigt Live-Progress.

## Risiko

- Workers koennen abstuerzen → Heartbeat + Stuck-Detection (Job > 30 Min ohne Heartbeat → fail)
- SSE benoetigt Reverse-Proxy-Konfiguration (Buffering disable in nginx)
- Idempotency-Storage muss ueber Restarts persistieren
