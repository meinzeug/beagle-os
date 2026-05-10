from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "apply-system-updates.sh"


def test_system_update_runner_falls_back_to_full_upgrade_for_kept_back_packages() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "count_not_upgraded_packages" in script
    assert "apt-get full-upgrade -y -qq" in script
    assert "Verbleibende Updates werden per full-upgrade installiert" in script


def test_system_update_runner_does_not_report_success_when_updates_remain() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "remaining_after_upgrade" in script
    assert "STATUS_RESULT=\"failed\"" in script
    assert "still not upgraded after automatic upgrade/full-upgrade" in script
