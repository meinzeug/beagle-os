# Projectleader State

Last updated: 2026-05-31

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

## Operator Notes

- Do not record passwords or tokens here.
- If a password is needed for `srv1`, load it from the local operator file
  specified by the user instead of printing it.
- `AGENTS.md` is local policy and must not be committed.
