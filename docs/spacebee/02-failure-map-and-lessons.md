# 02 — Failure Map & Lessons

Stand: 2026-06-10

Dieses Dokument kartiert, **wo** Beagle OS einfrieren/abstuerzen/driften kann,
welche **Fehlerklassen** sich wiederholen, und welche **systemische**
Gegenmassnahme die Klasse schliesst (nicht nur den Einzelfall).

## 1. Stabilitaetskarte der Flotte

| Schicht | Komponente | Sprache/Runtime | Primaere Stabilitaetsrisiken |
|---|---|---|---|
| Control-Plane | `beagle-host/services/stream_http_surface.py` (Broker `:9088`), `service_registry.py`, `async_job_queue.py` | Python-Daemon | Langlauf-Leaks, Job-Queue-Stau, State-Korruption, Request-Stampede |
| State | `core/persistence/`, SQLite `state.db` (WAL) | Python | Korruption bei Crash-waehrend-Write, Lock-Contention, Migrationsdrift |
| Web Console | `website/ui/*.js` | Browser-JS | Hung-Fetch ohne Timeout, fehlende Error-/Empty-States |
| Gast-Desktop | VM100 KDE Plasma + `beagle-stream-server` (Sunshine-Fork) | C++ | GPU-Encode-Crash, Session-Leak, Guardian-Restart-Flapping |
| Gast-Agenten | `beagle-host/bin/beagle-guest-updater`, `beagle-host/netbridge/*` | Python/Qt | UI-Thread-Blocking, Token-Leak im Fehlerpfad |
| Thin-Client | `beagle-stream-client` (Moonlight-Fork), `thin-client-assistant/runtime/*` | C++/Qt + Shell | RAM-Erschoepfung, Launcher-Reentry, WG-Fallback, Lock-FD-Vererbung |
| TC-Update | `beagle-os/overlay/usr/local/sbin/beagle-update-client` (A/B-Slots) | Python | **Download in volatilen RAM**, Medium-voll-Fallback, halbfertiger Slot-Switch |
| Image/Boot | `beagle-os/`, `server-installer/`, `build-iso.yml` | Bash/Build | Nicht-reproduzierbarer Build, Boot-Integritaet, Low-RAM-Boot |
| Netz/Policy | WireGuard `wg-beagle`, Enrollment | Shell | Stiller Public-Fallback, Tunnel-Flap, Split-DNS |

## 2. Wiederkehrende Fehlerklassen (die echten Gegner)

Jede Klasse hat bereits **mindestens einen** Live-Incident verursacht. SpaceBee
behandelt die Klasse als Ganzes.

### FK-1 — Unbeschraenkter Schreibzugriff auf volatilen Speicher
- **Symptom:** RAM-Erschoepfung → Freeze des gesamten (gestreamten) Desktops.
- **Beispiel:** `beagle-update-client` lud 906 MB OS-Payload in tmpfs-Overlay
  (TC ohne Swap), Disk-Space-Guard wurde uebersprungen, weil der Feed kein
  `payload_size` lieferte. Fix `40c3e632`.
- **Klassen-Gegenmassnahme:** zentraler Schreib-Guard
  `path_is_ram_backed()` + Budget-/Defer-Politik (siehe
  [04-resilience-and-selfheal.md](04-resilience-and-selfheal.md) §1). **Jeder**
  potenziell grosse Write (Update, Cache, Log, Coredump, tarball-extract) muss
  durch diesen Guard.

### FK-2 — Blockierende I/O im Event-/UI-Thread
- **Symptom:** UI/Panel/Menue haengt; bei DBus-Menues stallt der ganze
  Plasma-Shell.
- **Beispiel:** `beagle-netbridge-tray` rief Agent/CUPS synchron im Qt-GUI-Thread
  (`menu.aboutToShow`). Fix: Worker-Threads + Signals.
- **Klassen-Gegenmassnahme:** Regel "kein Netzwerk-/Subprozess-Call im
  UI-/Reactor-Thread"; alle externen Calls mit Timeout + auf Worker; CI-Lint, der
  blockierende Aufrufe in UI-Pfaden erkennt.

### FK-3 — Health-Checks ohne Hysterese
- **Symptom:** Guardian killt/restartet einen gesunden Dienst, weil eine
  Readiness-Probe einmal flackerte → Selbst-DoS.
- **Beispiel:** Stream-Server-Guardian-Restart bei Probe-Flapping (in STATUS.md
  als "recently closed" vermerkt).
- **Klassen-Gegenmassnahme:** alle Health-Gates mit N-aus-M-Hysterese, getrennten
  Zustaenden `starting`/`ready`/`degraded`/`dead`, und `StartLimitIntervalSec`
  gegen Restart-Sturm.

### FK-4 — Policy degradiert still statt fail-closed
- **Symptom:** Sicherheits-/Netzpfad weicht bei fehlender Konfig auf einen
  unsicheren Default aus.
- **Beispiel:** S-052 — Thin-Client fiel bei fehlender WG-Konfig auf
  Public-Stream-Host (`46.4.96.80:50000`) zurueck.
- **Klassen-Gegenmassnahme:** `vpn_required` und vergleichbare Policies sind
  fail-closed; jeder Fallback ist explizit erlaubt (env opt-in) und auditiert.

### FK-5 — Lifecycle ohne Idempotenz / Reentry-Schutz
- **Symptom:** Doppelt gestartete Launcher, vererbte Lock-FDs, verwaiste
  Sessions, "stale runtime state" nach Delete/Recreate.
- **Beispiel:** TC-Stream-Launcher-Reentry + Lock-FD-Vererbung (STATUS.md).
- **Klassen-Gegenmassnahme:** Single-Instance-Locks mit `flock` + `O_CLOEXEC`;
  idempotente Start/Stop-Transitions; definierte State-Machine je Session.

### FK-6 — Kapazitaet/Drift wird nicht vorab geprueft
- **Symptom:** Medium voll → Update kann nicht staging; Version/Artefakt-Drift
  zwischen `main`, CI, `srv1`, Public-Downloads.
- **Beispiel:** `/run/live/medium` zu 96 % voll; wiederkehrende Versionsdrift in
  Release-/Update-Pruefung (Risk-Register Massnahme 1+3).
- **Klassen-Gegenmassnahme:** Preflight-Kapazitaetschecks vor jedem Stage;
  Versionskohaerenz-Gate in CI (`VERSION` == Release-Asset == repo-status ==
  download-status).

### FK-7 — Ressourcenlecks im Langlauf
- **Symptom:** RSS/FD/Handle/Disk wachsen ueber Stunden bis zum Kollaps.
- **Beispiel:** noch unbewiesen abwesend — es gibt **kein** Soak-Gate. Das ist
  selbst das Risiko.
- **Klassen-Gegenmassnahme:** 72-h-Soak mit Leak-Trendpruefung (S3) als
  Pflicht-Gate vor jedem Release.

### FK-8 — Fork-Drift / Supply-Chain
- **Symptom:** Forks divergieren unkontrolliert von Upstream; CVE in Sunshine/
  Moonlight bleibt unbemerkt; Build nicht reproduzierbar.
- **Klassen-Gegenmassnahme:** siehe [03-stream-forks-hardening.md](03-stream-forks-hardening.md).

## 3. Bereits bezahlte Incidents (Lessons learned)

Diese Faelle sind die empirische Grundlage von SpaceBee. Sie sind gefixt; die
**Verallgemeinerung** ist die offene Arbeit.

| Datum | Incident | Sofortfix | Verallgemeinerung (SpaceBee) |
|---|---|---|---|
| 2026-06-10 | Live-TC-Freeze durch 906 MB Update-Download in RAM | `40c3e632` (RAM-Guard + Defer + `--max-filesize` + extract off tmpfs) | FK-1 global: zentraler Volatile-Write-Guard + INV-RAM |
| 2026-06-10 | Tray blockierte Plasma ueber DBus | Worker-Threads + Qt-Signals | FK-2: UI-Thread-Block-Lint + Timeout-Pflicht |
| 2026-05-xx | Stream-Guardian-Restart bei Probe-Flap | Guardian-Logik entschaerft | FK-3: Hysterese-Standard fuer alle Health-Gates |
| 2026-05-16 | S-052 Public-Stream-Fallback ohne WG | Launcher erzwingt WG bei `egress_type=wireguard` | FK-4: Fail-Closed-Policy-Standard |
| 2026-05-xx | TC-Launcher-Reentry + Lock-FD-Vererbung | Reentry-Guard + FD-Handling | FK-5: Idempotenz-/Lock-Standard |
| laufend | Versions-/Artefakt-Drift | Release-Workflow-Fix | FK-6: Versionskohaerenz-Gate |

## 4. Was fehlt, um die Klassen *systemisch* zu schliessen

Priorisiert (Detail-Tasks gehen in [checklists/](../checklists/), Reihenfolge in
[06-execution-waves.md](06-execution-waves.md)):

1. **Zentraler Volatile-Write-Guard als geteiltes Modul** statt nur im
   Update-Client (FK-1).
2. **systemd-Resource-Control + Watchdog** fuer jeden Langlauf-Dienst auf jedem
   Knoten (FK-1/FK-3/FK-7).
3. **UI-Thread-Block-Lint** + verpflichtende Timeouts an allen externen Calls
   (FK-2).
4. **Hysterese-Health-Library** fuer Guardians/Probes (FK-3).
5. **Fail-Closed-Audit** aller Policy-/Fallback-Pfade (FK-4).
6. **Idempotenz-/Single-Instance-Konvention** fuer alle Launcher/Lifecycle-Skripte
   (FK-5).
7. **Preflight-Kapazitaet + Versionskohaerenz-Gate** (FK-6).
8. **Soak-Harness mit Leak-Trend** (FK-7).
9. **Fork-Hardening-Programm** (FK-8, eigenes Dokument).
