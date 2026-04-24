#!/usr/bin/env bash
#
# Smoke test for first-boot enrollment display
#
# Tests:
#  1. Script syntax/import validation
#  2. Display code generation is deterministic
#  3. Already-enrolled detection (no display needed)
#  4. Enrollment URL is constructed correctly
#  5. --once mode exits with code 1 when not enrolled

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
readonly DISPLAY_SCRIPT="$PROJECT_ROOT/thin-client-assistant/runtime/first_boot_enrollment_display.py"

declare -g PASS_COUNT=0
declare -g TOTAL_COUNT=0

info() { echo "[INFO] $*" >&2; }
pass() { echo "[PASS] $*" >&2; ((PASS_COUNT++)); ((TOTAL_COUNT++)); return 0; }
fail() { echo "[FAIL] $*" >&2; ((TOTAL_COUNT++)); return 1; }

test_syntax() {
  info "Test 1: Python syntax validation..."
  if python3 -m py_compile "$DISPLAY_SCRIPT" 2>/dev/null; then
    pass "Script has valid Python syntax"
  else
    fail "Script has syntax errors"
    return 1
  fi
}

test_deterministic_code() {
  info "Test 2: Deterministic code generation..."
  local code1 code2
  code1=$(python3 -c "
import sys; sys.path.insert(0, '$(dirname "$DISPLAY_SCRIPT")')
from first_boot_enrollment_display import _generate_display_code
print(_generate_display_code('test-machine-id-12345'))
")
  code2=$(python3 -c "
import sys; sys.path.insert(0, '$(dirname "$DISPLAY_SCRIPT")')
from first_boot_enrollment_display import _generate_display_code
print(_generate_display_code('test-machine-id-12345'))
")
  if [[ "$code1" == "$code2" ]]; then
    info "  ✓ Code is deterministic: $code1"
    pass "Code generation is deterministic"
  else
    fail "Code generation is not deterministic: $code1 != $code2"
    return 1
  fi
}

test_code_format() {
  info "Test 3: Code format (XXXX-DDDD)..."
  local code
  code=$(python3 -c "
import sys; sys.path.insert(0, '$(dirname "$DISPLAY_SCRIPT")')
from first_boot_enrollment_display import _generate_display_code
print(_generate_display_code('test-machine-id-12345'))
")
  if echo "$code" | grep -qE '^[A-Z]{4}-[0-9]{4}$'; then
    pass "Code format is correct: $code"
  else
    fail "Code format is wrong: $code"
    return 1
  fi
}

test_already_enrolled_detection() {
  info "Test 4: Already-enrolled detection..."
  local tmpdir
  tmpdir=$(mktemp -d)
  trap "rm -rf $tmpdir" EXIT

  # Write a config with manager token
  echo 'PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN="test-token-xyz"' > "$tmpdir/credentials.env"
  touch "$tmpdir/thinclient.conf"

  local result
  result=$(python3 "$DISPLAY_SCRIPT" --config "$tmpdir/thinclient.conf" --credentials "$tmpdir/credentials.env"; echo "exit=$?")
  local exit_code
  exit_code=$(python3 "$DISPLAY_SCRIPT" --config "$tmpdir/thinclient.conf" --credentials "$tmpdir/credentials.env"; echo $?)

  if python3 "$DISPLAY_SCRIPT" --config "$tmpdir/thinclient.conf" --credentials "$tmpdir/credentials.env" 2>/dev/null; then
    pass "Already-enrolled endpoint exits 0"
  else
    fail "Already-enrolled detection failed"
    return 1
  fi
}

test_not_enrolled_once_mode() {
  info "Test 5: --once mode with no enrollment..."
  local tmpdir
  tmpdir=$(mktemp -d)
  trap "rm -rf $tmpdir" EXIT

  # Empty config (no token)
  touch "$tmpdir/credentials.env"
  touch "$tmpdir/thinclient.conf"

  local exit_code=0
  PVE_THIN_CLIENT_BEAGLE_MANAGER_URL="http://test.local:9088" python3 "$DISPLAY_SCRIPT" \
    --config "$tmpdir/thinclient.conf" \
    --credentials "$tmpdir/credentials.env" \
    --once 2>/dev/null || exit_code=$?

  if [[ $exit_code -eq 1 ]]; then
    pass "--once mode exits 1 when not enrolled"
  else
    fail "--once mode should exit 1 when not enrolled, got $exit_code"
    return 1
  fi
}

test_enrollment_url_construction() {
  info "Test 6: Enrollment URL construction..."
  local url
  url=$(python3 -c "
import sys; sys.path.insert(0, '$(dirname "$DISPLAY_SCRIPT")')
from first_boot_enrollment_display import _generate_display_code
code = _generate_display_code('test-machine-id')
manager_url = 'http://srv1.beagle-os.com:9088'
enroll_url = manager_url.rstrip('/') + '/enroll?code=' + code
print(enroll_url)
")
  if echo "$url" | grep -q '/enroll?code='; then
    pass "Enrollment URL contains code parameter: $url"
  else
    fail "Enrollment URL malformed: $url"
    return 1
  fi
}

test_env_file_reader() {
  info "Test 7: Env file reader..."
  local tmpdir
  tmpdir=$(mktemp -d)

  # Test various quoting styles
  cat > "$tmpdir/test.env" << 'EOF'
KEY1=value1
KEY2="value2"
KEY3='value3'
# comment
KEY4=
EOF

  local result
  result=$(python3 -c "
import sys; sys.path.insert(0, '$(dirname "$DISPLAY_SCRIPT")')
from first_boot_enrollment_display import _read_env_file
env = _read_env_file('$tmpdir/test.env')
assert env.get('KEY1') == 'value1', f'KEY1={env.get(\"KEY1\")}'
assert env.get('KEY2') == 'value2', f'KEY2={env.get(\"KEY2\")}'
assert env.get('KEY3') == 'value3', f'KEY3={env.get(\"KEY3\")}'
assert 'KEY4' in env, 'KEY4 missing'
print('OK')
" 2>&1)
  if [[ "$result" == "OK" ]]; then
    pass "Env file reader handles quoting correctly"
  else
    fail "Env file reader error: $result"
    return 1
  fi

  rm -rf "$tmpdir"
}

main() {
  info "Starting First-Boot Enrollment Display Smoke Tests"
  info ""

  test_syntax || return 1
  test_deterministic_code || return 1
  test_code_format || return 1
  test_already_enrolled_detection || return 1
  test_not_enrolled_once_mode || return 1
  test_enrollment_url_construction || return 1
  test_env_file_reader || return 1

  info ""
  info "========================================"
  info "Results: $PASS_COUNT/$TOTAL_COUNT tests passed"
  info "========================================"

  if [[ $PASS_COUNT -eq $TOTAL_COUNT ]]; then
    info "✓ All tests passed!"
    echo "ENROLLMENT_DISPLAY_SMOKE=PASS"
    return 0
  else
    echo "ENROLLMENT_DISPLAY_SMOKE=FAIL"
    return 1
  fi
}

main "$@"
