# Beagle OS Agent Instructions

## Diamond Plan trigger

When the user says **"verfolge den diamond plan"**, treat
`docs/lasthope/05-diamond-plan.md` as the controlling execution plan for all
Beagle OS repository development.

In that mode:

1. Start with the earliest unfinished Diamond gate D0..D7.
2. Prefer work that directly advances Clean-Install, VM-Lifecycle,
   BeagleStream E2E, Backup/Restore, Update/Rollback, two-host operation,
   Security review readiness, hardware proof, or launch readiness.
3. Do not add comfort features while a P0/D0-D3 gate is red unless the user
   explicitly overrides the Diamond Plan.
4. Every live hotfix must be made reproducible in the repo before it is counted
   as done.
5. Hardware/runtime gates require real host evidence, not only mocks or unit
   tests.
6. Update the relevant checklist, runbook, progress log, or security findings
   document when a Diamond gate changes state.

Canonical references:

- `docs/lasthope/05-diamond-plan.md`
- `docs/lasthope/README.md`
- `docs/lasthope/01-enterprise-gap-list.md`
- `docs/lasthope/02-execution-order.md`
- `docs/lasthope/04-validation-matrix.md`
- `docs/checklists/`
- `docs/refactor/05-progress.md`
- `docs/refactor/06-next-steps.md`
- `docs/refactor/11-security-findings.md`

## General project direction

Beagle OS is a standalone KVM/libvirt-based virtualization, streaming, endpoint
OS, and gaming kiosk platform. The active provider is `providers/beagle/`.
Do not introduce new Proxmox coupling or new references to `qm`, `pvesh`,
`/api2/json`, `PVEAuthCookie`, or Proxmox file paths.

Keep changes incremental, reproducible, tested, and aligned with the active
checklists. Prefer code and validation over long planning-only updates.

