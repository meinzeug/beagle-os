<!-- Beagle OS Gaming Kiosk - MIT Licensed -->
# Beagle OS Gaming Kiosk

Open-source Electron kiosk for `Beagle OS Gaming`.

## Components

- `main.js`
  Electron main process, GeForce NOW process control, catalog refresh IPC, and secure store-window handling.
- `preload.js`
  Renderer bridge for the kiosk UI.
- `renderer/`
  Library view, catalog view, search, filters, pagination, and modal flows.
- `update_catalog.py`
  Catalog builder based on the official NVIDIA GeForce NOW game list plus Green Man Gaming storefront matching.
- `kiosk.conf.example`
  Runtime configuration template.
- `systemd/`
  Service and timer templates for kiosk boot and catalog refresh.
- `launch.sh`
  AppImage launcher wrapper.

## Build

```bash
cd beagle-kiosk
npm install
npm run dist
npm run release-metadata -- dist/beagle-kiosk-vX.Y.Z-linux-x64.AppImage https://beagle-os.com/beagle-updates/beagle-kiosk-vX.Y.Z-linux-x64.AppImage
```

The release build produces:

- the kiosk AppImage
- `dist/kiosk-release.json`
- `dist/kiosk-release-hash.txt`

## Runtime Model

- `Meine Bibliothek`
  Reads the cached GeForce NOW library state from `user_library.json` and exposes direct `Jetzt spielen`.
- `Spielekatalog`
  Builds a GFN-compatible catalog from live source data, opens store links directly, and supports manual refresh.
- `GeForce NOW`
  Runs as a child process launched by the kiosk. The kiosk closes or hides during streaming and returns when GFN exits.

## Installation

For repository-based installation on a running system:

```bash
sudo ./beagle-kiosk/INSTALL.sh
```

For endpoint images and fresh Gaming boots, the canonical runtime installer remains:

- [`beagle-os/overlay/usr/local/sbin/beagle-kiosk-install`](../beagle-os/overlay/usr/local/sbin/beagle-kiosk-install)

## License

This module is part of the repository-wide MIT license.
