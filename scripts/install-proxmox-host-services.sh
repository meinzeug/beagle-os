#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/opt/beagle}"
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
USB_TUNNEL_USER="${BEAGLE_USB_TUNNEL_SSH_USER:-thinovernet}"
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
    PermitTTY no
    X11Forwarding no
    GatewayPorts clientspecified
EOF
chmod 0644 "$USB_TUNNEL_SSHD_DROPIN"

install -d -m 0755 "$SYSTEMD_DIR"
install -d -m 0755 "$INSTALL_DIR/proxmox-host/bin"
install_unit "$ROOT_DIR/proxmox-host/systemd/$SERVICE_NAME" "$SYSTEMD_DIR/$SERVICE_NAME"
install -m 0644 "$ROOT_DIR/proxmox-host/systemd/$TIMER_NAME" "$SYSTEMD_DIR/$TIMER_NAME"
install_unit "$ROOT_DIR/proxmox-host/systemd/$UI_REAPPLY_SERVICE" "$SYSTEMD_DIR/$UI_REAPPLY_SERVICE"
install -m 0644 "$ROOT_DIR/proxmox-host/systemd/$UI_REAPPLY_PATH" "$SYSTEMD_DIR/$UI_REAPPLY_PATH"
install_unit "$ROOT_DIR/proxmox-host/systemd/$BEAGLE_CONTROL_SERVICE" "$SYSTEMD_DIR/$BEAGLE_CONTROL_SERVICE"
install_unit "$ROOT_DIR/proxmox-host/systemd/$BEAGLE_PUBLIC_STREAM_SERVICE" "$SYSTEMD_DIR/$BEAGLE_PUBLIC_STREAM_SERVICE"
install -m 0644 "$ROOT_DIR/proxmox-host/systemd/$BEAGLE_PUBLIC_STREAM_TIMER" "$SYSTEMD_DIR/$BEAGLE_PUBLIC_STREAM_TIMER"
if [[ "$(readlink -f "$ROOT_DIR/proxmox-host/bin/beagle-control-plane.py")" != "$(readlink -f "$INSTALL_DIR/proxmox-host/bin/beagle-control-plane.py" 2>/dev/null || true)" ]]; then
  install -m 0755 "$ROOT_DIR/proxmox-host/bin/beagle-control-plane.py" "$INSTALL_DIR/proxmox-host/bin/beagle-control-plane.py"
fi
if [[ "$(readlink -f "$ROOT_DIR/proxmox-host/bin/beagle-usb-tunnel-session")" != "$(readlink -f "$INSTALL_DIR/proxmox-host/bin/beagle-usb-tunnel-session" 2>/dev/null || true)" ]]; then
  install -m 0755 "$ROOT_DIR/proxmox-host/bin/beagle-usb-tunnel-session" "$INSTALL_DIR/proxmox-host/bin/beagle-usb-tunnel-session"
fi
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
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_USB_TUNNEL_SSH_USER" "\"$USB_TUNNEL_USER\""
set_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_USB_TUNNEL_AUTH_ROOT" "\"$USB_TUNNEL_AUTH_ROOT\""

if grep -q '^BEAGLE_ENDPOINT_SHARED_TOKEN=' "$BEAGLE_CONTROL_ENV_FILE"; then
  sed -i '/^BEAGLE_ENDPOINT_SHARED_TOKEN=/d' "$BEAGLE_CONTROL_ENV_FILE"
fi

systemctl daemon-reload
systemctl restart ssh.service >/dev/null 2>&1 || systemctl restart sshd.service >/dev/null 2>&1 || true
systemctl enable --now "$TIMER_NAME"
systemctl enable "$UI_REAPPLY_SERVICE"
systemctl enable --now "$UI_REAPPLY_PATH"
systemctl enable --now "$BEAGLE_CONTROL_SERVICE"
systemctl enable --now "$BEAGLE_PUBLIC_STREAM_TIMER"
systemctl start "$BEAGLE_PUBLIC_STREAM_SERVICE" >/dev/null 2>&1 || true

echo "Installed host services: $SERVICE_NAME, $TIMER_NAME, $UI_REAPPLY_SERVICE, $UI_REAPPLY_PATH, $BEAGLE_CONTROL_SERVICE, $BEAGLE_PUBLIC_STREAM_SERVICE, $BEAGLE_PUBLIC_STREAM_TIMER"
