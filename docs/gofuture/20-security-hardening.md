# 20 — Security Hardening (alle Phasen)

Stand: 2026-04-20  
Priorität: Kontinuierlich (Nebenbedingung jedes Runs)  
Referenz: `docs/refactorv2/12-security-compliance.md`, `docs/refactor/11-security-findings.md`

---

## Grundsatz

Security ist keine spätere Phase sondern Nebenbedingung jedes einzelnen Änderungs-
Schritts. Diese Checkliste wird bei jedem größeren Arbeitsschritt als Referenz
verwendet. Neue Security-Funde landen immer in `docs/refactor/11-security-findings.md`.

---

## Schritte

### Schritt 1 — API-Gateway-Härtung

- [x] Rate-Limiting auf alle API-Endpoints via nginx oder Python-Middleware.
- [x] Brute-Force-Schutz auf Login-Endpoint: Exponential Backoff + Lockout nach N Fehlversuchen.

Ohne Rate-Limiting ist jeder API-Endpoint anfällig für Credential-Stuffing- und Brute-Force-Angriffe.
Ein einfaches Rate-Limit (z.B. 10 Requests/Sekunde pro IP auf `/api/v1/auth/login`)
über nginx `limit_req_zone` ist in 30 Minuten implementierbar. Für den Login-Endpoint
ist zusätzlich ein Brute-Force-Counter pro Nutzerkonto notwendig. Nach 5 Fehlversuchen
innerhalb von 60 Sekunden sollte der Account für 5 Minuten gesperrt werden (Soft-Lock).
Die Lockout-State wird im Beagle-internen State (Memory oder DB) gehalten damit ein
Neustart des Control Plane das Lockout nicht zurücksetzt. Alle Lockout-Ereignisse
erzeugen Audit-Events. Die bestehende JavaScript-seitige Auth-Lock-Logik ist nur UX,
kein Sicherheitsmerkmal.

---

### Schritt 2 — Token-Management hardenen

- [x] JWT Access-Token Lebensdauer: <= 15 Minuten.
- [x] Refresh-Token: HTTP-only, SameSite=Strict Cookie; keine localStorage-Speicherung.

Kurze Access-Token-Lebenszeiten begrenzen das Angriffsfenster bei Token-Diebstahl.
15 Minuten ist der Industriestandard für Access-Tokens in Web-Anwendungen. Refresh-
Tokens müssen als HTTP-only Cookies übertragen werden damit sie nicht per XSS-Angriff
ausgelesen werden können. `SameSite=Strict` verhindert CSRF-Angriffe auf die
Refresh-Token-Route. In `localStorage` gespeicherte Refresh-Tokens sind durch jedes
JavaScript-Snippet auf der Seite lesbar (XSS-Risiko). Falls Refresh-Tokens aktuell
in localStorage liegen muss das sofort korrigiert werden.

---

### Schritt 3 — Content-Security-Policy (CSP) verschärfen

- [x] CSP-Header in nginx: `script-src 'self'`, `style-src 'self'`, `img-src 'self' data:`, `connect-src 'self' wss:`.
- [x] Keine `'unsafe-inline'`, kein `'unsafe-eval'`.

Die CSP verhindert XSS-Angriffe indem sie dem Browser vorschreibt welche Ressourcen
er laden und ausführen darf. `'unsafe-inline'` und `'unsafe-eval'` heben den XSS-Schutz
faktisch auf und dürfen nicht gesetzt sein. Inline-Event-Handler in HTML (`onclick=...`)
sind mit strikter CSP nicht vereinbar und müssen durch JavaScript-Event-Listener
ersetzt werden. Data-URIs für Bilder (`img-src 'self' data:`) sind für kleine Icons
akzeptabel. WebSocket-Verbindungen für Live-Updates müssen explizit in `connect-src`
erlaubt sein (`wss://`). Der aktuelle CSP-Stand ist in `/memories/repo/csp-source-of-truth.md`
dokumentiert und bei jeder Änderung zu aktualisieren.

---

### Schritt 4 — Secrets-Management

- [ ] Alle Secrets (DB-Passwörter, API-Keys, Signing-Keys) aus Code und Config-Dateien in Umgebungsvariablen oder Secret-Store verlagern.
- [ ] `.gitignore` prüfen: keine `.env`-Dateien mit Secrets im Repo.

Klartext-Secrets in versionierten Dateien sind der häufigste Ursache für
Security-Incidents in Open-Source-Projekten. Ein Secret-Scanner (z.B. `gitleaks`,
`truffleHog`) läuft als Pre-Commit-Hook und verhindert versehentliches Committen.
Secrets werden über Umgebungsvariablen oder (für Produktionsdeployments) über einen
Secret-Store (HashiCorp Vault, systemd-Credentials, oder einfache verschlüsselte
env-Datei) bereitgestellt. Default-Werte in Config-Templates niemals mit echten
Secrets befüllen; Platzhalter wie `CHANGE_ME` oder `REQUIRED` verwenden.

---

### Schritt 5 — NoVNC-Proxy und Console-Zugang absichern

- [x] Console-Token-Generator: Single-Use-Token mit <= 30s TTL für noVNC-Session.
- [x] noVNC-Proxy akzeptiert nur validierte, nicht-wiederverwendbare Tokens.

Der noVNC-Proxy gibt Zugang zur VM-Console und ist damit ein hochsensibles Medium.
Ein statisches oder langlebiges Token für alle Console-Zugänge ist ein kritisches
Sicherheitsrisiko. Single-Use-Tokens für jeden Console-Öffnungs-Vorgang begrenzen
das Angriffsfenster auf 30 Sekunden. Das Token wird beim Ablauf oder nach einmaliger
Verwendung invalidiert. Der noVNC-Proxy prüft das Token gegen den Control Plane;
bei ungültigem Token wird die Verbindung sofort getrennt. Der aktuelle Stand dieser
Sicherung ist in `/memories/repo/novnc-readwritepaths.md` dokumentiert.

---

### Schritt 6 — Systemd-Unit-Hardening für alle Beagle-Services

- [x] Jede systemd-Unit bekommt: `NoNewPrivileges=yes`, `PrivateTmp=yes`, `RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6`, `CapabilityBoundingSet`.
- [x] Kein Service läuft als root wenn nicht zwingend erforderlich.

Systemd bietet umfangreiche Sandboxing-Optionen die bei korrekter Anwendung erheblich
den Blast-Radius eines kompromittierten Services begrenzen. `NoNewPrivileges=yes` verhindert
Privilege-Escalation via setuid-Binaries. `PrivateTmp=yes` isoliert `/tmp`. `ProtectSystem=strict`
macht das Dateisystem read-only außer explizit freigegebenen Pfaden. `ProtectHome=yes`
verhindert Zugriff auf Home-Verzeichnisse. Die Capabilities werden mit
`CapabilityBoundingSet=` auf das absolut Minimum beschränkt. Services die keine
Netzwerkkommunikation brauchen bekommen `PrivateNetwork=yes`.

---

### Schritt 7 — Dependency-Updates und CVE-Scanning

- [x] `requirements.txt` (Python) und `package.json` (Node.js) monatlich auf CVEs prüfen.
- [x] `pip-audit` oder `safety` für Python, `npm audit` für Node.js in CI integrieren.

Bekannte CVEs in Abhängigkeiten sind einer der am einfachsten ausnutzbaren Angriffsvektoren.
Automatisches CVE-Scanning in CI warnt bei jeder Code-Änderung wenn eine bekannte
Schwachstelle in einer Abhängigkeit vorhanden ist. `pip-audit` prüft Python-Pakete
gegen die OSV-Datenbank. `npm audit` tut dasselbe für Node.js-Pakete. Kritische CVEs
(CVSS >= 9.0) blockieren den Build bis sie behoben sind. High-CVEs (CVSS 7–8.9)
erzeugen eine Warnung. Die Ergebnisse werden in einem `security-report.md` im
`docs/` Verzeichnis festgehalten.

---

### Schritt 8 — Penetration-Test-Checkliste und Bug-Bounty-Vorbereitung

- [ ] OWASP Top 10 Checkliste für alle API-Endpoints und Web-Console durcharbeiten.
- [ ] `docs/refactor/11-security-findings.md` mit vollständiger OWASP-Abdeckung aktualisieren.

Vor dem ersten öffentlichen Release muss eine strukturierte Security-Review stattfinden.
Die OWASP Top 10 ist der Mindeststandard für Web-Anwendungen. Besonders relevant für
Beagle: A1 (Broken Access Control — RBAC-Lücken), A2 (Cryptographic Failures — Token-
Handling), A3 (Injection — VM-Namen-Validation), A5 (Security Misconfiguration —
Default-Credentials), A8 (Software and Data Integrity Failures — Update-Signaturen).
Ein strukturiertes Bug-Bounty-Programm (HackerOne oder ähnlich) ist langfristig geplant
und erfordert eine vollständige Scope-Definition und einen klaren Responsible-Disclosure-
Prozess. Diese Schritte werden vor dem 7.0-Release abgearbeitet.

---

## Laufende Pflichten (nach jedem Arbeitsschritt zu prüfen)

- [x] Neue Secrets in nicht-commitete Konfiguration? (kein `.env` im Repo)
- [x] Neuer Code prüft Input-Validierung an API-Boundaries?
- [ ] Neue RBAC-Prüfung für neuen Endpoint implementiert?
- [x] Security-Funde in `docs/refactor/11-security-findings.md` eingetragen?
- [x] Neue Abhängigkeiten auf bekannte CVEs geprüft?
