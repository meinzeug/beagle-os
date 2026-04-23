# 12 — 7.1.2 GPU Plane (Passthrough + vGPU)

Stand: 2026-04-20  
Priorität: 7.1 (Q2 2027)  
Referenz: `docs/refactorv2/10-gpu-device-passthrough.md`

---

## Schritte

### Schritt 1 — GPU-Inventory (PCI-Scan, IOMMU-Gruppen) implementieren

- [x] `beagle-host/services/gpu_inventory.py` anlegen: PCI-Scan, IOMMU-Gruppen ermitteln, GPU-Modelle identifizieren.
- [x] Web Console: GPU-Inventory-Sektion im Knoten-Detail.

Das GPU-Inventory ist die Grundvoraussetzung für alle weiteren GPU-Plane-Funktionen.
Es scannt die PCI-Devices des Hosts via `lspci` und filtert GPU-Klassen (03xx).
IOMMU-Gruppen werden aus `/sys/kernel/iommu_groups/` gelesen. Für jede GPU wird
der Vendor (NVIDIA/AMD/Intel), das Modell, der aktuell geladene Treiber, der verfügbare
vGPU-Typ und der IOMMU-Gruppen-Status ermittelt. Eine GPU ist nur für Passthrough
nutzbar wenn alle Geräte ihrer IOMMU-Gruppe passthrough-fähig sind. Das Web Console
zeigt im Knoten-Detail alle verfügbaren GPUs mit Status: verfügbar-für-passthrough,
bereits zugeteilt, nicht isolierbar (IOMMU-Gruppe enthält weitere Geräte).

---

### Schritt 2 — GPU-Passthrough-Workflow mit Host-Treiber-Detach implementieren

- [x] `gpu_passthrough_service.py` anlegen: `vfio-pci`-Binding, Treiber-Detach, libvirt-XML-Patch.
- [x] Web Console: "GPU zu VM zuweisen" Action im VM-Detail.

GPU-Passthrough erfordert dass der Host-Treiber (nvidia, amdgpu, i915) von der GPU
entladen und `vfio-pci` als Ersatz-Treiber gebunden wird. Dieser Prozess erfordert
einen Reboot des Hosts (oder zumindest ein GPU-Reset wenn das unterstützt wird).
Das Web Console warnt den Betreiber explizit über den erforderlichen Host-Reboot.
Nach dem Treiber-Wechsel wird die GPU per PCI-Passthrough der VM zugewiesen indem
die libvirt-Domain-XML um ein `<hostdev>`-Element erweitert wird. Die VM sieht
dann die GPU als physisches Gerät und kann den nativen Treiber installieren.

---

### Schritt 3 — NVIDIA Mediated Devices (vGPU) implementieren

- [x] `vgpu_service.py` anlegen: mdev-Typen lesen, mdev-Instanzen anlegen, VMs zuweisen.
- [x] Web Console: vGPU-Typ und Slot auswählen bei VM-Konfiguration.

NVIDIA vGPU (Mediated Devices) ermöglicht die Teilung einer physischen GPU in mehrere
virtuelle GPU-Instanzen. Voraussetzung: NVIDIA-vGPU-Treiber (erfordert NVIDIA-Lizenz,
dokumentiert in Risk R5) und kompatible GPU. `mdev`-Typen werden aus
`/sys/class/mdev_bus/*/mdev_supported_types/` gelesen. Eine mdev-Instanz wird per
`/sys/class/mdev_bus/*/mdev_supported_types/*/create` erzeugt. Die libvirt-Domain-XML
wird um ein `<hostdev model="vfio-pci">` mit der mdev-UUID erweitert. Da NVIDIA-Lizenzen
kostenpflichtig sind ist vGPU ein optionales Feature das explizit aktiviert wird.

---

### Schritt 4 — Intel SR-IOV vGPU implementieren

- [x] Intel SR-IOV on Arc/Xe-LP: VF-Erzeugung, libvirt-Assignment.
- [x] Dokumentation: Hardware-Voraussetzungen und Kernel-Modul-Konfiguration.

Intel GPU SR-IOV (verfügbar ab Intel Arc / Xe-LP Architektur) erlaubt ähnlich wie
NVIDIA vGPU die Aufteilung einer GPU in virtuelle Funktionen (VFs). Die Anzahl VFs
wird als Kernel-Parameter oder zur Laufzeit über `/sys/bus/pci/devices/.../sriov_numvfs`
konfiguriert. Jede VF ist eine eigenständige PCI-Funktion und kann per Passthrough
einer VM zugewiesen werden. Intel SR-IOV erfordert keine zusätzliche Lizenz was es
als Open-Source-Alternative zu NVIDIA vGPU attraktiv macht. Der Treiber-Support
in aktuellen Linux-Kerneln (6.x) ist noch experimentell und wird im Test-Bericht
dokumentiert.

---

### Schritt 5 — Pool-Constraint `gpu_class` im Scheduler implementieren

- [x] `DesktopPool` bekommt optionales Feld `gpu_class` (z.B. `nvidia-l4-1g`, `passthrough-amd-rx7900`).
- [x] Scheduler reserviert GPU-Slots bei Pool-Scaling und weist VMs nur Knoten mit passendem GPU-Slot zu.

Der Scheduler muss bei der Zuweisung von Pool-VMs auf Knoten nicht nur CPU/RAM
sondern auch GPU-Slots berücksichtigen. Ein Pool mit `gpu_class: nvidia-l4-1g`
darf VMs nur auf Knoten starten wo mdev-Instanzen dieses Typs verfügbar sind.
GPU-Slot-Reservierungen werden im Cluster-Store gespeichert damit kein GPU-Slot
doppelt vergeben wird. Wenn nicht genug GPU-Slots verfügbar sind landen neue Pool-VMs
in einem `pending-gpu`-Status und die Web Console zeigt eine Warnung. Der Betreiber
kann dann entweder den Pool verkleinern oder neue GPU-Hardware hinzufügen.

---

## Testpflicht nach Abschluss

- [ ] GPU-Passthrough: VM sieht physische GPU, `nvidia-smi` oder `glxinfo` erfolgreich.
- [ ] vGPU: 4 VMs je 1 vGPU, 5. VM bleibt in `pending-gpu`.
- [ ] GPU-Inventory in Web Console zeigt alle verfügbaren GPUs mit korrektem Status.
- [ ] After-Passthrough-Reboot: beagle-control-plane startet ohne Fehler.
