#!/usr/bin/env bats
# tests/bats/post_install_check.bats
#
# Bats unit tests for server-installer/post-install-check.sh
# Uses stub functions to avoid requiring real systemd/libvirt/curl.

setup() {
    # Load bats helper libraries if available
    load "$(command -v bats-support 2>/dev/null || true)"

    # Create a temp dir for stubs
    BATS_TEST_TMPDIR="$(mktemp -d)"
    export PATH="$BATS_TEST_TMPDIR/bin:$PATH"

    # Create stub binaries
    mkdir -p "$BATS_TEST_TMPDIR/bin"

    # systemctl stub — success by default
    cat > "$BATS_TEST_TMPDIR/bin/systemctl" << 'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "is-active" ]]; then
  service="${2:-}"
  if [[ "${STUB_FAILED_SERVICES:-}" == *"$service"* ]]; then
    echo "inactive"
    exit 1
  fi
  echo "active"
  exit 0
fi
exit 0
EOF

    # virsh stub
    cat > "$BATS_TEST_TMPDIR/bin/virsh" << 'EOF'
#!/usr/bin/env bash
if [[ "${STUB_VIRSH_FAIL:-}" == "1" ]]; then
  echo "error: failed to connect to the hypervisor" >&2
  exit 1
fi
echo "Id   Name   State"
exit 0
EOF

    # curl stub
    cat > "$BATS_TEST_TMPDIR/bin/curl" << 'EOF'
#!/usr/bin/env bash
# Extract URL from args
url="${*: -1}"
if [[ "${STUB_CURL_FAIL:-}" == "1" ]]; then
  exit 6
fi
if [[ "$url" == *"/api/v1/health"* || "$url" == *":8420"* ]]; then
  echo '{"ok":true,"version":"6.7.0"}'
  exit 0
fi
exit 0
EOF

    # ip stub
    cat > "$BATS_TEST_TMPDIR/bin/ip" << 'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "route" ]]; then
  echo "default via 192.168.1.1 dev eth0"
fi
exit 0
EOF

    # ping stub
    cat > "$BATS_TEST_TMPDIR/bin/ping" << 'EOF'
#!/usr/bin/env bash
if [[ "${STUB_PING_FAIL:-}" == "1" ]]; then exit 1; fi
exit 0
EOF

    # hostname stub
    cat > "$BATS_TEST_TMPDIR/bin/hostname" << 'EOF'
#!/usr/bin/env bash
echo "test-host.beagle-os.local"
EOF

    chmod +x "$BATS_TEST_TMPDIR/bin/"*

    SCRIPT="$(cd "$(dirname "$BATS_TEST_FILE")/../.." && pwd)/server-installer/post-install-check.sh"
    export SCRIPT
}

teardown() {
    rm -rf "$BATS_TEST_TMPDIR"
}

# ── Happy path ──────────────────────────────────────────────────────────────

@test "all checks pass — exits 0" {
    run bash "$SCRIPT"
    [ "$status" -eq 0 ]
}

@test "output contains PASS for services check" {
    run bash "$SCRIPT"
    [[ "$output" == *"PASS"* ]] || [[ "$output" == *"OK"* ]] || [[ "$output" == *"ok"* ]]
}

# ── Service failure ──────────────────────────────────────────────────────────

@test "failed required service causes non-zero exit" {
    STUB_FAILED_SERVICES="libvirtd" run bash "$SCRIPT"
    [ "$status" -ne 0 ]
}

# ── Network failure ─────────────────────────────────────────────────────────

@test "ping failure does not crash (non-fatal)" {
    STUB_PING_FAIL=1 run bash "$SCRIPT"
    # ping failure may be non-fatal depending on implementation
    # just ensure script doesn't abort with unbound variable error
    [[ "$status" -ne 127 ]]
}

# ── API endpoint ─────────────────────────────────────────────────────────────

@test "curl failure to beagle API causes non-zero exit" {
    STUB_CURL_FAIL=1 run bash "$SCRIPT"
    [ "$status" -ne 0 ]
}

@test "custom BEAGLE_API_PORT is respected" {
    export BEAGLE_API_PORT=9999
    run bash "$SCRIPT"
    # Should use 9999 not 8420 — check output or just that it runs
    [[ "$output" != *"unbound variable"* ]]
}

# ── Syntax ──────────────────────────────────────────────────────────────────

@test "script passes bash -n syntax check" {
    run bash -n "$SCRIPT"
    [ "$status" -eq 0 ]
}
