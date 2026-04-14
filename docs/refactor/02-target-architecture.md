# Beagle OS Refactor - Target Architecture

Stand: 2026-04-13

## Architekturprinzipien
- Beagle-native zuerst: alle Kernfaehigkeiten muessen ohne Fremd-Provider laufen.
- Contracts vor Implementierung: Domain-Vertrag zuerst, Runtime danach.
- Security-by-default: AuthN, AuthZ, Audit und Secret-Handling als Querschnitt.
- Streaming ist keine Erweiterung, sondern Teil des VM-Lifecycle.

## Zielschichten

### 1. Experience Layer
- Beagle Web Console (website/)
- Rolle-basierte Navigation und Aktionen
- Task Center, Events, Audit und Incident-Sicht

### 2. Identity & Access Layer
- Local identity store (users, password hashes, groups)
- Session service (access/refresh, idle/absolute timeout)
- Role/Permission registry
- Policy engine (scope: global/node/pool/vm/tenant)

### 3. Control Plane Domain Layer (beagle-host/services)
- Compute service
- Streaming orchestration service
- Provisioning service
- Storage inventory and policy service
- Network inventory and policy service
- HA/scheduler service
- Backup/restore service
- Task/event/audit service

### 4. Platform Contracts (core/)
- virtualization contracts
- provider contracts
- platform runtime contracts
- authz contract
- task/event contract

### 5. Runtime & Providers (providers/)
- beagle-native provider als Primarprovider
- optionale externe Provider als Adapter

## Referenzfaehigkeiten (Tier-1)
- Compute: create/update/start/stop/reboot/template/clone/snapshot/migrate
- Streaming: stream endpoint provisioning, readiness checks, credential rotation, remote access tickets
- IAM: user/group/role CRUD, path/object permissions, API tokens for automation
- Storage: pools, classes, quotas, snapshot policies, replication policies
- Network: bridges, VLANs, overlays, isolation, firewall policies
- HA: failure detection, fencing strategy, placement rules, maintenance mode
- Backup/DR: schedules, retention, restore, live-restore, consistency hooks
- Ops: upgrades, certs, telemetry, external metrics, audit exports

## Betriebsmodi
- standalone mode: beagle-native compute/storage/network/iam/ha stack
- external-provider mode: gleiche API/UX, anderer Provideradapter

## Qualitätsziele
- API backwards-compatible per versioned contract
- every mutation endpoint has permission gate + audit entry
- deterministic task IDs and event streams across all domains
