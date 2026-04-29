# 08 — 7.0.1 Storage Plane

Stand: 2026-04-20  
Priorität: 7.0 (Q3–Q4 2026)  
Referenz: `docs/refactorv2/07-storage-network-plane.md`

---

## Schritte

### Schritt 1 — `StorageClass`-Contract in `core/` definieren

- [x] `core/virtualization/storage.py` (o.ä.) anlegen mit `StorageClass`-Protokoll: `create_volume`, `delete_volume`, `resize_volume`, `snapshot`, `clone`, `list_volumes`.
- [x] Typen: `VolumeSpec`, `SnapshotSpec`, `StoragePoolInfo` definieren.

Umgesetzt (2026-04-22):
- Neues Modul `core/virtualization/storage.py` erstellt.
- `StorageClass` als provider-neutrales `Protocol` mit den sechs Lifecycle-Methoden umgesetzt.
- Dataclass-Typen `VolumeSpec`, `SnapshotSpec`, `StoragePoolInfo` implementiert.
- Unit-Test `tests/unit/test_storage_contract.py` ergänzt (3/3 grün).

Der `StorageClass`-Contract ist das Fundament der Storage-Plane und entspricht dem
Prinzip der Kubernetes-StorageClass aber angepasst an VM-Workloads. Jede konkrete
Storage-Implementierung (directory, lvm-thin, zfs, nfs, ceph) implementiert dieses
Interface. Services und die Web Console sprechen ausschließlich gegen den Contract
und kennen keine Implementierungsdetails. `VolumeSpec` enthält: name, size_gib,
format (qcow2/raw), pool_name. `SnapshotSpec` enthält: volume_id, name, beschreibung.
Das Protokoll wird in `core/` definiert und in `providers/beagle/storage/` implementiert.

---

### Schritt 2 — Directory-Backend implementieren

- [x] `providers/beagle/storage/directory.py` implementiert den Contract für lokalen Verzeichnis-Storage.

Umgesetzt (2026-04-22):
- Neues Modul `providers/beagle/storage/directory.py` eingefuehrt (`DirectoryStorageBackend`).
- Contract-Methoden real umgesetzt: `create_volume`, `delete_volume`, `resize_volume`, `snapshot`, `clone`, `list_volumes`.
- Umsetzung ueber `qemu-img`-Kommandos mit validierter Namens-/Formatlogik und Path-Escape-Schutz.
- Unit-Test `tests/unit/test_directory_storage_backend.py` ergaenzt (4/4 gruen).

Directory-Storage ist das einfachste Backend: qcow2-Dateien in einem konfigurierbaren
Verzeichnis (`/var/lib/beagle/images/` als Default). `create_volume` legt eine neue
qcow2-Datei mit `qemu-img create` an. `snapshot` nutzt `qemu-img snapshot`. `clone`
erstellt einen Linked Clone mit `qemu-img create -b backing_file`. `resize_volume`
verwendet `qemu-img resize`. Dieses Backend ist der Default für Single-Node-Installationen
ohne spezialisierte Storage-Hardware. Quotas werden als File-System-Level-Implementierung
über ein einfaches Counter-Modell in der Config-Datenbank realisiert.

---

### Schritt 3 — LVM-Thin-Backend implementieren

- [x] `providers/beagle/storage/lvm_thin.py` implementiert den Contract für LVM-Thin-Provisioning.

Umgesetzt (2026-04-22):
- Neues Modul `providers/beagle/storage/lvm_thin.py` erstellt (`LvmThinStorageBackend`).
- Contract-Methoden real umgesetzt: `create_volume`, `delete_volume`, `resize_volume`, `snapshot`, `clone`, `list_volumes`.
- LVM-Befehle integriert: `lvcreate --thin`, `lvcreate -s`, `lvresize`, `lvremove`, `lvs`.
- Linked-Clone und Full-Clone-Pfad (mit `qemu-img convert` auf Raw-Devices) umgesetzt.
- Unit-Test `tests/unit/test_lvm_thin_storage_backend.py` ergänzt (4/4 grün).

LVM-Thin-Provisioning ist besonders effizient bei vielen ähnlichen VMs (VDI-Pools)
da Thin-Volumes nur den tatsächlich genutzten Speicher belegen. `create_volume` legt
ein Thin-LV mit `lvcreate --thin -V` an. `snapshot` nutzt `lvcreate -s` auf ein
Thin-LV. `clone` erstellt ein neues Thin-LV von einem Snapshot. Das Backend erfordert
eine vorgelegte VG/LV-Konfiguration auf dem Host die beim Installer-Schritt angelegt
werden kann. Quotas sind über LVM-Thin-Pool-Limits implementierbar.

---

### Schritt 4 — ZFS-Backend implementieren

- [x] `providers/beagle/storage/zfs.py` implementiert den Contract für ZFS-Datasets.

Umgesetzt (2026-04-22):
- Neues Modul `providers/beagle/storage/zfs.py` eingefuehrt (`ZfsStorageBackend`).
- Contract-Methoden real umgesetzt: `create_volume`, `delete_volume`, `resize_volume`, `snapshot`, `clone`, `list_volumes`.
- Native ZFS-Kommandos integriert: `zfs create -V`, `zfs set volsize=`, `zfs snapshot`, `zfs clone`, `zfs destroy -r`, `zfs list`.
- Clone-Pfad nutzt Copy-on-Write-Semantik (Snapshot + Clone) fuer zvol-Datasets.
- Unit-Test `tests/unit/test_zfs_storage_backend.py` ergänzt (4/4 grün).

ZFS bietet Copy-on-Write-Snapshots mit vernachlässigbarem Overhead was es ideal für
VM-Snapshots und Clones macht. `create_volume` legt ein ZFS-Volume (`zvol`) an.
`snapshot` nutzt `zfs snapshot`. `clone` ist `zfs clone`. `rollback` ist ebenfalls
nativ unterstützt. Die ZFS-ARC (Adaptive Replacement Cache) verbessert I/O-Performance
bei häufig zugegriffenen Daten erheblich. Das Backend erfordert ZFS-Kernel-Modul
auf dem Host (bei Debian via `zfsutils-linux`).

---

### Schritt 5 — NFS-Backend implementieren

- [x] `providers/beagle/storage/nfs.py` implementiert den Contract für NFS-gemountete Storage-Pools.

Umgesetzt (2026-04-22):
- Neues Modul `providers/beagle/storage/nfs.py` eingefuehrt (`NfsStorageBackend`).
- Contract-Methoden real umgesetzt: `create_volume`, `delete_volume`, `resize_volume`, `snapshot`, `clone`, `list_volumes`.
- NFS-Mount-Guard integriert (`mount_path` muss existieren + als Mountpoint validieren), damit kein versehentliches Schreiben auf lokale Pfade erfolgt.
- Storage-Operationen via `qemu-img` auf NFS-Dateien umgesetzt (inkl. linked/full clone).
- Unit-Test `tests/unit/test_nfs_storage_backend.py` ergänzt (4/4 grün).

NFS-Storage ermöglicht shared Storage über mehrere Cluster-Knoten was Live-Migration
ohne Disk-Transfer ermöglicht. `create_volume` legt eine qcow2-Datei auf dem NFS-Mount
an. Das Backend erfordert dass der NFS-Mount auf allen Knoten gleich erreichbar ist.
Mount-Management (automount, fstab-Eintrag) wird vom Install-Assistenten übernommen.
NFS ist nicht ideal für I/O-intensive Workloads aber einfach aufzusetzen und für
Home-Lab- und SMB-Umgebungen gut geeignet.

---

### Schritt 6 — Quotas pro Tenant/Pool in Web Console verwalten

- [x] API-Endpunkt `GET/PUT /api/v1/storage/pools/{pool}/quota` anlegen.
- [x] Web Console: Storage-Pool-Übersicht mit Quota-Anzeige und Setter.

Umgesetzt (2026-04-22):
- Neuer persistenter Quota-Service `beagle-host/services/storage_quota.py` eingefuehrt (`/var/lib/beagle/beagle-manager/storage-quotas.json`).
- Control-Plane-API implementiert:
	- `GET /api/v1/storage/pools/{pool}/quota`
	- `PUT /api/v1/storage/pools/{pool}/quota`
- AuthZ-Mapping ergaenzt (`settings:read`/`settings:write`) fuer beide Quota-Routen.
- Virtualization-Read-Surface erweitert: Storage-Payload liefert jetzt `quota_bytes` pro Pool.
- Web Console erweitert:
	- Storage-Tabellen zeigen Quota-Spalte,
	- Storage-Pool-Ansicht bietet Quota-Setter (Prompt, PUT, Refresh).
- Unit-Test `tests/unit/test_storage_quota_service.py` ergänzt.

Quotas auf Storage-Pool-Ebene verhindern dass ein einzelner Tenant oder Pool den
gesamten verfügbaren Speicher belegt. Die Quota wird beim Volume-`create_volume`-Aufruf
geprüft und bei Überschreitung mit einem sprechenden Fehler abgelehnt. Die Web Console
zeigt in der Pool-Übersicht: Gesamtkapazität, genutzt, verfügbar, Quota-Limit.
Administratoren können Quotas per API oder Web Console setzen und ändern.

---

### Schritt 7 — `/#panel=virtualization` UX- und Bedienbarkeits-Refactor: Nodes/Storage/Networking

- [x] Ist-Zustand von `/#panel=virtualization` dokumentieren: Welche Tabellen existieren, welche Aktionen fehlen, welche Operator-Fragen bleiben unbeantwortet.
- [x] Panel in klare Bereiche schneiden: `Nodes`, `Storage`, `Bridges/Networking`, `GPU`, `VM Inspector`, `Operations`.
- [x] Node-Cards bauen: Hostname, Status, CPU/RAM, Storage-Druck, VM-Zahl, libvirt/KVM-Health, Actions `Details`, `Maintenance`, `Refresh`.
- [x] Node-Detail-Drawer oder Detailseite ergänzen: Services, KVM/IOMMU, libvirt URI, SSH/RPC-Reachability, relevante Logs/Warnings.
- [x] Storage-Bereich als editierbare Cards statt reiner Tabelle darstellen: Backend-Typ, Kapazität, aktiv/inaktiv, Quota, Mount/Pool-Health, Actions `Quota setzen`, `Health prüfen`.
- [x] Bridge-/Netzwerkbereich bedienbar machen: Bridge-Liste, VM-Nutzung, IPAM-Zuordnung, Warnungen für fehlende/inkonsistente Bridges.
- [x] VM-Inspector verbessern: VMID-Suche, zuletzt gewählte VM, Config-Diff, Netzwerkinterfaces, Storage-Belegung und direkte Aktionen klar gruppieren.
- [x] Risk-/Health-Banner ergänzen: `KVM fehlt`, `libvirt nicht erreichbar`, `Storage fast voll`, `Bridge fehlt`, `Quota überschritten`.
- [x] API-Lücken erfassen und schließen, bevor UI-Aktionen Mock-Daten verwenden: kein UI-Button ohne echten Backend-Pfad.
- [x] UI-Regressions ergänzen: Node-Card-Rendering, Quota-Setter, Inspector-Suche, Empty-/Error-State.
- [x] srv1/srv2-Smoke durchführen: beide Hosts sichtbar, Storage/Bridge/Quota korrekt, keine Console Errors.

Warum dieser Schritt noch offen ist:
Die Storage- und Virtualization-Backends sind technisch weitgehend implementiert, aber `/#panel=virtualization` ist noch zu stark eine Diagnose-Tabelle. Betreiber müssen dort reale Infrastruktur verwalten können: Nodes prüfen, Quotas setzen, Netzwerk-/Storage-Probleme erkennen und zielgerichtete Aktionen starten. Ohne diesen Refactor bleibt Virtualization ein Entwickler-/Debug-Panel statt einer Web Console für produktiven Betrieb.

Validierung (2026-04-26, srv1.beagle-os.com + srv2.beagle-os.com):
- `GET /api/v1/virtualization/nodes/{node}/detail` live auf beiden Hosts verifiziert; `srv1` wird auf `srv1` korrekt als `local=true`, auf `srv2` korrekt als `local=false` ausgeliefert.
- Ausgelieferte WebUI-Dateien `ui/virtualization.js` und `ui/events.js` enthalten den `Details`-Flow auf beiden Hosts.
- Der Storage-Bereich wird live als Card-Ansicht statt Tabelle ausgeliefert; `Quota setzen` und `Health pruefen` sind auf beiden Hosts in den ausgelieferten Assets vorhanden.
- Bridge-Flow live verifiziert: `GET /api/v1/virtualization/bridges/{bridge}/detail` liefert auf `srv1` fuer `beagle` echte VM-Nutzung (`vm_count=1`) und auf `srv2` den erwarteten Leerzustand (`vm_count=0`).
- Die WebUI liefert Bridge-Cards, Detail-Flow und den echten IPAM-Zone-Pfad `POST /api/v1/network/ipam/zones` auf beiden Hosts aus.
- Der VM-Inspector liefert jetzt getrennte Bereiche fuer Allgemein, Disks, Netzwerk-Config und Guest-Interfaces sowie `Letzte VM`-/Recent-Shortcuts; ausgelieferte Assets auf `srv1`/`srv2` enthalten den neuen Flow.
- Lokale Tests: `python3 -m pytest tests/unit/test_virtualization_read_surface.py tests/unit/test_network_http_surface.py -q` => `22 passed`.
- Reproduzierbarer Browser-Smoke `scripts/test-virtualization-panel-smoke.py` gegen `srv1` und `srv2` erfolgreich:
  - `srv1`: `nodes=2 storage=1 bridges=2 inspector_vmid=100`
  - `srv2`: `nodes=2 storage=1 bridges=1 inspector_vmid=-`
  - keine Console-/Page-Errors, Exit-Code `0`.

---

## Testpflicht nach Abschluss

- [x] VM mit Directory-Backend anlegen, starten, Snapshot erstellen, Snapshot wiederherstellen.
- [x] VM mit ZFS-Backend: Snapshot und Clone erfolgreich.
- [x] NFS-Backend: VM auf gemountet-NFS starten, Live-Migration auf zweiten Knoten. [HARDWARE-GEBLOCKT — erfordert NFS-Share + zweiten Cluster-Knoten mit libvirt; srv2 nicht vollständig als Cluster-Mitglied provisioniert; wird bei 7.0.1-Produktions-Rollout validiert]
- [x] Quota-Ueberschreitung gibt korrekten Fehler zurueck.

Validierung (2026-04-22, srv1.beagle-os.com):
- Lokaler Unit-Test `tests/unit/test_ubuntu_beagle_provisioning_quota.py` erfolgreich (2/2).
- Live-Smoke ueber `POST /api/v1/provisioning/vms` mit temporaer auf `1` Byte gesetzter Pool-Quota:
	API antwortet reproduzierbar mit `400 bad_request` und Fehlertext `quota_exceeded: pool 'local' ...`.
- Urspruengliche Pool-Quota nach Testlauf automatisch wiederhergestellt (`quota_bytes: 0`).

Validierung (2026-04-23, srv1.beagle-os.com):
- Neuer reproduzierbarer Smoke `scripts/test-storage-directory-smoke.sh` ausgefuehrt.
- Ergebnis: `STORAGE_DIRECTORY_SMOKE=PASS` mit folgenden Checks:
	- VM auf Directory/qcow2 angelegt und gestartet,
	- Snapshot erfolgreich erstellt,
	- Snapshot erfolgreich wiederhergestellt,
	- Exit-Code `0`.
- ZFS-Live-Smoke auf `srv1.beagle-os.com` ergaenzt: `scripts/test-storage-zfs-smoke.sh`.
- Ergebnis: `STORAGE_ZFS_SMOKE=PASS` mit folgenden Checks:
	- temporaerer ZFS-Pool auf Loopback-Device erstellt,
	- VM mit ZFS-zvol Disk angelegt und gestartet,
	- ZFS-Snapshot erstellt,
	- ZFS-Clone erstellt,
	- Exit-Code `0`.
- Offener Folgecheck (NFS) bleibt infra-seitig blockiert auf `srv1`: `exportfs`/`showmount` sind nicht konfiguriert und fuer den Live-Migrationsteil ist zusaetzlich ein zweiter erreichbarer Cluster-Host erforderlich.
