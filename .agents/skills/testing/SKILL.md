---
name: testing
description: Erweitert und stabilisiert Tests fuer Unit, Integration, Bats und E2E in Beagle OS.
---

# Testing

## Ablauf

1. Betroffenen Layer bestimmen (`tests/unit`, `tests/integration`, `tests/bats`, `tests/e2e`).
2. Realistische Regressionsfaelle aus Fehlerbild oder Feature ableiten.
3. Tests deterministisch halten (keine zufaelligen Timeouts ohne Guards).
4. CI-Impact pruefen und dokumentieren.
5. Testluecken in `.agents/backlog.md` erfassen.
