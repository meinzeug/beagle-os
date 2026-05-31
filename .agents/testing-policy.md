# Testing Policy

## Mindestregel

Jede Aenderung braucht Verifikation auf passendem Niveau:

- Unit-Tests fuer Logik/Bugfixes.
- Integrationstests fuer Service-Interaktionen.
- Smoke/E2E fuer UI/Runtime-Pfade, wenn betroffen.

## Repo-spezifische Prioritaet

1. `tests/unit/`
2. `tests/integration/`
3. `tests/bats/`
4. `tests/e2e/` (falls benoetigt/verfuegbar)

## Bei fehlenden Tests

- Mindestens reproduzierbaren manuellen Smoke dokumentieren.
- Test-Luecke in `.agents/backlog.md` erfassen.
