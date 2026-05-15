# Beagle OS Live USB — Boot Bug Dokumentation

Datum: 2026-05-13  
Hardware: Lenovo B50-45 (InsydeH20 BIOS A1CN24WW V1.12, AMD A6-6310 Kabini, 8 GB RAM)  
Stick: Generic Flash Disk 468 GB, GPT, Label BEAGLELIVE

---

## Symptome (chronologisch)

### Phase 1 — Stick wird gar nicht angezeigt
- Lenovo B50-45 zeigt den USB-Stick weder im UEFI- noch im Legacy-Boot-Menü.
- Kein Boot-Eintrag, egal ob USB 2.0 oder 3.0 Port.

**Ursache:** Reines GPT mit Protective MBR.  
InsydeH20 wertet kein aktives (`0x80`) Legacy-MBR-Partitionseintrag aus und ignoriert den Stick.  
Zusätzlich: `EFI/BOOT/grub.cfg` hatte `hd1,gpt2` hartkodiert → scheitert wenn USB nicht als zweite Disk enumiert wird.  
`BOOTX64.CSV` enthielt Ubuntu-Branding statt Beagle OS.

**Fix (Commits a42d63c):**
- `_apply_hybrid_mbr()` in `usb_writer_write_stage.sh`: `sgdisk --hybrid 2` + Python-Patch setzt MBR-Eintrag auf active (`0x80`) + Typ `0x0C` (FAT32 LBA)
- `EFI/BOOT/grub.cfg`: hartkodierter Disk-Hint durch `search --no-floppy --fs-uuid` ersetzt
- `BOOTX64.CSV`: Beagle OS Branding eingetragen
- GRUB-Module ergänzt: `insmod part_msdos usb usb_keyboard`, `terminal_input console`
- `live-media-timeout` 30→60, `rootdelay=10` für USB 3.x Timing
- AMD-spezifische Kernel-Parameter: `amd_iommu=off` in safe mode, `idle=poll` in legacy IRQ entry
- GRUB-Timeout 5→10s; `gdisk` in apt-Install-Liste und required-tools aufgenommen

---

### Phase 2 — BOOT FAILED: Unable to find a medium containing a live file system
- Stick wird jetzt erkannt und GRUB startet.
- Linux-Kernel bootet und erreicht das live-boot Initramfs-Stage.
- live-boot schlägt fehl mit: **"Unable to find a medium containing a live file system"**

**Ursache:** live-boot Medium-Detection war auf strict UUID-Binding konfiguriert (`live-media=/dev/disk/by-uuid/…`).  
Auf älteren BIOS/Chipsätzen ist der Block-Device-Pfad zu diesem Zeitpunkt noch nicht stabil.  
Außerdem: `toram` war in **allen** Live-Menüeinträgen aktiv, nicht nur im Copy-to-RAM-Eintrag.  
`toram` destabilisiert das frühe Medium-Handling auf Systemen mit wenig USB-Timing-Marge.

**Fix (Commits a375870, 4825194, pending):**
- UUID-Bindung entfernt; Medium-Scan ueber `live-media-path` + `ignore_uuid` (kein `live-media=removable` mehr)
- `live-media-path=/live` bleibt explizit gesetzt
- `live-media-timeout=180` (war 30/60)
- `rootdelay=15 rootwait usb-storage.delay_use=5` ergänzt
- `toram` nur noch im expliziten Copy-to-RAM-Menüeintrag

---

### Phase 3 — Splash erscheint kurz, kein Plymouth, kein Netzwerk-Menü (aktuell offen)
- Stick wird erkannt, GRUB startet, Linux lädt kurz den Splash.
- Danach Schwarzbild oder Reboot, kein Plymouth, kein Netzwerk-TUI-Menü.
- Kein Output mehr sichtbar.

**Bisher nicht eindeutig diagnostiziert** (kein Logzugriff gehabt).

**Update 2026-05-14 (Root Cause gefunden):**
- Der Fruehboot-Logger in `init-premount` stoppte nach `candidate media detected`.
- Ursache war der persistente USB-Mount im Logger selbst (`mount -t vfat -o rw <dev>`),
	der auf Lenovo B50-45 reproduzierbar haengen kann.
- Ergebnis: Der Hook blockiert den Bootpfad vor `init-premount exit`; live-boot faellt
	danach in `Unable to find a medium containing a live file system`.

**Fix (pending commit):**
- Kein Mount mehr im `init-premount`-Logger.
- Logger schreibt nur noch nach `/run/beagle-boot-early.log` und `dmesg`.
- Medium wird weiterhin erkannt und geloggt, aber ohne Blockade-Risiko.

**Verdächtige Ursachen:**
- Plymouth/DRM Initialisierung schlägt auf AMD A6-6310 (amdgpu/radeon) fehl und hängt
- `quiet splash` im Standard-Eintrag unterdrückt alle Meldungen → Hänger unsichtbar
- `idle=nomwait` / `processor.max_cstate=1` nicht ausreichend für Kabini ACPI
- Squashfs/overlayfs mountet nicht korrekt (initramfs findet Medium aber kann nicht mounten)
- frühe systemd-Unit schlägt fehl ohne Retry-Loop

**Nächste Schritte:**
1. **Rebuild mit Payload von srv1** nötig (aktuell in Vorbereitung) — der Stick hat veraltete Payload
2. Beim Boot explizit den **"safe mode / AMD compat"**-Eintrag oder **"legacy IRQ / no ACPI"** wählen, nicht den Standard-Eintrag
3. Frühboot-Logger (`/beagle-boot-early.log` auf Stick) nur in neu gebautem Stick aktiv — noch nicht in alter Payload
4. Falls Simulation nötig: `qemu-system-x86_64` auf srv1 mit `kernel/initrd/squashfs` direkt aus Payload; serielle Ausgabe aktivieren

---

## Frühboot-Logger (Commit 0362ae3)

Datei: `thin-client-assistant/live-build/config/includes.chroot/etc/initramfs-tools/scripts/init-premount/10-beagle-early-bootlog`

- Läuft als `init-premount` Hook im Initramfs, direkt nach GRUB-Übergabe
- Logged nach `/run/beagle-boot-early.log` (immer)
- Versucht best-effort, auf die BEAGLELIVE-Partition zu schreiben: `/beagle-boot-early.log`
- Inhalt: `/proc/cmdline`, `/dev/disk/by-label`, `/dev/disk/by-uuid`, Block-Devices, Retry-Status
- **Greift erst mit neu gebautem Stick** (initrd muss neu generiert worden sein)

Nach Boot: Log lesen mit:
```
# Wenn initramfs-Shell:
cat /run/beagle-boot-early.log

# Wenn Stick am PC:
sudo mount /dev/sdb2 /mnt && cat /mnt/beagle-boot-early.log && sudo umount /mnt
```

---

## Relevante Dateien

| Datei | Funktion |
|---|---|
| `thin-client-assistant/usb/usb_writer_write_stage.sh` | USB-Partitionierung, GRUB-Install, GRUB-Config-Template, `_apply_hybrid_mbr()` |
| `thin-client-assistant/usb/pve-thin-client-usb-installer.sh` | Dependency-Check (gdisk/sgdisk) |
| `thin-client-assistant/live-build/config/includes.chroot/etc/initramfs-tools/scripts/init-premount/10-beagle-early-bootlog` | Frühboot-Logger im Initramfs |
| `thin-client-assistant/live-build/config/hooks/live/013-configure-amd-initramfs.hook.chroot` | AMD amdgpu/drm Module ins Initramfs |
| `thin-client-assistant/live-build/config/hooks/live/015-refresh-initramfs-early-bootlog.hook.chroot` | Frühlogger ins Initramfs einbauen |
| `thin-client-assistant/live-build/config/hooks/live/016-verify-initramfs-early-bootlog.hook.chroot` | Build-Verify: Frühlogger muss im initrd sein |

---

## Commits (dieser Bug-Serie)

| Commit | Inhalt |
|---|---|
| `a42d63c` | Hybrid MBR, BOOTX64.CSV Branding, EFI grub.cfg UUID-Fix, AMD Kernel-Params, USB-Timing |
| `a375870` | live-media=removable, live-media-timeout=180, rootdelay/rootwait/usb-storage.delay_use |
| `4825194` | toram nur noch im Copy-to-RAM-Eintrag |
| `0362ae3` | Initramfs Frühboot-Logger init-premount |
| `831e56c` | `live-media=removable` entfernt; `live-media-path + ignore_uuid` fuer robusten Medium-Scan |
| `9ee9529` | `init-premount` Logger mountet USB nicht mehr (verhindert Boot-Haenger) |
| `338ac01` | SDHCI-Blacklist in Live-GRUB entfernt, `mmc_core.use_spi_crc=N` aktiv |
| `556b483` | USB-Bootstrap: stale `*-latest` Cache wird standardmaessig nicht mehr vertraut |
| `3ef2535` | USB-Installer bricht hart ab, wenn stale Helper noch `module_blacklist=sdhci...` enthaelt |
| `c7b32a2` | Neuer initramfs `init-bottom` Hook persistiert `/run/beagle-boot-early.log` auf den Stick |

---

## Lenovo B50-45 BIOS-Spezifika

- **InsydeH20 Setup Utility A1CN24WW V1.12**
- Boot-Menü-Taste: **F12** beim POST
- Legacy-Modus: USB-Stick benötigt hybrid MBR mit aktivem (`0x80`) FAT32-LBA (`0x0C`) MBR-Eintrag
- UEFI-Modus: benötigt `EFI/BOOT/BOOTX64.EFI` (liegt vor), `EFI/BOOT/grub.cfg` ohne hartkodierte Disk-Hints
- AMD A6-6310 (Kabini/Jaguar): kritische Kernel-Parameter: `amd_iommu=off`, `nomodeset irqpoll noapic nolapic` für Fallback
- USB 3.0 Ports haben bekannte xHCI-Handoff-Bugs in diesem BIOS-Stand → USB 2.0 Port bevorzugen

---

## Offener Stand (2026-05-15)

- [x] Rebuild mit frischer Payload von srv1 durchgeführt
- [x] Stick neu geschrieben
- [x] Verifiziert: Payload-URL enthaelt `mmc_core.use_spi_crc=N` und keine SDHCI-Blacklist
- [x] Verifiziert: Aktuelle Stick-Fehlerbilder reproduzierbar dokumentiert
- [ ] Nach Boot erneut Logs auf Stick auslesen (`/beagle-boot-early.log`, `pve-thin-client/state/debug/latest.log`)
- [ ] Falls weiterhin keine Logs persistieren: neuen `init-bottom` Persistenz-Hook aus `c7b32a2` im naechsten Build/Stick verifizieren
- [ ] Danach erneuter Lenovo B50-45 Boot-Test bis Netzwerk-TUI oder klarer Stop-Punkt mit persistiertem Early-Log

## Update 2026-05-15

- Trotz aktualisierter Payload und neu geschriebenem Stick bleibt der Endpoint vor der Netzwerk-TUI haengen.
- Auf dem betroffenen Stick waren weder `/beagle-boot-early.log` noch `pve-thin-client/state/debug/latest.log` vorhanden.
- Das weist auf einen sehr fruehen Abbruch hin (vor spaeter Runtime-Logpersistenz).
- Zur Diagnostik wurde ein zusaetzlicher initramfs-Hook im `init-bottom` eingefuehrt,
  der den fruehen `/run/beagle-boot-early.log` best-effort auf den Live-Stick kopiert,
  ohne den Bootablauf bei Persistenzfehlern zu blockieren.

### Phase 4 — SDHCI Controller Interrupt Timeout (Lenovo B50-45 mit Safe Mode)

**Symptome (aus Screenshot 2026-05-15):**
- Boot-Sequenz: GRUB → Kernel laden → `init-premount` läuft bis Completion → USB-Medium erkannt (`/dev/sda2`)
- Dannach: `mmc0: Timeout waiting for hardware cmd interrupt` Schleife
- `SDHCI REGISTER DUMP` erscheint wiederholt
- Boot hängt, erreicht niemals Netzwerk-TUI
- Keine Log-Persistierung auf Stick (weil Boot vorher steckenbleibt)

**Root Cause:** 
- SDHCI/MMC-Kontroller-Hardware auf Lenovo B50-45 verursacht Interrupt-Timeout im Kernel
- `mmc_core.use_spi_crc=N` Parameter unterdrückt nur CRC-Fehler, NICHT Interrupt-Handler-Timeouts
- Der Kernel versucht mmc0-Device zu initialisieren und hängt in der Interrupt-Abarbeitung

**Fix (Commit 3b47fd8):**
- BEIDE Blacklist-Syntaxen zu Safe- und Legacy-Boot-Modi hinzufügen:
  - `module_blacklist=sdhci,sdhci_pci,sdhci_acpi` (initramfs-Syntax)
  - `rd.driver.blacklist=sdhci,sdhci_pci,sdhci_acpi` (kernel/dracut-Syntax)
- Nur für Safe/Legacy Modi, nicht für Runtime-Eintrag (dort bleibt `mmc_core.use_spi_crc=N` für breitere Kompatibilität)
- Damit wird das SDHCI-Modul komplett deaktiviert, bevor der Kernel die Interrupt-Handler initialisiert

**Nächste Schritte:**
1. Payload neu bauen auf srv1 mit Commit 3b47fd8
2. USB-Stick neu schreiben
3. Auf Lenovo B50-45: "Safe Mode / AMD compat" Boot-Eintrag versuchen
4. Logs nach erfolgreichem Boot-up prüfen
