# Next Steps

## Immediate (Hetzner installimage path - CORRECTED)

0. **Publish the corrected installimage tarball to both GitHub and beagle-os.com** (NEXT):
	- push the repo changes from commit `497eee2` to main branch so the builder is available in public repo,
	- upload the tarball as a release/public artifact beside the existing installer ISOs,
	- verify direct HTTP reachability plus checksum/status-json coverage for the tarball on `beagle-os.com`,
	- update public release metadata to include the new tarball with its validated checksum.

0. **Install the public tarball on the new Hetzner server via Rescue + installimage**:
	- use Rescue System with a custom-image `IMAGE_PATH` pointing at the published tarball,
	- let installimage set root password from the active Rescue password,
	- boot the installed system and confirm Beagle first-boot bootstrap completes successfully,
	- create the requested operator user `beagle` after the target is reachable.

## Immediate (docs/process consistency)

0. **Keep the shortened local operator policy stable**:
	- Treat `AGENTS.md` as compact policy only.
	- Move future roadmap/detail architecture edits into `docs/refactor/*`, not back into `AGENTS.md`.
	- If a new rule is truly permanent, add it concisely; if it is status, planning, or migration detail, document it elsewhere.

## Immediate (security/process hygiene)

0. **Commit and push the operator-file de-tracking change before the next shared sync**:
	- Keep `AGENTS.md` and `CLAUDE.md` local-only and out of Git tracking.
	- Verify the next commit removes both files from the shared repo state on GitHub.
	- Confirm future local edits stay ignored by Git.

0. **Run a targeted secret-leak sweep now that local operator docs are isolated**:
	- Search the repo for plaintext passwords, tokens, SSH snippets and operator-only notes that should not be versioned.
	- Document every finding in `docs/refactor/11-security-findings.md`.
	- Patch or remove any safe-to-fix exposures in the same run.

## Immediate (blocking on environmental readiness, not code)

0. **Deploy and validate the firstboot callback retry guard fix (VM163 blocker)**:
	- Deploy updated [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl) to `/opt/beagle/...` on beagleserver.
	- Recreate one fresh ubuntu desktop VM and verify the firstboot systemd unit remains eligible until `/var/lib/beagle/ubuntu-firstboot-callback.done` exists.
	- Simulate callback delay/failure once and confirm service retries and eventually posts `/complete?restart=0`.
	- Confirm provisioning transitions out of `installing` and VM performs the expected post-completion reboot handoff.

0. **Unstick currently affected VM163 runtime state**:
	- Trigger callback endpoint `POST /api/v1/public/ubuntu-install/<token>/complete?restart=0` using VM163 token.
	- Verify VM163 provisioning state becomes `completed/complete` and rerun stream-ready checks.

0. **Finish live validation for the freshly recreated VM161**:
	- Monitor VM `161` until provisioning transitions from `installing/autoinstall` to `firstboot`/`complete`.
	- Continue periodic installer screenshot checks to ensure progression beyond `stage-curthooks/.../installing-kernel` and detect any new deterministic stall point.
	- Confirm VM XML cleanup after autoinstall transition (installer media + kernel args removed, disk boot only).
	- Verify inside guest that `beagle-ubuntu-firstboot.service` exists and executes automatically on first boot.
	- Verify `lightdm`, desktop session and `qemu-guest-agent` become active.

0. **Deploy and validate repo-first firstboot hardening (new)**:
	- Deploy updated template [beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl](beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl) to running beagleserver host stack.
	- Recreate a fresh ubuntu desktop VM from the provisioning API and verify firstboot no longer stalls at tty-only state.
	- Confirm `beagle-ubuntu-firstboot.service` reaches success, `lightdm` is installed/active, and callback transitions state out of `installing/firstboot`.
	- Confirm Sunshine service and API port are reachable after completion.

0. **Deploy full 6.6.8 runtime code on host before final acceptance**:
	- Sync all relevant changed host files (not only template) from repo `main` to `/opt/beagle/...`.
	- Restart `beagle-control-plane` and verify runtime version/config behavior reflects 6.6.8 expectations.
	- Re-run the same VM lifecycle checks after full code deploy to avoid validating against mixed runtime state.

0. **Validate new bridge/interface consistency fix on fresh VM run**:
	- Ensure runtime env on host contains `BEAGLE_PUBLIC_STREAM_LAN_IF` matching libvirt `beagle` network bridge (expected `virbr10`).
	- Trigger `/opt/beagle/scripts/reconcile-public-streams.sh` and confirm generated `beagle-stream-allow` rules use detected bridge iface, not legacy `vmbr1`.
	- Create one fresh ubuntu desktop VM and verify firstboot + callback complete without any manual host nft forward patching.

1. **Guest IP and qemu-agent availability** (in progress on beagleserver):
	- VMs 100, 101, 102 are running but have not yet obtained DHCP IP addresses.
	- Root cause: VMs are either still in autoinstall phase (VM102) or waiting for qemu-guest-agent to initialize (VMs 100, 101).
	- **Next agent should**: Wait ~10 min, then retry `virsh guestinfo beagle-{100,101,102} --types network` to get IP addresses.
	- Once IPs are available, re-run `ensure-vm-stream-ready.sh --vmid 102 --node beagle-0` to validate full stream-ready workflow (secret persistence + Sunshine install + ready state).
	- Expected outcome: `installer_guest_ip` populated, `sunshine_status: {binary: 1, service: 1, process: 1}`, state phase transitions to "ready".

## High priority (secret persistence validated, now prove E2E)

1. Execute a full no-manual reproducibility run for stream prep on fresh VMs (once IPs available):
	- run installer-prep/stream-ready flow without console or ad-hoc SSH intervention,
	- confirm state payload includes `installer_guest_ip` and `installer_guest_password_available=true`,
	- confirm the guest password is sourced from persisted `vm-secrets` on new VMs and only uses the `ubuntu-beagle-install` fallback for legacy runs,
	- confirm Sunshine install reaches `ready` only through repo-managed scripts.
2. Confirm guest runtime readiness after fallback completion:
	- verify Sunshine port/API path reaches a stable state,
	- verify qemu-guest-agent comes up (`org.qemu.guest_agent.0` no longer disconnected),
	- verify no hidden firstboot service crash loop remains.
3. Keep callback path as primary signal for fresh runs and re-test on a clean recreate:
	- ensure generated seed contains both late-command callback attempts (`sh -c ...` and `curtin in-target ...`),
	- confirm callbacks (`prepare-firstboot`, `complete` or `failed`) appear in host ingress logs when guest networking behaves.
4. Fix immediate post-install disk boot on `beagleserver` after successful installer completion:
	- verify effective libvirt boot-order/device mapping for `vda` vs empty `sda` cdrom,
	- confirm GRUB/boot target on installed disk,
	- reach first boot login on installed host without live-ISO runtime artifacts.
5. Re-run clean reinstall once with the now-proven patched ISO path and confirm no residual transient state in `/var/log/beagle-server-installer.log`.
6. Continue the requested realistic E2E product flow from installed host state:
	- open Beagle Web UI,
	- create Beagle Ubuntu/XFCE/Sunshine desktop VM (re-validate UI no longer reports `Request timeout` on provisioning create),
	- download Live-USB installer script via Web UI,
	- reinstall `beaglethinclient`,
	- verify first-time Moonlight -> Sunshine auto-connect and active stream.
7. Persist and verify stream firewall reconciliation on installed beagleserver host:
	- run `/opt/beagle/scripts/reconcile-public-streams.sh` on boot/service restart,
	- confirm `inet filter forward` contains `beagle-stream-allow` rules for RTSP + UDP stream ports.
8. Verify the guest `beagle-sunshine-healthcheck.timer` path on VM 101:
	- timer active after reboot,
	- forced crash (`pkill sunshine`) is recovered automatically,
	- local `/api/apps` check succeeds again without manual intervention.
9. Fix server-installer live smoke DHCP reliability in local libvirt harness (`scripts/test-server-installer-live-smoke.sh`) after the boot-path stabilization.
10. Stabilize standalone stream simulation harness for real-libvirt execution (`scripts/test-standalone-desktop-stream-sim.sh`).
11. Once end-to-end passes, run final docs sync + commit/push:
	- `05-progress.md`,
	- `06-next-steps.md`,
	- `08-todo-global.md`,
	- `09-provider-abstraction.md`.
