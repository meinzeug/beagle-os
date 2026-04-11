# Next Steps

## Immediate next slice

Now that the control plane exposes a normalized endpoint profile contract `v1`, the browser-side VM profile mapper and helper layer are shared, the Proxmox UI entrypoint is down to about 410 lines, the extension entrypoint is down to about 189 lines, the host bootstrap selects `HOST_PROVIDER` through `beagle-host/providers/registry.py`, and the extracted host-service surface now also includes `EndpointEnrollmentService`, `RuntimeEnvironmentService`, plus the expanded `ActionQueueService` wait loop, `beagle-control-plane.py` is down to about `3370` lines. The host-side extraction track now covers `VirtualizationInventoryService`, `VmStateService`, `VmProfileService`, `DownloadMetadataService`, `UpdateFeedService`, `FleetInventoryService`, `HealthPayloadService`, `InstallerPrepService`, `InstallerScriptService`, `InstallerTemplatePatchService`, `EndpointReportService`, `ActionQueueService`, `PolicyStoreService`, `PolicyNormalizationService`, `SupportBundleStoreService`, `EndpointEnrollmentService`, `UbuntuBeagleInputsService`, `UbuntuBeagleStateService`, `UbuntuBeagleProvisioningService`, `VmSecretStoreService`, `VmSecretBootstrapService`, `EnrollmentTokenStoreService`, `SunshineAccessTokenStoreService`, `EndpointTokenStoreService`, `VmUsbService`, `SunshineIntegrationService`, `PublicStreamService`, and `RuntimeEnvironmentService`. The next slice should keep shrinking `beagle-ui.js` while continuing to turn the control plane into a real service-composition surface and completing the provider-neutral host boundary.

Strategic framing:

- these immediate slices are not only about cleaner Proxmox support
- they are the preparation path toward a first-party Beagle virtualization provider with Proxmox as an optional provider
- the generic host/control-plane surface is now named `beagle-host/`; new work should use that name consistently for repo-internal architecture

### Concrete next tasks

1. Continue splitting `proxmox-ui/beagle-ui.js`:
   - extract the remaining fleet/profile launch orchestration and dependency-composition wrappers into dedicated modules under `proxmox-ui/components/` and `proxmox-ui/state/`
   - after `modal-shell.js`, `extjs-integration.js`, and the modal renderers are out, the remaining file should converge on dependency lookup plus a small `boot()` entrypoint
2. Continue decomposing `beagle-host/bin/beagle-control-plane.py` around service-oriented modules:
   - `EndpointEnrollmentService` now owns installer enrollment-token issuance and `/api/v1/endpoints/enroll` bootstrap payload shaping; the next valuable extraction is the scheduled-restart cancellation/state helper cluster around `cancel_scheduled_ubuntu_beagle_vm_restart(...)`
   - this is now the most coherent remaining non-HTTP business block because restart-state cleanup and signal/process-group handling still live inline in the entrypoint while the ubuntu-beagle provisioning flow already depends on the result shape
   - follow the same pattern again: move restart-cancel/state cleanup behind a small host service, keep the existing helper names as thin wrappers during migration, and only then simplify the handler/provisioning call sites
3. Continue the host-provider abstraction itself:
   - define the next provider-complete contract slice in `beagle-host/providers/host_provider_contract.py` and move any remaining host-side direct provider assumptions to that contract or to service modules consuming it
   - thread `BEAGLE_HOST_PROVIDER` through the deploy/install/runtime docs and prepare the repo for a second provider or mock provider without changing current Proxmox behavior
4. Continue splitting the browser UI action/render layers:
   - move the next action-heavy profile modal helpers out of `extension/components/profile-modal.js` and, where shared, out of `proxmox-ui/components/profile-modal.js`
   - keep the shared browser helper seam under `extension/shared/*` when both browser surfaces intentionally expose the same profile semantics
5. Isolate the still-Proxmox-specific ExtJS runtime coupling in `proxmox-ui/components/extjs-integration.js` further:
   - document and reduce hard-coded selectors/component queries where practical
   - avoid letting new business logic drift back into that component
6. Follow the restart-cancel/state extraction with the next remaining pure-business helper cluster in the entrypoint, likely the remaining environment/cache utility seams such as `cache_get` / `cache_put` or shell-env parsing that still sit directly in `beagle-control-plane.py`.
7. Inventory remaining direct `qm`/`pvesh` usage in scripts and move the first reusable calls behind provider helpers instead of raw subprocess invocations.
8. Align installer-generation/env builders with the same endpoint-profile contract source instead of reshaping overlapping fields in multiple browser/runtime places.
9. Add broader automated checks for the browser extension, Proxmox UI modules, and beagle-host modules beyond syntax and `py_compile`.
10. Keep `09-provider-abstraction.md` current whenever a direct Proxmox dependency is removed or newly discovered.

## After that

1. Add smoke verification for generated installer URLs and expected public artifact names.
2. Begin thin client runtime seam extraction around config, network, pairing, and Moonlight launch.
