# Hetzner Installimage Deployment Guide

## Overview

This document describes how to deploy Beagle OS Server on Hetzner dedicated servers using the custom installimage tarball.

## Artifacts

**Version**: 6.6.9  
**Tarball**: `Debian-1201-bookworm-amd64-beagle-server.tar.gz`  
**SHA256**: `3d0a0623585265e9d690f9bcf7d9a1c7baa0aa0f85cbfa0544ef967f2fb7c34d`  
**Size**: 512 MB  
**Source**: `/home/dennis/beagle-os/dist/` (local repo)  
**Status**: ✓ Validated and ready for deployment

## Validation Checklist

The tarball has been verified to include:

- ✓ All bootstrap scripts for first-boot automation
- ✓ Systemd service units for SSH hostkey and Beagle bootstrap
- ✓ Nested Beagle source archive with full installation flow
- ✓ No operator files (AGENTS.md, CLAUDE.md removed via builder fix)
- ✓ Clean filesystem without build artifacts
- ✓ Proper extraction and integrity confirmed

## Deployment Steps

### 1. Upload Tarball to Hosting

The tarball must be accessible via HTTP from Hetzner Rescue environment:

```bash
# From your workstation (repo owner)
# Requires: BEAGLE_PUBLIC_SSH_TARGET and BEAGLE_HOSTED_DOWNLOADS_BASE_URL env vars

cd /home/dennis/beagle-os
scripts/publish-hosted-artifacts-to-public.sh
```

This script:
1. Validates SHA256 checksums
2. Uploads tarball to public Hetzner host
3. Makes it accessible at configured public URL

### 2. Boot Hetzner Server into Rescue

1. Order or provision Hetzner dedicated server
2. Reboot into Rescue System (via Hetzner Console)
3. Note the rescue system password

### 3. Run Hetzner Installimage

Execute in Rescue environment:

```bash
#!/bin/bash
export ARCH=amd64
export HOSTNAME=beagle-server
export FORCE_GRUB_INSTALL=1
export IMAGE_PATH=https://beagle-os.com/beagle-updates/Debian-1201-bookworm-amd64-beagle-server.tar.gz

curl -fsSL https://stable.example.com/custom/installimage | bash
```

Or alternatively:

```bash
wget https://stable.example.com/custom/installimage -O /tmp/installimage
chmod +x /tmp/installimage

IMAGE_PATH=https://beagle-os.com/beagle-updates/Debian-1201-bookworm-amd64-beagle-server.tar.gz \
HOSTNAME=beagle-server \
ARCH=amd64 \
/tmp/installimage
```

### 4. Wait for First-Boot Bootstrap

After installation and reboot:

- Beagle installimage-bootstrap service runs automatically
- Unpacks bundled Beagle sources
- Runs full Beagle host installation flow
- Regenerates SSH host keys (rescue-specific)
- Outputs credentials to `/root/beagle-firstboot-credentials.txt`

**Expected duration**: 5-15 minutes depending on network

### 5. Verify Installation

Once first-boot completes:

```bash
# SSH to the server (using rescue password initially)
ssh root@<server-ip>

# Check bootstrap logs
tail -100 /var/log/beagle-installimage-bootstrap.log

# Verify Beagle services
systemctl status beagle-control-plane
curl http://localhost:9088/api/v1/status

# Retrieve generated credentials
cat /root/beagle-firstboot-credentials.txt
```

### 6. Create Operator User

```bash
ssh root@<server-ip>

# Create beagle operator user
adduser beagle
usermod -aG sudo beagle

# Copy SSH keys for password-less access
mkdir -p /home/beagle/.ssh
cp /root/.ssh/authorized_keys /home/beagle/.ssh/
chown -R beagle:beagle /home/beagle/.ssh
chmod 700 /home/beagle/.ssh
chmod 600 /home/beagle/.ssh/authorized_keys
```

## KnownIssues

- **First-boot takes time**: The bootstrap process unpacks ~500MB tarball and runs full apt installation. Do not terminate the process.
- **SSH hostkeys regenerated**: Keys are different from build time (by design). Clients may need `known_hosts` cleared.
- **DHCP on first boot**: Server obtains IP via DHCP on first boot, then may switch to static if configured in host.env.

## Troubleshooting

### Bootstrap didn't complete

Check logs:
```bash
tail -200 /var/log/beagle-installimage-bootstrap.log
journalctl -u beagle-installimage-bootstrap.service -n 100
```

Manual rerun:
```bash
/usr/local/bin/beagle-installimage-bootstrap
```

### Beagle services not running

```bash
systemctl start beagle-control-plane
systemctl status beagle-*
```

### Network issues

```bash
# Check DHCP status
systemctl status systemd-networkd
ip addr show
ip route show

# Try static configuration in /etc/network/interfaces if needed
```

## Builder and Source

All builder scripts are open-source and available in the Beagle OS repository:

- **Builder**: `scripts/build-server-installimage.sh`
- **Bootstrap scripts**: `server-installer/installimage/`
- **Installation flow**: `scripts/install-beagle-host.sh` and dependencies

Refer to the main Beagle OS repository for latest changes and updates.

## References

- [Hetzner Installimage Documentation](https://docs.hetzner.cloud/en/dedicated-server/linux-images/custom-images#use-a-custom-image-partition-table)
- [Beagle OS Repository](https://github.com/meinzeug/beagle-os)
- [Build Documentation](../beagle-os-build.md)
