#!/usr/bin/env bash

INSTALLER_DEFAULTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLER_ENV_DEFAULTS_JSON="${INSTALLER_ENV_DEFAULTS_JSON:-$INSTALLER_DEFAULTS_DIR/env-defaults.json}"

apply_installer_env_defaults() {
  local defaults_file="${1:-$INSTALLER_ENV_DEFAULTS_JSON}"
  [[ -r "$defaults_file" ]] || return 1

  while IFS=$'\t' read -r key value; do
    [[ "$key" =~ ^[A-Z0-9_]+$ ]] || continue
    if [[ -z "${!key:-}" ]]; then
      printf -v "$key" '%s' "$value"
    fi
  done < <(
    python3 - "$defaults_file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
for key, value in payload.items():
    print(f"{key}\t{value}")
PY
  )
}
