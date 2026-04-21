# Security Findings

Stand: 2026-04-19

## Zweck

- Diese Datei sammelt alle waehrend der laufenden Refactor-Arbeit gefundenen Sicherheitsprobleme, Secret-Leaks, unsicheren Defaults und offenen Hardening-Punkte.
- Jeder neue Fund muss hier mit Status, Auswirkung und naechstem Schritt eingetragen werden.
- Wenn ein Fund im selben Run sicher und reproduzierbar behebbar ist, wird er direkt gepatcht und hier als mitigiert dokumentiert.

## S-001 - Lokale Operator-Dateien waren im Git-Tracking

- Status: mitigiert im Workspace, Shared-Repo-Commit/Pull-Request noch erforderlich
- Risiko: Hoch
- Betroffene Dateien:
  - `AGENTS.md`
  - `CLAUDE.md`
- Beschreibung:
  - Beide lokalen Operator-Dateien waren im Git-Tracking und konnten dadurch versehentlich auf GitHub landen.
  - Dadurch besteht ein strukturelles Risiko, dass interne Arbeitsanweisungen, lokale Betriebsdetails oder spaeter eingetragene Zugangshinweise offengelegt werden.
- Mitigation:
  - `.gitignore` wurde um `AGENTS.md` und `CLAUDE.md` erweitert.
  - `AGENTS.md` und `CLAUDE.md` wurden aus dem Git-Index entfernt und lokal beibehalten.
  - Diese Dateien muessen aus dem Git-Tracking entfernt bleiben.
  - `AGENTS.md` wurde explizit um die Regel erweitert, dass beide Dateien lokal-only sind.
- Naechster Schritt:
  - Sicherstellen, dass die Tracking-Entfernung committed und nach GitHub gepusht wird.

## S-002 - Klartext-Secrets duerfen nicht in versionierte Repo-Dateien

- Status: aktiv als Guardrail
- Risiko: Hoch
- Beschreibung:
  - Im Rahmen von Live-Betrieb, Deployments und Multi-Agent-Arbeit tauchen regelmaessig Zugriffswege, Hostnamen und Credentials auf.
  - Wenn diese als Klartext in versionierten Repo-Dateien landen, entsteht sofort ein Secret-Leak-Risiko fuer GitHub, Releases und Forks.
- Mitigation:
  - Sicherheitsregel in `AGENTS.md` verankert: keine Klartext-Passwoerter oder Zugangsdaten in commitbare Dateien.
  - Lokale Operator-Hinweise duerfen nur in nicht versionierten Dateien stehen.
  - SSH-Zugriff auf `srv1.meinzeug.cloud` erfolgt lokal ueber den Alias `ssh meinzeug` mit lokalem Key statt ueber Repo-dokumentierte Passwoerter.
- Naechster Schritt:
  - Repo gezielt nach weiteren potenziellen Klartext-Secrets, Tokens oder sensiblen Operator-Hinweisen durchsuchen und bereinigen.

## S-003 - Installimage source bundle enthaelt lokale Operator-Dateien

- Status: mitigiert, neu gebaut, verifiziert und als `6.6.9` veroeffentlicht
- Risiko: Hoch
- Betroffene Dateien:
  - `scripts/build-server-installimage.sh`
  - eingebettetes Archiv `/usr/local/share/beagle/beagle-os-source.tar.gz` innerhalb des installimage-Tarballs
- Beschreibung:
  - Der erste Build des neuen Hetzner-installimage-Artefakts hat die lokalen Dateien `AGENTS.md` und `CLAUDE.md` in das eingebettete Beagle-Source-Archiv aufgenommen.
  - Dadurch waeren lokale Operator-Hinweise ueber das oeffentlich verteilte installimage-Artefakt weitergegeben worden.
- Mitigation:
  - Builder wurde direkt gepatcht, sodass nur explizit erlaubte Repo-Pfade gebuendelt werden und `AGENTS.md` / `CLAUDE.md` nicht mehr Teil des Source-Bundles sind.
  - Das korrigierte `Debian-1201-bookworm-amd64-beagle-server.tar.gz` wurde fuer `6.6.9` neu gebaut, gegen den eingebetteten Source-Tarball verifiziert und auf `beagle-os.com` veroeffentlicht.
  - Die installierte Hetzner-Zielmaschine wurde auf dieses Artefakt aktualisiert.
- Naechster Schritt:
  - GitHub Release Assets nachziehen, sobald ein authentifizierter Release-Upload-Pfad verfuegbar ist.

## S-004 - Public source/server-installer bundles enthielten lokale Operator-Dateien

- Status: mitigiert im Workspace und in `6.6.9` Release-Artefakten, GitHub-Push noch erforderlich
- Risiko: Hoch
- Betroffene Dateien:
  - `scripts/package.sh`
  - `scripts/build-server-installer.sh`
  - `beagle-os-v*.tar.gz`
  - server-installer embedded source archive
- Beschreibung:
  - Neben dem installimage-Pfad waren auch das public source tarball Packaging und der server-installer embedded source bundle fuer lokale Operator-Dateien anfaellig.
  - Dadurch haetten `AGENTS.md` oder `CLAUDE.md` ueber allgemeine Release-Artefakte oder Server-Installer-ISO-Inhalte veroeffentlicht werden koennen.
- Mitigation:
  - `scripts/package.sh` und `scripts/build-server-installer.sh` wurden auf explizite erlaubte Repo-Pfade ohne `AGENTS.md` / `CLAUDE.md` umgestellt.
  - `beagle-os-v6.6.9.tar.gz` und das `6.6.9` installimage embedded source bundle wurden lokal auf Abwesenheit dieser Dateien geprueft.
- Naechster Schritt:
  - Repo-Aenderungen nach GitHub pushen, damit die Scrubbing-Regeln nicht nur lokal und in den gebauten Artefakten existieren.

## S-005 - Security/TLS WebUI scheiterte auf frischen Hosts an unvollstaendiger Let's-Encrypt Runtime und Service-Sandbox

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel bis Hoch
- Betroffene Dateien:
  - `beagle-host/services/server_settings.py`
  - `beagle-host/systemd/beagle-control-plane.service`
  - `scripts/install-beagle-host-services.sh`
  - `scripts/install-beagle-proxy.sh`
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
- Beschreibung:
  - Die Security-Einstellungen konnten auf einem frisch installierten Standalone-Host kein Let's-Encrypt-Zertifikat ausstellen.
  - Root Cause 1: `certbot` und `python3-certbot-nginx` wurden in den kanonischen Host-/Installer-Pfaden nicht zuverlaessig mitinstalliert.
  - Root Cause 2: selbst nach Paketinstallation scheiterte der API-Pfad innerhalb des gehaerteten `beagle-control-plane.service`-Sandboxes bei `certbot --nginx`, weil Let's-Encrypt- und nginx-Logpfade nicht im gleichen Ausfuehrungskontext nutzbar waren.
- Mitigation:
  - Installpfade wurden auf automatische Installation von `certbot` und `python3-certbot-nginx` erweitert.
  - `server_settings.py` prueft nun explizit auf fehlendes `certbot` bzw. fehlenden nginx-Plugin-Support und liefert klare Fehlerbilder.
  - TLS-Issuance laeuft bevorzugt ueber einen transienten `systemd-run` Prozess, damit die Funktion mit bestehender Service-Haertung kompatibel bleibt.
  - `ReadWritePaths=` des Control-Plane-Services wurde fuer relevante Let's-Encrypt/nginx-Pfade erweitert.
  - Live auf `srv1.beagle-os.com` verifiziert: API-Issuance erfolgreich, Status meldet `provider=letsencrypt`, Zertifikat vorhanden, nginx TLS aktiv.
- Naechster Schritt:
  - Den Fix ueber neu gebaute Installer-Artefakte ausrollen und einen Regressionstest fuer den Security/TLS-Pfad ergaenzen.
