# Next Steps

## Immediate next slice

Now that the control plane exposes a normalized endpoint profile contract `v1`, the browser-side VM profile mapper is shared, the Proxmox UI monolith is down to about 797 lines, and the extension entrypoint is down to about 328 lines, the next slice should keep shrinking the remaining entrypoint/UI monoliths and remove the next browser-side duplication layer.

### Concrete next tasks

1. Continue splitting `proxmox-ui/beagle-ui.js`:
   - extract the catalog/profile resolution and bootstrap wiring into dedicated modules under `proxmox-ui/provisioning/` and `proxmox-ui/state/`
   - the remaining file should eventually act purely as the ExtJS entrypoint that composes imports and wires them to the Proxmox UI lifecycle.
2. Split `extension/content.js` further into UI-focused modules:
   - extract toolbar/menu injection and mutation-observer boot logic into dedicated extension modules
   - keep `content.js` as the entrypoint that composes those pieces
3. Reduce the next browser-side duplication layer between:
   - `proxmox-ui/components/profile-modal.js`
   - `extension/services/profile.js`
   around endpoint-env export, note generation, and related formatter helpers where behavior is intentionally aligned
4. Inventory remaining direct `qm`/`pvesh` usage in scripts and move the first reusable calls behind provider helpers instead of raw subprocess invocations.
5. Start decomposing `proxmox-host/bin/beagle-control-plane.py` around service-oriented modules now that provider-backed read/write/guest-exec seams and the explicit endpoint profile contract exist.
6. Add broader automated checks for the browser extension, Proxmox UI modules, and proxmox-host modules beyond syntax and `py_compile`.
7. Keep `09-provider-abstraction.md` current whenever a direct Proxmox dependency is removed or newly discovered.

## After that

1. Add smoke verification for generated installer URLs and expected public artifact names.
2. Begin thin client runtime seam extraction around config, network, pairing, and Moonlight launch.
