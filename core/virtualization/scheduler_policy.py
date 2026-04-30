from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SchedulerGroup:
    group_id: str
    vmids: tuple[int, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SchedulerPolicy:
    affinity_groups: tuple[SchedulerGroup, ...] = field(default_factory=tuple)
    anti_affinity_groups: tuple[SchedulerGroup, ...] = field(default_factory=tuple)


def _normalize_group(raw: Any, *, prefix: str, index: int) -> SchedulerGroup | None:
    if not isinstance(raw, dict):
        return None
    _vmids_candidate = raw.get("vmids")
    vmids_raw: list[Any] = _vmids_candidate if isinstance(_vmids_candidate, list) else []
    vmids: list[int] = []
    for item in vmids_raw:
        try:
            vmid = int(item)
        except (TypeError, ValueError):
            continue
        if vmid <= 0:
            continue
        if vmid not in vmids:
            vmids.append(vmid)
    if len(vmids) < 2:
        return None
    group_id = str(raw.get("group_id") or raw.get("name") or f"{prefix}-{index}").strip() or f"{prefix}-{index}"
    return SchedulerGroup(group_id=group_id, vmids=tuple(vmids))


def scheduler_policy_from_payload(payload: Any) -> SchedulerPolicy:
    if not isinstance(payload, dict):
        return SchedulerPolicy()

    _affinity_candidate = payload.get("affinity_groups")
    affinity_raw: list[Any] = _affinity_candidate if isinstance(_affinity_candidate, list) else []
    _anti_candidate = payload.get("anti_affinity_groups")
    anti_raw: list[Any] = _anti_candidate if isinstance(_anti_candidate, list) else []

    affinity_groups: list[SchedulerGroup] = []
    anti_affinity_groups: list[SchedulerGroup] = []

    for idx, item in enumerate(affinity_raw, start=1):
        group = _normalize_group(item, prefix="affinity", index=idx)
        if group is not None:
            affinity_groups.append(group)

    for idx, item in enumerate(anti_raw, start=1):
        group = _normalize_group(item, prefix="anti-affinity", index=idx)
        if group is not None:
            anti_affinity_groups.append(group)

    return SchedulerPolicy(
        affinity_groups=tuple(affinity_groups),
        anti_affinity_groups=tuple(anti_affinity_groups),
    )
