# Provider Abstraction Status

## Goal

Keep Beagle OS fully Proxmox-compatible now, but prevent Proxmox from remaining the permanent architecture center.

## Proxmox Couplings Found

### Browser / UI

- `proxmox-ui/beagle-ui.js`
  - Proxmox VM context detection
  - `/api2/json` VM config and guest-agent reads
  - node selection from the Proxmox UI
- `proxmox-ui/components/profile-modal.js`
  - provider-neutral profile modal renderer and action orchestration
- `proxmox-ui/components/fleet-modal.js`
  - provider-neutral fleet renderer and action orchestration
- `proxmox-ui/components/provisioning-result-modal.js`
  - provider-neutral provisioning result window and badge renderer
- `proxmox-ui/components/provisioning-create-modal.js`
  - provider-neutral Ubuntu Beagle create/edit modal orchestration
- `extension/providers/proxmox.js`
  - direct `/api2/json` cluster/config/guest-agent calls
  - Proxmox VM context detection for the browser extension
- `extension/content.js`
  - duplicated VM profile synthesis logic and modal/UI orchestration still live here, but direct Proxmox reads were removed

### Host / control plane

- `proxmox-host/providers/proxmox_host_provider.py`
  - `pvesh get /cluster/resources`
  - `pvesh get /nodes`
  - `pvesh get /storage`
  - `pvesh get /nodes/{node}/qemu/{vmid}/config`
  - `qm guest cmd ... network-get-interfaces`
  - `qm create`, `qm set`, `qm start`, `qm stop`
  - `qm guest exec`, `qm guest exec-status`
- `proxmox-host/bin/beagle-control-plane.py`
  - VM profile synthesis from Proxmox metadata

### Scripts / provisioning / artifacts

- `scripts/reconcile-public-streams.sh`
- `scripts/prepare-host-downloads.sh`
- `scripts/configure-sunshine-guest.sh`
- `scripts/install-proxmox-host.sh`
- `scripts/install-proxmox-ui-integration.sh`
- `server-installer/.../beagle-server-installer`

Coupling forms:

- `/api2/json`
- `PVE.*`
- `qm`
- `pvesh`
- Proxmox package/repository assumptions

### Thin client

- `thin-client-assistant/usb/pve-thin-client-proxmox-api.py`
- `thin-client-assistant/runtime/connect-proxmox-spice.sh`

## Interfaces Introduced

### `core/provider/registry.js`

Purpose:

- register and resolve provider implementations by role

Current usage:

- registers the virtualization provider role

### `core/virtualization/service.js`

Generic contract:

- `listHosts()`
- `listNodes()`
- `listVms()`
- `getVmState(ctx)`
- `getVmConfig(ctx)`
- `getVmGuestInterfaces(ctx)`
- `selectedNodeName()`

### `core/platform/service.js`

Generic contract:

- `fetchHealth()`
- `fetchInventory()`
- `fetchPolicies()`
- `fetchProvisioningCatalog()`
- `createVm(payload)`
- `updateVm(vmid, payload)`
- `fetchVmProvisioningState(vmid)`
- `fetchPublicVmState(vmid)`
- `fetchInstallerTargetEligibility(ctx)`
- `fetchInstallerPreparation(vmid)`
- `prepareInstallerTarget(vmid)`
- `fetchVmCredentials(vmid)`
- `createSunshineAccess(vmid)`
- `fetchVmUsbState(vmid)`
- `refreshVmUsb(vmid)`
- `attachUsb(vmid, busid)`
- `detachUsb(vmid, busid, port)`
- `queueVmAction(vmid, action)`
- `queueBulkAction(vmids, action)`
- `createPolicy(payload)`
- `deletePolicy(name)`

### `providers/proxmox/virtualization-provider.js`

Current concrete implementation:

- Proxmox browser-side virtualization provider
- encapsulates `/api2/json` and `PVE.ResourceStore` access for the UI

### Browser extension provider seam

Current concrete implementation:

- `extension/provider-registry.js`
- `extension/services/virtualization.js`
- `extension/services/platform.js`
- `extension/providers/proxmox.js`

Generic contract now exposed to `extension/content.js`:

- `isVmView()`
- `parseVmContext()`
- `listHosts()`
- `listNodes()`
- `listVms()`
- `getVmState(ctx)`
- `getVmConfig(ctx)`
- `getVmGuestInterfaces(ctx)`
- `resolveUsbInstallerUrl(ctx)`
- `resolveInstallerIsoUrl(ctx)`
- `resolveControlPlaneHealthUrl()`
- `resolveWebUiUrl()`
- `resolveBeagleApiUrl(path)`
- `fetchPublicVmState(vmid)`
- `fetchInstallerTargetEligibility(ctx)`
- `fetchInstallerPreparation(vmid)`
- `prepareInstallerTarget(vmid)`
- `createSunshineAccess(vmid)`

### Host-side provider seam

Current concrete implementation:

- `proxmox-host/providers/proxmox_host_provider.py`

Current contract extracted from the control plane:

- `next_vmid()`
- `list_storage_inventory()`
- `list_nodes()`
- `list_vms()`
- `get_vm_config(node, vmid)`
- `get_guest_ipv4(vmid)`
- `create_vm(vmid, options)`
- `set_vm_options(vmid, options)`
- `delete_vm_options(vmid, option_names)`
- `set_vm_description(vmid, description)`
- `set_vm_boot_order(vmid, order)`
- `start_vm(vmid)`
- `stop_vm(vmid, skiplock=False)`
- `guest_exec_bash(vmid, command, timeout_seconds=None, request_timeout=None)`
- `guest_exec_status(vmid, pid, timeout=None)`
- `guest_exec_script_text(vmid, script, poll_attempts=300, poll_interval_seconds=2.0)`
- `schedule_vm_restart_after_stop(vmid, wait_timeout_seconds)`

## Already Decoupled

### Browser-side Proxmox UI

These flows now go through generic services first:

- selected node resolution in `proxmox-ui/beagle-ui.js`
- provisioning catalog fallback node loading
- fleet health/inventory/policy loading
- VM config/resource/guest-agent access for profile resolution
- installer target eligibility lookup in `proxmox-ui/state/installer-eligibility.js`
- installer-prep, USB attach/detach/refresh, Sunshine access, and policy/action queue calls through `core/platform/service.js`
- profile modal rendering and action handling through `proxmox-ui/components/profile-modal.js`
- fleet rendering and action handling through `proxmox-ui/components/fleet-modal.js`
- provisioning result window, badge, and status rendering through `proxmox-ui/components/provisioning-result-modal.js`
- Ubuntu Beagle create/edit modal orchestration through `proxmox-ui/components/provisioning-create-modal.js`

### Browser extension

These flows now go through provider-backed services first:

- Proxmox VM context detection from the current page
- VM config, cluster resource, and guest-agent interface reads
- hosted installer URL, ISO URL, and Web UI URL resolution
- public VM state, installer-target eligibility, installer-prep, and Sunshine access lookups
- shared Beagle API token/config resolution through `extension/common.js` and `extension/services/platform.js`

## Still Directly Coupled

### Browser extension

- `extension/content.js` still performs local profile synthesis, modal rendering, and action orchestration, but it no longer performs direct Proxmox API calls.

### Control plane

- `proxmox-host/bin/beagle-control-plane.py` still synthesizes VM profiles from Proxmox metadata and remains a large monolith, but its VM reads, writes, guest-exec flows, and scheduled restart helper are now routed through `ProxmoxHostProvider`.

### Script surfaces

- several scripts still execute `qm`/`pvesh` directly and should move to reusable provider helpers incrementally.

### Thin-client Proxmox access

- thin-client-side Proxmox API and SPICE helpers are still explicitly Proxmox-bound.

## Migration Rule

From this point onward:

- new business logic should bind to `core/*` contracts first
- new Proxmox specifics should land in `providers/proxmox/`
- any remaining direct coupling must be documented before expanding it
- this file is part of the mandatory multi-agent handoff set and must stay current after provider-related changes
