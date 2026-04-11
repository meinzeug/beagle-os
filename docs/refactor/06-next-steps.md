# Next Steps

## Immediate next slice

Now that the control plane exposes a normalized endpoint profile contract `v1`, the browser-side VM profile mapper and helper layer are shared, the Proxmox UI entrypoint is down to about `350` lines, the extension entrypoint is down to about `189` lines, the host bootstrap selects `HOST_PROVIDER` through `beagle-host/providers/registry.py`, the first script-side provider helper exists as `scripts/lib/beagle_provider.py`, and the extracted host-service surface now also includes `TimeSupportService`, `RuntimePathsService`, `PersistenceSupportService`, `RequestSupportService`, `RuntimeExecService`, `RuntimeSupportService`, `UbuntuBeagleRestartService`, `EndpointEnrollmentService`, `RuntimeEnvironmentService`, plus the expanded `ActionQueueService` wait loop, `beagle-control-plane.py` is down to about `3276` lines. The host-side extraction track now covers `VirtualizationInventoryService`, `VmStateService`, `VmProfileService`, `DownloadMetadataService`, `UpdateFeedService`, `FleetInventoryService`, `HealthPayloadService`, `InstallerPrepService`, `InstallerScriptService`, `InstallerTemplatePatchService`, `EndpointReportService`, `ActionQueueService`, `PolicyStoreService`, `PolicyNormalizationService`, `SupportBundleStoreService`, `EndpointEnrollmentService`, `UbuntuBeagleInputsService`, `UbuntuBeagleRestartService`, `UbuntuBeagleStateService`, `UbuntuBeagleProvisioningService`, `VmSecretStoreService`, `VmSecretBootstrapService`, `EnrollmentTokenStoreService`, `SunshineAccessTokenStoreService`, `EndpointTokenStoreService`, `VmUsbService`, `SunshineIntegrationService`, `PublicStreamService`, `RuntimeEnvironmentService`, `RuntimeSupportService`, `RuntimeExecService`, `PersistenceSupportService`, `RequestSupportService`, `TimeSupportService`, and `RuntimePathsService`. The next slice should focus on browser-surface deduplication plus the next wave of script/provider decoupling while continuing to turn the control plane into a real service-composition surface.

Strategic framing:

- these immediate slices are not only about cleaner Proxmox support
- they are the preparation path toward a first-party Beagle virtualization provider with Proxmox as an optional provider
- the generic host/control-plane surface is now named `beagle-host/`; new work should use that name consistently for repo-internal architecture

### Concrete next tasks

1. Reduce duplicated browser-side config/token/API logic across `proxmox-ui/`, `extension/`, and `website/`:
   - now that `proxmox-ui/beagle-ui.js` no longer owns fleet/provisioning orchestration, the next browser-side structural win is to converge repeated token/config/API-path helpers into shared browser modules instead of keeping near-duplicates across the three surfaces
   - keep provider-neutral semantics in shared browser modules and avoid letting website-specific or Proxmox-specific details leak back into entrypoints
2. Continue decomposing `beagle-host/bin/beagle-control-plane.py` around service-oriented modules:
   - `TimeSupportService` and `RuntimePathsService` now own the shared timestamp and data-root/path seams; the next valuable extraction is the remaining small generic helper cluster around slug/secret formatting and other pure utility helpers that still sit directly in the entrypoint
   - this is now the most coherent remaining non-HTTP utility block because `safe_slug(...)`, `random_secret(...)`, and `random_pin()` still feed multiple extracted services while remaining as free functions in `beagle-control-plane.py`
   - follow the same pattern again: move those pure utility helpers behind a small host utility service, then keep the existing helper names as thin wrappers until the remaining factories consume that seam directly
3. Continue the host-provider abstraction itself:
   - define the next provider-complete contract slice in `beagle-host/providers/host_provider_contract.py` and move any remaining host-side direct provider assumptions to that contract or to service modules consuming it
   - thread `BEAGLE_HOST_PROVIDER` through the deploy/install/runtime docs and prepare the repo for a second provider or mock provider without changing current Proxmox behavior
4. Continue migrating script/install surfaces onto the provider-facing helper seam:
   - `scripts/lib/beagle_provider.py` now owns the first reusable read contract; move the next remaining raw `qm` / `pvesh` read sites behind that seam, then decide whether write/guest-exec flows need a second helper boundary
   - keep `09-provider-abstraction.md` aligned with every migrated script surface so future provider work can see which shell/runtime paths are still Proxmox-bound
5. Continue splitting the browser UI action/render layers:
   - move the next action-heavy profile modal helpers out of `extension/components/profile-modal.js` and, where shared, out of `proxmox-ui/components/profile-modal.js`
   - keep the shared browser helper seam under `extension/shared/*` when both browser surfaces intentionally expose the same profile semantics
6. Isolate the still-Proxmox-specific ExtJS runtime coupling in `proxmox-ui/components/extjs-integration.js` further:
   - document and reduce hard-coded selectors/component queries where practical
   - avoid letting new business logic drift back into that component
7. Follow the runtime-path extraction with the next remaining pure-business helper cluster in the entrypoint, likely the shared slug/secret helper seam first and then the next handler-local response-model blocks that still sit directly in `beagle-control-plane.py`.
8. Align installer-generation/env builders with the same endpoint-profile contract source instead of reshaping overlapping fields in multiple browser/runtime places.
9. Add broader automated checks for the browser extension, Proxmox UI modules, website modules, and beagle-host modules beyond syntax and `py_compile`.
10. Keep `09-provider-abstraction.md` current whenever a direct Proxmox dependency is removed or newly discovered.

## After that

1. Add smoke verification for generated installer URLs and expected public artifact names.
2. Begin thin client runtime seam extraction around config, network, pairing, and Moonlight launch.
