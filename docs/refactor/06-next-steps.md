# Next Steps

## Immediate next slice

Extend the new provider-neutral seam beyond the first browser-side wiring step and keep shrinking the Proxmox-specific surface area.

### Concrete next tasks

1. Move the large profile modal renderer and fleet modal renderer from `proxmox-ui/beagle-ui.js` into `components/`, but keep them bound to `core/platform` and `core/virtualization` services only.
2. Introduce the same provider-neutral browser-side contract into `extension/content.js` or an aligned shared browser module to stop re-encoding Proxmox inventory logic there.
3. Start a host-side provider seam for `proxmox-host/bin/beagle-control-plane.py`, initially around inventory and VM config access.
4. Inventory direct `qm`/`pvesh` usage in scripts and move the first reusable calls behind a provider helper instead of raw subprocess invocations.
5. Add broader automated checks for newly introduced browser-side modules beyond syntax-only validation.
6. Keep `09-provider-abstraction.md` current whenever a direct Proxmox dependency is removed or newly discovered.

## After that

1. Define a versioned endpoint profile contract used by:
   - Proxmox UI
   - control plane
   - hosted installer generation
2. Add smoke verification for generated installer URLs and expected public artifact names.
3. Begin thin client runtime seam extraction around config, network, pairing, and Moonlight launch.
