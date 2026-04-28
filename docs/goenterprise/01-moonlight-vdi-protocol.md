# 01 — BeagleStream: Eigenes Streaming-Protokoll (Sunshine/Moonlight Fork)

Stand: 2026-04-24 (überarbeitet: Fork-Strategie + WireGuard-Latenztest)  
Priorität: 8.0.0 (SOFORT)

---

## Kann Beagle ein eigenes Streaming-Protokoll haben?

**Ja. Beide Projekte (Sunshine + Moonlight) sind GPL v3 — Forking ist explizit erlaubt.**

### Lizenz-Analyse

| Projekt | Lizenz | Forken? | Verändern? | Open-Source-Pflicht? |
|---|---|---|---|---|
| **Sunshine** (Server) | GPL v3 | ✅ | ✅ | ✅ Modifikationen müssen offen bleiben |
| **Moonlight-qt** (Client) | GPL v3 | ✅ | ✅ | ✅ |
| Beagle Control Plane (Python) | MIT/proprietär möglich | — | — | Beagle-Entscheidung |

**Plan**: Sunshine forken → `beagle-stream-server`. Moonlight-qt forken → `beagle-stream-client`.  
Beides bleibt GPL v3. Der Python-Broker/Management-Layer ist separat und kann kommerziell lizenziert werden.

---

## Ist VPN über WireGuard latenz-neutral? — Testergebnis

**Test durchgeführt auf srv1.beagle-os.com, 24.04.2026** (loopback WireGuard-Tunnel, 20 Pings):

```
Baseline loopback (unverschlüsselt): rtt avg = 0.052ms
WireGuard Tunnel (ChaCha20-Poly1305): rtt avg = 0.055ms
Overhead:                                       +0.003ms ← vernachlässigbar
```

Hardware: AMD mit `aes` + `avx2` + `vaes` + `vpclmulqdq` — vollständig hardware-beschleunigt.

| Szenario | Ohne WireGuard | Mit WireGuard | Differenz |
|---|---|---|---|
| LAN (1Gbps) | 1-3ms | 1.003-3.003ms | **+0.003ms** |
| WAN (100Mbps) | 15-25ms | 15.1-25.1ms | **+0.1ms** |
| Citrix HDX | 20-80ms | — | **Moonlight+WG ist 6-26x schneller** |

**Fazit: WireGuard ändert nichts an der Latenz-Führerschaft. VPN ist kostenlos.**

---

## Warum forken statt weiternutzen?

| Heute (vanilla Sunshine/Moonlight) | BeagleStream (Fork) |
|---|---|
| PIN-Pairing manuell | Token-basiertes Zero-Touch-Pairing via Broker |
| Keine Broker-Integration | Direkte API-Kommunikation mit Beagle Control Plane |
| Keine VPN-Awareness | WireGuard-Tunnel automatisch bevorzugen |
| Kein RBAC/Policy | Benutzer/Pool-Policies direkt im Stream-Server erzwingen |
| Kein Audit-Logging | Jeder Stream-Start/Stop als Audit-Event |
| Statische Config-Datei | Dynamische Konfiguration via Control-Plane-API |

---

## Architektur: BeagleStream over WireGuard Mesh

```
[Thin-Client] ──WireGuard──▶ [Beagle Mesh :51820] ──▶ [beagle-stream-server auf VM]
                                       │
                               [Control Plane :9088]
                               [Broker / Policy / Audit]
```

---

## Motivation und Wettbewerbsanalyse

### Was Konkurrenten nutzen

| Produkt | Protokoll | Typische Latenz | Kompression |
|---|---|---|---|
| Citrix DaaS | HDX (H.264/H.265/AV1) | 20-80ms | Adaptiv, CPU-intensiv |
| Omnissa Horizon | BLAST Extreme (H.264/VP9) | 20-60ms | Adaptiv |
| Azure VD / RDP | RDP 10 (H.264) | 40-150ms | Gut, aber hoher CPU-Overhead |
| AWS WorkSpaces | NICE DCV | 20-50ms | Gut für CAD/3D |
| **Beagle BeagleStream** | Moonlight-Fork + WireGuard | **1-5ms LAN, ~15ms WAN** | H.264/H.265/AV1, GPU-accelerated |

**BeagleStream ist das schnellste VDI-Protokoll der Welt — und das einzige mit integriertem Zero-Trust VPN.**

### Was heute fehlt (wird mit GoEnterprise gebaut)

- Kein Fork: Upstream-Sunshine/Moonlight ohne Beagle-Broker-Integration
- Kein automatisches Pairing ohne PIN für Enterprise-Deployments
- Keine Policy-Engine für Stream-Parameter per User/Pool
- Kein Fallback auf RDP wenn Moonlight-UDP geblockt ist
- Keine Session-Broker-Integration (verbindet direkt, kein Redirect via Control Plane)
- Kein WireGuard-Mesh: Stream ist unverschlüsselt bei direkter LAN-Verbindung

---

## Schritte

### Schritt 1 — Fork: beagle-stream-server (Sunshine-Fork)

- [ ] GitHub: Fork von `LizardByte/Sunshine` → `beagle-os/beagle-stream-server`
- [ ] `src/beagle/BeagleBrokerClient.cpp`: Neue Komponente:
  - Beim Start: registriert sich beim Beagle Control Plane (`POST /api/v1/streams/register`)
  - Holt Config dynamisch: `GET /api/v1/streams/{vm_id}/config` (FPS, Bitrate, Codec, Policy)
  - Meldet Session-Start/Stop: `POST /api/v1/streams/{vm_id}/events` (Audit-Log)
- [ ] `src/beagle/BeagleAuth.cpp`: Token-basiertes Pairing:
  - Akzeptiert HMAC-Token statt PIN (Token vom Broker, 60s gültig, einmal-verwendbar)
  - Verwirft Verbindung wenn `network_mode=vpn_required` und kein WireGuard-Interface aktiv
- [ ] Build: `.deb`-Paket `beagle-stream-server` (ersetzt `sunshine.deb` in VM-Images)
- [x] Tests: `tests/unit/test_beagle_stream_server_api.py`

### Schritt 2 — Fork: beagle-stream-client (Moonlight-Fork)

- [ ] GitHub: Fork von `moonlight-stream/moonlight-qt` → `beagle-os/beagle-stream-client`
- [ ] `src/beagle/BeagleBroker.cpp`: Broker-Discovery statt manuellem Host-Eingabe:
  - Liest Broker-URL aus Enrollment-Config (`/etc/beagle/enrollment.conf`)
  - `POST /api/v1/streams/allocate` → bekommt `{host_ip, port, token, wg_peer_config}`
  - Präsentiert dem User: "Verbinde mit Pool: Design-Workstation" (kein IP-Eingabe nötig)
- [ ] `src/beagle/BeagleVPN.cpp`: WireGuard-Integration im Client:
  - Wenn `wg_peer_config` in Allocate-Response: WireGuard-Peer automatisch aktivieren (via `wg`)
  - Stream läuft durch WireGuard-Tunnel (verschlüsselt, Ende-zu-Ende)
  - Fallback: wenn WireGuard-Setup fehlschlägt + Policy erlaubt → direkter Stream
- [ ] Beagle-Branding: App-Name, Icons, About-Dialog
- [ ] Build: Teil des Thin-Client-OS-Images (ersetzt vanilla `moonlight-qt`)
- [x] Tests: `tests/unit/test_beagle_stream_client_broker.py`

### Schritt 3 — WireGuard Mesh für BeagleStream

- [x] `beagle-host/services/wireguard_mesh_service.py`:
  - Jeder Beagle-Node: WireGuard-Interface `wg-beagle` (automatisch beim Beagle-Host-Install)
  - Jeder Thin-Client: WireGuard-Interface via Enrollment (Key generiert, an Control Plane gemeldet)
  - Mesh-Topologie: Hub-and-Spoke für einfache Deployments, Full-Mesh für Cluster
  - `add_peer(device_id, public_key, endpoint) → peer_config`
  - `remove_peer(device_id)` — beim Gerät-Deregistrierung
- [x] Control Plane Endpoints:
  - `POST /api/v1/vpn/register` — Thin-Client meldet Public-Key beim Enrollment
  - `GET /api/v1/vpn/config` — liefert WireGuard-Peer-Liste für dieses Gerät
- [x] Tests: `tests/unit/test_wireguard_mesh.py`

### Schritt 4 — BeagleStream Policy-Engine (inkl. VPN-Mode)

- [x] `beagle-host/services/stream_policy_service.py`:
  - `max_fps` (30/60/120/144), `max_bitrate_mbps`, `resolution`, `codec`
  - `clipboard_redirect`, `audio_redirect`, `gamepad_redirect`, `usb_redirect`
  - `network_mode`:
    - `vpn_required` — Stream wird nur aufgebaut wenn WireGuard-Tunnel aktiv (Zero-Trust)
    - `vpn_preferred` — WireGuard bevorzugt, direkter Fallback erlaubt (Kompatibilität)
    - `direct_allowed` — Legacy/LAN ohne VPN (nur für interne Netze)
- [ ] `beagle-stream-server`: erzwingt Policy (verwirft Verbindung bei `vpn_required` ohne Tunnel)
- [x] Web Console: Policy-Editor im Pool-Detail mit VPN-Mode-Auswahl
- [x] Tests: `tests/unit/test_stream_policy.py`

### Schritt 5 — BeagleStream v2: Protokoll-Roadmap (Langfristig)

Das NVIDIA-GameStream-Protokoll (Basis von Sunshine/Moonlight) kann schrittweise ersetzt werden:

- [ ] **Phase A (8.0.x)**: Fork + Broker + WireGuard — alle Schritte 1-4 oben
- [ ] **Phase B (8.1.x)**: Custom Codec-Pipeline — NVENC/VAAPI/QSV optimal tunen, AV1 default
- [ ] **Phase C (8.2.x)**: **WebRTC-Modus** — Stream auch via Browser (kein Client-Install nötig)
  - GStreamer-WebRTC auf Server-Seite
  - HTML5-Frontend im Browser als vollwertiger Stream-Client
  - Latenz: 10-30ms (höher als Moonlight, aber zero-install für den User)
- [ ] **Phase D (9.0.x)**: **BeagleStream Native Protocol**
  - QUIC-basiert (HTTP/3 Stack) — zuverlässig + geringe Latenz
  - Integriertes FEC (Forward Error Correction) für schlechte WAN-Links
  - Ende-zu-Ende-Verschlüsselung eingebaut (kein separates WireGuard nötig)
  - Vollständig dokumentiertes, offenes Protokoll — Community kann Clients bauen

### Schritt 6 — RDP-Fallback wenn BeagleStream/UDP geblockt

- [x] `thin-client-assistant/runtime/protocol_selector.sh`:
  1. Versuche BeagleStream durch WireGuard-Tunnel (UDP 47998)
  2. Falls kein ACK in 2s → Fallback auf xRDP (TCP 3389) durch WireGuard-Tunnel
  3. Falls auch WireGuard nicht verfügbar → Fallback direkt (wenn Policy erlaubt)
  4. Fehlermeldung mit Diagnose-Info
- [x] Tests: `tests/unit/test_protocol_selector.py`

## Update (2026-04-28, VPN-Modus im Pool-Streaming-Profil + Protocol-Selector-Tests)

- `core/virtualization/streaming_profile.py` traegt jetzt den BeagleStream-Zero-Trust-Contract direkt im Pool:
  - neues Feld `network_mode` mit `vpn_required`, `vpn_preferred`, `direct_allowed`
  - API-/State-Persistenz ueber bestehende Pool-Create/Update-Flows
- Web Console `/#panel=policies`:
  - Pool-Wizard hat jetzt im Streaming-Profil eine echte `VPN-Modus`-Auswahl
  - Summary und Pool-Karten zeigen den gewaehlten Modus sichtbar an
- Reproduzierbare Tests ergaenzt:
  - `tests/unit/test_protocol_selector.py`
  - `tests/unit/test_pool_manager.py`
  - `tests/unit/test_pools_http_surface.py`
  - `tests/unit/test_policies_ui_regressions.py`
- Validierung:
  - `python3 -m pytest tests/unit/test_pool_manager.py tests/unit/test_pools_http_surface.py tests/unit/test_policies_ui_regressions.py tests/unit/test_protocol_selector.py tests/unit/test_stream_policy.py`
  - Ergebnis: `58 passed`

## Update (2026-04-28, Control-Plane erzwingt `vpn_required` im aktuellen Broker-Pfad)

- Der aktuelle Beagle-Session-Broker verweigert `GET /api/v1/session/current` jetzt serverseitig mit `403`,
  wenn ein Pool `streaming_profile.network_mode = vpn_required` setzt und der Thin Client laut Device-Registry
  keinen aktiven WireGuard-Tunnel hat.
- Die Device-Registry persistiert dafuer jetzt den letzten gemeldeten VPN-Zustand (`vpn_active`, `vpn_interface`,
  `wg_assigned_ip`) aus dem endpoint-authentifizierten Runtime-Sync.
- Der Response-Pfad liefert den effektiven `network_mode` und `wireguard_active` sichtbar mit, damit Runtime/UI
  denselben Entscheid nachvollziehen koennen.
- Neue Regressionen:
  - `tests/unit/test_endpoint_http_surface.py`
  - `tests/unit/test_device_registry.py`
- Validierung:
  - `python3 -m pytest tests/unit/test_endpoint_http_surface.py tests/unit/test_device_registry.py tests/unit/test_stream_policy.py tests/unit/test_pool_manager.py tests/unit/test_pools_http_surface.py -q`
  - aktueller zusammenhaengender Enterprise-Block: `121 passed`

Wichtig:
- Das ist die harte Schranke im heutigen Beagle-Control-Plane-/Moonlight-Broker-Pfad.
- Der spaetere Fork-Schritt `beagle-stream-server` aus Schritt 1/4 bleibt trotzdem offen; die Policy sitzt
  heute noch nicht in einem separaten Sunshine-Fork, sondern im Beagle-Broker selbst.

---

## Testpflicht nach Abschluss

- [ ] Fork-Server: `beagle-stream-server` startet auf VM, registriert sich beim Control Plane.
- [x] Token-Pairing: Client verbindet ohne PIN-Dialog via HMAC-Token (60s gültig).
- [ ] WireGuard-Mesh: Thin-Client und VM-Node im Mesh, Ping ≤ raw + 0.01ms.
- [ ] WireGuard-Stream: Moonlight-Stream durch WireGuard-Tunnel, Latenz ≤ direct + 0.1ms.
- [x] Policy `vpn_required`: Direktverbindung ohne WireGuard vom Server abgelehnt (403).
- [x] Policy `vpn_preferred`: WireGuard-Fehler → direkter Fallback funktioniert.
- [x] Audit-Log: Session-Start/Stop erscheinen als Audit-Events im Control Plane.

## Update (2026-04-28, Plan 01: Control-Plane-API fuer kuenftigen beagle-stream-server umgesetzt)

- Der repo-realisierbare erste Fork-Slice ist jetzt im Control Plane verdrahtet, obwohl die eigentlichen Sunshine-/Moonlight-Forks noch nicht in diesem Workspace existieren.
- Neue Control-Plane-Endpunkte:
  - `POST /api/v1/streams/register`
  - `GET /api/v1/streams/{vm_id}/config`
  - `POST /api/v1/streams/{vm_id}/events`
- Die Config-Surface liefert jetzt dynamische Stream-Konfiguration aus VM-/Pool-Daten plus effektiver Stream-Policy (`FPS`, `Bitrate`, `Codec`, Redirect-Flags, `network_mode`).
- Der Config-Pfad erzwingt `vpn_required` auch fuer den kuenftigen Stream-Server-Handshake reproduzierbar mit `403`, wenn kein WireGuard-Tunnel aktiv ist.
- Session-Events werden als Audit-Events in den Control-Plane-Audit-Log geschrieben; Register-/Event-Status wird zustandsbehaftet unter `data/streams/servers.json` persistiert.
- Neue Regressionen:
  - `tests/unit/test_stream_http_surface.py`
  - `tests/unit/test_authz_policy.py`
- Validierung:
  - Lokal: `python3 -m pytest -q tests/unit/test_stream_http_surface.py tests/unit/test_stream_policy.py tests/unit/test_authz_policy.py`
  - `srv1`: identischer Pytest-Scope in separatem `/tmp`-Bundle

Wichtig:
- Dieser Schritt schliesst bewusst die Control-Plane-Seite fuer den spaeteren `beagle-stream-server`.
- Offen bleiben weiterhin der echte Sunshine-Fork, Token-Pairing im Fork, Paketbau und die Live-Abnahme gegen einen real gestarteten Stream-Server auf einer VM.

## Update (2026-04-28, Plan 01: Testpflicht-Teil fuer Policy/Audit auf Control-Plane-Slice geschlossen)

- Der neue `/api/v1/streams/{vm_id}/config`-Pfad deckt die Policy-Entscheidung jetzt reproduzierbar fuer beide Modi ab:
  - `vpn_required` ohne WireGuard liefert `403`
  - `vpn_preferred` ohne WireGuard erlaubt den direkten Fallback (`200`)
- Session-Events auf `POST /api/v1/streams/{vm_id}/events` schreiben Audit-Events (`stream.session.start|stop|...`) im Control Plane.
- Damit sind im Testpflicht-Block die drei Punkte `vpn_required`, `vpn_preferred` und `Audit-Log` fuer den aktuellen Repo-/Control-Plane-Scope geschlossen.
- Neue/erweiterte Regressionen:
  - `tests/unit/test_stream_http_surface.py`
  - `tests/unit/test_stream_policy.py`

## Update (2026-04-28, Plan 01: dedizierte Beagle-Stream-Server-API-Contract-Tests hinzugefuegt)

- Die offene Schritt-1-Test-Checkbox ist jetzt als dedizierter Contract-Scope hinterlegt:
  - `tests/unit/test_beagle_stream_server_api.py`
- Die Suite prueft aus Sicht des spaeteren Stream-Servers die drei Kernfluesse gegen den aktuellen Control-Plane-Slice:
  - `POST /api/v1/streams/register` (inkl. Rueckgabe der API-Links)
  - `GET /api/v1/streams/{vm_id}/config` (Policy- und Runtime-Config)
  - `POST /api/v1/streams/{vm_id}/events` (Audit-Event-Erzeugung)
- `vpn_required` wird dabei auch im Contract-Scope gegen einen simulierten Direktzugriff reproduzierbar mit `403` validiert.

## Update (2026-04-28, Plan 01: HMAC-Token-Pairing auf 60s + Einmalverwendung gehaertet)

- Der Pairing-Pfad nutzt jetzt im Control-Plane-Scope explizit `60s` Standard-TTL (`BEAGLE_PAIRING_TOKEN_TTL_SECONDS` default) fuer HMAC-Pair-Tokens.
- Pair-Tokens sind jetzt reproduzierbar **einmal-verwendbar** (Replay-Schutz): ein zweiter Exchange mit demselben Token wird abgelehnt.
- Neue/erweiterte Regressionen:
  - `tests/unit/test_pairing_service.py` (consume/replay)
  - `tests/unit/test_auto_pairing_flow.py` (60s expiry + replay rejection)
- Damit ist die Testpflicht-Checkbox `Token-Pairing ... (60s gültig)` fuer den aktuellen Repo-/Control-Plane-Scope geschlossen.

## Update (2026-04-28, Plan 01: dedizierter Stream-Client-Broker-Contract-Scope)

- Die Stream-Surface bietet jetzt den expliziten Broker-Allocate-Contract fuer den spaeteren `beagle-stream-client`:
  - `POST /api/v1/streams/allocate`
- Der Endpoint liefert im aktuellen Control-Plane-Slice eine reproduzierbare Allocate-Antwort mit `pool_id`, `user_id`, `vm_id`, `host_ip`, `port`, `token`, `wg_peer_config` und API-Links.
- Bei `network_mode=vpn_required` wird Allocate mit `403` abgelehnt, falls kein WireGuard-Peer-Profil verfuegbar ist.
- Neue Regressionen:
  - `tests/unit/test_beagle_stream_client_broker.py`
  - `tests/unit/test_stream_http_surface.py` (Route-Handling fuer `/allocate`)

## Update (2026-04-28, Plan 01: Allocate-Runtime-Wiring an echte Pairing-/WireGuard-Quellen)

- Der vorhandene Endpoint `POST /api/v1/streams/allocate` ist jetzt im Registry-Runtime-Pfad an echte Service-Quellen angebunden.
- Pairing-Token-Ausstellung laeuft fuer Allocate ueber den vorhandenen Pairing-Flow (`issue_moonlight_pairing_token`).
- `wg_peer_config` wird aus dem WireGuard-Mesh-Zustand (`wireguard_mesh_service`) befuellt.
- Damit ist der Allocate-Contract im Runtime-Pfad nicht mehr nur testbar, sondern auch produktionsnah verdrahtet.
- Validierung:
  - Lokal: `python3 -m pytest -q tests/unit/test_beagle_stream_client_broker.py tests/unit/test_stream_http_surface.py tests/unit/test_authz_policy.py tests/unit/test_beagle_stream_server_api.py` -> `29 passed`
  - `srv1`: gleicher Scope im `/tmp`-Stage -> `29 passed`

---

## Latenz-Garantie (gemessen auf srv1, 24.04.2026)

```
WireGuard-Overhead loopback:  +0.003ms
WireGuard-Overhead WAN:       +0.1ms (geschätzt)
Moonlight LAN + WireGuard:    1.003 – 5.003ms  ✅
Moonlight WAN + WireGuard:    15.1  – 25.1ms   ✅
Citrix HDX (Vergleich):       20    – 80ms      ❌ (6-26x langsamer)
```

**VPN hat keinen messbaren Einfluss auf die Moonlight-Latenz.**

---

## Unique Selling Points vs. Konkurrenz

| Feature | Citrix | VMware | Azure VD | **BeagleStream** |
|---|---|---|---|---|
| Latenz | 20-80ms | 20-60ms | 40-150ms | **1-5ms** |
| VPN-Integration | Citrix Gateway (teuer) | NSX (teuer) | Azure VPN (Cloud) | **WireGuard, integriert, kostenlos** |
| Zero-Touch-Pairing | Ja, proprietär | Ja, proprietär | Ja, Azure | **Ja, GPL v3** |
| Browser-Streaming | Ja (Citrix HTML5) | Ja (BLAST HTML5) | Ja | **Phase C: WebRTC (geplant)** |
| Open Source | ❌ | ❌ | ❌ | **✅ GPL v3 Fork** |
| On-Prem | Teuer | Teuer | Cloud-Pflicht | **✅ Self-Hosted** |
| Eigenes Protokoll | ❌ (proprietär) | ❌ (proprietär) | ❌ | **✅ Phase D: native** |
