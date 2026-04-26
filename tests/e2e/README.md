# E2E Tests

GoAdvanced Plan 10 — Schritt 7 + 8.

## Übersicht

Die E2E-Tests in `tests/e2e/` laufen gegen einen **live Beagle-Host** (srv1/srv2).
Sie sind automatisch deaktiviert wenn `BEAGLE_E2E_TOKEN` nicht gesetzt ist.

| Modul                  | Testet                                      |
|------------------------|---------------------------------------------|
| `test_smoke_srv1.py`   | Health, VM-List, Auth, Jobs, VM-Lifecycle   |

## Voraussetzungen

```bash
export BEAGLE_E2E_URL=https://srv1.beagle-os.com:8443
export BEAGLE_E2E_TOKEN=<admin-bearer-token>

# Optional: self-signed Zertifikat ignorieren
export BEAGLE_E2E_INSECURE=1

# Optional: VM-Create/Delete-Tests überspringen
export BEAGLE_E2E_SKIP_MUTATING=1
```

**Wichtig**: `BEAGLE_E2E_TOKEN` darf niemals committed werden.
Lokale `.env`-Dateien sind in `.gitignore` gelistet.
CI nutzt GitHub Secrets (`secrets.BEAGLE_E2E_TOKEN`).

## Lokal ausführen

```bash
cd beagle-host/services

BEAGLE_BEAGLE_PROVIDER_STATE_DIR=/tmp/beagle-test/providers \
BEAGLE_E2E_URL=https://srv1.beagle-os.com:8443 \
BEAGLE_E2E_TOKEN=<token> \
PYTHONPATH=. \
python3 -m pytest ../../tests/e2e/ -v
```

## Cleanup-Verhalten

Mutating-Tests (VM-Lifecycle) nutzen die `e2e_cleanup_vms`-Fixture.
Diese löscht alle erstellten Test-VMs **unconditionally** am Testende —
auch bei Fehlern. Test-VMs haben den Prefix `beagle-e2e-smoke-`.

Manuelle Bereinigung nach abgebrochenem Test:

```bash
# Liste aller Test-VMs
curl -H "Authorization: Bearer $BEAGLE_E2E_TOKEN" \
  "$BEAGLE_E2E_URL/api/v1/vms" | jq '[.[] | select(.name | startswith("beagle-e2e-smoke-"))]'
```

## Nightly CI

```yaml
# .github/workflows/e2e-nightly.yml (Beispiel)
env:
  BEAGLE_E2E_URL: https://srv1.beagle-os.com:8443
  BEAGLE_E2E_TOKEN: ${{ secrets.BEAGLE_E2E_TOKEN }}
  BEAGLE_E2E_INSECURE: "1"
```
