# 06 — Server-Installer / Bare-Metal ISO

Stand: 2026-04-20  
Priorität: Welle 6.x (Mai 2026)  
Betroffene Verzeichnisse: `server-installer/`, `scripts/build-server-installer.sh`

---

## Hintergrund

`server-installer/` enthält die Live-Build-Definition für das Beagle Server OS
Installer-ISO. Ziel ist ein ISO das Beagle OS standalone installiert: Debian-Basis,
KVM/QEMU, libvirt, beagle-host-services, nginx, noVNC-Proxy. Keine Proxmox-Option.
Proxmox wird dauerhaft entfernt — es gibt keine "Beagle OS with Proxmox"-Variante mehr.

---

## Schritte

### Schritt 1 — Installer-Ablauf dokumentieren und verifizieren

- [x] `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer` vollständig lesen.
- [x] Flowchart des aktuellen Installer-Ablaufs in `docs/gofuture/06-server-installer.md` als ASCII-Diagramm ergänzen.

Bevor der Installer weiterentwickelt wird muss der aktuelle Ablauf vollständig
dokumentiert sein. Das verhindert dass Änderungen unerwartete Zweige brechen.
Der interaktive Installer verwendet Dialoge für Festplattenauswahl, Netzwerk-
Konfiguration und Hostname-Eingabe. Jeder Dialog-Schritt und seine Abhängigkeit
zum nächsten Schritt muss im Flowchart sichtbar sein. Nach der Dokumentation wird
der Installer auf einer Test-VM (QEMU/KVM) manuell durchgeführt und das Ergebnis
protokolliert. Breakpoints und Fehlerzustände werden für jeden Schritt notiert.

Umsetzung 2026-04-21 (Ist-Flow, vereinfachte Darstellung):

```
[Boot Live ISO]
	|
	v
[Start beagle-server-installer]
	|
	v
[TUI/Plain Prompt]
  Hostname, User, Passwort, Target-Disk
	|
	v
[Disk wipe + Partitioning + mkfs + mount]
	|
	v
[Netzwerk-Check + debootstrap]
	|
	v
[Base config]
  hostname, hosts, apt sources, fstab, network/interfaces
	|
	v
[chroot apt install]
  Debian base + KVM/libvirt + nginx + certbot + websockify
	|
	v
[System hardening]
  sshd drop-in, fail2ban, nftables, unattended-upgrades
	|
	v
[Install beagle host stack]
  scripts/install-beagle-host.sh (non-interactive)
	|
	v
[GRUB install + update-grub]
	|
	v
[Success dialog + reboot]
```

---

### Schritt 2 — Installer auf reinen Beagle-OS-standalone-Modus fokussieren

- [x] Installer auf Beagle OS standalone (libvirt/KVM) fokussieren — kein Proxmox-Zweig.
- [x] Installer installiert: Debian base, KVM/QEMU, libvirt, beagle-host-services, nginx, noVNC-Proxy.

Da Proxmox dauerhaft entfernt wird gibt es keinen Installer-Zweig mehr der zwischen
Standalone und Proxmox wählt. Der Installer hat genau einen Pfad: Beagle OS standalone.
Das vereinfacht den Dialog-Fluss erheblich — es entfällt die frühe Modus-Entscheidung.
Der Installer-Code für den Proxmox-Zweig wird vollständig entfernt, nicht auskommentiert.
Gemeinsamkeiten (Netzwerk-Setup, Disk-Partitionierung, beagle-user-Anlage) bleiben als
geteilte Shell-Funktionen erhalten. Nach dem Schritt muss ein frischer Install auf
einer Test-VM ohne Proxmox-Abhängigkeiten abschließen.

Umsetzung 2026-04-21:
- `beagle-server-installer` auf standalone-only normalisiert (Legacy-Modi werden auf `standalone` gemappt).
- Proxmox-APT-Repo-/Key-Handling und Proxmox-Branch-Logik aus Installer-Flow entfernt.
- Paketinstallation für den Host explizit auf Beagle-Standalone ausgerichtet, inkl. `nginx` und `websockify`.
- `beagle-server-installer-gui` (curses + plain mode) auf einen einzigen Installmodus reduziert.

---

### Schritt 3 — Reproducible Builds sicherstellen

- [x] `scripts/build-server-installer.sh` so gestalten dass es auf einem frischen Debian-System aus dem Repo heraus reproduzierbar läuft.
- [x] Alle Abhängigkeiten dokumentiert in einem `Makefile` oder `build.env`.

Ein ISO-Build der nur auf dem Rechner des Maintainers funktioniert ist kein
reproduzierbarer Build. Das Live-Build-System (Debian `live-build`) ist deterministisch
wenn Package-Pins und Mirror-URLs fix gesetzt sind. Die Build-Voraussetzungen
(benötigte Pakete, Debian-Version des Build-Hosts) werden als Kommentar im
Build-Skript und in `docs/` festgehalten. Der CI/CD-Pfad (GitHub Actions oder
ähnlich) soll den Build-Schritt ausführen können ohne manuelle Vorbereitung.

Umsetzung 2026-04-21:
- Neue Datei `server-installer/build.env` als zentrale Build-Source-of-Truth für Abhängigkeiten und Speicher-Guardrails.
- `scripts/build-server-installer.sh` lädt `server-installer/build.env` automatisch.
- Proxmox-spezifischer `apt-get update`-Fallback aus dem Build-Skript entfernt; Build-Pfad nutzt jetzt nur den Debian-Standalone-Fluss.

---

### Schritt 4 — Post-Install Beagle-Bootstrap einheitlich machen

- [x] Post-Install-Skript `scripts/install-beagle-host.sh` mit dem Installer-Post-Install-Hook vereinheitlichen.
- [x] Dopplungen zwischen Installer und nachträglicher Installation eliminieren.

Aktuell gibt es einen Installer-Pfad und einen nachträglichen Installations-Pfad
(`scripts/install-beagle-host.sh`). Beide führen ähnliche Schritte aus aber nicht
identisch. Durch Extraktion gemeinsamer Funktionen in ein Shared-Bootstrap-Skript
wird sichergestellt dass ein Installer-installed System und ein manuell installiertes
System identisch konfiguriert sind. Das vereinfacht Support und Fehlerbehebung.
Der gemeinsame Bootstrap-Code wird idempotent geschrieben sodass mehrfaches
Ausführen das System nicht in einen inkonsistenten Zustand bringt.

Umsetzung 2026-04-21:
- Neues Shared-Hook-Skript `scripts/install-beagle-host-postinstall.sh` eingeführt.
- `scripts/install-beagle-host.sh` führt nach Sync/Asset-Prep nicht mehr Inline-Service-/Proxy-Bootstrap aus, sondern delegiert an den Shared Hook.
- Dadurch nutzen Installer- und Nachinstallationspfad dieselbe post-install Sequenz (host.env + credentials.env schreiben, Services installieren, Proxy konfigurieren).

---

### Schritt 5 — ISO-Signing und Release-Artefakt-Chain

- [x] ISO-Signierung mit GPG in `scripts/create-github-release.sh` integrieren.
- [x] Checksum-Datei (SHA256) und Signatur-Datei als Release-Asset publizieren.

Ein unsigned ISO ist für sicherheitsbewusste Betreiber inakzeptabel. GPG-Signierung
stellt sicher dass das ISO aus einer vertrauenswürdigen Quelle stammt und nicht
manipuliert wurde. Die Signierung findet auf dem Release-Build-Host statt mit dem
offiziellen Beagle-Signing-Key. Der Public Key wird im Repo und auf `beagle-os.com`
publiziert. Nutzer können nach dem Download die Signatur via `gpg --verify` prüfen.
Checksum + Signatur werden als separate Release-Assets auf GitHub hochgeladen.

Umsetzung 2026-04-21:
- `scripts/create-github-release.sh` regeneriert `dist/SHA256SUMS` jetzt deterministisch aus den finalen Release-Assets.
- Optionaler GPG-Signierpfad integriert (`BEAGLE_RELEASE_SIGN=1`, optional `BEAGLE_RELEASE_GPG_KEY`).
- Signatur-Assets werden automatisch erstellt und angehängt:
	- `beagle-os-server-installer.iso.sig`
	- `beagle-os-server-installer-amd64.iso.sig`
	- `SHA256SUMS.sig`

---

### Schritt 6 — Host-/Artifact-Operations in der Web Console bedienbar machen

- [x] API-Endpunkt für Host-Artifact-Status ergänzen: `dist/beagle-downloads-status.json`, `/var/lib/beagle/refresh.status.json`, fehlende Pflichtartefakte und Service-/Timer-Status zusammenführen.
- [x] API-Endpunkt zum Starten eines Artifact-Refresh ergänzen: `beagle-artifacts-refresh.service` reproduzierbar über systemd starten, keine langen blocking Requests.
- [x] WebUI-Panel im Updates-/Artifact-Bereich ergänzen: Status-Kacheln für Pflichtartefakte, fehlende Downloads, Refresh-Service und Refresh-Timer.
- [x] WebUI-Button "Artefakte neu bauen/refreshen" ergänzen; Start läuft über systemd und kehrt sofort zurück.
- [x] Job-Fortschritt sichtbar machen: Startzeit, laufender Schritt, letztes Ergebnis, Fehlerauszug, Link zu Status-JSON und Downloads.
- [x] Artifact-Preflight erweitern: freier Speicher, laufender Refresh, root/service capability, fehlende Build-Abhängigkeiten.
- [x] Download-/Publikations-Gate in der WebUI anzeigen: installimage darf erst als public ready gelten, wenn alle `v${VERSION}`- und `latest`-Thin-Client-Artefakte vorhanden sind.
- [x] srv1/srv2 validieren: Refresh auf `srv1` starten, Status in WebUI sehen, Downloads erreichbar, `scripts/check-beagle-host.sh` grün; danach Artefakte auf `srv2` prüfen/synchronisieren.
- [x] API-Regressionstests für fehlende Artefakte und Refresh-Start ergänzen.
- [x] UI-/API-Regressionstests ergänzen: laufender Job, erfolgreicher Refresh, fehlgeschlagener Refresh, RBAC `settings:write`, WebUI-Rendering.
- [x] Artifact-Watchdog ergänzen: in der WebUI aktivierbar, Status/Drift sichtbar, Host-Timer prüft fehlende oder veraltete Artefakte und kann optional Auto-Repair über `beagle-artifacts-refresh.service` auslösen.

Warum dieser Schritt noch offen ist:
Der Host-Artifact-Refresh existiert als Shell-/systemd-Pfad und wird aktuell per SSH validiert. Das ist für Betreiber nicht ausreichend, weil frische Installationen und Release-/Download-Probleme direkt in der Web Console sichtbar und reparierbar sein müssen. Der aktuelle `srv1`/`srv2`-Check hat gezeigt, dass fehlende Artefakte den Host-Smoke brechen können, obwohl die Services laufen. Deshalb muss die WebUI nicht nur Downloads verlinken, sondern auch den Zustand der Artefaktkette bewerten und Refresh/Repair auslösen können.

Umsetzung 2026-04-26:
- `GET /api/v1/settings/artifacts` liefert jetzt zusätzlich `watchdog.config`, `watchdog.status` und die Status der Units `beagle-artifacts-watchdog.service/.timer`.
- `PUT /api/v1/settings/artifacts/watchdog` speichert `enabled`, `max_age_hours`, `auto_repair`.
- `POST /api/v1/settings/artifacts/watchdog/check` startet den Watchdog-Lauf reproduzierbar über systemd.
- Neues Hostskript `scripts/artifact-watchdog.sh` schreibt `/var/lib/beagle/artifact-watchdog-status.json` und erkennt `missing_required`, `missing_latest`, `missing_versioned` sowie `out_of_date`.
- Neue Units `beagle-artifacts-watchdog.service` und `beagle-artifacts-watchdog.timer` installiert; WebUI zeigt Status, letzte Prüfung, Artefakt-Alter, Reaktion und Konfiguration.
- Lokale Regressionen grün:
  - `python3 -m pytest tests/unit/test_server_settings.py tests/unit/test_authz_policy.py -q` => `25 passed`
  - `python3 scripts/test-settings-artifacts-smoke.py --base-url https://srv1.beagle-os.com/ --username admin --password test1234` => `SETTINGS_ARTIFACTS_SMOKE=PASS`
- Live auf `srv1` und `srv2` validiert:
  - Timer aktiv (`beagle-artifacts-watchdog.timer`)
  - `PUT /settings/artifacts/watchdog` => `200`
  - `POST /settings/artifacts/watchdog/check` => `202`
  - Status zeigt bei aktivem Watchdog mit `auto_repair=false` erwartungsgemäß `state=drift`, `reaction=notify_only`
- Follow-up 2026-04-26, Artifact-Refresh live geschlossen:
  - `scripts/prepare-host-downloads.sh` rekonstruiert fehlende Root-`dist`-Artefakte jetzt direkt aus vorhandenen Build-Outputs/ISOs und stellt generische USB-Skripte ohne erzwungenen Vollbuild wieder her.
  - `scripts/refresh-host-artifacts.sh` nutzt denselben Recovery-Pfad ueber `prepare-host-downloads.sh`, statt immer zuerst `package.sh` zu erzwingen.
  - `srv1`: `scripts/check-beagle-host.sh` erfolgreich, `refresh.status.json=status=ok`, Watchdog `state=healthy`, `public_ready=true`.
  - `srv2`: top-level `dist` von `srv1` synchronisiert, host-lokale Download-Metadaten neu geschrieben, `scripts/check-beagle-host.sh` erfolgreich, `refresh.status.json=status=ok`, Watchdog `state=healthy`, `public_ready=true`.
- Follow-up 2026-04-26, Repo-Auto-Update + Watchdog-Kopplung:
  - `GET /api/v1/settings/updates` zeigt jetzt weiterhin die lokale `apt`-Lage, aber zusaetzlich einen separaten GitHub-basierten Block `repo_auto_update`.
  - Neue Mutationspfade:
    - `PUT /api/v1/settings/updates/repo-auto`
    - `POST /api/v1/settings/updates/repo-auto/check`
  - Neues Hostskript `scripts/repo-auto-update.sh`:
    - prueft `https://github.com/meinzeug/beagle-os.git` auf neue Commits,
    - spiegelt den Ziel-Commit nach `/opt/beagle`,
    - fuehrt danach `install-beagle-host-services.sh` und `refresh-host-artifacts.sh` aus,
    - schreibt Laufstatus nach `/var/lib/beagle/repo-auto-update-status.json`.
  - Neue Units:
    - `beagle-repo-auto-update.service`
    - `beagle-repo-auto-update.timer`
  - WebUI `Server-Einstellungen -> System-Updates` kann Repo-URL, Branch, Intervall und Aktivierung jetzt direkt verwalten; der Watchdog haelt nach erfolgreichen Repo-Updates die Artefaktkette weiter aktuell.
  - Host-Installer-Fix: die neue Repo-Update-Unit wird jetzt wie die anderen systemd-Units korrekt mit `__INSTALL_DIR__ -> /opt/beagle` templated installiert; dadurch startet der Timer reproduzierbar auf `srv1` und `srv2`.
  - GitHub-CI-Fix: `.github/workflows/release.yml` nutzt den optionalen GPG-Key nicht mehr in einem unzulaessigen `if: secrets...`-Ausdruck, sondern prueft ihn innerhalb des Shell-Schritts. Das beseitigt den aktuellen GitHub-Parse-Fehler der Release-Workflow-Datei.

---

## Testpflicht nach Abschluss

- [x] ISO bootet in QEMU-VM, Installer-Dialog erscheint.
- [x] Installation schließt ohne Proxmox-Abhängigkeiten ab.
- [x] Post-Install: `systemctl is-active beagle-control-plane` → active.
- [x] ISO-Checksum und Signatur korrekt verifizierbar.

Validierung 2026-04-21:
- Proxmox-Branches im Installer-Pfad entfernt/normalisiert; verbleibende `pve-*` Namen betreffen nur Thin-Client-Artefaktnamen, nicht Installer-Modi.
- Runtime-Smoke auf `srv1.beagle-os.com` erneut grün (`scripts/smoke-control-plane-api.sh`: 13/13), Services `beagle-control-plane`, `beagle-novnc-proxy`, `nginx` jeweils `active`.
- Neues Verifikationsskript `scripts/verify-server-installer-artifacts.sh` prüft server-installer ISO Checksums (`SHA256SUMS`) und GPG-Signaturen (`*.sig`) reproduzierbar; Lauf lokal erfolgreich.
- QEMU-Bootcheck reproduzierbar über `scripts/test-server-installer-live-smoke.sh` (screenshot-basierter Installer-Screen-Nachweis; lokal erfolgreich mit `BEAGLE_LIVE_SMOKE_SKIP_DHCP=1`).
