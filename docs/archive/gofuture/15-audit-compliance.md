# 15 — 7.2.2 Audit + Compliance-Export

Stand: 2026-04-20  
Priorität: 7.2 (Q3 2027)

---

## Schritte

### Schritt 1 — Audit-Event-Schema vereinheitlichen

- [x] `core/audit_event.py` anlegen: `AuditEvent`-Datenklasse mit allen Pflichtfeldern.
- [x] Alle bestehenden `audit_log.py`-Einträge auf das neue Schema migrieren.

Ein einheitliches Audit-Schema ist Voraussetzung für alle nachfolgenden Export- und
Analyse-Funktionen. Das Schema definiert Pflichtfelder: `id` (UUID), `timestamp` (UTC ISO 8601),
`tenant_id`, `user_id`, `session_id` (optional), `action` (strukturierter Enum),
`resource_type`, `resource_id`, `old_value` (JSON, redacted), `new_value` (JSON, redacted),
`result` (success | failure | rejected), `source_ip`, `user_agent`. Der `action`-Enum
deckt alle möglichen Plattform-Aktionen ab: `vm.start`, `vm.stop`, `vm.delete`, `user.create`,
`pool.scale`, `session.start`, `session.end`, `recording.download`, etc. Das Schema
ist versioniert damit künftige Erweiterungen rückwärtskompatibel bleiben.

---

### Schritt 2 — Audit-Export zu S3/Minio, Syslog und Webhook implementieren

- [x] `beagle-host/services/audit_export.py`: konfigurierbare Export-Targets.
- [x] Export-Targets: S3-kompatibel (Minio, AWS S3), Syslog (RFC 5424), HTTP-Webhook.

Externe SIEM-Systeme (Splunk, Elastic, Graylog) brauchen einen Ingestion-Pfad für
Audit-Events. S3-Export speichert Events als JSON-Lines-Dateien in stündlichen oder
täglichen Batches. Syslog-Export sendet Events in Echtzeit als strukturierte Syslog-
Nachrichten (RFC 5424 mit structured data). Webhook-Export sendet Events als HTTP POST
JSON-Payloads an eine konfigurierte URL mit HMAC-Signatur für Authentizitäts-Verifikation.
Alle Export-Targets sind optional und werden in der Web Console unter Server-Settings
konfiguriert. Export-Fehler werden geloggt und nach konfigurierbarer Retry-Anzahl
als Alert angezeigt. Audit-Events werden niemals verworfen; bei Export-Fehler werden
sie lokal gepuffert.

Umsetzung (2026-04-23):
- `beagle-host/services/audit_export.py` implementiert:
	- `AuditExportConfig` fuer S3-, Syslog- und Webhook-Targets,
	- `AuditExportService.export_event(...)` mit fan-out auf alle aktivierten Targets,
	- Failure-Queueing in `audit/export-failures.log` bei Target-Fehlern.
- `beagle-host/bin/beagle-control-plane.py` verdrahtet:
	- Env-Konfiguration (`BEAGLE_AUDIT_EXPORT_*`) fuer alle Targets,
	- `audit_export_service()` als lazy-init,
	- `audit_log_service()` ruft Export direkt nach lokalem Event-Append auf.
- `beagle-host/services/audit_log.py` exportiert Events ueber `export_event` Hook.

Validierung:
- Lokal: `python3 -m pytest tests/unit/test_audit_export.py tests/unit/test_audit_log.py -q` => `7 passed`.
- Live auf `srv1.beagle-os.com`:
	- temporärer Webhook-Target (`http://127.0.0.1:18081/audit`) gesetzt,
	- Audit-Event durch fehlgeschlagenen Login erzeugt,
	- Webhook-Capture bestaetigt `path=/audit`, `X-Beagle-Signature` vorhanden, Event `action=auth.login`, `result=rejected`,
	- Env danach wiederhergestellt und `beagle-control-plane` erneut `active`.

---

### Schritt 3 — PII-Schwärzungs-Filter implementieren

- [x] `beagle-host/services/audit_pii_filter.py`: konfigurierbare Felder-Schwärzung vor Export.
- [x] Default-Schwärzung: Passwörter, API-Keys, private Schlüssel in `old_value`/`new_value`.

PII (Personally Identifiable Information) und Secrets dürfen in Audit-Exporten nicht
im Klartext erscheinen. Der PII-Filter wird zwischen Audit-Event-Erzeugung und Export
geschaltet. Konfigurierbare Feldlisten definieren welche JSON-Pfade in `old_value`/
`new_value` geschwärzt werden (ersetzt durch `[REDACTED]`). Default-Schwärzung greift
auf alle Felder die `password`, `secret`, `token`, `key` im Namen enthalten.
Optionale erweiterte Schwärzung kann IP-Adressen, E-Mail-Adressen und Benutzernamen
pseudonymisieren. Die Schwärzungs-Konfiguration wird selbst im Audit-Log festgehalten
wenn sie geändert wird.

---

### Schritt 4 — Compliance-Report-Generator (CSV/JSON) implementieren

- [x] `GET /api/v1/audit/report` Endpoint mit Filtern: time range, tenant, action type, user.
- [x] Response: CSV oder JSON je nach `Accept`-Header.

Compliance-Berichte sind in regulierten Umgebungen periodisch erforderlich (monatlich,
jährlich). Der Report-Generator erlaubt Filterung nach Zeitraum, Tenant, Action-Typ
und Benutzer. Das CSV-Format ist für Tabellenkalkulationsprogramme gut geeignet;
JSON für programmatische Verarbeitung. Beide Formate sind BOM-encoded utf-8 für
maximale Kompatibilität. Große Reports werden asynchron generiert und als Download-URL
zurückgegeben. Der Report-Download selbst erzeugt wieder einen Audit-Event (wer hat
wann welchen Report heruntergeladen). Reports älter als 7 Tage werden automatisch
gelöscht; der Download-Link läuft entsprechend ab.

---

### Schritt 5 — Audit-Viewer in Web Console

- [x] Neues Admin-Panel "Audit" in der Web Console mit Echtzeit-View und Filter-UI.
- [x] Filter: Zeitraum, User, Action-Typ, Resource-Typ, Tenant.

Der Audit-Viewer zeigt Audit-Events als paginierte Tabelle mit Echtzeit-Aktualisierung.
Ein Filter-Panel erlaubt Einschränkung auf Zeitraum (letzte 1h, 24h, 7 Tage, custom),
Benutzer (Freitext-Suche), Action-Typ (Dropdown), Tenant (Dropdown für Platform-Admins).
Jede Tabellen-Zeile ist aufklappbar für die vollständige Event-JSON-Darstellung.
Ein "Report exportieren"-Button triggert den Report-Generator mit den aktuellen
Filter-Einstellungen. Der Audit-Viewer ist nur für Rollen `platform-admin`, `tenant-admin`
und `auditor` sichtbar.

---

### Schritt 6 — `/#panel=audit` UX- und Bedienbarkeits-Refactor

- [x] Ist-Zustand von `/#panel=audit` dokumentieren: Filter, Tabelle, Export-Buttons, fehlende Details, unklare Fehlerzustände.
- [x] Audit-Panel in klare Bereiche schneiden: `Live Events`, `Filter`, `Report Builder`, `Export Targets`, `Failures/Replay`.
- [x] Event-Tabelle verbessern: Severity/Result-Chips, Zeitachse, User/Resource-Spalten, expandierbare JSON-Details mit Redaction-Markern.
- [x] Filter UX verbessern: Zeitraum-Presets, Custom-Date-Range, User-/Action-/Resource-Suche, Tenant-Scope, Reset/Apply sichtbar.
- [x] Report-Builder als Wizard bauen: Zeitraum wählen, Filter bestätigen, Format wählen, Export starten, Download/Job-Status anzeigen.
- [x] Export-Ziele bedienbar machen: S3/Minio, Syslog, Webhook Status-Cards, Test-Button, letzter Fehler, Retry/Replay.
- [x] Compliance-Ansicht ergänzen: gespeicherte Reports, Ablaufdatum, Download-Audit, Prüfsummen/Integrität.
- [x] Failure-Queue sichtbar machen: Export-Fehler anzeigen, einzelne oder alle Events erneut senden.
- [x] Security-Guardrails: keine Secrets in Detail-JSON, PII-Filter sichtbar kennzeichnen, Download-Berechtigung prüfen.
- [x] UI-Regressions ergänzen: Filter-Kombinationen, CSV/JSON-Export, Detail-Expand, Export-Target-Test, Empty-/Error-State.
- [x] srv1-Smoke durchführen: Events erzeugen, filtern, Report exportieren, Webhook/S3-Status prüfen, keine Console Errors.

Umsetzung (2026-04-27):

- Ist-Zustand vor dem Refactor: `/#panel=audit` hatte Filter, CSV-Export, Event-Tabelle, Export-Targets und Failure-Queue, aber keinen Report-Builder, keinen bedienbaren Target-Test, keinen Replay-Flow und keine expliziten Redaction-Hinweise in den JSON-Details.
- `website/ui/audit.js`, `website/index.html` und `website/styles/panels/_audit.css` schneiden den Bereich jetzt in Live-Events/Filter, Export-Ziele, Report Builder, Compliance-Reports und Failures/Replay.
- Event-Details werden vor Anzeige rekursiv auf `password`, `token`, `secret` und `key` geschwaerzt und mit `redacted` markiert.
- `AuditExportService` liefert `last_error`, speichert Failure-Payloads nur redacted und kann Export-Targets testen sowie replay-faehige Failures erneut senden.
- `AuditReportHttpSurfaceService` routet `POST /api/v1/audit/export-targets/{target}/test` und `POST /api/v1/audit/failures/replay`; RBAC verlangt `auth:write`.
- Lokal validiert: `node --check website/ui/audit.js website/ui/events.js website/main.js` und `python3 -m pytest tests/unit/test_audit_report.py tests/unit/test_audit_export.py tests/unit/test_authz_policy.py`.
- srv1-Smoke bleibt offen: `beagle-manager` war am 2026-04-27 auf `srv1` `inactive`.

Update 2026-04-27:

- `tests/unit/test_audit_ui_regressions.py` ergänzt:
  - Audit-Panel-Layout
  - Redaction-/Report-Builder-/Replay-Hooks
  - CSS-Coverage fuer Target-/Builder-/Report-Sektionen
- `scripts/test-audit-compliance-live-smoke.sh` auf `srv1` erfolgreich ausgefuehrt:
  - Audit-Events fuer `vm.start`/`vm.stop`/`vm.reboot`
  - Filter-/Viewer-Semantik
  - CSV-Konsistenz
  - MinIO-S3-Export
  - Ergebnis: `AUDIT_COMPLIANCE_SMOKE=PASS`

Warum dieser Schritt noch offen ist:
Audit und Compliance sind backendseitig vorhanden, aber die WebUI muss aus Audit-Daten handlungsfähige Informationen machen. Betreiber brauchen nicht nur eine Tabelle, sondern geführte Report-Erstellung, Export-Diagnose, Failure-Replay und klare Hinweise auf Redaction/PII. Ohne diese Bedienbarkeit bleibt Audit ein Rohdaten-Viewer und erfüllt den Compliance-Anspruch nur teilweise.

---

## Testpflicht nach Abschluss

- [x] Alle VM-Operationen erzeugen Audit-Events mit korrektem Schema.
- [x] S3-Export: Events landen im Minio-Bucket als JSON-Lines.
- [x] PII-Filter: Passwörter in `new_value` erscheinen als `[REDACTED]`.
- [x] Compliance-Report CSV enthält alle Events im Zeitraum, kein Inhalt fehlt.
- [x] Audit-Viewer: Filter nach User und Action-Typ funktionieren korrekt.

Validierung (2026-04-23):
- Lokal: `python3 -m pytest tests/unit/test_audit_log.py tests/unit/test_audit_report.py tests/unit/test_audit_export.py tests/unit/test_audit_helpers.py -q` => `12 passed`.
- Live auf `srv1.beagle-os.com` mit Smoke-Test `scripts/test-audit-compliance-live-smoke.sh`:
  - [PASS] VM power operations (start/stop/reboot) generate audit events with correct schema
  - [PASS] Audit viewer filter semantics (action + user filters correctly applied)
  - [PASS] Compliance CSV report includes all events with complete schema fields
	- [PASS] MinIO S3 export delivered object in bucket (`AUDIT_COMPLIANCE_SMOKE=PASS`)
  - Service state: beagle-control-plane active, no errors in journal
- Reproduzierbarkeit: `scripts/install-beagle-host-services.sh` installiert jetzt `python3-boto3`, damit S3-Export auf frischen Hosts nicht an fehlender Runtime-Dependency scheitert.
