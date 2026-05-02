# Changelog

## v8.0.9 - 2026-05-02

- Fixed the GitHub release workflow so release-version bumps are committed back into `main` together with the synced repo metadata (`VERSION`, extension manifest, kiosk metadata and WebUI cache-busters) instead of drifting ahead only in the published release tag.
- Added a shared release-version sync helper and wired packaging to it so local builds and GitHub releases emit one consistent product version across host runtime, extension, kiosk and WebUI assets.
- Fixed Ubuntu Beagle Plasma Cyberpunk firstboot provisioning by embedding the required wallpaper asset into cloud-init write-files under `/var/lib/beagle/seed`, so recreated VMs like `vm100` no longer fail when cloud-init does not expose extra seed ISO files through `/var/lib/cloud/*`.
- Purged stale VM runtime artifacts on delete and explicit recreate (`endpoint` reports, installer-prep state, action queues, VM secrets and old ubuntu-beagle token states) so a deleted/recreated VMID does not inherit stale update/runtime metadata.

## v8.0.2 - 2026-05-02

- Synced the committed Beagle OS runtime version to `8.0.2` so repo, srv1 runtime and public release artifacts stop drifting apart.
- Clarified the Updates panel: it now shows the installed Beagle OS version directly and exposes installed/remote commit plus remote version details instead of presenting a commit hash as the primary version field.
- Extended repo auto-update status payloads with explicit `installed_version` and `remote_version` fields so runtime/UI consumers can render human-readable release state.

## v8.0 - 2026-04-27

- Added token-scoped installer run logging for generated Linux and Windows USB scripts. VM-specific installer and live-USB downloads now carry a short-lived write-only log token and post lifecycle events to the Beagle Control Plane without embedding admin credentials.
- Added `/api/v1/public/installer-logs` as the unauthenticated token intake and authenticated `GET /api/v1/installer-logs` read APIs for operators with `settings:read`, including redaction of sensitive payload keys before persistence.
- Hardened the USB writer scripts with non-blocking API log calls for script start, bootstrap, device listing, privilege escalation, dependency, asset, write, completion and failure stages.
- Promoted the public release line to `8.0` so GitHub and hosted artifacts no longer present the older `6.6.x` release as current.

## v6.7.0 - 2026-04-21

- Split the Beagle Web Console monolith into native ES modules under `website/ui/`, switched `website/index.html` to the new `website/main.js` entrypoint, and replaced the monolithic stylesheet with imported CSS partials under `website/styles/`.
- Fixed fresh-install onboarding so standalone hosts keep the mandatory first-run setup flow even when a bootstrap admin exists, and deployed the same correction to `srv1.beagle-os.com`.
- Hardened standalone TLS issuance in the Security settings flow by auto-installing `certbot` plus `python3-certbot-nginx`, adding explicit backend preflight checks, and executing `certbot` through a transient `systemd-run` context so Let's Encrypt works on hardened hosts.
- Extended refactor/go-future documentation for the executed WebUI split, strategic 7.0 planning wave, live host recovery work, onboarding fix, and the validated Let's Encrypt runtime path.

## v6.6.9 - 2026-04-19

- Added the corrected Hetzner `installimage` tarball to the public release line and published it beside the endpoint ISO, server installer ISO, USB bundles, source tarball and kiosk AppImage on `beagle-os.com`.
- Fixed first-boot standalone host bootstrap on minimal Debian installimage targets by running `apt-get update` before installing runtime packages and by failing visibly instead of swallowing missing-package errors.
- Hardened release/source packaging so local-only operator files (`AGENTS.md`, `AGENTS.md`) are excluded from the public source tarball, server installer embedded source bundle and Hetzner installimage embedded source bundle.
- Improved build cleanup guardrails so root-owned reproducible build directories from live/debootstrap runs can be removed through `sudo` when local disk pressure requires cleanup.
- Installed and updated the real Hetzner host `beagle-server` from the public installimage path, regenerated host-local download metadata and verified Control Plane, nginx downloads, libvirt/KVM and public checksums on version `6.6.9`.

## v6.6.8 - 2026-04-19

- Hardened Ubuntu desktop autoinstall recovery so missed installer callbacks no longer leave new desktop VMs permanently stuck in `installing/autoinstall`.
- Added target-side firstboot artifact fallback in cloud-init late-commands: generated seed now writes and enables `beagle-ubuntu-firstboot.service` directly in `/target` as a deterministic backup path.
- Extended control-plane stale-state handling with `BEAGLE_UBUNTU_AUTOINSTALL_STALE_SECONDS` to force server-side transition from `autoinstall` to `firstboot` when callbacks are missing.
- Kept and wired firstboot stale completion fallback to avoid indefinite `installing/firstboot` states.
- Improved local release/build stability with reusable disk-space guardrails and integrated checks in packaging and installer build scripts.
- Refreshed refactor handoff docs (`05-progress`, `06-next-steps`, `08-todo-global`) with live VM recreate validation status and remaining runtime validation steps.

## v6.6.7 - 2026-04-10

- Continued the provider-neutral refactor without breaking the active Beagle host deployment path. The host control plane now routes the remaining Ubuntu Beagle guest-exec flows and scheduled restart helper through `beagle-host/providers/beagle_host_provider.py` instead of shaping `qm guest exec`, `qm guest exec-status`, `qm start` and `qm stop` calls directly in `beagle-control-plane.py`.
- Finished the current host-provider lifecycle slice by giving `Beagle hostHostProvider` first-class helpers for guest bash execution, exec-status polling, script-text execution and delayed restart scheduling. This keeps the Beagle host-specific subprocess behavior in one provider file while the large control-plane HTTP entrypoint moves closer to orchestration-only behavior.
- Fixed the public release surface so `website/` ships in the versioned source tarball and `website/app.js` is part of project validation. That keeps the published source bundle aligned with the repo and stops the website from drifting outside the checked browser surfaces.
- Updated the mandatory refactor handoff set, provider-abstraction notes and architecture guidance so the next continuation step is clear: shrink `extension/content.js`, inventory direct script-side Beagle host couplings, and keep release/deploy verification explicit across `srv.thinover.net` and `beagle-os.com`.

## v6.6.6 - 2026-04-06

- Rebranded the full public Beagle OS surface around the new splash and transparent logo assets. The README, extension assets, website-facing repo assets, runtime wallpapers, Plymouth theme and Gaming kiosk backgrounds now share the same public branding.
- Refreshed the public website with a stronger poster-style landing page, a first-viewport showcase, a public marketing/media kit, wallpaper downloads and a unified visual shell across home, docs and product subpages.
- Added public legal and privacy pages plus a minimal site privacy notice banner for the marketing surface, while keeping the public site free of analytics and other non-essential tracking services.
- Removed public Google Fonts dependencies from the marketing pages and switched the live site to self-hosted web fonts so the public surface no longer leaks font requests to third-party servers by default.
- Promoted the current USB-writer fixes into the release line. The Linux USB helper now parses device candidates correctly again, and the Windows USB helper keeps the direct DiskPart path that was validated during the Windows test pass.
- Prepared the `6.6.6` release surface for fresh branded installer media: endpoint installer ISO, server installer ISO, USB helper scripts, public update metadata and the open-source kiosk AppImage all ship together from the same release line.

## v6.0.1 - 2026-04-06

- Scrubbed the public Beagle OS repository and website source of internal infrastructure references. Public-facing defaults, release metadata, install snippets, and website copy now reference `beagle-os.com` plus the public `github.com/meinzeug/beagle-os` repository without leaking internal hostnames or operator aliases.
- Moved remaining public artifact fallbacks away from hosted internal URLs and onto the public `beagle-os.com/beagle-updates` surface, including kiosk release metadata, server-installer source download defaults, and website installer examples.
- Refreshed the public website wording so the visible release narrative follows the new `6.x` open-source line instead of the older `5.2` SaaS-oriented product language.

## v6.0.0 - 2026-04-06

- Rebased the public Beagle OS release line onto a fully MIT-licensed repository. The root license now uses MIT, the Gaming kiosk source tree lives directly in the public repo, and the old closed-source and affiliate-only constraints are removed from the active product surface.
- Added the public `beagle-kiosk/` source tree to the release path and updated the repository packaging flow so the GitHub source tarball now includes the open kiosk, the endpoint image builder, and the new server-installer sources together.
- Added a new bootable `beagle-os-server-installer-amd64.iso` workflow that installs Debian Bookworm, adds Beagle host from the official Beagle host repository, prompts for hostname, Linux username, password, and target disk, and then installs Beagle from the public GitHub release source on top.
- Extended the packaging, host-download, GitHub release, and public artifact publication scripts so the server installer ISO is built on the dedicated release host, published alongside the endpoint ISO, exposed in `beagle-downloads-status.json`, and mirrored to `beagle-os.com`.
- Reworked the public website content for the open-source direction: the Gaming page now describes the public kiosk codebase, the Download page exposes the new server installer ISO, and the old dashboard/login/register entry points are redirected away from the marketing site.

## v5.2.31 - 2026-04-06

- Fixed the Beagle Fleet desktop cold-start regression on freshly installed thinclients. The Moonlight launcher no longer probes `PVE_THIN_CLIENT_MOONLIGHT_LOCAL_HOST` first when that address is only reachable through an upstream gateway, so endpoints outside the Beagle-side private subnet stop wasting startup time on dead `10.10.10.x` attempts before falling back to the real public Sunshine host.
- Verified the launcher fix live on the real VM100 thinclient at `192.168.178.92`: the desktop runtime dropped from the earlier `moonlight.start -> moonlight.exec` path of roughly 80 seconds down to about 6 seconds on the subsequent restart, while still connecting to the same public host `65.109.80.76:50100`.
- Fixed runtime config regeneration so Beagle no longer discards Sunshine bootstrap metadata and pinning material when `/usr/local/sbin/beagle-render-config` rewrites `/etc/pve-thin-client/`. The renderer now preserves Sunshine pinned pubkeys plus server name, stream port, unique ID and certificate fields, which keeps fresh Desktop images from regressing into the slow first-run bootstrap path after config refreshes.

## v5.2.30 - 2026-04-06

- Fixed the GeForce NOW handoff regression that could restart the full Gaming session shortly after GFN launched. The previous stream-optimization path terminated kiosk processes directly, which tore down the shared X11 session and caused `pve-thin-client-runtime.service` to restart on the real VM100 thinclient.
- Changed the streaming handoff to close the kiosk gracefully through the window manager first, instead of hard-killing the Electron processes. During an active GFN session the kiosk now exits cleanly, the runtime stays alive, and the kiosk supervisor waits until the stream ends before relaunching the kiosk.
- Added `wmctrl` to both the runtime image and the thin-client live-build package set so this graceful-close path is available after fresh installs and USB-based reinstalls as well.
- Verified the new handoff live on `192.168.178.92`: `pve-thin-client-runtime.service` stayed `active`, GeForce NOW continued running, and the runtime trace recorded `phase=streaming.kiosk-stop mode=graceful-close` instead of the earlier crash/restart sequence.
- Fixed the Beagle Fleet desktop-stream provisioning path for Ubuntu guest VMs. Newly configured Sunshine guests now install a real user-audio stack (`pipewire`, `pipewire-pulse`, `wireplumber`) instead of only `pulseaudio-utils`, enable those user services after LightDM autologin, and keep the Pulse socket available for Sunshine audio capture.
- Hardened the generated `beagle-sunshine.service` so Sunshine no longer starts before the guest desktop and audio session are actually ready. The unit now waits for the X11 display, X authority, user DBus runtime, Pulse socket and a connected XRandR output before launching Sunshine.
- Verified the VM100 fix live on the Beagle host side: Sunshine stopped reproducing the old `Unable to initialize capture method` failure, accepted real desktop streaming sessions from the thinclient again, and initialized audio capture with `sink-sunshine-stereo` plus `Opus initialized` instead of `Couldn't connect to pulseaudio`.
- Fixed Moonlight audio routing on the thinclient runtime. Desktop sessions now prefer the local PipeWire/Pulse path instead of forcing SDL and ALSA straight onto a hard-coded hardware PCM, and the generated ALSA default now points back at PipeWire when the plugin is installed. This keeps Beagle Fleet desktop streams compatible with real output selection on fresh installs instead of silently sending audio to the wrong low-level device.

## v5.2.29 - 2026-04-05

- Reduced GeForce NOW stream interference from local Beagle background work. The runtime GeForce NOW launcher now enters a dedicated stream mode that stops Beagle management timers and the kiosk catalog timer while a primary GeForce NOW session is active, then restores them automatically after the client exits.
- Changed the GeForce NOW runtime path to pause the kiosk sidecars themselves after handoff, instead of merely hiding the window. During active streaming the kiosk renderer and the interactive update monitor no longer keep consuming CPU in the background.
- Hardened `beagle-endpoint-report`, `beagle-endpoint-dispatch` and `beagle-runtime-heartbeat` so they self-suppress when a GeForce NOW stream session is already active, which closes the race window if one of those timers fires just as the stream starts.
- Verified the fix live on the real VM100 thinclient: timer units transitioned to `inactive` during the simulated stream mode and resumed afterward, while report/dispatch/heartbeat all wrote `skipped-streaming` status instead of doing normal work.

## v5.2.28 - 2026-04-05

- Fixed the Beagle OS Gaming boot path so fresh installs no longer stall before the kiosk appears. `beagle-kiosk-install --ensure` previously ran both the first-time GeForce NOW Flatpak installation and the initial `games.json` catalog refresh synchronously in the session startup path, which blocked `launch-session.sh` and left the screen sitting in openbox with no visible kiosk.
- Changed the kiosk ensure flow to keep those heavyweight tasks asynchronous. The kiosk binary now starts immediately after install, while GeForce NOW preparation and catalog refresh continue in the background and write to `/opt/beagle-kiosk/logs/gfn-install.log` and `/opt/beagle-kiosk/logs/catalog-refresh.log`.
- Verified the fix live on the real VM100 thinclient: after replacing the boot-time `beagle-kiosk-install`, killing the stuck synchronous installer, and letting the session resume, the Gaming boot started `/opt/beagle-kiosk/beagle-kiosk` successfully under X11 again.

## v5.2.27 - 2026-04-05

- Fixed the Gaming kiosk store refresh so Green Man Gaming lookup errors no longer collapse the catalog into an empty `games.json`. The updater now uses smaller GMG batches, recursively splits failing batches, and falls back to direct GMG search URLs when no exact store match is available.
- Changed kiosk catalog writes to an atomic replace flow and fixed the ownership model for `/opt/beagle-kiosk/`, `games.json`, `assets/` and `logs/` so the running `thinclient` kiosk session can refresh the catalog successfully from the UI without hitting permission errors.
- Verified the new catalog flow end-to-end on the real VM100 thinclient: `beagle-kiosk-install --ensure` now leaves `/opt/beagle-kiosk/` writable for the kiosk process, and the live catalog rendered successfully with 5335 entries after refresh.

## v5.2.26 - 2026-04-05

- Fixed fresh Beagle OS Gaming installs that booted into a missing kiosk even though `client_mode=gaming` was active. The packaged `/usr/local/sbin/beagle-kiosk-install` script had lost its executable bit inside the runtime image, so the gaming ensure step never ran, `/opt/beagle-kiosk/` was never created, and `beagle-kiosk-launch` stayed absent.
- Restored executable permissions for both shipped `beagle-kiosk-install` entrypoints used by runtime images and live-build output, so first-boot gaming sessions can install the kiosk payload, create `/usr/local/sbin/beagle-kiosk-launch`, and start the Electron kiosk automatically after installation.

## v5.2.25 - 2026-04-05

- Added a real Beagle OS Gaming store-catalog pipeline based on NVIDIA's official GeForce NOW supported-games feed plus live Green Man Gaming storefront search results. `update_catalog.py` now builds purchasable `games.json` entries from current GFN-compatible titles instead of relying on a static placeholder catalog.
- Added a manual catalog refresh action directly inside the kiosk UI so users can reload the GMG-backed game catalog on demand without reinstalling Beagle OS or waiting for the daily updater timer.
- Seeded the kiosk catalog automatically during kiosk installation and upgrade by running the catalog updater once after payload deployment. Fresh gaming installs therefore come up with a populated local `games.json` whenever catalog generation succeeds.
- Hardened the kiosk store flow for missing affiliate configuration. If `beagle-os.com/api/kiosk/affiliate-config` does not return active partner identifiers, store links stay functional in direct mode and the kiosk surfaces a non-blocking banner instead of disabling the catalog.

## v5.2.24 - 2026-04-05

- Fixed the remaining fresh-install GeForce NOW regression in Gaming boots. `beagle-kiosk-install --ensure` previously executed `install-geforcenow.sh` as `root`, which caused the persistent Flatpak user store under `/run/live/medium/pve-thin-client/state/gfn` to be populated with `root:root` files and directories. The next GeForce NOW launch then failed before `flatpak run` with permission errors inside the user repo.
- Changed both kiosk-install entrypoints to run the GeForce NOW ensure step as the runtime user (`thinclient`) with the matching `XDG_RUNTIME_DIR` and session-bus path, so boot-time kiosk preparation no longer corrupts the user Flatpak storage.
- Hardened the runtime storage preparation helper to recursively repair existing ownership drift inside the persistent GeForce NOW storage root before running Flatpak commands. Systems that already contain stale `root:root` files now self-heal instead of requiring a manual cleanup.

## v5.2.23 - 2026-04-05

- Fixed GeForce NOW launcher preparation when the runtime helper runs as `root` during kiosk install or boot-time ensure steps. The runtime ownership helper now creates and repairs user-facing GeForce NOW paths with `thinclient:thinclient` ownership instead of leaving files like `~/.local/share/applications/com.nvidia.geforcenow.desktop` and `~/.config/mimeapps.list` behind as `root:root`.
- Hardened `install-geforcenow.sh` to explicitly repair ownership and writability for the `thinclient` desktop-launcher files before writing URL-handler registrations. This prevents the gaming kiosk from failing immediately on `Mit GeForce NOW einloggen` after a fresh install, where the previous release could abort before `flatpak run` because the handler files were not writable by the session user.

## v5.2.22 - 2026-04-05

- Fixed Beagle OS Gaming installs that carried forward an old `GFN_BINARY=/usr/bin/GeForceNOW` or direct AppImage path in `/opt/beagle-kiosk/kiosk.conf`. `beagle-kiosk-install --ensure` now normalizes those legacy values back to the supported runtime launcher path (`/usr/local/lib/pve-thin-client/runtime/launch-geforcenow.sh`) instead of silently preserving a stale configuration.
- Applied the same kiosk-config normalization to the public `beagle-kiosk/INSTALL.sh` and the live-build copy used inside runtime images, so both fresh installs and already-installed gaming systems converge on the same launcher-based GeForce NOW path.
- Fixed the GeForce NOW URL-handler registration path so browser callbacks are written into the real `thinclient` desktop profile instead of `/root` or the temporary GFN storage home. This keeps the Chromium-to-GFN handoff working after login redirects on live gaming systems.

## v5.2.21 - 2026-04-05

- Fixed the GeForce NOW browser-to-app callback path in Beagle OS runtime builds. The runtime installer now registers a host-side `geforcenow://` URL handler for the `thinclient` user, writes the matching desktop and mime handler entries, and installs a per-user `xdg-open` wrapper that routes GeForce NOW callbacks through `gio open` instead of silently dropping them.
- Updated the GeForce NOW launcher so callback URLs received from Chromium are forwarded into `flatpak run`, while the runtime PATH now prefers the user-local wrapper directory. This allows NVIDIA login and subsequent entitlement redirects to return to the installed GeForce NOW client instead of reopening the kiosk without completing the handoff.
- Optimized `install-geforcenow.sh --ensure-only` for already-prepared systems by skipping redundant Flatpak installs when both the runtime and app are already present. Repeated kiosk or runtime launches therefore no longer stall on unnecessary GeForce NOW reinstall checks.

## v5.2.20 - 2026-04-05

- Fixed the Desktop Moonlight connect-host selection so `PVE_THIN_CLIENT_MOONLIGHT_LOCAL_HOST` is only preferred when the endpoint can reach that host directly without routing through an upstream gateway. Real thinclients on external LANs now choose the public Sunshine/Moonlight host first instead of stalling on an internal Beagle host-only address like `10.10.10.x`.
- Verified the live VM100 endpoint on `192.168.178.92` against this fix: after clearing the stale local-only host override, the desktop runtime paired successfully and started a real `moonlight stream 65.109.80.76:50100 Desktop` session again.

## v5.2.19 - 2026-04-05

- Changed the Beagle OS Gaming boot entry to use the normal thin-client runtime path instead of booting a separate `beagle-kiosk.target`. Gaming now comes up through the same stable X11/runtime pipeline as Desktop while still selecting `client_mode=gaming`, which makes SSH, management timers and runtime preparation available during Gaming boots as well.
- Added a root-side kiosk ensure step to `prepare-runtime.sh` for `KIOSK` mode so `/opt/beagle-kiosk/` and the launcher wrapper are prepared before the user session starts.
- Updated the runtime launcher to re-run `beagle-kiosk-install --ensure` as a best-effort safety net before entering the kiosk.
- Hardened the generated kiosk launcher script so Electron always starts in an explicit X11 environment, with a valid runtime directory, optional session D-Bus bootstrap via `dbus-run-session`, and Linux-safe flags (`--disable-gpu`, `--disable-gpu-compositing`, `--disable-dev-shm-usage`) that avoid the earlier Chromium GPU crash on the thinclient hardware.
- Changed `beagle-kiosk-install --ensure` to rewrite `launch.sh` even when the kiosk version is already current, so existing installations receive launcher fixes immediately instead of only on a version bump.

## v5.2.18 - 2026-04-05

- Fixed the remaining VM100 USB-install failure after successful GRUB installation. On the affected thinclient, `lsblk -no PARTN /dev/mmcblk0p2` returned a non-zero status under `set -o pipefail`, which previously aborted the installer inside `install_efi_boot_entry()` even though both BIOS and removable EFI bootloaders were already installed successfully.
- Added a robust EFI partition-number resolver with a sysfs fallback (`/sys/class/block/<part>/partition`) and changed missing partition-number detection from a fatal error to a warning, because the removable EFI fallback written by `grub-install --removable --no-nvram` is already sufficient for booting.

## v5.2.17 - 2026-04-05

- Stopped copying the entire temporary log directory back onto the FAT USB stick for every single log line. The installer now keeps detailed logs in RAM during execution and only flushes persisted snapshots explicitly, which makes post-failure USB logs much less likely to corrupt on abrupt exits or reboot loops.
- Added an explicit filesystem sync after persisted installer log snapshots are written to the USB stick so `LATEST.txt`, `session.env` and the copied log files survive the next reboot more reliably.
- Reduced overly chatty live-medium probe logging in the local USB installer so `local-installer.log` reaches the actual install stages instead of filling with repeated mount-candidate noise first.
- Made bootloader installation more tolerant on UEFI thin clients: legacy BIOS `grub-install` is now best-effort during EFI boots, the primary EFI `grub-install` no longer tries to write NVRAM implicitly, and an explicit `efibootmgr` failure is downgraded to a warning because the removable EFI fallback remains bootable.

## v5.2.16 - 2026-04-05

- Added unhandled-error logging to the local USB installer so the first uncaught failing command now records exit code, line number and shell command in `local-installer.log` before the installer exits.
- Wrapped the post-selection install steps with explicit command logging, including disk wipe, GPT partitioning, filesystem creation, target mounts, asset copy and bootloader installation. Future `preset install failed` runs will therefore show the exact failing operation instead of stopping after `prepare_install_assets`.
- Extended EFI helper logging so `mount efivarfs`, `efibootmgr` and `grub-install` failures are captured in the USB logs rather than disappearing from the post-mortem trace.

## v5.2.15 - 2026-04-05

- Fixed preset-based USB installs to prefer the payload already embedded on the USB stick instead of re-downloading the same `pve-thin-client-usb-payload-*.tar.gz` during installation. This removes an unnecessary online dependency from the actual disk-install step and avoids installer failures on low-RAM live systems where `/tmp` is a small tmpfs.
- Added direct extractor stderr logging for the remote payload path so any future tar/unpack failure is recorded in `local-installer.log` instead of collapsing into a generic `failed to extract` message.

## v5.2.14 - 2026-04-05

- Fixed the target-disk parser in the local installer so disks with an empty `MODEL` field no longer disappear from the candidate list. On affected thinclients the shell field splitting previously swallowed the built-in eMMC/NVMe entry, leaving only the USB stick visible and causing `No writable target disk found.` despite a valid internal target disk being present.
- Normalized `lsblk` removable-state parsing to `0/1` values instead of Python `True`/`False` strings, keeping the removable/USB preference logic stable across different devices and live environments.
- Excluded `mmcblk*boot*` and `mmcblk*rpmb` pseudo-devices from installer target selection so only real writable system disks are offered during Beagle OS installs.
- Applied the same robust block-device parsing to the USB writer utility to avoid repeating the empty-model parsing bug in installer media creation workflows.

## v5.2.13 - 2026-04-04

- Fixed a duplicate `candidate_live_devices()` override in the live installer menu. The later function definition still treated internal EFI `vfat` partitions as possible installer media and silently undid part of the `5.2.12` live-media fix. Both live-menu code paths now agree on explicit Beagle labels or removable/USB media only.

## v5.2.12 - 2026-04-04

- Fixed the installer success path so the live menu now preserves the real exit code of the local installer instead of always treating a failed preset install as successful. Errors like `No writable target disk found.` therefore no longer fall through to `Installation complete`.
- Reworked target-disk selection to prefer internal non-removable disks first and only fall back to removable/non-live media if no internal disk exists. This keeps a built-in NVMe/SATA drive selectable even if live-medium detection is imperfect.
- Removed the live-menu log-persistence heuristic that treated any internal EFI `vfat` partition as possible installer media, which could hide the real USB stick during log sync and diagnostics.

## v5.2.11 - 2026-04-04

- Fixed USB installer live-medium detection so a normal internal EFI `vfat` partition is no longer mistaken for the installer stick. Thinclients with one internal system disk plus one USB installer now keep the internal disk visible in the target-disk picker instead of failing with `No writable target disk found.`

## v5.2.10 - 2026-04-04

- Removed `whiptail` from the text-mode installer menu path entirely. When the USB stick boots with `pve_thin_client.installer_ui=text`, the main menu now uses a plain numbered TTY prompt, so `1 Start preset installation` is accepted reliably on problematic hardware and serial-like consoles.
- Added explicit live-menu selection logging (`main menu selection: ...`) so a failed keypress path can be distinguished from a later installer failure in the USB logs.

## v5.2.9 - 2026-04-04

- Reworked the text-mode preset installer to show plain numbered prompts for target-disk selection, streaming-mode selection and destructive confirmation instead of relying on nested `whiptail` screens after `Start preset installation`.
- Added visible step messages in the local installer (`Loading preset configuration`, `Detecting target disks`, `Preparing installation assets`) so a stalled install no longer looks like a dead black screen.
- Hardened USB log persistence by remounting the live medium read-write before falling back to a second mount, allowing installer sessions to leave diagnostics under `pve-thin-client/logs/` on sticks booted via the Debian live environment.

## v5.2.8 - 2026-04-04

- Fixed the preset-driven USB installer flow so `Start preset installation` now launches the fully interactive installer instead of re-entering the `--auto-install` fast path. Bundled VM installs therefore stop on the target-disk picker and wipe confirmation instead of behaving like a silent auto-run.
- Added persistent installer USB logging for both the live menu and the local installer. Each installer session now copies its logs back onto the stick under `pve-thin-client/logs/<session>/`, with `LATEST.txt` pointing at the newest run for post-mortem debugging.
- Changed the post-install reboot prompt so successful preset installs now pause for explicit confirmation, giving the operator time to remove the USB stick before rebooting.

## v5.2.7 - 2026-04-04

- Fixed the VM-specific USB installer boot flow so bundled presets no longer start disk installation immediately on boot. The installer now always opens its menu first and only starts the preset install after explicit user confirmation, making the target-disk picker and wipe confirmation visible again.

## v5.2.6 - 2026-04-04

- Changed the bundled USB installer flow so VM presets are still auto-loaded, but the user must now explicitly choose the target disk before installation begins instead of relying on an implicit auto-pick.
- Restored an explicit destructive-action confirmation in the preset-driven installer path, preventing unattended `--yes` wipes on the wrong disk during USB-based reinstalls.
- Clarified the live installer text so bundled VM media now advertises interactive target-disk selection instead of suggesting a fully automatic install.
- Fixed the text-installer auto-install lock path so a passive secondary menu session no longer reports success and triggers a premature reboot while the real installer owner is still running.
- Fixed live-media disk detection in the installer so VM-style USB boots exclude the actual installer carrier from the target-disk picker instead of offering it as a wipe target.
- Fixed the preset installer cancel path so backing out of disk selection or wipe confirmation no longer bubbles up as a successful install and forces an immediate reboot.
- Realigned the gaming runtime model with the kiosk architecture so `pve_thin_client.client_mode=gaming` now reports as `KIOSK` instead of the legacy direct-`GFN` flatpak path in runtime status and health output.
- Hardened the gaming session wrappers and kiosk launcher so failed kiosk starts now leave a visible on-screen error terminal with the recent kiosk log instead of silently falling back to a wallpaper-only session.
- Made the kiosk AppImage launcher more robust for VM and appliance boots by forcing extract-and-run mode, pinning Electron to X11, and adding virtualization-safe GPU-disable flags plus explicit launch/exit logging.
- Fixed the kiosk installer and launcher permissions so the runtime user can always write kiosk logs, with an automatic fallback to a user-writable log directory if `/opt/beagle-kiosk/logs` is not writable.
- Fixed the desktop runtime renderer so Beagle host-managed endpoints can carry a dedicated `MOONLIGHT_LOCAL_HOST`, allowing internal same-host test clients to prefer the guest-side Sunshine address instead of hairpinning through the public stream IP.
- Hardened the thinclient updater against low-space payload failures by pruning stale cached payloads before download and surfacing clearer disk-write errors when a large release tarball cannot be written locally.

## v5.2.5 - 2026-04-03

- Fixed the installer boot flow so the text-mode installer menu now starts only in explicit text-installer boots instead of racing the graphical installer session on `tty1` and tripping the bundled auto-install lock.
- Softened the bundled auto-install lock handling so a passive secondary installer session no longer surfaces a fatal-looking "another installer session" dialog while the real auto-install owner is already working.
- Extended endpoint health reporting with dispatch/report/update timer state so dead action-pull loops and stalled update scans show up directly in the manager-side health payload.

## v5.2.3 - 2026-04-03

- Fixed `Beagle OS Gaming` on thinclients so the GeForce NOW Flatpak now installs into persistent storage on the writable live medium instead of exhausting the volatile overlay filesystem during first launch.
- Fixed the gaming and desktop session wrappers to stay POSIX-shell compatible, preventing the runtime X session from crashing on the boot-profile background selection path when `pve_thin_client.client_mode=gaming` is active.
- Added a dedicated `beagleos-gaming.png` runtime background so `Beagle OS Gaming` shows the new BeagleOS gaming artwork during session startup on both the live image and the installed overlay.
- Improved runtime failure reporting in the thinclient session wrapper so non-zero launcher exits are recorded instead of being flattened into a misleading success marker.
- Added the closed-source `beagle-kiosk` installation surface to the public repo, including a release-verifying installer, README guardrails, AGENTS rules and the Affiliate Protection Clause in the repository license.
- Reworked the `Beagle OS Gaming` boot path so the GRUB entry now isolates into `beagle-kiosk.target` instead of sharing the normal desktop runtime path, while `Beagle OS Desktop` stays on the regular Moonlight/desktop boot track.
- Added dedicated kiosk session units and X11 session wrappers for both the installed overlay and the live-build thinclient image so the gaming profile can start a kiosk binary cleanly on tty1 once it has been installed.

## v5.2.2 - 2026-04-03

- Added a dedicated per-boot update check so every Beagle OS thinclient now performs a fresh release scan after each restart instead of relying only on the periodic timer cadence.
- Taught the updater to remember which boot already completed a scan, preventing the session-start fallback path from re-triggering duplicate forced scans within the same boot.
- Extended runtime unit activation and support-bundle collection so the new boot-scan service is enabled automatically on updated clients and its journal is captured for future debugging.

## v5.2.1 - 2026-04-03

- Reversed the dual-boot profile mapping so `Beagle OS Gaming` now launches the official NVIDIA GeForce NOW client and `Beagle OS Desktop` now launches Moonlight, matching the intended product naming.
- Updated both installed-system and USB-installer GRUB generation so the visible boot menu, safe mode and slot fallback entries all stay semantically aligned with the new `Gaming = GeForce NOW` and `Desktop = Moonlight` split.
- Repacked and republished the thinclient runtime artifacts so fresh installs, staged updates and hosted VM-specific installer scripts all inherit the corrected boot-profile behavior.

## v5.2.0 - 2026-04-02

- Expanded the Beagle host-hosted Beagle Fleet Manager so new Beagle desktop VMs can be provisioned with a selectable desktop profile, including `XFCE`, `GNOME`, `KDE Plasma`, `MATE` and `LXQt`, instead of being hard-wired to a single desktop.
- Added software selection to the Fleet create and edit flows with named presets plus free-form extra APT packages, and carried those choices through the control-plane catalog, VM metadata, Ubuntu autoinstall seed and in-guest reconfiguration path.
- Added an edit path for existing managed Beagle desktop VMs so operators can change desktop, locale, keyboard layout and package selections later from the Fleet Manager instead of rebuilding the VM from scratch.
- Fixed the Beagle host control-plane provisioning sandbox so `qm create`, seed ISO generation, task logging, KVM startup and bridge activation all work reliably from the hardened systemd service context.
- Fixed the managed-desktop Sunshine startup order so guest reconfiguration now waits for a real X11 session before launching Sunshine, preventing broken post-edit streams on non-XFCE desktops.
- Switched managed desktop defaults and metadata handling to German locale and keymap where requested, and verified the existing `VM100` desktop session now uses the German keyboard layout.
- Rebooted and revalidated the local Beagle OS thinclient on `192.168.178.92`, confirming that Moonlight still starts and streams correctly after the surrounding host-side changes.
- Verified the new Fleet workflow against a real test VM by provisioning `VM101` with `LXQt`, `Thunderbird`, `VLC` and `de_DE.UTF-8`/`de` settings through the live control-plane API that backs the Beagle host UI, then editing the same VM in place to `MATE` with `LibreOffice`, `FileZilla` and `GIMP` while keeping Sunshine streamable.

## v5.1.0 - 2026-04-01

- Reworked Moonlight target selection so Beagle OS endpoints now distinguish between local and public Sunshine routes correctly instead of getting stuck on an unreachable internal VM IP when only the public stream path is available.
- Hardened the Sunshine API selection path so the runtime rewrites and probes the effective API endpoint against the actually selected Moonlight connect host, keeping public-host routing and TLS pinning aligned.
- Fixed the automatic pairing flow so a successful manager-side registration no longer skips the real `moonlight list`/pair verification path; endpoints now continue into PIN-based pairing when registration alone did not make the host usable.
- Removed the conflicting passworded `sudo` fallback from the thinclient sudoers override, restoring the intended passwordless update actions for the limited `beagle-update-client` command path.
- Verified the currently installed local thinclient on `192.168.178.92` against the new public-host route, completed pairing against `VM100` on `65.109.80.76:50100`, and confirmed that Moonlight can now see the exported `Desktop` app through the paired public target.

## v5.0.4 - 2026-03-29

- Fixed the live and installed Moonlight runtime so it now validates and selects a working `XAUTHORITY` before pairing or streaming, preventing the black-screen boot loop where Moonlight could not open `DISPLAY=:0`.
- Fixed the standalone and VM-rendered USB live writers so they no longer depend on the downloaded filename to decide between `live` and `installer` mode.
- Fixed the hosted USB bootstrap so current runtime and installer helper scripts are always repacked into the published payload instead of leaking stale cached files into new USB media.
- Fixed the published VM USB presets and EFI boot path so large per-VM presets stay off the kernel command line while runtime mode, Moonlight host/port and Sunshine secrets still land on the stick.
- Rebuilt and verified the Internet-routed live USB flow end-to-end in a Beagle host test VM until Moonlight streamed the VM100 desktop successfully.

## v5.0.2 - 2026-03-28

- Changed license from MIT to Beagle OS Source Available License: free for personal and non-commercial use, commercial use required separate written permission or licensing.
- Completely redesigned the management Web UI with a modern dark theme, cleaner layout, sticky detail panel, and English-language interface replacing the previous German UI.
- Improved CORS policy in the control plane API to reflect the request Origin header instead of allowing all origins with a wildcard.
- Added AGENTS.md project conventions file for contributor tooling.
- Updated extension manifest version to 5.0.2.
- Added license section to README.

## v5.0.1 - 2026-03-27

- Fixed the Beagle OS runtime X11 startup path so installed endpoints no longer race on a stale `XAUTHORITY` file before Moonlight and Openbox come up.
- Reworked the live and installed boot experience around a Beagle-branded Plymouth theme with a white background, centered Beagle logo, animated spinner and live status messages during runtime preparation.
- Removed the competing tty1 autologin/getty boot path from the runtime flow so the installed endpoint starts through a single deterministic graphics session instead of showing long black screens.
- Updated both installer and installed GRUB/runtime boot arguments to suppress live-config autologin side effects and carry the same polished splash behavior across safe, legacy IRQ and text-mode boots.
- Hardened runtime Moonlight reachability checks to wait for the real target/API path before failing, reducing slow-start and false-negative connection attempts on Internet-routed endpoints.
- Fixed host download publishing so rebuilding the installer also refreshes the publicly served `latest` ISO, payload and bootstrap artifacts instead of leaving stale USB media behind.

## v5.0.0 - 2026-03-26

- Added production-facing endpoint egress controls with `direct`, `split` and `full` modes, including WireGuard-backed residential exit configuration, route application and runtime status reporting.
- Added endpoint identity controls for hostname, timezone, locale, keymap and persistent Chrome-profile naming, applied during first boot and runtime preparation.
- Extended the Beagle control plane policy model, VM profiles, enrollment payloads and installer presets so egress and identity settings flow end-to-end from Beagle host policy to endpoint check-in.
- Added VM fingerprint risk assessment to the control plane inventory and compliance path so obviously server-like guest configurations can be surfaced before operators hit service trust issues.
- Added a real Beagle OS product website served from the host installation on HTTPS port `443`, backed by live control-plane and downloads metadata instead of a placeholder page.

## v4.0.1 - 2026-03-26

- Fixed runtime device access for installed thin clients by ensuring `thinclient` gets `input` and `render` group membership during autologin setup.
- Added a `pve-thin-client-runtime.service` session override path so the runtime starts with `PAMName=login` and the required supplementary groups on tty1.
- Added `Xwrapper.config` to the installer/live image and Beagle OS overlay so Xorg can start with the required device access on kiosk hardware.
- Hardened Moonlight decoder selection to fall back to software decoding when DRM render nodes exist but are not accessible.

## v4.0.0 - 2026-03-23

- Promoted Beagle OS to a first-class distro-branded release with stronger on-system identity: `/etc/os-release`, `lsb-release`, login banner and GRUB now present the installed endpoint as `Beagle OS`.
- Rebranded the install media path around `Beagle OS Installer`, including Beagle-specific boot menu titles, hostnames and USB labels instead of the old thin-client-facing wording.
- Added direct `beagle-os-installer.iso` and `beagle-os-installer-amd64.iso` outputs to the installer build, so the project now ships a real downloadable installer ISO in addition to the USB writer scripts.
- Extended the release packaging path to include the Beagle installer ISO in `SHA256SUMS` and GitHub release assets.

## v3.4.0 - 2026-03-22

- Added a first-class Beagle VM profile dialog to both the host-installed Beagle host UI and the browser extension, so operators can inspect a fully resolved Moonlight/Sunshine endpoint profile per VM and export it directly from the Beagle host workflow.
- Added installer, profile-export and control-plane health actions to the Beagle UI path, turning the Beagle host integration into an operator surface instead of a single download trigger.
- Added a host-side `beagle-control-plane` service that publishes Beagle health and VM inventory data for installed Beagle hosts.
- Narrowed Beagle preset generation to Moonlight/Sunshine-only profiles so new per-VM installers no longer publish legacy SPICE, noVNC or DCV fallbacks in Beagle profiles.
- Updated the main architecture, installation and security documentation to describe Beagle as a Beagle-native Moonlight/Sunshine endpoint and management stack.

## v3.3.1 - 2026-03-17

- Fixed the Sunshine guest provisioning path so LightDM is forced in as the actual `display-manager.service`, replacing the stale `gdm3` default that kept the Xfce autologin desktop from coming up after the first reboot.
- Locked Sunshine guest defaults to H.264-only software streaming by explicitly disabling HEVC and AV1 in the generated `sunshine.conf`, matching the low-latency CPU-only target profile for this host.
- Tightened the Xfce autostart path so Sunshine starts only inside the intended Xfce session rather than relying on generic desktop autostart semantics.
- Added a lightweight Xfce window-manager profile for provisioned guests that disables compositor overhead by default, leaving more CPU budget available for software capture and encoding.
- Updated the Beagle host installer to reuse packaged GitHub release assets for the USB installer and payload when they are available, so release-tarball installs no longer have to rebuild the live image locally on every host.

## v3.3.0 - 2026-03-17

- Added a first-class `MOONLIGHT` runtime mode that auto-pairs against Sunshine through its authenticated `/api/pin` endpoint and then starts a preseeded Moonlight desktop stream without asking the operator for any extra runtime details.
- Extended the thin-client configuration model with Moonlight host/app, codec, decoder, bitrate, resolution, FPS and Sunshine API credentials so the installed target keeps all Sunshine-specific state outside the old SPICE/noVNC/DCV-only path.
- Added a live-build hook that bundles Moonlight from the official upstream AppImage into the installer image as a local wrapper binary, removing any dependency on distro packaging for the client itself.
- Expanded VM preset generation so host-served per-VM USB installers can embed Sunshine/Moonlight defaults including auto-pairing PIN, Sunshine API URL, default mode and a low-latency H.264 1080p60 profile.
- Upgraded the graphical USB installer dashboard and local installer preset flow to understand `MOONLIGHT`, prefer preset-defined default modes and surface Sunshine target metadata directly in the on-stick UI.
- Kept the old SPICE, noVNC and DCV paths intact as secondary modes, so mixed environments can publish Moonlight first while still exposing the legacy fallbacks per VM.

## v3.2.1 - 2026-03-16

- Fixed the host installer so `/opt/pve-dcv-integration` is always normalized to `root:root` with world-executable directory permissions after deployment, preventing `nginx` from returning `403 Forbidden` on hosted USB download artifacts.

## v3.2.0 - 2026-03-16

- Replaced the old text-only installer boot path with a local Chromium app front end that serves a richer USB installer dashboard from the live medium itself.
- Added bundled Unsplash-backed JPEG artwork for the boot medium and installer UI so the USB experience has a graphical hero background and mode cards without relying on live internet access.
- Added graphical installer actions for install, preset inspection, shell, reboot and poweroff while keeping the existing shell-based installer as a fallback underneath.
- Extended the local installer with JSON/state endpoints and noninteractive flags so the graphical front end can drive mode selection and disk targeting without re-asking the user in text dialogs.
- Upgraded the USB writer on graphical Linux desktops to prefer `zenity`-based target selection and confirmation instead of falling straight back to `whiptail`.
- Styled GRUB on both the USB stick and installed thin-client target with a bundled JPEG background so the media looks intentional from first boot onward.

## v3.1.0 - 2026-03-16

- Reworked the USB deployment flow around backend-generated per-VM installer launchers named `pve-thin-client-usb-installer-vm-<vmid>.sh`, so the Beagle host toolbar can hand each VM its own preseeded thin-client installer download.
- Embedded VM-specific connection presets directly into the hosted USB installer and wrote them onto the USB medium as `pve-thin-client/preset.env`, preserving those presets across the writer's `sudo` escalation boundary.
- Simplified the USB local-install path so bundled media now asks only for the streaming mode and the target disk; the previous full questionnaire remains only as a fallback for non-preseeded media.
- Added preset-aware mode validation for `SPICE`, `NOVNC` and `DCV`, including automatic single-mode selection when only one streaming target is configured for the chosen VM.
- Updated the Beagle host UI and browser extension so the `USB Installer` action resolves a VM-specific download URL template with `{host}`, `{node}` and `{vmid}` placeholders instead of always pointing to a generic host-wide launcher.
- Expanded hosted download metadata with a VM installer URL template and machine-readable VM installer inventory under `dist/pve-dcv-vm-installers.json` and the published downloads status JSON.
- Added persistent Beagle host UI reapply units so package updates or replaced `/usr/share/pve-manager` assets automatically reinstall the integration on the next file change and again on subsequent boots.

## v3.0.2 - 2026-03-16

- Fixed hosted USB payload checksum verification in standalone mode by downloading the payload under its original release filename, so `SHA256SUMS` can be checked successfully before extraction.

## v3.0.1 - 2026-03-16

- Fixed the standalone USB installer launcher so it no longer tries to read `VERSION` from a non-repository path before the hosted payload bundle has been downloaded and extracted.

## v3.0.0 - 2026-03-15

- Expanded the Beagle host UI from a single `DCV` action into a small operator toolset with dedicated toolbar buttons for `DCV`, `Copy DCV URL`, `DCV Info`, `USB Installer` and `Downloads Status`.
- Added matching Beagle host console-menu actions for `Copy DCV URL`, `DCV Info` and `DCV Downloads` in the host-installed UI integration.
- Added resolved-launch introspection in the host UI so operators can see whether a DCV launch came from `dcv-url`, metadata fallbacks, guest-agent IP discovery or the configured fallback URL.
- Added clipboard integration in the host UI for copying fully resolved DCV URLs without launching the session immediately.
- Added a host-side `DCV Info` dialog that exposes VM, source, session, token presence, auto-submit state and the hosted download-status endpoint.
- Expanded the browser extension toolbar with direct `DCV`, `Copy DCV URL`, `DCV Info`, `USB Installer` and `Downloads Status` buttons on VM views.
- Added matching browser-extension console-menu actions for `Copy DCV URL`, `DCV Info` and `Downloads Status`.
- Added extension-side resolved-launch inspection so operators can inspect the computed target and metadata source even when they are not using the host-installed UI integration.
- Added extension-side clipboard copying for the resolved DCV URL, reducing trial launches during admin work.
- Added extension-side direct access to the host-local download status JSON so frontend operators can jump from a VM view straight to the published thin-client artifact status.

## v2.0.0 - 2026-03-15

- Promoted the project to a major operational release with stricter host-side health validation, richer hosted download metadata and persistent refresh run-state tracking.
- Expanded `/pve-dcv-downloads/pve-dcv-downloads-status.json` to include server identity, published paths, artifact filenames, sizes and SHA256 checksums for both the hosted installer and payload bundle.
- Upgraded the hosted download index page so operators can inspect release version, host endpoint and checksums directly from the browser without opening raw JSON.
- Added persistent refresh result logging under `/var/lib/pve-dcv-integration/refresh.status.json` so automated artifact rebuilds leave a machine-readable success/failure record behind.
- Hardened `check-beagle-host.sh` to verify service activity, hosted URL binding, status JSON consistency and on-disk SHA256 parity instead of only checking for file presence.
- Carried forward the previous USB and DCV runtime hardening as the stable baseline for the 2.0 line.

## v0.5.1 - 2026-03-15

- Hardened the USB writer so it refuses non-removable or system disks by default, enforces a minimum device size and waits for freshly created partitions before formatting them.
- Added SHA256 verification for hosted USB payload downloads when `SHA256SUMS` is available and now validates live installer assets both before and after they are copied to the target media.
- Hardened the DCV thin-client launch path by enforcing safer `.dcv` file permissions, validating token/session combinations and supporting browser fallback when `dcvviewer` is unavailable but a proxied HTTPS DCV endpoint exists.
- Restored the Beagle host UI asset in the working tree so host deployments remain reproducible after the local interrupted edit sequence.

## v0.5.0 - 2026-03-15

- Added production-oriented host operations tooling: a hosted-artifact refresh script, an installable systemd service/timer and a host healthcheck command.
- Added release automation and project validation scripts so future GitHub releases can be built and published reproducibly without re-uploading the large USB payload artifact.
- Added host-side download status metadata and a dedicated status JSON under `/pve-dcv-downloads/`.
- Updated packaging and host deployment to include Beagle host service templates and to install the recurring host artifact refresh timer.

## v0.4.7 - 2026-03-15

- Fixed the host-side `nginx` download location so `/pve-dcv-downloads/<file>` is served as a real prefix path instead of falling through to the DCV backend.
- Revalidated the Beagle host-hosted USB installer endpoint after the hosted download routing fix.

## v0.4.6 - 2026-03-15

- Reworked the USB distribution path so the large thin-client payload is served by each installed Beagle host under `/pve-dcv-downloads/` instead of being expected from GitHub releases.
- Added host-local download preparation that generates a Beagle host-hosted USB installer script with the correct local payload URL baked in.
- Extended the Beagle-side `nginx` setup to always publish hosted download artifacts on the standard HTTPS endpoint, even when no DCV backend proxy is configured.
- Added a Beagle host UI runtime config asset so the `USB Installer` toolbar button opens the host-local installer endpoint by default.

## v0.4.5 - 2026-03-15

- Fixed DCV launch URL generation so `dcv-url` in VM metadata always overrides the internal guest IP template path.
- Fixed metadata parsing for VM descriptions that contain literal `\\n` separators, preventing `dcv-user` and `dcv-password` from being merged into one query value.
- Revalidated the server-installed Beagle host UI integration with the public DCV proxy URL on the control plane.

## v0.4.4 - 2026-03-15

- Fixed the standalone USB writer bootstrap path by moving large release extraction out of space-constrained `/tmp` defaults and into a more suitable temporary location.
- Fixed USB media rewriting on already mounted sticks by unmounting target partitions before calling `wipefs`.
- Added a dedicated release USB payload tarball with prebuilt live installer assets so `pve-thin-client-usb-installer-latest.sh` no longer depends on a local `live-build` run in the normal path.
- Hardened the live-build helper to populate its build tree through `sudo` consistently, preventing permission issues during debootstrap/chroot setup.

## v0.4.3 - 2026-03-15

- Added DCV metadata support for `dcv-user`, `dcv-password`, `dcv-auth-token`, `dcv-session` and `dcv-auto-submit`.
- Added browser-side and proxied-page DCV auto-login helpers so VM-specific credentials can be prefilled and submitted automatically when opening DCV from Beagle host.
- Added host-side DCV proxy injection of `pve-dcv-autologin.js` so the server-installed Beagle host integration can auto-fill the DCV web login page without a browser extension.

## v0.4.2 - 2026-03-15

- Added a Beagle host-host DCV TLS proxy installer that can publish a backend DCV service on the standard HTTPS endpoint with the already valid Beagle host certificate.
- Integrated DCV proxy deployment into the standard Beagle host installer so UI deployment can also fix invalid/self-signed DCV web certificates.
- Added backend auto-detection from VM metadata and guest-agent IPs, plus explicit `PVE_DCV_PROXY_VMID` and `PVE_DCV_PROXY_BACKEND_HOST` installation controls.
- Added cleanup of legacy host-side `iptables` DNAT rules on the DCV port so the local TLS proxy can bind cleanly.

## v0.4.1 - 2026-03-15

- Added a documented GitHub-release installation path for deploying the project onto arbitrary Beagle hosts without a git checkout.
- Updated the Beagle host installers to self-escalate through `sudo` instead of requiring an explicit root invocation from the user.
- Added automatic `rsync` dependency installation for the host deployment script so extracted release tarballs are directly installable on fresh hosts.
- Fixed the release tarball contents so host deployments from GitHub releases include the Beagle host UI asset and extension sources needed for repackaging.

## v0.4.0 - 2026-03-15

- Rebuilt the USB installer flow around a bootable live installer architecture inspired by the existing ThinOverNet approach.
- Replaced the old root-only USB writer with a sudo-escalating writer that selects target devices interactively and can bootstrap the release payload automatically.
- Added a live-build based thin-client installer environment, a live setup menu and a local disk installer that copies a bootable thin-client runtime to the target disk.
- Expanded the thin-client configuration model with network, credentials, Beagle host SPICE ticket mode and generated DCV connection files.
- Added runtime helpers for Beagle host-backed SPICE auto-connect and direct DCV connection-file generation.
- Fixed BIOS+UEFI USB and local-disk partition layouts by adding explicit `bios_grub` partitions for GRUB-on-GPT boot paths.
- Added runtime hostname/network application through generated `systemd-networkd` config and enabled the live image to run that preparation path before launching the kiosk session.
- Added NICE DCV Viewer installation to the live-build image so the DCV runtime path is usable from the generated installer media.

## v0.3.0 - 2026-03-15

- Reworked the extension to inject `DCV` into the existing Beagle host console dropdown instead of using only a floating page button.
- Added a `USB Installer` toolbar button that downloads the thin-client USB writer script.
- Added a first USB writer script and starter payload for building a deployable thin-client installer stick.

## v0.2.1 - 2026-03-15

- Added explicit packaging dependency checks for `zip`, `tar` and `sha256sum`.
- Hardened the Beagle host deployment path after validating installation on a live Beagle host 8.4 host.

## v0.2.0 - 2026-03-15

- Added a production-oriented repository layout for the browser extension, thin-client assistant, docs and release scripts.
- Expanded the Beagle host browser extension with stronger VM context detection, metadata fallbacks and configurable launch behavior.
- Added a first functional Linux thin-client assistant with installer, setup menu, runtime launchers, config templates and autostart assets.
- Added architecture, security and installation documentation.
- Added release packaging for extension and thin-client assistant artifacts with checksums.

## v0.1.0 - 2026-03-15

- Initial third-party Beagle host web extension.
- Adds `DCV` action button on VM pages.
- Resolves VM IP via guest-agent API.
- Supports URL-template and fallback parsing from VM description.
- Release packaging script.
