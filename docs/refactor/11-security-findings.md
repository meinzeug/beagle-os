# Security Findings

Stand: 2026-04-30 (ergänzt: S-038 Ubuntu-Desktop-Firstboot-Drift repariert, S-037 TLS-Reload-Disconnect-Drift repariert, S-036 TLS-Switch-Permission-Drift repariert, S-035 Reinstall-Auth-/Onboarding-Drift korrigiert)

## S-038 — Unterbrochene Ubuntu-Firstboot-Paketketten konnten Desktop-VMs ohne finalen Reboot und ohne vollständiges Session-Setup hinterlassen (PATCHED)

- Status: **gepatcht** (2026-04-30)
- Risiko: **Mittel**
- Betroffene Dateien:
  - `beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl`
  - `tests/unit/test_ubuntu_beagle_firstboot_regressions.py`
- Beschreibung:
  - Frisch per WebUI provisionierte Ubuntu-Desktop-VMs konnten im Guest-Firstboot in einem halbfertigen `apt/dpkg`-Zustand steckenbleiben, insbesondere in der X11-/LightDM-Kette.
  - Dadurch liefen nicht nur Guest-Reboot und Desktop-Login kaputt; es blieben auch nachgelagerte Guest-Initialisierungsschritte aus, die fuer einen konsistenten, gehärteten Desktop-Zielzustand vorgesehen sind.
- Fix:
  - Das Firstboot-Template heilt unterbrochene Paketzustände jetzt vor jedem `apt`-Versuch, nach erfolgreichen Läufen und nach jeder kritischen Desktop-Installationsphase explizit über `dpkg --audit`, `dpkg --configure -a` und `apt-get install -f -y`.
  - Regressionen fixieren diese Heilungslogik am Template.
- Live-Verifikation:
  - `srv1`/VM100: der festhängende `libxklavier16`-/`lightdm-gtk-greeter`-Pfad wurde identifiziert; der Repo-Fix ist auf dem Host ausgerollt und der laufende Gast wurde gegen denselben Fehlerpfad repariert.

## S-037 — nginx/TLS-Reloads konnten in-flight API-Requests als 500/Broken-Pipe-Fehler eskalieren lassen (PATCHED)

- Status: **gepatcht** (2026-04-30)
- Risiko: **Mittel bis Hoch**
- Betroffene Dateien:
  - `beagle-host/services/request_handler_mixin.py`
  - `beagle-host/services/control_plane_handler.py`
  - `website/ui/api.js`
  - `website/ui/settings.js`
  - `tests/unit/test_request_handler_mixin_client_addr.py`
  - `tests/unit/test_api_js_regressions.py`
- Beschreibung:
  - Nach erfolgreichem Let's-Encrypt-POST schloss nginx beim TLS-Reload einzelne in-flight Upstream-Verbindungen. Die Control Plane behandelte diese normalen Client-Disconnects als unhandled Fehler (`BrokenPipeError`) und produzierte dafuer 500-Logpfade.
  - Parallel hatte die WebUI fuer idempotente GET-Reads keinen gezielten Kurz-Retry gegen genau diesen Reload-Moment; dadurch konnten Panels und Session-Refreshes in vermeidbare Timeouts laufen.
- Fix:
  - Client-Disconnects (`BrokenPipeError`, `ConnectionResetError`, `EPIPE`, `ECONNRESET`) werden serverseitig jetzt explizit als normale Verbindungsabbrueche behandelt.
  - Der WebUI-Request-Layer retryt idempotente `GET`/`HEAD`-Requests einmal fuer transiente Netzwerk-/Abort-Fehler.
  - Der Security-UI-Flow wartet nach erfolgreichem LE-POST kurz vor dem ersten TLS-Status-Refresh.
- Live-Verifikation:
  - `srv1`: frueh abgebrochener Request gegen `GET /api/v1/auth/providers` erzeugt keinen neuen `BrokenPipeError`-/500-Trace mehr.
  - Externer Read `GET /beagle-api/api/v1/auth/providers` antwortet wieder stabil mit `HTTP 200`.
  - die vormals betroffenen Dashboard-/Auth-Endpunkte erscheinen danach im Journal wieder mit `api.response status=200`.

## S-036 — WebUI-Let's-Encrypt konnte Zertifikate ausstellen, aber den aktiven TLS-Pfad nicht umschalten (PATCHED)

- Status: **gepatcht** (2026-04-30)
- Risiko: **Hoch**
- Betroffene Dateien:
  - `scripts/install-beagle-proxy.sh`
  - `beagle-host/services/server_settings.py`
  - `tests/unit/test_server_settings.py`
  - `tests/unit/test_proxy_env_precedence_regressions.py`
- Beschreibung:
  - Die Security-WebUI konnte ueber Certbot bereits ein gueltiges Zertifikat ausstellen, scheiterte aber beim anschliessenden Umschalten der aktiven nginx-/Beagle-TLS-Dateien unter `/etc/beagle/tls`.
  - Root Cause 1: `scripts/install-beagle-proxy.sh` legte das Verzeichnis implizit als `root:root 0700` an; der produktive non-root-Dienst `beagle-control-plane` konnte den Zielpfad deshalb nicht traversieren oder beschreiben.
  - Root Cause 2: der Switch-Pfad in `server_settings.py` ueberschrieb bestehende PEM-Dateien direkt, statt sie atomar zu ersetzen; damit blieb der Pfad zusaetzlich fragil gegen Legacy-Datei-Owner-Drift.
- Fix:
  - Proxy-Installer heilt `/etc/beagle/tls` jetzt bei jedem Lauf reproduzierbar auf `beagle-manager:beagle-manager` mit Modus `0750`.
  - Der Let's-Encrypt-Switch ersetzt Zertifikat und Key jetzt atomar per Temp-Datei + `os.replace`.
  - Regressionen decken sowohl die TLS-Dir-Permissions als auch den atomaren Switch-Pfad ab.
- Live-Verifikation:
  - `srv1`: `/etc/beagle/tls` -> `beagle-manager:beagle-manager 0750`.
  - Direkter Host-Test von `_switch_nginx_tls_to_letsencrypt("srv1.beagle-os.com")` -> `ok=True`.
  - `nginx` und `beagle-control-plane` bleiben dabei `active`.

## S-035 — Frische Server-Neuinstallationen konnten alten Auth-State und Bootstrap-Drift weitertragen (PATCHED)

- Status: **gepatcht** (2026-04-30)
- Risiko: **Hoch**
- Betroffene Dateien:
  - `scripts/install-beagle-host-services.sh`
  - `scripts/install-beagle-host.sh`
  - `scripts/install-beagle-host-postinstall.sh`
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
  - `server-installer/installimage/usr/local/bin/beagle-installimage-bootstrap`
  - `tests/unit/test_install_beagle_host_services_regressions.py`
- Beschreibung:
  - Nach einer Neuinstallation konnte ein Host in zwei fehlerhafte Sicherheitszustaende geraten:
    - `beagle-control-plane` startete nicht, weil der neue Secret-Store-Pfad `/var/lib/beagle/secrets` fuer den non-root-Service-User nicht vorbereitet war.
    - frische Installationen bzw. spaetere Service-Re-Runs konnten alten Auth-State oder einen falschen Bootstrap-Modus weitertragen; dadurch erschien das WebUI-Onboarding nicht mehr, obwohl ein frischer Setup-Zustand erwartet wurde.
  - Besonders kritisch war der zweite Teil: ein alter `admin`-State oder ein erneut aktivierter Bootstrap-Login konterkariert die Erwartung einer sauberen Ersteinrichtung.
- Fix:
  - Host-Service-Installer legt den Secret-Store-Pfad jetzt reproduzierbar mit restriktiven Rechten fuer `beagle-manager` an.
  - Frische Server-Installationen setzen `BEAGLE_AUTH_RESET_ON_INSTALL=1` und verwerfen alten Auth-State explizit.
  - Spaetere Re-Runs des Host-Service-Installers konservieren einen vorhandenen `BEAGLE_AUTH_BOOTSTRAP_DISABLE`-Zustand und loeschen stale Bootstrap-Passwoerter, statt den Host still in einen anderen Auth-Modus zu drehen.
- Live-Verifikation:
  - `srv1`: `beagle-control-plane` startet wieder stabil.
  - Public API: `/beagle-api/api/v1/auth/onboarding/status` -> `200` mit `{pending: true, completed: false}`.
  - Browser-Smoke: sichtbares Onboarding-Modal `Beagle Server Onboarding`.

## S-034 — Thinclients konnten trotz `vpn_required`/WireGuard-Bausteinen weiterhin direkt ins Internet streamen (PATCHED)

- Status: **gepatcht** (2026-04-29)
- Risiko: **Hoch**
- Betroffene Dateien:
  - `beagle-host/services/service_registry.py`
  - `beagle-host/services/endpoint_lifecycle_surface.py`
  - `beagle-host/services/wireguard_mesh_service.py`
  - `thin-client-assistant/runtime/enrollment_wireguard.sh`
  - `thin-client-assistant/runtime/runtime_endpoint_enrollment.sh`
  - `thin-client-assistant/runtime/prepare-runtime.sh`
  - `scripts/apply-beagle-wireguard.sh`
  - `scripts/apply-beagle-firewall.sh`
  - `scripts/install-beagle-host-services.sh`
  - `thin-client-assistant/live-build/config/package-lists/pve-thin-client.list.chroot`
  - `thin-client-assistant/live-build/config/hooks/live/011-verify-runtime-deps.hook.chroot`
  - `beagle-host/systemd/beagle-wireguard-reconcile.service`
  - `beagle-host/systemd/beagle-wireguard-reconcile.path`
- Beschreibung:
  - Ein echter Thinclient lief live noch mit `connection_method=direct` bzw. spaeter trotz umgestellter Config ohne funktionierenden Tunnel weiter ueber das lokale Default-Gateway.
  - Ursachen waren kombiniert:
    - kein vollstaendiger endpoint-authentifizierter `vpn/register`-Pfad im produktiven Control-Plane-Slice,
    - Thinclient-Image ohne garantierte WireGuard-/`jq`-Runtime-Abhaengigkeiten,
    - fragiler `wg-quick`-/DNS-Helfer-Pfad auf Debian-Live-Systemen,
    - Server uebernahm neu registrierte Peers nicht automatisch in die laufende `wg-beagle`-Konfiguration,
    - Host-Firewall/WireGuard-Port mussten im aktuellen Repo-Slice noch explizit nachgezogen werden.
- Fix:
  - Control Plane liefert jetzt WireGuard-Bootstrap und endpoint-authentifizierte Peer-Registrierung.
  - Thinclient-Enroll setzt den Tunnel ohne `wg-quick` direkt mit `wg`/`ip` auf und faellt bei DNS-Helfer-Problemen deterministisch zurueck.
  - Thinclient-Live-Images enthalten WireGuard-/`jq`-Abhaengigkeiten reproduzierbar; der Build prueft diese Abhaengigkeiten hart.
  - `srv1` rendert registrierte Mesh-Peers jetzt automatisiert per Root-Reconcile in `wg-beagle`.
  - Host-Firewall erlaubt UDP `51820` und Forwarding fuer das WireGuard-Interface standardmaessig.
- Live-Verifikation:
  - Thinclient `192.168.178.92`: `wg show beagle-egress` meldet `latest handshake`, Traffic-Zaehler und Route zu `1.1.1.1` ueber `beagle-egress`.
  - `srv1`: `wg show wg-beagle` enthaelt den Thinclient-Peer mit `latest handshake`; nftables-Basis ist aktiv.

## S-033 — Public-Streams-Service entzog sich fuer eigene Root-Aufgabe alle Capabilities (PATCHED)

- Status: **gepatcht** (2026-04-28)
- Risiko: **Niedrig bis Mittel**
- Betroffene Dateien:
  - `beagle-host/systemd/beagle-public-streams.service`
  - `scripts/beagle-cluster-auto-join.sh`
  - `scripts/repo-auto-update.sh`
  - `server-installer/installimage/usr/local/sbin/beagle-network-interface-heal`
- Beschreibung:
  - `beagle-public-streams.service` soll nftables-Regeln und persistenten Beagle-State reconciliieren.
  - Die Unit setzte aber `CapabilityBoundingSet=` leer; dadurch konnte das Root-Skript bestehende State-Verzeichnisse nicht chmod/chownen und waere spaeter auch fuer Netfilter-Aenderungen unzureichend privilegiert.
  - Parallel war `beagle-cluster-auto-join.sh` nicht executable, wodurch ein enabled oneshot beim Boot/Install als failed stehen blieb.
  - Der Repo-Auto-Update-Status konnte durch Short-vs-Full-Hash-Vergleich unnoetige Update-/Repair-Laeufe ausloesen.
- Fix:
  - Public-Streams bekommt nur die fuer diesen Job notwendigen Capabilities (`CAP_DAC_OVERRIDE`, `CAP_FOWNER`, `CAP_NET_ADMIN`, `CAP_NET_RAW`) und explizite Schreibpfade.
  - Cluster-Auto-Join-Skript ist executable.
  - Repo-Auto-Update vergleicht Short-/Full-Hashes robust.
  - Network-Heal normalisiert nicht-idempotente Route-Hooks, damit Netzwerkkonfiguration nicht wegen bereits vorhandener Route failed bleibt.

## S-032 — Login-Guard und API-Rate-Limit nutzten hinter nginx nur die Proxy-IP (PATCHED)

- Status: **gepatcht** (2026-04-28)
- Risiko: **Mittel**
- Betroffene Dateien:
  - `beagle-host/services/request_handler_mixin.py`
  - `website/ui/auth.js`
  - `tests/unit/test_request_handler_mixin_client_addr.py`
- Beschreibung:
  - Die Control Plane laeuft auf `srv1` hinter nginx.
  - nginx setzt `X-Forwarded-For`, aber `_client_addr()` nutzte bisher nur den direkten TCP-Peer.
  - Dadurch teilten alle externen Browser den Login-Guard-/Rate-Limit-Key `127.0.0.1`; fehlgeschlagene Versuche aus einem Kontext konnten korrekte Logins anderer Kontexte mit `429 login temporarily blocked` blockieren.
- Fix:
  - `X-Forwarded-For`/`X-Real-IP` wird nur ausgewertet, wenn der direkte Peer ein lokaler Proxy ist.
  - Direkte externe Requests koennen den Header nicht zum Rate-Limit-Spoofing verwenden.
  - Auth-Session-Audit und Login-Guard nutzen dieselbe korrigierte Client-IP.
  - Login-POSTs werden im Browser als Single-Flight behandelt und zeigen `retry_after_seconds` lesbar an.

## S-031 — WebUI erzeugte CSP-verbotene Inline-Style-Attribute (PATCHED)

- Status: **gepatcht** (2026-04-28)
- Risiko: **Niedrig bis Mittel**
- Betroffene Dateien:
  - `website/ui/scheduler_insights.js`
  - `website/ui/energy_dashboard.js`
  - `website/ui/gpu_dashboard.js`
  - `website/ui/settings.js`
  - `website/ui/cluster.js`
  - `website/ui/virtualization.js`
  - `website/styles/_helpers.css`
  - `website/styles/panels/_cluster.css`
  - `website/styles/panels/_settings.css`
  - `website/styles/panels/_virtualization.css`
- Beschreibung:
  - Die produktive CSP erlaubt Styles nur aus `self`.
  - Mehrere WebUI-Renderer erzeugten dennoch HTML-Strings mit `style="..."` fuer Heatmaps, Balken, Grid-Layouts und Statusmeldungen.
  - Das fuehrte zu Browser-Console-Fehlern und untergrub die Absicht der strikten CSP, Inline-Style-Ausnahmen nicht still wieder einzufuehren.
- Fix:
  - Inline-Style-Attribute wurden durch CSS-Klassen und feste Prozent-/Heatmap-Buckets ersetzt.
  - Die CSP bleibt strikt; es wurde kein `unsafe-inline` ergaenzt.
  - Repo-Check `rg -n "style=|setAttribute\\(['\"]style|cssText|<style" website ...` liefert keine Treffer mehr.

## S-030 — Geschuetzte Settings-Telemetrie wurde vor Login browserseitig vorab angefragt (PATCHED)

- Status: **gepatcht** (2026-04-28)
- Risiko: **Niedrig bis Mittel**
- Betroffene Dateien:
  - `website/main.js`
  - `website/ui/state.js`
  - `website/ui/scheduler_insights.js`
  - `website/ui/cost_dashboard.js`
  - `website/ui/energy_dashboard.js`
- Beschreibung:
  - Die WebUI hat beim Bootstrap mehrere Settings-/Telemetry-Slices bereits ohne aktive Session gerendert.
  - Dadurch entstanden sofortige `401 Unauthorized`-Requests gegen geschuetzte Endpunkte wie `/api/v1/scheduler/insights`, `/api/v1/costs/*` und `/api/v1/energy/*`.
  - Das war kein direkter Datenabfluss, aber vermeidbarer Auth-Layer-Laerm und ein Debugging-/UX-Problem: Operatoren sahen vor dem eigentlichen Login bereits Fehlerbilder, die wie ein kaputtes Backend wirkten.
- Fix:
  - Scheduler-/Kosten-/Energie-Renderer pruefen jetzt zuerst Session und `settings:read`, bevor ueberhaupt Requests gestartet werden.
  - Schreibaktionen spiegeln zusaetzlich `settings:write` im UI.
  - Der Bootstrap rendert diese Panels nicht mehr blind vor dem ersten Auth-/Session-Load.

## S-029 — `vpn_required` war bisher nur Policy-Metadatum und konnte im Session-Broker umgangen werden (PATCHED)

- Status: **gepatcht** (2026-04-28)
- Risiko: **Hoch**
- Betroffene Dateien:
  - `beagle-host/services/endpoint_http_surface.py`
  - `beagle-host/services/device_registry.py`
  - `beagle-host/services/fleet_http_surface.py`
  - `thin-client-assistant/runtime/device_sync.sh`
  - `thin-client-assistant/runtime/device_state_enforcement.sh`
  - `thin-client-assistant/runtime/launch-session.sh`
- Beschreibung:
  - `streaming_profile.network_mode = vpn_required` war bereits im Pool-Contract, im UI und im Thin-Client-Protokoll-Selector vorhanden.
  - Der aktuelle Session-Broker `GET /api/v1/session/current` pruefte diesen Zustand aber noch nicht hart. Ein Endpoint konnte daher trotz `vpn_required`
    weiter Stream-Zieldaten bekommen, wenn er den lokalen VPN-Zustand ignorierte oder falsch meldete.
  - Gleichzeitig setzte die Runtime `locked` / `wipe_pending` nur als lokale Markerdateien, ohne vor Session-Start wirklich zu blockieren oder einen Wipe zu bestaetigen.
- Fix:
  - `session/current` verweigert jetzt `403`, wenn der zugehoerige Pool `vpn_required` setzt und das Device laut Registry keinen aktiven WireGuard-Tunnel hat.
  - Die Device-Registry persistiert den letzten VPN-Zustand (`vpn_active`, `vpn_interface`, `wg_assigned_ip`) aus dem endpoint-authentifizierten Device-Sync.
  - Die Runtime blockiert den Session-Start jetzt hart bei `device.locked`.
  - Bei `device.wipe-pending` fuehrt die Runtime einen reproduzierbaren Secret-/Config-Wipe aus und sendet danach endpoint-authentifiziert `confirm-wiped`.
- Rest-Risiko:
  - Der aktuelle Wipe ist noch kein vollstaendiger Datentraeger-Erase mit TPM-Key-Reset.
  - Der separate spaetere `beagle-stream-server`-Fork muss denselben Enforcement-Gedanken spaeter nochmals auf Stream-Server-Ebene tragen, auch wenn der heutige Broker-Pfad bereits blockiert.

## S-028 — Installer-Skript-Laufprotokolle duerfen keine Operator-Credentials benoetigen (PATCHED)

- Status: **gepatcht** (2026-04-27)
- Risiko: **Mittel**
- Betroffene Dateien:
  - `beagle-host/services/installer_log_service.py`
  - `beagle-host/services/installer_script.py`
  - `beagle-host/services/installer_template_patch.py`
  - `beagle-host/services/control_plane_handler.py`
  - `thin-client-assistant/usb/pve-thin-client-usb-installer.sh`
  - `thin-client-assistant/usb/pve-thin-client-usb-installer.ps1`
- Beschreibung:
  - Betreiber brauchen nachvollziehbare Laufprotokolle fuer heruntergeladene USB-Installer-/Live-Skripte.
  - Eine naive Implementierung mit Manager-/Admin-/Session-Token im Skript haette bei Weitergabe des Skripts volle API-Rechte offengelegt.
  - Deshalb bekommen VM-spezifische Skripte jetzt einen eigenen kurzlebigen HMAC-Token mit Scope `installer-log:write`, der nur Events an `POST /api/v1/public/installer-logs` schreiben kann.
- Fix:
  - Read-API fuer Logs ist authentifiziert und per RBAC auf `settings:read` begrenzt.
  - Persistierte Event-Details redigieren Felder mit `token`, `secret`, `password`, `credential` oder `key`.
  - Shell-/PowerShell-Logging ist non-blocking, damit ein Log-Endpoint-Ausfall keine Provisionierung verhindert.
  - Alte Hosted-Templates werden beim Patchen um fehlende Log-Defaults ergaenzt, damit veraltete Download-Artefakte keinen 500er verursachen.
- Validierung:
  - Lokal: `tests/unit/test_installer_log_service.py`, `test_installer_script.py`, `test_authz_policy.py` gruen.
  - Live `srv1`: gueltiger VM100-Token schreibt Skript-Events; ungueltiger Bearer-Token liefert `401`; `/beagle-downloads` liefert neue Skripte mit Logging-Hooks.

## S-027 — Zero-Touch-Seed-Configs benoetigen aktuell ein Klartext-Admin-Passwort (DOCUMENTED)

- Status: **dokumentiert, Rest-Follow-up offen** (2026-04-27)
- Risiko: **Mittel**
- Betroffene Dateien:
  - `server-installer/seed_config_parser.py`
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
  - `docs/deployment/pxe-deployment.md`
- Beschreibung:
  - Der neue Zero-Touch-Pfad liest Seed-Dateien jetzt produktiv aus USB/PXE und verlangt fuer den vollautomatischen Lauf aktuell ein `admin_password`.
  - `admin_password_hash` wird im Parser zwar weiter akzeptiert, der aktuelle Installer setzt fuer den eigentlichen Linux-User-/Root-Bootstrap aber noch den Klartextwert ein.
  - Folge: Operatoren muessen Seed-Dateien mit Klartext-Passwort als sensibles Einweg-Material behandeln; liegen sie laenger auf USB-Sticks, HTTP-Seeds oder ungehärteten Shares, ist Credential-Leak moeglich.
- Aktuelle Mitigation:
  - Die Doku weist den Seed-/PXE-Pfad jetzt explizit als operator-sensibel aus.
  - Seed-Dateien werden nicht im Repo versioniert; der Installer laedt/liest sie nur zur Laufzeit.
  - PXE-Smokes wurden im Temp-Root ohne echte Secrets validiert.
- Offener naechster Schritt:
  - Installer-Bootstrap auf `admin_password_hash`-First umbauen, so dass Zero-Touch ohne Klartext-Admin-Passwort moeglich wird.
  - Optional zeitlich eng begrenzte First-Boot-Enrollment-Secrets statt statischem Admin-Seed evaluieren.

## S-026 — Neue Session-Handover-State-Dateien koennen durch Root-Debug/Smoke in Ownership-Drift laufen (MITIGATED)

- Status: **mitigiert live, Repo-Follow-up offen** (2026-04-27)
- Risiko: **Niedrig bis Mittel**
- Betroffene Dateien/Pfade:
  - `/var/lib/beagle/beagle-manager/session-manager/`
  - `beagle-host/services/session_manager.py`
  - `docs/goenterprise/06-session-handover.md`
- Betroffene Hosts:
  - `srv1.beagle-os.com` (live reproduziert)
  - potentiell alle Hosts, wenn Root den Session-Manager ausserhalb des laufenden Dienstusers initialisiert
- Beschreibung:
  - Beim Live-Smoke fuer den neuen Endpoint-Session-Broker wurde `session-manager/sessions.json` einmal aus dem Root-Kontext erzeugt.
  - Der produktive Dienst laeuft als `beagle-manager`; dadurch konnte derselbe Pfad spaeter mit `PermissionError` brechen.
  - Das ist kein externer Remote-Angriffspfad, aber ein realer Betriebs-/Privilege-Drift fuer Root-gefuehrte Debug- oder Wartungsschritte.
- Mitigation:
  - Ownership auf `srv1` und vorsorglich `srv2` live auf `beagle-manager:beagle-manager` korrigiert.
  - Weitere Live-Smokes fuer `GET /api/v1/session/current` wurden danach bewusst als `beagle-manager` ausgefuehrt.
- Rest-Risiko:
  - Root-gefuehrte Ad-hoc-Skripte koennen denselben Drift fuer neue State-Pfade erneut erzeugen, solange kein repo-eigener Guard oder fixer Ownership-Repair fuer den Session-Manager existiert.

## S-025 — Root-gefuehrte Wartungs-/Smoke-Skripte konnten Pool-State-Locks unbenutzbar hinterlassen (PATCHED)

- Status: **gepatcht** (2026-04-27)
- Risiko: **Mittel**
- Betroffene Dateien:
  - `scripts/smoke-gaming-kiosk-flow.sh`
  - `beagle-host/services/request_handler_mixin.py`
- Betroffene Hosts:
  - `srv1.beagle-os.com` (live reproduziert)
  - potentiell alle Hosts mit root-gefuehrten State-Mutationen unter `/var/lib/beagle/beagle-manager`
- Beschreibung:
  - Ein Live-Smoke gegen `POST /api/v1/pools/kiosk/sessions/{vmid}/extend` schlug auf `srv1` mit `500 internal server error` fehl.
  - Die Ursache war kein fachlicher API-Fehler, sondern eine von Root hinterlassene Dateirechte-Drift:
    `/var/lib/beagle/beagle-manager/desktop-pools.json.lock` lag als `root:root` vor.
  - Der produktive Dienst laeuft als `beagle-manager`; dadurch scheiterte `JsonStateStore.save()` beim Oeffnen der Lock-Datei mit `PermissionError`.
  - Auswirkung: Mutierende Pool-/Session-Operationen konnten hostseitig in einen teilweisen Denial-of-Service laufen, obwohl API-Code und Unit-Tests gruen waren.
- Fix:
  - `scripts/smoke-gaming-kiosk-flow.sh` setzt `desktop-pools.json` nach dem Lauf wieder auf `beagle-manager:beagle-manager`, behaelt den Dateimodus bei und entfernt stale `.lock`-Dateien.
  - `beagle-host/services/request_handler_mixin.py` loggt ungefangene Request-Exceptions jetzt mit strukturiertem Voll-Traceback, damit hostspezifische Rechte-/Runtime-Drifts sofort in `journalctl` sichtbar sind.
  - Live-Drift auf `srv1` und `srv2` bereinigt: State-Dateien wieder `beagle-manager:beagle-manager`, keine Testzustandsreste mehr vorhanden.
- Rest-Risiko:
  - Andere manuelle Root-Eingriffe in State-Dateien koennen denselben Drift erneut erzeugen, solange sie nicht dieselbe Ownership-Disziplin einhalten.
  - Der generelle Schutz gegen solche Operatorfehler liegt weiterhin in reproduzierbaren Repo-Skripten und nicht in einer kompletten Abschottung des Host-Dateisystems.

## S-024 — Beagle-Repo-Updates und Artifact-Reparatur waren nicht standardmaessig scharf genug (PATCHED)

- Status: **gepatcht** (2026-04-26)
- Risiko: **Mittel**
- Betroffene Dateien:
  - `beagle-host/services/server_settings.py`
  - `scripts/repo-auto-update.sh`
  - `scripts/artifact-watchdog.sh`
  - `scripts/install-beagle-host-services.sh`
  - `beagle-host/systemd/beagle-repo-auto-update.timer`
  - `beagle-host/systemd/beagle-artifacts-watchdog.timer`
- Beschreibung:
  - Frische Serverinstallationen mussten Repo-Auto-Update und Artifact-Watchdog bisher effektiv per UI/Operator-Konfiguration schaerfen.
  - In einem Schwachstellenfall ist das zu langsam: ein Host kann dadurch auf einem alten Repo-Stand oder mit veralteten Installer-/Download-Artefakten bleiben.
- Fix:
  - Repo-Auto-Update ist per Default aktiv, prueft `meinzeug/beagle-os` Branch `main` und nutzt `interval_minutes=1`.
  - Der Repo-Timer startet nach 1 Minute Bootzeit und laeuft danach jede Minute mit `AccuracySec=10s`.
  - Der Artifact-Watchdog ist per Default aktiv, repariert automatisch und setzt `max_age_hours=6`.
  - Der Host-Service-Installer schreibt diese Defaults fuer frische Installationen idempotent in `/var/lib/beagle/beagle-manager/server-settings.json`, ohne bestehende Operator-Werte zu ueberschreiben.
- Rest-Risiko:
  - Wenn ein Operator die Automatik bewusst deaktiviert, bleibt der Host absichtlich im manuellen Betriebsmodus.
  - GitHub-/Netzwerk-Ausfaelle verhindern weiterhin den Pull neuer Commits; der Status muss dann in der WebUI sichtbar bleiben.

---

## S-023 — GitHub Release Workflow war durch unzulaessigen `secrets`-Ausdruck deaktiviert (PATCHED)

- Status: **gepatcht** (2026-04-26)
- Risiko: **Mittel**
- Betroffene Dateien:
  - `.github/workflows/release.yml`
- Beschreibung:
  - Der Release-Workflow nutzte `if: ${{ secrets.BEAGLE_RELEASE_GPG_KEY != '' }}`.
  - GitHub Actions akzeptiert `secrets.*` an dieser Stelle nicht; der gesamte Workflow wurde deshalb schon beim Parsen als invalid verworfen.
  - Folge: Pushes nach `main` bzw. Release-Laeufe konnten keinen gueltigen Workflow-Run erzeugen, Artefakte/Checksummen/Signaturen wurden gar nicht mehr gebaut.
- Fix:
  - Die Secret-Pruefung wurde in den Shell-Schritt verlegt.
  - Der Schritt importiert den GPG-Key jetzt nur noch, wenn `BEAGLE_RELEASE_GPG_KEY` in `env` gesetzt ist; sonst wird sauber ohne Signaturpfad weitergelaufen.
  - Follow-up: der `no-legacy-provider-references`-Workflow normalisiert `./`-Pfade vor dem Allowlist-Vergleich, damit erlaubte Legacy-Dateien nicht faelschlich als neue Legacy-Provider-Referenzen blockieren.
- Rest-Risiko:
  - Die eigentliche Release-Erzeugung auf GitHub muss nach Push erneut live bestaetigt werden.

---

## S-022 — Artifact-Watchdog las initial die falsche Settings-Datei (PATCHED)

- Status: **gepatcht** (2026-04-26)
- Risiko: **Niedrig bis Mittel**
- Betroffene Dateien:
  - `scripts/artifact-watchdog.sh`
  - `beagle-host/services/server_settings.py`
- Beschreibung:
  - Die WebUI speichert Server-/Artifact-Einstellungen im Manager-Datenpfad (`/var/lib/beagle/beagle-manager/server-settings.json`).
  - Der neue Artifact-Watchdog las initial `/etc/beagle/server-settings.json` und konnte dadurch `enabled`/`auto_repair`/`max_age_hours` ignorieren.
  - Folge: UI-Konfiguration und Host-Reaktion konnten auseinanderlaufen.
- Fix:
  - Watchdog liest jetzt standardmaessig denselben Manager-Datenpfad wie die Control-Plane (`${BEAGLE_MANAGER_DATA_DIR:-/var/lib/beagle/beagle-manager}/server-settings.json`).
  - Live auf `srv1` und `srv2` verifiziert: `PUT /settings/artifacts/watchdog` + `POST /settings/artifacts/watchdog/check` fuehren jetzt zu konsistentem `watchdog.config` und `watchdog.status`.
- Rest-Risiko:
  - Solange der Artifact-Refresh selbst noch fehlschlaegt bzw. Artefakte fehlen, meldet der Watchdog korrekt `drift`; das ist kein Sicherheitsproblem, sondern Betriebszustand.

---

## S-021 — Cluster-Preflight und RPC-Port waren zu offen (PATCHED)

- Status: **kritische Punkte gepatcht/live gehärtet** (2026-04-26)
- Risiko vorher: **Hoch**
- Risiko nach Fix: **Niedrig**
- Betroffene Server: `srv1.beagle-os.com`, `srv2.beagle-os.com`
- Betroffene Dateien:
  - `beagle-host/services/request_handler_mixin.py`
  - `beagle-host/services/auth_session_http_surface.py`
  - `beagle-host/services/cluster_membership.py`
  - `scripts/harden-cluster-api-iptables.sh` (live erneut fuer `9089` genutzt)
  - `/etc/iptables/rules.v4` auf `srv1` und `srv2`
- Gefundene Ist-Situation:
  - Von extern erreichbar waren `22`, `80`, `443`, `9089`.
  - `9088` war bereits peer-gefiltert, `9089` aber noch nicht.
  - `/beagle-api/api/v1/health` lieferte ohne Login detaillierte Betriebsinformationen.
  - `/beagle-api/api/v1/auth/onboarding/status` lieferte ohne Login interne Details wie `completed_by` und `user_count`.
  - Der Cluster-Preflight rief auf Zielservern unauthentifiziert `/health` ab.
- Fix:
  - `9089` auf beiden Hosts mit persistenter iptables-Chain `BEAGLE_CLUSTER_RPC_9089` auf localhost + Peer-IP begrenzt.
  - `/api/v1/health` erfordert jetzt Authentifizierung; nur `/healthz` bleibt als minimaler Liveness-Pfad public.
  - Onboarding-Status gibt public nur noch `pending` und `completed` aus.
  - Cluster-Preflight macht keine unauthentifizierte `/health`-Abfrage mehr; `api_health` wird bis zum echten Remote-Setup-Token als `skipped` markiert.
  - Zielserver-Setup-Code umgesetzt: `POST /api/v1/cluster/setup-code` erzeugt nach Login einen kurzlebigen Einmal-Code, speichert nur den SHA-256-Hash und gibt keine Secrets ins Audit.
  - Leader-Auto-Join umgesetzt: `POST /api/v1/cluster/auto-join` verbindet neue Server per Hostname + Setup-Code; der Zielserver akzeptiert `POST /api/v1/cluster/join-with-setup-code` nur bei gültigem Code.
  - Join-Tokens pruefen jetzt serverseitig ihr Ablaufdatum und werden nach Ablauf verworfen.
  - Cluster-Member-Leave folgt jetzt einem Leader-bestaetigten 2-Phasen-Flow; ein normales Mitglied kann die Leader-Memberliste nicht mehr lokal still ueberschreiben.
- Verifikation:
  - Externer TCP-Test nach Fix: öffentlich erreichbar nur noch `22`, `80`, `443`; `9088/9089` nicht mehr extern offen.
  - Public API nach Fix: `/health` -> `401`, `/cluster/status` -> `401`, `/auth/onboarding/status` -> nur `{pending, completed}`.
  - `9089` ohne Client-Zertifikat gab vorher keine Daten heraus (`TLS alert certificate required`), ist jetzt zusaetzlich netzseitig begrenzt.
- Rest-Risiken:
  - Der separate Legacy-Download/API-Port wurde entfernt.
  - `22` ist öffentlich erreichbar; SSH-Key-Policy/Fail2ban/Allowlist muss separat bewertet werden.
  - `srv2` nutzt derzeit ein self-signed TLS-Zertifikat auf `443`.
- Naechster Schritt:
  - Der separate legacy HTTPS listener sollte nicht wieder eingeführt werden.
  - Remote-KVM/libvirt-Preflight nur ueber den setup-code-geschuetzten Zielserverpfad ausfuehren, nicht ueber offene Detail-Endpunkte.

---

Stand: 2026-04-25 (ergänzt: S-020 iptables-Härtung aktiv)

## S-020 — Cluster-Mode: API bindet auf 0.0.0.0 (PATCHED, HARDENED)

- Status: **gepatcht/gehärtet** (2026-04-25)
- Risiko: **Niedrig** (auth + rate-limit + IP-Allowlist auf 9088)
- Betroffene Server: `srv1.beagle-os.com` (46.4.96.80), `srv2.beagle-os.com` (176.9.127.50)
- Betroffene Dateien:
  - `scripts/harden-cluster-api-iptables.sh`
  - `/etc/beagle/beagle-manager.env` (nicht versioniert — lokale Operatorkonfiguration)
  - `/etc/iptables/rules.v4` auf `srv1` und `srv2`
- Beschreibung:
  - Für Cluster-Betrieb muss `BEAGLE_MANAGER_LISTEN_HOST=0.0.0.0` gesetzt sein, damit der andere Node
    die API (Port 9088) für Join-Token-Validierung und Health-Probes erreichen kann.
  - Dadurch war Port 9088 grundsätzlich breit erreichbar.
- Mitigationen aktiv:
  - API-Authentifizierung: alle Management-Endpoints erfordern `Authorization: Bearer` oder Session-Cookie
  - Ausnahmen nur: `/api/v1/cluster/join` (join-token-validiert intern), `/healthz`, öffentliche Endpoints
  - Rate Limiting: 240 Requests/60s pro IP, Lockout nach 5 fehlgeschlagenen Logins (300s)
  - Neue IP-Allowlist-Chain `BEAGLE_CLUSTER_API_9088`:
    - `srv1`: erlaubt `127.0.0.1/32` und `176.9.127.50`, sonst DROP auf tcp/9088
    - `srv2`: erlaubt `127.0.0.1/32` und `46.4.96.80`, sonst DROP auf tcp/9088
  - Neue IP-Allowlist-Chain `BEAGLE_CLUSTER_RPC_9089`:
    - `srv1`: erlaubt `127.0.0.1/32` und `176.9.127.50`, sonst DROP auf tcp/9089
    - `srv2`: erlaubt `127.0.0.1/32` und `46.4.96.80`, sonst DROP auf tcp/9089
  - Persistenz aktiv via `netfilter-persistent`/`iptables-persistent` (Regeln reboot-fest)
- Verbleibende Restrisiken:
  - Public-IP-Transport bleibt ohne VPN grundsätzlich exponiert (trotz Auth + IP-Filter).
  - Empfohlen bleibt ein WireGuard-Mesh und Binding auf das VPN-Interface.
- Nächster Schritt:
  - Optional: automatisches Anwenden der Script-Logik direkt im Cluster-Init/Join-Workflow verdrahten.

---

Stand: 2026-04-29 (ergänzt: Network POST fehlende Authentifizierung gepatcht)

## S-019 — Network POST Endpoints: Fehlende _is_authenticated()-Prüfung (PATCHED)

- Status: **gepatcht** (commit `adbb20f`)
- Risiko: **Mittel** (war — unauthentifizierte Anfragen an Network POST-Endpoints)
- Betroffene Dateien: `beagle-host/bin/beagle-control-plane.py` (do_POST, network-Sektion)
- Beschreibung:
  - Die originalen `do_POST`-Handler für `/api/v1/network/ipam/zones`, `/api/v1/network/ipam/zones/*/allocate`, `/api/v1/network/ipam/zones/*/release`, `/api/v1/network/firewall/profiles`, `/api/v1/network/firewall/profiles/*/apply` hatten kein explizites `_is_authenticated()`-Check.
  - `_authorize_or_respond()` wurde aufgerufen, aber wenn `_auth_principal()` `None` zurückgab (unauthentifiziert + keine Permission konfiguriert), wurde `True` zurückgegeben ohne Authentifizierungsprüfung.
- Fix: Bei Verdrahtung der NetworkHttpSurfaceService in `do_POST` wurde `if not self._is_authenticated():` explizit hinzugefügt.

---

## S-018 — BeagleStream (Sunshine-Fork): Unverschlüsselter LAN-Stream ohne WireGuard

- Status: **architektonisch bekannt**, Mitigation in Plan 01 (GoEnterprise) dokumentiert
- Risiko: **Hoch** (Produktionsumgebungen ohne Verschlüsselung auf dem Streaming-Kanal)
- Betroffene Dateien: `beagle-host/services/sunshine_integration.py`, zukünftig `beagle-stream-server/`
- Beschreibung:
  - Vanilla Sunshine/Moonlight überträgt Video/Audio über UDP ohne Transportverschlüsselung.
  - Im LAN ist ein Angreifer mit physischem Netzwerkzugang in der Lage, Streaming-Traffic mitzulesen oder zu manipulieren (MITM auf UDP-Ebene).
  - Betrifft alle heutigen Beagle-Deployments.
- Mitigation (in Plan 01 GoEnterprise):
  - WireGuard-Mesh: alle Streaming-Verbindungen laufen durch verschlüsselten Tunnel.
  - WireGuard-Latenz-Overhead: **+0.003ms** (gemessen auf srv1, 24.04.2026) — latenz-neutral.
  - `network_mode=vpn_required` in Stream-Policy: Server lehnt Direktverbindungen ohne WireGuard ab.
  - Hardware-Beschleunigung bestätigt: `aes`, `avx2`, `vaes`, `vpclmulqdq` vorhanden auf srv1.
- Nächster konkreter Schritt: `beagle-host/services/wireguard_mesh_service.py` implementieren (Plan 01, Schritt 3).

## S-017 - beagle_curl_tls_args: --pinnedpubkey ohne -k bypasst CA-Verifizierung nicht

- Status: **gefixt** in Repo (2026-04-24)
- Risiko: Mittel (verhinderte TLS-Pinning-Nutzung; kein Sicherheits-Downgrade, aber Pairing-Block)
- Betroffene Datei: `thin-client-assistant/runtime/runtime_value_helpers.sh`
- Beschreibung:
  - `beagle_curl_tls_args` gab bei konfiguriertem Pinned-Pubkey nur `--pinnedpubkey SHA` aus.
  - Bei self-signed Sunshine-Certs (keine CA-Kette) scheiterte curl zuerst an `SSL certificate problem: self-signed certificate` (Error 60), bevor der Pubkey-Check greifen konnte.
  - Effekt: Moonlight-Pairing-API-Calls schlugen fehl; `credentials.env` wurde nicht korrekt evaluiert.
- Fix: `-k` wird nun immer zusammen mit `--pinnedpubkey` ausgegeben (CA-Check bypassen, Pubkey-Pinning bleibt aktiv als Sicherheitsgarantie).
- Verbleibende Note: Mit `-k --pinnedpubkey` schützt nur der Pubkey-Hash; falls Sunshine-Key rotiert wird, muss `PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY` in `credentials.env` ebenfalls aktualisiert werden.

## S-016 - Cluster-Join-Ziel waere als Installer-Secret in breit konsumierten Env-Dateien geleakt

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel
- Betroffene Dateien:
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer-gui`
  - `scripts/install-beagle-host.sh`
  - `scripts/install-beagle-host-postinstall.sh`
  - `scripts/install-beagle-host-services.sh`
- Beschreibung:
  - Mit dem neuen Installer-Join-Dialog aus Plan 07 Schritt 5 muessen Join-Token oder Leader-Ziele durch den Installpfad transportiert werden.
  - Wuerden diese Werte direkt in `host.env`, Proxy-Env oder andere breit gesourcte Runtime-Dateien geschrieben, waeren sie fuer mehr Prozesse/Operator-Pfade sichtbar als noetig.
- Mitigation:
  - Join-Daten werden jetzt in `/etc/beagle/cluster-join.env` mit Modus `0600` persistiert.
  - Allgemeine Runtime-Env-Dateien enthalten nur `BEAGLE_CLUSTER_JOIN_REQUESTED` und den Pfad zur Secret-Datei, nicht das eigentliche Join-Ziel.
  - Der Plain-Mode- und GUI-Installerpfad wurde lokal und auf `srv1.beagle-os.com` mit erfolgreicher State-Erzeugung verifiziert.

## S-015 - Restriktive VDI-Pools waren fuer beliebige `pool:read`-Principals sichtbar

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel
- Betroffene Dateien:
  - `beagle-host/bin/beagle-control-plane.py`
  - `beagle-host/services/entitlement_service.py`
  - `scripts/test-vdi-pools-smoke.py`
- Beschreibung:
  - Die Pool-GET-Routen lieferten bisher alle VDI-Pools an jeden authentifizierten Principal mit `pool:read` aus.
  - Dadurch waren Pool-IDs, Modi und Slot-Status restriktiver Pools sichtbar, obwohl dieselben User spaeter bei `POST /allocate` korrekt ein `403 not entitled to this pool` erhielten.
  - Das war ein Informationsleck zwischen Sichtbarkeit und Mutations-Guard.
- Mitigation:
  - `GET /api/v1/pools` filtert restriktive Pools jetzt serverseitig anhand der Entitlements.
  - `GET /api/v1/pools/{pool}`, `/vms` und `/entitlements` maskieren nicht sichtbare Pools als `404 pool not found`.
  - Operator-/Admin-Bearbeiter mit `pool:write` bzw. `*` behalten den Vollzugriff fuer Betrieb und Diagnose.
  - `EntitlementService` fuehrt die explizite Sichtbarkeits-Semantik (`has_explicit_entitlements`, `can_view_pool`) zentral.
  - `scripts/test-vdi-pools-smoke.py` prueft den Fall jetzt reproduzierbar mit echten Bearer-Sessions (Admin vs. berechtigter User vs. unberechtigter User) lokal und auf `srv1.beagle-os.com`.
- Naechster Schritt:
  - Wenn Auth-Principals kuenftig echte Gruppenclaims aus OIDC/SAML/SCIM tragen, denselben Sichtbarkeits-/Allocate-Pfad auch fuer Gruppen-Entitlements live verifizieren.

## S-014 - Audit-Events schrieben Secrets/PII ungeschwaerzt in `old_value` / `new_value`

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel bis Hoch
- Betroffene Dateien:
  - `core/audit_event.py`
  - `beagle-host/services/audit_pii_filter.py`
  - `beagle-host/services/audit_log.py`
  - `beagle-host/services/audit_report.py`
- Beschreibung:
  - Mit dem neuen Audit-Schema konnten sensible Inhalte wie Passwoerter, API-Tokens oder private Schluessel in `old_value` bzw. `new_value` landen.
  - Ohne Redaction waeren diese Daten sowohl lokal im Audit-Log als auch im CSV/JSON-Export sichtbar geblieben.
- Mitigation:
  - Neues Modul `beagle-host/services/audit_pii_filter.py` schwaerzt rekursiv Felder, deren Name `password`, `secret`, `token` oder `key` enthaelt.
  - `core/audit_event.py` wendet die Redaction zentral beim Erzeugen und Normalisieren von Audit-Records auf `old_value` und `new_value` an.
  - Unit-Test deckt Passwoerter, verschachtelte Tokens und private Keys explizit ab.
  - Live auf `srv1.beagle-os.com` per Python-Snippet gegen die deployte Runtime verifiziert (`[REDACTED]`).
- Naechster Schritt:
  - Optional konfigurierbare Pfadlisten/Pseudonymisierung fuer E-Mail, IP und Username ergaenzen, falls regulierte Deployments das verlangen.

## Zweck

- Diese Datei sammelt alle waehrend der laufenden Refactor-Arbeit gefundenen Sicherheitsprobleme, Secret-Leaks, unsicheren Defaults und offenen Hardening-Punkte.
- Jeder neue Fund muss hier mit Status, Auswirkung und naechstem Schritt eingetragen werden.
- Wenn ein Fund im selben Run sicher und reproduzierbar behebbar ist, wird er direkt gepatcht und hier als mitigiert dokumentiert.

## S-001 - Lokale Operator-Dateien waren im Git-Tracking

- Status: mitigiert im Workspace, Shared-Repo-Commit/Pull-Request noch erforderlich
- Risiko: Hoch
- Betroffene Dateien:
  - `AGENTS.md`
  - `AGENTS.md`
- Beschreibung:
  - Beide lokalen Operator-Dateien waren im Git-Tracking und konnten dadurch versehentlich auf GitHub landen.
  - Dadurch besteht ein strukturelles Risiko, dass interne Arbeitsanweisungen, lokale Betriebsdetails oder spaeter eingetragene Zugangshinweise offengelegt werden.
- Mitigation:
  - `.gitignore` wurde um `AGENTS.md` und `AGENTS.md` erweitert.
  - `AGENTS.md` und `AGENTS.md` wurden aus dem Git-Index entfernt und lokal beibehalten.
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
  - Der erste Build des neuen Hetzner-installimage-Artefakts hat die lokalen Dateien `AGENTS.md` und `AGENTS.md` in das eingebettete Beagle-Source-Archiv aufgenommen.
  - Dadurch waeren lokale Operator-Hinweise ueber das oeffentlich verteilte installimage-Artefakt weitergegeben worden.
- Mitigation:
  - Builder wurde direkt gepatcht, sodass nur explizit erlaubte Repo-Pfade gebuendelt werden und `AGENTS.md` / `AGENTS.md` nicht mehr Teil des Source-Bundles sind.
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
  - Dadurch haetten `AGENTS.md` oder `AGENTS.md` ueber allgemeine Release-Artefakte oder Server-Installer-ISO-Inhalte veroeffentlicht werden koennen.
- Mitigation:
  - `scripts/package.sh` und `scripts/build-server-installer.sh` wurden auf explizite erlaubte Repo-Pfade ohne `AGENTS.md` / `AGENTS.md` umgestellt.
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
  - `server_settings.py` schaltet nginx nach erfolgreicher Zertifikatserstellung jetzt aktiv auf die Let's-Encrypt-Pfade um (`fullchain.pem`/`privkey.pem`), prueft die Konfiguration mit `nginx -t` und laedt nginx neu.
  - Damit wird verhindert, dass ein gueltiges LE-Zertifikat zwar ausgestellt ist, aber weiterhin ein Self-Signed-Zertifikat ausgeliefert wird.
  - TLS-Issuance laeuft bevorzugt ueber einen transienten `systemd-run` Prozess, damit die Funktion mit bestehender Service-Haertung kompatibel bleibt.
  - `ReadWritePaths=` des Control-Plane-Services wurde fuer relevante Let's-Encrypt/nginx-Pfade erweitert.
  - Live auf `srv1.beagle-os.com` verifiziert: externer TLS-Handshake liefert Issuer `Let's Encrypt (E8)`, nginx referenziert LE-Pfade, Status meldet `provider=letsencrypt`, Zertifikat vorhanden, nginx TLS aktiv.
- Naechster Schritt:
  - Den Fix ueber neu gebaute Installer-Artefakte ausrollen und einen Regressionstest fuer den Security/TLS-Pfad ergaenzen.

## S-006 - Control-Plane API ohne harte Gateway-Guards (Rate-Limit/Brute-Force/Error-Schema)

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Hoch
- Betroffene Dateien:
  - `beagle-host/bin/beagle-control-plane.py`
  - `scripts/install-beagle-host-services.sh`
- Beschreibung:
  - Die API hatte zuvor kein durchgaengiges Request-Rate-Limit auf allen `/api/*`-Routen.
  - Login-Fehlversuche wurden nicht mit serverseitigem Exponential-Backoff + Lockout begrenzt.
  - Error-Responses waren teilweise ohne einheitliches `code`-Feld.
  - Unbehandelte Exceptions hatten keine zentrale Sanitization-Grenze.
- Mitigation:
  - Python-Middleware-Rate-Limit fuer alle API-Endpunkte implementiert (`BEAGLE_API_RATE_LIMIT_WINDOW_SECONDS`, `BEAGLE_API_RATE_LIMIT_MAX_REQUESTS`).
  - Login-Brute-Force-Schutz mit Exponential-Backoff und Lockout implementiert (`BEAGLE_AUTH_LOGIN_LOCKOUT_THRESHOLD`, `BEAGLE_AUTH_LOGIN_LOCKOUT_SECONDS`, `BEAGLE_AUTH_LOGIN_BACKOFF_MAX_SECONDS`).
  - Access-Token-Default auf 15 Minuten gehaertet (`BEAGLE_AUTH_ACCESS_TTL_SECONDS=900`).
  - Einheitliches Error-Schema durch automatisches `code`-Feld auf Fehler-Payloads ergaenzt.
  - Zentrale Exception-Grenze (`handle_one_request`) liefert sanitisiertes 500-JSON (`internal_error`).
  - Strukturierte JSON-Response-Logs enthalten jetzt `user`, `action`, `resource_type`, `resource_id`.
- Validierung:
  - `srv1`: `/api/v1/auth/me` liefert `401` mit `code=unauthorized`.
  - `srv1`: wiederholte falsche Logins liefern `429` mit `code=rate_limited` und `retry_after_seconds`.
  - `srv1`: bei temporaerem Limit `BEAGLE_API_RATE_LIMIT_MAX_REQUESTS=5` schaltet API reproduzierbar auf `429 rate_limited` nach mehreren Requests.
  - Env-Werte auf `srv1` geprueft und auf Produktionswert (`240`) zurueckgesetzt.
- Naechster Schritt:
  - Refresh-Token auf HTTP-only/SameSite=Strict Cookie-Flow umstellen (aktuell noch offen in GoFuture 20, Schritt 2).

## S-007 - Fehlende serverseitige Payload-Whitelist/Identifier-Validation in Auth-POST-Routen

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel bis Hoch
- Betroffene Dateien:
  - `beagle-host/bin/beagle-control-plane.py`
  - `beagle-host/services/auth_session.py`
  - `tests/unit/test_auth_session.py`
- Beschreibung:
  - Mehrere Auth-POST-Routen akzeptierten bislang zusaetzliche oder ungueltige Felder ohne strikte Whitelist-Pruefung.
  - Identifier-Checks waren nicht durchgaengig serverseitig erzwungen (z.B. User-/Role-Namen mit ungueltigen Zeichen).
- Mitigation:
  - Control-Plane hat jetzt Whitelist-Schema-Pruefung fuer zentrale Auth-POST-Routen (`login`, `refresh`, `logout`, `onboarding/complete`, `auth/users`, `auth/roles`).
  - Serverseitige Identifier-Sanitizer in Handler + Auth-Session-Service ergaenzt.
  - `AuthSessionService` erzwingt `USERNAME_PATTERN`/`ROLE_NAME_PATTERN` in `create_user`, `update_user`, `save_role`, `complete_onboarding`, `login`.
  - Unit-Tests um negative Faelle erweitert (`invalid username`, `invalid role name`).
- Validierung:
  - Lokal: `python -m unittest tests.unit.test_auth_session` -> OK.
  - `srv1`: `/api/v1/auth/onboarding/complete` mit `username="bad user"` liefert `400` + `code=bad_request`.
  - `srv1`: `/api/v1/auth/login` mit zusaetzlichem Feld `extra` liefert `400` + `invalid payload: unexpected keys`.

## S-010 - Persistente noVNC-Tokens (kein TTL, nicht single-use)

- Status: behoben in Repo und auf `srv1.beagle-os.com`
- Risiko: Hoch
- Betroffene Dateien:
  - `beagle-host/services/vm_console_access.py`
  - `beagle-host/bin/beagle_novnc_token.py` (neu)
  - `beagle-host/systemd/beagle-novnc-proxy.service`
- Beschreibung: noVNC-Tokens waren persistent pro VM (nie rotiert), wiederverwendbar und ohne TTL. Ein einmal erlangtes Token konnte unbegrenzt lange genutzt werden.
- Mitigation:
  - Pro Console-Öffnung wird jetzt ein frischer 32-Byte-Token generiert (TTL=30s).
  - Tokens werden beim ersten erfolgreichen `lookup()` als verwendet markiert (single-use).
  - Benutzerdefinierter websockify-Plugin `BeagleTokenFile` liest aus JSON-Store statt plaintext-Tokenfile.
  - 8/8 Unit-Tests validiert; live auf `srv1.beagle-os.com` deployed und verifiziert via `journalctl`.

## S-011 - Refresh-Token in localStorage / JSON-Body (kein HttpOnly Cookie)

- Status: behoben in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel-Hoch (XSS-exponiert)
- Betroffene Dateien:
  - `beagle-host/bin/beagle-control-plane.py`
- Beschreibung: Refresh-Token war bisher im JSON-Response-Body enthalten, was Clients veranlassen konnte, ihn in localStorage zu speichern (XSS-zugänglich).
- Mitigation:
  - Login und Refresh setzen jetzt `Set-Cookie: beagle_refresh_token=...; HttpOnly; SameSite=Strict; Path=/api/v1/auth; Secure`.
  - `/auth/refresh` liest Token aus Cookie wenn nicht im Body.
  - Logout leert den Cookie via `Max-Age=0`.
  - Fehlgeschlagener Refresh löscht Cookie ebenfalls.

## S-009 - Uneinheitliche systemd-Hardening/CSP-Baseline in Host-Units

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel
- Betroffene Dateien:
  - `beagle-host/systemd/beagle-novnc-proxy.service`
  - `beagle-host/systemd/beagle-artifacts-refresh.service`
  - `beagle-host/systemd/beagle-public-streams.service`
  - `beagle-host/systemd/beagle-ui-reapply.service`
  - `scripts/install-beagle-proxy.sh`
- Beschreibung:
  - Mehrere Beagle-Units hatten keine explizite `CapabilityBoundingSet`-/`RestrictAddressFamilies`-Absicherung.
  - noVNC lief als root obwohl kein privilegierter Port oder root-only capability erforderlich war.
  - CSP im nginx-Proxypfad war ohne explizite `wss:`-Freigabe im `connect-src`.
- Mitigation:
  - Unit-Hardening auf die betroffenen Beagle-Units ausgerollt (`CapabilityBoundingSet=`, `RestrictAddressFamilies=...`).
  - `beagle-novnc-proxy.service` auf non-root `beagle-manager` umgestellt und weiter gesandboxed.
  - CSP im nginx-Proxypfad auf `connect-src 'self' wss:` angepasst, weiterhin ohne `unsafe-inline`/`unsafe-eval`.
- Validierung:
  - `srv1`: `systemctl show beagle-novnc-proxy.service` zeigt `User=beagle-manager`, `CapabilityBoundingSet=` und eingeschraenkte AddressFamilies.
  - `srv1`: `curl -kI https://127.0.0.1/` zeigt den erwarteten CSP-Header mit `wss:`.

## S-008 - Fehlende automatisierte Dependency-Audit-Integration

- Status: mitigiert (Automation vorhanden), Findings offen
- Risiko: Mittel
- Betroffene Dateien:
  - `scripts/security-audit.sh`
  - `.github/workflows/security-audit.yml`
  - `.gitignore`
- Beschreibung:
  - Es fehlte ein reproduzierbarer, regelmaessig laufender CVE-Check fuer Python- und Node-Abhaengigkeiten.
- Mitigation:
  - Neues Skript `scripts/security-audit.sh` hinzugefuegt (`pip-audit` + `npm audit`, Report-Ausgabe nach `dist/security-audit/`).
  - Neuer GitHub-Workflow `.github/workflows/security-audit.yml` mit monatlichem Schedule + manuellem Trigger + Report-Artefakt-Upload.
  - `.gitignore` um `.env` / `.env.*` erweitert.
- Validierung:
  - Lokal ausgefuehrt (`BEAGLE_SECURITY_AUDIT_STRICT=0 scripts/security-audit.sh`).
  - Ergebnis: bekannte Vulnerabilities gemeldet (`pip` im venv; npm audit findings im `beagle-kiosk`-Scope) und als Reports gespeichert.
- Naechster Schritt:
  - `pip` im Runtime-/CI-Umfeld auf gefixte Version anheben,
  - npm findings im `beagle-kiosk` aufloesen oder begruendete Ignore-Liste mit Ablaufdatum einfuehren.

## S-012 - Unsicherer Installer-Debug-SSH-Default (aktiv + Standardpasswort)

- Status: mitigiert in Repo
- Risiko: Hoch
- Betroffene Dateien:
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
- Beschreibung:
  - Der Server-Installer aktivierte Debug-SSH im Live-System per Default (`BEAGLE_SERVER_INSTALLER_DEBUG_SSH_ENABLE=1`) und setzte ein statisches Root-Passwort (`beagle-debug`).
  - Auf exponierten Install-Netzen war damit ein triviales Remote-Login-Risiko vorhanden.
- Mitigation:
  - Debug-SSH ist jetzt standardmäßig deaktiviert (`BEAGLE_SERVER_INSTALLER_DEBUG_SSH_ENABLE=0`).
  - Es gibt kein statisches Standardpasswort mehr (`BEAGLE_SERVER_INSTALLER_DEBUG_SSH_PASSWORD` ist per Default leer).
  - Debug-SSH bleibt nur als explizit gesetzte Operator-Option verfügbar.
- Naechster Schritt:
  - Nach ISO-Rebuild verifizieren, dass Debug-SSH im Live-Boot ohne explizite Aktivierung nicht gestartet wird.

## S-013 - Fehlende verpflichtende Secret-Hygiene-Gates im Repo

- Status: mitigiert in Repo
- Risiko: Hoch
- Betroffene Dateien:
  - `scripts/security-secrets-check.sh` (neu)
  - `.github/workflows/security-secrets-check.yml` (neu)
  - `.security-secrets-allowlist` (neu)
- Beschreibung:
  - Es fehlte ein verpflichtender Repo-Gate, der harte Secret-Leaks (getrackte `.env`, Operator-Dateien, typische Hardcoded-Secret-Muster) frühzeitig blockiert.
- Mitigation:
  - Neues Skript `scripts/security-secrets-check.sh` erzwingt Secret-Hygiene-Regeln und erzeugt Report in `dist/security-audit/secrets-check.txt`.
  - CI-Workflow läuft monatlich + manuell + bei Änderungen an sicherheitsrelevanten Pfaden.
  - Allowlist-Datei für explizite, reviewbare Ausnahmen ergänzt.

## S-014 - OWASP-Baseline-Checks waren nicht reproduzierbar automatisiert

- Status: mitigiert in Repo
- Risiko: Mittel
- Betroffene Dateien:
  - `scripts/security-owasp-smoke.sh` (neu)
- Beschreibung:
  - OWASP Top-10 Abdeckung war primär textuell dokumentiert, aber nicht als reproduzierbarer API-Smoke in den operativen Skripten verfügbar.
- Mitigation:
  - `scripts/security-owasp-smoke.sh` implementiert reproduzierbare Baseline-Checks für zentrale OWASP-relevante Klassen:
    - Broken Access Control (unauth mutating routes -> 401)
    - Identification/Authentication Failures (auth endpoints unauth)
    - Injection/Input Validation (malformed payload -> 400)
    - Security Misconfiguration (unknown route handling)
  - Script ist für lokale und srv1-Läufe vorgesehen.

## S-015 - OIDC-Callback ohne kryptografische ID-Token-Signaturprüfung

- Status: offen (teilweise mitigiert, Follow-up erforderlich)
- Risiko: Mittel bis Hoch
- Betroffene Dateien:
  - `beagle-host/services/oidc_service.py`
  - `beagle-host/bin/beagle-control-plane.py`
- Beschreibung:
  - Der neue OIDC-Flow verarbeitet Authorization-Code + PKCE und extrahiert Claims aus `id_token`/`userinfo`, prüft derzeit aber die Signatur des `id_token` nicht gegen JWKS.
  - Ohne Signaturprüfung ist die Claim-Quelle nicht kryptografisch abgesichert.
- Mitigation (bereits umgesetzt):
  - PKCE (`S256`) + `state`/`nonce` werden serverseitig erzeugt und verwaltet.
  - Endpunkte sind auf explizite OIDC-Aktivierung (`BEAGLE_OIDC_ENABLED`) und konfigurierte IdP-URLs begrenzt.
- Nächster Schritt:
  - JWKS-Fetch + Key-Rotation + RSA/ECDSA-Signaturprüfung für `id_token` implementieren,
  - Claims erst nach erfolgreicher Signatur-, Issuer-, Audience- und Expiry-Validierung akzeptieren.

## S-016 - SCIM-Bearer-Token aktuell als statischer Klartext-Env-Wert

- Status: offen (mitigiert durch separate Token-Grenze, Rotation noch ausstehend)
- Risiko: Mittel
- Betroffene Dateien:
  - `beagle-host/bin/beagle-control-plane.py`
  - `beagle-host/services/scim_service.py`
- Beschreibung:
  - SCIM-Zugriff ist korrekt von Session/API-Token getrennt und erfordert `BEAGLE_SCIM_BEARER_TOKEN`,
    aber der Token liegt derzeit als statischer Klartext-Environment-Wert vor.
  - Ohne Rotation/Secret-Backend steigt das Risiko bei Host-Config-Leak oder Operator-Fehlbedienung.
- Mitigation (bereits umgesetzt):
  - eigener SCIM-Auth-Guard (`Authorization: Bearer <scim-token>`) auf allen `/scim/v2/*` Routen,
  - fehlender/falscher Token liefert `401 unauthorized`.
- Nächster Schritt:
  - SCIM-Token-Rotation und optional Hash-at-rest/Secret-Store-Integration ergänzen,
  - SCIM-Mutationsaufrufe strukturiert auditieren.

## S-017 - manager-api-token und weitere Secrets nicht mehr als Klartext-Env (GELOEST)

- Status: geloest (GoAdvanced Plan 03, 2026-04)
- Risiko: Hoch → Geschlossen
- Beschreibung:
  - `BEAGLE_MANAGER_API_TOKEN`, `BEAGLE_AUTH_SECRET` und weitere Laufzeit-Secrets wurden beim
    ersten Start als Klartext-Env-Vars gesetzt oder fehlten vollstaendig.
  - Ohne Rotation/Versioning war ein kompromittierter Token dauerhaft gueltig.
- Mitigation (umgesetzt):
  - `SecretStoreService` (Plan 03 Schritt 2): JSON-Backend unter `/var/lib/beagle/secrets/` (mode 0o600),
    Versions-Tracking, Grace-Period (24h), sofortige Revocation.
  - Auto-Bootstrap (Plan 03 Schritt 3): beim ersten Start wird `secrets.token_hex(32)` generiert
    und nur ins Journal geloggt (Name + Version, KEIN Wert), Env-Var bleibt als Override-Option.
  - Audit-Events (Plan 03 Schritt 4): `secret_accessed` / `secret_rotated` / `secret_revoked` im AuditLog
    — Klartext-Werte landen NICHT im Audit-Log (Test: `test_secret_bootstrap.py::TestBootstrapAuditLogSafety`).
  - Rotation-CLI: `beaglectl secret rotate|list|revoke` (Plan 03 Schritt 5).
  - SecretStore-Kopplung: `_bootstrap_secret()` in `service_registry.py` liest aus SecretStore statt Env.
- Naechster Schritt:
  - Phase 2: optionaler Vault/AWS-Secrets-Manager-Adapter (deferred, Plan 03 Schritt 2 Phase 2).
  - S-016 (SCIM-Token) als naechstes SecretStore-integrieren.

## S-018 - Operator-Debug-Traces koennen Runtime-Secrets in Logs ausgeben

- Status: offen (prozessual erkannt, technischer Guard noch ausstehend)
- Risiko: Mittel bis Hoch
- Betroffene Bereiche:
  - Operator-Ausfuehrung von Shell-Skripten mit `bash -x`
  - Skripte, die `/etc/beagle/*.env` oder andere Secret-/Runtime-Env-Dateien sourcen
- Beschreibung:
  - Shell-xtrace kann expandierte Environment-Werte und Funktionsaufrufe in Terminal-/CI-/Agent-Logs schreiben.
  - Wenn solche Skripte Runtime-Env-Dateien sourcen, koennen Tokens oder andere sensitive Werte in nicht dafuer vorgesehene Logs gelangen.
  - In diesem Run wurden keine Secret-Werte in Repo-Dateien dokumentiert; der Fund betrifft die Arbeitsweise und kuenftige Reproduzierbarkeit.
- Naechster Schritt:
  - Operator-Runbooks und kritische Skripte so haerten, dass Secret-sourcende Abschnitte `set +x` erzwingen.
  - Optional einen Shellcheck-/grep-Smoke ergaenzen, der `bash -x`/`set -x` in Kombination mit `/etc/beagle/*.env` markiert.
  - WebUI-/Job-Logs duerfen Secret-Felder nur redacted anzeigen.

## S-019 - Audit-Failure-Payloads duerfen keine Secrets persistieren

- Status: geloest (2026-04-27)
- Risiko: Mittel
- Betroffene Dateien:
  - `beagle-host/services/audit_export.py`
  - `website/ui/audit.js`
- Beschreibung:
  - Fuer Failure-Replay muss der Audit-Exporter fehlerhafte Events mit Payload-Kontext puffern.
  - Ohne Redaction koennten Felder wie `password`, `token`, `secret` oder `key` in `/var/lib/beagle/audit/export-failures.log` oder im WebUI-Detail landen.
- Mitigation:
  - Failure-Payloads werden vor Persistenz rekursiv redacted.
  - WebUI-JSON-Details werden vor Anzeige rekursiv redacted und mit `redacted` markiert.
  - Regression: `tests/unit/test_audit_export.py::AuditExportServiceTests::test_failure_log_redacts_sensitive_payload_fields`.

## S-020 - Root-owned auth state kann Login-DoS ausloesen

- Status: mitigiert in Repo, Live-Fix auf `srv1`/`srv2` ausgerollt (2026-04-27)
- Risiko: Mittel
- Betroffene Dateien:
  - `beagle-host/services/auth_session.py`
  - `beagle-host/services/control_plane_handler.py`
- Beschreibung:
  - Der Login-Pfad brach auf `srv1`/`srv2` zeitweise mit `500` ab.
  - Ursache A: der Audit-POST-Dispatch konnte vor dem Auth-Handler mit `AttributeError` scheitern.
  - Ursache B: `AuthSessionService._load_roles_doc()` schrieb `roles.json` selbst bei einem reinen Read jedes Mal zurueck; wenn die Datei zwischenzeitlich `root:root` gehoerte, fuehrte bereits ein ungueltiger Login zu `PermissionError` statt zu einer sauberen `401`.
  - Effekt: partieller Auth-DoS fuer die WebUI.
- Mitigation:
  - Audit-POST-Dispatch nutzt jetzt die konkrete Surface-Instanz statt des fragilen Klassenaufrufs.
  - Rollen-State wird nur noch geschrieben, wenn die Normalisierung den Payload wirklich aendert.
  - `srv1`-Runtime-Datei `/var/lib/beagle/beagle-manager/auth/roles.json` wurde wieder auf `beagle-manager:beagle-manager` gesetzt.
  - Regressionen:
    - `tests/unit/test_audit_report.py`
    - `tests/unit/test_auth_session.py`
- Naechster Schritt:
  - Pruefen, welcher Root-Pfad `roles.json` zuvor als `root:root` hinterlassen hat, und diesen Deploy-/Operator-Pfad zusaetzlich bereinigen.

## S-021 - Cluster-Liveness war implizit an Public-TLS-Trust gekoppelt (mitigiert)

- Status: mitigiert (2026-04-27)
- Risiko: Mittel
- Betroffene Dateien:
  - `beagle-host/services/cluster_membership.py`
- Beschreibung:
  - Der Cluster-Member-Probe nutzte die konfigurierten `api_url`s und validierte bei HTTPS implizit die oeffentliche Zertifikatskette.
  - Auf `srv2` fuehrte die bekannte unvollstaendige Public-CA-Kette dazu, dass `srv1` den Member trotz erreichbarer WebUI als `unreachable` markierte.
  - Folge: Operatoren sahen einen falschen Cluster-Fehlerzustand; Auto-Join-/Install-Check-Folgeschritte waeren unnötig blockiert oder verwirrend gewesen.
- Mitigation:
  - Liveness-Probe entkoppelt von Browser-Trust und nutzt fuer HTTPS einen unverified SSL context.
  - Die Ausnahme ist bewusst eng auf den unauthentifizierten `healthz`-Probe beschraenkt; privilegierte Cluster-RPCs bleiben an mTLS mit Cluster-CA gebunden.
- Rest-Risiko:
  - Die oeffentliche TLS-Kette auf `srv2` bleibt operativ trotzdem zu bereinigen; die Mitigation verhindert nur falsche Cluster-Offlines durch dieses Problem.

## S-022 - Host-Firewall war auf srv1 nicht als Default-Drop-Baseline aktiv

- Status: mitigiert in Repo und live auf `srv1` (2026-04-27)
- Risiko: Hoch
- Betroffene Dateien:
  - `scripts/apply-beagle-firewall.sh`
  - `scripts/install-beagle-host-services.sh`
  - `scripts/check-beagle-host.sh`
  - `beagle-host/services/server_settings.py`
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-live-server-bootstrap`
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
- Beschreibung:
  - Auf `srv1` war `nftables` zwar enabled, aber inaktiv; die vorhandenen INPUT/FORWARD-Policies waren effektiv accept.
  - Public Cluster-RPC/API waren nur durch separate iptables-Allowlist-Hotfixes begrenzt, nicht durch eine reproduzierbare Beagle-Install-Baseline.
  - Frische Server-Installationen konnten dadurch vor dem ersten Operator-Hardening zu offen starten.
- Mitigation:
  - Neue Beagle nftables Guard-Baseline mit Default-Drop fuer Host-Input und Forward.
  - Erlaubt nur `22/80/443`, VM-Bridge-DNS/DHCP, lokale/peer-allowlisted Cluster-Ports und explizit DNAT-getriggerte VM-Stream-Forwards.
  - Installer und Host-Service-Install wenden die Baseline automatisch an.
  - WebUI/API nutzt nun Beagle nftables statt UFW.
  - Live `srv1`: `nftables` aktiv, `table inet beagle_guard` aktiv, externe Probe sieht `9088/9089` geschlossen.
- Regression/Abnahme:
  - `scripts/check-beagle-host.sh` prueft die Beagle-Guard-Baseline.
  - `pytest -q tests/unit` -> 1222 passed, 4 subtests passed.
- Rest-Risiko:
  - Stream-Persistenz ueber kompletten Host-Reboot ist noch separat zu validieren, damit DNAT-Reconciler, libvirt und Beagle-Guard nach Boot-Reihenfolge zusammenspielen.
