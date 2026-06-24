# Projectleader State

Last updated: 2026-06-24

## Role

The active agent acts as project lead for Beagle OS. The job is not only to fix
the immediate symptom, but to keep release quality, live validation and the
LastHope/Diamond gates moving forward.

## Current Direction

- Beagle OS is a standalone KVM/libvirt virtualization platform.
- Proxmox is being removed; new provider coupling is forbidden.
- Live validation targets are `srv1.beagle-os.com` first and `srv2.beagle-os.com`
  when a second host is needed.
- User expectation is code-first: fix in repo, validate on live host, then give a
  short operational summary.

## Recent Runtime And Release Memory

- `v8.3.9` is published but contains a VM provisioning regression for Ubuntu
  autoinstall media permissions.
- Fix commit on `main`: `f05e4b7 Fix Ubuntu autoinstall media permissions`.
- `f05e4b7` fixes:
  - writable extracted autoinstall `grub.cfg`;
  - libvirt-readable ISO/kernel/initrd/seed assets;
  - idempotent deletion of skeleton VMs;
  - cleanup for seed ISOs, seed dirs and VM secret locks.
- Local verification for that fix passed:
  `python3 -m pytest tests/unit/test_runtime_cleanup.py tests/unit/test_ubuntu_beagle_autoinstall_iso.py tests/unit/test_beagle_host_provider_contract_extensions.py tests/unit/test_vm_api_regressions.py -q`
  with `25 passed`.
- `srv1` was updated to rolling `f05e4b7` and validated:
  - `beagle-control-plane`, `nginx`, `libvirtd` active;
  - `systemctl --failed` empty;
  - `/opt/beagle/scripts/check-beagle-host.sh` passed;
  - VM create smoke returned HTTP 201, libvirt domain reached running, delete
    returned HTTP 200, cleanup left no domains/seed ISOs/provider VMs.
- The already released `v8.3.9` server image is still broken for fresh installs
  until a new release is built from `f05e4b7` or newer.

## Release Process Memory

- The user asked for `8.3.9.1`, then interrupted and changed the requirement to a
  release versioning model with alpha/beta/rc instead of every build becoming a
  stable release.
- Existing scripts currently primarily assume stable `x.y.z` release versions.
- The next release-system change should support SemVer prereleases such as
  `8.3.10-alpha.1`, `8.3.10-beta.1`, and `8.3.10-rc.1`.
- Prereleases must not become GitHub `latest` or overwrite public stable
  artifacts on `beagle-os.com`.
- Browser extension metadata cannot directly use arbitrary prerelease strings as
  manifest `version`; keep a compatible numeric `version` and put the full
  product version in `version_name`.

## Active Risks

- Fresh-install confidence is currently below the required R1 gate because the
  stable published image is known-bad.
- Release workflow changes can accidentally promote prerelease artifacts to the
  public stable mirror; guard this explicitly.
- Live hotfixes on `srv1` must never remain only on the host.
- Heavy artifact builds on live hosts can overload the machine; stop unintended
  refresh jobs before starting new release work.
- Local thinclient `192.168.178.30` currently requires a physical power-cycle or
  another way to restart the device: it pings, WireGuard handshakes through
  `srv1` stay fresh, and TCP/22 is open, but sshd no longer sends a banner.
  NetBridge/47100 is not reachable.
- A corrected local thinclient payload exists, but the Streaming Gate is still
  open until the device boots `filesystem.squashfs=668fed9d...` without
  hotpatching and reaches a working VM desktop stream.

## Operator Notes

- Do not record passwords or tokens here.
- If a password is needed for `srv1`, load it from the local operator file
  specified by the user instead of printing it.
- `AGENTS.md` is local policy and must not be committed.

## Runtime Validation 2026-06-23

- Local thinclient evidence:
  - Device `192.168.178.30`, user `thinclient`, live runtime boot.
  - Current installed/runtime version reported by update status: `8.3.17`.
  - Public/update feed seen on device advertises `latest_version=8.3.18`.
- Root causes found:
  - BeagleStream was ready but blocked in `beagle-stream-client.register-wait`
    for 30 attempts before launching.
  - Startup indicator browser output was discarded, so UI failures were silent.
  - Runtime heartbeat only checked `beagle-stream-client`, not the actual
    `beagle-stream stream` process.
  - Live-USB update scan treated RAM-backed cache deferral as a failed systemd
    unit.
- Hotfix validation on the device after copying repo scripts:
  - `ready` proceeded to `register-wait-skip` and then stream exec.
  - Chromium startup indicator process was active and logged to
    `beagle-stream-client-startup-ui.log`.
  - `beagle-stream stream 192.168.123.114:50000 Desktop ...` established the
    VM desktop stream and received video/audio packets.
  - `beagle-runtime-heartbeat` reported `beagle-stream-client=1`.
  - `beagle-update-client scan --auto-apply-if-idle` exited 0 with
    `state=deferred`; `systemctl --failed` was empty after reset.
- No-hotpatch Slot-B attempt:
  - First rebuilt Slot `b` booted without copying scripts after boot.
  - Booted medium showed `/run/live/medium/live/current -> b` and the expected
    hotfix markers in the rootfs.
  - Heartbeat/update-scan stayed healthy, but the fresh BeagleStream client had
    no local server certificate (`srvcert`) and hit SSL/app lookup failures.
  - Repo now requires local host config readiness when `PairStatus=1` and forces
    the stream repair loop on live app/TLS errors.
  - A later local 8.3.18 Slot-B boot reached Xorg/Openbox/startup UI with no
    failed units but hung in Pairing step 6 because no local BeagleStream client
    config/certificate existed before manager token exchange.
  - Repo now bootstraps local BeagleStream QSettings credentials before
    register/pair/stream and treats manager `pairing_mode=token` as accepted
    without running the legacy PIN follow-up.
  - Corrected local payload:
    `.tmp-thinclient-fix/20260623/pve-thin-client-usb-payload-v8.3.18-bootstreamfix-20260623.tar.gz`.
    Payload SHA256: `18bb7bfc6c2bb350c01f8fd181f212bf573e546156c5fb78e23975c35001c94c`.
    Live rootfs SHA256: `668fed9d3def1ae57360d4f12b1a16523143caf0eaccd113bd78a8497506776e`.
  - Local verification after the credential/token fix:
    `120 passed` for the focused unit/integration suite covering payload repair,
    pairing runtime, launcher runtime, heartbeat/update deferral and endpoint
    boot-to-stream tests; `git diff --check` and shell syntax checks are clean.

## Runtime Validation 2026-06-24 Thinclient Admin

- VM100 on `srv1` was used as the live desktop VM for the NetBridge tray/admin
  path.
- The Beagle Thinclient Verwaltung was rebuilt as the full Thinclient management
  center launched from `beagle-netbridge`:
  - modern dashboard header, status pills, overview cards and quick actions;
  - clear tabs for updates, stream, services, USB/AV, devices, network and
    diagnostics;
  - overview Live-Details now use explicit `Bereich | Status | Details`
    columns;
  - stream settings now support presets and editable custom profile values.
- Root cause for empty data in the admin view was the tray backend control
  timeout: the full thinclient `status` response can exceed the old 6 second
  generic timeout. The status/action/long-action paths now use dedicated
  configurable timeouts.
- VM100 hot validation:
  - current admin and tray files were deployed through the QEMU guest agent;
  - `/usr/local/bin/beagle-thinclient-admin --selftest` returned
    `agent_status: ok host=10.88.1.1`;
  - `/usr/local/bin/beagle-netbridge-tray --selftest` returned
    `agent_host: 10.88.1.1` and `stream_profile: custom`;
  - VM100 offscreen screenshot was generated as `.tmp-thinclient-admin-smoke.png`
    and showed visible overview statuses.
- Local direct check for `192.168.178.30:47100` returned connection refused;
  the active production path from VM100 through WireGuard to `10.88.1.1:47100`
  is working.
- GitHub already had published `v8.3.19`; the next stable release for this
  admin fix is prepared as `8.3.20`.
- Release run `28087083296` for `2f7f73d5` was cancelled on user request before
  shipping because per-tab screenshots showed the first admin UI pass was still
  too empty and table-like.
- Follow-up VM100 screenshot pass captured all tabs under `.tmp-thinclient-tabs/`.
  The admin now has visible status cards on the operational tabs, unclipped
  update actions, readable USB/AV rows, inline LAN-device creation, explicit
  empty states and row-driven service actions. No new release was started after
  this follow-up.
