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

- [ ] **Schritt 1** — Inventur
  - [ ] `grep -rn 'pvesh\|qm \|/etc/pve\|PVEAuthCookie\|api2/json\|proxmox' --include='*.py' --include='*.sh' --include='*.md' --include='*.js'`
  - [ ] Pro Treffer: dokumentieren in `docs/goadvanced/11-proxmox-inventar.md`
    - Spalten: Datei, Zeile, Typ (Code/Doku/Skript), Aktion (loeschen / migrieren / als historisch markieren)

- [ ] **Schritt 2** — Feature-Parity-Audit
  - [ ] Pro Proxmox-Funktion pruefen:
    - Existiert Aequivalent in `providers/beagle/`?
    - Wenn nein → Migration ist Vorbedingung (Issue oeffnen)
  - [ ] Liste in `docs/goadvanced/11-proxmox-parity-checklist.md`

- [ ] **Schritt 3** — Soft-Disable
  - [ ] `scripts/install-proxmox-host.sh` → echo "DEPRECATED: use scripts/install-beagle-host.sh"; exit 1
  - [ ] `scripts/install-proxmox-ui-integration.sh` → analog
  - [ ] `scripts/check-proxmox-host.sh` → analog
  - [ ] `scripts/optimize-proxmox-vm-for-beagle.sh` → analog
  - [ ] Falls in systemd-Units referenziert: Units anpassen / entfernen
  - [ ] Doku in `docs/refactor/03-refactor-plan.md` aktualisieren

- [ ] **Schritt 4** — Code-Migration der letzten Restposten
  - [ ] `beagle-host/services/`: alle `pvesh`/`qm`-Aufrufe identifizieren und auf `providers/beagle/` umstellen
  - [ ] Falls Funktion nicht migrierbar → Tracking-Issue oeffnen, in `docs/goadvanced/11-proxmox-rest-issues.md`

- [ ] **Schritt 5** — Hard-Delete
  - [ ] `git rm -r proxmox-ui/`
  - [ ] `git rm -r providers/proxmox/`
  - [ ] `git rm scripts/install-proxmox-*.sh scripts/check-proxmox-host.sh scripts/optimize-proxmox-vm-for-beagle.sh`
  - [ ] systemd-Unit-Dateien fuer Proxmox-Bezogenes entfernen
  - [ ] Tests, die Proxmox-Mocks nutzen, entfernen oder migrieren

- [ ] **Schritt 6** — Doku-Cleanup
  - [ ] `docs/refactor/03-refactor-plan.md`: "Proxmox vollstaendig entfernt am YYYY-MM-DD"
  - [ ] `docs/refactor/05-progress.md`: Eintrag mit Commit-Hash
  - [ ] `AGENTS.md`: "Status: Proxmox-Mandat erfuellt"
  - [ ] Entferne historische Verweise nicht (sie zeigen Refactor-Geschichte) — markiere mit "[entfernt 2026-XX-XX]"

- [ ] **Schritt 7** — CI-Guard
  - [ ] `.github/workflows/no-proxmox-references.yml` (siehe Plan 09)
  - [ ] Wirft Fehler bei `pvesh|qm |PVEAuthCookie|api2/json|/etc/pve|proxmox-ui` ausserhalb `docs/refactor/` und `CHANGELOG.md`

- [ ] **Schritt 8** — Validierung
  - [ ] Frischer Clone + `scripts/install-beagle-host.sh` auf srv2 → Beagle-OS-only Stack laeuft
  - [ ] ISO-Build auf srv1 → kein Proxmox-Code im Image
  - [ ] `docs/refactor/05-progress.md` aktualisiert mit Validierungs-Datum

## Abnahmekriterien

- [ ] `proxmox-ui/`, `providers/proxmox/` existieren nicht mehr.
- [ ] Keine `proxmox`-Referenzen in `beagle-host/`, `providers/`, `core/`, `scripts/`, `website/`.
- [ ] CI-Guard `no-proxmox-references` ist gruen.
- [ ] Beagle-OS standalone laeuft auf srv1 + srv2 ohne Proxmox.
- [ ] AGENTS.md aktualisiert.

## Risiko

- Versteckte Abhaengigkeit (z.B. systemd-Unit zieht Proxmox-Skript) → Soft-Disable VOR Hard-Delete macht das auffindbar.
- Externe User koennten alte Skripte nutzen → CHANGELOG-Hinweis + Migrationsanleitung in `docs/migration/proxmox-to-beagle.md`.
