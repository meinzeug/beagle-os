# 11 — 7.1.1 Streaming v2: Apollo + Virtual Display

Stand: 2026-04-22  
Priorität: 7.1 (Q1–Q2 2027)  
Referenz: `docs/refactorv2/05-streaming-protocol-strategy.md`, Entscheidung `docs/refactor/07-decisions.md#D-031`

---

## Ziel

**Linux-Desktops**: Sunshine + Virtual Display (vkms) ohne physischen Monitor.  
**Windows-Desktops**: Apollo + SudoVDA Virtual Display für HDR, Multi-Monitor (2–4), 4:4:4.  
Auto-Pairing per signiertem Token aus Web Console (beide Plattformen).  
Akzeptanz: Linux-VM streamt 3840×2160@60 (Sunshine+vkms), Windows-VM streamt 3840×2160@60 HDR (Apollo) auf Beagle Endpoint OS ohne Artefakte.

---

## Streaming-Backend-Strategie

**Apollo ist Windows-only für Virtual Display** – der SudoVDA-Treiber ist nicht für Linux verfügbar.
Für Beagle OS gilt daher:

| Szenario | Backend | Virtual Display | Priorität |
|----------|---------|-----------------|-----------|
| Linux Desktop (default) | Sunshine | `vkms` (DRM kernel module) | 2026-Q1 |
| Windows Desktop (optional) | Apollo | SudoVDA (Windows driver) | 2026-Q1 |
| Linux Server streaming | Sunshine | kernel `vkms` oder software-fallback | 2026-Q1 |
| Apollo auf Linux (eval only) | Apollo from Source | ❌ nicht vorhanden | 2026-Q2 |

---

## Schritte

### Schritt 1 — Virtual Display auf Linux mit vkms implementieren (Priorität 1)

- [x] PoC: `vkms` (Virtual Kernel Mode Setting) als Virtual-Display-Treiber auf Ubuntu 24.04 XFCE in beagle-100.
- [x] Firstboot-Skript `virtual-display-setup.sh.tpl`: vkms Modul laden, virtual outputs konfigurieren, X11/XFCE an vkms binden.
- [x] Moonlight Client auf Endpoint: Auflösung vom Client einlesen (z. B. 3840×2160), vkms via `xrandr` anpassen, Stream starten.

Umsetzung: Endpoint ruft vor Streamstart den Manager-Hook
`/api/v1/endpoints/moonlight/prepare-stream` auf und uebergibt die lokal erkannte
`WIDTHxHEIGHT`-Aufloesung. Der Host setzt die Guest-Aufloesung per `xrandr` via
Guest-Exec (`DISPLAY=:0`, `XAUTHORITY=/home/<guest>/.Xauthority`) und startet danach
den normalen Moonlight-Stream.

Reproduzierbarer Baseline-Smoke ist jetzt verfuegbar: `scripts/test-streaming-quality-smoke.py`.
Aktueller Lauf gegen `srv1.beagle-os.com`/`beagle-100` ergab `pass_with_4k_limit`:
`vkms` geladen, `DISPLAY=:0` + `xrandr` ok, Sunshine API (`/api/apps`) erreichbar,
4K-Mode vorhanden aber in der aktuellen VM-Grafikpipeline noch `xrandr: Configure crtc 0 failed`.

Ein virtuelles Display ist notwendig damit Sunshine eine Auflösung rendern kann ohne physischen Monitor am Host angeschlossen. `vkms` ist im Mainline-Kernel enthalten und erzeugt einen virtuellen DRM-Framebuffer. Der PoC auf `beagle-100` hat `vkms`-Load, X11-Session-Access (`DISPLAY=:0`) und Sunshine-Laufzeit erfolgreich verifiziert. Der 4K-Mode ist zwar im `xrandr` sichtbar, laeuft in der aktuellen VM-Grafikkonfiguration aber in `xrandr: Configure crtc 0 failed`; daher ist im Setup ein reproduzierbarer Fallback auf 1920x1080 hinterlegt. Falls `vkms` Probleme zeigt wird `xvfb` als Fallback verwendet (software-rendered, kein Hardware-Encode).

---

### Schritt 2 — Auto-Pairing per signiertem Token implementieren

- [x] `beagle-host/services/pairing_service.py` anlegen: Pairing-Token erzeugen, signieren, validieren.
- [x] Sunshine/Apollo-Pairing-PIN durch Token-Exchange ersetzen.

Umsetzung (2026-04-22):
- Neues Service-Modul `beagle-host/services/pairing_service.py` mit HMAC-SHA256 signierten, kurzlebigen Pairing-Tokens (`issued_at`, `expires_at`, Scope/VM/Endpoint-Bindung).
- Neue Endpoint-API-Routen:
	- `POST /api/v1/endpoints/moonlight/pair-token`
	- `POST /api/v1/endpoints/moonlight/pair-exchange`
- Control-Plane-Wiring in `beagle-host/bin/beagle-control-plane.py` + Endpoint-Surface in `beagle-host/services/endpoint_http_surface.py` umgesetzt.
- Endpoint-Runtime umgestellt:
	- `thin-client-assistant/runtime/moonlight_manager_registration.sh` nutzt Token-Ausgabe + Exchange-Call,
	- `thin-client-assistant/runtime/moonlight_pairing.sh` versucht zuerst Token-Exchange und faellt bei Bedarf auf Legacy-PIN-Submit zurueck.
- Stabilitaetsfix fuer Endpoint-Auth-Token-Lookup auf non-root Runtime:
	- `beagle-host/services/endpoint_token_store.py` ignoriert `chmod`-Fehler robust statt `500`.

Validierung:
- Unit-Tests: `python3 -m pytest tests/unit/test_endpoint_token_store.py tests/unit/test_endpoint_http_surface.py tests/unit/test_pairing_service.py -q` => `11 passed`.
- Live auf `srv1.beagle-os.com`:
	- `POST /api/v1/endpoints/moonlight/pair-token` => `201` mit signiertem Token + PIN,
	- keine `request.unhandled_exception`-Events mehr fuer den vorherigen `PermissionError` im Endpoint-Token-Pfad.

Der manuelle PIN-Pairing-Prozess von Sunshine ist für Enterprise-VDI-Deployments nicht skalierbar. Ein signierter Token aus der Web Console ersetzt den PIN: Der Admin generiert einen Pairing-Token für eine VM (oder Pool) in der Web Console; der Token enthält verschlüsselt: VM-ID, Tenant-ID, Ablaufzeit, Berechtigungsscope. Das Endpoint-OS oder der Browser übergibt diesen Token beim ersten Verbindungsaufbau. Sunshine/Apollo bekommt einen HTTP-Hook den Beagle aufrufen kann um das Pairing automatisch zu bestätigen. Das verhindert dass Endnutzer einen manuellen PIN-Dialog auf der VM sehen müssen.

---

### Schritt 3 — Encoder-Auswahl pro Pool/VM/Profil implementieren

- [x] `StreamingProfile`-Objekt in `core/` definieren: encoder (nvenc/vaapi/quicksync/software), bitrate, resolution, fps, color (H264/H265/AV1), hdr.
- [x] Web Console: Streaming-Profil-Editor im Pool-Wizard.

Umsetzung (2026-04-22):
- Neues Core-Modul `core/virtualization/streaming_profile.py` eingefuehrt.
- Typisierte Basisschicht vorhanden fuer:
	- `encoder`: `auto|nvenc|vaapi|quicksync|software`
	- `color`: `h264|h265|av1`
	- `bitrate_kbps`, `resolution`, `fps`, `hdr`
- Pool-Contract erweitert:
	- `core/virtualization/desktop_pool.py` traegt `streaming_profile` jetzt in `DesktopPoolSpec` und `DesktopPoolInfo`.
- Control-Plane + Pool-Manager verdrahtet:
	- `POST /api/v1/pools` akzeptiert `streaming_profile`,
	- `PUT /api/v1/pools/{pool}` aktualisiert `streaming_profile`,
	- `GET /api/v1/pools` und `GET /api/v1/pools/{pool}` liefern das Profil zurueck.
- Web Console erweitert:
	- `website/index.html` enthaelt jetzt Wizard-Felder fuer `encoder`, `codec`, `bitrate_kbps`, `fps`, `resolution`, `hdr`,
	- `website/ui/policies.js` mappt diese Felder auf `payload.streaming_profile`, validiert Basiswerte und zeigt das Profil in Wizard-Summary + Pool-Karten,
	- `website/styles/panels/_policies.css` styled den neuen Streaming-Profil-Block im Pool-Wizard.

Validierung:
- Lokal:
	- `python3 -m pytest tests/unit/test_streaming_profile_contract.py tests/unit/test_desktop_pool_contract.py tests/unit/test_pool_manager.py -q` => `12 passed`
	- `python3 -m py_compile beagle-host/bin/beagle-control-plane.py` => OK
	- `node --check website/ui/policies.js website/ui/events.js` => OK
- Live auf `srv1.beagle-os.com`:
	- temp Pool mit `streaming_profile` erfolgreich erstellt (`201`), per `GET` verifiziert, per `PUT` von `vaapi/h264/1920x1080/60` auf `software/av1/2560x1440/75` geaendert und geloescht (`200`),
	- neue Wizard-Felder werden in der ausgelieferten WebUI sichtbar ausgeliefert (`pool-stream-encoder`, `pool-stream-color`, `pool-stream-bitrate`, `pool-stream-fps`, `pool-stream-resolution`, `pool-stream-hdr`),
	- UI-Smoke mit temporaer geseedetem Template und Pool-Wizard/Create-Cleanup gegen `srv1` durchgefuehrt.
Eine feste Encoder-Konfiguration für alle VMs ist nicht optimal da verschiedene Workloads und Hardware unterschiedliche Encoder bevorzugen. NVENC ist ideal für NVIDIA-GPU-passthrough-VMs. VA-API ist für Intel-iGPU-basierte VMs geeignet. QuickSync bietet hohe Qualität bei moderatem CPU-Overhead auf Intel-Systemen. Software-Encoding (x264/x265) ist immer verfügbar aber CPU-intensiv. Das `StreamingProfile`-Objekt wird pro Pool gesetzt und kann für einzelne VMs überschrieben werden. Ungültige Encoder-Konfigurationen (NVENC ohne GPU) werden bei Pool-Erstellung mit einer Warnung markiert.

---

### Schritt 4 — HDR, Multi-Monitor, Audio-In, Gamepad-Redirect konfigurierbar machen

- [ ] Alle relevanten Moonlight/Sunshine-Konfigurationsparameter in `StreamingProfile` abbilden.
- [ ] Test-Matrix: Audio-Hin und Zurück, Gamepad, Wacom-Tablet, USB-Redirect dokumentieren und testen.

HDR erfordert HDR-fähige Encoder-Konfiguration (HEVC Main 10 oder AV1) und HDR-Metadaten-Passing durch den Encoder. Multi-Monitor (2–4) erfordert entsprechende Virtual-Display-Konfiguration auf dem Guest und Multi-Display-Unterstützung in Apollo (Windows) oder xrandr-Multi-Output (Linux). Audio-Input (Mikrofon) ist seit Moonlight-Protokoll-Version 5 unterstützt und erfordert explizite Konfiguration in Sunshine/Apollo. Gamepad-Redirect funktioniert via Moonlight-Input-Protokoll und erfordert `uinput`-Berechtigung im Guest. Wacom-Tablet-Redirect ist über Moonlight-Pen-Input implementiert. Jede dieser Funktionen wird in einer Test-Matrix dokumentiert mit Status: ✓ / ⚠ / ✗ und Hinweis auf erforderliche Konfiguration.

---

### Schritt 5 — Stream-Health-Telemetrie im Session-Objekt speichern

- [ ] Sunshine/Apollo-Metriken (RTT, FPS, Dropped-Frames, Encoder-Load) per API in `session.stream_health` speichern.
- [ ] Web Console: Stream-Health-Anzeige in der Session-Detailansicht.

Stream-Health-Telemetrie ermöglicht proaktives Support-Management: Wenn ein Nutzer hohe Latenz oder Dropped Frames meldet kann der Admin die Session-Metriken einsehen. Sunshine/Apollo bietet eine lokale Stats-API (`/api/v1/stats` oder metrics endpoint). `session_service.py` pollt diese API periodisch und speichert die letzten X Messpunkte im Session-Objekt. Die Web Console zeigt in der Session-Detailansicht ein Live-Graph für Latenz und FPS des aktiven Streams. Session-Health-Daten fließen ebenfalls in den Fleet-Health-Alert-Mechanismus der Web Console ein.

---

### Schritt 6 — Apollo auf Windows Desktop-VM evaluieren und vergleichen

- [ ] Separat: Windows Guest-Desktop mit Apollo + SudoVDA evaluieren (optional, 2026-Q2).
- [ ] Benchmarking: Vergleich Sunshine (Linux) vs Apollo (Windows) für gleiche Workload/Resolution.
- [ ] Dokumentation: Performance-Baseline und Backend-Auswahl-Kriterien in `docs/refactor/07-decisions.md#D-031`.

Apollo nutzt SudoVDA als Virtual Display-Treiber (Windows-spezifisch). Der Evaluationsschritt prüft ob Apollo in Windows-Gast-VMs Superior-Features (HDR, Auto-Resolution, Per-Client-Permissions) zu messbarem Performance-Vorteil nutzt. Falls ja wird Apollo optional für Windows-Desktop-Pools empfohlen. Falls nein bleibt Sunshine Default für alle Plattformen.

---

## Testpflicht nach Abschluss

- [ ] Linux Desktop (beagle-100): vkms Virtual Display funktioniert, Moonlight zeigt Auflösung angepasst auf 3840×2160@60 ohne Artefakte.
- [ ] Linux Desktop (beagle-100): vkms Virtual Display funktioniert, Moonlight zeigt Auflösung angepasst auf 3840×2160@60 ohne Artefakte. (Baseline bereits vorhanden: `scripts/test-streaming-quality-smoke.py` => `pass_with_4k_limit`)
- [ ] Windows Desktop (optional): Apollo-VM streamt 3840×2160@60 HDR auf Moonlight ohne Artefakte.
- [ ] Auto-Pairing ohne manuellen PIN: Token generieren → Client verbindet automatisch.
- [ ] Multi-Monitor (Linux): zwei xrandr-Outputs konfiguriert, Moonlight zeigt beide (wenn supported).
- [ ] Stream-Health-Metriken in Web Console sichtbar während Session läuft.

