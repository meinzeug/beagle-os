# 07 — Fleet-Intelligence + Predictive Maintenance

Stand: 2026-04-24  
Priorität: 8.1.1 (Q4 2026)

---

## Motivation

### Das Problem in großen Installationen

Ein IT-Admin mit 500 Thin-Clients und 20 Nodes sieht heute nur: "Alles grün" oder "Etwas ist ausgefallen."

**Enterprise-Anforderung**: 
- Probleme voraussagen bevor sie auftreten
- "Node A wird in 3 Tagen ausfallen (Disk-SMART-Fehler eskaliert)"
- "Thin-Client B in Raum 204 hat in letzten 7 Tagen 15x neugestartet (defektes RAM?)"
- "GPU C nähert sich thermischem Limit täglich zwischen 14-16 Uhr"

### Wettbewerbslage

| Produkt | Predictive Maintenance |
|---|---|
| Beagle host | SMART-Anzeige, aber kein Trending, kein Alert |
| Citrix | Director — reaktives Monitoring, kein Predictive |
| VMware | vRealize Operations (teuer, komplex) |
| Azure | Azure Monitor (nur Azure-Hardware) |
| **Beagle GoEnterprise** | **Integriertes Predictive Maintenance für Nodes + Thin-Clients** |

---

## Schritte

### Schritt 1 — Health-Telemetrie-Kollektor

- [x] `beagle-host/services/fleet_telemetry_service.py`:
  - Node-Telemetrie: SMART-Werte (via `smartctl`), CPU-Temperatur, GPU-Temperatur, RAM-Fehler (ECC), Netzwerk-Fehler
  - Thin-Client-Telemetrie: Reboot-Count, Uptime, CPU-Temperatur, RAM-Fehler, Netzwerk-Qualität
  - Polling: alle 5 Minuten, Speicherung in Zeitreihe
- [x] Tests: `tests/unit/test_fleet_telemetry.py`

### Schritt 2 — Anomalie-Erkennung

- [x] `beagle-host/services/fleet_telemetry_service.py`: `detect_anomalies()`:
  - Vergleiche aktuelle Werte mit 30-Tage-Baseline (Mittelwert + Standardabweichung)
  - Anomalie wenn: `value > baseline + 3 * std_dev` oder linearer Trend zeigt auf kritischen Schwellwert in <7 Tagen
  - Ergebnis: `AnomalyReport {device_id, metric, current_value, baseline, trend, estimated_failure_days}`
- [x] Tests: `tests/unit/test_anomaly_detection.py`

### Schritt 3 — Predictive-Alert-System

- [x] `beagle-host/services/alert_service.py`: Erweiterung um Fleet-Alerts:
  - `disk_failure_predicted` — SMART-Trending auf Fehlergrenze
  - `gpu_thermal_limit_approaching` — GPU-Temp trendend auf >85°C
  - `thin_client_hardware_degradation` — >5 Reboots/Woche
  - `node_memory_ecc_errors` — ECC-Fehlerrate steigt
- [x] Alerts via: Web Console Notification, E-Mail, Webhook (Slack/Teams)
- [x] Tests: `tests/unit/test_fleet_alerts.py`

### Schritt 4 — Maintenance-Scheduling

- [x] `beagle-host/services/fleet_telemetry_service.py`: `schedule_maintenance(device_id, reason, suggested_window)`:
  - Legt Maintenance-Fenster an (z.B. "Nächster Sonntag 2-6 Uhr")
  - Migriert VMs vom Node weg bevor Maintenance beginnt (automatisch via Smart-Scheduler)
  - Nach Maintenance: Node wieder in Rotation
- [x] Web Console: Maintenance-Kalender pro Node/Thin-Client
- [x] Tests: `tests/unit/test_maintenance_scheduling.py`

### Schritt 5 — Fleet-Health-Dashboard

- [x] `website/ui/fleet_health.js`:
  - Heatmap: Gesundheitsstatus aller Nodes + Thin-Clients
  - Risikoliste: "Diese 5 Geräte benötigen bald Wartung"
  - Metriken-Graphen: SMART, Temperatur, Fehlerrate über Zeit
  - Hardware-Lifecycle: Gerätealter, Garantiestatus, empfohlener Austausch

---

## Testpflicht nach Abschluss

- [x] Telemetrie: Node-SMART-Werte werden korrekt gesammelt und gespeichert.
- [x] Anomalie: Simulierter Disk-Fehler-Trend → Anomalie erkannt nach 7 Tagen.
- [x] Alert: Disk-Failure-Predicted Alert ausgelöst, Web-Notification erscheint.
- [x] Maintenance: Maintenance-Fenster angelegt, VMs automatisch migriert.

## Update 2026-04-28 (Fleet-Telemetrie/Alerts in Control Plane und WebUI verdrahtet)

- Control Plane:
  - `fleet_http_surface.py` liefert jetzt echte Fleet-Health-Routen statt nur UI-Platzhaltern:
    - `GET /api/v1/fleet/anomalies`
    - `GET /api/v1/fleet/maintenance`
    - `GET /api/v1/fleet/alerts`
    - `GET /api/v1/fleet/alerts/rules`
    - `POST /api/v1/fleet/alerts/rules`
    - `PUT /api/v1/fleet/alerts/rules/{rule_id}`
    - `POST /api/v1/fleet/alerts/{alert_id}/resolve`
  - `alert_service.py` seeded jetzt reproduzierbare Default-Regeln fuer Disk-/GPU-/Reboot-/ECC-Alerts
  - `service_registry.py` verdrahtet Fleet-Telemetry und Alert-Service jetzt produktiv inklusive Webhook-Dispatch ueber den bestehenden `webhook_service`
- Thin-Client-Runtime:
  - `device_sync.sh` liefert jetzt neben WireGuard-/Runtime-Status auch Health-Metriken:
    - `uptime_hours`
    - `reboot_count_7d`
    - `cpu_temp_c`
    - `network_errors`
  - Boot-History wird lokal persistiert, damit Reboot-Trends ueber den Runtime-Sync sichtbar werden
- Endpoint-Sync:
  - `endpoint_http_surface.py` ingestet die Runtime-Metriken jetzt direkt in `fleet_telemetry_service`
  - Anomalien werden beim Device-Sync sofort gegen `alert_service` geprueft
  - der Sync-Response liefert `health.anomaly_count`, `health.alert_count` und `health.new_alert_count`
- WebUI:
  - `website/ui/fleet_health.js` zeigt jetzt eine echte `Predictive Alerts`-Flaeche
  - offene Alerts koennen im Fleet-Panel quittiert werden
  - Alert-Regeln koennen direkt in der WebUI angelegt, angepasst und aktiviert/deaktiviert werden
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_fleet_http_surface.py`
  - `tests/unit/test_endpoint_http_surface.py`
  - `tests/unit/test_device_sync_runtime.py`
  - `tests/unit/test_fleet_ui_regressions.py`
  - `tests/unit/test_authz_policy.py`
