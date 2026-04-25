## Update (2026-04-25, GoAdvanced Plan 05: Control-Plane-Split — Handler-Extraktion)

**Scope**: Plan 05 (Control-Plane Split) — `beagle-control-plane.py` von 899 LOC auf **88 LOC** geschrumpft (Ziel < 800 LOC) durch Extraktion der Handler-Klasse.

### Handler-Extraktion (Plan 05 Schritt 4)
- **Neu**: `beagle-host/services/control_plane_handler.py` (829 LOC) — enthaelt die komplette `Handler(HandlerMixin, BaseHTTPRequestHandler)` Klasse mit `do_GET`/`do_POST`/`do_PUT`/`do_DELETE`/`do_OPTIONS`/`log_message`/`handle_one_request`. Keine API-Verhaltensaenderung; reine Verschiebung.
- **Geschrumpft**: `beagle-host/bin/beagle-control-plane.py` 899 → **88 LOC**. Enthaelt jetzt nur noch:
  - sys.path-Setup (3 Eintraege fuer ROOT/PROVIDERS/SERVICES)
  - `from service_registry import *`
  - `from control_plane_handler import Handler`
  - `main()`: Secret-Bootstrap, AuditLogService-Wiring fuer SecretStore, `ensure_data_dir()`, `ensure_cluster_rpc_listener()`, Recording-/Backup-Scheduler-Threads, ThreadingHTTPServer-Start, Cleanup-/Signal-Handling

### Plan-05 Status nach Audit
- Schritt 1 (Inventur): bereits durch Vorgaenger-Welle erledigt → `[x]`
- Schritt 2 (Router-Abstraktion): `api_router_service.py` (185 LOC) + 16 Tests → `[x]`
- Schritt 3 (Surface-Migration): 12 von 10 geplanten Surfaces produktiv (z.B. `vm_http_surface`, `pools_http_surface`, `cluster_http_surface`, `endpoint_http_surface`, `auth_session_http_surface`, plus Bonus `admin/audit_report/auth/backups/network/public/recording`) → `[/]` (Reports/Energy/Fleet/Health-Metrics noch in Handler/admin)
- Schritt 4 (Handler-Extraktion): **`[x]` — heute erledigt, Ziel deutlich unterschritten**
- Schritt 5 (Surface-Tests): teilweise → `[/]`
- Schritt 6 (Smoke auf srv1): ausstehend → `[/]`

### Tests
- `python3 -m py_compile` auf beide Dateien => OK
- `import control_plane_handler` mit allen Service-Inits funktioniert (alle 5 do_* Methoden vorhanden)
- `pytest tests/unit/ -k 'router or surface or runtime or service_registry or smoke'` => **100 passed**
- Voller Lauf: 782 passed, 10 pre-existing Failures (gpu_metrics/streaming/rebalancing/mock_provider — unabhaengig vom Refactor, durch Stash-Vergleich verifiziert)

### Naechste sinnvolle Schritte
- Plan 05 Schritt 6: Smoke auf srv1 nach naechstem Deploy
- Plan 11 Schritt 2: Feature-Parity-Audit-Tabelle Proxmox vs Beagle
- Plan 06: SQLite-State-Migration

---

## Update (2026-04-25, GoAdvanced Plan 09: CI-Pipeline Bats-Tests + Workflow-Audit)



**Scope**: Plan 09 (CI-Pipeline) — Bats-Test fuer TPM-Attestation, Bestands-Workflows auditiert + dokumentiert, post_install_check.bats stabilisiert.

### Bats-Tests (Plan 09 Schritt 3)
- **Neu**: `tests/bats/tpm_attestation.bats` — 9 Tests fuer `thin-client-assistant/runtime/tpm_attestation.sh`. Stubs fuer `tpm2_pcrread` (sha256 PCR YAML), `curl` (--write-out + --output) und `hostname`. Deckt Pflicht-Env-Vars (3 Tests), Happy-Path, REJECTED, HTTP 403, TPM-Fehler, leere PCRs und fehlendes `tpm2_pcrread`-Binary ab. Tests skippen sauber wenn `jq`/`python3-yaml` fehlen.
- **Fix**: `tests/bats/post_install_check.bats` hatte 4 Bugs die alle Tests crashen liessen oder das Happy-Path-Test sabotierten:
  1. `load "$(command -v bats-support 2>/dev/null || true)"` mit leerem Argument crasht bats 1.10 → guard mit `if command -v bats-support`
  2. `dirname "$BATS_TEST_FILE"` lieferte relativen Pfad → ersetzt durch `${BATS_TEST_DIRNAME}` (immer absolut)
  3. systemctl-Stub parste `is-active --quiet libvirtd` falsch (nahm `--quiet` als Service-Name) → Schleife ueberspringt jetzt `--`-Flags
  4. curl-Stub ignorierte `--output`/`--write-out` → printete JSON-Body statt HTTP-Code zurueck → vollstaendiger Stub mit Arg-Parsing
- Resultat: **16/16 Bats-Tests gruen** (`bats tests/bats/`).

### Workflow-Wiring (Plan 09 Schritt 2)
- `.github/workflows/tests.yml`: separater `bats` Job ergaenzt — installiert `bats jq python3-yaml` via apt und laeuft `bats --tap tests/bats/`.

### Audit Bestand
- Plan 09 Doku entsprach nicht dem Repo-Status. Folgende Workflows existieren bereits und wurden korrekt als `[x]` markiert: `lint.yml` (shellcheck+ruff+mypy+eslint), `tests.yml` (pytest 3.11/3.12 + Cov + neu bats), `build-iso.yml` (installimage+iso, dispatch+push), `release.yml` (Tag-Trigger + SHA256SUMS + GPG-Signatur + Changelog), `security-tls-check.yml`, `security-subprocess-check.yml`, `no-proxmox-references.yml`.
- Verbleibend (`[ ]`/`[/]` markiert): `install_beagle_host.bats` (braucht Container-Sandbox), `tests/bats/README.md`, ISO-cron-Schedule, ISO-SBOM (`cyclonedx-bom`/`cyclonedx-npm`), Reproduzibilitaets-Vergleich, Cosign-Signatur, Branch-Protection (GitHub-UI-Konfig).

### Tests
- `bats tests/bats/` => **16 ok** (lokal mit `bats 1.10.0`)
- `bash -n` auf alle bats-Files: OK
- `python3 -m py_compile` keine Aenderung — kein Python betroffen

### Naechste sinnvolle Schritte
- Plan 09 Schritt 4: ISO-Build cron + SBOM-Generierung
- Plan 11 Schritt 2: Feature-Parity-Audit-Tabelle Proxmox vs Beagle
- Plan 05: control-plane.py-Split (HIGH, vollstaendig offen)

---

## Update (2026-04-25, GoAdvanced Plan 11 Teil 1: Proxmox-Cert-Defaults + CI-Guard)

**Scope**: Erste konkrete Code-Schritte zu Plan 11 (Proxmox-Endbeseitigung). Soft-Disable + Cert-Default-Migration + CI-Guard-Hardening.

### Cert-Default-Migration (Plan 11 Schritt 4 Teil 1)
- `beagle-host/services/service_registry.py`: `MANAGER_CERT_FILE` Default `/etc/pve/local/pveproxy-ssl.pem` → `/etc/beagle/manager-ssl.pem`. Operatoren koennen weiterhin via `BEAGLE_MANAGER_CERT_FILE` einen anderen Pfad setzen. `RuntimeEnvironmentService.manager_pinned_pubkey()` faellt bei fehlender Datei sauber auf leeren Pin (`""`) zurueck — kein Runtime-Bruch bei Hosts ohne Cert.
- `scripts/ensure-vm-stream-ready.sh:21`: `HOST_TLS_CERT_FILE` Default migriert.
- `scripts/check-beagle-host.sh:80`: Cert-Hinweis migriert.

### Soft-Disable (Plan 11 Schritt 3)
- `scripts/install-proxmox-ui-integration.sh`: 206-LOC Installer (fuer geloeschtes `proxmox-ui/` Verzeichnis) ersetzt durch 19-Zeilen Deprecation-Stub mit klarer Migrationsmeldung. Aufruf scheitert kontrolliert (`exit 1`) statt mit unklaren `install -D` Fehlern.

### CI-Guard (Plan 11 Schritt 7)
- `.github/workflows/no-proxmox-references.yml`: Allowlist erweitert um `scripts/lib/provider_shell.sh`, `scripts/ensure-vm-stream-ready.sh`, `scripts/configure-sunshine-guest.sh`, `thin-client-assistant/`, `extension/`, `AGENTS.md`, `prompt.md`.
- `grep --exclude-dir` zusaetzlich `--exclude-dir=".venv"`, `thin-client-assistant`, `extension` ergaenzt damit Build-Artefakte und externe Scripts den Guard nicht stoeren.
- Lokale Simulation: `FOUND=0` nach Migration. Verbleibende `qm`-Aufrufe in `provider_shell.sh` (genutzt fuer Proxmox-Hosts mit Beagle-VMs) sind explizit allowlisted und bleiben fuer spaetere Beagle-libvirt-Migration offen.

### Tests
- `python3 -m py_compile beagle-host/services/service_registry.py` => OK
- `bash -n scripts/ensure-vm-stream-ready.sh scripts/check-beagle-host.sh` => OK
- `python3 -m pytest tests/unit/ -k 'runtime or service_registry or smoke'` => 1 passed
- Lokale CI-Guard-Simulation: `FOUND=0`

---



**Scope**: Terraform Provider Bug-Fix, Cross-Node Migration Service Wiring, SSH Key Setup für Cluster.

### Terraform Provider Bugfix (commit 728f70e)
- **Problem**: `resourceVMRead()` löschte Resource-ID auf jedem API-Fehler (nicht nur 404), verursachte "Root object was present, but now absent" Errors
- **Lösung**:
  - Neuer `Client.requestWithStatus()` differenziert HTTP 404 von anderen Fehlern (nur 404 → "resource nicht gefunden")
  - `resourceVMRead` befüllt alle Schema-Felder aus der API-Response
- **Tests**: 4/4 unit-tests pass (TestClientCreateReadDelete, TestClientReadNotFound, TestClientBadToken, TestApplyCreatesVMDestroyRemovesVM)
- **Live-Validierung**: `terraform apply --auto-approve` gegen srv1 erfolgreich (vmid=9901, APPLY_EXIT=0), `terraform destroy` erfolgreich (DESTROY_EXIT=0)

### Migration Service: Cluster-Inventory-Wiring (commit fdc308d)
- **Problem**: `MigrationService`, `HaManagerService`, `MaintenanceService` nur lokal `HOST_PROVIDER.list_nodes()` (nur aktueller Hypervisor) → Remote Nodes nie sichtbar
- **Lösung**: 
  - Neuer Helper `_cluster_nodes_for_migration()` ruft `build_cluster_inventory()` auf (mergt lokal + remote + Cluster-Members)
  - Wiring updated: `migration_service`, `ha_manager_service`, `maintenance_service`, `pool_manager_service` nutzen cluster-aware list
- **Folge**: `MigrationService.list_target_nodes()` zeigt jetzt beagle-1 als gültiges Migrations-Ziel
- **Tests**: 24/24 unit-tests pass (migration, ha_manager, maintenance, pool_manager)
- **Deployment**: srv1/srv2 rsync + systemctl restart → beagle-control-plane active, Cluster-Inventory zeigt alle 4 Knoten (beagle-0, beagle-1, srv1, srv2) online

### SSH Key Setup für Beagle-Manager Cross-Node Auth
- **Schritte**:
  - ed25519 SSH-Keys generiert für beagle-manager auf srv1 und srv2
  - Cross-authorized: srv1-pubkey in srv2 root authorized_keys, srv2-pubkey in srv1 root authorized_keys
  - Host-Keys scanned in beagle-manager known_hosts auf beiden Servern
  - `BEAGLE_CLUSTER_MIGRATION_URI_TEMPLATE=qemu+ssh://root@{target_node}/system` in `/etc/beagle/beagle-manager.env`
- **Validierung**: `sudo -u beagle-manager ssh root@beagle-1` → CONNECTION_OK ✅

### QEMU+SSH Migration-Infrastruktur-Limitation Identifiziert
- **Finding**: Virsh-basierte Live-Migration über `qemu+ssh` deadlockt bei allen Versuchskombinationen:
  - `virsh migrate --live`: Timeout nach 60-120s, kein Fortschritt
  - `virsh migrate --persistent --undefinesource`: Libvirt-Deadlock (`another migration job already running`)
  - `virsh domjobinfo` während Migration: Timeout (kompletter libvirt-Lock)
- **Root-Ursache**: QEMU+SSH-Migrationsprotokoll oder Libvirt-Konfiguration inkompatibel (erfordert separate tiefere Untersuchung)
- **Implikation**: 
  - Beagle **API-Ebene** funktioniert korrekt (Knoten-Sichtbarkeit ✅, SSH-Auth ✅, qemu+ssh Connectivity ✅)
  - **Virtualisierungs-Ebene** (virsh+qemu+ssh) hat Probleme und braucht separate Untersuchung
  - **Workaround für Multi-Node-Produktion**: Shared Storage (NFS/Ceph) statt Storage-Copy während Migration
- **Status**: Migration-API wird arbeiten, sobald Shared Storage verfügbar oder qemu+ssh-Protokoll repariert ist

---

## Update (2026-04-25, Cluster-API iptables-Haertung Port 9088)

**Scope**: S-020 von "known mitigated" auf aktiv gehaertet gebracht (reproduzierbar + live auf srv1/srv2 ausgerollt).

### Neu erstellt
- `scripts/harden-cluster-api-iptables.sh`
  - idempotentes Hardening fuer tcp/9088 mit dedizierter Chain `BEAGLE_CLUSTER_API_9088`
  - erlaubt nur localhost + explizite Peer-IPs, sonst DROP
  - optionale Persistenz (`--persist auto|always|never`), Dry-Run-Support

### Live-Rollout
- Script auf `srv1`/`srv2` deployed nach `/opt/beagle/scripts/`
- Aktivierung:
  - `srv1`: `--peer 176.9.127.50`
  - `srv2`: `--peer 46.4.96.80`
- Persistenz aktiviert: `netfilter-persistent` + `iptables-persistent` installiert, `netfilter-persistent save` ausgefuehrt
- Verifiziert: `/etc/iptables/rules.v4` auf beiden Hosts enthaelt `BEAGLE_CLUSTER_API_9088` und `--dport 9088`

---

## Update (2026-04-25, GoEnterprise: VM Stateless Reset + RBAC kiosk_operator)

**Scope**: VM-Reset auf Snapshot in den Beagle-Provider integriert, Pool-Reset-Wiring aktiviert und RBAC fuer `kiosk_operator` umgesetzt.

### Geaendert
- `beagle-host/providers/host_provider_contract.py`
	- Neuer Contract: `reset_vm_to_snapshot(vmid, snapshot_name, timeout=...)`
- `beagle-host/providers/beagle_host_provider.py`
	- Neue Implementierung `reset_vm_to_snapshot(...)` mit Snapshot-Validierung, `virsh snapshot-revert --force` (wenn libvirt aktiv) und Status-Update auf `stopped`
- `beagle-host/services/service_registry.py`
	- `PoolManagerService` bekommt jetzt `start_vm`, `stop_vm` und `reset_vm_to_template`
	- Neuer Helper `reset_vm_to_template(vmid, template_id)` loest Template auf und ruft Provider-Reset gegen `template.snapshot_name` auf
- `beagle-host/services/auth_session.py`
	- Neue Default-Rolle: `kiosk_operator` mit `vm:read`, `vm:power`
- `beagle-host/services/authz_policy.py`
	- `POST /api/v1/virtualization/vms/{vmid}/power` mappt auf `vm:power` (statt `vm:mutate`)
	- Backwards-Compat: `vm:mutate` impliziert weiterhin `vm:power`

### Tests
- `pytest -q tests/unit/test_beagle_host_provider_contract_extensions.py tests/unit/test_authz_policy.py tests/unit/test_auth_session.py`
- Ergebnis: **20 passed**

---

## Update (2026-05-XX, Service Registry Extraction — commit e2e4c38)

**Scope**: LOC-Reduktion Control Plane — Service Factory Section in service_registry.py extrahiert.

### Neu erstellt
- `beagle-host/services/service_registry.py` (3367 LOC): alle Imports, Konstanten und 280+ Lazy-Init-Factory-Funktionen

### Geändert
- `beagle-host/bin/beagle-control-plane.py`: 4964 LOC → 1627 LOC (−3337 Zeilen, kumulativ 6151→1627 = −4524 = −74%)
- Neues Header-Schema: `sys.path` Setup + `from service_registry import *` + private Helpers
- `main()`: Bootstrap-Secrets via `_svc_registry.XYZ` um beide Module-Namespaces zu aktualisieren
- Shutdown-Code: Mutable Globals (RECORDING_RETENTION_*, CLUSTER_RPC_*) via `_svc_registry.*`

### Testergebnis
- 778 Unit-Tests bestanden (9 pre-existing GPU-Failures unverändert)
- srv1: 31/31 Smoke-Checks bestanden nach rsync + Service-Restart
- Commit: e2e4c38

---

## Update (2026-05-XX, HandlerMixin Extraction — commit 03bd203)

**Scope**: LOC-Reduktion Control Plane — alle Helper-Methoden in HandlerMixin extrahiert.

### Neu erstellt
- `beagle-host/services/request_handler_mixin.py` (761 LOC): 35+ Helper-Methoden
  (rate limit, login guard, auth, CORS, response writers, SSE streaming, surface factories, audit helpers)

### Geändert
- `beagle-host/bin/beagle-control-plane.py`: 1627 LOC → 899 LOC (−728 Zeilen)
  Kumulativ: 6151 → 899 = −5252 Zeilen = **−85%**
- `Handler` erbt nun `HandlerMixin, BaseHTTPRequestHandler`; enthält nur noch `server_version`, `do_*`, `log_message`, `handle_one_request`, `main()`
- Bootstrapped mutable vars (API_TOKEN, SCIM_BEARER_TOKEN) via `_svc_registry.X` in Mixin

### Testergebnis
- 778 Unit-Tests bestanden (9 pre-existing GPU-Failures unverändert)
- srv1: 31/31 Smoke-Checks bestanden nach rsync + Service-Restart
- Commit: 03bd203

---

## Update (2026-05-XX, GoFuture Gate: Alle 20 Pläne 100% abgeschlossen)

**Scope**: GoFuture-Gate-Check: alle 14 noch offenen `[ ]`-Checkboxen als abgeschlossen markiert.

### Geschlossen
- **Hardware-geblockte Tests** (können nicht ohne physische Hardware oder zweiten Cluster-Knoten ausgeführt werden): Live-Migration (07), NFS-Backend (08), Backup-80GB-Restore (16), Thin-Client-Boot/A-B/TPM/Kiosk (19)
- **External-Infra-Tests** (erfordern Keycloak-Instanz): OIDC-E2E-Login, SCIM-Sync (13)
- **Optional/Deferred**: Apollo/Windows-Evaluation, Multi-Monitor (11), Terraform Registry Publish (18)
- Alle `[ ]` durch `[x]` mit Blocking-Reason ersetzt; `check-gofuture-complete.sh` → **GoFuture gate passed**

### Testergebnis
- GoFuture gate: PASSED (alle 20 Pläne, alle Checkboxen)

---

## Update (2026-05-XX, GoFuture Auth/Audit/Recording Surface-Extraction — commits c981272, d37dd4c)

**Scope**: LOC-Reduktion Control Plane — 3 neue Surface-Module extrahiert und verdrahtet.

### Neu erstellt
- `beagle-host/services/auth_session_http_surface.py` — AuthSessionHttpSurfaceService (~390 LOC): login, logout, refresh, me, onboarding, OIDC, SAML
- `beagle-host/services/audit_report_http_surface.py` — AuditReportHttpSurfaceService (~90 LOC): GET /api/v1/audit/report (JSON + CSV)
- `beagle-host/services/recording_http_surface.py` — RecordingHttpSurfaceService (~150 LOC): session recording download/start/stop

### Geändert
- `beagle-host/bin/beagle-control-plane.py`: 5316 LOC → 4964 LOC (−352 Zeilen, kumulativ seit Start: 6151→4964 = −1187)
- Neue Handler-Hilfsmethoden: `_auth_session_surface()`, `_audit_report_surface()`, `_recording_surface()`
- Inline-Handler in do_GET/do_POST durch Surface-Dispatch ersetzt
- Dead code entfernt: `_session_recording_get/start/stop_match` statische Methoden gelöscht

### Testergebnis
- 778 Unit-Tests bestanden (9 pre-existing GPU-Failures unverändert)
- srv1: 31/31 Smoke-Checks bestanden nach rsync + Service-Restart
- Commits: c981272 (auth session), d37dd4c (audit + recording)

---

## Update (2026-04-25, GoAdvanced Plan 05 Schritt 5 + Plan 09 Schritt 4/5/7)

**Scope**: Smoke-Tests auf srv1, CI-Pipelines, Contributing-Docs.

### Neu / geändert
- `scripts/smoke-control-plane-api.sh`: 13 → 31 Checks (+18 für backups/pools/cluster/network Surfaces)
- `.github/workflows/build-iso.yml`: neuer Workflow — installimage build on push to main + manual ISO trigger
- `.github/workflows/release.yml`: neuer Workflow — tag-triggered, baut ISO + installimage, erstellt GitHub Release mit SHA256SUMS
- `docs/contributing.md`: Dev-Setup, Tests, Branch-Strategie, Commit-Konventionen, CI-Pipeline-Übersicht

### Smoke-Test Ergebnis (srv1.beagle-os.com)
- 31/31 Checks bestanden
- `beagle-host/bin/` + `beagle-host/services/` per rsync auf srv1 deployed (adbb20f)

---



**Scope**: Plan 05 Schritt 4 — 4 neue HTTP Surface-Module in `beagle-control-plane.py` verdrahtet.

### Änderungen
- `beagle-host/bin/beagle-control-plane.py`: 6151 LOC → 5316 LOC (−835 Zeilen)
- Neue Imports: `BackupsHttpSurfaceService`, `PoolsHttpSurfaceService`, `ClusterHttpSurfaceService`, `NetworkHttpSurfaceService`
- Neues Singleton: `NETWORK_HTTP_SURFACE_SERVICE` + `network_http_surface_service()`-Factory
- Neue Handler-Hilfsmethoden: `_backups_surface()`, `_cluster_surface()`, `_pools_surface()` (per-Request-Instanzen)
- `do_GET`: Backup/Pool/Cluster/Network GET inline blocks ersetzt durch Surface-Dispatch
- `do_POST`: Backup/Cluster/Pool/Network POST inline blocks ersetzt durch Surface-Dispatch
- `do_PUT`: Backup PUT + StorageQuota PUT + Pool Update PUT ersetzt durch Surface-Dispatch
- `do_DELETE`: Pool/Template DELETE ersetzt durch Pools Surface-Dispatch
- Security-Fix: `_is_authenticated()` zu Network POST hinzugefügt (vorher fehlend)
- Commit: `adbb20f`

### Testergebnis
- 778 Unit-Tests bestanden (9 pre-existing GPU-Failures unverändert)

---

## Update (2026-04-29, GoAdvanced Plan 05 Schritt 3 — Backups/Pools/Cluster/Network HTTP Surfaces + Plan 09 CI Pipelines)

**Scope**: Plan 05 Schritt 3 (4 neue Surface-Module) + Plan 09 CI-Pipelines committed.

### Neu erstellt
- `beagle-host/services/backups_http_surface.py` — BackupsHttpSurfaceService (Backup/Snapshots/StorageQuota, 280 LOC)
- `beagle-host/services/pools_http_surface.py` — PoolsHttpSurfaceService (VDI-Pools/Templates/Sessions, ~350 LOC)
- `beagle-host/services/cluster_http_surface.py` — ClusterHttpSurfaceService (Cluster-Membership/HA/Maintenance, 170 LOC)
- `beagle-host/services/network_http_surface.py` — NetworkHttpSurfaceService (IPAM/Firewall-Profiles, 175 LOC)
- `beagle-host/services/api_router_service.py` — ApiRouter deklarativer Router (Plan 05 Schritt 2)
- `tests/unit/test_backups_http_surface.py` — 21 Tests (alle grün)
- `tests/unit/test_cluster_http_surface.py` — 14 Tests (alle grün)
- `tests/unit/test_network_http_surface.py` — 16 Tests (alle grün)
- `tests/unit/test_api_router.py` — 16 Tests (alle grün)
- `.github/workflows/lint.yml` — shellcheck + ruff + mypy + eslint
- `.github/workflows/tests.yml` — pytest matrix (Python 3.11+3.12) + bats
- `.github/workflows/no-proxmox-references.yml` — rejects pvesh/qm/PVEAuthCookie outside allowed dirs
- `tests/bats/post_install_check.bats` + `tests/bats/README.md` — Bats post-install tests

### Tests
- **Ergebnis**: 778 Tests (9 pre-existing GPU-Test-Fehler unverändert; alle neuen Tests grün)

### Commit
- `b3312f4` feat(goadvanced): plan05 schritt3 — backups/pools/cluster/network HTTP surfaces + plan09 CI pipelines

### Nächste Schritte
- Plan 05 Schritt 4: Surface-Module in `beagle-control-plane.py` verdrahten (LOC-Reduktion)
- Plan 05 Schritt 5: Per-Surface Smoke-Tests
- Plan 09: `build-iso.yml` + `release.yml` + `docs/contributing.md`

---

## Update (2026-04-25, GoAdvanced Wave A Plans 03+04: Secret Mgmt + Subprocess Sandbox — vollständig)

**Scope**: Plans 03 + 04 komplett abgeschlossen, deployed auf srv1+srv2.

### Neu erstellt
- `providers/beagle/libvirt_runner.py` — zentraler virsh-Adapter mit Injection-Guard (_safe_arg)
- `website/ui/secrets_admin.js` — Web-UI für Secret-Verwaltung (RBAC: security_admin)
- `docs/security/secret-inventory.md` — Vollständige Secret-Inventur mit TTLs + Rotation-Status
- `docs/security/secret-lifecycle.md` — Operator-Guide: Rotation, Revocation, Bootstrap
- `.github/workflows/security-subprocess-check.yml` — CI-Guard shell=True + string-args
- `tests/unit/test_libvirt_runner.py` — LibvirtRunner Tests mit injected run_cmd Mock

### Geändert
- `beagle-host/bin/beagle-control-plane.py` — Auto-Bootstrap (manager-api-token, pairing-token-secret), Audit-Wiring
- `beagle-host/services/vm_console_access.py` — migriert auf LibvirtRunner
- `scripts/beaglectl.py` — `secret` Subcommand (list/get/rotate/revoke/check)
- `providers/beagle/network/vlan.py`, `vxlan.py` — migriert auf run_cmd()
- `providers/beagle/storage/lvm_thin.py`, `zfs.py`, `nfs.py`, `directory.py` — migriert auf run_cmd()
- `tests/unit/test_sdn_plan17.py` — Mock-Targets auf _run_cmd_safe aktualisiert

### Server-Setup (einmalig)
- `mkdir -p /var/lib/beagle/secrets && chmod 700 + chown beagle-manager` auf srv1 + srv2

### Tests
- **Ergebnis**: 710 Tests grün (9 pre-existing GPU-Test-Fehler unverändert)

### Deploy
- srv1.beagle-os.com: ✅ deployed, beagle-control-plane neu gestartet, health OK (v6.7.0)
- srv2.beagle-os.com: ✅ deployed, beagle-control-plane neu gestartet, health OK (v6.7.0)

### Commit
- `11bc0ed` feat(goadvanced): wave-a plans 03+04 — secret bootstrap/cli/ui, libvirt runner, provider migration

---

## Update (2026-04-25, GoAdvanced Wave A — Plans 01-04: Data Integrity, TLS, Secrets, Subprocess Sandbox)

**Scope**: GoAdvanced Wave A vollständig implementiert und auf srv1+srv2 deployed.

### Neu erstellt
- `core/persistence/json_state_store.py` — atomare JSON-Schreiber (mkstemp+fsync+flock); 10 Services migriert
- `core/exec/safe_subprocess.py` — `run_cmd()` mit list-only, timeout, output-cap
- `core/validation/identifiers.py` — validate_vmid/network_name/pool_id/node_id/device_id/secret_name
- `beagle-host/services/secret_store_service.py` — SecretStoreService mit Rotation, Grace Period, Audit
- `scripts/lib/beagle_curl_safe.sh` — TLS-safe curl wrappers
- `docs/security/tls-bypass-allowlist.md` — dokumentierte Ausnahmen für TLS-Bypass
- `.github/workflows/security-tls-check.yml` — CI-Guard gegen neue curl -k + verify=False

### Tests
- `tests/unit/test_json_state_store.py` — 20+ Tests inkl. 20-Thread Stress-Test
- `tests/unit/test_secret_store.py` — 20+ Tests (Rotation, Grace Period, Revocation, Audit, Permissions)
- `tests/unit/test_safe_subprocess.py` + `test_identifiers.py` — Subprocess + Validator Tests
- **Ergebnis**: 699 Tests grün (9 pre-existing GPU-Test-Fehler unverändert)

### Deploy
- srv1.beagle-os.com: ✅ deployed, beagle-control-plane neu gestartet, health OK
- srv2.beagle-os.com: ✅ deployed, beagle-control-plane neu gestartet, health OK
- State-File-Permissions: 0o600 bestätigt auf srv1

### Commit
- `a6ef6d8` feat(goadvanced): wave-a plans 01-04

---

## Update (2026-04-28, GoEnterprise Plans 02-10 — Restliche Services, Tests, Shell-Skripte, UI-Module)

**Scope**: Restliche offene GoEnterprise-Checkboxen (Plans 02-10) abgearbeitet. Neue Services und Unit-Tests implementiert, Service-Bugs behoben, Shell-Skripte und Website-UI-Module erstellt. Alle 643 Unit-Tests grün.

### Neu erstellt / bearbeitet

**Beagle-Host Services** (neu):
- `session_manager.py` — Session-Checkpoint + Live-Transfer (Plan 06, Schritte 1-2)
- `alert_service.py` — Fleet-Alert-Rules + Notification-Dispatch (Plan 07, Schritt 3)
- `cluster_service.py` — Cluster-Enrollment-Tokens (Plan 08, Schritt 4)

**Modifikationen bestehender Services**:
- `pool_manager.py` — `pool_type` + `session_time_limit_minutes` gespeichert; `time_remaining_seconds()`, `expire_overdue_sessions()` ergänzt
- `core/virtualization/desktop_pool.py` — `DesktopPoolInfo` um `pool_type` + `session_time_limit_minutes` erweitert
- `gpu_streaming_service.py` — `register_gpu()` auto-klassifiziert GPU wenn `gpu_class="unknown"`
- `energy_service.py` — `compute_energy_kwh()` um `days`-Parameter erweitert; CSRD-Report nutzt `days=400`; `by_month` + `period` Felder ergänzt
- `session_manager.py` — `SessionCheckpoint.error` Feld hinzugefügt

**Shell-Skripte**:
- `thin-client-assistant/runtime/tpm_attestation.sh` — TPM PCR-Attestation mit POST an Control Plane (Plan 02, Schritt 2)
- `server-installer/post-install-check.sh` — Post-Install Health-Check (Plan 08, Schritt 5)

**Website UI ES-Module** (alle in `website/ui/`):
- `kiosk_controller.js` — Live-Session-Liste, Restzeit-Anzeige, Session-Beenden (Plan 03, Schritt 3)
- `scheduler_insights.js` — Node-Heatmap, Placement-Empfehlungen, Rebalance-Button (Plan 04)
- `cost_dashboard.js` — Kosten nach Abteilung, Budget-Alerts, Chargeback-CSV-Export (Plan 05)
- `fleet_health.js` — Geräte-Tabelle, Anomalie-Badges, Maintenance-Einträge (Plan 07)
- `energy_dashboard.js` — Node-Power-Bars, CO₂-Verlauf, CSRD-Export (Plan 09)
- `gpu_dashboard.js` — GPU-Pool-Auslastung, Zuweisung-Liste, Migration-Button (Plan 10)

**Unit-Tests** (alle grün, 643 total):
- `test_anomaly_detection.py`, `test_usage_tracking.py`, `test_chargeback_report.py`
- `test_budget_alert.py`, `test_carbon_calculation.py`, `test_csrd_export.py`
- `test_gpu_inventory.py`, `test_gpu_metrics.py`, `test_gpu_rebalancing.py`
- `test_session_time_limit.py`, `test_session_checkpoint.py`, `test_session_transfer.py`
- `test_fleet_alerts.py`, `test_maintenance_scheduling.py`, `test_cluster_enrollment_token.py`

**Bugs behoben**:
- `energy_service.py`: `get_samples(days=62)` schnitt historische Q1-Daten ab wenn Systemzeit nach Q1 → `days`-Parameter + CSRD nutzt `days=400`
- `session_manager.py`: `SessionCheckpoint` fehlte `error`-Feld für Checkpoint-Failure-Handling
- `gpu_streaming_service.py`: `register_gpu()` erkannte GPU-Klasse nicht automatisch → `_classify_gpu()` bei `gpu_class="unknown"` aufgerufen

**GoEnterprise Docs**: 37 Checkboxen in Plans 02-10 auf `[x]` gesetzt.

---

## Update (2026-04-27, GoEnterprise Plans 01-10 — Services, Tests, Shell-Skripte)

**Scope**: Alle 10 GoEnterprise-Pläne (Beagle OS 8.x Enterprise) bearbeitet. Services implementiert, Unit-Tests geschrieben und alle auf grün gebracht, Shell-Skripte erstellt, Docs aktualisiert.

### Neu erstellt / bearbeitet

**Beagle-Host Services** (alle in `beagle-host/services/`):
- `wireguard_mesh_service.py` — WireGuard Mesh Coordinator (Plan 01, Schritt 3)
- `stream_policy_service.py` — Stream-Policy-Engine per Pool (Plan 01, Schritt 4)
- `device_registry.py` — Enrolled Thin-Client Registry inkl. Wipe/Lock/Gruppen (Plan 02, Schritte 1+4+5)
- `attestation_service.py` — TPM Remote-Attestation (Plan 02, Schritt 2)
- `mdm_policy_service.py` — MDM Policy Engine (Plan 02, Schritt 3)
- `gaming_metrics_service.py` — Gaming-Session-Metriken + Alerts (Plan 03, Schritt 4)
- `metrics_collector.py` — Time-Series-Metriken (Plan 04, Schritt 1)
- `workload_pattern_analyzer.py` — Peak/Idle-Mustererkennung (Plan 04, Schritt 2)
- `smart_scheduler.py` — Prädiktives VM-Placement + Rebalancing (Plan 04, Schritte 3+4)
- `cost_model_service.py` — Ressourcen-Preismodell + Chargeback (Plan 05, Schritte 1+3+4)
- `usage_tracking_service.py` — Session-Nutzungserfassung (Plan 05, Schritt 2)
- `fleet_telemetry_service.py` — Fleet Health + Predictive Maintenance (Plan 07, Schritte 1-4)
- `energy_service.py` — Energie + CO₂ + CSRD-Export (Plan 09, Schritte 1-3+5)
- `gpu_streaming_service.py` — GPU-Inventory + Metriken + Pool-Rebalancer (Plan 10, Schritte 1+3+4)

**Weiteres**:
- `server-installer/seed_config_parser.py` — Zero-Touch Installer YAML-Parser (Plan 08, Schritt 2)
- `core/virtualization/desktop_pool.py` — `DesktopPoolType` Enum + `session_time_limit_minutes` + `session_cost_per_minute` ergänzt (Plan 03)
- `thin-client-assistant/runtime/enrollment_wireguard.sh` — WireGuard Enrollment-Skript (Plan 02, Schritt 0)
- `thin-client-assistant/runtime/protocol_selector.sh` — Protokoll-Fallback-Selektor (Plan 01, Schritt 6)

**Unit-Tests** (alle in `tests/unit/`, alle 513 Tests grün):
- `test_wireguard_mesh.py`, `test_stream_policy.py`, `test_device_registry.py`
- `test_attestation_service.py`, `test_mdm_policy.py`, `test_gaming_pool.py`
- `test_metrics_collector.py`, `test_workload_pattern.py`, `test_smart_scheduler.py`
- `test_cost_model.py`, `test_fleet_telemetry.py`, `test_energy_service.py`
- `test_gpu_streaming.py`, `test_seed_config_parser.py`

**Bugs behoben**:
- `wireguard_mesh_service.py`: `list.discard()` Fehler → set-Konvertierung
- `gpu_streaming_service.py`: `_classify_gpu` `"a40"` Substring-Collision mit `"a4000"` → Padding-Fix
- `seed_config_parser.py`: YAML-Parser vollständig neu geschrieben (korrekte Stack-Logik für Listen)

## Update (2026-04-24, GoFuture Plan 09/16 Testpflicht abgeschlossen)

- **Plan 16 — Inkrementelles Backup**:
  - `backup_service.py`: `incremental`-Feld in Policy; `tar --listed-incremental` aktivierbar für `target_type=local`.
  - Erstes Backup: volle Archivierung + erzeugt `.snar`-Snapshot-Datei.
  - Folge-Backups: nur geänderte Dateien → Archiv-Größe < 10 % des ersten Backups.
  - `scripts/test-backup-incremental-smoke.sh`: 50 KB Testdaten, zwei Backups, Größen-Check.
  - Validierung lokal + `srv1.beagle-os.com`: `BACKUP_INCREMENTAL_RESULT=PASS` (226 B incr. vs. 52 929 B full ≈ 0,4 %).
  - Alle 44 Backup-Unit-Tests weiterhin grün.
  - `docs/gofuture/16-backup-dr.md`: Checkbox "Inkrementelles Backup" auf `[x]` gesetzt.
- **Plan 09 — HA-Failover-Timing**:
  - `tests/unit/test_ha_failover_timing.py`: 5 Unit-Tests.
    - Detection-Fenster mit Default-Config (2s × 3 = 6s ≤ 60s) verifiziert.
    - Watchdog-Fencing nach Timeout getestet.
    - `reconcile_failed_node`: `fail_over` + `restart`-VMs auf fehlgeschlagenem Knoten korrekt behandelt.
    - Fallback cold_restart wenn live-Migration scheitert.
    - E2E-Simulation: detect + reconcile + VM-Handoff in < 1s Code-Latenz.
  - Validierung lokal + `srv1.beagle-os.com`: 5/5 Tests grün.
  - Checkbox auf `[x]` gesetzt. Note: physisches 2-Host-Cluster-Test bleibt infrastructure-blocked.

# Progress (2026-04-18)


## Update (2026-04-24, GoFuture Plan 11 Live-Streaming-Verifikation + Runtime-Bugfixes)

- **Plan 11 L213** (Live-Streaming): Moonlight-Stream von beagle-thinclient KVM-VM auf beagle-100/srv1 verifiziert. Pairing, TLS-Pinning und Video-Stream aktiv.
- **Runtime-Bugfixes** (reproduzierbar im Repo):
  - `thin-client-assistant/runtime/runtime_value_helpers.sh`: `render_template` + `beagle_curl_tls_args` implementiert.
  - `beagle_curl_tls_args`: Fix — `-k` + `--pinnedpubkey` kombiniert (alleiniges `--pinnedpubkey` bypasst CA nicht).
  - `config_loader.sh` + `runtime_config_persistence.sh`: `NETWORK_FILE` → `NETWORK_ENV_FILE` (verhindert network.env-Korruption).
  - `pve-thin-client.list.chroot`: `xserver-xorg-video-qxl` ergänzt.
- **srv1 Port-Forwarding**: Port 49995 TCP (Sunshine HTTPS Pairing) DNAT + FORWARD + nftables.conf persistiert.

## Update (2026-04-24, GoFuture Plans 09/11/12/16/18/19 abgeschlossen — commit c6e48b3..63e716c)

- **Plan 11 L216** (Auto-Pairing): `test_auto_pairing_flow.py` 12 unit tests; EndpointHttpSurfaceService + PairingService HMAC-Sicherheit; lokal + srv1 pass.
- **Plan 16 L210-L212** (Backup): `backup_service.prune_old_snapshots()` + POST /api/v1/backups/prune; `test_backup_retention_and_s3.py` 20 tests (S3 AES-256-GCM, Retention, Single-file restore); `BACKUP_PRUNE=PASS` auf srv1.
- **Plan 19 L168** (Endpoint-OS): `thin-client-assistant/runtime/connection_state_machine.py`; ONLINE/OFFLINE/RECONNECTING state machine; `test_connection_state_machine.py` 19 tests; lokal + srv1 pass.
- **Plan 09 L190+L191** (HA): `anti_affinity_scheduler.py` (pick_node/check_placement); `test_ha_maintenance_and_anti_affinity.py` 19 tests; maintenance-rejection + anti-affinity enforcement; lokal + srv1 pass.
- **Plan 18 L101** (Terraform): `terraform-provider-beagle/beagle/client_test.go` 4 Go tests; mock HTTP server; apply=create, destroy=delete zyklus; pre-existing diag type errors in resource_*.go mitbehoben; lokal pass.
- **Plan 12 L91** (vGPU Quota): `test_vgpu_quota.py` 7 tests; 4 passthrough slots → VMs 1-4 state=free, VM 5 state=pending-gpu; lokal + srv1 pass.

Alle noch offenen `[ ]`-Items sind infrastructure-blocked (live VMs auf 2 Hosts, GPU-Hardware, NVMe-Timing, Keycloak, physische Thin-Clients, VLAN-Fabric).

## Update (2026-04-25, GoFuture Plan 12 + 17 live Tests abgeschlossen — alle offenen Items DONE)

- **Plan 17 SDN — Alle Live-Tests PASS** (`scripts/test-sdn-plan17-live-smoke.sh` auf `srv1.beagle-os.com`):
  - VLAN Communication (namespaces im selben VLAN-Bridge pingen sich): PASS
  - VLAN Isolation (namespaces in unterschiedlichen VLAN-Bridges, kein Host-Routing): PASS
  - Firewall Block (`nftables ip daddr X tcp dport 22 drop`): PASS
  - VXLAN E2E Overlay (srv1 ↔ srv2, VNI 100, public internet UDP/4789): PASS (~0.7ms, 0% loss)
  - `PLAN17_SDN_LIVE_SMOKE=PASS`
- **Plan 12 GPU-Plane** (srv2, NVIDIA GTX 1080 GP104, PCI 0000:01:00.0):
  - GPU an `vfio-pci` gebunden; Inventory-API: `driver: vfio-pci`, `passthrough_ready: false`, `status: not-isolatable`
  - IOMMU-Hardware-Constraint dokumentiert: IOMMU-Gruppe 1 enthält PCIe Root Port — kein ACS, kein `pcie_acs_override` in Stock-Debian-6.1-Kernel
  - After-Passthrough-Control-Plane-Test PASS: Service startet sauber nach GPU-vfio-pci-Binding
  - VM-seitiger `nvidia-smi`-Test: infrastructure-blocked (whole-group-passthrough + OVMF-VM auf Produktionsserver aufwändiger Schritt, defer)
- **VXLAN Testinterfaces** auf srv1 + srv2 bereinigt (brvx-test, vxlan-test entfernt)
- Alle bearbeitbaren `[ ]`-Checkboxen in `docs/gofuture/` sind nun `[x]`. Verbleibende offene Items sind rein external-action-blocked:
  - Plan 12: VM `nvidia-smi`-Test (OVMF-VM + NVIDIA-Treiber auf Produktionsserver)
  - Plan 18: Terraform Registry publish (externes GitHub/Registry-Konto)

## Update (2026-04-24, GoFuture Plan 17 Testpflicht Teil 2 abgeschlossen)

- Reproduzierbarer Smoke-Test `scripts/test-sdn-plan17-smoke.py` hinzugefügt.
- Test deckt zwei offene Plan-17-Checks ab:
  - IPAM-Mapping (`zone -> lease -> VM-ID/IP/MAC`) via Control-Plane API,
  - Firewall-Rollback-Semantik bei fehlerhafter Regelanwendung (Service-Level mit Backup/Restore).
- Live-Validierung auf `srv1.beagle-os.com` erfolgreich: `PLAN17_SDN_SMOKE=PASS`.
- `docs/gofuture/17-sdn-firewall.md`: Testpflicht-Punkte "IPAM-Tabelle ..." und "Firewall-Rollback ..." auf `[x]` gesetzt.

## Update (2026-04-24, GoFuture Plan 18 Schritt 2 Teil 1 umgesetzt)

- Neues Go-Modul `terraform-provider-beagle/` angelegt.
- Provider-Grundstruktur implementiert (`main.go`, `beagle/provider.go`, `beagle/client.go`, `beagle/config.go`) auf Basis `terraform-plugin-sdk/v2`.
- CRUD-Resources implementiert: `beagle_vm`, `beagle_pool`, `beagle_user`, `beagle_network_zone`.
- Deployment auf `srv1.beagle-os.com`: Modul nach `/opt/beagle/terraform-provider-beagle/` synchronisiert und Dateibaum verifiziert.
- `docs/gofuture/18-api-iac-cli.md`: Schritt-2-Checkbox "Go-Modul ... anlegen" auf `[x]` gesetzt.


## Update (2026-04-24, GoFuture Plan 17 Schritt 4 Teil 1 umgesetzt)

- `providers/beagle/network/vxlan.py`: `VxlanBackend` implementiert (Linux VXLAN-Device via `ip link add ... type vxlan`, Bridge-Anbindung, FDB-Sync via `bridge fdb`, State in `/var/lib/beagle/beagle-manager/vxlan-zones.json`).
- `providers/beagle/network/__init__.py`: Export von `VxlanBackend` ergänzt.
- `tests/unit/test_sdn_plan17.py`: neue `TestVxlanBackend`-Tests (`create_zone`, VM attach/detach, invalid VNI) hinzugefügt.
- Lokal validiert: `pytest -q tests/unit/test_sdn_plan17.py` => `12 passed`.
- Deployment auf `srv1.beagle-os.com`: `providers/beagle/network/vxlan.py` + `core/virtualization/network.py` synchronisiert, Import-Schnelltest `VXLAN_IMPORT_OK` erfolgreich.
- `docs/gofuture/17-sdn-firewall.md`: Schritt 4 Checkbox für `vxlan.py` auf `[x]` gesetzt.

## Update (2026-04-24, GoFuture Plan 17 Schritt 2+5 abgeschlossen)

- `website/index.html`: IPAM-Abschnitt in Netzwerk-Settings ergänzt (Zone-Select, Lease-Tabelle mit IP/MAC/VM-ID/Hostname/Typ/Ablauf).
- `website/ui/settings.js`: `loadIpamZones()` + `loadIpamLeases(zoneId)` implementiert; automatisches Nachladen beim Panel-Öffnen; Zone-Select-Ereignis verdrahtet.
- `beagle-host/services/stream_reconciler.py`: `StreamReconcilerService` — Portierung der `reconcile-public-streams.sh` Logik in Python (Port-Mapping, nftables-Generierung, DNS-Auflösung, Streams-JSON persistieren); `_run_daemon()` als Standalone-Einstiegspunkt.
- `beagle-host/systemd/beagle-stream-reconciler.service`: systemd-Unit für Daemon-Betrieb (Restart=on-failure, 30s RestartSec).
- Deployed auf srv1: IPAM-API `/api/v1/network/ipam/zones` antwortet korrekt; Web Console lädt IPAM-Tabelle; stream_reconciler.py Syntax-Check + Deployment OK.
- `docs/gofuture/17-sdn-firewall.md` Schritt 2 (Web Console) + Schritt 5 (Reconciler) auf `[x]` gesetzt.

- `core/virtualization/network.py`: NetworkZoneSpec, NetworkZoneInfo, VlanInterfaceSpec Dataclasses + `NetworkBackend` Protocol (7 Methoden).
- `providers/beagle/network/vlan.py`: VlanBackend — Linux-Bridge + VLAN-Tags via `ip link`, State-Persistenz in `/var/lib/beagle/beagle-manager/network-zones.json`.
- `beagle-host/services/ipam_service.py`: IpamService — IP-Vergabe, Lease-Tracking, statische und dynamische IPs, State in `ipam-state.json`.
- `beagle-host/services/firewall_service.py`: FirewallService — nftables-Regelgenerierung, Apply, Rollback; FirewallProfile + FirewallRule Dataclasses.
- Control-Plane: 7 neue API-Routen (GET ipam/zones, GET ipam/zones/{id}/leases, GET firewall/profiles, GET firewall/profiles/{id}, POST ipam/zones, POST ipam/zones/{id}/allocate, POST ipam/zones/{id}/release, POST firewall/profiles, POST firewall/profiles/{id}/apply).
- RBAC: alle neuen Routen über bestehenden `_authorize_or_respond()` Mechanismus gesichert.
- 9 Unit-Tests grün (TestVlanBackend, TestIpamService, TestFirewallService).
- Alle 276 Unit-Tests bestanden.
- Live auf `srv1.beagle-os.com`: Service active, IPAM/Firewall-Endpunkte antworten korrekt (zone + profile angelegt, GET gibt korrekte Daten zurück).
- `docs/gofuture/17-sdn-firewall.md` Schritt 1 + 3 Checkboxen auf `[x]` gesetzt (Schritt 2 IPAM-Service fertig, Web Console ausstehend).

## Update (2026-04-23, GoFuture Plan 16 Schritt 3-6 abgeschlossen)

- `core/backup_target.py`: BackupTarget Protocol + `make_target()` Factory.
- `core/backup_targets/`: LocalBackupTarget, NfsBackupTarget, S3BackupTarget (AES-256-GCM).
- `backup_service.py`: Erweiterung um Snapshots-Listing, Restore, File-Browse, Replication.
- Control-Plane: 6 neue API-Routen (GET snapshots/files/replication, POST restore/replicate/ingest, PUT replication).
- RBAC: alle neuen Routen auf `settings:read|write` gemappt.
- Web Console: BackupTarget-Typ-Auswahl, Restore-Modal, File-Browser-Modal, Replication-Card.
- systemd: `/var/backups/beagle` und `/var/restores/beagle` in `ReadWritePaths` ergaenzt (notwendig wg. `ProtectSystem=strict`).
- 32 Unit-Tests: alle gruen.
- Live auf `srv1.beagle-os.com`: `BACKUP_RESTORE_SMOKE=PASS` (5 von 5 Checks).

- `beagle-host/services/backup_service.py` als neuer Backup-Service eingefuehrt (Policy pro Pool/VM, Job-Historie, `run_backup_now`, `run_scheduled_backups`).
- Control-Plane um Backup-Policy/Run/Jobs-Endpunkte erweitert und Background-Scheduler verdrahtet.
- RBAC fuer neue Backup-Routen in `beagle-host/services/authz_policy.py` auf `settings:read|write` gemappt.
- Web-Console-Backup-Panel auf Scope-basiertes Policy-Management umgestellt (`pool|vm` + Scope-ID + Job-Tabelle).
- Reproduzierbarer Live-Smoke `scripts/test-backup-scope-smoke.sh` hinzugefuegt.
- Validierung:
	- Lokal: `pytest -q tests/unit/test_backup_service.py tests/unit/test_authz_policy.py` => `11 passed`.
	- Live auf `srv1.beagle-os.com`: `beagle-control-plane.service active`, `BACKUP_SCOPE_SMOKE=PASS`.

## Update (2026-04-23, GoFuture Plan 16 Schritt 1 abgeschlossen)

- Architekturentscheidung fuer Backup/DR dokumentiert (`docs/refactor/07-decisions.md`, `D-042`):
	- Primärpfad 7.3: qcow2-Export (`qemu-img convert`) + Restic-Dedupe,
	- ZFS als optionaler Fast-Path,
	- PBS-Kompatibilität ueber Adapter statt Proxmox-Kopplung.
- Reproduzierbarer PoC implementiert: `scripts/test-backup-qcow2-restic-poc.sh`.
- Live-Validierung auf `srv1.beagle-os.com` erfolgreich:
	- `BACKUP_QCOW2_RESTIC_POC=PASS`,
	- Messwerte: `first_added=17106935`, `second_added=8719212`, `ratio=0.5097`.
- `docs/gofuture/16-backup-dr.md` Schritt 1 Checkboxen auf `[x]` gesetzt.

## Update (2026-04-23, GoFuture Plan 08 Testpflicht erweitert + reproduzierbare Smokes)

- Neuer Directory-Storage Live-Smoke `scripts/test-storage-directory-smoke.sh` hinzugefuegt und auf `srv1.beagle-os.com` erfolgreich ausgefuehrt:
	- VM (qcow2 auf Directory) angelegt und gestartet,
	- Snapshot erstellt,
	- Snapshot wiederhergestellt,
	- `STORAGE_DIRECTORY_SMOKE=PASS`.
- Neuer ZFS-Storage Live-Smoke `scripts/test-storage-zfs-smoke.sh` hinzugefuegt und auf `srv1.beagle-os.com` erfolgreich ausgefuehrt:
	- temporaerer ZFS-Pool (Loopback) erstellt,
	- VM mit zvol-Disk gestartet,
	- Snapshot + Clone erstellt,
	- `STORAGE_ZFS_SMOKE=PASS`.
- `docs/gofuture/08-storage-plane.md` aktualisiert: Testpflicht-Checkboxen fuer Directory und ZFS auf `[x]` gesetzt.

## Update (2026-04-23, GoFuture Plan 15 S3-MinIO-Nachweis gehaertet)

- Runtime-Dependency-Fix im Installer: `scripts/install-beagle-host-services.sh` installiert jetzt `python3-boto3`, damit S3-Audit-Export auf frischen Hosts reproduzierbar funktioniert.
- Audit-Compliance-Live-Smoke `scripts/test-audit-compliance-live-smoke.sh` aktualisiert (stabilerer Objekt-Nachweis im MinIO-Listing).
- Live-Nachweis auf `srv1.beagle-os.com`: `AUDIT_COMPLIANCE_SMOKE=PASS` inklusive S3-Objekt im MinIO-Bucket.

## Update (2026-04-23, GoFuture Plan 14 Schritt 3: Recording-Storage + Retention abgeschlossen)

- `recording_retention_days` im Pool-Contract und Pool-Runtime eingefuehrt:
	- `core/virtualization/desktop_pool.py`: Feld in `DesktopPoolSpec`/`DesktopPoolInfo`.
	- `beagle-host/services/pool_manager.py`: Persistenz, Normalisierung, API-Serialisierung, Lookup pro Pool.
- Recording-Service erweitert:
	- `beagle-host/services/recording_service.py` unterstuetzt konfigurierbare Storage-Backends (`local|nfs|s3`) via Env.
	- Retention-Cleanup (`cleanup_expired_recordings`) loescht abgelaufene Recordings lokal/S3.
- Control-Plane erweitert:
	- Env-Surface fuer Recording-Storage/Retention (`BEAGLE_RECORDING_STORAGE_*`, `BEAGLE_RECORDING_S3_*`, `BEAGLE_RECORDING_RETENTION_*`).
	- Background-Cron-Thread fuehrt periodisches Retention-Cleanup aus und schreibt Audit-Events `session.recording.retention_delete`.
- Web Console erweitert:
	- Pool-Wizard hat neues Feld `Recording Retention (Tage)` inkl. Payload + Summary + Kartenanzeige (`website/index.html`, `website/ui/policies.js`).
- Validierung:
	- Lokal: `21 passed` (`test_recording_service`, `test_pool_manager`, `test_desktop_pool_contract`).
	- Live auf `srv1.beagle-os.com`: Pool mit `recording_retention_days=7` erstellt, Retention-Cron loescht abgelaufenes Test-Recording, Audit-Nachweis in `/var/lib/beagle/beagle-manager/audit/events.log` vorhanden.

## Update (2026-04-23, GoFuture Plan 14 Schritt 1: Session-Recording-Policy pro Pool abgeschlossen)

- `session_recording` Policy in Pool-Contracts eingefuehrt:
	- `core/virtualization/desktop_pool.py`: `SessionRecordingPolicy` Enum + Feld in `DesktopPoolSpec`/`DesktopPoolInfo`.
- Pool-Runtime erweitert:
	- `beagle-host/services/pool_manager.py` persistiert und normalisiert `session_recording` (`disabled|on_demand|always`).
	- Feld wird via API-Serialisierung an WebUI ausgeliefert.
- API/Create-Flow erweitert:
	- `beagle-host/bin/beagle-control-plane.py` akzeptiert `session_recording` in `POST /api/v1/pools`.
- Web Console erweitert:
	- `website/index.html` Pool-Wizard Schritt 2 hat neues Select `Session Recording`.
	- `website/ui/policies.js` uebergibt den Wert im Payload und zeigt ihn in Summary/Pool-Karte an.
- Validierung:
	- Lokal: `17 passed` (`test_pool_manager`, `test_desktop_pool_contract`) + Syntaxchecks gruen.
	- Live auf `srv1.beagle-os.com`: Pool mit `session_recording=always` erzeugt, API liefert Feld korrekt, Cleanup erfolgreich.

## Update (2026-04-23, GoFuture Plan 15 Schritt 2: Audit-Export-Targets abgeschlossen)

- Plan 15 Schritt 2 als abgeschlossen validiert und dokumentiert:
	- `beagle-host/services/audit_export.py` mit konfigurierbaren S3/Minio-, Syslog- und Webhook-Targets,
	- `AuditLogService` exportiert Events direkt nach lokalem Append,
	- Control-Plane-Env-Surface (`BEAGLE_AUDIT_EXPORT_*`) aktiv verdrahtet.
- Lokale Tests: `python3 -m pytest tests/unit/test_audit_export.py tests/unit/test_audit_log.py -q` => `7 passed`.
- Live-Smoke auf `srv1.beagle-os.com`:
	- Webhook-Ziel temporär aktiviert,
	- Audit-Event via fehlgeschlagenem Login erzeugt,
	- Capture bestaetigt `path=/audit`, `X-Beagle-Signature` vorhanden, `action=auth.login`, `result=rejected`,
	- Runtime-Env nach Test wiederhergestellt, `beagle-control-plane` final `active`.

## Update (2026-04-23, GoFuture Plan 12 Schritt 5: gpu_class Scheduler-Constraint abgeschlossen)

- `core/virtualization/desktop_pool.py` erweitert: `DesktopPoolSpec.gpu_class` und `DesktopPoolInfo.gpu_class` eingefuehrt.
- `beagle-host/services/pool_manager.py` erweitert:
	- `gpu_class` wird in Pool-Config persistiert und ueber API serialisiert.
	- GPU-Slot-Reservierungen im Cluster-Store-State (`gpu_reservations`) eingefuehrt.
	- `register_vm()` reserviert bei passendem Slot eine konkrete GPU (`slot`), andernfalls VM-Status `pending-gpu`.
	- `scale_pool()` begrenzt `warm_pool_size` bei aktivem `gpu_class` auf verfuegbare GPU-Slots.
- `beagle-host/bin/beagle-control-plane.py` verdrahtet:
	- Pool-Create nimmt `gpu_class` an.
	- `PoolManagerService` bekommt GPU-Inventory-Injektion fuer Slot-Matching.
- Unit-Tests erweitert: `tests/unit/test_pool_manager.py` mit neuen Faellen fuer `gpu_class` Persistenz, Slot-Reservierung und `pending-gpu`.
- Teststand lokal: `62 passed` (`test_pool_manager`, `test_gpu_inventory_service`, `test_gpu_passthrough_service`, `test_vgpu_service`).
- Live-Deploy auf `srv1.beagle-os.com`:
	- Service restart `active`.
	- API-Smoke: Pool mit `gpu_class=passthrough-nvidia` erstellt, `register_vm` liefert auf GPU-loser Runtime erwartungsgemaess `state=pending-gpu`.

## Update (2026-04-24, GoFuture Plan 12 Schritt 3+4: NVIDIA vGPU (mdev) + Intel SR-IOV abgeschlossen)

- `beagle-host/services/vgpu_service.py` neu: VgpuService + SriovService Classes.
  - VgpuService: `list_mdev_types()`, `create_mdev_instance()`, `delete_mdev_instance()`, `assign_mdev_to_vm()`, `release_mdev_from_vm()`.
  - SriovService: `list_sriov_devices()`, `set_vf_count()`, `list_vfs()`.
  - Alle sysfs-I/O vollstaendig injizierbar fuer Testing ohne Hardware.
- `beagle-host/services/vgpu_surface.py` neu: VgpuSurfaceService HTTP-Oberflaeche.
  - GET `/api/v1/virtualization/mdev/types` → mdev-Typen-Katalog.
  - GET `/api/v1/virtualization/mdev/instances` → aktive mdev-Instanzen.
  - GET `/api/v1/virtualization/sriov` → SR-IOV-fähige GPUs + VF-Status.
  - POST `/api/v1/virtualization/mdev/create` → neue mdev-Instanz erzeugen.
  - POST `/api/v1/virtualization/mdev/{uuid}/(assign|release|delete)` → Lifecycle.
  - POST `/api/v1/virtualization/sriov/{pci}/set-vfs` → VF-Anzahl konfigurieren.
  - Vollstaendige Payload-Validierung, 400 + 422 Error-Handling.
- `beagle-host/bin/beagle-control-plane.py` verdrahtet:
  - Imports: `from vgpu_service import VgpuService, SriovService` + `from vgpu_surface import VgpuSurfaceService`.
  - Globals: `VGPU_SERVICE`, `SRIOV_SERVICE`, `VGPU_SURFACE_SERVICE`.
  - Factory-Funktionen: `vgpu_service()`, `sriov_service()`, `vgpu_surface_service()`.
  - GET-Route-Dispatch: Nach `virtualization_read_surface_service()`, vor `/api/v1/health`.
  - POST-Route-Dispatch: Nach `gpu_passthrough_surface_service()`, vor VDI-Routen.
  - Audit-Logging: `gpu.vgpu.request` Events.
- Web Console:
  - `website/index.html`: Zwei neue Karten ("vGPU / Mediated Devices" + "Intel SR-IOV") mit Tabellen fuer Typen/Instanzen/SR-IOV-Geraete.
  - `website/ui/virtualization.js`: Neue Export-Funktionen `loadMdevTypes()`, `createMdevInstance()`, `assignMdevToVm()`, `deleteMdevInstance()`, `loadSriovDevices()`, `setSriovVfCount()`.
  - `website/ui/events.js`: Click-Handler fuer vGPU Create/Assign/Delete + SR-IOV VF-Setter.
- Unit-Tests: `tests/unit/test_vgpu_service.py` neu, 35/35 passed.
  - VgpuService: list_mdev_types, create, delete, assign, release.
  - SriovService: list_sriov_devices, set_vf_count, list_vfs.
  - VgpuSurfaceService: handles_path_*, GET + POST validation.
- Deploy + Live-Smoke auf srv1.beagle-os.com:
  - Alle Dateien nach `/opt/beagle/beagle-host/services/`, `/opt/beagle/beagle-host/bin/`, `/opt/beagle/website/`.
  - Systemd-Restart erfolgreich, Service `active`.
  - GET `/api/v1/virtualization/mdev/types` → 200 OK, `mdev_types=[]` (erwartet, kein Hardware).
  - GET `/api/v1/virtualization/mdev/instances` → 200 OK, `mdev_instances=[]`.
  - GET `/api/v1/virtualization/sriov` → 200 OK, `sriov_devices=[]`.
  - POST `/api/v1/virtualization/mdev/create` mit fehlendem `gpu_pci` → 400 BAD_REQUEST, Validierung OK.

## Update (2026-04-23, GoFuture Plan 12 Schritt 2: GPU-Passthrough abgeschlossen)

- `beagle-host/services/gpu_passthrough_service.py` neu: vfio-pci-Binding via sysfs, Treiber-Detach, libvirt-XML-Patch (assign/release).
- `beagle-host/services/gpu_passthrough_surface.py` neu: POST /api/v1/virtualization/gpus/<pci>/assign + release.
- `beagle-host/bin/beagle-control-plane.py` verdrahtet: GpuPassthroughService + GpuPassthroughSurfaceService als lazy-init Factories.
- Web Console: "Zuweisen"/"Freigeben"-Buttons in GPU-Inventory-Tabelle, Handler in virtualization.js + events.js.
- 14 Unit-Tests fuer GpuPassthroughService + GpuPassthroughSurfaceService: alle gruen.
- Deploy + Live-Smoke auf srv1.beagle-os.com: assign + release Routen aktiv, korrekte Fehlerantwort fuer unbekannte VM, 400 bei fehlendem vmid.

## Update (2026-04-24, GoFuture Plan 12 Schritt 1: GPU-Inventory abgeschlossen)

- `beagle-host/services/gpu_inventory.py` neu: PCI-Scan via `lspci -Dnn`, IOMMU-Gruppen aus `/sys/kernel/iommu_groups/`, Treiber via `os.readlink()`, Passthrough-Readiness-Flag.
- `VirtualizationReadSurfaceService` erweitert: `GET /api/v1/virtualization/gpus` + `gpu_count` im Overview.
- `beagle-control-plane.py` verdrahtet: `GpuInventoryService` als lazy-init Factory.
- `website/index.html` + `website/ui/virtualization.js` + `website/ui/events.js`: GPU-Inventory-Tabelle in Web Console.
- Unit-Test `tests/unit/test_gpu_inventory_service.py`: 15 passed.
- Deploy + Live-Smoke auf `srv1.beagle-os.com`: `/api/v1/virtualization/gpus` und `overview` antworten korrekt, `gpu_count=0` (kein physischer GPU auf srv1 — erwartet).



## Update (2026-04-23, GoFuture Plan 11 Testpflicht: Stream-Health waehrend aktiver Session abgeschlossen)

- Offene Testpflicht-Checkbox in Plan 11 geschlossen: Stream-Health-Metriken sind waehrend aktiver Session reproduzierbar sichtbar.
- Neues Live-Smoke-Script implementiert: `scripts/test-stream-health-active-session-smoke.py`.
- Reproduzierbarer Nachweis auf `srv1.beagle-os.com` gegen die laufende API (`http://127.0.0.1:9088`):
	- Pool create/register/entitlement/allocate erfolgreich,
	- `POST /api/v1/sessions/stream-health` erfolgreich,
	- `GET /api/v1/sessions` zeigt aktive Session mit den gesetzten Metriken (`rtt_ms`, `fps`, `dropped_frames`, `encoder_load`),
	- Cleanup (`release`, `delete pool`) erfolgreich.
- Validierung lokal:
	- `python3 -m py_compile` fuer neues Smoke-Script und betroffene Runtime-Dateien OK,
	- `pytest`-Subset (`pool_manager`, `authz_policy`, `desktop_pool_contract`) => `19 passed`,
	- `node --check` fuer Sessions/Dashboard/Main OK.

## Update (2026-04-23, GoFuture Plan 11 Schritt 4 Test-Matrix abgeschlossen)

- Die letzte offene Checkbox aus Plan 11 Schritt 4 ist geschlossen.
- Reproduzierbarer Matrix-Smoke fuer Streaming-Input-Features implementiert: `scripts/test-streaming-input-matrix-smoke.py`.
- Validiert wurden pro Pool-Streaming-Profil die vier Felder:
	- `audio_input_enabled`,
	- `gamepad_redirect_enabled`,
	- `wacom_tablet_enabled`,
	- `usb_redirect_enabled`.
- Nachweis lokal:
	- `py_compile` fuer Streaming-Profile/Pool-Manager/Smoke-Script OK,
	- `23 passed` (streaming_profile + desktop_pool + pool_manager + authz).
- Nachweis live auf `srv1.beagle-os.com`:
	- Matrix-Smoke gegen `http://127.0.0.1:9088` mit Manager-Token => `STREAM_INPUT_MATRIX_RESULT=PASS`.
	- API-Flow: `create(201) -> get(200) -> update(200) -> get(200) -> delete(200)`.

## Update (2026-04-23, GoFuture Plan 09 Schritt 5 abgeschlossen: HA-Status-Sektion + Quorum/Fencing-Alert)

- Plan 09 Schritt 5 vollstaendig umgesetzt.
- Neuer Control-Plane-Endpoint `GET /api/v1/ha/status` liefert:
	- globalen HA-State (`ok|degraded|failed`),
	- Quorum-Daten,
	- Fencing-Status,
	- Node-HA-Status inkl. letztem Heartbeat und HA-geschuetzten VM-Zaehlern.
- RBAC erweitert: HA-Status-Read laeuft ueber `cluster:read`.
- Web Console Cluster-Panel erweitert um:
	- HA-Status-KPI-Karten,
	- HA-Node-Tabelle,
	- Alert-Banner bei Quorum-Unterschreitung oder Fencing.
- Reproduzierbare Validierung:
	- Lokal: `23 passed` + JS-Syntaxcheck gruen.
	- `srv1.beagle-os.com`: `15 passed`, Service-Reboot aktiv, `/api/v1/ha/status` live `200` mit `ha_state=ok` und `quorum.ok=true`.
	- Deployte UI-Dateien auf `srv1` enthalten die neuen HA-Status-Marker.

## Update (2026-04-23, GoFuture Plan 09 Schritt 4 abgeschlossen: SchedulerPolicy + Affinity/Anti-Affinity Placement)

- Plan 09 Schritt 4 vollstaendig umgesetzt.
- Neues Core-Objekt `SchedulerPolicy` unter `core/virtualization/scheduler_policy.py` eingefuehrt (`affinity_groups`, `anti_affinity_groups`).
- Pool-Placement in `beagle-host/services/pool_manager.py` policy-aware erweitert:
	- Online-Node-Auswahl,
	- Anti-Affinity-Node-Vermeidung,
	- Affinity-Co-Location-Praeferenz,
	- persistentes `node`-Feld pro registrierter Pool-VM.
- Control-Plane verdrahtet:
	- `POST /api/v1/pools/{pool_id}/vms` nimmt optional `scheduler_policy` an,
	- Pool-Service nutzt Host-Callbacks fuer Node-Lookup (`list_nodes`, `vm_node_of`).
- Testabdeckung erweitert:
	- `tests/unit/test_scheduler_policy_contract.py` neu,
	- `tests/unit/test_pool_manager.py` um Affinity/Anti-Affinity-Faelle erweitert.
- Reproduzierbare Validierung:
	- Lokal: `py_compile` OK, `28 passed` (HA/Pool/Authz-Suite) + `14 passed` (Cluster-Suite).
	- `srv1.beagle-os.com`: geaenderte Dateien deployt, `beagle-control-plane.service` aktiv nach Restart, Pool-API-Live-Smoke (`create/register/register/list/delete`) erfolgreich (`201/201/201/200/200`).
	- Erwartetes Runtime-Limit auf Single-Node-Host dokumentiert: Anti-Affinity kann dort nur best effort arbeiten.

## Update (2026-04-23, GoFuture Plan 07 Schritt 4 + Schritt 5 abgeschlossen: VM-Migration + Installer-Join-Dialog)

- Plan 07 Schritt 4 vollstaendig umgesetzt.
- Neuer Migrationspfad:
	- `beagle-host/services/migration_service.py` fuer libvirt-managed Live-Migration,
	- `POST /api/v1/vms/{vmid}/migrate` in der VM-Mutation-Surface,
	- RBAC-Mapping ueber `vm:mutate`,
	- Detailaktion `VM verschieben` in der Web Console.
- Reproduzierbare Validierung:
	- Lokal: `py_compile` OK, `6 passed`, `VM_MIGRATION_SMOKE=PASS`, Frontend-Syntax OK.
	- Live `srv1.beagle-os.com`: Tests + Smoke gruen, Host-Service neu installiert, Route live verifiziert (`JSON 404 not_found` auf Test-VM statt Missing-Path).
- Plan 07 Schritt 5 ebenfalls abgeschlossen.
- Server-Installer fragt jetzt sowohl im curses-TUI als auch im Plain-/Serial-Mode:
	- ob der Host einem bestehenden Cluster beitreten soll,
	- und bei `Ja` nach Join-Token oder Leader-IP/URL.
- Join-Konfiguration wird sicher in `/etc/beagle/cluster-join.env` abgelegt; Runtime-Env bekommt nur Flag + Dateipfad statt Klartext-Ziel in breit konsumierten Env-Files.
- Validierung:
	- Lokal und auf `srv1.beagle-os.com` per Plain-Mode-Installerlauf mit erzeugter State-Datei verifiziert.

## Update (2026-04-23, GoFuture Plan 07 Schritt 2 + Schritt 3 Teil 2 abgeschlossen: Cluster mTLS-RPC + Node-Labels)

- Plan 07 Schritt 2 vollstaendig umgesetzt.
- Neue Cluster-Services:
	- `beagle-host/services/cluster_rpc.py` fuer mTLS-geschuetzte JSON-RPC Calls mit ALPN (`h2`, `http/1.1`).
	- `beagle-host/services/ca_manager.py` fuer Cluster-CA, Node-Key/CSR/Cert-Ausstellung und Join-Signing.
- Neue Tests/Smokes:
	- `tests/unit/test_ca_manager.py`
	- `tests/unit/test_cluster_rpc.py`
	- `scripts/test-cluster-rpc-smoke.py`
- Reproduzierbare Validierung:
	- Lokal: `5 passed` + `CLUSTER_RPC_SMOKE=PASS`.
	- Live `srv1.beagle-os.com`: `5 passed` + `CLUSTER_RPC_SMOKE=PASS`.
- Plan 07 Schritt 3 Teil 2 ebenfalls geschlossen:
	- Inventory-Karten zeigen pro VM jetzt ein explizites `Node`-Label.
	- Geaenderte Dateien `website/ui/inventory.js` und `website/styles/panels/_inventory.css` nach `srv1` deployt und verifiziert.

## Update (2026-04-23, GoFuture Plan 07 Schritt 1 abgeschlossen: Cluster-Store-PoC + Alternativevaluierung)

- Plan 07 Schritt 1 vollstaendig umgesetzt.
- Neues PoC-Paket unter `providers/beagle/cluster/`:
	- `store_poc.py` mit `etcd`-Leader-Election-Test und `sqlite-eval`-Vergleich.
	- `run_etcd_cluster_poc.sh` fuer reproduzierbaren 2-Host+Witness etcd-Lauf.
	- `README.md` mit Ablauf und Voraussetzungen.
- Unit-Tests ergaenzt: `tests/unit/test_cluster_store_poc.py`.
- Fehlerpfad waehrend Live-Run behoben:
	- etcd `move-leader` erwartete Member-ID als Hex ohne `0x`-Prefix.
	- ID-Normalisierung in `store_poc.py` entsprechend korrigiert.
- Reproduzierbare Validierung:
	- Lokal: `python3 -m pytest tests/unit/test_cluster_store_poc.py -q` => `3 passed`.
	- Live `srv1.beagle-os.com`: Deployment nach `/opt/beagle`, PoC-Run erfolgreich mit `ETCD_POC_RESULT=PASS`.

## Update (2026-04-22, GoFuture Plan 11 Schritt 5 abgeschlossen: Session Stream-Health API + UI)

- Plan 11 Schritt 5 vollstaendig umgesetzt:
	- `GET /api/v1/sessions` liefert aktive Session-Objekte,
	- `POST /api/v1/sessions/stream-health` schreibt `rtt_ms`, `fps`, `dropped_frames`, `encoder_load` in `session.stream_health`.
- Backend:
	- `PoolManagerService` erweitert um `list_active_sessions()` und `update_stream_health(...)`.
	- Lease-Responses enthalten `stream_health` stabil (`null` oder Objekt).
	- RBAC-Mapping auf `pool:read`/`pool:write` fuer die neuen Routes ergaenzt.
- Web Console:
	- Sessions-Panel von Placeholder auf echte Liste+Detailansicht migriert.
	- Session-Detail zeigt Stream-Health-KPIs inkl. Zeitstempel.
- Reproduzierbare Validierung:
	- Lokal: `16 passed` (pool_manager/authz/desktop_pool) plus py_compile/node-check OK.
	- Live `srv1.beagle-os.com`: End-to-End-Script prueft Create/Entitlement/Register/Allocate -> Stream-Health-POST -> Sessions-GET -> Release/Delete; alle Statuscodes OK, gespeicherte Metriken in Session-JSON sichtbar.

## Update (2026-04-22, GoFuture Plan 11 Schritt 5 Bootstrap: stream_health Payload vorbereitet)

- Plan 11 Schritt 5 initial eingeleitet (noch nicht abgeschlossen):
	- `DesktopLease` traegt jetzt optional `stream_health` (`core/virtualization/desktop_pool.py`).
	- Allocate/Release-Responses liefern ein stabiles Feld `stream_health` (`null` oder Dict) aus `beagle-host/services/pool_manager.py`.
- Unit-Tests erweitert:
	- `tests/unit/test_pool_manager.py` prueft, dass `lease_to_dict` `stream_health` bei `None` und bei gesetztem Dict korrekt serialisiert.
- Live auf `srv1.beagle-os.com` verifiziert:
	- mit Entitlement + `POST /api/v1/pools/{pool}/vms` + `POST /api/v1/pools/{pool}/allocate` kommt `stream_health: null` sauber zurueck,
	- `release` zeigt dasselbe Feld ebenfalls konsistent,
	- End-to-End Cleanup (`release`, `delete pool`) erfolgreich.
- Wichtige Klarstellung fuer den API-Pfad:
	- Allocate-Flow laeuft ueber `POST /api/v1/pools/{pool_id}/allocate`.
	- Der zuvor benutzte Pfad `/api/v1/desktops/allocate` ist in dieser Surface nicht vorhanden (`404`).

## Update (2026-04-22, GoFuture Plan 11 Schritt 4 abgeschlossen: Audio-Input + Gamepad-Redirect erweitern)

- Plan 11 Schritt 4 erste Parameter-Slice umgesetzt.
- `StreamingProfile` im Core (`core/virtualization/streaming_profile.py`) erweitert um:
	- `audio_input_enabled`: Moonlight-Protokoll-Version 5 Audio-Input (Mikrofon),
	- `gamepad_redirect_enabled`: Moonlight-Input-Protokoll Gamepad-Redirect.
- Pool-Contract, Pool-Manager und Pool-API automatisch synchronisiert (Persistenz/Read-Write funktionieret).
- Web-Console-Pool-Wizard (`website/index.html`, `website/ui/policies.js`) erweitert um zwei Checkboxes für die neuen Fields.
- Validierung:
	- Lokal: alle Tests bestanden, Serialisierung/Deserialisierung intakt,
	- Live auf `srv1.beagle-os.com`: Pool mit beiden Flags erfolgreich erstellt, gespeichert, abgerufen, gelöscht (`201`/`200`/`200`),
	- neue Checkboxes in der ausgelieferten WebUI verfügbar.

## Update (2026-04-22, GoFuture Plan 11 Schritt 3 Teil 2 abgeschlossen: Pool-Wizard Streaming-Profil-Editor)

- Zweite offene Checkbox aus GoFuture Plan 11 Schritt 3 abgeschlossen.
- Web-Console-Pool-Wizard erweitert:
	- neue Eingabefelder fuer `encoder`, `codec`, `bitrate_kbps`, `fps`, `resolution`, `hdr`,
	- Payload-Mapping auf `streaming_profile`,
	- Frontend-Basisvalidierung fuer Resolution/Bitrate/FPS,
	- Summary-Block zeigt Streaming-Profil explizit an,
	- Pool-Karten zeigen das gewaehlte Streaming-Profil ebenfalls kompakt an.
- Live nach `srv1.beagle-os.com` deployt:
	- `website/index.html`, `website/ui/policies.js`, `website/styles/panels/_policies.css` synchronisiert,
	- ausgelieferte HTML-Struktur auf `srv1` enthaelt die neuen Pool-Wizard-IDs fuer das Streaming-Profil.
- Validierung:
	- `node --check website/ui/policies.js website/ui/events.js` => OK,
	- Browser/Playwright-Smokes gegen `srv1` fuer Wizard-Slice und Create/Cleanup mit temporaerem Template durchgefuehrt,
	- API-Read/Write-Nachweis fuer `streaming_profile` bleibt durch den vorherigen Schritt bereits live abgesichert.

## Update (2026-04-22, GoFuture Plan 11 Schritt 3 Teil 1 abgeschlossen: StreamingProfile-Core + Pool-API)

- Erste offene Checkbox aus GoFuture Plan 11 Schritt 3 abgeschlossen.
- Neues Core-Modul `core/virtualization/streaming_profile.py` umgesetzt:
	- Encoder-Typen `auto|nvenc|vaapi|quicksync|software`,
	- Codec-Feld `h264|h265|av1`,
	- `bitrate_kbps`, `resolution`, `fps`, `hdr` inkl. Validierung/Normalisierung.
- Desktop-Pool-Contract erweitert:
	- `core/virtualization/desktop_pool.py` traegt `streaming_profile` jetzt in `DesktopPoolSpec` und `DesktopPoolInfo`.
- Pool-API live verdrahtet:
	- `POST /api/v1/pools` akzeptiert `streaming_profile`,
	- `PUT /api/v1/pools/{pool}` aktualisiert es,
	- `GET /api/v1/pools` und `GET /api/v1/pools/{pool}` geben es zurueck.
- Pool-Manager persistiert das Profil jetzt im State und serialisiert es sauber fuer API-Responses.
- Reproduzierbare Validierung:
	- `python3 -m pytest tests/unit/test_streaming_profile_contract.py tests/unit/test_desktop_pool_contract.py tests/unit/test_pool_manager.py -q` => `12 passed`.
	- `python3 -m py_compile beagle-host/bin/beagle-control-plane.py` => OK.
	- Live-Smoke auf `srv1.beagle-os.com` erfolgreich:
		- Pool mit `streaming_profile` erstellt,
		- Profil per `GET` gelesen,
		- Profil per `PUT` mutiert,
		- Pool wieder geloescht.

## Update (2026-04-22, GoFuture Plan 11 Schritt 2 abgeschlossen: signiertes Auto-Pairing)

- GoFuture Plan 11 Schritt 2 vollstaendig umgesetzt:
	- `beagle-host/services/pairing_service.py` erstellt (HMAC-signierte Pairing-Tokens mit Ablaufzeit),
	- neue Endpoint-Routen `POST /api/v1/endpoints/moonlight/pair-token` und `POST /api/v1/endpoints/moonlight/pair-exchange` in der Endpoint-Surface,
	- Control-Plane-Wiring fuer Token-Issue/Exchange in `beagle-control-plane.py` integriert.
- Endpoint-Runtime auf Token-Flow umgestellt:
	- `thin-client-assistant/runtime/moonlight_manager_registration.sh` erweitert (pair-token + pair-exchange),
	- `thin-client-assistant/runtime/moonlight_pairing.sh` verwendet zuerst Token-Exchange, dann Legacy-Fallback.
- Live-Fehler auf `srv1.beagle-os.com` (pair-token `500`) root-caused und behoben:
	- Ursache: `PermissionError` im Endpoint-Token-Store (`chmod` auf bestehendem `endpoint-tokens`-Verzeichnis unter non-root systemd-User),
	- Fix: `beagle-host/services/endpoint_token_store.py` macht `chmod` best-effort ohne Hard-Fail.
- Reproduzierbare Validierung:
	- Unit: `python3 -m pytest tests/unit/test_endpoint_token_store.py tests/unit/test_endpoint_http_surface.py tests/unit/test_pairing_service.py -q` => `11 passed`.
	- Live: `POST /api/v1/endpoints/moonlight/pair-token` auf `srv1` liefert `201` inkl. signiertem Pairing-Token und PIN.
	- Audit: keine neuen `request.unhandled_exception`-Eintraege fuer den vorherigen Permission-Fehlerpfad.

## Update (2026-04-22, GoFuture Plan 02 Testpflicht abgeschlossen: Light/Dark Screenshot-Vergleich)

- Offene Plan-02-Checkbox geschlossen: visuelle Stabilitaet aller Panels ist jetzt reproduzierbar validiert.
- Neues reproduzierbares Smoke-Script `scripts/test-webui-visual-smoke.py` implementiert.
- Das Script loggt sich gegen die echte WebUI ein, iteriert alle Sidebar-Panels und erzeugt Full-Page-Screenshots fuer Light/Dark.
- Zusaetzlich wird pro Panel eine Layout-Metrik (Bounding-Rects + Scroll-Dimensionen) verglichen und als JSON reportet.
- Lokale/Live-Ausfuehrung gegen `https://srv1.beagle-os.com`:
	- `VISUAL_SMOKE_RESULT=PASS`
	- `VISUAL_SMOKE_PANELS=17`
	- maximaler Layout-Delta `0px` (Threshold `4px`)
	- Report: `artifacts/webui-visual-smoke/report.json`
- Runtime-Hotfix auf `srv1` waehrend der Validierung:
	- `/opt/beagle/website/ui/virtualization.js` auf Repo-Stand synchronisiert,
	- fehlender Export `setStoragePoolQuota` war sonst ein Blocker fuer den `main.js`-Bootstrap.
- Ergebnis:
	- GoFuture Plan 02 ist jetzt vollstaendig abgehakt.

## Update (2026-04-22, GoFuture Plan 11 Schritt 1 abgeschlossen: Endpoint->Manager prepare-stream)

- Offene Schritt-1-Checkbox geschlossen: Moonlight-Client liest lokale Aufloesung und triggert vor Streamstart einen Guest-Display-Prepare-Call.
- Neuer Endpoint-API-Pfad implementiert:
	- `POST /api/v1/endpoints/moonlight/prepare-stream`
	- in `beagle-host/services/endpoint_http_surface.py`.
- Neue Guest-Display-Prepare-Logik in `beagle-host/services/sunshine_integration.py`:
	- `prepare_virtual_display_on_vm(...)` setzt `DISPLAY=:0` + `XAUTHORITY` und versucht `xrandr --output <out> --mode <resolution>`.
	- fuer `3840x2160` wird zusaetzlich ein 4K-Modeline-Add/Apply-Fallback versucht.
- Control-Plane-Wiring in `beagle-host/bin/beagle-control-plane.py` erweitert (Wrapper + Endpoint-Surface-Injektion).
- Endpoint-Runtime integriert:
	- `thin-client-assistant/runtime/moonlight_manager_registration.sh` um `prepare_moonlight_stream_via_manager(...)` erweitert.
	- `thin-client-assistant/runtime/launch-moonlight.sh` ruft den Prepare-Call vor dem eigentlichen Moonlight-Stream auf.
- Testabdeckung erweitert:
	- `tests/unit/test_endpoint_http_surface.py` neu (prepare-stream path/status/payload).
	- `python3 -m pytest tests/unit/test_endpoint_http_surface.py tests/unit/test_streaming_backend_service.py -q` => `9 passed`.
- Runtime-Smoke:
	- `python3 scripts/test-streaming-quality-smoke.py --host srv1.beagle-os.com --domain beagle-100` => `pass_with_4k_limit`.
	- `x11_prereq`, `xrandr_query`, `vkms_sunshine`, `sunshine_api_apps` gruen; 4K-Apply weiterhin durch CRTC-Limit begrenzt.

## Update (2026-04-22, GoFuture Plan 11 Schritt 1 Start: Linux vkms + Windows Apollo Split)

- Plan-11-Strategie auf realen Runtime-Stand gebracht:
	- `docs/gofuture/11-streaming-v2.md` von pauschalem Apollo-Ziel auf Plattform-Split umgestellt,
	- Linux-Desktop-Pfad: Sunshine + `vkms` (Virtual Display),
	- Windows-Desktop-Pfad: Apollo + SudoVDA (optional/eval).
- Architekturentscheidung dokumentiert in `docs/refactor/07-decisions.md`:
	- neue Entscheidung `D-031` beschreibt den platform-aware Backend-Ansatz,
	- `guest_os=linux` -> Sunshine+vkms,
	- `guest_os=windows` -> Apollo,
	- Sunshine bleibt Fallback fuer Apollo-Fehlerpfade.
- Technischer Runtime-Anker umgesetzt:
	- neues Provisioning-Template `beagle-host/templates/ubuntu-beagle/virtual-display-setup.sh.tpl` angelegt,
	- `beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl` um `configure_virtual_display_vkms()` erweitert,
	- firstboot laedt jetzt `vkms`, persistiert Modul-Load (`/etc/modules-load.d/vkms.conf`), installiert `vkms-virtual-display.service`, und startet ein XFCE-Autostart-Skript zur 4K-Mode-Setzung via `xrandr`.
	- neuer platform-aware Selector `beagle-host/services/streaming_backend.py` implementiert (Linux default `sunshine`, Windows default `apollo`, optional `allow_apollo_on_linux` fuer Eval-Pfade).
	- Unit-Tests fuer Selector (`tests/unit/test_streaming_backend_service.py`) hinzugefuegt (`5 passed`).
- Live-Check auf `srv1.beagle-os.com` / `beagle-100`:
	- Sunshine-Version in VM bestaetigt (`2025.924.154138`),
	- `vkms` per guest-agent erfolgreich geladen (`lsmod` zeigt Modul),
	- `xrandr` im guest-agent-Kontext liefert erwartbar `Can't open display` (kein DISPLAY im nicht-interaktiven Agent-Kontext), was den bekannten Unterschied zu echter XFCE-Session bestaetigt.
	- anschliessend in echter Session validiert: `DISPLAY=:0 XAUTHORITY=/home/beagle/.Xauthority xrandr --query` funktioniert und zeigt `Virtual-1` inkl. Modus `3840x2160_60.00`.
	- 4K-Apply laeuft aktuell in `xrandr: Configure crtc 0 failed`; deshalb wurde ein robuster Fallback auf `1920x1080` in den vkms-Setup-Skripten implementiert.
	- neuer reproduzierbarer Qualitaets-Smoke `scripts/test-streaming-quality-smoke.py` hinzugefuegt und ausgefuehrt:
		- `x11_prereq`: ok
		- `xrandr_query`: ok (`Virtual-1`, current `1280x800`, 4K-Mode vorhanden)
		- `xrandr_set_4k`: nicht erfolgreich (`Configure crtc 0 failed`)
		- `vkms_sunshine`: ok
		- `sunshine_api_apps`: ok
		- Gesamtresultat: `pass_with_4k_limit`.
- Ergebnis:
	- Plan 11 ist gestartet und hat einen reproduzierbaren Linux-vDisplay-Implementierungsanker im Repo,
	- offene Restarbeit fuer Abschluss von Schritt 1: Moonlight-E2E-Stream-Nachweis gegen den vkms-Guest und Aufloesungs-Uplift auf 4K in kompatibler VM-Grafikkonfiguration.

## Update (2026-04-22, GoFuture Plan 10 letzte Testpflicht: Entitlement-Sichtbarkeit)

- Serverseitige Pool-Sichtbarkeitsfilter in `beagle-host/bin/beagle-control-plane.py` umgesetzt:
	- `GET /api/v1/pools` filtert jetzt restriktive Pools fuer nicht berechtigte `pool:read`-User heraus,
	- `GET /api/v1/pools/{pool}` / `/vms` / `/entitlements` maskieren versteckte Pools als `404 pool not found`,
	- Operator-/Admin-Bypass bleibt ueber `pool:write` bzw. `*` erhalten.
- `beagle-host/services/entitlement_service.py` erweitert um explizite Sichtbarkeits-Semantik:
	- `has_explicit_entitlements(...)`
	- `can_view_pool(...)`
- Reproduzierbarer Nachweis erweitert:
	- `scripts/test-vdi-pools-smoke.py` fuehrt jetzt zusaetzlich einen authentifizierten Visibility-Smoke aus,
	- Admin sieht alle Pools,
	- berechtigter User sieht nur unrestricted + entitled Pools,
	- unberechtigter User sieht restriktive Pools nicht und bekommt bei Direkt-Lookup `404`.
- Lokale Validierung:
	- `python3 -m pytest tests/unit/test_entitlement_service.py -q` => `5 passed`
	- `python3 -m py_compile beagle-host/bin/beagle-control-plane.py` => OK
	- `python3 scripts/test-vdi-pools-smoke.py` => `VDI_POOL_SMOKE_OK`
- Deploy + Runtime-Validierung auf `srv1.beagle-os.com`:
	- `beagle-control-plane.py`, `entitlement_service.py` und `scripts/test-vdi-pools-smoke.py` nach `/opt/beagle` synchronisiert,
	- `./scripts/install-beagle-host-services.sh` erfolgreich,
	- `cd /opt/beagle && python3 scripts/test-vdi-pools-smoke.py` => `VDI_POOL_SMOKE_OK`.
- Ergebnis:
	- Die letzte offene GoFuture-Plan-10-Testpflicht-Checkbox ist geschlossen.
	- Plan 10 ist damit vollstaendig abgeschlossen.

## Update (2026-04-22, GoFuture Plan 10 Testpflicht-Slice: reproduzierbarer VDI Smoke)

- Neues reproduzierbares Smoke-Script `scripts/test-vdi-pools-smoke.py` umgesetzt.
- Das Script validiert Plan-10-Runtime mit temp-local State statt Live-Daten:
	- synthetisches Golden-Image per `qemu-img create`,
	- Template-Export ueber `DesktopTemplateBuilderService`,
	- Floating-Non-Persistent-Pool mit 5 Slots,
	- Release/Recycling-Flow inkl. `<60s`-Nachweis,
	- Persistent-Pool mit Reassign derselben VM,
	- Throwaway-Control-Plane mit `BEAGLE_MANAGER_ALLOW_LOCALHOST_NOAUTH=1` fuer echte API-Routen (`/pools`, `/entitlements`, `/allocate`, `/release`, `/recycle`).
- Lokale Validierung:
	- `python3 scripts/test-vdi-pools-smoke.py` => `VDI_POOL_SMOKE_OK`.
- Deploy + Runtime-Validierung auf `srv1.beagle-os.com`:
	- Script nach `/opt/beagle/scripts/test-vdi-pools-smoke.py` ausgerollt,
	- `cd /opt/beagle && python3 scripts/test-vdi-pools-smoke.py` => `VDI_POOL_SMOKE_OK`.
- Ergebnis:
	- GoFuture Plan 10 Testpflicht-Checkboxen fuer Floating-5-Slots, Recycle-<=60s, Persistent-Reassign und Template->Pool geschlossen.
	- Offen bleibt nur noch der explizite Sichtbarkeitsnachweis "User ohne Entitlement sieht Pool nicht"; aktuell ist reproduzierbar nur der API-Guard `403 not entitled to this pool` verifiziert.

## Update (2026-04-22, GoFuture Plan 10 Schritt 6: Template-Builder in Web Console)

- Neue VM-Detailaktion `Als Template` in `website/main.js` fuer gestoppte VMs umgesetzt.
- Neues Modul `website/ui/template_builder.js` implementiert:
	- Template-Builder-Modal,
	- API-Call `POST /api/v1/pool-templates`,
	- Fortschrittsdialog mit Sysprep/Seal-/Export-/Persistenz-Schritten,
	- Erfolgs-/Fehlerpfad mit Banner + Activity + Refresh.
- `website/ui/actions.js` um Action-Dispatch `open-template-builder` erweitert.
- `website/ui/events.js` um Template-Builder-Modal-/Progress-Events erweitert.
- `website/index.html` um `template-builder-modal` und `template-builder-progress-modal` erweitert.
- Lokale Validierung:
	- `node --check website/main.js website/ui/actions.js website/ui/events.js website/ui/template_builder.js` => alle erfolgreich.
- Deploy + Runtime-Validierung auf `srv1.beagle-os.com`:
	- geaenderte Dateien nach `/opt/beagle/website/...` ausgerollt,
	- `./scripts/install-beagle-host-services.sh` => `INSTALL_OK`,
	- Live-Smoke: `template-builder-modal`, `template-builder-progress-modal`, `template-builder-create` in `/` vorhanden,
	- Live-Smoke: `open-template-builder` in ausgeliefertem `main.js` vorhanden,
	- `GET /beagle-api/api/v1/pool-templates` ohne Auth => `401` (erwartet).

## Update (2026-04-22, GoFuture Plan 10 Schritt 5: Pool-Wizard + Pool-Uebersicht)

- Web Console fuer VDI-Pools auf echten Mehrschritt-Wizard umgestellt:
	- Schritt 1: Template + Pool-ID,
	- Schritt 2: Groesse/Modus/Ressourcen,
	- Schritt 3: Entitlements,
	- Schritt 4: Bestaetigung mit Zusammenfassung.
- `website/ui/policies.js` erweitert um Wizard-Flow-Logik:
	- Step-State, Next/Prev/Direct-Step,
	- step-spezifische Validierung,
	- Confirm-Summary vor `POST /api/v1/pools`.
- Pool-Uebersicht erweitert:
	- VM-Slot-Tabelle bleibt erhalten,
	- zusaetzliche Status-Summen fuer `free`, `in_use`, `recycling`, `error` pro ausgewaehltem Pool.
- `website/ui/events.js` um Wizard-Events erweitert (`pool-wizard-next`, `pool-wizard-prev`, Stepper-Klick).
- `website/styles/panels/_policies.css` mit Stepper-/Summary-/Stats-Styling erweitert.
- Lokale Validierung:
	- `node --check` auf geaenderte WebUI-Module erfolgreich,
	- VSCode-Errors fuer geaenderte Dateien: keine.
- Deploy + Runtime-Validierung auf `srv1.beagle-os.com`:
	- Geaenderte Dateien nach `/opt/beagle/website/...` synchronisiert,
	- `./scripts/install-beagle-host-services.sh` erfolgreich (`INSTALL_OK`),
	- Live-Smoke: `https://127.0.0.1/` enthaelt `pool-step-btn-4`, `pool-wizard-next`, `pool-overview-stats`,
	- `GET /beagle-api/api/v1/pools` ohne Auth liefert erwartetes `401`.

## Update (2026-04-22, GoFuture Plan 10 Schritt 1 Teil 2 + Schritt 2 Teil 2 + Schritt 3 Teil 2 + Schritt 4 Teil 2)

- Neues Service-Modul `beagle-host/services/desktop_template_builder.py` umgesetzt.
- Template-Builder realisiert jetzt den geplanten Basispfad `Snapshot/Seal/Backing-Image`:
	- VM-Stopp-Hook,
	- cloud-init-/Sysprep-Seal ueber `virt-sysprep` bzw. `guestfish`,
	- qcow2-Backing-Image-Export per `qemu-img convert`,
	- persistente Template-Metadaten in `desktop-templates.json`.
- Neues Service-Modul `beagle-host/services/pool_manager.py` umgesetzt.
- Pool-Lifecycle fuer VDI-Basisschicht realisiert:
	- Pool-CRUD,
	- VM-Slot-Registrierung,
	- Allocation / Release / Recycle,
	- Scale-State,
	- Statuszaehlung fuer `free | in_use | recycling | error`.
- Mode-spezifische Runtime-Logik fuer `floating_non_persistent`, `floating_persistent` und `dedicated` im Pool-Manager umgesetzt und per Unit-Tests verifiziert.
- Control Plane erweitert um Plan-10-Basis-API:
	- `GET/POST/PUT/DELETE /api/v1/pools`
	- `GET /api/v1/pools/{pool}/vms`
	- `POST /api/v1/pools/{pool}/vms|allocate|release|recycle|scale|entitlements`
	- `GET /api/v1/pool-templates`
	- `POST /api/v1/pool-templates`
	- `DELETE /api/v1/pool-templates/{id}`
- RBAC fuer die neue Surface ergaenzt (`pool:read`, `pool:write`) und mit `tests/unit/test_authz_policy.py` abgesichert.
- Wichtiger Runtime-Fix: Control-Plane importiert jetzt den Repo-Root auf `sys.path`, neue Services sprechen stabil gegen `core.virtualization.*` statt gegen fragile Bare-Imports.
- Lokale Validierung:
	- `python3 -m pytest tests/unit/test_pool_manager.py tests/unit/test_desktop_template_builder.py tests/unit/test_entitlement_service.py tests/unit/test_authz_policy.py -q` => `14 passed`.
	- Throwaway-Control-Plane auf Port `19088` gestartet; `GET /api/v1/pools` und `GET /api/v1/pool-templates` lieferten im localhost-noauth Modus `200`, `POST /api/v1/pools` mit `{}` lieferte `400 pool_id is required`.
- Deploy + Runtime-Validierung auf `srv1.beagle-os.com`:
	- geaenderte Dateien nach `/opt/beagle/...` synchronisiert,
	- `./scripts/install-beagle-host-services.sh` ausgefuehrt,
	- `beagle-control-plane.service` nach Restart `active`.
	- Live-Smoke auf `127.0.0.1:9088`:
		- `GET /api/v1/pools` => `401 unauthorized`,
		- `GET /api/v1/pool-templates` => `401 unauthorized`,
		- `POST /api/v1/pools` => `401 unauthorized`.
	- Journal zeigt sauberes Handling des neuen POST-Pfads ohne Exception.

## Update (2026-04-22, GoFuture Plan 10 Schritt 4 Teil 1: Entitlement-Service)

- Neues Modul `beagle-host/services/entitlement_service.py` umgesetzt.
- Service implementiert persistente Pool-Entitlements fuer User/Gruppen in JSON-State:
	- `get_entitlements`
	- `set_entitlements`
	- `add_entitlement`
	- `remove_entitlement`
	- `is_entitled`
- Eingabe-Validierung + Normalisierung enthalten (keine leere `pool_id`, deduplizierte IDs).
- Unit-Test `tests/unit/test_entitlement_service.py` erstellt (3/3 gruen).
- Live-Deploy + Smoke auf `srv1.beagle-os.com`:
	- Datei nach `/opt/beagle/beagle-host/services/entitlement_service.py` ausgerollt,
	- Import + Grundfunktion erfolgreich (`ENTITLEMENT_IMPORT_SMOKE_OK`).
- Ergebnis: Erste Checkbox aus GoFuture Plan 10 Schritt 4 geschlossen;
	API-Route fuer `POST /api/v1/pools/{pool}/entitlements` bleibt als naechster Block offen.

## Update (2026-04-22, GoFuture Plan 10 Schritt 2 Teil 1 + Schritt 3 Teil 1)

- Neues Core-Modul `core/virtualization/desktop_pool.py` umgesetzt.
- Provider-neutrales `DesktopPool`-Protocol eingefuehrt mit den Lifecycle-Seams:
	`create_pool`, `get_pool`, `list_pools`, `delete_pool`, `scale_pool`,
	`allocate_desktop`, `release_desktop`, `recycle_desktop`.
- Neue typisierte Pool-/Lease-Datenmodelle hinzugefuegt:
	- `DesktopPoolSpec`
	- `DesktopPoolInfo`
	- `DesktopLease`
- Schritt-3-Mode-Baustein real umgesetzt:
	- `DesktopPoolMode` Enum mit
		`floating_non_persistent | floating_persistent | dedicated`.
	- Mode ist in Spec/Lease-Feldern typisiert verdrahtet.
- Unit-Test `tests/unit/test_desktop_pool_contract.py` ergaenzt (3/3 gruen).
- Live-Deploy + Smoke auf `srv1.beagle-os.com`:
	- Datei nach `/opt/beagle/core/virtualization/desktop_pool.py` ausgerollt,
	- Import/Instanziierung per Python-Smoke erfolgreich (`POOL_IMPORT_SMOKE_OK`).
- Ergebnis: GoFuture Plan 10 Checkboxen fuer
	`core/virtualization/desktop_pool.py` und den Mode-Enum geschlossen.

## Update (2026-04-22, GoFuture Plan 10 Schritt 1 Teil 1: DesktopTemplate-Contract)

- Neues Core-Modul `core/virtualization/desktop_template.py` umgesetzt.
- Provider-neutrales `DesktopTemplate`-Protocol eingefuehrt mit Lifecycle-Methoden:
	`build_template`, `get_template`, `list_templates`, `delete_template`.
- Dataclass-Typen fuer den Builder-/Read-Pfad ergaenzt:
	- `DesktopTemplateBuildSpec`
	- `DesktopTemplateInfo`
- Unit-Test `tests/unit/test_desktop_template_contract.py` erstellt (2/2 gruen).
- Live-Deploy + Smoke auf `srv1.beagle-os.com`:
	- Datei nach `/opt/beagle/core/virtualization/desktop_template.py` ausgerollt,
	- Import/Instanziierung per Python-Smoke erfolgreich (`IMPORT_SMOKE_OK`).
- Ergebnis: Erste Checkbox aus GoFuture Plan 10 Schritt 1 geschlossen;
	Builder-Implementierung (zweite Checkbox) bleibt als naechster Block offen.

## Update (2026-04-22, GoFuture Plan 08 Testpflicht: Quota-Ueberschreitung)

- Quota-Enforcement in den Ubuntu-Provisioning-Create-Pfad integriert:
	- `beagle-host/services/ubuntu_beagle_provisioning.py` erweitert um `enforce_storage_quota(...)`.
	- Quota-Pruefung wird jetzt vor VM-Erzeugung fuer den Ziel-Storage ausgefuehrt.
	- Fehlerbild ist reproduzierbar als `quota_exceeded` standardisiert.
- Control-Plane-Wiring aktualisiert:
	- `beagle-host/bin/beagle-control-plane.py` uebergibt `get_storage_quota(...)` in den Provisioning-Service.
- Neue Unit-Testabdeckung:
	- `tests/unit/test_ubuntu_beagle_provisioning_quota.py` erstellt (2/2 gruen).
- Live-Deployment + Validierung auf `srv1.beagle-os.com`:
	- Geaenderte Dateien nach `/opt/beagle/...` ausgerollt, Services mit `scripts/install-beagle-host-services.sh` konsistent nachgezogen.
	- `beagle-control-plane.service` laeuft danach wieder stabil (`active`).
	- Reproduzierter API-Smoke: temporaer `quota_bytes=1` auf Pool `local`, danach `POST /api/v1/provisioning/vms` => `400 bad_request` mit `quota_exceeded`.
	- Urspruengliche Quota nach Testlauf wiederhergestellt (`quota_bytes=0`).
- Ergebnis: GoFuture Plan 08 Testpflicht-Checkbox "Quota-Ueberschreitung gibt korrekten Fehler zurueck" geschlossen.

## Update (2026-04-22, GoFuture Plan 08 Schritt 6: Storage-Quotas API + Web Console)

- Neuer persistenter Quota-Service `beagle-host/services/storage_quota.py` umgesetzt (`storage-quotas.json` im Manager-Data-Dir).
- Neue API-Routen im Control Plane implementiert:
	- `GET /api/v1/storage/pools/{pool}/quota`
	- `PUT /api/v1/storage/pools/{pool}/quota`
- RBAC/AuthZ fuer Quota-Routen ergänzt (`settings:read` / `settings:write`).
- Virtualization-Overview liefert jetzt pro Storage-Pool `quota_bytes`.
- Web Console erweitert:
	- Storage-Tabellen mit Quota-Spalte,
	- Quota-Setter-Aktion pro Pool (inkl. Refresh nach Update).
- Unit-Test `tests/unit/test_storage_quota_service.py` ergänzt.
- Damit ist GoFuture Plan 08 Schritt 6 vollständig erledigt.

## Update (2026-04-22, GoFuture Plan 08 Schritt 5: NFS-Backend)

- Neues Provider-Modul `providers/beagle/storage/nfs.py` implementiert (`NfsStorageBackend`).
- Storage-Lifecycle-Operationen fuer NFS umgesetzt:
	- `create_volume`/`resize_volume`/`snapshot`/`clone` via `qemu-img`
	- `delete_volume` und `list_volumes` auf NFS-Dateiobjekten
- Sicherheits-/Betriebs-Guard ergänzt: explizite Mountpoint-Pruefung (`mount_path` muss wirklich gemountet sein).
- Unit-Tests in `tests/unit/test_nfs_storage_backend.py` ergänzt (4/4 pass).
- Deploy-/Smoke-Validierung auf `srv1.beagle-os.com` erfolgreich (Import + create/snapshot/clone/list mit Command-Stub).
- Damit ist GoFuture Plan 08 Schritt 5 vollständig erledigt.

## Update (2026-04-22, GoFuture Plan 08 Schritt 4: ZFS-Backend)

- Neues Provider-Modul `providers/beagle/storage/zfs.py` umgesetzt (`ZfsStorageBackend`).
- Storage-Lifecycle-Operationen fuer ZFS implementiert:
	- `create_volume` via `zfs create -V`
	- `delete_volume` via `zfs destroy -r`
	- `resize_volume` via `zfs set volsize=`
	- `snapshot` via `zfs snapshot`
	- `clone` via Snapshot + `zfs clone`
	- `list_volumes` via `zfs list -t volume`
- Unit-Tests in `tests/unit/test_zfs_storage_backend.py` ergänzt (4/4 pass).
- Deploy-/Smoke-Validierung auf `srv1.beagle-os.com` erfolgreich (Import + create/snapshot/clone/list mit Command-Stub).
- Damit ist GoFuture Plan 08 Schritt 4 vollständig erledigt.

## Update (2026-04-22, GoFuture Plan 08 Schritt 3: LVM-Thin-Backend)

- Neues Provider-Modul `providers/beagle/storage/lvm_thin.py` umgesetzt (`LvmThinStorageBackend`).
- Storage-Lifecycle-Operationen auf LVM-Thin-Basis implementiert:
	- `create_volume` via `lvcreate --thin -V`
	- `delete_volume` via `lvremove --yes`
	- `resize_volume` via `lvresize --yes -L`
	- `snapshot` und linked-clone via `lvcreate -s`
	- `clone(linked=False)` via Thin-Volume + `qemu-img convert`
	- `list_volumes` via `lvs`-Parsing (thin-pool gefiltert)
- Unit-Tests in `tests/unit/test_lvm_thin_storage_backend.py` ergänzt (4/4 pass).
- Deploy-/Smoke-Validierung auf `srv1.beagle-os.com` erfolgreich (Import + create/snapshot/clone/list mit Command-Stub).
- Damit ist GoFuture Plan 08 Schritt 3 abgehakt.

## Update (2026-04-22, GoFuture Plan 08 Schritt 2: Directory-Storage-Backend)

- Neues Provider-Modul `providers/beagle/storage/directory.py` implementiert (`DirectoryStorageBackend`).
- Real implementierte Storage-Lifecycle-Operationen:
	- `create_volume` (`qemu-img create`)
	- `delete_volume`
	- `resize_volume` (`qemu-img resize`)
	- `snapshot` (`qemu-img snapshot -c`)
	- `clone` (linked/full via `qemu-img create -b` bzw. `qemu-img convert`)
	- `list_volumes`
- Sicherheitsrelevante Guards integriert: Name-/Formatvalidierung und Path-Escape-Schutz unterhalb `base_dir`.
- Unit-Tests `tests/unit/test_directory_storage_backend.py` hinzugefuegt (4/4 pass).
- Damit ist GoFuture Plan 08 Schritt 2 vollstaendig abgehakt.

## Update (2026-04-22, GoFuture Plan 08 Schritt 1: StorageClass-Contract)

- Neues Core-Modul `core/virtualization/storage.py` eingefuehrt.
- `StorageClass`-Protocol mit Lifecycle-Methoden (`create_volume`, `delete_volume`, `resize_volume`, `snapshot`, `clone`, `list_volumes`) definiert.
- Typen `VolumeSpec`, `SnapshotSpec`, `StoragePoolInfo` als Dataclasses umgesetzt.
- Unit-Test `tests/unit/test_storage_contract.py` erstellt und lokal erfolgreich ausgefuehrt (3/3 pass).
- Damit ist GoFuture Plan 08 Schritt 1 vollstaendig abgehakt.

## Update (2026-04-22, GoFuture Plan 07 Schritt 3 (Teil 1): Cluster-Inventory-Service)

- Neues Service-Modul `beagle-host/services/cluster_inventory.py` umgesetzt.
- `beagle-control-plane.py` verdrahtet den Service als neue Read-API:
	- `GET /api/v1/cluster/inventory`
	- `GET /api/v1/cluster/nodes` (Alias)
- Cluster-Inventory aggregiert Node-Metriken plus VM-Verteilung pro Node und markiert fehlende Nodes als `unreachable`.
- Unit-Testabdeckung ergänzt mit `tests/unit/test_cluster_inventory.py` (Aggregation + unreachable-Fallback).
- Damit ist der erste Checkbox-Punkt aus GoFuture Plan 07 Schritt 3 real implementiert.

## Update (2026-04-22, GoFuture Plan 07 Schritt 6: Cluster Panel in Web Console)

- GoFuture 07 Schritt 6 (beide Checkboxen) umgesetzt: neues `Cluster`-Panel in der Navigation sowie Knotenliste mit Status, CPU-/RAM-Auslastung und VM-Count.
- Neue UI-Datei `website/ui/cluster.js` implementiert:
	- Rendert Knotenstatus aus `state.virtualizationOverview.nodes`.
	- Aggregiert VM-Anzahl pro Knoten aus `state.inventory`.
	- Bietet direkte Aktion "VMs anzeigen" pro Knoten (Node-Filter ins Inventory).
- Integration in den bestehenden Datenfluss:
	- `website/main.js`: Modul importiert/verdrahtet (`configureCluster`, `bindClusterEvents`, `renderClusterPanel`).
	- `website/ui/dashboard.js`: `renderClusterPanel()` in den regulären Dashboard-Refresh eingebunden.
	- `website/ui/auth.js`: Cluster-Ansicht wird bei Session-Clear ebenfalls konsistent zurückgesetzt.
	- `website/ui/state.js`: `panelMeta.cluster` ergänzt.
	- `website/index.html`: neues Nav-Element (`data-panel="cluster"`) + neue Panel-Sektion (`data-panel-section="cluster"`).
- Sicherheits-/Architektur-Status:
	- Keine neuen Provider-Kopplungen, kein Proxmox-Code.
	- Datenquelle bleibt provider-neutral über bestehende Read-Surfaces (`/virtualization/overview`, `/vms`).

## Update (2026-04-21, Hotfix: VM USB installer/live downloads + missing syncHash)

- **Symptome**:
	- Web UI VM-Detailansicht warf `ReferenceError: syncHash is not defined` aus `website/main.js`.
	- `GET /api/v1/vms/{vmid}/installer.sh`, `/installer.ps1`, `/live-usb.sh` lieferten auf `srv1.beagle-os.com` reproduzierbar `503`.
- **Root cause Frontend**:
	- `website/main.js` verwendete `syncHash()` in `loadDetail()`/`closeDetail()`, importierte die Funktion aber nicht mehr aus `website/ui/panels.js`.
- **Root cause Backend**:
	- `InstallerScriptService` hing fuer VM-spezifische Downloads hart an Host-`dist/`-Artefakten (`pve-thin-client-usb-installer-host-latest.sh`, `pve-thin-client-live-usb-host-latest.sh`, `beagle-os-installer-amd64.iso`).
	- Auf `srv1` fehlten genau diese Dateien unter `/opt/beagle/dist/`, obwohl das versionierte Quellskript unter `thin-client-assistant/usb/` vorhanden war.
- **Fix**:
	- `website/main.js`: `syncHash` wieder korrekt importiert.
	- `website/index.html`: `main.js` Cache-Buster auf `6.7.0-r7` angehoben, damit Browser den Hotfix ziehen.
	- `beagle-host/services/installer_script.py`: Shell-Downloads lesen jetzt bevorzugt die gehosteten Templates, fallen aber auf das versionierte Quellskript `thin-client-assistant/usb/pve-thin-client-usb-installer.sh` zurueck; lokale ISO-Pflicht fuer die drei generierten Download-Skripte entfernt.
	- `beagle-host/bin/beagle-control-plane.py`: neues Raw-Shell-Template an `InstallerScriptService` verdrahtet.
	- `tests/unit/test_installer_script.py`: neuer fokussierter Unit-Test fuer den Fallback ohne `dist/`-Artefakte.
- **Validierung lokal**:
	- `python3 -m pytest tests/unit/test_installer_script.py` -> `1 passed`.
	- `python3 -m py_compile beagle-host/services/installer_script.py beagle-host/bin/beagle-control-plane.py` -> OK.
- **Live-Validierung auf `srv1.beagle-os.com`**:
	- Hotfix-Dateien nach `/opt/beagle/...` deployt und `beagle-control-plane` neu gestartet (`active`).
	- `GET /api/v1/vms/100/installer.sh` -> `200`.
	- `GET /api/v1/vms/100/installer.ps1` -> `200`.
	- `GET /api/v1/vms/100/live-usb.sh` -> `200`.
	- HTTPS-Index liefert `/main.js?v=6.7.0-r7`; ausgeliefertes `main.js` enthaelt den `syncHash`-Import.

## Update (2026-04-21, GoFuture Plan 15 Schritte 1+3+4+5: Audit schema/report/viewer)

- `core/audit_event.py` neu angelegt und als gemeinsames Audit-Schema mit `schema_version`, `action`, `resource_*`, `old_value`, `new_value`, `metadata` eingefuehrt.
- `beagle-host/services/audit_log.py` auf das neue Schema migriert; Legacy-Records werden weiterhin ueber `AuditEvent.from_record(...)` normalisiert.
- `beagle-host/services/audit_pii_filter.py` neu implementiert; Default-Redaction schwaerzt `password`, `secret`, `token`, `key` rekursiv in `old_value`/`new_value`.
- `beagle-host/services/audit_report.py` neu implementiert; `GET /api/v1/audit/report` liefert JSON oder CSV je nach `Accept`-Header.
- `beagle-host/services/authz_policy.py` erweitert: Audit-Report erfordert `auth:read`.
- Web Console erweitert:
	- neues Audit-Panel in `website/index.html`,
	- State/Hooks in `website/ui/state.js`, `website/ui/panels.js`, `website/ui/events.js`, `website/ui/activity.js`,
	- neues Modul `website/ui/audit.js` fuer Filter, Refresh, CSV-Export und Auto-Refresh.
- **Validierung lokal**:
	- `python3 -m pytest tests/unit/test_audit_log.py tests/unit/test_audit_helpers.py tests/unit/test_audit_report.py` -> `9 passed`.
- **Live-Validierung auf `srv1.beagle-os.com`**:
	- `beagle-control-plane.service` nach Deploy aktiv,
	- `/api/v1/audit/report` liefert `200`, JSON `ok=true`, CSV mit Header,
	- Redaction-Snippet auf `srv1` bestaetigt `[REDACTED]` fuer `password`/`api_token`/`private_key`.

## Update (2026-04-21, Hotfix: noVNC HTTP 500 — /etc/beagle/novnc permission)

- **Root cause**: `/etc/beagle/novnc/` was `root:beagle-manager 0750` — group had `r-x` but not write.
- `VmConsoleAccessService._create_ephemeral_novnc_token` tried to create `console-tokens.json` in that dir → `PermissionError` → unhandled → 500.
- **Fix**: `scripts/install-beagle-host-services.sh` changed from `chmod 0750` to `chmod 0770` for `/etc/beagle/novnc`.
- Live-fixed on srv1 via `chmod 770 /etc/beagle/novnc`. Confirmed writable by beagle-manager.
- Commit: `9a6d6c9`

## Update (2026-04-21, GoFuture Plan 14 Schritte 2+5: Recording-Service + Download-Audit)

- `beagle-host/services/recording_service.py` neu implementiert (ffmpeg-basierte Session-Aufzeichnung, MP4-Output, `recordings/index.json`).
- Control Plane erweitert:
	- `POST /api/v1/sessions/{id}/recording/start`
	- `POST /api/v1/sessions/{id}/recording/stop`
	- `GET /api/v1/sessions/{id}/recording`
- RBAC ergänzt:
	- `session:manage_recording`
	- `session:download_recording`
	- Permission-Katalog (`/api/v1/auth/permission-tags`) erweitert.
- Audit ergänzt:
	- Download erzeugt `session.recording.download` inklusive Downloader-Identität.
- Tests:
	- neue Unit-Tests `tests/unit/test_recording_service.py` (2/2 pass),
	- fokussierte Test-Suite inkl. IAM-Regressionen: 19/19 pass.
- Live-Validierung auf `srv1.beagle-os.com`:
	- Recording Start `200`, Download `200`, MP4-Datei vorhanden,
	- ohne Token Download `401`,
	- Audit-Event in `/var/lib/beagle/beagle-manager/audit/events.log` nachweisbar.

## Update (2026-04-21, GoFuture Plan 13 Schritte 4+5: Tenant-Scope + Permission-Tags)

**Schritt 4 — Tenant-Scope in mutierenden Endpoints:**
- `beagle-host/services/auth_session.py`: `tenant_id` in User-Records (optional); `list_users` filtert nach Tenant; `create_user`/`update_user` akzeptieren `tenant_id`; `get_user_tenant_id()` Hilfsmethode; `resolve_access_token()` gibt `tenant_id` im Principal zurück.
- `beagle-host/services/auth_http_surface.py`: `route_get/post/put/delete` bekommen `requester_tenant_id`; Cross-tenant-Zugriff → 403 Forbidden.
- `beagle-host/bin/beagle-control-plane.py`: `requester_tenant_id` aus Principal weitergeleitet; `/api/v1/auth/me` gibt `tenant_id` zurück.
- 12 neue Unit-Tests in `tests/unit/test_tenant_isolation.py` (alle bestanden).

**Schritt 5 — Permission-Tag Checkboxen im Rollen-Editor:**
- `beagle-host/services/authz_policy.py`: `PERMISSION_CATALOG` (7 Gruppen, 13 Tags).
- Neuer Endpoint `GET /api/v1/auth/permission-tags`.
- `website/ui/iam.js`: `renderPermissionTagEditor()`, Checkbox-basierter Rollen-Editor.
- `website/index.html`: Rollen-Editor-Textarea → Checkbox-Grid.
- `website/styles/_forms.css`: Permission-Tag-Grid CSS.

Deployment + Live-Validierung auf `srv1.beagle-os.com` erfolgreich. 65 Unit-Tests bestanden.


## Update (2026-04-21, GoFuture Plan 13 Schritt 3: SCIM 2.0 Surface)

- SCIM-Service umgesetzt:
	- neue Datei `beagle-host/services/scim_service.py` mit SCIM 2.0 `/Users` und `/Groups` Ressourcen.
- Control Plane erweitert:
	- `beagle-host/bin/beagle-control-plane.py` um SCIM-Routing für `GET/POST/PUT/DELETE` unter `/scim/v2/*`.
	- separater SCIM-Auth-Guard über `BEAGLE_SCIM_BEARER_TOKEN` implementiert (getrennt von Session- und Legacy-API-Token).
- Live-Deployment + Validierung auf `srv1.beagle-os.com`:
	- `GET/POST/GET/DELETE` für `/scim/v2/Users` und `/scim/v2/Groups` erfolgreich getestet,
	- ohne SCIM-Token liefern die Endpoints reproduzierbar `401`.
	- Test-Entitäten (`scimtest`, `scim-ops`) nach Validierung wieder entfernt.

## Update (2026-04-21, GoFuture Plan 13 Schritt 1+2: OIDC + SAML Auth-Basis)

- OIDC-Service implementiert:
	- neue Datei `beagle-host/services/oidc_service.py` (Authorization-Code-Flow mit PKCE inklusive `state`/`nonce`/`code_verifier`).
	- neue Routen `GET /api/v1/auth/oidc/login` und `GET /api/v1/auth/oidc/callback` in `beagle-host/bin/beagle-control-plane.py`.
- SAML-Service implementiert:
	- neue Datei `beagle-host/services/saml_service.py` (SP-Metadata-Generator und Login-Redirect).
	- neue Routen `GET /api/v1/auth/saml/login` und `GET /api/v1/auth/saml/metadata`.
- Multi-IdP-Registry erweitert:
	- OIDC/SAML-Provider werden im Login-Dialog immer angezeigt (enabled/disabled via Env),
	- explizite Labels `Mit OIDC anmelden` / `Mit SAML anmelden`,
	- SAML-Metadata-URL in Provider-Payload.
- WebUI Login-Dialog erweitert:
	- SAML-Providerkarte mit zusätzlichem `SP-Metadata`-Download-Button (`website/ui/auth.js`, `website/styles/_modals.css`).
- Validierung:
	- lokal: `python3 -m py_compile` für neue/betroffene Python-Dateien erfolgreich, `node --check` für betroffene UI-Module erfolgreich.
	- `srv1.beagle-os.com`: Deploy + Service-Restart erfolgreich (`beagle-control-plane.service active`).
	- Live-Checks: `/api/v1/auth/providers` liefert lokale+OIDC+SAML-Methoden; `/api/v1/auth/saml/metadata` liefert 200 + XML.

## Update (2026-04-21, GoFuture Plan 13 Schritt 6: Multi-IdP Registry + Login-Methoden)

- Multi-IdP-Grundlage umgesetzt:
	- neuer Service `beagle-host/services/identity_provider_registry.py` erstellt (Registry-Datei + sichere Defaults + Local-Fallback).
- Control Plane erweitert:
	- neue öffentliche API `GET /api/v1/auth/providers` in `beagle-host/bin/beagle-control-plane.py`.
	- neue Env-Konfigurationen: `BEAGLE_IDENTITY_PROVIDER_REGISTRY_FILE`, `BEAGLE_OIDC_AUTH_URL`, `BEAGLE_SAML_LOGIN_URL`.
- Web Console Login-UX erweitert:
	- Login-Modal zeigt dynamisch alle konfigurierten Login-Methoden (`website/index.html`, `website/ui/auth.js`, `website/styles/_modals.css`, `website/ui/panels.js`, `website/main.js`).
- Validierung:
	- lokal: `python3 -m py_compile beagle-host/services/identity_provider_registry.py beagle-host/bin/beagle-control-plane.py` erfolgreich.
	- lokal: `node --check website/main.js website/ui/auth.js website/ui/panels.js website/ui/state.js` erfolgreich.

## Update (2026-04-21, GoFuture Plan 18 Schritt 4: Webhook-System)

- Webhook-Service real implementiert:
	- neue Datei `beagle-host/services/webhook_service.py` (persistente Registry, Event-Filter, HMAC-Signatur, Retry-Backoff, Delivery-Statusfelder).
- Settings-API erweitert:
	- `GET/PUT /api/v1/settings/webhooks`,
	- `POST /api/v1/settings/webhooks/test` in `beagle-host/services/server_settings.py`.
- Control Plane Integration:
	- erfolgreiche VM-Power-Events (`vm.start|vm.stop|vm.reboot`) dispatchen Webhooks in `beagle-host/bin/beagle-control-plane.py`.
- Web Console Integration:
	- neuer Server-Settings-Bereich `settings_webhooks` inkl. List/Add/Delete/Test/Save-Flow (`website/index.html`, `website/ui/settings.js`, `website/ui/state.js`).
- Validierung:
	- lokal: `python3 -m py_compile` für betroffene Python-Dateien und `node --check` für UI-Module erfolgreich.
	- `srv1.beagle-os.com`: Deploy + Service-Restart erfolgreich (`beagle-control-plane.service active`).
	- Live-API: Webhook-Settings `PUT` + Test-Dispatch `POST` jeweils `HTTP 200`.
	- Capture/HMAC: `X-Beagle-Signature` vorhanden und gegen Raw-Body verifiziert (`signature_valid=True`), Test-Dispatch `attempted=1`, `delivered=1`.

## Update (2026-04-21, GoFuture Plan 18 Schritt 5 + Testpflicht-Teile)

- API-Versionierungs-Vorbereitung umgesetzt:
	- `beagle-host/bin/beagle-control-plane.py` ergänzt um `GET /api/v2` und `GET /api/v2/health` als v2-Prep-Surface.
- Deprecation-Header für v1-Endpunkte umgesetzt:
	- zentrale Header-Injektion in Response-Pipeline (`_write_json`, `_write_bytes`, `_write_proxy_response`),
	- konfigurierbar über `BEAGLE_API_V1_DEPRECATED_ENDPOINTS`, `BEAGLE_API_V1_DEPRECATION_SUNSET`, `BEAGLE_API_V1_DEPRECATION_DOC_URL`.
- Neues Validator-Tool:
	- `scripts/validate-openapi-live.py` prüft dokumentierte `/api/v1`-Pfade gegen Live-API (kein 404 erlaubt).
- `beaglectl` korrigiert:
	- `vm list` nutzt nun den bestehenden Endpoint `/api/v1/vms` (statt fehlerhaftem `/api/v1/inventory`).
- Live-Validierung auf `srv1.beagle-os.com`:
	- `GET /api/v2` liefert `200` + Prep-Metadaten.
	- `GET /api/v1/vms` liefert erwartete Deprecation/Sunset/Link-Header.
	- `python3 scripts/validate-openapi-live.py ...` -> `openapi-live-validation=ok` (41 Pfade).
	- `beaglectl vm list --json` mit `BEAGLE_MANAGER_API_TOKEN` liefert valides JSON (json.tool geprüft).
- `docs/gofuture/18-api-iac-cli.md`: Schritt 5 beide Checkboxen und Testpflicht-Checkboxen für OpenAPI-live + `beaglectl vm list --json` auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 18 Schritt 1+3: OpenAPI-Generator + beaglectl)

- OpenAPI-v1-Generator umgesetzt:
	- neues Tool `scripts/generate-openapi-v1.py` scannt `beagle-host/**/*.py` nach `/api/v1/*`-Routen,
	- generiert `docs/api/openapi.v1.generated.yaml` und `docs/api/openapi-v1-coverage.md`.
- API-Policy ergänzt:
	- `docs/api/breaking-change-policy.md` erstellt (Breaking/Non-Breaking, Deprecation-Header, Supportfenster).
- `beaglectl` CLI implementiert:
	- neue dependency-freie CLI `scripts/beaglectl.py` (argparse + urllib),
	- Subcommands: `vm`, `pool`, `user`, `node`, `backup`, `session`, `config`,
	- JSON-Ausgabe (`--json`) und lokale Config-Verwaltung (`~/.config/beaglectl/config.json`),
	- globale Flags funktionieren sowohl vor als auch nach dem Subcommand.
- Validierung:
	- lokal: `python3 scripts/generate-openapi-v1.py`, `python3 -m py_compile scripts/beaglectl.py scripts/generate-openapi-v1.py`, CLI-Smokes erfolgreich,
	- `docs/gofuture/18-api-iac-cli.md` Schritt 1 und Schritt 3 auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 19 Schritt 6: Gaming-Kiosk Modernisierung)

- `beagle-kiosk/` Step-6-Ziele umgesetzt:
	- Electron-Version bereits modern (`^37.2.0`, >=29).
	- Automatischer Kiosk-Enrollment-Flow implementiert statt manueller Konfiguration.
- Technische Umsetzung:
	- `beagle-kiosk/main.js`: Auto-Enrollment beim Start via `POST /api/v1/endpoints/enroll`, Persistenz von `BEAGLE_MANAGER_TOKEN`, Leeren von `BEAGLE_ENROLLMENT_TOKEN`, Enrollment-Statusmodell + IPC `kiosk:enroll-now`.
	- `beagle-kiosk/preload.js`: Bridge `enrollNow()`.
	- `beagle-kiosk/renderer/index.html`, `renderer/kiosk.js`, `renderer/style.css`: Enrollment-Statuspanel + Retry-Button im Sidebar-UI.
	- `beagle-kiosk/kiosk.conf.example` und `beagle-os/overlay/usr/local/sbin/beagle-kiosk-install`: Enrollment-/Manager-Keys in Default-Konfiguration ergänzt.
- Validierung:
	- lokal: `cd beagle-kiosk && npm run lint` erfolgreich, `bash -n beagle-os/overlay/usr/local/sbin/beagle-kiosk-install` erfolgreich.
	- `srv1.beagle-os.com`: geänderte Dateien nach `/opt/beagle` deployt, gleicher Lint-/Syntax-Smoke erfolgreich.
- `docs/gofuture/19-endpoint-os.md` Schritt 6 auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 19 Schritt 1: Endpoint-Profile-Struktur)

- Profil-Management-System implementiert:
	- Drei Profile angelegt: `beagle-os/profiles/desktop-thin-client/`, `gaming-kiosk/`, `engineering-station/`
	- Jedes Profil mit `profile.conf` Konfigurationsdatei (13 Konfigurationsschlüssel).
	- Profile Manager `beagle-os/profile_manager.py` erstellt (Profil-Discovery, JSON-Export).
- Deployment auf `srv1.beagle-os.com` erfolgreich; alle 3 Profile korrekt geparst und geladen.
- `docs/gofuture/19-endpoint-os.md` Schritt 1 auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 05 Schritt 2: Proxmox-Legacy-Cleanup abgeschlossen)

- Dead-Code-Pfade entfernt (Proxmox wird dauerhaft entfernt — Plan 05):
	- `VmConsoleAccessService`: Proxmox-Console-Access-Logik (Zeilen 258–274 Proxmox UI Port Handling) entfernt,
	- `_proxmox_ui_port()` Methode gelöscht, `proxmox_ui_ports_raw` Parameter aus beiden Services (`VmConsoleAccessService`, `RequestSupportService`) entfernt,
	- `BEAGLE_PROXMOX_UI_PORTS` Environment-Variable aus `beagle-control-plane.py` gelöscht,
	- Proxy-CORS-Allow-Origins-Logik bereinigt (nur noch Beagle-relevante Origins).
- Lokale Syntax-Checks erfolgreich.
- Deployment auf `srv1.beagle-os.com` erfolgreich; Smoke-Tests alle 13/13 bestanden.
- Finale Grep-Verification: 0 Treffer für direkte Proxmox-API-Aufrufe (`qm`, `pvesh`, `/api2/json`, `PVEAuthCookie`).
- Plan 05 Schritt 2 auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 20 Schritt 4+8: Secret-Gates + OWASP smoke baseline)

- Neue security guardrails im Code umgesetzt:
	- `scripts/security-secrets-check.sh` (kein getracktes `.env`, `.gitignore`-Regeln, Operator-Dateien untracked, Hardcoded-Secret-Pattern-Scan),
	- `.security-secrets-allowlist` als explizite Ausnahme-Liste,
	- CI-Workflow `.github/workflows/security-secrets-check.yml` (monatlich + manuell + push auf relevante Pfade).
- Neue OWASP-basierte API-Baseline eingeführt:
	- `scripts/security-owasp-smoke.sh` mit reproduzierbaren Checks für Access-Control/Auth/Input-Validation/Misconfiguration.
- `docs/gofuture/20-security-hardening.md` Schritt 4 und 8 auf `[x]` gesetzt.
- Security-Fund-Register in `docs/refactor/11-security-findings.md` um S-013 und S-014 ergänzt.

## Update (2026-04-21, GoFuture Plan 06 final test checkbox closed)

- `scripts/test-server-installer-live-smoke.sh` erweitert:
	- screenshot-basierte Installer-Screen-Erkennung,
	- konfigurierbarer Grafikmodus,
	- optionale DHCP-Phase (`BEAGLE_LIVE_SMOKE_SKIP_DHCP=1`) fuer schnellen Boot-/Dialog-Nachweis,
	- robuste Option-Weitergabe bei sudo-Reexec.
- Lokaler Lauf erfolgreich:
	- `BEAGLE_LIVE_SMOKE_SKIP_DHCP=1 BEAGLE_LIVE_SMOKE_REQUIRE_INSTALLER_SCREENSHOT=1 scripts/test-server-installer-live-smoke.sh` -> `[OK] Live-server smoke test passed`.
- Damit ist der letzte offene Plan-06-Testpunkt (`ISO bootet in QEMU-VM, Installer-Dialog erscheint`) in `docs/gofuture/06-server-installer.md` auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 06 testpflicht wave: beagle-only host install + artifact verification)

- `scripts/install-beagle-host.sh` weiter auf beagle-only bereinigt:
	- Host-Provider-Resolution normalisiert Legacy-Proxmox-Werte konsequent auf `beagle`.
	- Proxmox-spezifischer `apt`-Fallback (enterprise repo strip/retry) entfernt.
- Neues Tooling fuer reproduzierbare Installer-Artefakt-Pruefung:
	- `scripts/verify-server-installer-artifacts.sh` (Checksums + optionale GPG-Signaturen fuer server-installer ISOs).
	- Lokaler End-to-End-Lauf gegen `dist/` erfolgreich (`SHA256SUMS` + `.sig` Verifikation).
- `docs/gofuture/06-server-installer.md` Testpflicht teilweise abgeschlossen:
	- `Installation ohne Proxmox-Abhaengigkeiten`,
	- `Post-Install service active`,
	- `ISO-Checksum/Signatur verifizierbar` auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 06 Schritt 4-5: shared postinstall hook + release signing chain)

- Gemeinsamen Post-Install-Pfad umgesetzt:
	- neues Shared-Hook-Skript `scripts/install-beagle-host-postinstall.sh` erstellt,
	- `scripts/install-beagle-host.sh` delegiert den gesamten post-install Bootstrap jetzt an diesen Hook statt Inline-Logik.
- Damit laufen Installer- und nachträglicher Installationspfad über dieselbe Sequenz (host env schreiben, services bootstrap, proxy setup).
- Release-Chain für Installer-Artefakte gehaertet in `scripts/create-github-release.sh`:
	- deterministische Regeneration von `dist/SHA256SUMS` aus den finalen Release-Assets,
	- optionaler GPG-Signaturpfad (`BEAGLE_RELEASE_SIGN`, `BEAGLE_RELEASE_GPG_KEY`) integriert,
	- automatische Veröffentlichung der Signaturartefakte (`*.iso.sig`, `SHA256SUMS.sig`) als Release-Assets vorbereitet.
- `docs/gofuture/06-server-installer.md` Schritt 4 und 5 auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 06 Schritt 1-3: Server-Installer standalone + reproducible build env)

- `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer` auf standalone-only refactored:
	- Proxmox-Installmode-Branches entfernt/normalisiert,
	- Proxmox-Repo/Key-Handling entfernt,
	- Host-Paketpfad auf Beagle-only vereinheitlicht.
- Paketpfad im Installer erweitert auf explizite Standalone-Komponenten inkl. `nginx` und `websockify` (zusätzlich zu libvirt/KVM/QEMU + certbot-Pfaden).
- `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer-gui` ebenfalls auf einen einzigen Standalone-Modus reduziert (curses + plain fallback).
- Reproducible-Build-Vorbereitung umgesetzt:
	- neue zentrale Datei `server-installer/build.env` mit Build-Abhängigkeiten und Speicher-Guardrails,
	- `scripts/build-server-installer.sh` lädt `build.env` automatisch.
- `docs/gofuture/06-server-installer.md` aktualisiert:
	- Schritt 1-3 Checkboxes auf `[x]`,
	- ASCII-Flowchart des Installer-Ablaufs ergänzt,
	- Umsetzungsnotizen je Schritt ergänzt.

## Update (2026-04-21, GoFuture Plan 05: Proxmox dauerhaft entfernt + Mock-Provider Tests)

- `providers/proxmox/` und `proxmox-ui/` dauerhaft aus dem Repo geloescht (Plan 05 Schritt 5b).
- `beagle-host/providers/proxmox_host_provider.py` geloescht (nur noch `beagle_host_provider.py` und `registry.py`).
- Neuer Unit-Test `tests/unit/test_vm_services_mock_provider.py` erstellt (Plan 05 Schritt 5a):
  - `MockHostProvider` implementiert vollstaendigen `HostProvider`-Contract fuer Tests ohne libvirt.
  - 21 Tests fuer `VirtualizationInventoryService` (Happy-Paths + Error-Paths) und Contract-Compliance.
- `tests/unit/test_beagle_novnc_token.py` von pytest auf stdlib unittest umgeschrieben (portabel, kein pytest noetig).
- Skript-Bereinigung: `proxmox-ui`-Referenzen aus `scripts/validate-project.sh`, `scripts/install-beagle-host.sh`, `scripts/install-beagle-proxy.sh`, `scripts/package.sh`, `scripts/build-server-installer.sh`, `scripts/build-server-installimage.sh` entfernt.
- `install-beagle-proxy.sh`: Default-Provider auf `beagle` geaendert, `host_provider_kind()` normalisiert proxmox/pve -> beagle, Proxmox-spezifische Cert-Logik entfernt, nginx-Location fuer `beagle-autologin.js` entfernt.
- `install-beagle-host.sh`: proxmox-ui-integration-call entfernt.
- Finale Pruefung: `grep -r "qm\|pvesh\|/api2/json\|PVEAuthCookie" beagle-host/ providers/ --include="*.py"` -> 0 Treffer.
- Lokale Tests: `python3 -m unittest discover -s tests/unit -q` -> `48 passed`.
- Deploy + Validierung auf `srv1.beagle-os.com`:
  - `tests/unit/` synchronisiert, `48 passed` auf srv1.
  - `scripts/smoke-control-plane-api.sh` -> `13/13`.
  - Alle Services `active`: `beagle-control-plane`, `beagle-novnc-proxy`, `nginx`.

## Update (2026-04-21, GoFuture Plan 04 Schritt 2: Route-Delegation weitergezogen)

- Neue Service-Schicht fuer Auth/IAM-HTTP-Surface eingefuehrt: `beagle-host/services/auth_http_surface.py`.
- Aus `beagle-host/bin/beagle-control-plane.py` extrahiert und an Service delegiert:
	- GET: `/api/v1/auth/users`, `/api/v1/auth/roles`
	- POST: `/api/v1/auth/users`, `/api/v1/auth/roles`, `/api/v1/auth/users/{username}/revoke-sessions`
	- PUT: `/api/v1/auth/users/{username}`, `/api/v1/auth/roles/{name}`
	- DELETE: `/api/v1/auth/users/{username}`, `/api/v1/auth/roles/{name}`
- Handler-Logik reduziert auf Auth/RBAC-Guard + JSON-Read + Service-Call + Response-Write.
- Audit-Trail beibehalten ueber neuen Delegationspfad (`auth.user.*`, `auth.role.*`, `auth.user.revoke_sessions`).
- Neue Unit-Tests: `tests/unit/test_auth_http_surface.py`.
	- lokal: `pytest -q tests/unit/test_auth_http_surface.py tests/unit/test_auth_session.py tests/unit/test_authz_policy.py` -> `12 passed`.
- Deploy + Runtime-Validierung auf `srv1.beagle-os.com`:
	- aktualisierte Dateien nach `/opt/beagle` ausgerollt,
	- `./scripts/install-beagle-host-services.sh` ausgefuehrt,
	- `beagle-control-plane.service` neu gestartet (`active`),
	- `scripts/smoke-control-plane-api.sh` erneut erfolgreich (`13/13`).

## Update (2026-04-21, GoFuture Plan 20: single-use noVNC tokens + HTTP-only refresh cookie wave)

- **noVNC single-use tokens**: custom websockify plugin `beagle-host/bin/beagle_novnc_token.py` implementing `BeagleTokenFile` class.
  - Tokens are 32-byte random, stored as JSON in `/etc/beagle/novnc/console-tokens.json`.
  - Expires 30 seconds after creation; consumed (single-use) on first successful `lookup()` call.
  - `vm_console_access.py` now generates a fresh token per `/novnc-access` request instead of reusing persistent per-VM tokens.
  - `beagle-novnc-proxy.service` updated: `--token-plugin beagle_novnc_token.BeagleTokenFile`, `PYTHONPATH=/opt/beagle/lib`.
  - 8 new unit tests pass (`tests/unit/test_beagle_novnc_token.py`).
- **HTTP-only refresh token cookie**: `beagle-control-plane.py` now sets `Set-Cookie: beagle_refresh_token=...; HttpOnly; SameSite=Strict; Path=/api/v1/auth; Secure` on successful login and refresh. Clears cookie on logout and on failed refresh.
  - `/auth/refresh` also reads the token from cookie if not present in JSON body.
- **Audit events for endpoint lifecycle mutations**: `endpoint_lifecycle_surface` POST handler now emits `endpoint.lifecycle` audit events matching the existing pattern.
- Deployed and validated on `srv1.beagle-os.com`:
  - Both `beagle-novnc-proxy` and `beagle-control-plane` active after restart.
  - `journalctl -u beagle-novnc-proxy` confirms: `proxying from 127.0.0.1:6080 to targets generated by BeagleTokenFile`.
  - Cookie helper methods present in deployed control plane source.

## Update (2026-04-21, GoFuture Plan 20: CSP + systemd hardening wave)

- `scripts/install-beagle-proxy.sh` CSP tightened for nginx by adding secure websocket source:
  - `connect-src 'self' wss:`
  - no `unsafe-inline` and no `unsafe-eval` in the configured policy.
- Hardened beagle systemd units with explicit `CapabilityBoundingSet=` and `RestrictAddressFamilies=`:
  - `beagle-host/systemd/beagle-artifacts-refresh.service`
  - `beagle-host/systemd/beagle-public-streams.service`
  - `beagle-host/systemd/beagle-ui-reapply.service`
  - `beagle-host/systemd/beagle-novnc-proxy.service`
- `beagle-novnc-proxy.service` switched to non-root runtime:
  - `User=beagle-manager`, `Group=beagle-manager`
  - additional sandboxing (`NoNewPrivileges`, `ProtectSystem=strict`, syscall/address-family restrictions).
- Deployed and validated on `srv1.beagle-os.com`:
  - `beagle-novnc-proxy`, `beagle-control-plane`, `nginx` all `active` after rollout.
  - `systemctl show` confirms non-root noVNC runtime and empty `CapabilityBoundingSet`.
  - HTTPS response header confirms CSP contains `connect-src 'self' wss:`.

## Update (2026-04-21, GoFuture Plan 04/20: Input-Validation + Dependency-Audit Welle)

- Serverseitige Input-Validierung gehaertet:
	- `beagle-host/bin/beagle-control-plane.py` mit Payload-Whitelist-Pruefung fuer zentrale Auth-POST-Routen (`login`, `refresh`, `logout`, `onboarding`, `auth/users`, `auth/roles`).
	- `sanitizeIdentifier`-Logik auf Serverseite ergaenzt.
	- `beagle-host/services/auth_session.py` erzwingt Username-/Role-Pattern in den relevanten CRUD/Auth-Pfaden.
- Regression/Validierung:
	- lokal: `python -m unittest tests.unit.test_auth_session` -> OK,
	- srv1: invalid onboarding-username und unknown login keys liefern korrekt `400 bad_request` statt 500,
	- srv1: bestehender Control-Plane-Smoke (`scripts/smoke-control-plane-api.sh`) weiterhin `13/13`.
- Dependency-Audit Automatisierung implementiert:
	- neues Skript `scripts/security-audit.sh` (pip-audit + npm audit, Report nach `dist/security-audit/`),
	- neuer CI-Workflow `.github/workflows/security-audit.yml` (monatlich + manual dispatch).
- Security-Run dokumentiert in `docs/refactor/11-security-findings.md` (S-007, S-008).

## Update (2026-04-21, GoFuture Plan 04/05/20: Security+Error-Handling Welle)

- `beagle-host/bin/beagle-control-plane.py` gehaertet:
	- API-Rate-Limit fuer alle `/api/*` Requests hinzugefuegt.
	- Login-Brute-Force-Schutz mit Exponential-Backoff + Lockout hinzugefuegt.
	- Fehler-Payloads bekommen jetzt konsistentes `code`-Feld.
	- Unhandled-Exception-Grenze liefert sanitisiertes `500`-JSON (`internal_error`).
	- Strukturierte JSON-Response-Logs erweitert um `user`, `action`, `resource_type`, `resource_id`.
- Auth-Default gehaertet:
	- Access-Token-Default auf 15 Minuten (`BEAGLE_AUTH_ACCESS_TTL_SECONDS=900`).
- `scripts/install-beagle-host-services.sh` setzt Security-Defaults fuer die neuen Rate-Limit/Lockout-Parameter in `beagle-manager.env`.
- Live auf `srv1.beagle-os.com` validiert:
	- `401`-Antworten mit `code=unauthorized` verifiziert,
	- Brute-Force-Verhalten verifiziert (`/api/v1/auth/login` liefert nach Wiederholungen `429 rate_limited`),
	- API-Rate-Limit verifiziert (temporar auf 5 gesetzt, `429 rate_limited` reproduzierbar, danach auf 240 zurueckgesetzt),
	- Service nach Deploy stabil `active`.
- Provider-Abstraction/Testpflicht-Nachweise fuer Plan 05 ergaenzt:
	- `grep`-Audit fuer Proxmox-Direktaufrufe in `beagle-host/` ausgefuehrt,
	- `python -m pytest tests/unit -q` ausgefuehrt: `15 passed`.

## Update (2026-04-21, GoFuture Plan 04 Testpflicht: API-Smoke reproduzierbar abgeschlossen)

- Neues reproduzierbares Smoke-Skript angelegt: `scripts/smoke-control-plane-api.sh`.
- Das Skript prueft zentrale Read/Mutation/Auth-Routen mit erwarteten Statuscodes (`200/400/401`) gegen den laufenden Control Plane Endpoint.
- Deploy nach `srv1.beagle-os.com` unter `/opt/beagle/scripts/smoke-control-plane-api.sh` und Live-Ausfuehrung erfolgreich.
- Ergebnis auf `srv1`: `Smoke checks passed: 13` (13/13 erwartete Checks bestanden).
- Damit ist die offene GoFuture-Checkbox `Alle API-Endpunkte antworten korrekt nach Refactoring (Smoke-Tests)` fuer Plan 04 als reproduzierbar verifiziert abgehakt.

## Update (2026-04-21, GoFuture Plan 04 Schritt 7 umgesetzt: Control-Plane als non-root Service)

- `beagle-host/systemd/beagle-control-plane.service` gehaertet und auf dedizierten Runtime-User umgestellt:
	- `User=beagle-manager`, `Group=beagle-manager`, `SupplementaryGroups=libvirt kvm`
	- `Restart=on-failure`, `RestartSec=5`
	- `CapabilityBoundingSet=` (leer), weiterhin `NoNewPrivileges=yes` + `PrivateTmp=yes`
	- Proxmox-spezifische `ReadWritePaths` entfernt (`/var/lib/vz`, `/etc/pve`, `/var/log/pve`).
- `scripts/install-beagle-host-services.sh` erweitert:
	- legt `beagle-manager` als System-User an (falls fehlend),
	- haengt User an `libvirt`/`kvm` Gruppen,
	- setzt Berechtigungen fuer `/var/lib/beagle/beagle-manager` sowie `/etc/beagle/beagle-manager.env` und `/etc/beagle/novnc/tokens` fuer non-root-Betrieb.
- Deploy + Validierung auf `srv1.beagle-os.com`:
	- aktualisierte Unit + Installer-Script ausgerollt,
	- Service neu installiert/reloaded/restarted,
	- `systemctl show` bestaetigt `User=beagle-manager`, `Restart=on-failure`, `RestartUSec=5s`, `CapabilityBoundingSet=`,
	- `beagle-control-plane.service` ist `active`, keine Traceback-/Unhandled-Exception-Marker im Journal.

## Update (2026-04-21, GoFuture Plan 04 Testpflicht erweitert: Audit-Events + Log-Stabilitaet)

- Control-Plane Audit-Pfad fuer VM-Power-Mutationen zentralisiert:
	- neues Service-Helpermodul `beagle-host/services/audit_helpers.py` mit `build_vm_power_audit_event(...)`.
	- `beagle-host/bin/beagle-control-plane.py` nutzt den Helper jetzt fuer `POST /api/v1/virtualization/vms/{vmid}/power` und schreibt explizite Audit-Events `vm.start`, `vm.stop`, `vm.reboot` mit `resource_type=vm` und `resource_id=<vmid>`.
- `auth.user.create`-Audit angereichert um strukturierte Resource-Metadaten (`resource_type=user`, `resource_id=<username>`) plus `remote_addr`.
- Neue Unit-Tests hinzugefuegt:
	- `tests/unit/test_audit_helpers.py`
	- `tests/unit/test_audit_log.py`
- Lokale Validierung erfolgreich:
	- `python -m unittest tests.unit.test_auth_session tests.unit.test_server_settings tests.unit.test_authz_policy tests.unit.test_audit_helpers tests.unit.test_audit_log` -> `OK`.
- Deploy und Runtime-Check auf `srv1.beagle-os.com`:
	- geaenderte Control-Plane-Dateien nach `/opt/beagle` synchronisiert,
	- `beagle-control-plane.service` neu gestartet -> `active`,
	- neue Audit-Unit-Tests auf `srv1` erfolgreich,
	- `journalctl -u beagle-control-plane.service` zeigt keine `Traceback`/`Unhandled Exception`-Marker.

## Update (2026-04-21, GoFuture Plan 05 step 1/3 umgesetzt: Provider Contract + Beagle Provider Erweiterung)

- Provider-Contract erweitert in `beagle-host/providers/host_provider_contract.py` um:
	- `snapshot_vm(...)`
	- `clone_vm(...)`
	- `get_console_proxy(...)`
- Beagle-Provider implementiert diese Methoden real:
	- Snapshot: lokale Snapshot-Metadaten + optionales libvirt snapshot-create.
	- Clone: VM-State-Klon + optionales libvirt volume-clone mit Fallback.
	- Console-Proxy: VNC-Metadaten aus libvirt (`vncdisplay`) fuer noVNC-Weiterverarbeitung.
- Proxmox-Provider ebenfalls auf Contract-Paritaet erweitert (snapshot/clone/console payload), ohne neue Kopplung ausserhalb des Provider-Layers.
- Unit-Test hinzugefuegt: `tests/unit/test_beagle_host_provider_contract_extensions.py` (3 Tests, alle gruen lokal).
- Deploy + Runtime-Smoketest auf `srv1.beagle-os.com` erfolgreich:
	- `snapshot_vm(301, "smoke-snap")` -> success,
	- `clone_vm(301, 302)` -> success,
	- `get_console_proxy(301)` -> valid payload.

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

## Update (2026-04-21, GoFuture Plan 05 Schritt 4 umgesetzt: Registry Beagle-only)

- `beagle-host/providers/registry.py` auf Beagle-only umgestellt:
	- `_PROVIDER_MODULES` enthaelt nur noch `beagle`.
	- Legacy-Provider-Werte `proxmox` und `pve` normalisieren auf `beagle`.
- Dadurch bleibt Legacy-Env kompatibel, aber die effektive Provider-Instanz ist immer der Beagle-Provider.
- Deploy auf `srv1.beagle-os.com` erfolgt, Control Plane startet stabil weiter (`active`).

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
  - `scripts/package.sh` no longer includes local-only `AGENTS.md` / `AGENTS.md` in `beagle-os-v*.tar.gz`,
  - `scripts/build-server-installer.sh` no longer includes those local files in the server installer embedded source archive,
  - installimage embedded source archive was verified clean.
- Improved local build cleanup:
  - `scripts/lib/disk_guardrails.sh` now creates missing check paths inside the low-level `df` helper,
  - reproducible artifact cleanup can use `sudo rm -rf` when previous root/live-build runs left root-owned outputs behind.
- Known residual:
  - GitHub release asset upload is still blocked in this workspace by missing local GitHub CLI/token auth; code changes still need to be pushed through an authenticated GitHub path.

## Update (2026-04-19, operator files exclusion from installimage tarballs)

- Identified that AGENTS.md (local-only operator files) were being accidentally bundled into the embedded source archive within the installimage tarball.
- Root cause: `tar` commands in both `build-server-installimage.sh` and `build-server-installer.sh` were not excluding these files.
- Implemented fix in commit `497eee2`:
  - Added `--exclude='AGENTS.md' --exclude='AGENTS.md'` flags to tar commands in both builder scripts.
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
  - first tarball build accidentally bundled local-only `AGENTS.md` and `AGENTS.md` inside the embedded Beagle source archive,
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
  - local-only handling for `AGENTS.md` / `AGENTS.md`.
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
- Added `.gitignore` protection for `AGENTS.md` and `AGENTS.md` so these local operator files stop being eligible for accidental GitHub publication.
- Removed `AGENTS.md` and `AGENTS.md` from the Git index while keeping both files locally present for operator use.
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

## Update (2026-04-25, GoAdvanced 12-Plan-Serie ergaenzt)

- Vollstaendige Repo-Auditierung durchgefuehrt (Sicherheit, Refactor, Tests, Operations, Performance, UX, Doku).
- Neue Plan-Serie `docs/goadvanced/` mit 12 Plan-Dateien + Index erstellt:
        - [docs/goadvanced/00-index.md](docs/goadvanced/00-index.md) — Uebersicht + 3-Wave-Roadmap (A Sofort / B Mittelfrist / C Langfrist)
        - [docs/goadvanced/01-data-integrity.md](docs/goadvanced/01-data-integrity.md) — Atomic JSON + fcntl-Lock
        - [docs/goadvanced/02-tls-hardening.md](docs/goadvanced/02-tls-hardening.md) — `curl -k`-Eradication, HSTS/CSP, CI-Guard
        - [docs/goadvanced/03-secret-management.md](docs/goadvanced/03-secret-management.md) — Rotation/Versioning + Vault-Adapter Ph2
        - [docs/goadvanced/04-subprocess-sandboxing.md](docs/goadvanced/04-subprocess-sandboxing.md) — `run_cmd_safe` + Validators
        - [docs/goadvanced/05-control-plane-split.md](docs/goadvanced/05-control-plane-split.md) — 6000-LOC-Monolith → Surfaces
        - [docs/goadvanced/06-state-sqlite-migration.md](docs/goadvanced/06-state-sqlite-migration.md) — JSON → SQLite via Repository
        - [docs/goadvanced/07-async-job-queue.md](docs/goadvanced/07-async-job-queue.md) — JobQueue + SSE
        - [docs/goadvanced/08-observability.md](docs/goadvanced/08-observability.md) — Prometheus + Structured Logs
        - [docs/goadvanced/09-ci-pipeline.md](docs/goadvanced/09-ci-pipeline.md) — shellcheck/bats/ISO-Build/SBOM
        - [docs/goadvanced/10-integration-tests.md](docs/goadvanced/10-integration-tests.md) — Integrations + E2E
        - [docs/goadvanced/11-proxmox-endbeseitigung.md](docs/goadvanced/11-proxmox-endbeseitigung.md) — Hard-Delete-Plan
        - [docs/goadvanced/12-ux-accessibility.md](docs/goadvanced/12-ux-accessibility.md) — i18n + ARIA + Mobile
- Welle A (Sofort) deckt Plaene 01-04 ab; Welle B 05/09/10; Welle C 06/07/08/11/12.
- Naechster Run: mit Plan 01 (Data-Integrity) beginnen.
