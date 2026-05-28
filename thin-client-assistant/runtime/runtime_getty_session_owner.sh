#!/usr/bin/env bash
set -euo pipefail

SYSTEMCTL_BIN="${BEAGLE_SYSTEMCTL_BIN:-systemctl}"
BOOT_MODE_BIN="${BEAGLE_BOOT_MODE_BIN:-/usr/local/bin/pve-thin-client-boot-mode}"
GETTY_UNIT="${PVE_THIN_CLIENT_RUNTIME_GETTY_UNIT:-getty@tty1.service}"
LOGGER_TAG="${PVE_THIN_CLIENT_RUNTIME_LOGGER_TAG:-beagle-runtime}"

log_event() {
  if command -v logger >/dev/null 2>&1; then
    logger -t "$LOGGER_TAG" "phase=runtime-session-owner $*"
  fi
}

boot_mode="$($BOOT_MODE_BIN 2>/dev/null || printf 'runtime')"
if [[ "$boot_mode" != "runtime" ]]; then
  log_event "state=skip mode=${boot_mode}"
  exit 0
fi

if ! command -v "$SYSTEMCTL_BIN" >/dev/null 2>&1; then
  log_event "state=error reason=systemctl-missing"
  exit 1
fi

if ! "$SYSTEMCTL_BIN" cat "$GETTY_UNIT" >/dev/null 2>&1; then
  log_event "state=error reason=getty-unit-missing unit=${GETTY_UNIT}"
  exit 1
fi

"$SYSTEMCTL_BIN" unmask "$GETTY_UNIT" >/dev/null 2>&1 || true
"$SYSTEMCTL_BIN" enable "$GETTY_UNIT" >/dev/null 2>&1 || true

if "$SYSTEMCTL_BIN" is-active --quiet "$GETTY_UNIT"; then
  "$SYSTEMCTL_BIN" restart --no-block "$GETTY_UNIT"
else
  "$SYSTEMCTL_BIN" start --no-block "$GETTY_UNIT"
fi

log_event "state=active unit=${GETTY_UNIT} mode=${boot_mode}"