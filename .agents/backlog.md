# Backlog

Stand: 2026-06-01

## P0

- [x] Agenten-Grundstruktur (`.agents/`, Skills, Policies, `ongoing.md`) eingerichtet.
- [x] Baseline-CI-Entryworkflow (`.github/workflows/ci.yml`) hinzugefuegt.
- [ ] Release-Versionierungslogik (stable/prerelease) gemaess `projectleader/todo.md` fertigstellen und absichern.
	- [x] `scripts/resolve-release-version.sh`: Stable + Prerelease SemVer akzeptieren, `release_class` ausgeben, 4-part Versionsschema ablehnen.
	- [ ] `release.yml`: `release_class` fuer prerelease-spezifisches GitHub Release Verhalten (`--prerelease --latest=false`) verdrahten.
	- [ ] Public stable deployment fuer prereleases explizit unterbinden.
	- [ ] `scripts/sync-release-version.py` fuer Extension `version`/`version_name` bei prerelease erweitern.
	- [ ] Zusatztets fuer Workflow-Gating und Sync-Logik.
- [ ] CI-Lint-Haertung vorbereiten (warn-only ruff schrittweise in fail-gates ueberfuehren).

## P1

- [ ] Tests fuer frischen VM-Provisioning-Lifecycle erweitern (Create -> Firstboot -> Stream-Ready).
- [ ] Dokumentierte Deploy-Checks fuer aktive Website-Serving-Pfade automatisieren.

## P2

- [ ] Zuschnitt und Priorisierung alter TODOs/Fixmes mit klaren Ownern.
- [ ] Doku-Konsistenz zwischen `projectleader/`, `docs/lasthope/` und `docs/refactor/` weiter verbessern.
