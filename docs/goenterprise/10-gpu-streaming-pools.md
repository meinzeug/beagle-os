# 10 — Intelligente GPU-Pool-Zuweisung + Stream-Routing

Stand: 2026-04-24  
Priorität: 8.2.1 (Q2 2027)

---

## Motivation

### Das Problem mit GPU-Ressourcen

GPUs sind der teuerste Teil einer Beagle-Infrastruktur.
Heute: GPU wird einem VM-Slot fix zugewiesen (Passthrough) — auch wenn die VM 90% der Zeit idle ist.

**Enterprise-Anforderung**: GPU-Ressourcen dynamisch zwischen VMs aufteilen. GPU-Nutzung tracken. Engpässe vorhersagen.

### Wettbewerbslage

| Produkt | GPU-Handling |
|---|---|
| Citrix | NVIDIA vGPU Support (teuer, proprietäre Treiber) |
| VMware | NVIDIA vGPU + MxGPU (AMD) — teuer |
| Azure | NV-series VMs (N-Series GPU), nur Cloud |
| Proxmox | GPU-Passthrough manuell, kein Pool-Management |
| **Beagle GoEnterprise** | **Dynamische GPU-Pools: Passthrough + vGPU + Time-Slicing, integriert** |

---

## Schritte

### Schritt 1 — GPU-Inventory + Capability-Tracking

- [x] `beagle-host/services/gpu_inventory_service.py` (impl. in gpu_streaming_service.py):
  - Erkennt alle GPUs pro Node: `nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv`
  - Klassifiziert: `class=gaming` (RTX consumer) | `class=workstation` (RTX Pro/Quadro) | `class=compute` (A100/H100)
  - Felder: `gpu_id`, `node_id`, `model`, `vram_gb`, `supports_vgpu`, `supports_timeslice`, `current_assignment`
- [x] Tests: `tests/unit/test_gpu_inventory.py`

### Schritt 2 — GPU-Zuweisung-Modi

- [x] `beagle-host/services/gpu_assignment_modes.py`: Drei Zuweisungs-Modi:
  1. **Passthrough** (`gpu_mode=passthrough`): ganze GPU an eine VM — maximale Performance, exklusiv
  2. **Time-Slicing** (`gpu_mode=timeslice`): GPU teilt sich zwischen N VMs (NVIDIA MIG-ähnlich via CUDA time-slicing) — für leichte CAD/Office-3D-Workloads
  3. **vGPU** (`gpu_mode=vgpu`): NVIDIA vGPU wenn Hardware es unterstützt — vollständige GPU-Isolation per VM
- [x] Pool-Manager: Pool-Typ `gpu_passthrough` | `gpu_timeslice` | `gpu_vgpu` (in `core/virtualization/desktop_pool.py` + `pool_manager.py` routing)
- [x] Tests: `tests/unit/test_gpu_assignment_modes.py` (28 Tests: 11 passthrough, 9 timeslice, 8 vgpu)

### Schritt 3 — GPU-Auslastungs-Tracking + Stream-Routing

- [x] `beagle-host/services/gpu_metrics_service.py` (impl. in gpu_streaming_service.py):
  - Alle 10s: GPU-Auslastung (%) + VRAM-Nutzung + GPU-Temperatur + Encoder-Auslastung (NVENC) pro VM
  - Stream-Routing: wenn GPU-Encoder (NVENC) überlastet (>90%) → warne oder migriere VM auf weniger ausgelasteten Node
- [x] Integration mit AI-Scheduler (Plan 04): GPU-Auslastungs-Prognose für Placement
  - [x] `NodeCapacity.gpu_utilization_pct` Feld ergänzt (smart_scheduler.py)
  - [x] `pick_node()` berücksichtigt GPU-Auslastung als Scoring-Faktor (Threshold 85%) und schließt überlastete Nodes aus
  - [x] `NodeCapacity.predicted_gpu_utilization_pct_4h` ergänzt; `pick_node()` bewertet jetzt die schlechtere von aktueller und prognostizierter GPU-Last und schließt damit Nodes aus, die in Kürze GPU-seitig überlaufen würden
- [x] Tests: `tests/unit/test_gpu_metrics.py`

### Schritt 4 — GPU-Pool-Rebalancing

- [x] `beagle-host/services/gpu_pool_rebalancer.py` (impl. in gpu_streaming_service.py):
  - Erkennt: GPU A bei 95%, GPU B bei 20% → empfiehlt VM-Migration
  - Berücksichtigt `gpu_class`: Gaming-VMs nur auf `class=gaming` GPUs migrieren
  - Auto-Modus: führt Migration durch (wenn konfiguriert)
- [x] Web Console: GPU-Pool-Übersicht mit Auslastungs-Bars, Migration-Button
- [x] Tests: `tests/unit/test_gpu_rebalancing.py`

### Schritt 5 — GPU-Dashboard + Capacity Planning

- [x] `website/ui/gpu_dashboard.js`:
  - Echtzeit-Grid: alle GPUs, Auslastung, Temperatur, aktive VMs (mit modeBadge + tempBadge)
  - Historisch: GPU-Auslastung letzte 30 Tage (Peak-Zeiten erkennen) — API-side (Metriken-Endpunkt)
  - Capacity-Planning: "Bei aktuellem Wachstum benötigst du in 3 Monaten eine weitere GPU" (capacityPlanningHtml)
  - VRAM-Nutzung pro VM (für vGPU/Time-Slicing Planung) (vram_used_gb in assignments table)

---

## Testpflicht nach Abschluss

- [x] Inventory: Alle GPUs auf allen Nodes korrekt erkannt und klassifiziert (test_gpu_inventory.py).
- [x] Passthrough: VM bekommt exklusive GPU, andere VMs haben keinen Zugriff (test_gpu_assignment_modes.py TestPassthrough).
- [x] Time-Slicing: 3 VMs teilen sich eine GPU, alle drei haben Encoder-Zugriff (test_gpu_assignment_modes.py TestTimeslice).
- [x] Metriken: GPU-Auslastung wird korrekt pro VM getrackt (test_gpu_metrics.py).
- [x] Rebalancing: Überlastete GPU → Empfehlung korrekt, Migration erfolgreich (test_gpu_rebalancing.py).

## Update (2026-04-27, GPU-Zeitfenster final geschlossen)

- `beagle-host/services/smart_scheduler.py` bewertet fuer GPU-Workloads jetzt nicht nur die aktuelle, sondern auch die prognostizierte GPU-Auslastung (`predicted_gpu_utilization_pct_4h`).
- Neue Regressionen in `tests/unit/test_smart_scheduler.py` decken ab:
  - Node mit heute niedriger, aber in 4h ueberlasteter GPU wird fuer neue GPU-Workloads nicht mehr bevorzugt
  - prognostizierte GPU-Ueberlastung schlaegt den Threshold-Guard genauso wie aktuelle Ueberlastung
- Reproduzierbarer Host-Smoke auf `srv2` ergaenzt:
  - `scripts/test-gpu-passthrough-guest-smoke.sh`
  - erzeugt eine transiente KVM-VM mit GTX 1080 + Audio als Hostdevs
  - prueft die reale PCI-Sicht im Gast ueber serielle Marker
  - validiert erfolgreich `10de:1b80` und `10de:10f0`
- Live validiert:
  - `srv2`: `scripts/test-gpu-passthrough-guest-smoke.sh` -> Gast erkennt GTX 1080 + Audio
  - `srv2`: `scripts/test-gpu-inventory-smoke.py` -> `PLAN12_GPU_SMOKE=PASS`

Damit sind die offenen Punkte, die real eine GPU auf `srv2` benoetigen, fuer den aktuellen Planstand geschlossen. Ein voller NVIDIA-Treiber-/Streaming-Benchmark im Gast bleibt optional und ist kein Pflichtblocker mehr.
