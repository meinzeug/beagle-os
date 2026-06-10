# 05 — Verification, Soak & Chaos

Stand: 2026-06-10

Stabilitaet, die nicht gemessen wird, existiert nicht. Dieses Dokument definiert,
**wie SpaceBee Stabilitaet beweist**: gruene Basis in CI, Langlauf-Soak und
gezielte Chaos-Experimente auf echter Hardware.

## 1. Zero-Known-Defect-Basis (S0)

### 1.1 Die 11 roten Tests schliessen

Im letzten Full-Suite-Lauf: **11 failed, 1942 passed**. Per Stash-Test bestaetigt
**vorbestehend** und unabhaengig vom Freeze-Fix. Sie sind die erste S0-Schuld.

- [ ] Jeder der 11 Fehlschlaege bekommt: Root-Cause, Fix **oder** dokumentierte
  Quarantaene mit Ticket. Betroffene Domaenen (Ausgangsbefund):
  `test_auto_pairing_flow` (3), `test_download_page_release_channel_regressions`,
  `test_goenterprise_zero_trust_acceptance`,
  `test_publish_public_update_artifacts_prerelease_regressions`,
  `test_sqlite_db`, u. a.
- [ ] **CI-Gate:** `tests.yml` schaltet die Full-Suite auf **hard-fail bei
  jedem roten Test** (kein "bekannt rot" mehr). Quarantaene ist ein expliziter,
  gezaehlter, befristeter Marker — kein stilles Ignorieren.

### 1.2 Flaky-Quarantaene

- [ ] Flaky-Detektor (Mehrfachlauf/Retry-Statistik) markiert instabile Tests;
  Quarantaene-Liste ist sichtbar, befristet und schrumpfend. Ein Test in
  Quarantaene blockiert kein Release, ein **wachsender** Quarantaene-Zaehler
  schon.

### 1.3 Kritische-Pfad-Coverage

- [ ] Coverage-Gate (bereits `pytest-cov` in `tests.yml`) wird auf die
  Stabilitaets-kritischen Module **hart**: Volatile-Write-Guard, Health-/Guardian-
  Logik, Update-/Rollback-Pfad, Fail-Closed-Policies, Lock-/Idempotenz-Helfer.

## 2. Soak-Tests (S3) — Stabilitaet ueber Zeit

Ziel: FK-7 (Lecks) und schleichende Degradation beweisbar ausschliessen. Laeuft
auf der Referenzflotte, nicht nur in CI.

| ID | Soak | Dauer | Pass-Kriterium |
|---|---|---|---|
| SOAK-SESS | Dauer-Stream VM100 → TC | 72 h | QoE im SLO; RSS/FD/GPU-Mem flach; 0 Freeze |
| SOAK-RECON | periodische WG-Flaps waehrend Session | 24 h | jeder Reconnect <= SLO-RECON; kein Server-Restart |
| SOAK-LOWRAM | TC mit kuenstlich reduziertem MemAvailable | 24 h | Client degradiert statt Freeze; INV-RAM gehalten |
| SOAK-API | Control-Plane unter Dauerlast (allocate/config/events) | 48 h | p99 <= SLO-API; keine FD-/Memory-Drift; Job-Queue ohne Stau |
| SOAK-UPD | wiederholte A/B-Update-Zyklen | 50 Zyklen | jeder Switch atomar; 0 Halb-Zustand; Auto-Rollback bei Inject-Fail |

- [ ] **Leak-Trend-Auswertung:** lineare Regression auf RSS/FD/Disk ueber das
  Soak-Fenster; Steigung signifikant > 0 → Fail.
- [ ] Soak-Ergebnisse landen als Protokoll unter
  `docs/runbooks/evidence/` und im Progress-Log.

## 3. Chaos- & Fault-Injection (S5) — Stabilitaet unter Stoerung

Gezielte, reproduzierbare Stoerungen auf echter Hardware. Jedes Experiment hat
eine **Hypothese** (erwartetes Recovery) und ist bestanden, wenn das System
innerhalb SLO **ohne Live-Eingriff** recovered.

| ID | Stoerung | Erwartetes Verhalten |
|---|---|---|
| CX-KILL | `kill -9` jedes kritischen Daemons (Broker, Stream-Server, Stream-Client, Update, Tray) | Watchdog/Restart recovered; Session reconnectet oder bleibt; kein Datenverlust |
| CX-MEM | Memory-Pressure-Injection auf dem TC (Ballast-Allokator) | Volatile-Write-Guard + zram greifen; kein Freeze; INV-RAM/PSI gehalten |
| CX-NET | WireGuard-Partition / Paketverlust / Latenz-Spike | Stream degradiert + reconnectet; `vpn_required` bleibt fail-closed |
| CX-DISK | Persistenz-Medium / State-Volume volllaufen lassen | Update/Backup defern + alarmieren; kein Stillstand; INV-DISK |
| CX-REBOOT | harter Host-Reboot (`srv1` / VM-Host) waehrend aktiver Session | Dienste kommen healthy hoch; State konsistent (WAL); VM erreicht `ready` |
| CX-POWER | Stromausfall am TC mitten in Session/Update | Boot-Integritaet; A/B-Slot konsistent; kein bricked Medium |
| CX-GPU | GPU-Reset/TDR (amdgpu TC-Decode, Encoder im Gast) | Decode/Encode recovern; Session friert nicht ein |
| CX-CLOCK | Clock-Skew / NTP-Sprung | HMAC-Token-Fenster (60 s) toleriert Skew kontrolliert; keine Auth-Massen-Fehler |
| CX-UPD | Update mitten im Switch abbrechen | atomarer Rollback auf alten Slot; Knoten bleibt bootfaehig |

- [ ] **Game-Day-Kadenz:** mindestens ein unangekuendigter Chaos-Drill pro
  Release-Kandidat; Ergebnis ins Incident-Runbook zurueckgespiegelt.
- [ ] Chaos-Tooling ist skriptbar und versioniert (`scripts/chaos/` o. ae.),
  damit Experimente reproduzierbar sind.

## 4. Hardware-in-the-Loop (S5/S3, Bezug Diamond D6)

- [ ] Reale GPU-Streaming-Session mit Latenz-/Qualitaetsmesswerten (NVENC im
  Gast, amdgpu-Decode am TC).
- [ ] VFIO-/GPU-Konfig ueberlebt Host-Reboot (Bezug `checklists/01-platform.md`,
  P2).
- [ ] TC-Boot auf echter Hardware aus **frischem Payload** (Cold-Boot, kein
  Hotpatch) — schliesst die offene D2-Luecke aus Stabilitaetssicht.

## 5. Release-Reproduzierbarkeit & Supply-Chain (S6)

- [ ] **Repro-Gate:** zwei Builds desselben Commits → identische Checksummen
  (Haupt-ISO via `build-iso.yml`, beide Forks via Fork-CI).
- [ ] **Signatur + SBOM** durchgehend: `release.yml` (GPG + Cosign + CycloneDX)
  plus Fork-Artefakte.
- [ ] **Canary/Staged-Rollout:** neue Version geht erst auf einen Kanary-Knoten
  der Referenzflotte; Auto-Rollback bei Health-Fail, bevor Breitenrollout.
- [ ] **No-Regression-Gate:** Release blockiert, wenn ein S-Gate rot oder ein
  Error-Budget gerissen ist.

## 6. Stabilitaets-Telemetrie als Test (S1-Verzahnung)

- [ ] Synthetische Monitore fahren die User-Journeys (Boot→Desktop, allocate,
  reconnect) periodisch gegen die Referenzflotte und speisen die SLI-Messung —
  so wird die SLO-Einhaltung kontinuierlich statt nur zum Soak-Zeitpunkt geprueft.
- [ ] Alerting auf Multi-Window-Burn-Rate (siehe
  [01-stability-charter.md](01-stability-charter.md) §2.3).

## 7. Verifikations-Matrix (Kurzform)

| S-Gate | Primaerer Nachweis | Ort |
|---|---|---|
| S0 | 0 rote Tests + Guard/Watchdog/Cap vorhanden | CI (`tests.yml`, `lint.yml`) |
| S1 | Dashboards + Crash/QoE-Events live | [observability/](../observability/) |
| S2 | CX-KILL/CX-MEM/CX-NET + Auto-Rollback PASS | Chaos-Report + Runbook |
| S3 | SOAK-* PASS, Leak-Trend flach | `runbooks/evidence/` |
| S4 | Fork-Repro + Telemetrie + Vanilla-Build gruen | Fork-CI |
| S5 | volle Chaos-Matrix PASS auf Hardware | Game-Day-Report |
| S6 | Repro + Signatur + Canary + Auto-Rollback | `release.yml` Evidence |
| S7 | 30-Tage-Budgets gehalten | SLO-Dashboard-Export |
