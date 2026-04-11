# Next Steps

## Immediate next slice

Now that the control plane exposes a normalized endpoint profile contract `v1`, the browser-side VM profile mapper and helper layer are shared, the Proxmox UI entrypoint is down to about 410 lines, the extension entrypoint is down to about 189 lines, the host-side read/state/profile/USB seams exist under `beagle-host/services/`, the host bootstrap now selects `HOST_PROVIDER` through `beagle-host/providers/registry.py`, and the next batch of host services (`UpdateFeedService`, `FleetInventoryService`, `HealthPayloadService`, `InstallerPrepService`, `InstallerScriptService`, `EndpointReportService`, `ActionQueueService`, `PolicyStoreService`, `SupportBundleStoreService`, `UbuntuBeagleStateService`, `VmSecretStoreService`, `VmSecretBootstrapService`, `EnrollmentTokenStoreService`, `SunshineAccessTokenStoreService`, `EndpointTokenStoreService`, `DownloadMetadataService`, `VmUsbService`) has been pulled out of `beagle-control-plane.py` (now around `4701` lines, with persistence-layer helpers, token stores, public download/artifact metadata, VM-secret credential/bootstrap orchestration, installer-prep Sunshine-readiness logic, and guest USB attach/detach state all behind dedicated seams), the next slice should keep shrinking `beagle-ui.js` while turning the control plane into a real service composition surface and making the host-provider contract more complete.

Strategic framing:

- these immediate slices are not only about cleaner Proxmox support
- they are the preparation path toward a first-party Beagle virtualization provider with Proxmox as an optional provider
- the generic host/control-plane surface is now named `beagle-host/`; new work should use that name consistently for repo-internal architecture

### Concrete next tasks

1. Continue splitting `proxmox-ui/beagle-ui.js`:
   - extract the remaining fleet/profile launch orchestration and dependency-composition wrappers into dedicated modules under `proxmox-ui/components/` and `proxmox-ui/state/`
   - after `modal-shell.js`, `extjs-integration.js`, and the modal renderers are out, the remaining file should converge on dependency lookup plus a small `boot()` entrypoint
2. Continue decomposing `beagle-host/bin/beagle-control-plane.py` around service-oriented modules:
   - `UpdateFeedService`, `FleetInventoryService`, `HealthPayloadService`, `InstallerPrepService`, `InstallerScriptService`, `EndpointReportService`, `ActionQueueService`, `PolicyStoreService`, `SupportBundleStoreService`, `UbuntuBeagleStateService`, `VmSecretStoreService`, `VmSecretBootstrapService`, `EnrollmentTokenStoreService`, `SunshineAccessTokenStoreService`, `EndpointTokenStoreService`, `DownloadMetadataService`, and `VmUsbService` are now out; the next valuable extraction is the Ubuntu-Beagle provisioning/lifecycle cluster (`build_provisioning_catalog`, `ensure_ubuntu_beagle_iso_cached`, `build_ubuntu_beagle_description`, `build_ubuntu_beagle_seed_iso`, `finalize_ubuntu_beagle_install`, `prepare_ubuntu_beagle_firstboot`, `create_ubuntu_beagle_vm`, and `update_ubuntu_beagle_vm`)
   - after the USB cluster moved out, the Ubuntu-Beagle provisioning block is the highest-signal remaining non-HTTP area because it still mixes provider-backed VM lifecycle operations, autoinstall artifact generation, state shaping, and provisioning-specific defaults in the control-plane entrypoint
   - this should follow the same pattern: a dedicated `beagle-host/services/*.py` module with a class that receives its collaborators (provider-backed VM operations, template paths, JSON/file helpers, password/slug helpers, and timing helpers) through the constructor, plus a lazily-initialized factory in `beagle-control-plane.py` that keeps wrapper signatures stable
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
