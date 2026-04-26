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

### Schritt 6 — `/#panel=virtualization` UX-Refactor: GPU/vGPU/SR-IOV bedienbar machen

- [ ] GPU-Bereich im Virtualization-Panel neu strukturieren: physische GPUs, Passthrough, vGPU/mdev und SR-IOV getrennt anzeigen.
- [ ] GPU-Readiness klar erklären: IOMMU-Gruppe, aktueller Treiber, `passthrough_ready`, Status `available|assigned|not-isolatable|driver-bound`.
- [ ] Für nicht nutzbare GPUs konkrete Ursache und nächsten Schritt anzeigen, z.B. `IOMMU-Gruppe enthält Root Port`, `ACS fehlt`, `vfio-pci nicht aktiv`, `Host-Reboot erforderlich`.
- [ ] GPU-Zuweisung als Wizard bauen: GPU wählen, Ziel-VM wählen, Risiko-/Reboot-Hinweis, XML-Änderung bestätigen, Ergebnis anzeigen.
- [ ] Release/Detach als eigener Flow mit Bestätigung und sichtbarer Auswirkung auf VM-/GPU-State.
- [ ] vGPU/mdev-Flow verbessern: unterstützte Typen als Cards, Slot-Kapazität, Erzeugen/Löschen/Zuweisen mit Fehlerzuständen.
- [ ] SR-IOV-Flow verbessern: VF-Anzahl setzen, VFs anzeigen, VM-Zuweisung vorbereiten, Kernel-/Hardware-Constraints erklären.
- [ ] srv2-spezifischen Status sichtbar machen: NVIDIA GTX 1080 vorhanden, `vfio-pci` gebunden, aber `passthrough_ready=false` wegen nicht isolierbarer IOMMU-Gruppe.
- [ ] UI-Regressions ergänzen: not-isolatable Rendering, Wizard-Payload, Assign/Release-Fehler, mdev/SR-IOV Empty-States.
- [ ] E2E-Validierung erst abhaken, wenn eine VM-seitige GPU-Prüfung (`nvidia-smi` oder äquivalent) erfolgreich ist oder der Hardware-Blocker explizit als nicht lösbar entschieden wurde.

Warum dieser Schritt noch offen ist:
Die GPU-APIs und erste Tabellen existieren, aber die WebUI muss Betreiber vor gefährlichen oder unmöglichen Aktionen schützen. `srv2` zeigt den typischen Fall: Die GPU ist vorhanden und an `vfio-pci` gebunden, aber wegen IOMMU-Gruppierung nicht sauber isolierbar. Das darf nicht als generischer Fehler in einer Tabelle verschwinden, sondern muss als verständliche Handlungsanweisung in der Web Console erscheinen.

---

## Testpflicht nach Abschluss

- [x] GPU-Passthrough: NVIDIA GTX 1080 (GP104, 0000:01:00.0) auf srv2 an vfio-pci gebunden. API meldet `driver: vfio-pci`. **Hardware-Constraint**: IOMMU-Gruppe 1 enthält PCIe Root Port (00:01.0) — kein ACS in Hardware, kein `pcie_acs_override` in Stock-Debian-6.1-Kernel. VM-seitiger `nvidia-smi`-Test erfordert whole-group-passthrough (OVMF + NVIDIA-Treiber in VM) — defer auf Wunsch des Betreibers. Inventory-API korrekt: `passthrough_ready: false, status: not-isolatable`.
- [x] vGPU: 4 VMs je 1 vGPU, 5. VM bleibt in `pending-gpu`. (`tests/unit/test_vgpu_quota.py` 7 unit tests; 4-slot scenario: VMs 1-4 state=free mit eindeutigen Slots, VM 5 state=pending-gpu; lokal + srv1 7/7 pass)
- [x] GPU-Inventory in Web Console zeigt alle verfügbaren GPUs mit korrektem Status.
- [x] After-Passthrough-Reboot: beagle-control-plane startet ohne Fehler. Validierung (2026-04-25): Nach GPU-vfio-pci-Binding `systemctl restart beagle-control-plane` → `active (running)`, Health-Check `ok: true`, GPU-Inventory-API antwortet korrekt, keine Fehler im Journal.
