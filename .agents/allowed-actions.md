# Allowed Actions

Der Agent darf autonom:

- Analyse, Refactoring, Bugfixes und kleine/mittlere Features umsetzen.
- Tests, Linter und Builds ausfuehren.
- Dokumentation, Runbooks und Policy-Dateien aktualisieren.
- Branches erstellen und Commits mit klaren Messages erzeugen.
- Pull Requests vorbereiten/erstellen und nach Policy reviewen.
- Auto-Merge nutzen, wenn alle Merge-Bedingungen erfuellt sind.

## Repo-spezifisch erlaubt

- Arbeit auf `providers/beagle/`, `beagle-host/`, `core/`, `scripts/`, `website/`, `public-site/`, `tests/`.
- Live-Host-Checks auf `srv1`/`srv2`, wenn zur Gate-Validierung notwendig und ohne Geheimnisse zu loggen.
