# Next Steps

## Delta (2026-04-23 nach Abschluss Plan 16 Schritt 2)

0. **Plan 16 Schritt 3 starten (Backup-Targets lokal/NFS/S3)**:
	- `BackupTarget`-Protokoll in `core/` definieren (`write_chunk`, `read_chunk`, `list_snapshots`),
	- konkrete Targets (`LocalBackupTarget`, `NfsBackupTarget`, `S3BackupTarget`) einziehen,
	- API-/Service-Anbindung fuer Target-Auswahl pro Scope vorbereiten.

0. **Plan 16 PoC-Metrik weiter optimieren**:
	- Restic-Delta-Ratio aus PoC (`0.5097`) Richtung Testpflichtziel `<10%` verbessern,
	- dafuer qemu-dirty-bitmap/externe Snapshot-Kette als naechste Iteration evaluieren.

0. **Infra-blockierte Punkte bleiben offen**:
	- Plan 07 Live-Migration Host-A→B,
	- Plan 08 NFS + Live-Migration auf zweitem Host,
	- Plan 11 Auto-Pairing (aktuell `pair-exchange 502`).

## Delta (2026-04-23 nach Abschluss Plan 08 Testpflicht Directory+ZFS)

0. **Plan 08 verbleibende Testpflicht abschliessen (NFS + Migration)**:
	- NFS-Backend-Live-Nachweis benoetigt konfiguriertes NFS (`exportfs`/`showmount`) plus zweiten erreichbaren Cluster-Host,
	- danach offenen NFS-Checkboxpunkt in `docs/gofuture/08-storage-plane.md` schliessen.

0. **Plan 07 verbleibende Live-Migration-Testpflicht**:
	- echter Host-A→Host-B Nachweis bleibt offen bis zweiter libvirt-Host von `srv1` aus erreichbar ist,
	- nach Bereitstellung: `POST /api/v1/vms/{vmid}/migrate` End-to-End mit laufender VM validieren und Checkbox setzen.

0. **Plan 11 verbleibende Streaming-v2 Testpflicht**:
	- Linux 4K@60 ohne Artefakte und Auto-Pairing End-to-End auf Runtime reproduzierbar abschliessen,
	- Windows/Apollo-Vergleich nur bei verfuegbarer Windows-Guest-Umgebung weiterziehen.

## Delta (2026-04-23 nach Abschluss von Plan 14 Schritt 1: session_recording Policy)

0. **Plan 14 offene Testpflicht priorisieren**:
	- Pool `session_recording: always` gegen echte Session + MP4-Erzeugung auf Runtime nachweisen,
	- Watermark-Sichtbarkeit als reproduzierbaren Smoke einfuehren (Plan 14 Schritt 4).

0. **Plan 14 Schritt 4 umsetzen (Watermark-Overlay)**:
	- Apollo-Plug-in oder guest-side Overlay-Layer implementieren,
	- konfigurierbaren Watermark-Text (Nutzername/Timestamp/Freitext) in Session-Start-Flow verdrahten.

## Delta (2026-04-23 nach Abschluss von Plan 15 Schritt 2: Audit-Export)

0. **Plan 15 Testpflicht weiter schliessen**:
	- S3/Minio-Live-Nachweis (`JSON-Lines` im Bucket) auf Test-Target fahren,
	- CSV-Report-Vollstaendigkeit und Audit-Viewer-Filter-Live-Nachweis reproduzierbar dokumentieren.

0. **Naechster umsetzbarer offener GoFuture-Codeblock**:
	- Plan 14 Schritt 1 (`session_recording` Feld + Pool-Editor),
	- danach Storage/Retention-Schritte in Plan 14 weiterziehen.

## Delta (2026-04-23 nach Abschluss von Plan 12 Schritt 5: gpu_class Constraint)

0. **Plan 12 Testpflicht abschliessen (runtime-blockiert auf srv1)**:
	- GPU-Passthrough- und vGPU-Nachweise benoetigen echte GPU-Hardware (inkl. `nvidia-smi` / Mehr-VM-vGPU-Lauf),
	- auf `srv1.beagle-os.com` sind keine mdev/SR-IOV-faehigen GPUs verfuegbar; daher nur API-/State-Smoke reproduzierbar.

0. **Naechster umsetzbarer offener GoFuture-Block**:
	- Plan 11 Schritt 6 (Windows Apollo + SudoVDA Eval + Benchmark) oder
	- Plan 15 Schritt 2 (Audit-Export-Targets S3/Syslog/Webhook) je nach verfuegbarer Runtime.

## Delta (2026-04-23 nach Abschluss von Plan 12 Schritt 2: GPU-Passthrough)

0. **Plan 12 Schritt 3 starten (NVIDIA vGPU / mdev)**:
	- `vgpu_service.py` implementieren: mdev-Typen aus `/sys/class/mdev_bus/*/mdev_supported_types/` lesen, Instanzen anlegen,
	- Web Console: vGPU-Typ und Slot auswählen bei VM-Konfiguration.

0. **Plan 11 verbleibende Testpflicht (runtime-blockiert)**:
	- Linux 4K@60 ohne Artefakte (vkms/xrandr Blocker auf srv1),
	- Auto-Pairing ohne manuellen PIN (Sunshine pair-exchange 502 Blocker).

## Delta (2026-04-24 nach Abschluss von Plan 12 Schritt 1: GPU-Inventory)

0. **Plan 12 Schritt 2 starten (GPU-Passthrough-Workflow)**:
	- `gpu_passthrough_service.py` implementieren: vfio-pci-Binding, Treiber-Detach, libvirt-XML-Patch,
	- Web Console: "GPU zu VM zuweisen" Action im VM-Detail.

0. **Plan 11 verbleibende Testpflicht (runtime-blockiert)**:
	- Linux 4K@60 ohne Artefakte (vkms/xrandr Blocker auf srv1),
	- Auto-Pairing ohne manuellen PIN (Sunshine pair-exchange 502 Blocker).



0. **Plan 11 Schritt 6 starten (Windows Apollo Eval/Benchmark)**:
	- Windows Guest + SudoVDA Eval-Lauf aufsetzen,
	- reproduzierbare Benchmark-Matrix Sunshine (Linux) vs Apollo (Windows) fuer gleiche Workload/Resolution definieren,
	- Ergebnisse in `docs/refactor/07-decisions.md` unter `D-031` nachziehen.

0. **Plan 11 verbleibende Testpflicht schliessen**:
	- Linux 4K@60 ohne Artefakte weiter absichern,
	- Auto-Pairing ohne manuellen PIN als E2E-Live-Nachweis fahren,
	- Multi-Monitor-Linux-Lauf mit dokumentiertem Ergebnis validieren.

0. **Plan 09 Multi-Node-Testpflicht bleibt runtime-blockiert**:
	- aktueller Live-Stand `srv1` zeigt nur einen Online-Knoten,
	- fuer offene HA-/Anti-Affinity-Nachweise ist ein zweiter online libvirt-Host erforderlich.

## Delta (2026-04-23 nach Abschluss von Plan 11 Schritt 4 Test-Matrix)

0. **Plan 11 Schritt 6 beginnen (Windows Apollo Eval)**:
	- Windows Guest + SudoVDA Evaluationspfad vorbereiten,
	- erste reproduzierbare Apollo-Laufzeitpruefung mit klaren PASS/FAIL-Kriterien aufsetzen.

0. **Plan 11 Testpflicht verbleibende Punkte schliessen**:
	- 4K@60 ohne Artefakte (Linux vkms) weiterhaerten,
	- Auto-Pairing End-to-End ohne manuellen PIN als Live-Nachweis fahren,
	- Stream-Health-Metriken waehrend aktiver Session in der WebUI sichtbar nachweisen.

## Delta (2026-04-23 nach Abschluss von Plan 09 Schritt 5)

0. **Plan 09 Testpflicht-Checkboxen schliessen**:
	- Knoten-Ausfall-Recovery <=60s als reproduzierbaren Lauf auf echter Multi-Node-Runtime nachweisen,
	- Fencing-Startblockade (kein VM-Start vor Abschluss) live pruefen,
	- Maintenance-Drain-Ende-zu-Ende sowie Anti-Affinity-Verteilung auf mindestens zwei echten Nodes validieren.

0. **HA-Alerts an echte Fencing-Ereignisse koppeln**:
	- Watchdog/Fencing-Eventpfad im Runtime-Betrieb triggern,
	- pruefen dass Bannertext und Node-Status in der Web Console waehrend/nach Fencing korrekt wechseln.

## Delta (2026-04-23 nach Abschluss von Plan 09 Schritt 4)

0. **Plan 09 Schritt 5 umsetzen (HA-Status in Web Console)**:
	- Cluster-Panel um HA-Status-Sektion erweitern (Node-Health, letzter Heartbeat, HA-geschuetzte VM-Anzahl),
	- globalen Alert-Banner fuer Quorum-Untergrenze und aktive Fencing-Aktionen anbinden.

0. **Plan 09 Testpflicht-Checkboxen schliessen**:
	- reproduzierbare Nachweise fuer Knoten-Ausfall-Recovery-Zeiten, Fencing-Startblockade und Anti-Affinity auf echter Multi-Node-Runtime liefern,
	- offene Test-Checkboxen in `docs/gofuture/09-ha-manager.md` danach schliessen.

0. **Single-Node-Runtime-Hinweis fuer SchedulerPolicy beibehalten**:
	- bei nur einem Online-Knoten bleibt Anti-Affinity best effort,
	- Multi-Node-Verteilung weiterhin als Pflicht-Smoke auf zwei echten Hosts validieren.

## Delta (2026-04-23 nach Abschluss von Plan 07 Schritt 4 + Schritt 5)

0. **Plan 07 Testpflicht gegen echte Multi-Node-Runtime schliessen**:
	- zwei echte Cluster-Knoten parallel betreiben und beide in der Web Console sichtbar machen,
	- Live-Migration einer laufenden Test-VM zwischen zwei Hosts real ausfuehren,
	- `unreachable`-Anzeige innerhalb von 10 Sekunden gegen echten Knotenausfall pruefen.

0. **Installer-Join Ende-zu-Ende fertigziehen**:
	- frisch installierten Host mit dem neuen Dialog gegen einen bestehenden Leader joinen lassen,
	- Zertifikatsausstellung, Cluster-Store-Registrierung und sofortige Sichtbarkeit in der Knoten-Liste live nachweisen.

0. **Plan 11 Resume danach wieder aufnehmen**:
	- Audio-In/Gamepad-Matrix sauber dokumentieren,
	- anschliessend Windows-Apollo-Eval fuer Streaming-v2 vorbereiten.

## Delta (2026-04-23 nach Abschluss von Plan 07 Schritt 2 + Schritt 3 Teil 2)

0. **Plan 07 Schritt 4 umsetzen (Live-Migration)**:
	- `beagle-host/services/migration_service.py` mit libvirt-managed Migration anlegen,
	- API-Seam fuer Vorbedingungen/Progress/Error-State definieren,
	- anschliessend UI-Aktion `VM verschieben` in der Detailansicht verdrahten.

0. **Plan 07 Schritt 5 starten (Cluster-Join im Installer)**:
	- Installer-Dialog fuer Cluster-Join (`Ja/Nein`) ergaenzen,
	- Eingabe fuer Leader-IP oder Join-Token und Uebergabe an den neuen CA-/RPC-Pfad vorbereiten.

0. **Plan 07 Testpflicht vorbereiten**:
	- zwei echte Cluster-Knoten gegen `srv1.beagle-os.com` aufbauen,
	- Multi-Node-Sichtbarkeit und `unreachable`-Darstellung gegen das bestehende Cluster-Panel validieren.

## Delta (2026-04-22 nach Abschluss von Plan 11 Schritt 5)

0. **Plan 11 Schritt 4 Test-Matrix schliessen**:
	- Audio-In/Gamepad/Wacom/USB-Redirect als reproduzierbare Matrix in `docs/gofuture/11-streaming-v2.md` dokumentieren,
	- fuer den aktuell umgesetzten Scope mindestens Audio-In + Gamepad live mit klaren API/UI-Belegen als `✓` nachziehen.

0. **Plan 11 Schritt 6 vorbereiten (Windows Apollo Eval)**:
	- minimalen Windows-Guest-Eval-Plan fuer Apollo + SudoVDA festziehen,
	- Vergleichskriterien Sunshine(Linux) vs Apollo(Windows) als messbare Baseline definieren.

## Delta (2026-04-22 nach Abschluss von Plan 11 Schritt 4)

0. **Plan 11 Schritt 5 einleiten (Stream-Health-Telemetrie)**:
	- Sunshine/Apollo-Session-Metriken (RTT, FPS, Dropped-Frames, Encoder-Load) via API in `session.stream_health` speichern,
	- Web-Console Session-Detailansicht mit Stream-Health-Graph erweitern.

## Delta (2026-04-22 nach Plan 11 Schritt 5 Bootstrap)

0. **Plan 11 Schritt 5 weiterziehen (echte Metriken statt `null`)**:
	- Polling-Quelle fuer Sunshine/Apollo-Stats fest in den Session-/Lease-Flow einhaengen,
	- `session.stream_health` mit echten Feldern (`rtt_ms`, `fps`, `dropped_frames`, `encoder_load`) fuellen,
	- API-Vertrag fuer Zeitreihenfenster (z. B. last N samples) festlegen.

0. **Web-Console Session-Detail um Stream-Health erweitern**:
	- vorhandenes `stream_health` Feld visualisieren (zuerst kompakte KPI-Kacheln),
	- danach optional Live-Graph fuer Verlauf.

0. **Streaming-v2 Runtime hardenen**:
	- CRTC-Limit fuer 4K-Apply weiter reduzieren (Guest-Grafikpfad),
	- Moonlight-E2E mit 3840x2160@60 als Ziel-Nachweis abschliessen.

0. **Visual Smoke in Host-Smokes integrieren**:
	- `scripts/test-webui-visual-smoke.py` in einen bestehenden Host-Smoke-Lauf einhaengen,
	- damit Light/Dark-Panel-Regressionschecks automatisch pro Deploy laufen.

## Delta (2026-04-22 nach Abschluss von Plan 10)

0. **Plan 11 Schritt 2 starten (Auto-Pairing Token)**:
	- `beagle-host/services/pairing_service.py` anlegen,
	- kurzlebige signierte Pairing-Tokens (VM/Scope/Expiry) einbauen,
	- Endpoint-Flow von PIN-zentriert auf Token-Exchange umstellen.

0. **Plan 11 Rest aus Schritt 1 hardenen**:
	- CRTC-Limit fuer 4K-Apply (`xrandr: Configure crtc 0 failed`) in der VM-Grafikpipeline reduzieren,
	- Moonlight-E2E mit 3840x2160@60 als Ziel-Nachweis abschliessen.

0. **Plan 11 Backend-Selector vorbereiten**:
	- `beagle-host/services/streaming_backend.py` als platform-aware Selector (`linux -> sunshine`, `windows -> apollo`) anlegen,
	- Initial-Wiring im Provisioning-/Pool-Pfad vorbereiten ohne bestehenden Sunshine-Default zu brechen.

0. **Entitlement-Gruppenpfad spaeter end-to-end schliessen**:
	- sobald Auth-Principals echte Gruppenclaims tragen (OIDC/SAML/SCIM), dieselbe Sichtbarkeits-/Allocate-Semantik fuer Gruppen-Entitlements gegen echte Gruppenmitglieder validieren.

## Delta (2026-04-22 nach Plan 10 Testpflicht-Slice)

0. **Letzte offene Plan-10-Testpflicht schliessen**:
	- Entitlement nicht nur als `403` auf `allocate`, sondern als echte Sichtbarkeits-/Filter-Semantik fuer User-Surfaces nachweisen oder implementieren,
	- anschliessend die letzte Checkbox in `docs/gofuture/10-vdi-pools.md` schliessen.

0. **Plan 11 vorbereiten**:
	- nach Abschluss der Entitlement-Sichtbarkeit mit `11-streaming-v2.md` weitermachen,
	- dabei zuerst den kleinsten echten Apollo/vDisplay-Laufzeit-Anchor waehlen.

## Delta (2026-04-22 nach Plan 10 Schritt 6)

0. **Plan 10 Testpflicht schliessen**:
	- auf `srv1.beagle-os.com` einen Pool mit 5 `floating_non_persistent`-VMs erzeugen,
	- Allocate/Release/Recycle-Flow inkl. <=60s Reset reproduzierbar dokumentieren,
	- persistenten Pool auf "zweiter Login bekommt dieselbe VM" verifizieren.

0. **Plan 10 Template-Builder E2E validieren**:
	- gestoppte Golden-VM in der Web Console zu Template bauen,
	- daraus Pool erstellen und erfolgreiche Verwendung der neuen Template-ID nachweisen.

0. **Plan 10 Entitlement-Testpflicht schliessen**:
	- User ohne Entitlement gegen Pool-Sicht/Allocate pruefen (erwartet kein Zugriff bzw. `403`),
	- Ergebnis inkl. API-Belegen und UI-Sicht dokumentieren.

## Delta (2026-04-22 nach Plan 10 Schritt 5)

0. **Plan 10 Schritt 6 umsetzen**:
	- Aktion `Neue VM als Template konvertieren` in der VM-Detailansicht einbauen,
	- Builder-Status-/Progress-Dialog fuer die Template-Erstellung in der Web Console anbinden.

0. **Plan 10 Testpflicht ausfuehren**:
	- auf `srv1.beagle-os.com` einen Pool mit 5 `floating_non_persistent`-Desktops erstellen,
	- Allocate/Release/Recycle inkl. <=60s Reset-Verhalten reproduzierbar testen und dokumentieren.

0. **Plan 10 Entitlement-Runtime gegen echte User pruefen**:
	- User ohne Entitlement gegen `allocate` pruefen (erwartet `403`),
	- Sichtbarkeit/Handling in der Web Console mit echten User-Rollen gegenvalidieren.

## Delta (2026-04-22 nach Plan 10 Schritt 1-4 Backend-Basis)

0. **Plan 10 Web-Console-Surface bauen**:
	- Pool-Wizard in `website/` umsetzen (`Template -> Groesse -> Modus -> Entitlements -> Bestaetigung`),
	- Pool-Uebersicht mit VM-Statusliste (`free`, `in-use`, `recycling`, `error`) anbinden.

0. **Plan 10 Template-Builder-UI nachziehen**:
	- Aktion `Neue VM als Template konvertieren` in der VM-Detailansicht verdrahten,
	- Builder-Progress-/Status-Dialog gegen die neue `/api/v1/pool-templates` Surface anbinden.

0. **Plan 10 Runtime-Testpflicht erweitern**:
	- echten Pool mit mehreren Slot-VMs auf `srv1.beagle-os.com` anlegen,
	- Entitlement-/Allocate-/Release-/Recycle-Flow gegen reale VM-Zustaende validieren.

## Delta (2026-04-22 nach Plan 10 Schritt 4 Teil 1)

0. **Plan 10 Entitlement-API nachziehen**:
	- `POST /api/v1/pools/{pool}/entitlements` im Control-Plane verdrahten,
	- RBAC fuer Pool-Entitlement-Mutationen festlegen und testen.

0. **Plan 10 Runtime-Verknuepfung bauen**:
	- `pool_manager.py` und Entitlement-Service koppeln,
	- Session-Zuweisung nur bei gueltigem Entitlement zulassen.

## Delta (2026-04-22 nach Plan 10 Schritt 2 Teil 1 + Schritt 3 Teil 1)

0. **Plan 10 Pool-Lifecycle starten**:
	- `beagle-host/services/pool_manager.py` als naechsten umsetzbaren Block implementieren,
	- dabei zuerst `floating_non_persistent` Ende-zu-Ende lauffaehig machen.

0. **Plan 10 Modus-Umsetzung fortsetzen**:
	- Enum ist vorhanden, als naechstes die mode-spezifische Runtime-Logik im Pool-Manager abbilden,
	- anschliessend API-Seam fuer Pool-CRUD + Lease-Aktionen vorbereiten.

## Delta (2026-04-22 nach Plan 10 Schritt 1 Teil 1)

0. **Plan 10 Schritt 1 Teil 2 umsetzen**:
	- Template-Builder-Service fuer `Snapshot -> Seal -> Backing-Image` implementieren,
	- API-Seam fuer Build-Start/Status vorbereiten.

0. **Plan 10 Basisschicht fortsetzen**:
	- anschliessend `core/virtualization/desktop_pool.py` als naechsten Contract-Schritt bauen,
	- danach Pool-Lifecycle in `beagle-host/services/pool_manager.py` beginnen.

## Delta (2026-04-22 nach Plan 08 Schritt 5)

0. **Plan 08 Testpflicht schließen**:
	- End-to-End-Validation der Backends (Directory/ZFS/NFS) gegen reale Host-Laufzeit durchführen,
	- die verbleibenden Test-Checkboxen fuer Directory/ZFS/NFS auf echter Runtime schließen.

0. **Plan 08 Rest-Testpflicht (nur noch Storage-Backends)**:
	- Directory: VM create/start/snapshot/restore als reproduzierbaren Smoke dokumentieren,
	- ZFS: Snapshot + Clone auf echtem ZFS-Pool verifizieren,
	- NFS + Migration: Shared-Storage-Lauf gegen zweiten Knoten mit Live-Migration abschliessen.

## Delta (2026-04-22 nach Plan 08 Schritt 4)

0. **Plan 08 Schritt 5 umsetzen**:
	- `providers/beagle/storage/nfs.py` als Shared-Storage-Backend auf Basis des bestehenden `DirectoryStorageBackend`-Patterns implementieren,
	- Pfad-/Mount-Validierung fuer konsistente Cluster-NFS-Mounts einbauen.

0. **Plan 08 Schritt 6 vorbereiten**:
	- API-Surface fuer Storage-Quota (`GET/PUT /api/v1/storage/pools/{pool}/quota`) im Control-Plane modellieren,
	- quota-aware create-path in Storage-Manager integrieren.

## Delta (2026-04-22 nach Plan 08 Schritt 3)

0. **Plan 08 Schritt 4 umsetzen**:
	- `providers/beagle/storage/zfs.py` auf dem gleichen `StorageClass`-Contract implementieren,
	- Snapshot-/Clone-Operationen mit nativen `zfs`-Kommandos abdecken.

0. **Cross-Backend Surface angleichen**:
	- konsistente Volume-ID-/Pool-Semantik fuer directory/lvm/zfs in einem zentralen Storage-Manager harmonisieren,
	- danach Quota-API (Schritt 6) auf stabilen Backend-Abstraktionen aufsetzen.

## Delta (2026-04-22 nach Plan 08 Schritt 2)

0. **Plan 08 Schritt 3 starten**:
	- `providers/beagle/storage/lvm_thin.py` als naechstes Backend auf denselben `StorageClass`-Contract umsetzen,
	- Command-Adapter und Fehlerbehandlung analog zum Directory-Backend aufbauen.

0. **Storage-Plane Integration vorbereiten**:
	- Backend-Auswahl (directory/lvm_thin/...) in einem `storage_manager`-Service konsolidieren,
	- API-Seam fuer spaetere Quota-Endpunkte (`/api/v1/storage/pools/{pool}/quota`) vorziehen.

## Delta (2026-04-22 nach Plan 08 Schritt 1)

0. **Plan 08 Schritt 2 umsetzen**:
	- `providers/beagle/storage/directory.py` als erste konkrete `StorageClass`-Implementierung bauen,
	- qemu-img-basierte create/resize/snapshot/clone-Operationen plus `list_volumes` integrieren.

0. **Storage-Provider-Testabdeckung erweitern**:
	- Unit-Tests fuer Directory-Backend mit Command-Stubs und Dateisystem-Fallbacks ergaenzen,
	- auf `srv1.beagle-os.com` per Import-/Smoke-Test validieren.

## Delta (2026-04-22 nach Plan 07 Schritt 6)

0. **Plan 07 Schritt 3 fortsetzen**:
	- bereits umgesetzt: `cluster_inventory.py` + `/api/v1/cluster/inventory`.
	- als Nächstes: Remote-Node-Aggregation über kommende Cluster-RPC-Schicht vorbereiten.

0. **Cluster-Panel live gegen Multi-Node validieren**:
	- zwei Testknoten einbinden,
	- verifizieren, dass Status/CPU/RAM/VM-Count pro Knoten korrekt und stabil aktualisieren.

0. **Plan 07 Schritt 4 vorbereiten**:
	- API-Seam für `migration_service.py` definieren,
	- UI-Aktion "VM verschieben" im VM-Detail als nächster implementierbarer Block planen.

## Delta (2026-04-21 nach Audit Schritt 1/3/4/5 + VM-Installer-Hotfix)

0. **Plan 15 Schritt 2 umsetzen**:
	- `beagle-host/services/audit_export.py` fuer S3/Minio, Syslog und Webhook bauen,
	- Retry/Pufferung fuer Export-Fehler definieren.

0. **Plan 15 Rest-Validierung schliessen**:
	- Audit-Viewer-Filter auf `srv1` noch gezielt gegen echte User-/Action-Kombinationen durchklicken,
	- CSV-Inhalt gegen laengeren Zeitraum verifizieren und Testpflicht-Checkboxen sauber schliessen.

0. **Host-Downloads wieder kanonisch vervollstaendigen**:
	- `scripts/prepare-host-downloads.sh` bzw. Host-Artifact-Refresh so nachziehen, dass die `dist/`-Templates auf dem Host wieder vorhanden sind,
	- Fallback in `InstallerScriptService` als Guardrail beibehalten.

## Delta (2026-04-21 nach Plan 14 Schritte 2+5)

0. **Plan 14 Schritt 1 abschließen**:
	- `session_recording` Policy-Feld im Pool-Modell ergänzen,
	- Recording-Policy im Web-Console Pool-Editor einführen.

0. **Plan 14 Schritt 3 umsetzen**:
	- Recording-Storage auf konfigurierbare Targets erweitern (lokal/NFS/S3),
	- Retention-Cleanup-Job mit Audit-Events implementieren.

0. **Plan 14 Schritt 4 umsetzen**:
	- Watermark-Overlay (server- oder guest-seitig) integrieren,
	- Watermark-Text konfigurierbar machen.

0. **Recording-Download hardening**:
	- Signed-URL-Modell statt direktem Byte-Download evaluieren und ggf. umsetzen,
	- Tenant-bezogene Download-Scopes ergänzen.

## Aktueller Status (2026-04-21 nach Plan 13 Schritte 4+5)

Plan 13 ist vollständig abgehakt (Schritte 1–6 alle [x]).

**Nächste offene GoFuture-Schritte:**

1. **Plan 14 — Session Recording + Watermark** (7.2.1): Recording-Infrastruktur für VDI-Sessions.
2. **Plan 15 — Audit-Export + Compliance-Report** (7.2.2): Strukturierter Audit-Export, Retention-Policy.
3. **OIDC-Hardening**: JWKS-Validierung für ID-Token-Signaturen ergänzen.
4. **SAML-Hardening**: ACS-POST-Endpoint mit Assertion-Signaturprüfung.
5. **SCIM PATCH**: Partial-Update-Semantik (RFC 7644 Operations).


## Delta (2026-04-21 nach Plan 13 Schritt 3: SCIM Surface)

0. **SCIM-Flow vervollständigen**:
	- `PATCH`-Semantik gemäß SCIM-Standard (Operations/Add/Replace/Remove) ergänzen,
	- Group-Member-Mapping auf Rollen-/User-Zuordnung erweitern.

0. **SCIM-Token-Hardening**:
	- SCIM-Token-Rotation + optional Hash-at-rest in Settings/Secrets-Store ergänzen,
	- Audit-Events für SCIM-Mutationen (`user.create/update/delete`, `group.create/update/delete`) pro Request schreiben.

## Delta (2026-04-21 nach Plan 13 Schritt 1+2: OIDC/SAML Basis)

0. **OIDC-Hardening abschließen**:
	- ID-Token-Signatur/JWKS-Validierung ergänzen (aktuell Claims-Extraktion ohne kryptografische Verifikation),
	- OIDC-Callback auf lokale Session-Erzeugung und UI-Redirect vervollständigen.

0. **SAML-Assertion-Flow vervollständigen**:
	- ACS-POST-Endpoint mit Signaturprüfung ergänzen,
	- Gruppen-/Rollen-Mapping und Audit-Events für fehlerhafte Assertions hinzufügen.

0. **Plan 18 Restpunkt bleibt offen**:
	- Terraform-Testpflicht (`terraform apply`/`destroy` mit realer VM auf `srv1`) abschließen.

## Delta (2026-04-21 nach Plan 13 Schritt 6: Multi-IdP Registry)

0. **Plan 13 Schritt 1/2 anschließen**:
	- OIDC-Service (`oidc_service.py`) und SAML-Service (`saml_service.py`) hinter die neue IdP-Registry hängen,
	- Login-Buttons aus `GET /api/v1/auth/providers` auf echte OIDC/SAML-Flows routen.

0. **Provider-Registry auf Runtime verifizieren**:
	- auf `srv1.beagle-os.com` mit Registry-Datei (`/etc/beagle/identity-providers.json`) testen,
	- Break-Glass-Fallback (`local`) bei fehlerhafter IdP-Konfiguration bestätigen.

0. **Plan 18 Restpunkt weiter offen**:
	- Terraform-Provider-Testpflicht (`apply/destroy`) auf `srv1` mit realer VM schließen.

## Delta (2026-04-21 nach Plan 18 Schritt 5 + Live-Checks)

0. **Deprecation-Rollout konkretisieren**:
	- weitere v1-Endpunkte, die in v2 entfallen sollen, in `BEAGLE_API_V1_DEPRECATED_ENDPOINTS` aufnehmen,
	- dazu Migrationsabschnitte in der öffentlichen API-Doku ergänzen.

0. **Plan 18 Schritt 4 ist abgeschlossen; Stabilisierung nachziehen**:
	- optional Delivery-Queue mit asynchronen Worker-Dispatches ergänzen (statt inline Dispatch),
	- erweiterte Event-Abdeckung über VM-Power hinaus priorisieren (z.B. Provisioning-/Backup-Events).

0. **beaglectl erweitern**:
	- über `list` hinaus mutierende Commands (`vm start/stop/reboot` mit klaren Exit-Codes) per srv1-Smoke gegen echte VMs verifizieren.

0. **Plan 18 Restpunkt schließen**:
	- Terraform-Provider (`terraform apply/destroy`) mit realer VM auf `srv1` validieren und letzte offene Testpflicht-Checkbox schließen.

## Delta (2026-04-21 nach Plan 18 Schritt 1+3: OpenAPI + beaglectl)

0. **OpenAPI-Generator präzisieren und CI-gebunden machen**:
	- Methodenerkennung weiter schärfen (weniger GET-Defaults),
	- Generator-Run als CI-Check einhängen (Fail bei Drift zwischen Code und `docs/api/openapi.v1.generated.yaml`).

0. **beaglectl End-to-End mit Auth-Token gegen srv1 verifizieren**:
	- `beaglectl vm list --json` mit gültigem Admin-/Service-Token live gegen `srv1.beagle-os.com` fahren,
	- danach Testpflicht-Checkbox in `docs/gofuture/18-api-iac-cli.md` setzen.

0. **Plan 18 Schritt 5 vorbereiten**:
	- konkrete Liste v1-Endpunkte definieren, die Deprecation-Header erhalten sollen,
	- Header-Ausgabe im Control-Plane-Response-Pfad zentral einziehen.

## Delta (2026-04-21 nach Plan 19 Schritt 6: Kiosk-Enrollment-Flow)

0. **Plan 19 Testpflicht für Gaming-Kiosk vollständig fahren**:
	- auf frischem Endpoint verifizieren: Boot -> Auto-Enrollment -> Spieleliste ohne manuelle `kiosk.conf`-Eingriffe,
	- Ergebnis in `docs/gofuture/19-endpoint-os.md` Testpflicht-Checkbox dokumentieren.

0. **Enrollment-Source im Installer weiterziehen**:
	- sicherstellen, dass `BEAGLE_ENROLLMENT_URL`/`BEAGLE_ENROLLMENT_TOKEN` beim Kiosk-Install aus Preset/Runtime automatisch in `kiosk.conf` landen.

0. **Kiosk-Ende-zu-Ende-Smoke auf srv1 ergänzen**:
	- kurzer Headless-/Runtime-Smoke für Enrollment-Statuswechsel (pending -> enrolled) als reproduzierbares Script unter `scripts/`.

## Delta (2026-04-21 nach Plan 19 Schritt 1: Endpoint-Profile-Struktur)

0. **Enrollment-Flow vorbereiten (Plan 19 Schritt 2)**:
	- QR-Code-Generator für Enrollment-Tokens (Python/qrcode Library),
	- Web-Console-Dialog "Neuen Endpoint enrollen" mit Token-Anzeige,
	- Endpoint-seitige QR-Code-Anzeige beim Boot (Zielarbeit für Ende Q2).

0. **A/B-Update-System-Vorbereitung (Plan 19 Schritt 3)**:
	- Boot-Loader-Slot-Switch-Logik in `thin-client-assistant/boot/` definieren,
	- Update-Service `thin-client-assistant/runtime/update_service.py` erweitern,
	- GPG-Signatur-Verifikation für Update-Images.

0. **Endpoint-Kiosk auf neueste Electron prüfen**:
	- `beagle-kiosk/` nutzt bereits Electron 37.2.0 (aktuell),
	- Beagle-Enrollment-Flow in Gaming-Kiosk später als separater Schritt.

## Delta (2026-04-21 nach Plan 05: Provider-Abstraction vollständig)

0. **Provider-Abstraction vollständig abgeschlossen**:
	- Plan 05 alle Schritte [x]: Contract-Interface, Grep auf 0 Treffer, Beagle-Provider Vollausstatsung, Provider-Registry Vereinfachung, Tests, Dokumentation.
	- Keine direkten Proxmox-API-Aufrufe (`qm`, `pvesh`, `/api2/json`) mehr im beagle-host-Code.
	- Dead-Code-Pfade (`VmConsoleAccessService` Proxmox-UI-Port-Handling, `RequestSupportService` Proxmox-CORS) entfernt.
	- Smoke-Tests auf `srv1.beagle-os.com` alle 13/13 bestanden nach Deploy der bereinigten Services.

0. **Nächste Priorität: Plan 07 (Cluster Foundation) vorbereiten**:
	- Plan 07 beginnt mit Libvirt-Network-Definitions und libvirt-Storage-Pool-API-Abstraktionen in `providers/beagle/`.
	- Das ist Q3 2026 geplant, aber Vorbereitung könnte jetzt beginnen.

0. **Kontinuierliche Aufräumarbeiten (Plan 19 / Plan 20)**:
	- Plan 19 (Endpoint OS): Drei Profiles-Struktur aufbauen (desktop-thin-client, gaming-kiosk, engineering-station) — später Priorität.
	- Plan 20 (Security): Alle Steps [x]; regelmäßige Security-Audits und Dependency-Updates fortsetzen.

## Delta (2026-04-21 nach Plan-20 Security-Gates-Welle)

0. **Security-Gates operationalisieren**:
	- `scripts/security-secrets-check.sh` als verpflichtenden lokalen Pre-commit Hook dokumentieren,
	- false positives regelmäßig gegen `.security-secrets-allowlist` reviewen (kein pauschales Whitelisting).

0. **OWASP-Baseline erweitern**:
	- `scripts/security-owasp-smoke.sh` um authentifizierte Negativ-/RBAC-Fälle ergänzen,
	- Ergebnisse in periodischen Security-Runs in `docs/refactor/11-security-findings.md` mit Zeitstempel protokollieren.

## Delta (2026-04-21 nach vollstaendiger Plan-06-Testpflicht)

0. **Plan 06 ist inhaltlich abgeschlossen; Fokus auf Release-Host-Operationalisierung**:
	- Signatur-Uploadpfad auf dem produktiven Release-Host laufen lassen,
	- verifizierte `.sig` Assets im naechsten GitHub-Release zwingend mitpublizieren.

## Delta (2026-04-21 nach Plan 06 Testpflicht-Teilabschluss)

0. **Offene Plan-06-Testpflicht schließen**:
	- QEMU-Boottest der aktuellen server-installer ISO bis sichtbarer Installer-Dialog reproduzierbar dokumentieren.

0. **Signierpfad auf Release-Host bestätigen**:
	- `scripts/create-github-release.sh` mit Produktions-GPG-Key laufen lassen,
	- prüfen, dass `.sig` Assets in GitHub Release hochgeladen und extern verifizierbar sind.

## Delta (2026-04-21 nach GoFuture Plan 06 Schritt 4-5)

0. **Plan 06 Testpflicht finalisieren**:
	- server-installer ISO im QEMU-Bootpfad bis Installer-Dialog und bis abgeschlossener Installation validieren,
	- Post-Install-Check `systemctl is-active beagle-control-plane` auf frischer Zielinstallation dokumentieren.

0. **Release signing runtime verifizieren**:
	- `scripts/create-github-release.sh` auf einem Signier-Host mit echtem GPG-Key ausführen,
	- erzeugte `SHA256SUMS.sig` und ISO-`*.sig` gegen den veröffentlichten Public-Key verifizieren.

## Delta (2026-04-21 nach GoFuture Plan 06 Schritt 1-3)

0. **Plan 06 Schritt 4 umsetzen (Installer/Post-Install vereinheitlichen)**:
	- Dopplungen zwischen `server-installer` Post-Install-Pfad und `scripts/install-beagle-host.sh` identifizieren,
	- gemeinsame idempotente Bootstrap-Funktionen extrahieren.

0. **Plan 06 Schritt 5 umsetzen (Release signing chain)**:
	- GPG-Signierung für Server-Installer-ISO in `scripts/create-github-release.sh` integrieren,
	- SHA256 + `.sig` als Pflicht-Release-Assets veröffentlichen.

0. **Plan 06 Testpflicht abschließen**:
	- frische QEMU-Install aus aktueller ISO bis `beagle-control-plane active` durchfahren,
	- Signatur-/Checksum-Verifikation in den Run integrieren und dokumentieren.

## Delta (2026-04-21 nach Auth/IAM-Surface-Extraktion)

0. **Plan 04 Schritt 2 Restextraktion fortsetzen**:
	- verbleibende groessere Bloecke in `do_POST` fuer Login/Refresh/Logout/Onboarding analog in eigenes Surface-Service-Modul verschieben,
	- Ziel bleibt: HTTP-Handler nur Guard + Delegation + Response.

0. **Plan 04 Schritt 2 Regressionstest erweitern**:
	- authenticated API-Smokes fuer Auth/IAM-Mutationspfade ergaenzen (create/update/delete/revoke mit Admin-Token),
	- als reproduzierbares Script unter `scripts/` dokumentieren.

0. **Plan 04/05 Testpflicht weiterziehen**:
	- neuen Auth-Surface-Pfad in bestehende Unit-/CI-Runs aufnehmen,
	- danach naechste offene Service-Extraktionswelle fuer nicht-auth Mutationspfade starten.

## GoFuture Plan 04/05 Provider-Abstraction execution (2026-04-21)

0. **Plan 04 Schritt 2 bleibt groesster Backend-Restblock**:
	- Route-Handler weiter in Services extrahieren bis Handler 5-10 Zeilen Delegierer sind.

0. **Plan 04 Schritt 5 Restpunkt abschliessen**:
	- Vollstaendige Audit-Abdeckung fuer alle mutierenden Operationspfade pruefen und verbleibende Luecken im `audit_log.py`-Pfad schliessen.

0. **Plan 04 Testpflicht ausbauen (zusatzlich zu bestehendem unauth-Smoketest)**:
	- `scripts/smoke-control-plane-api.sh` um authentifizierte Mutation-Checks erweitern (z.B. `/api/v1/auth/users`, `/api/v1/settings/*` mit Admin-Token),
	- Ergebnisse als separaten Run im Progress-Log dokumentieren.

0. **Plan 04 Schritt 6 (Fehlerformat) als naechster harter Backend-Block**:
	- Error-Response-Schema ist umgesetzt; als Nachlauf nur noch Surface-spezifische Sonderfaelle pruefen,
	- Regressionstest fuer `internal_error`-Boundary als Unit-/Integrationstest aufnehmen.

0. **Plan 20 Security Follow-up** aus offenen Findings:
	- Plan 20 Schritt 4 (Secrets-Management): `.gitignore` + gitleaks-Hook prüfen und nachziehen.
	- OWASP Top 10 Checkliste für alle API-Endpoints (Plan 20 items 129/130).
	- plan 06-server-installer.md: Installer auf Standalone fokussieren (nächste SOFORT-Aufgabe).

0. **Plan 04 Schritt 3 ist umgesetzt, jetzt Schritt 2 und 4 fortsetzen**:
	- Route-Handler weiter aus `beagle-control-plane.py` in `beagle-host/services/` extrahieren,
	- serverseitige Payload-Whitelist-Validierung fuer Mutationsendpunkte nachziehen,
	- verbleibende Error-Schema-Vereinheitlichung (`error` + `code`) umsetzen.

0. **Plan 05 Schritt 2: Proxmox-Direktaufrufe final prüfen und migrieren**:
   - grep -r "qm\|pvesh\|/api2/json\|PVEAuthCookie" komplettes Workspace durchlaufen (nicht nur beagle-host/),
   - Check auf `providers/` direkte Aufrufe und versteckte Proxmox-Kopplungen,
   - Verifizieren dass alle Proxmox-Aufrufe nur in `beagle-host/providers/proxmox_host_provider.py` existieren.

0. **Plan 05 Schritt 3: Beagle-Provider (libvirt/KVM) auf Vollständigkeit prüfen**:
   - Sicherstellen dass alle Contract-Methoden aus `host_provider_contract.py` implementiert sind,
   - Stub-Implementierungen mit aussagekräftigen `NotImplementedError` ersetzen,
   - libvirt-Konnektivität und Domain-Management auf minimal viable implementiert.

0. **Plan 04 Schritt 2: Route-Handler von Business-Logik trennen**:
   - `beagle-host/bin/beagle-control-plane.py` durchgehen und jeden >20-Zeiler Handler in Service extrahieren,
   - Service-Modul unter `beagle-host/services/` als neuer Handler-Delegator einrichten,
   - Provider-Registry-Nutzung vereinfachen (Default ist jetzt "beagle", kann Option durchgängig werden).

0. **Plan 05 Schritt 5a: Provider-neutrale Unit-Tests für alle Services schreiben**:
   - Mock-Provider implementieren der `HostProvider`-Contract erfüllt,
   - `tests/unit/` Verzeichnis erweitern mit Service-Tests,
   - kein echter libvirt oder Proxmox-Zugriff in Unit-Tests notwendig.

0. **Plan 05 Schritt 5b: Proxmox-Verzeichnisse nach vollständiger Beagle-Migration löschen**:
   - ERST nach erfolgreicher Beagle-Migration + Tests,
   - `rm -rf providers/proxmox/ proxmox-ui/` mit finalen Verifikation,
   - Alle Referenzen in Scripts, CI-Config entfernen,
   - Dokumentation mit Löschdatum aktualisieren.

## Immediate TLS/onboarding follow-up (2026-04-21)

0. **Rebuild and republish host installer artifacts with the latest onboarding + TLS fixes**:
	- rebuild the Hetzner installimage tarball and any server-installer artifacts so fresh installs ship both the corrected onboarding behavior and automatic `certbot`/`python3-certbot-nginx` installation,
	- republish the updated artifact set before the next dedicated-host reinstall.

0. **Add one end-to-end regression check for the Security/TLS API path**:
	- cover the `request_letsencrypt()` execution wrapper path and/or an integration-level smoke against a disposable nginx/certbot environment,
	- ensure a future sandbox or packaging regression cannot silently break the WebUI Security panel again.

0. **Re-validate the fresh-install WebUI flow on `srv1.beagle-os.com`**:
	- open the WebUI after a clean session,
	- confirm the onboarding modal appears instead of the login-only flow,
	- complete onboarding once and verify the bootstrap marker is cleared afterwards.

## GoFuture execution now in progress (2026-04-20)

0. **Plan 02/03 Restvalidierung abschliessen**:
   - authentifizierte Panels auf Light/Dark visuell gegenpruefen,
   - Login-Flow und Kernpanels unter dem neuen HTML/CSS/JS-Einstieg voll durchtesten,
	- dafuer bestehende Operator-Credentials fuer `srv1.beagle-os.com` verwenden oder bewusst einen temporaeren Admin-Reset freigeben.

0. **Modulpfad auf `srv1.beagle-os.com` weiter validieren**:
   - Login mit echten Credentials testen,
   - Dashboard-Datenpfade, Inventory, Provisioning, IAM und noVNC-Aktionen unter dem neuen Modul-Bootstrap durchklicken,
   - verbleibende Browserfehler oder Import-Kopplungen direkt patchen.

## WebUI 7.0 (website/) — next steps after navigation restructure

0. **Deploy updated `website/` to `srv1.beagle-os.com`** once bootstrap finishes:
   - Verify scope switcher, new nav sections and Sessions panel render correctly.
   - Check that all existing panels load without JS errors.

0. **Wire scope switcher to API** (`/api/v1/status` → node count → update `#scope-badge`).

0. **Pools & Policies panel** – rename panel eyebrow/title already done; next: split the inline policy editor into a pools-oriented layout (pool directory table + per-pool assignment form).

0. **Sessions panel real data** – requires 7.0 API endpoint `/api/v2/sessions`; document contract in `docs/refactorv2/14-platform-api-extensibility.md`.

## Immediate (Dedicated host `46.4.96.80`, 2026-04-20)

0. **Finalize bootstrap on new dedicated host**:
	- wait for `beagle-installimage-bootstrap.service` to reach `active (exited)`,
	- verify `beagle-control-plane`, `beagle-novnc-proxy`, `nginx` are active,
	- verify listeners on `127.0.0.1:9088`, `:443`, `:8443`.

0. **Validate KVM capability on bare metal and provisioning path**:
	- assert `/dev/kvm` exists,
	- assert `virsh domcapabilities --virttype kvm` succeeds,
	- create one fresh ubuntu-beagle VM via API/UI and confirm no `virt type 'kvm'` error.

0. **Close release artifact consistency gap that caused bootstrap 404**:
	- ensure `beagle-os.com/beagle-updates/` always contains the full required `v${VERSION}` + `latest` thin-client installer/payload/bootstrap set,
	- add this as a mandatory preflight in release publication flow before installimage deployment.

0. **Capture final handoff state after bootstrap completes**:
	- update `05-progress.md` with completed status and service health,
	- update `08-todo-global.md` by marking dedicated reinstall + bootstrap validation done,
	- append any runtime/security residue to `11-security-findings.md` if discovered.

## Immediate (Hetzner installimage boot fix, 2026-04-20)

0. **Recover `srv1.beagle-os.com` (178.104.179.245)** - BLOCKER:
   - rescue ssh window expired by failed v1 install reboot,
   - operator must re-activate Hetzner Rescue in the Hetzner panel for `srv1.beagle-os.com` and trigger hardware reboot (cannot be done from SSH),
   - then provide fresh root rescue password so the v2 tarball can be uploaded + installimage re-run.

0. **Bump VERSION to 6.7.1 + publish corrected tarball**:
   - tarball `dist/beagle-os-server-installimage/Debian-1201-bookworm-amd64-beagle-server.tar.gz` (sha256 `11ee375adcfbafaa8982ed8ef0d0c9d0a37c9348428506d93109983dcf232095`, 738M, built 2026-04-20 20:02 UTC) is the validated artifact,
   - run `scripts/publish-public-update-artifacts.sh` once VERSION is bumped so `https://beagle-os.com/beagle-updates/` serves the fixed image,
   - update `beagle-downloads-status.json` + `SHA256SUMS`.

0. **Add CI/smoke gate for installimage tarball**:
   - assert tarball contains: non-empty `/etc/default/grub`, non-empty `/etc/kernel-img.conf`, `/usr/sbin/grub-install`, `/usr/sbin/update-grub`, `/boot/grub/grub.cfg` with at least one `menuentry`, plus `/boot/vmlinuz-*` and matching `/boot/initrd.img-*`,
   - so this regression class cannot ship again.

## Immediate (refactorv2 follow-up, 2026-04-20)

0. **Resolve open architecture decisions in [docs/refactorv2/15-risks-open-questions.md](../refactorv2/15-risks-open-questions.md)** and capture each in `docs/refactor/07-decisions.md`:
   - cluster store (etcd vs. Litestream vs. Corosync),
   - default storage backend for 7.0.1 (ZFS / NFS / both),
   - streaming backend in 7.1.1 (Apollo only vs. Apollo + Sunshine selectable),
   - Linux virtual display (vkms / xvfb / xrandr-virtual),
   - backup format (PBS / Restic / native),
   - SDN scope (nftables only vs. nftables + OVS),
   - CLI language (Python vs. Go).

0. **Spike-Phase Welle 7.0.0 Cluster Foundation**:
   - PoC mit etcd, Cluster-CA, `beaglectl cluster init/join`,
   - Inter-Host RPC ueber mTLS,
   - keine Aenderung an v1-API.

0. **Spike-Phase Welle 7.1.1 Streaming v2**:
   - Apollo-Build-Layer und systemd-Template,
   - Linux Virtual Display PoC (vkms-basiert) auf Test-VM,
   - Auto-Pairing-Token-Flow Ende-zu-Ende.

## Immediate (2026-04-20 follow-up)

0. **Complete full in-VM beagleserver installation after ISO boot recreate**:
	- VM `beagleserver` has been recreated and is running from rebuilt server-installer ISO,
	- complete installer flow inside VM (disk wipe + host config) and verify post-install disk boot.

0. **Stabilize local server-installer harness against KVM availability variance**:
	- local run encountered `failed to initialize kvm: Permission denied`,
	- define a deterministic fallback strategy (`--virt-type qemu` or explicit preflight) in smoke/reinstall workflow to avoid false negatives.

0. **Re-validate installer endpoint behavior on fresh host install**:
	- after full install from the rebuilt ISO, verify `installer.sh` / `live-usb.sh` return `200` without manual file copies,
	- this confirms the `install-beagle-host.sh` reproducibility fix is effective end-to-end.

## Immediate (release publication follow-up)

0. **Push `6.6.9` repo changes to GitHub and attach release assets**:
	- local/public artifact publication to `beagle-os.com` is complete and verified,
	- running Hetzner host `beagle-server` is updated to `6.6.9`,
	- remaining blocker is GitHub-side release publication from this workspace because local `gh`/git credentials are not available,
	- next authenticated GitHub step must push the code changes and upload the already-built `6.6.9` release assets.

0. **Keep `6.6.9` artifact verification attached to handoff**:
	- public installimage SHA256: `3d0a0623585265e9d690f9bcf7d9a1c7baa0aa0f85cbfa0544ef967f2fb7c34d`,
	- public source tarball SHA256 is recorded in `SHA256SUMS` because the source tarball is regenerated when handoff docs change,
	- target host `/opt/beagle/dist/beagle-downloads-status.json` reports `version: 6.6.9`.

## Immediate (docs/process consistency)

0. **Keep the shortened local operator policy stable**:
	- Treat `AGENTS.md` as compact policy only.
	- Move future roadmap/detail architecture edits into `docs/refactor/*`, not back into `AGENTS.md`.
	- If a new rule is truly permanent, add it concisely; if it is status, planning, or migration detail, document it elsewhere.

## Immediate (security/process hygiene)

0. **Commit and push the operator-file de-tracking/release-scrub changes before the next shared sync**:
	- Keep `AGENTS.md` and `AGENTS.md` local-only and out of Git tracking.
	- Verify the next commit removes both files from the shared repo state on GitHub.
	- Confirm future local edits stay ignored by Git and excluded from source/release/installimage bundles.

0. **Run a targeted secret-leak sweep now that local operator docs are isolated**:
	- Search the repo for plaintext passwords, tokens, SSH snippets and operator-only notes that should not be versioned.
	- Document every finding in `docs/refactor/11-security-findings.md`.
	- Patch or remove any safe-to-fix exposures in the same run.

## Immediate (blocking on environmental readiness, not code)

0. **Deploy and validate the firstboot callback retry guard fix (VM163 blocker)**:
	- Deploy updated [beagle-host/templates/ubuntu-beagle/user-data.tpl](beagle-host/templates/ubuntu-beagle/user-data.tpl) to `/opt/beagle/...` on beagleserver.
	- Recreate one fresh ubuntu desktop VM and verify the firstboot systemd unit remains eligible until `/var/lib/beagle/ubuntu-firstboot-callback.done` exists.
	- Simulate callback delay/failure once and confirm service retries and eventually posts `/complete?restart=0`.
	- Confirm provisioning transitions out of `installing` and VM performs the expected post-completion reboot handoff.

0. **Unstick currently affected VM163 runtime state**:
	- Trigger callback endpoint `POST /api/v1/public/ubuntu-install/<token>/complete?restart=0` using VM163 token.
	- Verify VM163 provisioning state becomes `completed/complete` and rerun stream-ready checks.

0. **Finish live validation for the freshly recreated VM161**:
	- Monitor VM `161` until provisioning transitions from `installing/autoinstall` to `firstboot`/`complete`.
	- Continue periodic installer screenshot checks to ensure progression beyond `stage-curthooks/.../installing-kernel` and detect any new deterministic stall point.
	- Confirm VM XML cleanup after autoinstall transition (installer media + kernel args removed, disk boot only).
	- Verify inside guest that `beagle-ubuntu-firstboot.service` exists and executes automatically on first boot.
	- Verify `lightdm`, desktop session and `qemu-guest-agent` become active.

0. **Validate fresh-install reproducibility of the XFCE/noVNC fix**:
	- Boot a host from the freshly rebuilt server installer ISO and complete a clean Beagle host install.
	- Recreate a fresh ubuntu desktop VM from the provisioning API and verify firstboot no longer stalls at tty-only state.
	- Confirm `beagle-x11vnc.service` is present in the guest, reaches `active`, and listens on guest port `5901` without any manual edits.
	- Confirm noVNC resolves to guest `x11vnc` when available and shows the real XFCE desktop instead of the VGA tty framebuffer.
	- Confirm Sunshine service and API port are reachable after completion.

0. **Deploy full 6.6.9 runtime code on host before final VM lifecycle acceptance**:
	- `beagle-server` already runs `/opt/beagle/VERSION=6.6.9`.
	- Re-run the same VM lifecycle checks after the full `6.6.9` code deploy to avoid validating against mixed runtime state.

0. **Validate new bridge/interface consistency fix on fresh VM run**:
	- Ensure runtime env on host contains `BEAGLE_PUBLIC_STREAM_LAN_IF` matching libvirt `beagle` network bridge (expected `virbr10`).
	- Trigger `/opt/beagle/scripts/reconcile-public-streams.sh` and confirm generated `beagle-stream-allow` rules use detected bridge iface, not legacy `vmbr1`.
	- Create one fresh ubuntu desktop VM and verify firstboot + callback complete without any manual host nft forward patching.

1. **Guest IP and qemu-agent availability** (in progress on beagleserver):
	- VMs 100, 101, 102 are running but have not yet obtained DHCP IP addresses.
	- Root cause: VMs are either still in autoinstall phase (VM102) or waiting for qemu-guest-agent to initialize (VMs 100, 101).
	- **Next agent should**: Wait ~10 min, then retry `virsh guestinfo beagle-{100,101,102} --types network` to get IP addresses.
	- Once IPs are available, re-run `ensure-vm-stream-ready.sh --vmid 102 --node beagle-0` to validate full stream-ready workflow (secret persistence + Sunshine install + ready state).
	- Expected outcome: `installer_guest_ip` populated, `sunshine_status: {binary: 1, service: 1, process: 1}`, state phase transitions to "ready".

## High priority (secret persistence validated, now prove E2E)

1. Execute a full no-manual reproducibility run for stream prep on fresh VMs (once IPs available):
	- run installer-prep/stream-ready flow without console or ad-hoc SSH intervention,
	- confirm state payload includes `installer_guest_ip` and `installer_guest_password_available=true`,
	- confirm the guest password is sourced from persisted `vm-secrets` on new VMs and only uses the `ubuntu-beagle-install` fallback for legacy runs,
	- confirm Sunshine install reaches `ready` only through repo-managed scripts.
2. Confirm guest runtime readiness after fallback completion:
	- verify Sunshine port/API path reaches a stable state,
	- verify qemu-guest-agent comes up (`org.qemu.guest_agent.0` no longer disconnected),
	- verify no hidden firstboot service crash loop remains.
3. Keep callback path as primary signal for fresh runs and re-test on a clean recreate:
	- ensure generated seed contains both late-command callback attempts (`sh -c ...` and `curtin in-target ...`),
	- confirm callbacks (`prepare-firstboot`, `complete` or `failed`) appear in host ingress logs when guest networking behaves.
4. Fix immediate post-install disk boot on `beagleserver` after successful installer completion:
	- verify effective libvirt boot-order/device mapping for `vda` vs empty `sda` cdrom,
	- confirm GRUB/boot target on installed disk,
	- reach first boot login on installed host without live-ISO runtime artifacts.
5. Re-run clean reinstall once with the now-proven patched ISO path and confirm no residual transient state in `/var/log/beagle-server-installer.log`.
6. Continue the requested realistic E2E product flow from installed host state:
	- open Beagle Web UI,
	- create Beagle Ubuntu/XFCE/Sunshine desktop VM (re-validate UI no longer reports `Request timeout` on provisioning create),
	- download Live-USB installer script via Web UI,
	- reinstall `beaglethinclient`,
	- verify first-time Moonlight -> Sunshine auto-connect and active stream.
7. Persist and verify stream firewall reconciliation on installed beagleserver host:
	- run `/opt/beagle/scripts/reconcile-public-streams.sh` on boot/service restart,
	- confirm `inet filter forward` contains `beagle-stream-allow` rules for RTSP + UDP stream ports.
8. Verify the guest `beagle-sunshine-healthcheck.timer` path on VM 101:
	- timer active after reboot,
	- forced crash (`pkill sunshine`) is recovered automatically,
	- local `/api/apps` check succeeds again without manual intervention.
9. Fix server-installer live smoke DHCP reliability in local libvirt harness (`scripts/test-server-installer-live-smoke.sh`) after the boot-path stabilization.
10. Stabilize standalone stream simulation harness for real-libvirt execution (`scripts/test-standalone-desktop-stream-sim.sh`).
11. Once end-to-end passes, run final docs sync + commit/push:
	- `05-progress.md`,
	- `06-next-steps.md`,
	- `08-todo-global.md`,
	- `09-provider-abstraction.md`.
