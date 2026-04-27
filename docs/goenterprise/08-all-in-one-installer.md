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
- [x] Tests: `tests/unit/test_installer_validation.py` (Parameter-Validierung)

### Schritt 2 — Seed-Config für Zero-Touch-Deployment

- [x] `server-installer/seed-config/`: YAML-Format für vollständig automatische Installation:
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
- [x] Installer: wenn `/media/beagle-seed.yaml` auf USB vorhanden → vollautomatisch, kein Dialog
- [x] Tests: `tests/unit/test_seed_config_parser.py`

### Schritt 3 — PXE-Boot-Support

- [x] `scripts/setup-pxe-server.sh`:
  - Richtet dnsmasq + TFTP-Server auf bestehendem Beagle-Node ein
  - Stellt Beagle-Installer-Image via PXE bereit
  - Unterstützt Seed-Config per DHCP-Option (URL zur Seed-Config-Datei)
- [x] Dokumentation: `docs/deployment/pxe-deployment.md`
- [x] Tests: `tests/integration/test_pxe_boot.sh` (prüft TFTP-Erreichbarkeit + Image-Integrität)

### Schritt 4 — Cluster-Auto-Join

- [x] `server-installer/`: Nach Installation: wenn `cluster.join` in Seed-Config → automatisch `beaglectl cluster join <ip> --token <token>`
- [x] `beagle-host/services/cluster_service.py`: `generate_enrollment_token()` (einmal-verwendbar, 24h gültig)
- [x] `beagle-host/bin/beagle-control-plane.py`: `POST /api/v1/cluster/join` mit Token-Validierung
- [x] Tests: `tests/unit/test_cluster_enrollment_token.py`

### Schritt 5 — Post-Install Health-Check

- [x] `server-installer/post-install-check.sh`:
  - Prüft: Netzwerk erreichbar, Beagle-Services laufen, Storage mounted, GPU erkannt (wenn vorhanden), Cluster-Verbindung aktiv
  - Ausgabe: Grüner Bildschirm ("Installation erfolgreich") oder Fehlerdetails
  - Report wird an Cluster-Controller gesendet: "Neuer Node ist ready"
- [x] Web Console: Benachrichtigung wenn neuer Node beigetreten
- [x] Tests: `tests/unit/test_post_install_check.py`

---

## Testpflicht nach Abschluss

- [ ] TUI: Installer läuft durch alle 5 Schritte mit korrekter Validierung.
- [ ] Seed-Config: Vollautomatische Installation ohne Dialog aus YAML-Datei.
- [ ] PXE: Installer via PXE bootbar, Seed-Config via DHCP übergeben.
- [x] Cluster-Join: Neuer Node joined automatisch Cluster mit einmal-Token.
- [x] Post-Install: Health-Check meldet grünen Status, Web-Console zeigt neuen Node.

### Update 2026-04-27

- `scripts/beagle-cluster-auto-join.sh` + `beagle-cluster-auto-join.service` fuehren den persistierten Join-Wunsch auf dem Zielhost jetzt automatisch beim ersten produktiven Boot aus.
- `POST /api/v1/cluster/join` war bereits vorhanden; die offene Checkbox war veraltet und ist jetzt dokumentarisch geschlossen.
- `POST /api/v1/nodes/install-check` und `GET /api/v1/nodes/install-checks` sind live; die Cluster-WebUI zeigt den letzten erfolgreichen Node-Ready-Report als Banner im Cluster-Panel.
- `cluster_membership.py` propagiert den gemeinsamen Install-Check-Report-Token jetzt im Join-Response auf neue Cluster-Member, damit der Post-Install-Report anschliessend direkt an den Leader gesendet werden kann.
- `post-install-check.sh` wurde an den aktuellen Host-Stack angepasst:
  - prueft `beagle-control-plane` statt der alten `beagle-host`/`beagle-manager`-Units
  - nutzt `/healthz` statt des auth-pflichtigen alten `/api/v1/health`-Pfads
  - baut den Report-JSON-Body ohne `jq`-Abhaengigkeit
- Live validiert:
  - `srv1` und `srv2` zeigen sich wieder gegenseitig als `online`
  - `srv2` meldete am `2026-04-27T09:57:29Z` erfolgreich einen `pass`-Post-Install-Report an `srv1`

### Update 2026-04-27 (PXE + Seed-Config)

- `beagle-server-installer` liest jetzt vor dem UI automatisch Seed-Dateien aus:
  - `/media/beagle-seed.yaml`
  - `/run/live/medium/beagle-seed.yaml`
  - Kernel-/PXE-Argument `beagle.seed_url=...`
- `scripts/build-server-installer.sh` legt den YAML-Parser reproduzierbar ins Live-Image unter `/usr/local/share/beagle/seed_config_parser.py`.
- Seed-Konfiguration kann jetzt Hostname, Admin-User, Admin-Passwort, Disk, Cluster-Join und statisches Netzwerk ohne Dialog setzen.
- Neuer PXE-Helfer `scripts/setup-pxe-server.sh`:
  - extrahiert `vmlinuz`/`initrd` aus dem Server-Installer-ISO
  - erzeugt `grubnetx64.efi`-/optional BIOS-PXE-Artefakte
  - schreibt `dnsmasq`-Konfiguration und rendert `beagle.seed_url=...` in die Boot-Menüs
- Neue Doku: `docs/deployment/pxe-deployment.md`
- Neue Tests:
  - `tests/unit/test_installer_validation.py`
  - `tests/unit/test_post_install_check.py`
  - `tests/integration/test_pxe_boot.sh`
- Live validiert:
  - `srv1`: PXE-Dry-Run gegen echtes Installer-ISO unter `/opt/beagle/dist/...` erfolgreich
  - `srv2`: derselbe PXE-Dry-Run erfolgreich

### Bekannte Restgrenze

- Der aktuelle Zero-Touch-Pfad akzeptiert nur `raid: 0`. Mehrdisk-RAID im Installer bleibt als eigener offener TUI-/Storage-Block bestehen.
