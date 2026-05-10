#!/usr/bin/env bash
set -euo pipefail

WG_IFACE="${WG_IFACE:-wg-beagle}"
WG_CONF="${WG_CONF:-/etc/wireguard/${WG_IFACE}.conf}"
GUARD_INTERVAL="${BEAGLE_WG_GUARD_INTERVAL:-2}"
LOCK_FILE="${BEAGLE_WG_GUARD_LOCK_FILE:-/run/beagle/wg-runtime-guard.lock}"
STATE_FILE="${BEAGLE_WG_GUARD_STATE_FILE:-/run/beagle/wg-runtime-guard.state}"
UNDERLAY_FILE="${BEAGLE_WG_GUARD_UNDERLAY_FILE:-/run/beagle/wg-runtime-underlay.env}"

mkdir -p /run/beagle >/dev/null 2>&1 || true
exec 9>"$LOCK_FILE"
flock -n 9 || exit 0

log_state() {
  local msg="$1"
  if [[ ! -r "$STATE_FILE" ]] || [[ "$(cat "$STATE_FILE" 2>/dev/null)" != "$msg" ]]; then
    printf '%s\n' "$msg" >"$STATE_FILE"
    logger -t beagle-runtime "phase=wg-runtime-guard ${msg}"
  fi
}

conf_value() {
  local key="$1"
  awk -F= -v key="$key" '
    index($0, "=") {
      lhs=substr($0, 1, index($0, "=") - 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", lhs)
      if (lhs == key) {
        value=substr($0, index($0, "=") + 1)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
        print value
        exit
      }
    }
  ' "$WG_CONF"
}

iface_runtime_conf() {
  local out_file="$1"
  awk '
    BEGIN{in_iface=0;in_peer=0}
    /^\[Interface\]/{in_iface=1;in_peer=0;print;next}
    /^\[Peer\]/{in_peer=1;in_iface=0;print;next}
    /^\[/{in_iface=0;in_peer=0;print;next}
    {
      if (in_iface==1) {
        if ($0 ~ /^[[:space:]]*(Address|DNS|MTU|Table|PreUp|PostUp|PreDown|PostDown|SaveConfig)[[:space:]]*=/) next
        print
        next
      }
      print
    }
  ' "$WG_CONF" >"$out_file"
}

ensure_iface() {
  local tmp_conf addr mtu
  if ! ip link show "$WG_IFACE" >/dev/null 2>&1; then
    tmp_conf="$(mktemp)"
    iface_runtime_conf "$tmp_conf"
    ip link add "$WG_IFACE" type wireguard >/dev/null 2>&1 || true
    wg setconf "$WG_IFACE" "$tmp_conf" >/dev/null 2>&1 || true
    rm -f "$tmp_conf" >/dev/null 2>&1 || true
    addr="$(conf_value Address | tr -d '[:space:]' | awk -F',' '{print $1}')"
    mtu="$(conf_value MTU | tr -d '[:space:]')"
    [[ -n "$mtu" ]] || mtu=1420
    [[ -n "$addr" ]] && ip address add "$addr" dev "$WG_IFACE" >/dev/null 2>&1 || true
    ip link set mtu "$mtu" up dev "$WG_IFACE" >/dev/null 2>&1 || true
    log_state "iface=recreated mtu=${mtu}"
    return
  fi
  ip link set up dev "$WG_IFACE" >/dev/null 2>&1 || true
}

ensure_routes() {
  local endpoint endpoint_host default_route default_gw default_dev
  local allowed route_count route
  local underlay_dev underlay_addr underlay_ip guessed_gw

  endpoint="$(conf_value Endpoint)"
  endpoint_host="${endpoint%%:*}"
  endpoint_host="${endpoint_host#[}"
  endpoint_host="${endpoint_host%]}"
  default_route="$(ip route show default 2>/dev/null | awk -v iface="$WG_IFACE" '$0 !~ (" dev " iface "( |$)") { print; exit }' || true)"
  default_gw=""
  default_dev=""
  if [[ -n "$default_route" ]]; then
    default_gw="$(awk '/default/{for(i=1;i<=NF;i++) if ($i=="via") {print $(i+1); exit}}' <<<"$default_route")"
    default_dev="$(awk '/default/{for(i=1;i<=NF;i++) if ($i=="dev") {print $(i+1); exit}}' <<<"$default_route")"
  fi
  if [[ -z "$default_route" && -r "$UNDERLAY_FILE" ]]; then
    default_gw="$(awk -F= '$1=="UNDERLAY_GW"{print substr($0, index($0, "=")+1); exit}' "$UNDERLAY_FILE")"
    default_dev="$(awk -F= '$1=="UNDERLAY_DEV"{print substr($0, index($0, "=")+1); exit}' "$UNDERLAY_FILE")"
  fi

  if [[ -z "$default_dev" ]]; then
    underlay_dev="$(ip -o -4 addr show up scope global 2>/dev/null | awk -v iface="$WG_IFACE" '$2 != iface {print $2; exit}')"
    underlay_addr="$(ip -o -4 addr show dev "$underlay_dev" scope global 2>/dev/null | awk 'NR==1 {print $4}')"
    underlay_ip="${underlay_addr%%/*}"
    guessed_gw="${BEAGLE_WG_GUARD_UNDERLAY_GATEWAY:-}"
    if [[ -z "$guessed_gw" && "$underlay_ip" =~ ^([0-9]+\.[0-9]+\.[0-9]+)\.[0-9]+$ ]]; then
      guessed_gw="${BASH_REMATCH[1]}.1"
    fi
    if [[ -n "$underlay_dev" && -n "$guessed_gw" ]]; then
      ip route replace default via "$guessed_gw" dev "$underlay_dev" >/dev/null 2>&1 || true
      default_dev="$underlay_dev"
      default_gw="$guessed_gw"
      log_state "underlay=restored dev=${underlay_dev} gw=${guessed_gw}"
    fi
  fi

  if [[ -n "$default_dev" ]]; then
    {
      printf 'UNDERLAY_GW=%s\n' "$default_gw"
      printf 'UNDERLAY_DEV=%s\n' "$default_dev"
    } >"$UNDERLAY_FILE"
  fi

  if [[ -n "$endpoint_host" && -n "$default_dev" ]]; then
    if [[ -n "$default_gw" ]]; then
      ip route replace "$endpoint_host" via "$default_gw" dev "$default_dev" >/dev/null 2>&1 || true
    else
      ip route replace "$endpoint_host" dev "$default_dev" >/dev/null 2>&1 || true
    fi
  fi

  allowed="$(conf_value AllowedIPs | tr -d '[:space:]')"
  route_count=0
  IFS=',' read -r -a routes <<<"$allowed"
  for route in "${routes[@]}"; do
    [[ -n "$route" ]] || continue
    case "$route" in
      0.0.0.0/0)
        ip route replace 0.0.0.0/1 dev "$WG_IFACE" >/dev/null 2>&1 || true
        ip route replace 128.0.0.0/1 dev "$WG_IFACE" >/dev/null 2>&1 || true
        ;;
      ::/0)
        ip -6 route replace ::/1 dev "$WG_IFACE" >/dev/null 2>&1 || true
        ip -6 route replace 8000::/1 dev "$WG_IFACE" >/dev/null 2>&1 || true
        ;;
      *:*)
        ip -6 route replace "$route" dev "$WG_IFACE" >/dev/null 2>&1 || true
        ;;
      *)
        ip route replace "$route" dev "$WG_IFACE" >/dev/null 2>&1 || true
        ;;
    esac
    route_count=$((route_count + 1))
  done

  log_state "iface=up routes=${route_count} endpoint=${endpoint_host:-none}"
}

while :; do
  if [[ ! -r "$WG_CONF" ]]; then
    log_state "conf=missing path=${WG_CONF}"
    sleep "$GUARD_INTERVAL"
    continue
  fi
  ensure_iface
  ensure_routes
  sleep "$GUARD_INTERVAL"
done
