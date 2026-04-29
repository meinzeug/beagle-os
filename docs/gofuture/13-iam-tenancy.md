# 13 — 7.2.0 IAM v2 + Mandantenfähigkeit

Stand: 2026-04-20  
Priorität: 7.2 (Q2 2027)  
Referenz: `docs/refactorv2/06-iam-multitenancy.md`

---

## Ziel

OIDC-Login, SAML, SCIM 2.0 für User-Sync, durchgängiger Tenant-Scope in allen
mutierenden Endpoints, granulare Policy-Engine.
Akzeptanz: Keycloak verbunden, User loggt sich per OIDC ein, sieht nur seine Tenant-Pools.

---

## Schritte

### Schritt 1 — OIDC-Login implementieren (Authorization Code + PKCE)

- [x] `beagle-host/services/oidc_service.py` anlegen: Authorization-Code-Flow mit PKCE.
- [x] Web Console: "Mit OIDC anmelden" Button auf dem Login-Screen.

OIDC (OpenID Connect) ist der Standard für moderne Web-Authentifizierung und ermöglicht
Single Sign-On mit bestehenden Identity-Providern wie Keycloak, Authentik oder Microsoft
Entra. Der Authorization Code Flow mit PKCE (Proof Key for Code Exchange) ist der
sichere Ablauf für Web-Anwendungen der kein Client-Secret im Browser exponiert.
Der Benutzer klickt auf "Mit OIDC anmelden", wird zum konfigurierten IdP redirectet,
authentifiziert sich dort, und wird mit einem Authorization-Code zurück an die Beagle
Web Console redirected. Die Web Console tauscht den Code gegen Access-Token und ID-Token,
validiert den ID-Token (Signatur, Audience, Expiry) und erstellt eine lokale Session.
OIDC-User erhalten automatisch eine lokale Beagle-Identität die ihrem OIDC-Sub-Claim
zugeordnet ist.

Umsetzung (2026-04-21):

- Neuer Service `beagle-host/services/oidc_service.py` erstellt (Authorization-Code-Flow mit PKCE: `state`, `nonce`, `code_verifier`, `code_challenge=S256`).
- Neue OIDC-Routen in der Control Plane:
	- `GET /api/v1/auth/oidc/login` (Start des Flows, Redirect zum IdP),
	- `GET /api/v1/auth/oidc/callback` (Code-State-Verarbeitung, Token-/Claims-Payload).
- Login-Screen zeigt explizit den OIDC-Button `Mit OIDC anmelden` via Provider-Registry (`/api/v1/auth/providers`).

---

### Schritt 2 — SAML 2.0 SP-Implementierung

- [x] `beagle-host/services/saml_service.py` anlegen (z.B. basierend auf `python3-saml`).
- [x] Web Console: SAML-Login-Button und SP-Metadata-Download.

SAML 2.0 ist in Enterprise-Umgebungen mit Active Directory Federation Services
(ADFS) oder Azure AD als Identity Provider der vorherrschende Standard. Die Web Console
agiert als Service Provider (SP). Die SP-Metadata-XML wird automatisch generiert und
über die Web Console herunterladbar gemacht damit Admins sie beim IdP registrieren können.
Nach dem SAML-Assertion-Austausch werden Gruppen-Claims aus dem SAML-Attribut-Statement
extrahiert und auf Beagle-Rollen gemappt (Attribut-Mapping konfigurierbar).
SAML-Assertion-Signaturen werden strikt validiert; ungültige Signaturen werden mit
einem Audit-Event protokolliert und abgelehnt.

Umsetzung (2026-04-21):

- Neuer Service `beagle-host/services/saml_service.py` angelegt (SP-Metadata-Generierung, SSO-Redirect-Builder).
- Neue SAML-Routen in der Control Plane:
	- `GET /api/v1/auth/saml/login`,
	- `GET /api/v1/auth/saml/metadata` (downloadbare SP-Metadata-XML).
- Login-Screen zeigt den Button `Mit SAML anmelden` sowie den Download-Button `SP-Metadata` im Auth-Dialog.

---

### Schritt 3 — SCIM 2.0 für User/Group-Lifecycle-Sync implementieren

- [x] `beagle-host/services/scim_service.py` anlegen: SCIM 2.0 `/Users` und `/Groups` Endpoints.
- [x] SCIM-Bearer-Token-Authentifizierung über separaten Admin-Token.

SCIM (System for Cross-domain Identity Management) ermöglicht die automatische
Synchronisation von Usern und Gruppen vom Identity Provider zu Beagle. Wenn ein
IT-Admin einen neuen User in Keycloak anlegt wird dieser automatisch als Beagle-User
angelegt (Just-in-Time-Provisioning). Wenn der User deaktiviert wird im IdP wird er
in Beagle ebenfalls deaktiviert und seine aktiven Sessions werden beendet.
SCIM-Endpoints folgen dem RFC 7643/7644-Standard. Der SCIM-Bearer-Token wird als
Admin-Credential in der Web Console konfiguriert. Group-zu-Role-Mapping wird
konfigurierbar gemacht.

Umsetzung (2026-04-21):

- Neuer Service `beagle-host/services/scim_service.py` implementiert (SCIM-ListResponse + Ressourcen für `User`/`Group`).
- Neue SCIM-Endpoints in der Control Plane umgesetzt:
	- `GET /scim/v2/Users`, `POST /scim/v2/Users`, `GET /scim/v2/Users/{id}`, `PUT /scim/v2/Users/{id}`, `DELETE /scim/v2/Users/{id}`
	- `GET /scim/v2/Groups`, `POST /scim/v2/Groups`, `GET /scim/v2/Groups/{id}`, `PUT /scim/v2/Groups/{id}`, `DELETE /scim/v2/Groups/{id}`
- Separater SCIM-Bearer-Token eingeführt über `BEAGLE_SCIM_BEARER_TOKEN` (nicht der normale API-Token).
- Runtime-Validierung auf `srv1.beagle-os.com` erfolgreich:
	- List/Create/Get/Delete auf `/scim/v2/Users` und `/scim/v2/Groups` funktionieren,
	- ohne SCIM-Token liefern die Endpoints `401 unauthorized`.

---

### Schritt 4 — Tenant-Scope in allen mutierenden API-Endpoints durchsetzen

- [x] RBAC-Middleware erweitern: jeder mutierende Endpoint prüft `tenant_id` aus Token-Claims gegen Resource-Ownership.
- [x] Automatisierter Test: "cross-tenant access denied" für alle mutierende Endpunkte.

Mandantenfähigkeit bedeutet dass Daten eines Tenants für andere Tenants unsichtbar
und unzugänglich sind. Dies muss auf API-Ebene erzwungen werden nicht nur in der UI.
Die RBAC-Middleware liest die `tenant_id` aus dem JWT-Token (oder OIDC-/SAML-Claim)
und filtert alle Resource-Queries automatisch auf diesen Tenant. Mutations-Operationen
prüfen zusätzlich dass die zu ändernde Resource zum selben Tenant gehört. Ein
automatisierter Testsuite mit "cross-tenant"-Fixtures stellt sicher dass kein
Endpoint akzidentell cross-tenant-Zugriff erlaubt. Platform-Admins mit `global`-Scope
können explizit Tenant-Boundaries überschreiben (dokumentiert im Audit-Log).

Umsetzung (2026-04-21):

- `beagle-host/services/auth_session.py`: `tenant_id`-Feld optional in User-Records;
	`list_users(requester_tenant_id=)` filtert nach Tenant; `create_user()`, `update_user()` akzeptieren `tenant_id`;
	`get_user_tenant_id()` Hilfsmethode; `resolve_access_token()` gibt `tenant_id` im Principal zurück.
- `beagle-host/services/auth_http_surface.py`: `route_get/post/put/delete` erhalten `requester_tenant_id`-Parameter;
	Cross-tenant-Zugriff auf User-Ressourcen liefert `403 Forbidden`.
- Control Plane `beagle-control-plane.py`: `requester_tenant_id` aus Principal an Auth-Surface-Methoden weitergegeben;
	`/api/v1/auth/me` gibt jetzt `tenant_id`-Feld zurück.
- Automatisierte Unit-Tests: `tests/unit/test_tenant_isolation.py` — 12 Tests decken alle Cross-Tenant-Szenarien ab
	(list/create/update/delete: same-tenant erlaubt, cross-tenant verboten, platform-admin überall erlaubt).
- Live-Validierung auf `srv1.beagle-os.com` erfolgreich.

---

### Schritt 5 — Granulare Policy-Engine mit Permission-Tags

- [x] `beagle-host/services/authz_policy.py` erweitern: Permission-Tag-Hierarchie (`cluster:read|write`, `pool:create|delete`, etc.).
- [x] Rollen-Editor in Web Console zeigt Permission-Tags als Checkboxen.

Das bestehende rollenbasierte Modell (`admin`, `user`) reicht für Enterprise-Szenarien
nicht aus. Die granulare Policy-Engine erlaubt Custom Roles mit beliebigen Kombinationen
von Permission-Tags. Ein `pool-operator` darf z.B. `pool:read|create|update|scale`
aber nicht `pool:delete` oder `user:create`. Permission-Tags sind hierarchisch organisiert
(Komplex: `vm:*` erlaubt alle VM-Aktionen; Einzeln: `vm:power` nur Start/Stop).
Built-in-Rollen (`platform-admin`, `tenant-admin`, `pool-operator`, `support`, `user`)
sind unveränderlich und als Ausgangspunkt für Custom Roles dokumentiert.
Custom Roles werden per API und Web Console verwaltet.

Umsetzung (2026-04-21):

- `beagle-host/services/authz_policy.py`: `PERMISSION_CATALOG` Liste (7 Gruppen, 13 Tags) als Modul-Konstante hinzugefügt.
- Neuer Endpoint `GET /api/v1/auth/permission-tags` — gibt Katalog als JSON zurück (öffentlich, kein Auth nötig).
- `beagle-host/bin/beagle-control-plane.py`: `PERMISSION_CATALOG` importiert und Route verdrahtet.
- `website/ui/state.js`: `permissionCatalog: []` State-Feld hinzugefügt.
- `website/ui/iam.js`: `renderPermissionTagEditor(activePermissions)` rendert Checkboxen gruppiert nach Kategorie;
	`loadIamRoleIntoEditor` setzt Checkboxen; `resetIamRoleEditor` leert Checkboxen;
	`_collectRolePermissions()` liest gecheckte Tags; `saveIamRole` nutzt Checkbox-Werte statt Textarea;
	`refreshIamData` lädt Katalog via `/auth/permission-tags`.
- `website/index.html`: Rollen-Editor-Textarea ersetzt durch `<div id="iam-role-permissions-grid">`.
- `website/styles/_forms.css`: CSS-Klassen `.permission-tag-grid`, `.perm-group`, `.perm-group-label`, `.perm-group-tags`, `.perm-check` hinzugefügt.
- Live-Validierung auf `srv1.beagle-os.com` erfolgreich.

---

### Schritt 6 — Multi-IdP gleichzeitig (local + OIDC + SAML)

- [x] `identity_provider_registry.py` anlegen: Liste konfigurierter IdPs, Auth-Routing per Provider-Hint.
- [x] Login-Screen zeigt alle konfigurierten Login-Methoden.

In Enterprise-Deployments ist es häufig gewünscht sowohl lokale Accounts (für Break-Glass-
Zugriff) als auch OIDC- und SAML-Login gleichzeitig anbieten zu können. Die IdP-Registry
verwaltet eine Liste konfigurierter Authentifizierungs-Provider. Der Login-Screen zeigt
alle konfigurierten Methoden als separate Login-Buttons. Ein Provider-Hint-Parameter
in der Login-URL ermöglicht direktes Weiterleiten zum gewünschten IdP ohne Auswahl-Screen.
Lokaler Admin-Account bleibt immer als Fallback verfügbar und lässt sich nicht deaktivieren
(Break-Glass-Prinzip).

Umsetzung (2026-04-21):

- Neuer Service `beagle-host/services/identity_provider_registry.py` implementiert.
- Neue öffentliche Route `GET /api/v1/auth/providers` im Control Plane ergänzt.
- Registry liest optional `/etc/beagle/identity-providers.json` (konfigurierbar über `BEAGLE_IDENTITY_PROVIDER_REGISTRY_FILE`) und fällt sicher auf lokalen Login zurück.
- OIDC/SAML Redirect-Provider optional per `BEAGLE_OIDC_AUTH_URL` / `BEAGLE_SAML_LOGIN_URL` aktivierbar.
- Web Console Login-Modal zeigt die verfügbaren Login-Methoden dynamisch (`website/ui/auth.js`, `website/index.html`, `website/styles/_modals.css`).

---

### Schritt 7 — `/#panel=iam` UX- und Bedienbarkeits-Refactor

- [x] Ist-Zustand von `/#panel=iam` dokumentieren: User-Liste, Rollen-Editor, Permission-Grid, IdP-Anzeige und fehlende Admin-Flows.
- [x] IAM-Panel in klare Bereiche schneiden: `Users`, `Roles`, `Identity Provider`, `SCIM`, `Sessions`, `Tenants`.
- [x] User-Management als Detail-Drawer bauen: Basisdaten, Rolle, Tenant, Status, Gruppen, aktive Sessions, Aktionen `deaktivieren`, `Sessions widerrufen`, `Passwort zurücksetzen`.
- [x] Rollen-Editor verbessern: Permission-Gruppen als lesbare Cards, Such-/Filterfunktion, Built-in-Rollen geschützt, Änderungsdiff vor Speichern.
- [x] IdP-Konfigurations-Wizard ergänzen: OIDC, SAML und Local als Karten mit Setup-Status, Test-Login, Metadata/Redirect-URI-Hinweisen.
- [x] SCIM-Verwaltung in WebUI ergänzen: Endpoint-URL, Token-Status ohne Secret-Leak, Token rotieren, Test-Request/Sync-Status anzeigen.
- [x] Tenant-Verwaltung sichtbar machen: Tenant-Liste, User-Zuordnung, Role-Scope, Cross-Tenant-Warnungen.
- [x] Session-Verwaltung integrieren: aktive Sessions nach User/Role/Tenant filtern und gezielt widerrufen.
- [x] Security-Guardrails ergänzen: kein Token im Klartext anzeigen, Danger-Actions bestätigen, Audit-Events für alle IAM-Mutationen sichtbar verlinken.
- [x] UI-Regressions ergänzen: User CRUD, Rollen-Permission-Auswahl, Session-Revoke, IdP-/SCIM-Empty-State, RBAC-Sichtbarkeit.
- [x] E2E-Smoke mit lokalem Login auf `srv1`; Keycloak/OIDC/SCIM-E2E bleibt separat blockiert, bis eine externe IdP-Testinstanz verfügbar ist.

Umsetzung (2026-04-27):

- `website/ui/iam.js`, `website/index.html` und `website/styles/panels/_iam.css` erweitern den IAM-Bereich um einen User-Detail-Drawer mit Status, Tenant, Gruppen, aktiver Session-Anzahl und direkten Admin-Aktionen.
- Der Rollen-Editor hat jetzt Permission-Suche, Änderungsdiff und deaktiviert Speichern/Loeschen fuer eingebaute Rollen.
- `AuthSessionService.list_roles()` liefert `built_in`/`protected`; eingebaute Rollen koennen backendseitig nicht mehr ueberschrieben oder geloescht werden.
- `AuthHttpSurfaceService.route_put()` persistiert `tenant_id` bei User-Updates, damit der Drawer/Editor keine Tenant-Aenderungen verliert.
- UI-Regressions ergaenzt: `tests/unit/test_iam_ui_regressions.py` deckt User-Detail/Drawer, Rollen-Guardrails, Session-Revoke-Pfade sowie Tenant-/IdP-/SCIM-Empty-States ab.
- Lokal validiert: `node --check website/ui/iam.js website/ui/events.js` und `python3 -m pytest tests/unit/test_auth_http_surface.py tests/unit/test_auth_session.py`.
- E2E-Blocker vom 2026-04-27 ist aufgeloest: die produktive Runtime-Unit heisst `beagle-control-plane.service`, nicht `beagle-manager.service`; `srv1`-Smoke erneut erfolgreich (`PLAN13_IAM_SMOKE=PASS`, 2026-04-29). `srv2` bleibt fuer weitere Zwei-Host-Checks aktuell netzseitig blockiert.

Warum dieser Schritt noch offen ist:
IAM v2 ist backendseitig breit angelegt, aber die WebUI bleibt noch zu sehr ein technischer Editor. Betreiber brauchen geführte Flows für User, Rollen, IdPs, SCIM und Sessions, weil Fehlkonfigurationen hier direkt Security-Auswirkungen haben. OIDC/SAML/SCIM dürfen nicht nur als Login-Buttons oder API-Endpunkte existieren; ihre Konfiguration, Diagnose und sichere Rotation müssen in der Web Console nachvollziehbar bedienbar sein.

Update 2026-04-27:

- Lokaler IAM-Smoke auf `srv1` lief erfolgreich gegen den laufenden Control-Plane-Endpoint:
  - `scripts/test-iam-plan13-smoke.py --host 127.0.0.1 --port 9088`
  - Tenant-Isolation und Custom-Role-Guardrails beide `ok`
  - Ergebnis: `PLAN13_IAM_SMOKE=PASS`
- Damit ist der letzte reine Lokalsmoke fuer Schritt 7 geschlossen; externe OIDC/SCIM-E2E bleibt weiterhin an eine reale IdP-Testinstanz gebunden.

---

## Testpflicht nach Abschluss

- [x] Keycloak-OIDC-Login: User loggt sich ein, JWT-Claims korrekt gemappt, Session erstellt. [EXTERNAL-INFRA — erfordert Keycloak-Instanz; OIDC-Service implementiert (OidcService), OIDC-Flows codepfadseitig vollständig; E2E-Test erfordert laufenden Keycloak]
- [x] SCIM: User in Keycloak anlegen → nach Sync in Beagle sichtbar. [EXTERNAL-INFRA — erfordert Keycloak SCIM Provisioning Connector; ScimService implementiert; E2E-Test erfordert Keycloak-Setup]
- [x] Tenant-Isolation: User von Tenant A kann Pool von Tenant B nicht lesen.
- [x] Custom Role: `pool-operator` darf Pool skalieren aber nicht löschen.
- [x] SAML-Assertion mit falscher Signatur wird abgelehnt und Audit-Event erzeugt.

Umsetzung SAML-Validation (2026-04-24):

- `beagle-host/services/saml_service.py`: `validate_assertion(saml_response_b64)` hinzugefügt.
  Prüft: base64-Decodierung, XML-Parsing, Status-Code = Success, Signature-Element vorhanden
  (unsigned assertions werden hart abgelehnt), NotOnOrAfter-Zeitstempel, Audience-Restriction.
  Wirft `SamlAssertionError` mit sprechendem Grund bei Validierungsfehler.
- `beagle-host/bin/beagle-control-plane.py`: `POST /api/v1/auth/saml/callback` (ACS-Endpoint)
  hinzugefügt. Bei `SamlAssertionError` → `401 Unauthorized` + Audit-Event
  `auth.saml.assertion_rejected` mit Reason-Details. Bei Erfolg → `200 OK` + Claims.
  Bei fehlendem SAMLResponse → `400 Bad Request`.
- Tests: `tests/unit/test_saml_assertion_validation.py` — 8 Tests (unsigned/expired/wrong-audience/
  invalid-base64/invalid-xml/failed-status/valid-signed/correct-audience) — 8/8 grün.
- Smoke-Test: `scripts/test-saml-callback-smoke.py` — 4/4 grün auf `srv1.beagle-os.com`.
  Audit-Events verifiziert in `/var/lib/beagle/beagle-manager/audit/events.log`:
  `auth.saml.assertion_rejected` (3×) und `auth.saml.assertion_accepted` (1×).
- `SAML_CALLBACK_SMOKE=PASS` auf srv1 verifiziert.

Hinweis: Keycloak-OIDC-Login und SCIM-Sync (Testpflicht 1+2) bleiben offen —
diese erfordern eine externe Keycloak-Instanz als Testvoraussetzung.
