# Integration Tests

GoAdvanced Plan 10 — Schritt 8.

## Übersicht

Die Integrations-Tests in `tests/integration/` testen geschäftskritische
Pfade **ohne HTTP-Server** und **ohne externe Abhängigkeiten** — nur mit
echten Service-Instanzen gegen temporäre Verzeichnisse.

| Modul                                | Testet                                       | Abhängigkeiten |
|--------------------------------------|----------------------------------------------|----------------|
| `test_pairing_lifecycle.py`          | Pairing-Token, Enrollment-Store, Endpoint-Store | stdlib only |
| `test_endpoint_boot_to_streaming.py` | Enrollment-Token-Lifecycle → Stream-Config   | stdlib only |
| `test_backup_restore_chain.py`       | Backup-Policy, run_backup_now, restore, file-listing | tar (system) |

## Lokal ausführen

```bash
cd beagle-host/services

# Alle Integration-Tests
BEAGLE_BEAGLE_PROVIDER_STATE_DIR=/tmp/beagle-test/providers \
PYTHONPATH=. \
python3 -m pytest ../../tests/integration/ -v

# Einzelnes Modul
BEAGLE_BEAGLE_PROVIDER_STATE_DIR=/tmp/beagle-test/providers \
PYTHONPATH=. \
python3 -m pytest ../../tests/integration/test_pairing_lifecycle.py -v
```

## Stubs und Testdesign

- **Keine Mocks** für Dateisystem — echte temporäre Verzeichnisse per `tmp_path` fixture.
- **Kein HTTP-Server** — Services werden direkt instanziiert und aufgerufen.
- **Dependency-Injection**: Alle Services akzeptieren callables als Parameter;
  Tests übergeben einfache Lambda-/Stub-Funktionen.
- **Backup-Tests**: `_TestBackupService` überschreibt `_run_backup_archive`
  um ein kontrolliertes temp-Verzeichnis statt `/etc/beagle` zu archivieren.

## Debuggen

Wenn ein Test fehlschlägt mit `tar: <path>: Cannot stat`:

```bash
# Prüfen ob tar verfügbar ist
which tar && tar --version | head -1
```

Wenn ein Test mit `ImportError` fehlschlägt, sicherstellen dass `PYTHONPATH`
auf `beagle-host/services` zeigt (oder das `cd`-Kommando im Root gestartet wird).

## CI-Integration

Integration-Tests laufen auf jedem PR automatisch (kein Token nötig).
E2E-Tests laufen nightly mit `BEAGLE_E2E_TOKEN` aus GitHub Secrets.
Deaktivierte Tests (GPU, mock-provider) werden per `--deselect` ausgeschlossen.
