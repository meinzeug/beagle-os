# 04 — Qualitaet, CI, Tests, Observability, Datenintegritaet

**Scope**: Lint, Unit-/Integration-/E2E-Tests, CI-Pipelines, Observability, Datenintegritaet, Async-Job-Queue.
**Quelle**: konsolidiert aus `docs/archive/goadvanced/01,06-10`, `docs/archive/gorelease/04`.

---

## Lint + Static Analysis (CI)

- [x] `lint.yml`: shellcheck + ruff hard-fail; mypy + eslint warn-only
- [x] CI-Guard `no-legacy-provider-references.yml` (Allowlist gehaertet, FOUND=0)
- [ ] mypy strict auf `core/` von warn-only auf hard-fail umstellen (Backlog: type-Backlog reduzieren)
- [ ] eslint hart auf `website/ui/*.js` schalten (Backlog)

## Unit + Integration + E2E

- [x] 643+ Unit-Tests in `tests/unit/` produktiv
- [x] 7 Integrations-Test-Module in `tests/integration/` (89 Tests gruen)
- [x] 3 bats-Tests aktiv (`post_install_check`, `tpm_attestation`, `cluster_auto_join`)
- [x] Integration-Tests laufen in CI (`tests.yml` Job `integration` — gefixt 2026-04-29)
- [x] E2E-Smoke `tests/e2e/test_smoke_srv1.py` + nightly-Cron `e2e-nightly.yml`
- [ ] `tests/bats/install_beagle_host.bats` mit Docker-Sandbox (deferred)
- [ ] Integration-Test-Coverage-Report als CI-Artefakt
- [ ] Cleanup-Hooks auf srv1 verlassen Host in sauberem Zustand (R3)

## Build + Release Pipeline

- [x] `build-iso.yml`: `workflow_dispatch` + push-Trigger + nightly cron + SBOM (CycloneDX) + Reproduzibilitaets-Check
- [x] `release.yml`: Tag-Trigger, GPG-Signatur (SHA256SUMS.sig), Cosign keyless, SBOM-Bundling
- [x] Frontend-Provisioning-Smoke (`webui-provisioning-smoke` Playwright Job)
- [ ] Branch-Protection auf `main` aktiv (manuelle GitHub-UI-Konfig, deferred bis Multi-Maintainer)

## Datenintegritaet

- [x] `JsonStateStore` mit atomic writes + file-locking (`docs/archive/goadvanced/01-data-integrity.md`)
- [x] `core/persistence/` Modul: write-temp + fsync + rename
- [ ] **Schritt 3** — Repository-Pattern fuer alle State-Konsumenten
- [ ] **Schritt 4** — One-Shot-Importer `scripts/migrate-json-to-sqlite.py`
- [ ] SQLite-DB unter `/var/lib/beagle/state.db` produktiv (Phase 2 — Backlog, JSON-Backend bleibt vorerst)

## Async Job Queue

- [x] Job-Queue + Worker (`async_job_queue.py`)
- [x] Job-Status via SSE in WebUI (`jobs_panel.js`)
- [x] Schritt 7 — Validation auf srv1 mit echtem Backup-Job + Long-Running-Stress (R3) — `ASYNC_JOB_QUEUE_SMOKE=PASS` auf `srv1` (2026-04-30, schema=valid)

## Observability

- [x] strukturierte Log-Helpers (`core/observability/`)
- [x] Prometheus-Metrics-Endpoint
- [ ] Massen-Migration aller `print()`-Aufrufe auf strukturierte Logs (Backlog)
- [x] Smoke-Test gegen laufenden Server: alle erwarteten Metric-Familien vorhanden (R3) — `METRICS_FAMILIES_SMOKE=PASS` auf `srv1` (2026-04-30, families_found=7)
- [ ] OpenTelemetry-Adapter (Phase 2 optional)

## UX / i18n / Accessibility

- [x] i18n-Modul `website/ui/i18n.js` (de/en, 68 Keys, 21 Tests gruen)
- [x] `website/ui/error-handler.js` standardisiert (showError/Warning/Success/Info, handleFetchError)
- [x] 5 `alert()`/`console.error()`-Calls migriert
- [ ] Migration aller hard-coded Strings in UI-Modulen auf `t()` (beginnend `auth_admin.js`, `vms_panel.js`)
- [ ] axe-core CLI gegen `https://srv1.beagle-os.com` — 0 Critical/Serious
- [ ] Lighthouse Mobile-Score > 90, Accessibility > 90
- [ ] Mobile-Responsive (Breakpoints 360/600/900/1200, Touch-Targets >= 44px)
- [ ] Dark-Mode persistiert + `prefers-color-scheme`-Default
- [ ] Skeleton-Loader + Empty-States + Error-States mit Retry-Button
