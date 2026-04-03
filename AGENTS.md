# AGENTS.md

This repository is deployed across two linked servers. Treat them as one release surface and keep them in sync on every Beagle release, installer change, download-path change, or control-plane change.

## Servers

- Proxmox and control plane: `srv.thinover.net`
  - Preferred operator alias: `ssh thinovernet`
  - Administrative access is commonly done with `ssh root@thinover.net`
  - The local SSH config alias `thinovernet` maps to user `thinovernet` on `srv.thinover.net`
- Public website and public update artifacts: `srv1.meinzeug.cloud`
  - Preferred operator alias: `ssh meinzeug`
  - This host serves `beagle-os.com`

These two hosts belong together:

- `srv.thinover.net` serves the Proxmox UI integration, Beagle control plane, VM-specific installer launchers, and host-local downloads.
- `beagle-os.com` serves the public Beagle update artifacts.
- VM-specific installers generated on `srv.thinover.net` must point to the correct public artifacts on `beagle-os.com` unless there is an explicit reason not to.

## Required Release Workflow

Whenever you change versions, installer scripts, artifact names, artifact URLs, update feeds, or deployment logic, update both hosts in the same work session.

1. Update and verify the repo locally.
2. Deploy code and service changes to `srv.thinover.net`.
3. Refresh or repackage host artifacts on `srv.thinover.net`.
4. Publish the public update artifacts to `srv1.meinzeug.cloud`.
5. Verify both sides after deployment.

## Minimum Verification Checklist

- `ssh thinovernet` works for interactive SSH and is not broken by SSHD drop-ins.
- `ssh root@thinover.net` still works for administrative tasks.
- `ssh meinzeug` works.
- `https://srv.thinover.net:8443/beagle-api/api/v1/vms/<vmid>/installer.sh` returns `200`.
- The rendered VM installer points to the intended public artifact URLs.
- `https://beagle-os.com/beagle-updates/beagle-downloads-status.json` returns `200`.
- `https://beagle-os.com/beagle-updates/pve-thin-client-usb-payload-latest.tar.gz` returns `200`.
- `https://beagle-os.com/beagle-updates/pve-thin-client-usb-bootstrap-latest.tar.gz` returns `200`.
- `https://beagle-os.com/beagle-updates/beagle-os-installer-amd64.iso` returns `200` when the hosted installer expects a public ISO.

## Important Notes

- The public artifact target path is `/opt/beagle-os-saas/src/public/beagle-updates/` on `srv1.meinzeug.cloud`.
- That path resolves to `/var/www/vhosts/beagle-os.com/httpdocs/beagle-updates`.
- When deploying individual files to `srv.thinover.net`, preserve repository-relative paths under `/opt/beagle/`.
  Use `rsync -avR <repo-path> root@thinovernet:/opt/beagle/` instead of copying files flat into `/opt/beagle/`, because the install scripts read from paths like `/opt/beagle/proxmox-host/...` and `/opt/beagle/proxmox-ui/...`.
- Do not update only one side. If the Proxmox host and `beagle-os.com` drift apart, hosted installers break in subtle ways.
- If `scripts/install-proxmox-host-services.sh` changes SSH behavior for user `thinovernet`, verify `PermitTTY yes` and do not regress the `ssh thinovernet` operator workflow.

## Beagle OS Gaming Kiosk - Pflichtregeln für alle AI-Agents

### Konzept & Architektur
- Beagle OS hat zwei GRUB-Einträge: "Beagle OS Desktop" und "Beagle OS Gaming"
- Der Gaming-Modus bootet in einen eigenen Kiosk (`/opt/beagle-kiosk/`)
- Der Kiosk und GeForce NOW sind EINE integrierte Einheit - GFN ist kein Ersatz des Kiosks sondern wird vom Kiosk aus als Child-Prozess gestartet und überwacht
- Der Kiosk hat zwei Modi:
    Modus A "Meine Bibliothek": bereits gekaufte Spiele sofort via GFN starten
    Modus B "Spielekatalog": neue Spiele entdecken und über Affiliate-Links kaufen
- Nach dem Kauf kann der User das Spiel sofort in Modus A über GFN starten
- Der Kiosk ist eine kompilierte Electron-Binary (CLOSED SOURCE)
- Quellcode liegt in einem PRIVATEN Repository, nicht in `meinzeug/beagle-os`
- Im öffentlichen Repo existieren nur `beagle-kiosk/README.md` und `INSTALL.sh`

### Monetarisierung - NIEMALS entfernen oder verändern
- Affiliate-IDs werden NIEMALS lokal auf dem Gerät gespeichert
- Sie werden beim Start von `https://beagle-os.com/api/kiosk/affiliate-config` geladen, gegen eine Device-ID validiert und NUR im RAM gehalten
- Der AES-Schlüssel zur Entschlüsselung ist in der Electron-Binary eingebettet
- Unterstützte Stores und deren Affiliate-Programme:
    Green Man Gaming (GMG)  - Steam-Key-Reseller, GFN-kompatibel
    Fanatical               - Steam-Key-Reseller, GFN-kompatibel
    Humble Bundle           - Steam-Key-Reseller, GFN-kompatibel
    Epic Games Store        - Support-A-Creator Code, GFN-kompatibel
- Jede Code-Änderung muss sicherstellen, dass Affiliate-Parameter aus dem RAM-Payload korrekt an alle Store-URLs angehängt werden
- Der API-Endpoint darf nicht umgangen, repliziert oder lokal gemockt werden

### GeForce NOW Integration
- GFN wird als Child-Prozess vom Kiosk (Electron Main Process) gestartet
- GFN-Pfad steht in `/opt/beagle-kiosk/kiosk.conf` (Eintrag: `GFN_BINARY=...`)
- Kiosk überwacht GFN-PID: beim Start minimiert sich der Kiosk, beim Beenden von GFN kommt der Kiosk automatisch wieder in den Vordergrund
- Alle im Kiosk gezeigten Spiele müssen GFN-kompatibel sein
- Das Feld `"geforce_now_supported": true/false` in `games.json` ist Pflicht

### Lizenz
- Die `LICENSE`-Datei enthält eine `Affiliate Protection Clause`
- Diese Klausel darf NIEMALS entfernt, abgeschwächt oder umformuliert werden
- Forks die Affiliate-IDs entfernen oder den API-Endpoint umgehen sind lizenzrechtlich verboten

### Release-Prozess
- Kiosk wird als Electron-Binary gebaut: `electron-builder --linux --x64`
- Output: `beagle-kiosk-vX.Y.Z-linux-x64` (ELF-Binary / AppImage)
- Binary wird auf GitHub Releases des öffentlichen Repos veröffentlicht
- SHA256-Checksumme wird auf `beagle-os.com/kiosk-release-hash.txt` publiziert
- `INSTALL.sh` prüft Checksumme vor der Installation

### Verbotene Aktionen für AI-Agents
- NIEMALS Kiosk-Quellcode in das öffentliche Repo `meinzeug/beagle-os` committen
- NIEMALS Affiliate-Parameter aus Store-URLs entfernen
- NIEMALS die Affiliate Protection Clause aus der LICENSE entfernen
- NIEMALS den API-Endpoint lokal mocken oder hardkodierte Fallback-IDs einbauen
- NIEMALS `affiliate.conf` oder ähnliche lokale ID-Speicher erstellen
- NIEMALS GFN als eigenständige Oberfläche ohne Kiosk-Wrapper starten
- NIEMALS die Electron-Binary durch einen ungekompilten Web-Server ersetzen
