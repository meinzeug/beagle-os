# Next Steps

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
3. **Watchdog mit Repo-Update zusammenspielen lassen**: auf einem Host absichtlich Artefakt-Drift nach erfolgreichem Repo-Update erzeugen und bestaetigen, dass der Watchdog `reaction=started_refresh` setzt und wieder `healthy/public_ready=true` erreicht.
4. **GitHub Release-Workflow erneut gegen echten Push pruefen**: bestaetigen, dass `.github/workflows/release.yml` nach dem Parse-Fix wieder laeuft und auf Push nach `main` einen neuen Rolling-/Release-Lauf erzeugt.
5. **APT-Automatik-Policy klaeren**: derzeit prueft die Karte automatisch und installiert APT manuell; falls OS-Paketupdates vollautomatisch installiert werden sollen, muss ein eigener sicherer unattended-upgrades-/Timer-Pfad gebaut werden.
6. **Plan 12 Schritt 6 fortsetzen**: GPU-Zuweisung und Release als gefuehrten Wizard/Danger-Flow bauen statt Prompt-Aktionen.
7. **Plan 12 Schritt 6 fortsetzen**: vGPU-/mdev- und SR-IOV-Bereiche von Tabellen auf Cards/erklaerende Operator-Flows umstellen.
8. **Thinclient-Hardware-Rerun auf echtem Stick**: neuen VM100-USB-Stick von `srv1` erzeugen und den bisher fehlgeschlagenen physischen `Preset Installation starten`-Pfad auf echter Hardware erneut abnehmen.
9. **Thinclient-Runtime visuell abnehmen**: lokale installierte Ziel-Disk mit grafischem Capture/Screenshot bis zur sichtbaren Moonlight-Session gegen `vm100` pruefen.
10. **Security vor Cluster-Komfort**: `8443` auf downloads-only reduzieren oder schließen; Installer-/Download-Pfade vorher sauber auf `443` migrieren.
11. **Leader-State-Reconcile bauen**: Drift in `members.json` reproduzierbar erkennen und vom Leader aus sauber neu aufbauen oder gegen den Cluster-Store abgleichen.
12. **Plan 10/13/15 Panels fortsetzen**: `/#panel=policies`, `/#panel=iam`, `/#panel=audit` von Statusansichten zu echten Operator-Flows umbauen.

**Blocker/Risiken**:
- `srv2` GPU: GTX 1080 ist an `vfio-pci`, aber IOMMU-Gruppe enthaelt weitere Geraete; Passthrough bleibt ohne ACS/BIOS/Hardware-Aenderung nicht sicher freigebbar.
- Artifact-Refresh ist jetzt auf `srv1` und `srv2` gruen; offener Rest fuer Plan 06 ist jetzt das echte Zusammenspiel `GitHub-Repo-Update -> Host-Deploy -> Artifact-Watchdog`.

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

1. **Plan 09 Schritt 6**: Branch-Protection-Regeln in GitHub repository settings aktivieren.
   _Manueller Schritt im GitHub UI; nicht Teil der technischen Untersetzung._

2. **QEMU+SSH Migration-Protokoll debuggen** (optional, nicht auf kritischem Pfad):
   - Untersuche Libvirt-Konfiguration, Firewall-Regeln, SSH-Agent-Issues
   - Alternativ: Shared Storage für Migration evaluieren
- Echten Runtime-Test fuer den neuen Windows-Live-USB-Writer auf Windows/UEFI-Hardware oder Windows-VM durchziehen und Bootverhalten verifizieren.
- Host-Downloads auf `srv1.beagle-os.com` und `srv2.beagle-os.com` mit den neuen `pve-thin-client-live-usb-*.ps1` Artefakten aktualisieren und per Download-Status gegenpruefen.
- WebUI-VM-Detail live auf `srv1`/`srv2` gegen den neuen `live-usb.ps1`-Pfad smoke-testen.
