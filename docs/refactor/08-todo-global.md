# Global TODO

- [x] Fix Web UI onboarding/login modal visibility conflicts.
- [x] Fix Web UI auth request handling to avoid immediate logout on non-critical 401 responses.
- [x] Fix session-token race condition in host auth service for concurrent requests.
- [x] Increase nginx API/auth rate limits to prevent refresh-path 503s during burst traffic.
- [x] Restore VM provisioning prerequisites on beagleserver (network/storage) and verify API create works.
- [x] Add VM delete function in inventory detail (Web UI + backend route + provider wiring).
- [ ] Add automated API regression test for `DELETE /api/v1/provisioning/vms/{vmid}`.
- [ ] Add UI regression test for VM delete action visibility and post-delete inventory refresh.
- [ ] Add regression tests for concurrent auth refresh + dashboard polling.
- [ ] Add UI-level provisioning smoke test in CI.
- [ ] Backport VM-side hotfixes through a fresh ISO reinstall validation run.

