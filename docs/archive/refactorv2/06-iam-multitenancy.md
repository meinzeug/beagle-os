# 06 — Identitaet, RBAC, Mandantenfaehigkeit

Stand: 2026-04-20

## Stand heute

- Lokale User + Onboarding-Flow (`services/auth_session.py`, `services/policy_store.py`, `services/authz_policy.py`).
- API-Token-Modell (`BEAGLE_MANAGER_API_TOKEN`).
- Roles + Scopes nicht durchgaengig auf alle Mutations-Endpunkte erzwungen (siehe `docs/refactor/01-problem-analysis.md`).

## Ziel 7.0

### Identity Provider

- Lokaler IdP bleibt Default.
- **OIDC-Login** als Erste-Klasse-Option (Authorization Code + PKCE).
- **SAML-Login** fuer Enterprise.
- **SCIM 2.0** fuer User/Group-Lifecycle (Just-in-Time-Provisioning).
- Multi-IdP gleichzeitig (z.B. local + OIDC + SAML).

Pflicht-Tests:

- Keycloak (selfhosted, Open Source Referenz).
- Authentik.
- Microsoft Entra ID.
- Google Workspace.

### Tenancy

- `Tenant` ist Top-Level-Namespace.
- Jeder Pool, Template, StorageClass, NetworkZone, FirewallProfile, User, Entitlement gehoert zu genau einem Tenant **oder** ist global.
- API-Routen erhalten implicit Tenant-Scope ueber Login-Kontext.
- Operatoren mit `role: platform-admin` koennen Tenant-Scope ueberschreiben.

### Rollenmodell

Vorschlag fuer Built-in Rollen:

| Rolle | Scope | Berechtigungen |
|---|---|---|
| `platform-admin` | global | alles, inkl. Cluster, Tenants |
| `tenant-admin` | tenant | Pools, Templates, Users, Entitlements im eigenen Tenant |
| `pool-operator` | tenant.pool | Lifecycle eigener Pools, kein User-CRUD |
| `support` | tenant | read-only + Session-Console-Zugang |
| `auditor` | global oder tenant | read-only Audit + Recordings |
| `user` | self | eigenen Desktop streamen, eigenes Profil verwalten |

Custom Roles ueber `RolePolicy` mit Permission-Tags.

### Permission-Tags

Beispielhafte Tag-Hierarchie:

- `cluster:read|write`
- `node:read|write|drain`
- `pool:read|create|update|delete|scale|recycle`
- `template:read|create|update|delete|publish`
- `vm:read|create|update|delete|power|console|stream`
- `session:read|terminate|record|download_recording`
- `user:read|create|update|delete|impersonate`
- `entitlement:read|create|delete`
- `network:read|write`
- `storage:read|write|snapshot|restore`
- `backup:read|create|restore|delete`
- `audit:read|export`

### Policies (Stream-Verhalten)

Pro User/Gruppe/Pool/Tenant kombinierbar:

- Clipboard: `none|host_to_guest|guest_to_host|bidirectional`
- USB-Redirect-Klassen: `hid`, `mass_storage`, `audio`, `printer`, `smartcard`, `wacom`, `gamepad`, `webcam`
- Watermark: bool + Template
- Session Recording: `off|on_demand|always`
- Idle Timeout (min)
- Absolute Session Timeout (min)
- Max Concurrent Sessions per User

### Audit

Jeder mutierende Endpunkt schreibt:

```json
{
  "ts": "2026-04-20T17:24:00Z",
  "actor": {"id": "alice@acme", "tenant": "acme", "via": "oidc:keycloak"},
  "action": "pool.scale",
  "subject": {"type": "DesktopPool", "id": "pool-engineering"},
  "params": {"from": 5, "to": 8},
  "result": "ok",
  "request_id": "req-...",
  "ip": "10.0.0.5",
  "ua": "BeagleConsole/7.0"
}
```

Audit-Sink-Konfiguration:

- file (rotated json),
- syslog,
- S3-bucket,
- webhook.

### Sicherheit

- Sessions: `Secure`, `HttpOnly`, `SameSite=Lax`, kurze Access-Token-Lebensdauer + Refresh.
- Refresh-Tokens an Endpoint-Fingerprint gebunden.
- Brute-Force-Schutz (rate limit + lockout) im API-Gateway.
- Passwort-Policy konfigurierbar pro Tenant.
- WebAuthn/Passkeys als optionaler 2. Faktor.
- API-Tokens scoped + revokable + auditiert.

### Migration heute -> 7.0

- 7.0.0: Cluster-State traegt jetzt User-/Role-Daten -> Migration der bestehenden lokal gespeicherten Identitaeten in den Cluster-Store.
- 7.2.0: OIDC-Adapter wird ergaenzt; lokaler Login bleibt fuer Bootstrap.
- Bestehende API-Tokens funktionieren weiter, werden aber sukzessive durch scoped tokens abgeloest.
