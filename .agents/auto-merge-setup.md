# Auto-Merge Setup (Owner Actions)

Diese Schritte muessen Repository-Owner einmalig in GitHub setzen:

1. Branch Protection fuer `main` aktivieren:
   - Require pull request before merging
   - Require status checks to pass before merging
   - Require branches to be up to date before merging
2. Als required checks mindestens aktivieren:
   - `pytest (Python 3.11)`
   - `pytest (Python 3.12)`
   - `bats (shell tests)`
   - `integration (Python)`
   - `WebUI provisioning smoke (Playwright)`
   - `shellcheck`, `mypy (type check — core/)`, `eslint (JS lint)`
   - Security-Checks aus den Security-Workflows
3. Repository setting "Allow auto-merge" aktivieren.
4. Secret `COPILOT_ASSIGNMENT_TOKEN` hinterlegen (wird von `copilot-autofix.yml` und `copilot-automerge.yml` genutzt).
5. Labels anlegen und im Betrieb nutzen:
   - `do-not-merge`
   - `needs-human-review`
   - `dangerous-change`

## Hinweis zum aktuellen Repo

Ein konservativer Auto-Merge-Pfad fuer Copilot-Branches existiert bereits (`.github/workflows/copilot-automerge.yml` + `scripts/merge-copilot-autofix-pr.sh`).

Wenn Auto-Merge fuer allgemeine Feature-Branches gewuenscht ist, muss ein zusaetzlicher Workflow eingefuehrt werden, der Label- und Diff-Sicherheitsregeln strikt prueft.
