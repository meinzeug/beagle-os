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
- [ ] Web Console: Geräte-Übersicht mit Hardware-Details, Online-Status, letzter Verbindung
- [ ] `beagle-host/bin/beagle-control-plane.py`: CRUD-Endpoints für Device Registry
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
- [ ] Thin-Client-OS: liest Policy beim Boot + bei jeder Verbindung vom Control Plane
- [ ] Web Console: MDM-Policy-Editor pro Gerät/Gerätegruppe
- [x] Tests: `tests/unit/test_mdm_policy.py`

### Schritt 4 — Remote-Wipe + Remote-Lock

- [x] `beagle-host/services/device_registry.py`: `wipe_device(device_id)` + `lock_device(device_id)`
- [ ] Thin-Client-OS: Bei nächstem Heartbeat-Poll: wenn `status=wipe_pending` → überschreibe alle Nutzdaten, setze TPM-Keys zurück, sende `wiped`-Bestätigung
- [ ] Wenn `status=locked` → Sperrbildschirm, kein Login möglich bis `unlock`
- [ ] Audit-Event für alle Wipe/Lock-Aktionen
- [ ] Tests: `tests/unit/test_device_wipe.py`

### Schritt 5 — Standort- und Gruppen-Management

- [x] `beagle-host/services/device_registry.py`: `location` und `group` Felder für Geräte
  - Beispiel: `location=Berlin-Office-1`, `group=reception-pool`
- [ ] Web Console: Karten-Ansicht (oder Standort-Tree) aller Geräte
- [ ] Bulk-Policies: "Alle Geräte in Berlin bekommen Policy X"
- [ ] Tests: `tests/unit/test_device_groups.py`

---

## Testpflicht nach Abschluss

- [ ] Enrollment: Thin-Client enrollt mit QR-Code, erscheint in Device Registry mit korrekter Hardware.
- [ ] TPM-Attestation: Kompromittiertes Gerät (manipulierte PCRs) wird abgelehnt, keine Session.
- [ ] MDM Policy: Gerät erhält Policy, nur erlaubte Pools verfügbar.
- [ ] Remote-Wipe: `wipe_device(id)` → Gerät löscht sich, sendet Bestätigung.
- [ ] Gruppen-Policy: Alle Geräte einer Gruppe bekommen Policy-Update automatisch.

---

## Unique Selling Point vs. Konkurrenz

- **AWS Thin Client**: Proprietäre Hardware, keine Flexibilität → Beagle: jede x86-Hardware, Raspberry Pi, alte Laptops
- **Citrix Managed Endpoints**: Windows-Agent, schwer zu verwalten → Beagle: Immutable OS, Zero-Touch-Deployment
- **Omnissa Workspace ONE**: teuer, komplex, Cloud-abhängig → Beagle: On-Prem, Open Source, self-hosted
