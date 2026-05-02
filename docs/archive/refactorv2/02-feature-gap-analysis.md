# 02 — Feature-Gap-Analyse

Stand: 2026-04-20

Basis: aktueller Repo-Stand (6.7.0) plus `docs/refactor/02-target-architecture.md` und Konkurrenzanalyse [01-competitor-research.md](01-competitor-research.md).

## Was Beagle OS heute schon kann

- Bare-Metal-Server-Installer (`server-installer/live-build`, `scripts/build-server-installer.sh`).
- Hetzner-`installimage`-Tarball (`scripts/build-server-installimage.sh`).
- Beagle-Host Control Plane in Python (`beagle-host/bin/beagle-control-plane.py`) mit Services unter `beagle-host/services/`.
- Provider-Neutralitaet ueber `core/provider`, `core/virtualization`, `providers/beagle`, `providers/beagle-host`, `beagle-host/providers/`.
- VM Lifecycle (create/start/stop/delete/resume) ueber `HostProvider`-Vertrag fuer Libvirt und Beagle host.
- Provisioning-Flow fuer Ubuntu Desktop + XFCE + Beagle Stream Server ueber `services/ubuntu_beagle_provisioning.py` und `templates/ubuntu-beagle/*`.
- noVNC-Zugriff ueber `services/vm_console_access.py` mit guest-side `x11vnc`-Praeferenz.
- Tokenisierter noVNC-Proxy ueber `beagle-host/systemd/beagle-novnc-proxy.service`.
- Lokales Identity + Onboarding + Session-Service (`services/auth_session.py`).
- Endpoint-OS (`beagle-os/`, `thin-client-assistant/`) inkl. Live-USB-Builder.
- Public Update- und Artifact-Verteilung ueber `scripts/publish-public-update-artifacts.sh`.
- Beagle Web Console (`website/`) als eigene Operator-Oberflaeche.

## Was fehlt fuer 7.0 (Allmacht)

Sortiert nach Prioritaet fuer den Versionssprung 7.0.

### P0 — ohne diese Punkte ist 7.0 keine echte Plattform

1. **Cluster und Live-Migration**
   - Mehrere Beagle-Hosts in eine Kontrollgruppe bringen.
   - Geteiltes Konfig-Image und Quorum (Corosync/etcd/SQLite-Replication-Variante).
   - libvirt-managed Live-Migration zwischen Hosts (shared storage oder block-pull).
   - Single-Pane-of-Glass in der Web Console fuer alle Knoten.

2. **HA-Manager**
   - Watchdog-basiertes Fencing.
   - Restart-Politik pro VM/Pool.
   - Maintenance-Mode pro Host (drain).
   - Anti-Affinity / Affinity Rules.

3. **Storage-Plane**
   - Klare Pool-Abstraktion (LVM, Directory, ZFS, NFS, Ceph RBD, Longhorn).
   - Storage-Klassen mit IOPS-/Quota-/Snapshot-Policy.
   - Snapshots, Linked Clones, Templates ueber alle Pools einheitlich.
   - Thin Provisioning + TRIM-Lifecycle.

4. **Pool- und Template-Modell fuer Desktops (VDI)**
   - "Golden Image" als first-class object.
   - Persistent Desktops (1:1 wie Cloud PC) und Non-Persistent Pools (Floating).
   - Instant-Clone mit Linked Clones (z.B. ueber qcow2 backing files).
   - Profile-Layer fuer Userdaten (FSLogix-aequivalent fuer Linux: bind-mounts auf User-Volume).
   - Entitlements pro User/Gruppe/Pool.

5. **Streaming-Plane v2**
   - Apollo-/Beagle Stream Server-Integration mit virtual display, HDR, Multi-Monitor, 4:4:4.
   - Encoder-Auswahl pro VM-Profil (NVENC/QSV/VAAPI/AMF/Software).
   - Auto-Pairing mit signiertem Token aus Web Console (kein manueller PIN-Tanz).
   - Audio-In + Mikro + Wacom + Gamepad-Redirect dokumentiert und getestet.

6. **IAM v2**
   - OIDC- und SAML-Login (Keycloak-, Authentik-, Entra-ID-, Google-tested).
   - Directory-Sync ueber SCIM 2.0.
   - Mandanten (Tenants) mit eigenem Pool-, User-, Quota-Scope.
   - Granulare Policies (clipboard, USB-redirect, watermark) pro User/Gruppe.

7. **Audit + Session Recording**
   - Audit-Eintrag fuer 100% mutierender API-Endpunkte (heute teilweise).
   - Optionales Session-Recording per VM/Pool-Policy (libvirt screenshots oder x11vnc-record).
   - Watermark-Overlay im Stream (Apollo-Plug-in oder guest-side).

8. **Backup + DR**
   - Inkrementelle Backups pro VM (qcow2-deltas, ZFS-Snapshots, Ceph-RBD-Snapshots).
   - Externes Backup-Ziel (S3, Restic, PBS-kompatibel).
   - Retention-Policy + Garbage Collection.
   - Live-Restore wie PBS.
   - Single-File-Restore aus Backup-Image.
   - Cross-Site Replication.

### P1 — wichtig fuer Wettbewerbsfaehigkeit

9. **Netzwerk-Plane v2**
   - SDN-Module fuer VLAN, VXLAN, einfaches EVPN.
   - Mikrosegmentierung mit Distributed Firewall (nftables-basiert).
   - Per-VM IP-Allocation und IPAM.
   - Public-Stream-Reconciliation bleibt, aber als Teil der SDN-Plane.

10. **GPU-Plane**
    - Vollstaendige PCI-Passthrough-Workflows (vfio-pci, IOMMU-Group-Mapping).
    - vGPU (NVIDIA Mediated Devices, Intel SR-IOV) sofern hardwareseitig vorhanden.
    - GPU als first-class Pool-Constraint (Pool A braucht GPU-Klasse X).
    - Encoder-Reservierung im Scheduler.

11. **API + IaC**
    - Stabile, versionierte OpenAPI-Spec.
    - Terraform-Provider (Resources: `beagle_vm`, `beagle_pool`, `beagle_template`, `beagle_user`, `beagle_entitlement`).
    - Webhooks fuer VM/Pool/Session-Events.
    - CLI (`beaglectl`).

12. **Observability**
    - Prometheus-Endpoint pro Host.
    - OpenTelemetry-Tracing in Control Plane.
    - Strukturiertes JSON-Logging mit corelation-id pro Task.
    - Audit-Export in S3/Syslog.

### P2 — Reife- und Polish-Themen

13. **Updates**
    - Cluster-aware rolling upgrades.
    - Zwei-Slot-A/B-Update fuer Endpoint-OS (rauf bis zu OSTree-aehnlich).
    - Signierte Release-Artefakte und automatische Verifikation.

14. **Compliance**
    - SOC2-/ISO27001-vorbereitendes Audit-/Retention-Modell.
    - DSGVO-konformer Export von User-Daten.
    - PII-Schwaerzung in Logs.

15. **Marktplatz**
    - Catalog von Image-Templates (Ubuntu Desktop, Win 11 Dev, Blender Workstation, Gaming Kiosk).
    - Catalog von Endpoint-Profilen (Office Thin Client, Gaming Kiosk, Engineering Workstation).

## Mapping auf Repo-Module

| Gap | betroffene Module |
|---|---|
| Cluster + HA + Live-Migration | `beagle-host/services/cluster_*` (neu), `beagle-host/providers/beagle_host_provider.py`, `core/virtualization/` |
| Storage-Plane | `beagle-host/services/storage_*` (neu), `core/virtualization/` Contracts |
| Pool/Template-Modell | `beagle-host/services/desktop_pool_*` (neu), `services/ubuntu_beagle_provisioning.py` |
| Streaming v2 | `services/beagle_stream_server_integration.py`, `services/public_streams.py`, neue `services/streaming_*` |
| IAM v2 | `services/auth_session.py`, neue `services/identity_oidc.py`, `services/identity_saml.py`, `services/scim_*` |
| Audit + Recording | `services/audit_log.py` (vorhanden), neue `services/session_recording.py` |
| Backup + DR | `services/backup_*` (neu), Storage-Pool-Hooks |
| Netzwerk v2 | `services/sdn_*` (neu), `scripts/reconcile-public-streams.sh`, `core/platform/` |
| GPU-Plane | `services/gpu_inventory.py`, `services/gpu_passthrough.py` (neu) |
| API + IaC | OpenAPI-Generator, neuer `terraform-provider-beagle/` Top-Level-Ordner, `cli/beaglectl/` |
| Observability | `services/metrics_*`, `services/tracing_*` (neu) |
