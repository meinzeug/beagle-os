# 06 — Cross-Node Session-Handover (Live-Migration für VDI)

Stand: 2026-04-24  
Priorität: 8.1.1 (Q4 2026)

---

## Motivation

### Das Problem

User "alice" sitzt morgens im Büro Berlin, arbeitet auf VM X (auf Node A in Berlin).
Nachmittags geht sie ins Homeoffice oder fährt in die Filiale München.
Heute: Session trennen, VM einfrieren, in München neu verbinden (20-60 Sekunden Unterbrechung).

**Enterprise-Anforderung**: Session-Handover in <3 Sekunden, ohne Datenverlust, von jedem Ort.

### Wettbewerbslage

| Produkt | Session-Handover |
|---|---|
| Citrix ICA | "Session Roaming" — nur im selben Datacenter, proprietär |
| VMware Horizon | "Client Roaming" — funktioniert, aber nur auf VMware-Hardware |
| Azure VD | Reconnect via Azure-Backbone, aber Cloud-Pflicht |
| AWS WorkSpaces | Reconnect in <5s, aber proprietäre AWS-Infra |
| **Beagle GoEnterprise** | **Cross-Site Session-Roaming ohne Cloud-Pflicht** |

---

## Schritte

### Schritt 1 — Session-State-Checkpoint

- [x] `beagle-host/services/session_manager.py`: `checkpoint_session(session_id)`:
  - Speichert aktuellen Session-State: aktiver VM-State (QEMU-Checkpoint), Moonlight-Connection-State, User-Context
  - Checkpoint-Datei in `/var/lib/beagle/session-checkpoints/{session_id}.ckpt`
- [x] Provoke: `providers/beagle/libvirt_provider.py`: `save_vm_state(vmid, checkpoint_path)` via virsh managedsave
- [x] Tests: `tests/unit/test_session_checkpoint.py`

### Schritt 2 — Cross-Node Checkpoint-Transfer

- [x] `beagle-host/services/session_manager.py`: `transfer_session(session_id, target_node)`:
  - Checkpoint zu Ziel-Node übertragen (rsync/SCP über Management-Netzwerk)
  - VM auf Quell-Node stoppen, auf Ziel-Node aus Checkpoint restoren
  - Moonlight: neue Verbindung zu Ziel-Node aufbauen, Client bekommt neue Server-IP
- [x] `providers/beagle/libvirt_provider.py`: `restore_vm_from_checkpoint(vmid, checkpoint_path)`
- [x] Tests: `tests/unit/test_session_transfer.py`

### Schritt 3 — Transparent Client Reconnect

- [x] Session-Broker-Erweiterung (Plan 01, Schritt 1): `GET /api/v1/session/current` gibt immer aktuellen Node zurück
- [x] Moonlight-Client-OS (Thin-Client): bei Reconnect → Broker fragen, automatisch auf richtigen Node umleiten
- [x] Max. Unterbrechungszeit-Ziel: <5 Sekunden (Checkpoint + Transfer + Restore + Reconnect)
- [x] Tests: E2E-Timing-Test: `tests/integration/test_session_handover_timing.py`

### Schritt 4 — Scheduled Handover (Geo-Routing)

- [x] `beagle-host/services/session_manager.py`: Geo-basiertes Auto-Handover:
  - User hat `home_site=berlin`, `office_site=munich`
  - Scheduler: wenn User von Berlin-Netz → München-Netz wechselt (IP-basiert) → automatisch Handover
- [x] Konfiguration: `session_geo_routing` pro User in User-Profil
- [x] Tests: `tests/unit/test_geo_routing.py`

### Schritt 5 — Handover-Log + Admin-Monitoring

- [x] Audit-Event für jeden Handover: `session_handover_started`, `session_handover_completed`, `session_handover_failed`
- [x] Web Console: Handover-Historie pro Session/User
- [x] Alert: Wenn Handover >10s → Admin-Alert

---

## Testpflicht nach Abschluss

- [x] Checkpoint: Session-State wird korrekt gespeichert (VM-State + Moonlight-State).
- [x] Transfer: Checkpoint von Node A zu Node B transferiert, VM auf B gestartet.
- [x] Client Reconnect: Client verbindet sich automatisch auf neuen Node, <5s Unterbrechung.
- [x] Geo-Routing: IP-Wechsel löst automatischen Handover aus.

---

## Unique Selling Point

**Kein On-Prem Open-Source VDI bietet Cross-Node Session Handover.**
Dies ist Enterprise-Feature das normalerweise nur in $100k/Jahr-Lizenz-Produkten (Citrix Platinum) oder proprietärer Cloud existiert.
