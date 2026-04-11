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
