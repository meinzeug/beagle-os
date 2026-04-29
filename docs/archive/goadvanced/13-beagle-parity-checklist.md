# Plan 11 — Feature-Parity-Audit: Beagle host → Beagle

Erstellt: 2026-05-XX (GoAdvanced Plan 11 Schritt 2)

Diese Datei listet alle relevanten Beagle host-Funktionen, die im alten Stack
vorhanden waren, und deren Entsprechung im Beagle-eigenen Stack
(`providers/beagle/` + `beagle-host/services/`).

Status-Legende:

- ✅ **vorhanden** — Beagle-Äquivalent implementiert und in Produktion
- 🔶 **partial** — Grundfunktion vorhanden, Feature-Lücken offen
- ❌ **fehlt** — kein Äquivalent; Migration blockiert oder explizit entfernt
- 🚫 **absichtlich entfernt** — Beagle host-Feature wird in Beagle-OS nicht repliziert

---

## 1. VM-Lifecycle

| Beagle host-Funktion | Beagle-Äquivalent | Status |
|---|---|---|
| VM erstellen (`qm create`) | `libvirt_runner.py` + `vm_http_surface.py` POST `/api/v1/vms` | ✅ |
| VM starten (`qm start`) | `service_registry.start_vm_checked()` + libvirt domain start | ✅ |
| VM stoppen (`qm stop`) | `service_registry.stop_vm()` + libvirt domain destroy/shutdown | ✅ |
| VM pause/resume (`qm suspend`) | libvirt domain suspend/resume über HTTP surface | 🔶 Pause via `/api/v1/vms/{id}/pause` implementiert |
| VM löschen (`qm destroy`) | `vm_http_surface` DELETE | ✅ |
| VM Status abfragen (`qm status`) | `virtualization_inventory.list_vms()` | ✅ |
| VM Config lesen (`qm config`) | VM details via `/api/v1/vms/{id}` | ✅ |
| VM Config ändern (`qm set`) | PUT `/api/v1/vms/{id}` | 🔶 Subset der Optionen implementiert |
| VM klonen (`qm clone`) | `VmMutationSurfaceService` POST `/api/v1/vms/{id}/clone` | ✅ |
| VM aus Template erstellen | Nicht implementiert | ❌ Template-Support steht in Plan 10 (VDI Pools) |
| VM CPU/RAM hotplug | Nicht implementiert | ❌ Tiefes libvirt Feature — Backlog |
| QEMU guest agent Befehle (`qm guest exec`) | `scripts/lib/provider_shell.sh` (CI-Allowlist) | ✅ Libvirt QEMU-GA API im Provider; Shell-Shim nur Fallback |

## 2. Snapshots

| Beagle host-Funktion | Beagle-Äquivalent | Status |
|---|---|---|
| Snapshot erstellen (`qm snapshot`) | `backup_service.py` + libvirt snapshot XML | 🔶 backup_service kapselt Snapshots; direktes VM-Snapshot-API fehlt noch |
| Snapshot-Liste (`qm listsnapshot`) | `backup_service.list_snapshots()` | ✅ |
| Snapshot revert (`qm rollback`) | `VmMutationSurfaceService` POST `/api/v1/vms/{id}/snapshot/revert` | ✅ |
| Snapshot löschen (`qm delsnapshot`) | `VmMutationSurfaceService` DELETE `/api/v1/vms/{id}/snapshot?name=...` | ✅ |

## 3. Storage

| Beagle host-Funktion | Beagle-Äquivalent | Status |
|---|---|---|
| Storage-Pool anlegen | `providers/beagle/storage/` (directory, lvm_thin, nfs, zfs) | 🔶 Backends implementiert; Provisioning-API noch nicht vollständig |
| Storage-Inhalt listen | `GET /api/v1/storage/pools/{pool}/files` | ✅ |
| Disk Image hochladen | `POST /api/v1/storage/pools/{pool}/upload` | ✅ ISO/qcow2/raw/img Upload-Endpoint vorhanden |
| Disk Image herunterladen | `GET /api/v1/storage/pools/{pool}/files?filename=...` | ✅ |
| Storage Migration (VM Disk verschieben) | `migration_service.migrate_vm()` (Host-Migration) | 🔶 Nur Host-Migration; Storage-only Migration fehlt |
| ZFS Storage | `providers/beagle/storage/zfs.py` | ✅ |
| LVM-thin | `providers/beagle/storage/lvm_thin.py` | ✅ |
| NFS | `providers/beagle/storage/nfs.py` | ✅ |
| Directory Storage | `providers/beagle/storage/directory.py` | ✅ |

## 4. Netzwerk

| Beagle host-Funktion | Beagle-Äquivalent | Status |
|---|---|---|
| Bridge anlegen | `network_http_surface_service` | 🔶 Konfiguration implementiert; Ansible-Rollout-Integration offen |
| VLAN-Tagging | `providers/beagle/network/vlan.py` | ✅ |
| VXLAN | `providers/beagle/network/vxlan.py` | ✅ |
| SDN/Overlay-Netzwerk | In Plan 17 (SDN + Firewall) | ❌ Noch nicht begonnen |
| Firewall (Beagle host SDN-Firewall) | `firewall_service.py` + nftables | 🔶 Basis-nftables implementiert; SDN-Integration offen (Plan 17) |
| IPAM | Nicht implementiert | ❌ Plan 17 |

## 5. Benutzerverwaltung / Auth

| Beagle host-Funktion | Beagle-Äquivalent | Status |
|---|---|---|
| Local User + PAM Auth | `auth_service.py` + `auth_http_surface.py` | ✅ |
| LDAP/AD Auth | `ldap_auth.py` + `AuthSessionService.login()` | ✅ Direktes LDAP-Bind als optionales Auth-Backend |
| SAML SSO | `saml_service.py` | ✅ |
| OIDC/OAuth2 | `auth_session_http_surface.py` | ✅ |
| RBAC / Permissions | `authz_policy_service()` | ✅ |
| Token-basierter API-Zugang | `BEAGLE_API_TOKEN` + Bearer | ✅ |
| Two-Factor Auth (TOTP) | `AuthSessionService` + `/api/v1/auth/users/{user}/totp/*` | ✅ Lokaler TOTP-Zweitfaktor vorhanden |
| Ticket-basierter Zugang (`PVEAuthCookie`) | **Absichtlich entfernt** | 🚫 |

## 6. Cluster / HA

| Beagle host-Funktion | Beagle-Äquivalent | Status |
|---|---|---|
| Cluster-Join / -Leave | `providers/beagle/cluster/` (PoC) | 🔶 etcd-PoC vorhanden; Produktion in Plan 07 |
| Live-Migration | `migration_service.migrate_vm()` | 🔶 Basis implementiert; zero-downtime Migration offen |
| HA-Manager | Nicht implementiert | ❌ Plan 09 |
| Fencing / Watchdog | Nicht implementiert | ❌ Plan 09 |
| Cluster-Config (`pvecm`) | Nicht implementiert | ❌ Plan 07 |
| corosync | **Absichtlich entfernt** — etcd stattdessen | 🚫 |

## 7. Backup / Restore

| Beagle host-Funktion | Beagle-Äquivalent | Status |
|---|---|---|
| Backup erstellen (`vzdump`) | `backup_service.py` POST `/api/v1/backups/run` | ✅ |
| Backup wiederherstellen | `backup_service.py` POST `/api/v1/backups/{id}/restore` | ✅ |
| Backup-Jobs / -Schedule | `backup_service.py` policies | 🔶 Policy-API vorhanden; Cron-Trigger in Plan 16 |
| Replikation | `backup_service.py` POST `/api/v1/backups/{id}/replicate` | 🔶 Basis implementiert |
| Beagle host Backup Server (PBS) | **Absichtlich entfernt** | 🚫 Eigener Backup-Stack (Plan 16) |

## 8. Web UI / API

| Beagle host-Funktion | Beagle-Äquivalent | Status |
|---|---|---|
| Beagle host Web Console (ExtJS) | `website/` — Beagle Web Console | ✅ |
| noVNC / SPICE Konsole | noVNC via `control_plane_handler` | ✅ |
| REST API (`/api2/json`) | Beagle REST `/api/v1/*` | ✅ |
| API v2 Vorbereitung | `API_V2_PREPARATION_ENABLED` Flag | 🔶 |
| legacylib.js | `extension/` + `website/` | ✅ (beagle-eigene UI) |

## 9. Monitoring / Observability

| Beagle host-Funktion | Beagle-Äquivalent | Status |
|---|---|---|
| Metriken (statsd/influx Export) | `prometheus_metrics.py` `/metrics` Endpoint | ✅ (Plan 08) |
| Health-Check | `health_aggregator.py` `/api/v1/health` | ✅ (Plan 08) |
| Structured Logging | `structured_logger.py` | ✅ (Plan 08) |
| Grafana-Dashboard | `docs/observability/grafana-dashboard.json` | ✅ (Plan 08) |
| Task-Logs / Job-History | `job_queue_service.py` | ✅ (Plan 07) |

---

## Offene Migrationsaufgaben (priorisiert)

| Priorität | Feature | Nächster Schritt |
|---|---|---|
| MEDIUM | SDN/Overlay Netzwerk | Plan 17 |
| MEDIUM | HA-Manager | Plan 09 |
| LOW | Cluster Live-Migration (zero-downtime) | Plan 07 |

---

## Beagle host-Features, die absichtlich nicht repliziert werden

- `corosync` / `pve-cluster` → ersetzt durch `etcd`
- Beagle host Backup Server (PBS) → eigener Backup-Stack (Plan 16)
- `PVEAuthCookie` Ticket-Auth → OAuth2/OIDC/SAML
- ExtJS Beagle host UI → Beagle Web Console (`website/`)
- `pvecm`, `pvesh`, `qm`-CLI → `beaglectl` (Plan 18)
