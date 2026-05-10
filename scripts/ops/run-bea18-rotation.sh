#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage:
  run-bea18-rotation.sh \
    --remote-user <user> \
    --auth-priv <current-admin.key> \
    --old-pub <compromised.pub> \
    --new-pub <new.pub> \
    --new-priv <new.key> \
    [--old-priv <compromised.key>] \
    [--known-hosts <known_hosts>] \
    [--out-dir <local-evidence-dir>]

Notes:
  - Runs BEA-18 key rotation on both srv1.beagle-os.com and srv2.beagle-os.com.
  - Writes per-host JSON evidence and one summary JSON.
USAGE
  exit 2
}

REMOTE_USER="root"
AUTH_PRIV=""
OLD_PUB=""
NEW_PUB=""
NEW_PRIV=""
OLD_PRIV=""
KNOWN_HOSTS_FILE="${HOME}/.ssh/known_hosts"
OUT_DIR="${PWD}/.tmp/bea18-rotation"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote-user)
      REMOTE_USER="${2:-}"
      shift 2
      ;;
    --auth-priv)
      AUTH_PRIV="${2:-}"
      shift 2
      ;;
    --old-pub)
      OLD_PUB="${2:-}"
      shift 2
      ;;
    --new-pub)
      NEW_PUB="${2:-}"
      shift 2
      ;;
    --new-priv)
      NEW_PRIV="${2:-}"
      shift 2
      ;;
    --old-priv)
      OLD_PRIV="${2:-}"
      shift 2
      ;;
    --known-hosts)
      KNOWN_HOSTS_FILE="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      ;;
  esac
done

[[ -n "$AUTH_PRIV" && -n "$OLD_PUB" && -n "$NEW_PUB" && -n "$NEW_PRIV" ]] || usage
[[ -r "$AUTH_PRIV" ]] || { echo "auth private key not readable: $AUTH_PRIV" >&2; exit 1; }
[[ -r "$OLD_PUB" ]] || { echo "old public key not readable: $OLD_PUB" >&2; exit 1; }
[[ -r "$NEW_PUB" ]] || { echo "new public key not readable: $NEW_PUB" >&2; exit 1; }
[[ -r "$NEW_PRIV" ]] || { echo "new private key not readable: $NEW_PRIV" >&2; exit 1; }
[[ -r "$KNOWN_HOSTS_FILE" ]] || { echo "known_hosts not readable: $KNOWN_HOSTS_FILE" >&2; exit 1; }
if [[ -n "$OLD_PRIV" && ! -r "$OLD_PRIV" ]]; then
  echo "old private key not readable: $OLD_PRIV" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROTATE_SCRIPT="${SCRIPT_DIR}/rotate-compromised-ssh-key.sh"
[[ -x "$ROTATE_SCRIPT" ]] || { echo "missing executable helper: $ROTATE_SCRIPT" >&2; exit 1; }

mkdir -p "$OUT_DIR"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
srv1_out="${OUT_DIR}/bea18-srv1-${ts}.json"
srv2_out="${OUT_DIR}/bea18-srv2-${ts}.json"
summary_out="${OUT_DIR}/bea18-summary-${ts}.json"

run_rotate() {
  local host="$1"
  local evidence="$2"
  local -a cmd=(
    "$ROTATE_SCRIPT"
    --host "$host"
    --remote-user "$REMOTE_USER"
    --auth-priv "$AUTH_PRIV"
    --old-pub "$OLD_PUB"
    --new-pub "$NEW_PUB"
    --new-priv "$NEW_PRIV"
    --known-hosts "$KNOWN_HOSTS_FILE"
    --evidence-out "$evidence"
  )
  if [[ -n "$OLD_PRIV" ]]; then
    cmd+=(--old-priv "$OLD_PRIV")
  fi
  "${cmd[@]}"
}

run_rotate "srv1.beagle-os.com" "$srv1_out"
run_rotate "srv2.beagle-os.com" "$srv2_out"

cat >"$summary_out" <<EOF
{
  "incident": "BEA-18",
  "timestamp_utc": "$(date -u +%FT%TZ)",
  "hosts": [
    "srv1.beagle-os.com",
    "srv2.beagle-os.com"
  ],
  "srv1_evidence": "$srv1_out",
  "srv2_evidence": "$srv2_out",
  "ci_secret_rotation_required": [
    "BEAGLE_PUBLIC_DEPLOY_SSH_KEY",
    "BEAGLE_PUBLIC_DEPLOY_KNOWN_HOSTS"
  ],
  "status": "PASS"
}
EOF
chmod 600 "$summary_out" || true

echo "BEA18_ROTATION_PASS"
echo "srv1_evidence=$srv1_out"
echo "srv2_evidence=$srv2_out"
echo "summary=$summary_out"
