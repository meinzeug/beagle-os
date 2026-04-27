from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
LIVE_MEDIUM_HELPERS = ROOT_DIR / "thin-client-assistant" / "usb" / "live_medium_helpers.sh"
WRITE_STAGE = ROOT_DIR / "thin-client-assistant" / "usb" / "usb_writer_write_stage.sh"
LIVE_MENU = ROOT_DIR / "thin-client-assistant" / "usb" / "pve-thin-client-live-menu.sh"


def test_live_medium_helpers_consult_manifest_bundled_payload_relpath_first() -> None:
    script = LIVE_MEDIUM_HELPERS.read_text(encoding="utf-8")

    assert 'python3 "$USB_MANIFEST_HELPER" read-bundled-payload-relpath --path "$manifest_path"' in script
    assert 'live_dir="$target/$bundled_relpath"' in script


def test_usb_writer_manifest_records_bundled_payload_relpath() -> None:
    script = WRITE_STAGE.read_text(encoding="utf-8")

    assert 'bundled_payload_relpath="pve-thin-client/live"' in script
    assert 'bundled_payload_relpath="live"' in script
    assert '--bundled-payload-relpath "$bundled_payload_relpath"' in script
    assert '--payload-source-kind bundled-usb' in script


def test_live_menu_prefers_payload_source_url_for_api_defaults() -> None:
    script = LIVE_MENU.read_text(encoding="utf-8")

    assert 'manifest.get("payload_source_url", "") or manifest.get("payload_source", "")' in script
