# Plan 08 — Observability: Prometheus, strukturierte Logs, Tracing

**Dringlichkeit**: MEDIUM
**Welle**: C (Langfrist)
**Audit-Bezug**: D-003, D-005

## Problem

- Logs werden als JSON nach stdout geschrieben — keine zentrale Aggregation, keine Rotation-Policy dokumentiert.
- Kein Prometheus `/metrics`-Endpoint.
- Keine verteilten Traces fuer Multi-Hop-Operationen (z.B. UI → control-plane → libvirt).
- Health-Check-Aggregation fehlt.

## Ziel

1. `/metrics` im Prometheus-Format (Counter, Gauge, Histogram).
2. Strukturierte Logs mit konsistenten Feldern (request_id, user_id, vm_id, duration_ms).
3. Optional OpenTelemetry-Tracing fuer Multi-Service-Calls.
4. Aggregierter Health-Endpoint `/api/v1/health` mit Details pro Subsystem.

## Schritte

- [ ] **Schritt 1** — Metrics-Service
  - [ ] `beagle-host/services/prometheus_metrics.py`:
    - `counter(name, labels=())`, `gauge(name, labels=())`, `histogram(name, buckets=...)`
    - In-Memory-Registry, Render-Funktion fuer Prometheus-Text-Format
    - Default-Metriken: `beagle_http_requests_total`, `beagle_http_request_duration_seconds`, `beagle_vm_count`, `beagle_session_count`, `beagle_auth_failures_total`, `beagle_rate_limit_drops_total`
  - [ ] Tests: `tests/unit/test_prometheus_metrics.py`

- [ ] **Schritt 2** — `/metrics`-Endpoint
  - [ ] `health_http_surface.py` erweitern um `GET /metrics` (text/plain)
  - [ ] Auth: optional via `?token=...` oder Bearer (Prometheus-Scrape-Token)
  - [ ] Tests: Endpoint liefert valides Prometheus-Format

- [ ] **Schritt 3** — Strukturierte Logs
  - [ ] `core/logging/structured_logger.py`:
    - `log(level, event, **fields)` → JSON-Zeile auf stdout
    - Pflichtfelder: `timestamp`, `level`, `service`, `event`
    - Optional: `request_id`, `user_id`, `correlation_id`, `duration_ms`
  - [ ] Migration: alle `print(...)`-Aufrufe in `beagle-control-plane.py` und Services umstellen
  - [ ] Tests: Log-Output-Parser pruefen
  - [ ] systemd-journald uebernimmt Rotation automatisch

- [ ] **Schritt 4** — Request-IDs + Tracing
  - [ ] HTTP-Middleware: liest `X-Request-Id`-Header oder generiert UUID
  - [ ] Request-ID wird in alle Logs der Request-Verarbeitung eingebaut
  - [ ] `X-Request-Id` in Response-Header zurueck
  - [ ] (Phase 2 optional) OpenTelemetry-Adapter fuer Distributed Tracing

- [ ] **Schritt 5** — Health-Aggregation
  - [ ] `health_http_surface.py`: `GET /api/v1/health`:
    ```json
    {
      "status": "healthy" | "degraded" | "unhealthy",
      "components": {
        "libvirt": {"status": "healthy", "latency_ms": 12},
        "database": {"status": "healthy"},
        "control_plane": {"status": "healthy", "uptime_seconds": 3600}
      }
    }
    ```
  - [ ] Per-Component-Check mit Timeout 2s
  - [ ] HTTP-Status: 200 healthy, 200 degraded, 503 unhealthy

- [ ] **Schritt 6** — Dashboards
  - [ ] `docs/observability/grafana-dashboard.json` (importierbar)
  - [ ] `docs/observability/prometheus-scrape-config.yml`
  - [ ] Doku: `docs/observability/setup.md`

- [ ] **Schritt 7** — Verifikation auf srv1
  - [ ] `curl https://srv1/metrics` liefert Prometheus-Format
  - [ ] `journalctl -u beagle-control-plane -o json | jq` zeigt strukturierte Logs
  - [ ] Health-Endpoint zeigt `degraded` wenn libvirt down ist

## Abnahmekriterien

- [ ] `/metrics` liefert mind. 10 Metriken im Prometheus-Format.
- [ ] Alle `print()`-Aufrufe in `beagle-host/services/` durch `structured_logger` ersetzt.
- [ ] Request-IDs in allen Log-Zeilen einer Request-Verarbeitung.
- [ ] `/api/v1/health` mit Component-Details.
- [ ] Grafana-Dashboard funktioniert auf srv1.

## Risiko

- In-Memory-Registry kann bei vielen Labels speicherintensiv werden → Label-Cardinality limitieren.
- Strukturierte Logs muessen rueckwaerts-kompat sein (alte journalctl-Greps weiterhin funktionsfaehig).
