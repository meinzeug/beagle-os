# Runbook — Pilotbetrieb

**Status**: Skelett · **Letzte Validierung**: —

Ziel: Anleitung fuer Pilotkunden zur Erstinstallation, Inbetriebnahme und
Tagesbetrieb einer Beagle-OS-Installation.

## 1. Pilot-Voraussetzungen (Pflicht)

- [ ] Hardware abgenommen nach [`installation.md`](installation.md)
- [ ] Backup-Strategie definiert + 1 erfolgreicher Restore-Test nach [`backup-restore.md`](backup-restore.md)
- [ ] Update-/Rollback-Strategie verstanden
- [ ] Incident-Response-Kontakte schriftlich hinterlegt
- [ ] Datenschutz-/Auftragsverarbeitungs-Vereinbarung unterzeichnet
- [ ] Mind. 1 Operator beim Betreiber geschult

## 2. Onboarding (Tag 1)

1. Frische Installation nach [`installation.md`](installation.md) durchfuehren.
2. Admin-Account erstellen (MFA pflichtig empfohlen).
3. Tenant(s) anlegen, RBAC-Rollen zuweisen.
4. Erste Test-VM erstellen, Lifecycle (start/stop/snapshot) verifizieren.
5. Erstes Backup ausfuehren + verifizieren.

## 3. Tagesbetrieb

| Aktivitaet | Frequenz | Verantwortlich |
|---|---|---|
| Health-Dashboard pruefen | taeglich | Operator |
| Backup-Erfolg pruefen | taeglich | Operator |
| Audit-Log-Stichprobe | woechentlich | Security |
| Update-Check | monatlich | Operator |
| Vollstaendiger Restore-Test | quartalsweise | Operator |
| Pen-Test / Security-Review | jaehrlich | extern |

## 4. Pilot-Erfolgskriterien

- [ ] 30 Tage produktiver Betrieb ohne SEV-1 Incident
- [ ] Mind. 1 erfolgreich durchgefuehrtes Update + 1 simulierter Rollback
- [ ] Mind. 1 vollstaendiger Restore-Test
- [ ] Operator beherrscht Standard-Operationen ohne Eskalation
- [ ] Backup-/Restore-Hashes dokumentiert

## 5. Abnahme + Uebergang in Produktion

Nach erfolgreichem Pilot:

- [ ] Pilot-Befunde in `docs/refactor/05-progress.md` eingetragen
- [ ] Konkrete Verbesserungswuensche als Items in `docs/checklists/` ergaenzt
- [ ] Pilotkunde unterzeichnet Production-Freigabe

## 6. Befund-Felder

- Pilot-Start:
- Pilot-Ende:
- Anzahl Operatoren:
- Anzahl produktiver VMs / Streams / Endpoints:
- SEV-1 Incidents:
- Kundenbewertung:
