#!/bin/bash
# Configure thin-client stream endpoint with direct VM connection info
# Usage: configure-thinclient-stream-endpoint.sh <thinclient_ip> <vm_host> <vm_port> [ssh_key]
# Purpose: Ensures thin-client connects directly to VM stream server, avoiding broker fallback issues
# 
# Root Cause: Beagle Stream Client broker may fallback to incorrect host after handoff.
# This script explicitly sets direct connection parameters to bypass broker routing.

set -euo pipefail

THINCLIENT_IP="${1:-}"
VM_HOST="${2:-}"
VM_PORT="${3:-50000}"
SSH_KEY="${4:--}"

if [[ -z "$THINCLIENT_IP" || -z "$VM_HOST" ]]; then
    echo "Usage: $0 <thinclient_ip> <vm_host> <vm_port> [ssh_key]" >&2
    echo "  Example: $0 192.168.178.27 192.168.123.115 50000" >&2
    exit 1
fi

SSH_OPTS=(-o StrictHostKeyChecking=no -o ConnectTimeout=5)
if [[ "$SSH_KEY" != "-" ]]; then
    SSH_OPTS+=(-i "$SSH_KEY")
fi

echo "=== Configuring Thin-Client Stream Endpoint ==="
echo "Thin-Client IP: $THINCLIENT_IP"
echo "VM Host: $VM_HOST"
echo "VM Port: $VM_PORT"
echo ""

# Deploy the configuration file to thin-client
CONFIG_CONTENT="# Beagle Stream Client Direct Connection Override
# Force direct connection to VM stream server, bypassing broker fallback
# Set by: configure-thinclient-stream-endpoint.sh
PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST=$VM_HOST
PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PORT=$VM_PORT
PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BROKER_HOST=
PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOSTLESS=0
"

# Write config via SSH
if ssh "${SSH_OPTS[@]}" "root@$THINCLIENT_IP" bash -c "
    mkdir -p /etc/beagle
    cat > /etc/beagle/beagle-stream-client.env <<'EOFCONFIG'
$CONFIG_CONTENT
EOFCONFIG
    chmod 0644 /etc/beagle/beagle-stream-client.env
    echo '[✓] Configuration written to /etc/beagle/beagle-stream-client.env'
"; then
    echo "[✓] Thin-client stream endpoint configured successfully"
    echo ""
    echo "Next: Restart beagle-stream-client on thin-client:"
    echo "  ssh -o StrictHostKeyChecking=no root@$THINCLIENT_IP 'pkill -9 beagle-stream; sleep 2; ps aux | grep beagle-stream | grep -v grep'"
else
    echo "[✗] Failed to configure thin-client. Check SSH connectivity." >&2
    exit 1
fi
