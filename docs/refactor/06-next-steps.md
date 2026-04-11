# Next Steps

## Immediate next slice


Strategic framing:

- these immediate slices are not only about cleaner Proxmox support
- they are the preparation path toward a first-party Beagle virtualization provider with Proxmox as an optional provider
- the generic host/control-plane surface is now named `beagle-host/`; new work should use that name consistently for repo-internal architecture

### Concrete next tasks

1. Continue migrating script/install surfaces onto the provider-facing helper seam:
   - `scripts/lib/beagle_provider.py` now covers synchronous guest-exec plus the first shared write commands, and the main Sunshine/setup scripts already prefer that seam
   - `scripts/lib/provider_shell.sh` now covers shared provider-helper discovery, local-vs-remote host dispatch, remote helper execution, and last-JSON-object parsing for the main shell scripts
   - `scripts/lib/prepare_host_downloads.py` now owns the large non-shell artifact patching and VM installer metadata/status block that used to live inline in `prepare-host-downloads.sh`
   - the next script task is to reduce the remaining direct-command fallback paths where rollout compatibility is no longer needed, especially the last compatibility branches in `configure-sunshine-guest.sh`, `ensure-vm-stream-ready.sh`, and `optimize-proxmox-vm-for-beagle.sh`
   - after that, reuse the new shell seam in the next provider-aware scripts that still duplicate host targeting or helper bootstrap logic instead of reintroducing those helpers locally
   - the generic top-level host install/setup/check/service entrypoints now live at `scripts/install-beagle-host.sh`, `scripts/install-beagle-host-services.sh`, `scripts/setup-beagle-host.sh`, and `scripts/check-beagle-host.sh`
   - the server-installer now has explicit provider dispatch seams for repo wiring, package installation, and the final Beagle host bootstrap; the next installer slice is to move the remaining Proxmox-only package/source definitions and post-install assumptions behind the same seam instead of keeping them inline as the only implementation
   - after that, decide whether this helper remains the long-term script provider contract or whether the write/exec slice should split into a second dedicated script-side provider module
2. Continue decomposing `beagle-host/bin/beagle-control-plane.py` around service-oriented modules:
   - the shared slug/secret/PIN helper cluster is now extracted behind `UtilitySupportService`
   - the shared description-meta/hostname helper cluster is now extracted behind `MetadataSupportService`
   - the inline `/api/v1/vms/...` GET response-model block now lives behind `VmHttpSurfaceService`
   - the non-VM read cluster for provisioning/catalog, endpoints, policies, and support-bundle downloads now lives behind `ControlPlaneReadSurfaceService`
   - the public VM state/endpoint surface plus endpoint-authenticated `/api/v1/endpoints/update-feed` now live behind `PublicHttpSurfaceService`
   - the public ubuntu-install lifecycle POST surface now lives behind `PublicUbuntuInstallSurfaceService`
   - the endpoint-authenticated Moonlight registration, action pull/result, and support-bundle-upload POST surface now lives behind `EndpointHttpSurfaceService`
   - the public Sunshine GET/POST proxy surface now lives behind `PublicSunshineSurfaceService`
   - the authenticated single-VM mutation surface for installer-prep, updates, actions, USB attach/detach, and Sunshine access now lives behind `VmMutationSurfaceService`
   - the authenticated non-VM admin mutation surface for policies, bulk actions, ubuntu-beagle create/provision/update now lives behind `AdminHttpSurfaceService`
   - the endpoint enrollment/check-in HTTP surface now lives behind `EndpointLifecycleSurfaceService`
   - the next valuable host slice is no longer another HTTP route block; it is the remaining non-HTTP orchestration/business helper cluster that still sits directly in `beagle-control-plane.py`
   - keep the entrypoint moving toward a thin HTTP composition surface instead of re-centralizing orchestration there
3. Continue the host-provider abstraction itself:
   - define the next provider-complete contract slice in `beagle-host/providers/host_provider_contract.py` and move any remaining host-side direct provider assumptions to that contract or to service modules consuming it
   - `BEAGLE_HOST_PROVIDER` now reaches `host.env`, `beagle-manager.env`, refresh paths, post-install checks, the proxy installer, the Proxmox-UI integration path, and the server-installer bootstrap; the next deploy task is to reduce the remaining Proxmox-only behavior at those surfaces rather than just carrying the variable through them
4. Continue aligning installer-generation/env builders with the same endpoint profile contract source instead of reshaping overlapping fields in multiple browser/runtime places:
   - the hosted VM installer catalog path in `scripts/lib/prepare_host_downloads.py` now normalizes overlapping installer/profile URLs through `endpoint_profile_contract.py`
   - the thin-client preset summary/UI-state path now shares one helper in `thin-client-assistant/usb/preset_summary.py` instead of carrying duplicated mode/preset shaping in both the local installer and the Proxmox API helper
   - the Proxmox-specific USB preset builder now lives in `thin-client-assistant/usb/proxmox_preset.py` instead of staying embedded in `pve-thin-client-proxmox-api.py`
   - the runtime enrollment config write path now also has an explicit helper in `thin-client-assistant/runtime/apply_enrollment_config.py` instead of an inline Python block inside `prepare-runtime.sh`
   - the runtime status write path now also shares one helper in `thin-client-assistant/runtime/status_writer.py` instead of two separate shell/inline-JSON implementations
   - the preset→runtime config generation path now also has an explicit helper in `thin-client-assistant/runtime/generate_config_from_preset.py` instead of a large inline export block in `common.sh`
   - the shared preset-base drift between `thin-client-assistant/usb/proxmox_preset.py` and `beagle-host/services/installer_script.py` now lives behind `beagle-host/services/thin_client_preset.py`
   - the shared installer/runtime default literals now live behind `thin-client-assistant/installer/env-defaults.json` plus `env-defaults.sh`
   - the runtime mode/cmdline override mapping now lives behind `thin-client-assistant/runtime/mode_overrides.py`
   - the runtime live-state/preset/config discovery logic now lives behind `thin-client-assistant/runtime/config_discovery.py`
   - the runtime preset-driven config generation and config file loading now live behind `thin-client-assistant/runtime/config_loader.sh`
   - the runtime baseline for user/group/home/uid lookup, Beagle state/logging, privileged commands, and live-medium discovery now lives behind `thin-client-assistant/runtime/runtime_core.sh`
   - the runtime TLS/template/browser-flag helper contract now lives behind `thin-client-assistant/runtime/runtime_value_helpers.sh`
   - the runtime X11/Xauthority display-selection and display-wait logic now lives behind `thin-client-assistant/runtime/x11_display.sh`
   - the runtime network config-file / NetworkManager profile / resolver-writing logic now lives behind `thin-client-assistant/runtime/runtime_network_config_files.sh`
   - the Moonlight host/local-host/API-url/IPv4 preference and target reachability logic now lives behind `thin-client-assistant/runtime/moonlight_targeting.sh`
   - the Sunshine API URL rewrite / selection logic now also lives behind `thin-client-assistant/runtime/moonlight_api_url.sh`
   - the Moonlight host-registry config mutation/detection logic now lives behind `thin-client-assistant/runtime/moonlight_host_registry.py`
   - the Moonlight pairing/bootstrap/config-sync logic now lives behind `thin-client-assistant/runtime/moonlight_pairing.sh`
   - the runtime streaming-session persistence and active-session detection now live behind `thin-client-assistant/runtime/stream_state.sh`
   - the runtime management timer/service suspension and resume orchestration now live behind `thin-client-assistant/runtime/stream_management_activity.sh`
   - the runtime local `usbipd` lifecycle and bound-device resync logic now live behind `thin-client-assistant/runtime/beagle_usb_runtime_usbipd.sh`
   - the GeForce NOW `xdg-open` wrapper and host-shim logic now live behind `thin-client-assistant/runtime/geforcenow_xdg_open_integration.sh`
   - the X11 Xauthority discovery and display-readiness selection logic now live behind `thin-client-assistant/runtime/x11_display_selection.sh`
   - the Beagle runtime state-path, trace, marker, and log-event logic now live behind `thin-client-assistant/runtime/runtime_beagle_state.sh`
   - the runtime systemd timer/service activation and USB tunnel unit control now live behind `thin-client-assistant/runtime/runtime_systemd_units.sh`
   - the USB tunnel/env and command accessor logic now lives behind `thin-client-assistant/runtime/beagle_usb_runtime_env.sh`
   - the Moonlight IPv4/preferred-host resolution logic now lives behind `thin-client-assistant/runtime/moonlight_host_resolution.sh`
   - the generic runtime-owned path helpers now live behind `thin-client-assistant/runtime/runtime_fs_ownership.sh`
   - the GeForce NOW storage/home/cache/config environment prep now lives behind `thin-client-assistant/runtime/geforcenow_storage_environment.sh`
   - the runtime kiosk process-pattern and stop-control block now lives behind `thin-client-assistant/runtime/kiosk_runtime.sh`
   - the runtime kiosk supervisor/relaunch loop now lives behind `thin-client-assistant/runtime/session_launcher.sh`
   - the USB tunnel-status and inventory/list/status payload shaping now live behind `thin-client-assistant/runtime/beagle_usb_runtime_payloads.sh`
   - the next remaining drift is in the host-only vs USB-only preset delta fields and in the remaining runtime orchestration around the now-thin prepare/network/pairing/USB/GFN-install wrappers, especially the next substantial runtime helper now that the Moonlight remote-API layer, the Moonlight API-URL layer, the Moonlight execution layer, the GFN stream-optimization layer, the USB payload layer, and the SSH/bootstrap layer have all been reduced to focused helper seams
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
2. Continue thin client runtime work from the now-thin `prepare-runtime.sh`, `apply-network-config.sh`, `moonlight_pairing.sh`, `beagle-usbctl.sh`, and `install-geforcenow.sh` entrypoints by selecting the next shell-heavy runtime/helper module, most likely one of the install/runtime crossover scripts or the next shared runtime helper with duplicated accessors.
