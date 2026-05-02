# Beagle OS — Master Plan (vereinheitlichter Gesamtplan)

Stand: 2026-05-02
Aktuelle Version (`VERSION`): **8.0.9**
Quelle der Wahrheit: **dieses Dokument**.

Dieses Dokument konsolidiert alle bisherigen Teilplaene zu einer einzigen,
widerspruchsfreien Sicht. Die historischen Plan-Verzeichnisse
(`docs/archive/refactorv2/`, `docs/archive/gofuture/`, `docs/archive/goenterprise/`, `docs/archive/goadvanced/`,
`docs/archive/gorelease/`) sind nach `docs/archive/` verschoben und dienen nur noch als
Hintergrundmaterial. Operative Aufgaben leben ausschliesslich in den fuenf
Checklisten unter [`docs/checklists/`](checklists/) (siehe Abschnitt 2).
Der konsolidierte Enterprise-GA-Steuerplan liegt unter
[`docs/lasthope/`](lasthope/) und fasst die offenen Gates fuer ein
firmentaugliches Angebot zusammen, ohne eigene Detail-Backlogs zu ersetzen.

Wenn ein archivierter Teilplan diesem Dokument widerspricht, gilt dieses Dokument.

---

## 1. Was Beagle OS ist

Beagle OS ist eine eigenstaendige, Open-Source Desktop-Virtualisierungs- und
Streaming-Plattform mit eigenem Endpoint-OS. Kernbausteine:

- **Beagle Host / Control Plane** (`beagle-host/`, `core/`, `providers/beagle/`):
  KVM/libvirt-basierte Virtualisierung, Provider-neutrale Services,
  Web Console, Auth/RBAC, Audit, Cluster-Foundation.
- **Beagle Web Console** (`website/`): einzige Operator-Oberflaeche.
- **BeagleStream** (Beagle Stream Server/Beagle Stream Client-Fork-Strategie, Plan GoEnterprise 01):
  Streaming-Protokoll mit WireGuard-Mesh.
- **Beagle Endpoint OS / Thin Client** (`beagle-os/`, `thin-client-assistant/`):
  eigenes Endpoint-OS, QR-Enrollment, Zero-Trust.
- **Gaming Kiosk** (`beagle-kiosk/`): Electron-basierter Kiosk-Mode.
- **Server-Installer** (`server-installer/`, `scripts/build-server-installer*.sh`):
  Bare-Metal-ISO und Hetzner installimage.
- **API/CLI/IaC** (`scripts/beaglectl.py`, OpenAPI v1, Terraform-Provider).

Proxmox ist vollstaendig entfernt. Es gibt nur noch einen Provider:
`providers/beagle/` (libvirt/KVM). `proxmox-ui/` und `providers/proxmox/`
existieren nicht mehr im Repo (verifiziert 2026-04-29).

---

## 2. Operatives Backlog — 5 Checklisten

**Stand 2026-05-02:** Saemtliche aktive Arbeit lebt in genau **fuenf** Checklisten
unter [`docs/checklists/`](checklists/). Die historischen Mehrfach-Plaene
(`refactorv2`, `gofuture`, `goenterprise`, `goadvanced`, `gorelease`) sind als
Hintergrundmaterial nach [`docs/archive/`](archive/) verschoben — sie sind
**keine Auftragslisten mehr**.

| # | Datei | Thema |
|---|---|---|
| 01 | [checklists/01-platform.md](checklists/01-platform.md) | Cluster, Storage, HA, VDI, GPU, SDN |
| 02 | [checklists/02-streaming-endpoint.md](checklists/02-streaming-endpoint.md) | BeagleStream, WireGuard, Endpoint, Kiosk, Session-Mgmt |
| 03 | [checklists/03-security.md](checklists/03-security.md) | Auth, RBAC, Secrets, Audit, TLS, IAM/Tenancy |
| 04 | [checklists/04-quality-ci.md](checklists/04-quality-ci.md) | CI, Tests, Datenintegritaet, Observability, UX/i18n |
| 05 | [checklists/05-release-operations.md](checklists/05-release-operations.md) | Release-Gates R0..R4, Runbooks, Operations |

Pro Aufgabe gilt: **eine** Checkliste, **ein** `[ ]`/`[x]`-Eintrag. Keine neuen
Detail-Plan-Dateien anlegen. `docs/lasthope/` ist die feste Enterprise-GA-
Sicht auf dieselben offenen Gates, nicht ein zweites Backlog.

Logbuecher:

- `docs/refactor/05-progress.md` — chronologisches Run-Log (append-only).
- `docs/refactor/06-next-steps.md` — letzte "Stand"-Eintraege ganz oben.
- `docs/refactor/08-todo-global.md` — globaler Checklisten-Stand.
- `docs/refactor/11-security-findings.md` — Security-Funde + Restrisiken.
- `docs/lasthope/README.md` — finale Enterprise-GA-Sicht fuer Firmenangebot,
  Gates und Reihenfolge.

Diese Logbuecher bleiben die Quelle fuer "was wurde wann gemacht"; dieses
Master-Dokument fasst Status pro Themengebiet zusammen.

---

## 3. Kanonische Themen-Zuordnung (Aufloesung der Ueberlappungen)

Mehrere Themen tauchen in mehreren Plan-Verzeichnissen auf. Pro Thema gilt
genau **ein** kanonischer Detailplan. Andere Vorkommen sind Hintergrund.

| Thema | Kanonischer Plan | Sekundaer / Hintergrund |
|---|---|---|
| Streaming-Protokoll (BeagleStream) | `archive/goenterprise/01-beagle-stream-client-vdi-protocol.md` | `archive/gofuture/11-streaming-v2.md`, `archive/refactorv2/05-streaming-protocol-strategy.md` |
| Zero-Trust Thin Client + WireGuard | `archive/goenterprise/02-zero-trust-thin-client.md` | `archive/gofuture/19-endpoint-os.md`, `archive/refactorv2/11-endpoint-strategy.md` |
| Gaming Kiosk Pools | `archive/goenterprise/03-gaming-kiosk-pools.md` | — |
| Smart Scheduler / Placement | `archive/goenterprise/04-ai-smart-scheduler.md` | `archive/refactorv2/08-ha-cluster.md` |
| Cost Transparency / Chargeback | `archive/goenterprise/05-cost-transparency.md` | — |
| Live Session Handover | `archive/goenterprise/06-session-handover.md` | `archive/gofuture/07-cluster-foundation.md` |
| Fleet Intelligence / Predictive Maintenance | `archive/goenterprise/07-fleet-intelligence.md` | `archive/refactorv2/13-observability-operations.md` |
| All-in-One Bare-Metal Installer + PXE | `archive/goenterprise/08-all-in-one-installer.md` | `archive/gofuture/06-server-installer.md` |
| Energy + CO2 Dashboard / CSRD | `archive/goenterprise/09-energy-dashboard.md` | — |
| GPU Pool / Streaming Routing | `archive/goenterprise/10-gpu-streaming-pools.md` | `archive/gofuture/12-gpu-plane.md`, `archive/refactorv2/10-gpu-device-passthrough.md` |
| Cluster Foundation / Live-Migration | `archive/gofuture/07-cluster-foundation.md` | `archive/refactorv2/08-ha-cluster.md` |
| Storage Plane (StorageClass, ZFS, Ceph) | `archive/gofuture/08-storage-plane.md` | `archive/refactorv2/07-storage-network-plane.md` |
| HA Manager / Fencing | `archive/gofuture/09-ha-manager.md` | `archive/refactorv2/08-ha-cluster.md` |
| VDI Pools + Templates | `archive/gofuture/10-vdi-pools.md` | — |
| IAM v2 + SSO + SCIM + Tenancy | `archive/gofuture/13-iam-tenancy.md` | `archive/refactorv2/06-iam-multitenancy.md` |
| Session Recording + Watermark | `archive/gofuture/14-session-recording.md` | `archive/refactorv2/12-security-compliance.md` |
| Audit + Compliance Export | `archive/gofuture/15-audit-compliance.md` | `archive/refactorv2/12-security-compliance.md` |
| Backup + Disaster Recovery | `archive/gofuture/16-backup-dr.md` | `archive/refactorv2/09-backup-dr.md` |
| SDN + Distributed Firewall | `archive/gofuture/17-sdn-firewall.md` | `archive/refactorv2/07-storage-network-plane.md` |
| OpenAPI + Terraform + `beaglectl` | `archive/gofuture/18-api-iac-cli.md` | `archive/refactorv2/14-platform-api-extensibility.md` |
| Provider-Abstraction (Proxmox-Endbeseitigung) | `archive/gofuture/05-provider-abstraction.md` | `refactor/09-provider-abstraction.md`, `archive/goadvanced/11-beagle-endbeseitigung.md` |
| Control-Plane Aufspaltung | `archive/goadvanced/05-control-plane-split.md` | `archive/gofuture/04-control-plane.md` |
| Datenintegritaet (atomic writes, locking, SQLite) | `archive/goadvanced/01-data-integrity.md`, `archive/goadvanced/06-state-sqlite-migration.md` | — |
| TLS-Haerte + Cert-Pinning | `archive/goadvanced/02-tls-hardening.md` | — |
| Secret-Rotation + Vault | `archive/goadvanced/03-secret-management.md` | — |
| Subprocess Sandboxing | `archive/goadvanced/04-subprocess-sandboxing.md` | — |
| Async Job Queue | `archive/goadvanced/07-async-job-queue.md` | — |
| Observability (Prometheus, OTel, Logs) | `archive/goadvanced/08-observability.md` | `archive/refactorv2/13-observability-operations.md` |
| CI Pipeline (shellcheck/bats/SBOM) | `archive/goadvanced/09-ci-pipeline.md` | — |
| Integration-/E2E-Tests | `archive/goadvanced/10-integration-tests.md` | `archive/gorelease/03-end-to-end-validation.md` |
| WebUI Modularisierung (JS/CSS/index) | `archive/gofuture/01..03-webui-*.md` | — |
| Release Gates (R0..R4) | `archive/gorelease/00-index.md` + `01..05-*.md` | — |
| Security-Hardening (kontinuierlich) | `archive/gofuture/20-security-hardening.md`, `archive/goadvanced/02..04`, `archive/gorelease/01-security-gates.md` | `refactor/11-security-findings.md` |
| UX/Accessibility/i18n | `archive/goadvanced/12-ux-accessibility.md` | — |

Regel: Wenn zwei Plaene sich widersprechen, gilt der kanonische. Der
sekundaere Plan ist als Hintergrund/Recherche zu lesen, nicht als Auftrag.

---

## 4. Aktueller Ist-Stand (verifiziert 2026-04-29)

### Erledigt (groesste Wellen)

- **Refactor Welle 1 (Identity/Session/RBAC)**: erledigt. Login, Refresh, Logout,
  RBAC-Middleware fuer alle mutierenden Endpoints.
- **Refactor Welle 2 (Stream-First VM Domain)**: erledigt. Stream-Lifecycle pro VM,
  vereinheitlichte Action-Queue.
- **Provider-Abstraction (Proxmox-Endbeseitigung)**: erledigt. Es gibt nur noch
  `providers/beagle/`. Grep nach `qm|pvesh|/api2/json|PVEAuthCookie` = 0 Treffer.
  `proxmox-ui/` und `providers/proxmox/` existieren nicht mehr.
- **WebUI Modularisierung** (`archive/gofuture/01..03`): erledigt; `app.js` ist in ES-Module
  zerlegt, `styles.css` in Teilmodule, `index.html` verweist auf `main.js`.
- **Server-Installer / Bare-Metal ISO** (`archive/gofuture/06`, `archive/goenterprise/08`):
  ISO + Hetzner installimage reproduzierbar bauen, TUI-/Seed-/PXE-Flows abgenommen.
- **Cluster Foundation 7.0.0** (`archive/gofuture/07`): WebUI-Cluster-Operations, Join/Drain,
  Member-Verwaltung verfuegbar; live-Migration in Single-Host getestet.
- **GoEnterprise Plan 02 — Zero-Trust Thin Client + MDM**: vollständig erledigt.
  Device-Registry, Lock/Wipe, Policy-Editor, Effective-Policy-Diff, Drift-/
  Auto-Remediation, WireGuard-Full-Tunnel produktiv. Grafischer X11-Lockscreen
  per Xvfb-Akzeptanztest live abgenommen (17/17 passed, 2026-04-29).
- **GoEnterprise Plan 04 — Smart Scheduler**: WebUI bedienbar, Heatmap, Green-Hours,
  Saved-CPU-Hours, Warm-Pool-Auto-Apply, Acceptance-Tests gruen.
- **GoEnterprise Plan 05 — Cost Transparency**: Chargeback, Budgets, Forecast,
  Drilldown, Acceptance-Tests gruen.
- **GoEnterprise Plan 07 — Fleet Intelligence**: SMART, Anomalie-Trend, Alert-Webhook,
  Maintenance-Migration getestet.
- **GoEnterprise Plan 08 — All-in-One Installer**: TUI 5-Schritte, Seed, PXE+DHCP,
  RAID0/1/5/10 multi-disk, Acceptance-Tests gruen.
- **GoEnterprise Plan 09 — Energy + CSRD**: RAPL/VM-Anteil, Carbon-Profil,
  Chargeback-Energiekosten, externer Feed-Job, Acceptance-Tests gruen.
- **GoEnterprise Plan 01 — BeagleStream (Control-Plane-Slice)**: Stream-Server-API
  (`/api/v1/streams/register|config|events|allocate`) verdrahtet, `vpn_required`-
  Enforcement (`403`), Token-Pairing 60 s TTL + Replay-Schutz, VM-seitiger Smoke
  per QEMU-Guest-Agent gruen.
- **WireGuard-Mesh Thinclient-Full-Tunnel**: Endpoint-authentifiziertes
  `vpn/register`, Root-Reconcile-Pfad, Host-Firewall-Default UDP 51820, robustes
  Thinclient-Enrollment ohne `wg-quick`-Haenger.
- **WebUI-Stabilitaet (CSP, Auth-Gating, Login-429, Inline-Styles, XFCE-Idle/Locker)**:
  alle bekannten Live-Befunde gepatcht und auf `srv1` verifiziert.
- **GoAdvanced Plan 09 — CI Pipeline**: shellcheck/bats/SBOM-Gates aktiv.

### In Arbeit / offen (echte Restpunkte)

- **GoEnterprise Plan 01 — Fork**: separater `beagle-stream-server`-Fork
  (Beagle Stream Server-Patches) inkl. .deb-Build und Beagle Stream Client-Client-Fork; Phase B/C/D der
  Stream-Roadmap; WireGuard-Mesh-Latenz-Live-Test (vorheriger Namespace-Sim
  erreichte das +0.01 ms-Threshold nicht); `vpn_required`-Enforcement im Fork.
- ~~**GoEnterprise Plan 02 — Restpunkte**~~: grafischen Sperrbildschirm live an X11-Session
  abgenommen via Xvfb-Akzeptanztest (`scripts/test-lockscreen-x11-acceptance.sh`). **ERLEDIGT 2026-04-29.**
- **GoEnterprise Plan 03 — Gaming Kiosk Pools**: Pool-Wizard, Esports-/Schul-/
  Militaer-Profile in der WebUI bedienbar.
- **GoEnterprise Plan 06 — Live Session Handover**: Stream-Uebergabe zwischen Nodes.
- **GoEnterprise Plan 10 — GPU Streaming Pools**: Pool-Routing + Stream-Routing.
- **GoFuture 7.0.1 Storage Plane** (`archive/gofuture/08`): StorageClass-Backends
  (lvm-thin, zfs, nfs, optional Ceph/Longhorn); Quotas pro Tenant.
- **GoFuture 7.0.2 HA Manager** (`archive/gofuture/09`): Watchdog-Fencing, Restart-Policies,
  Anti-/Affinity, 60-s-Recovery-Akzeptanz.
- **GoFuture 7.1.0 VDI Pools** (`archive/gofuture/10`): Pool-Wizard, Template-Builder,
  Floating-/Persistent-/Dedicated-Modi.
- **GoFuture 7.1.1 Streaming v2** (`archive/gofuture/11`): Apollo + Virtual Display,
  Auto-Pairing per signiertem Token, HDR + Multi-Monitor + 4:4:4, Audio-In/Mikro/
  Wacom/Gamepad-Redirect E2E.
- **GoFuture 7.1.2 GPU Plane** (`archive/gofuture/12`): vGPU (Mediated Devices, SR-IOV),
  Pool-Constraint `gpu_class`, Scheduler-GPU-Reservation.
- **GoFuture 7.2.0 IAM v2 + Tenancy** (`archive/gofuture/13`): OIDC, SAML, SCIM 2.0,
  Tenant-Scope flaechendeckend, Policy-Engine.
- **GoFuture 7.2.1 Session Recording + Watermark** (`archive/gofuture/14`).
- **GoFuture 7.2.2 Audit + Compliance Export** (`archive/gofuture/15`): Schema-Vereinheitlichung,
  S3/Syslog/Webhook, PII-Schwaerzung, Reportgenerator.
- **GoFuture 7.3.0 Backup + DR** (`archive/gofuture/16`): inkrementelle Backups, S3/NFS/Restic,
  Live-Restore, Single-File-Restore, Cross-Site Replication.
- **GoFuture 7.3.1 SDN + Firewall** (`archive/gofuture/17`): VLAN/VXLAN, Distributed Firewall,
  IPAM, Public-Stream-Reconciliation.
- **GoFuture 7.4.0 OpenAPI v2 + Terraform + `beaglectl`** (`archive/gofuture/18`): Stabilisierung.
- **GoAdvanced 01 / 06 — Datenintegritaet + SQLite-Migration**: atomic writes,
  file locking, JSON->SQLite-Backend.
- **GoAdvanced 02 / 03 — TLS-Haerte + Secret-Rotation**: `curl -k` entfernen,
  Cert-Pinning, Vault-Integration.
- **GoAdvanced 04 — Subprocess-Sandboxing**: `run_cmd_safe()`, Argument-Validation.
- **GoAdvanced 05 — Control-Plane-Split**: 6000+-LOC-Monolith zerlegen.
- **GoAdvanced 07 — Async-Job-Queue**.
- **GoAdvanced 08 — Observability**: Prometheus `/metrics`, strukturierte Logs, Tracing.
- **GoAdvanced 10 — Integration-Tests**: Boot->Enrollment->Streaming, Backup->Restore E2E.
- **GoAdvanced 12 — UX/Accessibility**: i18n, ARIA, mobile.
- **GoRelease R3/R4-Gates**: alle "Nicht-verhandelbaren-Gates" aus
  `archive/gorelease/00-index.md` muessen reproduzierbar gruen sein, externer
  Security-Review/Pentest steht aus.

### Bekannte Doku-/Repo-Hygiene-Schulden

- In einigen aelteren Plan-Texten ist eine globale Stringersetzung aktiv,
  die "Proxmox" durch "Beagle host" und `proxmox-ui/` durch `beagle-ui/`
  ersetzt hat. Das verfaelscht Loesch-Direktiven (z. B. "Beagle host wird
  dauerhaft entfernt"). Faktisch gemeint und faktisch bereits umgesetzt
  ist die Entfernung von **Proxmox**. Beagle Host (`beagle-host/`) ist die
  aktive Control-Plane und bleibt. Betroffene Dateien werden im Rahmen von
  Plan `archive/gofuture/05-provider-abstraction.md` schrittweise textuell korrigiert.

---

## 5. Kanonische Reihenfolge ab jetzt

1. **GoEnterprise 8.x abschliessen** (Plan 01 Fork, 02 Restpunkte, 03, 06, 10).
   Dies ist die aktuelle Hauptarbeitslinie. Jeder Schritt: Code im Repo, Test
   lokal, Live-Validierung auf `srv1.beagle-os.com` / `srv2.beagle-os.com`,
   Checkbox setzen, `05-progress.md` ergaenzen.
2. **GoFuture 7.x in der Reihenfolge 08 -> 09 -> 10 -> 11 -> 12 -> 13 -> 14 -> 15 -> 16 -> 17 -> 18**.
   Storage- und HA-Plane sind Voraussetzung fuer VDI-Pools und Streaming v2.
3. **GoAdvanced parallel als Nebenbedingung**: bei jeder Plattform-Aenderung
   die zugehoerigen Hardening-Tickets (Atomic Writes, TLS, Secrets, Sandbox,
   Observability) mitziehen, statt sie ans Ende zu schieben.
4. **GoRelease-Gates kontinuierlich pflegen**: Release-Artefakte (`latest`),
   SBOM/Checksumme/Signatur, Clean-Install/Update/Rollback-Runbooks,
   Pentest-Vorbereitung; R3 ist das naechste Release-Ziel.
5. **Refactorv2 ist Vision/Architekturreferenz** und liefert keine eigenen
   Tickets; tatsaechliche Tickets stehen in den Plaenen oben.

---

## 6. Querschnittsregeln (gelten fuer alle Plaene)

- Kein Big Bang. Jede Aenderung haelt den Build stabil.
- Code-First: zuerst implementieren, dann kurz dokumentieren.
- Beagle Web Console (`website/`) ist die einzige Operator-Oberflaeche; ein
  Schritt ist erst fertig, wenn er in der WebUI bedienbar, getestet und auf
  `srv1`/`srv2` validiert ist.
- Nur ein Provider: `providers/beagle/`. Kein neuer Code mit `qm`, `pvesh`,
  `/api2/json`, `PVEAuthCookie` oder Proxmox-Pfaden.
- Security ist Nebenbedingung jedes Runs. Funde gehen sofort nach
  `docs/refactor/11-security-findings.md`; im Scope wird mitgepatcht.
- Keine Klartext-Secrets in versionierten Dateien.
- Provider-Neutralitaet: zuerst `core/`-Contract erweitern, dann
  `providers/beagle/` implementieren, dann Service umstellen.
- Pflicht-Doku nach jedem groesseren Schritt:
  - `[x]` im zugehoerigen Plan setzen,
  - `docs/refactor/05-progress.md` ergaenzen,
  - `docs/refactor/06-next-steps.md` aktualisieren,
  - `docs/refactor/08-todo-global.md` aktualisieren,
  - bei Architekturentscheidungen `docs/refactor/07-decisions.md`,
  - bei Provider-Grenzen `docs/refactor/09-provider-abstraction.md`,
  - bei Security-Beruehrung `docs/refactor/11-security-findings.md`,
  - dieses Master-Dokument bei Veraenderung der Themen-Zuordnung oder
    Prioritaetsreihenfolge.

---

## 7. Agent-Einstieg in 30 Sekunden

1. Dieses Dokument lesen (Themen-Zuordnung in Abschnitt 3, Reihenfolge in
   Abschnitt 5).
2. Letzten "Stand"-Block in `docs/refactor/06-next-steps.md` lesen.
3. Naechsten Punkt aus Abschnitt 5 hier nehmen, im kanonischen Plan die
   naechste offene `[ ]`-Checkbox waehlen.
4. Code-Aenderung implementieren, lokal testen, auf `srv1.beagle-os.com`
   live verifizieren (bei Runtime-Bezug auch `srv2.beagle-os.com`).
5. Checkbox `[x]` setzen, Logbuecher (5/6/8) und ggf. 7/9/11 aktualisieren.
6. Falls dieser Plan sich aendern muss (neue Ueberlappung, neuer kanonischer
   Plan, andere Prioritaet): Abschnitt 3 oder 5 hier patchen — nicht in
   einem der Teilplaene heimlich.

---

## 8. Aenderungsregeln fuer dieses Dokument

- Aenderungen an Abschnitt 3 (Themen-Zuordnung) oder Abschnitt 5 (Reihenfolge)
  sind Architektur-Entscheidungen und werden zusaetzlich in
  `docs/refactor/07-decisions.md` notiert.
- Eintraege in Abschnitt 4 (Ist-Stand) werden nur dann von "offen" auf
  "erledigt" verschoben, wenn der zugehoerige Detailplan komplett `[x]` ist
  oder im zugehoerigen Service-/Test-Code reproduzierbar gruen ist.
- Dieses Dokument ist **knapp**. Detailbegruendungen, Schrittlisten und
  Acceptance-Tests bleiben in den Detailplaenen.
