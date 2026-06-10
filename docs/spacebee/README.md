# SpaceBee — Beagle OS Stability Program

Stand: 2026-06-10
Version-Bezug: `VERSION` = 8.3.15

SpaceBee ist das **Stabilitaets- und Reliability-Programm** fuer Beagle OS und
die beiden Streaming-Forks `beagle-stream-server` und `beagle-stream-client`.

Es ersetzt **nicht** den [Diamond Plan](../lasthope/05-diamond-plan.md). Der
Diamond Plan beantwortet *"Was muss bewiesen sein, damit wir verkaufen duerfen?"*
(Pilot-/Enterprise-Gates D0–D7). SpaceBee beantwortet die andere Haelfte:

> **"Was bedarf es, damit Beagle OS unter Last, ueber Wochen, auf echter
> Hardware und ueber alle Forks hinweg nicht mehr einfriert, abstuerzt,
> driftet oder still degradiert — nach absoluten High-Standards 2026?"**

SpaceBee ist die **Reliability-Overlay** ueber dem Diamond Plan: jede Diamond-
Phase wird erst dann als wirklich abgeschlossen betrachtet, wenn das zugehoerige
SpaceBee-Stabilitaets-Gate (S0–S7) gehalten wird.

## Warum dieses Programm jetzt

Die letzten Live-Incidents waren keine Feature-Luecken, sondern **Stabilitaets-
Klassen**, die sich wiederholen, weil es bisher kein systematisches
Reliability-Programm gab:

- **Live-TC-Freeze (2026-06-10):** `beagle-update-client` lud ein ~906 MB
  OS-Payload in den RAM-backed tmpfs-Overlay eines Live-Thin-Clients mit 3,3 GB
  RAM **ohne Swap** → MemAvailable fiel auf 428 MB → der gestreamte Desktop fror
  komplett ein. Fix committet (`40c3e632`), aber die **Klasse** "unbeschraenkter
  Schreibzugriff auf volatilen Speicher" war systemweit ungeschuetzt.
- **Tray blockierte den GUI-Thread** → DBus-Menue-Requests stalleten
  `plasmashell`. Klasse: "blockierende I/O im Event-/UI-Thread".
- **Stream-Guardian** startete einen gesunden Server neu, weil Readiness-Probes
  flackerten. Klasse: "Health-Checks ohne Hysterese".
- **Broker-Fallback** zielte bei fehlender WireGuard-Konfig auf den Public-Host.
  Klasse: "Policy-Pfad degradiert still statt fail-closed".
- **11 rote Unit-Tests** im Full-Suite-Lauf (vorbestehend, unabhaengig vom
  Freeze-Fix). Klasse: "kein Zero-Known-Defect-Gate".

SpaceBee schliesst nicht einzelne Bugs — es schliesst die **Fehlerklassen**.

## Aktive Struktur

| Datei | Rolle |
|---|---|
| [01-stability-charter.md](01-stability-charter.md) | Definition von "absolut stabil", SLO-Katalog, Error-Budgets, Stabilitaets-Gates S0–S7, Arbeitsregeln |
| [02-failure-map-and-lessons.md](02-failure-map-and-lessons.md) | Stabilitaetskarte der gesamten Flotte (inkl. Forks), wiederkehrende Fehlerklassen, bereits bezahlte Incidents, systemische Gegenmassnahmen |
| [03-stream-forks-hardening.md](03-stream-forks-hardening.md) | `beagle-stream-server` (Sunshine-Fork) und `beagle-stream-client` (Moonlight-Fork): Upstream-Tracking, reproduzierbare Builds, Crash-/QoE-Telemetrie, Resource-Caps, Soak |
| [04-resilience-and-selfheal.md](04-resilience-and-selfheal.md) | Resource-Governance, systemd-Watchdog/Restart-Policy, Concurrency-Disziplin, Fail-Closed, A/B-Update-Sicherheit + Auto-Rollback |
| [05-verification-soak-chaos.md](05-verification-soak-chaos.md) | Zero-Known-Defect-CI, Flaky-Quarantaene, Soak-/Chaos-/Fault-Injection-Matrix, Hardware-in-the-Loop, Release-Reproduzierbarkeit |
| [06-execution-waves.md](06-execution-waves.md) | Sequenzierung S-W0 … S-W7, Abnahmekriterien, No-Go-Regeln, Owner-Rollen, Mapping auf die Diamond-Phasen |

## Kanonische Regeln

1. Ein Stabilitaets-Gate ist **erst gruen, wenn der Nachweis reproduzierbar im
   Repo, in CI oder als Live-Evidence-Protokoll** liegt — nie durch Doku allein
   (gleiche Regel wie [Diamond Plan](../lasthope/05-diamond-plan.md)).
2. Jeder Live-Hotfix wird im selben Arbeitsblock ins Repo zurueckgefuehrt und
   bekommt einen Regressionstest fuer die **Fehlerklasse**, nicht nur den
   Einzelfall.
3. Ein gerissenes Error-Budget oder ein rotes S-Gate **blockiert Komfort-
   Features** — exakt wie ein rotes P0-Diamond-Gate.
4. Stabilitaet wird **gemessen, nicht behauptet**: jede Aussage "stabil" braucht
   eine SLO-Zahl, ein Soak-Protokoll oder ein Chaos-Ergebnis.
5. Neue offene Stabilitaetsaufgaben gehen in genau **eine** der bestehenden
   Checklisten ([checklists/](../checklists/)); SpaceBee-Dateien definieren nur
   Ziel, Gate und Reihenfolge — nicht das Backlog.

## Referenzflotte (Stabilitaets-Messpunkte)

| Knoten | Rolle | Stabilitaets-Risikoprofil |
|---|---|---|
| `srv1.beagle-os.com` | Control-Plane / Broker (`:9088`), libvirt-Host | Langlaeufer-Daemon, State-Store, Job-Queue |
| `beagle-100` / VM100 (`192.168.123.114`) | Gast-Desktop (KDE Plasma), `beagle-stream-server` | GPU-Encode, langer Session-Lifecycle |
| TC `192.168.178.30` | Live-Thin-Client, `beagle-stream-client` | RAM-constrained (3,3 GB, **kein Swap**), amdgpu, USB-Medium |

Diese drei Knoten sind die **Minimal-Referenzflotte**, gegen die alle SpaceBee-
SLOs, Soak-Laeufe und Chaos-Experimente gemessen werden, bevor ein S-Gate als
gehalten gilt.
