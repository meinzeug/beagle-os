# Beagle OS Documentation

Stand: 2026-05-29

Version: 8.3.4

Operative source of truth: [lasthope/05-diamond-plan.md](lasthope/05-diamond-plan.md)

Beagle OS is a standalone KVM/libvirt virtualization, streaming, endpoint OS,
and gaming kiosk platform. This documentation is intentionally split into a
small set of active documents and a clearly marked archive.

## Active Structure

| Area | Role | Files |
|---|---|---|
| Product gates | What must be proven before pilot/enterprise use | [lasthope/](lasthope/) |
| Implementation backlog | Detailed open and completed tasks | [checklists/](checklists/) |
| Architecture map | Current system shape and ownership boundaries | [MASTER-PLAN.md](MASTER-PLAN.md), [architecture/](architecture/) |
| Status snapshot | 30-second readiness summary | [STATUS.md](STATUS.md) |
| Runbooks | Operator procedures and validation records | [runbooks/](runbooks/) |
| Security | Security model, secrets, TLS exceptions | [security/](security/) |
| API | OpenAPI and compatibility policy | [api/](api/) |
| Deployment | Build/install/deployment procedures | [deployment/](deployment/) |
| Observability | Monitoring setup and dashboards | [observability/](observability/) |
| Work log | Chronological progress, decisions, risks | [refactor/](refactor/) |
| Historical plans | Non-operative old plans and research | [archive/](archive/) |

## Canonical Rules

1. [lasthope/05-diamond-plan.md](lasthope/05-diamond-plan.md) controls priority.
2. Open implementation work lives in exactly one file under [checklists/](checklists/).
3. Runtime or hardware gates are not closed by docs alone; they need real host evidence.
4. Live hotfixes count only after the same fix is reproducible in the repo.
5. [archive/](archive/) is historical background, not a task source.
6. [refactor/05-progress.md](refactor/05-progress.md) is append-only evidence/history, not the current plan.
7. [refactor/06-next-steps.md](refactor/06-next-steps.md) may summarize recent handoff state, but it must not contradict LastHope.

## Current Product Direction

- Active provider: [../providers/beagle](../providers/beagle) and [../beagle-host/providers](../beagle-host/providers).
- Operator UI: [../website](../website).
- BeagleStream client/server artifacts are consumed from GitHub `releases/latest/download` by default.
- `providers/proxmox/` and `proxmox-ui/` are not active product paths.
- Legacy `pve-thin-client` file/service names still exist as endpoint-runtime compatibility names; they are not a Proxmox provider dependency.

## Where To Put New Information

| Information | Put it here |
|---|---|
| A new open task | One of [checklists/01-platform.md](checklists/01-platform.md), [checklists/02-streaming-endpoint.md](checklists/02-streaming-endpoint.md), [checklists/03-security.md](checklists/03-security.md), [checklists/04-quality-ci.md](checklists/04-quality-ci.md), [checklists/05-release-operations.md](checklists/05-release-operations.md) |
| A completed live validation | Relevant checklist plus [refactor/05-progress.md](refactor/05-progress.md) |
| A handoff note | [refactor/06-next-steps.md](refactor/06-next-steps.md) |
| A security finding | [refactor/11-security-findings.md](refactor/11-security-findings.md) |
| A product gate change | Relevant [lasthope/](lasthope/) file plus checklist |
| Historical context | [archive/](archive/) |

## Non-Goals For Docs Cleanup

- Do not create another master roadmap.
- Do not duplicate checklist items inside new plan files.
- Do not mark hardware/runtime gates complete without real evidence.
- Do not delete historical plans solely because they are old; keep them under [archive/](archive/) with clear status.
