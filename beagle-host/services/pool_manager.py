from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.virtualization.desktop_pool import (
    DesktopLease,
    DesktopPoolInfo,
    DesktopPoolMode,
    DesktopPoolSpec,
    SessionRecordingPolicy,
)
from core.virtualization.scheduler_policy import SchedulerPolicy, scheduler_policy_from_payload
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
_STATE_PENDING_GPU = "pending-gpu"


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
        list_nodes: Any = None,
        vm_node_of: Any = None,
        list_gpu_inventory: Any = None,
    ) -> None:
        self._state_file = Path(state_file)
        self._utcnow = utcnow or (lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        # Optional provider callables (may be None in unit tests / offline mode)
        self._start_vm = start_vm  # callable(vmid) -> None
        self._stop_vm = stop_vm    # callable(vmid) -> None
        self._reset_vm_to_template = reset_vm_to_template  # callable(vmid, template_id) -> None
        self._list_nodes = list_nodes  # callable() -> list[dict]
        self._vm_node_of = vm_node_of  # callable(vmid) -> str
        self._list_gpu_inventory = list_gpu_inventory  # callable() -> list[dict]

    # ------------------------------------------------------------------
    # State persistence helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if not self._state_file.exists():
            return {"pools": {}, "vms": {}, "gpu_reservations": {}}
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8") or "{}")
        except (json.JSONDecodeError, OSError):
            return {"pools": {}, "vms": {}}
        if not isinstance(data.get("pools"), dict):
            data["pools"] = {}
        if not isinstance(data.get("vms"), dict):
            data["vms"] = {}
        if not isinstance(data.get("gpu_reservations"), dict):
            data["gpu_reservations"] = {}
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
            "gpu_class": str(spec.gpu_class or "").strip(),
            "session_recording": self._normalize_session_recording(spec.session_recording),
            "recording_retention_days": self._normalize_retention_days(spec.recording_retention_days),
            "recording_watermark_enabled": bool(spec.recording_watermark_enabled),
            "recording_watermark_custom_text": self._normalize_watermark_text(spec.recording_watermark_custom_text),
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
        state["gpu_reservations"] = {
            vmid: item
            for vmid, item in state.get("gpu_reservations", {}).items()
            if str(item.get("pool_id") or "") != pool_id
        }
        self._save(state)
        return True

    def update_pool(self, pool_id: str, updates: dict[str, Any]) -> DesktopPoolInfo:
        """Update mutable pool fields (min/max size, enabled)."""
        _allowed = {
            "min_pool_size",
            "max_pool_size",
            "warm_pool_size",
            "enabled",
            "labels",
            "streaming_profile",
            "gpu_class",
            "session_recording",
            "recording_retention_days",
            "recording_watermark_enabled",
            "recording_watermark_custom_text",
        }
        state = self._load()
        if pool_id not in state["pools"]:
            raise ValueError(f"pool {pool_id!r} not found")
        pool_entry = state["pools"][pool_id]
        for key, value in updates.items():
            if key in _allowed:
                if key == "streaming_profile":
                    profile = None if value is None else streaming_profile_from_payload(value)
                    pool_entry[key] = streaming_profile_to_dict(profile)
                elif key == "gpu_class":
                    pool_entry[key] = str(value or "").strip()
                elif key == "session_recording":
                    pool_entry[key] = self._normalize_session_recording(value)
                elif key == "recording_retention_days":
                    pool_entry[key] = self._normalize_retention_days(value)
                elif key == "recording_watermark_enabled":
                    pool_entry[key] = bool(value)
                elif key == "recording_watermark_custom_text":
                    pool_entry[key] = self._normalize_watermark_text(value)
                else:
                    pool_entry[key] = value
        self._save(state)
        return self._pool_info(state, pool_id)

    @staticmethod
    def _normalize_session_recording(value: Any) -> str:
        if isinstance(value, SessionRecordingPolicy):
            raw = value.value
        else:
            raw = str(value or SessionRecordingPolicy.DISABLED.value).strip().lower()
        allowed = {
            SessionRecordingPolicy.DISABLED.value,
            SessionRecordingPolicy.ON_DEMAND.value,
            SessionRecordingPolicy.ALWAYS.value,
        }
        if raw not in allowed:
            return SessionRecordingPolicy.DISABLED.value
        return raw

    @staticmethod
    def _normalize_retention_days(value: Any) -> int:
        try:
            days = int(value)
        except Exception:
            days = 30
        return max(1, min(days, 3650))

    @staticmethod
    def _normalize_watermark_text(value: Any) -> str:
        text = str(value or "").strip()
        return text[:120]

    def get_pool_recording_retention_days(self, pool_id: str) -> int:
        state = self._load()
        pool = state.get("pools", {}).get(str(pool_id or "").strip())
        if not isinstance(pool, dict):
            return 30
        return self._normalize_retention_days(pool.get("recording_retention_days", 30))

    def get_pool_recording_watermark(self, pool_id: str) -> dict[str, Any]:
        state = self._load()
        pool = state.get("pools", {}).get(str(pool_id or "").strip())
        if not isinstance(pool, dict):
            return {"enabled": False, "custom_text": ""}
        return {
            "enabled": bool(pool.get("recording_watermark_enabled", False)),
            "custom_text": self._normalize_watermark_text(pool.get("recording_watermark_custom_text", "")),
        }

    @staticmethod
    def _gpu_class_normalized(gpu_class: Any) -> str:
        return str(gpu_class or "").strip().lower()

    @staticmethod
    def _gpu_matches_class(gpu_item: dict[str, Any], gpu_class: str) -> bool:
        if not isinstance(gpu_item, dict):
            return False
        normalized = PoolManagerService._gpu_class_normalized(gpu_class)
        if not normalized:
            return True
        status = str(gpu_item.get("status") or "").strip().lower()
        if not status:
            return False
        # Current implementation supports passthrough classes from inventory.
        if normalized.startswith("passthrough-"):
            remainder = normalized[len("passthrough-"):]
            vendor = ""
            model_token = ""
            if "-" in remainder:
                vendor, model_token = remainder.split("-", 1)
            else:
                vendor = remainder
            item_vendor = str(gpu_item.get("vendor") or "").strip().lower()
            item_model = str(gpu_item.get("model") or "").strip().lower()
            if vendor and item_vendor != vendor:
                return False
            if model_token:
                model_parts = [part for part in model_token.split("-") if part]
                if any(part not in item_model for part in model_parts):
                    return False
            return status in ("available-for-passthrough", "assigned")
        return False

    def _gpu_slots_by_node(self, gpu_class: str) -> dict[str, list[str]]:
        if self._list_gpu_inventory is None:
            return {}
        try:
            inventory = self._list_gpu_inventory()
        except Exception:
            return {}
        slots_by_node: dict[str, list[str]] = {}
        for item in inventory if isinstance(inventory, list) else []:
            if not isinstance(item, dict):
                continue
            if not self._gpu_matches_class(item, gpu_class):
                continue
            node = str(item.get("node") or "").strip()
            pci = str(item.get("pci_address") or "").strip().lower()
            status = str(item.get("status") or "").strip().lower()
            if not node or not pci:
                continue
            if status != "available-for-passthrough":
                continue
            slots_by_node.setdefault(node, [])
            if pci not in slots_by_node[node]:
                slots_by_node[node].append(pci)
        return slots_by_node

    @staticmethod
    def _reserved_slots(state: dict[str, Any], gpu_class: str) -> set[str]:
        normalized = PoolManagerService._gpu_class_normalized(gpu_class)
        reserved: set[str] = set()
        for item in state.get("gpu_reservations", {}).values():
            if not isinstance(item, dict):
                continue
            if PoolManagerService._gpu_class_normalized(item.get("gpu_class")) != normalized:
                continue
            slot = str(item.get("slot") or "").strip().lower()
            if slot:
                reserved.add(slot)
        return reserved

    @staticmethod
    def _cleanup_stale_gpu_reservations(state: dict[str, Any]) -> None:
        vms = state.get("vms", {})
        reservations = state.get("gpu_reservations", {})
        if not isinstance(vms, dict) or not isinstance(reservations, dict):
            return
        stale = [vmid for vmid in reservations.keys() if vmid not in vms]
        for vmid in stale:
            del reservations[vmid]

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

    def _online_nodes(self) -> list[str]:
        if self._list_nodes is None:
            return []
        nodes: list[str] = []
        try:
            payload = self._list_nodes()
        except Exception:
            return []
        for item in payload if isinstance(payload, list) else []:
            if not isinstance(item, dict):
                continue
            node = str(item.get("name") or item.get("node") or "").strip()
            status = str(item.get("status") or "unknown").strip().lower()
            if not node or status != "online":
                continue
            if node not in nodes:
                nodes.append(node)
        return sorted(nodes)

    def _known_vm_node(self, vmid: int) -> str:
        if self._vm_node_of is None:
            return ""
        try:
            return str(self._vm_node_of(int(vmid)) or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _nodes_for_group(group_vmids: tuple[int, ...], placements: dict[int, str], *, skip_vmid: int) -> set[str]:
        nodes: set[str] = set()
        for item in group_vmids:
            if int(item) == int(skip_vmid):
                continue
            node = str(placements.get(int(item), "") or "").strip()
            if node:
                nodes.add(node)
        return nodes

    def _choose_node_for_vmid(
        self,
        *,
        vmid: int,
        policy: SchedulerPolicy,
        placements: dict[int, str],
    ) -> str:
        online_nodes = self._online_nodes()
        current = str(placements.get(int(vmid), "") or self._known_vm_node(int(vmid)) or "").strip()
        if not online_nodes:
            return current

        avoid_nodes: set[str] = set()
        preferred_nodes: set[str] = set()

        for group in policy.anti_affinity_groups:
            if int(vmid) in set(group.vmids):
                avoid_nodes |= self._nodes_for_group(group.vmids, placements, skip_vmid=int(vmid))

        for group in policy.affinity_groups:
            if int(vmid) in set(group.vmids):
                preferred_nodes |= self._nodes_for_group(group.vmids, placements, skip_vmid=int(vmid))

        candidates = [node for node in online_nodes if node not in avoid_nodes]
        if not candidates:
            candidates = list(online_nodes)

        preferred_candidates = [node for node in sorted(preferred_nodes) if node in candidates]
        if preferred_candidates:
            return preferred_candidates[0]
        if current and current in candidates:
            return current
        return sorted(candidates)[0]

    def register_vm(self, pool_id: str, vmid: int, *, scheduler_policy: SchedulerPolicy | dict[str, Any] | None = None) -> dict[str, Any]:
        """Register a VM slot in the pool as free."""
        state = self._load()
        if pool_id not in state["pools"]:
            raise ValueError(f"pool {pool_id!r} not found")

        pool_cfg = state["pools"][pool_id]
        gpu_class = str(pool_cfg.get("gpu_class") or "").strip()

        self._cleanup_stale_gpu_reservations(state)

        policy = scheduler_policy if isinstance(scheduler_policy, SchedulerPolicy) else scheduler_policy_from_payload(scheduler_policy)
        placements: dict[int, str] = {}
        for item in self._pool_vms(state, pool_id):
            if not isinstance(item, dict):
                continue
            existing_vmid = int(item.get("vmid") or 0)
            if existing_vmid <= 0:
                continue
            existing_node = str(item.get("node") or self._known_vm_node(existing_vmid) or "").strip()
            if existing_node:
                placements[existing_vmid] = existing_node

        node = self._choose_node_for_vmid(vmid=int(vmid), policy=policy, placements=placements)
        vm_state = _STATE_FREE
        reserved_slot = ""

        if gpu_class:
            slots_by_node = self._gpu_slots_by_node(gpu_class)
            if slots_by_node:
                reserved = self._reserved_slots(state, gpu_class)
                candidate_nodes = [
                    node_name
                    for node_name in sorted(slots_by_node.keys())
                    if any(slot not in reserved for slot in slots_by_node.get(node_name, []))
                ]
                if candidate_nodes:
                    if node in candidate_nodes:
                        selected_node = node
                    else:
                        selected_node = candidate_nodes[0]
                    node = selected_node
                    for slot in slots_by_node.get(selected_node, []):
                        if slot not in reserved:
                            reserved_slot = slot
                            break
                else:
                    node = ""
                    vm_state = _STATE_PENDING_GPU
            else:
                node = ""
                vm_state = _STATE_PENDING_GPU

        vm_key = str(vmid)
        state["vms"][vm_key] = {
            "vmid": vmid,
            "pool_id": pool_id,
            "node": node,
            "state": vm_state,
            "user_id": None,
            "assigned_at": None,
        }
        if gpu_class and vm_state == _STATE_FREE and reserved_slot:
            state["gpu_reservations"][vm_key] = {
                "pool_id": pool_id,
                "vmid": int(vmid),
                "gpu_class": gpu_class,
                "node": node,
                "slot": reserved_slot,
                "reserved_at": self._utcnow(),
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
        recording_raw = self._normalize_session_recording(pool.get("session_recording"))
        try:
            session_recording = SessionRecordingPolicy(recording_raw)
        except ValueError:
            session_recording = SessionRecordingPolicy.DISABLED
        return DesktopPoolInfo(
            pool_id=pool_id,
            template_id=pool.get("template_id", ""),
            mode=mode,
            min_pool_size=int(pool.get("min_pool_size", 0)),
            max_pool_size=int(pool.get("max_pool_size", 0)),
            warm_pool_size=int(pool.get("warm_pool_size", 0)),
            gpu_class=str(pool.get("gpu_class") or "").strip(),
            session_recording=session_recording,
            recording_retention_days=self._normalize_retention_days(pool.get("recording_retention_days", 30)),
            free_desktops=counts[_STATE_FREE],
            in_use_desktops=counts[_STATE_IN_USE],
            recycling_desktops=counts[_STATE_RECYCLING],
            error_desktops=counts[_STATE_ERROR],
            enabled=bool(pool.get("enabled", True)),
            streaming_profile=self._parse_streaming_profile(pool.get("streaming_profile")),
            recording_watermark_enabled=bool(pool.get("recording_watermark_enabled", False)),
            recording_watermark_custom_text=self._normalize_watermark_text(pool.get("recording_watermark_custom_text", "")),
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
            vm["stream_health"] = None
        elif mode == DesktopPoolMode.FLOATING_PERSISTENT:
            vm["state"] = _STATE_FREE
            # keep user_id for next login
            vm["stream_health"] = None
        elif mode == DesktopPoolMode.DEDICATED:
            vm["state"] = _STATE_FREE
            # keep user_id permanently
            vm["stream_health"] = None
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
        vm["stream_health"] = None
        self._save(state)
        return self._make_lease(pool_id, vm, mode)

    def list_desktops(self, pool_id: str) -> list[dict[str, Any]]:
        """Return all VM slot states for a pool."""
        state = self._load()
        if pool_id not in state["pools"]:
            raise ValueError(f"pool {pool_id!r} not found")
        return list(self._pool_vms(state, pool_id))

    def list_active_sessions(self) -> list[dict[str, Any]]:
        """Return all in-use desktop leases as session objects."""
        state = self._load()
        sessions: list[dict[str, Any]] = []
        for vm in state["vms"].values():
            if str(vm.get("state") or "") != _STATE_IN_USE:
                continue
            pool_id = str(vm.get("pool_id") or "").strip()
            if not pool_id:
                continue
            pool_cfg = state["pools"].get(pool_id, {})
            mode_raw = pool_cfg.get("mode", DesktopPoolMode.FLOATING_NON_PERSISTENT.value)
            try:
                mode = DesktopPoolMode(mode_raw)
            except ValueError:
                mode = DesktopPoolMode.FLOATING_NON_PERSISTENT
            vmid = int(vm.get("vmid") or 0)
            session_id = f"{pool_id}:{vmid}"
            sessions.append(
                {
                    "session_id": session_id,
                    "pool_id": pool_id,
                    "vmid": vmid,
                    "user_id": str(vm.get("user_id") or ""),
                    "mode": mode.value,
                    "state": _STATE_IN_USE,
                    "assigned_at": str(vm.get("assigned_at") or ""),
                    "stream_health": vm.get("stream_health") if isinstance(vm.get("stream_health"), dict) else None,
                }
            )
        sessions.sort(key=lambda item: str(item.get("assigned_at") or ""), reverse=True)
        return sessions

    def update_stream_health(self, *, pool_id: str, vmid: int, stream_health: dict[str, Any] | None) -> DesktopLease:
        """Persist stream-health telemetry for one in-use desktop lease."""
        state = self._load()
        vm_key = str(vmid)
        vm = state["vms"].get(vm_key)
        if vm is None or vm.get("pool_id") != pool_id:
            raise ValueError(f"vmid {vmid} not found in pool {pool_id!r}")

        pool_cfg = state["pools"].get(pool_id, {})
        mode_raw = pool_cfg.get("mode", DesktopPoolMode.FLOATING_NON_PERSISTENT.value)
        try:
            mode = DesktopPoolMode(mode_raw)
        except ValueError:
            mode = DesktopPoolMode.FLOATING_NON_PERSISTENT

        metrics = stream_health if isinstance(stream_health, dict) else {}
        vm["stream_health"] = {
            "rtt_ms": int(metrics["rtt_ms"]) if metrics.get("rtt_ms") is not None else None,
            "fps": int(metrics["fps"]) if metrics.get("fps") is not None else None,
            "dropped_frames": int(metrics["dropped_frames"]) if metrics.get("dropped_frames") is not None else None,
            "encoder_load": int(metrics["encoder_load"]) if metrics.get("encoder_load") is not None else None,
            "updated_at": str(metrics.get("updated_at") or self._utcnow()),
        }
        self._save(state)
        return self._make_lease(pool_id, vm, mode)

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
        gpu_class = str(pool_cfg.get("gpu_class") or "").strip()
        if target_size < min_size:
            target_size = min_size
        if target_size > max_size:
            target_size = max_size
        if gpu_class:
            slots_by_node = self._gpu_slots_by_node(gpu_class)
            total_slots = sum(len(slots) for slots in slots_by_node.values())
            if total_slots > 0 and target_size > total_slots:
                target_size = total_slots
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
            stream_health=vm.get("stream_health") if isinstance(vm.get("stream_health"), dict) else None,
        )

    def pool_info_to_dict(self, info: DesktopPoolInfo) -> dict[str, Any]:
        return {
            "pool_id": info.pool_id,
            "template_id": info.template_id,
            "mode": info.mode.value if hasattr(info.mode, "value") else str(info.mode),
            "min_pool_size": info.min_pool_size,
            "max_pool_size": info.max_pool_size,
            "warm_pool_size": info.warm_pool_size,
            "gpu_class": info.gpu_class,
            "session_recording": info.session_recording.value if hasattr(info.session_recording, "value") else str(info.session_recording),
            "recording_retention_days": int(info.recording_retention_days),
            "recording_watermark_enabled": bool(info.recording_watermark_enabled),
            "recording_watermark_custom_text": str(info.recording_watermark_custom_text or ""),
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
            "stream_health": lease.stream_health,
        }
