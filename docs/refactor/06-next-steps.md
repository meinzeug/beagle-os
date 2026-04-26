# Next Steps

## Stand (2026-05-XX, GoAdvanced Plan 07 vollständig: Async Job Queue)

**Zuletzt erledigt**:
- Plan 07 Schritt 3 komplett: `POST /api/v1/cluster/migrate` → enqueue + 202 (cluster_http_surface)
- Plan 07 Schritt 5: `Idempotency-Key`-Header in HTTP-Surfaces verdrahtet (backup + snapshot)
- Plan 07 Schritte 1–5 vollständig abgeschlossen
- Plan 10 Schritt 7 CI: `.github/workflows/e2e-nightly.yml` erstellt
- Test-Baseline: 968 passed (unit + integration), 0 Regressions

**Nächste konkrete Schritte**:

1. **Plan 07 Schritt 6** (MEDIUM): Web-UI Jobs-Panel mit SSE-Subscribe + Toast bei Job-Completion.
2. **Plan 09 CI Pipeline**: Restliche CI-Checks (lint, security) konsolidieren.
3. **Plan 08 Observability**: Structured logging + Prometheus-Metriken Endpoint.
4. **Plan 09** (HIGH, in Planung): HA-Manager — Prerequisit für Plan 10 Schritt 4 (HA-Failover-Tests).

---

## Stand (2026-04-25, update) — Terraform Provider Fix + Migration Service Wiring

**Zuletzt erledigt (dieser Session)**:
- **Terraform Provider Bugfix** (`728f70e`):
  - `client.requestWithStatus()` hinzugefügt (unterscheidet 404 von anderen Fehlern)
  - `resourceVMRead` fixt: nur Resource-ID löschen bei echtem 404, nicht auf allen Errors
  - Schema-Felder nun bevölkert mit API-Response-Werten
  - Unit-Tests: 4/4 pass (TestClientCreateReadDelete, TestClientReadNotFound, TestClientBadToken, TestApplyCreatesVMDestroyRemovesVM)
  - Validierung: `terraform apply` + `destroy` auf srv1 gegen beagle_vm.test (vmid=9901), APPLY_EXIT=0, DESTROY_EXIT=0 ✅

- **Migration Service: Cluster-Inventory-Wiring** (`fdc308d`):
  - Neuer Helper `_cluster_nodes_for_migration()` ruft `build_cluster_inventory()` auf
  - Wiring updated: `migration_service`, `ha_manager_service`, `maintenance_service`, `pool_manager_service` nutzen cluster-aware node list
  - **Folge**: Remote Hypervisoren (z.B. beagle-1) sind jetzt sichtbar als gültige Migrations-Ziele
  - Unit-Tests: 24/24 pass (migration, ha_manager, maintenance, pool_manager)
  - Deployment auf srv1/srv2 + systemctl restart beagle-control-plane → `active` ✅
  - Cluster-Inventory nach Deployment: alle 4 Knoten (beagle-0, beagle-1, srv1, srv2) online ✅

- **SSH-Keys für Cross-Node Migration**:
  - Beagle-manager SSH-Keys (ed25519) generiert auf srv1/srv2
  - Cross-authorized: srv1-key in srv2 authorized_keys, srv2-key in srv1 authorized_keys
  - Validierung: `sudo -u beagle-manager ssh root@beagle-1` → CONNECTION_OK ✅
  - `BEAGLE_CLUSTER_MIGRATION_URI_TEMPLATE=qemu+ssh://root@{target_node}/system` in `/etc/beagle/beagle-manager.env` ✅

---

### **Gefundenes QEMU+SSH Migration-Deadlock-Problem**
Virsh-basierte Live-Migration über `qemu+ssh` deadlockt bei allen Versuch-Kombinationen:
- `virsh migrate --live --copy-storage-inc`: Timeout nach 60-120s, kein Fortschritt
- `virsh migrate --live --copy-storage-all`: Gleiches Verhalten
- `virsh migrate --persistent --undefinesource`: Bringt libvirt in Deadlock (`another migration job already running`)
- `virsh domjobinfo` während Migration: Timeout (kompletter libvirt-Lock)
- Root-Ursache: Qemu+SSH Migration-Protokoll oder Libvirt-Konfiguration inkompatibel (erfordert tiefere QEMU/Libvirt-Untersuchung)

**Implikation für Beagle Migration-API**:
- API-Layer ist funktional (kann Ziel-Knoten korrekt identifizieren, SSH-Schlüssel vorhanden, qemu+ssh Connectivity OK)
- **Aber**: Virtualisierungs-Infrastruktur-Layer (virsh+qemu+ssh) ist fehlerhaft und braucht separate Untersuchung
- **Workaround für Multi-Node-Produktion**: Shared Storage (NFS/Ceph) verwenden statt Storage-Copy während Migration
- Migration-API wird korrekt arbeiten, sobald Shared Storage vorhanden oder QEMU+SSH-Protokoll repariert ist

## Zuletzt erledigt (vorherige Session, 2026-04-25)

- GoFuture Gate: alle 20 Pläne (docs/gofuture/) abgeschlossen (d588939)
- `service_registry.py` extrahiert: `beagle-control-plane.py` 4964 → 1627 LOC (e2e4c38)
- `request_handler_mixin.py` extrahiert: `beagle-control-plane.py` 1627 → 899 LOC (03bd203)
- **Multi-Node Cluster**: srv1 (46.4.96.80) + srv2 (176.9.127.50) verbunden (52f5d48)
  - `BEAGLE_MANAGER_LISTEN_HOST=0.0.0.0` auf beiden Servern
  - members.json URLs korrigiert (127.0.0.1 → echte IPs)
  - srv2 via Join-Token beigetreten: `3/3 nodes online, 0 unreachable`
- **Cluster-Metriken**: `beagle-0` (srv1) und `beagle-1` (srv2) zeigen echte RAM/CPU-Werte
  - Root-Ursache: Beide Hypervisoren hießen `beagle-0` (Name-Kollision)
  - Fix: `BEAGLE_BEAGLE_PROVIDER_DEFAULT_NODE=beagle-0` auf srv1, `beagle-1` auf srv2
  - `/api/v1/cluster/nodes` zeigt jetzt `beagle-0: 64GB/12CPU`, `beagle-1: 64GB/8CPU`
- **GoEnterprise: VM Stateless Reset** umgesetzt:
  - Neuer Provider-Contract + Implementierung `reset_vm_to_snapshot(...)`
  - Pool-Manager-Wiring aktiv (`reset_vm_to_template`), nutzt Template-`snapshot_name`
- **GoEnterprise: RBAC kiosk_operator** umgesetzt:
  - Neue Default-Rolle `kiosk_operator` mit `vm:read`, `vm:power`
  - VM-Power-Endpoint nutzt jetzt Permission `vm:power` (Backwards-Compat für `vm:mutate` bleibt)
- **Cluster-Sicherheit Port 9088 gehärtet**:
  - Neues reproduzierbares Script `scripts/harden-cluster-api-iptables.sh` (idempotent, Chain `BEAGLE_CLUSTER_API_9088`)
  - Live ausgerollt auf `srv1`/`srv2` mit Peer-Allowlist (`srv1` erlaubt `176.9.127.50`, `srv2` erlaubt `46.4.96.80`)
  - Persistenz aktiviert (`netfilter-persistent` + `iptables-persistent`, `rules.v4` enthält 9088-Chain)

---

### Verbleibende Punkte (nach Priorität)

1. **Plan 09 Schritt 6**: Branch-Protection-Regeln in GitHub repository settings aktivieren.
   _Manueller Schritt im GitHub UI; nicht Teil der technischen Untersetzung._

2. **QEMU+SSH Migration-Protokoll debuggen** (optional, nicht auf kritischem Pfad):
   - Untersuche Libvirt-Konfiguration, Firewall-Regeln, SSH-Agent-Issues
   - Alternativ: Shared Storage für Migration evaluieren
