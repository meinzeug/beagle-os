# Provider-Abstraction Notes (2026-04-18)

- Session/auth stability fixes were implemented in provider-neutral surfaces:
	- [beagle-host/services/auth_session.py](beagle-host/services/auth_session.py)
	- [website/app.js](website/app.js)
	- [scripts/install-beagle-proxy.sh](scripts/install-beagle-proxy.sh)
- No new direct coupling to Proxmox APIs (`qm`, `pvesh`, `/api2/json`, `PVE.*`) was introduced.
- VM create validation was executed through the generic provisioning API (`/beagle-api/api/v1/provisioning/*`) on the beagle provider.
- Host runtime prerequisites (libvirt pool/network) remain provider implementation concerns and are correctly contained in host/provider layers.
- VM delete was added provider-neutral first:
	- Generic contract: `HostProvider.delete_vm(...)` in [beagle-host/providers/host_provider_contract.py](beagle-host/providers/host_provider_contract.py).
	- Provider implementations:
		- [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py)
		- [beagle-host/providers/proxmox_host_provider.py](beagle-host/providers/proxmox_host_provider.py)
	- Generic admin API path: `DELETE /api/v1/provisioning/vms/{vmid}` in [beagle-host/services/admin_http_surface.py](beagle-host/services/admin_http_surface.py).
	- UI action in [website/app.js](website/app.js) targets the generic provisioning route, not provider-specific APIs.
- Proxmox-specific command usage (`qm destroy`) remains isolated in `providers/proxmox/*` and is not called from HTTP/UI layers.
- noVNC access was added through a dedicated host service, not inline in HTTP handlers:
	- New service: [beagle-host/services/vm_console_access.py](beagle-host/services/vm_console_access.py).
	- New generic read route: `GET /api/v1/vms/{vmid}/novnc-access` in [beagle-host/services/vm_http_surface.py](beagle-host/services/vm_http_surface.py).
	- UI integration in [website/app.js](website/app.js) only calls the generic route.
	- Provider-specific behavior is centralized in the service:
		- `proxmox`: returns direct noVNC URL.
		- `beagle`: resolves libvirt VNC display and returns Beagle-tokenized noVNC URL via local websockify proxy.
- Beagle-specific noVNC runtime integration remains isolated to beagle host/proxy layers:
	- Tokenized websocket proxy unit: [beagle-host/systemd/beagle-novnc-proxy.service](beagle-host/systemd/beagle-novnc-proxy.service).
	- Host-service bootstrap: [scripts/install-beagle-host-services.sh](scripts/install-beagle-host-services.sh).
	- Proxy route wiring: [scripts/install-beagle-proxy.sh](scripts/install-beagle-proxy.sh).
	- No new Proxmox UI/ExtJS coupling introduced.
- Installer artifact reliability hardening in [scripts/install-beagle-host.sh](scripts/install-beagle-host.sh) is provider-neutral and enforces generic host prerequisites before service startup.
- Standalone host runtime prerequisite handling was tightened in provider-adjacent install glue ([scripts/install-beagle-host-services.sh](scripts/install-beagle-host-services.sh)) without introducing provider leaks into HTTP/UI layers:
	- libvirt readiness wait,
	- explicit beagle-network/local-pool verification,
	- no new Proxmox coupling.
- Beagle-provider runtime inventory now resolves storage/network from live libvirt first in [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py), keeping API/catalog defaults aligned with real backend capabilities.
- Beagle-provider `start_vm` now redefines libvirt XML from current provider config before start, so generic service-layer cleanups (boot order/media removal) are actually enforced in runtime domains.
- Thinclient preset installer disk-selection hardening in [thin-client-assistant/usb/pve-thin-client-local-installer.sh](thin-client-assistant/usb/pve-thin-client-local-installer.sh) is endpoint-runtime logic only and does not add provider-specific coupling.

- RTSP stream-fix work stayed provider-neutral in host/runtime layers:
	- Runtime-side Moonlight host retarget/sync hardening was implemented in thinclient runtime modules, not in provider-specific APIs.
	- Public stream firewall reconciliation changes were implemented in [scripts/reconcile-public-streams.sh](scripts/reconcile-public-streams.sh), which already operates on generic stream inventory/ports and not on Proxmox-only APIs.
	- No new direct coupling to `qm`, `pvesh`, `/api2/json`, or `PVE.*` was introduced by the RTSP fix path.

- 2026-04-19 provider-neutral follow-up changes:
	- Chroot/offline install behavior in [scripts/install-beagle-host-services.sh](scripts/install-beagle-host-services.sh) is now explicit:
		- live libvirt readiness wait/provisioning only runs when a live libvirt system context is actually manageable,
		- installer chroot mode skips those runtime-only operations instead of failing,
		- no Proxmox-specific coupling was introduced in this fix path.
	- Beagle Web Console now exposes existing generic live-USB endpoint actions from [website/app.js](website/app.js) (`/api/v1/vms/{vmid}/live-usb.sh`), without introducing any provider-specific UI API calls.
	- Provisioning default bridge selection in [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py) now validates configured defaults against discovered bridge inventory, reducing implicit coupling to environment-specific defaults (for example `vmbr1` in non-Proxmox labs).
	- ISO staging helper added in the same provider-neutral provisioning service to align generated media availability with provider-advertised storage pool paths while preserving graceful fallback when pool paths are not writable in local simulation contexts.

- Current residual coupling risks discovered in local simulation harness (not production API coupling):
	- `scripts/test-standalone-desktop-stream-sim.sh` still depends on local libvirt host permissions/ownership and kernel boot semantics that differ between developer hosts.
	- These are test-harness environment assumptions and should be hardened inside simulation scripts/services, not by introducing provider-specific behavior into generic HTTP/UI layers.

