"""Tests for Stream Policy Service (GoEnterprise Plan 01, Schritt 4)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from stream_policy_service import (
    StreamPolicy,
    StreamPolicyService,
)


def make_svc(tmp_path: Path) -> StreamPolicyService:
    return StreamPolicyService(state_file=tmp_path / "policies.json")


def test_create_and_retrieve_policy(tmp_path):
    svc = make_svc(tmp_path)
    p = StreamPolicy(policy_id="p1", name="High Quality", max_fps=120, max_bitrate_mbps=50)
    svc.create_policy(p)
    got = svc.get_policy("p1")
    assert got is not None
    assert got.max_fps == 120
    assert got.max_bitrate_mbps == 50


def test_duplicate_policy_raises(tmp_path):
    svc = make_svc(tmp_path)
    p = StreamPolicy(policy_id="p1", name="P1")
    svc.create_policy(p)
    with pytest.raises(ValueError):
        svc.create_policy(p)


def test_update_policy(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(StreamPolicy(policy_id="p1", name="P1", max_fps=60))
    svc.update_policy(StreamPolicy(policy_id="p1", name="P1-updated", max_fps=144))
    assert svc.get_policy("p1").max_fps == 144


def test_delete_policy(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(StreamPolicy(policy_id="p1", name="P1"))
    assert svc.delete_policy("p1") is True
    assert svc.get_policy("p1") is None


def test_assign_and_resolve(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(StreamPolicy(policy_id="gaming", name="Gaming", max_fps=144, network_mode="vpn_required"))
    svc.assign_policy("pool-gaming", "gaming")
    resolved = svc.resolve_policy("pool-gaming")
    assert resolved.policy_id == "gaming"
    assert resolved.max_fps == 144


def test_resolve_falls_back_to_default(tmp_path):
    svc = make_svc(tmp_path)
    resolved = svc.resolve_policy("unknown-pool")
    assert resolved.policy_id == "__default__"


def test_vpn_required_blocks_direct_connection(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(StreamPolicy(policy_id="strict", name="Strict", network_mode="vpn_required"))
    svc.assign_policy("pool-strict", "strict")
    allowed, reason = svc.check_connection_allowed("pool-strict", wireguard_active=False)
    assert allowed is False
    assert "403" in reason or "vpn_required" in reason


def test_vpn_required_allows_with_wireguard(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(StreamPolicy(policy_id="strict", name="Strict", network_mode="vpn_required"))
    svc.assign_policy("pool-strict", "strict")
    allowed, _ = svc.check_connection_allowed("pool-strict", wireguard_active=True)
    assert allowed is True


def test_vpn_preferred_allows_without_wireguard(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(StreamPolicy(policy_id="flex", name="Flex", network_mode="vpn_preferred"))
    svc.assign_policy("pool-flex", "flex")
    allowed, _ = svc.check_connection_allowed("pool-flex", wireguard_active=False)
    assert allowed is True


def test_invalid_fps_raises(tmp_path):
    svc = make_svc(tmp_path)
    with pytest.raises(ValueError):
        svc.create_policy(StreamPolicy(policy_id="bad", name="Bad", max_fps=90))


def test_list_policies(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(StreamPolicy(policy_id="a", name="A"))
    svc.create_policy(StreamPolicy(policy_id="b", name="B"))
    assert len(svc.list_policies()) == 2
