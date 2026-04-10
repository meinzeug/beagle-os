# Next Steps

## Immediate next slice

Now that the Proxmox UI monolith is down to about 950 lines and the host provider owns VM lifecycle writes, guest-exec, and scheduled restarts, the next slice should shrink the remaining browser monoliths and start moving script-side Proxmox couplings behind reusable seams.

### Concrete next tasks

1. Continue splitting `proxmox-ui/beagle-ui.js`:
   - extract the catalog/profile resolution and bootstrap wiring into dedicated modules under `proxmox-ui/provisioning/` and `proxmox-ui/state/`
   - the remaining file should eventually act purely as the ExtJS entrypoint that composes imports and wires them to the Proxmox UI lifecycle.
2. Split `extension/content.js` further into UI-focused modules now that Proxmox inventory/config access lives in `extension/providers/proxmox.js` and `extension/services/*`.
3. Inventory remaining direct `qm`/`pvesh` usage in scripts and move the first reusable calls behind provider helpers instead of raw subprocess invocations.
4. Start decomposing `proxmox-host/bin/beagle-control-plane.py` around service-oriented modules now that provider-backed read/write/guest-exec seams exist.
5. Add broader automated checks for the browser extension, Proxmox UI modules, and proxmox-host modules beyond syntax and `py_compile`.
6. Keep `09-provider-abstraction.md` current whenever a direct Proxmox dependency is removed or newly discovered.

## After that

1. Define a versioned endpoint profile contract used by:
   - Proxmox UI
   - control plane
   - hosted installer generation
2. Add smoke verification for generated installer URLs and expected public artifact names.
3. Begin thin client runtime seam extraction around config, network, pairing, and Moonlight launch.
