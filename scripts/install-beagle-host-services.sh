#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/opt/beagle}"
HOST_RUNTIME_DIR="$INSTALL_DIR/beagle-host"
LEGACY_HOST_RUNTIME_DIR="$INSTALL_DIR/proxmox-host"
CONFIG_DIR="${PVE_DCV_CONFIG_DIR:-/etc/beagle}"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_NAME="beagle-artifacts-refresh.service"
TIMER_NAME="beagle-artifacts-refresh.timer"
UI_REAPPLY_SERVICE="beagle-ui-reapply.service"
UI_REAPPLY_PATH="beagle-ui-reapply.path"
BEAGLE_CONTROL_SERVICE="beagle-control-plane.service"
BEAGLE_PUBLIC_STREAM_SERVICE="beagle-public-streams.service"
BEAGLE_PUBLIC_STREAM_TIMER="beagle-public-streams.timer"
BEAGLE_CONTROL_ENV_FILE="$CONFIG_DIR/beagle-manager.env"
BEAGLE_HOST_PROVIDER="${BEAGLE_HOST_PROVIDER:-beagle}"
BEAGLE_AUTH_BOOTSTRAP_USERNAME="${BEAGLE_AUTH_BOOTSTRAP_USERNAME:-admin}"
BEAGLE_AUTH_BOOTSTRAP_PASSWORD="${BEAGLE_AUTH_BOOTSTRAP_PASSWORD:-}"
USB_TUNNEL_USER="${BEAGLE_USB_TUNNEL_SSH_USER:-beagle}"
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
      BEAGLE_AUTH_BOOTSTRAP_USERNAME="$BEAGLE_AUTH_BOOTSTRAP_USERNAME" \
      BEAGLE_AUTH_BOOTSTRAP_PASSWORD="$BEAGLE_AUTH_BOOTSTRAP_PASSWORD" \
      "$0" "$@"
  fi

  echo "This installer must run as root or use sudo." >&2
  exit 1
}

install_unit() {
  local source_file="$1"
  local target_file="$2"

  sed "s|__INSTALL_DIR__|$INSTALL_DIR|g" "$source_file" > "$target_file"
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

ensure_root "$@"

if ! id "$USB_TUNNEL_USER" >/dev/null 2>&1; then
  if [[ -z "$USB_TUNNEL_HOME" ]]; then
    USB_TUNNEL_HOME="/var/lib/beagle/${USB_TUNNEL_USER}"
  fi
  useradd --system --home-dir "$USB_TUNNEL_HOME" --create-home --shell /bin/bash "$USB_TUNNEL_USER"
  usermod -p "$(generate_password_hash)" "$USB_TUNNEL_USER"
fi
if [[ -z "$USB_TUNNEL_HOME" ]]; then
  USB_TUNNEL_HOME="$(getent passwd "$USB_TUNNEL_USER" | cut -d: -f6)"
fi
install -d -m 0755 "$USB_TUNNEL_HOME"
install -d -m 0755 "$(dirname "$USB_TUNNEL_AUTH_ROOT")"
install -d -m 0700 "$USB_TUNNEL_AUTH_ROOT" "$USB_TUNNEL_AUTH_ROOT/authorized_keys.d"
touch "$USB_TUNNEL_AUTH_ROOT/authorized_keys"
chmod 0600 "$USB_TUNNEL_AUTH_ROOT/authorized_keys"
chown "$USB_TUNNEL_USER:$USB_TUNNEL_USER" "$USB_TUNNEL_AUTH_ROOT" "$USB_TUNNEL_AUTH_ROOT/authorized_keys.d" "$USB_TUNNEL_AUTH_ROOT/authorized_keys"

cat >"$USB_TUNNEL_SSHD_DROPIN" <<EOF
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
install_unit "$ROOT_DIR/beagle-host/systemd/$SERVICE_NAME" "$SYSTEMD_DIR/$SERVICE_NAME"
install -m 0644 "$ROOT_DIR/beagle-host/systemd/$TIMER_NAME" "$SYSTEMD_DIR/$TIMER_NAME"
install_unit "$ROOT_DIR/beagle-host/systemd/$UI_REAPPLY_SERVICE" "$SYSTEMD_DIR/$UI_REAPPLY_SERVICE"
install -m 0644 "$ROOT_DIR/beagle-host/systemd/$UI_REAPPLY_PATH" "$SYSTEMD_DIR/$UI_REAPPLY_PATH"
install_unit "$ROOT_DIR/beagle-host/systemd/$BEAGLE_CONTROL_SERVICE" "$SYSTEMD_DIR/$BEAGLE_CONTROL_SERVICE"
install_unit "$ROOT_DIR/beagle-host/systemd/$BEAGLE_PUBLIC_STREAM_SERVICE" "$SYSTEMD_DIR/$BEAGLE_PUBLIC_STREAM_SERVICE"
install -m 0644 "$ROOT_DIR/beagle-host/systemd/$BEAGLE_PUBLIC_STREAM_TIMER" "$SYSTEMD_DIR/$BEAGLE_PUBLIC_STREAM_TIMER"
if [[ "$(readlink -f "$ROOT_DIR/beagle-host/bin/beagle-control-plane.py")" != "$(readlink -f "$HOST_RUNTIME_DIR/bin/beagle-control-plane.py" 2>/dev/null || true)" ]]; then
  install -m 0755 "$ROOT_DIR/beagle-host/bin/beagle-control-plane.py" "$HOST_RUNTIME_DIR/bin/beagle-control-plane.py"
fi
if [[ "$(readlink -f "$ROOT_DIR/beagle-host/bin/beagle-usb-tunnel-session")" != "$(readlink -f "$HOST_RUNTIME_DIR/bin/beagle-usb-tunnel-session" 2>/dev/null || true)" ]]; then
  install -m 0755 "$ROOT_DIR/beagle-host/bin/beagle-usb-tunnel-session" "$HOST_RUNTIME_DIR/bin/beagle-usb-tunnel-session"
fi
if [[ "$(readlink -f "$ROOT_DIR/beagle-host/bin/endpoint_profile_contract.py")" != "$(readlink -f "$HOST_RUNTIME_DIR/bin/endpoint_profile_contract.py" 2>/dev/null || true)" ]]; then
  install -m 0644 "$ROOT_DIR/beagle-host/bin/endpoint_profile_contract.py" "$HOST_RUNTIME_DIR/bin/endpoint_profile_contract.py"
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
if [[ -e "$LEGACY_HOST_RUNTIME_DIR" && ! -L "$LEGACY_HOST_RUNTIME_DIR" ]]; then
  rm -rf "$LEGACY_HOST_RUNTIME_DIR"
fi
ln -sfn "$HOST_RUNTIME_DIR" "$LEGACY_HOST_RUNTIME_DIR"
rm -f "$USB_TUNNEL_TEST_DROPIN" "$USB_TUNNEL_AUTH_COMMAND"

install -d -m 0755 "$CONFIG_DIR"
if [[ ! -f "$BEAGLE_CONTROL_ENV_FILE" ]]; then
  cat > "$BEAGLE_CONTROL_ENV_FILE" <<EOF
BEAGLE_MANAGER_LISTEN_HOST="127.0.0.1"
BEAGLE_MANAGER_LISTEN_PORT="9088"
BEAGLE_MANAGER_DATA_DIR="/var/lib/beagle/beagle-manager"
BEAGLE_MANAGER_API_TOKEN="$(generate_token)"
BEAGLE_MANAGER_ALLOW_LOCALHOST_NOAUTH="0"
EOF
  chmod 0600 "$BEAGLE_CONTROL_ENV_FILE"
fi
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_HOST_PROVIDER" "\"$BEAGLE_HOST_PROVIDER\""
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_MANAGER_LISTEN_HOST" '"127.0.0.1"'
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_MANAGER_ALLOW_LOCALHOST_NOAUTH" '"0"'
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_USB_TUNNEL_SSH_USER" "\"$USB_TUNNEL_USER\""
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_USB_TUNNEL_AUTH_ROOT" "\"$USB_TUNNEL_AUTH_ROOT\""
if [[ -n "$BEAGLE_AUTH_BOOTSTRAP_USERNAME" ]]; then
  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_AUTH_BOOTSTRAP_USERNAME" "\"$BEAGLE_AUTH_BOOTSTRAP_USERNAME\""
fi
if [[ -n "$BEAGLE_AUTH_BOOTSTRAP_PASSWORD" ]]; then
  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_AUTH_BOOTSTRAP_PASSWORD" "\"$BEAGLE_AUTH_BOOTSTRAP_PASSWORD\""
  set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_AUTH_BOOTSTRAP_DISABLE" "\"0\""
fi

if grep -q '^BEAGLE_ENDPOINT_SHARED_TOKEN=' "$BEAGLE_CONTROL_ENV_FILE"; then
  sed -i '/^BEAGLE_ENDPOINT_SHARED_TOKEN=/d' "$BEAGLE_CONTROL_ENV_FILE"
fi

systemctl daemon-reload 2>/dev/null || true
systemctl restart ssh.service >/dev/null 2>&1 || systemctl restart sshd.service >/dev/null 2>&1 || true
systemctl enable "$TIMER_NAME" 2>/dev/null || true
systemctl enable "$UI_REAPPLY_SERVICE" 2>/dev/null || true
systemctl enable "$UI_REAPPLY_PATH" 2>/dev/null || true
systemctl enable "$BEAGLE_CONTROL_SERVICE" 2>/dev/null || true
systemctl enable "$BEAGLE_PUBLIC_STREAM_TIMER" 2>/dev/null || true
systemctl start "$TIMER_NAME" "$UI_REAPPLY_PATH" "$BEAGLE_CONTROL_SERVICE" "$BEAGLE_PUBLIC_STREAM_TIMER" "$BEAGLE_PUBLIC_STREAM_SERVICE" 2>/dev/null || true

echo "Installed host services: $SERVICE_NAME, $TIMER_NAME, $UI_REAPPLY_SERVICE, $UI_REAPPLY_PATH, $BEAGLE_CONTROL_SERVICE, $BEAGLE_PUBLIC_STREAM_SERVICE, $BEAGLE_PUBLIC_STREAM_TIMER"
