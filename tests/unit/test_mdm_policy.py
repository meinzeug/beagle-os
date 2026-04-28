"""Tests for MDM Policy Service (GoEnterprise Plan 02, Schritt 3)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from mdm_policy_service import MDMPolicy, MDMPolicyService


def make_svc(tmp_path: Path) -> MDMPolicyService:
    return MDMPolicyService(state_file=tmp_path / "mdm.json")


def test_create_and_get_policy(tmp_path):
    svc = make_svc(tmp_path)
    p = MDMPolicy(
        policy_id="corp",
        name="Corporate",
        allowed_pools=["pool-finance", "pool-hr"],
        screen_lock_timeout_seconds=300,
    )
    svc.create_policy(p)
    got = svc.get_policy("corp")
    assert got is not None
    assert got.screen_lock_timeout_seconds == 300
    assert "pool-finance" in got.allowed_pools


def test_assign_to_device_and_resolve(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(MDMPolicy(policy_id="corp", name="Corp", allowed_pools=["pool-a"]))
    svc.assign_to_device("dev-001", "corp")
    resolved = svc.resolve_policy("dev-001")
    assert resolved.policy_id == "corp"


def test_group_assignment_inherited(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(MDMPolicy(policy_id="lab", name="Lab"))
    svc.assign_to_group("lab-group", "lab")
    resolved = svc.resolve_policy("dev-999", group="lab-group")
    assert resolved.policy_id == "lab"


def test_device_overrides_group(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(MDMPolicy(policy_id="lab", name="Lab"))
    svc.create_policy(MDMPolicy(policy_id="special", name="Special"))
    svc.assign_to_group("lab-group", "lab")
    svc.assign_to_device("dev-001", "special")
    resolved = svc.resolve_policy("dev-001", group="lab-group")
    assert resolved.policy_id == "special"


def test_default_policy_fallback(tmp_path):
    svc = make_svc(tmp_path)
    resolved = svc.resolve_policy("unknown-device")
    assert resolved.policy_id == "__default__"


def test_pool_allowed(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(MDMPolicy(policy_id="restricted", name="R", allowed_pools=["pool-a"]))
    svc.assign_to_device("dev-001", "restricted")
    assert svc.is_pool_allowed("dev-001", "pool-a") is True
    assert svc.is_pool_allowed("dev-001", "pool-b") is False


def test_codec_allowed(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(MDMPolicy(policy_id="hq", name="HQ", allowed_codecs=["h265", "av1"]))
    svc.assign_to_device("dev-001", "hq")
    assert svc.is_codec_allowed("dev-001", "h265") is True
    assert svc.is_codec_allowed("dev-001", "h264") is False


def test_delete_removes_assignments(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(MDMPolicy(policy_id="temp", name="Temp"))
    svc.assign_to_device("dev-001", "temp")
    svc.update_policy(MDMPolicy(policy_id="temp", name="Temp Updated"))
    got = svc.get_policy("temp")
    assert got.name == "Temp Updated"
    assert svc.delete_policy("temp") is True
    assert svc.get_policy("temp") is None
    assert svc.resolve_policy("dev-001").policy_id == "__default__"


def test_clear_assignment_and_list_assignments(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(MDMPolicy(policy_id="corp", name="Corp"))
    svc.assign_to_device("dev-001", "corp")
    svc.assign_to_group("lab", "corp")
    snapshot = svc.list_assignments()
    assert snapshot["device_assignments"]["dev-001"] == "corp"
    assert snapshot["group_assignments"]["lab"] == "corp"
    assert svc.clear_device_assignment("dev-001") is True
    assert svc.clear_group_assignment("lab") is True
    cleared = svc.list_assignments()
    assert cleared["device_assignments"] == {}
    assert cleared["group_assignments"] == {}


def test_bulk_device_assignment_and_clear(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(MDMPolicy(policy_id="corp", name="Corp"))
    updated = svc.assign_to_devices(["dev-001", "dev-002", ""], "corp")
    assert updated == ["dev-001", "dev-002"]
    assert svc.resolve_policy("dev-001").policy_id == "corp"
    assert svc.resolve_policy("dev-002").policy_id == "corp"
    cleared = svc.clear_device_assignments(["dev-001", "dev-003"])
    assert cleared == ["dev-001"]
    assert svc.resolve_policy("dev-001").policy_id == "__default__"


def test_resolve_policy_with_source(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(MDMPolicy(policy_id="lab", name="Lab"))
    svc.assign_to_group("grp-a", "lab")
    policy, source_type, source_id = svc.resolve_policy_with_source("dev-001", "grp-a")
    assert policy.policy_id == "lab"
    assert source_type == "group"
    assert source_id == "grp-a"


def test_validate_policy_rejects_invalid_ranges_and_codecs(tmp_path):
    svc = make_svc(tmp_path)
    validation = svc.validate_policy(
        MDMPolicy(
            policy_id="corp",
            name="Corp",
            allowed_codecs=["h264", "badcodec"],
            max_resolution="320x200",
            update_window_start_hour=24,
            update_window_end_hour=24,
            screen_lock_timeout_seconds=-1,
        )
    )
    assert validation["ok"] is False
    assert any("invalid codecs" in item for item in validation["errors"])
    assert any("max_resolution" in item for item in validation["errors"])
    assert any("update_window_start_hour" in item for item in validation["errors"])
    assert any("screen_lock_timeout_seconds" in item for item in validation["errors"])


def test_describe_effective_policy_conflicts_reports_device_override(tmp_path):
    svc = make_svc(tmp_path)
    svc.create_policy(MDMPolicy(policy_id="group-policy", name="Group"))
    svc.create_policy(MDMPolicy(policy_id="device-policy", name="Device"))
    svc.assign_to_group("grp-a", "group-policy")
    svc.assign_to_device("dev-001", "device-policy")
    conflicts = svc.describe_effective_policy_conflicts("dev-001", "grp-a")
    assert conflicts == ["device assignment overrides group policy group-policy"]
