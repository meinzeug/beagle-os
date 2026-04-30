# Endpoint Update Architecture

## Ausgangslage

Stand vom 30.03.2026:

- lokale Festplatten-Installationen booten nicht als klassisches Debian-System, sondern als Live-Layout von der Zielplatte
- geschrieben werden aktuell `vmlinuz`, `initrd.img` und `filesystem.squashfs` nach `/live`
- persistente Client-Daten liegen separat unter `/pve-thin-client/state`
- die Beagle Control Plane auf dem Beagle-Host existiert bereits und kann Endpoints periodisch sehen
- Endpoints melden sich bereits per `beagle-endpoint-report` bei der Control Plane
- Endpoints ziehen bereits Aktionen per `beagle-endpoint-dispatch` von der Control Plane

Auf dem dedizierten Control-Plane-Host werden die Release-Artefakte bereits veröffentlicht.
Zum Zeitpunkt der Analyse liefert `beagle-downloads-status.json` Version `5.0.10` mit einem Payload von `1228401208` Bytes.

## Ziel

Installierte Thinclients sollen:

- erkennen, dass eine neue Beagle-OS-Version verfügbar ist
- Updates zuverlässig herunterladen und verifizieren
- entweder automatisch oder nach Benutzerbestätigung umschalten
- ihren Update-Status im Beagle host-Manager melden
- bei Problemen auf den vorherigen Stand zurückfallen können

## Vorschlag

### 1. Artefakt-Hosting trennen

- `beagle-os.com` hostet die oeffentlichen Update-Payloads
- der Beagle host-Host bleibt die autoritative Management- und Freigabeinstanz

Implementiertes Modell:

- oeffentliche Payloads und Checksummen unter `https://beagle-os.com/beagle-updates/`
- versionierte Payload-Datei `pve-thin-client-usb-payload-v<version>.tar.gz`
- `SHA256SUMS` fuer die oeffentlichen Artefakte
- optional ein schlankes oeffentliches `beagle-downloads-status.json`

Der Endpoint zieht die Freigabe nicht direkt aus einer oeffentlichen JSON-Datei, sondern ueber die Beagle Control Plane:

- `GET /api/v1/endpoints/update-feed`

Dieses Feed-Endpoint ist authentifiziert und liefert:

- `latest_version`
- `available`
- `payload_url`
- `payload_sha256`
- `sha256sums_url`
- Policy-Informationen wie `behavior`, `channel`, `version_pin`

Der Beagle host-Host kann dieselben Dateien weiterhin zusaetzlich unter `/beagle-downloads` anbieten.
Damit bleibt der Rollout auch ohne `beagle-os.com` funktionsfaehig.

### 2. Update-Kanal ueber die bestehende Control Plane steuern

Keine zweite Management-Strecke bauen.
Die vorhandene Beagle Control Plane ist bereits die richtige Stelle fuer:

- Update-Policy pro VM oder Client
- Freigabe von `stable`, `pilot`, `pinned`
- Anzeige `Update verfuegbar`, `wird geladen`, `wartet auf Neustart`, `fehlgeschlagen`
- Trigger fuer `download`, `apply`, `rollback`

Neue Actions im vorhandenen Action-Queue-Modell:

- `os-update-scan`
- `os-update-download`
- `os-update-apply`
- `os-update-rollback`

### 3. Update-Format auf Basis des bestehenden Live-Layouts

Fuer bestehende Installationen ist kein Repartitionieren noetig.
Die pragmatische Variante ist ein Zwei-Slot-Modell auf derselben ext4-Partition:

- `/live/a/...`
- `/live/b/...`
- GRUB bootet immer den aktiven Slot
- Update wird komplett in den inaktiven Slot geladen
- nach erfolgreicher Pruefung wird nur der aktive Slot umgeschaltet
- der vorherige Slot bleibt als Rollback erhalten

Warum das besser ist als direkt `/live` zu ueberschreiben:

- kein halb aktualisierter Kernel/Initrd/SquashFS-Mix
- Slot-Wechsel ist klein und atomar
- Rollback ist ohne Neuinstallation moeglich

### 4. Update-Metadaten

Es gibt zwei Ebenen von Metadaten:

- oeffentliche Artefakt-Metadaten auf Basis von `SHA256SUMS`
- ein vom Manager erzeugtes Update-Feed pro Endpoint

Der Endpoint speichert lokal:

- `install-manifest.json`
- `install-manifest.pending.json`
- `status.json`
- `staged-manifest.json`

Damit werden aktuelle Version, aktiver Slot, gestagte Version und Rollback-Stand nachgehalten.

### 5. Client-Verhalten

Empfohlenes Verhalten auf dem Endpoint:

1. `beagle-update-scan.timer` prueft alle 6 Stunden auf Update-Metadaten.
2. Ist eine neue Version freigegeben, wird die Payload verifiziert und in den inaktiven Slot geladen.
3. Der Client meldet den Status ueber `beagle-endpoint-report` an den Manager.
4. Je nach Policy wird entweder sofort umgeschaltet und rebootet oder beim Session-Start ein `zenity`-Dialog angezeigt.
5. Nach erfolgreichem Boot bestaetigt `beagle-update-confirm.service` den aktiven Slot und uebernimmt das Pending-Manifest.

### 6. UI-Dialog

Fuer die erste Ausbaustufe reicht ein sehr einfacher lokaler Dialog:

- X11/Chromium-Overlay oder `zenity`
- nur anzeigen, wenn gerade keine aktive Stream-Session laeuft
- alternativ bei Session-Ende oder im Idle-Fenster

Policy-Beispiele:

- Kiosk-Standort: vollautomatisch nachts zwischen `02:00` und `04:00`
- Einzelplatz: Hinweisdialog mit `Spaeter`
- Pilotgruppe: sofort nach Download

## Empfohlene Reihenfolge

### Umgesetzter Stand

- Versions- und Install-Metadaten haengen am Endpoint-Report
- Slot-Layout `a/b` und GRUB-Umschaltung sind in der lokalen Installation umgesetzt
- Endpoint-Service fuer `scan`, `apply`, `rollback`, `confirm-boot` ist vorhanden
- Manager-API fuer Update-Feed und Update-Aktionen ist vorhanden
- Dialog im laufenden Client ist als `zenity`-Prompt umgesetzt

Noch offen fuer eine spaetere Ausbaustufe:

- echtes zeitgesteuertes Wartungsfenster statt `auto` oder `prompt`
- Rollout-Prozentsaetze oder Pilotgruppen auf Server-Seite
- automatischer Rollback anhand eines Health-Timeouts statt rein manuell

## Bewertung

Ja, das ist technisch gut machbar.

Die bestehende Architektur hilft bereits:

- Releases werden schon versioniert gebaut
- Checksummen existieren schon
- der Manager sieht Endpoints schon
- die Action-Queue existiert schon

Der fehlende Teil ist nicht die Infrastruktur, sondern die Update-Orchestrierung.
Genau dafuer sollte Beagle nicht einen Fremd-Updater anbauen, sondern den vorhandenen Manager und das bestehende Live-Layout erweitern.
