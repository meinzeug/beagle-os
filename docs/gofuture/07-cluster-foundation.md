# 07 — 7.0.0 Cluster Foundation

Stand: 2026-04-20  
Priorität: 7.0 (Q3 2026)  
Referenz: `docs/refactorv2/04-roadmap-v2.md`, `docs/refactorv2/08-ha-cluster.md`

---

## Ziel

Zwei Beagle-Hosts bilden ein Cluster mit gemeinsamer Web Console und Live-Migration.
Akzeptanz: Zwei Hosts gestartet, Web Console zeigt beide, eine laufende VM wird
live von Host A auf Host B migriert.

---

## Schritte

### Schritt 1 — Cluster-Store-Technologie entscheiden und PoC bauen

- [ ] PoC: etcd als Cluster-Store auf zwei VM-Hosts aufsetzen und Leader-Election testen.
- [ ] Falls etcd-Footprint zu groß: SQLite + Litestream als Alternative evaluieren.

Die Wahl des Cluster-Stores ist die wichtigste architekturelle Entscheidung für 7.0.
etcd bietet starke Konsistenzgarantien und Leader-Election out-of-the-box aber erfordert
ungeradzahliges Quorum (mindestens drei Nodes für Produkten). SQLite + Litestream ist
einfacher zu betreiben hat aber kein automatisches Leader-Election-Protokoll.
Für einen 2-Node-Cluster ist etcd mit einem externen Witness-Node oder einem embedded
Etcd-Tiebreaker möglich. Alternativ kann ein leichtgewichtiges Raft-Protokoll wie
`dragonboat` oder `hashicorp/raft` direkt in `beagle-host` eingebettet werden.
Die Entscheidung wird in `docs/refactor/07-decisions.md` mit Begründung festgehalten.
Der PoC-Code landet in `providers/beagle/cluster/` und ist nicht produktionsreif.

---

### Schritt 2 — Inter-Host-RPC mit mTLS implementieren

- [ ] `beagle-host/services/cluster_rpc.py` anlegen mit HTTP/2 oder gRPC-Basis und mTLS-Zertifikaten.
- [ ] Cluster-CA anlegen, Node-Zertifikate beim Cluster-Join signieren.

mTLS bedeutet dass beide Seiten einer Verbindung sich gegenseitig mit Zertifikaten
authentifizieren. Die Cluster-CA ist ein selbst-signiertes CA-Zertifikat das nur
im Cluster existiert und niemals nach außen publiziert wird. Bei einem Cluster-Join
generiert der neue Node ein Schlüsselpaar und lässt sich das Zertifikat von der CA
signieren. Abgelaufene oder kompromittierte Node-Zertifikate können mit CRL oder OCSP
widerrufen werden. Die CA-Pflege wird in einem `beagle-host/services/ca_manager.py`
Service gebündelt. Alle inter-host API-Calls über Port 9089 (gewählt) laufen über mTLS.

---

### Schritt 3 — VM-Inventory über Cluster-Knoten konsolidieren

- [x] `beagle-host/services/cluster_inventory.py` anlegen der Inventory aus allen Knoten aggregiert.
- [ ] Web Console zeigt Knoten-Label neben jeder VM.

Umsetzung 2026-04-22:
- Neues Backend-Service-Modul `beagle-host/services/cluster_inventory.py` eingeführt.
- Service aggregiert Node-Metadaten (`status`, `cpu`, `mem`, `maxmem`, `maxcpu`) und VM-Verteilung pro Node aus bestehendem VM-Inventory.
- Unbekannte/temporär nicht gelistete Nodes werden als `unreachable` modelliert, damit VM-Zuordnung im Cluster-Blick erhalten bleibt.
- Neue Read-Endpunkte freigeschaltet: `GET /api/v1/cluster/inventory` und Alias `GET /api/v1/cluster/nodes`.
- Unit-Tests ergänzt: `tests/unit/test_cluster_inventory.py`.

Heute zeigt das Inventory nur VMs des lokalen Hosts. Im Cluster-Modus aggregiert
`cluster_inventory.py` die Inventories aller Knoten über die Cluster-RPC-Schicht.
Jede VM bekommt ein `node`-Feld das anzeigt auf welchem Knoten sie läuft.
Der Aggregations-Service pollt alle Knoten, kumuliert die Antworten und cacht
das Ergebnis mit einem kurzen TTL (3–5 Sekunden). Ausgefallene Knoten werden
als `unreachable` markiert ihre letzten bekannten VMs bleiben sichtbar aber
als `status: unknown` markiert. Die Web Console kann dann einen Knoten-Filter anbieten.

---

### Schritt 4 — Live-Migration implementieren

- [ ] `beagle-host/services/migration_service.py` anlegen mit libvirt-managed Live-Migration.
- [ ] Web Console bekommt "VM verschieben"-Button in der Detailansicht.

Live-Migration überträgt den RAM-Zustand einer laufenden VM auf den Ziel-Knoten ohne
sichtbaren Downtime (bei shared storage). Die libvirt-API `virDomainMigrate3` übernimmt
die eigentliche Migration; `migration_service.py` orchestriert Vorbedingungsprüfung
(Ziel-Knoten erreichbar? Storage vorhanden? Genug RAM?), startet die Migration und
überwacht den Fortschritt. Die Web Console zeigt Migrations-Progress in Prozent.
Bei Fehler wird die VM auf dem Quell-Knoten belassen und ein Fehler-Event erzeugt.
Live-Migration ohne shared storage (Cold-Migration mit Disk-Transfer) ist als
späterer Schritt vorgesehen.

---

### Schritt 5 — Cluster-Setup-Assistent im Server-Installer

- [ ] Installer-Dialog: "Diesen Host einem Cluster beitreten?" (Ja/Nein).
- [ ] Bei Ja: Join-Token oder IP des bestehenden Cluster-Leaders eingeben.

Der Cluster-Join-Prozess muss für Betreiber ohne Kubernetes-Kenntnisse zugänglich sein.
Ein einfacher Dialog im `beagle-server-installer`-Skript fragt ob der neue Host einem
bestehenden Cluster beitreten soll. Bei Ja wird ein Join-Token (kurzer Code or URL)
eingegeben der vom bestehenden Leader-Node generiert wurde. Der neue Host authentifiziert
sich mit dem Token beim Leader, erhält ein signiertes Node-Zertifikat und wird in den
Cluster-Store aufgenommen. Nach dem Join zeigt die Web Console des Leaders den neuen
Knoten sofort in der Knoten-Liste.

---

### Schritt 6 — Cluster-Status in Web Console anzeigen

- [x] Neues Panel "Cluster" in der Web Console Navigation anlegen.
- [x] Knoten-Liste mit Status, CPU-/RAM-Auslastung, VM-Count.

Umsetzung 2026-04-22:
- WebUI-Navigation um `Cluster`-Panel erweitert (`website/index.html`, `data-panel="cluster"`) inkl. eigener Panel-Metadaten in `website/ui/state.js`.
- Neues Modul `website/ui/cluster.js` implementiert: rendert Cluster-Knoten-Tabelle aus `state.virtualizationOverview.nodes`, berechnet CPU-/RAM-Auslastung und VM-Count pro Knoten (Aggregation aus `state.inventory`).
- Dashboard-Load verdrahtet (`website/ui/dashboard.js` + `website/main.js`), sodass Clusterdaten bei jedem Refresh/SSE-Tick live aktualisiert werden.
- Cluster-Panel bietet direkte Aktion „VMs anzeigen" pro Knoten via Filter-Deep-Link ins Inventory.

Das Cluster-Panel ist der erste Punkt in der Web Console wo mehrere Hosts sichtbar
und managebar sind. Die Knoten-Karten zeigen: Knoten-Name, IP, Status (online/offline/joining),
CPU-Gesamt vs. genutzt, RAM-Gesamt vs. genutzt, Anzahl laufender VMs.
Ein "In Maintenance versetzen" Button startet den Drain-Prozess (VMs wandern ab).
Der Cluster-Status selbst (Leader, Quorum-Konfiguration) wird als eigene Card angezeigt.
WebSocket oder SSE für Live-Updates des Cluster-Status wäre ideal; ein 5-Sekunden-Poll
ist zunächst ausreichend.

---

## Testpflicht nach Abschluss

- [ ] Zwei QEMU-VMs als Cluster-Knoten gestartet, beide in Web Console sichtbar.
- [ ] Live-Migration einer laufenden Test-VM von Host A nach Host B erfolgreich.
- [ ] Knoten-Ausfall: Web Console zeigt Knoten als unreachable innerhalb von 10 Sekunden.
- [ ] Cluster-Join über Installer-Dialog funktioniert auf frisch installiertem Host.
