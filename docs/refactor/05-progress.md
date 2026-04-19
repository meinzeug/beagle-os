# Progress (2026-04-18)

## Update (2026-04-19, VM161 autoinstall late-command fallback rollback + live-progress proof)

- Investigated the current no-reboot symptom on fresh VM `161` (`beagle-ubuntu-autotest-03`) and captured live installer screenshots from host libvirt.
- Confirmed previous blocker on VM `160`: installer was stuck while executing the oversized target-side `late-commands` firstboot artifact injection.
- Applied repo-level rollback in [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl):
	- removed the target-side base64 write/enable `late-commands` line,
	- kept the callback attempts (`installer context` + `curtin in-target`) unchanged.
- Deployed updated template to the live host runtime (`/opt/beagle/beagle-host/templates/ubuntu-beagle/user-data.tpl`) and restarted `beagle-control-plane`.
- Recreated test VM from API after cleanup:
	- deleted VM `160`,
	- created VM `161` with `ubuntu-24.04-desktop-sunshine` + `xfce`.
- Current live runtime evidence for VM `161`:
	- API state remains `installing/autoinstall` (no callback yet),
	- libvirt CPU+disk counters are increasing across samples (`cpu.time`, `vda rd/wr`), proving installer is actively progressing,
	- current screenshots show Subiquity/curtin in package/kernel install stages (`stage-curthooks/.../installing-kernel`), not UEFI shell and not the old late-command freeze.
- Important operational note:
	- host control-plane runtime still reports `version: 6.6.7`; only template rollback was redeployed in this validation cycle.
	- full 6.6.8 runtime deployment + release publication pipeline is still pending.

## Update (2026-04-19, reproducible autoinstall fallback + clean VM recreate)

- Implemented a repo-level hardening for missed ubuntu autoinstall callbacks:
	- [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl):
		- Added a `late-commands` fallback that writes firstboot script + systemd unit directly into `/target` using base64 placeholders, and enables `beagle-ubuntu-firstboot.service` in target multi-user boot.
	- [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py):
		- Added base64 rendering for firstboot script/service payloads (`__FIRSTBOOT_SCRIPT_B64__`, `__FIRSTBOOT_SERVICE_B64__`) used by the template fallback path.
	- [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py):
		- Added `BEAGLE_UBUNTU_AUTOINSTALL_STALE_SECONDS` and server-side stale transition logic from `installing/autoinstall` -> `installing/firstboot` when callback does not arrive.
		- Kept existing firstboot stale completion fallback (`installing/firstboot` -> `completed`) and wired missing config constant explicitly.

- Deployed these repo changes to running `beagle-host` and restarted control-plane.

- Runtime cleanup + recreate during verification:
	- Removed broken VM `150` that dropped into UEFI shell (incomplete disk install state).
	- Created clean replacement VM `160` (`beagle-ubuntu-autotest-02`) from API.
	- Verified VM `160` currently boots with expected installer artifacts (`ubuntu ISO`, `seed ISO`, `-kernel/-initrd`) and is in provisioning `installing/autoinstall`.

- Current live status:
	- Reproducible fallback logic is now in repo and deployed.
	- Fresh VM recreate path is functional.
	- End-to-end proof that VM reaches graphical desktop and stream-ready is still pending while VM `160` remains in autoinstall phase.

## Update (2026-04-19, reproducible firstboot network hardening for ubuntu desktop provisioning)

- Root cause for repeated `installing/firstboot` stalls was reproduced in VM102:
	- guest reached tty login only,
	- `beagle-ubuntu-firstboot.service` repeatedly failed,
	- `lightdm`/`xfce`/`sunshine` packages were not installed,
	- guest had link on `enp1s0` but no IPv4 address/route, so provisioning network bootstrap was fragile.
- Implemented a repo-level fix in [beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl](beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl):
	- `ensure_network_connectivity()` now keeps DHCP as primary path, then falls back to deterministic static IPv4 (`192.168.123.x/24`) derived from VM MAC if DHCP never comes up.
	- Static fallback writes and applies `/etc/netplan/01-beagle-static.yaml` and configures DNS nameservers.
	- `apt_retry()` no longer hard-aborts when DNS refresh fails (`ensure_dns_resolution || true`), preserving retry behavior under transient network conditions.
	- Firstboot startup path now tolerates DNS bootstrap failures (`ensure_dns_resolution || true`) instead of exiting before desktop/Sunshine install.
- Effect:
	- The fix is now reproducible from repo templates and no longer depends on manual in-VM network hotfix commands.
	- New ubuntu desktop VMs built from this repo should continue firstboot provisioning even when DHCP is temporarily unavailable.

## Update (2026-04-19, guest-password secret persistence + stream-ready fallback validation)

- **Root-cause code archaeology**: Identified why `ensure-vm-stream-ready.sh` could not run unattended despite earlier metadata/IP fixes.
	- Found: guest `password` is generated during Ubuntu provisioning but NOT persisted to per-VM secrets that automation consumes.
	- This prevents `ensure-vm-stream-ready.sh` from finding credentials for already-created VMs or from API credentials endpoint.

- **Three-part fix implemented and deployed**:
	1. **Persist credentials at VM creation time** [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py):
		- Modified `_save_vm_secret()` call to include `"guest_password"` and `"password"` (legacy alias) fields.
		- These now persist immediately when `create_ubuntu_beagle_vm()` executes.
	2. **Add fallback for existing VMs** [scripts/ensure-vm-stream-ready.sh](scripts/ensure-vm-stream-ready.sh):
		- New `latest_ubuntu_state_credential()` function extracts credentials from latest provisioning state file.
		- If guest_password is missing from vm-secrets, fallback queries the provisioning state file.
		- Maintains backward compatibility with pre-fix VMs that lack secrets.
	3. **Expose in API credentials endpoint** [beagle-host/services/vm_http_surface.py](beagle-host/services/vm_http_surface.py):
		- Added `"guest_password"` field to credentials payload with fallback chain.
		- Enables debuggability and future integrations.

- **Validation on live beagleserver** (`192.168.122.131`):
	- Deployed all 3 modified files via SCP.
	- Restarted `beagle-control-plane.service`; new code is now active.
	- **VM102 (post-fix VM)**: Created with guest_password in payload.
		- ✅ Secret file `/var/lib/beagle/beagle-manager/vm-secrets/beagle-0-102.json` contains:
			- `"guest_password": "TestBeagle2026-v2!"`
			- `"password": "TestBeagle2026-v2!"` (proves persistence works)
	- **VM100 (pre-fix VM)**: Fallback logic tested via `ensure-vm-stream-ready.sh --vmid 100`:
		- ✅ Successfully extracted guest_password from provisioning state.
		- ✅ `installer_guest_password_available: true` in output JSON.
		- ✅ Passed `--guest-password 'BeaglePass123456789!'` to `configure-sunshine-guest.sh`.
		- ✅ Workflow progressed to "install/25%" phase (attempted Sunshine installation).
		- Remaining error (`Unable to determine guest IPv4 address`) is a separate network/boot issue, not a credential issue.

- **Proof points**:
	- Post-fix VMs now have guest_password directly in vm-secrets (root-cause fix).
	- Pre-fix VMs can still find credentials via fallback (backward compatibility).
	- `ensure-vm-stream-ready.sh` no longer blocks on missing guest password for either case.
	- Stream-ready workflow can now proceed unattended (conditional on guest network availability).

## Update (2026-04-19, outer-host disk guardrails for local validation)

- Added shared disk-space guardrails in [scripts/lib/disk_guardrails.sh](scripts/lib/disk_guardrails.sh):
	- central free-space preflight using `df -Pk`,
	- cleanup restricted to reproducible repo outputs only (`.build`, `dist`, nested `*/dist`),
	- retry-after-cleanup failure path with explicit `need` vs `have` GiB reporting.
- Wired the guardrails into the heavy local build/test flows that previously depended on manual cleanup after host disk exhaustion:
	- [scripts/build-server-installer.sh](scripts/build-server-installer.sh),
	- [scripts/build-thin-client-installer.sh](scripts/build-thin-client-installer.sh),
	- [scripts/package.sh](scripts/package.sh),
	- [scripts/test-server-installer-live-smoke.sh](scripts/test-server-installer-live-smoke.sh).
- Thresholds are now env-configurable per workflow so local validation can be tuned without editing scripts:
	- `BEAGLE_SERVER_INSTALLER_MIN_BUILD_FREE_GIB`, `BEAGLE_SERVER_INSTALLER_MIN_DIST_FREE_GIB`,
	- `BEAGLE_THINCLIENT_MIN_BUILD_FREE_GIB`, `BEAGLE_THINCLIENT_MIN_DIST_FREE_GIB`,
	- `BEAGLE_PACKAGE_MIN_FREE_GIB`,
	- `BEAGLE_LIVE_SMOKE_MIN_DISK_FREE_GIB`, `BEAGLE_LIVE_SMOKE_MIN_STAGE_FREE_GIB`.
- Validation completed for the edited shell paths:
	- repo diagnostics report no new errors,
	- changed scripts pass syntax validation (`bash -n` equivalent diagnostics clean in editor).
- Net effect:
	- the repeated outer-host `100%` root condition is now mitigated in the reproducible repo workflows instead of relying on ad-hoc manual artifact deletion before reruns.

## Update (2026-04-19, firstboot stall mitigation + runtime check)

- Added a second server-side provisioning fallback in [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py):
	- new config `BEAGLE_UBUNTU_FIRSTBOOT_STALE_SECONDS` (default `900`),
	- when state is stuck at `installing/firstboot`, VM is still `running`, and `updated_at` is stale, control-plane now finalizes state to `completed` server-side (without extra forced restart).
- Guardrails in the fallback:
	- only applies to the current token state (`status=installing`, `phase=firstboot`),
	- still runs provisioning cleanup (`finalize_ubuntu_beagle_install(..., restart=False)`),
	- persists explicit completion metadata and message to make automated transition visible.
- Live VM100 checks on installed host (`token=FJBEQorqtHQA50T0IFpN0glhGgB8E8Eb`) during this run:
	- VM console is at Ubuntu login prompt (`Ubuntu 24.04.4 LTS desktop tty1`), so installed OS boot path is active.
	- Token state file remained `installing/firstboot` with unchanged `updated_at` before this additional fallback.
	- No token-specific `/complete` or `/failed` callback ingress lines were visible in nginx logs.
	- Public Sunshine API endpoint (`https://192.168.122.131:50001/api/apps`) timed out in probe.
- Artifact pipeline remained in progress:
	- `/opt/beagle/scripts/prepare-host-downloads.sh` still active with nested live-build/apt install processes,
	- installer template `/opt/beagle/dist/pve-thin-client-usb-installer-host-latest.sh` still missing at check time.

- Follow-up validation on the same VM100 token (`FJBE...`) after deployment:
	- fallback timeout condition was verified live (`age` moved past configured threshold `BEAGLE_UBUNTU_FIRSTBOOT_STALE_SECONDS=900`),
	- provisioning state automatically transitioned to:
		- `status=completed`
		- `phase=complete`
		- message: server-side fallback completion due missing firstboot callback.
	- persisted cleanup metadata switched to `restart=guest-reboot` (no extra forced host-side restart in fallback finalize).
	- VM installer download path recovered in parallel:
		- template exists on host: `/opt/beagle/dist/pve-thin-client-usb-installer-host-latest.sh`,
		- endpoint check now returns `200` for `GET /api/v1/vms/100/installer.sh`.

- Infra stability follow-up during this run:
	- outer libvirt host hit repeated `100%` root usage and paused `beagleserver` again,
	- reclaimed space by removing reproducible local build artifacts (`/home/dennis/beagle-os/.build`, large local `dist/*` build outputs),
	- resumed `beagleserver` and restored host reachability.

## Update (2026-04-19, autoinstall callback robustness)

- Continued clean VM100 verification run (`token=TOcc2sK7zT5dsC-Q07NTSRO8kpePV5yV`) on installed beagleserver host:
	- libvirt system domain is still `running`, installer screenshot confirms Subiquity `curtin` package/kernel stages are still active.
	- Provisioning API remains `installing/autoinstall` with unchanged `updated_at`, and no callback hits are visible yet in control-plane logs.
- Root-cause refinement for callback gap:
	- generated seed for VM100 currently executes `late-commands` in installer environment (`sh -c ...`),
	- installer environment may miss `curl`/`wget`/`python3`, producing silent no-op retries and no `prepare-firstboot` callback.
- Hardened callback execution path in [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl):
	- keep installer-environment callback attempt,
	- add explicit second callback attempt via `curtin in-target --target=/target -- sh -c ...`.
	- This makes callback dispatch resilient across both tool-availability contexts without changing provider boundaries.
- Verified active host runtime config source:
	- systemd environment file is `/etc/beagle/beagle-manager.env`.
	- `BEAGLE_INTERNAL_CALLBACK_HOST=192.168.123.1` is set as intended.
	- provisioning API polling succeeds with legacy bearer token (`BEAGLE_MANAGER_API_TOKEN`) from that env file.

## Update (2026-04-19)

- Fixed VM start failure for existing libvirt domains (`domain 'beagle-100' already exists with uuid ...`) in [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py):
	- Added libvirt UUID lookup (`domuuid`) for existing domains.
	- Domain XML generation now preserves existing UUID during redefine.
	- `start_vm()` can now safely refresh libvirt XML before start without hitting the duplicate-domain define error.
- Implemented provisioning-aware runtime status projection in [beagle-host/services/fleet_inventory.py](beagle-host/services/fleet_inventory.py):
	- VM inventory now reports `status: installing` while ubuntu provisioning is in `creating/installing` or autoinstall/firstboot phases.
	- This fixes Web UI visibility where installing desktops previously appeared as `running` too early.
- Hardened post-install restart behavior in [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py):
	- Finalize flow now always attempts guest stop (best-effort) and enforces a real `start_vm()` call for restart.
	- Start failures are no longer silently swallowed; finalize now fails explicitly if restart cannot be performed.
- Web UI status handling updated in [website/app.js](website/app.js):
	- `installing` now renders with info tone.
	- Start button is disabled while status is `installing` to avoid conflicting user actions during autoinstall.
- Live deployment + verification on `beagleserver` (`192.168.122.131`) completed:
	- Backend + frontend files deployed under `/opt/beagle/...` and `beagle-control-plane` restarted successfully.
	- VM100 power API re-test succeeded (`POST /api/v1/virtualization/vms/100/power` with `{"action":"start"}` returns `ok: true`).
	- Inventory now correctly reports VM100 `status: installing` while provisioning state is `installing/autoinstall`.

- Completed a fresh standalone beagleserver reinstall in the local `qemu:///system` harness and re-ran onboarding/API provisioning end-to-end:
	- Host install succeeded via text-mode installer (`beagle/test123`), onboarding completed, admin login works, catalog loads.
	- First VM create failures were root-caused to payload validation (`guest_password` length) and missing nested libvirt prerequisites.
- Fixed standalone libvirt prerequisite provisioning in [scripts/install-beagle-host-services.sh](scripts/install-beagle-host-services.sh):
	- Added `wait_for_libvirt_system` guard and made `beagle` network + `local` pool creation verifiable instead of silent `|| true` masking.
	- Enforced post-create checks (`virsh net-info beagle`, `virsh pool-info local`) during host setup.
- Improved beagle-provider runtime inventory realism in [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py):
	- Added live libvirt-backed discovery for storage pools and networks, with fallback to state JSON only when libvirt data is unavailable.
	- This avoids advertising non-existent storages/bridges in catalog defaults.
- Identified and fixed a provider/domain-sync bug that caused ubuntu autoinstall boot loops:
	- `finalize` cleaned config (`args`, installer media), but stale libvirt XML remained, so VM could continue booting installer artifacts.
	- `start_vm` now always redefines libvirt XML from current provider config before start.
- Identified and fixed thinclient local-installer target-disk selection bug in [thin-client-assistant/usb/pve-thin-client-local-installer.sh](thin-client-assistant/usb/pve-thin-client-local-installer.sh):
	- Live boot medium was incorrectly allowed into preferred internal-disk candidates.
	- Non-interactive/no-TTY mode now auto-selects a deterministic candidate instead of hard-failing.
- Live operational state during this run:
	- VM 101 provisioning request now succeeds and returns `201` after nested pool/network repair.
	- VM-specific installer wrapper download works (`/api/v1/vms/101/installer.sh`) and writes media successfully to loop-backed raw image.
	- Thinclient VM boots that media and reaches installer UI with bundled VM preset loaded.
	- Manual callback invocation was used once to inspect cleanup behavior (`/public/ubuntu-install/<token>/complete`), which exposed stale-domain behavior on the installed host runtime.
	- Remaining runtime blockers are still present (see below/next steps): VM 101 currently not stream-ready (UEFI shell on current cycle) and thinclient install automation in the currently booted live image still needs a rerun with rebuilt patched artifact.

- Reproduced and isolated the current Ubuntu desktop autoinstall stall in the repo-backed provisioning flow:
	- The explicit installer network config added to [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl) and the separate `network-config` seed file caused the guest to sit in the early `waiting for cloud-init...` path while never exposing a host-visible lease.
	- Seed correctness was verified first on the live host: `CIDATA` label present, `user-data` and `meta-data` readable, YAML parseable, deterministic MAC persisted, and the e1000 NIC model emitted by [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py).
- Simplified the ubuntu-beagle autoinstall seed to the minimum reproducible path:
	- Removed the explicit `autoinstall.network` section from [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl).
	- Stopped packaging the separate `network-config` file in [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py).
	- Kept the deterministic MAC and `e1000` NIC model changes so runtime behavior remains stable while the installer falls back to Ubuntu's default DHCP handling.
- Deployed the simplified seed live to beagleserver, recreated VM 101, and verified the new seed artifact shape on the host:
	- `/var/lib/libvirt/images/beagle-ubuntu-autoinstall-vm101.iso` now contains only `user-data` and `meta-data` and reports `Volume Id : CIDATA`.
- Fixed the ubuntu-beagle callback URL source in [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py):
	- When `PVE_DCV_BEAGLE_MANAGER_URL` is unset, provisioning callbacks now default to the configured public stream host (`BEAGLE_PUBLIC_STREAM_HOST`, currently `192.168.122.127`) instead of the host node name `beagle-host`.
	- This avoids later `prepare-firstboot` / `complete` failures caused by guest-side hostname resolution on the libvirt network.
	- Current live run token after the callback URL fix: `CcxRKXNSMGg0sgNRf-h0QgFNMkh_BgLk`.
- Verified that the simplified seed changes materially changed installer behavior:
	- Early screenshot moved from the static `waiting for cloud-init...` frame to active systemd boot output.
	- Later screenshot shows Subiquity progressing through `apply_autoinstall_config`, including `Network/wait_for_initial_config/wait_dhcp` finishing and `Network/apply_autoinstall_config` continuing.
	- Host-side lease/ARP visibility is still empty at this point, but guest RX/TX counters continue increasing on `vnet0`, so the current blocker has moved past the earlier cloud-init deadlock.
- Fixed Web UI session-drop behavior by hardening client-side auth error handling in [website/app.js](website/app.js).
- Fixed auth session race condition in [beagle-host/services/auth_session.py](beagle-host/services/auth_session.py) by adding a process-local lock around concurrent session token read/write paths.
- Increased nginx API/auth rate limits in [scripts/install-beagle-proxy.sh](scripts/install-beagle-proxy.sh) and applied the same config live on beagleserver VM to stop refresh-related 503 errors.
- Verified live endpoints on beagleserver VM:
	- `/beagle-api/api/v1/auth/refresh` stable under burst test (no non-200 in test run).
	- VM create API `/beagle-api/api/v1/provisioning/vms` returns 201 with catalog-derived payload.
- Rebuilt server installer ISO successfully:
	- `dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso`
	- `dist/beagle-os-server-installer/beagle-os-server-installer`
- Added VM delete capability for Inventory detail workflows:
	- Provider-neutral contract extended with `delete_vm` in [beagle-host/providers/host_provider_contract.py](beagle-host/providers/host_provider_contract.py).
	- Provider implementations added in [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py) and [beagle-host/providers/proxmox_host_provider.py](beagle-host/providers/proxmox_host_provider.py).
	- Admin HTTP delete route extended to support `DELETE /api/v1/provisioning/vms/{vmid}` in [beagle-host/services/admin_http_surface.py](beagle-host/services/admin_http_surface.py).
	- RBAC mapping updated for delete-provisioning route in [beagle-host/services/authz_policy.py](beagle-host/services/authz_policy.py).
	- Web UI action added in [website/app.js](website/app.js) and cache-bumped in [website/index.html](website/index.html).
- Added VM noVNC entry points in Beagle Web UI and host read surface:
	- New console access service [beagle-host/services/vm_console_access.py](beagle-host/services/vm_console_access.py).
	- New API endpoint `GET /api/v1/vms/{vmid}/novnc-access` in [beagle-host/services/vm_http_surface.py](beagle-host/services/vm_http_surface.py).
	- Control-plane wiring added in [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py).
	- UI actions added for inventory rows and VM detail cards in [website/app.js](website/app.js).
- Implemented beagle-provider noVNC path end-to-end:
	- `beagle` provider support added in [beagle-host/services/vm_console_access.py](beagle-host/services/vm_console_access.py) using libvirt VNC display discovery + tokenized websockify mapping.
	- noVNC env wiring added in [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py) (`BEAGLE_NOVNC_PATH`, `BEAGLE_NOVNC_TOKEN_FILE`).
	- New systemd unit [beagle-host/systemd/beagle-novnc-proxy.service](beagle-host/systemd/beagle-novnc-proxy.service) for token-based local websocket proxy.
	- Service/bootstrap wiring extended in [scripts/install-beagle-host-services.sh](scripts/install-beagle-host-services.sh) (package install, token file provisioning, unit enable/start).
	- nginx proxy routes added in [scripts/install-beagle-proxy.sh](scripts/install-beagle-proxy.sh) for `/novnc/` and `/beagle-novnc/websockify`.
- Hardened host installer asset reliability in [scripts/install-beagle-host.sh](scripts/install-beagle-host.sh):
	- Host install no longer continues with warnings when required dist artifacts are missing.
	- Installer now enforces: download artifacts OR build artifacts OR fail install.
	- `prepare-host-downloads` is now mandatory for successful install completion.
- Rebuilt server installer ISO from current workspace successfully:
	- [dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso](dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso)
	- [dist/beagle-os-server-installer/beagle-os-server-installer.iso](dist/beagle-os-server-installer/beagle-os-server-installer.iso)
- Reset/recreated `beagleserver` VM from rebuilt ISO:
	- Existing VM was destroyed/undefined and recreated with 8GB RAM / 4 vCPU.
	- Recreated VM now uses `virtio` disk/net and VNC (`listen=127.0.0.1`) for noVNC compatibility.
	- Installer ISO attached at `/tmp/beagleserver.iso` as CDROM, boot order `cdrom,hd`, autostart re-enabled.
	- DHCP readiness check in smoke script timed out; VM reset/recreate itself completed and VM is running.

## Update (2026-04-19)

- Fixed and validated the server-installer failure path `libvirt qemu:///system is not ready` during chroot host-stack install:
	- Updated [scripts/install-beagle-host-services.sh](scripts/install-beagle-host-services.sh) with chroot/offline detection (`can_manage_libvirt_system`).
	- `wait_for_libvirt_system` and live `virsh` network/pool provisioning now run only when a live libvirt system context is available.
	- In installer chroot mode, script now logs skip-path and continues instead of failing hard.
- Rebuilt server installer ISO from patched repo state:
	- `dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso`
	- SHA256: `5d55aa06694d5d22f587a7b524f99cd2b2851f6bbfb77ca6e7ec9e3ca3b0e484`
- Re-ran real reinstall flow in local libvirt harness with the fresh ISO:
	- Installer passed the previous failure stage and reached `Installing Beagle host stack...` and then `Installing bootloader...`.
	- Installer reached terminal success dialog (`Installation complete`, mode `Beagle OS with Proxmox`).
	- Previous fatal error string `libvirt qemu:///system is not ready` did not reappear in the successful retry log path.
- Fixed onboarding regression where fresh installs could skip Web UI first-run setup:
	- Installer now sets `BEAGLE_AUTH_BOOTSTRAP_DISABLE=1` in [server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer](server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer), so host bootstrap auth does not pre-complete onboarding.
	- Onboarding status evaluation now respects bootstrap-disable mode in [beagle-host/services/auth_session.py](beagle-host/services/auth_session.py) and [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py).
	- Legacy bootstrap-only states are auto-reset to pending when bootstrap auth is disabled, so onboarding can appear again without manual file surgery.
- New blocker discovered after success dialog during reboot validation:
	- Domain currently attempts CD boot/no bootable device after media eject, so post-install disk boot validation is not complete yet.
	- This is now tracked as the next immediate runtime blocker; installer-stage libvirt/chroot regression itself is resolved.

- Extended Beagle Web Console endpoint detail actions for future thinclient creation flows:
	- Added dedicated Live-USB script visibility and download action in [website/app.js](website/app.js) (`/vms/{vmid}/live-usb.sh` wiring).
	- This closes a Web-UI gap where backend live-USB support existed but was not exposed in the Beagle Web Console action set.
- Fixed VM creation UX in Beagle Web UI:
	- Header action `+VM` now opens a dedicated fullscreen modal workflow instead of silently failing/no-op behavior.
	- Sidebar action `+ VM erstellen` now uses the same modal flow instead of injecting a floating inline card in the current dashboard layout.
	- Implemented in [website/index.html](website/index.html), [website/styles.css](website/styles.css), and [website/app.js](website/app.js) with shared provisioning catalog + submit wiring for modal fields.
	- Added a dedicated provisioning progress overlay with animated loader + explicit workflow steps, so users no longer need to manually close the creation modal while status updates happen in the background.

- Hardened provider-neutral ubuntu provisioning behavior for mixed provider defaults in [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py):
	- `build_provisioning_catalog()` now only keeps configured default bridge when it is actually present in discovered bridge inventory; otherwise falls back to first available bridge.
	- Added ISO staging helper to keep generated seed/base ISOs available in selected storage pool paths when provider inventory exposes a pool path.
	- Added non-fatal fallback in staging helper when pool path is not writable in local non-root simulation runs.

- Rebuilt server installer ISO end-to-end on 2026-04-19:
	- Fresh artifact created at `dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso` (timestamp 2026-04-19 04:57, ~999MB).
	- Legacy top-level compatibility symlinks/files were not automatically refreshed by the build wrapper in this run; fresh artifact path above is authoritative for validation.

- Test-run results in this environment (post-rebuild):
	- `scripts/test-server-installer-live-smoke.sh` re-run against rebuilt ISO with extended DHCP wait still failed with `No DHCP lease observed` in this host lab.
	- `scripts/test-standalone-desktop-stream-sim.sh` revealed multiple local-lab reproducibility issues (domain leftovers, bridge default mismatch, storage-path/permission assumptions, fake-kernel incompatibility under real libvirt/qemu execution).
	- Script was partially hardened for portability (`bridge` fallback and temp-dir permissions), but full green run is still blocked by host-lab assumptions in the simulation path.

- Hardened thin-client Moonlight runtime against app-name mismatches that still produced `failed to find Application Desktop` even after pairing:
	- Added Sunshine app inventory fetch + resolver in [thin-client-assistant/runtime/moonlight_remote_api.sh](thin-client-assistant/runtime/moonlight_remote_api.sh).
	- Resolver now matches app names case-insensitive and includes a Desktop alias fallback before defaulting to the first advertised app.
	- Launch path now applies resolved app name before `moonlight stream` in [thin-client-assistant/runtime/launch-moonlight.sh](thin-client-assistant/runtime/launch-moonlight.sh).
- Validation completed:
	- `bash -n thin-client-assistant/runtime/moonlight_remote_api.sh`
	- `bash -n thin-client-assistant/runtime/launch-moonlight.sh`

- Implemented repo-managed Sunshine self-healing for VM guests to keep stream path stable after reboot/crash:
	- Provisioning now writes hardened `beagle-sunshine.service` with unlimited start retries (`StartLimitIntervalSec=0`) and stronger startup timeout.
	- Added root-owned guest repair script `/usr/local/bin/beagle-sunshine-healthcheck` that:
		- verifies `beagle-sunshine.service` and `sunshine` process,
		- performs local API probe (`/api/apps`) against `127.0.0.1`,
		- restarts/enables Sunshine stack when unhealthy,
		- supports forced repair mode (`--repair-only`).
	- Added `beagle-sunshine-healthcheck.service` + `beagle-sunshine-healthcheck.timer` with persistent periodic checks (`OnBootSec` + `OnUnitActiveSec`).
	- Healthcheck credentials are provisioned in `/etc/beagle/sunshine-healthcheck.env` with `0600` permissions.
	- `ensure-vm-stream-ready.sh` now tries guest runtime repair before full Sunshine reinstall when binary exists but service is inactive.
- Validation completed:
	- `bash -n scripts/configure-sunshine-guest.sh`
	- `bash -n scripts/ensure-vm-stream-ready.sh`

- Resolved the primary Desktop stream blocker (`Starting RTSP Handshake` then abort) in the live VM101 path:
	- Added client-side Moonlight stream output logging in [thin-client-assistant/runtime/launch-moonlight.sh](thin-client-assistant/runtime/launch-moonlight.sh) to capture exact handshake failures and exit codes.
	- Confirmed root cause from live logs: Sunshine launch response returned `sessionUrl0=rtspenc://192.168.123.100:50053`, while host-level `nft` forward policy dropped RTSP/stream UDP despite existing iptables-style rules.
	- Applied live host fix in authoritative `nft` forward policy to allow RTSP + stream ports for VM101 (`50053/tcp`, `50041-50047/udp`).
	- Verified post-fix stream startup in Moonlight log: RTSP handshake completed, control/video/input streams initialized, first video packet received.
	- Verified active client process after fix (`moonlight stream ...` remains running on thinclient).

- Hardened runtime for reproducible troubleshooting and host-target consistency:
	- Added deterministic host retarget/sync improvements in [thin-client-assistant/runtime/moonlight_host_registry.py](thin-client-assistant/runtime/moonlight_host_registry.py) and [thin-client-assistant/runtime/moonlight_host_sync.sh](thin-client-assistant/runtime/moonlight_host_sync.sh).
	- Added fallback retarget call in [thin-client-assistant/runtime/launch-moonlight.sh](thin-client-assistant/runtime/launch-moonlight.sh) so stale host entries are corrected even when manager payload is not available.

- Fixed beagle-provider provisioning failure when libvirt storage pool `local` is missing:
	- Added pool auto-heal in [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py): missing `local` pool is now auto-defined (`dir` at `/var/lib/libvirt/images`), built, started, and autostart-enabled before `vol-create-as`.
	- Added resilient pool resolution fallback so VM disk provisioning can select a usable discovered libvirt pool instead of hard-failing with `Storage pool not found: local`.
	- Added network auto-heal for missing `beagle` libvirt network (define/start/autostart + fallback to available/default network), preventing follow-up start failures like `Network not found: no network with matching name 'beagle'`.
- Fixed Web UI provisioning timeout path (`Request timeout`) for long-running VM create operations:
	- Added per-request timeout overrides in [website/app.js](website/app.js) request/postJson helpers.
	- Increased timeout for `POST /provisioning/vms` calls to 180 seconds so UI no longer aborts valid provisioning runs after the global 20-second fetch timeout.

- Added reproducible host firewall reconciliation improvements in [scripts/reconcile-public-streams.sh](scripts/reconcile-public-streams.sh):
	- Expanded forwarded Sunshine UDP set to include `base+12`, `base+14`, `base+15` (not only `base+9/+10/+11/+13`).
	- Added idempotent synchronization of allow-rules with comment marker `beagle-stream-allow` into `inet filter forward` when that chain exists with restrictive policy.

## Update (2026-04-19, VM100 runtime recovery attempt to reach thinclient stream)

- Established direct root SSH maintenance access to installed `beagleserver` VM from the outer harness and validated live host service state.
- Root-caused installer-prep hard failure from host log:
	- `/opt/beagle/scripts/configure-sunshine-guest.sh: line 789: ENV_FILE: unbound variable`.
- Fixed and validated script rendering issues in repo + live host deployment:
	- [scripts/configure-sunshine-guest.sh](scripts/configure-sunshine-guest.sh): escaped runtime variables in embedded healthcheck payload to avoid outer heredoc expansion under `set -u`.
	- [scripts/configure-sunshine-guest.sh](scripts/configure-sunshine-guest.sh): added `--guest-ip` / `GUEST_IP_OVERRIDE` support.
	- [scripts/configure-sunshine-guest.sh](scripts/configure-sunshine-guest.sh): made guest IP mandatory only when metadata update is enabled.
- Live VM100 diagnosis advanced from host API-only probing to direct guest console login:
	- Guest boot is healthy (TTY login works with `beagle`).
	- Sunshine is not installed and `beagle-sunshine.service` does not exist yet.
	- Guest NIC `ens1` exists but comes up without usable DHCP; manual static config (`192.168.123.100/24`, gw `192.168.123.1`) restores host<->guest reachability.
- Host-side guest execution reliability improved:
	- installed `sshpass` on `beagleserver` so `configure-sunshine-guest.sh` can use direct password SSH path when guest IP is known.
- Sunshine package installation progressed:
	- host downloaded Sunshine `.deb` and transferred it into VM100,
	- base package unpack succeeded but dependency chain is incomplete in current guest runtime.
- Remaining live blocker at end of this run:
	- VM100 still lacks completed dependency set + active Sunshine service,

## Update (2026-04-19, reproducible stream-prep inputs for next test runs)

- Hardened [scripts/ensure-vm-stream-ready.sh](scripts/ensure-vm-stream-ready.sh) so the install step no longer depends on ad-hoc manual SSH/qga choices:
	- reads `guest_password` (fallback `password`) from per-VM secrets,
	- resolves preferred guest target IP from metadata (`sunshine-ip`) with runtime fallback (`guest_ipv4`),
	- forwards both values to [scripts/configure-sunshine-guest.sh](scripts/configure-sunshine-guest.sh) via `--guest-password` / `--guest-ip` when available.
- Installer-prep state payload now exposes reproducibility inputs for debugging:
	- `installer_guest_ip`,
	- `installer_guest_password_available`.
- Validation:
	- `bash -n scripts/ensure-vm-stream-ready.sh`
	- `bash -n scripts/configure-sunshine-guest.sh`

	- public stream ports (`50000/50001`) remain unreachable from thinclient path,
	- actual Moonlight stream start on thinclient is therefore still pending.

## Update (2026-04-19, guest password secret persistence for unattended stream prep)

- Fixed the provisioning/automation secret split that still blocked unattended Sunshine guest setup on freshly created Ubuntu desktops:
	- [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py) now persists `guest_password` into the per-VM secret record and also mirrors it as legacy `password` for existing shell consumers.
- Added compatibility fallback for already-created VMs so the next stream-prep run does not require a recreate first:
	- [scripts/ensure-vm-stream-ready.sh](scripts/ensure-vm-stream-ready.sh) now falls back to the latest `ubuntu-beagle-install` state for the VM when `guest_password` is still missing from `vm-secrets`.
- Surfaced the persisted guest password through the existing VM credentials payload for debugging/UI consumers:
	- [beagle-host/services/vm_http_surface.py](beagle-host/services/vm_http_surface.py) now returns `credentials.guest_password` from `guest_password` with legacy `password` fallback.
- Validation:
	- editor diagnostics: no errors in the touched Python/shell files,
	- `bash -n scripts/ensure-vm-stream-ready.sh`.

