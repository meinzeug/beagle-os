# Target Architecture

## Principle

Refactor around existing deployable surfaces first. Do not begin with a repo-wide move or a new build system. Introduce stable seams inside current directories, preserve runtime entrypoints, and migrate module-by-module.

Proxmox remains the first supported runtime provider, but it must no longer be treated as the permanent architecture anchor. New logic should depend on provider-neutral contracts first and on Proxmox-specific implementations only behind explicit provider modules.

The long-term target is not merely "support more than one external provider". The long-term target is a first-party Beagle virtualization stack, with Proxmox and future third-party backends reduced to optional providers behind the same contracts. Provider-neutrality is therefore a migration strategy toward Beagle-owned virtualization, not the end state by itself.

The target install surface for new servers is a Beagle-owned bare-metal installer ISO with two explicit modes:

- `Beagle OS standalone`
- `Beagle OS with Proxmox`

Both modes must converge on the same generic Beagle host/control-plane architecture. Proxmox integration is an optional install branch, not the defining architecture.

## Provider Abstraction Layer

New cross-surface seams introduced incrementally:

- `core/provider/`
  - provider registry or contract definitions
  - runtime-neutral provider lookup
- `beagle-host/providers/`
  - host-side provider registry and provider contracts
  - runtime selection of the current host provider via environment/config instead of direct concrete imports
- `core/virtualization/`
  - generic host/node/VM access contracts
  - VM state/config lookup interfaces
- `core/platform/`
  - generic Beagle platform services such as inventory, provisioning catalog, installer preparation, USB actions, and policy operations
- `providers/proxmox/`
  - the current concrete implementation of virtualization/provider behavior for Proxmox
- `providers/beagle/`
  - future first-party Beagle virtualization/provider implementation behind the same contracts

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

## North Star

End state to optimize toward:

- Beagle can run its control plane, provisioning, inventory, fleet, installer, and endpoint-management flows without requiring Proxmox.
- Proxmox remains usable, but only as one provider implementation among several.
- A first-party Beagle virtualization provider and host runtime can plug into the same contracts already used by the UI, control plane, and installers.
- New architecture decisions should prefer seams that a future Beagle-owned provider can implement directly instead of seams that only mirror today's Proxmox behavior.

## Target Modules

### 0. First-Party Beagle Virtualization Stack

Working title:

- `beagalation`

Target internal modules:

- `providers/beagle/`
  - first-party provider implementation for Beagle-owned virtualization
- `core/virtualization/contracts/`
  - host, node, VM, storage, network, and lifecycle contracts shared by all providers
- `beagle-virtualization/host-runtime/`
  - host agent/runtime hooks for VM lifecycle, resource inventory, and control-plane integration
- `beagle-virtualization/compute/`
  - VM creation, update, start, stop, and console lifecycle orchestration
- `beagle-virtualization/network/`
  - bridges, endpoint connectivity, public stream exposure, and future provider-neutral network plumbing
- `beagle-virtualization/storage/`
  - image/ISO handling, disk lifecycle, and provisioning artifacts

Rules:

- do not block current refactor work on implementing the first-party provider immediately
- but cut today's seams so a first-party provider can be added without reworking every business flow again

### 0b. Beagle Server Installer Modes

Target install modes:

- `Beagle OS standalone`
  - installs Beagle host runtime and Beagle virtualization components directly on bare metal
  - no Proxmox packages, UI, or repositories required
- `Beagle OS with Proxmox`
  - installs Beagle host runtime plus the Proxmox provider/integration path
  - keeps today's compatibility path for operators who still want Proxmox underneath

Rules:

- both install modes must share one top-level installer flow and one host bootstrap contract
- provider selection must happen explicitly during install, not implicitly through package layout
- all post-install bootstrap logic must route through `beagle-host/providers/registry.py`

### 1. Beagle Host / Control Plane

Current root:

- `beagle-host/`

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

### 1b. Beagle Web Console / Host UI

Target root:

- `beagle-web/` or equivalent dedicated host UI surface introduced incrementally

Responsibilities:

- dashboard and host overview
- node, VM, storage, and network inventory views
- VM lifecycle actions and create/update flows
- fleet, provisioning, installer, and artifact workflows
- provider-neutral operator workflows against `beagle-host`

Rules:

- this is the long-term UI center
- `proxmox-ui/` remains transitionary integration only
- new durable browser-side business logic should target generic services reusable by the future Beagle Web Console first

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
- treat this as a compatibility surface, not the permanent host UI

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
- produce a standalone-capable server installer ISO plus the optional Proxmox-enabled variant from one coherent build flow

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
- make room for a future first-party Beagle provider to become the preferred or default implementation

Target provider set:

- `providers/beagle/`
  - preferred long-term provider for Beagle-owned virtualization and Beagle Web Console operation
- `providers/proxmox/`
  - optional compatibility provider

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
- `beagle-host/bin/beagle-control-plane.py` becomes a thin app entrypoint over internal services

## Phase C: Stabilize contracts

- define schemas for endpoint profiles, installer metadata, and public artifact manifests
- add validation for generated outputs

## Phase D: Increase verification

## Exit Criteria For The Architecture

The architecture is not "done" when Proxmox is only wrapped better. It is done when:

- Beagle business logic no longer requires direct Proxmox knowledge outside provider layers
- a first-party Beagle provider can be added behind the same contracts without restructuring the UI and control plane again
- Proxmox can be disabled or omitted in a deployment without collapsing the core Beagle management model
- fleet, provisioning, installer, and endpoint flows all run against provider-neutral contracts first

- add smoke tests around critical shell flows
- add behavior-level checks for generated URLs and manifests
- add focused regression checks for Moonlight launch path and kiosk GFN supervision

## Success Criteria

- smaller files with clear ownership
- explicit contracts for shared data
- critical runtime paths still behave identically
- documentation always reflects current state
- another agent can resume work in minutes without hidden context
