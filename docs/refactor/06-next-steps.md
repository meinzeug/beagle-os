# Next Steps

## Immediate next slice

Now that the control plane exposes a normalized endpoint profile contract `v1`, the browser-side VM profile mapper and helper layer are shared, the Proxmox UI entrypoint is down to about 410 lines, the extension entrypoint is down to about 189 lines, the host bootstrap selects `HOST_PROVIDER` through `beagle-host/providers/registry.py`, and the extracted host-service surface now also includes `PersistenceSupportService`, `RequestSupportService`, `RuntimeExecService`, `RuntimeSupportService`, `UbuntuBeagleRestartService`, `EndpointEnrollmentService`, `RuntimeEnvironmentService`, plus the expanded `ActionQueueService` wait loop, `beagle-control-plane.py` is down to about `3293` lines. The host-side extraction track now covers `VirtualizationInventoryService`, `VmStateService`, `VmProfileService`, `DownloadMetadataService`, `UpdateFeedService`, `FleetInventoryService`, `HealthPayloadService`, `InstallerPrepService`, `InstallerScriptService`, `InstallerTemplatePatchService`, `EndpointReportService`, `ActionQueueService`, `PolicyStoreService`, `PolicyNormalizationService`, `SupportBundleStoreService`, `EndpointEnrollmentService`, `UbuntuBeagleInputsService`, `UbuntuBeagleRestartService`, `UbuntuBeagleStateService`, `UbuntuBeagleProvisioningService`, `VmSecretStoreService`, `VmSecretBootstrapService`, `EnrollmentTokenStoreService`, `SunshineAccessTokenStoreService`, `EndpointTokenStoreService`, `VmUsbService`, `SunshineIntegrationService`, `PublicStreamService`, `RuntimeEnvironmentService`, `RuntimeSupportService`, `RuntimeExecService`, `PersistenceSupportService`, and `RequestSupportService`. The next slice should keep shrinking `beagle-ui.js` while continuing to turn the control plane into a real service-composition surface and completing the provider-neutral host boundary.

Strategic framing:

- these immediate slices are not only about cleaner Proxmox support
- they are the preparation path toward a first-party Beagle virtualization provider with Proxmox as an optional provider
- the generic host/control-plane surface is now named `beagle-host/`; new work should use that name consistently for repo-internal architecture

### Concrete next tasks

1. Continue splitting `proxmox-ui/beagle-ui.js`:
   - extract the remaining fleet/profile launch orchestration and dependency-composition wrappers into dedicated modules under `proxmox-ui/components/` and `proxmox-ui/state/`
   - after `modal-shell.js`, `extjs-integration.js`, and the modal renderers are out, the remaining file should converge on dependency lookup plus a small `boot()` entrypoint
2. Continue decomposing `beagle-host/bin/beagle-control-plane.py` around service-oriented modules:
   - `PersistenceSupportService` and `RequestSupportService` now own the shared file/JSON and request/origin helper seams; the next valuable extraction is the remaining small generic runtime/HTTP utility block around directory/bootstrap helpers such as `ensure_data_dir()` and the related path/bootstrap wrappers that still live inline in the entrypoint
   - this is now the most coherent remaining non-HTTP utility block because it still centralizes runtime bootstrap behavior in `beagle-control-plane.py` while many extracted services already depend on the directories and state roots it establishes
   - follow the same pattern again: move the remaining generic bootstrap/path helpers behind a small host runtime-path or data-root service, then keep the existing helper names as thin wrappers until the factories consume that seam directly
3. Continue the host-provider abstraction itself:
   - define the next provider-complete contract slice in `beagle-host/providers/host_provider_contract.py` and move any remaining host-side direct provider assumptions to that contract or to service modules consuming it
   - thread `BEAGLE_HOST_PROVIDER` through the deploy/install/runtime docs and prepare the repo for a second provider or mock provider without changing current Proxmox behavior
4. Continue splitting the browser UI action/render layers:
   - move the next action-heavy profile modal helpers out of `extension/components/profile-modal.js` and, where shared, out of `proxmox-ui/components/profile-modal.js`
   - keep the shared browser helper seam under `extension/shared/*` when both browser surfaces intentionally expose the same profile semantics
5. Isolate the still-Proxmox-specific ExtJS runtime coupling in `proxmox-ui/components/extjs-integration.js` further:
   - document and reduce hard-coded selectors/component queries where practical
   - avoid letting new business logic drift back into that component
6. Follow the request-support extraction with the next remaining pure-business helper cluster in the entrypoint, likely the shared data-root/bootstrap helpers first and then the next handler-local response-model blocks that still sit directly in `beagle-control-plane.py`.
7. Inventory remaining direct `qm`/`pvesh` usage in scripts and move the first reusable calls behind provider helpers instead of raw subprocess invocations.
8. Align installer-generation/env builders with the same endpoint-profile contract source instead of reshaping overlapping fields in multiple browser/runtime places.
9. Add broader automated checks for the browser extension, Proxmox UI modules, and beagle-host modules beyond syntax and `py_compile`.
10. Keep `09-provider-abstraction.md` current whenever a direct Proxmox dependency is removed or newly discovered.

## After that

1. Add smoke verification for generated installer URLs and expected public artifact names.
2. Begin thin client runtime seam extraction around config, network, pairing, and Moonlight launch.
