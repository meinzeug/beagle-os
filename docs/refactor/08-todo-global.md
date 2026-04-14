# Beagle OS Refactor - Global TODO

Stand: 2026-04-14

## P0 - Security Backbone
- [~] Auth data model und persistence layer (Bootstrap-User + Session + User/Role-CRUD vorhanden, Group-Modell offen)
- [~] Session service mit rotation/revocation (login/refresh/logout + idle/absolute timeout + revoke-user-sessions vorhanden, rotation policy offen)
- [x] RBAC middleware und permission registry (Enforcement aktiv, Mapping im authz-Service)
- [~] Audit log schema + write path (append-only audit events aktiv, query/export offen)
- [~] Website login und session handling (username/password Login + first-install onboarding integriert, IAM-Panel fuer User/Role CRUD + revoke-sessions aktiv, Automation-Token-UI-Aufraeumen offen)
- [ ] Website trusted API origin allowlist als deploybare Konfiguration absichern und E2E validieren
- [ ] URL-hash token import policy (`allowHashToken`) fuer Bootstrap-Flows dokumentieren und standardmaessig deaktiviert halten
- [ ] Absolute API target policy (`allowAbsoluteApiTargets`) dokumentieren und default-off E2E absichern
- [ ] Legacy-Header-Opt-In (`sendLegacyApiTokenHeader`) auf echte Migrationsfaelle begrenzen
- [ ] Security-Review: Credential-Reveal-Flows (in-memory secretVault) auf DOM-Leaks und lifecycle cleanup pruefen
- [x] Installer Security: Default SSH password auth policy finalisiert/dokumentiert (`BEAGLE_SERVER_SSH_PASSWORD_AUTH=no`, Override nur bewusst)
- [ ] Installer Security: expose-port policy als automatisierten Test absichern (22/443/8443 + optional 8006)
- [ ] Proxy Security: Auth/API rate limits unter Last testen und false positives vermeiden

## P0 - IAM Surface
- [~] Web-UI IAM Workspace (Users/Roles/Sessions) umgesetzt, Gruppenmodell und feinere Permission-UX offen
- [ ] IAM rollenbasierte E2E Tests (admin/ops/viewer) fuer alle UI-Aktionen

## P1 - Streaming-First VM Plattform
- [ ] VM <-> endpoint binding model vereinheitlichen
- [ ] stream readiness state machine
- [ ] unified action/task orchestration
- [ ] streaming incident and recovery flows

## P1 - Native Virtualization Runtime
- [~] beagle provider contract finalisieren (beagle-default im Host-Installpfad aktiv, Capability-Ausbau offen)
- [~] Web-UI Virtualization Surface erweitert (Node-Filter + VM Inspector fuer config/interfaces umgesetzt, E2E-Haertung offen)
- [ ] beagle compute service baseline
- [ ] beagle storage service baseline
- [ ] beagle network service baseline
- [ ] HA scheduler baseline

## P1 - Installer & Host Modes
- [~] standalone/with-proxmox Installpfade ueber gemeinsamen Host-Bootstrap (Mode-Umschaltung aktiv, manuelle Build-/Runtime-Smokes gruen, Testmatrix offen)
- [x] Live-Mode Standard-Web-UI-Credentials gesetzt und in MOTD sichtbar (`admin` / `test123`)
- [x] Installer-Flow mapped Linux-Install-User auf Web-UI-Bootstrap-Credentials
- [x] Frische Server-Installer-ISO gebaut, in libvirt-Imagepfad repliziert und an `beagleserver` reattached (Boot pruefbar)
- [x] CSP fuer Live- und Installer-Web-UI auf Worker-Kompatibilitaet gehaertet (`worker-src 'self' blob:`) und `frame-ancestors` aus Meta-CSP entfernt
- [x] Onboarding-Gating fuer vorhandenen Bootstrap-User behoben (kein Login-Deadlock bei `user_count=1`)
- [x] Web-UI 401-Loop-Fix: bei 401/403 Session-Lock statt weiterem Polling mit ungueltigem Token
- [x] CSP-Style-Fix: Usage-Balken ohne Inline-Styles (progress-basiertes Rendering)
- [x] Web-UI Session-Hardening erweitert (Refresh-Token-Store, Auto-Refresh auf 401/403, Logout-Revoke-Flow)
- [x] Web-UI UX/A11y verfeinert (Panel-Persistenz, remembered username, `/` Suche-Fokus, Live-Regionen fuer Status/Alerts)
- [x] Web-UI Request/Rendering-Hardening erweitert (Timeout-Wrapper, Dashboard-Load-Dedupe, eindeutige Virtualization-Section-IDs)
- [ ] Credential-E2E-Smoke fuer Live-Mode und Installer-Erstboot dokumentiert/automatisiert
- [ ] automatisierte Smoke-Tests fuer beide Modi (Install, Boot, API/UI-Portprofil)

## P2 - Enterprise Operations
- [ ] backup jobs + retention policies
- [ ] restore/live-restore UX
- [ ] certificate lifecycle management
- [ ] upgrade orchestration and rollback markers
- [ ] external metrics and alert hooks

## P2 - Quality and Testing
- [ ] API contract tests je domain
- [ ] role-matrix integration tests
- [~] smoke e2e for critical flows (live-smoke script fuer server-installer vorhanden, CI-Integration offen)
- [ ] WebUI mutation single-flight audit (alle mutierenden Actions gegen Doppel-Submit abgesichert)
- [ ] WebUI input-validation matrix testen (username/role/policy/password Grenzen und Fehlermeldungen)
- [ ] chaos/failure tests for HA and streaming
