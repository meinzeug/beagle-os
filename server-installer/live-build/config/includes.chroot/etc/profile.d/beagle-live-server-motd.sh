#!/bin/sh
set -eu

case "$(cat /proc/cmdline 2>/dev/null || true)" in
  *" beagle_server_live=1 "*) ;;
  *) return 0 2>/dev/null || exit 0 ;;
esac

# Show only for interactive login shells.
case "${-:-}" in
  *i*) ;;
  *) return 0 2>/dev/null || exit 0 ;;
esac

BOOTSTRAP_SCRIPT="/usr/local/bin/beagle-live-server-bootstrap"
BOOTSTRAP_STATE_DIR="/run/beagle-live-server"
BOOTSTRAP_DONE_FILE="$BOOTSTRAP_STATE_DIR/bootstrap.done"
BOOTSTRAP_PID_FILE="$BOOTSTRAP_STATE_DIR/bootstrap.pid"
LIVE_WEBUI_USERNAME="${BEAGLE_LIVE_DEFAULT_WEBUI_USERNAME:-admin}"
LIVE_WEBUI_PASSWORD="${BEAGLE_LIVE_DEFAULT_WEBUI_PASSWORD:-test123}"

mkdir -p "$BOOTSTRAP_STATE_DIR"
if [ -x "$BOOTSTRAP_SCRIPT" ] && [ ! -f "$BOOTSTRAP_DONE_FILE" ]; then
  bootstrap_pid=""
  if [ -f "$BOOTSTRAP_PID_FILE" ]; then
    bootstrap_pid="$(cat "$BOOTSTRAP_PID_FILE" 2>/dev/null || true)"
  fi
  if [ -z "$bootstrap_pid" ] || ! kill -0 "$bootstrap_pid" 2>/dev/null; then
    nohup "$BOOTSTRAP_SCRIPT" >/var/log/beagle-live-server-bootstrap.log 2>&1 &
    echo "$!" >"$BOOTSTRAP_PID_FILE"
  fi
fi

detect_primary_ip() {
  local route_ip addr_ip
  route_ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')"
  if [ -n "$route_ip" ]; then
    printf '%s\n' "$route_ip"
    return 0
  fi
  addr_ip="$(ip -4 -o addr show up scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -n1)"
  if [ -n "$addr_ip" ]; then
    printf '%s\n' "$addr_ip"
    return 0
  fi
  hostname -I 2>/dev/null | awk '{print $1}'
}

# At auto-login time DHCP might still be in-flight; wait briefly for a real IPv4.
primary_ip=""
for _ in 1 2 3 4 5 6 7 8 9 10; do
  primary_ip="$(detect_primary_ip || true)"
  if [ -n "$primary_ip" ]; then
    break
  fi
  sleep 1
done
[ -n "$primary_ip" ] || primary_ip="<no-ip-detected>"

if [ "$primary_ip" = "<no-ip-detected>" ]; then
  web_ui_url="https://<host-or-ip>"
  api_url="https://<host-or-ip>/beagle-api/api/v1"
else
  web_ui_url="https://$primary_ip"
  api_url="https://$primary_ip/beagle-api/api/v1"
fi

cat <<EOF

============================================================
 Beagle-OS Live Server
============================================================

Web UI URL:      $web_ui_url
API URL:         $api_url

Live login:
  Username: root
  Password: no password (console auto-login)

Web UI login:
  Username: $LIVE_WEBUI_USERNAME
  Password: $LIVE_WEBUI_PASSWORD

Notes:
  - This is the dedicated live server mode from USB/ISO.
  - Installer autostart is disabled in this mode.
  - Beagle host services are bootstrapped automatically in live mode.
  - If URLs are not reachable yet, wait for bootstrap to finish.

============================================================

EOF