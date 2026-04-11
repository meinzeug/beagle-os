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

- `core/platform/browser-common.js`
  - shared browser-side token storage, template, URL, and Beagle-API helper seam used by the Proxmox UI, extension, and website surfaces
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
- `proxmox-ui/state/fleet.js`
  - provider-neutral fleet data loader for health/inventory/policies/catalog payload assembly used by the host-installed UI
- `proxmox-ui/components/profile-modal.js`
  - provider-neutral profile modal renderer and action orchestration that consumes the shared browser-side profile helpers
- `proxmox-ui/components/fleet-modal.js`
  - provider-neutral fleet renderer and action orchestration
- `proxmox-ui/provisioning/flow.js`
  - provider-neutral provisioning flow orchestrator for catalog/state fetches plus create/result modal wiring
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
- `beagle-host/services/thin_client_preset.py`
  - shared thin-client preset base-field contract used by both the host installer builder and the USB Proxmox preset builder
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
- `beagle-host/services/policy_normalization.py`
  - host-side policy contract normalization service that shapes selector/profile payloads without leaving that contract logic in the HTTP entrypoint
- `beagle-host/services/runtime_environment.py`
  - host-side runtime environment service for public-stream host resolution and manager pinned-pubkey derivation used by multiple other host services
- `beagle-host/services/endpoint_enrollment.py`
  - host-side endpoint enrollment/bootstrap service for installer enrollment-token issuance and endpoint bootstrap/config response shaping
- `beagle-host/services/ubuntu_beagle_restart.py`
  - host-side ubuntu-beagle restart orchestration service for scheduled restart state reuse and cancellation
- `beagle-host/services/runtime_support.py`
  - host-side runtime support service for in-memory cache and shell-environment parsing used by provider bootstrap and host helpers
- `beagle-host/services/runtime_exec.py`
  - host-side runtime execution service for shared subprocess JSON/text/checked command wrappers used by provider bootstrap and host helpers
- `beagle-host/services/time_support.py`
  - host-side time support service for shared UTC timestamp generation, parsing, and age calculation used by multiple extracted host services
- `beagle-host/services/runtime_paths.py`
  - host-side runtime path service for resolved data-root selection and managed directory creation used by multiple extracted host services
- `beagle-host/services/metadata_support.py`
  - host-side metadata support service for shared VM description-meta parsing and normalized hostname derivation used by multiple extracted host services
- `beagle-host/services/persistence_support.py`
  - host-side persistence support service for shared JSON/file loading and writing used by multiple extracted host services
- `beagle-host/services/request_support.py`
  - host-side request support service for bearer-token parsing, origin normalization, and computed CORS-origin policy used by the HTTP handlers
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

- `scripts/lib/beagle_provider.py`
  - provider-facing script helper for VM inventory, VM config, and guest-interface reads
- `scripts/lib/provider_shell.sh`
  - shared shell-side provider bootstrap for local-vs-remote host dispatch, provider-helper discovery, remote helper execution, and raw JSON payload extraction
- `scripts/reconcile-public-streams.sh`
- `scripts/prepare-host-downloads.sh`
- `scripts/configure-sunshine-guest.sh`
- `scripts/install-proxmox-host.sh`
- `scripts/install-beagle-proxy.sh`
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

### `core/platform/browser-common.js`

Current browser-side contract:

- `createSessionTokenStore(storageKey)`
- `fillTemplate(template, values)`
- `withNoCache(url)`
- `managerUrlFromHealthUrl(healthUrl)`
- `normalizeBeagleApiPath(path)`
- `joinBaseAndPath(base, path)`
- `appendHashToken(url, token, hashKey="beagle_token")`

### `scripts/lib/beagle_provider.py`

Current script-side contract:

- `provider_kind()`
- `list_vms()`
- `vm_config(node, vmid)`
- `guest_interfaces(vmid)`
- `parse_description_meta(description)`
- `find_vm_record(vmid)`
- `vm_node(vmid)`
- `vm_description_text(node, vmid)`
- `vm_description_text_for_vmid(vmid)`
- `vm_description_meta(node, vmid)`
- `vm_description_meta_for_vmid(vmid)`
- `first_guest_ipv4(vmid)`
- `guest_exec_bash(vmid, command, timeout_seconds=None)`
- `guest_exec_status(vmid, pid)`
- `set_vm_options(vmid, option_pairs)`
- `set_vm_description(vmid, description)`
- `reboot_vm(vmid)`

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

### `beagle-host/services/time_support.py`

Current host-side contract:

- `utcnow()`
- `parse_utc_timestamp(value)`
- `timestamp_age_seconds(value)`

### `beagle-host/services/runtime_paths.py`

Current host-side contract:

- `ensure_data_dir()`
- `data_dir()`
- `endpoints_dir()`
- `actions_dir()`
- `support_bundles_dir()`
- `policies_dir()`

### `beagle-host/services/persistence_support.py`

Current host-side contract:

- `load_json_file(path, fallback)`
- `write_json_file(path, payload, mode=...)`

### `beagle-host/services/request_support.py`

Current host-side contract:

- `extract_bearer_token(header_value)`
- `normalized_origin(value)`
- `cors_allowed_origins()`

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

### `beagle-host/services/policy_normalization.py`

Current host-side contract:

- `normalize_payload(payload, policy_name=None)`

### `beagle-host/services/support_bundle_store.py`

Current host-side contract:

- `metadata_path(bundle_id)`
- `archive_path(bundle_id, filename)`
- `find_metadata(bundle_id)`
- `list_metadata(node=None, vmid=None)`
- `store(node, vmid, action_id, filename, content)`

### `beagle-host/services/installer_template_patch.py`

Current host-side contract:

- `patch_installer_defaults(script_text, preset_name, preset_b64, installer_iso_url, installer_bootstrap_url, installer_payload_url, writer_variant)`
- `patch_windows_installer_defaults(script_text, preset_name, preset_b64, installer_iso_url)`

### `beagle-host/services/ubuntu_beagle_inputs.py`

Current host-side contract:

- `validate_linux_username(value, field_name)`
- `validate_password(value, field_name, allow_empty=False)`
- `normalize_locale(value)`
- `normalize_keymap(value)`
- `normalize_package_names(value, field_name=...)`
- `resolve_ubuntu_beagle_desktop(value)`
- `normalize_package_presets(value)`
- `expand_software_packages(package_presets, extra_packages)`

### `beagle-host/services/action_queue.py`

Current host-side contract:

- `queue_path(node, vmid)`
- `result_path(node, vmid)`
- `load_queue(node, vmid)`
- `save_queue(node, vmid, queue)`
- `queue_action(vm, action_name, requested_by, params=None)`
- `queue_bulk_actions(vmids, action_name, requested_by)`
- `dequeue_actions(node, vmid)`
- `load_result(node, vmid)`
- `wait_for_result(node, vmid, action_id, timeout_seconds=...)`
- `store_result(node, vmid, payload)`
- `summarize_result(payload)`

### `beagle-host/services/endpoint_enrollment.py`

Current host-side contract:

- `issue_enrollment_token(vm)`
- `enroll_endpoint(payload)`

### `beagle-host/services/runtime_environment.py`

Current host-side contract:

- `resolve_public_stream_host(host)`
- `current_public_stream_host()`
- `manager_pinned_pubkey()`

### `beagle-host/services/ubuntu_beagle_restart.py`

Current host-side contract:

- `schedule(vmid, wait_timeout_seconds=...)`
- `ensure_restart_state(state, vmid)`
- `restart_running(restart_state)`
- `cancel(state)`

### `beagle-host/services/runtime_support.py`

Current host-side contract:

- `cache_get(key, ttl_seconds)`
- `cache_put(key, value)`
- `cache_invalidate(*keys)`
- `load_shell_env_file(path)`

### `beagle-host/services/runtime_exec.py`

Current host-side contract:

- `run_json(command, timeout=...)`
- `run_text(command, timeout=...)`
- `run_checked(command, timeout=...)`

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

- shared session-token, URL-template, cache-busting, manager-URL, Beagle-API path, and hash-token helper semantics through `core/platform/browser-common.js`
- selected node resolution in `proxmox-ui/beagle-ui.js`
- provisioning catalog fallback node loading
- fleet health/inventory/policy loading
- VM config/resource/guest-agent access for profile resolution
- installer target eligibility lookup in `proxmox-ui/state/installer-eligibility.js`
- fleet payload loading through `proxmox-ui/state/fleet.js`
- installer-prep, USB attach/detach/refresh, Sunshine access, and policy/action queue calls through `core/platform/service.js`
- profile modal rendering and action handling through `proxmox-ui/components/profile-modal.js`
- fleet rendering and action handling through `proxmox-ui/components/fleet-modal.js`
- provisioning result window, badge, and status rendering through `proxmox-ui/components/provisioning-result-modal.js`
- Ubuntu Beagle create/edit modal orchestration through `proxmox-ui/components/provisioning-create-modal.js`
- provisioning catalog/state fetch and modal wiring through `proxmox-ui/provisioning/flow.js`
- shared modal CSS/loading-overlay rendering through `proxmox-ui/components/modal-shell.js`
- VM profile resolution through `proxmox-ui/state/vm-profile.js`, with `beagle-ui.js` reduced to thin orchestration/bootstrap wrappers
- Proxmox ExtJS toolbar/menu/create-VM/fleet runtime wiring through `proxmox-ui/components/extjs-integration.js`, with `beagle-ui.js` no longer owning that large block directly
- shared browser-side VM profile mapping through `extension/shared/vm-profile-mapper.js`
- shared browser-side endpoint-env/note/action-state semantics through `extension/shared/vm-profile-helpers.js`

### Browser extension

These flows now go through provider-backed services first:

- shared session-token, URL-template, cache-busting, manager-URL, Beagle-API path, and hash-token helper semantics through `core/platform/browser-common.js`
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
- host-provider registry resolution now lazy-loads provider modules instead of directly importing one concrete provider at registry import time
- VM listing, node listing, guest IPv4 lookup, VM config lookup, and bridge inventory through `beagle-host/services/virtualization_inventory.py`
- endpoint compliance evaluation and VM-state composition through `beagle-host/services/vm_state.py`
- VM profile synthesis, assignment resolution, policy matching, public-stream derivation, and VM fingerprint assessment through `beagle-host/services/vm_profile.py`
- VM detail/download HTTP route matching plus response-envelope/payload shaping for `/api/v1/vms/...` through `beagle-host/services/vm_http_surface.py`
- non-VM read-route matching plus response-envelope/payload shaping for provisioning catalog/state, endpoint list, policy reads, and support-bundle downloads through `beagle-host/services/control_plane_read_surface.py`
- public VM state/endpoint route matching plus endpoint-authenticated update-feed shaping through `beagle-host/services/public_http_surface.py`
- public ubuntu-install lifecycle POST route matching and state-transition payload shaping through `beagle-host/services/public_ubuntu_install_surface.py`
- endpoint-authenticated Moonlight registration, action pull/result, and support-bundle-upload POST route matching through `beagle-host/services/endpoint_http_surface.py`
- public Sunshine GET/POST proxy dispatch and ticket-based response shaping through `beagle-host/services/public_sunshine_surface.py`
- authenticated single-VM mutation POST route matching for installer-prep, updates, VM actions, USB attach/detach, and Sunshine access through `beagle-host/services/vm_mutation_surface.py`
- authenticated non-VM admin mutation route matching for policies, bulk actions, ubuntu-beagle create, provisioning create, and provisioning update through `beagle-host/services/admin_http_surface.py`
- endpoint enrollment and endpoint check-in route matching plus endpoint-report persistence handoff through `beagle-host/services/endpoint_lifecycle_surface.py` and the expanded `beagle-host/services/endpoint_report.py`
- public download/artifact URL, latest-download resolution, checksum lookup, and update-payload metadata shaping through `beagle-host/services/download_metadata.py`
- VM-secret credential/bootstrap orchestration, Sunshine pinned-pubkey backfill, and USB-tunnel `authorized_keys` synchronization through `beagle-host/services/vm_secret_bootstrap.py`
- installer-prep state loading, Sunshine-readiness probing, default/summary shaping, and background prep-script launch through `beagle-host/services/installer_prep.py`
- guest USB attach/detach orchestration, usbip/vhci parsing, and tunnel-state shaping through `beagle-host/services/vm_usb.py`
- ubuntu-beagle provisioning catalog assembly, ISO/seed artifact generation, VM create/update/finalize flows, and firstboot restart orchestration through `beagle-host/services/ubuntu_beagle_provisioning.py`
- Sunshine pinned-pubkey retrieval, Moonlight certificate registration, Sunshine server identity discovery, access-ticket issuance/resolution, and Sunshine HTTP proxying through `beagle-host/services/sunshine_integration.py`
- public-stream mapping persistence, explicit-port sync, stale-entry cleanup, and next-free base-port allocation through `beagle-host/services/public_streams.py`
- policy selector/profile/default normalization through `beagle-host/services/policy_normalization.py`
- runtime host resolution and manager pinned-pubkey derivation through `beagle-host/services/runtime_environment.py`
- installer enrollment-token issuance and endpoint bootstrap/config payload shaping through `beagle-host/services/endpoint_enrollment.py`
- ubuntu-beagle scheduled restart state reuse, scheduling, and cancellation through `beagle-host/services/ubuntu_beagle_restart.py`
- shared in-memory cache semantics and shell-env parsing through `beagle-host/services/runtime_support.py`
- shared subprocess JSON/text/checked command execution through `beagle-host/services/runtime_exec.py`
- shared UTC timestamp generation/parsing/age semantics through `beagle-host/services/time_support.py`
- shared data-root selection and managed-directory creation through `beagle-host/services/runtime_paths.py`, with the service composition path no longer depending on the old `EFFECTIVE_DATA_DIR` global
- shared VM description-meta parsing and normalized hostname derivation through `beagle-host/services/metadata_support.py`
- shared JSON/file persistence through `beagle-host/services/persistence_support.py`
- shared bearer-token parsing, origin normalization, and computed CORS-origin policy through `beagle-host/services/request_support.py`
- support-bundle archive persistence, metadata shaping, and filtered metadata lookup through `beagle-host/services/support_bundle_store.py`
- installer shell/Windows template patching through `beagle-host/services/installer_template_patch.py`, with preset Base64 encoding now living inside `beagle-host/services/installer_script.py`
- ubuntu-beagle user/password/locale/keymap validation plus desktop/package preset normalization through `beagle-host/services/ubuntu_beagle_inputs.py`
- action queue orchestration, bulk dedupe, dequeue behavior, and action-result waiting through the expanded `beagle-host/services/action_queue.py`
- VM lifecycle writes, guest-exec flows, delayed restart scheduling, storage inventory, and next-VMID allocation through the selected host provider, currently `beagle-host/providers/proxmox_host_provider.py`
- browser-/installer-facing endpoint profile payload normalization through `beagle-host/bin/endpoint_profile_contract.py`

### Script / installer surfaces

These flows now go through a provider-facing helper seam first:

- VM inventory/config/guest-interface reads in `scripts/reconcile-public-streams.sh`
- shared description-meta parsing plus VM inventory/config reads in `scripts/prepare-host-downloads.sh`
- hosted installer/live-USB/Windows template patching plus VM installer catalog/status shaping through `scripts/lib/prepare_host_downloads.py`, with overlapping installer/profile URL fields normalized through `beagle-host/bin/endpoint_profile_contract.py`
- VM description metadata reads, guest-interface reads, and the Sunshine guest-status exec probe in `scripts/ensure-vm-stream-ready.sh`
- backend VM enumeration, description metadata reads, and guest-interface reads in `scripts/install-beagle-proxy.sh`
- preferred remote guest-IPv4/current-description reads plus guest-exec/status, description updates, and reboot flows in `scripts/configure-sunshine-guest.sh`, with direct `qm` fallbacks retained for not-yet-updated hosts
- synchronous guest-exec polling through `scripts/lib/beagle_provider.py` in both `scripts/configure-sunshine-guest.sh` and `scripts/ensure-vm-stream-ready.sh`, with direct `qm` fallbacks retained only as compatibility branches
- shared provider-helper bootstrap and remote/local execution through `scripts/lib/provider_shell.sh` in `scripts/configure-sunshine-guest.sh`, `scripts/ensure-vm-stream-ready.sh`, and `scripts/optimize-proxmox-vm-for-beagle.sh`
- preferred VM baseline option writes in `scripts/optimize-proxmox-vm-for-beagle.sh`, with direct `qm set` fallback retained for not-yet-updated hosts
- shared script-side virtualization reads through `scripts/lib/beagle_provider.py`
- shared thin-client preset base fields and streaming-mode input shaping through `beagle-host/services/thin_client_preset.py` in both `beagle-host/services/installer_script.py` and `thin-client-assistant/usb/proxmox_preset.py`

## Still Directly Coupled

### Browser extension

- `extension/components/vm-page-integration.js` still depends on today's Proxmox ExtJS DOM structure, menu labels, and selectors, even though direct Proxmox API access and VM profile synthesis are no longer coupled to that module.

### Proxmox UI runtime coupling

- `proxmox-ui/components/extjs-integration.js` still depends on today's Proxmox ExtJS component queries, menu structure, toolbar layout, and localized create-VM labels, even though the business logic behind those actions no longer lives in the same file.
- `proxmox-ui/beagle-ui.js` is now mostly orchestration, but selected-node detection still depends on the active Proxmox virtualization provider/runtime and the remaining boot path still assumes the Proxmox host-installed UI surface.
- `proxmox-ui/beagle-ui-common.js` no longer owns duplicated generic browser helpers, but it still carries Proxmox-UI-specific runtime config defaults and API-token prompt semantics for the host-installed UI surface.

### Control plane

- `beagle-host/bin/beagle-control-plane.py` no longer owns the main VM profile/assignment/public-stream synthesis block directly, no longer owns the `/api/v1/vms/...` GET response surface inline, no longer owns the next non-VM provisioning/policy/support-bundle read surface inline, no longer owns the public VM state/endpoint plus endpoint-authenticated update-feed surface inline, no longer owns the public ubuntu-install lifecycle POST surface inline, no longer owns the endpoint-authenticated Moonlight/action/result/support-bundle-upload POST surface inline, no longer owns the public Sunshine proxy flow inline, no longer owns the authenticated single-VM mutation POST surface inline, no longer owns the remaining authenticated non-VM admin mutation routes inline, and no longer owns the endpoint enrollment/check-in lifecycle routes inline. It remains a monolith because business/orchestration helpers and provider/deploy/runtime assumptions still live there, but the next host refactor target is now those non-HTTP seams rather than another large HTTP route block.
- `beagle-host/services/vm_profile.py` is now the host-side seam for profile synthesis, but it still derives business state from today's Proxmox-backed metadata/config semantics through provider-backed reads and existing description-meta conventions.
- `beagle-host/providers/registry.py` makes provider selection real at bootstrap time, but the registry still only exposes one concrete implementation today. Provider selection is no longer hard-coded in the control-plane import graph, yet provider diversity is still unfinished work.
- `beagle-host/services/ubuntu_beagle_provisioning.py` removed the ubuntu-beagle lifecycle block from the entrypoint, but it still uses today's Proxmox-shaped VM option semantics and `scripts/configure-sunshine-guest.sh --proxmox-host localhost` path under the new service seam.
- `beagle-host/services/sunshine_integration.py` removed the Sunshine/Moonlight block from the entrypoint, but it still depends on Sunshine-specific guest file paths/state layout, Sunshine HTTP/API semantics, `curl`/`openssl` behavior, and current Moonlight certificate-registration conventions under the new service seam.
- `beagle-host/services/public_streams.py` removed port-state/orchestration from the entrypoint, but it still interprets today's description-meta keys (`beagle-public-moonlight-port`) and VM inventory/config semantics through provider-backed reads under the new service seam.
- `beagle-host/services/policy_normalization.py` removed policy contract shaping from the entrypoint, but the normalized fields still reflect today's endpoint/profile policy semantics and browser/runtime expectations under the new service seam.
- `beagle-host/services/runtime_environment.py` removed manager pinned-pubkey derivation and public-host resolution from the entrypoint, but it still depends on today's manager-cert file location, local OpenSSL CLI behavior, and current DNS/IPv4-first host-resolution semantics under the new service seam.
- `beagle-host/services/endpoint_enrollment.py` removed endpoint enrollment/bootstrap payload shaping from the entrypoint, but it still reflects today's endpoint update/Moonlight/USB/egress/identity config contract plus the current thin-client enrollment-token flow under the new service seam.
- `beagle-host/services/ubuntu_beagle_restart.py` removed scheduled restart state/cancel logic from the entrypoint, but it still depends on today's host-provider delayed-restart behavior, process-group semantics, and the current `host_restart` / `host_restart_cancelled` state shape under the new service seam.
- `beagle-host/services/runtime_support.py` removed cache/env state from the entrypoint, but it still reflects today's simple in-memory cache semantics and the current shell-env parsing rules used for credentials/bootstrap under the new service seam.
- `beagle-host/services/runtime_exec.py` removed command-wrapper boilerplate from the entrypoint, but it still reflects today's `subprocess.run` behavior, default timeout semantics, and stdout-based JSON/text contracts under the new service seam.
- `beagle-host/services/time_support.py` removed timestamp helpers from the entrypoint, but it still reflects today's ISO-8601 formatting, `Z`-to-UTC parsing behavior, and positive-age calculation semantics under the new service seam.
- `beagle-host/services/runtime_paths.py` removed data-root and managed-directory creation from the entrypoint, but it still reflects today's preferred-vs-fallback data-dir behavior, `0700` chmod expectations, and current directory names (`endpoints`, `actions`, `support-bundles`, `policies`) under the new service seam.
- `beagle-host/services/metadata_support.py` removed description-meta parsing and normalized-hostname derivation from the entrypoint, but it still reflects today's `key: value` description convention and current `beagle-{vmid}` hostname fallback semantics under the new service seam.
- `beagle-host/services/persistence_support.py` removed shared JSON/file I/O from the entrypoint, but it still reflects today's pretty-printed JSON, trailing-newline, fallback-on-invalid-JSON, and best-effort chmod semantics under the new service seam.
- `beagle-host/services/request_support.py` removed bearer/origin/CORS policy from the entrypoint, but it still reflects today's manager/web/public-stream host assumptions, Proxmox UI port expansion, runtime cache keying, and current Authorization/CORS semantics under the new service seam.
- `beagle-host/services/support_bundle_store.py` now owns upload persistence too, but it intentionally preserves today's sanitized-filename behavior, including `.bin` fallback when suffixes are lost, so downstream download behavior stays unchanged until that contract is redesigned deliberately.
- `beagle-host/services/installer_template_patch.py` removed template rewrite semantics from the entrypoint, but the patched variable names and placeholders still reflect today's thin-client installer templates and release artifact surface under the new service seam.
- `beagle-host/services/ubuntu_beagle_inputs.py` removed ubuntu-beagle validation/preset semantics from the entrypoint, but those rules still intentionally reflect today's ubuntu-beagle desktop catalog, package preset IDs, and provisioning defaults under the new service seam.
- `beagle-host/services/action_queue.py` now owns queue orchestration and result waiting too, but action-id shape, polling cadence, result-file semantics, and queue timestamping still reflect today's control-plane action semantics so downstream endpoint/runtime consumers keep working unchanged.

### Script surfaces

- `scripts/lib/beagle_provider.py` is now the shared script-side read and first-write/exec seam, but it still only implements the Proxmox backend today.
- `scripts/lib/provider_shell.sh` is now the shared script-side provider bootstrap seam, but it still assumes today's SSH/bash execution model and only dispatches into the Proxmox-backed provider helper today.
- `scripts/lib/prepare_host_downloads.py` removes the hosted-download Python monolith from the shell script, but it still consumes the current provider helper plus the current Proxmox-shaped preset field set for hosted thin-client installers.
- `beagle-host/services/thin_client_preset.py` removes the overlapping preset-base duplication, but the host-only enrollment/update/identity delta and the USB-only slim preset delta still reflect today’s two related but not yet fully unified installer/runtime contracts.
- several scripts still execute `qm`/`pvesh` directly for fallback compatibility, install flows, or unreached write paths and should move to provider helpers incrementally.
- the clearest remaining direct script couplings are now the reduced compatibility branches retained in `scripts/configure-sunshine-guest.sh`, `scripts/ensure-vm-stream-ready.sh`, and `scripts/optimize-proxmox-vm-for-beagle.sh`, plus the still-separate thin-client/local-installer env builders that shape overlapping installer/profile fields outside the shared endpoint-profile contract

### Deploy / runtime provider threading

- `scripts/install-proxmox-host.sh` now records `BEAGLE_HOST_PROVIDER` into `host.env` and passes it into `install-proxmox-host-services.sh`
- `scripts/install-proxmox-host-services.sh` now writes `BEAGLE_HOST_PROVIDER` into `beagle-manager.env`
- `scripts/refresh-host-artifacts.sh` and `scripts/check-proxmox-host.sh` now run under the same selected host-provider kind
- `scripts/install-beagle-proxy.sh` now reads and persists the selected host-provider kind too, even though backend auto-detection still expects Proxmox semantics today
- `scripts/install-proxmox-ui-integration.sh` now reads the selected host-provider kind and skips cleanly when it is not `proxmox`
- the server-installer bootstrap now passes `BEAGLE_HOST_PROVIDER='proxmox'` explicitly into `install-proxmox-host.sh`
- this does not make Proxmox optional yet, but it removes another hidden assumption that provider choice only exists inside the Python control-plane process

### Thin-client Proxmox access

- thin-client-side Proxmox API and SPICE helpers are still explicitly Proxmox-bound.
- `thin-client-assistant/usb/preset_summary.py` now centralizes the derived preset-summary/UI-state layer used by the local installer and the Proxmox API helper, but the underlying preset assembly in `thin-client-assistant/usb/pve-thin-client-proxmox-api.py` still reflects current Proxmox login and VM-config semantics.
- `thin-client-assistant/usb/proxmox_preset.py` now centralizes the Proxmox-specific thin-client preset assembly and endpoint/login parsing instead of keeping that contract inside `pve-thin-client-proxmox-api.py`, but the contract is still intentionally Proxmox-shaped today.
- `thin-client-assistant/runtime/apply_enrollment_config.py` now centralizes the runtime enrollment-response write path used by `prepare-runtime.sh`, but the underlying field mapping still reflects today’s endpoint enrollment payload contract and runtime env naming.
- `thin-client-assistant/runtime/status_writer.py` now centralizes runtime and launch status-file serialization, but the status semantics still reflect today’s Moonlight/Kiosk/GFN runtime model and current thin-client env names.
- `thin-client-assistant/runtime/generate_config_from_preset.py` now centralizes preset-file parsing plus preset→runtime config generation for `common.sh`, and the default table it uses is now shared with the shell installer/runtime paths through `thin-client-assistant/installer/env-defaults.json`; the remaining drift is therefore narrower and mostly in mode/cmdline override behavior rather than raw default literals.
- `thin-client-assistant/runtime/mode_overrides.py` now centralizes the cmdline-driven `client_mode`→runtime-mode/boot-profile mapping used by `common.sh`, so the remaining runtime shell drift is no longer in mode semantics but in config discovery and preset restoration behavior.
- `thin-client-assistant/runtime/config_discovery.py` now centralizes live-state config discovery, preset discovery, cmdline preset restore/decode, and preset-driven config-dir resolution used by `common.sh`, so the remaining runtime shell drift is narrower and mostly in config sourcing plus path/ownership orchestration.
- `thin-client-assistant/runtime/config_loader.sh` now centralizes preset-driven config generation and runtime config file loading used by `common.sh`, so the remaining runtime shell drift is narrower and mostly in path ownership, stream state, and runtime environment orchestration.

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
