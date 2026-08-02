# Projectleader Todo

Last updated: 2026-08-02

## Immediate

- [ ] Renew the expired TLS certificate for `beagle-os.com` on the external
  public webhost (`212.227.63.45`) and verify the public download status,
  thinclient payload and installer ISO without a TLS bypass.
- [ ] Schedule maintenance for `srv1`: inspect SATA power/data paths and
  controller logs, replace the two high-hour HGST RAID1 members in a controlled
  sequence, and verify RAID rebuild plus extended SMART tests after each change.

## R1 Clean Install Gate

- [ ] Publish a fixed server installimage that includes the autoinstall media
  permission fix.
- [ ] Reinstall `srv1` from the published fixed installimage, not from a manual
  hotfix.
- [ ] Verify after reboot:
  - bootstrap done marker exists;
  - `beagle-control-plane`, `nginx`, `libvirtd` active;
  - no failed systemd units;
  - `/opt/beagle/scripts/check-beagle-host.sh` passes.
- [ ] Create a VM from WebUI/API and observe:
  - provisioning request accepted;
  - libvirt domain starts;
  - firstboot/provisioning completes;
  - VM reaches desktop-ready state.
- [ ] Delete and recreate VM without stale state.

## Streaming Gate

- [x] Reproduce and hotfix local thinclient boot-to-stream delay on `192.168.178.30`.
- [x] Verify BeagleStream server/client path on the local thinclient after hotfix.
- [x] Verify first local no-hotpatch Slot-B boot contains the hotfix and keeps heartbeat/update-scan healthy.
- [x] Fix fresh-boot PairStatus/TLS readiness regression found during Slot-B boot.
- [x] Fix fresh-boot missing BeagleStream client credentials and Manager token-mode pairing regression.
- [x] Build a local fixed 8.3.18 thin-client payload for hardware recovery (`filesystem.squashfs=668fed9d...`, payload SHA256 `18bb7bfc...`).
- [x] Repair VM100 DHCP/X11/KWallet failures and validate automatic network and
  stream recovery on `srv1`.
- [x] Fix the thinclient audio watcher lock inheritance and validate
  WirePlumber, RTSP, 1920x1080 video and stereo audio on hardware.
- [x] Refresh VM-scoped USB tunnel configuration through device sync and support
  legacy thinclient installer identities.
- [x] Validate the USB/IP reverse listener and VM100 microphone bridge with an
  active PipeWire recording (`dropped=0`, `reconnects=0`).
- [x] Make telemetry JSONL recovery tolerant and restore recurring device sync
  to HTTP 200.
- [ ] Build and publish a fresh thin-client payload containing the boot,
  network/capture retry and audio-lock fixes.
- [ ] Install and boot that fresh payload on the local thinclient, then confirm
  streaming without manual hotpatches.
- [ ] Check WireGuard-required path, stream health events and absence of secrets in
  logs.

## Documentation Hygiene

- [ ] Keep `projectleader/state.md` current after every meaningful release or live
  validation step.
- [ ] Keep `projectleader/todo.md` as the next-run queue.
- [ ] Mirror completed gate evidence into `docs/lasthope/`,
  `docs/checklists/05-release-operations.md`, and `docs/refactor/05-progress.md`
  when a gate actually passes.
