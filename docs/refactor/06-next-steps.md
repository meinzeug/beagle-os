# Next Steps

1. Complete interactive install flow inside recreated `beagleserver` VM (currently booted from server-installer ISO).
2. Deploy latest host/proxy changes to installed beagleserver and run full service re-install (`install-beagle-host-services.sh` + `install-beagle-proxy.sh`).
3. Validate installer/download endpoints after hardening:
	- `GET /beagle-api/api/v1/vms/{vmid}/installer.sh` returns 200 and script body.
	- `GET /beagle-api/api/v1/vms/{vmid}/installer.ps1` returns 200 and script body.
4. Validate noVNC action flow in both UI entry points:
	- Inventory row action `noVNC`
	- Detail action `noVNC Console`
5. Validate provider-specific noVNC behavior in both modes:
	- `proxmox` provider: generated URL opens Proxmox noVNC console directly.
	- `beagle` provider: generated URL opens tokenized Beagle noVNC path successfully.
6. Validate VM delete end-to-end on beagleserver Web UI (detail action -> confirmation -> VM removed from inventory).
7. Add API smoke tests for:
	- `DELETE /beagle-api/api/v1/provisioning/vms/{vmid}`
	- `GET /beagle-api/api/v1/vms/{vmid}/novnc-access`
8. Re-check onboarding plus post-login stability after reinstall (including installer endpoints and noVNC).

