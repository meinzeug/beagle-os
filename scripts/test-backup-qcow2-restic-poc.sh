#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="$(mktemp -d)"
SRC_IMG="$TMP_DIR/source.qcow2"
WORK_DIR="$TMP_DIR/work"
RESTIC_REPO="$TMP_DIR/restic-repo"
RESTIC_PASSWORD_VALUE="beagle-backup-poc"
FULL_EXPORT="$WORK_DIR/full-base.qcow2"
DELTA_OVERLAY="$WORK_DIR/inc-overlay.qcow2"
DELTA_EXPORT="$WORK_DIR/inc-export.qcow2"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

require_cmd() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "[FAIL] required command not found: $name" >&2
    exit 1
  fi
}

require_cmd qemu-img
require_cmd qemu-io
require_cmd restic
require_cmd python3

mkdir -p "$WORK_DIR"
qemu-img create -f qcow2 "$SRC_IMG" 2G >/dev/null

# Seed baseline content so dedupe behavior is measurable.
qemu-io -f qcow2 -c "write -P 0x11 0 64M" "$SRC_IMG" >/dev/null

qemu-img convert -O qcow2 "$SRC_IMG" "$FULL_EXPORT"

export RESTIC_REPOSITORY="$RESTIC_REPO"
export RESTIC_PASSWORD="$RESTIC_PASSWORD_VALUE"

restic init >/dev/null

capture_added_bytes() {
  local target_dir="$1"
  local json_file="$2"
  restic backup "$target_dir" --json >"$json_file"
  python3 - "$json_file" <<'PY'
import json
import sys

path = sys.argv[1]
added = -1
with open(path, "r", encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("message_type") == "summary":
            added = int(obj.get("data_added") or 0)
if added < 0:
    raise SystemExit(1)
print(added)
PY
}

FIRST_BYTES="$(capture_added_bytes "$WORK_DIR" "$TMP_DIR/backup-1.jsonl")"

# Build an incremental qcow2 overlay against the full export and write a small delta.
qemu-img create -f qcow2 -F qcow2 -b "$FULL_EXPORT" "$DELTA_OVERLAY" >/dev/null
qemu-io -f qcow2 -c "write -P 0x22 512M 8M" "$DELTA_OVERLAY" >/dev/null

# Export the incremental delta as qcow2 while preserving backing-chain semantics.
qemu-img convert -O qcow2 -o "backing_file=${FULL_EXPORT},backing_fmt=qcow2" "$DELTA_OVERLAY" "$DELTA_EXPORT"

SECOND_BYTES="$(capture_added_bytes "$WORK_DIR" "$TMP_DIR/backup-2.jsonl")"

python3 - "$FIRST_BYTES" "$SECOND_BYTES" <<'PY'
import sys

first = int(sys.argv[1])
second = int(sys.argv[2])
ratio = 0.0 if first <= 0 else (second / first)

if first <= 0:
    print("[FAIL] invalid first backup data_added")
    raise SystemExit(1)
if second >= first:
    print(f"[FAIL] dedupe not observed: first={first} second={second}")
    raise SystemExit(1)

print(f"[PASS] restic dedupe observed: first_added={first} second_added={second} ratio={ratio:.4f}")
print("BACKUP_QCOW2_RESTIC_POC=PASS")
PY