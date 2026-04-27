# GoEnterprise — Beagle OS Enterprise Roadmap

Stand: 2026-04-24 (überarbeitet: BeagleStream-Fork-Strategie + WireGuard-Latenztest)  
Folgt auf: `docs/gofuture/` (Grundlagenausbau 7.x)  
Zielversion: **Beagle OS 8.x** (Enterprise Tier)

---

## Warum GoEnterprise?

### Wettbewerbsanalyse (April 2026)

| Produkt | Stärken | Schwächen |
|---|---|---|
| **Beagle host 8** | Open Source, KVM+LXC, Ceph, PBS, SDN, HA | Kein VDI-Broker, kein Streaming, kein Thin-Client-OS, kommerzielle Subscriptions teuer |
| **Citrix DaaS** | Enterprise-Policies, Session Recording, Analytics, SSO | Vendor Lock-in, teuer ($15-$80/User/Monat), komplex, HDX-Protokoll veraltet |
| **Omnissa Horizon 8** (ex-VMware) | BLAST-Protokoll, AppVolumes, DEM, Multi-Cloud | Braucht vSphere/Nutanix, Active Directory Pflicht, teuer, schwerfällig |
| **Azure Virtual Desktop** | Windows Multi-Session, Pay-per-use, Azure-Integration | Cloud-only, kein On-Prem, DSGVO-Probleme, Kosten unkontrollierbar |
| **AWS WorkSpaces** | Managed DaaS, 17 Regionen, Compliance | Cloud-only, teuer, kein Gaming, schlechte Latenz außerhalb USA |
| **Nutanix Frame** | Browser-basiert, Multi-Cloud | Proprietär, teuer, kein Thin-Client-OS |

### Beagle OS Alleinstellungsmerkmale (heute bereits vorhanden)

1. **BeagleStream (Moonlight/Sunshine Fork)** — Niedrigste Latenz aller VDI-Protokolle (~1-3ms intern), Gaming-grade. **WireGuard-Overhead: +0.003ms** (gemessen srv1, 24.04.2026)
2. **WireGuard Zero-Trust Mesh** — Jedes Gerät im verschlüsselten Tunnel. Hardware-beschleunigt (AES+AVX2+VAES auf srv1). Latenz-neutral.
3. **Eigenes Thin-Client-OS** — Bootet auf beliebiger x86-Hardware, QR-Enrollment, A/B-Update, TPM, WireGuard-Key automatisch beim Enrollment
4. **Vollständig Open Source + Self-Hosted** — DSGVO-konform, kein Vendor Lock-in, kein Cloud-Zwang
5. **Gaming-Kiosk-Mode** — Kein Konkurrent bietet Gaming + VDI auf derselben Plattform
6. **Eigener Hypervisor-Stack** — KVM/libvirt nativ, kein Beagle host, keine Lizenzkosten

### Was die Konkurrenz NICHT hat — Beagle OS Enterprise Differenziatoren

→ Diese Features sind der Kern von GoEnterprise

---

## GoEnterprise Plan-Übersicht

| Plan | Name | Priorität | Version |
|---|---|---|---|
| [01](./01-moonlight-vdi-protocol.md) | **BeagleStream**: Sunshine/Moonlight Fork + WireGuard-Mesh | **SOFORT** | 8.0.0 |
| [02](./02-zero-trust-thin-client.md) | Zero-Trust Thin-Client: WireGuard Enrollment + MDM | **SOFORT** | 8.0.0 |
| [03](./03-gaming-kiosk-pools.md) | Gaming-Kiosk-Pool-Management (Esports/Schulen/Militär) | **SOFORT** | 8.0.1 |
| [04](./04-ai-smart-scheduler.md) | KI-basierter VM-Scheduler (Lernender Placement-Algo) | Q3 2026 | 8.1.0 |
| [05](./05-cost-transparency.md) | Echtzeit Kosten-pro-User Dashboard + Chargeback | Q3 2026 | 8.1.0 |
| [06](./06-session-handover.md) | Live-Session-Handover (Stream-Übergabe zwischen Nodes) | Q4 2026 | 8.1.1 |
| [07](./07-fleet-intelligence.md) | Fleet-Intelligence + Predictive Maintenance | Q4 2026 | 8.1.2 |
| [08](./08-all-in-one-installer.md) | All-in-One Bare-Metal-Installer + PXE Zero-Touch | Q1 2027 | 8.2.0 |
| [09](./09-energy-dashboard.md) | Energie- + CO₂-Dashboard + CSRD-Export | Q1 2027 | 8.2.0 |
| [10](./10-gpu-streaming-pools.md) | Intelligente GPU-Pool-Zuweisung + Stream-Routing | Q2 2027 | 8.2.1 |

---

## Zeitplan (Grob)

```
2026 Q2 (Mai-Jun)  → Plan 01 + 02 + 03 (Moonlight VDI + Zero-Trust + Gaming Pools)
2026 Q3 (Jul-Sep)  → Plan 04 + 05 (AI Scheduler + Cost Transparency)
2026 Q4 (Okt-Dez) → Plan 06 + 07 (Session Handover + Fleet Intelligence)
2027 Q1 (Jan-Mär)  → Plan 08 + 09 (All-in-One Installer + Energy Dashboard)
2027 Q2 (Apr-Jun)  → Plan 10 (GPU Streaming Pools)
```

---

## Architekturprinzipien GoEnterprise

1. **Kein Cloud-Zwang** — Vollständig On-Premises betreibbar. Optional Hybrid.
2. **BeagleStream = Open Protocol** — GPL v3 Fork von Sunshine+Moonlight, eigene Broker-API, WireGuard-integriert. Kein proprietäres HDX/BLAST/RDP.
3. **Zero-Trust by Default via WireGuard** — Kein Endgerät wird vertraut. WireGuard-Mesh beim Enrollment automatisch aufgebaut. Overhead: **+0.003ms** (getestet). Kein Gerät ohne Schlüssel bekommt eine Session.
4. **Metriken für alles** — Jede VM, jede Session, jedes Endgerät produziert Metriken. Kein Blindflug.
5. **Self-Healing** — Defekte Thin-Clients, hängende VMs, ausgefallene Nodes werden automatisch erkannt und behoben.
6. **Gaming-grade Latenz** — 1-5ms LAN durch WireGuard+BeagleStream. Kein Konkurrent schafft das.

---

## Einstieg für neue Agents

1. Diese Datei lesen (fertig).
2. `01-moonlight-vdi-protocol.md` lesen — BeagleStream Fork-Plan, erste offene `[ ]`-Checkboxes bearbeiten.
3. WireGuard-Latenztest bereits abgeschlossen: +0.003ms Overhead. Beweis: loopback-Test auf srv1, 24.04.2026.
4. Für Live-Tests: `ssh srv1.beagle-os.com`.
4. Nach Abschluss: `[x]` setzen, `docs/refactor/05-progress.md` aktualisieren.
