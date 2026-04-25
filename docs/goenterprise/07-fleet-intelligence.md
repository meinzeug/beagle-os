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
| Proxmox | SMART-Anzeige, aber kein Trending, kein Alert |
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
- [ ] Tests: `tests/unit/test_anomaly_detection.py`

### Schritt 3 — Predictive-Alert-System

- [ ] `beagle-host/services/alert_service.py`: Erweiterung um Fleet-Alerts:
  - `disk_failure_predicted` — SMART-Trending auf Fehlergrenze
  - `gpu_thermal_limit_approaching` — GPU-Temp trendend auf >85°C
  - `thin_client_hardware_degradation` — >5 Reboots/Woche
  - `node_memory_ecc_errors` — ECC-Fehlerrate steigt
- [ ] Alerts via: Web Console Notification, E-Mail, Webhook (Slack/Teams)
- [ ] Tests: `tests/unit/test_fleet_alerts.py`

### Schritt 4 — Maintenance-Scheduling

- [x] `beagle-host/services/fleet_telemetry_service.py`: `schedule_maintenance(device_id, reason, suggested_window)`:
  - Legt Maintenance-Fenster an (z.B. "Nächster Sonntag 2-6 Uhr")
  - Migriert VMs vom Node weg bevor Maintenance beginnt (automatisch via Smart-Scheduler)
  - Nach Maintenance: Node wieder in Rotation
- [ ] Web Console: Maintenance-Kalender pro Node/Thin-Client
- [ ] Tests: `tests/unit/test_maintenance_scheduling.py`

### Schritt 5 — Fleet-Health-Dashboard

- [ ] `website/ui/fleet_health.js`:
  - Heatmap: Gesundheitsstatus aller Nodes + Thin-Clients
  - Risikoliste: "Diese 5 Geräte benötigen bald Wartung"
  - Metriken-Graphen: SMART, Temperatur, Fehlerrate über Zeit
  - Hardware-Lifecycle: Gerätealter, Garantiestatus, empfohlener Austausch

---

## Testpflicht nach Abschluss

- [ ] Telemetrie: Node-SMART-Werte werden korrekt gesammelt und gespeichert.
- [ ] Anomalie: Simulierter Disk-Fehler-Trend → Anomalie erkannt nach 7 Tagen.
- [ ] Alert: Disk-Failure-Predicted Alert ausgelöst, Web-Notification erscheint.
- [ ] Maintenance: Maintenance-Fenster angelegt, VMs automatisch migriert.
