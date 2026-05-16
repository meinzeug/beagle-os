#!/usr/bin/env bash
set -euo pipefail

REQUEST_FILE="${BEAGLE_FIREWALL_ACTION_FILE:-/run/beagle-control-plane/firewall-action.env}"
STATUS_FILE="${BEAGLE_FIREWALL_STATUS_FILE:-/run/beagle-control-plane/firewall-action.status}"
FIREWALL_SCRIPT="${BEAGLE_FIREWALL_SCRIPT:-/opt/beagle/scripts/apply-beagle-firewall.sh}"

die() {
  echo "$*" >&2
  exit 2
}

decode_b64() {
  local value="$1"
  if command -v base64 >/dev/null 2>&1; then
    printf '%s' "$value" | base64 -d 2>/dev/null
  else
    python3 -c 'import base64,sys; sys.stdout.write(base64.b64decode(sys.argv[1]).decode())' "$value"
  fi
}

encode_b64() {
  if command -v base64 >/dev/null 2>&1; then
    base64 | tr -d '\n'
  else
    python3 -c 'import base64,sys; sys.stdout.write(base64.b64encode(sys.stdin.buffer.read()).decode())'
  fi
}

run_firewall() {
  local output rc encoded tmp
  set +e
  output="$("$FIREWALL_SCRIPT" "$@" 2>&1)"
  rc=$?
  set -e
  encoded="$(printf '%s' "$output" | encode_b64)"
  tmp="${STATUS_FILE}.$$"
  {
    printf 'BEAGLE_FIREWALL_RC=%s\n' "$rc"
    printf 'BEAGLE_FIREWALL_OUTPUT_B64=%s\n' "$encoded"
  } >"$tmp"
  chgrp beagle-manager "$tmp" 2>/dev/null || true
  chmod 0640 "$tmp" 2>/dev/null || true
  mv "$tmp" "$STATUS_FILE"
  if [[ "$rc" -eq 0 ]]; then
    [[ -z "$output" ]] || printf '%s\n' "$output"
  else
    [[ -z "$output" ]] || printf '%s\n' "$output" >&2
  fi
  exit "$rc"
}

[[ -x "$FIREWALL_SCRIPT" ]] || die "firewall script not executable: $FIREWALL_SCRIPT"
[[ -f "$REQUEST_FILE" ]] || die "firewall action request not found: $REQUEST_FILE"

action=""
arg=""
while IFS='=' read -r key value; do
  case "$key" in
    BEAGLE_FIREWALL_ACTION)
      action="$value"
      ;;
    BEAGLE_FIREWALL_ARG_B64)
      arg="$(decode_b64 "$value")"
      ;;
  esac
done <"$REQUEST_FILE"

case "$action" in
  enable)
    run_firewall --enable
    ;;
  disable)
    run_firewall --disable
    ;;
  status)
    run_firewall --status
    ;;
  add-extra-rule)
    [[ "$arg" =~ ^(tcp|udp)[[:space:]]dport[[:space:]][0-9]{1,5}[[:space:]](accept|drop)$ ]] ||
      die "invalid firewall extra rule request"
    run_firewall --add-extra-rule "$arg"
    ;;
  delete-extra-rule)
    [[ "$arg" =~ ^[0-9]+$ ]] || die "invalid firewall delete request"
    run_firewall --delete-extra-rule "$arg"
    ;;
  *)
    die "invalid firewall action request"
    ;;
esac
