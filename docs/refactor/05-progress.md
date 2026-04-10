# Refactor Progress

## 2026-04-09

### 2026-04-10 additions

- Extracted the remaining large Proxmox UI provisioning blocks out of `proxmox-ui/beagle-ui.js`:
  - added `proxmox-ui/components/provisioning-result-modal.js` carrying `provisioningStatusLabel`, `provisioningStatusBadgeClass`, `renderProvisioningBadge`, `renderProvisioningResultHtml`, and `showProvisioningResultWindow`
  - added `proxmox-ui/components/provisioning-create-modal.js` carrying `safeHostnameCandidate`, `listToMultiline`, `readCheckedValues`, and the full `showUbuntuBeagleCreateModal` orchestration
  - reduced `proxmox-ui/beagle-ui.js` from about 1760 lines to about 950 lines; it now holds only delegation wrappers for the provisioning result window, the create/edit modal, and the inline badge renderer
- Updated `scripts/install-proxmox-ui-integration.sh` and `scripts/validate-project.sh` so both new `components/` modules are installed into `/usr/share/pve-manager/js/`, injected into `index.html.tpl`, and syntax-checked on validate.
- Extended the host-side provider seam in `proxmox-host/providers/proxmox_host_provider.py` with VM lifecycle write methods:
  - `create_vm`, `set_vm_options`, `delete_vm_options`, `set_vm_description`, `set_vm_boot_order`, `start_vm`, `stop_vm`
  - all go through a shared `_flatten_option_pairs` helper so callers pass either `Mapping` or list-of-tuples option shapes
  - constructor now takes an explicit `run_checked` callable in addition to `run_json` and `run_text`
- Rerouted VM lifecycle writes in `proxmox-host/bin/beagle-control-plane.py` through the provider:
  - `finalize_ubuntu_beagle_install` uses `delete_vm_options`, `set_vm_boot_order`, `stop_vm`, and `start_vm`
  - `create_ubuntu_beagle_vm` uses `create_vm`, `set_vm_description`, `set_vm_options`, `set_vm_boot_order`, and `start_vm`
  - `update_ubuntu_beagle_vm` uses `set_vm_description`
- Finished the next host-provider slice for control-plane guest execution and restart scheduling:
  - added `guest_exec_bash`, `guest_exec_status`, `guest_exec_script_text`, and `schedule_vm_restart_after_stop` to `proxmox-host/providers/proxmox_host_provider.py`
  - `schedule_ubuntu_beagle_vm_restart` now delegates to the provider instead of embedding the restart shell flow inline
  - `guest_exec_text`, `guest_exec_out_data`, and `guest_exec_payload` now delegate to provider methods instead of issuing `qm guest exec` / `qm guest exec-status` directly from `beagle-control-plane.py`
- Continued shrinking the browser entrypoints and documenting the still-missing profile contract:
  - added `proxmox-ui/state/vm-profile.js` and moved the Beagle profile synthesis flow out of `proxmox-ui/beagle-ui.js`
  - added `extension/services/profile.js` and moved the extension-side VM profile resolution, installer readiness state helpers, action-state formatting, endpoint env generation, and operator notes there
  - reduced `proxmox-ui/beagle-ui.js` further from about 950 lines to about 813 lines
  - reduced `extension/content.js` from about 700+ lines to about 541 lines, leaving it as a renderer/event entrypoint instead of carrying profile synthesis internals
  - updated `extension/manifest.json`, `scripts/install-proxmox-ui-integration.sh`, and `scripts/validate-project.sh` so both new modules are loaded and syntax-checked everywhere
- Made the host-side public endpoint profile contract explicit:
  - added `proxmox-host/bin/endpoint_profile_contract.py` with normalized browser-/installer-facing profile fields plus contract version `v1`
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
- `proxmox-ui/` now has `common`, `api-client`, `state`, `provisioning`, `usb`, `utils`, and a full `components` set including `profile-modal.js`, `fleet-modal.js`, `provisioning-result-modal.js`, and `provisioning-create-modal.js`. `beagle-ui.js` dropped from roughly 2500+ lines to about 950 lines and now mostly orchestrates bootstrap, context resolution, catalog loading, and delegation wrappers.
- `extension/content.js` no longer performs raw `/api2/json`, Beagle API token/config plumbing, inline VM profile synthesis, or inline profile modal rendering itself, but it is still the extension's DOM integration/boot monolith.
- `proxmox-host/bin/beagle-control-plane.py` now delegates VM inventory, node inventory, VM config lookup, next-VMID allocation, storage inventory, guest IPv4 lookup, VM lifecycle writes (create, set, description, boot order, start, stop, option delete), guest-exec flows, and scheduled restart orchestration into `proxmox-host/providers/proxmox_host_provider.py`, while the browser-facing endpoint profile contract is normalized by `proxmox-host/bin/endpoint_profile_contract.py`.
- No new behavioral tests or smoke tests have been added yet.

### Known risks after this run

- `beagle-control-plane.py` remains a large monolith, even though VM lifecycle writes, guest-exec flows, and scheduled restarts now flow through provider helpers.
- `proxmox-ui/beagle-ui.js` is materially smaller and the profile synthesis block is out, but the file still holds bootstrap/catalog/context-resolution orchestration that will need further splits before it can become a thin entrypoint.
- Frontend token handling still exists as documented.
- The provider abstraction now covers Proxmox UI, browser extension, host-side reads, host-side VM lifecycle writes, guest-exec, scheduled restart orchestration, an explicit host-side endpoint profile contract, and one shared browser-side VM profile mapper. The remaining browser-side duplication is mostly in endpoint export/note/helper logic and in entrypoint-level UI orchestration.
- Script surfaces and installer-side provider neutrality are still pending.
- Local `.build/` and `dist/` directories still exist and should not be treated as authoritative release outputs.
