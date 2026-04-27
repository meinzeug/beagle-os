# Beagle OS — Observability Setup

GoAdvanced Plan 08 Schritt 6.

This document describes how to scrape Beagle OS metrics with Prometheus,
visualise them in Grafana, and parse structured logs from journald.

## 1. Prometheus scrape configuration

Beagle exposes Prometheus-format metrics at `GET /metrics` on the control
plane (default port 443). The endpoint is **unauthenticated by default**
which is appropriate when:

- Prometheus runs on the same host (`localhost` scrape).
- A reverse proxy in front of the control plane enforces a network ACL.

For setups where neither holds, set `BEAGLE_METRICS_BEARER_TOKEN` in the
`beagle-control-plane.service` environment and configure Prometheus to send
the same token via `bearer_token` (or `bearer_token_file`).

See [`prometheus-scrape-config.yml`](prometheus-scrape-config.yml) for a
ready-to-paste job definition.

### Default metric families

| Metric                                     | Type      | Labels         | Notes                              |
|--------------------------------------------|-----------|----------------|------------------------------------|
| `beagle_http_requests_total`               | counter   | method, status | All HTTP requests handled.         |
| `beagle_http_request_duration_seconds`     | histogram | method         | Default Prometheus buckets.        |
| `beagle_vm_count`                          | gauge     | —              | VMs known to the control plane.    |
| `beagle_session_count`                     | gauge     | —              | Active streaming sessions.         |
| `beagle_auth_failures_total`               | counter   | kind           | Failed authentication attempts.    |
| `beagle_rate_limit_drops_total`            | counter   | path           | Rate-limit-dropped requests.       |
| `beagle_process_start_time_seconds`        | gauge     | —              | Unix epoch second of process start.|

Caller code may register additional metrics through
`service_registry.prometheus_metrics_service()`.

### Cardinality cap

The in-memory registry caps each metric at 10000 distinct label
combinations (configurable via `PrometheusMetricsService(max_label_combinations=...)`).
Combinations beyond the cap are silently dropped and a warning is written
to stderr. Avoid putting unbounded values (request paths with IDs, IP
addresses, full URLs) into labels.

## 2. Health endpoint

`GET /api/v1/health` returns the existing flat status payload **plus**:

```json
{
  "status": "healthy" | "degraded" | "unhealthy",
  "components": {
    "control_plane": {"status": "healthy", "latency_ms": 0, "detail": "uptime=3600s"},
    "providers":     {"status": "healthy", "latency_ms": 1, "detail": "providers=beagle"},
    "data_dir":      {"status": "healthy", "latency_ms": 2}
  }
}
```

By default the HTTP status is **200** for any aggregated state. To opt
into HTTP 503 on `unhealthy` (e.g. for Kubernetes/HAProxy liveness),
set `BEAGLE_HEALTH_503_ON_UNHEALTHY=1`.

Per-check timeout is 2 seconds. Checks that exceed the timeout are
recorded as `unhealthy` with `error="check timed out after 2.0s"`.

## 3. Structured logs

The control plane emits JSON-line logs on stdout. systemd-journald
captures them automatically; no rotation policy needs to be configured.

```
$ journalctl -u beagle-control-plane -o cat | jq -r 'select(.level=="error")'
```

Mandatory fields: `timestamp`, `level`, `service`, `event`. HTTP requests
add `request_id`, `method`, `path`, `client` to every log line emitted
during their dispatch.

`BEAGLE_LOG_LEVEL` controls the minimum level (`debug | info | warn | error`,
default `info`).

## 4. Request-ID propagation

Every response carries an `X-Request-Id` header. Clients may set it on
the request to correlate downstream calls — values matching
`[A-Za-z0-9._-]{1,128}` are passed through; anything else is replaced
with a fresh UUID.

```
$ curl -sI -H 'X-Request-Id: deploy-2026-04-26-001' \
    https://srv1.beagle-os.com/api/v1/health | grep -i request-id
X-Request-Id: deploy-2026-04-26-001
```

## 5. Grafana dashboard

Import [`grafana-dashboard.json`](grafana-dashboard.json) via
*Dashboards → Import → Upload JSON*. The dashboard ships with five panels:

1. HTTP request rate (by status class)
2. HTTP request p50/p95/p99 latency
3. Auth failures (rate, by kind)
4. Rate-limit drops (rate, by path)
5. VM and session count (gauges)

It uses `${DS_PROMETHEUS}` as the datasource variable.
