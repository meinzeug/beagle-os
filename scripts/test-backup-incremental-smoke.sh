#!/usr/bin/env bash
# test-backup-incremental-smoke.sh
# Plan 16 — Testpflicht: Inkrementelles Backup dauert weniger als 10% des ersten Backups.
#
# Verfahren:
#   1. Legt /etc/beagle/backup-smoke-test/ mit 50 KB Testdaten an.
#   2. Läuft erstes Backup (full) mit --listed-incremental.
#   3. Ändert genau eine Datei (< 1 KB).
#   4. Läuft zweites Backup (incremental) mit demselben .snar.
#   5. Prüft: Größe Backup-2 < 10 % Größe Backup-1.
#   6. Räumt auf.
#
# Exit 0 = PASS, Exit 1 = FAIL
set -euo pipefail

TARGET_DIR=$(mktemp -d /tmp/beagle-backup-smoke-XXXXXX)
SNAR="${TARGET_DIR}/smoke-test-vm-9999.snar"
DATA_DIR="/etc/beagle/backup-smoke-test"
CREATED_DATA=0
RESULT="FAIL"

cleanup() {
    rm -rf "${TARGET_DIR}"
    if [[ "${CREATED_DATA}" -eq 1 ]]; then
        rm -rf "${DATA_DIR}"
    fi
    echo "BACKUP_INCREMENTAL_RESULT=${RESULT}"
    [[ "${RESULT}" == "PASS" ]] && exit 0 || exit 1
}
trap cleanup EXIT

# --- Setup: create ~50 KB test data under /etc/beagle ---
if [[ ! -d /etc/beagle ]]; then
    echo "ERROR: /etc/beagle does not exist — run on a beagle host or create it first" >&2
    exit 1
fi

mkdir -p "${DATA_DIR}"
CREATED_DATA=1

# Write 50 KB across 5 files (10 KB each)
for i in $(seq 1 5); do
    dd if=/dev/urandom bs=1K count=10 2>/dev/null | base64 > "${DATA_DIR}/data-${i}.txt"
done

# --- Backup 1: full (no .snar yet) ---
ARCHIVE1="${TARGET_DIR}/smoke-backup-vm-9999-$(date -u +%Y%m%dT%H%M%S)-full.tar.gz"
tar --ignore-failed-read \
    --listed-incremental="${SNAR}" \
    -czf "${ARCHIVE1}" \
    "${DATA_DIR}" 2>/dev/null || true

SIZE1=$(stat -c%s "${ARCHIVE1}" 2>/dev/null || echo 0)
if [[ "${SIZE1}" -eq 0 ]]; then
    echo "ERROR: first backup archive is empty or missing" >&2
    exit 1
fi
echo "Backup 1 (full): ${ARCHIVE1} — ${SIZE1} bytes"

# --- Modify exactly one small file (simulate a tiny change) ---
echo "incremental-test-change-$(date -u +%s)" > "${DATA_DIR}/data-1.txt"

# --- Backup 2: incremental (re-uses existing .snar) ---
ARCHIVE2="${TARGET_DIR}/smoke-backup-vm-9999-$(date -u +%Y%m%dT%H%M%S)-incr.tar.gz"
tar --ignore-failed-read \
    --listed-incremental="${SNAR}" \
    -czf "${ARCHIVE2}" \
    "${DATA_DIR}" 2>/dev/null || true

SIZE2=$(stat -c%s "${ARCHIVE2}" 2>/dev/null || echo 0)
if [[ "${SIZE2}" -eq 0 ]]; then
    echo "ERROR: second backup archive is empty or missing" >&2
    exit 1
fi
echo "Backup 2 (incremental): ${ARCHIVE2} — ${SIZE2} bytes"

# --- Check: SIZE2 < 10% of SIZE1 ---
# Use integer arithmetic: SIZE2 * 100 < SIZE1 * 10 ↔ SIZE2 * 10 < SIZE1
THRESHOLD=$(( SIZE1 / 10 ))
echo "Threshold (10% of full): ${THRESHOLD} bytes"
if [[ "${SIZE2}" -lt "${THRESHOLD}" ]]; then
    RESULT="PASS"
    echo "PASS: incremental backup (${SIZE2} B) < 10% of full backup (${SIZE1} B)"
else
    RESULT="FAIL"
    echo "FAIL: incremental backup (${SIZE2} B) >= 10% of full backup (${SIZE1} B)"
fi
