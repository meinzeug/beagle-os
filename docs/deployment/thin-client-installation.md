# Thin-Client Installation

## Target scenario

Beagle OS is built for one endpoint model:

- `Beagle Stream Server` runs inside the streamed VM
- `Beagle Stream Client` runs on the endpoint
- the current infrastructure provider supplies inventory, metadata and installer distribution

The active provider is Beagle host infrastructure. The endpoint/runtime contract should remain stable even as host integration is moved behind explicit provider seams.

The repository ships both the Beagle endpoint runtime and the USB/local-disk installation path used to put that runtime onto real hardware or test VMs.

## Current assumptions

- Debian or Ubuntu style package management on the build/installer side
- the USB writer is executed on a Linux workstation with `sudo`
- the resulting endpoint is a dedicated Beagle device, not a general-purpose desktop
- the endpoint boots directly into a Beagle Stream Client session against a provider-assigned Beagle Stream Server VM

## Installation flow

1. Install the Beagle integration on the active management host.
2. Prepare the target VM with Beagle Stream Server.
3. Store the Beagle metadata on that VM in the management plane.
4. Download the VM-specific Beagle installer from the Beagle UI.
5. Write the installer to USB or install directly to a target disk.
6. Boot the endpoint and verify that Beagle Stream Client starts against the intended VM.

The preferred operator path is now VM-centric: the current provider host publishes one installer per VM, already seeded with the correct Beagle profile.

## Beagle Stream Client profile behavior

A Beagle profile contains:

- the Beagle Stream Server host / API URL
- the Beagle Stream Client app name, usually `Desktop`
- codec, decoder, bitrate, FPS and audio defaults
- optional Beagle Stream Server credentials and pairing PIN
- the current provider location/binding fields, today usually host and VMID

This means a Beagle endpoint does not need manual target entry during rollout.
The endpoint simply boots with the profile that belongs to the streamed VM.

## Example commands

Interactive install on an existing Linux system:

```bash
sudo ./thin-client-assistant/installer/install.sh
```

Install project assets on a Beagle host for local operator distribution:

```bash
./scripts/install-beagle-host.sh
```

Provision an Ubuntu guest for the preferred Beagle Stream Server path:

```bash
./scripts/configure-beagle-stream-server-guest.sh \
  --beagle-host beagle.local \
  --vmid 100 \
  --guest-user dennis \
  --beagle-stream-server-user beagle-stream-server \
  --beagle-stream-server-password 'choose-a-strong-password'
```

Register a Beagle endpoint certificate on the Beagle Stream Server VM without interactive pairing:

```bash
./scripts/register-beagle-stream-client-on-beagle-stream-server.sh \
  --client-config Beagle Stream Client.conf \
  --beagle-stream-server-state /home/dennis/.config/beagle-stream-server/beagle_stream_server_state.json \
  --device-name beagle-os-101
```

Install the latest published release on a Beagle host without cloning the repository:

```bash
tmpdir="$(mktemp -d)"
cd "$tmpdir"
curl -fsSLo beagle-os.tar.gz \
  https://beagle-os.com/beagle-updates/beagle-os-latest.tar.gz
tar -xzf beagle-os.tar.gz
./scripts/install-beagle-host.sh
```

## Hosted installer endpoints

The Beagle host publishes these operator-facing endpoints:

- VM-specific installer: `https://<host>/beagle-downloads/pve-thin-client-usb-installer-vm-<vmid>.sh`
- Beagle installer ISO: `https://<host>/beagle-downloads/beagle-os-installer-amd64.iso`
- generic fallback installer: `https://<host>/beagle-downloads/pve-thin-client-usb-installer-host-latest.sh`
- hosted status JSON: `https://<host>/beagle-downloads/beagle-downloads-status.json`
- Beagle control-plane health: `https://<host>/beagle-api/api/v1/health`

In the current management UI path, the VM-specific download path is guarded by Beagle's installer preparation flow:

- `USB Installer bereit`: the target VM is ready and the installer can be downloaded immediately
- `Beagle Stream Server wird vorbereitet`: Beagle is still checking or configuring Beagle Stream Server for the selected VM
- `Ziel ungeeignet`: the selected VM is not offered as a final streaming target

The intended VM-centric flow today is:

1. Download the VM-specific `USB Installer Skript` in the management UI.
2. Run the script on the workstation that has the target USB stick attached.
3. The script downloads the current Beagle installer ISO from the management host.
4. The script writes the bootable USB stick and embeds the selected VM profile.
5. Install Beagle OS on the thin client.
6. The installed endpoint boots with Beagle Stream Client defaults for that VM.

## Build and validation commands

Prepare a USB installer stick:

```bash
./thin-client-assistant/usb/pve-thin-client-usb-installer.sh --device /dev/sdX
```

Build the live installer assets explicitly:

```bash
./scripts/build-thin-client-installer.sh
```

Build the Beagle OS image directly:

```bash
./scripts/build-beagle-os.sh
```

Refresh hosted artifacts on an installed Beagle host:

```bash
sudo /opt/beagle/scripts/refresh-host-artifacts.sh
```

Verify that a host installation is healthy:

```bash
/opt/beagle/scripts/check-beagle-host.sh
```

## Post-install verification

- inspect `/etc/pve-thin-client/thinclient.conf`
- inspect `/etc/beagle-os/endpoint.env` on Beagle OS images
- run `systemctl status pve-thin-client-prepare.service`
- verify `beagle-stream-client` is available on the endpoint
- verify `beagle-stream-client list <beagle-stream-server-host>` resolves the streamed target app
- verify the endpoint can actually start the Beagle Stream Server `Desktop` stream for the assigned VM
