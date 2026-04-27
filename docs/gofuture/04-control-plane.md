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

- [x] `beagle-control-plane.py` vollständig lesen und alle Route-Handler mit zugehörigen Services identifizieren.
- [x] Liste aller direkten Provider-Aufrufe (qm, pvesh, libvirt, etc.) in nicht-Provider-Code erstellen.

Bevor Code verschoben wird muss der aktuelle Zustand vollständig verstanden sein.
Jede Zeile die direkt `qm`, `pvesh` oder `/api2/json` aufruft und sich nicht in
`beagle-host/providers/` befindet ist ein Architekturverstoß der dokumentiert werden muss.
Die Abhängigkeitskarte zeigt, welche Services bereits in `beagle-host/services/` vorhanden
sind und welche noch im Hauptskript versteckt sind. Ergebnis dieser Analyse landet
in `docs/refactor/05-progress.md` und `docs/refactor/08-todo-global.md`.

---

### Schritt 2 — Route-Handler von Business-Logik trennen

- [x] Jeden langen Route-Handler-Block in eine Service-Funktion in `beagle-host/services/` extrahieren.
- [x] Route-Handler in `beagle-control-plane.py` werden zu 5–10-Zeilen-Deleagierern.

Ein Route-Handler der mehr als 20 Zeilen hat enthält mit hoher Wahrscheinlichkeit
Business-Logik die nicht in den HTTP-Layer gehört. Die Extraktion folgt dem Muster:
Route-Handler valdiert Input, ruft Service auf, gibt Ergebnis als JSON zurück.
Eingabevalidierung kann in dedizierte Validator-Funktionen ausgelagert werden.
Der Service kann damit unabhängig von HTTP getestet werden. Dieser Schritt wird
inkrementell ausgeführt: ein Handler nach dem anderen, jedes Mal mit Smoke-Test.

> Umsetzung 2026-04-21: Neues Service-Modul `beagle-host/services/auth_http_surface.py` eingeführt und Auth/IAM-Business-Logik (`/api/v1/auth/users`, `/api/v1/auth/roles`, `.../revoke-sessions`, User/Role `PUT`/`DELETE`) aus `beagle-control-plane.py` extrahiert. `do_GET`/`do_POST`/`do_PUT`/`do_DELETE` delegieren diese Pfade jetzt an das Surface-Service-Modul. Zusätzlich Unit-Test `tests/unit/test_auth_http_surface.py` ergänzt (lokal: `pytest` grün) und Runtime-Smoke auf `srv1.beagle-os.com` erneut 13/13 erfolgreich.

---

### Schritt 3 — Auth- und RBAC-Middleware vereinheitlichen

- [x] Sicherstellen, dass alle mutierenden Endpoints (`POST`, `PUT`, `DELETE`, `PATCH`) durch RBAC-Middleware laufen.
- [x] Fehlende Middleware-Aufrufe identifizieren und nachrüsten.

`docs/refactor/01-problem-analysis.md` hat bereits dokumentiert dass RBAC nicht
durchgängig auf alle Mutations-Endpunkte erzwungen wird. Dieser Schritt schließt
diese Lücke. Jeder Endpoint der State verändert muss einen gültigen Token prüfen
und die Berechtigung des Users für genau diese Operation verifizieren. Ein
Middleware-Decorator oder eine Wrapper-Funktion stellt das konsistent sicher.
Fehlendes RBAC auf einem Endpoint ist ein Security-Finding und landet in
`docs/refactor/11-security-findings.md`.

---

### Schritt 4 — Input-Validierung bei API-Boundaries härten

- [x] Alle POSTed JSON-Bodies durch Whitelist-Schemata validieren.
- [x] `sanitizeIdentifier` und ähnliche Prüffunktionen serverseitig nicht nur clientseitig erzwingen.

Clientseitige Validierung im JavaScript ist kein Sicherheitsmerkmal sondern nur UX.
Alle Eingaben die an den Server gehen müssen server-seitig nochmals nach Typ, Länge
und erlaubtem Zeichensatz geprüft werden. Insbesondere VM-Namen, Hostnamen, Passwörter
und Pfad-Parameter sind anfällig für Injection wenn nicht korrekt validiert.
Das Validierungsschema wird explizit dokumentiert und bei Änderungen mitgepflegt.
`jsonschema` (Python) oder eigengeschriebene Validator-Funktionen können eingesetzt werden.

---

### Schritt 5 — Logging und Audit-Trail standardisieren

- [x] Alle Service-Aufrufe bekommen strukturiertes Logging (JSON) mit User-ID, Action, Resource-ID.
- [x] Audit-Events für alle mutablen Operationen werden in `services/audit_log.py` persistent gespeichert.

Ohne Audit-Log ist es unmöglich im Nachhinein nachzuvollziehen wer wann welche VM
gelöscht oder welchen User geändert hat. Der Audit-Log ist Pflicht für RBAC-Compliance
und für `docs/refactorv2/15-risks-open-questions.md` R6 (Mandanten-Isolation).
Strukturierte JSON-Logs erlauben späteres Shipping an externe SIEM-Systeme.
Jeder Audit-Eintrag enthält: Timestamp (UTC), User-ID, Tenant-ID, Action, Resource-Typ,
Resource-ID, alten Wert (redacted), neuen Wert (redacted), Ergebnis (success/fail).

---

### Schritt 6 — Fehlerbehandlung vereinheitlichen

- [x] HTTP-Fehlerantworten auf konsistentes JSON-Schema bringen: `{"error": "...", "code": "..."}`.
- [x] Alle unhandelten Exceptions werden zu 500-Fehlern mit gesanitiztem Error-Text.

Aktuell geben verschiedene Endpunkte unterschiedliche Fehlerformate zurück was die
Frontend-Fehlerbehandlung verkompliziert und inkonsistent macht. Ein einheitliches
Error-Response-Schema wird definiert und in einem Error-Handler-Decorator umgesetzt.
Interne Server-Fehler dürfen dem Client niemals den Stack-Trace oder interne Pfade
preisgeben. Der Stack-Trace wird geloggt aber nicht zurückgegeben. Das Frontend kann
damit auf ein konsistentes Error-Objekt mit `error`- und `code`-Feld reagieren.

---

### Schritt 7 — Service-Start und systemd-Unit sauber halten

- [x] `beagle-host/systemd/beagle-control-plane.service` auf korrekte `ExecStart`-Pfade, `Restart`-Policy und `CapabilityBoundingSet` prüfen.
- [x] Keine unnötigen Capabilities oder root-Privileges im Service-User.

Ein Python-API-Server der auf Port 9088 läuft braucht keine root-Rechte; ein dedizierter
`beagle`-User mit den minimal notwendigen Capabilities ist der sichere Default.
`CapabilityBoundingSet=` in der systemd-Unit wird explizit auf das Notwendige beschränkt.
`Restart=on-failure` und `RestartSec=5` stellen automatische Wiederanlauf sicher.
`PrivateTmp=yes` und `NoNewPrivileges=yes` sind obligatorische Hardening-Optionen.

> Umsetzung 2026-04-21: Unit auf dedizierten Service-User `beagle-manager` umgestellt (`User/Group`), `SupplementaryGroups=libvirt kvm` gesetzt, `Restart=on-failure` + `RestartSec=5` gesetzt, `CapabilityBoundingSet=` geleert und Beagle host-spezifische Write-Paths entfernt. Auf `srv1.beagle-os.com` per installiertem Script ausgerollt und verifiziert (`systemctl show` zeigt non-root + leeres Capability-Set, Service `active`).

---

## Testpflicht nach Abschluss

- [x] Alle API-Endpunkte antworten korrekt nach Refactoring (Smoke-Tests; reproduzierbar ueber `scripts/smoke-control-plane-api.sh`, auf `srv1.beagle-os.com` 2026-04-21 mit 13/13 Checks erfolgreich ausgefuehrt).
- [x] RBAC: unauthentizierter POST auf `/api/v1/vms` gibt 401 zurück.
- [x] RBAC: User ohne Admin-Rolle kann keine Settings ändern.
- [x] Audit-Log schreibt Entries bei VM-Start, VM-Stop, User-Create (Handler-Auditpfad erweitert: `vm.start|vm.stop|vm.reboot` aus VM-Power-Responses, `auth.user.create` mit Resource-Metadaten; validiert durch `tests/unit/test_audit_helpers.py` + `tests/unit/test_audit_log.py` lokal und auf `srv1`).
- [x] `journalctl -u beagle-control-plane` zeigt keine Unhandled-Exception-Traces (verifiziert auf `srv1.beagle-os.com`, 2026-04-21).
