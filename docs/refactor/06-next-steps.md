# Next Steps

## Immediate next slice

Now that the control plane exposes a normalized endpoint profile contract `v1`, the browser-side VM profile mapper and helper layer are shared, the Proxmox UI entrypoint is down to about 552 lines, and the extension entrypoint is down to about 189 lines, the next slice should keep shrinking the remaining UI/control-plane monoliths and remove the next orchestration-heavy blocks.

### Concrete next tasks

1. Continue splitting `proxmox-ui/beagle-ui.js`:
   - extract the remaining loading-overlay/profile-shell/bootstrap helpers and catalog/context wiring into dedicated modules under `proxmox-ui/components/`, `proxmox-ui/provisioning/`, and `proxmox-ui/state/`
   - the remaining file should eventually act purely as the ExtJS entrypoint that composes imports and wires them to the Proxmox UI lifecycle.
2. Continue splitting the browser UI action/render layers:
   - move the next action-heavy profile modal helpers out of `extension/components/profile-modal.js` and, where shared, out of `proxmox-ui/components/profile-modal.js`
   - keep the shared browser helper seam under `extension/shared/*` when both browser surfaces intentionally expose the same profile semantics
3. Isolate the still-Proxmox-specific ExtJS runtime coupling in `proxmox-ui/components/extjs-integration.js` further:
   - document and reduce hard-coded selectors/component queries where practical
   - avoid letting new business logic drift back into that component
4. Inventory remaining direct `qm`/`pvesh` usage in scripts and move the first reusable calls behind provider helpers instead of raw subprocess invocations.
5. Start decomposing `proxmox-host/bin/beagle-control-plane.py` around service-oriented modules now that provider-backed read/write/guest-exec seams and the explicit endpoint profile contract exist.
6. Align installer-generation/env builders with the same endpoint-profile contract source instead of reshaping overlapping fields in multiple browser/runtime places.
7. Add broader automated checks for the browser extension, Proxmox UI modules, and proxmox-host modules beyond syntax and `py_compile`.
8. Keep `09-provider-abstraction.md` current whenever a direct Proxmox dependency is removed or newly discovered.

## After that

1. Add smoke verification for generated installer URLs and expected public artifact names.
2. Begin thin client runtime seam extraction around config, network, pairing, and Moonlight launch.
