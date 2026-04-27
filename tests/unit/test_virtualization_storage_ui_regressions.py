from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VIRTUALIZATION_JS = ROOT / "website" / "ui" / "virtualization.js"
EVENTS_JS = ROOT / "website" / "ui" / "events.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_storage_detail_actions_are_rendered_in_virtualization_ui() -> None:
    js = _read(VIRTUALIZATION_JS)

    assert "openStoragePoolDetail" in js
    assert "data-storage-detail" in js
    assert "data-storage-file-download" in js
    assert "blobRequest(" in js
    assert "request('/storage/pools/' + encodeURIComponent(pool) + '/files')" in js
    assert "/storage/pools/' + encodeURIComponent(pool) + '/files?filename=" in js


def test_storage_detail_events_are_bound_in_both_views() -> None:
    js = _read(EVENTS_JS)

    assert "button[data-storage-detail]" in js
    assert "openStoragePoolDetail(" in js
    assert "virtualization-storage-cards" in js
    assert "storage-body" in js
