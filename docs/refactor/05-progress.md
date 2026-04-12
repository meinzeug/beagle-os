# Refactor Progress

### 2026-04-12 — explicit standalone vs Proxmox server-installer mode split

- Made the server installer expose the new target architecture directly instead of only implying it through provider environment variables:
  - extended `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer` with explicit install-mode selection for:
    - `Beagle OS standalone`
    - `Beagle OS with Proxmox`
  - normalized installer mode separately from provider kind and mapped the standalone path to `BEAGLE_HOST_PROVIDER=beagle` and the Proxmox-backed path to `BEAGLE_HOST_PROVIDER=proxmox`
  - changed the installer banner text so the ISO now describes Debian + Beagle host installation with an explicit standalone-vs-Proxmox choice instead of presenting Proxmox as the only target
  - split the network baseline by install mode:
    - standalone now writes a direct DHCP interface config on the primary NIC
    - Proxmox mode keeps the existing `vmbr0` bridge baseline
  - split package/repository bootstrap by provider:
    - standalone skips Proxmox repository wiring and installs a Debian/Beagle base package set
    - Proxmox mode keeps the existing `proxmox-ve` package path
  - threaded `BEAGLE_SERVER_INSTALL_MODE` into `scripts/install-beagle-host.sh` and into the generated host env so the chosen installer mode survives beyond the installer prompt
- Reduced another Proxmox-only assumption in host validation:
  - updated `scripts/check-beagle-host.sh` so the generic host check no longer hard-requires Proxmox UI files, nginx, `pveproxy`, or proxied `/beagle-api/healthz` for `BEAGLE_HOST_PROVIDER=beagle`
  - added a standalone-friendly local health check against `http://127.0.0.1:${BEAGLE_MANAGER_LISTEN_PORT:-9088}/healthz`
  - made the few remaining absolute validation file paths configurable so the standalone path can be smoke-tested in a temporary environment
- Validation and smoke checks for this slice passed:
  - `bash -n server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer scripts/install-beagle-host.sh scripts/check-beagle-host.sh`
  - focused smoke test for installer-mode normalization plus standalone DHCP network rendering using a main-less test copy of `beagle-server-installer`
  - focused smoke test for `scripts/check-beagle-host.sh` in `BEAGLE_HOST_PROVIDER=beagle` mode with temporary files and stubbed `systemctl` / `curl`
  - `./scripts/validate-project.sh`

### 2026-04-12 — Script-side provider fallback wrapper extraction

- Reduced the remaining direct `qm` fallback duplication in the provider-aware shell scripts:
  - extended `scripts/lib/provider_shell.sh` with shared wrappers for `beagle_provider_guest_exec_sync_bash()`, `beagle_provider_guest_ipv4()`, `beagle_provider_vm_description()`, `beagle_provider_set_vm_description_b64()`, `beagle_provider_reboot_vm()`, and `beagle_provider_set_vm_options()`
  - `scripts/configure-sunshine-guest.sh` now delegates guest exec, guest IPv4 lookup, VM description reads/writes, and reboot dispatch through those shared wrappers instead of carrying its own helper-vs-raw-`qm` fallback block
  - `scripts/ensure-vm-stream-ready.sh` now delegates its Sunshine guest-status guest-exec path and guest IPv4 lookup through the same shared wrapper layer
  - `scripts/optimize-proxmox-vm-for-beagle.sh` now delegates `qm set` writes through the same shared VM-option wrapper instead of maintaining a second local fallback implementation
- This tightens the script-side provider seam:
  - helper-backed and raw-`qm` fallback execution now live in one place instead of being repeated across multiple host scripts
  - future provider-side script work can keep reducing fallback usage against one shell contract instead of chasing per-script copies
- Validation and smoke checks for this slice passed:
  - `bash -n scripts/lib/provider_shell.sh scripts/configure-sunshine-guest.sh scripts/ensure-vm-stream-ready.sh scripts/optimize-proxmox-vm-for-beagle.sh`
  - focused smoke test for helper-backed wrapper execution in `provider_shell.sh`
  - focused smoke test for remote raw-`qm` fallback paths in `provider_shell.sh` with a stubbed `ssh`
  - `./scripts/validate-project.sh`

### 2026-04-12 — Shared live-medium content-acceptance helper extraction

- Removed the remaining duplicated mounted-content acceptance checks from the USB installer entrypoints:
  - extended `thin-client-assistant/usb/live_medium_helpers.sh` with `candidate_preset_path()`, `live_medium_contains_manifest_or_assets()`, `live_medium_contains_preset_or_assets()`, and `live_medium_contains_persist_root()`
  - `thin-client-assistant/usb/pve-thin-client-live-menu.sh` now uses the shared helper for both the read-only live-medium mount validator and the writable log-persistence validator
  - `thin-client-assistant/usb/pve-thin-client-local-installer.sh` now uses the same shared helper for preset/live-asset acceptance and log-persistence acceptance instead of carrying its own `candidate_preset_path()` and local validator functions
- This closes another USB installer drift seam:
  - live-medium device discovery, mount-candidate discovery, mount orchestration, and now the mounted-content acceptance rules all live in the same shared helper layer
  - the entrypoints keep only their script-specific logging and high-level resolution flow instead of re-describing what counts as a usable mounted live medium
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/usb/live_medium_helpers.sh thin-client-assistant/usb/pve-thin-client-live-menu.sh thin-client-assistant/usb/pve-thin-client-local-installer.sh`
  - focused smoke tests for preset-path, manifest-path, live-asset, and persist-root acceptance in `live_medium_helpers.sh`
  - `./scripts/validate-project.sh`

### 2026-04-12 — Shared runtime preset-extension helper extraction

- Reduced the host-only vs USB-only preset-field drift by moving the extended runtime preset field contract behind one shared helper:
  - added `build_runtime_extension_fields()` to `beagle-host/services/thin_client_preset.py` for network-static, Beagle update/enrollment, egress, identity, Moonlight port, and Sunshine identity fields
  - `beagle-host/services/installer_script.py` now builds its extended VM-installer preset fields through that helper instead of carrying a long inline `extra_fields` block
  - `thin-client-assistant/usb/proxmox_preset.py` now uses the same helper so USB-generated presets emit the same extended field set and default/empty-value rules, with Proxmox-local values filled from description metadata where available
- This narrows a remaining preset contract drift:
  - host-generated and USB-generated presets now share one explicit contract for the extended runtime field set instead of only sharing the minimal base preset keys
  - runtime defaults such as update, egress, identity, and Moonlight-port related fields now come from one shared implementation path
- Validation and smoke checks for this slice passed:
  - `python3 -m py_compile beagle-host/services/thin_client_preset.py beagle-host/services/installer_script.py thin-client-assistant/usb/proxmox_preset.py`
  - focused smoke test for `build_runtime_extension_fields()` default/override output
  - focused smoke test for `thin-client-assistant/usb/proxmox_preset.py build_preset()` with network/egress/identity/Moonlight-port metadata
  - `./scripts/validate-project.sh`

### 2026-04-12 — Hosted download layout helper extraction

- Removed the duplicated hosted-download vs public-release artifact URL shaping from the host download-generation and validation scripts:
  - added `scripts/lib/hosted_download_layout.sh` for `beagle_host_origin_url()`, `beagle_host_downloads_base_url()`, `beagle_public_artifact_base_url()`, `beagle_hosted_download_url()`, `beagle_public_release_artifact_url()`, and `beagle_vm_api_url_template()`
  - `scripts/prepare-host-downloads.sh` now derives hosted installer/live/status URLs and public payload/bootstrap/ISO URLs through that helper instead of constructing the two artifact sources inline
  - `scripts/check-beagle-host.sh` now validates the same URLs through the same helper instead of reconstructing expected hosted/public artifact URLs separately
- This tightens the hosted-installer artifact-source seam:
  - host-local downloads served by the Beagle host and public release artifacts from the update host now have one explicit shared layout contract
  - generation and validation now use the same filename/base-URL rules, reducing drift risk when hosted and public artifact names change
- Validation and smoke checks for this slice passed:
  - `bash -n scripts/lib/hosted_download_layout.sh scripts/prepare-host-downloads.sh scripts/check-beagle-host.sh`
  - focused smoke tests for hosted/public URL normalization and VM API template rendering in `hosted_download_layout.sh`
  - `./scripts/validate-project.sh`

### 2026-04-12 — USB writer device-selection helper extraction

- Removed the remaining operator-facing device-selection and safety block from the USB writer entrypoint:
  - added `thin-client-assistant/usb/usb_writer_device_selection.sh` for `choose_device()`, `device_is_usb_like()`, `root_backing_disk()`, `device_contains_path_source()`, `ensure_target_is_safe()`, `show_target_device()`, `confirm_device_selection()`, and `confirm_device()`
  - `thin-client-assistant/usb/pve-thin-client-usb-installer.sh` now sources that helper and stays focused on argument parsing, dependency/bootstrap handling, and the final write orchestration
- This closes the last large operator/safety seam in the USB writer:
  - device picking, removable-device gating, system-disk protection, and confirmation dialogs now live behind one dedicated helper instead of staying embedded in the entrypoint
  - the writer entrypoint is now effectively just orchestration around helper seams for sources, bootstrap, device selection, and write-stage execution
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/usb/usb_writer_device_selection.sh thin-client-assistant/usb/pve-thin-client-usb-installer.sh`
  - focused smoke test for `device_is_usb_like()`, `root_backing_disk()`, `device_contains_path_source()`, and `ensure_target_is_safe()` with stubbed `lsblk` / `findmnt` / `blockdev`
  - focused smoke test for the `DRY_RUN=1` confirmation short-circuit in `confirm_device_selection()`
  - `./scripts/validate-project.sh`

### 2026-04-12 — USB writer write-stage helper extraction

- Removed the remaining write-stage block from the USB writer entrypoint:
  - added `thin-client-assistant/usb/usb_writer_write_stage.sh` for `partition_suffix()`, `release_target_device()`, `write_usb_manifest()`, `write_usb_preset()`, `write_live_state_config()`, `boot_ip_arg()`, `usb_writer_print_write_plan()`, and `write_usb()`
  - `thin-client-assistant/usb/pve-thin-client-usb-installer.sh` now delegates the whole partition/write/copy/grub flow to that helper and keeps the top-level control flow, device selection, and dependency/bootstrap handling
- This is the biggest USB-writer shrink so far:
  - the writer entrypoint is now mostly orchestration plus operator interaction
  - the actual write pipeline, preset embedding, manifest writing, and GRUB/runtime-state staging now live in one dedicated module
  - the extracted `write_live_state_config()` path now also uses an explicit `echo ...; exit 1` failure path instead of depending on a missing `fail()` function name
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/usb/usb_writer_write_stage.sh thin-client-assistant/usb/pve-thin-client-usb-installer.sh`
  - focused smoke test for `usb_writer_print_write_plan()` with stubbed source-resolution helpers
  - focused smoke test for `write_live_state_config()` with a temporary `write-config.sh` and embedded preset payload
  - `./scripts/validate-project.sh`

### 2026-04-12 — USB writer bootstrap/live-asset helper extraction

- Removed the bootstrap/download/live-asset preparation block from the USB writer entrypoint:
  - added `thin-client-assistant/usb/usb_writer_bootstrap.sh` for `allocate_bootstrap_dir()`, `bootstrap_repo_root()`, `payload_has_live_assets()`, `download_installer_iso()`, `populate_live_assets_from_iso()`, `ensure_live_assets()`, and `validate_live_assets()`
  - `thin-client-assistant/usb/pve-thin-client-usb-installer.sh` now sources that helper and keeps `require_tool()` plus the write/device orchestration in the entrypoint
- This reduces the writer monolith materially:
  - hosted-bootstrap unpacking, ISO download/cache logic, and live-asset extraction/validation now live behind one explicit helper seam
  - the writer entrypoint is now more clearly split into source-selection, bootstrap/live-asset preparation, and actual USB write flow
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/usb/usb_writer_bootstrap.sh thin-client-assistant/usb/pve-thin-client-usb-installer.sh`
  - focused smoke test for `payload_has_live_assets()` and `ensure_live_assets()` build fallback with temporary assets and a stubbed build script
  - focused smoke test for the ISO branch of `ensure_live_assets()` with a stubbed `populate_live_assets_from_iso()`
  - `./scripts/validate-project.sh`

### 2026-04-12 — USB writer source-selection helper extraction

- Removed the repeated USB-writer source-selection and variant-path logic from the USB writer entrypoint:
  - added `thin-client-assistant/usb/usb_writer_sources.sh` for `usb_payload_bundle_path()`, `resolve_usb_install_payload_source()`, `resolve_usb_plan_bootstrap_source()`, `usb_writer_media_label()`, and `usb_writer_live_assets_path()`
  - `thin-client-assistant/usb/pve-thin-client-usb-installer.sh` now sources that helper and reuses it for usage text, USB-manifest payload-source selection, and the dry-run write plan
- This reduces another remaining USB monolith seam:
  - install-payload and bootstrap-source selection now live behind one small writer-specific helper instead of being reconstructed inline in multiple places
  - the writer's `installer` vs `live` path/label differences are now explicit helper contracts instead of scattered conditionals
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/usb/usb_writer_sources.sh thin-client-assistant/usb/pve-thin-client-usb-installer.sh`
  - focused smoke test for default and explicit source resolution plus writer-variant media-label/live-path helpers
  - `./scripts/validate-project.sh`

### 2026-04-12 — USB install-payload asset helper extraction

- Removed the install-payload acquisition and install-manifest block from the local thin-client installer entrypoint:
  - added `thin-client-assistant/usb/install_payload_assets.sh` for `resolve_payload_url_from_manifest()`, `download_install_payload_from_server()`, `prepare_install_assets()`, `resolve_install_manifest_file()`, `read_manifest_project_version()`, `resolve_install_project_version()`, and `write_install_manifest()`
  - `thin-client-assistant/usb/pve-thin-client-local-installer.sh` now sources that helper and stays focused on disk prep, preset/runtime orchestration, and install flow control
- This creates a clearer USB installer seam:
  - remote payload download/fallback, manifest source resolution, and install-manifest writing now live behind one dedicated helper instead of remaining embedded in the local installer monolith
  - the helper still consumes the existing shell/runtime collaborators (`log_msg`, `candidate_manifest_path()`, `USB_MANIFEST_HELPER`) so runtime behavior stays unchanged while the large entrypoint shrinks
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/usb/install_payload_assets.sh thin-client-assistant/usb/pve-thin-client-local-installer.sh`
  - focused smoke test for payload-source resolution, install-manifest resolution/version selection, bundled-asset selection, and `write_install_manifest()` with temporary manifest/assets and a stubbed `log_msg`
  - `./scripts/validate-project.sh`

### 2026-04-12 — USB shared mount-loop extraction

- Removed the duplicated live-medium mount/umount loop from the thin-client USB installer entrypoints:
  - extended `thin-client-assistant/usb/live_medium_helpers.sh` with shared `live_medium_have_mount_privileges()`, `live_medium_run_privileged()`, and `mount_candidate_live_medium()`
  - `thin-client-assistant/usb/pve-thin-client-live-menu.sh` now uses small validator wrappers plus the shared helper for both `mount_discovered_live_medium()` and `mount_writable_live_medium_for_logs()`
  - `thin-client-assistant/usb/pve-thin-client-local-installer.sh` now uses the same shared helper for both mount paths and keeps the installer-specific log messages at the call sites
- This further tightens the USB installer seam:
  - live-device discovery, live-mount candidate discovery, and the actual mount/umount candidate loop now all live in one helper module
  - the two entrypoints still own their different acceptance rules for mounted content and their different logging expectations, so behavior stays split where it is product-specific
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/usb/live_medium_helpers.sh thin-client-assistant/usb/pve-thin-client-live-menu.sh thin-client-assistant/usb/pve-thin-client-local-installer.sh`
  - focused smoke test for `mount_candidate_live_medium()` with stubbed `mount` / `umount` and validator callbacks against `/dev/loop0`
  - `./scripts/validate-project.sh`

### 2026-04-12 — USB live-mount helper extraction

- Removed the duplicated live-medium mount-candidate logic from the thin-client USB installer entrypoints:
  - extended `thin-client-assistant/usb/live_medium_helpers.sh` with shared `candidate_live_mounts()`
  - `thin-client-assistant/usb/pve-thin-client-live-menu.sh` now consumes that helper instead of carrying its own mount-candidate implementation
  - `thin-client-assistant/usb/pve-thin-client-local-installer.sh` now consumes the same helper and keeps its existing `log_msg` trail at the mount-resolution call sites instead of in a duplicated mount-list function
- This further tightens the USB installer continuation seam:
  - live-device discovery and live-mount candidate discovery now both live in the same shared shell helper
  - the local installer still logs candidate mounts where it actually resolves live media and preset files, so operator-facing diagnostics stay in place while the mount-list contract stops drifting
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/usb/live_medium_helpers.sh thin-client-assistant/usb/pve-thin-client-live-menu.sh thin-client-assistant/usb/pve-thin-client-local-installer.sh`
  - focused smoke test for `candidate_live_mounts()` with stubbed `findmnt`
  - `./scripts/validate-project.sh`

### 2026-04-12 — USB live-device and payload-source helper extraction

- Removed the last duplicated live-medium device-candidate logic and one more inline manifest reader from the thin-client USB installer surfaces:
  - extended `thin-client-assistant/usb/live_medium_helpers.sh` with shared `candidate_live_devices()`
  - `thin-client-assistant/usb/pve-thin-client-live-menu.sh` now consumes that helper instead of carrying two separate `candidate_live_devices()` copies in the same file
  - `thin-client-assistant/usb/pve-thin-client-local-installer.sh` now consumes the same helper instead of keeping its own live-device candidate implementation
  - extended `thin-client-assistant/usb/usb_manifest.py` with `read-payload-source`
  - `thin-client-assistant/usb/pve-thin-client-local-installer.sh` now delegates manifest `payload_source` validation/parsing to `usb_manifest.py` instead of embedding another inline Python block
- This further reduces the USB installer surface into explicit shared seams:
  - live-device discovery now lives in exactly one shell helper instead of drifting between the live menu and the local installer
  - manifest payload-source validation now lives in the same Python helper that already owns the other manifest reads/writes
  - the live menu no longer carries duplicate `candidate_live_devices()` definitions, which removes an avoidable continuation hazard for later agents
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/usb/live_medium_helpers.sh thin-client-assistant/usb/pve-thin-client-live-menu.sh thin-client-assistant/usb/pve-thin-client-local-installer.sh`
  - `python3 -m py_compile thin-client-assistant/usb/usb_manifest.py`
  - focused smoke test for `usb_manifest.py read-payload-source` with valid `https://` and invalid `file://` payload sources
  - focused smoke test for `candidate_live_devices()` with stubbed `blkid` / `lsblk`
  - `./scripts/validate-project.sh`

### 2026-04-12 — shared live-medium helper extraction

- Removed the duplicated live-medium asset/manifest path checks from the USB installer entrypoints:
  - added `thin-client-assistant/usb/live_medium_helpers.sh` for shared `candidate_live_asset_dir()` and `candidate_manifest_path()` helpers
  - `thin-client-assistant/usb/pve-thin-client-local-installer.sh` now sources that helper and keeps only the local-installer-specific preset/live-medium orchestration
  - `thin-client-assistant/usb/pve-thin-client-live-menu.sh` now sources the same helper instead of carrying a second copy of the live-medium asset/manifest discovery logic
- This reduces the USB installer surface into a clearer seam:
  - manifest-path and live-asset-path selection now live in one shell helper instead of drifting between the live menu and the local installer
  - the local installer still keeps the stricter boot-asset requirement via the helper's `require_boot_assets` flag, so behavior stays unchanged
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/usb/live_medium_helpers.sh thin-client-assistant/usb/pve-thin-client-local-installer.sh thin-client-assistant/usb/pve-thin-client-live-menu.sh`
  - focused smoke test for `candidate_live_asset_dir()` and `candidate_manifest_path()` with and without required boot assets
  - `./scripts/validate-project.sh`

### 2026-04-12 — USB manifest helper extraction

- Removed the inline manifest/version Python blocks from the thin-client USB shell entrypoints:
  - added `thin-client-assistant/usb/usb_manifest.py` for shared `read-project-version`, `write-install-manifest`, and `write-usb-manifest` subcommands
  - `thin-client-assistant/usb/pve-thin-client-local-installer.sh` now delegates manifest project-version reads plus install-manifest writes to that helper
  - `thin-client-assistant/usb/pve-thin-client-usb-installer.sh` now delegates USB-manifest writes to that helper and keeps only shell orchestration plus asset-copy behavior
- This reduces the USB installer surface into a clearer seam:
  - JSON manifest parsing/writing now lives in one explicit helper instead of duplicated inline Python snippets across multiple shell entrypoints
  - the shell scripts stay focused on payload selection, disk preparation, and copy/install orchestration
  - the previously observed version drift on a written VM100 USB stick is now easier to reason about because manifest formatting is separated from artifact-source selection
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/usb/pve-thin-client-usb-installer.sh thin-client-assistant/usb/pve-thin-client-local-installer.sh`
  - `python3 -m py_compile thin-client-assistant/usb/usb_manifest.py`
  - focused smoke test for `write-usb-manifest`, `read-project-version`, and `write-install-manifest`
  - `./scripts/validate-project.sh`

### 2026-04-11 — server-installer host-provider dispatch seam

- Introduced explicit host-provider dispatch seams inside `server-installer/live-build/.../beagle-server-installer`:
  - added `BEAGLE_SERVER_HOST_PROVIDER` normalization/validation via `host_provider_kind()` and `require_supported_host_provider()`
  - split provider-specific apt source wiring into `write_provider_apt_sources()`
  - split provider-specific package installation into `install_host_provider_packages()`
  - renamed the final chroot Beagle bootstrap step to `install_beagle_host_stack()` and threaded the selected provider into `BEAGLE_HOST_PROVIDER`
- This is the first real provider seam inside the server ISO path rather than only a renamed outer script:
  - current behavior remains identical for the default `proxmox` provider
  - unsupported providers now fail explicitly at the seam instead of silently drifting deeper into Proxmox-only package and install steps
- Validation and smoke checks for this slice passed:
  - `bash -n server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
  - focused smoke check that the installer now contains `host_provider_kind`, `write_provider_apt_sources`, `install_host_provider_packages`, and `install_beagle_host_stack`
  - `./scripts/validate-project.sh`

### 2026-04-11 — generic host service-installer entrypoint extraction

- Moved the host service/bootstrap installer behind a provider-neutral script entrypoint:
  - added `scripts/install-beagle-host-services.sh` as the canonical generic host-service installer entrypoint
  - reduced `scripts/install-proxmox-host-services.sh` to a compatibility wrapper that delegates to `install-beagle-host-services.sh`
  - rewired `scripts/install-beagle-host.sh` to invoke `install-beagle-host-services.sh`
- This continues the outer host bootstrap naming cleanup without hiding the current provider-specific implementation state:
  - the service installer still deploys the current Proxmox provider/runtime assets and keeps `install-proxmox-ui-integration.sh` explicit
  - the canonical host installer path no longer points at a Proxmox-named service-installer entrypoint
- Validation and smoke checks for this slice passed:
  - `bash -n scripts/install-beagle-host.sh scripts/install-beagle-host-services.sh scripts/install-proxmox-host-services.sh`
  - focused smoke check that the legacy service-installer wrapper delegates to the new generic entrypoint
  - `./scripts/validate-project.sh`

### 2026-04-11 — generic host health-check entrypoint extraction

- Moved the post-install host validation bootstrap behind a provider-neutral script entrypoint:
  - added `scripts/check-beagle-host.sh` as the canonical generic host health-check entrypoint
  - reduced `scripts/check-proxmox-host.sh` to a compatibility wrapper that delegates to `check-beagle-host.sh`
  - rewired `scripts/setup-beagle-host.sh`, the README quick-start, and the thin-client installation guide to invoke `check-beagle-host.sh`
- This completes the top-level install/setup/check naming seam for the host bootstrap path without removing current Proxmox compatibility:
  - provider-specific health assertions inside the check script remain unchanged for now
  - the canonical operator-facing validation path is no longer hard-coded to Proxmox naming
- Validation and smoke checks for this slice passed:
  - `bash -n scripts/install-beagle-host.sh scripts/install-proxmox-host.sh scripts/setup-beagle-host.sh scripts/setup-proxmox-host.sh scripts/check-beagle-host.sh scripts/check-proxmox-host.sh server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
  - focused smoke check that the legacy wrapper scripts delegate to the new generic install/setup/check entrypoints
  - `./scripts/validate-project.sh`

### 2026-04-11 — generic host-installer entrypoint extraction

- Moved the host installer bootstrap behind a provider-neutral script entrypoint:
  - added `scripts/install-beagle-host.sh` as the canonical generic host installer entrypoint
  - reduced `scripts/install-proxmox-host.sh` to a compatibility wrapper that delegates to `install-beagle-host.sh`
  - added `scripts/setup-beagle-host.sh` as the canonical generic setup/check entrypoint
  - reduced `scripts/setup-proxmox-host.sh` to a compatibility wrapper that delegates to `setup-beagle-host.sh`
  - rewired `server-installer/live-build/.../beagle-server-installer` to invoke `install-beagle-host.sh` while still passing `BEAGLE_HOST_PROVIDER='proxmox'`
- This moves the operator/bootstrap naming one step closer to a provider-neutral server ISO without removing current Proxmox compatibility:
  - provider-specific adapters such as `install-proxmox-host-services.sh` and `install-proxmox-ui-integration.sh` stay explicit
  - the top-level host install/setup path is no longer hard-coded to Proxmox naming
- Validation and smoke checks for this slice passed:
  - `bash -n scripts/install-beagle-host.sh scripts/install-proxmox-host.sh scripts/setup-beagle-host.sh scripts/setup-proxmox-host.sh server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
  - focused smoke check that the legacy wrapper scripts delegate to the new generic entrypoints
  - `./scripts/validate-project.sh`

### 2026-04-11 — Moonlight host-resolution helper extraction

- Removed the IPv4/preferred-host resolution block from `thin-client-assistant/runtime/moonlight_connect_host.sh`:
  - added `thin-client-assistant/runtime/moonlight_host_resolution.sh` for `resolve_ipv4_host()` and `resolve_preferred_moonlight_host()`
  - `thin-client-assistant/runtime/moonlight_connect_host.sh` now sources that helper and stays focused on direct-local-host checks, gateway fallback, and final connect-host candidate selection
- This reduces the Moonlight connect-host layer into a clearer resolution-vs-selection seam:
  - host resolution and connect-host selection now live in separate modules instead of one mixed helper
  - `moonlight_targeting.sh`, `launch-moonlight.sh`, and `moonlight_pairing.sh` still consume the same public helper surface, so runtime behavior stays unchanged
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/moonlight_host_resolution.sh thin-client-assistant/runtime/moonlight_connect_host.sh thin-client-assistant/runtime/moonlight_targeting.sh thin-client-assistant/runtime/moonlight_reachability.sh thin-client-assistant/runtime/moonlight_pairing.sh thin-client-assistant/runtime/launch-moonlight.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `resolve_preferred_moonlight_host()` with stubbed `prefer_ipv4()`, `is_ip_literal()`, and `resolve_ipv4_host()`
  - focused smoke test for `moonlight_connect_host()` candidate ordering and fallback behavior with stubbed probe outcomes

### 2026-04-11 — USB runtime env helper extraction

- Removed the USB tunnel/env accessor block from `thin-client-assistant/runtime/beagle_usb_runtime_state.sh`:
  - added `thin-client-assistant/runtime/beagle_usb_runtime_env.sh` for `usb_enabled()`, tunnel host/user/port/attach/key accessors, binary accessors, and `require_enabled()`
  - `thin-client-assistant/runtime/beagle_usb_runtime_state.sh` now sources that helper and stays focused on USB state-path resolution plus bound-busid persistence
- This reduces the USB runtime state layer into a clearer env-vs-state seam:
  - USB tunnel/runtime accessors and persisted bound-device state now live in separate modules instead of one mixed helper
  - `beagle_usb_runtime_actions.sh` and `beagle_usb_runtime_payloads.sh` still consume the same public helper surface through `beagle_usb_runtime_state.sh`, so runtime behavior stays unchanged
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/beagle_usb_runtime_env.sh thin-client-assistant/runtime/beagle_usb_runtime_state.sh thin-client-assistant/runtime/beagle_usb_runtime_payloads.sh thin-client-assistant/runtime/beagle_usb_runtime_usbipd.sh thin-client-assistant/runtime/beagle_usb_runtime_actions.sh thin-client-assistant/runtime/beagle-usbctl.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for USB env/tunnel accessor helpers and `require_enabled()` with explicit temporary env values
  - focused smoke test for bound-busid persistence plus `list-json` / `status-json` surfaces with stubbed `usbip`, `pgrep`, and temporary USB state files

### 2026-04-11 — runtime systemd-units helper extraction

- Removed the systemd unit/timer activation block from `thin-client-assistant/runtime/runtime_systemd_bootstrap.sh`:
  - added `thin-client-assistant/runtime/runtime_systemd_units.sh` for `runtime_systemctl_bin()`, `ensure_usb_tunnel_service()`, and `ensure_beagle_management_units()`
  - `thin-client-assistant/runtime/runtime_systemd_bootstrap.sh` now sources that helper and stays focused on boot-mode detection, getty override installation, and boot-service normalization
- This reduces the runtime systemd bootstrap layer into a clearer units-vs-boot seam:
  - service/timer activation and boot/getty orchestration now live in separate modules instead of one mixed helper
  - `prepare-runtime.sh` and the SSH/network helpers still consume the same public helper surface through `runtime_bootstrap_services.sh`, so runtime behavior stays unchanged
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/runtime_systemd_bootstrap.sh thin-client-assistant/runtime/runtime_systemd_units.sh thin-client-assistant/runtime/runtime_bootstrap_services.sh thin-client-assistant/runtime/runtime_ssh_service_config.sh thin-client-assistant/runtime/runtime_network_backend.sh thin-client-assistant/runtime/prepare-runtime.sh`
  - focused smoke test for `ensure_usb_tunnel_service()` and `ensure_beagle_management_units()` with stubbed `systemctl` and `beagle_unit_file_present`
  - focused smoke test for `ensure_getty_overrides()` and `normalize_boot_services()` with temporary override directories plus stubbed `systemctl` and `pve-thin-client-boot-mode`

### 2026-04-11 — runtime Beagle-state helper extraction

- Removed the Beagle state/trace/logging block from `thin-client-assistant/runtime/runtime_core.sh`:
  - added `thin-client-assistant/runtime/runtime_beagle_state.sh` for `beagle_state_dir()`, `beagle_trace_file()`, `beagle_last_marker_file()`, `ensure_beagle_state_dir()`, and `beagle_log_event()`
  - `thin-client-assistant/runtime/runtime_core.sh` now sources that helper and stays focused on runtime user/group/home/uid lookup, live-medium discovery, privileged command execution, and systemd unit-file presence checks
- This reduces the runtime core layer into a clearer identity-vs-state seam:
  - Beagle runtime state persistence/logging and generic runtime identity/privileged wrappers now live in separate modules instead of one mixed helper
  - `common.sh` still sources `runtime_core.sh`, so the public helper surface for the runtime stays unchanged
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/runtime_core.sh thin-client-assistant/runtime/runtime_beagle_state.sh thin-client-assistant/runtime/common.sh thin-client-assistant/runtime/prepare-runtime.sh thin-client-assistant/runtime/launch-session.sh`
  - focused smoke test for `beagle_state_dir()`, `ensure_beagle_state_dir()`, and `beagle_log_event()` with temporary state paths and a stubbed `logger`
  - focused smoke test for `runtime_user_name()`, `runtime_group_name()`, `runtime_user_home()`, `runtime_user_uid()`, `beagle_run_privileged()`, and `beagle_unit_file_present()` with stubbed `sudo` and `systemctl`

### 2026-04-11 — X11 display-selection helper extraction

- Removed the Xauthority discovery and selection block from `thin-client-assistant/runtime/x11_display.sh`:
  - added `thin-client-assistant/runtime/x11_display_selection.sh` for `detect_xauthority()`, `x_display_ready()`, and `select_xauthority()`
  - `thin-client-assistant/runtime/x11_display.sh` now sources that helper and stays focused on `wait_for_x_display_selected()` and `wait_for_x_display()`
- This reduces the X11 runtime layer into a clearer selection-vs-wait seam:
  - Xauthority candidate discovery/readiness and display-wait orchestration now live in separate modules instead of one mixed helper
  - `launch-geforcenow.sh` and `moonlight_runtime_environment.sh` still call the same helper surface through `common.sh`, so runtime behavior stays unchanged
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/x11_display.sh thin-client-assistant/runtime/x11_display_selection.sh thin-client-assistant/runtime/common.sh thin-client-assistant/runtime/launch-geforcenow.sh thin-client-assistant/runtime/moonlight_runtime_environment.sh`
  - focused smoke test for `detect_xauthority()`, `x_display_ready()`, and `select_xauthority()` with temporary Xauthority files plus stubbed `ps` and `xset`
  - focused smoke test for `wait_for_x_display_selected()` and `wait_for_x_display()` with stubbed `xset`, `sleep`, and `beagle_log_event`

### 2026-04-11 — GeForce NOW `xdg-open` helper extraction

- Removed the `xdg-open` wrapper and host-shim block from `thin-client-assistant/runtime/geforcenow_desktop_integration.sh`:
  - added `thin-client-assistant/runtime/geforcenow_xdg_open_integration.sh` for `gfn_wrapper_target()`, `gfn_browser_target()`, `gfn_host_xdg_open_path()`, `gfn_host_xdg_open_log_dir()`, `install_gfn_xdg_open_wrapper()`, `install_gfn_host_xdg_open_shim()`, and `ensure_gfn_xdg_open_integration()`
  - `thin-client-assistant/runtime/geforcenow_desktop_integration.sh` now sources that helper and stays focused on desktop-file generation plus MIME registration
- This reduces the GeForce NOW desktop integration layer into a clearer desktop-registration seam:
  - desktop/MIME registration and `xdg-open` integration now live in separate modules instead of one mixed helper
  - `install-geforcenow.sh` still calls the same `ensure_gfn_desktop_integration()` entrypoint, so runtime behavior stays unchanged
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/geforcenow_desktop_integration.sh thin-client-assistant/runtime/geforcenow_xdg_open_integration.sh thin-client-assistant/runtime/geforcenow_flatpak.sh thin-client-assistant/runtime/install-geforcenow.sh thin-client-assistant/runtime/launch-geforcenow.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `install_gfn_url_handler()` with temporary desktop and MIME paths plus stubbed `update-desktop-database` / `xdg-mime`
  - focused smoke test for `install_gfn_xdg_open_wrapper()` and `install_gfn_host_xdg_open_shim()` with temporary target paths and wrapper/browser targets

### 2026-04-11 — USB `usbipd` lifecycle helper extraction

- Removed the `usbipd` lifecycle and exportability block from `thin-client-assistant/runtime/beagle_usb_runtime_actions.sh`:
  - added `thin-client-assistant/runtime/beagle_usb_runtime_usbipd.sh` for `have_usbipd()`, `restart_usbipd()`, `have_exportable_devices()`, `ensure_usbipd()`, and `sync_bound_devices()`
  - `thin-client-assistant/runtime/beagle_usb_runtime_actions.sh` now sources that helper and stays focused on public USB list/status/bind/unbind actions plus the SSH tunnel entrypoint
- This reduces the USB runtime actions layer into a clearer action seam:
  - local `usbipd` lifecycle handling and public action/tunnel operations now live in separate modules instead of one mixed helper
  - `beagle-usbctl.sh` still drives the same public helper surface, so runtime behavior stays unchanged
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/beagle_usb_runtime_actions.sh thin-client-assistant/runtime/beagle_usb_runtime_usbipd.sh thin-client-assistant/runtime/beagle_usb_runtime_state.sh thin-client-assistant/runtime/beagle_usb_runtime_payloads.sh thin-client-assistant/runtime/beagle-usbctl.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `ensure_usbipd()`, `have_exportable_devices()`, and `sync_bound_devices()` with stubbed `usbip`, `usbipd`, `pgrep`, `pkill`, `modprobe`, and `sleep`
  - focused smoke test for `bind_usb_device()`, `unbind_usb_device()`, `usb_list_json()`, and `usb_status_json()` with stubbed `systemctl` and temporary bound-busid state

### 2026-04-11 — streaming management-activity helper extraction

- Removed the management timer/service suspension block from `thin-client-assistant/runtime/stream_state.sh`:
  - added `thin-client-assistant/runtime/stream_management_activity.sh` for management timer/service unit lists plus `beagle_suspend_management_activity()` and `beagle_resume_management_activity()`
  - `thin-client-assistant/runtime/stream_state.sh` now sources that helper and stays focused on stream-state path selection, session-state persistence, and active-session detection
- This reduces the streaming runtime state helper into a clearer persistence seam:
  - streaming-session state and management-activity orchestration now live in separate modules instead of one mixed helper
  - `geforcenow_stream_optimization.sh`, `launch-geforcenow.sh`, and `session_launcher.sh` still consume the same public helper surface through `common.sh`, so runtime behavior stays unchanged
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/stream_state.sh thin-client-assistant/runtime/stream_management_activity.sh thin-client-assistant/runtime/common.sh thin-client-assistant/runtime/geforcenow_stream_optimization.sh thin-client-assistant/runtime/launch-geforcenow.sh thin-client-assistant/runtime/session_launcher.sh`
  - focused smoke test for `beagle_stream_state_dir()`, `beagle_mark_streaming_session()`, and `beagle_streaming_session_active()` with temporary runtime paths and a stubbed `pgrep`
  - focused smoke test for `beagle_suspend_management_activity()` and `beagle_resume_management_activity()` with stubbed `systemctl`, `beagle_run_privileged`, and `beagle_unit_file_present`

### 2026-04-11 — runtime network config-file helper extraction

- Removed the config-file and resolver-writing block from `thin-client-assistant/runtime/runtime_network_backend.sh`:
  - added `thin-client-assistant/runtime/runtime_network_config_files.sh` for networkd path accessors, NetworkManager connection-file paths, DNS server resolution, `write_network_file()`, `write_nmconnection()`, and `write_resolv_conf()`
  - `thin-client-assistant/runtime/runtime_network_backend.sh` now sources that helper and stays focused on backend detection plus `systemd-networkd` / `NetworkManager` restart control
- This reduces the runtime network backend into a clearer backend-control seam:
  - config-file writing and service restart logic are now split into separate helpers instead of one mixed backend file
  - `apply-network-config.sh` still drives the same public helper calls, so network runtime behavior stays unchanged
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/runtime_network_backend.sh thin-client-assistant/runtime/runtime_network_config_files.sh thin-client-assistant/runtime/runtime_network_runtime.sh thin-client-assistant/runtime/runtime_network_identity.sh thin-client-assistant/runtime/runtime_network_wait.sh thin-client-assistant/runtime/apply-network-config.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `write_network_file()`, `write_nmconnection()`, and `write_resolv_conf()` with temporary runtime paths
  - focused smoke test for `have_networkmanager()`, `restart_networkmanager()`, and `restart_networkd()` with stubbed `systemctl` and `nmcli`

### 2026-04-11 — Moonlight API-URL helper extraction

- Removed the Sunshine API URL/rewrite block from `thin-client-assistant/runtime/moonlight_reachability.sh`:
  - added `thin-client-assistant/runtime/moonlight_api_url.sh` for `rewrite_url_host()`, `sunshine_api_url()`, `effective_sunshine_api_url()`, and `selected_sunshine_api_url()`
  - `thin-client-assistant/runtime/moonlight_reachability.sh` now sources that helper and stays focused on probe, candidate testing, and wait behavior
- This reduces the remaining Moonlight reachability helper into a clearer probe/wait seam:
  - URL/template rewriting and active reachability probes now live in separate modules instead of one mixed helper
  - `moonlight_remote_api.sh`, `launch-moonlight.sh`, and `moonlight_pairing.sh` still consume the same public helper surface, so runtime behavior stays unchanged
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/moonlight_api_url.sh thin-client-assistant/runtime/moonlight_reachability.sh thin-client-assistant/runtime/moonlight_targeting.sh thin-client-assistant/runtime/moonlight_remote_api.sh thin-client-assistant/runtime/moonlight_pairing.sh thin-client-assistant/runtime/launch-moonlight.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `rewrite_url_host()`, `sunshine_api_url()`, `effective_sunshine_api_url()`, and `selected_sunshine_api_url()`
  - focused smoke test for `probe_stream_target()`, `probe_stream_candidate()`, and `wait_for_stream_target()` with stubbed `curl`

## 2026-04-09

### 2026-04-11 — Moonlight host-registry helper extraction

- Removed the remaining inline host-registry Python blocks from `thin-client-assistant/runtime/moonlight_host_sync.sh`:
  - added `thin-client-assistant/runtime/moonlight_host_registry.py` for runtime-response JSON seeding, Moonlight host-entry detection, and Moonlight config-file host-entry synchronization
  - `thin-client-assistant/runtime/moonlight_host_sync.sh` now calls that helper instead of carrying three separate inline Python programs
- This keeps the mutable Moonlight host-registration path explicit and more testable:
  - `thin-client-assistant/runtime/moonlight_host_sync.sh` dropped to about `95` lines
  - the shell helper now mainly owns wrapper/orchestration behavior plus bootstrap triggering, while config parsing/mutation lives in a dedicated Python seam
- Validation and smoke checks for this slice passed:
  - `python3 -m py_compile thin-client-assistant/runtime/moonlight_host_registry.py`
  - `bash -n thin-client-assistant/runtime/moonlight_host_sync.sh thin-client-assistant/runtime/moonlight_pairing.sh thin-client-assistant/runtime/launch-moonlight.sh`
  - focused smoke test for `seed-response`, `sync-config`, and `is-configured` against a temporary Moonlight config file
  - focused smoke test for `seed_moonlight_host_from_runtime_config()` and `moonlight_host_configured()` with stubbed Moonlight accessors

### 2026-04-11 — USB runtime payload helper extraction

- Split the USB inventory/payload-rendering block out of `thin-client-assistant/runtime/beagle_usb_runtime_state.sh`:
  - added `thin-client-assistant/runtime/beagle_usb_runtime_payloads.sh` for tunnel-status detection, local USB inventory JSON shaping, and list/status payload rendering
  - `thin-client-assistant/runtime/beagle_usb_runtime_state.sh` now sources that helper and stays focused on USB state-path resolution, env accessors, and bound-busid persistence
- This reduces the remaining USB runtime state helper to clearer seams:
  - state persistence and payload shaping are now separate modules instead of one mixed file
  - `beagle_usb_runtime_actions.sh` and `beagle-usbctl.sh` still consume the same public helper surface, so runtime behavior stays unchanged
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/beagle_usb_runtime_state.sh thin-client-assistant/runtime/beagle_usb_runtime_payloads.sh thin-client-assistant/runtime/beagle_usb_runtime_actions.sh thin-client-assistant/runtime/beagle-usbctl.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for bound-busid persistence and `list_local_usb_json()` with a stubbed `usbip`
  - focused smoke test for `is_tunnel_running()`, `render_usb_list_json()`, and `render_usb_status_json()` with a stubbed `pgrep`

### 2026-04-11 — Moonlight manager-registration helper extraction

- Split the manager-registration path out of `thin-client-assistant/runtime/moonlight_remote_api.sh`:
  - added `thin-client-assistant/runtime/moonlight_manager_registration.sh` for manager registration payload generation and manager-side client registration
  - `thin-client-assistant/runtime/moonlight_remote_api.sh` now sources that helper and stays focused on shared remote-API accessors plus Sunshine PIN submission and JSON status extraction
- This reduces the remaining Moonlight remote API helper to clearer seams:
  - manager registration and Sunshine PIN submission are now separate helper surfaces instead of one mixed remote API file
  - `moonlight_pairing.sh` and `launch-moonlight.sh` still consume the same public helper functions, so runtime behavior stays unchanged
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/moonlight_manager_registration.sh thin-client-assistant/runtime/moonlight_remote_api.sh thin-client-assistant/runtime/moonlight_pairing.sh thin-client-assistant/runtime/launch-moonlight.sh`
  - focused smoke test for `build_moonlight_manager_registration_payload()` and `register_moonlight_client_via_manager()` with stubbed `curl` and manager sync hooks
  - focused smoke test for `submit_sunshine_pin()` and `json_bool()` with stubbed `curl`

### 2026-04-11 — runtime ownership / GeForce NOW storage split

- Split the mixed ownership/GFN-storage helper layer from `thin-client-assistant/runtime/runtime_ownership.sh`:
  - added `thin-client-assistant/runtime/runtime_fs_ownership.sh` for `ensure_runtime_owned_dir()`, `ensure_runtime_owned_file()`, and `ensure_runtime_owned_tree()`
  - added `thin-client-assistant/runtime/geforcenow_storage_environment.sh` for `prepare_geforcenow_environment()`
  - reduced `thin-client-assistant/runtime/runtime_ownership.sh` to a thin composition wrapper that sources those focused helpers
- This keeps generic filesystem ownership separate from GeForce NOW-specific runtime storage preparation:
  - the generic ownership helpers remain reusable by `geforcenow_desktop_integration.sh` and other runtime code without carrying GFN-specific environment exports
  - the GeForce NOW storage/home/cache/config bootstrap now lives in an explicit helper seam instead of a mixed utility file
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/runtime_ownership.sh thin-client-assistant/runtime/runtime_fs_ownership.sh thin-client-assistant/runtime/geforcenow_storage_environment.sh thin-client-assistant/runtime/common.sh thin-client-assistant/runtime/launch-geforcenow.sh thin-client-assistant/runtime/install-geforcenow.sh`
  - focused smoke test for `ensure_runtime_owned_dir()`, `ensure_runtime_owned_file()`, and `ensure_runtime_owned_tree()` with temporary local paths
  - focused smoke test for `prepare_geforcenow_environment()` export and directory-creation behavior with a temporary storage root

### 2026-04-11 — GeForce NOW stream-optimization helper extraction

- Removed the callback-target and stream-optimization block from `thin-client-assistant/runtime/launch-geforcenow.sh`:
  - added `thin-client-assistant/runtime/geforcenow_stream_optimization.sh` for callback-target logging/detection plus management-suspension and delayed kiosk-stop orchestration
  - `thin-client-assistant/runtime/launch-geforcenow.sh` now sources that helper instead of carrying stream-optimization state transitions inline
- This keeps the GeForce NOW launcher focused on environment/bootstrap and final `flatpak run` execution:
  - `thin-client-assistant/runtime/launch-geforcenow.sh` dropped to about `69` lines
  - the side-effect-heavy callback/kiosk/management coordination now lives in an explicit helper seam
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/geforcenow_stream_optimization.sh thin-client-assistant/runtime/launch-geforcenow.sh thin-client-assistant/runtime/common.sh thin-client-assistant/runtime/install-geforcenow.sh`
  - focused smoke test for callback-target logging, stream-optimization activation/deactivation, delayed kiosk-stop invocation, and management suspend/resume behavior with stubbed helpers

### 2026-04-11 — Moonlight host-sync helper extraction

- Removed the manager-response host-sync/bootstrap block from `thin-client-assistant/runtime/moonlight_config_state.sh`:
  - added `thin-client-assistant/runtime/moonlight_host_sync.sh` for runtime-config seeding, configured-host detection, manager-response config sync, and bootstrap list priming
  - `thin-client-assistant/runtime/moonlight_config_state.sh` now sources that helper instead of carrying host-sync/bootstrap logic inline
- This reduces the Moonlight config-state helper into a focused config/certificate seam:
  - `thin-client-assistant/runtime/moonlight_config_state.sh` dropped to about `45` lines
  - the remaining file is now just config-path discovery plus client-certificate extraction, while the mutable host-sync path lives in its own module
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/moonlight_config_state.sh thin-client-assistant/runtime/moonlight_host_sync.sh thin-client-assistant/runtime/moonlight_pairing.sh thin-client-assistant/runtime/moonlight_remote_api.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `sync_moonlight_host_from_manager_response()`, `moonlight_host_configured()`, and `extract_moonlight_certificate_pem()` with a temporary Moonlight config file
  - focused smoke test for `bootstrap_moonlight_client()` with stubbed `moonlight` / `timeout`

### 2026-04-11 — runtime network identity helper extraction

- Removed the interface/address/hostname block from `thin-client-assistant/runtime/runtime_network_runtime.sh`:
  - added `thin-client-assistant/runtime/runtime_network_identity.sh` for sysfs and binary path accessors, interface selection, static IPv4 CIDR shaping, hostname application, static route installation, and static address application
  - `thin-client-assistant/runtime/runtime_network_runtime.sh` now sources that helper instead of carrying interface/address/hostname logic inline
- This completes the main reduction of the runtime network helper:
  - `thin-client-assistant/runtime/runtime_network_runtime.sh` dropped further to about `17` lines
  - the file is now just a small composition layer for the extracted network wait and network identity seams
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/runtime_network_runtime.sh thin-client-assistant/runtime/runtime_network_identity.sh thin-client-assistant/runtime/runtime_network_wait.sh thin-client-assistant/runtime/runtime_network_backend.sh thin-client-assistant/runtime/common.sh thin-client-assistant/runtime/apply-network-config.sh`
  - focused smoke test for `pick_interface()` and `static_ipv4_cidr()` with a temporary fake `/sys/class/net`
  - focused smoke test for `apply_static_address()`, `ensure_static_routes()`, and `apply_hostname()` with stubbed `ip`, `hostnamectl`, and `hostname`

### 2026-04-11 — runtime network wait helper extraction

- Removed the DNS/default-route wait and host-resolution block from `thin-client-assistant/runtime/runtime_network_runtime.sh`:
  - added `thin-client-assistant/runtime/runtime_network_wait.sh` for IP-literal checks, URL-host extraction, DNS wait-target shaping, IPv4 resolution checks, default-route waiting, and DNS-target waiting
  - `thin-client-assistant/runtime/runtime_network_runtime.sh` now sources that helper instead of carrying wait/lookup logic inline
- This reduces the runtime network helper into a more focused interface/address/hostname module:
  - `thin-client-assistant/runtime/runtime_network_runtime.sh` dropped to about `123` lines
  - the remaining file is now mainly about interface selection, static IPv4 CIDR shaping, hostname application, and static address/route writes
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/runtime_network_runtime.sh thin-client-assistant/runtime/runtime_network_wait.sh thin-client-assistant/runtime/runtime_network_backend.sh thin-client-assistant/runtime/common.sh thin-client-assistant/runtime/apply-network-config.sh`
  - focused smoke test for `extract_host_from_url()`, `dns_wait_targets()`, and `network_is_ip_literal()`
  - focused smoke test for `wait_for_default_route()` and `wait_for_dns_targets()` with stubbed `ip` and `getent`

### 2026-04-11 — Moonlight connect-host helper extraction

- Removed the connect-host selection block from `thin-client-assistant/runtime/moonlight_targeting.sh`:
  - added `thin-client-assistant/runtime/moonlight_connect_host.sh` for IPv4 resolution, preferred-host resolution, direct-local-host checks, usable-local-host selection, gateway fallback selection, primary/public connect-host derivation, and the final connect-host candidate selection flow
  - `thin-client-assistant/runtime/moonlight_targeting.sh` now sources that helper instead of carrying host-candidate selection and fallback logic inline
- This leaves the Moonlight targeting entry helper very small:
  - `thin-client-assistant/runtime/moonlight_targeting.sh` dropped further to about `60` lines
  - the remaining file is now just Moonlight host/local-host/port accessors, IPv4 preference/IP-literal checks, and target formatting
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/moonlight_targeting.sh thin-client-assistant/runtime/moonlight_connect_host.sh thin-client-assistant/runtime/moonlight_reachability.sh thin-client-assistant/runtime/common.sh thin-client-assistant/runtime/launch-moonlight.sh`
  - focused smoke test for primary/public connect-host IPv4 preference resolution
  - focused smoke test for connect-host candidate ordering and fallback selection

### 2026-04-11 — Moonlight reachability helper extraction

- Removed the Sunshine URL rewrite / probe / wait block from `thin-client-assistant/runtime/moonlight_targeting.sh`:
  - added `thin-client-assistant/runtime/moonlight_reachability.sh` for Sunshine API URL derivation, URL host rewriting, API/TCP stream probing, effective API URL selection, selected API URL shaping, reachability checks, and the stream-target wait loop
  - `thin-client-assistant/runtime/moonlight_targeting.sh` now sources that helper instead of carrying URL rewrite, probe, and wait logic inline
- This reduces the Moonlight targeting helper into a more focused host-selection module:
  - `thin-client-assistant/runtime/moonlight_targeting.sh` dropped to about `192` lines
  - the remaining file is now mainly about host/local-host/gateway selection and connect-host resolution, while reachability/probing lives in its own seam
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/moonlight_targeting.sh thin-client-assistant/runtime/moonlight_reachability.sh thin-client-assistant/runtime/common.sh thin-client-assistant/runtime/launch-moonlight.sh`
  - focused smoke test for `rewrite_url_host()`, `effective_sunshine_api_url()`, and `probe_stream_target()` with a stubbed `curl`
  - focused smoke test for `wait_for_stream_target()` with a stubbed reachability function and log capture

### 2026-04-11 — runtime SSH service-config helper extraction

- Removed the remaining managed SSH config/service-validation block from `thin-client-assistant/runtime/runtime_bootstrap_services.sh`:
  - added `thin-client-assistant/runtime/runtime_ssh_service_config.sh` for `sshd` binary/service/config accessors, managed-block markers, managed-block stripping, validated `sshd` restart/start helpers, and `apply_runtime_ssh_config()`
  - `thin-client-assistant/runtime/runtime_bootstrap_services.sh` now sources that helper instead of carrying managed SSH config rewriting and `sshd` validation/restart logic inline
- This completes the main reduction of the old bootstrap helper:
  - `thin-client-assistant/runtime/runtime_bootstrap_services.sh` dropped further to about `32` lines
  - the remaining file is now just the stable `ensure_runtime_ssh_host_keys()` orchestration wrapper over the extracted SSH host-key and SSH service-config helpers
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/runtime_bootstrap_services.sh thin-client-assistant/runtime/runtime_ssh_service_config.sh thin-client-assistant/runtime/runtime_ssh_host_keys.sh thin-client-assistant/runtime/runtime_systemd_bootstrap.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `apply_runtime_ssh_config()` with stubbed `sshd` and `systemctl`
  - focused smoke test for the unchanged `ensure_runtime_ssh_host_keys()` wrapper with stubbed `sshd`, `systemctl`, and `ssh-keygen`

### 2026-04-11 — runtime SSH host-key helper extraction

- Removed the persistent SSH host-key block from `thin-client-assistant/runtime/runtime_bootstrap_services.sh`:
  - added `thin-client-assistant/runtime/runtime_ssh_host_keys.sh` for SSH keygen and SSH directory accessors, persistent host-key directory resolution, persistent-to-runtime key copy, empty-key cleanup, key-presence checks, conditional host-key generation, and runtime-to-persistent host-key writes
  - `thin-client-assistant/runtime/runtime_bootstrap_services.sh` now sources that helper instead of carrying host-key persistence and generation logic inline, while keeping `ensure_runtime_ssh_host_keys()` as the stable orchestration wrapper
- This continues the reduction of the old bootstrap helper:
  - `thin-client-assistant/runtime/runtime_bootstrap_services.sh` dropped further to about `117` lines
  - the remaining file is now focused on managed SSH config rewriting, `sshd` validation/start helpers, and the final host-key orchestration wrapper
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/runtime_bootstrap_services.sh thin-client-assistant/runtime/runtime_ssh_host_keys.sh thin-client-assistant/runtime/runtime_systemd_bootstrap.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for host-key copy/remove/presence/persist helpers with temporary SSH and live-state directories
  - focused smoke test for `ensure_runtime_ssh_host_keys()` with stubbed `sshd`, `systemctl`, and `ssh-keygen`

### 2026-04-11 — runtime systemd bootstrap helper extraction

- Removed the systemd/getty/boot-mode block from `thin-client-assistant/runtime/runtime_bootstrap_services.sh`:
  - added `thin-client-assistant/runtime/runtime_systemd_bootstrap.sh` for `systemctl`/boot-mode path resolution, getty override path accessors, USB tunnel service control, Beagle management unit activation, getty override installation, and boot-service normalization
  - `thin-client-assistant/runtime/runtime_bootstrap_services.sh` now sources that helper instead of carrying the systemd/getty/bootstrap unit logic inline
- This reduces the old bootstrap helper into a more focused SSH-oriented module:
  - `thin-client-assistant/runtime/runtime_bootstrap_services.sh` dropped to about `195` lines
  - the remaining file is now primarily about managed SSH config rewriting and persistent SSH host-key handling
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/runtime_bootstrap_services.sh thin-client-assistant/runtime/runtime_systemd_bootstrap.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `ensure_getty_overrides()`, `normalize_boot_services()`, `ensure_beagle_management_units()`, and `ensure_usb_tunnel_service()` with stubbed `systemctl` and boot-mode binaries
  - focused smoke test for installer-mode normalization plus disabled USB tunnel handling

### 2026-04-11 — GeForce NOW flatpak helper extraction

- Removed the remaining GeForce NOW scope/flatpak install block from `thin-client-assistant/runtime/install-geforcenow.sh` and the duplicated scope parser from `thin-client-assistant/runtime/launch-geforcenow.sh`:
  - added `thin-client-assistant/runtime/geforcenow_flatpak.sh` for flatpak binary discovery, install-scope normalization, dry-run command execution, flatpak availability checks, install-scope permission checks, installed-ref detection, and the shared flatpak remote/install flow
  - `thin-client-assistant/runtime/install-geforcenow.sh` now sources that helper instead of carrying scope parsing, dry-run execution, flatpak availability checks, and remote/app install logic inline
  - `thin-client-assistant/runtime/launch-geforcenow.sh` now also uses the same install-scope resolver instead of keeping a second local `flatpak_scope_flag()`
- This completes the main `install-geforcenow.sh` split:
  - `thin-client-assistant/runtime/install-geforcenow.sh` dropped further to about `73` lines
  - the entrypoint now mostly owns argument parsing, environment preparation, logging, and composition of extracted GeForce NOW helpers
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/install-geforcenow.sh thin-client-assistant/runtime/launch-geforcenow.sh thin-client-assistant/runtime/geforcenow_flatpak.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `resolve_gfn_install_scope()` across `user` / `system` forms
  - focused smoke test for `ensure_gfn_flatpak_installation()` with a stubbed `flatpak` binary covering cached runtime plus missing app installation

### 2026-04-11 — GeForce NOW desktop integration helper extraction

- Removed the GeForce NOW desktop-file / MIME / `xdg-open` integration block from `thin-client-assistant/runtime/install-geforcenow.sh`:
  - added `thin-client-assistant/runtime/geforcenow_desktop_integration.sh` for desktop-database and `xdg-mime` binary accessors, desktop-file generation, MIME registration, user `xdg-open` wrapper generation, host `xdg-open` shim generation, and the top-level desktop integration orchestration
  - `thin-client-assistant/runtime/install-geforcenow.sh` now sources that helper instead of carrying desktop-file generation and wrapper/shim writes inline
- This starts the real reduction of the GeForce NOW installer wrapper:
  - `thin-client-assistant/runtime/install-geforcenow.sh` dropped from about `238` lines to about `125` lines on this slice before the flatpak-helper extraction completed the reduction
  - the extracted helper accepts path/binary overrides for desktop database, `xdg-mime`, wrapper targets, browser target, host shim path, and host shim log directory, which keeps runtime defaults but makes the integration seam smoke-testable
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/install-geforcenow.sh thin-client-assistant/runtime/geforcenow_desktop_integration.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for desktop file, `mimeapps.list`, user `xdg-open` wrapper, and host shim generation with temporary home paths and stubbed `update-desktop-database` / `xdg-mime`

### 2026-04-11 — USB runtime action helper extraction

- Removed the remaining `usbip` daemon/bind/tunnel orchestration block from `thin-client-assistant/runtime/beagle-usbctl.sh`:
  - added `thin-client-assistant/runtime/beagle_usb_runtime_actions.sh` for `usbipd` process/binary accessors, daemon restart handling, exportable-device detection, bound-device resync, bind/unbind orchestration, list/status JSON dispatch, and the SSH tunnel daemon exec path
  - `thin-client-assistant/runtime/beagle-usbctl.sh` now sources that helper instead of carrying daemon lifecycle, `usbip bind`/`unbind`, service restart, and tunnel exec logic inline
- This completes the main `beagle-usbctl.sh` reduction:
  - `thin-client-assistant/runtime/beagle-usbctl.sh` is now down to about `38` lines
  - the entrypoint is now just runtime-config loading plus command dispatch into the extracted USB runtime helpers
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/beagle-usbctl.sh thin-client-assistant/runtime/beagle_usb_runtime_state.sh thin-client-assistant/runtime/beagle_usb_runtime_actions.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `sync_bound_devices()` with stubbed `usbip`, `usbipd`, `pgrep`, `pkill`, `modprobe`, and `sleep`
  - focused smoke test for `bind_usb_device()` / `unbind_usb_device()` with stubbed `usbip`, `usbipd`, `pgrep`, `pkill`, `modprobe`, `systemctl`, and `sleep`

### 2026-04-11 — USB runtime state helper extraction

- Removed the USB runtime state/tunnel-status/payload-shaping block from `thin-client-assistant/runtime/beagle-usbctl.sh`:
  - added `thin-client-assistant/runtime/beagle_usb_runtime_state.sh` for USB state-path resolution, persisted bound-busid state reads/writes, enabled/tunnel env accessors, tunnel-state detection, local USB inventory JSON shaping, and list/status payload rendering
  - `thin-client-assistant/runtime/beagle-usbctl.sh` now sources that helper instead of mixing state I/O, JSON generation, tunnel-status checks, and payload shaping with the command flow
- This is the first real split of the USB runtime entrypoint:
  - `thin-client-assistant/runtime/beagle-usbctl.sh` dropped to about `135` lines on the first slice before the follow-up action-helper extraction completed the reduction
  - the extracted helper keeps the USB state contract explicit and smoke-testable with temporary state roots and stubbed `usbip` / `pgrep`
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/beagle-usbctl.sh thin-client-assistant/runtime/beagle_usb_runtime_state.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `write_state()`, `state_bound_busids()`, `bound_add()`, and `bound_remove()` with a temporary `BEAGLE_USB_STATE_DIR`
  - focused smoke test for `list_local_usb_json()`, `render_usb_list_json()`, `render_usb_status_json()`, and `is_tunnel_running()` with stubbed `usbip` and `pgrep`

### 2026-04-11 — Moonlight config/state helper extraction

- Removed the local Moonlight config/certificate/bootstrap block from `thin-client-assistant/runtime/moonlight_pairing.sh`:
  - added `thin-client-assistant/runtime/moonlight_config_state.sh` for config-path discovery, runtime-config seeding, host-config presence checks, client-certificate extraction, manager-response host sync, and bootstrap list priming
  - `thin-client-assistant/runtime/moonlight_pairing.sh` now sources that helper instead of mixing local config state with the remaining pair-process orchestration
- This leaves the pairing module much closer to its final shape:
  - `thin-client-assistant/runtime/moonlight_pairing.sh` dropped further to about `77` lines
  - the file now mostly owns list-timeout/bootstrap-timeout constants and the final `ensure_paired()` orchestration loop
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/moonlight_pairing.sh thin-client-assistant/runtime/moonlight_config_state.sh thin-client-assistant/runtime/moonlight_remote_api.sh thin-client-assistant/runtime/moonlight_targeting.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for config-path detection, certificate extraction, manager-response sync, and `moonlight_host_configured()` with a temporary Moonlight config file
  - focused smoke test for `seed_moonlight_host_from_runtime_config()` plus `bootstrap_moonlight_client()` with a temporary config file and stubbed Moonlight binary

### 2026-04-11 — Moonlight remote API helper extraction

- Removed the manager/Sunshine remote API block from `thin-client-assistant/runtime/moonlight_pairing.sh`:
  - added `thin-client-assistant/runtime/moonlight_remote_api.sh` for Moonlight client device-name resolution, manager registration payload generation, manager-side client registration, Sunshine PIN submission, and `json_bool()` status extraction
  - `thin-client-assistant/runtime/moonlight_pairing.sh` now sources that helper instead of mixing remote API calls with local config/bootstrap/pairing logic
- This is the first real split of the remaining Moonlight pairing monolith after the targeting/runtime-exec work:
  - `thin-client-assistant/runtime/moonlight_pairing.sh` dropped to about `358` lines
  - the remaining file is now more clearly about local config/certificate/bootstrap state plus the final `ensure_paired()` flow
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/moonlight_pairing.sh thin-client-assistant/runtime/moonlight_remote_api.sh thin-client-assistant/runtime/moonlight_targeting.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `register_moonlight_client_via_manager()` with stubbed `curl` and a temporary Moonlight config file
  - focused smoke test for `submit_sunshine_pin()` and `json_bool()` with stubbed `curl` and hostname resolution

### 2026-04-11 — runtime network runtime helper extraction

- Removed the remaining network-runtime logic from `thin-client-assistant/runtime/apply-network-config.sh`:
  - added `thin-client-assistant/runtime/runtime_network_runtime.sh` for interface selection, static IPv4 CIDR calculation, URL-host extraction, DNS wait-target shaping, IPv4 resolution checks, default-route waiting, DNS-target waiting, hostname application, static route installation, and static address application
  - `thin-client-assistant/runtime/apply-network-config.sh` now sources that helper instead of carrying the route/wait/identity block inline
- This completes the main `apply-network-config.sh` split:
  - `thin-client-assistant/runtime/apply-network-config.sh` is now down to about `41` lines
  - the entrypoint now mostly sequences the extracted network backend and network runtime helpers
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/apply-network-config.sh thin-client-assistant/runtime/runtime_network_runtime.sh thin-client-assistant/runtime/runtime_network_backend.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `pick_interface()`, `static_ipv4_cidr()`, and `extract_host_from_url()` with a temporary fake `/sys/class/net`
  - focused smoke test for `apply_static_address()`, `ensure_static_routes()`, `apply_hostname()`, `wait_for_default_route()`, and `wait_for_dns_targets()` with stubbed `ip`, `getent`, and `hostnamectl`

### 2026-04-11 — runtime network backend helper extraction

- Removed the network backend file/restart layer from `thin-client-assistant/runtime/apply-network-config.sh`:
  - added `thin-client-assistant/runtime/runtime_network_backend.sh` for networkd file writing, NetworkManager connection writing, DNS server resolution, `resolv.conf` management, and network backend restart/reload helpers
  - `thin-client-assistant/runtime/apply-network-config.sh` now sources that helper instead of carrying the backend config-file and restart logic inline
  - `apply-network-config.sh` also now reuses `load_runtime_config_with_retry()` from `runtime_prepare_flow.sh` instead of duplicating the same retry wrapper locally
- This starts the next runtime shell reduction track after `prepare-runtime.sh`:
  - `thin-client-assistant/runtime/apply-network-config.sh` dropped to about `208` lines from roughly `363`
  - the remaining script is now focused on interface selection, route/DNS wait behavior, address/route application, and top-level sequencing
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/apply-network-config.sh thin-client-assistant/runtime/runtime_network_backend.sh thin-client-assistant/runtime/runtime_prepare_flow.sh thin-client-assistant/runtime/runtime_bootstrap_services.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `write_network_file()`, `write_nmconnection()`, and `write_resolv_conf()` with temporary output paths
  - focused smoke test for `have_networkmanager()`, `restart_networkmanager()`, and `restart_networkd()` with stubbed `systemctl` and `nmcli`

### 2026-04-11 — runtime prepare status helper extraction

- Removed the final runtime-status assembly block from `thin-client-assistant/runtime/prepare-runtime.sh`:
  - added `thin-client-assistant/runtime/runtime_prepare_status.sh` for runtime status-path resolution, required-binary selection, binary-availability detection, and final runtime-status emission through `status_writer.py`
  - `thin-client-assistant/runtime/prepare-runtime.sh` now delegates the last status-file assembly block to that helper instead of keeping binary-mode switching and file writes inline
- This leaves the entrypoint thinner and makes the final runtime-status contract directly smoke-testable with temp paths and stub binaries.
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/prepare-runtime.sh thin-client-assistant/runtime/runtime_prepare_status.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `runtime_required_binary()`, `runtime_binary_available()`, and `write_prepare_runtime_status()`

### 2026-04-11 — runtime prepare flow helper extraction

- Removed the remaining retry/bootstrap wrapper block from `thin-client-assistant/runtime/prepare-runtime.sh`:
  - added `thin-client-assistant/runtime/runtime_prepare_flow.sh` for `load_runtime_config_with_retry()`, boot-mode detection, Plymouth status messaging, optional hook execution, and `ensure_kiosk_runtime()`
  - `thin-client-assistant/runtime/prepare-runtime.sh` now sources that helper instead of carrying retry, Plymouth, and kiosk-prepare logic inline
- This is the point where `prepare-runtime.sh` effectively becomes an orchestration shell:
  - `thin-client-assistant/runtime/prepare-runtime.sh` is now down to about `65` lines
  - the entrypoint now mostly sequences dedicated helpers instead of implementing runtime behavior itself
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/prepare-runtime.sh thin-client-assistant/runtime/runtime_prepare_flow.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for boot-mode detection, Plymouth status calls, kiosk preparation, and optional runtime hook execution with stub binaries

### 2026-04-11 — runtime endpoint enrollment helper extraction

- Removed the endpoint-enrollment request/apply/reload flow from `thin-client-assistant/runtime/prepare-runtime.sh`:
  - added `thin-client-assistant/runtime/runtime_endpoint_enrollment.sh` for runtime config/credential path resolution, enrollment URL selection, endpoint hostname/ID derivation, enrollment request execution, response application through `apply_enrollment_config.py`, and config reload after a successful enrollment
  - `thin-client-assistant/runtime/prepare-runtime.sh` now sources that helper instead of carrying the full enrollment curl/apply/reload block inline
- Hardened the shared curl/TLS helper while extracting the enrollment seam:
  - `thin-client-assistant/runtime/runtime_value_helpers.sh` no longer emits an empty argument line when no TLS options apply
  - this fixes the latent blank-argument `curl` failure that could affect runtime enrollment and other extracted curl-based helpers
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/prepare-runtime.sh thin-client-assistant/runtime/runtime_endpoint_enrollment.sh thin-client-assistant/runtime/runtime_value_helpers.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `beagle_curl_tls_args()` with and without TLS arguments
  - focused smoke test for `enroll_endpoint_if_needed()` using a stub curl binary plus the real `apply_enrollment_config.py` helper

### 2026-04-11 — runtime SSH/bootstrap service helper extraction

- Removed the SSH/bootstrap-management block from `thin-client-assistant/runtime/prepare-runtime.sh`:
  - added `thin-client-assistant/runtime/runtime_bootstrap_services.sh` for managed SSH config rewriting, SSH host-key persistence/generation, USB tunnel service control, Beagle management timer/service activation, getty override installation, and boot-mode service normalization
  - `thin-client-assistant/runtime/prepare-runtime.sh` now sources that helper instead of carrying the SSH/service/bootstrap block inline
  - `thin-client-assistant/runtime/runtime_core.sh` now lets `beagle_unit_file_present()` honor `BEAGLE_SYSTEMCTL_BIN`, which makes the unit checks testable without affecting runtime defaults
- This is the largest `prepare-runtime.sh` reduction so far:
  - the entrypoint dropped to about `190` lines before the enrollment extraction and now sits at about `152` lines
  - the remaining shell now mostly owns top-level sequencing, kiosk-specific runtime preparation, and final runtime-status emission
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/prepare-runtime.sh thin-client-assistant/runtime/runtime_bootstrap_services.sh thin-client-assistant/runtime/runtime_core.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `apply_runtime_ssh_config()` with stubbed `sshd` and `systemctl`
  - focused smoke test for `ensure_runtime_ssh_host_keys()` with temporary SSH/live-state directories and stubbed `sshd` / `systemctl` / `ssh-keygen`
  - focused smoke test for `ensure_getty_overrides()`, `ensure_beagle_management_units()`, `ensure_usb_tunnel_service()`, and `normalize_boot_services()` with stubbed `systemctl`

### 2026-04-11 — runtime user setup helper extraction

- Removed the runtime user/secret-permission/hostname block from `thin-client-assistant/runtime/prepare-runtime.sh`:
  - added `thin-client-assistant/runtime/runtime_user_setup.sh` for local-auth path resolution, runtime login-shell resolution, runtime user creation/update, secret-permission normalization, and local hostname/hosts-file synchronization
  - `thin-client-assistant/runtime/prepare-runtime.sh` now sources that helper instead of carrying those bootstrap steps inline
- This continues the real reduction of the prepare-runtime entrypoint:
  - `thin-client-assistant/runtime/prepare-runtime.sh` dropped further to about `375` lines
  - the extracted helper supports command and path overrides for `id`, `useradd`, `usermod`, `chpasswd`, `chown`, `hostname`, `/etc/hostname`, and `/etc/hosts`, which preserves runtime defaults but makes the bootstrap seam smoke-testable
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/prepare-runtime.sh thin-client-assistant/runtime/runtime_user_setup.sh thin-client-assistant/runtime/runtime_config_persistence.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `ensure_runtime_user()` with stubbed user-management binaries and a temporary `local-auth.env`
  - focused smoke test for `adjust_secret_permissions()` plus `sync_local_hostname()` with temporary config and hosts files

### 2026-04-11 — runtime config persistence helper extraction

- Removed the runtime config sync/live-state persistence block from `thin-client-assistant/runtime/prepare-runtime.sh`:
  - added `thin-client-assistant/runtime/runtime_config_persistence.sh` for system-config target resolution, shared sync file lists, config-path rebinding, permission normalization, live-state remount handling, and config persistence to the live state directory
  - `thin-client-assistant/runtime/prepare-runtime.sh` now sources that helper instead of keeping the config-copy and live-state persistence block inline
  - the prepare entrypoint also now reuses `beagle_unit_file_present()` from `runtime_core.sh` instead of carrying another local unit-file presence helper
- This is the first real split of the remaining `prepare-runtime.sh` monolith:
  - `thin-client-assistant/runtime/prepare-runtime.sh` dropped to about `438` lines
  - the extracted helper accepts optional source/target arguments, which keeps runtime behavior unchanged while making the persistence seam smoke-testable outside the live system path layout
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/prepare-runtime.sh thin-client-assistant/runtime/runtime_config_persistence.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `sync_runtime_config_to_system()` with temporary source/target config directories
  - focused smoke test for `persist_runtime_config_to_live_state()` with a temporary live-state directory

### 2026-04-11 — Moonlight runtime-exec helper extraction

- Removed the remaining decoder/audio/display/stream-argument block from `thin-client-assistant/runtime/launch-moonlight.sh`:
  - added `thin-client-assistant/runtime/moonlight_runtime_exec.sh` for `moonlight_bin()`, `moonlight_app()`, audio-driver selection, decoder selection, local display detection, resolution shaping, stream-arg assembly, and graphics/audio runtime environment preparation
  - `thin-client-assistant/runtime/launch-moonlight.sh` now sources that helper instead of carrying the full stream-execution setup inline
- This finishes the main Moonlight launcher split into explicit seams:
  - `thin-client-assistant/runtime/launch-moonlight.sh` is now down to about `106` lines and mostly owns top-level orchestration plus final `exec`
  - `moonlight_targeting.sh` owns target selection and reachability
  - `moonlight_pairing.sh` owns pairing/bootstrap/config sync
  - `moonlight_runtime_exec.sh` owns stream execution setup and argument shaping
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/launch-moonlight.sh thin-client-assistant/runtime/moonlight_runtime_exec.sh thin-client-assistant/runtime/moonlight_pairing.sh thin-client-assistant/runtime/moonlight_targeting.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `build_stream_args()` through the extracted helper
  - focused smoke tests for `moonlight_audio_driver()` override/default behavior and `moonlight_resolution()`

### 2026-04-11 — Moonlight runtime environment helper extraction

- Removed the audio/graphics runtime-environment block from `thin-client-assistant/runtime/moonlight_runtime_exec.sh`:
  - added `thin-client-assistant/runtime/moonlight_runtime_environment.sh` for `moonlight_audio_driver()`, `configure_graphics_runtime()`, and `configure_audio_runtime()`
  - `thin-client-assistant/runtime/moonlight_runtime_exec.sh` now sources that helper instead of carrying display/audio environment setup inline
- This keeps the Moonlight execution layer split by concern instead of only by launcher entrypoint:
  - `launch-moonlight.sh` remains a thin top-level orchestration wrapper at about `106` lines
  - `moonlight_runtime_environment.sh` now owns the mutable display/audio environment contract
  - `moonlight_runtime_exec.sh` no longer mixes stream-argument shaping with runtime env export logic
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/moonlight_runtime_exec.sh thin-client-assistant/runtime/moonlight_runtime_environment.sh thin-client-assistant/runtime/launch-moonlight.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `moonlight_audio_driver()` override behavior plus `configure_audio_runtime()` / `configure_graphics_runtime()` with stubbed X11 helpers

### 2026-04-11 — Moonlight stream-profile helper extraction

- Removed the decoder-choice and resolution-shaping block from `thin-client-assistant/runtime/moonlight_runtime_exec.sh`:
  - added `thin-client-assistant/runtime/moonlight_stream_profile.sh` for `moonlight_video_decoder()`, `record_decoder_choice()`, `local_display_resolution()`, and `moonlight_resolution()`
  - `thin-client-assistant/runtime/moonlight_runtime_exec.sh` now sources that helper and stays focused on Moonlight binary/app resolution plus stream-argument assembly
- This reduces the remaining execution helper to a small composition seam:
  - `thin-client-assistant/runtime/moonlight_runtime_exec.sh` is now down to about `60` lines
  - the stream-profile policy is isolated from audio/display environment mutation and from the final launcher orchestration
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/moonlight_runtime_exec.sh thin-client-assistant/runtime/moonlight_stream_profile.sh thin-client-assistant/runtime/moonlight_runtime_environment.sh thin-client-assistant/runtime/launch-moonlight.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `moonlight_resolution()`, `moonlight_video_decoder()`, and `record_decoder_choice()` with stubbed `xrandr`

### 2026-04-11 — Moonlight pairing/helper extraction

- Removed the Moonlight pairing/bootstrap/config-sync block from `thin-client-assistant/runtime/launch-moonlight.sh`:
  - added `thin-client-assistant/runtime/moonlight_pairing.sh` for Moonlight config-path discovery, host-config seeding/sync, certificate extraction, manager-side registration, list/bootstrap helpers, Sunshine PIN submission, and the `ensure_paired()` flow
  - `thin-client-assistant/runtime/launch-moonlight.sh` now sources that helper instead of carrying the pairing/bootstrap block inline
- This separates the remaining Moonlight runtime concerns much more cleanly:
  - `thin-client-assistant/runtime/launch-moonlight.sh` is now down to about `288` lines
  - target/network selection lives in `moonlight_targeting.sh`
  - pairing/bootstrap/config sync lives in `moonlight_pairing.sh`
  - the remaining launcher file is now mostly decoder/audio/display setup plus final stream execution
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/launch-moonlight.sh thin-client-assistant/runtime/moonlight_pairing.sh thin-client-assistant/runtime/moonlight_targeting.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for `moonlight_list_timeout()`, `moonlight_bootstrap_timeout()`, `json_bool()`, and exported pairing helpers
  - focused smoke test for `moonlight_client_config_path()`

### 2026-04-11 — Moonlight targeting helper extraction

- Removed the largest Moonlight host/target/API-url resolution block from `thin-client-assistant/runtime/launch-moonlight.sh`:
  - added `thin-client-assistant/runtime/moonlight_targeting.sh` for host/local-host/port resolution, IPv4 preference handling, Sunshine API URL rewriting, target reachability probes, and stream-target wait orchestration
  - `thin-client-assistant/runtime/launch-moonlight.sh` now sources that helper instead of carrying the full target-selection and reachability block inline
- This cleanly separates Moonlight target/network selection from the remaining pairing/bootstrap/stream execution logic:
  - `thin-client-assistant/runtime/launch-moonlight.sh` dropped to about `727` lines
  - the next Moonlight slice can now focus on pairing/bootstrap/config synchronization instead of mixing that with target probing and API-url rewriting
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/launch-moonlight.sh thin-client-assistant/runtime/moonlight_targeting.sh thin-client-assistant/runtime/common.sh`
  - focused smoke test for Moonlight host/local-host/port and Sunshine API URL resolution through the new helper
  - focused smoke test for `rewrite_url_host()`

### 2026-04-11 — shared X11 display helper extraction

- Removed the duplicated X11/Xauthority display-wait logic from the Moonlight and GeForce NOW launchers:
  - added `thin-client-assistant/runtime/x11_display.sh` for `detect_xauthority()`, `x_display_ready()`, `select_xauthority()`, `wait_for_x_display()`, and `wait_for_x_display_selected()`
  - `thin-client-assistant/runtime/launch-moonlight.sh` now uses the shared helper while preserving its log-emitting reselect-on-each-attempt behavior
  - `thin-client-assistant/runtime/launch-geforcenow.sh` now uses the same helper while preserving its fixed-auth-candidate wait path
  - `thin-client-assistant/runtime/common.sh` now sources the shared X11 helper seam
- This removes one of the last clear runtime duplications between the mode-specific launchers and narrows the next runtime work further toward Moonlight-specific networking and connection orchestration rather than repeated display bootstrap code.
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/common.sh thin-client-assistant/runtime/x11_display.sh thin-client-assistant/runtime/launch-geforcenow.sh thin-client-assistant/runtime/launch-moonlight.sh thin-client-assistant/runtime/open-browser-url.sh`
  - focused smoke test for `select_xauthority()` and exported X11 helper availability through `common.sh`
  - focused smoke test that `x_display_ready()` still fails cleanly for missing auth files

### 2026-04-11 — runtime value-helper extraction

- Removed the last small generic helper block from `thin-client-assistant/runtime/common.sh`:
  - added `thin-client-assistant/runtime/runtime_value_helpers.sh` for `beagle_curl_tls_args()`, `render_template()`, and `split_browser_flags()`
  - `thin-client-assistant/runtime/common.sh` now sources that helper instead of carrying the value-expansion and TLS helper logic inline
- This leaves `common.sh` as a very thin runtime composition shell:
  - `thin-client-assistant/runtime/common.sh` is now down to about `74` lines
  - the remaining logic there is primarily config discovery, mode override application, and sourcing of the extracted runtime seams
- Validation and smoke checks for this slice passed:
  - `bash -n` across the affected runtime scripts
  - focused smoke test for `render_template()` placeholder expansion
  - focused smoke test for `beagle_curl_tls_args()` and `split_browser_flags()`

### 2026-04-11 — runtime core helper extraction

- Removed the remaining shared state/logging/runtime-user baseline helpers from `thin-client-assistant/runtime/common.sh`:
  - added `thin-client-assistant/runtime/runtime_core.sh` for runtime user/group/home/uid lookup, Beagle state-dir selection, trace/marker path helpers, runtime logging, privileged command execution, unit-file presence checks, and live-medium discovery
  - `thin-client-assistant/runtime/common.sh` now sources that helper instead of carrying those generic runtime-baseline functions inline
- This turns `common.sh` into a much thinner composition shell:
  - `thin-client-assistant/runtime/common.sh` is now down to about `120` lines
  - the extracted runtime helpers now depend on an explicit shared core seam instead of implicitly reaching back into a monolith for logging/user/state behavior
- Validation and smoke checks for this slice passed:
  - `bash -n` across the affected runtime helper and launch scripts
  - focused smoke test for `beagle_log_event()`, `beagle_trace_file()`, `beagle_last_marker_file()`, and runtime user/group/home lookup through `common.sh`
  - focused smoke test for `ensure_beagle_state_dir()` candidate selection

### 2026-04-11 — runtime kiosk-session launcher extraction

- Removed the kiosk supervisor/relaunch loop from `thin-client-assistant/runtime/launch-session.sh`:
  - added `thin-client-assistant/runtime/session_launcher.sh` for `beagle_wait_for_stream_end()`, `beagle_ensure_kiosk_runtime()`, and `beagle_launch_kiosk_session()`
  - `thin-client-assistant/runtime/launch-session.sh` now only owns mode dispatch, launch-status writing, and delegation into the extracted session helper
- Runtime behavior stays the same for the kiosk path:
  - the same streaming-session wait behavior, kiosk relaunch logic, failure counting, and `beagle-kiosk-install --ensure` preflight are preserved
  - `launch-session.sh` dropped to about `74` lines, which makes the remaining runtime session orchestration explicit instead of burying it in the mode-dispatch entrypoint
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/launch-session.sh thin-client-assistant/runtime/session_launcher.sh thin-client-assistant/runtime/common.sh thin-client-assistant/runtime/launch-geforcenow.sh`
  - focused smoke test that `session_launcher.sh` exports `beagle_launch_kiosk_session()`, `beagle_wait_for_stream_end()`, and `beagle_ensure_kiosk_runtime()`
  - focused smoke test for the `beagle_wait_for_stream_end()` contract using a temporary streaming-session state file

### 2026-04-11 — runtime kiosk-control helper extraction

- Removed the remaining kiosk runtime control block from `thin-client-assistant/runtime/common.sh`:
  - added `thin-client-assistant/runtime/kiosk_runtime.sh` for kiosk process-pattern detection, window-close attempts, and the graceful-to-forceful stop flow used during GFN stream optimization
  - `thin-client-assistant/runtime/common.sh` now sources that helper instead of carrying the kiosk control block inline
- Runtime behavior stays the same for current callers:
  - `launch-geforcenow.sh` still uses `beagle_stop_kiosk_for_stream()` through `common.sh`
  - the kiosk process-pattern contract and stop escalation behavior are unchanged
- `thin-client-assistant/runtime/common.sh` dropped again and now sits at about `240` lines. The remaining larger runtime shell work is now mostly generic logging/path wrappers and the launcher/session orchestration outside the shared sourcing shell.
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/common.sh thin-client-assistant/runtime/kiosk_runtime.sh thin-client-assistant/runtime/launch-geforcenow.sh thin-client-assistant/runtime/launch-session.sh thin-client-assistant/live-build/config/includes.chroot/usr/local/sbin/beagle-runtime-heartbeat`
  - focused smoke test that `common.sh` still exposes `beagle_stop_kiosk_for_stream()` and the expected kiosk process patterns
  - focused smoke test for the `beagle_close_kiosk_window_for_stream()` contract with and without `wmctrl`

### 2026-04-11 — runtime stream-state and GFN ownership helper extraction

- Removed two more operational helper clusters from `thin-client-assistant/runtime/common.sh` without changing the runtime entrypoints:
  - added `thin-client-assistant/runtime/stream_state.sh` for stream-state path selection, streaming-session state persistence, and management timer/service suspension plus resume handling
  - added `thin-client-assistant/runtime/runtime_ownership.sh` for runtime-owned directory/file/tree helpers plus `prepare_geforcenow_environment()`
  - `thin-client-assistant/runtime/common.sh` now sources both helpers instead of keeping those blocks inline
- Runtime behavior stays the same for current callers:
  - `launch-session.sh` still checks streaming-session state through `common.sh`
  - `launch-geforcenow.sh` and `install-geforcenow.sh` still prepare the same GFN storage/home/cache/config layout through `common.sh`
  - `beagle-runtime-heartbeat` still sees the same streaming-session predicate after sourcing `common.sh`
- This closes the `common.sh` drift that `06-next-steps.md` had still called out around path ownership, GFN environment prep, and live-state persistence behavior. The remaining large runtime shell block is now mainly kiosk/session orchestration and the broader split between runtime, network, pairing, and launch surfaces.
- Validation and smoke checks for this slice passed:
  - `bash -n thin-client-assistant/runtime/common.sh thin-client-assistant/runtime/stream_state.sh thin-client-assistant/runtime/runtime_ownership.sh thin-client-assistant/runtime/launch-geforcenow.sh thin-client-assistant/runtime/install-geforcenow.sh thin-client-assistant/runtime/launch-session.sh thin-client-assistant/live-build/config/includes.chroot/usr/local/sbin/beagle-runtime-heartbeat`
  - focused smoke test for `beagle_mark_streaming_session()` / `beagle_streaming_session_active()`
  - focused smoke test for `prepare_geforcenow_environment()` storage/home/cache/config export behavior
  - `./scripts/validate-project.sh`

### 2026-04-11 — Proxmox USB preset builder extraction

- Split the Proxmox-specific USB preset contract away from the API/CLI wrapper:
  - added `thin-client-assistant/usb/proxmox_preset.py` for endpoint normalization, Proxmox login parsing, description-meta parsing, preset assembly, and preset env-line rendering
  - `thin-client-assistant/usb/pve-thin-client-proxmox-api.py` now focuses on Proxmox API transport, VM resolution, and command dispatch instead of also owning the full preset builder contract inline
  - the CLI output shape stays the same, but the Proxmox preset assembly now sits at an explicit provider seam
- This does not neutralize the thin-client Proxmox path yet, but it isolates the remaining Proxmox-shaped preset contract into one module, which is the right prerequisite for any later provider-neutral or Beagle-owned preset builder.
- Validation and smoke checks for this slice passed:
  - `python3 -m py_compile thin-client-assistant/usb/proxmox_preset.py thin-client-assistant/usb/pve-thin-client-proxmox-api.py`
  - focused smoke test for endpoint normalization plus preset generation
  - `bash -n thin-client-assistant/usb/pve-thin-client-local-installer.sh thin-client-assistant/usb/pve-thin-client-live-menu.sh thin-client-assistant/usb/pve-thin-client-usb-installer.sh`

### 2026-04-11 — runtime preset-to-config generator extraction

- Removed the largest preset→runtime env-mapping block from `thin-client-assistant/runtime/common.sh`:
  - added `thin-client-assistant/runtime/generate_config_from_preset.py` for parsing preset env files and driving `thin-client-assistant/installer/write-config.sh` with the mapped runtime/install env contract
  - `generate_config_dir_from_preset()` in `thin-client-assistant/runtime/common.sh` now delegates to that helper instead of exporting dozens of preset-derived variables inline
  - this keeps the generated `thinclient.conf`, `network.env`, `credentials.env`, and `local-auth.env` behavior unchanged while shrinking the remaining runtime-shell monolith
- This is the first explicit seam for the preset→runtime config generation path, which was one of the remaining installer/runtime drift points after the shared preset summary, enrollment writer, and status writer slices.
- Validation and smoke checks for this slice passed:
  - `python3 -m py_compile thin-client-assistant/runtime/generate_config_from_preset.py`
  - `bash -n thin-client-assistant/runtime/common.sh thin-client-assistant/installer/write-config.sh`
  - focused smoke test for preset-driven generation of `thinclient.conf`, `credentials.env`, and `local-auth.env`

### 2026-04-11 — runtime status writer extraction

- Introduced a shared runtime status helper for thin-client boot/session scripts:
  - added `thin-client-assistant/runtime/status_writer.py` for `launch.status.json` and `runtime.status` generation
  - `thin-client-assistant/runtime/launch-session.sh` now delegates launch-status JSON writes to that helper instead of carrying another inline Python block
  - `thin-client-assistant/runtime/prepare-runtime.sh` now delegates the final runtime-status file write to the same helper instead of assembling the file inline in shell
- This keeps both status file formats stable while removing another pair of shell/JSON writer implementations from the runtime entrypoints.
- Validation and smoke checks for this slice passed:
  - `python3 -m py_compile thin-client-assistant/runtime/status_writer.py`
  - `bash -n thin-client-assistant/runtime/prepare-runtime.sh thin-client-assistant/runtime/launch-session.sh`
  - focused smoke checks for `launch-status` and `runtime-status`

### 2026-04-11 — runtime enrollment-config writer extraction

- Removed the large enrollment-config inline Python block from `thin-client-assistant/runtime/prepare-runtime.sh`:
  - added `thin-client-assistant/runtime/apply_enrollment_config.py` for writing enrolled manager/sunshine credentials, runtime config env values, and USB tunnel key/known-host files from the endpoint enrollment response payload
  - `thin-client-assistant/runtime/prepare-runtime.sh` now delegates that config/credential write path to the helper instead of embedding the mapping logic inline
  - `prepare-runtime.sh` dropped by about `87` lines on this slice while preserving the existing env-file and sidecar key-file behavior
- This keeps the runtime enrollment path behavior unchanged, but it creates an explicit seam for the next runtime/installer contract-alignment slice instead of leaving that mapping buried inside the shell entrypoint.
- Validation and smoke checks for this slice passed:
  - `python3 -m py_compile thin-client-assistant/runtime/apply_enrollment_config.py`
  - `bash -n thin-client-assistant/runtime/prepare-runtime.sh`
  - focused smoke test for enrollment response application into `thinclient.conf`, `credentials.env`, `usb-tunnel.key`, and `usb-tunnel-known_hosts`

### 2026-04-11 — thin-client preset summary helper extraction

- Reduced duplicated thin-client installer preset/UI-state shaping by introducing a shared USB helper:
  - added `thin-client-assistant/usb/preset_summary.py` for streaming-mode availability, preset summary JSON, debug payload shaping, and UI-state disk inventory payloads
  - `thin-client-assistant/usb/pve-thin-client-proxmox-api.py` now derives `available_modes` through the shared helper instead of carrying its own local mode-availability rule set
  - `thin-client-assistant/usb/pve-thin-client-local-installer.sh` now calls the shared helper for `print_preset_json` and `print_ui_state_json` instead of embedding two separate inline Python blocks with overlapping preset/mode logic
- This does not make the thin-client path provider-neutral yet, but it removes another layer of duplicated installer/env-builder field shaping and keeps the local installer and the Proxmox API helper on the same preset-summary semantics.
- Validation and smoke checks for this slice passed:
  - `python3 -m py_compile thin-client-assistant/usb/preset_summary.py thin-client-assistant/usb/pve-thin-client-proxmox-api.py`
  - `bash -n thin-client-assistant/usb/pve-thin-client-local-installer.sh`
  - focused smoke checks for `preset-summary-json` and `ui-state-json`

### 2026-04-11 — hosted download-preparation helper extraction

- Removed the large inline Python blocks from `scripts/prepare-host-downloads.sh` and moved that logic behind a dedicated helper seam:
  - added `scripts/lib/prepare_host_downloads.py` for host installer/live-USB/Windows template patching, VM installer catalog generation, and downloads-status JSON generation
  - `scripts/prepare-host-downloads.sh` now acts as a thinner shell orchestrator and dropped from about `684` lines to about `340` lines
  - the helper now reuses `beagle-host/services/installer_template_patch.py` instead of carrying another local regex/template patch implementation
- Reduced installer-contract drift for the hosted VM installer catalog:
  - the VM installer metadata builder now normalizes overlapping installer/profile fields through `beagle-host/bin/endpoint_profile_contract.py` instead of reshaping those URLs inline again inside the shell script
  - the helper still preserves the previous hosted-download preset semantics, including the legacy `pve-tc-<vmid>` hostname fallback and empty embedded Proxmox credential fields
  - provider-backed VM inventory/config reads still flow through `scripts/lib/beagle_provider.py`, but the metadata/payload shaping is no longer embedded inline in the shell entrypoint
- Validation and smoke checks for this slice passed:
  - `python3 -m py_compile scripts/lib/prepare_host_downloads.py`
  - `bash -n scripts/prepare-host-downloads.sh`
  - focused smoke checks for template patching, fake-provider VM installer metadata generation, and downloads-status JSON generation through `scripts/lib/prepare_host_downloads.py`
  - `./scripts/validate-project.sh`

### 2026-04-11 — provider threading through proxy, UI integration, and server installer

- Continued threading `BEAGLE_HOST_PROVIDER` through the remaining installer/deploy edges instead of leaving those surfaces implicitly Proxmox-only:
  - `scripts/install-beagle-proxy.sh` now loads provider selection from `host.env` / `beagle-manager.env`, preserves it through sudo escalation, writes it into `beagle-proxy.env`, and logs explicitly when backend auto-detection is running under a non-Proxmox provider selection
  - `scripts/install-proxmox-ui-integration.sh` now reads provider selection from host env and skips itself cleanly when the active host provider is not `proxmox`
  - `server-installer/live-build/.../beagle-server-installer` now invokes `install-proxmox-host.sh` with `BEAGLE_HOST_PROVIDER='proxmox'` explicitly so the installed target host records the selected provider instead of relying on an implicit default
- This does not make Proxmox optional yet, but it removes more hidden assumptions that the deploy/install chain can silently rely on the Proxmox provider without passing or documenting provider selection.
- Validation for this slice passed:
  - `bash -n scripts/install-beagle-proxy.sh scripts/install-proxmox-ui-integration.sh server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
  - `./scripts/validate-project.sh`

### 2026-04-11 — host-provider registry lazy loading and runtime env threading

- Continued the provider-abstraction work across deploy/install/runtime boundaries instead of leaving provider selection as a control-plane-only detail:
  - `beagle-host/providers/registry.py` no longer imports `ProxmoxHostProvider` directly at module import time
  - the registry now supports lazy provider-module loading through `register_provider_module(...)` and resolves concrete provider factories only when `create_provider(...)` is called
  - `list_providers()` now reflects both eagerly registered factories and module-registered providers, which makes the registry ready for additional providers without re-centralizing import wiring
- Threaded `BEAGLE_HOST_PROVIDER` through the host install/runtime scripts:
  - `scripts/install-proxmox-host.sh` now carries `BEAGLE_HOST_PROVIDER` through sudo escalation, records it in `/etc/beagle/host.env`, and passes it into `install-proxmox-host-services.sh`
  - `scripts/install-proxmox-host-services.sh` now preserves `BEAGLE_HOST_PROVIDER` through sudo escalation and writes it into `/etc/beagle/beagle-manager.env`
  - `scripts/refresh-host-artifacts.sh` now preserves and exports `BEAGLE_HOST_PROVIDER` so refresh/package paths run under the same host-provider selection
  - `scripts/check-proxmox-host.sh` now validates the selected provider config and checks that the matching runtime provider file is installed alongside the registry and contract files
  - `scripts/setup-proxmox-host.sh` usage text now documents `BEAGLE_HOST_PROVIDER` explicitly so operator flows stop treating provider selection as an undocumented hidden input
- Validation and smoke checks for this slice all passed:
  - `python3 -m py_compile beagle-host/providers/registry.py`
  - `bash -n scripts/install-proxmox-host.sh scripts/install-proxmox-host-services.sh scripts/check-proxmox-host.sh scripts/refresh-host-artifacts.sh scripts/setup-proxmox-host.sh`
  - focused smoke checks for lazy registry module loading and provider creation
  - `./scripts/validate-project.sh`

### 2026-04-11 — script-side sync guest-exec provider seam

- Extended `scripts/lib/beagle_provider.py` with a synchronous guest-exec contract:
  - added `guest_exec_bash_sync(...)`
  - added the CLI command `guest-exec-bash-sync-b64`
  - the helper now owns the `qm guest exec` plus `qm guest exec-status` polling loop for script consumers instead of leaving that wait logic duplicated in shell scripts
- Moved more script-side guest-exec and VM-write call paths behind the provider helper seam:
  - `scripts/configure-sunshine-guest.sh` now prefers the new synchronous helper command instead of issuing provider-helper `guest-exec` plus separate `guest-exec-status` calls itself
  - `scripts/ensure-vm-stream-ready.sh` now uses the same synchronous helper path for Sunshine status probing, and its direct `qm` fallback now also performs an explicit `exec-status` polling loop instead of assuming the initial `qm guest exec` payload is the final result
  - `scripts/optimize-proxmox-vm-for-beagle.sh` now caches provider-helper availability and uses safer quoted fallback command execution for the remaining direct `qm set` compatibility path
  - `scripts/configure-sunshine-guest.sh` now also caches provider-helper availability so repeated SSH `test -f` probes do not sit in every helper call
- Validation and smoke checks for this slice all passed:
  - `python3 -m py_compile scripts/lib/beagle_provider.py`
  - `bash -n scripts/configure-sunshine-guest.sh scripts/ensure-vm-stream-ready.sh scripts/optimize-proxmox-vm-for-beagle.sh`
  - focused smoke checks for `guest_exec_bash_sync(...)`
  - `./scripts/validate-project.sh`

### 2026-04-11 — remaining authenticated admin and endpoint-lifecycle surface extraction

- Extracted the remaining authenticated non-VM write surface out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/admin_http_surface.py`:
  - `AdminHttpSurfaceService` now owns route matching, validation, queueing, and response shaping for policy create/update/delete, bulk action queueing, ubuntu-beagle VM creation, generic provisioning create, and provisioning update
  - the service composes the already-extracted policy store, action queue, and ubuntu-beagle provisioning seams instead of leaving that admin-facing HTTP mutation block inline in the entrypoint
- Extracted the remaining endpoint enrollment/check-in HTTP surface into `beagle-host/services/endpoint_lifecycle_surface.py`:
  - `EndpointLifecycleSurfaceService` now owns route matching, scope validation, enrollment error mapping, endpoint check-in report persistence, and response shaping for `/api/v1/endpoints/enroll` and `/api/v1/endpoints/check-in`
  - `EndpointReportService` gained a dedicated `store(...)` seam so endpoint check-in persistence no longer writes JSON files directly from the control-plane handler
- Rewired the control-plane entrypoint to delegate those route families instead of rebuilding them inline:
  - `beagle-control-plane.py` now only performs the auth gate and generic JSON-body read before handing off to `AdminHttpSurfaceService` and `EndpointLifecycleSurfaceService`
  - `scripts/install-proxmox-host-services.sh` now installs both new surface modules into the deployed host runtime
- Validation and smoke checks for this slice all passed:
  - `python3 -m py_compile beagle-host/services/admin_http_surface.py beagle-host/services/endpoint_lifecycle_surface.py beagle-host/services/endpoint_report.py beagle-host/bin/beagle-control-plane.py`
  - `bash -n scripts/install-proxmox-host-services.sh`
  - focused smoke checks for `AdminHttpSurfaceService`, `EndpointLifecycleSurfaceService`, and the new `EndpointReportService.store(...)` seam
  - `./scripts/validate-project.sh`
- Current size marker after this slice:
  - `beagle-host/bin/beagle-control-plane.py` is down to about `2354` lines

### 2026-04-11 — host authenticated VM mutation surface extraction

- Extracted the remaining single-VM authenticated mutation POST cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/vm_mutation_surface.py`:
  - `VmMutationSurfaceService` now owns route matching, validation, queueing, and response shaping for VM installer-prep start, OS update queueing, generic VM actions, USB refresh, USB attach/detach orchestration, and Sunshine access-ticket issuance
  - the service now composes the already-extracted action queue, installer-prep, VM USB, and Sunshine integration seams instead of keeping that per-VM mutation logic inline in the HTTP entrypoint
- Rewired the control-plane entrypoint to delegate that authenticated VM mutation cluster through `VmMutationSurfaceService`:
  - `beagle-control-plane.py` now only performs the auth gate plus required/optional JSON-body reads before handing off to the service
  - `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/vm_mutation_surface.py` into the deployed host runtime
- Validation and smoke checks for this slice all passed:
  - `python3 -m py_compile beagle-host/services/vm_mutation_surface.py beagle-host/bin/beagle-control-plane.py`
  - `bash -n scripts/install-proxmox-host-services.sh`
  - focused smoke checks for `VmMutationSurfaceService` queueing, USB orchestration, and Sunshine access response shaping
  - `./scripts/validate-project.sh`
- Current size marker after this slice:
  - `beagle-host/bin/beagle-control-plane.py` is down to about `2468` lines

### 2026-04-11 — host public sunshine proxy extraction

- Extracted the public Sunshine proxy flow out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/public_sunshine_surface.py`:
  - `PublicSunshineSurfaceService` now owns ticket resolution, proxy request dispatch, and proxy-vs-error response shaping for the public Sunshine GET/POST surface
  - the service composes the existing Sunshine integration seam instead of leaving ticket lookup and proxy orchestration duplicated between `do_GET` and `do_POST`
- Rewired the control-plane entrypoint to delegate the public Sunshine proxy in both directions:
  - `beagle-control-plane.py` now only performs the generic proxy response write and, for POST, the binary-body read before handing off to the service
  - the entrypoint-local `_sunshine_ticket_vm(...)` helper is gone
  - `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/public_sunshine_surface.py` into the deployed host runtime
- Validation and smoke checks for this slice all passed:
  - `python3 -m py_compile beagle-host/services/public_sunshine_surface.py beagle-host/bin/beagle-control-plane.py`
  - `bash -n scripts/install-proxmox-host-services.sh`
  - focused smoke checks for `PublicSunshineSurfaceService` route handling and proxy/error response shaping
  - `./scripts/validate-project.sh`
- Current size marker after this slice:
  - `beagle-host/bin/beagle-control-plane.py` is at about `2717` lines

### 2026-04-11 — host endpoint POST-surface extraction

- Extracted the endpoint-authenticated POST surface for Moonlight registration, action pull/result, and support-bundle upload out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/endpoint_http_surface.py`:
  - `EndpointHttpSurfaceService` now owns the route matching, scope validation, payload shaping, and response envelopes for `/api/v1/endpoints/moonlight/register`, `/api/v1/endpoints/actions/pull`, `/api/v1/endpoints/actions/result`, and `/api/v1/endpoints/support-bundles/upload`
  - the service now composes the already-extracted action queue, support-bundle store, Sunshine integration, and VM lookup seams instead of reassembling those endpoint-facing POST flows inline in the HTTP entrypoint
- Rewired the control-plane entrypoint to delegate that endpoint-facing POST cluster through `EndpointHttpSurfaceService`:
  - `beagle-control-plane.py` now only performs the endpoint-auth gate plus generic JSON/binary body reads before handing off to the service
  - `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/endpoint_http_surface.py` into the deployed host runtime
- Validation and smoke checks for this slice all passed:
  - `python3 -m py_compile beagle-host/services/endpoint_http_surface.py beagle-host/bin/beagle-control-plane.py`
  - `bash -n scripts/install-proxmox-host-services.sh`
  - focused smoke checks for `EndpointHttpSurfaceService` route handling, scope validation, and response shaping
  - `./scripts/validate-project.sh`
- Current size marker after this slice:
  - `beagle-host/bin/beagle-control-plane.py` is down to about `2713` lines

### 2026-04-11 — host public ubuntu-install POST-surface extraction

- Extracted the public Ubuntu install lifecycle POST block out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/public_ubuntu_install_surface.py`:
  - `PublicUbuntuInstallSurfaceService` now owns the route matching and payload shaping for `public/ubuntu-install/<token>/complete`, `prepare-firstboot`, and `failed`
  - the service now composes the already-extracted ubuntu-beagle provisioning, ubuntu-beagle state, and scheduled-restart cancellation seams instead of mutating/installing that lifecycle state inline in the HTTP entrypoint
- Rewired the control-plane entrypoint to delegate those public install POST routes instead of rebuilding the same lifecycle transitions inline:
  - `beagle-control-plane.py` now only does the optional JSON-body read for the `failed` route and the final response write for this surface
  - `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/public_ubuntu_install_surface.py` into the deployed host runtime
- Validation and smoke checks for this slice all passed:
  - `python3 -m py_compile beagle-host/services/public_ubuntu_install_surface.py beagle-host/bin/beagle-control-plane.py`
  - `bash -n scripts/install-proxmox-host-services.sh`
  - focused smoke checks for `PublicUbuntuInstallSurfaceService` route handling and lifecycle payload shaping
  - `./scripts/validate-project.sh`
- Current size marker after this slice:
  - `beagle-host/bin/beagle-control-plane.py` is down to about `2832` lines

### 2026-04-11 — host public/read and endpoint-update surface extraction

- Extracted the next public/endpoint-facing GET cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/public_http_surface.py`:
  - `PublicHttpSurfaceService` now owns the route matching and payload shaping for `public/vms/<vmid>/state`, `public/vms/<vmid>/endpoint`, and the intentionally forbidden public installer-download routes
  - the same service now also owns the endpoint-authenticated update-feed response assembly for `/api/v1/endpoints/update-feed`, including query parsing and VM/identity verification against the existing extracted update-feed/profile seams
- Rewired the control-plane entrypoint to delegate those public and endpoint-facing reads instead of rebuilding them inline:
  - `beagle-control-plane.py` now keeps that area at sunshine-proxy dispatch, auth checks, and final response writing only
  - the now-obsolete entrypoint-local `_endpoint_summary_for_vmid(...)` and `_vm_state_for_vmid(...)` helpers are gone
  - `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/public_http_surface.py` into the deployed host runtime
- Validation and smoke checks for this slice all passed:
  - `python3 -m py_compile beagle-host/services/public_http_surface.py beagle-host/bin/beagle-control-plane.py`
  - `bash -n scripts/install-proxmox-host-services.sh`
  - focused smoke checks for `PublicHttpSurfaceService` route handling and endpoint update-feed shaping
  - `./scripts/validate-project.sh`
- Current size marker after this slice:
  - `beagle-host/bin/beagle-control-plane.py` is down to about `2899` lines

### 2026-04-11 — host non-VM read-surface extraction

- Extracted the next non-VM GET response cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/control_plane_read_surface.py`:
  - `ControlPlaneReadSurfaceService` now owns the route matching and payload/download shaping for `provisioning/catalog`, `provisioning/vms/<vmid>`, `endpoints`, `policies`, `policies/<name>`, and `support-bundles/<bundle_id>/download`
  - the service now composes the already-extracted provisioning, endpoint-report, policy-store, and support-bundle-store collaborators instead of rebuilding those HTTP envelopes inline in the control-plane entrypoint
- Rewired the control-plane entrypoint to delegate that whole read surface through `control_plane_read_surface_service().route_get(path)`:
  - `beagle-control-plane.py` now keeps that area at routing/response-writing level only
  - `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/control_plane_read_surface.py` into the deployed host runtime
- Validation and smoke checks for this slice all passed:
  - `python3 -m py_compile beagle-host/services/control_plane_read_surface.py beagle-host/bin/beagle-control-plane.py`
  - `bash -n scripts/install-proxmox-host-services.sh`
  - focused smoke checks for `ControlPlaneReadSurfaceService` route handling and download/payload shaping
  - `./scripts/validate-project.sh`
- Current size marker after this slice:
  - `beagle-host/bin/beagle-control-plane.py` is down to about `2961` lines

### 2026-04-11 — host VM HTTP-surface extraction

- Extracted the inline `/api/v1/vms/...` GET response-model/download block out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/vm_http_surface.py`:
  - `VmHttpSurfaceService` now owns the VM subresource route matching for `installer.sh`, `live-usb.sh`, `installer.ps1`, `credentials`, `installer-prep`, `policy`, `support-bundles`, `usb`, `update`, `state`, `actions`, `endpoint`, and the base VM profile payload
  - the service now shapes the JSON envelopes and download payload descriptors for those routes while keeping the handler responsible only for request dispatch and writing the response body
- Rewired the control-plane entrypoint to consume the new service instead of rebuilding those payloads inline:
  - `beagle-control-plane.py` now delegates the whole `/api/v1/vms/...` GET block to `vm_http_surface_service().route_get(path)`
  - `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/vm_http_surface.py` into the deployed host runtime
- Validation and smoke checks for this slice all passed:
  - `python3 -m py_compile beagle-host/services/vm_http_surface.py beagle-host/bin/beagle-control-plane.py`
  - `bash -n scripts/install-proxmox-host-services.sh`
  - focused smoke checks for `VmHttpSurfaceService` route handling and payload shaping
  - `./scripts/validate-project.sh`
- Current size marker after this slice:
  - `beagle-host/bin/beagle-control-plane.py` is down to about `3013` lines

### 2026-04-11 — host metadata-support extraction

- Extracted the remaining host-side VM description/hostname helper block out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/metadata_support.py`:
  - `MetadataSupportService` now owns `parse_description_meta(description)` and `safe_hostname(name, vmid)`
  - the existing control-plane helper names remain as thin wrappers, so callers and HTTP handlers kept their current surface
- Rewired the extracted host services to consume the metadata seam directly instead of monolith-local helper implementations:
  - `PublicStreamService` now receives `parse_description_meta` from `MetadataSupportService`
  - `SunshineIntegrationService` now receives `parse_description_meta` from `MetadataSupportService`
  - `VmProfileService` now receives both `parse_description_meta` and `safe_hostname` from `MetadataSupportService`
  - `InstallerScriptService` now receives both `parse_description_meta` and `safe_hostname` from `MetadataSupportService`
  - `UbuntuBeagleProvisioningService` now receives `safe_hostname` from `MetadataSupportService`
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/metadata_support.py` into the deployed host runtime
- Validation and smoke checks for this slice all passed:
  - `python3 -m py_compile beagle-host/services/metadata_support.py beagle-host/bin/beagle-control-plane.py`
  - `bash -n scripts/install-proxmox-host-services.sh`
  - focused smoke checks for `MetadataSupportService`
  - `./scripts/validate-project.sh`
- Current size marker after this slice:
  - `beagle-host/bin/beagle-control-plane.py` is at about `3275` lines

### 2026-04-11 — script-side guest-exec and VM-write helper expansion

- Expanded `scripts/lib/beagle_provider.py` from a read-only helper into the first shared script-side execution/write seam:
  - added `guest_exec_bash(vmid, command, timeout_seconds=...)`
  - added `guest_exec_status(vmid, pid)`
  - added `set_vm_options(vmid, option_pairs)`
  - added `set_vm_description(vmid, description)`
  - added `reboot_vm(vmid)`
  - added CLI commands `guest-exec-bash-b64`, `guest-exec-status`, `set-vm-options`, `set-vm-description-b64`, and `reboot-vm`
- Moved more mutation-heavy script flows onto the provider helper while preserving the old direct-path fallback where rollout compatibility still matters:
  - `scripts/configure-sunshine-guest.sh` now prefers the installed helper for `qm guest exec`, `qm guest exec-status`, `qm config` description reads, `qm set --description`, and `qm reboot`
  - those flows still fall back to the previous direct `qm` commands when the helper is unavailable on the target host, which keeps partially updated hosts working
  - `scripts/ensure-vm-stream-ready.sh` now prefers the helper for the Sunshine guest-status `qm guest exec` probe, with a direct `qm guest exec` fallback
  - `scripts/optimize-proxmox-vm-for-beagle.sh` now prefers the installed helper for the repeated `qm set` baseline writes, with the old direct `qm set` path retained as fallback
- Validation and smoke checks for this slice all passed:
  - `python3 -m py_compile scripts/lib/beagle_provider.py`
  - `bash -n scripts/configure-sunshine-guest.sh scripts/ensure-vm-stream-ready.sh scripts/optimize-proxmox-vm-for-beagle.sh`
  - focused smoke checks for the new guest-exec/write helper functions in `scripts/lib/beagle_provider.py`
  - `./scripts/validate-project.sh`

### 2026-04-11 — remote script-side provider reads for Sunshine guest setup

- Continued the script/provider migration by extending `scripts/lib/beagle_provider.py` with reusable VM-node and raw-description helpers:
  - added `vm_node(vmid)`
  - added `vm_description_text(node, vmid)` and `vm_description_text_for_vmid(vmid)`
  - added CLI commands for `vm-node` and `vm-description` alongside the existing read commands
- Moved more Sunshine-setup reads behind the provider-facing helper seam without changing the current write/guest-exec behavior:
  - `scripts/configure-sunshine-guest.sh` now prefers the installed/shared provider helper for guest IPv4 detection and current VM description lookup
  - the script now resolves the helper path as local repo path for localhost targets and as `/opt/beagle/scripts/lib/beagle_provider.py` for remote installed hosts by default
  - new env overrides `BEAGLE_REMOTE_INSTALL_DIR` and `BEAGLE_REMOTE_PROVIDER_MODULE_PATH` make that remote helper path explicit and adjustable
  - if the helper is missing or the helper call fails, the script deliberately falls back to the previous direct `qm guest cmd` / `qm config` reads so operator behavior stays intact
- Simplified another host-side read callsite to the shared helper CLI:
  - `scripts/ensure-vm-stream-ready.sh` now resolves guest IPv4 through `python3 "$PROVIDER_MODULE_PATH" guest-ipv4 "$VMID"` instead of re-embedding the guest-interface parsing logic inline
- Validation and smoke checks for this slice all passed:
  - `python3 -m py_compile scripts/lib/beagle_provider.py`
  - `bash -n scripts/configure-sunshine-guest.sh scripts/ensure-vm-stream-ready.sh`
  - focused smoke checks for the expanded `scripts/lib/beagle_provider.py`
  - `./scripts/validate-project.sh`

### 2026-04-11 — host utility support and richer script-provider reads

- Extracted the remaining shared slug/secret/PIN helper cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/utility_support.py`:
  - `UtilitySupportService` now owns `safe_slug(...)`, `random_secret(...)`, and `random_pin()`
  - the public helper names in the control plane stay stable as thin wrappers, so existing handlers and service collaborators kept their current call surface
- Rewired the already-extracted host services to depend on the utility seam instead of the monolith-local helper implementations:
  - `ActionQueueService`, `SupportBundleStoreService`, `PolicyStoreService`, `VmSecretStoreService`, `VmSecretBootstrapService`, `InstallerPrepService`, `UbuntuBeagleStateService`, `UbuntuBeagleProvisioningService`, `PublicStreamService`, and `SunshineIntegrationService` now receive utility callbacks from `UtilitySupportService`
  - `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/utility_support.py` into the deployed host runtime
- Expanded `scripts/lib/beagle_provider.py` beyond low-level reads so scripts can share more provider-facing logic instead of re-implementing it inline:
  - added `parse_description_meta(description)`
  - added `find_vm_record(vmid)`
  - added `vm_description_meta(node, vmid)` plus `vm_description_meta_for_vmid(vmid)`
  - added `first_guest_ipv4(vmid)`
  - added CLI access for `guest-ipv4` and `vm-description-meta`
- Moved more script-side read logic behind the shared provider seam:
  - `scripts/reconcile-public-streams.sh` now imports description-meta parsing and guest IPv4 resolution from `scripts/lib/beagle_provider.py` instead of embedding those helpers inline
  - `scripts/prepare-host-downloads.sh` now imports shared description-meta parsing from the same helper instead of carrying another local copy
  - `scripts/install-beagle-proxy.sh` now resolves backend candidate metadata through `vm_description_meta_for_vmid(...)` and guest IPv4 through `first_guest_ipv4(...)` instead of rebuilding those reads locally
- Validation and smoke checks for this slice all passed:
  - `python3 -m py_compile beagle-host/services/utility_support.py beagle-host/bin/beagle-control-plane.py scripts/lib/beagle_provider.py`
  - `bash -n scripts/install-proxmox-host-services.sh scripts/install-beagle-proxy.sh scripts/reconcile-public-streams.sh scripts/prepare-host-downloads.sh`
  - focused smoke checks for `UtilitySupportService` and the expanded `scripts/lib/beagle_provider.py`
  - `./scripts/validate-project.sh`
- Current size markers after this slice:
  - `beagle-host/bin/beagle-control-plane.py` is at about `3283` lines
  - `proxmox-ui/beagle-ui.js` remains at about `344` lines

### 2026-04-11 — shared browser common extraction

- Reduced duplicated browser-side config/token/API helper logic across the main browser surfaces by introducing `core/platform/browser-common.js`:
  - `BeagleBrowserCommon` now owns session-token store creation, URL template filling, no-cache URL decoration, health-to-manager URL derivation, Beagle API path normalization, base/path joining, and `beagle_token` hash injection
  - `proxmox-ui/beagle-ui-common.js` and `extension/common.js` now delegate those shared helpers instead of maintaining parallel implementations
  - `website/app.js` now uses the same session-token store helper instead of carrying its own local `sessionStorage` probe/write/remove block
- Finished the browser runtime wiring across all three browser surfaces:
  - `scripts/install-proxmox-ui-integration.sh` now installs `/pve2/js/beagle-browser-common.js` and injects it before `beagle-ui-common.js`
  - the extension now loads `core/platform/browser-common.js` before `common.js` in both the content-script chain and `options.html`
  - `website/index.html` now loads `/core/platform/browser-common.js`, and `scripts/install-beagle-proxy.sh` exposes that asset through nginx for the deployed website surface
- Kept behavior stable while shrinking local duplication:
  - Proxmox UI and extension still use the same session token key and `beagle_token` URL-hash behavior as before
  - manager/control-plane URL shaping still preserves the current `/api/v1/health` to manager-base contract
  - no-cache URL handling still preserves the same `_beagle_ts` query parameter semantics

### 2026-04-11 — install-beagle-proxy read-path migration

- Continued the script/provider decoupling by moving the remaining pure VM-read paths in `scripts/install-beagle-proxy.sh` behind `scripts/lib/beagle_provider.py`:
  - backend candidate guest-IP lookup now resolves guest interfaces through the provider helper instead of raw `qm guest cmd`
  - backend description metadata lookup now resolves VM inventory/config through the provider helper instead of raw `qm config`
  - backend auto-detection now enumerates candidate VMIDs through the provider helper instead of raw `qm list`
- Kept the migration intentionally read-only and incremental:
  - the proxy installer now has no direct `qm` / `pvesh` read dependency left for backend detection
  - mutation-heavy script flows are still deferred until the helper contract grows beyond read operations

### 2026-04-11 — Proxmox UI fleet/provisioning state-flow extraction

- Continued shrinking `proxmox-ui/beagle-ui.js` by moving the remaining catalog/fleet orchestration out of the entrypoint:
  - added `proxmox-ui/state/fleet.js`, where `BeagleUiFleetState.loadFleetPayload()` now owns the combined health/inventory/policies/catalog fetch
  - added `proxmox-ui/provisioning/flow.js`, where `BeagleUiProvisioningFlow` now owns provisioning-catalog/state fetches plus the result-window/create-modal orchestration around the existing provisioning components
  - `proxmox-ui/beagle-ui.js` now stays focused on dependency lookup, thin browser action wrappers, modal dispatch, and `boot()`
- Finished the runtime wiring so the Proxmox UI entrypoint no longer owns the remaining fleet/provisioning orchestration directly:
  - fleet loading now goes through `BeagleUiFleetState` instead of an inline `Promise.all(...)` block
  - provisioning create/result flows now go through `BeagleUiProvisioningFlow` instead of local wrapper functions that rebuilt the same collaborator graph in `beagle-ui.js`
  - unused helper wrappers (`getInstallerEligibilityKey`, unused provisioning API wrappers, unused USB-formatting wrappers) are gone from the entrypoint
- `scripts/install-proxmox-ui-integration.sh` now installs the new `beagle-ui-fleet-state.js` and `beagle-ui-provisioning-flow.js` assets and injects them into the Proxmox UI load order before `beagle-ui.js`
- `scripts/validate-project.sh` now syntax-checks the new UI modules
- `proxmox-ui/beagle-ui.js` first dropped from `410` to `350` lines with this slice and now sits at `344` lines after the follow-up shared-browser-common cleanup

### 2026-04-11 — script-side provider read helper extraction

- Introduced `scripts/lib/beagle_provider.py` as the first provider-neutral script helper for host-side virtualization reads:
  - the helper currently exposes `provider_kind()`, `list_vms()`, `vm_config(node, vmid)`, and `guest_interfaces(vmid)`
  - `pve` aliases normalize to `proxmox`, so scripts now have one provider-facing read seam even though Proxmox is still the only concrete script backend today
- Moved the first script-side read paths behind the helper instead of leaving raw Proxmox commands spread across inline Python blocks:
  - `scripts/reconcile-public-streams.sh` now reads VM inventory, VM config, and guest interfaces through `scripts/lib/beagle_provider.py`
  - `scripts/prepare-host-downloads.sh` now reads VM inventory and VM config through the same helper while keeping installer metadata generation behavior unchanged
  - `scripts/ensure-vm-stream-ready.sh` now resolves VM description metadata and guest IPv4 lookup through the helper instead of calling `qm config` / `qm guest cmd` directly for those read paths
- Kept the migration incremental and non-breaking:
  - guest-exec/write paths such as `qm guest exec`, `qm set`, and provider-specific install flows remain in place for now
  - the new helper only covers the first reusable read contract so additional scripts can migrate without cloning more raw `pvesh` / `qm guest cmd` code
- Smoke-tested the new helper outside the scripts:
  - provider-kind normalization still maps `pve` to `proxmox`
  - list/config/guest-interface helper calls still shape the expected JSON payloads for downstream scripts

### 2026-04-11 — time support extraction

- Extracted the remaining UTC timestamp helper cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/time_support.py`:
  - `TimeSupportService` now owns `utcnow()`, `parse_utc_timestamp(value)`, and `timestamp_age_seconds(value)`
  - the control-plane helper names stay stable as thin wrappers, so existing host services and handlers kept their current collaborator surface
- Finished the wiring so shared timestamp logic no longer lives inline in the entrypoint:
  - ISO timestamp generation and parsing now live behind one explicit service instead of being repeated as module-local helpers
  - age calculation now reuses the same injected clock as `utcnow()`, making timestamp behavior testable without reaching into the HTTP entrypoint
  - all existing services that already consume `utcnow` / `parse_utc_timestamp` / `timestamp_age_seconds` kept their signatures unchanged
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/time_support.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - fixed-clock `utcnow()` still emits the same ISO-8601 value
  - valid timestamps still parse, invalid timestamps still return `None`
  - age calculation still returns the same positive-second delta and still returns `None` for empty inputs

### 2026-04-11 — runtime paths extraction

- Extracted the remaining runtime data-root and managed-directory helper cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/runtime_paths.py`:
  - `RuntimePathsService` now owns `ensure_data_dir()`, `data_dir()`, `endpoints_dir()`, `actions_dir()`, `support_bundles_dir()`, and `policies_dir()`
  - the control-plane helper names stay stable as thin wrappers, so downstream services and handlers did not need path-signature changes
- Finished the wiring so data-root and managed subdirectory creation no longer live inline in the entrypoint:
  - preferred-data-dir vs fallback-data-dir selection now lives behind the dedicated runtime-path seam instead of in a nested helper inside `ensure_data_dir()`
  - service factories that previously captured `EFFECTIVE_DATA_DIR` now bind to `runtime_paths_service().data_dir`, so path resolution is no longer spread across lambdas and a global mutable variable
  - the legacy `EFFECTIVE_DATA_DIR` runtime-global is gone from the service composition path; startup now logs the resolved data dir directly from the runtime-path seam
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/runtime_paths.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - preferred data-root creation still succeeds and creates the expected `endpoints`, `actions`, `support-bundles`, and `policies` subdirectories
  - simulated `PermissionError` on the preferred root still falls back to `/run`-style behavior through the injected fallback path
  - managed directory chmod calls still preserve the existing `0700` semantics
- `beagle-control-plane.py` dropped from `3293` to `3276` lines across the time/runtime-path slices, and the host-side extracted-service module count moved from `30` to `32`

### 2026-04-11 — persistence support extraction

- Extracted the remaining file/JSON persistence helper cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/persistence_support.py`:
  - `PersistenceSupportService` now owns `load_json_file(path, fallback)` and `write_json_file(path, payload, mode=...)`
  - the control-plane helper names stay stable as thin wrappers, so the extracted host services that already consume those helpers did not need signature changes
- Finished the wiring so shared JSON/file persistence no longer lives inline in the entrypoint:
  - parent-directory creation, pretty-printed JSON output, trailing newline handling, and best-effort chmod now live behind the dedicated persistence seam
  - missing-file and invalid-JSON fallback handling is now testable without reaching into the HTTP entrypoint
  - existing host services still receive the same `load_json_file` / `write_json_file` collaborators, but those helpers now delegate into `PersistenceSupportService`
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/persistence_support.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - JSON write/read round-trips still preserve the existing pretty-print contract
  - missing files still return the supplied fallback
  - invalid JSON still returns the supplied fallback instead of raising

### 2026-04-11 — request support extraction

- Extracted the remaining bearer-token / origin-normalization / CORS-origin helper cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/request_support.py`:
  - `RequestSupportService` now owns `extract_bearer_token(...)`, `normalized_origin(...)`, and `cors_allowed_origins()`
  - the control-plane helper names stay stable as thin wrappers, so the HTTP handlers did not need payload or call-shape changes
- Finished the wiring so request/origin policy no longer lives inline in the entrypoint:
  - `cors-allowed-origins` caching now lives behind the dedicated request-support seam instead of being assembled directly in `beagle-control-plane.py`
  - public manager / web UI / stream host / configured Proxmox UI port origin synthesis now happens in one explicit service
  - Authorization bearer-token parsing and origin normalization are now isolated from the HTTP handler class
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/request_support.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - bearer-token extraction still strips the `Bearer ` prefix exactly as before
  - origin normalization still collapses default ports and rejects non-HTTP(S) schemes
  - computed CORS origins still include manager/web/stream/custom origins and still use the runtime cache
- `beagle-control-plane.py` dropped from `3322` to `3293` lines across the persistence/request slices, and the host-side extracted-service module count moved from `28` to `30`

### 2026-04-11 — runtime exec extraction

- Extracted the remaining command-wrapper helper cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/runtime_exec.py`:
  - `RuntimeExecService` now owns `run_json(...)`, `run_text(...)`, and `run_checked(...)`
  - the control-plane helper names stay stable as thin wrappers, so host-provider bootstrap and existing service collaborators did not need signature changes
- Finished the runtime-exec wiring so subprocess timeout/default handling no longer lives inline in the entrypoint:
  - the default-timeout sentinel and timeout normalization are now handled by `RuntimeExecService`
  - `HOST_PROVIDER` bootstrap still receives the same wrappers, but they now delegate into the dedicated runtime-exec seam
  - the entrypoint no longer owns the repeated `subprocess.run(...capture_output...)` blocks for JSON/text/checked execution
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/runtime_exec.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - default timeout application still works when the sentinel is passed
  - JSON parsing still returns `None` on invalid JSON and command failure
  - text execution still returns `""` on missing commands and command errors
  - checked execution still returns stdout on success and keeps exception behavior on failure
- `beagle-control-plane.py` dropped from `3342` to `3322` lines with this slice, and the host-side extracted-service module count moved from `27` to `28`

### 2026-04-11 — runtime support extraction

- Extracted the remaining cache / shell-environment helper cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/runtime_support.py`:
  - `RuntimeSupportService` now owns `cache_get(...)`, `cache_put(...)`, `cache_invalidate(...)`, and `load_shell_env_file(path)`
  - the control-plane helper names stay stable as thin wrappers, so `HOST_PROVIDER` bootstrap, `DownloadMetadataService`, CORS-origin caching, and default-credential loading did not need surface changes
- Finished the wiring so cache and shell-env state no longer live inline in the entrypoint:
  - module-local `_CACHE` state is gone from `beagle-control-plane.py`
  - `DEFAULT_CREDENTIALS` now loads through the dedicated runtime-support seam instead of the inline parser
  - provider bootstrap still receives `cache_get` / `cache_put`, but those helpers now delegate into `RuntimeSupportService`
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/runtime_support.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - cache insert, TTL expiry, and invalidation still behave the same
  - shell env parsing still ignores comments/invalid lines and still strips wrapped `'` / `"` quotes the same way as before
  - missing env files still return an empty mapping
- `beagle-control-plane.py` dropped from `3361` to `3342` lines with this slice, and the host-side extracted-service module count moved from `26` to `27`

### 2026-04-11 — ubuntu-beagle restart-state extraction

- Extracted the scheduled ubuntu-beagle host-restart helper cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/ubuntu_beagle_restart.py`:
  - `UbuntuBeagleRestartService` now owns `schedule(vmid, ...)`, `ensure_restart_state(state, vmid)`, `restart_running(restart_state)`, and `cancel(state)`
  - the control-plane helper names `schedule_ubuntu_beagle_vm_restart(...)` and `cancel_scheduled_ubuntu_beagle_vm_restart(...)` stay stable as thin wrappers, while a new thin wrapper `ensure_ubuntu_beagle_vm_restart_state(...)` feeds the provisioning service
- Finished the restart-state wiring so the entrypoint no longer owns process-group cancellation or host-restart state transitions:
  - `UbuntuBeagleProvisioningService` now depends on `ensure_ubuntu_beagle_vm_restart_state(...)` instead of checking `host_restart` PIDs inline and scheduling directly
  - the public ubuntu-install failure handlers still emit the same `host_restart_cancelled` payload shape, but now get that result from the dedicated restart service
  - `signal` import and direct `os.killpg(...)` usage are gone from `beagle-control-plane.py`
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/ubuntu_beagle_restart.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - scheduling still enforces the minimum wait timeout and returns the same `{vmid, pid, wait_timeout_seconds, scheduled_at}` shape
  - `ensure_restart_state(...)` still reuses a live restart PID and reschedules when no active restart exists
  - cancellation still returns the existing `cancelled_at` / `cancelled` / `reason` semantics, including the current pid-`0` edge case where only `host_restart` is cleared
- `beagle-control-plane.py` dropped from `3370` to `3361` lines with this slice, and the host-side extracted-service module count moved from `25` to `26`

### 2026-04-11 — endpoint enrollment and bootstrap extraction

- Extracted the endpoint enrollment / bootstrap helper cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/endpoint_enrollment.py`:
  - `EndpointEnrollmentService` now owns `issue_enrollment_token(vm)` and `enroll_endpoint(payload)`
  - the control-plane helper name `issue_enrollment_token(...)` stays stable as a thin wrapper, so `InstallerScriptService` and installer-generation flows kept their existing collaborator surface
- Moved the non-HTTP endpoint bootstrap response shaping behind the new service seam:
  - enrollment-token TTL math, thin-client password lookup, endpoint-token issuance, Sunshine pinned-pubkey backfill, and endpoint config payload assembly no longer live inline in the HTTP entrypoint
  - `/api/v1/endpoints/enroll` now maps HTTP status codes to domain errors from the service instead of building the full payload inline
  - the implicit `profile` dependency in the old enroll handler is gone; the new service now explicitly builds the VM profile before emitting the endpoint config response
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/endpoint_enrollment.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - installer-side enrollment token issuance still returns a token plus the expected `thinclient_password` and `profile_name`
  - endpoint enrollment still emits the existing manager/update/Moonlight/USB/egress/identity config shape
  - Sunshine pinned-pubkey backfill still updates the returned secret/config payload before the response is built
  - invalid payloads still fail as `ValueError`, missing/expired tokens as `PermissionError`, and missing VMs as `LookupError`, which the handler now maps to `400` / `401` / `404`
- `beagle-control-plane.py` dropped from `3418` to `3370` lines with this slice, and the host-side extracted-service module count moved from `24` to `25`

### 2026-04-11 — runtime environment extraction

- Extracted the runtime host-resolution / manager-pinned-pubkey helper cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/runtime_environment.py`:
  - `RuntimeEnvironmentService` now owns `resolve_public_stream_host(host)`, `current_public_stream_host()`, and `manager_pinned_pubkey()`
  - the control-plane helper names stay stable as thin wrappers, so downstream handler and service collaborators did not need surface changes
- Finished the factory wiring so the entrypoint no longer carries direct runtime pinning state:
  - `DownloadMetadataService`, `VmProfileService`, `UbuntuBeagleProvisioningService`, and `InstallerScriptService` now receive `manager_pinned_pubkey()` through the new service seam instead of a module-level constant
  - endpoint enrollment responses now emit `beagle_manager_pinned_pubkey` from the same runtime service path
  - `PublicStreamService` and `VmSecretBootstrapService` now consume the runtime-resolved public stream host through the same service seam
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/runtime_environment.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - direct IPv4 values still short-circuit unchanged
  - DNS-backed public stream hosts still resolve to the first IPv4 result
  - manager pinned-pubkey generation still returns the same `sha256//...` format and now caches the result after the first OpenSSL round-trip
  - missing manager certs still return an empty pinned-pubkey string
- `beagle-control-plane.py` and the immediate follow-up queue-wait slice together dropped from `3447` to `3418` lines, and the host-side extracted-service module count moved from `23` to `24`

### 2026-04-11 — action-result wait extraction

- Finished the remaining result-wait loop inside `beagle-host/services/action_queue.py`:
  - `ActionQueueService` now owns `wait_for_result(node, vmid, action_id, timeout_seconds=...)` in addition to queue/result path lookup, queue orchestration, result persistence, and result summarization
  - the control-plane helper name `wait_for_action_result(...)` stays stable as a thin wrapper, so the USB attach/detach retry handlers kept their existing call shape and timeouts
- Kept the result-wait seam inside the existing queue service instead of creating another tiny helper module:
  - the wait loop already depends on result-file semantics and the queue/result persistence contract
  - injected `monotonic` and `sleep` collaborators make the wait behavior explicit and testable without pushing it back into the HTTP entrypoint
- Smoke-tested the expanded queue service outside the server loop:
  - queue IDs still retain the current `node-vmid-timestamp-index` format
  - bulk queueing still deduplicates VMIDs and ignores missing VMs
  - waiting for the matching `action_id` still returns the stored result, while non-matching IDs still time out to `None`

### 2026-04-11 — Ubuntu-Beagle input and preset normalization extraction

- Extracted the ubuntu-beagle input/preset normalization block out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/ubuntu_beagle_inputs.py`:
  - `UbuntuBeagleInputsService` now owns `validate_linux_username`, `validate_password`, `normalize_locale`, `normalize_keymap`, `normalize_package_names`, `resolve_ubuntu_beagle_desktop`, `normalize_package_presets`, and `expand_software_packages`
  - the control-plane helper names stay stable as thin wrappers, while `UbuntuBeagleProvisioningService` and `VmProfileService` now depend directly on the new service methods instead of on inline entrypoint helpers
- Kept the input-validation seam explicit instead of leaving provisioning semantics in the HTTP entrypoint:
  - ubuntu-beagle provisioning still owns the create/update/finalize lifecycle
  - the new service only owns canonical validation and preset/package expansion rules shared by provisioning and profile synthesis
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/ubuntu_beagle_inputs.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - usernames, passwords, locale, and keymap still validate against the same rules and defaults
  - desktop aliases still resolve to the same desktop descriptors
  - package preset validation and final package expansion still preserve the existing dedupe/order semantics
- `beagle-control-plane.py` dropped from `3508` to `3470` lines with this slice, and the host-side extracted-service module count moved from `22` to `23`

### 2026-04-11 — action-queue orchestration extraction

- Finished the remaining queue-orchestration block inside `beagle-host/services/action_queue.py`:
  - `ActionQueueService` now owns `queue_action(...)`, `queue_bulk_actions(...)`, and `dequeue_actions(...)` in addition to the existing queue/result path, I/O, and result-summary helpers
  - the control-plane helper names `queue_vm_action`, `queue_bulk_actions`, and `dequeue_vm_actions` stay stable as thin wrappers, so the VM action endpoints and USB retry flows kept their existing handler surface and payload shapes
- Kept the queue seam cohesive instead of creating a second queue service:
  - queue file I/O and result storage were already in `ActionQueueService`
  - action-id generation, timestamping, duplicate-VM suppression for bulk queues, and queue-drain behavior now live in the same service boundary
- Smoke-tested the expanded queue service outside the server loop:
  - action IDs still increment with queue depth
  - bulk queueing still deduplicates VMIDs and skips missing VMs
  - dequeue still returns the current queue and clears it on disk
- `beagle-control-plane.py` dropped further from `3470` to `3447` lines with this slice; the host-side extracted-service module count stays at `23` because the work moved under the existing `ActionQueueService`

### 2026-04-11 — installer template patching extraction

- Extracted the installer template/default rewrite block out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/installer_template_patch.py`:
  - `InstallerTemplatePatchService` now owns shell-template default rewrites via `patch_installer_defaults(...)`, Windows template rewrites via `patch_windows_installer_defaults(...)`, and the shared shell escaping helper
  - `InstallerScriptService` now depends directly on the new service methods instead of on inline control-plane helpers
- Closed the remaining installer-local helper loop in the same slice:
  - preset Base64 encoding moved into `beagle-host/services/installer_script.py` as an internal helper, so `encode_installer_preset(...)` no longer lives in the control-plane entrypoint
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/installer_template_patch.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the installer helper seam outside the server loop:
  - shell-template rewriting still patches all expected variables and preserves escaping for `"`, `$`, and backticks
  - Windows template rewriting still replaces all three Beagle placeholders
  - preset encoding still returns a non-empty Base64 payload from canonical preset key/value lines
- `beagle-control-plane.py` dropped from `3533` to `3508` lines with this slice, and the host-side extracted-service module count moved from `21` to `22`

### 2026-04-11 — support-bundle storage/upload extraction

- Finished the remaining support-bundle storage/upload block inside `beagle-host/services/support_bundle_store.py`:
  - `SupportBundleStoreService` now owns not only metadata/archive path lookup and listing, but also `store(...)` for archive persistence, metadata shaping, SHA256 calculation, and metadata-file writes
  - the control-plane helper name `store_support_bundle(...)` stays stable as a thin wrapper, so the VM action-result upload path kept its existing handler surface and payload shape
- Kept the bundle-storage seam explicit instead of leaving upload orchestration in the HTTP entrypoint:
  - bundle archive and metadata paths still come from the existing store service
  - JSON persistence still goes through the existing `write_json_file(...)` helper
  - the slice intentionally preserves the legacy filename-sanitizing behavior, including the current `.bin` fallback when sanitized names lose suffixes
- Smoke-tested the expanded store service outside the server loop:
  - uploaded bundle content still lands on disk
  - metadata still records `bundle_id`, `size`, `sha256`, `uploaded_at`, and `download_path`
  - lookup and filtered listing still recover the stored bundle metadata correctly
- `beagle-control-plane.py` dropped from `3556` to `3533` lines with this slice, while the host-side extracted-service module count stays at `21` because this flow moved under the existing `SupportBundleStoreService` instead of adding another service file

### 2026-04-11 — policy normalization extraction

- Extracted the policy payload normalization block out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/policy_normalization.py`:
  - `PolicyNormalizationService` now owns canonical normalization of policy `selector` and `profile` payloads plus `assigned_target`, `update_enabled`, and list-valued egress field shaping
  - the control-plane helper name `normalize_policy_payload` stays stable as a thin wrapper, and `PolicyStoreService` now depends on the service method instead of the inline entrypoint function
- Kept the policy contract seam explicit instead of leaving it in the HTTP entrypoint:
  - policy file CRUD remains in `beagle-host/services/policy_store.py`
  - list/boolean/time shaping still reuses the existing generic collaborators `listify`, `truthy`, and `utcnow`
  - the new service only owns policy contract normalization and validation between those seams
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/policy_normalization.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - selector/profile payloads still normalize into the existing persisted shape
  - `assigned_target` still maps to `{vmid, node}` or `None`
  - `policy_name=` override still wins over payload-local names
  - invalid non-object `selector`/`profile` payloads still raise the same `ValueError` paths
- `beagle-control-plane.py` dropped from `3614` to `3556` lines with this slice, and the host-side extracted-service count moved from 20 to 21

### 2026-04-11 — public-stream allocation and state extraction

- Extracted the public-stream port-state/allocation cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/public_streams.py`:
  - `PublicStreamService` now owns `public_streams_file`, `load_public_streams`, `save_public_streams`, `public_stream_key`, `explicit_public_stream_base_port`, `used_public_stream_base_ports`, and `allocate_public_stream_base_port`
  - the control-plane helper names stay stable as thin wrappers, so `VmProfileService` and `UbuntuBeagleProvisioningService` kept their existing collaborator signatures and did not need behavioral changes
- Kept the port-allocation seam explicit instead of leaving it in the HTTP entrypoint:
  - persistent mapping I/O still goes through the existing JSON helpers
  - VM/config inspection still goes through provider-backed `list_vms()` and `get_vm_config()`
  - host availability gating still comes from `current_public_stream_host()`
  - the new service only owns mapping normalization, stale-entry cleanup, explicit-port syncing, and next-free-port selection between those seams
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/public_streams.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - explicit `beagle-public-moonlight-port` values still override stored mappings and persist back to disk
  - stale mapping keys are still removed during sync
  - automatic allocation still chooses the next free stepped base port and persists it
  - disabled public-stream hosts still short-circuit allocation with `None`
- `beagle-control-plane.py` dropped from `3651` to `3614` lines with this slice, and the host-side extracted-service count moved from 19 to 20

### 2026-04-11 — Sunshine/Moonlight guest integration and proxy extraction

- Extracted the Sunshine/Moonlight guest-integration cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/sunshine_integration.py`:
  - `SunshineIntegrationService` now owns `fetch_https_pinned_pubkey`, `guest_exec_text`, `sunshine_guest_user`, `register_moonlight_certificate_on_vm`, `fetch_sunshine_server_identity`, `internal_sunshine_api_url`, `resolve_vm_sunshine_pinned_pubkey`, `issue_sunshine_access_token`, `resolve_ticket_vm`, `sunshine_proxy_ticket_url`, and `proxy_sunshine_request`
  - the control-plane helper names stay stable as thin wrappers, so the public Sunshine proxy handlers, endpoint enrollment flow, Moonlight certificate registration endpoint, installer-script collaborators, and VM-secret bootstrap seam did not need payload or signature changes
- Kept the integration seam explicit instead of leaving streaming internals in the HTTP entrypoint:
  - provider-backed guest execution still goes through `HOST_PROVIDER.guest_exec_script_text`
  - Sunshine access-token persistence and validity remain behind `SunshineAccessTokenStoreService`
  - VM-secret credential lookup remains behind `VmSecretBootstrapService`
  - the new service only owns the guest-side scripting, Sunshine identity discovery, TLS pinned-pubkey retrieval, ticket-backed VM resolution, and authenticated Sunshine proxy orchestration between those seams
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/sunshine_integration.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - HTTPS pinned-pubkey extraction still returns the expected `sha256//...` shape
  - Moonlight certificate registration still targets the guest Sunshine state file for the resolved guest user and preserves the expected response payload
  - Sunshine server identity discovery still round-trips `uniqueid`, `server_cert_pem`, `sunshine_name`, and `stream_port`
  - access-ticket issuance and ticket-to-VM resolution still preserve the existing public Sunshine proxy semantics
  - Sunshine HTTP proxying still forwards method, body, headers, and response status/header/body triplets unchanged
- `beagle-control-plane.py` dropped from `3930` to `3651` lines with this slice, and the host-side extracted-service count moved from 18 to 19

### 2026-04-11 — ubuntu-beagle provisioning and lifecycle extraction

- Extracted the ubuntu-beagle provisioning/lifecycle cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/ubuntu_beagle_provisioning.py`:
  - `UbuntuBeagleProvisioningService` now owns provisioning catalog assembly, storage resolution, installer ISO caching/extraction, autoinstall seed ISO creation, metadata description shaping, finalize/firstboot flows, VM creation, and VM update/reconfiguration
  - the control-plane helper names (`build_provisioning_catalog`, `create_provisioned_vm`, `finalize_ubuntu_beagle_install`, `prepare_ubuntu_beagle_firstboot`, `create_ubuntu_beagle_vm`, `update_ubuntu_beagle_vm`) stay stable as thin wrappers, so the provisioning and public ubuntu-install HTTP handlers did not need signature or payload changes
- Kept the provisioning seam explicit instead of pushing more logic into the entrypoint:
  - provider-backed VM create/set/start/stop/delete operations stay behind `HOST_PROVIDER`
  - ubuntu-beagle state persistence stays behind `UbuntuBeagleStateService`
  - VM-secret bootstrap stays behind `VmSecretBootstrapService`
  - the new service owns the orchestration and artifact/template logic between those seams
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/ubuntu_beagle_provisioning.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop with fake provider + temp templates/artifacts:
  - provisioning catalog still resolves online nodes, bridges, and image/ISO storages correctly
  - create flow still builds ISO/seed assets, saves provisioning state, calls provider VM lifecycle methods, and persists initial secret material
  - update flow still reapplies metadata and running-guest package/configuration changes
  - finalize and firstboot-prep flows still remove installer media, repair boot order, and schedule the deferred restart path
- `beagle-control-plane.py` dropped from `4701` to `3930` lines with this slice, and the host-side extracted-service count moved from 17 to 18

### 2026-04-11 — USB guest-attachment and tunnel-state extraction

- Extracted the guest-USB attachment / tunnel-state helper cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/vm_usb.py`:
  - `VmUsbService` now owns `parse_usbip_port_output`, `parse_vhci_status_output`, `guest_usb_attachment_state`, `wait_for_guest_usb_attachment`, `build_vm_usb_state`, `attach_usb_to_guest`, and `detach_usb_from_guest`
  - the control-plane helper names stay stable as thin wrappers, so the `/api/v1/vms/{vmid}/usb`, `/usb/attach`, and `/usb/detach` handlers did not need signature or payload changes
- Kept the host-service boundary clean:
  - guest-side usbip/vhci probing still goes through the existing provider-backed `guest_exec_*` wrappers
  - endpoint USB inventory/tunnel metadata still comes from `EndpointReportService`
  - VM-secret/tunnel-port lookup still comes from `VmSecretBootstrapService`
  - the new service only owns the orchestration and parsing layer between those seams
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/vm_usb.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - `usbip port` parsing still recovers `port`, `busid`, and device lines
  - `vhci_hcd` status parsing still recovers attached guest ports
  - `build_vm_usb_state()` still emits the expected tunnel metadata plus endpoint device counts
  - attach and detach still round-trip through the same guest command semantics and attachment confirmation logic
- `beagle-control-plane.py` dropped from about `4840` to `4701` lines with this slice, and the host-side extracted-service count moved from 16 to 17

### 2026-04-11 — installer-prep and sunshine-readiness extraction

- Extracted the installer-prep / Sunshine-readiness helper cluster out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/installer_prep.py`:
  - `InstallerPrepService` now owns `prep_dir`, `state_path`, `log_path`, `load_state`, `quick_sunshine_status`, `default_state`, `summarize_state`, `is_running`, and `start`
  - the control-plane helper names (`installer_prep_dir`, `installer_prep_path`, `installer_prep_log_path`, `load_installer_prep_state`, `quick_sunshine_status`, `default_installer_prep_state`, `summarize_installer_prep_state`, `installer_prep_running`, `start_installer_prep`) stay stable as thin wrappers, so HTTP handlers and `VmStateService` wiring did not need signature changes
- Wired the new service into the existing seams:
  - `VmStateService` continues to consume the same wrappers, which now delegate into `InstallerPrepService`
  - installer-prep HTTP read/start handlers still call the same helpers, but the state-path, Sunshine probing, default/summary shaping, and background-script launch logic no longer live in the control-plane entrypoint
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/installer_prep.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - state and log paths still resolve to `<node>-<vmid>.json` / `.log`
  - `quick_sunshine_status()` still parses the guest JSON probe into `{binary, service, process}`
  - a ready VM produces the expected `ready` default state, and `start()` writes the bootstrapped `running` state plus launches the prep script with the expected environment
  - an unsupported VM still returns the `unsupported` state without trying to spawn the prep script
- `beagle-control-plane.py` dropped from about `4955` to about `4840` lines with this slice, and the host-side extracted-service count moved from 15 to 16

### 2026-04-11 — vm-secret bootstrap extraction

- Extracted the higher-level VM-secret bootstrap/orchestration block out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/vm_secret_bootstrap.py`:
  - `VmSecretBootstrapService` now owns `default_usb_tunnel_port`, `generate_ssh_keypair`, `usb_tunnel_known_host_line`, `usb_tunnel_user_info`, `usb_tunnel_home`, `usb_tunnel_auth_root`, `usb_tunnel_auth_dir`, `usb_tunnel_authorized_keys_path`, `usb_tunnel_authorized_key_line`, `sync_usb_tunnel_authorized_key`, `ensure_vm_sunshine_pinned_pubkey`, and `ensure_vm_secret`
  - the control-plane helper names stay stable as thin wrappers, so `issue_enrollment_token`, installer rendering, USB attach/detach state building, ubuntu-beagle VM creation, and endpoint enrollment flows did not need signature changes
- Split the previous VM-secret responsibility cleanly in two:
  - `VmSecretStoreService` remains the persistence boundary for reading/writing the JSON record
  - `VmSecretBootstrapService` now owns credential generation, SSH keypair creation, Sunshine pinned-pubkey backfill, and managed USB-tunnel `authorized_keys` synchronization
- Added the small shared helper `resolve_vm_sunshine_pinned_pubkey(vm)` in the control plane so both endpoint enrollment and `VmSecretBootstrapService` reuse the same Sunshine pin resolution path instead of duplicating `build_profile(... allow_assignment=False)` plus `fetch_https_pinned_pubkey(...)`
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/vm_secret_bootstrap.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - a new VM secret gets the expected generated Sunshine credentials, tunnel keypair, tunnel port, pinned pubkey, and managed `authorized_keys` block
  - an existing incomplete secret record gets the missing fields backfilled without changing the wrapper surface
  - `usb_tunnel_known_host_line()` still emits the combined public-server/public-stream host line from the configured hostkey file
- `beagle-control-plane.py` dropped from about `5072` to about `4955` lines with that slice, and a later installer-prep extraction reduced it further to about `4840`

### 2026-04-11 — download/artifact metadata extraction

- Extracted the download/artifact metadata helper block out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/download_metadata.py`:
  - `DownloadMetadataService` now owns `public_installer_iso_url`, `public_windows_installer_url`, `public_update_sha256sums_url`, `public_versioned_payload_url`, `public_versioned_bootstrap_url`, `public_payload_latest_download_url`, `public_bootstrap_latest_download_url`, `public_latest_payload_url`, `public_latest_bootstrap_url`, `url_host_matches`, `checksum_for_dist_filename`, and `update_payload_metadata`
  - the control-plane helper names stay stable as thin wrappers, so handler-local and service-local call sites did not need to change signature
- Wired the new service into the already extracted host services:
  - `VmProfileService` now receives `public_installer_iso_url` directly from `download_metadata_service()`
  - `UpdateFeedService` now receives `update_payload_metadata` and `public_update_sha256sums_url` directly from `download_metadata_service()`
  - `FleetInventoryService` and `InstallerScriptService` now receive their installer/payload/bootstrap URL helpers from `download_metadata_service()` instead of from inline control-plane helpers
- `scripts/install-proxmox-host-services.sh` now installs `beagle-host/services/download_metadata.py` into `$HOST_RUNTIME_DIR/services/`
- Smoke-tested the new service outside the server loop:
  - versioned payload SHA256 comes from `SHA256SUMS` when present
  - latest payload SHA256 falls back to `beagle-downloads-status.json` when the current version is not yet present in `SHA256SUMS`
  - payload pinned-pubkey emission still depends on host matching against `PUBLIC_MANAGER_URL`
  - latest bootstrap URL still honors the explicit `bootstrap_url` override from `beagle-downloads-status.json`
- `beagle-control-plane.py` dropped from about `5098` to about `5072` lines with this slice, and the host-side extracted-service count moved from 13 to 14

### 2026-04-11 — sunshine-access-token and endpoint-token store extraction

- Extracted the sunshine-access-token persistence and validity helpers out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/sunshine_access_token_store.py`:
  - `SunshineAccessTokenStoreService` owns `tokens_dir()`, `token_path(token)`, `store(token, payload)`, `load(token)`, and `is_valid(payload)`; the sha256-hashed token path and the expiry-only validity check match the previous helper semantics
  - `sunshine_access_tokens_dir`, `sunshine_access_token_path`, `load_sunshine_access_token`, and `sunshine_access_token_is_valid` in the control plane now delegate through `sunshine_access_token_store_service()`; `issue_sunshine_access_token` keeps its `VmSummary`-shaped payload construction and TTL math and calls `.store()` on the service for persistence
- Extracted the endpoint-token persistence helpers into `beagle-host/services/endpoint_token_store.py`:
  - `EndpointTokenStoreService` owns `tokens_dir()`, `token_path(token)`, `store(token, payload)` (stamping `token_issued_at` via the injected `utcnow`), and `load(token)`
  - `endpoint_tokens_dir`, `endpoint_token_path`, `store_endpoint_token`, and `load_endpoint_token` in the control plane now delegate through `endpoint_token_store_service()`; endpoint enrollment and token rotation flows keep working without signature changes because the service preserves the legacy `token_issued_at` stamping contract
- `scripts/install-proxmox-host-services.sh` installs both new service files into `$HOST_RUNTIME_DIR/services/`
- Verified the live control-plane module still imports cleanly with `BEAGLE_MANAGER_DATA_DIR=/tmp/beagle-smoketest` and round-trips through both services: the token paths match the sha256 hex digest for both stores, `sunshine_access_token_is_valid` returns `False` for `None`/past expiry and `True` for a future expiry, and `store_endpoint_token({'endpoint_id':'ep-1','scope':'read'})` stamps `token_issued_at` and round-trips through `load_endpoint_token`
- `beagle-control-plane.py` grew slightly (5086 → 5098 lines) for that slice because the two lazy factories add more lines than the short helper bodies they replaced — a later slice reduced it again to about 5072 after the download/artifact metadata helpers moved behind `DownloadMetadataService`

### 2026-04-11 — vm-secret and enrollment-token store extraction

- Extracted the VM-secret persistence helpers out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/vm_secret_store.py`:
  - `VmSecretStoreService` owns `secrets_dir()`, `secret_path(node, vmid)`, `load(node, vmid)`, and `save(node, vmid, payload)`; `save()` stamps `node`, `vmid`, and `updated_at` via the injected `utcnow` callable, matching the previous helper semantics
  - `vm_secrets_dir`, `vm_secret_path`, `load_vm_secret`, and `save_vm_secret` in the control plane now delegate through `vm_secret_store_service()`; the later `VmSecretBootstrapService` extraction kept those persistence wrappers stable and moved the higher-level credential/bootstrap logic out of the control plane
- Extracted the enrollment-token persistence and validity helpers into `beagle-host/services/enrollment_token_store.py`:
  - `EnrollmentTokenStoreService` owns `tokens_dir()`, `token_path(token)`, `store(token, payload)`, `load(token)`, `mark_used(token, payload, *, endpoint_id)`, and `is_valid(payload, *, endpoint_id)`
  - `enrollment_tokens_dir`, `enrollment_token_path`, `load_enrollment_token`, `mark_enrollment_token_used`, and `enrollment_token_is_valid` in the control plane now delegate through `enrollment_token_store_service()`; `issue_enrollment_token` still builds its payload from `VmSummary` + `ensure_vm_secret` + TTL math and calls `.store()` on the service so the payload shape stays in the control plane
- `scripts/install-proxmox-host-services.sh` installs both new service files into `$HOST_RUNTIME_DIR/services/`
- Verified the live control-plane module still imports cleanly with `BEAGLE_MANAGER_DATA_DIR=/tmp/beagle-smoketest` and round-trips through both services: `vm_secret_path('pve1', 101).name` is `pve1-101.json`, saving and loading a secret preserves `node`, `vmid`, and a fresh `updated_at`, `enrollment_token_path('demo').name` matches the sha256 hex digest, and `enrollment_token_is_valid` correctly handles `None`, bad timestamps, future-unused, and endpoint-id reuse vs. mismatch
- `beagle-control-plane.py` net change was +2 lines (5084 → 5086) for this slice because the two lazy factories offset the short helper bodies — this slice is about the architectural seam, not line count

### 2026-04-11 — ubuntu-beagle provisioning-state extraction

- Extracted the ubuntu-beagle installer state persistence and summarization helpers out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/ubuntu_beagle_state.py`:
  - `UbuntuBeagleStateService` owns `tokens_dir()`, `token_path(token)`, `load(token)`, `save(token, payload)`, `summarize(payload, *, include_credentials)`, `list_all(*, include_credentials)`, and `latest_for_vmid(vmid, *, include_credentials)`; collaborators (`data_dir` callable, `load_json_file`, `write_json_file`, `safe_slug`, `ubuntu_beagle_profile_id`) are injected through the kwargs-only constructor so the service stays agnostic of the Proxmox control plane
  - `ubuntu_beagle_tokens_dir`, `ubuntu_beagle_token_path`, `load_ubuntu_beagle_state`, `save_ubuntu_beagle_state`, `summarize_ubuntu_beagle_state`, `list_ubuntu_beagle_states`, and `latest_ubuntu_beagle_state_for_vmid` in the control plane now delegate through `ubuntu_beagle_state_service()` with unchanged signatures, so HTTP handlers under `/api/v1/public/ubuntu-install/*`, `/api/v1/ubuntu-beagle-vms`, and the `VmProfileService` / `VmStateService` wiring keep working without any further edits
  - The `schedule_ubuntu_beagle_vm_restart`, `cancel_scheduled_ubuntu_beagle_vm_restart`, and `public_ubuntu_beagle_complete_url` helpers stay in the control plane because they depend on `HOST_PROVIDER`, `PUBLIC_MANAGER_URL`, and process-signal plumbing that is not part of the persistence seam
- `scripts/install-proxmox-host-services.sh` installs the new service file into `$HOST_RUNTIME_DIR/services/`
- Verified the live control-plane module still imports cleanly with `BEAGLE_MANAGER_DATA_DIR=/tmp/beagle-smoketest`, and the save/load/summarize/list/latest round-trip works end-to-end through the wrappers (saved vmid 101 with `started: True`, round-tripped through the service, summarized as `installing` / `autoinstall`, recovered through `latest_ubuntu_beagle_state_for_vmid`)
- `beagle-control-plane.py` shrank from about 5138 to about 5084 lines as part of this slice

### 2026-04-11 — policy and support-bundle store extraction

- Extracted the policy-store I/O helpers out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/policy_store.py`:
  - `PolicyStoreService` owns `policy_path(name)`, `save(payload, policy_name=...)`, `load(name)`, `delete(name)`, and `list_all()`; `save()` is wired with the existing `normalize_policy_payload` callable so the policy shape is still owned by the control plane but I/O and listing lives behind the service
  - `policy_path`, `save_policy`, `load_policy`, `delete_policy`, and `list_policies` in the control plane now delegate through `policy_store_service()`; HTTP handler call sites and `HealthPayloadService` (which already takes `list_policies` as a callable) keep working with no wiring changes
- Extracted the support-bundle metadata/archive helpers into `beagle-host/services/support_bundle_store.py`:
  - `SupportBundleStoreService` owns `metadata_path(bundle_id)`, `archive_path(bundle_id, filename)`, `find_metadata(bundle_id)`, and `list_metadata(*, node=None, vmid=None)`
  - `support_bundle_metadata_path`, `support_bundle_archive_path`, `list_support_bundle_metadata`, and `find_support_bundle_metadata` in the control plane now delegate through `support_bundle_store_service()`; `store_support_bundle()` continues to call the wrapper-backed path helpers and is unchanged
- `scripts/install-proxmox-host-services.sh` installs both new service files into `$HOST_RUNTIME_DIR/services/`
- Verified `beagle-control-plane.py` still imports cleanly with an isolated data dir; `policy_path('my-policy')`, `support_bundle_metadata_path('b-abc')`, `support_bundle_archive_path('b-abc', 'bundle.tar.gz')`, `list_policies()`, `find_support_bundle_metadata('nonexistent')`, and `list_support_bundle_metadata()` all returned the expected shapes
- `beagle-control-plane.py` net change was only about -1 line for this slice because the two lazy factories offset the short helper bodies — this slice is about the architectural seam, not line count

### 2026-04-11 — endpoint-report and action-queue service extraction

- Extracted the endpoint-report I/O and summarization helpers out of `beagle-host/bin/beagle-control-plane.py` into `beagle-host/services/endpoint_report.py`:
  - `EndpointReportService` owns `report_path(node, vmid)`, `load(node, vmid)`, `list_all()`, and `summarize(payload)`
  - `summarize_endpoint_report`, `endpoint_report_path`, `load_endpoint_report`, and `list_endpoint_reports` in the control plane now delegate through `endpoint_report_service()`; the control-plane helper signatures are unchanged so `HealthPayloadService`, `FleetInventoryService`, and the HTTP handler at `/api/v1/endpoints/{node}/{vmid}/reports` keep working without touching the service wiring
- Extracted the action-queue I/O and result summarization helpers into `beagle-host/services/action_queue.py`:
  - `ActionQueueService` owns `queue_path(node, vmid)`, `result_path(node, vmid)`, `load_queue`, `save_queue`, `load_result`, `store_result`, and `summarize_result`
  - `action_queue_path`, `action_result_path`, `load_action_queue`, `save_action_queue`, `load_action_result`, `store_action_result`, and `summarize_action_result` in the control plane now delegate through `action_queue_service()`; `queue_vm_action`, `queue_bulk_actions`, and `dequeue_vm_actions` continue to work via those wrappers with no changes
- `scripts/install-proxmox-host-services.sh` installs both new service files into `$HOST_RUNTIME_DIR/services/`
- Verified the control-plane module still imports cleanly and both new lazy factories (`endpoint_report_service()`, `action_queue_service()`) instantiate with the expected class names; `summarize_endpoint_report({})` and `summarize_action_result(None)` return the documented empty shapes
- `beagle-control-plane.py` shrank from about 5222 to about 5139 lines as part of this slice

### 2026-04-11 — health and installer-script service extraction

- Continued pulling HTTP-facing response builders out of `beagle-host/bin/beagle-control-plane.py`:
  - added `beagle-host/services/health_payload.py` with `HealthPayloadService.build_payload()` covering downloads-status lookup, VM listing + per-VM endpoint compliance bucketing, pending action counts, and the full `/api/v1/health` envelope
  - added `beagle-host/services/installer_script.py` with `InstallerScriptService.build_preset()` plus `render_installer_script()`, `render_live_usb_script()`, and `render_windows_installer_script()` covering the entire VM installer/live-USB/Windows-installer script generation flow including profile lookup, enrollment token issuance, sunshine identity fetch, preset assembly, template patching, and filename derivation
  - `beagle-control-plane.py` now keeps only thin `build_health_payload`, `build_installer_preset`, `render_vm_installer_script`, `render_vm_live_usb_script`, and `render_vm_windows_installer_script` wrappers that delegate to lazily-initialized module-level service singletons (`health_payload_service()`, `installer_script_service()`), mirroring the existing service factory pattern
- `scripts/install-proxmox-host-services.sh` installs the two new service files into `$HOST_RUNTIME_DIR/services/`; `scripts/validate-project.sh` picks them up automatically through the `beagle-host/` python discovery
- Verified `beagle-control-plane.py` still imports cleanly with all five HTTP-facing wrappers wired through the lazy factories
- `beagle-control-plane.py` shrank from about 5385 to about 5222 lines as part of this slice

### 2026-04-10 — response-builder service extraction

- Extracted the next batch of HTTP-facing response builders out of `beagle-host/bin/beagle-control-plane.py` into dedicated service modules:
  - added `beagle-host/services/update_feed.py` with `UpdateFeedService.build_update_feed(profile, ...)` covering downloads-status lookup, channel/behavior/pin resolution, payload readiness, and the full update-feed response shape
  - added `beagle-host/services/fleet_inventory.py` with `FleetInventoryService.build_inventory()` covering VM listing, per-VM profile composition, endpoint/action/provisioning summaries, installer URLs, and the final `{service, version, generated_at, vms}` envelope
  - `beagle-control-plane.py` now keeps only thin `build_update_feed` / `build_vm_inventory` wrappers that delegate to lazily-initialized module-level service singletons, mirroring the existing `vm_profile_service()` / `vm_state_service()` pattern
- `scripts/install-proxmox-host-services.sh` installs the two new service files into `$HOST_RUNTIME_DIR/services/` alongside the existing ones; `scripts/validate-project.sh` picks them up automatically through the `beagle-host/` python discovery.
- Smoke-tested both services outside the server loop: `UpdateFeedService` resolves `installed_version != latest_version` into `available=True`, and `FleetInventoryService.build_inventory()` returns the expected `beagle-control-plane` envelope for an empty VM list.

### 2026-04-10 additions

- Aligned the refactor north star with the intended product direction:
  - documented explicitly that provider-neutrality is a means to a first-party Beagle virtualization product/provider, not the final target
  - documented Proxmox as a future optional provider rather than the architecture center
  - added the missing roadmap language and exit criteria for eventually making external providers optional
- Renamed the generic host/control-plane repo surface from `proxmox-host/` to `beagle-host/`:
  - updated the canonical repo path, systemd unit source path, host-service installer, validation, packaging, and repo documentation to use `beagle-host/`
  - kept a compatibility bridge in `scripts/install-proxmox-host-services.sh` by linking `/opt/beagle/proxmox-host` to `/opt/beagle/beagle-host` during install
  - kept genuinely provider-specific names such as `proxmox_host_provider.py`, `install-proxmox-host.sh`, and external `--proxmox-host` flags unchanged to avoid breaking the active Proxmox deployment surface
- Extracted the remaining large Proxmox UI provisioning blocks out of `proxmox-ui/beagle-ui.js`:
  - added `proxmox-ui/components/provisioning-result-modal.js` carrying `provisioningStatusLabel`, `provisioningStatusBadgeClass`, `renderProvisioningBadge`, `renderProvisioningResultHtml`, and `showProvisioningResultWindow`
  - added `proxmox-ui/components/provisioning-create-modal.js` carrying `safeHostnameCandidate`, `listToMultiline`, `readCheckedValues`, and the full `showUbuntuBeagleCreateModal` orchestration
  - reduced `proxmox-ui/beagle-ui.js` from about 1760 lines to about 950 lines; it now holds only delegation wrappers for the provisioning result window, the create/edit modal, and the inline badge renderer
- Updated `scripts/install-proxmox-ui-integration.sh` and `scripts/validate-project.sh` so both new `components/` modules are installed into `/usr/share/pve-manager/js/`, injected into `index.html.tpl`, and syntax-checked on validate.
- Extended the host-side provider seam in `beagle-host/providers/proxmox_host_provider.py` with VM lifecycle write methods:
  - `create_vm`, `set_vm_options`, `delete_vm_options`, `set_vm_description`, `set_vm_boot_order`, `start_vm`, `stop_vm`
  - all go through a shared `_flatten_option_pairs` helper so callers pass either `Mapping` or list-of-tuples option shapes
  - constructor now takes an explicit `run_checked` callable in addition to `run_json` and `run_text`
- Rerouted VM lifecycle writes in `beagle-host/bin/beagle-control-plane.py` through the provider:
  - `finalize_ubuntu_beagle_install` uses `delete_vm_options`, `set_vm_boot_order`, `stop_vm`, and `start_vm`
  - `create_ubuntu_beagle_vm` uses `create_vm`, `set_vm_description`, `set_vm_options`, `set_vm_boot_order`, and `start_vm`
  - `update_ubuntu_beagle_vm` uses `set_vm_description`
- Finished the next host-provider slice for control-plane guest execution and restart scheduling:
  - added `guest_exec_bash`, `guest_exec_status`, `guest_exec_script_text`, and `schedule_vm_restart_after_stop` to `beagle-host/providers/proxmox_host_provider.py`
  - `schedule_ubuntu_beagle_vm_restart` now delegates to the provider instead of embedding the restart shell flow inline
  - `guest_exec_text`, `guest_exec_out_data`, and `guest_exec_payload` now delegate to provider methods instead of issuing `qm guest exec` / `qm guest exec-status` directly from `beagle-control-plane.py`
- Continued shrinking the browser entrypoints and documenting the still-missing profile contract:
  - added `proxmox-ui/state/vm-profile.js` and moved the Beagle profile synthesis flow out of `proxmox-ui/beagle-ui.js`
  - added `extension/services/profile.js` and moved the extension-side VM profile resolution, installer readiness state helpers, action-state formatting, endpoint env generation, and operator notes there
  - reduced `proxmox-ui/beagle-ui.js` further from about 950 lines to about 813 lines
  - reduced `extension/content.js` from about 700+ lines to about 541 lines, leaving it as a renderer/event entrypoint instead of carrying profile synthesis internals
  - updated `extension/manifest.json`, `scripts/install-proxmox-ui-integration.sh`, and `scripts/validate-project.sh` so both new modules are loaded and syntax-checked everywhere
- Made the host-side public endpoint profile contract explicit:
  - added `beagle-host/bin/endpoint_profile_contract.py` with normalized browser-/installer-facing profile fields plus contract version `v1`
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
- Removed the next browser-side duplication layer and split the extension DOM boot path:
  - added `extension/shared/vm-profile-helpers.js` as the shared browser-side source for endpoint-env export, operator notes, and action-state formatting
  - rewired `proxmox-ui/state/vm-profile.js`, `proxmox-ui/components/profile-modal.js`, and `extension/services/profile.js` onto that shared helper so note/export semantics no longer depend on one browser surface importing the other's component logic
  - removed the old `proxmox-ui/state/vm-profile.js` dependency on `proxmox-ui/components/profile-modal.js` for note/env generation; state now depends only on shared mapper/helper modules plus services
  - added `extension/components/vm-page-integration.js` for toolbar/menu injection and mutation-observer boot logic
  - reduced `extension/content.js` again from about 328 lines to about 189 lines so it now focuses on overlay/styles, VM profile resolution, and modal/download launch actions
  - updated `extension/manifest.json`, `scripts/install-proxmox-ui-integration.sh`, and `scripts/validate-project.sh` so the new shared helper and extension DOM-integration module are loaded and validated everywhere they are needed
- Extracted the remaining Proxmox-UI ExtJS/DOM integration monolith out of `proxmox-ui/beagle-ui.js`:
  - added `proxmox-ui/components/extjs-integration.js` for Proxmox console button wiring, fleet launcher injection, create-VM button/menu integration, and the periodic `integrate()` boot loop
  - removed the ExtJS label matching and Create-VM DOM fallback logic from `proxmox-ui/beagle-ui.js`
  - reduced `proxmox-ui/beagle-ui.js` from about 797 lines to about 552 lines so it is much closer to a bootstrap/orchestration entrypoint
  - updated `scripts/install-proxmox-ui-integration.sh` and `scripts/validate-project.sh` so the new component is installed, loaded before `beagle-ui.js`, and syntax-checked
- Extracted the shared Proxmox-UI modal shell out of `proxmox-ui/beagle-ui.js`:
  - added `proxmox-ui/components/modal-shell.js` for shared modal CSS, overlay lifecycle helpers, the fleet launcher DOM identifier, and a reusable loading-overlay renderer
  - rewired `showFleetModal` and `showProfileModal` so they call `modalShell.showLoadingOverlay(...)` instead of building inline loading markup in the entrypoint
  - reduced `proxmox-ui/beagle-ui.js` again from about 552 lines to about 410 lines so it is now mostly dependency lookup, thin wrappers, and `boot()` wiring
  - updated `scripts/install-proxmox-ui-integration.sh` and `scripts/validate-project.sh` so the new shell component is installed, injected into `index.html.tpl`, and syntax-checked
- Started the first service-oriented control-plane split under `beagle-host/services/`:
  - added `beagle-host/services/virtualization_inventory.py` with `VirtualizationInventoryService` for provider-backed VM listing, node inventory, guest IPv4 lookup, VM config lookup, bridge parsing, and bridge inventory
  - rewired the existing wrappers `first_guest_ipv4`, `list_vms`, `list_nodes_inventory`, `config_bridge_names`, `list_bridge_inventory`, `get_vm_config`, and `find_vm` in `beagle-host/bin/beagle-control-plane.py` to delegate through the new service singleton instead of touching `ProxmoxHostProvider` directly
  - added `beagle-host/services/vm_state.py` with `VmStateService` for endpoint compliance evaluation and VM-state composition
  - rewired `evaluate_endpoint_compliance` and `build_vm_state` in `beagle-host/bin/beagle-control-plane.py` to delegate through the new service singleton while keeping existing function names stable for handlers
  - reduced `beagle-host/bin/beagle-control-plane.py` from about 5785 lines to about 5677 lines while creating the first stable `beagle-host/services/*` seams for future profile/inventory extraction
- Extracted the next host-side business-logic block under `beagle-host/services/`:
  - added `beagle-host/services/vm_profile.py` with `VmProfileService` for VM profile synthesis, assignment resolution, policy matching, public-stream derivation, and VM fingerprint assessment
  - rewired `should_use_public_stream`, `build_public_stream_details`, `resolve_assigned_target`, `resolve_policy_for_vm`, `assess_vm_fingerprint`, and `build_profile` in `beagle-host/bin/beagle-control-plane.py` to delegate through a new `vm_profile_service()` singleton
  - kept the public helper names and call shapes stable so handlers, installer flows, and existing internal call sites did not change during the extraction
  - updated `scripts/install-proxmox-host-services.sh` so the new host service is installed alongside the other `beagle-host/services/*` modules
  - reduced `beagle-host/bin/beagle-control-plane.py` again from about 5677 lines to about 5429 lines while removing the largest remaining inline profile/assignment/public-stream block from the HTTP entrypoint
- Introduced the first real host-side provider registry/contract seam:
  - added `beagle-host/providers/host_provider_contract.py` as the explicit host-provider contract for node, VM, storage, guest-exec, guest-IP, and lifecycle operations currently needed by the control plane
  - added `beagle-host/providers/registry.py` as the host-provider registry and provider factory, with Proxmox registered as the first concrete host provider and `pve` normalized to `proxmox`
  - rewired `beagle-host/bin/beagle-control-plane.py` to bootstrap `HOST_PROVIDER` through the registry via `BEAGLE_HOST_PROVIDER` instead of importing `ProxmoxHostProvider` directly
  - rewired the remaining direct provider call sites in the control plane to the generic `HOST_PROVIDER` object and added the active provider plus `available_providers` to `/api/v1/health`
  - updated `beagle-host/services/virtualization_inventory.py` to depend on the typed host-provider contract instead of `Any`
  - updated `scripts/install-proxmox-host-services.sh` so the host-provider contract and registry ship to the runtime host alongside the concrete Proxmox provider
  - kept the control-plane entrypoint roughly flat at about 5434 lines while removing another direct architectural dependency on a concrete provider class
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
- `beagle-host/` is now the canonical generic host/control-plane surface in the repo; `proxmox-host/` is no longer the source tree path.
- `proxmox-ui/` now has `common`, `api-client`, `state`, `provisioning`, `usb`, `utils`, and a full `components` set including `modal-shell.js`, `profile-modal.js`, `fleet-modal.js`, `provisioning-result-modal.js`, `provisioning-create-modal.js`, and `extjs-integration.js`. `beagle-ui.js` dropped from roughly 2500+ lines to about 410 lines and now mostly orchestrates bootstrap, context resolution, token/url wrappers, and delegation into extracted modules.
- `extension/content.js` no longer performs raw `/api2/json`, Beagle API token/config plumbing, inline VM profile synthesis, inline profile modal rendering, or toolbar/menu boot orchestration itself; that DOM integration now lives in `extension/components/vm-page-integration.js`, leaving `content.js` as a much thinner entrypoint.
- `beagle-host/bin/beagle-control-plane.py` now delegates provider-backed VM/node/config/bridge/guest-IP read paths through `beagle-host/services/virtualization_inventory.py`, delegates endpoint compliance and VM-state composition through `beagle-host/services/vm_state.py`, delegates VM inventory, node inventory, VM config lookup, next-VMID allocation, storage inventory, guest IPv4 lookup, VM lifecycle writes (create, set, description, boot order, start, stop, option delete), guest-exec flows, and scheduled restart orchestration into `beagle-host/providers/proxmox_host_provider.py`, while the browser-facing endpoint profile contract is normalized by `beagle-host/bin/endpoint_profile_contract.py`.
- No new behavioral tests or smoke tests have been added yet.
- Reduced duplicated script-side provider bootstrap and JSON payload parsing across the main VM-setup scripts:
  - added `scripts/lib/provider_shell.sh`
  - moved local-vs-remote host detection, provider-module path selection, helper availability checks, remote helper execution, and last-JSON-object parsing behind that shared shell seam
  - rewired `scripts/configure-sunshine-guest.sh` to reuse the shared provider shell helper for remote/local provider execution instead of carrying its own copies of those functions
  - rewired `scripts/optimize-proxmox-vm-for-beagle.sh` to reuse the same provider shell helper for provider-module discovery and remote/local execution
  - rewired `scripts/ensure-vm-stream-ready.sh` to reuse the shared provider-helper availability check and JSON payload parsing helper
  - kept the remaining direct `qm` fallback branches unchanged for rollout compatibility; this slice only removes duplicated helper plumbing, not the fallback semantics
- Reduced duplicated thin-client preset field assembly across the host installer and the USB Proxmox path:
  - added `beagle-host/services/thin_client_preset.py`
  - moved the overlapping Proxmox/network/transport/Moonlight/Sunshine preset base fields behind `build_common_preset(...)`
  - moved the shared available-modes input shaping behind `build_streaming_mode_input(...)`
  - rewired `beagle-host/services/installer_script.py` to build its shared preset base through the new helper and add only host-specific enrollment/update/identity/credential fields on top
  - rewired `thin-client-assistant/usb/proxmox_preset.py` to build its shared preset base through the same helper and keep only the USB/Proxmox-specific delta locally
  - updated `scripts/install-proxmox-host-services.sh` to deploy `thin_client_preset.py` alongside the other extracted host services
- Reduced duplicated installer/runtime default literals across the thin-client shell and Python paths:
  - added `thin-client-assistant/installer/env-defaults.json` as the shared installer-env default contract
  - added `thin-client-assistant/installer/env-defaults.sh` as the shared shell loader for that default contract
  - rewired `thin-client-assistant/runtime/generate_config_from_preset.py` to load defaults from the shared JSON contract instead of keeping a second full default table inline
  - rewired `thin-client-assistant/installer/write-config.sh`, `thin-client-assistant/installer/install.sh`, and `thin-client-assistant/installer/setup-menu.sh` to hydrate their default values through the same shared loader instead of repeating the same literal block
  - kept the menu-specific Proxmox demo placeholders in `setup-menu.sh` local so the interactive UX stays explicit while the base runtime/install defaults now come from one source
- Reduced duplicated runtime mode/cmdline override business logic in the thin-client runtime:
  - added `thin-client-assistant/runtime/mode_overrides.py`
  - moved the `pve_thin_client.client_mode` cmdline parsing and the `PVE_THIN_CLIENT_MODE` / `PVE_THIN_CLIENT_BOOT_PROFILE` mapping rules out of `thin-client-assistant/runtime/common.sh`
  - rewired `apply_runtime_mode_overrides()` in `common.sh` into a thin shell wrapper over the new helper instead of keeping the mapping rules inline
  - kept the rest of `common.sh` unchanged so the runtime still sources config files and then applies the same final override semantics as before
- Reduced duplicated runtime config-discovery and cmdline-preset restore logic in the thin-client runtime:
  - added `thin-client-assistant/runtime/config_discovery.py`
  - moved live-state discovery, preset-file discovery, and cmdline-preset restore/decode logic out of `thin-client-assistant/runtime/common.sh`
  - rewired `find_live_state_dir()` and `find_config_dir()` in `common.sh` into thin shell wrappers over the new helper
  - kept the runtime shell responsible for sourcing the resolved config files and for the remaining high-level orchestration only
- Reduced duplicated runtime config-loading/orchestration logic in the thin-client runtime:
  - added `thin-client-assistant/runtime/config_loader.sh`
  - moved `generate_config_dir_from_preset()`, runtime config file sourcing, and `load_runtime_config()` out of `thin-client-assistant/runtime/common.sh`
  - rewired `common.sh` to source the new loader helper instead of carrying those config-loading functions inline
  - kept `common.sh` as the shared orchestration library, but not as the place where config loading/discovery business logic keeps accumulating
- Removed an eager Moonlight manager-registration roundtrip from the thin-client launch fast path:
  - changed `thin-client-assistant/runtime/launch-moonlight.sh` so already configured clients try `moonlight_list()` first and log `moonlight.ready` when the cached pairing is usable
  - kept the manager-registration and PIN-pairing path in `ensure_paired()` as the fallback only, so first-boot/unpaired behavior stays unchanged
  - validated the new branch locally with focused shell smoke tests for the fast-ready path and the fallback-pairing path, plus `bash -n` and `./scripts/validate-project.sh`
  - investigated the live endpoint `192.168.178.92` directly via SSH with the host-issued thin-client password and confirmed that the current boot delay is not caused by the `10.10.x` address selection: both before and after reboot the runtime logs showed `connect_host=65.109.80.76`
  - captured the actual slow phase on the live endpoint from `/run/user/1000/beagle-os/runtime-trace.log`: `moonlight.cached-config` at `2026-04-12T03:19:30+00:00` and `moonlight.registered` at `2026-04-12T03:19:42+00:00`, with `moonlight.exec` only at `2026-04-12T03:19:44+00:00`
  - confirmed the same pattern again after a reboot at `2026-04-12T03:26:30+00:00` → `2026-04-12T03:26:43+00:00` → `2026-04-12T03:26:45+00:00`
  - verified that the current installed endpoint image is still `6.6.6`; a manual file replacement on the running client was overwritten by the booted image/runtime refresh on reboot, so the repo fix is correct but not yet part of the deployed thin-client payload
- Reduced the Moonlight runtime CLI/timeout seam further so pairing and bootstrap no longer carry their own `moonlight list` execution wrapper:
  - added `thin-client-assistant/runtime/moonlight_cli.sh`
  - moved `moonlight_list_timeout()`, `moonlight_bootstrap_timeout()`, `moonlight_target()`, `run_moonlight_cli_with_timeout()`, and `moonlight_list()` into that dedicated helper
  - rewired `thin-client-assistant/runtime/moonlight_pairing.sh` to source the new helper and keep only pairing/recovery flow plus a small `start_moonlight_pair_with_pin()` wrapper
  - rewired `thin-client-assistant/runtime/moonlight_host_sync.sh` to reuse `bootstrap_moonlight_client_probe()` from the shared helper instead of carrying another inline `timeout "$bin" list "$target"` block
  - validated with `bash -n`, focused shell smoke tests for the CLI wrapper and pairing recovery flow, and `./scripts/validate-project.sh`
- Restored the standalone host-download USB installer path after the recent USB writer modularization:
  - changed `thin-client-assistant/usb/pve-thin-client-usb-installer.sh` so the distributed single-file launcher detects missing local helper modules and self-bootstrap them from `RELEASE_BOOTSTRAP_URL` / `RELEASE_PAYLOAD_URL`
  - kept the in-repo path unchanged when the helper files are present locally, so repo development and ISO build flows still source the extracted helper modules directly
  - verified the exact broken case locally by copying the installer into a temporary foreign directory, patching host-style default URLs into it, and confirming that `--help` now succeeds after downloading/extracting the bootstrap bundle instead of failing on `/home/thin-client-assistant/usb/usb_writer_sources.sh`
  - also verified checksum-aware helper bootstrap against a temporary local HTTP server plus `SHA256SUMS`, alongside `bash -n` and `./scripts/validate-project.sh`
- Corrected the artifact source used by host-facing USB installer surfaces:
  - changed `beagle-host/services/download_metadata.py` so VM-/host-installer downloads now point `installer ISO`, `payload`, and `bootstrap` to the host-local `/beagle-downloads/*` surface instead of the external public update bucket
  - changed `scripts/prepare-host-downloads.sh` and `scripts/check-beagle-host.sh` to treat those same host-local artifact URLs as the expected launcher/status binding
  - confirmed locally that the download-metadata service now emits `https://srv.thinover.net:8443/beagle-downloads/beagle-os-installer-amd64.iso`, `.../pve-thin-client-usb-payload-latest.tar.gz`, and `.../pve-thin-client-usb-bootstrap-latest.tar.gz` for installer-facing surfaces
  - this specifically fixes the operational regression where freshly rendered VM installers tried to bootstrap from `https://beagle-os.com/beagle-updates/pve-thin-client-usb-bootstrap-latest.tar.gz`, which currently resolves to a much larger wrong artifact for USB-creation bootstrapping
- Moved the script-side virtualization helper onto the real host-provider registry instead of keeping a second hidden Proxmox client in `scripts/lib/beagle_provider.py`:
  - extended `beagle-host/providers/host_provider_contract.py` with `get_guest_network_interfaces()` and `reboot_vm()` as explicit provider lifecycle/network seams needed by script callers
  - implemented those seams in `beagle-host/providers/proxmox_host_provider.py` and rewired `get_guest_ipv4()` there to reuse the new guest-network contract instead of repeating the `qm guest cmd ... network-get-interfaces` call locally
  - rewrote `scripts/lib/beagle_provider.py` to create its provider through `beagle-host/providers/registry.py`, delegate reads/writes/guest-exec/reboot through the provider object, and expose provider-neutral CLI commands like `provider-kind`, `next-vmid`, `list-storage`, and `list-nodes`
  - kept the script-side `vm-node`, `vm-description`, and `vm-description-meta` helpers as small compositions on top of provider-backed `list_vms()` and `get_vm_config()` rather than direct Proxmox commands
  - validated with `py_compile`, a focused stub-provider registration smoke test that proved `scripts/lib/beagle_provider.py` now delegates through the registry contract, and `./scripts/validate-project.sh`
- Introduced the first real Beagle-owned provider skeleton instead of only documenting it as future work:
  - added `beagle-host/providers/beagle_host_provider.py` as a registry-backed, state-backed host provider implementation under the real host provider contract instead of an alias to Proxmox behavior
  - the host skeleton persists node, storage, VM, VM-config, guest-interface, guest-exec-status, and scheduled-restart state under `BEAGLE_BEAGLE_PROVIDER_STATE_DIR` (default `/var/lib/beagle/providers/beagle`)
  - implemented a minimum writable contract in the skeleton for `next_vmid`, `list_storage_inventory`, `list_nodes`, `list_vms`, `get_vm_config`, `create_vm`, `set_vm_options`, `delete_vm_options`, `set_vm_description`, `set_vm_boot_order`, `start_vm`, `reboot_vm`, `stop_vm`, `guest_exec_bash`, `guest_exec_status`, `guest_exec_script_text`, `schedule_vm_restart_after_stop`, and `get_guest_ipv4`
  - registered the new provider in `beagle-host/providers/registry.py`, so `BEAGLE_HOST_PROVIDER=beagle` is now a real bootstrap option instead of only planned architecture
  - rewired `scripts/install-beagle-host-services.sh` to sync every `*_host_provider.py` file into the host runtime instead of hard-coding `proxmox_host_provider.py`, which removes one more deploy-time Proxmox assumption before the Beagle provider exists on a live host
  - added `providers/beagle/virtualization-provider.js` as the first browser-side Beagle virtualization skeleton and documented its current HTTP-backed scope in `providers/beagle/README.md`
  - validated the new host skeleton with `py_compile`, `node --check`, a focused temp-state smoke test covering create/read/write/lifecycle/guest-exec/restart flows, and `./scripts/validate-project.sh`
- Re-aligned the refactor plan to the actual product target instead of stopping at "clean Proxmox abstraction":
  - updated `AGENTS.md` so the intended end-state is now explicit: a Beagle-owned bare-metal server installer ISO with two modes, `Beagle OS standalone` and `Beagle OS with Proxmox`, plus a dedicated Beagle Web Console as the long-term operator UI
  - updated `docs/refactor/02-target-architecture.md` to add explicit target modules for Beagle server installer modes and the future Beagle Web Console / Host UI instead of only documenting the Proxmox UI transition path
  - updated `docs/refactor/03-refactor-plan.md` so the staged roadmap now explicitly includes a dual-mode server-installer architecture, Beagle Web Console foundation work, and a standalone-Beagle operation stage before Proxmox becomes merely optional
  - updated the risk register so "ending at polished Proxmox integration without a standalone Beagle host/UI target" is now an explicit tracked architecture risk

### 2026-04-12 — standalone host proxy/web surface bootstrap

- Completed the next standalone installer slice so `Beagle OS standalone` now gets the same basic HTTPS/download/web operator surface provisioning instead of stopping at local control-plane validation only:
  - changed `scripts/install-beagle-proxy.sh` so proxy TLS material is no longer hard-wired to `/etc/pve/local/pveproxy-ssl.pem` and `/etc/pve/local/pveproxy-ssl.key`
  - added provider-aware default TLS paths there, using `/etc/beagle/tls/beagle-proxy.crt` and `/etc/beagle/tls/beagle-proxy.key` for the `beagle` provider while preserving the existing Proxmox defaults for the `proxmox` provider
  - added standalone self-signed certificate generation in `install-beagle-proxy.sh` for the `beagle` provider when no explicit certificate/key is configured yet, so first boot no longer depends on Proxmox-owned certificate files
  - made `scripts/install-beagle-host.sh` persist optional `BEAGLE_HOST_TLS_CERT_FILE` / `BEAGLE_HOST_TLS_KEY_FILE` into `host.env` and call `scripts/install-beagle-proxy.sh` for standalone Beagle installs even when `/etc/pve/local/pveproxy-ssl.pem` does not exist
  - kept the existing Proxmox UI integration path unchanged and still gated on `/usr/share/pve-manager/js`
  - extended `scripts/check-beagle-host.sh` so the standalone `beagle` provider path now validates:
    - nginx configuration presence
    - standalone TLS certificate presence
    - hosted `/beagle-downloads/*` artifact reachability over HTTPS
    - the Beagle Web UI root over the configured site port
    - in addition to the existing local control-plane health probe
- Validation:
  - `bash -n scripts/install-beagle-proxy.sh scripts/install-beagle-host.sh scripts/check-beagle-host.sh`
  - focused standalone proxy smoke test using a temp asset root plus stub `nginx` / `systemctl`, confirming self-signed TLS generation, env-file persistence, and both HTTPS listener blocks in the generated nginx config
  - focused standalone host-validation smoke test using temp install/config trees plus stub `curl` / `systemctl` / `id` / `getent`, confirming the `beagle` provider path validates the standalone TLS file, nginx, hosted download URLs, and the Web UI root successfully
  - `./scripts/validate-project.sh`

### 2026-04-12 — first provider-neutral browser virtualization read surface

- Added the first explicit provider-neutral browser/operator read surface for Beagle host virtualization data instead of continuing to synthesize it from `/api/v1/vms`:
  - added `beagle-host/services/virtualization_read_surface.py`
  - exposed authenticated GET routes for:
    - `/api/v1/virtualization/overview`
    - `/api/v1/virtualization/hosts`
    - `/api/v1/virtualization/nodes`
    - `/api/v1/virtualization/storage`
    - `/api/v1/virtualization/vms/<vmid>/config`
    - `/api/v1/virtualization/vms/<vmid>/interfaces`
  - wired `beagle-host/bin/beagle-control-plane.py` to lazy-create the new service and route those requests before the remaining inline fallback GET handlers
  - added thin wrappers in the control-plane entrypoint for `list_storage_inventory()` and `get_guest_network_interfaces()` so the new service consumes the same provider seam as the rest of the host inventory logic
- Removed more Beagle browser-provider synthesis:
  - changed `providers/beagle/virtualization-provider.js` so host/node/config/guest-interface reads now come from `/api/v1/virtualization/*` instead of deriving nodes from VM inventory and returning an empty guest-interface list
  - updated `providers/beagle/README.md` to document the new host-side contract and remove the outdated note that the provider still synthesizes config and guest interfaces
- Started using the new surface in the existing Beagle website shell:
  - changed `website/app.js` to fetch `/virtualization/overview` during dashboard load
  - the manager status line now shows provider plus node/storage counts, so the served website already consumes the new provider-neutral read surface instead of only VM inventory/policy/health payloads
- Validation:
  - `python3 -m py_compile beagle-host/services/virtualization_read_surface.py beagle-host/bin/beagle-control-plane.py`
  - `node --check providers/beagle/virtualization-provider.js`
  - `node --check website/app.js`
  - focused Python smoke test with the state-backed `beagle` provider confirming `overview`, VM config, and guest-interface routes
  - focused Node smoke test with mocked `BeagleUiApiClient` / `BeagleProviderRegistry` confirming the browser Beagle provider now really calls the new `/api/v1/virtualization/*` routes
  - `./scripts/validate-project.sh`

### Known risks after this run

- `beagle-control-plane.py` remains a large monolith, even though provider-backed read helpers now live in `beagle-host/services/virtualization_inventory.py`, endpoint compliance and VM-state composition now live in `beagle-host/services/vm_state.py`, and VM lifecycle writes, guest-exec flows, and scheduled restarts already flow through provider helpers.
- `proxmox-ui/beagle-ui.js` is materially smaller and no longer owns the profile synthesis, provisioning modal bodies, ExtJS wiring, or shared loading-shell markup/CSS, but it still holds bootstrap/context-resolution/token/url wrapper orchestration that should shrink further before it becomes a minimal entrypoint.
- Frontend token handling still exists as documented.
- The provider abstraction now covers Proxmox UI, browser extension, host-side reads, host-side VM lifecycle writes, guest-exec, scheduled restart orchestration, an explicit host-side endpoint profile contract, and shared browser-side profile mapper/helper modules. The remaining browser-side UI debt is now mostly in `proxmox-ui/beagle-ui.js` orchestration, `proxmox-ui/components/extjs-integration.js` runtime coupling to the current Proxmox ExtJS surface, and the still-large extension/proxmox profile action renderers.
- Script surfaces and installer-side provider neutrality are still pending.
- Local `.build/` and `dist/` directories still exist and should not be treated as authoritative release outputs.
- Live endpoints on older released payloads can still boot back into pre-fix runtime scripts even after an on-device hot patch; validating runtime refactors against a real endpoint now requires either a rebuilt thin-client payload/update or an explicit post-boot deployment step.
- Already downloaded host USB installers without the self-bootstrap fix will continue to fail until refreshed from regenerated host download artifacts.
- The first `beagle` provider is now real, but it is still a state-backed skeleton and not yet a compute/runtime backend. It proves contract shape and deploy wiring, not a finished hypervisor implementation.
- `providers/beagle/virtualization-provider.js` now consumes a provider-neutral read surface for hosts/nodes/config/interfaces, but storage/network inventory is not yet surfaced into the website or other browser clients as first-class operator flows.
- The plan is now pointed at the correct end-state, but there is still no implemented Beagle Web Console module and no finished standalone server-installer branch yet; those remain planning and implementation gaps, not solved work.
- The standalone install path now provisions nginx plus HTTPS/download/web entrypoints, but its operator surface is still only the existing website shell over current control-plane endpoints; it is not yet a dedicated provider-neutral Beagle Web Console with node/storage/network inventory or Beagle-runtime lifecycle actions.
