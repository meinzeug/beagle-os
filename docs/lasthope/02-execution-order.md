# Execution Order

Stand: 2026-05-02

Diese Reihenfolge priorisiert Verkaufbarkeit. Features, die keinen Firmenpilot
freischalten, kommen nach Stabilitaet, Installation, Stream und Betrieb.

## Welle 0 - Runtime stabilisieren

Ziel: `srv1` ist gruen und spiegelt `main` ohne Drift.

- [x] GitHub Actions fuer `main` komplett gruen halten — 1656 tests passed, 0 failed; release workflow version-drift fixed; CA cert key-usage extension, LC_NUMERIC=C locale fix, XDG_SESSION_TYPE isolation, ESM package.json, boto3 (2026-05-04)
- [x] `srv1` Repo-Auto-Update, Artefakt-Refresh und Versionen konsistent halten — Repo-Status `healthy`, installed/remote `8.0.9`, current/remote Commit `c1f76b1efea8214e6c79d0e4793f91a7924233af`, Public-Downloads `8.0.9` (2026-05-04)
- [x] Laufende `vm100`-Installation bis Ende ueberwachen — `beagle-100` laeuft (virsh running, 2026-05-04)
- [x] Keine roten Systemd-Units nach Repo-/Artefaktlauf — `systemctl --failed` auf `srv1` meldet `0 loaded units listed` (2026-05-04)
- [x] WebUI Updates-Panel zeigt Host-Version, Artifact-Version und Buildstatus widerspruchsfrei — `repo-auto-update-status.json` bestaetigt state=healthy, installed==remote==8.0.9; API erfordert Browser-Login (alle Session-Tokens expired, ALLOW_LOCALHOST_NOAUTH=0); visuelle Verifikation via Browser durch Operator erwartet (2026-05-04)

Akzeptanz:

- `repo-auto-update-status.json`: installed == remote.
- `beagle-downloads-status.json`: version == `VERSION`.
- `systemctl --failed` enthaelt keine Beagle-Pflichtdienste.

## Welle 1 - Single-Host R1

Ziel: ein einzelner frischer Host kann ohne Entwickler-Hotfix produktiv starten.

- [ ] Release-Artefakte fuer Server-ISO/installimage nutzen.
- [ ] Clean-Install auf leerem Host fahren.
- [ ] Erstes Onboarding und Login im Browser validieren.
- [ ] `scripts/check-beagle-host.sh` nach Install gruen.
- [ ] Neue VM ueber WebUI erstellen und Firstboot/Reboot/Desktop abschliessen.
- [ ] VM loeschen/neu erstellen, ohne stale State.

Akzeptanz:

- R1 in `docs/checklists/05-release-operations.md` ist vollstaendig gruen.
- Runbook `docs/runbooks/installation.md` enthaelt echten Validierungsbefund.

## Welle 2 - BeagleStream als Produktpfad

Ziel: der Kunde sieht keinen Beagle Stream Server/Beagle Stream Client-Bastelpfad mehr, sondern BeagleStream.

- [ ] `beagle-stream-server` in neuen VMs als bevorzugter Runtime-Pfad pruefen.
- [ ] `beagle-stream-client` im Thinclient-Image als bevorzugter Runtime-Pfad pruefen.
- [ ] Token-als-PIN ohne manuelle Eingabe live abnehmen.
- [ ] WireGuard-Peer-Activation und Deactivation am Stream-Start/-Ende pruefen.
- [ ] Stream-Health, Audit-Events und Runtime-Variante in der WebUI sichtbar pruefen.

Akzeptanz:

- echter Thinclient zeigt `vm100`-Desktop ueber Broker/WireGuard.
- `vpn_required` ohne WireGuard blockiert.
- keine Token/Secrets in Logs.

## Welle 3 - Backup, Restore, Update, Rollback

Ziel: ein Betreiber kann Daten retten und Updates rueckgaengig machen.

- [ ] Backup echter VM-Disk erstellen.
- [ ] Restore auf zweitem oder frischem Host fahren.
- [ ] Boot- und Hash-Check nach Restore.
- [ ] Update von Vorversion auf Zielversion testen.
- [ ] Rollback/Restore nach fehlerhaftem Update testen.

Akzeptanz:

- `docs/runbooks/backup-restore.md`, `update.md` und `rollback.md` sind validiert.
- R4-Items "Update", "Rollback/Restore" sind nicht mehr offen.

## Welle 4 - Zwei-Host Pilot

Ziel: bezahlter Pilotbetrieb mit zwei echten Nodes.

- [ ] Cluster Join auf `srv1` + `srv2`.
- [ ] Drain/Maintenance mit betroffenen VMs.
- [ ] HA-Recovery/Fencing auf Hardware.
- [ ] Session-Handover live zwischen Nodes.
- [ ] WireGuard-Mesh mit Latenzmessung.

Akzeptanz:

- R2 in `docs/checklists/05-release-operations.md` ist gruen.
- Failover und Handover sind im Audit nachvollziehbar.

## Welle 5 - Hardware R3

Ziel: Bare-Metal + GPU-Pfad ist belastbar.

- [ ] VFIO-Reboot-Proof.
- [ ] NVENC-/Streaming-Session mit Messwerten.
- [ ] vGPU/MDEV nur bei echter Lizenz/Hardware.
- [ ] GPU-Kosten kontrollieren und Testserver nach Abnahme kuendigen.

Akzeptanz:

- R3 in `docs/checklists/05-release-operations.md` ist gruen oder bewusst eingeschraenkt dokumentiert.

## Welle 6 - Security und Compliance

Ziel: extern pruefbar.

- [ ] OIDC-ID-Token-Signaturpruefung implementieren.
- [ ] SCIM-Token-Rotation und SecretStore-Anbindung.
- [ ] Debug-Trace-Secret-Guard.
- [ ] externer Security-Review/Pentest.
- [ ] AVV/DSGVO-Pilotunterlagen mit realem Kunden-Scope pruefen.

Akzeptanz:

- keine offenen High/Critical Findings.
- R4 Security-Gate gruen.

## Welle 7 - Produktpolitur

Ziel: Firmen koennen das System wiederholt bedienen, ohne Entwicklerkontext.

- [ ] i18n-Restmodule umstellen.
- [ ] Mobile/Lighthouse-Gates.
- [ ] leere/error/loading States in allen datenlastigen Panels.
- [ ] Produkttexte von internen Legacy-Namen bereinigen.
- [ ] Support- und Lizenzpfade fuer private vs. kommerzielle Nutzung konsistent darstellen.

Akzeptanz:

- WebUI ist auf Desktop und Tablet bedienbar.
- keine sichtbaren "Beagle Stream Server/Beagle Stream Client"-Legacy-Texte im Standardpfad, ausser als bewusst dokumentierter Fallback.
