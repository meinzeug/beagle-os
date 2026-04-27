from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_JS = ROOT / "website" / "ui" / "dashboard.js"


def test_dashboard_skips_unauthorized_cluster_pool_and_iam_fetches() -> None:
    js = DASHBOARD_JS.read_text(encoding="utf-8")

    assert "function currentUserPermissions(me)" in js
    assert "function canReadWithPermissions(permissions, permission)" in js
    assert "canReadWithPermissions(permissions, 'cluster:read')" in js
    assert "? request('/nodes/install-checks', { __suppressAuthLock: true })" in js
    assert "canReadWithPermissions(permissions, 'auth:read')" in js
    assert "canReadWithPermissions(permissions, 'pool:read')" in js
    assert "? request('/pools', { __suppressAuthLock: true })" in js
    assert ": Promise.resolve({ pools: [] })" in js
    assert "? request('/sessions', { __suppressAuthLock: true })" in js
    assert ": Promise.resolve({ sessions: [] })" in js
