from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "thin-client-assistant" / "usb" / "pve-thin-client-usb-installer.sh"


def test_usb_installer_reuses_bootstrap_tree_across_sudo_rerun() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'BOOTSTRAP_DIR="${PVE_DCV_BOOTSTRAP_DIR:-}"' in script
    assert 'if [[ -n "$BOOTSTRAP_DIR" && -d "$BOOTSTRAP_DIR/extracted" ]]; then' in script
    assert 'beagle_installer_log_event "bootstrap_reused" "bootstrap" "ok" "$BOOTSTRAP_DIR"' in script
    assert 'PVE_DCV_BOOTSTRAP_DIR="$BOOTSTRAP_DIR" \\' in script
