# Beagle OS Refactor - Decisions

Stand: 2026-04-13

## D-061: Doku auf 5 thematische Checklisten konsolidiert (2026-04-29)

Kontext: Sechs parallele Plan-Verzeichnisse (`refactor/`, `refactorv2/`, `gofuture/`, `goenterprise/`, `goadvanced/`, `gorelease/`) mit 60+ Plan-Dateien hatten sich ueberschnitten und widersprachen sich teilweise. Onboarding-Aufwand fuer neue Agents zu hoch.

Entscheidung:

- Es gibt genau **5** aktive Checklisten unter `docs/checklists/01..05-*.md` (Platform, Streaming/Endpoint, Security, Quality/CI, Release/Operations).
- Alle anderen Plan-Verzeichnisse sind nach `docs/archive/` verschoben (History via `git mv` erhalten) und gelten ausschliesslich als Hintergrundmaterial.
- Neue Aufgaben kommen ausschliesslich in eine der 5 Checklisten. Es entstehen keine neuen Plan-Dateien mehr.
- `docs/MASTER-PLAN.md` bleibt die kanonische Vision; `docs/STATUS.md` ist der Enterprise-Readiness-Snapshot mit Ampel; `docs/README.md` ist die zentrale Navigation.
- `scripts/check-gofuture-complete.sh` wurde zu `scripts/check-checklists-complete.sh` generalisiert (optional `CHECKLIST_GATE_LIST` zur Selektion).
- Logbuecher (`05-progress.md`, `06-next-steps.md`, `07-decisions.md`, `08-todo-global.md`, `11-security-findings.md`) bleiben als chronologische Run-Logs erhalten.

Nebenwirkung Live-Fix: `tests.yml` faehrt nun auch Integration-Tests in CI (Job `integration` zwischen `bats` und `webui-provisioning-smoke`); 89 Tests lokal verifiziert.

---

## D-058: qemu+ssh-Migrations-Deadlocks werden mit expliziter Shared-Storage-Guidance behandelt
- Entscheidung: Der Migrationsservice erkennt qemu+ssh-nahe Timeout-/Connection-Deadlock-Indikatoren und erweitert den Fehlerpfad um eine klare Operator-Empfehlung: bevorzugter Abnahmepfad ist shared-storage live migration; fallback ist `copy_storage=true` als cold/offline copy path.
- Grund: Der Runtime-Fehler war bisher zu unscharf und fuehrte zu wiederholten, schwer unterscheidbaren Fehlversuchen. Die explizite Guidance macht den naechsten reproduzierbaren Operator-Schritt direkt sichtbar und reduziert Trial-and-Error im HA-/Cluster-Betrieb.
- Dateien: `beagle-host/services/migration_service.py`, `tests/unit/test_migration_service.py`.

## D-057: Desktop-Streaming-Guards im Ready-Flow sind sichtbar, aber nicht hart blockierend
- Entscheidung: `scripts/ensure-vm-stream-ready.sh` prueft nach erfolgreichem Sunshine-API-Check zusaetzlich `xset q` und die Abwesenheit von `light-locker`/`xfce4-power-manager`; ein fehlschlagender Guard setzt einen Warnhinweis im Ready-Ergebnis statt den gesamten Provisioning-Flow auf `error` zu brechen.
- Grund: Der Guard macht Live-Desktop-Drift fuer Operatoren sichtbar, ohne bestehende Bereitstellungspfade unnoetig hart zu unterbrechen (z.B. bei temporaerer Display-/Session-Unsauberkeit waehrend des First-Login-Fensters).
- Dateien: `scripts/ensure-vm-stream-ready.sh`, `tests/unit/test_ensure_vm_stream_ready_regressions.py`.

## D-056: Session-Repository erzwingt referenzierbare Pool-Zuordnung als Pflichtfeld
- Entscheidung: `session_repository.py` behandelt `pool_id` als Pflichtfeld und persistiert Sessions nur FK-kompatibel gegen die `pools`-Tabelle; `vmid` bleibt optional (nullable) fuer laufende oder entkoppelte Session-Phasen.
- Grund: Der Session-Lifecycle ist fachlich pool-gebunden, waehrend die VM-Referenz je nach Zustand fehlen kann; diese Regel reduziert inkonsistente Session-Daten frueh im SQLite-Pfad.
- Dateien: `core/repository/session_repository.py`, `tests/unit/test_session_repository.py`.

## D-055: Device-Repository nutzt Status/Fingerprint als erste native Query-Spalten
- Entscheidung: Der zweite SQLite-Repository-Slice (`device_repository.py`) fuehrt neben `payload_json` explizit `status` und `fingerprint` als filterbare Spalten, um die haeufigsten Registry-Abfragen frueh ohne JSON-Scan abzubilden.
- Grund: Device-Fleet-Operatorik arbeitet regelmaessig nach Zustand und Hardware-Fingerprint; diese beiden Felder liefern sofort messbaren Nutzen fuer die spaetere Service-Migration bei minimalem Schema-Risiko.
- Dateien: `core/repository/device_repository.py`, `core/persistence/migrations/001_init.sql`, `tests/unit/test_device_repository.py`.

## D-054: VM-Repository startet als Hybrid-Store (Filterspalten + volle JSON-Payload)
- Entscheidung: Das erste produktive SQLite-Repository (`vm_repository.py`) persistiert die komplette VM-Struktur in `payload_json`, fuehrt aber `vmid`, `node_id`, `status`, `name`, `pool_id` als dedizierte Spalten fuer gezielte Filter und spaetere Indizes.
- Grund: Damit bleibt der Einstieg migrationsarm und kompatibel zu bestehenden JSON-Strukturen, waehrend die wichtigsten Read-Pfade schon jetzt effizient und typisiert auf SQLite laufen.
- Dateien: `core/repository/vm_repository.py`, `tests/unit/test_vm_repository.py`, `core/persistence/migrations/001_init.sql`.

## D-053: Erstes SQLite-Schema startet als Hybrid aus Schluesselspalten und `payload_json`
- Entscheidung: `001_init.sql` modelliert die zentralen Entitaeten (`vms`, `pools`, `sessions`, `devices`, `gpus`, `audit_events`, `secrets_meta`) zunaechst mit stabilen Lookup-/Beziehungsfeldern plus einer generischen `payload_json`-Spalte statt sofort alle bisherigen JSON-Felder relational auszunormalisieren.
- Grund: Fuer den ersten SQLite-Einstieg brauchen die naechsten Repository- und Importer-Slices verlässliche Identitaeten, Indizes und Foreign-Keys, aber noch keinen Big-Bang auf das volle Feldmodell aller heutigen JSON-States.
- Dateien: `core/persistence/migrations/001_init.sql`, `tests/unit/test_sqlite_db.py`.

## D-052: SQLite-State-Layer nutzt pro Thread eine gecachte Verbindung mit WAL + zentralem Migrationslog
- Entscheidung: Der neue SQLite-Unterbau kapselt DB-Zugriffe in `core/persistence/sqlite_db.py` als `BeagleDb`, aktiviert auf jeder Verbindung `journal_mode=WAL`, `foreign_keys=ON`, setzt `busy_timeout` und verfolgt angewendete SQL-Dateien in `schema_migrations`.
- Grund: Die spaetere JSON->SQLite-Migration braucht einen kleinen, testbaren Basiskern, der Schreibkonkurrenz, referenzielle Integritaet und wiederholbare Schema-Upgrades standardisiert, bevor einzelne Services oder Repositories umgestellt werden.
- Dateien: `core/persistence/sqlite_db.py`, `tests/unit/test_sqlite_db.py`.

## D-051: Host-Oneshots muessen ihre Sandbox an die Aufgabe koppeln
- Entscheidung: Systemd-Oneshots, die Host-State oder nftables aktiv reparieren, duerfen nicht pauschal alle Capabilities verlieren; sie bekommen eng begrenzte Capabilities und explizite `ReadWritePaths`.
- Grund: Eine zu harte Sandbox kann Self-Heal- und Reconcile-Jobs in eine permanente failed-Schleife bringen. Minimal notwendige Privilegien sind sicherer als ein formal harter, aber funktionsloser Dienst.
- Dateien: `beagle-host/systemd/beagle-public-streams.service`, `scripts/beagle-cluster-auto-join.sh`, `scripts/repo-auto-update.sh`.

## D-050: Proxy-Forwarded-Client-IP nur von lokalem Reverse Proxy vertrauen
- Entscheidung: Die Control Plane nutzt `X-Forwarded-For`/`X-Real-IP` fuer Audit, Login-Guard und API-Rate-Limit nur, wenn der direkte Peer ein lokaler Proxy ist.
- Grund: nginx terminiert die oeffentliche WebUI und setzt Forwarded-For; ohne Auswertung werden alle Nutzer als `127.0.0.1` limitiert. Direkte externe Clients duerfen den Header aber nicht spoofend kontrollieren.
- Dateien: `beagle-host/services/request_handler_mixin.py`, `tests/unit/test_request_handler_mixin_client_addr.py`.

## D-049: WebUI bleibt unter strikter CSP ohne Inline-Style-Ausnahmen
- Entscheidung: Neue und bestehende WebUI-Renderer duerfen keine `style="..."`-Attribute in HTML-Strings erzeugen; dynamische Visualisierung nutzt CSS-Klassen, feste Buckets oder echte Stylesheets.
- Grund: Die produktive CSP `style-src 'self'` soll nicht durch `unsafe-inline` aufgeweicht werden. Klassenbasierte Darstellung erhaelt die Sicherheitsgrenze und vermeidet Browser-Console-Fehler.
- Dateien: `website/ui/scheduler_insights.js`, `website/ui/energy_dashboard.js`, `website/ui/gpu_dashboard.js`, `website/ui/settings.js`, `website/ui/cluster.js`, `website/ui/virtualization.js`, `website/styles/_helpers.css`.

## D-048: Geschuetzte Settings-Panels duerfen ohne Session keine API-Reads ausloesen
- Entscheidung: WebUI-Renderer fuer Settings-/Telemetry-Slices muessen vor jedem Fetch mindestens Session- und RBAC-Gates spiegeln; geschuetzte Panels duerfen beim Bootstrap nicht blind vorgerendert werden.
- Grund: Backend-RBAC allein schuetzt zwar die Daten, aber unautorisierte Vorab-Requests erzeugen auf Live-Systemen irrefuehrende Fehlerfluten, erschweren Session-Debugging und verschlechtern die Operator-Erfahrung.
- Dateien: `website/main.js`, `website/ui/state.js`, `website/ui/scheduler_insights.js`, `website/ui/cost_dashboard.js`, `website/ui/energy_dashboard.js`.

## D-047: Stream-Zero-Trust-Modus lebt im Pool-Streaming-Profil
- Entscheidung: Der BeagleStream-VPN-Modus (`vpn_required`, `vpn_preferred`, `direct_allowed`) wird im bestehenden `StreamingProfile` des Desktop-Pools persistiert, statt als separates ad-hoc UI-Flag oder nur im Thin-Client zu existieren.
- Grund: Der Wert muss entlang derselben Kette verfuegbar sein, die auch Codec/FPS/Bitrate beschreibt: Pool-Wizard -> Pool-API -> Pool-State -> spaeterer Stream-Server-/Thin-Client-Consume.
- Dateien: `core/virtualization/streaming_profile.py`, `website/ui/policies.js`, `website/index.html`.

## D-001: Beagle-native ist Primarpfad
- Entscheidung: Zielarchitektur ist eigenstaendig lauffaehig ohne Beagle host.
- Grund: Produktstrategie verlangt Plattformautonomie.

## D-002: Thinclient-Streaming ist Kernfaehigkeit
- Entscheidung: Streaming-Orchestrierung pro VM wird als Tier-1 Domain behandelt.
- Grund: Das ist das unterscheidende Produktmerkmal von Beagle OS.

## D-003: Session-basierte Auth als Standard
- Entscheidung: username/password + session lifecycle ersetzt Token-First UI.
- Grund: Multi-User Betrieb, Auditierbarkeit und RBAC brauchen identity-native Zugriffe.

## D-004: RBAC serverseitig erzwungen
- Entscheidung: Autorisierung wird im Backend zentral und deklarativ geprueft.
- Grund: UI-only checks sind unsicher und nicht ausreichend.

## D-005: Legacy API-Token nur fuer Automation
- Entscheidung: API tokens bleiben optional fuer machine-to-machine Zwecke.
- Grund: Rueckwaertskompatibilitaet fuer Skripte, ohne UI-Primarzugang darauf aufzubauen.

## D-006: Inkrementelle Wellen statt Big Bang
- Entscheidung: Umsetzung in vier Wellen mit klaren Abnahmen.
- Grund: Minimiert Runtime-Risiken und ermoeglicht fortlaufende Lieferbarkeit.

## D-007: Bootstrap-Admin fuer Erstzugang
- Entscheidung: Beim Start wird ein Bootstrap-Admin angelegt, wenn noch kein User existiert und Credentials gesetzt sind.

## D-008: Refactor Wave 2 zielt auf 7.0 als Cluster + VDI + Streaming Plattform
- Entscheidung: Naechster Versionssprung 7.0 erweitert Beagle OS um Cluster-Plane, VDI-Pools, Storage- und Network-Plane, GPU-Plane, IAM v2, Backup/DR, OpenAPI v2 und Terraform-Provider.
- Detail: gesamter Plan in `docs/refactorv2/`, Roadmap in `docs/refactorv2/04-roadmap-v2.md`.
- Grund: Heutiges Single-Node-Beagle ist konkurrenzfaehig fuer Single-Host-Streaming, aber strukturell nicht anschlussfaehig an Beagle host/Omnissa/Citrix/Win365/Parsec. Cluster + Pool + Identity sind die Tor-Features.
- Provider-Neutralitaet bleibt verbindlich; Cluster-Plane lebt im `core/`-Layer und im Beagle-Provider, Beagle host-Adapter wird nachgezogen aber nicht zur Voraussetzung gemacht.

## D-009: /api/v2 wird additiv eingefuehrt, /api/v1 bleibt stabil bis 8.0
- Entscheidung: Neue Cluster-/Pool-/Tenant-Konzepte erscheinen unter /api/v2; /api/v1 wird nicht gebrochen, sondern als Single-Node-Compatibility-Shim ueber denselben Cluster-Store abgebildet.
- Grund: bestehende Web Console, Endpoints und Skripte bleiben funktional waehrend des gesamten Wave-2-Rollouts.

## D-010: Streaming-Backend wird konfigurierbar (Apollo bevorzugt)
- Entscheidung: Default-Backend in 7.1.1 ist Apollo (Sunshine-Fork mit virtual display, HDR, per-client permissions); Sunshine-Mainline bleibt als Fallback waehlbar pro Pool.
- Grund: Apollo loest die Engpaesse virtual display, HDR, multi-monitor und auto-resolution, die heute gegen Parsec/Win365 fehlen.
- Grund: Ermöglicht kontrollierten Erstzugang ohne separaten Setup-Wizard.

## D-008: Session-Token als primaerer API-Auth-Mechanismus
- Entscheidung: Bearer Session-Token werden als Standard fuer UI-Authentifizierung verwendet.
- Grund: Passt zu username/password Login und erlaubt klare Session-Lifecycles.

## D-009: Legacy API-Token bleibt waehrend Migration gueltig
- Entscheidung: X-Beagle-Api-Token und Bearer-Token mit Legacy-Wert bleiben im Backend als Fallback aktiv.
- Grund: Bestehende Automationspfade und Tools duerfen waehrend Umbau nicht brechen.

## D-010: RBAC-Matrix v1 wird im Handler erzwungen
- Entscheidung: Mutierende API-Routen werden serverseitig ueber eine explizite Permission-Matrix geprueft (deny-by-default).
- Grund: Sofortige Risikoreduktion fuer Write-Aktionen, bevor User/Role-CRUD vollstaendig verfuegbar ist.

## D-011: Audit-Basis als append-only Event-Log
- Entscheidung: Auth- und Mutationsereignisse werden in ein append-only JSONL Audit-Log geschrieben.
- Grund: Nachvollziehbarkeit und Security-Forensik werden frueh aktiviert, ohne erst auf vollstaendige Audit-UI warten zu muessen.

## D-012: Auth-User/Role-CRUD als Backend-API
- Entscheidung: Benutzer- und Rollenverwaltung wird als eigene API-Surface unter /api/v1/auth/users und /api/v1/auth/roles bereitgestellt.
- Grund: RBAC muss operativ verwaltbar sein und darf nicht nur aus Bootstrap-Konfiguration bestehen.

## D-013: Permission-Mapping in dediziertem AuthZ-Service
- Entscheidung: Routen-zu-Permission-Abbildung liegt in beagle-host/services/authz_policy.py statt im Handler.
- Grund: Trennung von HTTP-Transport und Autorisierungslogik verbessert Wartbarkeit und Testbarkeit.

## D-014: Session-Lifecycle mit Idle- und Absolute-Timeout serverseitig erzwingen
- Entscheidung: Session-Validierung prueft idle timeout und absolute timeout im Backend, nicht nur Token-Ablauf.
- Grund: Reduziert Risiko langlebiger oder inaktiver Sessions in Multi-User-Betrieb.

## D-015: User-weiter Session-Revoke als Admin-Operation
- Entscheidung: POST /api/v1/auth/users/<username>/revoke-sessions ermoeglicht gezielte Session-Invalidierung.
- Grund: Incident-Response und Account-Schutz brauchen sofortige serverseitige Sperrung aktiver Sessions.

## D-016: First-Install-Onboarding ist verpflichtend vor Dashboard-Zugriff
- Entscheidung: Bei pending Onboarding zeigt die Website einen Setup-Dialog und blockiert den normalen Dashboard-Flow.
- Grund: Frisch installierte Hosts brauchen einen gefuehrten Erst-Setup statt direkter UI-Nutzung ohne Initialkonfiguration.

## D-017: Onboarding-Status als eigener Auth-Endpunkt
- Entscheidung: /api/v1/auth/onboarding/status und /api/v1/auth/onboarding/complete bilden den expliziten Server-Setup-Lifecycle.
- Grund: UI und Backend brauchen einen klaren, persistierten Zustand fuer "first boot" vs "configured".

## D-018: Beagle ist Default-Provider im Host-Installpfad

## D-019: SSH-Passwort-Auth Default ist `yes` im Standalone-Installer
- Entscheidung: `BEAGLE_SERVER_SSH_PASSWORD_AUTH` Default im Server-Installer auf `yes` gesetzt.
- Grund: Ein frisch installiertes System muss per SSH erreichbar sein; Passwort-Deaktivierung bleibt opt-in fuer Hardening, nicht opt-out fuer Grundfunktionalitaet.
- Datei: `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer` Zeile 31.

## D-020: USB-Tunnel-User heisst `beagle-tunnel`, nicht `beagle`
- Entscheidung: Default-Benutzername fuer den SSH-USB-Tunnel-Account ist `beagle-tunnel`, nicht `beagle`.
- Grund: Wurde `beagle` verwendet, ueberschrieb das SSH-Match-Block (`AuthenticationMethods publickey`) auch den Basis-Admin-User und blockierte Passwort-Login vollstaendig.
- Dateien: `scripts/install-beagle-host-services.sh`, `scripts/check-beagle-host.sh`, `beagle-host/bin/beagle-control-plane.py`.

## D-021: Script-Provider-Wrapper muss Provider-Timeouts transparent durchreichen
- Entscheidung: `scripts/lib/beagle_provider.py` akzeptiert fuer `run_json`/`run_text`/`run_checked` optional `timeout` und behandelt `TimeoutExpired` als kontrollierten Fehlerpfad.
- Grund: Provider-Implementierungen nutzen `timeout=` bereits; ohne Durchreichen entstehen Laufzeitfehler (`TypeError`) und der VM-Prep bricht ab.
- Datei: `scripts/lib/beagle_provider.py`.

## D-022: Debian-Hosts duerfen nicht an Ubuntu-only Language-Packs scheitern
- Entscheidung: `configure-sunshine-guest.sh` installiert `language-pack-*` nur, wenn die Pakete auf dem Zielhost im APT-Index existieren.
- Grund: Das gleiche VM-Prep-Skript wird auf Debian- und Ubuntu-basierten Hosts genutzt; Ubuntu-only Pakete duerfen den Gesamtflow nicht stoppen.
- Datei: `scripts/configure-sunshine-guest.sh`.

## D-023: Libvirt-Kernel-Boot fuer Ubuntu-Install nutzt per-domain `seclabel type=none`
- Entscheidung: Fuer beagle-provider Domains mit `qemu:commandline` (`-kernel/-initrd`) wird im Domain-XML `seclabel type="none"` gesetzt.
- Grund: libvirt/AppArmor blockiert in dieser Konstellation den Kernel-Dateizugriff ansonsten reproduzierbar mit `Permission denied`, selbst bei lesbaren Dateien.
- Scope: Nur beagle-provider Install-Domain-Flow; keine hostweite Abschaltung des libvirt Security Drivers im Installer.
- Betroffene Datei: `beagle-host/providers/beagle_host_provider.py`.

## D-024: Moonlight USB-Presets duerfen nicht ohne Sunshine Auto-Pair Credentials ausgeliefert werden
- Entscheidung: Der VM-Installer-Skriptgenerator bricht Moonlight-Preset-Generierung ab, wenn `sunshine_username`, `sunshine_password` oder `sunshine_pin` fehlen.
- Grund: Unvollstaendige Presets fuehren nach Thinclient-Reboot zu manueller PIN-Eingabe und brechen den Zielpfad "auto-connect".
- Umsetzung: `beagle-host/services/installer_script.py` priorisiert explizite VM-Metadaten (`sunshine-user/password/pin`) und nutzt danach VM-Secret-Fallback; bei fehlenden Pflichtfeldern wird ein Fehler geworfen.

## D-025: Standalone-Host-Service-Install darf nicht auf distro-spezifischem QEMU-Paketnamen haengen
- Entscheidung: `scripts/install-beagle-host-services.sh` waehlt QEMU-Paketnamen dynamisch nach verfuegbarem APT-Candidate (`qemu-kvm` -> `qemu-system-x86` -> `qemu-system`) statt hartem Debian/Ubuntu-Annahmenmix.
- Grund: Frische Server-ISO-Installationen auf Debian 12 brachen reproduzierbar beim Host-Service-Install mit "qemu-kvm has no installation candidate".
- Wirkung: Standalone-Host-Setup bleibt zwischen Debian-/Ubuntu-Familien robust reproduzierbar.

## D-026: Standalone-Provisioning braucht `xorriso` als Pflicht-Tool
- Entscheidung: `xorriso` ist verpflichtender Teil der Standalone-Host-Abhaengigkeiten und Runtime-Readiness-Pruefung.
- Grund: Ohne `xorriso` scheitert die Seed-ISO-Erzeugung im Ubuntu-Autoinstall-Flow trotz ansonsten erfolgreichem Host-Setup.
- Umsetzung: Paketliste + Readiness-Check in `scripts/install-beagle-host-services.sh` erweitert (`virsh`, `qemu-img`, `xorriso`).

## D-027: API-Reverse-Proxy fuer Provisioning auf Long-Running Calls auslegen
- Entscheidung: `proxy_read_timeout` und `proxy_send_timeout` fuer Beagle-API-Locations werden auf 900 Sekunden gesetzt.
- Grund: Laengere Provisioning-Operationen (z. B. ISO-Download/VM-Setup) liefen reproduzierbar in 504 Timeouts bei 30s Default.
- Datei: `scripts/install-beagle-proxy.sh`.

## D-028: Frischer Host muss generische Thinclient-Artefakte immer mitziehen
- Entscheidung: Host-Install zieht zusaetzlich die generischen Shell-/PowerShell-Installer-Artefakte (`pve-thin-client-live-usb*`, `pve-thin-client-usb-installer*`) als Pflichtbestandteil des Release-Downloads.
- Grund: Ohne diese Artefakte liefern VM-spezifische Wrapper-Endpunkte (`/vms/<vmid>/installer.sh`) auf frischen Hosts 503 oder unvollstaendige Payloads.
- Datei: `scripts/install-beagle-host.sh`.

## D-029: Host-Service-Installer darf in Installer-Chroot kein Live-libvirt erzwingen
- Entscheidung: `scripts/install-beagle-host-services.sh` unterscheidet zwischen live-managebarer libvirt-Systemumgebung und chroot/offline Installationskontext; runtime-nahe libvirt waits/provisioning (`wait_for_libvirt_system`, `virsh net/pool`) werden nur in live Kontexten ausgefuehrt.
- Grund: Frische Server-ISO Installationen brachen im chroot-Host-Stack-Schritt reproduzierbar mit `libvirt qemu:///system is not ready` ab, obwohl der Schritt nur Zielsystem-Datei/Service-Provisioning benoetigte.
- Wirkung: Installer kann den Host-Stack im chroot zu Ende provisionieren; Live-libvirt Initialisierung bleibt fuer den gebooteten Hostpfad erhalten.
- Datei: `scripts/install-beagle-host-services.sh`.

## D-030: Server-Installer erzwingt Onboarding-First statt Bootstrap-Admin-Autocomplete
- Entscheidung: Der Server-Installer setzt im chroot Host-Installpfad `BEAGLE_AUTH_BOOTSTRAP_DISABLE=1`, und der Onboarding-Status behandelt bootstrap-only Nutzer in diesem Modus nicht als abgeschlossenes Setup.
- Grund: Frische Host-Installationen zeigten keinen Onboarding-Dialog mehr, weil ein automatisch angelegter Bootstrap-User den Setup-Status auf `completed` setzte.
- Wirkung: Web UI zeigt nach frischer Installation wieder verlässlich den verpflichtenden Onboarding-Flow; bestehende bootstrap-only Zustände werden auf `pending` zurückgeführt, sobald Bootstrap-Auth deaktiviert ist.
- Dateien: `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`, `beagle-host/services/auth_session.py`, `beagle-host/bin/beagle-control-plane.py`.

## D-031: Streaming-Backend-Strategie: Windows-Apollo + Linux-Sunshine-vkms
- Entscheidung: Plan 11 (Streaming v2) teilt sich in zwei Pfade: (1) **Windows-Desktops nutzen Apollo** mit nativer Virtual Display (SudoVDA), HDR, Multi-Monitor; (2) **Linux-Desktops nutzen Sunshine** mit Virtual Display via DRM-vkms PoC (Standard), optional Apollo-Build aus Source (ohne Virtual Display).
- Grund: Apollo ist Windows-only für Virtual Display (`SudoVDA`-Treiber, geplant für Linux aber nicht implementiert). Linux-Desktops brauchen Virtual Display für headless Hosts (keine physischen Monitore). vkms ist im Mainline-Kernel enthalten und wird per Firstboot-Skript provisioniert.
- Konsequenz: `beagle-host/services/streaming_backend.py` wird platform-aware: `guest_os == "windows"` → Apollo (default), `guest_os == "linux"` → Sunshine + vkms. Fallback für Apollo-Fehler: Sunshine mainline. Provider-Neutralität bleibt erhalten.
- Performance-Baseline (2026-04-24, Linux): `python3 scripts/test-streaming-quality-smoke.py --host srv1.beagle-os.com --domain beagle-100` => `result=pass_with_4k_limit` (4K-Modus aktuell nicht setzbar, aber reproduzierbarer Virtual-Output + Sunshine-API funktionsfähig).
- Backend-Auswahl-Kriterien:
  1. Linux-Guest: Sunshine bevorzugt, solange `vkms`/Virtual-Output reproduzierbar ist und `sunshine_api_apps=ok` bleibt.
  2. Windows-Guest: Apollo bevorzugt, wenn SudoVDA verfügbar und HDR/Multi-Monitor-Anforderungen bestehen.
  3. Fallback-Regel: Wenn Primär-Backend nicht stabil ist (Healthchecks/Smoke fehlschlagen), auf Sunshine zurückschalten.
  4. Release-Gate: Änderungen am Default-Backend nur mit reproduzierbarem Smoke-Ergebnis und dokumentierter Entscheidung in D-031.
- Umsetzung:
  1. **Schritt 1 (2026-04)**: Sunshine mainline bleibt Default für alle VMs bis vkms-PoC validiert ist.
  2. **Schritt 2 (2026-05)**: vkms PoC auf Linux Desktop-VM validieren (resolution persistence, Moonlight compatibility).
  3. **Schritt 3 (Q1 2027)**: Apollo Build aus Source für Linux evaluieren (nur für Vergleichsmessungen, ohne Virtual Display-Features).
  4. **Schritt 4 (Q1 2027)**: Windows Guest-VM mit Apollo + SudoVDA evaluieren (Baseline für kompetitives Benchmarking).
- Testakzeptanz: Linux-Desktop streamt 3840×2160@60 (Sunshine + vkms); Windows-Desktop streamt 3840×2160@60 HDR (Apollo + SudoVDA); beide ohne Artefakte und mit Endpunkt-Moonlight-Kompatibilität.
- Dateien: `docs/gofuture/11-streaming-v2.md`, `docs/refactorv2/05-streaming-protocol-strategy.md`, `beagle-host/services/streaming_backend.py` (neu).

## D-032: Endpoint triggert Guest-Display-Prepare vor Moonlight-Stream
- Entscheidung: Vor dem Moonlight-Stream ruft der Endpoint den Manager-Hook `POST /api/v1/endpoints/moonlight/prepare-stream` auf und uebergibt die lokal erkannte Aufloesung (`WIDTHxHEIGHT`).
- Grund: Der Linux-vkms-Guest muss die Zielauflosung vor Streamstart aktiv setzen (xrandr), damit Stream-Session nicht auf statischem Fallback verbleibt.
- Umsetzung: `thin-client-assistant/runtime/launch-moonlight.sh` + `moonlight_manager_registration.sh` triggern den Hook; Backend setzt per guest-exec (`DISPLAY=:0`, `XAUTHORITY`) via `xrandr`.
- Dateien: `beagle-host/services/endpoint_http_surface.py`, `beagle-host/services/sunshine_integration.py`, `thin-client-assistant/runtime/launch-moonlight.sh`, `thin-client-assistant/runtime/moonlight_manager_registration.sh`.

## D-031: Security-Funde muessen pro Run dokumentiert und nach Moeglichkeit sofort gepatcht werden
- Entscheidung: Jeder Agent-Run muss im bearbeiteten Scope aktiv nach Security-Funden suchen; neue Funde werden in `docs/refactor/11-security-findings.md` dokumentiert und direkt mitgepatcht, wenn der Fix reproduzierbar und risikoarm ist.
- Grund: Security darf im laufenden Refactor nicht als spaetere Phase behandelt werden, sonst akkumulieren versteckte Risiken zwischen mehreren Agentenruns.

## D-032: `AGENTS.md` und `AGENTS.md` sind lokale Operator-Dateien und duerfen nicht versioniert werden
- Entscheidung: `AGENTS.md` und `AGENTS.md` bleiben lokal-only, stehen in `.gitignore` und muessen aus dem Git-Tracking entfernt werden.
- Grund: Diese Dateien koennen interne Arbeitsanweisungen oder lokale Betriebsdetails enthalten und duerfen nicht versehentlich auf GitHub landen.

## D-033: Operator-Zugriff fuer `srv1.meinzeug.cloud` laeuft lokal ueber SSH-Key alias `meinzeug`
- Entscheidung: Lokaler Remote-Zugriff auf `srv1.meinzeug.cloud` wird ueber `ssh meinzeug` mit dediziertem Key `/home/dennis/.ssh/meinzeug_ed25519` abgewickelt.
- Grund: Vereinheitlicht Operator-Zugriff im Workspace und reduziert Passwort-Nutzung im Tagesbetrieb.

## D-034: `AGENTS.md` bleibt kompakte Policy, nicht der Volltext-Refactorplan
- Entscheidung: Die lokale `AGENTS.md` wird kurz gehalten und enthaelt nur dauerhafte Arbeitsregeln, Sicherheitsvorgaben, Uebergabepflichten und lokale Operator-Hinweise.
- Grund: Die alte Mischform aus Policy, Roadmap und Dateiplatzierungsdetails war drift-anfaellig und fuer neue Agents schwerer scanbar.
- Detailplanung, Architekturfeinschnitt und Migrationsstand gehoeren stattdessen nach `docs/refactor/*`.

## D-035: Release- und Installer-Source-Bundles duerfen keine lokalen Operator-Dateien enthalten
- Entscheidung: `AGENTS.md` und `AGENTS.md` werden nicht in `beagle-os-v*.tar.gz`, server-installer embedded source bundles oder Hetzner installimage embedded source bundles aufgenommen.
- Grund: Diese Dateien sind lokale Operator-Artefakte und koennen interne Hinweise oder Zugangsdaten enthalten; sie duerfen nicht ueber GitHub, ISO oder tar.gz verteilt werden.
- Dateien: `scripts/package.sh`, `scripts/build-server-installer.sh`, `scripts/build-server-installimage.sh`.

## D-036: Runtime-Paketinstallation muss APT-Index explizit aktualisieren und darf Fehler nicht verschlucken
- Entscheidung: Standalone/Beagle-Provider Host-Service-Installationen fuehren vor Runtime-Paketinstallationen `apt-get update` aus und lassen fehlgeschlagene Pflichtinstallationen sichtbar fehlschlagen.
- Grund: Minimal-Rootfs aus Hetzner `installimage` hat keine zuverlaessigen APT-Listen; ein still geschluckter Installationsfehler fuehrte zu fehlendem `virsh` und gebrochenem Firstboot.
- Datei: `scripts/install-beagle-host-services.sh`.

## D-037: KVM-only Provisioning ist an Bare-Metal-Hostfaehigkeit gebunden
- Entscheidung: Wenn Beagle im KVM-only Modus betrieben wird, ist ein echter Bare-Metal-Host verpflichtend; virtuelle/vServer-Hosts ohne `/dev/kvm` gelten als nicht konforme Zielplattform fuer produktive Provisioning-Pfade.
- Grund: Auf virtualisierten Hosts ohne nested KVM scheitert libvirt-domain define/start reproduzierbar mit `Emulator ... does not support virt type 'kvm'`.
- Betriebsfolge:
	- install/acceptance runbooks muessen KVM-Preflight enthalten (`/dev/kvm`, `virsh domcapabilities --virttype kvm`),
	- bei negativem Preflight ist der Host vor produktiver Nutzung als KVM-Provider abzulehnen statt implizit auf langsame Software-Emulation auszuweichen.

## D-038: Let's Encrypt wird aus dem Security-Handler ueber transienten systemd-Run ausgefuehrt
- Entscheidung: `beagle-host/services/server_settings.py` fuehrt `certbot` fuer die Security/TLS-WebUI bevorzugt ueber `systemd-run --wait --pipe --collect --service-type=exec` aus, statt direkt im `beagle-control-plane.service` Prozess.
- Grund: Der gehaertete Control-Plane-Service laeuft mit `ProtectSystem=strict`; direkter `certbot --nginx` Aufruf scheiterte reproduzierbar an Let's-Encrypt- und nginx-Logpfaden, obwohl die benoetigten Pakete installiert waren.
- Wirkung: Die WebUI-TLS-Funktion bleibt mit der bestehenden Service-Haertung kompatibel, ohne die gesamte Control Plane unspezifisch zu entschaerfen.
- Dateien: `beagle-host/services/server_settings.py`, `beagle-host/systemd/beagle-control-plane.service`.

## D-039: Cluster-Store fuer 7.0 ist etcd mit Witness; SQLite+Litestream bleibt DR-Option
- Entscheidung: Plan-07 Cluster-Foundation nutzt etcd als autoritativen Cluster-Store mit nativer Leader-Election; fuer Zwei-Host-Betrieb wird ein dritter Witness eingeplant.
- Grund: Der PoC unter `providers/beagle/cluster/` hat reproduzierbar Leader-Wechsel mit etcd gezeigt (`ETCD_POC_RESULT=PASS` auf `srv1.beagle-os.com`). SQLite+Litestream reduziert zwar den Footprint, bietet aber keine eingebaute Leader-Election-Authority.
- Konsequenz:
  1. Inter-Host-RPC/Join-Flows in Plan 07 Schritt 2 bauen auf etcd-Clusterzustand auf.
  2. SQLite+Litestream wird optional als Replikations-/DR-Baustein betrachtet, nicht als primarer Konsistenz-/Leader-Layer.
- Dateien: `providers/beagle/cluster/store_poc.py`, `providers/beagle/cluster/run_etcd_cluster_poc.sh`, `providers/beagle/cluster/README.md`, `docs/gofuture/07-cluster-foundation.md`.

## D-040: Cluster-Interconnect nutzt mTLS mit lokaler Cluster-CA und node-signierten Zertifikaten
- Entscheidung: Inter-Host-RPC fuer Plan 07 laeuft ueber eine mTLS-geschuetzte JSON-RPC-Surface; jede Cluster-Verbindung verlangt ein von der Cluster-CA signiertes Node-Zertifikat.
- Grund: Der neue Cluster-RPC-Smoke konnte lokal und auf `srv1.beagle-os.com` reproduzierbar einen gegenseitig authentifizierten TLS-Handshake zwischen zwei Nodes nachweisen (`CLUSTER_RPC_SMOKE=PASS`).

## D-041: Installer-Cluster-Join-Ziele liegen in separater Secret-Datei statt in breit konsumierten Env-Dateien

## D-042: Backup-Basis fuer 7.3 ist qcow2-export + Restic-Dedupe; ZFS bleibt optionales Backend
- Entscheidung: Fuer 7.3 wird Backup auf Beagle-Hosts primär als `qemu-img convert`-Export von qcow2-Diskständen plus Restic-Repository-Deduplikation umgesetzt.
- Entscheidung: ZFS-Snapshots bleiben ein optionaler Fast-Path auf Hosts mit ZFS, sind aber nicht mehr harte Voraussetzung der Backup-Architektur.
- Entscheidung: PBS-Kompatibilität wird über Export-/Import-Adapter und Snapshot-Metadaten vorgesehen, nicht über direkte Beagle host-Abhängigkeiten.
- Grund: Der Ansatz funktioniert provider-neutral auf Nicht-ZFS-Hosts, nutzt existierende QEMU-Tools und reduziert Storage-Bedarf über content-addressed Dedupe.
- Validierung: reproduzierbarer PoC `scripts/test-backup-qcow2-restic-poc.sh` zeigt auf Runtime deduplizierte zweite Sicherung (`BACKUP_QCOW2_RESTIC_POC=PASS`).
- Entscheidung: Der Server-Installer schreibt Join-Wunsch und Join-Ziel fuer neue Cluster-Nodes in eine dedizierte Datei `/etc/beagle/cluster-join.env` mit Modus `0600`; allgemeine Runtime-Env-Dateien enthalten nur das Flag und den Dateipfad.
- Grund: Join-Token oder Leader-Ziele koennen sensitiv sein. `host.env` und Proxy-nahe Env-Dateien werden von mehreren Scripts/Units gelesen und sind deshalb der falsche Ort fuer solche Daten.
- Wirkung: Der neue Installer-Dialog aus Plan 07 Schritt 5 bleibt fuer spaetere Join-Orchestrierung nutzbar, ohne den Token breit ueber Runtime-Glue oder Logs zu verteilen.
- Dateien: `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`, `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer-gui`, `scripts/install-beagle-host.sh`, `scripts/install-beagle-host-postinstall.sh`, `scripts/install-beagle-host-services.sh`.
- Detail:
  1. `beagle-host/services/ca_manager.py` besitzt die CA und signiert Join-Zertifikate fuer Nodes.
  2. `beagle-host/services/cluster_rpc.py` erzwingt `CERT_REQUIRED`, TLS >= 1.2 und ALPN fuer `h2`/`http/1.1`.
  3. SANs (`DNS:`/`IP:`) werden bei Node-Zertifikaten explizit mit ausgestellt.
- Konsequenz: Cluster-Join, Remote-Inventory und spaetere Migrations-/Maintenance-RPCs verwenden keine shared secrets als Primarauthentisierung, sondern CA-vertrauensbasierte Node-Identitaeten.
- Dateien: `beagle-host/services/ca_manager.py`, `beagle-host/services/cluster_rpc.py`, `tests/unit/test_ca_manager.py`, `tests/unit/test_cluster_rpc.py`, `scripts/test-cluster-rpc-smoke.py`.

## D-043: WebUI-Bedienbarkeit ist Abschlusskriterium fuer GoFuture-Operator-Flows

- Entscheidung: Ein GoFuture-Schritt mit Operator-Bezug gilt nicht mehr als abgeschlossen, wenn nur API, CLI, Statusanzeige oder Rohdaten-Tabelle existieren.
- Entscheidung: Abschluss erfordert einen bedienbaren WebUI-Flow mit Validierung, sichtbarem Fortschritt/Job-Status, Fehlerdetails, sicherer Bestaetigung fuer riskante Aktionen und dokumentiertem Testpfad.
- Grund: Die Beagle Web Console ist die einzige Operator-Oberflaeche. Cluster, Virtualization, Policies, IAM und Audit muessen dort nicht nur sichtbar, sondern vollstaendig editierbar und betrieblich nutzbar sein.
- Konsequenz: `docs/gofuture/00-index.md` fuehrt aktive Re-Open-Punkte fuer `/#panel=cluster`, `/#panel=virtualization`, `/#panel=policies`, `/#panel=iam` und `/#panel=audit`.
- Konsequenz: Statusanzeigen alleine sind explizit unzureichend; UI-Buttons duerfen erst als erledigt gelten, wenn ein echter Backend-Pfad, RBAC, Fehlerzustand und Regressionstest existieren.
- Dateien: `docs/gofuture/00-index.md`, `docs/gofuture/07-cluster-foundation.md`, `docs/gofuture/08-storage-plane.md`, `docs/gofuture/10-vdi-pools.md`, `docs/gofuture/13-iam-tenancy.md`, `docs/gofuture/15-audit-compliance.md`.

## D-044: Cluster Auto-Join nutzt Zielserver-Setup-Code statt offener Remote-Probes

- Entscheidung: Der Standardpfad zum Hinzufuegen eines Servers ist Hostname + kurzlebiger Setup-Code, den der Zielserver nach Login erzeugt.
- Entscheidung: Der Leader fragt keine unauthentifizierten Detail-Endpunkte wie `/api/v1/health` oder Inventory auf dem Zielserver ab.
- Entscheidung: Setup-Codes werden auf dem Zielserver nur gehasht gespeichert, sind einmalig nutzbar, laufen kurzlebig ab und werden nicht in Audit-Events geschrieben.
- Entscheidung: Join-Tokens besitzen eine echte serverseitige Ablaufpruefung und werden beim Einloesen als used markiert.
- Grund: Ein Cluster-Wizard darf keine offen aus dem Internet auslesbaren Serverinformationen voraussetzen. Der Betreiber muss den Zielserver bewusst in dessen WebUI vorbereiten, bevor ein Leader ihn verbinden kann.
- Konsequenz: `POST /api/v1/cluster/setup-code` ist authentifiziert, `POST /api/v1/cluster/join-with-setup-code` ist nur setup-code-geschuetzt und darf keine Secrets auditieren.
- Dateien: `beagle-host/services/cluster_membership.py`, `beagle-host/services/cluster_http_surface.py`, `beagle-host/services/control_plane_handler.py`, `website/ui/cluster.js`, `website/index.html`.

## D-045: Cluster-Liveness darf nicht an oeffentlicher TLS-Vertrauenskette haengen

- Entscheidung: Der reine Peer-Liveness-Probe (`healthz`) fuer Cluster-Member validiert nicht die oeffentliche Browser-CA-Kette, wenn `api_url` auf eine HTTPS-WebUI-URL zeigt.
- Grund: Der Cluster-Zustand darf nicht durch ein zeitweilig unvollstaendiges Public-Certificate-Setup auf `srv1`/`srv2` auf `unreachable` kippen, solange der Host selbst ueber die konfigurierte Peer-URL erreichbar ist.
- Begrenzung:
  1. Die Ausnahme gilt nur fuer den unauthentifizierten Liveness-Probe.
  2. Privilegierte Cluster-RPCs bleiben weiter am mTLS-Cluster-CA-Modell haengen.
- Dateien: `beagle-host/services/cluster_membership.py`.

## D-046: Downloadbare Installer-Skripte nutzen scoped Log-Tokens statt Operator-Credentials

- Entscheidung: VM-spezifisch generierte USB-Installer-/Live-Skripte duerfen keine Admin-, Session- oder Manager-Tokens enthalten. Fuer Laufprotokolle wird pro Skript ein kurzlebiger HMAC-signierter write-only Token mit Scope `installer-log:write` erzeugt.
- Entscheidung: Der Token darf nur `POST /api/v1/public/installer-logs` schreiben; Lesen der Logs bleibt authentifiziert und benoetigt `settings:read`.
- Entscheidung: Logging ist non-blocking. Ein nicht erreichbarer Log-Endpoint darf keine Provisionierung abbrechen; echte Skriptfehler werden trotzdem ueber `ERR`/PowerShell-`trap` protokolliert, wenn der Endpoint erreichbar ist.
- Grund: Operatoren muessen nachweisen koennen, was heruntergeladene Installer-Skripte getan haben, ohne den Sicherheitsumfang der Skripte auf volle API-Berechtigungen zu erweitern.
- Konsequenz: Alte Hosted-Templates ohne Log-Defaults werden beim Patchen self-healing ergaenzt, damit Download-Drift keinen `500` erzeugt.
- Dateien: `beagle-host/services/installer_log_service.py`, `beagle-host/services/installer_script.py`, `beagle-host/services/installer_template_patch.py`, `thin-client-assistant/usb/pve-thin-client-usb-installer.sh`, `thin-client-assistant/usb/pve-thin-client-usb-installer.ps1`.

## D-047: Hosted Artifact-Veröffentlichung ist exklusiv gelockt

- Entscheidung: Prozesse, die Host-Download-Artefakte schreiben (`package.sh`, `prepare-host-downloads.sh`), muessen denselben Lock halten.
- Grund: Repo-Auto-Update, Artifact-Refresh und manuelle Refreshes koennen sonst ISO/Payload/Status-JSON parallel schreiben; dadurch entstehen kurzzeitig falsche Checksummen und stale Download-Indizes.
- Konsequenz: `prepare-host-downloads.sh` haelt den Lock auch waehrend eines internen `package.sh`-Laufs. Direkte `package.sh`-Aufrufe nehmen denselben Lock selbst.
- Konsequenz: Alte versionierte Thin-Client-Download-Artefakte werden beim Veroeffentlichen entfernt, damit oeffentliche Download-Indizes keine alten `v6.x`-Launcher mit veralteten URLs weiter anbieten.
- Dateien: `scripts/lib/artifact_lock.sh`, `scripts/package.sh`, `scripts/prepare-host-downloads.sh`, `scripts/check-beagle-host.sh`.

## D-048: Release-Assets duerfen keine kollidierenden Basenames haben

- Entscheidung: Das Release-Workflow-Assetset darf keine zwei Dateien mit demselben Basename hochladen.
- Grund: GitHub Release Assets werden anhand des Asset-Namens verwaltet; `dist/SHA256SUMS` und `dist/sbom/SHA256SUMS` kollidieren als `SHA256SUMS` und koennen den finalen Release-Job fehlschlagen lassen.
- Konsequenz: Die SBOM-interne `SHA256SUMS` bleibt im Workflow-Artefakt, wird aber nicht als separates Release-Asset hochgeladen. Die root `dist/SHA256SUMS` bleibt das veroeffentlichte Checksummen-Manifest.
- Dateien: `.github/workflows/release.yml`.

## D-049: GoRelease ist Freigabe-Gate, GoEnterprise bleibt Architekturquelle

- Entscheidung: `docs/goenterprise/` wird nicht durch Security-/Release-Gates ersetzt, weil dort weiterhin beschrieben ist, wie Enterprise-Funktionen gebaut sind.
- Entscheidung: Firmenfreigabe, Security-GA, Hardware-Abnahme und Release-Prozess liegen ab sofort in `docs/gorelease/`.
- Grund: Feature-Fertigstellung und Unternehmensfreigabe sind unterschiedliche Ebenen. Eine Funktion kann gebaut sein, ohne fuer produktive Firmenumgebungen freigegeben zu sein.
- Konsequenz: Vor jeder Aussage wie "firmentauglich", "Enterprise Candidate" oder "Enterprise GA" muessen die passenden GoRelease-Gates geprueft werden.
- Konsequenz: Hardware wird kostenbewusst gebucht: kleine 2-4 Core Hetzner VMs fuer Dauer-Smokes, dedizierte CPU-Hosts fuer KVM/Bare-Metal und kurzzeitig gemietete GPU-Server nur fuer GPU-Gates.
- Dateien: `docs/gorelease/00-index.md`, `docs/gorelease/01-security-gates.md`, `docs/gorelease/02-hardware-test-matrix.md`, `docs/gorelease/03-end-to-end-validation.md`, `docs/gorelease/04-release-pipeline.md`, `docs/gorelease/05-operations-compliance.md`.

## D-050: Host-Firewall ist Beagle-Guard-Baseline, nicht UFW

- Entscheidung: Frische und aktualisierte Beagle-Server aktivieren eine eigene nftables-Tabelle `inet beagle_guard` als Default-Drop-Baseline.
- Entscheidung: Die Baseline wird additiv geladen und darf libvirt-/Stream-Reconciler-Tabellen nicht per `flush ruleset` entfernen.
- Entscheidung: WebUI-Settings fuer Firewall sprechen die Beagle-nftables-Baseline an; UFW ist kein Runtime-Backend mehr.
- Grund: Der Server muss von Beginn an geschuetzt sein und VM-Regeln duerfen dynamisch erweitert werden, ohne SSH/WebUI, libvirt NAT oder explizite Stream-DNATs zu zerstoeren.
- Konsequenz: `22/80/443` sind die einzigen allgemeinen Public-Host-Ports. `9088/9089` sind nur lokal, von VM-Bridges oder konfigurierten/erkannten Cluster-Peers erlaubt. VM-Forwarding ist Bridge-Egress oder explizit DNAT-getriggert.
- Dateien: `scripts/apply-beagle-firewall.sh`, `scripts/install-beagle-host-services.sh`, `scripts/check-beagle-host.sh`, `beagle-host/services/server_settings.py`, `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-live-server-bootstrap`, `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`.

## D-051: Produktive Beagle-Hosts hosten nur Endpoint-Artefakte lokal

- Entscheidung: Produktive Beagle-Hosts (`srv1`/`srv2`) bauen und validieren unter `/beagle-downloads` nur endpoint-/thin-client-bezogene Artefakte.
- Entscheidung: `beagle-os-server-installer-amd64.iso` und `Debian-1201-bookworm-amd64-beagle-server.tar.gz` bleiben Public-Release-Artefakte und sind nicht Teil des lokalen Host-Refresh-/Watchdog-/Health-Pfads.
- Grund: Die beiden Server-Release-Dateien sind gross, fuer die Runtime des Beagle-Hosts selbst nicht notwendig und verlaengern lokale Artefakt-Refreshes unnoetig. Die getrennte Bereitstellung auf der Public-Website reicht fuer Server-Installationsfaelle aus.
- Konsequenz: `prepare-host-downloads.sh`, `artifact-watchdog.sh`, `check-beagle-host.sh`, `install-beagle-host.sh` und die WebUI-Artefaktpruefung behandeln diese Dateien auf laufenden Hosts nicht mehr als Pflicht. Fuer echte Release-/Public-Publish-Laeufe bleibt der Buildpfad weiter ueber `package.sh` mit aktivierten Server-Release-Artefakten verfuegbar.
- Dateien: `scripts/package.sh`, `scripts/prepare-host-downloads.sh`, `scripts/check-beagle-host.sh`, `scripts/artifact-watchdog.sh`, `scripts/install-beagle-host.sh`, `scripts/lib/prepare_host_downloads.py`, `beagle-host/services/server_settings.py`.

## 2026-04-26 - Cluster Leave und Virtualization Overview bleiben leader-/cluster-autoritativ

- Ein Cluster-Mitglied darf seinen lokalen Cluster-State loeschen, aber nicht den Leader-State still implizit veraendern.
- Deshalb laeuft Member-Leave jetzt in zwei Phasen:
  1. Das Mitglied fordert `leave-local` an.
  2. Der Leader entfernt den Member autoritativ ueber den mTLS-RPC-Pfad `cluster.member.leave`.
  3. Erst danach wird lokal aufgeraeumt.
- `GET /api/v1/virtualization/overview` bleibt die Datenquelle fuer die Virtualization-WebUI, wird aber nicht mehr host-lokal interpretiert. Der Endpoint liest bevorzugt die clusterweit aggregierte Inventory, damit die WebUI auf jedem Host denselben Clusterstand zeigt.

## D-052: Public Website folgt SemVer-Release und verwendet Beagle-eigene Wallpapers

- Entscheidung: Die oeffentliche Website zeigt Release-Versionen als SemVer-Tag wie `v8.0.0`; harte `v8.0`-/`8.0`-Checks werden durch `VERSION`-basierte Workflow-Pruefungen ersetzt.
- Entscheidung: Das GTA-/Cyberpunk-inspirierte Website-Design nutzt ausschliesslich eigene Beagle-OS-Assets, konkret das vorhandene `beagleos-gaming.png` aus dem Kiosk-/Runtime-Bestand.
- Entscheidung: Der Release-Workflow veroeffentlicht nach Artefakt-Mirror-Pruefung auch die Public-Website und validiert live HTML, CSS und Wallpaper-Asset.
- Entscheidung: Alte Public-Site-Dokumentationspfade fuer entfernte Provider-Varianten werden nicht mehr als statische Seiten ausgeliefert.
- Grund: GitHub, Website und Release-Artefakte muessen dieselbe aktuelle Version zeigen, ohne manuelle Nacharbeit auf dem Plesk-/SaaS-Server.
- Konsequenz: Website-Smokes duerfen Wallpaper-Referenzen nicht im HTML erwarten, wenn sie korrekt aus CSS geladen werden; die Workflows pruefen daher `/styles.css` und die direkte Bild-URL.
- Dateien: `VERSION`, `.github/workflows/release.yml`, `.github/workflows/public-website.yml`, `public-site/index.html`, `public-site/styles.css`, `public-site/assets/img/beagleos-gaming.png`.

## D-053: Copilot-Autofix-PRs duerfen automatisch ready/approved/merged werden

- Entscheidung: Copilot-Autofix-PRs sind technische CI-Fix-PRs und duerfen durch den Automerge-Workflow aus Draft geholt, fuer pausierte Workflow-Runs approved und nach gruenen Checks automatisch gemerged werden.
- Entscheidung: Neue Autofix-Issues werden pro Workflow/Branch dedupliziert; Folgefehler kommentieren das bestehende Issue statt neue parallele Copilot-Aufgaben zu erzeugen.
- Entscheidung: Autofix-Issues werden automatisch geschlossen, wenn der betroffene Workflow auf `main` oder einem Release-Tag wieder erfolgreich laeuft.
- Grund: GitHub erzeugt Copilot-Coding-Agent-PRs haeufig als Draft und PR-Workflow-Runs koennen auf `action_required` stehen. Ohne automatisches Ready/Approval koennen auch mergebare PRs nicht in den Merge-Pfad gelangen.
- Konsequenz: Der Automerge-Workflow nutzt bevorzugt `COPILOT_ASSIGNMENT_TOKEN`, faellt aber auf `GITHUB_TOKEN` zurueck. Branch-Protection oder fehlende Token-Rechte bleiben harte externe Blocker.
- Dateien: `.github/workflows/copilot-automerge.yml`, `scripts/approve-copilot-pr-workflow-run.sh`, `scripts/close-resolved-copilot-autofix-issues.sh`, `scripts/create-copilot-autofix-issue.sh`, `scripts/merge-copilot-autofix-pr.sh`.
## BeagleStream-Forks unter `meinzeug/*` statt `beagle-os/*` (2026-05-01)

Die Plan-Dokumente referenzierten eine GitHub-Organisation `beagle-os`, die real nicht existiert. Die echten Fork-Repositories fuer Phase A wurden deshalb unter dem real verfuegbaren Owner `meinzeug` angelegt:

- `meinzeug/beagle-stream-server`
- `meinzeug/beagle-stream-client`

Die Fork-Implementierung arbeitet ab jetzt gegen diese beiden Repositories. Doku und Checklisten muessen denselben Zielort verwenden, damit Folge-Runs keine tote Remote referenzieren.

## BeagleStream Phase A: Token-als-PIN (2026-05-01)

- Entscheidung: `BeagleAuth` nutzt `nvhttp::pin()` aus Sunshine unveraendert.
- Entscheidung: Der HMAC-Pairing-Token aus dem Broker wird als PIN-String uebergeben.
- Grund: Das Moonlight-/GFE-Protokoll bleibt unveraendert; es gibt keinen neuen Pairing-Handshake und keinen Breaking Change.
- Konsequenz: Vanilla-Moonlight-Clients bleiben kompatibel, waehrend BeagleStream-Clients den Broker-Token vorausgefuellt an den bestehenden Pairing-Pfad senden.
- Repos: `meinzeug/beagle-stream-server`, `meinzeug/beagle-stream-client`, jeweils Branch `beagle/phase-a`.

## BeagleStream Thin-Client bleibt hostless nur bei Enrollment (2026-05-02)

- Entscheidung: Thin-Clients starten `beagle-stream stream "<App>"` nur, wenn kein statischer `PVE_THIN_CLIENT_MOONLIGHT_HOST` gesetzt ist und `/etc/beagle/enrollment.conf` die Felder `control_plane`, `enrollment_token`, `device_id` und `pool_id` enthaelt.
- Entscheidung: Der Thin-Client-Build versucht standardmaessig das mutable BeagleStream-Client-Release `https://github.com/meinzeug/beagle-stream-client/releases/download/beagle-phase-a/BeagleStream-latest-x86_64.AppImage`, kann per `PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_URL`/`BEAGLE_STREAM_CLIENT_URL` ueberschrieben werden und faellt bei Downloadfehlern auf das bestehende upstream Moonlight-AppImage zurueck.
- Grund: Bestehende Installationen mit statischem Moonlight-Ziel duerfen nicht brechen, waehrend neue BeagleStream-Endpunkte Broker-Allocate, WireGuard und Token-Pairing im Client-Fork ausfuehren.
- Konsequenz: Ohne gebundelten `beagle-stream` meldet der Endpoint-Healthcheck im hostless Enrollment-Modus einen klaren Health-Failure statt still auf den alten Moonlight-Pfad mit falscher CLI-Signatur zu fallen.
- Dateien: `scripts/build-thin-client-installer.sh`, `thin-client-assistant/runtime/moonlight_runtime_exec.sh`, `thin-client-assistant/runtime/launch-moonlight.sh`, `thin-client-assistant/runtime/launch-session.sh`, `beagle-os/overlay/usr/local/sbin/beagle-healthcheck`.

## BeagleStream Server-Paket ersetzt Sunshine nur mit Fallback (2026-05-02)

- Entscheidung: VM-Guest-Prep und Ubuntu-Beagle-Firstboot versuchen zuerst das mutable Server-Fork-Release `https://github.com/meinzeug/beagle-stream-server/releases/download/beagle-phase-a/beagle-stream-server-latest-ubuntu-24.04-amd64.deb`.
- Entscheidung: Wenn dieses Paket noch nicht verfuegbar ist oder der Download fehlschlaegt, wird weiter das bekannte upstream Sunshine `.deb` installiert.
- Grund: Neue VMs sollen reproduzierbar auf den eigenen BeagleStream-Server wechseln, ohne VM-Provisioning komplett zu blockieren, solange die Server-Fork-Release-Pipeline noch laeuft.
- Konsequenz: Service-/Metadaten-Namen bleiben vorerst kompatibel (`beagle-sunshine.service`, Sunshine API), waehrend das installierte Binary/Paket aus dem BeagleStream-Fork kommen kann.
- Dateien: `scripts/configure-sunshine-guest.sh`, `beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl`, `beagle-host/services/service_registry.py`, `beagle-host/services/ubuntu_beagle_provisioning.py`.
