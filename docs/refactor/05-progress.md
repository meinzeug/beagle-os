# Refactor Progress

## 2026-04-09

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

### Known risks after this run

- `beagle-control-plane.py` remains a large monolith, even though provider-backed read helpers now live in `beagle-host/services/virtualization_inventory.py`, endpoint compliance and VM-state composition now live in `beagle-host/services/vm_state.py`, and VM lifecycle writes, guest-exec flows, and scheduled restarts already flow through provider helpers.
- `proxmox-ui/beagle-ui.js` is materially smaller and no longer owns the profile synthesis, provisioning modal bodies, ExtJS wiring, or shared loading-shell markup/CSS, but it still holds bootstrap/context-resolution/token/url wrapper orchestration that should shrink further before it becomes a minimal entrypoint.
- Frontend token handling still exists as documented.
- The provider abstraction now covers Proxmox UI, browser extension, host-side reads, host-side VM lifecycle writes, guest-exec, scheduled restart orchestration, an explicit host-side endpoint profile contract, and shared browser-side profile mapper/helper modules. The remaining browser-side UI debt is now mostly in `proxmox-ui/beagle-ui.js` orchestration, `proxmox-ui/components/extjs-integration.js` runtime coupling to the current Proxmox ExtJS surface, and the still-large extension/proxmox profile action renderers.
- Script surfaces and installer-side provider neutrality are still pending.
- Local `.build/` and `dist/` directories still exist and should not be treated as authoritative release outputs.
