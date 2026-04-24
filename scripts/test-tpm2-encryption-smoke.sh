#!/usr/bin/env bash
#
# Smoke test for TPM2-based LUKS2 disk encryption setup
#
# Tests:
#  1. Script syntax validation
#  2. Dry-run prerequisite checks
#  3. Logic validation for TPM2 detection
#

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
readonly SETUP_SCRIPT="$PROJECT_ROOT/thin-client-assistant/installer/setup-tpm2-encryption.sh"

declare -g TEST_RESULTS=0
declare -g TEST_TOTAL=0

info() {
  echo "[INFO] $*" >&2
}

pass() {
  echo "[PASS] $*" >&2
  ((TEST_RESULTS++))
  ((TEST_TOTAL++))
  return 0
}

fail() {
  echo "[FAIL] $*" >&2
  ((TEST_TOTAL++))
  return 1
}

test_syntax() {
  info "Test 1: Script syntax validation..."
  
  if bash -n "$SETUP_SCRIPT" 2>/dev/null; then
    pass "Script has valid bash syntax"
  else
    fail "Script has syntax errors"
    return 1
  fi
}

test_help() {
  info "Test 2: Help text..."
  
  if bash "$SETUP_SCRIPT" -h 2>&1 | grep -q "TPM2\|LUKS2\|Usage"; then
    pass "Help text is available"
  else
    fail "Help text missing or malformed"
    return 1
  fi
}

test_function_definitions() {
  info "Test 3: Function definitions..."
  
  local functions=(
    "require_root"
    "check_prereqs"
    "has_tpm2"
    "validate_device"
    "setup_luks2_tpm2"
    "setup_luks2_passphrase"
    "setup_dracut"
    "setup_crypttab"
  )
  
  for func in "${functions[@]}"; do
    if grep -q "^${func}()" "$SETUP_SCRIPT"; then
      info "  ✓ Function '$func' defined"
    else
      fail "Function '$func' not found"
      return 1
    fi
  done
  
  pass "All required functions are defined"
}

test_tpm2_detection_logic() {
  info "Test 4: TPM2 detection logic..."
  
  # Extract and test TPM2 detection conditions
  if grep -q "/dev/tpm0\|/dev/tpmrm0\|tpm2_getcap" "$SETUP_SCRIPT"; then
    pass "TPM2 detection checks are present"
  else
    fail "TPM2 detection logic incomplete"
    return 1
  fi
}

test_luks2_configuration() {
  info "Test 5: LUKS2 configuration..."
  
  # Verify LUKS2 settings
  local required_settings=(
    "aes-xts-plain64"    # cipher
    "sha256"              # hash
    "argon2i"             # pbkdf
    "512"                 # key-size
  )
  
  for setting in "${required_settings[@]}"; do
    if grep -q "$setting" "$SETUP_SCRIPT"; then
      info "  ✓ LUKS2 setting '$setting' found"
    else
      fail "LUKS2 setting '$setting' missing"
      return 1
    fi
  done
  
  pass "LUKS2 configuration is complete"
}

test_fallback_logic() {
  info "Test 6: Fallback mechanism..."
  
  # Check for auto-fallback logic
  if grep -q "ENCRYPTION_METHOD=\"auto\"\|ENCRYPTION_METHOD == \"auto\"" "$SETUP_SCRIPT"; then
    pass "Auto-fallback mode is implemented"
  else
    fail "Auto-fallback logic not found"
    return 1
  fi
}

test_device_validation() {
  info "Test 7: Device validation..."
  
  # Check device validation
  if grep -q "validate_device" "$SETUP_SCRIPT" && grep -q "\-b.*device" "$SETUP_SCRIPT"; then
    pass "Device validation is implemented"
  else
    fail "Device validation logic incomplete"
    return 1
  fi
}

test_cleanup_handler() {
  info "Test 8: Cleanup handler..."
  
  # Check for cleanup and trap
  if grep -q "trap cleanup EXIT\|cleanup()" "$SETUP_SCRIPT"; then
    pass "Cleanup handler is set up"
  else
    fail "Cleanup handler missing"
    return 1
  fi
}

test_crypttab_integration() {
  info "Test 9: Crypttab integration..."
  
  # Check crypttab setup
  if grep -q "setup_crypttab\|/etc/crypttab" "$SETUP_SCRIPT"; then
    pass "Crypttab integration is present"
  else
    fail "Crypttab integration missing"
    return 1
  fi
}

test_dracut_integration() {
  info "Test 10: Dracut integration..."
  
  # Check dracut configuration
  if grep -q "setup_dracut\|dracut\|crypt cryptsetup" "$SETUP_SCRIPT"; then
    pass "Dracut integration is present"
  else
    fail "Dracut integration missing"
    return 1
  fi
}

main() {
  info "Starting TPM2 Encryption Smoke Tests"
  info ""
  
  test_syntax || return 1
  test_help || true
  test_function_definitions || return 1
  test_tpm2_detection_logic || return 1
  test_luks2_configuration || return 1
  test_fallback_logic || return 1
  test_device_validation || return 1
  test_cleanup_handler || return 1
  test_crypttab_integration || return 1
  test_dracut_integration || return 1
  
  info ""
  info "========================================="
  info "Results: $TEST_RESULTS/$TEST_TOTAL tests passed"
  info "========================================="
  
  if [[ $TEST_RESULTS -eq $TEST_TOTAL ]]; then
    info "✓ All tests passed!"
    echo "TPM2_ENCRYPTION_SMOKE=PASS"
    return 0
  else
    info "✗ Some tests failed"
    echo "TPM2_ENCRYPTION_SMOKE=FAIL"
    return 1
  fi
}

main "$@"
