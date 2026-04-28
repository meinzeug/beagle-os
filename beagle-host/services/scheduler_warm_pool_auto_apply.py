from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def normalize_auto_apply_config(config: dict[str, Any] | None) -> dict[str, Any]:
    source = config if isinstance(config, dict) else {}

    enabled = bool(source.get("warm_pool_auto_apply_enabled", False))

    try:
        max_pools_per_run = int(source.get("warm_pool_auto_apply_max_pools_per_run", 3) or 3)
    except (TypeError, ValueError):
        max_pools_per_run = 3
    max_pools_per_run = max(1, min(20, max_pools_per_run))

    try:
        max_increase = int(source.get("warm_pool_auto_apply_max_increase", 2) or 2)
    except (TypeError, ValueError):
        max_increase = 2
    max_increase = max(1, min(10, max_increase))

    try:
        min_miss_rate = float(source.get("warm_pool_auto_apply_min_miss_rate", 0.35) or 0.35)
    except (TypeError, ValueError):
        min_miss_rate = 0.35
    min_miss_rate = max(0.0, min(1.0, min_miss_rate))

    try:
        cooldown_minutes = int(source.get("warm_pool_auto_apply_cooldown_minutes", 30) or 30)
    except (TypeError, ValueError):
        cooldown_minutes = 30
    cooldown_minutes = max(5, min(720, cooldown_minutes))

    last_run_at = str(source.get("warm_pool_auto_apply_last_run_at") or "").strip()

    return {
        "warm_pool_auto_apply_enabled": enabled,
        "warm_pool_auto_apply_max_pools_per_run": max_pools_per_run,
        "warm_pool_auto_apply_max_increase": max_increase,
        "warm_pool_auto_apply_min_miss_rate": round(min_miss_rate, 4),
        "warm_pool_auto_apply_cooldown_minutes": cooldown_minutes,
        "warm_pool_auto_apply_last_run_at": last_run_at,
    }


def should_run_auto_apply(
    *,
    last_run_at: str,
    cooldown_minutes: int,
    now: datetime,
) -> bool:
    stamp = str(last_run_at or "").strip()
    if not stamp:
        return True
    try:
        parsed = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return now - parsed >= timedelta(minutes=max(1, int(cooldown_minutes or 1)))


def select_recommendations_for_auto_apply(
    recommendations: list[dict[str, Any]],
    *,
    max_pools_per_run: int,
    max_increase: int,
    min_miss_rate: float,
) -> list[dict[str, Any]]:
    if not isinstance(recommendations, list):
        return []

    selected: list[dict[str, Any]] = []
    for item in recommendations:
        if not isinstance(item, dict):
            continue
        pool_id = str(item.get("pool_id") or "").strip()
        if not pool_id:
            continue

        try:
            current = int(item.get("current_warm_pool_size") or 0)
            recommended = int(item.get("recommended_warm_pool_size") or 0)
            miss_rate = float(item.get("miss_rate") or 0.0)
            misses = int(item.get("prewarm_misses") or 0)
            hits = int(item.get("prewarm_hits") or 0)
        except (TypeError, ValueError):
            continue

        if recommended <= current:
            continue
        if miss_rate < float(min_miss_rate):
            continue
        if misses <= hits:
            continue

        capped_target = min(recommended, current + max(1, int(max_increase)))
        selected.append(
            {
                **item,
                "pool_id": pool_id,
                "current_warm_pool_size": current,
                "recommended_warm_pool_size": int(capped_target),
                "miss_rate": round(miss_rate, 4),
                "prewarm_misses": misses,
                "prewarm_hits": hits,
            }
        )

    selected.sort(
        key=lambda value: (
            float(value.get("miss_rate", 0.0) or 0.0),
            int(value.get("prewarm_misses", 0) or 0),
        ),
        reverse=True,
    )
    return selected[: max(1, int(max_pools_per_run or 1))]
