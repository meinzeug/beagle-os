# Beagle OS Refactor - Risk Register

Stand: 2026-04-13

## BEA-9 - Top-Risiken und 2-Wochen-Umsetzungsplan (Stand: 2026-05-10)

Prioritaetslogik: erst Build-/Release-Reproduzierbarkeit (blockiert jede sichere Auslieferung), dann Security-Baseline (blockiert Freigabe), danach Runtime-/Repo-Drift und erst danach mittelfristige Architekturdrifts.

### Massnahme 1 (Prioritaet P1) - Reproduzierbarer Release-Build
- Zielrisiko: R7 (Ueberdehnung der Roadmap) + sichtbare Build-Reproduzierbarkeits-Drift
- Owner-Rolle: Release Engineer
- Erwartetes Ergebnis: Ein reproduzierbarer Release-Lauf erzeugt identische Versions-/Artefaktmetadaten fuer `VERSION`, Release-Assets und Host-Update-Status.
- Done-Kriterium: Zwei aufeinanderfolgende Runs auf gleichem Commit liefern gleiche Artefakt-Checksummen und keinen Versionsdrift-Fehler in Release-/Update-Pruefung.

### Massnahme 2 (Prioritaet P2) - Security-Baseline ohne Secret-Leaks
- Zielrisiko: R6 + R8
- Owner-Rolle: Security Engineer
- Erwartetes Ergebnis: Secret-Pfade und Auth-Defaults sind auf deny-by-default gehaertet, und neue Klartext-Secrets werden im Repo-Delta vor Merge erkannt.
- Done-Kriterium: Secret-Scan auf dem aktuellen Hauptpfad ist ohne neue Findings; dokumentierte Rest-Risiken stehen in `docs/refactor/11-security-findings.md`.

### Massnahme 3 (Prioritaet P3) - Runtime/Repo-Drift auf `srv1` und `srv2` schliessen
- Zielrisiko: inkonsistenter Repo-Stand zwischen Laufzeit und Git-Stand
- Owner-Rolle: Platform Engineer
- Erwartetes Ergebnis: Beide Referenzhosts melden denselben Commit-/Versionsstand wie `main` und keinen offenen Auto-Update-Drift.
- Done-Kriterium: Host-Checks (`check-beagle-host` + Repo-Update-Status) sind auf beiden Hosts gruen und zeigen identischen Commit/Version.

### Massnahme 4 (Prioritaet P4) - Stream/Thinclient E2E-Abnahme stabilisieren
- Zielrisiko: R3 + R5
- Owner-Rolle: Streaming Engineer
- Erwartetes Ergebnis: Der produktive Thinclient-Pfad (Boot -> Broker-Allocate -> WireGuard -> Desktop) ist reproduzierbar und ohne manuelle Hotfixes nachweisbar.
- Done-Kriterium: Ein kompletter E2E-Smoke auf frischem Thinclient-Artefakt ist PASS und im Progress-Log mit Host/Datum dokumentiert.

### Massnahme 5 (Prioritaet P5) - Provider- und API-Drift aktiv begrenzen
- Zielrisiko: R4 + R5
- Owner-Rolle: Backend Engineer
- Erwartetes Ergebnis: Neue Backend-Aenderungen laufen nur ueber Beagle-Provider-/Contract-Grenzen; UI/API-Drift wird frueh durch Vertrags-/Smoke-Tests erkannt.
- Done-Kriterium: Kein neuer Proxmox-spezifischer Zugriff im Delta und mindestens ein erfolgreicher Contract-/Smoke-Test fuer geaenderte API-Surfaces im Merge-Nachweis.

## R1 - Auth Migration Bricht Bestehende Flows
- Risiko: Hoch
- Wahrscheinlichkeit: Mittel
- Mitigation:
  - Dual-stack Uebergang (session + legacy token fuer automation)
  - Feature flag fuer neue Loginpflicht
  - Contract tests fuer alte und neue auth paths

## R2 - RBAC Luecken bei Mutierenden APIs
- Risiko: Hoch
- Wahrscheinlichkeit: Mittel
- Mitigation:
  - zentrale permission matrix
  - deny-by-default
  - audit event bei jeder denied/allowed mutation

## R3 - Streaming-Orchestrierung wird inkonsistent
- Risiko: Hoch
- Wahrscheinlichkeit: Mittel
- Mitigation:
  - state machine mit definierten transitions
  - idempotente actions
  - retry/backoff + dead-letter queue

## R4 - Provider-Neutralitaet wird unter Zeitdruck unterlaufen
- Risiko: Hoch
- Wahrscheinlichkeit: Mittel
- Mitigation:
  - alle neuen compute/storage/network features nur ueber contracts
  - architecture checks in review checklist
  - provider-specific code nur unter providers/

## R5 - UI/Backend Drift
- Risiko: Mittel
- Wahrscheinlichkeit: Mittel
- Mitigation:
  - typed API response contracts
  - smoke e2e flows je release
  - changelog fuer API surface

## R6 - Sicherheitstechnische Schulden
- Risiko: Hoch
- Wahrscheinlichkeit: Mittel
- Mitigation:
  - password hashing policy (argon2id/bcrypt policy)
  - session rotation und revocation
  - secret-at-rest policy

## R7 - Ueberdehnung der Roadmap
- Risiko: Mittel
- Wahrscheinlichkeit: Hoch
- Mitigation:
  - Tier-1 capabilities zuerst
  - klare Wellenabnahmen
  - harte non-goals pro Welle

## R8 - Lokale Operator-Dateien oder Secrets werden versehentlich versioniert
- Risiko: Hoch
- Wahrscheinlichkeit: Mittel
- Mitigation:
  - `AGENTS.md` und `AGENTS.md` lokal-only halten und in `.gitignore` erzwingen
  - Security-Funde pro Run in `docs/refactor/11-security-findings.md` dokumentieren
  - keine Klartext-Secrets in versionierten Docs, Defaults oder Scripts zulassen
