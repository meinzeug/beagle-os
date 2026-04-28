#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${PVE_DCV_CONFIG_DIR:-/etc/beagle}"
MANAGER_ENV_FILE="${BEAGLE_MANAGER_ENV_FILE:-$CONFIG_DIR/beagle-manager.env}"
HOST_ENV_FILE="${PVE_DCV_HOST_ENV_FILE:-$CONFIG_DIR/host.env}"
NFTABLES_CONF="${BEAGLE_NFTABLES_CONF:-/etc/nftables.conf}"
NFT_RULE_FILE="${BEAGLE_FIREWALL_RULE_FILE:-$CONFIG_DIR/beagle-firewall.nft}"
EXTRA_RULE_FILE="${BEAGLE_FIREWALL_EXTRA_RULE_FILE:-$CONFIG_DIR/beagle-firewall-extra.rules}"
TABLE_NAME="${BEAGLE_FIREWALL_TABLE:-beagle_guard}"
ACTION="${1:---enable}"

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

write_nft_rules() {
  local bridges=()
  local peers=()
  local ipv4_peers=()
  local ipv6_peers=()
  local bridge_set=""
  local ipv4_peer_set=""
  local ipv6_peer_set=""
  local peer

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

  install -d -m 0755 "$CONFIG_DIR"
  {
    cat <<EOF
table inet $TABLE_NAME {
  chain input {
    type filter hook input priority -20; policy drop;

    ct state invalid drop
    ct state { established, related } accept
    iifname "lo" accept

    ip protocol icmp accept
    ip6 nexthdr icmpv6 accept

    tcp dport 22 ct state new limit rate 30/minute burst 30 packets accept
    tcp dport { 80, 443 } ct state new limit rate 300/minute burst 300 packets accept

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

disable_rules() {
  if command -v nft >/dev/null 2>&1; then
    nft delete table inet "$TABLE_NAME" >/dev/null 2>&1 || true
  fi
}

source_env_file "$HOST_ENV_FILE"
source_env_file "$MANAGER_ENV_FILE"

case "$ACTION" in
  --enable|enable)
    write_nft_rules
    if [[ "${BEAGLE_FIREWALL_NO_APPLY:-0}" != "1" ]]; then
      apply_rules
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
    echo "Usage: $0 [--enable|--write-only|--disable|--status]" >&2
    exit 2
    ;;
esac
