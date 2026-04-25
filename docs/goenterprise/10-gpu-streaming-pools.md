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
- [ ] Tests: `tests/unit/test_gpu_inventory.py`

### Schritt 2 — GPU-Zuweisung-Modi

- [ ] `providers/beagle/libvirt_provider.py`: Drei Zuweisungs-Modi:
  1. **Passthrough** (`gpu_mode=passthrough`): ganze GPU an eine VM — maximale Performance, exklusiv
  2. **Time-Slicing** (`gpu_mode=timeslice`): GPU teilt sich zwischen N VMs (NVIDIA MIG-ähnlich via CUDA time-slicing) — für leichte CAD/Office-3D-Workloads
  3. **vGPU** (`gpu_mode=vgpu`): NVIDIA vGPU wenn Hardware es unterstützt — vollständige GPU-Isolation per VM
- [ ] Pool-Manager: Pool-Typ `gpu_passthrough` | `gpu_timeslice` | `gpu_vgpu`
- [ ] Tests: `tests/unit/test_gpu_assignment_modes.py`

### Schritt 3 — GPU-Auslastungs-Tracking + Stream-Routing

- [x] `beagle-host/services/gpu_metrics_service.py` (impl. in gpu_streaming_service.py):
  - Alle 10s: GPU-Auslastung (%) + VRAM-Nutzung + GPU-Temperatur + Encoder-Auslastung (NVENC) pro VM
  - Stream-Routing: wenn GPU-Encoder (NVENC) überlastet (>90%) → warne oder migriere VM auf weniger ausgelasteten Node
- [ ] Integration mit AI-Scheduler (Plan 04): GPU-Auslastungs-Prognose für Placement
- [ ] Tests: `tests/unit/test_gpu_metrics.py`

### Schritt 4 — GPU-Pool-Rebalancing

- [x] `beagle-host/services/gpu_pool_rebalancer.py` (impl. in gpu_streaming_service.py):
  - Erkennt: GPU A bei 95%, GPU B bei 20% → empfiehlt VM-Migration
  - Berücksichtigt `gpu_class`: Gaming-VMs nur auf `class=gaming` GPUs migrieren
  - Auto-Modus: führt Migration durch (wenn konfiguriert)
- [ ] Web Console: GPU-Pool-Übersicht mit Auslastungs-Bars, Migration-Button
- [ ] Tests: `tests/unit/test_gpu_rebalancing.py`

### Schritt 5 — GPU-Dashboard + Capacity Planning

- [ ] `website/ui/gpu_dashboard.js`:
  - Echtzeit-Grid: alle GPUs, Auslastung, Temperatur, aktive VMs
  - Historisch: GPU-Auslastung letzte 30 Tage (Peak-Zeiten erkennen)
  - Capacity-Planning: "Bei aktuellem Wachstum benötigst du in 3 Monaten eine weitere GPU"
  - VRAM-Nutzung pro VM (für vGPU/Time-Slicing Planung)

---

## Testpflicht nach Abschluss

- [ ] Inventory: Alle GPUs auf allen Nodes korrekt erkannt und klassifiziert.
- [ ] Passthrough: VM bekommt exklusive GPU, andere VMs haben keinen Zugriff.
- [ ] Time-Slicing: 3 VMs teilen sich eine GPU, alle drei haben Encoder-Zugriff.
- [ ] Metriken: GPU-Auslastung wird korrekt pro VM getrackt.
- [ ] Rebalancing: Überlastete GPU → Empfehlung korrekt, Migration erfolgreich.
