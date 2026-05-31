---
name: pr-review
description: Fuehrt eine strenge, autonome PR-Selbstpruefung nach Policy durch.
---

# PR Review

## Ablauf

1. Vollstaendigen Diff lesen.
2. Geaenderte Dateien und relevante Aufrufer voll lesen.
3. Test-/Build-/Lint-Ergebnisse pruefen.
4. Security- und Secret-Risiken explizit abpruefen.
5. Merge-Freigabe nur bei Erfuellung von `.agents/review-policy.md` und `.agents/merge-policy.md`.
