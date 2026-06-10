# 03 — Stream Forks Hardening

Stand: 2026-06-10

Beagle OS steht und faellt mit den beiden geforkten Streaming-Kernen. Sie sind
der einzige C++-Code im Produktpfad, laufen in **jeder** Session und sind die
Komponenten mit dem hoechsten Crash- und Latenz-Risiko. Dieses Dokument macht
die Forks zu einem stabilen, wartbaren, beweisbaren Teil des Produkts.

## 1. Die Forks und ihr Upstream

| Fork-Repo | Upstream | Rolle | Beagle-Patch-Oberflaeche |
|---|---|---|---|
| `meinzeug/beagle-stream-server` | `LizardByte/Sunshine` | Stream-Server im Gast (VM100) | `src/beagle/` (Config, BrokerClient, Auth), CMake `BEAGLE_INTEGRATION`, `.deb` |
| `meinzeug/beagle-stream-client` | `moonlight-stream/moonlight-qt` | Stream-Client auf dem TC | `app/beagle/` (Config, Broker, VPN), Session-Integration, Branding |

Vertraglicher Bezugspunkt der Forks ist die Control-Plane-API in
[fork.md](../../fork.md) (`/api/v1/streams/{register,config,events,allocate}`).

### Grundprinzip (bereits Constraint in `fork.md`, hier zur Stabilitaet erhoben)

- **Alle Beagle-Erweiterungen sind nicht-fatal.** Fehlende Config → Fork laeuft
  exakt wie Upstream. Das ist nicht nur Kompatibilitaet, sondern eine
  **Stabilitaetsgarantie**: ein Bug in der Beagle-Schicht darf nie den
  Streaming-Kern mitreissen.
- **Keine neuen Build-Dependencies.** Nur libcurl (Server) und Qt Network
  (Client), die schon da sind. Jede neue Dependency vergroessert die
  Supply-Chain-Angriffsflaeche und die Build-Drift.

## 2. Upstream-Tracking & Drift-Kontrolle (schliesst FK-8)

Das groesste Langzeitrisiko ist **stiller Fork-Drift**: Upstream fixt Crashes
und CVEs, der Fork bleibt zurueck.

- [ ] **Upstream gepinnt per Submodule/Tag**, nicht per Floating-Branch. Der
  Beagle-Code lebt ausschliesslich in `src/beagle/` bzw. `app/beagle/` als
  **additives Overlay**, damit Upstream-Merges konfliktarm bleiben.
- [ ] **Rebase-Kadenz:** mindestens monatlich + sofort bei Upstream-Security-
  Release. Jeder Rebase erzeugt einen Eintrag in `docs/refactor/05-progress.md`
  mit Upstream-Tag, gemergten Commits und Soak-Ergebnis.
- [ ] **CVE-Watch:** automatischer Abgleich der gepinnten Upstream-Version gegen
  Sunshine-/Moonlight-Advisories und die transitive Dependency-Liste; Treffer →
  Ticket mit Severity.
- [ ] **`BEAGLE_INTEGRATION`-Patch-Budget:** die Beagle-Diff bleibt klein und
  reviewbar (Richtwert < ~1500 LOC pro Fork). Waechst sie, wird upstream-faehiger
  Code als PR nach oben gegeben statt im Fork zu akkumulieren.
- [ ] **Vanilla-Build-Schutz:** CI baut beide Forks **mit und ohne**
  `BEAGLE_INTEGRATION`; der Vanilla-Build muss unveraendert gruen bleiben.

## 3. Reproduzierbare, signierte Fork-Builds (S4/S6)

- [ ] **Deterministischer Build:** gepinnte Toolchain/Container, `SOURCE_DATE_
  EPOCH`, sortierte Inputs; zwei Builds desselben Commits liefern identische
  Artefakt-Checksummen (gleiche Regel wie `build-iso.yml` Repro-Check).
- [ ] **SBOM pro Fork** (CycloneDX) inkl. aller statisch gelinkten Libs;
  gebundlet wie im Haupt-`release.yml`.
- [ ] **Signatur:** `.deb`-Artefakte GPG-signiert + Cosign-keyless, analog
  Haupt-Release. Der TC/Gast akzeptiert nur signierte Stream-Artefakte.
- [ ] **Pinned `.deb`-Metadaten:** `Conflicts/Provides/Replaces` sauber, damit
  Update den vorherigen Stream-Stack atomar ersetzt (kein Halb-Zustand).

## 4. Crash- & Health-Telemetrie aus den Forks (S1)

Heute sind die Forks die *am wenigsten* beobachtbare Schicht. Das aendert sich:

- [ ] **Coredump-Capture:** Server (im Gast) und Client (auf dem TC) schreiben
  Coredumps an einen **nicht-volatilen, groessenbeschraenkten** Pfad (FK-1!),
  nie in tmpfs. `systemd-coredump` mit `Storage=` auf Persistenz-Medium +
  `ProcessSizeMax`/Rotation.
- [ ] **Strukturierte Crash-Events:** bei Absturz/Neustart meldet der Fork ein
  Event ueber den bestehenden Broker-Kanal
  (`POST /api/v1/streams/{vm_id}/events`, `event_type=session.error`) — **ohne
  Token/Secret** (bestehender `"[redacted]"`-Constraint).
- [ ] **Watchdog statt blindem Restart:** der Server nutzt `sd_notify`
  WATCHDOG; der Guardian respektiert Hysterese (FK-3) und unterscheidet
  `starting` von `dead`.
- [ ] **Crash-free Session-Rate** (INV-CRASH >= 99,9 %) wird aus diesen Events
  berechnet und ins SLO-Dashboard gespeist.

## 5. QoE-Telemetrie (macht SLO-QOE messbar, S1)

Ohne QoE-Zahlen sind die Stream-SLOs nicht pruefbar. Beide Forks emittieren pro
Session periodisch (low-overhead, samplebar):

- [ ] **Server-seitig:** encodete FPS, Ziel-vs-Ist-Bitrate, Encoder-Queue-Tiefe,
  Encoder-Fehler/Resets, GPU-Encode-Latenz.
- [ ] **Client-seitig:** dekodierte FPS, Frame-Drops, End-to-End-Input-Latenz,
  RTT, Reconnect-Zaehler, Audio-Underruns.
- [ ] Aggregation in Prometheus (bestehender Metrics-Pfad,
  [observability/](../observability/)); Dashboards fuer SLO-QOE-LAT/-FRM und
  SLO-SESS/-RECON.

## 6. Resource-Caps & Crash-Containment (S0/INV-*)

Die Forks duerfen den Host/Gast nie mit in den Abgrund ziehen:

- [ ] **systemd-Resource-Control** fuer beide Dienste: `MemoryHigh`/`MemoryMax`,
  `TasksMax`, sinnvoller `OOMScoreAdjust` (der Stream-Kern soll **nicht** als
  erstes vom OOM-Killer getroffen werden, aber begrenzt bleiben).
- [ ] **`Restart=on-failure` + Backoff** (`RestartSec`, `StartLimitIntervalSec`,
  `StartLimitBurst`) gegen Restart-Sturm (FK-3).
- [ ] **Client auf dem TC** beachtet INV-RAM: kein unbeschraenkter Frame-/Log-/
  Cache-Buffer in RAM-backed FS; Logrotation auf Persistenz-Medium.
- [ ] **GPU-Reset-Ueberleben:** Server-Encode (NVENC/VAAPI, im Gast) und
  Client-Decode (amdgpu auf dem TC) recovern nach GPU-Reset/`amdgpu` TDR statt
  zu haengen (Bezug Chaos-Experiment CX-GPU in
  [05-verification-soak-chaos.md](05-verification-soak-chaos.md)).

## 7. Fork-Soak (S3)

- [ ] **72-h-Dauer-Session** VM100→TC: QoE bleibt im SLO, RSS/FD/GPU-Mem
  flach (FK-7), keine Encoder-Resets ueber Schwelle.
- [ ] **Reconnect-Soak:** periodische WG-Flaps; jede Session reconnectet
  innerhalb SLO-RECON ohne Server-Neustart.
- [ ] **Low-RAM-Soak auf dem TC:** Session laeuft stabil bei kuenstlich
  reduziertem MemAvailable; Client degradiert (Bitrate/FPS) statt zu freezen.

## 8. Fork-CI (S4)

- [ ] Eigene CI je Fork: Build (vanilla + `BEAGLE_INTEGRATION`), Unit-/Smoke-Test
  der `beagle/`-Schicht (Config-Parsing, Broker-Mock, Fail-Closed-Policy),
  `clang-tidy`/ASan/UBSan auf der Beagle-Diff, Repro-Check, SBOM, Signatur.
- [ ] **Contract-Test gegen die Control-Plane:** der Fork-CI ruft eine gemockte
  oder ephemere `stream_http_surface`-Instanz und prueft register/config/
  allocate/events-Kompatibilitaet — fail-fast bei API-Drift (Bezug Risk-Register
  Massnahme 5).
- [ ] Fork-Release triggert einen Smoke auf der Referenzflotte, bevor das `.deb`
  als bevorzugter Runtime-Pfad (D2) markiert wird.

## 9. Akzeption fuer S4 (Forks gehaertet)

- Beide Forks bauen reproduzierbar (zwei Runs, gleiche Checksumme) und signiert.
- Upstream ist gepinnt, CVE-Watch aktiv, letzter Rebase < 30 Tage und im
  Progress-Log dokumentiert.
- Crash- und QoE-Telemetrie erscheinen live im Dashboard; INV-CRASH messbar.
- Vanilla-Build (ohne `BEAGLE_INTEGRATION`) ist gruen — die Beagle-Schicht ist
  beweisbar nicht-fatal.
- Fork-Soak (72 h) und Reconnect-Soak bestanden, ohne Leak/Resets ueber Schwelle.
