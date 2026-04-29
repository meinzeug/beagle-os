# 01 — Plattform: Cluster, Storage, HA, VDI, GPU, Netzwerk

**Scope**: Multi-Node-Virtualisierungsplattform (KVM/libvirt) — Cluster, Storage, HA, VDI-Pools, GPU, SDN, Backup.
**Quelle**: konsolidiert aus `docs/archive/gofuture/07-12,16,17` und `docs/archive/goenterprise/04,06,10`.

---

## Cluster + HA (Foundation)

- [x] Cluster-Foundation Welle 7.0.0 (siehe `docs/archive/gofuture/07-cluster-foundation.md`)
- [x] HA-Manager + Fencing + Anti-Affinity (Welle 7.0.2)
- [x] Cluster-Ops in WebUI (Create/Join/Drain/Member-Mgmt) live auf srv1+srv2
- [x] Live Session Handover als produktives Feature

## Storage Plane

- [x] StorageClass-Abstraktion + Backends (Welle 7.0.1)
- [x] Snapshot/Clone/Backup-Targets via Provider-Seam
- [ ] Reale ZFS+Ceph-Backend-Validierung auf Hardware-Pool (R3 Gate)

## Backup + Disaster Recovery

- [x] Backup-Service inkl. 5GB-Lasttest auf srv1 (PASS 2026-04-29)
- [x] Backup-Replikation auf zweiten Node nachgewiesen
- [ ] Backup → Restore einer echten VM-Disk auf frischem Cleanhost reproduzierbar (R3)
- [ ] Disaster-Recovery-Runbook getestet und in `docs/runbooks/` (R4)

## VDI Pools

- [x] VDI Pools + Templates (Welle 7.1.0) — Lifecycle-Tests gruen
- [x] Quotas/Recycling produktiv

## GPU Plane

- [x] GPU Passthrough + vGPU Surface (Welle 7.1.2)
- [ ] GPU-Pool Inventory + Auslastung in WebUI auf echter Hardware abgenommen (R3)
- [ ] Reboot-Proof: VFIO-Konfiguration ueberlebt Host-Reboot auf Hardware (R3)
- [ ] vGPU/MDEV nur als bestanden markieren wenn Hardware + Lizenz real vorliegen

## SDN + Firewall

- [x] VLAN + IPAM + nftables (Welle 7.3.1)
- [ ] Distributed-Firewall-Regeln in WebUI bedienbar (Backlog)

## Smart Scheduler / Placement

- [x] AI Smart Scheduler (Welle 7.0.3)
- [ ] Placement-Hints + Predictive Scheduling auf Mehr-Node-Pool validiert (Backlog)
