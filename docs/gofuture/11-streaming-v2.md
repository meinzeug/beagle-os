# 11 — 7.1.1 Streaming v2: Apollo + Virtual Display

Stand: 2026-04-20  
Priorität: 7.1 (Q1–Q2 2027)  
Referenz: `docs/refactorv2/05-streaming-protocol-strategy.md`

---

## Ziel

Apollo (oder Apollo-Patches über Sunshine-Mainline) als bevorzugtes Streaming-Backend.
Virtual Display auf Linux ohne physischen Monitor. Auto-Pairing per signiertem Token
aus der Web Console. HDR, Multi-Monitor (2–4), 4:4:4.
Akzeptanz: Apollo-VM streamt 3840×2160@60 HDR mit zwei Monitoren auf Beagle Endpoint OS.

---

## Schritte

### Schritt 1 — Apollo als Streaming-Backend evaluieren und integrieren

- [ ] Apollo-Fork von Sunshine auf Stabilität und Upstream-Divergenz prüfen.
- [ ] Apollo in einem Test-Desktop-VM installieren und Streaming-Qualität messen.

Apollo ist ein Fork von Sunshine mit Fokus auf virtualisierte Umgebungen, insbesondere
Virtual-Display-Support und verbesserte Encoder-Kompatibilität in VMs ohne physische GPU.
Der Evaluationsschritt prüft ob Apollo produktionsreif ist oder ob Apollo-Patches
direkt in Sunshine-Mainline besser funktionieren. Mess-Kriterien: Latenz (E2E), FPS-
Stabilität, Encoder-Auslastung, HDR-Support, Multi-Monitor-Konfiguration. Die Entscheidung
wird in `docs/refactor/07-decisions.md` festgehalten. Falls Apollo stagniert wird
ein Fallback auf Sunshine-Mainline mit eigenen Patches geplant. Der apolllo-Build-Prozess
wird in `docs/gofuture/11-streaming-v2.md` dokumentiert.

---

### Schritt 2 — Virtual Display auf Linux implementieren

- [ ] PoC: `vkms` (Virtual Kernel Mode Setting) als Virtual-Display-Treiber auf Ubuntu 24.04 XFCE.
- [ ] Alternativ: DRM-Virtual-Display über `drm_vkms` oder `xrandr --addmode`.

Ein virtuelles Display ist notwendig damit Sunshine/Apollo eine Auflösung rendern kann
ohne physischen Monitor angeschlossen. Auf Windows erledigt das SudoVDA (Virtual Display
Adapter); auf Linux gibt es mehrere Optionen. `vkms` ist im Mainline-Kernel enthalten
und erzeugt einen virtuellen DRM-Framebuffer. Der PoC startet eine VM ohne physische
GPU, lädt `vkms`, konfiguriert eine 4K-Auflösung, startet den Display-Compositor und
validiert dass Sunshine/Apollo den virtuellen Display sieht und streamt. Bei Problemen
mit `vkms` ist `xvfb` als Fallback verfügbar (software-rendered, kein Hardware-Encode).

---

### Schritt 3 — Auto-Pairing per signiertem Token implementieren

- [ ] `beagle-host/services/pairing_service.py` anlegen: Pairing-Token erzeugen, signieren, validieren.
- [ ] Sunshine/Apollo-Pairing-PIN durch Token-Exchange ersetzen.

Der manuelle PIN-Pairing-Prozess von Sunshine ist für Enterprise-VDI-Deployments
nicht skalierbar. Ein signierter Token aus der Web Console ersetzt den PIN: Der Admin
generiert einen Pairing-Token für eine VM (oder Pool) in der Web Console; der Token
enthält verschlüsselt: VM-ID, Tenant-ID, Ablaufzeit, Berechtigungsscope. Das Endpoint-
OS oder der Browser übergibt diesen Token beim ersten Verbindungsaufbau. Sunshine/Apollo
bekommt einen HTTP-Hook den Beagle aufrufen kann um das Pairing automatisch zu bestätigen.
Das verhindert dass Endnutzer einen manuellen PIN-Dialog auf der VM sehen müssen.

---

### Schritt 4 — Encoder-Auswahl pro Pool/VM/Profil implementieren

- [ ] `StreamingProfile`-Objekt in `core/` definieren: encoder (nvenc/vaapi/quicksync/software), bitrate, resolution, fps, color (H264/H265/AV1), hdr.
- [ ] Web Console: Streaming-Profil-Editor im Pool-Wizard.

Eine feste Encoder-Konfiguration für alle VMs ist nicht optimal da verschiedene
Workloads und Hardware unterschiedliche Encoder bevorzugen. NVENC ist ideal für
NVIDIA-GPU-passthrough-VMs. VA-API ist für Intel-iGPU-basierte VMs geeignet.
QuickSync bietet hohe Qualität bei moderatem CPU-Overhead auf Intel-Systemen.
Software-Encoding (x264/x265) ist immer verfügbar aber CPU-intensiv. Das `StreamingProfile`-
Objekt wird pro Pool gesetzt und kann für einzelne VMs überschrieben werden. Ungültige
Encoder-Konfigurationen (NVENC ohne GPU) werden bei Pool-Erstellung mit einer
Warnung markiert.

---

### Schritt 5 — HDR, Multi-Monitor, Audio-In, Gamepad-Redirect konfigurierbar machen

- [ ] Alle relevanten Moonlight/Sunshine-Konfigurationsparameter in `StreamingProfile` abbilden.
- [ ] Test-Matrix: Audio-Hin und Zurück, Gamepad, Wacom-Tablet, USB-Redirect dokumentieren und testen.

HDR erfordert HDR-fähige Encoder-Konfiguration (HEVC Main 10 oder AV1) und HDR-Metadaten-
Passing durch den Encoder. Multi-Monitor (2–4) erfordert entsprechende Virtual-Display-
Konfiguration auf dem Guest und Multi-Display-Unterstützung in Apollo. Audio-Input
(Mikrofon) ist seit Moonlight-Protokoll-Version 5 unterstützt und erfordert explizite
Konfiguration in Sunshine/Apollo. Gamepad-Redirect funktioniert via Moonlight-Input-
Protokoll und erfordert `uinput`-Berechtigung im Guest. Wacom-Tablet-Redirect ist über
Moonlight-Pen-Input implementiert. Jede dieser Funktionen wird in einer Test-Matrix
dokumentiert mit Status: ✓ / ⚠ / ✗ und Hinweis auf erforderliche Konfiguration.

---

### Schritt 6 — Stream-Health-Telemetrie im Session-Objekt speichern

- [ ] Sunshine/Apollo-Metriken (RTT, FPS, Dropped-Frames, Encoder-Load) per API in `session.stream_health` speichern.
- [ ] Web Console: Stream-Health-Anzeige in der Session-Detailansicht.

Stream-Health-Telemetrie ermöglicht proaktives Support-Management: Wenn ein Nutzer
hohe Latenz oder Dropped Frames meldet kann der Admin die Session-Metriken einsehen.
Sunshine/Apollo bietet eine lokale Stats-API (`/api/v1/stats` oder metrics endpoint).
`session_service.py` pollt diese API periodisch und speichert die letzten X Messpunkte
im Session-Objekt. Die Web Console zeigt in der Session-Detailansicht ein Live-Graph
für Latenz und FPS des aktiven Streams. Session-Health-Daten fließen ebenfalls in
den Fleet-Health-Alert-Mechanismus der Web Console ein.

---

## Testpflicht nach Abschluss

- [ ] Apollo/Sunshine-VM streamt 3840×2160@60 auf Beagle Endpoint OS ohne Artefakte.
- [ ] Virtual Display ohne physischen Monitor funktioniert.
- [ ] Auto-Pairing ohne manuellen PIN: Token generieren → Client verbindet automatisch.
- [ ] Multi-Monitor: zwei virtuelle Displays konfiguriert, Moonlight zeigt beide.
- [ ] Stream-Health-Metriken in Web Console sichtbar während Session läuft.
