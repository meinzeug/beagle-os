# Next Steps

## Immediate next slice

Now that the control plane exposes a normalized endpoint profile contract `v1`, the browser-side VM profile mapper and helper layer are shared, the Proxmox UI entrypoint is down to about 410 lines, the extension entrypoint is down to about 189 lines, and the first provider-backed host read/state services exist under `proxmox-host/services/`, the next slice should keep shrinking `beagle-ui.js` while turning the control plane into a real service composition surface instead of one huge file.

### Concrete next tasks

1. Continue splitting `proxmox-ui/beagle-ui.js`:
   - extract the remaining fleet/profile launch orchestration and dependency-composition wrappers into dedicated modules under `proxmox-ui/components/` and `proxmox-ui/state/`
   - after `modal-shell.js`, `extjs-integration.js`, and the modal renderers are out, the remaining file should converge on dependency lookup plus a small `boot()` entrypoint
2. Continue decomposing `proxmox-host/bin/beagle-control-plane.py` around service-oriented modules:
   - move the next browser-/installer-facing profile orchestration blocks behind thin service helpers that consume `VirtualizationInventoryService`, `VmStateService`, `ProxmoxHostProvider`, and `endpoint_profile_contract.py`
   - the most valuable next extraction is now `build_profile` itself plus the related assignment/public-stream helpers, because `build_vm_state` and compliance evaluation already live behind a service seam
3. Continue splitting the browser UI action/render layers:
   - move the next action-heavy profile modal helpers out of `extension/components/profile-modal.js` and, where shared, out of `proxmox-ui/components/profile-modal.js`
   - keep the shared browser helper seam under `extension/shared/*` when both browser surfaces intentionally expose the same profile semantics
4. Isolate the still-Proxmox-specific ExtJS runtime coupling in `proxmox-ui/components/extjs-integration.js` further:
   - document and reduce hard-coded selectors/component queries where practical
   - avoid letting new business logic drift back into that component
5. Inventory remaining direct `qm`/`pvesh` usage in scripts and move the first reusable calls behind provider helpers instead of raw subprocess invocations.
6. Align installer-generation/env builders with the same endpoint-profile contract source instead of reshaping overlapping fields in multiple browser/runtime places.
7. Add broader automated checks for the browser extension, Proxmox UI modules, and proxmox-host modules beyond syntax and `py_compile`.
8. Keep `09-provider-abstraction.md` current whenever a direct Proxmox dependency is removed or newly discovered.

## After that

1. Add smoke verification for generated installer URLs and expected public artifact names.
2. Begin thin client runtime seam extraction around config, network, pairing, and Moonlight launch.
