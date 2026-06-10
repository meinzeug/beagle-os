# 01 — Stability Charter

Stand: 2026-06-10

Dieses Dokument definiert verbindlich, was "absolut stabil nach High-Standards
2026" fuer Beagle OS bedeutet, wie es gemessen wird und welche Gates passiert
sein muessen.

## 1. Definition: Wann ist Beagle OS "absolut stabil"?

Beagle OS gilt als absolut stabil, wenn **alle** folgenden Aussagen gleichzeitig
und reproduzierbar wahr sind:

1. **Kein Single-Point-Freeze.** Kein einzelner Dienst, kein Update, kein
   Ressourcenengpass und kein Endgeraet kann den gestreamten Desktop oder die
   Control-Plane einfrieren. Jede kritische Komponente hat ein definiertes
   Verhalten unter Druck (degrade, defer, fail-closed) statt Stillstand.
2. **Selbstheilung vor Mensch.** Jeder erwartbare Fehler (Crash, OOM, Netz-
   Partition, Medium voll, GPU-Reset, Stromausfall am TC) wird automatisch
   erkannt und recovered, bevor ein Operator per SSH eingreifen muss.
3. **Stabil ueber Zeit, nicht nur im Moment.** Ein 72-Stunden-Soak einer echten
   Stream-Session bleibt innerhalb aller QoE-SLOs, ohne Ressourcenleck
   (RSS/FD/Handles/Disk stabil).
4. **Stabil ueber Updates.** Ein Update kann die Verfuegbarkeit nie unter SLO
   druecken; fehlgeschlagene Updates rollen automatisch zurueck.
5. **Stabil ueber alle Forks.** `beagle-stream-server` und
   `beagle-stream-client` bauen reproduzierbar, tracken Upstream kontrolliert,
   liefern Crash-/QoE-Telemetrie und halten die gleichen SLOs wie der
   Python-Stack.
6. **Stabil sichtbar.** Jede SLO ist live in einem Dashboard messbar; ein
   Error-Budget-Burn loest Alarm aus, bevor ein Nutzer es meldet.
7. **Zero-Known-Defect.** Es gibt keinen bekannten roten Test, keinen
   bekannten Freeze-Pfad und keinen akzeptierten Stabilitaets-Workaround ohne
   Eintrag mit Risiko und naechstem Schritt.

> Solange auch nur eine dieser Aussagen nur "meistens" gilt, ist Beagle OS
> *robust*, aber nicht *absolut stabil*. SpaceBee schliesst die Luecke zwischen
> "laeuft bei uns" und "laeuft ueberall, immer, ohne uns".

## 2. SLO-Katalog (Service Level Objectives)

SLOs werden auf der Referenzflotte (siehe [README](README.md)) ueber ein
rollierendes 30-Tage-Fenster gemessen. Die Zahlen sind die **Ziel-Ratifizierung**
fuer S0; Abweichungen werden in [06-execution-waves.md](06-execution-waves.md)
nachgezogen, nicht stillschweigend gesenkt.

### 2.1 User-Journey-SLOs

| ID | Journey | SLI | Ziel (SLO) |
|---|---|---|---|
| SLO-BOOT | TC Cold-Boot → BeagleStream-Desktop sichtbar | Erfolgsrate / Latenz | >= 99,5 % Erfolg, p95 <= 90 s |
| SLO-SESS | Gestartete Stream-Session bleibt nutzbar | Ungeplante Abbrueche / Session | <= 0,5 % Drop-Rate |
| SLO-RECON | Reconnect nach transientem Netzfehler | Zeit bis Bild zurueck | p95 <= 10 s, kein manueller Eingriff |
| SLO-QOE-LAT | End-to-End-Input-Latenz (LAN/WG-direct) | p95 | <= 50 ms direct, <= 80 ms tunneled |
| SLO-QOE-FRM | Frame-Drop-Rate im Stream | gedroppte / gesendete Frames | <= 1 % |
| SLO-API | Control-Plane `/api/v1/streams/*` | Verfuegbarkeit / p99-Latenz | >= 99,9 % / p99 <= 300 ms |
| SLO-UPD | Update (A/B-TC + Guest + Host) | Erfolg mit Auto-Rollback bei Health-Fail | >= 99 % Erfolg, 0 Verfuegbarkeitsverlust > SLO |

### 2.2 Resource-Safety-SLOs (Invarianten)

Diese sind **harte Invarianten**, kein Mittelwert — jede Verletzung ist ein
Incident.

| ID | Invariante | Schwelle |
|---|---|---|
| INV-RAM | TC MemAvailable im Normalbetrieb | nie < 256 MB; **nie** unbeschraenkter Write in RAM-backed FS |
| INV-OOM | OOM-Kill eines kritischen Prozesses | 0 |
| INV-PSI | Memory-Pressure-Stall (PSI `some avg10`) | < 10 % anhaltend |
| INV-FD | File-Descriptor-/Handle-Wachstum im Langlauf | flach ueber 72 h Soak |
| INV-DISK | Persistenz-Medium / State-Volume | nie ueber 90 % ohne Defer/Alarm |
| INV-CRASH | Crash-free Session-Rate (beide Forks) | >= 99,9 %; jeder Crash erzeugt Coredump + Telemetrie |

### 2.3 Error-Budgets

Jede SLO hat ein Budget = `100 % − SLO`. Beispiel: SLO-BOOT 99,5 % → 0,5 %
Budget pro 30 Tage. Regeln:

- **Multi-Window-Burn-Alarm:** schneller Burn (1 h) UND langsamer Burn (6 h)
  ueber Schwelle → Page; nur langsamer Burn → Ticket.
- **Budget aufgebraucht → Feature-Freeze** der betroffenen Komponente, bis das
  Budget regeneriert ist (analog rotes P0-Gate im Diamond Plan).
- **Invarianten haben kein Budget:** INV-* sind 0-Toleranz; eine Verletzung
  oeffnet sofort einen Incident nach [runbooks/incident-response.md](../runbooks/incident-response.md).

## 3. Stabilitaets-Gates S0–S7

Analog zu den Diamond-Gates D0–D7. Ein S-Gate ist erst gruen, wenn sein
Nachweis reproduzierbar vorliegt.

| Gate | Bedeutung | Muss gehalten sein |
|---|---|---|
| **S0** | Gruene Basis | 0 bekannte rote Tests; Version/Artefakt kohaerent; jeder kritische Daemon hat Watchdog + Restart-Policy + Resource-Cap; **kein unbeschraenkter Write in volatilen Speicher** (Freeze-Klasse global geschlossen) |
| **S1** | Observability vollstaendig | jeder Knoten liefert strukturierte Logs + Metrics + Crash/Coredump-Capture + PSI/OOM-Events; SLO-Dashboards live; Burn-Rate-Alerting aktiv |
| **S2** | Selbstheilung bewiesen | Kill-and-Recover jedes Daemons; TC ueberlebt Memory-Pressure-Injection; WG-Flap recovered; Update-Auto-Rollback bewiesen |
| **S3** | Soak bewiesen | 24 h/72 h Stream-Soak innerhalb QoE-SLO; kein Ressourcenleck; Medium-voll- und Low-RAM-Soak bestanden |
| **S4** | Forks gehaertet | reproduzierbare Fork-Builds; gepinntes Upstream + CVE-Watch; Crash-/QoE-Telemetrie aus beiden Forks; `BEAGLE_INTEGRATION`-Patches minimal, nicht-fatal, getestet; Fork-CI gruen |
| **S5** | Chaos bestanden | Netz-Partition, Host-Reboot, amdgpu-Reset, TC-Stromausfall, Disk-Full, Clock-Skew, unterbrochenes Update — alle recovern innerhalb SLO |
| **S6** | Release-/Rollback-Sicherheit | Canary/Staged-Rollout; automatischer Rollback; No-Regression-Gate; signiert + SBOM + reproduzierbar (an `release.yml` angebunden) |
| **S7** | Stability-Sign-off | 30-Tage-Error-Budgets auf Referenzflotte gehalten; Incident-Runbooks geuebt; "absolut stabil" mit Evidence deklariert |

### Gate-Kopplung an den Diamond Plan

| Diamond | SpaceBee-Vorbedingung |
|---|---|
| D1 (Single-Host-Pilot) | S0 + S1 |
| D2 (BeagleStream-Produktpfad) | S2 + S4 |
| D3 (Backup/Update-Vertrauen) | S2 (Auto-Rollback) + S6 |
| D4 (Zwei-Host-Pilot) | S3 + S5 |
| D5 (Security/Compliance) | S1 (kein Secret-Leak in Telemetrie) + S5 |
| D6 (Hardware/GPU) | S5 (GPU-Reset) + S3 (GPU-Soak) |
| D7 (Launch) | S7 |

Lies: **Kein Diamond-Gate gilt als bestanden, solange sein gekoppeltes
SpaceBee-Gate rot ist.**

## 4. Arbeitsregeln bis Absolut-Stabil

1. Jede abgeschlossene S-Phase erzeugt einen reproduzierbaren Nachweis (Repo,
   CI-Run, Soak-Protokoll, Chaos-Report).
2. Jeder Live-Hotfix wird im selben Arbeitsblock ins Repo zurueckgefuehrt **und**
   erhaelt einen Regressionstest, der die *Fehlerklasse* abdeckt
   (Beispiel: nicht "Payload X zu gross", sondern "kein Download in RAM-backed
   FS").
3. Mock-/Unit-Tests zaehlen als Vorbereitung; Gates mit Runtime-/Hardware-Bezug
   brauchen Live-Nachweise auf der Referenzflotte.
4. Ein rotes S-Gate oder ein gerissenes Error-Budget blockiert Komfort-Features.
5. Stabilitaetsfunde werden sofort gefixt oder in
   [refactor/04-risk-register.md](../refactor/04-risk-register.md) mit Risiko und
   naechstem Schritt dokumentiert.
6. Kein Pfad gilt als stabil, solange sein Fehlerfall, sein Recovery-Pfad und
   sein Rueckweg nicht dokumentiert und mindestens einmal ausgeloest wurden.

## 5. Stability-Durchbruchskriterium

Absolut stabil ist erreicht, wenn die Referenzflotte (`srv1` + VM100 + TC) ueber
**30 zusammenhaengende Tage** alle SLOs und alle INV-Invarianten haelt, dabei
mindestens einen unangekuendigten Chaos-Drill (S5) und einen vollstaendigen
Update-mit-Rollback-Zyklus (S6) ohne menschlichen Live-Eingriff uebersteht — und
jeder dieser Nachweise reproduzierbar im Repo und in den Runbooks liegt.
