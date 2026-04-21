# 03 — Zielarchitektur 7.0

Stand: 2026-04-20

Erweitert die Zielarchitektur aus `docs/refactor/02-target-architecture.md` um Cluster, VDI-Pools und Multi-Node-Plattform.

## Schichten

```
+----------------------------------------------------------------------------+
|  Beagle Web Console (Operator + User Portal)                                |
|  Beagle CLI (beaglectl)  |  Terraform Provider  |  Webhooks  |  OpenAPI    |
+----------------------------------------------------------------------------+
|  API Gateway (Auth, Rate-Limit, Audit, RBAC, Tenancy)                       |
+----------------------------------------------------------------------------+
|  Identity Plane                                                              |
|   - Local IdP                                                                |
|   - OIDC / SAML / SCIM                                                       |
|   - Tenants / Roles / Policies                                               |
+----------------------------------------------------------------------------+
|  Domain Services (beagle-host/services/)                                     |
|   - Compute    - DesktopPool   - Streaming   - Storage   - Network          |
|   - GPU        - Cluster       - HA          - Backup    - Session          |
|   - Audit      - Task          - Event       - Update    - Metrics          |
+----------------------------------------------------------------------------+
|  Platform Contracts (core/)                                                  |
|   - virtualization, provider, platform, authz, task, event                  |
+----------------------------------------------------------------------------+
|  Provider Adapters (providers/)                                              |
|   - beagle (libvirt + KVM/QEMU + nft + zfs/ceph/longhorn) -- DEFAULT        |
|   - proxmox (qm/pvesh) -- OPTIONAL                                          |
+----------------------------------------------------------------------------+
|  Beagle Server OS (Debian-basierte Distro mit beagle-host vorinstalliert)   |
+----------------------------------------------------------------------------+
                |
        +---------------------+
        |   Cluster Fabric    |  Corosync/etcd-aequivalent + verschluesselte
        |   (multi-node)      |  inter-node API + shared config store
        +---------------------+
                |
        +---------------------+      +---------------------+
        |   Beagle Endpoint   |      |   Beagle Endpoint   |
        |   OS (Thin Client)  | ...  |   OS (Thin Client)  |
        |   Moonlight + Auto- |      |   Moonlight + Auto- |
        |   Pairing           |      |   Pairing           |
        +---------------------+      +---------------------+
```

## Kernkonzepte

## Web Console Informationsarchitektur (7.0 Leitbild)

Die bestehende Web Console darf fuer 7.0 nicht weiter als lose Sammlung einzelner Panels wachsen. Ab 7.0 wird die UI entlang klarer Plattform-Scopes organisiert, wie man es von Proxmox-, VMware- oder Citrix-aehnlichen Umgebungen erwartet, aber provider-neutral und streaming-orientiert.

### Navigationsprinzip

- **Globaler Scope-Switcher** oben links:
  - Global
  - Datacenter / Cluster
  - Tenant
  - Pool
  - VM
- **Persistente Primärnavigation** links, immer gleich sortiert:
  - Overview
  - Compute
  - Pools
  - Templates
  - Sessions
  - Storage
  - Network
  - Identity
  - Operations
  - Platform Settings
- **Kontextleiste** rechts/oben im Content-Bereich:
  - aktueller Scope,
  - Breadcrumbs,
  - schnelle Aktionen,
  - Health / Alerts / Running Tasks.

### Objektmodell in der UI

Die UI folgt denselben first-class Objekten wie die API:

- `Datacenter`: Einstieg fuer globale Health, Kapazitaet, Alarme, Releases, Cluster-Status.
- `Node`: Host-spezifische Compute-/Storage-/Network-Ansicht, Services, Maintenance, GPU, PCI.
- `Pool`: Skalierungs-, Entitlement- und Session-zentrierte Ansicht fuer VDI/Desktop-Betrieb.
- `Template`: Golden Images, Versionen, Publish/Deprecate, Build-History.
- `VM`: Detailansicht fuer Runtime, Konsole, Netzwerk, Snapshot, Migration, Stream.
- `Session`: aktiver Benutzerkontext mit Stream-Telemetrie, Endpoint, Recording, Policies.
- `StorageClass` und `NetworkZone`: keine versteckten Settings mehr, sondern sichtbare Infrastruktur-Objekte.

### Empfohlene Seitenstruktur

#### 1. Datacenter Dashboard

- Zweck: Proxmox-aehnlicher Gesamtblick auf die Plattform.
- Widgets:
  - Cluster Health,
  - Host-Auslastung,
  - Pool-Kapazitaet,
  - aktive Sessions,
  - laufende Tasks,
  - Alerts / Failed Jobs,
  - Storage Pressure,
  - Network Incidents.

#### 2. Compute

- Unterseiten:
  - Nodes
  - Virtual Machines
  - GPU / PCI Devices
  - Placement / HA
- Tabellen muessen gruppierbar und filterbar sein nach:
  - Tenant,
  - Node,
  - Pool,
  - Power State,
  - Health,
  - Tags.

#### 3. Pools

- Nicht mehr "VM erstellen" als singulaerer Hauptpfad, sondern Pools als primaeres Betriebsobjekt.
- Unterseiten:
  - Pool Directory
  - Entitlements
  - Scaling Policies
  - Session Behavior
  - Pool Activity
- Einzelne VM-Erstellung bleibt moeglich, aber als Experten-Flow unter Compute.

#### 4. Templates

- Template-Katalog mit:
  - OS-Familie,
  - Release,
  - Streaming Backend,
  - GPU-Klasse,
  - Patch-Level,
  - Publish-Status.
- Template-Builds brauchen eigene Task/History-Sicht.

#### 5. Sessions

- Zentral fuer Beagle-Differenzierung gegenueber klassischem Hypervisor-UI.
- Zeigt:
  - User,
  - Endpoint,
  - Pool,
  - VM,
  - Stream-Status,
  - Quality Metrics,
  - Recording/Watermark-Status,
  - Session Policies.

#### 6. Storage und Network

- Aus den heute verstreuten Settings in echte Betriebsbereiche ziehen.
- Storage:
  - Klassen,
  - Kapazitaet,
  - Snapshots,
  - Backups,
  - Replication.
- Network:
  - Zones,
  - Bridges,
  - VLAN/VXLAN,
  - Firewall Profiles,
  - Public Stream Paths.

#### 7. Operations

- Einheitlicher Ort fuer:
  - Tasks,
  - Events,
  - Audit,
  - Backups,
  - Updates,
  - Support Bundles,
  - Maintenance Mode.

### UX-Regeln fuer Skalierbarkeit

- **Listen-first, Drawer-second, Full-page-third**:
  - Listen fuer Massenbetrieb,
  - Side-Drawer fuer Quick Inspect,
  - Vollseiten fuer komplexe Workflows.
- **Aktionen sind objektgebunden**:
  - keine unklaren globalen Buttons ohne Scope,
  - jede Aktion zeigt Zielobjekt, Auswirkung und Rueckrollpfad.
- **Task Center statt versteckter Spinner**:
  - alle long-running Actions in einer persistenten Task-Leiste,
  - jede Task hat Status, Logs, Retry, Fehlerdetail.
- **State-Farben strikt semantisch**:
  - gruen = healthy/running,
  - amber = degraded/pending,
  - rot = failed/blocked,
  - blau = info/in-progress.
- **Settings werden entmonolithisiert**:
  - kein Sammelpanel mehr fuer alles,
  - jede Konfiguration gehoert in den passenden Domain-Bereich.

### Migrationspfad aus der heutigen UI

- Heutige Panels werden wie folgt ueberfuehrt:
  - `overview` -> Datacenter Dashboard,
  - `inventory` -> Compute > Virtual Machines,
  - `virtualization` -> Compute > Nodes / Storage / Network,
  - `provisioning` -> Pools + Compute > Create VM,
  - `policies` -> Pools / Sessions / Identity je nach Policy-Art,
  - `iam` -> Identity,
  - `settings_*` -> Platform Settings oder jeweilige Domain.
- Die erste 7.0-Umsetzung soll die bestehende JS-App nicht sofort ersetzen, sondern ihre Panels in diese Informationsarchitektur umhaengen.

### Cluster

- Genau **eine logische Beagle-Cluster-Instanz** pro Deployment.
- Jeder Knoten faehrt dieselbe `beagle-control-plane`, eines der Mitglieder ist Leader (Raft-Election ueber etcd-aequivalent oder einfache leader-lease in SQLite-litestream).
- Konfig-/IAM-/Pool-/Entitlement-State liegen im **Cluster-Store**, nicht pro Host.
- Provider-Operationen (start_vm, migrate_vm) werden vom Leader an den zustaendigen Host geroutet.

### Desktop Pools

Neuer first-class Domain-Type. Schema (vereinfacht):

```yaml
DesktopPool:
  id: pool-engineering
  tenant: acme
  template: tmpl-ubuntu-2404-xfce-sunshine
  mode: persistent | floating | dedicated
  capacity:
    min: 1
    max: 50
    spare: 2
  resources:
    cores: 4
    memory_mb: 8192
    disk_gb: 80
    gpu_class: nvidia-l4-1g
  network:
    vnet: tenant-acme-vnet
    firewall_profile: desktop-default
  streaming:
    backend: apollo
    max_resolution: 4K
    hdr: true
    multi_monitor: 2
    encoder_pref: nvenc
  policies:
    clipboard: bidirectional
    usb: allow:hid,mass_storage
    watermark: "{{user.email}} {{timestamp}}"
    session_recording: on_demand
  entitlements:
    - groups: [engineering]
    - users: [alice@acme.example]
```

### Templates

Templates sind versionierte qcow2-Backing-Images plus Provisioning-Profile (`templates/ubuntu-beagle/`). 
Live-Build: Template wird aus laufender VM via Snapshot eingefroren -> Sysprep/Cloud-Init-reset -> Backing-Image fuer Linked Clones.

### Streaming-Sessions

Eine **Session** ist ein first-class Object:

```yaml
Session:
  id: sess-...
  user: alice@acme.example
  tenant: acme
  desktop_vm: 142
  pool: pool-engineering
  endpoint: thin-client-7c2a
  protocol: moonlight
  encoder: nvenc
  resolution: 3840x2160@60
  hdr: true
  start_at: ...
  end_at: ...
  audit:
    recording_uri: s3://...
    watermark_applied: true
  health:
    rtt_ms: 18
    pkt_loss_pct: 0.1
    encoder_fps: 60
```

### Tenants

- Top-level Mandanten-Namespace.
- Pools, Users, Templates, Storage-Klassen koennen tenant-scoped sein.
- Globale Operatoren ueberspannen Tenants.

### Storage-Klassen

```yaml
StorageClass:
  id: sc-fast-local
  provider: zfs
  pool: tank/desktops
  thin: true
  snapshot_policy: hourly:24, daily:7, weekly:4
  quota_gb_per_vm: 200
```

## Abgrenzung zu Welle 1

- Welle 1 hat **eine** Beagle-Host-Instanz produktiv gemacht.
- Welle 2 oeffnet die Architektur fuer **mehrere Hosts in einem Cluster** und **viele Desktops in Pools** ohne Provider-Lock-in.

## Datenmodell-Skizze

Neue Domain-Tabellen (wo sie implementiert werden, ist Implementation Detail):

- `cluster_node`
- `desktop_pool`
- `desktop_template`
- `entitlement`
- `tenant`
- `storage_class`
- `network_zone`
- `firewall_profile`
- `session`
- `session_recording`
- `gpu_device`
- `backup_job`
- `backup_artifact`
- `audit_event` (existiert grundsaetzlich, wird normalisiert)

## API-Konvention

- Alle neuen Routen unter `/api/v2/...`.
- `/api/v1/...` bleibt fuer 7.0 stabil (read + bestehende Mutationen).
- Versionierte Contracts in `core/` (kein Bruch ohne neuen Major).
