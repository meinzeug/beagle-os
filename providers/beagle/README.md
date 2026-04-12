# Beagle Provider Skeleton

This directory is the first provider-neutral browser-side Beagle virtualization skeleton.

Current scope:

- `virtualization-provider.js` registers `providerId: "beagle"` against `core/provider/registry.js`
- inventory reads come from the Beagle host surface `/api/v1/vms`
- VM config is synthesized from inventory because there is not yet a dedicated provider-neutral VM-config HTTP route
- guest-interface reads intentionally return an empty list until a provider-neutral guest-network endpoint exists

Host-side pairing:

- the matching host provider lives in `beagle-host/providers/beagle_host_provider.py`
- that provider is state-backed, not Proxmox-backed
- default state root is `/var/lib/beagle/providers/beagle`
- override with `BEAGLE_BEAGLE_PROVIDER_STATE_DIR`

This is a skeleton, not a finished hypervisor backend. Its purpose is to prove that the repo now has a real second provider seam instead of only Proxmox-shaped abstractions.
