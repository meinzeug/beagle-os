# Repository Analysis

Stand: 2026-06-01

## Aktueller Projektstand

Beagle OS ist bereits ein grosses Multi-Stack-Repository mit produktionsnahen Komponenten fuer:

- Host Control Plane und API (`beagle-host/`, Python)
- Provider-Layer fuer KVM/libvirt (`providers/beagle/`)
- Thin-Client Runtime und Installer-Artefakte (`thin-client-assistant/`, Shell/Python)
- Gaming-Kiosk (`beagle-kiosk/`, Electron)
- WebUI/Public Site (`website/`, `public-site/`, HTML/CSS/JS)
- Umfangreiche Testlandschaft (`tests/unit`, `tests/integration`, `tests/e2e`, `tests/bats`)

Der produktive Fokus im Repo liegt auf dem Standalone-Beagle-Provider und LastHope/Diamond-Gates unter `docs/lasthope/`.

## Erkannte Technologie-Stacks

- Python: Control Plane, Services, API-Logik, viele Tests
- Shell: Build-, Install-, Deploy-, Security- und Runtime-Skripte
- JavaScript/Node:
  - Electron Kiosk (`beagle-kiosk/`)
  - WebUI/UI-Skripte (`website/`, `extension/`)
  - Playwright-Capture fuer Doku (`scripts/capture-webui-doc-assets.mjs`)
- Go: Terraform Provider (`terraform-provider-beagle/`)
- GitHub Actions: CI, Security, Release, Website, Copilot-Autofix/Automerge

## Vorhandene Start-/Build-/Testbefehle

### Lokale Kernbefehle

- Host Setup: `./scripts/setup-beagle-host.sh`
- Host Check: `./scripts/check-beagle-host.sh`
- Thin Client Build: `./scripts/build-thin-client-installer.sh`
- Server ISO Build: `./scripts/build-server-installer.sh`
- Installimage Build: `./scripts/build-server-installimage.sh`
- Download-Artefakte: `./scripts/prepare-host-downloads.sh`

### Tests

- Unit: `python3 -m pytest -q tests/unit/`
- Integration: `python3 -m pytest -q tests/integration/`
- E2E: `python3 -m pytest -q tests/e2e/`
- Bats: `bats --tap tests/bats/`

### Lint/Type

- Ruff: `ruff check core/ beagle-host/services/ providers/ scripts/ tests/`
- Mypy: `mypy core/ --strict --ignore-missing-imports`
- Shellcheck: auf `.sh`-Skripten
- ESLint: `website/ui/*.js`, `extension/*.js`

## CI/CD-Ueberblick

Vorhanden unter `.github/workflows/`:

- `tests.yml` (pytest matrix, bats, integration, Playwright WebUI smoke)
- `lint.yml` (shellcheck, ruff, mypy, eslint)
- Security-Workflows (`security-secrets-check`, `security-subprocess-check`, `security-tls-check`, `security-audit`)
- Release-Pipeline (`release.yml`, `build-iso.yml`, `public-website.yml`)
- Copilot-Loops (`copilot-autofix.yml`, `copilot-automerge.yml`)

## Architekturuebersicht

- API/Control Plane: `beagle-host/services/` mit modularen Surfaces und Service-Registry.
- Abstraktion: Provider-Contract + aktiver Beagle-Provider, keine neue Proxmox-Kopplung.
- Endpoint/Streaming: Thin-Client Runtime, Enrollment, WireGuard, Stream-Integration.
- UI: Web Console und Public Docs/Website als getrennte Oberflaechen.
- Artefakte/Releases: Build-Skripte + GitHub Releases + Website-Mirror.

## Risiken

- Hohe Komplexitaet durch Multi-Stack und viele Build-/Releasepfade.
- Teilweise warn-only Lint-Regeln (`ruff` in `lint.yml`), dadurch Schuldenstau moeglich.
- Runtime-Gates benoetigen echte Host-Evidenz; reine Unit-Tests reichen nicht.
- Secrets-/Token-Risiko bei operatornahen Skripten bleibt hoch und braucht strikte Hygiene.
- Bestehender Copilot-Automerge-Pfad ist branch-spezifisch (`copilot/*`) und setzt Secrets/Repo-Konfiguration voraus.

## Fehlende Tests (prioritaer)

- Mehr Regressionstests fuer Release-Kanal-/Versionierungslogik (stable vs prerelease).
- Mehr End-to-End-Abdeckung fuer frischen VM-Create -> Firstboot -> Stream-Ready.
- Zusatztests fuer Website/Doku-Deploy-Pfade (aktive Express-Static-Quelle vs vhost-root).

## Fehlende Dokumentation

- Einheitliche Agenten-Governance fuer autonome Entwicklungszyklen fehlte (wird mit `.agents/` geschlossen).
- Explizite Auto-Merge-Owner-Schritte fuer GitHub-Reposettings bisher nicht zentral dokumentiert.

## Kurzfristige Verbesserungsideen (1-2 Wochen)

- Agenten-Struktur + Policies + Skills finalisieren.
- Baseline-CI (`ci.yml`) als zentralen Entry-Workflow bereitstellen.
- Release-/Versioning-Regressionen laut `projectleader/todo.md` priorisieren.

## Mittelfristige Roadmap (1-2 Monate)

- Clean-Install-Gate R1 mit reproduzierbarer Evidence schliessen.
- Stream-E2E-Gates fuer frische Payloads ohne Hotpatches stabilisieren.
- Backup/Restore auf 2 Hosts reproduzierbar nachweisen.
- Lint-Backlog reduzieren und warn-only Regeln schrittweise haerten.

## Langfristige Vision

Beagle OS als stabile, dokumentierte und enterprise-faehige Standalone-Plattform:

- reproduzierbare Bare-Metal-Installationen
- stabile VM-/Stream-Lifecycle-Automation
- sichere Endpoint-Vernetzung
- belastbare Update-/Rollback- und Support-Prozesse
- kontinuierliche, testgetriebene Weiterentwicklung ueber autonome Agenten
