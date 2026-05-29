# Beagle OS - Enterprise Readiness Snapshot

Stand: 2026-05-29

Version: 8.3.4

Priority source: [lasthope/05-diamond-plan.md](lasthope/05-diamond-plan.md)

This file is the quick status view. It is not a backlog. Open work is tracked in
[lasthope/](lasthope/) and the five [checklists/](checklists/).

## Current State

| Area | Status | Notes |
|---|---|---|
| Repo architecture | green | Beagle provider is the active provider path; KVM/libvirt is the target stack. |
| Web console/control plane | green/yellow | Main surfaces exist and are used; product gates still require fresh install and VM lifecycle evidence. |
| BeagleStream runtime | yellow | VM100/TC live path has been hot-validated repeatedly; cold-boot from fresh artifacts still needs gate evidence. |
| Thin client runtime | yellow | TC `192.168.178.30` has live fixes for launcher lifecycle and visible startup steps; fresh payload boot remains open. |
| VM guest lifecycle | yellow | VM100 path is heavily validated, but new VM from WebUI through firstboot/reboot/desktop is still an open P0 gate. |
| Release artifacts | yellow | Current repo version is `8.3.4`; BeagleStream defaults use latest release assets. R1 clean install from current artifacts remains open. |
| Backup/restore | red/yellow | Runbook exists; real VM-disk restore on fresh/second host is still open. |
| Two-host operation | red/yellow | Requires `srv1` + `srv2` join/drain/failover evidence. |
| Security/compliance | yellow/red | Auth/RBAC/audit surfaces exist; OIDC/SCIM/debug-secret hardening and external review remain open. |
| GPU/R3 | yellow/red | Some hardware inventory/proof exists historically; NVENC/VFIO reboot/vGPU gates remain open. |

## Active Blockers Before A Pilot Claim

1. R1 clean install from current release artifacts on a blank host.
2. New VM provisioning from WebUI through firstboot, reboot, desktop, and `ready` state.
3. Cold-boot BeagleStream E2E with fresh TC payload and no live hotpatch.
4. WireGuard direct-vs-tunnel stream latency measurements.
5. Backup/restore of a real VM disk with boot/hash evidence.
6. Update and rollback proof from release artifacts.

## Recently Closed Evidence

- TC stream launcher reentry and lock-FD inheritance fixed in repo and hot-deployed.
- VM stream-server healthcheck/guardian no longer restarts an active server solely because readiness probes flap.
- TC startup UI now renders progressing steps instead of freezing on the initial HTML state.
- BeagleStream client/server default artifact wiring uses GitHub `releases/latest/download` paths.

## How To Read This Snapshot

- Green means implemented and backed by current evidence.
- Yellow means implementation exists but gate evidence is incomplete or hardware-specific.
- Red means external hardware, clean environment, or third-party review is still required.