# 05 — Release, Operations, Hardware-Abnahme, Pilot

**Scope**: Release-Gates R0..R4, Hardware-Abnahme, Runbooks, Operations, Pilotbetrieb.
**Quelle**: konsolidiert aus `docs/archive/gorelease/00..05`.

---

## R0 — Pre-Release Smoke (auf Test-VMs `rel1`/`rel2`)

- [x] Server-Installer-ISO baut reproduzierbar (`build-iso.yml`)
- [x] Installimage-Tarball baut reproduzierbar
- [x] `latest`-Release zeigt auf aktuelle Zielversion (8.0)
- [x] `8443` aus allen Pfaden entfernt
- [x] Public Download-Skripte ohne Admin-/Manager-Credentials (CI-Guard `security-secrets-check.yml`)

## R1 — Funktionale Abnahme auf Test-VMs

- [x] Login + Refresh + Logout browserseitig + per API
- [x] noVNC-/Console-Token TTL + Scope + Audit
- [x] Sunshine Stream-Prep unattended PASS auf VM100 (srv1)
- [ ] **Frische ISO-Installation auf leerem Host:** Erst-Boot erreicht WebUI ohne manuelle Hotfixes
- [ ] `scripts/check-beagle-host.sh` gruen nach Clean-Install
- [ ] Dashboard, Settings, Updates, Downloads, Pools, Policies, IAM, Audit, Virtualization laden ohne `500`
- [ ] VM-Lifecycle aus WebUI + API: create, start, snapshot, reboot, delete
- [ ] Autoinstall + Firstboot-Service melden Completion selbststaendig
- [ ] Backup einer echten VM-Disk → Restore auf zweitem Host → Hash-Match

## R2 — Pilot-fertig

- [ ] R1 vollstaendig gruen
- [ ] Mind. 1 Cluster-Smoke (Join + Drain + Failover) auf 2-Node-Hardware
- [ ] HA-Manager + Fencing auf Hardware (kein Mock)
- [ ] Session-Handover live zwischen 2 Nodes
- [ ] WireGuard-Mesh + Stream-Tunnel mit echten Latenz-Messwerten

## R3 — Hardware-Abnahme (Bare-Metal + GPU)

- [ ] GPU-Server bei Hetzner gebucht, IOMMU/VFIO/libvirt verifiziert
- [ ] GPU-Inventory: Karte, Treiber, IOMMU-Gruppe, Passthrough-Faehigkeit korrekt
- [ ] Passthrough-VM sieht GPU + Audio
- [ ] NVENC-/Streaming-Pfad mit echter Session, Latenz-Messwerten
- [ ] Reboot-Proof: VFIO-Konfiguration ueberlebt Host-Reboot
- [ ] Gaming-Pool blockiert sauber wenn keine GPU verfuegbar
- [ ] vGPU/MDEV nur als bestanden markieren wenn Hardware + Lizenz real vorliegen
- [ ] GPU-Server unmittelbar nach Abnahme gekuendigt (Kosten)

## R4 — Production-Ready (Enterprise)

- [ ] R3 vollstaendig gruen
- [ ] Externer Security-Review / Penetrationstest ohne kritische Findings
- [ ] Mind. 1 Clean-Install aus Release-Artefakten reproduzierbar
- [ ] Mind. 1 Update von Vorversion auf Zielversion durchlaufen
- [ ] Mind. 1 Rollback/Restore erfolgreich
- [ ] Pilot-Runbook fuer Kunden in `docs/runbooks/pilot.md`
- [ ] Support-/Incident-Prozess in `docs/runbooks/incident-response.md`

## Operations + Runbooks

- [ ] `docs/runbooks/installation.md` — Installations-Runbook
- [ ] `docs/runbooks/update.md` — Update-Runbook
- [ ] `docs/runbooks/rollback.md` — Rollback-Runbook
- [ ] `docs/runbooks/backup-restore.md` — Backup-/Restore-Runbook
- [ ] `docs/runbooks/incident-response.md` — Incident-Response-Runbook
- [ ] `docs/runbooks/pilot.md` — Pilot-Runbook fuer Kunden
- [ ] Notfallzugriff ohne Klartext-Secrets in Dokumenten
- [ ] Wartungsfenster + Supportzeiten definiert

## Monitoring + Alerting

- [ ] Control-Plane-Health-Endpoint liefert + alerted
- [ ] nginx/TLS-Health
- [ ] Disk-/Storage-Fuellstand-Alert
- [ ] VM-/Session-/Stream-Health
- [ ] Backup-Erfolg + Restore-Alter
- [ ] Webhook oder E-Mail fuer kritische Alerts

## Compliance + Datenschutz

- [ ] Datenarten dokumentiert (Nutzer, Sessions, Audit, Stream-Health, Endpoint-HW)
- [ ] Retention-Regeln definiert
- [ ] Audit-Export fuer Administratoren produktiv
- [ ] PII-/Secret-Redaction validiert
- [ ] Auftragsverarbeitung/DSGVO-Hinweise fuer Pilotkunden vorbereitet
