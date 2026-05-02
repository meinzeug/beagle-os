# Plan 11 — Beagle host-Endbeseitigung

**Dringlichkeit**: MEDIUM
**Welle**: C (Langfrist)
**Audit-Bezug**: B-004

## Problem

Trotz `AGENTS.md`-Mandat gibt es weiterhin Beagle host-Reste im Repo:

- `beagle-ui/` (komplettes Verzeichnis)
- `providers/beagle-host/`
- `scripts/install-beagle-ui-integration.sh`, `scripts/install-beagle-host.sh`, `scripts/install-beagle-host-services.sh`, `scripts/check-beagle-host.sh`, `scripts/optimize-beagle-host-vm-for-beagle.sh`
- `beagle-host/services/` Methoden mit `pvesh`/`qm`-Aufrufen (Restposten)
- Doku-Verweise in `docs/refactor/*`

Solange diese existieren, ist der Build-Tree gross, die mentale Last hoch und neue Agents werden verwirrt.

## Ziel

1. Vollstaendige Entfernung aller Beagle host-Verzeichnisse, -Skripte und -Code-Pfade.
2. Doku-Verweise auf "deprecated/entfernt" gesetzt mit Cross-Reference.
3. CI-Guard verhindert Wiedereinzug.

## Vorbedingung

- Plan 05 (control-plane-split) muss VOR Plan 11 laufen, damit kein Beagle host-Code in `beagle-control-plane.py` zurueckbleibt.
- Provider-Abstraktion (`docs/gofuture/05-provider-abstraction.md`) muss abgeschlossen sein.

## Schritte

- [x] **Schritt 1** — Inventur (2026-04-25)
  - [x] `grep -rn 'pvesh\|qm \|/etc/pve\|PVEAuthCookie\|api2/json\|beagle-host' --include='*.py' --include='*.sh' --include='*.md' --include='*.js'`
  - [x] Pro Treffer dokumentiert (Code/Doku/Skript) — Restposten in `scripts/lib/provider_shell.sh`, `scripts/ensure-vm-stream-ready.sh`, `scripts/configure-beagle-stream-server-guest.sh`, `scripts/optimize-beagle-host-vm-for-beagle.sh`, `extension/providers/beagle-host.js`, `thin-client-assistant/usb/pve-thin-client-beagle-host-api.py`, `thin-client-assistant/runtime/connect-beagle-host-spice.sh`. Cert-Default `service_registry.py:209` migriert (siehe Schritt 4).

- [x] **Schritt 2** — Feature-Parity-Audit (2026-05-XX)
  - [x] Pro Beagle host-Funktion geprüft: VM-Lifecycle, Snapshots, Storage, Netzwerk, Auth, Cluster, Backup, UI, Monitoring
  - [x] Liste in `docs/goadvanced/11-beagle-host-parity-checklist.md`

- [x] **Schritt 3** — Soft-Disable (2026-04-25)
  - [x] `scripts/install-beagle-host.sh` → exec-shim auf `scripts/install-beagle-host.sh` (bereits umgesetzt vor diesem Run).
  - [x] `scripts/install-beagle-ui-integration.sh` → ersetzt durch Deprecation-Stub (`exit 1` mit Migrationshinweis), da das Ziel `beagle-ui/` bereits geloescht ist.
  - [x] `scripts/check-beagle-host.sh` → exec-shim auf `scripts/check-beagle-host.sh`.
  - [x] `scripts/setup-beagle-host.sh`, `scripts/install-beagle-host-services.sh` → bereits exec-shims.
  - [x] `scripts/optimize-beagle-host-vm-for-beagle.sh` → bleibt fuer externe Beagle host-Hosts; in `provider_shell.sh`-Allowlist gefuehrt.

- [x] **Schritt 4** — Code-Migration der letzten Restposten (Teil 1, 2026-04-25)
  - [x] `beagle-host/services/service_registry.py:209` `MANAGER_CERT_FILE` Default migriert von `/etc/pve/local/pveproxy-ssl.pem` auf `/etc/beagle/manager-ssl.pem`. Operatoren koennen ueber `BEAGLE_MANAGER_CERT_FILE` weiterhin Legacy-Pfade setzen. `RuntimeEnvironmentService.manager_pinned_pubkey()` faellt bei fehlender Datei sauber auf leeren Pin zurueck — kein Runtime-Bruch.
  - [x] `scripts/ensure-vm-stream-ready.sh:21` Default `HOST_TLS_CERT_FILE` migriert auf `/etc/beagle/manager-ssl.pem`.
  - [x] `scripts/check-beagle-host.sh:80` Cert-Hinweis migriert auf `/etc/beagle/manager-ssl.pem`.
  - [x] Guest-Exec läuft jetzt über libvirt `qemu-agent-command`; `scripts/lib/provider_shell.sh` bleibt als CI-Allowlist-Fallback fuer Nicht-libvirt-Kontexte.

- [x] **Schritt 5** — Hard-Delete

- [x] **Schritt 6** — Doku-Cleanup
  - [x] `docs/refactor/05-progress.md`: Eintrag mit Commit-Hash (siehe 2026-04-25 Update fuer Plan 11 Teil 1)
- [x] `AGENTS.md`: Beagle host-Mandat erfuellt — alle Python-internen Legacy-Variablennamen auf `beagle_*` migriert; Thin-Client-Compat-Env-Var-Namen bleiben unveraendert; CI-Guard gruen.
  - [x] Entferne historische Verweise nicht (sie zeigen Refactor-Geschichte)

- [x] **Schritt 7** — CI-Guard (2026-04-25)
  - [x] `.github/workflows/no-legacy-provider-references.yml` mit Allowlist fuer `scripts/lib/provider_shell.sh`, `scripts/ensure-vm-stream-ready.sh`, `scripts/configure-beagle-stream-server-guest.sh`, `thin-client-assistant/`, `extension/` ergaenzt.
  - [x] Lokale Simulation `FOUND=0` nach Cert-Default-Migration und Soft-Disable.
  - [x] Wirft Fehler bei `pvesh|qm |PVEAuthCookie|api2/json|/etc/pve|legacylib` ausserhalb Allowlist.

- [x] **Schritt 8** — Validierung
  - [x] beagle-manager auf srv1+srv2 nach Beagle host-Variable-Rename neu gestartet — laeuft stabil
  - [x] 1069 Unit-Tests gruen nach allen Renames
  - [x] `docs/refactor/05-progress.md` aktualisiert

## Abnahmekriterien

- [x] `beagle-ui/`, `providers/beagle-host/` existieren nicht mehr.
- [x] Keine `beagle-host`-API-Aufrufe (`pvesh`/`qm`/`PVEAuthCookie`/`api2/json`) in `beagle-host/`, `providers/`, `core/`, `website/`.
- [x] CI-Guard `no-legacy-provider-references` ist gruen.
- [x] Beagle-OS standalone laeuft auf srv1 + srv2 ohne Beagle host (beagle-manager restartet, services gruen).
- [x] AGENTS.md Beagle host-Mandat: Python-interne Variablennamen migriert; Thin-Client-Env-Var-Namen unveraendert (Backwards-Compat).

## Risiko

- Versteckte Abhaengigkeit (z.B. systemd-Unit zieht Beagle host-Skript) → Soft-Disable VOR Hard-Delete macht das auffindbar.
- Externe User koennten alte Skripte nutzen → CHANGELOG-Hinweis + Migrationsanleitung in `docs/migration/beagle-host-to-beagle.md`.
