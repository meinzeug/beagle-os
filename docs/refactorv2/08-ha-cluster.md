# 08 — Cluster, HA, Live-Migration

Stand: 2026-04-20

## Stand heute

- Single-Node Beagle-Host. `beagle-control-plane` laeuft pro Host. Kein Quorum, keine Inter-Host-Koordination.
- Provider-Inventories sind pro Host (libvirt) bzw. pro Proxmox-Cluster.

## Ziel 7.0

### Cluster-Modell

- Eine **Beagle-Cluster-Instanz** umfasst 1 - N Beagle-Hosts.
- Single-Node-Mode bleibt voll unterstuetzt (Cluster-Groesse = 1).
- Mehrknoten erfordern **>= 3 Knoten** fuer Quorum (oder 2-Node + externer Witness).

### Cluster-Store

Anforderungen:

- Konsistente Replikation der Konfig (Pools, Templates, Users, Entitlements, Storage/Network-Configs).
- Leader-Election fuer schreibende Operationen.
- Recovery nach Knoten-Ausfall ohne manuelle Eingriffe.

Optionen (Entscheidung in `docs/refactor/07-decisions.md` zu fuehren):

1. **etcd** (kubernetes-style, RAFT, mTLS) — reife Wahl, bringt jedoch eigenes Daemon mit.
2. **Litestream + SQLite mit Lease-basierter Leader-Election** — leichter, aber eigenes Failover-Handling.
3. **Corosync + pmxcfs-aequivalent** — Proxmox-Stil, gut erprobt, aber spezifischer Stack.

Empfehlung Welle 7.0.0: **etcd** als pragmatische Wahl mit reichem Tooling.

### Inter-Host-RPC

- gRPC oder REST ueber mTLS, Cluster-CA wird beim Cluster-Init ausgerollt.
- jeder Knoten hat ein Cluster-Zertifikat + Knoten-Identity.
- Operationen (start_vm, migrate_vm, snapshot, ...) werden vom Leader an den zustaendigen Host geroutet.

### Live-Migration

- Bevorzugt libvirt managed (`virsh migrate --live --tunnelled --p2p ...`).
- Voraussetzung: kompatible CPU-Modelle, gleiches QEMU/libvirt Major.
- Storage:
  - shared (NFS/Ceph/iSCSI/ZFS-over-NFS) -> direkt;
  - lokal -> storage-copy-on-migrate via `--copy-storage-all` (langsamer).
- Vor-Migration-Checks: cpu compat, ressourcen frei, anti-affinity, network bridges vorhanden.

### Scheduler

- **Placement-Service** (`services/placement.py` neu):
  - Eingaben: Pool-Resource-Constraints, GPU-Klassen, Network/Storage-Bindings, Affinity/Anti-Affinity.
  - Ausgaben: Zielknoten fuer neue VMs, Migration-Vorschlaege bei Knoten-Drain.
- Ressourcen-Score: cpu_overcommit, mem_overcommit, free_gpu_slots, storage_iops_headroom.

### HA-Manager

- Pro Knoten ein **Watchdog** (Software-Watchdog ueber `/dev/watchdog0` falls vorhanden).
- HA-Status pro VM:
  - `none` (keine Recovery),
  - `restart-on-host` (lokal restart),
  - `restart-on-cluster` (any healthy node),
  - `migrate-only`.
- Fencing: bei Knoten-Verlust isolieren wir vor Restart, um Split-Brain bei shared storage zu vermeiden (z.B. ueber IPMI-/BMC-Hooks oder Power-Plug-Hooks; Default: warten auf Lease-Expiry + STONITH).
- Maintenance-Mode: drain alle HA-VMs ab, Knoten ist dann safe fuer Reboot/Upgrade.

### Affinity/Anti-Affinity

- Pro Pool oder VM:
  - "muss zusammen" (z.B. zwei AppServer auf demselben Knoten),
  - "darf nicht zusammen" (z.B. gleiches Pool-Replikat auf verschiedenen Knoten).
- Pruefung im Scheduler vor jeder Placement-/Migration-Entscheidung.

### Cluster-Lifecycle

- `beaglectl cluster init` auf erstem Knoten -> generiert Cluster-CA, etcd-Bootstrap.
- `beaglectl cluster join --token ...` auf weiteren Knoten -> Knoten registriert sich, etcd-Member, Storage-/Network-Discovery.
- `beaglectl cluster leave` -> drain + sicherer Austritt.
- Cluster-Updates: rolling upgrade, ein Knoten nach dem anderen, Health-Gate zwischen Knoten.

### Provider-Neutralitaet

- Cluster-Plane lebt im `core/cluster/` Contract und im Beagle-Provider.
- Der Proxmox-Adapter mappt diese Operationen auf `pvesh`/`qm migrate` und Proxmox-Cluster, ist aber **optional**.
- Keine Proxmox-Spezifika in `services/cluster_*` oder im API-Layer.

### Akzeptanzkriterien fuer Welle 7.0.0 + 7.0.2

- 3-Knoten Cluster aus `beaglectl cluster init/join` reproduzierbar.
- Web Console zeigt Knoten + per-VM-HA-Status.
- Live-Migration einer 4 GB / 60 GB qcow2 VM zwischen zwei Knoten (shared NFS) ohne Stream-Abbruch.
- Knoten-Verlust (Power off): VM mit `restart-on-cluster` startet auf anderem Knoten in <= 60 s.
