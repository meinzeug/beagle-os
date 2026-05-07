#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${PVE_DCV_CONFIG_DIR:-/etc/beagle}"
MANAGER_ENV_FILE="${BEAGLE_MANAGER_ENV_FILE:-$CONFIG_DIR/beagle-manager.env}"
HOST_ENV_FILE="${PVE_DCV_HOST_ENV_FILE:-$CONFIG_DIR/host.env}"
NFTABLES_CONF="${BEAGLE_NFTABLES_CONF:-/etc/nftables.conf}"
NFT_RULE_FILE="${BEAGLE_FIREWALL_RULE_FILE:-$CONFIG_DIR/beagle-firewall.nft}"
EXTRA_RULE_FILE="${BEAGLE_FIREWALL_EXTRA_RULE_FILE:-$CONFIG_DIR/beagle-firewall-extra.rules}"
TABLE_NAME="${BEAGLE_FIREWALL_TABLE:-beagle_guard}"
LEGACY_PUBLIC_STREAM_TABLE="${BEAGLE_LEGACY_PUBLIC_STREAM_TABLE:-beagle_stream}"
ACTION="${1:---enable}"
ACTION_ARG="${2:-}"

source_env_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    # shellcheck disable=SC1090
    set -a; source "$file"; set +a
  fi
}

normalize_csv() {
  printf '%s\n' "$*" | tr ',;' '  ' | xargs -n1 2>/dev/null | sed '/^$/d' | sort -u
}

is_ipv4_cidr() {
  [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,2})?$ ]]
}

is_ipv6_cidr() {
  [[ "$1" == *:* && "$1" =~ ^[0-9A-Fa-f:]+(/[0-9]{1,3})?$ ]]
}

nft_quote_list() {
  local item
  local first=1
  for item in "$@"; do
    [[ -z "$item" ]] && continue
    if [[ "$first" -eq 0 ]]; then
      printf ', '
    fi
    printf '"%s"' "$item"
    first=0
  done
}

nft_addr_list() {
  local item
  local first=1
  for item in "$@"; do
    [[ -z "$item" ]] && continue
    if [[ "$first" -eq 0 ]]; then
      printf ', '
    fi
    printf '%s' "$item"
    first=0
  done
}

detect_vm_bridges() {
  local configured="${BEAGLE_PUBLIC_STREAM_LAN_IF:-virbr10}"
  local bridge
  normalize_csv "$configured virbr10 virbr0"
  if command -v ip >/dev/null 2>&1; then
    ip -o link show 2>/dev/null | awk -F': ' '/: virbr[0-9]+:/{print $2}' | cut -d@ -f1 | sort -u
  fi
}

detect_public_ipv4() {
  local configured="${BEAGLE_PUBLIC_STREAM_GUARD_ADDR:-${BEAGLE_PUBLIC_IPV4:-}}"
  if [[ -n "$configured" ]]; then
    printf '%s\n' "$configured"
    return 0
  fi
  if command -v ip >/dev/null 2>&1; then
    ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i == "src") {print $(i+1); exit}}'
  fi
}

detect_existing_cluster_peers() {
  if command -v iptables >/dev/null 2>&1; then
    iptables -S BEAGLE_CLUSTER_RPC_9089 2>/dev/null |
      awk '$1 == "-A" && $3 == "-s" && $5 == "-j" && $6 == "ACCEPT" {print $4}' |
      grep -Ev '^127\.|^::1(/|$)' || true
    iptables -S BEAGLE_CLUSTER_API_9088 2>/dev/null |
      awk '$1 == "-A" && $3 == "-s" && $5 == "-j" && $6 == "ACCEPT" {print $4}' |
      grep -Ev '^127\.|^::1(/|$)' || true
  fi
}

install_extra_rule_file() {
  local source_file="$1"
  local group_name="root"

  if getent group beagle-manager >/dev/null 2>&1; then
    group_name="beagle-manager"
  fi
  install -m 0640 -o root -g "$group_name" "$source_file" "$EXTRA_RULE_FILE"
}

read_extra_rules() {
  [[ -f "$EXTRA_RULE_FILE" ]] || return 0
  sed '/^[[:space:]]*$/d; /^[[:space:]]*#/d' "$EXTRA_RULE_FILE"
}

write_extra_rules() {
  local tmp
  tmp="$(mktemp)"
  {
    echo "# Managed by Beagle Web Console. Syntax is nft input-chain snippets."
    cat
  } >"$tmp"
  install_extra_rule_file "$tmp"
  rm -f "$tmp"
}

add_extra_rule() {
  local rule="$1"
  local tmp
  if [[ -z "$rule" || "$rule" == *$'\n'* ]]; then
    echo "invalid extra firewall rule" >&2
    return 2
  fi
  tmp="$(mktemp)"
  read_extra_rules | grep -Fxv "$rule" >"$tmp" || true
  printf '%s\n' "$rule" >>"$tmp"
  write_extra_rules <"$tmp"
  rm -f "$tmp"
}

delete_extra_rule() {
  local rule_number="$1"
  local tmp
  if [[ ! "$rule_number" =~ ^[0-9]+$ || "$rule_number" -lt 1 ]]; then
    echo "invalid extra firewall rule number" >&2
    return 2
  fi
  tmp="$(mktemp)"
  read_extra_rules | awk -v n="$rule_number" 'NR != n {print}' >"$tmp"
  write_extra_rules <"$tmp"
  rm -f "$tmp"
}

write_nft_rules() {
  local bridges=()
  local peers=()
  local ipv4_peers=()
  local ipv6_peers=()
  local bridge_set=""
  local ipv4_peer_set=""
  local ipv6_peer_set=""
  local peer
  local wg_enabled=0
  local wg_iface=""
  local wg_port=""
  local public_stream_guard_enabled="${BEAGLE_PUBLIC_STREAM_GUARD_ENABLED:-1}"
  local public_stream_addr=""

  mapfile -t bridges < <(detect_vm_bridges | sed '/^$/d' | sort -u)
  if [[ "${#bridges[@]}" -eq 0 ]]; then
    bridges=("virbr10" "virbr0")
  fi
  bridge_set="$(nft_quote_list "${bridges[@]}")"

  mapfile -t peers < <(
    {
      normalize_csv "${BEAGLE_FIREWALL_CLUSTER_PEERS:-}" "${BEAGLE_CLUSTER_ALLOWED_PEERS:-}" "${BEAGLE_CLUSTER_PEERS:-}"
      detect_existing_cluster_peers
    } | sed '/^$/d' | sort -u
  )
  for peer in "${peers[@]}"; do
    peer="${peer#http://}"
    peer="${peer#https://}"
    peer="${peer%%/*}"
    peer="${peer%%:*}"
    if is_ipv4_cidr "$peer"; then
      ipv4_peers+=("$peer")
    elif is_ipv6_cidr "$peer"; then
      ipv6_peers+=("$peer")
    fi
  done
  ipv4_peer_set="$(nft_addr_list "${ipv4_peers[@]}")"
  ipv6_peer_set="$(nft_addr_list "${ipv6_peers[@]}")"
  if [[ "${BEAGLE_WIREGUARD_ENABLED:-0}" =~ ^(1|true|yes|on)$ ]]; then
    wg_enabled=1
    wg_iface="${BEAGLE_WIREGUARD_INTERFACE:-wg-beagle}"
    wg_port="${BEAGLE_WIREGUARD_PORT:-51820}"
  fi
  if [[ "$public_stream_guard_enabled" =~ ^(1|true|yes|on)$ ]]; then
    public_stream_addr="$(detect_public_ipv4 | head -n1)"
  fi

  install -d -m 0755 "$CONFIG_DIR"
  {
    cat <<EOF
table inet $TABLE_NAME {
EOF
    if [[ -n "$public_stream_addr" && "$public_stream_addr" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
      cat <<EOF
  chain prerouting {
    type filter hook prerouting priority -110; policy accept;

    ip daddr $public_stream_addr tcp dport { 49995, 50000, 50001, 50021 } drop
    ip daddr $public_stream_addr udp dport { 50009, 50010, 50011, 50012, 50013, 50014, 50015 } drop
  }

EOF
    fi
    cat <<EOF
  chain input {
    type filter hook input priority -20; policy drop;

    ct state invalid drop
    ct state { established, related } accept
    iifname "lo" accept

    ip protocol icmp accept
    ip6 nexthdr icmpv6 accept

    tcp dport 22 ct state new limit rate 30/minute burst 30 packets accept
    tcp dport { 80, 443 } ct state new limit rate 300/minute burst 300 packets accept
EOF
    if [[ "$wg_enabled" -eq 1 ]]; then
      printf '    udp dport %s ct state new limit rate 300/minute burst 300 packets accept\n' "$wg_port"
    fi
    cat <<EOF
    iifname { $bridge_set } udp dport { 53, 67 } accept
    iifname { $bridge_set } tcp dport 53 accept
    iifname { $bridge_set } tcp dport { 9088, 9089 } accept
EOF
    if [[ -n "$ipv4_peer_set" ]]; then
      printf '    ip saddr { %s } tcp dport { 9088, 9089 } accept\n' "$ipv4_peer_set"
    fi
    if [[ -n "$ipv6_peer_set" ]]; then
      printf '    ip6 saddr { %s } tcp dport { 9088, 9089 } accept\n' "$ipv6_peer_set"
    fi
    if [[ -f "$EXTRA_RULE_FILE" ]]; then
      while IFS= read -r line; do
        [[ -z "$line" || "$line" == \#* ]] && continue
        printf '    %s\n' "$line"
      done <"$EXTRA_RULE_FILE"
    fi
    cat <<EOF
  }

  chain forward {
    type filter hook forward priority -20; policy drop;

    ct state invalid drop
    ct state { established, related } accept
EOF
    if [[ "$wg_enabled" -eq 1 ]]; then
      printf '    iifname "%s" accept\n' "$wg_iface"
    fi
    cat <<EOF
    iifname { $bridge_set } accept
    ct status dnat oifname { $bridge_set } accept
  }

  chain output {
    type filter hook output priority -20; policy accept;
  }
}
EOF
  } >"$NFT_RULE_FILE.tmp"

  local nft_check_output=""
  if ! nft_check_output="$(nft --check -f "$NFT_RULE_FILE.tmp" 2>&1)"; then
    if ! grep -qi 'Operation not permitted' <<<"$nft_check_output"; then
      printf '%s\n' "$nft_check_output" >&2
      return 1
    fi
    echo "Warning: nft syntax check skipped because netlink is not permitted in this environment" >&2
  fi
  install -m 0644 "$NFT_RULE_FILE.tmp" "$NFT_RULE_FILE"
  rm -f "$NFT_RULE_FILE.tmp"

  cat >"$NFTABLES_CONF" <<EOF
#!/usr/sbin/nft -f
include "$NFT_RULE_FILE"
EOF
  chmod 0644 "$NFTABLES_CONF"
}

apply_rules() {
  if ! command -v nft >/dev/null 2>&1; then
    echo "nft command not found; install nftables first" >&2
    return 1
  fi
  if [[ -n "$LEGACY_PUBLIC_STREAM_TABLE" && "$LEGACY_PUBLIC_STREAM_TABLE" != "$TABLE_NAME" ]]; then
    nft delete table inet "$LEGACY_PUBLIC_STREAM_TABLE" >/dev/null 2>&1 || true
  fi
  if [[ -d /run/systemd/system ]]; then
    systemctl enable nftables >/dev/null 2>&1 || true
    if ! systemctl is-active --quiet nftables; then
      nft delete table inet "$TABLE_NAME" >/dev/null 2>&1 || true
      systemctl start nftables >/dev/null 2>&1 || true
      if nft list table inet "$TABLE_NAME" >/dev/null 2>&1; then
        return 0
      fi
    fi
  fi
  nft delete table inet "$TABLE_NAME" >/dev/null 2>&1 || true
  nft -f "$NFT_RULE_FILE"
}

ensure_libvirt_wireguard_forward_rules() {
  local bridges=()
  local bridge
  local wg_iface="${BEAGLE_WIREGUARD_INTERFACE:-wg-beagle}"

  [[ "${BEAGLE_WIREGUARD_ENABLED:-0}" =~ ^(1|true|yes|on)$ ]] || return 0
  command -v nft >/dev/null 2>&1 || return 0
  nft list table ip filter >/dev/null 2>&1 || return 0

  mapfile -t bridges < <(detect_vm_bridges | sed '/^$/d' | sort -u)
  if [[ "${#bridges[@]}" -eq 0 ]]; then
    bridges=("virbr10" "virbr0")
  fi

  for bridge in "${bridges[@]}"; do
    if nft list chain ip filter FORWARD >/dev/null 2>&1 &&
       ! nft list chain ip filter FORWARD 2>/dev/null | grep -Fq "beagle-wireguard-forward-to-${bridge}"; then
      nft insert rule ip filter FORWARD iifname "$wg_iface" oifname "$bridge" accept comment "beagle-wireguard-forward-to-${bridge}" >/dev/null 2>&1 || true
    fi
    if nft list chain ip filter FORWARD >/dev/null 2>&1 &&
       ! nft list chain ip filter FORWARD 2>/dev/null | grep -Fq "beagle-wireguard-forward-from-${bridge}"; then
      nft insert rule ip filter FORWARD iifname "$bridge" oifname "$wg_iface" accept comment "beagle-wireguard-forward-from-${bridge}" >/dev/null 2>&1 || true
    fi
    if nft list chain ip filter LIBVIRT_FWI >/dev/null 2>&1 &&
       ! nft list chain ip filter LIBVIRT_FWI 2>/dev/null | grep -Fq "beagle-wireguard-to-${bridge}"; then
      nft insert rule ip filter LIBVIRT_FWI iifname "$wg_iface" oifname "$bridge" accept comment "beagle-wireguard-to-${bridge}" >/dev/null 2>&1 || true
    fi
    if nft list chain ip filter LIBVIRT_FWO >/dev/null 2>&1 &&
       ! nft list chain ip filter LIBVIRT_FWO 2>/dev/null | grep -Fq "beagle-wireguard-from-${bridge}"; then
      nft insert rule ip filter LIBVIRT_FWO iifname "$bridge" oifname "$wg_iface" accept comment "beagle-wireguard-from-${bridge}" >/dev/null 2>&1 || true
    fi
  done
}

disable_rules() {
  if command -v nft >/dev/null 2>&1; then
    nft delete table inet "$TABLE_NAME" >/dev/null 2>&1 || true
    if [[ -n "$LEGACY_PUBLIC_STREAM_TABLE" && "$LEGACY_PUBLIC_STREAM_TABLE" != "$TABLE_NAME" ]]; then
      nft delete table inet "$LEGACY_PUBLIC_STREAM_TABLE" >/dev/null 2>&1 || true
    fi
  fi
}

source_env_file "$HOST_ENV_FILE"
source_env_file "$MANAGER_ENV_FILE"

case "$ACTION" in
  --enable|enable)
    write_nft_rules
    if [[ "${BEAGLE_FIREWALL_NO_APPLY:-0}" != "1" ]]; then
      apply_rules
      ensure_libvirt_wireguard_forward_rules
    fi
    ;;
  --add-extra-rule|add-extra-rule)
    add_extra_rule "$ACTION_ARG"
    write_nft_rules
    if [[ "${BEAGLE_FIREWALL_NO_APPLY:-0}" != "1" ]]; then
      apply_rules
      ensure_libvirt_wireguard_forward_rules
    fi
    ;;
  --delete-extra-rule|delete-extra-rule)
    delete_extra_rule "$ACTION_ARG"
    write_nft_rules
    if [[ "${BEAGLE_FIREWALL_NO_APPLY:-0}" != "1" ]]; then
      apply_rules
      ensure_libvirt_wireguard_forward_rules
    fi
    ;;
  --write-only|write-only)
    write_nft_rules
    ;;
  --disable|disable)
    disable_rules
    ;;
  --status|status)
    if command -v nft >/dev/null 2>&1 && nft list table inet "$TABLE_NAME" >/dev/null 2>&1; then
      echo "active"
    else
      echo "inactive"
    fi
    ;;
  *)
    echo "Usage: $0 [--enable|--write-only|--disable|--status|--add-extra-rule RULE|--delete-extra-rule NUMBER]" >&2
    exit 2
    ;;
esac
