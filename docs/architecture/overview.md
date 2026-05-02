# Architecture

## Overview

The repository is split into two deployable product surfaces:

- `extension/` adds Beagle operator actions to Beagle host VM pages
- `beagle-ui/`, `beagle-host/` and `scripts/` install the same Beagle workflow directly on a Beagle host
- `core/` and `providers/` are the new provider-neutral architecture seam, with Beagle host as the first implementation
- `thin-client-assistant/` prepares a Moonlight-based endpoint that boots into a dedicated streaming session
- `beagle-os/` builds the dedicated endpoint operating system and kernel profile

These parts are intentionally aligned around one runtime path, while the architecture moves toward provider neutrality:

- `Beagle host` is the current management-system provider
- `Sunshine` runs inside the streamed VM
- `Moonlight` runs on the Beagle endpoint

## Provider model

Beagle now distinguishes between:

- provider-neutral contracts and services under `core/`
- concrete provider implementations under `providers/`

Current status:

- Beagle host is the first supported provider
- provider-neutral browser-side seams exist for virtualization and platform service access
- the browser extension now mirrors that split through `extension/common.js`, `extension/provider-registry.js`, `extension/providers/beagle-host.js`, and `extension/services/*`
- browser-side VM profile mapping now lives in one shared helper `extension/shared/vm-profile-mapper.js` used by both the browser extension and the host-installed UI
- the browser extension now also has a dedicated `extension/components/profile-modal.js` renderer, with `extension/content.js` reduced toward DOM integration and bootstrapping
- browser-side endpoint profile resolution now lives in `beagle-ui/state/vm-profile.js` and `extension/services/profile.js` instead of the entrypoint files
- the host control plane now exposes an explicit browser-/installer-facing endpoint profile contract via `beagle-host/bin/endpoint_profile_contract.py`
- the host-installed Beagle host UI now also carries dedicated `components/profile-modal.js`, `components/fleet-modal.js`, `components/provisioning-result-modal.js`, and `components/provisioning-create-modal.js` renderers, with `beagle-ui.js` reduced toward orchestration
- host-side VM lifecycle writes, guest-exec flows, and scheduled restart helpers now flow through `beagle-host/providers/beagle_host_provider.py` alongside the existing read paths
- script-side and thin-client-side provider neutrality are still being migrated incrementally

## Beagle host operator surface

The browser extension and the host-installed UI integration both expose the same operator model on VM pages:

1. Detect the current Beagle host VM context (`node`, `vmid`)
2. Read the VM config and cluster resource state through provider-backed virtualization services
3. Parse Beagle metadata from the VM description
4. Resolve the Sunshine target, Moonlight defaults and Beagle installer URL
5. Show a Beagle profile dialog with export and download actions

The Beagle profile view is now a first-class management primitive.
It gives the operator a resolved endpoint profile for the selected VM instead of only a raw download link.

The profile dialog exposes:

- VM identity and live status
- guest-agent IP discovery where available
- Sunshine host and API URL
- Moonlight app, codec, decoder, bitrate and FPS defaults
- exported endpoint environment data for reproducible rollouts
- direct jump points to the hosted installer and control-plane health

## Managed desktop VM defaults

New managed Ubuntu desktop VMs now default to KDE Plasma with the desktop profile `plasma-cyberpunk` (`Beagle OS Cyberpunk`).
The provisioning stack keeps the older desktop families available for compatibility, but the operator-facing WebUI catalog is intentionally narrowed to the two supported Plasma variants:

- `plasma-cyberpunk` (`Beagle OS Cyberpunk`) — default dark Beagle-branded Plasma profile with the bundled cyberpunk wallpaper
- `plasma-classic` (`KDE Plasma Classic`) — neutral Breeze-style Plasma profile without the branded neon treatment

Selection flow:

- WebUI: `Provisioning -> Neue Beagle VM erstellen -> Desktop-Design`
- API: `POST /api/v1/provisioning/vms` with the field `desktop`
- legacy API aliases such as `plasma` still resolve to the classic Plasma profile for backward compatibility

Implementation notes:

- the guest firstboot path still provisions the desktop through `beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl`
- the cyberpunk wallpaper is a versioned repo asset at `assets/branding/beagle-cyberpunk-wallpaper.png`
- the guest seed ISO embeds that wallpaper so provisioning does not depend on an operator home directory or ad-hoc local files

## Beagle host integration

The host-side installation path adds four operational pieces:

1. a JavaScript asset loaded by the Beagle host web UI
2. a runtime config asset that publishes hosted Beagle URLs into the UI
3. an `nginx` endpoint on `443` that serves hosted downloads and the Beagle API proxy
4. a local Beagle control-plane service that publishes health and VM inventory data

The Beagle host path is intentionally simple:

- the Beagle host generates per-VM installer artifacts
- the host publishes them under `/beagle-downloads/`
- the host also runs a small control plane for health and inventory data
- refresh services keep those artifacts current after host-side changes

This turns a Beagle host into a Beagle management node instead of just a VM hypervisor.
Architecturally, that should now be read as: a Beagle host-backed Beagle management node, not a permanently Beagle host-locked core design.

## Thin-client assistant architecture

The thin-client assistant is split into installer, runtime, system assets and templates.

- `installer/` writes configuration and deploys assets
- `runtime/` contains the actual launch and boot preparation logic
- `systemd/` contains the system service units
- `templates/` contains default config and autostart assets
- `usb/` contains the USB writer, installer UI and local disk installer
- `live-build/` contains the bootable installer definition

### Runtime model

The current Beagle endpoint baseline assumes:

- a dedicated local user account for kiosk operation
- tty/X11 based autologin into a controlled session
- a preseeded Moonlight profile bound to one Beagle host VM
- Sunshine trust and API settings coming from the Beagle profile

Boot flow:

1. the live or local-disk boot medium exposes `vmlinuz`, `initrd.img` and `filesystem.squashfs`
2. the endpoint prepares hostname and networking from the stored profile
3. the runtime loads its Beagle configuration from disk or live media state
4. the session launcher validates that the selected mode is `MOONLIGHT`
5. `launch-moonlight.sh` pairs or reuses trust and starts the configured Sunshine app

## Configuration model

Primary runtime config files:

- `/etc/pve-thin-client/thinclient.conf`
- `/run/live/medium/pve-thin-client/state/thinclient.conf`
- `/etc/beagle-os/endpoint.env` inside the Beagle OS image path

The effective profile contains:

- Beagle host, node and VMID binding
- provider-specific location data as currently rendered by the active provider
- Moonlight host and target app
- Moonlight codec, decoder, bitrate, FPS and audio defaults
- Sunshine API URL, username, password and pairing PIN
- local runtime user and autostart toggles

## Packaging model

The release scripts create:

- a browser extension zip for manual installation
- a Beagle host tarball that currently targets Beagle host deployment
- hosted USB payload and installer artifacts
- optional Beagle OS image artifacts produced by `build-beagle-os.sh`
- sha256 checksums for release verification

Operationally, GitHub only needs to carry the deployable artifacts.
After installation on a Beagle host, the host rebuilds and republishes its own local `/beagle-downloads/` tree for operators and endpoints.
