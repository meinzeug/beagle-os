#!/usr/bin/env bash
set -euo pipefail

PORT="${BEAGLE_CLUSTER_API_PORT:-9088}"
CHAIN="${BEAGLE_CLUSTER_API_CHAIN:-BEAGLE_CLUSTER_API_9088}"
PERSIST="${BEAGLE_CLUSTER_API_PERSIST:-auto}"
ALLOW_LOCALHOST=1
DRY_RUN=0

PEERS=()

usage() {
  cat <<'EOF'
Usage:
  harden-cluster-api-iptables.sh --peer <ip-or-cidr> [--peer <ip-or-cidr> ...] [options]

Options:
  --peer <ip-or-cidr>   Allowed source for cluster API port (repeatable).
  --port <port>         Target API port (default: 9088).
  --chain <name>        iptables chain name (default: BEAGLE_CLUSTER_API_9088).
  --persist <mode>      Persistence mode: auto|always|never (default: auto).
  --no-localhost        Do not allow localhost access.
  --dry-run             Print actions without applying rules.
  -h, --help            Show this help.

Examples:
  sudo ./scripts/harden-cluster-api-iptables.sh --peer 176.9.127.50
  sudo ./scripts/harden-cluster-api-iptables.sh --peer 46.4.96.80 --peer 176.9.127.50 --persist always
EOF
}

log() {
  printf '[cluster-api-hardening] %s\n' "$*"
}

run_cmd() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] '
    printf '%q ' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

require_root() {
  if [[ "$DRY_RUN" == "1" ]]; then
    return 0
  fi
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi
  log "run as root (or via sudo)"
  exit 1
}

require_iptables() {
  if command -v iptables >/dev/null 2>&1; then
    return 0
  fi
  log "iptables command not found"
  exit 1
}

parse_args() {
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --peer)
        shift
        [[ "$#" -gt 0 ]] || { log "missing value for --peer"; exit 1; }
        PEERS+=("$1")
        ;;
      --port)
        shift
        [[ "$#" -gt 0 ]] || { log "missing value for --port"; exit 1; }
        PORT="$1"
        ;;
      --chain)
        shift
        [[ "$#" -gt 0 ]] || { log "missing value for --chain"; exit 1; }
        CHAIN="$1"
        ;;
      --persist)
        shift
        [[ "$#" -gt 0 ]] || { log "missing value for --persist"; exit 1; }
        PERSIST="$1"
        ;;
      --no-localhost)
        ALLOW_LOCALHOST=0
        ;;
      --dry-run)
        DRY_RUN=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        log "unknown argument: $1"
        usage
        exit 1
        ;;
    esac
    shift
  done
}

validate_inputs() {
  [[ "$PORT" =~ ^[0-9]+$ ]] || { log "invalid port: $PORT"; exit 1; }
  if (( PORT < 1 || PORT > 65535 )); then
    log "port out of range: $PORT"
    exit 1
  fi

  case "$PERSIST" in
    auto|always|never) ;;
    *)
      log "invalid --persist mode: $PERSIST (expected auto|always|never)"
      exit 1
      ;;
  esac

  if (( ${#PEERS[@]} == 0 && ALLOW_LOCALHOST == 0 )); then
    log "refusing to apply deny-all on port $PORT without any allowed source"
    exit 1
  fi
}

ensure_chain_exists() {
  if iptables -nL "$CHAIN" >/dev/null 2>&1; then
    return 0
  fi
  run_cmd iptables -N "$CHAIN"
}

ensure_input_jump() {
  if iptables -C INPUT -p tcp --dport "$PORT" -j "$CHAIN" >/dev/null 2>&1; then
    return 0
  fi
  run_cmd iptables -I INPUT 1 -p tcp --dport "$PORT" -j "$CHAIN"
}

rebuild_chain_rules() {
  run_cmd iptables -F "$CHAIN"

  if (( ALLOW_LOCALHOST == 1 )); then
    run_cmd iptables -A "$CHAIN" -s 127.0.0.1/32 -j ACCEPT
  fi

  local peer
  for peer in "${PEERS[@]}"; do
    run_cmd iptables -A "$CHAIN" -s "$peer" -j ACCEPT
  done

  run_cmd iptables -A "$CHAIN" -j DROP
}

persist_rules() {
  if [[ "$DRY_RUN" == "1" ]]; then
    log "dry-run: skipping persistence step"
    return 0
  fi
  case "$PERSIST" in
    never)
      log "persistence disabled (--persist never)"
      return 0
      ;;
    auto|always)
      if command -v netfilter-persistent >/dev/null 2>&1; then
        run_cmd netfilter-persistent save
        log "rules persisted via netfilter-persistent"
        return 0
      fi
      if [[ "$PERSIST" == "always" ]]; then
        log "requested --persist always but netfilter-persistent is unavailable"
        exit 1
      fi
      log "netfilter-persistent not found; rules are active but not persisted"
      return 0
      ;;
  esac
}

print_summary() {
  if [[ "$DRY_RUN" == "1" ]]; then
    log "dry-run complete for tcp/$PORT"
    return 0
  fi
  log "hardening active for tcp/$PORT"
  iptables -S INPUT | grep -- "-p tcp -m tcp --dport $PORT -j $CHAIN" || true
  iptables -S "$CHAIN" || true
}

main() {
  parse_args "$@"
  validate_inputs
  require_root
  require_iptables

  ensure_chain_exists
  ensure_input_jump
  rebuild_chain_rules
  persist_rules
  print_summary
}

main "$@"
