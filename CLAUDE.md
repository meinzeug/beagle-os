# Beagle OS

Open-source host tooling, endpoint runtime, gaming kiosk, and installer stack with Proxmox as the current first provider.

## Architecture

- **beagle-host/**: Control plane (Python API server on port 9088) plus systemd services
- **proxmox-ui/**: JavaScript injection into the Proxmox VE UI
- **core/**: Provider-neutral contracts and shared services
- **providers/**: Concrete provider implementations, currently Proxmox
- **extension/**: Browser extension for Chrome/Firefox
- **thin-client-assistant/**: Endpoint runtime, installer, and USB writers
- **beagle-os/**: Dedicated endpoint OS image builder
- **beagle-kiosk/**: Public Electron gaming kiosk source tree
- **server-installer/**: Live-build definition for the Beagle + Proxmox host installer ISO
- **scripts/**: Installation, packaging, publishing, and release scripts

## Key files

- `beagle-host/bin/beagle-control-plane.py` - Main API server
- `proxmox-ui/beagle-ui.js` - Proxmox UI integration entrypoint
- `beagle-kiosk/main.js` - Gaming kiosk main process
- `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer` - Interactive server installer

## Conventions

- Shell scripts use `set -euo pipefail`
- Frontend code stays dependency-light
- Public release artifacts are published via GitHub Releases and `beagle-os.com`
- Heavy build work must run on a dedicated release build host, not on the local control workstation

## Build

- `scripts/build-beagle-os.sh` builds the endpoint OS image
- `scripts/build-thin-client-installer.sh` builds the endpoint installer ISO
- `scripts/build-server-installer.sh` builds the Proxmox host installer ISO
- `scripts/package.sh` creates release artifacts
- `scripts/create-github-release.sh` publishes a GitHub release

## License

The repository is MIT licensed.
