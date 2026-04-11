#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_PROVIDER_MODULE_PATH="${BEAGLE_PROVIDER_MODULE_PATH:-$SCRIPT_DIR/lib/beagle_provider.py}"
REMOTE_INSTALL_DIR="${BEAGLE_REMOTE_INSTALL_DIR:-/opt/beagle}"
REMOTE_PROVIDER_MODULE_PATH="${BEAGLE_REMOTE_PROVIDER_MODULE_PATH:-${REMOTE_INSTALL_DIR%/}/scripts/lib/beagle_provider.py}"
PROVIDER_HELPER_AVAILABLE_CACHE="${PROVIDER_HELPER_AVAILABLE_CACHE:-}"

PROXMOX_HOST="${PROXMOX_HOST:-proxmox.local}"
VMID="${VMID:-}"
ENABLE_AUDIO="${ENABLE_AUDIO:-1}"
SET_ONBOOT="${SET_ONBOOT:-1}"

usage() {
  cat <<'EOF'
Usage: optimize-proxmox-vm-for-beagle.sh --vmid <id> [--proxmox-host <ssh-host>] [--no-audio] [--no-onboot]

Applies a reproducible Beagle OS / Moonlight-friendly baseline to a Proxmox VM:
  - machine: q35
  - cpu: host
  - qemu guest agent: enabled
  - scsi controller: virtio-scsi-single
  - vga: virtio
  - memory ballooning: disabled
  - rng device: enabled
  - optional virtual audio device
EOF
}

require_tool() {
  local tool="$1"
  command -v "$tool" >/dev/null 2>&1 || {
    echo "Missing required tool: $tool" >&2
    exit 1
  }
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --vmid) VMID="$2"; shift 2 ;;
      --proxmox-host) PROXMOX_HOST="$2"; shift 2 ;;
      --no-audio) ENABLE_AUDIO="0"; shift ;;
      --no-onboot) SET_ONBOOT="0"; shift ;;
      -h|--help) usage; exit 0 ;;
      *)
        echo "Unknown argument: $1" >&2
        usage
        exit 1
        ;;
    esac
  done
}

ssh_host() {
  if is_local_host_target; then
    bash -lc "$*"
    return 0
  fi
  ssh "$PROXMOX_HOST" "$@"
}

is_local_host_target() {
  case "${PROXMOX_HOST:-}" in
    localhost|127.0.0.1|::1|"$(hostname)"|"$(hostname -f 2>/dev/null || hostname)")
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

provider_module_path_for_target() {
  if is_local_host_target; then
    printf '%s\n' "$LOCAL_PROVIDER_MODULE_PATH"
    return 0
  fi
  printf '%s\n' "$REMOTE_PROVIDER_MODULE_PATH"
}

provider_helper_available() {
  if [[ "$PROVIDER_HELPER_AVAILABLE_CACHE" == "1" ]]; then
    return 0
  fi
  if [[ "$PROVIDER_HELPER_AVAILABLE_CACHE" == "0" ]]; then
    return 1
  fi
  local module_path
  module_path="$(provider_module_path_for_target)"
  if ssh_host "test -f '$module_path'"; then
    PROVIDER_HELPER_AVAILABLE_CACHE="1"
    return 0
  fi
  PROVIDER_HELPER_AVAILABLE_CACHE="0"
  return 1
}

provider_helper_exec() {
  local module_path
  module_path="$(provider_module_path_for_target)"
  local shell_command
  shell_command="$(printf '%q ' python3 "$module_path" "$@")"
  ssh_host "${shell_command% }"
}

set_vm_options() {
  local args=("$@")
  if provider_helper_available; then
    provider_helper_exec set-vm-options "$VMID" "${args[@]}" >/dev/null
    return 0
  fi
  local shell_command
  shell_command="$(printf '%q ' sudo /usr/sbin/qm set "$VMID" "${args[@]}")"
  ssh_host "${shell_command% }"
}

main() {
  parse_args "$@"
  require_tool ssh

  [[ -n "$VMID" ]] || {
    echo "--vmid is required" >&2
    exit 1
  }

  # Core VM baseline for low-latency remote desktop workloads.
  set_vm_options --machine q35
  set_vm_options --cpu host
  set_vm_options --agent enabled=1
  set_vm_options --scsihw virtio-scsi-single
  set_vm_options --vga virtio
  set_vm_options --balloon 0
  set_vm_options --rng0 source=/dev/urandom

  if [[ "$SET_ONBOOT" == "1" ]]; then
    set_vm_options --onboot 1
  fi

  if [[ "$ENABLE_AUDIO" == "1" ]]; then
    # Provide a deterministic virtual audio device for guest audio capture paths.
    set_vm_options --audio0 device=ich9-intel-hda,driver=spice
  fi

  echo "Applied Beagle OS VM baseline to VM $VMID on host $PROXMOX_HOST"
}

main "$@"
