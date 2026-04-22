from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.virtualization.desktop_pool import (
    DesktopLease,
    DesktopPoolInfo,
    DesktopPoolMode,
    DesktopPoolSpec,
)
from core.virtualization.streaming_profile import (
    StreamingProfile,
    streaming_profile_from_payload,
    streaming_profile_to_dict,
)


# ---------------------------------------------------------------------------
# VM Desktop State keys
# ---------------------------------------------------------------------------
_STATE_FREE = "free"
_STATE_IN_USE = "in_use"
_STATE_RECYCLING = "recycling"
_STATE_ERROR = "error"


class PoolManagerService:
    """
    Manages VDI desktop pools stored in a JSON state file.

    Supports three pool modes:
    - floating_non_persistent: VM is reset to template state on release.
    - floating_persistent: VM is kept per-user across sessions.
    - dedicated: One VM permanently assigned per user.
    """

    def __init__(
        self,
        *,
        state_file: Path,
        utcnow: Any = None,
        start_vm: Any = None,
        stop_vm: Any = None,
        reset_vm_to_template: Any = None,
    ) -> None:
        self._state_file = Path(state_file)
        self._utcnow = utcnow or (lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        # Optional provider callables (may be None in unit tests / offline mode)
        self._start_vm = start_vm  # callable(vmid) -> None
        self._stop_vm = stop_vm    # callable(vmid) -> None
        self._reset_vm_to_template = reset_vm_to_template  # callable(vmid, template_id) -> None

    # ------------------------------------------------------------------
    # State persistence helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if not self._state_file.exists():
            return {"pools": {}, "vms": {}}
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8") or "{}")
        except (json.JSONDecodeError, OSError):
            return {"pools": {}, "vms": {}}
        if not isinstance(data.get("pools"), dict):
            data["pools"] = {}
        if not isinstance(data.get("vms"), dict):
            data["vms"] = {}
        return data

    def _save(self, state: dict[str, Any]) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

    # ------------------------------------------------------------------
    # Pool CRUD
    # ------------------------------------------------------------------

    def create_pool(self, spec: DesktopPoolSpec) -> DesktopPoolInfo:
        """Persist a new pool configuration."""
        pool_id = str(spec.pool_id or "").strip()
        if not pool_id:
            raise ValueError("pool_id is required")
        state = self._load()
        if pool_id in state["pools"]:
            raise ValueError(f"pool {pool_id!r} already exists")
        state["pools"][pool_id] = {
            "pool_id": pool_id,
            "template_id": spec.template_id,
            "mode": str(spec.mode.value if hasattr(spec.mode, "value") else spec.mode),
            "min_pool_size": spec.min_pool_size,
            "max_pool_size": spec.max_pool_size,
            "warm_pool_size": spec.warm_pool_size,
            "cpu_cores": spec.cpu_cores,
            "memory_mib": spec.memory_mib,
            "storage_pool": spec.storage_pool,
            "enabled": spec.enabled,
            "labels": list(spec.labels),
            "streaming_profile": streaming_profile_to_dict(spec.streaming_profile),
            "created_at": self._utcnow(),
        }
        self._save(state)
        return self._pool_info(state, pool_id)

    def get_pool(self, pool_id: str) -> DesktopPoolInfo | None:
        state = self._load()
        if pool_id not in state["pools"]:
            return None
        return self._pool_info(state, pool_id)

    def list_pools(self) -> list[DesktopPoolInfo]:
        state = self._load()
        return [self._pool_info(state, pid) for pid in state["pools"]]

    def delete_pool(self, pool_id: str) -> bool:
        state = self._load()
        if pool_id not in state["pools"]:
            return False
        del state["pools"][pool_id]
        # Remove all VMs belonging to this pool
        state["vms"] = {
            vmid: vm for vmid, vm in state["vms"].items()
            if vm.get("pool_id") != pool_id
        }
        self._save(state)
        return True

    def update_pool(self, pool_id: str, updates: dict[str, Any]) -> DesktopPoolInfo:
        """Update mutable pool fields (min/max size, enabled)."""
        _allowed = {"min_pool_size", "max_pool_size", "warm_pool_size", "enabled", "labels", "streaming_profile"}
        state = self._load()
        if pool_id not in state["pools"]:
            raise ValueError(f"pool {pool_id!r} not found")
        pool_entry = state["pools"][pool_id]
        for key, value in updates.items():
            if key in _allowed:
                if key == "streaming_profile":
                    profile = None if value is None else streaming_profile_from_payload(value)
                    pool_entry[key] = streaming_profile_to_dict(profile)
                else:
                    pool_entry[key] = value
        self._save(state)
        return self._pool_info(state, pool_id)

    @staticmethod
    def _parse_streaming_profile(raw: Any) -> StreamingProfile | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            return None
        try:
            return streaming_profile_from_payload(raw)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # VM slot management
    # ------------------------------------------------------------------

    def register_vm(self, pool_id: str, vmid: int) -> dict[str, Any]:
        """Register a VM slot in the pool as free."""
        state = self._load()
        if pool_id not in state["pools"]:
            raise ValueError(f"pool {pool_id!r} not found")
        vm_key = str(vmid)
        state["vms"][vm_key] = {
            "vmid": vmid,
            "pool_id": pool_id,
            "state": _STATE_FREE,
            "user_id": None,
            "assigned_at": None,
        }
        self._save(state)
        return state["vms"][vm_key]

    def _pool_vms(self, state: dict[str, Any], pool_id: str) -> list[dict[str, Any]]:
        return [vm for vm in state["vms"].values() if vm.get("pool_id") == pool_id]

    def _pool_info(self, state: dict[str, Any], pool_id: str) -> DesktopPoolInfo:
        pool = state["pools"][pool_id]
        vms = self._pool_vms(state, pool_id)
        counts: dict[str, int] = {_STATE_FREE: 0, _STATE_IN_USE: 0, _STATE_RECYCLING: 0, _STATE_ERROR: 0}
        for vm in vms:
            counts[vm.get("state", _STATE_FREE)] = counts.get(vm.get("state", _STATE_FREE), 0) + 1
        mode_raw = pool.get("mode", "floating_non_persistent")
        try:
            mode = DesktopPoolMode(mode_raw)
        except ValueError:
            mode = DesktopPoolMode.FLOATING_NON_PERSISTENT
        return DesktopPoolInfo(
            pool_id=pool_id,
            template_id=pool.get("template_id", ""),
            mode=mode,
            min_pool_size=int(pool.get("min_pool_size", 0)),
            max_pool_size=int(pool.get("max_pool_size", 0)),
            warm_pool_size=int(pool.get("warm_pool_size", 0)),
            free_desktops=counts[_STATE_FREE],
            in_use_desktops=counts[_STATE_IN_USE],
            recycling_desktops=counts[_STATE_RECYCLING],
            error_desktops=counts[_STATE_ERROR],
            enabled=bool(pool.get("enabled", True)),
            streaming_profile=self._parse_streaming_profile(pool.get("streaming_profile")),
        )

    # ------------------------------------------------------------------
    # Desktop allocation / release / recycle
    # ------------------------------------------------------------------

    def allocate_desktop(self, pool_id: str, user_id: str) -> DesktopLease:
        """
        Allocate a desktop to a user.

        - floating_non_persistent / floating_persistent:
            Look for a free VM or (for persistent) a VM already assigned to this user.
        - dedicated:
            Look for VM already assigned to this user; if none, take a free one.
        """
        user = str(user_id or "").strip()
        if not user:
            raise ValueError("user_id is required")
        state = self._load()
        if pool_id not in state["pools"]:
            raise ValueError(f"pool {pool_id!r} not found")

        pool_cfg = state["pools"][pool_id]
        mode_raw = pool_cfg.get("mode", "floating_non_persistent")
        try:
            mode = DesktopPoolMode(mode_raw)
        except ValueError:
            mode = DesktopPoolMode.FLOATING_NON_PERSISTENT

        vms = self._pool_vms(state, pool_id)

        # For persistent/dedicated modes: try to find existing assigned VM
        if mode in (DesktopPoolMode.FLOATING_PERSISTENT, DesktopPoolMode.DEDICATED):
            for vm in vms:
                if vm.get("user_id") == user and vm.get("state") == _STATE_IN_USE:
                    # Already in use by this user — return existing lease
                    return self._make_lease(pool_id, vm, mode)
            # Find the persisted VM for this user (not currently in session)
            for vm in vms:
                if vm.get("user_id") == user and vm.get("state") == _STATE_FREE:
                    vm["state"] = _STATE_IN_USE
                    vm["assigned_at"] = self._utcnow()
                    self._save(state)
                    if self._start_vm is not None:
                        try:
                            self._start_vm(vm["vmid"])
                        except Exception:
                            pass
                    return self._make_lease(pool_id, vm, mode)

        # For all modes: find an unassigned free VM
        for vm in vms:
            if vm.get("state") == _STATE_FREE and vm.get("user_id") is None:
                vm["state"] = _STATE_IN_USE
                vm["user_id"] = user
                vm["assigned_at"] = self._utcnow()
                self._save(state)
                if self._start_vm is not None:
                    try:
                        self._start_vm(vm["vmid"])
                    except Exception:
                        pass
                return self._make_lease(pool_id, vm, mode)

        raise RuntimeError(f"no free desktop available in pool {pool_id!r}")

    def release_desktop(self, pool_id: str, vmid: int, user_id: str) -> DesktopLease:
        """
        Release a desktop after user session ends.

        Mode behaviour:
        - floating_non_persistent: mark as recycling (will be reset to template).
        - floating_persistent:     mark as free but keep user_id assignment.
        - dedicated:               mark as free, keep user_id permanently.
        """
        state = self._load()
        vm_key = str(vmid)
        vm = state["vms"].get(vm_key)
        if vm is None or vm.get("pool_id") != pool_id:
            raise ValueError(f"vmid {vmid} not found in pool {pool_id!r}")

        pool_cfg = state["pools"].get(pool_id, {})
        mode_raw = pool_cfg.get("mode", "floating_non_persistent")
        try:
            mode = DesktopPoolMode(mode_raw)
        except ValueError:
            mode = DesktopPoolMode.FLOATING_NON_PERSISTENT

        if mode == DesktopPoolMode.FLOATING_NON_PERSISTENT:
            vm["state"] = _STATE_RECYCLING
            vm["user_id"] = None
            vm["assigned_at"] = None
        elif mode == DesktopPoolMode.FLOATING_PERSISTENT:
            vm["state"] = _STATE_FREE
            # keep user_id for next login
        elif mode == DesktopPoolMode.DEDICATED:
            vm["state"] = _STATE_FREE
            # keep user_id permanently
        self._save(state)
        if self._stop_vm is not None:
            try:
                self._stop_vm(vmid)
            except Exception:
                pass
        return self._make_lease(pool_id, vm, mode)

    def recycle_desktop(self, pool_id: str, vmid: int) -> DesktopLease:
        """
        Reset a recycling VM to template state and mark it free.
        Typically called by background recycler after non-persistent release.
        """
        state = self._load()
        vm_key = str(vmid)
        vm = state["vms"].get(vm_key)
        if vm is None or vm.get("pool_id") != pool_id:
            raise ValueError(f"vmid {vmid} not found in pool {pool_id!r}")

        pool_cfg = state["pools"].get(pool_id, {})
        template_id = pool_cfg.get("template_id", "")
        mode_raw = pool_cfg.get("mode", "floating_non_persistent")
        try:
            mode = DesktopPoolMode(mode_raw)
        except ValueError:
            mode = DesktopPoolMode.FLOATING_NON_PERSISTENT

        if self._reset_vm_to_template is not None:
            try:
                self._reset_vm_to_template(vmid, template_id)
            except Exception:
                vm["state"] = _STATE_ERROR
                self._save(state)
                return self._make_lease(pool_id, vm, mode)

        vm["state"] = _STATE_FREE
        vm["user_id"] = None
        vm["assigned_at"] = None
        self._save(state)
        return self._make_lease(pool_id, vm, mode)

    def list_desktops(self, pool_id: str) -> list[dict[str, Any]]:
        """Return all VM slot states for a pool."""
        state = self._load()
        if pool_id not in state["pools"]:
            raise ValueError(f"pool {pool_id!r} not found")
        return list(self._pool_vms(state, pool_id))

    # ------------------------------------------------------------------
    # Scale pool
    # ------------------------------------------------------------------

    def scale_pool(self, pool_id: str, target_size: int) -> DesktopPoolInfo:
        """
        Adjust the pool's warm_pool_size to target_size.
        Actual VM provisioning is done externally (provider layer).
        """
        state = self._load()
        if pool_id not in state["pools"]:
            raise ValueError(f"pool {pool_id!r} not found")
        pool_cfg = state["pools"][pool_id]
        min_size = int(pool_cfg.get("min_pool_size", 0))
        max_size = int(pool_cfg.get("max_pool_size", 999))
        if target_size < min_size:
            target_size = min_size
        if target_size > max_size:
            target_size = max_size
        pool_cfg["warm_pool_size"] = target_size
        self._save(state)
        return self._pool_info(state, pool_id)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_lease(pool_id: str, vm: dict[str, Any], mode: DesktopPoolMode) -> DesktopLease:
        return DesktopLease(
            pool_id=pool_id,
            vmid=int(vm["vmid"]),
            user_id=str(vm.get("user_id") or ""),
            mode=mode,
            state=str(vm.get("state", _STATE_FREE)),
            assigned_at=str(vm.get("assigned_at") or ""),
        )

    def pool_info_to_dict(self, info: DesktopPoolInfo) -> dict[str, Any]:
        return {
            "pool_id": info.pool_id,
            "template_id": info.template_id,
            "mode": info.mode.value if hasattr(info.mode, "value") else str(info.mode),
            "min_pool_size": info.min_pool_size,
            "max_pool_size": info.max_pool_size,
            "warm_pool_size": info.warm_pool_size,
            "free_desktops": info.free_desktops,
            "in_use_desktops": info.in_use_desktops,
            "recycling_desktops": info.recycling_desktops,
            "error_desktops": info.error_desktops,
            "enabled": info.enabled,
            "streaming_profile": streaming_profile_to_dict(info.streaming_profile),
        }

    def lease_to_dict(self, lease: DesktopLease) -> dict[str, Any]:
        return {
            "pool_id": lease.pool_id,
            "vmid": lease.vmid,
            "user_id": lease.user_id,
            "mode": lease.mode.value if hasattr(lease.mode, "value") else str(lease.mode),
            "state": lease.state,
            "assigned_at": lease.assigned_at,
        }
