# Next Steps

## Immediate next slice

Now that the Proxmox UI monolith is down to about 950 lines and VM lifecycle writes run through `proxmox-host/providers/proxmox_host_provider.py`, the next slice should finish the control-plane provider seam and continue shrinking the browser-side monoliths.

### Concrete next tasks

1. Move the remaining direct `qm` usage in `proxmox-host/bin/beagle-control-plane.py` behind the host provider:
   - `qm guest exec` and `qm guest exec-status` paths used by Ubuntu Beagle finalize/refresh flows
   - the `schedule_ubuntu_beagle_vm_restart` bash heredoc, either by wrapping it in a provider helper or by encapsulating the `qm`/`systemd-run` invocations it emits
   - add matching provider methods (for example `guest_exec`, `guest_exec_status`, `schedule_restart`) so the control plane never calls `qm` directly.
2. Continue splitting `proxmox-ui/beagle-ui.js`:
   - extract the catalog/profile resolution and bootstrap wiring into dedicated modules under `proxmox-ui/provisioning/` and `proxmox-ui/state/`
   - the remaining file should eventually act purely as the ExtJS entrypoint that composes imports and wires them to the Proxmox UI lifecycle.
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
