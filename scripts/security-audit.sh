#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${BEAGLE_SECURITY_AUDIT_REPORT_DIR:-$ROOT_DIR/dist/security-audit}"
STRICT_MODE="${BEAGLE_SECURITY_AUDIT_STRICT:-0}"
PYTHON_BIN="${BEAGLE_SECURITY_AUDIT_PYTHON:-$ROOT_DIR/.venv/bin/python}"

mkdir -p "$REPORT_DIR"

status=0

run_pip_audit() {
  local report_file="$REPORT_DIR/pip-audit.txt"
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "[WARN] Python runtime not found for pip-audit: $PYTHON_BIN" | tee "$report_file"
    return 0
  fi
  if ! "$PYTHON_BIN" -m pip_audit --version >/dev/null 2>&1; then
    echo "[WARN] pip-audit is not installed in $PYTHON_BIN environment" | tee "$report_file"
    return 0
  fi

  echo "[INFO] Running pip-audit..." | tee "$report_file"
  if "$PYTHON_BIN" -m pip_audit | tee -a "$report_file"; then
    echo "[PASS] pip-audit found no known vulnerabilities." | tee -a "$report_file"
    return 0
  fi

  echo "[WARN] pip-audit reported vulnerabilities." | tee -a "$report_file"
  return 1
}

run_npm_audit() {
  local report_file="$REPORT_DIR/npm-audit.json"
  if [[ ! -f "$ROOT_DIR/beagle-kiosk/package.json" ]]; then
    echo "[WARN] beagle-kiosk/package.json not found" | tee "$REPORT_DIR/npm-audit.txt"
    return 0
  fi

  if ! command -v npm >/dev/null 2>&1; then
    echo "[WARN] npm not available, skipping npm audit" | tee "$REPORT_DIR/npm-audit.txt"
    return 0
  fi

  echo "[INFO] Running npm audit in beagle-kiosk..."
  pushd "$ROOT_DIR/beagle-kiosk" >/dev/null
  if npm audit --json > "$report_file" 2>/dev/null; then
    echo "[PASS] npm audit found no known vulnerabilities." | tee "$REPORT_DIR/npm-audit.txt"
    popd >/dev/null
    return 0
  fi
  popd >/dev/null

  echo "[WARN] npm audit reported vulnerabilities (see $report_file)." | tee "$REPORT_DIR/npm-audit.txt"
  return 1
}

if ! run_pip_audit; then
  status=1
fi

if ! run_npm_audit; then
  status=1
fi

if [[ "$status" -ne 0 && "$STRICT_MODE" == "1" ]]; then
  echo "[FAIL] Security audit found vulnerabilities and strict mode is enabled." >&2
  exit 1
fi

if [[ "$status" -ne 0 ]]; then
  echo "[WARN] Security audit completed with findings (strict mode disabled)." >&2
else
  echo "[PASS] Security audit completed with no findings."
fi
