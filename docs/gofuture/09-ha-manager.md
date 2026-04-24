# 09 — 7.0.2 HA Manager

Stand: 2026-04-20  
Priorität: 7.0 (Q4 2026)  
Referenz: `docs/refactorv2/08-ha-cluster.md`

---

## Schritte

### Schritt 1 — Watchdog-Fencing pro Host implementieren

- [x] `beagle-host/services/ha_watchdog.py` anlegen mit Heartbeat-Sende- und Empfangs-Logik.
- [x] Bei ausbleibendem Heartbeat: Fencing-Aktion auslösen (IPMI-Reset, Watchdog-Timer, VM-Forcestop).

Umgesetzt (2026-04-23):
- Neues Modul `beagle-host/services/ha_watchdog.py` implementiert (`HaWatchdogService`).
- Heartbeat-Lifecycle real umgesetzt: Heartbeats senden (`send_heartbeats`), empfangen/verbuchen (`record_heartbeat`) und Timeout-Pruefung (`evaluate_timeouts`).
- Fencing-Prioritaeten umgesetzt: `ipmi_reset` -> `watchdog_timer` -> `vm_forcestop` -> `software_isolation`.
- Persistenter Service-State in JSON (`state_file`) fuer Node-Health, letztes Heartbeat-Timestamp und letzte Fencing-Methode.
- Unit-Test `tests/unit/test_ha_watchdog.py` deckt Heartbeat-Sendung, Timeout/Fencing und No-Timeout-Pfad ab (3/3 gruen).

HA ohne Fencing ist gefährlich: wenn ein Knoten nur temporär nicht erreichbar ist
(Netzwerk-Partition) aber noch läuft, können beim Neustart der VMs auf einem anderen
Knoten Datenkonsistenzprobleme auftreten (Split-Brain). Fencing erzwingt dass der
ausgefallene Knoten tatsächlich gestoppt ist bevor seine VMs anderswo gestartet werden.
Der Watchdog sendet alle 2 Sekunden einen Heartbeat über die Cluster-RPC-Verbindung.
Nach 3 ausgebliebenen Heartbeats (6 Sekunden) startet der Fencing-Prozess.
Fencing-Methoden in Prioritätsreihenfolge: IPMI/BMC-Reset, UEFI-Watchdog-Timer,
falls nicht verfügbar: Software-Isolation (alle Outbound-Verbindungen blockieren).
Kein Fencing verfügbar muss explizit akzeptiert und im Web Console-Setup dokumentiert sein.

---

### Schritt 2 — Restart-Policies pro VM und Pool implementieren

- [x] VM-Config bekommt opt. Feld `ha_policy`: `disabled | restart | fail_over`.
- [x] HA-Manager prüft Policy nach Knoten-Ausfall und startet/verschiebt VM entsprechend.

Umgesetzt (2026-04-23):
- Neues Modul `beagle-host/services/ha_manager.py` eingefuehrt (`HaManagerService`).
- HA-Reconcile-Logik implementiert (`reconcile_failed_node`):
	- `ha_policy=disabled` -> Skip,
	- `ha_policy=restart` -> Cold-Restart auf online Target-Node,
	- `ha_policy=fail_over` -> Live-Migration-Versuch, bei Fehler automatischer Cold-Restart-Fallback.
- VM-Policy-Verdrahtung im Provisioning-Flow umgesetzt:
	- Create: `ha_policy` wird validiert und als VM-Option persistiert.
	- Update: `ha_policy` kann per API geaendert werden (`disabled|restart|fail_over`).
- Neuer API-Endpunkt `POST /api/v1/ha/reconcile-failed-node` in der Control Plane.
- RBAC-Mapping ergaenzt (`cluster:write`) fuer HA-Reconcile-Endpunkt.
- Unit-Tests ergaenzt:
	- `tests/unit/test_ha_manager.py` (Restart, Live-Migration, Fallback),
	- `tests/unit/test_ha_policy_validation.py` (Policy-Validierung).

Validierung (2026-04-23, lokal + srv1):
- Lokal: `python3 -m pytest tests/unit/test_ha_manager.py tests/unit/test_ha_policy_validation.py tests/unit/test_ha_watchdog.py -q` => `8 passed`.
- srv1: identischer Testlauf => `8 passed`.
- Live-Smoke: `POST /api/v1/ha/reconcile-failed-node` mit `{"failed_node":"ha-smoke-node"}` liefert `ok=true` und valide HA-Reconcile-Response.

Restart-Policies ermöglichen feingranulare Kontrolle darüber wie bei Knoten-Ausfall
verfahren wird. `disabled` bedeutet die VM wird nicht automatisch neugestartet.
`restart` bedeutet die VM wird auf einem anderen verfügbaren Knoten neu gestartet
(Cold-Start; Disk-Transfer wenn kein shared Storage). `fail_over` triggert Live-Migration
falls der Knoten noch erreichbar ist oder Cold-Migration als Fallback.
Die Policy wird pro VM gesetzt über die Web Console oder die API.
Pool-Level-Defaults können das individuelle VM-Verhalten überschreiben wenn kein
VM-spezifischer Wert gesetzt ist.

---

### Schritt 3 — Maintenance-Mode (Drain) implementieren

- [x] `beagle-host/services/maintenance_service.py` anlegen: alle VMs eines Knotens koordiniert auf andere Knoten verschieben.
- [x] Web Console: "In Maintenance versetzen" Button im Cluster-Panel.

Umgesetzt (2026-04-23):
- Neues Modul `beagle-host/services/maintenance_service.py` eingefuehrt (`MaintenanceService`).
- Maintenance-Drain-Flow implementiert (`drain_node`):
	- markiert Knoten persistent als Maintenance,
	- verarbeitet Knoten-VMs policy-basiert (`disabled` skip, `restart` cold restart, `fail_over` live migration mit cold-restart fallback),
	- persisted `maintenance_nodes` in `ha-maintenance-state.json`.
- Neuer API-Endpunkt `POST /api/v1/ha/maintenance/drain` in der Control Plane.
- Start-Guard fuer VM-Power-Start in Maintenance-Modus verdrahtet (`start_vm_checked`), damit Starts auf Maintenance-Knoten abgelehnt werden.
- RBAC-Mapping erweitert (`cluster:write`) fuer Maintenance-Drain-Endpoint.
- Web Console Cluster-Panel erweitert:
	- neuer Button `In Maintenance versetzen` je Knoten,
	- UI ruft Drain-Endpoint auf und refresht Dashboard nach erfolgreichem Drain.
- Unit-Tests ergaenzt:
	- `tests/unit/test_maintenance_service.py`,
	- `tests/unit/test_authz_policy.py` um HA-Maintenance-Routen.

Validierung (2026-04-23, lokal + srv1):
- Lokal: `python3 -m pytest tests/unit/test_maintenance_service.py tests/unit/test_authz_policy.py tests/unit/test_ha_manager.py tests/unit/test_ha_policy_validation.py tests/unit/test_ha_watchdog.py -q` => `17 passed`.
- srv1: identischer Testlauf => `17 passed`.
- Live-Smoke auf srv1: `POST /api/v1/ha/maintenance/drain` fuer `node_name=beagle-0` liefert `200` und `ok=true`.
- UI-Smoke auf srv1: ausgeliefertes `website/ui/cluster.js` enthaelt `In Maintenance versetzen`.

Maintenance-Mode ist notwendig für geplante Wartung (Kernel-Update, Hardware-Tausch)
ohne VM-Downtime. Beim Drain werden alle laufenden VMs mit aktiver HA-Policy
per Live-Migration (bei shared Storage) oder Per-Stop/Start (ohne shared Storage)
auf andere Knoten verschoben. Neue VM-Starts auf dem Maintenance-Knoten werden
abgelehnt. Der Knoten bleibt im Cluster aber mit Status `maintenance`. Sobald
alle VMs abgewandert sind zeigt die Web Console den Knoten als "bereit für Wartung".
Nach der Wartung wird Maintenance-Mode manuell deaktiviert.

---

### Schritt 4 — Anti-Affinity- und Affinity-Regeln implementieren

- [x] `SchedulerPolicy`-Objekt in `core/` definieren mit `affinity_groups` und `anti_affinity_groups`.
- [x] VM-Scheduler berücksichtigt Policy bei Placement-Entscheidungen.

Umgesetzt (2026-04-23):
- Neues Core-Modul `core/virtualization/scheduler_policy.py` eingefuehrt (`SchedulerPolicy`, `SchedulerGroup`, `scheduler_policy_from_payload`).
- Pool-Scheduler in `beagle-host/services/pool_manager.py` erweitert:
	- ermittelt online Knoten,
	- beruecksichtigt `anti_affinity_groups` als Hard-Preference (Nodes vermeiden),
	- beruecksichtigt `affinity_groups` als Co-Location-Preference,
	- persistiert den gewaehlten `node` pro registrierter Pool-VM.
- API-Wiring umgesetzt:
	- `POST /api/v1/pools/{pool_id}/vms` akzeptiert jetzt optional `scheduler_policy`.
	- `pool_manager_service()` verdrahtet Node-Callbacks (`list_nodes`, `vm_node_of`) fuer Placement.
- Tests ergaenzt:
	- `tests/unit/test_scheduler_policy_contract.py`
	- `tests/unit/test_pool_manager.py` um Anti-Affinity-/Affinity-Placement-Faelle.

Validierung (2026-04-23, lokal + srv1):
- Lokal:
	- `python3 -m py_compile core/virtualization/scheduler_policy.py beagle-host/services/pool_manager.py beagle-host/bin/beagle-control-plane.py` => OK
	- `python3 -m pytest tests/unit/test_scheduler_policy_contract.py tests/unit/test_pool_manager.py tests/unit/test_authz_policy.py tests/unit/test_maintenance_service.py tests/unit/test_ha_manager.py tests/unit/test_ha_policy_validation.py tests/unit/test_ha_watchdog.py -q` => `28 passed`
	- `python3 -m pytest tests/unit/test_cluster_membership.py tests/unit/test_cluster_inventory.py tests/unit/test_beaglectl_cluster.py tests/unit/test_cluster_rpc.py -q` => `14 passed`
- srv1:
	- `py_compile` fuer die geaenderten Module => OK
	- Dienst-Neustart `beagle-control-plane.service` => `active`
	- Live-Smoke gegen `/api/v1/pools/{pool}/vms` mit `scheduler_policy.anti_affinity_groups`:
		- Create/Register/Register/List/Delete => `201/201/201/200/200`
		- auf Single-Node-Host landen beide VMs erwartbar auf `beagle-0`; Multi-Node-Verteilung wird durch Unit-Tests mit zwei Online-Knoten reproduzierbar abgedeckt.

Affinity-Regeln stellen sicher dass bestimmte VMs bevorzugt auf demselben Knoten
laufen (z.B. Datenbank und Anwendungsserver für niedrige Latenz). Anti-Affinity-Regeln
stellen sicher dass VMs auf verschiedenen Knoten laufen (z.B. zwei Replicas desselben
Dienstes). Der Scheduler prüft bei jedem VM-Start und jeder Migration ob Affinity-Regeln
verletzt würden. Ist ein Placement-Konflikt unvermeidbar (zu wenige Knoten available)
wird der Operator über einen Alert in der Web Console informiert.

---

### Schritt 5 — HA-Status in Web Console anzeigen

- [x] Cluster-Panel: HA-Status-Sektion mit Knoten-Health und VM-HA-Übersicht.
- [x] Alert-Banner wenn Quorum unter Mindestgröße oder Fencing-Aktion aktiv.

Umgesetzt (2026-04-23):
- Neuer API-Endpunkt `GET /api/v1/ha/status` in der Control Plane implementiert.
	- aggregiert Quorum (`minimum_nodes`, `online_nodes`, `ok`),
	- globalen HA-Status (`ok|degraded|failed`),
	- Fencing-Status inkl. letzter Methode,
	- Node-Health-Liste mit letztem Heartbeat und Anzahl HA-geschuetzter VMs.
- RBAC erweitert: `GET /api/v1/ha/status` mappt auf `cluster:read`.
- Web Console Cluster-Panel erweitert:
	- neue HA-Status-Sektion mit Karten fuer `HA Health`, `HA-Protected VMs`, `Quorum`, `Fencing aktiv`,
	- Node-HA-Tabelle (`Status`, `Letzter Heartbeat`, `HA-VMs`, `Fencing`),
	- Alert-Banner fuer Quorum-Unterschreitung/Fencing-Ereignisse.

Validierung (2026-04-23, lokal + srv1):
- Lokal:
	- `python3 -m py_compile beagle-host/bin/beagle-control-plane.py beagle-host/services/authz_policy.py` => OK
	- `python3 -m pytest tests/unit/test_authz_policy.py tests/unit/test_maintenance_service.py tests/unit/test_ha_manager.py tests/unit/test_ha_watchdog.py tests/unit/test_cluster_inventory.py tests/unit/test_cluster_membership.py -q` => `23 passed`
	- `node --check website/ui/cluster.js website/ui/dashboard.js website/main.js` => OK
- srv1:
	- `py_compile` auf deployten Dateien => OK
	- `pytest` (`authz_policy`, `maintenance`, `ha_manager`, `ha_watchdog`) => `15 passed`
	- `beagle-control-plane.service` Restart => `active`
	- API-Smoke `GET /api/v1/ha/status` => `200`, `ha_state=ok`, `quorum.ok=true`, `fencing.active=false`, `alerts_count=0`
	- UI-Smoke auf deployten Assets: Marker `cluster-ha-alert`, `cluster-ha-nodes-body` und `renderHaStatusPanel` vorhanden.

Der HA-Status ist für Betreiber das wichtigste Monitoring-Instrument im Cluster-Betrieb.
Eine Karte pro Knoten zeigt: letzter Heartbeat-Zeitpunkt, Status (active/maintenance/fencing),
Anzahl HA-geschützter VMs. Eine globale HA-Health-Card zeigt Gesamtstatus (OK/DEGRADED/FAILED).
Wenn ein Knoten in den Fencing-Prozess geht erscheint ein prominenter Alert-Banner
mit dem betroffenen Knoten-Namen und der Fencing-Methode. Audit-Events werden für
alle HA-Ereignisse (Fencing-Start, Fencing-Complete, VM-Restart, VM-Migration) erzeugt.

---

## Testpflicht nach Abschluss

- [ ] Knoten-Ausfall: HA-Manager erkennt in <= 60s, VM auf gesundem Knoten läuft in <= 60s.
- [x] Fencing blockiert VM-Start vor Abschluss (kein Split-Brain).
- [ ] Maintenance-Mode: alle VMs abgewandert, neuer VM-Start auf Maintenance-Knoten abgelehnt.
- [ ] Anti-Affinity: zwei VMs gleicher Gruppe landen auf unterschiedlichen Knoten.

Validierung (2026-04-24, srv1):
- Temporärer Watchdog-State gesetzt: `nodes.beagle-0.status=fencing` und `fencing_active=true`.
- `POST /api/v1/virtualization/vms/100/power` mit `{"action":"start"}` liefert `502` mit `node beagle-0 is fenced; VM start rejected`.
- Nach Restore des Watchdog-States liefert derselbe Call weiterhin `502`, aber mit Provider-Fehler `Domain is already active` (kein Fencing-Block mehr aktiv).
