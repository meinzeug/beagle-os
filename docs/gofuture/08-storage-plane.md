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

- [ ] `providers/beagle/storage/lvm_thin.py` implementiert den Contract für LVM-Thin-Provisioning.

LVM-Thin-Provisioning ist besonders effizient bei vielen ähnlichen VMs (VDI-Pools)
da Thin-Volumes nur den tatsächlich genutzten Speicher belegen. `create_volume` legt
ein Thin-LV mit `lvcreate --thin -V` an. `snapshot` nutzt `lvcreate -s` auf ein
Thin-LV. `clone` erstellt ein neues Thin-LV von einem Snapshot. Das Backend erfordert
eine vorgelegte VG/LV-Konfiguration auf dem Host die beim Installer-Schritt angelegt
werden kann. Quotas sind über LVM-Thin-Pool-Limits implementierbar.

---

### Schritt 4 — ZFS-Backend implementieren

- [ ] `providers/beagle/storage/zfs.py` implementiert den Contract für ZFS-Datasets.

ZFS bietet Copy-on-Write-Snapshots mit vernachlässigbarem Overhead was es ideal für
VM-Snapshots und Clones macht. `create_volume` legt ein ZFS-Volume (`zvol`) an.
`snapshot` nutzt `zfs snapshot`. `clone` ist `zfs clone`. `rollback` ist ebenfalls
nativ unterstützt. Die ZFS-ARC (Adaptive Replacement Cache) verbessert I/O-Performance
bei häufig zugegriffenen Daten erheblich. Das Backend erfordert ZFS-Kernel-Modul
auf dem Host (bei Debian via `zfsutils-linux`).

---

### Schritt 5 — NFS-Backend implementieren

- [ ] `providers/beagle/storage/nfs.py` implementiert den Contract für NFS-gemountete Storage-Pools.

NFS-Storage ermöglicht shared Storage über mehrere Cluster-Knoten was Live-Migration
ohne Disk-Transfer ermöglicht. `create_volume` legt eine qcow2-Datei auf dem NFS-Mount
an. Das Backend erfordert dass der NFS-Mount auf allen Knoten gleich erreichbar ist.
Mount-Management (automount, fstab-Eintrag) wird vom Install-Assistenten übernommen.
NFS ist nicht ideal für I/O-intensive Workloads aber einfach aufzusetzen und für
Home-Lab- und SMB-Umgebungen gut geeignet.

---

### Schritt 6 — Quotas pro Tenant/Pool in Web Console verwalten

- [ ] API-Endpunkt `GET/PUT /api/v1/storage/pools/{pool}/quota` anlegen.
- [ ] Web Console: Storage-Pool-Übersicht mit Quota-Anzeige und Setter.

Quotas auf Storage-Pool-Ebene verhindern dass ein einzelner Tenant oder Pool den
gesamten verfügbaren Speicher belegt. Die Quota wird beim Volume-`create_volume`-Aufruf
geprüft und bei Überschreitung mit einem sprechenden Fehler abgelehnt. Die Web Console
zeigt in der Pool-Übersicht: Gesamtkapazität, genutzt, verfügbar, Quota-Limit.
Administratoren können Quotas per API oder Web Console setzen und ändern.

---

## Testpflicht nach Abschluss

- [ ] VM mit Directory-Backend anlegen, starten, Snapshot erstellen, Snapshot wiederherstellen.
- [ ] VM mit ZFS-Backend: Snapshot und Clone erfolgreich.
- [ ] NFS-Backend: VM auf gemountet-NFS starten, Live-Migration auf zweiten Knoten.
- [ ] Quota-Überschreitung gibt korrekten Fehler zurück.
