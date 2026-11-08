# Android debugging through a thin client

This is an opt-in ADB bridge, not USB passthrough: Android Studio or adb can
use the phone's debugging protocol, but the VM does not get a USB device and
other USB applications or file-transfer protocols do not use this bridge.
USB/IP remains the general USB forwarding path. Some Android phones disconnect
when bound to Linux usbip-host, even with ADB-only mode enabled.

## Set up

On the thin client install the distro `adb` and Android USB permission rules,
then install `scripts/lib/beagle-adb-local.service` under
`/etc/systemd/system/`. The unit runs as the existing `thinclient` user and
binds ADB to the thin client's loopback interface, never a network interface.
Enable it using `systemctl daemon-reload` and
`systemctl enable --now beagle-adb-local.service`. Verify `ss -lnt` shows
`127.0.0.1:5037`, not `0.0.0.0:5037`.

On the VM, arrange an existing trusted SSH identity and verify the thin-client
host key out of band. The thin-client account must allow local TCP forwarding.
Create `~/.config/beagle/adb-tunnel.env` (mode 0600) containing absolute paths
and the known SSH target, for example:

```
BEAGLE_ADB_SSH_KEY=/home/user/.ssh/thinclient_key
BEAGLE_ADB_KNOWN_HOSTS=/home/user/.ssh/known_hosts
BEAGLE_ADB_SSH_TARGET=thinclient@10.88.1.1
```

Install `scripts/lib/beagle-adb-tunnel.service` into
`~/.config/systemd/user/`, run `systemctl --user daemon-reload`, and enable
and start it with `systemctl --user enable --now beagle-adb-tunnel.service`.
It forwards only `127.0.0.1:5038` to the thin client's local ADB socket; SSH
strict host-key verification is required. Do not expose the ADB port to the
network or share its debugging keys. ADB credentials and approval belong to
the thin-client user. Unlock the phone and approve its Android debugging
prompt for that key. Revoking that approval disconnects the device.

Use `scripts/beagle-adb devices -l` and `scripts/beagle-adb shell ...`, or
set `ADB_SERVER_SOCKET=tcp:127.0.0.1:5038` for an individual process. Do not
set it globally if local devices or emulators also need the local ADB server.
The SSH tunnel does not provide a kernel USB device, and Android Studio must
be launched with the latter environment variable to use this server.
