#!/usr/bin/env python3
"""
Plan 13 — IAM Tenancy smoke test.

Verifies:
1. Tenant-Isolation: User von Tenant A kann Pool von Tenant B nicht lesen.
2. Custom Role: `pool-operator` (pool:scale only) darf Pool skalieren aber nicht loeschen.

Usage:
  python3 scripts/test-iam-plan13-smoke.py --host 127.0.0.1 --port 9088

Environment:
  BEAGLE_MANAGER_API_TOKEN  — admin bearer token
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

_TS = str(int(time.time()))[-6:]


def _env_token() -> str:
    tok = os.environ.get("BEAGLE_MANAGER_API_TOKEN", "")
    if not tok:
        sys.exit("ERROR: BEAGLE_MANAGER_API_TOKEN not set")
    return tok


class APIClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url
        self.token = token

    def _req(self, method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {token or self.token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.getcode(), json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode())
            except Exception:
                payload = {"error": str(exc)}
            return exc.code, payload

    def get(self, path: str, token: str | None = None) -> tuple[int, dict]:
        return self._req("GET", path, token=token)

    def post(self, path: str, body: dict, token: str | None = None) -> tuple[int, dict]:
        return self._req("POST", path, body=body, token=token)

    def delete(self, path: str, token: str | None = None) -> tuple[int, dict]:
        return self._req("DELETE", path, token=token)

    def login(self, username: str, password: str) -> str | None:
        status, data = self.post("/api/v1/auth/login", {"username": username, "password": password})
        if status == 200:
            tok = data.get("access_token") or data.get("token")
            if tok:
                return str(tok)
        return None


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def cleanup(client: APIClient, usernames: list[str], role_names: list[str], pool_ids: list[str]) -> None:
    for uid in usernames:
        client.delete(f"/api/v1/auth/users/{uid}")
    for rid in role_names:
        client.delete(f"/api/v1/auth/roles/{rid}")
    for pid in pool_ids:
        client.delete(f"/api/v1/pools/{pid}")


# ---------------------------------------------------------------------------
# Test 1: Tenant-Isolation
# ---------------------------------------------------------------------------

def test_tenant_isolation(client: APIClient) -> str:
    """
    1. Create user-a (tenant: tenant-alpha) and user-b (tenant: tenant-beta).
    2. Create pool-alpha (tenant: tenant-alpha) and pool-beta (tenant: tenant-beta) as admin.
    3. List pools as user-a — must not see pool-beta.
    4. List pools as user-b — must not see pool-alpha.
    """
    user_a = f"smoke-ta-{_TS}"
    user_b = f"smoke-tb-{_TS}"
    pool_a = f"pool-alpha-{_TS}"
    pool_b = f"pool-beta-{_TS}"
    pool_reader_role = f"pool-reader-{_TS}"
    pw = "SmokeTest!2026"

    created_users = []
    created_roles = []
    created_pools = []

    try:
        # Create a role with pool:read for tenant users
        status, r = client.post("/api/v1/auth/roles", {
            "name": pool_reader_role,
            "permissions": ["pool:read"],
        })
        assert status in (200, 201), f"create pool-reader role failed: {status} {r}"
        created_roles.append(pool_reader_role)

        # Create users in different tenants
        status, _ = client.post("/api/v1/auth/users", {
            "username": user_a, "password": pw, "role": pool_reader_role,
            "tenant_id": "tenant-alpha",
        })
        assert status in (200, 201), f"create user-a failed: {status}"
        created_users.append(user_a)

        status, _ = client.post("/api/v1/auth/users", {
            "username": user_b, "password": pw, "role": pool_reader_role,
            "tenant_id": "tenant-beta",
        })
        assert status in (200, 201), f"create user-b failed: {status}"
        created_users.append(user_b)

        # Create pools as admin (pools inherit tenant from their tenant_id field)
        status, r = client.post("/api/v1/pools", {
            "pool_id": pool_a, "template_id": "smoke-tpl", "mode": "floating_non_persistent",
            "min_pool_size": 0, "max_pool_size": 1, "warm_pool_size": 0,
            "cpu_cores": 1, "memory_mib": 512,
            "tenant_id": "tenant-alpha",
        })
        assert status in (200, 201), f"create pool-alpha failed: {status} {r}"
        created_pools.append(pool_a)

        status, r = client.post("/api/v1/pools", {
            "pool_id": pool_b, "template_id": "smoke-tpl", "mode": "floating_non_persistent",
            "min_pool_size": 0, "max_pool_size": 1, "warm_pool_size": 0,
            "cpu_cores": 1, "memory_mib": 512,
            "tenant_id": "tenant-beta",
        })
        assert status in (200, 201), f"create pool-beta failed: {status} {r}"
        created_pools.append(pool_b)

        # Grant entitlements as admin: user-a to BOTH pools (tenant-filter is separate from entitlement)
        client.post(f"/api/v1/pools/{pool_a}/entitlements", {
            "action": "add", "user_id": user_a,
        })
        client.post(f"/api/v1/pools/{pool_b}/entitlements", {
            "action": "add", "user_id": user_a,
        })
        client.post(f"/api/v1/pools/{pool_a}/entitlements", {
            "action": "add", "user_id": user_b,
        })
        client.post(f"/api/v1/pools/{pool_b}/entitlements", {
            "action": "add", "user_id": user_b,
        })

        # Login as user-a and user-b
        tok_a = client.login(user_a, pw)
        assert tok_a, f"login as {user_a} failed"
        tok_b = client.login(user_b, pw)
        assert tok_b, f"login as {user_b} failed"

        # User-A has entitlement to both pools, but tenant filter only shows pool-alpha
        _, data_a = client.get("/api/v1/pools", token=tok_a)
        pool_ids_a = {p["pool_id"] for p in data_a.get("pools", [])}
        assert pool_a in pool_ids_a, f"user-a must see pool-alpha, got: {pool_ids_a}"
        assert pool_b not in pool_ids_a, f"tenant isolation FAIL: user-a (tenant-alpha) sees pool-beta (tenant-beta)!"

        # User-B has entitlement to both pools, but tenant filter only shows pool-beta
        _, data_b = client.get("/api/v1/pools", token=tok_b)
        pool_ids_b = {p["pool_id"] for p in data_b.get("pools", [])}
        assert pool_b in pool_ids_b, f"user-b must see pool-beta, got: {pool_ids_b}"
        assert pool_a not in pool_ids_b, f"tenant isolation FAIL: user-b (tenant-beta) sees pool-alpha (tenant-alpha)!"

        # Direct GET for cross-tenant pool must return 404 or 403
        status_cross, _ = client.get(f"/api/v1/pools/{pool_b}", token=tok_a)
        assert status_cross in (403, 404), f"tenant isolation FAIL: user-a can GET pool-beta (status {status_cross})"

        return "ok"

    finally:
        cleanup(client, created_users, created_roles, created_pools)


# ---------------------------------------------------------------------------
# Test 2: Custom Role pool-operator (pool:scale only)
# ---------------------------------------------------------------------------

def test_custom_role_pool_operator(client: APIClient) -> str:
    """
    1. Create role `pool-operator` with permissions = ["pool:scale", "pool:read"].
    2. Create user-op with this role.
    3. Create a pool as admin.
    4. Scale pool as user-op → must succeed (200).
    5. Delete pool as user-op → must fail (403).
    """
    role_name = f"pool-op-{_TS}"
    user_op = f"smoke-op-{_TS}"
    pool_id = f"pool-op-{_TS}"
    pw = "SmokeOp!2026"

    created_users: list[str] = []
    created_roles: list[str] = []
    created_pools: list[str] = []

    try:
        # Create role with pool:scale and pool:read only (NOT pool:write)
        status, r = client.post("/api/v1/auth/roles", {
            "name": role_name,
            "permissions": ["pool:read", "pool:scale"],
        })
        assert status in (200, 201), f"create role failed: {status} {r}"
        created_roles.append(role_name)

        # Create user with that role
        status, _ = client.post("/api/v1/auth/users", {
            "username": user_op, "password": pw, "role": role_name,
        })
        assert status in (200, 201), f"create user-op failed"
        created_users.append(user_op)

        # Create pool as admin
        status, r = client.post("/api/v1/pools", {
            "pool_id": pool_id, "template_id": "smoke-tpl", "mode": "floating_non_persistent",
            "min_pool_size": 0, "max_pool_size": 5, "warm_pool_size": 0,
            "cpu_cores": 1, "memory_mib": 512,
        })
        assert status in (200, 201), f"create pool failed: {status} {r}"
        created_pools.append(pool_id)

        # Grant user-op visibility to pool via entitlement
        client.post(f"/api/v1/pools/{pool_id}/entitlements", {
            "action": "add", "type": "user", "value": user_op,
        })

        # Login as user-op
        tok_op = client.login(user_op, pw)
        assert tok_op, f"login as {user_op} failed"

        # Scale pool → must succeed
        status, r = client.post(f"/api/v1/pools/{pool_id}/scale", {
            "target_size": 1,
        }, token=tok_op)
        assert status == 200, f"pool-op scale FAIL: expected 200 got {status}: {r}"

        # Delete pool → must fail with 403
        status, r = client.delete(f"/api/v1/pools/{pool_id}", token=tok_op)
        assert status == 403, f"custom role FAIL: pool-op deleted pool (status {status}): {r}"

        return "ok"

    finally:
        cleanup(client, created_users, created_roles, created_pools)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9088)
    args = parser.parse_args()
    base_url = f"http://{args.host}:{args.port}"
    client = APIClient(base_url, _env_token())

    tests = [
        ("tenant_isolation", test_tenant_isolation),
        ("custom_role_pool_operator", test_custom_role_pool_operator),
    ]

    results: dict[str, str] = {}
    failures: list[str] = []

    for name, fn in tests:
        print(f"Running {name}...")
        try:
            result = fn(client)
            results[name] = result
            print(f"  {name}: {result}")
        except Exception as exc:
            results[name] = f"FAIL: {exc}"
            failures.append(name)
            print(f"  {name}: FAIL: {exc}")

    print()
    if failures:
        print(f"PLAN13_IAM_SMOKE=FAIL ({', '.join(failures)})")
        sys.exit(1)
    print("PLAN13_IAM_SMOKE=PASS")


if __name__ == "__main__":
    main()
