# 03 - End-to-End Validierung

Stand: 2026-04-27  
Ziel: keine Firmenfreigabe ohne echte Nutzungsablaeufe von Release-Artefakt bis Betrieb.

---

## Gate E1 - Clean Install

- [ ] Aktuelle Server-ISO herunterladen.
- [ ] Aktuelles Installimage herunterladen.
- [ ] Leeren Host installieren.
- [ ] Erster Boot erreicht WebUI.
- [ ] Onboarding funktioniert ohne manuelle Hotfixes.
- [ ] Control Plane, nginx, TLS und Downloads sind aktiv.
- [ ] `scripts/check-beagle-host.sh` ist gruen.

Hardware:

- H3 dedizierter CPU-Server oder lokale Bare-Metal-Testmaschine.

---

## Gate E2 - WebUI und Auth

- [ ] Login per Chrome DevTools testen.
- [ ] DevTools Console auf `error`/`warn` pruefen.
- [ ] Dashboard, Settings, Updates, Downloads, Pools, Policies, IAM, Audit und Virtualization laden ohne `500`.
- [ ] Nicht-Admin-Rolle sieht keine Admin-Aktionen.
- [ ] Logout und Session-Ablauf funktionieren.

Hardware:

- H1 reicht fuer Basis.
- H3 fuer Virtualization-/VM-Aktionen.

---

## Gate E3 - USB Installer und Thin Client

- [ ] VM-spezifisches USB-Installer-Skript herunterladen.
- [ ] Live-USB-Skript herunterladen.
- [x] Skripte enthalten Log-Endpoint, scoped Token und keine Admin-Credentials. Lokal per `tests/unit/test_installer_script.py` validiert.
- [x] Skripte laden Artefakte nur dort remote, wo es technisch noetig ist. Lokal per `tests/unit/test_usb_payload_resolution_regressions.py` validiert; Bootstrap-/Payload-Cache wird wiederverwendet.
- [x] Nach Disk-Auswahl wird lokaler Payload genutzt, kein zweiter unnoetiger Remote-Download. Lokal per `tests/unit/test_usb_payload_resolution_regressions.py` validiert; der Installpfad nutzt den vorhandenen USB-/Bootstrap-Payload vor Remote-Fallback.
- [ ] Installer-Logs erscheinen ueber API.
- [ ] Thin Client enrolled sich und startet Broker/Stream.

Hardware:

- H1 fuer Skript-/Download-/API-Smoke.
- H3 oder echte Testmaschine fuer Boot-/USB-/Install-Pfad.

---

## Gate E4 - VM-Provisioning

- [ ] VM aus WebUI erstellen.
- [ ] VM aus API erstellen.
- [ ] Autoinstall laeuft ohne manuelle Callback-Korrektur durch.
- [ ] Firstboot-Service meldet Completion selbst.
- [ ] Guest-Agent/IP-Erkennung funktioniert.
- [ ] Beagle Stream Server/Beagle Stream Client-Setup wird automatisch bereit.
- [ ] VM Delete/Reset/Snapshot funktionieren.

Hardware:

- H3 dedizierter CPU-Server.

---

## Gate E5 - Streaming

- [ ] Endpoint bekommt Session ueber Broker.
- [ ] Stream startet ohne manuelles Pairing.
- [ ] Stream-Health wird gemeldet.
- [ ] Reconnect nach Host-/VM-Reboot funktioniert.
- [ ] Stream laeuft im Enterprise-Pfad verschluesselt oder ueber dokumentierten WireGuard-Mesh.
- [ ] Abbruch, Timeout und Session-Ende werden auditierbar gespeichert.

Hardware:

- H3 fuer CPU-basierte Streaming-Smokes.
- H5 fuer NVENC/GPU-Gaming.

---

## Gate E6 - Backup, Restore und Disaster Recovery

- [ ] Backup einer echten VM-Disk ausloesen.
- [ ] Backup-Status und Job-Fortschritt in WebUI sehen.
- [ ] Restore auf denselben Host testen.
- [ ] Restore auf zweiten Host testen, wenn Multi-Node verkauft wird.
- [ ] 5GB-Lasttest mit echter ausreichend grosser Disk fahren.
- [ ] Restore-Runbook dokumentieren.

Hardware:

- H3 fuer Single-Host.
- H4 fuer Cross-Host-Restore.

---

## Gate E7 - Cluster, HA und Failover

- [ ] Zwei Nodes joinen.
- [ ] Remote Inventory bleibt konsistent.
- [ ] Maintenance/Drain in WebUI ausfuehren.
- [ ] Node-Ausfall simulieren.
- [ ] Fencing- oder Start-Block-Regel verhindert Split-Brain.
- [ ] HA-Status und Alerts sind nachvollziehbar.

Hardware:

- H2 fuer Control-Plane-Clusterlogik.
- H3 + H4 fuer echte VM-/HA-Abnahme.

---

## Gate E8 - GPU

- [ ] GPU-Inventory zeigt reale Karte.
- [ ] Passthrough-Smoke erkennt GPU im Gast.
- [ ] Gaming-Pool weist GPU korrekt zu.
- [ ] Stream nutzt NVENC oder dokumentierten GPU-Pfad.
- [ ] Host-Reboot erhaelt GPU-Konfiguration.
- [ ] Keine GPU-Funktion wird als GA markiert, wenn sie nur gemockt getestet wurde.

Hardware:

- H5 GPU-Server.
