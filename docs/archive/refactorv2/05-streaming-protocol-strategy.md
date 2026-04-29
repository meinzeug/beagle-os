# 05 — Streaming- und Protokoll-Strategie

Stand: 2026-04-20

## Stand heute (6.7.0)

- Sunshine wird per `services/sunshine_integration.py` und `templates/ubuntu-beagle/firstboot-provision.sh.tpl` in jede Desktop-VM gesetzt.
- Pairing erfolgt heute teils interaktiv, teils ueber `services/public_sunshine_surface.py`.
- noVNC-Fallback ueber `services/vm_console_access.py` mit guest-side x11vnc.
- Endpoint-Runtime nutzt Moonlight-Embedded und Beagle-Endpoint-OS-Wrapper (`beagle-os/`, `thin-client-assistant/runtime/`).

## Lueckenliste vs Konkurrenz

- **Virtual Display** (Apollo/SudoVDA, Linux DRM virtual display) fuer headless-Hosts und Auto-Resolution-Matching: F.
- **HDR**: F.
- **Multi-Monitor (>=2)**: F.
- **4:4:4 Chroma**: F (heute 4:2:0 default).
- **Hardware-Encoder-Auswahl pro Profil** (NVENC/QSV/VAAPI/AMF/Software): T (Sunshine-Default), kein Pool-Profil.
- **Audio-Input + Mikro + Wacom + Gamepad-Redirect**: T (Moonlight-Stack faehig, nicht durchgaengig getestet/aktiviert).
- **Auto-Pairing per signiertem Token**: F (heute PIN-zentriert).
- **Watermark / Session-Recording im Stream**: F.
- **Stream-Health-Telemetrie ins Session-Object**: F.

## Ziel 7.0

### Backend-Strategie

Beagle OS 7.0 setzt auf **Apollo** als bevorzugten Sunshine-Fork. Begruendung:

- Built-in Virtual Display mit auto-resolution + HDR.
- Per-Client-Permission-Modell.
- Auto-pause/resume Hooks.
- Aktive Maintenance, Sunshine ist verfuegbar als Fallback.

Implementierung:

- `services/streaming_backend.py` (neu): Backend-Selector (apollo|sunshine).
- `templates/ubuntu-beagle/streaming/apollo.service.tpl`: systemd-Service fuer Apollo im Guest.
- `services/streaming_pairing.py` (neu): Auto-Pairing per signiertem Token.

Provider-Neutralitaet: kein direkter Apollo-Code im HTTP-Layer; nur Service-Layer und Template-Layer.

### Virtual Display Linux

- Apollo Virtual Display ist heute Windows-only.
- Fuer Linux: Beagle OS 7.0 verwendet **DRM virtual display** ueber `vkms` Modul oder einen guest-side X11/Wayland virtual head.
- Skript `templates/ubuntu-beagle/virtual-display-setup.sh.tpl` provisioniert beim firstboot:
  - `vkms` Modul laden,
  - virtual outputs konfigurieren,
  - LightDM/Display-Session daran binden.

### Auto-Pairing-Flow

```
User klickt in Web Console "Connect to my desktop"
  -> Control Plane signiert kurzlebigen Pairing-Token (JWT, 60 s, scope: vm-id, user)
  -> Token wird mit dem Endpoint via HTTPS-API ausgeliefert
  -> Endpoint Moonlight-Wrapper benutzt Token gegen Beagle-Streaming-Pairing-Endpoint
  -> Beagle Streaming-Service ruft Apollo-Pairing-API mit serverseitig erzeugtem PIN auf
  -> Pairing erfolgreich, Stream-Session wird im Session-Store eroeffnet
```

Sicherheit:

- Pairing-Tokens sind kurzlebig, an User+VM gebunden.
- Apollo-Pairing-PIN nie an User exponiert.
- Audit-Event `session.pair` mit User, VM, Endpoint.

### Profile

`StreamingProfile` ist Teil des `DesktopPool`-Schemas. Beispiel:

```yaml
streaming:
  backend: apollo
  encoder_pref: nvenc
  fallback_encoders: [vaapi, software]
  resolution_max: 3840x2160
  fps_max: 60
  hdr: true
  multi_monitor: 2
  chroma: "4:4:4"
  audio:
    output: true
    input: true
  redirect:
    keyboard: true
    mouse: true
    gamepad: true
    wacom: true
    usb_classes: [hid, mass_storage]
  watermark:
    enabled: true
    template: "{{user.email}} | {{timestamp}}"
  recording:
    mode: off | on_demand | always
    target: s3://acme-recordings
    retention_days: 30
```

### Telemetrie

- Apollo/Sunshine schreiben Stats; Beagle-Service liest periodisch und schreibt in `Session.health`.
- Web Console zeigt Live-Stats (RTT, FPS, dropped frames, bitrate).
- Prometheus-Export `beagle_stream_*`.

### Migration heute -> 7.0

- 6.7.0-Provisionierung bleibt funktionsfaehig (Sunshine + manuelles Pairing).
- 7.1.1 fuegt Apollo-Backend hinzu, Pool-Profile entscheiden, ob Apollo oder Sunshine.
- Bestehende VMs koennen per Migration-Skript auf Apollo umgestellt werden.

## Endpoint-Seite

Beagle Endpoint OS und der Browser-Client sollen **denselben Pairing-Flow** beherrschen:

- Beagle Endpoint OS: Moonlight-Embedded mit Beagle-Pairing-Plug-in.
- Browser: Moonlight-Web-Client (WebRTC-Bridge) als Fallback.

Beide muessen mindestens HEVC-Decoding und WebRTC-Audio (Opus) unterstuetzen.
