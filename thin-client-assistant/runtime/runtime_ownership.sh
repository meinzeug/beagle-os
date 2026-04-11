#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_FS_OWNERSHIP_SH="${RUNTIME_FS_OWNERSHIP_SH:-$SCRIPT_DIR/runtime_fs_ownership.sh}"
GEFORCENOW_STORAGE_ENVIRONMENT_SH="${GEFORCENOW_STORAGE_ENVIRONMENT_SH:-$SCRIPT_DIR/geforcenow_storage_environment.sh}"

# shellcheck disable=SC1090
source "$RUNTIME_FS_OWNERSHIP_SH"
# shellcheck disable=SC1090
source "$GEFORCENOW_STORAGE_ENVIRONMENT_SH"
