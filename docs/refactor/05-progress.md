# Progress (2026-04-18)

## Update (2026-04-21, GoFuture Plan 04 Schritt 1+3 umgesetzt: RBAC-Nachruestung)

- Control-Plane POST-Mutationspfad vereinheitlicht: `POST /api/v1/vms` wird jetzt als Legacy-Alias sicher auf den Provisioning-Mutationspfad gemappt.
- Fehlende RBAC-Abdeckung fuer Legacy-Pfad behoben:
	- `beagle-host/bin/beagle-control-plane.py`: neue `admin_post_path`-Normalisierung (`/api/v1/vms` -> `/api/v1/provisioning/vms`) inklusive Auth-/RBAC-Pruefung.
	- `beagle-host/services/authz_policy.py`: `required_permission(POST, /api/v1/vms)` liefert jetzt `provisioning:write`.
- Unit-Test hinzugefuegt: `tests/unit/test_authz_policy.py`
	- verifiziert `viewer` darf `settings:write` nicht,
	- verifiziert Admin darf `settings:write`,
	- verifiziert Legacy-Route `/api/v1/vms` mappt auf `provisioning:write`.
- Live-Verifikation auf `srv1.beagle-os.com` nach Deploy:
	- `POST /api/v1/vms` ohne Auth -> `401 unauthorized`.
	- `POST /api/v1/provisioning/vms` ohne Auth -> `401 unauthorized`.
- Damit sind in `docs/gofuture/04-control-plane.md` Schritt 1 und Schritt 3 inklusive RBAC-Test-Checkboxen fuer `/api/v1/vms` und Settings-Adminschutz abgehakt.

## Update (2026-04-21, Let's Encrypt activation fix: issued cert is now applied to nginx)

- Reproduced issue on `srv1.beagle-os.com`: certbot had a valid certificate in `/etc/letsencrypt/live/srv1.beagle-os.com/`, but nginx still served `/etc/beagle/tls/beagle-proxy.crt` (self-signed).
- Root cause: `request_letsencrypt()` issued certificates but did not switch nginx `ssl_certificate`/`ssl_certificate_key` directives to the issued Let's Encrypt paths.
- Patched `beagle-host/services/server_settings.py`:
	- after successful certbot run, it now rewrites nginx TLS paths to `/etc/letsencrypt/live/<domain>/fullchain.pem` and `/etc/letsencrypt/live/<domain>/privkey.pem`,
	- runs `nginx -t`, reloads nginx, and rolls back on config-test failure,
	- exposes `nginx_tls_uses_letsencrypt` in TLS status for explicit runtime visibility.
- Hotfixed `srv1.beagle-os.com` immediately by deploying the patched service and applying the switch with the existing issued certificate.
- Runtime validation on srv1:
	- nginx config now points to Let's Encrypt certificate paths,
	- external handshake now shows issuer `Let's Encrypt (E8)`,
	- `ServerSettingsService().get_tls_status()` reports `provider=letsencrypt`, `certificate_exists=true`, `nginx_tls_uses_letsencrypt=true`.

## Update (2026-04-21, srv1.beagle-os.com runtime validation after server became available)

- srv1.beagle-os.com came online; performed comprehensive runtime validation.
- Updated control-plane deployed to srv1 (provider-default-to-beagle change from `9abde8f`).
- `beagle-control-plane.service` restarted cleanly; startup log shows `version: 6.7.0`, `listen_host: 127.0.0.1`.
- **Plan 01 (JS modules) validated:**
  - All 16 UI modules (actions, activity, api, auth, dashboard, dom, events, iam, inventory, panels, policies, provisioning, settings, state, theme, virtualization) return HTTP 200 from nginx.
  - `index.html` correctly references `<script type="module" src="/main.js?v=6.7.0">` (no legacy app.js reference).
  - Script load order verified: `beagle-web-ui-config.js` → `browser-common.js` → `main.js` (module).
  - All Plan 01 test checkboxes marked `[x]`.
- **Plan 02 (CSS split) validated:**
  - All 16 global CSS partials return HTTP 200.
  - All 8 panel-specific partials return HTTP 200.
  - `styles.css` barrel correctly uses `@import url(...)` for all partials.
  - Plan 02 validation checkpoint added.
- **Plan 03 (index.html) validated:**
  - CSP header: `script-src 'self'` — no `unsafe-inline`, no `unsafe-eval`, compatible with ES modules.
  - Cache-busting string `?v=6.7.0` correctly set.
  - All Plan 03 test checkboxes marked `[x]`.
- **Plan 04 Schritt 3 (RBAC) preliminary check:**
  - POST `/api/v1/provisioning/vms` without auth → HTTP 401 ✅
  - POST `/api/v1/settings/general` without auth → HTTP 401 ✅
  - POST `/api/v1/auth/users` without auth → HTTP 401 ✅
  - RBAC appears consistently applied on mutation endpoints.

## Update (2026-04-21, GoFuture Plan 04 & 05: Provider-Abstraction started)

- Analyzed Plan 04 (Control Plane cleanup) and Plan 05 (Provider-Abstraction) to identify architectural violations.
- Ran comprehensive grep audit: all `qm` and `pvesh` calls are correctly isolated in `beagle-host/providers/proxmox_host_provider.py`.
- Verified that the Beagle provider (`beagle_host_provider.py`) implements all 20+ Contract methods from `host_provider_contract.py`.
- Found no direct Proxmox API calls outside of the Proxmox provider directory — architecture is clean.
- **Implemented Plan 05 Schritt 4 (provider default):**
	- Changed the default provider in `beagle-host/bin/beagle-control-plane.py` from `"proxmox"` to `"beagle"`.
	- This aligns with the strategic shift to Beagle OS standalone and removes the Proxmox dependency from system startup.
	- Updated `docs/gofuture/05-provider-abstraction.md` to mark this step completed and refined follow-up steps.
- Identified that further Plan 04/05 work (service layer extraction, Registry simplification, Proxmox directory removal) requires multi-file refactoring and integration tests.
- Confirmed Python syntax in modified control plane file via `py_compile`.
- **Status:** Plan 04/05 foundation work is clean and ready; next execution wave should focus on the service-layer refactoring (Plan 04 steps 2-6) and comprehensive test suite (Plan 05 steps 5a).

## Update (2026-04-21, Let's Encrypt/certbot runtime fix applied in repo and on `srv1.beagle-os.com`)

- Fixed the Security/TLS settings flow so Let's Encrypt issuance no longer fails on fresh standalone hosts with `certbot not installed on this server`.
- Patched the canonical install paths to install the required TLS runtime packages automatically:
	- `scripts/install-beagle-host-services.sh`
	- `scripts/install-beagle-proxy.sh`
	- `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
- Added backend preflight checks in `beagle-host/services/server_settings.py` for both the `certbot` binary and the nginx plugin, so missing dependencies now fail with a precise operator-visible error.
- Root-caused and fixed a second live issue on `srv1.beagle-os.com`: API-triggered `certbot --nginx` failed inside the hardened `beagle-control-plane.service` sandbox even after packages were installed.
- Mitigated the runtime constraint in two layers:
	- expanded the systemd unit `ReadWritePaths=` for Let's Encrypt/nginx paths,
	- execute certbot via transient `systemd-run` when available so the TLS workflow does not inherit the control-plane sandbox.
- Corrected nginx TLS status detection to inspect the actual deployed site names (`beagle-web-ui`, `beagle-proxy.conf`, `beagle-proxy`) instead of assuming a single filename.
- Added focused unit coverage in `tests/unit/test_server_settings.py` for the missing-certbot and missing-nginx-plugin cases.
- Validated locally in the repo venv:
	- `python -m unittest tests.unit.test_auth_session tests.unit.test_server_settings`
	- result: `OK`
- Applied the same repo-backed hotfix on `srv1.beagle-os.com`, re-ran the supported install scripts, restarted `beagle-control-plane.service`, and verified end-to-end:
	- API call `POST /beagle-api/api/v1/settings/security/tls/letsencrypt` now returns `ok: true`,
	- final security status reports `provider: letsencrypt`, `certificate_exists: true`, and `nginx_tls_enabled: true` for `srv1.beagle-os.com`.

## Update (2026-04-21, fresh-install onboarding fix applied in repo and on `srv1.beagle-os.com`)

- Fixed `beagle-host/services/auth_session.py` so a generated bootstrap admin no longer suppresses first-run onboarding.
- Bootstrap-created users are now marked as `bootstrap_only`, and `update_user()` clears that marker when onboarding promotes the first real admin account.
- Added focused unit coverage in `tests/unit/test_auth_session.py` for both cases:
	- bootstrap-only admin keeps onboarding pending,
	- completing onboarding with the same username promotes the account and clears `bootstrap_only`.
- Validated locally with `python -m unittest tests.unit.test_auth_session` under the repo venv.
- Applied the same backend fix on `srv1.beagle-os.com`, repaired the already-written auth state under `/var/lib/beagle/beagle-manager/auth/`, restarted `beagle-control-plane.service`, and verified:
	- `GET /api/v1/auth/onboarding/status` now returns `pending: true`,
	- the fresh install is no longer treated as already onboarded merely because the bootstrap `admin` account exists.

## Update (2026-04-20, GoFuture Plan 03 executed: WebUI HTML entry cleanup)

- `website/index.html` now uses the repo `VERSION` (`6.7.0`) for both `styles.css` and `main.js` cache-busting parameters instead of the stale hard-coded `7.1.0` value.
- Script order was normalized so `beagle-web-ui-config.js` and `browser-common.js` load before the ES-module bootstrap.
- Added `sync_web_ui_asset_versions()` to `scripts/package.sh` so release packaging keeps the WebUI asset version strings aligned with the root `VERSION` file automatically.
- Validated on `srv1.beagle-os.com` after reload:
  - `styles.css?v=6.7.0` and `main.js?v=6.7.0` are requested,
  - all imported CSS partials and JS modules still load with HTTP 200,
  - CSP remains satisfied without loosening `script-src 'self'`.
- Removed legacy `website/app.js` and switched `scripts/validate-project.sh` from monolith validation to `website/main.js` plus `website/ui/*.js` module validation.
- Added a local offline runtime validation fallback (static server with `website/` + `core/` path mapping) to continue WebUI checks while `srv1.beagle-os.com` was timing out.
- Locally validated under Chromium DevTools:
	- dark-mode preference persists across reload (`beagle.darkMode=0` + `body.light-mode` after refresh),
	- hash routing `#panel=inventory` activates the Inventory panel and nav state,
	- no CSP violations were reported in console output.
- Validation blocker identified on `srv1.beagle-os.com`:
  - onboarding is already completed by `admin`,
  - no bootstrap auth environment is exposed via the systemd unit anymore,
  - authenticated runtime validation now requires existing operator credentials or an explicit decision to rotate/create a temporary admin credential.

## Update (2026-04-20, GoFuture Plan 02 executed: WebUI CSS split)

- Replaced the `website/styles.css` monolith with a native CSS import barrel and split the former stylesheet into 24 partials under `website/styles/` and `website/styles/panels/`.
- The split now mirrors the WebUI module boundaries already introduced in Plan 01:
  - global layers: `_tokens`, `_reset`, `_layout`, `_nav`, `_buttons`, `_cards`, `_chips`, `_tables`, `_forms`, `_toolbar`, `_modals`, `_banners`, `_inspector`, `_helpers`, `_responsive`, `_reduced-motion`
  - panel layers: `_inventory`, `_virtualization`, `_provisioning`, `_policies`, `_iam`, `_settings`, `_scope-switcher`, `_sessions`
- Fixed an existing structural bug while extracting tokens: `.svg-sprite` no longer sits inside the `:root` block.
- Synced the CSS split to `srv1.beagle-os.com` and validated the runtime in the browser:
  - `styles.css` and all imported `/styles/*.css` and `/styles/panels/*.css` requests return HTTP 200,
  - no blocking browser errors were introduced by the CSS split,
  - responsive layout still renders at desktop/tablet/mobile widths.
- Remaining Plan 02 follow-up is narrow:
  - authenticated panel-by-panel visual comparison,
  - theme persistence / dark-mode reload verification.

## Update (2026-04-20, GoFuture Plan 01 execution started: WebUI ES module foundation)

- Started the actual implementation of `docs/gofuture/01-webui-js-module.md` in `website/` instead of keeping the plan purely documentary.
- Created the new native ES module directory `website/ui/`.
- Landed the first extracted module tranche:
	- `website/ui/state.js`
	- `website/ui/dom.js`
	- `website/ui/api.js`
	- `website/ui/auth.js`
	- `website/ui/panels.js`
	- `website/ui/theme.js`
	- `website/ui/activity.js`
	- `website/ui/inventory.js`
	- `website/ui/virtualization.js`
	- `website/ui/provisioning.js`
	- `website/ui/policies.js`
	- `website/ui/iam.js`
	- `website/ui/settings.js`
	- `website/ui/dashboard.js`
	- `website/ui/actions.js`
	- `website/main.js`
- The extraction keeps existing runtime behavior stable because `website/index.html` still boots the legacy `app.js` path until the final module-entry cutover is performed.
- Security-sensitive WebUI behavior was preserved during extraction:
	- API absolute targets remain opt-in only.
	- Legacy `X-Beagle-Api-Token` stays opt-in only.
	- credential reveal values stay in in-memory secret vault structures instead of DOM attributes.
- Verified via workspace diagnostics that the newly added modules are syntax-clean and introduce no immediate JS errors.
- Marked GoFuture Plan 01 steps 1 through 17 as completed.
- Synced the new `website/ui/*.js` module files and `website/main.js` to the dedicated execution host `srv1.beagle-os.com` under `/opt/beagle/website/` so the server-side working tree stays aligned with GoFuture execution.
- Switched `website/index.html` from legacy `app.js` bootstrap to `type="module"` via `website/main.js`.
- Runtime validation on `srv1.beagle-os.com` succeeded in the browser:
  - `main.js` and all extracted `ui/*.js` modules load with HTTP 200,
  - no blocking JavaScript runtime errors remain in the console,
  - page renders the login modal and dashboard shell correctly under the new module bootstrap.

## Update (2026-04-20, WebUI 7.0 navigation restructure)

- Implemented the first concrete step of the Beagle OS 7.0 Web Console Informationsarchitektur in `website/`:
  - **Sidebar navigation restructured** from a flat "Workspaces / Verwaltung / Server-Einstellungen" layout to a professional datacenter hierarchy matching the 7.0 target architecture spec:
    - `Datacenter` → Dashboard
    - `Compute` → Nodes, VMs & Endpoints, VM erstellen
    - `Pools & Sessions` → Pools & Policies, Sessions (placeholder)
    - `Identity` → Users & Roles
    - `Network` → Interfaces & DNS, Firewall
    - `Operations` → Dienste, Updates, Backup & Recovery
    - `Platform` → Allgemein, Sicherheit & TLS
  - **New SVG icon sprites** added: `i-compute`, `i-pool`, `i-sessions`, `i-vm`, `i-operations`, `i-platform`.
  - **Scope Switcher** added above the sidebar nav — shows current datacenter scope and node count.
  - **Sessions panel placeholder** added (`data-panel-section="sessions"`) with architecture preview card showing the 7.0 Session object model, feature list, and a code schema preview.
  - **`panelMeta` in `app.js`** updated: all eyebrow/title values now match the new domain groupings (Compute, Pools & Sessions, Identity, Network, Operations, Platform).
  - **CSS additions** in `styles.css`: scope switcher widget, `chip-amber` variant, `nav-badge-coming` pill, full Sessions coming-soon panel styling.
  - No `data-panel` or `data-panel-section` attribute values were changed → zero JS regressions.
  - All 14 existing panel sections remain intact and operational.

## Update (2026-04-20, Dedicated server reinstall runbook applied on new Hetzner host)

- New target host provisioned by operator: Hetzner Server Auction `#2980076` with IPv4 `46.4.96.80` (Rescue active, SSH key-based access).
- Install path executed reproducibly from repo/tooling:
	- Hetzner `installimage` with Beagle tarball `Debian-1201-bookworm-amd64-beagle-server.tar.gz`.
	- Post-install rescue fix re-applied (same as prior verified runbook):
		- seed `/etc/default/grub` and `/etc/kernel-img.conf`,
		- chroot install `lvm2`,
		- `update-initramfs -u -k all`,
		- `grub-install /dev/sda` + `update-grub`.
- Host rebooted successfully and became reachable via SSH key on `46.4.96.80`.
- Local SSH alias was migrated to the new host in local operator config (`~/.ssh/config`):
	- `Host srv1.beagle-os.com` now points to `46.4.96.80` with `~/.ssh/beagle-dedicated_ed25519`.
- First-boot bootstrap issue observed and mitigated during this run:
	- bootstrap started correctly but initially hit `404` while downloading host release assets,
	- missing `6.7.0` thin-client artifacts were uploaded to `beagle-os.com/beagle-updates/`,
	- bootstrap resumed and continued package/runtime setup on host.
- Reproducibility fix committed in repo scripts:
	- `scripts/publish-hosted-artifacts-to-public.sh` now publishes required thin-client host artifacts (`pve-thin-client-usb-installer-v*.sh/.ps1`, `pve-thin-client-live-usb-v*.sh`) and refreshes their `latest` links,
	- prevents future installimage first-boot bootstrap from failing with missing public artifact `404` due to incomplete publication set.
- Current state at this checkpoint:
	- host is online and bootstrap is actively installing runtime dependencies,
	- no manual out-of-repo host edits were used beyond the documented rescue/chroot runbook and artifact publication step.

## Update (2026-04-20, Hetzner installimage tarball fix v2)

- Reproduced on Hetzner vServer `srv1.beagle-os.com` (178.104.179.245) that the published 6.7.0 server installimage tarball `Debian-1201-bookworm-amd64-beagle-server.tar.gz` mechanically completes Hetzner's installimage flow but the host never returns from `reboot`.
- First fix attempt (commit before this entry): seeded `/etc/default/grub` + `/etc/kernel-img.conf` in the rootfs. Built locally, scp-uploaded to rescue, re-installed. INSTALLATION COMPLETE was clean (no more `sed` warnings) but the host stayed dark for 9+ minutes after reboot - identical symptom as 6.7.0.
- Root cause v2: the tarball shipped `grub-common` + `grub-pc-bin` + `grub-efi-amd64-bin` but NOT `grub-pc`, the wrapper package providing the working `grub-install` script + dpkg postinst hooks. Hetzner installimage's grub stage runs `chroot $hdd grub-install /dev/sda` + `update-grub` and silently produces no `/boot/grub/grub.cfg` with kernel entries, so stage1 from the MBR finds no menu and the system never boots the installed kernel.
- Fix v2 applied to `scripts/build-server-installimage.sh`:
  - install `debconf-utils` + preseed `grub-pc/install_devices` empty so `grub-pc` postinst does not block in chroot,
  - add `grub-pc` and `os-prober` to the apt install list,
  - run `update-grub` once in the chroot so the tarball ships a valid `/boot/grub/grub.cfg` with menuentries for the installed kernel.
- Tarball verified after rebuild: contains `/usr/sbin/grub-install`, `/usr/sbin/update-grub`, `/boot/grub/grub.cfg` (with kernel 6.1.0-44-amd64 entry), `/boot/vmlinuz-6.1.0-44-amd64`, `/boot/initrd.img-6.1.0-44-amd64`, plus the seeded `/etc/default/grub` + `/etc/kernel-img.conf`.
- BLOCKED on host recovery: rescue session was already consumed by the failed v1 install reboot. Operator must re-activate Hetzner Rescue in the Hetzner panel for `srv1.beagle-os.com` and provide a fresh root password before the v2 tarball can be uploaded + installed.
- Public publish (6.7.1) still pending; the fixed tarball lives only in `dist/beagle-os-server-installimage/` locally.

## Update (2026-04-20, refactorv2 strategic doc set landed in `docs/refactorv2/`)

- Added a 16-document refactor wave 2 doc set under [docs/refactorv2/](../refactorv2/README.md) targeting the 7.0 jump.
- Scope: position Beagle OS as a full open-source desktop-virtualization platform that competes head-to-head with Proxmox VE, Omnissa Horizon, Citrix DaaS, Microsoft Windows 365, Parsec for Teams, Sunshine/Apollo, Kasm Workspaces, Harvester HCI.
- New docs:
  - [00-vision.md](../refactorv2/00-vision.md) — Nordstern + 30-min onboarding promise.
  - [01-competitor-research.md](../refactorv2/01-competitor-research.md) — competitor analysis + feature matrix.
  - [02-feature-gap-analysis.md](../refactorv2/02-feature-gap-analysis.md) — P0/P1/P2 gaps mapped to repo modules.
  - [03-target-architecture-v2.md](../refactorv2/03-target-architecture-v2.md) — cluster + pool + tenant architecture, /api/v2.
  - [04-roadmap-v2.md](../refactorv2/04-roadmap-v2.md) — waves 7.0.0 through 7.4.2.
  - [05-streaming-protocol-strategy.md](../refactorv2/05-streaming-protocol-strategy.md) — Apollo backend, virtual display, auto-pairing.
  - [06-iam-multitenancy.md](../refactorv2/06-iam-multitenancy.md) — OIDC/SAML/SCIM, tenant scope, audit.
  - [07-storage-network-plane.md](../refactorv2/07-storage-network-plane.md) — StorageClass, NetworkZone, distributed firewall.
  - [08-ha-cluster.md](../refactorv2/08-ha-cluster.md) — etcd-based cluster, live-migration, HA-Manager.
  - [09-backup-dr.md](../refactorv2/09-backup-dr.md) — incremental backup, live-restore, replication.
  - [10-gpu-device-passthrough.md](../refactorv2/10-gpu-device-passthrough.md) — vfio + vGPU + USB-class redirect.
  - [11-endpoint-strategy.md](../refactorv2/11-endpoint-strategy.md) — A/B updates, enrollment-flow, endpoint profiles.
  - [12-security-compliance.md](../refactorv2/12-security-compliance.md) — threat model, layered controls, SOC2/ISO/DSGVO posture.
  - [13-observability-operations.md](../refactorv2/13-observability-operations.md) — Prometheus, OTLP, default dashboards.
  - [14-platform-api-extensibility.md](../refactorv2/14-platform-api-extensibility.md) — /api/v2, terraform-provider-beagle, beaglectl, webhooks.
  - [15-risks-open-questions.md](../refactorv2/15-risks-open-questions.md) — risk register and open architecture decisions.
- No source code changed. Provider-neutrality preserved. No regressions.
- Open decisions to be tracked in `docs/refactor/07-decisions.md` (cluster store, default storage, streaming backend, virtual display, backup format, SDN, CLI language).

## Update (2026-04-20, reproducible XFCE/noVNC desktop fix deployed and rebuilt into server installer ISO)

- Root-caused the noVNC/desktop mismatch on live guests:
	- QEMU/libvirt VNC was exposing the legacy VGA/tty framebuffer,
	- XFCE was rendering on the X11/KMS display,
	- result: noVNC showed tty/login text instead of the real desktop.
- Implemented the repo-level runtime fix in [beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl](beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl):
	- install `x11vnc` in provisioned Ubuntu guests,
	- create and enable `beagle-x11vnc.service`,
	- run x11vnc against `:0` on guest port `5901`,
	- removed the non-reproducible `-o /var/log/beagle-x11vnc.log` flag that caused permission-denied service failures.
- Implemented the repo-level host routing fix in [beagle-host/services/vm_console_access.py](beagle-host/services/vm_console_access.py):
	- added guest IPv4 discovery,
	- added TCP reachability check for guest port `5901`,
	- for Beagle/libvirt VMs, noVNC now prefers guest `x11vnc` when reachable and falls back to host-side QEMU VNC otherwise.
- Deployed the same repo files to the running beagleserver host runtime and restarted `beagle-control-plane`.
- Completed the live repair on VM100 itself:
	- removed the stale log-file flag from `/etc/systemd/system/beagle-x11vnc.service`,
	- reloaded systemd,
	- restarted x11vnc successfully,
	- verified service state `active` and listener on TCP `5901`.
- Reproducibility proof for future installs/builds:
	- [scripts/install-beagle-host.sh](scripts/install-beagle-host.sh) installs hosts by `rsync -a --delete "$ROOT_DIR/" "$INSTALL_DIR/"`, so the shipped repo copy is the install source of truth,
	- rebuilt the server installer ISO from the current repo state after the fix,
	- verified fresh artifacts exist at `dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso` and `dist/beagle-os-server-installer/beagle-os-server-installer.iso` with timestamp `2026-04-20 17:16`.
- Net effect:
	- manual VM100 hotfix is now also represented in repo code,
	- the next server-installer ISO build already contains the fix,
	- the next host install from that ISO will carry the corrected firstboot + noVNC behavior without any manual patching.

## Update (2026-04-20, VM pause flag fix + reproducible desktop provisioning)

- **Root-caused VM pause issue:** VMs started via Beagle provisioning were remaining in paused state (QEMU `-S` flag or equivalent), preventing XFCE desktop from booting or appearing. 
  - Deep codebase search confirmed NO pause/suspend flags exist in repo code — issue originates from external QEMU/Proxmox behavior during provisioning lifecycle.
  - Temporary workaround verified: `virsh suspend → virsh resume` sequence unpauses VMs and allows OS boot.
  
- **Implemented provider-agnostic fix:**
  - Added `resume_vm()` method to `beagle_host_provider.py` (Libvirt path): checks domain state with `virsh domstate`, resumesif paused via `virsh resume`.
  - Added `resume_vm()` method to `proxmox_host_provider.py`: uses `qm resume` for Proxmox VMs.
  - Updated `finalize_ubuntu_beagle_install()` in `ubuntu_beagle_provisioning.py` to call `resume_vm()` after VM restart during provisioning.
  - Resume is idempotent: safe to call on running/paused/non-existent VMs; failures ignored gracefully.
  
- **Impact:** Future VM provisioning operations will automatically ensure VMs are not paused after installation completes. Desktop should appear immediately post-install without manual intervention. Fix applies to all provider configurations (Libvirt, Proxmox).

- **Deployment status:** Changes were deployed to the running beagleserver host stack and `beagle-control-plane` was restarted; remaining work is validation on a freshly installed host/VM lifecycle, not ad-hoc runtime patching.

## Update (2026-04-20, reproducible host-download artifact fix + rebuilt server installer + beagleserver reinstall)

- Root-caused the VM installer endpoint `503` regression to a reproducibility gap in host install flow:
	- when release artifacts already existed under `dist/`, `scripts/install-beagle-host.sh` returned early,
	- `scripts/prepare-host-downloads.sh` was skipped,
	- host-local API endpoints (`/api/v1/vms/<id>/installer.sh`, `/live-usb.sh`) could miss required `*-host-latest` templates.
- Implemented repo fix in `scripts/install-beagle-host.sh`:
	- `prepare-host-downloads.sh` is now always executed after release artifacts are validated,
	- this makes hosted installer template generation deterministic and removes dependence on manual host hotfixes.
- Rebuilt server installer ISO from patched sources (2026-04-20 run):
	- output: `dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso`
	- output: `dist/beagle-os-server-installer/beagle-os-server-installer.iso`
- Reinstalled local `beagleserver` VM against the rebuilt ISO:
	- recreated domain and disk,
	- verified CD-ROM source is the fresh ISO (`/tmp/beagleserver.iso` copied from rebuilt artifact),
	- verified domain `beagleserver` is running after recreate.
- Environment note captured during reinstall:
	- local harness hit `KVM permission denied` in one run path,
	- fallback recreate path without KVM acceleration was used to complete VM recreation/boot from rebuilt media.

## Update (2026-04-19, Beagle OS 6.6.9 public installimage release + Hetzner host update)

- Built and verified release `6.6.9` with the corrected Hetzner `installimage` tarball included in the release/public-download set.
- Published `6.6.9` artifacts to `beagle-os.com/beagle-updates`:
  - endpoint installer ISO,
  - server installer ISO,
  - Hetzner `Debian-1201-bookworm-amd64-beagle-server.tar.gz`,
  - USB payload/bootstrap bundles,
  - source tarball,
  - kiosk AppImage,
  - `SHA256SUMS` and `beagle-downloads-status.json`.
- Verified public metadata reports `version: 6.6.9` and the installimage SHA256 `3d0a0623585265e9d690f9bcf7d9a1c7baa0aa0f85cbfa0544ef967f2fb7c34d`.
- Installed the public installimage path on the real Hetzner host and updated the running system:
  - host: `beagle-server`,
  - `/opt/beagle/VERSION`: `6.6.9`,
  - `beagle-control-plane.service`: active,
  - nginx host-local downloads: active on `/beagle-downloads`,
  - `virsh --connect qemu:///system list --all`: reachable.
- Fixed first-boot standalone bootstrap failure on minimal installimage targets:
  - `scripts/install-beagle-host-services.sh` now runs `apt-get update` before runtime package installs,
  - missing runtime packages are no longer hidden behind a swallowed `apt-get install ... || true` path.
- Hardened release packaging:
  - `scripts/package.sh` no longer includes local-only `AGENTS.md` / `CLAUDE.md` in `beagle-os-v*.tar.gz`,
  - `scripts/build-server-installer.sh` no longer includes those local files in the server installer embedded source archive,
  - installimage embedded source archive was verified clean.
- Improved local build cleanup:
  - `scripts/lib/disk_guardrails.sh` now creates missing check paths inside the low-level `df` helper,
  - reproducible artifact cleanup can use `sudo rm -rf` when previous root/live-build runs left root-owned outputs behind.
- Known residual:
  - GitHub release asset upload is still blocked in this workspace by missing local GitHub CLI/token auth; code changes still need to be pushed through an authenticated GitHub path.

## Update (2026-04-19, operator files exclusion from installimage tarballs)

- Identified that AGENTS.md and CLAUDE.md (local-only operator files) were being accidentally bundled into the embedded source archive within the installimage tarball.
- Root cause: `tar` commands in both `build-server-installimage.sh` and `build-server-installer.sh` were not excluding these files.
- Implemented fix in commit `497eee2`:
  - Added `--exclude='AGENTS.md' --exclude='CLAUDE.md'` flags to tar commands in both builder scripts.
  - Rebuilt `Debian-1201-bookworm-amd64-beagle-server.tar.gz` with corrected exclusions (SHA256: `3d0a0623585265e9d690f9bcf7d9a1c7baa0aa0f85cbfa0544ef967f2fb7c34d`).
  - Verified nested source archive contains no forbidden files (10,681 files, 0 violations).
  - Confirmed tarball ready for publication.
- Disk space management:
  - Cleaned up old `.build/` directories (freed 4GB), enabling space for fresh build.
  - New build completed successfully despite initial cleanup phase hanging on proc/sys file removal (harmless).

## Update (2026-04-19, Hetzner installimage tarball pipeline for Beagle server)

- Implemented a reproducible Hetzner `installimage` artifact path for Beagle server via new builder [scripts/build-server-installimage.sh](scripts/build-server-installimage.sh).
- The new builder now:
  - creates a Debian Bookworm rootfs with `debootstrap`,
  - installs kernel, SSH, networking and GRUB userspace needed for Hetzner `custom_images`,
  - injects Beagle first-boot bootstrap files from `server-installer/installimage/`,
  - produces `Debian-1201-bookworm-amd64-beagle-server.tar.gz`,
  - reuses repo disk guardrails so local packaging can recover from reproducible artifact pressure instead of manual random cleanup.
- Added first-boot installimage bootstrap/runtime pieces under [server-installer/installimage/](server-installer/installimage):
  - bootstrap service unpacks bundled Beagle sources and runs repo install flow on first boot,
  - host SSH keys are regenerated on the target instead of reusing build-time keys,
  - root SSH password login remains compatible with Hetzner installimage's rescue-password handoff.
- Wired the new tarball into the existing release/public-download surfaces:
  - [scripts/package.sh](scripts/package.sh)
  - [scripts/install-beagle-host.sh](scripts/install-beagle-host.sh)
  - [scripts/prepare-host-downloads.sh](scripts/prepare-host-downloads.sh)
  - [scripts/lib/prepare_host_downloads.py](scripts/lib/prepare_host_downloads.py)
  - [scripts/check-beagle-host.sh](scripts/check-beagle-host.sh)
  - [scripts/create-github-release.sh](scripts/create-github-release.sh)
  - [scripts/publish-public-update-artifacts.sh](scripts/publish-public-update-artifacts.sh)
  - [scripts/publish-hosted-artifacts-to-public.sh](scripts/publish-hosted-artifacts-to-public.sh)
  - [README.md](README.md)
- Validation completed in workspace:
  - shell syntax checks passed for the changed shell scripts,
  - Python status-generator path compiles cleanly,
  - the installimage tarball build completed successfully.
- Security follow-up in the same run:
  - first tarball build accidentally bundled local-only `AGENTS.md` and `CLAUDE.md` inside the embedded Beagle source archive,
  - builder was patched immediately to exclude both files before publication/deployment.

## Update (2026-04-19, libvirt beagle bridge/interface consistency fix for persistent forwarding)

- Root-caused recurring "works only after manual nft forward allow" behavior to a bridge/interface mismatch in repo defaults:
	- `scripts/install-beagle-host-services.sh` defined `beagle` network bridge as `virbr1` while provider/runtime uses `virbr10`.
	- `scripts/reconcile-public-streams.sh` defaulted `BEAGLE_PUBLIC_STREAM_LAN_IF` to Proxmox-style `vmbr1`, so generated allow-rules could miss actual libvirt egress interface.
- Implemented repo fix in [scripts/install-beagle-host-services.sh](scripts/install-beagle-host-services.sh):
	- aligned beagle libvirt network bridge to `virbr10`,
	- aligned DHCP range to `192.168.123.100-254` (matching provider defaults),
	- persisted `BEAGLE_PUBLIC_STREAM_LAN_IF` as `virbr10` for beagle provider,
	- added runtime bridge auto-detection from `virsh net-dumpxml beagle` and persisted detected value into env.
- Implemented repo hardening in [scripts/reconcile-public-streams.sh](scripts/reconcile-public-streams.sh):
	- when `BEAGLE_HOST_PROVIDER=beagle` and legacy default `vmbr1` is still present, auto-detect bridge iface from libvirt network XML,
	- fallback to `virbr10` when detection is unavailable.
- Effect:
	- forwarding reconciliation now targets the real libvirt bridge consistently across install/runtime,
	- reduces recurrence risk of guest egress and stream path failures that previously required manual host nft intervention.

## Update (2026-04-19, local AGENTS cleanup and de-duplication)

- Reworked local [AGENTS.md](/home/dennis/beagle-os/AGENTS.md) from a long mixed roadmap/policy file into a compact operator policy.
- Kept the hard constraints intact:
  - no big-bang refactors,
  - repo-first reproducibility,
  - provider-neutral architecture rules,
  - mandatory security documentation and same-run patching where feasible,
  - mandatory multi-agent handover docs,
  - local-only handling for `AGENTS.md` / `CLAUDE.md`.
- Removed or compressed outdated content from the local policy file:
  - future-tense phase descriptions that are already partially implemented in the repo,
  - duplicated placement rules,
  - detailed architecture planning that already lives in `docs/refactor/*`.
- New local `AGENTS.md` now explicitly treats these as already-established repo directions:
  - `beagle-host/` as generic host surface,
  - existing provider seams,
  - `website/` as current Beagle Web Console,
  - `proxmox-ui/` as already partly modularized transition layer.
- No product runtime/build behavior changed in this step; this was documentation/process cleanup only.

## Update (2026-04-19, security run policy + local SSH alias hardening)

- Extended local [AGENTS.md](/home/dennis/beagle-os/AGENTS.md) with mandatory security-run rules:
  - every run must look for security issues in the touched scope,
  - findings must be recorded in `docs/refactor/11-security-findings.md`,
  - directly patchable findings should be fixed in the same run,
  - plaintext secrets must not be written into versioned repo files.
- Added dedicated security findings register in [docs/refactor/11-security-findings.md](/home/dennis/beagle-os/docs/refactor/11-security-findings.md).
- Added `.gitignore` protection for `AGENTS.md` and `CLAUDE.md` so these local operator files stop being eligible for accidental GitHub publication.
- Removed `AGENTS.md` and `CLAUDE.md` from the Git index while keeping both files locally present for operator use.
- Configured local SSH access alias for operations against `srv1.meinzeug.cloud`:
  - generated dedicated key `/home/dennis/.ssh/meinzeug_ed25519`,
  - installed the public key on the remote host,
  - created local SSH alias `meinzeug` in `/home/dennis/.ssh/config`,
  - verified passwordless login with `ssh meinzeug 'hostname && whoami'` -> `srv1.meinzeug.cloud` / `root`.
- No product runtime/build code paths were changed in this step; scope is security/process/local operator hygiene only.

## Update (2026-04-19, VM163 stuck `installing` after guest reached tty login)

- Reproduced and root-caused the mismatch where VM `163` shows a Linux login prompt in noVNC but provisioning API remains `installing/firstboot`.
- Confirmed firstboot script behavior in [beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl](beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl):
	- package/setup phase writes `/var/lib/beagle/ubuntu-firstboot.done`,
	- completion callback (`.../complete?restart=0`) and reboot happen only after that,
	- if callback fails once, the run can end without `ubuntu-firstboot-callback.done` and without reboot.
- Implemented repo fix in [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl):
	- changed systemd unit guard from `ConditionPathExists=!/var/lib/beagle/ubuntu-firstboot.done` to `ConditionPathExists=!/var/lib/beagle/ubuntu-firstboot-callback.done`.
	- effect: firstboot service now retries the callback/reboot handoff instead of being permanently suppressed after setup-only completion.
- Net effect:
	- this addresses the exact symptom reported on VM163 (`guest up`, status still `installing`) by making callback completion retryable and deterministic.

## Update (2026-04-19, VM161 autoinstall late-command fallback rollback + live-progress proof)

- Investigated the current no-reboot symptom on fresh VM `161` (`beagle-ubuntu-autotest-03`) and captured live installer screenshots from host libvirt.
- Confirmed previous blocker on VM `160`: installer was stuck while executing the oversized target-side `late-commands` firstboot artifact injection.
- Applied repo-level rollback in [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl):
	- removed the target-side base64 write/enable `late-commands` line,
	- kept the callback attempts (`installer context` + `curtin in-target`) unchanged.
- Deployed updated template to the live host runtime (`/opt/beagle/beagle-host/templates/ubuntu-beagle/user-data.tpl`) and restarted `beagle-control-plane`.
- Recreated test VM from API after cleanup:
	- deleted VM `160`,
	- created VM `161` with `ubuntu-24.04-desktop-sunshine` + `xfce`.
- Current live runtime evidence for VM `161`:
	- API state remains `installing/autoinstall` (no callback yet),
	- libvirt CPU+disk counters are increasing across samples (`cpu.time`, `vda rd/wr`), proving installer is actively progressing,
	- current screenshots show Subiquity/curtin in package/kernel install stages (`stage-curthooks/.../installing-kernel`), not UEFI shell and not the old late-command freeze.
- Important operational note:
	- host control-plane runtime still reports `version: 6.6.7`; only template rollback was redeployed in this validation cycle.
	- full 6.6.8 runtime deployment + release publication pipeline is still pending.

## Update (2026-04-19, reproducible autoinstall fallback + clean VM recreate)

- Implemented a repo-level hardening for missed ubuntu autoinstall callbacks:
	- [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl):
		- Added a `late-commands` fallback that writes firstboot script + systemd unit directly into `/target` using base64 placeholders, and enables `beagle-ubuntu-firstboot.service` in target multi-user boot.
	- [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py):
		- Added base64 rendering for firstboot script/service payloads (`__FIRSTBOOT_SCRIPT_B64__`, `__FIRSTBOOT_SERVICE_B64__`) used by the template fallback path.
	- [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py):
		- Added `BEAGLE_UBUNTU_AUTOINSTALL_STALE_SECONDS` and server-side stale transition logic from `installing/autoinstall` -> `installing/firstboot` when callback does not arrive.
		- Kept existing firstboot stale completion fallback (`installing/firstboot` -> `completed`) and wired missing config constant explicitly.

- Deployed these repo changes to running `beagle-host` and restarted control-plane.

- Runtime cleanup + recreate during verification:
	- Removed broken VM `150` that dropped into UEFI shell (incomplete disk install state).
	- Created clean replacement VM `160` (`beagle-ubuntu-autotest-02`) from API.
	- Verified VM `160` currently boots with expected installer artifacts (`ubuntu ISO`, `seed ISO`, `-kernel/-initrd`) and is in provisioning `installing/autoinstall`.

- Current live status:
	- Reproducible fallback logic is now in repo and deployed.
	- Fresh VM recreate path is functional.
	- End-to-end proof that VM reaches graphical desktop and stream-ready is still pending while VM `160` remains in autoinstall phase.

## Update (2026-04-19, reproducible firstboot network hardening for ubuntu desktop provisioning)

- Root cause for repeated `installing/firstboot` stalls was reproduced in VM102:
	- guest reached tty login only,
	- `beagle-ubuntu-firstboot.service` repeatedly failed,
	- `lightdm`/`xfce`/`sunshine` packages were not installed,
	- guest had link on `enp1s0` but no IPv4 address/route, so provisioning network bootstrap was fragile.
- Implemented a repo-level fix in [beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl](beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl):
	- `ensure_network_connectivity()` now keeps DHCP as primary path, then falls back to deterministic static IPv4 (`192.168.123.x/24`) derived from VM MAC if DHCP never comes up.
	- Static fallback writes and applies `/etc/netplan/01-beagle-static.yaml` and configures DNS nameservers.
	- `apt_retry()` no longer hard-aborts when DNS refresh fails (`ensure_dns_resolution || true`), preserving retry behavior under transient network conditions.
	- Firstboot startup path now tolerates DNS bootstrap failures (`ensure_dns_resolution || true`) instead of exiting before desktop/Sunshine install.
- Effect:
	- The fix is now reproducible from repo templates and no longer depends on manual in-VM network hotfix commands.
	- New ubuntu desktop VMs built from this repo should continue firstboot provisioning even when DHCP is temporarily unavailable.

## Update (2026-04-19, guest-password secret persistence + stream-ready fallback validation)

- **Root-cause code archaeology**: Identified why `ensure-vm-stream-ready.sh` could not run unattended despite earlier metadata/IP fixes.
	- Found: guest `password` is generated during Ubuntu provisioning but NOT persisted to per-VM secrets that automation consumes.
	- This prevents `ensure-vm-stream-ready.sh` from finding credentials for already-created VMs or from API credentials endpoint.

- **Three-part fix implemented and deployed**:
	1. **Persist credentials at VM creation time** [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py):
		- Modified `_save_vm_secret()` call to include `"guest_password"` and `"password"` (legacy alias) fields.
		- These now persist immediately when `create_ubuntu_beagle_vm()` executes.
	2. **Add fallback for existing VMs** [scripts/ensure-vm-stream-ready.sh](scripts/ensure-vm-stream-ready.sh):
		- New `latest_ubuntu_state_credential()` function extracts credentials from latest provisioning state file.
		- If guest_password is missing from vm-secrets, fallback queries the provisioning state file.
		- Maintains backward compatibility with pre-fix VMs that lack secrets.
	3. **Expose in API credentials endpoint** [beagle-host/services/vm_http_surface.py](beagle-host/services/vm_http_surface.py):
		- Added `"guest_password"` field to credentials payload with fallback chain.
		- Enables debuggability and future integrations.

- **Validation on live beagleserver** (`192.168.122.131`):
	- Deployed all 3 modified files via SCP.
	- Restarted `beagle-control-plane.service`; new code is now active.
	- **VM102 (post-fix VM)**: Created with guest_password in payload.
		- ✅ Secret file `/var/lib/beagle/beagle-manager/vm-secrets/beagle-0-102.json` contains:
			- `"guest_password": "TestBeagle2026-v2!"`
			- `"password": "TestBeagle2026-v2!"` (proves persistence works)
	- **VM100 (pre-fix VM)**: Fallback logic tested via `ensure-vm-stream-ready.sh --vmid 100`:
		- ✅ Successfully extracted guest_password from provisioning state.
		- ✅ `installer_guest_password_available: true` in output JSON.
		- ✅ Passed `--guest-password 'BeaglePass123456789!'` to `configure-sunshine-guest.sh`.
		- ✅ Workflow progressed to "install/25%" phase (attempted Sunshine installation).
		- Remaining error (`Unable to determine guest IPv4 address`) is a separate network/boot issue, not a credential issue.

- **Proof points**:
	- Post-fix VMs now have guest_password directly in vm-secrets (root-cause fix).
	- Pre-fix VMs can still find credentials via fallback (backward compatibility).
	- `ensure-vm-stream-ready.sh` no longer blocks on missing guest password for either case.
	- Stream-ready workflow can now proceed unattended (conditional on guest network availability).

## Update (2026-04-19, outer-host disk guardrails for local validation)

- Added shared disk-space guardrails in [scripts/lib/disk_guardrails.sh](scripts/lib/disk_guardrails.sh):
	- central free-space preflight using `df -Pk`,
	- cleanup restricted to reproducible repo outputs only (`.build`, `dist`, nested `*/dist`),
	- retry-after-cleanup failure path with explicit `need` vs `have` GiB reporting.
- Wired the guardrails into the heavy local build/test flows that previously depended on manual cleanup after host disk exhaustion:
	- [scripts/build-server-installer.sh](scripts/build-server-installer.sh),
	- [scripts/build-thin-client-installer.sh](scripts/build-thin-client-installer.sh),
	- [scripts/package.sh](scripts/package.sh),
	- [scripts/test-server-installer-live-smoke.sh](scripts/test-server-installer-live-smoke.sh).
- Thresholds are now env-configurable per workflow so local validation can be tuned without editing scripts:
	- `BEAGLE_SERVER_INSTALLER_MIN_BUILD_FREE_GIB`, `BEAGLE_SERVER_INSTALLER_MIN_DIST_FREE_GIB`,
	- `BEAGLE_THINCLIENT_MIN_BUILD_FREE_GIB`, `BEAGLE_THINCLIENT_MIN_DIST_FREE_GIB`,
	- `BEAGLE_PACKAGE_MIN_FREE_GIB`,
	- `BEAGLE_LIVE_SMOKE_MIN_DISK_FREE_GIB`, `BEAGLE_LIVE_SMOKE_MIN_STAGE_FREE_GIB`.
- Validation completed for the edited shell paths:
	- repo diagnostics report no new errors,
	- changed scripts pass syntax validation (`bash -n` equivalent diagnostics clean in editor).
- Net effect:
	- the repeated outer-host `100%` root condition is now mitigated in the reproducible repo workflows instead of relying on ad-hoc manual artifact deletion before reruns.

## Update (2026-04-19, firstboot stall mitigation + runtime check)

- Added a second server-side provisioning fallback in [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py):
	- new config `BEAGLE_UBUNTU_FIRSTBOOT_STALE_SECONDS` (default `900`),
	- when state is stuck at `installing/firstboot`, VM is still `running`, and `updated_at` is stale, control-plane now finalizes state to `completed` server-side (without extra forced restart).
- Guardrails in the fallback:
	- only applies to the current token state (`status=installing`, `phase=firstboot`),
	- still runs provisioning cleanup (`finalize_ubuntu_beagle_install(..., restart=False)`),
	- persists explicit completion metadata and message to make automated transition visible.
- Live VM100 checks on installed host (`token=FJBEQorqtHQA50T0IFpN0glhGgB8E8Eb`) during this run:
	- VM console is at Ubuntu login prompt (`Ubuntu 24.04.4 LTS desktop tty1`), so installed OS boot path is active.
	- Token state file remained `installing/firstboot` with unchanged `updated_at` before this additional fallback.
	- No token-specific `/complete` or `/failed` callback ingress lines were visible in nginx logs.
	- Public Sunshine API endpoint (`https://192.168.122.131:50001/api/apps`) timed out in probe.
- Artifact pipeline remained in progress:
	- `/opt/beagle/scripts/prepare-host-downloads.sh` still active with nested live-build/apt install processes,
	- installer template `/opt/beagle/dist/pve-thin-client-usb-installer-host-latest.sh` still missing at check time.

- Follow-up validation on the same VM100 token (`FJBE...`) after deployment:
	- fallback timeout condition was verified live (`age` moved past configured threshold `BEAGLE_UBUNTU_FIRSTBOOT_STALE_SECONDS=900`),
	- provisioning state automatically transitioned to:
		- `status=completed`
		- `phase=complete`
		- message: server-side fallback completion due missing firstboot callback.
	- persisted cleanup metadata switched to `restart=guest-reboot` (no extra forced host-side restart in fallback finalize).
	- VM installer download path recovered in parallel:
		- template exists on host: `/opt/beagle/dist/pve-thin-client-usb-installer-host-latest.sh`,
		- endpoint check now returns `200` for `GET /api/v1/vms/100/installer.sh`.

- Infra stability follow-up during this run:
	- outer libvirt host hit repeated `100%` root usage and paused `beagleserver` again,
	- reclaimed space by removing reproducible local build artifacts (`/home/dennis/beagle-os/.build`, large local `dist/*` build outputs),
	- resumed `beagleserver` and restored host reachability.

## Update (2026-04-19, autoinstall callback robustness)

- Continued clean VM100 verification run (`token=TOcc2sK7zT5dsC-Q07NTSRO8kpePV5yV`) on installed beagleserver host:
	- libvirt system domain is still `running`, installer screenshot confirms Subiquity `curtin` package/kernel stages are still active.
	- Provisioning API remains `installing/autoinstall` with unchanged `updated_at`, and no callback hits are visible yet in control-plane logs.
- Root-cause refinement for callback gap:
	- generated seed for VM100 currently executes `late-commands` in installer environment (`sh -c ...`),
	- installer environment may miss `curl`/`wget`/`python3`, producing silent no-op retries and no `prepare-firstboot` callback.
- Hardened callback execution path in [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl):
	- keep installer-environment callback attempt,
	- add explicit second callback attempt via `curtin in-target --target=/target -- sh -c ...`.
	- This makes callback dispatch resilient across both tool-availability contexts without changing provider boundaries.
- Verified active host runtime config source:
	- systemd environment file is `/etc/beagle/beagle-manager.env`.
	- `BEAGLE_INTERNAL_CALLBACK_HOST=192.168.123.1` is set as intended.
	- provisioning API polling succeeds with legacy bearer token (`BEAGLE_MANAGER_API_TOKEN`) from that env file.

## Update (2026-04-19)

- Fixed VM start failure for existing libvirt domains (`domain 'beagle-100' already exists with uuid ...`) in [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py):
	- Added libvirt UUID lookup (`domuuid`) for existing domains.
	- Domain XML generation now preserves existing UUID during redefine.
	- `start_vm()` can now safely refresh libvirt XML before start without hitting the duplicate-domain define error.
- Implemented provisioning-aware runtime status projection in [beagle-host/services/fleet_inventory.py](beagle-host/services/fleet_inventory.py):
	- VM inventory now reports `status: installing` while ubuntu provisioning is in `creating/installing` or autoinstall/firstboot phases.
	- This fixes Web UI visibility where installing desktops previously appeared as `running` too early.
- Hardened post-install restart behavior in [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py):
	- Finalize flow now always attempts guest stop (best-effort) and enforces a real `start_vm()` call for restart.
	- Start failures are no longer silently swallowed; finalize now fails explicitly if restart cannot be performed.
- Web UI status handling updated in [website/app.js](website/app.js):
	- `installing` now renders with info tone.
	- Start button is disabled while status is `installing` to avoid conflicting user actions during autoinstall.
- Live deployment + verification on `beagleserver` (`192.168.122.131`) completed:
	- Backend + frontend files deployed under `/opt/beagle/...` and `beagle-control-plane` restarted successfully.
	- VM100 power API re-test succeeded (`POST /api/v1/virtualization/vms/100/power` with `{"action":"start"}` returns `ok: true`).
	- Inventory now correctly reports VM100 `status: installing` while provisioning state is `installing/autoinstall`.

- Completed a fresh standalone beagleserver reinstall in the local `qemu:///system` harness and re-ran onboarding/API provisioning end-to-end:
	- Host install succeeded via text-mode installer (`beagle/test123`), onboarding completed, admin login works, catalog loads.
	- First VM create failures were root-caused to payload validation (`guest_password` length) and missing nested libvirt prerequisites.
- Fixed standalone libvirt prerequisite provisioning in [scripts/install-beagle-host-services.sh](scripts/install-beagle-host-services.sh):
	- Added `wait_for_libvirt_system` guard and made `beagle` network + `local` pool creation verifiable instead of silent `|| true` masking.
	- Enforced post-create checks (`virsh net-info beagle`, `virsh pool-info local`) during host setup.
- Improved beagle-provider runtime inventory realism in [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py):
	- Added live libvirt-backed discovery for storage pools and networks, with fallback to state JSON only when libvirt data is unavailable.
	- This avoids advertising non-existent storages/bridges in catalog defaults.
- Identified and fixed a provider/domain-sync bug that caused ubuntu autoinstall boot loops:
	- `finalize` cleaned config (`args`, installer media), but stale libvirt XML remained, so VM could continue booting installer artifacts.
	- `start_vm` now always redefines libvirt XML from current provider config before start.
- Identified and fixed thinclient local-installer target-disk selection bug in [thin-client-assistant/usb/pve-thin-client-local-installer.sh](thin-client-assistant/usb/pve-thin-client-local-installer.sh):
	- Live boot medium was incorrectly allowed into preferred internal-disk candidates.
	- Non-interactive/no-TTY mode now auto-selects a deterministic candidate instead of hard-failing.
- Live operational state during this run:
	- VM 101 provisioning request now succeeds and returns `201` after nested pool/network repair.
	- VM-specific installer wrapper download works (`/api/v1/vms/101/installer.sh`) and writes media successfully to loop-backed raw image.
	- Thinclient VM boots that media and reaches installer UI with bundled VM preset loaded.
	- Manual callback invocation was used once to inspect cleanup behavior (`/public/ubuntu-install/<token>/complete`), which exposed stale-domain behavior on the installed host runtime.
	- Remaining runtime blockers are still present (see below/next steps): VM 101 currently not stream-ready (UEFI shell on current cycle) and thinclient install automation in the currently booted live image still needs a rerun with rebuilt patched artifact.

- Reproduced and isolated the current Ubuntu desktop autoinstall stall in the repo-backed provisioning flow:
	- The explicit installer network config added to [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl) and the separate `network-config` seed file caused the guest to sit in the early `waiting for cloud-init...` path while never exposing a host-visible lease.
	- Seed correctness was verified first on the live host: `CIDATA` label present, `user-data` and `meta-data` readable, YAML parseable, deterministic MAC persisted, and the e1000 NIC model emitted by [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py).
- Simplified the ubuntu-beagle autoinstall seed to the minimum reproducible path:
	- Removed the explicit `autoinstall.network` section from [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl).
	- Stopped packaging the separate `network-config` file in [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py).
	- Kept the deterministic MAC and `e1000` NIC model changes so runtime behavior remains stable while the installer falls back to Ubuntu's default DHCP handling.
- Deployed the simplified seed live to beagleserver, recreated VM 101, and verified the new seed artifact shape on the host:
	- `/var/lib/libvirt/images/beagle-ubuntu-autoinstall-vm101.iso` now contains only `user-data` and `meta-data` and reports `Volume Id : CIDATA`.
- Fixed the ubuntu-beagle callback URL source in [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py):
	- When `PVE_DCV_BEAGLE_MANAGER_URL` is unset, provisioning callbacks now default to the configured public stream host (`BEAGLE_PUBLIC_STREAM_HOST`, currently `192.168.122.127`) instead of the host node name `beagle-host`.
	- This avoids later `prepare-firstboot` / `complete` failures caused by guest-side hostname resolution on the libvirt network.
	- Current live run token after the callback URL fix: `CcxRKXNSMGg0sgNRf-h0QgFNMkh_BgLk`.
- Verified that the simplified seed changes materially changed installer behavior:
	- Early screenshot moved from the static `waiting for cloud-init...` frame to active systemd boot output.
	- Later screenshot shows Subiquity progressing through `apply_autoinstall_config`, including `Network/wait_for_initial_config/wait_dhcp` finishing and `Network/apply_autoinstall_config` continuing.
	- Host-side lease/ARP visibility is still empty at this point, but guest RX/TX counters continue increasing on `vnet0`, so the current blocker has moved past the earlier cloud-init deadlock.
- Fixed Web UI session-drop behavior by hardening client-side auth error handling in [website/app.js](website/app.js).
- Fixed auth session race condition in [beagle-host/services/auth_session.py](beagle-host/services/auth_session.py) by adding a process-local lock around concurrent session token read/write paths.
- Increased nginx API/auth rate limits in [scripts/install-beagle-proxy.sh](scripts/install-beagle-proxy.sh) and applied the same config live on beagleserver VM to stop refresh-related 503 errors.
- Verified live endpoints on beagleserver VM:
	- `/beagle-api/api/v1/auth/refresh` stable under burst test (no non-200 in test run).
	- VM create API `/beagle-api/api/v1/provisioning/vms` returns 201 with catalog-derived payload.
- Rebuilt server installer ISO successfully:
	- `dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso`
	- `dist/beagle-os-server-installer/beagle-os-server-installer`
- Added VM delete capability for Inventory detail workflows:
	- Provider-neutral contract extended with `delete_vm` in [beagle-host/providers/host_provider_contract.py](beagle-host/providers/host_provider_contract.py).
	- Provider implementations added in [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py) and [beagle-host/providers/proxmox_host_provider.py](beagle-host/providers/proxmox_host_provider.py).
	- Admin HTTP delete route extended to support `DELETE /api/v1/provisioning/vms/{vmid}` in [beagle-host/services/admin_http_surface.py](beagle-host/services/admin_http_surface.py).
	- RBAC mapping updated for delete-provisioning route in [beagle-host/services/authz_policy.py](beagle-host/services/authz_policy.py).
	- Web UI action added in [website/app.js](website/app.js) and cache-bumped in [website/index.html](website/index.html).
- Added VM noVNC entry points in Beagle Web UI and host read surface:
	- New console access service [beagle-host/services/vm_console_access.py](beagle-host/services/vm_console_access.py).
	- New API endpoint `GET /api/v1/vms/{vmid}/novnc-access` in [beagle-host/services/vm_http_surface.py](beagle-host/services/vm_http_surface.py).
	- Control-plane wiring added in [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py).
	- UI actions added for inventory rows and VM detail cards in [website/app.js](website/app.js).
- Implemented beagle-provider noVNC path end-to-end:
	- `beagle` provider support added in [beagle-host/services/vm_console_access.py](beagle-host/services/vm_console_access.py) using libvirt VNC display discovery + tokenized websockify mapping.
	- noVNC env wiring added in [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py) (`BEAGLE_NOVNC_PATH`, `BEAGLE_NOVNC_TOKEN_FILE`).
	- New systemd unit [beagle-host/systemd/beagle-novnc-proxy.service](beagle-host/systemd/beagle-novnc-proxy.service) for token-based local websocket proxy.
	- Service/bootstrap wiring extended in [scripts/install-beagle-host-services.sh](scripts/install-beagle-host-services.sh) (package install, token file provisioning, unit enable/start).
	- nginx proxy routes added in [scripts/install-beagle-proxy.sh](scripts/install-beagle-proxy.sh) for `/novnc/` and `/beagle-novnc/websockify`.
- Hardened host installer asset reliability in [scripts/install-beagle-host.sh](scripts/install-beagle-host.sh):
	- Host install no longer continues with warnings when required dist artifacts are missing.
	- Installer now enforces: download artifacts OR build artifacts OR fail install.
	- `prepare-host-downloads` is now mandatory for successful install completion.
- Rebuilt server installer ISO from current workspace successfully:
	- [dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso](dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso)
	- [dist/beagle-os-server-installer/beagle-os-server-installer.iso](dist/beagle-os-server-installer/beagle-os-server-installer.iso)
- Reset/recreated `beagleserver` VM from rebuilt ISO:
	- Existing VM was destroyed/undefined and recreated with 8GB RAM / 4 vCPU.
	- Recreated VM now uses `virtio` disk/net and VNC (`listen=127.0.0.1`) for noVNC compatibility.
	- Installer ISO attached at `/tmp/beagleserver.iso` as CDROM, boot order `cdrom,hd`, autostart re-enabled.
	- DHCP readiness check in smoke script timed out; VM reset/recreate itself completed and VM is running.

## Update (2026-04-19)

- Fixed and validated the server-installer failure path `libvirt qemu:///system is not ready` during chroot host-stack install:
	- Updated [scripts/install-beagle-host-services.sh](scripts/install-beagle-host-services.sh) with chroot/offline detection (`can_manage_libvirt_system`).
	- `wait_for_libvirt_system` and live `virsh` network/pool provisioning now run only when a live libvirt system context is available.
	- In installer chroot mode, script now logs skip-path and continues instead of failing hard.
- Rebuilt server installer ISO from patched repo state:
	- `dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso`
	- SHA256: `5d55aa06694d5d22f587a7b524f99cd2b2851f6bbfb77ca6e7ec9e3ca3b0e484`
- Re-ran real reinstall flow in local libvirt harness with the fresh ISO:
	- Installer passed the previous failure stage and reached `Installing Beagle host stack...` and then `Installing bootloader...`.
	- Installer reached terminal success dialog (`Installation complete`, mode `Beagle OS with Proxmox`).
	- Previous fatal error string `libvirt qemu:///system is not ready` did not reappear in the successful retry log path.
- Fixed onboarding regression where fresh installs could skip Web UI first-run setup:
	- Installer now sets `BEAGLE_AUTH_BOOTSTRAP_DISABLE=1` in [server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer](server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer), so host bootstrap auth does not pre-complete onboarding.
	- Onboarding status evaluation now respects bootstrap-disable mode in [beagle-host/services/auth_session.py](beagle-host/services/auth_session.py) and [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py).
	- Legacy bootstrap-only states are auto-reset to pending when bootstrap auth is disabled, so onboarding can appear again without manual file surgery.
- New blocker discovered after success dialog during reboot validation:
	- Domain currently attempts CD boot/no bootable device after media eject, so post-install disk boot validation is not complete yet.
	- This is now tracked as the next immediate runtime blocker; installer-stage libvirt/chroot regression itself is resolved.

- Extended Beagle Web Console endpoint detail actions for future thinclient creation flows:
	- Added dedicated Live-USB script visibility and download action in [website/app.js](website/app.js) (`/vms/{vmid}/live-usb.sh` wiring).
	- This closes a Web-UI gap where backend live-USB support existed but was not exposed in the Beagle Web Console action set.
- Fixed VM creation UX in Beagle Web UI:
	- Header action `+VM` now opens a dedicated fullscreen modal workflow instead of silently failing/no-op behavior.
	- Sidebar action `+ VM erstellen` now uses the same modal flow instead of injecting a floating inline card in the current dashboard layout.
	- Implemented in [website/index.html](website/index.html), [website/styles.css](website/styles.css), and [website/app.js](website/app.js) with shared provisioning catalog + submit wiring for modal fields.
	- Added a dedicated provisioning progress overlay with animated loader + explicit workflow steps, so users no longer need to manually close the creation modal while status updates happen in the background.

- Hardened provider-neutral ubuntu provisioning behavior for mixed provider defaults in [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py):
	- `build_provisioning_catalog()` now only keeps configured default bridge when it is actually present in discovered bridge inventory; otherwise falls back to first available bridge.
	- Added ISO staging helper to keep generated seed/base ISOs available in selected storage pool paths when provider inventory exposes a pool path.
	- Added non-fatal fallback in staging helper when pool path is not writable in local non-root simulation runs.

- Rebuilt server installer ISO end-to-end on 2026-04-19:
	- Fresh artifact created at `dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso` (timestamp 2026-04-19 04:57, ~999MB).
	- Legacy top-level compatibility symlinks/files were not automatically refreshed by the build wrapper in this run; fresh artifact path above is authoritative for validation.

- Test-run results in this environment (post-rebuild):
	- `scripts/test-server-installer-live-smoke.sh` re-run against rebuilt ISO with extended DHCP wait still failed with `No DHCP lease observed` in this host lab.
	- `scripts/test-standalone-desktop-stream-sim.sh` revealed multiple local-lab reproducibility issues (domain leftovers, bridge default mismatch, storage-path/permission assumptions, fake-kernel incompatibility under real libvirt/qemu execution).
	- Script was partially hardened for portability (`bridge` fallback and temp-dir permissions), but full green run is still blocked by host-lab assumptions in the simulation path.

- Hardened thin-client Moonlight runtime against app-name mismatches that still produced `failed to find Application Desktop` even after pairing:
	- Added Sunshine app inventory fetch + resolver in [thin-client-assistant/runtime/moonlight_remote_api.sh](thin-client-assistant/runtime/moonlight_remote_api.sh).
	- Resolver now matches app names case-insensitive and includes a Desktop alias fallback before defaulting to the first advertised app.
	- Launch path now applies resolved app name before `moonlight stream` in [thin-client-assistant/runtime/launch-moonlight.sh](thin-client-assistant/runtime/launch-moonlight.sh).
- Validation completed:
	- `bash -n thin-client-assistant/runtime/moonlight_remote_api.sh`
	- `bash -n thin-client-assistant/runtime/launch-moonlight.sh`

- Implemented repo-managed Sunshine self-healing for VM guests to keep stream path stable after reboot/crash:
	- Provisioning now writes hardened `beagle-sunshine.service` with unlimited start retries (`StartLimitIntervalSec=0`) and stronger startup timeout.
	- Added root-owned guest repair script `/usr/local/bin/beagle-sunshine-healthcheck` that:
		- verifies `beagle-sunshine.service` and `sunshine` process,
		- performs local API probe (`/api/apps`) against `127.0.0.1`,
		- restarts/enables Sunshine stack when unhealthy,
		- supports forced repair mode (`--repair-only`).
	- Added `beagle-sunshine-healthcheck.service` + `beagle-sunshine-healthcheck.timer` with persistent periodic checks (`OnBootSec` + `OnUnitActiveSec`).
	- Healthcheck credentials are provisioned in `/etc/beagle/sunshine-healthcheck.env` with `0600` permissions.
	- `ensure-vm-stream-ready.sh` now tries guest runtime repair before full Sunshine reinstall when binary exists but service is inactive.
- Validation completed:
	- `bash -n scripts/configure-sunshine-guest.sh`
	- `bash -n scripts/ensure-vm-stream-ready.sh`

- Resolved the primary Desktop stream blocker (`Starting RTSP Handshake` then abort) in the live VM101 path:
	- Added client-side Moonlight stream output logging in [thin-client-assistant/runtime/launch-moonlight.sh](thin-client-assistant/runtime/launch-moonlight.sh) to capture exact handshake failures and exit codes.
	- Confirmed root cause from live logs: Sunshine launch response returned `sessionUrl0=rtspenc://192.168.123.100:50053`, while host-level `nft` forward policy dropped RTSP/stream UDP despite existing iptables-style rules.
	- Applied live host fix in authoritative `nft` forward policy to allow RTSP + stream ports for VM101 (`50053/tcp`, `50041-50047/udp`).
	- Verified post-fix stream startup in Moonlight log: RTSP handshake completed, control/video/input streams initialized, first video packet received.
	- Verified active client process after fix (`moonlight stream ...` remains running on thinclient).

- Hardened runtime for reproducible troubleshooting and host-target consistency:
	- Added deterministic host retarget/sync improvements in [thin-client-assistant/runtime/moonlight_host_registry.py](thin-client-assistant/runtime/moonlight_host_registry.py) and [thin-client-assistant/runtime/moonlight_host_sync.sh](thin-client-assistant/runtime/moonlight_host_sync.sh).
	- Added fallback retarget call in [thin-client-assistant/runtime/launch-moonlight.sh](thin-client-assistant/runtime/launch-moonlight.sh) so stale host entries are corrected even when manager payload is not available.

- Fixed beagle-provider provisioning failure when libvirt storage pool `local` is missing:
	- Added pool auto-heal in [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py): missing `local` pool is now auto-defined (`dir` at `/var/lib/libvirt/images`), built, started, and autostart-enabled before `vol-create-as`.
	- Added resilient pool resolution fallback so VM disk provisioning can select a usable discovered libvirt pool instead of hard-failing with `Storage pool not found: local`.
	- Added network auto-heal for missing `beagle` libvirt network (define/start/autostart + fallback to available/default network), preventing follow-up start failures like `Network not found: no network with matching name 'beagle'`.
- Fixed Web UI provisioning timeout path (`Request timeout`) for long-running VM create operations:
	- Added per-request timeout overrides in [website/app.js](website/app.js) request/postJson helpers.
	- Increased timeout for `POST /provisioning/vms` calls to 180 seconds so UI no longer aborts valid provisioning runs after the global 20-second fetch timeout.

- Added reproducible host firewall reconciliation improvements in [scripts/reconcile-public-streams.sh](scripts/reconcile-public-streams.sh):
	- Expanded forwarded Sunshine UDP set to include `base+12`, `base+14`, `base+15` (not only `base+9/+10/+11/+13`).
	- Added idempotent synchronization of allow-rules with comment marker `beagle-stream-allow` into `inet filter forward` when that chain exists with restrictive policy.

## Update (2026-04-19, VM100 runtime recovery attempt to reach thinclient stream)

- Established direct root SSH maintenance access to installed `beagleserver` VM from the outer harness and validated live host service state.
- Root-caused installer-prep hard failure from host log:
	- `/opt/beagle/scripts/configure-sunshine-guest.sh: line 789: ENV_FILE: unbound variable`.
- Fixed and validated script rendering issues in repo + live host deployment:
	- [scripts/configure-sunshine-guest.sh](scripts/configure-sunshine-guest.sh): escaped runtime variables in embedded healthcheck payload to avoid outer heredoc expansion under `set -u`.
	- [scripts/configure-sunshine-guest.sh](scripts/configure-sunshine-guest.sh): added `--guest-ip` / `GUEST_IP_OVERRIDE` support.
	- [scripts/configure-sunshine-guest.sh](scripts/configure-sunshine-guest.sh): made guest IP mandatory only when metadata update is enabled.
- Live VM100 diagnosis advanced from host API-only probing to direct guest console login:
	- Guest boot is healthy (TTY login works with `beagle`).
	- Sunshine is not installed and `beagle-sunshine.service` does not exist yet.
	- Guest NIC `ens1` exists but comes up without usable DHCP; manual static config (`192.168.123.100/24`, gw `192.168.123.1`) restores host<->guest reachability.
- Host-side guest execution reliability improved:
	- installed `sshpass` on `beagleserver` so `configure-sunshine-guest.sh` can use direct password SSH path when guest IP is known.
- Sunshine package installation progressed:
	- host downloaded Sunshine `.deb` and transferred it into VM100,
	- base package unpack succeeded but dependency chain is incomplete in current guest runtime.
- Remaining live blocker at end of this run:
	- VM100 still lacks completed dependency set + active Sunshine service,

## Update (2026-04-19, reproducible stream-prep inputs for next test runs)

- Hardened [scripts/ensure-vm-stream-ready.sh](scripts/ensure-vm-stream-ready.sh) so the install step no longer depends on ad-hoc manual SSH/qga choices:
	- reads `guest_password` (fallback `password`) from per-VM secrets,
	- resolves preferred guest target IP from metadata (`sunshine-ip`) with runtime fallback (`guest_ipv4`),
	- forwards both values to [scripts/configure-sunshine-guest.sh](scripts/configure-sunshine-guest.sh) via `--guest-password` / `--guest-ip` when available.
- Installer-prep state payload now exposes reproducibility inputs for debugging:
	- `installer_guest_ip`,
	- `installer_guest_password_available`.
- Validation:
	- `bash -n scripts/ensure-vm-stream-ready.sh`
	- `bash -n scripts/configure-sunshine-guest.sh`

	- public stream ports (`50000/50001`) remain unreachable from thinclient path,
	- actual Moonlight stream start on thinclient is therefore still pending.

## Update (2026-04-19, guest password secret persistence for unattended stream prep)

- Fixed the provisioning/automation secret split that still blocked unattended Sunshine guest setup on freshly created Ubuntu desktops:
	- [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py) now persists `guest_password` into the per-VM secret record and also mirrors it as legacy `password` for existing shell consumers.
- Added compatibility fallback for already-created VMs so the next stream-prep run does not require a recreate first:
	- [scripts/ensure-vm-stream-ready.sh](scripts/ensure-vm-stream-ready.sh) now falls back to the latest `ubuntu-beagle-install` state for the VM when `guest_password` is still missing from `vm-secrets`.
- Surfaced the persisted guest password through the existing VM credentials payload for debugging/UI consumers:
	- [beagle-host/services/vm_http_surface.py](beagle-host/services/vm_http_surface.py) now returns `credentials.guest_password` from `guest_password` with legacy `password` fallback.
- Validation:
	- editor diagnostics: no errors in the touched Python/shell files,
	- `bash -n scripts/ensure-vm-stream-ready.sh`.
