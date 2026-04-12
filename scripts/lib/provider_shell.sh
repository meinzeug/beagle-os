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

beagle_provider_guest_exec_sync_bash() {
  local vmid="$1"
  local command="$2"
  local timeout_seconds="${3:-}"
  local raw_output payload_json pid status_raw status_json exitcode command_b64

  if beagle_provider_helper_available; then
    command_b64="$(printf '%s' "$command" | base64 -w0)"
    if [[ -n "$timeout_seconds" ]]; then
      raw_output="$(beagle_provider_helper_exec guest-exec-bash-sync-b64 "$vmid" "$command_b64" "$timeout_seconds")"
    else
      raw_output="$(beagle_provider_helper_exec guest-exec-bash-sync-b64 "$vmid" "$command_b64")"
    fi
    status_json="$(beagle_json_last_object "$raw_output")"
  else
    raw_output="$(beagle_provider_ssh_host "sudo /usr/sbin/qm guest exec '$vmid' -- bash -lc $(printf '%q' "$command")")"
    payload_json="$(beagle_json_last_object "$raw_output")"

    pid="$(python3 - "$payload_json" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1] or "{}")
pid = payload.get("pid")
print("" if pid is None else str(pid))
PY
)"

    if [[ -z "$pid" ]]; then
      status_json="$payload_json"
    else
      while true; do
        sleep 2
        status_raw="$(beagle_provider_ssh_host "sudo /usr/sbin/qm guest exec-status '$vmid' '$pid'")"
        status_json="$(beagle_json_last_object "$status_raw")"
        if python3 - "$status_json" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1] or "{}")
raise SystemExit(0 if payload.get("exited") else 1)
PY
        then
          break
        fi
      done
    fi
  fi

  exitcode="$(python3 - "$status_json" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1] or "{}")
print(int(payload.get("exitcode", 0) or 0))
PY
)"
  if [[ "$exitcode" != "0" ]]; then
    python3 - "$status_json" <<'PY' >&2
import json
import sys

payload = json.loads(sys.argv[1] or "{}")
stdout = str(payload.get("out-data", "") or "").strip()
stderr = str(payload.get("err-data", "") or "").strip()
if stdout:
    print(stdout)
if stderr:
    print(stderr, file=sys.stderr)
PY
    return 1
  fi

  printf '%s\n' "$status_json"
}

beagle_provider_guest_ipv4() {
  local vmid="$1"
  local raw_output=""

  if beagle_provider_helper_available; then
    beagle_provider_helper_exec guest-ipv4 "$vmid"
    return 0
  fi

  raw_output="$(beagle_provider_ssh_host "sudo /usr/sbin/qm guest cmd '$vmid' network-get-interfaces" 2>/dev/null || true)"
  python3 - "$raw_output" <<'PY'
import json
import sys

raw = sys.argv[1].strip()
if not raw:
    raise SystemExit(1)

try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    raise SystemExit(1)

for iface in payload if isinstance(payload, list) else []:
    for address in iface.get("ip-addresses", []):
        ip = str(address.get("ip-address", "")).strip()
        if address.get("ip-address-type") != "ipv4":
            continue
        if not ip or ip.startswith("127.") or ip.startswith("169.254."):
            continue
        print(ip)
        raise SystemExit(0)

raise SystemExit(1)
PY
}

beagle_provider_vm_description() {
  local vmid="$1"

  if beagle_provider_helper_available; then
    beagle_provider_helper_exec vm-description "$vmid"
    return 0
  fi

  beagle_provider_ssh_host "sudo /usr/sbin/qm config '$vmid'" | sed -n 's/^description: //p'
}

beagle_provider_set_vm_description_b64() {
  local vmid="$1"
  local description_b64="$2"

  if beagle_provider_helper_available; then
    beagle_provider_helper_exec set-vm-description-b64 "$vmid" "$description_b64" >/dev/null
    return 0
  fi

  beagle_provider_ssh_host "python3 - '$vmid' '$description_b64' <<'PY'
import base64
import subprocess
import sys

vmid = sys.argv[1]
desc = base64.b64decode(sys.argv[2]).decode('utf-8')
subprocess.run(['sudo', '/usr/sbin/qm', 'set', vmid, '--description', desc], check=True)
PY" >/dev/null
}

beagle_provider_reboot_vm() {
  local vmid="$1"

  if beagle_provider_helper_available; then
    beagle_provider_helper_exec reboot-vm "$vmid" >/dev/null 2>&1 || true
    return 0
  fi

  beagle_provider_ssh_host "sudo /usr/sbin/qm reboot '$vmid'" >/dev/null 2>&1 || true
}

beagle_provider_set_vm_options() {
  local vmid="$1"
  shift
  local args=("$@")
  local shell_command=""

  if beagle_provider_helper_available; then
    beagle_provider_helper_exec set-vm-options "$vmid" "${args[@]}" >/dev/null
    return 0
  fi

  shell_command="$(printf '%q ' sudo /usr/sbin/qm set "$vmid" "${args[@]}")"
  beagle_provider_ssh_host "${shell_command% }"
}
