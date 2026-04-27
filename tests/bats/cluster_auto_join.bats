#!/usr/bin/env bats

setup() {
    BATS_TEST_TMPDIR="$(mktemp -d)"
    export PATH="$BATS_TEST_TMPDIR/bin:$PATH"
    mkdir -p "$BATS_TEST_TMPDIR/bin" "$BATS_TEST_TMPDIR/etc/beagle" "$BATS_TEST_TMPDIR/var/lib/beagle/beagle-manager"

    cat > "$BATS_TEST_TMPDIR/bin/curl" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

    cat > "$BATS_TEST_TMPDIR/bin/python3" <<'EOF'
#!/usr/bin/env bash
/usr/bin/python3 "$@"
EOF

    cat > "$BATS_TEST_TMPDIR/bin/hostname" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "-f" ]]; then
  echo "srv2.beagle-os.com"
else
  echo "srv2"
fi
EOF

    cat > "$BATS_TEST_TMPDIR/bin/beaglectl.py" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" > "${STUB_BEAGLECTL_ARGS}"
exit "${STUB_BEAGLECTL_EXIT_CODE:-0}"
EOF

    chmod +x "$BATS_TEST_TMPDIR/bin/"*

    cat > "$BATS_TEST_TMPDIR/etc/beagle/beagle-manager.env" <<'EOF'
BEAGLE_MANAGER_API_TOKEN="local-token"
BEAGLE_CLUSTER_NODE_NAME="srv2"
EOF

    cat > "$BATS_TEST_TMPDIR/etc/beagle/cluster-join.env" <<'EOF'
BEAGLE_CLUSTER_JOIN_REQUESTED="yes"
BEAGLE_CLUSTER_JOIN_TARGET="join-token-value"
EOF

    SCRIPT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/scripts/beagle-cluster-auto-join.sh"
    export SCRIPT
    export STUB_BEAGLECTL_ARGS="$BATS_TEST_TMPDIR/beaglectl.args"
}

teardown() {
    rm -rf "$BATS_TEST_TMPDIR"
}

@test "auto join uses persisted join token and disables request on success" {
    run env \
      PVE_DCV_CONFIG_DIR="$BATS_TEST_TMPDIR/etc/beagle" \
      BEAGLE_CLUSTER_JOIN_STATUS_FILE="$BATS_TEST_TMPDIR/var/lib/beagle/beagle-manager/cluster-auto-join-status.json" \
      BEAGLECTL_BIN="$BATS_TEST_TMPDIR/bin/beaglectl.py" \
      bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q -- "--join-token join-token-value" "$STUB_BEAGLECTL_ARGS"
    grep -q 'BEAGLE_CLUSTER_JOIN_REQUESTED="no"' "$BATS_TEST_TMPDIR/etc/beagle/cluster-join.env"
}

@test "leader url without token fails hard" {
    cat > "$BATS_TEST_TMPDIR/etc/beagle/cluster-join.env" <<'EOF'
BEAGLE_CLUSTER_JOIN_REQUESTED="yes"
BEAGLE_CLUSTER_JOIN_TARGET="https://srv1.beagle-os.com/beagle-api/api/v1"
EOF
    run env \
      PVE_DCV_CONFIG_DIR="$BATS_TEST_TMPDIR/etc/beagle" \
      BEAGLE_CLUSTER_JOIN_STATUS_FILE="$BATS_TEST_TMPDIR/var/lib/beagle/beagle-manager/cluster-auto-join-status.json" \
      BEAGLECTL_BIN="$BATS_TEST_TMPDIR/bin/beaglectl.py" \
      bash "$SCRIPT"
    [ "$status" -ne 0 ]
}
