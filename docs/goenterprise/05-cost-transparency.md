# 05 — Cost-Transparency + Chargeback

Stand: 2026-04-24  
Priorität: 8.1.0 (Q3 2026)

---

## Motivation

### Das Problem in Enterprise-Umgebungen

IT-Abteilungen investieren in Beagle-Server, aber können den Abteilungen nicht zeigen: 
"Marketing hat diesen Monat 1.200 GPU-Stunden verbraucht und kostet uns €3.400."

**Ohne Chargeback ist Virtualisierung ein unsichtbares Kostenzentrum.**

### Was Konkurrenten bieten

| Produkt | Cost-Transparenz |
|---|---|
| Azure Virtual Desktop | Azure-Billing mit per-User-Reporting |
| AWS WorkSpaces | Pay-per-Use, AWS Cost Explorer Integration |
| Citrix DaaS | Citrix Analytics - nur in teurer Cloud-Version |
| Beagle host | **Gar nichts** |
| VMware Horizon | Optional mit vRealize Operations ($$$) |
| **Beagle GoEnterprise** | **Integriert, On-Prem, Abteilungs-granular, kostenlos** |

---

## Schritte

### Schritt 1 — Ressourcen-Preismodell

- [x] `beagle-host/services/cost_model_service.py`:
  - Konfigurierbares Preismodell: `cpu_hour_cost`, `ram_gb_hour_cost`, `gpu_hour_cost`, `storage_gb_month_cost`
  - Eingabe: tatsächliche Hardware-Anschaffungskosten + Abschreibungszeitraum + Stromkosten
  - Kalkuliert `hourly_rate_per_vm(vmid)` basierend auf zugewiesenen Ressourcen
- [x] Admin-Konfiguration in Web Console: Preismodell-Editor
- [x] Tests: `tests/unit/test_cost_model.py`

### Schritt 2 — Nutzungs-Tracking per Nutzer/Abteilung

- [x] `beagle-host/services/usage_tracking_service.py`:
  - Jede Session: `user_id`, `department`, `pool_id`, `vm_id`, `start_time`, `end_time`, `resources_used`
  - Tägliche Aggregation: Kosten pro User, pro Abteilung, pro Pool
  - Speicherung in SQLite: `/var/lib/beagle/usage/usage.db`
- [x] Integration mit Session-Manager: bei `session_end` → `record_usage(session)`
- [x] Tests: `tests/unit/test_usage_tracking.py`

### Schritt 3 — Chargeback-Reports

- [x] `beagle-host/services/cost_model_service.py`: `generate_chargeback_report(month, department=None)`:
  - Ausgabe: CSV + JSON
  - Felder: `department`, `user`, `sessions`, `cpu_hours`, `gpu_hours`, `storage_gb`, `total_cost`
  - Drill-down: von Abteilung → User → einzelne Session
- [x] Control-Plane-Surface: `GET /api/v1/costs/chargeback?month=2025-04&department=marketing`, `GET /api/v1/costs/chargeback.csv`, `GET /api/v1/costs/budget-alerts`
- [x] Tests: `tests/unit/test_chargeback_report.py`

### Schritt 4 — Budget-Alerts

- [x] `beagle-host/services/cost_model_service.py`: `BudgetAlert`:
  - `department`, `monthly_budget`, `alert_at_percent` (z.B. 80%)
  - E-Mail/Webhook wenn Schwelle erreicht
- [x] Web Console: Budget-Verwaltung pro Abteilung
- [x] Tests: `tests/unit/test_budget_alert.py`

### Schritt 5 — Cost-Dashboard

- [x] `website/ui/cost_dashboard.js`:
  - Monatskosten nach Abteilung (Balkendiagramm)
  - Top-10 kostenintensivste VMs
  - GPU-Cost vs CPU-Cost Aufteilung
  - Forecast: "Wenn aktuelles Nutzungsmuster anhält, Monatskosten = €X"
  - Export als PDF/CSV

---

## Testpflicht nach Abschluss

- [ ] Kosten-Kalkulation: GPU-VM mit 2 CPU, 8GB RAM, 1 GPU kostet nach Preismodell korrekt.
- [ ] Tracking: 5 Sessions für User "alice" aus "marketing" → Report zeigt korrekte Summe.
- [ ] Chargeback-CSV: Export enthält alle Sessions, Kosten korrekt summiert.
- [ ] Budget-Alert: Abteilung bei 85% Budget → Alert ausgelöst.

---

## Einzigartigkeit

**Kein On-Prem Open-Source VDI-Stack bietet integriertes Chargeback.**
Beagle host: nichts. OpenStack: Ceilometer existiert, aber nicht VDI-integriert. XCP-ng: nichts.
Beagle GoEnterprise: vollständig integriert, konfigurierbar, free of charge.
