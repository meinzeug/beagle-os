from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "refresh-host-artifacts.sh"


def test_refresh_host_artifacts_seeds_download_status_placeholder_when_missing() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'DOWNLOAD_STATUS_FILE="$ROOT_DIR/dist/beagle-downloads-status.json"' in script
    assert "write_download_status_placeholder()" in script
    assert '"status": "refreshing"' in script
    assert 'write_download_status_placeholder' in script.split('update_refresh_step "prepare-host-downloads" 20', 1)[1]
