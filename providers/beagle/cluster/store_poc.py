#!/usr/bin/env python3
"""PoC helper for evaluating cluster-store options for Beagle 7.0.

This utility is intentionally non-production and targets GoFuture plan step 07.1.
It validates etcd leader election behavior and emits a compact SQLite+Litestream
trade-off matrix for two-host deployments.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class EtcdEndpointStatus:
    endpoint: str
    member_id: str
    leader_id: str
    raft_term: int


def _run_checked(command: List[str], timeout: int = 15) -> str:
    completed = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    return completed.stdout


def _normalize_id(raw: Any) -> str:
    if raw is None:
        return ""
    text = str(raw).strip()
    if text.startswith("0x"):
        return text[2:].lower()
    if text.isdigit():
        return format(int(text), "x")
    return text.lower()


def parse_etcd_endpoint_status_json(payload: str) -> List[EtcdEndpointStatus]:
    parsed = json.loads(payload)
    if not isinstance(parsed, list):
        raise ValueError("etcdctl endpoint status payload must be a list")
    result: List[EtcdEndpointStatus] = []
    for entry in parsed:
        endpoint = str(entry.get("Endpoint") or "").strip()
        status = entry.get("Status") or {}
        header = status.get("header") or {}
        member_id = _normalize_id(header.get("member_id"))
        leader_id = _normalize_id(status.get("leader"))
        raft_term_raw = status.get("raftTerm")
        raft_term = int(raft_term_raw) if raft_term_raw is not None else 0
        if not endpoint:
            raise ValueError("etcd endpoint entry missing Endpoint")
        result.append(
            EtcdEndpointStatus(
                endpoint=endpoint,
                member_id=member_id,
                leader_id=leader_id,
                raft_term=raft_term,
            )
        )
    return result


def load_etcd_status(endpoints: str) -> List[EtcdEndpointStatus]:
    raw = _run_checked(["etcdctl", "--endpoints", endpoints, "endpoint", "status", "-w", "json"])
    return parse_etcd_endpoint_status_json(raw)


def assert_single_leader(statuses: List[EtcdEndpointStatus]) -> str:
    leader_ids = {s.leader_id for s in statuses if s.leader_id}
    if len(leader_ids) != 1:
        raise RuntimeError(f"expected exactly one leader, got {sorted(leader_ids)}")
    return next(iter(leader_ids))


def move_leader(endpoints: str, transferee_member_id: str) -> None:
    _run_checked(["etcdctl", "--endpoints", endpoints, "move-leader", transferee_member_id])


def wait_for_new_leader(endpoints: str, previous_leader_id: str, timeout_seconds: int) -> str:
    deadline = time.time() + timeout_seconds
    last_seen: Optional[str] = None
    while time.time() < deadline:
        try:
            statuses = load_etcd_status(endpoints)
            current = assert_single_leader(statuses)
            last_seen = current
            if current != previous_leader_id:
                return current
        except Exception:
            pass
        time.sleep(1.0)
    raise RuntimeError(
        "leader did not change within timeout; "
        f"previous={previous_leader_id}, last_seen={last_seen or 'unknown'}"
    )


def run_etcd_leader_election_poc(endpoints: str, failover_timeout_seconds: int) -> Dict[str, Any]:
    statuses = load_etcd_status(endpoints)
    if len(statuses) < 2:
        raise RuntimeError("need at least two etcd members for the PoC")

    initial_leader = assert_single_leader(statuses)
    candidate = next((s.member_id for s in statuses if s.member_id and s.member_id != initial_leader), None)
    if not candidate:
        raise RuntimeError("could not find a candidate member for leadership transfer")

    move_leader(endpoints, candidate)
    new_leader = wait_for_new_leader(endpoints, previous_leader_id=initial_leader, timeout_seconds=failover_timeout_seconds)
    final_statuses = load_etcd_status(endpoints)

    return {
        "mode": "etcd_leader_election",
        "endpoints": endpoints,
        "members_seen": len(final_statuses),
        "initial_leader": initial_leader,
        "transferee": candidate,
        "new_leader": new_leader,
        "raft_terms": sorted({s.raft_term for s in final_statuses}),
        "result": "pass",
    }


def evaluate_sqlite_litestream() -> Dict[str, Any]:
    litestream_present = bool(shutil_which("litestream"))
    sqlite_present = bool(shutil_which("sqlite3"))

    matrix = {
        "etcd": {
            "consistency": "strong quorum",
            "leader_election": "native raft",
            "failure_model_two_hosts": "requires external witness for safe quorum",
            "operational_footprint": "medium/high",
        },
        "sqlite_litestream": {
            "consistency": "single-writer with async replication",
            "leader_election": "not built-in (needs external lock/raft)",
            "failure_model_two_hosts": "simple failover but potential lag window",
            "operational_footprint": "low",
        },
    }

    recommendation = (
        "Keep etcd with a witness node for Cluster Foundation 7.0. "
        "Use SQLite+Litestream only as a DR replication layer, not as leader-election authority."
    )

    return {
        "mode": "sqlite_litestream_evaluation",
        "binary_presence": {
            "sqlite3": sqlite_present,
            "litestream": litestream_present,
        },
        "matrix": matrix,
        "recommendation": recommendation,
    }


def shutil_which(name: str) -> Optional[str]:
    paths = os.environ.get("PATH", "").split(os.pathsep)
    for base in paths:
        candidate = os.path.join(base, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Cluster-store PoC helper")
    sub = parser.add_subparsers(dest="command", required=True)

    etcd_parser = sub.add_parser("etcd", help="Run etcd leader-election PoC")
    etcd_parser.add_argument(
        "--endpoints",
        required=True,
        help="Comma-separated etcd endpoints, e.g. http://127.0.0.1:23791,http://127.0.0.1:23792",
    )
    etcd_parser.add_argument("--timeout", type=int, default=20, help="Leader change timeout in seconds")

    sub.add_parser("sqlite-eval", help="Emit SQLite+Litestream evaluation matrix")

    args = parser.parse_args(argv)

    try:
        if args.command == "etcd":
            result = run_etcd_leader_election_poc(args.endpoints, args.timeout)
        else:
            result = evaluate_sqlite_litestream()
    except Exception as exc:
        print(json.dumps({"result": "fail", "error": str(exc)}, indent=2, sort_keys=True))
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
