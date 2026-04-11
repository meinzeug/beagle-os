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

- Add `beagle-host/bin/endpoint_profile_contract.py` as the canonical normalizer for the browser-/installer-facing endpoint profile payload emitted by the control plane.
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

### D26. Provider-backed control-plane read helpers belong in `beagle-host/services/*`

Decision:

- Move provider-backed VM list, node list, guest IPv4 lookup, VM config lookup, and bridge inventory helpers into service modules under `beagle-host/services/`.
- `beagle-control-plane.py` may keep thin compatibility wrappers for call sites and handlers, but it should no longer own the concrete read-helper logic itself.

Reason:

- Provider-backed host reads were already abstracted at the provider boundary, but the control-plane entrypoint still directly shaped those reads and cache keys. A small service layer creates the first real internal module seam for the host process without changing HTTP behavior and gives later profile/inventory extractions a stable dependency to build on.

### D27. VM-state and compliance composition should be a host service, not inline control-plane logic

Decision:

- Move endpoint compliance evaluation and VM-state assembly into a dedicated service module under `beagle-host/services/`.
- Keep the public helper names `evaluate_endpoint_compliance()` and `build_vm_state()` in `beagle-control-plane.py` as thin delegation wrappers so existing handler call sites stay stable during the migration.

Reason:

- Once provider-backed inventory reads had a service seam, the next repeated read-model composition block was VM-state and compliance. Extracting that block gives multiple handlers a shared internal service without forcing a broad call-site rewrite and reduces the control-plane entrypoint by another chunk before tackling the larger `build_profile()` logic.

### D28. Provider-neutrality is a waypoint, not the product end state

Decision:

- Treat provider-neutral seams as an enabling step toward a first-party Beagle virtualization product/provider, not as the final destination.
- Plan for Proxmox to become one optional provider among several rather than the permanent operational default.
- Prefer new abstractions that a future Beagle-owned provider can implement directly, even when Proxmox is the only concrete provider today.

Reason:

- The intended product direction is not simply "Beagle on top of whatever hypervisor happens to be underneath". The intended direction is Beagle owning the virtualization path itself over time. Without recording that explicitly, the refactor could converge on a permanently external-provider-centered architecture that is cleaner than today but still strategically wrong.

### D29. The generic host surface is `beagle-host/`, not `proxmox-host/`

Decision:

- Rename the canonical repo surface for the host control plane, systemd units, templates, and internal host services from `proxmox-host/` to `beagle-host/`.
- Keep only truly provider-specific names under that surface, such as `providers/proxmox_host_provider.py`, and preserve external Proxmox-facing flags/scripts where renaming them would be a compatibility break.

Reason:

- The host control plane is no longer architecturally Proxmox-specific. Leaving the whole repo surface named `proxmox-host/` would keep encoding the old architecture center into every future refactor slice and would directly contradict the goal of making Proxmox optional.

### D30. Host-side VM profile synthesis should be a service, not inline control-plane logic

Decision:

- Move VM profile synthesis, assignment resolution, policy matching, public-stream derivation, and VM fingerprint assessment into `beagle-host/services/vm_profile.py`.
- Keep the public helper names `should_use_public_stream()`, `build_public_stream_details()`, `resolve_assigned_target()`, `resolve_policy_for_vm()`, `assess_vm_fingerprint()`, and `build_profile()` in `beagle-host/bin/beagle-control-plane.py` as thin delegation wrappers so handlers and internal call sites stay stable during the migration.

Reason:

- After provider-backed read, state, and compliance services existed, the next large business block still living in the HTTP entrypoint was profile synthesis. Extracting it creates a clearer service boundary for installer/profile/fleet flows, reduces the size of the control-plane monolith again, and keeps the remaining provider-neutral contract work focused on response builders instead of another inlined metadata synthesis block.

### D31. Host-provider bootstrap belongs in a registry plus explicit contract, not in direct concrete imports

Decision:

- Add `beagle-host/providers/host_provider_contract.py` as the explicit host-provider contract that the control plane and host services code against.
- Add `beagle-host/providers/registry.py` as the single host-provider registry/factory and bootstrap `HOST_PROVIDER` in `beagle-host/bin/beagle-control-plane.py` through `BEAGLE_HOST_PROVIDER`.
- Remove the direct `ProxmoxHostProvider` import from the control-plane entrypoint; concrete providers stay behind the registry even while Proxmox remains the only real implementation.

Reason:

- The previous host refactors still left one architectural hard stop: the control-plane bootstrap directly imported the concrete Proxmox provider. That made every later provider-neutral slice start from a Proxmox-first entrypoint. Moving provider selection to a registry keeps current runtime behavior identical while making the host side follow the same provider-indirection pattern already introduced on the browser side.

### D32. HTTP response builders should move behind host services via lazy factories and delegating wrappers

Decision:

- Treat every remaining HTTP-facing aggregation/response-builder in `beagle-host/bin/beagle-control-plane.py` as a candidate for extraction into a dedicated `beagle-host/services/*.py` module.
- Each extracted service must take its collaborators (loaders, profile service, URL helpers, contract normalizer, provider contract, constants like version/service name) through a kwargs-only constructor and must not reach back into `beagle-control-plane.py` globals.
- `beagle-control-plane.py` keeps a module-level `SERVICE_NAME: Type | None = None` singleton plus a lazy `service_name_service()` factory and a thin delegating wrapper that preserves the original helper signature, so handler call sites and HTTP behavior stay stable across the migration.
- Start with builders whose inputs are already routed through existing seams (profile, inventory, provider contract, loaders); defer builders that still couple to inline subprocess/Proxmox logic until that coupling is removed first.

Reason:

- The control-plane entrypoint still owned multiple large response-builder blocks (update feed, fleet inventory, health payload, installer preset, endpoint report summarization) that were business logic, not HTTP plumbing. Extracting them one at a time keeps the migration reviewable, mirrors the pattern already proven by `VmProfileService`/`VmStateService`, and gives tests and future providers a stable DI seam without forcing every HTTP handler to change during the slice.

### D33. Public download/artifact URL and checksum shaping should be one host service

Decision:

- Move the public artifact URL helpers, latest-download resolution, SHA256 lookup, and `update_payload_metadata()` into `beagle-host/services/download_metadata.py`.
- Keep the old helper names in `beagle-host/bin/beagle-control-plane.py` as thin wrappers so existing handler/service call signatures stay stable while other extracted services are rewired to the new singleton gradually.

Reason:

- The update-feed, installer-script, fleet-inventory, and VM-profile services all depended on the same small cluster of public artifact helpers. Leaving those helpers inline in the control plane would keep a shared business rule block duplicated via wrapper injection instead of via one service seam. Extracting them creates a reusable host-side source of truth for public download URLs and checksums before the remaining credential/bootstrap logic is tackled.

### D34. VM-secret persistence and VM-secret bootstrap are separate host services

Decision:

- Keep `beagle-host/services/vm_secret_store.py` focused on JSON persistence only.
- Move `ensure_vm_secret`, Sunshine pinned-pubkey backfill, SSH keypair creation, USB-tunnel path/known-host helpers, and managed `authorized_keys` synchronization into `beagle-host/services/vm_secret_bootstrap.py`.
- Keep the old helper names in `beagle-host/bin/beagle-control-plane.py` as thin wrappers so enrollment, installer, USB, and provisioning flows continue to call the same surface during the migration.

Reason:

- VM-secret persistence and VM-secret bootstrap are different concerns. The first is stable file I/O; the second mixes credential generation, key material, filesystem side effects, and Sunshine/USB tunnel integration. Splitting them keeps the persistence service simple, gives the higher-level bootstrap logic its own DI seam, and removes one of the largest remaining non-HTTP helper clusters from the control-plane monolith.

### D35. Installer-prep state and Sunshine-readiness belong in one host service

Decision:

- Move installer-prep path helpers, state loading, quick Sunshine readiness probing, default/summary payload shaping, and background prep-script launch into `beagle-host/services/installer_prep.py`.
- Keep the old helper names in `beagle-host/bin/beagle-control-plane.py` as thin wrappers so HTTP handlers and `VmStateService` continue to call the same surface during the migration.

Reason:

- The installer-prep flow was a cohesive non-HTTP block: it shaped the same payload contract, read and wrote the same state files, performed the same guest-side Sunshine probe, and launched the same background script. Leaving that logic split across multiple helper functions in the control plane would keep the entrypoint responsible for state orchestration instead of request dispatch. Extracting it creates one host-side seam for installer readiness and removes another large helper cluster from the monolith.

### D36. Guest USB attach/detach and tunnel-state orchestration belong in one host service

Decision:

- Move usbip/vhci parsing, guest USB attachment polling, VM USB state shaping, and guest attach/detach orchestration into `beagle-host/services/vm_usb.py`.
- Keep `beagle-host/bin/beagle-control-plane.py` wrappers for `parse_usbip_port_output`, `parse_vhci_status_output`, `guest_usb_attachment_state`, `wait_for_guest_usb_attachment`, `build_vm_usb_state`, `attach_usb_to_guest`, and `detach_usb_from_guest` so the HTTP handlers under `/api/v1/vms/{vmid}/usb*` keep the same call surface during migration.
- Inject provider-backed guest-exec helpers, endpoint-report loading, VM-secret/tunnel metadata, time helpers, and shell quoting into the service constructor instead of letting the service reach into control-plane globals.

Reason:

- The USB block was the next cohesive non-HTTP cluster after installer-prep: it mixed guest probing, usbip parsing, endpoint USB inventory, tunnel-port lookup, and attach/detach orchestration in one entrypoint file. Extracting it keeps the provider boundary intact, removes another high-signal business block from the HTTP monolith, and makes the remaining host-side work more clearly about provisioning/lifecycle flows rather than USB runtime mechanics.

### D37. Ubuntu-Beagle provisioning and lifecycle orchestration belong in one host service

Decision:

- Move provisioning catalog assembly, storage resolution, ubuntu installer ISO caching/extraction, seed-ISO generation, metadata description shaping, finalize/firstboot flows, and ubuntu-beagle VM create/update logic into `beagle-host/services/ubuntu_beagle_provisioning.py`.
- Keep `beagle-host/bin/beagle-control-plane.py` wrappers for `build_provisioning_catalog`, `create_provisioned_vm`, `finalize_ubuntu_beagle_install`, `prepare_ubuntu_beagle_firstboot`, `create_ubuntu_beagle_vm`, and `update_ubuntu_beagle_vm` so the provisioning HTTP handlers and public ubuntu-install callbacks keep the same call surface during migration.
- Inject provider-backed VM operations, template/artifact paths, state/secret services, stream helpers, validation helpers, and timing helpers into the service constructor instead of letting the service reach into control-plane globals.

Reason:

- The ubuntu-beagle block was the largest remaining provisioning/lifecycle area in the entrypoint. It mixed catalog shaping, autoinstall artifact generation, provider-backed VM lifecycle operations, state persistence, and running-guest reconfiguration in one file. Extracting it removes another major business block from the HTTP monolith, keeps the control plane reviewable, and makes the remaining work focus on streaming/proxy and other runtime-specific seams instead of provisioning boilerplate.

### D38. Sunshine and Moonlight guest integration belong in one host service

Decision:

- Move pinned-pubkey retrieval, guest-side Sunshine user/config discovery, Moonlight certificate registration, Sunshine server identity discovery, Sunshine access-ticket issuance/resolution, and Sunshine HTTP proxying into `beagle-host/services/sunshine_integration.py`.
- Keep `beagle-host/bin/beagle-control-plane.py` wrappers for `fetch_https_pinned_pubkey`, `guest_exec_text`, `sunshine_guest_user`, `register_moonlight_certificate_on_vm`, `fetch_sunshine_server_identity`, `internal_sunshine_api_url`, `resolve_vm_sunshine_pinned_pubkey`, `issue_sunshine_access_token`, `sunshine_proxy_ticket_url`, and `proxy_sunshine_request`, and move handler-local ticket resolution to the same service.
- Inject provider-backed guest execution, token-store seams, VM lookup/profile/config helpers, subprocess execution, and public-manager URL shaping into the service constructor instead of letting the service reach into control-plane globals.

Reason:

- The streaming integration block was the next cohesive non-HTTP area after ubuntu-beagle provisioning. It mixed guest-side scripting, Sunshine metadata parsing, TLS pinned-pubkey discovery, access-ticket state, and HTTP proxy orchestration in the request entrypoint. Extracting it preserves current handler surfaces while making the Sunshine/Moonlight path explicit, testable, and easier to replace when Beagle gets its own virtualization/streaming provider path.

### D39. Public-stream port state and allocation belong in one host service

Decision:

- Move the persistent public-stream mapping file, explicit-port interpretation, stale-entry synchronization, used-port calculation, and next-free-port allocation into `beagle-host/services/public_streams.py`.
- Keep `beagle-host/bin/beagle-control-plane.py` wrappers for `public_streams_file`, `load_public_streams`, `save_public_streams`, `public_stream_key`, `explicit_public_stream_base_port`, `used_public_stream_base_ports`, and `allocate_public_stream_base_port` so `VmProfileService` and `UbuntuBeagleProvisioningService` keep their existing collaborator surface.
- Inject data-dir access, JSON load/save helpers, provider-backed VM/config lookups, public-stream host availability, and port-range constants into the service constructor instead of letting the service reach into control-plane globals.

Reason:

- The public-stream cluster was cohesive business logic, not HTTP plumbing: it owned a persistent mapping file, interpreted VM metadata, synchronized mappings against current inventory, and allocated collision-free port ranges. Leaving that logic in the entrypoint would keep stream-orchestration state mixed into the HTTP surface. Extracting it makes the port-allocation contract explicit and prepares the later provider-neutral streaming path for Beagle-owned virtualization.

### D40. Policy contract normalization belongs in one host service

Decision:

- Move policy selector/profile normalization, boolean/list/time shaping, and `assigned_target` normalization into `beagle-host/services/policy_normalization.py`.
- Keep `beagle-host/bin/beagle-control-plane.py` wrapper `normalize_policy_payload(...)` stable so policy CRUD handlers do not change surface while `PolicyStoreService` switches to the new service method internally.
- Inject only generic collaborators (`listify`, `truthy`, `utcnow`) into the service constructor instead of letting the service reach into control-plane globals.

Reason:

- Policy CRUD was already separated at the file-I/O layer, but the canonical contract still lived inline in the entrypoint. That kept selector/profile semantics undocumented in a reusable module and made future policy evolution depend on editing the HTTP monolith. Extracting the normalization layer gives policy contract semantics their own host-side seam without changing persisted shape or handler behavior.

### D41. Support-bundle upload shaping belongs in the existing store service

Decision:

- Expand `beagle-host/services/support_bundle_store.py` to own `store(...)` in addition to metadata/archive path lookup and listing.
- Keep `store_support_bundle(...)` in `beagle-host/bin/beagle-control-plane.py` as a thin wrapper so the VM action-result upload path keeps the same helper surface.
- Preserve current filename-sanitizing behavior during this slice, including the existing `.bin` fallback when the sanitized filename no longer has suffixes.

Reason:

- The remaining bundle-upload block was not a separate domain from the existing store service; it was the missing write half of the same persistence seam. Creating a second support-bundle service would have split one cohesive responsibility across two modules. Expanding the existing store service keeps archive-path logic, metadata lookup/listing, and upload persistence in one place while still removing the business block from the HTTP entrypoint.

### D42. Installer template patching belongs in its own host service

Decision:

- Move shell and Windows installer template rewrite logic into `beagle-host/services/installer_template_patch.py`.
- Keep `patch_installer_defaults(...)` and `patch_windows_installer_defaults(...)` in `beagle-host/bin/beagle-control-plane.py` only as thin wrappers so the existing helper surface stays stable during the migration.
- Let `InstallerScriptService` depend directly on `InstallerTemplatePatchService`, and move preset Base64 encoding fully into `InstallerScriptService` instead of keeping it in the entrypoint.

Reason:

- `InstallerScriptService` already owned the generated installer artifact flow, but the canonical template rewrite contract still lived inline in the control-plane entrypoint. That kept escaping rules and placeholder semantics detached from the service that actually renders those artifacts. Splitting out a dedicated patching service and moving preset encoding into `InstallerScriptService` closes the installer helper seam cleanly without changing generated output.

### D43. Ubuntu-Beagle input validation and preset expansion belong in one host service

Decision:

- Move ubuntu-beagle user/password/locale/keymap validation plus desktop/package preset normalization and package expansion into `beagle-host/services/ubuntu_beagle_inputs.py`.
- Keep the existing control-plane helper names as thin wrappers, but wire `UbuntuBeagleProvisioningService` and `VmProfileService` directly to the new service methods instead of to inline entrypoint helpers.

Reason:

- These helpers were no longer generic control-plane utilities; they defined the canonical ubuntu-beagle provisioning contract. Leaving them inline in the entrypoint kept provisioning semantics detached from the provisioning/profile services that consume them. Pulling them into one dedicated service makes the ubuntu-beagle input contract explicit and reusable without changing runtime behavior.

### D44. Queue orchestration belongs in the existing action-queue service

Decision:

- Expand `beagle-host/services/action_queue.py` to own `queue_action(...)`, `queue_bulk_actions(...)`, and `dequeue_actions(...)` in addition to queue/result path and I/O helpers.
- Keep `queue_vm_action`, `queue_bulk_actions`, and `dequeue_vm_actions` in `beagle-host/bin/beagle-control-plane.py` only as thin wrappers so handler behavior and payload shape remain unchanged.

Reason:

- The remaining queue block was not a separate concern from the existing action-queue service; it was the missing orchestration half of the same queue boundary. Creating a new service for timestamps/action IDs/bulk dedupe would have split one cohesive responsibility across modules. Expanding the existing service keeps queue file I/O, result storage, and queue orchestration in one place while shrinking the entrypoint further.

### D45. Runtime host resolution and manager pinning belong in one host service

Decision:

- Move `resolve_public_stream_host(...)`, `current_public_stream_host()`, and `manager_pinned_pubkey()` into `beagle-host/services/runtime_environment.py`.
- Keep the existing control-plane helper names as thin wrappers so downstream handlers and service factories keep their current surface while the runtime/environment logic leaves the entrypoint.
- Let the service own manager-cert-file lookup, OpenSSL pubkey hashing, public-host DNS resolution, and pinned-pubkey caching through injected runtime collaborators instead of re-reading globals directly in the entrypoint.

Reason:

- These helpers were a small but cohesive runtime block used by multiple host services. Leaving them inline in the entrypoint kept TLS pinning and public-host resolution as module-level state instead of an explicit seam. Extracting them makes the runtime assumptions testable and documented without changing current behavior.

### D46. Action-result waiting belongs in the existing action-queue service

Decision:

- Expand `beagle-host/services/action_queue.py` to own `wait_for_result(node, vmid, action_id, timeout_seconds=...)` in addition to queue/result path lookup, queue orchestration, result persistence, and result summarization.
- Keep `wait_for_action_result(...)` in `beagle-host/bin/beagle-control-plane.py` only as a thin wrapper so USB retry handlers and other callers keep the same helper surface.

Reason:

- The result-wait loop is not a separate domain from queue/result persistence; it depends directly on the same result-file contract and action-id semantics already owned by `ActionQueueService`. Expanding the existing service avoids another tiny helper module, makes the timing behavior injectable for tests, and keeps one cohesive action-queue boundary.

### D47. Endpoint enrollment and bootstrap belong in one host service

Decision:

- Move installer enrollment-token issuance plus `/api/v1/endpoints/enroll` bootstrap/config payload shaping into `beagle-host/services/endpoint_enrollment.py`.
- Keep `issue_enrollment_token(...)` in `beagle-host/bin/beagle-control-plane.py` only as a thin wrapper so `InstallerScriptService` and other callers keep their current collaborator surface.
- Let the service compose `build_profile`, VM-secret bootstrap, token-store seams, Sunshine pinned-pubkey backfill, manager pinning, and USB-tunnel config shaping instead of leaving those concerns inline in the HTTP entrypoint.

Reason:

- The enrollment flow had become the next cohesive non-HTTP block: token TTL math, thin-client password lookup, endpoint-token issuance, endpoint bootstrap config assembly, and secret/pinned-pubkey reconciliation were all still coupled directly to the entrypoint. Extracting them makes the endpoint bootstrap contract explicit, testable, and reusable for future non-Proxmox provisioning surfaces.

### D48. Ubuntu-beagle scheduled restart state belongs in one host service

Decision:

- Move scheduled ubuntu-beagle restart scheduling, running-state checks, and cancellation into `beagle-host/services/ubuntu_beagle_restart.py`.
- Keep `schedule_ubuntu_beagle_vm_restart(...)` and `cancel_scheduled_ubuntu_beagle_vm_restart(...)` in `beagle-host/bin/beagle-control-plane.py` only as thin wrappers, and add `ensure_ubuntu_beagle_vm_restart_state(...)` as the thin provisioning-facing wrapper.
- Let `UbuntuBeagleProvisioningService` depend on the restart service seam for host-restart state reuse/reschedule behavior instead of inspecting `host_restart` PIDs inline.

Reason:

- Restart scheduling was already a host-provider responsibility, but the stateful orchestration around reusing a live restart PID and cancelling the scheduled restart still lived split between the HTTP entrypoint and the provisioning service. Pulling that logic into one host service gives the ubuntu-beagle restart contract one explicit seam and removes direct process-group handling from the entrypoint.

### D49. Cache and shell-env helpers belong in one host runtime-support service

Decision:

- Move `cache_get(...)`, `cache_put(...)`, `cache_invalidate(...)`, and `load_shell_env_file(...)` into `beagle-host/services/runtime_support.py`.
- Keep the existing control-plane helper names as thin wrappers so provider bootstrap, CORS-origin caching, and default-credential loading keep their current surface while the in-memory cache and shell-env parsing leave the entrypoint.
- Let the service own the in-memory cache map and monotonic-time dependency instead of keeping module-local cache state in `beagle-host/bin/beagle-control-plane.py`.

Reason:

- After restart extraction, the remaining cache/env helpers were the next cohesive non-HTTP utility block. They were shared by provider bootstrap and host services but still carried hidden module-local state in the entrypoint. Extracting them makes the runtime utility seam explicit and testable without changing current behavior.

### D50. Command wrappers belong in one host runtime-exec service

Decision:

- Move `run_json(...)`, `run_text(...)`, and `run_checked(...)` into `beagle-host/services/runtime_exec.py`.
- Keep the existing control-plane helper names as thin wrappers so host-provider bootstrap and existing services keep their current surface while subprocess timeout/default handling leaves the entrypoint.
- Let the service own default-timeout normalization around the existing sentinel plus the shared `subprocess.run(... capture_output ...)` behavior instead of duplicating that logic inline.

Reason:

- After the cache/env slice, the remaining command wrappers were the next cohesive non-HTTP utility block. They were already a shared runtime seam for provider bootstrap and other helpers, but they still duplicated subprocess boilerplate directly in the entrypoint. Extracting them makes host command execution behavior explicit and testable without changing runtime semantics.

### D51. File/JSON persistence belongs in one host persistence-support service

Decision:

- Move `load_json_file(path, fallback)` and `write_json_file(path, payload, mode=...)` into `beagle-host/services/persistence_support.py`.
- Keep the existing control-plane helper names as thin wrappers so the extracted host services keep their current collaborator surface while shared JSON/file persistence leaves the entrypoint.
- Let the service own parent-directory creation, pretty JSON output, trailing newline behavior, and best-effort chmod semantics instead of duplicating those persistence assumptions inline.

Reason:

- After the runtime-support and runtime-exec slices, the remaining file/JSON helpers were the next cohesive non-HTTP utility block. Multiple extracted services already depended on that seam indirectly, but the persistence behavior was still hidden inside the entrypoint. Extracting it makes the persistence contract explicit and testable without changing current runtime behavior.

### D52. Bearer-token, origin, and CORS helper logic belongs in one host request-support service

Decision:

- Move `extract_bearer_token(...)`, `normalized_origin(...)`, and `cors_allowed_origins()` into `beagle-host/services/request_support.py`.
- Keep the existing control-plane helper names as thin wrappers so HTTP handlers keep their current surface while request/origin policy leaves the entrypoint.
- Let the service own `cors-allowed-origins` cache usage plus manager/web/stream/custom origin synthesis instead of rebuilding that request-policy logic inline in `beagle-control-plane.py`.

Reason:

- Once file/JSON persistence was extracted, the remaining bearer/origin/CORS block became the next cohesive non-HTTP request utility seam. It was still directly coupled to global runtime values and cache helpers in the entrypoint, even though its behavior is shared request policy rather than handler-specific business logic. Extracting it makes the request-support contract explicit and testable without changing current CORS or auth semantics.

### D53. UTC timestamp helpers belong in one host time-support service

Decision:

- Move `utcnow()`, `parse_utc_timestamp(value)`, and `timestamp_age_seconds(value)` into `beagle-host/services/time_support.py`.
- Keep the existing control-plane helper names as thin wrappers so existing service collaborators keep their current surface while shared timestamp logic leaves the entrypoint.
- Let the service own the injected clock used for ISO timestamp generation and age calculation instead of reaching directly into `datetime.now(...)` from module-local helpers.

Reason:

- After request-support extraction, the remaining timestamp helpers were the next cohesive non-HTTP utility block. They were already a shared contract across many extracted services, but the actual parsing and age semantics still lived inline in the entrypoint. Extracting them makes the time contract explicit and testable without changing runtime timestamp behavior.

### D54. Runtime data-root and managed subdirectories belong in one host runtime-paths service

Decision:

- Move `ensure_data_dir()`, `endpoints_dir()`, `actions_dir()`, `support_bundles_dir()`, and `policies_dir()` into `beagle-host/services/runtime_paths.py`.
- Keep the existing control-plane helper names as thin wrappers so callers keep their current surface while data-root and managed-directory creation leave the entrypoint.
- Rebind service factories that previously captured `EFFECTIVE_DATA_DIR` to `runtime_paths_service().data_dir` so the resolved data root lives behind one explicit seam instead of a mutable module-global.

Reason:

- Once file/JSON persistence and request-support logic were extracted, the remaining data-root/bootstrap block became the next cohesive runtime seam. It still carried fallback-path selection, mkdir/chmod behavior, and managed-directory naming directly in the entrypoint. Extracting it makes path behavior explicit and testable while reducing global state in the host bootstrap path.

### D55. Remaining Proxmox UI fleet/provisioning orchestration belongs in dedicated state/provisioning modules

Decision:

- Move the remaining fleet-data loading block out of `proxmox-ui/beagle-ui.js` into `proxmox-ui/state/fleet.js`.
- Move the remaining provisioning result/create-modal orchestration block out of `proxmox-ui/beagle-ui.js` into `proxmox-ui/provisioning/flow.js`.
- Keep `beagle-ui.js` focused on dependency lookup, thin browser action wrappers, modal dispatch, and `boot()` instead of rebuilding collaborator graphs for fleet/provisioning flows inline.

Reason:

- `beagle-ui.js` was already much smaller than before, but the last meaningful non-bootstrap logic left in the file was still fleet loading and provisioning flow orchestration. Those blocks already depended on modules that existed elsewhere, so keeping them in the entrypoint would only preserve a thin monolith shell instead of a real composition surface.

### D56. Script-side provider reads need a shared helper seam before broader script migration

Decision:

- Introduce `scripts/lib/beagle_provider.py` as the first provider-facing helper for script-side virtualization reads.
- Move script read paths such as VM inventory, VM config lookup, and guest-interface lookup onto that helper before touching more mutation-heavy script flows.
- Keep the helper provider-neutral at the interface level and let it normalize `pve` to `proxmox`, even though Proxmox is still the only concrete script backend today.

Reason:

- Several scripts had already started to repeat the same raw `pvesh` and `qm guest cmd` calls inside inline Python blocks. Migrating every script independently would hard-code Proxmox deeper into shell/runtime surfaces. A shared helper gives the script layer one place to evolve toward a second provider or a mock backend without rewriting each script separately.

### D57. Browser-wide token/template/API helpers belong in one shared browser module

Decision:

- Introduce `core/platform/browser-common.js` as the shared browser utility seam for the Proxmox UI, browser extension, and website surfaces.
- Move repeated session-token store creation, URL template filling, cache-busting URL decoration, manager-URL derivation, Beagle-API path normalization, base/path joining, and `beagle_token` hash injection behind that shared module.
- Keep surface-specific config/default lookup in the existing entry modules, but stop recreating the same generic browser helper logic in each surface.

Reason:

- After the Proxmox UI entrypoint shrank, the next browser-side duplication hotspot was no longer rendering but repeated token/template/API helper code across `proxmox-ui/beagle-ui-common.js`, `extension/common.js`, and `website/app.js`. Leaving that duplication in place would keep three browser surfaces drifting independently on the same runtime contract.

### D58. Proxy-installer backend detection should use the shared script provider read seam

Decision:

- Move `scripts/install-beagle-proxy.sh` backend-detection reads for guest interfaces, VM descriptions/config, and VM enumeration behind `scripts/lib/beagle_provider.py`.
- Keep the migration read-only for now and leave write/mutation flows for a later helper expansion.

Reason:

- `install-beagle-proxy.sh` had become another place where raw `qm` reads would spread Proxmox assumptions through installer/runtime surfaces. Using the shared script helper keeps backend auto-detection on the same provider-facing seam already adopted by the other migrated scripts.

### D59. Shared slug/secret/PIN helpers belong in one host utility-support service

Decision:

- Move `safe_slug(...)`, `random_secret(...)`, and `random_pin()` into `beagle-host/services/utility_support.py`.
- Keep the existing control-plane helper names as thin wrappers so handlers and already-extracted services keep their current call surface while the pure utility logic leaves the entrypoint.
- Rebind extracted host services directly to `utility_support_service()` where practical instead of keeping them attached to monolith-local helper implementations.

Reason:

- After the time/runtime-path/request/persistence extractions, the remaining slug/secret/PIN helpers were the last small pure utility cluster still shared across many extracted services but still implemented inline in `beagle-control-plane.py`. Pulling them behind a dedicated service keeps that behavior explicit and testable without changing runtime payloads or file naming semantics.

### D60. Script-side provider reads should grow into higher-level shared helpers, not repeated inline metadata parsing

Decision:

- Expand `scripts/lib/beagle_provider.py` with higher-level read helpers such as description-meta parsing, VM-record lookup, and first guest IPv4 resolution.
- Migrate scripts to import those helpers instead of carrying their own inline Python implementations for the same metadata and guest-interface logic.
- Keep this seam read-only for now; guest-exec and write semantics remain a separate follow-up contract decision.

Reason:

- Once several scripts already used the first provider helper, the next duplication hotspot was no longer raw command invocation alone but repeated parsing of the same provider-backed VM description and guest-interface payloads. Growing the shared helper keeps behavior aligned across scripts and prevents the script layer from becoming a second place where provider-specific metadata rules drift apart.

### D61. Remote host scripts should prefer the installed provider helper but preserve direct-command fallback

Decision:

- `scripts/configure-sunshine-guest.sh` should use the installed/shared provider helper on the target host for read-only VM lookups such as guest IPv4 and VM description retrieval.
- The script should resolve that helper path explicitly, defaulting to the repo-local helper for localhost targets and `/opt/beagle/scripts/lib/beagle_provider.py` for remote installed hosts.
- The script must keep the existing direct `qm guest cmd` / `qm config` read path as a fallback when the helper is unavailable or outdated so operator behavior does not regress on partially updated hosts.

Reason:

- `configure-sunshine-guest.sh` is one of the remaining places where provider-specific reads still lived behind ad-hoc SSH-wrapped `qm` calls. Reusing the installed helper keeps host-side script reads on the same abstraction path as the other migrated scripts, but the fallback is necessary because this script may run against hosts that have not yet been updated to the newest helper version.

### D62. Script-side guest-exec and VM-write flows should use the same provider helper seam

Decision:

- Extend `scripts/lib/beagle_provider.py` beyond read-only calls so scripts can also route guest execution, VM option writes, description updates, and VM reboot requests through one provider-facing helper.
- Use base64-encoded payload arguments for script-side guest commands and multi-line descriptions where shell quoting would otherwise be brittle.
- Keep direct `qm` fallbacks in the calling scripts only where rollout compatibility with not-yet-updated remote hosts still matters.

Reason:

- After the read migration, the remaining repeated script-side Proxmox coupling was concentrated in `qm guest exec`, `qm guest exec-status`, `qm set`, and `qm reboot` flows. Leaving those inlined across multiple scripts would simply recreate the same provider sprawl in mutation-heavy code. Moving them behind the helper creates one script-side provider seam for both reads and the first controlled writes while keeping deployment safety through explicit fallbacks.

### D63. VM description parsing and hostname normalization belong in one host metadata-support service

Decision:

- Move `parse_description_meta(description)` and `safe_hostname(name, vmid)` into `beagle-host/services/metadata_support.py`.
- Keep the control-plane helper names as thin wrappers so the public host composition surface stays stable while extracted services bind directly to the new metadata seam.
- Use the service as the single injected source for description-meta parsing and host-name derivation in `PublicStreamService`, `SunshineIntegrationService`, `VmProfileService`, `InstallerScriptService`, and `UbuntuBeagleProvisioningService`.

Reason:

- After the runtime, utility, and script-helper slices, the remaining small but high-fanout host helper block still sitting in `beagle-control-plane.py` was the VM description/hostname logic. Those semantics are shared business helpers used by multiple extracted services, not HTTP-entrypoint behavior. Pulling them into a dedicated service removes another monolith-local dependency without changing payloads or naming rules.

### D64. VM detail/download HTTP payload shaping belongs in one host VM HTTP-surface service

Decision:

- Move the inline `/api/v1/vms/...` GET route-matching, payload-envelope shaping, and installer-download response descriptors into `beagle-host/services/vm_http_surface.py`.
- Keep `beagle-control-plane.py` responsible only for request dispatch and final response writing for that route family.
- Let the new service compose the already-extracted collaborators (`VmStateService`, `VmProfileService`, `InstallerScriptService`, `InstallerPrepService`, `VmUsbService`, support-bundle store, endpoint report, and VM-secret bootstrap) instead of reassembling those payloads inside the HTTP entrypoint.

Reason:

- After the utility and metadata helper extractions, the next meaningful block left in the host monolith was no longer a tiny shared helper but the full `/api/v1/vms/...` GET response surface. That code already depended mostly on extracted services, but the HTTP entrypoint still owned route matching, payload envelopes, and download descriptors. Pulling that block behind one dedicated service removes a large handler-local business surface in one step and pushes the control plane closer to a thin composition layer without changing the public API.

### D65. The next non-VM read routes belong in a second control-plane read-surface service

Decision:

- Move the non-VM GET response cluster for `provisioning/catalog`, `provisioning/vms/<vmid>`, `endpoints`, `policies`, `policies/<name>`, and `support-bundles/<bundle_id>/download` into `beagle-host/services/control_plane_read_surface.py`.
- Keep `beagle-control-plane.py` responsible only for dispatching that route family and writing the returned JSON or byte response.
- Let the new service compose the already-extracted provisioning, endpoint-report, policy-store, and support-bundle-store seams instead of keeping those HTTP envelopes and download descriptors in the entrypoint.

Reason:

- After extracting the VM HTTP surface, the next coherent block in the host monolith was the remaining non-VM read surface. Those routes were already mostly thin wrappers around extracted services, but the entrypoint still owned route matching, `generated_at` envelopes, and archive-download response descriptors. Pulling them behind a second dedicated HTTP service keeps the decomposition pattern consistent and reduces the monolith without inventing another tiny utility slice.

### D66. Public VM state and endpoint-authenticated update-feed belong in one public HTTP-surface service

Decision:

- Move the public VM read routes for `public/vms/<vmid>/state`, `public/vms/<vmid>/endpoint`, and the explicitly forbidden public installer-download endpoints into `beagle-host/services/public_http_surface.py`.
- Fold the endpoint-authenticated `/api/v1/endpoints/update-feed` response shaping into the same service because it is the same public/endpoint-facing contract family and already composes the extracted `VmStateService`, `VmProfileService`, and `UpdateFeedService`.
- Keep `beagle-control-plane.py` responsible only for the auth gate and final response writing for that route family.

Reason:

- After the VM and non-VM read slices, the remaining GET logic in the entrypoint was concentrated in the public VM state surface and the endpoint-authenticated update-feed path. Those routes share the same external-facing contract boundary and were still mostly envelope/orchestration code around extracted services. Moving them together keeps the HTTP-surface extraction pattern coherent and removes another meaningful handler block without changing public behavior.

### D67. Public ubuntu-install lifecycle POST routes belong in one dedicated public install surface

Decision:

- Move the public ubuntu-install lifecycle POST routes for `complete`, `prepare-firstboot`, and `failed` into `beagle-host/services/public_ubuntu_install_surface.py`.
- Keep `beagle-control-plane.py` responsible only for the optional JSON-body read on the `failed` route and for writing the final HTTP response.
- Let the new service compose the already-extracted ubuntu-beagle provisioning, ubuntu-beagle state persistence, and scheduled-restart cancellation seams instead of mutating install-state payloads inline in the entrypoint.

Reason:

- After the public GET surface moved out, the next cohesive external-facing POST block was the ubuntu-install lifecycle. Those routes all operate on the same public token/state contract and were still mostly state mutation plus response-envelope code around extracted services. Pulling them behind one dedicated surface keeps the decomposition consistent and shrinks the monolith without changing the installer-facing API.

### D68. Endpoint-authenticated action/result/upload and Moonlight registration belong in one endpoint HTTP surface

Decision:

- Move the endpoint-authenticated POST routes for Moonlight registration, action pull/result, and support-bundle upload into `beagle-host/services/endpoint_http_surface.py`.
- Keep `beagle-control-plane.py` responsible only for the endpoint-auth gate plus generic JSON/binary body reads before handing off to the service.
- Let the new service own endpoint scope validation, response envelopes, and the composition of the existing action queue, support-bundle store, Sunshine integration, and VM lookup seams.

Reason:

- After the public-install lifecycle left the entrypoint, the next coherent POST cluster was the endpoint-facing runtime contract used by enrolled clients. Those routes already depended on extracted services but still duplicated scope checks, envelope shaping, and per-route validation inside the HTTP entrypoint. Pulling them together behind one endpoint surface keeps the decomposition pattern consistent and meaningfully shrinks the monolith without changing endpoint behavior.

### D69. The public Sunshine proxy belongs in its own dedicated streaming surface

Decision:

- Move the public Sunshine GET/POST proxy flow into `beagle-host/services/public_sunshine_surface.py`.
- Let that service own ticket resolution, proxy dispatch, and the distinction between proxied downstream responses and JSON error payloads.
- Keep `beagle-control-plane.py` responsible only for generic proxy response writing and, on POST, the binary-body read before delegating to the service.

Reason:

- After the other public and endpoint-facing surfaces were extracted, the remaining public streaming block was the Sunshine proxy. That logic was still duplicated between `do_GET` and `do_POST` and was already entirely defined by the existing Sunshine integration seam. Pulling it behind its own service removes the last public streaming block from the HTTP entrypoint without changing the external proxy contract.

### D70. Authenticated single-VM mutation routes belong in one VM mutation surface

Decision:

- Move the authenticated single-VM mutation POST routes for installer-prep start, OS update queueing, generic VM actions, USB refresh/attach/detach, and Sunshine access-ticket issuance into `beagle-host/services/vm_mutation_surface.py`.
- Keep `beagle-control-plane.py` responsible only for the auth gate plus required/optional JSON-body reads before handing off to the service.
- Let the new service own route matching, action mapping, queueing, USB attach/detach orchestration, and response envelopes on top of the already-extracted `ActionQueueService`, `InstallerPrepService`, `VmUsbService`, and Sunshine integration seams.

Reason:

- After extracting the public and endpoint-facing surfaces, the next coherent block left in the entrypoint was the authenticated per-VM mutation surface. Those routes were already mostly orchestration across extracted services but still duplicated VM lookup, queueing, USB attach/detach sequencing, and response shaping inline. Pulling them together behind one mutation surface removes another large block from the HTTP entrypoint without changing the authenticated API contract.

### D71. Remaining authenticated non-VM writes and endpoint lifecycle routes should leave the entrypoint as dedicated HTTP surfaces

Decision:

- Move the authenticated non-VM admin mutation routes for policy create/update/delete, bulk action queueing, ubuntu-beagle creation, provisioning create, and provisioning update into `beagle-host/services/admin_http_surface.py`.
- Move the remaining endpoint lifecycle HTTP routes for enrollment and endpoint check-in into `beagle-host/services/endpoint_lifecycle_surface.py`.
- Extend `beagle-host/services/endpoint_report.py` with a dedicated `store(...)` seam so endpoint report persistence no longer writes JSON files directly from `beagle-control-plane.py`.
- Keep `beagle-control-plane.py` responsible only for auth gates, generic JSON-body reads, and final response writing for these route families.

Reason:

- After the VM mutation surface extraction, the largest handler-local blocks left in the control-plane entrypoint were the remaining admin-facing non-VM write routes and the endpoint enrollment/check-in lifecycle routes. They were already mostly orchestration around extracted services, but the HTTP entrypoint still owned route matching, validation, error mapping, and response envelopes. Pulling both route families behind dedicated surfaces keeps the decomposition pattern consistent, removes the last major inline HTTP mutation blocks, and leaves the next host refactor target as non-HTTP business/orchestration logic rather than more route glue.

### D72. Script-side guest-exec polling belongs in the shared provider helper, not in each shell script

Decision:

- Extend `scripts/lib/beagle_provider.py` with a synchronous guest-exec helper and CLI entrypoint that hides the `qm guest exec` plus `qm guest exec-status` polling loop behind the script-side provider seam.
- Update `configure-sunshine-guest.sh` and `ensure-vm-stream-ready.sh` to prefer that synchronous helper instead of carrying their own provider-specific polling logic.
- Keep direct `qm` fallbacks only as compatibility branches for partially updated hosts or missing helper deployments.

Reason:

- The first script-provider slice already moved read paths and low-level exec/write commands behind `scripts/lib/beagle_provider.py`, but the shell scripts still duplicated the provider-specific polling and raw-payload parsing needed to turn guest exec into a synchronous result. That kept Proxmox execution semantics spread across multiple scripts. Moving the wait loop into the helper keeps the provider contract explicit, reduces duplicate shell logic, and narrows the remaining direct `qm` compatibility paths.

### D73. Host-provider registry and deploy/runtime env should be provider-aware before a second provider exists

Decision:

- Convert `beagle-host/providers/registry.py` from direct concrete-provider imports to lazy module loading through registry metadata.
- Persist `BEAGLE_HOST_PROVIDER` through the host install/runtime env files and the related refresh/check surfaces instead of treating provider selection as an in-process control-plane detail only.
- Keep the current concrete implementation as Proxmox, but make the bootstrap path ready for an additional provider or test provider without reworking import wiring and host env propagation first.

Reason:

- Provider-neutrality is not real if the control plane can choose a provider but the surrounding install/runtime surfaces silently assume one concrete backend and the registry itself directly imports that backend at module import time. Lazy loading plus persisted provider selection reduces that coupling now and lowers the cost of introducing `providers/beagle/` or a conformance mock later.

### D74. Proxmox-specific install adapters should stay explicit, but they must read the selected provider and skip cleanly when mismatched

Decision:

- Keep scripts such as `install-proxmox-ui-integration.sh` and `install-proxmox-host.sh` explicit about being Proxmox adapters instead of hiding provider-specific behavior behind generic names too early.
- Make those scripts read the active `BEAGLE_HOST_PROVIDER`, propagate it through their env files, and skip or log clearly when the selected provider is not `proxmox`.
- Make the server-installer bootstrap pass the provider selection explicitly rather than relying on the current default.

Reason:

- These install surfaces are still genuinely Proxmox-specific today, so pretending they are already generic would only hide coupling. The right intermediate state is explicit adapter naming plus explicit provider selection, so future non-Proxmox install paths can coexist without another round of implicit-default cleanup first.

### D75. Hosted download preparation should move behind a dedicated helper and reuse the endpoint profile contract for overlapping VM installer metadata

Decision:

- Move the non-shell artifact patching, VM installer catalog generation, and downloads-status JSON shaping out of `scripts/prepare-host-downloads.sh` into `scripts/lib/prepare_host_downloads.py`.
- Reuse `beagle-host/services/installer_template_patch.py` for the hosted installer/live-USB/Windows template rewrite path instead of carrying another local patch implementation inside the shell script.
- Normalize the overlapping VM installer/profile URL fields through `beagle-host/bin/endpoint_profile_contract.py` when generating `beagle-vm-installers.json`, while deliberately preserving the existing preset semantics that the hosted-download path already exposed.

Reason:

- `prepare-host-downloads.sh` had become one of the remaining large script monoliths because it embedded several separate inline Python programs for template patching, VM metadata shaping, and status JSON generation. That made the shell entrypoint harder to review and kept installer/profile contract logic detached from the explicit host-side contract module. Pulling the Python work behind a dedicated helper preserves behavior, shrinks the shell script materially, and makes the next installer/env-builder contract slice narrower and easier to reason about.

### D76. Thin-client preset summary and UI-state shaping should live in one shared USB helper

Decision:

- Add `thin-client-assistant/usb/preset_summary.py` as the shared source for streaming-mode availability, preset summary JSON, debug payload shaping, and local-installer UI-state payloads.
- Reuse that helper from both `thin-client-assistant/usb/pve-thin-client-proxmox-api.py` and `thin-client-assistant/usb/pve-thin-client-local-installer.sh` instead of keeping separate inline Python blocks and separate availability rules.
- Keep the higher-level Proxmox preset assembly unchanged for now; this slice only centralizes the derived summary/view logic.

Reason:

- The remaining installer/env-builder drift was no longer only on the host side. The thin-client USB path still carried duplicated `available_modes` and preset-summary logic in both the Proxmox API helper and the local installer shell script. Moving the derived summary/view layer behind one helper reduces drift immediately, narrows the next preset-builder slice, and keeps the user-facing installer JSON surfaces stable.

### D77. Runtime enrollment-response config writes should leave prepare-runtime.sh

Decision:

- Move the endpoint-enrollment response mapping and file-write logic out of `thin-client-assistant/runtime/prepare-runtime.sh` into `thin-client-assistant/runtime/apply_enrollment_config.py`.
- Keep the helper focused on applying the current payload contract to `thinclient.conf`, `credentials.env`, `usb-tunnel.key`, and `usb-tunnel-known_hosts` without changing the contract itself.
- Let `prepare-runtime.sh` stay responsible for the enroll HTTP call and subsequent sourcing/reload behavior only.

Reason:

- The runtime entrypoint still embedded a large inline Python writer for the enrollment response payload. That made one of the remaining runtime/env-builder contracts effectively undocumented in code structure and harder to align with future installer/runtime contract work. Extracting the writer keeps behavior stable, shrinks the shell entrypoint, and creates a dedicated seam for the next round of shared runtime-config normalization.

### D78. Thin-client runtime status files should be written through one helper, not separate shell implementations

Decision:

- Add `thin-client-assistant/runtime/status_writer.py` as the shared writer for `launch.status.json` and `runtime.status`.
- Update `launch-session.sh` and `prepare-runtime.sh` to delegate file generation to that helper while preserving the existing payload/file shapes.
- Keep the shell scripts responsible for deciding values such as `binary_available`; the helper only owns timestamping and file serialization.

Reason:

- The runtime path still had two separate status-write implementations: one inline Python JSON writer in `launch-session.sh` and one shell-assembled key/value writer in `prepare-runtime.sh`. They were small individually but duplicated the same “derive runtime metadata then serialize it” seam. Centralizing the write contract removes more shell/JSON mixing and makes later runtime-observability changes one-module work.

### D79. Preset-to-runtime config generation should leave common.sh

Decision:

- Move the preset-file parsing plus preset→installer-env mapping out of `thin-client-assistant/runtime/common.sh` into `thin-client-assistant/runtime/generate_config_from_preset.py`.
- Keep `thin-client-assistant/installer/write-config.sh` as the canonical writer for the generated config directory; the new helper only owns preset parsing and env shaping before that call.
- Keep `generate_config_dir_from_preset()` in `common.sh` as a thin wrapper so the existing shell call sites stay stable.

Reason:

- After the shared preset summary, enrollment writer, and status writer slices, the largest remaining installer/runtime drift block was the huge preset→runtime env export cluster inside `generate_config_dir_from_preset()`. That logic was real business mapping, not shell orchestration. Extracting it makes the mapping explicit, keeps the existing output stable, and narrows the remaining runtime work to defaults/override behavior instead of another giant inline export chain.

### D80. Proxmox USB preset assembly should be isolated from the Proxmox API transport layer

Decision:

- Move the Proxmox-specific endpoint normalization, login parsing, description-meta parsing, and USB preset assembly out of `thin-client-assistant/usb/pve-thin-client-proxmox-api.py` into `thin-client-assistant/usb/proxmox_preset.py`.
- Keep `pve-thin-client-proxmox-api.py` responsible for HTTPS/API transport, VM enumeration, and command dispatch only.
- Keep the generated preset and CLI payload shapes stable so downstream installer flows do not change during the slice.

Reason:

- The API helper still mixed two different responsibilities: talking to Proxmox and defining the Proxmox-shaped thin-client preset contract. That made the remaining provider-specific contract harder to compare against the host-side installer builder and harder to replace later. Pulling the preset builder into its own module makes the Proxmox seam explicit without changing behavior.

### D81. Script-side provider bootstrap belongs in one shared shell helper, not copied across each Proxmox-facing script

Decision:

- Add `scripts/lib/provider_shell.sh` as the shared shell seam for local-vs-remote host detection, provider-module path resolution, provider-helper availability checks, remote helper execution, and raw-output JSON-object extraction.
- Rewire `scripts/configure-sunshine-guest.sh`, `scripts/optimize-proxmox-vm-for-beagle.sh`, and `scripts/ensure-vm-stream-ready.sh` to delegate that plumbing to the shared shell helper instead of carrying private copies.
- Keep the remaining direct `qm` fallback branches intact for now; this slice removes duplicated bootstrap/plumbing, not the compatibility behavior itself.

Reason:

- The script-provider abstraction had already moved reads, writes, and synchronous guest-exec polling into `scripts/lib/beagle_provider.py`, but the surrounding shell scripts still duplicated the mechanics for deciding whether the helper exists locally or remotely, how to run it over SSH, and how to recover the final JSON payload from noisy command output. That kept the provider boundary spread across several scripts and made later fallback cleanup harder. Centralizing that shell-side plumbing makes the next script refactor slices smaller and reduces the chance of reintroducing slightly different provider bootstrap logic in yet another script.

### D82. The overlapping thin-client preset base belongs in one shared host-side helper, with host-only and USB-only deltas layered on top

Decision:

- Add `beagle-host/services/thin_client_preset.py` as the shared source for the overlapping thin-client preset base fields used by both `beagle-host/services/installer_script.py` and `thin-client-assistant/usb/proxmox_preset.py`.
- Keep only the truly shared Proxmox/network/transport/Moonlight/Sunshine base fields in that helper and let each caller add its own delta fields:
  - host installer path keeps enrollment/update/egress/identity/credential/server-identity fields local
  - USB Proxmox path keeps only its local manager-token delta
- Also move the shared `available_modes(...)` input shaping behind the same helper so the USB path no longer reconstructs that mapping manually from raw preset keys.

Reason:

- The remaining installer/env-builder drift was no longer about completely separate builders; it was concentrated in a wide overlapping preset base that both sides maintained with near-identical key names and defaults. Extracting only that shared base reduces contract drift materially without falsely pretending that the richer host installer and the slimmer USB preset are already the same artifact. This keeps behavior stable while making the next remaining drift narrower and easier to reason about.

### D83. Installer/runtime default literals should come from one data contract for both shell and Python paths

Decision:

- Add `thin-client-assistant/installer/env-defaults.json` as the shared source of truth for installer/runtime environment defaults.
- Add `thin-client-assistant/installer/env-defaults.sh` as the shell-side loader for that data contract.
- Rewire `thin-client-assistant/runtime/generate_config_from_preset.py`, `thin-client-assistant/installer/write-config.sh`, `thin-client-assistant/installer/install.sh`, and `thin-client-assistant/installer/setup-menu.sh` to read defaults from that shared contract instead of keeping parallel literal blocks.
- Keep menu-only example placeholders such as `proxmox.example.internal`, `pve01`, `100`, and the demo PIN local to `setup-menu.sh` so interactive UX hints remain explicit and do not silently redefine the base runtime/install contract.

Reason:

- After extracting the preset builder seams, the next source of contract drift was the repeated default table for installer/runtime environment variables across one Python helper and several shell entrypoints. That duplication was large, low-signal, and easy to let drift. Moving the defaults into a data contract removes another broad literal block, keeps behavior stable for the runtime/install paths, and narrows the remaining runtime work to explicit mode/cmdline override behavior instead of scattered default values.

### D84. Runtime mode/cmdline override semantics should live in a dedicated helper, not inline in common.sh

Decision:

- Add `thin-client-assistant/runtime/mode_overrides.py` as the dedicated helper for:
  - reading `pve_thin_client.client_mode` from the kernel cmdline
  - mapping it onto `PVE_THIN_CLIENT_MODE`
  - deriving the resulting `PVE_THIN_CLIENT_BOOT_PROFILE`
  - preserving the existing `PVE_THIN_CLIENT_CLIENT_MODE` value when no cmdline override is present
- Rewire `apply_runtime_mode_overrides()` in `thin-client-assistant/runtime/common.sh` into a thin shell wrapper that only applies the helper output.
- Leave the rest of runtime config discovery and preset restoration in `common.sh` for now.

Reason:

- After the shared default contract moved out, the next real business block left in the runtime shell monolith was the cmdline-driven mode override mapping. It was small, but it defined real runtime behavior and therefore deserved an explicit seam rather than staying as another inline rule block in `common.sh`. Extracting it keeps behavior stable and narrows the remaining runtime work to config discovery and preset restoration rather than mode semantics.

### D85. Runtime config discovery and cmdline-preset restore should live in a dedicated helper, not inline in common.sh

Decision:

- Add `thin-client-assistant/runtime/config_discovery.py` as the dedicated helper for:
  - live-state config directory discovery
  - preset-file discovery
  - cmdline preset restore/decode
  - end-to-end runtime config directory resolution, including preset-driven config generation
- Rewire `find_live_state_dir()` and `find_config_dir()` in `thin-client-assistant/runtime/common.sh` into thin wrappers over that helper.
- Keep `common.sh` responsible for sourcing the resulting config files and for the remaining runtime orchestration only.

Reason:

- After mode overrides moved out, the next substantial business/orchestration block left in `common.sh` was the combination of config discovery, preset discovery, and cmdline preset restoration. That logic mixed path policy, boot-time recovery behavior, and preset regeneration semantics. Pulling it behind a dedicated helper preserves behavior while further shrinking the runtime shell monolith and makes the remaining shell work much more obviously orchestration-only.

### D86. Runtime config generation and config-file sourcing should live in a dedicated loader helper, not inline in common.sh

Decision:

- Add `thin-client-assistant/runtime/config_loader.sh` as the dedicated shell helper for:
  - preset-driven runtime config generation via `generate_config_from_preset.py`
  - runtime config file sourcing for `thinclient.conf`, `network.env`, and `credentials.env`
  - the high-level `load_runtime_config()` flow that composes config discovery plus sourcing plus mode overrides
- Rewire `common.sh` to source `config_loader.sh` instead of carrying these functions inline.
- Keep `common.sh` focused on shared runtime orchestration, path helpers, stream/session helpers, and the remaining environment/state support behavior.

Reason:

- Once config discovery moved out, the next remaining config-specific block in `common.sh` was the actual generation and loading of runtime config files. That is still real config-loading behavior, not generic orchestration. Extracting it keeps the runtime shell surface modular and makes the remaining work in `common.sh` more clearly about runtime state and path orchestration rather than config assembly.

### D87. `common.sh` should degrade into a sourcing shell, not remain the runtime behavior sink

Decision:

- Extract thin-client runtime operational helper clusters out of `thin-client-assistant/runtime/common.sh` into sourced runtime modules as soon as a block has a stable caller contract.
- Keep stream-session state and management timer suspension/resume logic in `thin-client-assistant/runtime/stream_state.sh`.
- Keep runtime-owned path helpers plus GeForce NOW storage/home/cache/config preparation in `thin-client-assistant/runtime/runtime_ownership.sh`.

Reason:

- `common.sh` is sourced by several runtime entrypoints and by live-build maintenance helpers, so it is the highest-risk place to let unrelated behavior accumulate. Splitting stable operational seams into sourced modules reduces monolith risk without changing the runtime bootstrap contract that callers already rely on.

### D88. Kiosk stop-control is a shared runtime seam, not a `common.sh` inline block

Decision:

- Keep kiosk process-pattern detection, window-close attempts, and graceful-to-forceful stop behavior in `thin-client-assistant/runtime/kiosk_runtime.sh`.
- `common.sh` should source that module instead of owning the kiosk control logic directly.

Reason:

- The kiosk stop contract is used as operational runtime behavior during GFN stream optimization, but it is not generic shell bootstrap logic. Moving it out keeps the sourcing monolith shrinking and isolates the remaining kiosk-specific behavior into a dedicated runtime seam without changing the callers.

### D89. Kiosk session supervision belongs in a dedicated launcher helper, not in the mode-dispatch entrypoint

Decision:

- Keep the kiosk relaunch loop, stream-wait handling, and kiosk-install preflight in `thin-client-assistant/runtime/session_launcher.sh`.
- Keep `thin-client-assistant/runtime/launch-session.sh` focused on launch-status writing, mode dispatch, and delegation into mode-specific launchers.

Reason:

- `launch-session.sh` is the top-level runtime mode entrypoint. Leaving the kiosk supervisor loop inline there mixes dispatch with long-running session control flow. Moving that logic into a dedicated helper preserves the runtime contract while making the remaining launch/session seams explicit and easier to continue extracting.

### D90. Runtime user/state/logging helpers should be one shared core seam, not ad hoc leftovers in common.sh

Decision:

- Keep the shared runtime baseline in `thin-client-assistant/runtime/runtime_core.sh`.
- This module owns runtime user/group/home/uid lookup, Beagle state-dir and trace/marker file helpers, runtime logging, privileged command execution, unit-file presence checks, and live-medium discovery.
- `common.sh` should source this core seam instead of retaining those cross-cutting helpers inline.

Reason:

- After the operational blocks moved out, the remaining large cluster in `common.sh` was no longer one feature but the implicit foundation used by multiple extracted modules. Making that foundation explicit reduces hidden coupling between runtime helpers and keeps `common.sh` on the path toward a pure composition shell.

### D91. Small generic runtime value helpers should share one seam instead of staying as common.sh leftovers

Decision:

- Keep `beagle_curl_tls_args()`, `render_template()`, and `split_browser_flags()` in `thin-client-assistant/runtime/runtime_value_helpers.sh`.
- `common.sh` should source that helper instead of retaining these small cross-cutting helpers inline.

Reason:

- Once the runtime core moved out, the last inline `common.sh` logic was a small but still cross-cutting value-helper cluster used by multiple runtime launchers. Extracting that cluster finishes the shift from monolith to composition shell and leaves the next work focused on feature orchestration instead of leftover utility code.

### D92. X11/Xauthority runtime display handling should be shared across mode launchers

Decision:

- Keep X11/Xauthority discovery, readiness checks, candidate selection, and display wait helpers in `thin-client-assistant/runtime/x11_display.sh`.
- `launch-moonlight.sh` and `launch-geforcenow.sh` must both consume that shared helper instead of maintaining separate display bootstrap implementations.
- Preserve launcher-specific behavior at the call site:
  - Moonlight keeps the reselect-on-each-attempt behavior and display-ready/unready event logging
  - GeForce NOW keeps the fixed selected-auth wait path

Reason:

- The Moonlight and GFN launchers had diverged slightly but were still solving the same display bootstrap problem twice. A shared seam reduces duplication without forcing the two launchers into identical behavior where their operational assumptions still differ.

### D93. Moonlight target resolution and reachability should be one dedicated seam before pairing refactors

Decision:

- Keep Moonlight host/local-host/port resolution, IPv4 preference handling, Sunshine API URL rewriting, connect-host selection, and stream-target reachability waits in `thin-client-assistant/runtime/moonlight_targeting.sh`.
- `launch-moonlight.sh` should source this helper instead of mixing target selection with pairing/bootstrap and stream execution.

Reason:

- The target-resolution block was the largest remaining cohesive networking block in `launch-moonlight.sh`. Pulling it out first lowers the next pairing/bootstrap slice risk and makes Moonlight runtime work separable into targeting, pairing/bootstrap, and stream execution concerns.

### D94. Moonlight pairing/bootstrap/config sync should be one seam separate from target selection and stream exec

Decision:

- Keep Moonlight config-path discovery, config seeding/sync, certificate extraction, manager registration, list/bootstrap helpers, Sunshine PIN submission, and `ensure_paired()` in `thin-client-assistant/runtime/moonlight_pairing.sh`.
- `launch-moonlight.sh` should source this helper instead of mixing those flows with target resolution and final stream execution.

Reason:

- After target resolution moved out, the next largest coherent block in `launch-moonlight.sh` was the pairing/bootstrap/config-sync flow. Extracting it isolates Moonlight runtime work into three clear concerns: targeting, pairing/bootstrap, and execution/runtime setup.

### D95. Moonlight stream execution setup should be its own runtime seam

Decision:

- Keep Moonlight binary/app resolution, audio-driver and decoder selection, local display/resolution shaping, stream-argument assembly, and graphics/audio runtime environment preparation in `thin-client-assistant/runtime/moonlight_runtime_exec.sh`.
- `launch-moonlight.sh` should source this helper and remain the thin top-level orchestrator for reachability, pairing, and final `exec`.

Reason:

- After targeting and pairing moved out, the remaining block in `launch-moonlight.sh` was no longer launcher orchestration but a cohesive execution/runtime-setup seam. Extracting that block completes the main Moonlight split without changing runtime behavior and moves the next thin-client work onto `prepare-runtime.sh` and the shared runtime/network surfaces instead of back into the launcher.

### D96. Runtime config sync and live-state persistence should leave `prepare-runtime.sh`

Decision:

- Keep system-config target resolution, shared runtime-config file lists, config-path rebinding, permission normalization, live-state remount handling, and runtime-config persistence in `thin-client-assistant/runtime/runtime_config_persistence.sh`.
- `prepare-runtime.sh` should source that helper instead of keeping the config-copy and live-state persistence flow inline.
- `prepare-runtime.sh` should reuse `beagle_unit_file_present()` from `runtime_core.sh` instead of carrying another local unit-file presence helper.

Reason:

- `prepare-runtime.sh` had become the next runtime monolith after the Moonlight launcher split. The config-sync/live-state block was cohesive, reused internal path policy, and could be made argument-driven for smoke testing without changing runtime behavior. Pulling that block out starts the real reduction of the prepare entrypoint and prevents another accumulation of low-level persistence helpers there.

### D97. Runtime user bootstrap and hostname sync should leave `prepare-runtime.sh`

Decision:

- Keep local-auth path resolution, runtime login-shell selection, runtime user creation/update, secret-permission normalization, and local hostname/hosts-file synchronization in `thin-client-assistant/runtime/runtime_user_setup.sh`.
- `prepare-runtime.sh` should source that helper instead of keeping those bootstrap steps inline.
- The extracted helper may expose binary/path overrides for user-management and hostname commands so the seam stays smoke-testable without changing runtime defaults.

Reason:

- After config persistence moved out, the next cohesive `prepare-runtime.sh` block was the runtime-user bootstrap path. That code mixed account creation, credential-file permission policy, and identity sync, but it was still one operational concern. Pulling it out keeps the entrypoint moving toward orchestration-only code and gives the refactor a testable seam for behavior that otherwise only runs on a live system.

### D98. Runtime SSH/bootstrap management should leave `prepare-runtime.sh`

Decision:

- Keep managed SSH config rewriting, SSH host-key persistence/generation, USB tunnel service control, Beagle management unit activation, getty override installation, and boot-service normalization in `thin-client-assistant/runtime/runtime_bootstrap_services.sh`.
- `prepare-runtime.sh` should source that helper instead of keeping those SSH/service/bootstrap steps inline.
- `beagle_unit_file_present()` in `runtime_core.sh` should honor `BEAGLE_SYSTEMCTL_BIN` so extracted runtime service helpers stay smoke-testable without changing runtime defaults.

Reason:

- Once config persistence and runtime-user setup left the entrypoint, the next largest cohesive block was the SSH/bootstrap management path. It mixed SSH policy, host-key persistence, and service normalization, but those are still one bootstrapping concern and belong together. Pulling them out makes `prepare-runtime.sh` dramatically smaller and keeps the remaining shell focused on sequencing rather than service implementation details.

### D99. Runtime endpoint enrollment should leave `prepare-runtime.sh`

Decision:

- Keep runtime config/credential path resolution, enrollment URL selection, endpoint hostname/ID derivation, enrollment request execution, response application, and post-enrollment config reload in `thin-client-assistant/runtime/runtime_endpoint_enrollment.sh`.
- `prepare-runtime.sh` should source that helper instead of carrying the enrollment curl/apply/reload sequence inline.
- The shared runtime TLS helper must not emit blank `curl` arguments when no TLS options are needed.

Reason:

- After the bootstrap-service block moved out, the remaining non-trivial business flow in `prepare-runtime.sh` was the endpoint enrollment path. That is a cohesive runtime concern with real payload shaping and state reload semantics, so it deserves its own seam. Extracting it keeps the entrypoint thin and exposed a real helper bug in the TLS-argument layer, which is now fixed centrally rather than patched at one call site.

### D100. The final runtime status block should leave `prepare-runtime.sh`

Decision:

- Keep runtime status-path resolution, required-binary selection, binary-availability detection, and final runtime-status emission in `thin-client-assistant/runtime/runtime_prepare_status.sh`.
- `prepare-runtime.sh` should call that helper instead of keeping the final mode-switching and status-file write block inline.

Reason:

- Once enrollment and bootstrap services were extracted, the last large non-trivial tail in `prepare-runtime.sh` was the runtime-status block. That logic is cohesive, testable in isolation, and not specific to the entrypoint itself. Pulling it out keeps the wrapper thin and makes the required-binary contract explicit.

### D101. Config-retry, boot-mode detection, Plymouth messaging, and kiosk prepare belong in one wrapper helper

Decision:

- Keep config-load retry, boot-mode detection, Plymouth status messaging, optional runtime hook execution, and kiosk preparation in `thin-client-assistant/runtime/runtime_prepare_flow.sh`.
- `prepare-runtime.sh` should source that helper instead of carrying those bootstrap wrapper behaviors inline.

Reason:

- After the other prepare-runtime slices moved out, the remaining inline logic was no longer business logic but wrapper behavior around the ordered prepare flow. Grouping those pieces into one helper reduces the entrypoint to orchestration and avoids leaving another small monolith of retry/UI-wrapper behavior behind.

### D102. Network backend config-file and restart logic should leave `apply-network-config.sh`

Decision:

- Keep networkd file writing, NetworkManager connection writing, DNS server resolution, `resolv.conf` management, and backend restart/reload helpers in `thin-client-assistant/runtime/runtime_network_backend.sh`.
- `apply-network-config.sh` should source that helper instead of carrying backend config-file and restart logic inline.
- `apply-network-config.sh` should reuse `load_runtime_config_with_retry()` from `runtime_prepare_flow.sh` instead of keeping another local copy of the same retry wrapper.

Reason:

- Once `prepare-runtime.sh` became thin, `apply-network-config.sh` became the next runtime shell monolith. Its backend write/restart layer was cohesive, testable with temp paths and stubbed service binaries, and independent from the remaining interface/route wait logic. Pulling that block out continues the same reduction strategy and avoids duplicating the config-retry wrapper across runtime entrypoints.

### D103. Network interface/route/wait logic should also leave `apply-network-config.sh`

Decision:

- Keep interface selection, static IPv4 CIDR calculation, URL-host extraction, DNS wait-target shaping, IPv4 resolution checks, default-route waiting, DNS-target waiting, hostname application, static route installation, and static address application in `thin-client-assistant/runtime/runtime_network_runtime.sh`.
- `apply-network-config.sh` should source that helper instead of carrying the runtime route/wait/identity block inline.
- The extracted helper may expose path/binary overrides for `/sys/class/net`, `ip`, `getent`, `hostnamectl`, `hostname`, and `/etc/hostname` so the seam stays smoke-testable without changing runtime defaults.

Reason:

- After the backend config-file/restart layer moved out, the remaining `apply-network-config.sh` logic was still a cohesive runtime network block rather than pure orchestration. Pulling it out completes the same pattern used on `prepare-runtime.sh`: the entrypoint becomes a sequencing shell, and the operational behavior moves into explicit helpers with test seams.

### D104. Moonlight remote API calls should leave `moonlight_pairing.sh`

Decision:

- Keep Moonlight client device-name resolution, manager registration payload generation, manager-side client registration, Sunshine PIN submission, and JSON status extraction in `thin-client-assistant/runtime/moonlight_remote_api.sh`.
- `moonlight_pairing.sh` should source that helper instead of mixing remote API calls with local config/certificate/bootstrap logic.
- The extracted helper should honor `BEAGLE_CURL_BIN` and `BEAGLE_HOSTNAME_BIN` so the remote API seam stays smoke-testable without changing runtime defaults.

Reason:

- After `prepare-runtime.sh` and `apply-network-config.sh` became thin entrypoints, `moonlight_pairing.sh` became the next clear runtime monolith. The remote API side was a cohesive first cut because it mixed HTTP payload shaping, TLS argument handling, manager registration, and Sunshine PIN submission, but it did not need to remain tangled with local Moonlight config editing and pair-process orchestration. Pulling it out reduces the pairing module and keeps the next pairing slices more focused.

### D105. Moonlight local config/certificate/bootstrap state should also leave `moonlight_pairing.sh`

Decision:

- Keep Moonlight config-path discovery, runtime-config seeding, host-config presence checks, client-certificate extraction, manager-response host sync, and bootstrap list priming in `thin-client-assistant/runtime/moonlight_config_state.sh`.
- `moonlight_pairing.sh` should source that helper instead of mixing local config state with the final pair-process orchestration loop.

Reason:

- Once the remote API block moved out, the remaining large block in `moonlight_pairing.sh` was the local Moonlight config and bootstrap state path. That logic is cohesive, stateful, and separately smoke-testable with temporary config files. Pulling it out reduces the pairing entrypoint to the actual pairing orchestration, which is the right long-term structure for the runtime layer.

### D106. USB runtime state and payload shaping should leave `beagle-usbctl.sh`

Decision:

- Keep USB state-path resolution, persisted bound-busid reads/writes, enabled/tunnel env accessors, tunnel-status detection, local USB inventory JSON shaping, and list/status payload rendering in `thin-client-assistant/runtime/beagle_usb_runtime_state.sh`.
- `beagle-usbctl.sh` should source that helper instead of mixing state I/O, tunnel-status checks, and JSON rendering with the command flow.

Reason:

- After `prepare-runtime.sh`, `apply-network-config.sh`, and `moonlight_pairing.sh` became thin wrappers, `beagle-usbctl.sh` was the next obvious runtime shell monolith. Its state/payload layer was a cohesive first cut because it mixed env accessors, persisted USB binding state, tunnel detection, and JSON response shaping, but those concerns are independent from the command dispatcher itself. Pulling them out makes the USB state contract explicit and smoke-testable with temporary state roots and stubbed binaries.

### D107. USB daemon, bind/unbind, and tunnel orchestration should also leave `beagle-usbctl.sh`

Decision:

- Keep `usbipd` process/binary accessors, daemon restart handling, exportable-device detection, bound-device resync, bind/unbind orchestration, list/status command helpers, and the SSH tunnel daemon exec path in `thin-client-assistant/runtime/beagle_usb_runtime_actions.sh`.
- `beagle-usbctl.sh` should source that helper instead of carrying `usbip` lifecycle logic, service restarts, and tunnel exec behavior inline.
- The extracted helper may expose binary overrides for `usbipd`, `pkill`, `modprobe`, `systemctl`, `ssh`, and `sleep` so the lifecycle path stays smoke-testable without changing runtime defaults.

Reason:

- Once the USB state/payload block left, the remainder of `beagle-usbctl.sh` was still not just dispatch glue; it still owned the operational `usbipd` lifecycle, persisted bound-device resync, bind/unbind side effects, and SSH reverse-tunnel startup. That is one cohesive runtime orchestration concern, and extracting it completes the same entrypoint-thinning pattern already used for the runtime prepare, network, and Moonlight paths.

### D108. GeForce NOW desktop and URL-handler integration should leave `install-geforcenow.sh`

Decision:

- Keep desktop-database and `xdg-mime` binary accessors, desktop-file generation, MIME registration, user `xdg-open` wrapper generation, host `xdg-open` shim generation, and the top-level desktop integration orchestration in `thin-client-assistant/runtime/geforcenow_desktop_integration.sh`.
- `install-geforcenow.sh` should source that helper instead of carrying desktop-file and wrapper/shim writes inline.
- The extracted helper may expose path and binary overrides for desktop database, `xdg-mime`, wrapper target, browser target, host shim path, and host shim log directory so the desktop integration seam stays smoke-testable without changing runtime defaults.

Reason:

- After the USB wrapper became thin, `install-geforcenow.sh` was the next runtime/install crossover monolith. Its desktop/MIME/URL-handler path was a cohesive first cut because it mixed file generation and environment-specific shell wrappers, but those concerns are independent from flatpak installation and storage preparation. Pulling them out makes the desktop-integration contract explicit and keeps the installer wrapper moving toward composition-only code.

### D109. GeForce NOW flatpak scope and install orchestration should also leave `install-geforcenow.sh`

Decision:

- Keep flatpak binary discovery, install-scope normalization, dry-run command execution, flatpak availability checks, install-scope permission checks, installed-ref detection, and the shared flatpak remote/install flow in `thin-client-assistant/runtime/geforcenow_flatpak.sh`.
- `install-geforcenow.sh` should source that helper instead of carrying scope parsing, dry-run execution, availability checks, and remote/app install logic inline.
- `launch-geforcenow.sh` should reuse the same install-scope resolver instead of keeping a second local `flatpak_scope_flag()` implementation.

Reason:

- Once the desktop integration block moved out, the remainder of `install-geforcenow.sh` still mixed installer orchestration with low-level flatpak execution policy and scope parsing. That logic is cohesive, testable with a stubbed `flatpak` binary, and shared conceptually with the runtime launcher. Extracting it completes the main reduction of the GeForce NOW installer wrapper and removes another duplicated scope parser from the runtime layer.
