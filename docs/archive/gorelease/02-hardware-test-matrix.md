# 02 - Hardware- und Test-Matrix

Stand: 2026-04-27  
Ziel: Kosten niedrig halten, aber echte Hardware nur dort einsetzen, wo sie technisch notwendig ist.

---

## Hardware-Klassen

| Klasse | Typ | Mindestgroesse | Zweck | Muss laufen |
|---|---|---|---|---|
| H0 | lokaler Entwickler-Rechner | 4 Cores, 16 GB RAM | Unit-Tests, statische Checks, Shell-Syntax, Docs | immer |
| H1 | kleine Hetzner VM | 2-4 vCPU, 4-8 GB RAM | WebUI/API/Auth/Update/Release-Smokes ohne echte KVM-Abnahme | R2 |
| H2 | zwei kleine Hetzner VMs | je 2-4 vCPU, 4-8 GB RAM | Zwei-Server-Logik, Cluster-Join, Auth, Repo-Auto-Update, Download-Status | R2/R3 |
| H3 | dedizierter CPU-Server | 8-16 Cores, 64 GB RAM, SSD/NVMe | KVM/libvirt, VM-Provisioning, ISO-Install, Backup/Restore | R3/R4 |
| H4 | zweiter dedizierter CPU-Server | 8-16 Cores, 32-64 GB RAM | echte Multi-Node-Migration/HA/Failover | R3/R4 falls HA verkauft wird |
| H5 | GPU-Server | NVIDIA GTX/RTX/Ada oder Datacenter-GPU, IOMMU | GPU-Passthrough, NVENC, Gaming-Pool, vGPU/MDEV falls Hardware kann | nur GPU-Gates |

---

## Kostenregel

- Kleine 2-4 Core Hetzner VMs sind Standard fuer dauerhafte Smoke- und Release-Gates.
- Dedizierte CPU-Server werden nur gebucht, wenn KVM/libvirt oder echte Storage-/Install-Tests benoetigt werden.
- GPU-Server werden nur fuer kurze Testfenster gebucht.
- GPU-Testfenster vorher festlegen: Ziel, Dauer, Skripte, erwartete Artefakte, Abbruchkriterien.
- Wenn ein Serverboerse-/Auction-GPU-Server nicht stundenweise verfuegbar ist, nur kurzfristig buchen und nach Testabschluss kuendigen.

---

## Dauerhafte Minimalumgebung

Diese Umgebung sollte permanent oder sehr guenstig laufen:

- [ ] `rel1`: kleine VM, 2 vCPU, 4-8 GB RAM, Ubuntu/Debian, nur Control Plane/API/WebUI-Smokes.
- [ ] `rel2`: kleine VM, 2 vCPU, 4-8 GB RAM, zweiter Node fuer Cluster-/Update-/Download-Smokes.
- [ ] DNS: `rel1.beagle-os.com`, `rel2.beagle-os.com` oder interne Subdomains.
- [ ] TLS: echte Zertifikate ueber Let's Encrypt.
- [ ] Firewall: nur `22`, `80`, `443` oeffentlich, interne Ports nur allowlisted.

Diese Umgebung ersetzt keine KVM-Abnahme.

---

## Dedizierte CPU-Abnahme

Fuer R3/R4 wird mindestens ein dedizierter CPU-Host benoetigt:

- [ ] `/dev/kvm` vorhanden.
- [ ] `libvirtd`/`virsh` funktionsfaehig.
- [ ] Beagle Server-Installer kann auf leerem Zielsystem installieren.
- [ ] VM-Provisioning aus WebUI und API funktioniert.
- [ ] VM-Start, Stop, Reboot, Delete, Snapshot und Reset funktionieren.
- [ ] Backup und Restore einer echten VM-Disk funktionieren.
- [ ] Host-Update erzeugt danach konsistente Download-Artefakte.

Empfehlung:

- 8-16 Cores
- 64 GB RAM
- 1 TB NVMe
- kein GPU-Zwang

---

## Zwei-Server-Abnahme

Zwei echte Server sind nur fuer folgende Gates zwingend:

- [ ] Cluster-Join und Member-Management.
- [ ] Remote-Inventory und konsistente Node-Sicht in der WebUI.
- [ ] Maintenance/Drain und Failover-Simulation.
- [ ] Backup-Replikation oder Restore auf anderem Host.
- [ ] HA-Manager/Fencing, falls als Enterprise-Funktion angeboten.
- [ ] Session-Handover, falls als produktives Feature angeboten.

Wenn nur Control-Plane-Logik getestet wird, reichen zwei kleine VMs. Wenn echte VM-Migration/HA getestet wird, braucht es zwei KVM-faehige dedizierte Hosts.

---

## GPU-Abnahme

GPU-Hardware ist nur fuer GPU-Funktionen Pflicht:

- [ ] GPU-Inventory erkennt Karte, Treiberzustand, IOMMU-Gruppe und Passthrough-Faehigkeit.
- [ ] Passthrough-VM sieht GPU und Audio-Funktion im Gast.
- [ ] NVENC-/Streaming-Pfad laeuft mit echter Session.
- [ ] Gaming-Pool blockiert sauber, wenn keine GPU verfuegbar ist.
- [ ] GPU-Pool zeigt Auslastung, Temperatur, VRAM und Assignment korrekt.
- [ ] Reboot-Proof: Host-Reboot erhaelt VFIO-/Passthrough-Konfiguration.
- [ ] vGPU/MDEV nur als bestanden markieren, wenn Hardware und Lizenzmodell es real unterstuetzen.

Mietstrategie:

- [ ] GPU-Server fuer 4-8 Stunden buchen.
- [ ] Vorher Testskripte lokal fertigstellen.
- [ ] Nach SSH-Zugriff sofort `lspci`, IOMMU, VFIO, libvirt und GPU-Smoke fahren.
- [ ] Ergebnisse in `docs/refactor/05-progress.md` dokumentieren.
- [ ] Server direkt nach erfolgreicher Abnahme kuendigen.

---

## Was kleine VMs nicht beweisen

Kleine 2-4 Core VMs sind guenstig, aber sie beweisen nicht:

- echte KVM-Performance
- GPU-Passthrough
- vGPU/MDEV
- Bare-Metal-Install
- Storage-Performance
- Reboot-Persistenz von VFIO/IOMMU
- echte Netzwerk-/Streaming-Latenz unter GPU-Last

Diese Punkte muessen auf H3/H4/H5 laufen.

