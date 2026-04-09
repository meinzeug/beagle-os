# Refactor Plan

## Status Overview

- Phase 0 Analysis: baseline completed in this run
- Phase 1 Target architecture: baseline completed in this run
- Phase 2 Proxmox UI refactor: not started
- Phase 3 Thin client runtime refactor: not started
- Phase 4 Security hardening: not started
- Phase 5 Packaging / build modularization: started only for process guardrails
- Phase 6 Clear module separation: not started

## Execution Rules

- no big-bang changes
- preserve current runtime entrypoints
- pair structural changes with documentation updates
- keep the repo in a runnable state after every slice

## Planned Slices

### Slice 1: Refactor baseline and enforcement

Goals:

- create `docs/refactor/`
- document current architecture, problems, risks, plan, decisions, progress, and TODOs
- ensure `AGENTS.md` is tracked and no longer ignored
- make `scripts/validate-project.sh` fail if the required documents are missing

Exit criteria:

- required docs exist
- validation checks them
- handoff state is explicit

### Slice 2: Proxmox UI seam extraction

Goals:

- extract configuration and token handling helpers from `proxmox-ui/beagle-ui.js`
- establish `api-client/`, `state/`, `components/`, `provisioning/`, `usb/`, and `utils/` layout
- keep installed runtime behavior identical

Exit criteria:

- no behavior regression in existing UI actions
- `beagle-ui.js` becomes a thin bootstrap entrypoint or composition shell

### Slice 3: Provider abstraction foundation

Goals:

- introduce provider-neutral seams under `core/provider/`, `core/virtualization/`, and `core/platform/`
- implement Proxmox as the first provider under `providers/proxmox/`
- move UI inventory/provisioning/business logic to generic services instead of direct `/api2/json`, `PVE.*`, or raw Proxmox endpoint knowledge

Exit criteria:

- browser-side business logic depends on `core/*` services first
- Proxmox-specific API access is isolated behind `providers/proxmox/`
- remaining direct Proxmox couplings are documented explicitly

### Slice 4: Shared browser-side helpers

Goals:

- remove duplicated token/config/API path logic across:
  - `proxmox-ui/`
  - `extension/`
  - `website/`
- define explicit shared contract for API base and auth header policy

Exit criteria:

- one shared logic source or clearly mirrored modules with aligned tests/checks

### Slice 5: Thin client runtime extraction

Goals:

- separate config, network, pairing, and Moonlight launch concerns
- keep Moonlight runtime path stable
- add smoke validation around the launch path

Exit criteria:

- critical runtime scripts are smaller and clearer
- Moonlight launch still works with current config inputs

### Slice 6: Control-plane extraction

Goals:

- carve out config, routing, inventory, provisioning, and artifact services from `beagle-control-plane.py`
- preserve endpoint URLs and payloads

Exit criteria:

- HTTP entrypoint is substantially thinner
- internal services are separable and easier to test

### Slice 7: Packaging and release contracts

Goals:

- split packaging orchestration into smaller scripts or library helpers
- formalize artifact naming and manifest generation
- add output verification for public artifact filenames and URLs

Exit criteria:

- packaging steps are composable
- release drift across the two servers is easier to detect

## Not In Scope for One Shot

These changes must not be attempted as one commit:

- moving all modules to a new top-level layout
- replacing all Bash with another language
- changing public artifact names or URLs without synchronized deployment work
- changing kiosk runtime ownership of GeForce NOW
