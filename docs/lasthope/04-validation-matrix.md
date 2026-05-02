# Validation Matrix

Stand: 2026-05-02

Diese Matrix definiert, welche Nachweise in Repo, CI und Live-Umgebung stehen
muessen. Ein Gate ist erst gruen, wenn der Nachweis reproduzierbar ist.

## E0 - Interne Runtime-Konsistenz

| Check | Nachweis | Status |
|---|---|---|
| `main` ist lokal und remote synchron | `git status --short --branch` | offen je Lauf |
| CI fuer `main` gruen | GitHub Actions | offen je Lauf |
| `srv1` installiert denselben Commit | `/opt/beagle/.beagle-installed-commit` | offen je Lauf |
| Versionen konsistent | `VERSION`, WebUI, repo-status, download-status | offen je Lauf |
| Artefaktlauf nicht rot bei Duplicate-Start | `beagle-artifacts-refresh.service` | offen je Lauf |

## E1 - Single-Host Pilot

| Check | Nachweis | Status |
|---|---|---|
| Clean-Install aus Release-ISO | Installationsprotokoll + Screenshot/WebUI-Login | offen |
| Host-Health gruen | `scripts/check-beagle-host.sh` | offen |
| VM-Erstellung ueber WebUI | `vm100` oder frische Test-VM | laufend |
| Firstboot/Callback/Reboot | Provisioning-State + Guest-Journal | offen |
| Desktop-Login | noVNC oder Stream | offen |
| Thinclient-Live-USB | echter Boot + IP + Enrollment | offen |
| BeagleStream | sichtbarer Desktop ueber Broker/WireGuard | offen |
| Backup/Restore Single-Host | Restore-Protokoll | offen |

## E2 - Zwei-Host Pilot

| Check | Nachweis | Status |
|---|---|---|
| Cluster Join | `srv1` + `srv2` Member healthy | offen |
| Maintenance/Drain | Job-Log + Audit | offen |
| HA/Fencing | kontrollierter Ausfalltest | offen |
| Session-Handover | Stream bleibt nutzbar oder reconnectet kontrolliert | offen |
| WireGuard-Latenz | Messprotokoll direct vs tunnel | offen |
| Backup-Replica | zweite Node oder frischer Host | offen |

## E3 - Firmenangebot

| Check | Nachweis | Status |
|---|---|---|
| R3 Hardware | GPU/NVENC/VFIO-Reboot/vGPU-Entscheid | offen |
| externer Security-Review | Bericht + Nachfix-Protokoll | offen |
| Update von Vorversion | Protokoll + Rollbackpunkt | offen |
| Rollback/Restore | erfolgreicher Rueckweg | offen |
| Runbooks validiert | Befund pro Runbook | offen |
| Support-/Incident-Prozess | Kontakt, Severity, Eskalation | vorbereitet |

## E4 - Enterprise-Ausbau

| Check | Nachweis | Status |
|---|---|---|
| Multi-Tenant IAM im Kundenscope | OIDC/SAML/SCIM live mit Test-IdP | offen |
| Compliance-Export | Audit/PII/Retention in Pilotdaten | offen |
| WebRTC oder Native Protocol | Feature-Branch + E2E | offen |
| vGPU/MDEV | echte Lizenz/Hardware | offen |
| Mobile/Accessibility | Lighthouse + axe + Browser-Matrix | offen |

