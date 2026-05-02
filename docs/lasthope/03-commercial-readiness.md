# Commercial Readiness

Stand: 2026-05-02

Dieses Dokument definiert, was vorhanden sein muss, bevor Beagle OS aktiv Firmen
angeboten wird.

## Angebotspaket

Beagle OS kann Firmen angeboten werden, wenn ein Betreiber diese Leistungen ohne
Entwicklerintervention liefern kann:

- Installation aus Release-ISO oder installimage
- Erstkonfiguration ueber WebUI-Onboarding
- VM-Erstellung mit KDE/Beagle OS Cyberpunk oder KDE Plasma Classic
- Thinclient-/Live-USB-Erstellung fuer eine VM
- BeagleStream-Verbindung ohne manuelle PIN
- Backup, Restore, Update und Rollback nach Runbook
- Monitoring, Alerting, Audit-Export und Incident-Prozess
- klarer Lizenz- und Supportkontakt fuer kommerzielle Nutzung

## Nicht verkaufen, solange offen

- Clean-Install ist nicht live validiert.
- BeagleStream-End-to-End ist nicht reproduzierbar abgeschlossen.
- Restore einer echten VM-Disk auf frischem Host fehlt.
- Externer Security-Review fehlt.
- HA/Fencing und WireGuard-Stream-Latenz sind nicht auf echter Zwei-Host-Umgebung abgenommen.

Diese Punkte duerfen nicht als "kleine Restarbeiten" behandelt werden. Sie sind
Vertrauensanker fuer Firmenkunden.

## Kommerzieller Mindestumfang

### Technisch

- eine stabile Release-Version mit Checksummen, SBOM und Signatur
- dokumentierter Upgrade-Pfad von der vorherigen Version
- dokumentierter Rollback-Pfad
- klare Hardware-Mindestanforderungen
- ein Support-Bundle-Export ohne Secrets
- Health-Check-Skript mit eindeutigem PASS/FAIL

### Betrieblich

- Pilot-Runbook mit Erfolgskriterien
- Incident-Runbook mit Severity-Stufen
- Wartungsfenster und Supportzeiten
- Backup-/Restore-Verantwortlichkeiten
- Datenschutzhinweise und AVV-Vorlage fuer Pilotkunden

### Rechtlich/Kommunikativ

- private Nutzung: Open Source gemaess GitHub-Lizenz
- Unternehmen: kommerzielle Anfrage ueber `contact@beagle-os.com` oder GitHub-Kontaktpfad
- keine oeffentliche SaaS-Vermarktung, solange SaaS kein Produktpfad ist
- keine Preislisten auf der Website, solange Lizenz-/Supportmodell nicht final ist

## Pilotdefinition

Ein Pilot ist zulaessig, wenn:

- E1 vollstaendig gruen ist
- ein Betreiberzugang und ein Break-Glass-Zugang dokumentiert sind
- ein Kunde weiss, dass es ein Pilot ist
- Backup/Restore vor produktiven Daten getestet wurde
- der Betreiber Messwerte fuer Stream-Latenz, Host-Auslastung, Backup-Erfolg und Fehlerfaelle erhaelt

Ein produktiver Firmenbetrieb ist erst zulaessig, wenn:

- E3 gruen ist
- ein externer Security-Review ohne kritische Findings abgeschlossen wurde
- mindestens ein echter Update- und Rollbacklauf erfolgreich war
- Restore und Incident-Prozess nachweislich funktionieren

## Go/No-Go Check

Vor jedem Firmenkontakt:

- [ ] Welche Version wird angeboten?
- [ ] Welche Host-Hardware ist freigegeben?
- [ ] Wurde genau diese Version clean installiert?
- [ ] Wurde eine VM aus der WebUI erstellt und gestreamt?
- [ ] Wurde ein Backup erstellt und restored?
- [ ] Sind Security-Findings offen?
- [ ] Sind Runbooks aktuell und validiert?
- [ ] Ist klar, was kostenlos/private Nutzung und was kommerzielle Anfrage ist?

