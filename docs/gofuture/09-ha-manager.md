# 09 — 7.0.2 HA Manager

Stand: 2026-04-20  
Priorität: 7.0 (Q4 2026)  
Referenz: `docs/refactorv2/08-ha-cluster.md`

---

## Schritte

### Schritt 1 — Watchdog-Fencing pro Host implementieren

- [ ] `beagle-host/services/ha_watchdog.py` anlegen mit Heartbeat-Sende- und Empfangs-Logik.
- [ ] Bei ausbleibendem Heartbeat: Fencing-Aktion auslösen (IPMI-Reset, Watchdog-Timer, VM-Forcestop).

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

- [ ] VM-Config bekommt opt. Feld `ha_policy`: `disabled | restart | fail_over`.
- [ ] HA-Manager prüft Policy nach Knoten-Ausfall und startet/verschiebt VM entsprechend.

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

- [ ] `beagle-host/services/maintenance_service.py` anlegen: alle VMs eines Knotens koordiniert auf andere Knoten verschieben.
- [ ] Web Console: "In Maintenance versetzen" Button im Cluster-Panel.

Maintenance-Mode ist notwendig für geplante Wartung (Kernel-Update, Hardware-Tausch)
ohne VM-Downtime. Beim Drain werden alle laufenden VMs mit aktiver HA-Policy
per Live-Migration (bei shared Storage) oder Per-Stop/Start (ohne shared Storage)
auf andere Knoten verschoben. Neue VM-Starts auf dem Maintenance-Knoten werden
abgelehnt. Der Knoten bleibt im Cluster aber mit Status `maintenance`. Sobald
alle VMs abgewandert sind zeigt die Web Console den Knoten als "bereit für Wartung".
Nach der Wartung wird Maintenance-Mode manuell deaktiviert.

---

### Schritt 4 — Anti-Affinity- und Affinity-Regeln implementieren

- [ ] `SchedulerPolicy`-Objekt in `core/` definieren mit `affinity_groups` und `anti_affinity_groups`.
- [ ] VM-Scheduler berücksichtigt Policy bei Placement-Entscheidungen.

Affinity-Regeln stellen sicher dass bestimmte VMs bevorzugt auf demselben Knoten
laufen (z.B. Datenbank und Anwendungsserver für niedrige Latenz). Anti-Affinity-Regeln
stellen sicher dass VMs auf verschiedenen Knoten laufen (z.B. zwei Replicas desselben
Dienstes). Der Scheduler prüft bei jedem VM-Start und jeder Migration ob Affinity-Regeln
verletzt würden. Ist ein Placement-Konflikt unvermeidbar (zu wenige Knoten available)
wird der Operator über einen Alert in der Web Console informiert.

---

### Schritt 5 — HA-Status in Web Console anzeigen

- [ ] Cluster-Panel: HA-Status-Sektion mit Knoten-Health und VM-HA-Übersicht.
- [ ] Alert-Banner wenn Quorum unter Mindestgröße oder Fencing-Aktion aktiv.

Der HA-Status ist für Betreiber das wichtigste Monitoring-Instrument im Cluster-Betrieb.
Eine Karte pro Knoten zeigt: letzter Heartbeat-Zeitpunkt, Status (active/maintenance/fencing),
Anzahl HA-geschützter VMs. Eine globale HA-Health-Card zeigt Gesamtstatus (OK/DEGRADED/FAILED).
Wenn ein Knoten in den Fencing-Prozess geht erscheint ein prominenter Alert-Banner
mit dem betroffenen Knoten-Namen und der Fencing-Methode. Audit-Events werden für
alle HA-Ereignisse (Fencing-Start, Fencing-Complete, VM-Restart, VM-Migration) erzeugt.

---

## Testpflicht nach Abschluss

- [ ] Knoten-Ausfall: HA-Manager erkennt in <= 60s, VM auf gesundem Knoten läuft in <= 60s.
- [ ] Fencing blockiert VM-Start vor Abschluss (kein Split-Brain).
- [ ] Maintenance-Mode: alle VMs abgewandert, neuer VM-Start auf Maintenance-Knoten abgelehnt.
- [ ] Anti-Affinity: zwei VMs gleicher Gruppe landen auf unterschiedlichen Knoten.
