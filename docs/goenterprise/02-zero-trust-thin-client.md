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
- [ ] Nach Enrollment: Gerät ist im Mesh, alle weiteren Heartbeats + Streams laufen durch WireGuard
- [ ] Tests: `tests/unit/test_enrollment_wireguard.py`

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
- [ ] Thin-Client-OS: Bei nächstem Heartbeat-Poll: wenn `status=wipe_pending` → überschreibe alle Nutzdaten, setze TPM-Keys zurück, sende `wiped`-Bestätigung
- [ ] Wenn `status=locked` → Sperrbildschirm, kein Login möglich bis `unlock`
- [x] Audit-Event für alle Wipe/Lock-Aktionen
- [ ] Tests: `tests/unit/test_device_wipe.py`

### Schritt 5 — Standort- und Gruppen-Management

- [x] `beagle-host/services/device_registry.py`: `location` und `group` Felder für Geräte
  - Beispiel: `location=Berlin-Office-1`, `group=reception-pool`
- [x] Web Console: Karten-Ansicht (oder Standort-Tree) aller Geräte
- [x] Bulk-Policies: "Alle Geräte in Berlin bekommen Policy X"
- [x] Tests: `tests/unit/test_device_groups.py`

---

## Testpflicht nach Abschluss

- [ ] Enrollment: Thin-Client enrollt mit QR-Code, erscheint in Device Registry mit korrekter Hardware.
- [ ] TPM-Attestation: Kompromittiertes Gerät (manipulierte PCRs) wird abgelehnt, keine Session.
- [ ] MDM Policy: Gerät erhält Policy, nur erlaubte Pools verfügbar.
- [ ] Remote-Wipe: `wipe_device(id)` → Gerät löscht sich, sendet Bestätigung.
- [ ] Gruppen-Policy: Alle Geräte einer Gruppe bekommen Policy-Update automatisch.

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

---

## Unique Selling Point vs. Konkurrenz

- **AWS Thin Client**: Proprietäre Hardware, keine Flexibilität → Beagle: jede x86-Hardware, Raspberry Pi, alte Laptops
- **Citrix Managed Endpoints**: Windows-Agent, schwer zu verwalten → Beagle: Immutable OS, Zero-Touch-Deployment
- **Omnissa Workspace ONE**: teuer, komplex, Cloud-abhängig → Beagle: On-Prem, Open Source, self-hosted
