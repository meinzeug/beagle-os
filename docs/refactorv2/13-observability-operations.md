# 13 — Observability und Operations

Stand: 2026-04-20

## Ziele

- Operator soll Plattform- und Stream-Health in Sekunden erkennen.
- Engineer soll Fehler bis zur Codezeile in Minuten zurueckverfolgen koennen.
- Compliance-Sicht (Audit) klar getrennt von operativer Telemetrie.

## Metriken

### Stack

- Pro Host ein Prometheus-Exporter `beagle-exporter` (Port 9100-aequivalent) mit Cluster- und VM-Metriken.
- Optional Push-Modell ueber OTLP fuer SaaS-Backends (Grafana Cloud, Datadog).

### Kern-Metriken

| Bereich | Metrik | Labels |
|---|---|---|
| Host | `beagle_host_cpu_used_pct` | node |
| Host | `beagle_host_mem_used_bytes` | node |
| Host | `beagle_host_disk_used_bytes` | node, pool |
| Host | `beagle_host_net_bytes_total` | node, iface, dir |
| VM | `beagle_vm_cpu_used_pct` | node, tenant, pool, vmid |
| VM | `beagle_vm_mem_used_bytes` | node, tenant, pool, vmid |
| VM | `beagle_vm_disk_io_bytes_total` | node, tenant, pool, vmid, dir |
| Stream | `beagle_stream_rtt_ms` | tenant, pool, vmid, session |
| Stream | `beagle_stream_fps` | tenant, pool, vmid, session |
| Stream | `beagle_stream_dropped_frames_total` | tenant, pool, vmid, session |
| Stream | `beagle_stream_bitrate_bps` | tenant, pool, vmid, session |
| Pool | `beagle_pool_size_current` | tenant, pool |
| Pool | `beagle_pool_size_target` | tenant, pool |
| Pool | `beagle_pool_assignments_total` | tenant, pool |
| Cluster | `beagle_cluster_node_health` (0/1) | node |
| Cluster | `beagle_cluster_leader` (0/1) | node |
| Backup | `beagle_backup_last_success_ts` | tenant, job |
| Backup | `beagle_backup_duration_seconds` | tenant, job |

## Tracing

- OpenTelemetry SDK in Python-Control-Plane.
- Spans um:
  - API request handling,
  - provider operation (libvirt call, qm call),
  - placement decision,
  - migration,
  - backup job step,
  - streaming pairing.
- Default-Exporter: OTLP/grpc.

## Logs

- Strukturiertes JSON pro Process.
- `correlation_id` in jeder Log-Zeile fuer einen Request, propagiert ueber Inter-Host-RPC.
- Standard-Felder: `ts`, `level`, `service`, `node`, `tenant`, `actor`, `subject`, `event`, `correlation_id`.

## Alerts

Beispielregeln (Prometheus alerting):

- `beagle_cluster_node_health == 0 for 2m` -> page.
- `beagle_stream_rtt_ms > 80 for 5m` -> notify pool owner.
- `beagle_backup_last_success_ts < now - 26h` -> notify ops.
- `beagle_pool_size_current < beagle_pool_size_target - 1 for 10m` -> notify pool owner.

## Dashboards

Default-Grafana-Dashboards in `docs/observability/grafana/`:

- Plattform-Overview.
- Cluster-Knoten-Health.
- Pool-Health.
- Stream-Health.
- Backup-Status.

## Operator-Workflows

### Updates

- Cluster-aware rolling upgrade:
  1. Drain Knoten N (HA-VMs migrieren weg).
  2. Stoppe `beagle-control-plane`, ersetze Binaries/Configs aus `dist/`.
  3. Starte, warte auf Health-Gate.
  4. Knoten N+1.
- Endpoint-OS A/B-Update parallel verteilbar, signiertes Manifest aus Cluster.

### Maintenance Windows

- Tenant-konfigurierbare Wartungsfenster.
- Innerhalb des Fensters duerfen Pools recyceln, Nodes drainen, Updates rollen.

### Disaster Recovery

- Replication zwischen Clustern (siehe [09-backup-dr.md](09-backup-dr.md)).
- Failover-Runbook in `docs/operations/dr-failover.md` (anzulegen).

### Telemetrie-Datenschutz

- Tenant-Telemetrie ist tenant-scoped sichtbar.
- Plattform-Telemetrie nur fuer Plattform-Operatoren.
- PII (User-Mail, Hostname) optional pseudonymisierbar.

## Akzeptanzkriterien Welle 7.4.1

- Prometheus exporter aktiv auf jedem Knoten, Default-Dashboards funktionieren.
- OTLP-Trace eines Pool-Scale-Events ueber Leader -> Worker -> libvirt sichtbar.
- Audit-Export in S3 fuer 24 h Last erfolgreich (>= 100k events ohne Verlust).
