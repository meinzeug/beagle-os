# PXE Deployment

Stand: 2026-04-27

## Ziel

Ein bestehender Beagle-Node stellt den Server-Installer per `dnsmasq` + TFTP bereit. Neue Hosts booten den Installer direkt aus dem Netz. Eine optionale Seed-URL wird in den Boot-Eintrag gerendert, damit der Installer ohne Dialog startet.

## Voraussetzungen

- vorhandener Beagle-Host mit Root-Zugriff
- `xorriso`
- `grub-efi-amd64-bin`
- optional `syslinux-common` fuer BIOS-PXE
- gebautes Installer-ISO unter `dist/beagle-os-server-installer/beagle-os-server-installer.iso`

## Setup

```bash
BEAGLE_PXE_INTERFACE=enp1s0 \
BEAGLE_PXE_DHCP_RANGE=10.40.0.100,10.40.0.180,255.255.255.0,12h \
BEAGLE_PXE_SEED_URL=https://srv1.beagle-os.com/seeds/rack-a.yaml \
./scripts/setup-pxe-server.sh
```

Das Script:

- extrahiert `/live/vmlinuz` und `/live/initrd` aus dem Installer-ISO
- legt Boot-Artefakte unter `/var/lib/beagle/pxe/tftp/` ab
- erzeugt `grubnetx64.efi` fuer UEFI-PXE
- legt bei vorhandenen Syslinux-Artefakten auch BIOS-PXE-Dateien ab
- schreibt `/etc/dnsmasq.d/beagle-pxe.conf`
- startet `dnsmasq` neu

## Ergebnis

Wichtige Pfade:

- TFTP-Root: `/var/lib/beagle/pxe/tftp`
- Boot-Eintrag: `/var/lib/beagle/pxe/tftp/beagle-installer/grub/grub.cfg`
- dnsmasq-Config: `/etc/dnsmasq.d/beagle-pxe.conf`

Wenn `BEAGLE_PXE_SEED_URL` gesetzt ist, enthaelt der Boot-Eintrag automatisch:

```text
beagle.seed_url=https://...
```

Der Installer laedt die Seed-Datei dann vor dem UI und fuehrt den Zero-Touch-Install ohne Dialog aus.

## Verifikation

Lokal:

```bash
bash tests/integration/test_pxe_boot.sh
```

Auf dem PXE-Host:

```bash
systemctl status dnsmasq
ls -lah /var/lib/beagle/pxe/tftp/beagle-installer
```

Vom zweiten Host im selben PXE-Netz:

```bash
curl -I http://<pxe-host>/seeds/rack-a.yaml
```

## Hinweise

- Der aktuelle Zero-Touch-Pfad unterstuetzt nur `raid: 0`. Mehrdisk-RAID bleibt ein separater Installer-Block.
- UEFI-PXE ist der Primärpfad. BIOS-PXE wird nur aktiviert, wenn `lpxelinux.0` und `ldlinux.c32` lokal vorhanden sind.
