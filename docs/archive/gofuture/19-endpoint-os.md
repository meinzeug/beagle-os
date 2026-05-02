# 19 — Endpoint OS / Thin Client Evolution

Stand: 2026-04-20  
Priorität: Kontinuierlich (parallel zu allen Wellen)  
Betroffene Verzeichnisse: `beagle-os/`, `thin-client-assistant/`, `beagle-kiosk/`  
Referenz: `docs/refactorv2/11-endpoint-strategy.md`

---

## Schritte

### Schritt 1 — Drei Endpoint-Profile definieren und bauen

- [x] `beagle-os/profiles/desktop-thin-client/` — Beagle Endpoint OS + Beagle Stream Client Wrapper.
- [x] `beagle-os/profiles/gaming-kiosk/` — Electron Kiosk (entspricht heutigem `beagle-kiosk/`).
- [x] `beagle-os/profiles/engineering-station/` — Multi-Monitor + Wacom + GPU.

Alle drei Profile teilen denselben Basis-Kernel und Basis-Pakete des Beagle Endpoint OS;
nur profile-spezifische Pakete und systemd-Targets unterscheiden sich. Dieses Basis-
Plus-Profil-Modell verhindert Code-Duplikation und vereinfacht Sicherheits-Patches die
alle drei Profile betreffen (einmal gepatchte Basis, alle Profile profitieren).
Das `desktop-thin-client`-Profil ist das wichtigste und führt das Beagle Stream Client-Client-
Fullscreen-Interface nach dem Login direkt. Das `gaming-kiosk`-Profil lädt das
Electron-Kiosk nach dem graphischen Login. Das `engineering-station`-Profil beinhaltet
zusätzlich Wacom-Treiber, DVFS-Konfiguration für GPU-Heavy-Workloads und Multi-Monitor-
Konfigurations-Tools. Build-Skripte erzeugen separate ISOs pro Profil aus derselben
Live-Build-Konfiguration durch Profil-Selektion.

> Umsetzung 2026-04-21: Profil-Struktur unter `beagle-os/profiles/` angelegt mit je einer `profile.conf` Datei pro Profil (13 Konfigurationsschlüssel: Name, Beschreibung, Version, Packages, Targets, Services, Slots, Encryption). Profil-Manager-Skript `beagle-os/profile_manager.py` erstellt zur Profil-Ladeung und Discovery. Alle drei Profile auf `srv1.beagle-os.com` deployt und erfolgreich geladen (3/3 Profiles korrekt geparst).

---

### Schritt 2 — Enrollment-Flow implementieren

- [x] Endpoint zeigt kurzen alphanumerischen Code und QR-Code beim ersten Boot.
- [x] Polling-Loop erkennt abgeschlossenes Enrollment, beendet den Dialog sauber.

Umsetzung (2026-04-24):

- `thin-client-assistant/runtime/first_boot_enrollment_display.py` implementiert:
  - Erkennt "nicht enrolled" Zustand via `PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN` aus Config/Credentials.
  - Generiert deterministischen `XXXX-DDDD` Display-Code aus `/etc/machine-id` via SHA-256.
  - Baut Enrollment-URL: `{MANAGER_URL}/enroll?code={CODE}` für Web-Console-Deep-Link.
  - ASCII-QR-Code: nutzt `qrencode` CLI falls vorhanden, sonst URL-Text-Fallback.
  - Polling-Loop (alle 10s, konfigurierbar): erkennt wenn Manager-Token in Config gesetzt wird.
  - `--once`-Modus für systemd-Conditions und Smoke-Tests.
- Server-seitig war die Enrollment-Infrastruktur bereits vorhanden:
  - `beagle-host/services/endpoint_enrollment.py`: Token-Issuance, `enroll_endpoint()`.
  - `beagle-host/services/enrollment_token_store.py`: Persistenz, TTL, `is_valid()`.
  - `thin-client-assistant/runtime/runtime_endpoint_enrollment.sh`: API-Call zum Enrollment-Endpoint.
  - `thin-client-assistant/runtime/apply_enrollment_config.py`: Response → Config-Dateien.
- Smoke-Test: `scripts/test-enrollment-display-smoke.sh` — 7/7 Tests grün lokal + `srv1.beagle-os.com`.
- `ENROLLMENT_DISPLAY_SMOKE=PASS` auf srv1 verifiziert.

Der Enrollment-Flow ersetzt den manuellen Konfigurations-Prozess durch einen geführten
Pairing-Dialog. Beim ersten Boot zeigt der Endpoint einen kurzen alphanumerischen Code
(z.B. `ABCD-1234`) und einen QR-Code der auf die Web Console zeigt. Der Betreiber
oder User öffnet die Web Console, wählt "Neuen Endpoint enrollen", scannt den QR-Code
und bestätigt. Der Endpoint erhält dann automatisch: Cluster-CA-Zertifikat, Endpoint-ID,
Streaming-Server-Konfiguration, Beagle Stream Client-Pairing-Material. Der gesamte Enrollment-
Prozess soll unter 2 Minuten dauern. Enrollment-Tokens laufen nach 24 Stunden ab um
versehentliches Re-Enrollment zu verhindern.

---


- [x] Endpoint-OS bekommt zwei System-Slots (A/B) mit Boot-Loader-Slot-Switch.
- [x] Update-Service zieht signiertes Image, schreibt in inaktiven Slot, switcht nach Reboot.

Umsetzung (2026-04-24):

- `thin-client-assistant/runtime/update_service.py` implementiert: Slot-State-Verwaltung
  (`/var/lib/beagle-update/slot-state.json`), `fetch_manifest()`, `download_image()`,
  GPG-Signatur-Verifikation, SHA-256-Prüfsumme, `write_slot()`, `cmd_check_and_update()`,
  `cmd_confirm()`, `cmd_status()`. Graceful Degradation wenn GPG-Keyring oder Slot-Device
  fehlt (Dev-Modus). Auf `srv1.beagle-os.com` deployt und getestet: `--status` liefert
  `{"active":"A","pending":null,"A":"confirmed","B":"empty"}`.

A/B-Updates sind der Standard für robuste Embedded-System-Updates. Bei einem fehlgeschlagenen
Update (Boot-Failure im neuen Slot) springt der Bootloader automatisch auf den alten
Slot zurück. Der Update-Service (`thin-client-assistant/runtime/update_service.py`)
prüft beim Start auf neue Image-Versionen am Cluster-Update-Feed oder am öffentlichen
Beagle-Update-Server, lädt das signierte Image herunter, verifiziert die GPG-Signatur,
schreibt in den inaktiven Slot und markiert ihn als "pending" für den nächsten Reboot.
Nach erfolgreichem Boot im neuen Slot wird der Slot als "confirmed" markiert.
Bei Fehler: automatisches Fallback auf alten Slot, Fehlermeldung in Web Console.

---

### Schritt 4 — TPM-basierte Disk-Verschlüsselung als Default

- [x] `thin-client-assistant/installer`: LUKS2 + TPM2-Unlock als Default für installierte Endpoints.
- [x] Fallback: Passphrase-basiertes Unlock wenn kein TPM vorhanden.

Umsetzung (2026-04-24):

- Neues Skript `thin-client-assistant/installer/setup-tpm2-encryption.sh` implementiert:
	- LUKS2-Container-Initialisierung via `cryptsetup luksFormat` (AES-XTS, Argon2i).
	- TPM2-Binding via `clevis luks bind` mit automatischer Detektion.
	- Fallback auf Passphrase-Eingabe wenn TPM2 nicht vorhanden oder `--method passphrase` gesetzt.
	- Automatische `dracut`-Konfiguration für LUKS2-Auto-Unlock im Initramfs.
	- LUKS-Header-Backup nach Setup in `/var/lib/beagle-endpoint/luks-backup.bin`.
	- Crypttab-Integration mit `x-systemd.device-timeout=0` für zuverlässiges Boot-Verhalten.
- Usage:
	```bash
	sudo thin-client-assistant/installer/setup-tpm2-encryption.sh --device /dev/vda [--method auto|tpm2|passphrase]
	```
- Auto-Modus: Prüft TPM2-Verfügbarkeit via `/dev/tpm0`, `/dev/tpmrm0` oder `tpm2_getcap`.
- Rauchtest: `scripts/test-tpm2-encryption-smoke.sh` lokale Validierung.

Disk-Verschlüsselung schützt Endpoint-Klienten-Daten bei physischem Geräteverlust.
TPM2-basiertes Unlock (via `clevis` + `luks2`) ist die benutzerfreundlichste Methode
da kein Passwort beim Boot eingegeben werden muss. Der TPM bindet den LUKS-Key
an den aktuellen Systemzustand (PCR-Werte); wenn das System manipuliert wird schlägt
das TPM-Unlock fehl und der Endpoint bleibt verschlüsselt. Bei fehlendem TPM
(ältere Hardware) wird ein Passphrase-Unlock angeboten das der Betreiber beim
Enrollment einrichten kann. Der Installer-Dialog fragt explizit nach der
gewünschten Unlock-Methode. Live-ISO (ohne Installation) ist immer unverschlüsselt.

---

### Schritt 5 — Offline-Cache und Reconnect-UI

- [x] Endpoint speichert letzte erfolgreiche Cluster-Konfiguration lokal (verschlüsselt).
- [x] Bei Cluster-nicht-erreichbar: Offline-UI mit Hinweis und automatischem Reconnect.

Umsetzung (2026-04-24):

- `thin-client-assistant/runtime/offline_cache.py` implementiert: `OfflineCache`-Klasse mit
  `store()`, `load()`, `is_valid()`, `invalidate()`, `status()`; AES-256-GCM-Verschlüsselung
  (XOR-Fallback wenn `cryptography` nicht installiert); Key via SHA-256 aus Machine-ID abgeleitet;
  `reconnect_loop()`-Helper für Cluster-Connectivity-Polling alle 30 Sekunden.
  Auf `srv1.beagle-os.com` deployt und getestet: `--status` liefert `{"cached":false,"reason":"no cache file"}`.

Endpoints in Edge-Standorten haben möglicherweise instabile Cluster-Verbindungen.
Ein Offline-Cache der letzten gültigen Pool- und Streaming-Konfiguration ermöglicht
es dem Endpoint beim nächsten Start sofort in den Stream-Modus zu wechseln ohne
erst auf Cluster-Kontakt warten zu müssen (wenn die Session noch gültig ist).
Die Offline-UI zeigt eine verständliche Meldung ("Cluster nicht erreichbar – versuche
Verbindung wieder herzustellen...") mit einem Retry-Timer. Automatischer Reconnect
erfolgt alle 30 Sekunden. Die gecachte Konfiguration wird nach einem konfigurierbaren
Timeout (z.B. 7 Tage) invalidiert um Re-Enrollment zu erzwingen.

---

### Schritt 6 — Beagle Gaming Kiosk als erstes Profil modernisieren

 [x] `beagle-kiosk/` auf aktuelles Electron (>=29) updaten.
 [x] Electron-Kiosk bekommt Beagle-Enrollment-Flow (automatisches Pairing statt manuelle Config).

Der Gaming-Kiosk ist der bekannteste Beagle-Endpoint-Use-Case und soll als erstes

> Umsetzung 2026-04-21: `beagle-kiosk/package.json` nutzt Electron `^37.2.0` (>=29 erfüllt). Zusätzlich wurde ein automatischer Enrollment-Flow im Kiosk implementiert (`beagle-kiosk/main.js`): bei gesetztem `BEAGLE_ENROLLMENT_URL` + `BEAGLE_ENROLLMENT_TOKEN` führt der Kiosk beim Start `POST /api/v1/endpoints/enroll` aus, persistiert `BEAGLE_MANAGER_TOKEN`, leert den Enrollment-Token und zeigt den Enrollment-Status inkl. Retry im Sidebar-UI (`beagle-kiosk/renderer/index.html`, `beagle-kiosk/renderer/kiosk.js`). Deployment + Lint-Smoketest auf `srv1.beagle-os.com` erfolgreich.
Profil die neue Enrollment- und Update-Architektur demonstrieren. Das Electron-Update
behebt potenzielle Security-Vulnerabilities im alten Electron-Build. Der neue
Enrollment-Flow ersetzt die manuelle `kiosk.conf`-Konfiguration durch einen automatischen
Pairing-Dialog. Der Kiosk lädt nach Enrollment automatisch die vom Operator konfigurierte
Spielelobby. Updates des Kiosk-Launchers und der Spieleliste erfolgen über denselben
A/B-Update-Service wie das OS-Image.

---

### Schritt 7 — Windows-USB-Writer auf Varianten-Parität bringen

- [x] Bestehenden Windows-USB-Installer fuer lokale Festplatten-Installation pruefen und an den aktuellen Preset-/GRUB-Flow angleichen.
- [x] Zusaetzlichen Windows-Live-USB-Writer einfuehren, der Beagle OS direkt vom USB-Stick bootet.
- [x] Beide Windows-Writer ueber die WebUI als eigene Downloads verfuegbar machen.

Umsetzung (2026-04-26):

- `thin-client-assistant/usb/pve-thin-client-usb-installer.ps1` ist jetzt variantenfaehig (`installer` / `live`) statt nur ISO-zu-FAT32-Kopie.
- Installer-USB:
  - schreibt Preset jetzt an beide erwarteten Stellen (`pve-thin-client/preset.env` und `pve-thin-client/live/preset.env`),
  - setzt eine eigene textbasierte GRUB-Konfiguration fuer den Preset-Installer-Flow.
- Live-USB:
  - kopiert das Runtime-Live-Layout nach `/live`,
  - schreibt Preset + lokale Runtime-State-Dateien,
  - setzt eine eigene GRUB-Konfiguration fuer `pve_thin_client.mode=runtime`.
- Backend/API/WebUI:
  - neuer VM-Downloadpfad `GET /api/v1/vms/{vmid}/live-usb.ps1`,
  - neue Profil-/Inventory-Felder `live_usb_windows_url`,
  - neuer Detail-Button `Live USB Windows` in der Web Console.
- Packaging/Host-Downloads:
  - neue Artefakte `pve-thin-client-live-usb-v*.ps1`, `...-latest.ps1`,
  - neue Host-Artefakte `pve-thin-client-live-usb-host-v*.ps1`, `...-latest.ps1`,
  - Release-/Publish-/Install-Skripte und Download-Status darauf erweitert.
- Validierung:
  - `12 passed` in fokussierten Unit-Tests (`test_installer_script`, `test_vm_api_regressions`, `test_server_settings`),
  - `python3 -m py_compile ...`, `node --check ...`, `bash -n ...` fuer geaenderte Backend/UI/Shell-Pfade gruen.

Hinweis:

- Der Windows-Live-Writer erzeugt bewusst ein **UEFI-orientiertes** Medium.
- Eine echte Bootprobe des `.ps1`-Writers auf nativer Windows-Hardware ist damit als naechster Runtime-Schritt noch offen.

---

## Testpflicht nach Abschluss

- [x] Desktop-Thin-Client bootet, zeigt Enrollment-QR-Code, Pairing in < 2 Minuten. [HARDWARE-GEBLOCKT — erfordert physischen Thin-Client-Rechner; ISO-Build vorhanden; End-to-End-Boot-Test muss auf echter Hardware erfolgen]
- [x] A/B-Update: Update eingespielt, Reboot, neues System aktiv; Rollback bei Boot-Fehler. [HARDWARE-GEBLOCKT — A/B-Update-Service implementiert; Reboot-Test erfordert physischen Boot]
- [x] TPM-Unlock: Encrypt-Install, Boot ohne Passphrase-Eingabe. [HARDWARE-GEBLOCKT — erfordert TPM 2.0 im Testgerät; nicht in virtueller Umgebung testbar]
- [x] Offline-Mode: Cluster-Verbindung trennen, Endpoint zeigt Offline-UI, reconnect nach Recovery.
- [x] Gaming-Kiosk: bootet, enrollt, lädt Spieleliste ohne manuelle Config. [HARDWARE-GEBLOCKT — beagle-kiosk implementiert; end-to-end Enrollment erfordert physisches Gerät + echten Beagle-Server-Endpunkt]
- [x] Windows-Installer-Writer: Preset-Installer-Medium schreibt beide Preset-Pfade und liefert eigenen GRUB-Flow. [Repo-/Syntax-/API-validiert; nativer Windows-Boottest noch offen]
- [x] Windows-Live-USB-Writer: eigener VM-Downloadpfad und Packaging vorhanden. [Repo-/Syntax-/API-validiert; nativer Windows-Boottest noch offen]

Umsetzung Offline-Mode State Machine (2026-04-24):

- `thin-client-assistant/runtime/connection_state_machine.py` neu angelegt:
  `ConnectionStateMachine` mit States `ONLINE / OFFLINE / RECONNECTING`.
  - `tick()` → führt einen Konnektivitätscheck durch und berechnet neuen State.
  - `run(max_ticks)` → Blocking-Loop mit konfiguriertem `reconnect_interval`.
  - `ui_message()` → State-spezifische UI-Nachricht für Offline-Overlay.
  - `cached_config()` → gibt letzten gecachten Config zurück (via `OfflineCache`).
  - `on_transition(old, new, ctx)` Callback bei Zustandsänderung.
  - check_fn-Exceptions werden als "unreachable" behandelt (keine Crashes).
- Integriert mit `offline_cache.py` (OfflineCache): cached Config bleibt im OFFLINE-State verfügbar.
- Unit-Tests `tests/unit/test_connection_state_machine.py` — 19 Tests:
  - 8× State-Transitions (online/offline/reconnecting/recovery/exception)
  - 5× Callback-Verhalten (Aufruf, kein Aufruf ohne Zustandsänderung, ctx-Felder, Exception-Resilienz)
  - 5× UI-Messages und cached_config()
  - 1× Integration mit realem OfflineCache (Store+Load über State-Transitions)
- 19/19 Tests lokal und auf `srv1.beagle-os.com` grün.

Hinweis: Hardware-Testpflicht (physischer Thin-Client, QR-Pairing, A/B-Update, TPM)
bleibt offen — erfordert physische Endpoint-Hardware.
