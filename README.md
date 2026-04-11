[![Beagle OS splash](docs/assets/beagle_splash.png)](docs/assets/beagle_splash.png)

[![Beagle OS logo](docs/assets/beagle_logo.png)](docs/assets/beagle_logo.png)

# Beagle OS

> **Built to boot. If it still won't boot, the BIOS is being dramatic.**

> **Open-source endpoint OS, gaming kiosk, and host installer with Proxmox as the current first provider.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[Download Latest](https://beagle-os.com/download/)
[![Shell](https://img.shields.io/badge/shell-54%25-green)]()
[![Python](https://img.shields.io/badge/python-24%25-blue)]()

Beagle OS is an MIT-licensed project for three tightly related jobs:

- `Beagle OS Desktop`
  Runs Moonlight on a dedicated endpoint and connects it to a Sunshine-enabled VM.
- `Beagle OS Gaming`
  Runs the Beagle gaming kiosk as the primary shell and launches GeForce NOW from that kiosk.
- `Beagle OS Server Installer`
  Boots a bare server, asks for basic install parameters, installs Debian + Proxmox VE, then installs the Beagle integration on top.

Beagle OS is not a generic broker platform. It is a focused stack for streamed desktops, gaming endpoints, and reproducible host installation. Today the main deployment path is Proxmox-backed, but the architecture is being refactored so Proxmox is a provider implementation rather than the permanent system center.

## What Lives in This Repository

- `beagle-host/`
  Host-side control plane, download publication, and installer rendering.
- `proxmox-ui/`
  Proxmox UI integration and Beagle Fleet controls.
- `core/`
  Provider-neutral contracts and shared services for virtualization and platform behavior.
- `providers/`
  Concrete backend/provider implementations, currently starting with Proxmox.
- `thin-client-assistant/`
  Endpoint runtime, live-build inputs, USB installers, and endpoint installer logic.
- `beagle-kiosk/`
  Open-source Electron source tree for the gaming kiosk.
- `scripts/`
  Build, packaging, publication, deployment, and validation utilities.

## Gaming Kiosk

The gaming kiosk is now part of the public repository.

Key points:

- Source lives in [`beagle-kiosk/`](beagle-kiosk/README.md)
- Built as an Electron AppImage for release distribution
- Supports `Meine Bibliothek` and `Spielekatalog`
- Launches GeForce NOW as a child process
- Uses direct store links without affiliate parameters
- Ships daily and manual catalog refresh support

## Quick Start

### Install Beagle on an Existing Host

```bash
git clone https://github.com/meinzeug/beagle-os.git
cd beagle-os
./scripts/setup-beagle-host.sh
./scripts/check-beagle-host.sh
```

After setup, the current provider host gets:

- the Beagle control plane
- hosted installer and update artifacts
- the Beagle Fleet button in the UI
- per-VM USB installer rendering

### Install a New Host with the Server Installer ISO

1. Download the current server installer ISO from `beagle-os.com`.
2. Boot the target machine from the ISO.
3. Enter the server hostname, Linux username, password, and target disk.
4. The installer installs Debian Bookworm, installs the current host provider stack, downloads Beagle from GitHub, and runs the Beagle host setup.

### Install an Endpoint

You can use:

- the public installer ISO
- the public USB helper scripts
- or the preferred VM-specific USB installer exposed by the Proxmox host

## Architecture

Beagle OS consists of three runtime layers plus a provider layer:

1. `Provider Layer`
   Concrete infrastructure integration, currently Proxmox first.
2. `Beagle OS Endpoint Runtime`
   Dedicated endpoint OS for Moonlight desktop mode and Gaming kiosk mode.
3. `Beagle Control Plane`
   Inventory, VM-aware artifact publication, host services, health, and UI integration.
4. `Beagle Server Installer`
   Bootable installer for new provider-backed Beagle hosts, currently Debian + Proxmox + Beagle.

In practice:

- Proxmox is the current primary operator surface, not the permanent architecture center.
- Sunshine inside the VM is the desktop streaming target.
- Moonlight on the endpoint is the desktop client path.
- The Beagle kiosk is the gaming shell around GeForce NOW.
- Public artifacts on `beagle-os.com` are the canonical release surface.

## Operational Model

Typical Desktop flow today:

1. Install Beagle on Proxmox.
2. Create or prepare a Sunshine-capable VM.
3. Download the VM-specific installer from Proxmox.
4. Write a USB stick.
5. Install the endpoint and boot `Beagle OS Desktop`.

Typical Gaming flow:

1. Install or update the endpoint OS.
2. Boot `Beagle OS Gaming`.
3. The kiosk starts as the primary shell.
4. Launch GeForce NOW from the kiosk.
5. When GFN exits, the kiosk returns.

Typical Host bootstrap flow today:

1. Boot the Beagle server installer ISO.
2. Select the install disk and set hostname/user/password.
3. Let the installer finish Debian + Proxmox + Beagle setup.
4. Log into the new Proxmox host and continue with Beagle Fleet or endpoint rollouts.

## Public Artifacts

The public update surface on `https://beagle-os.com/beagle-updates/` publishes:

- `beagle-downloads-status.json`
- `SHA256SUMS`
- `beagle-os-installer-amd64.iso`
- `beagle-os-server-installer-amd64.iso`
- `pve-thin-client-usb-payload-latest.tar.gz`
- `pve-thin-client-usb-bootstrap-latest.tar.gz`
- USB helper scripts
- kiosk release metadata and kiosk AppImage artifacts

## Build and Release

Heavy builds must run on a dedicated release build host, not on this local workstation.

Common release steps:

```bash
./scripts/validate-project.sh
./scripts/package.sh
./scripts/publish-public-update-artifacts.sh
./scripts/create-github-release.sh
```

## License

This repository is licensed under the [MIT License](LICENSE).
