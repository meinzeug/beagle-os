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

### D17. Host-side guest execution and delayed restarts are provider responsibilities

Decision:

- `ProxmoxHostProvider` owns the host-side `qm guest exec`, `qm guest exec-status`, guest script execution, and delayed restart scheduling helpers.
- `beagle-control-plane.py` may keep small wrapper functions for call-site ergonomics, but it must not shape those Proxmox subprocess calls directly anymore.

Reason:

- Once VM reads and writes were provider-backed, leaving guest-exec and restart orchestration in the HTTP monolith would still keep Proxmox as a business-logic concern instead of a provider concern. Moving these flows into the provider keeps subprocess behavior, polling, timeout handling, and restart sequencing in one replaceable boundary.

### D18. Browser-side VM profile synthesis belongs in dedicated state/service modules before it becomes a shared contract

Decision:

- Move Proxmox-UI VM profile resolution into `proxmox-ui/state/vm-profile.js`.
- Move extension-side VM profile resolution into `extension/services/profile.js`.
- Keep the entrypoints `proxmox-ui/beagle-ui.js` and `extension/content.js` focused on bootstrapping, rendering, and event wiring.

Reason:

- The Beagle endpoint profile is business logic, not UI chrome. Extracting it out of the entrypoints lowers regression risk for the next step, where the remaining duplicated field contract can be unified across browser surfaces and the control plane.

### D19. The control plane must own an explicit endpoint profile contract module

Decision:

- Add `proxmox-host/bin/endpoint_profile_contract.py` as the canonical normalizer for the browser-/installer-facing endpoint profile payload emitted by the control plane.
- `build_profile` may stay the place where profile values are derived, but the public contract shape and defaults must not remain implicit across multiple handlers and helper flows.

Reason:

- The next browser-side contract work depends on one explicit server-owned shape. Without that, the UI and extension can only chase whatever subset each handler happened to serialize, which keeps the contract undocumented in code and increases drift risk.

### D20. Browser-side VM profile mapping should live in one shared browser helper

Decision:

- Add `extension/shared/vm-profile-mapper.js` as the single browser-side mapper for turning provider-backed VM data plus the control-plane contract into browser-local profile objects.
- Keep `proxmox-ui/state/vm-profile.js` and `extension/services/profile.js` as thin fetch/delegation modules instead of maintaining two independent mapping implementations.

Reason:

- The host-side contract is now explicit. Keeping two separate browser mappers after that point would still permit field drift and metadata-fallback drift, only on the client side instead of the server side.

### D21. Extension modal rendering should follow the same component extraction path as the Proxmox UI

Decision:

- Move the Beagle profile renderer/action block out of `extension/content.js` into `extension/components/profile-modal.js`.

Reason:

- The extension had reached the same failure mode the host UI had earlier: one entrypoint file owned both runtime bootstrapping and a large modal renderer. Keeping the render block separate reduces risk for the next DOM-integration splits and aligns the two browser surfaces structurally.

### D22. Browser-facing profile export and note semantics belong in one shared helper

Decision:

- Add `extension/shared/vm-profile-helpers.js` as the single browser-side helper for endpoint-env export, operator notes, and action-state formatting.
- `proxmox-ui/state/vm-profile.js`, `proxmox-ui/components/profile-modal.js`, and `extension/services/profile.js` must consume that shared helper instead of recreating or importing each other's browser-facing profile semantics.

Reason:

- After the host-side contract and the shared browser mapper existed, the remaining drift risk moved to the helper layer. Keeping export/note rules duplicated across UI and extension would still let the two browser surfaces diverge and would keep state modules coupled to component modules for non-rendering logic.

### D23. Extension DOM integration should be a component, not entrypoint logic

Decision:

- Move toolbar injection, menu injection, and mutation-observer boot logic out of `extension/content.js` into a dedicated DOM-integration module under `extension/components/`.
- Keep `extension/content.js` focused on overlay styling, VM profile resolution, and modal/download launch actions.

Reason:

- Provider-backed services and the profile renderer were already extracted. Leaving the Proxmox DOM integration lifecycle in the entrypoint would still keep `content.js` responsible for too many concerns and would slow the next UI refactor slices.

### D24. Proxmox UI ExtJS wiring belongs in a dedicated component

Decision:

- Move Proxmox-console button wiring, fleet-launcher injection, create-VM menu/button integration, and the periodic `integrate()` loop out of `proxmox-ui/beagle-ui.js` into a dedicated component module.
- Keep `beagle-ui.js` focused on runtime collaborators, overlay/bootstrap orchestration, and delegation into dedicated components/state/services.

Reason:

- After the profile/provisioning/fleet/render logic moved out, the largest remaining `beagle-ui.js` block was no longer business logic but Proxmox-ExtJS runtime wiring. That coupling still exists, but isolating it in one component keeps the entrypoint thin and makes the Proxmox-specific UI surface explicit and easier to replace later.

### D25. Shared Proxmox UI modal shell chrome belongs in its own component

Decision:

- Move shared Proxmox-UI modal CSS, overlay lifecycle helpers, and generic loading-overlay rendering into `proxmox-ui/components/modal-shell.js`.
- `proxmox-ui/beagle-ui.js` and other runtime entrypoints may consume that shell, but they must not recreate inline modal CSS or inline loading markup for each flow.

Reason:

- After the renderers, provisioning modals, and ExtJS wiring moved out, the last repeated UI chrome still left in `beagle-ui.js` was the shared overlay shell itself. Treating that shell as a dedicated component keeps styling and loading-state markup separate from fleet/profile business flows and makes the host-installed asset order explicit.

### D26. Provider-backed control-plane read helpers belong in `proxmox-host/services/*`

Decision:

- Move provider-backed VM list, node list, guest IPv4 lookup, VM config lookup, and bridge inventory helpers into service modules under `proxmox-host/services/`.
- `beagle-control-plane.py` may keep thin compatibility wrappers for call sites and handlers, but it should no longer own the concrete read-helper logic itself.

Reason:

- Provider-backed host reads were already abstracted at the provider boundary, but the control-plane entrypoint still directly shaped those reads and cache keys. A small service layer creates the first real internal module seam for the host process without changing HTTP behavior and gives later profile/inventory extractions a stable dependency to build on.

### D27. VM-state and compliance composition should be a host service, not inline control-plane logic

Decision:

- Move endpoint compliance evaluation and VM-state assembly into a dedicated service module under `proxmox-host/services/`.
- Keep the public helper names `evaluate_endpoint_compliance()` and `build_vm_state()` in `beagle-control-plane.py` as thin delegation wrappers so existing handler call sites stay stable during the migration.

Reason:

- Once provider-backed inventory reads had a service seam, the next repeated read-model composition block was VM-state and compliance. Extracting that block gives multiple handlers a shared internal service without forcing a broad call-site rewrite and reduces the control-plane entrypoint by another chunk before tackling the larger `build_profile()` logic.
