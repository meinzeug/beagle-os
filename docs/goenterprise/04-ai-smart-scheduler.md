# 04 — KI-basierter Smart-Scheduler

Stand: 2026-04-24  
Priorität: 8.1.0 (Q3 2026)

---

## Motivation

### Heutiger Scheduler (statisch)

Der aktuelle Beagle-Scheduler platziert VMs nach simplen Regeln:
1. Node mit meisten freien Ressourcen gewinnt
2. Anti-Affinity wird beachtet
3. GPU-Klassen werden gemappt

**Problem**: Keine Lernfähigkeit. Eine VM die immer morgens 100% CPU braucht und nachmittags idle ist, wird genauso behandelt wie eine 24/7-Last-VM.

### Was Konkurrenten bieten

| Produkt | Scheduling-Feature |
|---|---|
| Citrix | Resource Limits + Load Evaluator (statische Schwellen) |
| VMware DRS | Automatisches Load-Balancing (reaktiv, nach Auslastung) |
| Azure | Auto-Scale (scale-out bei Last, scale-in bei Idle) |
| **Beagle GoEnterprise** | **Prädiktiver AI-Scheduler (lernt Muster, handelt vorausschauend)** |

### Beagle-Differenzierung

- **Prädiktiv statt reaktiv**: Der Scheduler lernt, wann bestimmte User/Pools Last produzieren, und startet VMs schon bevor die Last kommt
- **Kostenbewusst**: Beim Scheduling wird Hardware-Kosten (Plan 05) berücksichtigt — billigste Platzierung bei gleicher Performance
- **Gaming-aware**: Gaming-Sessions haben harte Latenz-Anforderungen; der Scheduler bevorzugt Nodes mit niedrigster RTT zum Client

---

## Schritte

### Schritt 1 — Metriken-Kollektor (Grundlage für AI)

- [x] `beagle-host/services/metrics_collector.py`:
  - Alle 30s: CPU, RAM, GPU-Auslastung pro VM + Node sammeln
  - Alle 5min: aggregierte Metriken in Zeitreihe speichern (JSON/SQLite in `/var/lib/beagle/metrics/`)
  - Retention: letzte 90 Tage
- [x] Tests: `tests/unit/test_metrics_collector.py`

### Schritt 2 — Auslastungsmuster-Erkennung

- [x] `beagle-host/services/workload_pattern_analyzer.py`:
  - Analyse der letzten 14 Tage Metriken
  - Erkennt Muster: "Montag-Freitag 8-17h: 90% CPU", "Nachts: 5% CPU"
  - Produziert `WorkloadProfile` je VM: `{peak_hours, idle_hours, avg_cpu, avg_ram, avg_gpu}`
  - Algorithmus: gleitender Durchschnitt + einfache Fourier-Analyse für Periodizität
- [x] Tests: `tests/unit/test_workload_pattern.py`

### Schritt 3 — Prädiktiver Placement-Algorithmus

- [x] `beagle-host/services/smart_scheduler.py`:
  - Vor jeder Placement-Entscheidung: `predict_load(vmid, target_time)` abfragen
  - Entscheidet Placement basierend auf: erwarteter Last der VM + aktueller Node-Auslastung + prognostizierter Node-Auslastung (nächste 4h)
  - Pre-warming: Wenn eine VM in 15min gebraucht wird (Pool-Schedule bekannt) → VM schon starten
  - `SmartPlacementResult`: `{node, reason, confidence, alternative_nodes}`
- [x] Integration mit `pool_manager.py`: `smart_scheduler` optional als Drop-In für `pick_node`
- [x] Tests: `tests/unit/test_smart_scheduler.py`

### Schritt 4 — Live-Rebalancing (DRS-ähnlich)

- [x] `beagle-host/services/smart_scheduler.py`: `rebalance_cluster()`:
  - Analyse: Welche Nodes sind über/unter ausgelastet?
  - Empfehlung: "Migriere VM X von Node A nach Node B (Node A bei 90%, Node B bei 30%)"
  - Automatic-Modus: führt Migration automatisch durch (wenn konfiguriert)
  - Conservative-Modus: nur Empfehlungen, Admin bestätigt
- [x] Web Console: Rebalancing-Empfehlungen mit 1-Click-Ausführung
- [ ] Tests: `tests/unit/test_cluster_rebalancing.py`

### Schritt 5 — Scheduler-Insights Dashboard

- [x] `website/ui/scheduler_insights.js`:
  - [x] Heatmap: Node-Auslastung über Zeit (letzte 7 Tage)
  - Top-5 empfohlene Migrations
  - [x] Prognostizierte Last (nächste 24h) per Node
  - [x] "Saved CPU-Hours" durch Pre-warming (wie viele User haben sofort eine VM bekommen vs. gewartet)
  - [x] Green-Hours-Konfiguration und aktiver Green-Window-Status im Dashboard
  - [x] Stündliche Heatmap der letzten 7 Tage pro Node
  - [x] Saved-CPU-Hours-Auswertung nach Pool und User
  - [x] Prewarm Hit-/Miss-Telemetrie und Warm-Pool-Empfehlungen im Dashboard

---

## Testpflicht nach Abschluss

- [ ] Muster-Erkennung: Nach 14 Tagen simulierter Metriken erkennt der Analyzer korrekte Peak-Stunden.
- [ ] Prädiktiver Scheduler: VM-Start 10min vor Peak → Nutzer wartet 0s statt 30s.
- [ ] Rebalancing: Überlasteter Node (>85%) → Scheduler empfiehlt VM-Migration auf freien Node.
- [x] Dashboard: Heatmap zeigt korrekte historische Auslastung.
