---
name: auto-merge
description: Fuehrt konservativen Auto-Merge nur bei vollstaendig gruenen Checks und ohne Risikoflags aus.
---

# Auto Merge

## Ablauf

1. Verifiziere required checks und Review-Status.
2. Pruefe Labels (`do-not-merge`, `needs-human-review`, `dangerous-change`).
3. Pruefe Diff auf verbotene Aenderungen.
4. Merge per Squash (oder dokumentierter Repo-Konvention).
5. Nach Merge `main` validieren und Statusdateien aktualisieren.
