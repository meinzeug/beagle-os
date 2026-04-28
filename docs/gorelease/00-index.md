# GoRelease - Enterprise-GA und Security-Freigabe

Stand: 2026-04-27  
Status: neuer Freigabeplan, ersetzt **nicht** `docs/goenterprise/`  
Ziel: Beagle OS erst dann als firmentauglich anbieten, wenn Security, Betrieb, Release-Artefakte und Hardware-Abnahmen reproduzierbar gruen sind.

---

## Zweck

`docs/goenterprise/` bleibt die Feature- und Architekturquelle. Dort steht, wie Enterprise-Funktionen gebaut sind.

`docs/gorelease/` ist die harte Freigabeschicht darueber. Hier steht, welche Gates bestanden sein muessen, bevor Beagle OS als sichere Unternehmensplattform verkauft oder produktiv betrieben wird.

Die zentrale Regel lautet:

> Kein Enterprise-GA ohne reproduzierbare Security-Gates, Clean-Install-Gates, Update-/Rollback-Gates, Runtime-Smokes und dokumentierte Hardware-Abnahme.

---

## Release-Stufen

| Stufe | Name | Aussage | Firmenangebot |
|---|---|---|---|
| R0 | Dev Build | Build laeuft lokal, keine Betriebszusage | Nein |
| R1 | Lab Green | Unit/CI gruen, Basis-Smokes gruen | Nein |
| R2 | Controlled Pilot | Dedizierte Pilotumgebung, bekannte Risiken dokumentiert | Ja, nur Pilot |
| R3 | Enterprise Candidate | Security-/Runtime-/Update-Gates gruen, Runbooks vorhanden | Ja, begrenzt |
| R4 | Enterprise GA | Externe Security-Pruefung, SLA-Prozess, Upgrade-/Rollback-Kette bewiesen | Ja, produktiv |

Aktueller Stand am 2026-04-27: Ziel ist `R2 -> R3`. `R4` ist noch nicht erreicht.

---

## Plan-Uebersicht

| Datei | Thema | Muss fuer |
|---|---|---|
| [01-security-gates.md](01-security-gates.md) | Auth, Tokens, TLS, Secrets, RBAC, Streaming, Audit, Hardening | R3/R4 |
| [02-hardware-test-matrix.md](02-hardware-test-matrix.md) | benoetigte Testhardware, kleine VMs, dedizierte Hosts, GPU-Zeitfenster | R2/R3/R4 |
| [03-end-to-end-validation.md](03-end-to-end-validation.md) | Clean install, WebUI, USB, Thin Client, VM, Backup, Cluster, GPU | R3/R4 |
| [04-release-pipeline.md](04-release-pipeline.md) | GitHub Release, SBOM, Signaturen, Checksummen, Self-Heal, Rollback | R3/R4 |
| [05-operations-compliance.md](05-operations-compliance.md) | Monitoring, Runbooks, Datenschutz, Incident Response, Pilotvertrag | R3/R4 |

---

## Nicht verhandelbare Gates

- [ ] `latest` GitHub Release zeigt auf die aktuelle Zielversion, nicht auf alte `6.x`-Artefakte.
- [ ] Alle Release-Artefakte haben Checksummen, SBOM und optional Signaturen.
- [ ] Frischer Server aus ISO/Installimage bootet selbststaendig und erreicht WebUI + Control Plane.
- [ ] Repo-Auto-Update heilt sich selbst, ohne Symlink-/Ownership-/Status-Drift.
- [ ] Oeffentliche Download-Skripte enthalten keine Admin- oder Manager-Credentials.
- [ ] Keine Download- oder Runtime-URL verweist auf `8443`.
- [ ] Login, Session Refresh, Logout und RBAC sind browserseitig und API-seitig abgenommen.
- [ ] noVNC-/Console-Tokens haben TTL, Scope und Audit-Nachweis.
- [ ] Streaming laeuft fuer Enterprise-Piloten verschluesselt oder ueber dokumentierten Zero-Trust-Pfad.
- [ ] Backup und Restore wurden auf echter VM-Disk nachgewiesen.
- [ ] Clean-Install, Update, Rollback und Disaster-Recovery sind als Runbook dokumentiert und getestet.

---

## Hardware-Grundsatz

Nicht jedes Gate braucht teure Hardware. Standardregel:

- Kleine 2-4 Core VMs bei Hetzner reichen fuer Control Plane, WebUI, Auth, Update, Release-Downloads, API, CI-Smokes und Zwei-Node-Logik ohne echte Nested-KVM-Anforderung.
- Dedizierte CPU-Server werden nur fuer KVM/libvirt, ISO-Install, VM-Provisioning, Storage, Backup/Restore und echte Thin-Client-Flows benoetigt.
- GPU-Server werden nur fuer GPU-Passthrough, vGPU/MDEV, NVENC/Streaming und Gaming-Pool-Abnahmen gebucht.
- GPU-Hardware wird stundenweise oder kurzfristig gemietet, z.B. GPU-Server aus Serverboerse/Server-Auktion oder anderer GPU-Rental-Anbieter. Wenn nur Monatsmiete verfuegbar ist, wird vorher ein 4-8h Testfensterplan erstellt und danach gekuendigt.

Details stehen in [02-hardware-test-matrix.md](02-hardware-test-matrix.md).

---

## Abschlussdefinition

Beagle OS darf als "Enterprise GA" bezeichnet werden, wenn:

- [ ] alle R3-Gates bestanden sind
- [ ] alle kritischen Security-Funde in `docs/refactor/11-security-findings.md` geschlossen oder als akzeptiertes Restrisiko signiert sind
- [ ] ein externer Security-Review oder Penetrationstest keine kritischen offenen Findings enthaelt
- [ ] mindestens ein Clean-Install von Release-Artefakten vollstaendig durchlief
- [ ] mindestens ein Update von vorheriger Version auf Zielversion durchlief
- [ ] mindestens ein Rollback/Restore erfolgreich war
- [ ] ein Pilot-Runbook fuer Kunden existiert
- [ ] Support-/Incident-Prozess dokumentiert ist

