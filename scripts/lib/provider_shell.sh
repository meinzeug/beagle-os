#!/usr/bin/env bash

beagle_provider_target_is_local() {
  local target="${PROXMOX_HOST:-${BEAGLE_PROVIDER_HOST:-}}"
  case "$target" in
    ""|localhost|127.0.0.1|::1|"$(hostname)"|"$(hostname -f 2>/dev/null || hostname)")
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

beagle_provider_ssh_host() {
  local target="${PROXMOX_HOST:-${BEAGLE_PROVIDER_HOST:-}}"
  if beagle_provider_target_is_local; then
    bash -lc "$*"
    return 0
  fi
  ssh "$target" "$@"
}

beagle_provider_module_path_for_target() {
  if beagle_provider_target_is_local; then
    if [[ -n "${LOCAL_PROVIDER_MODULE_PATH:-}" ]]; then
      printf '%s\n' "$LOCAL_PROVIDER_MODULE_PATH"
      return 0
    fi
    printf '%s\n' "${PROVIDER_MODULE_PATH:-}"
    return 0
  fi
  if [[ -n "${REMOTE_PROVIDER_MODULE_PATH:-}" ]]; then
    printf '%s\n' "$REMOTE_PROVIDER_MODULE_PATH"
    return 0
  fi
  printf '%s\n' "${PROVIDER_MODULE_PATH:-}"
}

beagle_provider_helper_available() {
  if [[ "${PROVIDER_HELPER_AVAILABLE_CACHE:-}" == "1" ]]; then
    return 0
  fi
  if [[ "${PROVIDER_HELPER_AVAILABLE_CACHE:-}" == "0" ]]; then
    return 1
  fi
  local module_path
  module_path="$(beagle_provider_module_path_for_target)"
  if [[ -n "$module_path" ]] && beagle_provider_ssh_host "test -f '$module_path'"; then
    PROVIDER_HELPER_AVAILABLE_CACHE="1"
    return 0
  fi
  PROVIDER_HELPER_AVAILABLE_CACHE="0"
  return 1
}

beagle_provider_helper_exec() {
  local module_path
  module_path="$(beagle_provider_module_path_for_target)"
  local shell_command
  shell_command="$(printf '%q ' python3 "$module_path" "$@")"
  beagle_provider_ssh_host "${shell_command% }"
}

beagle_json_last_object() {
  python3 - "${1:-}" <<'PY'
import json
import sys

raw = sys.argv[1]
payload = {}
for line in reversed([line.strip() for line in raw.splitlines() if line.strip()]):
    try:
        payload = json.loads(line)
        break
    except json.JSONDecodeError:
        continue
print(json.dumps(payload))
PY
}
