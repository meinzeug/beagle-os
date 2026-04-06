#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALLER="$ROOT_DIR/beagle-os/overlay/usr/local/sbin/beagle-kiosk-install"

if [[ ! -x "$INSTALLER" ]]; then
  echo "Missing installer entrypoint: $INSTALLER" >&2
  exit 1
fi

exec "$INSTALLER" "$@"
