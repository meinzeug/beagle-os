# Beagle Provider Skeleton

This directory is the first provider-neutral browser-side Beagle virtualization skeleton.

Current scope:

- `virtualization-provider.js` registers `providerId: "beagle"` against `core/provider/registry.js`
- VM inventory reads come from the Beagle host surface `/api/v1/vms`
- node, host, storage, VM-config, and guest-interface reads come from the provider-neutral Beagle host surface under `/api/v1/virtualization/*`
- the browser provider is therefore no longer synthesizing node lists or VM config from the VM inventory response alone

Host-side pairing:

- the matching host provider lives in `beagle-host/providers/beagle_host_provider.py`
- that provider is state-backed, not Proxmox-backed
- default state root is `/var/lib/beagle/providers/beagle`
- override with `BEAGLE_BEAGLE_PROVIDER_STATE_DIR`

This is a skeleton, not a finished hypervisor backend. Its purpose is to prove that the repo now has a real second provider seam instead of only Proxmox-shaped abstractions.
