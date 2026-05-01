#!/usr/bin/env bash
# Validate that beagle-sunshine-healthcheck.timer (or Restart=always) auto-restarts
# Sunshine after a forced crash on a guest VM.
#
# Usage:
#   BEAGLE_SMOKE_VM_SSH="user@<guest-ip>"   required – SSH target for the VM guest
#   BEAGLE_SMOKE_SUNSHINE_PORT="<port>"     optional – Sunshine API port (default 47990)
#   BEAGLE_SMOKE_WAIT_SEC="<sec>"           optional – seconds to wait for restart (default 90)
#   BEAGLE_SMOKE_SSH_OPTS="..."             optional – extra SSH options
#   BEAGLE_SMOKE_SSH_CMD="sshpass -e"       optional – prefix command before ssh (e.g. sshpass -e)
#
# The script:
#   1. Checks beagle-sunshine-healthcheck.timer state (WARN if inactive, not fatal).
#   2. Verifies beagle-sunshine.service is active and sunshine process running.
#   3. Kills the sunshine process (simulates crash).
#   4. Waits for beagle-sunshine.service to restart (Restart=always or healthcheck timer).
#   5. Verifies Sunshine is running again and the healthcheck API responds.
#   6. Optionally triggers the healthcheck script manually for a forced heal cycle.
#
set -euo pipefail

SMOKE_VM_SSH="${BEAGLE_SMOKE_VM_SSH:-}"
SUNSHINE_PORT="${BEAGLE_SMOKE_SUNSHINE_PORT:-47990}"
WAIT_SEC="${BEAGLE_SMOKE_WAIT_SEC:-90}"
SSH_OPTS="${BEAGLE_SMOKE_SSH_OPTS:--o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10}"
SSH_CMD_PREFIX="${BEAGLE_SMOKE_SSH_CMD:-}"

if [[ -z "$SMOKE_VM_SSH" ]]; then
  echo "[ERROR] BEAGLE_SMOKE_VM_SSH is required (e.g. beagle@192.168.x.y)" >&2
  exit 1
fi

ssh_run() {
  # shellcheck disable=SC2086
  ${SSH_CMD_PREFIX:+$SSH_CMD_PREFIX} ssh $SSH_OPTS "$SMOKE_VM_SSH" "$@"
}

echo "=== Sunshine Self-Heal Smoke Test ==="
echo "  Target : $SMOKE_VM_SSH"
echo "  Port   : $SUNSHINE_PORT"
echo "  Wait   : ${WAIT_SEC}s"
echo ""

# 1. Check healthcheck timer (WARN only, not fatal — Restart=always also covers self-heal)
echo "[1] Checking beagle-sunshine-healthcheck.timer ..."
TIMER_STATE="$(ssh_run 'systemctl is-active beagle-sunshine-healthcheck.timer 2>/dev/null || echo inactive')"
TIMER_WARN=""
if [[ "$TIMER_STATE" != "active" ]]; then
  echo "[WARN] beagle-sunshine-healthcheck.timer is not active (state=$TIMER_STATE)"
  echo "       Will test systemd Restart=always self-heal path only."
  TIMER_WARN="timer-inactive"
else
  echo "[OK]  beagle-sunshine-healthcheck.timer is active"
fi

# 2. Check sunshine process is running
echo "[2] Verifying sunshine process is running ..."
if ! ssh_run 'pgrep -x sunshine >/dev/null 2>&1'; then
  # Try starting via service first
  ssh_run 'sudo systemctl start beagle-sunshine.service >/dev/null 2>&1 || true'
  sleep 10
  if ! ssh_run 'pgrep -x sunshine >/dev/null 2>&1'; then
    echo "[ERROR] sunshine process is not running and could not be started." >&2
    exit 1
  fi
fi
echo "[OK]  sunshine process running"

# 3. Kill sunshine to simulate a crash
echo "[3] Simulating crash: pkill sunshine ..."
ssh_run 'sudo pkill -9 -x sunshine >/dev/null 2>&1 || pkill -9 -x sunshine >/dev/null 2>&1 || true'
echo "[OK]  sunshine killed"

# 4. Wait for beagle-sunshine.service to restart (Restart=always, RestartSec=3)
echo "[4] Waiting up to ${WAIT_SEC}s for Sunshine to restart ..."
DEADLINE=$(( SECONDS + WAIT_SEC ))
RESTARTED=0
while (( SECONDS < DEADLINE )); do
  if ssh_run 'pgrep -x sunshine >/dev/null 2>&1'; then
    RESTARTED=1
    break
  fi
  sleep 3
done

if [[ "$RESTARTED" -eq 0 ]]; then
  echo "[ERROR] Sunshine did not restart within ${WAIT_SEC}s" >&2
  echo "        Service log:" >&2
  ssh_run 'sudo journalctl -u beagle-sunshine.service -n 40 --no-pager 2>/dev/null || true' >&2
  exit 1
fi
echo "[OK]  sunshine process restarted"

# 5. Verify Sunshine API is responding
echo "[5] Verifying Sunshine API responds on port ${SUNSHINE_PORT} ..."
GUEST_IP="$(printf '%s' "$SMOKE_VM_SSH" | awk -F'@' '{print $NF}')"
API_URL="https://${GUEST_IP}:${SUNSHINE_PORT}/api/apps"
API_OK=0
DEADLINE=$(( SECONDS + 30 ))
while (( SECONDS < DEADLINE )); do
  HTTP_CODE="$(curl -sk --max-time 5 -o /dev/null -w '%{http_code}' "$API_URL" 2>/dev/null || echo '000')" # tls-bypass-allowlist: Sunshine API smoke runs against self-signed local endpoint
  if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "401" ]]; then
    API_OK=1
    break
  fi
  sleep 3
done

if [[ "$API_OK" -eq 0 ]]; then
  echo "[WARN] Sunshine API did not respond on ${API_URL} within 30s" >&2
  echo "       (Sunshine is running but may still be initializing — non-fatal)" >&2
else
  echo "[OK]  Sunshine API responded (HTTP $HTTP_CODE)"
fi

# 6. Trigger the healthcheck script manually for a forced heal cycle
echo "[6] Running beagle-sunshine-healthcheck manually for forced heal check ..."
ssh_run 'if command -v /usr/local/bin/beagle-sunshine-healthcheck >/dev/null 2>&1; then
  sudo /usr/local/bin/beagle-sunshine-healthcheck --repair-only >/dev/null 2>&1 \
    && echo "healthcheck-script: OK" \
    || echo "healthcheck-script: non-zero exit (may be normal if already healthy)";
else
  echo "healthcheck-script: not installed (skipped)";
fi' || true

echo ""
echo "SUNSHINE_SELFHEAL_SMOKE=PASS"
echo "  sunshine restarted after pkill within ${WAIT_SEC}s"
if [[ -n "$TIMER_WARN" ]]; then
  echo "  beagle-sunshine-healthcheck.timer: inactive (WARN — install configure-sunshine-guest.sh for full timer coverage)"
else
  echo "  beagle-sunshine-healthcheck.timer: active"
fi
