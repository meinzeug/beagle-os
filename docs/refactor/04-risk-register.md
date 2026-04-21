# Beagle OS Refactor - Risk Register

Stand: 2026-04-13

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
