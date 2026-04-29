# 05 - Betrieb, Compliance und Firmenfreigabe

Stand: 2026-04-27  
Ziel: Firmen bekommen kein loses Bastelprodukt, sondern einen kontrollierten Betriebsrahmen.

---

## Gate O1 - Betriebsmodell

- [ ] Installations-Runbook.
- [ ] Update-Runbook.
- [ ] Rollback-Runbook.
- [ ] Backup-/Restore-Runbook.
- [ ] Incident-Response-Runbook.
- [ ] Notfallzugriff ohne Klartext-Secrets in Dokumenten.
- [ ] Wartungsfenster und Supportzeiten definieren.

---

## Gate O2 - Monitoring und Alerting

- [ ] Control Plane Health.
- [ ] nginx/TLS Health.
- [ ] Disk-/Storage-Fuellstand.
- [ ] VM-/Session-/Stream-Health.
- [ ] Backup-Erfolg und Restore-Alter.
- [ ] Artifact-/Repo-Auto-Update-Status.
- [ ] Security-relevante Auth-/RBAC-/Audit-Events.
- [ ] Webhook oder E-Mail fuer kritische Alerts.

---

## Gate O3 - Datenschutz und Audit

- [ ] Datenarten dokumentieren: Nutzer, Sessions, Audit, Stream-Health, Endpoint-Hardware.
- [ ] Retention-Regeln definieren.
- [ ] Audit-Export fuer Administratoren.
- [ ] PII-/Secret-Redaction validieren.
- [ ] Mandanten-/Rollen-Sichtbarkeit pruefen.
- [ ] Auftragsverarbeitung/DSGVO-Hinweise fuer Pilotkunden vorbereiten.

---

## Gate O4 - Pilotfreigabe

Beagle OS darf als Firmen-Pilot angeboten werden, wenn:

- [ ] R2 erreicht ist.
- [ ] Kunde versteht Beta-/Pilotstatus.
- [ ] Pilot laeuft auf dedizierter Umgebung.
- [ ] Kein kritischer produktiver Workload ohne Backup/Restore-Test.
- [x] `srv1` ist firewall- und TLS-gehaertet: Beagle nftables Guard aktiv, `9088/9089` extern geschlossen, WebUI/API via `443` erreichbar.
- [ ] Pilotvertrag nennt bekannte Restrisiken.
- [ ] Monitoring und Kontaktweg fuer Stoerungen sind aktiv.

Empfohlene Pilot-Hardware:

- 1 dedizierter CPU-Server fuer echte VM-/Thin-Client-Tests.
- 1-2 kleine Hetzner VMs fuer externe Control-Plane-/Update-/DNS-/Monitoring-Smokes.
- optional 1 GPU-Server nur fuer Gaming-/GPU-Pilot.

---

## Gate O5 - Enterprise-GA-Freigabe

Beagle OS darf als Enterprise-GA angeboten werden, wenn:

- [ ] R3 vollstaendig gruen ist.
- [ ] Externer Security-Review ohne kritische offene Findings abgeschlossen ist.
- [ ] Ein Clean-Install aus Release-Artefakten reproduzierbar war.
- [ ] Ein Update von vorheriger Version reproduzierbar war.
- [ ] Ein Restore aus Backup reproduzierbar war.
- [ ] Support-/Incident-Prozess steht.
- [ ] Security-Findings in `docs/refactor/11-security-findings.md` sind bereinigt oder als Restrisiko akzeptiert.
- [ ] Hardware-Matrix fuer die verkaufte Funktionsklasse bestanden ist.

---

## Angebotsformulierung

Bis R3:

`Beagle OS 8.x Controlled Enterprise Pilot`

Ab R3:

`Beagle OS 8.x Enterprise Candidate`

Erst ab R4:

`Beagle OS 8.x Enterprise GA`

Nicht verwenden, solange R4 nicht erreicht ist:

`vollstaendig sicher`, `garantiert sicher`, `zero risk`, `ungeprueft production ready`

Stattdessen:

`security-gated`, `self-hosted`, `auditierbar`, `kontrolliert abgenommen`, `mit dokumentierten Restrisiken`
