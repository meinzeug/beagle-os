# 04 — Roadmap 7.0

Stand: 2026-04-20

Inkrementelle Wellen, jede einzeln build- und runtime-stabil. Keine Big-Bang-Umbauten. Reihenfolge orientiert sich an [02-feature-gap-analysis.md](02-feature-gap-analysis.md).

## 7.0.0 — "Cluster Foundation"

Ziel: zwei Beagle-Hosts werden ein Cluster mit gemeinsamer Web Console und Live-Migration.

- Cluster-Store (verschluesselt, Leader-Election, persistente State-Replikation).
- Inter-Host RPC (mTLS, gegenseitige Auth ueber Cluster-CA).
- VM-Inventory ueber Knoten hinweg konsolidiert in `services/cluster_inventory.py`.
- Live-Migration (libvirt managed) bei shared storage.
- Web Console: Knoten-Liste, Knoten-Status, "VM auf Knoten X verschieben".
- Cluster-Setup-Assistent in `beagle-server-installer`.

Akzeptanz: zwei Hosts gestartet, Web Console zeigt beide, eine laufende VM wird live von Host A auf Host B migriert.

## 7.0.1 — "Storage Plane"

- Pool-Abstraktion (`StorageClass` Contract in `core/`).
- Beagle-Provider implementiert: directory, lvm-thin, zfs, nfs.
- Optionale Adapter: Ceph RBD, Longhorn.
- Snapshots + Linked Clones einheitlich.
- Quotas pro Tenant/Pool.

Akzeptanz: VM auf zfs-pool, Snapshot, Clone, Restore.

## 7.0.2 — "HA Manager"

- Watchdog-Fencing pro Host.
- Restart-Policies pro VM und pro Pool.
- Maintenance-Mode (drain).
- Anti-/Affinity-Regeln.
- HA-Status in Web Console.

Akzeptanz: Knoten verliert Strom, HA-Manager erkennt das in <= 60 s, VM startet auf gesundem Knoten in <= 60 s.

## 7.1.0 — "VDI Pools + Templates"

- `DesktopTemplate` Contract + Builder (Snapshot -> Sysprep/cloud-init -> Backing-Image).
- `DesktopPool` Contract + Lifecycle (provisioning, scaling, recycling).
- Persistent + Non-Persistent + Dedicated Modi.
- Entitlements (User/Gruppe -> Pool).
- Web Console: Pool-Wizard, Template-Builder.

Akzeptanz: Pool von 5 Floating-Desktops, User loggt sich ein und bekommt einen freien Desktop, Logout recycelt.

## 7.1.1 — "Streaming v2 mit Apollo + Virtual Display"

- Apollo (oder Apollo-Patches in Sunshine) als bevorzugter Backend.
- Virtual Display Linux (Apollo-Roadmap-Konform: SudoVDA-Aequivalent oder DRM-virtual).
- Auto-Pairing per signiertem Token aus Web Console (kein manueller PIN).
- Encoder-Auswahl pro Pool/VM/Profil.
- HDR, Multi-Monitor (2-4), 4:4:4.
- Audio-In, Mikro, Wacom, Gamepad-Redirect end-to-end getestet.
- Stream-Health Telemetrie (rtt, fps, dropped frames) im Session-Object.

Akzeptanz: Apollo-VM streamt 3840x2160@60 HDR mit zwei Monitoren auf Beagle Endpoint OS, Audio in beide Richtungen, Wacom-Druck funktioniert.

## 7.1.2 — "GPU Plane"

- GPU-Inventory (PCI scan, IOMMU group, vendor/model).
- Passthrough-Workflow inkl. Host-Treiber-Detach.
- vGPU (NVIDIA Mediated Devices, Intel SR-IOV) wo Hardware das hergibt.
- Pool-Constraint "gpu_class".
- Scheduler reserviert GPU-Slots.

Akzeptanz: Pool mit `gpu_class: nvidia-l4-1g`, 4 Desktops bekommen je 1 vGPU, 5. Desktop bleibt im Queue.

## 7.2.0 — "IAM v2 + Tenancy"

- OIDC-Login.
- SAML-Login.
- SCIM 2.0 fuer User/Group-Sync.
- Tenant-Scope durchgaengig in allen mutierenden Endpoints.
- Granulare Policy-Engine (clipboard/USB/watermark/recording).

Akzeptanz: Keycloak verbunden, User loggt sich per OIDC ein, bekommt nur seine Tenant-Pools, Watermark-Policy aktiv.

## 7.2.1 — "Session Recording + Watermark"

- Optionales Session Recording per Pool-Policy.
- Watermark-Overlay im Stream (entweder ueber Apollo-Plug-in oder guest-side compositor).
- Recording-Storage mit Retention-Policy.
- Audit-Event "session_recorded" mit Speicherort.

Akzeptanz: Pool mit `session_recording: always`, Session erzeugt mp4 + Audit-Eintrag, Retention loescht nach Policy.

## 7.2.2 — "Audit + Compliance"

- Audit-Event-Schema vereinheitlicht.
- Audit-Export S3 / Syslog / Webhook.
- PII-Schwaerzung-Filter.
- Compliance-Report-Generator (CSV/JSON).

## 7.3.0 — "Backup + DR"

- Inkrementelle Backups (qcow2-deltas, ZFS/Ceph snapshots).
- Backup-Targets: lokal, NFS, S3, Restic, optional PBS-kompatibel.
- Retention + GC.
- Live-Restore.
- Single-File-Restore (guestfs-mount).
- Cross-Site Replication.

Akzeptanz: stuendliche Inkrementelle, Restore einer 80 GB Desktop-VM in <= 5 min, Single-File-Restore aus 7-Tage-altem Backup.

## 7.3.1 — "SDN + Firewall"

- VLAN, VXLAN, optional EVPN-light.
- Distributed Firewall pro VM/Pool/Tenant.
- IPAM pro vnet.
- Public-Stream-Reconciliation als Teil der SDN-Plane.

## 7.4.0 — "API + IaC + CLI"

- OpenAPI v2 stabil.
- Terraform-Provider mit core resources.
- `beaglectl` CLI.
- Webhook-System.

## 7.4.1 — "Observability"

- Prometheus exporter pro Host.
- OpenTelemetry tracing in Control Plane.
- Structured JSON logs mit correlation-id.
- Default Grafana-Dashboards in `docs/observability/`.

## 7.4.2 — "Polish + Marketplace"

- Image-Marketplace (Ubuntu Desktop, Windows 11 Dev, Blender Workstation, Gaming Kiosk, ...).
- Endpoint-Profile-Marketplace.
- Cluster-aware rolling upgrades.
- A/B-Update fuer Endpoint-OS.

## Querschnittsregeln

- Jede Welle bringt:
  - keine Regression in Welle-1-Funktionen,
  - aktualisierte Tests in `scripts/test-*.sh` und `docs/refactor/04-latest-e2e-test-report.md`,
  - aktualisierte Provider-Abstraction-Notes in `docs/refactor/09-provider-abstraction.md`,
  - aktualisierte Security-Findings falls beruehrt (`docs/refactor/11-security-findings.md`).
- Provider-Neutralitaet bleibt Pflicht: jede Welle erweitert zuerst `core/`-Contracts, dann den Beagle-Provider, dann optional Beagle host-Adapter.
