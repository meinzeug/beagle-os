# Beagle OS Refactor - Global TODO

Stand: 2026-04-16

## Update 2026-04-17
- [x] VM-spezifische USB-Installer-/Live-Script-Generierung auf Sunshine Auto-Pair Credentials gehaertet (Moonlight-Preset verlangt username/password/pin)
- [ ] Hostseitiger Download-Negativtest dokumentieren (fehlende Sunshine-Credentials muessen Script-Generierung blockieren)
- [x] Standalone-Host-Install gegen distro-spezifische QEMU-Paketnamen gehaertet (`qemu-kvm`/`qemu-system-x86`/`qemu-system`)
- [x] Standalone-Host-Provisioning um `xorriso` als Pflicht-Dependency und Readiness-Kriterium erweitert
- [x] API-Reverse-Proxy-Timeout fuer Long-Running Provisioning-Flows auf 900s erhoeht
- [x] Host-Artifact-Download um fehlende generische Thinclient-Installer-Artefakte erweitert
- [~] Lokaler End-to-End Reinstall-Loop (Server -> VM-Provisioning -> Thinclient-Reinstall) erfolgreich bis sichtbare Thinclient-Runtime; finaler Desktop-Stream-Nachweis noch offen

## P1 - Beagle Provider / Ubuntu Provisioning
- [~] libvirt-backed VM create/start fuer Beagle-Provider (VM106 mehrfach reproduzierbar erzeugt; Host-Recovery und finale Readiness-Checks offen)
- [x] Start-Blocker `qemu could not open kernel file` behoben
- [x] Kernel/Initrd-Extract in lokales ISO-Storage verschoben (`/var/lib/libvirt/images/beagle-extracted/...`)
- [x] API-Route `GET /api/v1/vms/<vmid>` Parser-Bug (`invalid vmid`) behoben
- [x] Autoinstall-Curtin-Failure (`qemu-guest-agent` Exit 100) in Seed-Template entschaerft
- [x] Control-Plane-Unit fuer libvirt-Writepaths gehaertet (ReadWritePaths erweitert)
- [x] USB-Tunnel-Secret-Write Rechteproblem im gehaerteten Servicepfad behoben
- [~] Finalize-Flow nach Install verifiziert (manueller Callback fuer VM106 erfolgreich, stabile Endverifikation noch offen)

## P1 - Streaming Zielpfad
- [~] VM106 Stream-Metadaten auf routbaren Host umgestellt (`192.168.122.130:50192/50193`)
- [~] VM-Downloadskripte uebergeben Sunshine Auto-Pair Credentials robust; Full E2E nach Server-Reinstall noch offen
- [ ] Sunshine in VM106 final `ready=true` verifizieren
- [ ] Thin-Client E2E-Stream VM106 nachweisen
- [ ] VM101 Provisioning-State-Drift (`running` vs `installing/autoinstall`) beheben und auf konsistent `completed/ready` bringen
- [ ] VM101 Stream-Ports (`50032/50033/50053`) und Sunshine-Credentials im Profil konsistent verifizieren

## P1 - Native Virtualization Runtime
- [~] beagle provider contract aktiv, `guest_exec`/`guest_exec_status` fuer echte readiness-Reads weiter ausbauen
- [ ] beagle compute/storage/network service baseline weiter ausarbeiten

## P1 - Installer & Host Modes
- [~] standalone/with-proxmox Pfade ueber gemeinsamen Bootstrap aktiv, Testmatrix weiter automatisieren
- [ ] Reproduzierbarer Reinstall-Loop inkl. Smoke-Checks
- [ ] Thinclient-VM Storage/I/O-Fehler beheben (`beaglethinclient` pausiert)

## P0/P2 Sammelthemen
- [ ] beagleserver Management-Recovery (SSH/HTTPS refused) stabilisieren und Ursache dokumentieren
- [ ] Security-E2E fuer Trusted-Origin/Hash-Token/Absolute-Target Policies finalisieren
- [ ] API contract tests und role-matrix integration tests erweitern
- [ ] CI-nahe Smoke-E2E fuer kritische Flows ausbauen
