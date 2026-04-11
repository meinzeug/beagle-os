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
