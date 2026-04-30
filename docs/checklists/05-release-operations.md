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

- [x] [`../runbooks/installation.md`](../runbooks/installation.md) — Installations-Runbook (Skelett, ungetestet)
- [x] [`../runbooks/update.md`](../runbooks/update.md) — Update-Runbook (Skelett, ungetestet)
- [x] [`../runbooks/rollback.md`](../runbooks/rollback.md) — Rollback-Runbook (Skelett, ungetestet)
- [x] [`../runbooks/backup-restore.md`](../runbooks/backup-restore.md) — Backup-/Restore-Runbook (Skelett, ungetestet)
- [x] [`../runbooks/incident-response.md`](../runbooks/incident-response.md) — Incident-Response-Runbook (Skelett, ungetestet)
- [x] [`../runbooks/pilot.md`](../runbooks/pilot.md) — Pilot-Runbook fuer Kunden (Skelett, ungetestet)
- [ ] Mind. 1 Runbook auf realer Hardware validiert (Befund eingetragen)
- [ ] Notfallzugriff ohne Klartext-Secrets in Dokumenten
- [ ] Wartungsfenster + Supportzeiten definiert

## Monitoring + Alerting

- [x] Control-Plane-Health-Endpoint liefert + alerted (R3) — `HEALTH_ENDPOINT_SMOKE=PASS` auf srv1 (2026-04-30, ok=true)
- [x] nginx/TLS-Health — `check-beagle-health.sh` PASS: nginx active, TLS cert valid 89 days, (2026-04-30)
- [x] Disk-/Storage-Fuellstand-Alert — `check-beagle-health.sh` PASS: /var/lib/beagle=1%, /var/lib/libvirt/images=33%, /=33% (threshold 80%, 2026-04-30)
- [ ] VM-/Session-/Stream-Health
- [ ] Backup-Erfolg + Restore-Alter
- [ ] Webhook oder E-Mail fuer kritische Alerts

## Compliance + Datenschutz

- [x] Datenarten dokumentiert (Nutzer, Sessions, Audit, Stream-Health, Endpoint-HW) — `docs/runbooks/data-retention.md` (2026-04-30)
- [x] Retention-Regeln definiert — `docs/runbooks/data-retention.md` Kapitel 2 (2026-04-30)
- [ ] Audit-Export fuer Administratoren produktiv
- [x] PII-/Secret-Redaction validiert — `docs/runbooks/data-retention.md` Kapitel 3 (2026-04-30)
- [ ] Auftragsverarbeitung/DSGVO-Hinweise fuer Pilotkunden vorbereitet
