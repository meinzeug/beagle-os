# Beagle Stream Client Broker Fallback Fix

## Problem

**Symptom**: Beagle Stream Client on thin-client connects initially to VM100 via broker, but after broker handoff, connection drops and client gets wrong host from broker.

**Root Cause**: 
- Beagle Stream Server broker (`BEAGLE_STREAM_SERVER_API_URL`) provides session routing info
- After pairing, broker may return incorrect `connect_host` (e.g., public IP 46.4.96.80 instead of VPN IP 192.168.123.115)
- Thin-client tries to connect to public IP through VPN tunnel → connection fails
- Client falls into retry loop with wrong endpoint

**Evidence**:
```
phase=beagle-stream-client.session-broker host=46.4.96.80 connect_host=46.4.96.80
```
Shows broker returning public IP when VPN IP was expected.

## Solution

### 1. Config Loader Enhancement (Runtime)
File: `thin-client-assistant/runtime/config_loader.sh`
- Added load of `/etc/beagle/beagle-stream-client.env` as runtime override
- Allows deployment-time or manual configuration of direct stream endpoint

### 2. Thin-Client Stream Endpoint Configuration Script
File: `scripts/configure-thinclient-stream-endpoint.sh`
- Deploys direct stream server host/port configuration to thin-client
- Bypasses broker routing by explicitly setting:
  - `PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST=<vm_ip>`
  - `PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PORT=<vm_port>`
  - `PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BROKER_HOST=` (empty)

### 3. Deployment Procedure

#### Option A: Manual Configuration (Hot Fix)
```bash
ssh root@<thinclient_ip> bash -c '
  mkdir -p /etc/beagle
  cat > /etc/beagle/beagle-stream-client.env <<EOF
PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST=192.168.123.115
PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PORT=50000
PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BROKER_HOST=
PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOSTLESS=0
EOF
  pkill -9 beagle-stream
  sleep 2
'
```

#### Option B: Script-based Deployment (Reproducible)
```bash
./scripts/configure-thinclient-stream-endpoint.sh 192.168.178.27 192.168.123.115 50000
```

#### Option C: Integrated Provisioning (Ideal - Future)
When thin-client pairs with manager and target VM is determined:
1. Manager calls `configure-thinclient-stream-endpoint.sh` with VM details
2. Thin-client is automatically configured with direct endpoint
3. Client restarts and connects directly, avoiding broker fallback

### 4. Verification

After configuration:
```bash
ssh root@<thinclient_ip> bash -c '
  cat /etc/beagle/beagle-stream-client.env
  echo ""
  ps aux | grep beagle-stream | grep -v grep
  echo ""
  ss -tnp 2>&1 | grep 50000 | head -3
'
```

Expected: TCP ESTABLISHED connection visible on port 50000.

## Architecture Impact

- **Config Precedence**: Environment variables from `/etc/beagle/beagle-stream-client.env` override defaults from `thinclient.conf`
- **Runtime Flexibility**: Thin-client can be reconfigured without re-provisioning ISO
- **Broker Independence**: Direct connection mode bypasses broker routing entirely
- **Multi-VM Support**: Same thin-client can connect to different VMs by updating config

## Testing Checklist

- [ ] Thin-client has `/etc/beagle/beagle-stream-client.env` with correct VM host/port
- [ ] Config loader reads override file (check `PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST` value)
- [ ] TCP connection established on VM stream port (e.g., 50000)
- [ ] Desktop streaming visible on thin-client display
- [ ] No broker phase messages in logs showing wrong `connect_host`

## Files Changed

- `thin-client-assistant/runtime/config_loader.sh` - Load `/etc/beagle/beagle-stream-client.env` override
- `scripts/configure-thinclient-stream-endpoint.sh` - Provisioning helper script

## Future Work

1. **Manager Integration**: Call `configure-thinclient-stream-endpoint.sh` automatically when VM is assigned to thin-client
2. **Broker Fallback**: Implement broker endpoint validation to detect incorrect host before connection attempt
3. **Heartbeat Monitoring**: Add watchdog to detect and recover from broker fallback failures
4. **Multi-endpoint Testing**: Test with multiple thin-clients and VM endpoints
