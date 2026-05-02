# Beagle OS Refactor - Umsetzungfahrplan

> Kanonische Gesamtübersicht: [`docs/MASTER-PLAN.md`](../MASTER-PLAN.md). Welle 1–2 sind weitgehend abgeschlossen; aktuelle Hauptarbeitslinie ist GoEnterprise 8.x (siehe Master-Plan Abschnitt 5).

Stand: 2026-04-13

## Strategisches Ziel
In 4 inkrementellen Wellen Beagle OS zu einer beagle-native Plattform ausbauen, die funktional auf Enterprise-Niveau liegt und Thinclient-Streaming pro VM nativ integriert.

## Welle 1 - Identity, Session, RBAC Backbone (2-4 Wochen)

### Deliverables
- username/password Login API
- Session endpoints (login, refresh, logout, me)
- Role/permission model v1
- RBAC middleware fuer alle mutierenden Endpunkte
- Web UI Login-Flow statt Token-Modal

### Nutzung vorhandener Komponenten
- beagle-host/bin/beagle-control-plane.py als Einstiegspunkt
- neue services in beagle-host/services fuer auth/session/rbac
- website/app.js und website/index.html fuer neuen auth flow

### Erfolgskriterien
- kein produktiver UI-Workflow mehr nur mit API-Token
- alle Write-Endpoints mit serverseitigem permission check

## Welle 2 - Streaming-First VM Domain (3-5 Wochen)

### Deliverables
- Vereinheitlichte VM lifecycle + stream lifecycle orchestration
- VM-zu-Endpoint-Zuordnung als first-class object
- stream readiness state machine (prepare, ready, degraded, blocked)
- actions queue harmonisiert fuer power/update/stream tasks

### Nutzung vorhandener Komponenten
- vm_state, vm_profile, vm_secret_bootstrap, installer_prep, beagle_stream_server_integration
- thin-client-assistant runtime und installer assets

### Erfolgskriterien
- pro VM sichtbarer Streaming-Lifecycle in UI und API
- einheitliche Fehlercodes fuer streamingkritische Schritte

## Welle 3 - Beagle-native Virtualization Core (6-10 Wochen)

### Deliverables
- beagle provider contract v1 final
- beagle-native compute/storage/network service skeleton produktiv
- HA scheduling baseline
- snapshot/clone/template baseline im beagle provider

### Nutzung vorhandener Komponenten
- core/provider, core/virtualization, providers/beagle
- host/provider registry fuer beagle as default

### Erfolgskriterien
- Kernworkflows laufen in standalone mode
- externe Provider nur optional

## Welle 4 - Operations Parity und Hardening (4-8 Wochen)

### Deliverables
- backup/restore jobs und retention
- audit/event/task center in UI
- certificate and upgrade operations
- metrics/export and alert hooks
- security hardening (secret storage, rotation, policy tests)

### Erfolgskriterien
- enterprisefaehiger Betriebsmodus inkl. Rollen, Audit, Recovery
- release-ready Architektur fuer breiteren Rollout

## Querschnittsregeln
- keine Big-Bang Umbauten
- jedes Inkrement build- und runtime-stabil
- migrationsfaehige APIs (versioned)
- feature flags fuer risikoarme Aktivierung
