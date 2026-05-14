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
| `pending` | `live-media=removable` entfernt; `live-media-path + ignore_uuid` fuer robusten Medium-Scan |

---

## Lenovo B50-45 BIOS-Spezifika

- **InsydeH20 Setup Utility A1CN24WW V1.12**
- Boot-Menü-Taste: **F12** beim POST
- Legacy-Modus: USB-Stick benötigt hybrid MBR mit aktivem (`0x80`) FAT32-LBA (`0x0C`) MBR-Eintrag
- UEFI-Modus: benötigt `EFI/BOOT/BOOTX64.EFI` (liegt vor), `EFI/BOOT/grub.cfg` ohne hartkodierte Disk-Hints
- AMD A6-6310 (Kabini/Jaguar): kritische Kernel-Parameter: `amd_iommu=off`, `nomodeset irqpoll noapic nolapic` für Fallback
- USB 3.0 Ports haben bekannte xHCI-Handoff-Bugs in diesem BIOS-Stand → USB 2.0 Port bevorzugen

---

## Offener Stand (2026-05-13)

- [ ] Rebuild mit frischer Payload von srv1 durchführen
- [ ] Stick neu schreiben (nicht nur grub.cfg patchen)
- [ ] Boot-Test auf Lenovo B50-45 mit frischem Stick
- [ ] Frühboot-Log `/beagle-boot-early.log` nach Boot auslesen
- [ ] Falls Phase-3-Hänger weiterhin: qemu-Simulation auf srv1 mit seriellem Output
