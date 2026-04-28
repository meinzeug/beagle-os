from __future__ import annotations

import sys
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from pairing_service import PairingService


def test_issue_and_validate_pairing_token() -> None:
    service = PairingService(
        signing_secret="secret-1",
        token_ttl_seconds=120,
        utcnow=lambda: "2026-04-22T12:00:00+00:00",
    )

    token = service.issue_token({"vmid": 100, "node": "beagle-0", "pairing_pin": "1234"})
    payload = service.validate_token(token)

    assert isinstance(payload, dict)
    assert int(payload.get("vmid", 0)) == 100
    assert str(payload.get("node", "")) == "beagle-0"
    assert str(payload.get("pairing_pin", "")) == "1234"


def test_rejects_tampered_pairing_token() -> None:
    service = PairingService(
        signing_secret="secret-2",
        token_ttl_seconds=120,
        utcnow=lambda: "2026-04-22T12:00:00+00:00",
    )
    token = service.issue_token({"vmid": 100, "node": "beagle-0", "pairing_pin": "1234"})
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    assert service.validate_token(tampered) is None


def test_rejects_expired_pairing_token() -> None:
    issue_service = PairingService(
        signing_secret="secret-3",
        token_ttl_seconds=30,
        utcnow=lambda: "2026-04-22T12:00:00+00:00",
    )
    token = issue_service.issue_token({"vmid": 100, "node": "beagle-0", "pairing_pin": "1234"})

    validate_service = PairingService(
        signing_secret="secret-3",
        token_ttl_seconds=30,
        utcnow=lambda: "2026-04-22T12:01:00+00:00",
    )

    assert validate_service.validate_token(token) is None


def test_consume_token_allows_once_then_rejects_replay() -> None:
    service = PairingService(
        signing_secret="secret-4",
        token_ttl_seconds=60,
        utcnow=lambda: "2026-04-22T12:00:00+00:00",
    )
    token = service.issue_token({"vmid": 100, "node": "beagle-0", "pairing_pin": "1234"})

    first = service.consume_token(token)
    second = service.consume_token(token)

    assert isinstance(first, dict)
    assert second is None
