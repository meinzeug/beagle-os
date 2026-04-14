# Beagle OS Refactor - Provider Abstraction

Stand: 2026-04-13

## Leitlinie
Provider-Abstraktion bleibt Pflicht, aber das Ziel ist jetzt klar: Beagle-native Runtime als Default Provider.

## Architekturregel
- Domain Services duerfen keine provider-spezifischen APIs direkt aufrufen.
- Alle Infrastrukturzugriffe laufen ueber Contracts in core/.
- Konkrete Implementierungen leben nur in providers/<name>/.

## Vertragsbereiche
- Compute contract: vm lifecycle, config mutate, migration hooks, snapshots
- Storage contract: pool inventory, volume lifecycle, policy capabilities
- Network contract: bridge/vlan/overlay primitives, attach/detach, policies
- Host ops contract: node inventory, maintenance transitions, health probes

## Capability-Modell
Jeder Provider liefert eine capability map, z. B.:
- supports_live_migration
- supports_snapshot_memory
- supports_streaming_attach
- supports_overlay_network
- supports_ha_fencing

Domain-Services entscheiden anhand der capability map, welche Flows freigegeben sind.

## Zielzustand
- beagle provider ist vollstaendig fuer standalone mode.
- Externe Provider sind optionale Adapter.
- Keine Kernfunktion ist von einem externen Provider abhaengig.

## Migrationsregel
- Jede neue Funktion zuerst gegen Contract + beagle provider bauen.
- Externer Provider Support danach als optionales Backlog.

## Aktueller Stand (2026-04-13)
- Provider-Normalisierung im Host-Provider-Registry-Fallback ist auf `beagle` umgestellt (kein impliziter Proxmox-Default mehr).
- Host-Installskripte verwenden jetzt Beagle als Default-Provider und leiten ohne Override den Provider aus dem Install-Mode ab (`with-proxmox` => `proxmox`, sonst `beagle`).
- Server-Installer-Hardening oeffnet Port 8006 nur noch im Proxmox-Zweig; Standalone bleibt ohne Proxmox-UI-Port.
- RBAC-Enforcement fuer mutierende API-Routen liegt im provider-neutralen Control-Plane-Handler.
- Audit-Events fuer Auth- und Mutationsentscheidungen liegen ebenfalls im provider-neutralen Layer.
- Permission-Mapping ist in ein dediziertes provider-neutrales Modul (beagle-host/services/authz_policy.py) ausgelagert.
- User-/Role-CRUD-Endpunkte wurden im provider-neutralen Auth-Layer eingefuehrt, ohne neue Provider-Kopplung.
- Session-Hardening (idle/absolute timeout) und user-spezifische Session-Revocation liegen im provider-neutralen Auth-Service.
- First-Install-Onboarding-Status und Completion-Endpunkte liegen im provider-neutralen Auth-Layer und fuehren keine Provider-Kopplung ein.
- Frischer Server-Installer-Build (2026-04-13) ist erfolgreich erzeugt; manueller Runtime-Smoketest (VM running + API/UI HTTPS) ist gruen.
- Es wurden in diesem Slice keine neuen provider-spezifischen Kopplungen eingefuehrt.
