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

- [x] **Schritt 1** — Metrics-Service
  - [x] `beagle-host/services/prometheus_metrics.py`:
    - `counter(name, labels=())`, `gauge(name, labels=())`, `histogram(name, buckets=...)`
    - In-Memory-Registry, Render-Funktion fuer Prometheus-Text-Format
    - Default-Metriken: `beagle_http_requests_total`, `beagle_http_request_duration_seconds`, `beagle_vm_count`, `beagle_session_count`, `beagle_auth_failures_total`, `beagle_rate_limit_drops_total`, `beagle_process_start_time_seconds`
    - Thread-safe (Lock pro Metric), Label-Cardinality-Cap (default 10000) mit Drop-Warnung auf stderr und Noop-Sentinels fuer ueberlaufende Combinations
  - [x] Tests: `tests/unit/test_prometheus_metrics.py` (23 Tests)

- [x] **Schritt 2** — `/metrics`-Endpoint
  - [x] `control_plane_handler.py` `do_GET`: `GET /metrics` liefert Prometheus-Text (Content-Type `text/plain; version=0.0.4; charset=utf-8`)
  - [x] Auth: optional via `BEAGLE_METRICS_BEARER_TOKEN` (Bearer-Header, `hmac.compare_digest`); ohne Token unauthenticated (lokal/Reverse-Proxy)
  - [x] Singleton via `service_registry.prometheus_metrics_service()` mit `register_defaults()` beim Erstaufruf
  - [ ] Smoke-Test gegen laufenden Server (verschoben — siehe Schritt 7)

- [x] **Schritt 3** — Strukturierte Logs
  - [x] `beagle-host/services/structured_logger.py` (`StructuredLogger`):
    - `debug/info/warn/error(event, **fields)` => JSON-Zeile auf stdout (oder beliebigen Stream).
    - Pflichtfelder: `timestamp`, `level`, `service`, `event`. Per-Thread-Context (`with log.context(...)`, `log.bind(...)`, `log.clear()`) merged Felder in jeden Emit.
    - Min-Level-Filter via `BEAGLE_LOG_LEVEL` env (default `info`). Thread-safe via `Lock`. Fallback fuer non-JSONable Werte (set/tuple/bytes/repr).
    - Compat-Shim `log_message(fmt, *args)` als Drop-In fuer `BaseHTTPRequestHandler.log_message`.
  - [x] Singleton `service_registry.structured_logger()`.
  - [x] `control_plane_handler.log_message` routet HTTP-Access-Logs durch den strukturierten Logger (Fallback `print` bei Fehler).
  - [x] Tests: `tests/unit/test_structured_logger.py` (15 Tests).
  - [ ] Massen-Migration aller `print()`-Aufrufe (deferred — separater Run pro Modul, niedriges Risiko, hohe Streuung).
  - [x] systemd-journald uebernimmt Rotation automatisch.

- [x] **Schritt 4** — Request-IDs + Tracing
  - [x] `control_plane_handler.handle_one_request` ist neu implementiert (statt `super().handle_one_request()`): liest `X-Request-Id`-Header (akzeptiert `[A-Za-z0-9._-]{1,128}`), faellt sonst auf `uuid4().hex` zurueck.
  - [x] Request-Id wird auf `self._beagle_request_id` gesetzt und in `request_handler_mixin._write_common_security_headers` als `X-Request-Id` Response-Header gesendet.
  - [x] Per-Request strukturiert-Logger-Context mit `request_id`, `method`, `path`, `client` umschliesst die `do_*()`-Dispatch — alle Logs der Request-Verarbeitung tragen die Felder automatisch.
  - [x] Tests: `tests/integration/test_request_id_middleware.py` (5 Tests — /metrics, generated-id, echo-incoming, unsafe-id replaced, unique-per-request).
  - [ ] OpenTelemetry-Adapter (Phase 2 optional, nicht in diesem Run).

- [x] **Schritt 5** — Health-Aggregation
  - [x] `health_aggregator.py` (`HealthAggregatorService`): Per-Component-Checks mit 2s-Timeout (Thread-Watchdog), Aggregation `healthy | degraded | unhealthy`, Eingebaute Checks: `control_plane_check` (uptime), `provider_check` (list_providers), `writable_path_check` (data_dir).
  - [x] `service_registry.health_aggregator_service()` Singleton mit drei Default-Checks (`control_plane`, `providers`, `data_dir`).
  - [x] `control_plane_handler.do_GET` `/api/v1/health`: alte Felder bleiben, `status` + `components` werden ergänzt.
  - [x] HTTP-Status: 200 default; Opt-In `BEAGLE_HEALTH_503_ON_UNHEALTHY=1` schaltet 503 fuer `unhealthy`.
  - [x] Tests: `tests/unit/test_health_aggregator.py` (16 Tests — Aggregation, Timeout, Exception, Replace, Built-Ins).

- [x] **Schritt 6** — Dashboards
  - [x] `docs/observability/grafana-dashboard.json` (importierbar, 7 Panels: HTTP rate/latency, Auth-Failures, Rate-Limit-Drops, VM-Count, Sessions, Uptime).
  - [x] `docs/observability/prometheus-scrape-config.yml` (15s Scrape, optional Bearer-Token, srv1+srv2 Targets, instance-Relabel).
  - [x] `docs/observability/setup.md` (5 Sektionen: Scrape-Config, Health-Endpoint, Strukturierte Logs, Request-ID-Propagation, Grafana-Import).

- [ ] **Schritt 7** — Verifikation auf srv1
  - [ ] `curl https://srv1.beagle-os.com/metrics` liefert Prometheus-Format
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
