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
- `scripts/lib/beagle_provider.py` wurde fuer provider-uebergreifende Timeout-Parameter gehaertet; damit funktionieren dieselben Script-Calls sowohl mit `beagle` als auch `proxmox` Provider-Semantik robuster.
- Sichtbarer Gap dokumentiert: Der `beagle` Provider liefert fuer `guest_exec`/`guest_exec_status` aktuell Skeleton-Responses. Dadurch kann `installer-prep` Sunshine-Readiness nicht verlaesslich aus dem Zielsystem lesen (false negatives trotz aktivem Service).
- Kurzfristiger Workaround im Run: VM103-Streamziel auf hostseitig erreichbare Adresse gebracht und Sunshine lokal gestartet; struktureller Fix bleibt die Erweiterung des `beagle` Provider-Contracts/Implementationspfads fuer echte Guest-Exec/State-Reads.

## Update (2026-04-16) - Beagle Provider Libvirt Install-Flow
- Beagle-Provider hat jetzt einen realen libvirt-backed VM-Provisioningpfad (Domain XML + virsh define/start/stop/reboot).
- Neue provider-spezifische Kopplung ist explizit in `beagle-host/providers/beagle_host_provider.py` gekapselt (`virsh`, Domain-XML, qemu:commandline).
- Install-Asset-Erzeugung bleibt provider-neutral orchestriert im Service-Layer, nutzt aber lokales ISO-Storage als gemeinsamen Vertragspfad (`beagle-host/services/ubuntu_beagle_provisioning.py`).
- Keine neue direkte Proxmox-Kopplung hinzugefuegt; die Aenderungen betreffen ausschließlich den Beagle-Provider.
- Bekannter Provider-Gap bleibt: Guest-Install-Readiness/Completion fuer den Beagle-Provider muss weiter gehaertet und als Smoke-Test reproduzierbar gemacht werden.
- Verifikation: frischer API-Flow `POST /api/v1/provisioning/vms` erzeugt VM 106 erfolgreich mit `status=installing` und laufendem Autoinstall.

## Update (2026-04-16) - VM106 Follow-up, Runtime/Host Boundaries
- Seed-Template fuer Ubuntu-Autoinstall wurde so angepasst, dass der Flow nicht mehr hart an frueher curtin-`qemu-guest-agent`-Installation scheitert; Guest-Agent bleibt Teil des First-Boot-Provisionings.
- Host-Service-Installer deployt jetzt auch `beagle-host/templates/ubuntu-beagle/*`, damit Runtime und Repo-Template-Stand konsistent bleiben.
- Public-Stream-Host wird im Host-Setup auf eine routbare IPv4 gehoben; damit bleibt Stream-Metadaten-Synthese provider-neutral nutzbar, waehrend provider-spezifische Umsetzung (Port-Forwarding) im Beagle-Provider bleibt.
- Control-Plane-Unit wurde fuer den Beagle/libvirt-Pfad mit expliziten Write-Scopes (`/var/lib/libvirt/images`, `/var/lib/libvirt/qemu`) aktualisiert; keine neue Proxmox-Kopplung.
- VM-Route-Parsing (`GET /api/v1/vms/<vmid>`) ist im provider-neutralen HTTP-Surface korrigiert; dies betrifft API-Vertragsebene, nicht Provider-Implementierungen.
- Aktueller Rest-Gap: Endgueltige VM106 Sunshine-Readiness und Thinclient-E2E sind durch einen separaten Host-Management-Ausfall (SSH/HTTPS refused) temporär blockiert.

## Update (2026-04-17) - USB Installer Credential Hardening
- Hostseitige VM-Installer-Skriptgenerierung wurde gehaertet, damit Moonlight-Presets Sunshine Auto-Pair Credentials konsistent mitfuehren.
- Die Aenderung liegt vollstaendig im provider-neutralen Service-Layer (`beagle-host/services/installer_script.py`) und fuehrt keine neue direkte Proxmox-Kopplung ein.
- Metadaten-/Secret-Aufloesung bleibt hinter bestehenden Service-Contracts; Provider-Implementierungen wurden nicht erweitert oder direkt referenziert.

## Update (2026-04-17) - Local E2E Reinstall Follow-up
- Neue Repro-Fixes liegen in Host-/Installer-Skripten (`scripts/install-beagle-host-services.sh`, `scripts/install-beagle-host.sh`, `scripts/install-beagle-proxy.sh`) und betreffen Infrastruktur-Readiness, nicht Provider-API-Vertraege.
- Keine neue direkte Proxmox-Kopplung eingefuehrt; die Aenderungen sind provider-agnostisch fuer den Beagle-Host-Bootstrap und verbessern den Standalone-Pfad.
- Relevanter Provider-Gap bleibt sichtbar: Nach finalisiertem Provisioning (`completed/complete`) zeigt VM101 weiterhin Laufzeit-/Read-Drift (`/vms` running vs hostseitig zeitweise `virsh` shut off) und nicht erreichbare Stream-Ports.
- Persistierter installer-prep Fehler fuer VM101 lautet `Unable to determine guest IPv4 address for VM 101`; damit blockiert die provider-gestuetzte Sunshine-Readiness-Orchestrierung weiterhin vor der eigentlichen Install/Health-Pruefung.
- Naechster Contract-Fokus: Beagle-Provider-gestuetzte Install-Completion/Readiness-Signale so stabilisieren, dass Thinclient-Autoconnect nur bei konsistent `completed + stream-ready` freigegeben wird.
