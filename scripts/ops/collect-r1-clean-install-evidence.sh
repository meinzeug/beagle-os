#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${BEAGLE_R1_EVIDENCE_DIR:-$ROOT_DIR/docs/runbooks/evidence/r1-clean-install}"
HOST="${1:-}"
SSH_BIN="${BEAGLE_R1_EVIDENCE_SSH_BIN:-ssh}"
SSH_OPTS=(
  -o BatchMode=yes
  -o ConnectTimeout="${BEAGLE_R1_EVIDENCE_SSH_TIMEOUT:-10}"
)

if [[ -z "$HOST" ]]; then
  cat >&2 <<'EOF'
Usage: scripts/ops/collect-r1-clean-install-evidence.sh <host>

Collects R1 clean-install evidence from a target host:
  - UTC timestamp
  - host identity
  - /opt/beagle/VERSION
  - /opt/beagle/scripts/check-beagle-host.sh output

Writes artifacts to:
  docs/runbooks/evidence/r1-clean-install/<timestamp>_<host>.{log,json}
EOF
  exit 64
fi

mkdir -p "$OUT_DIR"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
safe_host="$(printf '%s' "$HOST" | tr -c '[:alnum:]._:-' '_')"
log_file="$OUT_DIR/${timestamp}_${safe_host}.log"
json_file="$OUT_DIR/${timestamp}_${safe_host}.json"

{
  echo "R1_CLEAN_INSTALL_EVIDENCE_BEGIN"
  echo "collector_timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "target_host=$HOST"
  echo "command=$SSH_BIN ${SSH_OPTS[*]} $HOST ..."
  set +e
  "$SSH_BIN" "${SSH_OPTS[@]}" "$HOST" '
set -euo pipefail
echo "remote_hostname=$(hostname -f 2>/dev/null || hostname)"
echo "remote_timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [[ -r /opt/beagle/VERSION ]]; then
  echo "remote_version=$(cat /opt/beagle/VERSION)"
else
  echo "remote_version=missing"
fi
if [[ ! -x /opt/beagle/scripts/check-beagle-host.sh ]]; then
  echo "check_beagle_host=missing"
  exit 3
fi
echo "check_beagle_host=begin"
/opt/beagle/scripts/check-beagle-host.sh
echo "check_beagle_host=end"
'
  ssh_rc=$?
  set -e
  echo "ssh_exit_code=$ssh_rc"
  echo "R1_CLEAN_INSTALL_EVIDENCE_END"
} >"$log_file" 2>&1

python3 - "$log_file" "$json_file" "$HOST" <<'PY'
import json
import re
import sys
from pathlib import Path

log_path = Path(sys.argv[1])
json_path = Path(sys.argv[2])
target_host = sys.argv[3]
raw = log_path.read_text(encoding="utf-8", errors="replace")

def find(name: str) -> str:
    m = re.search(rf"^{re.escape(name)}=(.*)$", raw, re.MULTILINE)
    return m.group(1).strip() if m else ""

ok = "FAIL" not in raw and "ERR " not in raw and "check_beagle_host=end" in raw
try:
    ssh_exit_code = int(find("ssh_exit_code") or "1")
except ValueError:
    ssh_exit_code = 1
payload = {
    "target_host": target_host,
    "collector_timestamp_utc": find("collector_timestamp_utc"),
    "remote_hostname": find("remote_hostname"),
    "remote_timestamp_utc": find("remote_timestamp_utc"),
    "remote_version": find("remote_version"),
    "ssh_exit_code": ssh_exit_code,
    "check_beagle_host_ok": ok,
    "log_file": str(log_path),
}
json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2))
PY

echo "[OK] Evidence written:"
echo "  - $log_file"
echo "  - $json_file"
if [[ "${ssh_rc:-1}" -ne 0 ]]; then
  echo "[ERR] SSH collection failed with exit code ${ssh_rc:-1}" >&2
  exit "${ssh_rc:-1}"
fi
