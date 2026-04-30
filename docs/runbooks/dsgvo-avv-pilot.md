# Datenschutz und Auftragsverarbeitung — Pilotkunden-Hinweise

**Status**: Aktiv · **Letzte Aktualisierung**: 2026-04-30

Dieses Dokument beschreibt die Datenschutz-Pflichten und
Auftragsverarbeitungs-Anforderungen fuer Beagle-OS-Pilotkunden im
Rahmen der DSGVO (EU 2016/679).

> **Hinweis**: Dieses Dokument ist kein Rechtsanwalt-Ersatz. Vor Produktivbetrieb
> muss eine rechtliche Pruefung durch den Betreiber oder dessen Datenschutzbeauftragten
> erfolgen.

---

## 1. Verarbeitete Personenbezogene Daten

| Datenkategorie | Zweck | Aufbewahrung | Betroffene |
|---|---|---|---|
| Admin-/User-Accounts | Authentifizierung + Autorisierung | Aktiv: unbegrenzt; nach Loeschung: sofort | Betreiber-Admins, Nutzer |
| Sitzungs-Tokens (JWT) | Auth-Session-Management | TTL ~8 h (Ablauf automatisch) | Aktive Nutzer |
| Audit-Logs | Nachvollziehbarkeit, Compliance | 90 Tage (konfigurierbar) | Admins, Nutzer |
| Stream-Session-Metadaten | Betrieb + Troubleshooting | 30 Tage (konfigurierbar) | Stream-Nutzer |
| Endpoint-Hardware-Daten | Inventory + Provisioning | Geraete-Lifetime | Thin-Client-Operator |
| Backup-Snapshots | Disaster Recovery | Backups-Aufbewahrungsregel | VMs und deren Nutzer |

Vollstaendige Datenarten-Liste: [`data-retention.md`](data-retention.md)

---

## 2. Auftragsverarbeitung (AVV)

Wenn Beagle OS als Dienstleistung durch einen Dritten (z. B. MSP, IT-Dienstleister)
betrieben wird, fuer dessen Kunden gilt:

- **AVV-Pflicht** (Art. 28 DSGVO): Ein schriftlicher Auftragsverarbeitungsvertrag
  zwischen Auftraggeber (Pilotkunde) und Auftragnehmer (Betreiber) ist **Pflicht**.
- **Vorlage**: Eine AVV-Vorlage muss durch den Betreiber bereitgestellt werden
  (nicht Teil dieses Repos — enthält unternehmensspezifische Angaben).
- **Unterzeichnung**: vor Aufnahme des Pilotbetriebs.
- **Mindestinhalte** (Art. 28 Abs. 3 DSGVO):
  - Gegenstand und Dauer der Verarbeitung
  - Art und Zweck
  - Kategorien personenbezogener Daten + betroffener Personen
  - Pflichten und Rechte des Verantwortlichen

---

## 3. Technisch-Organisatorische Massnahmen (TOMs)

| Massnahme | Stand |
|---|---|
| TLS-Verschluesselung (Transit) | [x] Aktiv (HTTPS + Nginx-Proxy) |
| Zugriffskontrolle (JWT Bearer Auth) | [x] Aktiv |
| Role-Based Access Control | [x] Aktiv |
| Audit-Log aller Admin-Aktionen | [x] Aktiv |
| Passwort-Hashing (bcrypt/argon2) | [x] Aktiv |
| No-Plaintext-Secrets in Repo | [x] Aktiv (AGENTS.md Policy) |
| Backup-Verschluesselung at-rest | [ ] Backlog (R3) |
| MFA fuer Admins | [ ] Empfohlen, optional derzeit |
| Netzwerksegmentierung | [ ] Backlog (WireGuard-Mesh R2) |

---

## 4. Betroffenenrechte

Betroffene Personen koennen folgende Rechte geltend machen (Art. 15–22 DSGVO):

| Recht | Bearbeitungsweg |
|---|---|
| Auskunft (Art. 15) | Admin: `beaglectl user export --user <id>` |
| Loeschung / Recht auf Vergessenwerden (Art. 17) | Admin: `beaglectl user delete --user <id> --purge-data` |
| Datenportabilitaet (Art. 20) | Admin: Audit-Log-Export + Account-Export |
| Einschraenkung der Verarbeitung (Art. 18) | Manuell: User deaktivieren, Audit-Log einfrieren |
| Widerspruch (Art. 21) | Per Operator-Kontakt; erfordert manuellen Eingriff |

**Fristen**: Antwort auf Auskunftsersuchen innerhalb von **30 Tagen** (Art. 12 Abs. 3).

---

## 5. Meldepflicht bei Datenpannen (Art. 33/34 DSGVO)

| Schwere | Meldung an Behoerde | Meldung an Betroffene |
|---|---|---|
| Geringes Risiko | Nicht noetig | Nicht noetig |
| Mittleres Risiko | 72 h (Art. 33) | Empfohlen |
| Hohes Risiko | 72 h (Art. 33) | Pflicht (Art. 34) |

Vorgehen bei Datenpanne: → [`incident-response.md`](incident-response.md)

---

## 6. Verzeichnis der Verarbeitungstaetigkeit (VVT)

Betreiber muessen ein VVT nach Art. 30 DSGVO fuehren. Vorlage-Elemente:

```
Verantwortlicher: <Name + Kontakt>
Zweck der Verarbeitung: Bereitstellung einer virtualisierten Gaming-/Desktop-Umgebung
Kategorien betroffener Personen: Mitarbeiter, interne Nutzer, Pilotnutzer
Kategorien personenbezogener Daten: Accountdaten, Sitzungsmetadaten, Audit-Events
Empfaenger: keine Weitergabe an Dritte (ausser AVV)
Drittlandtransfer: nein (wenn On-Premise / Hetzner EU)
Loeschfristen: siehe data-retention.md
Technische Massnahmen: siehe Abschnitt 3 TOMs
```

---

## 7. Checkliste vor Pilotstart

- [ ] AVV mit Pilotkunden unterzeichnet
- [ ] Datenschutzbeauftragter (DSB) informiert (falls vorhanden)
- [ ] VVT-Eintrag durch Betreiber erstellt
- [ ] Betroffenenrechte-Prozess intern klar geregelt
- [ ] Backup-/Restore-Test erfolgreich
- [ ] Admin-Credentials nur in sicherem Passwort-Manager hinterlegt
- [ ] Wartungsfenster + Supportzeiten kommuniziert → [`maintenance-windows.md`](maintenance-windows.md)

---

## 8. Change-Log

| Datum | Aenderung |
|---|---|
| 2026-04-30 | Initiale Version erstellt |
