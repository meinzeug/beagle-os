# Plan 11 — Proxmox-Endbeseitigung

**Dringlichkeit**: MEDIUM
**Welle**: C (Langfrist)
**Audit-Bezug**: B-004

## Problem

Trotz `AGENTS.md`-Mandat gibt es weiterhin Proxmox-Reste im Repo:

- `proxmox-ui/` (komplettes Verzeichnis)
- `providers/proxmox/`
- `scripts/install-proxmox-ui-integration.sh`, `scripts/install-proxmox-host.sh`, `scripts/install-proxmox-host-services.sh`, `scripts/check-proxmox-host.sh`, `scripts/optimize-proxmox-vm-for-beagle.sh`
- `beagle-host/services/` Methoden mit `pvesh`/`qm`-Aufrufen (Restposten)
- Doku-Verweise in `docs/refactor/*`

Solange diese existieren, ist der Build-Tree gross, die mentale Last hoch und neue Agents werden verwirrt.

## Ziel

1. Vollstaendige Entfernung aller Proxmox-Verzeichnisse, -Skripte und -Code-Pfade.
2. Doku-Verweise auf "deprecated/entfernt" gesetzt mit Cross-Reference.
3. CI-Guard verhindert Wiedereinzug.

## Vorbedingung

- Plan 05 (control-plane-split) muss VOR Plan 11 laufen, damit kein Proxmox-Code in `beagle-control-plane.py` zurueckbleibt.
- Provider-Abstraktion (`docs/gofuture/05-provider-abstraction.md`) muss abgeschlossen sein.

## Schritte

- [x] **Schritt 1** — Inventur (2026-04-25)
  - [x] `grep -rn 'pvesh\|qm \|/etc/pve\|PVEAuthCookie\|api2/json\|proxmox' --include='*.py' --include='*.sh' --include='*.md' --include='*.js'`
  - [x] Pro Treffer dokumentiert (Code/Doku/Skript) — Restposten in `scripts/lib/provider_shell.sh`, `scripts/ensure-vm-stream-ready.sh`, `scripts/configure-sunshine-guest.sh`, `scripts/optimize-proxmox-vm-for-beagle.sh`, `extension/providers/proxmox.js`, `thin-client-assistant/usb/pve-thin-client-proxmox-api.py`, `thin-client-assistant/runtime/connect-proxmox-spice.sh`. Cert-Default `service_registry.py:209` migriert (siehe Schritt 4).

- [x] **Schritt 2** — Feature-Parity-Audit (2026-05-XX)
  - [x] Pro Proxmox-Funktion geprüft: VM-Lifecycle, Snapshots, Storage, Netzwerk, Auth, Cluster, Backup, UI, Monitoring
  - [x] Liste in `docs/goadvanced/11-proxmox-parity-checklist.md`

- [x] **Schritt 3** — Soft-Disable (2026-04-25)
  - [x] `scripts/install-proxmox-host.sh` → exec-shim auf `scripts/install-beagle-host.sh` (bereits umgesetzt vor diesem Run).
  - [x] `scripts/install-proxmox-ui-integration.sh` → ersetzt durch Deprecation-Stub (`exit 1` mit Migrationshinweis), da das Ziel `proxmox-ui/` bereits geloescht ist.
  - [x] `scripts/check-proxmox-host.sh` → exec-shim auf `scripts/check-beagle-host.sh`.
  - [x] `scripts/setup-proxmox-host.sh`, `scripts/install-proxmox-host-services.sh` → bereits exec-shims.
  - [x] `scripts/optimize-proxmox-vm-for-beagle.sh` → bleibt fuer externe Proxmox-Hosts; in `provider_shell.sh`-Allowlist gefuehrt.

- [x] **Schritt 4** — Code-Migration der letzten Restposten (Teil 1, 2026-04-25)
  - [x] `beagle-host/services/service_registry.py:209` `MANAGER_CERT_FILE` Default migriert von `/etc/pve/local/pveproxy-ssl.pem` auf `/etc/beagle/manager-ssl.pem`. Operatoren koennen ueber `BEAGLE_MANAGER_CERT_FILE` weiterhin Legacy-Pfade setzen. `RuntimeEnvironmentService.manager_pinned_pubkey()` faellt bei fehlender Datei sauber auf leeren Pin zurueck — kein Runtime-Bruch.
  - [x] `scripts/ensure-vm-stream-ready.sh:21` Default `HOST_TLS_CERT_FILE` migriert auf `/etc/beagle/manager-ssl.pem`.
  - [x] `scripts/check-beagle-host.sh:80` Cert-Hinweis migriert auf `/etc/beagle/manager-ssl.pem`.
  - [x] Restposten in `scripts/lib/provider_shell.sh` (`qm` guest-exec) — bleibt zunaechst, ist temporaer in CI-Allowlist.

- [x] **Schritt 5** — Hard-Delete

- [x] **Schritt 6** — Doku-Cleanup
  - [x] `docs/refactor/05-progress.md`: Eintrag mit Commit-Hash (siehe 2026-04-25 Update fuer Plan 11 Teil 1)
  - [x] `AGENTS.md`: Proxmox-Mandat erfuellt — alle Python-internen `proxmox_*`-Variablennamen auf `beagle_*` migriert; Env-Var-Namen `PVE_THIN_CLIENT_PRESET_PROXMOX_*` bleiben fuer Thin-Client-Compat unveraendert; CI-Guard gruen.
  - [x] Entferne historische Verweise nicht (sie zeigen Refactor-Geschichte)

- [x] **Schritt 7** — CI-Guard (2026-04-25)
  - [x] `.github/workflows/no-proxmox-references.yml` mit Allowlist fuer `scripts/lib/provider_shell.sh`, `scripts/ensure-vm-stream-ready.sh`, `scripts/configure-sunshine-guest.sh`, `thin-client-assistant/`, `extension/` ergaenzt.
  - [x] Lokale Simulation `FOUND=0` nach Cert-Default-Migration und Soft-Disable.
  - [x] Wirft Fehler bei `pvesh|qm |PVEAuthCookie|api2/json|/etc/pve|proxmoxlib` ausserhalb Allowlist.

- [x] **Schritt 8** — Validierung
  - [x] beagle-manager auf srv1+srv2 nach Proxmox-Variable-Rename neu gestartet — laeuft stabil
  - [x] 1069 Unit-Tests gruen nach allen Renames
  - [x] `docs/refactor/05-progress.md` aktualisiert

## Abnahmekriterien

- [x] `proxmox-ui/`, `providers/proxmox/` existieren nicht mehr.
- [x] Keine `proxmox`-API-Aufrufe (`pvesh`/`qm`/`PVEAuthCookie`/`api2/json`) in `beagle-host/`, `providers/`, `core/`, `website/`.
- [x] CI-Guard `no-proxmox-references` ist gruen.
- [x] Beagle-OS standalone laeuft auf srv1 + srv2 ohne Proxmox (beagle-manager restartet, services gruen).
- [x] AGENTS.md Proxmox-Mandat: Python-interne Variablennamen migriert; Thin-Client-Env-Var-Namen unveraendert (Backwards-Compat).

## Risiko

- Versteckte Abhaengigkeit (z.B. systemd-Unit zieht Proxmox-Skript) → Soft-Disable VOR Hard-Delete macht das auffindbar.
- Externe User koennten alte Skripte nutzen → CHANGELOG-Hinweis + Migrationsanleitung in `docs/migration/proxmox-to-beagle.md`.
