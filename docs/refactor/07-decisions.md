# Decisions

## 2026-04-09

### D1. Refactor starts with enforcement and documentation

Decision:

- Create and maintain the `docs/refactor/` set before broad code movement.

Reason:

- The repo is now explicitly multi-agent and requires fast handoff without hidden state.

### D2. No big-bang restructure

Decision:

- Refactor around current deployable surfaces first and keep current runtime entrypoints stable.

Reason:

- The product has multiple critical runtime paths and release surfaces that cannot tolerate a repo-wide rewrite.

### D3. `AGENTS.md` must be tracked, not ignored

Decision:

- Remove `AGENTS.md` from `.gitignore`.

Reason:

- A central continuation document cannot be intentionally ignored by default.

### D4. Validation should enforce refactor continuity

Decision:

- `scripts/validate-project.sh` must require `AGENTS.md` and all mandatory `docs/refactor/` files.

Reason:

- Process-critical files should fail validation if they disappear.

### D5. Shared-core work will be incremental

Decision:

- Do not create a large new shared package immediately. First extract small seams inside existing deployable directories.

Reason:

- This lowers regression risk and avoids a speculative abstraction layer.

### D6. Start Proxmox UI modularization with a runtime-safe helper seam

Decision:

- Extract config/token/URL helper logic from `proxmox-ui/beagle-ui.js` into a separately installed runtime asset first.

Reason:

- This creates a real module boundary without changing the Proxmox UI entrypoint or operator workflow.

### D7. Keep deployed Proxmox UI asset names flat while the repo structure becomes modular

Decision:

- Store extracted modules in repo subdirectories such as `proxmox-ui/api-client/` and `proxmox-ui/state/`, but install them on the Proxmox host as flat JS asset names.

Reason:

- This preserves modular repo structure while avoiding unnecessary runtime risk from assuming nested static asset paths inside the Proxmox UI host.

### D8. Treat Proxmox as the first provider, not the fixed architecture center

Decision:

- Introduce provider-neutral seams and move new business logic behind them, with Proxmox as the first concrete provider implementation.

Reason:

- The product must stay fully Proxmox-compatible now while becoming replaceable or extensible later without reworking every UI, control-plane, and provisioning flow.

### D9. Introduce top-level provider-neutral browser seams under `core/` and `providers/`

Decision:

- Add `core/provider/`, `core/virtualization/`, `core/platform/`, and `providers/proxmox/` to host the first runtime abstraction used by the Proxmox UI.

Reason:

- A top-level seam makes the provider split explicit across the repo and avoids burying provider-neutral contracts inside a Proxmox-specific directory.

### D10. Make provider-coupling documentation mandatory for continuation

Decision:

- Treat `docs/refactor/09-provider-abstraction.md` as part of the required handoff set and enforce its presence in validation.

Reason:

- Provider neutrality is now a core architecture rule, so the repo needs one authoritative place that tracks what is already abstracted and what is still directly Proxmox-bound.

### D11. The browser extension must mirror the same provider seam as the host-installed UI

Decision:

- Move browser-extension VM context resolution and Proxmox reads into explicit `extension/providers/*` and `extension/services/*` files instead of leaving them inside `extension/content.js`.

Reason:

- Provider neutrality cannot stop at the host UI if the browser extension exposes the same operator workflow.

### D12. Control-plane read paths should move first into host-side provider modules

Decision:

- Start the control-plane provider migration with VM inventory, node inventory, storage inventory, next-VMID lookup, VM config reads, and guest IPv4 lookup before touching mutation-heavy flows.

Reason:

- Read paths are the lowest-risk way to establish a stable host-side provider boundary without breaking provisioning and lifecycle operations.

### D13. Large Proxmox UI modals should be extracted as dedicated components before deeper behavioral changes

Decision:

- Move the profile modal and fleet modal out of `proxmox-ui/beagle-ui.js` into `proxmox-ui/components/*`, keeping `beagle-ui.js` as the orchestration layer.

Reason:

- These renderers were the biggest remaining safe extraction targets and reducing the monolith size now makes the next provisioning/UI splits much lower risk.

## 2026-04-10

### D14. Provisioning modals use dependency injection via an options object

Decision:

- `proxmox-ui/components/provisioning-result-modal.js` and `proxmox-ui/components/provisioning-create-modal.js` accept all collaborators (API clients, toast/error helpers, catalog accessors, `showProfileModal`, `showProvisioningResultWindow`, `virtualizationService`, `parseListText`) through a single options object on the exported entrypoint.

Reason:

- These modules load as plain browser IIFEs inside the Proxmox UI runtime and cannot rely on a module system. An options-based seam keeps the contract explicit, avoids creating new shared globals, and lets `beagle-ui.js` keep owning the orchestration layer while the heavy rendering moves out.

### D15. Host-side VM lifecycle writes must go through the provider

Decision:

- `create_vm`, `set_vm_options`, `delete_vm_options`, `set_vm_description`, `set_vm_boot_order`, `start_vm`, and `stop_vm` are provider contract methods on `ProxmoxHostProvider`. Control-plane code must not call `qm create`, `qm set`, `qm start`, or `qm stop` directly.
- Option bags are passed as either a `Mapping` or an iterable of `(name, value)` pairs and get normalized by the provider's `_flatten_option_pairs` helper so callers never build `--flag value` argv themselves.

Reason:

- The read-only host-provider seam was already proven safe. Extending it to writes keeps `qm` as a provider-local implementation detail, gives future providers a single interface to target, and avoids scattering subprocess shaping logic across the request handlers.

### D16. Guest-exec and scheduled restart are a separate host-provider slice

Decision:

- `qm guest exec` / `qm guest exec-status` flows and the `schedule_ubuntu_beagle_vm_restart` bash heredoc stay inside `beagle-control-plane.py` for now and are scheduled as the next host-provider slice.

Reason:

- Guest-exec semantics (long-running commands, pid polling, stdout/stderr capture) and the self-deleting systemd-run restart script are shaped differently from the lifecycle writes. Bundling them into the same slice would have mixed concerns and increased regression risk on a flow that was already runtime-safe.
