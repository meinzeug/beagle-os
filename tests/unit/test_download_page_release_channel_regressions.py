from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_download_page_shows_stable_and_prerelease_widgets() -> None:
    page = (ROOT / "public-site" / "download" / "index.html").read_text(encoding="utf-8")

    assert 'data-build-status-widget' in page
    assert 'beagle-downloads-status.json' in page
    assert 'beagle-downloads-prerelease-status.json' in page
    assert 'prereleases/&lt;version&gt;' in page or '/beagle-updates/prereleases/&lt;version&gt;/' in page


def test_download_page_loads_build_status_widget_script() -> None:
    page = (ROOT / "public-site" / "download" / "index.html").read_text(encoding="utf-8")

    assert '/assets/js/build-status.js' in page
    assert 'Latest GitHub release' in page
    assert 'Release channels' in page