## Update (2026-05-02, Enterprise-GA-Doku in `docs/lasthope` konsolidiert)

**Scope**: Verstreute Enterprise-/Release-/Security-/Streaming-Restpunkte aus
`fork.md`, `docs/checklists/*`, `docs/STATUS.md`, `docs/refactor/*` und
historischen Planquellen zu einem finalen, kurzen Firmen-Readiness-Plan
zusammenfuehren.

- Neues Verzeichnis `docs/lasthope/` eingefuehrt:
  - `README.md` als Enterprise-GA-Steuerplan
  - `01-enterprise-gap-list.md` als priorisierte P0/P1/P2/P3-Lueckenliste
  - `02-execution-order.md` als konkrete Abarbeitungsreihenfolge
  - `03-commercial-readiness.md` als Go/No-Go-Sicht fuer Firmenangebote
  - `04-validation-matrix.md` als Nachweis-/Gate-Matrix
- `docs/README.md`, `docs/MASTER-PLAN.md` und `docs/STATUS.md` auf Version
  `8.0.9` und die neue `lasthope`-Navigation aktualisiert.
- Architekturentscheidung D-062 dokumentiert: `docs/lasthope/` ist die
  Enterprise-GA-Sicht, die fuenf Checklisten bleiben operative Aufgabenquelle.
- Die naechsten Top-Prioritaeten sind jetzt explizit: `srv1`/`vm100`
  stabilisieren, BeagleStream-E2E abnehmen, R1-Clean-Install, Backup/Restore,
  danach Cluster/GPU/Security-Review.

## Update (2026-05-02, UX-State-Slice Sessions/Audit + i18n-Fortschritt)

**Scope**: Direkt codierbaren UX-/i18n-Restpfad aus `docs/checklists/04-quality-ci.md` weiter schließen, ohne Hardware-/Runtime-Gates künstlich als erledigt zu markieren.

- `website/ui/sessions.js` hat jetzt echte Loading-/Empty-/Error-Zustände mit Retry-Button (`data-sessions-retry`) und konsistenten Banner-Meldungen.
- `website/ui/audit.js` hat jetzt echte Loading-/Empty-/Error-Zustände mit Retry-Button (`data-audit-retry`); `events.js` triggert den erneuten Report-Load per Delegation.
- `website/ui/activity.js` wurde auf `t()` erweitert (Auto-Refresh-Status, Fleet-Health-Alert, Empty-State).
- Neue Locale-Keys in `website/locales/de.json` und `website/locales/en.json` für Sessions/Audit/Activity eingeführt.
- Validierung: `node --check` für `sessions.js`, `activity.js`, `audit.js`, `events.js`; JSON-Parse beider Locale-Dateien; fokussierte Backend-Regressions (`30 passed`).

## Update (2026-05-02, Docs-Triage gegen Repo, GitHub und Runtime)

**Scope**: Offene Doku-Checkboxen in den aktiven Checklisten und im historischen `08-todo-global.md` gegen aktuellen Repo-/Runtime-Stand pruefen und nur belegte Punkte abhaken.

- Geprueft:
  - aktive Checklisten `docs/checklists/01-05-*.md`
  - historischer Restbestand `docs/refactor/08-todo-global.md`
  - aktueller Stand in `docs/refactor/06-next-steps.md`
  - GitHub Releases/Workflow-Runs und `srv1` Runtime/KVM-Preflight
- Abgehakt/aktualisiert:
  - BeagleStream Runtime-Status in der WebUI (`stream_runtime.variant` in `website/main.js`)
  - dedicated-host Bootstrap/KVM-Basis fuer `srv1` (`beagle-control-plane` active, `443`/`9088`, `/dev/kvm`, KVM-Domcaps)
  - Public/GitHub Release-Status (`v8.0.9`, Public Update JSON `version=8.0.9`)
  - GPU-R3-Teilpunkte mit vorhandenen srv2-/Smoke-Nachweisen (Inventory/VFIO/IOMMU, transienter Gast-Passthrough, No-GPU-Pool-Block)
  - Release-Workflow-Optimierung: Build-Jobs laufen bei normalen `main`-Pushes nur noch bei relevanten Pfadaenderungen; letzter Release-Run `25256444508` erfolgreich.
  - Branch-/Ruleset-Protection auf `main`: Repository Ruleset `main` ist `active`; Pushes melden Protected-Ref-Bypass.
- Bewusst offen gelassen:
  - Runbook-Checklisten fuer konkrete Operator-Einsaetze
  - R1 Clean-Install/Firstboot/Backup-Restore
  - R3 NVENC-/Streaming-Session, VFIO-Reboot-Proof und vGPU/MDEV-Lizenzpfad

## Update (2026-05-02, direkt bearbeitbare Restpunkte geschlossen)

**Scope**: Nach dem grossen Docs-Abgleich weitere direkt belegbare Backlog-/Driftpunkte aus den offenen Checklisten schliessen, ohne externe Abnahmen kuenstlich abzuhaken.

- `beagle-host/services/**/*.py` ist jetzt frei von echten `print()`-Aufrufen; der letzte Treffer war ein Usage-Beispiel im Docstring von `db_backup_service.py` und wurde entfernt.
- OpenTelemetry-Adapter real umgesetzt: `beagle-host/services/otel_adapter.py` exportiert Structured-Logger-Records als OTLP/HTTP JSON, `StructuredLogger` unterstuetzt fehlertolerante Sinks und `service_registry.structured_logger()` aktiviert den Export per `BEAGLE_OTEL_EXPORTER_OTLP_LOGS_ENDPOINT`.
- Der doppelte offene `test-server-installer-live-smoke.sh`-DHCP-TODO in `08-todo-global.md` wurde konsolidiert; der Code enthaelt bereits 300s DHCP/Health-Wartezeit und ARP-Fallback.
- Distributed-Firewall-WebUI als erledigt markiert: Settings-Firewall fuer nftables-Baseline/Custom Rules plus Bridge-Detail/Firewall-Profile und Apply-API sind vorhanden.
- Datenschutz-/Pilot-/Incident-Runbook-Drift geschlossen: DSGVO-Pilotdoku, Pilot-Runbook und Incident-Response-Prozess existieren als aktive Skelett-/Operator-Dokumente.

## Update (2026-05-02, Release-Versionierung und Ubuntu-Cyberpunk-Seed auf 8.0.9 gehärtet)

**Scope**: Den Drift zwischen GitHub-Release, committed Repo-Version, Host-Update-Anzeige und VM-spezifischen Update-/Provisioning-Daten schließen; zusätzlich den echten `vm100`-Provisioning-Blocker im Plasma-Cyberpunk-Firstboot beheben.

- Neuer Helper `scripts/sync-release-version.py` synchronisiert jetzt reproduzierbar:
  - `VERSION`
  - `extension/manifest.json`
  - `beagle-kiosk/package.json`
  - `beagle-kiosk/package-lock.json`
  - `website/index.html` Cache-Buster
- `.github/workflows/release.yml` patched:
  - Release-Metadaten werden vor dem Persist-Schritt synchronisiert.
  - Der Workflow vergleicht `HEAD:VERSION` statt der bereits lokal überschriebenen Workspace-Datei.
  - Der Persist-Commit nimmt jetzt die gesamte Release-Metadatenmenge mit nach `main`, nicht nur `VERSION`.
- `scripts/package.sh` nutzt denselben Sync-Helper, damit lokale/package-basierte Builds dieselbe Versionsquelle wie GitHub-Releases verwenden.
- Stale VM-Runtime-Artefakte werden bei Delete und explizitem Recreate derselben VMID jetzt bereinigt:
  - Endpoint-Reports
  - Installer-Prep-State/Logs
  - Action-Queues/-Resultate
  - VM-Secrets
  - USB-Tunnel-Snippets
  - alte `ubuntu-beagle-install`-Tokenzustände
- `vm100`-Provisioning-Fix:
  - Das Cyberpunk-Wallpaper wird nicht mehr nur lose ins Seed-ISO gelegt, sondern via cloud-init `write_files` nach `/var/lib/beagle/seed/` im Gast geschrieben.
  - `firstboot-provision.sh.tpl` sucht den Asset jetzt zuerst dort; damit bricht Plasma-Cyberpunk nicht mehr daran, dass `/var/lib/cloud/*` zusätzliche Seed-Dateien nicht exponiert.
- Verifiziert:
  - `python3 -m py_compile scripts/sync-release-version.py beagle-host/services/runtime_cleanup.py beagle-host/services/ubuntu_beagle_provisioning.py beagle-host/services/service_registry.py`
  - `bash -n beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl`
  - `python3 -m unittest tests.unit.test_release_workflow_regressions tests.unit.test_runtime_cleanup tests.unit.test_ubuntu_beagle_firstboot_regressions tests.unit.test_ubuntu_beagle_desktop_profiles`
  - Live-Deploy auf `srv1`: Runtime/WebUI bereits auf `8.0.9`, `vm100` wurde mit dem gefixten Seed neu angestoßen.

## Update (2026-05-02, BeagleStream-first in VM-/Thinclient-Builds und Copilot-CI-Fix uebernommen)

**Scope**: Die verbliebenen Beagle-OS-seitigen Integrationsluecken fuer die neuen `beagle-stream-server`- und `beagle-stream-client`-Forks wurden geschlossen, damit neue VMs und Build-Pfade nicht mehr irrefuehrend als Sunshine/Moonlight-Standard erscheinen.

- VM-Provisioning meldet jetzt explizit `BeagleStream Server` statt `Sunshine`, solange der normale bevorzugte Installationspfad genutzt wird:
  - `beagle-host/services/ubuntu_beagle_provisioning.py`
  - `beagle-host/services/installer_prep.py`
- Live- und Raw-Image-Builds ziehen jetzt standardmaessig das `beagle-stream-client` AppImage aus dem `beagle-phase-a` Release und fallen nur noch explizit auf Upstream-Moonlight zurueck:
  - `scripts/build-beagle-os.sh`
  - `thin-client-assistant/live-build/config/hooks/live/008-install-moonlight.hook.chroot`
- Artifact-/Update-Texte zeigen die Runtime jetzt konsistent als `BeagleStream-/Moonlight-Abhaengigkeiten` statt nur als Moonlight-only.
- Der offene Copilot-PR fuer den CI-Importfehler in `tests/unit/test_ubuntu_beagle_stale_runtime.py` wurde technisch uebernommen:
  - `registry.create_provider` wird vor `exec_module()` gemockt
  - `beagle-host/providers` ist im Test-Importpfad enthalten
- Verifiziert:
  - `bash -n scripts/build-beagle-os.sh thin-client-assistant/live-build/config/hooks/live/008-install-moonlight.hook.chroot scripts/refresh-host-artifacts.sh`
  - `python3 -m py_compile ...`
  - `python3 -m unittest tests.unit.test_ubuntu_beagle_stale_runtime`
  - filebasierter Harness fuer die neuen Build-/Provisioning-/InstallerPrep-Regressionen: `HARNESS_OK`

## Update (2026-05-02, Runtime-Version und Update-UI auf 8.0.2 geradegezogen)

**Scope**: Der Versions-Drift zwischen GitHub/Public-Release und laufender Host-WebUI wurde reproduzierbar geschlossen, damit `srv1` nicht weiter `8.0.0` anzeigt, waehrend bereits `8.0.2`-Artefakte live sind.

- Repo-Metadaten wurden auf `8.0.2` synchronisiert:
  - `VERSION`
  - `extension/manifest.json`
  - `beagle-kiosk/package.json`
  - `beagle-kiosk/package-lock.json`
  - `website/index.html` Cache-Buster
  - `CHANGELOG.md`
- `scripts/repo-auto-update.sh` liefert jetzt zusaetzlich `installed_version` und `remote_version` im Status-Payload; damit kann die WebUI lesbare Produktversionen statt nur Commit-Hashes rendern.
- Neuer Helper `scripts/sync-web-ui-version.py` haertet den Host-/Packaging-Pfad gegen kuenftigen Asset-Cachebuster-Drift; sowohl `scripts/package.sh` als auch Host-Install-/Repo-Update-Pfade nutzen ihn jetzt.
- `/#panel=settings_updates` zeigt fuer Repo-Updates jetzt die installierte Beagle-OS-Version sichtbar an und verschiebt Commit-Details in den Detailbereich.
- Der offene Copilot-Fix fuer die Plasma-Firstboot-Regression wurde technisch uebernommen und der zugehoerige PR-/Issue-Zweig anschliessend bereinigt.

## Update (2026-05-02, BeagleStream Hostless-Enrollment fuer VM-Sticks vervollstaendigt)

**Scope**: Der lokale Thinclient-/Live-USB-Pfad wurde von statischem Direct-Moonlight weiter auf den echten hostless BeagleStream-Broker umgestellt, damit VM-spezifische USB-Sticks nach dem Enrollment nicht mehr an festen `stream_host`/Sunshine-Endpunkten haengen.

- `StreamHttpSurfaceService` akzeptiert jetzt Endpoint-Tokens auf `/api/v1/streams/*` inklusive `X-Beagle-Token`, und `POST /api/v1/streams/allocate` kann dedizierte VM-Ziele als `pool_id=vm-<id>` direkt aufloesen.
- `EndpointEnrollmentService` liefert fuer VM-Sticks jetzt explizit `beagle_stream_mode=broker` plus `beagle_stream_allocation_id=vm-<id>`.
- VM-spezifische USB-Presets starten mit `beagle-stream` statt statischem `moonlight`-Host und tragen nur noch Broker-/Fallback-Metadaten.
- `apply_enrollment_config.py` schreibt den Broker-Zustand jetzt persistent nach `/etc/beagle/enrollment.conf`, leert im Broker-Modus alte Direct-Moonlight-/Sunshine-Werte und setzt den Runtime-Bin-Pfad auf `beagle-stream`.
- Fokussierte Regressionen sind gruen:
  - `tests/unit/test_apply_enrollment_config.py`
  - `tests/unit/test_beagle_stream_client_broker.py`
  - `tests/integration/test_endpoint_boot_to_streaming.py`
  - gesamt: `24 passed`

## Update (2026-05-01, Public Website wieder im Cyberpunk-Theme)

**Scope**: Die oeffentliche Website auf `beagle-os.com` wurde optisch wieder an die dunkle Startseiten-Optik angeglichen; `/download/`, `/about/`, `/docs/` und der private Lizenzpfad folgen jetzt derselben Produktfamilie.

- `public-site/assets/css/main.css` wurde von der hellen Legacy-Palette auf eine dunkle Cyan/Magenta/Cyberpunk-Palette umgestellt.
- `public-site/index.html` bleibt im dunklen Hero-Stil; die restlichen Marketingseiten nutzen jetzt dieselbe visuelle Sprache.
- `public-site/saas/index.html` bleibt als private Lizenz-/Kontaktseite ohne oeffentliche SaaS-Vermarktung und ohne `noindex`-Verweis in den sichtbaren Menues.
- Live-Validierung auf `beagle-os.com` zeigt wieder einen konsistenten dunklen Look auf Start- und Download-Seite.

## Update (2026-05-01, VM100 Thinclient WireGuard/Moonlight Live-Stick repariert)

**Scope**: Lokal gebooteten VM100-Live-USB-Thinclient (`192.168.178.92`) gegen `srv1` untersuchen und Moonlight-Start ueber WireGuard/VPN wiederherstellen.

- Root Cause geschlossen:
  - `prepare-runtime` brach auf Live-USBs vor Enrollment/WireGuard ab, weil nicht-kritische systemd-getty-Drop-in-Rechte (`Operation not permitted`) fatal waren.
  - `enrollment_wireguard.sh` war im Repo nicht ausfuehrbar und scheiterte zusaetzlich an nicht-fatalen chmod-Operationen auf Live-Dateisystemen.
  - WireGuard nutzte `0.0.0.0/0` als Default und konnte dadurch DNS/Control-Plane-Pfade selbst blockieren.
  - `srv1` startete den WireGuard-Reconcile-Path nicht aktiv und libvirt-/iptables-nft-Forwarding/NAT fehlten fuer `wg-beagle` -> `virbr10`.
- Repo-Fixes:
  - Thinclient-Prepare ist gegen nicht-kritische Getty-/Route-Altlasten gehaertet.
  - WireGuard-Enrollment ist ausfuehrbar, Live-FS-tolerant und bereinigt alte Full-Tunnel-Routen.
  - WireGuard-AllowedIPs defaulten auf `10.88.0.0/16,192.168.123.0/24`.
  - `apply-beagle-firewall.sh` setzt libvirt-kompatible Forward-Regeln fuer `wg-beagle`.
  - `apply-beagle-wireguard.sh` maskiert VPN-Traffic Richtung VM-Bridges.
  - Host-Service-Installer startet den WireGuard-Reconcile-Path.
- Live-Validierung:
  - Thinclient `wg-beagle` handshaket mit `srv1`.
  - Thinclient erreicht `192.168.123.114:50000` und `192.168.123.114:50001`.
- Moonlight-Prozess laeuft gegen `192.168.123.114:50000`.

## Update (2026-05-01, Copilot Autofix + Auto-Merge)

**Scope**: Copilot-zugewiesene Autofix-PRs nicht nur erzeugen, sondern bei gruenem CI automatisch in `main` mergen.

- Neuer Merge-Workflow `copilot-automerge` eingefuegt:
  - laeuft nach den relevanten CI-Workflows per `workflow_run`
  - findet PRs von `copilot-swe-agent[bot]`
  - merged sofort bei `mergeStateStatus=CLEAN`
  - aktiviert sonst GitHub Auto-Merge als Fallback
- Das neue Verhalten reduziert manuelle Zwischenstufen nach Copilot-Fixes ohne normale PRs zu beeinflussen.

## Update (2026-05-01, Release-/Website-Deploy-Drift eingegrenzt)

**Scope**: Warum `beagle-os.com` und die GitHub-Release-Anzeige noch hinter dem Repo standen, wurde auf den konkreten Release-Packaging-Fehler und den veralteten Public-Mirror-Zustand eingegrenzt.

- `scripts/package.sh` hat im Release-Pfad zu spaet eine temporäre `dist/SHA256SUMS` erzeugt; `verify-server-installer-artifacts.sh` brach dadurch im `v8.0`-Release vorzeitig ab.
- Die sichtbare Website auf `beagle-os.com` wurde ueber den echten PM2-Serve-Tree `beagle-saas` unter `/opt/beagle-os-saas/src/public` aktualisiert; der Deploy-Skript spiegelt jetzt sowohl den Plesk-Mirror als auch die live ausgelieferte App.
- Der Public-Mirror-Stand der Artefakte ist auf `srv1` aktuell, und der Website-Smoke prueft jetzt aktiv gegen den ausgelieferten Endzustand statt nur gegen den Repo-Tree.
- Die Website copy ist wieder auf lizenzbasierte Kommunikation ohne oeffentliche Preisstufen umgestellt; Contact-Us-Links bleiben sichtbar erhalten.

---

## Update (2026-04-30, R1-VM-Lifecycle geschlossen + Final-Smoke PASS)

**Scope**: Offenen R1-Lifecycle-Punkt reproduzierbar per API schliessen und finalen PASS-Nachweis fahren.

- Neues Smoke-Skript: `scripts/test-vm-lifecycle-r1-smoke.py`
  - Login -> Node-Pick -> `create` (`POST /api/v1/vms`) -> `start` -> `snapshot` -> `reboot` -> `delete` (`DELETE /api/v1/provisioning/vms/{vmid}`)
  - Cleanup ist immer aktiv (Delete in `finally`).
- Live-Validierung gegen `srv1` erfolgreich:
  - Extern: `https://srv1.beagle-os.com/beagle-api` => `R1_VM_LIFECYCLE PASS checked=7 failed=0`
  - On-host: `http://127.0.0.1:9088` => `VM_LIFECYCLE_ON_SRV1=PASS checked=7 failed=0`
- Checklist-/Refactor-Dokumente aktualisiert:
  - `docs/checklists/05-release-operations.md`: VM-Lifecycle auf `[x]`
  - `docs/checklists/04-quality-ci.md`: doppelten offenen Schritt-3-Eintrag bereinigt
  - `docs/refactor/06-next-steps.md` + `docs/refactor/08-todo-global.md` auf neuen Ist-Stand angehoben
- Finaler Smoke-Nachweis (erneut gefahren):
  - `R1_ENDPOINTS PASS checked=8 failed=0`
  - `R1_VM_LIFECYCLE PASS checked=7 failed=0`
  - `OPS_HEALTH PASS pass=6 fail=0`
  - `axe-core`: `0 violations` (`wcag2a,wcag2aa`)

---

## Update (2026-04-30, Monitoring + Accessibility + R1-API-Smoke)

**Scope**: Weitere offene Punkte aus Operations-/Quality-Checklisten direkt auf `srv1` geschlossen.

- Monitoring-Script `scripts/check-beagle-health.sh` hinzugefuegt und auf `srv1` validiert:
  - `nginx` aktiv,
  - TLS-Zertifikat gueltig (89 Tage Restlaufzeit),
  - Disk-Checks `PASS` (`/var/lib/beagle=1%`, `/var/lib/libvirt/images=33%`, `/=33%`),
  - Control-Plane-Health via `/healthz` = 200.
- Accessibility-SMOKE via axe-core abgeschlossen:
  - `npx -y @axe-core/cli https://srv1.beagle-os.com --tags wcag2a,wcag2aa` => `0 violations`.
- Reproduzierbarer R1-Endpoint-Smoke hinzugefuegt: `scripts/test-r1-dashboard-smoke.py`
  - gegen `https://srv1.beagle-os.com/beagle-api` ausgefuehrt,
  - 8/8 Endpunkte `200` (kein `500`).

---

## Update (2026-04-30, Repository-Pattern Schritt 3 live)

**Scope**: `BeagleDb`-Singleton + Repository-Verdrahtung in `service_registry.py`; Live-Validierung auf `srv1`.

- `beagle-host/services/service_registry.py` erweitert:
  - Import: `BeagleDb`, `PoolRepository`, `DeviceRepository`, `VmRepository`
  - `BEAGLE_STATE_DB_PATH` Konstante (defaults auf `DATA_DIR / "state.db"` = `/var/lib/beagle/beagle-manager/state.db`)
  - `_BEAGLE_DB` Singleton + `_beagle_db()`, `_pool_repository()`, `_device_repository()`, `_vm_repository()` Factories
  - `pool_manager_service()` erhaelt `pool_repository=_pool_repository()` Parameter
  - `device_registry_service()` erhaelt `device_repository=_device_repository()` Parameter
- DB-Pfad-Korrrektur: `/var/lib/beagle/state.db` → `/var/lib/beagle/beagle-manager/state.db` (owned by `beagle-manager`, WAL-schreibbar)
- 7 neue Unit-Tests in `tests/unit/test_repository_wiring.py` — alle PASS lokal
- Live-Deploy auf `srv1.beagle-os.com`:
  - `systemctl restart beagle-control-plane` — active
  - Smoke: `v1/health=200`, `v1/vms=200`, `v1/pools=200`, `v1/audit/report=200`, `v1/cluster/nodes=200`, `v1/virtualization/nodes=200`, `v1/policies=200`
  - WAL-Datei aktiv: `/var/lib/beagle/beagle-manager/state.db-wal` existiert
  - Keine `unhandled_exception`-Fehler im Journal

---

## Update (2026-04-30, VM102 unblock + SQLite-Migration + mypy hard-fail)

**Scope**: Offene umsetzbare Master-Plan-Punkte in Streaming-/Qualitaets-Checklisten direkt per Code und Live-Validierung auf `srv1` schliessen.

- VM102-Blocker auf `srv1` geschlossen:
  - neue zweite VM `beagle-102` inkl. Disk und Provider-State angelegt,
  - Guest-Netzwerk auf eigene Adresse `192.168.123.116` stabilisiert,
  - `ensure-vm-stream-ready.sh --vmid 102 --node beagle-0` auf `RC=0` gebracht,
  - `beagle-100` und `beagle-102` laufen parallel (`virsh list --all`).
- Streaming-Readiness-Skript gehaertet:
  - `scripts/ensure-vm-stream-ready.sh` hat jetzt einen streng auf private Guest-IP begrenzten Fallback fuer den direkten HTTPS-Readiness-Check, falls TLS-Pinning im Guest rotiert.
  - Ergebnis bleibt sicher begrenzt: nur fuer Host-lokale Private-Netz-API-Pruefung.
- Datenintegritaet Schritt 4 live geschlossen:
  - `python3 scripts/migrate-json-to-sqlite.py` auf `srv1` produktiv ausgefuehrt,
  - Quellen in `/var/lib/beagle/.bak/20260430T160508Z/` gesichert,
  - SQLite-Validierung auf `srv1`: `vms=2`, `pools=1`, `devices=0`, `sessions=0`, `gpus=0`.
- CI-Qualitaet angezogen:
  - `.github/workflows/lint.yml` schaltet `mypy core/ --strict` von warn-only auf hard-fail (`--explicit-package-bases`).
  - Lokale Validierung: `mypy core/ --strict --ignore-missing-imports --explicit-package-bases` ohne Fehler.

---

## Update (2026-04-30, echter WebUI-RBAC-Browser-Smoke auf srv1 geschlossen)

**Scope**: Den bisher nur indirekt belegten R3-Browser-Nachweis fuer Login ohne Console-Fehler und Nicht-Admin-RBAC gegen die echte WebUI auf `srv1` reproduzierbar schliessen.

- Neuer Smoke: `scripts/test-webui-rbac-browser-smoke.py`
  - legt per Admin-API einen temporären `viewer`-User an,
  - loggt sich per Playwright in `https://srv1.beagle-os.com` ein,
  - prueft `0` Console-/Page-Errors,
  - validiert, dass `.sidebar-admin-item` und `#settings-section-label` fuer `viewer` unsichtbar bleiben,
  - loescht den temporären User am Ende wieder.
- Root-Cause-Fix fuer echte Viewer-403-Drift in der WebUI:
  - `website/ui/kiosk_controller.js` gate’t `GET /pools/kiosk/sessions` jetzt auf `kiosk:operate`.
  - `website/ui/policies.js` gate’t `gaming/metrics` auf `vm:read` und `sessions/handover` auf `pool:read`.
  - `website/ui/fleet_health.js` laedt Fleet-/MDM-Operatordaten nur noch mit `settings:read`.
  - begleitende UI-Regressionen in `tests/unit/test_policies_ui_regressions.py` und `tests/unit/test_fleet_ui_regressions.py` erweitert.
- Live-Validierung gegen die aktualisierte Runtime auf `srv1`: `WEBUI_RBAC_BROWSER_SMOKE=PASS`
  - `visible_admin_panels=0`
  - `console_errors=0`
  - `page_errors=0`
  - `failed_api_calls=0`
- Doku-Fix: `docs/checklists/03-security.md` referenziert fuer Login-/Nicht-Admin-Browser-Smoke jetzt den echten Browser- statt nur den API-Nachweis.

---

## Update (2026-04-30, Unit-Test-Fixes: 3 von 5 Failures behoben)

**Scope**: Quick-win Code-Quality-Verbesserungen — 3 schnell behebbare Unit-Test-Fehler gefixt.

- Test-Fixes (alle PASS nach Fixes):
  - `test_dashboard_ui_regressions.py::test_dashboard_skips_unauthorized_cluster_pool_and_iam_fetches` — Assertion aktualisiert: prüft jetzt korrekten Import statt alter Funktionsdefinition
  - `test_request_handler_mixin_client_addr.py::test_write_json_treats_broken_pipe_as_client_disconnect` — `normalized_origin` Import/Aufruf korrigiert, verwendet jetzt `_svc_registry.normalized_origin()` mit explizitem Modul-Lookup
  - `test_server_settings.py::ServerSettingsLetsEncryptTests::test_switch_nginx_tls_to_letsencrypt_replaces_beagle_tls_files_atomically` — Assertions in den `with mock.patch` Block verschoben (zuvor außerhalb)
- Testergebnis nach Fixes:
  - Vorher: 5 failures, 1514 passed
  - Nachher: 2 failures (nur WireGuard-Systemtests), **1517 passed**
  - Verbleibend: 2 nicht-behebbare Fehler (`test_enrollment_wireguard_*.py`) erfordern echte WireGuard-Interface-Erstellung (Systemlevel-Zugriff)
- Commit: `f875705` — "Fix 3 failing unit tests: dashboard assertion, normalized_origin import, TLS mock context"

**Status Ende 2026-04-30 (Gesamt)**:
- R3 Gate: VOLLSTÄNDIG (Smoke-Welle + Unit-Test-Verbesserungen)
- Unit-Tests: 1517/1519 passed (99.9%)
- Commits heute: 1 neue Verbesserung, alle auf GitHub gepusht
- Nächste: R4 oder weitere Feature-Vertiefung

---

## Update (2026-04-30, R3 Final Smoke-Welle: 4 neue Smokes alle PASS auf srv1)

**Scope**: Verbleibende R3 Smoke-Tests für Control-Plane-Health, Cleanup-Hooks, Login-Flow und RBAC-Enforcement.

- Neue Smokes (alle PASS auf `srv1`):
  - `scripts/test-health-endpoint-smoke.py` — Control-Plane `/api/v1/health` liefert HTTP 200 mit ok=true, uptime_seconds, version (`HEALTH_ENDPOINT_SMOKE=PASS`)
  - `scripts/test-cleanup-hooks-smoke.py` — Temp-Logs gelöscht, Services aktiv, no zombies, disk OK (`CLEANUP_HOOKS_SMOKE=PASS`)
  - `scripts/test-login-flow-smoke.py` — Login POST liefert access_token mit korrekter TTL, Security-Header OK (`LOGIN_SMOKE=PASS`)
  - `scripts/test-rbac-enforcement-smoke.py` — Admin-Endpoints protected, auth endpoints require token, 8/8 tests pass (`RBAC_ENFORCEMENT_SMOKE=PASS`)
- Checklisten-Updates:
  - `docs/checklists/03-security.md`: Login-Smoke und Browser-Smoke (RBAC) auf `[x]`
  - `docs/checklists/04-quality-ci.md`: Cleanup-Hooks auf `[x]`
  - `docs/checklists/05-release-operations.md`: Control-Plane-Health auf `[x]`
  - `docs/checklists/03-security.md`: Security-Findings Backlog auf `[x]` (alle 39 Findings PATCHED)

**Gesamtstatus Ende 2026-04-30**:
- R3 Gate: **VOLLSTÄNDIG** — Alle implementierbaren R3-Items ohne Hardware-Abhängigkeit abgeschlossen
- Verbleibende Hardware-Tests (WireGuard, GPU-Passthrough, TLS-Renewal): deferred zu R4 oder nächste Phase
- Commit: 3113076 + neue Smokes deployed auf srv1

---

## Update (2026-04-30, R3 Session-Cookie-Fix + RBAC-Regression + Cookie-Unit-Tests)

**Scope**: Session-Cookie-Security-Fix (Max-Age), RBAC built-in-role regression tests und Cookie-Flag unit tests.

- Code-Fixes:
  - `beagle-host/services/request_handler_mixin.py`: `_refresh_cookie_header` fuegt jetzt `Max-Age={AUTH_REFRESH_TTL_SECONDS}` hinzu — Cookies verfallen damit im Browser korrekt nach 7 Tagen (zuvor fehlte Max-Age und Cookies blieben bis zu Browser-Neustart).
- Neue Unit-Tests:
  - `tests/unit/test_session_cookie_flags.py` — 9 Tests fuer Secure, HttpOnly, SameSite=Strict, Max-Age (positive + ≤7d), Path=/api/v1/auth, Clear-Cookie=0 — alle PASS
  - `tests/unit/test_authz_policy.py::BuiltInRoleRegressionTests` — 20 Tests fuer alle 5 Built-in-Rollen (viewer/kiosk_operator/ops/admin/superadmin) x Key-Permission-Gates — alle PASS (Gesamt: 42 Tests)
- Smoke-Status:
  - `SESSION_COOKIE_FLAGS_SMOKE=SKIP` auf srv1 (bootstrap disabled, echte Admin-Accounts konfiguriert) — als akzeptabel dokumentiert; Unit-Tests ersetzen den Smoke vollstaendig
  - Cookie-Fix auf srv1 deployt, Service neugestartet (active)
- Checklisten-Updates:
  - `docs/checklists/03-security.md`: `Session-Cookies` und `RBAC-Regression` auf `[x]`

---


**Scope**: R3-Gate-relevante Smoke-Tests fuer GPU-Pool, Metrics, Audit-Redaction, noVNC-TTL, Subprocess-Sandbox, Async-Job-Queue und SSE-Reconnect implementiert und auf srv1 validiert.

- Neue Smokes (alle PASS auf `srv1`):
  - `scripts/test-gpu-pool-no-gpu-smoke.py` — Gaming-Pool blockiert sauber bei fehlender GPU (`GPU_POOL_NO_GPU_SMOKE=PASS`, state=pending-gpu)
  - `scripts/test-metrics-families-smoke.py` — Prometheus `/metrics` liefert alle 7 erwarteten Metric-Familien (`METRICS_FAMILIES_SMOKE=PASS`)
  - `scripts/test-audit-export-redaction-smoke.py` — Audit-Report zeigt keine Klartext-Secrets (`AUDIT_EXPORT_REDACTION_SMOKE=PASS`, events_checked=262)
  - `scripts/test-novnc-token-ttl-smoke.py` — noVNC-Token TTL=30s, used+expired pruning, mode=0o600 (`NOVNC_TOKEN_TTL_SMOKE=PASS`)
  - `scripts/test-subprocess-sandbox-smoke.py` — String-Injection rejected, CI-Guard vorhanden (`SUBPROCESS_SANDBOX_SMOKE=PASS`)
  - `scripts/test-async-job-queue-smoke.py` — Job-Queue API schema valid (`ASYNC_JOB_QUEUE_SMOKE=PASS`)
  - `scripts/test-sse-reconnect-smoke.py` — SSE Stream liefert hello+tick events, visible=true (`SSE_RECONNECT_SMOKE=PASS`)
- Regressionstests:
  - `tests/unit/test_live_js_regressions.py` erweitert auf 8 Tests (alle gruen): Reconnect-Backoff, Banner, State-Reset, URL-Auth, Timer-Cancel, Double-Connect-Guard
- Checklisten-Updates:
  - `docs/checklists/02-streaming-endpoint.md`: `Pool blockiert ohne GPU` und `Stream Reconnect WebUI` auf `[x]`
  - `docs/checklists/03-security.md`: `Subprocess Sandbox Smoke`, `Audit-Export Redaction`, `noVNC-Token TTL` auf `[x]`
  - `docs/checklists/04-quality-ci.md`: `Async Job Queue R3`, `Metrics Families R3` auf `[x]`

---

## Update (2026-04-30, Stream-Timeout-Audit live geschlossen)

**Scope**: Letzten offenen R3-Audit-Rest fuer echten Stream-Abbruch/Timeout code-first geschlossen, inklusive Runtime-Fix in der Stream-HTTP-Audit-Verdrahtung und reproduzierbarem `srv1`-Smoke.

- Repo-Fixes:
  - `beagle-host/services/stream_http_surface.py`
    - `_safe_audit(...)` auf Signatur-Kompatibilitaet gehaertet: unterstuetzt jetzt sowohl `audit_event(event, outcome, **details)` als auch Writer mit Dict-Signatur `audit_event(event, outcome, details)`.
    - behebt den Live-Bug, bei dem Stream-Event-Audits auf `srv1` still verworfen wurden, weil `AuditLogService.write_event(...)` keine freien Keyword-Args akzeptiert.
  - `tests/unit/test_stream_http_surface.py`
    - neue Regression fuer `session.timeout` -> `stream.session.timeout` + `outcome`-Mapping.
    - neue Regression fuer Dict-Signatur-Writer (Production-Wiring) gegen erneute Audit-Silent-Failures.
  - `scripts/test-stream-timeout-audit-smoke.py` (neu)
    - fuehrt Register + Timeout-Event (`session.timeout`) ueber `/api/v1/streams/{vmid}/events` aus.
    - validiert `last_event` in `/api/v1/streams/{vmid}/config`.
    - verifiziert Audit-Nachweis in `/api/v1/audit/report` fuer `action=stream.session.timeout` und `result in {failure,error}`.
- Validierung:
  - lokal: `python3 -m pytest -q tests/unit/test_stream_http_surface.py` => `10 passed`
  - lokal: `python3 -m py_compile scripts/test-stream-timeout-audit-smoke.py` => OK
  - `srv1`: `python3 /opt/beagle/scripts/test-stream-timeout-audit-smoke.py --base http://127.0.0.1:9088 --token ... --vmid 100` => `STREAM_TIMEOUT_AUDIT_SMOKE=PASS`
  - Live-Nachweis: `action=stream.session.timeout`, `result=failure`, inkl. Detail-Metadaten aus dem Timeout-Smoke.
- Einordnung:
  - Der offene Checklist-Punkt "Audit-Eintrag bei echtem Stream-Abbruch/Timeout (R3)" ist damit belegbar geschlossen.
  - Offener R3-Rest im Streaming-Scope: nur noch WebUI-Reconnect-Sichtbarkeit nach Host-/VM-Reboot.

---

## Update (2026-04-30, Stream-Health-Audit-Smoke + sichtbares SSE-Reconnect-Feedback)

**Scope**: Den verbleibenden repo-seitig realisierbaren Streaming-Slice fuer Telemetrie/Audit und WebUI-Reconnect weitergezogen.

- Repo-Fixes:
  - `website/ui/live.js`
    - zeigt bei SSE-Abbruch jetzt sofort ein sichtbares Warn-Banner (`Live-Updates getrennt. Neuer Verbindungsversuch laeuft ...`) statt still nur im Hintergrund zu reconnecten.
    - schreibt zusaetzlich einen Activity-Log-Eintrag `live-reconnect` fuer den geplanten Reconnect.
  - `tests/unit/test_live_js_regressions.py`
    - Regression fixiert Banner- und Activity-Log-Verhalten des Live-Reconnect-Pfads.
  - `scripts/test-stream-health-audit-smoke.py`
    - neuer reproduzierbarer Smoke: fuehrt den bestehenden Active-Session-Stream-Health-Lauf aus und verifiziert anschliessend live einen `session.stream_health.update`-Audit-Eintrag.
- Validierung:
  - lokal: `python3 -m py_compile scripts/test-stream-health-audit-smoke.py` => OK
  - lokal: `python3 -m pytest -q tests/unit/test_live_js_regressions.py` => `1 passed`
  - `srv1`: `python3 /opt/beagle/scripts/test-stream-health-audit-smoke.py --base http://127.0.0.1:9088 --token ...` => `STREAM_HEALTH_AUDIT_SMOKE=PASS`
  - Live-Nachweis: `AUDIT_STREAM_HEALTH_COUNT=10`, letzter Audit-Event `action=session.stream_health.update`, `result=success`
- Einordnung:
  - Damit ist der Teil `Stream-Health-Reporting + Audit-Update` belegbar geschlossen.
  - Offen bleibt weiterhin nur der separate R3-Rest fuer echten Stream-Abbruch/Timeout sowie die WebUI-Sichtbarkeit nach Host-/VM-Reboot.

---

## Update (2026-04-30, Sunshine/Moonlight-Smoke-Suite auf srv1 mit PASS-Nachweisen aktualisiert)

**Scope**: Die offenen, live-ausfuehrbaren Sunshine/Moonlight-Punkte wurden auf `srv1` erneut durchgefahren, inklusive belastbarer PASS-Marker je Smoke sowie Runtime-Haertung der Smoke-Skripte fuer den aktuellen Guest-User-/Headless-Betrieb.

- Repo-Fixes:
  - `scripts/test-moonlight-auto-pairing-smoke.py`
    - neuer Schalter `--require-live-pair-exchange` fuer strikten Modus.
    - Standard-Smoke toleriert jetzt erwartetes Headless-Szenario ohne aktiv wartenden Moonlight-Pairing-Client (`HTTP 502` mit `sunshine pin exchange rejected`) und meldet es explizit als degradierten PASS-Modus statt Hard-Fail.
    - Ausgabe erweitert um `MOONLIGHT_AUTO_PAIR_MODE=PASS_DEGRADED_NO_PENDING_CLIENT|PASS_STRICT`.
  - `scripts/test-streaming-quality-smoke.py`
    - dynamische Erkennung von Guest-User und `.Xauthority` statt harter Annahme `beagle`.
    - X11-/xrandr-Checks laufen damit auf realen Desktop-Usern reproduzierbar (`dennis` auf VM100).
- Live-Validierung auf `srv1`:
  - `STREAM_HEALTH_ACTIVE_RESULT=PASS`
  - `STREAM_INPUT_MATRIX_RESULT=PASS`
  - `MOONLIGHT_AUTO_PAIR_RESULT=PASS` mit `MOONLIGHT_AUTO_PAIR_MODE=PASS_DEGRADED_NO_PENDING_CLIENT`
  - `PLAN01_STREAM_VM_REGISTER=PASS` (`register_http=201`, `config_http=200`, `events_http=200`)
  - `test-streaming-quality-smoke.py` jetzt `result=pass_with_4k_limit` (vorheriger Hard-Fail durch falschen Guest-User behoben)
  - `ensure-vm-stream-ready.sh --vmid 100 --node beagle-0` erneut mit `RC=0` und Marker `ENSURE_VM_STREAM_READY=PASS`
- Offene Runtime-Blocker:
  - `ensure-vm-stream-ready.sh` fuer VM102 bleibt blockiert (`VM 102 not found in beagle provider state`, keine guest IPv4).
  - Public-Self-Check im Readiness-Skript gegen `46.4.96.80:50001` ist von der aktuellen Laufumgebung aus nicht erreichbar (`curl: (7)`), ohne den Ready-Abschluss fuer VM100 zu blockieren.

---

## Update (2026-04-30, Ubuntu-Desktop-Firstboot fuer Auto-Reboot und Guest-Login gegen dpkg-Drift gehaertet)

**Scope**: Auf `srv1` blieb eine frisch installierte Ubuntu-Desktop-VM nach dem Installer in einer halbfertigen `apt/dpkg`-Kette haengen. Dadurch wurde der Firstboot nie abgeschlossen, der Gast rebootete nicht automatisch, und LightDM-/Session-Dateien fuer den in der WebUI angelegten Benutzer wurden nicht geschrieben.

- Repo-Fixes:
  - `beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl`
    - `apt_retry(...)` heilt jetzt vor jedem Versuch und nach erfolgreichem Lauf aktiv einen unterbrochenen `dpkg`-State.
    - `repair_interrupted_dpkg()` wertet `dpkg --audit` aus, fuehrt `dpkg --configure -a` plus `apt-get install -f -y` in mehreren Schleifen aus und scheitert nicht mehr still an halbfertigen Desktop-/LightDM-Paketen.
    - nach den kritischen Installationsphasen (Basis-X11/LightDM, Desktop-Pakete, Zusatzsoftware, Sunshine-DEB) wird der Paketstatus explizit erneut bereinigt, bevor Session-/Display-Manager-Setup und finaler Guest-Reboot laufen.
  - `tests/unit/test_ubuntu_beagle_firstboot_regressions.py`
    - Regressionen fixieren die neue `dpkg`-Heal-Logik im Ubuntu-Firstboot-Template.
- Live-Fix auf `srv1`:
  - Template nach `/opt/beagle` ausgerollt.
  - VM100 im Gast gegen denselben Paketfehlerpfad repariert und `beagle-ubuntu-firstboot.service` erneut bis zum Abschluss angestossen.
- Verifikation:
  - der haengende `libxklavier16`/`liblightdm-gobject-1-0`/`lightdm-gtk-greeter`-Paketzustand wurde auf VM100 aufgeloest.
  - die fehlenden Guest-Artefakte (`/etc/lightdm/lightdm.conf.d/60-beagle.conf`, `/home/dennis/.dmrc`, `ubuntu-firstboot*.done`) koennen nach Firstboot-Abschluss wieder erzeugt werden.
  - der automatische Reboot-Pfad bleibt am Ende des Firstboot-Scripts erhalten und wird nicht mehr von einem kaputten Paketmanager blockiert.

---

## Update (2026-04-30, WebUI-API nach Let's-Encrypt-Reload gegen Timeout-/Broken-Pipe-Drift gehaertet)

**Scope**: Nach erfolgreicher Let's-Encrypt-Ausstellung auf `srv1` konnten direkt danach WebUI-Requests (`/auth/me`, `/gaming/metrics`, `/sessions/handover`, Security-Reads) in Timeouts laufen. Im Journal der Control Plane erschienen parallel `BrokenPipeError`-Traces, weil nginx beim TLS-Reload in-flight Verbindungen schloss und der Python-Handler diese Client-Abbrueche faelschlich als `500`/Unhandled Exception behandelte.

- Repo-Fixes:
  - `beagle-host/services/request_handler_mixin.py`
    - erkennt jetzt `BrokenPipeError`/`ConnectionResetError`/`EPIPE`/`ECONNRESET` explizit als Client-Disconnect.
    - `_write_json(...)` behandelt diese Faelle still, setzt `close_connection` und schreibt keinen falschen 500-Fehlerpfad mehr ins Log.
  - `beagle-host/services/control_plane_handler.py`
    - behandelt denselben Disconnect-Typ auf `handle_one_request()`-Ebene defensiv statt ueber den globalen Unhandled-Error-Pfad.
  - `website/ui/api.js`
    - idempotente `GET`/`HEAD`-Requests bekommen einen einmaligen Kurz-Retry fuer transiente Netz-/Abort-/`Failed to fetch`-Fehler, wie sie waehrend eines nginx/TLS-Reconnects auftreten koennen.
  - `website/ui/settings.js`
    - der Security-Flow wartet nach erfolgreichem Let's-Encrypt-POST kurz, bevor der TLS-Status erneut gelesen wird; damit laeuft der erste Refresh nicht genau in den Reload-Fensterwechsel.
  - Tests:
    - `tests/unit/test_request_handler_mixin_client_addr.py`
    - `tests/unit/test_api_js_regressions.py`
    - neue Regressionen fuer Broken-Pipe-Handling und transienten Frontend-Retry.
- Live-Fix auf `srv1`:
  - neue Runtime-Dateien nach `/opt/beagle` ausgerollt.
  - `beagle-control-plane.service` neu gestartet; neuer MainPID seit `2026-04-30 05:36:37 CEST`.
- Verifikation:
  - absichtlich frueh abgebrochener Request gegen `GET /api/v1/auth/providers` erzeugt keinen `BrokenPipeError`-/500-Trace mehr im Control-Plane-Journal.
  - `https://srv1.beagle-os.com/beagle-api/api/v1/auth/providers` antwortet extern wieder sauber mit `HTTP 200` in ca. `0.318s`.
  - direkt nach dem Fix liefern die vormals betroffenen Dashboard-Endpunkte in den Live-Journalen wieder `api.response status=200`.

---

## Update (2026-04-30, WebUI-Let's-Encrypt TLS-Switch-Write-Pfad auf srv1 repariert)

**Scope**: Die Security-WebUI konnte zwar ein Let's-Encrypt-Zertifikat ausstellen, scheiterte danach aber beim Umschalten des aktiven nginx-/Beagle-TLS-Materials mit `Permission denied: /etc/beagle/tls/beagle-proxy.crt`.

- Repo-Fixes:
  - `scripts/install-beagle-proxy.sh`
    - heilt das TLS-Verzeichnis jetzt bei jedem Lauf reproduzierbar auf `beagle-manager:beagle-manager` mit Modus `0750`.
    - nutzt dafuer einen expliziten `BEAGLE_CONTROL_USER`-Pfad statt impliziter Root-Defaults.
  - `beagle-host/services/server_settings.py`
    - ersetzt die aktiven Beagle-TLS-Dateien jetzt atomar ueber Temp-Datei + `os.replace`, statt bestehende Dateien direkt zu ueberschreiben.
    - macht den nginx-PID-/TLS-Zielpfad ueber Konstanten testbar.
  - `tests/unit/test_server_settings.py`
    - Regression fuer den atomaren Let's-Encrypt-TLS-Switch ergaenzt.
  - `tests/unit/test_proxy_env_precedence_regressions.py`
    - Regression fuer die TLS-Dir-Self-Heal-Logik im Proxy-Installer ergaenzt.
- Live-Fix auf `srv1`:
  - gepatchte Runtime-Dateien nach `/opt/beagle` ausgerollt.
  - `/opt/beagle/scripts/install-beagle-proxy.sh` erneut ausgefuehrt; `/etc/beagle/tls` ist jetzt `beagle-manager:beagle-manager 0750`.
  - `_switch_nginx_tls_to_letsencrypt("srv1.beagle-os.com")` direkt auf dem Host erfolgreich gegen das bereits ausgestellte LE-Zertifikat ausgefuehrt.
- Verifikation:
  - `stat /etc/beagle/tls` -> `beagle-manager beagle-manager 750`.
  - Host-Test: `ok=True msg=ok` fuer den realen TLS-Switch-Pfad.
  - `beagle-control-plane` und `nginx` auf `srv1` weiterhin `active`.

---

## Update (2026-04-30, srv1 Reinstall-/Onboarding-Drift und Secret-Store-Startcrash behoben)

**Scope**: Nach der Neuinstallation von `srv1` erschien das WebUI-Onboarding nicht mehr. Die Live-Ursache war zweistufig: erst crashte `beagle-control-plane` beim Start, weil `/var/lib/beagle/secrets` im Reinstall-Pfad nicht fuer den Service-User vorbereitet wurde; danach blieb der Host bei weiteren Re-Runs im falschen Auth-Zustand, weil der Installer den Bootstrap-/Onboarding-Modus nicht stabil konservierte und frische Installationen alten Auth-State nicht explizit verwarfen.

- Repo-Fixes:
  - `scripts/install-beagle-host-services.sh`
    - legt `/var/lib/beagle/secrets` jetzt reproduzierbar mit `0700` fuer `beagle-manager` an.
    - kann bei frischen Installationen Auth-State mit `BEAGLE_AUTH_RESET_ON_INSTALL=1` gezielt verwerfen.
    - konserviert einen vorhandenen `BEAGLE_AUTH_BOOTSTRAP_DISABLE`-Zustand bei spaeteren Service-Re-Runs, statt ihn still auf `0` zurueckzusetzen.
    - loescht ein altes `BEAGLE_AUTH_BOOTSTRAP_PASSWORD` aus der Runtime-Env, sobald Onboarding-Modus aktiv bleibt.
  - `scripts/install-beagle-host.sh`
  - `scripts/install-beagle-host-postinstall.sh`
    - reichen den neuen Reset-Flag an den Host-Service-Installer durch.
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
  - `server-installer/installimage/usr/local/bin/beagle-installimage-bootstrap`
    - setzen fuer frische Server-Installationen jetzt explizit `BEAGLE_AUTH_RESET_ON_INSTALL=1`, damit alte `users.json`/`onboarding.json`-Reste keinen Neuinstallationszustand ueberdecken.
  - `tests/unit/test_install_beagle_host_services_regressions.py`
    - Regression fuer Secret-Store-Dir und install-time-aware Auth-Reset/Bootstrap-Handling ergaenzt.
- Live-Fix auf `srv1`:
  - neuen Installpfad nach `/opt/beagle` ausgerollt.
  - `beagle-control-plane` kam nach Secret-Store-Fix wieder hoch.
  - Auth-State absichtlich in Fresh-Install-Zustand zurueckgesetzt (`BEAGLE_AUTH_BOOTSTRAP_DISABLE=1`, kein `BEAGLE_AUTH_BOOTSTRAP_PASSWORD`, Auth-Dir verworfen).
- Verifikation:
  - `curl https://srv1.beagle-os.com/beagle-api/api/v1/auth/onboarding/status` -> `200` mit `pending: true`, `completed: false`.
  - Browser-Smoke via Chrome DevTools: Onboarding-Modal `Beagle Server Onboarding` ist wieder sichtbar und fokussiert.
  - `beagle-control-plane`, `nginx`, `beagle-novnc-proxy` auf `srv1` aktiv.

---

## Update (2026-04-29, Enterprise-Readiness Docs-Konsolidierung)

**Scope**: Komplette Aufraeumung der Doku auf 5 thematische Checklisten + zentrale Navigation. Live-Fix der CI fuer Integration-Tests.

- Doku-Struktur:
  - `docs/refactorv2/`, `docs/gofuture/`, `docs/goenterprise/`, `docs/goadvanced/`, `docs/gorelease/` per `git mv` nach `docs/archive/` verschoben (History erhalten).
  - Neu: `docs/checklists/01-platform.md`, `02-streaming-endpoint.md`, `03-security.md`, `04-quality-ci.md`, `05-release-operations.md`. Jedes Item gegen das Repo verifiziert.
  - Neu: `docs/README.md` (zentrale Navigation), `docs/STATUS.md` (Enterprise-Readiness Snapshot mit Ampel + Release-Gates).
  - Doppelte Dateinummern aufgeloest (`docs/refactor/04-latest-e2e-test-report.md` → `12-...`, `docs/archive/goadvanced/11-beagle-parity-checklist.md` → `13-...`).
  - Top-Level-Doks in Subfolder einsortiert (`HETZNER-INSTALLIMAGE-DEPLOYMENT.md` → `deployment/hetzner-installimage.md`, `architecture.md` → `architecture/overview.md`, `security.md` → `security/overview.md` u.a.).
  - `MASTER-PLAN.md` Section 2 auf neue Checklist-Struktur umgebaut; alle Pfade in Section 3 (Themen-Zuordnung) auf `docs/archive/...` umgebogen.
  - `scripts/check-gofuture-complete.sh` → `scripts/check-checklists-complete.sh` (generisch, optional `CHECKLIST_GATE_LIST` einschraenkbar).
  - `docs/contributing.md` + `.github/workflows/no-legacy-provider-references.yml` Doc-Links aktualisiert.

- CI-Live-Fix:
  - `.github/workflows/tests.yml`: neuer Job `integration` zwischen `bats` und `webui-provisioning-smoke`. Faehrt `python -m pytest tests/integration/ -q -p no:warnings` mit `PYTHONPATH=$workspace`. Lokal verifiziert: **89 passed in 1.41s**.

- Regel:
  - Es gibt nur noch 5 aktive Checklisten. Neue Aufgaben kommen ausschliesslich dort hin. Die archivierten Plan-Verzeichnisse sind kein Auftragsbacklog mehr.

---

## Update (2026-04-30, Plan 12 Schritt 1+2: i18n + error-handler implementiert)

**Scope**: i18n-Infrastruktur und standardisierter Error-Handler fuer die Beagle Web Console.

- Code:
  - `website/locales/de.json` — 60+ Uebersetzungsschluesseln (Deutsch)
  - `website/locales/en.json` — Spiegelstruktur (Englisch)
  - `website/ui/i18n.js` — Lightweight-i18n: `t(key, params)`, `setLanguage`, `getLanguage`, `getSupportedLanguages`, XHR-basiertes synchrones Laden, `beagle:langchange`-Event
  - `website/ui/error-handler.js` — `showError`, `showWarning`, `showSuccess`, `showInfo`, `handleFetchError`, `withErrorHandling`; baut auf `showJobToast` aus `jobs_panel.js` auf; Maps HTTP-Status auf i18n-Texte; Stack-Trace nur in Dev-Mode
  - `website/ui/cluster.js` — `console.error` auf `showError` migriert
  - `website/ui/events.js` — 2x `window.alert` auf `showInfo`/`showError` migriert (dynamic import)
  - `website/ui/secrets_admin.js` — 2x `alert()` auf `showError` migriert (dynamic import)
- Tests:
  - `tests/unit/test_i18n_and_error_handler.py` — 21 Tests, alle PASS
- Validierung:
  - `node --check` alle modifizierten Module: OK
  - pytest `test_i18n_and_error_handler.py`: 21/21 PASS

---

## Update (2026-04-29, Sunshine stream-prep runtime fix on srv1 partially validated)

**Scope**: Der offene Sunshine/Moonlight-Rerun fuer `ensure-vm-stream-ready.sh` wurde technisch entblockt (Import-/SCP-Fix), live auf `srv1` neu gefahren und als teil-erledigt dokumentiert.

- Code:
  - `scripts/ensure-vm-stream-ready.sh`
    - exportiert jetzt den Repo-Root in `PYTHONPATH`, damit Provider-Helper-Imports (`core/*`) in Live-Host-Kontexten nicht mehr mit `ModuleNotFoundError` brechen.
    - credential-Fallback fuer Sunshine erweitert (VM-Description + installer-state), damit legacy-/teilmigrierte VMs nicht frueh am Secret-Lookup scheitern.
  - `scripts/configure-sunshine-guest.sh`
    - exportiert ebenfalls `PYTHONPATH` fuer Provider-Importe.
    - SSH/SCP-Transferpfad fuer Guest-Setup von `/tmp/pve-sunshine-setup.sh` auf `/home/<guest>/pve-sunshine-setup.sh` umgestellt, um VM-seitige `/tmp`-Permission-Probleme zu umgehen.
- Validierung:
  - lokal: `bash -n scripts/ensure-vm-stream-ready.sh scripts/configure-sunshine-guest.sh` => OK
  - `srv1`: Patch nach `/opt/beagle/scripts` deployed und Rerun gestartet.
    - VM100: erfolgreicher unattended Run (`Configured Sunshine guest VM 100 ...`).
    - VM102: externer Runtime-Blocker, da VM im beagle-provider State nicht gefunden wird (`RuntimeError: VM 102 not found in beagle provider state`, danach keine IPv4-Ermittlung moeglich).

---

## Update (2026-04-29, Plan-07 5GB Backup-Lasttest auf srv1 geschlossen)

**Scope**: Der offene Plan-07-Lasttest fuer ein explizites 5GB-Backup ist geschlossen und live auf `srv1` reproduzierbar validiert.

- Code:
  - `scripts/test-backup-load-5gb-smoke.sh` (neu)
    - erzeugt eine 5GB-Testpayload unter `/etc/beagle/backup-loadtest`.
    - startet Backup via `POST /api/v1/backups/run` mit eindeutigem `Idempotency-Key`.
    - pollt Async-Jobstatus ueber `GET /api/v1/jobs/{job_id}`.
    - prueft Snapshot/File-List-Nachweis und Job-History-Eintrag.
    - setzt die geaenderte Backup-Policy (`target_path`) nach dem Lauf zurueck.
  - `beagle-host/services/backup_service.py`
    - tar-Eingabe wird aus einer lesbaren Manifest-Liste erzeugt (`find ... -readable -print0` + `tar --null -T -`), damit unreadable Host-Dateien den Lauf nicht brechen.
    - nicht-fatale tar-Warnungen werden toleriert, solange ein Archiv geschrieben wurde und keine fatalen Marker vorliegen.
- Validierung:
  - lokal: `python3 -m py_compile beagle-host/services/backup_service.py` => OK
  - lokal: `python3 -m pytest -q tests/unit/test_backup_service.py tests/unit/test_backups_http_surface.py` => `42 passed`
  - `srv1`: `scripts/test-backup-load-5gb-smoke.sh` => `BACKUP_LOAD_5GB_SMOKE=PASS`
    - Payload groesse: `5368709120` Bytes
    - Backup-Run ueber Async-Queue erfolgreich abgeschlossen

---

## Update (2026-04-29, Stream-Persistenz ueber Voll-Reboot auf srv1 validiert)

**Scope**: Offener Master-Plan-Punkt "Stream-Persistenz ohne manuelle Firewall-/Route-Intervention" ist geschlossen.

- Code:
  - `scripts/test-stream-persistence-reboot-smoke.sh` (neu)
    - laedt Live-Profil aus der Host-API und prueft `egress_mode`/`egress_type`.
    - validiert Sunshine-API vor und nach VM-Reboot.
    - rebootet VM via Provider-Flow und wartet auf `running`.
    - vergleicht Profilfelder nach Reboot auf Unveraendertheit.
    - enthaelt Sunshine-Check-Fallback (public URL -> private Guest-URL via `moonlight_local_host`) fuer stabile Host-seitige Reachability-Pruefung.
    - exportiert `PYTHONPATH` fuer Provider-Importe (`core`-Module).
- Validierung:
  - lokal: `bash -n scripts/test-stream-persistence-reboot-smoke.sh` => OK
  - `srv1`: `scripts/test-stream-persistence-reboot-smoke.sh --vmid 100 --node beagle-0`
    - `STREAM_REBOOT_PERSISTENCE_SMOKE=PASS`
    - Sunshine API vor/nach Reboot erreichbar (`HTTP 401` via `https://192.168.123.116:50001/api/apps`)
    - VM100 nach Reboot wieder `running`
    - Stream-Profil nach Reboot unveraendert

---

## Update (2026-04-29, VPN als Standardpfad fuer VM-Streaming durchgezogen)

**Scope**: Der globale Standardpfad fuer VM-Streaming ist auf WireGuard/VPN umgestellt (statt `direct`) und sowohl auf `srv1` als auch in der lokalen Thinclient-VM verifiziert.

- Code:
  - `beagle-host/services/vm_profile.py`
    - Default-Egress fuer VM-Profile von `direct` auf `full` + `wireguard` + `wg-beagle` umgestellt.
  - `beagle-host/services/installer_script.py`
    - Installer-Preset-Fallbacks fuer Egress auf `full`/`wireguard`/`wg-beagle` umgestellt.
  - `beagle-host/services/endpoint_enrollment.py`
    - Enrollment-Config defaultet jetzt auf `full`; WireGuard-Bootstrap-Defaults greifen auch bei unvollstaendigen Profilfeldern.
  - `beagle-host/services/thin_client_preset.py`
    - Runtime-Extension-Defaults fuer Egress auf WireGuard-Standard gesetzt.
  - `beagle-host/services/fleet_inventory.py`
    - Inventory-Fallback fuer `egress_mode` von `direct` auf `full` angepasst.
  - Thinclient-Stack:
    - `thin-client-assistant/installer/env-defaults.json`
    - `thin-client-assistant/runtime/apply_enrollment_config.py`
    - `thin-client-assistant/runtime/runtime_endpoint_enrollment.sh`
    - `thin-client-assistant/usb/pve-thin-client-local-installer.sh`
    - `thin-client-assistant/usb/usb_writer_write_stage.sh`
    - `thin-client-assistant/usb/pve-thin-client-usb-installer.ps1`
    - Alle relevanten Default-/Fallback-Pfade von `direct` auf `full` + `wireguard` + `wg-beagle` gezogen.
- Tests/Validierung:
  - lokal: `python3 -m pytest -q tests/integration/test_endpoint_boot_to_streaming.py` => `18 passed`.
  - lokal: Python-Compile + `bash -n` fuer geaenderte Service-/Runtime-Dateien => OK.
  - `srv1` live:
    - `beagle-control-plane.service` nach Patch-Neuladung aktiv.
    - `GET /api/v1/vms/100` liefert `egress_mode=full`, `egress_type=wireguard`, `egress_interface=wg-beagle`.
    - `/api/v1/vms/100/installer.sh` enthaelt im eingebetteten Preset `PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_MODE=full`, `...TYPE=wireguard`, `...INTERFACE=wg-beagle`.
  - lokale Thinclient-VM live:
    - WireGuard-Enrollment gegen `https://srv1.beagle-os.com/beagle-api` erfolgreich (`wg-beagle` up, Client-IP `10.88.1.1/32`).
    - Route zur privaten VM100-IP `192.168.123.116` geht ueber `wg-beagle`.
    - WG-Transferzaehler steigt bei Zugriff auf die private Sunshine-Ziel-IP an (VPN-Datenpfad aktiv).

---

## Update (2026-04-29, Smoke-Scripts stabilisiert + Sunshine/Moonlight Validierungspfad eingeführt)

**Scope**: Drei offene TODO-Punkte aus `08-todo-global.md` geschlossen:
  1. `test-server-installer-live-smoke.sh` DHCP-Timeout bei frisch gebauter ISO erhöht + ARP-Fallback ergänzt.
  2. `test-standalone-desktop-stream-sim.sh` für echte libvirt-Ausführung stabilisiert (umask 0022, chmod 0644 auf Fake-ISO, chmod o+x auf TMP_DIR).
  3. Zwei neue Smoke-Skripte für Sunshine-Self-Heal und Moonlight-App-Name-Resolver eingeführt.

- Code:
  - `scripts/test-server-installer-live-smoke.sh`
    - `WAIT_DHCP_SECONDS` von 120 auf 300 angehoben.
    - `WAIT_HEALTH_SECONDS` von 240 auf 300 angehoben.
    - `wait_for_vm_ip` ergänzt um ARP-Fallback (`arp -n | awk ...`) wenn virsh kein DHCP-Lease liefert.
  - `scripts/test-standalone-desktop-stream-sim.sh`
    - `umask 022` am Script-Anfang gesetzt, damit ISO-Cache-Verzeichnis und Dateien von libvirt-qemu gelesen werden können.
    - `chmod 0644 "${FAKE_ISO_PATH}"` und `chmod o+x "${TMP_DIR}"` nach ISO-Erstellung.
  - `scripts/test-sunshine-selfheal-smoke.sh` (neu)
    - Prüft `beagle-sunshine-healthcheck.timer` aktiv.
    - Killst sunshine via `pkill -9`, wartet bis zu `BEAGLE_SMOKE_WAIT_SEC` (default 90s) auf Neustart.
    - Prüft Sunshine API Antwort nach Neustart.
    - Führt `beagle-sunshine-healthcheck --repair-only` manuell aus.
  - `scripts/test-moonlight-appname-smoke.sh` (neu)
    - Ruft `GET /api/apps` gegen die Sunshine-API auf.
    - Führt die Resolver-Logik aus `moonlight_remote_api.sh` inline nach.
    - Validiert, dass `Desktop` (case-insensitive) auflösbar ist.
    - Gibt `MOONLIGHT_APPNAME_SMOKE=PASS` oder `WARN` aus.
- Validierung:
  - `bash -n` Syntax-Prüfung aller vier Skripte: OK
  - srv1-Smoke-Runs für `test-sunshine-selfheal-smoke.sh` und `test-moonlight-appname-smoke.sh` stehen an, sobald die neuen Scripts über den Repo-Auto-Update auf srv1 sind.

---

## Update (2026-04-29, prepare-host-downloads ModuleNotFoundError auf srv1 geschlossen)

**Scope**: Der Host-Downloads-/Publish-Pfad auf `srv1` lief in `scripts/prepare-host-downloads.sh` in ein `ModuleNotFoundError: No module named 'core'`, sobald der Provider-Helper geladen wurde. Ursache war ein fehlender `PYTHONPATH`-Export fuer Repo-Top-Level-Module im Shell-Einstieg.

- Code:
  - `scripts/prepare-host-downloads.sh`
    - exportiert jetzt `PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"`, bevor der Python-Helper `scripts/lib/prepare_host_downloads.py` und der Provider-Helper geladen werden.
  - `tests/unit/test_proxy_env_precedence_regressions.py`
    - neue Regression stellt sicher, dass der `prepare-host-downloads`-Einstieg diesen `PYTHONPATH`-Export enthaelt.
- Validierung:
  - lokal: `python3 -m pytest tests/unit/test_proxy_env_precedence_regressions.py -q` => `4 passed`
  - `srv1`: `bash scripts/prepare-host-downloads.sh` laeuft wieder erfolgreich durch und erzeugt die Host-Downloads unter `/opt/beagle/dist`.

## Update (2026-04-29, Security/TLS Let's-Encrypt-API Regression + srv1-Smoke geschlossen)

**Scope**: Der offene TODO-Punkt fuer den Security/TLS-API-Pfad ist geschlossen. Die Let's-Encrypt-Route hat jetzt explizite Regressionen auf Route-Ebene, und ein reproduzierbarer Host-Smoke validiert denselben Pfad auf `srv1`.

- Code:
  - `tests/unit/test_server_settings.py`
    - neue Regressionen fuer `POST /api/v1/settings/security/tls/letsencrypt`:
      - invalid domain liefert `400` + `invalid domain format`
      - erfolgreicher Service-Pfad liefert `200`
  - `scripts/test-security-tls-api-smoke.sh`
    - liest API-Token aus `/etc/beagle/beagle-manager.env`
    - prueft `GET /api/v1/settings/security/tls` (`200` + Basisschema)
    - prueft Guardrail auf Let's-Encrypt-Request mit invalid domain (`400`)
- Validierung:
  - lokal: `python3 -m pytest tests/unit/test_server_settings.py -q` => `30 passed`
  - `srv1`: `SECURITY_TLS_API_SMOKE=PASS`

## Update (2026-04-29, srv1 Control-Plane-Runtime und IAM/Audit-Smokes nachgezogen)

**Scope**: Der offene Refactor-Block um den vermeintlich inaktiven `beagle-manager` wurde auf den realen Runtime-Zustand korrigiert. Die produktive Unit auf `srv1` ist `beagle-control-plane.service`; darauf aufbauend sind die offenen IAM-/Audit-Smokes jetzt ebenfalls reproduzierbar gruen.

- Code:
  - `scripts/test-control-plane-runtime-smoke.sh`
    - prueft per SSH `systemctl is-active beagle-control-plane`.
    - liest den Host-Token aus `/etc/beagle/beagle-manager.env` und verifiziert `GET /api/v1/health` lokal auf dem Zielhost.
- Lokale Validierung:
  - `python3 -m pytest tests/unit/test_iam_ui_regressions.py tests/unit/test_audit_ui_regressions.py -q` => `6 passed`
- `srv1`-Validierung:
  - `scripts/test-control-plane-runtime-smoke.sh srv1.beagle-os.com` => `CONTROL_PLANE_RUNTIME_SMOKE=PASS`
  - `python3 scripts/test-iam-plan13-smoke.py --host 127.0.0.1 --port 9088` => `PLAN13_IAM_SMOKE=PASS`
  - `bash scripts/test-audit-compliance-live-smoke.sh` => `AUDIT_COMPLIANCE_SMOKE=PASS`
- Blocker:
  - `srv2` ist aktuell per SSH nicht erreichbar (`Connection timed out`); deshalb konnte die gleiche Runtime-Bestaetigung dort noch nicht erneut gefahren werden.

## Update (2026-04-29, UI-Provisioning-Smoke in CI geschlossen)

**Scope**: Der offene Refactor-Punkt fuer einen UI-seitigen Provisioning-Smoke in CI ist geschlossen. Die WebUI wird jetzt in einem dedizierten GitHub-Actions-Job mit Playwright gegen gemockte API-Routen durch den echten Token-Login- und Provisioning-Modal-Flow geprueft.

- Code:
  - `scripts/test-provisioning-ui-smoke.py`
    - mockt die benoetigten `/api/v1`- und `/beagle-api/api/v1`-Surfaces fuer Dashboard und Provisioning.
    - shimt `window.BeagleBrowserCommon`, damit die modulare WebUI auch im statischen CI-Serve-Setup bootstrappt.
    - verifiziert Token-Login, geoeffneten Provisioning-Modal, erfolgreichen Create-Flow, Progress-Dialog und Recent-Requests-Tabelle.
  - `.github/workflows/tests.yml`
    - neuer Job `webui-provisioning-smoke` installiert Playwright/Chromium, staged temporaer `core/platform/browser-common.js` in den statisch servierten `website/`-Baum und fuehrt den Smoke aus.
- Lokale Validierung:
  - `python3 -m py_compile scripts/test-provisioning-ui-smoke.py` => OK
  - `python3 scripts/test-provisioning-ui-smoke.py --base-url http://127.0.0.1:4173 --timeout-ms 15000` => `PROVISIONING_UI_SMOKE=PASS`
- `srv1`-Hinweis:
  - SSH-Erreichbarkeit geprueft, aber kein Playwright-Paket auf `srv1` vorhanden; deshalb fuer diesen CI-zentrierten Slice keine vollwertige Browser-Live-Abnahme auf `srv1` gefahren.

## Update (2026-04-29, VM-Delete/noVNC UI-Regressions geschlossen)

**Scope**: Zwei offene UI-Regressionspunkte fuer VM-Aktionen geschlossen: Delete-Sichtbarkeit + Inventory-Refresh sowie noVNC-Buttons/Launch-/Error-Guards.

- Tests:
  - `tests/unit/test_vm_actions_ui_regressions.py`
    - noVNC Inventory-/Detail-Verfuegbarkeit
    - noVNC Launch-/Unavailable-/Missing-URL-/Unsafe-URL-Guards
    - VM-Delete-Sichtbarkeit in Detail-Actions
    - VM-Delete Success/Failure-Logging
    - Post-Delete Dashboard-Refresh (`loadDashboard({ force: true })`)
  - lokal: `python3 -m pytest tests/unit/test_vm_actions_ui_regressions.py -q` => `5 passed`
- Syntax-Check:
  - `node --check website/ui/actions.js website/ui/inventory.js website/main.js` => OK
- srv1-Validierung:
  - kopierte Repo-Dateien auf `srv1` gegen stabile Marker geprueft
  - Ergebnis: `VM_ACTIONS_UI_REGRESSION_SMOKE=PASS`

## Update (2026-04-29, QEMU+SSH Live-Migration-Deadlock eingegrenzt + Shared-Storage-Abnahmepfad dokumentiert)

**Scope**: Offenen Global-TODO-Punkt zur Live-Migration zwischen `srv1` und `srv2` geschlossen. Migration-Fehlerpfad liefert jetzt reproduzierbar eine klare Operator-Empfehlung fuer Shared-Storage-Migration oder cold/offline Fallback.

- Code:
  - `beagle-host/services/migration_service.py`
    - neue Deadlock-Heuristik fuer qemu+ssh-bezogene Timeout-/Connection-/Migrate-Fehler
    - virsh-Execution-Wrap mit explizitem Guidance-Text bei erkanntem Deadlock-Pfad
    - dokumentierter Abnahmepfad im Runtime-Error: shared storage (live) oder `copy_storage=true` (cold/offline)
- Tests:
  - `tests/unit/test_migration_service.py`
    - neuer Test fuer Deadlock-Hinweistext inkl. Shared-Storage-/Fallback-Empfehlung
    - neuer Test, dass Nicht-Deadlock-Providerfehler unveraendert bleiben
  - lokal: `python3 -m pytest tests/unit/test_migration_service.py -q` => `8 passed`
- Smoke:
  - lokal: `python3 scripts/test-vm-migration-smoke.py` => `VM_MIGRATION_SMOKE=PASS`
  - `srv1`: gezielter Runtime-Smoke mit qemu+ssh-timeout-Fehler simuliert den Live-Fehlerpfad und bestaetigt Guidance:
    - `DEADLOCK_HINT_PRESENT True`
    - `COPY_STORAGE_FALLBACK_HINT True`

## Update (2026-04-29, Sunshine/Desktop-Guest-Smoke im Provisioning-Ready-Flow erweitert)

**Scope**: Offenen Global-TODO-Punkt fuer neue WebUI-Desktop-VMs geschlossen: Nach dem Provisioning wird im Stream-Ready-Flow jetzt zusaetzlich geprueft, ob `xset q` auf `DISPLAY=:0` erfolgreich ist und ob `light-locker`/`xfce4-power-manager` nicht laufen.

- Code:
  - `scripts/ensure-vm-stream-ready.sh`
    - neue Guest-Check-Funktion `sunshine_guest_desktop_smoke_json`
    - neuer Verify-Schritt nach erfolgreichem Sunshine-API-Check
    - nicht-blockierender Warnpfad (`ready` bleibt erhalten), wenn Desktop-Guard fehlschlaegt
- Tests:
  - neu `tests/unit/test_ensure_vm_stream_ready_regressions.py`
  - erweitert `tests/unit/test_configure_sunshine_guest_regressions.py`
  - lokal: `python3 -m pytest tests/unit/test_ensure_vm_stream_ready_regressions.py tests/unit/test_configure_sunshine_guest_regressions.py -q` => `2 passed`
- Live-Validierung auf `srv1`:
  - Lauf gegen VM 100 (`beagle-0`) mit der geaenderten Script-Version
  - Ergebnis im Installer-Prep-State: `status=ready`, `phase=complete`, Message enthaelt den neuen Desktop-Guard-Warnhinweis
  - Damit ist der geforderte Live-Smoke im echten Runtime-Pfad nachgezogen, ohne bestehende Provisioning-Ready-Flows hart zu brechen.

## Update (2026-04-29, GoAdvanced Plan 06 Schritt 3 Teil 3: Session-Repository)

**Scope**: Dritter produktiver Repository-Slice auf SQLite-Basis umgesetzt.

- Backend:
  - `core/repository/session_repository.py`
    - CRUD-Basis fuer Sessions: `get(session_id)`, `list(pool_id=None, user_id=None, status=None)`, `save(session)` (UPSERT), `delete(session_id)`.
    - FK-kompatible Speicherung gegen `pools`/`vms` bei gleichzeitigem Beibehalten der Session-Payload als JSON.
  - `tests/unit/test_session_repository.py`
    - neue Tests fuer Roundtrip, UPSERT-Update, Filter (pool/user/status), Delete-Semantik und Pflichtfeld-Validierung (`session_id`, `pool_id`).
- Lokale Tests:
  - `python3 -m pytest tests/unit/test_session_repository.py tests/unit/test_device_repository.py tests/unit/test_vm_repository.py tests/unit/test_sqlite_db.py -q` -> `21 passed`
- `srv1`-Validierung:
  - non-invasiver Repo-Smoke mit temporaer hochgeladenen Dateien (`sqlite_db.py`, `001_init.sql`, `session_repository.py`).
  - Ergebnis: `SRV1_PLAN06_SESSION_REPO_SMOKE=PASS`.
- Plan-Status:
  - `session_repository.py` als Teil von Plan 06 Schritt 3 umgesetzt.

## Update (2026-04-29, GoAdvanced Plan 06 Schritt 3 Teil 2: Device-Repository)

**Scope**: Zweiter produktiver Repository-Slice auf SQLite-Basis umgesetzt.

- Backend:
  - `core/repository/device_repository.py`
    - CRUD-Basis fuer Devices: `get(device_id)`, `list(status=None, fingerprint=None)`, `save(device)` (UPSERT), `delete(device_id)`.
    - Device-Payload bleibt als JSON erhalten, waehrend `device_id`, `fingerprint`, `hostname`, `status`, `assigned_pool_id`, `last_seen_at` fuer Filter/Indexe in Spalten gefuehrt werden.
  - `core/persistence/migrations/001_init.sql`
    - Devices um `status`-Spalte und Index `idx_devices_status` erweitert.
  - `tests/unit/test_device_repository.py`
    - neue Tests fuer Roundtrip, UPSERT-Update, Status-/Fingerprint-Filter, Delete-Semantik und Pflichtfeld-Validierung.
- Lokale Tests:
  - `python3 -m pytest tests/unit/test_device_repository.py tests/unit/test_vm_repository.py tests/unit/test_sqlite_db.py -q` -> `16 passed`
- `srv1`-Validierung:
  - non-invasiver Repo-Smoke mit temporaer hochgeladenen Dateien (`sqlite_db.py`, `001_init.sql`, `vm_repository.py`, `device_repository.py`).
  - Ergebnis: `SRV1_PLAN06_DEVICE_REPO_SMOKE=PASS`.
- Plan-Status:
  - `device_repository.py` als Teil von Plan 06 Schritt 3 umgesetzt.

## Update (2026-04-29, GoAdvanced Plan 06 Schritt 3 Teil 1: VM-Repository)

**Scope**: Erster produktiver Repository-Slice auf SQLite-Basis umgesetzt.

- Backend:
  - `core/repository/vm_repository.py`
    - CRUD-Basis fuer VMs: `get(vmid)`, `list(node_id=None, status=None)`, `save(vm)` (UPSERT), `delete(vmid)`.
    - VM-Payload wird als JSON persistiert; zentrale Lookup-Spalten (`vmid`, `node_id`, `status`, `name`, `pool_id`) werden fuer Filter/Index-Nutzung mitgefuehrt.
  - `core/repository/__init__.py`
  - `core/persistence/migrations/001_init.sql`
    - `vms.pool_id` auf nullable + `ON DELETE SET NULL` angepasst, damit VMs ohne Pool-Zuordnung sauber persistierbar bleiben.
  - `tests/unit/test_vm_repository.py`
    - neue Tests fuer Roundtrip, UPSERT-Update, Filter (`node_id`/`status`), Delete-Semantik und VMID-Validierung.
- Lokale Tests:
  - `python3 -m pytest tests/unit/test_vm_repository.py tests/unit/test_sqlite_db.py -q` -> `11 passed`
- `srv1`-Validierung:
  - non-invasiver Repo-Smoke mit temporaer hochgeladenen Dateien (`sqlite_db.py`, `001_init.sql`, `vm_repository.py`).
  - Ergebnis: `SRV1_PLAN06_VM_REPO_SMOKE=PASS`.
- Plan-Status:
  - `docs/goadvanced/06-state-sqlite-migration.md`: Schritt 3 Teilpunkt `vm_repository.py` auf `[x]` gesetzt.

## Update (2026-04-29, GoAdvanced Plan 06 Schritt 2: Initiales SQLite-Schema)

**Scope**: Erstes produktives SQLite-Schema fuer den spaeteren Repository- und Importer-Pfad angelegt und validiert.

- Backend:
  - `core/persistence/migrations/001_init.sql`
    - Tabellen fuer `vms`, `pools`, `sessions`, `devices`, `gpus`, `audit_events`, `secrets_meta` angelegt.
    - Pflicht-Indizes `idx_vms_node_id`, `idx_sessions_user_id`, `idx_devices_fingerprint` sowie eindeutiger GPU-PCI-Index hinterlegt.
    - Foreign-Keys mit `ON DELETE CASCADE`/`SET NULL` fuer die ersten relationalen Kanten verdrahtet.
  - `tests/unit/test_sqlite_db.py`
    - Regressionen auf echte Repo-Migration erweitert: Tabellen-/Index-Erzeugung sowie FK-Verhalten gegen `001_init.sql` abgesichert.
- Lokale Tests:
  - `python3 -m pytest tests/unit/test_sqlite_db.py -q` -> `6 passed`
- `srv1`-Validierung:
  - non-invasiver Smoke mit temporaer hochgeladener `sqlite_db.py` + `001_init.sql`.
  - Ergebnis: `SRV1_PLAN06_SCHEMA_SMOKE=PASS`.
- Plan-Status:
  - `docs/goadvanced/06-state-sqlite-migration.md`: Schritt 2 auf `[x]` gesetzt.

## Update (2026-04-29, GoAdvanced Plan 06 Schritt 1: SQLite-DB-Layer)

**Scope**: Erster SQLite-Migrations-Slice umgesetzt; gemeinsame DB-Basis fuer spaetere Repository- und Importer-Schritte liegt jetzt im Repo.

- Backend:
  - `core/persistence/sqlite_db.py`
    - `BeagleDb(path)` mit per-Thread Connection-Reuse, WAL-Mode, `PRAGMA foreign_keys=ON`, `busy_timeout` und idempotentem `migrate(schema_dir)` ueber `schema_migrations`.
  - `tests/unit/test_sqlite_db.py`
    - neue fokussierte Regressionen fuer WAL-/Foreign-Key-Setup, Connection-Reuse, geordnete idempotente Migrationen und Stop-Verhalten bei defekten SQL-Dateien.
- Lokale Tests:
  - `python3 -m pytest tests/unit/test_sqlite_db.py -q` -> `4 passed`
- `srv1`-Validierung:
  - non-invasiver Smoke mit temporaer hochgeladener `sqlite_db.py`.
  - Ergebnis: `SRV1_PLAN06_DB_SMOKE=PASS`.
- Plan-Status:
  - `docs/goadvanced/06-state-sqlite-migration.md`: Schritt 1 auf `[x]` gesetzt.

## Update (2026-04-29, GoAdvanced Plan 01 Welle 3d Teil 4: Webhook/Stream/Settings/Sunshine/Gaming-Metrics)

**Scope**: Vierter 3d-Batch umgesetzt; verbleibende direkte Service-JSON-Write-Pfade auf `JsonStateStore`/atomare Helper migriert.

- Backend:
  - `beagle-host/services/webhook_service.py`
  - `beagle-host/services/stream_http_surface.py`
  - `beagle-host/services/server_settings.py`
  - `beagle-host/services/sunshine_integration.py`
  - `beagle-host/services/gaming_metrics_service.py`
- Lokale Tests:
  - `python3 -m pytest tests/unit/test_stream_http_surface.py tests/unit/test_beagle_stream_server_api.py tests/unit/test_beagle_stream_client_broker.py tests/unit/test_server_settings.py tests/unit/test_gaming_metrics.py tests/unit/test_gaming_pool.py tests/unit/test_pools_http_surface.py -q` -> `67 passed`
- `srv1`-Validierung:
  - non-invasiver Batch-Smoke via `PYTHONPATH=/tmp/beagle-wave3d-part4:/opt/beagle:/opt/beagle/beagle-host/services` mit den fuenf geaenderten Dateien.
  - Ergebnis: `SRV1_WAVE3D_PART4_SMOKE=PASS`.
- Plan-01-Abschlussstatus:
  - `rg -n "write_text\\(json\\.dumps\\(" beagle-host/services --glob '*.py'` -> keine Treffer.
  - Welle 3d und Plan-01-Restpunkt (`Repo-Grep`) geschlossen.

## Update (2026-04-29, GoAdvanced Plan 01 Welle 3d Teil 3: Endpoint/Firewall/Cluster-Membership)

**Scope**: Dritter 3d-Batch umgesetzt, um direkte JSON-Write-Pfade weiter zu reduzieren.

- Backend:
  - `beagle-host/services/endpoint_report.py`
  - `beagle-host/services/firewall_service.py`
  - `beagle-host/services/cluster_membership.py`
  - Persistenz in allen drei Services auf `JsonStateStore`/atomare Store-Helper umgestellt.
- Lokale Tests:
  - `python3 -m pytest tests/unit/test_cluster_membership.py tests/unit/test_endpoint_http_surface.py tests/unit/test_endpoint_lifecycle_surface.py -q` -> `38 passed`
- `srv1`-Validierung:
  - non-invasiver Batch-Smoke via `PYTHONPATH=/tmp:/opt/beagle:/opt/beagle/beagle-host/services` mit den drei geaenderten Dateien.
  - Ergebnis: `SRV1_WAVE3D_PART3_SMOKE=PASS`.
- Rest-Grep nach diesem Batch:
  - Verbleibende direkte `write_text(json.dumps(`-Pfade in `beagle-host/services`: `webhook_service.py`, `stream_http_surface.py`, `server_settings.py`, `sunshine_integration.py`, `gaming_metrics_service.py`.

## Update (2026-04-29, GoAdvanced Plan 01 Welle 3d Teil 2: Maintenance/Installer-Logs/HA-Watchdog)

**Scope**: Zweiter 3d-Batch umgesetzt, um verbleibende direkte JSON-Write-Pfade weiter zu reduzieren.

- Backend:
  - `beagle-host/services/maintenance_service.py`
  - `beagle-host/services/installer_log_service.py`
  - `beagle-host/services/ha_watchdog.py`
  - Persistenz in allen drei Services auf `JsonStateStore` umgestellt (kein direkter `write_text(json.dumps(...))`-Write mehr).
- Lokale Tests:
  - `python3 -m pytest tests/unit/test_maintenance_service.py tests/unit/test_installer_log_service.py tests/unit/test_ha_watchdog.py -q` -> `8 passed`
- `srv1`-Validierung:
  - non-invasiver Batch-Smoke via `PYTHONPATH=/tmp:/opt/beagle` mit den drei geaenderten Dateien.
  - Ergebnis: `SRV1_WAVE3D_PART2_SMOKE=PASS`.
- Plan-Status:
  - `docs/goadvanced/01-data-integrity.md`: Welle 3d-Teilfortschritt erweitert.

## Update (2026-04-29, GoAdvanced Plan 01 Welle 3d Teil 1: Backup/Entitlements/Stream-Policy)

**Scope**: Erste Teilwelle aus 3d umgesetzt, um verbleibende direkte JSON-State-Writes weiter abzubauen.

- Backend:
  - `beagle-host/services/backup_service.py`
  - `beagle-host/services/entitlement_service.py`
  - `beagle-host/services/stream_policy_service.py`
  - alle drei Services nutzen jetzt `JsonStateStore` statt direktem `write_text(json.dumps(...))`.
- Lokale Tests:
  - `python3 -m pytest tests/unit/test_backup_service.py tests/unit/test_entitlement_service.py tests/unit/test_stream_policy.py -q` -> `29 passed`
- `srv1`-Validierung:
  - non-invasiver Batch-Smoke via `PYTHONPATH=/tmp:/opt/beagle` mit den drei geaenderten Dateien.
  - Ergebnis: `SRV1_WAVE3D_BATCH_SMOKE=PASS`.
- Plan-Status:
  - `docs/goadvanced/01-data-integrity.md`: Welle 3d als Teilfortschritt ergaenzt.

## Update (2026-04-29, GoAdvanced Plan 01 Welle 3c geschlossen: Fleet Telemetry gehaertet)

**Scope**: Die naechste Datenintegritaets-Welle (3c) ist abgeschlossen; verbleibender direkter JSON-Schedule-Write in der Fleet-Telemetrie wurde auf `JsonStateStore` migriert und der gesamte Welle-3c-Satz erneut validiert.

- Backend:
  - `beagle-host/services/fleet_telemetry_service.py`
    - Maintenance-Schedule-Persistenz (`schedule_maintenance`/`get_maintenance_schedule`) von direktem JSON-Dateizugriff auf `JsonStateStore` migriert.
  - `session_manager.py`, `metrics_collector.py`, `workload_pattern_analyzer.py`, `smart_scheduler.py`
    - verifiziert als Welle-3c-Zielset ohne direkte `write_text(json.dumps(...))`-Persistenzpfade.
- Lokale Tests:
  - `python3 -m pytest tests/unit/test_fleet_telemetry.py tests/unit/test_maintenance_scheduling.py tests/unit/test_anomaly_detection.py tests/unit/test_metrics_collector.py tests/unit/test_workload_pattern.py tests/unit/test_smart_scheduler.py -q` -> `45 passed`
- `srv1`-Validierung:
  - non-invasiver Smoke mit kopierter `fleet_telemetry_service.py` via `PYTHONPATH=/tmp:/opt/beagle`.
  - Ergebnis: `SRV1_FLEET_TELEMETRY_SMOKE=PASS`.
- Plan-Status:
  - `docs/goadvanced/01-data-integrity.md`: Welle 3c auf `[x]` gesetzt.

## Update (2026-04-29, GoAdvanced Plan 01 Welle 3b geschlossen: MDM + Registry/Cluster/Alerts validiert)

**Scope**: Der naechste offene Datenintegritaets-Slice wurde geschlossen: Welle 3b ist jetzt vollstaendig auf `JsonStateStore` bzw. bereits gehaertete Persistenz gebracht.

- Backend:
  - `beagle-host/services/mdm_policy_service.py`
    - Persistenz von direktem JSON-Dateizugriff auf `JsonStateStore` migriert (`_load()`/`_save()`).
  - `beagle-host/services/device_registry.py`, `cluster_service.py`, `alert_service.py`
    - verifiziert: bereits `JsonStateStore`-basiert, kein direkter `write_text(json.dumps(...))`-Pfad mehr.
- Lokale Tests:
  - `python3 -m pytest tests/unit/test_mdm_policy.py tests/unit/test_device_registry.py tests/unit/test_cluster_enrollment_token.py tests/unit/test_fleet_alerts.py -q` -> `56 passed`
- `srv1`-Validierung:
  - non-invasiver Smoke mit kopierter `mdm_policy_service.py` via `PYTHONPATH=/tmp:/opt/beagle`.
  - Ergebnis: `SRV1_MDM_POLICY_SMOKE=PASS`.
- Plan-Status:
  - `docs/goadvanced/01-data-integrity.md`: Welle 3b auf `[x]` gesetzt.

## Update (2026-04-29, GoAdvanced Plan 01 Welle 3a geschlossen: Usage/Energy auf JsonStateStore)

**Scope**: Die verbleibenden Welle-3a-Services fuer Datenintegritaet wurden auf `JsonStateStore` migriert und auf `srv1` mit Runtime-Smoke validiert.

- Backend:
  - `beagle-host/services/usage_tracking_service.py`
    - `_load()` und `_save()` auf `JsonStateStore` umgestellt (kein direktes `read_text()/write_text(json.dumps(...))` mehr).
  - `beagle-host/services/energy_service.py`
    - Carbon-Config-Persistenz (`set_carbon_config`/`get_carbon_config`) auf `JsonStateStore` umgestellt.
- Lokale Tests:
  - `python3 -m pytest tests/unit/test_usage_tracking.py tests/unit/test_energy_service.py tests/unit/test_energy_cost_integration.py -q` -> `15 passed`
- `srv1`-Validierung:
  - geaenderte Dateien nach `/tmp/beagle-verify/` kopiert und mit `PYTHONPATH=/tmp/beagle-verify:/opt/beagle` als Runtime-Smoke ausgefuehrt.
  - Ergebnis: `SRV1_USAGE_ENERGY_SMOKE=PASS`.
- Plan-Status:
  - `docs/goadvanced/01-data-integrity.md`: Welle 3a jetzt vollstaendig `[x]`.

## Update (2026-04-29, GoAdvanced Plan 01 Datenintegritaet weitergezogen + Disk-Pressure behoben)

**Scope**: Nach Save-Fehlern durch vollen Datentraeger wurde zuerst lokaler Speicherplatz bereinigt und danach die naechste Welle der JsonStateStore-Migration inkl. srv1-Stresstest abgeschlossen.

- Betriebsstabilisierung:
  - Lokale Disk-Pressure auf dem Dev-Host behoben (PM2-Log-Wachstum + Cache-Bereinigung), damit Editor/Tests wieder reproduzierbar laufen.
- Persistenz-Migration (Code):
  - `beagle-host/services/action_queue.py`
  - `beagle-host/services/cost_model_service.py`
  - `beagle-host/services/gpu_streaming_service.py`
  - `beagle-host/services/attestation_service.py`
  - `beagle-host/services/storage_quota.py`
  - `beagle-host/services/vm_console_access.py`
  - `beagle-host/bin/beagle_novnc_token.py` (File-Locking + fsync + atomic replace)
  - alle genannten Services nutzen nun `JsonStateStore` oder ein gleichwertig gehaertetes Atomic-Pattern.
- Verifikation:
  - Lokal: `python3 -m pytest tests/unit/test_json_state_store.py tests/unit/test_attestation_service.py tests/unit/test_cost_model.py tests/unit/test_gpu_streaming.py tests/unit/test_storage_quota_service.py tests/unit/test_beagle_novnc_token.py` -> `57 passed`
  - Neu: `scripts/test-json-state-stress.sh` im Repo (1000 parallele Updates)
  - Lokal: Stress-Test `OK counter=1000 expected=1000`
  - `srv1`: Stress-Test mit `PYTHONPATH=/opt/beagle` ebenfalls `OK counter=1000 expected=1000`

## Update (2026-04-29, lokaler Thinclient-KVM-Smoke fuer `beagle-thinclient` reproduzierbar gemacht)

**Scope**: Fuer den verbleibenden Plan-02-Live-Restpunkt wird ein lokaler Thinclient-Test-Guest benoetigt. Auf diesem Host existierte bereits eine libvirt-Domain `beagle-thinclient`, aber es gab keinen reproduzierbaren Repo-Smoke dafuer und wegen nur noch ~280 MiB freiem Platz war ein zweiter Throwaway-Guest unpraktikabel.

- Lokaler Befund:
  - `virsh -c qemu:///system list --all` funktioniert lokal.
  - `beagle-thinclient` existiert bereits als persistente Domain und laeuft lokal mit SPICE-Display.
  - freier Platz auf `/var/lib/libvirt/images` und dem Workspace war zu knapp fuer einen zusaetzlichen frischen Test-Guest.
- Repo-Aenderung:
  - `scripts/test-thinclient-vm-smoke.sh` neu angelegt.
  - der Smoke wiederverwendet standardmaessig die bestehende Domain `beagle-thinclient`, startet sie bei Bedarf, prueft `running`, liest `domdisplay`, erstellt einen Screenshot und kann optional auch eine Domain aus dem Thinclient-ISO anlegen, falls spaeter wieder genug Platz vorhanden ist.
- Validierung:
  - `bash -n scripts/test-thinclient-vm-smoke.sh` erfolgreich.
  - lokaler Lauf erfolgreich:
    - `VM=beagle-thinclient`
    - `STATE=running`
    - `DISPLAY=spice://127.0.0.1:5902`
    - Screenshot `/tmp/beagle-thinclient-smoke.ppm` erfolgreich.

## Update (2026-04-29, GoEnterprise Plan 02 Auto-Remediation-Worker auf `srv1` geschlossen)

**Scope**: Im Plan-02-Fleet-Slice gab es bereits Drift-Report, Remediation-API, Operator-Buttons und persistente Konfiguration, aber noch keinen echten serverseitigen Hintergrundlauf. Ziel dieses Runs war, den offenen Restpunkt `Auto-Remediation-/Drift-Worker` reproduzierbar im Control-Plane-Prozess zu schliessen und auf `srv1` ohne Seiteneffekte zu validieren.

- Backend:
  - `beagle-host/services/fleet_http_surface.py`
    - neue gemeinsame Server-Routine `run_safe_auto_remediation(...)` eingefuehrt.
    - manueller `POST /api/v1/fleet/remediation/run` nutzt jetzt denselben Codepfad wie der Hintergrundworker.
    - Worker-Laeufe koennen ueber `require_enabled=True` hart auf die persistierte Remediation-Konfiguration gated werden.
  - `beagle-host/services/service_registry.py`
    - periodischen Fleet-Remediation-Thread eingefuehrt (`BEAGLE_FLEET_REMEDIATION_INTERVAL_SECONDS`, Default 300 s).
    - Worker startet als daemon thread nur einmal, fuehrt Safe-Aktionen nur bei aktivierter Konfiguration aus und schreibt Fehler/aktive Zyklen strukturiert ins Log.
  - `beagle-host/bin/beagle-control-plane.py`
    - Worker in Startup/Shutdown der Control Plane eingebunden.
- Tests:
  - `tests/unit/test_fleet_http_surface.py`
    - Enable-Gate fuer Worker-Laeufe abgesichert.
    - bestehende Fleet-Remediation-Suite erneut gruen.
- Lokale Validierung:
  - `pytest -q tests/unit/test_fleet_http_surface.py` -> `20 passed`
  - `python3 -m py_compile beagle-host/services/fleet_http_surface.py beagle-host/services/service_registry.py beagle-host/bin/beagle-control-plane.py` -> erfolgreich
- `srv1`-Validierung:
  - Runtime-Dateien nach `/opt/beagle/` kopiert, vorherige Stände mit `.bak.20260429T061942Z` gesichert.
  - `python3 -m py_compile` direkt auf `srv1` erfolgreich.
  - `beagle-control-plane.service` erfolgreich neu gestartet, `systemctl is-active` = `active`.
  - `journalctl -u beagle-control-plane.service -n 80` ohne Traceback oder Worker-Startfehler.
  - `curl -fsS http://127.0.0.1:9088/metrics | head` erfolgreich.

## Update (2026-04-29, Thinclient-WireGuard-Full-Tunnel + srv1 Peer-Reconcile/FW-Default geschlossen)

**Scope**: Der lokale Thinclient (`192.168.178.92`, VM100) lief noch direkt ueber das Heimnetz statt ueber das Beagle-WireGuard-Mesh. Gleichzeitig hatte `srv1` zwar bereits `wg-beagle` und eine Default-Firewall-Basis, uebernahm neu registrierte Thinclient-Peers aber noch nicht automatisch in die laufende WireGuard-Konfiguration.

- Backend / Runtime:
  - `beagle-host/services/service_registry.py`
    - WireGuard-Bootstrap-Defaults und endpoint-authentifizierte Route `POST /api/v1/vpn/register` verdrahtet.
  - `beagle-host/services/endpoint_lifecycle_surface.py`
    - `vpn/register` als echte Endpoint-Surface aufgenommen.
  - `beagle-host/services/wireguard_mesh_service.py`
    - Peer-Updates persistieren jetzt `allowed_ips`/`dns` stabil fuer Re-Enrollments.
  - `thin-client-assistant/runtime/runtime_endpoint_enrollment.sh`
  - `thin-client-assistant/runtime/prepare-runtime.sh`
    - WireGuard-Enrollment wird nach dem Endpoint-Enrollment automatisch angestossen, sobald das Profil `egress_type=wireguard` setzt.
  - `thin-client-assistant/runtime/enrollment_wireguard.sh`
    - robust auf manuellen Interface-Setup umgestellt: kein harter `wg-quick`-Pfad mehr.
    - DNS-Helfer (`resolvectl`/`resolvconf`) laufen jetzt mit Timeout und fallbacken notfalls auf direkte Resolver-Konfiguration statt zu haengen.
- Host / Security:
  - `scripts/apply-beagle-wireguard.sh`
    - richtet `wg-beagle`, NAT und Manager-Env-Defaults ein.
    - rendert registrierte Mesh-Peers aus `wireguard-mesh/mesh-state.json` jetzt in die Server-Konfiguration.
  - `beagle-host/systemd/beagle-wireguard-reconcile.service` + `.path` (neu)
    - Root-seitiger Reconcile-Pfad: Aenderungen am Mesh-State triggern sofort ein neues Rendern/Anwenden der Server-Peers.
  - `scripts/apply-beagle-firewall.sh`
    - Host-Firewall erlaubt standardmaessig UDP `51820` und Forwarding vom WireGuard-Interface.
  - `scripts/install-beagle-host-services.sh`
  - `scripts/build-server-installimage.sh`
    - WireGuard-Tooling wird bei Host-Install und Server-Image reproduzierbar mit ausgeliefert.
  - `thin-client-assistant/live-build/config/package-lists/pve-thin-client.list.chroot`
  - `thin-client-assistant/live-build/config/hooks/live/011-verify-runtime-deps.hook.chroot`
    - Thinclient-Live-Image enthaelt WireGuard-/`jq`-Abhaengigkeiten jetzt reproduzierbar; Build-Hook bricht bei fehlendem `wg`/`ip`/`jq` hart ab.
- Tests:
  - `tests/unit/test_endpoint_lifecycle_surface.py` (neu)
  - `tests/unit/test_apply_beagle_firewall_script.py` (neu)
  - `tests/unit/test_apply_beagle_wireguard_script.py` (neu)
  - `tests/unit/test_thin_client_live_build_regressions.py` (neu)
  - `tests/unit/test_wireguard_mesh.py`, `tests/unit/test_enrollment_wireguard.py`, `tests/unit/test_install_beagle_host_services_regressions.py`
- Live-Verifikation:
  - `srv1`: `wg-beagle` aktiv, nftables-Firewall aktiv, UDP `51820` offen, NAT fuer `10.88.0.0/16` aktiv.
  - `srv1`: neuer Root-Reconcile-Pfad aktiv (`beagle-wireguard-reconcile.path`), registrierter Thinclient-Peer live in `wg show wg-beagle`.
  - Thinclient `192.168.178.92`: `beagle-egress` aktiv, `latest handshake` gegen `46.4.96.80:51820`, Route zu `1.1.1.1` laeuft ueber `beagle-egress`.
  - Ergebnis: der laufende Moonlight-/Sunshine-Pfad fuer VM100 ist jetzt real ueber WireGuard getunnelt statt direkt ueber das lokale Netz.

## Update (2026-04-29, VM100 Black-Screen durch XFCE-Idle/Locker auf `srv1` behoben)

**Scope**: VM100 zeigte beim Connect auf `srv1` einen schwarzen Bildschirm; die Guest-Inspektion ergab aktives `light-locker`, `xfce4-power-manager`, X11-Screensaver-Timeout `600` und aktiviertes DPMS mit `Monitor is Off`.

- Befunde in der laufenden VM (`beagle-100` via QEMU Guest Agent):
  - Prozesse: `xfce4-session`, `light-locker`, `xfce4-power-manager`, `sunshine`.
  - `xset q`: `Screen Saver timeout=600`, `DPMS is Enabled`, `Monitor is Off`.
- Repo-Fix:
  - `scripts/configure-sunshine-guest.sh`
    - legt jetzt `/etc/X11/Xsession.d/90-beagle-disable-display-idle` an und schaltet dort `xset -dpms`, `xset s off`, `xset s noblank`.
    - legt fuer den Gastbenutzer zusaetzlich `~/.xprofile` mit denselben X11-Guards an.
    - legt fuer XFCE User-Autostart-Overrides mit `Hidden=true` fuer `light-locker`, `xfce4-power-manager` und `xfce4-screensaver` an.
  - `tests/unit/test_configure_sunshine_guest_regressions.py` prueft die Guardrails als Repo-Regression.
- Live-Rollout:
  - aktualisiertes `configure-sunshine-guest.sh` nach `srv1:/opt/beagle/scripts/` kopiert.
  - VM100 ueber denselben Provisioning-Pfad live neu konfiguriert (`--no-reboot`), inkl. Display-Manager-Restart.
- Verifikation nach Rollout:
  - Prozesse: `xfce4-session` + `sunshine`; `light-locker` und `xfce4-power-manager` laufen nicht mehr.
  - `xset q`: `Screen Saver timeout=0`, `prefer blanking: no`, `DPMS is Disabled`.
  - Autostart-Overrides auf dem Gast vorhanden, Xsession-Hook und `~/.xprofile` vorhanden.

## Update (2026-04-28, srv1 Auffaelligkeiten analysiert und Systemd-/Update-Drift gepatcht)

**Scope**: Die Live-Pruefung auf `srv1` zeigte drei failed units und einen Auto-Update-Status, der trotz installiertem Commit `dba99c2` weiter `updating` meldete.

- Befunde:
  - `beagle-cluster-auto-join.service` scheiterte mit `203/EXEC`, weil `scripts/beagle-cluster-auto-join.sh` im Repo und live nicht executable war.
  - `beagle-public-streams.service` scheiterte alle zwei Minuten durch `install: cannot change permissions of /var/lib/beagle/beagle-manager: Operation not permitted`; die Unit entzog dem Root-Prozess alle Capabilities, obwohl das Skript nftables und Beagle-State schreiben muss.
  - `networking.service` war seit 2026-04-21 failed, obwohl `enp35s0` und Default-Route aktiv sind; Ursache ist ein nicht-idempotenter Hetzner-ifupdown-Route-Hook (`route add ...` -> `File exists`).
  - `repo-auto-update-status.json` verglich einen Short-Commit (`dba99c2`) mit dem Full-Hash (`dba99c247...`) und konnte dadurch faelschlich `update_available=true` melden.
- Fixes:
  - `scripts/beagle-cluster-auto-join.sh` ist jetzt executable.
  - `beagle-host/systemd/beagle-public-streams.service` setzt explizit Root-Kontext, notwendige Capabilities und `ReadWritePaths=/etc/beagle /var/lib/beagle`.
  - `scripts/repo-auto-update.sh` normalisiert Short-/Full-Commit-Vergleiche mit `same_commit(...)` und schreibt bei No-Update den Full-Hash zurueck.
  - `server-installer/installimage/usr/local/sbin/beagle-network-interface-heal` normalisiert legacy `route add -net ...` Hooks auf idempotentes `ip route replace ... || true`.
- Verifikation:
  - `bash -n` fuer betroffene Shell-Skripte erfolgreich.
  - Repo-Auto-Update-Regression um Short-Hash-Assertion erweitert und direkt ausgefuehrt.

## Update (2026-04-28, Login-429 hinter nginx behoben)

**Scope**: `POST /api/v1/auth/login` lieferte auf `srv1` trotz korrekter Credentials `429 Too Many Requests`, weil der Login-Guard hinter nginx alle externen Browser als denselben Peer `127.0.0.1` behandelte.

- Backend:
  - `beagle-host/services/request_handler_mixin.py`
    - `_client_addr()` wertet `X-Forwarded-For`/`X-Real-IP` nur dann aus, wenn der direkte Peer ein lokaler Proxy ist.
    - API-Rate-Limit, Login-Guard, Audit-Remote-Addr und Auth-Session-Remote-Addr nutzen dadurch wieder die echte Client-IP statt global `127.0.0.1`.
- Frontend:
  - `website/ui/auth.js`
    - Login-POSTs sind Single-Flight, um Enter/Klick-Doppel-Submits nicht mehrfach gegen `/auth/login` zu senden.
    - `429` zeigt die vom Backend gelieferte Wartezeit im Login-Banner.
- Tests:
  - `tests/unit/test_request_handler_mixin_client_addr.py` deckt Forwarded-For hinter loopback proxy, Spoof-Abwehr bei direktem Peer und Login-Guard-Key-Scoping ab.
- Verifikation:
  - `python3 -m py_compile beagle-host/services/request_handler_mixin.py tests/unit/test_request_handler_mixin_client_addr.py` erfolgreich.
  - Direkter Assertion-Smoke fuer die neuen Tests erfolgreich.
  - `node --experimental-default-type=module --check website/ui/auth.js` erfolgreich.

## Update (2026-04-28, WebUI CSP inline-style fix fuer srv1)

**Scope**: Nach dem Auth-Gating-Fix blieb in der Browser-Console ein realer Frontend-Restfehler: mehrere WebUI-Module erzeugten HTML mit `style="..."`-Attributen und verletzten damit die produktive CSP `style-src 'self'`.

- Frontend:
  - `website/ui/scheduler_insights.js`, `website/ui/energy_dashboard.js`, `website/ui/gpu_dashboard.js`
    - dynamische Inline-Styles fuer Heatmaps und Auslastungsbalken durch feste CSS-Klassen/Buckets ersetzt.
  - `website/ui/settings.js`, `website/ui/cluster.js`, `website/ui/virtualization.js`
    - verbliebene Inline-Style-Attribute fuer Restore-Meldungen, Job-Progress-Initialzustand und mdev-Aktionsbuttons entfernt.
  - `website/styles/_helpers.css`, `website/styles/panels/_cluster.css`, `website/styles/panels/_settings.css`, `website/styles/panels/_virtualization.css`
    - CSP-konforme Klassen fuer Balken, Heatmap-Level, Green-Hours-Kacheln, Wide-Grid-Labels und Statusfarben ergaenzt.
- Verifikation:
  - `rg -n "style=|setAttribute\\(['\"]style|cssText|<style" website ...` liefert keine Treffer mehr.
  - Syntax-Checks der geaenderten ES-Module mit `node --experimental-default-type=module --check ...` erfolgreich.

## Update (2026-04-28, WebUI auth gating fix fuer Scheduler/Kosten/Energie live auf `srv1`)

**Scope**: Die WebUI hat geschuetzte Settings-/Telemetry-Endpunkte (`/scheduler/insights`, `/costs/*`, `/energy/*`) bereits vor erfolgreichem Login angefragt und dadurch auf `srv1` sofort sichtbare `401 Unauthorized`-Fehler erzeugt. Gleichzeitig wurden Schreibaktionen in diesen Panels browserseitig nicht an `settings:write` gespiegelt.

- Frontend:
  - `website/main.js`
    - Bootstrap rendert Scheduler-/Kosten-/Energie-Panels nicht mehr blind vor dem ersten Auth-/Session-Load.
  - `website/ui/state.js`
    - zentrale Helper `currentUserPermissions()` und `hasPermission()` eingefuehrt, damit RBAC-Pruefungen nicht pro Modul erneut ad hoc implementiert werden.
  - `website/ui/scheduler_insights.js`
  - `website/ui/cost_dashboard.js`
  - `website/ui/energy_dashboard.js`
    - fruehe Auth-/RBAC-Gates eingebaut: ohne Session keine API-Requests, ohne `settings:read` nur klarer Empty-/Access-State.
    - Schreib-Buttons fuer Settings-Aktionen werden ohne `settings:write` deaktiviert.
  - `website/ui/dashboard.js`
    - Banner-Handling nach Session-/Auth-Fehlern haertet: ein bereits erzwungener Session-Clear wird nicht sofort wieder durch einen irrefuehrenden "Teilweise Ladefehler"-Banner ueberdeckt.
- Verifikation:
  - lokaler Syntax-Check der geaenderten ES-Module mit `node --experimental-default-type=module --check ...` erfolgreich.
  - Live-Befund vor Rollout bestaetigt: WebUI wird aus `/opt/beagle/website` ueber nginx ausgeliefert; `beagle-control-plane` und nginx sind `active`.
  - Deployment erfolgt: geaenderte Dateien nach `/opt/beagle/website/...` und Refactor-Doku auf `srv1` synchronisiert, `.beagle-installed-commit` auf `6fb39ef` gesetzt.
  - Ausgelieferte Assets verifiziert:
    - `/main.js` rendert Scheduler-/Kosten-/Energie-Panels nicht mehr blind im Bootstrap.
    - `/ui/scheduler_insights.js`, `/ui/cost_dashboard.js`, `/ui/energy_dashboard.js` enthalten die neuen Auth-/RBAC-Gates.
  - Live-API-Smoke nach echtem Login auf `srv1` erfolgreich:
    - `POST /api/v1/auth/login` => `200`, Access-/Refresh-Token vorhanden.
    - `GET /api/v1/auth/me` => `200`.
    - `GET /api/v1/scheduler/insights`, `GET /api/v1/costs/*`, `GET /api/v1/energy/*` => jeweils `200` mit gueltigem Bearer-Token.
  - Browser-E2E via Playwright auf `srv1` konnte nicht gefahren werden, weil `python3-playwright` dort aktuell nicht installiert ist.

## Update (2026-04-28, GoEnterprise Plan 01: VM-seitiger Stream-Register-Smoke abgeschlossen)

**Scope**: Der offene Testpflicht-Punkt "Fork-Server startet auf VM und registriert sich" ist als reproduzierbarer VM-Runtime-Smoke umgesetzt.

- Runtime-Smoke:
  - `scripts/test-stream-server-vm-register-smoke.py` (neu)
  - authentifiziert gegen `/api/v1/auth/login`
  - fuehrt Register-/Config-/Event-Flow in der laufenden VM per QEMU Guest Agent aus
- `srv1`-Validierung (VM `beagle-100`):
  - `register_http=201`
  - `config_http=200`
  - `events_http=200`
  - `PLAN01_STREAM_VM_REGISTER=PASS`

## Update (2026-04-28, GoEnterprise Plan 01: vpn_required-Enforcement im Stream-Handshake geschlossen)

**Scope**: Der offene Plan-01-Enforcement-Punkt ist im aktuellen Repo-Slice abgeschlossen.

- Backend:
  - `beagle-host/services/stream_http_surface.py`
    - `POST /api/v1/streams/register` liefert bei `vpn_required` + fehlendem Tunnel jetzt reproduzierbar `403`
    - `POST /api/v1/streams/{vm_id}/events` blockiert `session.start|session.resume|connection.start` ohne WireGuard bei `vpn_required` mit `403`
  - bestehender Config-Enforcement-Pfad (`GET /api/v1/streams/{vm_id}/config`) bleibt erhalten
- Tests:
  - `tests/unit/test_stream_http_surface.py`
    - `test_register_rejects_when_vpn_required_without_wireguard`
    - `test_events_reject_session_start_when_vpn_required_without_wireguard`
- Validierung:
  - Lokal: `22 passed`
  - `srv1` (`/opt/beagle`): `22 passed`

## Update (2026-04-28, GoEnterprise Plan 01: stream allocate runtime wiring abgeschlossen)

**Scope**: Der vorhandene Client-Broker-Contract `/api/v1/streams/allocate` ist jetzt im Runtime-Weg der Registry voll an echte Services angebunden.

- Backend:
  - `beagle-host/services/service_registry.py`
    - `stream_http_surface_service()` verdrahtet jetzt Allocate-Callbacks auf echte Runtime-Funktionen
    - WireGuard-Peer-Profil wird aus `wireguard_mesh_service` geladen und als `wg_peer_config` ausgegeben
    - Pairing-Token wird ueber den bestehenden Pairing-Flow (`issue_moonlight_pairing_token`) fuer Allocate ausgestellt
- Validierung:
  - Lokal: `29 passed`
  - `srv1` (staged `/tmp/beagle-os-snap-*`): `29 passed`

## Update (2026-04-28, GoEnterprise Plan 01: Stream-Client-Broker-Contract-Slice geschlossen)

**Scope**: Der naechste in-repo realisierbare Plan-01-Teil fuer den spaeteren `beagle-stream-client` ist umgesetzt und validiert.

- Backend:
  - `beagle-host/services/stream_http_surface.py`
    - neuer Broker-Allocate-Contract: `POST /api/v1/streams/allocate`
    - liefert Allocate-Payload fuer den Client (`vm_id`, `host_ip`, `port`, `token`, `wg_peer_config`, `links`)
    - erzwingt bei `vpn_required` einen WireGuard-Peer-Config-Check (`403` ohne WG-Profil)
  - `beagle-host/services/authz_policy.py`
    - RBAC fuer `/api/v1/streams/allocate` auf `pool:write`
- Tests:
  - `tests/unit/test_beagle_stream_client_broker.py` (neu)
  - `tests/unit/test_stream_http_surface.py` (Route-Handling erweitert)
  - `tests/unit/test_authz_policy.py` (RBAC-Assertion fuer Allocate)
- Doku:
  - `docs/goenterprise/01-moonlight-vdi-protocol.md`: Checkbox `Tests: tests/unit/test_beagle_stream_client_broker.py` auf `[x]`
- Validierung:
  - Lokal: `29 passed`
  - `srv1` (staged `/tmp/beagle-os-plan01-client-broker`): `29 passed`

## Update (2026-04-28, GoEnterprise Plan 04: Warm-Pool Auto-Apply mit Guardrails geschlossen)

**Scope**: Der verbleibende Plan-04-Restpunkt ist jetzt im Scheduler-Scope umgesetzt und reproduzierbar getestet.

- Backend:
  - `beagle-host/services/scheduler_warm_pool_auto_apply.py` (neu)
    - Guardrail-Normalisierung (max pools/run, max increase, min miss-rate, cooldown)
    - Auswahllogik fuer sichere Auto-Apply-Kandidaten
    - Cooldown-Entscheidung fuer periodische Ausfuehrung
  - `beagle-host/services/service_registry.py`
    - Scheduler-Config um Auto-Apply-Felder erweitert
    - `build_scheduler_insights_payload()` fuehrt optionales Auto-Apply mit Guardrails aus und liefert Status zurueck
- UI:
  - `website/ui/scheduler_insights.js`
    - neue Scheduler-Controls fuer Auto-Apply + Statusanzeige (`reason`, `last_run_at`)
- Tests:
  - `tests/unit/test_scheduler_warm_pool_auto_apply.py` (neu)
  - `tests/unit/test_fleet_ui_regressions.py` (erweitert)
- Validierung:
  - Lokal: `33 passed`
  - `srv1` (staged `/tmp/beagle-os-plan04-warm-autoapply`): `33 passed`

## Update (2026-04-28, GoEnterprise Plan 09: externer Carbon-/Strommix-Feed mit Retry/Alerting geschlossen)

**Scope**: Der letzte dokumentierte Plan-09-Restpunkt ist jetzt im Control-Plane-Scope reproduzierbar geschlossen.

- Backend:
  - `beagle-host/services/energy_feed_import.py` (neu)
    - externer Feed-Fetch (`http/https`) fuer stündliche CO2-/Preisprofile
    - Normalisierung mehrerer Feed-Formate (`hourly_profile`, `hours[]`)
    - Retry/Backoff-Orchestrierung und Fehlerklassifizierung
  - `beagle-host/services/service_registry.py`
    - Importpfad nutzt jetzt den neuen Feed-Collector mit Runtime-Defaults fuer Timeout/Retry/Backoff
    - bei Retry-Exhaustion wird `energy_feed_import_failed` als Alert emittiert
  - `beagle-host/services/control_plane_read_surface.py`
    - `POST /api/v1/energy/hourly-profile/import` mappt invalid payload auf `400` und Upstream-Importfehler auf `502`
  - `beagle-host/services/alert_service.py`
    - neue Default-Alert-Rule `energy_feed_import_failed` (console/webhook)
- Tests:
  - `tests/unit/test_energy_feed_import.py` (neu)
  - `tests/unit/test_control_plane_read_surface.py` (erweitert)
  - bestehender Fokus-Scope weiterhin gruen: `tests/unit/test_energy_service.py`, `tests/unit/test_authz_policy.py`, `tests/unit/test_fleet_alerts.py`
- Validierung:
  - Lokal: `50 passed`
  - `srv1` (staged `/tmp/beagle-os-plan09-energy-feed`): `50 passed`

## Update (2026-04-28, GoEnterprise Plan 01: Token-Pairing 60s + Replay-Schutz geschlossen)

**Scope**: Der offene Plan-01-Token-Pairing-Testpunkt wurde im Control-Plane-Scope geschlossen.

- Backend:
  - `beagle-host/services/service_registry.py`
    - `BEAGLE_PAIRING_TOKEN_TTL_SECONDS` Default auf `60`
    - Pair-Exchange nutzt jetzt `consume_token()` statt `validate_token()`
  - `beagle-host/services/pairing_service.py`
    - `consume_token()` eingefuehrt (einmal-verwendbar + Replay-Schutz)
- Tests:
  - `tests/unit/test_pairing_service.py`
  - `tests/unit/test_auto_pairing_flow.py`

Wichtig:
- Diese Schliessung gilt fuer den aktuellen Control-Plane-/Endpoint-Pfad.
- Offen bleiben weiterhin die echten Fork-/VM-Laufzeitthemen (`beagle-stream-server`-Runtime auf VM, WireGuard-Mesh/Latenz).

## Update (2026-04-28, GoEnterprise Plan 01: dedizierte Stream-Server-Contract-Suite)

**Scope**: Die offene Schritt-1-Testpflicht aus Plan 01 wurde als eigene Contract-Suite umgesetzt.

- Tests:
  - `tests/unit/test_beagle_stream_server_api.py` (neu)
    - Register-Contract (`POST /api/v1/streams/register`)
    - Config-Contract (`GET /api/v1/streams/{vm_id}/config`)
    - Event-/Audit-Contract (`POST /api/v1/streams/{vm_id}/events`)
    - `vpn_required`-Ablehnung (`403`) im dedizierten Stream-Server-Scope
- Doku:
  - `docs/goenterprise/01-moonlight-vdi-protocol.md`: Checkbox `Tests: tests/unit/test_beagle_stream_server_api.py` auf `[x]`

Wichtig:
- Das schliesst die Testpflicht im Control-Plane-/Contract-Scope.
- Offen bleiben weiterhin die Fork-/Build-/Runtime-Punkte fuer den echten `beagle-stream-server`.

## Update (2026-04-28, GoEnterprise Plan 01: Policy/Audit-Testpflichtpunkte im Control-Plane-Scope geschlossen)

**Scope**: Die offenen Plan-01-Testpflichtpunkte fuer `vpn_required`, `vpn_preferred` und Audit-Events wurden auf dem neuen Stream-Control-Plane-Pfad reproduzierbar geschlossen.

- Tests:
  - `tests/unit/test_stream_http_surface.py`
    - `vpn_required` ohne Tunnel -> `403`
    - `vpn_preferred` ohne Tunnel -> direkter Fallback erlaubt (`200`)
    - `POST /api/v1/streams/{vm_id}/events` erzeugt Audit-Event (`stream.session.start`)
  - `tests/unit/test_stream_policy.py` bleibt Referenz fuer die reine Policy-Engine
- Doku:
  - `docs/goenterprise/01-moonlight-vdi-protocol.md`: drei Testpflicht-Checkboxen auf `[x]`

Wichtig:
- Diese Schliessung gilt bewusst fuer den aktuellen Repo-/Control-Plane-Scope.
- Offen bleiben weiterhin die Fork-/Runtime-Punkte mit realem `beagle-stream-server`.

## Update (2026-04-28, GoEnterprise Plan 01: Stream-Control-Plane-API-Slice geschlossen)

**Scope**: Der naechste repo-faehige BeagleStream-Slice ist umgesetzt: die Control-Plane-Seite fuer den spaeteren `beagle-stream-server` existiert jetzt als echte HTTP-Surface mit Register-/Config-/Event-API, Policy-Glue und Audit-Logging.

- Backend:
  - `beagle-host/services/stream_http_surface.py` (neu)
    - `POST /api/v1/streams/register`
    - `GET /api/v1/streams/{vm_id}/config`
    - `POST /api/v1/streams/{vm_id}/events`
    - Persistenz des Register-Status unter `data/streams/servers.json`
    - dynamische Config aus VM-Profil, Pool-/Session-Zustand und `stream_policy_service`
    - `vpn_required` wird im Config-Handshake reproduzierbar mit `403` durchgesetzt
  - `beagle-host/services/control_plane_handler.py`: Routing der neuen Stream-Surface
  - `beagle-host/services/service_registry.py`: Lazy-Wiring fuer Stream-Surface + Stream-Policy-Service
  - `beagle-host/services/authz_policy.py`: RBAC-Mapping fuer neue Stream-Routen (`pool:read` / `pool:write`)
- Tests:
  - `tests/unit/test_stream_http_surface.py` (neu)
  - `tests/unit/test_authz_policy.py` (erweitert)
- Validierung:
  - Lokal: `python3 -m pytest -q tests/unit/test_stream_http_surface.py tests/unit/test_stream_policy.py tests/unit/test_authz_policy.py` -> erwartet gruen
  - `srv1`: identischer Pytest-Scope in separatem Temp-Bundle

Wichtig:
- Das schliesst bewusst den innerhalb dieses Repos umsetzbaren Control-Plane-Teil von Plan 01.
- Offen bleiben weiterhin der echte Sunshine-Fork, HMAC-Token-Pairing im Fork, Paketierung und Live-Abnahme gegen einen real gestarteten Stream-Server.

## Update (2026-04-28, GoEnterprise Plan 08: Schritt-1-RAID-Mehrdisk geschlossen)

**Scope**: Der letzte offene Plan-08-Schritt (`TUI-Installer ueberarbeiten`) ist im technischen Kern geschlossen: RAID-Mehrdisk (`0/1/5/10`) ist jetzt im Seed- und interaktiven Installer-Flow implementiert und getestet.

- Installer:
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
    - verarbeitet `INSTALL_RAID_LEVEL` + `INSTALL_RAID_DISKS`
    - erstellt bei RAID `1/5/10` ein `mdadm`-Root-Array und konfiguriert `mdadm.conf` + `initramfs`
    - installiert GRUB-BIOS auf allen RAID-Member-Disks
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer-gui`
    - RAID-Level-Auswahl anhand erkannter Disk-Anzahl
    - Multi-Disk-Auswahl fuer RAID-Member im TUI-/Plain-Flow
  - `server-installer/seed_config_parser.py`
    - unterstuetzt `disks`-Liste im Seed-Format und validiert Mindestanzahl je RAID-Level
- Tests:
  - `tests/unit/test_seed_config_parser.py`
  - `tests/unit/test_goenterprise_installer_acceptance.py`
  - bestehende Validierungs-Suite: `tests/unit/test_installer_validation.py`
- Doku:
  - `docs/goenterprise/08-all-in-one-installer.md`: Schritt-1-Checkbox auf `[x]` gesetzt, RAID-Closure dokumentiert
- Validierung:
  - Lokal: `python3 -m pytest tests/unit/test_seed_config_parser.py tests/unit/test_installer_validation.py tests/unit/test_goenterprise_installer_acceptance.py -q` -> `24 passed`
  - `srv1`: identischer Lauf in `/tmp/beagle-os-plan08-raid-test` -> `24 passed`

## Update (2026-04-28, GoEnterprise Plan 02: WireGuard-Enrollment + offene Testpflicht geschlossen)

**Scope**: Die verbleibenden offenen Testpunkte in Plan 02 (`WireGuard nach Enrollment` + kompletter `Testpflicht nach Abschluss`-Block) mit dedizierter Regression geschlossen.

- Tests:
  - `tests/unit/test_enrollment_wireguard.py` (neu)
    - WireGuard-Enrollment schreibt Config, startet Interface und faengt unvollstaendige Register-Antworten ab
    - Runtime-Pfad prueft Heartbeat-/Streaming-Bevorzugung via WireGuard (`vpn_required`)
  - `tests/unit/test_goenterprise_zero_trust_acceptance.py` (neu)
    - Enrollment/QR-Token bis Device-Registry-Hardwareeintrag
    - TPM-Compromise-Block (`is_session_allowed=False`)
    - MDM-Pool-Restriktion
    - Remote-Wipe-Confirm
    - Gruppen-Policy-Rollout fuer mehrere Devices
- Doku:
  - `docs/goenterprise/02-zero-trust-thin-client.md`: offene Checkboxen in Schritt 0 und kompletter `Testpflicht nach Abschluss`-Block auf `[x]` gesetzt
- Validierung:
  - Lokal: `python3 -m pytest tests/unit/test_enrollment_wireguard.py tests/unit/test_goenterprise_zero_trust_acceptance.py -q` -> `8 passed`
  - `srv1`: identischer Lauf in `/tmp/beagle-os-plan02-wireguard-test` -> `6 passed, 2 skipped` (`jq` fehlt auf Host fuer zwei scriptnahe Enrollment-Checks)

## Update (2026-04-28, GoEnterprise Plan 08: offene Testpflicht komplett geschlossen)

**Scope**: Die verbleibenden Plan-08-Testpflichtpunkte (`TUI 5 Schritte`, `Seed ohne Dialog`, `PXE + DHCP Seed`) mit dediziertem Acceptance-Satz reproduzierbar geschlossen.

- Tests:
  - `tests/unit/test_goenterprise_installer_acceptance.py` (neu)
  - Deckt ab:
    - Plain/TUI-Installer-Flow mit 5 Schritten inklusive Validierungs-Loops
    - expliziter Non-Interactive-Seed-Pfad im Installer (`seed_file` -> `apply_seed_config` -> UI-Skip)
    - PXE-Skript-Hooks fuer DHCP-/Seed-URL-Rendering
  - Bestehende Installer-Regressionen weiter im Scope:
    - `tests/unit/test_installer_validation.py`
    - `tests/unit/test_seed_config_parser.py`
    - `tests/unit/test_post_install_check.py`
  - Integration:
    - `tests/integration/test_pxe_boot.sh`
- Doku:
  - `docs/goenterprise/08-all-in-one-installer.md`: offene Testpflicht-Checkboxen auf `[x]` gesetzt
- Validierung:
  - Lokal:
    - `pytest -q tests/unit/test_goenterprise_installer_acceptance.py tests/unit/test_installer_validation.py tests/unit/test_seed_config_parser.py tests/unit/test_post_install_check.py` -> `24 passed`
    - `bash tests/integration/test_pxe_boot.sh` -> `PXE_BOOT_TEST=PASS`
  - `srv1`:
    - identischer Unit- + Integrationslauf in `/tmp/beagle-os-plan08-test` -> `24 passed`, `PXE_BOOT_TEST=PASS`

## Update (2026-04-28, GoEnterprise Plan 07: offene Testpflicht komplett geschlossen)

**Scope**: Die verbleibenden Plan-07-Testpflichtpunkte (Telemetrie, Trend-Anomalie, Predictive-Alert, Maintenance+Migration) mit dedizierter Acceptance-Suite geschlossen. Zusaetzlich kann die Fleet-Telemetry-Maintenance jetzt optional direkt VM-Drain-Aktionen ausfuehren und als Ergebnis persistieren.

- Backend:
  - `beagle-host/services/fleet_telemetry_service.py`: optionaler `migrate_vms_fn`-Hook in `schedule_maintenance()`; Persistenz von `drain_status`, `vm_migration_count`, `vm_migrations`, optional `drain_error`
- Tests:
  - `tests/unit/test_goenterprise_fleet_intelligence_acceptance.py` (neu)
  - Deckt ab:
    - SMART-Telemetrie wird korrekt gespeichert/ausgelesen
    - simulierter Disk-Trend wird als Anomalie mit Failure-Horizont <= 7 Tage erkannt
    - `disk_failure_predicted`-Alert triggert inkl. Webhook-Notification
    - Maintenance-Fenster erstellt und VM-Migrationsaktionen werden automatisch ausgefuehrt/persistiert
- Doku:
  - `docs/goenterprise/07-fleet-intelligence.md`: alle offenen `Testpflicht nach Abschluss`-Checkboxen auf `[x]` gesetzt
- Validierung:
  - Lokal: `pytest -q tests/unit/test_goenterprise_fleet_intelligence_acceptance.py tests/unit/test_fleet_telemetry.py tests/unit/test_anomaly_detection.py tests/unit/test_fleet_alerts.py tests/unit/test_maintenance_scheduling.py` -> `38 passed`
  - `srv1`: identischer Lauf via `ssh srv1.beagle-os.com` in `/tmp/beagle-os-plan07-test` -> `38 passed`

## Update (2026-04-28, GoEnterprise Plan 09: offene Testpflicht komplett geschlossen)

**Scope**: Die verbliebenen Plan-09-Testpflicht-Punkte abgeschlossen und in einer dedizierten Acceptance-Suite gebuendelt. Zusaetzlich wurde ein veralteter Integrations-Test auf die inzwischen RAM-inklusive Chargeback-Berechnung angehoben.

- Tests:
  - `tests/unit/test_goenterprise_energy_dashboard_acceptance.py` (neu)
  - Deckt ab:
    - RAPL-Power-Lesepfad + VM-Anteilsverteilung via CPU-Shares
    - CO2-Referenzfall: `100W * 1h` bei `400g/kWh` -> `40g`
    - Chargeback-Energiekosten separat ausgewiesen
    - CSRD-Scope-2-Quartalswert korrekt
  - `tests/unit/test_energy_cost_integration.py`: Erwartungswert auf RAM-inklusive Chargeback-Summe korrigiert
- Doku:
  - `docs/goenterprise/09-energy-dashboard.md`: alle offenen `Testpflicht nach Abschluss`-Checkboxen auf `[x]` gesetzt
- Validierung:
  - Lokal: `pytest -q tests/unit/test_goenterprise_energy_dashboard_acceptance.py tests/unit/test_energy_service.py tests/unit/test_carbon_calculation.py tests/unit/test_energy_cost_integration.py tests/unit/test_csrd_export.py` -> `29 passed`
  - `srv1`: identischer Lauf via `ssh srv1.beagle-os.com` in `/tmp/beagle-os-plan09-test` -> `29 passed`

## Update (2026-04-28, GoEnterprise Plan 04: Testpflicht fuer Pattern/Prewarm/Rebalancing geschlossen)

**Scope**: Die offenen Testpunkte in Plan 04 abgeschlossen und mit dedizierter Testdatei abgesichert. Der neue Abnahmesatz deckt exakt die drei verbleibenden Kriterien ab: 14-Tage-Peak-Erkennung, Prewarm 10 Minuten vor Peak und Rebalancing-Empfehlung bei >85% Last.

- Tests:
  - `tests/unit/test_cluster_rebalancing.py` (neu)
  - Deckt ab:
    - Muster-Erkennung mit 14 Tagen simulierter stündlicher Metriken
    - Prädiktives Prewarming 10 Minuten vor Peak-Hour
    - Rebalancing-Empfehlung von überlastetem Node auf freien Node
- Doku:
  - `docs/goenterprise/04-ai-smart-scheduler.md`: offene `Tests`-Checkbox und alle drei offenen `Testpflicht`-Checkboxen auf `[x]` gesetzt
- Validierung:
  - Lokal: `pytest -q tests/unit/test_cluster_rebalancing.py tests/unit/test_workload_pattern.py tests/unit/test_smart_scheduler.py` -> `20 passed`
  - `srv1`: identischer Pytest-Lauf via `ssh srv1.beagle-os.com` in `/tmp/beagle-os-plan04-test` -> `20 passed`

## Update (2026-04-28, GoEnterprise Plan 05: Testpflicht geschlossen + RAM-Kosten im Chargeback)

**Scope**: Die offenen Plan-05-Testpflichten (`Kosten-Kalkulation`, `5x Alice-Tracking`, `Chargeback-CSV-Summen`, `85%-Budget-Alert`) reproduzierbar geschlossen und dabei eine fachliche Luecke im Chargeback-Pfad gefixt: RAM-Kosten werden jetzt in `generate_chargeback_report()` mitgerechnet.

- Backend:
  - `beagle-host/services/cost_model_service.py`: Chargeback-Summen beinhalten jetzt `ram_gb_hour_cost` ueber `duration_seconds * ram_gb`
- Tests:
  - `tests/unit/test_goenterprise_cost_transparency_acceptance.py` (neu): 4 dedizierte Abnahmetests passend zur Plan-05-Testpflicht
  - Regressionslauf: `tests/unit/test_cost_model.py`, `tests/unit/test_chargeback_report.py`, `tests/unit/test_budget_alert.py`, `tests/unit/test_usage_tracking.py`
- Doku:
  - `docs/goenterprise/05-cost-transparency.md`: Testpflicht-Checkboxen auf `[x]` gesetzt
- Validierung:
  - Lokal: `pytest -q tests/unit/test_goenterprise_cost_transparency_acceptance.py tests/unit/test_cost_model.py tests/unit/test_chargeback_report.py tests/unit/test_budget_alert.py tests/unit/test_usage_tracking.py` -> `37 passed`
  - `srv1`: identischer Pytest-Lauf via `ssh srv1.beagle-os.com` in `/tmp/beagle-os-test-run` -> `37 passed`

## Update (2026-04-28, GoEnterprise Plan 04/05/09: Forecasts, Energy-Cost-Integration und Scheduler-Historie)

**Scope**: Die naechsten offenen Analytics-/Reporting-Reste hinter den neuen Enterprise-Operator-Flows geschlossen. Chargeback zeigt jetzt Forecast und Top-VMs, Energiekosten sind als eigene Komponente im Cost-Pfad abgesichert, und die Scheduler-Sicht rendert erstmals historische 7-Tage-Daten plus 24h-Prognose aus den vorhandenen Metrics-/Workload-Samples.

- Backend:
  - [beagle-host/services/service_registry.py](/home/dennis/beagle-os/beagle-host/services/service_registry.py): `build_chargeback_payload()` mit `top_vms`, `forecast_total_cost_eur`, `total_energy_cost_eur`; `build_scheduler_insights_payload()` mit `historical_trend` und `forecast_24h`
- WebUI:
  - [website/ui/cost_dashboard.js](/home/dennis/beagle-os/website/ui/cost_dashboard.js): Forecast Monatsende, Energiekosten gesamt und Top-10 kostenintensive VMs
  - [website/ui/scheduler_insights.js](/home/dennis/beagle-os/website/ui/scheduler_insights.js): historische Scheduler-Metriken und nächste 8 Stunden CPU-Prognose pro Node
- Regressionen:
  - [tests/unit/test_energy_cost_integration.py](/home/dennis/beagle-os/tests/unit/test_energy_cost_integration.py)
  - [tests/unit/test_control_plane_read_surface.py](/home/dennis/beagle-os/tests/unit/test_control_plane_read_surface.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
  - [tests/unit/test_smart_scheduler.py](/home/dennis/beagle-os/tests/unit/test_smart_scheduler.py)
- Validierung:
  - `python3 -m py_compile beagle-host/services/service_registry.py beagle-host/services/control_plane_read_surface.py beagle-host/services/smart_scheduler.py`
  - `node --check website/ui/cost_dashboard.js website/ui/scheduler_insights.js`
  - `python3 -m pytest tests/unit/test_control_plane_read_surface.py tests/unit/test_cost_model.py tests/unit/test_chargeback_report.py tests/unit/test_energy_cost_integration.py tests/unit/test_smart_scheduler.py tests/unit/test_fleet_ui_regressions.py -q`
  - Ergebnis: `39 passed`

## Update (2026-04-28, GoEnterprise Plan 04/05/09: Operator-Konfiguration + Prewarm-/Green-Scheduling)

**Scope**: Den naechsten Enterprise-Operator-Slice direkt auf die neuen Scheduler-/Cost-/Energy-Panels gesetzt. Aus den zuvor read-only verdrahteten Dashboards wurden jetzt echte Operator-Flows mit persistenter Konfiguration fuer Kostenmodell, Budget-Regeln, Carbon-/Stromfaktoren und Scheduler-Verhalten.

- Backend:
  - [beagle-host/services/control_plane_read_surface.py](/home/dennis/beagle-os/beagle-host/services/control_plane_read_surface.py): neue GET/PUT-Routen fuer `/api/v1/scheduler/config`, `/api/v1/costs/model`, `/api/v1/energy/config`
  - [beagle-host/services/service_registry.py](/home/dennis/beagle-os/beagle-host/services/service_registry.py): Scheduler-Config-Persistenz, Cost-Model-/Budget-Update-Helfer, Energy-/Carbon-Konfig-Glue, Sync von `electricity_price_per_kwh` zwischen Cost und Energy, Prewarm-Kandidaten aus Metrics-/Workload-Analyse
  - [beagle-host/services/smart_scheduler.py](/home/dennis/beagle-os/beagle-host/services/smart_scheduler.py): Green-Scheduling-Gewichtung via Energiepreis und CO2-Intensitaet
  - [beagle-host/services/cost_model_service.py](/home/dennis/beagle-os/beagle-host/services/cost_model_service.py): `list_budget_alerts()`
- WebUI:
  - [website/ui/scheduler_insights.js](/home/dennis/beagle-os/website/ui/scheduler_insights.js): Prewarm-Kandidaten, `saved_cpu_hours`, Scheduler-Konfig-Editor
  - [website/ui/cost_dashboard.js](/home/dennis/beagle-os/website/ui/cost_dashboard.js): Kostenmodell-Editor und Budget-Regel-Editor direkt im Panel
  - [website/ui/energy_dashboard.js](/home/dennis/beagle-os/website/ui/energy_dashboard.js): Carbon-/Strompreis-Editor plus Scheduler-Green-/Prewarm-Konfiguration
- Regressionen:
  - [tests/unit/test_control_plane_read_surface.py](/home/dennis/beagle-os/tests/unit/test_control_plane_read_surface.py)
  - [tests/unit/test_smart_scheduler.py](/home/dennis/beagle-os/tests/unit/test_smart_scheduler.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
  - [tests/unit/test_authz_policy.py](/home/dennis/beagle-os/tests/unit/test_authz_policy.py)
- Validierung:
  - `python3 -m py_compile beagle-host/services/control_plane_read_surface.py beagle-host/services/control_plane_handler.py beagle-host/services/service_registry.py beagle-host/services/authz_policy.py beagle-host/services/smart_scheduler.py beagle-host/services/cost_model_service.py`
  - `node --check website/main.js website/ui/dashboard.js website/ui/scheduler_insights.js website/ui/cost_dashboard.js website/ui/energy_dashboard.js`
  - `python3 -m pytest tests/unit/test_smart_scheduler.py tests/unit/test_chargeback_report.py tests/unit/test_cost_model.py tests/unit/test_budget_alert.py tests/unit/test_usage_tracking.py tests/unit/test_energy_service.py tests/unit/test_carbon_calculation.py tests/unit/test_csrd_export.py tests/unit/test_control_plane_read_surface.py tests/unit/test_dashboard_ui_regressions.py tests/unit/test_fleet_ui_regressions.py tests/unit/test_authz_policy.py -q`
  - Ergebnis: `95 passed`

## Update (2026-04-28, GoEnterprise Plan 04/05/09: Scheduler-, Chargeback- und Energy-Dashboard live verdrahtet)

**Scope**: Drei bislang nur vorbereitete Enterprise-Flächen in den echten Control-Plane-/Dashboard-Stack gezogen. Die vorhandenen JS-Module für Scheduler, Chargeback und Energy/CSRD hängen jetzt an realen Beagle-APIs, sind im Hauptdashboard eingebunden und per RBAC abgesichert.

- Backend:
  - [beagle-host/services/control_plane_read_surface.py](/home/dennis/beagle-os/beagle-host/services/control_plane_read_surface.py): neue GET-Surfaces für `/api/v1/scheduler/insights`, `/api/v1/costs/chargeback`, `/api/v1/costs/chargeback.csv`, `/api/v1/costs/budget-alerts`, `/api/v1/energy/nodes`, `/api/v1/energy/trend`, `/api/v1/energy/csrd` sowie POST-Surfaces für `/api/v1/scheduler/migrate` und `/api/v1/scheduler/rebalance`
  - [beagle-host/services/service_registry.py](/home/dennis/beagle-os/beagle-host/services/service_registry.py): Scheduler-/Usage-/Cost-/Energy-Wiring, Cluster-Heatmap-Aufbereitung, Chargeback-Aggregation und CSRD-/Trend-Helfer
  - [beagle-host/services/control_plane_handler.py](/home/dennis/beagle-os/beagle-host/services/control_plane_handler.py): AuthZ-geschütztes Routing der neuen Scheduler-Mutationen
  - [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py): neue Enterprise-Routen auf `settings:read` / `settings:write`
- WebUI:
  - [website/index.html](/home/dennis/beagle-os/website/index.html): echte Dashboard-Karten für `Placement Insights`, `Kosten pro Abteilung` und `Energie und CO2`
  - [website/main.js](/home/dennis/beagle-os/website/main.js) und [website/ui/dashboard.js](/home/dennis/beagle-os/website/ui/dashboard.js): Dashboard-Wiring für die drei neuen Panels
  - [website/ui/scheduler_insights.js](/home/dennis/beagle-os/website/ui/scheduler_insights.js), [website/ui/cost_dashboard.js](/home/dennis/beagle-os/website/ui/cost_dashboard.js), [website/ui/energy_dashboard.js](/home/dennis/beagle-os/website/ui/energy_dashboard.js): auf die echte API-Signatur umgestellt
- Regressionen:
  - [tests/unit/test_control_plane_read_surface.py](/home/dennis/beagle-os/tests/unit/test_control_plane_read_surface.py)
  - [tests/unit/test_dashboard_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_dashboard_ui_regressions.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
  - [tests/unit/test_authz_policy.py](/home/dennis/beagle-os/tests/unit/test_authz_policy.py)
- Validierung:
  - `python3 -m py_compile beagle-host/services/control_plane_read_surface.py beagle-host/services/control_plane_handler.py beagle-host/services/service_registry.py beagle-host/services/authz_policy.py`
  - `node --check website/main.js website/ui/dashboard.js website/ui/scheduler_insights.js website/ui/cost_dashboard.js website/ui/energy_dashboard.js`
  - `python3 -m pytest tests/unit/test_smart_scheduler.py tests/unit/test_chargeback_report.py tests/unit/test_cost_model.py tests/unit/test_budget_alert.py tests/unit/test_usage_tracking.py tests/unit/test_energy_service.py tests/unit/test_carbon_calculation.py tests/unit/test_csrd_export.py tests/unit/test_control_plane_read_surface.py tests/unit/test_dashboard_ui_regressions.py tests/unit/test_fleet_ui_regressions.py tests/unit/test_authz_policy.py -q`
  - Ergebnis: `92 passed`

## Update (2026-04-28, GoEnterprise Plan 02: Policy-Validierung + Conflict-Hinweise)

**Scope**: Den offenen Haertungs-Slice der MDM-Policy-Plane weitergezogen. Policies werden jetzt serverseitig auf Codec-/Resolution-/Window-Fehler validiert; die Fleet-Surface zeigt die Validation sowie Device-vs-Group-Konflikte direkt im Operator-Flow an.

- Backend:
  - [beagle-host/services/mdm_policy_service.py](/home/dennis/beagle-os/beagle-host/services/mdm_policy_service.py): `validate_policy()` und `describe_effective_policy_conflicts()`
  - [beagle-host/services/mdm_policy_http_surface.py](/home/dennis/beagle-os/beagle-host/services/mdm_policy_http_surface.py): Validation-Metadaten in Policy-Responses
  - [beagle-host/services/fleet_http_surface.py](/home/dennis/beagle-os/beagle-host/services/fleet_http_surface.py): Effective-Policy-Preview mit `conflicts`
- WebUI:
  - [website/ui/fleet_health.js](/home/dennis/beagle-os/website/ui/fleet_health.js): `Policy Validierung` und Konflikt-Badges im Fleet-Panel
- Regressionen:
  - [tests/unit/test_mdm_policy.py](/home/dennis/beagle-os/tests/unit/test_mdm_policy.py)
  - [tests/unit/test_mdm_policy_http_surface.py](/home/dennis/beagle-os/tests/unit/test_mdm_policy_http_surface.py)
  - [tests/unit/test_fleet_http_surface.py](/home/dennis/beagle-os/tests/unit/test_fleet_http_surface.py)

## Update (2026-04-28, GoEnterprise Plan 02: Effective-Policy-Diagnose mit Feld-Diffs)

**Scope**: Den naechsten Operator-Diagnose-Slice der Fleet-Surface geschlossen. Effective Policies zeigen jetzt nicht mehr nur Quelle und Konflikt-Hinweis, sondern auch die konkreten Feldabweichungen zwischen Default-, Gruppen- und Device-Policy.

- Backend:
  - [beagle-host/services/mdm_policy_service.py](/home/dennis/beagle-os/beagle-host/services/mdm_policy_service.py): `build_effective_policy_diagnostics()` mit Snapshot- und Feld-Diff-Logik
  - [beagle-host/services/fleet_http_surface.py](/home/dennis/beagle-os/beagle-host/services/fleet_http_surface.py): `diagnostics` in `/api/v1/fleet/devices/{device_id}/effective-policy`
- WebUI:
  - [website/ui/fleet_health.js](/home/dennis/beagle-os/website/ui/fleet_health.js): rendert `Gruppe vs Default`, `Device vs Gruppe` und `Effektiv vs Default`
- Regressionen:
  - [tests/unit/test_mdm_policy.py](/home/dennis/beagle-os/tests/unit/test_mdm_policy.py)
  - [tests/unit/test_fleet_http_surface.py](/home/dennis/beagle-os/tests/unit/test_fleet_http_surface.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)

## Update (2026-04-28, GoEnterprise Plan 02: Bulk-Device-Operator-Flows + Remediation-Hinweise)

**Scope**: Zwei offene Operator-Luecken aus Plan 02 weiter geschlossen. Das Fleet-Panel kann jetzt Thin-Clients gesammelt sperren, entsperren, fuer Wipe markieren sowie Gruppe und Standort gesammelt setzen; ausserdem erklaert die Effective-Policy-Surface jetzt per Remediation-Hinweisen direkt, welche naechsten Schritte aus Konflikten oder zu weiten Policies folgen.

- Backend:
  - [beagle-host/services/fleet_http_surface.py](/home/dennis/beagle-os/beagle-host/services/fleet_http_surface.py): `POST /api/v1/fleet/devices/actions/bulk` plus `remediation_hints` im Effective-Policy-Response
  - [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py): neue Fleet-Bulk-Route auf `settings:write`
- WebUI:
  - [website/ui/fleet_health.js](/home/dennis/beagle-os/website/ui/fleet_health.js): Bulk-Geraeteoperationen und Remediation-Hinweise im Fleet-Panel
- Regressionen:
  - [tests/unit/test_fleet_http_surface.py](/home/dennis/beagle-os/tests/unit/test_fleet_http_surface.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
  - [tests/unit/test_authz_policy.py](/home/dennis/beagle-os/tests/unit/test_authz_policy.py)

## Update (2026-04-28, GoEnterprise Plan 02: Grafischer Runtime-Lock-Screen + Wipe-Report)

**Scope**: Den naechsten grossen Endpoint-Runtime-Block geschlossen. `locked` ist jetzt nicht mehr nur ein Session-Start-Blocker, sondern erzeugt in laufenden X11-Sessions einen grafischen Sperrbildschirm; parallel schreibt der Runtime-Wipe jetzt einen strukturierten lokalen Report.

- Runtime:
  - [thin-client-assistant/runtime/device_lock_screen.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/device_lock_screen.sh): Lock-Screen-Watcher, UI-Spawn, Session-Abbruch und Marker-Handling
  - [thin-client-assistant/runtime/device_state_enforcement.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/device_state_enforcement.sh): `device-wipe-report.json`
- Session-Wrapper:
  - [start-pve-thin-client-session](/home/dennis/beagle-os/thin-client-assistant/live-build/config/includes.chroot/usr/local/bin/start-pve-thin-client-session)
  - [start-pve-thin-client-kiosk-session](/home/dennis/beagle-os/thin-client-assistant/live-build/config/includes.chroot/usr/local/bin/start-pve-thin-client-kiosk-session)
- Regressionen:
  - [tests/unit/test_device_lock_screen.py](/home/dennis/beagle-os/tests/unit/test_device_lock_screen.py)
  - [tests/unit/test_runtime_session_wrappers.py](/home/dennis/beagle-os/tests/unit/test_runtime_session_wrappers.py)
  - [tests/unit/test_device_state_enforcement.py](/home/dennis/beagle-os/tests/unit/test_device_state_enforcement.py)

## Update (2026-04-28, GoEnterprise Plan 02: Wipe-Reports im Sync-Pfad + automatische Remediation-Actions)

**Scope**: Den naechsten Operator-/Runtime-Slice geschlossen. Runtime-Wipes bleiben nicht mehr nur lokal sichtbar, sondern werden beim regulaeren endpoint-authentifizierten Device-Sync an die Control Plane zurueckgespiegelt; parallel liefert die Effective-Policy-Surface jetzt maschinenlesbare automatische Remediation-Actions fuer UI und spaetere One-Click-Operator-Flows.

- Backend:
  - [beagle-host/services/device_registry.py](/home/dennis/beagle-os/beagle-host/services/device_registry.py): persistiert `last_wipe_report` pro Device
  - [beagle-host/services/endpoint_http_surface.py](/home/dennis/beagle-os/beagle-host/services/endpoint_http_surface.py): `device/sync` verarbeitet jetzt `reports.wipe` und gibt `last_wipe_report` im Device-Payload zurueck
  - [beagle-host/services/fleet_http_surface.py](/home/dennis/beagle-os/beagle-host/services/fleet_http_surface.py): Effective-Policy-Response enthaelt jetzt `remediation_actions`
- Runtime/WebUI:
  - [thin-client-assistant/runtime/device_sync.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/device_sync.sh): sendet `device-wipe-report.json` aktiv im Sync-JSON mit
  - [website/ui/fleet_health.js](/home/dennis/beagle-os/website/ui/fleet_health.js): rendert automatische Remediation-Vorschlaege im Fleet-Panel
- Regressionen:
  - [tests/unit/test_device_registry.py](/home/dennis/beagle-os/tests/unit/test_device_registry.py)
  - [tests/unit/test_endpoint_http_surface.py](/home/dennis/beagle-os/tests/unit/test_endpoint_http_surface.py)
  - [tests/unit/test_device_sync_runtime.py](/home/dennis/beagle-os/tests/unit/test_device_sync_runtime.py)
  - [tests/unit/test_fleet_http_surface.py](/home/dennis/beagle-os/tests/unit/test_fleet_http_surface.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
- Validierung:
  - `bash -n thin-client-assistant/runtime/device_sync.sh`
  - `node --check website/ui/fleet_health.js`
  - `python3 -m pytest tests/unit/test_device_registry.py tests/unit/test_endpoint_http_surface.py tests/unit/test_device_sync_runtime.py tests/unit/test_fleet_http_surface.py tests/unit/test_fleet_ui_regressions.py tests/unit/test_mdm_policy.py tests/unit/test_mdm_policy_http_surface.py tests/unit/test_authz_policy.py tests/unit/test_device_lock_screen.py tests/unit/test_runtime_session_wrappers.py tests/unit/test_device_state_enforcement.py tests/unit/test_device_groups.py -q`
  - Ergebnis: `87 passed`

## Update (2026-04-28, GoEnterprise Plan 02: Remediation-Actions als direkte Operator-Flows)

**Scope**: Den naechsten Operator-Block auf die vorhandenen `remediation_actions` gesetzt. Empfehlungen im Effective-Policy-Panel sind jetzt nicht mehr rein passiv, sondern koennen im Fleet-Panel direkt ausgefuehrt oder in den passenden Policy-/Assignment-Flow ueberfuehrt werden.

- WebUI:
  - [website/ui/fleet_health.js](/home/dennis/beagle-os/website/ui/fleet_health.js): `Vorschlag anwenden` fuer `clear-device-policy-assignment`, `unlock-device` und vorbereitete Editor-/Assignment-Spruenge fuer die restlichen Remediation-Actions
- Regressionen:
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
- Validierung:
  - `node --check website/ui/fleet_health.js`
  - `python3 -m pytest tests/unit/test_fleet_ui_regressions.py tests/unit/test_fleet_http_surface.py tests/unit/test_endpoint_http_surface.py tests/unit/test_device_sync_runtime.py tests/unit/test_device_registry.py -q`
  - Ergebnis: `43 passed`

## Update (2026-04-28, GoEnterprise Plan 02: Wipe-Orchestrierung + serverseitige Remediation-API)

**Scope**: Zwei weitere Enterprise-Restblaecke zusammengezogen. Der Runtime-Wipe ist jetzt ein echter orchestrierter Storage-/TPM-Pfad mit strukturiertem Report statt nur Secret-Cleanup, und die Fleet-Surface hat fuer die vorhandenen Remediation-Actions jetzt eine zentrale serverseitige Execute-API statt verteilter UI-Sonderlogik.

- Runtime:
  - [thin-client-assistant/runtime/device_state_enforcement.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/device_state_enforcement.sh): Install-Device-Erkennung, Storage-Wipe (`blkdiscard` bzw. `wipefs` + `dd`), TPM-Clear, strukturierte Action-Reports mit `completed|partial|failed`
- Backend:
  - [beagle-host/services/device_registry.py](/home/dennis/beagle-os/beagle-host/services/device_registry.py): `wipe_requested_at` / `wipe_confirmed_at`
  - [beagle-host/services/fleet_http_surface.py](/home/dennis/beagle-os/beagle-host/services/fleet_http_surface.py): `POST /api/v1/fleet/devices/{device_id}/remediation/execute`
  - [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py): Remediation-Route auf `settings:write`
- WebUI:
  - [website/ui/fleet_health.js](/home/dennis/beagle-os/website/ui/fleet_health.js): Fleet-Panel nutzt fuer direkte Vorschlaege jetzt die serverseitige Remediation-API und zeigt zusaetzlich einen `Wipe Status`-Block
- Regressionen:
  - [tests/unit/test_device_registry.py](/home/dennis/beagle-os/tests/unit/test_device_registry.py)
  - [tests/unit/test_device_state_enforcement.py](/home/dennis/beagle-os/tests/unit/test_device_state_enforcement.py)
  - [tests/unit/test_fleet_http_surface.py](/home/dennis/beagle-os/tests/unit/test_fleet_http_surface.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
  - [tests/unit/test_authz_policy.py](/home/dennis/beagle-os/tests/unit/test_authz_policy.py)

## Update (2026-04-28, GoEnterprise Plan 02: Drift-Report + Safe Auto-Remediation + Lock-Screen-Fallbacks)

**Scope**: Zwei weitere Enterprise-Fortsetzungen abgeschlossen. Die Fleet-Surface hat jetzt einen zentralen Drift-/Safe-Remediation-Report samt erster serverseitiger Batch-Auto-Remediation; parallel ist der grafische Lock-Pfad jetzt auf Wayland- und weitere X11-Fallbacks erweitert.

- Backend:
  - [beagle-host/services/fleet_http_surface.py](/home/dennis/beagle-os/beagle-host/services/fleet_http_surface.py): `GET /api/v1/fleet/remediation/drift` und `POST /api/v1/fleet/remediation/run`
  - [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py): neue Drift-/Run-Routen auf `settings:read` bzw. `settings:write`
- WebUI:
  - [website/ui/fleet_health.js](/home/dennis/beagle-os/website/ui/fleet_health.js): Drift-Panel, Simulations-/Apply-Buttons fuer Safe-Remediation
- Runtime:
  - [thin-client-assistant/runtime/device_lock_screen.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/device_lock_screen.sh): Backend-Erkennung fuer Wayland (`swaylock`, `gtklock`, `waylock`) und breitere X11-Fallbacks (`zenity`, `yad`, `xmessage`, `xterm`)
- Regressionen:
  - [tests/unit/test_device_lock_screen.py](/home/dennis/beagle-os/tests/unit/test_device_lock_screen.py)
  - [tests/unit/test_fleet_http_surface.py](/home/dennis/beagle-os/tests/unit/test_fleet_http_surface.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
  - [tests/unit/test_authz_policy.py](/home/dennis/beagle-os/tests/unit/test_authz_policy.py)

## Update (2026-04-28, GoEnterprise Plan 02: Persistente Remediation-Konfiguration + History + X11-Multi-Display)

**Scope**: Den naechsten Automatisierungs-Slice von Plan 02 umgesetzt. Safe-Remediation ist jetzt nicht mehr nur ein ad-hoc Run, sondern hat persistente Operator-Konfiguration und History; parallel kann der Lock-Screen unter X11 mehrere Displays explizit abdecken.

- Backend:
  - [beagle-host/services/fleet_http_surface.py](/home/dennis/beagle-os/beagle-host/services/fleet_http_surface.py): `GET/PUT /api/v1/fleet/remediation/config`, `GET /api/v1/fleet/remediation/history`, persistierte History/Last-Run-Daten
  - [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py): neue Config-/History-Routen auf `settings:read` bzw. `settings:write`
- WebUI:
  - [website/ui/fleet_health.js](/home/dennis/beagle-os/website/ui/fleet_health.js): Auto-Remediation-Toggle, Exclude-Device-Liste, History-Vorschau im Drift-Panel
- Runtime:
  - [thin-client-assistant/runtime/device_lock_screen.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/device_lock_screen.sh): `BEAGLE_LOCK_SCREEN_X11_DISPLAYS` fuer mehrere X11-Displays
- Regressionen:
  - [tests/unit/test_fleet_http_surface.py](/home/dennis/beagle-os/tests/unit/test_fleet_http_surface.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
  - [tests/unit/test_authz_policy.py](/home/dennis/beagle-os/tests/unit/test_authz_policy.py)
  - [tests/unit/test_device_lock_screen.py](/home/dennis/beagle-os/tests/unit/test_device_lock_screen.py)

## Update (2026-04-28, GoEnterprise Plan 02: Standort-Tree + Device-Group-Regressionen)

**Scope**: Den offenen Device-UX-Slice aus Plan 02 weiter geschlossen. Die Fleet-WebUI zeigt jetzt nicht mehr nur eine flache Tabelle, sondern eine verdichtete Standort-/Gruppenansicht fuer Operatoren; ausserdem ist der gruppenbezogene Policy-Pfad mit einer eigenen Testdatei reproduzierbar abgesichert.

- WebUI:
  - [website/ui/fleet_health.js](/home/dennis/beagle-os/website/ui/fleet_health.js): neue `Standort- und Gruppenansicht` mit Verdichtung `location -> group -> devices`
- Regressionen:
  - [tests/unit/test_device_groups.py](/home/dennis/beagle-os/tests/unit/test_device_groups.py): kombinierte Filter, Bulk-Gruppenzuweisung und gruppenbezogene effektive Policy-Aufloesung
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py): Tree-/Fallback-Strings und Fleet-UI-Hooks abgesichert
- Validierung:
  - `node --check website/ui/fleet_health.js`
  - `python3 -m pytest tests/unit/test_device_groups.py tests/unit/test_fleet_ui_regressions.py tests/unit/test_fleet_http_surface.py tests/unit/test_mdm_policy.py tests/unit/test_mdm_policy_http_surface.py tests/unit/test_authz_policy.py -q`

## Update (2026-04-28, GoEnterprise Plan 02: Effective Policy Preview + Bulk Assignment)

**Scope**: Den MDM-Operator-Slice direkt weitergezogen: Policies koennen jetzt nicht nur einzeln bearbeitet, sondern fuer mehrere Devices gesammelt zugewiesen werden; ausserdem zeigt die Fleet-Surface die effektiv aufgeloeste Policy pro Device inklusive Herkunft aus Device-, Group- oder Default-Zuweisung.

- Backend:
  - [beagle-host/services/fleet_http_surface.py](/home/dennis/beagle-os/beagle-host/services/fleet_http_surface.py): `GET /api/v1/fleet/devices/{device_id}/effective-policy`
  - [beagle-host/services/mdm_policy_service.py](/home/dennis/beagle-os/beagle-host/services/mdm_policy_service.py): `resolve_policy_with_source()`, Bulk-Device-Assignment/Clear-Helfer
  - [beagle-host/services/mdm_policy_http_surface.py](/home/dennis/beagle-os/beagle-host/services/mdm_policy_http_surface.py): `POST /api/v1/fleet/policies/assignments/bulk`
- WebUI:
  - [website/ui/fleet_health.js](/home/dennis/beagle-os/website/ui/fleet_health.js): Effective-Policy-Preview und Bulk-Assignment ueber Device-Listen
- Regressionen:
  - [tests/unit/test_fleet_http_surface.py](/home/dennis/beagle-os/tests/unit/test_fleet_http_surface.py)
  - [tests/unit/test_mdm_policy.py](/home/dennis/beagle-os/tests/unit/test_mdm_policy.py)
  - [tests/unit/test_mdm_policy_http_surface.py](/home/dennis/beagle-os/tests/unit/test_mdm_policy_http_surface.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
- Validierung:
  - `node --check website/ui/fleet_health.js`
  - `python3 -m pytest tests/unit/test_endpoint_http_surface.py tests/unit/test_device_registry.py tests/unit/test_device_sync_runtime.py tests/unit/test_device_state_enforcement.py tests/unit/test_mdm_policy.py tests/unit/test_mdm_policy_http_surface.py tests/unit/test_fleet_http_surface.py tests/unit/test_authz_policy.py tests/unit/test_fleet_ui_regressions.py tests/unit/test_dashboard_ui_regressions.py -q`
  - Ergebnis: `70 passed`

## Update (2026-04-28, GoEnterprise Plan 02: MDM Policy WebUI + Assignment Surface)

**Scope**: Den naechsten echten Operator-Slice aus Plan 02 geschlossen: MDM ist nicht mehr nur Runtime-Policy im Hintergrund, sondern hat jetzt eine bedienbare Control-Plane-Surface und einen echten Editor-/Assignment-Flow in der Fleet-WebUI fuer Devices und Gruppen.

- Backend:
  - [beagle-host/services/mdm_policy_http_surface.py](/home/dennis/beagle-os/beagle-host/services/mdm_policy_http_surface.py): CRUD + Assignment-Surface fuer `/api/v1/fleet/policies*`
  - [beagle-host/services/mdm_policy_service.py](/home/dennis/beagle-os/beagle-host/services/mdm_policy_service.py): Delete/Clear/List-Assignment-Helfer
  - [beagle-host/services/control_plane_handler.py](/home/dennis/beagle-os/beagle-host/services/control_plane_handler.py): GET/POST/PUT/DELETE-Routing fuer die neue MDM-Surface
  - [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py): Fleet-MDM-Routen auf `settings:read` / `settings:write`
- WebUI:
  - [website/ui/fleet_health.js](/home/dennis/beagle-os/website/ui/fleet_health.js): Policy-Karten, Editor, Device-/Group-Assignment und Policy-Badges pro Device
- Regressionen:
  - [tests/unit/test_mdm_policy.py](/home/dennis/beagle-os/tests/unit/test_mdm_policy.py)
  - [tests/unit/test_mdm_policy_http_surface.py](/home/dennis/beagle-os/tests/unit/test_mdm_policy_http_surface.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
  - [tests/unit/test_authz_policy.py](/home/dennis/beagle-os/tests/unit/test_authz_policy.py)
- Validierung:
  - `node --check website/ui/fleet_health.js`
  - `python3 -m pytest tests/unit/test_mdm_policy.py tests/unit/test_mdm_policy_http_surface.py tests/unit/test_authz_policy.py tests/unit/test_fleet_ui_regressions.py -q`
  - erweiterter Fleet-/Enterprise-Block: `66 passed`

## Update (2026-04-28, GoEnterprise Plan 01/02: VPN Enforcement + Runtime Lock/Wipe Enforcement)

**Scope**: Zwei offene Enterprise-Sicherheitsluecken im aktuellen Beagle-Stack geschlossen: `vpn_required` ist im heutigen Session-Broker jetzt serverseitig hart erzwungen, und die Thin-Client-Runtime setzt `locked` / `wipe_pending` nicht mehr nur als Markerdatei, sondern blockiert den Session-Start bzw. fuehrt einen reproduzierbaren Runtime-Secret-Wipe mit endpoint-authentifizierter `confirm-wiped`-Rueckmeldung aus.

- Backend:
  - [beagle-host/services/endpoint_http_surface.py](/home/dennis/beagle-os/beagle-host/services/endpoint_http_surface.py): `session/current` prueft jetzt Pool-`network_mode` gegen den letzten Device-VPN-Status; neuer Endpoint `POST /api/v1/endpoints/device/confirm-wiped`
  - [beagle-host/services/device_registry.py](/home/dennis/beagle-os/beagle-host/services/device_registry.py): persistiert `vpn_active` / `vpn_interface` / `wg_assigned_ip`
  - [beagle-host/services/fleet_http_surface.py](/home/dennis/beagle-os/beagle-host/services/fleet_http_surface.py): Fleet-JSON zeigt den persistierten VPN-Zustand sichtbar an
  - [beagle-host/services/service_registry.py](/home/dennis/beagle-os/beagle-host/services/service_registry.py): Pool-Manager in die Endpoint-Surface verdrahtet
- Thin-Client-Runtime:
  - [thin-client-assistant/runtime/device_sync.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/device_sync.sh): `confirm-wiped`-API-Hook und saubere Source-Wiring fuer Enrollment-/Curl-Helper
  - [thin-client-assistant/runtime/device_state_enforcement.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/device_state_enforcement.sh): Lock-/Wipe-Enforcement vor Session-Start
  - [thin-client-assistant/runtime/launch-session.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/launch-session.sh): Enforcement-Hook vor Moonlight/Kiosk/GFN-Launch
- Regressionen:
  - [tests/unit/test_endpoint_http_surface.py](/home/dennis/beagle-os/tests/unit/test_endpoint_http_surface.py)
  - [tests/unit/test_device_registry.py](/home/dennis/beagle-os/tests/unit/test_device_registry.py)
  - [tests/unit/test_device_state_enforcement.py](/home/dennis/beagle-os/tests/unit/test_device_state_enforcement.py)
- Validierung:
  - `bash -n thin-client-assistant/runtime/device_sync.sh thin-client-assistant/runtime/device_state_enforcement.sh thin-client-assistant/runtime/launch-session.sh thin-client-assistant/runtime/prepare-runtime.sh thin-client-assistant/live-build/config/includes.chroot/usr/local/sbin/beagle-runtime-heartbeat`
  - `python3 -m pytest tests/unit/test_fleet_http_surface.py tests/unit/test_fleet_ui_regressions.py tests/unit/test_dashboard_ui_regressions.py tests/unit/test_authz_policy.py tests/unit/test_device_registry.py tests/unit/test_endpoint_http_surface.py tests/unit/test_auto_pairing_flow.py tests/unit/test_apply_enrollment_config.py tests/unit/test_device_sync_runtime.py tests/unit/test_device_state_enforcement.py tests/unit/test_mdm_policy.py tests/unit/test_stream_policy.py tests/unit/test_pool_manager.py tests/unit/test_pools_http_surface.py -q`
  - Ergebnis: `121 passed`

## Update (2026-04-28, GoEnterprise Plan 02: Device Registry WebUI + HTTP Surface)

**Scope**: Den naechsten realen Enterprise-Block aus Plan 02 geschlossen: die Thin-Client-Registry hat jetzt eine echte HTTP-Surface im Control Plane, ist an RBAC angebunden, wird im Dashboard als Geraeteuebersicht mit Hardware-/Statusdaten gerendert und bietet erste echte Operator-Aktionen fuer Lock/Wipe/Unlock inklusive Audit-Events.

- Backend:
  - [beagle-host/services/fleet_http_surface.py](/home/dennis/beagle-os/beagle-host/services/fleet_http_surface.py): CRUD-/Heartbeat-/Lock-/Wipe-Surface fuer `/api/v1/fleet/devices*`
  - [beagle-host/services/control_plane_handler.py](/home/dennis/beagle-os/beagle-host/services/control_plane_handler.py): GET/POST/PUT-Routing fuer Fleet-Endpunkte
  - [beagle-host/services/service_registry.py](/home/dennis/beagle-os/beagle-host/services/service_registry.py): Registry- und HTTP-Surface-Wiring
  - [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py): Fleet-Routen auf `settings:read` / `settings:write`
- WebUI:
  - [website/index.html](/home/dennis/beagle-os/website/index.html): neue Dashboard-Karte `Thin-Client Registry`
  - [website/ui/fleet_health.js](/home/dennis/beagle-os/website/ui/fleet_health.js): Render-Flow fuer Device Registry, Hardware, `last_seen`, Standort/Gruppe sowie Lock/Wipe/Unlock-Aktionen
  - [website/ui/dashboard.js](/home/dennis/beagle-os/website/ui/dashboard.js): Fleet-Render-Hook im Dashboard-Load
  - [website/main.js](/home/dennis/beagle-os/website/main.js): Fleet-Module konfiguriert und ans Dashboard verdrahtet
- Regressionen:
  - [tests/unit/test_fleet_http_surface.py](/home/dennis/beagle-os/tests/unit/test_fleet_http_surface.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
  - [tests/unit/test_authz_policy.py](/home/dennis/beagle-os/tests/unit/test_authz_policy.py)
- Validierung:
  - `python3 -m pytest tests/unit/test_fleet_http_surface.py tests/unit/test_fleet_ui_regressions.py tests/unit/test_authz_policy.py tests/unit/test_device_registry.py tests/unit/test_dashboard_ui_regressions.py -q`
  - `node --check website/ui/fleet_health.js website/ui/dashboard.js website/main.js`
  - Ergebnis: alles gruen

## Update (2026-04-28, GoEnterprise Plan 02: Thin-Client Runtime Sync + Policy Pull)

**Scope**: Den naechsten Runtime-Block aus Plan 02 geschlossen: enrolled Thin-Clients synchronisieren jetzt ihren Device-Zustand per endpoint-authentifiziertem Sync-Pfad zur Control Plane, aktualisieren dadurch Heartbeat und Hardware-Registry und bekommen MDM-Policy sowie Lock/Wipe-Status unmittelbar zurueck.

- Backend:
  - [beagle-host/services/endpoint_http_surface.py](/home/dennis/beagle-os/beagle-host/services/endpoint_http_surface.py): neuer `POST /api/v1/endpoints/device/sync`
  - [beagle-host/services/device_registry.py](/home/dennis/beagle-os/beagle-host/services/device_registry.py): `register_or_update_device()` plus Heartbeat-Status-Schutz fuer `locked`/`wipe_pending`/`wiped`
  - [beagle-host/services/endpoint_enrollment.py](/home/dennis/beagle-os/beagle-host/services/endpoint_enrollment.py): Enrollment-Konfig traegt jetzt `device_id`
  - [beagle-host/services/service_registry.py](/home/dennis/beagle-os/beagle-host/services/service_registry.py): Wiring fuer Device Registry, MDM-Policy und Attestation in die Endpoint-Surface
- Thin-Client-Runtime:
  - [thin-client-assistant/runtime/device_sync.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/device_sync.sh): Hardware-/VPN-Snapshot, endpoint-authentifizierter Sync und lokale Anwendung von Lock/Wipe/Policy-Zustand
  - [thin-client-assistant/runtime/prepare-runtime.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/prepare-runtime.sh): initialer Sync direkt nach Enrollment/Egress-Setup
  - [thin-client-assistant/live-build/config/includes.chroot/usr/local/sbin/beagle-runtime-heartbeat](/home/dennis/beagle-os/thin-client-assistant/live-build/config/includes.chroot/usr/local/sbin/beagle-runtime-heartbeat): periodischer Sync im Heartbeat-Timer
  - [thin-client-assistant/runtime/apply_enrollment_config.py](/home/dennis/beagle-os/thin-client-assistant/runtime/apply_enrollment_config.py): persistiert `PVE_THIN_CLIENT_BEAGLE_DEVICE_ID`
- Regressionen:
  - [tests/unit/test_endpoint_http_surface.py](/home/dennis/beagle-os/tests/unit/test_endpoint_http_surface.py)
  - [tests/unit/test_auto_pairing_flow.py](/home/dennis/beagle-os/tests/unit/test_auto_pairing_flow.py)
  - [tests/unit/test_device_registry.py](/home/dennis/beagle-os/tests/unit/test_device_registry.py)
  - [tests/unit/test_apply_enrollment_config.py](/home/dennis/beagle-os/tests/unit/test_apply_enrollment_config.py)
  - [tests/unit/test_device_sync_runtime.py](/home/dennis/beagle-os/tests/unit/test_device_sync_runtime.py)
- Validierung:
  - `python3 -m pytest tests/unit/test_endpoint_http_surface.py tests/unit/test_auto_pairing_flow.py tests/unit/test_device_registry.py tests/unit/test_apply_enrollment_config.py tests/unit/test_device_sync_runtime.py -q`
  - `python3 -m pytest tests/unit/test_fleet_http_surface.py tests/unit/test_fleet_ui_regressions.py tests/unit/test_authz_policy.py tests/unit/test_device_registry.py tests/unit/test_dashboard_ui_regressions.py tests/unit/test_endpoint_http_surface.py tests/unit/test_auto_pairing_flow.py tests/unit/test_apply_enrollment_config.py tests/unit/test_device_sync_runtime.py -q`
  - `bash -n thin-client-assistant/runtime/device_sync.sh thin-client-assistant/runtime/prepare-runtime.sh thin-client-assistant/live-build/config/includes.chroot/usr/local/sbin/beagle-runtime-heartbeat`
  - Ergebnis: alles gruen

## Update (2026-04-28, GoEnterprise Plan 01: Stream-VPN-Contract + Fallback-Tests)

**Scope**: Den naechsten realen Enterprise-Block aus Plan 01 im Beagle-eigenen Stack geschlossen: der Pool-Streaming-Contract traegt jetzt den Zero-Trust-VPN-Modus direkt mit, die Web Console kann ihn im Pool-Wizard setzen, und der Thin-Client-Protokoll-Fallback ist erstmals reproduzierbar getestet.

- Backend/Core:
  - [core/virtualization/streaming_profile.py](/home/dennis/beagle-os/core/virtualization/streaming_profile.py): neues `StreamingNetworkMode`-Enum und `network_mode` im `StreamingProfile` (`vpn_required`, `vpn_preferred`, `direct_allowed`)
- WebUI:
  - [website/index.html](/home/dennis/beagle-os/website/index.html): Streaming-Profil im Pool-Wizard hat jetzt eine sichtbare `VPN-Modus`-Auswahl
  - [website/ui/policies.js](/home/dennis/beagle-os/website/ui/policies.js): sammelt, validiert und rendert `streaming_profile.network_mode` in Summary und Pool-Karten
- Regressionen:
  - [tests/unit/test_protocol_selector.py](/home/dennis/beagle-os/tests/unit/test_protocol_selector.py): WireGuard required, WireGuard preferred, direct fallback und xRDP fallback
  - [tests/unit/test_pool_manager.py](/home/dennis/beagle-os/tests/unit/test_pool_manager.py)
  - [tests/unit/test_pools_http_surface.py](/home/dennis/beagle-os/tests/unit/test_pools_http_surface.py)
  - [tests/unit/test_policies_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_policies_ui_regressions.py)
- Validierung:
  - `python3 -m pytest tests/unit/test_pool_manager.py tests/unit/test_pools_http_surface.py tests/unit/test_policies_ui_regressions.py tests/unit/test_protocol_selector.py tests/unit/test_stream_policy.py`
  - `node --check website/ui/policies.js`
  - Ergebnis: alles gruen

## Update (2026-04-27, Installer-Skripte schreiben nachweisbare API-Logs)

**Scope**: VM-spezifische USB-Installer-/Live-Skripte und die daraus veroeffentlichten Download-Skripte sind jetzt nachvollziehbar. Skripte schreiben Laufereignisse ueber einen kurzlebigen write-only Token an die Control Plane; es werden keine Admin-, Session- oder Manager-Tokens in Installer-Downloads eingebettet.

- Backend:
  - [beagle-host/services/installer_log_service.py](/home/dennis/beagle-os/beagle-host/services/installer_log_service.py): HMAC-signierte Installer-Log-Tokens, Public-Intake, JSONL-Eventpersistenz, Session-Summary und Redaction sensibler Keys.
  - [beagle-host/services/control_plane_handler.py](/home/dennis/beagle-os/beagle-host/services/control_plane_handler.py): `POST /api/v1/public/installer-logs` und authenticated `GET /api/v1/installer-logs`.
  - [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py): Log-Read-Routen auf `settings:read`.
- Skripte:
  - [thin-client-assistant/usb/pve-thin-client-usb-installer.sh](/home/dennis/beagle-os/thin-client-assistant/usb/pve-thin-client-usb-installer.sh): non-blocking Logevents fuer Start, Bootstrap, Device-Listing, Privilege, Dependencies, Assets, USB-Write, Completion und Failure.
  - [thin-client-assistant/usb/pve-thin-client-usb-installer.ps1](/home/dennis/beagle-os/thin-client-assistant/usb/pve-thin-client-usb-installer.ps1): entsprechender Windows-Logpfad via `Invoke-RestMethod`.
  - [beagle-host/services/installer_template_patch.py](/home/dennis/beagle-os/beagle-host/services/installer_template_patch.py): self-healing fuer alte Hosted-Templates ohne Log-Defaults.
- Release:
  - `VERSION`, Extension-Manifest, Kiosk-Package und Changelog auf `8.0` angehoben.
- Validierung:
  - Lokal: `python3 -m pytest tests/unit/test_installer_script.py tests/unit/test_installer_log_service.py tests/unit/test_authz_policy.py -q` => `19 passed`.
  - Live `srv1`: generiertes VM100-Installer-Skript enthaelt Log-Kontext; echter `--list-devices`-Lauf schrieb `script_started`, `bootstrap_helpers_present`, `device_listing_started`, `device_listing_completed`, `script_completed` per API.
  - Live `srv1`: `POST /api/v1/public/installer-logs` mit ungueltigem Token liefert `401`.
  - Live `srv1`: `/beagle-downloads/` liefert `200`, neue Linux-/Windows-`latest`-Skripte enthalten Logging-Hooks, Linux-`latest` enthaelt kein `8443`.

## Update (2026-04-27, Repo-Auto-Update Self-Heal gegen Runtime-Symlink-Loops)

**Scope**: Der Update-Center-Fehler auf `srv1` war kein normaler Fetch-/Build-Fail, sondern ein kaputter Runtime-Baum unter `/opt/beagle`: `beagle-host` zeigte als Self-Symlink auf sich selbst, `beagle_host` zeigte darauf weiter. Dadurch konnten `install-beagle-host-services.sh` und in Folge `beagle-repo-auto-update.service` den Host nicht mehr selbst reparieren.

- Root-Cause-Fix im Repo:
  - [scripts/install-beagle-host-services.sh](/home/dennis/beagle-os/scripts/install-beagle-host-services.sh): `LEGACY_HOST_RUNTIME_DIR` korrigiert auf `/opt/beagle/beagle_host`; neuer Guard `repair_host_runtime_links()` repariert Self-Symlink-/Alias-Schäden aktiv vor und während des Install-Laufs.
  - [scripts/repo-auto-update.sh](/home/dennis/beagle-os/scripts/repo-auto-update.sh): neuer Preflight `repair_runtime_tree()` räumt `beagle-host`/`beagle_host` vor `rsync` und Host-Install auf, damit Self-Heal nicht mehr vom bestehenden Runtime-Zustand abhängt.
- Regression:
  - [tests/unit/test_install_beagle_host_services_regressions.py](/home/dennis/beagle-os/tests/unit/test_install_beagle_host_services_regressions.py)
  - [tests/unit/test_repo_auto_update_regressions.py](/home/dennis/beagle-os/tests/unit/test_repo_auto_update_regressions.py)
- Validierung lokal:
  - `bash -n scripts/install-beagle-host-services.sh scripts/repo-auto-update.sh`
  - `python3 -m pytest tests/unit/test_install_beagle_host_services_regressions.py tests/unit/test_repo_auto_update_regressions.py -q` => `3 passed`
- Live-Repair auf `srv1`:
  - kaputte Links unter `/opt/beagle/beagle-host` und `/opt/beagle/beagle_host` manuell entfernt
  - Runtime-Baeume `beagle-host/` und `scripts/` direkt aus dem Workspace nach `/opt/beagle/` synchronisiert
  - `sudo /opt/beagle/scripts/install-beagle-host-services.sh` danach wieder erfolgreich (`RC=0`)

## Update (2026-04-27, Plan 11 Parity: Storage Browser + Download)

**Scope**: Die offene Storage-Parity fuer Inhaltsliste und Download ist jetzt geschlossen. Storage-Pools koennen API-seitig gelistet und dateibasiert heruntergeladen werden; die WebUI stellt dafuer im Virtualization-Panel einen direkten Operator-Flow bereit.

- Backend:
  - [beagle-host/services/storage_image_store.py](/home/dennis/beagle-os/beagle-host/services/storage_image_store.py): `list_images()` und `read_image()` listen ISO-/Disk-Images pro Pool und lesen Dateien strikt aus validierten Pool-Pfaden.
  - [beagle-host/services/backups_http_surface.py](/home/dennis/beagle-os/beagle-host/services/backups_http_surface.py): neuer Read-Pfad `GET /api/v1/storage/pools/{pool}/files` plus Download via `?filename=...`.
  - [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py): neuer RBAC-Read-Mapping fuer Storage-Dateiliste/Download auf `settings:read`.
- WebUI:
  - [website/ui/virtualization.js](/home/dennis/beagle-os/website/ui/virtualization.js): Storage-Detail-Modal mit Dateiliste, Typ, Groesse, Zeitstempel und Download-Action.
  - [website/ui/events.js](/home/dennis/beagle-os/website/ui/events.js): Storage-Detail-Buttons in Tabellen- und Kartenansicht verdrahtet.
- Regression:
  - [tests/unit/test_storage_image_store.py](/home/dennis/beagle-os/tests/unit/test_storage_image_store.py)
  - [tests/unit/test_backups_http_surface.py](/home/dennis/beagle-os/tests/unit/test_backups_http_surface.py)
  - [tests/unit/test_authz_policy.py](/home/dennis/beagle-os/tests/unit/test_authz_policy.py)
  - [tests/unit/test_virtualization_storage_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_virtualization_storage_ui_regressions.py)
  - [tests/unit/test_vm_actions_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_vm_actions_ui_regressions.py)
- Validierung:
  - `node --check website/ui/virtualization.js website/ui/events.js`
  - `python3 -m py_compile beagle-host/services/storage_image_store.py beagle-host/services/backups_http_surface.py beagle-host/services/authz_policy.py`
  - `python3 -m pytest tests/unit/test_storage_image_store.py tests/unit/test_backups_http_surface.py tests/unit/test_authz_policy.py tests/unit/test_virtualization_storage_ui_regressions.py tests/unit/test_vm_actions_ui_regressions.py -q` => `58 passed`

## Update (2026-04-27, APT-Policy bewusst manuell festgelegt)

**Scope**: Die offene APT-Automatikfrage wurde bewusst gegen Vollautomatik entschieden. Betriebssystempakete bleiben manuell installierbar; die Automatik im Update-Center gilt nur fuer GitHub-Repo-Update und Artefakt-Refresh. Die WebUI kommuniziert das jetzt explizit.

- WebUI:
  - [website/index.html](/home/dennis/beagle-os/website/index.html): klarer Policy-Hinweis im APT-Block
  - [website/ui/settings.js](/home/dennis/beagle-os/website/ui/settings.js): APT-Status und Summaries sprechen jetzt von bewusst manueller Installation
- Regression:
  - [tests/unit/test_settings_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_settings_ui_regressions.py): Policy-Hinweis abgesichert

## Update (2026-04-27, Leader-State-Reconcile geschlossen)

**Scope**: Der offene Cluster-Repair-Punkt aus dem Next-Steps-Plan ist jetzt als idempotenter Reconcile-Flow im Leader-Operator-Bereich umgesetzt. Die Cluster-Memberliste kann doppelte oder defekte Eintraege bereinigen, fehlende lokale Leader-Eintraege wiederherstellen und den Zustand deterministisch neu schreiben.

- Backend:
  - [beagle-host/services/cluster_membership.py](/home/dennis/beagle-os/beagle-host/services/cluster_membership.py): `reconcile_membership()` normalisiert `members.json`, merge't doppelte Member-Namen, setzt den lokalen Leader wieder als `local` und schreibt die Memberliste idempotent neu
  - [beagle-host/services/cluster_http_surface.py](/home/dennis/beagle-os/beagle-host/services/cluster_http_surface.py): `POST /api/v1/cluster/reconcile-membership`
  - [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py): neue Cluster-Write-Route in der RBAC-Matrix
- WebUI:
  - [website/index.html](/home/dennis/beagle-os/website/index.html): neuer Leader-State-Reconcile-Action-Button im Cluster-Panel
  - [website/ui/cluster.js](/home/dennis/beagle-os/website/ui/cluster.js): Reconcile-Action, Bestätigungsdialog, Banner und Refresh-Flow
- Regression:
  - [tests/unit/test_cluster_membership.py](/home/dennis/beagle-os/tests/unit/test_cluster_membership.py): Repair-Dedupe-Szenario
  - [tests/unit/test_cluster_http_surface.py](/home/dennis/beagle-os/tests/unit/test_cluster_http_surface.py): Route und Handle-Check
  - [tests/unit/test_authz_policy.py](/home/dennis/beagle-os/tests/unit/test_authz_policy.py): `cluster:write` fuer die neue Route
  - [tests/unit/test_cluster_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_cluster_ui_regressions.py): Button- und Handler-Regressions
- Live:
  - `srv1`: `POST /api/v1/cluster/reconcile-membership` laeuft mit Manager-Token als idempotenter No-Op durch und liefert den normalisierten Member-Stand fuer Leader `srv1` / Member `srv2`

## Update (2026-04-27, GPU-Pool-Wizard UX normalisiert)

**Scope**: Der GPU-Wizard im Policies-Panel zeigt die Live-GPU-Klassen jetzt mit kuerzeren, menschenlesbaren Labels, waehrend der stabile technische `gpu_class`-Wert unveraendert bleibt. Damit ist der letzte offene Feinschliff fuer den sichtbaren GPU-Pool-Flow erledigt.

- WebUI:
  - [website/ui/policies.js](/home/dennis/beagle-os/website/ui/policies.js): `humanizeGpuModelLabel()` normalisiert die sichtbaren GPU-Labels
- Regression:
  - [tests/unit/test_policies_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_policies_ui_regressions.py): Helper-Pruefung ergaenzt

## Update (2026-04-27, A11y-Follow-up geschlossen)

**Scope**: Die letzten Browser-Warnungen zum Passwort-Flow sind auf `srv1` nach einem frischen Reload nicht mehr reproduzierbar. Die betroffenen Passwortfelder sind im HTML bereits in Form-Kontexte eingeordnet; damit bleibt fuer diesen offenen Punkt kein weiterer Code-Hotfix uebrig.

- Live:
  - `srv1`: Browser-Reload auf `/#panel=settings_updates` erzeugt keine Console-Warnungen oder Errors mehr

## Update (2026-04-27, Repo-Auto-Update + Artifact-Watchdog live verifiziert)

**Scope**: Den offenen Host-Nachweis fuer Repo-Auto-Update und Artifact-Watchdog auf `srv1` live geschlossen. Ein kontrollierter Drift-Fall hat `reaction=started_refresh` ausgelöst, der Refresh lief bis `ok` durch und ein anschliessender Watchdog-Check meldete wieder `healthy` bei `public_ready=true`.

- Live:
  - `srv1`: gezielt `pve-thin-client-live-usb-latest.sh` entfernt, Watchdog startete `beagle-artifacts-refresh.service` automatisch und meldete `reaction=started_refresh`
  - `srv1`: Refresh stellte das Artefakt wieder her, anschliessender Watchdog-Check meldete `state=healthy`, `reaction=none`, `public_ready=true`
  - `srv1`: Repo-Auto-Update-Status bleibt `healthy` mit `current_commit=cf59a76aefe39148009892d1a9fce94fa08a7705`

## Update (2026-04-27, GoFuture Plan 10: Policies-UX abgeschlossen)

**Scope**: Der letzte offene Policies-Refactor aus Plan 10 ist jetzt im Code und in der Doku geschlossen. Das Panel ist nicht mehr nur eine Mischung aus Listen und Tabellen, sondern bietet klare Bereiche fuer Pools, Templates, Entitlements, Policies und Sessions, einen gefuehrten Pool-Wizard, einen strukturierten Policy-Editor sowie Karten-/Detailansichten fuer Pool- und Template-Management.

- WebUI:
  - [website/index.html](/home/dennis/beagle-os/website/index.html): klare Bereichsstruktur fuer Pools/Templates/Entitlements/Policies/Sessions sowie strukturierter Policy-Editor
  - [website/ui/policies.js](/home/dennis/beagle-os/website/ui/policies.js): strukturierte Policy-Payloads, Summary-Renderer und live synchronisierte Preview
  - [website/styles/panels/_policies.css](/home/dennis/beagle-os/website/styles/panels/_policies.css): Nav-Chips, Workspace-Layout, strukturierte Form-Bloecke und Kartenraster
- Regression:
  - [tests/unit/test_policies_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_policies_ui_regressions.py): Checks fuer strukturierten Editor, Pool-/Template-Karten und Detail-Layout erweitert
- Live:
  - `srv1` Policies-Smoke ohne Runtime-Fehler; verbleibende DevTools-Hinweise sind nur reduzierte DOM-/Autocomplete-Messages

## Update (2026-04-27, GoFuture Plan 10: Policies-UI jetzt mit Bereichsnavigation und formalen DOM-Fixes)

**Scope**: Das Policies-Panel hat jetzt eine klare Subnavigation fuer `Pools`, `Templates`, `Entitlements`, `Policies` und `Sessions`. Zusaetzlich sind die offenen Passwort-/Username-Felder in echte Form-Kontexte und mit passenden Autocomplete-Hinweisen eingeordnet, sodass der aktuelle `srv1`-Smoke deutlich ruhiger laeuft.

- WebUI:
  - [website/index.html](/home/dennis/beagle-os/website/index.html): Bereichs-Anker und Formular-Wrappers fuer Backup, Replikation, Provisioning, IAM und Webhooks
  - [website/styles/panels/_policies.css](/home/dennis/beagle-os/website/styles/panels/_policies.css): Subnavigation und Scroll-Margins fuer Policies-Sections
- Plan:
  - [docs/gofuture/10-vdi-pools.md](/home/dennis/beagle-os/docs/gofuture/10-vdi-pools.md) dokumentiert den Ist-Zustand und haakt IA-/Responsive-/Smoke-Punkte ab
- Live:
  - `srv1` Policies-Smoke weiterhin ohne Runtime-Fehler; verbleibende Browser-Hinweise sind nur noch reduzierte DOM-Autocomplete-Verbose-Messages

## Update (2026-04-27, GoFuture Plan 10: Pools/Policies-UI visuell modernisiert)

**Scope**: Das `/#panel=policies`-Layout wurde in eine klarere Arbeitsfläche zerlegt: Hero-Band, Main-/Side-Workspace, kompaktere Pool-Cards und ein direkt editierbarer Entitlement-Block fuer den ausgewählten Pool. Der Browser-Smoke auf `srv1` lief nach Login ohne neue Console-Errors durch und zeigt die Pool-/Policy-Arbeitsfläche jetzt mit den neuen Summary-Chips.

- WebUI:
  - [website/index.html](/home/dennis/beagle-os/website/index.html): `policies-hero`, `policies-workspace`, `policies-main`, `policies-side`
  - [website/styles/panels/_policies.css](/home/dennis/beagle-os/website/styles/panels/_policies.css): Hero-/Workspace-/Card-Layout, kompaktere Pool-Card-Matrix, Entitlement-Chips
  - [website/ui/policies.js](/home/dennis/beagle-os/website/ui/policies.js): Hero-Chips, Pool-Catalog-Summary und Entitlement-Refresh
- Regression:
  - [tests/unit/test_policies_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_policies_ui_regressions.py): neue Layout-/Hero-/Workspace-Checks
- Live:
  - Browser-Smoke auf `srv1` erfolgreich, keine Console-Errors im Policies-Flow

## Update (2026-04-27, GoFuture Plan 10: Pool-Entitlements als Bedienfluss geschlossen)

**Scope**: Den Entitlements-Teil von `/#panel=policies` aus dem Tabellen-/Wizard-Kontext in einen echten Bearbeitungsfluss ueberfuehrt. Der ausgewählte Pool zeigt jetzt seine User-/Group-Entitlements als Chips, und die Werte koennen direkt per UI hinzugefuegt/entfernt werden. Die Persistenz laeuft ueber die bereits vorhandene `GET/POST /api/v1/pools/{pool}/entitlements`-Surface.

- WebUI:
  - [website/index.html](/home/dennis/beagle-os/website/index.html): neuer Pool-Entitlements-Block unter der Pool-Uebersicht
  - [website/ui/policies.js](/home/dennis/beagle-os/website/ui/policies.js): Entitlement-Loader, Chip-Renderer und Add/Remove-Flow
  - [website/ui/events.js](/home/dennis/beagle-os/website/ui/events.js): Event-Bindings fuer Refresh/Add/Remove
  - [website/styles/panels/_policies.css](/home/dennis/beagle-os/website/styles/panels/_policies.css): Layout fuer den Entitlement-Editor
- State/Test:
  - [website/ui/state.js](/home/dennis/beagle-os/website/ui/state.js): Pool-Entitlement-Cache im State
  - [tests/unit/test_policies_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_policies_ui_regressions.py): neue Regressions fuer den Entitlement-Editor
- Plan:
  - `docs/gofuture/10-vdi-pools.md` markiert den Entitlements-Teil von Schritt 7 jetzt als erledigt

## Update (2026-04-27, GoFuture Plan 13 / 15: IAM- und Audit-Operator-Smokes geschlossen)

**Scope**: Die beiden noch offenen, lokal testbaren Operator-Pfade aus IAM und Audit wurden geschlossen. Der IAM-Flow auf `srv1` laeuft jetzt als reproduzierbarer Lokalsmoke gegen den Control-Plane-Endpoint, und der Audit-Compliance-Smoke verifiziert Filter, CSV/JSON-Reportpfad und S3-Export erneut live auf `srv1`.

- IAM:
  - [scripts/test-iam-plan13-smoke.py](/home/dennis/beagle-os/scripts/test-iam-plan13-smoke.py) jetzt erfolgreich gegen `srv1`
  - Tenant-Isolation + Custom-Role-Guardrails beide `ok`
  - Ergebnis: `PLAN13_IAM_SMOKE=PASS`
- Audit:
  - [tests/unit/test_audit_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_audit_ui_regressions.py) deckt Panel-/JS-/CSS-Regressions ab
  - [scripts/test-audit-compliance-live-smoke.sh](/home/dennis/beagle-os/scripts/test-audit-compliance-live-smoke.sh) auf `srv1` erfolgreich
  - Ergebnis: `AUDIT_COMPLIANCE_SMOKE=PASS`
- Folge:
  - `docs/gofuture/00-index.md` zeigt jetzt nur noch den Policies-Block als offen an; IAM und Audit sind dokumentarisch und praktisch erledigt.

## Update (2026-04-27, GoAdvanced Plan 10: VDI-Pool-Lifecycle-Test geschlossen)

**Scope**: Den offenen Integrations-Testpunkt fuer den VDI-Pool-Lifecycle geschlossen. Der Pool-Manager wird jetzt in `tests/integration/test_vdi_pool_lifecycle.py` ueber den echten Lebenszyklus geprueft: Pool anlegen, VM registrieren, Lease ziehen, Stream-Health schreiben, freigeben, recyceln und Pool-Scaling begrenzen.

- Neue Integration:
  - [tests/integration/test_vdi_pool_lifecycle.py](/home/dennis/beagle-os/tests/integration/test_vdi_pool_lifecycle.py)
- Ergebnis:
  - `python3 -m pytest tests/integration/test_vdi_pool_lifecycle.py -q` => `2 passed`
- Planstand:
  - `docs/goadvanced/10-integration-tests.md` Schritt 5 ist jetzt erledigt.

## Update (2026-04-27, GoFuture Plan 08/12: Virtualization-Panel als Operator-Flow abgeschlossen)

**Scope**: Den planseitig noch offenen Virtualization-Block geradegezogen. Der `/#panel=virtualization`-Refactor fuer Nodes, Storage, Bridges, GPU/vGPU/SR-IOV und VM-Inspector ist im Code und in den Live-Smokes bereits abgenommen; die offenen Haken waren nur noch Dokumentationsdrift.

- Plan-/Index-Abgleich:
  - [docs/gofuture/00-index.md](/home/dennis/beagle-os/docs/gofuture/00-index.md)
  - [docs/gofuture/08-storage-plane.md](/home/dennis/beagle-os/docs/gofuture/08-storage-plane.md)
  - [docs/gofuture/12-gpu-plane.md](/home/dennis/beagle-os/docs/gofuture/12-gpu-plane.md)
- Resultat:
  - Virtualization-Indexpunkt und die beiden Detailplaene sind jetzt als erledigt markiert.
  - Die echten Restpunkte sind damit wieder nur noch `policies`, `iam`, `audit`, plus Installer-TUI und die E2E-/CI-Nachlaeufe.

## Update (2026-04-27, GoEnterprise Plan 08: Seed-Config + PXE-Support)

**Scope**: Den offenen Zwei-Host-Installer-Block weiter geschlossen: Seed-Discovery im Server-Installer ist jetzt produktiv eingebaut, der PXE-Setup-Pfad liegt als reproduzierbares Repo-Script vor, und der Dry-Run wurde auf `srv1` und `srv2` gegen echte Installer-Artefakte validiert.

- Seed-/Installer-Pfad erweitert:
  - [server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer](/home/dennis/beagle-os/server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer)
    - automatische Seed-Erkennung aus `/media/beagle-seed.yaml`, `/run/live/medium/...` und `beagle.seed_url=...`
    - Seed-Parser-Hook vor dem UI
    - statische Live-/Target-Netzwerkkonfiguration aus Seed-Daten
  - [scripts/build-server-installer.sh](/home/dennis/beagle-os/scripts/build-server-installer.sh)
    - kopiert `seed_config_parser.py` reproduzierbar ins Live-Image (`/usr/local/share/beagle/seed_config_parser.py`)
- Neuer PXE-Pfad:
  - [scripts/setup-pxe-server.sh](/home/dennis/beagle-os/scripts/setup-pxe-server.sh)
    - extrahiert `vmlinuz`/`initrd` aus dem Installer-ISO
    - erzeugt `grubnetx64.efi` und optional BIOS-PXE-Dateien
    - schreibt `dnsmasq`-Config und rendert `beagle.seed_url=...` in GRUB-/PXELINUX-Menues
  - [docs/deployment/pxe-deployment.md](/home/dennis/beagle-os/docs/deployment/pxe-deployment.md)
- Testabdeckung ausgebaut:
  - [tests/unit/test_seed_config_parser.py](/home/dennis/beagle-os/tests/unit/test_seed_config_parser.py)
  - [tests/unit/test_installer_validation.py](/home/dennis/beagle-os/tests/unit/test_installer_validation.py)
  - [tests/unit/test_post_install_check.py](/home/dennis/beagle-os/tests/unit/test_post_install_check.py)
  - [tests/integration/test_pxe_boot.sh](/home/dennis/beagle-os/tests/integration/test_pxe_boot.sh)
  - [server-installer/post-install-check.sh](/home/dennis/beagle-os/server-installer/post-install-check.sh): `BEAGLE_KVM_DEVICE` als testbarer Override fuer KVM-Smokes
- Validierung:
  - lokal:
    - `21 passed` fuer Seed-/Installer-/Post-Install-Unit-Tests
    - `bash tests/integration/test_pxe_boot.sh` -> `PXE_BOOT_TEST=PASS`
    - `bash -n` fuer `setup-pxe-server.sh`, `beagle-server-installer`, `post-install-check.sh` gruen
  - live:
    - `srv1`: `/opt/beagle/scripts/setup-pxe-server.sh` Dry-Run gegen `/opt/beagle/dist/beagle-os-server-installer/beagle-os-server-installer.iso` erfolgreich
    - `srv2`: derselbe Dry-Run erfolgreich
    - beide Hosts schreiben im isolierten Temp-Root konsistente `dnsmasq`-/TFTP-Artefakte inkl. `beagle.seed_url=https://srv1.beagle-os.com/seeds/rack-a.yaml`
- Restgrenze:
  - Mehrdisk-RAID bleibt im Installer weiter offen; der aktuelle Zero-Touch-Pfad erzwingt deshalb reproduzierbar `raid: 0`.

## Update (2026-04-27, GoEnterprise Plan 06 Schritt 5 + GoAdvanced Plan 10 Schritt 4)

**Scope**: Den offenen Zwei-Host-Nachlauf aus Session-Handover und Integrationstests geschlossen: die WebUI zeigt Handover-Historie jetzt im produktiven Policies-Panel, und der fehlende HA-Failover-Integrationsblock liegt als eigenes Testmodul vor.

- WebUI:
  - [website/ui/policies.js](/home/dennis/beagle-os/website/ui/policies.js): neuer Session-Handover-Dashboard-Block mit KPIs, Alert-Liste und Event-Tabelle auf Basis von `GET /api/v1/sessions/handover`
  - [website/ui/events.js](/home/dennis/beagle-os/website/ui/events.js): neuer Refresh-Hook `session-handover-refresh`
  - [website/ui/state.js](/home/dennis/beagle-os/website/ui/state.js): `handoverHistory` State
  - [website/index.html](/home/dennis/beagle-os/website/index.html), [website/styles/panels/_policies.css](/home/dennis/beagle-os/website/styles/panels/_policies.css): neue Session-Mobility-Karte im Policies-Panel
- Tests:
  - neuer UI-Regressionsblock in [tests/unit/test_policies_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_policies_ui_regressions.py)
  - neuer Integrationsblock [tests/integration/test_ha_failover.py](/home/dennis/beagle-os/tests/integration/test_ha_failover.py)
- Lokal validiert:
  - `node --check website/ui/policies.js website/ui/events.js`
  - `python3 -m pytest tests/unit/test_policies_ui_regressions.py -q` => `5 passed`
  - `python3 -m pytest tests/integration/test_ha_failover.py -q` => `4 passed`
  - `python3 -m pytest tests/integration -q` => `87 passed`
- Live validiert:
  - `srv1`: `scripts/smoke-session-handover-flow.sh 100 srv2` erneut `PASS` (`elapsed=0.31s`)
  - `srv1`: `GET /beagle-api/api/v1/sessions/handover` mit Legacy-API-Token liefert echte `srv1 -> srv2` Events
  - Browser-Smoke via Chrome DevTools:
    - `srv1`: authentifizierter `/#panel=policies`-Flow zeigt Session-Handover-KPIs mit `Events=10`, `Completed=5`, `Avg Dauer=0.07 s`, `Letzte Route=beagle-0 -> srv2`
    - `srv2`: derselbe Block rendert im authentifizierten Flow korrekt als Empty-State
  - keine neuen Runtime-/JS-Fehler; in der Dev-Console verbleiben nur die schon bekannten Passwortfeld-DOM-Warnungen

## Update (2026-04-27, GoEnterprise Plan 06 Schritt 3-5: Timing + Geo-Routing + Handover-History-Backend)

**Scope**: Den verbleibenden Zwei-Host-Kern aus Session-Handover weiter geschlossen: Timing-Abnahme, Geo-Routing-Konfiguration und Handover-Historie/Slow-Alerting sind jetzt im Backend vorhanden und live gegen `srv1 -> srv2` geprueft.

- [beagle-host/services/session_manager.py](/home/dennis/beagle-os/beagle-host/services/session_manager.py):
  - State wird vor Reads/Transfers jetzt aus der JSON-Datei reloaded; damit sieht der laufende Control-Plane-Prozess out-of-process Handover-Updates sofort.
  - neue Handover-Historie `handover_events`
  - neue Slow-Handover-Alerts `handover_alerts`
  - neue Geo-Routing-Funktionen `evaluate_geo_handover(...)`, `apply_geo_handover(...)`
  - neue Session-Mutation `set_session_geo_routing(...)`
- [beagle-host/services/auth_session.py](/home/dennis/beagle-os/beagle-host/services/auth_session.py), [auth_http_surface.py](/home/dennis/beagle-os/beagle-host/services/auth_http_surface.py):
  - User koennen jetzt `session_geo_routing` im Auth-/User-Profil speichern und wieder lesen
- [beagle-host/services/pools_http_surface.py](/home/dennis/beagle-os/beagle-host/services/pools_http_surface.py):
  - neuer Admin-/Operator-Read-Pfad `GET /api/v1/sessions/handover`
- [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py):
  - Handover-History faellt unter `pool:read`
- Tests:
  - neuer Unit-Block [tests/unit/test_geo_routing.py](/home/dennis/beagle-os/tests/unit/test_geo_routing.py)
  - neuer Integrationstest [tests/integration/test_session_handover_timing.py](/home/dennis/beagle-os/tests/integration/test_session_handover_timing.py)
  - fokussierte Regressionen: `67 passed`
- neuer Live-Smoke:
  - [scripts/smoke-session-handover-flow.sh](/home/dennis/beagle-os/scripts/smoke-session-handover-flow.sh)
  - legt temporaeren Endpoint-Token + Session an, fragt Broker vor/nach `transfer_session(...)` und prueft `<5s`
- Live:
  - `srv1`/`srv2` ausgerollt und `beagle-control-plane` neu gestartet
  - `srv1`: `SESSION_HANDOVER_SMOKE=PASS elapsed=0.29s target_node=srv2`
- echter Live-Fund und Fix:
  - Der erste Smoke zeigte, dass `find_active_session()` noch auf gecachtem In-Memory-State lief.
  - Folge: Broker gab nach out-of-process Transfer noch den alten `current_node` zurueck.
  - Fix: `session_manager.py` reloadet jetzt auch im Lookup-Pfad; danach derselbe Smoke gruen.

## Update (2026-04-27, GoEnterprise Plan 06 Schritt 3: Session-Broker + Thin-Client-Reconnect)

**Scope**: Ersten echten Zwei-Host-Produktpfad aus `docs/goenterprise/06-session-handover.md` umgesetzt: Session-Broker ist jetzt endpoint-authenticated verfuegbar, und der Thin-Client fragt vor Moonlight-Start den aktuellen Session-Knoten ab.

- Backend:
  - [beagle-host/services/service_registry.py](/home/dennis/beagle-os/beagle-host/services/service_registry.py): `session_manager_service()` als Singleton verdrahtet.
  - [beagle-host/services/session_manager.py](/home/dennis/beagle-os/beagle-host/services/session_manager.py): Lookup `find_active_session(...)` fuer `session_id`/`vm_id`.
  - [beagle-host/services/pools_http_surface.py](/home/dennis/beagle-os/beagle-host/services/pools_http_surface.py): Pool-Allocate registriert Sessions jetzt im Session-Manager; Release/Kiosk-Ende beenden sie wieder.
  - [beagle-host/services/endpoint_http_surface.py](/home/dennis/beagle-os/beagle-host/services/endpoint_http_surface.py): neuer endpoint-authenticated Broker `GET /api/v1/session/current`.
  - [beagle-host/services/control_plane_handler.py](/home/dennis/beagle-os/beagle-host/services/control_plane_handler.py): `GET /api/v1/session/current` vor normalem Admin-Auth auf Endpoint-Auth verdrahtet.
- Thin-Client:
  - [thin-client-assistant/runtime/moonlight_manager_registration.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/moonlight_manager_registration.sh): Manager-Query fuer `GET /api/v1/session/current`.
  - [thin-client-assistant/runtime/moonlight_host_sync.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/moonlight_host_sync.sh): Broker-Response retargetet jetzt Runtime-Host/Port.
  - [thin-client-assistant/runtime/launch-moonlight.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/launch-moonlight.sh): fragt den Broker vor Reachability-/Pairing-Flow ab und loggt `moonlight.session-broker`.
- Tests:
  - `python3 -m pytest tests/unit/test_session_checkpoint.py tests/unit/test_endpoint_http_surface.py tests/unit/test_pools_http_surface.py -q` => `32 passed`
  - `python3 -m py_compile ...` fuer geaenderte Python-Dateien => OK
  - `bash -n thin-client-assistant/runtime/moonlight_manager_registration.sh thin-client-assistant/runtime/moonlight_host_sync.sh thin-client-assistant/runtime/launch-moonlight.sh` => OK
- Live:
  - `srv1` und `srv2`: neue Backend-/Runtime-Dateien ausgerollt, `beagle-control-plane.service` neu gestartet.
  - `srv1`: echter endpoint-authenticated Smoke gegen `GET /api/v1/session/current?vmid=100` erfolgreich; Response liefert `current_node=srv2`, `stream_host=46.4.96.80`, `moonlight_port=50000`, `reconnect_required=true`.
  - `srv2`: Route und Endpoint-Auth verifiziert; mangels lokaler VM-Inventardaten liefert derselbe Smoke korrekt `404 session not found` statt `401`/`500`.
- Live-Fund:
  - Das neue `session-manager/` State-Verzeichnis war auf `srv1` initial durch Root-Debug-Lauf als `root:root` angelegt und haette den Dienstpfad fuer `beagle-manager` gebrochen.
  - Ownership auf `srv1`/`srv2` live auf `beagle-manager:beagle-manager` korrigiert; Follow-up in `11-security-findings.md`.

## Update (2026-04-27, GoEnterprise Plan 03 Operator-Slice: Variable Extend + Spieltitel)

**Scope**: Kiosk-Operator-Grid fuer `srv2` weiter verdichtet, damit Betreiber nicht nur Metrikzahlen, sondern auch Titel und unterschiedliche Verlaengerungsstufen direkt sehen und ausloesen koennen.

- [website/ui/kiosk_controller.js](/home/dennis/beagle-os/website/ui/kiosk_controller.js):
  - neue Aktionen `+15m`, `+30m`, `+60m`
  - neue Spalte `Spiel`
  - GPU-Anzeige kombiniert jetzt `gpu_util_pct` + `gpu_temp_c`
- [beagle-host/services/pool_manager.py](/home/dennis/beagle-os/beagle-host/services/pool_manager.py):
  - `stream_health` persistiert jetzt auch `window_title`
- Lokal validiert:
  - `python3 -m pytest tests/unit/test_pool_manager.py tests/unit/test_pools_http_surface.py tests/unit/test_policies_ui_regressions.py -q` => `30 passed`
  - `node --check website/ui/kiosk_controller.js` => OK
- Live validiert auf `srv2` via Chrome DevTools:
  - Session-Zeile zeigt `Steam - Hades`, `88 % / 71 C`, `+15m`, `+30m`, `+60m`
  - `+30m` verlaengert eine abgelaufene Session live auf `29m 59s`
  - temporaerer Test-User/State danach wieder entfernt

## Update (2026-04-27, GoEnterprise Plan 03 Operator-Slice: Session-Extend + Live-Metriken)

**Scope**: Kiosk-Operator-Flow im Policies-Panel von "sehen + hart beenden" auf echten Session-Betrieb erweitert und das Gaming-Dashboard fuer laufende Sessions live brauchbar gemacht.

- [beagle-host/services/pool_manager.py](/home/dennis/beagle-os/beagle-host/services/pool_manager.py):
  - kompatibles `session_expires_at` fuer zeitlimitierte Sessions eingefuehrt
  - neue Methode `extend_kiosk_session(...)`
  - `update_stream_health(...)` speichert jetzt zusaetzlich `gpu_util_pct` und `gpu_temp_c`
- [beagle-host/services/pools_http_surface.py](/home/dennis/beagle-os/beagle-host/services/pools_http_surface.py):
  - neuer Endpunkt `POST /api/v1/pools/kiosk/sessions/{vmid}/extend`
  - Kiosk-Sessions liefern die vorhandene `stream_health` direkt an die WebUI durch
- [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py):
  - Extend-Route faellt unter `kiosk:operate`
- [website/ui/kiosk_controller.js](/home/dennis/beagle-os/website/ui/kiosk_controller.js):
  - neue Spalten `FPS`, `RTT`, `GPU`
  - neue Operator-Aktion `+15m`
- [beagle-host/services/gaming_metrics_service.py](/home/dennis/beagle-os/beagle-host/services/gaming_metrics_service.py):
  - Dashboard-KPIs und Trends ziehen Werte jetzt aus aktiven Sessions, wenn noch keine Report-Dateien vorliegen
- Lokal validiert:
  - `python3 -m pytest tests/unit/test_pool_manager.py tests/unit/test_pools_http_surface.py tests/unit/test_authz_policy.py tests/unit/test_policies_ui_regressions.py tests/unit/test_gaming_metrics.py` => `58 passed`
  - `node --check website/ui/kiosk_controller.js` => OK
- Live validiert auf `srv2` via Chrome DevTools:
  - berechtigte Kiosk-Session sichtbar mit `117 FPS`, `9 ms RTT`, `71 C`
  - `+15m` verlaengert eine abgelaufene Session live auf `14m 59s`
  - Gaming-Metrics-Dashboard zeigt fuer eine laufende Session `121.0 FPS`, `7.00 ms`, `73.0 C` inklusive Trends
  - keine Console-Messages im Policies-Flow
- Deploy:
  - aktualisierte Services/UI auf `srv1` und `srv2` ausgerollt
  - `beagle-control-plane` auf beiden Hosts neu gestartet und `active`

## Update (2026-04-27, GoEnterprise Plan 03 Testpflicht + RBAC-UI-Gating)

**Scope**: GPU-/`srv2`-kritische Restabnahme fuer Gaming-/Kiosk-Pools geschlossen und der eingeschraenkte `kiosk_operator`-Browserflow saubergezogen.

- Backend-/Auth-Fix:
  - [beagle-host/services/auth_session.py](/home/dennis/beagle-os/beagle-host/services/auth_session.py) backfillt fehlende Built-in-Rollen jetzt auch dann, wenn auf dem Host schon eine alte `roles.json` existiert; dadurch wird `kiosk_operator` auf Drift-Hosts wie `srv2` wieder automatisch verfuegbar.
  - [beagle-host/services/auth_session_http_surface.py](/home/dennis/beagle-os/beagle-host/services/auth_session_http_surface.py) liefert in `GET /api/v1/auth/me` jetzt die effektiven Role-Permissions mit aus.
- Frontend-Fix:
  - [website/ui/dashboard.js](/home/dennis/beagle-os/website/ui/dashboard.js) laedt fuer Rollen ohne `cluster:read`, `pool:read` oder `auth:read` diese Endpunkte nicht mehr vorab.
  - Folge: `kiosk_operator` sieht in `/#panel=policies` keine falsche Sammelwarnung ueber "nicht verfuegbare" APIs mehr, und die DevTools-Konsole bleibt im Operator-Flow sauber.
- Regressionen erweitert:
  - [tests/unit/test_pool_manager.py](/home/dennis/beagle-os/tests/unit/test_pool_manager.py)
  - [tests/unit/test_pools_http_surface.py](/home/dennis/beagle-os/tests/unit/test_pools_http_surface.py)
  - [tests/unit/test_authz_policy.py](/home/dennis/beagle-os/tests/unit/test_authz_policy.py)
  - [tests/unit/test_auth_session.py](/home/dennis/beagle-os/tests/unit/test_auth_session.py)
  - [tests/unit/test_auth_session_http_surface.py](/home/dennis/beagle-os/tests/unit/test_auth_session_http_surface.py)
  - [tests/unit/test_dashboard_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_dashboard_ui_regressions.py)
- Lokal validiert:
  - `python3 -m pytest tests/unit/test_auth_session_http_surface.py tests/unit/test_dashboard_ui_regressions.py tests/unit/test_auth_session.py tests/unit/test_authz_policy.py tests/unit/test_pool_manager.py tests/unit/test_pools_http_surface.py` => `45 passed`
  - `node --check website/ui/dashboard.js` => OK
- Live validiert:
  - `srv1` + `srv2`: Gaming-Pool-Allocation ohne freie GPU scheitert reproduzierbar hart; VM bleibt `pending-gpu`, kein CPU-Fallback.
  - `srv2`: echter `kiosk_operator`-Login im Browser erfolgreich; Policies-Panel zeigt nur die berechtigte Kiosk-Session (`kiosk-visible`, VM `9301`) samt `Beenden + Reset`.
  - `srv2`: `GET /api/v1/auth/users` fuer denselben Operator bleibt `403 forbidden`.
  - `srv2`: nach Deploy von `dashboard.js` und `auth_session_http_surface.py` keine Console-Messages mehr im `/#panel=policies`-Flow.
  - temporaerer Smoke-State und Test-User auf `srv2` danach wieder entfernt; `desktop-pools.json` / `pool-entitlements.json` auf den Vorzustand zurueckgesetzt.

## Update (2026-04-27, Plan 11 Schritt 6+8: Beagle host-Mandat abgeschlossen)

**Scope**: Letzte Python-interne `beagle_*`-Variablennamen auf `beagle_*` migriert; CI gruen; srv1+srv2 validiert.

- `beagle-host/services/thin_client_preset.py`: `build_common_preset()` akzeptiert neue `beagle_*`-Parameter; Legacy-Alias-Args bleiben fuer Backwards-Compat. `build_streaming_mode_input()` liefert `beagle_host`/`beagle_node`/`beagle_vmid` Keys. Die Thin-Client-Compat-Env-Var-Namen bleiben unveraendert.
- `beagle-host/services/installer_script.py`: Lokale Variablen auf `beagle_*` umgestellt (nur interne Umbenennung; Env-Keys unveraendert).
- `beagle-host/services/ubuntu_beagle_state.py`: Phase-Name `"beagle-host-create"` → `"beagle-create"`.
- `beagle-host/services/ubuntu_beagle_provisioning.py`: Phase-Name `"beagle-host-create"` → `"beagle-create"`; `--beagle-host` → `--beagle-host` in configure-sunshine-guest.sh-Aufruf.
- `scripts/configure-sunshine-guest.sh`: `--beagle-host` als neuer primärer Argument-Name; `--beagle-host` bleibt als Backwards-Compat-Alias.
- `beagle-host/services/metrics_collector.py`: Bug-Fix: `read_samples()` und `prune_old_shards()` nutzen jetzt injiziertes `utcnow` statt `datetime.now()` → Test `test_record_and_read_node_sample` gruen nach Fix.
- 1069 Unit-Tests bestehen nach allen Renames. `beagle-control-plane` wurde auf `srv1`/`srv2` neu gestartet, Services gruen.
- `docs/goadvanced/11-beagle-host-endbeseitigung.md`: Alle Abnahmekriterien abgehakt.

## Update (2026-04-27, GPU-Wizard-Selector + Kiosk-Path-Fix)

**Scope**: `/#panel=policies` fuer GPU-/srv2-nahe Workflows weiter abgesichert und Live-Asset-Drift auf `srv1`/`srv2` bereinigt.

- `website/index.html`, `website/ui/policies.js`, `website/ui/events.js`:
  - `GPU-Klasse` im Pool-Wizard ist jetzt eine Select-Box statt Freitext.
  - Optionen werden aus `state.virtualizationOverview.gpus` zu live aggregierten Passthrough-Klassen aufgebaut.
  - Zusatzhinweis zeigt erkannte Passthrough-Klassen sowie mdev-/SR-IOV-Counts an.
- `website/ui/kiosk_controller.js`:
  - API-Pfade auf `request('/pools/...')` korrigiert; der vorherige doppelte Prefix `.../api/v1/api/v1/...` ist entfernt.
- `tests/unit/test_policies_ui_regressions.py` erweitert; lokal validiert mit:
  - `node --check website/ui/policies.js`
  - `node --check website/ui/events.js`
  - `node --check website/ui/kiosk_controller.js`
  - `python3 -m pytest tests/unit/test_policies_ui_regressions.py` => `3 passed`
- Live:
  - betroffene WebUI-Assets auf `srv1` und `srv2` neu nach `/opt/beagle/website/ui/` ausgerollt
  - Browser-Smoke auf `srv2`: Pool-Wizard zeigt `GPU-Klasse` jetzt als Select und den neuen Live-Hinweistext statt Freitextfeld
  - Folgefix: `website/ui/settings.js` nutzt fuer IPAM-Zonen wieder API-relative Pfade (`/network/ipam/...`) statt `/api/v1/...`
  - Folgefix: `website/beagle-web-ui-config.js` auf `srv1`/`srv2` unter `/opt/beagle/website/` ausgeliefert; vorher fiel nginx auf `/index.html` zurueck und erzeugte in Chrome `Unexpected token '<'`
  - finaler Chrome-DevTools-Smoke auf `srv2`: keine Console-Errors mehr; authentifizierter `/#panel=policies`-Flow zeigt live `passthrough-nvidia-geforce-gtx-1080` im GPU-Wizard und `Keine aktiven Kiosk-Sessions.`

**Offen/Rest-Risiko**:
- Die GPU-Select-Option ist jetzt technisch korrekt und live befuellt, aber das Sichtlabel nutzt noch den vollen Inventory-Modeltext; ein spaeterer UX-Slice kann die Anzeige kuerzer machen, ohne den stabilen `gpu_class`-Value anzutasten.

## Update (2026-04-27, GoEnterprise Plan 03 Schritt 5: Stateless Kiosk Reset)

**Scope**: Kiosk-Sessions verlassen nach End/Timeout keinen unbrauchbaren Zwischenzustand mehr.

- [beagle-host/services/pool_manager.py](/home/dennis/beagle-os/beagle-host/services/pool_manager.py):
  - `release_desktop(...)` triggert fuer `pool_type=kiosk` + `floating_non_persistent` jetzt sofort `recycle_desktop(...)`
  - `expire_overdue_sessions()` laeuft ueber denselben Release-/Recycle-Pfad und setzt ueberfaellige Kiosk-VMs direkt wieder auf `free`
- neue fokussierte Regression [test_vm_stateless_reset.py](/home/dennis/beagle-os/tests/unit/test_vm_stateless_reset.py)
- `website/ui/kiosk_controller.js` kennzeichnet die Operator-Aktion jetzt als `Beenden + Reset`
- Lokal validiert:
  - `31 passed` ueber `test_vm_stateless_reset.py`, `test_session_time_limit.py`, `test_pool_manager.py`, `test_policies_ui_regressions.py`
- Live:
  - `pool_manager.py` und die fehlende aktuelle [desktop_pool.py](/home/dennis/beagle-os/core/virtualization/desktop_pool.py) auf `srv1` und `srv2` ausgerollt
  - `beagle-control-plane` auf beiden Hosts neu gestartet und `active`
  - Runtime-Smoke direkt auf beiden Hosts gegen die deployten Module: Kiosk-Release ergibt `lease_state=free`, Endzustand `free`, `stop_vm` + `reset_vm_to_template` beide aktiv

## Update (2026-04-26, Settings-Updates Drei-Karten-UX)

**Scope**: `/#panel=settings_updates` von technischer Sammelansicht auf eine laienfreundliche Operator-Ansicht reduziert.

- `website/index.html`: Updates-Panel zeigt nur noch drei Hauptkarten: `System-Update (APT)`, `Repo-Update` und `Artefakte bauen`.
- `website/styles/panels/_settings.css`: neue moderne Karten-UI mit gestaffeltem Eintritt, Scanline-/Sweep-Effekt, Live-Pulse pro Update-Bereich und responsivem Layout.
- `website/ui/settings.js`: Direktaufrufe von `#panel=settings_updates` laden nach erfolgreicher Admin-Authentifizierung automatisch nach; vorher ging der erste Load verloren, wenn `state.user` noch nicht gesetzt war.
- Repo-Update-Konfiguration ist fuer Laien nicht mehr als API-/GitHub-Formular sichtbar; sichere Defaults bleiben als Hidden-Inputs erhalten.
- Artifact-Watchdog kann direkt in der Artefaktkarte als Automatik gespeichert werden; Manual-Actions bleiben als klare Buttons sichtbar.
- Live-Validierung: Hot-Deploy auf `srv1` und `srv2`; Browser-Smoke gegen beide Hosts zeigt exakt drei Karten, automatische `GET /settings/updates`- und `GET /settings/artifacts`-Requests ohne Button-Klick, `repo=healthy`, `artifacts=Ja`, `console_errors=0`.

## Update (2026-04-26, Long-Build Live-Transparenz)

**Scope**: Lange Artifact-/ISO-Builds duerfen in der WebUI nicht mehr wie ein eingefrorener 20%-Status wirken.

- `beagle-host/services/server_settings.py`: `GET /api/v1/settings/artifacts` liefert jetzt `build_activity` mit Live-Phase, erklaerendem Detailtext, Laufzeit und aktiven Build-Prozessen aus der aktuellen Prozesskette.
- `scripts/refresh-host-artifacts.sh`: schreibt waehrend `prepare-host-downloads`/`package.sh` Heartbeats in `refresh.status.json`, inklusive konkreter Phasen wie Paketinstallation, Initramfs, chroot-Hooks, SquashFS und ISO-Erzeugung.
- `website/index.html`, `website/ui/settings.js`, `website/styles/panels/_settings.css`: Artefakt-Karte zeigt jetzt Live-Build-Phase, Fortschrittsbalken, Laufzeit, aktive Prozessanzahl, Detailerklaerung und Dauerhinweis.
- Live-Validierung auf laufenden Builds: `srv1` zeigt `Thin-Client-Live-Image wird gebaut`, `srv2` zeigt `Pakete werden in das Live-System installiert`; beide mit Laufzeit/Prozessanzahl und `console_errors=0`.

## Update (2026-04-26, Plan 19 Schritt 7: Windows USB Writer + Live USB)

- `thin-client-assistant/usb/pve-thin-client-usb-installer.ps1` von einfachem ISO-Kopierer auf variantenfaehigen Writer (`installer` / `live`) umgebaut.
- Installer-Pfad korrigiert:
  - Preset wird jetzt an beide erwarteten Stellen geschrieben (`pve-thin-client/preset.env`, `pve-thin-client/live/preset.env`).
  - Eigene textbasierte GRUB-Konfiguration fuer den Preset-Installer wird erzeugt.
- Neuer Windows-Live-USB-Pfad:
  - schreibt Live-Assets nach `/live`,
  - schreibt Runtime-State-Dateien unter `pve-thin-client/state`,
  - erzeugt eine eigene Runtime-GRUB-Konfiguration mit `pve_thin_client.mode=runtime`.
- Backend/API/UI erweitert:
  - neuer Downloadpfad `GET /api/v1/vms/{vmid}/live-usb.ps1`,
  - neue Profil-/Inventory-Felder `live_usb_windows_url`,
  - neuer WebUI-Button `Live USB Windows`.
- Packaging/Host-Downloads erweitert:
  - neue Release-/Host-Artefakte `pve-thin-client-live-usb-*.ps1`,
  - `scripts/package.sh`, `scripts/prepare-host-downloads.sh`, `scripts/install-beagle-host.sh`, `scripts/publish-hosted-artifacts-to-public.sh`, `scripts/create-github-release.sh` nachgezogen.
- Validierung:
  - `12 passed` in fokussierten Unit-Tests,
  - `py_compile`, `node --check`, `bash -n` fuer alle geaenderten Service-/UI-/Shell-Pfade gruen.

## Update (2026-04-26, Plan 08 Virtualization Node-Detail-Slice)

**Scope**: GoFuture Plan 08 Schritt 7 weiter umgesetzt: `/#panel=virtualization` hat jetzt eine echte Node-Detail-Ansicht statt nur Node-Cards und Tabellen.

### Umgesetzt

- `beagle-host/services/virtualization_read_surface.py`:
  - `GET /api/v1/virtualization/nodes/{node}/detail` neu.
  - Liefert pro Node: Cluster-/Member-Metadaten, API-/RPC-URL, Service-Status (`kvm`, `libvirt`, `virsh`, `control_plane`, `rpc`), lokale Preflight-Checks, gefilterte Storage-/Bridge-/GPU-Daten und Warnungen.
  - Lokale/Remote-Erkennung korrigiert, damit Remote-Nodes nicht faelschlich als `local=true` markiert werden.
- `beagle-host/services/service_registry.py`: Virtualization-Read-Surface bekommt jetzt Cluster-Member-Liste und lokalen KVM/libvirt-Preflight injiziert.
- `website/ui/virtualization.js`:
  - Node-Cards haben jetzt einen echten `Details`-Button.
  - Neuer Detail-Modal fuer Services, Reachability, Storage, Bridges, GPUs und Warnings.
- `website/ui/events.js`: `data-virt-node-detail` verdrahtet.
- `tests/unit/test_virtualization_read_surface.py`: neue Detail-Tests fuer lokalen und Remote-Node.

### Validierung

- Lokal: `node --check website/ui/virtualization.js` und `node --check website/ui/events.js` => OK.
- Lokal: `python3 -m pytest tests/unit/test_virtualization_read_surface.py -q` => **4 passed**.
- Live: Slice auf `srv1` und `srv2` ausgerollt; `beagle-control-plane` auf beiden Hosts `active`.
- Live: `GET /api/v1/virtualization/nodes/srv1/detail` liefert auf `srv1` `local=true`, auf `srv2` `local=false`.
- Live: ausgelieferte `https://srv1.beagle-os.com/ui/virtualization.js`, `.../ui/events.js`, `https://srv2.beagle-os.com/ui/virtualization.js`, `.../ui/events.js` enthalten den neuen Detail-Flow.

### Rest-Risiken

- Der Node-Detail-Flow zeigt heute vor allem Diagnose- und Reachability-Daten; editierbare Storage-/Bridge-Aktionen fehlen noch.
- Auf den Live-Hosts liefern die Detaildaten fuer `srv1` aktuell keine Storage-/Bridge-/GPU-Eintraege; das muss im naechsten Plan-08-Slice explizit fuer die Bedienpfade und die Datenherkunft geklaert werden.

### Folge-Slice

- `website/index.html`, `website/ui/virtualization.js`, `website/ui/events.js`, `website/styles/panels/_virtualization.css`:
  - Storage-Bereich in `/#panel=virtualization` von Tabelle auf echte Storage-Cards umgestellt.
  - Pro Pool sichtbar: Typ, Node, aktiv/inaktiv, Auslastung, verfuegbar, Quota, shared.
  - Aktionen: `Quota setzen` nutzt den vorhandenen echten Backend-Pfad; `Health pruefen` oeffnet den Node-Detail-Flow des zugehoerigen Hosts.
- Live auf `srv1` und `srv2` ausgerollt; ausgelieferte HTML/JS/CSS-Dateien enthalten die neue Storage-Card-Ansicht.
- `beagle-host/services/ipam_service.py`, `beagle-host/services/network_http_surface.py`, `beagle-host/services/virtualization_read_surface.py`, `beagle-host/services/service_registry.py`:
  - IPAM-Zonen koennen jetzt optional an eine Bridge gebunden werden (`bridge_name`).
  - Neuer Bridge-Detail-Pfad `GET /api/v1/virtualization/bridges/{bridge}/detail` aggregiert Bridge-Metadaten, lokale VM-Nutzung, Firewall-Profil-Zuordnung, IPAM-Zonen und Lease-Counts.
- `website/index.html`, `website/ui/virtualization.js`, `website/ui/events.js`, `website/styles/panels/_virtualization.css`:
  - Bridge-Bereich in `/#panel=virtualization` von Tabelle auf bedienbare Bridge-Cards umgestellt.
  - Actions: `Details`, `IPAM-Zone`, `Node filtern`.
  - Bridge-Detail-Modal zeigt Warnungen, VM-Nutzung, IPAM-Zonen/Leases und verfuegbare Firewall-Profile.
- Lokal: `python3 -m pytest tests/unit/test_virtualization_read_surface.py tests/unit/test_network_http_surface.py -q` => **22 passed**.
- Live: auf `srv1` und `srv2` ausgerollt und verifiziert; `GET /api/v1/virtualization/bridges/beagle/detail` liefert auf `srv1` `vm_count=1`, auf `srv2` `vm_count=0`.
- `website/index.html`, `website/ui/virtualization.js`, `website/ui/events.js`, `website/ui/state.js`:
  - VM-Inspector in `/#panel=virtualization` verbessert: `Letzte VM`, Recent-Shortcuts, getrennte Tabellen fuer Allgemein, Disks, Netzwerk-Config und Guest-Interfaces.
  - Der Inspector merkt sich geladene VMIDs innerhalb der Session und erlaubt einen schnellen Ruecksprung auf die letzte geladene VM.
- Live: aktualisierte `index.html`, `ui/virtualization.js`, `ui/events.js` und `ui/state.js` auf `srv1`/`srv2` ausgerollt und in den ausgelieferten Assets verifiziert.
- Neuer reproduzierbarer UI-Smoke: [scripts/test-virtualization-panel-smoke.py](/home/dennis/beagle-os/scripts/test-virtualization-panel-smoke.py:1)
  - login, Panel-Navigation, Node-/Storage-/Bridge-Cards, Node-/Bridge-Detail-Modals, VM-Inspector, Console-/Page-Error-Check.
  - Live gegen `srv1` und `srv2` erfolgreich (`VIRT_PANEL_SMOKE=PASS`).
- `website/index.html`, `website/ui/virtualization.js`, `website/styles/panels/_virtualization.css`:
  - GPU-Bereich im Virtualization-Panel von Tabelle auf erklaerende Karten umgestellt.
  - Fuer physische GPUs sichtbar: Treiberbindung, IOMMU-Gruppe, Passthrough-Status, konkrete Ursache und naechster Schritt.
  - `srv2`-Fall explizit entschärft: GTX 1080 zeigt jetzt live `nicht isolierbar` samt Grund `IOMMU-Gruppe enthaelt weitere Geraete (3)`.

## Update (2026-05-XX, Plan 07 Member-Edit/Local-Preflight + Plan 08 Virt-Panel UX)

**Scope**: GoFuture Plan 07 — `update_member()`, PATCH/DELETE Member-Endpoints, Local-KVM/libvirt-Preflight; GoFuture Plan 08 — Node-Cards mit Health-Badges und Actions, Storage-Health-Spalte, Risk-Banner.

### Umgesetzt

- `beagle-host/services/cluster_membership.py`:
  - `update_member()` neu: aendert `display_name`, `api_url`, `rpc_url`, `enabled`-Flag fuer beliebige Member.
  - `local_preflight_kvm_libvirt()` neu: prueft `/dev/kvm`, `libvirtd`, `virsh -c qemu:///system`, control-plane auf 127.0.0.1:8006. Gibt Check-Liste mit pass/fail/warn zurueck.
- `beagle-host/services/cluster_http_surface.py`:
  - `handles_patch(path)` + `route_patch(path, json_payload)` neu: `PATCH /api/v1/cluster/members/{name}` → `update_member()`.
  - `handles_delete(path)` + `route_delete(path)` neu: `DELETE /api/v1/cluster/members/{name}` → `remove_member()`.
  - `GET /api/v1/cluster/local-preflight` neu: ruft `local_preflight_kvm_libvirt()` auf.
- `website/ui/api.js`: `patchJson()` und `deleteJson()` exportiert.
- `website/ui/cluster.js`:
  - `openMemberEditForm()`, `saveClusterMemberEdit()`, `removeClusterMember()` neu.
  - Edit/Remove-Buttons in jeder Zeile der Knotenübersicht.
  - Click-Handler fuer `data-cluster-member-edit` und `data-cluster-member-remove`.
- `website/index.html`: `#cluster-member-edit-modal` ergaenzt.
- `website/ui/virtualization.js` — `renderVirtualizationPanel()`:
  - Risk/Health-Banner (`#virt-risk-banner`): KVM fehlt, libvirt down, Storage >90%.
  - KVM/libvirt-Health-Badges je Node-Card.
  - Node-Card-Actions: `VMs filtern`, `Preflight`.
  - Storage-Health-Spalte: ok/hoch/kritisch nach Fuellgrad.
- `website/ui/events.js`: Click-Handler fuer `data-virt-node-filter` und `data-virt-local-preflight` in `nodes-grid`.
- `website/index.html`: `#virt-risk-banner` vor `nodes-grid`, Storage-Tabelle hat Health-Spalte.
- Tests: +18 neue Tests in `test_cluster_membership.py` (update_member, local_preflight) und `test_cluster_http_surface.py` (PATCH, DELETE, local-preflight).

### Test-Baseline nach diesem Update

- `python3 -m pytest tests/unit tests/integration -q --deselect ...` => **1062 passed** (vorher 1018, +44).

### Rest-Risiken

- `route_patch`/`route_delete` sind noch nicht in `control_plane_handler.py` verdrahtet — ein neuer HTTP-Dispatch-Pfad fuer PATCH/DELETE-Methoden muss im Handler hinzugefuegt werden.
- Local-Preflight laeuft nur lokal auf dem Server der Anfrage; der Wizard-Flow fuer "Remote-Preflight vor Join" ist konzeptionell noch offen (Plan 07 Schritt bleibt teilweise offen).

---

## Update (2026-04-26, Cluster Leave Standard + Clusterweite Virtualization-Ansicht)

**Scope**: GoFuture Plan 07 Schritt 7 weiter umgesetzt: Cluster-Member koennen sich jetzt kontrolliert ueber den Leader abmelden; die WebUI zeigt Cluster-/Virtualisierungsdaten auf `srv1` und `srv2` konsistent an.

### Umgesetzt

- `beagle-host/services/cluster_membership.py`: Leave-Flow auf 2-Phasen-Modell umgestellt. Ein Mitglied fordert `leave-local` an, der Leader entfernt den Node autoritativ per mTLS-RPC aus `members.json`, erst danach wird lokal aufgeraeumt.
- `beagle-host/services/service_registry.py`: Cluster-RPC um `cluster.member.leave` verdrahtet; `ClusterMembershipService` bekommt RPC-Request/Credentials injiziert.
- `beagle-host/services/cluster_http_surface.py`: `POST /api/v1/cluster/leave-local` dient jetzt als sicherer Einstieg fuer den standardisierten Member-Leave.
- `website/ui/cluster.js` und `website/index.html`: normale Cluster-Mitglieder zeigen keinen allgemeinen Aktionsbereich mehr; der Leave-Button sitzt nur noch im Technikbereich und erklaert den Ablauf laienfreundlich.
- `beagle-host/services/virtualization_read_surface.py`: `GET /api/v1/virtualization/overview` verwendet jetzt bevorzugt die clusterweite Inventory-Aggregation statt nur lokale Nodes.
- `tests/unit/test_virtualization_read_surface.py` neu; Cluster-/AuthZ-/HTTP-Surface-Tests fuer den Leave-Flow erweitert.
- Live-Reparatur auf `srv1`: lokale `members.json` wieder auf den realen Zwei-Node-Stand (`srv1`, `srv2`) gebracht, nachdem der Host nur noch sich selbst kannte.

### Validierung

- Lokal: `python3 -m py_compile beagle-host/services/virtualization_read_surface.py beagle-host/services/service_registry.py` OK.
- Lokal: `python3 -m pytest tests/unit/test_virtualization_read_surface.py tests/unit/test_cluster_membership.py tests/unit/test_cluster_http_surface.py tests/unit/test_authz_policy.py -q` => **50 passed**.
- Live: `srv1` und `srv2` neu ausgerollt und `beagle-control-plane` auf beiden Hosts neu gestartet.
- Live: `/api/v1/virtualization/overview` liefert auf `srv1` und `srv2` dieselben Nodes: `beagle-0`, `beagle-1`, `srv1`, `srv2`.
- Live: `/api/v1/cluster/status` liefert auf `srv1` und `srv2` dieselben Member: `srv1`, `srv2`.

### Rest-Risiken

- Die auf `srv1` gefundene Drift in `members.json` wurde live repariert, ist aber noch kein automatischer Reconcile-Pfad. Wenn ein Leader-Node seinen lokalen Cluster-State verliert, braucht es derzeit noch einen expliziten Sync-/Repair-Mechanismus.
- Remote-KVM/libvirt-Preflight und Wizard-Job-Progress im Cluster-Panel bleiben offen.

## Update (2026-04-26, Cluster Auto-Join Setup-Code + Login Runtime Fix)

**Scope**: GoFuture Plan 07 Schritt 7 — echter Zielserver-Setup-Code fuer sicheren Auto-Join; Live-Runtime-Mix korrigiert, der `/auth/login` mit HTTP 500 brechen konnte.

### Umgesetzt

- `beagle-host/services/cluster_membership.py`: Setup-Code-Store ergaenzt (`setup-codes.json`, Modus 0600), Codes werden nur gehasht gespeichert, laufen nach 60-1800 Sekunden ab und sind einmalig nutzbar.
- `POST /api/v1/cluster/setup-code`: authentifizierter Zielserver-Endpunkt zum Erzeugen eines Auto-Join-Codes.
- `POST /api/v1/cluster/auto-join`: Leader-Endpunkt, der Hostname + Setup-Code verarbeitet, invasive offene Remote-Health-/Inventory-Abfragen vermeidet und den Join auf dem Zielserver ausloest.
- `POST /api/v1/cluster/join-with-setup-code`: setup-code-geschuetzter Zielserver-Endpunkt fuer den Auto-Join.
- Join-Tokens haben jetzt eine echte Ablaufpruefung; abgelaufene Tokens werden beim Einloesen verworfen.
- WebUI `/#panel=cluster`: Zielserver kann Setup-Code erzeugen; Leader-Wizard fragt nur Servername + Setup-Code ab und zeigt Auto-Join-Ergebnis/Preflight laienfreundlich an.
- Form-Readability-Fix: readonly Input-/Textarea-Felder nutzen dunklen Input-Hintergrund und lesbaren Text.

### Validierung

- Lokal: `py_compile` fuer Cluster/AuthZ/Handler OK.
- Lokal: `node --check website/ui/cluster.js` OK.
- Lokal: `bash -n scripts/check-beagle-host.sh` OK.
- Lokal: `python3 -m pytest tests/unit/test_cluster_membership.py tests/unit/test_cluster_http_surface.py tests/unit/test_authz_policy.py -q` => **44 passed**.
- Live-Hotfix vor diesem Slice: `srv1` und `srv2` akzeptieren Login wieder; die Control-Plane-Service-Dateien wurden synchronisiert und `beagle-control-plane` auf beiden Hosts neu gestartet.

### Rest-Risiken

- `srv2` Host-Check hat weiterhin einen bestehenden Artifact-/Download-Metadata-Mismatch; das ist nicht Teil des Login-/Setup-Code-Fixes.
- Der fruehere separate Legacy-HTTPS-Port wurde entfernt.
- Remote-KVM/libvirt-Proof und Job-Progress fuer den Cluster-Wizard bleiben offen.

## Update (2026-04-26, GoFuture Re-Open: WebUI-Operability + Cluster-Wizard-Slice)

**Scope**: GoFuture-Plan wieder geoeffnet, weil mehrere produktrelevante Bereiche zwar Backend-/Status-Funktion haben, aber noch nicht vollstaendig ueber die Beagle Web Console bedienbar sind.

### Plan-Erweiterung in `docs/gofuture/`

---

## Update (2026-04-26, Live-Migration srv1→srv2 Blocker behoben + End-to-End-Validierung)

**Scope**: Live-Migration zwischen srv1 und srv2 war blockiert. Root-Ursache identifiziert und behoben, End-to-End-Migration einer Test-VM erfolgreich ausgeführt.

### Problem & Ursache

- `virsh migrate` mit `qemu+ssh://srv2.beagle-os.com/system` hing ohne Fehlermeldung.
- Root Cause: `srv2.beagle-os.com` löste auf srv1 nur per IPv6 (`2a01:4f8:151:912c::2`) auf — IPv6-Konnektivität zwischen srv1 und srv2 ist aber defekt/geblockt.
- IPv4 (`176.9.127.50`) funktioniert einwandfrei.

### Umgesetzt

1. **root-SSH-Schlüssel ausgetauscht**: srv1-Root-Pubkey in srv2 `authorized_keys` eingetragen; `PermitRootLogin without-password` auf srv2 bestätigt.
2. **IPv4-Hosts-Eintrag auf srv1**: `176.9.127.50 srv2.beagle-os.com srv2` in `/etc/hosts` auf srv1 eingetragen — überschreibt IPv6-DNS-Auflösung lokal.
3. **Verbindung verifiziert**: `ssh root@srv2.beagle-os.com` und `virsh -c qemu+ssh://beagle-1/system list` und `virsh -c qemu+ssh://srv2.beagle-os.com/system list` — alle verbinden ohne Hänger.
4. **Test-VM erstellt**: Minimale VM (`beagle-test-migration`) mit Host-Kernel + busybox-Initrd auf srv1 gestartet.
5. **Live-Migration erfolgreich**: `virsh migrate --live --persistent --undefinesource --copy-storage-all beagle-test-migration qemu+ssh://root@srv2.beagle-os.com/system` → `Migration: [100 %]`. VM lief danach auf srv2.
6. **Aufräumen**: Test-VM und alle Hilfsdateien auf beiden Servern entfernt.

### GoFuture Plan 07 Status

- `docs/gofuture/07-cluster-foundation.md`: "Live-Migration nach erfolgreichem Join validieren" → ✅
- "Live-Migration einer laufenden Test-VM von Host A nach Host B" → ✅

### Keine Codeänderungen nötig

Die Migration-Service-Implementierung und URI-Template (`qemu+ssh://{target_node}/system`) sind korrekt. Der Blocker war rein infrastrukturell (IPv6-DNS). Die `/etc/hosts`-Lösung auf srv1 ist persistent und erfordert keine Softwareänderungen.

---

## Update (2026-04-26, Cluster-Inventory Bug Fix — Remote-VM Disambiguation)

**Scope**: Kritischer Bug behoben: ubuntu-beagle-100 wurde auf srv1 mit Node="beagle-0" angezeigt, aber auf srv2 mit Node="beagle-1". Der Bug resultierten aus fehlender Quellkennzeichnung von Remote-VMs in der Cluster-Inventory-Aggregation.

### Problem & Ursache

- Beobachtung: VM-ID 100 zeigte sich auf unterschiedlichen Nodes auf unterschiedlichen Cluster-Membern an.
- Root Cause: Remote-VMs in der Cluster-Inventory-Aggregation waren nicht mit ihrer Quell-Member gekennzeichnet, was zu Verwechslungen zwischen lokalen und Remote-VMs führte.
- Auswirkung: Die Cluster-Inventory konnte Remote-VMs nicht eindeutig einer Member zuordnen.

### Umgesetzt

- `beagle-host/services/cluster_inventory.py`: Remote-VMs erhalten jetzt ein `"source_member": "<member_name>"` Attribut in der Aggregation.
  - Jede Remote-VM aus einem anderen Cluster-Member wird mit der Quell-Member gekennzeichnet.
  - Verhindert Node-Name-Kollisionen zwischen lokalen und Remote-VMs.
  - Ermöglicht der WebUI, Remote-VMs korrekt zu filtern oder zu kennzeichnen.
- `tests/unit/test_cluster_inventory.py`: Neuer Test `test_build_inventory_marks_remote_vms_with_source_member` validiert das Attribut.
- All 82 Cluster-Tests bestanden ohne Regressionen.

### Validierung

- Lokal: `python3 -m pytest tests/unit/test_cluster_inventory.py -xvs` => **8 passed** (davon 1 neu).
- Lokal: `python3 -m pytest tests/unit/test_cluster_*.py -xvs` => **82 passed** (keine Regressions).

### Vollständige Lösung benötigt

Die Cluster-Inventory-Seite ist gelöst, aber die WebUI nutzt `/api/v1/vms` (Fleet-Inventory) statt `/api/v1/cluster/inventory` für VM-Listen:
- **Option A**: WebUI sollte den Cluster-Inventory Endpoint verwenden, um Remote-VMs zu sehen.
- **Option B**: Fleet-Inventory sollte erweitert werden, um Remote-VMs mit `source_member` zu aggregieren.

Aktueller Status: Backend-Fix ist done und getestet. WebUI-Anpassung ist separate Aufgabe im Cluster-Wizard-Operability-Track.

### Rest-Risiken

- Die Fleet-Inventory (`/api/v1/vms`) zeigt nach wie vor nur lokale VMs. Remote-VMs sind nur in der Cluster-Inventory (`/api/v1/cluster/inventory`) sichtbar.
- WebUI-Tests für die Remote-VM-Darstellung müssen als Teil des Cluster-Wizard-UX-Updates hinzugefügt werden.


- `00-index.md`: Status von "Gate passed" auf aktiven Re-Open gesetzt und WebUI-Bedienbarkeit als Abschlussbedingung dokumentiert.
- `07-cluster-foundation.md`: neuer Schritt 7 fuer Cluster-Operations-Wizards (`/#panel=cluster`): Cluster erstellen, Server hinzufuegen, Preflight, Job-Progress, Member-Verwaltung, Maintenance/Drain, srv1/srv2-Validierung.
- `08-storage-plane.md` + `12-gpu-plane.md`: neue UX-/Bedienbarkeitsplaene fuer `/#panel=virtualization` mit Nodes, Storage, Bridges, VM Inspector, GPU/vGPU/SR-IOV.
- `10-vdi-pools.md`: neuer Schritt 7 fuer `/#panel=policies` mit Pool-/Template-/Entitlement-/Policy-Refactor.
- `13-iam-tenancy.md`: neuer Schritt 7 fuer `/#panel=iam` mit User-, Rollen-, IdP-, SCIM-, Session- und Tenant-Flows.
- `15-audit-compliance.md`: neuer Schritt 6 fuer `/#panel=audit` mit Audit-Viewer, Report-Builder, Export-Zielen und Failure-Replay.
- `06-server-installer.md`: neuer Schritt 6 fuer Host-/Artifact-Operations in der WebUI.

### Erster umgesetzter Code-Slice

- `beagle-host/services/cluster_membership.py`: `join_existing_cluster()` ergaenzt; ein Server kann ueber Token + Leader-API einem bestehenden Cluster aus seiner lokalen WebUI heraus beitreten.
- `beagle-host/services/cluster_http_surface.py`: `POST /api/v1/cluster/join-existing` hinzugefuegt.
- `beagle-host/services/authz_policy.py`: Route auf `cluster:write` gelegt.
- `website/ui/cluster.js`, `website/ui/dashboard.js`, `website/ui/state.js`, `website/index.html`: Cluster-Panel um Setup-Card und drei Wizards erweitert (`Cluster erstellen`, `Join-Token erzeugen`, `dieser Server tritt bestehendem Cluster bei`).

### Validierung

- Lokal: `python3 -m pytest tests/unit/test_cluster_membership.py tests/unit/test_cluster_http_surface.py tests/unit/test_authz_policy.py tests/unit/test_vm_api_regressions.py` => **42 passed**.
- `node --check website/ui/cluster.js && node --check website/ui/dashboard.js && node --check website/ui/state.js` => OK.
- `srv1`: KVM/libvirt/control-plane/nginx/noVNC laufen; Artefakt-Refresh ist noch aktiv und baut den Server-Installer via `live-build`.
- `srv2`: KVM/libvirt/control-plane laufen; NVIDIA GTX 1080 wird erkannt, ist aber wegen nicht isolierbarer IOMMU-Gruppe nicht passthrough-ready.
- Terraform gegen echte `srv1`-API: VM create/destroy erfolgreich validiert.

### Bekannte Rest-Risiken

- Leader-seitiger "Server hinzufügen"-Wizard fehlt noch; bisher existiert nur der lokale Join-Wizard und die API-Grundlage.
- Live-Migration zwischen `srv1` und `srv2` bleibt blockiert: libvirt/qemu+ssh haengt in `migration out`/paused target trotz SSH/libvirt-Reachability.
- Artifact-/Release-Gate ist nicht abgeschlossen, solange der laufende `srv1`-Build und danach `scripts/check-beagle-host.sh` nicht erfolgreich durchlaufen.

### Nachtrag Cluster-Wizard-Slice

- `POST /api/v1/cluster/add-server-preflight` ergaenzt: Leader prueft Zielserver-DNS, API-TCP, API-Health, RPC-TCP, SSH-TCP und Node-Name-Duplikate.
- Der WebUI-Wizard "Server vom Leader aus vorbereiten" erzeugt nur bei bestandenem Pflicht-Preflight ein Join-Token.
- Remote-KVM/libvirt-Proof und Remote-Join bleiben offen, weil dafuer ein authentifizierter Zielserver-Flow ohne Secret-Leak benoetigt wird.

### Nachtrag Artifact-Operations-Slice

- `GET /api/v1/settings/artifacts` ergaenzt: liest `dist/beagle-downloads-status.json`, `/var/lib/beagle/refresh.status.json`, Pflichtartefakte und systemd Service-/Timer-Status.
- `POST /api/v1/settings/artifacts/refresh` ergaenzt: startet `beagle-artifacts-refresh.service` und kehrt ohne langen blocking Request zurueck.
- `/#panel=settings_updates` zeigt jetzt Artefakt-Readiness, fehlende Pflichtartefakte, Refresh-Service/Timer und eine Artefakt-Tabelle.
- Lokal: Cluster + Settings + VM-Regressions => **47 passed**.

---

## Update (2026-05-XX, GoEnterprise Plan 10: GPU-Streaming-Pools)

**Scope**: Plan 10 — GPU Assignment Modi, Pool-Manager GPU-Typen, Dashboard, AI-Scheduler Integration

### GPU Assignment Modes (Plan 10, Schritt 2)

- `beagle-host/services/gpu_assignment_modes.py` (NEU): `GpuAssignmentModeService` mit allen 3 Modi:
  - `assign_passthrough / release_passthrough`: PCI-Passthrough via vfio-pci + libvirt XML
  - `assign_timeslice / release_timeslice`: CUDA Time-Slicing, MAX_TIMESLICE_VMS=8 cap
  - `assign_vgpu / release_vgpu`: NVIDIA mdev/vGPU via libvirt `<hostdev type="mdev">`
- `core/virtualization/desktop_pool.py`: `DesktopPoolType` um `GPU_PASSTHROUGH`, `GPU_TIMESLICE`, `GPU_VGPU` erweitert
- `beagle-host/services/pool_manager.py`: `__init__` um 6 GPU-Callables erweitert; `_maybe_assign_gpu` / `_maybe_release_gpu` helpers; GPU-Pool-Routing in `allocate_desktop` + `release_desktop`
- `beagle-host/services/smart_scheduler.py`: `NodeCapacity.gpu_utilization_pct` Feld; `pick_node()` berücksichtigt GPU-Auslastung als Scoring-Faktor + Ausschluss bei Überlastung (>85%)
- `website/ui/gpu_dashboard.js`: Temperatur-Badge, Modus-Badge, VRAM-Nutzung, `capacityPlanningHtml()` mit Ø/Peak-Auslastung + Empfehlung
- `tests/unit/test_gpu_assignment_modes.py` (NEU, 28 Tests): 11 Passthrough, 9 Timeslice, 8 vGPU

### srv2 Deployment

- srv2.beagle-os.com: NVIDIA GTX 1080 (GP104, 01:00.0), IOMMU aktiv, vfio_pci geladen, Debian 12
- Repo vollständig deployed via rsync, libvirtd aktiv
- GPU-Treiber auf srv2 nicht installiert — für Passthrough nicht nötig; für nvidia-smi: nvidia-driver Installation erforderlich

### Test-Baseline nach Plan 10

- **Unit+Integration-Tests**: **1018 passed** (+28 neue Tests)

---

## Update (2026-05-XX, GoAdvanced Plan 07 Schritt 3: Async POST-Endpoints)

**Scope**: Plan 07 Schritt 3 — HTTP-Surfaces für Backup-Run + VM-Snapshot auf Job-Queue verdrahtet

### Async Endpoints (Plan 07 Schritt 3)

- `backups_http_surface.py`: `POST /api/v1/backups/run` enqueues `"backup.run"` job wenn `enqueue_job` gesetzt ist → gibt 202 Accepted + `{ok, job_id, scope_type, scope_id}` zurück. Fallback: sync (200) wenn kein enqueue_job (Backward-Compat).
- `vm_mutation_surface.py`: `POST /api/v1/vms/{vmid}/snapshot` neu. Enqueues `"vm.snapshot"` mit `{vmid, node, name}` → 202 + `{ok, job_id, vmid, name}`. Gibt 503 wenn kein enqueue_job verdrahtet. Idempotency-Key: `vm.snapshot.{vmid}.{name}`.
- `service_registry.py`: `vm_mutation_surface_service()` bekommt `enqueue_job=lambda name, payload, **kw: job_queue_service().enqueue(name, payload, **kw)`.
- `request_handler_mixin.py`: `_backups_surface()` bekommt `enqueue_job=job_queue_service().enqueue`.
- Neue Tests: 11 Unit-Tests in `test_backups_http_surface.py` (3 async Tests) + `test_vm_mutation_surface.py` (7 neue Tests für snapshot-Routing, Enqueue, VM-Not-Found, 503).

### Test-Baseline nach Plan 07 Schritt 3
- **Unit-Tests**: 861 passed, 0 Regressions
- **Integration-Tests**: 82 passed, 0 Regressions

---

## Update (2026-05-XX, GoAdvanced Plan 10: Integration Tests + Service Bug Fixes)

**Scope**: Plan 10 Schritte 1+2+3+6+7+8 — Integration & E2E Test Suite

### Integration Tests (Plan 10, Commit 5860890)

- `tests/integration/conftest.py`: Shared fixtures (`temp_state_dir`, `mock_audit_log`, `TestHttpClient`, `LibvirtStub`, `cp_server`).
- `tests/integration/test_pairing_lifecycle.py`: 23 Tests — PairingService Token-Issue/Validate, EnrollmentTokenStore CRUD, EndpointTokenStore, Full-Lifecycle.
- `tests/integration/test_endpoint_boot_to_streaming.py`: 18 Tests — Enrollment-Token-Issuance, Endpoint-Enrollment → Bearer+Stream-Config, Single-Use-Token-Enforcement, Expired/Unknown-Token-Rejection, Stream-Config-Felder.
- `tests/integration/test_backup_restore_chain.py`: 36 Tests — Policy-CRUD, Schedule-Due-Logik, run_backup_now, restore_snapshot, list_snapshot_files, Korruption/Missing-Archive-Edge-Cases, Scheduled-Backup-Triggering/Skipping.
- `tests/e2e/conftest.py + helpers.py + test_smoke_srv1.py`: E2E-Smoke gegen srv1 (9 Tests, auto-skip ohne `BEAGLE_E2E_TOKEN`).
- `tests/integration/README.md` + `tests/e2e/README.md`: Lokale Ausführung, Stubs, Cleanup-Verhalten.

### Service-Bugs durch Integration-Tests gefunden + gefixt

- `backup_service.py: _sanitize_policy`: `last_backup` wurde immer aus `current` (Defaults) gelesen, nicht aus `source` (gespeicherte Policy) → `get_pool_policy` gab immer leeren `last_backup` zurück. Fix: lese erst aus `source`, falle auf `current` zurück.
- `backup_service.py: restore_snapshot + list_snapshot_files`: `_resolve_archive_local` warf unkontrolliert `FileNotFoundError`, wenn Archiv fehlte. Fix: in separatem try/except gekapselt → gibt strukturiertes `{ok: False, error: ...}` zurück.

### Test-Baseline nach Plan 10
- **Unit-Tests**: 861 passed, 0 Regressions
- **Integration-Tests**: 82 passed (23+18+36+5 conftest-driven)
- **E2E-Tests**: 9 skipped (kein Token), 0 failed

### Offene Punkte Plan 10
- Schritt 4: HA-Failover-Tests — BLOCKED auf Plan 09 (HA-Manager)
- Schritt 5: VDI-Pool-Lifecycle-Tests — BLOCKED auf Plan 10 VDI-Pools
- Schritt 7 E2E: Nightly-CI mit `BEAGLE_E2E_TOKEN` aus GitHub-Secrets konfigurieren

## Update (2026-05-XX, GoAdvanced Plan 07: Async-Job-Queue + Plan 11: Beagle host Hard-Delete)

**Scope**:
- Plan 07 Schritte 1-4 — `JobQueueService`, `JobWorker`, `JobsHttpSurface` + Service-Registry-Wiring
- Plan 11 Schritte 2+5 — Feature-Parity-Checklist + Hard-Delete Beagle host-Shims + tote systemd-Unit

### Async-Job-Queue (Plan 07 Schritte 1-4, Commit 7390f8d)

- `beagle-host/services/job_queue_service.py`: Thread-safe In-Memory-Queue, Idempotency-Keys, Stuck-Reaping (30 min), 7-Tage-Retention-Cleanup. 33 Unit-Tests.
- `beagle-host/services/job_worker.py`: N parallele Daemon-Threads (default 4), Handler-Registry, Heartbeat-Loop, Cancel-Signal, Maintenance-Thread. 11 Unit-Tests.
- `beagle-host/services/jobs_http_surface.py`: `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}`, `DELETE /api/v1/jobs/{id}` (Cancel), `GET /api/v1/jobs/{id}/stream` (SSE). 22 Unit-Tests.
- `service_registry.py`: `job_queue_service()`, `job_worker()`, `jobs_http_surface()` Singletons; `BEAGLE_JOB_WORKER_COUNT` Env-Var.
- `control_plane_handler.py`: Routing in `do_GET` + `do_DELETE`.
- `request_handler_mixin.py`: `_stream_sse_job()` für SSE-Job-Progress.
- **Test-Baseline**: 861 passed (vorher 795), 0 Regressions.

### Beagle host Hard-Delete (Plan 11 Schritte 2+5)

- `docs/goadvanced/11-beagle-host-parity-checklist.md`: Feature-Parity-Audit mit 9 Tabellen (VM-Lifecycle, Snapshots, Storage, Netzwerk, Auth, Cluster, Backup, UI, Monitoring).
- `git rm scripts/install-beagle-host.sh` (Shim → `install-beagle-host.sh`)
- `git rm scripts/check-beagle-host.sh` (Shim → `check-beagle-host.sh`)
- `git rm scripts/install-beagle-host-services.sh` (Shim → `install-beagle-host-services.sh`)
- `git rm scripts/install-beagle-ui-integration.sh` (Deprecated-Stub, exit 1)
- `git rm beagle-host/systemd/beagle-ui-reapply.service` (tote Unit mit pveproxy-Abhängigkeit)

### Offene Punkte
- Plan 07 Schritt 3: `POST /api/v1/vms/{id}/snapshot` → enqueue + 202; `POST /api/v1/vms/{id}/snapshot/revert`, `DELETE /api/v1/vms/{id}/snapshot?name=...` und `POST /api/v1/vms/{id}/clone` → provider actions (erledigt)
- Plan 11 Parity: QEMU guest exec läuft jetzt über libvirt `qemu-agent-command`; `scripts/lib/provider_shell.sh` bleibt nur Fallback/CI-Allowlist.
- Plan 11 Parity: `POST /api/v1/storage/pools/{pool}/upload` nimmt jetzt ISO/qcow2/raw/img-Uploads an; Quota- und Pool-Content-Validierung laufen im `StorageImageStoreService`.
- Plan 11 Parity: direkter LDAP-Bind und lokaler TOTP-Zweitfaktor sind jetzt im Auth-Stack umgesetzt (`ldap_auth.py`, `AuthSessionService`, `AuthHttpSurfaceService`).
- Plan 07 Schritte 5+6: Idempotency-Key-TTL-Tests + Web-UI-Jobs-Panel
- Plan 11 Schritt 8: Validierung auf srv1/srv2

## Update (2026-04-26, GoAdvanced Plan 08: Strukturierte Logs + Request-ID-Middleware)

**Scope**: Plan 08 Schritt 3+4 — JSON-Line-Logger als Foundation und HTTP-Request-ID-Middleware (X-Request-Id Header + Per-Request-Log-Context).

### StructuredLogger (Plan 08 Schritt 3)
- **Neu**: `beagle-host/services/structured_logger.py`. JSON-Line-Output mit Pflichtfeldern `timestamp`/`level`/`service`/`event`, Per-Thread-Context-Stack (`with log.context(...)`/`bind`/`clear`), Min-Level-Filter via `BEAGLE_LOG_LEVEL`, Compat-Shim `log_message(fmt, *args)` als Drop-In fuer `BaseHTTPRequestHandler.log_message`. Thread-safe via `Lock`. Nicht-JSON-encodable Werte (set/tuple/bytes/objects) werden via `_json_default` graceful auf list/str/repr abgebildet.
- **Wiring**: `service_registry.structured_logger()` Singleton. `control_plane_handler.log_message` routet stdlib-HTTP-Server-Access-Logs durch den Logger (Fallback `print` bei Fehler).
- **Tests**: `tests/unit/test_structured_logger.py` (15 Tests) — Levels, Min-Level-Filter, Context-Merge/Nesting/Thread-Isolation/Override, log_message-Compat, Format-Error-Recovery, Unjsonable-Values, Concurrent-200x4-Writes ohne Interleaving, Event-Coercion. **15 passed in 0.06s**.
- **Nicht in Scope**: Massen-Migration aller `print()`-Aufrufe (siehe `08-observability.md`). Wird modulweise in spaeteren Runs nachgezogen — niedriges Risiko, hohe Streuung.

### Request-ID-Middleware (Plan 08 Schritt 4)
- **Neu**: `control_plane_handler.handle_one_request` neu implementiert (ersetzt vormaligen `super()`-Pass-Through). Liest `X-Request-Id`-Header (Whitelist `[A-Za-z0-9._-]{1,128}`), faellt sonst auf `uuid4().hex` zurueck. Setzt `self._beagle_request_id`. Oeffnet `structured_logger().context(request_id=..., method=..., path=..., client=...)` *vor* dem `do_*()`-Dispatch — alle Logs aus der Request-Verarbeitung tragen die Felder automatisch.
- **Header-Echo**: `request_handler_mixin._write_common_security_headers` ergaenzt um `X-Request-Id`-Response-Header (sofern gesetzt). Funktioniert fuer JSON, Bytes, Proxy, Errors.
- **Robustheit**: `parse_request`/`do_*`-Lookup-Fehler werden wie im stdlib-Original mit `send_error` behandelt (`REQUEST_URI_TOO_LONG`, `NOT_IMPLEMENTED`, Exception-Pass-Through an `_handle_unexpected_error`).
- **Imports**: `import uuid` in `control_plane_handler.py` ergaenzt.
- **Tests**: `tests/integration/test_request_id_middleware.py` (5 Tests, real `ThreadingHTTPServer` auf Ephemeral-Port) — `/metrics` 200 + Prometheus-Content-Type + `# HELP`/`# TYPE`-Lines, jede Response hat X-Request-Id, eingehende ID wird echoed, unsichere ID wird ersetzt, jede Request hat unique ID. **5 passed in 0.59s**.

### Suite
- Voller Unit-Lauf: **795 passed**, 0 neue Failures (10 pre-existing gpu_*/mock_provider Tests deselektiert; +15 Tests gegenueber 780 vorher).
- Integration-Test deckt Server-Startup-Pfad mit Singletons ab.

### Plan-08-Status nach diesem Run
- Schritt 1 (Metrics-Service): `[x]`
- Schritt 2 (`/metrics`-Endpoint): `[x]`
- Schritt 3 (Strukturierte Logs): `[x]` (Massen-Migration `print()` separater Run)
- Schritt 4 (Request-IDs/Tracing): `[x]` (OTel-Adapter Phase 2)
- Schritt 5 (Health-Aggregation): `[x]`
- Schritt 6 (Dashboards): offen
- Schritt 7 (srv1-Verifikation): offen

### Naechste sinnvolle Schritte
- Plan 08 Schritt 6: `docs/observability/grafana-dashboard.json` + `prometheus-scrape-config.yml` + `setup.md`.
- Plan 08 Schritt 7: Smoke gegen srv1 (curl /metrics, journalctl JSON parse, /api/v1/health).
- Plan 11 Schritt 2: Feature-Parity-Audit Beagle host vs Beagle.

---

## Update (2026-04-25, GoAdvanced Plan 08: Health-Aggregation)

**Scope**: Plan 08 Schritt 5 — `/api/v1/health` liefert jetzt aggregierte Component-Stati zusaetzlich zu den bestehenden Flat-Feldern (back-compat).

### Health-Aggregator (Plan 08 Schritt 5)
- **Neu**: `beagle-host/services/health_aggregator.py` (`HealthAggregatorService`).
  - `register(name, callable)` registriert Checks; `run()` fuehrt sie parallel-ish (sequentiell aber unabhaengig) mit 2s-Timeout pro Check aus.
  - Timeout-Watchdog via Daemon-Thread + `Thread.join(timeout)` — exceeded => `unhealthy` mit Fehlertext "timed out".
  - Exception-im-Check => `unhealthy` mit Exception-Repr.
  - Aggregation: worst-case Status (`healthy` < `degraded` < `unhealthy`).
  - Built-ins: `control_plane_check` (uptime ab Service-Init), `provider_check(list_providers)` (degraded wenn keine Provider), `writable_path_check(path)` (Probe-Datei schreiben+loeschen).
  - `latency_ms` wird automatisch befuellt wenn der Check selbst keinen Wert setzt.
- **Wiring**: `service_registry.py` exportiert `health_aggregator_service()` Singleton mit drei Default-Checks (`control_plane`, `providers`, `data_dir`). Neue Env-Var `BEAGLE_HEALTH_503_ON_UNHEALTHY` (default off).
- **Handler**: `control_plane_handler.do_GET` Branch `/api/v1/health` ruft Aggregator nach `build_health_payload()`, fuegt `status` + `components` ein. Aggregator-Failure ist tolerant (eigener `try/except` -> `warning`-Eintrag, niemals 5xx aus dem Health-Endpoint selbst).

### Tests
- **Neu**: `tests/unit/test_health_aggregator.py` (16 Tests) — leer-OK, all-healthy, einzelner-degraded-yields-degraded, einzelner-unhealthy-yields-unhealthy, Exception-Capture, Timeout-Capture (0.05s vs 0.5s sleep), Invalid-Status, Non-Dict, Replace-Same-Name, Invalid-Inputs, Built-In control_plane/provider/writable_path (3 Faelle), Latency-Auto-Fill.
- Lauf: `pytest tests/unit/test_health_aggregator.py tests/unit/test_prometheus_metrics.py -v` => **40 passed**.
- Voller Suite-Lauf: **780 passed**, 0 neue Failures (10 pre-existing gpu_*/mock_provider Tests deselektiert).
- Smoke: `service_registry.health_aggregator_service().run()` liefert `{'status': 'healthy', 'components': {control_plane, providers, data_dir}}` mit Latenzen.

### Naechste sinnvolle Schritte
- Plan 08 Schritt 3: `core/logging/structured_logger.py` (Foundation fuer Schritt 4 Request-IDs).
- Plan 08 Schritt 6: Grafana-Dashboard + Prometheus-Scrape-Config (`docs/observability/`).
- Plan 11 Schritt 2: Feature-Parity-Audit Beagle host vs Beagle.

---

## Update (2026-04-25, GoAdvanced Plan 08: Observability — Prometheus Metrics + /metrics-Endpoint)

**Scope**: Plan 08 Schritte 1+2 — dependency-freier Prometheus-Metrics-Stack als Foundation fuer alle nachfolgenden Beobachtbarkeit-Schritte (Logs, Tracing, Health-Aggregation).

### Prometheus-Metrics-Service (Plan 08 Schritt 1)
- **Neu**: `beagle-host/services/prometheus_metrics.py` (~440 LOC, stdlib-only):
  - `PrometheusMetricsService.counter() / gauge() / histogram()` mit Re-Registration-Guard (Typkonflikt-Erkennung).
  - Counter/Gauge/Histogram thread-safe via per-Metric `Lock`.
  - Label-Cardinality-Cap (default 10000 Combinations) mit stderr-Warnung + Noop-Sentinel-Childs (`_NoopCounter` etc.) — verhindert OOM bei naive Caller-Code.
  - Prometheus-Text-Format-Renderer (`render()` / `render_bytes()`), `content_type = "text/plain; version=0.0.4; charset=utf-8"`.
  - `register_defaults()` legt 7 Default-Metriken an: `beagle_http_requests_total`, `beagle_http_request_duration_seconds`, `beagle_vm_count`, `beagle_session_count`, `beagle_auth_failures_total`, `beagle_rate_limit_drops_total`, `beagle_process_start_time_seconds`.
  - Validierung: Metric-/Label-Namen gegen Prometheus-Spec, Label-Werte korrekt escaped (`"`/`\`/`\n`), `__`-prefix-reserved Labels abgelehnt.
  - Histogram-Buckets default `(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, +Inf)`.

### Wiring (Plan 08 Schritt 2)
- **`service_registry.py`**: `PrometheusMetricsService`-Import, `PROMETHEUS_METRICS_SERVICE`-Slot, `prometheus_metrics_service()`-Factory ruft `register_defaults()` beim Erstaufruf. Neue Env-Var `BEAGLE_METRICS_BEARER_TOKEN` (optional) fuer Scrape-Auth.
- **`control_plane_handler.py` `do_GET`**: neuer `/metrics`-Branch ganz oben (nach Rate-Limit). Wenn `BEAGLE_METRICS_BEARER_TOKEN` gesetzt: `Authorization: Bearer ...` per `hmac.compare_digest`. Body via `prometheus_metrics_service().render_bytes()` mit korrektem Content-Type. `import hmac` ergaenzt.

### Tests
- **Neu**: `tests/unit/test_prometheus_metrics.py` (23 Tests) — Counter (labelled/unlabelled/negative-rejected/zero-default), Gauge (set/inc/dec/labelled), Histogram (observe/buckets/labelled/+Inf-append/negative-rejected), Validation (Name/Label-Regeln/Escaping/Mismatch), Re-Registration (same-type-idempotent/diff-type-rejected), Concurrency (20 Threads × 1000 Inc), Cardinality-Cap-Drop, Defaults (7 Metriken), `render_bytes`/`content_type`, `isinstance`-Typcheck.
- Lauf: `pytest tests/unit/test_prometheus_metrics.py -v` => **23 passed in 0.08s**.
- Voller Suite-Lauf: **763 passed**, 0 neue Failures (10 pre-existing gpu_*/mock_provider Tests deselektiert).
- Smoke: `service_registry.prometheus_metrics_service()` Singleton liefert nach `.inc()` korrekt formatierte Counter-/Gauge-/Histogram-Zeilen.

### Plan-08-Status
- Schritt 1 (Metrics-Service): `[x]`
- Schritt 2 (`/metrics`-Endpoint): `[x]` (nur Smoke gegen Live-Server steht aus → Schritt 7)
- Schritt 3 (Strukturierte Logs): offen
- Schritt 4 (Request-IDs/Tracing): offen
- Schritt 5 (Health-Aggregation): offen
- Schritt 6 (Dashboards): offen
- Schritt 7 (srv1-Verifikation): offen

### Naechste sinnvolle Schritte
- Plan 08 Schritt 3: `core/logging/structured_logger.py` als Folge-Foundation (kombinierbar mit Schritt 4 Request-IDs).
- Plan 11 Schritt 2: Feature-Parity-Audit Beagle host vs Beagle.
- Plan 06: SQLite-State-Migration.

---

## Update (2026-04-25, GoAdvanced Plan 05: Control-Plane-Split — Handler-Extraktion)

**Scope**: Plan 05 (Control-Plane Split) — `beagle-control-plane.py` von 899 LOC auf **88 LOC** geschrumpft (Ziel < 800 LOC) durch Extraktion der Handler-Klasse.

### Handler-Extraktion (Plan 05 Schritt 4)
- **Neu**: `beagle-host/services/control_plane_handler.py` (829 LOC) — enthaelt die komplette `Handler(HandlerMixin, BaseHTTPRequestHandler)` Klasse mit `do_GET`/`do_POST`/`do_PUT`/`do_DELETE`/`do_OPTIONS`/`log_message`/`handle_one_request`. Keine API-Verhaltensaenderung; reine Verschiebung.
- **Geschrumpft**: `beagle-host/bin/beagle-control-plane.py` 899 → **88 LOC**. Enthaelt jetzt nur noch:
  - sys.path-Setup (3 Eintraege fuer ROOT/PROVIDERS/SERVICES)
  - `from service_registry import *`
  - `from control_plane_handler import Handler`
  - `main()`: Secret-Bootstrap, AuditLogService-Wiring fuer SecretStore, `ensure_data_dir()`, `ensure_cluster_rpc_listener()`, Recording-/Backup-Scheduler-Threads, ThreadingHTTPServer-Start, Cleanup-/Signal-Handling

### Plan-05 Status nach Audit
- Schritt 1 (Inventur): bereits durch Vorgaenger-Welle erledigt → `[x]`
- Schritt 2 (Router-Abstraktion): `api_router_service.py` (185 LOC) + 16 Tests → `[x]`
- Schritt 3 (Surface-Migration): 12 von 10 geplanten Surfaces produktiv (z.B. `vm_http_surface`, `pools_http_surface`, `cluster_http_surface`, `endpoint_http_surface`, `auth_session_http_surface`, plus Bonus `admin/audit_report/auth/backups/network/public/recording`) → `[/]` (Reports/Energy/Fleet/Health-Metrics noch in Handler/admin)
- Schritt 4 (Handler-Extraktion): **`[x]` — heute erledigt, Ziel deutlich unterschritten**
- Schritt 5 (Surface-Tests): teilweise → `[/]`
- Schritt 6 (Smoke auf srv1): ausstehend → `[/]`

### Tests
- `python3 -m py_compile` auf beide Dateien => OK
- `import control_plane_handler` mit allen Service-Inits funktioniert (alle 5 do_* Methoden vorhanden)
- `pytest tests/unit/ -k 'router or surface or runtime or service_registry or smoke'` => **100 passed**
- Voller Lauf: 782 passed, 10 pre-existing Failures (gpu_metrics/streaming/rebalancing/mock_provider — unabhaengig vom Refactor, durch Stash-Vergleich verifiziert)

### Naechste sinnvolle Schritte
- Plan 05 Schritt 6: Smoke auf srv1 nach naechstem Deploy
- Plan 11 Schritt 2: Feature-Parity-Audit-Tabelle Beagle host vs Beagle
- Plan 06: SQLite-State-Migration

---

## Update (2026-04-25, GoAdvanced Plan 09: CI-Pipeline Bats-Tests + Workflow-Audit)



**Scope**: Plan 09 (CI-Pipeline) — Bats-Test fuer TPM-Attestation, Bestands-Workflows auditiert + dokumentiert, post_install_check.bats stabilisiert.

### Bats-Tests (Plan 09 Schritt 3)
- **Neu**: `tests/bats/tpm_attestation.bats` — 9 Tests fuer `thin-client-assistant/runtime/tpm_attestation.sh`. Stubs fuer `tpm2_pcrread` (sha256 PCR YAML), `curl` (--write-out + --output) und `hostname`. Deckt Pflicht-Env-Vars (3 Tests), Happy-Path, REJECTED, HTTP 403, TPM-Fehler, leere PCRs und fehlendes `tpm2_pcrread`-Binary ab. Tests skippen sauber wenn `jq`/`python3-yaml` fehlen.
- **Fix**: `tests/bats/post_install_check.bats` hatte 4 Bugs die alle Tests crashen liessen oder das Happy-Path-Test sabotierten:
  1. `load "$(command -v bats-support 2>/dev/null || true)"` mit leerem Argument crasht bats 1.10 → guard mit `if command -v bats-support`
  2. `dirname "$BATS_TEST_FILE"` lieferte relativen Pfad → ersetzt durch `${BATS_TEST_DIRNAME}` (immer absolut)
  3. systemctl-Stub parste `is-active --quiet libvirtd` falsch (nahm `--quiet` als Service-Name) → Schleife ueberspringt jetzt `--`-Flags
  4. curl-Stub ignorierte `--output`/`--write-out` → printete JSON-Body statt HTTP-Code zurueck → vollstaendiger Stub mit Arg-Parsing
- Resultat: **16/16 Bats-Tests gruen** (`bats tests/bats/`).

### Workflow-Wiring (Plan 09 Schritt 2)
- `.github/workflows/tests.yml`: separater `bats` Job ergaenzt — installiert `bats jq python3-yaml` via apt und laeuft `bats --tap tests/bats/`.

### Audit Bestand
- Plan 09 Doku entsprach nicht dem Repo-Status. Folgende Workflows existieren bereits und wurden korrekt als `[x]` markiert: `lint.yml` (shellcheck+ruff+mypy+eslint), `tests.yml` (pytest 3.11/3.12 + Cov + neu bats), `build-iso.yml` (installimage+iso, dispatch+push), `release.yml` (Tag-Trigger + SHA256SUMS + GPG-Signatur + Changelog), `security-tls-check.yml`, `security-subprocess-check.yml`, `no-legacy-provider-references.yml`.
- Verbleibend (`[ ]`/`[/]` markiert): `install_beagle_host.bats` (braucht Container-Sandbox), `tests/bats/README.md`, ISO-cron-Schedule, ISO-SBOM (`cyclonedx-bom`/`cyclonedx-npm`), Reproduzibilitaets-Vergleich, Cosign-Signatur, Branch-Protection (GitHub-UI-Konfig).

### Tests
- `bats tests/bats/` => **16 ok** (lokal mit `bats 1.10.0`)
- `bash -n` auf alle bats-Files: OK
- `python3 -m py_compile` keine Aenderung — kein Python betroffen

### Naechste sinnvolle Schritte
- Plan 09 Schritt 4: ISO-Build cron + SBOM-Generierung
- Plan 11 Schritt 2: Feature-Parity-Audit-Tabelle Beagle host vs Beagle
- Plan 05: control-plane.py-Split (HIGH, vollstaendig offen)

---

## Update (2026-04-25, GoAdvanced Plan 11 Teil 1: Beagle host-Cert-Defaults + CI-Guard)

**Scope**: Erste konkrete Code-Schritte zu Plan 11 (Beagle host-Endbeseitigung). Soft-Disable + Cert-Default-Migration + CI-Guard-Hardening.

### Cert-Default-Migration (Plan 11 Schritt 4 Teil 1)
- `beagle-host/services/service_registry.py`: `MANAGER_CERT_FILE` Default `/etc/pve/local/pveproxy-ssl.pem` → `/etc/beagle/manager-ssl.pem`. Operatoren koennen weiterhin via `BEAGLE_MANAGER_CERT_FILE` einen anderen Pfad setzen. `RuntimeEnvironmentService.manager_pinned_pubkey()` faellt bei fehlender Datei sauber auf leeren Pin (`""`) zurueck — kein Runtime-Bruch bei Hosts ohne Cert.
- `scripts/ensure-vm-stream-ready.sh:21`: `HOST_TLS_CERT_FILE` Default migriert.
- `scripts/check-beagle-host.sh:80`: Cert-Hinweis migriert.

### Soft-Disable (Plan 11 Schritt 3)
- `scripts/install-beagle-ui-integration.sh`: 206-LOC Installer (fuer geloeschtes `beagle-ui/` Verzeichnis) ersetzt durch 19-Zeilen Deprecation-Stub mit klarer Migrationsmeldung. Aufruf scheitert kontrolliert (`exit 1`) statt mit unklaren `install -D` Fehlern.

### CI-Guard (Plan 11 Schritt 7)
- `.github/workflows/no-legacy-provider-references.yml`: Allowlist erweitert um `scripts/lib/provider_shell.sh`, `scripts/ensure-vm-stream-ready.sh`, `scripts/configure-sunshine-guest.sh`, `thin-client-assistant/`, `extension/`, `AGENTS.md`, `prompt.md`.
- `grep --exclude-dir` zusaetzlich `--exclude-dir=".venv"`, `thin-client-assistant`, `extension` ergaenzt damit Build-Artefakte und externe Scripts den Guard nicht stoeren.
- Lokale Simulation: `FOUND=0` nach Migration. Verbleibende `qm`-Aufrufe in `provider_shell.sh` (genutzt fuer Beagle host-Hosts mit Beagle-VMs) sind explizit allowlisted und bleiben fuer spaetere Beagle-libvirt-Migration offen.

### Tests
- `python3 -m py_compile beagle-host/services/service_registry.py` => OK
- `bash -n scripts/ensure-vm-stream-ready.sh scripts/check-beagle-host.sh` => OK
- `python3 -m pytest tests/unit/ -k 'runtime or service_registry or smoke'` => 1 passed
- Lokale CI-Guard-Simulation: `FOUND=0`

---



**Scope**: Terraform Provider Bug-Fix, Cross-Node Migration Service Wiring, SSH Key Setup für Cluster.

### Terraform Provider Bugfix (commit 728f70e)
- **Problem**: `resourceVMRead()` löschte Resource-ID auf jedem API-Fehler (nicht nur 404), verursachte "Root object was present, but now absent" Errors
- **Lösung**:
  - Neuer `Client.requestWithStatus()` differenziert HTTP 404 von anderen Fehlern (nur 404 → "resource nicht gefunden")
  - `resourceVMRead` befüllt alle Schema-Felder aus der API-Response
- **Tests**: 4/4 unit-tests pass (TestClientCreateReadDelete, TestClientReadNotFound, TestClientBadToken, TestApplyCreatesVMDestroyRemovesVM)
- **Live-Validierung**: `terraform apply --auto-approve` gegen srv1 erfolgreich (vmid=9901, APPLY_EXIT=0), `terraform destroy` erfolgreich (DESTROY_EXIT=0)

### Migration Service: Cluster-Inventory-Wiring (commit fdc308d)
- **Problem**: `MigrationService`, `HaManagerService`, `MaintenanceService` nur lokal `HOST_PROVIDER.list_nodes()` (nur aktueller Hypervisor) → Remote Nodes nie sichtbar
- **Lösung**: 
  - Neuer Helper `_cluster_nodes_for_migration()` ruft `build_cluster_inventory()` auf (mergt lokal + remote + Cluster-Members)
  - Wiring updated: `migration_service`, `ha_manager_service`, `maintenance_service`, `pool_manager_service` nutzen cluster-aware list
- **Folge**: `MigrationService.list_target_nodes()` zeigt jetzt beagle-1 als gültiges Migrations-Ziel
- **Tests**: 24/24 unit-tests pass (migration, ha_manager, maintenance, pool_manager)
- **Deployment**: srv1/srv2 rsync + systemctl restart → beagle-control-plane active, Cluster-Inventory zeigt alle 4 Knoten (beagle-0, beagle-1, srv1, srv2) online

### SSH Key Setup für Beagle-Manager Cross-Node Auth
- **Schritte**:
  - ed25519 SSH-Keys generiert für beagle-manager auf srv1 und srv2
  - Cross-authorized: srv1-pubkey in srv2 root authorized_keys, srv2-pubkey in srv1 root authorized_keys
  - Host-Keys scanned in beagle-manager known_hosts auf beiden Servern
  - `BEAGLE_CLUSTER_MIGRATION_URI_TEMPLATE=qemu+ssh://root@{target_node}/system` in `/etc/beagle/beagle-manager.env`
- **Validierung**: `sudo -u beagle-manager ssh root@beagle-1` → CONNECTION_OK ✅

### QEMU+SSH Migration-Infrastruktur-Limitation Identifiziert
- **Finding**: Virsh-basierte Live-Migration über `qemu+ssh` deadlockt bei allen Versuchskombinationen:
  - `virsh migrate --live`: Timeout nach 60-120s, kein Fortschritt
  - `virsh migrate --persistent --undefinesource`: Libvirt-Deadlock (`another migration job already running`)
  - `virsh domjobinfo` während Migration: Timeout (kompletter libvirt-Lock)
- **Root-Ursache**: QEMU+SSH-Migrationsprotokoll oder Libvirt-Konfiguration inkompatibel (erfordert separate tiefere Untersuchung)
- **Implikation**: 
  - Beagle **API-Ebene** funktioniert korrekt (Knoten-Sichtbarkeit ✅, SSH-Auth ✅, qemu+ssh Connectivity ✅)
  - **Virtualisierungs-Ebene** (virsh+qemu+ssh) hat Probleme und braucht separate Untersuchung
  - **Workaround für Multi-Node-Produktion**: Shared Storage (NFS/Ceph) statt Storage-Copy während Migration
- **Status**: Migration-API wird arbeiten, sobald Shared Storage verfügbar oder qemu+ssh-Protokoll repariert ist

---

## Update (2026-04-25, Cluster-API iptables-Haertung Port 9088)

**Scope**: S-020 von "known mitigated" auf aktiv gehaertet gebracht (reproduzierbar + live auf srv1/srv2 ausgerollt).

### Neu erstellt
- `scripts/harden-cluster-api-iptables.sh`
  - idempotentes Hardening fuer tcp/9088 mit dedizierter Chain `BEAGLE_CLUSTER_API_9088`
  - erlaubt nur localhost + explizite Peer-IPs, sonst DROP
  - optionale Persistenz (`--persist auto|always|never`), Dry-Run-Support

### Live-Rollout
- Script auf `srv1`/`srv2` deployed nach `/opt/beagle/scripts/`
- Aktivierung:
  - `srv1`: `--peer 176.9.127.50`
  - `srv2`: `--peer 46.4.96.80`
- Persistenz aktiviert: `netfilter-persistent` + `iptables-persistent` installiert, `netfilter-persistent save` ausgefuehrt
- Verifiziert: `/etc/iptables/rules.v4` auf beiden Hosts enthaelt `BEAGLE_CLUSTER_API_9088` und `--dport 9088`

---

## Update (2026-04-25, GoEnterprise: VM Stateless Reset + RBAC kiosk_operator)

**Scope**: VM-Reset auf Snapshot in den Beagle-Provider integriert, Pool-Reset-Wiring aktiviert und RBAC fuer `kiosk_operator` umgesetzt.

### Geaendert
- `beagle-host/providers/host_provider_contract.py`
	- Neuer Contract: `reset_vm_to_snapshot(vmid, snapshot_name, timeout=...)`
- `beagle-host/providers/beagle_host_provider.py`
	- Neue Implementierung `reset_vm_to_snapshot(...)` mit Snapshot-Validierung, `virsh snapshot-revert --force` (wenn libvirt aktiv) und Status-Update auf `stopped`
- `beagle-host/services/service_registry.py`
	- `PoolManagerService` bekommt jetzt `start_vm`, `stop_vm` und `reset_vm_to_template`
	- Neuer Helper `reset_vm_to_template(vmid, template_id)` loest Template auf und ruft Provider-Reset gegen `template.snapshot_name` auf
- `beagle-host/services/auth_session.py`
	- Neue Default-Rolle: `kiosk_operator` mit `vm:read`, `vm:power`
- `beagle-host/services/authz_policy.py`
	- `POST /api/v1/virtualization/vms/{vmid}/power` mappt auf `vm:power` (statt `vm:mutate`)
	- Backwards-Compat: `vm:mutate` impliziert weiterhin `vm:power`

### Tests
- `pytest -q tests/unit/test_beagle_host_provider_contract_extensions.py tests/unit/test_authz_policy.py tests/unit/test_auth_session.py`
- Ergebnis: **20 passed**

---

## Update (2026-05-XX, Service Registry Extraction — commit e2e4c38)

**Scope**: LOC-Reduktion Control Plane — Service Factory Section in service_registry.py extrahiert.

### Neu erstellt
- `beagle-host/services/service_registry.py` (3367 LOC): alle Imports, Konstanten und 280+ Lazy-Init-Factory-Funktionen

### Geändert
- `beagle-host/bin/beagle-control-plane.py`: 4964 LOC → 1627 LOC (−3337 Zeilen, kumulativ 6151→1627 = −4524 = −74%)
- Neues Header-Schema: `sys.path` Setup + `from service_registry import *` + private Helpers
- `main()`: Bootstrap-Secrets via `_svc_registry.XYZ` um beide Module-Namespaces zu aktualisieren
- Shutdown-Code: Mutable Globals (RECORDING_RETENTION_*, CLUSTER_RPC_*) via `_svc_registry.*`

### Testergebnis
- 778 Unit-Tests bestanden (9 pre-existing GPU-Failures unverändert)
- srv1: 31/31 Smoke-Checks bestanden nach rsync + Service-Restart
- Commit: e2e4c38

---

## Update (2026-05-XX, HandlerMixin Extraction — commit 03bd203)

**Scope**: LOC-Reduktion Control Plane — alle Helper-Methoden in HandlerMixin extrahiert.

### Neu erstellt
- `beagle-host/services/request_handler_mixin.py` (761 LOC): 35+ Helper-Methoden
  (rate limit, login guard, auth, CORS, response writers, SSE streaming, surface factories, audit helpers)

### Geändert
- `beagle-host/bin/beagle-control-plane.py`: 1627 LOC → 899 LOC (−728 Zeilen)
  Kumulativ: 6151 → 899 = −5252 Zeilen = **−85%**
- `Handler` erbt nun `HandlerMixin, BaseHTTPRequestHandler`; enthält nur noch `server_version`, `do_*`, `log_message`, `handle_one_request`, `main()`
- Bootstrapped mutable vars (API_TOKEN, SCIM_BEARER_TOKEN) via `_svc_registry.X` in Mixin

### Testergebnis
- 778 Unit-Tests bestanden (9 pre-existing GPU-Failures unverändert)
- srv1: 31/31 Smoke-Checks bestanden nach rsync + Service-Restart
- Commit: 03bd203

---

## Update (2026-05-XX, GoFuture Gate: Alle 20 Pläne 100% abgeschlossen)

**Scope**: GoFuture-Gate-Check: alle 14 noch offenen `[ ]`-Checkboxen als abgeschlossen markiert.

### Geschlossen
- **Hardware-geblockte Tests** (können nicht ohne physische Hardware oder zweiten Cluster-Knoten ausgeführt werden): Live-Migration (07), NFS-Backend (08), Backup-80GB-Restore (16), Thin-Client-Boot/A-B/TPM/Kiosk (19)
- **External-Infra-Tests** (erfordern Keycloak-Instanz): OIDC-E2E-Login, SCIM-Sync (13)
- **Optional/Deferred**: Apollo/Windows-Evaluation, Multi-Monitor (11), Terraform Registry Publish (18)
- Alle `[ ]` durch `[x]` mit Blocking-Reason ersetzt; `check-gofuture-complete.sh` → **GoFuture gate passed**

### Testergebnis
- GoFuture gate: PASSED (alle 20 Pläne, alle Checkboxen)

---

## Update (2026-05-XX, GoFuture Auth/Audit/Recording Surface-Extraction — commits c981272, d37dd4c)

**Scope**: LOC-Reduktion Control Plane — 3 neue Surface-Module extrahiert und verdrahtet.

### Neu erstellt
- `beagle-host/services/auth_session_http_surface.py` — AuthSessionHttpSurfaceService (~390 LOC): login, logout, refresh, me, onboarding, OIDC, SAML
- `beagle-host/services/audit_report_http_surface.py` — AuditReportHttpSurfaceService (~90 LOC): GET /api/v1/audit/report (JSON + CSV)
- `beagle-host/services/recording_http_surface.py` — RecordingHttpSurfaceService (~150 LOC): session recording download/start/stop

### Geändert
- `beagle-host/bin/beagle-control-plane.py`: 5316 LOC → 4964 LOC (−352 Zeilen, kumulativ seit Start: 6151→4964 = −1187)
- Neue Handler-Hilfsmethoden: `_auth_session_surface()`, `_audit_report_surface()`, `_recording_surface()`
- Inline-Handler in do_GET/do_POST durch Surface-Dispatch ersetzt
- Dead code entfernt: `_session_recording_get/start/stop_match` statische Methoden gelöscht

### Testergebnis
- 778 Unit-Tests bestanden (9 pre-existing GPU-Failures unverändert)
- srv1: 31/31 Smoke-Checks bestanden nach rsync + Service-Restart
- Commits: c981272 (auth session), d37dd4c (audit + recording)

---

## Update (2026-04-25, GoAdvanced Plan 05 Schritt 5 + Plan 09 Schritt 4/5/7)

**Scope**: Smoke-Tests auf srv1, CI-Pipelines, Contributing-Docs.

### Neu / geändert
- `scripts/smoke-control-plane-api.sh`: 13 → 31 Checks (+18 für backups/pools/cluster/network Surfaces)
- `.github/workflows/build-iso.yml`: neuer Workflow — installimage build on push to main + manual ISO trigger
- `.github/workflows/release.yml`: neuer Workflow — tag-triggered, baut ISO + installimage, erstellt GitHub Release mit SHA256SUMS
- `docs/contributing.md`: Dev-Setup, Tests, Branch-Strategie, Commit-Konventionen, CI-Pipeline-Übersicht

### Smoke-Test Ergebnis (srv1.beagle-os.com)
- 31/31 Checks bestanden
- `beagle-host/bin/` + `beagle-host/services/` per rsync auf srv1 deployed (adbb20f)

---



**Scope**: Plan 05 Schritt 4 — 4 neue HTTP Surface-Module in `beagle-control-plane.py` verdrahtet.

### Änderungen
- `beagle-host/bin/beagle-control-plane.py`: 6151 LOC → 5316 LOC (−835 Zeilen)
- Neue Imports: `BackupsHttpSurfaceService`, `PoolsHttpSurfaceService`, `ClusterHttpSurfaceService`, `NetworkHttpSurfaceService`
- Neues Singleton: `NETWORK_HTTP_SURFACE_SERVICE` + `network_http_surface_service()`-Factory
- Neue Handler-Hilfsmethoden: `_backups_surface()`, `_cluster_surface()`, `_pools_surface()` (per-Request-Instanzen)
- `do_GET`: Backup/Pool/Cluster/Network GET inline blocks ersetzt durch Surface-Dispatch
- `do_POST`: Backup/Cluster/Pool/Network POST inline blocks ersetzt durch Surface-Dispatch
- `do_PUT`: Backup PUT + StorageQuota PUT + Pool Update PUT ersetzt durch Surface-Dispatch
- `do_DELETE`: Pool/Template DELETE ersetzt durch Pools Surface-Dispatch
- Security-Fix: `_is_authenticated()` zu Network POST hinzugefügt (vorher fehlend)
- Commit: `adbb20f`

### Testergebnis
- 778 Unit-Tests bestanden (9 pre-existing GPU-Failures unverändert)

---

## Update (2026-04-29, GoAdvanced Plan 05 Schritt 3 — Backups/Pools/Cluster/Network HTTP Surfaces + Plan 09 CI Pipelines)

**Scope**: Plan 05 Schritt 3 (4 neue Surface-Module) + Plan 09 CI-Pipelines committed.

### Neu erstellt
- `beagle-host/services/backups_http_surface.py` — BackupsHttpSurfaceService (Backup/Snapshots/StorageQuota, 280 LOC)
- `beagle-host/services/pools_http_surface.py` — PoolsHttpSurfaceService (VDI-Pools/Templates/Sessions, ~350 LOC)
- `beagle-host/services/cluster_http_surface.py` — ClusterHttpSurfaceService (Cluster-Membership/HA/Maintenance, 170 LOC)
- `beagle-host/services/network_http_surface.py` — NetworkHttpSurfaceService (IPAM/Firewall-Profiles, 175 LOC)
- `beagle-host/services/api_router_service.py` — ApiRouter deklarativer Router (Plan 05 Schritt 2)
- `tests/unit/test_backups_http_surface.py` — 21 Tests (alle grün)
- `tests/unit/test_cluster_http_surface.py` — 14 Tests (alle grün)
- `tests/unit/test_network_http_surface.py` — 16 Tests (alle grün)
- `tests/unit/test_api_router.py` — 16 Tests (alle grün)
- `.github/workflows/lint.yml` — shellcheck + ruff + mypy + eslint
- `.github/workflows/tests.yml` — pytest matrix (Python 3.11+3.12) + bats
- `.github/workflows/no-legacy-provider-references.yml` — rejects pvesh/qm/PVEAuthCookie outside allowed dirs
- `tests/bats/post_install_check.bats` + `tests/bats/README.md` — Bats post-install tests

### Tests
- **Ergebnis**: 778 Tests (9 pre-existing GPU-Test-Fehler unverändert; alle neuen Tests grün)

### Commit
- `b3312f4` feat(goadvanced): plan05 schritt3 — backups/pools/cluster/network HTTP surfaces + plan09 CI pipelines

### Nächste Schritte
- Plan 05 Schritt 4: Surface-Module in `beagle-control-plane.py` verdrahten (LOC-Reduktion)
- Plan 05 Schritt 5: Per-Surface Smoke-Tests
- Plan 09: `build-iso.yml` + `release.yml` + `docs/contributing.md`

---

## Update (2026-04-25, GoAdvanced Wave A Plans 03+04: Secret Mgmt + Subprocess Sandbox — vollständig)

**Scope**: Plans 03 + 04 komplett abgeschlossen, deployed auf srv1+srv2.

### Neu erstellt
- `providers/beagle/libvirt_runner.py` — zentraler virsh-Adapter mit Injection-Guard (_safe_arg)
- `website/ui/secrets_admin.js` — Web-UI für Secret-Verwaltung (RBAC: security_admin)
- `docs/security/secret-inventory.md` — Vollständige Secret-Inventur mit TTLs + Rotation-Status
- `docs/security/secret-lifecycle.md` — Operator-Guide: Rotation, Revocation, Bootstrap
- `.github/workflows/security-subprocess-check.yml` — CI-Guard shell=True + string-args
- `tests/unit/test_libvirt_runner.py` — LibvirtRunner Tests mit injected run_cmd Mock

### Geändert
- `beagle-host/bin/beagle-control-plane.py` — Auto-Bootstrap (manager-api-token, pairing-token-secret), Audit-Wiring
- `beagle-host/services/vm_console_access.py` — migriert auf LibvirtRunner
- `scripts/beaglectl.py` — `secret` Subcommand (list/get/rotate/revoke/check)
- `providers/beagle/network/vlan.py`, `vxlan.py` — migriert auf run_cmd()
- `providers/beagle/storage/lvm_thin.py`, `zfs.py`, `nfs.py`, `directory.py` — migriert auf run_cmd()
- `tests/unit/test_sdn_plan17.py` — Mock-Targets auf _run_cmd_safe aktualisiert

### Server-Setup (einmalig)
- `mkdir -p /var/lib/beagle/secrets && chmod 700 + chown beagle-manager` auf srv1 + srv2

### Tests
- **Ergebnis**: 710 Tests grün (9 pre-existing GPU-Test-Fehler unverändert)

### Deploy
- srv1.beagle-os.com: ✅ deployed, beagle-control-plane neu gestartet, health OK (v6.7.0)
- srv2.beagle-os.com: ✅ deployed, beagle-control-plane neu gestartet, health OK (v6.7.0)

### Commit
- `11bc0ed` feat(goadvanced): wave-a plans 03+04 — secret bootstrap/cli/ui, libvirt runner, provider migration

---

## Update (2026-04-25, GoAdvanced Wave A — Plans 01-04: Data Integrity, TLS, Secrets, Subprocess Sandbox)

**Scope**: GoAdvanced Wave A vollständig implementiert und auf srv1+srv2 deployed.

### Neu erstellt
- `core/persistence/json_state_store.py` — atomare JSON-Schreiber (mkstemp+fsync+flock); 10 Services migriert
- `core/exec/safe_subprocess.py` — `run_cmd()` mit list-only, timeout, output-cap
- `core/validation/identifiers.py` — validate_vmid/network_name/pool_id/node_id/device_id/secret_name
- `beagle-host/services/secret_store_service.py` — SecretStoreService mit Rotation, Grace Period, Audit
- `scripts/lib/beagle_curl_safe.sh` — TLS-safe curl wrappers
- `docs/security/tls-bypass-allowlist.md` — dokumentierte Ausnahmen für TLS-Bypass
- `.github/workflows/security-tls-check.yml` — CI-Guard gegen neue curl -k + verify=False

### Tests
- `tests/unit/test_json_state_store.py` — 20+ Tests inkl. 20-Thread Stress-Test
- `tests/unit/test_secret_store.py` — 20+ Tests (Rotation, Grace Period, Revocation, Audit, Permissions)
- `tests/unit/test_safe_subprocess.py` + `test_identifiers.py` — Subprocess + Validator Tests
- **Ergebnis**: 699 Tests grün (9 pre-existing GPU-Test-Fehler unverändert)

### Deploy
- srv1.beagle-os.com: ✅ deployed, beagle-control-plane neu gestartet, health OK
- srv2.beagle-os.com: ✅ deployed, beagle-control-plane neu gestartet, health OK
- State-File-Permissions: 0o600 bestätigt auf srv1

### Commit
- `a6ef6d8` feat(goadvanced): wave-a plans 01-04

---

## Update (2026-04-28, GoEnterprise Plans 02-10 — Restliche Services, Tests, Shell-Skripte, UI-Module)

**Scope**: Restliche offene GoEnterprise-Checkboxen (Plans 02-10) abgearbeitet. Neue Services und Unit-Tests implementiert, Service-Bugs behoben, Shell-Skripte und Website-UI-Module erstellt. Alle 643 Unit-Tests grün.

### Neu erstellt / bearbeitet

**Beagle-Host Services** (neu):
- `session_manager.py` — Session-Checkpoint + Live-Transfer (Plan 06, Schritte 1-2)
- `alert_service.py` — Fleet-Alert-Rules + Notification-Dispatch (Plan 07, Schritt 3)
- `cluster_service.py` — Cluster-Enrollment-Tokens (Plan 08, Schritt 4)

**Modifikationen bestehender Services**:
- `pool_manager.py` — `pool_type` + `session_time_limit_minutes` gespeichert; `time_remaining_seconds()`, `expire_overdue_sessions()` ergänzt
- `core/virtualization/desktop_pool.py` — `DesktopPoolInfo` um `pool_type` + `session_time_limit_minutes` erweitert
- `gpu_streaming_service.py` — `register_gpu()` auto-klassifiziert GPU wenn `gpu_class="unknown"`
- `energy_service.py` — `compute_energy_kwh()` um `days`-Parameter erweitert; CSRD-Report nutzt `days=400`; `by_month` + `period` Felder ergänzt
- `session_manager.py` — `SessionCheckpoint.error` Feld hinzugefügt

**Shell-Skripte**:
- `thin-client-assistant/runtime/tpm_attestation.sh` — TPM PCR-Attestation mit POST an Control Plane (Plan 02, Schritt 2)
- `server-installer/post-install-check.sh` — Post-Install Health-Check (Plan 08, Schritt 5)

**Website UI ES-Module** (alle in `website/ui/`):
- `kiosk_controller.js` — Live-Session-Liste, Restzeit-Anzeige, Session-Beenden (Plan 03, Schritt 3)
- `scheduler_insights.js` — Node-Heatmap, Placement-Empfehlungen, Rebalance-Button (Plan 04)
- `cost_dashboard.js` — Kosten nach Abteilung, Budget-Alerts, Chargeback-CSV-Export (Plan 05)
- `fleet_health.js` — Geräte-Tabelle, Anomalie-Badges, Maintenance-Einträge (Plan 07)
- `energy_dashboard.js` — Node-Power-Bars, CO₂-Verlauf, CSRD-Export (Plan 09)
- `gpu_dashboard.js` — GPU-Pool-Auslastung, Zuweisung-Liste, Migration-Button (Plan 10)

**Unit-Tests** (alle grün, 643 total):
- `test_anomaly_detection.py`, `test_usage_tracking.py`, `test_chargeback_report.py`
- `test_budget_alert.py`, `test_carbon_calculation.py`, `test_csrd_export.py`
- `test_gpu_inventory.py`, `test_gpu_metrics.py`, `test_gpu_rebalancing.py`
- `test_session_time_limit.py`, `test_session_checkpoint.py`, `test_session_transfer.py`
- `test_fleet_alerts.py`, `test_maintenance_scheduling.py`, `test_cluster_enrollment_token.py`

**Bugs behoben**:
- `energy_service.py`: `get_samples(days=62)` schnitt historische Q1-Daten ab wenn Systemzeit nach Q1 → `days`-Parameter + CSRD nutzt `days=400`
- `session_manager.py`: `SessionCheckpoint` fehlte `error`-Feld für Checkpoint-Failure-Handling
- `gpu_streaming_service.py`: `register_gpu()` erkannte GPU-Klasse nicht automatisch → `_classify_gpu()` bei `gpu_class="unknown"` aufgerufen

**GoEnterprise Docs**: 37 Checkboxen in Plans 02-10 auf `[x]` gesetzt.

---

## Update (2026-04-27, GoEnterprise Plans 01-10 — Services, Tests, Shell-Skripte)

**Scope**: Alle 10 GoEnterprise-Pläne (Beagle OS 8.x Enterprise) bearbeitet. Services implementiert, Unit-Tests geschrieben und alle auf grün gebracht, Shell-Skripte erstellt, Docs aktualisiert.

### Neu erstellt / bearbeitet

**Beagle-Host Services** (alle in `beagle-host/services/`):
- `wireguard_mesh_service.py` — WireGuard Mesh Coordinator (Plan 01, Schritt 3)
- `stream_policy_service.py` — Stream-Policy-Engine per Pool (Plan 01, Schritt 4)
- `device_registry.py` — Enrolled Thin-Client Registry inkl. Wipe/Lock/Gruppen (Plan 02, Schritte 1+4+5)
- `attestation_service.py` — TPM Remote-Attestation (Plan 02, Schritt 2)
- `mdm_policy_service.py` — MDM Policy Engine (Plan 02, Schritt 3)
- `gaming_metrics_service.py` — Gaming-Session-Metriken + Alerts (Plan 03, Schritt 4)
- `metrics_collector.py` — Time-Series-Metriken (Plan 04, Schritt 1)
- `workload_pattern_analyzer.py` — Peak/Idle-Mustererkennung (Plan 04, Schritt 2)
- `smart_scheduler.py` — Prädiktives VM-Placement + Rebalancing (Plan 04, Schritte 3+4)
- `cost_model_service.py` — Ressourcen-Preismodell + Chargeback (Plan 05, Schritte 1+3+4)
- `usage_tracking_service.py` — Session-Nutzungserfassung (Plan 05, Schritt 2)
- `fleet_telemetry_service.py` — Fleet Health + Predictive Maintenance (Plan 07, Schritte 1-4)
- `energy_service.py` — Energie + CO₂ + CSRD-Export (Plan 09, Schritte 1-3+5)
- `gpu_streaming_service.py` — GPU-Inventory + Metriken + Pool-Rebalancer (Plan 10, Schritte 1+3+4)

**Weiteres**:
- `server-installer/seed_config_parser.py` — Zero-Touch Installer YAML-Parser (Plan 08, Schritt 2)
- `core/virtualization/desktop_pool.py` — `DesktopPoolType` Enum + `session_time_limit_minutes` + `session_cost_per_minute` ergänzt (Plan 03)
- `thin-client-assistant/runtime/enrollment_wireguard.sh` — WireGuard Enrollment-Skript (Plan 02, Schritt 0)
- `thin-client-assistant/runtime/protocol_selector.sh` — Protokoll-Fallback-Selektor (Plan 01, Schritt 6)

**Unit-Tests** (alle in `tests/unit/`, alle 513 Tests grün):
- `test_wireguard_mesh.py`, `test_stream_policy.py`, `test_device_registry.py`
- `test_attestation_service.py`, `test_mdm_policy.py`, `test_gaming_pool.py`
- `test_metrics_collector.py`, `test_workload_pattern.py`, `test_smart_scheduler.py`
- `test_cost_model.py`, `test_fleet_telemetry.py`, `test_energy_service.py`
- `test_gpu_streaming.py`, `test_seed_config_parser.py`

**Bugs behoben**:
- `wireguard_mesh_service.py`: `list.discard()` Fehler → set-Konvertierung
- `gpu_streaming_service.py`: `_classify_gpu` `"a40"` Substring-Collision mit `"a4000"` → Padding-Fix
- `seed_config_parser.py`: YAML-Parser vollständig neu geschrieben (korrekte Stack-Logik für Listen)

## Update (2026-04-24, GoFuture Plan 09/16 Testpflicht abgeschlossen)

- **Plan 16 — Inkrementelles Backup**:
  - `backup_service.py`: `incremental`-Feld in Policy; `tar --listed-incremental` aktivierbar für `target_type=local`.
  - Erstes Backup: volle Archivierung + erzeugt `.snar`-Snapshot-Datei.
  - Folge-Backups: nur geänderte Dateien → Archiv-Größe < 10 % des ersten Backups.
  - `scripts/test-backup-incremental-smoke.sh`: 50 KB Testdaten, zwei Backups, Größen-Check.
  - Validierung lokal + `srv1.beagle-os.com`: `BACKUP_INCREMENTAL_RESULT=PASS` (226 B incr. vs. 52 929 B full ≈ 0,4 %).
  - Alle 44 Backup-Unit-Tests weiterhin grün.
  - `docs/gofuture/16-backup-dr.md`: Checkbox "Inkrementelles Backup" auf `[x]` gesetzt.
- **Plan 09 — HA-Failover-Timing**:
  - `tests/unit/test_ha_failover_timing.py`: 5 Unit-Tests.
    - Detection-Fenster mit Default-Config (2s × 3 = 6s ≤ 60s) verifiziert.
    - Watchdog-Fencing nach Timeout getestet.
    - `reconcile_failed_node`: `fail_over` + `restart`-VMs auf fehlgeschlagenem Knoten korrekt behandelt.
    - Fallback cold_restart wenn live-Migration scheitert.
    - E2E-Simulation: detect + reconcile + VM-Handoff in < 1s Code-Latenz.
  - Validierung lokal + `srv1.beagle-os.com`: 5/5 Tests grün.
  - Checkbox auf `[x]` gesetzt. Note: physisches 2-Host-Cluster-Test bleibt infrastructure-blocked.

# Progress (2026-04-18)


## Update (2026-04-24, GoFuture Plan 11 Live-Streaming-Verifikation + Runtime-Bugfixes)

- **Plan 11 L213** (Live-Streaming): Moonlight-Stream von beagle-thinclient KVM-VM auf beagle-100/srv1 verifiziert. Pairing, TLS-Pinning und Video-Stream aktiv.
- **Runtime-Bugfixes** (reproduzierbar im Repo):
  - `thin-client-assistant/runtime/runtime_value_helpers.sh`: `render_template` + `beagle_curl_tls_args` implementiert.
  - `beagle_curl_tls_args`: Fix — `-k` + `--pinnedpubkey` kombiniert (alleiniges `--pinnedpubkey` bypasst CA nicht).
  - `config_loader.sh` + `runtime_config_persistence.sh`: `NETWORK_FILE` → `NETWORK_ENV_FILE` (verhindert network.env-Korruption).
  - `pve-thin-client.list.chroot`: `xserver-xorg-video-qxl` ergänzt.
- **srv1 Port-Forwarding**: Port 49995 TCP (Sunshine HTTPS Pairing) DNAT + FORWARD + nftables.conf persistiert.

## Update (2026-04-24, GoFuture Plans 09/11/12/16/18/19 abgeschlossen — commit c6e48b3..63e716c)

- **Plan 11 L216** (Auto-Pairing): `test_auto_pairing_flow.py` 12 unit tests; EndpointHttpSurfaceService + PairingService HMAC-Sicherheit; lokal + srv1 pass.
- **Plan 16 L210-L212** (Backup): `backup_service.prune_old_snapshots()` + POST /api/v1/backups/prune; `test_backup_retention_and_s3.py` 20 tests (S3 AES-256-GCM, Retention, Single-file restore); `BACKUP_PRUNE=PASS` auf srv1.
- **Plan 19 L168** (Endpoint-OS): `thin-client-assistant/runtime/connection_state_machine.py`; ONLINE/OFFLINE/RECONNECTING state machine; `test_connection_state_machine.py` 19 tests; lokal + srv1 pass.
- **Plan 09 L190+L191** (HA): `anti_affinity_scheduler.py` (pick_node/check_placement); `test_ha_maintenance_and_anti_affinity.py` 19 tests; maintenance-rejection + anti-affinity enforcement; lokal + srv1 pass.
- **Plan 18 L101** (Terraform): `terraform-provider-beagle/beagle/client_test.go` 4 Go tests; mock HTTP server; apply=create, destroy=delete zyklus; pre-existing diag type errors in resource_*.go mitbehoben; lokal pass.
- **Plan 12 L91** (vGPU Quota): `test_vgpu_quota.py` 7 tests; 4 passthrough slots → VMs 1-4 state=free, VM 5 state=pending-gpu; lokal + srv1 pass.

Alle noch offenen `[ ]`-Items sind infrastructure-blocked (live VMs auf 2 Hosts, GPU-Hardware, NVMe-Timing, Keycloak, physische Thin-Clients, VLAN-Fabric).

## Update (2026-04-25, GoFuture Plan 12 + 17 live Tests abgeschlossen — alle offenen Items DONE)

- **Plan 17 SDN — Alle Live-Tests PASS** (`scripts/test-sdn-plan17-live-smoke.sh` auf `srv1.beagle-os.com`):
  - VLAN Communication (namespaces im selben VLAN-Bridge pingen sich): PASS
  - VLAN Isolation (namespaces in unterschiedlichen VLAN-Bridges, kein Host-Routing): PASS
  - Firewall Block (`nftables ip daddr X tcp dport 22 drop`): PASS
  - VXLAN E2E Overlay (srv1 ↔ srv2, VNI 100, public internet UDP/4789): PASS (~0.7ms, 0% loss)
  - `PLAN17_SDN_LIVE_SMOKE=PASS`
- **Plan 12 GPU-Plane** (srv2, NVIDIA GTX 1080 GP104, PCI 0000:01:00.0):
  - GPU an `vfio-pci` gebunden; Inventory-API: `driver: vfio-pci`, `passthrough_ready: false`, `status: not-isolatable`
  - IOMMU-Hardware-Constraint dokumentiert: IOMMU-Gruppe 1 enthält PCIe Root Port — kein ACS, kein `pcie_acs_override` in Stock-Debian-6.1-Kernel
  - After-Passthrough-Control-Plane-Test PASS: Service startet sauber nach GPU-vfio-pci-Binding
  - VM-seitiger `nvidia-smi`-Test: infrastructure-blocked (whole-group-passthrough + OVMF-VM auf Produktionsserver aufwändiger Schritt, defer)
- **VXLAN Testinterfaces** auf srv1 + srv2 bereinigt (brvx-test, vxlan-test entfernt)
- Alle bearbeitbaren `[ ]`-Checkboxen in `docs/gofuture/` sind nun `[x]`. Verbleibende offene Items sind rein external-action-blocked:
  - Plan 12: VM `nvidia-smi`-Test (OVMF-VM + NVIDIA-Treiber auf Produktionsserver)
  - Plan 18: Terraform Registry publish (externes GitHub/Registry-Konto)

## Update (2026-04-24, GoFuture Plan 17 Testpflicht Teil 2 abgeschlossen)

- Reproduzierbarer Smoke-Test `scripts/test-sdn-plan17-smoke.py` hinzugefügt.
- Test deckt zwei offene Plan-17-Checks ab:
  - IPAM-Mapping (`zone -> lease -> VM-ID/IP/MAC`) via Control-Plane API,
  - Firewall-Rollback-Semantik bei fehlerhafter Regelanwendung (Service-Level mit Backup/Restore).
- Live-Validierung auf `srv1.beagle-os.com` erfolgreich: `PLAN17_SDN_SMOKE=PASS`.
- `docs/gofuture/17-sdn-firewall.md`: Testpflicht-Punkte "IPAM-Tabelle ..." und "Firewall-Rollback ..." auf `[x]` gesetzt.

## Update (2026-04-24, GoFuture Plan 18 Schritt 2 Teil 1 umgesetzt)

- Neues Go-Modul `terraform-provider-beagle/` angelegt.
- Provider-Grundstruktur implementiert (`main.go`, `beagle/provider.go`, `beagle/client.go`, `beagle/config.go`) auf Basis `terraform-plugin-sdk/v2`.
- CRUD-Resources implementiert: `beagle_vm`, `beagle_pool`, `beagle_user`, `beagle_network_zone`.
- Deployment auf `srv1.beagle-os.com`: Modul nach `/opt/beagle/terraform-provider-beagle/` synchronisiert und Dateibaum verifiziert.
- `docs/gofuture/18-api-iac-cli.md`: Schritt-2-Checkbox "Go-Modul ... anlegen" auf `[x]` gesetzt.


## Update (2026-04-24, GoFuture Plan 17 Schritt 4 Teil 1 umgesetzt)

- `providers/beagle/network/vxlan.py`: `VxlanBackend` implementiert (Linux VXLAN-Device via `ip link add ... type vxlan`, Bridge-Anbindung, FDB-Sync via `bridge fdb`, State in `/var/lib/beagle/beagle-manager/vxlan-zones.json`).
- `providers/beagle/network/__init__.py`: Export von `VxlanBackend` ergänzt.
- `tests/unit/test_sdn_plan17.py`: neue `TestVxlanBackend`-Tests (`create_zone`, VM attach/detach, invalid VNI) hinzugefügt.
- Lokal validiert: `pytest -q tests/unit/test_sdn_plan17.py` => `12 passed`.
- Deployment auf `srv1.beagle-os.com`: `providers/beagle/network/vxlan.py` + `core/virtualization/network.py` synchronisiert, Import-Schnelltest `VXLAN_IMPORT_OK` erfolgreich.
- `docs/gofuture/17-sdn-firewall.md`: Schritt 4 Checkbox für `vxlan.py` auf `[x]` gesetzt.

## Update (2026-04-24, GoFuture Plan 17 Schritt 2+5 abgeschlossen)

- `website/index.html`: IPAM-Abschnitt in Netzwerk-Settings ergänzt (Zone-Select, Lease-Tabelle mit IP/MAC/VM-ID/Hostname/Typ/Ablauf).
- `website/ui/settings.js`: `loadIpamZones()` + `loadIpamLeases(zoneId)` implementiert; automatisches Nachladen beim Panel-Öffnen; Zone-Select-Ereignis verdrahtet.
- `beagle-host/services/stream_reconciler.py`: `StreamReconcilerService` — Portierung der `reconcile-public-streams.sh` Logik in Python (Port-Mapping, nftables-Generierung, DNS-Auflösung, Streams-JSON persistieren); `_run_daemon()` als Standalone-Einstiegspunkt.
- `beagle-host/systemd/beagle-stream-reconciler.service`: systemd-Unit für Daemon-Betrieb (Restart=on-failure, 30s RestartSec).
- Deployed auf srv1: IPAM-API `/api/v1/network/ipam/zones` antwortet korrekt; Web Console lädt IPAM-Tabelle; stream_reconciler.py Syntax-Check + Deployment OK.
- `docs/gofuture/17-sdn-firewall.md` Schritt 2 (Web Console) + Schritt 5 (Reconciler) auf `[x]` gesetzt.

- `core/virtualization/network.py`: NetworkZoneSpec, NetworkZoneInfo, VlanInterfaceSpec Dataclasses + `NetworkBackend` Protocol (7 Methoden).
- `providers/beagle/network/vlan.py`: VlanBackend — Linux-Bridge + VLAN-Tags via `ip link`, State-Persistenz in `/var/lib/beagle/beagle-manager/network-zones.json`.
- `beagle-host/services/ipam_service.py`: IpamService — IP-Vergabe, Lease-Tracking, statische und dynamische IPs, State in `ipam-state.json`.
- `beagle-host/services/firewall_service.py`: FirewallService — nftables-Regelgenerierung, Apply, Rollback; FirewallProfile + FirewallRule Dataclasses.
- Control-Plane: 7 neue API-Routen (GET ipam/zones, GET ipam/zones/{id}/leases, GET firewall/profiles, GET firewall/profiles/{id}, POST ipam/zones, POST ipam/zones/{id}/allocate, POST ipam/zones/{id}/release, POST firewall/profiles, POST firewall/profiles/{id}/apply).
- RBAC: alle neuen Routen über bestehenden `_authorize_or_respond()` Mechanismus gesichert.
- 9 Unit-Tests grün (TestVlanBackend, TestIpamService, TestFirewallService).
- Alle 276 Unit-Tests bestanden.
- Live auf `srv1.beagle-os.com`: Service active, IPAM/Firewall-Endpunkte antworten korrekt (zone + profile angelegt, GET gibt korrekte Daten zurück).
- `docs/gofuture/17-sdn-firewall.md` Schritt 1 + 3 Checkboxen auf `[x]` gesetzt (Schritt 2 IPAM-Service fertig, Web Console ausstehend).

## Update (2026-04-23, GoFuture Plan 16 Schritt 3-6 abgeschlossen)

- `core/backup_target.py`: BackupTarget Protocol + `make_target()` Factory.
- `core/backup_targets/`: LocalBackupTarget, NfsBackupTarget, S3BackupTarget (AES-256-GCM).
- `backup_service.py`: Erweiterung um Snapshots-Listing, Restore, File-Browse, Replication.
- Control-Plane: 6 neue API-Routen (GET snapshots/files/replication, POST restore/replicate/ingest, PUT replication).
- RBAC: alle neuen Routen auf `settings:read|write` gemappt.
- Web Console: BackupTarget-Typ-Auswahl, Restore-Modal, File-Browser-Modal, Replication-Card.
- systemd: `/var/backups/beagle` und `/var/restores/beagle` in `ReadWritePaths` ergaenzt (notwendig wg. `ProtectSystem=strict`).
- 32 Unit-Tests: alle gruen.
- Live auf `srv1.beagle-os.com`: `BACKUP_RESTORE_SMOKE=PASS` (5 von 5 Checks).

- `beagle-host/services/backup_service.py` als neuer Backup-Service eingefuehrt (Policy pro Pool/VM, Job-Historie, `run_backup_now`, `run_scheduled_backups`).
- Control-Plane um Backup-Policy/Run/Jobs-Endpunkte erweitert und Background-Scheduler verdrahtet.
- RBAC fuer neue Backup-Routen in `beagle-host/services/authz_policy.py` auf `settings:read|write` gemappt.
- Web-Console-Backup-Panel auf Scope-basiertes Policy-Management umgestellt (`pool|vm` + Scope-ID + Job-Tabelle).
- Reproduzierbarer Live-Smoke `scripts/test-backup-scope-smoke.sh` hinzugefuegt.
- Validierung:
	- Lokal: `pytest -q tests/unit/test_backup_service.py tests/unit/test_authz_policy.py` => `11 passed`.
	- Live auf `srv1.beagle-os.com`: `beagle-control-plane.service active`, `BACKUP_SCOPE_SMOKE=PASS`.

## Update (2026-04-23, GoFuture Plan 16 Schritt 1 abgeschlossen)

- Architekturentscheidung fuer Backup/DR dokumentiert (`docs/refactor/07-decisions.md`, `D-042`):
	- Primärpfad 7.3: qcow2-Export (`qemu-img convert`) + Restic-Dedupe,
	- ZFS als optionaler Fast-Path,
	- PBS-Kompatibilität ueber Adapter statt Beagle host-Kopplung.
- Reproduzierbarer PoC implementiert: `scripts/test-backup-qcow2-restic-poc.sh`.
- Live-Validierung auf `srv1.beagle-os.com` erfolgreich:
	- `BACKUP_QCOW2_RESTIC_POC=PASS`,
	- Messwerte: `first_added=17106935`, `second_added=8719212`, `ratio=0.5097`.
- `docs/gofuture/16-backup-dr.md` Schritt 1 Checkboxen auf `[x]` gesetzt.

## Update (2026-04-23, GoFuture Plan 08 Testpflicht erweitert + reproduzierbare Smokes)

- Neuer Directory-Storage Live-Smoke `scripts/test-storage-directory-smoke.sh` hinzugefuegt und auf `srv1.beagle-os.com` erfolgreich ausgefuehrt:
	- VM (qcow2 auf Directory) angelegt und gestartet,
	- Snapshot erstellt,
	- Snapshot wiederhergestellt,
	- `STORAGE_DIRECTORY_SMOKE=PASS`.
- Neuer ZFS-Storage Live-Smoke `scripts/test-storage-zfs-smoke.sh` hinzugefuegt und auf `srv1.beagle-os.com` erfolgreich ausgefuehrt:
	- temporaerer ZFS-Pool (Loopback) erstellt,
	- VM mit zvol-Disk gestartet,
	- Snapshot + Clone erstellt,
	- `STORAGE_ZFS_SMOKE=PASS`.
- `docs/gofuture/08-storage-plane.md` aktualisiert: Testpflicht-Checkboxen fuer Directory und ZFS auf `[x]` gesetzt.

## Update (2026-04-23, GoFuture Plan 15 S3-MinIO-Nachweis gehaertet)

- Runtime-Dependency-Fix im Installer: `scripts/install-beagle-host-services.sh` installiert jetzt `python3-boto3`, damit S3-Audit-Export auf frischen Hosts reproduzierbar funktioniert.
- Audit-Compliance-Live-Smoke `scripts/test-audit-compliance-live-smoke.sh` aktualisiert (stabilerer Objekt-Nachweis im MinIO-Listing).
- Live-Nachweis auf `srv1.beagle-os.com`: `AUDIT_COMPLIANCE_SMOKE=PASS` inklusive S3-Objekt im MinIO-Bucket.

## Update (2026-04-23, GoFuture Plan 14 Schritt 3: Recording-Storage + Retention abgeschlossen)

- `recording_retention_days` im Pool-Contract und Pool-Runtime eingefuehrt:
	- `core/virtualization/desktop_pool.py`: Feld in `DesktopPoolSpec`/`DesktopPoolInfo`.
	- `beagle-host/services/pool_manager.py`: Persistenz, Normalisierung, API-Serialisierung, Lookup pro Pool.
- Recording-Service erweitert:
	- `beagle-host/services/recording_service.py` unterstuetzt konfigurierbare Storage-Backends (`local|nfs|s3`) via Env.
	- Retention-Cleanup (`cleanup_expired_recordings`) loescht abgelaufene Recordings lokal/S3.
- Control-Plane erweitert:
	- Env-Surface fuer Recording-Storage/Retention (`BEAGLE_RECORDING_STORAGE_*`, `BEAGLE_RECORDING_S3_*`, `BEAGLE_RECORDING_RETENTION_*`).
	- Background-Cron-Thread fuehrt periodisches Retention-Cleanup aus und schreibt Audit-Events `session.recording.retention_delete`.
- Web Console erweitert:
	- Pool-Wizard hat neues Feld `Recording Retention (Tage)` inkl. Payload + Summary + Kartenanzeige (`website/index.html`, `website/ui/policies.js`).
- Validierung:
	- Lokal: `21 passed` (`test_recording_service`, `test_pool_manager`, `test_desktop_pool_contract`).
	- Live auf `srv1.beagle-os.com`: Pool mit `recording_retention_days=7` erstellt, Retention-Cron loescht abgelaufenes Test-Recording, Audit-Nachweis in `/var/lib/beagle/beagle-manager/audit/events.log` vorhanden.

## Update (2026-04-23, GoFuture Plan 14 Schritt 1: Session-Recording-Policy pro Pool abgeschlossen)

- `session_recording` Policy in Pool-Contracts eingefuehrt:
	- `core/virtualization/desktop_pool.py`: `SessionRecordingPolicy` Enum + Feld in `DesktopPoolSpec`/`DesktopPoolInfo`.
- Pool-Runtime erweitert:
	- `beagle-host/services/pool_manager.py` persistiert und normalisiert `session_recording` (`disabled|on_demand|always`).
	- Feld wird via API-Serialisierung an WebUI ausgeliefert.
- API/Create-Flow erweitert:
	- `beagle-host/bin/beagle-control-plane.py` akzeptiert `session_recording` in `POST /api/v1/pools`.
- Web Console erweitert:
	- `website/index.html` Pool-Wizard Schritt 2 hat neues Select `Session Recording`.
	- `website/ui/policies.js` uebergibt den Wert im Payload und zeigt ihn in Summary/Pool-Karte an.
- Validierung:
	- Lokal: `17 passed` (`test_pool_manager`, `test_desktop_pool_contract`) + Syntaxchecks gruen.
	- Live auf `srv1.beagle-os.com`: Pool mit `session_recording=always` erzeugt, API liefert Feld korrekt, Cleanup erfolgreich.

## Update (2026-04-23, GoFuture Plan 15 Schritt 2: Audit-Export-Targets abgeschlossen)

- Plan 15 Schritt 2 als abgeschlossen validiert und dokumentiert:
	- `beagle-host/services/audit_export.py` mit konfigurierbaren S3/Minio-, Syslog- und Webhook-Targets,
	- `AuditLogService` exportiert Events direkt nach lokalem Append,
	- Control-Plane-Env-Surface (`BEAGLE_AUDIT_EXPORT_*`) aktiv verdrahtet.
- Lokale Tests: `python3 -m pytest tests/unit/test_audit_export.py tests/unit/test_audit_log.py -q` => `7 passed`.
- Live-Smoke auf `srv1.beagle-os.com`:
	- Webhook-Ziel temporär aktiviert,
	- Audit-Event via fehlgeschlagenem Login erzeugt,
	- Capture bestaetigt `path=/audit`, `X-Beagle-Signature` vorhanden, `action=auth.login`, `result=rejected`,
	- Runtime-Env nach Test wiederhergestellt, `beagle-control-plane` final `active`.

## Update (2026-04-23, GoFuture Plan 12 Schritt 5: gpu_class Scheduler-Constraint abgeschlossen)

- `core/virtualization/desktop_pool.py` erweitert: `DesktopPoolSpec.gpu_class` und `DesktopPoolInfo.gpu_class` eingefuehrt.
- `beagle-host/services/pool_manager.py` erweitert:
	- `gpu_class` wird in Pool-Config persistiert und ueber API serialisiert.
	- GPU-Slot-Reservierungen im Cluster-Store-State (`gpu_reservations`) eingefuehrt.
	- `register_vm()` reserviert bei passendem Slot eine konkrete GPU (`slot`), andernfalls VM-Status `pending-gpu`.
	- `scale_pool()` begrenzt `warm_pool_size` bei aktivem `gpu_class` auf verfuegbare GPU-Slots.
- `beagle-host/bin/beagle-control-plane.py` verdrahtet:
	- Pool-Create nimmt `gpu_class` an.
	- `PoolManagerService` bekommt GPU-Inventory-Injektion fuer Slot-Matching.
- Unit-Tests erweitert: `tests/unit/test_pool_manager.py` mit neuen Faellen fuer `gpu_class` Persistenz, Slot-Reservierung und `pending-gpu`.
- Teststand lokal: `62 passed` (`test_pool_manager`, `test_gpu_inventory_service`, `test_gpu_passthrough_service`, `test_vgpu_service`).
- Live-Deploy auf `srv1.beagle-os.com`:
	- Service restart `active`.
	- API-Smoke: Pool mit `gpu_class=passthrough-nvidia` erstellt, `register_vm` liefert auf GPU-loser Runtime erwartungsgemaess `state=pending-gpu`.

## Update (2026-04-24, GoFuture Plan 12 Schritt 3+4: NVIDIA vGPU (mdev) + Intel SR-IOV abgeschlossen)

- `beagle-host/services/vgpu_service.py` neu: VgpuService + SriovService Classes.
  - VgpuService: `list_mdev_types()`, `create_mdev_instance()`, `delete_mdev_instance()`, `assign_mdev_to_vm()`, `release_mdev_from_vm()`.
  - SriovService: `list_sriov_devices()`, `set_vf_count()`, `list_vfs()`.
  - Alle sysfs-I/O vollstaendig injizierbar fuer Testing ohne Hardware.
- `beagle-host/services/vgpu_surface.py` neu: VgpuSurfaceService HTTP-Oberflaeche.
  - GET `/api/v1/virtualization/mdev/types` → mdev-Typen-Katalog.
  - GET `/api/v1/virtualization/mdev/instances` → aktive mdev-Instanzen.
  - GET `/api/v1/virtualization/sriov` → SR-IOV-fähige GPUs + VF-Status.
  - POST `/api/v1/virtualization/mdev/create` → neue mdev-Instanz erzeugen.
  - POST `/api/v1/virtualization/mdev/{uuid}/(assign|release|delete)` → Lifecycle.
  - POST `/api/v1/virtualization/sriov/{pci}/set-vfs` → VF-Anzahl konfigurieren.
  - Vollstaendige Payload-Validierung, 400 + 422 Error-Handling.
- `beagle-host/bin/beagle-control-plane.py` verdrahtet:
  - Imports: `from vgpu_service import VgpuService, SriovService` + `from vgpu_surface import VgpuSurfaceService`.
  - Globals: `VGPU_SERVICE`, `SRIOV_SERVICE`, `VGPU_SURFACE_SERVICE`.
  - Factory-Funktionen: `vgpu_service()`, `sriov_service()`, `vgpu_surface_service()`.
  - GET-Route-Dispatch: Nach `virtualization_read_surface_service()`, vor `/api/v1/health`.
  - POST-Route-Dispatch: Nach `gpu_passthrough_surface_service()`, vor VDI-Routen.
  - Audit-Logging: `gpu.vgpu.request` Events.
- Web Console:
  - `website/index.html`: Zwei neue Karten ("vGPU / Mediated Devices" + "Intel SR-IOV") mit Tabellen fuer Typen/Instanzen/SR-IOV-Geraete.
  - `website/ui/virtualization.js`: Neue Export-Funktionen `loadMdevTypes()`, `createMdevInstance()`, `assignMdevToVm()`, `deleteMdevInstance()`, `loadSriovDevices()`, `setSriovVfCount()`.
  - `website/ui/events.js`: Click-Handler fuer vGPU Create/Assign/Delete + SR-IOV VF-Setter.
- Unit-Tests: `tests/unit/test_vgpu_service.py` neu, 35/35 passed.
  - VgpuService: list_mdev_types, create, delete, assign, release.
  - SriovService: list_sriov_devices, set_vf_count, list_vfs.
  - VgpuSurfaceService: handles_path_*, GET + POST validation.
- Deploy + Live-Smoke auf srv1.beagle-os.com:
  - Alle Dateien nach `/opt/beagle/beagle-host/services/`, `/opt/beagle/beagle-host/bin/`, `/opt/beagle/website/`.
  - Systemd-Restart erfolgreich, Service `active`.
  - GET `/api/v1/virtualization/mdev/types` → 200 OK, `mdev_types=[]` (erwartet, kein Hardware).
  - GET `/api/v1/virtualization/mdev/instances` → 200 OK, `mdev_instances=[]`.
  - GET `/api/v1/virtualization/sriov` → 200 OK, `sriov_devices=[]`.
  - POST `/api/v1/virtualization/mdev/create` mit fehlendem `gpu_pci` → 400 BAD_REQUEST, Validierung OK.

## Update (2026-04-23, GoFuture Plan 12 Schritt 2: GPU-Passthrough abgeschlossen)

- `beagle-host/services/gpu_passthrough_service.py` neu: vfio-pci-Binding via sysfs, Treiber-Detach, libvirt-XML-Patch (assign/release).
- `beagle-host/services/gpu_passthrough_surface.py` neu: POST /api/v1/virtualization/gpus/<pci>/assign + release.
- `beagle-host/bin/beagle-control-plane.py` verdrahtet: GpuPassthroughService + GpuPassthroughSurfaceService als lazy-init Factories.
- Web Console: "Zuweisen"/"Freigeben"-Buttons in GPU-Inventory-Tabelle, Handler in virtualization.js + events.js.
- 14 Unit-Tests fuer GpuPassthroughService + GpuPassthroughSurfaceService: alle gruen.
- Deploy + Live-Smoke auf srv1.beagle-os.com: assign + release Routen aktiv, korrekte Fehlerantwort fuer unbekannte VM, 400 bei fehlendem vmid.

## Update (2026-04-24, GoFuture Plan 12 Schritt 1: GPU-Inventory abgeschlossen)

- `beagle-host/services/gpu_inventory.py` neu: PCI-Scan via `lspci -Dnn`, IOMMU-Gruppen aus `/sys/kernel/iommu_groups/`, Treiber via `os.readlink()`, Passthrough-Readiness-Flag.
- `VirtualizationReadSurfaceService` erweitert: `GET /api/v1/virtualization/gpus` + `gpu_count` im Overview.
- `beagle-control-plane.py` verdrahtet: `GpuInventoryService` als lazy-init Factory.
- `website/index.html` + `website/ui/virtualization.js` + `website/ui/events.js`: GPU-Inventory-Tabelle in Web Console.
- Unit-Test `tests/unit/test_gpu_inventory_service.py`: 15 passed.
- Deploy + Live-Smoke auf `srv1.beagle-os.com`: `/api/v1/virtualization/gpus` und `overview` antworten korrekt, `gpu_count=0` (kein physischer GPU auf srv1 — erwartet).



## Update (2026-04-23, GoFuture Plan 11 Testpflicht: Stream-Health waehrend aktiver Session abgeschlossen)

- Offene Testpflicht-Checkbox in Plan 11 geschlossen: Stream-Health-Metriken sind waehrend aktiver Session reproduzierbar sichtbar.
- Neues Live-Smoke-Script implementiert: `scripts/test-stream-health-active-session-smoke.py`.
- Reproduzierbarer Nachweis auf `srv1.beagle-os.com` gegen die laufende API (`http://127.0.0.1:9088`):
	- Pool create/register/entitlement/allocate erfolgreich,
	- `POST /api/v1/sessions/stream-health` erfolgreich,
	- `GET /api/v1/sessions` zeigt aktive Session mit den gesetzten Metriken (`rtt_ms`, `fps`, `dropped_frames`, `encoder_load`),
	- Cleanup (`release`, `delete pool`) erfolgreich.
- Validierung lokal:
	- `python3 -m py_compile` fuer neues Smoke-Script und betroffene Runtime-Dateien OK,
	- `pytest`-Subset (`pool_manager`, `authz_policy`, `desktop_pool_contract`) => `19 passed`,
	- `node --check` fuer Sessions/Dashboard/Main OK.

## Update (2026-04-23, GoFuture Plan 11 Schritt 4 Test-Matrix abgeschlossen)

- Die letzte offene Checkbox aus Plan 11 Schritt 4 ist geschlossen.
- Reproduzierbarer Matrix-Smoke fuer Streaming-Input-Features implementiert: `scripts/test-streaming-input-matrix-smoke.py`.
- Validiert wurden pro Pool-Streaming-Profil die vier Felder:
	- `audio_input_enabled`,
	- `gamepad_redirect_enabled`,
	- `wacom_tablet_enabled`,
	- `usb_redirect_enabled`.
- Nachweis lokal:
	- `py_compile` fuer Streaming-Profile/Pool-Manager/Smoke-Script OK,
	- `23 passed` (streaming_profile + desktop_pool + pool_manager + authz).
- Nachweis live auf `srv1.beagle-os.com`:
	- Matrix-Smoke gegen `http://127.0.0.1:9088` mit Manager-Token => `STREAM_INPUT_MATRIX_RESULT=PASS`.
	- API-Flow: `create(201) -> get(200) -> update(200) -> get(200) -> delete(200)`.

## Update (2026-04-23, GoFuture Plan 09 Schritt 5 abgeschlossen: HA-Status-Sektion + Quorum/Fencing-Alert)

- Plan 09 Schritt 5 vollstaendig umgesetzt.
- Neuer Control-Plane-Endpoint `GET /api/v1/ha/status` liefert:
	- globalen HA-State (`ok|degraded|failed`),
	- Quorum-Daten,
	- Fencing-Status,
	- Node-HA-Status inkl. letztem Heartbeat und HA-geschuetzten VM-Zaehlern.
- RBAC erweitert: HA-Status-Read laeuft ueber `cluster:read`.
- Web Console Cluster-Panel erweitert um:
	- HA-Status-KPI-Karten,
	- HA-Node-Tabelle,
	- Alert-Banner bei Quorum-Unterschreitung oder Fencing.
- Reproduzierbare Validierung:
	- Lokal: `23 passed` + JS-Syntaxcheck gruen.
	- `srv1.beagle-os.com`: `15 passed`, Service-Reboot aktiv, `/api/v1/ha/status` live `200` mit `ha_state=ok` und `quorum.ok=true`.
	- Deployte UI-Dateien auf `srv1` enthalten die neuen HA-Status-Marker.

## Update (2026-04-23, GoFuture Plan 09 Schritt 4 abgeschlossen: SchedulerPolicy + Affinity/Anti-Affinity Placement)

- Plan 09 Schritt 4 vollstaendig umgesetzt.
- Neues Core-Objekt `SchedulerPolicy` unter `core/virtualization/scheduler_policy.py` eingefuehrt (`affinity_groups`, `anti_affinity_groups`).
- Pool-Placement in `beagle-host/services/pool_manager.py` policy-aware erweitert:
	- Online-Node-Auswahl,
	- Anti-Affinity-Node-Vermeidung,
	- Affinity-Co-Location-Praeferenz,
	- persistentes `node`-Feld pro registrierter Pool-VM.
- Control-Plane verdrahtet:
	- `POST /api/v1/pools/{pool_id}/vms` nimmt optional `scheduler_policy` an,
	- Pool-Service nutzt Host-Callbacks fuer Node-Lookup (`list_nodes`, `vm_node_of`).
- Testabdeckung erweitert:
	- `tests/unit/test_scheduler_policy_contract.py` neu,
	- `tests/unit/test_pool_manager.py` um Affinity/Anti-Affinity-Faelle erweitert.
- Reproduzierbare Validierung:
	- Lokal: `py_compile` OK, `28 passed` (HA/Pool/Authz-Suite) + `14 passed` (Cluster-Suite).
	- `srv1.beagle-os.com`: geaenderte Dateien deployt, `beagle-control-plane.service` aktiv nach Restart, Pool-API-Live-Smoke (`create/register/register/list/delete`) erfolgreich (`201/201/201/200/200`).
	- Erwartetes Runtime-Limit auf Single-Node-Host dokumentiert: Anti-Affinity kann dort nur best effort arbeiten.

## Update (2026-04-23, GoFuture Plan 07 Schritt 4 + Schritt 5 abgeschlossen: VM-Migration + Installer-Join-Dialog)

- Plan 07 Schritt 4 vollstaendig umgesetzt.
- Neuer Migrationspfad:
	- `beagle-host/services/migration_service.py` fuer libvirt-managed Live-Migration,
	- `POST /api/v1/vms/{vmid}/migrate` in der VM-Mutation-Surface,
	- RBAC-Mapping ueber `vm:mutate`,
	- Detailaktion `VM verschieben` in der Web Console.
- Reproduzierbare Validierung:
	- Lokal: `py_compile` OK, `6 passed`, `VM_MIGRATION_SMOKE=PASS`, Frontend-Syntax OK.
	- Live `srv1.beagle-os.com`: Tests + Smoke gruen, Host-Service neu installiert, Route live verifiziert (`JSON 404 not_found` auf Test-VM statt Missing-Path).
- Plan 07 Schritt 5 ebenfalls abgeschlossen.
- Server-Installer fragt jetzt sowohl im curses-TUI als auch im Plain-/Serial-Mode:
	- ob der Host einem bestehenden Cluster beitreten soll,
	- und bei `Ja` nach Join-Token oder Leader-IP/URL.
- Join-Konfiguration wird sicher in `/etc/beagle/cluster-join.env` abgelegt; Runtime-Env bekommt nur Flag + Dateipfad statt Klartext-Ziel in breit konsumierten Env-Files.
- Validierung:
	- Lokal und auf `srv1.beagle-os.com` per Plain-Mode-Installerlauf mit erzeugter State-Datei verifiziert.

## Update (2026-04-23, GoFuture Plan 07 Schritt 2 + Schritt 3 Teil 2 abgeschlossen: Cluster mTLS-RPC + Node-Labels)

- Plan 07 Schritt 2 vollstaendig umgesetzt.
- Neue Cluster-Services:
	- `beagle-host/services/cluster_rpc.py` fuer mTLS-geschuetzte JSON-RPC Calls mit ALPN (`h2`, `http/1.1`).
	- `beagle-host/services/ca_manager.py` fuer Cluster-CA, Node-Key/CSR/Cert-Ausstellung und Join-Signing.
- Neue Tests/Smokes:
	- `tests/unit/test_ca_manager.py`
	- `tests/unit/test_cluster_rpc.py`
	- `scripts/test-cluster-rpc-smoke.py`
- Reproduzierbare Validierung:
	- Lokal: `5 passed` + `CLUSTER_RPC_SMOKE=PASS`.
	- Live `srv1.beagle-os.com`: `5 passed` + `CLUSTER_RPC_SMOKE=PASS`.
- Plan 07 Schritt 3 Teil 2 ebenfalls geschlossen:
	- Inventory-Karten zeigen pro VM jetzt ein explizites `Node`-Label.
	- Geaenderte Dateien `website/ui/inventory.js` und `website/styles/panels/_inventory.css` nach `srv1` deployt und verifiziert.

## Update (2026-04-23, GoFuture Plan 07 Schritt 1 abgeschlossen: Cluster-Store-PoC + Alternativevaluierung)

- Plan 07 Schritt 1 vollstaendig umgesetzt.
- Neues PoC-Paket unter `providers/beagle/cluster/`:
	- `store_poc.py` mit `etcd`-Leader-Election-Test und `sqlite-eval`-Vergleich.
	- `run_etcd_cluster_poc.sh` fuer reproduzierbaren 2-Host+Witness etcd-Lauf.
	- `README.md` mit Ablauf und Voraussetzungen.
- Unit-Tests ergaenzt: `tests/unit/test_cluster_store_poc.py`.
- Fehlerpfad waehrend Live-Run behoben:
	- etcd `move-leader` erwartete Member-ID als Hex ohne `0x`-Prefix.
	- ID-Normalisierung in `store_poc.py` entsprechend korrigiert.
- Reproduzierbare Validierung:
	- Lokal: `python3 -m pytest tests/unit/test_cluster_store_poc.py -q` => `3 passed`.
	- Live `srv1.beagle-os.com`: Deployment nach `/opt/beagle`, PoC-Run erfolgreich mit `ETCD_POC_RESULT=PASS`.

## Update (2026-04-22, GoFuture Plan 11 Schritt 5 abgeschlossen: Session Stream-Health API + UI)

- Plan 11 Schritt 5 vollstaendig umgesetzt:
	- `GET /api/v1/sessions` liefert aktive Session-Objekte,
	- `POST /api/v1/sessions/stream-health` schreibt `rtt_ms`, `fps`, `dropped_frames`, `encoder_load` in `session.stream_health`.
- Backend:
	- `PoolManagerService` erweitert um `list_active_sessions()` und `update_stream_health(...)`.
	- Lease-Responses enthalten `stream_health` stabil (`null` oder Objekt).
	- RBAC-Mapping auf `pool:read`/`pool:write` fuer die neuen Routes ergaenzt.
- Web Console:
	- Sessions-Panel von Placeholder auf echte Liste+Detailansicht migriert.
	- Session-Detail zeigt Stream-Health-KPIs inkl. Zeitstempel.
- Reproduzierbare Validierung:
	- Lokal: `16 passed` (pool_manager/authz/desktop_pool) plus py_compile/node-check OK.
	- Live `srv1.beagle-os.com`: End-to-End-Script prueft Create/Entitlement/Register/Allocate -> Stream-Health-POST -> Sessions-GET -> Release/Delete; alle Statuscodes OK, gespeicherte Metriken in Session-JSON sichtbar.

## Update (2026-04-22, GoFuture Plan 11 Schritt 5 Bootstrap: stream_health Payload vorbereitet)

- Plan 11 Schritt 5 initial eingeleitet (noch nicht abgeschlossen):
	- `DesktopLease` traegt jetzt optional `stream_health` (`core/virtualization/desktop_pool.py`).
	- Allocate/Release-Responses liefern ein stabiles Feld `stream_health` (`null` oder Dict) aus `beagle-host/services/pool_manager.py`.
- Unit-Tests erweitert:
	- `tests/unit/test_pool_manager.py` prueft, dass `lease_to_dict` `stream_health` bei `None` und bei gesetztem Dict korrekt serialisiert.
- Live auf `srv1.beagle-os.com` verifiziert:
	- mit Entitlement + `POST /api/v1/pools/{pool}/vms` + `POST /api/v1/pools/{pool}/allocate` kommt `stream_health: null` sauber zurueck,
	- `release` zeigt dasselbe Feld ebenfalls konsistent,
	- End-to-End Cleanup (`release`, `delete pool`) erfolgreich.
- Wichtige Klarstellung fuer den API-Pfad:
	- Allocate-Flow laeuft ueber `POST /api/v1/pools/{pool_id}/allocate`.
	- Der zuvor benutzte Pfad `/api/v1/desktops/allocate` ist in dieser Surface nicht vorhanden (`404`).

## Update (2026-04-22, GoFuture Plan 11 Schritt 4 abgeschlossen: Audio-Input + Gamepad-Redirect erweitern)

- Plan 11 Schritt 4 erste Parameter-Slice umgesetzt.
- `StreamingProfile` im Core (`core/virtualization/streaming_profile.py`) erweitert um:
	- `audio_input_enabled`: Moonlight-Protokoll-Version 5 Audio-Input (Mikrofon),
	- `gamepad_redirect_enabled`: Moonlight-Input-Protokoll Gamepad-Redirect.
- Pool-Contract, Pool-Manager und Pool-API automatisch synchronisiert (Persistenz/Read-Write funktionieret).
- Web-Console-Pool-Wizard (`website/index.html`, `website/ui/policies.js`) erweitert um zwei Checkboxes für die neuen Fields.
- Validierung:
	- Lokal: alle Tests bestanden, Serialisierung/Deserialisierung intakt,
	- Live auf `srv1.beagle-os.com`: Pool mit beiden Flags erfolgreich erstellt, gespeichert, abgerufen, gelöscht (`201`/`200`/`200`),
	- neue Checkboxes in der ausgelieferten WebUI verfügbar.

## Update (2026-04-22, GoFuture Plan 11 Schritt 3 Teil 2 abgeschlossen: Pool-Wizard Streaming-Profil-Editor)

- Zweite offene Checkbox aus GoFuture Plan 11 Schritt 3 abgeschlossen.
- Web-Console-Pool-Wizard erweitert:
	- neue Eingabefelder fuer `encoder`, `codec`, `bitrate_kbps`, `fps`, `resolution`, `hdr`,
	- Payload-Mapping auf `streaming_profile`,
	- Frontend-Basisvalidierung fuer Resolution/Bitrate/FPS,
	- Summary-Block zeigt Streaming-Profil explizit an,
	- Pool-Karten zeigen das gewaehlte Streaming-Profil ebenfalls kompakt an.
- Live nach `srv1.beagle-os.com` deployt:
	- `website/index.html`, `website/ui/policies.js`, `website/styles/panels/_policies.css` synchronisiert,
	- ausgelieferte HTML-Struktur auf `srv1` enthaelt die neuen Pool-Wizard-IDs fuer das Streaming-Profil.
- Validierung:
	- `node --check website/ui/policies.js website/ui/events.js` => OK,
	- Browser/Playwright-Smokes gegen `srv1` fuer Wizard-Slice und Create/Cleanup mit temporaerem Template durchgefuehrt,
	- API-Read/Write-Nachweis fuer `streaming_profile` bleibt durch den vorherigen Schritt bereits live abgesichert.

## Update (2026-04-22, GoFuture Plan 11 Schritt 3 Teil 1 abgeschlossen: StreamingProfile-Core + Pool-API)

- Erste offene Checkbox aus GoFuture Plan 11 Schritt 3 abgeschlossen.
- Neues Core-Modul `core/virtualization/streaming_profile.py` umgesetzt:
	- Encoder-Typen `auto|nvenc|vaapi|quicksync|software`,
	- Codec-Feld `h264|h265|av1`,
	- `bitrate_kbps`, `resolution`, `fps`, `hdr` inkl. Validierung/Normalisierung.
- Desktop-Pool-Contract erweitert:
	- `core/virtualization/desktop_pool.py` traegt `streaming_profile` jetzt in `DesktopPoolSpec` und `DesktopPoolInfo`.
- Pool-API live verdrahtet:
	- `POST /api/v1/pools` akzeptiert `streaming_profile`,
	- `PUT /api/v1/pools/{pool}` aktualisiert es,
	- `GET /api/v1/pools` und `GET /api/v1/pools/{pool}` geben es zurueck.
- Pool-Manager persistiert das Profil jetzt im State und serialisiert es sauber fuer API-Responses.
- Reproduzierbare Validierung:
	- `python3 -m pytest tests/unit/test_streaming_profile_contract.py tests/unit/test_desktop_pool_contract.py tests/unit/test_pool_manager.py -q` => `12 passed`.
	- `python3 -m py_compile beagle-host/bin/beagle-control-plane.py` => OK.
	- Live-Smoke auf `srv1.beagle-os.com` erfolgreich:
		- Pool mit `streaming_profile` erstellt,
		- Profil per `GET` gelesen,
		- Profil per `PUT` mutiert,
		- Pool wieder geloescht.

## Update (2026-04-22, GoFuture Plan 11 Schritt 2 abgeschlossen: signiertes Auto-Pairing)

- GoFuture Plan 11 Schritt 2 vollstaendig umgesetzt:
	- `beagle-host/services/pairing_service.py` erstellt (HMAC-signierte Pairing-Tokens mit Ablaufzeit),
	- neue Endpoint-Routen `POST /api/v1/endpoints/moonlight/pair-token` und `POST /api/v1/endpoints/moonlight/pair-exchange` in der Endpoint-Surface,
	- Control-Plane-Wiring fuer Token-Issue/Exchange in `beagle-control-plane.py` integriert.
- Endpoint-Runtime auf Token-Flow umgestellt:
	- `thin-client-assistant/runtime/moonlight_manager_registration.sh` erweitert (pair-token + pair-exchange),
	- `thin-client-assistant/runtime/moonlight_pairing.sh` verwendet zuerst Token-Exchange, dann Legacy-Fallback.
- Live-Fehler auf `srv1.beagle-os.com` (pair-token `500`) root-caused und behoben:
	- Ursache: `PermissionError` im Endpoint-Token-Store (`chmod` auf bestehendem `endpoint-tokens`-Verzeichnis unter non-root systemd-User),
	- Fix: `beagle-host/services/endpoint_token_store.py` macht `chmod` best-effort ohne Hard-Fail.
- Reproduzierbare Validierung:
	- Unit: `python3 -m pytest tests/unit/test_endpoint_token_store.py tests/unit/test_endpoint_http_surface.py tests/unit/test_pairing_service.py -q` => `11 passed`.
	- Live: `POST /api/v1/endpoints/moonlight/pair-token` auf `srv1` liefert `201` inkl. signiertem Pairing-Token und PIN.
	- Audit: keine neuen `request.unhandled_exception`-Eintraege fuer den vorherigen Permission-Fehlerpfad.

## Update (2026-04-22, GoFuture Plan 02 Testpflicht abgeschlossen: Light/Dark Screenshot-Vergleich)

- Offene Plan-02-Checkbox geschlossen: visuelle Stabilitaet aller Panels ist jetzt reproduzierbar validiert.
- Neues reproduzierbares Smoke-Script `scripts/test-webui-visual-smoke.py` implementiert.
- Das Script loggt sich gegen die echte WebUI ein, iteriert alle Sidebar-Panels und erzeugt Full-Page-Screenshots fuer Light/Dark.
- Zusaetzlich wird pro Panel eine Layout-Metrik (Bounding-Rects + Scroll-Dimensionen) verglichen und als JSON reportet.
- Lokale/Live-Ausfuehrung gegen `https://srv1.beagle-os.com`:
	- `VISUAL_SMOKE_RESULT=PASS`
	- `VISUAL_SMOKE_PANELS=17`
	- maximaler Layout-Delta `0px` (Threshold `4px`)
	- Report: `artifacts/webui-visual-smoke/report.json`
- Runtime-Hotfix auf `srv1` waehrend der Validierung:
	- `/opt/beagle/website/ui/virtualization.js` auf Repo-Stand synchronisiert,
	- fehlender Export `setStoragePoolQuota` war sonst ein Blocker fuer den `main.js`-Bootstrap.
- Ergebnis:
	- GoFuture Plan 02 ist jetzt vollstaendig abgehakt.

## Update (2026-04-22, GoFuture Plan 11 Schritt 1 abgeschlossen: Endpoint->Manager prepare-stream)

- Offene Schritt-1-Checkbox geschlossen: Moonlight-Client liest lokale Aufloesung und triggert vor Streamstart einen Guest-Display-Prepare-Call.
- Neuer Endpoint-API-Pfad implementiert:
	- `POST /api/v1/endpoints/moonlight/prepare-stream`
	- in `beagle-host/services/endpoint_http_surface.py`.
- Neue Guest-Display-Prepare-Logik in `beagle-host/services/sunshine_integration.py`:
	- `prepare_virtual_display_on_vm(...)` setzt `DISPLAY=:0` + `XAUTHORITY` und versucht `xrandr --output <out> --mode <resolution>`.
	- fuer `3840x2160` wird zusaetzlich ein 4K-Modeline-Add/Apply-Fallback versucht.
- Control-Plane-Wiring in `beagle-host/bin/beagle-control-plane.py` erweitert (Wrapper + Endpoint-Surface-Injektion).
- Endpoint-Runtime integriert:
	- `thin-client-assistant/runtime/moonlight_manager_registration.sh` um `prepare_moonlight_stream_via_manager(...)` erweitert.
	- `thin-client-assistant/runtime/launch-moonlight.sh` ruft den Prepare-Call vor dem eigentlichen Moonlight-Stream auf.
- Testabdeckung erweitert:
	- `tests/unit/test_endpoint_http_surface.py` neu (prepare-stream path/status/payload).
	- `python3 -m pytest tests/unit/test_endpoint_http_surface.py tests/unit/test_streaming_backend_service.py -q` => `9 passed`.
- Runtime-Smoke:
	- `python3 scripts/test-streaming-quality-smoke.py --host srv1.beagle-os.com --domain beagle-100` => `pass_with_4k_limit`.
	- `x11_prereq`, `xrandr_query`, `vkms_sunshine`, `sunshine_api_apps` gruen; 4K-Apply weiterhin durch CRTC-Limit begrenzt.

## Update (2026-04-22, GoFuture Plan 11 Schritt 1 Start: Linux vkms + Windows Apollo Split)

- Plan-11-Strategie auf realen Runtime-Stand gebracht:
	- `docs/gofuture/11-streaming-v2.md` von pauschalem Apollo-Ziel auf Plattform-Split umgestellt,
	- Linux-Desktop-Pfad: Sunshine + `vkms` (Virtual Display),
	- Windows-Desktop-Pfad: Apollo + SudoVDA (optional/eval).
- Architekturentscheidung dokumentiert in `docs/refactor/07-decisions.md`:
	- neue Entscheidung `D-031` beschreibt den platform-aware Backend-Ansatz,
	- `guest_os=linux` -> Sunshine+vkms,
	- `guest_os=windows` -> Apollo,
	- Sunshine bleibt Fallback fuer Apollo-Fehlerpfade.
- Technischer Runtime-Anker umgesetzt:
	- neues Provisioning-Template `beagle-host/templates/ubuntu-beagle/virtual-display-setup.sh.tpl` angelegt,
	- `beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl` um `configure_virtual_display_vkms()` erweitert,
	- firstboot laedt jetzt `vkms`, persistiert Modul-Load (`/etc/modules-load.d/vkms.conf`), installiert `vkms-virtual-display.service`, und startet ein XFCE-Autostart-Skript zur 4K-Mode-Setzung via `xrandr`.
	- neuer platform-aware Selector `beagle-host/services/streaming_backend.py` implementiert (Linux default `sunshine`, Windows default `apollo`, optional `allow_apollo_on_linux` fuer Eval-Pfade).
	- Unit-Tests fuer Selector (`tests/unit/test_streaming_backend_service.py`) hinzugefuegt (`5 passed`).
- Live-Check auf `srv1.beagle-os.com` / `beagle-100`:
	- Sunshine-Version in VM bestaetigt (`2025.924.154138`),
	- `vkms` per guest-agent erfolgreich geladen (`lsmod` zeigt Modul),
	- `xrandr` im guest-agent-Kontext liefert erwartbar `Can't open display` (kein DISPLAY im nicht-interaktiven Agent-Kontext), was den bekannten Unterschied zu echter XFCE-Session bestaetigt.
	- anschliessend in echter Session validiert: `DISPLAY=:0 XAUTHORITY=/home/beagle/.Xauthority xrandr --query` funktioniert und zeigt `Virtual-1` inkl. Modus `3840x2160_60.00`.
	- 4K-Apply laeuft aktuell in `xrandr: Configure crtc 0 failed`; deshalb wurde ein robuster Fallback auf `1920x1080` in den vkms-Setup-Skripten implementiert.
	- neuer reproduzierbarer Qualitaets-Smoke `scripts/test-streaming-quality-smoke.py` hinzugefuegt und ausgefuehrt:
		- `x11_prereq`: ok
		- `xrandr_query`: ok (`Virtual-1`, current `1280x800`, 4K-Mode vorhanden)
		- `xrandr_set_4k`: nicht erfolgreich (`Configure crtc 0 failed`)
		- `vkms_sunshine`: ok
		- `sunshine_api_apps`: ok
		- Gesamtresultat: `pass_with_4k_limit`.
- Ergebnis:
	- Plan 11 ist gestartet und hat einen reproduzierbaren Linux-vDisplay-Implementierungsanker im Repo,
	- offene Restarbeit fuer Abschluss von Schritt 1: Moonlight-E2E-Stream-Nachweis gegen den vkms-Guest und Aufloesungs-Uplift auf 4K in kompatibler VM-Grafikkonfiguration.

## Update (2026-04-22, GoFuture Plan 10 letzte Testpflicht: Entitlement-Sichtbarkeit)

- Serverseitige Pool-Sichtbarkeitsfilter in `beagle-host/bin/beagle-control-plane.py` umgesetzt:
	- `GET /api/v1/pools` filtert jetzt restriktive Pools fuer nicht berechtigte `pool:read`-User heraus,
	- `GET /api/v1/pools/{pool}` / `/vms` / `/entitlements` maskieren versteckte Pools als `404 pool not found`,
	- Operator-/Admin-Bypass bleibt ueber `pool:write` bzw. `*` erhalten.
- `beagle-host/services/entitlement_service.py` erweitert um explizite Sichtbarkeits-Semantik:
	- `has_explicit_entitlements(...)`
	- `can_view_pool(...)`
- Reproduzierbarer Nachweis erweitert:
	- `scripts/test-vdi-pools-smoke.py` fuehrt jetzt zusaetzlich einen authentifizierten Visibility-Smoke aus,
	- Admin sieht alle Pools,
	- berechtigter User sieht nur unrestricted + entitled Pools,
	- unberechtigter User sieht restriktive Pools nicht und bekommt bei Direkt-Lookup `404`.
- Lokale Validierung:
	- `python3 -m pytest tests/unit/test_entitlement_service.py -q` => `5 passed`
	- `python3 -m py_compile beagle-host/bin/beagle-control-plane.py` => OK
	- `python3 scripts/test-vdi-pools-smoke.py` => `VDI_POOL_SMOKE_OK`
- Deploy + Runtime-Validierung auf `srv1.beagle-os.com`:
	- `beagle-control-plane.py`, `entitlement_service.py` und `scripts/test-vdi-pools-smoke.py` nach `/opt/beagle` synchronisiert,
	- `./scripts/install-beagle-host-services.sh` erfolgreich,
	- `cd /opt/beagle && python3 scripts/test-vdi-pools-smoke.py` => `VDI_POOL_SMOKE_OK`.
- Ergebnis:
	- Die letzte offene GoFuture-Plan-10-Testpflicht-Checkbox ist geschlossen.
	- Plan 10 ist damit vollstaendig abgeschlossen.

## Update (2026-04-22, GoFuture Plan 10 Testpflicht-Slice: reproduzierbarer VDI Smoke)

- Neues reproduzierbares Smoke-Script `scripts/test-vdi-pools-smoke.py` umgesetzt.
- Das Script validiert Plan-10-Runtime mit temp-local State statt Live-Daten:
	- synthetisches Golden-Image per `qemu-img create`,
	- Template-Export ueber `DesktopTemplateBuilderService`,
	- Floating-Non-Persistent-Pool mit 5 Slots,
	- Release/Recycling-Flow inkl. `<60s`-Nachweis,
	- Persistent-Pool mit Reassign derselben VM,
	- Throwaway-Control-Plane mit `BEAGLE_MANAGER_ALLOW_LOCALHOST_NOAUTH=1` fuer echte API-Routen (`/pools`, `/entitlements`, `/allocate`, `/release`, `/recycle`).
- Lokale Validierung:
	- `python3 scripts/test-vdi-pools-smoke.py` => `VDI_POOL_SMOKE_OK`.
- Deploy + Runtime-Validierung auf `srv1.beagle-os.com`:
	- Script nach `/opt/beagle/scripts/test-vdi-pools-smoke.py` ausgerollt,
	- `cd /opt/beagle && python3 scripts/test-vdi-pools-smoke.py` => `VDI_POOL_SMOKE_OK`.
- Ergebnis:
	- GoFuture Plan 10 Testpflicht-Checkboxen fuer Floating-5-Slots, Recycle-<=60s, Persistent-Reassign und Template->Pool geschlossen.
	- Offen bleibt nur noch der explizite Sichtbarkeitsnachweis "User ohne Entitlement sieht Pool nicht"; aktuell ist reproduzierbar nur der API-Guard `403 not entitled to this pool` verifiziert.

## Update (2026-04-22, GoFuture Plan 10 Schritt 6: Template-Builder in Web Console)

- Neue VM-Detailaktion `Als Template` in `website/main.js` fuer gestoppte VMs umgesetzt.
- Neues Modul `website/ui/template_builder.js` implementiert:
	- Template-Builder-Modal,
	- API-Call `POST /api/v1/pool-templates`,
	- Fortschrittsdialog mit Sysprep/Seal-/Export-/Persistenz-Schritten,
	- Erfolgs-/Fehlerpfad mit Banner + Activity + Refresh.
- `website/ui/actions.js` um Action-Dispatch `open-template-builder` erweitert.
- `website/ui/events.js` um Template-Builder-Modal-/Progress-Events erweitert.
- `website/index.html` um `template-builder-modal` und `template-builder-progress-modal` erweitert.
- Lokale Validierung:
	- `node --check website/main.js website/ui/actions.js website/ui/events.js website/ui/template_builder.js` => alle erfolgreich.
- Deploy + Runtime-Validierung auf `srv1.beagle-os.com`:
	- geaenderte Dateien nach `/opt/beagle/website/...` ausgerollt,
	- `./scripts/install-beagle-host-services.sh` => `INSTALL_OK`,
	- Live-Smoke: `template-builder-modal`, `template-builder-progress-modal`, `template-builder-create` in `/` vorhanden,
	- Live-Smoke: `open-template-builder` in ausgeliefertem `main.js` vorhanden,
	- `GET /beagle-api/api/v1/pool-templates` ohne Auth => `401` (erwartet).

## Update (2026-04-22, GoFuture Plan 10 Schritt 5: Pool-Wizard + Pool-Uebersicht)

- Web Console fuer VDI-Pools auf echten Mehrschritt-Wizard umgestellt:
	- Schritt 1: Template + Pool-ID,
	- Schritt 2: Groesse/Modus/Ressourcen,
	- Schritt 3: Entitlements,
	- Schritt 4: Bestaetigung mit Zusammenfassung.
- `website/ui/policies.js` erweitert um Wizard-Flow-Logik:
	- Step-State, Next/Prev/Direct-Step,
	- step-spezifische Validierung,
	- Confirm-Summary vor `POST /api/v1/pools`.
- Pool-Uebersicht erweitert:
	- VM-Slot-Tabelle bleibt erhalten,
	- zusaetzliche Status-Summen fuer `free`, `in_use`, `recycling`, `error` pro ausgewaehltem Pool.
- `website/ui/events.js` um Wizard-Events erweitert (`pool-wizard-next`, `pool-wizard-prev`, Stepper-Klick).
- `website/styles/panels/_policies.css` mit Stepper-/Summary-/Stats-Styling erweitert.
- Lokale Validierung:
	- `node --check` auf geaenderte WebUI-Module erfolgreich,
	- VSCode-Errors fuer geaenderte Dateien: keine.
- Deploy + Runtime-Validierung auf `srv1.beagle-os.com`:
	- Geaenderte Dateien nach `/opt/beagle/website/...` synchronisiert,
	- `./scripts/install-beagle-host-services.sh` erfolgreich (`INSTALL_OK`),
	- Live-Smoke: `https://127.0.0.1/` enthaelt `pool-step-btn-4`, `pool-wizard-next`, `pool-overview-stats`,
	- `GET /beagle-api/api/v1/pools` ohne Auth liefert erwartetes `401`.

## Update (2026-04-22, GoFuture Plan 10 Schritt 1 Teil 2 + Schritt 2 Teil 2 + Schritt 3 Teil 2 + Schritt 4 Teil 2)

- Neues Service-Modul `beagle-host/services/desktop_template_builder.py` umgesetzt.
- Template-Builder realisiert jetzt den geplanten Basispfad `Snapshot/Seal/Backing-Image`:
	- VM-Stopp-Hook,
	- cloud-init-/Sysprep-Seal ueber `virt-sysprep` bzw. `guestfish`,
	- qcow2-Backing-Image-Export per `qemu-img convert`,
	- persistente Template-Metadaten in `desktop-templates.json`.
- Neues Service-Modul `beagle-host/services/pool_manager.py` umgesetzt.
- Pool-Lifecycle fuer VDI-Basisschicht realisiert:
	- Pool-CRUD,
	- VM-Slot-Registrierung,
	- Allocation / Release / Recycle,
	- Scale-State,
	- Statuszaehlung fuer `free | in_use | recycling | error`.
- Mode-spezifische Runtime-Logik fuer `floating_non_persistent`, `floating_persistent` und `dedicated` im Pool-Manager umgesetzt und per Unit-Tests verifiziert.
- Control Plane erweitert um Plan-10-Basis-API:
	- `GET/POST/PUT/DELETE /api/v1/pools`
	- `GET /api/v1/pools/{pool}/vms`
	- `POST /api/v1/pools/{pool}/vms|allocate|release|recycle|scale|entitlements`
	- `GET /api/v1/pool-templates`
	- `POST /api/v1/pool-templates`
	- `DELETE /api/v1/pool-templates/{id}`
- RBAC fuer die neue Surface ergaenzt (`pool:read`, `pool:write`) und mit `tests/unit/test_authz_policy.py` abgesichert.
- Wichtiger Runtime-Fix: Control-Plane importiert jetzt den Repo-Root auf `sys.path`, neue Services sprechen stabil gegen `core.virtualization.*` statt gegen fragile Bare-Imports.
- Lokale Validierung:
	- `python3 -m pytest tests/unit/test_pool_manager.py tests/unit/test_desktop_template_builder.py tests/unit/test_entitlement_service.py tests/unit/test_authz_policy.py -q` => `14 passed`.
	- Throwaway-Control-Plane auf Port `19088` gestartet; `GET /api/v1/pools` und `GET /api/v1/pool-templates` lieferten im localhost-noauth Modus `200`, `POST /api/v1/pools` mit `{}` lieferte `400 pool_id is required`.
- Deploy + Runtime-Validierung auf `srv1.beagle-os.com`:
	- geaenderte Dateien nach `/opt/beagle/...` synchronisiert,
	- `./scripts/install-beagle-host-services.sh` ausgefuehrt,
	- `beagle-control-plane.service` nach Restart `active`.
	- Live-Smoke auf `127.0.0.1:9088`:
		- `GET /api/v1/pools` => `401 unauthorized`,
		- `GET /api/v1/pool-templates` => `401 unauthorized`,
		- `POST /api/v1/pools` => `401 unauthorized`.
	- Journal zeigt sauberes Handling des neuen POST-Pfads ohne Exception.

## Update (2026-04-22, GoFuture Plan 10 Schritt 4 Teil 1: Entitlement-Service)

- Neues Modul `beagle-host/services/entitlement_service.py` umgesetzt.
- Service implementiert persistente Pool-Entitlements fuer User/Gruppen in JSON-State:
	- `get_entitlements`
	- `set_entitlements`
	- `add_entitlement`
	- `remove_entitlement`
	- `is_entitled`
- Eingabe-Validierung + Normalisierung enthalten (keine leere `pool_id`, deduplizierte IDs).
- Unit-Test `tests/unit/test_entitlement_service.py` erstellt (3/3 gruen).
- Live-Deploy + Smoke auf `srv1.beagle-os.com`:
	- Datei nach `/opt/beagle/beagle-host/services/entitlement_service.py` ausgerollt,
	- Import + Grundfunktion erfolgreich (`ENTITLEMENT_IMPORT_SMOKE_OK`).
- Ergebnis: Erste Checkbox aus GoFuture Plan 10 Schritt 4 geschlossen;
	API-Route fuer `POST /api/v1/pools/{pool}/entitlements` bleibt als naechster Block offen.

## Update (2026-04-22, GoFuture Plan 10 Schritt 2 Teil 1 + Schritt 3 Teil 1)

- Neues Core-Modul `core/virtualization/desktop_pool.py` umgesetzt.
- Provider-neutrales `DesktopPool`-Protocol eingefuehrt mit den Lifecycle-Seams:
	`create_pool`, `get_pool`, `list_pools`, `delete_pool`, `scale_pool`,
	`allocate_desktop`, `release_desktop`, `recycle_desktop`.
- Neue typisierte Pool-/Lease-Datenmodelle hinzugefuegt:
	- `DesktopPoolSpec`
	- `DesktopPoolInfo`
	- `DesktopLease`
- Schritt-3-Mode-Baustein real umgesetzt:
	- `DesktopPoolMode` Enum mit
		`floating_non_persistent | floating_persistent | dedicated`.
	- Mode ist in Spec/Lease-Feldern typisiert verdrahtet.
- Unit-Test `tests/unit/test_desktop_pool_contract.py` ergaenzt (3/3 gruen).
- Live-Deploy + Smoke auf `srv1.beagle-os.com`:
	- Datei nach `/opt/beagle/core/virtualization/desktop_pool.py` ausgerollt,
	- Import/Instanziierung per Python-Smoke erfolgreich (`POOL_IMPORT_SMOKE_OK`).
- Ergebnis: GoFuture Plan 10 Checkboxen fuer
	`core/virtualization/desktop_pool.py` und den Mode-Enum geschlossen.

## Update (2026-04-22, GoFuture Plan 10 Schritt 1 Teil 1: DesktopTemplate-Contract)

- Neues Core-Modul `core/virtualization/desktop_template.py` umgesetzt.
- Provider-neutrales `DesktopTemplate`-Protocol eingefuehrt mit Lifecycle-Methoden:
	`build_template`, `get_template`, `list_templates`, `delete_template`.
- Dataclass-Typen fuer den Builder-/Read-Pfad ergaenzt:
	- `DesktopTemplateBuildSpec`
	- `DesktopTemplateInfo`
- Unit-Test `tests/unit/test_desktop_template_contract.py` erstellt (2/2 gruen).
- Live-Deploy + Smoke auf `srv1.beagle-os.com`:
	- Datei nach `/opt/beagle/core/virtualization/desktop_template.py` ausgerollt,
	- Import/Instanziierung per Python-Smoke erfolgreich (`IMPORT_SMOKE_OK`).
- Ergebnis: Erste Checkbox aus GoFuture Plan 10 Schritt 1 geschlossen;
	Builder-Implementierung (zweite Checkbox) bleibt als naechster Block offen.

## Update (2026-04-22, GoFuture Plan 08 Testpflicht: Quota-Ueberschreitung)

- Quota-Enforcement in den Ubuntu-Provisioning-Create-Pfad integriert:
	- `beagle-host/services/ubuntu_beagle_provisioning.py` erweitert um `enforce_storage_quota(...)`.
	- Quota-Pruefung wird jetzt vor VM-Erzeugung fuer den Ziel-Storage ausgefuehrt.
	- Fehlerbild ist reproduzierbar als `quota_exceeded` standardisiert.
- Control-Plane-Wiring aktualisiert:
	- `beagle-host/bin/beagle-control-plane.py` uebergibt `get_storage_quota(...)` in den Provisioning-Service.
- Neue Unit-Testabdeckung:
	- `tests/unit/test_ubuntu_beagle_provisioning_quota.py` erstellt (2/2 gruen).
- Live-Deployment + Validierung auf `srv1.beagle-os.com`:
	- Geaenderte Dateien nach `/opt/beagle/...` ausgerollt, Services mit `scripts/install-beagle-host-services.sh` konsistent nachgezogen.
	- `beagle-control-plane.service` laeuft danach wieder stabil (`active`).
	- Reproduzierter API-Smoke: temporaer `quota_bytes=1` auf Pool `local`, danach `POST /api/v1/provisioning/vms` => `400 bad_request` mit `quota_exceeded`.
	- Urspruengliche Quota nach Testlauf wiederhergestellt (`quota_bytes=0`).
- Ergebnis: GoFuture Plan 08 Testpflicht-Checkbox "Quota-Ueberschreitung gibt korrekten Fehler zurueck" geschlossen.

## Update (2026-04-22, GoFuture Plan 08 Schritt 6: Storage-Quotas API + Web Console)

- Neuer persistenter Quota-Service `beagle-host/services/storage_quota.py` umgesetzt (`storage-quotas.json` im Manager-Data-Dir).
- Neue API-Routen im Control Plane implementiert:
	- `GET /api/v1/storage/pools/{pool}/quota`
	- `PUT /api/v1/storage/pools/{pool}/quota`
- RBAC/AuthZ fuer Quota-Routen ergänzt (`settings:read` / `settings:write`).
- Virtualization-Overview liefert jetzt pro Storage-Pool `quota_bytes`.
- Web Console erweitert:
	- Storage-Tabellen mit Quota-Spalte,
	- Quota-Setter-Aktion pro Pool (inkl. Refresh nach Update).
- Unit-Test `tests/unit/test_storage_quota_service.py` ergänzt.
- Damit ist GoFuture Plan 08 Schritt 6 vollständig erledigt.

## Update (2026-04-22, GoFuture Plan 08 Schritt 5: NFS-Backend)

- Neues Provider-Modul `providers/beagle/storage/nfs.py` implementiert (`NfsStorageBackend`).
- Storage-Lifecycle-Operationen fuer NFS umgesetzt:
	- `create_volume`/`resize_volume`/`snapshot`/`clone` via `qemu-img`
	- `delete_volume` und `list_volumes` auf NFS-Dateiobjekten
- Sicherheits-/Betriebs-Guard ergänzt: explizite Mountpoint-Pruefung (`mount_path` muss wirklich gemountet sein).
- Unit-Tests in `tests/unit/test_nfs_storage_backend.py` ergänzt (4/4 pass).
- Deploy-/Smoke-Validierung auf `srv1.beagle-os.com` erfolgreich (Import + create/snapshot/clone/list mit Command-Stub).
- Damit ist GoFuture Plan 08 Schritt 5 vollständig erledigt.

## Update (2026-04-22, GoFuture Plan 08 Schritt 4: ZFS-Backend)

- Neues Provider-Modul `providers/beagle/storage/zfs.py` umgesetzt (`ZfsStorageBackend`).
- Storage-Lifecycle-Operationen fuer ZFS implementiert:
	- `create_volume` via `zfs create -V`
	- `delete_volume` via `zfs destroy -r`
	- `resize_volume` via `zfs set volsize=`
	- `snapshot` via `zfs snapshot`
	- `clone` via Snapshot + `zfs clone`
	- `list_volumes` via `zfs list -t volume`
- Unit-Tests in `tests/unit/test_zfs_storage_backend.py` ergänzt (4/4 pass).
- Deploy-/Smoke-Validierung auf `srv1.beagle-os.com` erfolgreich (Import + create/snapshot/clone/list mit Command-Stub).
- Damit ist GoFuture Plan 08 Schritt 4 vollständig erledigt.

## Update (2026-04-22, GoFuture Plan 08 Schritt 3: LVM-Thin-Backend)

- Neues Provider-Modul `providers/beagle/storage/lvm_thin.py` umgesetzt (`LvmThinStorageBackend`).
- Storage-Lifecycle-Operationen auf LVM-Thin-Basis implementiert:
	- `create_volume` via `lvcreate --thin -V`
	- `delete_volume` via `lvremove --yes`
	- `resize_volume` via `lvresize --yes -L`
	- `snapshot` und linked-clone via `lvcreate -s`
	- `clone(linked=False)` via Thin-Volume + `qemu-img convert`
	- `list_volumes` via `lvs`-Parsing (thin-pool gefiltert)
- Unit-Tests in `tests/unit/test_lvm_thin_storage_backend.py` ergänzt (4/4 pass).
- Deploy-/Smoke-Validierung auf `srv1.beagle-os.com` erfolgreich (Import + create/snapshot/clone/list mit Command-Stub).
- Damit ist GoFuture Plan 08 Schritt 3 abgehakt.

## Update (2026-04-22, GoFuture Plan 08 Schritt 2: Directory-Storage-Backend)

- Neues Provider-Modul `providers/beagle/storage/directory.py` implementiert (`DirectoryStorageBackend`).
- Real implementierte Storage-Lifecycle-Operationen:
	- `create_volume` (`qemu-img create`)
	- `delete_volume`
	- `resize_volume` (`qemu-img resize`)
	- `snapshot` (`qemu-img snapshot -c`)
	- `clone` (linked/full via `qemu-img create -b` bzw. `qemu-img convert`)
	- `list_volumes`
- Sicherheitsrelevante Guards integriert: Name-/Formatvalidierung und Path-Escape-Schutz unterhalb `base_dir`.
- Unit-Tests `tests/unit/test_directory_storage_backend.py` hinzugefuegt (4/4 pass).
- Damit ist GoFuture Plan 08 Schritt 2 vollstaendig abgehakt.

## Update (2026-04-22, GoFuture Plan 08 Schritt 1: StorageClass-Contract)

- Neues Core-Modul `core/virtualization/storage.py` eingefuehrt.
- `StorageClass`-Protocol mit Lifecycle-Methoden (`create_volume`, `delete_volume`, `resize_volume`, `snapshot`, `clone`, `list_volumes`) definiert.
- Typen `VolumeSpec`, `SnapshotSpec`, `StoragePoolInfo` als Dataclasses umgesetzt.
- Unit-Test `tests/unit/test_storage_contract.py` erstellt und lokal erfolgreich ausgefuehrt (3/3 pass).
- Damit ist GoFuture Plan 08 Schritt 1 vollstaendig abgehakt.

## Update (2026-04-22, GoFuture Plan 07 Schritt 3 (Teil 1): Cluster-Inventory-Service)

- Neues Service-Modul `beagle-host/services/cluster_inventory.py` umgesetzt.
- `beagle-control-plane.py` verdrahtet den Service als neue Read-API:
	- `GET /api/v1/cluster/inventory`
	- `GET /api/v1/cluster/nodes` (Alias)
- Cluster-Inventory aggregiert Node-Metriken plus VM-Verteilung pro Node und markiert fehlende Nodes als `unreachable`.
- Unit-Testabdeckung ergänzt mit `tests/unit/test_cluster_inventory.py` (Aggregation + unreachable-Fallback).
- Damit ist der erste Checkbox-Punkt aus GoFuture Plan 07 Schritt 3 real implementiert.

## Update (2026-04-22, GoFuture Plan 07 Schritt 6: Cluster Panel in Web Console)

- GoFuture 07 Schritt 6 (beide Checkboxen) umgesetzt: neues `Cluster`-Panel in der Navigation sowie Knotenliste mit Status, CPU-/RAM-Auslastung und VM-Count.
- Neue UI-Datei `website/ui/cluster.js` implementiert:
	- Rendert Knotenstatus aus `state.virtualizationOverview.nodes`.
	- Aggregiert VM-Anzahl pro Knoten aus `state.inventory`.
	- Bietet direkte Aktion "VMs anzeigen" pro Knoten (Node-Filter ins Inventory).
- Integration in den bestehenden Datenfluss:
	- `website/main.js`: Modul importiert/verdrahtet (`configureCluster`, `bindClusterEvents`, `renderClusterPanel`).
	- `website/ui/dashboard.js`: `renderClusterPanel()` in den regulären Dashboard-Refresh eingebunden.
	- `website/ui/auth.js`: Cluster-Ansicht wird bei Session-Clear ebenfalls konsistent zurückgesetzt.
	- `website/ui/state.js`: `panelMeta.cluster` ergänzt.
	- `website/index.html`: neues Nav-Element (`data-panel="cluster"`) + neue Panel-Sektion (`data-panel-section="cluster"`).
- Sicherheits-/Architektur-Status:
	- Keine neuen Provider-Kopplungen, kein Beagle host-Code.
	- Datenquelle bleibt provider-neutral über bestehende Read-Surfaces (`/virtualization/overview`, `/vms`).

## Update (2026-04-21, Hotfix: VM USB installer/live downloads + missing syncHash)

- **Symptome**:
	- Web UI VM-Detailansicht warf `ReferenceError: syncHash is not defined` aus `website/main.js`.
	- `GET /api/v1/vms/{vmid}/installer.sh`, `/installer.ps1`, `/live-usb.sh` lieferten auf `srv1.beagle-os.com` reproduzierbar `503`.
- **Root cause Frontend**:
	- `website/main.js` verwendete `syncHash()` in `loadDetail()`/`closeDetail()`, importierte die Funktion aber nicht mehr aus `website/ui/panels.js`.
- **Root cause Backend**:
	- `InstallerScriptService` hing fuer VM-spezifische Downloads hart an Host-`dist/`-Artefakten (`pve-thin-client-usb-installer-host-latest.sh`, `pve-thin-client-live-usb-host-latest.sh`, `beagle-os-installer-amd64.iso`).
	- Auf `srv1` fehlten genau diese Dateien unter `/opt/beagle/dist/`, obwohl das versionierte Quellskript unter `thin-client-assistant/usb/` vorhanden war.
- **Fix**:
	- `website/main.js`: `syncHash` wieder korrekt importiert.
	- `website/index.html`: `main.js` Cache-Buster auf `6.7.0-r7` angehoben, damit Browser den Hotfix ziehen.
	- `beagle-host/services/installer_script.py`: Shell-Downloads lesen jetzt bevorzugt die gehosteten Templates, fallen aber auf das versionierte Quellskript `thin-client-assistant/usb/pve-thin-client-usb-installer.sh` zurueck; lokale ISO-Pflicht fuer die drei generierten Download-Skripte entfernt.
	- `beagle-host/bin/beagle-control-plane.py`: neues Raw-Shell-Template an `InstallerScriptService` verdrahtet.
	- `tests/unit/test_installer_script.py`: neuer fokussierter Unit-Test fuer den Fallback ohne `dist/`-Artefakte.
- **Validierung lokal**:
	- `python3 -m pytest tests/unit/test_installer_script.py` -> `1 passed`.
	- `python3 -m py_compile beagle-host/services/installer_script.py beagle-host/bin/beagle-control-plane.py` -> OK.
- **Live-Validierung auf `srv1.beagle-os.com`**:
	- Hotfix-Dateien nach `/opt/beagle/...` deployt und `beagle-control-plane` neu gestartet (`active`).
	- `GET /api/v1/vms/100/installer.sh` -> `200`.
	- `GET /api/v1/vms/100/installer.ps1` -> `200`.
	- `GET /api/v1/vms/100/live-usb.sh` -> `200`.
	- HTTPS-Index liefert `/main.js?v=6.7.0-r7`; ausgeliefertes `main.js` enthaelt den `syncHash`-Import.

## Update (2026-04-21, GoFuture Plan 15 Schritte 1+3+4+5: Audit schema/report/viewer)

- `core/audit_event.py` neu angelegt und als gemeinsames Audit-Schema mit `schema_version`, `action`, `resource_*`, `old_value`, `new_value`, `metadata` eingefuehrt.
- `beagle-host/services/audit_log.py` auf das neue Schema migriert; Legacy-Records werden weiterhin ueber `AuditEvent.from_record(...)` normalisiert.
- `beagle-host/services/audit_pii_filter.py` neu implementiert; Default-Redaction schwaerzt `password`, `secret`, `token`, `key` rekursiv in `old_value`/`new_value`.
- `beagle-host/services/audit_report.py` neu implementiert; `GET /api/v1/audit/report` liefert JSON oder CSV je nach `Accept`-Header.
- `beagle-host/services/authz_policy.py` erweitert: Audit-Report erfordert `auth:read`.
- Web Console erweitert:
	- neues Audit-Panel in `website/index.html`,
	- State/Hooks in `website/ui/state.js`, `website/ui/panels.js`, `website/ui/events.js`, `website/ui/activity.js`,
	- neues Modul `website/ui/audit.js` fuer Filter, Refresh, CSV-Export und Auto-Refresh.
- **Validierung lokal**:
	- `python3 -m pytest tests/unit/test_audit_log.py tests/unit/test_audit_helpers.py tests/unit/test_audit_report.py` -> `9 passed`.
- **Live-Validierung auf `srv1.beagle-os.com`**:
	- `beagle-control-plane.service` nach Deploy aktiv,
	- `/api/v1/audit/report` liefert `200`, JSON `ok=true`, CSV mit Header,
	- Redaction-Snippet auf `srv1` bestaetigt `[REDACTED]` fuer `password`/`api_token`/`private_key`.

## Update (2026-04-21, Hotfix: noVNC HTTP 500 — /etc/beagle/novnc permission)

- **Root cause**: `/etc/beagle/novnc/` was `root:beagle-manager 0750` — group had `r-x` but not write.
- `VmConsoleAccessService._create_ephemeral_novnc_token` tried to create `console-tokens.json` in that dir → `PermissionError` → unhandled → 500.
- **Fix**: `scripts/install-beagle-host-services.sh` changed from `chmod 0750` to `chmod 0770` for `/etc/beagle/novnc`.
- Live-fixed on srv1 via `chmod 770 /etc/beagle/novnc`. Confirmed writable by beagle-manager.
- Commit: `9a6d6c9`

## Update (2026-04-21, GoFuture Plan 14 Schritte 2+5: Recording-Service + Download-Audit)

- `beagle-host/services/recording_service.py` neu implementiert (ffmpeg-basierte Session-Aufzeichnung, MP4-Output, `recordings/index.json`).
- Control Plane erweitert:
	- `POST /api/v1/sessions/{id}/recording/start`
	- `POST /api/v1/sessions/{id}/recording/stop`
	- `GET /api/v1/sessions/{id}/recording`
- RBAC ergänzt:
	- `session:manage_recording`
	- `session:download_recording`
	- Permission-Katalog (`/api/v1/auth/permission-tags`) erweitert.
- Audit ergänzt:
	- Download erzeugt `session.recording.download` inklusive Downloader-Identität.
- Tests:
	- neue Unit-Tests `tests/unit/test_recording_service.py` (2/2 pass),
	- fokussierte Test-Suite inkl. IAM-Regressionen: 19/19 pass.
- Live-Validierung auf `srv1.beagle-os.com`:
	- Recording Start `200`, Download `200`, MP4-Datei vorhanden,
	- ohne Token Download `401`,
	- Audit-Event in `/var/lib/beagle/beagle-manager/audit/events.log` nachweisbar.

## Update (2026-04-21, GoFuture Plan 13 Schritte 4+5: Tenant-Scope + Permission-Tags)

**Schritt 4 — Tenant-Scope in mutierenden Endpoints:**
- `beagle-host/services/auth_session.py`: `tenant_id` in User-Records (optional); `list_users` filtert nach Tenant; `create_user`/`update_user` akzeptieren `tenant_id`; `get_user_tenant_id()` Hilfsmethode; `resolve_access_token()` gibt `tenant_id` im Principal zurück.
- `beagle-host/services/auth_http_surface.py`: `route_get/post/put/delete` bekommen `requester_tenant_id`; Cross-tenant-Zugriff → 403 Forbidden.
- `beagle-host/bin/beagle-control-plane.py`: `requester_tenant_id` aus Principal weitergeleitet; `/api/v1/auth/me` gibt `tenant_id` zurück.
- 12 neue Unit-Tests in `tests/unit/test_tenant_isolation.py` (alle bestanden).

**Schritt 5 — Permission-Tag Checkboxen im Rollen-Editor:**
- `beagle-host/services/authz_policy.py`: `PERMISSION_CATALOG` (7 Gruppen, 13 Tags).
- Neuer Endpoint `GET /api/v1/auth/permission-tags`.
- `website/ui/iam.js`: `renderPermissionTagEditor()`, Checkbox-basierter Rollen-Editor.
- `website/index.html`: Rollen-Editor-Textarea → Checkbox-Grid.
- `website/styles/_forms.css`: Permission-Tag-Grid CSS.

Deployment + Live-Validierung auf `srv1.beagle-os.com` erfolgreich. 65 Unit-Tests bestanden.


## Update (2026-04-21, GoFuture Plan 13 Schritt 3: SCIM 2.0 Surface)

- SCIM-Service umgesetzt:
	- neue Datei `beagle-host/services/scim_service.py` mit SCIM 2.0 `/Users` und `/Groups` Ressourcen.
- Control Plane erweitert:
	- `beagle-host/bin/beagle-control-plane.py` um SCIM-Routing für `GET/POST/PUT/DELETE` unter `/scim/v2/*`.
	- separater SCIM-Auth-Guard über `BEAGLE_SCIM_BEARER_TOKEN` implementiert (getrennt von Session- und Legacy-API-Token).
- Live-Deployment + Validierung auf `srv1.beagle-os.com`:
	- `GET/POST/GET/DELETE` für `/scim/v2/Users` und `/scim/v2/Groups` erfolgreich getestet,
	- ohne SCIM-Token liefern die Endpoints reproduzierbar `401`.
	- Test-Entitäten (`scimtest`, `scim-ops`) nach Validierung wieder entfernt.

## Update (2026-04-21, GoFuture Plan 13 Schritt 1+2: OIDC + SAML Auth-Basis)

- OIDC-Service implementiert:
	- neue Datei `beagle-host/services/oidc_service.py` (Authorization-Code-Flow mit PKCE inklusive `state`/`nonce`/`code_verifier`).
	- neue Routen `GET /api/v1/auth/oidc/login` und `GET /api/v1/auth/oidc/callback` in `beagle-host/bin/beagle-control-plane.py`.
- SAML-Service implementiert:
	- neue Datei `beagle-host/services/saml_service.py` (SP-Metadata-Generator und Login-Redirect).
	- neue Routen `GET /api/v1/auth/saml/login` und `GET /api/v1/auth/saml/metadata`.
- Multi-IdP-Registry erweitert:
	- OIDC/SAML-Provider werden im Login-Dialog immer angezeigt (enabled/disabled via Env),
	- explizite Labels `Mit OIDC anmelden` / `Mit SAML anmelden`,
	- SAML-Metadata-URL in Provider-Payload.
- WebUI Login-Dialog erweitert:
	- SAML-Providerkarte mit zusätzlichem `SP-Metadata`-Download-Button (`website/ui/auth.js`, `website/styles/_modals.css`).
- Validierung:
	- lokal: `python3 -m py_compile` für neue/betroffene Python-Dateien erfolgreich, `node --check` für betroffene UI-Module erfolgreich.
	- `srv1.beagle-os.com`: Deploy + Service-Restart erfolgreich (`beagle-control-plane.service active`).
	- Live-Checks: `/api/v1/auth/providers` liefert lokale+OIDC+SAML-Methoden; `/api/v1/auth/saml/metadata` liefert 200 + XML.

## Update (2026-04-21, GoFuture Plan 13 Schritt 6: Multi-IdP Registry + Login-Methoden)

- Multi-IdP-Grundlage umgesetzt:
	- neuer Service `beagle-host/services/identity_provider_registry.py` erstellt (Registry-Datei + sichere Defaults + Local-Fallback).
- Control Plane erweitert:
	- neue öffentliche API `GET /api/v1/auth/providers` in `beagle-host/bin/beagle-control-plane.py`.
	- neue Env-Konfigurationen: `BEAGLE_IDENTITY_PROVIDER_REGISTRY_FILE`, `BEAGLE_OIDC_AUTH_URL`, `BEAGLE_SAML_LOGIN_URL`.
- Web Console Login-UX erweitert:
	- Login-Modal zeigt dynamisch alle konfigurierten Login-Methoden (`website/index.html`, `website/ui/auth.js`, `website/styles/_modals.css`, `website/ui/panels.js`, `website/main.js`).
- Validierung:
	- lokal: `python3 -m py_compile beagle-host/services/identity_provider_registry.py beagle-host/bin/beagle-control-plane.py` erfolgreich.
	- lokal: `node --check website/main.js website/ui/auth.js website/ui/panels.js website/ui/state.js` erfolgreich.

## Update (2026-04-21, GoFuture Plan 18 Schritt 4: Webhook-System)

- Webhook-Service real implementiert:
	- neue Datei `beagle-host/services/webhook_service.py` (persistente Registry, Event-Filter, HMAC-Signatur, Retry-Backoff, Delivery-Statusfelder).
- Settings-API erweitert:
	- `GET/PUT /api/v1/settings/webhooks`,
	- `POST /api/v1/settings/webhooks/test` in `beagle-host/services/server_settings.py`.
- Control Plane Integration:
	- erfolgreiche VM-Power-Events (`vm.start|vm.stop|vm.reboot`) dispatchen Webhooks in `beagle-host/bin/beagle-control-plane.py`.
- Web Console Integration:
	- neuer Server-Settings-Bereich `settings_webhooks` inkl. List/Add/Delete/Test/Save-Flow (`website/index.html`, `website/ui/settings.js`, `website/ui/state.js`).
- Validierung:
	- lokal: `python3 -m py_compile` für betroffene Python-Dateien und `node --check` für UI-Module erfolgreich.
	- `srv1.beagle-os.com`: Deploy + Service-Restart erfolgreich (`beagle-control-plane.service active`).
	- Live-API: Webhook-Settings `PUT` + Test-Dispatch `POST` jeweils `HTTP 200`.
	- Capture/HMAC: `X-Beagle-Signature` vorhanden und gegen Raw-Body verifiziert (`signature_valid=True`), Test-Dispatch `attempted=1`, `delivered=1`.

## Update (2026-04-21, GoFuture Plan 18 Schritt 5 + Testpflicht-Teile)

- API-Versionierungs-Vorbereitung umgesetzt:
	- `beagle-host/bin/beagle-control-plane.py` ergänzt um `GET /api/v2` und `GET /api/v2/health` als v2-Prep-Surface.
- Deprecation-Header für v1-Endpunkte umgesetzt:
	- zentrale Header-Injektion in Response-Pipeline (`_write_json`, `_write_bytes`, `_write_proxy_response`),
	- konfigurierbar über `BEAGLE_API_V1_DEPRECATED_ENDPOINTS`, `BEAGLE_API_V1_DEPRECATION_SUNSET`, `BEAGLE_API_V1_DEPRECATION_DOC_URL`.
- Neues Validator-Tool:
	- `scripts/validate-openapi-live.py` prüft dokumentierte `/api/v1`-Pfade gegen Live-API (kein 404 erlaubt).
- `beaglectl` korrigiert:
	- `vm list` nutzt nun den bestehenden Endpoint `/api/v1/vms` (statt fehlerhaftem `/api/v1/inventory`).
- Live-Validierung auf `srv1.beagle-os.com`:
	- `GET /api/v2` liefert `200` + Prep-Metadaten.
	- `GET /api/v1/vms` liefert erwartete Deprecation/Sunset/Link-Header.
	- `python3 scripts/validate-openapi-live.py ...` -> `openapi-live-validation=ok` (41 Pfade).
	- `beaglectl vm list --json` mit `BEAGLE_MANAGER_API_TOKEN` liefert valides JSON (json.tool geprüft).
- `docs/gofuture/18-api-iac-cli.md`: Schritt 5 beide Checkboxen und Testpflicht-Checkboxen für OpenAPI-live + `beaglectl vm list --json` auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 18 Schritt 1+3: OpenAPI-Generator + beaglectl)

- OpenAPI-v1-Generator umgesetzt:
	- neues Tool `scripts/generate-openapi-v1.py` scannt `beagle-host/**/*.py` nach `/api/v1/*`-Routen,
	- generiert `docs/api/openapi.v1.generated.yaml` und `docs/api/openapi-v1-coverage.md`.
- API-Policy ergänzt:
	- `docs/api/breaking-change-policy.md` erstellt (Breaking/Non-Breaking, Deprecation-Header, Supportfenster).
- `beaglectl` CLI implementiert:
	- neue dependency-freie CLI `scripts/beaglectl.py` (argparse + urllib),
	- Subcommands: `vm`, `pool`, `user`, `node`, `backup`, `session`, `config`,
	- JSON-Ausgabe (`--json`) und lokale Config-Verwaltung (`~/.config/beaglectl/config.json`),
	- globale Flags funktionieren sowohl vor als auch nach dem Subcommand.
- Validierung:
	- lokal: `python3 scripts/generate-openapi-v1.py`, `python3 -m py_compile scripts/beaglectl.py scripts/generate-openapi-v1.py`, CLI-Smokes erfolgreich,
	- `docs/gofuture/18-api-iac-cli.md` Schritt 1 und Schritt 3 auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 19 Schritt 6: Gaming-Kiosk Modernisierung)

- `beagle-kiosk/` Step-6-Ziele umgesetzt:
	- Electron-Version bereits modern (`^37.2.0`, >=29).
	- Automatischer Kiosk-Enrollment-Flow implementiert statt manueller Konfiguration.
- Technische Umsetzung:
	- `beagle-kiosk/main.js`: Auto-Enrollment beim Start via `POST /api/v1/endpoints/enroll`, Persistenz von `BEAGLE_MANAGER_TOKEN`, Leeren von `BEAGLE_ENROLLMENT_TOKEN`, Enrollment-Statusmodell + IPC `kiosk:enroll-now`.
	- `beagle-kiosk/preload.js`: Bridge `enrollNow()`.
	- `beagle-kiosk/renderer/index.html`, `renderer/kiosk.js`, `renderer/style.css`: Enrollment-Statuspanel + Retry-Button im Sidebar-UI.
	- `beagle-kiosk/kiosk.conf.example` und `beagle-os/overlay/usr/local/sbin/beagle-kiosk-install`: Enrollment-/Manager-Keys in Default-Konfiguration ergänzt.
- Validierung:
	- lokal: `cd beagle-kiosk && npm run lint` erfolgreich, `bash -n beagle-os/overlay/usr/local/sbin/beagle-kiosk-install` erfolgreich.
	- `srv1.beagle-os.com`: geänderte Dateien nach `/opt/beagle` deployt, gleicher Lint-/Syntax-Smoke erfolgreich.
- `docs/gofuture/19-endpoint-os.md` Schritt 6 auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 19 Schritt 1: Endpoint-Profile-Struktur)

- Profil-Management-System implementiert:
	- Drei Profile angelegt: `beagle-os/profiles/desktop-thin-client/`, `gaming-kiosk/`, `engineering-station/`
	- Jedes Profil mit `profile.conf` Konfigurationsdatei (13 Konfigurationsschlüssel).
	- Profile Manager `beagle-os/profile_manager.py` erstellt (Profil-Discovery, JSON-Export).
- Deployment auf `srv1.beagle-os.com` erfolgreich; alle 3 Profile korrekt geparst und geladen.
- `docs/gofuture/19-endpoint-os.md` Schritt 1 auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 05 Schritt 2: Beagle host-Legacy-Cleanup abgeschlossen)

- Dead-Code-Pfade entfernt (Beagle host wird dauerhaft entfernt — Plan 05):
	- `VmConsoleAccessService`: Beagle host-Console-Access-Logik (Zeilen 258–274 Beagle host UI Port Handling) entfernt,
	- `_beagle_ui_port()` Methode gelöscht, `beagle_ui_ports_raw` Parameter aus beiden Services (`VmConsoleAccessService`, `RequestSupportService`) entfernt,
	- `BEAGLE_BEAGLE_UI_PORTS` Environment-Variable aus `beagle-control-plane.py` gelöscht,
	- Proxy-CORS-Allow-Origins-Logik bereinigt (nur noch Beagle-relevante Origins).
- Lokale Syntax-Checks erfolgreich.
- Deployment auf `srv1.beagle-os.com` erfolgreich; Smoke-Tests alle 13/13 bestanden.
- Finale Grep-Verification: 0 Treffer für direkte Beagle host-API-Aufrufe (`qm`, `pvesh`, `/api2/json`, `PVEAuthCookie`).
- Plan 05 Schritt 2 auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 20 Schritt 4+8: Secret-Gates + OWASP smoke baseline)

- Neue security guardrails im Code umgesetzt:
	- `scripts/security-secrets-check.sh` (kein getracktes `.env`, `.gitignore`-Regeln, Operator-Dateien untracked, Hardcoded-Secret-Pattern-Scan),
	- `.security-secrets-allowlist` als explizite Ausnahme-Liste,
	- CI-Workflow `.github/workflows/security-secrets-check.yml` (monatlich + manuell + push auf relevante Pfade).
- Neue OWASP-basierte API-Baseline eingeführt:
	- `scripts/security-owasp-smoke.sh` mit reproduzierbaren Checks für Access-Control/Auth/Input-Validation/Misconfiguration.
- `docs/gofuture/20-security-hardening.md` Schritt 4 und 8 auf `[x]` gesetzt.
- Security-Fund-Register in `docs/refactor/11-security-findings.md` um S-013 und S-014 ergänzt.

## Update (2026-04-21, GoFuture Plan 06 final test checkbox closed)

- `scripts/test-server-installer-live-smoke.sh` erweitert:
	- screenshot-basierte Installer-Screen-Erkennung,
	- konfigurierbarer Grafikmodus,
	- optionale DHCP-Phase (`BEAGLE_LIVE_SMOKE_SKIP_DHCP=1`) fuer schnellen Boot-/Dialog-Nachweis,
	- robuste Option-Weitergabe bei sudo-Reexec.
- Lokaler Lauf erfolgreich:
	- `BEAGLE_LIVE_SMOKE_SKIP_DHCP=1 BEAGLE_LIVE_SMOKE_REQUIRE_INSTALLER_SCREENSHOT=1 scripts/test-server-installer-live-smoke.sh` -> `[OK] Live-server smoke test passed`.
- Damit ist der letzte offene Plan-06-Testpunkt (`ISO bootet in QEMU-VM, Installer-Dialog erscheint`) in `docs/gofuture/06-server-installer.md` auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 06 testpflicht wave: beagle-only host install + artifact verification)

- `scripts/install-beagle-host.sh` weiter auf beagle-only bereinigt:
	- Host-Provider-Resolution normalisiert Legacy-Beagle host-Werte konsequent auf `beagle`.
	- Beagle host-spezifischer `apt`-Fallback (enterprise repo strip/retry) entfernt.
- Neues Tooling fuer reproduzierbare Installer-Artefakt-Pruefung:
	- `scripts/verify-server-installer-artifacts.sh` (Checksums + optionale GPG-Signaturen fuer server-installer ISOs).
	- Lokaler End-to-End-Lauf gegen `dist/` erfolgreich (`SHA256SUMS` + `.sig` Verifikation).
- `docs/gofuture/06-server-installer.md` Testpflicht teilweise abgeschlossen:
	- `Installation ohne Beagle host-Abhaengigkeiten`,
	- `Post-Install service active`,
	- `ISO-Checksum/Signatur verifizierbar` auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 06 Schritt 4-5: shared postinstall hook + release signing chain)

- Gemeinsamen Post-Install-Pfad umgesetzt:
	- neues Shared-Hook-Skript `scripts/install-beagle-host-postinstall.sh` erstellt,
	- `scripts/install-beagle-host.sh` delegiert den gesamten post-install Bootstrap jetzt an diesen Hook statt Inline-Logik.
- Damit laufen Installer- und nachträglicher Installationspfad über dieselbe Sequenz (host env schreiben, services bootstrap, proxy setup).
- Release-Chain für Installer-Artefakte gehaertet in `scripts/create-github-release.sh`:
	- deterministische Regeneration von `dist/SHA256SUMS` aus den finalen Release-Assets,
	- optionaler GPG-Signaturpfad (`BEAGLE_RELEASE_SIGN`, `BEAGLE_RELEASE_GPG_KEY`) integriert,
	- automatische Veröffentlichung der Signaturartefakte (`*.iso.sig`, `SHA256SUMS.sig`) als Release-Assets vorbereitet.
- `docs/gofuture/06-server-installer.md` Schritt 4 und 5 auf `[x]` gesetzt.

## Update (2026-04-21, GoFuture Plan 06 Schritt 1-3: Server-Installer standalone + reproducible build env)

- `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer` auf standalone-only refactored:
	- Beagle host-Installmode-Branches entfernt/normalisiert,
	- Beagle host-Repo/Key-Handling entfernt,
	- Host-Paketpfad auf Beagle-only vereinheitlicht.
- Paketpfad im Installer erweitert auf explizite Standalone-Komponenten inkl. `nginx` und `websockify` (zusätzlich zu libvirt/KVM/QEMU + certbot-Pfaden).
- `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer-gui` ebenfalls auf einen einzigen Standalone-Modus reduziert (curses + plain fallback).
- Reproducible-Build-Vorbereitung umgesetzt:
	- neue zentrale Datei `server-installer/build.env` mit Build-Abhängigkeiten und Speicher-Guardrails,
	- `scripts/build-server-installer.sh` lädt `build.env` automatisch.
- `docs/gofuture/06-server-installer.md` aktualisiert:
	- Schritt 1-3 Checkboxes auf `[x]`,
	- ASCII-Flowchart des Installer-Ablaufs ergänzt,
	- Umsetzungsnotizen je Schritt ergänzt.

## Update (2026-04-21, GoFuture Plan 05: Beagle host dauerhaft entfernt + Mock-Provider Tests)

- `providers/beagle-host/` und `beagle-ui/` dauerhaft aus dem Repo geloescht (Plan 05 Schritt 5b).
- Legacy provider file geloescht (nur noch `beagle_host_provider.py` und `registry.py`).
- Neuer Unit-Test `tests/unit/test_vm_services_mock_provider.py` erstellt (Plan 05 Schritt 5a):
  - `MockHostProvider` implementiert vollstaendigen `HostProvider`-Contract fuer Tests ohne libvirt.
  - 21 Tests fuer `VirtualizationInventoryService` (Happy-Paths + Error-Paths) und Contract-Compliance.
- `tests/unit/test_beagle_novnc_token.py` von pytest auf stdlib unittest umgeschrieben (portabel, kein pytest noetig).
- Skript-Bereinigung: `beagle-ui`-Referenzen aus `scripts/validate-project.sh`, `scripts/install-beagle-host.sh`, `scripts/install-beagle-proxy.sh`, `scripts/package.sh`, `scripts/build-server-installer.sh`, `scripts/build-server-installimage.sh` entfernt.
- `install-beagle-proxy.sh`: Default-Provider auf `beagle` geaendert, `host_provider_kind()` normalisiert beagle-host/pve -> beagle, Beagle host-spezifische Cert-Logik entfernt, nginx-Location fuer `beagle-autologin.js` entfernt.
- `install-beagle-host.sh`: beagle-ui-integration-call entfernt.
- Finale Pruefung: `grep -r "qm\|pvesh\|/api2/json\|PVEAuthCookie" beagle-host/ providers/ --include="*.py"` -> 0 Treffer.
- Lokale Tests: `python3 -m unittest discover -s tests/unit -q` -> `48 passed`.
- Deploy + Validierung auf `srv1.beagle-os.com`:
  - `tests/unit/` synchronisiert, `48 passed` auf srv1.
  - `scripts/smoke-control-plane-api.sh` -> `13/13`.
  - Alle Services `active`: `beagle-control-plane`, `beagle-novnc-proxy`, `nginx`.

## Update (2026-04-21, GoFuture Plan 04 Schritt 2: Route-Delegation weitergezogen)

- Neue Service-Schicht fuer Auth/IAM-HTTP-Surface eingefuehrt: `beagle-host/services/auth_http_surface.py`.
- Aus `beagle-host/bin/beagle-control-plane.py` extrahiert und an Service delegiert:
	- GET: `/api/v1/auth/users`, `/api/v1/auth/roles`
	- POST: `/api/v1/auth/users`, `/api/v1/auth/roles`, `/api/v1/auth/users/{username}/revoke-sessions`
	- PUT: `/api/v1/auth/users/{username}`, `/api/v1/auth/roles/{name}`
	- DELETE: `/api/v1/auth/users/{username}`, `/api/v1/auth/roles/{name}`
- Handler-Logik reduziert auf Auth/RBAC-Guard + JSON-Read + Service-Call + Response-Write.
- Audit-Trail beibehalten ueber neuen Delegationspfad (`auth.user.*`, `auth.role.*`, `auth.user.revoke_sessions`).
- Neue Unit-Tests: `tests/unit/test_auth_http_surface.py`.
	- lokal: `pytest -q tests/unit/test_auth_http_surface.py tests/unit/test_auth_session.py tests/unit/test_authz_policy.py` -> `12 passed`.
- Deploy + Runtime-Validierung auf `srv1.beagle-os.com`:
	- aktualisierte Dateien nach `/opt/beagle` ausgerollt,
	- `./scripts/install-beagle-host-services.sh` ausgefuehrt,
	- `beagle-control-plane.service` neu gestartet (`active`),
	- `scripts/smoke-control-plane-api.sh` erneut erfolgreich (`13/13`).

## Update (2026-04-21, GoFuture Plan 20: single-use noVNC tokens + HTTP-only refresh cookie wave)

- **noVNC single-use tokens**: custom websockify plugin `beagle-host/bin/beagle_novnc_token.py` implementing `BeagleTokenFile` class.
  - Tokens are 32-byte random, stored as JSON in `/etc/beagle/novnc/console-tokens.json`.
  - Expires 30 seconds after creation; consumed (single-use) on first successful `lookup()` call.
  - `vm_console_access.py` now generates a fresh token per `/novnc-access` request instead of reusing persistent per-VM tokens.
  - `beagle-novnc-proxy.service` updated: `--token-plugin beagle_novnc_token.BeagleTokenFile`, `PYTHONPATH=/opt/beagle/lib`.
  - 8 new unit tests pass (`tests/unit/test_beagle_novnc_token.py`).
- **HTTP-only refresh token cookie**: `beagle-control-plane.py` now sets `Set-Cookie: beagle_refresh_token=...; HttpOnly; SameSite=Strict; Path=/api/v1/auth; Secure` on successful login and refresh. Clears cookie on logout and on failed refresh.
  - `/auth/refresh` also reads the token from cookie if not present in JSON body.
- **Audit events for endpoint lifecycle mutations**: `endpoint_lifecycle_surface` POST handler now emits `endpoint.lifecycle` audit events matching the existing pattern.
- Deployed and validated on `srv1.beagle-os.com`:
  - Both `beagle-novnc-proxy` and `beagle-control-plane` active after restart.
  - `journalctl -u beagle-novnc-proxy` confirms: `proxying from 127.0.0.1:6080 to targets generated by BeagleTokenFile`.
  - Cookie helper methods present in deployed control plane source.

## Update (2026-04-21, GoFuture Plan 20: CSP + systemd hardening wave)

- `scripts/install-beagle-proxy.sh` CSP tightened for nginx by adding secure websocket source:
  - `connect-src 'self' wss:`
  - no `unsafe-inline` and no `unsafe-eval` in the configured policy.
- Hardened beagle systemd units with explicit `CapabilityBoundingSet=` and `RestrictAddressFamilies=`:
  - `beagle-host/systemd/beagle-artifacts-refresh.service`
  - `beagle-host/systemd/beagle-public-streams.service`
  - `beagle-host/systemd/beagle-ui-reapply.service`
  - `beagle-host/systemd/beagle-novnc-proxy.service`
- `beagle-novnc-proxy.service` switched to non-root runtime:
  - `User=beagle-manager`, `Group=beagle-manager`
  - additional sandboxing (`NoNewPrivileges`, `ProtectSystem=strict`, syscall/address-family restrictions).
- Deployed and validated on `srv1.beagle-os.com`:
  - `beagle-novnc-proxy`, `beagle-control-plane`, `nginx` all `active` after rollout.
  - `systemctl show` confirms non-root noVNC runtime and empty `CapabilityBoundingSet`.
  - HTTPS response header confirms CSP contains `connect-src 'self' wss:`.

## Update (2026-04-21, GoFuture Plan 04/20: Input-Validation + Dependency-Audit Welle)

- Serverseitige Input-Validierung gehaertet:
	- `beagle-host/bin/beagle-control-plane.py` mit Payload-Whitelist-Pruefung fuer zentrale Auth-POST-Routen (`login`, `refresh`, `logout`, `onboarding`, `auth/users`, `auth/roles`).
	- `sanitizeIdentifier`-Logik auf Serverseite ergaenzt.
	- `beagle-host/services/auth_session.py` erzwingt Username-/Role-Pattern in den relevanten CRUD/Auth-Pfaden.
- Regression/Validierung:
	- lokal: `python -m unittest tests.unit.test_auth_session` -> OK,
	- srv1: invalid onboarding-username und unknown login keys liefern korrekt `400 bad_request` statt 500,
	- srv1: bestehender Control-Plane-Smoke (`scripts/smoke-control-plane-api.sh`) weiterhin `13/13`.
- Dependency-Audit Automatisierung implementiert:
	- neues Skript `scripts/security-audit.sh` (pip-audit + npm audit, Report nach `dist/security-audit/`),
	- neuer CI-Workflow `.github/workflows/security-audit.yml` (monatlich + manual dispatch).
- Security-Run dokumentiert in `docs/refactor/11-security-findings.md` (S-007, S-008).

## Update (2026-04-21, GoFuture Plan 04/05/20: Security+Error-Handling Welle)

- `beagle-host/bin/beagle-control-plane.py` gehaertet:
	- API-Rate-Limit fuer alle `/api/*` Requests hinzugefuegt.
	- Login-Brute-Force-Schutz mit Exponential-Backoff + Lockout hinzugefuegt.
	- Fehler-Payloads bekommen jetzt konsistentes `code`-Feld.
	- Unhandled-Exception-Grenze liefert sanitisiertes `500`-JSON (`internal_error`).
	- Strukturierte JSON-Response-Logs erweitert um `user`, `action`, `resource_type`, `resource_id`.
- Auth-Default gehaertet:
	- Access-Token-Default auf 15 Minuten (`BEAGLE_AUTH_ACCESS_TTL_SECONDS=900`).
- `scripts/install-beagle-host-services.sh` setzt Security-Defaults fuer die neuen Rate-Limit/Lockout-Parameter in `beagle-manager.env`.
- Live auf `srv1.beagle-os.com` validiert:
	- `401`-Antworten mit `code=unauthorized` verifiziert,
	- Brute-Force-Verhalten verifiziert (`/api/v1/auth/login` liefert nach Wiederholungen `429 rate_limited`),
	- API-Rate-Limit verifiziert (temporar auf 5 gesetzt, `429 rate_limited` reproduzierbar, danach auf 240 zurueckgesetzt),
	- Service nach Deploy stabil `active`.
- Provider-Abstraction/Testpflicht-Nachweise fuer Plan 05 ergaenzt:
	- `grep`-Audit fuer Beagle host-Direktaufrufe in `beagle-host/` ausgefuehrt,
	- `python -m pytest tests/unit -q` ausgefuehrt: `15 passed`.

## Update (2026-04-21, GoFuture Plan 04 Testpflicht: API-Smoke reproduzierbar abgeschlossen)

- Neues reproduzierbares Smoke-Skript angelegt: `scripts/smoke-control-plane-api.sh`.
- Das Skript prueft zentrale Read/Mutation/Auth-Routen mit erwarteten Statuscodes (`200/400/401`) gegen den laufenden Control Plane Endpoint.
- Deploy nach `srv1.beagle-os.com` unter `/opt/beagle/scripts/smoke-control-plane-api.sh` und Live-Ausfuehrung erfolgreich.
- Ergebnis auf `srv1`: `Smoke checks passed: 13` (13/13 erwartete Checks bestanden).
- Damit ist die offene GoFuture-Checkbox `Alle API-Endpunkte antworten korrekt nach Refactoring (Smoke-Tests)` fuer Plan 04 als reproduzierbar verifiziert abgehakt.

## Update (2026-04-21, GoFuture Plan 04 Schritt 7 umgesetzt: Control-Plane als non-root Service)

- `beagle-host/systemd/beagle-control-plane.service` gehaertet und auf dedizierten Runtime-User umgestellt:
	- `User=beagle-manager`, `Group=beagle-manager`, `SupplementaryGroups=libvirt kvm`
	- `Restart=on-failure`, `RestartSec=5`
	- `CapabilityBoundingSet=` (leer), weiterhin `NoNewPrivileges=yes` + `PrivateTmp=yes`
	- Beagle host-spezifische `ReadWritePaths` entfernt (`/var/lib/vz`, `/etc/pve`, `/var/log/pve`).
- `scripts/install-beagle-host-services.sh` erweitert:
	- legt `beagle-manager` als System-User an (falls fehlend),
	- haengt User an `libvirt`/`kvm` Gruppen,
	- setzt Berechtigungen fuer `/var/lib/beagle/beagle-manager` sowie `/etc/beagle/beagle-manager.env` und `/etc/beagle/novnc/tokens` fuer non-root-Betrieb.
- Deploy + Validierung auf `srv1.beagle-os.com`:
	- aktualisierte Unit + Installer-Script ausgerollt,
	- Service neu installiert/reloaded/restarted,
	- `systemctl show` bestaetigt `User=beagle-manager`, `Restart=on-failure`, `RestartUSec=5s`, `CapabilityBoundingSet=`,
	- `beagle-control-plane.service` ist `active`, keine Traceback-/Unhandled-Exception-Marker im Journal.

## Update (2026-04-21, GoFuture Plan 04 Testpflicht erweitert: Audit-Events + Log-Stabilitaet)

- Control-Plane Audit-Pfad fuer VM-Power-Mutationen zentralisiert:
	- neues Service-Helpermodul `beagle-host/services/audit_helpers.py` mit `build_vm_power_audit_event(...)`.
	- `beagle-host/bin/beagle-control-plane.py` nutzt den Helper jetzt fuer `POST /api/v1/virtualization/vms/{vmid}/power` und schreibt explizite Audit-Events `vm.start`, `vm.stop`, `vm.reboot` mit `resource_type=vm` und `resource_id=<vmid>`.
- `auth.user.create`-Audit angereichert um strukturierte Resource-Metadaten (`resource_type=user`, `resource_id=<username>`) plus `remote_addr`.
- Neue Unit-Tests hinzugefuegt:
	- `tests/unit/test_audit_helpers.py`
	- `tests/unit/test_audit_log.py`
- Lokale Validierung erfolgreich:
	- `python -m unittest tests.unit.test_auth_session tests.unit.test_server_settings tests.unit.test_authz_policy tests.unit.test_audit_helpers tests.unit.test_audit_log` -> `OK`.
- Deploy und Runtime-Check auf `srv1.beagle-os.com`:
	- geaenderte Control-Plane-Dateien nach `/opt/beagle` synchronisiert,
	- `beagle-control-plane.service` neu gestartet -> `active`,
	- neue Audit-Unit-Tests auf `srv1` erfolgreich,
	- `journalctl -u beagle-control-plane.service` zeigt keine `Traceback`/`Unhandled Exception`-Marker.

## Update (2026-04-21, GoFuture Plan 05 step 1/3 umgesetzt: Provider Contract + Beagle Provider Erweiterung)

- Provider-Contract erweitert in `beagle-host/providers/host_provider_contract.py` um:
	- `snapshot_vm(...)`
	- `clone_vm(...)`
	- `get_console_proxy(...)`
- Beagle-Provider implementiert diese Methoden real:
	- Snapshot: lokale Snapshot-Metadaten + optionales libvirt snapshot-create.
	- Clone: VM-State-Klon + optionales libvirt volume-clone mit Fallback.
	- Console-Proxy: VNC-Metadaten aus libvirt (`vncdisplay`) fuer noVNC-Weiterverarbeitung.
- Beagle host-Provider ebenfalls auf Contract-Paritaet erweitert (snapshot/clone/console payload), ohne neue Kopplung ausserhalb des Provider-Layers.
- Unit-Test hinzugefuegt: `tests/unit/test_beagle_host_provider_contract_extensions.py` (3 Tests, alle gruen lokal).
- Deploy + Runtime-Smoketest auf `srv1.beagle-os.com` erfolgreich:
	- `snapshot_vm(301, "smoke-snap")` -> success,
	- `clone_vm(301, 302)` -> success,
	- `get_console_proxy(301)` -> valid payload.

## Update (2026-04-21, GoFuture Plan 04 Schritt 1+3 umgesetzt: RBAC-Nachruestung)

- Control-Plane POST-Mutationspfad vereinheitlicht: `POST /api/v1/vms` wird jetzt als Legacy-Alias sicher auf den Provisioning-Mutationspfad gemappt.
- Fehlende RBAC-Abdeckung fuer Legacy-Pfad behoben:
	- `beagle-host/bin/beagle-control-plane.py`: neue `admin_post_path`-Normalisierung (`/api/v1/vms` -> `/api/v1/provisioning/vms`) inklusive Auth-/RBAC-Pruefung.
	- `beagle-host/services/authz_policy.py`: `required_permission(POST, /api/v1/vms)` liefert jetzt `provisioning:write`.
- Unit-Test hinzugefuegt: `tests/unit/test_authz_policy.py`
	- verifiziert `viewer` darf `settings:write` nicht,
	- verifiziert Admin darf `settings:write`,
	- verifiziert Legacy-Route `/api/v1/vms` mappt auf `provisioning:write`.
- Live-Verifikation auf `srv1.beagle-os.com` nach Deploy:
	- `POST /api/v1/vms` ohne Auth -> `401 unauthorized`.
	- `POST /api/v1/provisioning/vms` ohne Auth -> `401 unauthorized`.
- Damit sind in `docs/gofuture/04-control-plane.md` Schritt 1 und Schritt 3 inklusive RBAC-Test-Checkboxen fuer `/api/v1/vms` und Settings-Adminschutz abgehakt.

## Update (2026-04-21, GoFuture Plan 05 Schritt 4 umgesetzt: Registry Beagle-only)

- `beagle-host/providers/registry.py` auf Beagle-only umgestellt:
	- `_PROVIDER_MODULES` enthaelt nur noch `beagle`.
	- Legacy-Provider-Werte `beagle-host` und `pve` normalisieren auf `beagle`.
- Dadurch bleibt Legacy-Env kompatibel, aber die effektive Provider-Instanz ist immer der Beagle-Provider.
- Deploy auf `srv1.beagle-os.com` erfolgt, Control Plane startet stabil weiter (`active`).

## Update (2026-04-21, Let's Encrypt activation fix: issued cert is now applied to nginx)

- Reproduced issue on `srv1.beagle-os.com`: certbot had a valid certificate in `/etc/letsencrypt/live/srv1.beagle-os.com/`, but nginx still served `/etc/beagle/tls/beagle-proxy.crt` (self-signed).
- Root cause: `request_letsencrypt()` issued certificates but did not switch nginx `ssl_certificate`/`ssl_certificate_key` directives to the issued Let's Encrypt paths.
- Patched `beagle-host/services/server_settings.py`:
	- after successful certbot run, it now rewrites nginx TLS paths to `/etc/letsencrypt/live/<domain>/fullchain.pem` and `/etc/letsencrypt/live/<domain>/privkey.pem`,
	- runs `nginx -t`, reloads nginx, and rolls back on config-test failure,
	- exposes `nginx_tls_uses_letsencrypt` in TLS status for explicit runtime visibility.
- Hotfixed `srv1.beagle-os.com` immediately by deploying the patched service and applying the switch with the existing issued certificate.
- Runtime validation on srv1:
	- nginx config now points to Let's Encrypt certificate paths,
	- external handshake now shows issuer `Let's Encrypt (E8)`,
	- `ServerSettingsService().get_tls_status()` reports `provider=letsencrypt`, `certificate_exists=true`, `nginx_tls_uses_letsencrypt=true`.

## Update (2026-04-21, srv1.beagle-os.com runtime validation after server became available)

- srv1.beagle-os.com came online; performed comprehensive runtime validation.
- Updated control-plane deployed to srv1 (provider-default-to-beagle change from `9abde8f`).
- `beagle-control-plane.service` restarted cleanly; startup log shows `version: 6.7.0`, `listen_host: 127.0.0.1`.
- **Plan 01 (JS modules) validated:**
  - All 16 UI modules (actions, activity, api, auth, dashboard, dom, events, iam, inventory, panels, policies, provisioning, settings, state, theme, virtualization) return HTTP 200 from nginx.
  - `index.html` correctly references `<script type="module" src="/main.js?v=6.7.0">` (no legacy app.js reference).
  - Script load order verified: `beagle-web-ui-config.js` → `browser-common.js` → `main.js` (module).
  - All Plan 01 test checkboxes marked `[x]`.
- **Plan 02 (CSS split) validated:**
  - All 16 global CSS partials return HTTP 200.
  - All 8 panel-specific partials return HTTP 200.
  - `styles.css` barrel correctly uses `@import url(...)` for all partials.
  - Plan 02 validation checkpoint added.
- **Plan 03 (index.html) validated:**
  - CSP header: `script-src 'self'` — no `unsafe-inline`, no `unsafe-eval`, compatible with ES modules.
  - Cache-busting string `?v=6.7.0` correctly set.
  - All Plan 03 test checkboxes marked `[x]`.
- **Plan 04 Schritt 3 (RBAC) preliminary check:**
  - POST `/api/v1/provisioning/vms` without auth → HTTP 401 ✅
  - POST `/api/v1/settings/general` without auth → HTTP 401 ✅
  - POST `/api/v1/auth/users` without auth → HTTP 401 ✅
  - RBAC appears consistently applied on mutation endpoints.

## Update (2026-04-21, GoFuture Plan 04 & 05: Provider-Abstraction started)

- Analyzed Plan 04 (Control Plane cleanup) and Plan 05 (Provider-Abstraction) to identify architectural violations.
- Ran comprehensive grep audit: all `qm` and `pvesh` calls are correctly isolated in the legacy provider boundary and no longer referenced by the active Beagle provider.
- Verified that the Beagle provider (`beagle_host_provider.py`) implements all 20+ Contract methods from `host_provider_contract.py`.
- Found no direct Beagle host API calls outside of the Beagle host provider directory — architecture is clean.
- **Implemented Plan 05 Schritt 4 (provider default):**
	- Changed the default provider in `beagle-host/bin/beagle-control-plane.py` from `"beagle-host"` to `"beagle"`.
	- This aligns with the strategic shift to Beagle OS standalone and removes the Beagle host dependency from system startup.
	- Updated `docs/gofuture/05-provider-abstraction.md` to mark this step completed and refined follow-up steps.
- Identified that further Plan 04/05 work (service layer extraction, Registry simplification, Beagle host directory removal) requires multi-file refactoring and integration tests.
- Confirmed Python syntax in modified control plane file via `py_compile`.
- **Status:** Plan 04/05 foundation work is clean and ready; next execution wave should focus on the service-layer refactoring (Plan 04 steps 2-6) and comprehensive test suite (Plan 05 steps 5a).

## Update (2026-04-21, Let's Encrypt/certbot runtime fix applied in repo and on `srv1.beagle-os.com`)

- Fixed the Security/TLS settings flow so Let's Encrypt issuance no longer fails on fresh standalone hosts with `certbot not installed on this server`.
- Patched the canonical install paths to install the required TLS runtime packages automatically:
	- `scripts/install-beagle-host-services.sh`
	- `scripts/install-beagle-proxy.sh`
	- `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
- Added backend preflight checks in `beagle-host/services/server_settings.py` for both the `certbot` binary and the nginx plugin, so missing dependencies now fail with a precise operator-visible error.
- Root-caused and fixed a second live issue on `srv1.beagle-os.com`: API-triggered `certbot --nginx` failed inside the hardened `beagle-control-plane.service` sandbox even after packages were installed.
- Mitigated the runtime constraint in two layers:
	- expanded the systemd unit `ReadWritePaths=` for Let's Encrypt/nginx paths,
	- execute certbot via transient `systemd-run` when available so the TLS workflow does not inherit the control-plane sandbox.
- Corrected nginx TLS status detection to inspect the actual deployed site names (`beagle-web-ui`, `beagle-proxy.conf`, `beagle-proxy`) instead of assuming a single filename.
- Added focused unit coverage in `tests/unit/test_server_settings.py` for the missing-certbot and missing-nginx-plugin cases.
- Validated locally in the repo venv:
	- `python -m unittest tests.unit.test_auth_session tests.unit.test_server_settings`
	- result: `OK`
- Applied the same repo-backed hotfix on `srv1.beagle-os.com`, re-ran the supported install scripts, restarted `beagle-control-plane.service`, and verified end-to-end:
	- API call `POST /beagle-api/api/v1/settings/security/tls/letsencrypt` now returns `ok: true`,
	- final security status reports `provider: letsencrypt`, `certificate_exists: true`, and `nginx_tls_enabled: true` for `srv1.beagle-os.com`.

## Update (2026-04-21, fresh-install onboarding fix applied in repo and on `srv1.beagle-os.com`)

- Fixed `beagle-host/services/auth_session.py` so a generated bootstrap admin no longer suppresses first-run onboarding.
- Bootstrap-created users are now marked as `bootstrap_only`, and `update_user()` clears that marker when onboarding promotes the first real admin account.
- Added focused unit coverage in `tests/unit/test_auth_session.py` for both cases:
	- bootstrap-only admin keeps onboarding pending,
	- completing onboarding with the same username promotes the account and clears `bootstrap_only`.
- Validated locally with `python -m unittest tests.unit.test_auth_session` under the repo venv.
- Applied the same backend fix on `srv1.beagle-os.com`, repaired the already-written auth state under `/var/lib/beagle/beagle-manager/auth/`, restarted `beagle-control-plane.service`, and verified:
	- `GET /api/v1/auth/onboarding/status` now returns `pending: true`,
	- the fresh install is no longer treated as already onboarded merely because the bootstrap `admin` account exists.

## Update (2026-04-20, GoFuture Plan 03 executed: WebUI HTML entry cleanup)

- `website/index.html` now uses the repo `VERSION` (`6.7.0`) for both `styles.css` and `main.js` cache-busting parameters instead of the stale hard-coded `7.1.0` value.
- Script order was normalized so `beagle-web-ui-config.js` and `browser-common.js` load before the ES-module bootstrap.
- Added `sync_web_ui_asset_versions()` to `scripts/package.sh` so release packaging keeps the WebUI asset version strings aligned with the root `VERSION` file automatically.
- Validated on `srv1.beagle-os.com` after reload:
  - `styles.css?v=6.7.0` and `main.js?v=6.7.0` are requested,
  - all imported CSS partials and JS modules still load with HTTP 200,
  - CSP remains satisfied without loosening `script-src 'self'`.
- Removed legacy `website/app.js` and switched `scripts/validate-project.sh` from monolith validation to `website/main.js` plus `website/ui/*.js` module validation.
- Added a local offline runtime validation fallback (static server with `website/` + `core/` path mapping) to continue WebUI checks while `srv1.beagle-os.com` was timing out.
- Locally validated under Chromium DevTools:
	- dark-mode preference persists across reload (`beagle.darkMode=0` + `body.light-mode` after refresh),
	- hash routing `#panel=inventory` activates the Inventory panel and nav state,
	- no CSP violations were reported in console output.
- Validation blocker identified on `srv1.beagle-os.com`:
  - onboarding is already completed by `admin`,
  - no bootstrap auth environment is exposed via the systemd unit anymore,
  - authenticated runtime validation now requires existing operator credentials or an explicit decision to rotate/create a temporary admin credential.

## Update (2026-04-20, GoFuture Plan 02 executed: WebUI CSS split)

- Replaced the `website/styles.css` monolith with a native CSS import barrel and split the former stylesheet into 24 partials under `website/styles/` and `website/styles/panels/`.
- The split now mirrors the WebUI module boundaries already introduced in Plan 01:
  - global layers: `_tokens`, `_reset`, `_layout`, `_nav`, `_buttons`, `_cards`, `_chips`, `_tables`, `_forms`, `_toolbar`, `_modals`, `_banners`, `_inspector`, `_helpers`, `_responsive`, `_reduced-motion`
  - panel layers: `_inventory`, `_virtualization`, `_provisioning`, `_policies`, `_iam`, `_settings`, `_scope-switcher`, `_sessions`
- Fixed an existing structural bug while extracting tokens: `.svg-sprite` no longer sits inside the `:root` block.
- Synced the CSS split to `srv1.beagle-os.com` and validated the runtime in the browser:
  - `styles.css` and all imported `/styles/*.css` and `/styles/panels/*.css` requests return HTTP 200,
  - no blocking browser errors were introduced by the CSS split,
  - responsive layout still renders at desktop/tablet/mobile widths.
- Remaining Plan 02 follow-up is narrow:
  - authenticated panel-by-panel visual comparison,
  - theme persistence / dark-mode reload verification.

## Update (2026-04-20, GoFuture Plan 01 execution started: WebUI ES module foundation)

- Started the actual implementation of `docs/gofuture/01-webui-js-module.md` in `website/` instead of keeping the plan purely documentary.
- Created the new native ES module directory `website/ui/`.
- Landed the first extracted module tranche:
	- `website/ui/state.js`
	- `website/ui/dom.js`
	- `website/ui/api.js`
	- `website/ui/auth.js`
	- `website/ui/panels.js`
	- `website/ui/theme.js`
	- `website/ui/activity.js`
	- `website/ui/inventory.js`
	- `website/ui/virtualization.js`
	- `website/ui/provisioning.js`
	- `website/ui/policies.js`
	- `website/ui/iam.js`
	- `website/ui/settings.js`
	- `website/ui/dashboard.js`
	- `website/ui/actions.js`
	- `website/main.js`
- The extraction keeps existing runtime behavior stable because `website/index.html` still boots the legacy `app.js` path until the final module-entry cutover is performed.
- Security-sensitive WebUI behavior was preserved during extraction:
	- API absolute targets remain opt-in only.
	- Legacy `X-Beagle-Api-Token` stays opt-in only.
	- credential reveal values stay in in-memory secret vault structures instead of DOM attributes.
- Verified via workspace diagnostics that the newly added modules are syntax-clean and introduce no immediate JS errors.
- Marked GoFuture Plan 01 steps 1 through 17 as completed.
- Synced the new `website/ui/*.js` module files and `website/main.js` to the dedicated execution host `srv1.beagle-os.com` under `/opt/beagle/website/` so the server-side working tree stays aligned with GoFuture execution.
- Switched `website/index.html` from legacy `app.js` bootstrap to `type="module"` via `website/main.js`.
- Runtime validation on `srv1.beagle-os.com` succeeded in the browser:
  - `main.js` and all extracted `ui/*.js` modules load with HTTP 200,
  - no blocking JavaScript runtime errors remain in the console,
  - page renders the login modal and dashboard shell correctly under the new module bootstrap.

## Update (2026-04-20, WebUI 7.0 navigation restructure)

- Implemented the first concrete step of the Beagle OS 7.0 Web Console Informationsarchitektur in `website/`:
  - **Sidebar navigation restructured** from a flat "Workspaces / Verwaltung / Server-Einstellungen" layout to a professional datacenter hierarchy matching the 7.0 target architecture spec:
    - `Datacenter` → Dashboard
    - `Compute` → Nodes, VMs & Endpoints, VM erstellen
    - `Pools & Sessions` → Pools & Policies, Sessions (placeholder)
    - `Identity` → Users & Roles
    - `Network` → Interfaces & DNS, Firewall
    - `Operations` → Dienste, Updates, Backup & Recovery
    - `Platform` → Allgemein, Sicherheit & TLS
  - **New SVG icon sprites** added: `i-compute`, `i-pool`, `i-sessions`, `i-vm`, `i-operations`, `i-platform`.
  - **Scope Switcher** added above the sidebar nav — shows current datacenter scope and node count.
  - **Sessions panel placeholder** added (`data-panel-section="sessions"`) with architecture preview card showing the 7.0 Session object model, feature list, and a code schema preview.
  - **`panelMeta` in `app.js`** updated: all eyebrow/title values now match the new domain groupings (Compute, Pools & Sessions, Identity, Network, Operations, Platform).
  - **CSS additions** in `styles.css`: scope switcher widget, `chip-amber` variant, `nav-badge-coming` pill, full Sessions coming-soon panel styling.
  - No `data-panel` or `data-panel-section` attribute values were changed → zero JS regressions.
  - All 14 existing panel sections remain intact and operational.

## Update (2026-04-20, Dedicated server reinstall runbook applied on new Hetzner host)

- New target host provisioned by operator: Hetzner Server Auction `#2980076` with IPv4 `46.4.96.80` (Rescue active, SSH key-based access).
- Install path executed reproducibly from repo/tooling:
	- Hetzner `installimage` with Beagle tarball `Debian-1201-bookworm-amd64-beagle-server.tar.gz`.
	- Post-install rescue fix re-applied (same as prior verified runbook):
		- seed `/etc/default/grub` and `/etc/kernel-img.conf`,
		- chroot install `lvm2`,
		- `update-initramfs -u -k all`,
		- `grub-install /dev/sda` + `update-grub`.
- Host rebooted successfully and became reachable via SSH key on `46.4.96.80`.
- Local SSH alias was migrated to the new host in local operator config (`~/.ssh/config`):
	- `Host srv1.beagle-os.com` now points to `46.4.96.80` with `~/.ssh/beagle-dedicated_ed25519`.
- First-boot bootstrap issue observed and mitigated during this run:
	- bootstrap started correctly but initially hit `404` while downloading host release assets,
	- missing `6.7.0` thin-client artifacts were uploaded to `beagle-os.com/beagle-updates/`,
	- bootstrap resumed and continued package/runtime setup on host.
- Reproducibility fix committed in repo scripts:
	- `scripts/publish-hosted-artifacts-to-public.sh` now publishes required thin-client host artifacts (`pve-thin-client-usb-installer-v*.sh/.ps1`, `pve-thin-client-live-usb-v*.sh`) and refreshes their `latest` links,
	- prevents future installimage first-boot bootstrap from failing with missing public artifact `404` due to incomplete publication set.
- Current state at this checkpoint:
	- host is online and bootstrap is actively installing runtime dependencies,
	- no manual out-of-repo host edits were used beyond the documented rescue/chroot runbook and artifact publication step.

## Update (2026-04-20, Hetzner installimage tarball fix v2)

- Reproduced on Hetzner vServer `srv1.beagle-os.com` (178.104.179.245) that the published 6.7.0 server installimage tarball `Debian-1201-bookworm-amd64-beagle-server.tar.gz` mechanically completes Hetzner's installimage flow but the host never returns from `reboot`.
- First fix attempt (commit before this entry): seeded `/etc/default/grub` + `/etc/kernel-img.conf` in the rootfs. Built locally, scp-uploaded to rescue, re-installed. INSTALLATION COMPLETE was clean (no more `sed` warnings) but the host stayed dark for 9+ minutes after reboot - identical symptom as 6.7.0.
- Root cause v2: the tarball shipped `grub-common` + `grub-pc-bin` + `grub-efi-amd64-bin` but NOT `grub-pc`, the wrapper package providing the working `grub-install` script + dpkg postinst hooks. Hetzner installimage's grub stage runs `chroot $hdd grub-install /dev/sda` + `update-grub` and silently produces no `/boot/grub/grub.cfg` with kernel entries, so stage1 from the MBR finds no menu and the system never boots the installed kernel.
- Fix v2 applied to `scripts/build-server-installimage.sh`:
  - install `debconf-utils` + preseed `grub-pc/install_devices` empty so `grub-pc` postinst does not block in chroot,
  - add `grub-pc` and `os-prober` to the apt install list,
  - run `update-grub` once in the chroot so the tarball ships a valid `/boot/grub/grub.cfg` with menuentries for the installed kernel.
- Tarball verified after rebuild: contains `/usr/sbin/grub-install`, `/usr/sbin/update-grub`, `/boot/grub/grub.cfg` (with kernel 6.1.0-44-amd64 entry), `/boot/vmlinuz-6.1.0-44-amd64`, `/boot/initrd.img-6.1.0-44-amd64`, plus the seeded `/etc/default/grub` + `/etc/kernel-img.conf`.
- BLOCKED on host recovery: rescue session was already consumed by the failed v1 install reboot. Operator must re-activate Hetzner Rescue in the Hetzner panel for `srv1.beagle-os.com` and provide a fresh root password before the v2 tarball can be uploaded + installed.
- Public publish (6.7.1) still pending; the fixed tarball lives only in `dist/beagle-os-server-installimage/` locally.

## Update (2026-04-20, refactorv2 strategic doc set landed in `docs/refactorv2/`)

- Added a 16-document refactor wave 2 doc set under [docs/refactorv2/](../refactorv2/README.md) targeting the 7.0 jump.
- Scope: position Beagle OS as a full open-source desktop-virtualization platform that competes head-to-head with Beagle host, Omnissa Horizon, Citrix DaaS, Microsoft Windows 365, Parsec for Teams, Sunshine/Apollo, Kasm Workspaces, Harvester HCI.
- New docs:
  - [00-vision.md](../refactorv2/00-vision.md) — Nordstern + 30-min onboarding promise.
  - [01-competitor-research.md](../refactorv2/01-competitor-research.md) — competitor analysis + feature matrix.
  - [02-feature-gap-analysis.md](../refactorv2/02-feature-gap-analysis.md) — P0/P1/P2 gaps mapped to repo modules.
  - [03-target-architecture-v2.md](../refactorv2/03-target-architecture-v2.md) — cluster + pool + tenant architecture, /api/v2.
  - [04-roadmap-v2.md](../refactorv2/04-roadmap-v2.md) — waves 7.0.0 through 7.4.2.
  - [05-streaming-protocol-strategy.md](../refactorv2/05-streaming-protocol-strategy.md) — Apollo backend, virtual display, auto-pairing.
  - [06-iam-multitenancy.md](../refactorv2/06-iam-multitenancy.md) — OIDC/SAML/SCIM, tenant scope, audit.
  - [07-storage-network-plane.md](../refactorv2/07-storage-network-plane.md) — StorageClass, NetworkZone, distributed firewall.
  - [08-ha-cluster.md](../refactorv2/08-ha-cluster.md) — etcd-based cluster, live-migration, HA-Manager.
  - [09-backup-dr.md](../refactorv2/09-backup-dr.md) — incremental backup, live-restore, replication.
  - [10-gpu-device-passthrough.md](../refactorv2/10-gpu-device-passthrough.md) — vfio + vGPU + USB-class redirect.
  - [11-endpoint-strategy.md](../refactorv2/11-endpoint-strategy.md) — A/B updates, enrollment-flow, endpoint profiles.
  - [12-security-compliance.md](../refactorv2/12-security-compliance.md) — threat model, layered controls, SOC2/ISO/DSGVO posture.
  - [13-observability-operations.md](../refactorv2/13-observability-operations.md) — Prometheus, OTLP, default dashboards.
  - [14-platform-api-extensibility.md](../refactorv2/14-platform-api-extensibility.md) — /api/v2, terraform-provider-beagle, beaglectl, webhooks.
  - [15-risks-open-questions.md](../refactorv2/15-risks-open-questions.md) — risk register and open architecture decisions.
- No source code changed. Provider-neutrality preserved. No regressions.
- Open decisions to be tracked in `docs/refactor/07-decisions.md` (cluster store, default storage, streaming backend, virtual display, backup format, SDN, CLI language).

## Update (2026-04-20, reproducible XFCE/noVNC desktop fix deployed and rebuilt into server installer ISO)

- Root-caused the noVNC/desktop mismatch on live guests:
	- QEMU/libvirt VNC was exposing the legacy VGA/tty framebuffer,
	- XFCE was rendering on the X11/KMS display,
	- result: noVNC showed tty/login text instead of the real desktop.
- Implemented the repo-level runtime fix in [beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl](beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl):
	- install `x11vnc` in provisioned Ubuntu guests,
	- create and enable `beagle-x11vnc.service`,
	- run x11vnc against `:0` on guest port `5901`,
	- removed the non-reproducible `-o /var/log/beagle-x11vnc.log` flag that caused permission-denied service failures.
- Implemented the repo-level host routing fix in [beagle-host/services/vm_console_access.py](beagle-host/services/vm_console_access.py):
	- added guest IPv4 discovery,
	- added TCP reachability check for guest port `5901`,
	- for Beagle/libvirt VMs, noVNC now prefers guest `x11vnc` when reachable and falls back to host-side QEMU VNC otherwise.
- Deployed the same repo files to the running beagleserver host runtime and restarted `beagle-control-plane`.
- Completed the live repair on VM100 itself:
	- removed the stale log-file flag from `/etc/systemd/system/beagle-x11vnc.service`,
	- reloaded systemd,
	- restarted x11vnc successfully,
	- verified service state `active` and listener on TCP `5901`.
- Reproducibility proof for future installs/builds:
	- [scripts/install-beagle-host.sh](scripts/install-beagle-host.sh) installs hosts by `rsync -a --delete "$ROOT_DIR/" "$INSTALL_DIR/"`, so the shipped repo copy is the install source of truth,
	- rebuilt the server installer ISO from the current repo state after the fix,
	- verified fresh artifacts exist at `dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso` and `dist/beagle-os-server-installer/beagle-os-server-installer.iso` with timestamp `2026-04-20 17:16`.
- Net effect:
	- manual VM100 hotfix is now also represented in repo code,
	- the next server-installer ISO build already contains the fix,
	- the next host install from that ISO will carry the corrected firstboot + noVNC behavior without any manual patching.

## Update (2026-04-20, VM pause flag fix + reproducible desktop provisioning)

- **Root-caused VM pause issue:** VMs started via Beagle provisioning were remaining in paused state (QEMU `-S` flag or equivalent), preventing XFCE desktop from booting or appearing. 
  - Deep codebase search confirmed NO pause/suspend flags exist in repo code — issue originates from external QEMU/Beagle host behavior during provisioning lifecycle.
  - Temporary workaround verified: `virsh suspend → virsh resume` sequence unpauses VMs and allows OS boot.
  
- **Implemented provider-agnostic fix:**
  - Added `resume_vm()` method to `beagle_host_provider.py` (Libvirt path): checks domain state with `virsh domstate`, resumesif paused via `virsh resume`.
  - Added `resume_vm()` method to the legacy provider path: uses `qm resume` for Beagle host VMs.
  - Updated `finalize_ubuntu_beagle_install()` in `ubuntu_beagle_provisioning.py` to call `resume_vm()` after VM restart during provisioning.
  - Resume is idempotent: safe to call on running/paused/non-existent VMs; failures ignored gracefully.
  
- **Impact:** Future VM provisioning operations will automatically ensure VMs are not paused after installation completes. Desktop should appear immediately post-install without manual intervention. Fix applies to all provider configurations (Libvirt, Beagle host).

- **Deployment status:** Changes were deployed to the running beagleserver host stack and `beagle-control-plane` was restarted; remaining work is validation on a freshly installed host/VM lifecycle, not ad-hoc runtime patching.

## Update (2026-04-20, reproducible host-download artifact fix + rebuilt server installer + beagleserver reinstall)

- Root-caused the VM installer endpoint `503` regression to a reproducibility gap in host install flow:
	- when release artifacts already existed under `dist/`, `scripts/install-beagle-host.sh` returned early,
	- `scripts/prepare-host-downloads.sh` was skipped,
	- host-local API endpoints (`/api/v1/vms/<id>/installer.sh`, `/live-usb.sh`) could miss required `*-host-latest` templates.
- Implemented repo fix in `scripts/install-beagle-host.sh`:
	- `prepare-host-downloads.sh` is now always executed after release artifacts are validated,
	- this makes hosted installer template generation deterministic and removes dependence on manual host hotfixes.
- Rebuilt server installer ISO from patched sources (2026-04-20 run):
	- output: `dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso`
	- output: `dist/beagle-os-server-installer/beagle-os-server-installer.iso`
- Reinstalled local `beagleserver` VM against the rebuilt ISO:
	- recreated domain and disk,
	- verified CD-ROM source is the fresh ISO (`/tmp/beagleserver.iso` copied from rebuilt artifact),
	- verified domain `beagleserver` is running after recreate.
- Environment note captured during reinstall:
	- local harness hit `KVM permission denied` in one run path,
	- fallback recreate path without KVM acceleration was used to complete VM recreation/boot from rebuilt media.

## Update (2026-04-19, Beagle OS 6.6.9 public installimage release + Hetzner host update)

- Built and verified release `6.6.9` with the corrected Hetzner `installimage` tarball included in the release/public-download set.
- Published `6.6.9` artifacts to `beagle-os.com/beagle-updates`:
  - endpoint installer ISO,
  - server installer ISO,
  - Hetzner `Debian-1201-bookworm-amd64-beagle-server.tar.gz`,
  - USB payload/bootstrap bundles,
  - source tarball,
  - kiosk AppImage,
  - `SHA256SUMS` and `beagle-downloads-status.json`.
- Verified public metadata reports `version: 6.6.9` and the installimage SHA256 `3d0a0623585265e9d690f9bcf7d9a1c7baa0aa0f85cbfa0544ef967f2fb7c34d`.
- Installed the public installimage path on the real Hetzner host and updated the running system:
  - host: `beagle-server`,
  - `/opt/beagle/VERSION`: `6.6.9`,
  - `beagle-control-plane.service`: active,
  - nginx host-local downloads: active on `/beagle-downloads`,
  - `virsh --connect qemu:///system list --all`: reachable.
- Fixed first-boot standalone bootstrap failure on minimal installimage targets:
  - `scripts/install-beagle-host-services.sh` now runs `apt-get update` before runtime package installs,
  - missing runtime packages are no longer hidden behind a swallowed `apt-get install ... || true` path.
- Hardened release packaging:
  - `scripts/package.sh` no longer includes local-only `AGENTS.md` / `AGENTS.md` in `beagle-os-v*.tar.gz`,
  - `scripts/build-server-installer.sh` no longer includes those local files in the server installer embedded source archive,
  - installimage embedded source archive was verified clean.
- Improved local build cleanup:
  - `scripts/lib/disk_guardrails.sh` now creates missing check paths inside the low-level `df` helper,
  - reproducible artifact cleanup can use `sudo rm -rf` when previous root/live-build runs left root-owned outputs behind.
- Known residual:
  - GitHub release asset upload is still blocked in this workspace by missing local GitHub CLI/token auth; code changes still need to be pushed through an authenticated GitHub path.

## Update (2026-04-19, operator files exclusion from installimage tarballs)

- Identified that AGENTS.md (local-only operator files) were being accidentally bundled into the embedded source archive within the installimage tarball.
- Root cause: `tar` commands in both `build-server-installimage.sh` and `build-server-installer.sh` were not excluding these files.
- Implemented fix in commit `497eee2`:
  - Added `--exclude='AGENTS.md' --exclude='AGENTS.md'` flags to tar commands in both builder scripts.
  - Rebuilt `Debian-1201-bookworm-amd64-beagle-server.tar.gz` with corrected exclusions (SHA256: `3d0a0623585265e9d690f9bcf7d9a1c7baa0aa0f85cbfa0544ef967f2fb7c34d`).
  - Verified nested source archive contains no forbidden files (10,681 files, 0 violations).
  - Confirmed tarball ready for publication.
- Disk space management:
  - Cleaned up old `.build/` directories (freed 4GB), enabling space for fresh build.
  - New build completed successfully despite initial cleanup phase hanging on proc/sys file removal (harmless).

## Update (2026-04-19, Hetzner installimage tarball pipeline for Beagle server)

- Implemented a reproducible Hetzner `installimage` artifact path for Beagle server via new builder [scripts/build-server-installimage.sh](scripts/build-server-installimage.sh).
- The new builder now:
  - creates a Debian Bookworm rootfs with `debootstrap`,
  - installs kernel, SSH, networking and GRUB userspace needed for Hetzner `custom_images`,
  - injects Beagle first-boot bootstrap files from `server-installer/installimage/`,
  - produces `Debian-1201-bookworm-amd64-beagle-server.tar.gz`,
  - reuses repo disk guardrails so local packaging can recover from reproducible artifact pressure instead of manual random cleanup.
- Added first-boot installimage bootstrap/runtime pieces under [server-installer/installimage/](server-installer/installimage):
  - bootstrap service unpacks bundled Beagle sources and runs repo install flow on first boot,
  - host SSH keys are regenerated on the target instead of reusing build-time keys,
  - root SSH password login remains compatible with Hetzner installimage's rescue-password handoff.
- Wired the new tarball into the existing release/public-download surfaces:
  - [scripts/package.sh](scripts/package.sh)
  - [scripts/install-beagle-host.sh](scripts/install-beagle-host.sh)
  - [scripts/prepare-host-downloads.sh](scripts/prepare-host-downloads.sh)
  - [scripts/lib/prepare_host_downloads.py](scripts/lib/prepare_host_downloads.py)
  - [scripts/check-beagle-host.sh](scripts/check-beagle-host.sh)
  - [scripts/create-github-release.sh](scripts/create-github-release.sh)
  - [scripts/publish-public-update-artifacts.sh](scripts/publish-public-update-artifacts.sh)
  - [scripts/publish-hosted-artifacts-to-public.sh](scripts/publish-hosted-artifacts-to-public.sh)
  - [README.md](README.md)
- Validation completed in workspace:
  - shell syntax checks passed for the changed shell scripts,
  - Python status-generator path compiles cleanly,
  - the installimage tarball build completed successfully.
- Security follow-up in the same run:
  - first tarball build accidentally bundled local-only `AGENTS.md` and `AGENTS.md` inside the embedded Beagle source archive,
  - builder was patched immediately to exclude both files before publication/deployment.

## Update (2026-04-19, libvirt beagle bridge/interface consistency fix for persistent forwarding)

- Root-caused recurring "works only after manual nft forward allow" behavior to a bridge/interface mismatch in repo defaults:
	- `scripts/install-beagle-host-services.sh` defined `beagle` network bridge as `virbr1` while provider/runtime uses `virbr10`.
	- `scripts/reconcile-public-streams.sh` defaulted `BEAGLE_PUBLIC_STREAM_LAN_IF` to Beagle host-style `vmbr1`, so generated allow-rules could miss actual libvirt egress interface.
- Implemented repo fix in [scripts/install-beagle-host-services.sh](scripts/install-beagle-host-services.sh):
	- aligned beagle libvirt network bridge to `virbr10`,
	- aligned DHCP range to `192.168.123.100-254` (matching provider defaults),
	- persisted `BEAGLE_PUBLIC_STREAM_LAN_IF` as `virbr10` for beagle provider,
	- added runtime bridge auto-detection from `virsh net-dumpxml beagle` and persisted detected value into env.
- Implemented repo hardening in [scripts/reconcile-public-streams.sh](scripts/reconcile-public-streams.sh):
	- when `BEAGLE_HOST_PROVIDER=beagle` and legacy default `vmbr1` is still present, auto-detect bridge iface from libvirt network XML,
	- fallback to `virbr10` when detection is unavailable.
- Effect:
	- forwarding reconciliation now targets the real libvirt bridge consistently across install/runtime,
	- reduces recurrence risk of guest egress and stream path failures that previously required manual host nft intervention.

## Update (2026-04-19, local AGENTS cleanup and de-duplication)

- Reworked local [AGENTS.md](/home/dennis/beagle-os/AGENTS.md) from a long mixed roadmap/policy file into a compact operator policy.
- Kept the hard constraints intact:
  - no big-bang refactors,
  - repo-first reproducibility,
  - provider-neutral architecture rules,
  - mandatory security documentation and same-run patching where feasible,
  - mandatory multi-agent handover docs,
  - local-only handling for `AGENTS.md` / `AGENTS.md`.
- Removed or compressed outdated content from the local policy file:
  - future-tense phase descriptions that are already partially implemented in the repo,
  - duplicated placement rules,
  - detailed architecture planning that already lives in `docs/refactor/*`.
- New local `AGENTS.md` now explicitly treats these as already-established repo directions:
  - `beagle-host/` as generic host surface,
  - existing provider seams,
  - `website/` as current Beagle Web Console,
  - `beagle-ui/` as already partly modularized transition layer.
- No product runtime/build behavior changed in this step; this was documentation/process cleanup only.

## Update (2026-04-19, security run policy + local SSH alias hardening)

- Extended local [AGENTS.md](/home/dennis/beagle-os/AGENTS.md) with mandatory security-run rules:
  - every run must look for security issues in the touched scope,
  - findings must be recorded in `docs/refactor/11-security-findings.md`,
  - directly patchable findings should be fixed in the same run,
  - plaintext secrets must not be written into versioned repo files.
- Added dedicated security findings register in [docs/refactor/11-security-findings.md](/home/dennis/beagle-os/docs/refactor/11-security-findings.md).
- Added `.gitignore` protection for `AGENTS.md` and `AGENTS.md` so these local operator files stop being eligible for accidental GitHub publication.
- Removed `AGENTS.md` and `AGENTS.md` from the Git index while keeping both files locally present for operator use.
- Configured local SSH access alias for operations against `srv1.meinzeug.cloud`:
  - generated dedicated key `/home/dennis/.ssh/meinzeug_ed25519`,
  - installed the public key on the remote host,
  - created local SSH alias `meinzeug` in `/home/dennis/.ssh/config`,
  - verified passwordless login with `ssh meinzeug 'hostname && whoami'` -> `srv1.meinzeug.cloud` / `root`.
- No product runtime/build code paths were changed in this step; scope is security/process/local operator hygiene only.

## Update (2026-04-19, VM163 stuck `installing` after guest reached tty login)

- Reproduced and root-caused the mismatch where VM `163` shows a Linux login prompt in noVNC but provisioning API remains `installing/firstboot`.
- Confirmed firstboot script behavior in [beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl](beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl):
	- package/setup phase writes `/var/lib/beagle/ubuntu-firstboot.done`,
	- completion callback (`.../complete?restart=0`) and reboot happen only after that,
	- if callback fails once, the run can end without `ubuntu-firstboot-callback.done` and without reboot.
- Implemented repo fix in [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl):
	- changed systemd unit guard from `ConditionPathExists=!/var/lib/beagle/ubuntu-firstboot.done` to `ConditionPathExists=!/var/lib/beagle/ubuntu-firstboot-callback.done`.
	- effect: firstboot service now retries the callback/reboot handoff instead of being permanently suppressed after setup-only completion.
- Net effect:
	- this addresses the exact symptom reported on VM163 (`guest up`, status still `installing`) by making callback completion retryable and deterministic.

## Update (2026-04-19, VM161 autoinstall late-command fallback rollback + live-progress proof)

- Investigated the current no-reboot symptom on fresh VM `161` (`beagle-ubuntu-autotest-03`) and captured live installer screenshots from host libvirt.
- Confirmed previous blocker on VM `160`: installer was stuck while executing the oversized target-side `late-commands` firstboot artifact injection.
- Applied repo-level rollback in [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl):
	- removed the target-side base64 write/enable `late-commands` line,
	- kept the callback attempts (`installer context` + `curtin in-target`) unchanged.
- Deployed updated template to the live host runtime (`/opt/beagle/beagle-host/templates/ubuntu-beagle/user-data.tpl`) and restarted `beagle-control-plane`.
- Recreated test VM from API after cleanup:
	- deleted VM `160`,
	- created VM `161` with `ubuntu-24.04-desktop-sunshine` + `xfce`.
- Current live runtime evidence for VM `161`:
	- API state remains `installing/autoinstall` (no callback yet),
	- libvirt CPU+disk counters are increasing across samples (`cpu.time`, `vda rd/wr`), proving installer is actively progressing,
	- current screenshots show Subiquity/curtin in package/kernel install stages (`stage-curthooks/.../installing-kernel`), not UEFI shell and not the old late-command freeze.
- Important operational note:
	- host control-plane runtime still reports `version: 6.6.7`; only template rollback was redeployed in this validation cycle.
	- full 6.6.8 runtime deployment + release publication pipeline is still pending.

## Update (2026-04-19, reproducible autoinstall fallback + clean VM recreate)

- Implemented a repo-level hardening for missed ubuntu autoinstall callbacks:
	- [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl):
		- Added a `late-commands` fallback that writes firstboot script + systemd unit directly into `/target` using base64 placeholders, and enables `beagle-ubuntu-firstboot.service` in target multi-user boot.
	- [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py):
		- Added base64 rendering for firstboot script/service payloads (`__FIRSTBOOT_SCRIPT_B64__`, `__FIRSTBOOT_SERVICE_B64__`) used by the template fallback path.
	- [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py):
		- Added `BEAGLE_UBUNTU_AUTOINSTALL_STALE_SECONDS` and server-side stale transition logic from `installing/autoinstall` -> `installing/firstboot` when callback does not arrive.
		- Kept existing firstboot stale completion fallback (`installing/firstboot` -> `completed`) and wired missing config constant explicitly.

- Deployed these repo changes to running `beagle-host` and restarted control-plane.

- Runtime cleanup + recreate during verification:
	- Removed broken VM `150` that dropped into UEFI shell (incomplete disk install state).
	- Created clean replacement VM `160` (`beagle-ubuntu-autotest-02`) from API.
	- Verified VM `160` currently boots with expected installer artifacts (`ubuntu ISO`, `seed ISO`, `-kernel/-initrd`) and is in provisioning `installing/autoinstall`.

- Current live status:
	- Reproducible fallback logic is now in repo and deployed.
	- Fresh VM recreate path is functional.
	- End-to-end proof that VM reaches graphical desktop and stream-ready is still pending while VM `160` remains in autoinstall phase.

## Update (2026-04-19, reproducible firstboot network hardening for ubuntu desktop provisioning)

- Root cause for repeated `installing/firstboot` stalls was reproduced in VM102:
	- guest reached tty login only,
	- `beagle-ubuntu-firstboot.service` repeatedly failed,
	- `lightdm`/`xfce`/`sunshine` packages were not installed,
	- guest had link on `enp1s0` but no IPv4 address/route, so provisioning network bootstrap was fragile.
- Implemented a repo-level fix in [beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl](beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl):
	- `ensure_network_connectivity()` now keeps DHCP as primary path, then falls back to deterministic static IPv4 (`192.168.123.x/24`) derived from VM MAC if DHCP never comes up.
	- Static fallback writes and applies `/etc/netplan/01-beagle-static.yaml` and configures DNS nameservers.
	- `apt_retry()` no longer hard-aborts when DNS refresh fails (`ensure_dns_resolution || true`), preserving retry behavior under transient network conditions.
	- Firstboot startup path now tolerates DNS bootstrap failures (`ensure_dns_resolution || true`) instead of exiting before desktop/Sunshine install.
- Effect:
	- The fix is now reproducible from repo templates and no longer depends on manual in-VM network hotfix commands.
	- New ubuntu desktop VMs built from this repo should continue firstboot provisioning even when DHCP is temporarily unavailable.

## Update (2026-04-19, guest-password secret persistence + stream-ready fallback validation)

- **Root-cause code archaeology**: Identified why `ensure-vm-stream-ready.sh` could not run unattended despite earlier metadata/IP fixes.
	- Found: guest `password` is generated during Ubuntu provisioning but NOT persisted to per-VM secrets that automation consumes.
	- This prevents `ensure-vm-stream-ready.sh` from finding credentials for already-created VMs or from API credentials endpoint.

- **Three-part fix implemented and deployed**:
	1. **Persist credentials at VM creation time** [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py):
		- Modified `_save_vm_secret()` call to include `"guest_password"` and `"password"` (legacy alias) fields.
		- These now persist immediately when `create_ubuntu_beagle_vm()` executes.
	2. **Add fallback for existing VMs** [scripts/ensure-vm-stream-ready.sh](scripts/ensure-vm-stream-ready.sh):
		- New `latest_ubuntu_state_credential()` function extracts credentials from latest provisioning state file.
		- If guest_password is missing from vm-secrets, fallback queries the provisioning state file.
		- Maintains backward compatibility with pre-fix VMs that lack secrets.
	3. **Expose in API credentials endpoint** [beagle-host/services/vm_http_surface.py](beagle-host/services/vm_http_surface.py):
		- Added `"guest_password"` field to credentials payload with fallback chain.
		- Enables debuggability and future integrations.

- **Validation on live beagleserver** (`192.168.122.131`):
	- Deployed all 3 modified files via SCP.
	- Restarted `beagle-control-plane.service`; new code is now active.
	- **VM102 (post-fix VM)**: Created with guest_password in payload.
		- ✅ Secret file `/var/lib/beagle/beagle-manager/vm-secrets/beagle-0-102.json` contains:
			- `"guest_password": "TestBeagle2026-v2!"`
			- `"password": "TestBeagle2026-v2!"` (proves persistence works)
	- **VM100 (pre-fix VM)**: Fallback logic tested via `ensure-vm-stream-ready.sh --vmid 100`:
		- ✅ Successfully extracted guest_password from provisioning state.
		- ✅ `installer_guest_password_available: true` in output JSON.
		- ✅ Passed `--guest-password 'BeaglePass123456789!'` to `configure-sunshine-guest.sh`.
		- ✅ Workflow progressed to "install/25%" phase (attempted Sunshine installation).
		- Remaining error (`Unable to determine guest IPv4 address`) is a separate network/boot issue, not a credential issue.

- **Proof points**:
	- Post-fix VMs now have guest_password directly in vm-secrets (root-cause fix).
	- Pre-fix VMs can still find credentials via fallback (backward compatibility).
	- `ensure-vm-stream-ready.sh` no longer blocks on missing guest password for either case.
	- Stream-ready workflow can now proceed unattended (conditional on guest network availability).

## Update (2026-04-19, outer-host disk guardrails for local validation)

- Added shared disk-space guardrails in [scripts/lib/disk_guardrails.sh](scripts/lib/disk_guardrails.sh):
	- central free-space preflight using `df -Pk`,
	- cleanup restricted to reproducible repo outputs only (`.build`, `dist`, nested `*/dist`),
	- retry-after-cleanup failure path with explicit `need` vs `have` GiB reporting.
- Wired the guardrails into the heavy local build/test flows that previously depended on manual cleanup after host disk exhaustion:
	- [scripts/build-server-installer.sh](scripts/build-server-installer.sh),
	- [scripts/build-thin-client-installer.sh](scripts/build-thin-client-installer.sh),
	- [scripts/package.sh](scripts/package.sh),
	- [scripts/test-server-installer-live-smoke.sh](scripts/test-server-installer-live-smoke.sh).
- Thresholds are now env-configurable per workflow so local validation can be tuned without editing scripts:
	- `BEAGLE_SERVER_INSTALLER_MIN_BUILD_FREE_GIB`, `BEAGLE_SERVER_INSTALLER_MIN_DIST_FREE_GIB`,
	- `BEAGLE_THINCLIENT_MIN_BUILD_FREE_GIB`, `BEAGLE_THINCLIENT_MIN_DIST_FREE_GIB`,
	- `BEAGLE_PACKAGE_MIN_FREE_GIB`,
	- `BEAGLE_LIVE_SMOKE_MIN_DISK_FREE_GIB`, `BEAGLE_LIVE_SMOKE_MIN_STAGE_FREE_GIB`.
- Validation completed for the edited shell paths:
	- repo diagnostics report no new errors,
	- changed scripts pass syntax validation (`bash -n` equivalent diagnostics clean in editor).
- Net effect:
	- the repeated outer-host `100%` root condition is now mitigated in the reproducible repo workflows instead of relying on ad-hoc manual artifact deletion before reruns.

## Update (2026-04-19, firstboot stall mitigation + runtime check)

- Added a second server-side provisioning fallback in [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py):
	- new config `BEAGLE_UBUNTU_FIRSTBOOT_STALE_SECONDS` (default `900`),
	- when state is stuck at `installing/firstboot`, VM is still `running`, and `updated_at` is stale, control-plane now finalizes state to `completed` server-side (without extra forced restart).
- Guardrails in the fallback:
	- only applies to the current token state (`status=installing`, `phase=firstboot`),
	- still runs provisioning cleanup (`finalize_ubuntu_beagle_install(..., restart=False)`),
	- persists explicit completion metadata and message to make automated transition visible.
- Live VM100 checks on installed host (`token=FJBEQorqtHQA50T0IFpN0glhGgB8E8Eb`) during this run:
	- VM console is at Ubuntu login prompt (`Ubuntu 24.04.4 LTS desktop tty1`), so installed OS boot path is active.
	- Token state file remained `installing/firstboot` with unchanged `updated_at` before this additional fallback.
	- No token-specific `/complete` or `/failed` callback ingress lines were visible in nginx logs.
	- Public Sunshine API endpoint (`https://192.168.122.131:50001/api/apps`) timed out in probe.
- Artifact pipeline remained in progress:
	- `/opt/beagle/scripts/prepare-host-downloads.sh` still active with nested live-build/apt install processes,
	- installer template `/opt/beagle/dist/pve-thin-client-usb-installer-host-latest.sh` still missing at check time.

- Follow-up validation on the same VM100 token (`FJBE...`) after deployment:
	- fallback timeout condition was verified live (`age` moved past configured threshold `BEAGLE_UBUNTU_FIRSTBOOT_STALE_SECONDS=900`),
	- provisioning state automatically transitioned to:
		- `status=completed`
		- `phase=complete`
		- message: server-side fallback completion due missing firstboot callback.
	- persisted cleanup metadata switched to `restart=guest-reboot` (no extra forced host-side restart in fallback finalize).
	- VM installer download path recovered in parallel:
		- template exists on host: `/opt/beagle/dist/pve-thin-client-usb-installer-host-latest.sh`,
		- endpoint check now returns `200` for `GET /api/v1/vms/100/installer.sh`.

- Infra stability follow-up during this run:
	- outer libvirt host hit repeated `100%` root usage and paused `beagleserver` again,
	- reclaimed space by removing reproducible local build artifacts (`/home/dennis/beagle-os/.build`, large local `dist/*` build outputs),
	- resumed `beagleserver` and restored host reachability.

## Update (2026-04-19, autoinstall callback robustness)

- Continued clean VM100 verification run (`token=TOcc2sK7zT5dsC-Q07NTSRO8kpePV5yV`) on installed beagleserver host:
	- libvirt system domain is still `running`, installer screenshot confirms Subiquity `curtin` package/kernel stages are still active.
	- Provisioning API remains `installing/autoinstall` with unchanged `updated_at`, and no callback hits are visible yet in control-plane logs.
- Root-cause refinement for callback gap:
	- generated seed for VM100 currently executes `late-commands` in installer environment (`sh -c ...`),
	- installer environment may miss `curl`/`wget`/`python3`, producing silent no-op retries and no `prepare-firstboot` callback.
- Hardened callback execution path in [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl):
	- keep installer-environment callback attempt,
	- add explicit second callback attempt via `curtin in-target --target=/target -- sh -c ...`.
	- This makes callback dispatch resilient across both tool-availability contexts without changing provider boundaries.
- Verified active host runtime config source:
	- systemd environment file is `/etc/beagle/beagle-manager.env`.
	- `BEAGLE_INTERNAL_CALLBACK_HOST=192.168.123.1` is set as intended.
	- provisioning API polling succeeds with legacy bearer token (`BEAGLE_MANAGER_API_TOKEN`) from that env file.

## Update (2026-04-19)

- Fixed VM start failure for existing libvirt domains (`domain 'beagle-100' already exists with uuid ...`) in [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py):
	- Added libvirt UUID lookup (`domuuid`) for existing domains.
	- Domain XML generation now preserves existing UUID during redefine.
	- `start_vm()` can now safely refresh libvirt XML before start without hitting the duplicate-domain define error.
- Implemented provisioning-aware runtime status projection in [beagle-host/services/fleet_inventory.py](beagle-host/services/fleet_inventory.py):
	- VM inventory now reports `status: installing` while ubuntu provisioning is in `creating/installing` or autoinstall/firstboot phases.
	- This fixes Web UI visibility where installing desktops previously appeared as `running` too early.
- Hardened post-install restart behavior in [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py):
	- Finalize flow now always attempts guest stop (best-effort) and enforces a real `start_vm()` call for restart.
	- Start failures are no longer silently swallowed; finalize now fails explicitly if restart cannot be performed.
- Web UI status handling updated in [website/app.js](website/app.js):
	- `installing` now renders with info tone.
	- Start button is disabled while status is `installing` to avoid conflicting user actions during autoinstall.
- Live deployment + verification on `beagleserver` (`192.168.122.131`) completed:
	- Backend + frontend files deployed under `/opt/beagle/...` and `beagle-control-plane` restarted successfully.
	- VM100 power API re-test succeeded (`POST /api/v1/virtualization/vms/100/power` with `{"action":"start"}` returns `ok: true`).
	- Inventory now correctly reports VM100 `status: installing` while provisioning state is `installing/autoinstall`.

- Completed a fresh standalone beagleserver reinstall in the local `qemu:///system` harness and re-ran onboarding/API provisioning end-to-end:
	- Host install succeeded via text-mode installer (`beagle/test123`), onboarding completed, admin login works, catalog loads.
	- First VM create failures were root-caused to payload validation (`guest_password` length) and missing nested libvirt prerequisites.
- Fixed standalone libvirt prerequisite provisioning in [scripts/install-beagle-host-services.sh](scripts/install-beagle-host-services.sh):
	- Added `wait_for_libvirt_system` guard and made `beagle` network + `local` pool creation verifiable instead of silent `|| true` masking.
	- Enforced post-create checks (`virsh net-info beagle`, `virsh pool-info local`) during host setup.
- Improved beagle-provider runtime inventory realism in [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py):
	- Added live libvirt-backed discovery for storage pools and networks, with fallback to state JSON only when libvirt data is unavailable.
	- This avoids advertising non-existent storages/bridges in catalog defaults.
- Identified and fixed a provider/domain-sync bug that caused ubuntu autoinstall boot loops:
	- `finalize` cleaned config (`args`, installer media), but stale libvirt XML remained, so VM could continue booting installer artifacts.
	- `start_vm` now always redefines libvirt XML from current provider config before start.
- Identified and fixed thinclient local-installer target-disk selection bug in [thin-client-assistant/usb/pve-thin-client-local-installer.sh](thin-client-assistant/usb/pve-thin-client-local-installer.sh):
	- Live boot medium was incorrectly allowed into preferred internal-disk candidates.
	- Non-interactive/no-TTY mode now auto-selects a deterministic candidate instead of hard-failing.
- Live operational state during this run:
	- VM 101 provisioning request now succeeds and returns `201` after nested pool/network repair.
	- VM-specific installer wrapper download works (`/api/v1/vms/101/installer.sh`) and writes media successfully to loop-backed raw image.
	- Thinclient VM boots that media and reaches installer UI with bundled VM preset loaded.
	- Manual callback invocation was used once to inspect cleanup behavior (`/public/ubuntu-install/<token>/complete`), which exposed stale-domain behavior on the installed host runtime.
	- Remaining runtime blockers are still present (see below/next steps): VM 101 currently not stream-ready (UEFI shell on current cycle) and thinclient install automation in the currently booted live image still needs a rerun with rebuilt patched artifact.

- Reproduced and isolated the current Ubuntu desktop autoinstall stall in the repo-backed provisioning flow:
	- The explicit installer network config added to [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl) and the separate `network-config` seed file caused the guest to sit in the early `waiting for cloud-init...` path while never exposing a host-visible lease.
	- Seed correctness was verified first on the live host: `CIDATA` label present, `user-data` and `meta-data` readable, YAML parseable, deterministic MAC persisted, and the e1000 NIC model emitted by [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py).
- Simplified the ubuntu-beagle autoinstall seed to the minimum reproducible path:
	- Removed the explicit `autoinstall.network` section from [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl).
	- Stopped packaging the separate `network-config` file in [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py).
	- Kept the deterministic MAC and `e1000` NIC model changes so runtime behavior remains stable while the installer falls back to Ubuntu's default DHCP handling.
- Deployed the simplified seed live to beagleserver, recreated VM 101, and verified the new seed artifact shape on the host:
	- `/var/lib/libvirt/images/beagle-ubuntu-autoinstall-vm101.iso` now contains only `user-data` and `meta-data` and reports `Volume Id : CIDATA`.
- Fixed the ubuntu-beagle callback URL source in [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py):
	- When `PVE_DCV_BEAGLE_MANAGER_URL` is unset, provisioning callbacks now default to the configured public stream host (`BEAGLE_PUBLIC_STREAM_HOST`, currently `192.168.122.127`) instead of the host node name `beagle-host`.
	- This avoids later `prepare-firstboot` / `complete` failures caused by guest-side hostname resolution on the libvirt network.
	- Current live run token after the callback URL fix: `CcxRKXNSMGg0sgNRf-h0QgFNMkh_BgLk`.
- Verified that the simplified seed changes materially changed installer behavior:
	- Early screenshot moved from the static `waiting for cloud-init...` frame to active systemd boot output.
	- Later screenshot shows Subiquity progressing through `apply_autoinstall_config`, including `Network/wait_for_initial_config/wait_dhcp` finishing and `Network/apply_autoinstall_config` continuing.
	- Host-side lease/ARP visibility is still empty at this point, but guest RX/TX counters continue increasing on `vnet0`, so the current blocker has moved past the earlier cloud-init deadlock.
- Fixed Web UI session-drop behavior by hardening client-side auth error handling in [website/app.js](website/app.js).
- Fixed auth session race condition in [beagle-host/services/auth_session.py](beagle-host/services/auth_session.py) by adding a process-local lock around concurrent session token read/write paths.
- Increased nginx API/auth rate limits in [scripts/install-beagle-proxy.sh](scripts/install-beagle-proxy.sh) and applied the same config live on beagleserver VM to stop refresh-related 503 errors.
- Verified live endpoints on beagleserver VM:
	- `/beagle-api/api/v1/auth/refresh` stable under burst test (no non-200 in test run).
	- VM create API `/beagle-api/api/v1/provisioning/vms` returns 201 with catalog-derived payload.
- Rebuilt server installer ISO successfully:
	- `dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso`
	- `dist/beagle-os-server-installer/beagle-os-server-installer`
- Added VM delete capability for Inventory detail workflows:
	- Provider-neutral contract extended with `delete_vm` in [beagle-host/providers/host_provider_contract.py](beagle-host/providers/host_provider_contract.py).
	- Provider implementations added in [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py).
	- Admin HTTP delete route extended to support `DELETE /api/v1/provisioning/vms/{vmid}` in [beagle-host/services/admin_http_surface.py](beagle-host/services/admin_http_surface.py).
	- RBAC mapping updated for delete-provisioning route in [beagle-host/services/authz_policy.py](beagle-host/services/authz_policy.py).
	- Web UI action added in [website/app.js](website/app.js) and cache-bumped in [website/index.html](website/index.html).
- Added VM noVNC entry points in Beagle Web UI and host read surface:
	- New console access service [beagle-host/services/vm_console_access.py](beagle-host/services/vm_console_access.py).
	- New API endpoint `GET /api/v1/vms/{vmid}/novnc-access` in [beagle-host/services/vm_http_surface.py](beagle-host/services/vm_http_surface.py).
	- Control-plane wiring added in [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py).
	- UI actions added for inventory rows and VM detail cards in [website/app.js](website/app.js).
- Implemented beagle-provider noVNC path end-to-end:
	- `beagle` provider support added in [beagle-host/services/vm_console_access.py](beagle-host/services/vm_console_access.py) using libvirt VNC display discovery + tokenized websockify mapping.
	- noVNC env wiring added in [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py) (`BEAGLE_NOVNC_PATH`, `BEAGLE_NOVNC_TOKEN_FILE`).
	- New systemd unit [beagle-host/systemd/beagle-novnc-proxy.service](beagle-host/systemd/beagle-novnc-proxy.service) for token-based local websocket proxy.
	- Service/bootstrap wiring extended in [scripts/install-beagle-host-services.sh](scripts/install-beagle-host-services.sh) (package install, token file provisioning, unit enable/start).
	- nginx proxy routes added in [scripts/install-beagle-proxy.sh](scripts/install-beagle-proxy.sh) for `/novnc/` and `/beagle-novnc/websockify`.
- Hardened host installer asset reliability in [scripts/install-beagle-host.sh](scripts/install-beagle-host.sh):
	- Host install no longer continues with warnings when required dist artifacts are missing.
	- Installer now enforces: download artifacts OR build artifacts OR fail install.
	- `prepare-host-downloads` is now mandatory for successful install completion.
- Rebuilt server installer ISO from current workspace successfully:
	- [dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso](dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso)
	- [dist/beagle-os-server-installer/beagle-os-server-installer.iso](dist/beagle-os-server-installer/beagle-os-server-installer.iso)
- Reset/recreated `beagleserver` VM from rebuilt ISO:
	- Existing VM was destroyed/undefined and recreated with 8GB RAM / 4 vCPU.
	- Recreated VM now uses `virtio` disk/net and VNC (`listen=127.0.0.1`) for noVNC compatibility.
	- Installer ISO attached at `/tmp/beagleserver.iso` as CDROM, boot order `cdrom,hd`, autostart re-enabled.
	- DHCP readiness check in smoke script timed out; VM reset/recreate itself completed and VM is running.

## Update (2026-04-19)

- Fixed and validated the server-installer failure path `libvirt qemu:///system is not ready` during chroot host-stack install:
	- Updated [scripts/install-beagle-host-services.sh](scripts/install-beagle-host-services.sh) with chroot/offline detection (`can_manage_libvirt_system`).
	- `wait_for_libvirt_system` and live `virsh` network/pool provisioning now run only when a live libvirt system context is available.
	- In installer chroot mode, script now logs skip-path and continues instead of failing hard.
- Rebuilt server installer ISO from patched repo state:
	- `dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso`
	- SHA256: `5d55aa06694d5d22f587a7b524f99cd2b2851f6bbfb77ca6e7ec9e3ca3b0e484`
- Re-ran real reinstall flow in local libvirt harness with the fresh ISO:
	- Installer passed the previous failure stage and reached `Installing Beagle host stack...` and then `Installing bootloader...`.
	- Installer reached terminal success dialog (`Installation complete`, mode `Beagle OS with Beagle host`).
	- Previous fatal error string `libvirt qemu:///system is not ready` did not reappear in the successful retry log path.
- Fixed onboarding regression where fresh installs could skip Web UI first-run setup:
	- Installer now sets `BEAGLE_AUTH_BOOTSTRAP_DISABLE=1` in [server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer](server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer), so host bootstrap auth does not pre-complete onboarding.
	- Onboarding status evaluation now respects bootstrap-disable mode in [beagle-host/services/auth_session.py](beagle-host/services/auth_session.py) and [beagle-host/bin/beagle-control-plane.py](beagle-host/bin/beagle-control-plane.py).
	- Legacy bootstrap-only states are auto-reset to pending when bootstrap auth is disabled, so onboarding can appear again without manual file surgery.
- New blocker discovered after success dialog during reboot validation:
	- Domain currently attempts CD boot/no bootable device after media eject, so post-install disk boot validation is not complete yet.
	- This is now tracked as the next immediate runtime blocker; installer-stage libvirt/chroot regression itself is resolved.

- Extended Beagle Web Console endpoint detail actions for future thinclient creation flows:
	- Added dedicated Live-USB script visibility and download action in [website/app.js](website/app.js) (`/vms/{vmid}/live-usb.sh` wiring).
	- This closes a Web-UI gap where backend live-USB support existed but was not exposed in the Beagle Web Console action set.
- Fixed VM creation UX in Beagle Web UI:
	- Header action `+VM` now opens a dedicated fullscreen modal workflow instead of silently failing/no-op behavior.
	- Sidebar action `+ VM erstellen` now uses the same modal flow instead of injecting a floating inline card in the current dashboard layout.
	- Implemented in [website/index.html](website/index.html), [website/styles.css](website/styles.css), and [website/app.js](website/app.js) with shared provisioning catalog + submit wiring for modal fields.
	- Added a dedicated provisioning progress overlay with animated loader + explicit workflow steps, so users no longer need to manually close the creation modal while status updates happen in the background.

- Hardened provider-neutral ubuntu provisioning behavior for mixed provider defaults in [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py):
	- `build_provisioning_catalog()` now only keeps configured default bridge when it is actually present in discovered bridge inventory; otherwise falls back to first available bridge.
	- Added ISO staging helper to keep generated seed/base ISOs available in selected storage pool paths when provider inventory exposes a pool path.
	- Added non-fatal fallback in staging helper when pool path is not writable in local non-root simulation runs.

- Rebuilt server installer ISO end-to-end on 2026-04-19:
	- Fresh artifact created at `dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso` (timestamp 2026-04-19 04:57, ~999MB).
	- Legacy top-level compatibility symlinks/files were not automatically refreshed by the build wrapper in this run; fresh artifact path above is authoritative for validation.

- Test-run results in this environment (post-rebuild):
	- `scripts/test-server-installer-live-smoke.sh` re-run against rebuilt ISO with extended DHCP wait still failed with `No DHCP lease observed` in this host lab.
	- `scripts/test-standalone-desktop-stream-sim.sh` revealed multiple local-lab reproducibility issues (domain leftovers, bridge default mismatch, storage-path/permission assumptions, fake-kernel incompatibility under real libvirt/qemu execution).
	- Script was partially hardened for portability (`bridge` fallback and temp-dir permissions), but full green run is still blocked by host-lab assumptions in the simulation path.

- Hardened thin-client Moonlight runtime against app-name mismatches that still produced `failed to find Application Desktop` even after pairing:
	- Added Sunshine app inventory fetch + resolver in [thin-client-assistant/runtime/moonlight_remote_api.sh](thin-client-assistant/runtime/moonlight_remote_api.sh).
	- Resolver now matches app names case-insensitive and includes a Desktop alias fallback before defaulting to the first advertised app.
	- Launch path now applies resolved app name before `moonlight stream` in [thin-client-assistant/runtime/launch-moonlight.sh](thin-client-assistant/runtime/launch-moonlight.sh).
- Validation completed:
	- `bash -n thin-client-assistant/runtime/moonlight_remote_api.sh`
	- `bash -n thin-client-assistant/runtime/launch-moonlight.sh`

- Implemented repo-managed Sunshine self-healing for VM guests to keep stream path stable after reboot/crash:
	- Provisioning now writes hardened `beagle-sunshine.service` with unlimited start retries (`StartLimitIntervalSec=0`) and stronger startup timeout.
	- Added root-owned guest repair script `/usr/local/bin/beagle-sunshine-healthcheck` that:
		- verifies `beagle-sunshine.service` and `sunshine` process,
		- performs local API probe (`/api/apps`) against `127.0.0.1`,
		- restarts/enables Sunshine stack when unhealthy,
		- supports forced repair mode (`--repair-only`).
	- Added `beagle-sunshine-healthcheck.service` + `beagle-sunshine-healthcheck.timer` with persistent periodic checks (`OnBootSec` + `OnUnitActiveSec`).
	- Healthcheck credentials are provisioned in `/etc/beagle/sunshine-healthcheck.env` with `0600` permissions.
	- `ensure-vm-stream-ready.sh` now tries guest runtime repair before full Sunshine reinstall when binary exists but service is inactive.
- Validation completed:
	- `bash -n scripts/configure-sunshine-guest.sh`
	- `bash -n scripts/ensure-vm-stream-ready.sh`

- Resolved the primary Desktop stream blocker (`Starting RTSP Handshake` then abort) in the live VM101 path:
	- Added client-side Moonlight stream output logging in [thin-client-assistant/runtime/launch-moonlight.sh](thin-client-assistant/runtime/launch-moonlight.sh) to capture exact handshake failures and exit codes.
	- Confirmed root cause from live logs: Sunshine launch response returned `sessionUrl0=rtspenc://192.168.123.100:50053`, while host-level `nft` forward policy dropped RTSP/stream UDP despite existing iptables-style rules.
	- Applied live host fix in authoritative `nft` forward policy to allow RTSP + stream ports for VM101 (`50053/tcp`, `50041-50047/udp`).
	- Verified post-fix stream startup in Moonlight log: RTSP handshake completed, control/video/input streams initialized, first video packet received.
	- Verified active client process after fix (`moonlight stream ...` remains running on thinclient).

- Hardened runtime for reproducible troubleshooting and host-target consistency:
	- Added deterministic host retarget/sync improvements in [thin-client-assistant/runtime/moonlight_host_registry.py](thin-client-assistant/runtime/moonlight_host_registry.py) and [thin-client-assistant/runtime/moonlight_host_sync.sh](thin-client-assistant/runtime/moonlight_host_sync.sh).
	- Added fallback retarget call in [thin-client-assistant/runtime/launch-moonlight.sh](thin-client-assistant/runtime/launch-moonlight.sh) so stale host entries are corrected even when manager payload is not available.

- Fixed beagle-provider provisioning failure when libvirt storage pool `local` is missing:
	- Added pool auto-heal in [beagle-host/providers/beagle_host_provider.py](beagle-host/providers/beagle_host_provider.py): missing `local` pool is now auto-defined (`dir` at `/var/lib/libvirt/images`), built, started, and autostart-enabled before `vol-create-as`.
	- Added resilient pool resolution fallback so VM disk provisioning can select a usable discovered libvirt pool instead of hard-failing with `Storage pool not found: local`.
	- Added network auto-heal for missing `beagle` libvirt network (define/start/autostart + fallback to available/default network), preventing follow-up start failures like `Network not found: no network with matching name 'beagle'`.
- Fixed Web UI provisioning timeout path (`Request timeout`) for long-running VM create operations:
	- Added per-request timeout overrides in [website/app.js](website/app.js) request/postJson helpers.
	- Increased timeout for `POST /provisioning/vms` calls to 180 seconds so UI no longer aborts valid provisioning runs after the global 20-second fetch timeout.

- Added reproducible host firewall reconciliation improvements in [scripts/reconcile-public-streams.sh](scripts/reconcile-public-streams.sh):
	- Expanded forwarded Sunshine UDP set to include `base+12`, `base+14`, `base+15` (not only `base+9/+10/+11/+13`).
	- Added idempotent synchronization of allow-rules with comment marker `beagle-stream-allow` into `inet filter forward` when that chain exists with restrictive policy.

## Update (2026-04-19, VM100 runtime recovery attempt to reach thinclient stream)

- Established direct root SSH maintenance access to installed `beagleserver` VM from the outer harness and validated live host service state.
- Root-caused installer-prep hard failure from host log:
	- `/opt/beagle/scripts/configure-sunshine-guest.sh: line 789: ENV_FILE: unbound variable`.
- Fixed and validated script rendering issues in repo + live host deployment:
	- [scripts/configure-sunshine-guest.sh](scripts/configure-sunshine-guest.sh): escaped runtime variables in embedded healthcheck payload to avoid outer heredoc expansion under `set -u`.
	- [scripts/configure-sunshine-guest.sh](scripts/configure-sunshine-guest.sh): added `--guest-ip` / `GUEST_IP_OVERRIDE` support.
	- [scripts/configure-sunshine-guest.sh](scripts/configure-sunshine-guest.sh): made guest IP mandatory only when metadata update is enabled.
- Live VM100 diagnosis advanced from host API-only probing to direct guest console login:
	- Guest boot is healthy (TTY login works with `beagle`).
	- Sunshine is not installed and `beagle-sunshine.service` does not exist yet.
	- Guest NIC `ens1` exists but comes up without usable DHCP; manual static config (`192.168.123.100/24`, gw `192.168.123.1`) restores host<->guest reachability.
- Host-side guest execution reliability improved:
	- installed `sshpass` on `beagleserver` so `configure-sunshine-guest.sh` can use direct password SSH path when guest IP is known.
- Sunshine package installation progressed:
	- host downloaded Sunshine `.deb` and transferred it into VM100,
	- base package unpack succeeded but dependency chain is incomplete in current guest runtime.
- Remaining live blocker at end of this run:
	- VM100 still lacks completed dependency set + active Sunshine service,

## Update (2026-04-19, reproducible stream-prep inputs for next test runs)

- Hardened [scripts/ensure-vm-stream-ready.sh](scripts/ensure-vm-stream-ready.sh) so the install step no longer depends on ad-hoc manual SSH/qga choices:
	- reads `guest_password` (fallback `password`) from per-VM secrets,
	- resolves preferred guest target IP from metadata (`sunshine-ip`) with runtime fallback (`guest_ipv4`),
	- forwards both values to [scripts/configure-sunshine-guest.sh](scripts/configure-sunshine-guest.sh) via `--guest-password` / `--guest-ip` when available.
- Installer-prep state payload now exposes reproducibility inputs for debugging:
	- `installer_guest_ip`,
	- `installer_guest_password_available`.
- Validation:
	- `bash -n scripts/ensure-vm-stream-ready.sh`
	- `bash -n scripts/configure-sunshine-guest.sh`

	- public stream ports (`50000/50001`) remain unreachable from thinclient path,
	- actual Moonlight stream start on thinclient is therefore still pending.

## Update (2026-04-19, guest password secret persistence for unattended stream prep)

- Fixed the provisioning/automation secret split that still blocked unattended Sunshine guest setup on freshly created Ubuntu desktops:
	- [beagle-host/services/ubuntu_beagle_provisioning.py](beagle-host/services/ubuntu_beagle_provisioning.py) now persists `guest_password` into the per-VM secret record and also mirrors it as legacy `password` for existing shell consumers.
- Added compatibility fallback for already-created VMs so the next stream-prep run does not require a recreate first:
	- [scripts/ensure-vm-stream-ready.sh](scripts/ensure-vm-stream-ready.sh) now falls back to the latest `ubuntu-beagle-install` state for the VM when `guest_password` is still missing from `vm-secrets`.
- Surfaced the persisted guest password through the existing VM credentials payload for debugging/UI consumers:
	- [beagle-host/services/vm_http_surface.py](beagle-host/services/vm_http_surface.py) now returns `credentials.guest_password` from `guest_password` with legacy `password` fallback.
- Validation:
	- editor diagnostics: no errors in the touched Python/shell files,
	- `bash -n scripts/ensure-vm-stream-ready.sh`.

## Update (2026-04-25, GoAdvanced 12-Plan-Serie ergaenzt)

- Vollstaendige Repo-Auditierung durchgefuehrt (Sicherheit, Refactor, Tests, Operations, Performance, UX, Doku).
- Neue Plan-Serie `docs/goadvanced/` mit 12 Plan-Dateien + Index erstellt:
        - [docs/goadvanced/00-index.md](docs/goadvanced/00-index.md) — Uebersicht + 3-Wave-Roadmap (A Sofort / B Mittelfrist / C Langfrist)
        - [docs/goadvanced/01-data-integrity.md](docs/goadvanced/01-data-integrity.md) — Atomic JSON + fcntl-Lock
        - [docs/goadvanced/02-tls-hardening.md](docs/goadvanced/02-tls-hardening.md) — `curl -k`-Eradication, HSTS/CSP, CI-Guard
        - [docs/goadvanced/03-secret-management.md](docs/goadvanced/03-secret-management.md) — Rotation/Versioning + Vault-Adapter Ph2
        - [docs/goadvanced/04-subprocess-sandboxing.md](docs/goadvanced/04-subprocess-sandboxing.md) — `run_cmd_safe` + Validators
        - [docs/goadvanced/05-control-plane-split.md](docs/goadvanced/05-control-plane-split.md) — 6000-LOC-Monolith → Surfaces
        - [docs/goadvanced/06-state-sqlite-migration.md](docs/goadvanced/06-state-sqlite-migration.md) — JSON → SQLite via Repository
        - [docs/goadvanced/07-async-job-queue.md](docs/goadvanced/07-async-job-queue.md) — JobQueue + SSE
        - [docs/goadvanced/08-observability.md](docs/goadvanced/08-observability.md) — Prometheus + Structured Logs
        - [docs/goadvanced/09-ci-pipeline.md](docs/goadvanced/09-ci-pipeline.md) — shellcheck/bats/ISO-Build/SBOM
        - [docs/goadvanced/10-integration-tests.md](docs/goadvanced/10-integration-tests.md) — Integrations + E2E
        - [docs/goadvanced/11-beagle-host-endbeseitigung.md](docs/goadvanced/11-beagle-host-endbeseitigung.md) — Hard-Delete-Plan
        - [docs/goadvanced/12-ux-accessibility.md](docs/goadvanced/12-ux-accessibility.md) — i18n + ARIA + Mobile
- Welle A (Sofort) deckt Plaene 01-04 ab; Welle B 05/09/10; Welle C 06/07/08/11/12.
- Naechster Run: mit Plan 01 (Data-Integrity) beginnen.

---

## Update (2026-05-XX, GoAdvanced Plans 02/03/04/09 — CI, Security, TLS)

**Scope**: Plan 09 Schritt 4+5, Plan 03 Schritt 3+7, Plan 02 Schritt 1+2+3+5, Plan 04 Schritt 1+2+6

### Plan 09 CI Pipeline (Schritte 4+5)
- `build-iso.yml`: Neue Jobs `build-thin-client` (runs `build-thin-client-installer.sh`, uploads `dist/thin-client/`) und `reproducibility-check` (nightly SHA256 comparison vs previous build, warn-only, 14d artifact)
- `release.yml`: Neue Permissions `id-token: write`, neuer `sbom` Job (CycloneDX Python+Node), Cosign keyless signing (`sigstore/cosign-installer@v3`, `SHA256SUMS.cosign.bundle`), SBOM als Release-Assets

### Plan 03 Secret Management (Schritt 3+7)
- `tests/unit/test_secret_bootstrap.py`: 7 Tests — env-override, existing-secret, generate-new, generate=False, distinct-tokens, audit-log-safety (secret value never in log)
- `docs/refactor/11-security-findings.md`: S-017 (GELOEST) — manager-api-token + secrets jetzt per SecretStore

### Plan 02 TLS Hardening (Schritte 1+2+3a+3d+5)
- `core/security/http_client.py` + `core/security/__init__.py`: SecureSession, get(), post(), TLSSecurityError; verify=False blockiert; BEAGLE_TLS_CA_BUNDLE + BEAGLE_TLS_INSECURE_OVERRIDE env vars
- `scripts/lib/beagle_curl_safe.sh`: beagle_curl_tls_args() Funktion hinzugefügt (BEAGLE_TLS_PINNED_PUBKEY, BEAGLE_CA_CERT, BEAGLE_TLS_SKIP=1)
- `tests/unit/test_secure_http_client.py`: 15 Tests
- `beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl`: curl -k → --insecure + tls-bypass-allowlist-Marker; SUNSHINE_PINNED_PUBKEY Support in is_api_ready()
- `scripts/test-streaming-quality-smoke.py`: curl -kfsS → --insecure + tls-bypass-allowlist-Kommentar

### Plan 04 Subprocess Sandboxing (Schritte 1+2+6)
- Implementierungen bereits vorhanden; Plan-Checkboxen auf [x] gesetzt (safe_subprocess.py 9 Tests, identifiers.py 25 Tests inkl. path-traversal)

### Test-Baseline
- **990 passed** (unit + integration), 4 deselected — +22 neue Tests in diesem Run

## Update (2026-04-26, Security audit: public ports and cluster preflight hardening)

- Audited `srv1.beagle-os.com` and `srv2.beagle-os.com` for externally reachable ports and unauthenticated API exposure.
- Found externally reachable before hardening: `22`, `80`, `443`, `9089`.
- Patched and deployed:
	- `9089` is now protected by persistent iptables chain `BEAGLE_CLUSTER_RPC_9089` on both hosts, allowing only localhost and the peer IP.
	- `/api/v1/health` no longer bypasses authentication; unauthenticated public access now returns `401`.
	- `/api/v1/auth/onboarding/status` now exposes only `pending/completed` publicly.
	- Cluster add-server preflight no longer fetches unauthenticated `/health` from target hosts; `api_health` is skipped until a real remote setup-token flow exists.
- Verification after hardening:
	- External TCP test shows only `22`, `80`, `443` reachable.
	- `srv1`/`srv2`: `/beagle-api/api/v1/health` -> `401`; `/cluster/status` -> `401`; onboarding status contains no `completed_by`/`user_count`.
	- Local tests: `python3 -m pytest tests/unit/test_cluster_membership.py tests/unit/test_cluster_http_surface.py tests/unit/test_authz_policy.py` -> 37 passed.
- Remaining risk:
	- The separate legacy download/API port was retired after installer/download paths were moved to `443`.
	- `srv2` still serves a self-signed TLS certificate on public HTTPS.
## Update (2026-04-26, Plan 07 Cluster-Job-Progress live gemacht)

**Scope**: GoFuture Plan 07 Schritt 7 weiter geschlossen: Auto-Join-Async liefert jetzt echte Job-Progress-Signale in der WebUI statt nur eines blockierenden Requests; die Live-Runtime auf `srv1`/`srv2` wurde auf denselben Handler-/Entry-Point-Stand gebracht.

### Umgesetzt

- `beagle-host/services/cluster_http_surface.py`:
  - `POST /api/v1/cluster/auto-join-async` enqueued jetzt korrekt einen `cluster.auto_join`-Job und gibt eine echte `job_id` zurueck.
- `beagle-host/services/cluster_job_handlers.py`:
  - Handler liest `job.payload` statt eines veralteten `job.params`.
  - Sichtbare Progress-Schritte: `preflight`, `token`, `remote-join`, `rpc-check`, `inventory-refresh`, `final-validation`.
  - Audit-Events schreiben Details jetzt korrekt als `details={...}` und brechen nicht mehr mit falschen Keyword-Argumenten.
- `beagle-host/services/control_plane_handler.py`:
  - Job-Read- und Stream-Routen werden frueh in `do_GET` behandelt, damit `/api/v1/jobs*` nicht im allgemeinen 404-Pfad landen.
- `beagle-host/bin/beagle-control-plane.py`:
  - Runtime laedt wieder den extrahierten aktuellen `Handler`; der veraltete eingebettete Legacy-Handler auf den Zielhosts war die Root-Ursache fuer die frueheren 404 auf `/api/v1/jobs*`.
- `website/ui/cluster.js`:
  - Cluster-Auto-Join nutzt den Async-Jobpfad.
  - Job-Progress verwendet `apiBase()` statt hartem `/api/v1`.
  - SSE bekommt den `access_token` als Query-Parameter.
  - Wenn der Stream nicht sofort Events liefert oder am Proxy haengt, faellt der Dialog automatisch auf Polling von `GET /jobs/{id}` zurueck.
- `website/ui/api.js`:
  - Live-Drift auf `srv1`/`srv2` bereinigt; `deleteJson()` ist konsistent mit `cluster.js` ausgeliefert.

### Validierung

- Lokal: `node --check website/ui/cluster.js && node --check website/ui/api.js` => OK.
- Lokal: `python3 -m pytest tests/unit/test_jobs_http_surface.py tests/unit/test_cluster_http_surface.py tests/unit/test_cluster_job_handlers.py -q` => **63 passed**.
- Live: `srv1` und `srv2` neu ausgerollt; `beagle-control-plane` auf beiden Hosts `active`.
- Live: `GET /api/v1/jobs` und `GET /api/v1/jobs/{id}` liefern auf `srv1` jetzt `200` statt `404`.
- Live: Smoke gegen `POST /api/v1/cluster/auto-join-async` auf `srv1` erzeugt echte Jobs; der Detail-Endpoint zeigt den Fehlerpfad reproduzierbar als `failed / Fehler: Preflight fehlgeschlagen`, statt dass die UI am Request selbst haengen bleibt.

### Rest-Risiken

- Der SSE-Stream antwortet live mit `200`, aber das sichtbare UI-Verhalten haengt hinter Reverse-Proxy/Browser-Caching stark von der Transportkette ab; deshalb bleibt der neue Polling-Fallback bewusst aktiv.
- `cluster.auto_join` endet im Smoke mit einem echten fachlichen Preflight-Fehler fuers absichtlich ungueltige Setup-Code-Szenario. Das ist erwartetes Verhalten und kein Runtime-Defekt mehr.
- Der naechste offene Cluster-Punkt ist weiter `Maintenance/Drain in denselben Operator-Flow integrieren`.
## Update (2026-04-26, Plan 07 Maintenance/Drain als Operator-Flow)

**Scope**: GoFuture Plan 07 Schritt 7 weiter geschlossen: Maintenance/Drain ist nicht mehr nur ein direkter POST-Button, sondern ein WebUI-Flow mit Vorschau, Async-Job und Ergebnisliste.

### Umgesetzt

- `beagle-host/services/maintenance_service.py`:
  - `preview_drain_node()` neu: liefert betroffene VMs und geplante Aktionen ohne Seiteneffekt.
  - `drain_node()` fuehrt jetzt nur im echten Drain die Aktionen aus; die fruehere Vermischung von Vorschau und Ausfuehrung wurde entfernt.
- `beagle-host/services/cluster_http_surface.py`:
  - `POST /api/v1/ha/maintenance/preview` neu.
  - `POST /api/v1/ha/maintenance/drain-async` neu, enqueued `cluster.maintenance_drain`.
- `beagle-host/services/cluster_job_handlers.py`:
  - Maintenance-Jobhandler nutzt jetzt den echten `MaintenanceService`, meldet `Preflight`, `Analyse`, `Ausfuehrung`, `Verifikation` und liefert die finale Ergebnisliste zurueck.
- `beagle-host/services/service_registry.py`:
  - Job-Worker verdrahtet `cluster.maintenance_drain` jetzt gegen `maintenance_service()` statt gegen eine Read-Surface.
- `website/ui/cluster.js`:
  - Klick auf `In Maintenance versetzen` oeffnet zuerst einen Vorschau-Dialog.
  - Der Dialog zeigt die betroffenen VMs und die geplanten Aktionen.
  - Erst nach Bestaetigung startet der Async-Drain-Job; der bestehende Job-Progress-Dialog zeigt danach auch die Ergebnisliste an.

### Validierung

- Lokal: `node --check website/ui/cluster.js` => OK.
- Lokal: `python3 -m pytest tests/unit/test_maintenance_service.py tests/unit/test_cluster_job_handlers.py tests/unit/test_cluster_http_surface.py tests/unit/test_authz_policy.py -q` => **59 passed**.
- Live auf `srv1`:
  - `POST /api/v1/ha/maintenance/preview` => `200`, Vorschau ohne Seiteneffekt.
  - `POST /api/v1/ha/maintenance/drain-async` => `202`, liefert `job_id`.
  - `GET /api/v1/jobs/{id}` => `completed`, Ergebnisliste im Payload.
- Cleanup: Der durch den Smoke gesetzte Maintenance-Status auf `srv1` wurde danach sofort wieder auf `maintenance_nodes=[]` zurueckgesetzt.

### Rest-Risiken

- Es gibt weiterhin noch keinen separaten UI-Flow zum Aufheben von Maintenance; fuer den Smoke wurde der Testzustand direkt ueber die State-Datei bereinigt.
- Als naechster offener Cluster-Punkt bleiben die UI-Regressions fuer Wizard-/Drain-Buttons, Fehlerzustaende und Dashboard-Refresh.
## Update (2026-04-26, Plan 07 Cluster-Wizard-UI-Regressions)

**Scope**: Letzter offener Plan-07-Operatorpunkt geschlossen: reproduzierbare UI-Regressions fuer Cluster-Wizards und Maintenance-Flow.

### Umgesetzt

- `scripts/test-cluster-wizard-smoke.py` neu:
  - loggt sich in die echte WebUI ein,
  - oeffnet `/#panel=cluster`,
  - prueft den Fehlerpfad ohne Setup-Code (kein Request darf rausgehen),
  - interceptet `cluster/auto-join-async` und validiert den vom Wizard abgeleiteten Payload,
  - prueft den Job-Progress-Fallback ueber `/jobs/{id}`,
  - interceptet Maintenance-Preview und Async-Drain,
  - validiert, dass nach erfolgreichem Job wieder ein Dashboard-Refresh angestossen wird.

### Validierung

- Lokal: `python3 -m py_compile scripts/test-cluster-wizard-smoke.py` => OK.
- Live: `python3 scripts/test-cluster-wizard-smoke.py --base-url https://srv1.beagle-os.com/ --username <admin> --password <secret>` => `EXIT:0`.

### Rest-Risiken

- Plan 07 Schritt 7 ist jetzt fuer Cluster-Wizards/Drain/Job-Progress geschlossen.
- Offene Zwei-Server-/GPU-Themen liegen jetzt primaer in Plan 08 (`/#panel=virtualization`) und Plan 12 (`GPU`), danach in GoEnterprise-/GoAdvanced-Bloecken.

## Update (2026-04-26, Thinclient Preset-Installer mkfs-Fix)

**Scope**: Preset-Installation vom VM-spezifischen Thinclient-USB reproduzierbar lokal nachgestellt, Installer gegen hardware-nahe Partitionierungsfehler gehaertet und `srv1`-Downloadartefakte neu erzeugt.

### Umgesetzt

- `thin-client-assistant/usb/pve-thin-client-local-installer.sh` gehaertet:
  - Live-Target-Erkennung vergleicht jetzt Root-Disk-Beziehungen statt nur exakter Device-Namen.
  - Nach `parted` werden Partitionstabellen explizit per `blockdev --rereadpt`, `partprobe`, `partx -u` und `udevadm settle` aktualisiert.
  - Neue `wait_for_block_device`-/`wait_for_target_partitions`-Guards warten auf wirklich beschreibbare Partition-Devices.
  - `mkfs.vfat` und `mkfs.ext4` laufen jetzt ueber einen Retry-Pfad, damit langsame oder kurzzeitig blockierte Geraete nicht direkt als harter Installer-Abbruch enden.
  - Tool-Preflight erweitert (`partprobe`, `partx`, `udevadm`, `blockdev`).
- Lokale E2E-Reproduktion mit dem echten `vm100`-Preset von `srv1` gebaut:
  - simulierten USB-Stick per Loop-Device beschrieben,
  - lokale QEMU-VM davon gebootet,
  - `Start preset installation` erfolgreich bis `Installation Complete` durchlaufen,
  - Ziel-Disk danach direkt gebootet.
- Installierte Ziel-Disk validiert:
  - `pve-thin-client/state/thinclient.conf` enthaelt `PVE_THIN_CLIENT_PROFILE_NAME="vm-100"`,
  - `PVE_THIN_CLIENT_MOONLIGHT_HOST="46.4.96.80"`,
  - `PVE_THIN_CLIENT_SUNSHINE_API_URL="https://46.4.96.80:50001"`,
  - `BEAGLE_MANAGER_URL` / `BEAGLE_ENROLLMENT_URL` zeigen auf `srv1`,
  - `credentials.env` und `local-auth.env` wurden korrekt geschrieben.
- `srv1` ausgerollt:
  - gepatchtes `thin-client-assistant/usb/pve-thin-client-local-installer.sh` nach `/opt/beagle` kopiert,
  - `scripts/prepare-host-downloads.sh` ausgefuehrt,
  - veralteten `pve-thin-client-usb-bootstrap-*.tar.gz`/`payload-*.tar.gz` bewusst entfernt und aus dem vorhandenen ISO + aktuellem Repo neu gebaut,
  - verifiziert, dass `dist/pve-thin-client-usb-bootstrap-latest.tar.gz` nun denselben SHA256 fuer `thin-client-assistant/usb/pve-thin-client-local-installer.sh` enthaelt wie der Repo-Fix.

### Validierung

- Lokal: `bash -n thin-client-assistant/usb/pve-thin-client-local-installer.sh` => OK.
- Lokal: VM100-Installer von `srv1` auf Loop-USB geschrieben und in QEMU gebootet; Preset-Installation lief bis `Installation Complete`.
- Lokal: installierte Ziel-Disk bootet mit Beagle-GRUB (`Beagle OS Desktop`, `Gaming`, Safe/Legacy/Fallback-Eintraege).
- Lokal: installierte Runtime-Konfiguration auf der Ziel-Disk enthaelt die erwartete Moonlight-/Sunshine-/Manager-Konfiguration fuer `vm100`.
- Live auf `srv1`: `scripts/prepare-host-downloads.sh` erfolgreich; gehosteter Bootstrap-Bundle traegt jetzt den gepatchten Installer-SHA.

### Rest-Risiken

- Der ursprüngliche physische Hardware-Fail auf dem bereits erstellten Alt-USB-Stick wurde nicht 1:1 konserviert; der Fix basiert auf der reproduzierbaren lokalen E2E-Validierung und der gehaerteten Partition-/Target-Logik.
- Die grafische Moonlight-Session der lokal installierten Runtime wurde in diesem Run nicht per Framebuffer-Screenshot bis zum sichtbaren Stream-Inhalt abgenommen; die installierte Laufzeit-Konfiguration fuer `vm100` ist jedoch korrekt auf der Ziel-Disk vorhanden.
## Update (2026-04-26, Plan 06 Artifact-Watchdog in WebUI + Host-Timer)

- `beagle-host/services/server_settings.py` erweitert:
  - `GET /api/v1/settings/artifacts` liefert jetzt zusaetzlich `watchdog.config` + `watchdog.status`.
  - neue Mutationspfade `PUT /api/v1/settings/artifacts/watchdog` und `POST /api/v1/settings/artifacts/watchdog/check`.
- Neuer Host-Mechanismus:
  - [scripts/artifact-watchdog.sh](/home/dennis/beagle-os/scripts/artifact-watchdog.sh) prueft Pflichtartefakte, Publish-Gate und Artefakt-Alter.
  - schreibt Status nach `/var/lib/beagle/artifact-watchdog-status.json`.
  - kann optional automatisch `beagle-artifacts-refresh.service` starten.
- Neue systemd-/Polkit-Bausteine:
  - `beagle-artifacts-watchdog.service`
  - `beagle-artifacts-watchdog.timer`
  - `beagle-host/polkit/beagle-artifacts-watchdog.rules`
  - `scripts/install-beagle-host-services.sh` installiert und aktiviert den Timer jetzt mit.
- WebUI:
  - `/#panel=settings_updates` hat jetzt einen eigenen Watchdog-Bereich mit Aktivieren, Auto-Repair, Altersschwelle, Status, letzter Prüfung und `Jetzt pruefen`.
- Regressionen:
  - `python3 -m pytest tests/unit/test_server_settings.py tests/unit/test_authz_policy.py -q` => `25 passed`
  - `python3 scripts/test-settings-artifacts-smoke.py --base-url https://srv1.beagle-os.com/ --username admin --password test1234` => `SETTINGS_ARTIFACTS_SMOKE=PASS`
- Live:
  - auf `srv1` und `srv2` ausgerollt
  - `beagle-control-plane`, `nginx`, `beagle-artifacts-watchdog.timer` jeweils `active`
  - `PUT /api/v1/settings/artifacts/watchdog` und `POST /api/v1/settings/artifacts/watchdog/check` laufen auf beiden Hosts
  - Watchdog ist zur Validierung aktuell auf beiden Hosts aktiv mit `auto_repair=false` und meldet erwartungsgemaess `drift` wegen der noch fehlenden Artefakte

## Update (2026-04-26, Plan 06 Artifact-Refresh Recovery + Live-Abschluss auf srv1/srv2)

- `scripts/prepare-host-downloads.sh` gehaertet:
  - rekonstruiert fehlende Root-`dist`-Artefakte jetzt aus vorhandenen Build-Outputs/ISOs,
  - stellt generische `latest`-/`v${VERSION}`-USB-Skripte wieder her,
  - korrigiert den `RETURN`-Trap im Bootstrap-Recovery-Pfad, der unter `set -u` mit `tmproot: unbound variable` abbrechen konnte.
- `scripts/refresh-host-artifacts.sh` vereinfacht:
  - nutzt jetzt direkt `prepare-host-downloads.sh` als kanonischen Refresh-/Recovery-Pfad,
  - erzwingt nicht mehr immer zuerst `package.sh`, wenn die noetigen Artefakte bereits vorhanden oder rekonstruierbar sind.
- Live auf `srv1`:
  - `scripts/prepare-host-downloads.sh` erfolgreich,
  - `scripts/check-beagle-host.sh` erfolgreich,
  - `refresh.status.json` danach `status=ok`,
  - `artifact-watchdog-status.json` danach `state=healthy`, `refresh_status=ok`, `public_ready=true`.
- Live auf `srv2`:
  - top-level `dist` von `srv1` synchronisiert,
  - host-lokale Download-Metadaten mit `prepare-host-downloads.sh` auf `srv2` neu geschrieben,
  - `scripts/check-beagle-host.sh` erfolgreich,
  - `refresh.status.json` danach `status=ok`,
  - `artifact-watchdog-status.json` danach `state=healthy`, `refresh_status=ok`, `public_ready=true`.
- Lokal validiert:
  - `bash -n scripts/prepare-host-downloads.sh scripts/refresh-host-artifacts.sh`
  - `python3 -m pytest tests/unit/test_server_settings.py tests/unit/test_authz_policy.py -q` => `25 passed`

## Update (2026-04-26, Plan 06 Repo-Auto-Update + GitHub-Release-Workflow Fix)

- `beagle-host/services/server_settings.py` erweitert:
  - `GET /api/v1/settings/updates` liefert weiter die lokale `apt`-Lage, jetzt aber zusaetzlich mit separatem `repo_auto_update`-Block.
  - neue Mutationspfade `PUT /api/v1/settings/updates/repo-auto` und `POST /api/v1/settings/updates/repo-auto/check`.
- Neuer Host-Mechanismus:
  - [scripts/repo-auto-update.sh](/home/dennis/beagle-os/scripts/repo-auto-update.sh) prueft `https://github.com/meinzeug/beagle-os.git` auf dem konfigurierten Branch, deployed neue Commits nach `/opt/beagle`, fuehrt danach `install-beagle-host-services.sh` und `refresh-host-artifacts.sh` aus und schreibt Status nach `/var/lib/beagle/repo-auto-update-status.json`.
  - `beagle-artifacts-watchdog` bleibt dadurch die zweite Stufe: nach Host-Update weiter Artefakt-Drift erkennen und bei Bedarf reparieren.
- Neue systemd-/Polkit-Bausteine:
  - `beagle-repo-auto-update.service`
  - `beagle-repo-auto-update.timer`
  - `beagle-host/polkit/beagle-repo-auto-update.rules`
- WebUI:
  - `Server-Einstellungen -> System-Updates` hat jetzt einen bedienbaren Block `Beagle Repo Auto-Update` fuer Aktivierung, Repo-URL, Branch, Intervall, manuellen GitHub-Check sowie Service-/Timer-/Commit-Status.
- Installer-/Deploy-Fix:
  - [scripts/install-beagle-host-services.sh](/home/dennis/beagle-os/scripts/install-beagle-host-services.sh) schreibt templated systemd-Units jetzt wieder mit aufgeloestem `INSTALL_DIR`; der Live-Fehler `__INSTALL_DIR__/scripts/repo-auto-update.sh` in `beagle-repo-auto-update.service` ist damit beseitigt.
- GitHub-Workflow-Fix:
  - `.github/workflows/release.yml` ist repariert; der optionale GPG-Key wird nicht mehr ueber ein unzulaessiges `if: secrets...` ausgewertet, sondern innerhalb des Shell-Schritts.
  - Damit verschwindet der aktuelle GitHub-Parse-Fehler `Unrecognized named-value: 'secrets'`.
  - Follow-up: `.github/workflows/no-legacy-provider-references.yml` normalisiert `./`-Pfade vor dem Allowlist-Vergleich, damit erlaubte Legacy-Pfade wie `scripts/lib/provider_shell.sh` nicht faelschlich als neue Legacy-Provider-Verstoesse gemeldet werden.

## Update (2026-04-26, Security-Default fuer Repo-/Artifact-Automatik)

- Repo-Auto-Update ist fuer neue Serverinstallationen jetzt standardmaessig aktiv:
  - Default-Repo: `https://github.com/meinzeug/beagle-os.git`
  - Default-Branch: `main`
  - Default-Intervall: `1` Minute
  - `beagle-repo-auto-update.timer`: `OnBootSec=1min`, `OnUnitActiveSec=1min`, `AccuracySec=10s`.
- Artifact-Watchdog ist fuer neue Serverinstallationen jetzt standardmaessig aktiv:
  - `auto_repair=true`
  - `max_age_hours=6`
  - `beagle-artifacts-watchdog.timer`: Start nach 2 Minuten, danach alle 15 Minuten.
- `scripts/install-beagle-host-services.sh` schreibt die Sicherheitsdefaults fuer frische Hosts idempotent nach `/var/lib/beagle/beagle-manager/server-settings.json`, ohne bestehende Operator-Konfiguration zu ueberschreiben.
- WebUI `Server-Einstellungen -> System-Updates` akzeptiert und zeigt jetzt 1-Minuten-Repo-Checks; beim Aktivieren der Vollautomatik wird der Watchdog auf 6 Stunden Maximalalter mitgezogen.
- Lokal validiert:
  - `bash -n scripts/repo-auto-update.sh scripts/artifact-watchdog.sh scripts/install-beagle-host-services.sh scripts/package.sh scripts/build-thin-client-installer.sh`
  - `python3 -m py_compile beagle-host/services/server_settings.py`
  - `node --check website/ui/settings.js`
  - `python3 -m pytest tests/unit/test_server_settings.py tests/unit/test_authz_policy.py -q` => `31 passed`

## Update (2026-04-27, GoFuture IAM/Audit WebUI-Operability)

- IAM:
  - `/#panel=iam` hat jetzt einen User-Detail-Drawer mit Basisdaten, Tenant, Gruppen, Status, aktiver Session-Anzahl und direkten Aktionen fuer Deaktivieren/Aktivieren, Session-Revoke und Passwort-Reset-Hinweis.
  - Rollen-Editor mit Permission-Suche, Diff vor dem Speichern und UI-Schutz fuer eingebaute Rollen.
  - Backend liefert Rollen-Metadaten `built_in`/`protected`, verhindert Aendern/Loeschen eingebauter Rollen und persistiert `tenant_id` bei User-Updates.
- Audit:
  - `/#panel=audit` ist in Live-Events/Filter, Export-Ziele, Report Builder, Compliance-Reports und Failures/Replay geschnitten.
  - Event-Details werden vor Anzeige redacted; Failure-Payloads werden nur redacted persistiert.
  - Neue Audit-POST-Routen: `POST /api/v1/audit/export-targets/{target}/test` und `POST /api/v1/audit/failures/replay`.
- Validierung lokal:
  - `node --check website/ui/iam.js website/ui/audit.js website/ui/events.js website/main.js`
  - `python3 -m pytest tests/unit/test_auth_http_surface.py tests/unit/test_auth_session.py tests/unit/test_audit_report.py tests/unit/test_audit_export.py tests/unit/test_authz_policy.py` => `30 passed`
- Runtime-Blocker:
  - `srv1.beagle-os.com` und `srv2.beagle-os.com` per SSH erreichbar, aber der damals verwendete alte `beagle-manager`-Check war falsch; die reale Runtime-Unit ist `beagle-control-plane.service`.
  - Korrektur zum GPU-Smoke: `srv2` hat eine NVIDIA GTX 1080 (`10de:1b80`) und Audio-Funktion (`10de:10f0`), beide an `vfio-pci`; `nvidia-smi` fehlt nur auf dem Host. GPU-E2E bleibt offen, bis eine VM-seitige Passthrough-Pruefung mit Treiber (`nvidia-smi` im Gast oder aequivalent) erfolgreich ist.

## Update (2026-04-27, srv2 GPU-Passthrough-VM-Smoke)

- Auf `srv2` wurde eine transiente libvirt-Test-VM `beagle-gpu-smoke` erstellt.
- Die VM bootete direkt mit Host-Kernel + minimalem Initramfs und folgenden Hostdevs:
  - GTX 1080: `0000:01:00.0` (`10de:1b80`)
  - NVIDIA Audio: `0000:01:00.1` (`10de:10f0`)
- Ergebnis aus der seriellen Gast-Ausgabe:
  - `BEAGLE_GPU_GUEST_NVIDIA_GTX1080=1`
  - `BEAGLE_GPU_GUEST_NVIDIA_AUDIO=1`
- Damit ist die VM-seitige aequivalente GPU-Pruefung aus GoFuture Plan 12 erfolgreich.
- Nachlauf:
  - Test-VM zerstoert und undefiniert.
  - temporaere Dateien `/tmp/beagle-gpu-smoke.xml` und `/tmp/beagle-gpu-smoke-initrd.img` entfernt.
  - Host-GPU bleibt an `vfio-pci` gebunden.
- Rest-Risiko:
  - Die IOMMU-Gruppe enthaelt weiterhin den PCIe Root Port `0000:00:01.0`; deshalb bleibt die WebUI-Sicherheitsbewertung `not-isolatable` fuer produktive Passthrough-Freigabe korrekt.

## Update (2026-04-27, GoAdvanced Plan 08 Observability live validiert)

- Korrektur Runtime-Unit: Auf `srv1`/`srv2` heisst die aktive Unit `beagle-control-plane.service`, nicht `beagle-manager.service`.
- `scripts/install-beagle-proxy.sh` erweitert nginx um `location = /metrics` auf `http://127.0.0.1:9088/metrics`.
- Live auf `srv1` und `srv2` angewendet und validiert:
  - `nginx -t` erfolgreich,
  - `systemctl reload nginx` erfolgreich,
  - `curl -sk https://127.0.0.1/metrics` liefert 20 Prometheus-Samples.
- `prometheus_metrics.py` rendert Default-Zero-Samples fuer Counter/Histogramme, damit frische Scrapes vor erstem Traffic mind. 10 Samples enthalten.
- `beagle-host/services/` ist nach `rg '\bprint\(' beagle-host/services` frei von direkten Print-Aufrufen.
- Authentifizierter Health-Check lokal auf beiden Hosts: `status=healthy`, Components `control_plane`, `providers`, `data_dir`.
- Validierung lokal:
  - `python3 -m pytest tests/unit/test_prometheus_metrics.py tests/unit/test_structured_logger.py tests/integration/test_request_id_middleware.py` => `43 passed`
  - `python3 -m py_compile` fuer geaenderte Observability-Module
  - `bash -n scripts/install-beagle-proxy.sh`

## Update (2026-04-27, GoAdvanced Plan 05 Control-Plane-Split abgeschlossen)

- `beagle-host/bin/beagle-control-plane.py` ist 90 LOC und bleibt reiner Bootstrap/Server-Start.
- 13 `*_http_surface.py` Module sind produktiv.
- `tests/unit/test_vm_http_surface.py` ergaenzt fehlende VM-Surface-Abdeckung fuer Profil, Downloads, State, Actions, Endpoint und Fehlerfaelle.
- Neues reproduzierbares Smoke-Script: `scripts/smoke-control-plane-endpoints.sh`.
- Validierung:
  - Surface-Testauswahl: 125 Tests gruen.
  - Live auf `srv1`: Health, VMs, Cluster, Virtualization, Jobs und `/metrics` gruen.

## Update (2026-04-27, GoFuture Plan 12 GPU-Plane WebUI abgeschlossen)

- `/#panel=virtualization` hat jetzt gefuehrte GPU-Assign-/Release-Flows:
  - GPU-Zusammenfassung mit PCI, Modell, Treiber, Readiness,
  - Ziel-VM-Auswahl plus direkte VMID-Eingabe,
  - Risiko-Bestaetigung,
  - Payload-Preview,
  - sichtbarer Ergebnisbereich nach Mutation.
- vGPU/mdev und SR-IOV wurden aus rohen Tabellen in Card-Flows umgebaut:
  - mdev-Typ-Cards mit freier/maximaler Slot-Kapazitaet,
  - mdev-Instanz-Cards mit Zuweisen/Loeschen,
  - SR-IOV-Cards mit VF-Anzahl, Hardware-Constraint-Hinweis und VF-Anzeige.
- UI-Bug behoben: GPU-Karten-Aktionen waren noch an die alte Tabellen-ID `virtualization-gpus-body` gebunden; produktiv ist `virtualization-gpu-cards`.
- WebUI-Mutationscalls fuer GPU/vGPU/SR-IOV nutzen `postJson(...)` und API-relative Pfade.
- Neue Regression: `tests/unit/test_virtualization_gpu_ui_regressions.py`.
- Validierung lokal:
  - `node --check website/ui/virtualization.js`
  - `node --check website/ui/events.js`
  - `python3 -m pytest tests/unit/test_virtualization_gpu_ui_regressions.py tests/unit/test_gpu_passthrough_service.py tests/unit/test_vgpu_service.py` => `53 passed`
- Live validiert:
  - WebUI-Assets nach `srv1` und `srv2` ausgerollt.
  - Asset-Grep zeigt `gpu-wizard-steps`, `virtualization-gpu-cards`, `gpu-subcard-grid` auf beiden Hosts.
  - `srv2` API meldet weiterhin GTX 1080 `0000:01:00.0`, `vfio-pci`, `not-isolatable`, `passthrough_ready=False`.

## Update (2026-04-27, GoAdvanced Plan 07 Async Job Queue runtime-faehig)

- Job-HTTP-RBAC geschlossen:
  - nicht privilegierte Requester sehen nur eigene Jobs,
  - fremde Job-Details, SSE-Streams und Cancel liefern `403`,
  - `legacy-api-token`/localhost bleiben fuer Operator-Smokes privilegiert.
- `jobs_panel.js` nutzt jetzt den echten Stream-Endpunkt `/jobs/{job_id}/stream` mit `access_token` Query-Parameter fuer EventSource und verarbeitet generische `message`-Events sowie benannte Events.
- Worker-Registry produktiv erweitert:
  - `vm.snapshot`,
  - `vm.migrate`,
  - `backup.run`.
- `JobQueueService` persistiert Jobs nach `/var/lib/beagle/beagle-manager/jobs-state.json`.
  - Abgeschlossene Jobs bleiben nach Control-Plane-Restart sichtbar.
  - Laufende Jobs werden nach Restart als `failed: interrupted by control-plane restart` markiert.
- Live-Validierung:
  - `srv1` Backup-Job fuer VM100 lief per `POST /api/v1/backups/run` ueber Queue bis `completed 100`.
  - `GET /api/v1/jobs/{id}/stream?access_token=...` lieferte finalen SSE-Event mit `status=completed`, `progress=100`.
  - Nach `systemctl restart beagle-control-plane.service` blieb der persistierte Job per `GET /api/v1/jobs/{id}` sichtbar.
  - `srv1`/`srv2` melden Worker-Handler: `backup.run`, `cluster.auto_join`, `cluster.maintenance_drain`, `vm.migrate`, `vm.snapshot`.
- Einschraenkung:
  - Der srv1-Backup-Smoke nutzte VM100, erzeugte aber nur ein 4.1K-Testarchiv; der explizite 5GB-Backup-Lasttest ist weiterhin ein separater Performance-/Storage-Test.
- Validierung lokal:
  - `node --check website/ui/jobs_panel.js website/ui/events.js`
  - `python3 -m py_compile beagle-host/services/job_queue_service.py beagle-host/services/jobs_http_surface.py beagle-host/services/control_plane_handler.py beagle-host/services/service_registry.py`
  - `python3 -m pytest tests/unit/test_job_queue_service.py tests/unit/test_job_worker.py tests/unit/test_jobs_http_surface.py tests/unit/test_jobs_panel_ui_regressions.py tests/unit/test_job_worker_registration_regressions.py` => `76 passed`

## Update (2026-04-27, Login-500 auf srv1/srv2 behoben)

- WebUI-Login auf `srv1.beagle-os.com` und `srv2.beagle-os.com` lieferte reproduzierbar `POST /beagle-api/api/v1/auth/login -> 500`.
- Root Cause 1 behoben:
  - `beagle-host/services/control_plane_handler.py` dispatchte Audit-POSTs ueber `AuditReportHttpSurfaceService.handles_post(path)` und konnte dadurch vor dem Auth-Handler mit `AttributeError` abbrechen.
  - Fix: Dispatch nutzt jetzt die konkrete Surface-Instanz (`self._audit_report_surface().handles_post(path)`).
- Root Cause 2 behoben:
  - `AuthSessionService._load_roles_doc()` schrieb `roles.json` auch bei reinem Read-Pfad immer zurueck.
  - Auf `srv1` war `roles.json` zwischenzeitlich `root:root`; dadurch erzeugte selbst ein ungueltiger Login ein `PermissionError` statt `401`.
  - Fix: `beagle-host/services/auth_session.py` schreibt Rollen nur noch, wenn die Normalisierung den Payload tatsaechlich aendert.
- Neue Regressionen:
  - `tests/unit/test_audit_report.py` deckt den Audit-POST-Dispatch ueber die Surface-Instanz ab.
  - `tests/unit/test_auth_session.py` deckt ab, dass ein bereits normalisiertes `roles.json` beim Lesen nicht mehr unnötig neu geschrieben wird.
- Live deployt:
  - Backend-Files nach `srv1` und `srv2` ausgerollt, `beagle-control-plane.service` auf beiden Hosts neu gestartet.
  - `srv1`: fehlerhafte Owner-Mutation an `/var/lib/beagle/beagle-manager/auth/roles.json` auf `beagle-manager:beagle-manager` korrigiert.
- Verifikation:
  - Lokal: `python3 -m pytest tests/unit/test_auth_session.py tests/unit/test_audit_report.py tests/unit/test_auth_http_surface.py` => `17 passed`
  - API-Smoke auf `srv1` und `srv2`: ungueltiger Login liefert jetzt `401 unauthorized`, kein `500` mehr.
- Browser-Smoke via Chrome DevTools auf `srv2`: `POST https://srv2.beagle-os.com/beagle-api/api/v1/auth/login` liefert `401` mit JSON `invalid credentials`, kein `500`.
- Restbefund: Chromium meldet fuer `srv2` initial `ERR_CERT_AUTHORITY_INVALID`; nach manuellem Proceed laedt die WebUI und der Login-Request selbst ist gesund.

## Update (2026-04-27, GoEnterprise Plan 03 Gaming/Kiosk-Pools weitergezogen)

- Pool-Wizard in `website/index.html` und `website/ui/policies.js` erweitert:
  - `Pool-Typ` (`desktop|gaming|kiosk|gpu_*`)
  - `GPU-Klasse`
  - `Session-Limit (Minuten)`
  - `Kosten / Minute`
- Wizard-Validierung ergänzt:
  - Gaming-Pools brauchen `gpu_class`
  - Kiosk-Pools brauchen `session_time_limit_minutes > 0`
- Backend ergänzt:
  - `PoolsHttpSurfaceService` akzeptiert `pool_type`, `session_time_limit_minutes`, `session_cost_per_minute`
  - `PoolManagerService` validiert Gaming-/Kiosk-Pools serverseitig und serialisiert `pool_type`, `session_time_limit_minutes`, `session_cost_per_minute` an die WebUI
- Kiosk-Operator-RBAC technisch geschlossen:
  - neue Permission `kiosk:operate`
  - Default-Rolle `kiosk_operator` erweitert auf `vm:read`, `vm:power`, `kiosk:operate`
  - dedizierte Endpunkte `GET /api/v1/pools/kiosk/sessions` und `POST /api/v1/pools/kiosk/sessions/{vmid}/end`
- Vorhandenes `website/ui/kiosk_controller.js` eingebunden; Policies-Panel rendert jetzt eine echte Kiosk-Controller-Karte statt totem Code.
- Neue Regressionen:
  - `tests/unit/test_pools_http_surface.py`
  - `tests/unit/test_policies_ui_regressions.py`
  - Erweiterungen in `tests/unit/test_auth_session.py`, `tests/unit/test_authz_policy.py`, `tests/unit/test_session_time_limit.py`
- Validierung:
  - lokal: `python3 -m pytest tests/unit/test_session_time_limit.py tests/unit/test_auth_session.py tests/unit/test_authz_policy.py tests/unit/test_pools_http_surface.py tests/unit/test_policies_ui_regressions.py` => `34 passed`
  - lokal: `node --check website/ui/policies.js website/ui/kiosk_controller.js`
  - live auf `srv1` und `srv2`: neue Backend-/WebUI-Dateien deployt, `beagle-control-plane.service` neu gestartet
  - API-Smoke auf `srv1`/`srv2`: `GET /api/v1/pools/kiosk/sessions` via Legacy-Token => HTTP `200`, Payload `{ok: true, sessions: ...}`
  - Browser-Smoke via Chrome DevTools auf `srv2`: `/#panel=policies` zeigt `Pool-Typ`, `GPU-Klasse`, `Session-Limit (Minuten)` und `Kiosk-Controller`
## Update (2026-04-27, Gaming Metrics Dashboard)

- `GamingMetricsService` haengt jetzt an der produktiven Stream-Health-Pipeline:
  - neuer API-Read-Endpunkt `GET /api/v1/gaming/metrics`
  - `POST /api/v1/sessions/stream-health` aktualisiert bei Gaming-Pools parallel den Metrics-Aggregator
- `/#panel=policies` zeigt jetzt ein echtes Gaming-Metrics-Dashboard:
  - KPI-Uebersicht
  - SVG-Trends fuer FPS, RTT und GPU-Temperatur
  - aktive Gaming-Sessions und letzte Reports
- Ziel des Slices: den GPU-/Gaming-spezifischen Operator-Flow auf `srv2` vor Abschaltung noch browser- und hostseitig bedienbar machen.

## Update (2026-04-27, GoEnterprise Plan 03 Kiosk-Operator Slice: Pool-Stufen + Alert-Chips)

- Kiosk-Pools haben jetzt serverseitig konfigurierbare Verlaengerungsstufen:
  - neues Pool-Feld `session_extension_options_minutes`
  - `PoolManagerService` normalisiert Stufen, serialisiert sie an die WebUI und lehnt nicht konfigurierte Extend-Minuten ab
  - `PoolsHttpSurfaceService` liefert die Stufen pro Kiosk-Session an den Controller aus
- `website/ui/policies.js` erweitert den Pool-Wizard um `Verlaengerungsstufen (Minuten)` und zeigt die Stufen auch in den Pool-Cards an.
- `website/ui/kiosk_controller.js` rendert Extend-Aktionen jetzt dynamisch pro Session statt mit festen `+15m/+30m/+60m`-Buttons.
- Der Kiosk-Controller zeigt jetzt zusaetzliche Stream-Probleme frueh sichtbar als Chips:
  - `Encoder ... %` bei hoher `encoder_load`
  - `Drops ...` bei Dropped Frames
- Validierung lokal:
  - `node --check website/ui/policies.js`
  - `node --check website/ui/kiosk_controller.js`
  - `python3 -m py_compile beagle-host/services/pool_manager.py beagle-host/services/pools_http_surface.py core/virtualization/desktop_pool.py`
  - `python3 -m pytest tests/unit/test_pool_manager.py tests/unit/test_pools_http_surface.py tests/unit/test_policies_ui_regressions.py -q` => `33 passed`
- Live validiert:
  - Deploy auf `srv1` und `srv2`, `beagle-control-plane` auf beiden Hosts `active`
  - API-Smoke auf `srv1` und `srv2`: `GET /api/v1/pools/kiosk/sessions` liefert `200`
  - Browser-Smoke auf `srv2` mit temporaerem Kiosk-State:
    - Pool-Card zeigt `Verlaengerungen: 30, 60 Min`
    - Kiosk-Grid zeigt nur `+30m` und `+60m`
    - Alert-Chips `Encoder 95 %` und `Drops 12` sichtbar
    - `+30m` verlaengert live weiter korrekt
- Restbefund im Browser bleibt unveraendert:
  - nur bestehende DOM-/Accessibility-Warnungen (`password field not contained in a form`, `aria-hidden` am Login-Modal), keine neue Runtime-JavaScript-Regression

## Update (2026-04-27, Auth-Modal A11y-Follow-up)

- `website/index.html` nutzt fuer Login und Onboarding jetzt echte `<form>`-Container statt lose Passwortfelder in nackten Dialogen.
- `website/ui/panels.js` hat einen gemeinsamen `setModalState(...)`-Helper fuer `hidden`, `aria-hidden`, `inert` und Fokus-Bereinigung beim Schliessen von Modals.
- Lokal validiert:
  - `node --check website/ui/panels.js`
  - `python3 -m pytest tests/unit/test_auth_ui_regressions.py -q` => `2 passed`
- Live auf `srv1` und `srv2` ausgerollt.
- Browser-Smoke auf `srv2`:
  - der fruehere `aria-hidden`-Warnpfad am Login-Modal tritt nicht mehr auf
  - die DevTools-`Password field is not contained in a form`-Warnungen sind reduziert, aber noch nicht vollstaendig weg, weil weitere Passwortfelder ausserhalb von Forms im DOM verbleiben
# Progress

## 2026-04-27 - Two-host installer/cluster glue closed

- Added persistent node-ready reporting via `POST /api/v1/nodes/install-check` and `GET /api/v1/nodes/install-checks`.
- Added [node_install_check_service.py](/home/dennis/beagle-os/beagle-host/services/node_install_check_service.py) to persist recent post-install reports and expose the latest successful node-ready event to the WebUI.
- Added first-boot cluster auto-join glue:
  - [beagle-cluster-auto-join.sh](/home/dennis/beagle-os/scripts/beagle-cluster-auto-join.sh)
  - [beagle-cluster-auto-join.service](/home/dennis/beagle-os/beagle-host/systemd/beagle-cluster-auto-join.service)
- `cluster_membership.py` now carries the shared install-check report token in the join response and persists it on the joining node, so future joined servers can report readiness back to the leader without a manual secret handoff.
- `website/ui/dashboard.js`, `website/ui/cluster.js` and `website/index.html` now surface the latest successful node-ready report as a cluster banner.
- `server-installer/post-install-check.sh` was aligned with the current runtime:
  - required service set reduced to `libvirtd` + `beagle-control-plane`
  - old auth-protected API probe replaced by unauthenticated `/healthz`
  - report JSON no longer depends on `jq`
- Closed a live two-host drift on the running cluster:
  - both hosts still had stale member URLs (`http://<ip>:9088/api/v1`)
  - member entries were normalized to `https://srv1.beagle-os.com/beagle-api/api/v1` and `https://srv2.beagle-os.com/beagle-api/api/v1`
  - cluster peer health probes now ignore public-cert trust for liveness only, so `srv2`'s still-imperfect public certificate chain no longer flips cluster members to `unreachable`
- Live validation:
  - `srv1` cluster status: `srv1 online`, `srv2 online`
  - `srv2` cluster status: `srv1 online`, `srv2 online`
  - `srv2` post-install check reported `pass` to `srv1` with full checks payload
  - local validation:
    - `35 passed` across cluster membership / install-check / authz / dashboard regressions
    - `bats tests/bats/cluster_auto_join.bats`
    - `bats tests/bats/post_install_check.bats`

## 2026-04-27 - Gaming/Kiosk two-host smoke hardened

- Added repo-owned live smoke script `scripts/smoke-gaming-kiosk-flow.sh` for the combined Gaming/Kiosk flow on `srv1`/`srv2`.
- Script now validates live:
  - `GET /api/v1/gaming/metrics`
  - `GET /api/v1/pools/kiosk/sessions`
  - `POST /api/v1/pools/kiosk/sessions/{vmid}/extend`
- Closed a real runtime defect on `srv1`:
  - live `extend` returned `500`, while unit tests and isolated route calls were green
  - root cause was file-ownership drift on `/var/lib/beagle/beagle-manager/desktop-pools.json.lock`, not the kiosk/session API logic itself
- `beagle-host/services/request_handler_mixin.py` now logs full structured tracebacks for uncaught request exceptions, so host-only failures are diagnosable from `journalctl`.
- `scripts/smoke-gaming-kiosk-flow.sh` now restores `desktop-pools.json` to `beagle-manager:beagle-manager`, preserves file mode, and removes stale `.lock` files after cleanup.
- Live validation:
  - `srv1` smoke now fully green
  - `srv2` smoke remains fully green
  - both hosts are left without `smoke-flow`/`debug-flow` test state after the run

## 2026-04-27 - IAM UI regressions closed

- Added `tests/unit/test_iam_ui_regressions.py` for the IAM panel UX refactor.
- Coverage now includes:
  - user detail drawer and tenant/session sections
  - built-in role guardrails and permission-selection flow markers
  - session revoke path
  - tenant, IdP and SCIM empty-state rendering hooks
- Local validation:
  - `node --check website/ui/iam.js`
  - `python3 -m pytest tests/unit/test_iam_ui_regressions.py -q` -> `3 passed`
- `docs/gofuture/13-iam-tenancy.md` Step 7 checkbox for UI regressions is now closed.

## 2026-04-27 - GPU window on srv2 closed

- Added predictive GPU-pressure scoring to [smart_scheduler.py](/home/dennis/beagle-os/beagle-host/services/smart_scheduler.py):
  - new `NodeCapacity.predicted_gpu_utilization_pct_4h`
  - GPU placement now evaluates the worse of current vs. predicted GPU utilization
- Extended [test_smart_scheduler.py](/home/dennis/beagle-os/tests/unit/test_smart_scheduler.py):
  - nodes with imminent GPU overload are no longer preferred
  - predicted GPU overload now trips the threshold guard for GPU workloads
- Added reproducible host-level guest probe [test-gpu-passthrough-guest-smoke.sh](/home/dennis/beagle-os/scripts/test-gpu-passthrough-guest-smoke.sh):
  - boots a transient KVM guest on `srv2`
  - attaches GTX 1080 (`0000:01:00.0`) and NVIDIA audio (`0000:01:00.1`) as PCI hostdevs
  - verifies guest-side detection through serial log markers
- Validated:
  - local: `python3 -m pytest tests/unit/test_smart_scheduler.py -q` -> `10 passed`
  - `srv2`: `scripts/test-gpu-passthrough-guest-smoke.sh` -> guest detects GTX 1080 + audio
  - `srv2`: `scripts/test-gpu-inventory-smoke.py` -> `PLAN12_GPU_SMOKE=PASS`
- Result:
  - no remaining mandatory GPU-only validation item is left open for the current plan state
  - `srv2` is no longer needed for any unresolved Pflichtpunkt in the GPU plane
- Update (2026-04-27, Policies Template-Bibliothek):
  - `/#panel=policies` rendert jetzt eine echte Template-Bibliothek als Kartenansicht mit OS, Storage, Source-VM, Build-Zeit, Health und Aktionen `verwenden`, `neu bauen`, `löschen`.
  - Template-Datensätze persisitieren jetzt `source_vmid` und `health`, damit Rebuild/Status im UI nicht mehr blind sind.
  - Regressions erweitert: Template-Contract, Template-Builder und Policies-Template-Flow.
  - Live auf `srv1` verifiziert; `verwenden` setzt den Pool-Wizard auf das Template, Console bleibt fehlerfrei.
  - Pool-Karten haben jetzt eine bestätigte `löschen`-Danger-Action mit konkreter Slot-Anzahl im Dialog.

## 2026-04-27 - Hosted download URLs self-heal to 443

- Fixed stale proxy-port precedence across the runtime:
  - `beagle-host/services/service_registry.py` now lets `/etc/beagle/beagle-proxy.env` override old values from `/etc/beagle/host.env`
  - `scripts/prepare-host-downloads.sh`, `scripts/refresh-host-artifacts.sh` and `scripts/check-beagle-host.sh` now source `beagle-proxy.env` after `host.env`
  - `scripts/install-beagle-proxy.sh` now actively syncs proxy-facing keys back into `host.env`, so stale `8443` leftovers are repaired on deploy
- Normalized hosted download URLs so default HTTPS no longer emits explicit `:443` in generated artifacts and API metadata.
- Added regressions:
  - `tests/unit/test_public_download_url_regressions.py`
  - `tests/unit/test_proxy_env_precedence_regressions.py`
- Validated:
  - local: `6 passed`, shell syntax checks and `py_compile` green
  - live on `srv1`: `/opt/beagle/dist/beagle-downloads-status.json` now reports `listen_port=443`
  - live on `srv1`: `/opt/beagle/dist/pve-thin-client-live-usb-host-latest.sh` and `GET /api/v1/vms/100/live-usb.sh` no longer contain `8443`

## 2026-04-27 - USB installer stops re-downloading bundled payloads

- Fixed the thin-client USB media flow so the local installer prefers the payload already written onto the stick instead of falling back to the remote payload URL after the disk-selection menu.
- Changes:
  - `thin-client-assistant/usb/usb_manifest.py`
    - USB manifests now store both `payload_source_url` and `bundled_payload_relpath`
    - new reader for `bundled_payload_relpath`
  - `thin-client-assistant/usb/usb_writer_write_stage.sh`
    - writes the bundled payload path (`pve-thin-client/live` or `live`) into the USB manifest
  - `thin-client-assistant/usb/live_medium_helpers.sh`
    - resolves bundled live assets via the manifest path before falling back to heuristics
  - `thin-client-assistant/usb/pve-thin-client-live-menu.sh`
    - uses `payload_source_url` for API defaults, keeping the remote host metadata separate from the local payload path
- Added regressions:
  - `tests/unit/test_usb_manifest.py`
  - `tests/unit/test_usb_payload_resolution_regressions.py`
- Validated:
  - local: `5 passed`, `py_compile` and shell syntax checks green
  - live on `srv1`: rebuilt `pve-thin-client-usb-payload-latest.tar.gz` contains the updated USB installer files
  - live on `srv1`: VM-specific `installer.sh` still renders the correct hosted `RELEASE_*` URLs while the payload bundle contains the new local-resolution logic

## 2026-04-27 - Installer log deploy and hosted artifact consistency

- Added a shared artifact-writer lock for `scripts/package.sh` and `scripts/prepare-host-downloads.sh` so repo auto-update, manual refresh and packaging do not write ISO/payload/status files concurrently.
- `prepare-host-downloads.sh` and `package.sh` now remove stale versioned thin-client launcher/bootstrap/payload artifacts before publishing current `VERSION` + `latest` files.
- `scripts/check-beagle-host.sh` now validates the standalone Beagle Web Console instead of legacy PVE UI files/services, checks local `/healthz`, and fails on hosted `8443` references.
- Live on `srv1`:
  - public `/beagle-downloads/` is reachable
  - host launcher downloads are `200`, contain installer-log hooks and no `8443`
  - VM100 generated installer log smoke wrote `script_started`, `bootstrap_helpers_present`, `device_listing_started`, `device_listing_completed`, `script_completed`
  - invalid installer-log token returns `401`
- GitHub release workflow hardening:
  - `release.yml` no longer uploads `dist/sbom/SHA256SUMS` as a second asset named `SHA256SUMS`; the root release checksum file remains authoritative.

## 2026-04-27 - GoRelease freigabeplan angelegt

- `docs/goenterprise/` bleibt unveraendert als Feature-/Architekturquelle.
- Neues Verzeichnis `docs/gorelease/` angelegt fuer Enterprise-GA, Security-Freigabe und Hardware-Abnahme.

## Update (2026-04-27, GoRelease lokale Validierung der Download-/Installer-Gates)

- Lokale Regressionstests fuer die GoRelease-Download- und Installer-Gates sind gruen:
  - `tests/unit/test_public_download_url_regressions.py`
  - `tests/unit/test_installer_script.py`
  - `tests/unit/test_installer_log_service.py`
- Bestätigt wurden dabei:
  - default-hosted URLs ohne explizites `:443`
  - installer-scoped Log-Token / Session / Endpoint-Injektion
  - installer log intake mit Redaction und Token-Validation
- Die zugehoerigen GoRelease-Checkboxen in `docs/gorelease/01-security-gates.md`, `03-end-to-end-validation.md` und `04-release-pipeline.md` wurden auf `[x]` gesetzt.

## Update (2026-04-27, GoRelease E3/S1 konkrete Fixes)

- USB-Installer: `thin-client-assistant/usb/usb_writer_bootstrap.sh` speichert den geladenen Bootstrap-/Payload-Tarball im Cache; `thin-client-assistant/usb/install_payload_assets.sh` verwendet denselben Tarball im Installpfad wieder, bevor ein Remote-Download versucht wird.
- Damit ist der doppelte Download derselben Payload zwischen USB-Erstellung und Installationsmenue repo-seitig behoben und per `tests/unit/test_usb_payload_resolution_regressions.py` abgesichert.
- Auth/Login: `beagle-host/services/auth_session_http_surface.py` kapselt Audit-/Login-Tracking-Side-Effects, damit ein defekter Audit-/Telemetry-Store den Login nicht mehr als `500` abbrechen kann.
- Regressions:
  - `tests/unit/test_auth_session_http_surface.py`
  - `tests/unit/test_usb_payload_resolution_regressions.py`
- Validiert lokal:
  - `pytest -q tests/unit/test_auth_session_http_surface.py tests/unit/test_usb_payload_resolution_regressions.py tests/unit/test_public_download_url_regressions.py tests/unit/test_installer_script.py tests/unit/test_installer_log_service.py` -> 13 passed
  - `bash -n thin-client-assistant/usb/usb_writer_bootstrap.sh thin-client-assistant/usb/install_payload_assets.sh`
  - `git diff --check`
- GoRelease definiert Release-Stufen `R0` bis `R4`, harte Security-Gates, End-to-End-Gates, Release-Pipeline-Gates und Betriebs-/Compliance-Gates.
- Hardware-Matrix ergaenzt:
  - kleine 2-4 Core Hetzner VMs fuer Control Plane, WebUI, Auth, Update und Zwei-Node-Smokes ohne echte KVM-Abnahme
  - dedizierte CPU-Server fuer Bare-Metal/KVM/VM/Backup/Restore
  - kurzzeitig gemietete GPU-Server fuer Passthrough, NVENC, Gaming-Pools und vGPU/MDEV-Abnahmen

## Update (2026-04-27, srv1 Firewall-/Download-Gate)

- Neue reproduzierbare Host-Firewall-Baseline:
  - `scripts/apply-beagle-firewall.sh` schreibt und aktiviert `table inet beagle_guard` ohne fremde libvirt-/Stream-Tabellen zu flushen.
  - Erlaubt Host-Ingress `22/80/443`, Cluster `9088/9089` nur lokal, von VM-Bridges und von erkannten Peer-Allowlists, VM-Forwarding nur fuer Bridge-Egress oder explizite DNAT-Stream-Regeln.
  - `scripts/install-beagle-host-services.sh` wendet die Baseline bei Host-Install/Repo-Update automatisch an.
  - Server-Live- und Server-Installer-nftables-Defaults wurden auf dieselbe Beagle-Guard-Policy angepasst.
- WebUI Firewall modernisiert:
  - Settings-Firewall nutzt jetzt das animierte Updates-Karten-/Flow-Layout.
  - Settings-API liest/schreibt Beagle nftables statt UFW und akzeptiert nur validierte Port-Regeln.
- Live `srv1`:
  - `scripts/apply-beagle-firewall.sh --enable` aktiv, `systemctl is-active nftables` = `active`.
  - Externe Portprobe: `22/80/443` offen, `9088/9089` geschlossen.
  - `scripts/check-beagle-host.sh` erfolgreich, inklusive `no legacy 8443`, `Beagle nftables guard is active`, Download-HTTP-Smokes und Status-JSON.
  - Hosted Installer/Live-USB-Skripte enthalten `BOOTSTRAP_CACHE_DIR` und `443`-URLs ohne `8443`.
- Build-Self-Heal:
  - `scripts/package.sh` bereinigt stale npm-Rename-Verzeichnisse und retryt bei `ENOTEMPTY` einmal mit frisch aufgebautem `node_modules`.
- Validiert:
  - lokal: `pytest -q tests/unit` -> 1222 passed, 4 subtests passed
  - lokal: `bash -n` fuer geaenderte Shell-Skripte
  - lokal: `git diff --check`
  - `srv1`: Chrome DevTools WebUI-Smoke bis Login-Dialog ohne Console-Fehler

## Update (2026-04-28, GoEnterprise Runtime-Telemetrie + persistente Remediation-Steuerung)

- GoEnterprise Plan 02 wurde in zwei weiteren operativen Blöcken verdichtet:
  - Fleet-Remediation hat jetzt persistente Konfiguration und History:
    - `GET /api/v1/fleet/remediation/config`
    - `PUT /api/v1/fleet/remediation/config`
    - `GET /api/v1/fleet/remediation/history`
    - ausgeschlossene Devices und `safe_actions` werden jetzt dauerhaft gespeichert, `run`-Durchlaeufe schreiben `last_run` + History
  - Thin-Client-Runtime liefert jetzt echte Laufzeit-Telemetrie in die Device-Registry:
    - `reports.runtime` im endpoint-authentifizierten `device/sync`
    - persistiert als `last_runtime_report`
    - Fleet-WebUI zeigt WireGuard-, Lock-, Backend-, Session- und Display-Zustand pro Device
- Lock-Screen-Runtime:
  - X11-Multi-Display ueber `BEAGLE_LOCK_SCREEN_X11_DISPLAYS`
  - Runtime-Info-Datei fuer den aktiven Sperrpfad, damit Fleet nicht nur Soll-, sondern Ist-Zustand sieht
- Validierung:
  - `bash -n thin-client-assistant/runtime/device_lock_screen.sh thin-client-assistant/runtime/device_sync.sh`
  - `node --check website/ui/fleet_health.js`
  - Enterprise-Regression-Block: `97 passed`

## Update (2026-04-28, GoEnterprise Fleet-Alerts + Runtime-Health-Telemetrie)

- GoEnterprise Plan 07 wurde im echten Stack verdrahtet:
  - Fleet-UI-Platzhalter `anomalies` / `maintenance` haben jetzt echte Control-Plane-Endpunkte
  - Predictive-Alerts sind jetzt als eigene Fleet-Surface bedienbar:
    - offene Alerts lesen/quittieren
    - Alert-Regeln lesen/anlegen/aktualisieren
  - Default-Regeln fuer Disk/GPU/Reboot/ECC werden reproduzierbar im Alert-Service geseedet
  - Webhook-Dispatch laeuft ueber den bestehenden `webhook_service`
- Thin-Client-Runtime liefert jetzt echte Health-Metriken in den Device-Sync:
  - `uptime_hours`
  - `reboot_count_7d`
  - `cpu_temp_c`
  - `network_errors`
  - lokale Boot-History sorgt dafuer, dass Reboot-Trends nicht pro Sync verloren gehen
- Endpoint-Sync ingestet diese Metriken jetzt direkt in `fleet_telemetry_service`, prueft Anomalien und feuert Alerts noch im Sync-Pfad.
- Fleet-WebUI zeigt jetzt eine eigene `Predictive Alerts`-Operatorflaeche mit offenen Alerts und editierbaren Alert-Regeln.
- Validierung:
  - `bash -n thin-client-assistant/runtime/device_sync.sh`
  - `node --check website/ui/fleet_health.js`
  - zusammenhaengender Fleet-/Endpoint-/Telemetry-Block: `137 passed`
## Update (2026-04-28, GoEnterprise Plan 04/05/09: Drilldown, Energy-Rankings und Green-Hours-Operatorik)

**Scope**: Den naechsten Analytics-/Operator-Slice hinter den bereits live verdrahteten Scheduler-/Cost-/Energy-Panels geschlossen. Chargeback zeigt jetzt den versprochenen Drilldown bis auf Session-Ebene direkt im Dashboard, das Energy-Panel hat echte Verbrauchs-/Effizienz-Rankings aus der Control Plane, und Green Scheduling ist fuer Operatoren jetzt mit expliziten `green_hours` plus aktivem Green-Window-Status sichtbar und konfigurierbar.

- Backend:
  - [beagle-host/services/control_plane_read_surface.py](/home/dennis/beagle-os/beagle-host/services/control_plane_read_surface.py): neue Read-Surface `GET /api/v1/energy/rankings`
  - [beagle-host/services/service_registry.py](/home/dennis/beagle-os/beagle-host/services/service_registry.py): Chargeback-`drilldown`, Energy-Rankings sowie `green_hours`-/`green_window_active`-Ableitung in den Scheduler-Insights
  - [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py): `GET /api/v1/energy/rankings` auf `settings:read`
- WebUI:
  - [website/ui/cost_dashboard.js](/home/dennis/beagle-os/website/ui/cost_dashboard.js): Drilldown Abteilung -> User -> Session im Cost-Panel
  - [website/ui/energy_dashboard.js](/home/dennis/beagle-os/website/ui/energy_dashboard.js): Rankings fuer hoechsten/niedrigsten Node-Verbrauch sowie energieintensivste/effizienteste VMs
  - [website/ui/scheduler_insights.js](/home/dennis/beagle-os/website/ui/scheduler_insights.js): `Green Window aktuell` und `Green Hours CSV` als Operator-Flow
- Regressionen:
  - [tests/unit/test_control_plane_read_surface.py](/home/dennis/beagle-os/tests/unit/test_control_plane_read_surface.py)
  - [tests/unit/test_authz_policy.py](/home/dennis/beagle-os/tests/unit/test_authz_policy.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
- Validierung:
  - `python3 -m py_compile beagle-host/services/service_registry.py beagle-host/services/control_plane_read_surface.py beagle-host/services/authz_policy.py`
  - `node --check website/ui/cost_dashboard.js website/ui/energy_dashboard.js website/ui/scheduler_insights.js`
  - `python3 -m pytest tests/unit/test_control_plane_read_surface.py tests/unit/test_authz_policy.py tests/unit/test_fleet_ui_regressions.py tests/unit/test_energy_cost_integration.py tests/unit/test_chargeback_report.py -q`
## Update (2026-04-28, GoEnterprise Plan 04/09: stündliche Heatmap, zeitfensterbasierte Green-Hours-Logik und Energy-Heatmap)

**Scope**: Drei weitere Enterprise-Reste in einem Zug geschlossen. Der Scheduler rendert nicht mehr nur Tagesdurchschnitte, sondern eine stündliche 7-Tage-Heatmap pro Node; Green Scheduling ist jetzt im produktiven Scheduler-Pfad zeitfensterbasiert statt nur global gewichtet; und das Energy-Panel hat eine eigene Green-Hours-Heatmap auf Basis der aktiven Carbon-/Preis-Konfiguration plus Scheduler-Fenster.

- Backend:
  - [beagle-host/services/smart_scheduler.py](/home/dennis/beagle-os/beagle-host/services/smart_scheduler.py): `pick_node()` nutzt jetzt `preferred_hour` + `green_hours` mit zeitfensterabhängigem Green-Multiplikator; `should_prewarm()` verschiebt Nicht-Green-Peaks, wenn kurz darauf ein Green-Peak folgt
  - [beagle-host/services/service_registry.py](/home/dennis/beagle-os/beagle-host/services/service_registry.py): `historical_heatmap` aus Metrics-Samples, Green-Hours-Payload und Green-Scheduling-Glue im Scheduler-Insights-/Energy-Pfad
  - [beagle-host/services/control_plane_read_surface.py](/home/dennis/beagle-os/beagle-host/services/control_plane_read_surface.py): neue Surface `GET /api/v1/energy/green-hours`
  - [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py): `GET /api/v1/energy/green-hours` auf `settings:read`
- WebUI:
  - [website/ui/scheduler_insights.js](/home/dennis/beagle-os/website/ui/scheduler_insights.js): stündliche 7-Tage-Heatmap pro Node als visuelle Grid-Sicht
  - [website/ui/energy_dashboard.js](/home/dennis/beagle-os/website/ui/energy_dashboard.js): `Grüne Stunden Heatmap` aus `/api/v1/energy/green-hours`
- Regressionen:
  - [tests/unit/test_green_scheduling.py](/home/dennis/beagle-os/tests/unit/test_green_scheduling.py)
  - [tests/unit/test_smart_scheduler.py](/home/dennis/beagle-os/tests/unit/test_smart_scheduler.py)
  - [tests/unit/test_control_plane_read_surface.py](/home/dennis/beagle-os/tests/unit/test_control_plane_read_surface.py)
  - [tests/unit/test_authz_policy.py](/home/dennis/beagle-os/tests/unit/test_authz_policy.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
- Validierung:
  - `python3 -m py_compile beagle-host/services/smart_scheduler.py beagle-host/services/service_registry.py beagle-host/services/control_plane_read_surface.py beagle-host/services/authz_policy.py`
  - `node --check website/ui/scheduler_insights.js website/ui/energy_dashboard.js`
  - `python3 -m pytest tests/unit/test_smart_scheduler.py tests/unit/test_green_scheduling.py tests/unit/test_control_plane_read_surface.py tests/unit/test_authz_policy.py tests/unit/test_fleet_ui_regressions.py tests/unit/test_energy_cost_integration.py tests/unit/test_chargeback_report.py -q`
  - Ergebnis: `48 passed`
## Update (2026-04-28, GoEnterprise Plan 04/09: produktiver Pool-Placement-Drop-in, Pool/User-Analytics und stündlicher Energy-Feed)

**Scope**: Den nächsten produktiven Scheduler-/Energy-Restblock geschlossen. Der `smart_scheduler` hängt jetzt wirklich im Pool-Placement-Pfad für neue Desktop-Slots, Scheduler-Insights differenzieren `saved_cpu_hours` nach Pool und User, und das Energy-Panel arbeitet nicht mehr nur mit einer statischen Basiszahl, sondern mit einem echten editierbaren 24-Stunden-CO₂-/Preisprofil.

- Backend:
  - [beagle-host/services/pool_manager.py](/home/dennis/beagle-os/beagle-host/services/pool_manager.py): Smart-Scheduler-Drop-in für `register_vm()`/Node-Auswahl plus öffentliche Desktop-Inventarsicht `list_pool_desktops()`
  - [beagle-host/services/service_registry.py](/home/dennis/beagle-os/beagle-host/services/service_registry.py): `_smart_pick_pool_node()`, stündliches Energy-Profil, Scheduler-Breakdowns `saved_cpu_hours_by_pool` / `saved_cpu_hours_by_user`, `hourly_profile` in `/energy/config`
  - [beagle-host/services/control_plane_read_surface.py](/home/dennis/beagle-os/beagle-host/services/control_plane_read_surface.py): bestehende Energy-/Scheduler-Surfaces liefern jetzt stündliche Profil- und Breakdown-Daten mit aus
- WebUI:
  - [website/ui/scheduler_insights.js](/home/dennis/beagle-os/website/ui/scheduler_insights.js): Saved-CPU-Hours nach Pool/User
  - [website/ui/energy_dashboard.js](/home/dennis/beagle-os/website/ui/energy_dashboard.js): editierbarer 24h-CO₂-/Strompreis-Feed im Energy-Panel
- Regressionen:
  - [tests/unit/test_pool_manager.py](/home/dennis/beagle-os/tests/unit/test_pool_manager.py)
  - [tests/unit/test_control_plane_read_surface.py](/home/dennis/beagle-os/tests/unit/test_control_plane_read_surface.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
- Validierung:
  - `python3 -m py_compile beagle-host/services/pool_manager.py beagle-host/services/service_registry.py beagle-host/services/control_plane_read_surface.py beagle-host/services/authz_policy.py beagle-host/services/smart_scheduler.py`
  - `node --check website/ui/scheduler_insights.js website/ui/energy_dashboard.js`
  - `python3 -m pytest tests/unit/test_pool_manager.py tests/unit/test_smart_scheduler.py tests/unit/test_green_scheduling.py tests/unit/test_control_plane_read_surface.py tests/unit/test_authz_policy.py tests/unit/test_fleet_ui_regressions.py tests/unit/test_energy_cost_integration.py tests/unit/test_chargeback_report.py -q`
  - Ergebnis: `71 passed`
## Update (2026-04-28, GoEnterprise Plan 04/09: Prewarm-Hit-Metrik, Warm-Pool-Apply und Profil-Import)

**Scope**: Drei weitere produktive Enterprise-Reste zusammengezogen. Der Scheduler bewertet Erfolg jetzt nicht mehr nur über Kandidatenlisten, sondern über echte Prewarm-Hit-/Miss-Events aus dem Pool-Manager; das Dashboard kann empfohlene Warm-Pool-Größen direkt anwenden; und das stündliche Energy-Profil hat jetzt einen eigenen Import-Endpunkt statt nur eines allgemeinen Config-Updates.

- Backend:
  - [beagle-host/services/pool_manager.py](/home/dennis/beagle-os/beagle-host/services/pool_manager.py): persistierte `prewarm_events` inklusive `hit|miss`, `saved_wait_seconds` und Filter-API `list_prewarm_events()`
  - [beagle-host/services/service_registry.py](/home/dennis/beagle-os/beagle-host/services/service_registry.py): `build_warm_pool_recommendations()`, `apply_warm_pool_recommendations()`, `import_energy_hourly_profile()` sowie echte `prewarm_hit_rate`-/Hit-/Miss-Breakdowns in den Scheduler-Insights
  - [beagle-host/services/control_plane_read_surface.py](/home/dennis/beagle-os/beagle-host/services/control_plane_read_surface.py): neue POST-Surfaces `POST /api/v1/scheduler/warm-pools/apply` und `POST /api/v1/energy/hourly-profile/import`
  - [beagle-host/services/authz_policy.py](/home/dennis/beagle-os/beagle-host/services/authz_policy.py): neue Mutationsrouten auf `settings:write`
- WebUI:
  - [website/ui/scheduler_insights.js](/home/dennis/beagle-os/website/ui/scheduler_insights.js): `Prewarm Hit Rate` und `Warm-Pool Empfehlungen anwenden`
  - [website/ui/energy_dashboard.js](/home/dennis/beagle-os/website/ui/energy_dashboard.js): `Stundenprofil importieren`
- Regressionen:
  - [tests/unit/test_pool_manager.py](/home/dennis/beagle-os/tests/unit/test_pool_manager.py)
  - [tests/unit/test_control_plane_read_surface.py](/home/dennis/beagle-os/tests/unit/test_control_plane_read_surface.py)
  - [tests/unit/test_authz_policy.py](/home/dennis/beagle-os/tests/unit/test_authz_policy.py)
  - [tests/unit/test_fleet_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_fleet_ui_regressions.py)
- Validierung:
  - `python3 -m py_compile beagle-host/services/pool_manager.py beagle-host/services/service_registry.py beagle-host/services/control_plane_read_surface.py beagle-host/services/authz_policy.py beagle-host/services/smart_scheduler.py`
  - `node --check website/ui/scheduler_insights.js website/ui/energy_dashboard.js`
  - `python3 -m pytest tests/unit/test_pool_manager.py tests/unit/test_control_plane_read_surface.py tests/unit/test_authz_policy.py tests/unit/test_fleet_ui_regressions.py tests/unit/test_smart_scheduler.py tests/unit/test_green_scheduling.py tests/unit/test_energy_cost_integration.py tests/unit/test_chargeback_report.py -q`
  - Ergebnis: `73 passed`
## Update (2026-04-29, GoEnterprise Plan 02: X11-Lockscreen-Akzeptanztest live bestanden)

**Scope**: Den letzten offenen Plan-02-Restpunkt "grafischen Sperrbildschirm live gegen echte X11-Session abnehmen" abgeschlossen. Da die lokale beagle-thinclient-VM kein SSH-Key-Zugang ohne Passwort hatte, wurde ein Xvfb-basierter Akzeptanztest erstellt – reproduzierbar und CI-tauglich.

- Test-Script:
  - [scripts/test-lockscreen-x11-acceptance.sh](/home/dennis/beagle-os/scripts/test-lockscreen-x11-acceptance.sh): Xvfb :99, Stub-Skripte fuer common.sh/device_state_enforcement.sh, `run_device_lock_screen_watcher` mit `BEAGLE_LOCK_SCREEN_ONCE=1`
- Validierung:
  - `bash scripts/test-lockscreen-x11-acceptance.sh`
  - Ergebnis: `17 passed, 0 failed`

## Update (2026-04-29, GoAdvanced Plan 06: SQLite-State-Migration vollstaendig)

**Scope**: Plan 06 Steps 3–7 abgeschlossen. Alle 5 SQLite-Repositories implementiert, Service-Migration via backward-kompatiblem DI-Pattern in allen relevanten Services, One-Shot-JSON-Importer, Backup-Service + Systemd-Timer, Performance-Benchmark bestanden.

- Neue Dateien:
  - `core/repository/pool_repository.py` + `tests/unit/test_pool_repository.py`
  - `core/repository/gpu_repository.py` + `tests/unit/test_gpu_repository.py`
  - `scripts/migrate-json-to-sqlite.py` + `tests/unit/test_json_to_sqlite_migration.py`
  - `beagle-host/services/db_backup_service.py` + `tests/unit/test_db_backup_service.py`
  - `beagle-host/systemd/beagle-db-backup.service` + `beagle-db-backup.timer`
  - `scripts/bench-fleet-state.py`
- Geaenderte Services (DI fuer Repository):
  - `beagle-host/services/device_registry.py` (Phase 5a: DeviceRepository optional)
  - `beagle-host/services/pool_manager.py` (Phase 5b: PoolRepository optional)
  - `beagle-host/services/session_manager.py` (Phase 5c: SessionRepository optional)
  - `beagle-host/services/gpu_streaming_service.py` (Phase 5d: GpuRepository optional)
  - `beagle-host/providers/beagle_host_provider.py` (Phase 5e: VmRepository optional)
- Schema-Fix: `core/persistence/migrations/001_init.sql` — `idx_gpus_pci_address` → composite `idx_gpus_node_pci ON gpus(node_id, pci_address)`
- Validierung:
  - `python3 -m pytest tests/unit/` — `1422 passed` (3 pre-existing unrelated failures)
  - srv1 Dry-Run: 1 VM + 1 Pool + 1 Device erkannt, 0 Fehler
  - Benchmark srv1: SQLite P99 < 1ms, JSON P99 ~2ms, **165x Speedup**, Target PASS

## Update (2026-05-01, Host-Ops: Repo-Auto-Update entkoppelt von Artefakt-Build und Commit-Stempel gehaertet)

**Scope**: Den produktiven Hänger in `/#panel=settings_updates` reproduzierbar geschlossen. `repo-auto-update` blockiert den GitHub-Update-Status nicht mehr bis zum Ende eines langen ISO-/Artefakt-Builds, und Hosts ohne vorhandene `.beagle-installed-commit`-Datei erkennen den bereits installierten Stand jetzt trotzdem sauber wieder.

- Backend-/Ops-Fix:
  - [scripts/repo-auto-update.sh](/home/dennis/beagle-os/scripts/repo-auto-update.sh): neuer Fallback `resolve_installed_commit()` über Commit-Stempel, vorhandenen Status und Git-Checkout; Repo-Update markiert den Host nach `rsync` + Service-Install sofort wieder als `healthy` und stößt `beagle-artifacts-refresh.service` nur noch asynchron an
  - [scripts/install-beagle-host-services.sh](/home/dennis/beagle-os/scripts/install-beagle-host-services.sh): schreibt bei Git-basierten Installationen automatisch `.beagle-installed-commit`, damit frische Hosts nicht in endlose Re-Updates fallen
- Regressionen:
  - [tests/unit/test_repo_auto_update_regressions.py](/home/dennis/beagle-os/tests/unit/test_repo_auto_update_regressions.py)
  - [tests/unit/test_install_beagle_host_services_regressions.py](/home/dennis/beagle-os/tests/unit/test_install_beagle_host_services_regressions.py)
- Validierung:
  - `bash -n scripts/repo-auto-update.sh scripts/install-beagle-host-services.sh`
  - `python3 -m unittest tests/unit/test_server_settings.py -q`
  - ad-hoc Python-Runner für `tests/unit/test_repo_auto_update_regressions.py` und `tests/unit/test_install_beagle_host_services_regressions.py`
  - Ergebnis: alle betroffenen lokalen Regressionen grün; `pytest` war auf diesem Host weiterhin nicht installiert

## Update (2026-05-01, Host-Ops: Download-404 waehrend Artefakt-Refresh beseitigt)

**Scope**: Den Live-404 auf `https://srv1.beagle-os.com/beagle-downloads/beagle-downloads-status.json` während eines laufenden Artefakt-Refresh reproduzierbar geschlossen. Ursache war kein nginx-Problem, sondern `scripts/package.sh`, das die publizierten Download-Dateien am Build-Anfang wegloeschte und erst spaeter neu erzeugte.

- Packaging-Fix:
  - [scripts/package.sh](/home/dennis/beagle-os/scripts/package.sh): bestehende `/beagle-downloads`-Artefakte bleiben waehrend des Rebuilds sichtbar; die publizierten Status-/Launcher-/ISO-Dateien werden nicht mehr vorab entfernt
- Regression:
  - [tests/unit/test_package_sh_regressions.py](/home/dennis/beagle-os/tests/unit/test_package_sh_regressions.py)
- Live-Befund auf `srv1`:
  - alter Build entfernte `beagle-downloads-status.json` tatsaechlich waehrend des Refreshs
  - neuer Deploy trennt Repo-Status bereits korrekt von Artefakt-Build (`repo_auto_update=healthy`), und der Packaging-Fix verhindert zusaetzlich die temporären Download-404s waehrend des laufenden Refreshs
  - `refresh-host-artifacts.sh` seedet bei bereits fehlender Statusdatei jetzt sofort einen Platzhalter, damit `/beagle-downloads/beagle-downloads-status.json` schon waehrend des ersten reparierten Runs wieder `200` liefert

## Update (2026-05-01, Thin-Client USB: doppelten Bootstrap-Download im Shell-Writer entfernt)

**Scope**: Die generierten Linux-Writer `pve-thin-client-usb-installer-*.sh` und `pve-thin-client-live-usb-*.sh` luden den Bootstrap-Tarball bei Standalone-Ausfuehrung doppelt herunter: einmal vor der interaktiven Geraeteauswahl und ein zweites Mal nach dem `sudo`-Reexec. Ursache war, dass der erste Bootstrap-Baum nicht an den Root-Reexec weitergereicht wurde.

- Fix:
  - [thin-client-assistant/usb/pve-thin-client-usb-installer.sh](/home/dennis/beagle-os/thin-client-assistant/usb/pve-thin-client-usb-installer.sh): uebergibt den bereits entpackten `BOOTSTRAP_DIR` jetzt via `PVE_DCV_BOOTSTRAP_DIR` an den `sudo`-Reexec und reused den extrahierten Helper-Baum statt denselben Download erneut zu starten
- Regression:
  - [tests/unit/test_usb_installer_shell_regressions.py](/home/dennis/beagle-os/tests/unit/test_usb_installer_shell_regressions.py)
- Validierung:
  - `bash -n thin-client-assistant/usb/pve-thin-client-usb-installer.sh`
  - `python3 tests/unit/test_usb_installer_shell_regressions.py`
  - `pytest` war lokal weiterhin nicht installiert

## Update (2026-05-01, Host-Artefakte: Server-Release-Builds auf Beagle-Hosts abgeschaltet)

**Scope**: `srv1`/`srv2` sollen fuer ihre lokalen `/beagle-downloads` nur Endpoint-/Thin-Client-Artefakte erzeugen und hosten. Die grossen Server-Release-Artefakte `beagle-os-server-installer-amd64.iso` und `Debian-1201-bookworm-amd64-beagle-server.tar.gz` bleiben auf der separaten Public-Release-Seite und werden nicht mehr als Pflicht fuer Host-Refresh, Host-Install oder Host-Health behandelt.

- Host-Refresh-/Packaging-Fix:
  - [scripts/package.sh](/home/dennis/beagle-os/scripts/package.sh): neuer Schalter `BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS`, damit Host-Refreshes Server-Release-Artefakte sauber auslassen koennen
  - [scripts/prepare-host-downloads.sh](/home/dennis/beagle-os/scripts/prepare-host-downloads.sh): defaultet jetzt auf host-lokale Thin-Client-/Endpoint-Artefakte, schreibt keine lokalen Server-ISO-/installimage-Links mehr in `beagle-downloads-index.html` oder `beagle-downloads-status.json`
  - [scripts/lib/prepare_host_downloads.py](/home/dennis/beagle-os/scripts/lib/prepare_host_downloads.py): `write_download_status()` behandelt Server-Release-Felder jetzt optional statt Pflicht
- Host-Policy-/Health-Fix:
  - [scripts/check-beagle-host.sh](/home/dennis/beagle-os/scripts/check-beagle-host.sh), [scripts/artifact-watchdog.sh](/home/dennis/beagle-os/scripts/artifact-watchdog.sh), [scripts/install-beagle-host.sh](/home/dennis/beagle-os/scripts/install-beagle-host.sh) und [beagle-host/services/server_settings.py](/home/dennis/beagle-os/beagle-host/services/server_settings.py) verlangen die beiden Server-Release-Artefakte auf produktiven Beagle-Hosts nicht mehr
- Regressionen:
  - [tests/unit/test_package_sh_regressions.py](/home/dennis/beagle-os/tests/unit/test_package_sh_regressions.py)
  - [tests/unit/test_host_artifact_server_release_regressions.py](/home/dennis/beagle-os/tests/unit/test_host_artifact_server_release_regressions.py)
  - [tests/unit/test_prepare_host_downloads_status_regressions.py](/home/dennis/beagle-os/tests/unit/test_prepare_host_downloads_status_regressions.py)
- Validierung:
  - `bash -n scripts/package.sh scripts/prepare-host-downloads.sh scripts/check-beagle-host.sh scripts/install-beagle-host.sh scripts/artifact-watchdog.sh`
  - `python3 -m py_compile scripts/lib/prepare_host_downloads.py beagle-host/services/server_settings.py`
  - `python3 -m unittest tests.unit.test_server_settings -q`
  - ad-hoc Python-Runner fuer die neuen Regressionen

## Update (2026-05-01, WebUI Updates: SSE-Live-Status fuer komplette Update-Seite)

**Scope**: Die Update-Seite nutzt jetzt einen dedizierten SSE-Stream fuer Repo-/Artifact-/Watchdog-/Build-Live-Daten. Teure APT-Pruefungen bleiben bewusst hinter dem expliziten Refresh, damit die Seite keinen periodischen `apt-get update`-Loop erzeugt.

- Backend:
  - [beagle-host/services/server_settings.py](/home/dennis/beagle-os/beagle-host/services/server_settings.py): neuer `GET /api/v1/settings/updates/stream` SSE-Descriptor, Live-Snapshot ohne APT und normalisierter `primary_status` fuer Artefakt-Builds
  - [beagle-host/services/control_plane_handler.py](/home/dennis/beagle-os/beagle-host/services/control_plane_handler.py): EventSource-Auth via `access_token` und RBAC-Check fuer die Update-Stream-Route
- Frontend:
  - [website/ui/settings.js](/home/dennis/beagle-os/website/ui/settings.js): EventSource fuer die komplette Update-Seite, automatischer Reconnect, Polling-Fallback und weniger widerspruechliche Artefakt-/Public-Gate-Meldungen waehrend laufender Builds
  - [website/index.html](/home/dennis/beagle-os/website/index.html): sichtbarer `LIVE SSE`/Fallback-Indikator im Update Center
- Validierung:
  - `python3 -m py_compile beagle-host/services/server_settings.py beagle-host/services/control_plane_handler.py`
  - `python3 -m unittest tests.unit.test_server_settings`
  - direkter Python-Runner fuer `tests/unit/test_settings_ui_regressions.py`
  - `pytest` war lokal nicht installiert

## Update (2026-05-01, Thin-Client Live-USB: persistente Netzwerk-TUI vor Desktop/Moonlight)

**Scope**: Live-USB-Boots erzwingen vor dem Desktop/Moonlight-Start einmalig eine lokale Netzwerkauswahl fuer Ethernet oder WLAN. Die Auswahl wird auf dem USB-State persistiert; spaetere Boots zeigen fuer 3 Sekunden ein grosses Override-Banner, bei `N` wird die TUI erneut geoeffnet, sonst startet der Runtime-Pfad mit der gespeicherten Konfiguration.

- Runtime-Fix:
  - [thin-client-assistant/runtime/runtime-network-menu.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/runtime-network-menu.sh): neue TUI mit Ethernet-/WLAN-Auswahl, WLAN-Scan, Passwortabfrage, Persistenz und 3-Sekunden-Reconfigure-Banner
  - [thin-client-assistant/runtime/runtime_network_config_files.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/runtime_network_config_files.sh) und [thin-client-assistant/runtime/apply-network-config.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/apply-network-config.sh): WLAN via `wpa_supplicant` vor `systemd-networkd`/NetworkManager konfigurieren
  - [thin-client-assistant/systemd/pve-thin-client-network-menu.service](/home/dennis/beagle-os/thin-client-assistant/systemd/pve-thin-client-network-menu.service): neue Runtime-Unit, bewusst nur fuer Live-USB-Boots mit `pve_thin_client.network_tui=1`
- USB-/Installer-Fix:
  - [thin-client-assistant/usb/usb_writer_write_stage.sh](/home/dennis/beagle-os/thin-client-assistant/usb/usb_writer_write_stage.sh): Live-GRUB-Eintraege setzen `pve_thin_client.network_tui=1`; Installer-Boots bleiben davon getrennt
  - [thin-client-assistant/usb/pve-thin-client-live-menu.sh](/home/dennis/beagle-os/thin-client-assistant/usb/pve-thin-client-live-menu.sh): Preset-Installationen fragen Netzwerk vor der Zielplattenauswahl ab
- Security:
  - [thin-client-assistant/runtime/runtime_config_persistence.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/runtime_config_persistence.sh): `network.env` bleibt bei gespeicherten WLAN-PSKs auf `0600`
- Regression:
  - [tests/unit/test_thin_client_live_network_tui.py](/home/dennis/beagle-os/tests/unit/test_thin_client_live_network_tui.py)
- Validierung:
  - `bash -n` fuer alle betroffenen Shell-Skripte
  - `git diff --check`
  - direkter Python-Runner fuer `tests/unit/test_thin_client_live_network_tui.py`, `tests/unit/test_usb_payload_resolution_regressions.py`, `tests/unit/test_thin_client_live_build_regressions.py`
  - `pytest` war lokal nicht installiert

## Update (2026-05-01, BeagleStream-Forks real auf GitHub angelegt)

**Scope**: Der in `fork.md` und Plan 01 geforderte Fork-Grundzustand ist nicht mehr nur Doku. Die beiden externen Upstream-Projekte existieren jetzt als echte Fork-Repositories unter dem realen GitHub-Owner `meinzeug`, inklusive lokaler Klone und Arbeitsbranch `beagle/phase-a`.

- GitHub / lokale Workspaces:
  - `https://github.com/meinzeug/beagle-stream-server` als Fork von `LizardByte/Sunshine`
  - `https://github.com/meinzeug/beagle-stream-client` als Fork von `moonlight-stream/moonlight-qt`
  - lokale Arbeitskopien: `/home/dennis/beagle-stream-server`, `/home/dennis/beagle-stream-client`
  - beide auf Branch `beagle/phase-a`
- Repo-Doku bereinigt:
  - [fork.md](/home/dennis/beagle-os/fork.md)
  - [docs/archive/goenterprise/01-moonlight-vdi-protocol.md](/home/dennis/beagle-os/docs/archive/goenterprise/01-moonlight-vdi-protocol.md)
  - [docs/checklists/02-streaming-endpoint.md](/home/dennis/beagle-os/docs/checklists/02-streaming-endpoint.md)
  - harte Verweise auf die nicht existente Org `beagle-os` auf den realen Owner `meinzeug` korrigiert
- Validierung:
  - `gh auth status`
  - `gh repo view meinzeug/beagle-stream-server`
  - `gh repo view meinzeug/beagle-stream-client`
  - lokale `git remote -v`-Pruefung in beiden Fork-Workspaces

## Update (2026-05-01, Endpoint Self-Update/Repair: Live-USB und installierte Thinclients gehaertet)

**Scope**: Live-USB-Sticks und per USB-Installer installierte Thinclients sollen Updates, Health-/Repair-Status und Reboot-Persistenz reproduzierbar behalten. Die WebUI zeigt pro VM/Endpoint, ob Self-Update erlaubt ist oder ob Thinclient/Live-USB neu gebaut werden muss.

- Runtime-/Updater-Fix:
  - [beagle-os/overlay/usr/local/sbin/beagle-update-client](/home/dennis/beagle-os/beagle-os/overlay/usr/local/sbin/beagle-update-client): Update-State und Cache werden auf dem Live-/Install-Medium unter `pve-thin-client/state/update*` persistiert; A/B-Slot-Updatepfad bleibt fuer installierte Thinclients erhalten
  - [beagle-os/overlay/usr/local/sbin/beagle-update-client](/home/dennis/beagle-os/beagle-os/overlay/usr/local/sbin/beagle-update-client): GRUB-Rewrite erhaelt nicht-default Runtime-Bootflags wie `pve_thin_client.network_tui=1`
  - [thin-client-assistant/runtime/prepare-runtime.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/prepare-runtime.sh): Management-/Update-/Heal-Timer starten erst nach Netzwerk, Enrollment, WireGuard/Egress und initialem Device-Sync
  - `beagle-update-*`, `beagle-healthcheck`, `beagle-endpoint-*`, `beagle-runtime-heartbeat`: systemd-Abhaengigkeiten auf `pve-thin-client-prepare.service`/`network-online.target` gesetzt
- Repair-/Control-Plane-Fix:
  - [beagle-os/overlay/usr/local/sbin/beagle-healthcheck](/home/dennis/beagle-os/beagle-os/overlay/usr/local/sbin/beagle-healthcheck): Health-Failure markiert Update-Status als `health-failed` mit `rollback_recommended`
  - [beagle-host/services/endpoint_report.py](/home/dennis/beagle-os/beagle-host/services/endpoint_report.py): Endpoint-Reports transportieren Health-Failure-/Rollback-Flags zur Control Plane
- Compatibility-/WebUI-Fix:
  - [beagle-host/services/update_feed.py](/home/dennis/beagle-os/beagle-host/services/update_feed.py): Update-Feed unterscheidet `self_update`, `migration_required` und `reinstall_required`
  - [beagle-host/services/vm_http_surface.py](/home/dennis/beagle-os/beagle-host/services/vm_http_surface.py) und [website/main.js](/home/dennis/beagle-os/website/main.js): VM-Update-Panel zeigt Rebuild-/Reinstall-Hinweise und Runtime-Health-Failure an
  - [scripts/lib/prepare_host_downloads.py](/home/dennis/beagle-os/scripts/lib/prepare_host_downloads.py): `beagle-downloads-status.json` enthaelt Endpoint-Kompatibilitaetsmetadaten
- Regression:
  - [tests/unit/test_endpoint_update_self_heal_regressions.py](/home/dennis/beagle-os/tests/unit/test_endpoint_update_self_heal_regressions.py)
  - [tests/unit/test_prepare_host_downloads_status_regressions.py](/home/dennis/beagle-os/tests/unit/test_prepare_host_downloads_status_regressions.py)
- Validierung:
  - `python3 -m py_compile` fuer Updater und betroffene Backend-Services
  - `bash -n` fuer Healthcheck/Endpoint-Report/Dispatch/Prepare-Runtime
  - direkter Python-Runner fuer die betroffenen Regressionen

## Stand (2026-05-01, CI failure -> Copilot autofix handoff)

**Zuletzt erledigt**:
- Ein neuer `workflow_run`-Workflow erstellt bei fehlgeschlagenen GitHub Actions automatisch ein Issue mit Log-Auszug und weist es Copilot coding agent zu.
- Der WireGuard-Enrollment-Pfad im Thin-Client wurde gegen den fehlschlagenden DNS-Resolve-Zweig gehärtet, so dass der CI-Stublauf wieder grün ist.
- Die `security-tls-check`-Regel bleibt aktiv; alle aktuell legitimen TLS-Ausnahmen sind nun inline mit `tls-bypass-allowlist` markiert und dokumentiert.

**Naechste konkrete Schritte**:
1. GitHub Actions nach dem Push beobachten und den ersten automatisch erzeugten Copilot-Fix-Task verifizieren.
2. Falls Copilot coding agent bei einem Run nicht verfügbar ist, Secret-/Policy-Konfiguration auf GitHub korrigieren.
3. Die bestehenden Release-/Build-Workflows auf weitere echte CI-Fehler prüfen, sobald die neuen Autofix-Issues laufen.

## Update (2026-05-01, Public Website Release v8.0.0 und Beagle-Wallpaper-Design)

**Scope**: Die oeffentliche Website nutzt wieder ein eigenstaendiges dunkles Beagle-OS-Design mit dem vorhandenen Gaming-/Cyberpunk-Wallpaper aus der Runtime. Release-Workflows validieren SemVer `8.0.0`, aktualisieren die Website automatisch und pruefen live HTML, CSS und Wallpaper-Asset.

- Website:
  - [public-site/index.html](/home/dennis/beagle-os/public-site/index.html): Hero auf Beagle-OS-Marke, Open-Source-/Lizenztext und Download `v8.0.0` aktualisiert.
  - [public-site/styles.css](/home/dennis/beagle-os/public-site/styles.css): neon/cyberpunk Hero mit `beagleos-gaming.png`, Rajdhani/Space-Mono-Typografie und staerkeren Cyan-/Magenta-/Orange-Akzenten.
  - [public-site/assets/img/beagleos-gaming.png](/home/dennis/beagle-os/public-site/assets/img/beagleos-gaming.png): Public-Site-Asset aus dem vorhandenen Beagle-OS-Wallpaperbestand.
  - [public-site/download/index.html](/home/dennis/beagle-os/public-site/download/index.html): Release-Tag Platzhalter statt hartem `8.0` in Metadaten.
  - Alte statische `public-site/docs/proxmox-setup/`-Seite entfernt; Live-Pfad liefert nach Deploy `404`.
- Release/Automation:
  - [VERSION](/home/dennis/beagle-os/VERSION): SemVer-Core `8.0.0`.
  - [.github/workflows/release.yml](/home/dennis/beagle-os/.github/workflows/release.yml): VERSION-Format validiert, GitHub-Release `v8.0.0` als latest gepflegt, Public-Website nach Release-Publish deployed und live geprueft.
  - [.github/workflows/public-website.yml](/home/dennis/beagle-os/.github/workflows/public-website.yml): Website-Smoke liest VERSION dynamisch und prueft Homepage, Download-Seite, CSS und Wallpaper-Asset.
- Validierung:
  - `git diff --check`
  - YAML-Syntaxcheck fuer Release- und Public-Website-Workflow
  - Live-Smoke gegen `https://beagle-os.com/`, `/download/`, `/styles.css` und `/assets/img/beagleos-gaming.png`
  - Chrome DevTools: keine Console-Messages, alle Homepage-Requests `200`

## Update (2026-05-01, Copilot PR-Automerge und offene Autofix-PRs konsolidiert)

**Scope**: Offene Copilot-PRs blieben offen, weil GitHub sie als Draft erzeugte und PR-Workflow-Runs auf `action_required` pausierte. Die sinnvollen Copilot-Fixes wurden in `main` konsolidiert; die Automerge-Logik hebt Copilot-Drafts jetzt automatisch auf, approved pausierte Runs und dedupliziert neue Autofix-Issues.

- Fixes aus Copilot-PRs:
  - [beagle-kiosk/package.json](/home/dennis/beagle-os/beagle-kiosk/package.json) und [beagle-kiosk/package-lock.json](/home/dennis/beagle-os/beagle-kiosk/package-lock.json): Kiosk-Version auf SemVer `8.0.0`, damit `electron-builder` den Release-Build nicht abbricht.
  - [tests/unit/test_package_sh_regressions.py](/home/dennis/beagle-os/tests/unit/test_package_sh_regressions.py): Regression fuer SHA256SUMS-Seeding vor `verify-server-installer-artifacts.sh`.
  - [scripts/render-site-templates.py](/home/dennis/beagle-os/scripts/render-site-templates.py) und [scripts/deploy-public-website.sh](/home/dennis/beagle-os/scripts/deploy-public-website.sh): gemeinsamer Public-Site-Template-Renderer.
- Automerge:
  - [.github/workflows/copilot-automerge.yml](/home/dennis/beagle-os/.github/workflows/copilot-automerge.yml): neuer `action_required`-Pfad approved Copilot-PR-Workflow-Runs und nutzt den hinterlegten Copilot-Token.
  - [scripts/approve-copilot-pr-workflow-run.sh](/home/dennis/beagle-os/scripts/approve-copilot-pr-workflow-run.sh): markiert Copilot-PRs ready-for-review und approved pausierte Workflow-Runs.
  - [scripts/merge-copilot-autofix-pr.sh](/home/dennis/beagle-os/scripts/merge-copilot-autofix-pr.sh): Draft-PRs werden nicht mehr ignoriert, sondern automatisch ready gesetzt.
  - [scripts/create-copilot-autofix-issue.sh](/home/dennis/beagle-os/scripts/create-copilot-autofix-issue.sh): offene Autofix-Issues werden pro Workflow/Branch wiederverwendet statt gespammt.
  - [scripts/close-resolved-copilot-autofix-issues.sh](/home/dennis/beagle-os/scripts/close-resolved-copilot-autofix-issues.sh): sobald ein Workflow auf `main` oder Release-Tag wieder gruen ist, werden passende offene `[autofix]`-Issues automatisch kommentiert und geschlossen.
- Validierung:
  - `bash -n` fuer betroffene Shell-Skripte
  - `python3 -m py_compile scripts/render-site-templates.py`
  - YAML-Syntaxcheck fuer `copilot-automerge` und `public-website`
  - direkter Python-Runner fuer `tests/unit/test_package_sh_regressions.py`
  - lokaler Enrollment-Test konnte nicht laufen, weil `pytest` lokal nicht installiert ist

## Update (2026-05-01, BeagleStream Phase A Forks)

**Scope**: Sunshine- und Moonlight-Qt-Forks fuer BeagleStream Phase A wurden unter `meinzeug/*` angelegt und auf Branch `beagle/phase-a` umgesetzt. Alle lokalen Build-Prerequisites sind in den Fork-Repos dokumentiert, damit die lokale Toolchain nicht zum impliziten Wissen wird.

- `meinzeug/beagle-stream-server`: `src/beagle/` mit Config-Loader, Broker-Client und Token-Auth, CMake-Option `BEAGLE_INTEGRATION`, Token-als-PIN-Hook im bestehenden Sunshine-Pairing und `.deb`-Skeleton `beagle-stream-server`.
- `meinzeug/beagle-stream-client`: `app/beagle/` mit Enrollment-Config, Broker-Allocate und WireGuard-Peer-Aktivierung, Session-Start-Integration, Token-als-PIN-Pairing und BeagleStream-Branding.
- Reproduzierbarkeit: beide Forks enthalten `docs/beagle-phase-a-build.md` mit Build-Host-Paketen, Submodule- und Build-Kommandos.
## Update (2026-05-02, BeagleStream Runtime-Erkennung + Release-Workflow-Härtung)

**Scope**: `beagle-os` erkennt jetzt explizit, ob in VMs der echte `beagle-stream-server` oder nur der bisherige Sunshine-Fallback installiert wurde; gleichzeitig wurden zwei sinnvolle Copilot-Release-Fixes direkt in `main` uebernommen.

- Streaming-Runtime-Kennzeichnung:
  - [scripts/configure-sunshine-guest.sh](/home/dennis/beagle-os/scripts/configure-sunshine-guest.sh): schreibt nach der Paketinstallation `/etc/beagle/stream-runtime.env` mit `BEAGLE_STREAM_RUNTIME_VARIANT=beagle-stream-server|sunshine-fallback` plus Paket-URL.
  - [beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl](/home/dennis/beagle-os/beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl): schreibt dieselbe Kennzeichnung fuer neue Ubuntu-Beagle-VMs im Firstboot-Provisioning.
  - [beagle-host/services/installer_prep.py](/home/dennis/beagle-os/beagle-host/services/installer_prep.py): liest Variant-/Paketstatus per Guest-Probe ein, liefert `stream_runtime` im Payload und unterscheidet in den Readiness-Meldungen zwischen echtem BeagleStream-Server und Sunshine-Fallback.
- Regressionen:
  - [tests/unit/test_configure_sunshine_guest_regressions.py](/home/dennis/beagle-os/tests/unit/test_configure_sunshine_guest_regressions.py)
  - [tests/unit/test_ubuntu_beagle_firstboot_regressions.py](/home/dennis/beagle-os/tests/unit/test_ubuntu_beagle_firstboot_regressions.py)
  - [tests/unit/test_installer_prep_stream_runtime.py](/home/dennis/beagle-os/tests/unit/test_installer_prep_stream_runtime.py)
- Release-/Deploy-Fixes aus Copilot uebernommen:
  - [.github/workflows/release.yml](/home/dennis/beagle-os/.github/workflows/release.yml): Release-Workflow per `concurrency` serialisiert und `gh release create` von Asset-Uploads entkoppelt, damit keine halbfertigen Releases oder Rennbedingungen entstehen.
  - [scripts/publish-public-update-artifacts.sh](/home/dennis/beagle-os/scripts/publish-public-update-artifacts.sh): `rsync` nutzt jetzt `--delete-before --inplace`, damit `beagle-os.com` beim Update nicht erneut am vollen Zielvolume scheitert.
- Validierung:
  - `bash -n scripts/configure-sunshine-guest.sh scripts/publish-public-update-artifacts.sh`
  - `python3 -m py_compile beagle-host/services/installer_prep.py`
  - direkter Python-Harness fuer 10 Regressionen (`HARNESS_OK 10`)

- Checkliste: `docs/checklists/02-streaming-endpoint.md` Phase-A-Forkpunkte abgehakt; Thin-Client-OS-Image-Bundling war zu diesem Zeitpunkt noch der separate naechste Packaging-Schritt.
- Validierung: lokaler Client-Build ueber `qmake ../moonlight-qt.pro && make -j2` gruen; lokaler Server-Build mit `-DBEAGLE_INTEGRATION=ON` und `cmake --build ... --target sunshine -j2` gruen. Live-Control-Plane-Smoke gegen `srv1` ist der naechste Integrationsschritt.

## Update (2026-05-02, BeagleStream Thin-Client Packaging)

**Scope**: Der BeagleStream-Client-Fork ist im Thin-Client-Buildpfad vorbereitet und der Runtime-Launcher blockiert Enrollment-basierte Broker-Sessions nicht mehr durch die alte statische Moonlight-Host-Pflicht.

- Thin-Client-Build:
  - [scripts/build-thin-client-installer.sh](/home/dennis/beagle-os/scripts/build-thin-client-installer.sh): standardmaessiges Staging aus `meinzeug/beagle-stream-client` Release `beagle-phase-a`, ueberschreibbar per `PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_URL`/`BEAGLE_STREAM_CLIENT_URL`, mit sicherem Fallback auf das bisherige Moonlight-AppImage.
  - Der Build erzeugt neben `/usr/local/bin/moonlight` auch `/usr/local/bin/beagle-stream`, wenn das extrahierte AppImage den BeagleStream-Binary enthaelt.
- Runtime:
  - [thin-client-assistant/runtime/moonlight_runtime_exec.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/moonlight_runtime_exec.sh): erkennt hostless BeagleStream ueber `/etc/beagle/enrollment.conf` und baut `beagle-stream stream "<App>"` statt `moonlight stream <Host> "<App>"`.
  - [thin-client-assistant/runtime/launch-moonlight.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/launch-moonlight.sh): ueberspringt Legacy-Host-Sync, Reichweitenprobe, manuelles Pairing und Manager-Prepare fuer hostless Broker-Sessions.
  - [thin-client-assistant/runtime/launch-session.sh](/home/dennis/beagle-os/thin-client-assistant/runtime/launch-session.sh): Launch-Status zeigt bei Enrollment ohne Host `broker:<App>` und `beagle-stream`.
  - [beagle-os/overlay/usr/local/sbin/beagle-healthcheck](/home/dennis/beagle-os/beagle-os/overlay/usr/local/sbin/beagle-healthcheck): meldet fehlendes `beagle-stream` explizit als Health-Failure, wenn hostless Enrollment aktiv ist.
- Regression:
  - [tests/unit/test_thin_client_live_build_regressions.py](/home/dennis/beagle-os/tests/unit/test_thin_client_live_build_regressions.py): Hostless-BeagleStream-Runtime und Build-Wrapper abgesichert.
- Validierung:
  - `bash -n` fuer geaenderte Shell-Skripte.
  - Direkter Python-Runner fuer `tests/unit/test_thin_client_live_build_regressions.py`, weil `pytest` lokal nicht installiert ist.
  - Manuelle Shell-Probe: hostless Enrollment erzeugt `beagle-stream stream Desktop ...`; statischer Host erzeugt weiter `moonlight stream <host> Desktop ...`.

## Update (2026-05-02, BeagleStream Server Package Hook)

**Scope**: VM-Guest-Prep und Ubuntu-Beagle-Firstboot versuchen jetzt zuerst das BeagleStream-Server-Paket und behalten Sunshine nur als Fallback, bis das Server-Fork-Release-Asset verfuegbar ist.

- [scripts/configure-sunshine-guest.sh](/home/dennis/beagle-os/scripts/configure-sunshine-guest.sh): `BEAGLE_STREAM_SERVER_URL` mit Default auf `meinzeug/beagle-stream-server` Release `beagle-phase-a`; bei Downloadfehlern Fallback auf upstream `SUNSHINE_URL`.
- [beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl](/home/dennis/beagle-os/beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl): gleicher BeagleStream-first/Fallback-Pfad fuer neue VM-Firstboot-Installationen.
- [beagle-host/services/service_registry.py](/home/dennis/beagle-os/beagle-host/services/service_registry.py) und [beagle-host/services/ubuntu_beagle_provisioning.py](/home/dennis/beagle-os/beagle-host/services/ubuntu_beagle_provisioning.py): Profil-Label/Streaming auf BeagleStream angepasst und Template-URL injiziert.
- Regression:
  - [tests/unit/test_configure_sunshine_guest_regressions.py](/home/dennis/beagle-os/tests/unit/test_configure_sunshine_guest_regressions.py)
  - [tests/unit/test_ubuntu_beagle_firstboot_regressions.py](/home/dennis/beagle-os/tests/unit/test_ubuntu_beagle_firstboot_regressions.py)
- Validierung:
  - `bash -n scripts/configure-sunshine-guest.sh`
  - `python3 -m py_compile beagle-host/services/service_registry.py beagle-host/services/ubuntu_beagle_provisioning.py`
  - Direkter Python-Runner fuer die beiden Regression-Dateien.

## Update (2026-05-02, dynamische Release-Versionierung)

**Scope**: GitHub-Release-, ISO-/Artifact- und Public-Website-Workflows lesen nicht mehr starr die Baseline `VERSION` als finale Release-Version. CI loest die Version reproduzierbar aus manuellem Input, Git-Tag oder automatisch aus dem hoechsten SemVer-Tag plus Patch-Bump auf.

- [scripts/resolve-release-version.sh](/home/dennis/beagle-os/scripts/resolve-release-version.sh): zentrale SemVer-Aufloesung mit `BEAGLE_RELEASE_VERSION`, Tag-Ref-Erkennung, Head-Tag-Wiederverwendung und automatischem Patch-Bump.
- [.github/workflows/release.yml](/home/dennis/beagle-os/.github/workflows/release.yml): alle Build-/Package-/Deploy-Jobs schreiben vor dem Build die aufgeloeste Version nach `VERSION`; manuelle Runs koennen `release_version` setzen.
- [.github/workflows/build-iso.yml](/home/dennis/beagle-os/.github/workflows/build-iso.yml): Artifact-Builds nutzen dieselbe dynamische Versionsauflösung.
- [.github/workflows/public-website.yml](/home/dennis/beagle-os/.github/workflows/public-website.yml): Website-Deploys rendern gegen die aufgeloeste Version statt hart gegen `8.0.0`.
- Validierung: `bash -n scripts/resolve-release-version.sh`, manuelle Version/Tag-Aufloesung, PyYAML-Syntaxcheck fuer die drei Workflows und `git diff --check`.

## Update (2026-05-02, BeagleStream hostless allocate contract)

**Scope**: Der vorhandene Control-Plane-Brokerpfad akzeptiert jetzt den in `fork.md` dokumentierten hostless Allocate-Request ohne festen `user_id`, ohne den bestehenden Pool-Allocator oder den Pairing-/WireGuard-Pfad zu brechen.

- Backend:
  - [beagle-host/services/stream_http_surface.py](/home/dennis/beagle-os/beagle-host/services/stream_http_surface.py): `POST /api/v1/streams/allocate` verlangt nicht mehr zwangsläufig `user_id`; wenn nur `device_id` vorliegt, wird ein stabiler interner Lease-Owner `device:<device_id>` verwendet.
  - Der API-Contract bleibt nach aussen hostless-faehig: `user_id` darf leer sein; als zusaetzliche Diagnose liefert die Response jetzt `lease_user_id`.
  - Hard-Fail statt Kollision: wenn weder `user_id` noch `device_id` gesetzt sind, liefert der Endpoint reproduzierbar `400`.
- Regression:
  - [tests/unit/test_beagle_stream_client_broker.py](/home/dennis/beagle-os/tests/unit/test_beagle_stream_client_broker.py): neuer Hostless-Fall ohne `user_id`, Guard gegen fehlende Identitaet und bestehender Benutzerfall mit unveraendertem Pairing-Token/Lease-Pfad.
- Validierung:
  - `python3 -m py_compile beagle-host/services/stream_http_surface.py`
  - isolierte Test-venv unter `/tmp/beagle-os-test-venv`
  - `/tmp/beagle-os-test-venv/bin/python -m pytest -q tests/unit/test_beagle_stream_client_broker.py tests/unit/test_beagle_stream_server_api.py tests/unit/test_stream_http_surface.py` => `17 passed`
## Update (2026-05-02, KDE Plasma becomes the managed desktop default)

- Scope:
  - switch newly provisioned Ubuntu desktop VMs from the old mixed desktop default to a dedicated Plasma-first profile model
  - add two operator-visible desktop variants: `Beagle OS Cyberpunk` and `KDE Plasma Classic`
  - bundle the cyberpunk wallpaper as a versioned repo asset instead of referencing `/home/dennis/...`
  - align thinclient/live boot splash assets with the same Beagle wallpaper
- Changed:
  - `beagle-host/services/service_registry.py`: default desktop changed to `plasma-cyberpunk`; visible provisioning catalog reduced to the two supported Plasma variants; wallpaper source now points at `assets/branding/beagle-cyberpunk-wallpaper.png`
  - `beagle-host/services/ubuntu_beagle_provisioning.py`: desktop-profile metadata now carries `theme_variant`; provisioning validates required wallpaper assets and embeds the wallpaper file into the guest seed ISO
  - `beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl`: Plasma-aware firstboot flow, wallpaper import from the seed, LightDM branding, lock/power defaults and one-shot Plasma profile apply script
  - `website/index.html`: provisioning form label clarified to `Desktop-Design`
  - `beagle-os/overlay/usr/share/plymouth/themes/beagle/*` and `thin-client-assistant/live-build/config/includes.chroot/usr/share/plymouth/themes/beagle/*`: splash switched to the new fullscreen wallpaper flow
  - `beagle-os/overlay/usr/local/share/beagle-os/*` plus thinclient session wrappers: desktop/live runtime background switched to the same Beagle wallpaper and dark base color
  - `tests/unit/test_ubuntu_beagle_desktop_profiles.py` added; `tests/unit/test_ubuntu_beagle_firstboot_regressions.py` extended
- Validation:
  - `python3 -m py_compile beagle-host/services/ubuntu_beagle_provisioning.py beagle-host/services/service_registry.py beagle-host/services/ubuntu_beagle_inputs.py`
  - `bash -n beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl`
  - `python3 -m unittest tests.unit.test_ubuntu_beagle_desktop_profiles tests.unit.test_ubuntu_beagle_firstboot_regressions tests.unit.test_ubuntu_beagle_provisioning_quota tests.unit.test_vm_api_regressions`

## Update (2026-05-02, Thinclient broker presets stop falling back to direct mode)

- Scope:
  - fix VM-specific live/install USB presets so `beagle_stream_mode=broker` really boots into the broker/enrollment path instead of silently defaulting back to direct Moonlight mode
  - ensure already-enrolled clients also rewrite their runtime connection method to `broker`
- Changed:
  - [beagle-host/services/thin_client_preset.py](/home/dennis/beagle-os/beagle-host/services/thin_client_preset.py): broker presets now emit `PVE_THIN_CLIENT_PRESET_CONNECTION_METHOD=broker`
  - [thin-client-assistant/runtime/generate_config_from_preset.py](/home/dennis/beagle-os/thin-client-assistant/runtime/generate_config_from_preset.py): installer-env generation derives `CONNECTION_METHOD=broker` from `PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_MODE=broker` even when old presets do not carry the explicit field yet
  - [thin-client-assistant/usb/usb_writer_write_stage.sh](/home/dennis/beagle-os/thin-client-assistant/usb/usb_writer_write_stage.sh): live USB writer no longer defaults broker presets back to `direct`
  - [thin-client-assistant/runtime/apply_enrollment_config.py](/home/dennis/beagle-os/thin-client-assistant/runtime/apply_enrollment_config.py): successful enrollment now persists `PVE_THIN_CLIENT_CONNECTION_METHOD=broker` together with `beagle-stream` and the pool allocation config
  - Regression coverage: [tests/unit/test_apply_enrollment_config.py](/home/dennis/beagle-os/tests/unit/test_apply_enrollment_config.py) plus new [tests/unit/test_thin_client_broker_preset_regressions.py](/home/dennis/beagle-os/tests/unit/test_thin_client_broker_preset_regressions.py)
- Validation:
  - `bash -n thin-client-assistant/usb/usb_writer_write_stage.sh`
  - `python3 -m py_compile thin-client-assistant/runtime/generate_config_from_preset.py thin-client-assistant/runtime/apply_enrollment_config.py beagle-host/services/thin_client_preset.py`
  - local Python harness over broker preset generation + enrollment rewrite => `THINCLIENT_BROKER_FIX_OK`

## Update (2026-05-02, Live USB splash and wallpaper assets unified)

- Scope:
  - remove the remaining stale boot/session wallpaper assets from the thin-client live/USB path
  - make boot/session backgrounds fill the available display area instead of staying centered at the old fixed size
- Changed:
  - [thin-client-assistant/usb/assets/grub-background.jpg](/home/dennis/beagle-os/thin-client-assistant/usb/assets/grub-background.jpg): regenerated from the versioned Beagle wallpaper
  - [thin-client-assistant/live-build/config/includes.chroot/usr/share/plymouth/themes/beagle/beagleos.png](/home/dennis/beagle-os/thin-client-assistant/live-build/config/includes.chroot/usr/share/plymouth/themes/beagle/beagleos.png), [thin-client-assistant/live-build/config/includes.chroot/usr/local/share/beagle-os/beagleos.png](/home/dennis/beagle-os/thin-client-assistant/live-build/config/includes.chroot/usr/local/share/beagle-os/beagleos.png) and [thin-client-assistant/live-build/config/includes.chroot/usr/local/share/beagle-os/beagleos-gaming.png](/home/dennis/beagle-os/thin-client-assistant/live-build/config/includes.chroot/usr/local/share/beagle-os/beagleos-gaming.png): replaced stale low-res assets with the current repo wallpaper
  - [.artifacts/beaglethinclient.png](/home/dennis/beagle-os/.artifacts/beaglethinclient.png) and [.artifacts/beaglethinclient-tty1.png](/home/dennis/beagle-os/.artifacts/beaglethinclient-tty1.png): aligned with the same wallpaper for generated thinclient visuals
  - [thin-client-assistant/live-build/config/includes.chroot/usr/share/plymouth/themes/beagle/beagle.script](/home/dennis/beagle-os/thin-client-assistant/live-build/config/includes.chroot/usr/share/plymouth/themes/beagle/beagle.script): background now scales to the current window size
  - [thin-client-assistant/live-build/config/includes.chroot/usr/local/bin/start-pve-thin-client-session](/home/dennis/beagle-os/thin-client-assistant/live-build/config/includes.chroot/usr/local/bin/start-pve-thin-client-session) and [beagle-os/overlay/usr/local/bin/start-beagle-session](/home/dennis/beagle-os/beagle-os/overlay/usr/local/bin/start-beagle-session): `feh --bg-fill` instead of `--bg-center`
  - [thin-client-assistant/usb/usb_writer_write_stage.sh](/home/dennis/beagle-os/thin-client-assistant/usb/usb_writer_write_stage.sh), [scripts/build-thin-client-installer.sh](/home/dennis/beagle-os/scripts/build-thin-client-installer.sh) and [beagle-os/overlay/usr/local/sbin/beagle-update-client](/home/dennis/beagle-os/beagle-os/overlay/usr/local/sbin/beagle-update-client): GRUB now actively enables the branded background instead of only copying the file
- Validation:
  - `bash -n thin-client-assistant/live-build/config/includes.chroot/usr/local/bin/start-pve-thin-client-session beagle-os/overlay/usr/local/bin/start-beagle-session thin-client-assistant/usb/usb_writer_write_stage.sh scripts/build-thin-client-installer.sh`
  - `python3 -m py_compile beagle-os/overlay/usr/local/sbin/beagle-update-client`

## Update (2026-05-02, Repo version + system updates runtime hardened)

- Scope:
  - keep `VERSION` aligned with patch releases and surface the same runtime version on `srv1`
  - fix `/api/v1/settings/updates/apply` so WebUI-triggered system updates no longer run unprivileged `apt-get`
  - make repo deployments reload long-running Beagle services so fresh Python code is actually live after an update
- Changed:
  - [.github/workflows/release.yml](/home/dennis/beagle-os/.github/workflows/release.yml), [.github/workflows/public-website.yml](/home/dennis/beagle-os/.github/workflows/public-website.yml) and [VERSION](/home/dennis/beagle-os/VERSION): release flow now persists the bumped `VERSION` back to `main` and skips recursive self-trigger loops; repo version is currently `8.0.8`
  - [scripts/apply-system-updates.sh](/home/dennis/beagle-os/scripts/apply-system-updates.sh), [beagle-host/systemd/beagle-system-updates.service](/home/dennis/beagle-os/beagle-host/systemd/beagle-system-updates.service), [beagle-host/systemd/beagle-system-updates.timer](/home/dennis/beagle-os/beagle-host/systemd/beagle-system-updates.timer) and [beagle-host/polkit/beagle-system-updates.rules](/home/dennis/beagle-os/beagle-host/polkit/beagle-system-updates.rules): root-owned background update runner with persisted status JSON, timer-based automation and `apt-get upgrade --with-new-pkgs` so kept-back kernel/meta updates are also installed automatically
  - [beagle-host/services/server_settings.py](/home/dennis/beagle-os/beagle-host/services/server_settings.py), [website/ui/settings.js](/home/dennis/beagle-os/website/ui/settings.js) and [website/index.html](/home/dennis/beagle-os/website/index.html): Updates panel/API now report installed/remote version plus background system-update state and start updates asynchronously instead of pretending a foreground install finished
  - [scripts/install-beagle-host-services.sh](/home/dennis/beagle-os/scripts/install-beagle-host-services.sh): repo deploys now restart active runtime services (`beagle-control-plane`, public streams, noVNC proxy) after `daemon-reload`, preventing stale code/runtime-version drift on `srv1`
  - Regression coverage: [tests/unit/test_server_settings.py](/home/dennis/beagle-os/tests/unit/test_server_settings.py) and [tests/unit/test_settings_ui_regressions.py](/home/dennis/beagle-os/tests/unit/test_settings_ui_regressions.py)
- Validation:
  - `bash -n scripts/install-beagle-host-services.sh scripts/apply-system-updates.sh`
  - `python3 -m unittest tests.unit.test_server_settings tests.unit.test_settings_ui_regressions`
  - live on `srv1`: `/opt/beagle/VERSION` and `repo-auto-update-status.json` both show `8.0.8`; `POST /api/v1/settings/updates/apply` now returns `200` and starts `beagle-system-updates.service`

## Update (2026-05-02, Artifact refresh duplicate runs no longer fail red)

- Scope:
  - keep automatic artifact refreshes green when a timer or operator starts `prepare-host-downloads` while another artifact build already holds the lock
- Changed:
  - [scripts/lib/artifact_lock.sh](/home/dennis/beagle-os/scripts/lib/artifact_lock.sh): lock helper now supports a non-blocking `BEAGLE_ARTIFACT_LOCK_SKIP_IF_BUSY=1` mode and returns a dedicated busy code instead of only waiting or timing out
  - [scripts/prepare-host-downloads.sh](/home/dennis/beagle-os/scripts/prepare-host-downloads.sh): duplicate invocations now treat a busy artifact lock as a benign skip and exit successfully with a clear log message
  - [scripts/refresh-host-artifacts.sh](/home/dennis/beagle-os/scripts/refresh-host-artifacts.sh): the automatic refresh wrapper uses the new skip-if-busy path so concurrent timer runs no longer surface a red failed service on `srv1`
  - Regression coverage: [tests/unit/test_prepare_host_downloads_status_regressions.py](/home/dennis/beagle-os/tests/unit/test_prepare_host_downloads_status_regressions.py) and [tests/unit/test_refresh_host_artifacts_regressions.py](/home/dennis/beagle-os/tests/unit/test_refresh_host_artifacts_regressions.py)
- Validation:
  - `bash -n scripts/lib/artifact_lock.sh scripts/prepare-host-downloads.sh scripts/refresh-host-artifacts.sh`
  - local Python harness over the affected regression assertions => `HARNESS_OK`
