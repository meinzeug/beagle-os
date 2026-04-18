# Progress (2026-04-18)

- Fixed Web UI session-drop behavior by hardening client-side auth error handling in [website/app.js](website/app.js).
- Fixed auth session race condition in [beagle-host/services/auth_session.py](beagle-host/services/auth_session.py) by adding a process-local lock around concurrent session token read/write paths.
- Increased nginx API/auth rate limits in [scripts/install-beagle-proxy.sh](scripts/install-beagle-proxy.sh) and applied the same config live on beagleserver VM to stop refresh-related 503 errors.
- Verified live endpoints on beagleserver VM:
	- `/beagle-api/api/v1/auth/refresh` stable under burst test (no non-200 in test run).
	- VM create API `/beagle-api/api/v1/provisioning/vms` returns 201 with catalog-derived payload.
- Rebuilt server installer ISO successfully:
	- `dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso`
	- `dist/beagle-os-server-installer/beagle-os-server-installer`
- Added VM delete capability for Inventory detail workflows:
	- Provider-neutral contract extended with `delete_vm` in [beagle-host/providers/host_provider_contract.py](beagle-host/providers/host_provider_contract.py).
	- Provider implementations added in [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py) and [beagle-host/providers/proxmox_host_provider.py](beagle-host/providers/proxmox_host_provider.py).
	- Admin HTTP delete route extended to support `DELETE /api/v1/provisioning/vms/{vmid}` in [beagle-host/services/admin_http_surface.py](beagle-host/services/admin_http_surface.py).
	- RBAC mapping updated for delete-provisioning route in [beagle-host/services/authz_policy.py](beagle-host/services/authz_policy.py).
	- Web UI action added in [website/app.js](website/app.js) and cache-bumped in [website/index.html](website/index.html).

