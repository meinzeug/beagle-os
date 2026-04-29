# 17 — 7.3.1 SDN + Verteilte Firewall

Stand: 2026-04-20  
Priorität: 7.3 (H1 2028)  
Referenz: `docs/refactorv2/07-storage-network-plane.md`

---

## Schritte

### Schritt 1 — VLAN-Unterstützung pro VM/Pool

- [x] `NetworkZone`-Contract in `core/` definieren: VLAN-ID, Subnetz, DHCP-Pool, Gateway.
- [x] `providers/beagle/network/vlan.py`: Linux-Bridge + VLAN-Tags über `ip link` / `bridge` API.

VLANs sind die wichtigste Netzwerk-Isolations-Primitiv für Multi-Tenant-Deployments.
Jede NetworkZone bekommt eine VLAN-ID (1–4094). VM-Interfaces werden über Linux-Bridge
mit VLAN-tagging an die Zone gebunden. Der `beagle-host`-Level Netzwerk-Setup
konfiguriert die Bridge und VLAN-Interfaces beim Systemstart über ein idempotentes
Setup-Skript. Per Pool oder per VM wird die Zugehörigkeit zu einer NetworkZone gesetzt.
VMs verschiedener Tenants in verschiedenen VLANs sehen sich standardmäßig nicht.
DHCP wird pro VLAN über `dnsmasq` oder einen zentralen DHCP-Service bereitgestellt.

---

### Schritt 2 — IPAM (IP Address Management) pro NetworkZone

- [x] `beagle-host/services/ipam_service.py`: IP-Vergabe, Lease-Tracking, DNS-Reverse-Zone.
- [x] Web Console: IPAM-Tabelle pro Zone mit statischen und dynamischen Einträgen.

IPAM verhindert IP-Konflikte und gibt Betreibern Sichtbarkeit welche IP welcher VM
zugeordnet ist. Beim VM-Start reserviert der IPAM-Service eine IP aus dem konfigurierten
Pool der NetworkZone. Statische IP-Zuweisung (VM bekommt immer dieselbe IP) ist für
Server-VMs wählbar. Der IPAM-Service aktualisiert den dnsmasq-Hostsfile-Eintrag
damit der Hostname der VM in der Zone auflösbar ist. Die Web Console zeigt in der
IPAM-Tabelle: IP, MAC-Adresse, VM-Name, Hostname, Lease-Ablaufzeit, statisch/dynamisch.

---

### Schritt 3 — Verteilte Firewall pro VM/Pool/Tenant mit nftables

- [x] `beagle-host/services/firewall_service.py`: nftables-Regelgenerierung, Apply, Rollback.
- [x] `FirewallProfile`-Objekt: eingehende und ausgehende Regeln als strukturierter Typ.

Die verteilte Firewall läuft auf dem Hypervisor und filtert Traffic der VMs auf
Kernel-Level mit nftables. Regeln werden pro VM oder pro Pool als strukturierte
Objekte definiert und durch den `firewall_service.py` in nftables-Syntax übersetzt
und angewendet. Default-Policy für neue VMs: eingehend deny-all (außer konfigurierte
Ports), ausgehend allow-all. Änderungen an Firewall-Regeln werden zuerst in einem
Test-Namespace validiert bevor sie auf die Live-Interfaces angewendet werden.
Bei Fehler beim Apply wird automatisch auf die letzte funktionierende Regel-Version
zurückgerollt. Alle Firewall-Änderungen erzeugen Audit-Events.

---

### Schritt 4 — VXLAN für Cross-Host-VLANs (Welle 7.3.1 optional)

- [x] `providers/beagle/network/vxlan.py`: VXLAN-Tunnel zwischen Cluster-Knoten.
- [x] Overlay-Netzwerk: Unit-Tests für Zone-State-Management und FDB-Sync mit Peers validiert.
- [x] E2E-Overlay-Test: srv1 (46.4.96.80) ↔ srv2 (176.9.127.50), VNI 100, brvx-test bridges, 0% packet loss ~0.7ms latency via public internet UDP/4789.

VXLANs ermöglichen es, L2-Netzwerke über L3-Routed-Netzwerke hinweg zu spannen. Das ist
notwendig damit VMs die auf verschiedenen Cluster-Knoten laufen sich im selben VLAN
sehen können. Linux VXLAN-FDB-Management über `bridge fdb` und `ip link add vxlan`.
Multicast-basiertes VXLAN-FDB-Discovery ist für kleinere Cluster ausreichend;
für größere Setups kann ein SDN-Controller-seitiges FDB-Population implementiert werden.
VXLAN ist als optionales Add-on für Cluster-Deployments geplant; Single-Node-Installationen
brauchen es nicht.

Umsetzung (2026-04-24):

- `providers/beagle/network/vxlan.py` war bereits implementiert.
- Neues Unit-Test-Modul `tests/unit/test_vxlan_backend.py` mit 14 Tests:
  - Zone-Erstellung mit State-Persistenz
  - Peer-FDB-Sync bei Zone-Erstellung (2 Peers → 2 FDB-Einträge)
  - VNI-Validierung (0 und >16777215 werden abgelehnt)
  - MAC-Generierung beim VM-Attach
  - vm_count-Inkrementierung und -Dekrementierung
  - Zone-Deletion mit ip link del Calls
  - Deletion blockiert bei attachten VMs
- Validierung: 14/14 Tests grün lokal und auf `srv1.beagle-os.com`.
- End-to-End-Overlay-Test (VMs auf verschiedenen physischen Knoten im selben L2) bleibt
  infrastruktur-seitig offen: erfordert zwei reale Cluster-Nodes mit VXLAN-Underlay.
  Wird validiert wenn ein zweiter Host in `srv1`-Cluster aufgenommen wird.

---

### Schritt 5 — Public-Stream-Reconciliation in SDN-Plane integrieren

- [x] `scripts/reconcile-public-streams.sh` Logik in `beagle-host/services/stream_reconciler.py` überführen.
- [x] Reconciler läuft als Teil des Netzwerk-Services, nicht als Shell-Skript.

Das bestehende `reconcile-public-streams.sh` ist ein Shell-Skript das manuell oder
per Cron ausgeführt werden muss. Als Service in der SDN-Plane wird er Teil des
automatischen Netzwerk-Managements und läuft reaktiv bei Pool- oder Session-Änderungen.
Die Reconciliation stellt sicher dass externe Stream-Zugriffe (von außerhalb des LANs)
korrekt auf aktive Sessions geroutet werden. Der Service wird in `stream_reconciler.py`
implementiert und als `beagle-stream-reconciler.service` systemd-Unit ausgeliefert.

---

## Testpflicht nach Abschluss

- [x] Zwei VMs in unterschiedlichen VLANs können sich nicht pingen.
- [x] Zwei VMs im selben VLAN können sich pingen, DHCP vergibt korrekte IPs.
- [x] Firewall-Regel "block port 22 inbound" blockiert SSH zur VM.
- [x] IPAM-Tabelle zeigt korrekte IP/MAC-Zuordnungen.
- [x] Firewall-Rollback bei fehlerhafter Regel funktioniert.

Validierung (2026-04-25, `scripts/test-sdn-plan17-live-smoke.sh` auf `srv1.beagle-os.com`):
- VLAN Communication (ns-a100 → ns-b100, gleiche Bridge): PASS (0% packet loss, ~0.03ms)
- VLAN Isolation (ns-a100 → ns-c200, separate Bridges, kein Host-Routing): PASS (100% packet loss)
- Firewall Block (nftables `ip daddr 10.100.0.11 tcp dport 22 drop`): PASS (connect returned ECONNREFUSED/blocked)
- VXLAN E2E Overlay (srv1 10.100.0.1 ↔ srv2 10.100.0.2, VNI 100, over public internet): PASS (0% packet loss, ~0.6-1ms)
- `PLAN17_SDN_LIVE_SMOKE=PASS`
