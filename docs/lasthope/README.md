# Beagle OS LastHope Enterprise Plan

Stand: 2026-05-02
Version: 8.0.9

Dieses Verzeichnis ist der endgueltige Enterprise-GA-Plan fuer Beagle OS.
Es ersetzt nicht die operativen Detail-Checklisten unter `docs/checklists/`.
Es fasst sie zu einem verkaufbaren Produktpfad zusammen: Was muss noch fertig
werden, bevor Beagle OS Firmen angeboten werden kann?

## Produktziel

Beagle OS Enterprise ist eine eigenstaendige On-Prem Desktop-Virtualisierungs-
und Streaming-Plattform auf KVM/libvirt-Basis.

Das verkaufbare Zielbild:

- Bare-Metal-Installation ohne manuelle Hotfixes
- Beagle Web Console als einzige Operator-Oberflaeche
- KVM/libvirt ohne Proxmox-Abhaengigkeit
- BeagleStream Server/Client statt manuellem Sunshine/Moonlight-Pairing
- WireGuard-geschuetzte Thinclient- und Stream-Pfade
- mandantenfaehige Auth/RBAC/IAM-Basis
- Backup, Restore, Audit, Monitoring und Incident-Prozess
- reproduzierbare Releases, Updates und Rollbacks
- getestete Runbooks und belastbare Support-Unterlagen

## Aktueller Zustand

Der Code ist bereits weit ueber einen Prototyp hinaus. Viele Enterprise-Bloecke
sind implementiert und teils auf `srv1`/`srv2` live validiert:

- Control Plane, Web Console, Auth/RBAC, Audit und Session-Handling
- KVM/libvirt-Provider, VM-Lifecycle, Storage-Abstraktion, Cluster-Surface
- BeagleStream Phase A in Forks und Beagle-OS-Integration vorbereitet
- Thinclient OS, Enrollment, WireGuard, Endpoint Reporting, Self-Heal
- Update-/Release-Automation, Artefakt-Builds und Public-Mirror-Pfad
- Observability, Health-Checks, strukturierte Logs und CI-Gates

Noch nicht Enterprise-GA:

- frischer Clean-Install aus Release-Artefakten ist noch kein gruenes R1-Gate
- `vm100`/neue VMs muessen Firstboot, Reboot, Desktop und Stream reproduzierbar abschliessen
- BeagleStream muss als echter End-to-End-Pfad Thinclient -> WireGuard -> Broker -> Desktop bewiesen werden
- Backup/Restore muss mit echter VM-Disk auf einem frischen bzw. zweiten Host nachgewiesen werden
- HA/Fencing/Storage/GPU brauchen weitere Hardware-Gates
- externer Security-Review/Pentest fehlt
- Runbooks sind vorhanden, aber noch nicht fuer alle kritischen Betriebsablaeufe live validiert

## Enterprise-Gates

| Gate | Ziel | Status | Verkaufbarkeit |
|---|---|---|---|
| E0 | Repo, CI, srv1 Runtime konsistent | weitgehend gruen | interne Entwicklung |
| E1 | Single-Host Pilot mit Clean-Install, VM, Thinclient, Backup | offen | technische Pilotkunden |
| E2 | Zwei-Host Pilot mit HA, Restore, Monitoring, Runbooks | offen | bezahlte Pilotphase |
| E3 | Security Review, Supportmodell, Update/Rollback, R3 Hardware | offen | Firmenangebot |
| E4 | Multi-Tenant, Compliance, GPU/vGPU, SLA-Betrieb | offen | Enterprise-Ausbau |

Beagle OS darf Firmen erst als produktionsnahes Angebot vorgestellt werden,
wenn mindestens E2 gruen ist. Fuer produktive Enterprise-Nutzung ist E3 Pflicht.

## Kanonische Detailquellen

| Bereich | Detailquelle |
|---|---|
| Plattform, HA, Storage, GPU, SDN | `docs/checklists/01-platform.md` |
| Streaming, Endpoint OS, Thinclient, Kiosk | `docs/checklists/02-streaming-endpoint.md` |
| Security, Auth, Audit, Compliance | `docs/checklists/03-security.md` |
| CI, Tests, Observability, Datenintegritaet, UX | `docs/checklists/04-quality-ci.md` |
| Release, Operations, Hardware, Pilot | `docs/checklists/05-release-operations.md` |
| BeagleStream Fork-Spezifikation | `fork.md` und `docs/archive/goenterprise/01-moonlight-vdi-protocol.md` |
| Security Restrisiken | `docs/refactor/11-security-findings.md` |

## Sofort-Reihenfolge

1. `vm100` neu provisionieren und bis Desktop/Stream-Endzustand ueberwachen.
2. BeagleStream-End-to-End mit echtem Thinclient beweisen.
3. R1 Clean-Install aus Release-Artefakten auf leerem Host durchfuehren.
4. Backup einer echten VM-Disk auf zweitem/frischem Host restoren und Hash/Boot pruefen.
5. Runbooks fuer Installation, Update, Rollback, Backup, Incident live validieren.
6. R3 Hardware-Reste fahren: NVENC-Session, VFIO-Reboot-Proof, vGPU/MDEV nur mit echter Lizenz/Hardware.
7. Security-Reste schliessen: OIDC-JWKS, SCIM-Token-Rotation, Debug-Secret-Guard, externer Pentest.
8. UI-Reste schliessen: i18n-Restmodule, Mobile-Responsive, Lighthouse-Gates.

## Dokumente in diesem Verzeichnis

- `01-enterprise-gap-list.md` sammelt die offenen Pflichtluecken.
- `02-execution-order.md` ordnet die Arbeit in umsetzbare Wellen.
- `03-commercial-readiness.md` definiert, was vor Firmenangeboten stehen muss.
- `04-validation-matrix.md` beschreibt die Abnahme pro Gate.

