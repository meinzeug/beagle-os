# 04 — Qualitaet, CI, Tests, Observability, Datenintegritaet

**Scope**: Lint, Unit-/Integration-/E2E-Tests, CI-Pipelines, Observability, Datenintegritaet, Async-Job-Queue.
**Quelle**: konsolidiert aus `docs/archive/goadvanced/01,06-10`, `docs/archive/gorelease/04`.

---

## Lint + Static Analysis (CI)

- [x] `lint.yml`: shellcheck + ruff + mypy hard-fail; eslint warn-only
- [x] CI-Guard `no-legacy-provider-references.yml` (Allowlist gehaertet, FOUND=0)
- [x] mypy strict auf `core/` von warn-only auf hard-fail umstellen — Workflow nutzt `--explicit-package-bases`, lokale Validierung: `Success: no issues found in 27 source files`.
- [x] eslint hart auf `website/ui/*.js` schalten — 0 errors, 22 warnings; `lint.yml` auf hard-fail umgestellt; `.eslintrc.json` fuer `website/ui/` erstellt (2026-04-30)

## Unit + Integration + E2E

- [x] 643+ Unit-Tests in `tests/unit/` produktiv
- [x] 7 Integrations-Test-Module in `tests/integration/` (89 Tests gruen)
- [x] 3 bats-Tests aktiv (`post_install_check`, `tpm_attestation`, `cluster_auto_join`)
- [x] Integration-Tests laufen in CI (`tests.yml` Job `integration` — gefixt 2026-04-29)
- [x] E2E-Smoke `tests/e2e/test_smoke_srv1.py` + nightly-Cron `e2e-nightly.yml`
- [ ] `tests/bats/install_beagle_host.bats` mit Docker-Sandbox (deferred)
- [x] Integration-Test-Coverage-Report als CI-Artefakt — `pytest-cov` in `tests.yml` fuer unit + integration Jobs; HTML+XML als Actions-Artefakte, retention 14 Tage (2026-04-30)
- [x] Cleanup-Hooks auf srv1 verlassen Host in sauberem Zustand (R3) — `CLEANUP_HOOKS_SMOKE=PASS` auf srv1 (2026-04-30)

## Build + Release Pipeline

- [x] `build-iso.yml`: `workflow_dispatch` + push-Trigger + nightly cron + SBOM (CycloneDX) + Reproduzibilitaets-Check
- [x] `release.yml`: Tag-Trigger, GPG-Signatur (SHA256SUMS.sig), Cosign keyless, SBOM-Bundling
- [x] `release.yml` baut ISO/installimage/thin-client bei normalen `main`-Pushes nur noch bei relevanten Pfadaenderungen; letzter Push-Run `25256444508` erfolgreich ohne Full-Release-Fallthrough (2026-05-02)
- [x] Frontend-Provisioning-Smoke (`webui-provisioning-smoke` Playwright Job)
- [ ] Branch-Protection auf `main` aktiv (manuelle GitHub-UI-Konfig; GitHub API 2026-05-02: `Branch not protected`, bleibt offen)

## Datenintegritaet

- [x] `JsonStateStore` mit atomic writes + file-locking (`docs/archive/goadvanced/01-data-integrity.md`)
- [x] `core/persistence/` Modul: write-temp + fsync + rename
- [x] **Schritt 3** — `BeagleDb`-Singleton + `PoolRepository` + `DeviceRepository` + `VmRepository` in `service_registry.py` verdrahtet; DB-Pfad `DATA_DIR/state.db` (`/var/lib/beagle/beagle-manager/state.db`); live auf `srv1` deployt, alle v1-Endpunkte 200, WAL aktiv (2026-04-30)
- [x] **Schritt 4** — One-Shot-Importer `scripts/migrate-json-to-sqlite.py` (live auf `srv1` ausgefuehrt; Backup unter `/var/lib/beagle/.bak/20260430T160508Z/`, SQLite-Rows: `vms=2`, `pools=1`)
- [x] SQLite-DB unter `/var/lib/beagle/beagle-manager/state.db` produktiv (WAL aktiv, owned by beagle-manager)

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
- [x] axe-core CLI gegen `https://srv1.beagle-os.com` — 0 Critical/Serious (`npx -y @axe-core/cli ... --tags wcag2a,wcag2aa`: 0 violations, 2026-04-30)
- [ ] Lighthouse Mobile-Score > 90, Accessibility > 90
- [ ] Mobile-Responsive (Breakpoints 360/600/900/1200, Touch-Targets >= 44px)
- [x] Dark-Mode persistiert + `prefers-color-scheme`-Default — `website/ui/theme.js` liest `prefers-color-scheme` wenn kein expliziter `localStorage`-Eintrag vorhanden (2026-04-30)
- [ ] Skeleton-Loader + Empty-States + Error-States mit Retry-Button
