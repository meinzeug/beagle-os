# 08 — All-in-One Bare-Metal Installer

Stand: 2026-04-24  
Priorität: 8.1.1 (Q4 2026)

---

## Motivation

### Das heutige Installations-Erlebnis

1. Download ISO
2. Boot von USB
3. Kompliziertes Setup (Netzwerk, RAID, LVM, Beagle-Services)
4. Manuelles Installieren der Beagle-Services
5. Manuelles Konfigurieren

**Ergebnis**: Ein technisch erfahrener Admin braucht 2-4 Stunden pro Server.

### Enterprise-Ziel: "30-Minuten-Zero-Touch-Deployment"

1. USB einstecken
2. Booten
3. 5 Fragen beantworten (oder: nichts, wenn PXE/Seed-Config)
4. Nach 30 Minuten: Server betriebsbereit, Web-Console erreichbar, ready to join cluster

### Was Konkurrenten bieten

| Produkt | Installer |
|---|---|
| Proxmox | Graphischer Installer, 10-15 Min, gut aber kein Zero-Touch |
| XCP-ng | Graphischer Installer, ähnlich Proxmox |
| Azure Stack HCI | Windows Admin Center, sehr komplex |
| **Beagle GoEnterprise** | **Zero-Touch PXE + USB-Installer mit Seed-Config** |

---

## Schritte

### Schritt 1 — Interaktiver TUI-Installer (Verbesserung)

- [ ] `server-installer/`: TUI-Installer (via `whiptail` oder `dialog`) überarbeiten:
  - Schritt 1: Sprache/Tastatur
  - Schritt 2: Disk-Auswahl + RAID-Level (RAID0/1/5/10) — automatisch erkannte Disks anzeigen
  - Schritt 3: Netzwerk (DHCP oder statisch, mit Test-Ping)
  - Schritt 4: Hostname + Admin-Password
  - Schritt 5: Cluster-Join (optional: IP des bestehenden Clusters oder "Neuer Cluster")
  - Auto-Validation aller Eingaben vor Bestätigung
- [ ] Tests: `tests/unit/test_installer_validation.py` (Parameter-Validierung)

### Schritt 2 — Seed-Config für Zero-Touch-Deployment

- [ ] `server-installer/seed-config/`: YAML-Format für vollständig automatische Installation:
  ```yaml
  hostname: beagle-node-1
  disk: /dev/sda
  raid: 1
  network:
    interface: eth0
    mode: static
    ip: 192.168.1.10/24
    gateway: 192.168.1.1
  cluster:
    join: 192.168.1.1
    token: <enrollment-token>
  ```
- [ ] Installer: wenn `/media/beagle-seed.yaml` auf USB vorhanden → vollautomatisch, kein Dialog
- [x] Tests: `tests/unit/test_seed_config_parser.py`

### Schritt 3 — PXE-Boot-Support

- [ ] `scripts/setup-pxe-server.sh`:
  - Richtet dnsmasq + TFTP-Server auf bestehendem Beagle-Node ein
  - Stellt Beagle-Installer-Image via PXE bereit
  - Unterstützt Seed-Config per DHCP-Option (URL zur Seed-Config-Datei)
- [ ] Dokumentation: `docs/deployment/pxe-deployment.md`
- [ ] Tests: `tests/integration/test_pxe_boot.sh` (prüft TFTP-Erreichbarkeit + Image-Integrität)

### Schritt 4 — Cluster-Auto-Join

- [ ] `server-installer/`: Nach Installation: wenn `cluster.join` in Seed-Config → automatisch `beaglectl cluster join <ip> --token <token>`
- [ ] `beagle-host/services/cluster_service.py`: `generate_enrollment_token()` (einmal-verwendbar, 24h gültig)
- [ ] `beagle-host/bin/beagle-control-plane.py`: `POST /api/v1/cluster/join` mit Token-Validierung
- [ ] Tests: `tests/unit/test_cluster_enrollment_token.py`

### Schritt 5 — Post-Install Health-Check

- [ ] `server-installer/post-install-check.sh`:
  - Prüft: Netzwerk erreichbar, Beagle-Services laufen, Storage mounted, GPU erkannt (wenn vorhanden), Cluster-Verbindung aktiv
  - Ausgabe: Grüner Bildschirm ("Installation erfolgreich") oder Fehlerdetails
  - Report wird an Cluster-Controller gesendet: "Neuer Node ist ready"
- [ ] Web Console: Benachrichtigung wenn neuer Node beigetreten
- [ ] Tests: `tests/unit/test_post_install_check.py`

---

## Testpflicht nach Abschluss

- [ ] TUI: Installer läuft durch alle 5 Schritte mit korrekter Validierung.
- [ ] Seed-Config: Vollautomatische Installation ohne Dialog aus YAML-Datei.
- [ ] PXE: Installer via PXE bootbar, Seed-Config via DHCP übergeben.
- [ ] Cluster-Join: Neuer Node joined automatisch Cluster mit einmal-Token.
- [ ] Post-Install: Health-Check meldet grünen Status, Web-Console zeigt neuen Node.
