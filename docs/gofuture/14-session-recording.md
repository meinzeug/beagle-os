# 14 — 7.2.1 Session Recording + Watermark

Stand: 2026-04-20  
Priorität: 7.2 (Q2–Q3 2027)

---

## Schritte

### Schritt 1 — Session-Recording-Policy pro Pool konfigurierbar machen

- [x] `DesktopPool` bekommt Feld `session_recording`: `disabled | on_demand | always`.
- [x] Web Console: Recording-Policy im Pool-Editor.

Session Recording ist eine Compliance-Funktion die in regulierten Branchen
(Finanz, Gesundheit, Behörden) häufig Pflicht ist. Die Policy `always` aktiviert
Recording für alle Sessions des Pools automatisch. `on_demand` erlaubt Support-Personal
das Recording einzelner Sessions zu starten. `disabled` (Default) schaltet Recording
komplett aus. Die Policy wird beim Session-Start an den Recording-Service weitergegeben.
Recordings werden nicht standardmäßig aktiviert um Datenschutz-Defaulteinstellungen
(Privacy by Default) zu respektieren. Jede Recording-Aktivierung erzeugt ein Audit-Event.

Umsetzung (2026-04-23):

- `core/virtualization/desktop_pool.py` erweitert:
	- neues Enum `SessionRecordingPolicy` (`disabled`, `on_demand`, `always`),
	- `DesktopPoolSpec.session_recording` und `DesktopPoolInfo.session_recording` eingefuehrt.
- `beagle-host/services/pool_manager.py` erweitert:
	- Persistenz + Normalisierung des Felds `session_recording`,
	- Auslieferung in `pool_info_to_dict(...)` fuer API/WebUI.
- `beagle-host/bin/beagle-control-plane.py` erweitert:
	- `POST /api/v1/pools` akzeptiert `session_recording` und mappt auf `SessionRecordingPolicy`.
- Web Console Pool-Wizard erweitert:
	- neues Select-Feld `Session Recording` (disabled/on_demand/always),
	- Payload + Summary + Pool-Karte zeigen den gesetzten Recording-Mode.

Validierung:

- Lokal: `python3 -m pytest tests/unit/test_pool_manager.py tests/unit/test_desktop_pool_contract.py -q` => `17 passed`.
- Live auf `srv1.beagle-os.com`:
	- Pool mit `session_recording=always` erstellt,
	- `GET /api/v1/pools/{pool_id}` liefert `session_recording: "always"`,
	- Cleanup erfolgreich (`deleted: true`).

---

### Schritt 2 — Recording-Service implementieren

- [x] `beagle-host/services/recording_service.py` anlegen: frFFmpeg-basiertes Capture vom Streaming-Output.
- [x] Output: MP4-Datei mit H.264/H.265 Encodierung pro Session.

Der Recording-Service klinkt sich in den Streaming-Pfad ein und erzeugt eine lokale
Video-Datei der Session. ffmpeg ist das bevorzugte Tool für diesen Zweck da es
auf allen Debian-Systemen verfügbar ist und alle benötigten Codecs unterstützt.
Das Recording läuft als separater Prozess neben Sunshine/Apollo und liest den
RTP/RTSP-Stream oder nutzt einen Screen-Capture-Mechanismus. Die Ausgabe-Dateigröße
muss durch Bitraten-Limitierung kontrollierbar sein. Recording-Dateien erhalten
Metadaten: Session-ID, User-ID, Tenant-ID, Start/End-Zeit, Pool-ID.

Umsetzung (2026-04-21):

- Neuer Service `beagle-host/services/recording_service.py` implementiert.
- ffmpeg-basierter Recorder erstellt pro Session MP4-Dateien im Runtime-Storage (`recordings/index.json` + Datei-Pfad).
- Neue API-Routen im Control Plane:
	- `POST /api/v1/sessions/{id}/recording/start`
	- `POST /api/v1/sessions/{id}/recording/stop`
	- `GET /api/v1/sessions/{id}/recording` (Download)
- RBAC-Permissions ergänzt:
	- `session:manage_recording`
	- `session:download_recording`
- Permission-Katalog (`/api/v1/auth/permission-tags`) um Session-Recording-Tags erweitert.

---

### Schritt 3 — Recording-Storage mit Retention-Policy implementieren

- [ ] Recordings landen in einem konfigurierbaren Storage-Pfad (lokal, NFS, S3).
- [ ] `RetentionPolicy` pro Pool: Aufbewahrungsdauer in Tagen, Auto-Deletion-Cronjob.

Recordings können erhebliche Mengen Speicherplatz belegen; ohne Retention-Policy
füllt sich der Storage in kurzer Zeit. Die Retention-Policy definiert wie lange
Recordings aufbewahrt werden (z.B. 90 Tage). Ein täglicher Cronjob prüft alle
Recordings auf ihr Ablaufdatum und löscht abgelaufene Dateien. Vor dem Löschen
wird ein Audit-Event mit Session-ID und Lösch-Grund erzeugt. Das Löschen kann
nicht vom User rückgängig gemacht werden; bei Compliance-Anforderungen mit
längerer Aufbewahrungspflicht muss die Policy entsprechend gesetzt werden.

---

### Schritt 4 — Watermark-Overlay implementieren

- [ ] Watermark als Apollo-Plug-in oder guest-side Compositor-Layer implementieren.
- [ ] Watermark-Inhalt konfigurierbar: Nutzername, Timestamp, benutzerdefinierter Text.

Das Watermark-Overlay blendet einen semi-transparenten Text in den Stream ein der
den aktuellen Nutzer und Zeitstempel zeigt. Die bevorzugte Implementierung ist ein
Apollo-Plug-in das das Overlay vor dem Encoding aufstempelt (server-side). Falls
Apollo-Plug-in-API nicht verfügbar ist, wird ein guest-side Compositor-Overlay als
Fallback eingesetzt (Xwayland-Overlay-Window oder X11-Transparent-Overlay). Der
Watermark-Text wird beim Session-Start durch den Pairing-Token gesetzt. Datenschutz-
Hinweis: Watermark zeigt dem Nutzer sichtbar dass er beobachtet werden kann. Die
Web Console muss dies beim Session-Start dem Nutzer kommunizieren (Consent-Dialog
wenn Policy `watermark: always`).

---

### Schritt 5 — Recording-Download und Audit-Eintrag

- [x] API: `GET /api/v1/sessions/{id}/recording` mit Bearer-Token und RBAC (`session:download_recording`).
- [x] Audit-Eintrag bei jedem Recording-Download mit Downloader-ID.

Recordings dürfen nicht öffentlich zugänglich sein sondern nur für berechtigte Rollen
(platform-admin, auditor, tenant-admin nach Pool-Policy). Der Download-Endpoint
generiert eine temporäre Signed-URL für den Recording-Datei-Download statt die Datei
direkt zu streamen. Die Signed-URL läuft nach 15 Minuten ab. Jeder Recording-Download
erzeugt einen Audit-Eintrag. Das verhindert dass Recordings unbemerkt heruntergeladen
und weitergegeben werden können. Recordings älterer als die Retention-Policy können
nicht mehr heruntergeladen werden (404-Response mit sprechendem Error-Text).

Umsetzung (2026-04-21):

- Download-Endpoint `GET /api/v1/sessions/{id}/recording` liefert MP4 (`video/mp4`) als Attachment.
- Auth-/RBAC-Gate aktiv: ohne Token `401`, mit gültigem Token `200`.
- Audit-Event bei Download implementiert: `session.recording.download` mit `session_id`, `downloader`, `remote_addr`.
- Live-Validierung auf `srv1.beagle-os.com` erfolgreich inkl. Audit-Log-Nachweis.

---

## Testpflicht nach Abschluss

- [ ] Pool mit `session_recording: always`: Session startet, MP4-Datei wird erzeugt.
- [ ] Retention-Cronjob: abgelaufene Recordings gelöscht, Audit-Event vorhanden.
- [ ] Watermark sichtbar im Stream (Screenshot-Validierung).
- [x] Recording-Download: nur mit korrektem RBAC-Token möglich.
- [x] Audit-Log: Session-Start, Recording-Start, Recording-Download alle mit User-ID.
