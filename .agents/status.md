# Autonomous Status

Stand: 2026-06-24

## Session Summary

- Repository-Analyse fuer Stack, CI, Tests, Doku und Risiken erstellt und in `.agents/repo-analysis.md` abgelegt.
- Vollstaendige Agenten-Governance unter `.agents/` inklusive Policies, Skills und Setup-Doku eingerichtet.
- Root-Steuerdateien `AGENTS.md` und `ongoing.md` fuer den autonomen Dauerbetrieb angelegt.
- Erste risikoarme Verbesserung umgesetzt: `.github/workflows/ci.yml` als baseline CI entry workflow hinzugefuegt.
- Lokale Verifikation erfolgreich:
	- `python3 -m pytest -q tests/unit/test_storage_pool_path_regressions.py tests/unit/test_ubuntu_beagle_desktop_profiles.py tests/unit/test_ubuntu_beagle_provisioning_quota.py`
	- `node --check scripts/capture-webui-doc-assets.mjs`
	- `node --check extension/common.js`
	- `node --check extension/content.js`
	- `node --check extension/options.js`

## Aktueller Fokus

- Beagle Thinclient Verwaltung aus dem NetBridge-Tray modernisieren und reparieren.
- Hot-Test auf `srv1`/VM100 mit echtem NetBridge-Agenten, danach Commit/Push auf `main` und Stable-Release-Workflow.
- `/goal`-Tool-Hinweis: Der alte usage-limited Goal-Eintrag konnte mit den verfuegbaren Tools nicht durch das neue Ziel ersetzt werden; der aktive Arbeitsstand wird deshalb hier und in `projectleader/state.md` festgehalten.

## Offene Risiken

- Release-/Versionierungslogik bleibt hoch priorisiert (aus `projectleader/todo.md`).
- Runtime-Gates brauchen weiter reale Host-Evidence.
- `AGENTS.md` ist aktuell in `.gitignore` enthalten; falls versioniert gewuenscht, muss bewusst entschieden werden, ob die Ignore-Regel angepasst oder `git add -f` genutzt wird.

## Naechster sinnvoller Schritt

Thinclient-Verwaltungsfix final committen, auf `main` pushen und danach `release.yml` fuer den Stable-Release neu starten.

## Session Update 2026-06-01 (Release Resolver Slice)

- Analysiert: `scripts/resolve-release-version.sh`, `tests/unit/test_release_workflow_regressions.py`, `projectleader/todo.md`, Release-Workflows.
- Geaendert: `scripts/resolve-release-version.sh` akzeptiert nun Stable und Prerelease-SemVer (`alpha|beta|rc`) und schreibt `release_class` in GitHub-Outputs.
- Geaendert: Neuer Regressionstest `tests/unit/test_resolve_release_version_script.py` fuer stable/prerelease/tag-ref/invalid-4-part.
- Getestet:
	- `bash -n scripts/resolve-release-version.sh`
	- `python3 -m pytest -q tests/unit/test_resolve_release_version_script.py tests/unit/test_release_workflow_regressions.py`
	- Ergebnis: `8 passed`.
- Offenes Risiko: Workflow-Gating fuer Prerelease-Publishing (`--prerelease --latest=false` und Public-Deploy-Bypass) ist noch offen.
- Naechster Schritt: `release.yml` und `public-website.yml` auf `release_class` verdrahten und mit Regressionstests absichern.

## Session Update 2026-06-01 (Release Channel Wiring + Extra Tasks)

- Analysiert: `.github/workflows/release.yml`, `.github/workflows/public-website.yml`, `scripts/sync-release-version.py`, `scripts/create-github-release.sh`.
- Geaendert: Release-Workflow nutzt `release_class` fuer GitHub Release Flags (`--prerelease --latest=false`) und blockiert `deploy-public-artifacts` fuer Prereleases.
- Geaendert: Public-Website-Workflow erkennt Prerelease-Versionen und ueberspringt Deployment/Verifikation fuer Prereleases.
- Geaendert: `scripts/sync-release-version.py` akzeptiert Prerelease-SemVer, synchronisiert Root/Kiosk/WebUI mit voller Produktversion und setzt Extension `version` numerisch (Core) plus `version_name` (voll).
- Geaendert (zusatz): `scripts/create-github-release.sh` mit `BEAGLE_RELEASE_CLASS` + stabilen/prerelease Release-Flags.
- Tests (zusatz):
	- `tests/unit/test_sync_release_version.py`
	- `tests/unit/test_public_website_workflow_regressions.py`
	- `tests/unit/test_create_github_release_script_regressions.py`
	- Erweiterung `tests/unit/test_release_workflow_regressions.py`
- Getestet:
	- `bash -n scripts/resolve-release-version.sh`
	- `bash -n scripts/create-github-release.sh`
	- `python3 -m pytest -q tests/unit/test_resolve_release_version_script.py tests/unit/test_sync_release_version.py tests/unit/test_release_workflow_regressions.py tests/unit/test_public_website_workflow_regressions.py tests/unit/test_create_github_release_script_regressions.py`
	- Ergebnis: `17 passed`.
- Offenes Risiko: Full-E2E fuer echte prerelease Publish-Runs in GitHub Actions muss nach PR-Merge beobachtet werden.
- Naechster Schritt: PR erstellen/aktualisieren und auf CI-Checks warten; danach auto-merge nur bei komplett gruenen Pflichtchecks.

## Session Update 2026-06-01 (Thin-Client Installer Hardening)

- Analysiert: `scripts/build-thin-client-installer.sh`, thin-client live-build hooks `007-install-dcv-viewer.hook.chroot` und `008-install-beagle-stream-client.hook.chroot`, sowie `tests/unit/test_thin_client_live_build_regressions.py`.
- Geaendert: Chroot-Apt-Konfiguration fuer live-build um `Acquire::Retries=5` und `Acquire::https::Timeout=60` ergaenzt.
- Geaendert: Beide paketinstallierenden Live-Hooks nutzen jetzt Retry-Wrapper und `apt-get install --fix-missing --no-install-recommends`.
- Geaendert: Regressionstests decken die neuen Retry-Guards und die Apt-Config ab.
- Getestet:
	- `bash -n thin-client-assistant/live-build/config/hooks/live/007-install-dcv-viewer.hook.chroot`
	- `bash -n thin-client-assistant/live-build/config/hooks/live/008-install-beagle-stream-client.hook.chroot`
	- `python3 -m pytest -q tests/unit/test_thin_client_live_build_regressions.py`
	- Ergebnis: `34 passed`.
- Offenes Risiko: Der bereits gestartete `v8.3.10-alpha.1` Run verwendet den alten Stand; der gefixte Stand braucht einen neuen Alpha-Tag.
- Naechster Schritt: Commit + Push des Fixes, dann neuen Prerelease-Tag auf den gefixten Commit setzen.

## Session Update 2026-06-01 (Prerelease Downloads on Public Site)

- Analysiert: `scripts/publish-public-update-artifacts.sh`, `public-site/download/index.html`, `public-site/assets/js/build-status.js`, `.github/workflows/public-website.yml`, `.github/workflows/release.yml`.
- Geaendert: Der Public-Mirror publiziert jetzt stabile und prerelease Artefakte getrennt:
	- stable bleibt unter `beagle-downloads-status.json` und den bisherigen Top-Level-URLs;
	- prereleases publizieren unter `beagle-downloads-prerelease-status.json` und `beagle-updates/prereleases/<version>/`.
- Geaendert: Die Download-Seite zeigt jetzt stabile und prerelease Kanäle nebeneinander und laedt beide per Widget.
- Geaendert: `public-website.yml` und `release.yml` erlauben Prerelease-Deploys wieder, damit Alpha/Beta/RCs sichtbar veröffentlicht werden.
- Getestet:
	- `bash -n scripts/publish-public-update-artifacts.sh`
	- `node --check public-site/assets/js/build-status.js`
	- `python3 -m pytest -q tests/unit/test_public_website_workflow_regressions.py tests/unit/test_release_workflow_regressions.py tests/unit/test_download_page_release_channel_regressions.py tests/unit/test_publish_public_update_artifacts_prerelease_regressions.py`
	- Ergebnis: `12 passed`.
- Offenes Risiko: Der neue Prerelease-Run muss bis zum Ende beobachtet werden, um die separaten Mirror-URLs live zu verifizieren.
- Naechster Schritt: Alpha-Run `v8.3.10-alpha.2` fertig beobachten und danach Live-Links/Artefaktpfade gegen die Public-Mirror-URLs pruefen.

## Session Update 2026-06-23 (Thinclient Boot-to-Stream Hotfix)

- Analysiert: lokaler Thinclient `192.168.178.30` per SSH, Live-Boot `runtime`, Version `8.3.17`, Update-Feed `latest_version=8.3.18`.
- Reproduziert:
	- Stream wurde grundsaetzlich erfolgreich gestartet, aber erst nach blockierendem `beagle-stream-client.register-wait attempt=1/30 ... 30/30`.
	- Die 10-Schritt-Startanzeige hatte keine verwertbare UI-Diagnose und konnte bei Browser-Crash still verschwinden.
	- `beagle-runtime-heartbeat` meldete `beagle-stream-client=0`, obwohl der neue `beagle-stream stream ...` Prozess lief.
	- `beagle-update-scan.service` blieb failed, wenn der Live-USB-Updatecache wegen vollem Medium auf RAM zurueckfiel.
- Geaendert:
	- `thin-client-assistant/runtime/launch-beagle-stream-client.sh`: Manager-Registrierungs-Wait ist standardmaessig nonblocking (`REGISTER_WAIT_REQUIRED=0`), die Startanzeige prueft den Browserprozess, loggt nach `beagle-stream-client-startup-ui.log` und faellt auf `zenity`/`xmessage` zurueck.
	- `beagle-os/overlay/usr/local/sbin/beagle-runtime-heartbeat`: erkennt auch `beagle-stream stream` und nutzt denselben tmpfs/device-sync Pfad wie die Live-Heartbeat-Variante.
	- `beagle-os/overlay/usr/local/sbin/beagle-update-client`: Live-USB/RAM-Cache-Deferral wird als `state=deferred` mit Exit 0 behandelt, statt den systemd Scan als failed zu markieren.
	- Regressionstests fuer Register-Wait, Startanzeige-Fallback, Heartbeat und Update-Deferral ergaenzt.
- Getestet lokal:
	- `bash -n thin-client-assistant/runtime/launch-beagle-stream-client.sh`
	- `bash -n beagle-os/overlay/usr/local/sbin/beagle-runtime-heartbeat`
	- `python3 -m py_compile beagle-os/overlay/usr/local/sbin/beagle-update-client`
	- `python3 -m pytest -q tests/unit/test_endpoint_update_self_heal_regressions.py tests/unit/test_thin_client_live_build_regressions.py tests/unit/test_launch_beagle_stream_client_runtime.py tests/unit/test_beagle_stream_client_pairing_runtime.py tests/unit/test_stream_auto_quality_runtime.py`
	- Ergebnis: `87 passed`.
	- `python3 -m pytest -q tests/integration/test_endpoint_boot_to_streaming.py`
	- Ergebnis: `18 passed`.
- Getestet auf Thinclient:
	- Hotfix-Skripte installiert und laufenden Stream-Launcher neu gestartet.
	- Neuer Ablauf: `ready` -> `register-wait-skip` statt 30 blockierende Versuche.
	- Chromium-Startanzeige lief als Kiosk-Prozess und schrieb `beagle-stream-client-startup-ui.log`.
	- Neuer `beagle-stream` Prozess verbunden mit erster Video-/Audio-Session nach RTSP-Handshake.
	- Heartbeat meldete danach `beagle-stream-client=1`.
	- `beagle-update-client scan --auto-apply-if-idle` endete mit `scan_rc=0`, `state=deferred`; `systemctl --failed` leer.
- Offenes Risiko:
	- Die Verifikation ist ein Hotfix auf dem laufenden Thinclient, noch kein frisch gebautes/publiziertes Live-USB- oder Installationsartefakt.
	- Shellcheck fuer den grossen Launcher zeigt bestehende Warnungen (`SC2034`, `SC2024`, `SC2155`, `SC2015`), keine neu isolierte Runtime-Regression; Heartbeat ist syntaktisch sauber.
- Naechster Schritt:
	- Commit/PR fuer den Hotfix, danach neues Thinclient-Artefakt bauen/publizieren und den lokalen Thinclient von diesem Artefakt frisch booten bzw. neu installieren.

## Session Update 2026-06-23 (Thinclient No-Hotpatch Slot-B Attempt)

- Thinclient-eMMC analysiert: installiertes A/B-Layout mit `live/current -> a`, leerem Slot `b` und ca. 5 GB freiem Platz auf `BEAGLEROOT`.
- Lokalen Slot `b` aus Slot `a` gebaut und die ersten Hotfix-Dateien ins SquashFS integriert; Checksummen und Readback aus dem neuen SquashFS waren erfolgreich.
- No-hotpatch-Reboot von `live/current -> b` verifiziert:
	- Neuer Boot-ID: `33ae60e3-286b-4281-95f3-5e5f82bf123b`.
	- `/run/live/medium/live/current -> b`.
	- Gebootetes `filesystem.squashfs` hatte Hash `1640ec0dd62169af8833bdf0d902bc6ad56681b50d6cbff5c92c86d3bc9362ba`.
	- Repo-Fixmarker fuer Launcher, Heartbeat und Update-Deferral waren im gebooteten Rootfs vorhanden.
	- Heartbeat meldete `xorg=1`, `openbox=1`, `beagle-stream-client=1`; `systemctl --failed` blieb leer.
	- `beagle-update-client scan --auto-apply-if-idle` endete erneut mit `scan_rc=0`, `state=deferred`, `latest_version=8.3.18`.
- Neuer frischer-Boot-Befund:
	- Der Launcher erreichte `beagle-stream-client.exec`, aber der Stream-Log zeigte nach frischem Boot `No existing credentials found`, `QNetworkReply::SslHandshakeFailedError` und `Failed to find application Desktop`.
	- Ursache im Runtime-Pfad: `PairStatus=1` wurde als ready akzeptiert, obwohl die lokale BeagleStream-Host-Konfiguration noch keinen Server-Cert-Eintrag (`srvcert`) hatte; der Streamprozess blieb trotz App-/TLS-Fehlern am Leben, sodass die bestehende Repair-Logik nicht griff.
- Repo-Fix ergaenzt:
	- `beagle_stream_client_stream_ready` akzeptiert `PairStatus=1` nur noch, wenn `beagle_stream_client_host_configured` erfolgreich ist oder `sync_beagle_stream_client_host_from_serverinfo_probe` die lokale Host-Konfiguration reparieren kann.
	- Der Stream-Watchdog im Launcher beendet laufende Streamprozesse bei App-/TLS-/Pairing-Fehlern im Log gezielt mit `beagle-stream-client.repair-trigger`, damit die vorhandene Restart-/Repair-Schleife sofort laeuft.
	- Neue Regressionstests fuer PairStatus-ohne-lokalen-Cert und den Repair-Trigger.
- Getestet lokal:
	- `bash -n thin-client-assistant/runtime/launch-beagle-stream-client.sh thin-client-assistant/runtime/beagle_stream_client_pairing.sh`
	- `python3 -m pytest -q tests/unit/test_endpoint_update_self_heal_regressions.py tests/unit/test_thin_client_live_build_regressions.py tests/unit/test_launch_beagle_stream_client_runtime.py tests/unit/test_beagle_stream_client_pairing_runtime.py tests/unit/test_stream_auto_quality_runtime.py tests/integration/test_endpoint_boot_to_streaming.py`
	- Ergebnis: `108 passed`.
- Blocker:
	- Zweiter Slot-`b`-Rebuild fuer den Pairing-Fix wurde gestartet, dabei wurde das Medium vorab auf `live/current -> a` zurueckgesetzt und der alte Slot `b` entfernt.
	- Der Remote-`unsquashfs`-Schritt hing danach; lokaler SSH-Abbruch beendete den Thinclient-Zugriff nicht sauber.
	- Thinclient pingt weiter und TCP/22 ist offen, aber sshd sendet keinen SSH-Banner mehr. Remote Cleanup/Reboot ist aktuell nicht moeglich.
	- Naechster Schritt nach manuellem Power-Cycle oder wenn SSH wieder antwortet: `/mnt/beagle-root` mounten, temporaere `build-rootfs-slot-b-*`/`b.new-*` entfernen, Slot `b` mit dem Pairing-Fix neu bauen und erneut no-hotpatch booten.

## Session Update 2026-06-24 (Thinclient Credential Bootstrap + Local Payload)

- Zweiter no-hotpatch-Boot aus lokalem 8.3.18-Slot `b` wurde erreicht, aber der frische Start blieb bei Pairing-Schritt 6 haengen:
	- Boot-ID: `0b9ab391-43db-42ab-9922-947cee64985a`.
	- `/run/live/medium/live/current -> b`.
	- Gebootetes `filesystem.squashfs`: `d3fd03989412f92ad9c58dd9f5c1027090330d5cf246fb38f93a1983cb7689b2`.
	- Xorg/Openbox/Startup-UI liefen und `systemctl --failed` war leer.
	- Pairing-Log wiederholte `pair-token acquired via manager`, danach `pair-exchange failed via manager; trying direct submit`.
- Neue Ursache:
	- Frische BeagleStream-Clients hatten noch keine lokale QSettings-Konfiguration mit Client-Zertifikat/Key/`uniqueid`.
	- Der Manager antwortete im Token-Modus; der Runtime-Pfad erwartete weiter PIN-Kompatibilitaet und startete dadurch einen falschen Folge-Handshake.
- Repo-Fix ergaenzt:
	- `ensure_beagle_stream_client_config` erzeugt vor Manager-Register/Pairing/Direct-Stream eine minimale lokale BeagleStream-Konfiguration mit selbstsigniertem Client-Zertifikat, Key und stabiler `uniqueid`.
	- Explizite `PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_CONFIG` Pfade werden nicht mehr still ignoriert, wenn sie unlesbar sind.
	- Manager-`pairing_mode=token` wird als akzeptierter Exchange behandelt; PIN-Folgehandshake laeuft nur noch fuer `pin-compat`.
	- Launcher loggt `beagle-stream-client.credentials-ready` vor Direct-/Hostless-Stream und bereitet Credentials auch im Register-Wait-Pfad vor.
- Korrigiertes lokales 8.3.18-Payload gebaut und validiert:
	- Rootfs: `668fed9d3def1ae57360d4f12b1a16523143caf0eaccd113bd78a8497506776e`.
	- Kernel: `4cc864b8e34c86c281f66b36157a52945a95a1b290762245c608b7c7e3934a11`.
	- Initrd: `65852b4959ca7a995befa5b4a75719ca613d2f59e961aae06e83105ea0eb9d7e`.
	- Payload: `.tmp-thinclient-fix/20260623/pve-thin-client-usb-payload-v8.3.18-bootstreamfix-20260623.tar.gz`.
	- Payload-SHA256 nach aktuellem Workspace-Rebuild: `18bb7bfc6c2bb350c01f8fd181f212bf573e546156c5fb78e23975c35001c94c`.
	- Archivstruktur, `SHA256SUMS`, `gzip -t` und SquashFS-Marker fuer Credential-/Token-Fix erfolgreich geprueft.
- Getestet lokal:
	- `bash -n thin-client-assistant/runtime/beagle_stream_client_config_state.sh thin-client-assistant/runtime/beagle_stream_client_pairing.sh thin-client-assistant/runtime/beagle_stream_client_manager_registration.sh thin-client-assistant/runtime/launch-beagle-stream-client.sh scripts/prepare-host-downloads.sh`
	- `python3 -m pytest -q tests/unit/test_prepare_host_downloads_status_regressions.py tests/unit/test_beagle_stream_client_pairing_runtime.py tests/unit/test_beagle_stream_pairing_broker_bypass_regression.py tests/unit/test_launch_beagle_stream_client_runtime.py tests/unit/test_endpoint_update_self_heal_regressions.py tests/unit/test_thin_client_live_build_regressions.py tests/unit/test_stream_auto_quality_runtime.py tests/integration/test_endpoint_boot_to_streaming.py`
	- Ergebnis: `120 passed`.
	- `git diff --check` sauber.
	- ShellCheck fuer die geaenderten Shell-Skripte hat nur bestehende Warnungen in `prepare-host-downloads.sh`/`launch-beagle-stream-client.sh` gemeldet; die neuen Repack-Trap-Warnungen wurden bereinigt.
- Aktueller Blocker:
	- Thinclient pingt lokal weiter, WireGuard-Handshakes ueber `srv1` bleiben frisch und TCP/22 ist offen.
	- SSH sendet aber keinen Banner mehr; NetBridge/47100 ist lokal `Connection refused` und ueber WireGuard nicht erreichbar.
	- Korrigiertes `668fed...` Slot-Image ist noch nicht auf dem Thinclient installiert/gebootet.
	- Naechster Schritt: physischen Power-Cycle ausloesen, direkt im fruehen Bootfenster per SSH Slot `b` durch die lokalen `668fed...` Live-Dateien ersetzen und danach den frischen no-hotpatch Boot-to-Stream beweisen.

## Session Update 2026-06-24 (Thinclient Verwaltung Modernisierung)

- Analysiert: `beagle-host/netbridge/beagle-thinclient-admin`, `beagle-host/netbridge/beagle-netbridge-tray` und NetBridge-Control-Fluss aus VM100 zum Thinclient-Agenten.
- Ursache fuer "keine Daten": Der Admin nutzte den Thinclient-Statuspfad ueber den Tray-Backend-Client, aber der generische 6s-Control-Timeout war fuer vollstaendige Statusantworten zu knapp. Der Statuspfad nutzt jetzt laengere, konfigurierbare Timeouts.
- Geaendert:
	- Thinclient-Verwaltung auf modernes Dashboard mit Header, Status-Pills, Uebersichtskarten, Quick-Actions, klaren Tabs, alternierenden Tabellenzeilen und Diagnoseansicht umgebaut.
	- Live-Details in der Uebersicht zeigen jetzt explizit `Bereich | Status | Details`, statt Status und Detailwerte zu vermischen.
	- Stream-Profilverwaltung erweitert: Presets plus editierbares Custom-Profil fuer Aufloesung, FPS, Bitrate, Paketgroesse, Codec, Decoder, Frame-Pacing, VSync und absolute Maus.
	- `--selftest` und `--screenshot` Smoke-Modus fuer reproduzierbare VM100-Pruefungen ergaenzt.
	- Tray-Backend unterstuetzt laengere Status-/Action-/Long-Action-Timeouts sowie Custom-Streamprofile.
- Getestet lokal:
	- `python3 -m py_compile beagle-host/netbridge/beagle-thinclient-admin beagle-host/netbridge/beagle-netbridge-tray beagle-host/netbridge/beagle-netbridge-agent`
	- `python3 -m pytest -q tests/unit/test_beagle_netbridge_regressions.py tests/unit/test_sync_release_version.py tests/unit/test_release_workflow_regressions.py`
	- `git diff --check`
	- Ergebnis: `26 passed`, Diff-Check sauber.
- Getestet auf `srv1`/VM100:
	- Aktuelle Admin-/Tray-Dateien per QEMU Guest Agent nach VM100 deployt.
	- `/usr/local/bin/beagle-thinclient-admin --selftest`: `agent_status: ok host=10.88.1.1`, Thinclient-Sektionen `audio,network,services,stream,update,usb,video`.
	- `/usr/local/bin/beagle-netbridge-tray --selftest`: `agent_host: 10.88.1.1`, `stream_profile: custom`.
	- Offscreen-Screenshot in VM100 erzeugt: `.tmp-thinclient-admin-smoke.png` mit sichtbaren Uebersichtsstatuswerten.
- Zusatzbefund:
	- Direkter lokaler Zugriff auf `192.168.178.30:47100` ist `Connection refused`; der produktive VM/WireGuard-Pfad `10.88.1.1:47100` funktioniert.
	- `v8.3.19` war bereits auf GitHub veroeffentlicht; der Abschluss-Release fuer diese Aenderung wird deshalb als `8.3.20` vorbereitet.

## Session Update 2026-06-24 (Thinclient Verwaltung Tab-Nachbesserung)

- Release-Run `28087083296` fuer Commit `2f7f73d5` auf Benutzeranweisung abgebrochen; GitHub-Status danach `completed/cancelled`.
- In VM100 fuer alle Reiter Screenshots erzeugt und lokal unter `.tmp-thinclient-tabs/` abgelegt.
- Befund aus den Screenshots:
	- `Updates`: Aktionsbuttons waren abgeschnitten.
	- `USB/AV`: USB-Geraete wurden als Platzhalter/IDs und Audio als rohes JSON angezeigt.
	- `Geraete`: keine LAN-Geraete und kein sinnvoller Leerzustand; manuelle Anlage war nur ueber Dialog erreichbar.
	- `Dienste`/`Netzwerk`: Daten vorhanden, aber ohne verwertbare Zusammenfassung.
- Nachbesserung:
	- Update-, Stream-, Dienste-, USB/AV- und Netzwerk-Reiter mit Statuskarten ergaenzt.
	- Update-Aktionen auf kurze Grid-Buttons umgestellt, keine abgeschnittenen Texte mehr.
	- LAN-Geraete-Reiter mit Inline-Formular fuer Name, Adresse, Typ, Port und IPP-Pfad.
	- Leere Tabellen erhalten sichtbare Leerzustandskarten.
	- USB/AV zeigt lesbare Bus-ID/Status/Geraet/Kennung und Audio-Details statt JSON.
	- Dienstetabelle waehlt den Dienst fuer Start/Restart direkt ueber die markierte Zeile.
- Hot-Test auf VM100:
	- `/usr/local/bin/beagle-thinclient-admin --selftest`: `agent_status: ok host=10.88.1.1`.
	- Alle acht Reiter erneut als VM100-Screenshots erzeugt; kritische Reiter `Updates`, `USB/AV`, `Geraete`, `Dienste`, `Netzwerk`, `Stream` visuell geprueft.
- Getestet lokal:
	- `python3 -m py_compile beagle-host/netbridge/beagle-thinclient-admin beagle-host/netbridge/beagle-netbridge-tray beagle-host/netbridge/beagle-netbridge-agent`
	- `python3 -m pytest -q tests/unit/test_beagle_netbridge_regressions.py`
	- `git diff --check`
	- Ergebnis: `17 passed`, Diff-Check sauber.
