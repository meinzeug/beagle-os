# 04 — Control Plane: beagle-host aufräumen

Stand: 2026-04-20  
Priorität: Welle 6.x (April–Mai 2026)  
Betroffene Verzeichnisse: `beagle-host/bin/`, `beagle-host/services/`, `beagle-host/providers/`

---

## Hintergrund

`beagle-host/bin/beagle-control-plane.py` ist der API-Server auf Port 9088.
Er enthält aktuell Route-Handler, Business-Logik und Provider-Aufrufe vermischt.
Das Ziel ist eine saubere Schichttrennung: Routen-Layer → Service-Layer → Provider-Layer.
Dabei soll `beagle-control-plane.py` zum reinen Routen-Dispatcher werden, während
alle Business-Logik in `beagle-host/services/*.py` landet.

---

## Schritte

### Schritt 1 — Abhängigkeitsbaum und Service-Grenzen kartieren

- [ ] `beagle-control-plane.py` vollständig lesen und alle Route-Handler mit zugehörigen Services identifizieren.
- [ ] Liste aller direkten Provider-Aufrufe (qm, pvesh, libvirt, etc.) in nicht-Provider-Code erstellen.

Bevor Code verschoben wird muss der aktuelle Zustand vollständig verstanden sein.
Jede Zeile die direkt `qm`, `pvesh` oder `/api2/json` aufruft und sich nicht in
`beagle-host/providers/` befindet ist ein Architekturverstoß der dokumentiert werden muss.
Die Abhängigkeitskarte zeigt, welche Services bereits in `beagle-host/services/` vorhanden
sind und welche noch im Hauptskript versteckt sind. Ergebnis dieser Analyse landet
in `docs/refactor/05-progress.md` und `docs/refactor/08-todo-global.md`.

---

### Schritt 2 — Route-Handler von Business-Logik trennen

- [ ] Jeden langen Route-Handler-Block in eine Service-Funktion in `beagle-host/services/` extrahieren.
- [ ] Route-Handler in `beagle-control-plane.py` werden zu 5–10-Zeilen-Deleagierern.

Ein Route-Handler der mehr als 20 Zeilen hat enthält mit hoher Wahrscheinlichkeit
Business-Logik die nicht in den HTTP-Layer gehört. Die Extraktion folgt dem Muster:
Route-Handler valdiert Input, ruft Service auf, gibt Ergebnis als JSON zurück.
Eingabevalidierung kann in dedizierte Validator-Funktionen ausgelagert werden.
Der Service kann damit unabhängig von HTTP getestet werden. Dieser Schritt wird
inkrementell ausgeführt: ein Handler nach dem anderen, jedes Mal mit Smoke-Test.

---

### Schritt 3 — Auth- und RBAC-Middleware vereinheitlichen

- [ ] Sicherstellen, dass alle mutierenden Endpoints (`POST`, `PUT`, `DELETE`, `PATCH`) durch RBAC-Middleware laufen.
- [ ] Fehlende Middleware-Aufrufe identifizieren und nachrüsten.

`docs/refactor/01-problem-analysis.md` hat bereits dokumentiert dass RBAC nicht
durchgängig auf alle Mutations-Endpunkte erzwungen wird. Dieser Schritt schließt
diese Lücke. Jeder Endpoint der State verändert muss einen gültigen Token prüfen
und die Berechtigung des Users für genau diese Operation verifizieren. Ein
Middleware-Decorator oder eine Wrapper-Funktion stellt das konsistent sicher.
Fehlendes RBAC auf einem Endpoint ist ein Security-Finding und landet in
`docs/refactor/11-security-findings.md`.

---

### Schritt 4 — Input-Validierung bei API-Boundaries härten

- [ ] Alle POSTed JSON-Bodies durch Whitelist-Schemata validieren.
- [ ] `sanitizeIdentifier` und ähnliche Prüffunktionen serverseitig nicht nur clientseitig erzwingen.

Clientseitige Validierung im JavaScript ist kein Sicherheitsmerkmal sondern nur UX.
Alle Eingaben die an den Server gehen müssen server-seitig nochmals nach Typ, Länge
und erlaubtem Zeichensatz geprüft werden. Insbesondere VM-Namen, Hostnamen, Passwörter
und Pfad-Parameter sind anfällig für Injection wenn nicht korrekt validiert.
Das Validierungsschema wird explizit dokumentiert und bei Änderungen mitgepflegt.
`jsonschema` (Python) oder eigengeschriebene Validator-Funktionen können eingesetzt werden.

---

### Schritt 5 — Logging und Audit-Trail standardisieren

- [ ] Alle Service-Aufrufe bekommen strukturiertes Logging (JSON) mit User-ID, Action, Resource-ID.
- [ ] Audit-Events für alle mutablen Operationen werden in `services/audit_log.py` persistent gespeichert.

Ohne Audit-Log ist es unmöglich im Nachhinein nachzuvollziehen wer wann welche VM
gelöscht oder welchen User geändert hat. Der Audit-Log ist Pflicht für RBAC-Compliance
und für `docs/refactorv2/15-risks-open-questions.md` R6 (Mandanten-Isolation).
Strukturierte JSON-Logs erlauben späteres Shipping an externe SIEM-Systeme.
Jeder Audit-Eintrag enthält: Timestamp (UTC), User-ID, Tenant-ID, Action, Resource-Typ,
Resource-ID, alten Wert (redacted), neuen Wert (redacted), Ergebnis (success/fail).

---

### Schritt 6 — Fehlerbehandlung vereinheitlichen

- [ ] HTTP-Fehlerantworten auf konsistentes JSON-Schema bringen: `{"error": "...", "code": "..."}`.
- [ ] Alle unhandelten Exceptions werden zu 500-Fehlern mit gesanitiztem Error-Text.

Aktuell geben verschiedene Endpunkte unterschiedliche Fehlerformate zurück was die
Frontend-Fehlerbehandlung verkompliziert und inkonsistent macht. Ein einheitliches
Error-Response-Schema wird definiert und in einem Error-Handler-Decorator umgesetzt.
Interne Server-Fehler dürfen dem Client niemals den Stack-Trace oder interne Pfade
preisgeben. Der Stack-Trace wird geloggt aber nicht zurückgegeben. Das Frontend kann
damit auf ein konsistentes Error-Objekt mit `error`- und `code`-Feld reagieren.

---

### Schritt 7 — Service-Start und systemd-Unit sauber halten

- [ ] `beagle-host/systemd/beagle-control-plane.service` auf korrekte `ExecStart`-Pfade, `Restart`-Policy und `CapabilityBoundingSet` prüfen.
- [ ] Keine unnötigen Capabilities oder root-Privileges im Service-User.

Ein Python-API-Server der auf Port 9088 läuft braucht keine root-Rechte; ein dedizierter
`beagle`-User mit den minimal notwendigen Capabilities ist der sichere Default.
`CapabilityBoundingSet=` in der systemd-Unit wird explizit auf das Notwendige beschränkt.
`Restart=on-failure` und `RestartSec=5` stellen automatische Wiederanlauf sicher.
`PrivateTmp=yes` und `NoNewPrivileges=yes` sind obligatorische Hardening-Optionen.

---

## Testpflicht nach Abschluss

- [ ] Alle API-Endpunkte antworten korrekt nach Refactoring (Smoke-Tests).
- [ ] RBAC: unauthentizierter POST auf `/api/v1/vms` gibt 401 zurück.
- [ ] RBAC: User ohne Admin-Rolle kann keine Settings ändern.
- [ ] Audit-Log schreibt Entries bei VM-Start, VM-Stop, User-Create.
- [ ] `journalctl -u beagle-control-plane` zeigt keine Unhandled-Exception-Traces.
