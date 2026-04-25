# 03 — Gaming-Kiosk-Pool-Management

Stand: 2026-04-24  
Priorität: 8.0.1

---

## Motivation — Ein Feature das kein Konkurrent hat

**Kein einziger VDI-Anbieter (Citrix, VMware, Azure, AWS) bietet Gaming-Kiosk-Pools an.**

Beagle OS ist die einzige Virtualisierungsplattform die:
1. Gaming-Grade Streaming (Moonlight/Sunshine) nativ integriert hat
2. Einen Kiosk-Modus für Endgeräte bietet
3. Beides auf derselben Hardware/Plattform kombinieren kann

### Zielkunden

| Kunde | Use-Case | Marktgröße |
|---|---|---|
| **Esports-Arenas** | 50-500 Gaming-PCs als VMs auf zentraler GPU-Hardware | ~$2Mrd global |
| **Schulen/Universitäten** | Gaming-Unterricht, Game-Design-Kurse, IT-Labore | ~$15Mrd EdTech |
| **Internet-Cafes 2.0** | Alle Games in der Cloud, kein lokales Installieren | ~$1Mrd |
| **Militär/Behörden** | Sichere Gaming-Räume für Entspannung, E-Sport-Teams | Enterprise-Vertrag |
| **Game-Publishing-QA** | Game-QA-Teams testen auf virtualisierten GPU-VMs | ~$500Mio |
| **Game-Streaming-Dienste** | Unternehmen wie Shadow PC nutzen KVM-basierte Infra | ~$5Mrd Cloud-Gaming |

### Was heute vorhanden ist

- `beagle-kiosk/` — Electron-basierter Game-Launcher für lokales Gaming
- GPU-Passthrough-Service (`gpu_passthrough_service.py`)
- Pool-Manager mit VDI-Pools

### Was fehlt

- Kein "Gaming Pool" Typ in Pool-Manager (nur "desktop" heute)
- Keine automatische Game-Installation in VMs (Steam/Epic/GOG)
- Kein "Session-Time-Limit" für Kiosk-Betreiber (Abrechnung nach Zeit)
- Kein "Gaming-Performance-Reporting" (FPS, Latenz, GPU-Auslastung)
- Kein "Kiosk-Controller" (Betreiber sieht alle aktiven Gaming-Sessions live)
- Keine Integration mit Steam-Family-Sharing / Enterprise-Lizenzen

---

## Schritte

### Schritt 1 — Pool-Typ "gaming" einführen

- [x] `core/virtualization/desktop_pool.py`: `pool_type` Feld erweitern: `desktop` | `gaming` | `kiosk`
  - `gaming`-Pools: GPU-Slot-Pflicht, höhere Standard-Bitrate (50-100Mbps), 60/120/144fps Standard
  - `kiosk`-Pools: Session-Time-Limit, keine Persistenz (VM reset nach Session), keine Datei-Uploads
- [ ] `beagle-host/services/pool_manager.py`: Pool-Typ-spezifische Allocation-Logik
  - Gaming-Pool: blockiert wenn keine GPU verfügbar (kein Soft-Fallback auf CPU)
- [ ] Web Console: Pool-Typ-Auswahl beim Erstellen
- [x] Tests: `tests/unit/test_gaming_pool.py`

### Schritt 2 — Session-Time-Limit + Kiosk-Abrechnung

- [x] `core/virtualization/desktop_pool.py`: `session_time_limit_minutes` (0 = unbegrenzt)
- [ ] `beagle-host/services/pool_manager.py`:
  - Beim Allocate: `session_expires_at = now + time_limit`
  - Background-Task: Session automatisch terminieren wenn abgelaufen
  - `session_cost_per_minute` Feld (für Abrechnung)
- [ ] `beagle-host/bin/beagle-control-plane.py`: `GET /api/v1/sessions/{id}/time-remaining`
- [ ] Web Console: Timer-Anzeige in Session-Übersicht (Kiosk-Betreiber sieht wie lang jede Session noch läuft)
- [ ] Tests: `tests/unit/test_session_time_limit.py`

### Schritt 3 — Kiosk-Controller-Dashboard

- [ ] `website/ui/kiosk_controller.js`: Echtzeit-Dashboard für Kiosk-Betreiber:
  - Grid aller Kiosk-Stationen (VM-Status, aktiver User, laufendes Spiel, verbleibende Zeit)
  - Aktionen: Session verlängern, vorzeitig beenden, VM-Reset anstoßen
  - Live-Metriken: GPU-Auslastung, FPS, Latenz der aktiven Streams
- [ ] Getrennte RBAC-Rolle: `kiosk_operator` (darf nur Kiosk-Sessions verwalten, keine Admin-Rechte)
- [ ] Tests: RBAC-Test für `kiosk_operator`

### Schritt 4 — Gaming-Performance-Reporting

- [x] `beagle-host/services/gaming_metrics_service.py`:
  - Aggregiert Stream-Health-Daten (RTT, FPS, dropped frames) + GPU-Metriken pro Session
  - Stündliche/tägliche Reports: Durchschnittliche FPS, Peak-Stunden, populärste Spiele (via Window-Title aus Sunshine)
  - Alert wenn FPS < 30 oder RTT > 50ms
- [ ] Web Console: Gaming-Metrics-Dashboard mit Graphen
- [ ] Tests: `tests/unit/test_gaming_metrics.py`

### Schritt 5 — VM-Reset-nach-Session (Stateless Gaming)

- [ ] `providers/beagle/libvirt_provider.py`: `reset_vm_to_snapshot(vmid, snapshot_name)`
  - Nach jeder Session: VM zurück auf sauberes Snapshot setzen
  - Kein User-Daten-Rückstand zwischen Sessions (Datenschutz + Hygiene)
- [ ] Pool-Manager: `on_session_release` Callback → Reset-VM wenn `pool_type=kiosk`
- [ ] Tests: `tests/unit/test_vm_stateless_reset.py`

---

## Testpflicht nach Abschluss

- [ ] Gaming-Pool: Allocation ohne verfügbare GPU schlägt fehl (kein CPU-Fallback).
- [ ] Session-Time-Limit: Session mit 30min Limit endet automatisch nach 30min.
- [ ] Kiosk-Controller: Operator sieht alle Sessions live, kann beenden.
- [ ] VM-Reset: Nach Session-Ende wird VM auf Snapshot zurückgesetzt (keine User-Daten übrig).
- [ ] RBAC: `kiosk_operator` kann nur eigene Kiosk-Sessions sehen, kein Admin-Zugriff.

---

## Unique Selling Point vs. Konkurrenz

- **Citrix/Omnissa**: Kein Gaming-Modus, RDP-Latenz für Gaming ungeeignet → Beagle: Moonlight, <5ms, Gaming-native
- **GeForce NOW / Shadow PC**: Cloud-only, teuer, DSGVO-Probleme → Beagle: On-Prem, selbst gehostet
- **Proxmox**: Kein Broker, kein Kiosk-UI, kein Time-Limit → Beagle: vollständiger Stack
