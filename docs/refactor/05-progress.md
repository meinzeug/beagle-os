# Progress (2026-04-18)

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
- New blocker discovered after success dialog during reboot validation:
	- Domain currently attempts CD boot/no bootable device after media eject, so post-install disk boot validation is not complete yet.
	- This is now tracked as the next immediate runtime blocker; installer-stage libvirt/chroot regression itself is resolved.

- Extended Beagle Web Console endpoint detail actions for future thinclient creation flows:
	- Added dedicated Live-USB script visibility and download action in [website/app.js](website/app.js) (`/vms/{vmid}/live-usb.sh` wiring).
	- This closes a Web-UI gap where backend live-USB support existed but was not exposed in the Beagle Web Console action set.

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

- Added reproducible host firewall reconciliation improvements in [scripts/reconcile-public-streams.sh](scripts/reconcile-public-streams.sh):
	- Expanded forwarded Sunshine UDP set to include `base+12`, `base+14`, `base+15` (not only `base+9/+10/+11/+13`).
	- Added idempotent synchronization of allow-rules with comment marker `beagle-stream-allow` into `inet filter forward` when that chain exists with restrictive policy.

