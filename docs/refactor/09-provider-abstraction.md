# Provider Abstraction Status

## Goal

Keep Beagle OS fully Proxmox-compatible now, but prevent Proxmox from remaining the permanent architecture center.

Long-term target:

- Beagle should gain its own first-party virtualization path/provider over time.
- Proxmox should remain supported, but only as one optional provider among several.
- The abstraction work in this file therefore exists to make Proxmox replaceable and to make a Beagle-owned provider possible.

## Target End State

- `providers/proxmox/` is one optional provider implementation.
- a future `providers/beagle/` implements the same contracts for a Beagle-owned virtualization path
- UI, control plane, provisioning, installer, fleet, and thin-client flows bind to provider-neutral services first
- disabling Proxmox must not invalidate the Beagle core architecture

## Proxmox Couplings Found

### Browser / UI

- `proxmox-ui/beagle-ui.js`
  - thin orchestration for Proxmox VM context detection, node selection from the Proxmox UI, and modal launch delegation
- `proxmox-ui/components/modal-shell.js`
  - provider-neutral modal shell for shared overlay CSS, overlay lifecycle helpers, loading-overlay rendering, and the fleet launcher DOM identifier used by the host-installed UI
- `extension/shared/vm-profile-mapper.js`
  - shared browser-side mapping from provider-backed VM data plus the host contract into browser-local profile objects
- `extension/shared/vm-profile-helpers.js`
  - shared browser-side endpoint-env export, operator notes, and action-state semantics for both browser surfaces
- `proxmox-ui/state/vm-profile.js`
  - thin Proxmox-UI wrapper around the shared browser-side profile mapper/helper seams
- `proxmox-ui/components/profile-modal.js`
  - provider-neutral profile modal renderer and action orchestration that consumes the shared browser-side profile helpers
- `proxmox-ui/components/fleet-modal.js`
  - provider-neutral fleet renderer and action orchestration
- `proxmox-ui/components/extjs-integration.js`
  - Proxmox ExtJS console/menu/toolbar/create-VM integration and the runtime `integrate()` loop
- `proxmox-ui/components/provisioning-result-modal.js`
  - provider-neutral provisioning result window and badge renderer
- `proxmox-ui/components/provisioning-create-modal.js`
  - provider-neutral Ubuntu Beagle create/edit modal orchestration
- `extension/providers/proxmox.js`
  - direct `/api2/json` cluster/config/guest-agent calls
  - Proxmox VM context detection for the browser extension
- `extension/services/profile.js`
  - thin extension-side wrapper around the shared browser-side profile mapper/helper seams
- `extension/components/profile-modal.js`
  - provider-neutral extension profile renderer and action orchestration
- `extension/components/vm-page-integration.js`
  - Proxmox-page toolbar/menu integration and mutation-observer boot logic for the extension
- `extension/content.js`
  - thin extension entrypoint for modal launch and overlay/profile-resolution orchestration; DOM boot logic moved to `extension/components/vm-page-integration.js`

### Host / control plane

- `beagle-host/`
  - canonical generic host/control-plane repo surface; no longer named after a single provider
- `beagle-host/bin/endpoint_profile_contract.py`
  - explicit public endpoint profile contract normalization for browser and installer consumers
- `beagle-host/services/virtualization_inventory.py`
  - provider-backed host read service for VM listing, node inventory, guest IPv4 lookup, VM config lookup, and bridge inventory used by the control plane
- `beagle-host/services/vm_state.py`
  - provider-backed host service for endpoint compliance evaluation and VM-state composition used by multiple control-plane handlers
- `beagle-host/services/vm_usb.py`
  - host-side USB attach/detach and tunnel-state service that composes provider-backed guest-exec calls, endpoint reports, and VM-secret tunnel metadata without leaving that orchestration in the HTTP entrypoint
- `beagle-host/services/ubuntu_beagle_provisioning.py`
  - host-side ubuntu-beagle provisioning/lifecycle service that composes provider-backed VM lifecycle operations, autoinstall artifact generation, provisioning state, and guest reconfiguration without leaving that orchestration in the HTTP entrypoint
- `beagle-host/services/sunshine_integration.py`
  - host-side Sunshine/Moonlight integration service that composes provider-backed guest execution, VM-secret credentials, profile/config lookup, access-ticket persistence, TLS pinned-pubkey retrieval, and authenticated Sunshine HTTP proxying without leaving that orchestration in the HTTP entrypoint
- `beagle-host/services/public_streams.py`
  - host-side public-stream mapping and port-allocation service that composes provider-backed VM/config lookup plus persistent mapping state without leaving that orchestration in the HTTP entrypoint
- `beagle-host/providers/proxmox_host_provider.py`
  - `pvesh get /cluster/resources`
  - `pvesh get /nodes`
  - `pvesh get /storage`
  - `pvesh get /nodes/{node}/qemu/{vmid}/config`
  - `qm guest cmd ... network-get-interfaces`
  - `qm create`, `qm set`, `qm start`, `qm stop`
  - `qm guest exec`, `qm guest exec-status`
- `beagle-host/bin/beagle-control-plane.py`
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

### `beagle-host/providers/host_provider_contract.py`

Generic contract:

- `next_vmid()`
- `list_storage_inventory()`
- `list_nodes()`
- `list_vms(...)`
- `get_vm_config(node, vmid, ...)`
- `create_vm(vmid, options, ...)`
- `set_vm_options(vmid, options, ...)`
- `delete_vm_options(vmid, option_names, ...)`
- `set_vm_description(vmid, description, ...)`
- `set_vm_boot_order(vmid, order, ...)`
- `start_vm(vmid, ...)`
- `stop_vm(vmid, ...)`
- `guest_exec_bash(vmid, command, ...)`
- `guest_exec_status(vmid, pid, ...)`
- `guest_exec_script_text(vmid, script, ...)`
- `schedule_vm_restart_after_stop(vmid, ...)`
- `get_guest_ipv4(vmid, ...)`

### `beagle-host/providers/registry.py`

Purpose:

- register, normalize, and instantiate host-provider implementations by kind

Current usage:

- boots the host-side `HOST_PROVIDER` from `BEAGLE_HOST_PROVIDER`
- currently registers Proxmox as the first concrete host provider and normalizes `pve` to `proxmox`

### `beagle-host/services/download_metadata.py`

Current host-side contract:

- `public_installer_iso_url()`
- `public_windows_installer_url()`
- `public_update_sha256sums_url()`
- `public_versioned_payload_url(version)`
- `public_versioned_bootstrap_url(version)`
- `public_payload_latest_download_url()`
- `public_bootstrap_latest_download_url()`
- `public_latest_payload_url()`
- `public_latest_bootstrap_url()`
- `checksum_for_dist_filename(filename)`
- `update_payload_metadata(version)`

### `beagle-host/services/vm_secret_bootstrap.py`

Current host-side contract:

- `default_usb_tunnel_port(vmid)`
- `generate_ssh_keypair(comment)`
- `usb_tunnel_known_host_line()`
- `usb_tunnel_user_info()`
- `usb_tunnel_home()`
- `usb_tunnel_auth_root()`
- `usb_tunnel_auth_dir()`
- `usb_tunnel_authorized_keys_path()`
- `usb_tunnel_authorized_key_line(vm, secret)`
- `sync_usb_tunnel_authorized_key(vm, secret)`
- `ensure_vm_sunshine_pinned_pubkey(vm, secret)`
- `ensure_vm_secret(vm)`

### `beagle-host/services/installer_prep.py`

Current host-side contract:

- `prep_dir()`
- `state_path(node, vmid)`
- `log_path(node, vmid)`
- `load_state(node, vmid)`
- `quick_sunshine_status(vmid)`
- `default_state(vm, sunshine_status=None)`
- `summarize_state(vm, state=None)`
- `is_running(state)`
- `start(vm)`

### `beagle-host/services/vm_usb.py`

Current host-side contract:

- `parse_usbip_port_output(output)`
- `parse_vhci_status_output(output)`
- `guest_usb_attachment_state(vmid)`
- `wait_for_guest_usb_attachment(vmid, busid, timeout_seconds=...)`
- `build_vm_usb_state(vm, report=None)`
- `attach_usb_to_guest(vm, busid)`
- `detach_usb_from_guest(vm, port=None, busid="")`

### `beagle-host/services/ubuntu_beagle_provisioning.py`

Current host-side contract:

- `build_provisioning_catalog()`
- `create_provisioned_vm(payload)`
- `storage_supports_content(storage_id, content_type)`
- `resolve_storage(preferred, content_type, fallback)`
- `ensure_ubuntu_beagle_iso_cached(iso_url)`
- `build_ubuntu_beagle_description(hostname, guest_user, public_stream=None, ...)`
- `build_ubuntu_beagle_seed_iso(...)`
- `finalize_ubuntu_beagle_install(state, restart=True)`
- `prepare_ubuntu_beagle_firstboot(state)`
- `create_ubuntu_beagle_vm(payload)`
- `update_ubuntu_beagle_vm(vmid, payload)`

### `beagle-host/services/sunshine_integration.py`

Current host-side contract:

- `fetch_https_pinned_pubkey(url)`
- `guest_exec_text(vmid, script)`
- `sunshine_guest_user(vm, config=None)`
- `register_moonlight_certificate_on_vm(vm, client_cert_pem, device_name=...)`
- `fetch_sunshine_server_identity(vm, guest_user)`
- `internal_sunshine_api_url(vm, profile=None)`
- `resolve_vm_sunshine_pinned_pubkey(vm)`
- `issue_sunshine_access_token(vm)`
- `resolve_ticket_vm(path)`
- `sunshine_proxy_ticket_url(token)`
- `proxy_sunshine_request(vm, request_path=..., query=..., method=..., body=..., request_headers=...)`

### `beagle-host/services/public_streams.py`

Current host-side contract:

- `public_streams_file()`
- `load_public_streams()`
- `save_public_streams(payload)`
- `public_stream_key(node, vmid)`
- `explicit_public_stream_base_port(config)`
- `used_public_stream_base_ports(mappings, exclude_key="", sync_mappings=False)`
- `allocate_public_stream_base_port(node, vmid)`

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
- `extension/shared/vm-profile-mapper.js`
- `extension/shared/vm-profile-helpers.js`
- `extension/services/profile.js`
- `extension/components/profile-modal.js`
- `extension/components/vm-page-integration.js`
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
- `resolveVmProfile(ctx)`

### Host-side provider seam

Current concrete implementation:

- `beagle-host/`
- `beagle-host/providers/proxmox_host_provider.py`
- `beagle-host/services/virtualization_inventory.py`
- `beagle-host/services/vm_state.py`

### Host-side endpoint profile contract

Current concrete implementation:

- `beagle-host/bin/endpoint_profile_contract.py`

Current contract characteristics:

- normalized browser-/installer-facing endpoint profile payload
- explicit `contract_version` field, currently `v1`
- normalized installer artifact URLs and installer-target fields
- normalized assignment/policy/profile list fields so consumers can rely on stable key presence

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
- host-side read-service wrappers:
  - `first_guest_ipv4(vmid)`
  - `list_vms(refresh=False)`
  - `list_nodes_inventory()`
  - `get_vm_config(node, vmid)`
  - `find_vm(vmid, refresh=False)`
  - `config_bridge_names(config)`
  - `list_bridge_inventory(node="")`
- host-side state-service wrappers:
  - `evaluate_endpoint_compliance(profile, report)`
  - `build_vm_state(vm)`

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
- shared modal CSS/loading-overlay rendering through `proxmox-ui/components/modal-shell.js`
- VM profile resolution through `proxmox-ui/state/vm-profile.js`, with `beagle-ui.js` reduced to thin orchestration/bootstrap wrappers
- Proxmox ExtJS toolbar/menu/create-VM/fleet runtime wiring through `proxmox-ui/components/extjs-integration.js`, with `beagle-ui.js` no longer owning that large block directly
- shared browser-side VM profile mapping through `extension/shared/vm-profile-mapper.js`
- shared browser-side endpoint-env/note/action-state semantics through `extension/shared/vm-profile-helpers.js`

### Browser extension

These flows now go through provider-backed services first:

- Proxmox VM context detection from the current page
- VM config, cluster resource, and guest-agent interface reads
- hosted installer URL, ISO URL, and Web UI URL resolution
- public VM state, installer-target eligibility, installer-prep, and Sunshine access lookups
- shared Beagle API token/config resolution through `extension/common.js` and `extension/services/platform.js`
- VM profile resolution through `extension/services/profile.js`, with `extension/content.js` reduced to rendering and DOM integration
- profile rendering and action handling through `extension/components/profile-modal.js`
- Proxmox-page toolbar/menu DOM integration through `extension/components/vm-page-integration.js`

### Host-side control plane

These flows now go through provider-backed services first:

- host bootstrap and host-provider selection through `beagle-host/providers/registry.py` and `beagle-host/providers/host_provider_contract.py`
- VM listing, node listing, guest IPv4 lookup, VM config lookup, and bridge inventory through `beagle-host/services/virtualization_inventory.py`
- endpoint compliance evaluation and VM-state composition through `beagle-host/services/vm_state.py`
- VM profile synthesis, assignment resolution, policy matching, public-stream derivation, and VM fingerprint assessment through `beagle-host/services/vm_profile.py`
- public download/artifact URL, latest-download resolution, checksum lookup, and update-payload metadata shaping through `beagle-host/services/download_metadata.py`
- VM-secret credential/bootstrap orchestration, Sunshine pinned-pubkey backfill, and USB-tunnel `authorized_keys` synchronization through `beagle-host/services/vm_secret_bootstrap.py`
- installer-prep state loading, Sunshine-readiness probing, default/summary shaping, and background prep-script launch through `beagle-host/services/installer_prep.py`
- guest USB attach/detach orchestration, usbip/vhci parsing, and tunnel-state shaping through `beagle-host/services/vm_usb.py`
- ubuntu-beagle provisioning catalog assembly, ISO/seed artifact generation, VM create/update/finalize flows, and firstboot restart orchestration through `beagle-host/services/ubuntu_beagle_provisioning.py`
- Sunshine pinned-pubkey retrieval, Moonlight certificate registration, Sunshine server identity discovery, access-ticket issuance/resolution, and Sunshine HTTP proxying through `beagle-host/services/sunshine_integration.py`
- public-stream mapping persistence, explicit-port sync, stale-entry cleanup, and next-free base-port allocation through `beagle-host/services/public_streams.py`
- VM lifecycle writes, guest-exec flows, delayed restart scheduling, storage inventory, and next-VMID allocation through the selected host provider, currently `beagle-host/providers/proxmox_host_provider.py`
- browser-/installer-facing endpoint profile payload normalization through `beagle-host/bin/endpoint_profile_contract.py`

## Still Directly Coupled

### Browser extension

- `extension/components/vm-page-integration.js` still depends on today's Proxmox ExtJS DOM structure, menu labels, and selectors, even though direct Proxmox API access and VM profile synthesis are no longer coupled to that module.

### Proxmox UI runtime coupling

- `proxmox-ui/components/extjs-integration.js` still depends on today's Proxmox ExtJS component queries, menu structure, toolbar layout, and localized create-VM labels, even though the business logic behind those actions no longer lives in the same file.

### Control plane

- `beagle-host/bin/beagle-control-plane.py` no longer owns the main VM profile/assignment/public-stream synthesis block directly, but it remains a large monolith with response-model shaping, inventory aggregation, and other handler-local orchestration still living in the entrypoint. Those remaining flows should move behind `beagle-host/services/*` incrementally.
- `beagle-host/services/vm_profile.py` is now the host-side seam for profile synthesis, but it still derives business state from today's Proxmox-backed metadata/config semantics through provider-backed reads and existing description-meta conventions.
- `beagle-host/providers/registry.py` makes provider selection real at bootstrap time, but the registry still only exposes one concrete implementation today. Provider selection is no longer hard-coded in the control-plane import graph, yet provider diversity is still unfinished work.
- `beagle-host/services/ubuntu_beagle_provisioning.py` removed the ubuntu-beagle lifecycle block from the entrypoint, but it still uses today's Proxmox-shaped VM option semantics and `scripts/configure-sunshine-guest.sh --proxmox-host localhost` path under the new service seam.
- `beagle-host/services/sunshine_integration.py` removed the Sunshine/Moonlight block from the entrypoint, but it still depends on Sunshine-specific guest file paths/state layout, Sunshine HTTP/API semantics, `curl`/`openssl` behavior, and current Moonlight certificate-registration conventions under the new service seam.
- `beagle-host/services/public_streams.py` removed port-state/orchestration from the entrypoint, but it still interprets today's description-meta keys (`beagle-public-moonlight-port`) and VM inventory/config semantics through provider-backed reads under the new service seam.

### Script surfaces

- several scripts still execute `qm`/`pvesh` directly and should move to reusable provider helpers incrementally.

### Thin-client Proxmox access

- thin-client-side Proxmox API and SPICE helpers are still explicitly Proxmox-bound.

## Exit Criteria Before Proxmox Becomes Optional

Proxmox should not be considered optional until all of the following are true:

- host-side business logic no longer requires direct Proxmox knowledge outside provider/service layers
- thin-client and installer flows no longer assume Proxmox-specific APIs or SPICE behavior by default
- script and deployment surfaces do not assume Proxmox package/layout semantics as the only supported path
- a second provider or a conformance-grade mock proves the contracts are not merely Proxmox-shaped wrappers
- the future Beagle-owned provider path has a defined contract target and module layout

## Migration Rule

From this point onward:

- new business logic should bind to `core/*` contracts first
- new Proxmox specifics should land in `providers/proxmox/`
- any remaining direct coupling must be documented before expanding it
- this file is part of the mandatory multi-agent handoff set and must stay current after provider-related changes
