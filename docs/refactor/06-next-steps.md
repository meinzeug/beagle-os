# Next Steps

## Immediate next slice

Now that the Proxmox UI monolith is down to about 813 lines, the extension entrypoint is smaller, and browser-side VM profile synthesis lives in dedicated modules, the next slice should turn that duplicated profile shape into a shared contract and keep shrinking the remaining entrypoint/UI monoliths.

### Concrete next tasks

1. Continue splitting `proxmox-ui/beagle-ui.js`:
   - extract the catalog/profile resolution and bootstrap wiring into dedicated modules under `proxmox-ui/provisioning/` and `proxmox-ui/state/`
   - the remaining file should eventually act purely as the ExtJS entrypoint that composes imports and wires them to the Proxmox UI lifecycle.
2. Define and implement a stable endpoint profile contract shared by:
   - `proxmox-ui/state/vm-profile.js`
   - `extension/services/profile.js`
   - the host-side control plane profile payload generator
3. Split `extension/content.js` further into UI-focused modules now that Proxmox inventory/config access and VM profile resolution live in `extension/services/*`.
4. Inventory remaining direct `qm`/`pvesh` usage in scripts and move the first reusable calls behind provider helpers instead of raw subprocess invocations.
5. Start decomposing `proxmox-host/bin/beagle-control-plane.py` around service-oriented modules now that provider-backed read/write/guest-exec seams exist.
6. Add broader automated checks for the browser extension, Proxmox UI modules, and proxmox-host modules beyond syntax and `py_compile`.
7. Keep `09-provider-abstraction.md` current whenever a direct Proxmox dependency is removed or newly discovered.

## After that

1. Add smoke verification for generated installer URLs and expected public artifact names.
2. Begin thin client runtime seam extraction around config, network, pairing, and Moonlight launch.
