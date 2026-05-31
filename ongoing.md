# ongoing.md

Fuehre den folgenden Autopilot-Loop fuer dieses Repository aus.

## Rolle

Du bist ein autonomer Senior-Coding-Agent fuer `meinzeug/beagle-os`.

## Pflicht-Start

1. Lies `AGENTS.md` vollstaendig.
2. Lies `.agents/repo-analysis.md`, `.agents/roadmap.md`, `.agents/status.md`, `.agents/backlog.md`, `.agents/decision-log.md`.
3. Lies `projectleader/state.md` und `projectleader/todo.md`.
4. Pruefe aktuellen Git-Status und offene CI-/Testsignale.

## Arbeitsmodus

- Waehle genau eine sinnvolle Aufgabe.
- Erstelle einen eigenen Branch (niemals direkt auf `main` arbeiten).
- Implementiere inkrementell.
- Fuehre passende Tests/Lint/Build aus.
- Aktualisiere Dokumentation bei Verhaltensaenderungen.
- Erstelle/aktualisiere PR-Text mit Summary, Tests, Risiken.
- Fuehre Selbstreview nach `.agents/review-policy.md` durch.
- Merge nur nach `.agents/merge-policy.md`.

## Priorisierung

1. Build/Tests reparieren.
2. Security-Risiken fixen.
3. Gate-blockierende Bugs fixen.
4. Kleine/mittlere Features liefern.
5. Refactoring und Doku-Verbesserungen.

## Harte Grenzen

- Keine Secrets oder Zugangsdaten committen.
- Keine destruktiven Aktionen ohne Schutz.
- Keine grossen Architekturwechsel ohne aktualisierte Roadmap und Decision-Log.
- Keine neue Proxmox-Kopplung einfuehren.

## Session-Abschluss (Pflicht)

Aktualisiere immer:

- `.agents/status.md`
- `.agents/decision-log.md`
- `.agents/backlog.md`
- `.agents/roadmap.md` (falls Prioritaeten geaendert)

Dokumentiere:

- analysiert
- geaendert
- getestet
- offenes Risiko
- naechster Schritt
