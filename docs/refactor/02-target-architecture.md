# Target Architecture

## Principle

Refactor around existing deployable surfaces first. Do not begin with a repo-wide move or a new build system. Introduce stable seams inside current directories, preserve runtime entrypoints, and migrate module-by-module.

Proxmox remains the first supported runtime provider, but it must no longer be treated as the permanent architecture anchor. New logic should depend on provider-neutral contracts first and on Proxmox-specific implementations only behind explicit provider modules.

## Provider Abstraction Layer

New cross-surface seams introduced incrementally:

- `core/provider/`
  - provider registry or contract definitions
  - runtime-neutral provider lookup
- `core/virtualization/`
  - generic host/node/VM access contracts
  - VM state/config lookup interfaces
- `core/platform/`
  - generic Beagle platform services such as inventory, provisioning catalog, installer preparation, USB actions, and policy operations
- `providers/proxmox/`
  - the current concrete implementation of virtualization/provider behavior for Proxmox

Initial contract set to stabilize:

- `listHosts()`
- `listNodes()`
- `listVms()`
- `getVmState(ctx)`
- `getVmConfig(ctx)`
- `getVmGuestInterfaces(ctx)`
- `selectedNodeName()`
- `fetchInventory()`
- `fetchProvisioningCatalog()`
- `createVm(payload)`
- `updateVm(vmid, payload)`
- `fetchVmProvisioningState(vmid)`
- `prepareInstallerTarget(vmid)`
- `attachUsb(vmid, busid)`
- `detachUsb(vmid, busid, port)`
- `createPolicy(payload)`
- `deletePolicy(name)`

## Target Modules

### 1. Beagle Host / Control Plane

Current root:

- `proxmox-host/`

Target internal modules:

- `http/`
  - request routing
  - auth guards
  - response helpers
- `inventory/`
  - VM listing
  - VM state synthesis
  - guest IP lookup
- `artifacts/`
  - installer metadata
  - public artifact manifest generation
  - checksum and download status helpers
- `provisioning/`
  - template rendering
  - Ubuntu guest provisioning helpers
  - enrollment token generation
- `integrations/`
  - Proxmox command wrappers
  - system interaction wrappers
- `config/`
  - env loading
  - defaults
  - path resolution

Public contracts to stabilize:

- `/api/v1/health`
- `/api/v1/public/vms/<vmid>/state`
- installer rendering endpoints
- generated VM profile payloads

### 2. Proxmox UI Integration

Current root:

- `proxmox-ui/`

Target internal modules:

- `api-client/`
- `state/`
- `components/`
- `provisioning/`
- `usb/`
- `utils/`

Rules:

- preserve current behavior and DOM integration
- keep the shipped runtime asset path stable while internals are extracted

### 3. Thin Client Runtime

Current root:

- `thin-client-assistant/runtime/`
- `thin-client-assistant/installer/`
- `thin-client-assistant/usb/`

Target internal modules:

- `config/`
  - config parsing
  - precedence rules
  - rendered env files
- `runtime/`
  - session orchestration
  - boot-mode selection
- `network/`
  - wired config application
  - identity and hostname application
- `pairing/`
  - Sunshine trust and pairing
- `moonlight-launch/`
  - launch preparation
  - app selection
  - session start

Rules:

- Moonlight path is critical and must remain stable through wrappers and smoke validation
- Bash may remain at the edges, but complex logic should migrate into smaller scripts or Python helpers where it materially improves safety

### 4. Gaming Kiosk

Current root:

- `beagle-kiosk/`

Target internal modules:

- `main-process/`
  - window lifecycle
  - child-process lifecycle
  - IPC registration
- `catalog/`
  - game loading
  - filtering
  - library reconciliation
- `config/`
  - config parsing
  - path resolution
  - defaults
- `gfn/`
  - launch plan resolution
  - process monitoring
  - session state
- `store-links/`
  - allowlist and validation

Rules:

- Kiosk remains the primary shell
- GeForce NOW remains a child process of the kiosk main process

### 5. Build / Packaging

Current root:

- `scripts/`

Target internal modules:

- `build/`
- `package/`
- `publish/`
- `validate/`
- `release/`

Responsibilities:

- isolate build orchestration by artifact family
- separate staging from publication
- formalize artifact metadata inputs and outputs

### 6. Shared Core

New target surface:

- `shared/` or equivalent internal library area introduced incrementally

Candidate shared contracts:

- endpoint profile schema
- artifact manifest schema
- URL/template resolution helpers
- token and auth header policy
- VM metadata parsing helpers

### 7. Provider Implementations

Current provider root:

- `providers/proxmox/`

Responsibilities:

- implement generic virtualization and inventory contracts for Proxmox
- isolate `/api2/json`, `PVE.*`, `qm`, `pvesh`, and Proxmox host assumptions behind explicit provider modules
- allow future providers to plug into the same contracts without rewriting business logic

## Dependency Rules

### Allowed direction

- business logic depends on `core/*` contracts and services
- provider-specific code depends on provider-neutral contracts, not the reverse
- UI surfaces depend on shared contracts, not on each other
- packaging depends on artifact builders, not the reverse
- host HTTP layer depends on services, not service code on HTTP request objects
- thin client runtime launchers depend on config/pairing helpers, not the reverse

### Avoid

- new direct calls to Proxmox APIs or commands from business logic outside `providers/proxmox/`
- direct coupling between website UI and Proxmox UI implementation details
- control plane modules importing UI concerns
- runtime launchers parsing installer templates directly
- packaging scripts duplicating artifact naming rules independently

## Migration Strategy

## Phase A: Establish seams

- create documentation, plan, risk register, progress tracking
- enforce required docs in repository validation
- remove process contradictions

## Phase B: Extract internals behind stable entrypoints

- keep current file names as runtime entrypoints
- move logic into nearby modules
- let entrypoints become thin composition layers
- route provider-specific operations through `core/*` services and `providers/proxmox/*`

Examples:

- `proxmox-ui/beagle-ui.js` becomes a bootstrap shell over extracted modules
- `proxmox-host/bin/beagle-control-plane.py` becomes a thin app entrypoint over internal services

## Phase C: Stabilize contracts

- define schemas for endpoint profiles, installer metadata, and public artifact manifests
- add validation for generated outputs

## Phase D: Increase verification

- add smoke tests around critical shell flows
- add behavior-level checks for generated URLs and manifests
- add focused regression checks for Moonlight launch path and kiosk GFN supervision

## Success Criteria

- smaller files with clear ownership
- explicit contracts for shared data
- critical runtime paths still behave identically
- documentation always reflects current state
- another agent can resume work in minutes without hidden context
