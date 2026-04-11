# Refactor Progress

## 2026-04-09

### 2026-04-11 — ubuntu-beagle provisioning-state extraction

- Extracted the ubuntu-beagle installer state persistence and summarization helpers out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/ubuntu_beagle_state.py`:
  - `UbuntuBeagleStateService` owns `tokens_dir()`, `token_path(token)`, `load(token)`, `save(token, payload)`, `summarize(payload, *, include_credentials)`, `list_all(*, include_credentials)`, and `latest_for_vmid(vmid, *, include_credentials)`; collaborators (`data_dir` callable, `load_json_file`, `write_json_file`, `safe_slug`, `ubuntu_beagle_profile_id`) are injected through the kwargs-only constructor so the service stays agnostic of the Proxmox control plane
  - `ubuntu_beagle_tokens_dir`, `ubuntu_beagle_token_path`, `load_ubuntu_beagle_state`, `save_ubuntu_beagle_state`, `summarize_ubuntu_beagle_state`, `list_ubuntu_beagle_states`, and `latest_ubuntu_beagle_state_for_vmid` in the control plane now delegate through `ubuntu_beagle_state_service()` with unchanged signatures, so HTTP handlers under `/api/v1/public/ubuntu-install/*`, `/api/v1/ubuntu-beagle-vms`, and the `VmProfileService` / `VmStateService` wiring keep working without any further edits
  - The `schedule_ubuntu_beagle_vm_restart`, `cancel_scheduled_ubuntu_beagle_vm_restart`, and `public_ubuntu_beagle_complete_url` helpers stay in the control plane because they depend on `HOST_PROVIDER`, `PUBLIC_MANAGER_URL`, and process-signal plumbing that is not part of the persistence seam
- `scripts/install-proxmox-host-services.sh` installs the new service file into `$HOST_RUNTIME_DIR/services/`
- Verified the live control-plane module still imports cleanly with `BEAGLE_MANAGER_DATA_DIR=/tmp/beagle-smoketest`, and the save/load/summarize/list/latest round-trip works end-to-end through the wrappers (saved vmid 101 with `started: True`, round-tripped through the service, summarized as `installing` / `autoinstall`, recovered through `latest_ubuntu_beagle_state_for_vmid`)
- `beagle-control-plane.py` shrank from about 5138 to about 5084 lines as part of this slice

### 2026-04-11 — policy and support-bundle store extraction

- Extracted the policy-store I/O helpers out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/policy_store.py`:
  - `PolicyStoreService` owns `policy_path(name)`, `save(payload, policy_name=...)`, `load(name)`, `delete(name)`, and `list_all()`; `save()` is wired with the existing `normalize_policy_payload` callable so the policy shape is still owned by the control plane but I/O and listing lives behind the service
  - `policy_path`, `save_policy`, `load_policy`, `delete_policy`, and `list_policies` in the control plane now delegate through `policy_store_service()`; HTTP handler call sites and `HealthPayloadService` (which already takes `list_policies` as a callable) keep working with no wiring changes
- Extracted the support-bundle metadata/archive helpers into `beagle-host/services/support_bundle_store.py`:
  - `SupportBundleStoreService` owns `metadata_path(bundle_id)`, `archive_path(bundle_id, filename)`, `find_metadata(bundle_id)`, and `list_metadata(*, node=None, vmid=None)`
  - `support_bundle_metadata_path`, `support_bundle_archive_path`, `list_support_bundle_metadata`, and `find_support_bundle_metadata` in the control plane now delegate through `support_bundle_store_service()`; `store_support_bundle()` continues to call the wrapper-backed path helpers and is unchanged
- `scripts/install-proxmox-host-services.sh` installs both new service files into `$HOST_RUNTIME_DIR/services/`
- Verified `beagle-control-plane.py` still imports cleanly with an isolated data dir; `policy_path('my-policy')`, `support_bundle_metadata_path('b-abc')`, `support_bundle_archive_path('b-abc', 'bundle.tar.gz')`, `list_policies()`, `find_support_bundle_metadata('nonexistent')`, and `list_support_bundle_metadata()` all returned the expected shapes
- `beagle-control-plane.py` net change was only about -1 line for this slice because the two lazy factories offset the short helper bodies — this slice is about the architectural seam, not line count

### 2026-04-11 — endpoint-report and action-queue service extraction

- Extracted the endpoint-report I/O and summarization helpers out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/endpoint_report.py`:
  - `EndpointReportService` owns `report_path(node, vmid)`, `load(node, vmid)`, `list_all()`, and `summarize(payload)`
  - `summarize_endpoint_report`, `endpoint_report_path`, `load_endpoint_report`, and `list_endpoint_reports` in the control plane now delegate through `endpoint_report_service()`; the control-plane helper signatures are unchanged so `HealthPayloadService`, `FleetInventoryService`, and the HTTP handler at `/api/v1/endpoints/{node}/{vmid}/reports` keep working without touching the service wiring
- Extracted the action-queue I/O and result summarization helpers into `beagle-host/services/action_queue.py`:
  - `ActionQueueService` owns `queue_path(node, vmid)`, `result_path(node, vmid)`, `load_queue`, `save_queue`, `load_result`, `store_result`, and `summarize_result`
  - `action_queue_path`, `action_result_path`, `load_action_queue`, `save_action_queue`, `load_action_result`, `store_action_result`, and `summarize_action_result` in the control plane now delegate through `action_queue_service()`; `queue_vm_action`, `queue_bulk_actions`, and `dequeue_vm_actions` continue to work via those wrappers with no changes
- `scripts/install-proxmox-host-services.sh` installs both new service files into `$HOST_RUNTIME_DIR/services/`
- Verified the control-plane module still imports cleanly and both new lazy factories (`endpoint_report_service()`, `action_queue_service()`) instantiate with the expected class names; `summarize_endpoint_report({})` and `summarize_action_result(None)` return the documented empty shapes
- `beagle-control-plane.py` shrank from about 5222 to about 5139 lines as part of this slice

### 2026-04-11 — health and installer-script service extraction

- Continued pulling HTTP-facing response builders out of `beagle-host/bin/beagle-control-plane.py`:
  - added `beagle-host/services/health_payload.py` with `HealthPayloadService.build_payload()` covering downloads-status lookup, VM listing + per-VM endpoint compliance bucketing, pending action counts, and the full `/api/v1/health` envelope
  - added `beagle-host/services/installer_script.py` with `InstallerScriptService.build_preset()` plus `render_installer_script()`, `render_live_usb_script()`, and `render_windows_installer_script()` covering the entire VM installer/live-USB/Windows-installer script generation flow including profile lookup, enrollment token issuance, sunshine identity fetch, preset assembly, template patching, and filename derivation
  - `beagle-control-plane.py` now keeps only thin `build_health_payload`, `build_installer_preset`, `render_vm_installer_script`, `render_vm_live_usb_script`, and `render_vm_windows_installer_script` wrappers that delegate to lazily-initialized module-level service singletons (`health_payload_service()`, `installer_script_service()`), mirroring the existing service factory pattern
- `scripts/install-proxmox-host-services.sh` installs the two new service files into `$HOST_RUNTIME_DIR/services/`; `scripts/validate-project.sh` picks them up automatically through the `beagle-host/` python discovery
- Verified `beagle-control-plane.py` still imports cleanly with all five HTTP-facing wrappers wired through the lazy factories
- `beagle-control-plane.py` shrank from about 5385 to about 5222 lines as part of this slice

### 2026-04-10 — response-builder service extraction

- Extracted the next batch of HTTP-facing response builders out of `beagle-host/bin/beagle-control-plane.py` into dedicated service modules:
  - added `beagle-host/services/update_feed.py` with `UpdateFeedService.build_update_feed(profile, ...)` covering downloads-status lookup, channel/behavior/pin resolution, payload readiness, and the full update-feed response shape
  - added `beagle-host/services/fleet_inventory.py` with `FleetInventoryService.build_inventory()` covering VM listing, per-VM profile composition, endpoint/action/provisioning summaries, installer URLs, and the final `{service, version, generated_at, vms}` envelope
  - `beagle-control-plane.py` now keeps only thin `build_update_feed` / `build_vm_inventory` wrappers that delegate to lazily-initialized module-level service singletons, mirroring the existing `vm_profile_service()` / `vm_state_service()` pattern
- `scripts/install-proxmox-host-services.sh` installs the two new service files into `$HOST_RUNTIME_DIR/services/` alongside the existing ones; `scripts/validate-project.sh` picks them up automatically through the `beagle-host/` python discovery.
- Smoke-tested both services outside the server loop: `UpdateFeedService` resolves `installed_version != latest_version` into `available=True`, and `FleetInventoryService.build_inventory()` returns the expected `beagle-control-plane` envelope for an empty VM list.

### 2026-04-10 additions

- Aligned the refactor north star with the intended product direction:
  - documented explicitly that provider-neutrality is a means to a first-party Beagle virtualization product/provider, not the final target
  - documented Proxmox as a future optional provider rather than the architecture center
  - added the missing roadmap language and exit criteria for eventually making external providers optional
- Renamed the generic host/control-plane repo surface from `proxmox-host/` to `beagle-host/`:
  - updated the canonical repo path, systemd unit source path, host-service installer, validation, packaging, and repo documentation to use `beagle-host/`
  - kept a compatibility bridge in `scripts/install-proxmox-host-services.sh` by linking `/opt/beagle/proxmox-host` to `/opt/beagle/beagle-host` during install
  - kept genuinely provider-specific names such as `proxmox_host_provider.py`, `install-proxmox-host.sh`, and external `--proxmox-host` flags unchanged to avoid breaking the active Proxmox deployment surface
- Extracted the remaining large Proxmox UI provisioning blocks out of `proxmox-ui/beagle-ui.js`:
  - added `proxmox-ui/components/provisioning-result-modal.js` carrying `provisioningStatusLabel`, `provisioningStatusBadgeClass`, `renderProvisioningBadge`, `renderProvisioningResultHtml`, and `showProvisioningResultWindow`
  - added `proxmox-ui/components/provisioning-create-modal.js` carrying `safeHostnameCandidate`, `listToMultiline`, `readCheckedValues`, and the full `showUbuntuBeagleCreateModal` orchestration
  - reduced `proxmox-ui/beagle-ui.js` from about 1760 lines to about 950 lines; it now holds only delegation wrappers for the provisioning result window, the create/edit modal, and the inline badge renderer
- Updated `scripts/install-proxmox-ui-integration.sh` and `scripts/validate-project.sh` so both new `components/` modules are installed into `/usr/share/pve-manager/js/`, injected into `index.html.tpl`, and syntax-checked on validate.
- Extended the host-side provider seam in `beagle-host/providers/proxmox_host_provider.py` with VM lifecycle write methods:
  - `create_vm`, `set_vm_options`, `delete_vm_options`, `set_vm_description`, `set_vm_boot_order`, `start_vm`, `stop_vm`
  - all go through a shared `_flatten_option_pairs` helper so callers pass either `Mapping` or list-of-tuples option shapes
  - constructor now takes an explicit `run_checked` callable in addition to `run_json` and `run_text`
- Rerouted VM lifecycle writes in `beagle-host/bin/beagle-control-plane.py` through the provider:
  - `finalize_ubuntu_beagle_install` uses `delete_vm_options`, `set_vm_boot_order`, `stop_vm`, and `start_vm`
  - `create_ubuntu_beagle_vm` uses `create_vm`, `set_vm_description`, `set_vm_options`, `set_vm_boot_order`, and `start_vm`
  - `update_ubuntu_beagle_vm` uses `set_vm_description`
- Finished the next host-provider slice for control-plane guest execution and restart scheduling:
  - added `guest_exec_bash`, `guest_exec_status`, `guest_exec_script_text`, and `schedule_vm_restart_after_stop` to `beagle-host/providers/proxmox_host_provider.py`
  - `schedule_ubuntu_beagle_vm_restart` now delegates to the provider instead of embedding the restart shell flow inline
  - `guest_exec_text`, `guest_exec_out_data`, and `guest_exec_payload` now delegate to provider methods instead of issuing `qm guest exec` / `qm guest exec-status` directly from `beagle-control-plane.py`
- Continued shrinking the browser entrypoints and documenting the still-missing profile contract:
  - added `proxmox-ui/state/vm-profile.js` and moved the Beagle profile synthesis flow out of `proxmox-ui/beagle-ui.js`
  - added `extension/services/profile.js` and moved the extension-side VM profile resolution, installer readiness state helpers, action-state formatting, endpoint env generation, and operator notes there
  - reduced `proxmox-ui/beagle-ui.js` further from about 950 lines to about 813 lines
  - reduced `extension/content.js` from about 700+ lines to about 541 lines, leaving it as a renderer/event entrypoint instead of carrying profile synthesis internals
  - updated `extension/manifest.json`, `scripts/install-proxmox-ui-integration.sh`, and `scripts/validate-project.sh` so both new modules are loaded and syntax-checked everywhere
- Made the host-side public endpoint profile contract explicit:
  - added `beagle-host/bin/endpoint_profile_contract.py` with normalized browser-/installer-facing profile fields plus contract version `v1`
  - `build_profile` now returns a normalized contract payload instead of relying on implicit handler-local defaults
  - installer-prep state generation now reuses the dedicated contract surface for installer URLs and stream metadata instead of rebuilding that subset inline
  - inventory rows now expose `profile_contract_version`, and browser profile views surface `control_plane_contract_version` in exported JSON for diagnostics
- Collapsed the duplicated browser-side VM profile mapper into one shared helper and continued the extension UI split:
  - added `extension/shared/vm-profile-mapper.js` as the shared browser-side mapper used by both `proxmox-ui/state/vm-profile.js` and `extension/services/profile.js`
  - reduced `proxmox-ui/state/vm-profile.js` from about 170 lines to about 70 lines; it now only fetches collaborators and delegates mapping
  - rewired `extension/services/profile.js` onto the same shared mapper so metadata fallback rules and field naming no longer drift independently
  - added `extension/components/profile-modal.js` and moved the extension profile renderer/action handling out of `extension/content.js`
  - reduced `extension/content.js` further from about 540 lines to about 328 lines so it now focuses on boot, toolbar/menu integration, and modal launching
  - updated `extension/manifest.json`, `scripts/install-proxmox-ui-integration.sh`, and `scripts/validate-project.sh` so the shared mapper is loaded in both browser surfaces and the extension profile component is validated
  - fixed the Proxmox host asset load order so the shared mapper and profile modal are present before `proxmox-ui/state/vm-profile.js` evaluates
- Removed the next browser-side duplication layer and split the extension DOM boot path:
  - added `extension/shared/vm-profile-helpers.js` as the shared browser-side source for endpoint-env export, operator notes, and action-state formatting
  - rewired `proxmox-ui/state/vm-profile.js`, `proxmox-ui/components/profile-modal.js`, and `extension/services/profile.js` onto that shared helper so note/export semantics no longer depend on one browser surface importing the other's component logic
  - removed the old `proxmox-ui/state/vm-profile.js` dependency on `proxmox-ui/components/profile-modal.js` for note/env generation; state now depends only on shared mapper/helper modules plus services
  - added `extension/components/vm-page-integration.js` for toolbar/menu injection and mutation-observer boot logic
  - reduced `extension/content.js` again from about 328 lines to about 189 lines so it now focuses on overlay/styles, VM profile resolution, and modal/download launch actions
  - updated `extension/manifest.json`, `scripts/install-proxmox-ui-integration.sh`, and `scripts/validate-project.sh` so the new shared helper and extension DOM-integration module are loaded and validated everywhere they are needed
- Extracted the remaining Proxmox-UI ExtJS/DOM integration monolith out of `proxmox-ui/beagle-ui.js`:
  - added `proxmox-ui/components/extjs-integration.js` for Proxmox console button wiring, fleet launcher injection, create-VM button/menu integration, and the periodic `integrate()` boot loop
  - removed the ExtJS label matching and Create-VM DOM fallback logic from `proxmox-ui/beagle-ui.js`
  - reduced `proxmox-ui/beagle-ui.js` from about 797 lines to about 552 lines so it is much closer to a bootstrap/orchestration entrypoint
  - updated `scripts/install-proxmox-ui-integration.sh` and `scripts/validate-project.sh` so the new component is installed, loaded before `beagle-ui.js`, and syntax-checked
- Extracted the shared Proxmox-UI modal shell out of `proxmox-ui/beagle-ui.js`:
  - added `proxmox-ui/components/modal-shell.js` for shared modal CSS, overlay lifecycle helpers, the fleet launcher DOM identifier, and a reusable loading-overlay renderer
  - rewired `showFleetModal` and `showProfileModal` so they call `modalShell.showLoadingOverlay(...)` instead of building inline loading markup in the entrypoint
  - reduced `proxmox-ui/beagle-ui.js` again from about 552 lines to about 410 lines so it is now mostly dependency lookup, thin wrappers, and `boot()` wiring
  - updated `scripts/install-proxmox-ui-integration.sh` and `scripts/validate-project.sh` so the new shell component is installed, injected into `index.html.tpl`, and syntax-checked
- Started the first service-oriented control-plane split under `beagle-host/services/`:
  - added `beagle-host/services/virtualization_inventory.py` with `VirtualizationInventoryService` for provider-backed VM listing, node inventory, guest IPv4 lookup, VM config lookup, bridge parsing, and bridge inventory
  - rewired the existing wrappers `first_guest_ipv4`, `list_vms`, `list_nodes_inventory`, `config_bridge_names`, `list_bridge_inventory`, `get_vm_config`, and `find_vm` in `beagle-host/bin/beagle-control-plane.py` to delegate through the new service singleton instead of touching `ProxmoxHostProvider` directly
  - added `beagle-host/services/vm_state.py` with `VmStateService` for endpoint compliance evaluation and VM-state composition
  - rewired `evaluate_endpoint_compliance` and `build_vm_state` in `beagle-host/bin/beagle-control-plane.py` to delegate through the new service singleton while keeping existing function names stable for handlers
  - reduced `beagle-host/bin/beagle-control-plane.py` from about 5785 lines to about 5677 lines while creating the first stable `beagle-host/services/*` seams for future profile/inventory extraction
- Extracted the next host-side business-logic block under `beagle-host/services/`:
  - added `beagle-host/services/vm_profile.py` with `VmProfileService` for VM profile synthesis, assignment resolution, policy matching, public-stream derivation, and VM fingerprint assessment
  - rewired `should_use_public_stream`, `build_public_stream_details`, `resolve_assigned_target`, `resolve_policy_for_vm`, `assess_vm_fingerprint`, and `build_profile` in `beagle-host/bin/beagle-control-plane.py` to delegate through a new `vm_profile_service()` singleton
  - kept the public helper names and call shapes stable so handlers, installer flows, and existing internal call sites did not change during the extraction
  - updated `scripts/install-proxmox-host-services.sh` so the new host service is installed alongside the other `beagle-host/services/*` modules
  - reduced `beagle-host/bin/beagle-control-plane.py` again from about 5677 lines to about 5429 lines while removing the largest remaining inline profile/assignment/public-stream block from the HTTP entrypoint
- Introduced the first real host-side provider registry/contract seam:
  - added `beagle-host/providers/host_provider_contract.py` as the explicit host-provider contract for node, VM, storage, guest-exec, guest-IP, and lifecycle operations currently needed by the control plane
  - added `beagle-host/providers/registry.py` as the host-provider registry and provider factory, with Proxmox registered as the first concrete host provider and `pve` normalized to `proxmox`
  - rewired `beagle-host/bin/beagle-control-plane.py` to bootstrap `HOST_PROVIDER` through the registry via `BEAGLE_HOST_PROVIDER` instead of importing `ProxmoxHostProvider` directly
  - rewired the remaining direct provider call sites in the control plane to the generic `HOST_PROVIDER` object and added the active provider plus `available_providers` to `/api/v1/health`
  - updated `beagle-host/services/virtualization_inventory.py` to depend on the typed host-provider contract instead of `Any`
  - updated `scripts/install-proxmox-host-services.sh` so the host-provider contract and registry ship to the runtime host alongside the concrete Proxmox provider
  - kept the control-plane entrypoint roughly flat at about 5434 lines while removing another direct architectural dependency on a concrete provider class
- Closed a release-surface gap before packaging:
  - `scripts/package.sh` now includes `website/` in the shipped source tarball
  - `scripts/validate-project.sh` now syntax-checks `website/app.js` so the public website code is validated alongside the other browser surfaces
- Reran `scripts/validate-project.sh` to confirm the extraction and provider seams still pass syntax, byte-compile, manifest, and changelog gates.

## 2026-04-09

### Completed in this run

- Created the mandatory `docs/refactor/` handoff and planning set:
  - `00-system-overview.md`
  - `01-problem-analysis.md`
  - `02-target-architecture.md`
  - `03-refactor-plan.md`
  - `04-risk-register.md`
  - `05-progress.md`
  - `06-next-steps.md`
  - `07-decisions.md`
  - `08-todo-global.md`
- Analyzed the current repository structure and identified the main monoliths and risk areas.
- Documented the target modular architecture and the incremental migration strategy.
- Removed `AGENTS.md` from `.gitignore` so the central control document is no longer implicitly excluded.
- Updated repository validation to require `AGENTS.md` and the `docs/refactor/` files.
- Updated source packaging to include `AGENTS.md`.
- Started Phase 2 with a first Proxmox UI seam extraction:
  - added `proxmox-ui/beagle-ui-common.js`
  - moved config/token/URL helper logic behind a dedicated runtime asset
  - updated `scripts/install-proxmox-ui-integration.sh` to install and load the extra asset
  - updated validation to syntax-check the new file
- Continued Phase 2 with additional module extraction:
  - added `proxmox-ui/api-client/beagle-api.js`
  - added `proxmox-ui/state/installer-eligibility.js`
  - reduced `proxmox-ui/beagle-ui.js` further to delegated bootstrap/wrapper behavior for API and state concerns
  - updated Proxmox UI installation to load the additional runtime assets in order
- Continued Phase 2 again with feature-specific API seams:
  - added `proxmox-ui/provisioning/api.js`
  - added `proxmox-ui/usb/api.js`
  - moved provisioning and installer-prep credential API wrappers out of `beagle-ui.js`
- Added the first `proxmox-ui/utils/` module:
  - `proxmox-ui/utils/browser-actions.js`
  - moved basic error/toast/open/download browser actions out of `beagle-ui.js`
- Started extracting USB-specific UI state handling:
  - added `proxmox-ui/usb/ui.js`
  - moved installer-prep banner/button/state update helpers out of `beagle-ui.js`
- Started `components/` extraction:
  - added `proxmox-ui/components/ui-helpers.js`
  - added `proxmox-ui/components/desktop-overlay.js`
  - moved generic HTML helpers and the desktop wallpaper overlay renderer out of `beagle-ui.js`
- Introduced the first provider-neutral architecture seam for browser-side logic:
  - added `core/provider/registry.js`
  - added `core/virtualization/service.js`
  - added `core/platform/service.js`
  - added `providers/proxmox/virtualization-provider.js`
  - rewired `proxmox-ui/state/installer-eligibility.js` to use the new platform service
  - moved `proxmox-ui/beagle-ui.js` inventory/profile/fleet loading paths onto generic virtualization/platform services instead of direct `/api2/json` usage
  - updated Proxmox UI installation, validation, and source packaging to include the new `core/` and `providers/` assets
- Continued the architecture handoff and rule set for provider-neutral work:
  - updated `AGENTS.md` to make provider-neutrality and `09-provider-abstraction.md` part of the mandatory continuation flow
  - updated refactor docs to describe `core/` and `providers/` as first-class repo surfaces
  - extended the risk register with the incomplete-provider-abstraction risk
  - aligned general architecture/security/install docs so Proxmox is described as the current provider, not as the permanent architecture center

### Current phase assessment

- Phase 0 Analysis: completed as a baseline
- Phase 1 Target architecture: completed as a baseline
- Phase 2 Proxmox UI refactor: advanced from helper extraction to dedicated profile/fleet component modules plus the first aligned browser-extension seam
- Provider abstraction groundwork: wired into the Proxmox UI, the browser extension, and a first host-side control-plane helper
- Provider-neutral documentation and continuation rules: aligned with the new architecture baseline
- Phase 3 onward: not yet implemented structurally, except for process guardrails

### What is not done yet

- `thin-client-assistant/` and `beagle-kiosk/` still have not been modularized.
- `beagle-host/` is now the canonical generic host/control-plane surface in the repo; `proxmox-host/` is no longer the source tree path.
- `proxmox-ui/` now has `common`, `api-client`, `state`, `provisioning`, `usb`, `utils`, and a full `components` set including `modal-shell.js`, `profile-modal.js`, `fleet-modal.js`, `provisioning-result-modal.js`, `provisioning-create-modal.js`, and `extjs-integration.js`. `beagle-ui.js` dropped from roughly 2500+ lines to about 410 lines and now mostly orchestrates bootstrap, context resolution, token/url wrappers, and delegation into extracted modules.
- `extension/content.js` no longer performs raw `/api2/json`, Beagle API token/config plumbing, inline VM profile synthesis, inline profile modal rendering, or toolbar/menu boot orchestration itself; that DOM integration now lives in `extension/components/vm-page-integration.js`, leaving `content.js` as a much thinner entrypoint.
- `beagle-host/bin/beagle-control-plane.py` now delegates provider-backed VM/node/config/bridge/guest-IP read paths through `beagle-host/services/virtualization_inventory.py`, delegates endpoint compliance and VM-state composition through `beagle-host/services/vm_state.py`, delegates VM inventory, node inventory, VM config lookup, next-VMID allocation, storage inventory, guest IPv4 lookup, VM lifecycle writes (create, set, description, boot order, start, stop, option delete), guest-exec flows, and scheduled restart orchestration into `beagle-host/providers/proxmox_host_provider.py`, while the browser-facing endpoint profile contract is normalized by `beagle-host/bin/endpoint_profile_contract.py`.
- No new behavioral tests or smoke tests have been added yet.

### Known risks after this run

- `beagle-control-plane.py` remains a large monolith, even though provider-backed read helpers now live in `beagle-host/services/virtualization_inventory.py`, endpoint compliance and VM-state composition now live in `beagle-host/services/vm_state.py`, and VM lifecycle writes, guest-exec flows, and scheduled restarts already flow through provider helpers.
- `proxmox-ui/beagle-ui.js` is materially smaller and no longer owns the profile synthesis, provisioning modal bodies, ExtJS wiring, or shared loading-shell markup/CSS, but it still holds bootstrap/context-resolution/token/url wrapper orchestration that should shrink further before it becomes a minimal entrypoint.
- Frontend token handling still exists as documented.
- The provider abstraction now covers Proxmox UI, browser extension, host-side reads, host-side VM lifecycle writes, guest-exec, scheduled restart orchestration, an explicit host-side endpoint profile contract, and shared browser-side profile mapper/helper modules. The remaining browser-side UI debt is now mostly in `proxmox-ui/beagle-ui.js` orchestration, `proxmox-ui/components/extjs-integration.js` runtime coupling to the current Proxmox ExtJS surface, and the still-large extension/proxmox profile action renderers.
- Script surfaces and installer-side provider neutrality are still pending.
- Local `.build/` and `dist/` directories still exist and should not be treated as authoritative release outputs.
