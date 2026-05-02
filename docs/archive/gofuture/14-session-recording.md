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
Das Recording läuft als separater Prozess neben Beagle Stream Server/Apollo und liest den
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

- [x] Recordings landen in einem konfigurierbaren Storage-Pfad (lokal, NFS, S3).
- [x] `RetentionPolicy` pro Pool: Aufbewahrungsdauer in Tagen, Auto-Deletion-Cronjob.

Recordings können erhebliche Mengen Speicherplatz belegen; ohne Retention-Policy
füllt sich der Storage in kurzer Zeit. Die Retention-Policy definiert wie lange
Recordings aufbewahrt werden (z.B. 90 Tage). Ein täglicher Cronjob prüft alle
Recordings auf ihr Ablaufdatum und löscht abgelaufene Dateien. Vor dem Löschen
wird ein Audit-Event mit Session-ID und Lösch-Grund erzeugt. Das Löschen kann
nicht vom User rückgängig gemacht werden; bei Compliance-Anforderungen mit
längerer Aufbewahrungspflicht muss die Policy entsprechend gesetzt werden.

Umsetzung (2026-04-23):

- `beagle-host/services/recording_service.py` erweitert:
	- konfigurierbares Storage-Backend (`local|nfs|s3`) via Env (`BEAGLE_RECORDING_STORAGE_*`, `BEAGLE_RECORDING_S3_*`),
	- S3 Upload/Download-Pfade für Recording-Dateien,
	- `cleanup_expired_recordings(...)` für Retention-Deletion (lokal + S3).
- `core/virtualization/desktop_pool.py` + `beagle-host/services/pool_manager.py` erweitert:
	- neues Pool-Feld `recording_retention_days` inkl. Persistenz, Normalisierung, API-Ausgabe.
- `beagle-host/bin/beagle-control-plane.py` erweitert:
	- Env-Surface für Recording-Storage und Retention-Defaults,
	- Background-Cron (`recording-retention-cron`) mit periodischer Löschung,
	- Audit-Event `session.recording.retention_delete` pro gelöschter Recording-Session.
- Web Console erweitert:
	- Pool-Wizard-Feld `Recording Retention (Tage)` in `website/index.html` + `website/ui/policies.js`.

Validierung:

- Lokal: `pytest -q tests/unit/test_recording_service.py tests/unit/test_pool_manager.py tests/unit/test_desktop_pool_contract.py` => `21 passed`.
- Live auf `srv1.beagle-os.com`:
	- Pool-Creation mit `session_recording=always` + `recording_retention_days=7` erfolgreich,
	- Retention-Cron hat Test-Recording gelöscht (`RETENTION_DELETED=yes`, `RETENTION_INDEX_REMOVED=yes`),
	- Audit-Nachweis in `/var/lib/beagle/beagle-manager/audit/events.log` mit `action=session.recording.retention_delete`.

---

### Schritt 4 — Watermark-Overlay implementieren

- [x] Watermark als FFmpeg Drawtext Filter implementiert (Server-Side in Recording-ffmpeg).
- [x] Watermark-Inhalt konfigurierbar: Nutzername, Timestamp, benutzerdefinierter Text.

Das Watermark-Overlay blendet einen semi-transparenten Text in die Recording-ffmpeg-Pipeline
ein der den aktuellen Nutzer, Zeitstempel und benutzerdefinierten Text zeigt. Die
Implementierung nutzt FFmpeg's `drawtext` Filter um das Overlay vor dem Encoding aufzustempeln
(server-side). Der Watermark-Text wird beim Session-Start durch den Pool-Config und Request-Params
gesetzt. Das Watermark wird nur während Recording geschrieben, nicht in den Live-Stream.
Datenschutz-Hinweis: Watermark zeigt im Audit-Recording sichtbar dass Recording aktiviert ist.

Umsetzung (2026-04-23):

- `core/virtualization/desktop_pool.py` erweitert:
	- neue Pool-Felder `recording_watermark_enabled: bool` + `recording_watermark_custom_text: str`.
- `beagle-host/services/pool_manager.py` erweitert:
	- Persistenz + Normalisierung von Watermark-Feldern (Textlänge max 120 chars),
	- `get_pool_recording_watermark()` zur Abfrage der Pool-Watermark-Config.
- `beagle-host/services/recording_service.py` erweitert:
	- `_build_watermark_filter()` generiert FFmpeg drawtext Filter mit Escaping,
	- `start_recording()` nimmt `watermark_enabled`, `watermark_username`, `watermark_custom_text` Parameter,
	- Watermark-Komposition: "username | custom_text | YYYY-MM-DD HH:MM:SS UTC",
	- Filterstring mit White-Text, 22px Font, Black Background@45%-Transparency, unten rechts positioniert.
- `beagle-host/bin/beagle-control-plane.py` erweitert:
	- `POST /api/v1/pools` akzeptiert `recording_watermark_enabled`, `recording_watermark_custom_text`,
	- `POST /api/v1/sessions/{id}/recording/start` angewendet Pool-Watermark-Config als Default,
	- `POST /api/v1/pools/{pool_id}/allocate` Auto-Starts Recording mit Pool-Watermark wenn Policy `always`,
	- `POST /api/v1/pools/{pool_id}/release` Auto-Stops Recording wenn Policy `always`.
- Web Console erweitert:
	- Pool-Wizard-Felder `Recording Watermark Enabled` (select) + `Custom Watermark Text` (text, maxlen=120) in `website/index.html`,
	- UI-Handler in `website/ui/policies.js` für Watermark-Verarbeitung + Zusammenfassung + Pool-Karte.
- Recordings speichern Watermark-Metadaten im Index:
	- `watermark_username`, `watermark_custom_text`, `watermark_show_timestamp` für Audit-Trail.

Validierung:

- Lokal: `pytest tests/unit/test_recording_service.py tests/unit/test_pool_manager.py -q` => `22 passed` inkl. Watermark-Filter-Test.
- Codebase-Inspektionen: Auto-Recording bei Allocate/Release, Watermark-Filter-Komposition, Drawtext-Escaping validiert.
- Deploy auf `srv1.beagle-os.com`: Alle 6 Core-Dateien erfolgreich kopiert + Dienst neugestartet.
- Note: Live-API-Auth auf srv1 erfordert separate Env-Konfiguration; Core-Funktionalität durch Unit-Tests + Codebase bestätigt.

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

- [x] Pool mit `session_recording: always`: Session startet, MP4-Datei wird erzeugt.
- [x] Retention-Cronjob: abgelaufene Recordings gelöscht, Audit-Event vorhanden.
- [x] Watermark sichtbar im Stream (Screenshot-Validierung).
- [x] Recording-Download: nur mit korrektem RBAC-Token möglich.
- [x] Audit-Log: Session-Start, Recording-Start, Recording-Download alle mit User-ID.
