# 01 — Konkurrenzanalyse

Stand: 2026-04-20

Quellen: offizielle Hersteller-Seiten und Doku (Beagle host, Omnissa, Citrix, Microsoft Learn, Parsec, BeagleStream Server, ClassicOldSong/Apollo, Kasm, Harvester, OpenStack, Wikipedia: Comparison of platform virtualization software).

## Marktsegmente

Wir konkurrieren **nicht** in nur einem Markt. Beagle OS sitzt zwischen vier Segmenten:

1. **Open-Source-Hypervisor-Plattformen**: Beagle host, XCP-ng/Citrix Hypervisor, Harvester HCI, OpenStack, OpenShift Virtualization (KubeVirt), oVirt.
2. **Enterprise-VDI-Plattformen**: Omnissa Horizon (ex-VMware), Citrix DaaS / Virtual Apps and Desktops.
3. **Cloud-PC-/DaaS-Anbieter**: Microsoft Windows 365, Azure Virtual Desktop, Amazon WorkSpaces, Shadow, Vagon, Cameyo.
4. **Niedrig-Latenz-Streaming-Stacks**: Parsec / Parsec for Teams, Beagle Stream Server + Beagle Stream Client, Apollo (Beagle Stream Server-Fork) + Artemis, Wolf, NICE DCV.

## Konkurrenten im Detail

### Beagle host

- **Stark**: KVM + LXC, multi-master Cluster ueber pmxcfs/Corosync, integriertes HA, Live-Migration, Ceph-HCI, vzdump-Backups + Beagle host Backup Server (inkrementell, Live-Restore, Single-File-Restore), SDN-Stack mit VLAN/QinQ/VXLAN/EVPN, Distributed Firewall, mehrere Auth-Realms inkl. AD/LDAP/OIDC, AGPLv3.
- **Schwach**: Kein nativer Desktop-Streaming-Stack, kein Pool-/Template-Modell fuer VDI, kein Endpoint-OS, UI ist ExtJS-Operator-orientiert (kein User-Portal).

### XCP-ng / Citrix Hypervisor

- **Stark**: Reifer Xen-Hypervisor, Live-Migration, Storage-XenMotion, ueber Xen Orchestra eigene Web-UI mit Backups und Replication.
- **Schwach**: Wie Beagle host kein VDI-Brokering, kein Streaming-First, kein Endpoint-OS.

### Harvester HCI (SUSE/Rancher)

- **Stark**: HCI auf KVM + KubeVirt + Longhorn (verteilt), Kubernetes-nativ, integrierte Bare-Metal-Distribution, integriert mit Rancher.
- **Schwach**: Kein Desktop-/Streaming-Fokus, hoeherer operativer Footprint (Kubernetes + Longhorn).

### OpenStack / OpenShift Virtualization (KubeVirt)

- **Stark**: Riesiger Featureumfang, Mandantenfaehigkeit, Quoten, IaC.
- **Schwach**: Hoher Komplexitaetsoverhead, kein nativer Endpoint-/Streaming-Stack, Lernkurve.

### Omnissa Horizon (ex-VMware)

- **Stark**: Klassische VDI-Architektur (Connection Server, Agent, Client, UAG), Blast-Extreme-Protokoll, Image-Management mit App Volumes, Dynamic Environment Manager, Session-Recording, Granular Policies, AD/Entra-Anbindung, Mehr-Cloud (vSphere, Nutanix AHV, OpenStack, OpenShift, Azure, AWS, GCP).
- **Schwach**: Kommerziell, Lizenzkosten, viele bewegliche Teile (Connection Server, UAG, App Volumes, DEM), keine integrierte Hypervisor-Plane (setzt auf vSphere/AHV/OpenStack/OpenShift).

### Citrix DaaS / Virtual Apps and Desktops

- **Stark**: Marktreferenz fuer VDI/RemoteApps, HDX-Protokoll, Sitzungsaufzeichnung, granulare Policies, on-prem + cloud, MCS/PVS-Image-Management.
- **Schwach**: Lizenzkosten, hohe Komplexitaet, Cloud Software Group / unsichere Roadmap, schmerzhaftes Migrationsverhalten.

### Microsoft Windows 365 / Azure Virtual Desktop

- **Stark**: 1:1 Cloud-PC pro User, Intune-Management, Entra-ID, transparente Provisionierung, Browser- und App-Zugang, Windows 365 Link Thin Client.
- **Schwach**: Nur Cloud, Vendor-Lock-in, Pro-User-Pro-Monat-Kosten, kein on-prem Standalone-Mode, nur Windows-Workloads.

### Parsec for Teams

- **Stark**: extrem niedrige Latenz, P2P-verschluesselt, Wacom/Multi-Monitor/4:4:4, Teamverwaltung, SSO, SCIM, Watermarks.
- **Schwach**: Nur Streaming-Layer, kein Hypervisor, kein VDI-Brokering, kein Self-Hosting (SaaS), Windows/macOS-Hosts only.

### BeagleStream Server

- **Stark**: Open Source (GPLv3), Beagle Stream Client-Protokoll, NVENC/QSV/VAAPI/AMF, Linux/Win/macOS, web UI, Pairing.
- **Schwach**: Pro Host-Daemon-zentrisch, kein Pool-Modell, kein Hypervisor, kein VDI, virtual display nur eingeschraenkt.

### Apollo (Beagle Stream Server-Fork) + Artemis (Beagle Stream Client-Fork)

- **Stark**: Built-in Virtual Display mit HDR und auto-resolution-matching, Per-Client-Permissions, Clipboard-Sync, Auto-pause/resume, Multi-Instance.
- **Schwach**: Windows-only Virtual Display, nicht zentral verwaltbar (pro Host), keine Plattform-Backplane.

### Kasm Workspaces

- **Stark**: Container- und VM-basierte Workspaces im Browser (HTML5/WebRTC/KasmVNC), Mandanten, RBAC, App-Streaming, Zero-Trust-Entry.
- **Schwach**: Browser-zentriert (kein nativer Low-Latency-Client wie Beagle Stream Client), Container-first (VM ist nachgelagert), kommerzieller Kern.

### NICE DCV / Amazon WorkSpaces

- **Stark**: Reife Pixel-Streaming, GPU/Headless-Linux, AWS-Integration.
- **Schwach**: Cloud-Lock-in oder Lizenzkosten.

### Cameyo / Vagon / Shadow

- **Stark**: App-Streaming bzw. Cloud-Gaming-Desktops, einfache User-Erfahrung.
- **Schwach**: SaaS-only, kein on-prem.

## Feature-Matrix (Kurzform)

Legende: V=Vorhanden, T=Teilweise, F=Fehlt.

| Feature | Beagle 6.7 | Beagle 7.0 (Ziel) | Beagle host | XCP-ng | Harvester | Omnissa Horizon | Citrix DaaS | Win 365 | Parsec Teams | Beagle Stream Server/Apollo | Kasm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| KVM/QEMU Hypervisor | V | V | V | (Xen) | V | F | F | F | F | F | T |
| Multi-Node Cluster | F | V | V | V | V | n/a | n/a | n/a | n/a | F | T |
| Live-Migration | F | V | V | V | V | n/a | n/a | n/a | n/a | F | T |
| HA-Manager | F | V | V | V | V | n/a | n/a | n/a | n/a | F | T |
| Verteiltes Storage (Ceph/Longhorn) | F | V (opt.) | V | V | V | n/a | n/a | n/a | n/a | F | T |
| Eigene SDN/VLAN/VXLAN | T | V | V | V | V | n/a | n/a | n/a | n/a | F | T |
| Distributed Firewall | F | V | V | V | T | n/a | n/a | n/a | n/a | F | T |
| Backup + Inkrementell + Live-Restore | F | V | V (PBS) | V | T | n/a | n/a | n/a | n/a | F | F |
| Pool- und Template-Mgmt fuer Desktops | T | V | F | F | F | V | V | V | T | F | V |
| Streaming-First pro VM | V | V | F | F | F | V (Blast) | V (HDX) | V (RDP/AVD) | V (Parsec) | V (Beagle Stream Client) | T (Web) |
| HDR / Multi-Monitor / 4:4:4 | F | V | F | F | F | V | V | V | V | T | F |
| Virtual Display + Auto-Res | F | V | F | F | F | V | V | V | T | V (Apollo) | F |
| Eigenes Endpoint-/Thin-Client-OS | V | V | F | F | F | (IGEL Partner) | (IGEL Partner) | V (Win 365 Link) | F | F | F |
| GPU-Passthrough + vGPU | T | V | T | T | T | V | V | V | n/a | n/a | T |
| USB-Redirect + Wacom + Audio In/Out | T | V | F (manuell) | F | F | V | V | V | V | T | T |
| Mandanten + SSO (OIDC/SAML) + SCIM | T | V | T | T | T | V | V | V | V | F | V |
| Session-Recording / Watermark | F | V | F | F | F | V | V | T | V (Watermark) | F | T |
| Audit-Log alle Mutationen | T | V | V | V | V | V | V | V | V | F | V |
| Terraform / IaC | F | V | T (community) | V | T | V | V | V | T | F | T |
| Bare-Metal-ISO-Installer | V | V | V | V | V | F | F | F | F | F | F |
| Open Source Lizenz | V (MIT) | V | V (AGPL) | V (GPL) | V (Apache) | F | F | F | F | V (GPL) | T |

## Kerneinsicht

- Niemand sonst liefert **alle vier Schichten in einem Produkt** (Hypervisor + VDI + Streaming + Endpoint-OS).
- Beagle host + Beagle Stream Server + IGEL + Active Directory ist heute der naheliegendste DIY-Stack — Beagle OS 7.0 macht das zu einem einzigen integrierten Produkt.
- Der schnellste Weg zur Konkurrenzfaehigkeit ist **nicht**, alles selbst zu bauen, sondern bestehende reife OSS-Bausteine zu integrieren (libvirt, Corosync/Pacemaker, Longhorn/Ceph, Apollo/Beagle Stream Server, OpenID Connect, OpenTelemetry).
