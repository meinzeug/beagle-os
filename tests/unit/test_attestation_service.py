"""Tests for Attestation Service (GoEnterprise Plan 02, Schritt 2)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from attestation_service import (
    AttestationReport,
    AttestationService,
)


GOOD_PCRS = {
    "pcr0": "abc123def456abc123def456abc123def456abc1",
    "pcr4": "fedcba9876543210fedcba9876543210fedcba98",
    "pcr7": "1234567890abcdef1234567890abcdef12345678",
}


def make_svc(tmp_path: Path) -> AttestationService:
    return AttestationService(
        state_file=tmp_path / "attestation.json",
        utcnow=lambda: "2026-04-25T10:00:00Z",
    )


def make_report(device_id: str, pcrs: dict) -> AttestationReport:
    return AttestationReport(
        device_id=device_id,
        reported_at="2026-04-25T10:00:00Z",
        pcr_values=pcrs,
        signature="fakesig==",
    )


def test_attested_when_pcrs_match(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_baseline("beagle-1.6.0", GOOD_PCRS)
    report = make_report("dev-001", GOOD_PCRS)
    record = svc.validate_report(report, "beagle-1.6.0")
    assert record.status == "attested"
    assert record.failure_reason == ""


def test_compromised_when_pcr_mismatch(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_baseline("beagle-1.6.0", GOOD_PCRS)
    bad_pcrs = dict(GOOD_PCRS)
    bad_pcrs["pcr0"] = "deadbeef" * 5  # tampered
    report = make_report("dev-002", bad_pcrs)
    record = svc.validate_report(report, "beagle-1.6.0")
    assert record.status == "compromised"
    assert "pcr0" in record.failure_reason


def test_unknown_when_no_baseline(tmp_path):
    svc = make_svc(tmp_path)
    report = make_report("dev-003", GOOD_PCRS)
    record = svc.validate_report(report, "unknown-image")
    assert record.status == "unknown"


def test_session_allowed_for_attested(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_baseline("img", GOOD_PCRS)
    svc.validate_report(make_report("dev-001", GOOD_PCRS), "img")
    allowed, _ = svc.is_session_allowed("dev-001")
    assert allowed is True


def test_session_blocked_for_compromised(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_baseline("img", GOOD_PCRS)
    bad = dict(GOOD_PCRS, pcr4="00000000" * 5)
    svc.validate_report(make_report("dev-002", bad), "img")
    allowed, reason = svc.is_session_allowed("dev-002")
    assert allowed is False
    assert "compromised" in reason


def test_session_allowed_no_record(tmp_path):
    svc = make_svc(tmp_path)
    allowed, reason = svc.is_session_allowed("ghost-device")
    assert allowed is True
    assert "no_attestation" in reason


def test_persistence(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_baseline("img", GOOD_PCRS)
    svc.validate_report(make_report("dev-001", GOOD_PCRS), "img")
    svc2 = make_svc(tmp_path)
    record = svc2.get_record("dev-001")
    assert record is not None
    assert record.status == "attested"
