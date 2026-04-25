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

- [ ] **Schritt 1** — Inventur
  - [ ] `grep -n 'def do_GET\|def do_POST\|def do_PUT\|def do_DELETE\|def _route_' beagle-host/bin/beagle-control-plane.py` → Liste aller Endpoint-Handler
  - [ ] Pro Endpoint: vermerken, welche Service-Surface zustaendig waere
  - [ ] Inventur in `docs/goadvanced/05-control-plane-inventory.md` (Hilfsdatei)

- [ ] **Schritt 2** — Router-Abstraktion
  - [ ] `beagle-host/services/api_router_service.py` neu
  - [ ] API:
    - `register(method, path_pattern, handler)`
    - `dispatch(method, path, request) -> Response`
    - Pfad-Pattern unterstuetzt `:param` (z.B. `/api/v1/vms/:vmid`)
  - [ ] Tests: `tests/unit/test_api_router.py`
    - [ ] Static Path Match
    - [ ] Param Extract
    - [ ] Method-Mismatch → 405
    - [ ] Unknown Path → 404
    - [ ] Multiple Handler-Reihenfolge

- [ ] **Schritt 3** — Surface-Migration je Domain (1 PR pro Domain)
  - [ ] **3a — VMs**: `beagle-host/services/vms_http_surface.py` mit GET/POST/PUT/DELETE `/api/v1/vms[/...]`
  - [ ] **3b — Pools**: `beagle-host/services/pools_http_surface.py`
  - [ ] **3c — Cluster**: `beagle-host/services/cluster_http_surface.py`
  - [ ] **3d — Devices/Endpoints**: `beagle-host/services/devices_http_surface.py`
  - [ ] **3e — Reports/Costs**: `beagle-host/services/reports_http_surface.py`
  - [ ] **3f — Energy/CSRD**: `beagle-host/services/energy_http_surface.py`
  - [ ] **3g — GPUs**: `beagle-host/services/gpus_http_surface.py`
  - [ ] **3h — Sessions**: `beagle-host/services/sessions_http_surface.py`
  - [ ] **3i — Fleet**: `beagle-host/services/fleet_http_surface.py`
  - [ ] **3j — Health/Metrics**: `beagle-host/services/health_http_surface.py`

- [ ] **Schritt 4** — `beagle-control-plane.py` schlank machen
  - [ ] Nur noch:
    - Argument-Parsing
    - Service-Initialisierung (Dependency-Injection)
    - Surface-Registrierung beim Router
    - HTTPServer-Start
    - Signal-Handling (graceful shutdown)
  - [ ] Ziel: < 800 LOC

- [ ] **Schritt 5** — Tests pro Surface
  - [ ] Pro Surface ein `tests/unit/test_*_http_surface.py` mit Mocked-Service-Dependencies
  - [ ] Mind. happy-path + 1 Error-Case + 1 Auth-Required-Case

- [ ] **Schritt 6** — Smoke auf srv1
  - [ ] `srv1.beagle-os.com`: alle Endpoints reagieren wie vorher (Smoke-Test-Skript `scripts/smoke-control-plane-endpoints.sh`)
  - [ ] Performance-Vergleich: P99-Latenz vs. Vorher (sollte sich nicht verschlechtern)
  - [ ] `docs/refactor/05-progress.md` aktualisiert

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
