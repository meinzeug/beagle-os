# 00 — Vision 7.0

Stand: 2026-04-20

## Nordstern

Beagle OS 7.0 ist die **erste Open-Source-Plattform**, die in einer einzigen, eigenstaendigen Distribution liefert:

1. einen **Hypervisor-Stack** auf KVM/QEMU + libvirt mit Cluster-, HA- und Live-Migration
2. eine **Desktop-Virtualisierungs-Plane** (VDI) mit Pools, Templates, Persistent- und Non-Persistent-Desktops
3. eine **Streaming-Plane pro Desktop-VM** auf Sunshine/Apollo + Moonlight (HDR, multi-monitor, virtual display)
4. ein **Endpoint-OS** fuer Thin Clients (Linux + Moonlight + Kiosk)
5. eine **eigene Web Console** als einzige Operator-/User-Oberflaeche
6. ein **Bare-Metal-Installer** fuer Standalone- und Hybrid-mit-Beagle host-Mode
7. eine **API-/IaC-Schicht** mit Terraform-Provider, OpenAPI und Webhooks
8. ein **Identity-/Mandanten-Modell** mit lokaler IdP, OIDC, SAML, SCIM und Directory-Sync

## Positionierung

Beagle OS 7.0 ist **nicht**:

- ein reines Hypervisor-Produkt (Beagle host, XCP-ng, Harvester) — es ist mehr.
- ein reines VDI-Brokering-Produkt (Omnissa Horizon, Citrix DaaS) — es bringt den Hypervisor mit.
- ein reines Streaming-Produkt (Parsec, Sunshine, Moonlight) — Streaming ist Teil des VM-Lifecycles, nicht ein angeflanschter Daemon.
- ein reines Cloud-PC-Produkt (Windows 365, Shadow, Vagon) — laeuft on-prem und edge ohne Cloud-Abhaengigkeit.

Beagle OS 7.0 ist die **Konvergenz** dieser vier Welten:

```
+--------------------------------------------------------------+
| Beagle Web Console (single pane of glass)                    |
+--------------------------------------------------------------+
| IAM / Tenancy / Policy / Audit                               |
+--------------------------------------------------------------+
| VDI Plane: Pools, Templates, Profiles, Entitlements          |
+--------------------------------------------------------------+
| Streaming Plane: Sunshine/Apollo/Moonlight, HDR, vDisplay    |
+--------------------------------------------------------------+
| Compute Plane: KVM/QEMU + libvirt + clustering + HA          |
+--------------------------------------------------------------+
| Storage / Network / GPU / Backup Planes                      |
+--------------------------------------------------------------+
| Bare-Metal Beagle Server OS (Debian-basiert) + Installer     |
+--------------------------------------------------------------+
                |                          |
+----------------------+      +----------------------------+
| Beagle Endpoint OS   |      | Beagle Web Console (Admin)|
| (Thin Client + KIOSK)|      | + Beagle Web Portal (User)|
+----------------------+      +----------------------------+
```

## Produktversprechen 7.0

Ein Operator soll innerhalb von **30 Minuten** vom Bare-Metal-Server zu einem ersten gestreamten Desktop kommen:

1. ISO booten, Beagle Server OS installieren (10 min).
2. Web Console oeffnen, Admin anlegen, optional OIDC verbinden (5 min).
3. Golden-Image-Template anlegen oder Beispiel-Profil "Ubuntu 24.04 + XFCE + Sunshine" waehlen (2 min).
4. Desktop-Pool von 1 - N Plaetzen erzeugen, GPU-Profil setzen, User/Gruppe entitleten (3 min).
5. Endpoint-Image herunterladen und auf USB schreiben, Thin Client booten, Pairing per Code (10 min).
6. Stream laeuft, Audio/USB/Mikro durchgereicht, Session wird auditiert.

Ein User soll **per Browser** oder **per Beagle Endpoint OS** den eigenen Desktop ueber denselben Login bekommen — aus dem Office, Home Office oder Edge-Standort.

## Erfolgskriterien

| Kategorie | Messpunkt | Zielwert 7.0 |
|---|---|---|
| Onboarding | First-Desktop-Time auf neuem Bare Metal | <= 30 min |
| Streaming | E2E-Latenz LAN | <= 25 ms |
| Streaming | Aufloesung pro Stream | bis 4K60 HDR |
| Streaming | Parallele Streams pro Host (CPU-encode) | >= 4 |
| Cluster | Live-Migration zweier laufender VMs | unterbrechungsfrei |
| HA | Recovery-Time eines verlorenen Knotens | <= 2 min |
| Backup | Inkrementelles Tages-Backup pro Desktop | <= 5 min |
| IAM | OIDC-Login + RBAC | aktiv |
| API | Terraform-Provider mit VM/Pool/User-CRUD | aktiv |
| Security | Audit-Log fuer 100% mutierender Endpunkte | erfuellt |

## Was sich nicht aendert

- AGPL/MIT-konforme Open-Source-Strategie.
- Provider-Neutralitaet (Beagle host bleibt **optionaler** Provider).
- Bestehende Repo-Struktur bleibt; Welle 2 baut **innerhalb** der bestehenden Module aus.
- Streaming bleibt **first-class** und ist nicht hinter Plug-in versteckt.
- Bare-Metal-Installer bleibt single-source-of-truth fuer reproduzierbare Hosts.
