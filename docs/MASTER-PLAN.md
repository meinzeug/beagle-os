# Beagle OS - Architecture and Product Map

Stand: 2026-05-29

Version: 8.3.4

Role: architecture/product map, not the operative backlog.

The operative execution plan is [lasthope/05-diamond-plan.md](lasthope/05-diamond-plan.md).
Detailed tasks live in the five [checklists/](checklists/). Historical planning
material lives under [archive/](archive/) and is not an active task source.

## Product Shape

Beagle OS is a standalone on-prem desktop virtualization and streaming platform:

- Host/control plane: [../beagle-host](../beagle-host), [../core](../core), [../providers/beagle](../providers/beagle)
- Provider model: KVM/libvirt via the Beagle provider only
- Web console: [../website](../website)
- Endpoint OS and thin client: [../beagle-os](../beagle-os), [../thin-client-assistant](../thin-client-assistant)
- BeagleStream runtime: `meinzeug/beagle-stream-server` and `meinzeug/beagle-stream-client` release artifacts consumed by Beagle OS
- Gaming kiosk: [../beagle-kiosk](../beagle-kiosk)
- Install/release tooling: [../server-installer](../server-installer), [../scripts](../scripts)
- API/IaC: [api](api/), [../terraform-provider-beagle](../terraform-provider-beagle), [../scripts/beaglectl.py](../scripts/beaglectl.py)

## Current Repo Facts

- `VERSION` is `8.3.4`.
- Active provider code is under [../providers/beagle](../providers/beagle) and [../beagle-host/providers](../beagle-host/providers).
- BeagleStream client default artifact: `https://github.com/meinzeug/beagle-stream-client/releases/latest/download/BeagleStream-latest-x86_64.AppImage`.
- BeagleStream server guest setup uses the `beagle-stream-server` service path and release asset flow.
- `pve-thin-client` names remain as endpoint-runtime compatibility names. They are not a Proxmox provider dependency.
- `docs/archive/*` contains old plans and research. Those files may mention older names or phased plans; they do not override active docs.

## Canonical Ownership

| Topic | Active owner/source |
|---|---|
| Priority and gates | [lasthope/05-diamond-plan.md](lasthope/05-diamond-plan.md) |
| Enterprise gap list | [lasthope/01-enterprise-gap-list.md](lasthope/01-enterprise-gap-list.md) |
| Execution order | [lasthope/02-execution-order.md](lasthope/02-execution-order.md) |
| Platform/cluster/storage/GPU | [checklists/01-platform.md](checklists/01-platform.md) |
| BeagleStream/thin client/kiosk | [checklists/02-streaming-endpoint.md](checklists/02-streaming-endpoint.md) |
| Security/IAM/audit/compliance | [checklists/03-security.md](checklists/03-security.md) |
| CI/quality/observability/UX | [checklists/04-quality-ci.md](checklists/04-quality-ci.md) |
| Release/ops/runbooks/hardware gates | [checklists/05-release-operations.md](checklists/05-release-operations.md) |
| Security findings | [refactor/11-security-findings.md](refactor/11-security-findings.md) |
| Progress log | [refactor/05-progress.md](refactor/05-progress.md) |
| Handoff | [refactor/06-next-steps.md](refactor/06-next-steps.md) |

## What Is Done At Architecture Level

- Beagle OS is KVM/libvirt-first and uses the Beagle provider as the active provider.
- Web console, control plane, runtime services, endpoint OS, and BeagleStream paths exist in the repo.
- BeagleStream release artifacts are integrated through `latest/download` defaults with checksum support.
- TC/VM100 stream lifecycle fixes from 2026-05-29 are reproducible in the repo and hot-validated on the TC/VM100 path.

## What Is Not Done Yet

These remain open until the corresponding LastHope/checklist evidence is produced:

- R1 clean install on a blank host from current release artifacts.
- New VM provisioning from WebUI through firstboot/reboot/desktop without manual hotfix.
- Cold-boot BeagleStream E2E from fresh payload/TC without hotpatch.
- WireGuard stream latency measurements.
- Backup/restore of a real VM disk on a fresh or second host.
- Update and rollback proof from release artifacts.
- Two-host join/drain/failover/session-handover gates.
- Security review and remaining OIDC/SCIM/debug-secret hardening.
- GPU/NVENC/VFIO/vGPU hardware gates.

## Documentation Rules

1. Do not add new roadmap folders under `docs/`.
2. Do not promote archived plans back into active work; move still-relevant items into a checklist.
3. Do not mark runtime/hardware work done without evidence from real hosts.
4. Keep this file short; detailed history belongs in [refactor/05-progress.md](refactor/05-progress.md).
5. When this file and LastHope disagree, LastHope controls execution priority.