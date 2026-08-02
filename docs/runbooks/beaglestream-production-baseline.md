# BeagleStream Production Baseline

Stand: 2026-07-30

Dieser Runbook-Eintrag friert den auf VM100/srv1/lokalem Thinclient live validierten Zustand ein. Er ist der aktuelle produktionsnahe Standard fuer Kundenbetrieb, bis Hardware-Encoding und native Latenzmetriken nachgezogen sind.

## Baseline

- Transport: Broker/WireGuard, kein Public-BeagleStream-DNAT.
- Server-Ziel: interne VM-IP, z. B. `192.168.123.114:50000`.
- Qualitaet: `1920x1080`, `60 fps`, `32000 kbps`, H.264.
- Thinclient-Renderer: SDL/OpenGL, Vulkan deaktiviert.
- Thinclient-Decode: `software` als getesteter stabiler Default.
- Client-Flags: `--display-mode windowed`, `--no-frame-pacing`, `--no-vsync`, `--absolute-mouse`, `--no-hdr`, `--no-yuv444`.
- Guest/BeagleStream: `encoder = software`, `sw_preset = ultrafast`, `sw_tune = zerolatency`, `capture = x11`, `minimum_fps_target = 60`, `max_bitrate = 35000`.
- Guest/Xorg: `SWCursor` ist fuer den modesetting-Treiber aktiv, damit KMS den Mauszeiger auch ohne dedizierten Cursor-Plane im Videoframe sieht.
- VM-Grafik: libvirt `virtio` video, nicht legacy VGA/Bochs.
- Prozessprioritaet: QEMU, Sunshine und Thinclient-Client koennen mit `scripts/apply-beagle-stream-latency-tuning.sh` auf `Nice=-10` gebracht werden.

## Security-Invarianten

- Public TCP `49995`, `50000`, `50001`, `50021` muss von aussen geschlossen sein.
- Public UDP `50009-50015` muss vor DNAT gedroppt werden.
- `srv1` darf keine Legacy-Tabelle `inet beagle_stream` fuer Public-DNAT enthalten.
- `inet beagle_stream_public_guard` muss mit `hook prerouting priority dstnat - 10` vor DNAT laufen.
- Interne VM-Ports duerfen erreichbar bleiben, damit WireGuard/Broker-Clients streamen koennen.
- Direct-Public ist nur ein expliziter, zeitlich begrenzter Debug-Modus und kein Produktpfad.
- `beagle-public-streams.timer` bleibt im Produktionspfad deaktiviert; `BEAGLE_PUBLIC_STREAMS_ENABLED=1` ist nur fuer bewusst freigegebene Debug-/Sonderfaelle erlaubt.

## Abnahme

```bash
scripts/check-beaglestream-production-baseline.sh \
  --public-ip 46.4.96.80 \
  --host srv1.beagle-os.com \
  --vm-ip 192.168.123.114
```

Optional mit Thinclient-SSH:

```bash
BEAGLE_THINCLIENT_SSH=root@192.168.178.37 \
scripts/check-beaglestream-production-baseline.sh \
  --public-ip 46.4.96.80 \
  --host srv1.beagle-os.com \
  --vm-ip 192.168.123.114
```

Erwartetes Ergebnis: `beaglestream_production_baseline=PASS`.

Fuer Live-E2E-Abnahme mit aktivem Thinclient muss zusaetzlich ein aktueller
WireGuard-Handshake fuer den Thinclient-Peer sichtbar sein:

```bash
scripts/check-beaglestream-production-baseline.sh \
  --public-ip 46.4.96.80 \
  --host srv1.beagle-os.com \
  --vm-ip 192.168.123.114 \
  --require-wg-handshake \
  --wg-peer-allowed-ip 10.88.1.1/32
```

Wenn dieser Modus fehlschlaegt, ist der Serverpfad nicht automatisch kaputt:
Dann ist der Thinclient nicht am Beagle-WireGuard sichtbar oder hat noch keinen
Handshake aufgebaut. In diesem Fall Thinclient lokal oder per SSH pruefen und
`wg-beagle` sowie den BeagleStream-Client neu starten.

## Automatische Wiederherstellung

Stream-VMs erhalten bei der Provisionierung folgende Schutzmechanismen:

- `beagle-guest-network-guardian.timer` prueft alle 30 Sekunden, ob das
  verwaltete Interface bei vorhandenem Carrier eine globale IPv4-Adresse hat.
  Nach zwei fehlgeschlagenen Pruefungen wird zuerst `networkctl reconfigure`
  ausgefuehrt und bei ausbleibender Erholung `systemd-networkd` neu gestartet.
- `beagle-stream-server-healthcheck.timer` prueft neben API und Stream-Port auch
  die X11-Sitzung mit `xrandr`. Alte `kwallet-query`-Prozesse werden nur dann
  beendet, wenn sie mindestens 120 Sekunden alt sind und explizit nach
  `Chrome Safe Storage` fragen. Bleibt X11 ueber den bestehenden
  Fehlerschwellwert unerreichbar, werden Display-Manager und Stream-Dienst neu
  gestartet.
- KWallet ist im provisionierten Desktop deaktiviert, damit unbeaufsichtigte
  Chromium-Prozesse keine Passwortdialoge oder blockierten Helper ansammeln.
- Der Thinclient zeigt die Zielerreichbarkeit als eigenen Startschritt 4 und
  startet den Stream bei einem serverseitigen Capture-/Encoder-503 kontrolliert
  neu.
- Der Thinclient-Audio-Watcher startet PipeWire, `pipewire-pulse` und
  WirePlumber ohne geerbte Lock-Dateideskriptoren. Damit kann der Watcher den
  Audio-Stack dauerhaft pruefen, ohne sich selbst zu blockieren.

Schnellpruefung in der Stream-VM:

```bash
systemctl is-active \
  beagle-guest-network-guardian.timer \
  beagle-stream-server-healthcheck.timer \
  beagle-stream-server-guardian.service \
  beagle-stream-server.service
ip -4 -o addr show scope global
sudo -u <desktop-user> env \
  DISPLAY=:0 XAUTHORITY=/home/<desktop-user>/.Xauthority \
  xrandr --query
pgrep -a -u <desktop-user> -x kwallet-query || true
journalctl -u beagle-guest-network-guardian.service \
  -u beagle-stream-server-healthcheck.service --since -15min
```

Erwartet werden aktive Timer/Guardians, eine globale Gast-IPv4-Adresse, ein
erfolgreiches `xrandr` und keine dauerhaft laufenden Chrome-KWallet-Helper.

Live validiert am 2026-07-30 mit `srv1`/VM100 und Thinclient
`192.168.178.30`: erzwungener IPv4-Verlust wurde automatisch per
`networkctl reconfigure` repariert; X11 und `libx264` erholten sich; der
Thinclient baute RTSP, 1920x1080-Video und Stereo-Audio ohne Queue-Overflows
auf.

## Bekannte Grenze

Dieser Stand ist fluessig und sicher fuer den aktuellen Pilotpfad, aber noch nicht final GeForce-/GameStream-Niveau: Hardware-Encoding auf srv1/VM100 ist noch nicht verfuegbar. Der naechste Produktreife-Schritt ist ein reproduzierbarer NVENC/VAAPI/QSV- oder GPU-Passthrough/vGPU-Pfad plus Capture/Encode/Network/Decode/Render-Metriken.
