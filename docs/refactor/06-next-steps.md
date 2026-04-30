# Next Steps

## Stand (2026-04-30, Streaming-R3-Rest nach Audit-Smoke weiter eingegrenzt)

**Zuletzt erledigt**:
- `STREAM_HEALTH_AUDIT_SMOKE=PASS` auf `srv1`; damit sind Stream-Health-Persistenz und Audit-Update-Pfad jetzt auch live zusammen nachgewiesen.
- Der WebUI-Live-Feed zeigt bei SSE-Abbruch jetzt ein sichtbares Reconnect-Warnbanner und protokolliert den Reconnect-Versuch im Activity-Log.

**Naechste konkrete Schritte**:

1. Den sichtbaren WebUI-Reconnect nach Host-/VM-Reboot browserseitig gegen `srv1` abnehmen und erst dann den offenen R3-WebUI-Punkt schliessen.
2. Parallel VM102 im Provider-State reparieren; erst danach ist der verbliebene Dual-VM-Readiness-Nachweis komplett schliessbar.
3. Den neuen Timeout-Audit-Smoke (`scripts/test-stream-timeout-audit-smoke.py`) in den kombinierten Streaming-Regression-Run aufnehmen, damit der Nachweis bei kuenftigen Deployments automatisch mitlaeuft.

---

## Stand (2026-04-30, Sunshine/Moonlight-Smokes auf srv1 mit VM102-Blocker)

**Zuletzt erledigt**:
- Die live fahrbaren Sunshine/Moonlight-Smokes auf `srv1` sind fuer VM100 erneut mit PASS-Nachweisen gelaufen (`STREAM_HEALTH_ACTIVE_RESULT=PASS`, `STREAM_INPUT_MATRIX_RESULT=PASS`, `MOONLIGHT_AUTO_PAIR_RESULT=PASS` im Headless-Degraded-Modus, `PLAN01_STREAM_VM_REGISTER=PASS`, `ensure-vm-stream-ready` mit `RC=0`).
- Die Smoke-Skripte wurden fuer den realen Guest-User-/Xauthority-Pfad und fuer Headless-Pairing ohne aktiven Moonlight-Client gehaertet.

**Naechste konkrete Schritte**:

1. VM102 im Provider-State auf `srv1` reparieren (neu registrieren oder neu provisionieren), bis `guest_exec` und `guest_ipv4` wieder funktionieren.
2. Danach den offenen Dual-VM-Nachweis erneut fahren: `ensure-vm-stream-ready.sh --vmid 100 --node beagle-0` und `--vmid 102 --node beagle-0` mit beiden Erfolgsmarkern.
3. Optional den Public-Self-Check-Pfad (`46.4.96.80:50001`) netzseitig absichern oder als erwartete Host-External-Limitation dokumentiert halten, solange der direkte VM-API-Check und Readiness-State gruen bleiben.

---

## Stand (2026-04-30, Ubuntu-Desktop-Firstboot-/Login-Drift auf srv1 geschlossen)

**Zuletzt erledigt**:
- Der Ubuntu-Desktop-Firstboot fuer WebUI-provisionierte VMs heilt jetzt unterbrochene `apt/dpkg`-Zustaende reproduzierbar, sodass der Abschluss-Callback, der finale Gast-Reboot und das LightDM-/Desktop-Setup fuer den angelegten Benutzer nicht mehr in halbfertigen Paketketten haengenbleiben.

**Naechste konkrete Schritte**:

1. Einen frischen Ubuntu-Desktop-VM-Create auf `srv1` komplett durchspielen und verifizieren, dass der Gast nach der Installation ohne manuellen Eingriff neu startet und direkt mit vollstaendigem Desktop-Login-Setup hochkommt.
2. Fuer denselben Pfad einen reproduzierbaren End-to-End-Smoke ergaenzen, der `ubuntu-firstboot.done`, LightDM-Config und Guest-Reboot fuer eine frisch provisionierte VM explizit prueft.
3. Den gleichen Firstboot-Template-Stand auf `srv2` spiegeln, bevor dort weitere Ubuntu-Desktop-Test-VMs ueber die WebUI erzeugt werden.

---

## Stand (2026-04-30, WebUI-Timeout-Drift nach TLS-Reload auf srv1 geschlossen)

**Zuletzt erledigt**:
- Der Post-Let's-Encrypt-Folgebug ist geschlossen: Control-Plane-Responses behandeln nginx-seitig abgebrochene Reload-Verbindungen jetzt sauber als Disconnect statt als 500, und idempotente WebUI-Reads retryen transiente Netzwerkabbrueche einmal automatisch.

**Naechste konkrete Schritte**:

1. Den kompletten Security-Flow in der echten WebUI noch einmal interaktiv gegen `srv1` abnehmen: neues Let's-Encrypt anstossen, danach direkt Login + `/#panel=policies` + `/#panel=settings_security` ohne Timeout-Console-Fehler pruefen.
2. Den gleichen Handler-/Retry-Stand bei der naechsten Runtime-Synchronisation auch auf `srv2` spiegeln.
3. Optional einen kleinen Browser-Smoke fuer den Reload-Moment ergaenzen, der nach erfolgreichem TLS-POST explizit einen `auth/me`-/Panel-Refresh gegen den umgeschalteten Host prueft.

---

## Stand (2026-04-30, WebUI-Let's-Encrypt-TLS-Switch auf srv1 wieder funktionsfaehig)

**Zuletzt erledigt**:
- Der WebUI-Fehler `certificate issued but nginx switch failed` ist geschlossen: der aktive TLS-Write-Pfad ist jetzt fuer `beagle-control-plane` beschreibbar, und der Let's-Encrypt-Switch ersetzt die PEM-Dateien atomar.

**Naechste konkrete Schritte**:

1. Den echten WebUI-Flow unter `/#panel=settings_security` einmal mit einem frischen Operator-Run gegen `srv1` nachziehen und die Success-Meldung plus aktives LE-Zertifikat im Browser abnehmen.
2. Diesen TLS-Permissions-/Switch-Smoke fuer frische Host-Installationen reproduzierbar ergaenzen, damit `certificate issued but nginx switch failed` nicht wieder unbemerkt zurueckkommt.
3. Den gleichen Proxy-Installer-Stand auf `srv2` spiegeln, sobald dort erneut Security-/TLS-Settings live bedient werden.

---

## Stand (2026-04-30, srv1 Neuinstallations-Onboarding wiederhergestellt)

**Zuletzt erledigt**:
- Der Reinstall-/Onboarding-Drift auf `srv1` ist geschlossen: Secret-Store-Startcrash behoben, Auth-State gezielt in Pending-Onboarding zurueckgesetzt und der Installer konserviert den Bootstrap-/Onboarding-Modus jetzt reproduzierbar.

**Naechste konkrete Schritte**:

1. Den neuen Reinstall-Pfad einmal mit einem echten frischen Server-Installer-Artefakt in einer Test-VM durchspielen und verifizieren, dass `users.json`/`onboarding.json` nicht vorzeitig entstehen.
2. Dieselbe Reset-/Bootstrap-Logik auf `srv2` spiegeln, falls dort ebenfalls frische Host-Rebuilds oder Test-Neuinstallationen anstehen.
3. Fuer den Server-Installer einen reproduzierbaren Smoke ergaenzen, der nach dem ersten WebUI-Load explizit `pending: true` plus sichtbares Onboarding-Modal prueft.

---

## Stand (2026-04-29, Enterprise-Readiness Doku-Konsolidierung abgeschlossen)

**Zuletzt erledigt**:
- Doku auf 5 thematische Checklisten konsolidiert: `docs/checklists/01..05-*.md`. Jede Aufgabe gegen Repo verifiziert.
- 5 alte Plan-Verzeichnisse (`refactorv2`, `gofuture`, `goenterprise`, `goadvanced`, `gorelease`) per `git mv` nach `docs/archive/` verschoben.
- `docs/README.md` (zentrale Navigation) + `docs/STATUS.md` (Ampel + Release-Gates).
- `MASTER-PLAN.md` Section 2 + 3 auf neue Struktur umgebaut, alle Pfade auf `docs/archive/...` aktualisiert.
- Top-Level-Doks in Subordner einsortiert (`deployment/`, `architecture/`, `security/`).
- `scripts/check-gofuture-complete.sh` → `scripts/check-checklists-complete.sh` (generisch).
- **CI-Live-Fix**: `tests.yml` faehrt jetzt Integration-Tests (`tests/integration/`, 89 Tests, lokal verifiziert).

**Naechste konkrete Schritte (Reihenfolge)**:

1. **Runbook-Skelette**: `docs/runbooks/{installation,update,rollback,backup-restore,incident-response,pilot}.md` anlegen — entsperrt R4.
2. **Frische ISO-Installation**: auf leerem Hetzner-Host live durchfuehren, `scripts/check-beagle-host.sh` gruen — entsperrt R1.
3. **Cluster-Smoke** auf `srv1`+`srv2`: Join + Drain + Failover + Live-Migration mit echter Latenz — entsperrt R2.
4. **GPU-Server** bei Hetzner buchen, IOMMU/VFIO/libvirt verifizieren — entsperrt R3.
5. **Externes Pen-Test-Engagement** vorbereiten (Scope, Termin, Vertrag) — entsperrt R4.
6. **Plan 12 i18n-Migration weiter**: `auth_admin.js`, `vms_panel.js` auf `t()` umstellen (Item in [`docs/checklists/04-quality-ci.md`](04-quality-ci.md) erfasst).
7. **VM102 Provider-State** auf `srv1` reparieren, dann `ensure-vm-stream-ready.sh --vmid 102` fahren.

---

## Historische Stand-Eintraege (vorher)



**Zuletzt erledigt**:
- Laufzeitfixes fuer den Stream-Ready-Pfad deployed (`PYTHONPATH`-Bootstrap in `ensure-vm-stream-ready.sh` + `configure-sunshine-guest.sh`, SCP-Zielpfad weg von `/tmp`).
- `srv1`-Rerun gegen VM100 war erfolgreich.
- VM102 bleibt als externer Runtime-Blocker offen (`VM 102 not found in beagle provider state`, keine Guest-IP).

**Naechste konkrete Schritte**:

1. Auf `srv1` die VM102-Inventar-/Provider-State-Diskrepanz beheben (VM neu registrieren oder neu provisionieren), bis `beagle_provider` wieder `guest-exec`/`guest-ipv4` liefern kann.
2. Danach den offenen Pflicht-Run erneut fahren: `scripts/ensure-vm-stream-ready.sh --vmid 100 --node beagle-0` und `--vmid 102 --node beagle-0`.
3. Erst nach dualem PASS den offenen Sunshine/Moonlight-TODO in `08-todo-global.md` auf `[x]` setzen und die restliche first-boot readiness gate Validierung (`clean VM100/101`) weiterziehen.

## Stand (2026-04-29, Plan-07 5GB Backup-Lasttest auf srv1 geschlossen)

**Zuletzt erledigt**:
- Neuer Lasttest `scripts/test-backup-load-5gb-smoke.sh` fuehrt einen expliziten 5GB-Backup-Run ueber die Async-Queue aus und validiert den Snapshot-/Job-Nachweis.
- `backup_service.py` ist fuer Live-Hosts gehaertet: lesbare Manifest-Liste fuer tar, tolerante Behandlung nicht-fataler tar-Warnungen.
- Live auf `srv1`: `BACKUP_LOAD_5GB_SMOKE=PASS`.

**Naechste konkrete Schritte**:

1. Den verbleibenden clean-install Host-Validierungspunkt schliessen: noVNC/XFCE/API/Downloads end-to-end auf frisch installiertem Server-Installer-Host abnehmen.
2. Danach den offenen Windows-Live-USB-Writer-Punkt mit echtem Windows/UEFI-Boottest validieren und dokumentieren.
3. Parallel den doppelt gefuehrten DHCP-Timeout-Restpunkt in `08-todo-global.md` aufraeumen (offener Duplicate zur bereits erledigten Fix-Checkbox).

## Stand (2026-04-29, Stream-Persistenz ueber Voll-Reboot auf srv1 geschlossen)

**Zuletzt erledigt**:
- `scripts/test-stream-persistence-reboot-smoke.sh` eingefuehrt und auf `srv1` gegen VM100 erfolgreich ausgefuehrt.
- Der Lauf validiert Profilkonsistenz + Sunshine-API-Recovery vor/nach Reboot ohne manuelle Firewall-/Routing-Eingriffe.
- Globales TODO wurde auf erledigt gesetzt.

**Naechste konkrete Schritte**:

1. Den verbleibenden offenen Installer-Live-Slice schliessen: `test-server-installer-live-smoke.sh` DHCP-Timeout in der lokalen libvirt-Harness final robust machen (offener, doppelter Restpunkt in `08-todo-global.md`).
2. Danach den offenen clean-install Host-Validierungspunkt auf frisch installiertem Server-Installer-Host end-to-end abnehmen (noVNC/XFCE/API/Downloads).
3. Anschliessend den Windows-Live-USB-Writer mit echtem Windows/UEFI-Boottest validieren und dokumentieren.

## Stand (2026-04-29, VPN-Default fuer VM-Streaming live)

**Zuletzt erledigt**:
- Egress-Defaults in Host-Profil, Installer-Generator und Thinclient-Runtime/Installer von `direct` auf `full` + `wireguard` + `wg-beagle` umgestellt.
- `srv1` liefert fuer VM100 jetzt API-/Installer-seitig konsistent WireGuard-Defaults.
- Lokale Thinclient-VM konnte `wg-beagle` erfolgreich gegen `srv1` enrollen; private Zielroute `192.168.123.116` laeuft ueber das VPN-Interface.

**Naechste konkrete Schritte**:

1. Frische VM100-Installer-Neuinstallation in der lokalen Thinclient-VM fahren (statt Legacy-Image-Fixups) und den gleichen WG-Nachweis ohne manuelle Script-Nachinstallation wiederholen.
2. End-to-End-Streamstart im VPN-Pfad finalisieren (Moonlight-Launch auf private Ziel-IP/Policy-Pfad) und als reproduzierbaren Smoke in `scripts/` festhalten.
3. Danach den verbleibenden offenen Host-Restblock aus `08-todo-global.md` (clean-install Host-Validierung post server-installer ISO) weiterziehen.

## Stand (2026-04-29, Smoke-Scripts stabilisiert + Sunshine/Moonlight Validierungspfad eingeführt)

**Zuletzt erledigt**:
- `test-server-installer-live-smoke.sh`: DHCP-Timeout auf 300s angehoben, ARP-Fallback in `wait_for_vm_ip` ergänzt.
- `test-standalone-desktop-stream-sim.sh`: libvirt-Permissions stabilisiert (umask 022, chmod 0644 auf Fake-ISO, chmod o+x auf TMP_DIR).
- `scripts/test-sunshine-selfheal-smoke.sh` (neu): validiert beagle-sunshine-healthcheck.timer + pkill-Szenario auf VM-Gast.
- `scripts/test-moonlight-appname-smoke.sh` (neu): ruft Sunshine /api/apps auf, führt Resolver-Logik nach, gibt PASS/WARN aus.

**Naechste konkrete Schritte**:

1. Neuen Scripts über Repo-Auto-Update auf `srv1` deployen (nach Push auf GitHub automatisch).
2. Sunshine-/Moonlight-Smokes gegen VM 100 auf `srv1` ausführen:
  - `BEAGLE_SMOKE_VM_SSH=beagle@<vm100-ip> bash scripts/test-sunshine-selfheal-smoke.sh`
  - `SUNSHINE_API_URL=https://<vm100-ip>:47990 SUNSHINE_PASSWORD=... bash scripts/test-moonlight-appname-smoke.sh`
3. Danach Installer-Rebuild-/Publish-Punkt weiterziehen: Server-Installer-/Installimage-Artefakte neu bauen damit Onboarding/LetsEncrypt-Fixes in frischen Installationen enthalten sind.


## Stand (2026-04-29, prepare-host-downloads Import-Fix auf srv1 geschlossen)

**Zuletzt erledigt**:
- `scripts/prepare-host-downloads.sh` exportiert jetzt den Repo-Root in `PYTHONPATH`, sodass der Host-Downloads-Pfad auf `srv1` nicht mehr an `ModuleNotFoundError: No module named 'core'` scheitert.
- Die gefixte Script-Version ist auf `srv1` eingespielt und der Lauf erzeugt wieder Host-Downloads unter `/opt/beagle/dist`.

**Naechste konkrete Schritte**:

1. Den jetzt entblockten Installer-Restpunkt weiterziehen: Server-Installer-/Installimage-Artefakte neu bauen und publizieren, damit Onboarding- und Let's-Encrypt-Fixes in frischen Installationen enthalten sind.
2. Danach den offenen Clean-Install-Host-Validierungspunkt nachziehen (noVNC/XFCE/API/Downloads end-to-end auf frischem Host).
3. `srv2`-abhaengige Zwei-Host-Slices weiter blockiert lassen, bis SSH-Reachability wiederhergestellt ist.

## Stand (2026-04-29, Security/TLS Let's-Encrypt-API Regression geschlossen)

**Zuletzt erledigt**:
- Route-Regressionen fuer den Let's-Encrypt-Pfad in `tests/unit/test_server_settings.py` ergaenzt.
- Neuer Host-Smoke `scripts/test-security-tls-api-smoke.sh` auf `srv1` erfolgreich ausgefuehrt (`SECURITY_TLS_API_SMOKE=PASS`).

**Naechste konkrete Schritte**:

1. Den verbleibenden Installer-Restpunkt schliessen: Server-Installer-/Installimage-Artefakte neu bauen und publizieren, damit Onboarding- und Let's-Encrypt-Fixes in frischen Installationen enthalten sind.
2. Danach den offenen Host-Validierungspunkt fuer clean install nachziehen (noVNC/XFCE/API/Downloads end-to-end auf frischem Host).
3. `srv2`-abhaengige Zwei-Host-Slices erst wieder aufnehmen, sobald SSH-Reachability stabil zurueck ist.

## Stand (2026-04-29, srv1 Control-Plane-Runtime und IAM/Audit-Smokes geschlossen)

**Zuletzt erledigt**:
- Der veraltete `beagle-manager`-SSH-Check ist durch `scripts/test-control-plane-runtime-smoke.sh` ersetzt; auf `srv1` ist die echte Runtime-Unit `beagle-control-plane` aktiv und die lokale Health-Surface antwortet `200`.
- IAM-/Audit-UI-Regressionen laufen lokal gruen, und die vorhandenen `srv1`-Smokes fuer Plan 13 und Audit-Compliance sind erfolgreich durchgelaufen.

**Naechste konkrete Schritte**:

1. Den verbliebenen Host-Restblock auf frischem Installer-System weiterziehen: noVNC/XFCE-Hotfixes, API- und Download-Pfade auf sauberem Host aus der aktuellen Server-Installer-ISO end-to-end abnehmen.
2. Sobald `srv2` wieder per SSH erreichbar ist, denselben Control-Plane-Runtime-Smoke dort nachziehen und die Zwei-Host-Live-Validierung wieder aufnehmen.
3. Danach die offenen GoRelease-R2/R3-Gates priorisieren, statt weitere `srv2`-abhaengige Multi-Node-Slices anzuschneiden.

## Stand (2026-04-29, UI-Provisioning-Smoke in CI geschlossen)

**Zuletzt erledigt**:
- `scripts/test-provisioning-ui-smoke.py` prueft jetzt den echten WebUI-Provisioning-Modal-Flow per Playwright gegen gemockte API-Routen.
- `.github/workflows/tests.yml` fuehrt dafuer einen eigenen CI-Job aus und staged den benoetigten `browser-common.js`-Asset temporaer in den statischen `website/`-Serve-Baum.

**Naechste konkrete Schritte**:

1. Den offenen Installer-/Host-Restblock weiterziehen: frischen Host aus der neuen Server-Installer-ISO aufsetzen und noVNC/API/Download-Hotfixes dort end-to-end abnehmen.
2. Danach den verbliebenen Plan-09-Multi-Node-Live-Block wieder aufnehmen, sobald `srv2` netzseitig verlässlich erreichbar ist.
3. Fuer spaetere UI-Smokes prüfen, ob ein gemeinsamer statischer Test-Serve-Pfad statt temporaerer Asset-Staging-Schritte sinnvoll ist.

## Stand (2026-04-29, Sunshine/Desktop-Guest-Smoke im Provisioning-Ready-Flow geschlossen)

**Zuletzt erledigt**:
- `scripts/ensure-vm-stream-ready.sh` prueft nach Provisioning jetzt live `xset q` plus Abwesenheit von `light-locker` und `xfce4-power-manager`.
- Der neue Desktop-Guard ist im Runtime-Pfad auf `srv1` gegen VM100 validiert; Warnungen bleiben sichtbar, ohne den Ready-Flow hart abzubrechen.

**Naechste konkrete Schritte**:

1. Offenen Top-Punkt aus `docs/refactor/08-todo-global.md` weiterziehen: QEMU+SSH-Live-Migration-Deadlock zwischen `srv1`/`srv2` reproduzierbar eingrenzen oder Shared-Storage-Migrationspfad als Abnahmeweg dokumentieren.
2. Danach den offenen Plan-09-Restpunkt (`node-failure<=60s`, fencing start-block, maintenance drain live, anti-affinity multi-node runtime) auf echter 2-Node-Laufzeit final abnehmen.
3. Anschliessend die verbleibenden GoRelease-R2/R3-Gates in `docs/gorelease/` mit dem gleichen Muster schliessen: erst reproduzierbarer Code-/Testpfad, dann `srv1`/`srv2`-Live-Validierung.

## Stand (2026-04-29, QEMU+SSH Live-Migration-Deadlock eingegrenzt)

**Zuletzt erledigt**:
- `migration_service.py` liefert bei qemu+ssh-Deadlock-/Timeout-Indikatoren jetzt explizite Guidance fuer den Abnahmepfad (shared storage live) bzw. fallback (`copy_storage=true` cold/offline).
- Der offene Global-TODO-Punkt zur Deadlock-Eingrenzung ist geschlossen und auf `srv1` via Runtime-Smoke validiert.

**Naechste konkrete Schritte**:

1. Den verbleibenden offenen Plan-09-Testpflichtpunkt auf echter Multi-Node-Laufzeit final abnehmen (`node-failure<=60s`, fencing start-block, maintenance drain live, anti-affinity).
2. Danach die offenen GoRelease-R2/R3-Checks priorisieren, beginnend mit frischem Install/Boot-Pfad und Artefakt-/Signaturkette.
3. Parallel den `beagle-control-plane`-Runtime-Status auf `srv1`/`srv2` als Vorbedingung fuer weitere Live-Smokes stabil gruen halten.

## Stand (2026-04-29, VM-Delete/noVNC UI-Regressions geschlossen)

**Zuletzt erledigt**:
- `tests/unit/test_vm_actions_ui_regressions.py` deckt jetzt die offenen Delete-/noVNC-UI-Regressionspunkte ab.
- Lokaler Testlauf ist gruen, und auf `srv1` wurde ein gezielter Smoke gegen die kopierten Repo-Dateien erfolgreich bestaetigt.

**Naechste konkrete Schritte**:

1. Den verbleibenden offenen Punkt `UI-level provisioning smoke test in CI` aus `docs/refactor/08-todo-global.md` schliessen.
2. Danach den Installer-/Host-Restblock weiterziehen: frischer ISO-Installpfad inklusive noVNC/API/Downloads nachinstall validieren.
3. Den Multi-Node-HA-Live-Smoke wieder aufnehmen, sobald `srv2` netzseitig wieder erreichbar ist.

## Stand (2026-04-29, GoAdvanced Plan 06 Schritt 3 Teil 3 abgeschlossen)

**Zuletzt erledigt**:
- drittes SQLite-Repository (`core/repository/session_repository.py`) mit CRUD + Pool/User/Status-Filterung eingefuehrt und auf `srv1` validiert.

**Naechste konkrete Schritte**:

1. Plan 06 Schritt 3 weiterziehen: `pool_repository.py` als naechsten Slice umsetzen.
2. Danach `gpu_repository.py` nachziehen und den Schritt-3-Block komplett auf `[x]` schliessen.
3. Direkt im Anschluss Schritt 4 starten: JSON->SQLite-Importer (Dry-Run zuerst) fuer die bereits vorhandenen Repositories (`vms`, `devices`, `sessions`).

## Stand (2026-04-29, GoAdvanced Plan 06 Schritt 3 Teil 2 abgeschlossen)

**Zuletzt erledigt**:
- zweites SQLite-Repository (`core/repository/device_repository.py`) mit CRUD + Status/Fingerprint-Filterung eingefuehrt und auf `srv1` validiert.

**Naechste konkrete Schritte**:

1. Plan 06 Schritt 3 weiterziehen: `session_repository.py` als naechsten Slice aufsetzen (inkl. FK-Kanten zu `pools`/`vms`).
2. Danach `pool_repository.py` und `gpu_repository.py` nachziehen, damit der Schritt-3-Block komplett wird.
3. Anschliessend Schritt 4 starten: JSON->SQLite-Importer mit Dry-Run fuer zuerst `vms` und `devices` aufbauen.

## Stand (2026-04-29, GoAdvanced Plan 06 Schritt 3 Teil 1 abgeschlossen)

**Zuletzt erledigt**:
- erstes SQLite-Repository (`core/repository/vm_repository.py`) mit CRUD + Filterung eingefuehrt und auf `srv1` validiert.

**Naechste konkrete Schritte**:

1. Plan 06 Schritt 3 weiterziehen: `device_repository.py` als naechsten kleinen Slice einfuehren, weil Device-Registry bereits klare Identifier (`device_id`, `fingerprint`) hat.
2. Danach `session_repository.py` aufsetzen und mit FK-Checks gegen `pools`/`vms` absichern.
3. Erst wenn mindestens zwei weitere Repositories stabil sind, Schritt 4 (JSON->SQLite-Importer) mit den zuerst migrierten Entitaeten starten.

## Stand (2026-04-29, GoAdvanced Plan 06 Schritt 2 abgeschlossen)

**Zuletzt erledigt**:
- `core/persistence/migrations/001_init.sql` mit den ersten SQLite-Tabellen, Indizes und Foreign-Keys eingefuehrt; lokale Tests + `srv1`-Smoke erfolgreich.

**Naechste konkrete Schritte**:

1. GoAdvanced Plan 06 Schritt 3 umsetzen: erstes echtes Repository (`vm_repository.py` oder `device_repository.py`) auf Basis von `BeagleDb` einfuehren.
2. Den ersten Repository-Slice mit In-Memory-SQLite fokussiert testen und ein kleines `srv1`-Smoke fuer CRUD + Filterung nachziehen.
3. Danach entscheiden, welcher JSON-State als erster produktiver Import-/Migrationskandidat fuer Schritt 4 und 5a am wenigsten Risiko hat.

## Stand (2026-04-29, GoAdvanced Plan 06 Schritt 1 abgeschlossen)

**Zuletzt erledigt**:
- `core/persistence/sqlite_db.py` als gemeinsame SQLite-Basis mit WAL/Foreign-Keys/Migrationslog eingefuehrt; lokale Tests + `srv1`-Smoke erfolgreich.

**Naechste konkrete Schritte**:

1. GoAdvanced Plan 06 Schritt 2 umsetzen: `core/persistence/migrations/001_init.sql` mit den ersten Tabellen und Indizes anlegen.
2. Direkt danach Plan 06 Schritt 3 vorbereiten: ersten produktiven Repository-Slice (`vm_repository.py` oder `device_repository.py`) gegen In-Memory-SQLite testbar machen.
3. Fuer Schritt 2/3 dieselbe Validierung beibehalten: fokussierte Unit-Tests lokal + kurzer non-invasiver `srv1`-Smoke.

## Stand (2026-04-29, GoAdvanced Plan 01 abgeschlossen)

**Zuletzt erledigt**:
- Welle 3d Teil 4 (`webhook_service.py`, `stream_http_surface.py`, `server_settings.py`, `sunshine_integration.py`, `gaming_metrics_service.py`) auf `JsonStateStore`/atomare Helper migriert; lokale Tests + `srv1`-Batch-Smoke erfolgreich.
- Plan-01-Restpunkt `Repo-Grep` fuer direkte `path.write_text(json.dumps(`-Writes in `beagle-host/services` auf Null gebracht.

**Naechste konkrete Schritte**:

1. GoAdvanced Plan 06 (`docs/goadvanced/06-state-sqlite-migration.md`) starten: State-Kandidaten fuer SQLite priorisieren und ersten Service-Slice mit Migrationspfad umsetzen.
2. Fuer den ersten Plan-06-Slice denselben Validierungsstandard fahren: fokussierte Unit-Tests lokal + non-invasiver `srv1`-Smoke.
3. Nach dem ersten Plan-06-Commit die Refactor-Dokumente (`05-progress.md`, `08-todo-global.md`) auf den neuen Fortschritt synchronisieren.

## Stand (2026-04-29, GoAdvanced Plan 01 Welle 3d Teil 3 abgeschlossen)

**Zuletzt erledigt**:
- `endpoint_report.py`, `firewall_service.py` und `cluster_membership.py` auf `JsonStateStore`/atomare JSON-Store-Helper migriert; lokale Tests + `srv1`-Batch-Smoke erfolgreich.

**Naechste konkrete Schritte**:

1. Welle 3d Teil 4: verbleibende Service-Pfade `webhook_service.py`, `stream_http_surface.py`, `server_settings.py`, `sunshine_integration.py`, `gaming_metrics_service.py` migrieren.
2. Danach Plan-01-Restpunkt `Repo-Grep` fuer direkte `path.write_text(json.dumps(` ausserhalb von Tests final auf Null bringen.
3. Nach Abschluss von Welle 3d den Gesamtstatus in `docs/goadvanced/01-data-integrity.md` und `docs/refactor/08-todo-global.md` als komplett markieren.

## Stand (2026-04-29, GoAdvanced Plan 01 Welle 3d Teil 2 abgeschlossen)

**Zuletzt erledigt**:
- `maintenance_service.py`, `installer_log_service.py` und `ha_watchdog.py` auf `JsonStateStore` migriert; lokale Tests + `srv1`-Batch-Smoke erfolgreich.

**Naechste konkrete Schritte**:

1. Welle 3d Teil 3: `endpoint_report.py`, `firewall_service.py`, `cluster_membership.py` auf `JsonStateStore`/atomare Writes migrieren.
2. Welle 3d Teil 4: verbleibende Service-Pfade (`server_settings.py`, `stream_http_surface.py`, `sunshine_integration.py`, ggf. `gaming_metrics_service.py`) in kleinen Batches nachziehen.
3. Danach Plan-01-Restpunkt `Repo-Grep` fuer direkte `path.write_text(json.dumps(` ausserhalb von Tests final auf Null bringen.

## Stand (2026-04-29, GoAdvanced Plan 01 Welle 3d Teil 1 abgeschlossen)

**Zuletzt erledigt**:
- `backup_service.py`, `entitlement_service.py` und `stream_policy_service.py` auf `JsonStateStore` migriert; lokale Tests + `srv1`-Batch-Smoke erfolgreich.

**Naechste konkrete Schritte**:

1. Welle 3d Teil 2: `webhook_service.py`, `maintenance_service.py`, `installer_log_service.py` auf `JsonStateStore`/atomare Writes ziehen.
2. Welle 3d Teil 3: `endpoint_report.py`, `firewall_service.py`, `cluster_membership.py` (wenn sinnvoll lock-basiert) nachziehen.
3. Danach den Plan-01-Restpunkt `Repo-Grep` fuer direkte `path.write_text(json.dumps(` ausserhalb von Tests erneut messen und auf Null bringen.

## Stand (2026-04-29, GoAdvanced Plan 01 Welle 3c abgeschlossen)

**Zuletzt erledigt**:
- `fleet_telemetry_service.py` Maintenance-Schedule auf `JsonStateStore` migriert; kompletter Welle-3c-Testblock lokal und auf `srv1` erfolgreich.

**Naechste konkrete Schritte**:

1. Welle 3d in kleinen Batches schliessen (3-5 Services pro Run), beginnend mit den verbleibenden direkten JSON-Write-Pfaden in `beagle-host/services/`.
2. Danach Plan-01-Schritt-4-Restpunkt abschliessen: Repo-Grep fuer direkte `path.write_text(json.dumps(`-Schreibpfade ausserhalb von Tests auf Null bringen.
3. Als Folgearbeit die SQLite-Migration (`goadvanced/06-state-sqlite-migration.md`) vorbereiten, sobald Welle 3d abgeschlossen ist.

## Stand (2026-04-29, GoAdvanced Plan 01 Welle 3b abgeschlossen)

**Zuletzt erledigt**:
- `mdm_policy_service.py` auf `JsonStateStore` migriert; `device_registry.py`, `cluster_service.py`, `alert_service.py` als bereits gehaertete `JsonStateStore`-Pfade verifiziert; lokale Tests + `srv1`-Smoke gruen.

**Naechste konkrete Schritte**:

1. Welle 3c umsetzen: `session_manager.py`, `fleet_telemetry_service.py`, `metrics_collector.py`, `workload_pattern_analyzer.py`, `smart_scheduler.py` auf `JsonStateStore`/atomic writes ziehen.
2. Welle 3d fuer verbleibende Services planbar schneiden (Batches mit je 3-5 Services) und jeweils mit lokalen Tests + `srv1`-Smoke absichern.
3. Danach den Restpunkt in Plan 01 schliessen: Repo-Grep fuer direkte `path.write_text(json.dumps(`-Writes ausserhalb von Tests auf Null bringen.

## Stand (2026-04-29, GoAdvanced Plan 01 Welle 3a abgeschlossen)

**Zuletzt erledigt**:
- `usage_tracking_service.py` und `energy_service.py` auf `JsonStateStore` migriert; lokale Unit-Tests sowie `srv1`-Runtime-Smoke erfolgreich.

**Naechste konkrete Schritte**:

1. Welle 3b im selben Plan abschliessen: `device_registry.py`, `mdm_policy_service.py`, `cluster_service.py`, `alert_service.py` auf `JsonStateStore` migrieren (`attestation_service.py` ist bereits erledigt).
2. Danach Welle 3c starten (`session_manager.py`, `fleet_telemetry_service.py`, `metrics_collector.py`, `workload_pattern_analyzer.py`, `smart_scheduler.py`).
3. Nach jeder Welle dieselbe Validierung fahren: betroffene Unit-Suite lokal + kurzer Runtime-Smoke auf `srv1`.

## Stand (2026-04-29, GoAdvanced Plan 01 Datenintegritaet: naechste Migrationswelle)

**Zuletzt erledigt**:
- JsonStateStore-Migration fuer mehrere Hochrisiko-/Service-Dateien abgeschlossen, lokaler + `srv1` Stress-Test (`1000` parallele Updates) erfolgreich.

**Naechste konkrete Schritte**:

1. Plan-01-Welle 3 vervollstaendigen: `usage_tracking_service.py`, `energy_service.py`, danach restliche Service-Wellen 3b/3c/3d auf `JsonStateStore` ziehen.
2. Repo-Grep-Restschuld fuer direkte `path.write_text(json.dumps(`-Schreibpfade systematisch abbauen (ausserhalb von Tests).
3. Nach jeder Welle: betroffene Unit-Suiten + Stress-Skript lokal und auf `srv1` erneut laufen lassen.

## Stand (2026-04-29, lokaler Thinclient-KVM-Smoke vorbereitet)

**Zuletzt erledigt**:
- Ein reproduzierbarer lokaler Smoke fuer die vorhandene libvirt-Domain `beagle-thinclient` liegt jetzt im Repo (`scripts/test-thinclient-vm-smoke.sh`) und wurde erfolgreich gegen den lokalen Guest gefahren.

**Naechste konkrete Schritte**:

1. Den neuen lokalen Guest gezielt fuer den offenen Plan-02-X11-Lockscreen-Test nutzen und den grafischen Sperrbildschirm live abnehmen.
2. Wenn fuer einen frischen Throwaway-Guest wieder genug Platz vorhanden ist, denselben Smoke optional mit `BEAGLE_THINCLIENT_CREATE_IF_MISSING=1` gegen ein Thinclient-ISO fahren.
3. Falls der Lockscreen-Test mehr Display-Details braucht, auf Basis desselben Guests noch einen kleinen Screenshot-/Console-/QEMU-Log-Smoke nachziehen.

## Stand (2026-04-29, Plan 02 Auto-Remediation-Worker auf `srv1` geschlossen)

**Zuletzt erledigt**:
- Der offene Plan-02-Restpunkt `serverseitiger Auto-Remediation-/Drift-Worker` ist geschlossen: Fleet-Remediation laeuft jetzt periodisch im Control-Plane-Prozess, teilt sich denselben sicheren Server-Codepfad mit dem manuellen Run und ist auf `srv1` erfolgreich deployt und neu gestartet.

**Naechste konkrete Schritte**:

1. Den verbleibenden Plan-02-Restpunkt schliessen: grafischen Sperrbildschirm live gegen eine echte Thin-Client-X11-Session abnehmen.
2. Falls der Live-Test X11-spezifische Luecken zeigt, denselben Sperrpfad direkt gegen Wayland-/Multi-Display-Sessions nachhaerten.
3. Optional einen kleinen Canary-Lauf mit `enabled=true` auf einer unkritischen Testgruppe fahren und die Remediation-History gegen reale Drift-Eintraege pruefen.

## Stand (2026-04-29, Thinclient-WireGuard-Full-Tunnel live auf VM100 + srv1 Reconcile/FW-Default)

**Zuletzt erledigt**:
- Der laufende Thinclient fuer VM100 wurde live von Direct-Egress auf echten WireGuard-Full-Tunnel umgestellt; `srv1` uebernimmt neue Peers jetzt automatisch ueber einen Root-Reconcile-Pfad in `wg-beagle`, und Host-Firewall/WireGuard-Basis sind standardmaessig im Repo verdrahtet.

**Naechste konkrete Schritte**:

1. Den aktuell laufenden Thinclient-Artefakt-Build auf `srv1` bis zum neuen `filesystem.squashfs`/ISO durchlaufen lassen und den Build-Output gegen `wireguard-tools`/`jq` im Image verifizieren.
2. Den neuen Stand auf `srv2` spiegeln, falls dort ebenfalls Thinclients oder WireGuard-geschuetzte Stream-VMs angebunden werden.
3. Einen echten USB-/Live-Stick aus dem frisch gebauten Thinclient-Artefakt booten und denselben WireGuard-Enroll-/Handshake-Pfad ohne manuelle Paketnachinstallation erneut abnehmen.

## Stand (2026-04-29, VM100 Display-Idle/Locker-Fix auf `srv1`)

**Zuletzt erledigt**:
- Der Black-Screen-Befund von VM100 wurde auf aktives XFCE-Idle/Locker-Verhalten zurueckgefuehrt und sowohl live in der VM als auch reproduzierbar im Provisioning-Skript behoben.

**Naechste konkrete Schritte**:

1. Den neuen Guest-Provisioning-Stand per normalem Repo-Deploy auch auf `srv2` spiegeln, falls dort Sunshine-/Desktop-VMs erstellt werden.
2. Den naechsten neu erstellten WebUI-Desktop-Guest einmal als Smoke bauen und direkt nach erstem Login `xset q` + Prozessliste validieren.
3. Optional einen kleinen Host-/Guest-Smoke fuer `configure-sunshine-guest.sh` ergaenzen, der `light-locker`/`xfce4-power-manager` nach der Konfiguration live auf einer Test-VM prueft.

## Stand (2026-04-28, srv1 Systemd-/Update-Drift gepatcht)

**Zuletzt erledigt**:
- Die failed-unit-Befunde auf `srv1` sind auf konkrete Ursachen zurueckgefuehrt und im Repo gepatcht: fehlendes Execute-Bit, zu harte Public-Streams-Sandbox, nicht-idempotenter ifupdown-Route-Hook und Short-vs-Full-Hash im Repo-Auto-Update.

**Naechste konkrete Schritte**:

1. Fixes auf `srv1` ausrollen, `systemctl daemon-reload` fahren und `beagle-cluster-auto-join.service` / `beagle-public-streams.service` erneut testen.
2. `/etc/network/interfaces` auf `srv1` live auf idempotenten Route-Hook umstellen und `networking.service` ohne Interface-Ausfall neu bewerten.
3. Nach Ende des aktuell laufenden Artifact-Builds `repo-auto-update-status.json` erneut pruefen; erwarteter Zielzustand ist `state=healthy`, `update_available=false`.

## Stand (2026-04-28, Login-429 hinter nginx behoben)

**Zuletzt erledigt**:
- Login-Rate-Limit/Guard nutzt hinter nginx wieder die echte Forwarded-For-Client-IP und nicht global `127.0.0.1`; Login-Doppel-Submits werden browserseitig zusammengefuehrt.

**Naechste konkrete Schritte**:

1. Fix auf `srv1` ausrollen, `beagle-control-plane` neu starten und Login mit `admin` verifizieren.
2. Danach denselben Runtime-Stand auf `srv2` spiegeln, falls dort nginx ebenfalls als Reverse Proxy vor der Control Plane steht.
3. Optional: Prometheus-/Audit-Auswertung fuer `beagle_rate_limit_drops_total` nach Host/Client-IP pruefen, um echte Brute-Force-Versuche von Proxy-Key-Drift zu unterscheiden.

## Stand (2026-04-28, WebUI CSP inline-style fix)

**Zuletzt erledigt**:
- Die verbliebenen WebUI-CSP-Fehler durch `style="..."`-Attribute wurden im Repo entfernt; Heatmaps, Green-Hours-Kacheln, Bars und Statusmeldungen nutzen jetzt Klassen statt Inline-Styles.

**Naechste konkrete Schritte**:

1. Fix auf `srv1` ausrollen und mit Chrome DevTools MCP nach Login gegen die Console verifizieren.
2. Danach denselben Asset-Stand auf `srv2` spiegeln, falls der Host die WebUI ebenfalls live ausliefert.
3. Bei kuenftigen WebUI-Slices `style-src 'self'` als harte Vorgabe behandeln: keine neuen Inline-Style-Attribute in HTML-Strings.

## Stand (2026-04-28, WebUI auth gating fix deployed on srv1)

**Zuletzt erledigt**:
- WebUI-Auth-/RBAC-Gates fuer Scheduler-/Kosten-/Energie-Panels sind im Repo eingezogen und nach `srv1` ausgerollt; die bekannten `401 Unauthorized`-Burst-Requests ohne Login werden browserseitig nicht mehr provoziert.
- Live-Login gegen `srv1` liefert wieder sauber Access-/Refresh-Token; die zuvor betroffenen Settings-Endpunkte antworten nach Authentifizierung mit `200`.

**Naechste konkrete Schritte**:

1. Browser-E2E-Smoke auf `srv1.beagle-os.com` nachziehen, sobald Playwright auf dem Host oder lokal verfuegbar ist, um die DevTools-Console explizit gegen den neuen Bootstrap zu pruefen.
2. Falls Nutzer noch den alten Fehler sehen: Browser-Cache fuer `/main.js?v=8.0` / `/ui/*.js` hart invalidieren und denselben Ablauf auf `srv2` gespiegelt ausrollen.
3. Den historischen Alt-Befund eines `beagle-manager = inactive` nicht weiter als Runtime-Signal verwenden; fuer den aktuellen WebUI-/Control-Plane-Fix ist die relevante Unit `beagle-control-plane`, und diese laeuft auf `srv1`.

## Stand (2026-04-28, GoEnterprise Plan 01 VM-register smoke completed)

**Zuletzt erledigt**:
- Der offene Plan-01-Testpflichtpunkt fuer den VM-seitigen Stream-Register-Flow ist geschlossen: reproduzierbarer Guest-Agent-Smoke gegen `/api/v1/streams/register|config|events` laeuft auf `srv1` erfolgreich.

**Naechste konkrete Schritte**:

1. **Plan 01 WireGuard-Rest**: verbleibende WireGuard-Mesh-/Latency-Testpflichtpunkte reproduzierbar im Runtime-Scope schliessen.
2. **Plan 01 Fork-Rest**: echten `beagle-stream-server`-Fork (Sunshine) mit Broker-/Auth-Komponenten in separatem Repo aufsetzen und gegen den vorhandenen Control-Plane-Slice verdrahten.
3. **Plan 02 Live-Restpunkte**: grafischen Sperrbildschirm und Device-Wipe auf echter Thin-Client-Hardware/X11-/Wayland-Sessions verifizieren.
4. **Plan 01 Fork-Enforcement**: denselben `vpn_required`-Enforcement-Pfad spaeter im separaten `beagle-stream-server`-Fork verankern.

## Stand (2026-04-28, GoEnterprise Plan 01 stream handshake enforcement completed)

**Zuletzt erledigt**:
- Plan-01-Enforcement im aktuellen Stream-Slice ist jetzt auf Register- und Session-Start-Pfaden geschlossen (`403` bei `vpn_required` ohne WireGuard), lokal und auf `srv1` mit `22 passed` validiert.

**Naechste konkrete Schritte**:

1. **Plan 01 Fork-Rest**: echten `beagle-stream-server` auf VM starten und realen Register-/Config-/Event-Handshake gegen die vorhandene API fahren.
2. **Plan 01 WireGuard-Rest**: verbleibende WireGuard-Mesh-/Latency-Testpflichtpunkte reproduzierbar im Runtime-Scope schliessen.
3. **Plan 02 Live-Restpunkte**: grafischen Sperrbildschirm und Device-Wipe auf echter Thin-Client-Hardware/X11-/Wayland-Sessions verifizieren.
4. **Plan 01 Fork-Enforcement**: denselben Enforcement-Pfad spaeter im separaten `beagle-stream-server`-Fork verankern.

## Stand (2026-04-28, GoEnterprise Plan 01 allocate runtime wiring completed)

**Zuletzt erledigt**:
- Der Allocate-Contract (`POST /api/v1/streams/allocate`) ist jetzt im Registry-Runtime-Pfad an echte Pairing-/WireGuard-Quellen verdrahtet.

**Naechste konkrete Schritte**:

1. **Plan 01 Fork-Rest**: echten `beagle-stream-server` auf VM starten und realen Register-/Config-/Event-Handshake gegen die vorhandene API fahren.
2. **Plan 01 WireGuard-Rest**: verbleibende WireGuard-Mesh-/Latency-Testpflichtpunkte reproduzierbar im Runtime-Scope schliessen.
3. **Plan 02 Live-Restpunkte**: grafischen Sperrbildschirm und Device-Wipe auf echter Thin-Client-Hardware/X11-/Wayland-Sessions verifizieren.
4. **Plan 01 Fork-Enforcement**: denselben `vpn_required`-Enforcement-Pfad im separaten Stream-Server-Fork verankern.

## Stand (2026-04-28, GoEnterprise Plan 01 client broker contract completed)

**Zuletzt erledigt**:
- Plan-01-Checkbox `tests/unit/test_beagle_stream_client_broker.py` ist geschlossen: `POST /api/v1/streams/allocate` liefert den dedizierten Client-Broker-Contract und erzwingt `vpn_required` im aktuellen Control-Plane-Slice reproduzierbar.

**Naechste konkrete Schritte**:

1. **Plan 01 Fork-Rest**: echten `beagle-stream-server` auf VM starten und reale Register-/Pairing-/Event-Flows gegen die bestehende API fahren.
2. **Plan 01 WireGuard-Rest**: verbleibende WireGuard-Mesh-/Latency-Testpflichtpunkte reproduzierbar im Runtime-Scope schliessen.
3. **Plan 02 Live-Restpunkte**: grafischen Sperrbildschirm und Device-Wipe auf echter Thin-Client-Hardware/X11-/Wayland-Sessions verifizieren.
4. **Plan 01 Fork-Enforcement**: spaeteren Enforcement-Pfad fuer `vpn_required` im separaten Stream-Server-Fork reproduzierbar nachziehen.

## Stand (2026-04-28, GoEnterprise Plan 04 warm-pool auto-apply completed)

**Zuletzt erledigt**:
- Plan-04-Restpunkt ist geschlossen: Warm-Pool-Empfehlungen koennen jetzt optional automatisch mit Guardrails ausgefuehrt werden (max Pools/Run, max Increase, min Miss-Rate, Cooldown) inklusive Scheduler-UI-Controls und Status-Feedback.

**Naechste konkrete Schritte**:

1. **Plan 01 Fork-Rest**: echten `beagle-stream-server` auf VM starten und reale Register-/Pairing-/Event-Flows gegen die bestehende API fahren.
2. **Plan 01 WireGuard-Rest**: verbleibende WireGuard-Mesh-/Latency-Testpflichtpunkte reproduzierbar im Runtime-Scope schliessen.
3. **Plan 02 Live-Restpunkte**: grafischen Sperrbildschirm und Device-Wipe auf echter Thin-Client-Hardware/X11-/Wayland-Sessions verifizieren.
4. **Plan 01 Fork-Enforcement**: spaeteren Enforcement-Pfad fuer `vpn_required` im separaten Stream-Server-Fork reproduzierbar nachziehen.

## Stand (2026-04-28, GoEnterprise Plan 09 external feed import completed)

**Zuletzt erledigt**:
- Plan-09-Restpunkt ist geschlossen: externer Carbon-/Strommix-Feed kann jetzt via Control-Plane-Importpfad mit Retry/Backoff eingespielt werden; bei Retry-Exhaustion wird ein Fleet-Alert erzeugt.

**Naechste konkrete Schritte**:

1. **Plan 01 Fork-Rest**: echten `beagle-stream-server` auf VM starten und reale Register-/Pairing-/Event-Flows gegen die bestehende API fahren.
2. **Plan 01 WireGuard-Rest**: verbleibende WireGuard-Mesh-/Latency-Testpflichtpunkte reproduzierbar im Runtime-Scope schliessen.
3. **Plan 02 Live-Restpunkte**: grafischen Sperrbildschirm und Device-Wipe auf echter Thin-Client-Hardware/X11-/Wayland-Sessions verifizieren.
4. **Plan 01 Fork-Enforcement**: spaeteren Enforcement-Pfad fuer `vpn_required` im separaten Stream-Server-Fork reproduzierbar nachziehen.

## Stand (2026-04-28, GoEnterprise Plan 01 token pairing hardening completed)

**Zuletzt erledigt**:
- Plan-01-Token-Pairing-Testpunkt ist im Control-Plane-Scope geschlossen: HMAC-Pair-Tokens laufen jetzt standardmaessig mit 60s TTL und sind einmal-verwendbar (Replay wird blockiert), mit dedizierten Tests abgesichert.

**Naechste konkrete Schritte**:

1. **Plan 01 Fork-Rest**: echten `beagle-stream-server` auf VM starten und reale Register-/Pairing-/Event-Flows gegen die bestehende API fahren.
2. **Plan 01 WireGuard-Rest**: verbleibende WireGuard-Mesh-/Latency-Testpflichtpunkte reproduzierbar im Runtime-Scope schliessen.
3. **Plan 04 Restpunkt**: Warm-Pool-Empfehlungen optional automatisch anwenden (mit Safety-Guardrails).
4. **Plan 02 Live-Restpunkte**: grafischen Sperrbildschirm und Device-Wipe auf echter Thin-Client-Hardware/X11-/Wayland-Sessions verifizieren.

## Stand (2026-04-28, GoEnterprise Plan 01 stream-server contract tests completed)

**Zuletzt erledigt**:
- Die offene Plan-01-Schritt-1-Testcheckbox ist geschlossen: `tests/unit/test_beagle_stream_server_api.py` deckt Register/Config/Events inkl. `vpn_required`-403 und Audit-Events gegen die neue `/api/v1/streams/*`-Surface ab.

**Naechste konkrete Schritte**:

1. **Plan 01 Fork-Rest**: den eigentlichen Sunshine-Fork `beagle-stream-server` mit HMAC-Token-Pairing und realem Startup-Register gegen diese API anheben.
2. **Plan 04 Restpunkt**: Warm-Pool-Empfehlungen optional automatisch anwenden (mit Safety-Guardrails).
3. **Plan 02 Live-Restpunkte**: grafischen Sperrbildschirm und Device-Wipe auf echter Thin-Client-Hardware/X11-/Wayland-Sessions verifizieren.
4. **Plan 01 WireGuard-Rest**: verbleibende WireGuard-Mesh-/Latency-Testpflichtpunkte reproduzierbar im Runtime-Scope schliessen.

## Stand (2026-04-28, GoEnterprise Plan 01 policy/audit testpflicht slice completed)

**Zuletzt erledigt**:
- Plan-01-Testpflicht im aktuellen Repo-Scope weiter geschlossen: `vpn_required`-Ablehnung (`403`), `vpn_preferred`-Fallback (`200`) und Audit-Events fuer Stream-Session-Events sind jetzt reproduzierbar auf der neuen Stream-HTTP-Surface abgesichert.

**Naechste konkrete Schritte**:

1. **Plan 01 Fork-Rest**: den eigentlichen Sunshine-Fork `beagle-stream-server` mit HMAC-Token-Pairing und realem Startup-Register gegen diese neue Control-Plane-API anheben.
2. **Plan 04 Restpunkt**: Warm-Pool-Empfehlungen optional automatisch anwenden (mit Safety-Guardrails).
3. **Plan 02 Live-Restpunkte**: grafischen Sperrbildschirm und Device-Wipe auf echter Thin-Client-Hardware/X11-/Wayland-Sessions verifizieren.
4. **Plan 01 WireGuard-Rest**: verbleibende WireGuard-Mesh-/Latency-Testpflichtpunkte reproduzierbar im Runtime-Scope schliessen.

## Stand (2026-04-28, GoEnterprise Plan 01 stream control-plane slice completed)

**Zuletzt erledigt**:
- Die repo-faehige Control-Plane-Seite fuer den spaeteren `beagle-stream-server` ist jetzt umgesetzt: Stream-Server-Register, dynamische Config und Session-Event-Audit laufen ueber echte `/api/v1/streams/*`-Routen.
- `vpn_required` wird auf dem neuen Config-Pfad reproduzierbar mit `403` durchgesetzt; RBAC und Unit-Regressionen fuer die neue Surface sind vorhanden.

**Naechste konkrete Schritte**:

1. **Plan 01 Fork-Rest**: den eigentlichen Sunshine-Fork `beagle-stream-server` mit HMAC-Token-Pairing und realem Startup-Register gegen diese neue Control-Plane-API anheben.
2. **Plan 04 Restpunkt**: Warm-Pool-Empfehlungen optional automatisch anwenden (mit Safety-Guardrails).
3. **Plan 02 Live-Restpunkte**: grafischen Sperrbildschirm und Device-Wipe auf echter Thin-Client-Hardware/X11-/Wayland-Sessions verifizieren.
4. **Plan 01 WireGuard-Rest**: verbleibende WireGuard-Mesh-/Latency-Testpflichtpunkte reproduzierbar im Runtime-Scope schliessen.

## Stand (2026-04-28, GoEnterprise Plan 08 Schritt 1 RAID closed)

**Zuletzt erledigt**:
- Der offene Plan-08-Schritt-1-Rest wurde geschlossen: Installer unterstuetzt jetzt RAID `0/1/5/10` inkl. Multi-Disk-Flow (Seed + TUI/Plain).
- Validierung lokal und auf `srv1` ist gruen (`24 passed`).

**Naechste konkrete Schritte**:

1. **Plan 04 Restpunkt**: Warm-Pool-Empfehlungen optional automatisch anwenden (mit Safety-Guardrails).
2. **Plan 01**: verbleibenden BeagleStream-Fork-/Client-Fork-Block priorisieren und in kleine implementierbare Slices schneiden.
3. **Plan 02 Live-Restpunkte**: grafischen Sperrbildschirm und Device-Wipe auf echter Thin-Client-Hardware/X11-/Wayland-Sessions verifizieren.
4. **Plan 01 WireGuard-Rest**: verbleibende WireGuard-Mesh-/Latency-Testpflichtpunkte reproduzierbar im Runtime-Scope schliessen.

## Stand (2026-04-28, GoEnterprise Plan 02 testpflicht completed)

**Zuletzt erledigt**:
- Plan 02 offene Testpflicht ist geschlossen (Enrollment/Registry-Hardware, TPM-Compromise-Block, MDM-Pool-Restriktion, Remote-Wipe-Confirm, Gruppen-Policy-Rollout).
- Der fehlende WireGuard-Enrollment-Regressionstest liegt jetzt als `tests/unit/test_enrollment_wireguard.py` vor.
- Fokuslauf lokal und auf `srv1` ist reproduzierbar dokumentiert (`8 passed` lokal, `6 passed + 2 skipped` auf `srv1` wegen fehlendem `jq`).

**Naechste konkrete Schritte**:

1. **Plan 08 Restblock Schritt 1**: eigentlichen RAID-/Disk-Mehrfachauswahlpfad im Installer (RAID0/1/5/10) von Doku-Status auf echte Runtime-Implementierung heben.
2. **Plan 04 Restpunkt**: Warm-Pool-Empfehlungen optional automatisch anwenden (mit Safety-Guardrails).
3. **Plan 02 Live-Restpunkte**: grafischen Sperrbildschirm und Device-Wipe auf echter Thin-Client-Hardware/X11-/Wayland-Sessions verifizieren.
4. **Plan 01 WireGuard-Rest**: verbleibende WireGuard-Mesh-/Latency-Testpflichtpunkte reproduzierbar im Runtime-Scope schliessen.

## Stand (2026-04-28, GoEnterprise Plan 08 testpflicht completed)

**Zuletzt erledigt**:
- Plan 08 Testpflicht ist geschlossen (TUI-Flow mit 5 Schritten inkl. Validierung, Seed ohne Dialog, PXE + DHCP-Seed-Handover).
- Neue Acceptance-Tests plus bestehende Installer-Regressionen und PXE-Integrationstest sind lokal und auf `srv1` gruen.

**Naechste konkrete Schritte**:

1. **Plan 08 Restblock Schritt 1**: eigentlichen RAID-/Disk-Mehrfachauswahlpfad im Installer (RAID0/1/5/10) von Doku-Status auf echte Runtime-Implementierung heben.
2. **Plan 09 Restpunkt**: externen Carbon-/Strommix-Feed als reproduzierbaren Importjob mit Retry/Alerting umsetzen.
3. **Plan 04 Restpunkt**: Warm-Pool-Empfehlungen optional automatisch anwenden (mit Safety-Guardrails).
4. **Plan 02 Live-Restpunkte**: Enrollment-/WireGuard-/TPM-End-to-End auf echter Runtime-Hardware reproduzierbar verankern.

## Stand (2026-04-28, GoEnterprise Plan 07 testpflicht completed)

**Zuletzt erledigt**:
- Plan 07 Testpflicht ist abgeschlossen (SMART-Telemetrie, Disk-Trend-Anomalie, Predictive-Disk-Alert mit Webhook, Maintenance inklusive automatischem VM-Drain).
- Fleet-Telemetry-Maintenance kann jetzt optional VM-Migrationsaktionen direkt ausfuehren und im Schedule persistieren.
- Neue Acceptance-Suite ist lokal und auf `srv1` gruen (`38 passed` pro Lauf).

**Naechste konkrete Schritte**:

1. **Plan 04 Restpunkt schliessen**: Warm-Pool-Empfehlungen optional automatisch anwenden (Auto-Apply mit Guardrails).
2. **Plan 01 Fork-Rest**: den eigentlichen Sunshine-Fork `beagle-stream-server` mit HMAC-Token-Pairing und realem Startup-Register gegen die bestehende API anheben.
3. **Plan 08 angehen**: offenen TUI-Installer-Block (5-Schritt-Validierung + Seed-YAML Non-Interactive + PXE-Seed-Pfad) in `server-installer/` umsetzen.
4. **Plan 02 Live-Restpunkte**: Enrollment-/WireGuard-/TPM-End-to-End-Abnahmen reproduzierbar auf Runtime-Hardware verankern.

## Stand (2026-04-28, GoEnterprise Plan 09 testpflicht completed)

**Zuletzt erledigt**:
- Plan 09 Testpflicht ist abgeschlossen (RAPL-/VM-Anteil, 100W->40g CO2, Chargeback-Energiekosten, CSRD Scope-2 Quartal).
- Neue Acceptance-Suite plus aktualisierter Integrations-Test laufen lokal und auf `srv1` gruen (`29 passed` jeweils).

**Naechste konkrete Schritte**:

1. **Plan 04 Restpunkt schliessen**: Warm-Pool-Empfehlungen optional automatisch anwenden und mit Safety-Grenzen absichern.
2. **Plan 01 Fork-Rest schliessen**: echten `beagle-stream-server` gegen die bestehende API in einer reproduzierbaren Runtime-Abnahme fahren.
3. **Plan 07 Testpflicht angehen**: dedizierte Suite fuer SMART-Telemetrie, Disk-Trend-Anomalie, Predictive-Alert und Maintenance-Migration erstellen.
4. **Plan 02 Live-Restpunkte**: Enrollment-/WireGuard-/TPM-Abnahmepfade reproduzierbar fuer echte Runtime-Hardware nachziehen.

## Stand (2026-04-28, GoEnterprise Plan 04 testpflicht completed)

**Zuletzt erledigt**:
- Plan 04 Testpflicht ist jetzt geschlossen (14-Tage-Peak-Erkennung, 10-Minuten-Prewarm, Rebalancing >85%).
- Neue dedizierte Abnahmetests laufen lokal und auf `srv1` stabil (`20 passed` auf beiden Laeufen).

**Naechste konkrete Schritte**:

1. **Plan 04 vertiefen**: Warm-Pool-Empfehlungen optional automatisch anwenden (`auto-apply`) mit klarer Safety-Grenze.
2. **Plan 01 Fork-Rest schliessen**: echten `beagle-stream-server` gegen die bestehende API in einer reproduzierbaren Runtime-Abnahme fahren.
3. **Plan 07 testpflicht schliessen**: Fleet-Telemetrie-/Anomalie-/Maintenance-Abnahmesuite (`SMART`, Disk-Trend, Alert, Migration) aufbauen und live gegen `srv1` validieren.
4. **Plan 02 live-rest abschliessen**: verbleibende End-to-End-Checks fuer Enrollment/TPM/WireGuard-Mesh und Gruppen-Policy reproduzierbar auf echter Runtime verankern.

## Stand (2026-04-28, GoEnterprise Plan 05 testpflicht completed)

**Zuletzt erledigt**:
- Plan 05 Testpflicht ist vollstaendig geschlossen (GPU-Preismodell-Kalkulation, 5x-Alice-Tracking, Chargeback-CSV-Summierung, 85%-Budget-Alert).
- Chargeback rechnet RAM-Kosten jetzt korrekt in `total_cost` ein.
- Validierung lokal und auf `srv1` mit identischem Pytest-Scope (`37 passed` auf beiden).

**Naechste konkrete Schritte**:

1. **Plan 05 vertiefen**: Chargeback-Drilldown um explizite Session-Zeilen im CSV/JSON erweitern (nicht nur Aggregation je Department/User).
2. **Plan 04 vertiefen**: offene Automatisierung der Warm-Pool-Empfehlungen kontrolliert hinter Feature-Flag nachziehen.
3. **Plan 01 WireGuard-Rest schliessen**: verbleibende WireGuard-Mesh-/Latency-Testpflichtpunkte reproduzierbar im Runtime-Scope abnehmen.
4. **Plan 02 live validieren**: grafischen Sperrbildschirm weiter auf echter Thin-Client-Hardware/X11-/Wayland-Setups abnehmen.

## Stand (2026-04-28, GoEnterprise Plan 04/05/09 analytics follow-up)

**Zuletzt erledigt**:
- Chargeback zeigt jetzt Forecast Monatsende, Energiekosten gesamt und Top-10 kostenintensive VMs.
- Energiekosten sind im Cost-/Chargeback-Pfad jetzt mit eigener Regression abgesichert.
- Scheduler-Insights zeigen jetzt neben Prewarm-Kandidaten auch eine erste 7-Tage-Historie und 24h-Prognose auf Basis der Metrics-/Workload-Historie.

**Naechste konkrete Schritte**:

1. **Plan 04 vertiefen**: echte Heatmap-Visualisierung statt Tabellen-Listing und später Pool-/User-bezogene Saved-CPU-Hours differenzieren.
2. **Plan 05 vertiefen**: Department- und Pool-Drilldown bis auf Session-Ebene im Dashboard nachziehen.
3. **Plan 09 vertiefen**: Ranking effizienteste vs. energieintensivste VMs/Nodes im Energy-Panel nachziehen.
4. **Plan 09 Green-Scheduling härten**: Green-Hours explizit modellieren und die Prognose-/Placement-Entscheidung zeitfensterbasiert statt nur global gewichtet machen.
5. **Plan 02 live validieren**: Lock-Screen, Wipe und Runtime-Telemetrie weiter gegen echte Thin-Client-Hardware/X11-/Wayland-Sessions abnehmen.
6. **Plan 07 live validieren**: Fleet-Alerts und Predictive-Maintenance gegen echte Runtime-Events provozieren und Webhook-/UI-Reaktion prüfen.

## Stand (2026-04-28, GoEnterprise Plan 04/05/09 operator follow-up)

**Zuletzt erledigt**:
- Scheduler-, Cost- und Energy-Panels sind jetzt nicht mehr read-only, sondern haben echte Operator-Konfiguration im Dashboard.
- Cost- und Energy-Settings synchronisieren jetzt `electricity_price_per_kwh` kontrolliert zwischen beiden Planes.
- Scheduler-Insights zeigen jetzt Prewarm-Kandidaten und eine erste `saved_cpu_hours`-Schätzung auf Basis der vorhandenen Metrics-/Workload-Historie.

**Naechste konkrete Schritte**:

1. **Plan 04 vertiefen**: echte historische Heatmap und 24h-Prognose aus persistierten Metrics ableiten, statt aktuell nur den Cluster-Istzustand zu zeigen.
2. **Plan 05 abschliessen**: Forecast pro Abteilung und Top-10 kostenintensive VMs direkt im neuen Cost-Panel nachziehen.
3. **Plan 09 vertiefen**: Energy-Cost-Integration mit echten Session-/Chargeback-Daten nachziehen und `tests/unit/test_energy_cost_integration.py` einführen.
4. **Plan 09 Green-Scheduling härten**: Green-Hours explizit modellieren und im Scheduler nicht nur per globalem Faktor, sondern per Zeitfenster anwenden.
5. **Plan 02 live validieren**: Lock-Screen, Wipe und Runtime-Telemetrie weiter gegen echte Thin-Client-Hardware/X11-/Wayland-Sessions abnehmen.
6. **Plan 07 live validieren**: Fleet-Alerts und Predictive-Maintenance gegen echte Runtime-Events provozieren und Webhook-/UI-Reaktion prüfen.

## Stand (2026-04-28, GoEnterprise Plan 04/05/09 follow-up)

**Zuletzt erledigt**:
- Scheduler-, Chargeback- und Energy-/CSRD-Panels sind jetzt keine toten UI-Module mehr, sondern laufen über echte Control-Plane-Routen im Hauptdashboard.
- Rebalancing-Empfehlungen lassen sich jetzt aus der WebUI direkt ausführen; Kosten-CSV und CSRD-Export sind am Dashboard verdrahtet.
- Die neuen Enterprise-Surfaces sind per RBAC auf `settings:read` / `settings:write` gelegt und mit gezielten Read-Surface-/UI-Regressions abgesichert.

**Naechste konkrete Schritte**:

1. **Plan 04 weiter vertiefen**: historische Scheduler-Heatmap und echte Prewarming-/Saved-CPU-Hours-Metrik nachziehen, damit das Dashboard nicht nur den Ist-Zustand zeigt.
2. **Plan 05 vervollstaendigen**: Preismodell-Editor und Budget-Verwaltung im Settings-/Enterprise-Flow sichtbar machen, statt nur die Read-Surface zu liefern.
3. **Plan 09 vertiefen**: Energy-Admin-Konfiguration und echte Green-Scheduling-Integration mit Plan 04 schließen.
4. **Plan 02 live validieren**: Lock-Screen, Wipe und Runtime-Telemetrie weiter gegen echte Thin-Client-Hardware/X11-/Wayland-Sessions abnehmen.
5. **Plan 07 live validieren**: Fleet-Alerts und Predictive-Maintenance gegen echte Runtime-Events provozieren und Webhook-/UI-Reaktion prüfen.
6. **Plan 01 Fork-Pfad weiterziehen**: VPN-Enforcement nach dem aktuellen Broker-Pfad auch im späteren `beagle-stream-server`-Fork vorbereiten.

## Stand (2026-04-28, GoEnterprise Plan 02 follow-up)

**Zuletzt erledigt**:
- GoEnterprise Plan 02 hat jetzt die erste echte Operator-Flaeche fuer die Thin-Client-Registry:
  - Fleet-/Device-Registry-Endpunkte laufen ueber die Control Plane
  - Dashboard rendert Hardware, Online-Status, `last_seen`, Standort und Gruppe
  - Fleet-Routen sind per RBAC auf `settings:read` / `settings:write` gelegt, Lock/Wipe/Unlock sind im UI bedienbar und die Aktionen schreiben Audit-Events
  - Thin-Client-Runtime synchronisiert Heartbeat, Hardware und VPN-Zustand jetzt per endpoint-authentifiziertem `device/sync` und zieht dabei MDM-Policy + Lock/Wipe-Status zurück
  - `vpn_required` wird im aktuellen Session-Broker jetzt serverseitig gegen den persistierten WireGuard-Status des Devices erzwungen
  - `locked` blockiert den Session-Start jetzt hart; `wipe_pending` fuehrt einen reproduzierbaren Runtime-Secret-Wipe aus und meldet `confirm-wiped` zurueck
  - die Fleet-WebUI hat jetzt einen echten MDM-Policy-Editor samt Device-/Group-Assignment-Flow
  - effective-policy-preview und Bulk-Device-Policy-Zuweisung sind jetzt ebenfalls direkt im Fleet-Panel bedienbar

**Naechste konkrete Schritte**:

1. **Plan 02 Wipe live abnehmen**: den neuen Storage-/TPM-Wipe auf echter Thin-Client- oder VM-Hardware verifizieren und den Umgang mit `partial`/`failed`-Reports operationalisieren.
2. **Plan 02 Device-UX live abnehmen**: den jetzt erweiterten Sperrbildschirm und die neue Runtime-Telemetrie auf echter X11-/Wayland-Session und echter Multi-Display-Hardware pruefen.
3. **Plan 07 live abnehmen**: Fleet-Alerts gegen echte Thin-Client-Hardware oder VM-Runtime provozieren und verifizieren, dass WebUI + Webhook-Dispatch wie erwartet reagieren.
4. **Plan 02/07 Fleet-Operatorik nachziehen**: Runtime-Telemetrie um Session-/Health-/Streaming-Signale erweitern, damit Lock/WG/Display nicht die letzten sichtbaren Ist-Daten bleiben.
5. **Plan 02 Policy-Plane weiter automatisieren**: auf der neuen Drift-/Run-/Config-Surface weitere sichere Batch-Aktionen und spaetere echte Auto-Remediation-Worker aufbauen.
6. **Plan 01 Fork-Pfad weiterziehen**: den spaeteren `beagle-stream-server`-Enforcement-Pfad im Sunshine-Fork vorbereiten, obwohl der heutige Broker-Pfad bereits blockiert.

## Stand (2026-04-27, two-host follow-up)

**Zuletzt erledigt**:
- Installer-/USB-Downloadskripte schreiben jetzt nachweisbare API-Logs mit kurzlebigen write-only Tokens; `srv1`-Live-Smoke fuer VM100-Logkontext, Script-Events, Invalid-Token-401 und `/beagle-downloads/` ist gruen.
- Release-Linie wurde im Repo auf `8.0` angehoben; GitHub-Release-Erstellung ist der naechste abschliessende Schritt nach Commit/Push und finaler Validierung.
- Repo-Auto-Update-/Host-Install-Self-Heal gegen kaputte Runtime-Symlink-Loops (`/opt/beagle/beagle-host` / `beagle_host`) ist jetzt im Repo verankert.
- Plan 11 Parity bekam jetzt auch den fehlenden ISO/qcow2/raw/img-Upload-Endpunkt (`POST /api/v1/storage/pools/{pool}/upload`) inklusive Quota- und Content-Validierung.
- Plan 11 Parity bekam jetzt auch Storage-Dateiliste und Download (`GET /api/v1/storage/pools/{pool}/files` plus `?filename=...`) inklusive Virtualization-UI-Flow im Storage-Panel.
- Plan 11 Parity bekam jetzt auch direktes LDAP-Bind und lokalen TOTP-Zweitfaktor im Auth-Stack.
- Policies-Panel hat jetzt eine Subnavigation fuer die Hauptbereiche; der Ist-Zustand ist in Plan 10 dokumentiert.
- Passwort-/Username-Felder in Hidden- und Modal-Flows sind in sauberere Form-Kontexte gezogen; die Browser-Warnungen sind deutlich reduziert.
- Policies-UI wurde sichtbarer modernisiert: Hero-Band, Main/Side-Workspace, kompaktere Pool-Cards und Entitlement-Chips sind live auf `srv1`.
- Policies Plan 10 bekam einen echten Entitlement-Operator-Flow: ausgewählter Pool zeigt User-/Group-Entitlements als Chips und kann direkt per UI gepflegt werden.
- Policies Plan 10 bekam eine Template-Bibliothek als Kartenansicht: OS, Storage, Source-VM, Build-Zeit, Health sowie `verwenden`/`neu bauen`/`löschen` sind jetzt direkt im Panel bedienbar.
- Policies Plan 10 bekam jetzt auch eine bestätigte Pool-Delete-Danger-Action mit Slot-Zähler; der verbleibende Rest liegt weiter beim strukturierten Policy-Editor und der Bulk-/Scale-/Recycle-Absicherung.
- IAM Plan 13 Schritt 7 ist jetzt auch als E2E-Smoke auf `srv1` geschlossen (`PLAN13_IAM_SMOKE=PASS`).
- Audit Plan 15 Schritt 6 ist jetzt mit UI-Regressions und Live-Smoke auf `srv1` geschlossen (`AUDIT_COMPLIANCE_SMOKE=PASS`).
- GoFuture Virtualization-Panel ist im Plan-Stand jetzt sauber als erledigt markiert; Nodes, Storage, Bridges, GPU/vGPU/SR-IOV und VM-Inspector sind bereits live bedienbar.
- GoEnterprise Plan 08 weiter geschlossen: Seed-Discovery im Server-Installer ist jetzt produktiv verdrahtet (`/media/beagle-seed.yaml`, `/run/live/medium/...`, `beagle.seed_url=...`), PXE-Setup-Script + Doku + Integrations-Smoke liegen im Repo.
- PXE-Dry-Run gegen echte Installer-Artefakte auf `srv1` und `srv2` erfolgreich; beide Hosts erzeugen konsistente `dnsmasq`-/TFTP-Baeume im isolierten Temp-Root.
- Cluster-Installer-Glue geschlossen: Auto-Join-Oneshot, Install-Check-API, Cluster-Banner in der WebUI.
- Live-Drift im laufenden Zwei-Host-Cluster behoben: `srv1` und `srv2` verwenden wieder gueltige `/beagle-api`-Member-URLs und sehen sich gegenseitig als `online`.
- `srv2` hat einen erfolgreichen Post-Install-Check an `srv1` gemeldet; der Report ist auf dem Leader abrufbar und in der WebUI sichtbar.
- GoEnterprise Plan 06 Schritt 3 begonnen: endpoint-authenticated Session-Broker `GET /api/v1/session/current` und Thin-Client-Reconnect-Hook sind umgesetzt; live auf `srv1` mit echtem Endpoint-Token erfolgreich abgenommen.
- GoEnterprise Plan 06 weiter geschlossen: Timing-Test `<5s`, Geo-Routing-Backend, Handover-History-API und Slow-Handover-Alerts sind implementiert; `scripts/smoke-session-handover-flow.sh` lieferte auf `srv1 -> srv2` live `PASS` in `0.29s`.
- GoEnterprise Plan 06 abgeschlossen: die WebUI rendert die neue Session-Handover-Historie jetzt live im Policies-Panel; auf `srv1` ist der neue Operator-Block mit echten `srv1 -> srv2`-Events browserseitig verifiziert.
- GoAdvanced Plan 10 Schritt 4 geschlossen: `tests/integration/test_ha_failover.py` ergänzt; gesamter Integrationssatz liegt jetzt bei `87 passed`.

**Naechste konkrete Schritte**:

1. **Cluster-WebUI-Operations vervollstaendigen**: `docs/gofuture/00-index.md` Schritt "Cluster-Operations in der WebUI vollständig machen" bleibt als echter Zwei-Host-Operator-Block offen.
2. **Release 8.0 abschliessen**: nach finalem Testlauf committen, pushen, Tag/Release `v8.0` auf GitHub erzeugen und pruefen, dass GitHub nicht mehr `6.6.7` als neuesten Release zeigt.
3. **Installer-Restgrenze sauber schliessen**: Mehrdisk-RAID und echter PXE-Boot mit DHCP-seitiger Seed-Uebergabe bleiben als verbleibender Installer-Nachlauf offen.
4. **Plan-11-Parity-Rest auf die großen Themen begrenzen**: offen bleiben jetzt nur noch SDN/Overlay, HA-Manager und zero-downtime Live-Migration.
5. **VM-Operator-Regressionen weiter verdichten**: nachgezogene noVNC-/Delete-UI-Regressions sind jetzt im Repo; naechster sinnvolle CI-Rest waere ein echter UI-Provisioning-Smoke.
6. **Self-Heal live nochmals beweisen**: nach Push muss `srv1` den neuen `origin/main`-Stand per `beagle-repo-auto-update.service` selbst ziehen und mit `state=healthy` enden.

## Stand (2026-04-26, GoFuture Re-Open: WebUI-Operability)

**Zuletzt erledigt**:
- GoFuture-Index und Detailplaene fuer `/#panel=cluster`, `/#panel=virtualization`, `/#panel=policies`, `/#panel=iam` und `/#panel=audit` mit echten Checkbox-Backlogs erweitert.
- Abschlussregel geschaerft: Statusanzeigen reichen nicht; Operator-Flows muessen in der WebUI bedienbar, validiert, progress-faehig und getestet sein.
- Erster Cluster-Wizard-Slice umgesetzt: lokaler Join in bestehenden Cluster per WebUI/API (`POST /api/v1/cluster/join-existing`) plus Setup-Card im Cluster-Panel.
- Leader-Preflight-Slice umgesetzt: `POST /api/v1/cluster/add-server-preflight` plus WebUI-Wizard fuer DNS/API/RPC/SSH-Pruefung und Join-Token nach bestandenem Pflicht-Preflight.
- Cluster-Panel markiert den lokalen Host jetzt sichtbar als `LEADER`, `MEMBER` oder `SETUP`; Leader-only Aktionen werden nur auf dem Leader angeboten.
- Der Leader-Wizard "Weiteren Server vorbereiten" ist jetzt auf eine Laien-Eingabe reduziert: Servername und Zielserver-Setup-Code eingeben; technische Felder liegen im Expertenbereich.
- Echter Zielserver-Setup-Code fuer Auto-Join ist implementiert: Zielserver erzeugt nach Login einen kurzlebigen, gehasht gespeicherten Einmal-Code; Leader verbindet per Hostname + Code ohne offene Remote-Health-/Inventory-Abfrage.
- Cluster-Member-Leave folgt jetzt einem 2-Phasen-Flow: Leader entfernt den Member autoritativ per mTLS-RPC, danach wird lokal aufgeraeumt.
- `GET /api/v1/virtualization/overview` ist cluster-aware; `srv1` und `srv2` zeigen beide dieselbe Knotenliste statt nur den lokalen Node.
- `/#panel=virtualization` hat jetzt einen echten Node-Detail-Flow mit Backend-Endpoint `GET /api/v1/virtualization/nodes/{node}/detail`, Service-/Reachability-Status und Live-Validierung auf `srv1`/`srv2`.
- Join-Tokens haben jetzt eine echte serverseitige Ablaufpruefung.
- Auth-503-Bursts reduziert: nginx `beagle_auth` Rate-Limit angehoben und Dashboard fragt IAM-User/Roles nur noch im IAM-Panel ab.
- Artifact-Operations-Slice umgesetzt: `GET/POST /api/v1/settings/artifacts*` plus WebUI-Status/Refresh im Updates-Panel.
- Artifact-Watchdog umgesetzt: WebUI kann den Host-Watchdog aktivieren, konfigurieren und direkt anstoßen; `srv1` und `srv2` melden nach abgeschlossenem Refresh jetzt `healthy` und `public_ready=true`.
- `/#panel=settings_updates` vereinfacht: nur noch drei moderne Karten fuer APT-Systemupdates, GitHub-Repo-Updates und Artefaktbau; Direktaufruf laedt Statusdaten nach Admin-Login automatisch ohne Button-Klick.
- Lange Artifact-/ISO-Builds sind in der WebUI jetzt sichtbar: Live-Phase, Laufzeit, aktive Prozessanzahl, Fortschrittsbalken und erklaerender Hinweis werden waehrend des laufenden Builds angezeigt.
- Lokale Regression: `42 passed` fuer Auth-HTTP, Cluster-Membership, Cluster-HTTP-Surface und AuthZ; Live-Burst auf `srv1` gegen `/auth/roles`: 35x `401`, 0x `503`.

**Naechste konkrete Schritte**:

1. **Repo-Auto-Update live fertig validieren**: nach Push auf `origin/main` `repo_auto_update_enabled=true` auf `srv1` und `srv2` setzen, manuellen GitHub-Check aus der WebUI/API anstoßen und bestaetigen, dass `/opt/beagle` auf den neuen Commit aktualisiert wird.
2. **Long-Build-Status final abnehmen**: laufende Repo-Auto-Updates auf `srv1`/`srv2` bis `state=healthy` beobachten und bestaetigen, dass die neue Live-Statusanzeige bis zum Abschluss korrekt bleibt.
3. **GitHub Release-Workflow erneut gegen echten Push pruefen**: bestaetigen, dass `.github/workflows/release.yml` nach dem Parse-Fix wieder laeuft und auf Push nach `main` einen neuen Rolling-/Release-Lauf erzeugt.
4. **Plan 12 Nachlauf nur optional**: voller NVIDIA-Treiber-/Streaming-Benchmark im Gast waere noch zusaetzliche Komfortvalidierung, ist aber kein Pflichtblocker mehr.
5. **Thinclient-Hardware-Rerun auf echtem Stick**: neuen VM100-USB-Stick von `srv1` erzeugen und den bisher fehlgeschlagenen physischen `Preset Installation starten`-Pfad auf echter Hardware erneut abnehmen.
6. **Thinclient-Runtime visuell abnehmen**: lokale installierte Ziel-Disk mit grafischem Capture/Screenshot bis zur sichtbaren Moonlight-Session gegen `vm100` pruefen.
7. **Security vor Cluster-Komfort**: separate legacy HTTPS listener abschalten; Installer-/Download-Pfade auf `443` migrieren.
**Blocker/Risiken**:
- `srv2` GPU: GTX 1080 ist an `vfio-pci`, aber IOMMU-Gruppe enthaelt weitere Geraete; Passthrough bleibt ohne ACS/BIOS/Hardware-Aenderung nicht sicher freigebbar.
- Artifact-Refresh ist jetzt auf `srv1` und `srv2` gruen; offener Rest fuer Plan 06 ist jetzt das echte Zusammenspiel `GitHub-Repo-Update -> Host-Deploy -> Artifact-Watchdog`.
- `srv2` hat im aktuellen Browser-Smoke zwar keine Console-Errors mehr, nutzt aber weiterhin eine Zertifikatskette mit frueherem `ERR_CERT_AUTHORITY_INVALID`-Fund; TLS-Bereinigung bleibt separat offen.

---

## Stand (2026-05-XX, GoAdvanced Plan 07 vollständig: Async Job Queue)

**Zuletzt erledigt**:
- Plan 07 Schritt 3 komplett: `POST /api/v1/cluster/migrate` → enqueue + 202 (cluster_http_surface)
- Plan 07 Schritt 5: `Idempotency-Key`-Header in HTTP-Surfaces verdrahtet (backup + snapshot)
- Plan 07 Schritte 1–5 vollständig abgeschlossen
- Plan 10 Schritt 7 CI: `.github/workflows/e2e-nightly.yml` erstellt
- Test-Baseline: 968 passed (unit + integration), 0 Regressions

**Nächste konkrete Schritte**:

1. **Plan 07 Schritt 6** (MEDIUM): Web-UI Jobs-Panel mit SSE-Subscribe + Toast bei Job-Completion.
2. **Plan 09 CI Pipeline**: Restliche CI-Checks (lint, security) konsolidieren.
3. **Plan 08 Observability**: Structured logging + Prometheus-Metriken Endpoint.
4. **Plan 09** (HIGH, in Planung): HA-Manager — Prerequisit für Plan 10 Schritt 4 (HA-Failover-Tests).

---

## Stand (2026-04-25, update) — Terraform Provider Fix + Migration Service Wiring

**Zuletzt erledigt (dieser Session)**:
- **Terraform Provider Bugfix** (`728f70e`):
  - `client.requestWithStatus()` hinzugefügt (unterscheidet 404 von anderen Fehlern)
  - `resourceVMRead` fixt: nur Resource-ID löschen bei echtem 404, nicht auf allen Errors
  - Schema-Felder nun bevölkert mit API-Response-Werten
  - Unit-Tests: 4/4 pass (TestClientCreateReadDelete, TestClientReadNotFound, TestClientBadToken, TestApplyCreatesVMDestroyRemovesVM)
  - Validierung: `terraform apply` + `destroy` auf srv1 gegen beagle_vm.test (vmid=9901), APPLY_EXIT=0, DESTROY_EXIT=0 ✅

- **Migration Service: Cluster-Inventory-Wiring** (`fdc308d`):
  - Neuer Helper `_cluster_nodes_for_migration()` ruft `build_cluster_inventory()` auf
  - Wiring updated: `migration_service`, `ha_manager_service`, `maintenance_service`, `pool_manager_service` nutzen cluster-aware node list
  - **Folge**: Remote Hypervisoren (z.B. beagle-1) sind jetzt sichtbar als gültige Migrations-Ziele
  - Unit-Tests: 24/24 pass (migration, ha_manager, maintenance, pool_manager)
  - Deployment auf srv1/srv2 + systemctl restart beagle-control-plane → `active` ✅
  - Cluster-Inventory nach Deployment: alle 4 Knoten (beagle-0, beagle-1, srv1, srv2) online ✅

- **SSH-Keys für Cross-Node Migration**:
  - Beagle-manager SSH-Keys (ed25519) generiert auf srv1/srv2
  - Cross-authorized: srv1-key in srv2 authorized_keys, srv2-key in srv1 authorized_keys
  - Validierung: `sudo -u beagle-manager ssh root@beagle-1` → CONNECTION_OK ✅
  - `BEAGLE_CLUSTER_MIGRATION_URI_TEMPLATE=qemu+ssh://root@{target_node}/system` in `/etc/beagle/beagle-manager.env` ✅

---

### **Gefundenes QEMU+SSH Migration-Deadlock-Problem**
Virsh-basierte Live-Migration über `qemu+ssh` deadlockt bei allen Versuch-Kombinationen:
- `virsh migrate --live --copy-storage-inc`: Timeout nach 60-120s, kein Fortschritt
- `virsh migrate --live --copy-storage-all`: Gleiches Verhalten
- `virsh migrate --persistent --undefinesource`: Bringt libvirt in Deadlock (`another migration job already running`)
- `virsh domjobinfo` während Migration: Timeout (kompletter libvirt-Lock)
- Root-Ursache: Qemu+SSH Migration-Protokoll oder Libvirt-Konfiguration inkompatibel (erfordert tiefere QEMU/Libvirt-Untersuchung)

**Implikation für Beagle Migration-API**:
- API-Layer ist funktional (kann Ziel-Knoten korrekt identifizieren, SSH-Schlüssel vorhanden, qemu+ssh Connectivity OK)
- **Aber**: Virtualisierungs-Infrastruktur-Layer (virsh+qemu+ssh) ist fehlerhaft und braucht separate Untersuchung
- **Workaround für Multi-Node-Produktion**: Shared Storage (NFS/Ceph) verwenden statt Storage-Copy während Migration
- Migration-API wird korrekt arbeiten, sobald Shared Storage vorhanden oder QEMU+SSH-Protokoll repariert ist

## Zuletzt erledigt (vorherige Session, 2026-04-25)

- GoFuture Gate: alle 20 Pläne (docs/gofuture/) abgeschlossen (d588939)
- `service_registry.py` extrahiert: `beagle-control-plane.py` 4964 → 1627 LOC (e2e4c38)
- `request_handler_mixin.py` extrahiert: `beagle-control-plane.py` 1627 → 899 LOC (03bd203)
- **Multi-Node Cluster**: srv1 (46.4.96.80) + srv2 (176.9.127.50) verbunden (52f5d48)
  - `BEAGLE_MANAGER_LISTEN_HOST=0.0.0.0` auf beiden Servern
  - members.json URLs korrigiert (127.0.0.1 → echte IPs)
  - srv2 via Join-Token beigetreten: `3/3 nodes online, 0 unreachable`
- **Cluster-Metriken**: `beagle-0` (srv1) und `beagle-1` (srv2) zeigen echte RAM/CPU-Werte
  - Root-Ursache: Beide Hypervisoren hießen `beagle-0` (Name-Kollision)
  - Fix: `BEAGLE_BEAGLE_PROVIDER_DEFAULT_NODE=beagle-0` auf srv1, `beagle-1` auf srv2
  - `/api/v1/cluster/nodes` zeigt jetzt `beagle-0: 64GB/12CPU`, `beagle-1: 64GB/8CPU`
- **GoEnterprise: VM Stateless Reset** umgesetzt:
  - Neuer Provider-Contract + Implementierung `reset_vm_to_snapshot(...)`
  - Pool-Manager-Wiring aktiv (`reset_vm_to_template`), nutzt Template-`snapshot_name`
- **GoEnterprise: RBAC kiosk_operator** umgesetzt:
  - Neue Default-Rolle `kiosk_operator` mit `vm:read`, `vm:power`
  - VM-Power-Endpoint nutzt jetzt Permission `vm:power` (Backwards-Compat für `vm:mutate` bleibt)
- **Cluster-Sicherheit Port 9088 gehärtet**:
  - Neues reproduzierbares Script `scripts/harden-cluster-api-iptables.sh` (idempotent, Chain `BEAGLE_CLUSTER_API_9088`)
  - Live ausgerollt auf `srv1`/`srv2` mit Peer-Allowlist (`srv1` erlaubt `176.9.127.50`, `srv2` erlaubt `46.4.96.80`)
  - Persistenz aktiviert (`netfilter-persistent` + `iptables-persistent`, `rules.v4` enthält 9088-Chain)

---

### Verbleibende Punkte (nach Priorität)

0. **GPU-Zeitfenster auf `srv2` nutzen, solange der Host noch verfuegbar ist**:
   - Erledigt: `srv2` GPU-Passthrough-Smoke per transienter VM; Gast sah GTX 1080 (`10de:1b80`) und Audio (`10de:10f0`).
   - Erledigt: GPU-Plane-WebUI mit Assign-/Release-Wizard, mdev-Cards, SR-IOV-Cards und UI-Regressions; Assets auf `srv1`/`srv2` ausgerollt.
   - Optional: voller NVIDIA-Treiber-/Streaming-Benchmark im Gast, falls `srv2` noch lange genug verfuegbar bleibt.
   - Danach: offene Nicht-GPU-WebUI-Smokes fuer IAM/Audit und die restlichen GoAdvanced/GoEnterprise-Punkte weiter abarbeiten.

1. **Plan 07 Rest-Lasttest**:
   - Optionalen 5GB-Backup-Lasttest auf `srv1` mit echter gross genug belegter VM/Disk ausfuehren.
   - Funktional ist Plan 07 runtime-faehig: Worker-Handler, SSE, UI-Subscribe, Idempotency und persistierte Job-History sind validiert.

2. **Plan 09 Schritt 6**: Branch-Protection-Regeln in GitHub repository settings aktivieren.
   _Manueller Schritt im GitHub UI; nicht Teil der technischen Untersetzung._

3. **QEMU+SSH Migration-Protokoll debuggen** (optional, nicht auf kritischem Pfad):
   - Untersuche Libvirt-Konfiguration, Firewall-Regeln, SSH-Agent-Issues
   - Alternativ: Shared Storage für Migration evaluieren
- Echten Runtime-Test fuer den neuen Windows-Live-USB-Writer auf Windows/UEFI-Hardware oder Windows-VM durchziehen und Bootverhalten verifizieren.
- Host-Downloads auf `srv1.beagle-os.com` und `srv2.beagle-os.com` mit den neuen `pve-thin-client-live-usb-*.ps1` Artefakten aktualisieren und per Download-Status gegenpruefen.
- WebUI-VM-Detail live auf `srv1`/`srv2` gegen den neuen `live-usb.ps1`-Pfad smoke-testen.
- Repo-/Artifact-Self-Heal weiter härten:
  - End-to-end smoke for VM installer/live-USB downloads after the next unattended repo auto-update on `srv1`
  - verify that regenerated hosted artifacts and VM-specific scripts still stay on `443` after that unattended update cycle
  - watch for repeated kiosk `npm` rename failures; `scripts/package.sh` now self-heals `ENOTEMPTY` once, but Node 18 engine warnings remain technical debt for the kiosk build chain
- GoRelease als neue Freigabeebene nutzen:
  - `docs/gorelease/00-index.md` vor Firmen-/Pilot-Entscheidungen lesen
  - zuerst R2/R3-Gates abarbeiten, nicht neue GoEnterprise-Features als "fertig fuer Firmen" interpretieren
  - Hardware nach `docs/gorelease/02-hardware-test-matrix.md` buchen: kleine Hetzner VMs fuer guenstige Dauer-Smokes, dedizierte KVM-Hosts nur fuer echte VM-/Install-Abnahme, GPU-Server nur im kurzen Testfenster
- Lokale GoRelease-Validierung ist bereits gruen:
  - Download-URLs normalisieren `443` weg
  - Installer-Downloads schreiben scoped Log-Events via API
  - naechster Schritt sind die verbleibenden Host-/Live-Gates auf `srv1`; `srv2` ist gekuendigt
- Thin-client USB install path runtime-smoke:
  - boot a freshly written USB installer/live medium in a VM
  - verify from installer logs that local bundled payload assets are used after the target-disk selection step
  - ensure no second remote payload download happens unless `PVE_THIN_CLIENT_FORCE_REMOTE_PAYLOAD=1`
- `srv2` TLS-/Zertifikatskette pruefen: Chrome DevTools sah am 27.04.2026 initial `ERR_CERT_AUTHORITY_INVALID`, obwohl die WebUI nach Ausnahme-Proceed und der Login-POST selbst funktionierten.
- Optional: Login-Modal/weitere Passwortfelder im HTML in echte `<form>`-Container ueberfuehren, damit die verbleibenden DevTools-DOM-Warnungen (`Password field is not contained in a form`) verschwinden.
- GoEnterprise Plan 03 weiterziehen:
  - Kiosk-Controller nicht nur im DOM, sondern mit echter Admin-Session auf `srv1`/`srv2` end-to-end testen
  - Session-Verlaengerung/Reset-Aktion statt nur `end` produktiv machen
  - pruefen, ob `kiosk_operator` fuer die gewuenschte Sichtbarkeit zusaetzlich Pool-Scoped Filter statt globaler Kiosk-Sicht braucht
- GoEnterprise Plan 03 / Plan 10 weiterziehen:
  - Pool-Wizard fuer GPU-Pooltypen weiterziehen: heute live Passthrough-Selektor + mdev/SR-IOV-Hints; als naechstes echte authentifizierte Slot-/Klassenvalidierung vervollstaendigen
- authenticated Live-Smoke fuer Gaming-Pools auf `srv1`/`srv2`: Stream-Health fuer echte Gaming-Session einspeisen und Dashboard mit Live-Daten pruefen
- `docs/goenterprise/03-gaming-kiosk-pools.md`: verbleibende Testpflicht fuer Gaming-Pool-Allocation ohne GPU sowie Kiosk-/RBAC-E2E sauber abschliessen
# Next Steps

## Stand (2026-04-28, GoEnterprise Plan 04/09 telemetry follow-up)

**Zuletzt erledigt**:
- Prewarm-Erfolg wird jetzt als echte Hit-/Miss-Telemetrie im Pool-Manager persistiert.
- Warm-Pool-Empfehlungen lassen sich direkt aus dem Scheduler-Panel anwenden.
- Das stündliche Energy-Profil hat jetzt einen eigenen Import-Endpunkt und eigenen UI-Flow.

**Naechste konkrete Schritte**:

1. **Plan 04 weiter operationalisieren**: Warm-Pool-Empfehlungen nicht nur manuell anwenden, sondern optional als sichere Auto-Scale-Policy ausführen.
2. **Plan 04 Erfolgsmessung vertiefen**: echte Wait-Time-Metrik aus Session-/Provisioning-Pfaden statt pauschalem `saved_wait_seconds`-Default erfassen.
3. **Plan 09 Feed vervollständigen**: externen Feed-/Importjob für das 24h-CO₂-/Preisprofil periodisch nachziehen.
4. **Plan 02 live validieren**: Lock-Screen, Wipe und Runtime-Telemetrie weiter gegen echte Thin-Client-Hardware/X11-/Wayland-Sessions abnehmen.
5. **Plan 07 live validieren**: Fleet-Alerts und Predictive-Maintenance gegen echte Runtime-Events provozieren und Webhook-/UI-Reaktion prüfen.

## Stand (2026-04-28, GoEnterprise Plan 04/09 productive follow-up)

**Zuletzt erledigt**:
- `smart_scheduler` hängt jetzt im produktiven Pool-Placement-Pfad für neue Desktop-Slots.
- Scheduler-Insights differenzieren `saved_cpu_hours` jetzt nach Pool und User.
- Energy-Dashboard arbeitet jetzt mit einem editierbaren stündlichen CO₂-/Strompreisprofil statt nur einer globalen Basiskonfiguration.

**Naechste konkrete Schritte**:

1. **Plan 04 Placement weiter haerten**: den Smart-Scheduler nicht nur bei Slot-Registrierung, sondern auch bei Scale-/Warm-Pool-Entscheidungen tiefer einziehen.
2. **Plan 04 Erfolgsmessung haerten**: echte Prewarm-Hit-/Miss-Telemetrie statt rein kandidatbasierter Saved-CPU-Hours-Auswertung aufbauen.
3. **Plan 09 Feed operationalisieren**: stündliches CO₂-/Strompreisprofil optional aus externem Feed oder Importjob aktualisieren, statt nur manuell im Dashboard.
4. **Plan 02 live validieren**: Lock-Screen, Wipe und Runtime-Telemetrie weiter gegen echte Thin-Client-Hardware/X11-/Wayland-Sessions abnehmen.
5. **Plan 07 live validieren**: Fleet-Alerts und Predictive-Maintenance gegen echte Runtime-Events provozieren und Webhook-/UI-Reaktion prüfen.

## Stand (2026-04-28, GoEnterprise Plan 04/09 green-window follow-up)

**Zuletzt erledigt**:
- Scheduler-Insights rendern jetzt eine stündliche 7-Tage-Heatmap pro Node statt nur Tagesdurchschnittstabellen.
- Green Scheduling ist im produktiven Scheduler-Pfad jetzt zeitfensterbasiert über `green_hours` verdrahtet.
- Energy-Dashboard zeigt jetzt eine eigene Green-Hours-Heatmap aus Carbon-/Strompreis-Konfiguration und Scheduler-Fenster.

**Naechste konkrete Schritte**:

1. **Plan 04 produktiv schließen**: `smart_scheduler` wirklich als optionalen Drop-In in den produktiven Pool-/Placement-Pfad ziehen.
2. **Plan 04 Analytics vertiefen**: Saved-CPU-Hours und Prewarm-Erfolg pro Pool/User differenzieren statt nur global zu summieren.
3. **Plan 09 Datenbasis vertiefen**: echten stündlichen Carbon-/Strommix-Feed hinter die Green-Hours-Heatmap legen, statt nur die aktuelle Konfiguration zu projizieren.
4. **Plan 02 live validieren**: Lock-Screen, Wipe und Runtime-Telemetrie weiter gegen echte Thin-Client-Hardware/X11-/Wayland-Sessions abnehmen.
5. **Plan 07 live validieren**: Fleet-Alerts und Predictive-Maintenance gegen echte Runtime-Events provozieren und Webhook-/UI-Reaktion prüfen.

## Stand (2026-04-28, GoEnterprise Plan 04/05/09 drilldown follow-up)

**Zuletzt erledigt**:
- Chargeback-Dashboard zeigt jetzt den Drilldown Abteilung -> User -> Session direkt aus der Control Plane.
- Energy-Dashboard hat jetzt echte Rankings fuer hoechsten/niedrigsten Node-Verbrauch sowie energieintensivste/effizienteste VMs.
- Scheduler-Operatorik modelliert Green Hours jetzt explizit und zeigt den aktiven Green-Window-Status direkt im Dashboard.

**Naechste konkrete Schritte**:

1. **Plan 04 vertiefen**: Heatmap-Visualisierung und differenzierte Saved-CPU-Hours pro Pool/User statt nur Gesamtwert nachziehen.
2. **Plan 04 haerten**: Green-Hours nicht nur anzeigen, sondern die zeitfensterbasierte Placement-/Prewarm-Entscheidung tiefer in den produktiven Scheduler-Pfad ziehen und mit eigener Regression absichern.
3. **Plan 09 vervollstaendigen**: Gruene-Stunden-Heatmap im Energy-Panel aus echten Carbon-/Strommix-Daten rendern.
4. **Plan 02 live validieren**: Lock-Screen, Wipe und Runtime-Telemetrie weiter gegen echte Thin-Client-Hardware/X11-/Wayland-Sessions abnehmen.
5. **Plan 07 live validieren**: Fleet-Alerts und Predictive-Maintenance gegen echte Runtime-Events provozieren und Webhook-/UI-Reaktion pruefen.
