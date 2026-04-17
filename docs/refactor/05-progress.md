# Beagle OS Refactor - Progress

Stand: 2026-04-16

## Update 2026-04-17 (Local E2E Reinstall + Provisioning Hardening)
- Voller lokaler Reinstall-Loop aufgesetzt: beagleserver aus aktueller Server-ISO neu installiert, Host/API/UI wieder hochgefahren, Desktop-VM 101 ueber echte API-Provisioning-Calls angelegt, VM-spezifisches Installer-Skript geladen, beaglethinclient via simuliertem USB neu installiert.
- Reproduzierbare Installer-/Host-Blocker im Repo gefixt:
	- `scripts/install-beagle-host-services.sh`: distro-kompatible QEMU-Paketaufloesung (`qemu-kvm`/`qemu-system-x86`/`qemu-system`), `xorriso` in Standalone-Abhaengigkeiten, Runtime-Readiness nur bei vorhandenem `virsh`+`qemu-img`+`xorriso`.
	- `scripts/install-beagle-proxy.sh`: API-Proxy-Timeouts auf 900s erhoeht, damit lange Provisioning-Requests nicht mit 504 abbrechen.
	- `scripts/install-beagle-host.sh`: zusaetzliche Release-Artefakte (`pve-thin-client-live-usb*.sh`, `pve-thin-client-usb-installer*.ps1`) werden jetzt mitgeladen; VM-spezifische Wrapper-Endpunkte liefern dadurch wieder verwertbare Skripte.
- Sichtbare Endpunkt-Seite nach Reinstall verifiziert: beaglethinclient bootet in die installierte Beagle-Runtime (GFN-Kiosk-UI sichtbar).

## Offener Gap nach heutigem Lauf
- Finales Ziel "sichtbarer Desktop-Stream von neuer VM auf Thinclient" ist noch nicht abgeschlossen.
- VM 101 wurde ueber den public finalize callback auf `status=completed`, `phase=complete` gebracht; der alte `installing/autoinstall` Drift ist damit fuer den Provisioning-State aufgeloest.
- Gleichzeitig bleibt ein Runtime-Drift bestehen: API-Profil meldet VM 101 als `running`, waehrend `virsh` auf dem Host zwischenzeitlich `shut off` zeigte und die VM manuell gestartet werden musste.
- `installer-prep` bleibt bei VM 101 im Schritt `install` haengen; persistierte Fehlerursache ist `Unable to determine guest IPv4 address for VM 101`.
- Stream-Endpunkte fuer VM 101 sind weiterhin nicht erreichbar (`50032/50033/50053` timeout), und Profilfelder fuer Sunshine-Credentials sind weiterhin leer.
- Damit ist die Installer-/Reinstall-Kette reproduzierbar stabilisiert, der letzte Stream-Readiness-Fix bleibt als naechster Schritt offen.

## Update 2026-04-17 (USB Installer / Live Script Credential-Pfad)
- VM-spezifische USB-Installer-/Live-Script-Generierung im Host gehaertet: Moonlight-Presets enthalten Sunshine-Credentials jetzt robust aus VM-Metadaten/Secret-Fallback.
- Neue Guardrail im Host-Generator: Wenn ein Moonlight-Target gesetzt ist, aber Sunshine `username/password/pin` fehlen, wird die Script-Generierung mit klarer Fehlermeldung abgebrochen (kein stilles Ausliefern unvollstaendiger Presets mehr).
- Zielwirkung: Beim Download von `installer.sh` und `live-usb.sh` fuer eine VM werden die Auto-Pairing-Credentials konsistent in den USB-Preset uebergeben.
- Technische Verifikation lokal:
	- Python-Syntaxcheck fuer `beagle-host/services/installer_script.py` erfolgreich.
	- Fokus-Test per Python-Stub: Preset enthaelt Sunshine-Credentials; Missing-Credentials-Fall wirft erwartetes `ValueError`.

## Erledigt in diesem Run (VM106 Provisioning + Stream-Pfad)
- VM106 neu aufgesetzt und Beagle-Provisioning erneut end-to-end gestartet (`POST /api/v1/provisioning/vms`, `vmid=106`).
- Autoinstall-Blocker behoben: `qemu-guest-agent` wurde aus der fruehen curtin-`packages`-Phase entfernt (Install bricht nicht mehr an `exit status 100` ab).
- Host-Service-Installer erweitert: Ubuntu-Template-Dateien werden jetzt mit deployed (`beagle-host/templates/ubuntu-beagle/*`).
- `BEAGLE_PUBLIC_STREAM_HOST` wird im Host-Service-Setup auf eine routbare IPv4 gesetzt (statt impliziter Loopback-Aufloesung).
- Control-Plane-Systemd-Unit auf beagleserver mit libvirt-Schreibpfaden aktualisiert (`ReadWritePaths` inkl. `/var/lib/libvirt/images`, `/var/lib/libvirt/qemu`) zur Behebung von `Read-only file system` im Provisioning.
- USB-Tunnel-Secret-Write-Flow gehaertet: Pfad-Besitz initial root-basiert und kein automatisches Zurueck-`chown` in `vm_secret_bootstrap`, damit der gehaertete Service ohne `CAP_DAC_OVERRIDE` schreiben kann.
- API-Bugfix: `GET /api/v1/vms/<vmid>` in `vm_http_surface` robust ueber Regex geparst (kein falsches `invalid vmid` mehr fuer VM106).
- VM106 erreichte den erwarteten Lifecycle-Schritt `Shutdown Finished after guest request` (Autoinstall-Poweroff), danach wurde der Callback-Pfad manuell aufgerufen (`prepare-firstboot`, `complete?restart=0`), Status wechselte auf `completed`.

## Verifikation
- Frischer Provisioning-Run fuer VM106: `public_stream.host=192.168.122.130`, `moonlight_port=50192`, `sunshine_api_url=https://192.168.122.130:50193`.
- Serielle Ausgabe zeigte Fortschritt bis `installing kernel`; Lifecycle-Event bestaetigte anschliessend Guest-initiierten Shutdown.
- Nach API-Bugfix liefert `GET /api/v1/vms/106` ein valides Profil statt `invalid vmid`.
- `GET /api/v1/vms/106/installer-prep` ist aktiv und laeuft in den `install`-Schritt, meldet aktuell aber noch fehlende Guest-IP/Sunshine-Readiness.

## Aktueller technischer Status
- VM `beagle-104`: stopped.
- VM `beagle-105`: stopped.
- VM `beagle-106`: Provisioning-State `completed` nach manuellem Callback-Finalize; Sunshine-Readiness noch nicht final gruen.

## Offener Blocker
- beagleserver-Managementzugriff ist momentan instabil: ICMP erreichbar, aber `22/443` liefern `connection refused`.
- Dadurch koennen Host-seitige Nachtests (Control-Plane/SSH/Nginx), finale Sunshine-Checks in VM106 und Thinclient-E2E aktuell nicht verifiziert werden.
