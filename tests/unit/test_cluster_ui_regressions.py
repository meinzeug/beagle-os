from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_cluster_reconcile_button_present() -> None:
    html = (ROOT / "website" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "website" / "ui" / "cluster.js").read_text(encoding="utf-8")

    assert 'id="cluster-action-reconcile"' in html
    assert 'data-cluster-reconcile' in html
    assert 'Leader-State-Reconcile' in html
    assert 'reconcileClusterMembership()' in js
    assert "POST('/cluster/reconcile-membership'" not in js
    assert "postJson('/cluster/reconcile-membership'" in js
