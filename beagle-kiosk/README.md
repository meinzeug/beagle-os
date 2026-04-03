# Beagle OS Gaming Kiosk

`beagle-kiosk` is the closed-source gaming surface for `Beagle OS Gaming`.

This public repository intentionally does **not** contain the Electron source code. The actual kiosk source lives in a separate private repository and is shipped only as a compiled Linux binary through GitHub Releases.

What this public directory contains:

- `README.md`: public module description
- `INSTALL.sh`: installer that downloads the compiled binary, verifies its SHA256 against `https://beagle-os.com/kiosk-release-hash.txt`, installs it into `/opt/beagle-kiosk/`, and wires up the required systemd units

The kiosk architecture stays fixed:

- `Beagle OS Gaming` boots into the kiosk
- `Beagle OS Desktop` keeps the normal desktop runtime
- The kiosk has a `Meine Bibliothek` mode and a `Spielekatalog` mode
- GeForce NOW is launched by the kiosk as a child process and returns to the kiosk when it exits
- Affiliate identifiers are fetched from `beagle-os.com` and held only in RAM
