# XFCE noVNC Desktop Display Fix - Summary

**Date:** 2026-04-20  
**Status:** ✅ DEPLOYED TO PRODUCTION

## Problem Statement
XFCE desktop in VM100 was not visible via noVNC. Instead, the QEMU VGA VNC showed a TTY1 login prompt, even though XFCE was running on the VM.

**Root Cause:**  
XFCE runs via X11 on KMS/modesetting (Virtual-1 display connector), which uses a separate framebuffer from the legacy QEMU VGA text buffer that QEMU's built-in VNC captures.

## Solution Implemented

### 1. Firstboot Template Enhancement
**File:** `/opt/beagle/beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl`

Added:
- `x11vnc` package to guest OS installation
- `beagle-x11vnc.service` systemd service that:
  - Waits for X11 session to be ready (socket + Xauthority)
  - Starts x11vnc on port 5901 (captures X11 display :0 directly)
  - Runs as guest user (not root, avoiding permission issues)
  - Auto-restarts on failure
  - **Key fix:** Removed `-o /var/log/beagle-x11vnc.log` (permission denied error)

```bash
ExecStart=/usr/bin/x11vnc -display :0 -rfbport 5901 -forever -nopw \
  -auth /home/${GUEST_USER}/.Xauthority -shared -noxdamage -xkb
```

### 2. Console Access Service Enhancement
**File:** `/opt/beagle/beagle-host/services/vm_console_access.py`

Added:
- `_libvirt_guest_ip()` static method: detects guest IPv4 address from libvirt
  - Tries virsh domifaddr with --source agent
  - Falls back to --source lease
- `_tcp_port_open()` static method: tests TCP connectivity to remote port
  - Uses socket.create_connection with 2-second timeout
- Updated `_beagle_novnc_url()` logic:
  - **If** guest IP detected AND port 5901 reachable → use `{guest_ip}:5901`
  - **Else** fall back to localhost QEMU VNC (backward compatible)

## Deployments Completed

### To beagle Server (192.168.122.51)
✅ `beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl`  
✅ `beagle-host/services/vm_console_access.py`  
✅ `beagle-control-plane` service restarted (PID 30702, status: active)

**Authentication:** SSH user `beagle` with password `test1234`

## Expected Behavior - Going Forward

### For New VMs (e.g., VM102+)
1. VM provisioning starts → firstboot template applied
2. Guest OS boot completes
3. x11vnc service starts automatically after X11 ready
4. noVNC console URL points to guest IP:5901
5. User sees XFCE desktop (not TTY1) in noVNC viewer

### For VM100 (Existing)
Manual steps required to match new config (can be skipped - will work on next rebuild):

```bash
ssh dennis@192.168.122.100
# Inside VM100:
sudo sed -i 's|-o /var/log/beagle-x11vnc.log||' /etc/systemd/system/beagle-x11vnc.service
sudo systemctl daemon-reload
sudo systemctl restart beagle-x11vnc.service
ps aux | grep x11vnc | grep -v grep
```

## Architecture Notes

### Why x11vnc on port 5901 (not 5900)?
- Port 5900 may be used by QEMU's built-in VNC on the host
- Port 5901 is safe, non-conflicting, and easy to detect

### Why guest IP detection?
- Guest x11vnc is only reachable from parent hypervisor via guest bridge network
- noVNC websockify proxy on beagle-host can forward to guest:5901 directly
- This avoids nested VNC proxying and improves latency/compatibility

### Why fallback to QEMU VNC?
- If x11vnc not running or unreachable, system gracefully falls back
- Ensures noVNC always provides some display (even if incomplete)
- Backward compatible with VMs not running x11vnc

## Testing Checklist

- [ ] Provision new VM via Web UI with XFCE profile
- [ ] Wait for provisioning to complete
- [ ] Open VM console in Web UI → check noVNC URL targets guest IP:5901
- [ ] View XFCE desktop in noVNC (not TTY1 login)
- [ ] Test mouse/keyboard input through noVNC
- [ ] Verify x11vnc process running inside guest: `ps aux | grep x11vnc`

## Known Issues / Limitations

1. **VM100 Existing**: Requires manual repair (x11vnc service fix for log flag)
2. **Nested Hypervisor Auth**: beagleserver SSH requires password (sshpass approach)
3. **Guest Network Isolation**: x11vnc only reachable on guest bridge (192.168.122.0/24)

## Files Modified (Local)

Local repo changes pending commit:
- `beagle-host/templates/ubuntu-beagle/firstboot-provision.sh.tpl`
- `beagle-host/services/vm_console_access.py`
- `docs/refactor/05-progress.md`
- `docs/refactor/06-next-steps.md`
- `docs/refactor/08-todo-global.md`
- `docs/refactor/09-provider-abstraction.md`
- `scripts/install-beagle-host.sh`

## Credential Notes

**beagleserver SSH access:**
- Host: 192.168.122.51
- User: beagle
- Password: test1234
- sudo: yes (password required)

**VM100 user:**
- SSH: dennis@192.168.122.100
- Password varies (TestBeagle2026! or developer-set)

---

**Deployment Timestamp:** 2026-04-20 15:02:54 UTC  
**Control Plane Status:** ✅ Active PID 30702  
**Next VM Provisioning:** Will automatically use corrected x11vnc config
