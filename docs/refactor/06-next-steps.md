# Next Steps

1. Validate VM delete end-to-end on beagleserver Web UI (detail action -> confirmation -> VM removed from inventory).
2. Validate provider-level delete behavior in both modes:
	- `beagle` provider: libvirt domain and local provider state files are cleaned up.
	- `proxmox` provider: `qm destroy --purge 1` path works with current host policies.
3. Add an API smoke test for `DELETE /beagle-api/api/v1/provisioning/vms/{vmid}` covering success and not-found responses.
4. Add a UI smoke test to ensure the new "Delete VM" action is present in detail view and refreshes inventory after deletion.
5. Reinstall one fresh host from the rebuilt ISO and re-check onboarding plus post-login stability.

