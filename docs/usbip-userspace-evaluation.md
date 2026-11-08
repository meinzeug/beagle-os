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

## Alternative server and actual data transfer

On 2026-11-08, an isolated evaluation of `calibrae/extender` v0.1.0,
commit `52eeb5a84fa0c9e99fe178848c98bf2021a07512`, revealed that
guest USB enumeration repeated SET_CONFIGURATION on the phone. The phone
then disconnected from the thin client, leaving the exported device handle
stale. The experimental patch in `third_party/usbip-extender/` skips that
request only when the physical device already has the requested configuration;
other requests retain the upstream behaviour.

With that patch, the phone appeared on the VM's virtual USB controller. After
the owner approved its new ADB host key, an Android property command succeeded
and a 256 KiB test file was transferred, checksum-verified, and removed. This
demonstrates a real USB data transfer through the experimental server, not
automatic provisioning or long-term stability. The test server was bound only
to thinclient loopback and reached over the existing authenticated SSH tunnel.
The temporary USB attachment was detached after testing and the existing ADB
bridge restored.

The SC420 microphone and webcam must remain available while USB is used.
The patched camera pipeline was separately exercised with the physical webcam:
the VM received three decoded 640x480 frames through a dedicated V4L2
loopback device. The audio bridge received non-zero PCM samples from the SC420;
the phone command, camera capture and microphone capture also succeeded
concurrently. No audio or video recording was retained. These temporary services do not
survive a thinclient reboot. Camera and audio streams are separate from the
experimental USB/IP server, which has not been validated for isochronous or
interrupt transfers.

Automatic integration remains open: pin and reproducibly build the patched
server for the target image, reconcile hotplug and device ownership, protect
local input, mounted storage, camera and audio, manage the secure tunnel and
restart/cleanup, and verify concurrent devices, unplug/replug and reboots on
the installed image. Do not enable an unverified general-purpose USB backend
or describe the temporary test as a completed automatic deployment.
