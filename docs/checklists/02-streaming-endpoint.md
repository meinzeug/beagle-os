# 02 — Streaming, Endpoint OS, Thin Client, Kiosk

**Scope**: BeagleStream-Protokoll, Endpoint/Thin-Client-OS, Gaming-Kiosk, Pairing-/Enrollment-Lifecycle.
**Quelle**: konsolidiert aus `docs/archive/goenterprise/01,02,03,07,08` und `docs/archive/gofuture/11,19`.

---

## BeagleStream Protocol (Sunshine/Moonlight Fork)

- [ ] **Phase A 8.0.x** — Fork `LizardByte/Sunshine` → `meinzeug/beagle-stream-server`
  - [ ] `src/beagle/BeagleBrokerClient.cpp` (Broker-getriebenes Pairing)
  - [ ] `src/beagle/BeagleAuth.cpp` (Token-basiert)
  - [ ] `.deb`-Paket `beagle-stream-server` ersetzt `sunshine.deb` in VM-Images
- [ ] **Phase A 8.0.x** — Fork `moonlight-stream/moonlight-qt` → `meinzeug/beagle-stream-client`
  - [ ] `src/beagle/BeagleBroker.cpp` (Broker-Discovery)
  - [ ] `src/beagle/BeagleVPN.cpp` (WireGuard-Integration)
  - [ ] Beagle-Branding (Name, Icons, About)
  - [ ] In Thin-Client-OS-Image gebundelt
- [ ] **Phase B 8.1.x** — NVENC/VAAPI/QSV Tuning, AV1 default
- [ ] **Phase C 8.2.x** — WebRTC-Modus (Browser-Stream ohne Client-Install)
- [ ] **Phase D 9.0.x** — BeagleStream Native Protocol (eigener Codec/Transport)

## WireGuard Mesh

- [ ] WireGuard-Mesh: Thin-Client + VM-Node, Ping ≤ raw + 0.01 ms
- [ ] WireGuard-Stream: Moonlight-Stream durch Tunnel, Latenz ≤ direct + 0.1 ms

## Endpoint OS / Thin Client

- [x] Thin Client Install / Enrollment / QR-Pairing live
- [x] Streaming-Stream-Persistenz ueber Voll-Reboot (srv1 PASS)
- [x] Sunshine Stream-Prep unattended (`ensure-vm-stream-ready.sh`) — VM100 PASS
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
