from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from scheduler_warm_pool_auto_apply import (
    normalize_auto_apply_config,
    select_recommendations_for_auto_apply,
    should_run_auto_apply,
)


def test_normalize_auto_apply_config_clamps_invalid_values() -> None:
    cfg = normalize_auto_apply_config(
        {
            "warm_pool_auto_apply_enabled": True,
            "warm_pool_auto_apply_max_pools_per_run": 200,
            "warm_pool_auto_apply_max_increase": -3,
            "warm_pool_auto_apply_min_miss_rate": 1.7,
            "warm_pool_auto_apply_cooldown_minutes": 1,
        }
    )
    assert cfg["warm_pool_auto_apply_enabled"] is True
    assert cfg["warm_pool_auto_apply_max_pools_per_run"] == 20
    assert cfg["warm_pool_auto_apply_max_increase"] == 1
    assert cfg["warm_pool_auto_apply_min_miss_rate"] == 1.0
    assert cfg["warm_pool_auto_apply_cooldown_minutes"] == 5


def test_select_recommendations_for_auto_apply_applies_guardrails() -> None:
    selected = select_recommendations_for_auto_apply(
        [
            {
                "pool_id": "pool-a",
                "current_warm_pool_size": 1,
                "recommended_warm_pool_size": 6,
                "miss_rate": 0.82,
                "prewarm_hits": 1,
                "prewarm_misses": 9,
            },
            {
                "pool_id": "pool-b",
                "current_warm_pool_size": 2,
                "recommended_warm_pool_size": 3,
                "miss_rate": 0.2,
                "prewarm_hits": 8,
                "prewarm_misses": 2,
            },
            {
                "pool_id": "pool-c",
                "current_warm_pool_size": 3,
                "recommended_warm_pool_size": 4,
                "miss_rate": 0.55,
                "prewarm_hits": 1,
                "prewarm_misses": 3,
            },
        ],
        max_pools_per_run=2,
        max_increase=2,
        min_miss_rate=0.35,
    )

    assert len(selected) == 2
    assert selected[0]["pool_id"] == "pool-a"
    assert selected[0]["recommended_warm_pool_size"] == 3
    assert selected[1]["pool_id"] == "pool-c"


def test_should_run_auto_apply_respects_cooldown() -> None:
    now = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
    assert should_run_auto_apply(
        last_run_at="2026-04-28T10:00:00Z",
        cooldown_minutes=30,
        now=now,
    ) is True
    assert should_run_auto_apply(
        last_run_at="2026-04-28T11:50:00Z",
        cooldown_minutes=30,
        now=now,
    ) is False
