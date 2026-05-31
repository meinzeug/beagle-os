# Review Policy

Jede PR muss vor Merge diese Selbstpruefung bestehen:

## Diff- und Kontextpruefung

- Gesamten Diff lesen.
- Jede geaenderte Datei vollstaendig lesen.
- Relevante Aufrufer, Imports und Abhaengigkeiten pruefen.
- Nebenwirkungen auf Scripts, Release- und Runtime-Pfade pruefen.

## Qualitaet

- Relevante Tests laufen lassen und Ergebnis dokumentieren.
- Relevante Build-Schritte pruefen.
- Linter/Type-Checks pruefen, falls fuer Scope vorhanden.

## Sicherheit

- Secret-Scan ohne neue Funde.
- Keine unsicheren TLS-Bypasses ohne begruendete Ausnahme.
- Keine riskanten subprocess-Aufrufe (`shell=True`, string commands ohne Guards).

## Architektur und Kompatibilitaet

- Keine unbegruendete grosse Architekturverschiebung.
- Keine stillen Breaking Changes.
- Keine Fantasie-Abhaengigkeiten.
- Keine toten Dateien ohne Grund oder Migrationspfad.

## Policy-Checks

- Aenderung passt zu `.agents/roadmap.md`.
- Aenderung verletzt keine Eintraege aus `.agents/forbidden-actions.md`.
