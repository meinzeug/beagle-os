# Thinclient microphone forwarding and recovery

A USB microphone stays attached to the thinclient. Its PCM stream reaches the
VM as `beagle_tc_microphone`; it need not appear in the VM's `lsusb` output.

## Normal provisioning

VM-specific installer presets carry the USB tunnel host, user, USB/audio/camera
ports, attach address, private SSH key and pinned server host key. The key values
are base64-encoded to preserve multiline data, and are written only to the
protected `credentials.env`, not the public `thinclient.conf`. Base64 provides
no confidentiality: treat installer presets and installation media as secrets.

At boot `config_loader.sh` restores missing preset keys under
`/run/beagle-os/usb-tunnel` (private key mode 0600). Existing enrollment keys in
the config directory take precedence. This also works with Windows-created Live
USB media: permission-sensitive SSH files are created in Linux runtime storage,
not used directly from FAT. Explicitly disabled USB stays disabled. Incomplete
tunnel configuration returns exit status 75 with a diagnostic, so systemd's
`Restart=on-failure` retries while enrollment/heartbeat repair provides the missing
configuration. Host-key checking remains enabled.

The updated manager must generate a new VM-specific preset, and the updated
thinclient runtime must be included in the signed payload/ISO release. Merely
updating a Git checkout does not change already downloaded installation media.
Existing enrolled clients can receive the normal heartbeat USB-config recovery.
Clients with neither a complete preset nor enrollment credentials still require
administrator provisioning; no generic host, key or credentials are inferred.

## Diagnose the physical-to-virtual path

On the thinclient:

```bash
arecord -l
systemctl status beagle-usb-tunnel.service --no-pager -l
journalctl -u beagle-usb-tunnel.service -n 40 --no-pager
```

On the VM:

```bash
pactl list short sources
pactl get-source-mute beagle_tc_microphone
systemctl status beagle-tc-mic-bridge.service --no-pager -l
```

Test the configured audio TCP port. A source name alone proves neither a
connected network tunnel nor captured microphone audio. Measure peak/RMS while
speaking; do not store or upload voice recordings as a diagnostic default.

## Verified incident and temporary direct SSH recovery (2026-10-10)

The physical SC420 USB microphone was visible in thinclient ALSA and PipeWire.
The VM virtual source was the default input, unmuted at 100%, but an eight-second
capture contained only zero samples. The thinclient tunnel exited with status 0
because its host/port were blank and its tunnel keys were absent. The host audio
port rejected TCP connections. This was a transport/provisioning failure before
Wine or TikTok accessed the source.

An administrator-authenticated direct SSH connection allowed a temporary repair:

1. On the thinclient, create `beagle-microphone-source.service` running the
   existing `beagle_audio_input_bridge.py` as the desktop user. Set its HOME,
   XDG_RUNTIME_DIR and PULSE_SERVER to that user's session. Bind only to
   `127.0.0.1:43200`, select the actual USB source, and use `Restart=on-failure`.
   Ensure `/var/log/beagle` exists and is writable by that user.
2. Generate a separate passwordless Ed25519 forwarding key on the VM. Add only
   its public key to the thinclient desktop user's `authorized_keys`, with
   `restrict,port-forwarding,permitopen="127.0.0.1:43200",command="/bin/false"`.
   The private key remains on the VM. This key grants no shell or PTY.
3. Run a VM user service using `ssh -N -T`, `BatchMode=yes`, `IdentitiesOnly=yes`,
   `StrictHostKeyChecking=yes`, a verified dedicated known-hosts file,
   `ExitOnForwardFailure=yes`, keepalives, and
   `-L 127.0.0.1:43200:127.0.0.1:43200`. Use the thinclient's private VPN address
   and its desktop account. Enable restart and autostart for the user service.
4. Add a VM `beagle-tc-mic-bridge.service` override setting
   `BEAGLE_TC_MIC_BRIDGE_HOST=127.0.0.1` and
   `BEAGLE_TC_MIC_BRIDGE_PORT=43200`; reload systemd and restart that bridge.

The repaired VM received 480373 samples in a ten-second test, 438517 nonzero,
with peak 5288. A subsequent twenty-second test reached peak 18410. Only numerical
levels were retained; no voice recordings or credentials were saved to Git.
This proves audio transport and detectable signal, not TikTok source selection.
The VM user tunnel and thinclient source services were enabled for autostart.
A reboot was not performed, to preserve the active remote desktop session.

To retire the temporary route after the normal reverse tunnel is verified,
disable the two dedicated microphone services and remove only their dedicated
bridge override and authorized-key entry. Preserve other keys and configuration.

## Regression checks

`tests/unit/test_microphone_preset_provisioning.py` exercises generated preset ->
installer configuration -> runtime key restoration without enrollment. It checks
per-VM ports, custom tunnel account/attach address, private-file permissions,
preservation of enrolled keys, invalid encoded data, and retryable configuration
failures. Adjacent installer, enrollment and Live USB regression tests cover the
existing paths. Native PowerShell parsing still requires a Windows/PowerShell
runner when PowerShell is absent from the Linux validation environment.
