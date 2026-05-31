# Projectleader Todo

Last updated: 2026-05-31

## Immediate

- [ ] Implement release channels for stable/prerelease:
  - accept stable `x.y.z`;
  - accept prerelease `x.y.z-alpha.N`, `x.y.z-beta.N`, `x.y.z-rc.N`;
  - reject invalid four-part stable versions like `8.3.9.1` unless a deliberate
    compatibility rule is added;
  - expose a release-class output from `scripts/resolve-release-version.sh`.
- [ ] Update release workflow so prereleases:
  - are created with `gh release create --prerelease --latest=false`;
  - do not run public stable artifact deployment;
  - do not rewrite stable public `latest` files or `beagle-downloads-status.json`;
  - still upload artifacts to the GitHub prerelease for testing.
- [ ] Update `scripts/sync-release-version.py` so prerelease versions work with:
  - root `VERSION`;
  - WebUI cache-busting;
  - Kiosk `package.json` and `package-lock.json`;
  - browser extension manifest using numeric `version` plus full `version_name`.
- [ ] Add unit/regression tests for stable vs alpha/beta/rc version resolution and
  release workflow gating.
- [ ] After release-system fix, build a new release from `f05e4b7` or newer and
  validate it with a clean `srv1` installimage run.

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

- [ ] After the VM is installed and stable, verify BeagleStream server/client path.
- [ ] Confirm streaming from a fresh thin-client payload without manual hotpatches.
- [ ] Check WireGuard-required path, stream health events and absence of secrets in
  logs.

## Documentation Hygiene

- [ ] Keep `projectleader/state.md` current after every meaningful release or live
  validation step.
- [ ] Keep `projectleader/todo.md` as the next-run queue.
- [ ] Mirror completed gate evidence into `docs/lasthope/`,
  `docs/checklists/05-release-operations.md`, and `docs/refactor/05-progress.md`
  when a gate actually passes.
