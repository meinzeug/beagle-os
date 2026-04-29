# Beagle OS — GoAdvanced Plan

> Kanonische Gesamtübersicht: [`docs/MASTER-PLAN.md`](../MASTER-PLAN.md). Bei Widerspruch gilt der Master-Plan.

**Stand**: 2026-04-25
**Vorgaenger**: `docs/gofuture/` (20 Plaene), `docs/goenterprise/` (10 Plaene)
**Status**: Naechste Ausbaustufe nach GoFuture + GoEnterprise

## Ziel

GoAdvanced behebt **strukturelle Schwaechen**, **Security-Luecken** und **Skalierungs-Bremsen**, die bei der Audit-Analyse vom 2026-04-25 gefunden wurden. Es ergaenzt — nicht ersetzt — die Featurearbeit von GoFuture/GoEnterprise.

Der Fokus liegt auf:

1. **Datenintegritaet**: Atomic Writes, Locking, SQLite-Migration
2. **Security-Haerte**: TLS, Secret-Rotation, Subprocess-Sandboxing, Rate-Limits
3. **Testbarkeit**: Service-Basisklassen, Integration-Tests, CI-Pipelines
4. **Skalierung**: Async-Jobs, Caching, JSON→SQLite
5. **Code-Qualitaet**: Monolithen-Aufspaltung, Beagle host-Endbeseitigung
6. **Beobachtbarkeit**: Prometheus-Metriken, strukturierte Logs, DR-Runbook
7. **UX & Accessibility**: i18n, ARIA, mobile

## Plan-Uebersicht (12 Plaene)

| # | Datei | Thema | Dringlichkeit |
|---|-------|-------|---------------|
| 01 | [01-data-integrity.md](01-data-integrity.md) | Atomic JSON-Writes + File-Locking + State-Base-Class | **HIGH** |
| 02 | [02-tls-hardening.md](02-tls-hardening.md) | `curl -k` entfernen, Cert-Pinning ueberall | **HIGH** |
| 03 | [03-secret-management.md](03-secret-management.md) | Secret-Rotation, Vault-Integration, Audit | **HIGH** |
| 04 | [04-subprocess-sandboxing.md](04-subprocess-sandboxing.md) | `run_cmd_safe()`, Argument-Validation, Timeouts | MEDIUM |
| 05 | [05-control-plane-split.md](05-control-plane-split.md) | `beagle-control-plane.py` (6000+ LOC) aufspalten | **HIGH** |
| 06 | [06-state-sqlite-migration.md](06-state-sqlite-migration.md) | JSON-State-Files → SQLite-Backend | MEDIUM |
| 07 | [07-async-job-queue.md](07-async-job-queue.md) | Async-Job-Queue fuer VM-Operationen | MEDIUM |
| 08 | [08-observability.md](08-observability.md) | Prometheus `/metrics`, strukturierte Logs, Tracing | MEDIUM |
| 09 | [09-ci-pipeline.md](09-ci-pipeline.md) | GitHub Actions: shellcheck, bats, ISO-Build, SBOM | **HIGH** |
| 10 | [10-integration-tests.md](10-integration-tests.md) | Boot→Enrollment→Streaming, Backup→Restore E2E | **HIGH** |
| 11 | [11-beagle-host-endbeseitigung.md](11-beagle-host-endbeseitigung.md) | `beagle-ui/` + `providers/beagle-host/` loeschen | MEDIUM |
| 12 | [12-ux-accessibility.md](12-ux-accessibility.md) | i18n, ARIA, mobile, Error-Standardisierung | LOW |

## Roadmap

**Welle A — Sofort (Sicherheit + Datenintegritaet):**
- Plan 01: Atomic Writes — verhindert State-Korruption
- Plan 02: TLS-Haerte — schliesst MITM-Angriffsflaechen
- Plan 03: Secret-Rotation — verhindert Langzeit-Token-Diebstahl

**Welle B — Mittelfrist (Skalierung + Wartbarkeit):**
- Plan 04: Subprocess-Sandboxing
- Plan 05: Control-Plane Split
- Plan 09: CI-Pipeline (parallel zu Welle A moeglich)
- Plan 10: Integration-Tests

**Welle C — Langfrist (Architektur):**
- Plan 06: SQLite-Migration
- Plan 07: Async-Job-Queue
- Plan 08: Observability
- Plan 11: Beagle host-Endbeseitigung
- Plan 12: UX & Accessibility

## Audit-Quelle

Alle Plaene basieren auf der Repo-Audit vom 2026-04-25 mit konkreten Datei- und Zeilen-Verweisen. Jeder Plan listet die betroffenen Dateien und einen ausfuehrlichen Schrittplan.

## Bezug zu bestehenden Dokumenten

- `docs/refactor/11-security-findings.md` — Security-Funde werden hier konsolidiert
- `docs/refactor/05-progress.md` — Fortschritt wird nach jedem Schritt aktualisiert
- `docs/refactor/06-next-steps.md` — Naechste Schritte werden parallel gepflegt
- `AGENTS.md` — Code-First-Regel und Multi-Agent-Regel gelten weiterhin
