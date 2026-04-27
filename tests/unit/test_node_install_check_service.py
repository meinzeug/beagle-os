from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import sys

SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from node_install_check_service import NodeInstallCheckService
from persistence_support import PersistenceSupportService


def test_submit_report_persists_and_returns_latest_ready_report(tmp_path: Path) -> None:
    service = NodeInstallCheckService(
        state_file=tmp_path / "install-checks.json",
        report_token="secret",
        now=lambda: datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc),
        persistence_support=PersistenceSupportService(),
    )

    result = service.submit_report(
        {
            "device_id": "srv2.beagle-os.com",
            "timestamp": "2026-04-27T11:59:00Z",
            "status": "pass",
            "checks": [{"check": "service:libvirtd", "status": "pass"}],
        },
        remote_addr="10.0.0.2",
    )

    assert result["ok"] is True
    payload = service.list_payload()
    assert payload["latest_ready_report"]["device_id"] == "srv2.beagle-os.com"
    assert payload["reports"][0]["remote_addr"] == "10.0.0.2"


def test_authorization_requires_exact_bearer_token(tmp_path: Path) -> None:
    service = NodeInstallCheckService(
        state_file=tmp_path / "install-checks.json",
        report_token="secret",
        now=lambda: datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc),
        persistence_support=PersistenceSupportService(),
    )

    assert service.is_authorized("Bearer secret") is True
    assert service.is_authorized("Bearer nope") is False
    assert service.is_authorized("") is False
