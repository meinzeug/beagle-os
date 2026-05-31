# Security Policy

## Geheimnisse

- Keine Secrets in Repo-Dateien, Commit-Historie oder Logs.
- `.env` nur mit Platzhaltern; nie echte Werte.

## Transport/Kommunikation

- Keine neuen TLS-Bypasses ohne begruendete, dokumentierte Ausnahme.
- Netzwerk- und Auth-Aenderungen mit negativen Tests/Checks absichern.

## Prozess-/Command-Sicherheit

- Keine unkontrollierten `shell=True`-Aufrufe.
- Keine unvalidierten String-Kommandos in subprocess-Pfaden.

## Repo-spezifisch

- Security-Funde in `docs/refactor/11-security-findings.md` spiegeln.
- Vor Merge sicherstellen, dass Security-Workflows fuer den Scope nicht regressieren.
