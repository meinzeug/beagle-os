# Coding Standards

## Allgemein

- Kleine, inkrementelle Commits mit klarer Intention.
- Bestehende Stilkonvention pro Teilprojekt respektieren.
- Oeffentliche API/CLI nur mit Kompatibilitaetspruefung aendern.

## Python

- Lesbare Funktionsgrenzen, fruehes Validieren von Inputs.
- Typisierung dort, wo der Code bereits typisiert ist.
- Neue Risiken mit Unit-/Integrationstests absichern.

## Shell

- `set -euo pipefail` fuer neue Skripte.
- Quoting und Exit-Code-Behandlung sauber halten.
- Keine ungesicherten eval-/command-injection-Muster.

## JS/Node

- Keine unnoetigen globalen Nebeneffekte.
- Fehlerpfade fuer UI-Automation und Deploy-Skripte robust behandeln.

## Doku

- Operative Doku muss reproduzierbar und hostnah sein.
- Kein geheimes oder nicht verifizierbares Wissen in Doku schreiben.
