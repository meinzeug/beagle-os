# Next Steps

## Immediate next slice

Now that the control plane exposes a normalized endpoint profile contract `v1`, the browser-side VM profile mapper and helper layer are shared, `core/platform/browser-common.js` now carries the first browser-wide token/template/API helper seam, the Proxmox UI entrypoint is down to about `344` lines, the extension entrypoint is down to about `189` lines, the host bootstrap selects `HOST_PROVIDER` through `beagle-host/providers/registry.py`, the script-side provider helper `scripts/lib/beagle_provider.py` is now used by `reconcile-public-streams.sh`, `prepare-host-downloads.sh`, `ensure-vm-stream-ready.sh`, and `install-beagle-proxy.sh`, and the extracted host-service surface now also includes `TimeSupportService`, `RuntimePathsService`, `PersistenceSupportService`, `RequestSupportService`, `RuntimeExecService`, `RuntimeSupportService`, `UbuntuBeagleRestartService`, `EndpointEnrollmentService`, `RuntimeEnvironmentService`, plus the expanded `ActionQueueService` wait loop, `beagle-control-plane.py` is down to about `3276` lines. The host-side extraction track now covers `VirtualizationInventoryService`, `VmStateService`, `VmProfileService`, `DownloadMetadataService`, `UpdateFeedService`, `FleetInventoryService`, `HealthPayloadService`, `InstallerPrepService`, `InstallerScriptService`, `InstallerTemplatePatchService`, `EndpointReportService`, `ActionQueueService`, `PolicyStoreService`, `PolicyNormalizationService`, `SupportBundleStoreService`, `EndpointEnrollmentService`, `UbuntuBeagleInputsService`, `UbuntuBeagleRestartService`, `UbuntuBeagleStateService`, `UbuntuBeagleProvisioningService`, `VmSecretStoreService`, `VmSecretBootstrapService`, `EnrollmentTokenStoreService`, `SunshineAccessTokenStoreService`, `EndpointTokenStoreService`, `VmUsbService`, `SunshineIntegrationService`, `PublicStreamService`, `RuntimeEnvironmentService`, `RuntimeSupportService`, `RuntimeExecService`, `PersistenceSupportService`, `RequestSupportService`, `TimeSupportService`, and `RuntimePathsService`. The next slice should focus on remaining script/provider coupling plus the next host utility extraction while keeping the browser surfaces on the new shared helper seam.

Strategic framing:

- these immediate slices are not only about cleaner Proxmox support
- they are the preparation path toward a first-party Beagle virtualization provider with Proxmox as an optional provider
- the generic host/control-plane surface is now named `beagle-host/`; new work should use that name consistently for repo-internal architecture

### Concrete next tasks

1. Continue migrating script/install surfaces onto the provider-facing helper seam:
   - `scripts/lib/beagle_provider.py` now covers the main reusable read helpers and is already used by four script surfaces; the next step is the remaining raw Proxmox read sites in scripts/installers that still bypass it
   - once the read migration is stable, decide whether a second helper seam is needed for script-side writes/guest-exec without leaking raw `qm` semantics back across multiple scripts
2. Continue decomposing `beagle-host/bin/beagle-control-plane.py` around service-oriented modules:
   - `TimeSupportService` and `RuntimePathsService` now own the shared timestamp and data-root/path seams; the next valuable extraction is the remaining small generic helper cluster around slug/secret formatting and other pure utility helpers that still sit directly in the entrypoint
   - this is now the most coherent remaining non-HTTP utility block because `safe_slug(...)`, `random_secret(...)`, and `random_pin()` still feed multiple extracted services while remaining as free functions in `beagle-control-plane.py`
   - follow the same pattern again: move those pure utility helpers behind a small host utility service, then keep the existing helper names as thin wrappers until the remaining factories consume that seam directly
3. Continue the host-provider abstraction itself:
   - define the next provider-complete contract slice in `beagle-host/providers/host_provider_contract.py` and move any remaining host-side direct provider assumptions to that contract or to service modules consuming it
   - thread `BEAGLE_HOST_PROVIDER` through the deploy/install/runtime docs and prepare the repo for a second provider or mock provider without changing current Proxmox behavior
4. Continue splitting the browser UI action/render layers:
   - move the next action-heavy profile modal helpers out of `extension/components/profile-modal.js` and, where shared, out of `proxmox-ui/components/profile-modal.js`
   - keep using `core/platform/browser-common.js` plus the existing shared browser helper modules instead of recreating token/template/API helpers in entrypoints
5. Isolate the still-Proxmox-specific ExtJS runtime coupling in `proxmox-ui/components/extjs-integration.js` further:
   - document and reduce hard-coded selectors/component queries where practical
   - avoid letting new business logic drift back into that component
6. Follow the runtime-path extraction with the next remaining pure-business helper cluster in the entrypoint, likely the shared slug/secret helper seam first and then the next handler-local response-model blocks that still sit directly in `beagle-control-plane.py`.
7. Align installer-generation/env builders with the same endpoint-profile contract source instead of reshaping overlapping fields in multiple browser/runtime places.
8. Add broader automated checks for the browser extension, Proxmox UI modules, website modules, and beagle-host modules beyond syntax and `py_compile`.
9. Keep `09-provider-abstraction.md` current whenever a direct Proxmox dependency is removed or newly discovered.

## After that

1. Add smoke verification for generated installer URLs and expected public artifact names.
2. Begin thin client runtime seam extraction around config, network, pairing, and Moonlight launch.
