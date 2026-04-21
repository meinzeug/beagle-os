# 06 — Server-Installer / Bare-Metal ISO

Stand: 2026-04-20  
Priorität: Welle 6.x (Mai 2026)  
Betroffene Verzeichnisse: `server-installer/`, `scripts/build-server-installer.sh`

---

## Hintergrund

`server-installer/` enthält die Live-Build-Definition für das Beagle Server OS
Installer-ISO. Ziel ist ein ISO das Beagle OS standalone installiert: Debian-Basis,
KVM/QEMU, libvirt, beagle-host-services, nginx, noVNC-Proxy. Keine Proxmox-Option.
Proxmox wird dauerhaft entfernt — es gibt keine "Beagle OS with Proxmox"-Variante mehr.

---

## Schritte

### Schritt 1 — Installer-Ablauf dokumentieren und verifizieren

- [ ] `server-installer/live-build/config/includes.chroot/usr/local/bin/beagle-server-installer` vollständig lesen.
- [ ] Flowchart des aktuellen Installer-Ablaufs in `docs/gofuture/06-server-installer.md` als ASCII-Diagramm ergänzen.

Bevor der Installer weiterentwickelt wird muss der aktuelle Ablauf vollständig
dokumentiert sein. Das verhindert dass Änderungen unerwartete Zweige brechen.
Der interaktive Installer verwendet Dialoge für Festplattenauswahl, Netzwerk-
Konfiguration und Hostname-Eingabe. Jeder Dialog-Schritt und seine Abhängigkeit
zum nächsten Schritt muss im Flowchart sichtbar sein. Nach der Dokumentation wird
der Installer auf einer Test-VM (QEMU/KVM) manuell durchgeführt und das Ergebnis
protokolliert. Breakpoints und Fehlerzustände werden für jeden Schritt notiert.

---

### Schritt 2 — Installer auf reinen Beagle-OS-standalone-Modus fokussieren

- [ ] Installer auf Beagle OS standalone (libvirt/KVM) fokussieren — kein Proxmox-Zweig.
- [ ] Installer installiert: Debian base, KVM/QEMU, libvirt, beagle-host-services, nginx, noVNC-Proxy.

Da Proxmox dauerhaft entfernt wird gibt es keinen Installer-Zweig mehr der zwischen
Standalone und Proxmox wählt. Der Installer hat genau einen Pfad: Beagle OS standalone.
Das vereinfacht den Dialog-Fluss erheblich — es entfällt die frühe Modus-Entscheidung.
Der Installer-Code für den Proxmox-Zweig wird vollständig entfernt, nicht auskommentiert.
Gemeinsamkeiten (Netzwerk-Setup, Disk-Partitionierung, beagle-user-Anlage) bleiben als
geteilte Shell-Funktionen erhalten. Nach dem Schritt muss ein frischer Install auf
einer Test-VM ohne Proxmox-Abhängigkeiten abschließen.

---

### Schritt 3 — Reproducible Builds sicherstellen

- [ ] `scripts/build-server-installer.sh` so gestalten dass es auf einem frischen Debian-System aus dem Repo heraus reproduzierbar läuft.
- [ ] Alle Abhängigkeiten dokumentiert in einem `Makefile` oder `build.env`.

Ein ISO-Build der nur auf dem Rechner des Maintainers funktioniert ist kein
reproduzierbarer Build. Das Live-Build-System (Debian `live-build`) ist deterministisch
wenn Package-Pins und Mirror-URLs fix gesetzt sind. Die Build-Voraussetzungen
(benötigte Pakete, Debian-Version des Build-Hosts) werden als Kommentar im
Build-Skript und in `docs/` festgehalten. Der CI/CD-Pfad (GitHub Actions oder
ähnlich) soll den Build-Schritt ausführen können ohne manuelle Vorbereitung.

---

### Schritt 4 — Post-Install Beagle-Bootstrap einheitlich machen

- [ ] Post-Install-Skript `scripts/install-beagle-host.sh` mit dem Installer-Post-Install-Hook vereinheitlichen.
- [ ] Dopplungen zwischen Installer und nachträglicher Installation eliminieren.

Aktuell gibt es einen Installer-Pfad und einen nachträglichen Installations-Pfad
(`scripts/install-beagle-host.sh`). Beide führen ähnliche Schritte aus aber nicht
identisch. Durch Extraktion gemeinsamer Funktionen in ein Shared-Bootstrap-Skript
wird sichergestellt dass ein Installer-installed System und ein manuell installiertes
System identisch konfiguriert sind. Das vereinfacht Support und Fehlerbehebung.
Der gemeinsame Bootstrap-Code wird idempotent geschrieben sodass mehrfaches
Ausführen das System nicht in einen inkonsistenten Zustand bringt.

---

### Schritt 5 — ISO-Signing und Release-Artefakt-Chain

- [ ] ISO-Signierung mit GPG in `scripts/create-github-release.sh` integrieren.
- [ ] Checksum-Datei (SHA256) und Signatur-Datei als Release-Asset publizieren.

Ein unsigned ISO ist für sicherheitsbewusste Betreiber inakzeptabel. GPG-Signierung
stellt sicher dass das ISO aus einer vertrauenswürdigen Quelle stammt und nicht
manipuliert wurde. Die Signierung findet auf dem Release-Build-Host statt mit dem
offiziellen Beagle-Signing-Key. Der Public Key wird im Repo und auf `beagle-os.com`
publiziert. Nutzer können nach dem Download die Signatur via `gpg --verify` prüfen.
Checksum + Signatur werden als separate Release-Assets auf GitHub hochgeladen.

---

## Testpflicht nach Abschluss

- [ ] ISO bootet in QEMU-VM, Installer-Dialog erscheint.
- [ ] Installation schließt ohne Proxmox-Abhängigkeiten ab.
- [ ] Post-Install: `systemctl is-active beagle-control-plane` → active.
- [ ] ISO-Checksum und Signatur korrekt verifizierbar.
