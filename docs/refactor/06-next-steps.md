# Beagle OS Refactor - Next Steps

Stand: 2026-04-16

## Update 2026-04-17

## Prioritaet 0 - Finalen Stream-Gap schliessen (aktueller Blocker)
1. Runtime-State-Drift fuer VM 101 aufloesen (`/api/v1/vms/101` running vs hostseitig zeitweise `virsh shut off`) und Host-Truth/Read-Model synchronisieren.
2. Ursache `Unable to determine guest IPv4 address for VM 101` im installer-prep beheben (IP-Detection/Lease/Agent-Pfad), damit Sunshine-Readiness fortschreiten kann.
3. Sunshine-Readiness in VM 101 finalisieren (guest IP, sunshine credentials, api reachability), danach Ports `50032/50033/50053` erneut pruefen.
4. Auf lokalem beaglethinclient den automatischen Moonlight-Connect gegen VM 101 bestaetigen und sichtbaren Desktop-Stream screenshot-basiert nachweisen.

## Prioritaet 1 - Repro/Regression-Schutz der heute gefixten Blocker
1. Frischen Host-Reinstall-Smoketest dokumentieren mit den drei neuen Script-Fixes (`install-beagle-host-services`, `install-beagle-proxy`, `install-beagle-host`).
2. Sicherstellen, dass VM-spezifische `installer.sh`-Downloads auch auf komplett frischen Hosts ohne manuelle Artefakt-Nachpflege funktionieren.
3. Regressionstest fuer lange Provisioning-Requests gegen Nginx-Proxy-Timeouts in die Host-Checkliste aufnehmen.

## Prioritaet A - Hostseitige Verifikation der Download-Artefakte
1. Auf beagleserver frische VM-spezifische Downloads pruefen (`/api/v1/vms/<vmid>/installer.sh` und `/api/v1/vms/<vmid>/live-usb.sh`) und sicherstellen, dass Preset-Credentials enthalten sind.
2. Negativtest fahren: VM ohne Sunshine-Credentials darf kein Moonlight-Installer-Skript mehr erhalten (erwarteter Guardrail-Fehler).
3. Download-/UI-Pfad in Proxmox-WebUI gegen den gehaerteten Generator erneut durchtesten.

## Prioritaet B - End-to-End Reinstall-Lauf
1. Server-Installer-ISO neu bauen und Build-Artefakt auf dem Host austauschen.
2. beagleserver-VM neu installieren (`standalone` oder `with-proxmox` gemaess Testplan) und Control-Plane/WebUI Health pruefen.
3. Ueber WebUI neue Ziel-VM anlegen, VM-spezifisches Thinclient-Installer-Skript herunterladen, beaglethinclient neu installieren und Moonlight->Sunshine Desktop-Stream verifizieren.

## Prioritaet A - Host-Recovery (Blocker aufloesen)
1. beagleserver-Zugriff stabilisieren (SSH/HTTPS wieder gruen) und Services pruefen: `ssh`, `nginx`, `beagle-control-plane`.
2. Nach Recovery direkten Health-Check fahren (`/beagle-api/api/v1/health`, Login, `vms/106`, `installer-prep`).
3. Ursache fuer den kurzzeitigen Management-Ausfall eingrenzen (journal/systemd/boot-sequenz) und dokumentieren.

## Prioritaet B - VM106 Stream-Ready machen
1. `installer-prep` fuer VM106 bis `ready=true` durchlaufen lassen (Guest-IP/Sunshine-Binary/Service/Process).
2. Public-Stream-Ports fuer VM106 validieren (`50192`, `50193`) inkl. Host-Firewall-/Forward-Regeln.
3. Sunshine-Credentials/API fuer VM106 testen und Moonlight-Handshake pruefen.

## Prioritaet C - Thinclient E2E
1. lokalen `beaglethinclient` auf VM106-Profil umstellen (Stream-Host/Port 192.168.122.130:50192).
2. Moonlight-Connect aus Thinclient starten und erfolgreichen Stream nachweisen.
3. Ergebnis inklusive Repro-Schritte als Smoke-Run dokumentieren.
