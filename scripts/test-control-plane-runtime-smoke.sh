#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <ssh-host> [<ssh-host> ...]" >&2
  exit 2
fi

run_host() {
  local host="$1"
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$host" '
set -euo pipefail
ENV_FILE="/etc/beagle/beagle-manager.env"
TOKEN_RAW=""
if [[ -f "$ENV_FILE" ]]; then
  TOKEN_RAW="$(sed -n "s/^BEAGLE_MANAGER_API_TOKEN=//p" "$ENV_FILE" | head -n1)"
  if [[ -z "$TOKEN_RAW" ]]; then
    TOKEN_RAW="$(sed -n "s/^BEAGLE_API_TOKEN=//p" "$ENV_FILE" | head -n1)"
  fi
  if [[ -z "$TOKEN_RAW" ]]; then
    TOKEN_RAW="$(sed -n "s/^BEAGLE_MANAGER_TOKEN=//p" "$ENV_FILE" | head -n1)"
  fi
fi
TOKEN="$(printf "%s" "$TOKEN_RAW" | sed -e "s/^\"//" -e "s/\"$//" -e "s/^'\''//" -e "s/'\''$//" | tr -d "\r\n[:space:]")"
STATE="$(systemctl is-active beagle-control-plane)"
echo "HOST=$HOSTNAME SERVICE=beagle-control-plane STATE=$STATE"
if [[ "$STATE" != "active" ]]; then
  systemctl status beagle-control-plane --no-pager -n 20 >&2 || true
  exit 1
fi
if [[ -z "$TOKEN" ]]; then
  echo "missing API token in $ENV_FILE" >&2
  exit 1
fi
HTTP_CODE="$(curl -sS -o /tmp/beagle-control-plane-health.json -w "%{http_code}" -H "Authorization: Bearer $TOKEN" http://127.0.0.1:9088/api/v1/health)"
if [[ "$HTTP_CODE" != "200" ]]; then
  cat /tmp/beagle-control-plane-health.json >&2 || true
  exit 1
fi
echo "HOST=$HOSTNAME API_HEALTH=200"
'
}

for host in "$@"; do
  run_host "$host"
done

echo "CONTROL_PLANE_RUNTIME_SMOKE=PASS hosts=$#"