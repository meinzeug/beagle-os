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

- [ ] **Schritt 1** — `JobQueueService`
  - [ ] `beagle-host/services/job_queue_service.py`
  - [ ] API:
    - `enqueue(name, payload, *, idempotency_key=None) -> Job`
    - `get(job_id) -> Job | None`
    - `update_progress(job_id, percent, message)`
    - `complete(job_id, result)` / `fail(job_id, error)`
    - `list(status=None, since=None) -> list[Job]`
    - `cancel(job_id) -> bool`
  - [ ] Job-Storage: SQLite (siehe Plan 06) oder JSON (`JsonStateStore` aus Plan 01)
  - [ ] Tests: `tests/unit/test_job_queue.py`

- [ ] **Schritt 2** — Worker
  - [ ] `beagle-host/services/job_worker.py`:
    - Pollt Queue, ruft registrierte Handler auf
    - Pro Job: separater Thread (oder asyncio Task)
    - Maximal N parallele Worker (konfigurierbar, Default 4)
    - Heartbeat-Update alle 5s (verhindert Stuck-Jobs)
  - [ ] Handler-Registry:
    - `register("vm.snapshot", snapshot_handler)`
    - `register("vm.migrate", migrate_handler)`
    - `register("backup.create", backup_handler)`
  - [ ] Tests: Worker-Crash-Recovery, Timeout-Handling

- [ ] **Schritt 3** — Integration in HTTP-Surfaces
  - [ ] `vms_http_surface.py`: `POST /api/v1/vms/{vmid}/snapshot` → enqueue + 202
  - [ ] `backup_http_surface.py`: `POST /api/v1/backups` → enqueue + 202
  - [ ] `cluster_http_surface.py`: `POST /api/v1/cluster/migrate` → enqueue + 202

- [ ] **Schritt 4** — Status-Endpoints
  - [ ] `jobs_http_surface.py`:
    - `GET /api/v1/jobs/{job_id}` → JSON
    - `GET /api/v1/jobs?status=running` → Liste
    - `DELETE /api/v1/jobs/{job_id}` → Cancel
    - `GET /api/v1/jobs/{job_id}/stream` → SSE mit Progress-Events
  - [ ] Auth: User darf nur eigene Jobs sehen (RBAC)

- [ ] **Schritt 5** — Idempotency
  - [ ] Client kann `Idempotency-Key`-Header senden
  - [ ] Bei Wiederholung mit gleichem Key → gleicher Job, kein neuer Enqueue
  - [ ] TTL fuer Idempotency-Keys: 24h
  - [ ] Tests: `tests/unit/test_job_idempotency.py`

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
