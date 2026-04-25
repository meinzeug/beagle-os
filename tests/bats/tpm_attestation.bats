#!/usr/bin/env bats
# tests/bats/tpm_attestation.bats
#
# Bats unit tests for thin-client-assistant/runtime/tpm_attestation.sh
# Uses stubs for tpm2_pcrread + curl + jq + python3 to avoid requiring real TPM
# hardware or network access.
#
# GoAdvanced Plan 09 Schritt 3.

setup() {
    BATS_TEST_TMPDIR="$(mktemp -d)"
    export BATS_TEST_TMPDIR

    # Prepend stub bin dir to PATH but keep system bin available for jq/python3
    # — we only override tpm2_pcrread and curl by default.
    mkdir -p "$BATS_TEST_TMPDIR/bin"
    export PATH="$BATS_TEST_TMPDIR/bin:$PATH"

    # tpm2_pcrread stub — emits sha256 PCR YAML matching real tool output
    cat > "$BATS_TEST_TMPDIR/bin/tpm2_pcrread" << 'EOF'
#!/usr/bin/env bash
if [[ "${STUB_TPM_FAIL:-}" == "1" ]]; then
  echo "tpm2_pcrread: communication failure" >&2
  exit 1
fi
if [[ "${STUB_TPM_EMPTY:-}" == "1" ]]; then
  echo "{}"
  exit 0
fi
cat <<'YAML'
sha256:
  0: 0x0000000000000000000000000000000000000000000000000000000000000000
  1: 0x1111111111111111111111111111111111111111111111111111111111111111
  2: 0x2222222222222222222222222222222222222222222222222222222222222222
  3: 0x3333333333333333333333333333333333333333333333333333333333333333
  4: 0x4444444444444444444444444444444444444444444444444444444444444444
  5: 0x5555555555555555555555555555555555555555555555555555555555555555
  6: 0x6666666666666666666666666666666666666666666666666666666666666666
  7: 0x7777777777777777777777777777777777777777777777777777777777777777
  14: 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
  15: 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
YAML
EOF

    # curl stub — produces controlled HTTP code and writes a response file.
    # Honors the --output and --write-out path conventions used by the script.
    cat > "$BATS_TEST_TMPDIR/bin/curl" << 'EOF'
#!/usr/bin/env bash
out_file=""
expect_url=""
http_code="${STUB_CURL_HTTP_CODE:-200}"
status_value="${STUB_CURL_STATUS:-accepted}"
prev=""
for arg in "$@"; do
  if [[ "$prev" == "--output" ]]; then
    out_file="$arg"
  fi
  prev="$arg"
done
if [[ -n "$out_file" ]]; then
  case "$status_value" in
    "")  printf '{}\n' > "$out_file" ;;
    *)   printf '{"status":"%s"}\n' "$status_value" > "$out_file" ;;
  esac
fi
printf '%s' "$http_code"
EOF

    # hostname stub for deterministic output
    cat > "$BATS_TEST_TMPDIR/bin/hostname" << 'EOF'
#!/usr/bin/env bash
echo "test-thin-client.beagle-os.local"
EOF

    chmod +x "$BATS_TEST_TMPDIR/bin/"*

    SCRIPT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/thin-client-assistant/runtime/tpm_attestation.sh"
    export SCRIPT

    # Required env vars
    export BEAGLE_CONTROL_PLANE="https://ctrl.test.beagle-os.local"
    export BEAGLE_DEVICE_ID="dev-bats-001"
    export BEAGLE_ATTEST_TOKEN="test-token-deadbeef"
}

teardown() {
    rm -rf "$BATS_TEST_TMPDIR"
}

# ── Required env vars ───────────────────────────────────────────────────────

@test "missing BEAGLE_CONTROL_PLANE => exit non-zero" {
    unset BEAGLE_CONTROL_PLANE
    run bash "$SCRIPT"
    [ "$status" -ne 0 ]
}

@test "missing BEAGLE_DEVICE_ID => exit non-zero" {
    unset BEAGLE_DEVICE_ID
    run bash "$SCRIPT"
    [ "$status" -ne 0 ]
}

@test "missing BEAGLE_ATTEST_TOKEN => exit non-zero" {
    unset BEAGLE_ATTEST_TOKEN
    run bash "$SCRIPT"
    [ "$status" -ne 0 ]
}

# ── Happy path ──────────────────────────────────────────────────────────────

@test "accepted attestation => exit 0" {
    if ! command -v jq >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
        skip "jq or python3 not available"
    fi
    if ! python3 -c 'import yaml' 2>/dev/null; then
        skip "python3 yaml module not available"
    fi
    run bash "$SCRIPT"
    [ "$status" -eq 0 ]
    [[ "$output" == *"accepted"* ]]
}

# ── Rejection / error paths ─────────────────────────────────────────────────

@test "control plane rejects => exit 1" {
    if ! command -v jq >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
        skip "jq or python3 not available"
    fi
    if ! python3 -c 'import yaml' 2>/dev/null; then
        skip "python3 yaml module not available"
    fi
    STUB_CURL_STATUS="rejected" run bash "$SCRIPT"
    [ "$status" -eq 1 ]
    [[ "$output" == *"REJECTED"* ]]
}

@test "HTTP 403 => exit 1 with token error" {
    if ! command -v jq >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
        skip "jq or python3 not available"
    fi
    if ! python3 -c 'import yaml' 2>/dev/null; then
        skip "python3 yaml module not available"
    fi
    STUB_CURL_HTTP_CODE="403" run bash "$SCRIPT"
    [ "$status" -eq 1 ]
    [[ "$output" == *"403"* ]]
}

@test "tpm2_pcrread fails => exit non-zero" {
    if ! command -v jq >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
        skip "jq or python3 not available"
    fi
    STUB_TPM_FAIL=1 run bash "$SCRIPT"
    [ "$status" -ne 0 ]
}

@test "tpm2_pcrread empty => exit non-zero" {
    if ! command -v jq >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
        skip "jq or python3 not available"
    fi
    if ! python3 -c 'import yaml' 2>/dev/null; then
        skip "python3 yaml module not available"
    fi
    STUB_TPM_EMPTY=1 run bash "$SCRIPT"
    [ "$status" -ne 0 ]
}

@test "missing tpm2_pcrread binary => exit non-zero" {
    rm -f "$BATS_TEST_TMPDIR/bin/tpm2_pcrread"
    # Also remove from any other PATH location by intercepting command -v
    PATH="$BATS_TEST_TMPDIR/bin:/usr/bin:/bin" run bash "$SCRIPT"
    [ "$status" -ne 0 ]
}
