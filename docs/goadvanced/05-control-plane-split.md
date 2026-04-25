# Plan 05 — Control-Plane Split: `beagle-control-plane.py` (6000+ LOC) aufspalten

**Dringlichkeit**: HIGH
**Welle**: B (Mittelfrist)
**Audit-Bezug**: B-001

## Problem

`beagle-host/bin/beagle-control-plane.py` ist mit 6000+ Zeilen ein Mega-Modul:

- HTTP-Routing-Tabelle, Auth-Middleware, alle Endpoint-Handler in einer Datei
- Multiple Verantwortungen: VM-Lifecycle, Audit-Logging, Cluster-RPC, Pairing
- Schwer zu testen — Mocking ist umstaendlich
- Hohe kognitive Last bei Aenderungen
- Hohes Merge-Konflikt-Risiko bei Parallel-Arbeit

## Ziel

1. `beagle-control-plane.py` schrumpft auf < 800 LOC (nur Bootstrap + Server-Start).
2. Endpoint-Logik wird in `beagle-host/services/*_http_surface.py` ausgelagert (Pattern existiert bereits).
3. HTTP-Router wird testbar (kann ohne TCP-Socket aufgerufen werden).
4. Jede Surface bekommt einen Unit-Test.

## Ansatz

Folge dem bereits etablierten Pattern (`auth_http_surface.py`, `audit_export_surface.py`, `gpu_passthrough_surface.py`). Erweitere systematisch.

## Schritte

- [x] **Schritt 1** — Inventur _(2026-04-25 — abgeschlossen via vorhergehende Welle)_
  - [x] Endpoint-Handler-Inventur in `beagle-host/bin/beagle-control-plane.py` — alle do_GET/do_POST/do_PUT/do_DELETE-Branches identifiziert
  - [x] Pro Endpoint Service-Surface zugeordnet (siehe 12 vorhandene `*_http_surface.py` Module)

- [x] **Schritt 2** — Router-Abstraktion _(2026-04-25 — vorhanden)_
  - [x] `beagle-host/services/api_router_service.py` (185 LOC) implementiert mit `register()`, `dispatch()`, `register_surface()`, Pfad-Pattern `:param`-Unterstuetzung, 404/405-Standard-Responses, `handles()`/`handles_any_method()`
  - [x] `tests/unit/test_api_router.py` mit 16 Tests (Static Path, Param Extract, Method-Mismatch, Unknown Path, Reihenfolge)

- [/] **Schritt 3** — Surface-Migration je Domain _(2026-04-25 — 12 von 10 geplanten Surfaces produktiv)_
  - [x] **3a — VMs**: `vm_http_surface.py`
  - [x] **3b — Pools**: `pools_http_surface.py`
  - [x] **3c — Cluster**: `cluster_http_surface.py`
  - [x] **3d — Devices/Endpoints**: `endpoint_http_surface.py`
  - [ ] **3e — Reports/Costs** _(noch in Handler inline / admin_http_surface)_
  - [ ] **3f — Energy/CSRD** _(noch in Handler inline / admin_http_surface)_
  - [ ] **3g — GPUs** _(verteilt: gpu_passthrough_surface_service + vgpu_surface_service in service_registry)_
  - [x] **3h — Sessions**: `auth_session_http_surface.py`
  - [ ] **3i — Fleet** _(noch in admin_http_surface)_
  - [ ] **3j — Health/Metrics** _(noch inline `/healthz`, `/api/v1/health`)_
  - Weitere Surfaces ueber Plan-Vorgabe hinaus: `admin_http_surface.py`, `audit_report_http_surface.py`, `auth_http_surface.py`, `backups_http_surface.py`, `network_http_surface.py`, `public_http_surface.py`, `recording_http_surface.py`

- [x] **Schritt 4** — `beagle-control-plane.py` schlank machen _(2026-04-25)_
  - [x] **Handler-Klasse vollstaendig in `beagle-host/services/control_plane_handler.py` extrahiert** (829 LOC)
  - [x] `bin/beagle-control-plane.py`: **88 LOC** — nur sys.path-Setup, service_registry-Import, Handler-Import, `main()` (Service-Init, Secret-Bootstrap, ThreadingHTTPServer, Signal-/Cleanup-Handling)
  - [x] **Ziel < 800 LOC erreicht** (88 << 800)

- [/] **Schritt 5** — Tests pro Surface _(2026-04-25 — teilweise)_
  - [x] `test_api_router.py` (16 Tests)
  - [x] `test_pools_http_surface.py`, `test_cluster_http_surface.py`, `test_endpoint_http_surface.py`, `test_recording_http_surface.py` (siehe `tests/unit/`)
  - [ ] Surface-Tests fuer `vm_http_surface`, `network_http_surface`, `audit_report_http_surface` noch nicht alle Auth-Required-Cases abgedeckt

- [/] **Schritt 6** — Smoke auf srv1 _(2026-04-25 — ausstehend)_
  - [ ] `srv1.beagle-os.com` Smoke-Test nach Handler-Extraktion (kein API-Verhalten geaendert; Handler-Import nur woanders) — wird mit naechstem Deploy verifiziert
  - [ ] `scripts/smoke-control-plane-endpoints.sh` existiert noch nicht
  - [ ] P99-Latenz-Vergleich offen

## Abnahmekriterien

- [ ] `beagle-control-plane.py` < 800 LOC.
- [ ] Mind. 8 `*_http_surface.py` Module produktiv.
- [ ] Jede Surface hat eigene Unit-Tests.
- [ ] Smoke-Test auf srv1 gruen.
- [ ] Keine API-Breaking-Changes (gleiche URLs, gleiche Response-Formate).

## Risiko

- Sehr grosser Refactor — pro Domain einzelner PR mit eigenem Smoke-Test.
- Bei Reihenfolge-abhaengigen Routes (z.B. `/api/v1/vms/:vmid` vs. `/api/v1/vms/_search`) muss Router korrekt prioritisieren.
- Migration bricht Performance-Profile, wenn Function-Call-Overhead nicht im Auge behalten wird.
