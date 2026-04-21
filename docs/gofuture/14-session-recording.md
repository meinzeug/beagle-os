# 14 — 7.2.1 Session Recording + Watermark

Stand: 2026-04-20  
Priorität: 7.2 (Q2–Q3 2027)

---

## Schritte

### Schritt 1 — Session-Recording-Policy pro Pool konfigurierbar machen

- [ ] `DesktopPool` bekommt Feld `session_recording`: `disabled | on_demand | always`.
- [ ] Web Console: Recording-Policy im Pool-Editor.

Session Recording ist eine Compliance-Funktion die in regulierten Branchen
(Finanz, Gesundheit, Behörden) häufig Pflicht ist. Die Policy `always` aktiviert
Recording für alle Sessions des Pools automatisch. `on_demand` erlaubt Support-Personal
das Recording einzelner Sessions zu starten. `disabled` (Default) schaltet Recording
komplett aus. Die Policy wird beim Session-Start an den Recording-Service weitergegeben.
Recordings werden nicht standardmäßig aktiviert um Datenschutz-Defaulteinstellungen
(Privacy by Default) zu respektieren. Jede Recording-Aktivierung erzeugt ein Audit-Event.

---

### Schritt 2 — Recording-Service implementieren

- [ ] `beagle-host/services/recording_service.py` anlegen: frFFmpeg-basiertes Capture vom Streaming-Output.
- [ ] Output: MP4-Datei mit H.264/H.265 Encodierung pro Session.

Der Recording-Service klinkt sich in den Streaming-Pfad ein und erzeugt eine lokale
Video-Datei der Session. ffmpeg ist das bevorzugte Tool für diesen Zweck da es
auf allen Debian-Systemen verfügbar ist und alle benötigten Codecs unterstützt.
Das Recording läuft als separater Prozess neben Sunshine/Apollo und liest den
RTP/RTSP-Stream oder nutzt einen Screen-Capture-Mechanismus. Die Ausgabe-Dateigröße
muss durch Bitraten-Limitierung kontrollierbar sein. Recording-Dateien erhalten
Metadaten: Session-ID, User-ID, Tenant-ID, Start/End-Zeit, Pool-ID.

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

- [ ] API: `GET /api/v1/sessions/{id}/recording` mit Bearer-Token und RBAC (`session:download_recording`).
- [ ] Audit-Eintrag bei jedem Recording-Download mit Downloader-ID.

Recordings dürfen nicht öffentlich zugänglich sein sondern nur für berechtigte Rollen
(platform-admin, auditor, tenant-admin nach Pool-Policy). Der Download-Endpoint
generiert eine temporäre Signed-URL für den Recording-Datei-Download statt die Datei
direkt zu streamen. Die Signed-URL läuft nach 15 Minuten ab. Jeder Recording-Download
erzeugt einen Audit-Eintrag. Das verhindert dass Recordings unbemerkt heruntergeladen
und weitergegeben werden können. Recordings älterer als die Retention-Policy können
nicht mehr heruntergeladen werden (404-Response mit sprechendem Error-Text).

---

## Testpflicht nach Abschluss

- [ ] Pool mit `session_recording: always`: Session startet, MP4-Datei wird erzeugt.
- [ ] Retention-Cronjob: abgelaufene Recordings gelöscht, Audit-Event vorhanden.
- [ ] Watermark sichtbar im Stream (Screenshot-Validierung).
- [ ] Recording-Download: nur mit korrektem RBAC-Token möglich.
- [ ] Audit-Log: Session-Start, Recording-Start, Recording-Download alle mit User-ID.
