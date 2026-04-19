# Next Steps

1. Validate ubuntu install completion path end-to-end on a fresh desktop VM:
	- wait for real guest callback (`/public/ubuntu-install/<token>/complete`),
	- confirm finalize restart occurs,
	- confirm VM status transitions from `installing` -> `running` after guest comes back.
2. Fix immediate post-install disk boot on `beagleserver` after successful installer completion:
	- verify effective libvirt boot-order/device mapping for `vda` vs empty `sda` cdrom,
	- confirm GRUB/boot target on installed disk,
	- reach first boot login on installed host without live-ISO runtime artifacts.
3. Re-run clean reinstall once with the now-proven patched ISO path and confirm no residual transient state in `/var/log/beagle-server-installer.log`.
4. Continue the requested realistic E2E product flow from installed host state:
	- open Beagle Web UI,
	- create Beagle Ubuntu/XFCE/Sunshine desktop VM (re-validate UI no longer reports `Request timeout` on provisioning create),
	- download Live-USB installer script via Web UI,
	- reinstall `beaglethinclient`,
	- verify first-time Moonlight -> Sunshine auto-connect and active stream.
5. Persist and verify stream firewall reconciliation on installed beagleserver host:
	- run `/opt/beagle/scripts/reconcile-public-streams.sh` on boot/service restart,
	- confirm `inet filter forward` contains `beagle-stream-allow` rules for RTSP + UDP stream ports.
6. Verify the guest `beagle-sunshine-healthcheck.timer` path on VM 101:
	- timer active after reboot,
	- forced crash (`pkill sunshine`) is recovered automatically,
	- local `/api/apps` check succeeds again without manual intervention.
7. Fix server-installer live smoke DHCP reliability in local libvirt harness (`scripts/test-server-installer-live-smoke.sh`) after the boot-path stabilization.
8. Stabilize standalone stream simulation harness for real-libvirt execution (`scripts/test-standalone-desktop-stream-sim.sh`).
9. Once end-to-end passes, run final docs sync + commit/push:
	- `05-progress.md`,
	- `06-next-steps.md`,
	- `08-todo-global.md`,
	- `09-provider-abstraction.md`.

