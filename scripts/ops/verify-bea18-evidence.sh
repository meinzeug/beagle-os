#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage:
  verify-bea18-evidence.sh \
    --srv1 <path-to-srv1-evidence.json> \
    --srv2 <path-to-srv2-evidence.json> \
    --summary <path-to-summary-evidence.json>

Checks:
  - incident == BEA-18
  - per-host rotation_status == PASS
  - per-host new_key_login == ok
  - summary status == PASS
  - summary references both evidence files
USAGE
  exit 2
}

SRV1=""
SRV2=""
SUMMARY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --srv1)
      SRV1="${2:-}"
      shift 2
      ;;
    --srv2)
      SRV2="${2:-}"
      shift 2
      ;;
    --summary)
      SUMMARY="${2:-}"
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

[[ -n "$SRV1" && -n "$SRV2" && -n "$SUMMARY" ]] || usage
[[ -r "$SRV1" ]] || { echo "missing srv1 evidence: $SRV1" >&2; exit 1; }
[[ -r "$SRV2" ]] || { echo "missing srv2 evidence: $SRV2" >&2; exit 1; }
[[ -r "$SUMMARY" ]] || { echo "missing summary evidence: $SUMMARY" >&2; exit 1; }

python3 - "$SRV1" "$SRV2" "$SUMMARY" <<'PY'
import json
import sys
from pathlib import Path

srv1_path = Path(sys.argv[1]).resolve()
srv2_path = Path(sys.argv[2]).resolve()
summary_path = Path(sys.argv[3]).resolve()

srv1 = json.loads(srv1_path.read_text(encoding="utf-8"))
srv2 = json.loads(srv2_path.read_text(encoding="utf-8"))
summary = json.loads(summary_path.read_text(encoding="utf-8"))

def require(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(msg)

for name, data, expected_host in (
    ("srv1", srv1, "srv1.beagle-os.com"),
    ("srv2", srv2, "srv2.beagle-os.com"),
):
    require(data.get("incident") == "BEA-18", f"{name}: incident != BEA-18")
    require(data.get("host") == expected_host, f"{name}: host mismatch")
    require(data.get("rotation_status") == "PASS", f"{name}: rotation_status != PASS")
    require(data.get("new_key_login") == "ok", f"{name}: new_key_login != ok")
    require(str(data.get("old_fingerprint") or "").strip(), f"{name}: old_fingerprint missing")
    require(str(data.get("new_fingerprint") or "").strip(), f"{name}: new_fingerprint missing")

require(summary.get("incident") == "BEA-18", "summary: incident != BEA-18")
require(summary.get("status") == "PASS", "summary: status != PASS")

summary_srv1 = Path(str(summary.get("srv1_evidence") or "")).resolve()
summary_srv2 = Path(str(summary.get("srv2_evidence") or "")).resolve()
require(summary_srv1 == srv1_path, "summary: srv1_evidence path mismatch")
require(summary_srv2 == srv2_path, "summary: srv2_evidence path mismatch")

print("BEA18_EVIDENCE_VERIFY=PASS")
PY
