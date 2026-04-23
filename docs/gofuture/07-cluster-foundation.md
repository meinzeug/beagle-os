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

- [x] PoC: etcd als Cluster-Store auf zwei VM-Hosts aufsetzen und Leader-Election testen.
- [x] Falls etcd-Footprint zu groß: SQLite + Litestream als Alternative evaluieren.

Umsetzung 2026-04-23:
- Neues PoC-Modul `providers/beagle/cluster/store_poc.py` eingefuehrt mit zwei Modi:
	- `etcd`: validiert Leader-Election via `etcdctl move-leader` und prueft den neuen Leader.
	- `sqlite-eval`: liefert eine Vergleichsmatrix fuer etcd vs SQLite+Litestream.
- Neues Runtime-Helper-Skript `providers/beagle/cluster/run_etcd_cluster_poc.sh` eingefuehrt:
	- startet drei lokale etcd-Member (`host-a`, `host-b`, `witness`) als 2-Host+Witness Topologie,
	- fuehrt den PoC reproduzierbar aus,
	- beendet alle Prozesse nach dem Lauf.
- Unit-Tests fuer Parsing/Entscheidungslogik ergaenzt: `tests/unit/test_cluster_store_poc.py`.
- Lokale Validierung: `python3 -m pytest tests/unit/test_cluster_store_poc.py -q` => `3 passed`.
- Live-Validierung auf `srv1.beagle-os.com`:
	- PoC-Dateien nach `/opt/beagle/providers/beagle/cluster/` deployt,
	- etcd Runtime (`etcd-server`, `etcd-client`) installiert,
	- `providers/beagle/cluster/run_etcd_cluster_poc.sh` erfolgreich mit `ETCD_POC_RESULT=PASS`.

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

- [x] `beagle-host/services/cluster_rpc.py` anlegen mit HTTP/2 oder gRPC-Basis und mTLS-Zertifikaten.
- [x] Cluster-CA anlegen, Node-Zertifikate beim Cluster-Join signieren.

Umsetzung 2026-04-23:
- Neues Service-Modul `beagle-host/services/cluster_rpc.py` eingefuehrt:
	- JSON-RPC Surface auf HTTPS/mTLS,
	- TLS >= 1.2,
	- ALPN fuer `h2` + `http/1.1` gesetzt,
	- Client-Zertifikate sind verpflichtend (`CERT_REQUIRED`).
- Neues Service-Modul `beagle-host/services/ca_manager.py` eingefuehrt:
	- erstellt eine lokale Cluster-CA,
	- generiert Node-Key/CSR/Cert-Bundles fuer Join-Szenarien,
	- signiert Node-Zertifikate mit SANs fuer DNS/IP.
- Neue reproduzierbare Validierung:
	- Unit-Tests `tests/unit/test_ca_manager.py` und `tests/unit/test_cluster_rpc.py`.
	- Smoke-Skript `scripts/test-cluster-rpc-smoke.py` erzeugt CA + Node-Zertifikate, startet einen lokalen mTLS-RPC-Server und prueft erfolgreichen Client-Handshake.
- Validierung:
	- Lokal: `python3 -m pytest tests/unit/test_ca_manager.py tests/unit/test_cluster_rpc.py -q` => `5 passed`.
	- Lokal: `python3 scripts/test-cluster-rpc-smoke.py` => `CLUSTER_RPC_SMOKE=PASS`.
	- Live `srv1.beagle-os.com`: derselbe Testpfad erfolgreich (`5 passed`, `CLUSTER_RPC_SMOKE=PASS`).

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
- [x] Web Console zeigt Knoten-Label neben jeder VM.

Umsetzung 2026-04-22:
- Neues Backend-Service-Modul `beagle-host/services/cluster_inventory.py` eingeführt.
- Service aggregiert Node-Metadaten (`status`, `cpu`, `mem`, `maxmem`, `maxcpu`) und VM-Verteilung pro Node aus bestehendem VM-Inventory.
- Unbekannte/temporär nicht gelistete Nodes werden als `unreachable` modelliert, damit VM-Zuordnung im Cluster-Blick erhalten bleibt.
- Neue Read-Endpunkte freigeschaltet: `GET /api/v1/cluster/inventory` und Alias `GET /api/v1/cluster/nodes`.
- Unit-Tests ergänzt: `tests/unit/test_cluster_inventory.py`.

Ergaenzung 2026-04-23:
- `website/ui/inventory.js` zeigt pro VM jetzt ein explizites `Node`-Label mit Knotennamen in jeder Inventory-Karte.
- `website/styles/panels/_inventory.css` um eigenes Node-Pill-Styling erweitert.
- Live auf `srv1.beagle-os.com` deployt und per Asset-Grep auf ausgelieferten Dateien verifiziert.

Heute zeigt das Inventory nur VMs des lokalen Hosts. Im Cluster-Modus aggregiert
`cluster_inventory.py` die Inventories aller Knoten über die Cluster-RPC-Schicht.
Jede VM bekommt ein `node`-Feld das anzeigt auf welchem Knoten sie läuft.
Der Aggregations-Service pollt alle Knoten, kumuliert die Antworten und cacht
das Ergebnis mit einem kurzen TTL (3–5 Sekunden). Ausgefallene Knoten werden
als `unreachable` markiert ihre letzten bekannten VMs bleiben sichtbar aber
als `status: unknown` markiert. Die Web Console kann dann einen Knoten-Filter anbieten.

---

### Schritt 4 — Live-Migration implementieren

 [x] `beagle-host/services/migration_service.py` anlegen mit libvirt-managed Live-Migration.
 [x] Web Console bekommt "VM verschieben"-Button in der Detailansicht.

 Umsetzung 2026-04-23:
 - Neues Service-Modul `beagle-host/services/migration_service.py` eingefuehrt:
 	- prueft Zielknoten gegen das aggregierte Cluster-Inventory,
 	- blockiert Self-Migration und Offline-Ziele,
 	- baut libvirt-managed Migrationsaufrufe fuer Live-Migration/Copy-Storage reproduzierbar auf.
 - Mutation-Surface erweitert:
 	- neuer Route-Handler `POST /api/v1/vms/{vmid}/migrate` in `beagle-host/services/vm_mutation_surface.py`,
 	- RBAC-Mapping in `beagle-host/services/authz_policy.py` auf `vm:mutate`,
 	- Control-Plane-Wiring in `beagle-host/bin/beagle-control-plane.py` inkl. Node-Persistenz nach erfolgreicher Migration.
 - Web Console erweitert:
 	- `website/main.js` zeigt fuer laufende VMs die Detailaktion `VM verschieben`,
 	- `website/ui/actions.js` ermittelt online Zielknoten aus dem Cluster-Overview, fragt bei mehreren Zielen nach und ruft die generische Migrationsroute auf.
 - Tests und Smokes:
 	- neue Unit-Tests `tests/unit/test_migration_service.py` und `tests/unit/test_vm_mutation_surface.py`,
 	- neues Smoke-Skript `scripts/test-vm-migration-smoke.py` fuer den Servicepfad.
 - Validierung:
 	- Lokal: `py_compile` OK, `6 passed`, `VM_MIGRATION_SMOKE=PASS`, `node --check` fuer `website/main.js` + `website/ui/actions.js` OK.
 	- Live `srv1.beagle-os.com`: dieselben Python-Tests/Smokes gruen, Host-Service neu installiert, ausgelieferte Assets enthalten Button/Route/Action.
 	- API-Live-Smoke auf `srv1`: `POST /api/v1/vms/999999/migrate` liefert JSON-`404 not_found` statt Missing-Path-HTML, die Route ist also runtime-seitig aktiv.

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

 [x] Installer-Dialog: "Diesen Host einem Cluster beitreten?" (Ja/Nein).
 [x] Bei Ja: Join-Token oder IP des bestehenden Cluster-Leaders eingeben.

 Umsetzung 2026-04-23:
 - Server-Installer-GUI erweitert:
 	- `beagle-server-installer-gui` fragt jetzt explizit `Soll dieser Host einem Cluster beitreten?`,
 	- bei `Yes` folgt ein Pflichtfeld fuer `Join-Token oder Leader-IP/URL`.
 - Text-/Seriell-Fallback ebenfalls erweitert:
 	- `beagle-server-installer` stellt dieselbe Ja/Nein-Frage auch ohne curses-GUI,
 	- Join-Target wird validiert und darf bei aktiviertem Join nicht leer bleiben.
 - Installer-Handoff durchgaengig verdrahtet:
 	- GUI-State traegt `BEAGLE_GUI_CLUSTER_JOIN` und `BEAGLE_GUI_CLUSTER_JOIN_TARGET`,
 	- Chroot-Install uebergibt die Werte an `scripts/install-beagle-host.sh`,
 	- Postinstall persistiert sie in `/etc/beagle/cluster-join.env` (0600) und markiert den Join-Wunsch in den Runtime-Env-Dateien.
 - Security/Runtime:
 	- Join-Target wird bewusst nicht breit in `host.env` oder Proxy-Env repliziert, sondern in einer dedizierten Root-Datei gehalten.
 	- `beagle-manager.env` enthaelt nur Join-Flag plus Pfad zur Secret-Datei fuer spaetere Join-Orchestrierung.
 - Validierung:
 	- Lokal: Python/Bash-Syntax gruen; Plain-Mode-Lauf schreibt `BEAGLE_GUI_CLUSTER_JOIN='yes'` und `BEAGLE_GUI_CLUSTER_JOIN_TARGET='10.0.0.15'` in die State-Datei.
 	- Live `srv1.beagle-os.com`: derselbe Syntax- und Plain-Mode-State-Test erfolgreich mit `leader.beagle-os.com` als Join-Ziel.

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

- [x] Zwei QEMU-VMs als Cluster-Knoten gestartet, beide in Web Console sichtbar.
- [ ] Live-Migration einer laufenden Test-VM von Host A nach Host B erfolgreich.
- [x] Knoten-Ausfall: Web Console zeigt Knoten als unreachable innerhalb von 10 Sekunden.
- [x] Cluster-Join über Installer-Dialog funktioniert auf frisch installiertem Host.

Validierung 2026-04-23 auf `srv1`:
- Cluster-Join erfolgreich (`JOIN_RC=0`), Leader-Memberliste enthält `srv1` + `node-b`.
- Cluster-Inventory zeigt alle Knoten inkl. Cluster-Member-Merge (`node_count=3`: `beagle-0`, `srv1`, `node-b`).
- Nach Kill von `node-b` wird der Knoten im ersten Poll als `unreachable` markiert (`node_unreachable_count=1`).
- Live-Migration bleibt offen, da in der aktuellen Testumgebung kein zweiter echter libvirt-Host für End-to-End-Migration vorhanden ist.

Validierung (2026-04-23, erneuter Check auf `srv1.beagle-os.com`):
- `GET /api/v1/cluster/nodes` liefert `srv1` und `beagle-0` als online, aber keinen erreichbaren zweiten Migrations-Host.
- Nicht-lokale Knotennamen sind aus `srv1` weder per DNS noch per SSH erreichbar (`resolved=false`, `ssh=false`).
- Damit bleibt ein echter Host-A→Host-B Live-Migrationsnachweis weiterhin offen.
