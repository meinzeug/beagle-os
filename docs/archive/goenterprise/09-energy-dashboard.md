# 09 — Energy-Dashboard + Carbon-Footprint

Stand: 2026-04-24  
Priorität: 8.2.0 (Q1 2027)

---

## Motivation

### Warum Energy-Tracking ein Enterprise-Killer-Feature ist

In 2024-2025 wurde in der EU die **CSRD (Corporate Sustainability Reporting Directive)** verpflichtend.
Unternehmen mit >500 Mitarbeitern müssen Scope-2-Emissionen (IT-Infrastruktur) dokumentieren.

**Kein On-Prem VDI-Produkt bietet heute integriertes Carbon-Tracking.**

**Beagle GoEnterprise** als erstes On-Prem VDI mit:
- Echtzeit-Energie-Verbrauch je VM, Pool, Abteilung
- CO₂-Footprint basierend auf lokalem Strommix
- Automatische CSRD-Export-Reports

### Wettbewerbslage

| Produkt | Energie/CO₂ |
|---|---|
| Azure / AWS | Cloud-Anbieter haben eigene Carbon-Dashboards (aber nur ihre Cloud) |
| Citrix | Nichts integriert |
| Beagle host | Nichts |
| VMware | vRealize Operations Energy (nur auf VMware-Hardware, teuer) |
| **Beagle GoEnterprise** | **Integriert, On-Prem, CSRD-ready** |

---

## Schritte

### Schritt 1 — Energie-Metriken sammeln

- [x] `beagle-host/services/energy_service.py`:
  - Pro Node: CPU-Package-Power via RAPL (`/sys/class/powercap/`), GPU-Power via NVML (`nvidia-smi`), PDU-Power falls vorhanden (SNMP)
  - Kalkuliert VM-Anteil: `vm_power = node_power * (vm_cpu_shares / total_cpu_shares)`
  - Zeitreihe: alle 60s, Retention 365 Tage
- [x] Tests: `tests/unit/test_energy_service.py`

### Schritt 2 — CO₂-Faktor-Konfiguration

- [x] `beagle-host/services/energy_service.py`: `CarbonConfig`:
  - `co2_grams_per_kwh` — konfigurierbar (z.B. Deutscher Strommix 2024: ~400g/kWh, Norwegen: ~30g/kWh)
  - Stündlich aktualisierbar (für Echtzeit-Spotmarkt-Strommix per API)
  - Kalkuliert: `co2_grams = energy_kwh * co2_grams_per_kwh`
- [x] Admin-Konfiguration in Web Console
- [x] Tests: `tests/unit/test_carbon_calculation.py`

### Schritt 3 — Energie-Kostenintegration

- [x] Integration mit Plan 05 (Cost-Transparency):
  - Energiekosten als separate Kostenkomponente: `energy_cost = energy_kwh * electricity_price_per_kwh`
  - `electricity_price_per_kwh` konfigurierbar (z.B. 0.30 €/kWh)
  - Chargeback-Report enthält Energiekosten separat ausgewiesen
- [x] Tests: `tests/unit/test_energy_cost_integration.py`

### Schritt 4 — Green-Scheduling

- [x] Integration mit Plan 04 (AI-Scheduler):
  - `green_scheduling_enabled`: wenn aktiviert → bevorzuge Scheduling zu Zeiten mit niedrigem CO₂-Faktor (z.B. Mittagsspitze Solar)
  - [x] "Green Hours": konfigurierbare Zeiten mit bevorzugtem Batch-Scheduling
  - [x] VM-Starts für nicht-dringende Workloads auf "Green Hours" verschieben
- [x] Tests: `tests/unit/test_green_scheduling.py`

### Schritt 5 — CSRD-Export + Energie-Dashboard

- [x] `beagle-host/services/energy_service.py`: `generate_csrd_report(year, quarter)`:
  - Ausgabe: JSON + Excel (via openpyxl) im CSRD Scope-2-Format
  - Felder: Zeitraum, Total-kWh, Total-CO₂, Aufschlüsselung nach Abteilung
- [x] `website/ui/energy_dashboard.js`:
  - Echtzeit-Energie-Verbrauch (kW aktuell)
  - CO₂-Footprint: heute, diese Woche, dieses Jahr
  - [x] Ranking: effizienteste vs. energieintensivste VMs
  - [x] "Grüne Stunden" Heatmap (wann ist der Strommix am saubersten)
  - [x] stündliches CO₂-/Strompreisprofil als editierbarer 24h-Feed
  - [x] Import-Pfad für stündliche Profile über die Control Plane
  - [x] externer Feed-Import mit Retry/Backoff und Alerting bei Fehlschlag
- [x] Control-Plane-Surface: `GET /api/v1/energy/nodes`, `GET /api/v1/energy/trend`, `GET /api/v1/energy/csrd?year=...&quarter=...`
- [x] Tests: `tests/unit/test_csrd_export.py`

## Update (2026-04-28, Plan-09-Restpunkt externer Feed-Importjob geschlossen)

- Der bestehende Importpfad `POST /api/v1/energy/hourly-profile/import` unterstuetzt jetzt neben CSV/Profile-Input auch direkte externe JSON-Feeds via `feed_url`.
- Der Feed-Fetch laeuft mit konfigurierbarem Timeout/Retry/Backoff (`timeout_seconds`, `retries`, `retry_backoff_seconds`; Defaults aus Runtime-Env).
- Bei wiederholtem Fehlschlag wird ein Fleet-Alert `energy_feed_import_failed` mit Kontext erzeugt (Console/Webhook), damit Operatoren den Ausfall sofort sehen.
- Fehlerpfade sind jetzt sauber als API-Status modelliert:
  - ungültige Payload/URL -> `400`
  - Upstream-Feed nach Retry weiterhin nicht erreichbar -> `502`
- Neue Regressionen:
  - `tests/unit/test_energy_feed_import.py`
  - `tests/unit/test_control_plane_read_surface.py` (Error-Mapping Importpfad)
- Validierung:
  - lokal + `srv1` reproduzierbar im Fokus-Scope: `50 passed`

---

## Testpflicht nach Abschluss

- [x] RAPL-Metriken: CPU-Power wird korrekt gelesen und pro VM anteilig berechnet.
- [x] CO₂: Bei 100W über 1h mit 400g/kWh → 40g CO₂ korrekt kalkuliert.
- [x] Chargeback: Energie-Kosten in Report korrekt aufgeschlüsselt.
- [x] CSRD-Export: Export enthält korrekten Scope-2-Wert für Quartal.

---

## Unique Selling Point

**Erster On-Prem Open-Source VDI-Stack mit CSRD-konformem Carbon-Reporting.**
Für EU-Unternehmen unter CSRD-Pflicht ist dies kein Nice-to-have — es ist Compliance-Anforderung.
