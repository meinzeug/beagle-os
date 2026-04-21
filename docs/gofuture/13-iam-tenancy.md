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

- [ ] `beagle-host/services/oidc_service.py` anlegen: Authorization-Code-Flow mit PKCE.
- [ ] Web Console: "Mit OIDC anmelden" Button auf dem Login-Screen.

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

---

### Schritt 2 — SAML 2.0 SP-Implementierung

- [ ] `beagle-host/services/saml_service.py` anlegen (z.B. basierend auf `python3-saml`).
- [ ] Web Console: SAML-Login-Button und SP-Metadata-Download.

SAML 2.0 ist in Enterprise-Umgebungen mit Active Directory Federation Services
(ADFS) oder Azure AD als Identity Provider der vorherrschende Standard. Die Web Console
agiert als Service Provider (SP). Die SP-Metadata-XML wird automatisch generiert und
über die Web Console herunterladbar gemacht damit Admins sie beim IdP registrieren können.
Nach dem SAML-Assertion-Austausch werden Gruppen-Claims aus dem SAML-Attribut-Statement
extrahiert und auf Beagle-Rollen gemappt (Attribut-Mapping konfigurierbar).
SAML-Assertion-Signaturen werden strikt validiert; ungültige Signaturen werden mit
einem Audit-Event protokolliert und abgelehnt.

---

### Schritt 3 — SCIM 2.0 für User/Group-Lifecycle-Sync implementieren

- [ ] `beagle-host/services/scim_service.py` anlegen: SCIM 2.0 `/Users` und `/Groups` Endpoints.
- [ ] SCIM-Bearer-Token-Authentifizierung über separaten Admin-Token.

SCIM (System for Cross-domain Identity Management) ermöglicht die automatische
Synchronisation von Usern und Gruppen vom Identity Provider zu Beagle. Wenn ein
IT-Admin einen neuen User in Keycloak anlegt wird dieser automatisch als Beagle-User
angelegt (Just-in-Time-Provisioning). Wenn der User deaktiviert wird im IdP wird er
in Beagle ebenfalls deaktiviert und seine aktiven Sessions werden beendet.
SCIM-Endpoints folgen dem RFC 7643/7644-Standard. Der SCIM-Bearer-Token wird als
Admin-Credential in der Web Console konfiguriert. Group-zu-Role-Mapping wird
konfigurierbar gemacht.

---

### Schritt 4 — Tenant-Scope in allen mutierenden API-Endpoints durchsetzen

- [ ] RBAC-Middleware erweitern: jeder mutierende Endpoint prüft `tenant_id` aus Token-Claims gegen Resource-Ownership.
- [ ] Automatisierter Test: "cross-tenant access denied" für alle mutierende Endpunkte.

Mandantenfähigkeit bedeutet dass Daten eines Tenants für andere Tenants unsichtbar
und unzugänglich sind. Dies muss auf API-Ebene erzwungen werden nicht nur in der UI.
Die RBAC-Middleware liest die `tenant_id` aus dem JWT-Token (oder OIDC-/SAML-Claim)
und filtert alle Resource-Queries automatisch auf diesen Tenant. Mutations-Operationen
prüfen zusätzlich dass die zu ändernde Resource zum selben Tenant gehört. Ein
automatisierter Testsuite mit "cross-tenant"-Fixtures stellt sicher dass kein
Endpoint akzidentell cross-tenant-Zugriff erlaubt. Platform-Admins mit `global`-Scope
können explizit Tenant-Boundaries überschreiben (dokumentiert im Audit-Log).

---

### Schritt 5 — Granulare Policy-Engine mit Permission-Tags

- [ ] `beagle-host/services/authz_policy.py` erweitern: Permission-Tag-Hierarchie (`cluster:read|write`, `pool:create|delete`, etc.).
- [ ] Rollen-Editor in Web Console zeigt Permission-Tags als Checkboxen.

Das bestehende rollenbasierte Modell (`admin`, `user`) reicht für Enterprise-Szenarien
nicht aus. Die granulare Policy-Engine erlaubt Custom Roles mit beliebigen Kombinationen
von Permission-Tags. Ein `pool-operator` darf z.B. `pool:read|create|update|scale`
aber nicht `pool:delete` oder `user:create`. Permission-Tags sind hierarchisch organisiert
(Komplex: `vm:*` erlaubt alle VM-Aktionen; Einzeln: `vm:power` nur Start/Stop).
Built-in-Rollen (`platform-admin`, `tenant-admin`, `pool-operator`, `support`, `user`)
sind unveränderlich und als Ausgangspunkt für Custom Roles dokumentiert.
Custom Roles werden per API und Web Console verwaltet.

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

## Testpflicht nach Abschluss

- [ ] Keycloak-OIDC-Login: User loggt sich ein, JWT-Claims korrekt gemappt, Session erstellt.
- [ ] SCIM: User in Keycloak anlegen → nach Sync in Beagle sichtbar.
- [ ] Tenant-Isolation: User von Tenant A kann Pool von Tenant B nicht lesen.
- [ ] Custom Role: `pool-operator` darf Pool skalieren aber nicht löschen.
- [ ] SAML-Assertion mit falscher Signatur wird abgelehnt und Audit-Event erzeugt.
