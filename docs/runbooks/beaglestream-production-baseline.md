# BeagleStream Production Baseline

Stand: 2026-05-07

Dieser Runbook-Eintrag friert den auf VM100/srv1/lokalem Thinclient live validierten Zustand ein. Er ist der aktuelle produktionsnahe Standard fuer Kundenbetrieb, bis Hardware-Encoding und native Latenzmetriken nachgezogen sind.

## Baseline

- Transport: Broker/WireGuard, kein Public-BeagleStream-DNAT.
- Server-Ziel: interne VM-IP, z. B. `192.168.123.114:50000`.
- Qualitaet: `1920x1080`, `60 fps`, `32000 kbps`, H.264.
- Thinclient-Renderer: SDL/OpenGL, Vulkan deaktiviert.
- Thinclient-Decode: `software` als getesteter stabiler Default.
- Client-Flags: `--display-mode windowed`, `--no-frame-pacing`, `--no-vsync`, `--absolute-mouse`, `--no-hdr`, `--no-yuv444`.
- Guest/Sunshine: `encoder = software`, `sw_preset = ultrafast`, `sw_tune = zerolatency`, `capture = kms`, `minimum_fps_target = 60`, `max_bitrate = 35000`.
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

## Bekannte Grenze

Dieser Stand ist fluessig und sicher fuer den aktuellen Pilotpfad, aber noch nicht final GeForce-/GameStream-Niveau: Hardware-Encoding auf srv1/VM100 ist noch nicht verfuegbar. Der naechste Produktreife-Schritt ist ein reproduzierbarer NVENC/VAAPI/QSV- oder GPU-Passthrough/vGPU-Pfad plus Capture/Encode/Network/Decode/Render-Metriken.