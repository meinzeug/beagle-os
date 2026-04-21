# 12 — Security und Compliance

Stand: 2026-04-20

Erweitert `docs/refactor/11-security-findings.md` um Architektur-Pflichten der Welle 2.

## Pflichtprinzipien

- **Default Deny** an jeder Vertrauensgrenze (API, network, USB).
- **Least Privilege** fuer Operatoren, Services und VMs.
- **Verifiable Releases**: Artefakte signiert, SHA256SUMS publiziert, Endpoint verifiziert vor Anwendung.
- **No plaintext secrets in repo / installer artifacts** (siehe AGENTS-Policy).
- **Audit fuer 100% mutierender Endpoints**.

## Threat-Modell (Kurz)

| Aktor | Ziel | Beispiel-Vektor |
|---|---|---|
| Externer Angreifer | Zugriff auf Streaming-Session | Pairing-Token-Leak, ungesicherte WebSocket |
| Tenant-Insider | Zugriff auf andere Tenant-Daten | Tenant-Scope-Bypass im API |
| Operator-Insider | Datenexfiltration | Clipboard, USB-Mass-Storage, Recordings |
| Endpoint-Diebstahl | Boot in fremde Sessions | Disk nicht verschluesselt, Token persistiert |
| Supply Chain | Unsigniertes Update | Update-Feed manipuliert |

## Schichten-Massnahmen

### 1. API-Gateway

- mTLS fuer Inter-Host-Calls.
- Rate-Limit + Lockout pro IP/User.
- CSRF-Schutz fuer Web-Sessions.
- Anti-Replay fuer Pairing-Tokens (one-shot, kurzlebig, audience-bound).

### 2. Identity

- Passwort-Policy konfigurierbar (Mindestlaenge, Charset, Rotation).
- WebAuthn/Passkeys als 2FA.
- Session-Cookies: `Secure; HttpOnly; SameSite=Lax; Path=/; Max-Age=*`.
- Refresh-Token rotation + Endpoint-Fingerprint-Bindung.

### 3. RBAC

- Tenant-Scope ist Pflicht-Filter in jedem read- und write-Endpoint.
- Permission-Tags zentral; kein Endpoint ohne Permission-Check.
- Default-Deny in Policy-Engine.

### 4. Stream Security

- Watermarks (User-bound) optional pro Pool.
- Session-Recording mit Verschluesselung (client-side AGE/Restic).
- Clipboard- und USB-Policy whitelist-basiert.
- Audit-Event pro Session-Start, -Pair, -End, -Recording.

### 5. Storage

- Verschluesselung at rest fuer Pools, die das hergeben (LUKS, ZFS native, Ceph encryption).
- Backup-Verschluesselung client-side, Schluessel in Tenant-KMS.

### 6. Network

- Default-Deny im Tenant-VNet.
- Distributed Firewall pro VM.
- Stream-Public-Ports nur ueber expliziten Reconciler / WireGuard-Tunnel.

### 7. Endpoint

- Disk-Encryption-Default.
- Cluster-signierter Endpoint-Cert.
- Lokale User ohne Root, kein offener SSH per Default.
- Boot-A/B mit Signaturpruefung.

### 8. Updates

- Release-Artefakte signiert (z.B. minisign / sigstore).
- Endpoint und Host pruefen Signatur vor Apply.
- Public Update Feed liefert Signaturen + SHA256SUMS.

### 9. Logging / Audit

- Audit-Log normalisiert (siehe [06-iam-multitenancy.md](06-iam-multitenancy.md)).
- PII-Schwaerzungs-Filter konfigurierbar (z.B. nur `user.id`, kein `user.email`).
- Audit-Sinks: file (rotated), syslog, S3, webhook.
- Tamper-evident Mode (append-only + per-Tag-Hash-Chain).

### 10. Dependency Management

- pinning per `requirements.txt` / `package.json` mit reproduzierbarem Build.
- regelmaessige `pip-audit`/`npm audit` in CI.
- third-party-Tarballs (Apollo, Moonlight) mit SHA-256-Pin und Signaturverifikation im Build-Skript.

## Compliance-Roadmap

- **SOC2 Typ II**: Audit-Trail + Access Reviews + Change Management.
- **ISO 27001**: dokumentierte Policies, Asset Inventory, Incident Response.
- **DSGVO**: Tenant-Data-Export + Loeschpfad pro User, Data-Locality-Policy pro Tenant.

Dokumentenpflicht in 7.0:

- `docs/security/threat-model.md`
- `docs/security/access-control.md`
- `docs/security/incident-response.md`
- `docs/refactor/11-security-findings.md` bleibt Backlog/Findings-Log.

## Verbote

- Klartext-Secrets in versionierten Dateien (siehe AGENTS).
- Auto-trust-on-first-use ohne Audit-Eintrag.
- "TODO security" ohne Eintrag in `docs/refactor/11-security-findings.md`.
