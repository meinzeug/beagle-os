# Autonomous Development Loop

1. Repository aktualisieren (`git fetch`, Branch-Status pruefen).
2. `.agents/status.md`, `.agents/repo-analysis.md`, `.agents/roadmap.md` lesen.
3. CI-Status und offene Fehler pruefen.
4. Priorisierung anwenden:
   - Build/Tests kaputt
   - Security-Probleme
   - Gate-blockierende Bugs
   - kleine/mittlere Verbesserungen
5. Genau eine umsetzbare Aufgabe auswaehlen.
6. Branch erstellen (nie direkt auf `main` arbeiten).
7. Inkrementell implementieren.
8. Relevante Tests/Linter/Build laufen lassen.
9. Doku/Runbooks/Policies aktualisieren.
10. PR erstellen.
11. PR nach `.agents/review-policy.md` vollstaendig selbst pruefen.
12. Merge nur nach `.agents/merge-policy.md` und gruenen Checks.
13. Nach Merge `main` erneut ziehen und verifizieren.
14. `.agents/status.md`, `.agents/decision-log.md`, `.agents/backlog.md`, optional `.agents/roadmap.md` aktualisieren.
15. Naechsten Schritt konkret vormerken.
