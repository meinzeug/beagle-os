# Next Steps

## Immediate next slice

Keep shrinking the Proxmox-specific surface area now that both browser surfaces share provider-backed seams and the control plane has its first provider helper.

### Concrete next tasks

1. Extract the remaining large Proxmox UI blocks from `proxmox-ui/beagle-ui.js`, starting with the Ubuntu desktop create/edit modal and the provisioning result window, into dedicated `components/` modules.
2. Continue the host-side provider seam in `proxmox-host/providers/proxmox_host_provider.py` by moving VM lifecycle, guest-exec, and provisioning mutations behind that module instead of calling `qm` and `pvesh` from request handlers.
3. Split `extension/content.js` further into UI-focused modules now that Proxmox inventory/config access lives in `extension/providers/proxmox.js` and `extension/services/*`.
4. Inventory remaining direct `qm`/`pvesh` usage in scripts and move the first reusable calls behind provider helpers instead of raw subprocess invocations.
5. Add broader automated checks for the browser extension, Proxmox UI modules, and proxmox-host modules beyond syntax and `py_compile`.
6. Keep `09-provider-abstraction.md` current whenever a direct Proxmox dependency is removed or newly discovered.

## After that

1. Define a versioned endpoint profile contract used by:
   - Proxmox UI
   - control plane
   - hosted installer generation
2. Add smoke verification for generated installer URLs and expected public artifact names.
3. Begin thin client runtime seam extraction around config, network, pairing, and Moonlight launch.
