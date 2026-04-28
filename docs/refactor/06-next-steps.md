# Next Steps

## Stand (2026-04-28, GoEnterprise Plan 04 testpflicht completed)

**Zuletzt erledigt**:
- Plan 04 Testpflicht ist jetzt geschlossen (14-Tage-Peak-Erkennung, 10-Minuten-Prewarm, Rebalancing >85%).
- Neue dedizierte Abnahmetests laufen lokal und auf `srv1` stabil (`20 passed` auf beiden Laeufen).

**Naechste konkrete Schritte**:

1. **Plan 04 vertiefen**: Warm-Pool-Empfehlungen optional automatisch anwenden (`auto-apply`) mit klarer Safety-Grenze.
2. **Plan 09 abschliessen**: offenen externen Carbon-/Strommix-Feed als reproduzierbaren Importjob implementieren.
3. **Plan 07 testpflicht schliessen**: Fleet-Telemetrie-/Anomalie-/Maintenance-Abnahmesuite (`SMART`, Disk-Trend, Alert, Migration) aufbauen und live gegen `srv1` validieren.
4. **Plan 02 live-rest abschliessen**: verbleibende End-to-End-Checks fuer Enrollment/TPM/WireGuard-Mesh und Gruppen-Policy reproduzierbar auf echter Runtime verankern.

## Stand (2026-04-28, GoEnterprise Plan 05 testpflicht completed)

**Zuletzt erledigt**:
- Plan 05 Testpflicht ist vollstaendig geschlossen (GPU-Preismodell-Kalkulation, 5x-Alice-Tracking, Chargeback-CSV-Summierung, 85%-Budget-Alert).
- Chargeback rechnet RAM-Kosten jetzt korrekt in `total_cost` ein.
- Validierung lokal und auf `srv1` mit identischem Pytest-Scope (`37 passed` auf beiden).

**Naechste konkrete Schritte**:

1. **Plan 05 vertiefen**: Chargeback-Drilldown um explizite Session-Zeilen im CSV/JSON erweitern (nicht nur Aggregation je Department/User).
2. **Plan 04 vertiefen**: offene Automatisierung der Warm-Pool-Empfehlungen kontrolliert hinter Feature-Flag nachziehen.
3. **Plan 09 vertiefen**: externen Carbon-/Strommix-Feed als reproduzierbaren Import-Job mit Retry/Alerting hinterlegen.
4. **Plan 02 live validieren**: grafischen Sperrbildschirm weiter auf echter Thin-Client-Hardware/X11-/Wayland-Setups abnehmen.

## Stand (2026-04-28, GoEnterprise Plan 04/05/09 analytics follow-up)

**Zuletzt erledigt**:
- Chargeback zeigt jetzt Forecast Monatsende, Energiekosten gesamt und Top-10 kostenintensive VMs.
- Energiekosten sind im Cost-/Chargeback-Pfad jetzt mit eigener Regression abgesichert.
- Scheduler-Insights zeigen jetzt neben Prewarm-Kandidaten auch eine erste 7-Tage-Historie und 24h-Prognose auf Basis der Metrics-/Workload-Historie.

**Naechste konkrete Schritte**:

1. **Plan 04 vertiefen**: echte Heatmap-Visualisierung statt Tabellen-Listing und später Pool-/User-bezogene Saved-CPU-Hours differenzieren.
2. **Plan 05 vertiefen**: Department- und Pool-Drilldown bis auf Session-Ebene im Dashboard nachziehen.
3. **Plan 09 vertiefen**: Ranking effizienteste vs. energieintensivste VMs/Nodes im Energy-Panel nachziehen.
4. **Plan 09 Green-Scheduling härten**: Green-Hours explizit modellieren und die Prognose-/Placement-Entscheidung zeitfensterbasiert statt nur global gewichtet machen.
5. **Plan 02 live validieren**: Lock-Screen, Wipe und Runtime-Telemetrie weiter gegen echte Thin-Client-Hardware/X11-/Wayland-Sessions abnehmen.
6. **Plan 07 live validieren**: Fleet-Alerts und Predictive-Maintenance gegen echte Runtime-Events provozieren und Webhook-/UI-Reaktion prüfen.

## Stand (2026-04-28, GoEnterprise Plan 04/05/09 operator follow-up)

**Zuletzt erledigt**:
- Scheduler-, Cost- und Energy-Panels sind jetzt nicht mehr read-only, sondern haben echte Operator-Konfiguration im Dashboard.
- Cost- und Energy-Settings synchronisieren jetzt `electricity_price_per_kwh` kontrolliert zwischen beiden Planes.
- Scheduler-Insights zeigen jetzt Prewarm-Kandidaten und eine erste `saved_cpu_hours`-Schätzung auf Basis der vorhandenen Metrics-/Workload-Historie.

**Naechste konkrete Schritte**:

1. **Plan 04 vertiefen**: echte historische Heatmap und 24h-Prognose aus persistierten Metrics ableiten, statt aktuell nur den Cluster-Istzustand zu zeigen.
2. **Plan 05 abschliessen**: Forecast pro Abteilung und Top-10 kostenintensive VMs direkt im neuen Cost-Panel nachziehen.
3. **Plan 09 vertiefen**: Energy-Cost-Integration mit echten Session-/Chargeback-Daten nachziehen und `tests/unit/test_energy_cost_integration.py` einführen.
4. **Plan 09 Green-Scheduling härten**: Green-Hours explizit modellieren und im Scheduler nicht nur per globalem Faktor, sondern per Zeitfenster anwenden.
5. **Plan 02 live validieren**: Lock-Screen, Wipe und Runtime-Telemetrie weiter gegen echte Thin-Client-Hardware/X11-/Wayland-Sessions abnehmen.
6. **Plan 07 live validieren**: Fleet-Alerts und Predictive-Maintenance gegen echte Runtime-Events provozieren und Webhook-/UI-Reaktion prüfen.

## Stand (2026-04-28, GoEnterprise Plan 04/05/09 follow-up)

**Zuletzt erledigt**:
- Scheduler-, Chargeback- und Energy-/CSRD-Panels sind jetzt keine toten UI-Module mehr, sondern laufen über echte Control-Plane-Routen im Hauptdashboard.
- Rebalancing-Empfehlungen lassen sich jetzt aus der WebUI direkt ausführen; Kosten-CSV und CSRD-Export sind am Dashboard verdrahtet.
- Die neuen Enterprise-Surfaces sind per RBAC auf `settings:read` / `settings:write` gelegt und mit gezielten Read-Surface-/UI-Regressions abgesichert.

**Naechste konkrete Schritte**:

1. **Plan 04 weiter vertiefen**: historische Scheduler-Heatmap und echte Prewarming-/Saved-CPU-Hours-Metrik nachziehen, damit das Dashboard nicht nur den Ist-Zustand zeigt.
2. **Plan 05 vervollstaendigen**: Preismodell-Editor und Budget-Verwaltung im Settings-/Enterprise-Flow sichtbar machen, statt nur die Read-Surface zu liefern.
3. **Plan 09 vertiefen**: Energy-Admin-Konfiguration und echte Green-Scheduling-Integration mit Plan 04 schließen.
4. **Plan 02 live validieren**: Lock-Screen, Wipe und Runtime-Telemetrie weiter gegen echte Thin-Client-Hardware/X11-/Wayland-Sessions abnehmen.
5. **Plan 07 live validieren**: Fleet-Alerts und Predictive-Maintenance gegen echte Runtime-Events provozieren und Webhook-/UI-Reaktion prüfen.
6. **Plan 01 Fork-Pfad weiterziehen**: VPN-Enforcement nach dem aktuellen Broker-Pfad auch im späteren `beagle-stream-server`-Fork vorbereiten.

## Stand (2026-04-28, GoEnterprise Plan 02 follow-up)

**Zuletzt erledigt**:
- GoEnterprise Plan 02 hat jetzt die erste echte Operator-Flaeche fuer die Thin-Client-Registry:
  - Fleet-/Device-Registry-Endpunkte laufen ueber die Control Plane
  - Dashboard rendert Hardware, Online-Status, `last_seen`, Standort und Gruppe
  - Fleet-Routen sind per RBAC auf `settings:read` / `settings:write` gelegt, Lock/Wipe/Unlock sind im UI bedienbar und die Aktionen schreiben Audit-Events
  - Thin-Client-Runtime synchronisiert Heartbeat, Hardware und VPN-Zustand jetzt per endpoint-authentifiziertem `device/sync` und zieht dabei MDM-Policy + Lock/Wipe-Status zurück
  - `vpn_required` wird im aktuellen Session-Broker jetzt serverseitig gegen den persistierten WireGuard-Status des Devices erzwungen
  - `locked` blockiert den Session-Start jetzt hart; `wipe_pending` fuehrt einen reproduzierbaren Runtime-Secret-Wipe aus und meldet `confirm-wiped` zurueck
  - die Fleet-WebUI hat jetzt einen echten MDM-Policy-Editor samt Device-/Group-Assignment-Flow
  - effective-policy-preview und Bulk-Device-Policy-Zuweisung sind jetzt ebenfalls direkt im Fleet-Panel bedienbar

**Naechste konkrete Schritte**:

1. **Plan 02 Wipe live abnehmen**: den neuen Storage-/TPM-Wipe auf echter Thin-Client- oder VM-Hardware verifizieren und den Umgang mit `partial`/`failed`-Reports operationalisieren.
2. **Plan 02 Device-UX live abnehmen**: den jetzt erweiterten Sperrbildschirm und die neue Runtime-Telemetrie auf echter X11-/Wayland-Session und echter Multi-Display-Hardware pruefen.
3. **Plan 07 live abnehmen**: Fleet-Alerts gegen echte Thin-Client-Hardware oder VM-Runtime provozieren und verifizieren, dass WebUI + Webhook-Dispatch wie erwartet reagieren.
4. **Plan 02/07 Fleet-Operatorik nachziehen**: Runtime-Telemetrie um Session-/Health-/Streaming-Signale erweitern, damit Lock/WG/Display nicht die letzten sichtbaren Ist-Daten bleiben.
5. **Plan 02 Policy-Plane weiter automatisieren**: auf der neuen Drift-/Run-/Config-Surface weitere sichere Batch-Aktionen und spaetere echte Auto-Remediation-Worker aufbauen.
6. **Plan 01 Fork-Pfad weiterziehen**: den spaeteren `beagle-stream-server`-Enforcement-Pfad im Sunshine-Fork vorbereiten, obwohl der heutige Broker-Pfad bereits blockiert.

## Stand (2026-04-27, two-host follow-up)

**Zuletzt erledigt**:
- Installer-/USB-Downloadskripte schreiben jetzt nachweisbare API-Logs mit kurzlebigen write-only Tokens; `srv1`-Live-Smoke fuer VM100-Logkontext, Script-Events, Invalid-Token-401 und `/beagle-downloads/` ist gruen.
- Release-Linie wurde im Repo auf `8.0` angehoben; GitHub-Release-Erstellung ist der naechste abschliessende Schritt nach Commit/Push und finaler Validierung.
- Repo-Auto-Update-/Host-Install-Self-Heal gegen kaputte Runtime-Symlink-Loops (`/opt/beagle/beagle-host` / `beagle_host`) ist jetzt im Repo verankert.
- Plan 11 Parity bekam jetzt auch den fehlenden ISO/qcow2/raw/img-Upload-Endpunkt (`POST /api/v1/storage/pools/{pool}/upload`) inklusive Quota- und Content-Validierung.
- Plan 11 Parity bekam jetzt auch Storage-Dateiliste und Download (`GET /api/v1/storage/pools/{pool}/files` plus `?filename=...`) inklusive Virtualization-UI-Flow im Storage-Panel.
- Plan 11 Parity bekam jetzt auch direktes LDAP-Bind und lokalen TOTP-Zweitfaktor im Auth-Stack.
- Policies-Panel hat jetzt eine Subnavigation fuer die Hauptbereiche; der Ist-Zustand ist in Plan 10 dokumentiert.
- Passwort-/Username-Felder in Hidden- und Modal-Flows sind in sauberere Form-Kontexte gezogen; die Browser-Warnungen sind deutlich reduziert.
- Policies-UI wurde sichtbarer modernisiert: Hero-Band, Main/Side-Workspace, kompaktere Pool-Cards und Entitlement-Chips sind live auf `srv1`.
- Policies Plan 10 bekam einen echten Entitlement-Operator-Flow: ausgewählter Pool zeigt User-/Group-Entitlements als Chips und kann direkt per UI gepflegt werden.
- Policies Plan 10 bekam eine Template-Bibliothek als Kartenansicht: OS, Storage, Source-VM, Build-Zeit, Health sowie `verwenden`/`neu bauen`/`löschen` sind jetzt direkt im Panel bedienbar.
- Policies Plan 10 bekam jetzt auch eine bestätigte Pool-Delete-Danger-Action mit Slot-Zähler; der verbleibende Rest liegt weiter beim strukturierten Policy-Editor und der Bulk-/Scale-/Recycle-Absicherung.
- IAM Plan 13 Schritt 7 ist jetzt auch als E2E-Smoke auf `srv1` geschlossen (`PLAN13_IAM_SMOKE=PASS`).
- Audit Plan 15 Schritt 6 ist jetzt mit UI-Regressions und Live-Smoke auf `srv1` geschlossen (`AUDIT_COMPLIANCE_SMOKE=PASS`).
- GoFuture Virtualization-Panel ist im Plan-Stand jetzt sauber als erledigt markiert; Nodes, Storage, Bridges, GPU/vGPU/SR-IOV und VM-Inspector sind bereits live bedienbar.
- GoEnterprise Plan 08 weiter geschlossen: Seed-Discovery im Server-Installer ist jetzt produktiv verdrahtet (`/media/beagle-seed.yaml`, `/run/live/medium/...`, `beagle.seed_url=...`), PXE-Setup-Script + Doku + Integrations-Smoke liegen im Repo.
- PXE-Dry-Run gegen echte Installer-Artefakte auf `srv1` und `srv2` erfolgreich; beide Hosts erzeugen konsistente `dnsmasq`-/TFTP-Baeume im isolierten Temp-Root.
- Cluster-Installer-Glue geschlossen: Auto-Join-Oneshot, Install-Check-API, Cluster-Banner in der WebUI.
- Live-Drift im laufenden Zwei-Host-Cluster behoben: `srv1` und `srv2` verwenden wieder gueltige `/beagle-api`-Member-URLs und sehen sich gegenseitig als `online`.
- `srv2` hat einen erfolgreichen Post-Install-Check an `srv1` gemeldet; der Report ist auf dem Leader abrufbar und in der WebUI sichtbar.
- GoEnterprise Plan 06 Schritt 3 begonnen: endpoint-authenticated Session-Broker `GET /api/v1/session/current` und Thin-Client-Reconnect-Hook sind umgesetzt; live auf `srv1` mit echtem Endpoint-Token erfolgreich abgenommen.
- GoEnterprise Plan 06 weiter geschlossen: Timing-Test `<5s`, Geo-Routing-Backend, Handover-History-API und Slow-Handover-Alerts sind implementiert; `scripts/smoke-session-handover-flow.sh` lieferte auf `srv1 -> srv2` live `PASS` in `0.29s`.
- GoEnterprise Plan 06 abgeschlossen: die WebUI rendert die neue Session-Handover-Historie jetzt live im Policies-Panel; auf `srv1` ist der neue Operator-Block mit echten `srv1 -> srv2`-Events browserseitig verifiziert.
- GoAdvanced Plan 10 Schritt 4 geschlossen: `tests/integration/test_ha_failover.py` ergänzt; gesamter Integrationssatz liegt jetzt bei `87 passed`.

**Naechste konkrete Schritte**:

1. **Cluster-WebUI-Operations vervollstaendigen**: `docs/gofuture/00-index.md` Schritt "Cluster-Operations in der WebUI vollständig machen" bleibt als echter Zwei-Host-Operator-Block offen.
2. **Release 8.0 abschliessen**: nach finalem Testlauf committen, pushen, Tag/Release `v8.0` auf GitHub erzeugen und pruefen, dass GitHub nicht mehr `6.6.7` als neuesten Release zeigt.
3. **Installer-Restgrenze sauber schliessen**: Mehrdisk-RAID und echter PXE-Boot mit DHCP-seitiger Seed-Uebergabe bleiben als verbleibender Installer-Nachlauf offen.
4. **Plan-11-Parity-Rest auf die großen Themen begrenzen**: offen bleiben jetzt nur noch SDN/Overlay, HA-Manager und zero-downtime Live-Migration.
5. **VM-Operator-Regressionen weiter verdichten**: nachgezogene noVNC-/Delete-UI-Regressions sind jetzt im Repo; naechster sinnvolle CI-Rest waere ein echter UI-Provisioning-Smoke.
6. **Self-Heal live nochmals beweisen**: nach Push muss `srv1` den neuen `origin/main`-Stand per `beagle-repo-auto-update.service` selbst ziehen und mit `state=healthy` enden.

## Stand (2026-04-26, GoFuture Re-Open: WebUI-Operability)

**Zuletzt erledigt**:
- GoFuture-Index und Detailplaene fuer `/#panel=cluster`, `/#panel=virtualization`, `/#panel=policies`, `/#panel=iam` und `/#panel=audit` mit echten Checkbox-Backlogs erweitert.
- Abschlussregel geschaerft: Statusanzeigen reichen nicht; Operator-Flows muessen in der WebUI bedienbar, validiert, progress-faehig und getestet sein.
- Erster Cluster-Wizard-Slice umgesetzt: lokaler Join in bestehenden Cluster per WebUI/API (`POST /api/v1/cluster/join-existing`) plus Setup-Card im Cluster-Panel.
- Leader-Preflight-Slice umgesetzt: `POST /api/v1/cluster/add-server-preflight` plus WebUI-Wizard fuer DNS/API/RPC/SSH-Pruefung und Join-Token nach bestandenem Pflicht-Preflight.
- Cluster-Panel markiert den lokalen Host jetzt sichtbar als `LEADER`, `MEMBER` oder `SETUP`; Leader-only Aktionen werden nur auf dem Leader angeboten.
- Der Leader-Wizard "Weiteren Server vorbereiten" ist jetzt auf eine Laien-Eingabe reduziert: Servername und Zielserver-Setup-Code eingeben; technische Felder liegen im Expertenbereich.
- Echter Zielserver-Setup-Code fuer Auto-Join ist implementiert: Zielserver erzeugt nach Login einen kurzlebigen, gehasht gespeicherten Einmal-Code; Leader verbindet per Hostname + Code ohne offene Remote-Health-/Inventory-Abfrage.
- Cluster-Member-Leave folgt jetzt einem 2-Phasen-Flow: Leader entfernt den Member autoritativ per mTLS-RPC, danach wird lokal aufgeraeumt.
- `GET /api/v1/virtualization/overview` ist cluster-aware; `srv1` und `srv2` zeigen beide dieselbe Knotenliste statt nur den lokalen Node.
- `/#panel=virtualization` hat jetzt einen echten Node-Detail-Flow mit Backend-Endpoint `GET /api/v1/virtualization/nodes/{node}/detail`, Service-/Reachability-Status und Live-Validierung auf `srv1`/`srv2`.
- Join-Tokens haben jetzt eine echte serverseitige Ablaufpruefung.
- Auth-503-Bursts reduziert: nginx `beagle_auth` Rate-Limit angehoben und Dashboard fragt IAM-User/Roles nur noch im IAM-Panel ab.
- Artifact-Operations-Slice umgesetzt: `GET/POST /api/v1/settings/artifacts*` plus WebUI-Status/Refresh im Updates-Panel.
- Artifact-Watchdog umgesetzt: WebUI kann den Host-Watchdog aktivieren, konfigurieren und direkt anstoßen; `srv1` und `srv2` melden nach abgeschlossenem Refresh jetzt `healthy` und `public_ready=true`.
- `/#panel=settings_updates` vereinfacht: nur noch drei moderne Karten fuer APT-Systemupdates, GitHub-Repo-Updates und Artefaktbau; Direktaufruf laedt Statusdaten nach Admin-Login automatisch ohne Button-Klick.
- Lange Artifact-/ISO-Builds sind in der WebUI jetzt sichtbar: Live-Phase, Laufzeit, aktive Prozessanzahl, Fortschrittsbalken und erklaerender Hinweis werden waehrend des laufenden Builds angezeigt.
- Lokale Regression: `42 passed` fuer Auth-HTTP, Cluster-Membership, Cluster-HTTP-Surface und AuthZ; Live-Burst auf `srv1` gegen `/auth/roles`: 35x `401`, 0x `503`.

**Naechste konkrete Schritte**:

1. **Repo-Auto-Update live fertig validieren**: nach Push auf `origin/main` `repo_auto_update_enabled=true` auf `srv1` und `srv2` setzen, manuellen GitHub-Check aus der WebUI/API anstoßen und bestaetigen, dass `/opt/beagle` auf den neuen Commit aktualisiert wird.
2. **Long-Build-Status final abnehmen**: laufende Repo-Auto-Updates auf `srv1`/`srv2` bis `state=healthy` beobachten und bestaetigen, dass die neue Live-Statusanzeige bis zum Abschluss korrekt bleibt.
3. **GitHub Release-Workflow erneut gegen echten Push pruefen**: bestaetigen, dass `.github/workflows/release.yml` nach dem Parse-Fix wieder laeuft und auf Push nach `main` einen neuen Rolling-/Release-Lauf erzeugt.
4. **Plan 12 Nachlauf nur optional**: voller NVIDIA-Treiber-/Streaming-Benchmark im Gast waere noch zusaetzliche Komfortvalidierung, ist aber kein Pflichtblocker mehr.
5. **Thinclient-Hardware-Rerun auf echtem Stick**: neuen VM100-USB-Stick von `srv1` erzeugen und den bisher fehlgeschlagenen physischen `Preset Installation starten`-Pfad auf echter Hardware erneut abnehmen.
6. **Thinclient-Runtime visuell abnehmen**: lokale installierte Ziel-Disk mit grafischem Capture/Screenshot bis zur sichtbaren Moonlight-Session gegen `vm100` pruefen.
7. **Security vor Cluster-Komfort**: separate legacy HTTPS listener abschalten; Installer-/Download-Pfade auf `443` migrieren.
**Blocker/Risiken**:
- `srv2` GPU: GTX 1080 ist an `vfio-pci`, aber IOMMU-Gruppe enthaelt weitere Geraete; Passthrough bleibt ohne ACS/BIOS/Hardware-Aenderung nicht sicher freigebbar.
- Artifact-Refresh ist jetzt auf `srv1` und `srv2` gruen; offener Rest fuer Plan 06 ist jetzt das echte Zusammenspiel `GitHub-Repo-Update -> Host-Deploy -> Artifact-Watchdog`.
- `srv2` hat im aktuellen Browser-Smoke zwar keine Console-Errors mehr, nutzt aber weiterhin eine Zertifikatskette mit frueherem `ERR_CERT_AUTHORITY_INVALID`-Fund; TLS-Bereinigung bleibt separat offen.

---

## Stand (2026-05-XX, GoAdvanced Plan 07 vollständig: Async Job Queue)

**Zuletzt erledigt**:
- Plan 07 Schritt 3 komplett: `POST /api/v1/cluster/migrate` → enqueue + 202 (cluster_http_surface)
- Plan 07 Schritt 5: `Idempotency-Key`-Header in HTTP-Surfaces verdrahtet (backup + snapshot)
- Plan 07 Schritte 1–5 vollständig abgeschlossen
- Plan 10 Schritt 7 CI: `.github/workflows/e2e-nightly.yml` erstellt
- Test-Baseline: 968 passed (unit + integration), 0 Regressions

**Nächste konkrete Schritte**:

1. **Plan 07 Schritt 6** (MEDIUM): Web-UI Jobs-Panel mit SSE-Subscribe + Toast bei Job-Completion.
2. **Plan 09 CI Pipeline**: Restliche CI-Checks (lint, security) konsolidieren.
3. **Plan 08 Observability**: Structured logging + Prometheus-Metriken Endpoint.
4. **Plan 09** (HIGH, in Planung): HA-Manager — Prerequisit für Plan 10 Schritt 4 (HA-Failover-Tests).

---

## Stand (2026-04-25, update) — Terraform Provider Fix + Migration Service Wiring

**Zuletzt erledigt (dieser Session)**:
- **Terraform Provider Bugfix** (`728f70e`):
  - `client.requestWithStatus()` hinzugefügt (unterscheidet 404 von anderen Fehlern)
  - `resourceVMRead` fixt: nur Resource-ID löschen bei echtem 404, nicht auf allen Errors
  - Schema-Felder nun bevölkert mit API-Response-Werten
  - Unit-Tests: 4/4 pass (TestClientCreateReadDelete, TestClientReadNotFound, TestClientBadToken, TestApplyCreatesVMDestroyRemovesVM)
  - Validierung: `terraform apply` + `destroy` auf srv1 gegen beagle_vm.test (vmid=9901), APPLY_EXIT=0, DESTROY_EXIT=0 ✅

- **Migration Service: Cluster-Inventory-Wiring** (`fdc308d`):
  - Neuer Helper `_cluster_nodes_for_migration()` ruft `build_cluster_inventory()` auf
  - Wiring updated: `migration_service`, `ha_manager_service`, `maintenance_service`, `pool_manager_service` nutzen cluster-aware node list
  - **Folge**: Remote Hypervisoren (z.B. beagle-1) sind jetzt sichtbar als gültige Migrations-Ziele
  - Unit-Tests: 24/24 pass (migration, ha_manager, maintenance, pool_manager)
  - Deployment auf srv1/srv2 + systemctl restart beagle-control-plane → `active` ✅
  - Cluster-Inventory nach Deployment: alle 4 Knoten (beagle-0, beagle-1, srv1, srv2) online ✅

- **SSH-Keys für Cross-Node Migration**:
  - Beagle-manager SSH-Keys (ed25519) generiert auf srv1/srv2
  - Cross-authorized: srv1-key in srv2 authorized_keys, srv2-key in srv1 authorized_keys
  - Validierung: `sudo -u beagle-manager ssh root@beagle-1` → CONNECTION_OK ✅
  - `BEAGLE_CLUSTER_MIGRATION_URI_TEMPLATE=qemu+ssh://root@{target_node}/system` in `/etc/beagle/beagle-manager.env` ✅

---

### **Gefundenes QEMU+SSH Migration-Deadlock-Problem**
Virsh-basierte Live-Migration über `qemu+ssh` deadlockt bei allen Versuch-Kombinationen:
- `virsh migrate --live --copy-storage-inc`: Timeout nach 60-120s, kein Fortschritt
- `virsh migrate --live --copy-storage-all`: Gleiches Verhalten
- `virsh migrate --persistent --undefinesource`: Bringt libvirt in Deadlock (`another migration job already running`)
- `virsh domjobinfo` während Migration: Timeout (kompletter libvirt-Lock)
- Root-Ursache: Qemu+SSH Migration-Protokoll oder Libvirt-Konfiguration inkompatibel (erfordert tiefere QEMU/Libvirt-Untersuchung)

**Implikation für Beagle Migration-API**:
- API-Layer ist funktional (kann Ziel-Knoten korrekt identifizieren, SSH-Schlüssel vorhanden, qemu+ssh Connectivity OK)
- **Aber**: Virtualisierungs-Infrastruktur-Layer (virsh+qemu+ssh) ist fehlerhaft und braucht separate Untersuchung
- **Workaround für Multi-Node-Produktion**: Shared Storage (NFS/Ceph) verwenden statt Storage-Copy während Migration
- Migration-API wird korrekt arbeiten, sobald Shared Storage vorhanden oder QEMU+SSH-Protokoll repariert ist

## Zuletzt erledigt (vorherige Session, 2026-04-25)

- GoFuture Gate: alle 20 Pläne (docs/gofuture/) abgeschlossen (d588939)
- `service_registry.py` extrahiert: `beagle-control-plane.py` 4964 → 1627 LOC (e2e4c38)
- `request_handler_mixin.py` extrahiert: `beagle-control-plane.py` 1627 → 899 LOC (03bd203)
- **Multi-Node Cluster**: srv1 (46.4.96.80) + srv2 (176.9.127.50) verbunden (52f5d48)
  - `BEAGLE_MANAGER_LISTEN_HOST=0.0.0.0` auf beiden Servern
  - members.json URLs korrigiert (127.0.0.1 → echte IPs)
  - srv2 via Join-Token beigetreten: `3/3 nodes online, 0 unreachable`
- **Cluster-Metriken**: `beagle-0` (srv1) und `beagle-1` (srv2) zeigen echte RAM/CPU-Werte
  - Root-Ursache: Beide Hypervisoren hießen `beagle-0` (Name-Kollision)
  - Fix: `BEAGLE_BEAGLE_PROVIDER_DEFAULT_NODE=beagle-0` auf srv1, `beagle-1` auf srv2
  - `/api/v1/cluster/nodes` zeigt jetzt `beagle-0: 64GB/12CPU`, `beagle-1: 64GB/8CPU`
- **GoEnterprise: VM Stateless Reset** umgesetzt:
  - Neuer Provider-Contract + Implementierung `reset_vm_to_snapshot(...)`
  - Pool-Manager-Wiring aktiv (`reset_vm_to_template`), nutzt Template-`snapshot_name`
- **GoEnterprise: RBAC kiosk_operator** umgesetzt:
  - Neue Default-Rolle `kiosk_operator` mit `vm:read`, `vm:power`
  - VM-Power-Endpoint nutzt jetzt Permission `vm:power` (Backwards-Compat für `vm:mutate` bleibt)
- **Cluster-Sicherheit Port 9088 gehärtet**:
  - Neues reproduzierbares Script `scripts/harden-cluster-api-iptables.sh` (idempotent, Chain `BEAGLE_CLUSTER_API_9088`)
  - Live ausgerollt auf `srv1`/`srv2` mit Peer-Allowlist (`srv1` erlaubt `176.9.127.50`, `srv2` erlaubt `46.4.96.80`)
  - Persistenz aktiviert (`netfilter-persistent` + `iptables-persistent`, `rules.v4` enthält 9088-Chain)

---

### Verbleibende Punkte (nach Priorität)

0. **GPU-Zeitfenster auf `srv2` nutzen, solange der Host noch verfuegbar ist**:
   - Erledigt: `srv2` GPU-Passthrough-Smoke per transienter VM; Gast sah GTX 1080 (`10de:1b80`) und Audio (`10de:10f0`).
   - Erledigt: GPU-Plane-WebUI mit Assign-/Release-Wizard, mdev-Cards, SR-IOV-Cards und UI-Regressions; Assets auf `srv1`/`srv2` ausgerollt.
   - Optional: voller NVIDIA-Treiber-/Streaming-Benchmark im Gast, falls `srv2` noch lange genug verfuegbar bleibt.
   - Danach: offene Nicht-GPU-WebUI-Smokes fuer IAM/Audit und die restlichen GoAdvanced/GoEnterprise-Punkte weiter abarbeiten.

1. **Plan 07 Rest-Lasttest**:
   - Optionalen 5GB-Backup-Lasttest auf `srv1` mit echter gross genug belegter VM/Disk ausfuehren.
   - Funktional ist Plan 07 runtime-faehig: Worker-Handler, SSE, UI-Subscribe, Idempotency und persistierte Job-History sind validiert.

2. **Plan 09 Schritt 6**: Branch-Protection-Regeln in GitHub repository settings aktivieren.
   _Manueller Schritt im GitHub UI; nicht Teil der technischen Untersetzung._

3. **QEMU+SSH Migration-Protokoll debuggen** (optional, nicht auf kritischem Pfad):
   - Untersuche Libvirt-Konfiguration, Firewall-Regeln, SSH-Agent-Issues
   - Alternativ: Shared Storage für Migration evaluieren
- Echten Runtime-Test fuer den neuen Windows-Live-USB-Writer auf Windows/UEFI-Hardware oder Windows-VM durchziehen und Bootverhalten verifizieren.
- Host-Downloads auf `srv1.beagle-os.com` und `srv2.beagle-os.com` mit den neuen `pve-thin-client-live-usb-*.ps1` Artefakten aktualisieren und per Download-Status gegenpruefen.
- WebUI-VM-Detail live auf `srv1`/`srv2` gegen den neuen `live-usb.ps1`-Pfad smoke-testen.
- Repo-/Artifact-Self-Heal weiter härten:
  - End-to-end smoke for VM installer/live-USB downloads after the next unattended repo auto-update on `srv1`
  - verify that regenerated hosted artifacts and VM-specific scripts still stay on `443` after that unattended update cycle
  - watch for repeated kiosk `npm` rename failures; `scripts/package.sh` now self-heals `ENOTEMPTY` once, but Node 18 engine warnings remain technical debt for the kiosk build chain
- GoRelease als neue Freigabeebene nutzen:
  - `docs/gorelease/00-index.md` vor Firmen-/Pilot-Entscheidungen lesen
  - zuerst R2/R3-Gates abarbeiten, nicht neue GoEnterprise-Features als "fertig fuer Firmen" interpretieren
  - Hardware nach `docs/gorelease/02-hardware-test-matrix.md` buchen: kleine Hetzner VMs fuer guenstige Dauer-Smokes, dedizierte KVM-Hosts nur fuer echte VM-/Install-Abnahme, GPU-Server nur im kurzen Testfenster
- Lokale GoRelease-Validierung ist bereits gruen:
  - Download-URLs normalisieren `443` weg
  - Installer-Downloads schreiben scoped Log-Events via API
  - naechster Schritt sind die verbleibenden Host-/Live-Gates auf `srv1`; `srv2` ist gekuendigt
- Thin-client USB install path runtime-smoke:
  - boot a freshly written USB installer/live medium in a VM
  - verify from installer logs that local bundled payload assets are used after the target-disk selection step
  - ensure no second remote payload download happens unless `PVE_THIN_CLIENT_FORCE_REMOTE_PAYLOAD=1`
- `srv2` TLS-/Zertifikatskette pruefen: Chrome DevTools sah am 27.04.2026 initial `ERR_CERT_AUTHORITY_INVALID`, obwohl die WebUI nach Ausnahme-Proceed und der Login-POST selbst funktionierten.
- Optional: Login-Modal/weitere Passwortfelder im HTML in echte `<form>`-Container ueberfuehren, damit die verbleibenden DevTools-DOM-Warnungen (`Password field is not contained in a form`) verschwinden.
- GoEnterprise Plan 03 weiterziehen:
  - Kiosk-Controller nicht nur im DOM, sondern mit echter Admin-Session auf `srv1`/`srv2` end-to-end testen
  - Session-Verlaengerung/Reset-Aktion statt nur `end` produktiv machen
  - pruefen, ob `kiosk_operator` fuer die gewuenschte Sichtbarkeit zusaetzlich Pool-Scoped Filter statt globaler Kiosk-Sicht braucht
- GoEnterprise Plan 03 / Plan 10 weiterziehen:
  - Pool-Wizard fuer GPU-Pooltypen weiterziehen: heute live Passthrough-Selektor + mdev/SR-IOV-Hints; als naechstes echte authentifizierte Slot-/Klassenvalidierung vervollstaendigen
- authenticated Live-Smoke fuer Gaming-Pools auf `srv1`/`srv2`: Stream-Health fuer echte Gaming-Session einspeisen und Dashboard mit Live-Daten pruefen
- `docs/goenterprise/03-gaming-kiosk-pools.md`: verbleibende Testpflicht fuer Gaming-Pool-Allocation ohne GPU sowie Kiosk-/RBAC-E2E sauber abschliessen
# Next Steps

## Stand (2026-04-28, GoEnterprise Plan 04/09 telemetry follow-up)

**Zuletzt erledigt**:
- Prewarm-Erfolg wird jetzt als echte Hit-/Miss-Telemetrie im Pool-Manager persistiert.
- Warm-Pool-Empfehlungen lassen sich direkt aus dem Scheduler-Panel anwenden.
- Das stündliche Energy-Profil hat jetzt einen eigenen Import-Endpunkt und eigenen UI-Flow.

**Naechste konkrete Schritte**:

1. **Plan 04 weiter operationalisieren**: Warm-Pool-Empfehlungen nicht nur manuell anwenden, sondern optional als sichere Auto-Scale-Policy ausführen.
2. **Plan 04 Erfolgsmessung vertiefen**: echte Wait-Time-Metrik aus Session-/Provisioning-Pfaden statt pauschalem `saved_wait_seconds`-Default erfassen.
3. **Plan 09 Feed vervollständigen**: externen Feed-/Importjob für das 24h-CO₂-/Preisprofil periodisch nachziehen.
4. **Plan 02 live validieren**: Lock-Screen, Wipe und Runtime-Telemetrie weiter gegen echte Thin-Client-Hardware/X11-/Wayland-Sessions abnehmen.
5. **Plan 07 live validieren**: Fleet-Alerts und Predictive-Maintenance gegen echte Runtime-Events provozieren und Webhook-/UI-Reaktion prüfen.

## Stand (2026-04-28, GoEnterprise Plan 04/09 productive follow-up)

**Zuletzt erledigt**:
- `smart_scheduler` hängt jetzt im produktiven Pool-Placement-Pfad für neue Desktop-Slots.
- Scheduler-Insights differenzieren `saved_cpu_hours` jetzt nach Pool und User.
- Energy-Dashboard arbeitet jetzt mit einem editierbaren stündlichen CO₂-/Strompreisprofil statt nur einer globalen Basiskonfiguration.

**Naechste konkrete Schritte**:

1. **Plan 04 Placement weiter haerten**: den Smart-Scheduler nicht nur bei Slot-Registrierung, sondern auch bei Scale-/Warm-Pool-Entscheidungen tiefer einziehen.
2. **Plan 04 Erfolgsmessung haerten**: echte Prewarm-Hit-/Miss-Telemetrie statt rein kandidatbasierter Saved-CPU-Hours-Auswertung aufbauen.
3. **Plan 09 Feed operationalisieren**: stündliches CO₂-/Strompreisprofil optional aus externem Feed oder Importjob aktualisieren, statt nur manuell im Dashboard.
4. **Plan 02 live validieren**: Lock-Screen, Wipe und Runtime-Telemetrie weiter gegen echte Thin-Client-Hardware/X11-/Wayland-Sessions abnehmen.
5. **Plan 07 live validieren**: Fleet-Alerts und Predictive-Maintenance gegen echte Runtime-Events provozieren und Webhook-/UI-Reaktion prüfen.

## Stand (2026-04-28, GoEnterprise Plan 04/09 green-window follow-up)

**Zuletzt erledigt**:
- Scheduler-Insights rendern jetzt eine stündliche 7-Tage-Heatmap pro Node statt nur Tagesdurchschnittstabellen.
- Green Scheduling ist im produktiven Scheduler-Pfad jetzt zeitfensterbasiert über `green_hours` verdrahtet.
- Energy-Dashboard zeigt jetzt eine eigene Green-Hours-Heatmap aus Carbon-/Strompreis-Konfiguration und Scheduler-Fenster.

**Naechste konkrete Schritte**:

1. **Plan 04 produktiv schließen**: `smart_scheduler` wirklich als optionalen Drop-In in den produktiven Pool-/Placement-Pfad ziehen.
2. **Plan 04 Analytics vertiefen**: Saved-CPU-Hours und Prewarm-Erfolg pro Pool/User differenzieren statt nur global zu summieren.
3. **Plan 09 Datenbasis vertiefen**: echten stündlichen Carbon-/Strommix-Feed hinter die Green-Hours-Heatmap legen, statt nur die aktuelle Konfiguration zu projizieren.
4. **Plan 02 live validieren**: Lock-Screen, Wipe und Runtime-Telemetrie weiter gegen echte Thin-Client-Hardware/X11-/Wayland-Sessions abnehmen.
5. **Plan 07 live validieren**: Fleet-Alerts und Predictive-Maintenance gegen echte Runtime-Events provozieren und Webhook-/UI-Reaktion prüfen.

## Stand (2026-04-28, GoEnterprise Plan 04/05/09 drilldown follow-up)

**Zuletzt erledigt**:
- Chargeback-Dashboard zeigt jetzt den Drilldown Abteilung -> User -> Session direkt aus der Control Plane.
- Energy-Dashboard hat jetzt echte Rankings fuer hoechsten/niedrigsten Node-Verbrauch sowie energieintensivste/effizienteste VMs.
- Scheduler-Operatorik modelliert Green Hours jetzt explizit und zeigt den aktiven Green-Window-Status direkt im Dashboard.

**Naechste konkrete Schritte**:

1. **Plan 04 vertiefen**: Heatmap-Visualisierung und differenzierte Saved-CPU-Hours pro Pool/User statt nur Gesamtwert nachziehen.
2. **Plan 04 haerten**: Green-Hours nicht nur anzeigen, sondern die zeitfensterbasierte Placement-/Prewarm-Entscheidung tiefer in den produktiven Scheduler-Pfad ziehen und mit eigener Regression absichern.
3. **Plan 09 vervollstaendigen**: Gruene-Stunden-Heatmap im Energy-Panel aus echten Carbon-/Strommix-Daten rendern.
4. **Plan 02 live validieren**: Lock-Screen, Wipe und Runtime-Telemetrie weiter gegen echte Thin-Client-Hardware/X11-/Wayland-Sessions abnehmen.
5. **Plan 07 live validieren**: Fleet-Alerts und Predictive-Maintenance gegen echte Runtime-Events provozieren und Webhook-/UI-Reaktion pruefen.
