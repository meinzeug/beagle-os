# AGENTS.md

This repository is deployed across two linked servers. Treat them as one release surface and keep them in sync on every Beagle release, installer change, download-path change, or control-plane change.

## Servers

- Proxmox and control plane: `srv.thinover.net`
  - Preferred operator alias: `ssh thinovernet`
  - Administrative access is commonly done with `ssh root@thinover.net`
  - The local SSH config alias `thinovernet` maps to user `thinovernet` on `srv.thinover.net`
- Public website and public update artifacts: `srv1.meinzeug.cloud`
  - Preferred operator alias: `ssh meinzeug`
  - This host serves `beagle-os.com`

These two hosts belong together:

- `srv.thinover.net` serves the Proxmox UI integration, Beagle control plane, VM-specific installer launchers, and host-local downloads.
- `beagle-os.com` serves the public Beagle update artifacts.
- VM-specific installers generated on `srv.thinover.net` must point to the correct public artifacts on `beagle-os.com` unless there is an explicit reason not to.

## Required Release Workflow

Whenever you change versions, installer scripts, artifact names, artifact URLs, update feeds, or deployment logic, update both hosts in the same work session.

1. Update and verify the repo locally.
2. Deploy code and service changes to `srv.thinover.net`.
3. Refresh or repackage host artifacts on `srv.thinover.net`.
4. Publish the public update artifacts to `srv1.meinzeug.cloud`.
5. Verify both sides after deployment.

## Minimum Verification Checklist

- `ssh thinovernet` works for interactive SSH and is not broken by SSHD drop-ins.
- `ssh root@thinover.net` still works for administrative tasks.
- `ssh meinzeug` works.
- `https://srv.thinover.net:8443/beagle-api/api/v1/vms/<vmid>/installer.sh` returns `200`.
- The rendered VM installer points to the intended public artifact URLs.
- `https://beagle-os.com/beagle-updates/beagle-downloads-status.json` returns `200`.
- `https://beagle-os.com/beagle-updates/pve-thin-client-usb-payload-latest.tar.gz` returns `200`.
- `https://beagle-os.com/beagle-updates/pve-thin-client-usb-bootstrap-latest.tar.gz` returns `200`.
- `https://beagle-os.com/beagle-updates/beagle-os-installer-amd64.iso` returns `200` when the hosted installer expects a public ISO.

## Important Notes

- The public artifact target path is `/opt/beagle-os-saas/src/public/beagle-updates/` on `srv1.meinzeug.cloud`.
- That path resolves to `/var/www/vhosts/beagle-os.com/httpdocs/beagle-updates`.
- When deploying individual files to `srv.thinover.net`, preserve repository-relative paths under `/opt/beagle/`.
  Use `rsync -avR <repo-path> root@thinovernet:/opt/beagle/` instead of copying files flat into `/opt/beagle/`, because the install scripts read from paths like `/opt/beagle/proxmox-host/...` and `/opt/beagle/proxmox-ui/...`.
- Do not update only one side. If the Proxmox host and `beagle-os.com` drift apart, hosted installers break in subtle ways.
- If `scripts/install-proxmox-host-services.sh` changes SSH behavior for user `thinovernet`, verify `PermitTTY yes` and do not regress the `ssh thinovernet` operator workflow.
