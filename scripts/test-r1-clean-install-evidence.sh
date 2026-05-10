#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLLECTOR="${BEAGLE_R1_EVIDENCE_COLLECTOR:-$ROOT_DIR/scripts/ops/collect-r1-clean-install-evidence.sh}"
HOST="${1:-}"
EXPECTED_VERSION="${2:-${BEAGLE_R1_EXPECTED_VERSION:-}}"

usage() {
  cat >&2 <<'EOF'
Usage: scripts/test-r1-clean-install-evidence.sh <host> [expected_version]

Runs the R1 clean-install evidence collector and enforces acceptance conditions:
  - ssh_exit_code == 0
  - check_beagle_host_ok == true
  - remote_version present
  - if expected_version is provided: remote_version == expected_version
EOF
  exit 64
}

if [[ -z "$HOST" ]]; then
  usage
fi

if [[ ! -x "$COLLECTOR" ]]; then
  echo "[ERROR] Collector not executable: $COLLECTOR" >&2
  exit 66
fi

set +e
"$COLLECTOR" "$HOST"
collector_rc=$?
set -e

latest_json="$(
  ls -1t "$ROOT_DIR"/docs/runbooks/evidence/r1-clean-install/*_"$(printf '%s' "$HOST" | tr -c '[:alnum:]._:-' '_')".json 2>/dev/null \
    | head -n1
)"

if [[ -z "$latest_json" ]]; then
  echo "[ERROR] No evidence json found for host: $HOST" >&2
  exit 2
fi

summary="$(python3 - "$latest_json" "$EXPECTED_VERSION" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = (sys.argv[2] or "").strip()

errors: list[str] = []
ssh_exit = int(payload.get("ssh_exit_code", 1))
ok = bool(payload.get("check_beagle_host_ok"))
remote_version = str(payload.get("remote_version", "")).strip()

if ssh_exit != 0:
    errors.append(f"ssh_exit_code={ssh_exit}")
if not ok:
    errors.append("check_beagle_host_ok=false")
if not remote_version or remote_version == "missing":
    errors.append("remote_version missing")
if expected and remote_version != expected:
    errors.append(f"remote_version={remote_version} expected={expected}")

if errors:
    print("FAIL " + "; ".join(errors))
    raise SystemExit(1)

print(f"PASS host={payload.get('target_host')} remote_version={remote_version}")
PY
)"

echo "$summary"

if [[ "$collector_rc" -ne 0 ]]; then
  echo "[ERROR] Collector exited non-zero before acceptance checks passed (rc=$collector_rc)." >&2
  exit "$collector_rc"
fi

echo "[OK] R1 clean-install evidence acceptance passed: $latest_json"
