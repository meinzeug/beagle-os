#!/usr/bin/env bash

SCRIPT_DIR="${RUNTIME_SCRIPT_DIR:-/usr/local/lib/pve-thin-client/runtime}"
RUNTIME_NETWORK_WAIT_SH="${RUNTIME_NETWORK_WAIT_SH:-$SCRIPT_DIR/runtime_network_wait.sh}"
RUNTIME_NETWORK_IDENTITY_SH="${RUNTIME_NETWORK_IDENTITY_SH:-$SCRIPT_DIR/runtime_network_identity.sh}"
# shellcheck disable=SC1090
source "$RUNTIME_NETWORK_WAIT_SH"
# shellcheck disable=SC1090
source "$RUNTIME_NETWORK_IDENTITY_SH"

runtime_network_wait_timeout() {
  printf '%s\n' "${PVE_THIN_CLIENT_NETWORK_WAIT_TIMEOUT:-20}"
}

runtime_getent_bin() {
  printf '%s\n' "${BEAGLE_GETENT_BIN:-getent}"
}
