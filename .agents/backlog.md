# Backlog

Stand: 2026-08-02

## P0

- [x] Agenten-Grundstruktur (`.agents/`, Skills, Policies, `ongoing.md`) eingerichtet.
- [x] Baseline-CI-Entryworkflow (`.github/workflows/ci.yml`) hinzugefuegt.
- [ ] Thinclient Boot-to-Stream fuer Live-USB/Neuinstallation stabilisieren.
	- [x] Lokalen Thinclient `192.168.178.30` reproduzierbar analysiert.
	- [x] Blockierende Manager-Registrierung im direkten BeagleStream-Pfad nonblocking gemacht.
	- [x] Stream-Startanzeige mit Browser-Healthcheck, UI-Log und Dialog-Fallback gehaertet.
	- [x] Heartbeat erkennt `beagle-stream stream` als aktiven Desktop-Stream.
	- [x] Live-USB-Update-Scan defers RAM-Cache-Downloads ohne failed systemd unit.
	- [x] Hotfix auf lokalem Thinclient verifiziert: Stream startet, Heartbeat gruen, `systemctl --failed` leer.
	- [x] Lokalen no-hotpatch Slot-B-Boot fuer ersten Hotfix verifiziert; Rootfs-Fixmarker, Heartbeat und Update-Deferral waren nach Reboot vorhanden.
	- [x] Frischen-Boot Pairing-/TLS-Folgefehler gefunden und Repo-Fix plus Regressionstests ergaenzt.
	- [x] Frischen-Boot Credential-/Token-Folgefehler gefunden: lokale BeagleStream-Client-Credentials fehlten und Manager-Token-Modus lief in PIN-Folgehandshake.
	- [x] Lokales 8.3.18-Bootstreamfix-Payload gebaut und validiert (`filesystem.squashfs=668fed9d...`, Payload-SHA256 `18bb7bfc...`).
	- [x] Thinclient wieder per SSH erreicht und den laufenden VM100-Stream auf genau einen Client-Prozess stabilisiert.
	- [x] VM-scoped USB-Konfiguration im Device-Sync nachgezogen und USB-/Mikrofon-Bridge live validiert.
	- [ ] Neues Thinclient-Artefakt publizieren und frischen Live-USB-/Neuinstallationsstart ohne Hotpatch verifizieren.
- [ ] `srv1` SATA-/Disk-Risiko operativ beheben: beide HGST RAID1-Mitglieder
  kontrolliert ersetzen und Kabel/Controller pruefen; RAID-Rebuild und lange
  SMART-Selbsttests dokumentieren.
- [ ] Release-Versionierungslogik (stable/prerelease) gemaess `projectleader/todo.md` fertigstellen und absichern.
	- [x] `scripts/resolve-release-version.sh`: Stable + Prerelease SemVer akzeptieren, `release_class` ausgeben, 4-part Versionsschema ablehnen.
	- [x] `release.yml`: `release_class` fuer prerelease-spezifisches GitHub Release Verhalten (`--prerelease --latest=false`) verdrahten.
	- [x] Public stable deployment fuer prereleases explizit unterbinden.
	- [x] `scripts/sync-release-version.py` fuer Extension `version`/`version_name` bei prerelease erweitern.
	- [x] Zusatztests fuer Workflow-Gating und Sync-Logik.
	- [ ] CI-Livebeobachtung eines echten prerelease Tags inklusive Mirror- und Release-Verhalten dokumentieren.
	- [x] Thin-client live-build Apt-Retries und `--fix-missing` fuer Paketdownloads gehärtet.
	- [x] Neuen Alpha-Tag auf den gefixten Commit setzen und Release-Run erneut beobachten.
	- [x] Prerelease-Mirror auf separatem Pfad und Download-Seite mit Stable/Prerelease-Kanälen veröffentlicht.
- [ ] CI-Lint-Haertung vorbereiten (warn-only ruff schrittweise in fail-gates ueberfuehren).

## P1

- [ ] Tests fuer frischen VM-Provisioning-Lifecycle erweitern (Create -> Firstboot -> Stream-Ready).
- [ ] Dokumentierte Deploy-Checks fuer aktive Website-Serving-Pfade automatisieren.

## P2

- [ ] Zuschnitt und Priorisierung alter TODOs/Fixmes mit klaren Ownern.
- [ ] Doku-Konsistenz zwischen `projectleader/`, `docs/lasthope/` und `docs/refactor/` weiter verbessern.
