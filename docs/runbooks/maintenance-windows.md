# Runbook — Wartungsfenster und Supportzeiten

**Status**: Aktiv · **Letzte Aktualisierung**: 2026-04-30

Definiert verbindliche Wartungsfenster, Supportzeiten und die
Eskalations-/Kommunikationsprozesse fuer Beagle-OS-Installationen.

---

## 1. Wartungsfenster

### 1.1 Regulaeres Wartungsfenster

| Parameter | Wert |
|---|---|
| Zeitpunkt | Jeden **Dienstag** von **02:00 – 04:00 Uhr** (Europe/Berlin) |
| Typ | Rolling — typisch kein Ausfall; Streaming-Unterbrechung moeglich |
| Vorankuendigung | Mind. **48 h** per E-Mail an alle Admin-Accounts |
| Rueckgaengig | Rollback nach [`rollback.md`](rollback.md) wenn noetig |

### 1.2 Notfall-Wartung (Emergency Patch)

| Parameter | Wert |
|---|---|
| Ausloeser | SEV-1 Sicherheitsvorfall oder kritische Stabilitaetsprobleme |
| Vorlaufzeit | Mindestens **2 h** Voranmeldung; bei aktiver Ausnutzung sofort |
| Kommunikation | E-Mail + Status-Page-Update |
| Post-Maintenance | Post-Mortem in `docs/refactor/11-security-findings.md` |

### 1.3 Kein Wartungsfenster noetig

- Hotfixes, die ausschliesslich Konfigurationsdateien oder Dokumentation betreffen
- Read-only UI-Updates ohne Service-Neustart
- Hinzufuegen von VMs oder Usern ohne Control-Plane-Neustart

---

## 2. Supportzeiten

### 2.1 Standard-Support (Pilot / Community)

| Kanal | Verfuegbarkeit | Reaktionszeit |
|---|---|---|
| GitHub Issues | Mo–Fr 09–18 Uhr (Europe/Berlin) | < 1 Werktag (SEV-3/4) |
| E-Mail | Mo–Fr 09–18 Uhr | < 4 h (SEV-2), < 1 h (SEV-1) |
| Notfallkontakt | 24/7 | < 30 min (SEV-1 mit AVV) |

### 2.2 Eskalation

```
Operator → Beagle-OS-Admin → Security-Verantwortlicher → Externe Forensik
```

Kontakte werden bei Projektstart in einem **nicht im Repo** versionierten
Betriebshandbuch hinterlegt (Datei: `/etc/beagle/operator-contacts.txt`,
Zugriffsrecht nur root).

---

## 3. Kommunikationstemplate

### Voranmeldung (E-Mail / Chat)

```
Betreff: [BEAGLE-OS] Wartungsfenster <DATUM> <UHRZEIT>–<UHRZEIT>

Hallo,

wir fuehren am <DATUM> von <START> bis <ENDE> Uhr (Europe/Berlin)
Wartungsarbeiten an der Beagle-OS-Instanz durch.

Auswirkung: [keiner Ausfall | kurze Unterbrechung des Streaming (< 5 min)]
Grund: [Sicherheitsupdate | Feature-Update | Konfigurationsaenderung]
Rollback-Plan: vorhanden (ca. 10 min)

Bei Fragen bitte per Reply oder unter <KONTAKT>.
```

### Abschlussmeldung

```
Betreff: [BEAGLE-OS] Wartung abgeschlossen — <STATUS>

Wartung am <DATUM> wurde um <UHRZEIT> abgeschlossen.
Status: [ERFOLGREICH | TEILWEISE | ROLLBACK]
Details: [Kurzbeschreibung]
Naechste Schritte: [keine | Nachbeobachtung bis <DATUM>]
```

---

## 4. Notfallzugriff

Notfallzugriff-Credentials werden **nicht** in versionierten Dokumenten
gespeichert. Stattdessen:

- Erstinstallations-Credentials: `/root/beagle-firstboot-credentials.txt`
  (nur auf dem Zielhost, nicht committed, nur root lesbar `chmod 600`)
- Break-Glass-Account: In einem separaten, verschluesselten Passwort-Manager
  des Betreibers (z. B. Vaultwarden, Bitwarden, KeePass).
- SSH-Notfall-Key: In `/root/.ssh/authorized_keys` des Zielhosts hinterlegt;
  privater Key nur beim authorisierten Operator.

**Pruefung**: mind. einmal jaehrlich verifizieren, dass der Notfallzugang
funktioniert (ohne Production-Impact: Testhost nutzen).

---

## 5. Change-Log

| Datum | Aenderung |
|---|---|
| 2026-04-30 | Initiale Version erstellt |
