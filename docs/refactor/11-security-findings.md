# Security Findings

Stand: 2026-04-19

## Zweck

- Diese Datei sammelt alle waehrend der laufenden Refactor-Arbeit gefundenen Sicherheitsprobleme, Secret-Leaks, unsicheren Defaults und offenen Hardening-Punkte.
- Jeder neue Fund muss hier mit Status, Auswirkung und naechstem Schritt eingetragen werden.
- Wenn ein Fund im selben Run sicher und reproduzierbar behebbar ist, wird er direkt gepatcht und hier als mitigiert dokumentiert.

## S-001 - Lokale Operator-Dateien waren im Git-Tracking

- Status: mitigiert im Workspace, Shared-Repo-Commit/Pull-Request noch erforderlich
- Risiko: Hoch
- Betroffene Dateien:
  - `AGENTS.md`
  - `CLAUDE.md`
- Beschreibung:
  - Beide lokalen Operator-Dateien waren im Git-Tracking und konnten dadurch versehentlich auf GitHub landen.
  - Dadurch besteht ein strukturelles Risiko, dass interne Arbeitsanweisungen, lokale Betriebsdetails oder spaeter eingetragene Zugangshinweise offengelegt werden.
- Mitigation:
  - `.gitignore` wurde um `AGENTS.md` und `CLAUDE.md` erweitert.
  - `AGENTS.md` und `CLAUDE.md` wurden aus dem Git-Index entfernt und lokal beibehalten.
  - Diese Dateien muessen aus dem Git-Tracking entfernt bleiben.
  - `AGENTS.md` wurde explizit um die Regel erweitert, dass beide Dateien lokal-only sind.
- Naechster Schritt:
  - Sicherstellen, dass die Tracking-Entfernung committed und nach GitHub gepusht wird.

## S-002 - Klartext-Secrets duerfen nicht in versionierte Repo-Dateien

- Status: aktiv als Guardrail
- Risiko: Hoch
- Beschreibung:
  - Im Rahmen von Live-Betrieb, Deployments und Multi-Agent-Arbeit tauchen regelmaessig Zugriffswege, Hostnamen und Credentials auf.
  - Wenn diese als Klartext in versionierten Repo-Dateien landen, entsteht sofort ein Secret-Leak-Risiko fuer GitHub, Releases und Forks.
- Mitigation:
  - Sicherheitsregel in `AGENTS.md` verankert: keine Klartext-Passwoerter oder Zugangsdaten in commitbare Dateien.
  - Lokale Operator-Hinweise duerfen nur in nicht versionierten Dateien stehen.
  - SSH-Zugriff auf `srv1.meinzeug.cloud` erfolgt lokal ueber den Alias `ssh meinzeug` mit lokalem Key statt ueber Repo-dokumentierte Passwoerter.
- Naechster Schritt:
  - Repo gezielt nach weiteren potenziellen Klartext-Secrets, Tokens oder sensiblen Operator-Hinweisen durchsuchen und bereinigen.

## S-003 - Installimage source bundle enthaelt lokale Operator-Dateien

- Status: mitigiert, neu gebaut, verifiziert und als `6.6.9` veroeffentlicht
- Risiko: Hoch
- Betroffene Dateien:
  - `scripts/build-server-installimage.sh`
  - eingebettetes Archiv `/usr/local/share/beagle/beagle-os-source.tar.gz` innerhalb des installimage-Tarballs
- Beschreibung:
  - Der erste Build des neuen Hetzner-installimage-Artefakts hat die lokalen Dateien `AGENTS.md` und `CLAUDE.md` in das eingebettete Beagle-Source-Archiv aufgenommen.
  - Dadurch waeren lokale Operator-Hinweise ueber das oeffentlich verteilte installimage-Artefakt weitergegeben worden.
- Mitigation:
  - Builder wurde direkt gepatcht, sodass nur explizit erlaubte Repo-Pfade gebuendelt werden und `AGENTS.md` / `CLAUDE.md` nicht mehr Teil des Source-Bundles sind.
  - Das korrigierte `Debian-1201-bookworm-amd64-beagle-server.tar.gz` wurde fuer `6.6.9` neu gebaut, gegen den eingebetteten Source-Tarball verifiziert und auf `beagle-os.com` veroeffentlicht.
  - Die installierte Hetzner-Zielmaschine wurde auf dieses Artefakt aktualisiert.
- Naechster Schritt:
  - GitHub Release Assets nachziehen, sobald ein authentifizierter Release-Upload-Pfad verfuegbar ist.

## S-004 - Public source/server-installer bundles enthielten lokale Operator-Dateien

- Status: mitigiert im Workspace und in `6.6.9` Release-Artefakten, GitHub-Push noch erforderlich
- Risiko: Hoch
- Betroffene Dateien:
  - `scripts/package.sh`
  - `scripts/build-server-installer.sh`
  - `beagle-os-v*.tar.gz`
  - server-installer embedded source archive
- Beschreibung:
  - Neben dem installimage-Pfad waren auch das public source tarball Packaging und der server-installer embedded source bundle fuer lokale Operator-Dateien anfaellig.
  - Dadurch haetten `AGENTS.md` oder `CLAUDE.md` ueber allgemeine Release-Artefakte oder Server-Installer-ISO-Inhalte veroeffentlicht werden koennen.
- Mitigation:
  - `scripts/package.sh` und `scripts/build-server-installer.sh` wurden auf explizite erlaubte Repo-Pfade ohne `AGENTS.md` / `CLAUDE.md` umgestellt.
  - `beagle-os-v6.6.9.tar.gz` und das `6.6.9` installimage embedded source bundle wurden lokal auf Abwesenheit dieser Dateien geprueft.
- Naechster Schritt:
  - Repo-Aenderungen nach GitHub pushen, damit die Scrubbing-Regeln nicht nur lokal und in den gebauten Artefakten existieren.

## S-005 - Security/TLS WebUI scheiterte auf frischen Hosts an unvollstaendiger Let's-Encrypt Runtime und Service-Sandbox

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel bis Hoch
- Betroffene Dateien:
  - `beagle-host/services/server_settings.py`
  - `beagle-host/systemd/beagle-control-plane.service`
  - `scripts/install-beagle-host-services.sh`
  - `scripts/install-beagle-proxy.sh`
  - `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer`
- Beschreibung:
  - Die Security-Einstellungen konnten auf einem frisch installierten Standalone-Host kein Let's-Encrypt-Zertifikat ausstellen.
  - Root Cause 1: `certbot` und `python3-certbot-nginx` wurden in den kanonischen Host-/Installer-Pfaden nicht zuverlaessig mitinstalliert.
  - Root Cause 2: selbst nach Paketinstallation scheiterte der API-Pfad innerhalb des gehaerteten `beagle-control-plane.service`-Sandboxes bei `certbot --nginx`, weil Let's-Encrypt- und nginx-Logpfade nicht im gleichen Ausfuehrungskontext nutzbar waren.
- Mitigation:
  - Installpfade wurden auf automatische Installation von `certbot` und `python3-certbot-nginx` erweitert.
  - `server_settings.py` prueft nun explizit auf fehlendes `certbot` bzw. fehlenden nginx-Plugin-Support und liefert klare Fehlerbilder.
  - `server_settings.py` schaltet nginx nach erfolgreicher Zertifikatserstellung jetzt aktiv auf die Let's-Encrypt-Pfade um (`fullchain.pem`/`privkey.pem`), prueft die Konfiguration mit `nginx -t` und laedt nginx neu.
  - Damit wird verhindert, dass ein gueltiges LE-Zertifikat zwar ausgestellt ist, aber weiterhin ein Self-Signed-Zertifikat ausgeliefert wird.
  - TLS-Issuance laeuft bevorzugt ueber einen transienten `systemd-run` Prozess, damit die Funktion mit bestehender Service-Haertung kompatibel bleibt.
  - `ReadWritePaths=` des Control-Plane-Services wurde fuer relevante Let's-Encrypt/nginx-Pfade erweitert.
  - Live auf `srv1.beagle-os.com` verifiziert: externer TLS-Handshake liefert Issuer `Let's Encrypt (E8)`, nginx referenziert LE-Pfade, Status meldet `provider=letsencrypt`, Zertifikat vorhanden, nginx TLS aktiv.
- Naechster Schritt:
  - Den Fix ueber neu gebaute Installer-Artefakte ausrollen und einen Regressionstest fuer den Security/TLS-Pfad ergaenzen.

## S-006 - Control-Plane API ohne harte Gateway-Guards (Rate-Limit/Brute-Force/Error-Schema)

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Hoch
- Betroffene Dateien:
  - `beagle-host/bin/beagle-control-plane.py`
  - `scripts/install-beagle-host-services.sh`
- Beschreibung:
  - Die API hatte zuvor kein durchgaengiges Request-Rate-Limit auf allen `/api/*`-Routen.
  - Login-Fehlversuche wurden nicht mit serverseitigem Exponential-Backoff + Lockout begrenzt.
  - Error-Responses waren teilweise ohne einheitliches `code`-Feld.
  - Unbehandelte Exceptions hatten keine zentrale Sanitization-Grenze.
- Mitigation:
  - Python-Middleware-Rate-Limit fuer alle API-Endpunkte implementiert (`BEAGLE_API_RATE_LIMIT_WINDOW_SECONDS`, `BEAGLE_API_RATE_LIMIT_MAX_REQUESTS`).
  - Login-Brute-Force-Schutz mit Exponential-Backoff und Lockout implementiert (`BEAGLE_AUTH_LOGIN_LOCKOUT_THRESHOLD`, `BEAGLE_AUTH_LOGIN_LOCKOUT_SECONDS`, `BEAGLE_AUTH_LOGIN_BACKOFF_MAX_SECONDS`).
  - Access-Token-Default auf 15 Minuten gehaertet (`BEAGLE_AUTH_ACCESS_TTL_SECONDS=900`).
  - Einheitliches Error-Schema durch automatisches `code`-Feld auf Fehler-Payloads ergaenzt.
  - Zentrale Exception-Grenze (`handle_one_request`) liefert sanitisiertes 500-JSON (`internal_error`).
  - Strukturierte JSON-Response-Logs enthalten jetzt `user`, `action`, `resource_type`, `resource_id`.
- Validierung:
  - `srv1`: `/api/v1/auth/me` liefert `401` mit `code=unauthorized`.
  - `srv1`: wiederholte falsche Logins liefern `429` mit `code=rate_limited` und `retry_after_seconds`.
  - `srv1`: bei temporaerem Limit `BEAGLE_API_RATE_LIMIT_MAX_REQUESTS=5` schaltet API reproduzierbar auf `429 rate_limited` nach mehreren Requests.
  - Env-Werte auf `srv1` geprueft und auf Produktionswert (`240`) zurueckgesetzt.
- Naechster Schritt:
  - Refresh-Token auf HTTP-only/SameSite=Strict Cookie-Flow umstellen (aktuell noch offen in GoFuture 20, Schritt 2).

## S-007 - Fehlende serverseitige Payload-Whitelist/Identifier-Validation in Auth-POST-Routen

- Status: mitigiert in Repo und auf `srv1.beagle-os.com`
- Risiko: Mittel bis Hoch
- Betroffene Dateien:
  - `beagle-host/bin/beagle-control-plane.py`
  - `beagle-host/services/auth_session.py`
  - `tests/unit/test_auth_session.py`
- Beschreibung:
  - Mehrere Auth-POST-Routen akzeptierten bislang zusaetzliche oder ungueltige Felder ohne strikte Whitelist-Pruefung.
  - Identifier-Checks waren nicht durchgaengig serverseitig erzwungen (z.B. User-/Role-Namen mit ungueltigen Zeichen).
- Mitigation:
  - Control-Plane hat jetzt Whitelist-Schema-Pruefung fuer zentrale Auth-POST-Routen (`login`, `refresh`, `logout`, `onboarding/complete`, `auth/users`, `auth/roles`).
  - Serverseitige Identifier-Sanitizer in Handler + Auth-Session-Service ergaenzt.
  - `AuthSessionService` erzwingt `USERNAME_PATTERN`/`ROLE_NAME_PATTERN` in `create_user`, `update_user`, `save_role`, `complete_onboarding`, `login`.
  - Unit-Tests um negative Faelle erweitert (`invalid username`, `invalid role name`).
- Validierung:
  - Lokal: `python -m unittest tests.unit.test_auth_session` -> OK.
  - `srv1`: `/api/v1/auth/onboarding/complete` mit `username="bad user"` liefert `400` + `code=bad_request`.
  - `srv1`: `/api/v1/auth/login` mit zusaetzlichem Feld `extra` liefert `400` + `invalid payload: unexpected keys`.

## S-008 - Fehlende automatisierte Dependency-Audit-Integration

- Status: mitigiert (Automation vorhanden), Findings offen
- Risiko: Mittel
- Betroffene Dateien:
  - `scripts/security-audit.sh`
  - `.github/workflows/security-audit.yml`
  - `.gitignore`
- Beschreibung:
  - Es fehlte ein reproduzierbarer, regelmaessig laufender CVE-Check fuer Python- und Node-Abhaengigkeiten.
- Mitigation:
  - Neues Skript `scripts/security-audit.sh` hinzugefuegt (`pip-audit` + `npm audit`, Report-Ausgabe nach `dist/security-audit/`).
  - Neuer GitHub-Workflow `.github/workflows/security-audit.yml` mit monatlichem Schedule + manuellem Trigger + Report-Artefakt-Upload.
  - `.gitignore` um `.env` / `.env.*` erweitert.
- Validierung:
  - Lokal ausgefuehrt (`BEAGLE_SECURITY_AUDIT_STRICT=0 scripts/security-audit.sh`).
  - Ergebnis: bekannte Vulnerabilities gemeldet (`pip` im venv; npm audit findings im `beagle-kiosk`-Scope) und als Reports gespeichert.
- Naechster Schritt:
  - `pip` im Runtime-/CI-Umfeld auf gefixte Version anheben,
  - npm findings im `beagle-kiosk` aufloesen oder begruendete Ignore-Liste mit Ablaufdatum einfuehren.
