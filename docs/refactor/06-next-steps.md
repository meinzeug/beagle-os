# Next Steps

1. Apply the repo onboarding fix on the running beagleserver host and verify runtime behavior:
	- deploy updated host scripts/services,
	- restart beagle manager,
	- verify `/api/v1/auth/onboarding/status` returns `pending=true` on fresh bootstrap-disabled state.
2. Validate Web UI onboarding flow end-to-end on installed host:
	- onboarding modal appears,
	- `/api/v1/auth/onboarding/complete` creates first admin,
	- post-onboarding login and dashboard load remain stable.
3. Fix immediate post-install disk boot on `beagleserver` after successful installer completion:
	- verify effective libvirt boot-order/device mapping for `vda` vs empty `sda` cdrom,
	- confirm GRUB/boot target on installed disk,
	- reach first boot login on installed host without live-ISO runtime artifacts.
4. Re-run clean reinstall once with the now-proven patched ISO path and confirm no residual transient state in `/var/log/beagle-server-installer.log`.
5. Continue the requested realistic E2E product flow from installed host state:
	- open Beagle Web UI,
	- create Beagle Ubuntu/XFCE/Sunshine desktop VM,
	- download Live-USB installer script via Web UI,
	- reinstall `beaglethinclient`,
	- verify first-time Moonlight -> Sunshine auto-connect and active stream.
6. Persist and verify stream firewall reconciliation on installed beagleserver host:
	- run `/opt/beagle/scripts/reconcile-public-streams.sh` on boot/service restart,
	- confirm `inet filter forward` contains `beagle-stream-allow` rules for RTSP + UDP stream ports.
7. Verify the guest `beagle-sunshine-healthcheck.timer` path on VM 101:
	- timer active after reboot,
	- forced crash (`pkill sunshine`) is recovered automatically,
	- local `/api/apps` check succeeds again without manual intervention.
8. Fix server-installer live smoke DHCP reliability in local libvirt harness (`scripts/test-server-installer-live-smoke.sh`) after the boot-path stabilization.
9. Stabilize standalone stream simulation harness for real-libvirt execution (`scripts/test-standalone-desktop-stream-sim.sh`).
10. Once end-to-end passes, run final docs sync + commit/push:
	- `05-progress.md`,
	- `06-next-steps.md`,
	- `08-todo-global.md`,
	- `09-provider-abstraction.md`.

