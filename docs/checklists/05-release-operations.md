# 05 — Release, Operations, Hardware-Abnahme, Pilot

**Scope**: Release-Gates R0..R4, Hardware-Abnahme, Runbooks, Operations, Pilotbetrieb.
**Quelle**: konsolidiert aus `docs/archive/gorelease/00..05`.

---

## R0 — Pre-Release Smoke (auf Test-VMs `rel1`/`rel2`)

- [x] Server-Installer-ISO baut reproduzierbar (`build-iso.yml`)
- [x] Installimage-Tarball baut reproduzierbar
- [x] `latest`-Release zeigt auf aktuelle Zielversion — GitHub `Latest` = `v8.0.9`, `beagle-os.com/beagle-updates/beagle-downloads-status.json` meldet `version=8.0.9` (2026-05-02)
- [x] `8443` aus allen Pfaden entfernt
- [x] Public Download-Skripte ohne Admin-/Manager-Credentials (CI-Guard `security-secrets-check.yml`)

## R1 — Funktionale Abnahme auf Test-VMs

- [x] Login + Refresh + Logout browserseitig + per API
- [x] noVNC-/Console-Token TTL + Scope + Audit
- [x] Sunshine Stream-Prep unattended PASS auf VM100 (srv1)
- [ ] **Frische ISO-Installation auf leerem Host:** Erst-Boot erreicht WebUI ohne manuelle Hotfixes
- [ ] `scripts/check-beagle-host.sh` gruen nach Clean-Install
- [x] Dashboard, Settings, Updates, Downloads, Pools, Policies, IAM, Audit, Virtualization laden ohne `500` — `scripts/test-r1-dashboard-smoke.py` gegen `https://srv1.beagle-os.com/beagle-api` (8 Endpunkte, alle 200, 2026-04-30)
- [x] VM-Lifecycle aus WebUI + API: create, start, snapshot, reboot, delete — API-Smoke `scripts/test-vm-lifecycle-r1-smoke.py` gegen `https://srv1.beagle-os.com/beagle-api` PASS (create/start/snapshot/reboot/delete, Cleanup inklusive, 2026-04-30)
- [ ] Autoinstall + Firstboot-Service melden Completion selbststaendig
- [ ] Backup einer echten VM-Disk → Restore auf zweitem Host → Hash-Match

## R2 — Pilot-fertig

- [ ] R1 vollstaendig gruen
- [ ] Mind. 1 Cluster-Smoke (Join + Drain + Failover) auf 2-Node-Hardware
- [ ] HA-Manager + Fencing auf Hardware (kein Mock)
- [ ] Session-Handover live zwischen 2 Nodes
- [ ] WireGuard-Mesh + Stream-Tunnel mit echten Latenz-Messwerten

## R3 — Hardware-Abnahme (Bare-Metal + GPU)

- [x] GPU-Server bei Hetzner gebucht, IOMMU/VFIO/libvirt verifiziert — srv2 GTX 1080 + Audiofunktion an `vfio-pci`, libvirt/API-Inventar vorhanden (2026-05-02 Docs-Triage)
- [x] GPU-Inventory: Karte, Treiber, IOMMU-Gruppe, Passthrough-Faehigkeit korrekt — `PLAN12_GPU_SMOKE=PASS`, Status bewusst `not-isolatable` wegen IOMMU-Gruppe mit Root Port (2026-05-02)
- [x] Passthrough-VM sieht GPU + Audio — transienter `beagle-gpu-smoke` sah `10de:1b80` + `10de:10f0` im Gast (srv2, dokumentiert 2026-04-27)
- [ ] NVENC-/Streaming-Pfad mit echter Session, Latenz-Messwerten
- [ ] Reboot-Proof: VFIO-Konfiguration ueberlebt Host-Reboot
- [x] Gaming-Pool blockiert sauber wenn keine GPU verfuegbar — `GPU_POOL_NO_GPU_SMOKE=PASS` auf srv1 (`pending-gpu`, allocation blocked, 2026-04-30)
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
- [x] Mind. 1 Runbook auf realer Hardware validiert (Befund eingetragen) — `check-beagle-health.sh` 11/11 PASS auf srv1 live (2026-04-30)
- [x] Notfallzugriff ohne Klartext-Secrets in Dokumenten — `docs/runbooks/maintenance-windows.md` Abschnitt 4: Break-Glass via verschluesseltem Passwort-Manager dokumentiert (2026-04-30)
- [x] Wartungsfenster + Supportzeiten definiert — `docs/runbooks/maintenance-windows.md` erstellt (Di 02-04 Uhr, SLA-Tabelle, Kommunikationstemplate, 2026-04-30)

## Monitoring + Alerting

- [x] Control-Plane-Health-Endpoint liefert + alerted (R3) — `HEALTH_ENDPOINT_SMOKE=PASS` auf srv1 (2026-04-30, ok=true)
- [x] nginx/TLS-Health — `check-beagle-health.sh` PASS: nginx active, TLS cert valid 89 days, (2026-04-30)
- [x] Disk-/Storage-Fuellstand-Alert — `check-beagle-health.sh` PASS: /var/lib/beagle=1%, /var/lib/libvirt/images=33%, /=33% (threshold 80%, 2026-04-30)
- [x] VM-/Session-/Stream-Health — `check-beagle-health.sh` erw.: virsh VM-health, sessions-API-alive, sunshine-service (11/11 PASS, 2026-04-30)
- [x] Backup-Erfolg + Restore-Alter — `check-beagle-health.sh` erw.: backup_age-Check in `BACKUP_DIR` (Threshold konfigurierbar, 2026-04-30)
- [x] Webhook oder E-Mail fuer kritische Alerts — `check-beagle-health.sh`: `--webhook-url` Flag + `$BEAGLE_ALERT_WEBHOOK_URL` Env; POST JSON bei FAIL (2026-04-30)

## Compliance + Datenschutz

- [x] Datenarten dokumentiert (Nutzer, Sessions, Audit, Stream-Health, Endpoint-HW) — `docs/runbooks/data-retention.md` (2026-04-30)
- [x] Retention-Regeln definiert — `docs/runbooks/data-retention.md` Kapitel 2 (2026-04-30)
- [x] Audit-Export fuer Administratoren produktiv — `scripts/test-audit-export-smoke.py` PASS: 474 events, export-targets 3, PII-Redaction OK (srv1, 2026-04-30)
- [x] PII-/Secret-Redaction validiert — `docs/runbooks/data-retention.md` Kapitel 3 (2026-04-30)
- [x] Auftragsverarbeitung/DSGVO-Hinweise fuer Pilotkunden vorbereitet — `docs/runbooks/dsgvo-avv-pilot.md` erstellt (TOMs, AVV-Pflicht, Betroffenenrechte, VVT-Vorlage, 2026-04-30)
