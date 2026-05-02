# 10 — GPU- und Device-Passthrough

Stand: 2026-04-20

## Stand heute

- libvirt unterstuetzt grundsaetzlich PCI-passthrough; in Beagle nicht als first-class Workflow exponiert.
- USB-Device-Bindings nur teilweise (`services/vm_usb.py`).

## Ziel 7.0

### GPU-Inventory

- `services/gpu_inventory.py` (neu) scannt PCI:
  - vendor/device,
  - IOMMU group,
  - vfio-binding-status,
  - vGPU-faehig (NVIDIA mdev, Intel SR-IOV) ja/nein,
  - Anzahl konfigurierter mdev-Profile.
- Inventory wird im Cluster-Store gehalten, sodass Scheduler ueber Knoten hinweg planen kann.

### GPU-Klassen

`GpuClass` ist Pool-Constraint:

```yaml
GpuClass:
  id: gpu-nvl4-1g
  vendor: nvidia
  model: L4
  share: vgpu
  profile: nvidia-l4-1g
  total_per_card: 7
```

Pool-Bindung:

```yaml
DesktopPool:
  resources:
    gpu_class: gpu-nvl4-1g
    gpu_count: 1
```

Scheduler placeert nur auf Knoten, die freie Slots dieser Klasse haben.

### Passthrough-Workflow

- Operator-Aktion in Web Console: "Knoten X: GPU bind to vfio".
- Service `services/gpu_passthrough.py` (neu) macht:
  1. Pruefung IOMMU enabled (`intel_iommu=on` oder `amd_iommu=on`),
  2. driver detach (NVIDIA/AMD/Intel host driver),
  3. vfio-pci binding,
  4. persistente Modprobe-Konfiguration ablegen,
  5. Reboot-Hint falls noetig.
- Audit + Rollback-Pfad.

### vGPU

- NVIDIA: mdev-Profile aus NVIDIA-vGPU-Treiber, Lizenzserver-Hinweise (NLS).
- Intel: SR-IOV (i915), GVT-d nur Single-User.
- AMD: derzeit eingeschraenkt, dokumentiert.
- Wo vGPU nicht verfuegbar ist, fallback auf full-passthrough.

### USB / Wacom / Audio Redirect

- USB-Redirect Klassen (siehe Policy in [06-iam-multitenancy.md](06-iam-multitenancy.md)).
- Wacom + Stylus-Druck: Apollo/Beagle Stream Server-Pfad + Beagle Stream Client-Embedded mit Tablet-Eingabe getestet.
- Audio-In: Mikro-Capture im Endpoint-OS, Apollo-Audio-In-Stream.
- Webcam: Pass-through ueber USB-Klassen-Redirect (HID + UVC) oder ueber dedicated stream channel.

### Encoder-Reservierung

- Manche GPUs haben harte Encoder-Limits (NVENC sessions).
- Scheduler pflegt `encoder_slots_used / encoder_slots_total` pro Karte.
- Pool-Profil kann Encoder-Reservierung erzwingen.

### Sicherheit

- vfio-Passthrough macht VMs faktisch zu Kernel-Trust-Zonen — nur fuer entsprechende Pools erlauben.
- USB-Klassen-Redirect: Default-Deny ausser Tastatur/Maus/HID.
- Audio-In nur, wenn Tenant-Policy es erlaubt (Datenschutz).

### Akzeptanzkriterien 7.1.2

- 1x NVIDIA L4 mit 7 vGPU-Slots: Pool von 7 Desktops, alle bekommen je 1 vGPU.
- 1x Wacom Cintiq an Endpoint, Druck-Sensitivitaet im Guest 1:1.
- USB-Mass-Storage-Redirect kann pro Pool deaktiviert werden, Audit-Eintrag bei Versuch.
