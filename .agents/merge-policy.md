# Merge Policy

## Grundregeln

- Niemals direkt auf `main` entwickeln.
- Immer Branch + Pull Request.
- Merge nur bei gruenen Pflicht-Checks.
- Merge nur nach bestandener Selbstpruefung (`.agents/review-policy.md`).

## Merge-Voraussetzungen

- Tests erfolgreich.
- Build fuer betroffenen Scope erfolgreich.
- Lint/Type-Checks fuer betroffenen Scope erfolgreich oder dokumentiert begrenzt.
- Keine neuen Secrets.
- Keine verbotenen Dateien/Aktionen.
- Kein Label wie `do-not-merge`, `needs-human-review`, `dangerous-change`.

## Merge-Modus

- Standard: Squash-Merge (kompakte Historie fuer autonome Kleinaenderungen).
- Falls Repo-Owner andere Konvention vorgibt: daran anpassen und in `.agents/decision-log.md` dokumentieren.

## Nach Merge

- `main` frisch ziehen.
- Kurzvalidierung ausfuehren (mindestens betroffener Test/Smoke).
- Bei Regression sofort Fix-Branch erstellen.
