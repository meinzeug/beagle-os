#!/usr/bin/env python3
"""Beagle Fleet State Benchmark — JSON vs SQLite lookup performance.

Generates 1000 VM records, then measures lookup latency for:
  - JSON full-file read + linear scan
  - SQLite indexed lookup via VmRepository

Usage:
    python3 scripts/bench-fleet-state.py [--count 1000] [--runs 100]

Target: SQLite P99 < 5ms for single-VM lookup, JSON > 50ms at 1000 VMs.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.persistence.json_state_store import JsonStateStore  # noqa: E402
from core.persistence.sqlite_db import BeagleDb  # noqa: E402
from core.repository.vm_repository import VmRepository  # noqa: E402

SCHEMA_DIR = REPO_ROOT / "core" / "persistence" / "migrations"


def _make_vm(vmid: int) -> dict:
    return {
        "vmid": vmid,
        "node": "srv1" if vmid % 2 == 0 else "srv2",
        "name": f"vm-{vmid:04d}",
        "status": "running" if vmid % 3 != 0 else "stopped",
        "pool_id": "",
        "cpu_cores": 4,
        "memory_mib": 4096,
        "template_id": "tmpl-ubuntu-22",
        "created_at": "2026-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# JSON benchmark
# ---------------------------------------------------------------------------

def bench_json(vms: list[dict], lookup_ids: list[int], tmp_dir: Path) -> dict:
    state_file = tmp_dir / "vms.json"
    store = JsonStateStore(state_file, default_factory=list)
    store.save(vms)

    # Warm-up: single read to prime OS page cache
    _ = store.load()

    times: list[float] = []
    for vmid in lookup_ids:
        t0 = time.perf_counter()
        data = store.load()
        result = next((v for v in data if v.get("vmid") == vmid), None)
        t1 = time.perf_counter()
        assert result is not None, f"vm {vmid} not found in JSON"
        times.append((t1 - t0) * 1000)  # ms

    return _stats("JSON full-scan", times)


# ---------------------------------------------------------------------------
# SQLite benchmark
# ---------------------------------------------------------------------------

def bench_sqlite(vms: list[dict], lookup_ids: list[int], tmp_dir: Path) -> dict:
    db_path = tmp_dir / "state.db"
    db = BeagleDb(db_path)
    db.migrate(SCHEMA_DIR)
    repo = VmRepository(db)

    for vm in vms:
        repo.save(vm)

    # Warm-up: single lookup
    repo.get(lookup_ids[0])

    times: list[float] = []
    for vmid in lookup_ids:
        t0 = time.perf_counter()
        result = repo.get(vmid)
        t1 = time.perf_counter()
        assert result is not None, f"vm {vmid} not found in SQLite"
        times.append((t1 - t0) * 1000)  # ms

    return _stats("SQLite indexed", times)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stats(label: str, times: list[float]) -> dict:
    return {
        "label": label,
        "n": len(times),
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
        "mean_ms": round(statistics.mean(times), 3),
        "median_ms": round(statistics.median(times), 3),
        "p95_ms": round(sorted(times)[int(len(times) * 0.95)], 3),
        "p99_ms": round(sorted(times)[int(len(times) * 0.99)], 3),
    }


def _print_results(json_stats: dict, sqlite_stats: dict) -> None:
    print("\n=== Beagle Fleet State Benchmark ===\n")
    for stats in (json_stats, sqlite_stats):
        print(f"  [{stats['label']}] n={stats['n']}")
        print(f"    min={stats['min_ms']}ms  mean={stats['mean_ms']}ms  "
              f"median={stats['median_ms']}ms  p95={stats['p95_ms']}ms  "
              f"p99={stats['p99_ms']}ms  max={stats['max_ms']}ms")

    speedup = json_stats["p99_ms"] / max(sqlite_stats["p99_ms"], 0.001)
    target_ok = sqlite_stats["p99_ms"] < 5.0

    print(f"\n  Speedup (P99): {speedup:.1f}x (SQLite vs JSON)")
    print(f"  Target (SQLite P99 < 5ms): {'PASS' if target_ok else 'FAIL'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=1000, help="Number of VMs to generate (default: 1000)")
    parser.add_argument("--runs", type=int, default=100, help="Number of lookup iterations (default: 100)")
    parser.add_argument("--output-json", metavar="FILE", help="Write results as JSON to FILE")
    args = parser.parse_args()

    count = max(10, int(args.count))
    runs = max(10, int(args.runs))

    print(f"Generating {count} VM records, {runs} lookup iterations...")
    vms = [_make_vm(vmid) for vmid in range(100, 100 + count)]

    # Pick random-ish lookup IDs distributed across the set
    step = max(1, count // runs)
    lookup_ids = [vms[i * step % count]["vmid"] for i in range(runs)]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        json_stats = bench_json(vms, lookup_ids, tmp_path / "json")
        (tmp_path / "json").mkdir(parents=True, exist_ok=True)

        sqlite_stats = bench_sqlite(vms, lookup_ids, tmp_path / "sqlite")
        (tmp_path / "sqlite").mkdir(parents=True, exist_ok=True)

        json_stats = bench_json(vms, lookup_ids, tmp_path / "json2")
        (tmp_path / "json2").mkdir(parents=True, exist_ok=True)

        sqlite_stats = bench_sqlite(vms, lookup_ids, tmp_path / "sqlite2")

    _print_results(json_stats, sqlite_stats)

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump({"json": json_stats, "sqlite": sqlite_stats}, f, indent=2)
        print(f"\n  Results written to {args.output_json}")

    return 0 if sqlite_stats["p99_ms"] < 5.0 else 1


if __name__ == "__main__":
    sys.exit(main())
