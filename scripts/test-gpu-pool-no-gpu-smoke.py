#!/usr/bin/env python3
"""Smoke: Gaming pool blocks allocation cleanly when no GPU is available.

Validates that:
- A gaming pool with a gpu_class puts VMs into 'pending-gpu' state
- allocate_desktop() raises RuntimeError('no free desktop available')
  instead of silently falling back to a CPU-only VM

Run on srv1 (which has no GPU inventory):
    python3 /opt/beagle/scripts/test-gpu-pool-no-gpu-smoke.py

Expected output: GPU_POOL_NO_GPU_SMOKE=PASS
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Make the pool_manager importable from /opt/beagle/services/
_OPT = Path("/opt/beagle")
_SERVICES_DIR = _OPT / "services"
if str(_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICES_DIR))
# core/ is at /opt/beagle/core
_CORE_DIR = _OPT / "core"
if str(_OPT) not in sys.path:
    sys.path.insert(0, str(_OPT))

# Also support running locally from repo root
_REPO_ROOT = Path(__file__).resolve().parents[1]
_REPO_SERVICES = _REPO_ROOT / "beagle-host" / "services"
if str(_REPO_SERVICES) not in sys.path:
    sys.path.insert(0, str(_REPO_SERVICES))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def main() -> int:
    try:
        from core.virtualization.desktop_pool import (
            DesktopPoolMode,
            DesktopPoolSpec,
            DesktopPoolType,
        )
        from pool_manager import PoolManagerService
    except ImportError as exc:
        print(f"GPU_POOL_NO_GPU_SMOKE=FAIL")
        print(f"error=import error: {exc}")
        return 2

    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "pool_state.json"

        service = PoolManagerService(
            state_file=str(state_file),
            list_nodes=lambda: [{"name": "node-a", "status": "online"}],
            # Empty GPU inventory — simulates a server without GPU (e.g. srv1)
            list_gpu_inventory=lambda: [],
        )

        pool_id = "gpu-smoke-no-gpu"
        service.create_pool(
            DesktopPoolSpec(
                pool_id=pool_id,
                template_id="tpl-smoke",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=4,
                warm_pool_size=1,
                cpu_cores=8,
                memory_mib=16384,
                storage_pool="local",
                pool_type=DesktopPoolType.GAMING,
                gpu_class="passthrough-nvidia-rtx-3090",
            )
        )

        # Register a VM — with no GPU inventory it must land in pending-gpu
        vm = service.register_vm(pool_id, 9990)
        vm_state = str(vm.get("state") or "")
        if vm_state != "pending-gpu":
            print(f"GPU_POOL_NO_GPU_SMOKE=FAIL")
            print(f"error=expected vm state 'pending-gpu', got '{vm_state}'")
            return 1

        # Allocation must fail cleanly — no CPU fallback
        try:
            service.allocate_desktop(pool_id, "smoke-user")
            print(f"GPU_POOL_NO_GPU_SMOKE=FAIL")
            print("error=allocate_desktop did not raise for no-GPU pool (CPU fallback occurred!)")
            return 1
        except RuntimeError as exc:
            if "no free desktop" not in str(exc).lower():
                print(f"GPU_POOL_NO_GPU_SMOKE=FAIL")
                print(f"error=wrong exception message: {exc}")
                return 1
            # Expected: allocation blocked cleanly

    print("GPU_POOL_NO_GPU_SMOKE=PASS")
    print("state=pending-gpu vm blocked allocation as expected (no GPU fallback)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
