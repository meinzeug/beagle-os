# Userspace USB/IP evaluation — 2026-11-08

The kernel `usbip-host` path repeatedly disconnected a Redmi 14C before it
could be used by a guest. A short isolated evaluation tested the MIT-licensed
[jiegec/usbip](https://github.com/jiegec/usbip) revision
`f78a13ded3b750d54f16b5a4b796d69558305ecd` with its libusb (`rusb`) backend.
This is an evaluation, not an integrated or production-ready Beagle backend.

The upstream QEMU passthrough test passed with emulated high-speed and
SuperSpeed devices using both the nusb and rusb backends. In a separate
headless QEMU Linux guest, the actual phone was exported by a temporary server
on the thin client, connected through an SSH tunnel bound to loopback, and
attached by the guest's Linux vhci driver. The guest enumerated the phone as
USB vendor/product 2717:ff48 and it remained present for eight seconds. The
phone's ADB bridge was stopped for the test and restored afterwards.

The guest's enumeration is not proof that ADB, file transfers, reconnect,
concurrent devices, server restarts or long-running sessions work. The example
server enumerates devices at startup and listens on all interfaces by default;
for the experiment it was modified to bind loopback only and filtered to the
phone. It must not be deployed as-is: a persistent integration needs explicit
authorization, isolation, a fixed dependency/build and license review, secure
transport, device ownership and release, hotplug handling, and tests for
failure recovery and the protected keyboard, mouse, audio and storage policy.

The userspace server generated a bus ID of the form `1-55-3`, while the kernel
server uses IDs such as `1-2.1.3`. The VM attach parser accepts both formats;
this alone does not install or enable the userspace server.
