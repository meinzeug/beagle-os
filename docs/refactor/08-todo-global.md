# Global TODO

- [x] Fix Web UI onboarding/login modal visibility conflicts.
- [x] Fix Web UI auth request handling to avoid immediate logout on non-critical 401 responses.
- [x] Fix session-token race condition in host auth service for concurrent requests.
- [x] Increase nginx API/auth rate limits to prevent refresh-path 503s during burst traffic.
- [x] Restore VM provisioning prerequisites on beagleserver (network/storage) and verify API create works.
- [x] Add VM delete function in inventory detail (Web UI + backend route + provider wiring).
- [x] Add noVNC launch actions in Web UI for each VM (inventory + detail).
- [x] Add host API endpoint for per-VM noVNC access metadata (`GET /api/v1/vms/{vmid}/novnc-access`).
- [x] Implement beagle-provider noVNC backend path (libvirt VNC discovery + tokenized websockify + nginx route).
- [x] Harden install flow so required dist artifacts are mandatory (no warning-only continue on missing installer assets).
- [x] Rebuild server installer ISO from current workspace changes.
- [x] Reset/recreate beagleserver VM to boot from rebuilt server-installer ISO.
- [x] Remove the explicit ubuntu-beagle installer network seed path that reproducibly trapped VM 101 in early cloud-init.
- [x] Recreate VM 101 with the simplified `CIDATA` seed (`user-data` + `meta-data` only) and verify Subiquity advances past the former cloud-init wait state.
- [ ] Re-run VM 101 autoinstall to true completion without manual callback forcing and confirm first-boot transition on its own.
- [ ] Verify first-boot Sunshine readiness gate and callback end-to-end on a fully clean VM 101 run (no manual completion override).
- [ ] Rebuild thin-client installer payload/bootstrap with patched non-interactive target-disk selection and rerun thinclient install.
- [ ] Redeploy patched provider start/redefine behavior on installed beagleserver host and recreate VM 101 to remove stale-domain autoinstall loop risk.
- [ ] Install beaglethinclient against the successfully provisioned VM 101 and verify Moonlight streaming end-to-end.
- [ ] Complete in-VM installer flow and re-validate host API/download/noVNC paths post-install.
- [ ] Add automated API regression test for `DELETE /api/v1/provisioning/vms/{vmid}`.
- [ ] Add automated API regression test for `GET /api/v1/vms/{vmid}/novnc-access` (proxmox + beagle success payloads and failure handling).
- [ ] Add UI regression test for VM delete action visibility and post-delete inventory refresh.
- [ ] Add UI regression test for noVNC action buttons in inventory/detail and launch/error behavior.
- [ ] Add regression tests for concurrent auth refresh + dashboard polling.
- [ ] Add UI-level provisioning smoke test in CI.
- [ ] Backport VM-side hotfixes through a fresh ISO reinstall validation run.

