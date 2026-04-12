# Refactor Plan

## Strategic North Star

- Beagle must not stop at "Proxmox abstraction".
- The target is a first-party Beagle virtualization product/provider, with Proxmox reduced to one optional provider among several.
- The target install surface is a Beagle-owned bare-metal server installer ISO with two explicit choices:
  - `Beagle OS standalone`
  - `Beagle OS with Proxmox`
- The target operator surface is a Beagle-owned Web Console; Proxmox UI integration is a migration bridge, not the end-state UI.
- Every refactor slice should therefore be judged by two questions:
  - does it reduce direct Proxmox dependency now?
  - does it make a future first-party Beagle provider easier to add?

## Status Overview

- Phase 0 Analysis: baseline completed in this run
- Phase 1 Target architecture: baseline completed in this run
- Phase 2 Proxmox UI refactor: started and partially extracted
- Phase 2b Beagle Web Console planning: not yet started explicitly enough
- Provider abstraction foundation: started in the browser-side UI path
- Server installer dual-mode architecture (`standalone` vs `with Proxmox`): started only implicitly, not yet explicit enough
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

### Slice 8: Beagle server installer dual-mode architecture

Goals:

- make the server installer explicitly offer:
  - `Beagle OS standalone`
  - `Beagle OS with Proxmox`
- route both branches through one generic host bootstrap contract
- isolate Proxmox repositories/packages/post-install assumptions as one optional install path

Exit criteria:

- standalone and Proxmox-enabled installs are both first-class documented paths
- host bootstrap no longer assumes Proxmox packages by default

### Slice 9: Beagle Web Console foundation

Goals:

- define the dedicated host UI surface that replaces Proxmox UI as the long-term operator console
- reuse the existing provider-neutral browser/core contracts where possible
- stop treating `proxmox-ui/` as the eventual product UI

Exit criteria:

- dedicated Beagle Web Console module/root is defined and begins consuming provider-neutral host APIs
- required host UI contracts for inventory, VM state/config, lifecycle, storage, and network are explicit

## Provider Independence Roadmap

This roadmap is the missing bridge between today's Proxmox-first repo and the desired Beagle-owned virtualization product.

### Stage 1: Thin control-plane and UI seams

Goals:

- finish shrinking `proxmox-ui/beagle-ui.js`
- continue splitting `beagle-host/bin/beagle-control-plane.py`
- remove business logic from runtime entrypoints

### Stage 2: Provider-complete host abstraction

Goals:

- route host bootstrap through a provider registry and explicit provider contract instead of directly importing a concrete provider
- inventory all remaining direct `qm` / `pvesh` / Proxmox package assumptions
- move them behind provider-facing modules or services
- make installers and scripts consume the same seams

### Stage 3: Thin-client and endpoint decoupling

Goals:

- remove direct Proxmox assumptions from thin-client API and runtime flows
- isolate SPICE- and Proxmox-specific launch behavior as optional provider integrations

### Stage 4: Stable provider contracts

Goals:

- formalize the host/node/vm/storage/network/lifecycle contracts all providers must implement
- add contract-level validation or conformance checks

### Stage 5: First non-Proxmox proving ground

Goals:

- add either a mock provider or a second lightweight provider implementation
- prove the contracts are not just wrappers around Proxmox naming

### Stage 6: First-party Beagle provider design

Goals:

- define the first-party Beagle provider/runtime layout
- carve out the modules needed for Beagle-owned compute, storage, network, and lifecycle
- keep the working path compatible with the same provider contracts

### Stage 7: Beagle standalone host operation

Goals:

- make `Beagle OS standalone` on bare metal a real installable and supportable path
- run host bootstrap, control plane, Web Console, fleet, provisioning, inventory, and installer flows without Proxmox

- reduce Proxmox to an optional compatibility provider

### Stage 8: Beagle-first operation

Goals:

- make the Beagle Web Console the primary operator surface
- make the Beagle provider the preferred default provider for new standalone installs
- keep the Proxmox path fully compatible as an optional backend and install mode

### Stage 9: Optional external providers

Goals:

- support Proxmox and other external providers as optional adapters
- treat the Beagle-owned provider as the architecture center instead of any external backend

## Not In Scope for One Shot

These changes must not be attempted as one commit:

- moving all modules to a new top-level layout
- replacing all Bash with another language
- changing public artifact names or URLs without synchronized deployment work
- changing kiosk runtime ownership of GeForce NOW
