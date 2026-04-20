# Next Steps

## Immediate (2026-04-20 follow-up)

0. **Complete full in-VM beagleserver installation after ISO boot recreate**:
	- VM `beagleserver` has been recreated and is running from rebuilt server-installer ISO,
	- complete installer flow inside VM (disk wipe + host config) and verify post-install disk boot.

0. **Stabilize local server-installer harness against KVM availability variance**:
	- local run encountered `failed to initialize kvm: Permission denied`,
	- define a deterministic fallback strategy (`--virt-type qemu` or explicit preflight) in smoke/reinstall workflow to avoid false negatives.

0. **Re-validate installer endpoint behavior on fresh host install**:
	- after full install from the rebuilt ISO, verify `installer.sh` / `live-usb.sh` return `200` without manual file copies,
	- this confirms the `install-beagle-host.sh` reproducibility fix is effective end-to-end.

## Immediate (release publication follow-up)

0. **Push `6.6.9` repo changes to GitHub and attach release assets**:
	- local/public artifact publication to `beagle-os.com` is complete and verified,
	- running Hetzner host `beagle-server` is updated to `6.6.9`,
	- remaining blocker is GitHub-side release publication from this workspace because local `gh`/git credentials are not available,
	- next authenticated GitHub step must push the code changes and upload the already-built `6.6.9` release assets.

0. **Keep `6.6.9` artifact verification attached to handoff**:
	- public installimage SHA256: `3d0a0623585265e9d690f9bcf7d9a1c7baa0aa0f85cbfa0544ef967f2fb7c34d`,
	- public source tarball SHA256 is recorded in `SHA256SUMS` because the source tarball is regenerated when handoff docs change,
	- target host `/opt/beagle/dist/beagle-downloads-status.json` reports `version: 6.6.9`.

## Immediate (docs/process consistency)

0. **Keep the shortened local operator policy stable**:
	- Treat `AGENTS.md` as compact policy only.
	- Move future roadmap/detail architecture edits into `docs/refactor/*`, not back into `AGENTS.md`.
	- If a new rule is truly permanent, add it concisely; if it is status, planning, or migration detail, document it elsewhere.

## Immediate (security/process hygiene)

0. **Commit and push the operator-file de-tracking/release-scrub changes before the next shared sync**:
	- Keep `AGENTS.md` and `CLAUDE.md` local-only and out of Git tracking.
	- Verify the next commit removes both files from the shared repo state on GitHub.
	- Confirm future local edits stay ignored by Git and excluded from source/release/installimage bundles.

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

0. **Validate fresh-install reproducibility of the XFCE/noVNC fix**:
	- Boot a host from the freshly rebuilt server installer ISO and complete a clean Beagle host install.
	- Recreate a fresh ubuntu desktop VM from the provisioning API and verify firstboot no longer stalls at tty-only state.
	- Confirm `beagle-x11vnc.service` is present in the guest, reaches `active`, and listens on guest port `5901` without any manual edits.
	- Confirm noVNC resolves to guest `x11vnc` when available and shows the real XFCE desktop instead of the VGA tty framebuffer.
	- Confirm Sunshine service and API port are reachable after completion.

0. **Deploy full 6.6.9 runtime code on host before final VM lifecycle acceptance**:
	- `beagle-server` already runs `/opt/beagle/VERSION=6.6.9`.
	- Re-run the same VM lifecycle checks after the full `6.6.9` code deploy to avoid validating against mixed runtime state.

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
