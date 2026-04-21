# 14 — Plattform-API und Erweiterbarkeit

Stand: 2026-04-20

## Ziele

- Jede Web-Console-Aktion ist auch per stabiler API moeglich.
- Infrastructure-as-Code als Erstklasse-Workflow (Terraform).
- Externe Systeme koennen Events konsumieren (Webhooks).
- Plattform ist erweiterbar, ohne den Kern zu forken (Provider-Plug-ins).

## API-Versionierung

- `/api/v1/...` bleibt fuer 7.0 stabil (keine Breaking Changes innerhalb Major-7).
- `/api/v2/...` fuer neue Cluster-/Pool-/Tenant-Konzepte.
- OpenAPI 3.1-Spec generiert aus dem Service-Layer (`beagle-host/services/`).
- Spec wird als Artefakt im Release-Build mitgeliefert (`dist/openapi/beagle-api-v2.yaml`).

## Auth

- `Authorization: Bearer <token>` mit:
  - Session-Token (kurzlebig, aus Login),
  - API-Token (lang lebend, scoped, revokable),
  - mTLS-Client-Cert (Inter-Host).

## Resource-Modell (Auswahl)

```
GET    /api/v2/clusters/me
GET    /api/v2/nodes
POST   /api/v2/nodes/{id}:drain

GET    /api/v2/tenants
POST   /api/v2/tenants
GET    /api/v2/tenants/{id}/quota

GET    /api/v2/templates
POST   /api/v2/templates
POST   /api/v2/templates/{id}:publish

GET    /api/v2/pools
POST   /api/v2/pools
PATCH  /api/v2/pools/{id}
POST   /api/v2/pools/{id}:scale
POST   /api/v2/pools/{id}:recycle

GET    /api/v2/vms
POST   /api/v2/vms
POST   /api/v2/vms/{id}:start|stop|reboot|migrate|snapshot|clone
GET    /api/v2/vms/{id}/console
GET    /api/v2/vms/{id}/stream/pair

GET    /api/v2/sessions
POST   /api/v2/sessions/{id}:terminate
GET    /api/v2/sessions/{id}/recording

GET    /api/v2/users
POST   /api/v2/users
POST   /api/v2/users/{id}:disable

GET    /api/v2/storage-classes
POST   /api/v2/storage-classes

GET    /api/v2/network-zones
POST   /api/v2/network-zones

GET    /api/v2/backup-jobs
POST   /api/v2/backup-jobs
POST   /api/v2/backup-jobs/{id}:run

GET    /api/v2/audit
```

## Webhooks

- Event-Typen: `vm.created`, `vm.power_changed`, `pool.scaled`, `session.started`, `session.ended`, `backup.completed`, `node.health_changed`, `audit.event` (filterbar).
- Signiert per HMAC-SHA256 + Replay-Schutz (timestamp + nonce).
- Retries mit exponential backoff.
- Konfiguration pro Tenant.

## Terraform-Provider

Resource-Typen (geplant):

- `beagle_template`
- `beagle_pool`
- `beagle_vm`
- `beagle_user`
- `beagle_group`
- `beagle_entitlement`
- `beagle_storage_class`
- `beagle_network_zone`
- `beagle_firewall_profile`
- `beagle_backup_job`
- `beagle_replication_profile`

Repo-Lage: `terraform-provider-beagle/` Top-Level (eigener Go-Build, eigener Release-Pfad).

## CLI

- `beaglectl` als Single-Binary CLI.
- Befehle spiegeln API-Surface.
- Beispiele:
  - `beaglectl cluster init`
  - `beaglectl cluster join --token ...`
  - `beaglectl pool create --tenant acme --template tmpl-... --size 5`
  - `beaglectl vm migrate 142 --to node-2`
  - `beaglectl backup run bj-engineering-nightly`

## Provider-Plug-ins

- Plug-in-Vertrag in `core/provider/`: erfuellt `HostProvider`, `StorageProvider`, `NetworkProvider`, `IdentityProvider`-Interfaces.
- Plug-in-Loading ueber `entry_points`/Pythonsmodule, kein dynamic-eval.
- Beagle-Provider und Proxmox-Provider sind Referenz-Implementierungen.

## Backwards Compatibility

- v1 bleibt fuer alle bestehenden UI-/Endpoint-Pfade.
- v2 ist additiv, keine v1-Datenfelder werden umgemodelt.
- Web Console liest beides waehrend Welle 7.x; ab 8.0 Konsolidierung auf v2.

## Akzeptanzkriterien Welle 7.4.0

- OpenAPI v2 stabil und in Release-Artefakt enthalten.
- Terraform-Provider mit `beagle_pool`, `beagle_vm`, `beagle_user` benutzbar (CRUD round-trip).
- Webhook-Receiver-Demo in `examples/webhooks/`.
- `beaglectl` deckt alle Welle-1-Operationen + Cluster + Pool + Backup ab.
