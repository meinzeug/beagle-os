# Next Steps

## Immediate next slice


Strategic framing:

- these immediate slices are not only about cleaner Proxmox support
- they are the preparation path toward a first-party Beagle virtualization provider with Proxmox as an optional provider
- the generic host/control-plane surface is now named `beagle-host/`; new work should use that name consistently for repo-internal architecture
- the target server installer must explicitly support both `Beagle OS standalone` and `Beagle OS with Proxmox`
- the target host UI is a Beagle Web Console, not the permanent continuation of `proxmox-ui/`

### Concrete next tasks

1. Continue migrating script/install surfaces onto the provider-facing helper seam:
   - `scripts/lib/beagle_provider.py` now delegates through `beagle-host/providers/registry.py` instead of being a second hidden Proxmox client, and it now exposes provider-backed `next-vmid`, node/storage inventory, guest-network, guest-exec, description, and reboot helpers
   - `scripts/lib/provider_shell.sh` now covers shared provider-helper discovery, local-vs-remote host dispatch, remote helper execution, last-JSON-object parsing, and the shared guest-exec / guest-ipv4 / description / reboot / `qm set` fallback wrappers for the main shell scripts
   - `scripts/lib/prepare_host_downloads.py` now owns the large non-shell artifact patching and VM installer metadata/status block that used to live inline in `prepare-host-downloads.sh`
   - the next script task is to reduce the remaining direct-command fallback paths where rollout compatibility is no longer needed, especially the last compatibility branches still surrounding guest script upload / metadata mutation flows and any remaining raw command paths outside `provider_shell.sh`
   - after that, decide whether `provider_shell.sh` should start consuming the new `list-nodes` / `list-storage` / `next-vmid` commands as well, so future script-side provider work does not create a third contract surface
   - after that, reuse the new shell seam in the next provider-aware scripts that still duplicate host targeting or helper bootstrap logic instead of reintroducing those helpers locally
   - the generic top-level host install/setup/check/service entrypoints now live at `scripts/install-beagle-host.sh`, `scripts/install-beagle-host-services.sh`, `scripts/setup-beagle-host.sh`, and `scripts/check-beagle-host.sh`
   - the server-installer now exposes explicit install modes for:
     - `Beagle OS standalone`
     - `Beagle OS with Proxmox`
   - the next installer slice is to move the remaining standalone-vs-Proxmox post-install assumptions behind the same seam, especially host validation, proxy/web UI setup expectations, and any remaining package/layout assumptions that still silently prefer the Proxmox path
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
   - the first real `beagle` provider now exists in `beagle-host/providers/beagle_host_provider.py`; the next provider slice is to stop treating it as only a persistence skeleton
   - extend the host provider contract and the Beagle skeleton together for the next missing surfaces: bridge inventory, network inventory, guest-script upload/result handling, and restart scheduling semantics that are still Proxmox-shaped in adjacent helpers
   - add the first provider-neutral HTTP read surface for nodes/hosts and guest interfaces so `providers/beagle/virtualization-provider.js` no longer has to synthesize those values from `/api/v1/vms` alone
   - keep the control-plane entrypoint moving toward a thin HTTP composition surface instead of re-centralizing orchestration there
3. Continue the host-provider abstraction itself:
   - define the next provider-complete contract slice in `beagle-host/providers/host_provider_contract.py` after the new state-backed `beagle` skeleton and move any remaining host-side direct provider assumptions to that contract or to service modules consuming it
   - the next high-value contract candidates are host-network/bridge inventory, guest-script upload/result handling, and the remaining restart scheduling assumptions that still leak around `provider_shell.sh`
   - `BEAGLE_HOST_PROVIDER` now reaches `host.env`, `beagle-manager.env`, refresh paths, post-install checks, the proxy installer, the Proxmox-UI integration path, and the server-installer bootstrap; the next deploy task is to reduce the remaining Proxmox-only behavior at those surfaces rather than just carrying the variable through them
   - after that, define which standalone host/bootstrap/network/storage/runtime responsibilities are Beagle-core and therefore must exist identically in both installer modes
   - after that, define the first standalone-capable host contract for local downloads/public proxying/web console delivery, because standalone currently validates through the local control-plane port but does not yet have an equivalent long-term web surface to the Proxmox-backed host
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
   - the shared USB manifest project-version read/write, install-manifest/USB-manifest JSON shaping, and payload-source validation now live behind `thin-client-assistant/usb/usb_manifest.py`
   - the shared live-medium asset/manifest path detection, live-device candidate discovery, live-mount candidate discovery, and shared candidate mount/umount loop now also live behind `thin-client-assistant/usb/live_medium_helpers.sh`
   - the local-installer payload download/fallback and install-manifest write path now also lives behind `thin-client-assistant/usb/install_payload_assets.sh`
   - the USB writer source-selection and variant-path plan logic now also lives behind `thin-client-assistant/usb/usb_writer_sources.sh`
   - the USB writer bootstrap unpacking, ISO download/cache, and live-asset validation now also live behind `thin-client-assistant/usb/usb_writer_bootstrap.sh`
   - the USB writer partition/write/copy/GRUB/runtime-state stage now also lives behind `thin-client-assistant/usb/usb_writer_write_stage.sh`
   - the runtime kiosk process-pattern and stop-control block now lives behind `thin-client-assistant/runtime/kiosk_runtime.sh`
   - the runtime kiosk supervisor/relaunch loop now lives behind `thin-client-assistant/runtime/session_launcher.sh`
   - the USB tunnel-status and inventory/list/status payload shaping now live behind `thin-client-assistant/runtime/beagle_usb_runtime_payloads.sh`
   - the USB writer device-selection/safety/operator-dialog path now also lives behind `thin-client-assistant/usb/usb_writer_device_selection.sh`
   - the hosted-installer artifact-source split for host-local downloads vs public release artifacts now lives behind `scripts/lib/hosted_download_layout.sh`
   - the shared extended runtime preset field set for host-generated and USB-generated presets now lives behind `beagle-host/services/thin_client_preset.py`
   - the mounted-content acceptance rules for live-medium detection, preset detection, and log-persistence roots now also live behind `thin-client-assistant/usb/live_medium_helpers.sh`
   - the next remaining drift is now in the still-host-only secret/enrollment/guest-identity sourcing around the shared preset contract
5. Continue splitting the browser UI action/render layers:
   - move the next action-heavy profile modal helpers out of `extension/components/profile-modal.js` and, where shared, out of `proxmox-ui/components/profile-modal.js`
   - keep using `core/platform/browser-common.js` plus the existing shared browser helper modules instead of recreating token/template/API helpers in entrypoints

6. Start the dedicated Beagle Web Console plan as its own architecture/workstream instead of only continuing the Proxmox UI cleanup:
   - define the repo/module root for the long-term host UI surface
   - define the minimum contracts it needs from `beagle-host` for dashboard, host/node inventory, VM list/detail, storage/network inventory, lifecycle actions, provisioning, installer downloads, and fleet status
   - keep extracting reusable browser/core helpers from `proxmox-ui/` only if they are genuinely reusable by the future Beagle Web Console

7. Isolate the still-Proxmox-specific ExtJS runtime coupling in `proxmox-ui/components/extjs-integration.js` further:
   - document and reduce hard-coded selectors/component queries where practical
   - avoid letting new business logic drift back into that component
8. Add broader automated checks for the browser extension, Proxmox UI modules, website modules, and beagle-host modules beyond syntax and `py_compile`.
9. Keep `09-provider-abstraction.md` current whenever a direct Proxmox dependency is removed or newly discovered.

10. Turn the new Beagle provider skeleton into the first usable Beagle backend scaffold instead of leaving it as an isolated state store:
   - define the minimal persisted state contract under `/var/lib/beagle/providers/beagle` for nodes, storage, VMs, guest interfaces, and action/runtime status
   - decide which lifecycle operations should stay synchronous state mutation in the skeleton and which should already move behind background job records
   - add one conformance-style smoke test that exercises the same CRUD/lifecycle expectations against both `proxmox` and `beagle` provider kinds where possible
   - define which host/runtime/network/storage seams this scaffold must own before `Beagle OS standalone` can be considered a real supported install mode

11. Propagate the Moonlight fast-path launch fix into the actual thin-client release/update path and verify it on a live endpoint:
   - rebuild or stage a thin-client payload/image that includes the updated `thin-client-assistant/runtime/launch-moonlight.sh`
   - deploy that payload to a live endpoint such as `192.168.178.92`
   - confirm from `runtime-trace.log` that already paired clients log `moonlight.ready` and go from `moonlight.cached-config` directly to `moonlight.exec` without the extra `moonlight.registered` pause
   - keep the fallback manager-registration/pairing path covered for unpaired clients

12. After the live runtime verification, continue the next runtime-heavy refactor slice from the same area instead of switching context:
   - either split the remaining non-trivial Moonlight fallback/pairing logic further
   - or move on to the next shell-heavy runtime crossover script that still mixes orchestration and implementation
   - the Moonlight CLI/timeout seam now already lives in `thin-client-assistant/runtime/moonlight_cli.sh`, so the next Moonlight slice should target the remaining recovery-specific business logic instead of reintroducing CLI wrappers elsewhere

13. Keep the host-download USB installer surface stable while continuing USB refactors:
   - regenerate and verify the hosted `pve-thin-client-usb-installer-*.sh` artifacts after the self-bootstrap and host-local artifact-URL fixes so fresh downloads no longer assume a local repo checkout or an external public update bucket
   - add one focused smoke check that copies a patched installer into a foreign directory and exercises the helper-bootstrap path against a hosted bootstrap bundle
   - continue keeping helper extraction inside `thin-client-assistant/usb/*` modules, but treat the single-file host/download launcher as a compatibility surface that must remain self-contained at startup

## After that

1. Add smoke verification for generated installer URLs and expected public artifact names.
2. Continue thin client runtime work from the now-thin `prepare-runtime.sh`, `apply-network-config.sh`, `moonlight_pairing.sh`, `beagle-usbctl.sh`, and `install-geforcenow.sh` entrypoints by selecting the next shell-heavy runtime/helper module, most likely one of the install/runtime crossover scripts or the next shared runtime helper with duplicated accessors.
