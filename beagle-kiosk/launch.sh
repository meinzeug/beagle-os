#!/usr/bin/env bash
# Beagle OS Gaming Kiosk - MIT Licensed
set -euo pipefail

INSTALL_ROOT="${BEAGLE_KIOSK_ROOT:-/opt/beagle-kiosk}"
BIN_PATH="${INSTALL_ROOT}/beagle-kiosk"
LOG_DIR="${INSTALL_ROOT}/logs"
LOG_FILE="${LOG_DIR}/kiosk.log"

mkdir -p "$LOG_DIR"

export ELECTRON_DISABLE_SECURITY_WARNINGS=1
export BEAGLE_KIOSK_ROOT="$INSTALL_ROOT"

exec "$BIN_PATH" >>"$LOG_FILE" 2>&1
