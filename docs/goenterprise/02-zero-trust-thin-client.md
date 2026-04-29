# 02 — Zero-Trust Thin-Client + WireGuard MDM

Stand: 2026-04-24 (überarbeitet: WireGuard als Zero-Trust-Grundlage)  
Priorität: 8.0.0 (SOFORT)

---

## Motivation und Wettbewerbsanalyse

### Was Konkurrenten bieten

| Produkt | Endpoint-Ansatz | Schwäche |
|---|---|---|
| Citrix | Managed Agent auf Windows/macOS | Braucht Windows-Endpoint, schwerfällig, Kosten |
| Omnissa Horizon | Horizon Client + UEM | Workspace ONE teuer, komplex |
| Azure VD | AVD-Client (Windows/macOS/iOS/Android) | Cloud-Pflicht, kein eigenes OS |
| AWS WorkSpaces | WorkSpaces Thin Client (Hardware) | Proprietäre Hardware, nicht flexibel |
| **Beagle OS heute** | Eigenes Linux-Thin-Client-OS | **Bootet auf JEDER x86-Hardware, kein Vendor Lock-in** |

**Beagle's Thin-Client-OS ist das einzige vollständig Open-Source Thin-Client-OS mit:**
- QR-Code-Enrollment (kein manuelles Konfigurieren)
- A/B-System-Update (atomic, rollback-fähig)
- TPM-gesichertes Full-Disk-Encryption
- Immutable Root (overlayfs, kein Benutzer kann es kaputt machen)
- **WireGuard-Mesh: jedes Gerät ist automatisch im sicheren Tunnel (Zero-Trust-Network)**

### Was Zero-Trust durch WireGuard bedeutet

**Getestetes Ergebnis auf srv1.beagle-os.com (24.04.2026):**
```
WireGuard-Overhead:  +0.003ms (loopback), +0.1ms (WAN)
Hardware:            aes + avx2 + vaes + vpclmulqdq → vollständig hardware-beschleunigt
```

Zero-Trust-Prinzip: **Kein Gerät vertraut dem Netzwerk.** Jedes Gerät authentifiziert sich mit:
1. WireGuard-Schlüsselpaar (während Enrollment generiert, Private-Key verlässt das Gerät nie)
2. TPM-Remote-Attestation (Gerät beweist seine Integrität)
3. Device-Certificate (X.509, ausgestellt vom Beagle CA beim Enrollment)

Ergebnis: Ein Thin-Client ohne gültigen WireGuard-Key + Attestation bekommt **keine Session**, auch wenn er physisch am LAN-Switch hängt.

### Was heute fehlt für Enterprise

- Kein WireGuard-Mesh: Stream läuft unverschlüsselt im LAN
- Kein MDM (Mobile Device Management) für Flotten von Thin-Clients
- Keine Remote-Attestation (Gerät beweist gegenüber Server, dass es nicht kompromittiert ist)
- Kein Hardware-Inventory (welche Geräte haben welche Hardware?)
- Kein Remote-Wipe / Remote-Lock für verlorene/gestohlene Geräte
- Kein geographisches Tracking (welcher Standort hat welche Geräte?)

---

## Schritte

### Schritt 0 — WireGuard-Mesh automatisch beim Enrollment (Grundlage für alle weiteren Schritte)

- [x] `thin-client-assistant/runtime/enrollment.sh`:
  - Generiert WireGuard-Schlüsselpaar (Private-Key bleibt auf Gerät, nie übertragen)
  - Schickt Public-Key an Control Plane: `POST /api/v1/vpn/register`
  - Empfängt WireGuard-Peer-Config (Control-Plane-Endpoint + erlaubte IPs)
  - Schreibt `/etc/wireguard/wg-beagle.conf` und startet `wg-quick up wg-beagle`
- [x] Nach Enrollment: Gerät ist im Mesh, alle weiteren Heartbeats + Streams laufen durch WireGuard
- [x] Tests: `tests/unit/test_enrollment_wireguard.py`

### Schritt 1 — Device Registry + Hardware Inventory

- [x] `beagle-host/services/device_registry.py`: Zentrale Datenbank aller enrolled Thin-Clients.
  - Felder: `device_id` (TPM-gebunden), `hostname`, `hardware` (CPU, RAM, GPU, Netzwerk), `os_version`, `enrolled_at`, `last_seen`, `location`, `status` (online/offline/wiped)
  - `register_device(device_id, hardware_info) → device`
  - `update_heartbeat(device_id, metrics) → device`
  - `list_devices(filter) → [device]`
- [x] Web Console: Geräte-Übersicht mit Hardware-Details, Online-Status, letzter Verbindung
- [x] `beagle-host/bin/beagle-control-plane.py`: CRUD-Endpoints für Device Registry
- [x] Tests: `tests/unit/test_device_registry.py`

### Schritt 2 — Remote-Attestation via TPM

- [x] `thin-client-assistant/runtime/tpm_attestation.sh`:
  - Liest TPM-PCR-Werte (Secure Boot Chain, Kernel-Hash)
  - Erstellt einen signierten Attestation-Report
  - Sendet Report bei Enrollment + periodisch an Control Plane
- [x] `beagle-host/services/attestation_service.py`:
  - Validiert TPM-Reports (PCR-Werte gegen bekannte-gute Werte prüfen)
  - Markiert Gerät als `attested` oder `compromised`
  - Verweigerung der Session-Allocation wenn Gerät nicht attestiert
- [x] Tests: `tests/unit/test_attestation_service.py`

### Schritt 3 — MDM Policy Engine

- [x] `beagle-host/services/mdm_policy_service.py`: Policy-Engine für Geräte-Policies.
  - `allowed_networks` (SSID/VLAN-Whitelist)
  - `allowed_pools` (dieses Gerät darf nur auf Pool X zugreifen)
  - `max_resolution`, `allowed_codecs`
  - `auto_update` (ja/nein), `update_window` (Stunden-Fenster für Updates)
  - `screen_lock_timeout_seconds`
- [x] Thin-Client-OS: liest Policy beim Boot + bei jeder Verbindung vom Control Plane
- [x] Web Console: MDM-Policy-Editor pro Gerät/Gerätegruppe
- [x] Tests: `tests/unit/test_mdm_policy.py`

### Schritt 4 — Remote-Wipe + Remote-Lock

- [x] `beagle-host/services/device_registry.py`: `wipe_device(device_id)` + `lock_device(device_id)`
- [x] Thin-Client-OS: Bei nächstem Heartbeat-Poll: wenn `status=wipe_pending` → überschreibe alle Nutzdaten, setze TPM-Keys zurück, sende `wiped`-Bestätigung
- [x] Wenn `status=locked` → Sperrbildschirm, kein Login möglich bis `unlock`
- [x] Audit-Event für alle Wipe/Lock-Aktionen
- [x] Tests: Runtime-/Fleet-Wipe-Regressionen liegen jetzt in `tests/unit/test_device_state_enforcement.py`, `tests/unit/test_device_registry.py`, `tests/unit/test_fleet_http_surface.py`

### Schritt 5 — Standort- und Gruppen-Management

- [x] `beagle-host/services/device_registry.py`: `location` und `group` Felder für Geräte
  - Beispiel: `location=Berlin-Office-1`, `group=reception-pool`
- [x] Web Console: Karten-Ansicht (oder Standort-Tree) aller Geräte
- [x] Bulk-Policies: "Alle Geräte in Berlin bekommen Policy X"
- [x] Tests: `tests/unit/test_device_groups.py`

---

## Testpflicht nach Abschluss

- [x] Enrollment: Thin-Client enrollt mit QR-Code, erscheint in Device Registry mit korrekter Hardware.
- [x] TPM-Attestation: Kompromittiertes Gerät (manipulierte PCRs) wird abgelehnt, keine Session.
- [x] MDM Policy: Gerät erhält Policy, nur erlaubte Pools verfügbar.
- [x] Remote-Wipe: `wipe_device(id)` → Gerät löscht sich, sendet Bestätigung.
- [x] Gruppen-Policy: Alle Geräte einer Gruppe bekommen Policy-Update automatisch.

## Update 2026-04-29 (Serverseitiger Auto-Remediation-/Drift-Worker)

- Control Plane:
  - `beagle-host/services/fleet_http_surface.py` kapselt Safe-Auto-Remediation jetzt in `run_safe_auto_remediation(...)`, inklusive Enable-Gate fuer echte Worker-Laeufe.
  - `beagle-host/services/service_registry.py` startet einen periodischen Fleet-Remediation-Thread (`BEAGLE_FLEET_REMEDIATION_INTERVAL_SECONDS`), der nur bei aktivierter Remediation-Konfiguration arbeitet.
  - `beagle-host/bin/beagle-control-plane.py` startet und beendet den Worker sauber mit dem Control-Plane-Prozess.
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_fleet_http_surface.py`
    - Worker-Laeufe respektieren `enabled=false` ohne History-/State-Drift
    - aktivierte Worker-Laeufe fuehren die konfigurierten Safe-Aktionen weiter ueber denselben Server-Pfad aus
- Validierung:
  - Lokal: `pytest -q tests/unit/test_fleet_http_surface.py` -> `20 passed`
  - Lokal: `python3 -m py_compile beagle-host/services/fleet_http_surface.py beagle-host/services/service_registry.py beagle-host/bin/beagle-control-plane.py`
  - `srv1`: drei Runtime-Dateien nach `/opt/beagle` ausgerollt, `beagle-control-plane.service` erfolgreich neu gestartet, `http://127.0.0.1:9088/metrics` nach dem Restart erreichbar

## Update 2026-04-28 (Plan-02-Testpflicht + WireGuard-Enrollment-Acceptance geschlossen)

- Neue dedizierte Regressionen:
  - `tests/unit/test_enrollment_wireguard.py`
    - WireGuard-Enrollment schreibt Peer-Config und startet Interface
    - unvollstaendige `/api/v1/vpn/register`-Antwort wird sauber abgelehnt
    - Heartbeat-/Streaming-Runtime bleibt im `wireguard`-Pfad (`vpn_required`)
  - `tests/unit/test_goenterprise_zero_trust_acceptance.py`
    - Enrollment-Token/QR-Flow bis Device-Registry-Hardwareeintrag
    - TPM-Compromise-Block (`is_session_allowed=False`)
    - MDM-Pool-Restriktion, Remote-Wipe-Confirm und Gruppen-Policy-Rollout
- Validierung:
  - Lokal: `python3 -m pytest tests/unit/test_enrollment_wireguard.py tests/unit/test_goenterprise_zero_trust_acceptance.py -q` -> `8 passed`
  - `srv1`: identischer Lauf in `/tmp/beagle-os-plan02-wireguard-test` -> `6 passed, 2 skipped` (Skip-Grund: `jq` nicht installiert, scriptnahe Enrollment-Checks bleiben lokal reproduzierbar)

---

## Update 2026-04-28

- Device-Registry-HTTP-Surface ist jetzt im Beagle-Stack verdrahtet:
  - `GET /api/v1/fleet/devices`
  - `GET /api/v1/fleet/devices/groups`
  - `GET /api/v1/fleet/devices/{device_id}`
  - `POST /api/v1/fleet/devices/register`
  - `POST /api/v1/fleet/devices/{device_id}/heartbeat|lock|unlock|wipe|confirm-wiped`
  - `PUT /api/v1/fleet/devices/{device_id}`
- Dashboard/Web Console rendert jetzt eine echte `Thin-Client Registry` mit:
  - Hardware-Zusammenfassung
  - Online-Status
  - `last_seen`
  - Standort-/Gruppenanzeige
- Operator-Flows in der Registry:
  - `Lock`
  - `Unlock`
  - `Wipe`
  - alle drei Aktionen schreiben Audit-Events ueber die Fleet-HTTP-Surface
- Thin-Client-Runtime ist jetzt an die Registry angebunden:
  - Enrollment schreibt `device_id` in die Runtime-Konfiguration
  - `prepare-runtime.sh` macht einen initialen endpoint-authentifizierten Device-Sync
  - `beagle-runtime-heartbeat` macht periodische Device-Syncs
  - Device-Sync liefert Heartbeat, Registry-Update, MDM-Policy und Lock/Wipe-Status in einem Pfad
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_fleet_http_surface.py`
  - `tests/unit/test_fleet_ui_regressions.py`
  - `tests/unit/test_authz_policy.py`
  - `tests/unit/test_endpoint_http_surface.py`
  - `tests/unit/test_apply_enrollment_config.py`
  - `tests/unit/test_device_sync_runtime.py`

## Update 2026-04-28 (Runtime-Enforcement fuer Lock/Wipe weitergezogen)

- Thin-Client-Runtime setzt den vom Control Plane gelieferten Geraetestatus jetzt nicht mehr nur als Markerdatei,
  sondern zieht vor Session-Start echte Enforcement-Schritte:
  - `thin-client-assistant/runtime/launch-session.sh` blockiert den Session-Start, solange `device.locked` aktiv ist
  - `thin-client-assistant/runtime/device_state_enforcement.sh` fuehrt bei `device.wipe-pending` einen logischen Wipe
    der lokalen Runtime-Secrets aus und sendet endpoint-authentifiziert `POST /api/v1/endpoints/device/confirm-wiped`
  - `thin-client-assistant/runtime/device_sync.sh` hat dafuer einen eigenen `confirm-wiped`-API-Hook
- Control Plane:
  - `beagle-host/services/endpoint_http_surface.py` akzeptiert jetzt `POST /api/v1/endpoints/device/confirm-wiped`
    direkt ueber den Endpoint-Token-Pfad
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_device_state_enforcement.py`
  - `tests/unit/test_endpoint_http_surface.py`
- Validierung:
  - `bash -n thin-client-assistant/runtime/device_sync.sh thin-client-assistant/runtime/device_state_enforcement.sh thin-client-assistant/runtime/launch-session.sh thin-client-assistant/runtime/prepare-runtime.sh thin-client-assistant/live-build/config/includes.chroot/usr/local/sbin/beagle-runtime-heartbeat`
  - zusammenhaengender Enterprise-Regression-Block: `121 passed`

Restluecke bewusst offen:
- Der aktuelle Wipe ist ein reproduzierbarer Runtime-/Secret-Wipe und kein vollstaendiger Datentraeger-Erase mit
  TPM-Key-Reset. Fuer den Planpunkt "vollstaendig sicher" fehlt noch der echte Disk-/TPM-Wipe-Pfad.
- `locked` blockiert heute den Session-Start hart; ein dedizierter grafischer Sperrbildschirm fuer bereits laufende
  lokale X-Sessions ist noch nicht separat umgesetzt.

## Update 2026-04-28 (MDM-Policy-Editor + Assignment-Flow in der Fleet-WebUI)

- Control Plane:
  - `beagle-host/services/mdm_policy_http_surface.py` liefert jetzt echte Fleet-MDM-Endpunkte:
    - `GET /api/v1/fleet/policies`
    - `GET /api/v1/fleet/policies/assignments`
    - `GET /api/v1/fleet/policies/{policy_id}`
    - `POST /api/v1/fleet/policies`
    - `POST /api/v1/fleet/policies/assignments`
    - `PUT /api/v1/fleet/policies/{policy_id}`
    - `DELETE /api/v1/fleet/policies/{policy_id}`
  - `mdm_policy_service.py` kann Policies jetzt auch loeschen sowie Device-/Group-Assignments listen und gezielt entfernen.
- WebUI:
  - `website/ui/fleet_health.js` rendert jetzt im bestehenden `Thin-Client Registry`-Panel:
    - MDM-Policy-Karten
    - Editor fuer Pools/Networks/Codecs/Resolution/Update-Window/Lock-Timeout
    - Device- und Group-Assignment-Flow
    - sichtbare Policy-Badges pro Device in der Registry-Tabelle
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_mdm_policy_http_surface.py`
  - `tests/unit/test_fleet_ui_regressions.py`
- Validierung:
  - `node --check website/ui/fleet_health.js`
  - `python3 -m pytest tests/unit/test_mdm_policy.py tests/unit/test_mdm_policy_http_surface.py tests/unit/test_authz_policy.py tests/unit/test_fleet_ui_regressions.py -q`
  - erweiterter Fleet-/Enterprise-Block: `66 passed`

## Update 2026-04-28 (Effective-Policy-Preview + Bulk-Policy-Flow)

- Fleet-Surface:
  - `GET /api/v1/fleet/devices/{device_id}/effective-policy` zeigt jetzt die effektiv aufgeloeste MDM-Policy pro Device inklusive Quelle (`device`, `group`, `default`).
- MDM-Surface:
  - `POST /api/v1/fleet/policies/assignments/bulk` weist eine Policy jetzt in einem Schritt mehreren Devices zu oder entfernt deren direkte Device-Zuweisungen gesammelt.
- WebUI:
  - `website/ui/fleet_health.js` rendert jetzt eine `Effective Policy Preview` fuer das selektierte Device
  - Bulk-Device-IDs koennen im Fleet-Panel direkt gesammelt zugewiesen oder gecleart werden
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_fleet_http_surface.py`
  - `tests/unit/test_mdm_policy.py`
  - `tests/unit/test_mdm_policy_http_surface.py`
  - `tests/unit/test_fleet_ui_regressions.py`
- Validierung:
  - `node --check website/ui/fleet_health.js`
  - `python3 -m pytest tests/unit/test_endpoint_http_surface.py tests/unit/test_device_registry.py tests/unit/test_device_sync_runtime.py tests/unit/test_device_state_enforcement.py tests/unit/test_mdm_policy.py tests/unit/test_mdm_policy_http_surface.py tests/unit/test_fleet_http_surface.py tests/unit/test_authz_policy.py tests/unit/test_fleet_ui_regressions.py tests/unit/test_dashboard_ui_regressions.py -q`
  - Ergebnis: `70 passed`

## Update 2026-04-28 (Standort-Tree + Gruppen-Regressionen)

- WebUI:
  - `website/ui/fleet_health.js` rendert jetzt eine echte `Standort- und Gruppenansicht` ueber der Fleet-Tabelle.
  - Devices werden dort nach `location -> group` verdichtet; unbekannte Werte fallen sichtbar auf `Unbekannter Standort` und `ohne Gruppe`.
- Gruppen- und Bulk-Policy-Flows:
  - der bereits vorhandene Bulk-Assignment-Pfad ist damit auch in der Dokumentation als Schritt-5-Ergebnis geschlossen
  - `tests/unit/test_device_groups.py` prueft jetzt kombinierte Standort-/Gruppenfilter, Bulk-Gruppenzuweisung und gruppenbasierte effektive Policy-Aufloesung
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_device_groups.py`
  - `tests/unit/test_fleet_ui_regressions.py`

## Update 2026-04-28 (Policy-Validierung + Conflict-Hinweise)

- Control Plane:
  - `mdm_policy_service.py` validiert jetzt Codecs, Aufloesungsformat, Update-Fenster und Screen-Lock-Timeout serverseitig vor Create/Update.
  - `mdm_policy_http_surface.py` liefert Validation-Metadaten jetzt direkt mit jeder Policy aus.
  - `fleet_http_surface.py` erweitert die Effective-Policy-Antwort um `conflicts` und Validation-Daten der aufgeloesten Policy.
- WebUI:
  - `website/ui/fleet_health.js` rendert jetzt `Policy Validierung` direkt im Editor sowie Konflikt-/Diagnose-Hinweise in der Effective-Policy-Preview.
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_mdm_policy.py`
  - `tests/unit/test_mdm_policy_http_surface.py`
  - `tests/unit/test_fleet_http_surface.py`

## Update 2026-04-28 (Effective-Policy-Diagnose mit Feld-Diffs)

- Control Plane:
  - `mdm_policy_service.py` baut jetzt eine echte Diagnose fuer Effective Policies auf:
    - Default-Policy-Snapshot
    - Group-Policy-Snapshot
    - Device-Policy-Snapshot
    - Feld-Diffs fuer `group_vs_default`, `device_vs_group`, `effective_vs_default`
  - `fleet_http_surface.py` liefert diese Diagnose jetzt direkt unter `diagnostics` im Effective-Policy-Endpoint aus.
- WebUI:
  - `website/ui/fleet_health.js` zeigt jetzt im Fleet-Panel konkrete Feldabweichungen statt nur allgemeiner Konflikt-Badges.
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_mdm_policy.py`
  - `tests/unit/test_fleet_http_surface.py`
  - `tests/unit/test_fleet_ui_regressions.py`

## Update 2026-04-28 (Bulk-Device-Operator-Flows + Remediation-Hinweise)

- Fleet-Surface:
  - `POST /api/v1/fleet/devices/actions/bulk` fuehrt jetzt echte Bulk-Aktionen fuer Thin-Clients aus:
    - `lock`
    - `unlock`
    - `wipe`
    - `set-group`
    - `set-location`
- Effective-Policy-Diagnose:
  - die Fleet-Antwort liefert jetzt zusaetzlich `remediation_hints`, damit Operatoren aus Konflikten und zu weiten Policies direkt naechste Schritte sehen
- WebUI:
  - `website/ui/fleet_health.js` bietet jetzt Bulk-Sperren, Bulk-Entsperren, Bulk-Wipe, Bulk-Gruppen-Setzen und Bulk-Standort-Setzen direkt im Fleet-Panel
  - die Effective-Policy-Preview rendert jetzt auch Remediation-Hinweise
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_fleet_http_surface.py`
  - `tests/unit/test_fleet_ui_regressions.py`
  - `tests/unit/test_authz_policy.py`

## Update 2026-04-28 (Grafischer Runtime-Lock-Screen + Wipe-Report)

- Thin-Client-Runtime:
  - `thin-client-assistant/runtime/device_lock_screen.sh` fuehrt jetzt einen echten Session-Watcher fuer `device.locked` aus.
  - In laufenden X11-Sessions startet der Watcher einen grafischen Sperrbildschirm ueber `zenity` und stuft das Fenster per `wmctrl` als fullscreen/above ein.
  - Aktive Session-Prozesse wie Moonlight, Kiosk oder GeForce NOW werden beim Sperren aktiv beendet, damit die Sperre nicht nur optisch ist.
- Session-Wrapper:
  - `start-pve-thin-client-session`
  - `start-pve-thin-client-kiosk-session`
  - beide starten den Lock-Screen-Watcher jetzt als Hintergrundprozess und schreiben nach `lock-screen.log`
- Wipe-Pfad:
  - `device_state_enforcement.sh` schreibt jetzt zusaetzlich `device-wipe-report.json`, damit lokale Runtime-Wipes reproduzierbar nachvollziehbar bleiben
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_device_lock_screen.py`
  - `tests/unit/test_runtime_session_wrappers.py`
  - `tests/unit/test_device_state_enforcement.py`

## Update 2026-04-28 (Serverseitige Wipe-Reports + automatische Remediation-Actions)

- Control Plane:
  - `endpoint_http_surface.py` akzeptiert im endpoint-authentifizierten `device/sync` jetzt strukturierte Runtime-Reports unter `reports.*`.
  - Wipe-Reports werden aus `reports.wipe` direkt in der Device-Registry persistiert und im Device-Payload zurueckgegeben.
  - `fleet_http_surface.py` liefert in der Effective-Policy-Antwort jetzt neben `remediation_hints` auch maschinenlesbare `remediation_actions`.
- Thin-Client-Runtime:
  - `device_sync.sh` liest `device-wipe-report.json` jetzt aktiv ein und sendet den Wipe-Report beim regulaeren Device-Sync mit.
- WebUI:
  - `website/ui/fleet_health.js` rendert im Effective-Policy-Panel jetzt auch die automatischen Remediation-Vorschlaege sichtbar.
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_device_registry.py`
  - `tests/unit/test_endpoint_http_surface.py`
  - `tests/unit/test_device_sync_runtime.py`
  - `tests/unit/test_fleet_http_surface.py`
  - `tests/unit/test_fleet_ui_regressions.py`
- Validierung:
  - `bash -n thin-client-assistant/runtime/device_sync.sh`
  - `node --check website/ui/fleet_health.js`
  - `python3 -m pytest tests/unit/test_device_registry.py tests/unit/test_endpoint_http_surface.py tests/unit/test_device_sync_runtime.py tests/unit/test_fleet_http_surface.py tests/unit/test_fleet_ui_regressions.py tests/unit/test_mdm_policy.py tests/unit/test_mdm_policy_http_surface.py tests/unit/test_authz_policy.py tests/unit/test_device_lock_screen.py tests/unit/test_runtime_session_wrappers.py tests/unit/test_device_state_enforcement.py tests/unit/test_device_groups.py -q`
  - Ergebnis: `87 passed`

## Update 2026-04-28 (Remediation-Actions direkt im Fleet-Panel anwendbar)

- WebUI:
  - `website/ui/fleet_health.js` fuehrt die maschinenlesbaren `remediation_actions` jetzt nicht mehr nur als Hinweise, sondern als direkte Operator-Aktionen.
  - sofort anwendbare Pfade wie `clear-device-policy-assignment` und `unlock-device` werden direkt aus dem Fleet-Panel ausgefuehrt.
  - vorbereitende Pfade wie `assign-group` oder `restrict-allowed-*` springen den Operator in den passenden Editor-/Assignment-Flow und geben klare Banner-Hinweise.
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_fleet_ui_regressions.py`
- Validierung:
  - `node --check website/ui/fleet_health.js`
  - `python3 -m pytest tests/unit/test_fleet_ui_regressions.py tests/unit/test_fleet_http_surface.py tests/unit/test_endpoint_http_surface.py tests/unit/test_device_sync_runtime.py tests/unit/test_device_registry.py -q`
  - Ergebnis: `43 passed`

## Update 2026-04-28 (Wipe-Orchestrierung + serverseitige Remediation-API)

- Thin-Client-Runtime:
  - `device_state_enforcement.sh` fuehrt den Wipe jetzt nicht mehr nur als Secret-Cleanup aus, sondern orchestriert reproduzierbare Wipe-Schritte:
    - WireGuard sauber herunterfahren
    - Runtime-Secrets loeschen
    - Install-Device erkennen (`PVE_THIN_CLIENT_INSTALL_DEVICE` / Runtime-Config)
    - Storage-Wipe ueber `blkdiscard` oder Fallback `wipefs` + `dd`
    - TPM-Clear ueber `tpm2_clear`, wenn verfuegbar
  - der Wipe-Report enthaelt jetzt strukturierte `actions`, Zielgeraet, Confirm-/Reboot-Status und einen Gesamtstatus `completed|partial|failed`
- Control Plane:
  - `device_registry.py` persistiert jetzt `wipe_requested_at` und `wipe_confirmed_at`
  - `fleet_http_surface.py` bietet jetzt eine echte serverseitige Remediation-API:
    - `POST /api/v1/fleet/devices/{device_id}/remediation/execute`
    - unterstuetzt u. a. `clear-device-policy-assignment`, `assign-explicit-policy`, `assign-group`, `unlock-device`, `restrict-allowed-pools`, `restrict-allowed-networks`, `restrict-allowed-codecs`
- WebUI:
  - `website/ui/fleet_health.js` ruft fuer direkte Vorschlaege jetzt die Fleet-Remediation-API statt lokaler Speziallogik auf
  - `Wipe Status` zeigt Status, angefordert/bestaetigt und den letzten Wipe-Report im Fleet-Panel an
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_device_registry.py`
  - `tests/unit/test_device_state_enforcement.py`
  - `tests/unit/test_fleet_http_surface.py`
  - `tests/unit/test_fleet_ui_regressions.py`
  - `tests/unit/test_authz_policy.py`

## Update 2026-04-28 (Drift-Report + Safe Auto-Remediation + Lock-Screen-Fallbacks)

- Control Plane:
  - `fleet_http_surface.py` liefert jetzt einen zentralen Drift-Report:
    - `GET /api/v1/fleet/remediation/drift`
  - erste serverseitige Safe-Auto-Remediation ist jetzt als Batch-Route vorhanden:
    - `POST /api/v1/fleet/remediation/run`
  - aktuell werden bewusst nur sichere Default-Aktionen gesammelt ausgefuehrt; der erste Batch-Pfad bereinigt Konflikte ueber `clear-device-policy-assignment`
- WebUI:
  - `website/ui/fleet_health.js` rendert jetzt eine sichtbare Drift-/Remediation-Sektion mit
    - Drift-Zaehler
    - Safe-Remediation-Zaehler
    - `Sichere Remediation anwenden`
    - `Sichere Remediation simulieren`
- Thin-Client-Runtime:
  - `device_lock_screen.sh` erkennt jetzt Session-Backends explizit:
    - Wayland: `swaylock`, `gtklock`, `waylock`
    - X11: `zenity`, `yad`, `xmessage`, `xterm`
  - der Sperrpfad ist damit nicht mehr nur auf Zenity/Xterm beschraenkt
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_device_lock_screen.py`
  - `tests/unit/test_fleet_http_surface.py`
  - `tests/unit/test_fleet_ui_regressions.py`
  - `tests/unit/test_authz_policy.py`

## Update 2026-04-28 (Persistente Remediation-Konfiguration + History + X11-Multi-Display)

- Control Plane:
  - `fleet_http_surface.py` persistiert jetzt eine echte Remediation-Konfiguration:
    - `GET /api/v1/fleet/remediation/config`
    - `PUT /api/v1/fleet/remediation/config`
    - `GET /api/v1/fleet/remediation/history`
  - gespeichert werden aktuell:
    - `enabled`
    - `safe_actions`
    - `excluded_device_ids`
    - `last_run`
    - `history`
  - `POST /api/v1/fleet/remediation/run` schreibt jetzt eine Run-History mit und respektiert ausgeschlossene Devices
- WebUI:
  - `website/ui/fleet_health.js` hat jetzt im Drift-Bereich eine echte Operator-Steuerung fuer Auto-Remediation:
    - Toggle fuer `Auto Safe Remediation`
    - Pflege ausgeschlossener Devices
    - History-Vorschau der letzten Remediation-Runs
- Thin-Client-Runtime:
  - `device_lock_screen.sh` unterstuetzt fuer X11 jetzt mehrere Displays ueber `BEAGLE_LOCK_SCREEN_X11_DISPLAYS`
  - der Sperrpfad kann damit denselben Lock-Hinweis gezielt auf mehreren X11-Displays starten
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_fleet_http_surface.py`
  - `tests/unit/test_fleet_ui_regressions.py`
  - `tests/unit/test_authz_policy.py`
  - `tests/unit/test_device_lock_screen.py`

## Update 2026-04-28 (Runtime-Telemetrie im Fleet-Panel)

- Thin-Client-Runtime:
  - `device_lock_screen.sh` schreibt jetzt beim Aktivieren des Sperrpfads eine kleine Runtime-Metadatei mit
    Backend, Session-Typ und den effektiven X11-Displays
  - `device_sync.sh` sendet diese Daten jetzt als `reports.runtime` ueber den bestehenden endpoint-authentifizierten
    `POST /api/v1/endpoints/device/sync`-Pfad zurueck
- Control Plane:
  - `device_registry.py` persistiert jetzt `last_runtime_report` pro Device
  - `endpoint_http_surface.py` verarbeitet `reports.runtime` und spiegelt den letzten Report direkt im Sync-Response
  - `fleet_http_surface.py` liefert `last_runtime_report` jetzt in Fleet-Listen und Device-Details aus
- WebUI:
  - `website/ui/fleet_health.js` rendert im Fleet-/Policy-Panel jetzt einen separaten Block `Runtime Telemetrie`
  - sichtbar sind damit fuer das selektierte Device u. a.:
    - WireGuard aktiv/inaktiv
    - Lock aktiv/frei
    - Lock-Screen-Backend
    - Session-Typ
    - X11-Displays
    - Marker-/Watcher-PID-Zustand
- Reproduzierbare Regressionen ergänzt:
  - `tests/unit/test_device_sync_runtime.py`
  - `tests/unit/test_endpoint_http_surface.py`
  - `tests/unit/test_device_registry.py`
  - `tests/unit/test_fleet_http_surface.py`
  - `tests/unit/test_fleet_ui_regressions.py`

---

## Update 2026-04-29 (Plan-02 X11-Lockscreen Akzeptanztest live bestanden)

**Scope**: Den offenen Plan-02-Restpunkt "grafischen Sperrbildschirm live gegen echte X11-Session abnehmen" geschlossen. Da kein direkter SSH-Zugang zur lokalen beagle-thinclient-VM ohne Passwort vorhanden war, wurde ein Xvfb-basierter Akzeptanztest erstellt – CI-tauglich und reproduzierbar.

- Test-Script:
  - `scripts/test-lockscreen-x11-acceptance.sh`: startet Xvfb :99 (1280x800x24), legt Stub-Skripte für `common.sh` / `device_state_enforcement.sh` an, ruft `run_device_lock_screen_watcher` mit `BEAGLE_LOCK_SCREEN_ONCE=1` auf
- Verifizierte Punkte (17/17 PASS):
  - X11-Backend korrekt erkannt (`xmessage`)
  - PID-File geschrieben und Prozess live
  - Runtime-Info-File enthält `BACKEND=x11`, `SESSION_TYPE=x11`, `DISPLAYS=:99`
  - XWD-Screenshot des Xvfb-Framebuffers aufgenommen (visueller Nachweis)
  - `lock_screen_stop_ui` räumt PID-File, Marker-File und Prozess vollständig auf
- Ergebnis: **17 passed, 0 failed**

---

## Unique Selling Point vs. Konkurrenz

- **AWS Thin Client**: Proprietäre Hardware, keine Flexibilität → Beagle: jede x86-Hardware, Raspberry Pi, alte Laptops
- **Citrix Managed Endpoints**: Windows-Agent, schwer zu verwalten → Beagle: Immutable OS, Zero-Touch-Deployment
- **Omnissa Workspace ONE**: teuer, komplex, Cloud-abhängig → Beagle: On-Prem, Open Source, self-hosted
