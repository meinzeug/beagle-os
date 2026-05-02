# Plan 10 — Integrations- und E2E-Tests

**Dringlichkeit**: HIGH
**Welle**: B (Mittelfrist)
**Audit-Bezug**: C-001

## Problem

Es gibt aktuell 643 Unit-Tests, aber **keine Integrations- oder End-to-End-Tests** fuer die geschaeftskritischen Pfade:

- Endpoint-Boot → Enrollment → Streaming-Session
- Backup → Restore (Datenintegritaet)
- HA-Failover (Cluster: Node down → VM auf anderer Node automatisch hoch)
- VDI-Pool: Template → Klon → Stream → Cleanup
- Pairing → Token-Rotation → Revocation

Bei Refactor (z.B. Plan 05 control-plane-split) waere ein vollstaendiges Regressions-Sicherheitsnetz noetig.

## Ziel

1. Integrations-Test-Suite in `tests/integration/` mit echten Komponenten gegen Mocks/Stubs.
2. E2E-Test-Suite in `tests/e2e/` gegen `srv1.beagle-os.com` (live).
3. Tests laufen automatisch auf jedem PR (Integration) bzw. nightly (E2E).

## Schritte

- [x] **Schritt 1** — Test-Infrastruktur
  - [x] `tests/integration/conftest.py`:
    - Fixtures: `temp_state_dir`, `mock_libvirt`, `mock_audit_log`, `test_http_client`
    - Stub fuer `virsh` (gibt vordefinierte XMLs zurueck)
    - Stub fuer `tpm2_pcrread`
  - [x] `tests/e2e/conftest.py`:
    - Fixture: `srv1_client` mit Bearer-Token aus Env-Var (NICHT committet)
    - Fixture: `srv1_test_vmid` (ephemere Test-VM, automatischer Cleanup)

- [x] **Schritt 2** — Endpoint-Boot-to-Streaming
  - [x] `tests/integration/test_endpoint_boot_to_streaming.py`:
    - Simulierter Endpoint registriert sich via Pairing-Token
    - Empfaengt Stream-Konfiguration
    - Faellt zurueck auf Fallback-Channel bei Stream-Failure
    - Reconnects nach Token-Rotation
  - [x] Stubs fuer Beagle Stream Server + Beagle Stream Client (Mock-Process)

- [x] **Schritt 3** — Backup → Restore
  - [x] `tests/integration/test_backup_restore_chain.py`:
    - Erzeuge VM mit Test-Disk + Snapshot
    - `backup_service.create()` → Archiv in temp_dir
    - `backup_service.restore()` in neuen Pool
    - Vergleiche Disk-Hash + VM-Config
  - [x] Edge-Cases: korruptes Archiv, fehlende Files, Disk-Full

- [x] **Schritt 4** — HA-Failover
  - [x] `tests/integration/test_ha_failover.py`:
    - 2-Node-Cluster (mock libvirt)
    - VM auf Node A
    - Simuliere Node-A-Ausfall (Heartbeat-Timeout)
    - Erwarte: VM startet auf Node B innerhalb T_max
    - Fencing-Trigger gepruefte
  - [x] Vorbedingung: HA-Manager existiert (siehe `docs/gofuture/09-ha-manager.md`)

- [x] **Schritt 5** — VDI-Pool-Lifecycle
  - [x] `tests/integration/test_vdi_pool_lifecycle.py`:
    - Template-VM erstellen
    - Pool mit min=2 max=5 anlegen
    - 3 Sessions claimen → 3 Klone aktiv
    - Sessions schliessen → Klone werden recycled
    - Quotas: 6. Session → wird abgewiesen mit klarer Fehlermeldung

- [x] **Schritt 6** — Pairing-Lifecycle
  - [x] `tests/integration/test_pairing_lifecycle.py`:
    - Pairing-Token generieren (TTL 60s)
    - Endpoint paart sich → langlebiger Bearer-Token
    - Token-Rotation (alter Token wird ungueltig)
    - Revocation → Token sofort ungueltig

- [x] **Schritt 7** — E2E gegen srv1
  - [x] `tests/e2e/test_smoke_srv1.py`:
    - `GET /api/v1/health` → healthy
    - `GET /api/v1/vms` → Liste
    - VM-Lifecycle: create → start → snapshot → delete
    - Cleanup-Hook: alle Test-Artefakte loeschen
  - [x] Nightly-Cron in CI (mit Secret BEARER_TOKEN)

- [x] **Schritt 8** — Doku
  - [x] `tests/integration/README.md`: Wie laufen lokal, welche Stubs, wie debuggen
  - [x] `tests/e2e/README.md`: Voraussetzungen (BEARER_TOKEN), Cleanup-Verhalten

## Abnahmekriterien

- [x] Mind. 6 Integrations-Test-Module produktiv.
- [ ] Mind. 1 E2E-Test laeuft nightly gegen srv1.
- [ ] Integrations-Tests laufen auf PR (in CI).
- [ ] Test-Coverage fuer kritische Pfade dokumentiert.
- [ ] Cleanup-Hooks verlassen srv1 in sauberem Zustand.

## Risiko

- E2E-Tests koennen srv1-Stabilitaet beeintraechtigen → striktes Cleanup, separater Test-Pool
- Integrations-Tests mit Mock-libvirt koennen reale Bugs verstecken → mind. 1 E2E pro Pfad zur Validierung
- Test-Daten muessen reproduzierbar sein → Seeds + deterministische UUIDs
