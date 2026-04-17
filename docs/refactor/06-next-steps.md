# Beagle OS Refactor - Next Steps

Stand: 2026-04-16

## Update 2026-04-17

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
