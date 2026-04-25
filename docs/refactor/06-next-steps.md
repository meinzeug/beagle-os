# Next Steps

## Stand (2026-04-25) — Cluster-Metriken und Migration-Infrastruktur

**Zuletzt erledigt**:
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
- **Migration-Infrastruktur verifiziert**:
  - root SSH-Key srv1 → srv2 (via `beagle-1` hostname) eingerichtet
  - `virsh -c qemu+ssh://root@beagle-1/system` funktioniert
  - Live-Migration gestartet und zu 23% validiert (beagle-100, `--copy-storage-inc`)
  - Migration abgebrochen (6.4 GB physisch bei 1 TB Virtual-Disk dauert ~15 min)
  - **Hinweis für Produktion**: `--copy-storage-inc` erfordert pre-created sparse qcow2 auf Ziel-Node;
    für `--copy-storage-all` muss genug Speicher für Preallokation vorhanden sein (schlägt bei 1 TB fehl)
    → Empfehlung: Shared Storage (NFS/Ceph) für transparente Migration ohne `--copy-storage`
- **GoEnterprise: VM Stateless Reset** umgesetzt:
  - Neuer Provider-Contract + Implementierung `reset_vm_to_snapshot(...)`
  - Pool-Manager-Wiring aktiv (`reset_vm_to_template`), nutzt Template-`snapshot_name`
- **GoEnterprise: RBAC kiosk_operator** umgesetzt:
  - Neue Default-Rolle `kiosk_operator` mit `vm:read`, `vm:power`
  - VM-Power-Endpoint nutzt jetzt Permission `vm:power` (Backwards-Compat für `vm:mutate` bleibt)

---

### Verbleibende Punkte (nach Priorität)

1. **Plan 09 Schritt 6**: Branch-Protection-Regeln in GitHub repository settings aktivieren.
   _Manueller Schritt im GitHub UI._

2. **Cluster-Sicherheit (optional)**: iptables-Regel für Port 9088 nur srv1↔srv2
   (Details in `docs/refactor/11-security-findings.md` S-020).

3. **Live-Migration vollständig validieren**: Migration einer kleinen Test-VM (< 20 GB) von beagle-0 → beagle-1
   über die API (`POST /api/v1/virtualization/vms/{vmid}/migrate`, `target_node: beagle-1`).
