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

- [ ] **Schritt 1** — `lint.yml` Workflow
  - [ ] `.github/workflows/lint.yml`:
    - shellcheck auf alle `*.sh` (excludes konfigurierbar via `.shellcheckrc`)
    - ruff auf `core/`, `beagle-host/services/`, `providers/`, `scripts/`, `tests/`
    - mypy auf `core/` (strikt) + `beagle-host/services/` (lax)
    - eslint auf `website/ui/*.js`, `extension/*.js` (Standard-Config)
  - [ ] Cache fuer node_modules + pip
  - [ ] Failt PR bei Fehlern

- [ ] **Schritt 2** — `tests.yml` Workflow
  - [ ] `.github/workflows/tests.yml`:
    - `python3 -m pytest tests/unit/ -q --cov=core --cov=beagle-host/services --cov-report=xml`
    - Coverage-Upload (codecov oder github-pages)
    - bats fuer kritische Skripte: `tests/bats/*.bats`
  - [ ] Matrix: Python 3.11, 3.12

- [ ] **Schritt 3** — Bats-Tests
  - [ ] `tests/bats/install_beagle_host.bats`: testet `scripts/install-beagle-host.sh` in chroot/container
  - [ ] `tests/bats/post_install_check.bats`: testet `server-installer/post-install-check.sh` mit Mock-Services
  - [ ] `tests/bats/tpm_attestation.bats`: testet `thin-client-assistant/runtime/tpm_attestation.sh` mit Stub-tpm2_pcrread
  - [ ] Doku: `tests/bats/README.md`

- [ ] **Schritt 4** — ISO-Build-Pipeline
  - [ ] `.github/workflows/build-iso.yml`:
    - Trigger: cron (taeglich) + `workflow_dispatch`
    - Schritt 1: `scripts/build-server-installer.sh`
    - Schritt 2: `scripts/build-thin-client-installer.sh`
    - Schritt 3: SHA256-Hash + Vergleich mit vorherigem Tag (Reproduzibilitaet)
    - Schritt 4: SBOM via `cyclonedx-bom` (Python) + `cyclonedx-npm` (JS)
    - Artefakte: ISO, SHA256SUMS, SBOM
  - [ ] Aufbewahrung: 7 Tage in GitHub Actions, dauerhaft bei Release

- [ ] **Schritt 5** — Release-Pipeline
  - [ ] `.github/workflows/release.yml`:
    - Trigger: Tag `v*.*.*`
    - Baut ISO + SBOM
    - Generiert Changelog aus Git-Log
    - Erstellt GitHub-Release mit Artefakten
    - Signiert ISO + SBOM mit Cosign (sigstore)

- [ ] **Schritt 6** — CI-Guards
  - [ ] `.github/workflows/security-tls-check.yml` (siehe Plan 02)
  - [ ] `.github/workflows/security-subprocess-check.yml` (siehe Plan 04)
  - [ ] `.github/workflows/no-proxmox-references.yml`: greppt auf `pvesh`, `qm`, `PVEAuthCookie`, `proxmox-ui` ausserhalb `proxmox-ui/` (das wird nach Plan 11 geloescht)

- [ ] **Schritt 7** — Branch-Protection
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
