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
