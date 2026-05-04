# 02 — Streaming, Endpoint OS, Thin Client, Kiosk

**Scope**: BeagleStream-Protokoll, Endpoint/Thin-Client-OS, Gaming-Kiosk, Pairing-/Enrollment-Lifecycle.
**Quelle**: konsolidiert aus `docs/archive/goenterprise/01,02,03,07,08` und `docs/archive/gofuture/11,19`.

---

## BeagleStream Protocol (BeagleStream Server/BeagleStream Client Fork)

**Korrektur 2026-05-03**: Die Fork-Repositories existieren und sind in den Beagle-OS-Artefaktpfad eingebunden, aber der Produktumbau ist noch nicht abgeschlossen. Beagle-Pfade muessen token-native werden; vorhandene PIN-/Moonlight-/Sunshine-Kompatibilitaet ist nur Uebergangsbruecke und kein Zielzustand.

- [ ] **Phase A 8.0.x** — Fork `meinzeug/beagle-stream-server` → echtes BeagleStream-Server-Produkt abschliessen
  - [x] `src/beagle/BeagleBrokerClient.cpp` (Broker-getriebenes Pairing)
  - [ ] `src/beagle/BeagleAuth.cpp` token-native machen: kein `nvhttp::pin(token, name)`-Shim, sondern Manager-/Signatur-/Expiry-/One-Time-Use-Validierung
  - [ ] `/api/pin` in Beagle-Builds deaktivieren oder strikt als Upstream-Kompatibilitaet isolieren
  - [ ] Server-Token-Rotation und Revocation gegen Beagle Manager verdrahten
  - [x] `.deb`-Paket `beagle-stream-server` ersetzt `beagle-stream-server.deb` in VM-Images
- [ ] **Phase A 8.0.x** — Fork `meinzeug/beagle-stream-client` → echtes BeagleStream-Client-Produkt abschliessen
  - [x] `app/beagle/BeagleBroker.cpp` (Broker-Discovery)
  - [x] `app/beagle/BeagleVPN.cpp` (WireGuard-Integration)
  - [x] Beagle-Branding (Name, Icons, About)
  - [x] In Thin-Client-OS-Image gebundelt: Build versucht standardmaessig `meinzeug/beagle-stream-client` Release `beagle-phase-a` und kann per `PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_URL` ueberschrieben werden; Runtime startet bei Enrollment ohne statischen Host hostless gegen den Broker.
  - [ ] CLI/UI auf Pairing-Token statt PIN umbenennen; Beagle-Runtime darf keine neue PIN-Benennung einfuehren.
  - [x] Broker-Start nutzt explizit `host:port app`, wenn der Manager ein Ziel geliefert hat; stale lokale Hosteintraege duerfen nicht gewinnen. Live-Hotfix/Abnahme 2026-05-04: lokaler Thinclient `ubuntu-beagle-100` meldet `broker_allocation_reachable=1`, `beagle_stream_client_target_reachable=1`, `update_state=current`.
- [ ] **Phase B 8.1.x** — NVENC/VAAPI/QSV Tuning, AV1 default
- [ ] **Phase C 8.2.x** — WebRTC-Modus (Browser-Stream ohne Client-Install)
- [ ] **Phase D 9.0.x** — BeagleStream Native Protocol (eigener Codec/Transport)

## WireGuard Mesh

- [ ] WireGuard-Mesh: Thin-Client + VM-Node, Ping ≤ raw + 0.01 ms
- [ ] WireGuard-Stream: Beagle Stream Client-Stream durch Tunnel, Latenz ≤ direct + 0.1 ms

## Endpoint OS / Thin Client

- [x] Thin Client Install / Enrollment / QR-Pairing live
- [x] Streaming-Stream-Persistenz ueber Voll-Reboot (srv1 PASS)
- [x] Beagle Stream Server Stream-Prep unattended (`ensure-vm-stream-ready.sh`) — VM100 PASS
- [x] VM102 Provider-State unblocken + Rerun (externe Inventar-Diskrepanz) — auf `srv1` als echte zweite VM `beagle-102` neu aufgebaut, eigene Guest-IP `192.168.123.116` gesetzt, `ensure-vm-stream-ready.sh --vmid 102 --node beagle-0` mit `RC=0`.
- [ ] Endpoint-Update-Architektur live in Hardware-Test-Matrix

## Gaming Kiosk

- [x] Kiosk Pools + Library-Sync (Welle 7.1.0)
- [x] Pool blockiert sauber wenn keine GPU verfuegbar (R3) — `GPU_POOL_NO_GPU_SMOKE=PASS` auf `srv1` (2026-04-30, state=pending-gpu, allocation blocked)

## Session Lifecycle

- [x] Pairing-Token-Generation, Rotation, Revocation (Integration-Test gruen)
- [x] Session Recording + Watermark (Welle 7.2.1)
- [x] Stream Reconnect nach Host-/VM-Reboot in WebUI sichtbar (R3) — `SSE_RECONNECT_SMOKE=PASS` auf `srv1` (2026-04-30, events=[hello,tick], 8 Regressionstests gruen)
- [x] Stream-Health-Reporting + Audit-Update live validiert (`STREAM_HEALTH_AUDIT_SMOKE=PASS` auf `srv1`, 2026-04-30)
- [x] Audit-Eintrag bei echtem Stream-Abbruch/Timeout (R3) — `STREAM_TIMEOUT_AUDIT_SMOKE=PASS` auf `srv1` (2026-04-30, `action=stream.session.timeout`, `result=failure`)
