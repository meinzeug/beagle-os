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
  - [x] Tests: `tests/unit/test_jobs_http_surface.py` (27 tests)
  - [x] Auth: User darf nur eigene Jobs sehen (RBAC); `legacy-api-token`/localhost bleiben privilegiert fuer Operator-Smokes.

- [x] **Schritt 5** — Idempotency
  - [x] Client kann `Idempotency-Key`-Header senden (Control-Plane-Handler extrahiert Header, leitet als `client_idempotency_key` weiter)
  - [x] Bei Wiederholung mit gleichem Key → gleicher Job, kein neuer Enqueue (Server-computed Key als Fallback wenn kein Client-Key)
  - [x] TTL fuer Idempotency-Keys: 24h (bereits in `job_queue_service.py` implementiert, `DEFAULT_IDEMPOTENCY_TTL=86400`)
  - [x] Tests: `tests/unit/test_job_idempotency.py` (10 Tests: TTL-Expiry, Dedup, Client-Key-Override, Server-Fallback)

- [x] **Schritt 6** — Web-UI
  - [x] `website/ui/jobs_panel.js`:
    - `initJobsPanel()`: mount + polling-Fallback (5s), refresh-Button
    - `subscribeJob(jobId)`: SSE-Subscribe für einzelnen Job mit Auto-Reconnect
    - `showJobToast(msg, tone)`: Toast-Notification (info/success/warn/error) mit Auto-Dismiss
    - `onAsyncResponse(resp, label)`: helper — call after POST → auto-subscribe wenn `job_id` in Response
    - `teardownJobsPanel()`: cleanup
  - [x] `website/styles/panels/_jobs.css`: Toast-Container (fixed bottom-right) + Panel-Table-Styles
  - [x] `website/styles.css`: `@import` für `_jobs.css` hinzugefügt
  - [x] Bei VM-Operation im UI: nach POST → automatisch SSE-Subscribe via `onAsyncResponse()`
  - [x] Toast bei Job-Completion (SSE `job_done`/generisches `message` Event)
    - Liste laufender Jobs mit Progress-Bars
    - Filter (status, type)
    - Cancel-Button
  - [x] Bei VM-Operation im UI: nach POST → automatisch SSE-Subscribe
  - [x] Toast bei Job-Completion

- [ ] **Schritt 7** — Validation auf srv1
  - [x] `srv1.beagle-os.com`: Backup einer VM via Job-Queue. Hinweis: VM100-Smoke-Archiv war nur 4.1K, kein 5GB-Datentraeger-Test.
  - [x] Browser-/SSE-Pfad zeigt Progress live: `GET /api/v1/jobs/{id}/stream?access_token=...` liefert `completed`, `progress=100`.
  - [x] Job-History bleibt nach Restart erhalten.

## Abnahmekriterien

- [x] `JobQueueService` produktiv mit mind. 3 registrierten Handlern.
- [x] Mind. 3 lange Operationen laufen async (Snapshot, Migrate, Backup).
- [x] `GET /api/v1/jobs/{id}` + SSE funktioniert.
- [x] Idempotency-Key respektiert.
- [x] UI zeigt Live-Progress.

Umsetzung/Validierung (2026-04-27):
- `jobs_http_surface.py` filtert nicht privilegierte Requester jetzt auf eigene Jobs und verweigert fremde Job-Details, SSE und Cancel mit `403`.
- `jobs_panel.js` nutzt den echten Backend-Stream `/jobs/{job_id}/stream`, haengt fuer EventSource `access_token` als Query-Parameter an und verarbeitet generische `message`-Events sowie benannte `job_update`/`job_done`-Events.
- `service_registry.py` registriert produktiv `vm.snapshot`, `vm.migrate` und `backup.run` im Worker.
- `job_queue_service.py` persistiert Jobs nach `/var/lib/beagle/beagle-manager/jobs-state.json`; abgeschlossene Jobs bleiben nach Restart sichtbar, laufende Jobs werden nach Restart als fehlgeschlagen markiert.
- Live auf `srv1`: Backup-Job `b2b74a1332664336b07decc903acf802` fuer VM100 lief `pending -> completed 100`; nach `systemctl restart beagle-control-plane.service` blieb `GET /jobs/{id}` `completed 100` mit Result erhalten.
- Live auf `srv1`: SSE-Stream fuer Job `725ead477aa14b088d83352467d6272e` lieferte ein finalisiertes `data:`-Event mit `status=completed`, `progress=100` und Backup-Result.
- Live auf `srv1`/`srv2`: Worker-Registry enthaelt `backup.run`, `cluster.auto_join`, `cluster.maintenance_drain`, `vm.migrate`, `vm.snapshot`.
- Lokal validiert:
  - `node --check website/ui/jobs_panel.js website/ui/events.js`
  - `python3 -m py_compile beagle-host/services/job_queue_service.py beagle-host/services/jobs_http_surface.py beagle-host/services/control_plane_handler.py beagle-host/services/service_registry.py`
  - `python3 -m pytest tests/unit/test_job_queue_service.py tests/unit/test_job_worker.py tests/unit/test_jobs_http_surface.py tests/unit/test_jobs_panel_ui_regressions.py tests/unit/test_job_worker_registration_regressions.py` => `76 passed`

## Risiko

- Workers koennen abstuerzen → Heartbeat + Stuck-Detection (Job > 30 Min ohne Heartbeat → fail)
- SSE benoetigt Reverse-Proxy-Konfiguration (Buffering disable in nginx)
- Idempotency-Storage muss ueber Restarts persistieren
