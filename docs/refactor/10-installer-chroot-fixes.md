# Beagle OS Server Installer Fixes and Documentation

## Issue #1: Chroot Detection in libvirt Management (FIXED)

### Problem
`can_manage_libvirt_system()` function used invalid syntax:
```bash
systemd-detect-virt --quiet --chroot
```
This always returned an error, causing the check to fail and the code to think it was NOT in a chroot environment.

### Root Cause
- `systemd-detect-virt` doesn't accept `--chroot` as a check parameter
- Need to call it without parameters and parse the output
- The function should check both `systemd-detect-virt` output AND `/run/systemd/system` existence

### Solution Applied
```bash
if command -v systemd-detect-virt >/dev/null 2>&1; then
    local virt_type
    virt_type=$(systemd-detect-virt 2>/dev/null || true)
    if [[ "$virt_type" == "chroot" ]]; then
      return 1
    fi
fi
```

### Testing
When this is fixed:
- `can_manage_libvirt_system()` returns true only on real host or VM (not in chroot)
- `can_manage_libvirt_system()` returns false during server installer chroot
- All `virsh` commands are skipped during chroot install
- No "libvirt qemu:///system is not ready" messages appear
- Install completes successfully
- First boot should have libvirt functional

## Files Modified
- `/home/dennis/beagle-os/scripts/install-beagle-host-services.sh` (lines 134-147)

## ISO Rebuild Status
- Fixed code committed
- New ISO building... (ETA ~30+ mins)
