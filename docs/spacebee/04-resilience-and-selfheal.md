# 04 — Resilience & Self-Heal

Stand: 2026-06-10

Dieses Dokument definiert die technischen Standards, mit denen die Fehlerklassen
aus [02-failure-map-and-lessons.md](02-failure-map-and-lessons.md) systemisch
geschlossen werden. Es ist die **Ingenieurs-Norm** hinter den S-Gates.

## 1. Resource-Governance (schliesst FK-1, INV-RAM/OOM/PSI/DISK)

### 1.1 Zentraler Volatile-Write-Guard

Der im Update-Client (`40c3e632`) eingefuehrte Schutz wird zu einem **geteilten,
wiederverwendbaren Baustein** erhoben.

- [ ] Gemeinsame Helfer (Python `core/` + Shell-Aequivalent fuer Runtime-Skripte):
  - `path_is_ram_backed(path)` — folgt Overlay-`upperdir` rekursiv, erkennt
    tmpfs/ramfs.
  - `mem_available_bytes()` — `/proc/meminfo MemAvailable`.
  - `guard_volatile_write(path, required_bytes, reserve)` — defert/abbricht, wenn
    Ziel RAM-backed und Budget unzureichend; opt-in-Override nur per Env.
- [ ] **Pflichtdurchlauf:** jeder potenziell grosse Write (Update-Payload, Cache,
  tarball-extract, Coredump, Log-Rotation-Ziel, Backup-Staging) ruft den Guard.
  CI-Check (grep-basiert) verhindert neue ungeschuetzte Grosswrites in
  Runtime-Pfaden.
- [ ] **Generalisierter `--max-filesize`/Quota-Ansatz** fuer alle Downloads
  (curl/requests) auf RAM-constrained Knoten.

### 1.2 systemd-Resource-Control fuer jeden Langlauf-Dienst

Auf `srv1`, im Gast und auf dem TC bekommt jeder Beagle-Daemon eine Drop-in mit:

- [ ] `MemoryHigh=` (weicher Druck) + `MemoryMax=` (harte Grenze, kontrollierter
  OOM **innerhalb** der Unit statt globalem Freeze).
- [ ] `TasksMax=`, `LimitNOFILE=` sinnvoll begrenzt.
- [ ] `OOMScoreAdjust=` nach Wichtigkeit: Stream-Kern und Control-Plane
  geschuetzter, Best-Effort-Jobs (Update, Backup-Staging) zuerst opferbar.
- [ ] **PSI-Ueberwachung** (`/proc/pressure/memory`) als Metrik + Alarm
  (INV-PSI).

### 1.3 Swap/Zram-Sicherheitsnetz auf dem TC

- [ ] **zram** als komprimierter Notfall-Swap auf dem No-Swap-Live-TC evaluieren
  und (falls stabil) aktivieren — verwandelt einen harten Freeze in eine
  kontrollierte Verlangsamung. Kein Ersatz fuer FK-1-Guard, sondern zweite
  Verteidigungslinie.

## 2. Self-Heal & Watchdogs (schliesst FK-3, S2)

### 2.1 Watchdog-Standard

- [ ] Jeder kritische Daemon implementiert `sd_notify` `WATCHDOG=1`;
  Unit setzt `WatchdogSec=` + `Restart=on-watchdog`. Ein haengender (nicht nur
  abgestuerzter) Prozess wird so erkannt — genau der Freeze-Fall.
- [ ] `Restart=on-failure` + `RestartSec=` + `StartLimitIntervalSec=` /
  `StartLimitBurst=` ueberall, gegen Restart-Sturm.

### 2.2 Hysterese-Health-Library

- [ ] Gemeinsame Health-Gate-Logik mit Zustaenden
  `starting → ready → degraded → dead` und N-aus-M-Hysterese. Guardians duerfen
  **nie** auf einen einzelnen Probe-Flap hin neu starten (FK-3).
- [ ] Getrennte Liveness- vs. Readiness-Semantik; "noch am Starten" ist kein
  "tot".

### 2.3 Recovery-Choreografie

- [ ] Definierte, idempotente Recovery-Schritte je Dienst (kein impliziter
  Zustand). Recovery-Aktionen sind in [runbooks/](../runbooks/) referenziert und
  per Chaos-Drill (S5) ausgeloest.

## 3. Concurrency-Disziplin (schliesst FK-2)

- [ ] **Harte Regel:** kein Netzwerk-/Subprozess-/Datei-Call im UI- oder
  Reactor-Thread. UI-Code (Tray, Web, Qt) dispatcht auf Worker + Signal/Callback
  (wie im Tray-Fix umgesetzt).
- [ ] **Timeouts ueberall:** jeder externe Call (HTTP, Subprozess, Socket) hat
  einen expliziten Timeout. Kein unbegrenztes `wait`/`read`.
- [ ] **Bounded Queues:** Job-/Event-Queues haben Obergrenzen + Backpressure
  statt unbegrenztem Wachstum (FK-7-Schutz fuer `async_job_queue`).
- [ ] **CI-Lint:** Heuristik-Check, der synchrone blockierende Calls in
  bekannten UI-/Reactor-Pfaden meldet.

## 4. Fail-Closed-Standard (schliesst FK-4)

- [ ] Jeder Policy-/Fallback-Pfad ist **fail-closed**: fehlt die sichere
  Voraussetzung (z. B. WireGuard bei `vpn_required`), wird der Vorgang mit klarer
  Meldung abgebrochen, **nicht** auf einen unsicheren Default umgeleitet.
- [ ] Jeder bewusst erlaubte Fallback ist **explizit opt-in per Env** und erzeugt
  ein Audit-Event.
- [ ] **Fail-Closed-Audit:** einmaliger Durchgang durch alle `||`-Fallbacks,
  `try/except`-Defaults und Connect-Host-Auswahlen im Runtime-Pfad; Findings in
  [refactor/11-security-findings.md](../refactor/11-security-findings.md).

## 5. Idempotenz & Single-Instance (schliesst FK-5)

- [ ] **Single-Instance-Locks** mit `flock` und `O_CLOEXEC`, damit Locks nicht an
  Kindprozesse vererbt werden (genau der TC-Launcher-Bug).
- [ ] **Idempotente Start/Stop**: erneuter Start erkennt laufende Instanz und
  no-op't; Stop raeumt Sessions/FDs deterministisch auf.
- [ ] **Definierte Session-State-Machine** mit erlaubten Transitions; kein
  "stale runtime state" nach Delete/Recreate (Bezug Diamond D1).

## 6. Update- & Rollback-Sicherheit (schliesst FK-1/FK-6, S2/S6)

Beagle OS hat drei Update-Pfade: TC-A/B (`beagle-update-client`),
Gast (`beagle-guest-updater`), Host (repo-auto-update auf `srv1`). Alle drei
bekommen denselben Sicherheitsrahmen:

- [ ] **Preflight:** Kapazitaets- + Volatile-Write-Guard (FK-1/FK-6) **vor** dem
  Download; Medium-/Disk-Voll wird deferred und gemeldet, nie erzwungen.
- [ ] **Atomarer A/B-Switch:** Payload wird in den inaktiven Slot gestaged,
  verifiziert (SHA + Signatur), dann atomar aktiv geschaltet. Kein Halb-Zustand.
- [ ] **Health-gated Boot + Auto-Rollback:** nach dem Switch entscheidet ein
  Post-Switch-Healthcheck (Boot-Counter / `ready`-Probe). Schlaegt er fehl →
  automatischer Rollback auf den vorherigen Slot, Event ins Audit.
- [ ] **Kein Verfuegbarkeitsverlust > SLO** waehrend Update (SLO-UPD); Stream-
  Sessions werden kontrolliert drained, nicht hart abgeschnitten.
- [ ] **Signatur-Pflicht:** Slot akzeptiert nur signierte, SBOM-begleitete
  Artefakte (Bezug S6 + Fork-Signatur §3 in
  [03-stream-forks-hardening.md](03-stream-forks-hardening.md)).

## 7. Kapazitaet & Drift-Preflight (schliesst FK-6)

- [ ] **Versionskohaerenz-Gate** in CI: `VERSION` == Release-Asset ==
  `repo-auto-update-status.json` == `beagle-downloads-status.json`. Drift ist ein
  Build-Fehler (Bezug Validation-Matrix E0, Risk-Register Massnahme 1).
- [ ] **Medium-/State-Volume-Preflight** vor jedem Stage-/Backup-Vorgang;
  Schwelle INV-DISK (90 %) loest Defer + Alarm aus, nicht Stillstand.

## 8. Datenintegritaet unter Crash (State)

- [ ] SQLite `state.db`: WAL + `synchronous=NORMAL/FULL` bewusst gewaehlt;
  Crash-waehrend-Write-Test (kill -9 mitten im Commit) beweist Konsistenz nach
  Neustart.
- [ ] `core/persistence/` write-temp+fsync+rename bleibt der einzige Schreibpfad
  fuer JSON-State; kein In-Place-Write.
- [ ] Migrationsskripte sind idempotent und erzeugen vor Lauf ein Backup
  (`scripts/migrate-json-to-sqlite.py`-Muster).
