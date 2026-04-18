# Next Steps

1. Rebuild and redeploy thin-client installer artifacts so the patched non-interactive disk selection logic is included in the booted media:
	- rebuild payload/bootstrap artifacts,
	- regenerate VM-specific wrapper from `/api/v1/vms/101/installer.sh`,
	- recreate thinclient USB raw image and reattach to `beaglethinclient`.
2. Re-run thinclient install from preset and verify it no longer fails at `line=2007 cmd=target_disk="$(choose_target_disk)"`.
3. Recreate VM 101 once with patched host provider/start behavior deployed on the installed beagleserver host (or sync runtime code), then validate:
	- no stale installer `args`/ISO after finalize,
	- no UEFI shell fallback,
	- guest gets IP and Sunshine readiness.
4. After VM 101 is stream-ready, boot `beaglethinclient` from installed disk (not USB media) and verify automatic Moonlight connect using preset credentials.
5. Capture final proof screenshot from `beaglethinclient` showing actual streamed desktop from VM 101.
6. Once end-to-end passes, run final docs sync + commit/push:
	- `05-progress.md`,
	- `06-next-steps.md`,
	- `08-todo-global.md`,
	- `09-provider-abstraction.md`.

