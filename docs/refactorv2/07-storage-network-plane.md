# 07 — Storage- und Netzwerk-Plane

Stand: 2026-04-20

## Storage-Plane

### Heute

- Beagle/libvirt nutzt `local`-Pool (Directory) und libvirt-Networks (`beagle`).
- Storage-Wahl ist implizit; keine Pool-Klassen, keine Quoten, keine zentrale Snapshot-Policy.

### Ziel 7.0

#### Pool-Abstraktion

`StorageClass` Contract in `core/virtualization/storage.py` (neu).

Built-in Provider-Implementierungen im Beagle-Provider:

| Backend | Use Case |
|---|---|
| `directory` | Test, kleine Hosts |
| `lvm-thin` | klassischer single-node Block-Storage |
| `zfs` | snapshots, send/recv replication, Bit-rot Schutz |
| `nfs` | shared storage fuer einfache Live-Migration |
| `ceph-rbd` | hyperkonvergent, scale-out, HA |
| `longhorn` | hyperkonvergent K8s-affin |

Optional: PBS-Datastore als read-only Restore-Source.

#### StorageClass-Schema

```yaml
StorageClass:
  id: sc-fast-zfs
  tenant: acme        # optional, sonst global
  provider: zfs
  config:
    pool: tank/desktops
    compression: lz4
    recordsize: 64K
  default_for: [desktops]
  thin: true
  snapshot_policy:
    hourly: 24
    daily: 14
    weekly: 8
    monthly: 6
  quota_gb_per_vm: 200
  quota_gb_per_tenant: 5000
  encryption: at_rest:zfs-native
```

#### Snapshots + Clones

- Einheitlicher Service `services/storage_snapshot.py`.
- Snapshots sind first-class Audit-Subjects.
- Linked-Clone-Support (qcow2 backing chain oder zfs clone).
- Garbage Collection mit Retention-Policy.

#### Live-Migration vs Storage

- Shared Storage (NFS, Ceph, ZFS-over-NFS): live-migration trivial.
- Local Storage: storage-pull-Migration ueber libvirt copy-storage-on (langsam, aber moeglich).
- Pool-Klassen-Metadaten flaggen Live-Migration-Faehigkeit.

## Netzwerk-Plane

### Heute

- libvirt Bridge `beagle` (siehe `scripts/install-beagle-host-services.sh`, `services/ubuntu_beagle_provisioning.py`).
- Public-Stream-Reconciliation ueber `scripts/reconcile-public-streams.sh` (nft-Regeln auf Bridge-IF).

### Ziel 7.0

#### NetworkZone-Schema

```yaml
NetworkZone:
  id: zone-acme-prod
  tenant: acme
  type: vlan | vxlan | bridge | sdn-overlay
  config:
    vlan_id: 102
    parent: bond0
  ipam:
    cidr: 10.10.0.0/16
    gateway: 10.10.0.1
    dns: [10.10.0.10, 10.10.0.11]
    dhcp: true
  firewall_profile: fp-desktop-default
```

#### SDN-Optionen

- **VLAN** (Linux Bridge VLAN aware) — Default, einfach.
- **VXLAN** mit Multicast oder Unicast-Map — fuer Multi-Host Mandanten-Isolation.
- **EVPN-light** — optional, wenn ein BGP-Daemon (FRR) konfiguriert ist.

#### Distributed Firewall

- nftables-basiert pro Host.
- Regeln werden zentral in `services/firewall_profile.py` verwaltet, pro Host gerendert und reloaded.
- Profile-Vererbung: tenant -> pool -> vm.
- Default-Deny im Tenant-Vnet, explicit allow-Regeln fuer Streaming-Ports und Admin-RDP/SSH.

#### Public Stream Path

- bestehender Reconciler bleibt, wird aber Teil der SDN-Plane (`services/sdn_public_streams.py`).
- Endpoint-Public-Reach ueber NAT/PortForward wird Profil-konfigurierbar.
- Optional: WireGuard-basiertes Endpoint-VPN fuer Remote-Endpoints, sodass keine Public-Ports per VM noetig sind.

#### IPAM

- Pro NetworkZone eigener IP-Pool.
- DHCP-Reservierung pro VM (MAC-Adresse stabil aus Pool-Template).
- A/AAAA-Eintraege optional in internen DNS via `services/dns_internal.py`.

## Migration

- Bestehende `beagle`-Bridge wird als implizite NetworkZone `zone-default` migriert.
- Bestehende `local` directory pool wird als StorageClass `sc-local-default` migriert.
- VMs behalten ihre bestehenden Bindings; neue Pools nutzen die neuen Konzepte.
