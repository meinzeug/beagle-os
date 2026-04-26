# Plan 09 — CI-Pipeline: shellcheck, bats, ISO-Build, SBOM

**Dringlichkeit**: HIGH
**Welle**: B (Mittelfrist)
**Audit-Bezug**: D-001, C-002

## Problem

Aktuell gibt es nur `.github/workflows/security-audit.yml` und `security-secrets-check.yml`. Es fehlt:

- shellcheck-Lint fuer alle Shell-Skripte
- bats-Tests fuer kritische Install-Skripte
- ISO-Build-Pipeline (Reproduzierbarkeit + SBOM)
- Python-Lint (ruff/mypy)
- Pytest-Run mit Coverage-Reporting
- Frontend-Lint (eslint fuer website/ui/)

Ohne CI sind Regressionen schwer zu vermeiden.

## Ziel

1. Vollstaendiger CI-Workflow auf jedem PR.
2. Shell + Python + JS gelintet.
3. Alle Tests laufen automatisch.
4. ISO-Build wird wenigstens taeglich getriggert (cron) und Hash veroeffentlicht.
5. SBOM (CycloneDX) bei jedem Release.

## Schritte

- [x] **Schritt 1** — `lint.yml` Workflow _(2026-04-25 — vorhanden)_
  - [x] `.github/workflows/lint.yml`: shellcheck (alle `*.sh`, excludes `.git`/`.build`/`node_modules`/`.artifacts`), ruff (`core/`, `beagle-host/services/`, `providers/`, `scripts/`, `tests/`), mypy strict auf `core/` (warn-only), eslint auf `website/ui/*.js`+`extension/*.js` (warn-only)
  - [x] pip-Cache via `actions/setup-python` `cache: pip`
  - [x] PR-Fail bei shellcheck/ruff (mypy + eslint warn-only bis Backlog reduziert)

- [x] **Schritt 2** — `tests.yml` Workflow _(2026-04-25 — pytest + bats)_
  - [x] `.github/workflows/tests.yml`: pytest mit `--cov=core` + `--cov=beagle-host/services`, Coverage als Artefakt (Retention 14d), Matrix `3.11`/`3.12`
  - [x] **Neu 2026-04-25**: separater `bats` Job laeuft `bats --tap tests/bats/` (installiert `bats jq python3-yaml` via apt)

- [x] **Schritt 3** — Bats-Tests _(2026-04-25)_
  - [ ] `tests/bats/install_beagle_host.bats` _(deferred — `install-beagle-host.sh` benoetigt chroot/Container; eigener Folge-Step mit Docker-Sandbox)_
  - [x] `tests/bats/post_install_check.bats`: 7 Tests — Stubs fuer `systemctl`/`virsh`/`curl`/`ip`/`ping`/`hostname`. Setup-Bug (`load ""` crash + relativer `BATS_TEST_FILE`-Pfad + `is-active --quiet`-Argumentparsing + `--write-out` curl-Stub) komplett gefixt; jetzt 7/7 gruen lokal.
  - [x] `tests/bats/tpm_attestation.bats` _(neu)_: 9 Tests — Stubs fuer `tpm2_pcrread`/`curl`/`hostname`; deckt Happy-Path (accepted), rejected, HTTP 403, TPM-Fehler, leere PCRs, fehlendes `tpm2_pcrread` und alle drei Pflicht-Env-Vars ab. Tests skip-en sauber wenn `jq`/`python3-yaml` fehlt.
  - [ ] `tests/bats/README.md` _(deferred — kommt mit `install_beagle_host.bats`)_

- [/] **Schritt 4** — ISO-Build-Pipeline _(2026-04-25 — cron + SBOM-Job ergaenzt)_
  - [x] `.github/workflows/build-iso.yml`: `workflow_dispatch` mit Auswahl `installimage`/`iso`/`both`, push-Trigger fuer `server-installer/`/`beagle-host/`/Build-Skripte/`VERSION`, baut via `build-server-installimage.sh` und `build-server-installer.sh`, lädt Artefakte hoch (Retention 30d)
  - [x] **Neu 2026-04-25**: cron-Schedule `17 3 * * *` (taeglicher Reproduzibilitaets-Build der installimage-Variante)
  - [x] **Neu 2026-04-25**: `sbom` Job — erzeugt CycloneDX-SBOMs fuer Python (cyclonedx-bom) und Node (`extension/`, `beagle-kiosk/` via cyclonedx-npm), bundelt SHA256SUMS, Artefakt-Retention 90d
  - [x] `build-thin-client-installer.sh`-Job — implementiert in `build-iso.yml` (job: `build-thin-client`)
  - [x] SHA256-Reproduzibilitaets-Vergleich vs Vortags-Build — implementiert (job: `reproducibility-check`, schedule-only, warn-only)

- [/] **Schritt 5** — Release-Pipeline _(2026-04-25 — Basis vorhanden, Cosign offen)_
  - [x] `.github/workflows/release.yml`: Tag-Trigger `v*.*.*`, baut Installimage+ISO, generiert `SHA256SUMS`, GPG-signiert (`SHA256SUMS.sig`), Changelog aus Git-Log, GitHub-Release mit Artefakten
  - [x] Cosign-Signatur (sigstore) — `sigstore/cosign-installer@v3`, keyless sign-blob, `.cosign.bundle` sidecar im Release; continue-on-error (kein Hard-Blocker bei fehlendem OIDC-Token)
  - [x] SBOM-Bundling — neuer `sbom`-Job im release.yml, alle `.cdx.json` als Release-Assets angehaengt

- [x] **Schritt 6** — CI-Guards _(2026-04-25 — alle drei aktiv)_
  - [x] `.github/workflows/security-tls-check.yml`
  - [x] `.github/workflows/security-subprocess-check.yml`
  - [x] `.github/workflows/no-proxmox-references.yml` (Allowlist + grep-Excludes via Plan 11 Schritt 7 gehärtet, lokale Simulation FOUND=0)

- [ ] **Schritt 7** — Branch-Protection _(GitHub-UI-Konfiguration, kein Repo-Code; deferred bis Multi-Maintainer)_
  - [ ] `main` Branch: alle CI-Jobs muessen gruen sein
  - [ ] Mind. 1 Review erforderlich (wenn Multi-Maintainer)
  - [ ] Doku: `docs/contributing.md`

## Abnahmekriterien

- [ ] `lint.yml` und `tests.yml` laufen auf jedem PR.
- [ ] Mind. 3 bats-Tests aktiv.
- [ ] `build-iso.yml` laeuft taeglich erfolgreich.
- [ ] SBOM wird generiert + bei Release veroeffentlicht.
- [ ] CI-Guards aktiv (TLS, subprocess, no-proxmox).
- [ ] Branch-Protection auf `main` aktiv.

## Risiko

- ISO-Builds in CI brauchen ggf. >2GB RAM und privileged Container → ggf. self-hosted Runner notwendig
- bats-Tests in chroot benoetigen evtl. Root-Privilegien → Docker-basierte Sandbox als Fallback
- Reproduzierbarkeit von ISO-Builds ist heikel (Timestamps, UUIDs) → SOURCE_DATE_EPOCH setzen
