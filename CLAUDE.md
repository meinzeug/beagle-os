# Beagle OS

Proxmox-native endpoint OS and management stack for streaming virtual desktops via Moonlight/Sunshine.

## Architecture

- **proxmox-host/**: Control plane (Python API server on port 9088) + systemd services
- **proxmox-ui/**: JavaScript injection into Proxmox VE UI
- **extension/**: Browser extension for Chrome/Firefox
- **website/**: Management dashboard served on HTTPS/443 from the Proxmox host
- **thin-client-assistant/**: Endpoint runtime, installer, USB writer
- **beagle-os/**: Dedicated endpoint OS image builder (Debian Bookworm + custom kernel)
- **scripts/**: Installation, build, packaging, and release scripts

## Key files

- `proxmox-host/bin/beagle-control-plane.py` - Main API server (~3000 lines Python)
- `proxmox-ui/beagle-ui.js` - Proxmox UI integration (~1400 lines JS)
- `website/app.js` - Management dashboard (~800 lines vanilla JS)
- `scripts/build-beagle-os.sh` - OS image builder

## Conventions

- Shell scripts use `set -euo pipefail`
- No npm/pip external dependencies - vanilla JS frontend, stdlib Python backend
- All UI text in English
- German README is intentional (target market)

## Build

- `scripts/build-beagle-os.sh` builds the endpoint OS image
- `scripts/build-thin-client-installer.sh` builds the bootable ISO
- `scripts/package.sh` creates release artifacts
- `scripts/create-github-release.sh` publishes to GitHub

## License

Beagle OS Source Available License - free for personal and non-commercial use, commercial use requires separate written permission or licensing from Dennis Wicht / meinzeug.
