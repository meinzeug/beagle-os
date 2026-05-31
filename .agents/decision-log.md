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
