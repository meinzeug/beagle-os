# 06 — Execution Waves

Stand: 2026-06-10

Reihenfolge, in der SpaceBee abgearbeitet wird. Prinzip: **erst die Klasse, die
schon einmal eingefroren hat, dann Beobachtbarkeit, dann Beweis.** Detail-Tasks
leben in [checklists/](../checklists/); diese Wellen definieren nur Ziel, Gate,
Abnahme, No-Go und Owner-Rolle.

Mapping-Spickzettel: jede Welle haelt das gleichnamige Gate aus
[01-stability-charter.md](01-stability-charter.md) und schaltet die gekoppelte
Diamond-Phase frei.

---

## S-W0 — Freeze-Klassen schliessen + gruene Basis (Gate S0)

**Owner:** Reliability Lead
**Ziel:** Kein bekannter Freeze-Pfad, kein bekannter roter Test.

- [ ] Volatile-Write-Guard als geteiltes Modul (FK-1) — generalisiert aus
  `40c3e632`, in `core/` + Shell-Helfer, Pflichtdurchlauf fuer alle Grosswrites.
- [ ] systemd-Resource-Control + Watchdog-Drop-ins fuer **jeden** Langlauf-Dienst
  auf `srv1`, im Gast, auf dem TC (FK-1/FK-3/FK-7).
- [ ] Die 11 roten Tests fixen oder befristet quarantaenisieren; `tests.yml` auf
  hard-fail.
- [ ] Versionskohaerenz-Gate (FK-6) in CI.

**Abnahme:** S0-Kriterien gehalten; Full-Suite gruen; `systemctl --failed` = 0
auf allen drei Referenzknoten; ein kuenstlicher Grosswrite in tmpfs wird vom
Guard nachweislich deferred.
**No-Go:** Kein neues Stabilitaets-Feature, solange ein roter Test oder ein
ungeschuetzter Volatile-Grosswrite existiert.

---

## S-W1 — Observability vollstaendig (Gate S1)

**Owner:** Observability Engineer
**Ziel:** Jeder Freeze/Crash ist sichtbar, bevor ein Nutzer ihn meldet.

- [ ] PSI-/OOM-/MemAvailable-Metriken auf allen Knoten (INV-RAM/OOM/PSI).
- [ ] Crash-/Coredump-Capture (nicht-volatil, groessenbeschraenkt) + strukturierte
  `session.error`-Events aus beiden Forks (ohne Secrets).
- [ ] QoE-Telemetrie (FPS/Bitrate/Latenz/Drops/RTT/Reconnect) → Prometheus.
- [ ] SLO-Dashboards + Multi-Window-Burn-Rate-Alerting live.

**Abnahme:** Alle SLO-/INV-Messpunkte aus
[01-stability-charter.md](01-stability-charter.md) sind live ablesbar; ein
injizierter Crash erscheint binnen Sekunden im Dashboard.
**No-Go:** Kein S2+, solange ein Stabilitaetsereignis nur in `journalctl` und
nicht im Dashboard sichtbar ist. **Schaltet Diamond D1 frei (mit S0).**

---

## S-W2 — Selbstheilung beweisen (Gate S2)

**Owner:** Platform Engineer
**Ziel:** Erwartbare Fehler heilen ohne Mensch.

- [ ] Hysterese-Health-Library + idempotente Recovery je Dienst (FK-3/FK-5).
- [ ] Fail-Closed-Audit aller Policy-/Fallback-Pfade (FK-4).
- [ ] Update-Auto-Rollback (health-gated A/B) auf TC + Gast (FK-1/FK-6).
- [ ] CX-KILL / CX-MEM / CX-NET als wiederholbare Drills.

**Abnahme:** Jeder kritische Daemon ueberlebt `kill -9`; TC ueberlebt
Memory-Pressure-Injection ohne Freeze; ein injiziertes Bad-Update rollt
automatisch zurueck.
**No-Go:** Kein Produktpfad-Claim (Diamond D2), solange ein Daemon-Kill oder ein
WG-Flap manuellen Eingriff braucht. **Schaltet Diamond D2 frei (mit S4).**

---

## S-W3 — Soak beweisen (Gate S3)

**Owner:** Streaming Engineer
**Ziel:** Stabil ueber Tage, kein Leck.

- [ ] SOAK-SESS (72 h), SOAK-RECON, SOAK-LOWRAM, SOAK-API, SOAK-UPD ausfuehren.
- [ ] Leak-Trend-Auswertung (RSS/FD/Disk flach) als Gate.

**Abnahme:** Alle SOAK-* PASS mit Protokoll unter `runbooks/evidence/`;
Leak-Trend-Steigung nicht signifikant > 0.
**No-Go:** Kein bezahlter Pilot (Diamond D4), solange kein 72-h-Soak ohne
Degradation vorliegt.

---

## S-W4 — Forks haerten (Gate S4)

**Owner:** Streaming Engineer + Release Engineer
**Ziel:** `beagle-stream-server` und `beagle-stream-client` sind stabil,
wartbar, beweisbar — Details in
[03-stream-forks-hardening.md](03-stream-forks-hardening.md).

- [ ] Upstream gepinnt, Rebase-Kadenz + CVE-Watch aktiv (FK-8).
- [ ] Reproduzierbare, signierte Fork-Builds + SBOM.
- [ ] Fork-CI (vanilla + `BEAGLE_INTEGRATION`, ASan/UBSan auf Beagle-Diff,
  Contract-Test gegen Control-Plane).
- [ ] Crash-/QoE-Telemetrie aus beiden Forks (verzahnt mit S1).
- [ ] Fork-Soak (72 h) + Reconnect-Soak.

**Abnahme:** S4-Akzeption aus
[03-stream-forks-hardening.md](03-stream-forks-hardening.md) §9 erfuellt.
**No-Go:** Kein "BeagleStream erledigt", solange der Vanilla-Build rot ist oder
der letzte Upstream-Rebase > 30 Tage zurueckliegt. **Schaltet Diamond D2 frei
(mit S2).**

---

## S-W5 — Chaos auf Hardware (Gate S5)

**Owner:** Reliability Lead + Hardware Owner
**Ziel:** Stabil unter realer Stoerung.

- [ ] Volle Chaos-Matrix (CX-*) auf echter Hardware inkl. CX-GPU, CX-POWER,
  CX-REBOOT, CX-CLOCK.
- [ ] Hardware-in-the-Loop: GPU-Streaming-Messwerte, VFIO-Reboot-Proof,
  Cold-Boot aus frischem Payload.
- [ ] Game-Day-Kadenz etabliert; Ergebnisse → Incident-Runbook.

**Abnahme:** Jedes CX-Experiment recovered innerhalb SLO ohne Live-Eingriff.
**No-Go:** Kein Hardware-/GPU-Versprechen (Diamond D6), solange CX-GPU oder
CX-POWER nicht bestanden ist. **Schaltet Diamond D4/D6 frei (mit S3).**

---

## S-W6 — Release-/Rollback-Sicherheit im Flottenmasstab (Gate S6)

**Owner:** Release Engineer
**Ziel:** Updates koennen die Stabilitaet nicht brechen.

- [ ] Canary/Staged-Rollout ueber die Referenzflotte.
- [ ] Automatischer Rollback bei Health-Fail im Rollout.
- [ ] No-Regression-Gate: Release blockiert bei rotem S-Gate / gerissenem Budget.
- [ ] Repro + Signatur + SBOM durchgehend (Haupt + Forks).

**Abnahme:** Ein injizierter Bad-Release wird vom Canary gestoppt und rollt
automatisch zurueck, bevor die Breite betroffen ist.
**No-Go:** Kein Breitenrollout ohne bestandenen Canary. **Schaltet Diamond D3
frei (mit S2).**

---

## S-W7 — Stability-Sign-off (Gate S7)

**Owner:** Reliability Lead
**Ziel:** "Absolut stabil" mit Evidence deklarieren.

- [ ] 30 Tage alle SLOs + INV-Invarianten auf der Referenzflotte gehalten.
- [ ] Mindestens ein unangekuendigter Chaos-Drill und ein voller
  Update+Rollback-Zyklus im Fenster ohne Live-Eingriff bestanden.
- [ ] Incident-Runbooks geuebt; Error-Budget-Politik gelebt.

**Abnahme:** Stability-Durchbruchskriterium aus
[01-stability-charter.md](01-stability-charter.md) §5 erfuellt und im Repo
belegt.
**No-Go:** Keine "absolut stabil"-Aussage nach aussen, solange ein S-Gate rot
ist. **Schaltet Diamond D7 frei.**

---

## Sequenz-Ueberblick

```
S-W0  Freeze-Klassen + gruene Basis     ── Gate S0 ─┐
S-W1  Observability                     ── Gate S1 ─┼─► Diamond D1
S-W2  Selbstheilung                     ── Gate S2 ─┐
S-W4  Forks haerten                     ── Gate S4 ─┴─► Diamond D2
S-W3  Soak                              ── Gate S3 ─┐
S-W5  Chaos auf Hardware                ── Gate S5 ─┴─► Diamond D4/D6
S-W6  Release/Rollback (Canary)         ── Gate S6 ───► Diamond D3
S-W7  Stability-Sign-off                ── Gate S7 ───► Diamond D7
```

## Owner-Rollen (Kurzlegende)

| Rolle | Verantwortung in SpaceBee |
|---|---|
| Reliability Lead | Gesamtprogramm, S-Gates, Chaos, Sign-off |
| Observability Engineer | Metriken, Dashboards, Alerting, Telemetrie |
| Platform Engineer | systemd-Resource-Control, Watchdog, Self-Heal, State |
| Streaming Engineer | Forks, QoE, Soak, Reconnect |
| Release Engineer | Repro-Build, Signatur, Canary, Auto-Rollback |
| Hardware Owner | GPU/VFIO/Cold-Boot/Power-Drills |

> Rollen sind Funktionen, keine Personen — im aktuellen Setup koennen sie
> gebuendelt sein. Wichtig ist, dass pro Welle **ein** verantwortlicher
> Gate-Halter benannt ist.
