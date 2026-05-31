# Autonomous Status

Stand: 2026-06-01

## Session Summary

- Repository-Analyse fuer Stack, CI, Tests, Doku und Risiken erstellt und in `.agents/repo-analysis.md` abgelegt.
- Vollstaendige Agenten-Governance unter `.agents/` inklusive Policies, Skills und Setup-Doku eingerichtet.
- Root-Steuerdateien `AGENTS.md` und `ongoing.md` fuer den autonomen Dauerbetrieb angelegt.
- Erste risikoarme Verbesserung umgesetzt: `.github/workflows/ci.yml` als baseline CI entry workflow hinzugefuegt.
- Lokale Verifikation erfolgreich:
	- `python3 -m pytest -q tests/unit/test_storage_pool_path_regressions.py tests/unit/test_ubuntu_beagle_desktop_profiles.py tests/unit/test_ubuntu_beagle_provisioning_quota.py`
	- `node --check scripts/capture-webui-doc-assets.mjs`
	- `node --check extension/common.js`
	- `node --check extension/content.js`
	- `node --check extension/options.js`

## Aktueller Fokus

- Commit/Push der neuen Agenten-Struktur und CI-Ergaenzung im Branch `chore/autonomous-agent-framework`.
- PR-Vorbereitung inkl. Auto-Merge-Einschaetzung nach `.agents/review-policy.md` und `.agents/merge-policy.md`.

## Offene Risiken

- Release-/Versionierungslogik bleibt hoch priorisiert (aus `projectleader/todo.md`).
- Runtime-Gates brauchen weiter reale Host-Evidence.
- `AGENTS.md` ist aktuell in `.gitignore` enthalten; falls versioniert gewuenscht, muss bewusst entschieden werden, ob die Ignore-Regel angepasst oder `git add -f` genutzt wird.

## Naechster sinnvoller Schritt

Agenten-Struktur + baseline CI als eigenen PR-Slice finalisieren, danach den naechsten kleinen P0/P1-Schritt aus `projectleader/todo.md` umsetzen (Release-Versionierung stable/prerelease).

## Session Update 2026-06-01 (Release Resolver Slice)

- Analysiert: `scripts/resolve-release-version.sh`, `tests/unit/test_release_workflow_regressions.py`, `projectleader/todo.md`, Release-Workflows.
- Geaendert: `scripts/resolve-release-version.sh` akzeptiert nun Stable und Prerelease-SemVer (`alpha|beta|rc`) und schreibt `release_class` in GitHub-Outputs.
- Geaendert: Neuer Regressionstest `tests/unit/test_resolve_release_version_script.py` fuer stable/prerelease/tag-ref/invalid-4-part.
- Getestet:
	- `bash -n scripts/resolve-release-version.sh`
	- `python3 -m pytest -q tests/unit/test_resolve_release_version_script.py tests/unit/test_release_workflow_regressions.py`
	- Ergebnis: `8 passed`.
- Offenes Risiko: Workflow-Gating fuer Prerelease-Publishing (`--prerelease --latest=false` und Public-Deploy-Bypass) ist noch offen.
- Naechster Schritt: `release.yml` und `public-website.yml` auf `release_class` verdrahten und mit Regressionstests absichern.

## Session Update 2026-06-01 (Release Channel Wiring + Extra Tasks)

- Analysiert: `.github/workflows/release.yml`, `.github/workflows/public-website.yml`, `scripts/sync-release-version.py`, `scripts/create-github-release.sh`.
- Geaendert: Release-Workflow nutzt `release_class` fuer GitHub Release Flags (`--prerelease --latest=false`) und blockiert `deploy-public-artifacts` fuer Prereleases.
- Geaendert: Public-Website-Workflow erkennt Prerelease-Versionen und ueberspringt Deployment/Verifikation fuer Prereleases.
- Geaendert: `scripts/sync-release-version.py` akzeptiert Prerelease-SemVer, synchronisiert Root/Kiosk/WebUI mit voller Produktversion und setzt Extension `version` numerisch (Core) plus `version_name` (voll).
- Geaendert (zusatz): `scripts/create-github-release.sh` mit `BEAGLE_RELEASE_CLASS` + stabilen/prerelease Release-Flags.
- Tests (zusatz):
	- `tests/unit/test_sync_release_version.py`
	- `tests/unit/test_public_website_workflow_regressions.py`
	- `tests/unit/test_create_github_release_script_regressions.py`
	- Erweiterung `tests/unit/test_release_workflow_regressions.py`
- Getestet:
	- `bash -n scripts/resolve-release-version.sh`
	- `bash -n scripts/create-github-release.sh`
	- `python3 -m pytest -q tests/unit/test_resolve_release_version_script.py tests/unit/test_sync_release_version.py tests/unit/test_release_workflow_regressions.py tests/unit/test_public_website_workflow_regressions.py tests/unit/test_create_github_release_script_regressions.py`
	- Ergebnis: `17 passed`.
- Offenes Risiko: Full-E2E fuer echte prerelease Publish-Runs in GitHub Actions muss nach PR-Merge beobachtet werden.
- Naechster Schritt: PR erstellen/aktualisieren und auf CI-Checks warten; danach auto-merge nur bei komplett gruenen Pflichtchecks.
