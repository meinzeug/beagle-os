# Beagle OS — Go Future: Vollständiger Entwicklungsplan

Stand: 2026-04-26
**Status: Re-opened — WebUI-Operability-Gap erkannt. Die Plattform-Funktionen existieren teilweise als API/CLI, muessen aber fuer Betreiber vollständig ueber die Beagle Web Console bedienbar werden.**
Sprache: Deutsch  
Format: Abhakbare Schritt-für-Schritt-Listen mit je 10 Erklärungssätzen pro Schritt.

---

## Warum dieser Plan existiert

Beagle OS wächst von einem Thin-Client-Streaming-Stack zu einer vollständigen
Open-Source-Virtualisierungsplattform. Dieser Plan hält fest, **was zu tun ist,
in welcher Reihenfolge und warum** — so dass jeder Entwickler und jeder
KI-Agent sofort anschließen kann, ohne den Kontext erst rekonstruieren zu müssen.

---

## Dateiübersicht

| Datei | Thema | Priorität |
|---|---|---|
| [01-webui-js-module.md](01-webui-js-module.md) | WebUI: app.js → ES-Module aufteilen | **Sofort** |
| [02-webui-css-split.md](02-webui-css-split.md) | WebUI: styles.css → Teilmodule | **Sofort** |
| [03-webui-index.md](03-webui-index.md) | WebUI: index.html aktualisieren | **Sofort** |
| [04-control-plane.md](04-control-plane.md) | beagle-host Control Plane aufräumen | Welle 6.x |
| [05-provider-abstraction.md](05-provider-abstraction.md) | Provider-Seam vollständig sauber ziehen | Welle 6.x |
| [06-server-installer.md](06-server-installer.md) | Server-Installer / Bare-Metal ISO | Welle 6.x |
| [07-cluster-foundation.md](07-cluster-foundation.md) | 7.0.0 Cluster Foundation | 7.0 |
| [08-storage-plane.md](08-storage-plane.md) | 7.0.1 Storage Plane | 7.0 |
| [09-ha-manager.md](09-ha-manager.md) | 7.0.2 HA Manager | 7.0 |
| [10-vdi-pools.md](10-vdi-pools.md) | 7.1.0 VDI Pools + Templates | 7.1 |
| [11-streaming-v2.md](11-streaming-v2.md) | 7.1.1 Streaming v2 Apollo + vDisplay | 7.1 |
| [12-gpu-plane.md](12-gpu-plane.md) | 7.1.2 GPU Plane (Passthrough + vGPU) | 7.1 |
| [13-iam-tenancy.md](13-iam-tenancy.md) | 7.2.0 IAM v2 + Mandantenfähigkeit | 7.2 |
| [14-session-recording.md](14-session-recording.md) | 7.2.1 Session Recording + Watermark | 7.2 |
| [15-audit-compliance.md](15-audit-compliance.md) | 7.2.2 Audit + Compliance-Export | 7.2 |
| [16-backup-dr.md](16-backup-dr.md) | 7.3.0 Backup + Disaster Recovery | 7.3 |
| [17-sdn-firewall.md](17-sdn-firewall.md) | 7.3.1 SDN + Distributed Firewall | 7.3 |
| [18-api-iac-cli.md](18-api-iac-cli.md) | 7.4.0 OpenAPI + Terraform + beaglectl | 7.4 |
| [19-endpoint-os.md](19-endpoint-os.md) | Endpoint OS / Thin Client Evolution | kontinuierlich |
| [20-security-hardening.md](20-security-hardening.md) | Security Hardening (alle Phasen) | kontinuierlich |

---

## Aktive Re-Open-Punkte (2026-04-26)

- [ ] Cluster-Operations in der WebUI vollständig machen: Cluster erstellen, Server hinzufügen, Join-Token erzeugen, bestehenden Server beitreten lassen, Member verwalten, Drain/Maintenance und Validierung auf `srv1`/`srv2` aus der WebUI heraus ausführen. Detailplan: [07-cluster-foundation.md](07-cluster-foundation.md) Schritt 7.
- [ ] `/#panel=virtualization` überarbeiten: Nodes, Storage, Bridges, GPU/vGPU/SR-IOV und VM-Inspector bedienbar statt nur tabellarisch anzeigen. Detailpläne: [08-storage-plane.md](08-storage-plane.md) Schritt 7 und [12-gpu-plane.md](12-gpu-plane.md) Schritt 6.
- [ ] Host-/Release-Artefakte in der WebUI bedienbar machen: Artifact-Status, fehlende Downloads, Refresh/Build starten, Job-Fortschritt sehen, Fehler auswerten. Detailplan: [06-server-installer.md](06-server-installer.md) Schritt 6.
- [ ] `/#panel=policies` grundlegend überarbeiten: weniger Tabellenwüste, bessere Informationsarchitektur, editierbare Cards/Wizards, klare Empty-/Error-States und nachvollziehbare Pool-/Policy-Flows. Detailplan: [10-vdi-pools.md](10-vdi-pools.md) Schritt 7.
- [ ] `/#panel=iam` überarbeiten: IdP-/SCIM-/Rollen-/Session-Verwaltung als geführte Admin-Flows statt roher Listen/Formulare. Detailplan: [13-iam-tenancy.md](13-iam-tenancy.md) Schritt 7.
- [ ] `/#panel=audit` überarbeiten: Audit-Viewer, Report-Builder, Export-Ziele und Compliance-Flows bedienbar und auswertbar machen. Detailplan: [15-audit-compliance.md](15-audit-compliance.md) Schritt 6.

Warum diese Punkte noch offen sind: Die bisherigen GoFuture-Schritte haben viele Backend-Contracts, APIs und erste Statusanzeigen geliefert, aber nicht konsequent jeden Betreiber-Workflow in klickbare, geführte WebUI-Abläufe übersetzt. Das widerspricht der Produktregel, dass die Beagle Web Console die einzige Operator-Oberfläche ist. Ab jetzt gilt: ein Plan-Schritt ist erst wirklich fertig, wenn er in der WebUI bedienbar, getestet und auf `srv1`/`srv2` validiert ist.

---

## Grundregeln (gelten für alle Pläne)

- Kein Big Bang. Jeder Schritt muss den Build stabil halten.
- Jede Änderung landet im Repo — kein manueller Live-Hotfix ohne Repo-Entsprechung.
- Proxmox wird dauerhaft entfernt — kein neuer Proxmox-Code, nirgendwo.
- `proxmox-ui/` und `providers/proxmox/` werden nach Plan 05 vollständig gelöscht.
- Beagle Web Console (`website/`) ist die einzige Operator-Oberfläche.
- Statusanzeigen allein reichen nicht. Jeder Betreiber-Workflow braucht WebUI-Aktionen, Validierung, Progress/Job-Status, Fehlerausgabe und einen dokumentierten Testpfad.
- Security ist Nebenbedingung jedes Schritts, keine spätere Phase.
- Dokumentation in `docs/refactor/` und `docs/refactorv2/` laufend nachziehen.

---

## Gesamt-Timeline (grob)

```
April 2026    → WebUI Modularisierung + Control Plane Cleanup
Mai    2026   → Provider-Abstraction vollständig + Server-Installer
Q3     2026   → 7.0.0 Cluster Foundation
Q4     2026   → 7.0.1 Storage + 7.0.2 HA
Q1     2027   → 7.1.0 VDI Pools + 7.1.1 Streaming v2
Q2     2027   → 7.1.2 GPU + 7.2.0 IAM v2
H2     2027   → 7.2.x Session Recording, Audit, 7.3.x Backup + SDN
2028          → 7.4.0 API + IaC + CLI + Eigener Hypervisor-Kern PoC
```
