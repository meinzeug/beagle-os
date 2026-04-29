# Beagle OS Refactor v2 — "Allmaechtig in Desktop-Virtualisierung"

> Kanonische Gesamtübersicht: [`docs/MASTER-PLAN.md`](../MASTER-PLAN.md). Refactor v2 ist Vision/Architekturreferenz, kein eigenständiger Ausführungsplan.

Stand: 2026-04-20
Zielversion: **7.0** (naechster grosser Versionssprung).

## Zweck dieser Dokumente

Dieses Verzeichnis ist die **zweite Refactor-Welle** und definiert, was Beagle OS leisten muss, um als ernsthaftes
Produkt fuer Desktop-Virtualisierung gegen die etablierten Plattformen anzutreten.

Es ersetzt nicht `docs/refactor/` (Welle 1), sondern setzt darauf auf:

- Welle 1 (`docs/refactor/`) hat die Beagle-native Plattformbasis definiert (IAM, Streaming-Lifecycle, Provider-Neutralitaet, beagle-native Compute).
- Welle 2 (`docs/refactorv2/`) macht daraus ein vollwertiges **Desktop-Virtualization-Produkt** mit Konkurrenzfaehigkeit zu Beagle host, Omnissa Horizon, Citrix DaaS, Windows 365, Parsec for Teams, Kasm Workspaces und Harvester HCI.

## Index

| # | Dokument | Inhalt |
|---|---|---|
| 00 | [00-vision.md](00-vision.md) | Produktvision 7.0 und Nordstern |
| 01 | [01-competitor-research.md](01-competitor-research.md) | Konkurrenzanalyse mit Feature-Matrix |
| 02 | [02-feature-gap-analysis.md](02-feature-gap-analysis.md) | Was Beagle OS heute fehlt vs Konkurrenz |
| 03 | [03-target-architecture-v2.md](03-target-architecture-v2.md) | Zielarchitektur 7.0 |
| 04 | [04-roadmap-v2.md](04-roadmap-v2.md) | Versionssprung-Plan in Wellen 7.0 - 7.4 |
| 05 | [05-streaming-protocol-strategy.md](05-streaming-protocol-strategy.md) | Streaming/Protokoll-Roadmap (Sunshine, Apollo, virtual display, HDR, multi-monitor) |
| 06 | [06-iam-multitenancy.md](06-iam-multitenancy.md) | Identitaet, RBAC, SSO/SAML/OIDC, Mandantenfaehigkeit |
| 07 | [07-storage-network-plane.md](07-storage-network-plane.md) | Storage- und Netzwerk-Plattform |
| 08 | [08-ha-cluster.md](08-ha-cluster.md) | Cluster, HA, Live-Migration, Scheduler |
| 09 | [09-backup-dr.md](09-backup-dr.md) | Backup, Restore, Replication, DR |
| 10 | [10-gpu-device-passthrough.md](10-gpu-device-passthrough.md) | GPU-, USB-, Peripherie-Plane |
| 11 | [11-endpoint-strategy.md](11-endpoint-strategy.md) | Thin-Client- und Endpoint-Strategie |
| 12 | [12-security-compliance.md](12-security-compliance.md) | Security, Audit, Compliance, Session Recording |
| 13 | [13-observability-operations.md](13-observability-operations.md) | Telemetrie, Metriken, Tasks, Events, Upgrades |
| 14 | [14-platform-api-extensibility.md](14-platform-api-extensibility.md) | API, SDK, Terraform-Provider, IaC |
| 15 | [15-risks-open-questions.md](15-risks-open-questions.md) | Risiken, Annahmen, offene Punkte |

## Executive Summary

Beagle OS hat heute schon das, was 90 Prozent der Konkurrenz **nicht** hat:

- voll integrierter **Streaming-Lifecycle pro VM** (Sunshine + Moonlight + thin client) als first-class-Feature
- ein **eigenstaendiges Endpoint-OS** (`beagle-os/`, `thin-client-assistant/`) und Installer-Stack
- ein **Bare-Metal-Server-Installer** mit Standalone- und Beagle host-Modus
- ein **Provider-neutrales Service-Modell** (`core/`, `providers/`, `beagle-host/services/`)

Was zur Allmacht im Desktop-Virtualization-Markt fehlt, ist im Wesentlichen:

1. **Cluster-/HA-/Live-Migration** als beagle-native Funktion (heute Single-Node-Fokus).
2. **Pool- und Templating-Modell fuer Desktops** (instant clones, golden images, FSLogix-aequivalent fuer Profile).
3. **GPU-Plane** mit Passthrough, vGPU-Partitioning, Live-Encoder-Auswahl, HDR und Multi-Monitor durchgaengig.
4. **Mandantenfaehigkeit + SSO/SAML/OIDC + Directory-Sync** und granulare Policies pro User/Gruppe/Pool.
5. **Backup/DR** mit inkrementellen Backups, Replication, Live-Restore und Single-File-Restore.
6. **Storage-Plane** mit Pools, Klassen, Quotas, Snapshots, Thin-Provisioning, optional verteilte Storage (Ceph/Longhorn).
7. **Netzwerk-Plane** mit SDN, VLAN, Overlays (VXLAN), Mikrosegmentierung und Distributed Firewall.
8. **Session- und Recording-Security** (Watermarking, Clipboard-/USB-Policy, Session Recording).
9. **API/SDK + Terraform-Provider** fuer Infrastructure-as-Code.
10. **Telemetrie-/Observability-Layer** mit OpenTelemetry, Prometheus-Endpunkt und Audit-Export.

Die Roadmap dazu liegt in [04-roadmap-v2.md](04-roadmap-v2.md) und ist in inkrementelle, build- und runtime-stabile Wellen geschnitten.
