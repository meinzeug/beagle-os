# Decision Log

## 2026-06-01 - Initial autonomous agent framework

- Entscheidung: Einheitliche `.agents/`-Struktur eingefuehrt, damit autonome Runs reproduzierbar starten.
- Entscheidung: Policies eng an bestehende Workflows (`tests.yml`, `lint.yml`, Security + Copilot automerge) gekoppelt.
- Entscheidung: Baseline-CI-Entry (`.github/workflows/ci.yml`) wird als risikoarme erste Verbesserung eingefuehrt.
- Grund: Wiederholbare autonome Weiterentwicklung mit klaren Merge- und Sicherheitsgrenzen.

## 2026-06-01 - AGENTS root file strategy

- Entscheidung: `AGENTS.md` vollstaendig neu geschrieben gemaess expliziter User-Vorgabe.
- Grund: Die neue Agenten-Steuerung soll klar, dauerhaft und ohne Altlasten funktionieren.

## 2026-06-01 - Auto-merge setup handling

- Entscheidung: Bestehenden Copilot-Automerge-Pfad beibehalten und Owner-Schritte in `.agents/auto-merge-setup.md` explizit dokumentieren.
- Grund: Repo hat bereits konservative Automerge-Mechanik fuer `copilot/*`, aber allgemeiner Auto-Merge braucht Repo-Settings/Labels durch Owner.

## 2026-06-01 - Release resolver prerelease support (slice)

- Entscheidung: `scripts/resolve-release-version.sh` erweitert auf SemVer-Prereleases (`x.y.z-alpha.N`, `x.y.z-beta.N`, `x.y.z-rc.N`) und `release_class` GitHub-Output (`stable|prerelease`).
- Grund: Erster P0-Teil aus `projectleader/todo.md` soll reproduzierbar abgeschlossen werden, bevor Workflow-Gates umgestellt werden.
- Guardrails: Auto-bump-Pfad bleibt stabil (`x.y.z`), Prerelease wird nur ueber expliziten Input/Tag aufgeloest.

## 2026-06-01 - Release channel workflow wiring

- Entscheidung: `release.yml` nutzt `release_class` fuer Release-Erstellung; Prereleases werden mit `--prerelease --latest=false` erstellt/editiert.
- Entscheidung: Public-Deploy-Job in `release.yml` wird fuer `release_class=prerelease` komplett uebersprungen, damit stabile Mirror-Dateien nicht ueberschrieben werden.
- Entscheidung: `public-website.yml` fuehrt fuer Prerelease-Versionen keinen Website-Deploy aus.
- Entscheidung: `scripts/sync-release-version.py` setzt Extension-Manifest auf numerisches Core-`version` und volle Produktversion in `version_name`.
- Grund: Stable-Artefakte und `latest`-Signal muessen vor Prerelease-Ueberschreiben geschuetzt bleiben; Extension-Manifest muss kompatibel numerisch bleiben.
