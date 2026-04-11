# Next Steps

## Immediate next slice

Now that the control plane exposes a normalized endpoint profile contract `v1`, the browser-side VM profile mapper and helper layer are shared, the Proxmox UI entrypoint is down to about 410 lines, the extension entrypoint is down to about 189 lines, the host-side read/state/profile seams exist under `beagle-host/services/`, the host bootstrap now selects `HOST_PROVIDER` through `beagle-host/providers/registry.py`, and the next batch of host services (`UpdateFeedService`, `FleetInventoryService`, `HealthPayloadService`, `InstallerScriptService`, `EndpointReportService`, `ActionQueueService`, `PolicyStoreService`, `SupportBundleStoreService`, `UbuntuBeagleStateService`) has been pulled out of `beagle-control-plane.py` (now around 5080 lines, with most persistence-layer helpers and the ubuntu-beagle installer state flow behind dedicated seams), the next slice should keep shrinking `beagle-ui.js` while turning the control plane into a real service composition surface and making the host-provider contract more complete.

Strategic framing:

- these immediate slices are not only about cleaner Proxmox support
- they are the preparation path toward a first-party Beagle virtualization provider with Proxmox as an optional provider
- the generic host/control-plane surface is now named `beagle-host/`; new work should use that name consistently for repo-internal architecture

### Concrete next tasks

1. Continue splitting `proxmox-ui/beagle-ui.js`:
   - extract the remaining fleet/profile launch orchestration and dependency-composition wrappers into dedicated modules under `proxmox-ui/components/` and `proxmox-ui/state/`
   - after `modal-shell.js`, `extjs-integration.js`, and the modal renderers are out, the remaining file should converge on dependency lookup plus a small `boot()` entrypoint
2. Continue decomposing `beagle-host/bin/beagle-control-plane.py` around service-oriented modules:
   - `UpdateFeedService`, `FleetInventoryService`, `HealthPayloadService`, `InstallerScriptService`, `EndpointReportService`, `ActionQueueService`, `PolicyStoreService`, `SupportBundleStoreService`, and `UbuntuBeagleStateService` are now out; the next valuable extractions are the VM-secret I/O helpers (`vm_secret_path`, `load_vm_secret`, `save_vm_secret` — the heavier `ensure_vm_secret` depends on ssh keygen + sunshine + usb-tunnel plumbing and should stay until those collaborators are themselves extracted), the enrollment-token helpers (`enrollment_tokens_dir`, `enrollment_token_path`, `load_enrollment_token`, `mark_enrollment_token_used`, `enrollment_token_is_valid`), and the download/artifact metadata helpers (`update_payload_metadata`, `public_installer_iso_url`, `public_payload_latest_download_url`, `public_bootstrap_latest_download_url` and sibling pure helpers)
   - these should follow the same pattern: a dedicated `beagle-host/services/*.py` module with a class that receives its collaborators (file loaders, dir helpers, slug helpers, time helpers) through the constructor, and a lazily-initialized module-level factory in `beagle-control-plane.py` that keeps the delegating wrapper signature stable
3. Continue the host-provider abstraction itself:
   - define the next provider-complete contract slice in `beagle-host/providers/host_provider_contract.py` and move any remaining host-side direct provider assumptions to that contract or to service modules consuming it
   - thread `BEAGLE_HOST_PROVIDER` through the deploy/install/runtime docs and prepare the repo for a second provider or mock provider without changing current Proxmox behavior
4. Continue splitting the browser UI action/render layers:
   - move the next action-heavy profile modal helpers out of `extension/components/profile-modal.js` and, where shared, out of `proxmox-ui/components/profile-modal.js`
   - keep the shared browser helper seam under `extension/shared/*` when both browser surfaces intentionally expose the same profile semantics
5. Isolate the still-Proxmox-specific ExtJS runtime coupling in `proxmox-ui/components/extjs-integration.js` further:
   - document and reduce hard-coded selectors/component queries where practical
   - avoid letting new business logic drift back into that component
6. Inventory remaining direct `qm`/`pvesh` usage in scripts and move the first reusable calls behind provider helpers instead of raw subprocess invocations.
7. Align installer-generation/env builders with the same endpoint-profile contract source instead of reshaping overlapping fields in multiple browser/runtime places.
8. Add broader automated checks for the browser extension, Proxmox UI modules, and beagle-host modules beyond syntax and `py_compile`.
9. Keep `09-provider-abstraction.md` current whenever a direct Proxmox dependency is removed or newly discovered.

## After that

1. Add smoke verification for generated installer URLs and expected public artifact names.
2. Begin thin client runtime seam extraction around config, network, pairing, and Moonlight launch.
