#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/opt/pve-dcv-integration}"
CONFIG_DIR="${PVE_DCV_CONFIG_DIR:-/etc/pve-dcv-integration}"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_NAME="pve-dcv-artifacts-refresh.service"
TIMER_NAME="pve-dcv-artifacts-refresh.timer"
UI_REAPPLY_SERVICE="pve-dcv-ui-reapply.service"
UI_REAPPLY_PATH="pve-dcv-ui-reapply.path"

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

ensure_root "$@"

install -d -m 0755 "$SYSTEMD_DIR"
install_unit "$ROOT_DIR/proxmox-host/systemd/$SERVICE_NAME" "$SYSTEMD_DIR/$SERVICE_NAME"
install -m 0644 "$ROOT_DIR/proxmox-host/systemd/$TIMER_NAME" "$SYSTEMD_DIR/$TIMER_NAME"
install_unit "$ROOT_DIR/proxmox-host/systemd/$UI_REAPPLY_SERVICE" "$SYSTEMD_DIR/$UI_REAPPLY_SERVICE"
install -m 0644 "$ROOT_DIR/proxmox-host/systemd/$UI_REAPPLY_PATH" "$SYSTEMD_DIR/$UI_REAPPLY_PATH"

systemctl daemon-reload
systemctl enable --now "$TIMER_NAME"
systemctl enable "$UI_REAPPLY_SERVICE"
systemctl enable --now "$UI_REAPPLY_PATH"

echo "Installed host services: $SERVICE_NAME, $TIMER_NAME, $UI_REAPPLY_SERVICE, $UI_REAPPLY_PATH"
