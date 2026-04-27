#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/opt/beagle}"
HOST_RUNTIME_DIR="$INSTALL_DIR/beagle-host"
LEGACY_HOST_RUNTIME_DIR="$INSTALL_DIR/beagle_host"
CONFIG_DIR="${PVE_DCV_CONFIG_DIR:-/etc/beagle}"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_NAME="beagle-artifacts-refresh.service"
TIMER_NAME="beagle-artifacts-refresh.timer"
WATCHDOG_SERVICE_NAME="beagle-artifacts-watchdog.service"
WATCHDOG_TIMER_NAME="beagle-artifacts-watchdog.timer"
REPO_AUTO_UPDATE_SERVICE_NAME="beagle-repo-auto-update.service"
REPO_AUTO_UPDATE_TIMER_NAME="beagle-repo-auto-update.timer"
UI_REAPPLY_SERVICE="beagle-ui-reapply.service"
UI_REAPPLY_PATH="beagle-ui-reapply.path"
BEAGLE_CONTROL_SERVICE="beagle-control-plane.service"
BEAGLE_CLUSTER_AUTO_JOIN_SERVICE="beagle-cluster-auto-join.service"
BEAGLE_PUBLIC_STREAM_SERVICE="beagle-public-streams.service"
BEAGLE_PUBLIC_STREAM_TIMER="beagle-public-streams.timer"
POLKIT_RULES_DIR="/etc/polkit-1/rules.d"
ARTIFACT_POLKIT_RULE_NAME="49-beagle-artifacts-refresh.rules"
ARTIFACT_WATCHDOG_POLKIT_RULE_NAME="49-beagle-artifacts-watchdog.rules"
REPO_AUTO_UPDATE_POLKIT_RULE_NAME="49-beagle-repo-auto-update.rules"
BEAGLE_NOVNC_PROXY_SERVICE="beagle-novnc-proxy.service"
BEAGLE_CONTROL_ENV_FILE="$CONFIG_DIR/beagle-manager.env"
IDENTITY_PROVIDER_REGISTRY_FILE="${BEAGLE_IDENTITY_PROVIDER_REGISTRY_FILE:-$CONFIG_DIR/identity-providers.json}"
BEAGLE_HOST_PROVIDER="${BEAGLE_HOST_PROVIDER:-beagle}"
BEAGLE_CONTROL_USER="${BEAGLE_CONTROL_USER:-beagle-manager}"
BEAGLE_AUTH_BOOTSTRAP_USERNAME="${BEAGLE_AUTH_BOOTSTRAP_USERNAME:-admin}"
BEAGLE_AUTH_BOOTSTRAP_PASSWORD="${BEAGLE_AUTH_BOOTSTRAP_PASSWORD:-}"
BEAGLE_AUTH_BOOTSTRAP_DISABLE="${BEAGLE_AUTH_BOOTSTRAP_DISABLE:-0}"
BEAGLE_CLUSTER_JOIN_REQUESTED="${BEAGLE_CLUSTER_JOIN_REQUESTED:-no}"
BEAGLE_CLUSTER_JOIN_ENV_FILE="${BEAGLE_CLUSTER_JOIN_ENV_FILE:-$CONFIG_DIR/cluster-join.env}"
USB_TUNNEL_USER="${BEAGLE_USB_TUNNEL_SSH_USER:-beagle-tunnel}"
USB_TUNNEL_HOME="${BEAGLE_USB_TUNNEL_HOME:-}"
USB_TUNNEL_AUTH_ROOT="${BEAGLE_USB_TUNNEL_AUTH_ROOT:-/var/lib/beagle/usb-tunnel/$USB_TUNNEL_USER}"
USB_TUNNEL_ATTACH_HOST="${BEAGLE_USB_TUNNEL_ATTACH_HOST:-10.10.10.1}"
USB_TUNNEL_SSHD_DROPIN="/etc/ssh/sshd_config.d/90-beagle-usb-tunnel.conf"
USB_TUNNEL_TEST_DROPIN="/etc/ssh/sshd_config.d/91-beagle-tunnel-test.conf"
USB_TUNNEL_AUTH_COMMAND="/usr/local/libexec/beagle-usb-authorized-keys"

ensure_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi

  if command -v sudo >/dev/null 2>&1; then
    exec sudo \
      INSTALL_DIR="$INSTALL_DIR" \
      PVE_DCV_CONFIG_DIR="$CONFIG_DIR" \
      BEAGLE_HOST_PROVIDER="$BEAGLE_HOST_PROVIDER" \
      BEAGLE_CONTROL_USER="$BEAGLE_CONTROL_USER" \
      BEAGLE_AUTH_BOOTSTRAP_USERNAME="$BEAGLE_AUTH_BOOTSTRAP_USERNAME" \
      BEAGLE_AUTH_BOOTSTRAP_PASSWORD="$BEAGLE_AUTH_BOOTSTRAP_PASSWORD" \
        BEAGLE_AUTH_BOOTSTRAP_DISABLE="$BEAGLE_AUTH_BOOTSTRAP_DISABLE" \
      "$0" "$@"
  fi

  echo "This installer must run as root or use sudo." >&2
  exit 1
}

install_unit() {
  local source_file="$1"
  local target_file="$2"

  sed "s|__INSTALL_DIR__|$INSTALL_DIR|g" "$source_file" > "$target_file"
  chmod 0644 "$target_file"
}

install_file_if_needed() {
  local mode="$1"
  local source_file="$2"
  local target_file="$3"

  if [[ "$(readlink -f "$source_file")" == "$(readlink -f "$target_file" 2>/dev/null || true)" ]]; then
    return 0
  fi

  install -m "$mode" "$source_file" "$target_file"
}

repair_host_runtime_links() {
  if [[ -L "$HOST_RUNTIME_DIR" ]]; then
    local target=""
    target="$(readlink "$HOST_RUNTIME_DIR" 2>/dev/null || true)"
    if [[ "$target" == "$HOST_RUNTIME_DIR" || "$target" == "/opt/beagle/beagle-host" || "$target" == "beagle-host" ]]; then
      rm -f "$HOST_RUNTIME_DIR"
      install -d -m 0755 "$HOST_RUNTIME_DIR"
    fi
  fi

  if [[ -e "$LEGACY_HOST_RUNTIME_DIR" && ! -L "$LEGACY_HOST_RUNTIME_DIR" ]]; then
    rm -rf "$LEGACY_HOST_RUNTIME_DIR"
  fi
  ln -sfn "beagle-host" "$LEGACY_HOST_RUNTIME_DIR"
}

has_ui_reapply_units() {
  [[ -f "$ROOT_DIR/beagle-host/systemd/$UI_REAPPLY_SERVICE" ]] &&
    [[ -f "$ROOT_DIR/beagle-host/systemd/$UI_REAPPLY_PATH" ]]
}

generate_token() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
    return 0
  fi

  python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
}

generate_password_hash() {
  if command -v openssl >/dev/null 2>&1; then
    openssl passwd -6 "$(openssl rand -base64 24)"
    return 0
  fi

  python3 - <<'PY'
import crypt
import secrets
import string

alphabet = string.ascii_letters + string.digits
password = "".join(secrets.choice(alphabet) for _ in range(32))
salt = "".join(secrets.choice(alphabet) for _ in range(16))
print(crypt.crypt(password, f"$6${salt}$"))
PY
}

run_account_cmd() {
  local attempt=0
  local max_attempts=5
  while true; do
    if "$@"; then
      return 0
    fi
    attempt=$((attempt + 1))
    if (( attempt >= max_attempts )); then
      return 1
    fi
    sleep 2
  done
}

resolve_qemu_system_package() {
  local package_name=""

  for package_name in qemu-kvm qemu-system-x86 qemu-system; do
    if apt-cache show "$package_name" >/dev/null 2>&1; then
      printf '%s\n' "$package_name"
      return 0
    fi
  done

  printf 'qemu-system-x86\n'
}

apt_update_for_runtime_packages() {
  DEBIAN_FRONTEND=noninteractive apt-get update
}

install_runtime_packages() {
  apt_update_for_runtime_packages
  DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
}

standalone_runtime_tools_ready() {
  command -v virsh >/dev/null 2>&1 &&
    command -v qemu-img >/dev/null 2>&1 &&
    command -v xorriso >/dev/null 2>&1 &&
    command -v zip >/dev/null 2>&1 &&
    command -v npm >/dev/null 2>&1
}

tls_runtime_tools_ready() {
  command -v certbot >/dev/null 2>&1 &&
    [[ -f /usr/lib/python3/dist-packages/certbot_nginx/__init__.py || -f /usr/lib/python3/dist-packages/certbot_nginx/_internal/configurator.py ]]
}

wait_for_libvirt_system() {
  local attempt=""

  systemctl enable --now libvirtd >/dev/null 2>&1 || true
  for attempt in $(seq 1 30); do
    if virsh --connect qemu:///system list --all >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "libvirt qemu:///system is not ready" >&2
  return 1
}

can_manage_libvirt_system() {
  # When called from server-installer chroot, skip all libvirt management.
  if [[ "${BEAGLE_IN_CHROOT_INSTALL:-0}" == "1" ]]; then
    return 1
  fi
  # During server-installer chroot installs, libvirt sockets/services are not
  # expected to be reachable. Defer runtime checks to first real boot.
  if command -v systemd-detect-virt >/dev/null 2>&1; then
    local virt_type
    virt_type=$(systemd-detect-virt 2>/dev/null || true)
    if [[ "$virt_type" == "chroot" ]]; then
      return 1
    fi
  fi

  if [[ ! -d /run/systemd/system ]]; then
    return 1
  fi

  return 0
}

set_env_value() {
  local env_file="$1"
  local key="$2"
  local value="$3"

  if grep -q "^${key}=" "$env_file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
    return 0
  fi
  printf '%s=%s\n' "$key" "$value" >>"$env_file"
}

is_loopback_host() {
  local candidate="${1:-}"
  candidate="${candidate//\"/}"
  candidate="${candidate//\'/}"
  candidate="$(printf '%s' "$candidate" | xargs 2>/dev/null || printf '%s' "$candidate")"
  [[ -z "$candidate" ]] && return 0
  [[ "$candidate" == "localhost" ]] && return 0
  [[ "$candidate" == "127."* ]] && return 0
  return 1
}

detect_primary_ipv4() {
  local candidate=""

  candidate="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i=="src") {print $(i+1); exit}}')"
  if [[ -n "$candidate" ]]; then
    printf '%s\n' "$candidate"
    return 0
  fi

  candidate="$(hostname -I 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i !~ /^127\./) {print $i; exit}}')"
  if [[ -n "$candidate" ]]; then
    printf '%s\n' "$candidate"
    return 0
  fi

  return 1
}

detect_beagle_network_gateway_ipv4() {
  local gateway=""

  if ! command -v virsh >/dev/null 2>&1; then
    return 1
  fi

  gateway="$(virsh --connect qemu:///system net-dumpxml beagle 2>/dev/null | awk -F"'" '/<ip address=/{print $2; exit}')"
  if [[ -z "$gateway" ]]; then
    return 1
  fi

  printf '%s\n' "$gateway"
  return 0
}

detect_beagle_network_bridge_iface() {
  local bridge=""

  if ! command -v virsh >/dev/null 2>&1; then
    return 1
  fi

  bridge="$(virsh --connect qemu:///system net-dumpxml beagle 2>/dev/null | awk -F"'" '/<bridge name=/{print $2; exit}')"
  if [[ -z "$bridge" ]]; then
    return 1
  fi

  printf '%s\n' "$bridge"
  return 0
}

# ---------------------------------------------------------------------------
# setup_beagle_manager_migration_ssh
#
# Ensures the beagle-manager service account has a dedicated ed25519 key and
# an SSH client config that:
#   - forces IPv4 (avoids IPv6/dual-stack DNS ambiguity)
#   - accepts new host keys automatically on first contact (accept-new)
#   - uses BatchMode so libvirt/virsh can't block on interactive prompts
#
# The public key is printed to stdout so operators / automation can distribute
# it to peer nodes via beagle-cluster-ssh-setup.sh or manually via
# ssh-copy-id / authorized_keys management.
#
# Idempotent: re-running never overwrites an existing key.
# ---------------------------------------------------------------------------
setup_beagle_manager_migration_ssh() {
  local ssh_home="/var/lib/beagle/.ssh"
  local key_file="$ssh_home/id_ed25519"
  local config_file="$ssh_home/config"

  install -d -m 0700 -o "$BEAGLE_CONTROL_USER" -g "$BEAGLE_CONTROL_USER" "$ssh_home"

  if [[ ! -f "$key_file" ]]; then
    ssh-keygen -t ed25519 -N '' \
      -f "$key_file" \
      -C "beagle-manager@$(hostname -s)-migration" \
      >/dev/null
    chown "$BEAGLE_CONTROL_USER:$BEAGLE_CONTROL_USER" "$key_file" "${key_file}.pub"
    chmod 0600 "$key_file"
    chmod 0644 "${key_file}.pub"
    echo "beagle-manager SSH key generated: $key_file" >&2
  fi

  # Write SSH client config — safe to overwrite (only manages our settings)
  cat > "$config_file" <<'SSHCFG'
# Managed by beagle install-beagle-host-services.sh — do not edit manually.
# Used by beagle-manager for virsh qemu+ssh:// live-migration connections.
Host *
    IdentityFile /var/lib/beagle/.ssh/id_ed25519
    AddressFamily inet
    StrictHostKeyChecking accept-new
    BatchMode yes
    ConnectTimeout 10
SSHCFG
  chown "$BEAGLE_CONTROL_USER:$BEAGLE_CONTROL_USER" "$config_file"
  chmod 0600 "$config_file"

  echo "beagle-manager SSH config written: $config_file" >&2
  echo "beagle-manager public key (distribute to cluster peers):"
  cat "${key_file}.pub"
}

ensure_root "$@"
repair_host_runtime_links

if ! id "$BEAGLE_CONTROL_USER" >/dev/null 2>&1; then
  run_account_cmd useradd --system --home-dir /var/lib/beagle --no-create-home --shell /usr/sbin/nologin "$BEAGLE_CONTROL_USER"
fi

for runtime_group in libvirt kvm; do
  if getent group "$runtime_group" >/dev/null 2>&1; then
    if ! id -nG "$BEAGLE_CONTROL_USER" | tr ' ' '\n' | grep -qx "$runtime_group"; then
      run_account_cmd usermod -a -G "$runtime_group" "$BEAGLE_CONTROL_USER"
    fi
  fi
done

if ! id "$USB_TUNNEL_USER" >/dev/null 2>&1; then
  if [[ -z "$USB_TUNNEL_HOME" ]]; then
    USB_TUNNEL_HOME="/var/lib/beagle/${USB_TUNNEL_USER}"
  fi
  run_account_cmd useradd --system --home-dir "$USB_TUNNEL_HOME" --create-home --shell /bin/bash "$USB_TUNNEL_USER"
  run_account_cmd usermod -p "$(generate_password_hash)" "$USB_TUNNEL_USER"
fi
if [[ -z "$USB_TUNNEL_HOME" ]]; then
  USB_TUNNEL_HOME="$(getent passwd "$USB_TUNNEL_USER" | cut -d: -f6)"
fi
install -d -m 0755 "$USB_TUNNEL_HOME"
install -d -m 0755 "$(dirname "$USB_TUNNEL_AUTH_ROOT")"
install -d -m 0710 "$USB_TUNNEL_AUTH_ROOT"
install -d -m 0700 "$USB_TUNNEL_AUTH_ROOT/authorized_keys.d"
touch "$USB_TUNNEL_AUTH_ROOT/authorized_keys"
chmod 0600 "$USB_TUNNEL_AUTH_ROOT/authorized_keys"
# auth_root: root owns the directory (sshd trusts it), group=beagle-manager with execute-only
# so the service can traverse into authorized_keys.d and write authorized_keys.
# authorized_keys.d is owned outright by beagle-manager for key fragments.
chown root:"$BEAGLE_CONTROL_USER" "$USB_TUNNEL_AUTH_ROOT"
chown "$BEAGLE_CONTROL_USER":"$BEAGLE_CONTROL_USER" "$USB_TUNNEL_AUTH_ROOT/authorized_keys" "$USB_TUNNEL_AUTH_ROOT/authorized_keys.d"

cat >"$USB_TUNNEL_SSHD_DROPIN" <<EOF
# StrictModes off for beagle-manager-owned authorized_keys (managed service account)
StrictModes no
Match User $USB_TUNNEL_USER
    AuthenticationMethods publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    PubkeyAuthentication yes
    AuthorizedKeysFile $USB_TUNNEL_AUTH_ROOT/authorized_keys .ssh/authorized_keys
    AllowTcpForwarding remote
    AllowAgentForwarding no
    PermitTTY yes
    X11Forwarding no
    GatewayPorts clientspecified
EOF
chmod 0644 "$USB_TUNNEL_SSHD_DROPIN"

install -d -m 0755 "$SYSTEMD_DIR"
install -d -m 0755 "$HOST_RUNTIME_DIR/bin"
install -d -m 0755 "$HOST_RUNTIME_DIR/providers"
install -d -m 0755 "$HOST_RUNTIME_DIR/services"
install -d -m 0755 "$HOST_RUNTIME_DIR/templates/ubuntu-beagle"
install_unit "$ROOT_DIR/beagle-host/systemd/$SERVICE_NAME" "$SYSTEMD_DIR/$SERVICE_NAME"
install -m 0644 "$ROOT_DIR/beagle-host/systemd/$TIMER_NAME" "$SYSTEMD_DIR/$TIMER_NAME"
install_unit "$ROOT_DIR/beagle-host/systemd/$WATCHDOG_SERVICE_NAME" "$SYSTEMD_DIR/$WATCHDOG_SERVICE_NAME"
install -m 0644 "$ROOT_DIR/beagle-host/systemd/$WATCHDOG_TIMER_NAME" "$SYSTEMD_DIR/$WATCHDOG_TIMER_NAME"
install_unit "$ROOT_DIR/beagle-host/systemd/$REPO_AUTO_UPDATE_SERVICE_NAME" "$SYSTEMD_DIR/$REPO_AUTO_UPDATE_SERVICE_NAME"
install -m 0644 "$ROOT_DIR/beagle-host/systemd/$REPO_AUTO_UPDATE_TIMER_NAME" "$SYSTEMD_DIR/$REPO_AUTO_UPDATE_TIMER_NAME"
if has_ui_reapply_units; then
  install_unit "$ROOT_DIR/beagle-host/systemd/$UI_REAPPLY_SERVICE" "$SYSTEMD_DIR/$UI_REAPPLY_SERVICE"
  install -m 0644 "$ROOT_DIR/beagle-host/systemd/$UI_REAPPLY_PATH" "$SYSTEMD_DIR/$UI_REAPPLY_PATH"
else
  rm -f "$SYSTEMD_DIR/$UI_REAPPLY_SERVICE" "$SYSTEMD_DIR/$UI_REAPPLY_PATH"
fi
install_unit "$ROOT_DIR/beagle-host/systemd/$BEAGLE_CONTROL_SERVICE" "$SYSTEMD_DIR/$BEAGLE_CONTROL_SERVICE"
install_unit "$ROOT_DIR/beagle-host/systemd/$BEAGLE_CLUSTER_AUTO_JOIN_SERVICE" "$SYSTEMD_DIR/$BEAGLE_CLUSTER_AUTO_JOIN_SERVICE"
install_unit "$ROOT_DIR/beagle-host/systemd/$BEAGLE_PUBLIC_STREAM_SERVICE" "$SYSTEMD_DIR/$BEAGLE_PUBLIC_STREAM_SERVICE"
install -m 0644 "$ROOT_DIR/beagle-host/systemd/$BEAGLE_PUBLIC_STREAM_TIMER" "$SYSTEMD_DIR/$BEAGLE_PUBLIC_STREAM_TIMER"
install -m 0644 "$ROOT_DIR/beagle-host/systemd/$BEAGLE_NOVNC_PROXY_SERVICE" "$SYSTEMD_DIR/$BEAGLE_NOVNC_PROXY_SERVICE"
if [[ "$(readlink -f "$ROOT_DIR/beagle-host/bin/beagle-control-plane.py")" != "$(readlink -f "$HOST_RUNTIME_DIR/bin/beagle-control-plane.py" 2>/dev/null || true)" ]]; then
  install -m 0755 "$ROOT_DIR/beagle-host/bin/beagle-control-plane.py" "$HOST_RUNTIME_DIR/bin/beagle-control-plane.py"
fi
if [[ "$(readlink -f "$ROOT_DIR/beagle-host/bin/beagle-usb-tunnel-session")" != "$(readlink -f "$HOST_RUNTIME_DIR/bin/beagle-usb-tunnel-session" 2>/dev/null || true)" ]]; then
  install -m 0755 "$ROOT_DIR/beagle-host/bin/beagle-usb-tunnel-session" "$HOST_RUNTIME_DIR/bin/beagle-usb-tunnel-session"
fi
if [[ "$(readlink -f "$ROOT_DIR/beagle-host/bin/endpoint_profile_contract.py")" != "$(readlink -f "$HOST_RUNTIME_DIR/bin/endpoint_profile_contract.py" 2>/dev/null || true)" ]]; then
  install -m 0644 "$ROOT_DIR/beagle-host/bin/endpoint_profile_contract.py" "$HOST_RUNTIME_DIR/bin/endpoint_profile_contract.py"
fi
if [[ "$(readlink -f "$ROOT_DIR/scripts/beagle-cluster-auto-join.sh")" != "$(readlink -f "$INSTALL_DIR/scripts/beagle-cluster-auto-join.sh" 2>/dev/null || true)" ]]; then
  install -m 0755 "$ROOT_DIR/scripts/beagle-cluster-auto-join.sh" "$INSTALL_DIR/scripts/beagle-cluster-auto-join.sh"
fi
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/providers/host_provider_contract.py" "$HOST_RUNTIME_DIR/providers/host_provider_contract.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/providers/registry.py" "$HOST_RUNTIME_DIR/providers/registry.py"
for provider_file in "$ROOT_DIR"/beagle-host/providers/*_host_provider.py; do
  [[ -f "$provider_file" ]] || continue
  install_file_if_needed 0644 "$provider_file" "$HOST_RUNTIME_DIR/providers/$(basename "$provider_file")"
done
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/virtualization_inventory.py" "$HOST_RUNTIME_DIR/services/virtualization_inventory.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/admin_http_surface.py" "$HOST_RUNTIME_DIR/services/admin_http_surface.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/runtime_environment.py" "$HOST_RUNTIME_DIR/services/runtime_environment.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/runtime_support.py" "$HOST_RUNTIME_DIR/services/runtime_support.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/runtime_exec.py" "$HOST_RUNTIME_DIR/services/runtime_exec.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/runtime_paths.py" "$HOST_RUNTIME_DIR/services/runtime_paths.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/time_support.py" "$HOST_RUNTIME_DIR/services/time_support.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/utility_support.py" "$HOST_RUNTIME_DIR/services/utility_support.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/metadata_support.py" "$HOST_RUNTIME_DIR/services/metadata_support.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/persistence_support.py" "$HOST_RUNTIME_DIR/services/persistence_support.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/request_support.py" "$HOST_RUNTIME_DIR/services/request_support.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/endpoint_enrollment.py" "$HOST_RUNTIME_DIR/services/endpoint_enrollment.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/endpoint_lifecycle_surface.py" "$HOST_RUNTIME_DIR/services/endpoint_lifecycle_surface.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/ubuntu_beagle_restart.py" "$HOST_RUNTIME_DIR/services/ubuntu_beagle_restart.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/vm_profile.py" "$HOST_RUNTIME_DIR/services/vm_profile.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/vm_http_surface.py" "$HOST_RUNTIME_DIR/services/vm_http_surface.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/control_plane_read_surface.py" "$HOST_RUNTIME_DIR/services/control_plane_read_surface.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/endpoint_http_surface.py" "$HOST_RUNTIME_DIR/services/endpoint_http_surface.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/public_http_surface.py" "$HOST_RUNTIME_DIR/services/public_http_surface.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/public_sunshine_surface.py" "$HOST_RUNTIME_DIR/services/public_sunshine_surface.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/public_ubuntu_install_surface.py" "$HOST_RUNTIME_DIR/services/public_ubuntu_install_surface.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/vm_mutation_surface.py" "$HOST_RUNTIME_DIR/services/vm_mutation_surface.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/vm_state.py" "$HOST_RUNTIME_DIR/services/vm_state.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/download_metadata.py" "$HOST_RUNTIME_DIR/services/download_metadata.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/update_feed.py" "$HOST_RUNTIME_DIR/services/update_feed.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/fleet_inventory.py" "$HOST_RUNTIME_DIR/services/fleet_inventory.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/health_payload.py" "$HOST_RUNTIME_DIR/services/health_payload.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/installer_prep.py" "$HOST_RUNTIME_DIR/services/installer_prep.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/installer_script.py" "$HOST_RUNTIME_DIR/services/installer_script.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/installer_template_patch.py" "$HOST_RUNTIME_DIR/services/installer_template_patch.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/thin_client_preset.py" "$HOST_RUNTIME_DIR/services/thin_client_preset.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/endpoint_report.py" "$HOST_RUNTIME_DIR/services/endpoint_report.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/action_queue.py" "$HOST_RUNTIME_DIR/services/action_queue.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/policy_normalization.py" "$HOST_RUNTIME_DIR/services/policy_normalization.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/policy_store.py" "$HOST_RUNTIME_DIR/services/policy_store.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/public_streams.py" "$HOST_RUNTIME_DIR/services/public_streams.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/support_bundle_store.py" "$HOST_RUNTIME_DIR/services/support_bundle_store.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/ubuntu_beagle_inputs.py" "$HOST_RUNTIME_DIR/services/ubuntu_beagle_inputs.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/vm_usb.py" "$HOST_RUNTIME_DIR/services/vm_usb.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/ubuntu_beagle_provisioning.py" "$HOST_RUNTIME_DIR/services/ubuntu_beagle_provisioning.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/ubuntu_beagle_state.py" "$HOST_RUNTIME_DIR/services/ubuntu_beagle_state.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/vm_secret_store.py" "$HOST_RUNTIME_DIR/services/vm_secret_store.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/vm_secret_bootstrap.py" "$HOST_RUNTIME_DIR/services/vm_secret_bootstrap.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/sunshine_integration.py" "$HOST_RUNTIME_DIR/services/sunshine_integration.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/enrollment_token_store.py" "$HOST_RUNTIME_DIR/services/enrollment_token_store.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/sunshine_access_token_store.py" "$HOST_RUNTIME_DIR/services/sunshine_access_token_store.py"
install_file_if_needed 0644 "$ROOT_DIR/beagle-host/services/endpoint_token_store.py" "$HOST_RUNTIME_DIR/services/endpoint_token_store.py"
# Keep runtime service module installation in sync with control-plane imports.
for service_file in "$ROOT_DIR"/beagle-host/services/*.py; do
  [[ -f "$service_file" ]] || continue
  install_file_if_needed 0644 "$service_file" "$HOST_RUNTIME_DIR/services/$(basename "$service_file")"
done
for template_file in "$ROOT_DIR"/beagle-host/templates/ubuntu-beagle/*; do
  [[ -f "$template_file" ]] || continue
  install_file_if_needed 0644 "$template_file" "$HOST_RUNTIME_DIR/templates/ubuntu-beagle/$(basename "$template_file")"
done
repair_host_runtime_links
rm -f "$USB_TUNNEL_TEST_DROPIN" "$USB_TUNNEL_AUTH_COMMAND"

# The artifact refresh service runs as beagle-manager and rebuilds package
# outputs directly from the deployed repo checkout under /opt/beagle.
if [[ -d "$INSTALL_DIR" ]]; then
  find "$INSTALL_DIR" \
    -path "$INSTALL_DIR/.build" -prune -o \
    -exec chgrp "$BEAGLE_CONTROL_USER" {} +
  find "$INSTALL_DIR" \
    -path "$INSTALL_DIR/.build" -prune -o \
    -exec chmod g+rwX {} +
  find "$INSTALL_DIR" \
    -path "$INSTALL_DIR/.build" -prune -o \
    -type d -exec chmod g+s {} +
fi

install -d -m 0755 "$CONFIG_DIR"
if [[ ! -f "$BEAGLE_CONTROL_ENV_FILE" ]]; then
  cat > "$BEAGLE_CONTROL_ENV_FILE" <<EOF
BEAGLE_MANAGER_LISTEN_HOST="127.0.0.1"
BEAGLE_MANAGER_LISTEN_PORT="9088"
BEAGLE_MANAGER_DATA_DIR="/var/lib/beagle/beagle-manager"
BEAGLE_MANAGER_API_TOKEN="$(generate_token)"
BEAGLE_MANAGER_ALLOW_LOCALHOST_NOAUTH="0"
EOF
  chmod 0640 "$BEAGLE_CONTROL_ENV_FILE"
fi
chown root:"$BEAGLE_CONTROL_USER" "$BEAGLE_CONTROL_ENV_FILE"
chmod 0640 "$BEAGLE_CONTROL_ENV_FILE"

if [[ ! -f "$IDENTITY_PROVIDER_REGISTRY_FILE" ]]; then
  cat > "$IDENTITY_PROVIDER_REGISTRY_FILE" <<'EOF'
{
  "providers": [
    {
      "id": "local",
      "type": "local",
      "label": "Lokaler Account",
      "description": "Benutzername + Passwort (Break-Glass).",
      "enabled": true,
      "login_url": ""
    },
    {
      "id": "oidc",
      "type": "oidc",
      "label": "Mit OIDC anmelden",
      "description": "Single Sign-On ueber OpenID Connect.",
      "enabled": false,
      "login_url": "/api/v1/auth/oidc/login"
    },
    {
      "id": "saml",
      "type": "saml",
      "label": "Mit SAML anmelden",
      "description": "Enterprise-Login ueber SAML 2.0.",
      "enabled": false,
      "login_url": "/api/v1/auth/saml/login"
    }
  ]
}
EOF
fi
chown root:"$BEAGLE_CONTROL_USER" "$IDENTITY_PROVIDER_REGISTRY_FILE"
chmod 0640 "$IDENTITY_PROVIDER_REGISTRY_FILE"

set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_HOST_PROVIDER" "\"$BEAGLE_HOST_PROVIDER\""
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_MANAGER_LISTEN_HOST" '"127.0.0.1"'
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_IDENTITY_PROVIDER_REGISTRY_FILE" "\"$IDENTITY_PROVIDER_REGISTRY_FILE\""
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_AUTH_ACCESS_TTL_SECONDS" '"900"'
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_API_RATE_LIMIT_WINDOW_SECONDS" '"60"'
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_API_RATE_LIMIT_MAX_REQUESTS" '"240"'
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_AUTH_LOGIN_LOCKOUT_THRESHOLD" '"5"'
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_AUTH_LOGIN_LOCKOUT_SECONDS" '"300"'
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_AUTH_LOGIN_BACKOFF_MAX_SECONDS" '"30"'
if ! grep -q '^BEAGLE_INSTALL_CHECK_REPORT_TOKEN=' "$BEAGLE_CONTROL_ENV_FILE"; then
  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_INSTALL_CHECK_REPORT_TOKEN" "\"$(generate_token)\""
fi
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_CLUSTER_JOIN_REQUESTED" "\"$BEAGLE_CLUSTER_JOIN_REQUESTED\""
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_CLUSTER_JOIN_ENV_FILE" "\"$BEAGLE_CLUSTER_JOIN_ENV_FILE\""

install -d -m 0755 /var/lib/beagle
install -d -m 0750 /var/lib/beagle/beagle-manager
chown -R "$BEAGLE_CONTROL_USER":"$BEAGLE_CONTROL_USER" /var/lib/beagle/beagle-manager
python3 - /var/lib/beagle/beagle-manager/server-settings.json <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    settings = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
except (OSError, json.JSONDecodeError):
    settings = {}
if not isinstance(settings, dict):
    settings = {}

defaults = {
    "repo_auto_update_enabled": True,
    "repo_auto_update_repo_url": "https://github.com/meinzeug/beagle-os.git",
    "repo_auto_update_branch": "main",
    "repo_auto_update_interval_minutes": 1,
    "artifact_watchdog_enabled": True,
    "artifact_watchdog_auto_repair": True,
    "artifact_watchdog_max_age_hours": 6,
}
changed = False
for key, value in defaults.items():
    if key not in settings:
        settings[key] = value
        changed = True
if changed or not path.is_file():
    path.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
chown "$BEAGLE_CONTROL_USER":"$BEAGLE_CONTROL_USER" /var/lib/beagle/beagle-manager/server-settings.json
chmod 0640 /var/lib/beagle/beagle-manager/server-settings.json
install -d -m 0750 /var/backups/beagle
install -d -m 0750 /var/restores/beagle
chown "$BEAGLE_CONTROL_USER":"$BEAGLE_CONTROL_USER" /var/backups/beagle /var/restores/beagle
# Provider data dirs must be writable by beagle-manager
install -d -m 0755 /var/lib/beagle/providers
install -d -m 0755 /var/lib/beagle/providers/beagle
install -d -m 0755 /var/lib/beagle/providers/beagle/vm-configs
install -d -m 0755 /var/lib/beagle/providers/beagle/guest-exec-status
install -d -m 0755 /var/lib/beagle/providers/beagle/guest-interfaces
install -d -m 0755 /var/lib/beagle/providers/beagle/scheduled-restarts
chown -R "$BEAGLE_CONTROL_USER":"$BEAGLE_CONTROL_USER" /var/lib/beagle/providers

if ! tls_runtime_tools_ready; then
  install_runtime_packages certbot python3-certbot-nginx
fi

if ! python3 -c 'import boto3' >/dev/null 2>&1; then
  install_runtime_packages python3-boto3
fi

# When running with the beagle (libvirt/KVM) provider, set storage paths and
# ensure libvirt + OVMF are installed.
if [[ "$BEAGLE_HOST_PROVIDER" == "beagle" ]]; then
  BEAGLE_LIBVIRT_IMAGES_DIR="${BEAGLE_LIBVIRT_IMAGES_DIR:-/var/lib/libvirt/images}"
  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_UBUNTU_LOCAL_ISO_DIR" "\"$BEAGLE_LIBVIRT_IMAGES_DIR\""
  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_UBUNTU_DISK_STORAGE" '"local"'
  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_UBUNTU_ISO_STORAGE" '"local"'
  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_UBUNTU_DEFAULT_BRIDGE" '"beagle"'
  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_PUBLIC_STREAM_LAN_IF" '"virbr10"'

  if ! standalone_runtime_tools_ready; then
    qemu_system_package="$(resolve_qemu_system_package)"
    install_runtime_packages \
      libvirt-daemon-system libvirt-clients "$qemu_system_package" qemu-utils ovmf xorriso zip nodejs npm novnc websockify
  fi
  if ! command -v websockify >/dev/null 2>&1 || [[ ! -f /usr/share/novnc/vnc.html ]]; then
    install_runtime_packages novnc websockify
  fi

  if can_manage_libvirt_system; then
    wait_for_libvirt_system
  else
    echo "Skipping live libvirt readiness check during offline/chroot install" >&2
  fi

  install -d -m 0755 /etc/beagle/novnc
  touch /etc/beagle/novnc/tokens
  chown root:"$BEAGLE_CONTROL_USER" /etc/beagle/novnc /etc/beagle/novnc/tokens
  chmod 0770 /etc/beagle/novnc
  chmod 0660 /etc/beagle/novnc/tokens

  # Deploy single-use noVNC token plugin for websockify
  install -d -m 0755 /opt/beagle/lib
  install -m 0644 "$ROOT_DIR/beagle-host/bin/beagle_novnc_token.py" /opt/beagle/lib/beagle_novnc_token.py
  chown root:"$BEAGLE_CONTROL_USER" /opt/beagle/lib/beagle_novnc_token.py

  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_NOVNC_PATH" '"/novnc"'
  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_NOVNC_TOKEN_FILE" '"/etc/beagle/novnc/tokens"'

  if can_manage_libvirt_system && virsh --connect qemu:///system list --all >/dev/null 2>&1; then
    # Create beagle libvirt network (192.168.123.0/24) if missing
    if ! virsh --connect qemu:///system net-info beagle >/dev/null 2>&1; then
      tmpnet=$(mktemp /tmp/beagle-net-XXXXXX.xml)
      cat >"$tmpnet" <<'NETEOF'
<network>
  <name>beagle</name>
  <forward mode='nat'/>
  <bridge name='virbr10' stp='on' delay='0'/>
  <ip address='192.168.123.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.123.100' end='192.168.123.254'/>
    </dhcp>
  </ip>
</network>
NETEOF
      virsh --connect qemu:///system net-define "$tmpnet" >/dev/null
      virsh --connect qemu:///system net-start beagle >/dev/null 2>&1 || true
      virsh --connect qemu:///system net-autostart beagle >/dev/null
      rm -f "$tmpnet"
    else
      virsh --connect qemu:///system net-start beagle >/dev/null 2>&1 || true
      virsh --connect qemu:///system net-autostart beagle >/dev/null
    fi
    virsh --connect qemu:///system net-info beagle >/dev/null

    detected_beagle_bridge_iface="$(detect_beagle_network_bridge_iface || true)"
    if [[ -n "$detected_beagle_bridge_iface" ]]; then
      set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_PUBLIC_STREAM_LAN_IF" "\"$detected_beagle_bridge_iface\""
    fi

    # Create local storage pool if missing
    if ! virsh --connect qemu:///system pool-info local >/dev/null 2>&1; then
      mkdir -p "$BEAGLE_LIBVIRT_IMAGES_DIR"
      virsh --connect qemu:///system pool-define-as local dir --target "$BEAGLE_LIBVIRT_IMAGES_DIR" >/dev/null
      virsh --connect qemu:///system pool-build local >/dev/null 2>&1 || true
      virsh --connect qemu:///system pool-start local >/dev/null 2>&1 || true
      virsh --connect qemu:///system pool-autostart local >/dev/null
    else
      virsh --connect qemu:///system pool-start local >/dev/null 2>&1 || true
      virsh --connect qemu:///system pool-autostart local >/dev/null
    fi
    # Ensure beagle-manager (in the libvirt group) can write ISOs and disk images
    # into the libvirt images directory. libvirt sets this dir to 0711 by default.
    chown root:libvirt "$BEAGLE_LIBVIRT_IMAGES_DIR"
    chmod 0771 "$BEAGLE_LIBVIRT_IMAGES_DIR"
    virsh --connect qemu:///system pool-info local >/dev/null
  else
    echo "Skipping libvirt network/storage bootstrap during offline/chroot install" >&2
  fi

  # Ensure nvram dir exists for OVMF vars
  mkdir -p /var/lib/libvirt/qemu/nvram

  # Set up SSH key + config for beagle-manager so virsh live-migration
  # (qemu+ssh://) can connect to peer nodes without interactive prompts.
  setup_beagle_manager_migration_ssh
fi
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_MANAGER_ALLOW_LOCALHOST_NOAUTH" '"0"'
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_USB_TUNNEL_SSH_USER" "\"$USB_TUNNEL_USER\""
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_USB_TUNNEL_AUTH_ROOT" "\"$USB_TUNNEL_AUTH_ROOT\""

configured_public_stream_host="${BEAGLE_PUBLIC_STREAM_HOST:-}"
if [[ -z "$configured_public_stream_host" ]]; then
  configured_public_stream_host="$(awk -F= '/^BEAGLE_PUBLIC_STREAM_HOST=/{print $2; exit}' "$BEAGLE_CONTROL_ENV_FILE" 2>/dev/null || true)"
fi
if is_loopback_host "$configured_public_stream_host"; then
  detected_public_stream_host="$(detect_primary_ipv4 || true)"
  if [[ -n "$detected_public_stream_host" ]]; then
    set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_PUBLIC_STREAM_HOST" "\"$detected_public_stream_host\""
  fi
elif [[ -n "$configured_public_stream_host" ]]; then
  configured_public_stream_host="${configured_public_stream_host//\"/}"
  configured_public_stream_host="${configured_public_stream_host//\'/}"
  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_PUBLIC_STREAM_HOST" "\"$configured_public_stream_host\""
fi

configured_internal_callback_host="${BEAGLE_INTERNAL_CALLBACK_HOST:-}"
if [[ -z "$configured_internal_callback_host" ]]; then
  configured_internal_callback_host="$(awk -F= '/^BEAGLE_INTERNAL_CALLBACK_HOST=/{print $2; exit}' "$BEAGLE_CONTROL_ENV_FILE" 2>/dev/null || true)"
fi

# For beagle provider VMs on the libvirt NAT network, callbacks must target the
# host-side beagle bridge gateway (usually 192.168.123.1), not the external host IP.
if [[ "$BEAGLE_HOST_PROVIDER" == "beagle" ]]; then
  if is_loopback_host "$configured_internal_callback_host"; then
    configured_internal_callback_host=""
  fi
  if [[ -z "$configured_internal_callback_host" ]]; then
    detected_internal_callback_host="$(detect_beagle_network_gateway_ipv4 || true)"
    if [[ -n "$detected_internal_callback_host" ]]; then
      set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_INTERNAL_CALLBACK_HOST" "\"$detected_internal_callback_host\""
    fi
  else
    configured_internal_callback_host="${configured_internal_callback_host//\"/}"
    configured_internal_callback_host="${configured_internal_callback_host//\'/}"
    set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_INTERNAL_CALLBACK_HOST" "\"$configured_internal_callback_host\""
  fi
elif [[ -n "$configured_internal_callback_host" ]]; then
  configured_internal_callback_host="${configured_internal_callback_host//\"/}"
  configured_internal_callback_host="${configured_internal_callback_host//\'/}"
  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_INTERNAL_CALLBACK_HOST" "\"$configured_internal_callback_host\""
fi

if [[ -n "$BEAGLE_AUTH_BOOTSTRAP_USERNAME" ]]; then
  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_AUTH_BOOTSTRAP_USERNAME" "\"$BEAGLE_AUTH_BOOTSTRAP_USERNAME\""
fi
bootstrap_disable_normalized="$(printf '%s' "$BEAGLE_AUTH_BOOTSTRAP_DISABLE" | tr '[:upper:]' '[:lower:]')"
case "$bootstrap_disable_normalized" in
  1|true|yes|on)
    set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_AUTH_BOOTSTRAP_DISABLE" '"1"'
    sed -i '/^BEAGLE_AUTH_BOOTSTRAP_PASSWORD=/d' "$BEAGLE_CONTROL_ENV_FILE"
    ;;
  *)
    set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_AUTH_BOOTSTRAP_DISABLE" '"0"'
    ;;
esac
if [[ "$bootstrap_disable_normalized" != "1" && "$bootstrap_disable_normalized" != "true" && "$bootstrap_disable_normalized" != "yes" && "$bootstrap_disable_normalized" != "on" && -n "$BEAGLE_AUTH_BOOTSTRAP_PASSWORD" ]]; then
  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_AUTH_BOOTSTRAP_PASSWORD" "\"$BEAGLE_AUTH_BOOTSTRAP_PASSWORD\""
fi

if grep -q '^BEAGLE_ENDPOINT_SHARED_TOKEN=' "$BEAGLE_CONTROL_ENV_FILE"; then
  sed -i '/^BEAGLE_ENDPOINT_SHARED_TOKEN=/d' "$BEAGLE_CONTROL_ENV_FILE"
fi

systemctl daemon-reload 2>/dev/null || true
systemctl restart ssh.service >/dev/null 2>&1 || systemctl restart sshd.service >/dev/null 2>&1 || true

cat > /etc/sudoers.d/beagle-artifacts-refresh <<'SUDOERS'
# Managed by install-beagle-host-services.sh — do not edit by hand.
beagle-manager ALL=(root) NOPASSWD: /bin/systemctl start beagle-artifacts-refresh.service, /bin/systemctl show -p Id beagle-artifacts-refresh.service
beagle-manager ALL=(root) NOPASSWD: /bin/systemctl start beagle-artifacts-watchdog.service, /bin/systemctl show -p Id beagle-artifacts-watchdog.service
beagle-manager ALL=(root) NOPASSWD: /bin/systemctl start beagle-repo-auto-update.service, /bin/systemctl show -p Id beagle-repo-auto-update.service
SUDOERS
chmod 0440 /etc/sudoers.d/beagle-artifacts-refresh

install -d -m 0755 "$POLKIT_RULES_DIR"
install -m 0644 "$INSTALL_DIR/beagle-host/polkit/beagle-artifacts-refresh.rules" "$POLKIT_RULES_DIR/$ARTIFACT_POLKIT_RULE_NAME"
install -m 0644 "$INSTALL_DIR/beagle-host/polkit/beagle-artifacts-watchdog.rules" "$POLKIT_RULES_DIR/$ARTIFACT_WATCHDOG_POLKIT_RULE_NAME"
install -m 0644 "$INSTALL_DIR/beagle-host/polkit/beagle-repo-auto-update.rules" "$POLKIT_RULES_DIR/$REPO_AUTO_UPDATE_POLKIT_RULE_NAME"
if [[ -f /var/lib/beagle/refresh.status.json ]]; then
  chgrp beagle-manager /var/lib/beagle/refresh.status.json 2>/dev/null || true
  chmod 0640 /var/lib/beagle/refresh.status.json 2>/dev/null || true
fi
if [[ -f /var/lib/beagle/artifact-watchdog-status.json ]]; then
  chgrp beagle-manager /var/lib/beagle/artifact-watchdog-status.json 2>/dev/null || true
  chmod 0640 /var/lib/beagle/artifact-watchdog-status.json 2>/dev/null || true
fi
if [[ -f /var/lib/beagle/repo-auto-update-status.json ]]; then
  chgrp beagle-manager /var/lib/beagle/repo-auto-update-status.json 2>/dev/null || true
  chmod 0640 /var/lib/beagle/repo-auto-update-status.json 2>/dev/null || true
fi

systemctl enable "$TIMER_NAME" 2>/dev/null || true
systemctl enable "$WATCHDOG_TIMER_NAME" 2>/dev/null || true
systemctl enable "$REPO_AUTO_UPDATE_TIMER_NAME" 2>/dev/null || true
if has_ui_reapply_units; then
  systemctl enable "$UI_REAPPLY_SERVICE" 2>/dev/null || true
  systemctl enable "$UI_REAPPLY_PATH" 2>/dev/null || true
else
  systemctl disable "$UI_REAPPLY_SERVICE" 2>/dev/null || true
  systemctl disable "$UI_REAPPLY_PATH" 2>/dev/null || true
  systemctl stop "$UI_REAPPLY_PATH" 2>/dev/null || true
fi
systemctl enable "$BEAGLE_CONTROL_SERVICE" 2>/dev/null || true
systemctl enable "$BEAGLE_CLUSTER_AUTO_JOIN_SERVICE" 2>/dev/null || true
systemctl enable "$BEAGLE_PUBLIC_STREAM_TIMER" 2>/dev/null || true
if [[ "$BEAGLE_HOST_PROVIDER" == "beagle" ]]; then
  systemctl enable "$BEAGLE_NOVNC_PROXY_SERVICE" 2>/dev/null || true
  systemctl start "$BEAGLE_NOVNC_PROXY_SERVICE" 2>/dev/null || true
else
  systemctl disable "$BEAGLE_NOVNC_PROXY_SERVICE" 2>/dev/null || true
  systemctl stop "$BEAGLE_NOVNC_PROXY_SERVICE" 2>/dev/null || true
fi
if has_ui_reapply_units; then
  systemctl start "$TIMER_NAME" "$WATCHDOG_TIMER_NAME" "$REPO_AUTO_UPDATE_TIMER_NAME" "$UI_REAPPLY_PATH" "$BEAGLE_CONTROL_SERVICE" "$BEAGLE_CLUSTER_AUTO_JOIN_SERVICE" "$BEAGLE_PUBLIC_STREAM_TIMER" "$BEAGLE_PUBLIC_STREAM_SERVICE" 2>/dev/null || true
else
  systemctl start "$TIMER_NAME" "$WATCHDOG_TIMER_NAME" "$REPO_AUTO_UPDATE_TIMER_NAME" "$BEAGLE_CONTROL_SERVICE" "$BEAGLE_CLUSTER_AUTO_JOIN_SERVICE" "$BEAGLE_PUBLIC_STREAM_TIMER" "$BEAGLE_PUBLIC_STREAM_SERVICE" 2>/dev/null || true
fi

echo "Installed host services: $SERVICE_NAME, $TIMER_NAME, $WATCHDOG_SERVICE_NAME, $WATCHDOG_TIMER_NAME, $REPO_AUTO_UPDATE_SERVICE_NAME, $REPO_AUTO_UPDATE_TIMER_NAME, $UI_REAPPLY_SERVICE, $UI_REAPPLY_PATH, $BEAGLE_CONTROL_SERVICE, $BEAGLE_CLUSTER_AUTO_JOIN_SERVICE, $BEAGLE_PUBLIC_STREAM_SERVICE, $BEAGLE_PUBLIC_STREAM_TIMER, $BEAGLE_NOVNC_PROXY_SERVICE"
