<!-- Beagle OS Gaming Kiosk - (c) Dennis Wicht / meinzeug - MIT Licensed -->
# Beagle OS Gaming Kiosk Setup

## Overview

The kiosk is now maintained directly inside `meinzeug/beagle-os`.

It can be:

- built locally for development
- packaged on `srv.thinover.net` for release
- installed onto Beagle Gaming endpoints through `beagle-kiosk-install`

## Development

```bash
cd beagle-kiosk
npm install
npm start
```

The renderer expects a runtime install root at `/opt/beagle-kiosk` by default. For local testing you can override:

```bash
BEAGLE_KIOSK_ROOT=/tmp/beagle-kiosk-test npm start
```

## Build and Release

```bash
cd beagle-kiosk
npm install
npm run dist
npm run release-metadata -- dist/beagle-kiosk-vX.Y.Z-linux-x64.AppImage https://github.com/meinzeug/beagle-os/releases/download/<tag>/beagle-kiosk-vX.Y.Z-linux-x64.AppImage
```

Publish these files with the matching Beagle release:

- `dist/beagle-kiosk-vX.Y.Z-linux-x64.AppImage`
- `dist/kiosk-release.json`
- `dist/kiosk-release-hash.txt`

## Catalog Data

`update_catalog.py` builds `games.json` from:

- the official NVIDIA GeForce NOW supported-games feed
- Green Man Gaming storefront lookups and search results

The updater is designed to keep the catalog usable even if some external lookups fail. Existing prices and URLs should remain stable when the upstream search path is incomplete.

## Device Layout

Install path on endpoints:

- `/opt/beagle-kiosk/beagle-kiosk`
- `/opt/beagle-kiosk/kiosk.conf`
- `/opt/beagle-kiosk/games.json`
- `/opt/beagle-kiosk/user_library.json`
- `/opt/beagle-kiosk/update_catalog.py`
- `/opt/beagle-kiosk/assets/`
- `/opt/beagle-kiosk/logs/`

## Services

The kiosk ships with:

- `beagle-kiosk.service`
- `beagle-kiosk.target`
- `beagle-kiosk-update-catalog.service`
- `beagle-kiosk-update-catalog.timer`

## Notes

- Store URLs are opened directly without affiliate parameters.
- The kiosk source tree is public and versioned together with the rest of Beagle OS.
- Heavy release builds belong on `srv.thinover.net`, not on the local workstation.
