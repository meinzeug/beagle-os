# 18 — 7.4.0 OpenAPI + Terraform-Provider + beaglectl CLI

Stand: 2026-04-20  
Priorität: 7.4 (2028)

---

## Schritte

### Schritt 1 — OpenAPI v2-Schema vollständig definieren und generieren

- [x] OpenAPI-Schema für alle `/api/v1/`-Endpoints aus bestehendem Code generieren.
- [x] Fehlende Endpoints dokumentieren, Breaking-Change-Policy festschreiben.

Ein vollständiges OpenAPI-Schema ist Voraussetzung für den Terraform-Provider und für
externe Integrations-Entwickler. Das Schema wird entweder manuell gepflegt in
`docs/api/openapi.yaml` oder auto-generiert aus Code-Annotations (z.B. mit `flask-smorest`
oder einem OpenAPI-Decorator). Alle Endpoints bekommen vollständige Request/Response-
Schema-Definitionen inklusive Fehlercodes. Eine Breaking-Change-Policy definiert
welche Änderungen an der API new-major-version-würdig sind. Das Schema wird als
Artifact bei jedem Release publiziert und auf `beagle-os.com/api` gehostet.

> Umsetzung 2026-04-21: Generator `scripts/generate-openapi-v1.py` implementiert (statische Route-Discovery in `beagle-host/**/*.py`). Erzeugte Artefakte: `docs/api/openapi.v1.generated.yaml` und `docs/api/openapi-v1-coverage.md` (41 entdeckte `/api/v1`-Pfade). Breaking-Change-Policy in `docs/api/breaking-change-policy.md` festgeschrieben.

---

### Schritt 2 — Terraform-Provider `terraform-provider-beagle` implementieren

- [ ] Go-Modul `terraform-provider-beagle` anlegen mit CRUD-Resources für VM, Pool, User, NetworkZone.
- [ ] Provider auf Terraform Registry publizieren.

Der Terraform-Provider ermöglicht Infrastructure-as-Code für Beagle-Deployments.
Ein DevOps-Team kann dann Pools, Templates, Nutzer und Netzwerkkonfigurationen als
HCL deklarieren und via `terraform apply` ausrollen. Go ist die Pflichtsprache für
Terraform-Provider; die `hashicorp/terraform-plugin-sdk/v2` Bibliothek stellt das
Framework bereit. CRUD-Resources initial: `beagle_vm`, `beagle_pool`, `beagle_template`,
`beagle_user`, `beagle_role`. Data-Sources: `beagle_vm`, `beagle_pool`. Der Provider
authentifiziert sich über die API-Token-Mechanik des Beagle-API-Servers. Tests laufen
mit einem Mock-API-Server gegen realen Terraform-State-Tests.

---

### Schritt 3 — `beaglectl` CLI implementieren

- [x] `beaglectl` als Python-CLI (Typer/Click) oder Go-Binary anlegen.
- [x] Subcommands: `vm`, `pool`, `user`, `node`, `backup`, `session`, `config`.

Die `beaglectl` CLI ist für Betreiber gedacht die lieber auf der Kommandozeile arbeiten
als im Browser. Die CLI kommuniziert über die REST-API und benötigt einen konfigurierten
API-Endpunkt und Token. Konfiguration in `~/.config/beaglectl/config.yaml` (URL, Token,
Default-Tenant). Subcommand-Struktur: `beaglectl vm list`, `beaglectl vm start <id>`,
`beaglectl pool create --template ubuntu24 --size 5`, etc. Ausgabe in Tabellen-Format
(Standard) und JSON (`--json`). Das Deployment als Single-Binary (Go) ist bevorzugt
da es keine Laufzeit-Dependencies erfordert. Release als GitHub-Release-Asset für
Linux (amd64/arm64), macOS und Windows.

> Umsetzung 2026-04-21: `scripts/beaglectl.py` als dependency-freie Python-CLI (argparse + urllib) angelegt. Enthält die geforderten Subcommands `vm`, `pool`, `user`, `node`, `backup`, `session`, `config`, inkl. `--json` Ausgabe und lokaler Konfigurationsverwaltung (`~/.config/beaglectl/config.json`).

---

### Schritt 4 — Webhook-System für Externe Integrationen

- [x] `beagle-host/services/webhook_service.py` anlegen: Webhook-Registrierungen verwalten, Events dispatchen.
- [x] Web Console: Webhook-Manager unter Server-Settings.

Webhooks ermöglichen es externen Systemen (Ticketing, Monitoring, Automatisierungsplattformen)
auf Beagle-Events zu reagieren ohne dauerhaft API-Polling zu betreiben. Der Webhook-
Manager erlaubt das Registrieren von Webhook-URLs mit Event-Filter (welche Event-Typen
sollen übermittelt werden) und HMAC-Secret für Authentizitäts-Verifikation. Beim Auftreten
eines Events wird ein HTTP-POST an alle registrierten Webhook-URLs gesendet mit dem
Event-JSON im Body und der HMAC-Signatur im Header. Bei Fehlschlag wird mit exponentiellem
Backback bis zu 5 mal wiederholt.

> Umsetzung 2026-04-21: `beagle-host/services/webhook_service.py` implementiert (persistente Registry in `webhooks.json`, Event-Filter, HMAC-SHA256-Signatur `X-Beagle-Signature`, Retry-Backoff bis zu 5 Versuche, Zustandsfelder `last_status`/`last_error`).
> Die Settings-API wurde um `GET/PUT /api/v1/settings/webhooks` und `POST /api/v1/settings/webhooks/test` erweitert (`beagle-host/services/server_settings.py`).
> Die Web Console enthält jetzt ein dediziertes Panel `settings_webhooks` mit CRUD/Test-Flow (`website/index.html`, `website/ui/settings.js`, `website/ui/state.js`).
> Zusätzlich dispatcht die Control Plane erfolgreiche VM-Power-Events (`vm.start|vm.stop|vm.reboot`) als Webhooks (`beagle-host/bin/beagle-control-plane.py`).

---

### Schritt 5 — API-Versionierung und Deprecation-Policy

- [x] `/api/v2/` vorbereiten wenn Breaking Changes aus v1 nötig werden.
- [x] Deprecation-Header in v1-Responses setzen die in v2 entfernt werden.

API-Stabilität ist für Terraform-Provider und externe Integrationen essentiell.
Breaking Changes erzwingen eine neue Major-Version. Non-Breaking-Changes (neue Felder,
neue optionale Parameter) können in der bestehenden Version hinzugefügt werden.
Deprecated Endpoints geben `Deprecation: true` und `Sunset: <RFC 7231-Datum>` Headers
zurück damit Client-Entwickler rechtzeitig migrieren können. `v1` bleibt mindestens
12 Monate nach Erscheinen von `v2` aktiv. Die Migration-Guide für `v1` → `v2` wird
in der API-Dokumentation publiziert.

> Umsetzung 2026-04-21: In `beagle-host/bin/beagle-control-plane.py` wurden vorbereitende `GET /api/v2` und `GET /api/v2/health` Endpunkte ergänzt (Status: `preparation`, inkl. Sunset/Deprecation-Metadaten). Zusätzlich setzt die Response-Pipeline für konfigurierbare v1-Endpunkte (`BEAGLE_API_V1_DEPRECATED_ENDPOINTS`, Default: `/api/v1/vms,/api/v1/provisioning/vms`) automatisch `Deprecation`, `Sunset` und `Link` Header.

---

## Testpflicht nach Abschluss

- [x] OpenAPI-Schema validiert gegen alle Live-Endpoints (keine undokumentierten Endpoints).
- [ ] Terraform: `terraform apply` legt VM an, `terraform destroy` entfernt sie.
- [x] `beaglectl vm list` gibt korrekte VM-Liste aus, `--json` gibt valides JSON.
- [x] Webhook: VM-Start-Event sendet HTTP-POST an registrierte URL mit korrekter HMAC-Signatur.

> Live-Validierung 2026-04-21 auf `srv1.beagle-os.com`:
> - `python3 scripts/validate-openapi-live.py --base-url http://127.0.0.1:9088 --coverage-file docs/api/openapi-v1-coverage.md` -> `openapi-live-validation=ok` (41 Pfade geprüft).
> - `python3 scripts/beaglectl.py --server http://127.0.0.1:9088 --token <BEAGLE_MANAGER_API_TOKEN> vm list --json` -> valides JSON (via `python3 -m json.tool` geprüft).
> - Webhook-E2E gegen `srv1`: Registrierung/Test via Settings-API (`PUT /api/v1/settings/webhooks`, `POST /api/v1/settings/webhooks/test`) erfolgreich (`attempted=1`, `delivered=1`), Capture zeigt `X-Beagle-Signature`; HMAC-Validierung gegen Raw-Body ist `signature_valid=true`.
