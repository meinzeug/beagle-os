# Next Steps

## Immediate next slice

Now that the control plane exposes a normalized endpoint profile contract `v1`, the browser-side VM profile mapper and helper layer are shared, `core/platform/browser-common.js` now carries the first browser-wide token/template/API helper seam, the Proxmox UI entrypoint is down to about `344` lines, the extension entrypoint is down to about `189` lines, the host bootstrap selects `HOST_PROVIDER` through `beagle-host/providers/registry.py`, the script-side provider helper `scripts/lib/beagle_provider.py` is now used by `reconcile-public-streams.sh`, `prepare-host-downloads.sh`, `ensure-vm-stream-ready.sh`, and `install-beagle-proxy.sh`, and the extracted host-service surface now also includes `UtilitySupportService`, `TimeSupportService`, `RuntimePathsService`, `PersistenceSupportService`, `RequestSupportService`, `RuntimeExecService`, `RuntimeSupportService`, `UbuntuBeagleRestartService`, `EndpointEnrollmentService`, `RuntimeEnvironmentService`, plus the expanded `ActionQueueService` wait loop, `beagle-control-plane.py` sits at about `3283` lines. The host-side extraction track now covers `VirtualizationInventoryService`, `VmStateService`, `VmProfileService`, `DownloadMetadataService`, `UpdateFeedService`, `FleetInventoryService`, `HealthPayloadService`, `InstallerPrepService`, `InstallerScriptService`, `InstallerTemplatePatchService`, `EndpointReportService`, `ActionQueueService`, `PolicyStoreService`, `PolicyNormalizationService`, `SupportBundleStoreService`, `EndpointEnrollmentService`, `UbuntuBeagleInputsService`, `UbuntuBeagleRestartService`, `UbuntuBeagleStateService`, `UbuntuBeagleProvisioningService`, `VmSecretStoreService`, `VmSecretBootstrapService`, `EnrollmentTokenStoreService`, `SunshineAccessTokenStoreService`, `EndpointTokenStoreService`, `VmUsbService`, `SunshineIntegrationService`, `PublicStreamService`, `RuntimeEnvironmentService`, `RuntimeSupportService`, `RuntimeExecService`, `PersistenceSupportService`, `RequestSupportService`, `TimeSupportService`, `RuntimePathsService`, and `UtilitySupportService`. The next slice should focus on the remaining script/provider couplings, installer-contract drift, and the next provider-complete contract definition while keeping browser surfaces on the new shared helper seam.

Strategic framing:

- these immediate slices are not only about cleaner Proxmox support
- they are the preparation path toward a first-party Beagle virtualization provider with Proxmox as an optional provider
- the generic host/control-plane surface is now named `beagle-host/`; new work should use that name consistently for repo-internal architecture

### Concrete next tasks

1. Continue migrating script/install surfaces onto the provider-facing helper seam:
   - `scripts/lib/beagle_provider.py` now covers the first shared guest-exec/write commands too, and the main script surfaces already prefer that seam
   - the next script task is to reduce the remaining direct-command fallback paths where rollout compatibility is no longer needed and to migrate any still-unreached write flows onto the same seam
   - after that, decide whether this helper remains the long-term script provider contract or whether the write/exec slice should split into a second dedicated script-side provider module
2. Continue decomposing `beagle-host/bin/beagle-control-plane.py` around service-oriented modules:
   - the shared slug/secret/PIN helper cluster is now extracted behind `UtilitySupportService`
   - the next valuable host slice is a larger handler-local business block or response-model cluster that still sits directly in `beagle-control-plane.py`, not another tiny utility
   - keep the entrypoint moving toward a thin HTTP composition surface instead of re-centralizing orchestration there
3. Continue the host-provider abstraction itself:
   - define the next provider-complete contract slice in `beagle-host/providers/host_provider_contract.py` and move any remaining host-side direct provider assumptions to that contract or to service modules consuming it
   - thread `BEAGLE_HOST_PROVIDER` through the deploy/install/runtime docs and prepare the repo for a second provider or mock provider without changing current Proxmox behavior
4. Align installer-generation/env builders with the same endpoint profile contract source instead of reshaping overlapping fields in multiple browser/runtime places.
5. Continue splitting the browser UI action/render layers:
   - move the next action-heavy profile modal helpers out of `extension/components/profile-modal.js` and, where shared, out of `proxmox-ui/components/profile-modal.js`
   - keep using `core/platform/browser-common.js` plus the existing shared browser helper modules instead of recreating token/template/API helpers in entrypoints
6. Isolate the still-Proxmox-specific ExtJS runtime coupling in `proxmox-ui/components/extjs-integration.js` further:
   - document and reduce hard-coded selectors/component queries where practical
   - avoid letting new business logic drift back into that component
7. Add broader automated checks for the browser extension, Proxmox UI modules, website modules, and beagle-host modules beyond syntax and `py_compile`.
8. Keep `09-provider-abstraction.md` current whenever a direct Proxmox dependency is removed or newly discovered.

## After that

1. Add smoke verification for generated installer URLs and expected public artifact names.
2. Begin thin client runtime seam extraction around config, network, pairing, and Moonlight launch.
