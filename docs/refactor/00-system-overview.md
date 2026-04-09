# Refactor System Overview

## Purpose

This document captures the current repository structure as of 2026-04-09 and establishes the baseline for the stepwise refactor mandated by `AGENTS.md`.

Beagle OS currently operates as one product family with multiple deployable surfaces:

- Proxmox host control plane and hosted installers
- Proxmox UI integration and browser-side operator workflows
- Thin client installer and runtime for Moonlight/Sunshine
- Gaming kiosk for GeForce NOW and store discovery
- Public artifact publication and release packaging
- Server installer ISO for Debian + Proxmox + Beagle bootstrap

## Top-Level Modules

### `proxmox-host/`

Host-side control plane code, systemd units, and VM provisioning templates.

- Main control plane entrypoint: `proxmox-host/bin/beagle-control-plane.py`
- Current size: about 5900 lines
- Responsibilities:
  - HTTP API
  - inventory and VM state resolution
  - artifact metadata generation
  - installer rendering
  - token issuance and control-plane auth
  - Ubuntu guest provisioning template rendering

### `proxmox-ui/`

Host-installed JavaScript injected into the Proxmox web UI.

- Main file: `proxmox-ui/beagle-ui.js`
- Current size: about 2966 lines
- Responsibilities:
  - detect Proxmox VM context
  - render Beagle UI modal and actions
  - call Beagle control-plane endpoints
  - export endpoint profiles
  - drive USB installer and provisioning actions

### `extension/`

Browser extension that mirrors much of the operator workflow without host-side UI installation.

- Main file: `extension/content.js`
- Current size: about 1059 lines
- Responsibilities overlap strongly with `proxmox-ui/`

### `website/`

Web control surface for Beagle inventory and policy views.

- Main app file: `website/app.js`
- Current size: about 1092 lines
- Uses session token handling in the browser

### `thin-client-assistant/`

Endpoint installer, live-build inputs, runtime shell scripts, USB tooling, and templates.

- Largest files:
  - `thin-client-assistant/usb/pve-thin-client-local-installer.sh` (~2557 lines)
  - `thin-client-assistant/usb/pve-thin-client-usb-installer.sh` (~1396 lines)
  - `thin-client-assistant/usb/pve-thin-client-live-menu.sh` (~1360 lines)
  - `thin-client-assistant/runtime/launch-moonlight.sh` (~1198 lines)
  - `thin-client-assistant/runtime/common.sh` (~881 lines)
- Responsibilities:
  - installer UI and local install flow
  - runtime preparation
  - network setup
  - Moonlight launch and pairing
  - GFN helper launch for gaming mode
  - live-build definitions for bootable media

### `beagle-os/`

Dedicated endpoint OS overlay and package definitions.

- Responsibilities:
  - overlay files for systemd, login, kiosk launch, update scan, reporting
  - package lists and endpoint image build inputs

### `beagle-kiosk/`

Open-source Electron kiosk for Gaming mode.

- Main process: `beagle-kiosk/main.js` (~1133 lines)
- Renderer: `beagle-kiosk/renderer/kiosk.js` (~891 lines)
- Responsibilities:
  - load kiosk config and cached data
  - spawn and monitor GeForce NOW as child process
  - catalog browsing and filtered game launching
  - store-link allowlisting

### `server-installer/`

Live-build based installer ISO for new Beagle servers.

- Main installer runtime: `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
- Responsibilities:
  - prompt for hostname, user, password, target disk
  - install Debian and Proxmox
  - bootstrap Beagle on the new host

### `scripts/`

Repository orchestration scripts for build, packaging, deployment, publishing, and validation.

- Key scripts:
  - `scripts/package.sh`
  - `scripts/build-thin-client-installer.sh`
  - `scripts/build-server-installer.sh`
  - `scripts/build-beagle-os.sh`
  - `scripts/install-proxmox-host.sh`
  - `scripts/install-proxmox-host-services.sh`
  - `scripts/install-proxmox-ui-integration.sh`
  - `scripts/publish-public-update-artifacts.sh`
  - `scripts/validate-project.sh`

## Runtime and Deployment Surfaces

### Surface A: Proxmox host

Runs:

- Beagle control plane
- hosted installer and artifact publishing
- Proxmox UI integration
- host-local refresh services

### Surface B: Public website and public artifacts

Serves:

- public update manifests
- public ISO and USB payload artifacts
- kiosk AppImage and release metadata

### Surface C: Endpoint device

Runs one of two user-facing modes:

- `Beagle OS Desktop` for Moonlight streaming
- `Beagle OS Gaming` for kiosk + GeForce NOW

### Surface D: New server bootstrap ISO

Installs Debian, Proxmox VE, and the Beagle integration on bare metal.

## Build and Release Reality

Build orchestration is currently script-centric rather than pipeline-centric.

- Validation is handled by `scripts/validate-project.sh`
- Packaging is handled by `scripts/package.sh`
- Thin client, server installer, kiosk, and optional Beagle OS image builds are triggered from shell scripts
- Heavy builds are expected to run on `srv.thinover.net`, not on the local workstation
- The release surface spans two linked hosts and must remain synchronized

## Current Code Shape Summary

The repository already has deployable boundaries, but not clean internal module boundaries.

Common recurring patterns:

- large single-file implementations
- duplicated browser-side logic across `proxmox-ui/`, `extension/`, and `website/`
- shell-driven configuration rendering across multiple scripts
- data contracts expressed implicitly through env vars and generated files rather than versioned schemas
- validation focused on syntax and packaging preconditions, not behavior or contract verification

## Immediate Refactor Baseline

The baseline for the next steps is:

- Phase 0 analysis documented
- Phase 1 target architecture documented
- multi-agent handoff files created under `docs/refactor/`
- repository validation updated to enforce these documents

