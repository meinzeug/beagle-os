# Refactor Problem Analysis

## Summary

The repository is functional and ships meaningful product surfaces, but the internal architecture is still dominated by large files, implicit contracts, duplicated browser logic, and script-heavy control flow. The refactor should preserve behavior while reducing coupling and surfacing explicit contracts.

## Major Structural Problems

### 1. Control-plane monolith

`beagle-host/bin/beagle-control-plane.py` is the single largest source file in the repo at roughly 5900 lines.

It currently mixes:

- HTTP routing
- auth checks
- Proxmox command execution
- cache handling
- VM profile synthesis
- artifact publication metadata
- token issuance
- template rendering
- response serialization

Impact:

- hard to reason about behavior changes
- hard to test in isolation
- high regression risk for even small edits

### 2. Proxmox UI monolith

`proxmox-ui/beagle-ui.js` is roughly 3000 lines and combines:

- configuration loading
- token handling
- API URL resolution
- VM parsing
- UI state
- DOM rendering
- provisioning actions
- export logic

Impact:

- Phase 2 target from `AGENTS.md` is not yet met
- behavior is difficult to isolate and reuse
- future UI changes carry high break risk

### 3. Browser-side duplication

Similar token/config/API helper logic appears in:

- `proxmox-ui/beagle-ui.js`
- `extension/content.js`
- `website/app.js`

Observed overlap:

- session storage handling
- API token prompts or reads
- Beagle API URL derivation
- control-plane URL derivation

Impact:

- inconsistent fixes are likely
- security changes require touching multiple surfaces
- behavior drift between host UI, extension, and website is likely

### 4. Thin client runtime and installer scripts are too large

The endpoint stack currently relies on multiple large shell scripts:

- `thin-client-assistant/usb/pve-thin-client-local-installer.sh`
- `thin-client-assistant/usb/pve-thin-client-usb-installer.sh`
- `thin-client-assistant/usb/pve-thin-client-live-menu.sh`
- `thin-client-assistant/runtime/launch-moonlight.sh`
- `thin-client-assistant/runtime/common.sh`

Impact:

- difficult to test and refactor safely
- configuration, network, pairing, and launch concerns are interleaved
- shell parsing and quoting risk is high

### 5. Proxmox is hard-wired across multiple layers

Direct Proxmox coupling currently exists in at least these areas:

- browser-side VM context and inventory resolution in `proxmox-ui/beagle-ui.js`
- browser extension inventory/profile logic in `extension/content.js`
- control-plane inventory and config reads in `beagle-host/bin/beagle-control-plane.py`
- host reconciliation and artifact generation in `scripts/reconcile-public-streams.sh` and `scripts/prepare-host-downloads.sh`
- guest configuration helpers in `scripts/configure-sunshine-guest.sh`
- thin-client Proxmox API access in `thin-client-assistant/usb/pve-thin-client-proxmox-api.py`
- runtime connection helpers such as `thin-client-assistant/runtime/connect-proxmox-spice.sh`
- bare-metal server bootstrap in `server-installer/.../beagle-server-installer`

Coupling forms:

- direct `/api2/json` calls
- `PVE.*` browser globals
- `qm` and `pvesh` command execution
- Proxmox package/repository bootstrap
- Proxmox-specific VM metadata assumptions

Impact:

- business logic is harder to port to another hypervisor or backend
- UI and control-plane behavior depend on Proxmox semantics instead of explicit contracts
- migration work risks touching many surfaces at once without a stable abstraction layer

### 6. Packaging and release coupling is implicit

`scripts/package.sh` coordinates thin client build, server installer build, kiosk build, checksum generation, and release artifact staging.

Issues:

- many steps are side-effectful
- build responsibilities are not separated into explicit phases
- failure boundaries are coarse
- artifact contracts exist mostly as filenames, not as typed metadata

### 7. Limited automated verification

Current validation covers:

- shell syntax
- Python bytecode compilation
- JavaScript syntax checks
- extension version consistency
- changelog version entry presence

Missing or weak:

- no unit tests
- no integration tests
- no smoke tests for generated installers
- no contract validation for public artifact manifests
- no behavioral verification for UI workflows

## Security and Configuration Findings

### 1. Frontend token handling is too permissive

API tokens are stored or handled in browser contexts:

- `proxmox-ui/beagle-ui.js`
- `extension/content.js`
- `website/app.js`
- `website/index.html`

Risk:

- tokens may be persisted in session storage or entered manually in browser contexts
- browser-side token exposure increases the blast radius of XSS or UI injection issues

### 2. Secrets and credentials flow through env vars and generated artifacts

Examples observed:

- Sunshine passwords
- Proxmox passwords or tokens
- Beagle manager API token
- enrollment tokens

Risk:

- contracts are implicit and scattered
- shell quoting mistakes can cause leakage or breakage
- generated artifacts may accidentally preserve sensitive values longer than intended

### 3. Local build artifacts exist on the control workstation

The local repo currently contains `.build/` and `dist/` directories. This is operationally risky because repository guidance already states that the workstation should act as a control node, not as a heavy build host.

Risk:

- disk pressure
- stale artifact confusion during validation and analysis
- accidental reliance on local outputs

## Architecture Debt by Area

### Host / control plane

- business logic and HTTP transport are tightly coupled
- command execution, caching, and rendering live in the same file
- output contracts are not formalized
- provider logic is mixed with control-plane logic instead of sitting behind an explicit provider seam

### Proxmox UI

- state, rendering, and transport logic are intertwined
- no directory-level modularization yet
- duplicated logic with extension and website
- direct Proxmox inventory access existed inside UI orchestration instead of a provider-neutral virtualization service

### Thin client runtime

- shell scripts are large and multi-purpose
- runtime config is distributed across templates, env files, and generated files
- Moonlight path is critical but not isolated as a stable module

### Gaming kiosk

- Electron main process is still large
- config parsing, GFN launch planning, session state, and store gating live together
- child process lifecycle is not yet separated into a dedicated service module

### Build / packaging

- one script orchestrates many build families
- reproducibility depends on environment discipline more than explicit contracts

## Refactor Opportunities

### Highest leverage

- split `beagle-control-plane.py` into service modules behind a thin HTTP layer
- split `proxmox-ui/beagle-ui.js` into `api-client`, `state`, `components`, `provisioning`, `usb`, and `utils`
- introduce provider-neutral `core/provider`, `core/virtualization`, and `core/platform` seams with Proxmox behind `providers/proxmox`
- formalize endpoint profile and artifact manifest contracts
- introduce shared helpers for duplicated browser-side config/token/API code

### Lowest-risk first steps

- introduce mandatory refactor documentation and progress tracking
- add repository validation for the new documentation baseline
- remove process contradictions such as ignored control documents
- perform small seam extractions without changing runtime behavior

## Conclusion

The repo does not need a rewrite. It needs explicit seams, smaller modules, better contract definition, and process guardrails. The safest path is incremental extraction around existing deployable boundaries, starting with documentation, validation, and small seams in the largest modules.
